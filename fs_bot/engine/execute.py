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
from fs_bot.commands.seize import seize_in_region, get_dispersible_tribes
from fs_bot.cards.card_effects import execute_event


# Bot command labels (mirror the per-bot ACTION_* constants, which all
# share these string values).
_CMD_EVENT = "Event"
_CMD_SEIZE = "Seize"

# Commands recognized but not yet wired in this slice.
_UNWIRED_COMMANDS = {
    "Battle", "March", "Rally", "Raid", "Recruit",
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
        except CommandError as exc:
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
