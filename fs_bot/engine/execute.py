"""Command/Event execution layer — bridges bot decisions to mechanics.

Phase-4b proof slice. The Sequence-of-Play decision engine
(`game_engine.resolve_card_turn`) records each faction's decision but did
not previously apply it to the board. This module translates a recorded
decision into calls on the already-implemented, already-tested mechanic
functions in `fs_bot/commands/` and `fs_bot/cards/`.

Scope of THIS slice (deliberately narrow — see WIRING_SCOPE.md):
  - Seize  (Roman Command) — the lightest Command, used to validate the
    whole decision -> execution path end to end.
  - Event  — via the existing `card_effects.execute_event` dispatcher.

Every other Command/SA is recognized but intentionally left as a no-op
here (``executed: False, reason: "not yet wired"``) so that enabling
execution does not crash or silently corrupt a full game while the rest
of the integration is built out incrementally.

Design notes:
  - This is OPT-IN. `resolve_card_turn(..., execute=True)` calls it; the
    default (execute=False) preserves the historical record-only behavior
    so existing tests are unaffected.
  - Execution never raises on an unhandled or failing action; it returns a
    structured result so the engine can keep running and tests can assert.
  - Mechanic-level validation (`validate_*`) is enforced inside the mechanic
    functions; CommandError is caught and reported, not propagated.
"""

from fs_bot.rules_consts import EVENT_SHADED
from fs_bot.commands.common import CommandError
from fs_bot.board.pieces import PieceError
from fs_bot.commands.seize import seize_in_region, get_dispersible_tribes
from fs_bot.commands.raid import raid_in_region
from fs_bot.commands.rally import rally_in_region
from fs_bot.battle.resolve import resolve_battle
from fs_bot.commands.sa_besiege import get_besiege_targets
from fs_bot.commands.rally import recruit_in_region
from fs_bot.commands.march import march_group, _flip_origin_pieces
from fs_bot.board.pieces import count_pieces, get_leader_in_region
from fs_bot.map.map_data import get_playable_regions
from fs_bot.bots.bot_common import random_select
from fs_bot.commands.sa_trade import trade as _sa_trade
from fs_bot.commands.sa_settle import settle as _sa_settle
from fs_bot.commands.sa_devastate import devastate_region as _sa_devastate
from fs_bot.commands.sa_intimidate import intimidate as _sa_intimidate
from fs_bot.commands.sa_suborn import suborn as _sa_suborn
from fs_bot.commands.sa_build import build_fort as _sa_build_fort
from fs_bot.commands.sa_build import build_subdue as _sa_build_subdue
from fs_bot.commands.sa_build import build_place_ally as _sa_build_ally
from fs_bot.commands.sa_rampage import rampage as _sa_rampage
from fs_bot.commands.sa_entreat import entreat_replace_piece as _sa_entreat_piece
from fs_bot.commands.sa_entreat import entreat_replace_ally as _sa_entreat_ally
from fs_bot.commands.sa_scout import scout_move as _sa_scout_move
from fs_bot.commands.sa_scout import scout_reveal as _sa_scout_reveal
from fs_bot.board.pieces import count_pieces_by_state as _count_state
from fs_bot.bots.bot_common import np_agrees_to_retreat
from fs_bot.commands.seize import execute_harassment_loss as _seize_harass_loss
from fs_bot.rules_consts import HARASSMENT_WARBANDS_PER_LOSS as _HWB_PER_LOSS
from fs_bot.cards.card_effects import execute_event

# Mechanic functions raise CommandError on rule violations and PieceError
# on invalid piece operations (e.g. a plan gone stale against the board).
# Execution captures both so a partly-infeasible plan resolves as far as it
# legally can rather than crashing the turn.
_EXEC_ERRORS = (CommandError, PieceError)
# Event card handlers are complex and may raise a range of errors when the
# board does not match a card's assumptions (missing pieces, absent params,
# etc.). Such an Event is simply Ineffective in this state — report it rather
# than let one card crash the game.
_EVENT_SAFE_ERRORS = (NotImplementedError, KeyError, ValueError,
                      AttributeError, TypeError, IndexError,
                      CommandError, PieceError)


# Bot command labels (mirror the per-bot ACTION_* constants, which all
# share these string values).
_CMD_EVENT = "Event"
_CMD_SEIZE = "Seize"
_CMD_RAID = "Raid"
_CMD_RALLY = "Rally"
_CMD_BATTLE = "Battle"
_CMD_RECRUIT = "Recruit"
_CMD_MARCH = "March"
_SA_AMBUSH = "Ambush"
_SA_BESIEGE = "Besiege"
_SA_TRADE = "Trade"
_SA_SETTLE = "Settle"
_SA_DEVASTATE = "Devastate"
_SA_INTIMIDATE = "Intimidate"
_SA_SUBORN = "Suborn"
_SA_BUILD = "Build"
_SA_RAMPAGE = "Rampage"
_SA_ENTREAT = "Entreat"
_SA_SCOUT = "Scout"
from fs_bot.rules_consts import ROMANS as _ROMANS_F
from fs_bot.rules_consts import AEDUI as _AEDUI_F
from fs_bot.rules_consts import GERMANS as _GERMANS_F
_SA_ENLIST = "Enlist"
SA_ACTION_NONE_LABEL = "No SA"
# SAs handled inside Battle resolution, not as standalone post-command SAs.
_BATTLE_MODIFYING_SAS = {_SA_AMBUSH, _SA_BESIEGE}
# Standalone SAs that resolve BEFORE the Battle they accompany.
_BEFORE_BATTLE_SAS = {_SA_INTIMIDATE, _SA_DEVASTATE, _SA_ENTREAT}

# Commands recognized but not yet wired in this slice.
_UNWIRED_COMMANDS = set()


def _apply_end_of_action_capabilities(state):
    """Ongoing capability effects checked at the end of any Faction's action.

    A70 (Nervii, shaded): "If Nervii Subdued at end of any Faction's action,
    place Belgic Ally there." Subdued = the Nervii Tribe neither Allied nor
    Dispersed (allied_faction None, status None).
    """
    from fs_bot.cards.capabilities import is_capability_active
    from fs_bot.rules_consts import (BELGAE, NERVII, TRIBE_NERVII, ALLY,
                                     EVENT_SHADED)
    from fs_bot.board.pieces import get_available, place_piece
    if not is_capability_active(state, "A70", EVENT_SHADED):
        return
    ti = state.get("tribes", {}).get(TRIBE_NERVII)
    if (ti and ti.get("allied_faction") is None and ti.get("status") is None
            and get_available(state, BELGAE, ALLY) > 0):
        place_piece(state, NERVII, BELGAE, ALLY)
        ti["allied_faction"] = BELGAE


def _command_executed(result) -> bool:
    """True when a Command result represents at least one legal effect.

    §4.1: a Special Ability accompanies a Command executed in at least one
    Region. An after-Command SA must therefore be withheld when the Command
    itself produced no legal effect (external mixed-matrix playtest, defect
    family 3: e.g. a failed zero-Resource Rally must not still award Trade).
    Before-Command SAs are unaffected (they need transactional handling --
    documented as an open item).
    """
    return bool(result) and result.get("executed") is not False


def _sa_runs_before_command(command, sa):
    """Whether a Command's accompanying Special Activity resolves BEFORE the
    Command rather than after.

    - Intimidate / Devastate / Entreat before a Battle remove or replace enemy
      pieces and so change that Battle's outcome (§8.7.1 / A8.7.1).
    - Roman Build resolves before a Recruit (§8.8.4: "Build before Recruit");
      after a March or Seize it resolves after (the default).
    """
    if command == _CMD_BATTLE and sa in _BEFORE_BATTLE_SAS:
        return True
    if command == _CMD_RECRUIT and sa == _SA_BUILD:
        return True
    return False


def execute_decision(state, faction, decision):
    """Apply a recorded SoP decision to the board, if supported.

    Args:
        state: Game state dict. Modified in place when an action executes.
        faction: The acting faction constant.
        decision: The dict returned by the engine decision_func. For bot
            turns this contains ``bot_action`` (the full action dict).

    A decision carries its executable plan under ``bot_action`` (produced by a
    bot flowchart) or ``player_action`` (produced by a human player / UI). Both
    use the same action shape ({command, regions, sa, sa_regions, details}) and
    execute through the same machinery, so a mixed human/bot game resolves human
    turns identically to bot turns. The only difference: a human Event uses the
    params the player supplied (``details['event_params']``) rather than the NP
    auto-derivation (§8.2.3), since a human chooses for themselves.

    Returns:
        Result dict: always has ``executed`` (bool) and ``command`` (str);
        plus ``reason`` when not executed, or command-specific details when
        executed.
    """
    bot_action = decision.get("bot_action")
    is_human = False
    if not bot_action:
        bot_action = decision.get("player_action")
        is_human = bot_action is not None
    if not bot_action:
        # No executable plan. A human menu that selected only an action TYPE
        # (Command/Event without regions/SA/params) cannot be auto-executed
        # until the plan is collected; report rather than crash.
        return {"executed": False, "command": None,
                "reason": "decision carries no executable plan "
                          "(no bot_action or player_action)"}

    command = bot_action.get("command")

    _COMMAND_HANDLERS = {
        _CMD_EVENT: _execute_event,
        _CMD_SEIZE: _execute_seize,
        _CMD_RAID: _execute_raid,
        _CMD_RALLY: _execute_rally,
        _CMD_BATTLE: _execute_battle,
        _CMD_RECRUIT: _execute_recruit,
        _CMD_MARCH: _execute_march,
    }
    handler = _COMMAND_HANDLERS.get(command)
    if handler is not None:
        sa = bot_action.get("sa")
        # Some SAs resolve BEFORE the Command they accompany: Intimidate,
        # Devastate, and Entreat before a Battle remove/replace enemy pieces
        # and so change that Battle's outcome (§8.7.1 / A8.7.1 / §4.x). Run
        # those first; all other standalone SAs run after the Command. Battle-
        # modifying SAs (Ambush/Besiege) are applied inside _execute_battle.
        before = _sa_runs_before_command(command, sa)
        sa_result = None
        if before:
            sa_result = _execute_sa(state, faction, bot_action)
        if command == _CMD_EVENT:
            result = _execute_event(state, faction, bot_action,
                                    human=is_human)
        else:
            result = handler(state, faction, bot_action)
        if not before:
            if command == _CMD_EVENT or _command_executed(result):
                sa_result = _execute_sa(state, faction, bot_action)
            else:
                result = dict(result)
                result["sa_skipped"] = "command produced no legal effect"
        if sa_result is not None:
            result = dict(result)
            result["sa_execution"] = sa_result
            result["sa_timing"] = "before" if before else "after"
        _apply_end_of_action_capabilities(state)
        return result
    if command in _UNWIRED_COMMANDS:
        return {"executed": False, "command": command,
                "reason": "command not yet wired (proof slice)"}
    # Pass / None / unknown
    return {"executed": False, "command": command,
            "reason": "no executable command"}


def _execute_bot_command(state, faction, bot_action):
    """Route a bot_action's Command (never an Event) to the matching command
    executor. Returns the result dict, or None if the command is not one of
    the wired board Commands."""
    cmd = bot_action.get("command")
    handlers = {
        _CMD_SEIZE: _execute_seize, _CMD_RAID: _execute_raid,
        _CMD_RALLY: _execute_rally, _CMD_BATTLE: _execute_battle,
        _CMD_RECRUIT: _execute_recruit, _CMD_MARCH: _execute_march,
    }
    h = handlers.get(cmd)
    if h is None:
        return None
    sa = bot_action.get("sa")
    before = _sa_runs_before_command(cmd, sa)
    sa_result = None
    if before:
        sa_result = _execute_sa(state, faction, bot_action)
    result = h(state, faction, bot_action)
    if not before:
        if _command_executed(result):
            sa_result = _execute_sa(state, faction, bot_action)
        else:
            result = dict(result)
            result["sa_skipped"] = "command produced no legal effect"
    if sa_result is not None:
        result = dict(result)
        result["sa_execution"] = sa_result
    return result


def _primary_command_region(bot_action):
    """The first Region a Command's plan acts in/from (for a Limited Command's
    single-Region restriction)."""
    cmd = bot_action.get("command")
    d = bot_action.get("details") or {}
    def reg_of(e):
        return e if isinstance(e, str) else (e.get("region") if isinstance(e, dict) else None)
    if cmd == _CMD_BATTLE:
        plan = d.get("battle_plan") or []
        return reg_of(plan[0]) if plan else None
    if cmd == _CMD_RAID:
        plan = d.get("raid_plan") or []
        return reg_of(plan[0]) if plan else None
    if cmd == _CMD_RECRUIT:
        plan = d.get("recruit_plan") or []
        return reg_of(plan[0]) if plan else None
    if cmd == _CMD_RALLY:
        rp = d.get("rally_plan") or {}
        for k in ("citadels", "allies", "warbands"):
            if rp.get(k):
                return reg_of(rp[k][0])
        return None
    if cmd == _CMD_SEIZE:
        regs = bot_action.get("regions") or []
        return regs[0] if regs else None
    if cmd == _CMD_MARCH:
        plan = d.get("march_plan") or d
        origins = plan.get("origins") or []
        if origins:
            o = origins[0]
            return o[0] if isinstance(o, (list, tuple)) else o
        return None
    return None


def _constrain_bot_action(bot_action, allowed):
    """Filter a chosen Command's plan to ``allowed`` Regions (for an event's
    "in/from <Region>" restriction). Returns a constrained copy of the action,
    or None if the Command has no action left within the allowed Regions.
    March is constrained to groups marching FROM an allowed Region ("from the
    destination Region")."""
    cmd = bot_action.get("command")
    ba = dict(bot_action)
    d = dict(bot_action.get("details") or {})

    def reg_of(e):
        return e if isinstance(e, str) else e.get("region")

    if cmd == _CMD_BATTLE:
        plan = [e for e in (d.get("battle_plan") or []) if reg_of(e) in allowed]
        if not plan:
            return None
        d["battle_plan"] = plan
    elif cmd == _CMD_RAID:
        plan = [e for e in (d.get("raid_plan") or []) if reg_of(e) in allowed]
        if not plan:
            return None
        d["raid_plan"] = plan
    elif cmd == _CMD_RECRUIT:
        plan = [e for e in (d.get("recruit_plan") or []) if reg_of(e) in allowed]
        if not plan:
            return None
        d["recruit_plan"] = plan
    elif cmd == _CMD_RALLY:
        rp = d.get("rally_plan") or {}
        new = {k: [e for e in (rp.get(k) or []) if reg_of(e) in allowed]
               for k in ("citadels", "allies", "warbands")}
        if not any(new.values()):
            return None
        d["rally_plan"] = new
    elif cmd == _CMD_SEIZE:
        regs = [r for r in (bot_action.get("regions") or []) if r in allowed]
        if not regs:
            return None
        ba["regions"] = regs
        d["disperse_regions"] = [r for r in (d.get("disperse_regions") or [])
                                 if r in allowed]
    elif cmd == _CMD_MARCH:
        plan = d.get("march_plan") or d
        origins = plan.get("origins") or []
        def onorm(o):
            return o[0] if isinstance(o, (list, tuple)) else o
        keep = [o for o in origins if onorm(o) in allowed]
        if not keep:
            return None
        if "march_plan" in d:
            mp = dict(d["march_plan"]); mp["origins"] = keep
            d["march_plan"] = mp
        else:
            d["origins"] = keep
    else:
        return None
    ba["details"] = d
    ba["sa_regions"] = [r for r in (bot_action.get("sa_regions") or [])
                        if (not isinstance(r, str)) or r in allowed]
    return ba


def _resolve_free_command(state, faction, allowed_regions=None,
                          exclude_commands=None, limited=False):
    """Execute one *free* Command for ``faction`` using its real flowchart.

    Event cards that grant "a free Command" (e.g. card 9 Mons Cevenna, card 70
    shaded) let the Faction take one Command of its choice. The faithful chooser
    is the Faction's own bot flowchart: we ask it for an action with Event-play
    disabled (so it returns a Command + Special Ability, not another Event or a
    recursive Event play), then execute that Command through the existing
    command executors. Game-run Factions (Germans in base, Arverni in
    Ariovistus) have no bot flowchart and are skipped.

    REGION RESTRICTION (cards 9/62/67/70/...): when ``allowed_regions`` is
    given, the Faction's flowchart-best Command is constrained to those
    Regions. If that board-wide best Command cannot act there, we follow the
    Faction's flowchart command order (the order its decision tree considers
    Commands) and take the first whose plan, constrained to the allowed
    Regions, is legal — i.e. "execute a free Command in/from <Region>" per the
    Faction's own command priority (§8.x flowcharts; NP guideline "follow their
    flowcharts"). See _region_restricted_free_command.
    """
    from fs_bot.bots.bot_dispatch import dispatch_bot_turn
    nps = state.get("non_player_factions", set())
    if faction not in nps:
        return {"executed": False, "command": None,
                "reason": "free Command actor is not a bot Faction"}
    prev_event = state.get("can_play_event")
    state["can_play_event"] = False  # force a Command, not an Event
    try:
        bot_action = dispatch_bot_turn(state, faction)
    except Exception as exc:  # BotDispatchError for game-run Factions, etc.
        state["can_play_event"] = prev_event
        return {"executed": False, "command": None, "reason": repr(exc)}
    state["can_play_event"] = prev_event
    cmd = bot_action.get("command")
    if cmd in (None, _CMD_EVENT):
        return {"executed": False, "command": cmd,
                "reason": "flowchart chose no free Command"}
    if exclude_commands and cmd in exclude_commands:
        # e.g. card 35 "no Battles": the flowchart's choice is disallowed here.
        return {"executed": False, "command": cmd,
                "reason": f"{cmd} excluded by card (e.g. no Battles)"}
    if limited:
        # Limited Command (§): one Region, no Special Activity.
        bot_action = dict(bot_action)
        bot_action["sa"] = SA_ACTION_NONE_LABEL
        bot_action["sa_regions"] = []
        primary = _primary_command_region(bot_action)
        if primary is not None:
            allowed_regions = ({primary} if allowed_regions is None
                               else set(allowed_regions) & {primary})
    if allowed_regions is not None:
        constrained = _constrain_bot_action(bot_action, set(allowed_regions))
        if constrained is None:
            # The flowchart's board-wide best Command cannot act in the named
            # Region(s). Follow the Faction's flowchart command order to take
            # its highest-priority Command that legally can (faithful to
            # "execute a free Command in/from <Region>").
            constrained = _region_restricted_free_command(
                state, faction, set(allowed_regions), exclude_commands)
            if constrained is None:
                return {"executed": False, "command": cmd,
                        "reason": "no Command available in the allowed Region(s)"}
        bot_action = constrained
    res = _execute_bot_command(state, faction, bot_action)
    if res is None:
        return {"executed": False, "command": cmd,
                "reason": "chosen Command not executable"}
    return res


# Each Faction's Command nodes in flowchart-decision order (the order its
# decision tree considers Commands). Used to pick a free Command restricted to
# a named Region when the board-wide best cannot act there — §8.5-8.8 / A8.7-8.8
# flowcharts; NP guideline "for free Commands ... follow their flowcharts".
_FACTION_COMMAND_NODE_ORDER = {
    "Romans": ("fs_bot.bots.roman_bot",
               ("node_r_battle", "node_r_march", "node_r_recruit",
                "node_r_seize")),
    "Arverni": ("fs_bot.bots.arverni_bot",
                ("node_v_battle", "node_v_rally", "node_v_march_spread",
                 "node_v_raid", "node_v_march_mass")),
    "Aedui": ("fs_bot.bots.aedui_bot",
              ("node_a_battle", "node_a_rally", "node_a_raid", "node_a_march")),
    "Belgae": ("fs_bot.bots.belgae_bot",
               ("node_b_battle", "node_b_rally", "node_b_raid", "node_b_march")),
    "Germans": ("fs_bot.bots.german_bot",
                ("node_g_battle", "node_g_march_threat", "node_g_raid",
                 "node_g_rally", "node_g_march_expand")),
}


def _region_restricted_free_command(state, faction, allowed_regions,
                                    exclude_commands=None):
    """Pick a free Command for ``faction`` that legally acts within
    ``allowed_regions``, following the Faction's flowchart command order.

    Evaluates each of the Faction's Command nodes (in flowchart-decision
    order), constrains its plan to ``allowed_regions``, and returns the first
    constrained action that has a legal action there — or None if the Faction
    has no Command available in those Region(s). The Command nodes are
    read-only planners; only the returned action is later executed.
    """
    spec = _FACTION_COMMAND_NODE_ORDER.get(faction)
    if spec is None:
        return None
    import importlib, copy
    module_name, node_names = spec
    try:
        module = importlib.import_module(module_name)
    except Exception:
        return None
    exclude = set(exclude_commands or ())
    for node_name in node_names:
        node = getattr(module, node_name, None)
        if node is None:
            continue
        try:
            # Plan on a deep copy: Command nodes consume state["rng"] for
            # §8.3.4 tie-breaks; isolating the copy keeps the real RNG stream
            # deterministic (only the executed Command advances it). The plan
            # is region/target strings, valid to execute on the real state.
            action = node(copy.deepcopy(state))
        except Exception:
            continue  # a node mis-fires out of its flowchart context — skip
        if not isinstance(action, dict):
            continue
        cmd = action.get("command")
        if cmd in (None, _CMD_EVENT, "Pass") or cmd in exclude:
            continue  # _constrain_bot_action also rejects non-Command actions
        constrained = _constrain_bot_action(action, allowed_regions)
        if constrained is not None:
            return constrained
    return None


def _resolve_free_rally(state, faction, allowed_regions=None):
    """Execute a *free* Rally (Recruit for the Romans) for ``faction`` using
    that Faction's own Rally node — node_a/v/b/g_rally, or node_r_recruit. The
    node returns a Rally/Recruit action with its plan; we execute it through
    the command executors, optionally restricting to ``allowed_regions``.
    Game-run Factions and any non-Rally fallthrough yield no action."""
    nodes = {
        "Aedui": ("fs_bot.bots.aedui_bot", "node_a_rally"),
        "Arverni": ("fs_bot.bots.arverni_bot", "node_v_rally"),
        "Belgae": ("fs_bot.bots.belgae_bot", "node_b_rally"),
        "Germans": ("fs_bot.bots.german_bot", "node_g_rally"),
        "Romans": ("fs_bot.bots.roman_bot", "node_r_recruit"),
    }
    spec = nodes.get(faction)
    if spec is None:
        return {"executed": False, "command": None,
                "reason": "no Rally node for Faction"}
    import importlib
    try:
        node = getattr(importlib.import_module(spec[0]), spec[1])
        bot_action = node(state)
    except Exception as exc:
        return {"executed": False, "command": None, "reason": repr(exc)}
    if not bot_action:
        return {"executed": False, "command": None,
                "reason": "Rally node produced no action"}
    cmd = bot_action.get("command")
    if cmd not in (_CMD_RALLY, _CMD_RECRUIT):
        return {"executed": False, "command": cmd,
                "reason": "no free Rally available (node fell through)"}
    if allowed_regions is not None:
        bot_action = _constrain_bot_action(bot_action, set(allowed_regions))
        if bot_action is None:
            return {"executed": False, "command": cmd,
                    "reason": "no Rally action in the allowed Region(s)"}
    res = _execute_bot_command(state, faction, bot_action)
    return res if res is not None else {"executed": False, "command": cmd,
                                        "reason": "Rally not executable"}


# ===========================================================================
# Free-action execution layer (event-granted free Battles/Commands)
# ---------------------------------------------------------------------------
# Several Ariovistus A-cards grant the acting Faction a *free* Battle (or
# Command) within a constrained Region set, sometimes forbidding the
# defender's Retreat. The card handlers set descriptive flags in
# ``state["event_modifiers"]``; nothing consumed them. This layer reads those
# flags after the Event resolves and runs the granted action through the
# existing command executors, choosing targets per the NP Battle guidance
# (§8.8.1 spirit: hit Leaders, then the most enemy mobile force, where the
# acting Faction has an attacking presence).
# ===========================================================================

_BATTLE_PIECE_TYPES = None  # filled lazily to avoid import-time cycles


def _attacker_has_force(state, region, faction):
    """True if ``faction`` has at least one Battle-capable piece in region."""
    from fs_bot.rules_consts import LEGION, AUXILIA, WARBAND
    from fs_bot.board.pieces import count_pieces, get_leader_in_region
    if get_leader_in_region(state, region, faction) is not None:
        return True
    return any(count_pieces(state, region, faction, pt) > 0
               for pt in (LEGION, AUXILIA, WARBAND))


def _rank_free_battle_defender(state, region, faction):
    """Pick the best enemy to Battle in ``region`` for ``faction``.

    Generic §8.8.1-style priority: Leader present, then most Warbands+Legions,
    then most Allies+Citadels in the Region. Returns a faction or None.
    """
    from fs_bot.rules_consts import (FACTIONS, WARBAND, LEGION, AUXILIA,
                                     ALLY, CITADEL)
    from fs_bot.board.pieces import count_pieces, get_leader_in_region
    best, best_key = None, None
    for enemy in FACTIONS:
        if enemy == faction:
            continue
        if count_pieces(state, region, enemy) <= 0:
            continue
        has_leader = 1 if get_leader_in_region(state, region, enemy) else 0
        # Mobile = all Battle-removable mobile pieces (Warbands, Auxilia,
        # Legions) — Roman mobile force is Auxilia+Legions, not Warbands.
        mobile = (count_pieces(state, region, enemy, WARBAND)
                  + count_pieces(state, region, enemy, AUXILIA)
                  + count_pieces(state, region, enemy, LEGION))
        struct = (count_pieces(state, region, enemy, ALLY)
                  + count_pieces(state, region, enemy, CITADEL))
        key = (has_leader, mobile, struct)
        if best_key is None or key > best_key:
            best, best_key = enemy, key
    return best


def _resolve_card_A34_german_pieces(state, faction, limit=3):
    """A34 unshaded: a non-German player uses German pieces to free Battle in up
    to ``limit`` Regions — the Germans Battle the acting Faction's rivals (never
    the acting Faction itself) where the Germans have a Loss-causing force. The
    card also permits free March; the NP takes the Battles, which benefit the
    acting Faction."""
    from fs_bot.rules_consts import (GERMANS, FACTIONS, WARBAND, AUXILIA, LEGION)
    from fs_bot.board.pieces import count_pieces, get_leader_in_region
    from fs_bot.battle.resolve import resolve_battle
    from fs_bot.map.map_data import get_playable_regions
    if faction == GERMANS:
        return []
    out = []
    for region in get_playable_regions(state["scenario"], state.get("capabilities")):
        if len(out) >= limit:
            break
        if not _attacker_has_force(state, region, GERMANS):
            continue
        best, best_key = None, None
        for ef in FACTIONS:
            if ef in (GERMANS, faction) or count_pieces(state, region, ef) <= 0:
                continue
            mobile = (count_pieces(state, region, ef, WARBAND)
                      + count_pieces(state, region, ef, AUXILIA)
                      + count_pieces(state, region, ef, LEGION))
            key = (1 if get_leader_in_region(state, region, ef) else 0, mobile)
            if best_key is None or key > best_key:
                best, best_key = ef, key
        if best is None:
            continue
        rd, rr = _decide_defender_retreat(state, region, GERMANS, best, False)
        try:
            res = resolve_battle(state, region, GERMANS, best,
                                 retreat_declaration=rd, retreat_region=rr)
            out.append({"free_action": "german_battle", "flag": "card_A34",
                        "region": region, "defender": best, "result": res})
        except _EXEC_ERRORS as exc:
            out.append({"free_action": "german_battle", "flag": "card_A34",
                        "region": region, "executed": False, "reason": repr(exc)})
    return out


def _predicted_legion_losses(state, region, attacker):
    """Losses that would fall on Roman Legions if ``attacker`` Battles Romans
    in ``region`` (no Retreat). Romans absorb with Auxilia before Legions
    (default loss order), so Legion Losses = min(Legions, total - Auxilia).

    Implements the Belgic NP instruction "Battle where most Losses forced on
    Legions" for the A21/A28/A57/Legiones card group.
    """
    from fs_bot.rules_consts import ROMANS, LEGION, AUXILIA
    from fs_bot.board.pieces import count_pieces
    from fs_bot.battle.losses import calculate_losses
    if count_pieces(state, region, ROMANS) <= 0:
        return 0
    legions = count_pieces(state, region, ROMANS, LEGION)
    auxilia = count_pieces(state, region, ROMANS, AUXILIA)
    try:
        total = calculate_losses(state, region, attacker, ROMANS,
                                 is_retreat=False)
    except Exception:
        return 0
    return max(0, min(legions, total - auxilia))


def _german_warband_floor_ok(state, region, faction, defender):
    """German NP instruction: "Battle only where Counterattack would not leave
    Ariovistus with fewer than 4 Warbands." The floor only binds in the Region
    holding Ariovistus; elsewhere his Warbands are not in the Battle.
    """
    from fs_bot.rules_consts import (GERMANS, WARBAND, ARIOVISTUS_LEADER)
    from fs_bot.board.pieces import count_pieces, get_leader_in_region
    from fs_bot.battle.losses import calculate_losses
    if get_leader_in_region(state, region, GERMANS) != ARIOVISTUS_LEADER:
        return True
    german_wb = count_pieces(state, region, GERMANS, WARBAND)
    try:
        # Conservative: predict counterattack Losses from the current (pre-
        # attack) defender — an upper bound on German Warbands lost.
        ca = calculate_losses(state, region, defender, GERMANS,
                              is_counterattack=True)
    except Exception:
        ca = 0
    return (german_wb - ca) >= 4


