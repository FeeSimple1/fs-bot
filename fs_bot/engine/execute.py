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
from fs_bot.map.map_data import is_adjacent, get_playable_regions
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
_SA_ENLIST = "Enlist"
SA_ACTION_NONE_LABEL = "No SA"
# SAs handled inside Battle resolution, not as standalone post-command SAs.
_BATTLE_MODIFYING_SAS = {_SA_AMBUSH, _SA_BESIEGE}

# Commands recognized but not yet wired in this slice.
_UNWIRED_COMMANDS = set()


def execute_decision(state, faction, decision):
    """Apply a recorded SoP decision to the board, if supported.

    Args:
        state: Game state dict. Modified in place when an action executes.
        faction: The acting faction constant.
        decision: The dict returned by the engine decision_func. For bot
            turns this contains ``bot_action`` (the full action dict).

    Returns:
        Result dict: always has ``executed`` (bool) and ``command`` (str);
        plus ``reason`` when not executed, or command-specific details when
        executed.
    """
    bot_action = decision.get("bot_action")
    if not bot_action:
        # Human decisions (or malformed) carry no bot_action plan; the
        # human execution path is a separate workstream.
        return {"executed": False, "command": None,
                "reason": "no bot_action plan in decision"}

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
        result = handler(state, faction, bot_action)
        # Run the accompanying standalone Special Activity, if any. Battle-
        # modifying SAs (Ambush/Besiege) are applied inside _execute_battle,
        # so they are skipped here.
        sa_result = _execute_sa(state, faction, bot_action)
        if sa_result is not None:
            result = dict(result)
            result["sa_execution"] = sa_result
        return result
    if command in _UNWIRED_COMMANDS:
        return {"executed": False, "command": command,
                "reason": "command not yet wired (proof slice)"}
    # Pass / None / unknown
    return {"executed": False, "command": command,
            "reason": "no executable command"}


def _execute_event(state, faction, bot_action):
    """Execute an Event via the card_effects dispatcher.

    The bot's Event decision carries the card id and the Dual-Use text
    preference (§8.2.2 / A8.2.2). We map that preference to the dispatcher's
    ``shaded`` flag. Unimplemented card stubs or unknown ids are reported,
    not raised, so a full game keeps running.
    """
    details = bot_action.get("details", {})
    card_id = details.get("card_id", state.get("current_card"))
    shaded = details.get("text_preference") == EVENT_SHADED

    try:
        event_result = execute_event(state, card_id, shaded=shaded)
    except (NotImplementedError, KeyError) as exc:
        return {"executed": False, "command": _CMD_EVENT,
                "card_id": card_id, "shaded": shaded,
                "reason": f"event not executable: {exc!r}"}
    except ValueError as exc:
        # Cards that need explicit choices read state["event_params"], which
        # the decision layer does not yet populate (a separate sub-workstream).
        # Report rather than crash so a full game keeps running.
        return {"executed": False, "command": _CMD_EVENT,
                "card_id": card_id, "shaded": shaded,
                "reason": f"event needs parameters: {exc!r}"}
    return {"executed": True, "command": _CMD_EVENT,
            "card_id": card_id, "shaded": shaded,
            "event_result": event_result}


