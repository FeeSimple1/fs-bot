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
from fs_bot.map.map_data import is_adjacent
from fs_bot.bots.bot_common import random_select
from fs_bot.commands.sa_trade import trade as _sa_trade
from fs_bot.commands.sa_settle import settle as _sa_settle
from fs_bot.commands.sa_devastate import devastate_region as _sa_devastate
from fs_bot.commands.sa_intimidate import intimidate as _sa_intimidate
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
            res = resolve_battle(
                state, region, faction, defender,
                is_ambush=is_ambush, besiege_target=besiege_target,
                retreat_declaration=None,
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

    marched = []
    errors = []
    deferred_origins = []
    for origin in origins:
        group = _mobile_march_group(state, faction, origin)
        if not _group_has_pieces(group):
            continue
        adj_dests = [d for d in dest_pool if is_adjacent(origin, d)]
        if not adj_dests:
            # Only single-step adjacent destinations are unambiguous here.
            deferred_origins.append(origin)
            continue
        dest = (random_select(state, adj_dests)
                if len(adj_dests) > 1 else adj_dests[0])
        try:
            # §3.2.2: marching pieces flip to Hidden (Underground) as they
            # March. march_group moves them in Hidden state, so flip first.
            _flip_origin_pieces(state, origin, faction)
            res = march_group(state, faction, origin, [dest], group)
            marched.append({"origin": origin,
                            "final_region": res.get("final_region")})
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