def _choose_free_battle(state, faction, allowed_regions):
    """Choose (region, defender) for a free Battle over ``allowed_regions``.

    Among Regions where the acting Faction has an attacking force and an enemy
    is present, pick the Region with the most enemy mobile pieces (most damage
    potential), then the top-ranked defender there.
    """
    from fs_bot.rules_consts import WARBAND, LEGION, AUXILIA, BELGAE, GERMANS
    from fs_bot.board.pieces import count_pieces

    # Belgic NP: "Battle where most Losses forced on Legions; if none, no
    # play." Score each Region by predicted Roman Legion Losses.
    if faction == BELGAE:
        best = None  # (region, defender, legion_losses)
        for region in allowed_regions:
            if not _attacker_has_force(state, region, faction):
                continue
            ll = _predicted_legion_losses(state, region, faction)
            if ll > 0 and (best is None or ll > best[2]):
                from fs_bot.rules_consts import ROMANS
                best = (region, ROMANS, ll)
        return (best[0], best[1]) if best else (None, None)

    best = None  # (region, defender, enemy_mobile)
    for region in allowed_regions:
        if not _attacker_has_force(state, region, faction):
            continue
        defender = _rank_free_battle_defender(state, region, faction)
        if defender is None:
            continue
        # German NP: skip Regions that would drop Ariovistus below 4 Warbands.
        if faction == GERMANS and not _german_warband_floor_ok(
                state, region, faction, defender):
            continue
        enemy_mobile = (count_pieces(state, region, defender, WARBAND)
                        + count_pieces(state, region, defender, AUXILIA)
                        + count_pieces(state, region, defender, LEGION))
        if best is None or enemy_mobile > best[2]:
            best = (region, defender, enemy_mobile)
    return (best[0], best[1]) if best else (None, None)


def _within1_of(state, region):
    """Region set = the Region itself plus its adjacencies."""
    from fs_bot.map.map_data import get_adjacent
    return {region, *get_adjacent(region, state["scenario"])}


def _free_battle_region_set(state, flag):
    """Map a free-Battle event flag to its constrained Region set."""
    from fs_bot.rules_consts import SEQUANI, BELGICA_REGIONS
    if flag in ("card_A21_first_no_retreat",):
        return _within1_of(state, SEQUANI)
    if flag in ("card_A57_first_no_retreat",):
        return set(BELGICA_REGIONS)
    if flag in ("card_A28_combined_battle",):
        return _within1_of(state, SEQUANI)  # "in and adjacent to Sequani"
    return set()


# Event-modifier flags that grant a single no-Retreat free Battle.
_FREE_FIRST_BATTLE_FLAGS = (
    "card_A21_first_no_retreat",
    "card_A57_first_no_retreat",
    # A28 Admagetobriga: a no-Retreat free Battle in/adjacent to Sequani.
    # The card additionally lets the actor treat Arverni and allied
    # Warbands/Auxilia as its own for this Battle's Losses ("combined
    # Battle"). That augmentation requires multi-Faction Loss math in the
    # battle engine (a Faction cannot literally own another's piece type —
    # e.g. Germans hold no Auxilia), so it is a documented follow-up; the
    # core no-Retreat Battle with the actor's own force is executed here.
    "card_A28_combined_battle",
)

# First-Battle flag -> the matching "optional second Battle there" flag
# (Retreat allowed for the second Battle). §A-card text for A21/A57.
_DOUBLE_BATTLE_FLAG = {
    "card_A21_first_no_retreat": "card_A21_double_battle",
    "card_A57_first_no_retreat": "card_A57_double_battle",
}


def _second_battle_worthwhile(state, faction, region):
    """NP willingness for the optional second free Battle in ``region``.

    The acting Faction takes the second Battle only if it still has an
    attacking force there and a defender with mobile pieces remains (so the
    Battle can still inflict a Loss). Returns the defender or None.
    """
    from fs_bot.rules_consts import WARBAND, LEGION, AUXILIA
    from fs_bot.board.pieces import count_pieces
    if not _attacker_has_force(state, region, faction):
        return None
    defender = _rank_free_battle_defender(state, region, faction)
    if defender is None:
        return None
    enemy_mobile = (count_pieces(state, region, defender, WARBAND)
                    + count_pieces(state, region, defender, AUXILIA)
                    + count_pieces(state, region, defender, LEGION))
    return defender if enemy_mobile > 0 else None



# One-shot Event flags consumed by _resolve_free_actions. Immediate
# free actions must not survive into later Events: stale flags made a
# later unrelated Event replay old free Commands/Battles (external
# mixed-matrix playtest, defect family 1). Persistent modifiers read
# by later phases (lost_eagle_no_shift_down, optimates_active,
# card_A63_quarters_devastated_only, card_A66_winter_uprising) are
# deliberately NOT listed.
_ONE_SHOT_FREE_ACTION_FLAGS = (
    "card_11_battle_region",
    "card_11_double_auxilia_losses",
    "card_11a_auxilia_battle",
    "card_11a_battle_region",
    "card_17_german_ambush",
    "card_17_germans_phase",
    "card_17_march_german_groups",
    "card_21_no_fort",
    "card_25_battle_region",
    "card_25_extra_losses",
    "card_26_arverni_rally",
    "card_2_auto_legion_loss",
    "card_2_battle_region",
    "card_34_free_rally",
    "card_35_free_limited_command",
    "card_35_gallic_commands",
    "card_36_free_battle",
    "card_36_gallic_ambush_battle",
    "card_44_free_raid",
    "card_44_free_scout",
    "card_44a_free_command",
    "card_45_battle_romans",
    "card_46_free_command",
    "card_47_council",
    "card_48_druids",
    "card_48_target_factions",
    "card_4_free_march_to",
    "card_51_aedui_free_command",
    "card_51_german_action",
    "card_52_free_command_sa",
    "card_54_joined_ranks",
    "card_54_march_limit",
    "card_54a_second_always_retreat",
    "card_57_march_britannia",
    "card_58_german_march_battle",
    "card_62_war_fleet",
    "card_64_belgae_rally",
    "card_65_german_march_ambush",
    "card_65_march_regions",
    "card_66_german_rally_march",
    "card_67_arduenna",
    "card_6_double_auxilia_losses",
    "card_70_free_command_sa",
    "card_70_legion_limit",
    "card_70_roman_march_battle",
    "card_70_target_regions",
    "card_72_hidden_march_battle",
    "card_9_free_march_and_command",
    "card_9_march_from",
    "card_9_march_to",
    "card_A17_roman_march_battle",
    "card_A19_march_romans",
    "card_A20_arverni_ambush",
    "card_A20_free_seize_veneti",
    "card_A21_double_battle",
    "card_A21_first_no_retreat",
    "card_A24_arverni_phase",
    "card_A27_arverni_phase",
    "card_A28_combined_battle",
    "card_A29_german_raid",
    "card_A32_arverni_phase",
    "card_A34_free_command",
    "card_A34_regions_limit",
    "card_A34_use_german_pieces",
    "card_A37_place_allies_move",
    "card_A45_free_intimidate",
    "card_A53_aedui_corn",
    "card_A57_double_battle",
    "card_A57_first_no_retreat",
    "card_A58_free_ambush",
    "card_A58_roman_battle_seize",
    "card_A5_remove_non_romans",
    "card_A65_kinship_battle",
    "card_A67_arduenna",
    "card_A69_ambush",
)

def _resolve_free_actions(state, faction):
    """Run any free actions granted by the just-resolved Event.

    Called from ``_execute_event`` for the acting Faction. Returns a list of
    result dicts (possibly empty). Errors in an individual free action are
    captured, not raised, to keep a full game running.
    """
    mods = state.get("event_modifiers") or {}
    results = []
    for flag in _FREE_FIRST_BATTLE_FLAGS:
        if not mods.get(flag):
            continue
        allowed = _free_battle_region_set(state, flag)
        region, defender = _choose_free_battle(state, faction, allowed)
        if region is None:
            results.append({"free_action": "battle", "flag": flag,
                            "executed": False, "reason": "no valid target"})
            continue
        from fs_bot.rules_consts import ARVERNI as _ARVERNI
        _details = {"battle_plan": [{"region": region, "target": defender}],
                    "no_retreat": True}
        if flag == "card_A28_combined_battle":
            _details["allied_factions"] = (_ARVERNI,)  # treat Arverni as own
        try:
            res = _execute_battle(state, faction, {
                "command": _CMD_BATTLE, "sa": SA_ACTION_NONE_LABEL,
                "sa_regions": [], "details": _details})
        except _EXEC_ERRORS as exc:
            results.append({"free_action": "battle", "flag": flag,
                            "executed": False, "reason": repr(exc)})
            continue
        results.append({"free_action": "battle", "flag": flag,
                        "region": region, "defender": defender,
                        "result": res})
        # Optional second Battle in the same Region (Retreat allowed).
        dbl = _DOUBLE_BATTLE_FLAG.get(flag)
        if dbl and mods.get(dbl):
            second = _second_battle_worthwhile(state, faction, region)
            if second is not None:
                try:
                    res2 = _execute_battle(state, faction, {
                        "command": _CMD_BATTLE, "sa": SA_ACTION_NONE_LABEL,
                        "sa_regions": [],
                        "details": {"battle_plan": [{"region": region,
                                                     "target": second}]}})
                    results.append({"free_action": "battle_second",
                                    "flag": dbl, "region": region,
                                    "defender": second, "result": res2})
                except _EXEC_ERRORS as exc:
                    results.append({"free_action": "battle_second",
                                    "flag": dbl, "region": region,
                                    "executed": False, "reason": repr(exc)})

    # A58 Aduatuci (unshaded): Romans free Battle anywhere in Belgica, then
    # free Seize in Belgica "as if Roman Control, with no Harassment" — the
    # Seize Disperses regardless of actual Control and skips Harassment.
    if mods.get("card_A58_roman_battle_seize"):
        results.extend(_resolve_a58_battle_seize(state, faction))
    if mods.get("card_A67_arduenna"):
        # A67 = base 67 effect, "updated to allow German use" (A Card Ref). A
        # non-German actor (Be/Ae/Ro) uses the faction-agnostic base resolver;
        # the German path has its own (March-to-Control + Battle + flip Hidden).
        from fs_bot.rules_consts import GERMANS as _G67
        if faction == _G67:
            results.extend(_resolve_a67_arduenna(state, faction))
        else:
            results.extend(_resolve_card67_arduenna(state, faction))
    if mods.get("card_A20_free_seize_veneti"):
        results.extend(_resolve_a20_free_seize(state))
    if mods.get("card_A20_arverni_ambush"):
        results.extend(_resolve_a20_arverni_ambush(state))
    if mods.get("card_A17_roman_march_battle"):
        results.extend(_resolve_a17_march_battle(state))
    if mods.get("card_A19_march_romans"):
        results.extend(_resolve_a19_march_romans(state, faction))
    if mods.get("card_6_double_auxilia_losses"):
        results.extend(_resolve_card6_scout_battle(state))
    if mods.get("card_11_double_auxilia_losses"):
        results.extend(_resolve_double_aux_battle_card(
            state, mods.get("card_11_battle_region"), "card_11"))
    if mods.get("card_11a_auxilia_battle"):
        results.extend(_resolve_double_aux_battle_card(
            state, mods.get("card_11a_battle_region"), "card_11a"))
    if mods.get("card_2_auto_legion_loss"):
        results.extend(_resolve_card2_battle(
            state, faction, mods.get("card_2_battle_region")))
    if mods.get("card_70_roman_march_battle"):
        results.extend(_resolve_card70_march_battle(
            state, mods.get("card_70_target_regions"),
            mods.get("card_70_legion_limit", 4)))
    if mods.get("card_72_hidden_march_battle"):
        results.extend(_resolve_card72_hidden_march_battle(state, faction))
    if mods.get("card_58_german_march_battle"):
        results.extend(_resolve_card58_german_ambush(state))
    if mods.get("card_65_german_march_ambush"):
        results.extend(_resolve_card65_german_march_ambush(
            state, mods.get("card_65_march_regions", 2)))
    if mods.get("card_17_german_ambush"):
        results.extend(_resolve_card17_march_ambush(
            state, mods.get("card_17_march_german_groups", 3)))
    if mods.get("card_17_germans_phase"):
        results.extend(_resolve_card17_germans_phase(state))
    if mods.get("card_57_march_britannia"):
        results.extend(_resolve_card57_britannia_march(state, faction))
    if mods.get("card_4_free_march_to"):
        results.extend(_resolve_card4_circumvallation(
            state, mods.get("card_4_free_march_to")))
    if mods.get("card_9_free_march_and_command"):
        results.extend(_resolve_card9_march_command(
            state, faction, mods.get("card_9_march_from"),
            mods.get("card_9_march_to")))
    if mods.get("card_70_free_command_sa"):
        results.extend(_resolve_card70_free_command(state, faction))
    if mods.get("card_46_free_command"):
        results.append({"free_action": "free_command", "flag": "card_46",
                        "result": _resolve_free_command(state, faction)})
    if mods.get("card_51_aedui_free_command"):
        from fs_bot.rules_consts import AEDUI as _AEDUI
        results.append({"free_action": "free_command", "flag": "card_51",
                        "result": _resolve_free_command(state, _AEDUI)})
    if mods.get("card_52_free_command_sa"):
        results.extend(_resolve_card52_free_command(state))
    if mods.get("card_35_gallic_commands"):
        results.extend(_resolve_card35_gallic(state, faction))
    if mods.get("card_35_free_limited_command"):
        results.extend(_resolve_card35_roman(state, faction))
    if mods.get("card_34_free_rally"):
        results.append({"free_action": "free_rally", "flag": "card_34",
                        "result": _resolve_free_rally(state, faction)})
    if mods.get("card_26_arverni_rally"):
        results.extend(_resolve_card26_arverni_rally(state))
    if mods.get("card_64_belgae_rally"):
        results.extend(_resolve_card64_belgae_rally(state))
    if mods.get("card_25_extra_losses"):
        results.extend(_resolve_card25_battle(
            state, faction, mods.get("card_25_battle_region"),
            mods.get("card_25_extra_losses", 3)))
    if mods.get("card_36_free_battle"):
        results.extend(_resolve_card36_battle(state, faction))
    if mods.get("card_36_gallic_ambush_battle"):
        results.extend(_resolve_card36_shaded(state, faction))
    if mods.get("card_66_german_rally_march"):
        results.extend(_resolve_card66_german_rally_march(state))
    if mods.get("card_21_no_fort"):
        results.extend(_resolve_card21_provincia_battle(state))
    if mods.get("card_45_battle_romans"):
        results.extend(_resolve_card45_battle(state, faction))
    if mods.get("card_54_joined_ranks"):
        results.extend(_resolve_card54_joined_ranks(
            state, faction, mods.get("card_54_march_limit", 8),
            bool(mods.get("card_54a_second_always_retreat"))))
    if mods.get("card_44_free_scout"):
        results.extend(_resolve_card44_scout(state))
    if mods.get("card_44_free_raid"):
        results.extend(_resolve_card44_raid(state, faction))
    if mods.get("card_48_druids"):
        results.extend(_resolve_card48_druids(
            state, mods.get("card_48_target_factions")))
    if mods.get("card_47_council"):
        results.extend(_resolve_card47_council(state))
    if mods.get("card_62_war_fleet"):
        results.extend(_resolve_card62_war_fleet(state, faction))
    if (mods.get("card_A24_arverni_phase") or mods.get("card_A27_arverni_phase")
            or mods.get("card_A32_arverni_phase")):
        results.extend(_resolve_event_arverni_phase(state))
    if mods.get("card_51_german_action"):
        # Germans are game-run (no flowchart): act with the placed Warbands via
        # an Ambush sweep (the aggressive "March/Raid/Battle" option).
        from fs_bot.rules_consts import GERMANS as _G
        results.append({"free_action": "german_ambush", "flag": "card_51",
                        "ambushes": _faction_ambush_sweep(state, _G)})
    if mods.get("card_44a_free_command"):
        # NOTE: card 44 (Ariovistus) shaded says "in Regions placed"; the
        # region restriction is a documented refinement (see QUESTIONS.md) —
        # the chooser is faithful but board-wide here.
        results.append({"free_action": "free_command", "flag": "card_44a",
                        "result": _resolve_free_command(state, faction)})
    if mods.get("card_A29_german_raid"):
        results.extend(_resolve_card_A29_raid(state))
    if mods.get("card_A34_use_german_pieces"):
        results.extend(_resolve_card_A34_german_pieces(
            state, faction, mods.get("card_A34_regions_limit", 3)))
    if mods.get("card_A34_free_command"):
        results.append({"free_action": "free_command", "flag": "card_A34",
                        "result": _resolve_free_command(state, faction)})
    if mods.get("card_A65_kinship_battle"):
        results.extend(_resolve_card_A65_battle(state, faction))
    if mods.get("card_A69_ambush"):
        results.extend(_resolve_card_A69_ambush(state))
    if mods.get("card_A58_free_ambush"):
        from fs_bot.rules_consts import ROMANS as _ROM
        results.append({"free_action": "ambush", "flag": "card_A58",
                        "ambushes": _faction_ambush_sweep(state, faction,
                                                          only_faction=_ROM)})
    if mods.get("card_A45_free_intimidate"):
        results.extend(_resolve_card_A45_intimidate(state))
    if mods.get("card_67_arduenna"):
        results.extend(_resolve_card67_arduenna(state, faction))
    if mods.get("card_A5_remove_non_romans"):
        results.extend(_resolve_card_A5_evict(state))
    if mods.get("card_A37_place_allies_move"):
        results.extend(_resolve_card_A37_move(state, faction))
    if mods.get("card_A53_aedui_corn"):
        results.extend(_resolve_card_A53_frumentum(state))
    # Consume the one-shot flags now that their actions resolved.
    em = state.get("event_modifiers")
    if em:
        for _flag in _ONE_SHOT_FREE_ACTION_FLAGS:
            em.pop(_flag, None)
    return results


def _resolve_card_A29_raid(state):
    """Card A29 (shaded): the placed German Warbands free Raid — Raid in each
    Region where the Germans have Warbands and an enemy with Resources is
    present."""
    from fs_bot.rules_consts import GERMANS, WARBAND, FACTIONS
    from fs_bot.board.pieces import count_pieces
    from fs_bot.map.map_data import get_playable_regions
    raid_plan = []
    for region in get_playable_regions(state["scenario"], state.get("capabilities")):
        if count_pieces(state, region, GERMANS, WARBAND) <= 0:
            continue
        target = next((f for f in FACTIONS if f != GERMANS
                       and count_pieces(state, region, f) > 0
                       and state["resources"].get(f, 0) > 0), None)
        raid_plan.append({"region": region, "target": target})
    if not raid_plan:
        return [{"free_action": "raid", "flag": "card_A29", "executed": False,
                 "reason": "no German Warband Region to Raid"}]
    try:
        res = _execute_raid(state, GERMANS, {"command": _CMD_RAID,
              "sa": SA_ACTION_NONE_LABEL, "sa_regions": [],
              "details": {"raid_plan": raid_plan}})
    except _EXEC_ERRORS as exc:
        return [{"free_action": "raid", "flag": "card_A29",
                 "executed": False, "reason": repr(exc)}]
    return [{"free_action": "raid", "flag": "card_A29", "result": res}]


def _resolve_card_A65_battle(state, faction):
    """Card A65 Kinship (unshaded): Belgae (without Leader) Battle Germans, or
    Germans (without Leader) Battle Belgae — in the Region where the acting
    Faction can hit the most of the opponent's pieces."""
    from fs_bot.rules_consts import BELGAE, GERMANS, WARBAND, AUXILIA, LEGION
    from fs_bot.board.pieces import count_pieces
    from fs_bot.map.map_data import get_playable_regions
    if faction not in (BELGAE, GERMANS):
        return [{"free_action": "battle", "flag": "card_A65", "executed": False,
                 "reason": "only Belgae or Germans Battle here"}]
    opp = GERMANS if faction == BELGAE else BELGAE
    best = None
    for R in get_playable_regions(state["scenario"], state.get("capabilities")):
        if not _attacker_has_force(state, R, faction):
            continue
        mob = (count_pieces(state, R, opp, WARBAND)
               + count_pieces(state, R, opp, AUXILIA)
               + count_pieces(state, R, opp, LEGION))
        if count_pieces(state, R, opp) > 0 and (best is None or mob > best[1]):
            best = (R, mob)
    if best is None:
        return [{"free_action": "battle", "flag": "card_A65", "executed": False,
                 "reason": "no opponent to Battle"}]
    R = best[0]
    from fs_bot.battle.resolve import resolve_battle
    rd, rr = _decide_defender_retreat(state, R, faction, opp, False)
    try:
        res = resolve_battle(state, R, faction, opp, no_attacker_leader=True,
                             retreat_declaration=rd, retreat_region=rr)
    except _EXEC_ERRORS as exc:
        return [{"free_action": "battle", "flag": "card_A65",
                 "executed": False, "reason": repr(exc)}]
    return [{"free_action": "battle", "flag": "card_A65", "region": R,
             "defender": opp, "result": res}]


def _resolve_card_A69_ambush(state):
    """Card A69 Bellovaci (shaded): the 6 placed Belgic Warbands Ambush at
    Bellovaci, causing 1 Loss each (warband_full_loss)."""
    from fs_bot.rules_consts import BELGAE, TRIBE_BELLOVACI, TRIBE_TO_REGION
    R = TRIBE_TO_REGION.get(TRIBE_BELLOVACI)
    if R is None:
        return [{"free_action": "ambush", "flag": "card_A69", "executed": False,
                 "reason": "Bellovaci region unknown"}]
    defender = _faction_ambush_target(state, R, BELGAE)
    if defender is None:
        return [{"free_action": "ambush", "flag": "card_A69", "executed": False,
                 "reason": "no legal Belgic Ambush at Bellovaci"}]
    try:
        res = _execute_battle(state, BELGAE, {
            "command": _CMD_BATTLE, "sa": _SA_AMBUSH, "sa_regions": [R],
            "details": {"battle_plan": [{"region": R, "target": defender}],
                        "warband_full_loss": True}})
    except _EXEC_ERRORS as exc:
        return [{"free_action": "ambush", "flag": "card_A69",
                 "executed": False, "reason": repr(exc)}]
    return [{"free_action": "ambush", "flag": "card_A69", "region": R,
             "defender": defender, "result": res}]


def _resolve_card_A45_intimidate(state):
    """Card A45 Savage Dictates (shaded): the Germans free Intimidate anywhere.
    Build a plan flipping Hidden German Warbands to remove enemy pieces in each
    Region where the Germans have Hidden Warbands and an enemy has removable
    mobile pieces (most-pieces enemy, up to 2 per Region)."""
    from fs_bot.rules_consts import (GERMANS, FACTIONS, WARBAND, AUXILIA,
                                     LEGION, HIDDEN, REVEALED)
    from fs_bot.board.pieces import count_pieces, count_pieces_by_state
    from fs_bot.map.map_data import get_playable_regions
    plan = []
    for region in get_playable_regions(state["scenario"], state.get("capabilities")):
        gh = count_pieces_by_state(state, region, GERMANS, WARBAND, HIDDEN)
        if gh <= 0:
            continue
        # Pick the enemy with the most removable mobile pieces here.
        best, best_n = None, 0
        for ef in FACTIONS:
            if ef == GERMANS:
                continue
            n = (count_pieces(state, region, ef, WARBAND)
                 + count_pieces(state, region, ef, AUXILIA)
                 + count_pieces(state, region, ef, LEGION))
            if n > best_n:
                best, best_n = ef, n
        if best is None:
            continue
        # Up to min(2, gh) removals of that enemy's mobile pieces.
        removable = []
        for pt in (WARBAND, AUXILIA, LEGION):
            for ps in (HIDDEN, REVEALED, None):
                if pt == LEGION and ps is not None:
                    continue
                cnt = (count_pieces(state, region, best, pt) if ps is None
                       else count_pieces_by_state(state, region, best, pt, ps))
                for _ in range(cnt):
                    removable.append((pt, ps if pt != LEGION else None))
        for (pt, ps) in removable[:min(2, gh)]:
            plan.append({"region": region, "target_faction": best,
                         "target_piece": pt, "target_state": ps})
    if not plan:
        return [{"free_action": "intimidate", "flag": "card_A45",
                 "executed": False, "reason": "no German Intimidate available"}]
    res = _execute_intimidate(state, GERMANS,
                              {"details": {"intimidate_plan": plan}})
    return [{"free_action": "intimidate", "flag": "card_A45", "result": res}]


def _resolve_card_A5_evict(state):
    """Card A5 Gallia Togata (unshaded): only Romans may stack in Cisalpina, so
    non-Roman pieces there move to a Home Region of their Faction (or are
    removed if none is available)."""
    from fs_bot.rules_consts import (CISALPINA, ARVERNI, AEDUI, BELGAE, GERMANS,
        LEADER, LEGION, AUXILIA, WARBAND, HIDDEN, REVEALED, SCOUTED, ARIOVISTUS_SCENARIOS,
        ARVERNI_HOME_REGIONS_BASE, ARVERNI_HOME_REGIONS_ARIOVISTUS,
        AEDUI_HOME_REGIONS, BELGAE_HOME_REGIONS,
        GERMAN_HOME_REGIONS_BASE)
    from fs_bot.board.pieces import (count_pieces, count_pieces_by_state,
        get_leader_in_region, move_piece, remove_piece)
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_playable_regions
    scen = state["scenario"]
    ario = scen in ARIOVISTUS_SCENARIOS
    homes = {
        ARVERNI: (ARVERNI_HOME_REGIONS_ARIOVISTUS if ario
                  else ARVERNI_HOME_REGIONS_BASE),
        AEDUI: AEDUI_HOME_REGIONS, BELGAE: BELGAE_HOME_REGIONS,
        GERMANS: GERMAN_HOME_REGIONS_BASE,
    }
    playable = set(get_playable_regions(scen, state.get("capabilities")))
    moved, removed = [], []
    for fac in (ARVERNI, AEDUI, BELGAE, GERMANS):
        dest = next((h for h in homes.get(fac, ()) if h in playable
                     and h != CISALPINA), None)
        # Leader
        if get_leader_in_region(state, CISALPINA, fac) is not None:
            if dest:
                move_piece(state, CISALPINA, dest, fac, LEADER)
                moved.append((fac, LEADER, dest))
            else:
                remove_piece(state, CISALPINA, fac, LEADER); removed.append((fac, LEADER))
        leg = count_pieces(state, CISALPINA, fac, LEGION)
        if leg:
            (move_piece(state, CISALPINA, dest, fac, LEGION, count=leg) if dest
             else remove_piece(state, CISALPINA, fac, LEGION, count=leg))
        for pt in (AUXILIA, WARBAND):
            for ps in (HIDDEN, REVEALED, SCOUTED):
                n = count_pieces_by_state(state, CISALPINA, fac, pt, ps)
                if n <= 0:
                    continue
                if dest:
                    move_piece(state, CISALPINA, dest, fac, pt, count=n,
                               piece_state=ps)
                    moved.append((fac, pt, dest))
                else:
                    remove_piece(state, CISALPINA, fac, pt, count=n,
                                 piece_state=ps)
                    removed.append((fac, pt))
    refresh_all_control(state)
    return [{"free_action": "evict_cisalpina", "flag": "card_A5",
             "moved": moved, "removed": removed,
             "executed": bool(moved or removed)}]


def _resolve_card_A37_move(state, faction):
    """Card A37 (unshaded): after placing an Ally in a Celtica Region within 1
    of German Control, the Faction moves its Leader and Warbands/Auxilia there
    from an adjacent Region (consolidating at the new Ally)."""
    from fs_bot.rules_consts import (AEDUI, ROMANS, ALLY, CELTICA_REGIONS,
                                     GERMANS)
    from fs_bot.board.pieces import count_pieces
    from fs_bot.board.control import is_controlled_by
    from fs_bot.map.map_data import get_adjacent
    if faction not in (AEDUI, ROMANS):
        return [{"free_action": "march", "flag": "card_A37", "executed": False,
                 "reason": "only Aedui/Romans"}]
    scen = state["scenario"]
    # Target = a Celtica Region (within 1 of German Control) where the Faction
    # now has an Ally.
    dest = None
    for region in CELTICA_REGIONS:
        if count_pieces(state, region, faction, ALLY) <= 0:
            continue
        if is_controlled_by(state, region, GERMANS) or any(
                is_controlled_by(state, a, GERMANS)
                for a in get_adjacent(region, scen)):
            dest = region
            break
    if dest is None:
        return [{"free_action": "march", "flag": "card_A37", "executed": False,
                 "reason": "no Ally Region to move to"}]
    srcs = [a for a in get_adjacent(dest, scen)
            if _group_has_pieces(_mobile_march_group(state, faction, a))]
    if not srcs:
        return [{"free_action": "march", "flag": "card_A37", "region": dest,
                 "executed": False, "reason": "no adjacent group to move"}]
    from fs_bot.rules_consts import LEGION, AUXILIA, WARBAND
    S = max(srcs, key=lambda a: sum(count_pieces(state, a, faction, pt)
                                    for pt in (LEGION, AUXILIA, WARBAND)))
    try:
        _march_with_harassment(state, faction, S, [dest])
    except _EXEC_ERRORS as exc:
        return [{"free_action": "march", "flag": "card_A37", "region": dest,
                 "executed": False, "reason": repr(exc)}]
    return [{"free_action": "march", "flag": "card_A37", "source": S,
             "region": dest}]