def _execute_seize(state, faction, bot_action):
    """Execute a Seize Command — §3.2.3, target priorities §8.8.5.

    The Roman bot supplies ``regions`` (all Seize regions, dispersal-capable
    first) and ``details['disperse_regions']`` (the subset where Dispersal
    should occur). In each dispersal region we Disperse the Subdued tribes
    the rules allow (`get_dispersible_tribes`, which already enforces Roman
    Control and the 4-marker cap); remaining regions still Forage.

    The Build Special Activity that accompanies the bot's Seize is part of
    the SA wiring workstream and is not executed here.
    """
    details = bot_action.get("details", {})
    regions = bot_action.get("regions", []) or []
    disperse_regions = set(details.get("disperse_regions", []) or [])

    per_region = []
    dispersed_total = 0
    forage_total = 0
    errors = []

    for region in regions:
        if region in disperse_regions:
            tribes = get_dispersible_tribes(state, region)
        else:
            tribes = []
        try:
            res = seize_in_region(state, region, tribes_to_disperse=tribes)
        except _EXEC_ERRORS as exc:
            errors.append({"region": region, "error": str(exc)})
            continue
        dispersed_total += len(res.get("tribes_dispersed", []))
        forage_total += res.get("forage_resources", 0)
        # Harassment against the seizing Romans — §3.2.3 / §8.4.2.
        harass = _resolve_seize_harassment(state, region)
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
        "sa_not_wired": bot_action.get("sa"),
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

    Any accompanying Special Activity (Devastate/Entreat/Intimidate) is part
    of the SA wiring workstream and is not executed here.
    """
    details = bot_action.get("details", {})
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
        "sa_not_wired": bot_action.get("sa"),
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
    details = bot_action.get("details", {})
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
        "sa_not_wired": bot_action.get("sa"),
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
    details = bot_action.get("details", {})
    battle_plan = details.get("battle_plan", []) or []
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

        is_ambush = (sa == _SA_AMBUSH and region in sa_regions)

        besiege_target = None
        if sa == _SA_BESIEGE and region in sa_regions:
            options = get_besiege_targets(state, region, defender)
            if options:
                besiege_target = options[0]  # Citadel > Ally > Settlement

        try:
            retreat_decl, retreat_region = _decide_defender_retreat(
                state, region, faction, defender, is_ambush)
            res = resolve_battle(
                state, region, faction, defender,
                is_ambush=is_ambush, besiege_target=besiege_target,
                retreat_declaration=retreat_decl,
                retreat_region=retreat_region,
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
    allow. The accompanying Build SA is part of the SA workstream.
    """
    details = bot_action.get("details", {})
    plan = details.get("recruit_plan", []) or []

    placed = []
    errors = []
    for entry in plan:
        region = entry.get("region")
        action = entry.get("action")
        if region is None or action is None:
            continue
        try:
            res = recruit_in_region(state, region, action,
                                    tribe=entry.get("tribe"))
            placed.append({"region": region, "action": action,
                           "tribe": entry.get("tribe")})
        except _EXEC_ERRORS as exc:
            errors.append({"region": region, "action": action,
                           "error": str(exc)})

    return {
        "executed": len(placed) > 0,
        "command": _CMD_RECRUIT,
        "placements": placed,
        "sa_not_wired": bot_action.get("sa"),
        "errors": errors,
    }


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
    details = bot_action.get("details", {})
    plan = details.get("march_plan", {}) or {}
    origins = plan.get("origins")
    destinations = plan.get("destinations")

    if not (isinstance(origins, list) and isinstance(destinations, list)
            and origins and destinations):
        return {"executed": False, "command": _CMD_MARCH,
                "reason": "march plan shape not execution-complete "
                          "(expand/mass routing deferred to bot enrichment)"}

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
        "sa_not_wired": bot_action.get("sa"),
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
    current = origin
    for i, nxt in enumerate(path):
        group = _mobile_march_group(state, faction, current)
        if not _group_has_pieces(group):
            break
        res = march_group(state, faction, current, [nxt], group)
        current = res.get("final_region", nxt)
        if current != nxt:
            break  # a crossing stop halted the group early
        # Intermediate Region (entered then about to be left) -> Harassment.
        if i < len(path) - 1:
            group_now = _mobile_march_group(state, faction, current)
            harassers = _np_harassers(state, current, faction, group_now)
            if harassers:
                from fs_bot.commands.march import resolve_harassment
                resolve_harassment(state, current, faction, group_now,
                                   harassing_factions=harassers)
    return current


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

    if sa == _SA_TRADE:
        return _execute_trade(state, faction)
    if sa == _SA_SETTLE:
        return _execute_settle(state, faction, bot_action)
    if sa == _SA_DEVASTATE:
        return _execute_devastate(state, faction, bot_action)
    if sa == _SA_INTIMIDATE:
        return _execute_intimidate(state, faction, bot_action)
    if sa == _SA_SUBORN:
        return _execute_suborn(state, faction, bot_action)
    if sa == _SA_BUILD:
        return _execute_build(state, faction, bot_action)
    if sa == _SA_RAMPAGE:
        return _execute_rampage(state, faction, bot_action)
    if sa == _SA_ENTREAT:
        return _execute_entreat(state, faction, bot_action)
    if sa == _SA_SCOUT:
        return _execute_scout(state, faction, bot_action)
    if sa == _SA_ENLIST:
        return _execute_enlist(state, faction, bot_action)

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
    details = bot_action.get("details", {})
    plan = details.get("intimidate_plan", []) or []

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
    details = bot_action.get("details", {})
    plan = details.get("suborn_plan", []) or []

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
                            "piece_type": _ALLY})
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
    return {"executed": len(done) > 0, "sa": _SA_BUILD,
            "actions": done, "errors": errors}


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
    from fs_bot.map.map_data import get_adjacent
    from fs_bot.board.control import is_controlled_by
    from fs_bot.battle.losses import calculate_losses

    if is_ambush:
        return (False, None)  # §4.3.3: Defender may not Retreat from Ambush
    scenario = state["scenario"]
    if defender == GERMANS and scenario in BASE_SCENARIOS:
        return (False, None)  # §3.2.4: Germans never Retreat (base)
    if defender == ARVERNI and scenario in ARIOVISTUS_SCENARIOS:
        return (False, None)  # A3.2.4: Arverni never Retreat

    # Condition (3): a Retreat removes no pieces only if a legal destination
    # exists — an adjacent Region the defender Controls, OR one Controlled by
    # a Faction that agrees to the Retreat (§1.5.2; Aedui/Romans per
    # §8.6.6/§8.8.6, via np_agrees_to_retreat).
    dest = _best_retreat_destination(state, region, defender)
    if dest is None:
        return (False, None)

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
                if np_agrees_to_retreat(c, faction, state):
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
    from fs_bot.rules_consts import ROMANS, AUXILIA, ALLY, LEGION, LEADER, FORT
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
    moves = plan.get("auxilia_moves", []) or []
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

    return {"executed": len(done) > 0, "sa": _SA_SCOUT,
            "actions": done, "errors": errors}


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
    ed = bot_action.get("details", {}).get("enlist")
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
            _flip_origin_pieces(state, origin, GERMANS)
            group = _mobile_march_group(state, GERMANS, origin)
            if not _group_has_pieces(group):
                return {"executed": False, "sa": _SA_ENLIST,
                        "type": t, "reason": "no German pieces to March"}
            march_group(state, GERMANS, origin, [dest], group, free=True)
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
