"""Card 63/A63: up to two paid Commands and/or Special Abilities.

Card Reference 63 explicitly releases normal SA/accompanying-Command and
Britannia restrictions; Ambush/Besiege still need the other action to be Battle.
"""

import copy

from fs_bot.engine.agent import consult_agent
from fs_bot.rules_consts import ROMANS, EVENT_SHADED, ARIOVISTUS_SCENARIOS


def validate_plan(state, faction, plan, remaining=2):
    """Validate the card's action budget/ownership; return actions consumed."""
    from fs_bot.cli.human_plan import _FACTION_COMMANDS, _faction_special_abilities
    if not isinstance(plan, dict):
        raise ValueError("Winter Campaign requires a plan object.")
    if plan == {"decline": True}:
        return 0
    command = plan.get("command")
    sa = plan.get("sa")
    has_command = command not in (None, "None")
    has_sa = sa not in (None, "No SA")
    if has_command and command not in _FACTION_COMMANDS.get(faction, ()):
        raise ValueError("Winter Campaign must use one of this faction's Commands.")
    if has_sa and sa not in _faction_special_abilities(faction, state["scenario"]):
        raise ValueError("Winter Campaign must use one of this faction's Special Abilities.")
    cost = int(has_command) + int(has_sa)
    if not cost or cost > remaining:
        raise ValueError(f"Winter Campaign has {remaining} action(s) remaining.")
    if sa in ("Ambush", "Besiege") and command != "Battle":
        raise ValueError("Ambush/Besiege must pair with Battle as the other action (card 63).")
    if plan.get("sa_timing", "after") not in ("before", "after"):
        raise ValueError("Winter Campaign paired actions use before or after timing.")
    if not isinstance(plan.get("details", {}), dict):
        raise ValueError("Winter Campaign details must be an object.")
    return cost


def _bot_plan(state, faction, remaining):
    from fs_bot.bots.bot_dispatch import dispatch_bot_turn
    # A shallow view changes only decision context. The shared RNG remains
    # authoritative for the real flowchart choice, and no free-cost flag is set.
    planning = dict(state, can_play_event=False, is_second_eligible=False)
    # A human may explicitly delegate this grant to the bot.  Dispatch checks
    # seat ownership, so mark only the planning view as NP; execution retains
    # the real seat's player rules and paid Command costs.
    planning["non_player_factions"] = set(state.get("non_player_factions", ())) | {faction}
    planning.pop("_planning_free_command", None)
    plan = dispatch_bot_turn(planning, faction)
    if plan.get("command") in (None, "None", "Pass", "Event"):
        return {"decline": True}
    plan = copy.deepcopy(plan)
    if remaining == 1:
        plan["sa"] = "No SA"
        plan["sa_regions"] = []
    return plan


def _execute_plan(state, faction, plan, *, uses_bot=False):
    """Apply one paid plan with the card's Command/SA compatibility exception."""
    from fs_bot.engine.execute import (_execute_decision, _execute_sa,
                                       _apply_end_of_action_capabilities)
    if plan.get("command") in (None, "None"):
        result = _execute_sa(state, faction, plan) or {"executed": False}
        _apply_end_of_action_capabilities(state)
        return result
    return _execute_decision(
        state, faction, {"bot_action" if uses_bot else "player_action": plan})


def validate_human_plan(state, faction, plan, remaining=2):
    """Check paid mechanical feasibility without consuming live pieces/RNG/input."""
    used = validate_plan(state, faction, plan, remaining)
    if not used:
        return used
    from fs_bot.engine.free_actions import _result_error
    from fs_bot.commands.common import CommandError
    from fs_bot.board.pieces import PieceError
    sim = copy.deepcopy({k: v for k, v in state.items() if k != "decision_agent"})
    try:
        result = _execute_plan(sim, faction, copy.deepcopy(plan))
    except (CommandError, PieceError, ValueError, TypeError, KeyError,
            IndexError, AttributeError) as exc:
        raise ValueError(f"Invalid Winter Campaign plan: {exc}") from exc
    error = _result_error(result)
    if error:
        raise ValueError(f"Invalid Winter Campaign plan: {error}")
    if not result.get("executed"):
        raise ValueError("Winter Campaign plan has no legal effect.")
    return used


def resolve_winter_campaign(state, owner, card_id):
    """Resolve paid actions, querying a human again after each single action."""
    remaining, results, errors = 2, [], []
    while remaining:
        player = owner not in state.get("non_player_factions", set())
        request = {
            "kind": "winter_campaign", "card_id": card_id,
            "remaining_actions": remaining,
        }
        if errors:
            request["errors"] = errors
        plan = consult_agent(state, owner, request) if player else None
        uses_bot = plan is None
        if uses_bot:
            plan = _bot_plan(state, owner, remaining)
            used = validate_plan(state, owner, plan, remaining)
        else:
            try:
                used = validate_human_plan(state, owner, plan, remaining)
            except ValueError as exc:
                errors = [str(exc)]
                continue
        if used == 0:
            break
        result = _execute_plan(state, owner, plan, uses_bot=uses_bot)
        results.append({"plan": plan, "actions": used, "result": result})
        remaining -= used
        errors = []
    return {"owner": owner, "card_id": card_id, "actions": results,
            "remaining_actions": remaining,
            "result": {"executed": any(e["result"].get("executed") for e in results)}}


def winter_campaign_after_harvest(state):
    """Return the active card's result, or None if there is no eligible owner."""
    from fs_bot.cards.capabilities import is_capability_active, get_capability_owner
    # A Scenario - The Gallic War, Lingering Events: A63 remains in effect
    # after the Interlude changes the current rules to the base game.
    cards = (("A63", 63) if state["scenario"] in ARIOVISTUS_SCENARIOS
             or state.get("interlude_completed") else (63,))
    for card_id in cards:
        if is_capability_active(state, card_id, EVENT_SHADED):
            owner = get_capability_owner(state, card_id)
            if owner is not None and owner != ROMANS:
                from fs_bot.engine.game_engine import get_sop_factions
                if owner not in get_sop_factions(state):
                    # The sources preserve Germanic capabilities in place but
                    # do not transfer their ownership to the new Arverni seat.
                    # Keep that unresolved owner's existing behavior (no
                    # player activation), without silently reassigning A63.
                    # See QUESTIONS.md: German-owned A63 after the Interlude.
                    continue
                return resolve_winter_campaign(state, owner, card_id)
    return None