def _resolve_card_A53_frumentum(state):
    """Card A53 Frumentum (unshaded): the Aedui lend Resources and the Romans
    spend them on a free Recruit + March + Special Activity. We transfer a
    modest amount of Aedui Resources to the Romans (an NP "specified amount"),
    then run a free Roman Recruit and a free Roman March."""
    from fs_bot.rules_consts import AEDUI, ROMANS
    from fs_bot.cards.card_effects import _cap_resources
    out = []
    lend = min(state["resources"].get(AEDUI, 0), 6)
    if lend > 0:
        _cap_resources(state, AEDUI, -lend)
        _cap_resources(state, ROMANS, lend)
        out.append({"free_action": "resource_transfer", "flag": "card_A53",
                    "from": AEDUI, "to": ROMANS, "amount": lend})
    # Roman free Recruit (node_r_recruit via the free-Rally layer) + free March.
    out.append({"free_action": "free_recruit", "flag": "card_A53",
                "result": _resolve_free_rally(state, ROMANS)})
    out.append({"free_action": "free_march", "flag": "card_A53",
                "result": _resolve_free_march(state, ROMANS)})
    # ...+ 1 free Special Activity. The Roman NP's default SA is Build (both
    # node_r_recruit and node_r_march select Build, §8.8.1/§8.8.4); run it free.
    sa_res = _execute_sa(state, ROMANS, {"sa": _SA_BUILD, "sa_regions": [],
                                         "details": {}})
    out.append({"free_action": "free_sa", "flag": "card_A53", "sa": _SA_BUILD,
                "result": sa_res})
    return out


def _resolve_card67_arduenna(state, faction):
    """Card 67 Arduenna (base): Romans or a Gallic Faction may free March into
    Nervii and/or Treveri, then a free Command except March in those Regions,
    then flip all friendly Warbands/Auxilia there Hidden."""
    from fs_bot.rules_consts import (NERVII, TREVERI, WARBAND, AUXILIA, LEGION,
                                     REVEALED, HIDDEN)
    from fs_bot.board.pieces import (count_pieces, count_pieces_by_state,
                                     flip_piece)
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_adjacent, get_playable_regions
    scen = state["scenario"]
    playable = set(get_playable_regions(scen, state.get("capabilities")))
    targets = [r for r in (NERVII, TREVERI) if r in playable]
    out = []
    # Free March a mobile group from an adjacent Region into each target.
    for T in targets:
        if _attacker_has_force(state, T, faction):
            continue
        srcs = [a for a in get_adjacent(T, scen) if a in playable
                and _group_has_pieces(_mobile_march_group(state, faction, a))]
        if not srcs:
            continue
        S = max(srcs, key=lambda a: sum(
            count_pieces(state, a, faction, pt)
            for pt in (LEGION, AUXILIA, WARBAND)))
        try:
            _march_with_harassment(state, faction, S, [T])
            out.append({"free_action": "march", "flag": "card_67",
                        "source": S, "dest": T})
        except _EXEC_ERRORS:
            pass
    # Free Command (except March) in/from the target Regions.
    cmd = _resolve_free_command(state, faction, allowed_regions=set(targets),
                               exclude_commands={_CMD_MARCH})
    out.append({"free_action": "free_command", "flag": "card_67", "result": cmd})
    # Flip all friendly Warbands/Auxilia in the targets to Hidden.
    flipped = 0
    for T in targets:
        for pt in (WARBAND, AUXILIA):
            rev = count_pieces_by_state(state, T, faction, pt, REVEALED)
            if rev > 0:
                flip_piece(state, T, faction, pt, rev,
                           from_state=REVEALED, to_state=HIDDEN)
                flipped += rev
    if flipped:
        refresh_all_control(state)
        out.append({"free_action": "flip_hidden", "flag": "card_67",
                    "flipped": flipped})
    return out


def _resolve_event_arverni_phase(state):
    """Cards A24/A27/A32: after placing Arverni Warbands, conduct an immediate
    Arverni Phase as if At War (A6.2) via run_arverni_phase."""
    from fs_bot.engine.arverni_phase import run_arverni_phase
    try:
        res = run_arverni_phase(state, force_at_war=True)
    except Exception as exc:
        return [{"free_action": "arverni_phase", "flag": "arverni_phase",
                 "executed": False, "reason": repr(exc)}]
    return [{"free_action": "arverni_phase", "flag": "arverni_phase",
             "executed": res is not None, "result": res}]


def _place_uprising_allies(state, faction, regions, n):
    """Place up to ``n`` Allies for ``faction`` on Subdued tribes within the
    given Regions (Card A66). Returns the number placed."""
    from fs_bot.board.pieces import get_available, place_piece
    from fs_bot.map.map_data import get_tribes_in_region
    from fs_bot.rules_consts import ALLY
    placed = 0
    scenario = state["scenario"]
    for region in regions:
        if placed >= n:
            break
        for tribe in get_tribes_in_region(region, scenario):
            if placed >= n:
                break
            t = state.get("tribes", {}).get(tribe)
            if not t:
                continue
            if (t.get("allied_faction") is None and t.get("status") is None
                    and get_available(state, faction, ALLY) > 0):
                place_piece(state, region, faction, ALLY)
                t["allied_faction"] = faction
                placed += 1
    return placed


def _place_uprising_warbands(state, faction, region, n):
    """Place up to ``n`` Warbands for ``faction`` in ``region`` (Card A66)."""
    from fs_bot.board.pieces import get_available, place_piece
    from fs_bot.rules_consts import WARBAND
    avail = get_available(state, faction, WARBAND)
    to_place = min(n, avail)
    if to_place > 0:
        place_piece(state, region, faction, WARBAND, count=to_place)
    return to_place


def _resolve_winter_uprising(state):
    """Card A66 Winter Uprising: after any Quarters Phase, remove the Uprising
    marker and resolve the placement + free Command/Arverni Phase — A66.

    If the marker is in Belgica, the Belgae place 2 Allies and 4 Warbands and
    execute a free Command + Special Activity within 1 Region of the marker; if
    in Germania, the Germans do so; otherwise place 4 Arverni Allies and 8
    Arverni Warbands within 1 Region of the marker and conduct an Arverni Phase
    as if At War.
    """
    mods = state.get("event_modifiers", {})
    region = mods.get("card_A66_uprising_region")
    # Consume the trigger so it fires exactly once.
    mods.pop("card_A66_winter_uprising", None)
    mods.pop("card_A66_uprising_region", None)
    if region:
        rm = state.get("markers", {}).get(region)
        if isinstance(rm, dict):
            rm.pop("Uprising", None)
    if not region:
        return [{"free_action": "winter_uprising", "executed": False,
                 "reason": "no Uprising marker region"}]
    from fs_bot.rules_consts import (
        REGION_TO_GROUP, BELGICA, GERMANIA, BELGAE, GERMANS, ARVERNI,
    )
    from fs_bot.map.map_data import get_adjacent, get_playable_regions
    group = REGION_TO_GROUP.get(region)
    playable = set(get_playable_regions(state["scenario"]))
    within1 = ({region} | set(get_adjacent(region, state["scenario"]))) \
        & playable
    if group == BELGICA:
        faction, n_ally, n_wb = BELGAE, 2, 4
    elif group == GERMANIA:
        faction, n_ally, n_wb = GERMANS, 2, 4
    else:
        faction, n_ally, n_wb = ARVERNI, 4, 8
    allies = _place_uprising_allies(state, faction, [region] + sorted(
        within1 - {region}), n_ally)
    warbands = _place_uprising_warbands(state, faction, region, n_wb)
    results = [{"free_action": "winter_uprising", "faction": faction,
                "region": region, "allies": allies, "warbands": warbands}]
    if faction == ARVERNI:
        results.extend(_resolve_event_arverni_phase(state))
    else:
        results.append(
            _resolve_free_command(state, faction, allowed_regions=within1)
        )
    return results


def _gallic_np_factions(state):
    from fs_bot.rules_consts import ARVERNI, AEDUI, BELGAE
    nps = state.get("non_player_factions", set())
    return [f for f in (ARVERNI, AEDUI, BELGAE) if f in nps]


def _resolve_card48_druids(state, target_factions):
    """Card 48 Druids: 1-3 Gallic Factions each execute a free Limited Command
    (which may add a free Special Ability), in initiative order. With no chosen
    list, all Gallic Non-player Factions act."""
    targets = [f for f in (target_factions or _gallic_np_factions(state))]
    out = []
    for fac in targets:
        out.append({"free_action": "free_command", "flag": "card_48",
                    "faction": fac,
                    "result": _resolve_free_command(state, fac, limited=True)})
    return out


def _resolve_card47_council(state):
    """Card 47 Chieftains' Council: in a Region with >=2 non-German Factions'
    pieces, those Factions (in initiative order) each either execute a free
    Limited Command (anywhere) or become Eligible (the peek informs the choice;
    we take the Command if effective, else stay Eligible)."""
    from fs_bot.rules_consts import (ROMANS, ARVERNI, AEDUI, BELGAE, ELIGIBLE)
    from fs_bot.board.pieces import count_pieces
    from fs_bot.map.map_data import get_playable_regions
    order = (ROMANS, ARVERNI, AEDUI, BELGAE)
    # Pick a Region with the most distinct non-German Factions (>=2).
    best, best_n = None, 1
    for R in get_playable_regions(state["scenario"], state.get("capabilities")):
        present = [f for f in order if count_pieces(state, R, f) > 0]
        if len(present) >= 2 and len(present) > best_n:
            best, best_n = (R, present), len(present)
    if best is None:
        return [{"free_action": "council", "flag": "card_47", "executed": False,
                 "reason": "no Region with 2+ non-German Factions"}]
    R, present = best
    out = []
    nps = state.get("non_player_factions", set())
    for fac in present:
        if fac not in nps:
            continue
        res = _resolve_free_command(state, fac, limited=True)
        if res.get("executed"):
            out.append({"free_action": "free_command", "flag": "card_47",
                        "region": R, "faction": fac, "result": res})
        else:
            state.setdefault("eligibility", {})[fac] = ELIGIBLE
            out.append({"free_action": "stay_eligible", "flag": "card_47",
                        "faction": fac, "executed": True})
    return out


def _resolve_card62_war_fleet(state, faction):
    """Card 62 War Fleet: after the coastal repositioning, the Faction executes
    a free Command in (or from) one of the War-Fleet Regions — the Arverni
    Region, Pictones, or a Region within 1 of Britannia."""
    from fs_bot.rules_consts import (ARVERNI_REGION, PICTONES, BRITANNIA)
    from fs_bot.map.map_data import get_adjacent, get_playable_regions
    playable = set(get_playable_regions(state["scenario"], state.get("capabilities")))
    near_brit = {BRITANNIA} | set(get_adjacent(BRITANNIA, state["scenario"]))
    allowed = ({ARVERNI_REGION, PICTONES} | near_brit) & playable
    return [{"free_action": "free_command", "flag": "card_62",
             "result": _resolve_free_command(state, faction,
                                             allowed_regions=allowed)}]


def _resolve_card25_battle(state, faction, region, extra):
    """Card 25 Aquitani (unshaded): free Battle in Pictones/Arverni with
    ``extra`` extra Losses and 1 Ally (not Citadel) removed first."""
    from fs_bot.battle.resolve import resolve_battle
    if region is None:
        return [{"free_action": "battle", "flag": "card_25", "executed": False,
                 "reason": "no Pictones/Arverni Battle target"}]
    defender = _rank_free_battle_defender(state, region, faction)
    if defender is None:
        return [{"free_action": "battle", "flag": "card_25", "executed": False,
                 "reason": "no enemy in Region"}]
    rd, rr = _decide_defender_retreat(state, region, faction, defender, False)
    try:
        res = resolve_battle(state, region, faction, defender,
                             extra_losses=extra, ally_first=True,
                             retreat_declaration=rd, retreat_region=rr)
    except _EXEC_ERRORS as exc:
        return [{"free_action": "battle", "flag": "card_25",
                 "executed": False, "reason": repr(exc)}]
    return [{"free_action": "battle", "flag": "card_25", "region": region,
             "defender": defender, "result": res}]


def _resolve_card36_battle(state, faction):
    """Card 36 Morasses (unshaded): free Battle against a Gallic Faction in 1
    Region — No Retreat, No Counterattack, no Citadel effect, Attackers
    Hidden."""
    from fs_bot.rules_consts import (ARVERNI, AEDUI, BELGAE, WARBAND, LEGION,
                                     AUXILIA)
    from fs_bot.board.pieces import count_pieces
    from fs_bot.map.map_data import get_playable_regions
    from fs_bot.battle.resolve import resolve_battle
    gallic = {ARVERNI, AEDUI, BELGAE}
    best = None  # (region, defender, enemy_mobile)
    for R in get_playable_regions(state["scenario"], state.get("capabilities")):
        if not _attacker_has_force(state, R, faction):
            continue
        for d in gallic:
            if d == faction or count_pieces(state, R, d) <= 0:
                continue
            mob = (count_pieces(state, R, d, WARBAND)
                   + count_pieces(state, R, d, AUXILIA)
                   + count_pieces(state, R, d, LEGION))
            if best is None or mob > best[2]:
                best = (R, d, mob)
    if best is None:
        return [{"free_action": "battle", "flag": "card_36", "executed": False,
                 "reason": "no Gallic Faction to Battle"}]
    R, d, _m = best
    try:
        res = resolve_battle(state, R, faction, d,
                             retreat_declaration=False,
                             no_counterattack=True, ignore_citadel=True,
                             attacker_stays_hidden=True)
    except _EXEC_ERRORS as exc:
        return [{"free_action": "battle", "flag": "card_36",
                 "executed": False, "reason": repr(exc)}]
    return [{"free_action": "battle", "flag": "card_36", "region": R,
             "defender": d, "result": res}]


def _resolve_card36_shaded(state, faction):
    """Card 36 Morasses (shaded): a Gallic Faction free Battles with Ambush
    anywhere (Ambush in every able Region), then free Marches."""
    ambushes = _faction_ambush_sweep(state, faction)
    march = _resolve_free_march(state, faction)
    return [{"free_action": "ambush_then_march", "flag": "card_36",
             "ambushes": ambushes, "march": march,
             "executed": bool(ambushes) or bool(march.get("executed"))}]


def _resolve_card66_german_rally_march(state):
    """Card 66 Migration: "Execute a Germanic Rally then March in/from up to 2
    Regions each." The Germans free Rally, then free March (base-game Germans
    are game-run; the rally/march nodes drive them)."""
    from fs_bot.rules_consts import GERMANS
    rally = _resolve_free_rally(state, GERMANS)
    march = _resolve_free_march(state, GERMANS)
    return [{"free_action": "german_rally_march", "flag": "card_66",
             "rally": rally, "march": march,
             "executed": bool(rally.get("executed") or march.get("executed"))}]


def _resolve_card21_provincia_battle(state):
    """Card 21 The Province (shaded): after the Arverni place Warbands in
    Provincia, they free Battle there as if no Fort (the Provincia Fort gives
    no protection)."""
    from fs_bot.rules_consts import ARVERNI, PROVINCIA
    from fs_bot.battle.resolve import resolve_battle
    if not _attacker_has_force(state, PROVINCIA, ARVERNI):
        return [{"free_action": "battle", "flag": "card_21", "executed": False,
                 "reason": "no Arverni force in Provincia"}]
    defender = _rank_free_battle_defender(state, PROVINCIA, ARVERNI)
    if defender is None:
        return [{"free_action": "battle", "flag": "card_21", "executed": False,
                 "reason": "no enemy in Provincia"}]
    rd, rr = _decide_defender_retreat(state, PROVINCIA, ARVERNI, defender, False)
    try:
        res = resolve_battle(state, PROVINCIA, ARVERNI, defender,
                             ignore_fort=True,
                             retreat_declaration=rd, retreat_region=rr)
    except _EXEC_ERRORS as exc:
        return [{"free_action": "battle", "flag": "card_21",
                 "executed": False, "reason": repr(exc)}]
    return [{"free_action": "battle", "flag": "card_21", "region": PROVINCIA,
             "defender": defender, "result": res}]


def _resolve_card45_battle(state, faction):
    """Card 45 Litaviccus (shaded): free Battle against the Romans in 1 Region,
    using Aedui pieces as the attacker's own, Ambushing if able."""
    from fs_bot.rules_consts import ROMANS, AEDUI, WARBAND, AUXILIA, HIDDEN
    from fs_bot.board.pieces import count_pieces, count_pieces_by_state
    from fs_bot.map.map_data import get_playable_regions
    best = None
    for R in get_playable_regions(state["scenario"], state.get("capabilities")):
        if count_pieces(state, R, ROMANS) <= 0:
            continue
        if not (_attacker_has_force(state, R, faction)
                or _attacker_has_force(state, R, AEDUI)):
            continue
        rp = count_pieces(state, R, ROMANS)
        if best is None or rp > best[1]:
            best = (R, rp)
    if best is None:
        return [{"free_action": "battle", "flag": "card_45", "executed": False,
                 "reason": "no Roman target with a combined force"}]
    R = best[0]
    g_hidden = (count_pieces_by_state(state, R, faction, WARBAND, HIDDEN)
                + count_pieces_by_state(state, R, AEDUI, WARBAND, HIDDEN)
                + count_pieces_by_state(state, R, AEDUI, AUXILIA, HIDDEN))
    r_hidden = (count_pieces_by_state(state, R, ROMANS, AUXILIA, HIDDEN)
                + count_pieces_by_state(state, R, ROMANS, WARBAND, HIDDEN))
    is_ambush = g_hidden > r_hidden and g_hidden > 0
    details = {"battle_plan": [{"region": R, "target": ROMANS}],
               "allied_factions": (AEDUI,)}
    bot_action = {"command": _CMD_BATTLE,
                  "sa": (_SA_AMBUSH if is_ambush else SA_ACTION_NONE_LABEL),
                  "sa_regions": ([R] if is_ambush else []), "details": details}
    try:
        res = _execute_battle(state, faction, bot_action)
    except _EXEC_ERRORS as exc:
        return [{"free_action": "battle", "flag": "card_45",
                 "executed": False, "reason": repr(exc)}]
    return [{"free_action": "battle", "flag": "card_45", "region": R,
             "defender": ROMANS, "ambush": is_ambush, "result": res}]


def _resolve_card54_joined_ranks(state, faction, march_limit,
                                 second_always_retreat=False):
    """Card 54 Joined Ranks: the executing Faction may free March a group to a
    Region that already has >=2 other Gallic/Roman Factions; then it free
    Battles there (No Retreat) and a 2nd such Faction free Battles there
    (Retreat allowed), each against a 3rd Faction."""
    from fs_bot.rules_consts import (ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
                                     ARIOVISTUS_SCENARIOS)
    from fs_bot.board.pieces import count_pieces
    from fs_bot.map.map_data import get_adjacent, get_playable_regions
    scen = state["scenario"]
    # The player Factions that count toward "2 other Factions" and may be the
    # 2nd Battler. In Ariovistus the card reads "2 other Factions" and Germans
    # are a player while Arverni are game-run (A6.2) — swap them in.
    if scen in ARIOVISTUS_SCENARIOS:
        gr = (ROMANS, GERMANS, AEDUI, BELGAE)
    else:
        gr = (ROMANS, ARVERNI, AEDUI, BELGAE)
    playable = set(get_playable_regions(scen, state.get("capabilities")))
    # Target Region: >=2 other Gallic/Roman Factions, reachable/occupied by us.
    T = None
    for R in sorted(playable):
        others = [f for f in gr if f != faction and count_pieces(state, R, f) > 0]
        if len(others) < 2:
            continue
        reachable = _attacker_has_force(state, R, faction) or any(
            _group_has_pieces(_mobile_march_group(state, faction, a))
            for a in get_adjacent(R, scen) if a in playable)
        if reachable:
            T = R
            break
    if T is None:
        return [{"free_action": "joined_ranks", "flag": "card_54",
                 "executed": False, "reason": "no Region with 2+ other "
                 "Gallic/Roman Factions reachable"}]
    out = []
    # Free March our group into T (if not already there).
    if not _attacker_has_force(state, T, faction):
        srcs = [a for a in get_adjacent(T, scen) if a in playable
                and _group_has_pieces(_mobile_march_group(state, faction, a))]
        if srcs:
            S = max(srcs, key=lambda a: sum(
                count_pieces(state, a, faction, pt)
                for pt in ("Legion", "Auxilia", "Warband")))
            try:
                _march_with_harassment(state, faction, S, [T])
                out.append({"free_action": "march", "flag": "card_54",
                            "source": S, "dest": T})
            except _EXEC_ERRORS as exc:
                out.append({"free_action": "march", "flag": "card_54",
                            "executed": False, "reason": repr(exc)})
    # First Battle: executing Faction (No Retreat).
    d1 = _rank_free_battle_defender(state, T, faction)
    if d1 is not None and _attacker_has_force(state, T, faction):
        try:
            r1 = _execute_battle(state, faction, {
                "command": _CMD_BATTLE, "sa": SA_ACTION_NONE_LABEL,
                "sa_regions": [], "details": {"battle_plan": [
                    {"region": T, "target": d1}], "no_retreat": True}})
            out.append({"free_action": "battle", "flag": "card_54",
                        "battler": faction, "region": T, "defender": d1,
                        "result": r1})
        except _EXEC_ERRORS as exc:
            out.append({"free_action": "battle", "flag": "card_54",
                        "executed": False, "reason": repr(exc)})
    # Second Battle: another Gallic/Roman Faction there (Retreat allowed),
    # ganging up on a 3rd Faction — prefer the one the executing Faction hit;
    # never the executing Faction itself.
    for f2 in gr:
        if f2 in (faction, d1) or not _attacker_has_force(state, T, f2):
            continue
        if d1 is not None and d1 != f2 and count_pieces(state, T, d1) > 0:
            d2 = d1
        else:
            d2 = _rank_free_battle_defender(state, T, f2)
        if d2 is None or d2 in (f2, faction):
            continue
        try:
            r2 = _execute_battle(state, f2, {
                "command": _CMD_BATTLE, "sa": SA_ACTION_NONE_LABEL,
                "sa_regions": [], "details": {"battle_plan": [
                    {"region": T, "target": d2}],
                    "force_retreat": second_always_retreat}})
            out.append({"free_action": "battle", "flag": "card_54",
                        "battler": f2, "region": T, "defender": d2,
                        "result": r2})
        except _EXEC_ERRORS:
            pass
        break
    return out


def _resolve_card44_scout(state):
    """Card 44 (unshaded): the Romans free Scout (as if Auxilia)."""
    from fs_bot.rules_consts import ROMANS
    try:
        res = _execute_scout(state, ROMANS, {"sa": _SA_SCOUT,
                                             "sa_regions": [], "details": {}})
    except _EXEC_ERRORS as exc:
        return [{"free_action": "scout", "flag": "card_44",
                 "executed": False, "reason": repr(exc)}]
    return [{"free_action": "scout", "flag": "card_44", "result": res}]


def _resolve_card44_raid(state, faction):
    """Card 44 (shaded): the acting Faction's Warbands free Raid — in each
    Region where it has Warbands and an enemy with Resources is present."""
    from fs_bot.rules_consts import WARBAND, FACTIONS
    from fs_bot.board.pieces import count_pieces
    from fs_bot.map.map_data import get_playable_regions
    raid_plan = []
    for region in get_playable_regions(state["scenario"], state.get("capabilities")):
        if count_pieces(state, region, faction, WARBAND) <= 0:
            continue
        target = next((f for f in FACTIONS if f != faction
                       and count_pieces(state, region, f) > 0
                       and state["resources"].get(f, 0) > 0), None)
        raid_plan.append({"region": region, "target": target})
    if not raid_plan:
        return [{"free_action": "raid", "flag": "card_44", "executed": False,
                 "reason": "no Warband Region to Raid"}]
    try:
        res = _execute_raid(state, faction, {"command": _CMD_RAID,
              "sa": SA_ACTION_NONE_LABEL, "sa_regions": [],
              "details": {"raid_plan": raid_plan}})
    except _EXEC_ERRORS as exc:
        return [{"free_action": "raid", "flag": "card_44",
                 "executed": False, "reason": repr(exc)}]
    return [{"free_action": "raid", "flag": "card_44", "result": res}]


def _resolve_card26_arverni_rally(state):
    """Card 26 Gobannitio (shaded): the Arverni free Rally within 1 Region of
    Vercingetorix."""
    from fs_bot.rules_consts import ARVERNI
    from fs_bot.board.pieces import find_leader
    from fs_bot.map.map_data import get_adjacent, get_playable_regions
    leader = find_leader(state, ARVERNI)
    if leader is None:
        return [{"free_action": "free_rally", "flag": "card_26",
                 "executed": False, "reason": "Vercingetorix not on map"}]
    playable = set(get_playable_regions(state["scenario"], state.get("capabilities")))
    allowed = ({leader} | set(get_adjacent(leader, state["scenario"]))) & playable
    return [{"free_action": "free_rally", "flag": "card_26",
             "result": _resolve_free_rally(state, ARVERNI, allowed_regions=allowed)}]


def _resolve_card64_belgae_rally(state):
    """Card 64 Correus (shaded): the Belgae free Rally in 1 Belgica Region."""
    from fs_bot.rules_consts import BELGAE, BELGICA_REGIONS
    from fs_bot.map.map_data import get_playable_regions
    playable = set(get_playable_regions(state["scenario"], state.get("capabilities")))
    allowed = set(BELGICA_REGIONS) & playable
    return [{"free_action": "free_rally", "flag": "card_64",
             "result": _resolve_free_rally(state, BELGAE, allowed_regions=allowed)}]


def _resolve_card35_roman(state, faction):
    """Card 35 Gallic Shouts (unshaded): "Romans may look at the next 2
    facedown cards and either execute a free Limited Command or be Eligible."

    The peek lets the Romans pick the better option. We model the choice by
    outcome: take the free Limited Command if it does something; otherwise take
    the alternative and remain Eligible (the peek is the information that drives
    this either/or — it has no board effect of its own)."""
    from fs_bot.rules_consts import ELIGIBLE
    res = _resolve_free_command(state, faction, limited=True)
    if res.get("executed"):
        return [{"free_action": "free_command", "flag": "card_35",
                 "result": res}]
    state.setdefault("eligibility", {})[faction] = ELIGIBLE
    return [{"free_action": "stay_eligible", "flag": "card_35",
             "executed": True, "faction": faction,
             "note": "no effective Limited Command; chose to be Eligible"}]


def _resolve_card35_gallic(state, faction):
    """Card 35 Gallic Shouts (shaded): "A Gallic Faction executes 1 Command and
    1 Limited Command, in either order, free, no Battles." Run a full free
    Command then a Limited free Command for the acting Faction, both excluding
    Battle."""
    out = []
    out.append({"free_action": "free_command", "flag": "card_35",
                "kind": "command",
                "result": _resolve_free_command(
                    state, faction, exclude_commands={_CMD_BATTLE})})
    out.append({"free_action": "free_command", "flag": "card_35",
                "kind": "limited_command",
                "result": _resolve_free_command(
                    state, faction, exclude_commands={_CMD_BATTLE},
                    limited=True)})
    return out


def _resolve_card52_free_command(state):
    """Card 52 Assembly of Gaul (shaded): "Faction Controlling Carnutes Region
    executes a Command that may add 2 Special Abilities, free."

    The controller runs a free Command via the flowchart, which carries the
    one Special Ability the bot selects (executed by _execute_bot_command). The
    card *permits* up to two SAs, but the Non-player flowchart has no rule for
    choosing a second SA — adding one would be invented behaviour — so the
    Faction adds the single SA its flowchart selects (within the allowance).
    The result reports whether a SA accompanied the Command."""
    from fs_bot.rules_consts import CARNUTES, FACTIONS
    from fs_bot.board.control import is_controlled_by
    controller = next((f for f in FACTIONS
                       if is_controlled_by(state, CARNUTES, f)), None)
    if controller is None:
        return [{"free_action": "free_command", "flag": "card_52",
                 "executed": False, "reason": "no Faction controls Carnutes"}]
    res = _resolve_free_command(state, controller)
    return [{"free_action": "free_command", "flag": "card_52",
             "controller": controller,
             "sa_included": bool((res or {}).get("sa_execution")),
             "result": res}]


def _resolve_card70_free_command(state, faction):
    """Card 70 Camulogenus (shaded): after placing Warbands among Atrebates/
    Carnutes/Mandubii, the Faction executes a free Command + Special Ability in
    the selected Region — the one of the three where it now has the most
    pieces (where the deriver placed). Restricted via the free-Command layer."""
    from fs_bot.rules_consts import ATREBATES, CARNUTES, MANDUBII
    from fs_bot.board.pieces import count_pieces
    from fs_bot.map.map_data import get_playable_regions
    playable = set(get_playable_regions(state["scenario"], state.get("capabilities")))
    regs = [r for r in (ATREBATES, CARNUTES, MANDUBII) if r in playable]
    if not regs:
        return [{"free_action": "free_command", "flag": "card_70_free_command_sa",
                 "executed": False, "reason": "no target Region in play"}]
    R = max(regs, key=lambda r: count_pieces(state, r, faction))
    cmd_res = _resolve_free_command(state, faction, allowed_regions={R})
    return [{"free_action": "free_command", "flag": "card_70_free_command_sa",
             "region": R, "result": cmd_res}]


