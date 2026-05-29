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
_SA_AMBUSH = "Ambush"
_SA_BESIEGE = "Besiege"

# Commands recognized but not yet wired in this slice.
_UNWIRED_COMMANDS = {
    "March", "Recruit",
}


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

    if command == _CMD_EVENT:
        return _execute_event(state, faction, bot_action)
    if command == _CMD_SEIZE:
        return _execute_seize(state, faction, bot_action)
    if command == _CMD_RAID:
        return _execute_raid(state, faction, bot_action)
    if command == _CMD_RALLY:
        return _execute_rally(state, faction, bot_action)
    if command == _CMD_BATTLE:
        return _execute_battle(state, faction, bot_action)
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
    sa_regions = set(bot_action.get("sa_regions", []) or [])

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