def _resolve_card9_march_command(state, faction, march_from, march_to):
    """Card 9 Mons Cevenna: "Free March from a Region into an adjacent Region,
    both within 1 Region of Provincia. Then execute a free Command and any free
    Special Ability in (or from) the destination Region." (Within 1 of
    Provincia = Provincia, Sequani, or Arverni.)

    Performs the free March (deriving a within-1-of-Provincia source/destination
    if the handler did not supply them), then a free Command via the flowchart-
    faithful chooser.
    """
    from fs_bot.rules_consts import PROVINCIA, SEQUANI, ARVERNI_REGION
    from fs_bot.map.map_data import get_adjacent, get_playable_regions
    out = []
    scen = state["scenario"]
    near = [r for r in (PROVINCIA, SEQUANI, ARVERNI_REGION)
            if r in set(get_playable_regions(scen, state.get("capabilities")))]
    S, B = march_from, march_to
    if not (S and B):
        # Derive: a within-1-of-Provincia source with a mobile group, into an
        # adjacent within-1-of-Provincia destination.
        for cand in near:
            if _group_has_pieces(_mobile_march_group(state, faction, cand)):
                dests = [d for d in get_adjacent(cand, scen) if d in near]
                if dests:
                    S, B = cand, dests[0]
                    break
    dest = None
    if S and B and _group_has_pieces(_mobile_march_group(state, faction, S)):
        try:
            final = _march_with_harassment(state, faction, S, [B])
            dest = final
            out.append({"free_action": "march", "flag": "card_9",
                        "source": S, "final_region": final})
        except _EXEC_ERRORS as exc:
            out.append({"free_action": "march", "flag": "card_9",
                        "executed": False, "reason": repr(exc)})
    # Free Command "in (or from) the destination Region" — restrict to dest.
    allowed = {dest} if dest else (set(near) if near else None)
    cmd_res = _resolve_free_command(state, faction, allowed_regions=allowed)
    out.append({"free_action": "free_command", "flag": "card_9",
                "result": cmd_res})
    return out


def _resolve_card4_circumvallation(state, region):
    """Card 4 Circumvallation: the Romans free March one mobile group into the
    marked enemy-Citadel Region (the Circumvallation marker was placed there by
    the card handler). Marches from the adjacent Region with the largest Roman
    mobile group."""
    from fs_bot.rules_consts import ROMANS, LEGION, AUXILIA, WARBAND, LEADER
    from fs_bot.map.map_data import get_adjacent, get_playable_regions
    if region is None:
        return []
    playable = set(get_playable_regions(state["scenario"], state.get("capabilities")))
    sources = [a for a in get_adjacent(region, state["scenario"])
               if a in playable
               and _group_has_pieces(_mobile_march_group(state, ROMANS, a))]
    if not sources:
        return [{"free_action": "march", "flag": "card_4_free_march_to",
                 "region": region, "executed": False,
                 "reason": "no adjacent Roman group to March in"}]
    def gsize(r):
        g = _mobile_march_group(state, ROMANS, r)
        return (g.get(LEGION, 0) + g.get(AUXILIA, 0) + g.get(WARBAND, 0)
                + (1 if g.get(LEADER) else 0))
    S = max(sources, key=gsize)
    try:
        final = _march_with_harassment(state, ROMANS, S, [region])
    except _EXEC_ERRORS as exc:
        return [{"free_action": "march", "flag": "card_4_free_march_to",
                 "region": region, "source": S, "executed": False,
                 "reason": repr(exc)}]
    return [{"free_action": "march", "flag": "card_4_free_march_to",
             "region": region, "source": S, "final_region": final}]


def _resolve_card57_britannia_march(state, faction):
    """Card 57 Land of Mist and Mystery (unshaded): "A non-German Faction may
    free March into Britannia, add any free Special Ability there, then — if
    in Britannia — add +4 Resources."

    Executes the free March: the acting non-German Faction Marches one mobile
    group from a coastal-adjacent Region (Morini, Atrebates, or Veneti) into
    Britannia, resolving Harassment en route. The +4 Resources is granted by
    the card handler. The open-ended "any free Special Ability there" depends
    on a generic per-Faction SA-choice layer and is a documented follow-up;
    the March (and the resulting Britannia presence that justifies the +4) is
    executed here.
    """
    from fs_bot.rules_consts import GERMANS, BRITANNIA, MORINI, ATREBATES, VENETI
    from fs_bot.map.map_data import get_playable_regions
    if faction == GERMANS:
        return [{"free_action": "march", "flag": "card_57_march_britannia",
                 "executed": False, "reason": "Germans may not March to Britannia"}]
    playable = set(get_playable_regions(state["scenario"], state.get("capabilities")))
    if BRITANNIA not in playable:
        return [{"free_action": "march", "flag": "card_57_march_britannia",
                 "executed": False, "reason": "Britannia not in play"}]
    sources = [r for r in (MORINI, ATREBATES, VENETI)
               if r in playable
               and _group_has_pieces(_mobile_march_group(state, faction, r))]
    if not sources:
        return [{"free_action": "march", "flag": "card_57_march_britannia",
                 "executed": False,
                 "reason": "no mobile group adjacent to Britannia"}]
    # March from the coastal source with the largest mobile group.
    def group_size(r):
        g = _mobile_march_group(state, faction, r)
        from fs_bot.rules_consts import LEGION, AUXILIA, WARBAND, LEADER
        return (g.get(LEGION, 0) + g.get(AUXILIA, 0) + g.get(WARBAND, 0)
                + (1 if g.get(LEADER) else 0))
    S = max(sources, key=group_size)
    try:
        final = _march_with_harassment(state, faction, S, [BRITANNIA])
    except _EXEC_ERRORS as exc:
        return [{"free_action": "march", "flag": "card_57_march_britannia",
                 "source": S, "executed": False, "reason": repr(exc)}]
    # "...then — if in Britannia — add +4 Resources." Only when the group
    # actually reached Britannia.
    bonus = 0
    if final == BRITANNIA and count_pieces(state, BRITANNIA, faction) > 0:
        from fs_bot.cards.card_effects import _cap_resources
        _cap_resources(state, faction, 4)
        bonus = 4
    return [{"free_action": "march", "flag": "card_57_march_britannia",
             "source": S, "final_region": final, "resources_bonus": bonus,
             "sa_deferred": "any free Special Ability (open-ended)"}]


def _resolve_card17_march_ambush(state, march_limit):
    """Card 17 Germanic Chieftains (unshaded): "Romans March up to 3 German
    groups, then Ambush with Germans in any 1 Region." Setup March of up to
    march_limit German groups (shared helper), then Ambush in the single best
    Region (Hidden-majority, Loss-causing; most enemy pieces — per Roman
    Battle priority 8.8.1's spirit)."""
    from fs_bot.rules_consts import GERMANS
    from fs_bot.board.pieces import count_pieces
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_playable_regions
    from fs_bot.battle.resolve import resolve_battle
    marched = _german_setup_marches(state, march_limit)
    # Single best Ambush Region.
    best, best_tgt, best_score = None, None, None
    for region in get_playable_regions(state["scenario"], state.get("capabilities")):
        tgt = _german_ambush_target(state, region)
        if tgt is None:
            continue
        score = count_pieces(state, region, tgt)
        if best_score is None or score > best_score:
            best, best_tgt, best_score = region, tgt, score
    if best is None:
        return [{"free_action": "german_march_ambush",
                 "flag": "card_17_german_ambush", "marches": marched,
                 "executed": False, "reason": "no legal German Ambush"}]
    try:
        res = resolve_battle(state, best, GERMANS, best_tgt, is_ambush=True)
    except _EXEC_ERRORS as exc:
        return [{"free_action": "german_march_ambush",
                 "flag": "card_17_german_ambush", "marches": marched,
                 "region": best, "executed": False, "reason": repr(exc)}]
    refresh_all_control(state)
    return [{"free_action": "german_march_ambush",
             "flag": "card_17_german_ambush", "marches": marched,
             "region": best, "defender": best_tgt, "result": res}]


def _resolve_card17_germans_phase(state):
    """Card 17 Germanic Chieftains (shaded): "Conduct an immediate Germans
    Phase as if Winter." Runs the full §6.2 Germans Phase (Rally, March, Raid,
    Battle-with-Ambush). Base game only; returns no-op in Ariovistus (where
    the Germans are a full Faction with no Germans Phase)."""
    from fs_bot.engine.winter import germans_phase
    try:
        res = germans_phase(state)
    except _EXEC_ERRORS as exc:
        return [{"free_action": "germans_phase", "flag":
                 "card_17_germans_phase", "executed": False,
                 "reason": repr(exc)}]
    return [{"free_action": "germans_phase", "flag": "card_17_germans_phase",
             "executed": res is not None, "result": res}]


def _faction_ambush_target(state, region, attacker, only_faction=None):
    """Best enemy for ``attacker`` to Ambush in ``region`` — the attacker's
    Hidden Warbands must outnumber the defender's Hidden pieces and the Ambush
    must cause a Loss. Picks the legal target with the most pieces. When
    ``only_faction`` is set, the Ambush target is restricted to that Faction
    (e.g. card A58 shaded "free Ambush Romans")."""
    from fs_bot.rules_consts import FACTIONS, WARBAND, AUXILIA, HIDDEN
    from fs_bot.board.pieces import count_pieces, count_pieces_by_state
    from fs_bot.battle.losses import calculate_losses
    a_hidden = count_pieces_by_state(state, region, attacker, WARBAND, HIDDEN)
    if a_hidden <= 0:
        return None
    candidates = [only_faction] if only_faction else FACTIONS
    best, best_score = None, None
    for ef in candidates:
        if ef == attacker or count_pieces(state, region, ef) <= 0:
            continue
        e_hidden = (count_pieces_by_state(state, region, ef, WARBAND, HIDDEN)
                    + count_pieces_by_state(state, region, ef, AUXILIA, HIDDEN))
        if a_hidden <= e_hidden:
            continue
        try:
            if calculate_losses(state, region, attacker, ef,
                                is_retreat=False) <= 0:
                continue
        except Exception:
            continue
        score = count_pieces(state, region, ef)
        if best_score is None or score > best_score:
            best, best_score = ef, score
    return best


def _german_ambush_target(state, region):
    from fs_bot.rules_consts import GERMANS
    return _faction_ambush_target(state, region, GERMANS)


def _faction_ambush_sweep(state, attacker, only_faction=None):
    """Ambush in every Region where ``attacker`` is able (Hidden-majority,
    Loss-causing). Returns the list of ambush results. ``only_faction``
    restricts the defender (e.g. card A58 shaded Ambushes Romans only)."""
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_playable_regions
    from fs_bot.battle.resolve import resolve_battle
    out = []
    for region in get_playable_regions(state["scenario"], state.get("capabilities")):
        tgt = _faction_ambush_target(state, region, attacker, only_faction)
        if tgt is None:
            continue
        try:
            res = resolve_battle(state, region, attacker, tgt, is_ambush=True)
            out.append({"region": region, "defender": tgt, "result": res})
        except _EXEC_ERRORS as exc:
            out.append({"region": region, "executed": False, "reason": repr(exc)})
    refresh_all_control(state)
    return out


def _resolve_free_march(state, faction):
    """Execute a *free* March for ``faction`` using its primary March node."""
    nodes = {
        "Aedui": ("fs_bot.bots.aedui_bot", "node_a_march"),
        "Arverni": ("fs_bot.bots.arverni_bot", "node_v_march_threat"),
        "Belgae": ("fs_bot.bots.belgae_bot", "node_b_march"),
        "Germans": ("fs_bot.bots.german_bot", "node_g_march_threat"),
        "Romans": ("fs_bot.bots.roman_bot", "node_r_march"),
    }
    spec = nodes.get(faction)
    if spec is None:
        return {"executed": False, "command": None, "reason": "no March node"}
    import importlib
    try:
        node = getattr(importlib.import_module(spec[0]), spec[1])
        bot_action = node(state)
    except Exception as exc:
        return {"executed": False, "command": None, "reason": repr(exc)}
    if not bot_action or bot_action.get("command") != _CMD_MARCH:
        return {"executed": False,
                "command": bot_action.get("command") if bot_action else None,
                "reason": "no free March available"}
    res = _execute_bot_command(state, faction, bot_action)
    return res if res is not None else {"executed": False, "command": _CMD_MARCH,
                                        "reason": "March not executable"}


def _german_setup_marches(state, march_limit):
    """Up to ``march_limit`` German setup Marches: gather a Region's German
    Hidden Warbands one step into an adjacent enemy-occupied Region where the
    move newly enables a legal, Loss-causing Ambush. Ranked by enemy force
    exposed; never strips a Region that already has a legal Ambush of its own.
    Returns the list of marches performed. (Shared by cards 65 and 17.)"""
    from fs_bot.rules_consts import GERMANS, WARBAND, HIDDEN
    from fs_bot.board.pieces import count_pieces, count_pieces_by_state, move_piece
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_adjacent, get_playable_regions
    scen = state["scenario"]
    playable = list(get_playable_regions(scen, state.get("capabilities")))
    candidates = []
    for S in sorted(playable):
        hid = count_pieces_by_state(state, S, GERMANS, WARBAND, HIDDEN)
        if hid <= 0:
            continue
        if _german_ambush_target(state, S) is not None:
            continue
        for B in get_adjacent(S, scen):
            if B not in playable:
                continue
            if _german_ambush_target(state, B) is not None:
                continue
            move_piece(state, S, B, GERMANS, WARBAND, count=hid,
                       piece_state=HIDDEN)
            tgt = _german_ambush_target(state, B)
            exposed = count_pieces(state, B, tgt) if tgt else 0
            move_piece(state, B, S, GERMANS, WARBAND, count=hid,
                       piece_state=HIDDEN)
            if tgt is not None:
                candidates.append((exposed, S, B, hid))
    candidates.sort(key=lambda c: -c[0])
    marched, used = [], set()
    for exposed, S, B, hid in candidates:
        if len(marched) >= march_limit:
            break
        if S in used:
            continue
        cur = count_pieces_by_state(state, S, GERMANS, WARBAND, HIDDEN)
        if cur <= 0:
            continue
        move_piece(state, S, B, GERMANS, WARBAND, count=cur, piece_state=HIDDEN)
        used.add(S)
        marched.append({"source": S, "dest": B, "warbands": cur})
    if marched:
        refresh_all_control(state)
    return marched


def _resolve_card65_german_march_ambush(state, march_limit):
    """Card 65 German Allegiances (unshaded): "March Germans from up to 2
    Regions, then Ambush with all Germans able."

    Setup March (<= march_limit source Regions): gather a Region's German
    Hidden Warbands one step into an adjacent enemy-occupied Region where the
    move newly enables a legal, Loss-causing Ambush. The moves giving the
    largest resulting enemy force under Ambush are taken first. Then Ambush in
    every Region where the Germans are able (Hidden-majority + would cause a
    Loss), best target first.
    """
    from fs_bot.rules_consts import GERMANS
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_playable_regions
    from fs_bot.battle.resolve import resolve_battle
    scen = state["scenario"]
    playable = list(get_playable_regions(scen, state.get("capabilities")))

    marched = _german_setup_marches(state, march_limit)

    # ---- Ambush with all Germans able (every legal Region).
    ambushes = []
    for region in sorted(playable):
        tgt = _german_ambush_target(state, region)
        if tgt is None:
            continue
        try:
            res = resolve_battle(state, region, GERMANS, tgt, is_ambush=True)
        except _EXEC_ERRORS as exc:
            ambushes.append({"region": region, "executed": False,
                             "reason": repr(exc)})
            continue
        ambushes.append({"region": region, "defender": tgt, "result": res})
    refresh_all_control(state)
    return [{"free_action": "german_march_ambush",
             "flag": "card_65_german_march_ambush",
             "marches": marched, "ambushes": ambushes,
             "executed": bool(ambushes)}]


def _resolve_card58_german_ambush(state):
    """Card 58 Aduatuca (shaded): "March Germans to 1 Region with a Fort. They
    Ambush Romans there, 1 Loss per 2 Warbands." ("Sugambri strike unprepared
    fort" — the Fort gives no protection: ignore_fort.)

    Gather German Hidden Warbands from a Roman-Fort Region and its neighbours
    into that Region, then resolve a German Ambush of the Romans there with
    ignore_fort (no halving, full auto-remove). Warband Losses are the normal
    1/2 each = 1 Loss per 2 Warbands. Chooses the Fort Region where the most
    German Warbands can be gathered and the Ambush is legal (German Hidden
    Warbands outnumber Roman Hidden pieces) and causes a Loss.
    """
    from fs_bot.rules_consts import (GERMANS, ROMANS, WARBAND, AUXILIA, FORT,
                                     HIDDEN)
    from fs_bot.board.pieces import (count_pieces, count_pieces_by_state,
                                     move_piece)
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_adjacent, get_playable_regions
    from fs_bot.battle.resolve import resolve_battle
    scen = state["scenario"]
    playable = set(get_playable_regions(scen, state.get("capabilities")))

    def roman_hidden(r):
        return (count_pieces_by_state(state, r, ROMANS, AUXILIA, HIDDEN)
                + count_pieces_by_state(state, r, ROMANS, WARBAND, HIDDEN))

    best = None  # (gatherable, R, sources)
    for R in sorted(playable):
        if count_pieces(state, R, ROMANS, FORT) <= 0:
            continue
        if count_pieces(state, R, ROMANS) <= 0:
            continue
        sources = {r: count_pieces_by_state(state, r, GERMANS, WARBAND, HIDDEN)
                   for r in [R] + [a for a in get_adjacent(R, scen)
                                   if a in playable]}
        sources = {r: n for r, n in sources.items() if n > 0}
        total = sum(sources.values())
        if total <= 0 or total // 2 < 1:
            continue
        if total <= roman_hidden(R):      # Ambush needs Hidden majority
            continue
        if best is None or total > best[0]:
            best = (total, R, sources)

    if best is None:
        return [{"free_action": "ambush", "flag": "card_58_german_march_battle",
                 "executed": False,
                 "reason": "no Fort Region where Germans can gather an Ambush"}]

    total, R, sources = best
    marched = 0
    for src, n in sources.items():
        if src == R:
            continue
        move_piece(state, src, R, GERMANS, WARBAND, count=n, piece_state=HIDDEN)
        marched += n
    refresh_all_control(state)
    try:
        res = resolve_battle(state, R, GERMANS, ROMANS,
                             is_ambush=True, ignore_fort=True)
    except _EXEC_ERRORS as exc:
        return [{"free_action": "ambush", "flag": "card_58_german_march_battle",
                 "region": R, "executed": False, "reason": repr(exc)}]
    return [{"free_action": "ambush", "flag": "card_58_german_march_battle",
             "region": R, "defender": ROMANS, "warbands_gathered": total,
             "warbands_marched": marched, "result": res}]


def _resolve_card72_hidden_march_battle(state, faction):
    """Card 72 Impetuosity (shaded): "Free March 1 group of your Hidden
    Warbands (no Leader). That group then may free Battle (alone)."

    Faction NP instructions for Impetuosity:
      Arverni / German: take Control of a Region with player pieces (Roman,
        then Aedui, then Belgae), then Battle that player there.
      Belgae: Battle the player with the highest victory margin.
      Aedui: continue on the flowchart instead (no free March/Battle).
      Romans: have no Warbands, so the Hidden-Warband March does not apply.

    Marches one group of the Faction's Hidden Warbands from an adjacent source
    into the chosen Region, then free Battles the target there (Retreat
    allowed).
    """
    from fs_bot.rules_consts import (ARVERNI, GERMANS, BELGAE, AEDUI, ROMANS,
                                     WARBAND, HIDDEN, FACTIONS)
    from fs_bot.board.pieces import count_pieces, count_pieces_by_state, move_piece
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_adjacent, get_playable_regions
    from fs_bot.engine.victory import calculate_victory_margin
    from fs_bot.battle.resolve import resolve_battle

    if faction not in (ARVERNI, GERMANS, BELGAE):
        return [{"free_action": "march_battle", "flag":
                 "card_72_hidden_march_battle", "executed": False,
                 "reason": "no Hidden-Warband March instruction for this Faction"}]
    scen = state["scenario"]
    playable = set(get_playable_regions(scen, state.get("capabilities")))

    def target_in(B):
        if faction in (ARVERNI, GERMANS):
            for pf in (ROMANS, AEDUI, BELGAE):
                if pf != faction and count_pieces(state, B, pf) > 0:
                    return pf
            return None
        # Belgae: enemy with the highest victory margin.
        best_f, best_m = None, None
        for ef in FACTIONS:
            if ef == faction or count_pieces(state, B, ef) <= 0:
                continue
            try:
                m = calculate_victory_margin(state, ef)
            except Exception:
                m = -999
            if best_m is None or m > best_m:
                best_f, best_m = ef, m
        return best_f

    # Enumerate (source S with Hidden Warbands) -> adjacent destination B with
    # a valid target. Score per Faction priority.
    best = None  # (score_tuple, S, B, target, hidden)
    # Sorted iteration: 'playable' is a set, whose order is
    # PYTHONHASHSEED-dependent; with the strict-'>' tie-break below that would
    # make the chosen (source, destination) nondeterministic across replays.
    for S in sorted(playable):
        hid = count_pieces_by_state(state, S, faction, WARBAND, HIDDEN)
        if hid <= 0:
            continue
        for B in sorted(get_adjacent(S, scen)):
            if B not in playable:
                continue
            tgt = target_in(B)
            if tgt is None:
                continue
            if faction in (ARVERNI, GERMANS):
                rank = (ROMANS, AEDUI, BELGAE).index(tgt)
                score = (-rank, hid)  # Roman best (rank 0 -> -0 highest), more WB
            else:
                try:
                    score = (calculate_victory_margin(state, tgt), hid)
                except Exception:
                    score = (-999, hid)
            if best is None or score > best[0]:
                best = (score, S, B, tgt, hid)

    if best is None:
        return [{"free_action": "march_battle", "flag":
                 "card_72_hidden_march_battle", "executed": False,
                 "reason": "no Hidden-Warband group can March to Battle a target"}]

    _sc, S, B, tgt, hid = best
    move_piece(state, S, B, faction, WARBAND, count=hid, piece_state=HIDDEN)
    refresh_all_control(state)
    rd, rr = _decide_defender_retreat(state, B, faction, tgt, False)
    try:
        res = resolve_battle(state, B, faction, tgt,
                             retreat_declaration=rd, retreat_region=rr)
    except _EXEC_ERRORS as exc:
        return [{"free_action": "march_battle",
                 "flag": "card_72_hidden_march_battle", "source": S,
                 "region": B, "executed": False, "reason": repr(exc)}]
    return [{"free_action": "march_battle",
             "flag": "card_72_hidden_march_battle", "source": S, "region": B,
             "defender": tgt, "warbands_marched": hid, "result": res}]


def _resolve_card70_march_battle(state, target_regions, legion_limit):
    """Card 70 Camulogenus (unshaded): "Romans may free March up to 4 Legions
    & any Auxilia to Atrebates, Carnutes, or Mandubii Region and free Battle
    there." Pick the named Region with the best Roman Battle target (8.8.1)
    that has an adjacent Roman group; March <= legion_limit Legions and all
    Auxilia from the strongest adjacent source in; free Battle there (no
    double Auxilia)."""
    from fs_bot.rules_consts import ROMANS, LEGION, AUXILIA
    from fs_bot.board.pieces import count_pieces, move_piece
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_adjacent, get_playable_regions
    from fs_bot.bots.roman_bot import _rank_battle_targets
    from fs_bot.battle.resolve import resolve_battle
    scen = state["scenario"]
    playable = set(get_playable_regions(scen, state.get("capabilities")))
    targets = [r for r in (target_regions or []) if r in playable]

    # Rank the named Regions by best available Roman Battle target there or
    # reachable: choose the (T, source) maximizing enemy mobile force in T.
    best = None  # (enemy_mobile, T, src, defender)
    for T in targets:
        defenders = _rank_battle_targets(state, T, scen)
        # Source: an adjacent Region with Roman Legions/Auxilia.
        src_best = None
        for src in get_adjacent(T, scen):
            leg = count_pieces(state, src, ROMANS, LEGION)
            aux = count_pieces(state, src, ROMANS, AUXILIA)
            if leg + aux <= 0:
                continue
            if src_best is None or (leg + aux) > src_best[1]:
                src_best = (src, leg + aux)
        # Enemy force already in T (for ranking) — Battle is fought after March.
        em = 0
        if defenders:
            d = defenders[0]
            em = (count_pieces(state, T, d, "Warband")
                  + count_pieces(state, T, d, AUXILIA)
                  + count_pieces(state, T, d, LEGION))
        # Need either an enemy already in T or pieces to bring + an enemy.
        if src_best is None and not defenders:
            continue
        if best is None or em > best[0]:
            best = (em, T, src_best[0] if src_best else None,
                    defenders[0] if defenders else None)
    if best is None:
        return [{"free_action": "march_battle", "flag":
                 "card_70_roman_march_battle", "executed": False,
                 "reason": "no named Region with a Roman group or target"}]

    _em, T, src, _d = best
    moved = {"legions": 0, "auxilia": 0}
    if src is not None:
        leg = count_pieces(state, src, ROMANS, LEGION)
        aux = count_pieces(state, src, ROMANS, AUXILIA)
        move_leg = min(legion_limit, leg)
        if move_leg:
            move_piece(state, src, T, ROMANS, LEGION, count=move_leg)
            moved["legions"] = move_leg
        if aux:
            moved["auxilia"] = _move_roman_aux(state, src, T, aux)
        refresh_all_control(state)
    defenders = _rank_battle_targets(state, T, scen)
    if not defenders:
        return [{"free_action": "march", "flag": "card_70_roman_march_battle",
                 "region": T, "moved": moved, "battle": None,
                 "reason": "no Battle target in T after March"}]
    defender = defenders[0]
    rd, rr = _decide_defender_retreat(state, T, ROMANS, defender, False)
    try:
        res = resolve_battle(state, T, ROMANS, defender,
                             retreat_declaration=rd, retreat_region=rr)
    except _EXEC_ERRORS as exc:
        return [{"free_action": "march_battle",
                 "flag": "card_70_roman_march_battle", "region": T,
                 "executed": False, "reason": repr(exc)}]
    return [{"free_action": "march_battle",
             "flag": "card_70_roman_march_battle", "region": T,
             "defender": defender, "moved": moved, "result": res}]


def _resolve_card2_battle(state, faction, region):
    """Card 2 Legiones (shaded): the acting Faction free Battles the Romans in
    ``region`` with auto_legion_loss (the first Roman Loss removes a Legion)."""
    from fs_bot.rules_consts import ROMANS
    from fs_bot.battle.resolve import resolve_battle
    if region is None or faction == ROMANS:
        return [{"free_action": "battle", "flag": "card_2", "executed": False,
                 "reason": "no battle region or Roman actor"}]
    rd, rr = _decide_defender_retreat(state, region, faction, ROMANS, False)
    try:
        res = resolve_battle(state, region, faction, ROMANS,
                             auto_legion_loss=True,
                             retreat_declaration=rd, retreat_region=rr)
    except _EXEC_ERRORS as exc:
        return [{"free_action": "battle", "flag": "card_2",
                 "executed": False, "reason": repr(exc)}]
    return [{"free_action": "battle", "flag": "card_2", "region": region,
             "defender": ROMANS, "result": res}]


def _free_double_aux_battle(state, region, auxilia_only=False):
    """Resolve a Roman free Battle in ``region`` with double Auxilia Losses,
    targeting the top Roman Battle-priority defender (8.8.1). Returns the
    battle result dict, or None if there is no valid target. ``auxilia_only``
    restricts the attack to Auxilia (card 11 Ariovistus)."""
    from fs_bot.rules_consts import ROMANS
    from fs_bot.bots.roman_bot import _rank_battle_targets
    from fs_bot.battle.resolve import resolve_battle
    if region is None:
        return None
    targets = _rank_battle_targets(state, region, state["scenario"])
    if not targets:
        return None
    defender = targets[0]
    rd, rr = _decide_defender_retreat(state, region, ROMANS, defender, False)
    return resolve_battle(state, region, ROMANS, defender,
                          double_auxilia=True, auxilia_only_attack=auxilia_only,
                          retreat_declaration=rd, retreat_region=rr)


def _resolve_double_aux_battle_card(state, region, flag):
    """Cards 11 / 11a (unshaded): free Battle in the Auxilia-placement Region
    with double Auxilia Losses (the placement itself was done by the card
    handler from the derived Region)."""
    res = _free_double_aux_battle(state, region, auxilia_only=(flag == "card_11a"))
    if res is None:
        return [{"free_action": "battle", "flag": flag, "executed": False,
                 "reason": "no Battle target in placement Region"}]
    return [{"free_action": "battle", "flag": flag, "region": region,
             "result": res}]


def _resolve_card6_scout_battle(state):
    """Card 6 Marcus Antonius (unshaded): "Romans may free Scout, then may free
    Battle in 1 Region, Auxilia causing twice usual Losses." Roman free Scout
    (4.2.2) via the Roman Scout node, then a free Battle in the Region chosen
    by Roman Battle priority (8.8.1), with double Auxilia Losses."""
    from fs_bot.rules_consts import ROMANS
    out = []
    # Free Scout (no Resource cost; the Scout node computes the plan).
    try:
        scout = _execute_scout(state, ROMANS, {"sa": _SA_SCOUT,
                                               "sa_regions": [], "details": {}})
        out.append({"free_action": "scout", "flag": "card_6", "result": scout})
    except _EXEC_ERRORS as exc:
        out.append({"free_action": "scout", "flag": "card_6",
                    "executed": False, "reason": repr(exc)})
    # Free Battle in 1 Region (double Auxilia), chosen across all playable
    # Regions by Roman Battle priority.
    from fs_bot.map.map_data import get_playable_regions
    allowed = set(get_playable_regions(state["scenario"], state.get("capabilities")))
    region, _defender = _choose_free_battle(state, ROMANS, allowed)
    if region is None:
        out.append({"free_action": "battle", "flag": "card_6",
                    "executed": False, "reason": "no valid Battle Region"})
        return out
    res = _free_double_aux_battle(state, region)
    if res is None:
        out.append({"free_action": "battle", "flag": "card_6",
                    "executed": False, "reason": "no Battle target"})
    else:
        out.append({"free_action": "battle", "flag": "card_6",
                    "region": region, "result": res})
    return out


def _resolve_a20_free_seize(state):
    """A20 Morbihan (unshaded): after the Arverni are removed from Veneti, the
    Romans free Seize there (§3.2.3 — Forage; Disperse Subdued Tribes only
    where Roman-Controlled). The Seize belongs to the Romans by the card text,
    so it is executed for the Romans regardless of which Faction played the
    Event. If the Romans hold no pieces in Veneti, Seize is not possible there
    and this no-ops (validate_seize_region, §3.2.3).

    A20 shaded (Arverni Ambush near Veneti) is handled separately by
    _resolve_a20_arverni_ambush. (The Arverni are NOT a player Faction in
    Ariovistus: per available_forces_ariovistus.txt and A6.2 they are
    game-run via the Arverni Phase, like the base game's Germans, with
    mechanical Battle-with-Ambush per A6.2.4.)
    """
    from fs_bot.rules_consts import ROMANS, VENETI
    from fs_bot.board.pieces import count_pieces
    from fs_bot.board.control import is_controlled_by
    if count_pieces(state, VENETI, ROMANS) <= 0:
        return [{"free_action": "seize", "flag": "card_A20_free_seize_veneti",
                 "executed": False, "reason": "Romans have no pieces in Veneti"}]
    # Card A20: "free Seize there as if Roman Control" — Disperse Veneti's
    # Subdued Tribes regardless of actual Control.
    try:
        res = _execute_seize(state, ROMANS, {
            "command": _CMD_SEIZE, "sa": SA_ACTION_NONE_LABEL,
            "regions": [VENETI], "details": {"disperse_regions": [VENETI],
                                             "as_if_control": True}})
    except _EXEC_ERRORS as exc:
        return [{"free_action": "seize", "flag": "card_A20_free_seize_veneti",
                 "executed": False, "reason": repr(exc)}]
    return [{"free_action": "seize", "flag": "card_A20_free_seize_veneti",
             "region": VENETI, "result": res}]


def _resolve_a20_arverni_ambush(state):
    """A20 Morbihan (shaded): "If Veneti Arverni Ally, Arverni Warbands within
    1 Region Ambush Romans in a Region within 1 as if there."

    The Arverni are game-run in Ariovistus (A6.2), so this is a mechanical
    Battle-with-Ambush per A6.2.4. The card's "as if there" lets Hidden
    Arverni Warbands within one Region of the Battle Region join the Ambush as
    if present: we gather those projecting Warbands into the Battle Region,
    resolve the standard Ambush (no Retreat, auto-remove; Step 5 Reveal flips
    surviving Hidden Warbands), then return the projected Warbands — now
    Revealed — to their home Regions. Ambush has no Counterattack, so the
    Arverni take no Losses and the projected Warbands are conserved.

    A6.2.4 requires Hidden Arverni Warbands to outnumber the Defender's Hidden
    pieces and the Ambush to cause an enemy Loss. The Battle Region is chosen
    to remove the most Roman pieces.
    """
    from fs_bot.rules_consts import (VENETI, ARVERNI, ROMANS, WARBAND, AUXILIA,
                                     LEGION, FORT, CITADEL, HIDDEN, REVEALED,
                                     ALLY)
    from fs_bot.board.pieces import (count_pieces, count_pieces_by_state,
                                     move_piece, get_leader_in_region)
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_adjacent
    from fs_bot.battle.resolve import resolve_battle

    if count_pieces(state, VENETI, ARVERNI, ALLY) <= 0:
        return [{"free_action": "ambush", "flag": "card_A20_arverni_ambush",
                 "executed": False, "reason": "no Arverni Ally in Veneti"}]
    scen = state["scenario"]
    theater = [VENETI] + list(get_adjacent(VENETI, scen))

    def roman_hidden(region):
        return (count_pieces_by_state(state, region, ROMANS, AUXILIA, HIDDEN)
                + count_pieces_by_state(state, region, ROMANS, WARBAND, HIDDEN))

    best = None  # (B, sources, projected, damage)
    for B in theater:
        if count_pieces(state, B, ROMANS) <= 0:
            continue
        # Projecting Hidden Arverni Warbands: in B, plus adjacent Regions that
        # are themselves within 1 of Veneti ("within 1 Region ... as if there").
        proj_regions = [B] + [r for r in get_adjacent(B, scen) if r in theater]
        sources = {r: count_pieces_by_state(state, r, ARVERNI, WARBAND, HIDDEN)
                   for r in proj_regions}
        sources = {r: n for r, n in sources.items() if n > 0}
        projected = sum(sources.values())
        if projected <= 0 or projected <= roman_hidden(B):
            continue
        # Arverni cause floor(Warbands * 1/2); halved again vs Fort/Citadel.
        raw = projected * 0.5
        if (count_pieces(state, B, ROMANS, FORT) > 0
                or count_pieces(state, B, ROMANS, CITADEL) > 0):
            raw *= 0.5
        predicted = int(raw)
        removable = (count_pieces(state, B, ROMANS, AUXILIA)
                     + count_pieces(state, B, ROMANS, LEGION)
                     + (1 if get_leader_in_region(state, B, ROMANS) else 0))
        damage = min(predicted, removable)
        if damage <= 0:
            continue
        if best is None or damage > best[3]:
            best = (B, sources, projected, damage)

    if best is None:
        return [{"free_action": "ambush", "flag": "card_A20_arverni_ambush",
                 "executed": False, "reason": "no valid Ambush within 1 of Veneti"}]

    B, sources, projected, _ = best
    moved = {}
    for r, n in sources.items():
        if r == B:
            continue
        move_piece(state, r, B, ARVERNI, WARBAND, count=n, piece_state=HIDDEN)
        moved[r] = n
    try:
        res = resolve_battle(state, B, attacking_faction=ARVERNI,
                             defending_faction=ROMANS, is_ambush=True)
    except _EXEC_ERRORS as exc:
        # Restore on failure to keep the board consistent.
        for r, n in moved.items():
            avail = count_pieces_by_state(state, B, ARVERNI, WARBAND, HIDDEN)
            take = min(n, avail)
            if take > 0:
                move_piece(state, B, r, ARVERNI, WARBAND, count=take,
                           piece_state=HIDDEN)
        refresh_all_control(state)
        return [{"free_action": "ambush", "flag": "card_A20_arverni_ambush",
                 "executed": False, "reason": repr(exc)}]
    # Return projected Warbands (now Revealed by Step 5) to their Regions.
    for r, n in moved.items():
        avail = count_pieces_by_state(state, B, ARVERNI, WARBAND, REVEALED)
        take = min(n, avail)
        if take > 0:
            move_piece(state, B, r, ARVERNI, WARBAND, count=take,
                       piece_state=REVEALED)
    refresh_all_control(state)
    return [{"free_action": "ambush", "flag": "card_A20_arverni_ambush",
             "region": B, "defender": ROMANS, "projected_warbands": projected,
             "result": res}]


def _move_roman_aux(state, src, dst, n):
    """Move up to n Roman Auxilia src->dst, Hidden first then Revealed."""
    from fs_bot.rules_consts import ROMANS, AUXILIA, HIDDEN, REVEALED
    from fs_bot.board.pieces import count_pieces_by_state, move_piece
    moved = 0
    for ps in (HIDDEN, REVEALED):
        if moved >= n:
            break
        avail = count_pieces_by_state(state, src, ROMANS, AUXILIA, ps)
        take = min(avail, n - moved)
        if take > 0:
            move_piece(state, src, dst, ROMANS, AUXILIA, count=take,
                       piece_state=ps)
            moved += take
    return moved


def _resolve_a17_march_battle(state):
    """A17 Publius Licinius Crassus (unshaded): "Romans may free March a group
    of 1-4 Legions and 1-8 Auxilia to a Region without Caesar and Battle
    there, double Losses by Auxilia."

    Roman NP instruction (Ariovistus): "Move Forces using Roman March
    priorities (8.8.3), then for 'Publius' use Roman Battle priorities
    (8.8.1)." So the destination is taken from the Roman March destination
    ranking (8.8.1/8.8.3), restricted to Regions without Caesar that have an
    adjacent Roman group to bring in; the Battle target is the top Roman
    Battle-priority defender there; the Battle applies double Auxilia Losses.
    """
    from fs_bot.rules_consts import ROMANS, CAESAR, LEGION, AUXILIA
    from fs_bot.board.pieces import (count_pieces, get_leader_in_region,
                                     move_piece)
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_adjacent
    from fs_bot.bots.roman_bot import (_rank_march_destinations,
                                       _rank_battle_targets)
    from fs_bot.battle.resolve import resolve_battle

    scen = state["scenario"]
    ranked = _rank_march_destinations(state, scen)  # [(region, enemy), ...]
    for T, _enemy in ranked:
        if get_leader_in_region(state, T, ROMANS) == CAESAR:
            continue  # "to a Region without Caesar"
        # Adjacent source with the most Roman Legions+Auxilia (Caesar stays).
        best_src = None
        for src in get_adjacent(T, scen):
            leg = count_pieces(state, src, ROMANS, LEGION)
            aux = count_pieces(state, src, ROMANS, AUXILIA)
            if leg + aux <= 0:
                continue
            if best_src is None or (leg + aux) > best_src[1]:
                best_src = (src, leg + aux, leg, aux)
        if best_src is None:
            continue
        src, _tot, leg, aux = best_src
        move_leg = min(4, leg)
        move_aux = min(8, aux)
        if move_leg + move_aux <= 0:
            continue
        if move_leg:
            move_piece(state, src, T, ROMANS, LEGION, count=move_leg)
        if move_aux:
            _move_roman_aux(state, src, T, move_aux)
        refresh_all_control(state)
        # Battle the top Roman-priority defender in T (double Auxilia Losses).
        targets = _rank_battle_targets(state, T, scen)
        if not targets:
            return [{"free_action": "march", "flag":
                     "card_A17_roman_march_battle", "region": T,
                     "moved": {"legions": move_leg, "auxilia": move_aux},
                     "battle": None, "reason": "no Battle target in T"}]
        defender = targets[0]
        retreat_decl, retreat_region = _decide_defender_retreat(
            state, T, ROMANS, defender, False)
        try:
            res = resolve_battle(state, T, ROMANS, defender,
                                 double_auxilia=True,
                                 retreat_declaration=retreat_decl,
                                 retreat_region=retreat_region)
        except _EXEC_ERRORS as exc:
            return [{"free_action": "march_battle",
                     "flag": "card_A17_roman_march_battle", "region": T,
                     "executed": False, "reason": repr(exc)}]
        return [{"free_action": "march_battle",
                 "flag": "card_A17_roman_march_battle", "region": T,
                 "defender": defender,
                 "moved": {"legions": move_leg, "auxilia": move_aux},
                 "result": res}]
    return [{"free_action": "march_battle", "flag":
             "card_A17_roman_march_battle", "executed": False,
             "reason": "no Caesar-free destination with an adjacent Roman group"}]


def _resolve_a19_march_romans(state, faction):
    """A19 Gaius Valerius Procillus (shaded): "March all Romans in 1 Region to
    an adjacent one with Germans."

    German NP instruction (Ariovistus): "Play only to move to where no Fort
    and Germans will outnumber Romans." So a Germanic actor relocates all
    Roman mobile pieces (Caesar, Legions, Auxilia) from a source Region into
    an adjacent destination that (a) contains Germans, (b) has no Fort, and
    (c) where, after the move, German mobile force outnumbers the Roman mobile
    force — trapping the Romans for a German attack. Among valid moves, the
    one trapping the most Roman pieces (then the largest German advantage) is
    chosen. Only the Germanic path is specified; other Factions no-op.
    """
    from fs_bot.rules_consts import (GERMANS, ROMANS, CAESAR, LEADER, LEGION,
                                     AUXILIA, WARBAND, FORT, HIDDEN, REVEALED,
                                     SCOUTED, ARIOVISTUS_LEADER)
    from fs_bot.board.pieces import (count_pieces, count_pieces_by_state,
                                     get_leader_in_region, move_piece)
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_adjacent, get_playable_regions
    if faction != GERMANS:
        return []
    scen = state["scenario"]
    playable = get_playable_regions(scen, state.get("capabilities"))

    def roman_mobile(r):
        m = (count_pieces(state, r, ROMANS, LEGION)
             + count_pieces(state, r, ROMANS, AUXILIA))
        if get_leader_in_region(state, r, ROMANS) == CAESAR:
            m += 1
        return m

    def german_mobile(r):
        m = count_pieces(state, r, GERMANS, WARBAND)
        if get_leader_in_region(state, r, GERMANS) == ARIOVISTUS_LEADER:
            m += 1
        return m

    best = None  # (S, D, trapped, advantage)
    for S in sorted(playable):
        rs = roman_mobile(S)
        if rs <= 0:
            continue
        for D in get_adjacent(S, scen):
            if count_pieces(state, D, GERMANS) <= 0:        # "with Germans"
                continue
            if count_pieces(state, D, ROMANS, FORT) > 0:     # "no Fort"
                continue
            romans_after = roman_mobile(D) + rs
            adv = german_mobile(D) - romans_after
            if adv <= 0:                                     # "outnumber"
                continue
            key = (rs, adv)
            if best is None or key > (best[2], best[3]):
                best = (S, D, rs, adv)

    if best is None:
        return [{"free_action": "march_romans", "flag":
                 "card_A19_march_romans", "executed": False,
                 "reason": "no move where Germans outnumber Romans (no Fort)"}]

    S, D, trapped, adv = best
    # Move all Roman mobile pieces S -> D (Caesar, then Legions, then Auxilia).
    moved = {"caesar": False, "legions": 0, "auxilia": 0}
    if get_leader_in_region(state, S, ROMANS) == CAESAR:
        move_piece(state, S, D, ROMANS, LEADER)
        moved["caesar"] = True
    legs = count_pieces(state, S, ROMANS, LEGION)
    if legs:
        move_piece(state, S, D, ROMANS, LEGION, count=legs)
        moved["legions"] = legs
    for ps in (HIDDEN, REVEALED, SCOUTED):
        a = count_pieces_by_state(state, S, ROMANS, AUXILIA, ps)
        if a:
            move_piece(state, S, D, ROMANS, AUXILIA, count=a, piece_state=ps)
            moved["auxilia"] += a
    refresh_all_control(state)
    return [{"free_action": "march_romans", "flag": "card_A19_march_romans",
             "source": S, "dest": D, "moved": moved,
             "german_advantage": adv}]


def _resolve_a67_arduenna(state, faction):
    """A67 Arduenna (German NP path): March Warbands+Leader into Nervii or
    Treveri to take Germanic Control of a Region with player pieces (Roman,
    then Aedui, then Belgae), then free Battle that player there, then flip
    the German pieces there Hidden.

    Per the German Ariovistus event instruction for "Arduenna, Impetuosity".
    Only the German path is specified by the references; other Factions no-op
    (documented). The "without losing Germanic Control" constraint is honored
    by only Marching from adjacent origins the Germans do not Control (no
    Control to lose); gathering surplus from Controlled origins is a
    documented refinement.
    """
    from fs_bot.rules_consts import (GERMANS, ROMANS, AEDUI, BELGAE, WARBAND,
                                     NERVII, TREVERI, REVEALED, HIDDEN, AUXILIA)
    from fs_bot.board.pieces import (count_pieces, count_pieces_by_state,
                                     flip_piece)
    from fs_bot.board.control import is_controlled_by
    from fs_bot.map.map_data import get_adjacent
    out = []
    if faction != GERMANS:
        return out
    priority = (ROMANS, AEDUI, BELGAE)

    def player_in(region):
        for pf in priority:
            if count_pieces(state, region, pf) > 0:
                return pf
        return None

    # Choose target: Nervii/Treveri holding the highest-priority player.
    target, defender = None, None
    for region in (NERVII, TREVERI):
        pf = player_in(region)
        if pf is None:
            continue
        if defender is None or priority.index(pf) < priority.index(defender):
            target, defender = region, pf
    if target is None:
        return out

    # March German Warbands+Leader from adjacent origins the Germans do NOT
    # Control (no Control lost) one step into the target, to build force.
    marched = []
    for origin in get_adjacent(target, state["scenario"]):
        if is_controlled_by(state, origin, GERMANS):
            continue
        grp = _mobile_march_group(state, faction, origin)
        if not _group_has_pieces(grp):
            continue
        try:
            final = _march_with_harassment(state, faction, origin, [target])
            marched.append({"origin": origin, "final_region": final})
        except _EXEC_ERRORS:
            continue
    out.append({"free_action": "march", "flag": "card_A67_arduenna",
                "target": target, "marches": marched})

    # Free Battle the priority player there (Retreat allowed).
    if count_pieces(state, target, faction, WARBAND) > 0 and \
            count_pieces(state, target, defender) > 0:
        try:
            res = _execute_battle(state, faction, {
                "command": _CMD_BATTLE, "sa": SA_ACTION_NONE_LABEL,
                "sa_regions": [],
                "details": {"battle_plan": [{"region": target,
                                             "target": defender}]}})
            out.append({"free_action": "battle", "flag": "card_A67_arduenna",
                        "region": target, "defender": defender, "result": res})
        except _EXEC_ERRORS as exc:
            out.append({"free_action": "battle", "flag": "card_A67_arduenna",
                        "executed": False, "reason": repr(exc)})

    # Flip the German pieces in the target Hidden (the card's final step).
    flipped = 0
    for pt in (WARBAND, AUXILIA):
        rev = count_pieces_by_state(state, target, faction, pt, REVEALED)
        if rev > 0:
            flip_piece(state, target, faction, pt, rev,
                       from_state=REVEALED, to_state=HIDDEN)
            flipped += rev
    if flipped:
        out.append({"free_action": "flip_hidden", "flag": "card_A67_arduenna",
                    "region": target, "flipped": flipped})
    return out


def _resolve_a58_battle_seize(state, faction):
    from fs_bot.rules_consts import ROMANS, BELGICA_REGIONS
    from fs_bot.board.pieces import count_pieces
    from fs_bot.board.control import is_controlled_by
    out = []
    if faction != ROMANS:
        return out
    belgica = set(BELGICA_REGIONS)
    # Free Battle in Belgica (Retreat allowed — the card sets no no-Retreat).
    region, defender = _choose_free_battle(state, faction, belgica)
    if region is not None:
        try:
            res = _execute_battle(state, faction, {
                "command": _CMD_BATTLE, "sa": SA_ACTION_NONE_LABEL,
                "sa_regions": [],
                "details": {"battle_plan": [{"region": region,
                                             "target": defender}]}})
            out.append({"free_action": "battle", "flag":
                        "card_A58_roman_battle_seize", "region": region,
                        "defender": defender, "result": res})
        except _EXEC_ERRORS as exc:
            out.append({"free_action": "battle",
                        "flag": "card_A58_roman_battle_seize",
                        "executed": False, "reason": repr(exc)})
    # Free Seize in Belgica Regions where Romans have pieces; Disperse where
    # Roman-Controlled (get_dispersible_tribes enforces the cap/Control).
    seize_regions = [r for r in BELGICA_REGIONS
                     if count_pieces(state, r, ROMANS) > 0]
    if seize_regions:
        # "as if Roman Control, with no Harassment": Disperse every Seize
        # Region's Subdued Tribes regardless of actual Control, no Harassment.
        try:
            sres = _execute_seize(state, faction, {
                "command": _CMD_SEIZE, "sa": SA_ACTION_NONE_LABEL,
                "regions": seize_regions,
                "details": {"disperse_regions": seize_regions,
                            "as_if_control": True, "no_harassment": True}})
            out.append({"free_action": "seize",
                        "flag": "card_A58_roman_battle_seize",
                        "regions": seize_regions, "result": sres})
        except _EXEC_ERRORS as exc:
            out.append({"free_action": "seize",
                        "flag": "card_A58_roman_battle_seize",
                        "executed": False, "reason": repr(exc)})
    return out


def _execute_event(state, faction, bot_action, *, human=False):
    """Execute an Event via the card_effects dispatcher.

    The decision carries the card id and the Dual-Use text preference
    (§8.2.2 / A8.2.2). We map that preference to the dispatcher's ``shaded``
    flag. Unimplemented card stubs or unknown ids are reported, not raised, so
    a full game keeps running.

    NP (bot) Events auto-derive their parameter choices per §8.2.3/§8.3.1. A
    human Event (``human=True``) instead uses the params the player supplied in
    ``details['event_params']`` — a human chooses for themselves, so the NP
    auto-derivation is skipped.
    """
    details = bot_action.get("details") or {}
    card_id = details.get("card_id", state.get("current_card"))
    shaded = details.get("text_preference") == EVENT_SHADED

    # Populate event_params before resolving; restore afterwards. For a bot,
    # derive the NP choice (§8.2.3/§8.3.1). For a human, take the player's own
    # params from the plan (no NP derivation). Cards whose choices aren't
    # available still raise ValueError and are reported, not crashed.
    prev_params = state.get("event_params")
    if human:
        derived = details.get("event_params")
    else:
        derived = _derive_event_params(state, faction, card_id, shaded)
    # Always expose a dict (never None) so card handlers that read
    # state.get("event_params").get(...) don't crash on missing params.
    state["event_params"] = {**(prev_params or {}), **(derived or {})}
    # Many card handlers read state["executing_faction"] to know who is
    # playing the Event; it was never set, so those cards no-op. Set it for
    # the acting faction (restored afterwards).
    prev_faction = state.get("executing_faction")
    state["executing_faction"] = faction
    try:
        event_result = execute_event(state, card_id, shaded=shaded)
    except _EVENT_SAFE_ERRORS as exc:
        # Ineffective/non-applicable Event in this state (missing pieces, a
        # stub, or a choice not derivable here). Report, do not crash.
        state["event_params"] = prev_params
        state["executing_faction"] = prev_faction
        return {"executed": False, "command": _CMD_EVENT,
                "card_id": card_id, "shaded": shaded,
                "reason": f"event not applicable: {exc!r}"}
    free_actions = _resolve_free_actions(state, faction)
    state["event_params"] = prev_params
    state["executing_faction"] = prev_faction
    result = {"executed": True, "command": _CMD_EVENT,
              "card_id": card_id, "shaded": shaded,
              "event_result": event_result}
    if free_actions:
        result["free_actions"] = free_actions
    return result


def _execute_seize(state, faction, bot_action):
    """Execute a Seize Command — §3.2.3, target priorities §8.8.5.

    The Roman bot supplies ``regions`` (all Seize regions, dispersal-capable
    first) and ``details['disperse_regions']`` (the subset where Dispersal
    should occur). In each dispersal region we Disperse the Subdued tribes
    the rules allow (`get_dispersible_tribes`, which already enforces Roman
    Control and the 4-marker cap); remaining regions still Forage.

    The accompanying Build Special Activity is executed by the orchestration
    layer (_execute_sa, reported under ``sa_execution``), not here.
    """
    details = bot_action.get("details") or {}
    regions = [r for r in (bot_action.get("regions") or []) if isinstance(r, str)]
    disperse_regions = {r for r in (details.get("disperse_regions") or [])
                        if isinstance(r, str)}

    per_region = []
    dispersed_total = 0
    forage_total = 0
    errors = []

    as_if_control = bool(details.get("as_if_control"))
    no_harassment = bool(details.get("no_harassment"))
    for region in regions:
        if region in disperse_regions:
            tribes = get_dispersible_tribes(state, region,
                                            as_if_control=as_if_control)
        else:
            tribes = []
        try:
            res = seize_in_region(state, region, tribes_to_disperse=tribes,
                                  as_if_control=as_if_control)
        except _EXEC_ERRORS as exc:
            errors.append({"region": region, "error": str(exc)})
            continue
        dispersed_total += len(res.get("tribes_dispersed", []))
        forage_total += res.get("forage_resources", 0)
        # Harassment against the seizing Romans — §3.2.3 / §8.4.2 (suppressed
        # when the card grants Seize "with no Harassment", e.g. A58).
        harass = None if no_harassment else _resolve_seize_harassment(state, region)
        if harass:
            res = dict(res)
            res["harassment"] = harass
        per_region.append(res)

    return {
        "executed": len(per_region) > 0,
        "command": _CMD_SEIZE,
        "regions_resolved": [r["region"] for r in per_region],
        "tribes_dispersed_total": dispersed_total,
        "forage_resources_total": forage_total,
        "errors": errors,
    }


def _execute_raid(state, faction, bot_action):
    """Execute a Raid Command — §3.3.3.

    Bots emit ``details['raid_plan']`` as a flat list of per-flip entries
    ``{"region": R, "target": faction_or_None}`` (steal from ``target`` or,
    when None, gain 1 Resource). All four raiding bots (Arverni, Aedui,
    Belgae, German) share this shape. We group flips by region in order,
    cap at the rules' 2 flips per region (§3.3.3), translate each flip to a
    raid action, and call ``raid_in_region`` once per region.

    Any accompanying Special Activity (Devastate/Entreat/Intimidate) is
    executed by the orchestration layer (_execute_sa), not here.
    """
    details = bot_action.get("details") or {}
    raid_plan = details.get("raid_plan", []) or []

    # Preserve region order of first appearance.
    by_region = {}
    order = []
    for entry in raid_plan:
        region = entry.get("region")
        if region is None:
            continue
        if region not in by_region:
            by_region[region] = []
            order.append(region)
        if entry.get("target") is None:
            by_region[region].append({"type": "gain"})
        else:
            by_region[region].append(
                {"type": "steal", "target": entry["target"]})

    per_region = []
    gained_total = 0
    errors = []
    for region in order:
        actions = by_region[region][:2]  # §3.3.3: max 2 Warbands/Region
        if not actions:
            continue
        try:
            res = raid_in_region(state, region, faction, actions)
        except _EXEC_ERRORS as exc:
            errors.append({"region": region, "error": str(exc)})
            continue
        gained_total += res.get("resources_gained", 0)
        per_region.append(res)

    return {
        "executed": len(per_region) > 0,
        "command": _CMD_RAID,
        "regions_resolved": [r["region"] for r in per_region],
        "resources_gained_total": gained_total,
        "errors": errors,
    }


def _execute_rally(state, faction, bot_action):
    """Execute a Rally Command — §3.3.1 (Gallic) / A8.7.4 (German).

    The bot supplies ``details['rally_plan']`` with up to three sub-lists,
    executed in flowchart order so freed Allies are available downstream:
      1. ``citadels``: ``{"region", "tribe"}`` — replace an Allied City Tribe
         with a Citadel (Gallic only; Germans have none).
      2. ``allies``:   ``{"region", "tribe"[, "cost"]}`` — place an Ally at a
         Subdued Tribe.
      3. ``warbands``: either a region string (Gallic) or ``{"region", ...}``
         (German) — place Warbands up to the region cap.

    Each sub-action calls ``rally_in_region`` (which enforces caps, cost, and
    prerequisites). Per-region CommandErrors are captured, not raised, so a
    plan that outruns Resources resolves as far as it legally can.
    """
    details = bot_action.get("details") or {}
    plan = details.get("rally_plan", {}) or {}

    placed = []
    errors = []

    def _do(region, action, tribe=None):
        try:
            res = rally_in_region(state, region, faction, action, tribe=tribe)
            placed.append({"region": region, "action": action,
                           "tribe": tribe})
        except _EXEC_ERRORS as exc:
            errors.append({"region": region, "action": action,
                           "error": str(exc)})

    for entry in plan.get("citadels", []) or []:
        _do(entry["region"], "place_citadel", entry.get("tribe"))
    for entry in plan.get("allies", []) or []:
        _do(entry["region"], "place_ally", entry.get("tribe"))
    for entry in plan.get("warbands", []) or []:
        region = entry if isinstance(entry, str) else entry.get("region")
        if region is not None:
            _do(region, "place_warbands")

    return {
        "executed": len(placed) > 0,
        "command": _CMD_RALLY,
        "placements": placed,
        "errors": errors,
    }


def _execute_battle(state, faction, bot_action):
    """Execute a Battle Command — §3.2.4 / §3.3.4 / §3.4.4.

    The bot supplies ``details['battle_plan']`` as a list of per-region
    entries. Two shapes exist: most bots emit ``{"region", "target"}`` (a
    single defending faction), while the Roman bot emits
    ``{"region", "targets": [...]}`` (defenders ranked by priority); we
    Battle the top-ranked defender per region.

    Battle-modifying Special Activities are applied as parameters to
    ``resolve_battle``:
      - Ambush (§4.3.3/§4.5.3/A4.6.3): ``is_ambush=True`` where the bot's
        ``sa`` is Ambush and the region is in ``sa_regions`` (eligibility was
        already gated by the bot's _check_ambush).
      - Besiege (§4.2.3/A4.2.3, Roman): remove a Citadel (else Ally, else
        Settlement) before Losses, chosen via get_besiege_targets.

    Defender Retreat is left to auto-determination (no retreat); routing the
    defender bot's Retreat decision (§8.4.3) is a separate workstream. Other
    standalone SAs accompanying a Battle (Scout, Intimidate) are not executed
    here.
    """
    details = bot_action.get("details") or {}
    battle_plan = details.get("battle_plan", []) or []
    # Free-Battle events may forbid the defender's Retreat (§ card text).
    no_retreat = bool(details.get("no_retreat"))
    force_retreat = bool(details.get("force_retreat"))
    allied_factions = tuple(details.get("allied_factions") or ())
    warband_full_loss = bool(details.get("warband_full_loss"))
    sa = bot_action.get("sa")
    # sa_regions are string Region names for Ambush/Besiege; other SAs
    # (e.g. Intimidate) carry dict plans we ignore here, so filter to strings.
    sa_regions = {r for r in (bot_action.get("sa_regions") or [])
                  if isinstance(r, str)}

    battles = []
    errors = []
    for entry in battle_plan:
        region = entry.get("region")
        if region is None:
            continue
        # Single target, or Roman ranked targets list -> take the top.
        if "target" in entry and entry["target"] is not None:
            defender = entry["target"]
        else:
            targets = entry.get("targets") or []
            defender = targets[0] if targets else None
        if defender is None:
            continue
        # A Battle requires the defender to actually be present in the Region
        # (§3.x) — skip a no-target entry rather than resolving a no-op.
        if count_pieces(state, region, defender) <= 0:
            errors.append({"region": region, "defender": defender,
                           "error": "defender not present"})
            continue

        is_ambush = (sa == _SA_AMBUSH and region in sa_regions)

        besiege_target = None
        if sa == _SA_BESIEGE and region in sa_regions:
            options = get_besiege_targets(state, region, defender)
            if options:
                besiege_target = options[0]  # Citadel > Ally > Settlement

        try:
            if no_retreat:
                retreat_decl, retreat_region = (False, None)
            elif force_retreat:
                _d, _dest = _decide_defender_retreat(
                    state, region, faction, defender, is_ambush)
                retreat_decl, retreat_region = (True, _dest)
            else:
                retreat_decl, retreat_region = _decide_defender_retreat(
                    state, region, faction, defender, is_ambush)
            res = resolve_battle(
                state, region, faction, defender,
                is_ambush=is_ambush, besiege_target=besiege_target,
                retreat_declaration=retreat_decl,
                retreat_region=retreat_region,
                allied_factions=allied_factions,
                warband_full_loss=warband_full_loss,
            )
        except _EXEC_ERRORS as exc:
            errors.append({"region": region, "defender": defender,
                           "error": str(exc)})
            continue
        battles.append({"region": region, "defender": defender,
                        "is_ambush": is_ambush,
                        "besiege": besiege_target,
                        "result": res})

    return {
        "executed": len(battles) > 0,
        "command": _CMD_BATTLE,
        "battles_resolved": [(b["region"], b["defender"]) for b in battles],
        "count": len(battles),
        "errors": errors,
    }


def _execute_recruit(state, faction, bot_action):
    """Execute a Roman Recruit — §3.2.1 / §8.8.4.

    The Roman bot now emits ``details['recruit_plan']`` as an ordered list of
    ``{"region", "action", ["tribe"]}`` entries (all Allies able, then all
    Auxilia able, Supply-Line Regions first). Each entry calls
    ``recruit_in_region`` (which enforces eligibility, caps, and cost).
    Per-region errors are captured so the plan resolves as far as Resources
    allow. The accompanying Build SA is executed by the orchestration layer
    (_execute_sa) before this Recruit (§8.8.4).
    """
    details = bot_action.get("details") or {}
    plan = details.get("recruit_plan", []) or []

    placed = []
    errors = []
    superseded = []
    for entry in plan:
        region = entry.get("region")
        action = entry.get("action")
        if region is None or action is None:
            continue
        tribe = entry.get("tribe")
        if action == "place_ally" and tribe is not None:
            # The Build SA resolves BEFORE this Recruit (§8.8.4 'Build
            # before Recruit') and may itself have allied the planned
            # tribe. Re-derive against the current board: keep the planned
            # tribe if still eligible, substitute another eligible Subdued
            # Tribe there, or drop the entry as superseded (not an error —
            # the piece the entry wanted is already on the map).
            from fs_bot.commands.rally import _find_subdued_tribe_for_ally
            eligible_now = _find_subdued_tribe_for_ally(state, region,
                                                        _ROMANS_F) or []
            if tribe not in eligible_now:
                replacement = next(
                    (t for t in eligible_now
                     if not any(p.get("tribe") == t for p in placed)), None)
                if replacement is None:
                    superseded.append({"region": region, "tribe": tribe})
                    continue
                tribe = replacement
            # The Build SA (§8.8.4 'Build before Recruit') may have placed the
            # Allies this Recruit planned, emptying the shared Ally pool. "Place
            # all Allies ABLE" — once none are Available, skip the entry as
            # superseded rather than letting the executor refuse it.
            from fs_bot.board.pieces import get_available as _get_avail
            from fs_bot.rules_consts import ALLY as _ALLY_C
            if _get_avail(state, _ROMANS_F, _ALLY_C) < 1:
                superseded.append({"region": region, "tribe": tribe})
                continue
        try:
            res = recruit_in_region(state, region, action, tribe=tribe)
            placed.append({"region": region, "action": action,
                           "tribe": tribe})
        except _EXEC_ERRORS as exc:
            errors.append({"region": region, "action": action,
                           "error": str(exc)})

    result = {
        "executed": len(placed) > 0,
        "command": _CMD_RECRUIT,
        "placements": placed,
        "errors": errors,
    }
    if superseded:
        result["superseded_by_build"] = superseded
    return result


def _mobile_march_group(state, faction, region):
    """Build a march group dict of ALL mobile pieces a faction has in region.

    Mobile = Leader + Legions + Auxilia + Warbands (totals across Hidden /
    Revealed / Scouted). This matches the threat-March instruction to "March
    all mobile Forces out of" a Region.
    """
    from fs_bot.rules_consts import LEADER, LEGION, AUXILIA, WARBAND
    group = {
        LEADER: get_leader_in_region(state, region, faction),
        LEGION: count_pieces(state, region, faction, LEGION),
        AUXILIA: count_pieces(state, region, faction, AUXILIA),
        WARBAND: count_pieces(state, region, faction, WARBAND),
    }
    return group


def _group_has_pieces(group):
    from fs_bot.rules_consts import LEADER
    for k, v in group.items():
        if k == LEADER:
            if v is not None:
                return True
        elif v:
            return True
    return False


def _execute_march(state, faction, bot_action):
    """Execute a March Command — threat-March case only (§8.5.1/A8.7.1 etc.).

    SCOPE: Only the execution-complete "threat" March shape is wired here —
    a plan carrying flat ``origins`` and ``destinations`` lists, whose
    flowchart instruction is to "March all mobile Forces out of each origin
    Region." For each origin we move its entire mobile group one step into an
    adjacent planned destination (chosen with the rules' §8.3.4 random tie-
    break when several are adjacent). march_group enforces adjacency, crossing
    stops, and cost.

    DEFERRED (returns executed=False with a reason, never guesses):
      - The "expand/mass/spread" March nodes, whose plans use different,
        decision-level keys (control_destinations, spread_destinations,
        leader_or_group_destination, ...) and imply leave-behind choices.
      - Multi-step routing to non-adjacent destinations.
      - Mid-March Harassment (§3.2.2-3) and per-group leave-behind to retain
        Control. These need bot-side plan enrichment, a separate workstream.
    """
    details = bot_action.get("details") or {}
    # Threat-March plans live either nested under "march_plan" (Belgae/German/
    # Arverni) or flat in details (Roman node_r_march). Accept both.
    plan = details.get("march_plan") or details
    origins = plan.get("origins")
    destinations = plan.get("destinations")

    if not (isinstance(origins, list) and isinstance(destinations, list)
            and origins and destinations):
        # Not the flat threat shape — try the expand/mass/spread/control shape,
        # which carries leader/spread/control destinations instead.
        return _execute_expand_march(state, faction, plan)

    # Normalize destinations to Region-name strings. The Roman bot emits
    # (region, target_faction) tuples; the others emit plain strings.
    destinations = [d[0] if isinstance(d, (list, tuple)) else d
                    for d in destinations]
    origins = [o[0] if isinstance(o, (list, tuple)) else o for o in origins]

    origin_set = set(origins)
    dest_pool = [d for d in destinations if d not in origin_set]

    scenario = state["scenario"]
    playable = set(get_playable_regions(scenario, state.get("capabilities")))

    marched = []
    errors = []
    deferred_origins = []
    for origin in origins:
        if not _group_has_pieces(_mobile_march_group(state, faction, origin)):
            continue
        # Choose the nearest reachable planned destination; BFS the path.
        best = None  # (path_len, dest, path)
        for d in dest_pool:
            path = _bfs_march_path(origin, d, playable)
            if path is None:
                continue
            if best is None or len(path) < best[0]:
                best = (len(path), d, path)
            elif len(path) == best[0]:
                # §8.3.4 random tie-break among equidistant destinations.
                if random_select(state, [best[1], d]) == d:
                    best = (len(path), d, path)
        if best is None:
            deferred_origins.append(origin)
            continue
        try:
            final = _march_with_harassment(state, faction, origin, best[2])
            marched.append({"origin": origin, "final_region": final})
        except _EXEC_ERRORS as exc:
            errors.append({"origin": origin, "error": str(exc)})

    return {
        "executed": len(marched) > 0,
        "command": _CMD_MARCH,
        "marches": marched,
        "deferred_origins": deferred_origins,
        "errors": errors,
    }


def _bfs_march_path(origin, dest, playable):
    """Shortest adjacency path origin -> dest over playable Regions.

    Returns the list of Regions to move into (excluding origin), or None if
    unreachable. Used to route a March to a planned but non-adjacent
    destination (the destination is the bot's choice; only the path is
    derived).
    """
    from collections import deque
    from fs_bot.map.map_data import get_adjacent
    if origin == dest:
        return []
    seen = {origin}
    q = deque([(origin, [])])
    while q:
        cur, path = q.popleft()
        for nb in sorted(get_adjacent(cur)):
            if nb in seen or nb not in playable:
                continue
            npath = path + [nb]
            if nb == dest:
                return npath
            seen.add(nb)
            q.append((nb, npath))
    return None


def _march_with_harassment(state, faction, origin, path):
    """March a faction's full mobile group origin -> ... -> path[-1], one step
    at a time, resolving Harassment (§3.2.2 / §8.4.2) in each Region the group
    enters and then leaves. Returns the final Region reached.
    """
    # §3.2.2: marching pieces flip to Hidden as they March.
    _flip_origin_pieces(state, origin, faction)
    # §3.2.2: the marching group is SELECTED AT THE ORIGIN and carried through
    # the whole path. It must NOT be recomputed from each intermediate Region:
    # doing so absorbed that Region's RESIDENT forces into the march (and tried
    # to move resident Revealed Warbands as Hidden, e.g. "Only 1 Hidden Warband
    # in <R>, need 15"), and applied Harassment to residents too. Pieces do not
    # join a March mid-route; Harassment only hits the marching group.
    group = _mobile_march_group(state, faction, origin)
    current = origin
    for i, nxt in enumerate(path):
        if not _group_has_pieces(group):
            break
        res = march_group(state, faction, current, [nxt], group)
        current = res.get("final_region", nxt)
        if current != nxt:
            break  # a crossing stop halted the group early
        # Intermediate Region (entered then about to be left) -> Harassment
        # against the carried group only; survivors continue.
        if i < len(path) - 1:
            harassers = _np_harassers(state, current, faction, group)
            if harassers:
                from fs_bot.commands.march import resolve_harassment
                hres = resolve_harassment(state, current, faction, group,
                                          harassing_factions=harassers)
                _apply_harassment_losses_to_group(group, hres)
    return current


def _apply_harassment_losses_to_group(group, harass_result):
    """Subtract Harassment removals from the carried marching group so the
    next hop moves only the survivors (§3.2.2). Removals are
    ``(piece_type, count, roll_or_None)``; a removed Leader clears the slot.
    """
    from fs_bot.rules_consts import LEADER
    for fl in (harass_result or {}).get("losses_by_faction", []):
        for removal in fl.get("removals", []):
            ptype, count = removal[0], removal[1]
            if ptype == LEADER:
                group[LEADER] = None
            else:
                group[ptype] = max(0, group.get(ptype, 0) - count)


def _sa_detail(bot_action, key):
    """Fetch an SA plan by key from an action's details, tolerating both
    layouts bots use: merged at the top level (Belgae) OR nested under
    details["sa_details"] (Aedui, German battle).
    """
    d = bot_action.get("details") or {}
    if d.get(key) is not None:
        return d.get(key)
    return (d.get("sa_details") or {}).get(key)


def _execute_sa(state, faction, bot_action):
    """Execute a standalone Special Activity accompanying a Command.

    Returns a result dict, or None when there is no standalone SA to run
    (No SA, or a battle-modifying SA already handled in _execute_battle).

    Wired (execution-complete from the bot plan):
      - Trade (Aedui): trade(state) — no targets.
      - Settle (German): settle(state, region) for each sa_region.
      - Devastate (Arverni/Aedui): devastate_region(state, region) per region.
      - Intimidate (German): intimidate(...) grouped by region + target.

    Deferred (need faithful plan translation / secondary choices — reported,
    not guessed): Build, Scout, Entreat, Suborn, Rampage, Enlist.
    """
    sa = bot_action.get("sa")
    if not sa or sa == SA_ACTION_NONE_LABEL or sa in _BATTLE_MODIFYING_SAS:
        return None

    if (faction == _AEDUI_F and sa in (_SA_TRADE, _SA_SUBORN)
            and faction in state.get("non_player_factions", set())):
        # §8.6.3 evaluates Trade "at that moment" — i.e. when the Special
        # Ability resolves, AFTER the Command has spent/earned Resources —
        # and falls through Trade -> Suborn -> no SA. Re-derive the whole
        # choice now against the current board (the decision-time pick used
        # pre-Command Resources; e.g. a Rally can spend the Aedui below the
        # Suborn price between planning and resolution). Humans keep their
        # declared SA.
        from fs_bot.bots.aedui_bot import (_determine_trade_sa,
                                           SA_ACTION_NONE as _A_NONE,
                                           SA_ACTION_TRADE as _A_TRADE)
        battled = bot_action.get("command") == _CMD_BATTLE
        new_sa, new_regions, new_details = _determine_trade_sa(
            state, state["scenario"], battled=battled)
        if new_sa == _A_NONE:
            return {"executed": False, "sa": sa,
                    "declined_no_effect": True,
                    "reason": "no Trade or Suborn at SA time (§8.6.3 "
                              "'at that moment'; if none, no SA)"}
        if new_sa == _A_TRADE:
            result = _execute_trade(state, faction)
            result.setdefault("rederived_at_sa_time", True)
            return result
        rederived = dict(bot_action)
        rederived["sa"] = new_sa
        rederived["sa_regions"] = new_regions
        d = dict(bot_action.get("details") or {})
        d.update(new_details or {})
        rederived["details"] = d
        result = _execute_suborn(state, faction, rederived)
        result.setdefault("rederived_at_sa_time", True)
        return result

    if sa == _SA_TRADE:
        return _execute_trade(state, faction)
    if sa == _SA_SETTLE:
        return _execute_settle(state, faction, bot_action)
    if sa == _SA_DEVASTATE:
        return _execute_devastate(state, faction, bot_action)
    if (sa == _SA_INTIMIDATE
            and faction == _GERMANS_F
            and bot_action.get("command") in (_CMD_MARCH, _CMD_RAID)
            and faction in state.get("non_player_factions", set())):
        # A8.7.1: the Germans Intimidate "after Raid or March" — i.e. when the
        # SA resolves, AFTER the Command has moved/revealed pieces. The plan
        # picked at decision time reads the pre-Command board, so a March that
        # empties its origin of Hidden Warbands leaves a stale Intimidate the
        # executor refuses ("Only 0 Hidden Germanic Warbands in <R>"). Re-derive
        # the Intimidate-or-Settle choice against the current board, exactly as
        # the Aedui Trade/Suborn path re-derives "at that moment". Humans keep
        # their declared SA.
        from fs_bot.bots.german_bot import (
            _determine_intimidate_or_settle_after_march as _g_march_sa,
            _determine_intimidate_after_raid as _g_raid_sa,
            SA_ACTION_INTIMIDATE as _G_INTIM,
            SA_ACTION_SETTLE as _G_SETTLE)
        details = bot_action.get("details") or {}
        if bot_action.get("command") == _CMD_MARCH:
            new_sa, new_regions, new_details = _g_march_sa(
                state, details.get("march_plan") or {})
        else:
            new_sa, new_regions, new_details = _g_raid_sa(
                state, details.get("raid_plan") or [])
        rederived = dict(bot_action)
        d = dict(details)
        d.update(new_details or {})
        rederived["details"] = d
        rederived["sa_regions"] = new_regions  # _execute_settle reads this
        if new_sa == _G_INTIM:
            result = _execute_intimidate(state, faction, rederived)
            result.setdefault("rederived_at_sa_time", True)
            return result
        if new_sa == _G_SETTLE:
            result = _execute_settle(state, faction, rederived)
            result.setdefault("rederived_at_sa_time", True)
            return result
        return {"executed": False, "sa": _SA_INTIMIDATE,
                "declined_no_effect": True, "rederived_at_sa_time": True,
                "reason": "no Intimidate or Settle at SA time (A8.7.1 "
                          "evaluated after the Command; if none, no SA)"}
    if sa == _SA_INTIMIDATE:
        return _execute_intimidate(state, faction, bot_action)
    if sa == _SA_SUBORN:
        return _execute_suborn(state, faction, bot_action)
    if sa == _SA_BUILD:
        result = _execute_build(state, faction, bot_action)
        if faction == _ROMANS_F and not result.get("actions"):
            # R_BUILD "If no Build: R_SCOUT" — Scout after Command instead
            # (roman_bot_flowchart §8.8.1). Recompute against the current
            # (post-Command) board, exactly like the Build it replaces.
            scout = _execute_scout(state, faction, bot_action)
            if scout.get("executed"):
                scout = dict(scout)
                scout["fell_through_from"] = _SA_BUILD
                return scout
        return result
    if sa == _SA_RAMPAGE:
        return _execute_rampage(state, faction, bot_action)
    if sa == _SA_ENTREAT:
        return _execute_entreat(state, faction, bot_action)
    if sa == _SA_SCOUT:
        return _execute_scout(state, faction, bot_action)
    if sa == _SA_ENLIST:
        result = _execute_enlist(state, faction, bot_action)
        if (not result.get("executed")
                and bot_action.get("command") != _CMD_BATTLE
                and faction in state.get("non_player_factions", set())):
            # B_ENLIST after a Command: the decision-time sub-command can be
            # stale by the time the SA resolves (the Command itself moved
            # pieces/Control). Re-derive per §8.5.1 against the current
            # board; the flowchart's "If none: no Special Ability" applies
            # when nothing is found.
            from fs_bot.bots.belgae_bot import _check_enlist_after_command
            fresh = _check_enlist_after_command(state, state["scenario"])
            if fresh:
                rederived = dict(bot_action)
                rederived["sa_regions"] = fresh.get("regions", [])
                d = dict(bot_action.get("details") or {})
                d["enlist"] = fresh
                rederived["details"] = d
                retry = _execute_enlist(state, faction, rederived)
                if retry.get("executed"):
                    retry["rederived_at_sa_time"] = True
                    return retry
            result = dict(result)
            result["declined_no_effect"] = True
        return result

    return {"executed": False, "sa": sa,
            "reason": "SA not yet wired (plan translation deferred)"}


def _execute_trade(state, faction):
    """Aedui Trade (§4.4.2) — yields Resources; no targets."""
    try:
        res = _sa_trade(state)
    except _EXEC_ERRORS as exc:
        return {"executed": False, "sa": _SA_TRADE, "error": str(exc)}
    return {"executed": True, "sa": _SA_TRADE, "result": res}


def _execute_settle(state, faction, bot_action):
    """German Settle (A4.6.1) — place a Settlement in each sa_region."""
    regions = [r for r in (bot_action.get("sa_regions") or [])
               if isinstance(r, str)]
    placed, errors = [], []
    for region in regions:
        try:
            _sa_settle(state, region)
            placed.append(region)
        except _EXEC_ERRORS as exc:
            errors.append({"region": region, "error": str(exc)})
    return {"executed": len(placed) > 0, "sa": _SA_SETTLE,
            "regions": placed, "errors": errors}


def _execute_devastate(state, faction, bot_action):
    """Arverni/Aedui Devastate (§4.3.1) — Devastate each sa_region."""
    regions = [r for r in (bot_action.get("sa_regions") or [])
               if isinstance(r, str)]
    done, errors = [], []
    for region in regions:
        try:
            _sa_devastate(state, region)
            done.append(region)
        except _EXEC_ERRORS as exc:
            errors.append({"region": region, "error": str(exc)})
    return {"executed": len(done) > 0, "sa": _SA_DEVASTATE,
            "regions": done, "errors": errors}


def _execute_intimidate(state, faction, bot_action):
    """German Intimidate (A4.6.2).

    The bot's ``intimidate_plan`` is a flat list of per-removal entries
    ``{region, target_faction, target_piece, target_state, free}``. The
    mechanic intimidate(region, warbands_to_flip, target_faction,
    target_removals) flips 1-2 Hidden Warbands and removes that many pieces
    of ONE target faction. We group entries by (region, target_faction), cap
    each group at the rules' 2 flips, and translate to one call per group.
    """
    plan = _sa_detail(bot_action, "intimidate_plan") or []

    groups = {}
    order = []
    for entry in plan:
        region = entry.get("region")
        tgt = entry.get("target_faction")
        if region is None or tgt is None:
            continue
        key = (region, tgt)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(
            (entry.get("target_piece"), entry.get("target_state")))

    done, errors = [], []
    for (region, tgt) in order:
        removals = groups[(region, tgt)][:2]  # A4.6.2: flip 1-2 Warbands
        try:
            _sa_intimidate(state, region, len(removals), tgt, removals)
            done.append({"region": region, "target": tgt,
                         "count": len(removals)})
        except _EXEC_ERRORS as exc:
            errors.append({"region": region, "target": tgt,
                           "error": str(exc)})
    return {"executed": len(done) > 0, "sa": _SA_INTIMIDATE,
            "intimidations": done, "errors": errors}


def _execute_suborn(state, faction, bot_action):
    """Aedui Suborn (§4.4.2 / §8.6.3).

    The bot's ``suborn_plan`` is a list of ``{region, actions}`` where each
    action is one of place_ally / remove_ally / place_warband /
    remove_warband / remove_auxilia. We translate these to the suborn()
    operation schema ({action: place|remove, faction, piece_type, tribe,
    piece_state}) and call suborn() once per region. Removed pieces use
    piece_state=None (any state); placed Aedui pieces use the Aedui faction.
    """
    from fs_bot.rules_consts import AEDUI as _AEDUI, ALLY as _ALLY,         WARBAND as _WARBAND, AUXILIA as _AUXILIA
    plan = _sa_detail(bot_action, "suborn_plan") or []

    done, errors = [], []
    for sp in plan:
        region = sp.get("region")
        ops = []
        for a in sp.get("actions", []) or []:
            act = a.get("action")
            if act == "place_ally":
                ops.append({"action": "place", "faction": _AEDUI,
                            "piece_type": _ALLY, "tribe": a.get("tribe")})
            elif act == "place_warband":
                ops.append({"action": "place", "faction": _AEDUI,
                            "piece_type": _WARBAND})
            elif act == "remove_ally":
                ops.append({"action": "remove",
                            "faction": a.get("target_faction"),
                            "piece_type": _ALLY,
                            "tribe": a.get("tribe")})
            elif act == "remove_warband":
                ops.append({"action": "remove",
                            "faction": a.get("target_faction"),
                            "piece_type": _WARBAND, "piece_state": None})
            elif act == "remove_auxilia":
                ops.append({"action": "remove",
                            "faction": a.get("target_faction"),
                            "piece_type": _AUXILIA, "piece_state": None})
        if not ops:
            continue
        try:
            _sa_suborn(state, region, ops)
            done.append(region)
        except _EXEC_ERRORS as exc:
            errors.append({"region": region, "error": str(exc)})
    return {"executed": len(done) > 0, "sa": _SA_SUBORN,
            "regions": done, "errors": errors}


def _execute_build(state, faction, bot_action):
    """Roman Build (§4.2.1).

    The Roman bot's node_r_build computes a complete build_plan
    ({forts:[region], subdue:[{region,tribe}], allies:[{region,tribe}]}) but
    the accompanying Build SA is emitted without it. We recompute the plan
    against the current (post-Command) board via node_r_build and execute it:
    Forts, then Subdue (target_faction derived from the tribe's current
    Allied faction — a lookup, not a choice), then place Allies.
    """
    from fs_bot.bots.roman_bot import node_r_build
    try:
        plan = node_r_build(state)
    except Exception as exc:  # bot helper failure must not crash the turn
        return {"executed": False, "sa": _SA_BUILD,
                "reason": f"build plan unavailable: {exc!r}"}

    done, errors = [], []
    for region in plan.get("forts", []) or []:
        try:
            _sa_build_fort(state, region)
            done.append(("fort", region))
        except _EXEC_ERRORS as exc:
            errors.append({"action": "fort", "region": region,
                           "error": str(exc)})
    for entry in plan.get("subdue", []) or []:
        region, tribe = entry.get("region"), entry.get("tribe")
        target = state.get("tribes", {}).get(tribe, {}).get("allied_faction")
        if target is None:
            continue
        try:
            _sa_build_subdue(state, region, tribe, target)
            done.append(("subdue", region, tribe))
        except _EXEC_ERRORS as exc:
            errors.append({"action": "subdue", "region": region,
                           "tribe": tribe, "error": str(exc)})
    for entry in plan.get("allies", []) or []:
        region, tribe = entry.get("region"), entry.get("tribe")
        try:
            _sa_build_ally(state, region, tribe)
            done.append(("ally", region, tribe))
        except _EXEC_ERRORS as exc:
            errors.append({"action": "ally", "region": region,
                           "tribe": tribe, "error": str(exc)})
    result = {"executed": len(done) > 0, "sa": _SA_BUILD,
              "actions": done, "errors": errors}
    if not done and not errors:
        # R_BUILD found nothing to do — the flowchart's "If no Build" case,
        # a legal outcome (-> Scout / no SA), not a refused proposal.
        result["declined_no_effect"] = True
    return result


def _decide_defender_retreat(state, region, attacker, defender, is_ambush):
    """Route the defending faction's Retreat decision per §8.4.3.

    Non-player Retreat rules (non_player_guidelines_summary.txt, §8.4.3):
      Retreat to save the last piece, or — if Romans — to reduce Losses on
      Legions, or if (1) no Citadel or Fort, (2) they would inflict < 1/2 the
      Losses they would suffer, and (3) the Retreat itself removes no pieces.

    Returns (retreat_declaration, retreat_region):
      - (False, None) if the defender will not or cannot Retreat.
      - (True, dest)  if it Retreats into an adjacent Region it Controls,
        joining the most friendly pieces ("Leaders join most friendly
        pieces", §8.4.3).

    Scope note: destinations are limited to the defender's OWN Control — the
    always-available Retreat. Retreat into another Faction's Control requires
    that Faction's agreement (§1.5.2; only Aedui/Romans might, §8.6.6/§8.8.6);
    that agreement routing is a separate, documented extension.
    """
    from fs_bot.rules_consts import (
        ROMANS, GERMANS, ARVERNI, LEGION, AUXILIA, WARBAND, CITADEL, FORT,
        BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    )
    from fs_bot.battle.losses import calculate_losses

    if is_ambush:
        return (False, None)  # §4.3.3: Defender may not Retreat from Ambush
    scenario = state["scenario"]
    if defender == GERMANS and scenario in BASE_SCENARIOS:
        return (False, None)  # §3.2.4: Germans never Retreat (base)
    if defender == ARVERNI and scenario in ARIOVISTUS_SCENARIOS:
        return (False, None)  # A3.2.4: Arverni never Retreat

    # Legal Retreat destinations (adjacent Regions the defender Controls, or
    # ones whose controller agrees — §1.5.2).
    legal = _retreat_destinations(state, region, defender)

    # Agent hook: a human/LLM controlling the defender decides the Retreat.
    from fs_bot.engine.agent import consult_agent, RETREAT
    resp = consult_agent(state, defender, {
        "kind": RETREAT, "region": region, "attacker": attacker,
        "defender": defender, "is_ambush": is_ambush,
        "legal_regions": sorted(legal)})
    if resp is not None:
        if resp.get("retreat") and resp.get("region") in legal:
            return (True, resp["region"])
        return (False, None)

    # Default NP logic. Condition (3): a Retreat removes no pieces only if a
    # legal destination exists.
    if not legal:
        return (False, None)
    dest = max(sorted(legal), key=lambda r: count_pieces(state, r, defender))

    suffer = calculate_losses(state, region, attacker, defender)
    suffer_if_retreat = calculate_losses(
        state, region, attacker, defender, is_retreat=True)
    inflict = calculate_losses(
        state, region, defender, attacker, is_counterattack=True)

    mobile = (count_pieces(state, region, defender, LEGION)
              + count_pieces(state, region, defender, AUXILIA)
              + count_pieces(state, region, defender, WARBAND)
              + (1 if get_leader_in_region(state, region, defender)
                 is not None else 0))
    has_hard = (count_pieces(state, region, defender, CITADEL) > 0
                or count_pieces(state, region, defender, FORT) > 0)

    # (a) Retreat to save the last piece: full Losses would wipe the mobile
    #     group, but halved (Retreat) Losses leave a survivor.
    if mobile > 0 and suffer >= mobile and suffer_if_retreat < mobile:
        return (True, dest)
    # (b) Romans Retreat to reduce Losses on Legions.
    if (defender == ROMANS
            and count_pieces(state, region, defender, LEGION) > 0
            and suffer > 0):
        return (True, dest)
    # (c) No Citadel/Fort, would inflict < 1/2 the Losses suffered, and a
    #     valid (piece-preserving) destination exists.
    if (not has_hard) and (inflict * 2 < suffer):
        return (True, dest)

    return (False, None)


def _retreat_destinations(state, region, faction):
    """Adjacent Regions a faction may Retreat into (§8.4.3 + §1.5.2).

    Includes Regions the faction Controls, plus Regions Controlled by another
    Faction that agrees to the Retreat (np_agrees_to_retreat — Aedui/Romans
    per §8.6.6/§8.8.6). Returns a list (possibly empty).
    """
    from fs_bot.rules_consts import FACTIONS
    from fs_bot.map.map_data import get_adjacent
    from fs_bot.board.control import is_controlled_by

    dests = []
    for r in get_adjacent(region):
        if is_controlled_by(state, r, faction):
            dests.append(r)
            continue
        for c in FACTIONS:
            if c == faction:
                continue
            if is_controlled_by(state, r, c):
                # The controlling Faction agrees? Agent hook (§1.5.2) for a
                # human/LLM-controlled Faction; else the NP rule.
                from fs_bot.engine.agent import consult_agent, AGREEMENT
                _a = consult_agent(state, c, {
                    "kind": AGREEMENT, "request_type": "retreat_into_control",
                    "requesting_faction": faction,
                    "context": {"region": r, "from_region": region}})
                agrees = (bool(_a) if _a is not None
                          else np_agrees_to_retreat(c, faction, state))
                if agrees:
                    dests.append(r)
                break
    return dests


def _best_retreat_destination(state, region, faction):
    """Pick the Retreat destination joining the most friendly pieces
    (§8.4.3), with a deterministic tie-break. None if no legal destination.
    """
    dests = _retreat_destinations(state, region, faction)
    if not dests:
        return None
    return max(sorted(dests), key=lambda r: count_pieces(state, r, faction))


def _execute_rampage(state, faction, bot_action):
    """Belgic Rampage (§4.5.2) — routes the TARGET's remove-vs-Retreat choice.

    For each flipped Hidden Belgic Warband the target must remove or Retreat
    one piece. The bot's rampage plan gives ``{region, target}``; we flip up
    to 2 Warbands (capped by Hidden Belgic Warbands present and by how many
    target pieces are available). The target loses its lowest-value mobile
    pieces first (Warbands, then Auxilia, then Legions — §8.4.1), and
    Retreats them to save them when a legal destination exists (§8.4.3),
    otherwise removes them. In Ariovistus a Rampaged Arverni target is removed
    rather than Retreating (A4.5).
    """
    from fs_bot.rules_consts import (
        BELGAE, ARVERNI, WARBAND, AUXILIA, LEGION, HIDDEN, REVEALED,
        ARIOVISTUS_SCENARIOS,
    )
    # The Belgae bot puts the Rampage plan in sa_regions as a list of dicts
    # {region, target, forces_removal, adds_control}.
    plan = [e for e in (bot_action.get("sa_regions") or [])
            if isinstance(e, dict)]
    if not plan:
        return {"executed": False, "sa": _SA_RAMPAGE,
                "reason": "no rampage plan with targets"}

    scenario = state["scenario"]
    done, errors = [], []
    for entry in plan:
        region = entry.get("region")
        target = entry.get("target")
        if region is None or target is None:
            continue
        hidden_belgic = _count_state(state, region, BELGAE, WARBAND, HIDDEN)
        if hidden_belgic <= 0:
            continue

        # Build the ordered pool of target pieces to lose (lowest value 1st).
        pool = []
        for pt in (WARBAND, AUXILIA):
            for ps in (REVEALED, HIDDEN):
                pool += [(pt, ps)] * _count_state(state, region, target, pt, ps)
        pool += [(LEGION, None)] * count_pieces(state, region, target, LEGION)
        if not pool:
            continue

        n = min(2, hidden_belgic, len(pool))
        dest = _best_retreat_destination(state, region, target)
        force_remove = (scenario in ARIOVISTUS_SCENARIOS and target == ARVERNI)

        actions = []
        for i in range(n):
            pt, ps = pool[i]
            if dest is not None and not force_remove:
                actions.append({"action": "retreat", "piece_type": pt,
                                "piece_state": ps, "retreat_region": dest})
            else:
                actions.append({"action": "remove", "piece_type": pt,
                                "piece_state": ps})
        try:
            _sa_rampage(state, region, target, n, actions)
            done.append({"region": region, "target": target, "count": n})
        except _EXEC_ERRORS as exc:
            errors.append({"region": region, "target": target,
                           "error": str(exc)})
    return {"executed": len(done) > 0, "sa": _SA_RAMPAGE,
            "rampages": done, "errors": errors}


def _np_harassers(state, region, target_faction, group):
    """Factions that opt to Harass per §8.4.2 (+ §3.4.5 / A3.2.2).

    §8.4.2: Belgae and Arverni Harass only Roman March and Seize; Aedui and
    Romans Harass only Vercingetorix March. §3.4.5: Germans always Harass
    (base). A3.2.2: Arverni always Harass (Ariovistus). A Faction can only
    Harass where it has at least 3 Hidden Warbands (§3.2.2).

    Args:
        target_faction: The faction being Harassed (the marcher/seizer).
        group: For a March, the moving group dict (to detect Vercingetorix);
            None for Seize.

    Returns:
        List of (faction, hidden_warbands), in FACTIONS order.
    """
    from fs_bot.rules_consts import (
        FACTIONS, ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS, VERCINGETORIX,
        LEADER, WARBAND, HIDDEN, BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    )
    scenario = state["scenario"]
    has_verc = bool(group) and group.get(LEADER) == VERCINGETORIX

    harassers = []
    for f in FACTIONS:
        if f == target_faction:
            continue
        hwb = _count_state(state, region, f, WARBAND, HIDDEN)
        if hwb < _HWB_PER_LOSS:
            continue
        opt = False
        if f == GERMANS and scenario in BASE_SCENARIOS:
            opt = True  # §3.4.5
        elif f == ARVERNI and scenario in ARIOVISTUS_SCENARIOS:
            opt = True  # A3.2.2
        elif f in (BELGAE, ARVERNI) and target_faction == ROMANS:
            opt = True  # §8.4.2: harass Roman March/Seize
        elif f in (AEDUI, ROMANS) and has_verc:
            opt = True  # §8.4.2: harass Vercingetorix March
        if opt:
            harassers.append((f, hwb))
    return harassers


def _resolve_seize_harassment(state, region):
    """Harassment against the seizing Romans in a Region (§3.2.3 / §8.4.2).

    Each opting Faction inflicts one Loss per 3 of its Hidden Warbands. The
    Romans take each Loss on their least valuable piece first — Auxilia, then
    Roman Ally — or, with only hard targets (Legion/Leader/Fort), roll a die.
    """
    from fs_bot.rules_consts import ROMANS, AUXILIA, ALLY, LEGION, FORT
    losses_applied = []
    for faction, hwb in _np_harassers(state, region, ROMANS, None):
        for _ in range(hwb // _HWB_PER_LOSS):
            if count_pieces(state, region, ROMANS, AUXILIA) > 0:
                choice = "auxilia"
            elif count_pieces(state, region, ROMANS, ALLY) > 0:
                choice = "ally"
            elif (count_pieces(state, region, ROMANS, LEGION) > 0
                  or get_leader_in_region(state, region, ROMANS) is not None
                  or count_pieces(state, region, ROMANS, FORT) > 0):
                choice = "roll"
            else:
                break  # nothing left for this harasser to remove
            try:
                res = _seize_harass_loss(state, region, choice)
                losses_applied.append({"by": faction, "choice": choice,
                                       "removed": res.get("removed")})
            except _EXEC_ERRORS:
                break
    return losses_applied


def _execute_entreat(state, faction, bot_action):
    """Arverni Entreat (§4.3.1). The bot's entreat action plan is carried in
    sa_regions as dicts. Each is one of replace_ally / remove_ally (an Allied
    Tribe) or replace_piece / remove_piece (a Warband/Auxilia). The mechanic
    replaces with an Arverni counterpart, or removes the target when the
    Arverni piece is unavailable.
    """
    plan = [e for e in (bot_action.get("sa_regions") or [])
            if isinstance(e, dict)]
    if not plan:
        # The Arverni Rally/March SA path passes only Region names and drops
        # the Entreat action plan; recompute it against the current board
        # (the Battle path passes the full plan and is used directly above).
        from fs_bot.bots.arverni_bot import _check_entreat
        plan = _check_entreat(state, state["scenario"]) or []
    done, errors = [], []
    for a in plan:
        act = a.get("action")
        region = a.get("region")
        tgt = a.get("target_faction")
        try:
            if act in ("replace_ally", "remove_ally"):
                _sa_entreat_ally(state, region, tgt, a.get("tribe"))
            elif act in ("replace_piece", "remove_piece"):
                _sa_entreat_piece(state, region, tgt, a.get("target_type"),
                                  a.get("target_state"))
            else:
                continue
            done.append({"region": region, "action": act})
        except _EXEC_ERRORS as exc:
            errors.append({"region": region, "action": act,
                           "error": str(exc)})
    return {"executed": len(done) > 0, "sa": _SA_ENTREAT,
            "actions": done, "errors": errors}


def _execute_scout(state, faction, bot_action):
    """Roman Scout (§4.2.2). The bot's node_r_scout computes a complete plan
    (auxilia_moves + scout_targets) but the SA is emitted without it; we
    recompute it against the current board and execute: move Auxilia, then
    Reveal — each flipped Hidden Auxilia Reveals up to 2 enemy Warbands.
    """
    from fs_bot.bots.roman_bot import node_r_scout
    from fs_bot.rules_consts import ROMANS, AUXILIA, HIDDEN
    try:
        plan = node_r_scout(state)
    except Exception as exc:
        return {"executed": False, "sa": _SA_SCOUT,
                "reason": f"scout plan unavailable: {exc!r}"}

    done, errors = [], []
    # Only execute Auxilia moves that carry a concrete from/to (scout_move
    # schema); the bot's escort "intentions" ({to,needed,reason}) are skipped.
    moves = [m for m in (plan.get("auxilia_moves") or [])
             if isinstance(m, dict) and m.get("from_region") and m.get("to_region")]
    if moves:
        try:
            _sa_scout_move(state, moves)
            done.append({"moves": len(moves)})
        except _EXEC_ERRORS as exc:
            errors.append({"action": "move", "error": str(exc)})

    for tgt in plan.get("scout_targets", []) or []:
        region = tgt.get("region")
        enemy = tgt.get("enemy")
        want = tgt.get("hidden", 0)  # Hidden enemy Warbands to Reveal
        if want <= 0:
            continue
        hidden_aux = _count_state(state, region, ROMANS, AUXILIA, HIDDEN)
        if hidden_aux <= 0:
            continue
        # Each flipped Hidden Auxilia Reveals up to 2 Warbands (§4.2.2).
        aux_count = min(hidden_aux, (want + 1) // 2)
        reveal = min(want, 2 * aux_count)
        targets = [{"faction": enemy, "count": reveal}]
        try:
            _sa_scout_reveal(state, region, aux_count, targets)
            done.append({"region": region, "revealed": reveal})
        except _EXEC_ERRORS as exc:
            errors.append({"region": region, "error": str(exc)})

    result = {"executed": len(done) > 0, "sa": _SA_SCOUT,
              "actions": done, "errors": errors}
    if not done and not errors:
        # R_SCOUT "If none ... no Special Ability" — legal outcome.
        result["declined_no_effect"] = True
    return result


def _execute_enlist(state, faction, bot_action):
    """Belgic Enlist (§4.5.1) — execute a free Germanic sub-Command.

    The bot's enlist_details (details['enlist']) names one of five sub-actions
    in a Region within reach of the Belgic Leader. We orchestrate each via the
    German faction's own mechanics (free where the mechanic supports it):
      - german_battle: a free German Battle (with Ambush in base game; A4.5.1
        adds no Ambush in Ariovistus), routing the defender's Retreat.
      - german_march: flip and March the German mobile group origin -> dest.
      - german_march_hide: flip the Region's Revealed German Warbands to Hidden.
      - german_rally: place a German Ally or Warbands.
      - german_raid: a free German Raid (steal from the named player, else gain).
    """
    from fs_bot.rules_consts import GERMANS, BASE_SCENARIOS
    ed = _sa_detail(bot_action, "enlist")
    if not isinstance(ed, dict):
        return {"executed": False, "sa": _SA_ENLIST,
                "reason": "no enlist sub-command details"}
    scenario = state["scenario"]
    t = ed.get("type")
    try:
        if t == "german_battle":
            region, target = ed.get("region"), ed.get("target")
            decl, rr = _decide_defender_retreat(
                state, region, GERMANS, target, scenario in BASE_SCENARIOS)
            resolve_battle(state, region, GERMANS, target,
                           is_ambush=(scenario in BASE_SCENARIOS),
                           retreat_declaration=decl, retreat_region=rr)
        elif t == "german_march":
            origin, dest = ed.get("origin"), ed.get("destination")
            if not _group_has_pieces(_mobile_march_group(state, GERMANS, origin)):
                return {"executed": False, "sa": _SA_ENLIST,
                        "type": t, "reason": "no German pieces to March"}
            playable = set(get_playable_regions(
                scenario, state.get("capabilities")))
            path = _bfs_march_path(origin, dest, playable)
            if not path:
                return {"executed": False, "sa": _SA_ENLIST, "type": t,
                        "reason": "no path to enlist March destination"}
            _march_with_harassment(state, GERMANS, origin, path)
        elif t == "german_march_hide":
            _flip_origin_pieces(state, ed.get("region"), GERMANS)
        elif t == "german_rally":
            region = ed.get("region")
            if ed.get("place") == "ally":
                rally_in_region(state, region, GERMANS, "place_ally",
                                tribe=ed.get("tribe"), free=True)
            else:
                rally_in_region(state, region, GERMANS, "place_warbands",
                                free=True)
        elif t == "german_raid":
            region, target = ed.get("region"), ed.get("target")
            actions = ([{"type": "steal", "target": target}] if target
                       else [{"type": "gain"}])
            raid_in_region(state, region, GERMANS, actions, free=True)
        else:
            return {"executed": False, "sa": _SA_ENLIST,
                    "type": t, "reason": "unknown enlist sub-type"}
    except _EXEC_ERRORS as exc:
        return {"executed": False, "sa": _SA_ENLIST, "type": t,
                "error": str(exc)}
    return {"executed": True, "sa": _SA_ENLIST, "type": t,
            "region": ed.get("region") or ed.get("origin")}


def _derive_event_params(state, faction, card_id, shaded):
    """Derive event_params for the acting NP faction where the choice is
    unambiguous under the NP rules (§8.2.3: choose benefits for self;
    §8.3.1: place/remove where most Legions, then Citadels, Allies).

    Returns a params dict (merged over any existing event_params), or None.

    SCOPE: This is the parameter-plumbing hook plus the clearly-derivable
    cases. Most parameterized cards encode a card-specific choice (which
    Region, which pieces, which Faction) whose faithful NP derivation is a
    per-card workstream; those remain reported as 'needs parameters' rather
    than guessed.
    """
    fn = _EVENT_PARAM_DERIVERS.get(card_id)
    if fn is None:
        return None
    return fn(state, faction, shaded)


def _derive_senate_direction(state, faction, shaded):
    """Cicero / Senate-shift cards: each Faction shifts the Senate toward its
    own benefit (§8.2.3). Romans favour Adulation (more Legions) -> DOWN;
    Gallic/Germanic Factions favour Uproar (fewer Roman Legions) -> UP.
    """
    from fs_bot.rules_consts import ROMANS, SENATE_UP, SENATE_DOWN
    return {"senate_direction": SENATE_DOWN if faction == ROMANS
            else SENATE_UP}


def _derive_card_28(state, faction, shaded):
    """Card 28 (Oppida): place the acting Gallic Faction's Available Allies at
    Subdued City Tribes not under Roman Control, and upgrade its City Allies to
    Citadels (§8.2.3 — the NP benefits itself; §8.3.1 — at Cities). Only a
    Gallic Faction benefits."""
    from fs_bot.rules_consts import (GALLIC_FACTIONS, CITY_TO_TRIBE,
                                     TRIBE_TO_REGION, ROMANS, ALLY, CITADEL)
    from fs_bot.board.control import is_controlled_by
    from fs_bot.board.pieces import get_available, count_pieces
    if faction not in GALLIC_FACTIONS:
        return None
    placements, upgrades = [], []
    avail_ally = get_available(state, faction, ALLY)
    for city, tribe in CITY_TO_TRIBE.items():
        region = TRIBE_TO_REGION.get(tribe)
        ti = state.get("tribes", {}).get(tribe)
        if not (region and ti):
            continue
        if (ti.get("allied_faction") is None
                and not is_controlled_by(state, region, ROMANS)
                and len(placements) < avail_ally):
            placements.append({"tribe": tribe, "faction": faction})
    avail_cit = get_available(state, faction, CITADEL)
    for city, tribe in CITY_TO_TRIBE.items():
        region = TRIBE_TO_REGION.get(tribe)
        ti = state.get("tribes", {}).get(tribe)
        if (region and ti and ti.get("allied_faction") == faction
                and count_pieces(state, region, faction, ALLY) > 0
                and len(upgrades) < avail_cit):
            upgrades.append(city)
    if not placements and not upgrades:
        return None
    return {"ally_placements": placements, "citadel_upgrades": upgrades}


def _derive_card_71(state, faction, shaded):
    """Card 71 (Colony): place the Colony + the acting Faction's Ally in a
    Region it Controls (or No Control), with no Colony yet. §8.3.1 — choose a
    Region the Faction Controls (keeps the +1 Control Value)."""
    from fs_bot.rules_consts import MARKER_COLONY, ALLY, NO_CONTROL
    from fs_bot.board.control import is_controlled_by, calculate_control
    from fs_bot.board.pieces import get_available
    if get_available(state, faction, ALLY) <= 0:
        return None
    playable = get_playable_regions(state["scenario"], state.get("capabilities"))
    controlled, nocontrol = [], []
    for r in sorted(playable):
        m = state.get("markers", {}).get(r) or {}
        if MARKER_COLONY in m:
            continue
        if is_controlled_by(state, r, faction):
            controlled.append(r)
        elif calculate_control(state, r) == NO_CONTROL:
            nocontrol.append(r)
    cands = sorted(controlled) or sorted(nocontrol)
    if not cands:
        return None
    region = cands[0]
    return {"region": region, "colony_tribe_name": f"Colony_{region}"}


def _derive_card_41(state, faction, shaded):
    """Card 41 (Avaricum): if the Faction holds Avaricum, place up to 2 Allies
    at Subdued Tribes within 1 of Bituriges and upgrade one City Ally to a
    Citadel (§8.2.3/§8.3.1 — benefit self near Avaricum)."""
    from fs_bot.rules_consts import (CITY_AVARICUM, CITY_TO_TRIBE,
                                     BITURIGES, ALLY, CITADEL)
    from fs_bot.map.map_data import (get_adjacent, get_tribes_in_region,
                                     is_city_tribe)
    from fs_bot.board.pieces import get_available, count_pieces
    av_tribe = CITY_TO_TRIBE.get(CITY_AVARICUM)
    ti = state.get("tribes", {}).get(av_tribe)
    if not ti or ti.get("allied_faction") != faction:
        return None
    scenario = state["scenario"]
    target_regions = [BITURIGES] + list(get_adjacent(BITURIGES, scenario))
    placements = []
    avail = get_available(state, faction, ALLY)
    for r in target_regions:
        for tribe in get_tribes_in_region(r, scenario):
            t_info = state.get("tribes", {}).get(tribe)
            if (t_info and t_info.get("allied_faction") is None
                    and len(placements) < min(2, avail)):
                placements.append({"tribe": tribe})
    citadel_tribe = None
    if get_available(state, faction, CITADEL) > 0:
        for r in target_regions:
            for tribe in get_tribes_in_region(r, scenario):
                t_info = state.get("tribes", {}).get(tribe)
                if (t_info and t_info.get("allied_faction") == faction
                        and is_city_tribe(tribe)
                        and count_pieces(state, r, faction, ALLY) > 0):
                    citadel_tribe = tribe
                    break
            if citadel_tribe:
                break
    if not placements and not citadel_tribe:
        return None
    out = {"ally_placements": [{"tribe": t["tribe"]} for t in placements]}
    if citadel_tribe:
        out["citadel_upgrade_tribe"] = citadel_tribe
    return out


def _derive_card_42(state, faction, shaded):
    """Card 42 (Roman Wine), unshaded: remove up to 4 non-own Allied Tribes
    (not Citadels) in Roman-Controlled Regions (§8.2.3 — remove enemies', not
    own).

    Shaded (Romanizing tribes): remove 1-3 Roman or Aedui Allies (not Citadels)
    in Roman-Aedui Supply-Line Regions (Card Reference 42 — Supply Lines per
    §3.2.1 computed "as if Romans and Aedui both agreed", i.e. chain Regions are
    No Control / Roman / Aedui). The NP removes enemies' Allies (§8.2.3) — never
    its own."""
    from fs_bot.rules_consts import TRIBE_TO_REGION, ROMANS, ALLY
    from fs_bot.board.control import is_controlled_by
    from fs_bot.board.pieces import count_pieces
    if shaded:
        from fs_bot.rules_consts import AEDUI
        from fs_bot.commands.rally import has_supply_line
        agreements = {ROMANS: True, AEDUI: True}
        removals = []
        for tribe in sorted(state.get("tribes", {})):
            if len(removals) >= 3:
                break
            ti = state["tribes"][tribe]
            af = ti.get("allied_faction")
            if af not in (ROMANS, AEDUI) or af == faction:
                continue  # only enemies' Roman/Aedui Allies
            region = TRIBE_TO_REGION.get(tribe)
            if not region or count_pieces(state, region, af, ALLY) <= 0:
                continue  # an Ally piece (not a Citadel city)
            if not has_supply_line(state, region, faction=ROMANS,
                                   agreements=agreements):
                continue
            removals.append({"tribe": tribe, "faction": af})
        return {"removals": removals} if removals else None
    removals = []
    for tribe, ti in state.get("tribes", {}).items():
        af = ti.get("allied_faction")
        region = TRIBE_TO_REGION.get(tribe)
        if (af and af != faction and region
                and is_controlled_by(state, region, ROMANS)
                and count_pieces(state, region, af, ALLY) > 0):
            removals.append({"tribe": tribe})
            if len(removals) >= 4:
                break
    return {"removals": removals} if removals else None


def _derive_card_23(state, faction, shaded):
    """Card 23 (Sacking), unshaded: Romans Raze a City under Roman Control
    (+8 Resources, permanent Disperse). Choose a Roman-Controlled City.

    Shaded (Costly siege): if a Legion is where the acting Faction has a
    Citadel, remove that Legion (Romans Ineligible through next card). Choose
    the Region with the acting Faction's Citadel holding the most Roman Legions
    (§8.3.1 — where most Legions). Non-Roman only ("your Citadel")."""
    from fs_bot.rules_consts import (CITY_TO_TRIBE, TRIBE_TO_REGION,
                                     MARKER_RAZED, ROMANS)
    from fs_bot.board.control import is_controlled_by
    if shaded:
        from fs_bot.rules_consts import LEGION, CITADEL
        from fs_bot.board.pieces import count_pieces
        if faction == ROMANS:
            return None
        best = None
        for region in get_playable_regions(state["scenario"],
                                            state.get("capabilities")):
            if count_pieces(state, region, faction, CITADEL) <= 0:
                continue
            legs = count_pieces(state, region, ROMANS, LEGION)
            if legs > 0 and (best is None or legs > best[1]):
                best = (region, legs)
        return {"target_region": best[0]} if best else None
    if faction != ROMANS:
        return None
    for city, tribe in CITY_TO_TRIBE.items():
        region = TRIBE_TO_REGION.get(tribe)
        if region and is_controlled_by(state, region, ROMANS):
            m = state.get("markers", {}).get(region) or {}
            if MARKER_RAZED in m:
                continue
            return {"target_city": city}
    return None


def _derive_card_68(state, faction, shaded):
    """Card 68 (Remi Influence), unshaded: if Remi are a Roman Ally or Subdued,
    Romans replace up to 2 non-Roman Allies within 1 Region of Remi (Atrebates)
    with Roman Allies (§8.2.3 — convert enemies' to own).

    Shaded (Mediation): a Gallic Faction with Remi as its Ally may remove
    anything at Alesia or Cenabum and place a Citadel + 4 Warbands there
    (Card Reference 68). Acting Faction must be the Gallic Faction allied with
    Remi; choose the City whose removal hurts an enemy most (else Alesia)."""
    from fs_bot.rules_consts import (TRIBE_REMI, TRIBE_TO_REGION, ATREBATES,
                                     ROMANS)
    from fs_bot.map.map_data import get_adjacent, get_tribes_in_region
    if shaded:
        from fs_bot.rules_consts import (GALLIC_FACTIONS, FACTIONS, CITADEL,
                                         CITY_ALESIA, CITY_CENABUM, CITY_TO_TRIBE)
        from fs_bot.board.pieces import count_pieces
        if faction not in GALLIC_FACTIONS:
            return None
        remi = state.get("tribes", {}).get(TRIBE_REMI)
        if not remi or remi.get("allied_faction") != faction:
            return None
        best = None  # (city, enemy_value)
        for city in (CITY_ALESIA, CITY_CENABUM):
            tribe = CITY_TO_TRIBE.get(city)
            region = TRIBE_TO_REGION.get(tribe)
            if not region:
                continue
            ti = state.get("tribes", {}).get(tribe) or {}
            enemy = 0
            af = ti.get("allied_faction")
            if af and af != faction:
                enemy += 1
            for f2 in FACTIONS:
                if f2 != faction:
                    enemy += count_pieces(state, region, f2, CITADEL)
            if best is None or enemy > best[1]:
                best = (city, enemy)
        return {"target_city": best[0]} if best else None
    if faction != ROMANS:
        return None
    _R = ROMANS
    ti = state.get("tribes", {}).get(TRIBE_REMI)
    if not ti:
        return None
    # "Dispersed Remi would not qualify for unshaded" (Card 68 Tips). Disperse
    # is stored in tribe["status"] (= Dispersed / Dispersed-Gathering).
    is_roman = ti.get("allied_faction") == _R
    is_subdued = (ti.get("allied_faction") is None
                  and ti.get("status") is None)
    if not (is_roman or is_subdued):
        return None
    scenario = state["scenario"]
    valid = [ATREBATES] + list(get_adjacent(ATREBATES, scenario))
    repl = []
    for region in valid:
        for tribe in get_tribes_in_region(region, scenario):
            t = state.get("tribes", {}).get(tribe)
            if (t and t.get("allied_faction")
                    and t.get("allied_faction") != _R
                    and len(repl) < 2):
                repl.append({"tribe": tribe})
    return {"replacements": repl} if repl else None


def _derive_card_58(state, faction, shaded):
    """Card 58 (Aduatuca), unshaded: remove up to 9 Belgic/Germanic Warbands
    from a Region with a (Roman) Fort. Choose the Fort Region with the most
    such Warbands. Only a Faction opposed to Belgae/Germans benefits. Shaded
    (free German March/Battle) deferred."""
    from fs_bot.rules_consts import (BELGAE, GERMANS, ROMANS, WARBAND, FORT)
    from fs_bot.board.pieces import count_pieces
    if shaded or faction in (BELGAE, GERMANS):
        return None
    playable = get_playable_regions(state["scenario"], state.get("capabilities"))
    best = None
    for region in sorted(playable):
        if count_pieces(state, region, ROMANS, FORT) <= 0:
            continue
        bg = (count_pieces(state, region, BELGAE, WARBAND)
              + count_pieces(state, region, GERMANS, WARBAND))
        if bg > 0 and (best is None or bg > best[1]):
            best = (region, bg)
    if best is None:
        return None
    region = best[0]
    removals = []
    for f in (BELGAE, GERMANS):
        n = count_pieces(state, region, f, WARBAND)
        if n > 0:
            removals.append({"faction": f, "count": min(n, 9)})
    return {"region": region, "removals": removals}


def _derive_card_22(state, faction, shaded):
    """Card 22 (Hostages), unshaded: among Regions the acting Faction Controls,
    replace up to 4 enemy Warbands/Auxilia with its own (§8.2.3 — convert
    enemies' to own).

    Shaded (Casus belli): place a Gallic Ally and any 1 Warband at each of 1 or
    2 Subdued Tribes where Roman pieces (Card Reference 22). The NP benefits
    itself (§8.2.3) — place its own Ally + own Warband. A Gallic Faction only;
    a Roman/German acting Faction gains nothing from placing a Gallic Ally, so
    no derivation (graceful no-op)."""
    from fs_bot.rules_consts import FACTIONS, WARBAND, AUXILIA
    from fs_bot.board.control import is_controlled_by
    from fs_bot.board.pieces import count_pieces
    if shaded:
        from fs_bot.rules_consts import (GALLIC_FACTIONS, ALLY, ROMANS,
                                         TRIBE_TO_REGION)
        from fs_bot.board.pieces import get_available
        if (faction not in GALLIC_FACTIONS
                or get_available(state, faction, ALLY) <= 0):
            return None
        target_tribes = []
        for tribe in sorted(state.get("tribes", {})):
            if len(target_tribes) >= 2:
                break
            ti = state["tribes"][tribe]
            # Subdued Tribe = neither Allied nor Dispersed (Key Terms Index).
            # Dispersed / Dispersed-Gathering / Razed live in tribe["status"].
            if ti.get("allied_faction") is not None or ti.get("status") is not None:
                continue
            region = TRIBE_TO_REGION.get(tribe)
            if not region or count_pieces(state, region, ROMANS) <= 0:
                continue  # "where Roman pieces"
            target_tribes.append({"tribe": tribe, "region": region,
                                  "faction": faction,
                                  "warband_faction": faction})
        return {"target_tribes": target_tribes} if target_tribes else None
    replacements = []
    playable = get_playable_regions(state["scenario"], state.get("capabilities"))
    for region in sorted(playable):
        if not is_controlled_by(state, region, faction):
            continue
        for tf in FACTIONS:
            if tf == faction:
                continue
            for pt in (WARBAND, AUXILIA):
                for _ in range(count_pieces(state, region, tf, pt)):
                    if len(replacements) >= 4:
                        break
                    replacements.append({"region": region,
                                         "target_faction": tf,
                                         "piece_type": pt})
    return {"replacements": replacements} if replacements else None


def _derive_card_A18(state, faction, shaded):
    """Card A18 (Rhenus Bridge), unshaded: remove all Germans from a Germania
    Region without Ariovistus. Choose the such Region with the most German
    pieces. Any non-German Faction benefits. Shaded deferred."""
    from fs_bot.rules_consts import (GERMANIA_REGIONS, GERMANS, ARIOVISTUS_LEADER,
                                     WARBAND, ALLY, SETTLEMENT, ROMANS)
    from fs_bot.board.pieces import count_pieces, get_leader_in_region
    from fs_bot.board.control import is_controlled_by
    from fs_bot.map.map_data import get_adjacent
    if shaded or faction == GERMANS:
        return None
    scen = state["scenario"]
    best = None
    for region in GERMANIA_REGIONS:
        if get_leader_in_region(state, region, GERMANS) == ARIOVISTUS_LEADER:
            continue
        # "...under or adjacent to Roman Control" (A18) — only such Regions.
        if not (is_controlled_by(state, region, ROMANS)
                or any(is_controlled_by(state, a, ROMANS)
                       for a in get_adjacent(region, scen))):
            continue
        g = (count_pieces(state, region, GERMANS, WARBAND)
             + count_pieces(state, region, GERMANS, ALLY)
             + count_pieces(state, region, GERMANS, SETTLEMENT))
        if g > 0 and (best is None or g > best[1]):
            best = (region, g)
    return {"region": best[0]} if best else None


def _derive_card_A45(state, faction, shaded):
    """Card A45 (Savage Dictates), unshaded: place up to 3 of the acting
    non-German Faction's Allies at Subdued Celtica Tribes. Shaded deferred."""
    from fs_bot.rules_consts import (GERMANS, CELTICA_REGIONS, ALLY,
                                     MARKER_INTIMIDATED)
    from fs_bot.map.map_data import get_tribes_in_region, get_adjacent
    from fs_bot.board.pieces import get_available
    if shaded or faction == GERMANS:
        return None
    avail = get_available(state, faction, ALLY)
    if avail <= 0:
        return None
    scen = state["scenario"]
    markers = state.get("markers", {})
    intimidated = {r for r, m in markers.items()
                   if isinstance(m, dict) and MARKER_INTIMIDATED in m}
    if not intimidated:
        return None  # "within 1 Region of Intimidated markers" — none exist

    def _within1(region):
        return region in intimidated or any(
            a in intimidated for a in get_adjacent(region, scen))

    placements = []
    for region in CELTICA_REGIONS:
        if not _within1(region):
            continue
        for tribe in get_tribes_in_region(region, scen):
            ti = state.get("tribes", {}).get(tribe)
            if (ti and ti.get("allied_faction") is None
                    and ti.get("status") is None
                    and len(placements) < min(3, avail)):
                placements.append({"tribe": tribe, "faction": faction})
    return {"placements": placements} if placements else None


def _derive_card_A37(state, faction, shaded):
    """Card A37 (All Gaul Gathers), shaded: remove up to 3 Aedui/Roman Allies
    in Celtica (§8.2.3 — enemies' Allies). Unshaded (place + Leader move) is
    deferred. Only a Faction other than Aedui/Romans benefits from shaded."""
    from fs_bot.rules_consts import CELTICA_REGIONS, AEDUI, ROMANS, ALLY
    from fs_bot.map.map_data import get_tribes_in_region
    from fs_bot.board.pieces import count_pieces, get_available
    from fs_bot.board.control import is_controlled_by
    from fs_bot.map.map_data import get_adjacent
    if not shaded:
        # Unshaded: if Aedui or Roman, place an Ally at a Subdued Celtica Tribe
        # within 1 of German Control. (The Leader/Warband move is executed by
        # _resolve_card_A37_move.)
        if faction not in (AEDUI, ROMANS) or get_available(state, faction, ALLY) <= 0:
            return None
        from fs_bot.rules_consts import GERMANS
        scen = state["scenario"]
        for region in CELTICA_REGIONS:
            near_gc = is_controlled_by(state, region, GERMANS) or any(
                is_controlled_by(state, a, GERMANS)
                for a in get_adjacent(region, scen))
            if not near_gc:
                continue
            for tribe in get_tribes_in_region(region, scen):
                ti = state.get("tribes", {}).get(tribe)
                if ti and ti.get("allied_faction") is None:
                    return {"ally_placements": [{"tribe": tribe,
                                                 "faction": faction}]}
        return None
    if faction in (AEDUI, ROMANS):
        return None
    removals = []
    for region in CELTICA_REGIONS:
        for tribe in get_tribes_in_region(region, state["scenario"]):
            ti = state.get("tribes", {}).get(tribe)
            af = ti.get("allied_faction") if ti else None
            if (af in (AEDUI, ROMANS)
                    and count_pieces(state, region, af, ALLY) > 0
                    and len(removals) < 3):
                removals.append({"tribe": tribe, "faction": af})
    return {"removals": removals} if removals else None


def _derive_card_A64(state, faction, shaded):
    """Card A64 (Abatis): place the Faction's Abatis marker in a Region where
    it has a Warband — prefer a Region also holding an enemy (frontier
    defense). No existing Abatis there."""
    from fs_bot.rules_consts import WARBAND, FACTIONS, MARKER_ABATIS
    from fs_bot.board.pieces import count_pieces
    playable = get_playable_regions(state["scenario"], state.get("capabilities"))
    frontier, plain = None, None
    for region in sorted(playable):
        if count_pieces(state, region, faction, WARBAND) <= 0:
            continue
        m = state.get("markers", {}).get(region) or {}
        if MARKER_ABATIS in m:
            continue
        enemy = any(count_pieces(state, region, of) > 0
                    for of in FACTIONS if of != faction)
        if enemy and frontier is None:
            frontier = region
        elif plain is None:
            plain = region
    region = frontier or plain
    return {"region": region} if region else None


def _derive_card_A66(state, faction, shaded):
    """Card A66 (Winter Uprising!): place the Uprising marker in a Region the
    acting Faction has pieces in (where it will benefit from the later
    placement+Command)."""
    from fs_bot.board.pieces import count_pieces
    playable = get_playable_regions(state["scenario"], state.get("capabilities"))
    cands = [r for r in sorted(playable) if count_pieces(state, r, faction) > 0
             and "Uprising" not in (state.get("markers", {}).get(r) or {})]
    return {"region": sorted(cands)[0]} if cands else None


def _derive_card_A17(state, faction, shaded):
    """A17 (shaded): "Remove 4 Auxilia from any 1 Region." Choose the Region
    per the acting Faction's Ariovistus instruction:
      German: most Roman Auxilia removable from Germania or where a German
              Settlement, then adjacent to Germania/Settlement; else none.
      Belgic: Belgica Regions first.
      Other:  most Roman Auxilia.
    The unshaded side is the Roman free March+Battle (executed, not derived).
    """
    if not shaded:
        return None
    from fs_bot.rules_consts import (ROMANS, GERMANS, BELGAE, AUXILIA,
                                     SETTLEMENT, GERMANIA_REGIONS,
                                     BELGICA_REGIONS)
    from fs_bot.board.pieces import count_pieces
    from fs_bot.map.map_data import get_adjacent, get_playable_regions
    scen = state["scenario"]
    playable = get_playable_regions(scen, state.get("capabilities"))
    cands = [(r, count_pieces(state, r, ROMANS, AUXILIA)) for r in sorted(playable)]
    cands = [(r, n) for r, n in cands if n > 0]
    if not cands:
        return None
    if faction == GERMANS:
        settlement_regions = {r for r in sorted(playable)
                              if count_pieces(state, r, GERMANS, SETTLEMENT) > 0}
        core = set(GERMANIA_REGIONS) | settlement_regions
        adj = set()
        for r in core:
            adj.update(get_adjacent(r, scen))
        def gkey(item):
            r, n = item
            tier = 0 if r in core else (1 if r in adj else 2)
            return (tier, -n)
        cands.sort(key=gkey)
        # German instruction targets Roman pieces near Germania; if the best
        # is neither in/adjacent to Germania nor a Settlement, still allowed
        # ("any 1 Region") — pick most Auxilia.
        return {"region": cands[0][0]}
    if faction == BELGAE:
        belgica = set(BELGICA_REGIONS)
        cands.sort(key=lambda it: (0 if it[0] in belgica else 1, -it[1]))
        return {"region": cands[0][0]}
    cands.sort(key=lambda it: -it[1])
    return {"region": cands[0][0]}


def _derive_card_11(state, faction, shaded):
    """Cards 11 (Numidians) / 11a (Ariovistus text): unshaded "Romans place 3
    Auxilia in a Region within 1 of their Leader and free Battle there."

    Roman NP instruction (Numidians): "Place the full number of Auxilia; if not
    able, treat as 'No Romans'." So choose a Region within 1 of the Roman
    Leader where the Romans can place all 3 Auxilia (>=3 Available) and an
    enemy is present to Battle, ranked by Roman Battle priority (8.8.1). If
    none qualifies, return None (no placement, no Battle).

    Returns both the base ("target_region") and Ariovistus ("region") param
    keys so whichever card text is in play reads its own key.
    """
    if shaded:
        return None
    from fs_bot.rules_consts import ROMANS, AUXILIA
    from fs_bot.board.pieces import (find_leader, count_pieces, get_available)
    from fs_bot.map.map_data import get_adjacent, get_playable_regions
    from fs_bot.bots.roman_bot import _rank_battle_targets
    if get_available(state, ROMANS, AUXILIA) < 3:
        return None  # "Place the full number ... if not able, 'No Romans'."
    leader = find_leader(state, ROMANS)
    if leader is None:
        return None
    scen = state["scenario"]
    playable = set(get_playable_regions(scen, state.get("capabilities")))
    within1 = ({leader} | set(get_adjacent(leader, scen))) & playable
    best = None  # (region, enemy_mobile)
    for r in sorted(within1):
        targets = _rank_battle_targets(state, r, scen)
        if not targets:
            continue
        enemy = targets[0]
        from fs_bot.rules_consts import WARBAND, LEGION, AUXILIA as AUX
        em = (count_pieces(state, r, enemy, WARBAND)
              + count_pieces(state, r, enemy, AUX)
              + count_pieces(state, r, enemy, LEGION))
        if best is None or em > best[1]:
            best = (r, em)
    if best is None:
        return None
    return {"target_region": best[0], "region": best[0]}


def _derive_card_2(state, faction, shaded):
    """Card 2 Legiones (shaded): "Free Battle against Romans in a Region. The
    first Loss removes a Legion automatically, if any there."

    The acting (non-Roman) Faction chooses a Region where it can Battle the
    Romans — preferring a Region holding a Roman Legion (so the auto-Legion
    Loss bites) and where it has an attacking force, by Roman pieces present.
    Returns {"battle_region": R}, or None if no such Region (the unshaded side
    is the Senate/Legions placement, handled in the card).
    """
    from fs_bot.rules_consts import ROMANS, LEGION
    if not shaded or faction == ROMANS:
        return None
    ROM = ROMANS
    from fs_bot.board.pieces import count_pieces
    from fs_bot.map.map_data import get_playable_regions
    playable = get_playable_regions(state["scenario"], state.get("capabilities"))
    best = None  # (region, has_legion, roman_pieces)
    for r in sorted(playable):
        if not _attacker_has_force(state, r, faction):
            continue
        if count_pieces(state, r, ROM) <= 0:
            continue
        has_leg = 1 if count_pieces(state, r, ROM, LEGION) > 0 else 0
        roman = count_pieces(state, r, ROM)
        key = (has_leg, roman)
        if best is None or key > best[1]:
            best = (r, key)
    return {"battle_region": best[0]} if best else None


def _derive_card_4(state, faction, shaded):
    """Card 4 Circumvallation: "Romans may free March to an adjacent Citadel
    and put Circumvallation marker on Citadel Faction's pieces there."

    Choose the Region holding a non-Roman Citadel that is adjacent to a Roman
    mobile group (so the Romans can March in), preferring the Citadel Region
    with the most enemy pieces to trap. Returns {"target_region": R} or None.
    Roman-only.
    """
    from fs_bot.rules_consts import ROMANS, CITADEL, FACTIONS
    from fs_bot.board.pieces import count_pieces
    from fs_bot.map.map_data import get_adjacent, get_playable_regions
    if faction != ROMANS:
        return None
    playable = set(get_playable_regions(state["scenario"], state.get("capabilities")))
    best = None  # (region, enemy_pieces)
    for R in sorted(playable):
        has_enemy_citadel = any(
            f != ROMANS and count_pieces(state, R, f, CITADEL) > 0
            for f in FACTIONS)
        if not has_enemy_citadel:
            continue
        adj_roman = any(
            _group_has_pieces(_mobile_march_group(state, ROMANS, a))
            for a in get_adjacent(R, state["scenario"]) if a in playable)
        if not adj_roman:
            continue
        enemy = sum(count_pieces(state, R, f) for f in FACTIONS if f != ROMANS)
        if best is None or enemy > best[1]:
            best = (R, enemy)
    return {"target_region": best[0]} if best else None


def _derive_card_70(state, faction, shaded):
    """Card 70 Camulogenus (shaded): "Place 0-6 Warbands among Atrebates,
    Carnutes, and Mandubii; select 1 for a free Command + Special Ability."

    Place all available Warbands (up to 6) of the acting Faction in the one of
    those Regions where it will best act: the Region with the most enemy
    pieces to Battle, else where the Faction already has the most presence,
    else the first. The executor then runs the free Command restricted to that
    Region. Unshaded (Roman March+Battle) needs no params.
    """
    if not shaded:
        return None
    from fs_bot.rules_consts import (ATREBATES, CARNUTES, MANDUBII, WARBAND,
                                     FACTIONS)
    from fs_bot.board.pieces import count_pieces, get_available
    from fs_bot.map.map_data import get_playable_regions
    if faction is None:
        return None
    avail = get_available(state, faction, WARBAND)
    if avail <= 0:
        return None
    playable = set(get_playable_regions(state["scenario"], state.get("capabilities")))
    regs = [r for r in (ATREBATES, CARNUTES, MANDUBII) if r in playable]
    if not regs:
        return None
    def score(r):
        enemy = sum(count_pieces(state, r, f) for f in FACTIONS if f != faction)
        own = count_pieces(state, r, faction)
        return (enemy, own)
    R = max(regs, key=score)
    return {"placements": [{"region": R, "count": min(6, avail)}]}


def _derive_card_25(state, faction, shaded):
    """Card 25 Aquitani (unshaded): free Battle in Pictones or the Arverni
    Region. Choose the one where the acting Faction has an attacking force and
    an enemy is present (most enemy pieces). Shaded is a Capability."""
    if shaded:
        return None
    from fs_bot.rules_consts import PICTONES, ARVERNI_REGION, FACTIONS
    from fs_bot.board.pieces import count_pieces
    from fs_bot.map.map_data import get_playable_regions
    playable = set(get_playable_regions(state["scenario"], state.get("capabilities")))
    best = None
    for R in (PICTONES, ARVERNI_REGION):
        if R not in playable or not _attacker_has_force(state, R, faction):
            continue
        enemy = sum(count_pieces(state, R, f) for f in FACTIONS if f != faction)
        if enemy > 0 and (best is None or enemy > best[1]):
            best = (R, enemy)
    return {"battle_region": best[0]} if best else None


def _derive_card_16(state, faction, shaded):
    """Card 16 Ambacti (unshaded): place 4 Auxilia in a Region with Romans, or
    6 with Caesar. Prefer Caesar's Region (6); else the Region with the most
    Roman pieces. Shaded (die-roll removal) is handled in the card."""
    from fs_bot.rules_consts import ROMANS, AUXILIA
    from fs_bot.board.pieces import find_leader, count_pieces, get_available
    if shaded or faction != ROMANS:
        return None
    from fs_bot.map.map_data import get_playable_regions
    if get_available(state, ROMANS, AUXILIA) <= 0:
        return None
    caesar = find_leader(state, ROMANS)
    if caesar is not None and count_pieces(state, caesar, ROMANS) > 0:
        return {"target_region": caesar}
    best = None
    for r in get_playable_regions(state["scenario"], state.get("capabilities")):
        rp = count_pieces(state, r, ROMANS)
        if rp > 0 and (best is None or rp > best[1]):
            best = (r, rp)
    return {"target_region": best[0]} if best else None


def _derive_card_44(state, faction, shaded):
    """Card 44 Dumnorix Loyalists. Unshaded: replace up to 4 enemy Warbands
    with Auxilia (Roman actor) or the acting Faction's Warbands; they free
    Scout. Shaded: replace up to 3 Roman Auxilia with the acting Faction's
    Warbands (take Auxilia first, exposing Legions); they free Raid."""
    from fs_bot.rules_consts import (ROMANS, WARBAND, AUXILIA, HIDDEN, REVEALED,
                                     FACTIONS)
    from fs_bot.board.pieces import count_pieces_by_state, count_pieces
    from fs_bot.map.map_data import get_playable_regions
    playable = get_playable_regions(state["scenario"], state.get("capabilities"))
    if not shaded:
        to_type = AUXILIA if faction == ROMANS else WARBAND
        reps = []
        for region in sorted(playable):
            for ef in FACTIONS:
                if ef == faction:
                    continue
                for ps in (HIDDEN, REVEALED):
                    for _ in range(count_pieces_by_state(state, region, ef,
                                                          WARBAND, ps)):
                        if len(reps) >= 4:
                            break
                        reps.append({"region": region, "from_faction": ef,
                                     "to_type": to_type, "to_faction": faction,
                                     "piece_state": ps})
        return {"replacements": reps} if reps else None
    reps = []
    for region in sorted(playable):
        for _ in range(count_pieces(state, region, ROMANS, AUXILIA)):
            if len(reps) >= 3:
                break
            reps.append({"region": region, "from_faction": ROMANS,
                         "from_type": AUXILIA, "to_faction": faction})
    return {"replacements": reps} if reps else None


def _derive_card_A58(state, faction, shaded):
    """Card A58 Aduatuca (shaded): in 1 Belgica Region, replace 1 Roman Ally
    and 3 Auxilia with the acting Faction's, then free Ambush Romans. Choose a
    Belgica Region with a Roman-allied Tribe and Roman Auxilia. (Unshaded is
    the Roman Battle+Seize, executed not derived.)"""
    if not shaded:
        return None
    from fs_bot.rules_consts import ROMANS, AUXILIA, BELGICA_REGIONS
    from fs_bot.board.pieces import count_pieces
    from fs_bot.map.map_data import get_tribes_in_region
    for R in BELGICA_REGIONS:
        if count_pieces(state, R, ROMANS, AUXILIA) <= 0:
            continue
        for t in get_tribes_in_region(R, state["scenario"]):
            ti = state.get("tribes", {}).get(t)
            if ti and ti.get("allied_faction") == ROMANS:
                return {"region": R, "ally_tribe": t}
    return None


# Registry of per-card event_param derivers (extend as cards gain faithful
# NP derivations). Card 1 (Cicero) is the unambiguous senate-direction case.
def _derive_card_A29(state, faction, shaded):
    """A29 unshaded: a Gaul or Roman places up to 2 own Allies at Subdued Tribes
    in Regions with (German) Settlements, plus 5 own Warbands (Gallic) / 3
    Auxilia (Roman) among those Regions (§8.2.3 — benefit self)."""
    if shaded:
        return None
    from fs_bot.rules_consts import (GERMANS, ROMANS, GALLIC_FACTIONS,
                                     SETTLEMENT, WARBAND, AUXILIA, ALLY)
    from fs_bot.board.pieces import count_pieces, get_available
    from fs_bot.map.map_data import get_playable_regions, get_tribes_in_region
    if faction == GERMANS:
        return None
    scen = state["scenario"]
    settlement_regions = [
        r for r in get_playable_regions(scen, state.get("capabilities"))
        if count_pieces(state, r, GERMANS, SETTLEMENT) > 0]
    if not settlement_regions:
        return None
    placements = []
    avail_ally = get_available(state, faction, ALLY)
    n_ally = 0
    for region in settlement_regions:
        if n_ally >= min(2, avail_ally):
            break
        for tribe in get_tribes_in_region(region, scen):
            ti = state.get("tribes", {}).get(tribe)
            if (ti and ti.get("allied_faction") is None
                    and ti.get("status") is None):
                placements.append({"region": region, "piece_type": ALLY,
                                   "faction": faction, "tribe": tribe})
                n_ally += 1
                break
    if faction in GALLIC_FACTIONS:
        n = min(5, get_available(state, faction, WARBAND))
        if n > 0:
            placements.append({"region": settlement_regions[0],
                               "piece_type": WARBAND, "faction": faction,
                               "count": n})
    elif faction == ROMANS:
        n = min(3, get_available(state, faction, AUXILIA))
        if n > 0:
            placements.append({"region": settlement_regions[0],
                               "piece_type": AUXILIA, "faction": faction,
                               "count": n})
    return {"placements": placements} if placements else None


def _derive_card_A40(state, faction, shaded):
    """A40 unshaded: place up to (3 Warbands / 2 Auxilia) of the acting Faction
    in each of up to 3 Regions within 1 of Cisalpina (§8.2.3 — own pieces;
    Romans place Auxilia, others place Warbands)."""
    if shaded:
        return None
    from fs_bot.rules_consts import ROMANS, WARBAND, AUXILIA, CISALPINA
    from fs_bot.board.pieces import get_available
    from fs_bot.map.map_data import get_adjacent, get_playable_regions
    scen = state["scenario"]
    playable = set(get_playable_regions(scen, state.get("capabilities")))
    near = [r for r in ([CISALPINA] + list(get_adjacent(CISALPINA, scen)))
            if r in playable]
    if not near:
        return None
    pt, cap = (AUXILIA, 2) if faction == ROMANS else (WARBAND, 3)
    avail = get_available(state, faction, pt)
    placements = []
    used = 0
    for region in near:
        if used >= 3 or avail <= 0:
            break
        n = min(cap, avail)
        if n > 0:
            placements.append({"region": region, "piece_type": pt,
                               "faction": faction, "count": n})
            avail -= n
            used += 1
    return {"placements": placements} if placements else None


_EVENT_PARAM_DERIVERS = {
    1: _derive_senate_direction,
    2: _derive_card_2,
    "A58": _derive_card_A58,
    44: _derive_card_44,
    16: _derive_card_16,
    25: _derive_card_25,
    4: _derive_card_4,
    70: _derive_card_70,
    11: _derive_card_11,
    "A17": _derive_card_A17,
    "A18": _derive_card_A18,
    "A37": _derive_card_A37,
    "A29": _derive_card_A29,
    "A40": _derive_card_A40,
    "A45": _derive_card_A45,
    "A64": _derive_card_A64,
    "A66": _derive_card_A66,
    22: _derive_card_22,
    28: _derive_card_28,
    41: _derive_card_41,
    23: _derive_card_23,
    42: _derive_card_42,
    58: _derive_card_58,
    68: _derive_card_68,
    71: _derive_card_71,
}


def _control_keep_warbands(state, faction, region, *, leader_leaving):
    """Warbands to LEAVE in a Region so the Faction keeps Control after a
    March out (flowcharts: 'leave one Warband and enough not to remove
    Control'). The Leader, if leaving, no longer counts toward strength.
    """
    from fs_bot.rules_consts import WARBAND, FACTIONS
    from fs_bot.board.control import is_controlled_by
    total_wb = count_pieces(state, region, faction, WARBAND)
    if total_wb <= 0:
        return 0
    others = sum(count_pieces(state, region, of)
                 for of in FACTIONS if of != faction)
    own_nonwb = count_pieces(state, region, faction) - total_wb
    if leader_leaving:
        own_nonwb -= 1
    if is_controlled_by(state, region, faction):
        keep = max(1, others - own_nonwb + 1)
    else:
        keep = 1  # still leave at least one behind
    return min(total_wb, keep)


def plan_expand_march_moves(state, faction, plan):
    """Dry-run of an "expand/mass/spread/control" March (§8.6.5/§8.7.4-6/
    A8.7.5): compute the moves the executor would make, WITHOUT mutating
    state.

    Shared by _execute_expand_march (which applies the moves) and the bot
    March nodes (which consult it for their flowchart "IF NONE" edges — e.g.
    V_MARCH_MASS/V_MARCH_SPREAD redirect to Raid when nothing is marchable,
    §8.7.4/§8.7.6). One rule, one implementation.

    Returns:
        List of move dicts {"origin", "path", "group", "leader": bool}.
        Empty list when nothing can March (pinned by Control-keeping
        leave-behinds, no reachable destination, or no plan).
    """
    from fs_bot.rules_consts import LEADER, WARBAND, LEGION, AUXILIA
    from fs_bot.board.pieces import find_leader

    if not isinstance(plan, dict):
        return []

    # "destination" (singular) is the V_MARCH_MASS shape (§8.7.6): a Leader
    # march. It was previously unread, so every mass March was refused.
    leader_dests = [plan.get(k) for k in
                    ("leader_destination", "leader_or_group_destination",
                     "diviciacus_destination", "destination")
                    if isinstance(plan.get(k), str)]
    cs_dests = []
    cd = plan.get("control_destination")
    if isinstance(cd, str):
        cs_dests.append(cd)
    for key in ("control_destinations", "spread_destinations", "destinations"):
        for v in (plan.get(key) or []):
            if isinstance(v, str):
                cs_dests.append(v)
            elif isinstance(v, (list, tuple)) and v and isinstance(v[0], str):
                cs_dests.append(v[0])
    if not cs_dests and isinstance(plan.get("destination"), str):
        cs_dests.append(plan["destination"])

    origins = list(plan.get("origins") or [])
    o1 = plan.get("origin")
    if isinstance(o1, str) and o1 not in origins:
        origins.append(o1)

    scenario = state["scenario"]
    playable = set(get_playable_regions(scenario, state.get("capabilities")))

    def _nearest(origin, candidates):
        best = None
        for d in candidates:
            if d == origin:
                continue
            path = _bfs_march_path(origin, d, playable)
            if path is None:
                continue
            if best is None or len(path) < best[0]:
                best = (len(path), d, path)
        return best

    moves, processed = [], set()

    # --- 1. Leader group march ---
    leader_region = find_leader(state, faction)
    if leader_region is not None:
        dests = leader_dests if leader_dests else cs_dests
        best = _nearest(leader_region, dests)
        if best is not None:
            keep = _control_keep_warbands(state, faction, leader_region,
                                          leader_leaving=True)
            march_wb = max(0, count_pieces(state, leader_region, faction,
                                           WARBAND) - keep)
            group = {LEADER: get_leader_in_region(state, leader_region,
                                                  faction),
                     WARBAND: march_wb, LEGION: 0, AUXILIA: 0}
            moves.append({"origin": leader_region, "path": best[2],
                          "group": group, "leader": True,
                          "warbands": march_wb})
            processed.add(leader_region)

    # --- 2. Warband-only control-spreading from other origins ---
    for origin in origins:
        if origin in processed or not isinstance(origin, str):
            continue
        keep = _control_keep_warbands(state, faction, origin,
                                      leader_leaving=False)
        march_wb = max(0, count_pieces(state, origin, faction, WARBAND) - keep)
        if march_wb <= 0:
            continue
        best = _nearest(origin, cs_dests)
        if best is None:
            continue
        group = {LEADER: None, WARBAND: march_wb, LEGION: 0, AUXILIA: 0}
        moves.append({"origin": origin, "path": best[2], "group": group,
                      "leader": False, "warbands": march_wb})
        processed.add(origin)

    return moves


def _execute_expand_march(state, faction, plan):
    """Execute an "expand/mass/spread/control" March (§8.6.5/§8.7.4-6/A8.7.5).

    Two parts, both with a Control-preserving leave-behind:
      1. Move the Faction LEADER's group toward its Leader destination
         (preferred) or a control/spread destination.
      2. Move spare Warbands from each other origin toward a control/spread
         destination to add Control, leaving one Warband and enough to keep
         the origin's Control.
    The moves themselves come from plan_expand_march_moves (also used by the
    bot planners' IF-NONE checks). Returns the standard March result dict.
    """
    moves = plan_expand_march_moves(state, faction, plan)

    marches, errors = [], []
    for mv in moves:
        try:
            _flip_origin_pieces(state, mv["origin"], faction)
            final = _march_group_fixed(state, faction, mv["origin"],
                                       mv["path"], mv["group"])
            marches.append({"origin": mv["origin"], "final_region": final,
                            "leader": mv["leader"],
                            "warbands": mv["warbands"]})
        except _EXEC_ERRORS as exc:
            errors.append({"origin": mv["origin"], "error": str(exc)})

    if not marches:
        return {"executed": False, "command": _CMD_MARCH,
                "reason": "expand/mass march: nothing marchable (leader/"
                          "warbands pinned by Control or no reachable dest)",
                "errors": errors}
    return {"executed": True, "command": _CMD_MARCH, "marches": marches,
            "deferred_origins": [], "errors": errors}


def _march_group_fixed(state, faction, origin, path, group):
    """March a specific group along a path (step by step), returning the final
    Region. Unlike _march_with_harassment this marches a CAPPED group (used for
    the Leader's expand/mass move with a Control-preserving Warband count)."""
    current = origin
    for nxt in path:
        march_group(state, faction, current, [nxt], group, free=False)
        current = nxt
    return current
