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
    planning.pop("_planning_free_command", None)
    plan = dispatch_bot_turn(planning, faction)
    if plan.get("command") in (None, "None", "Pass", "Event"):
        return {"decline": True}
    plan = copy.deepcopy(plan)
    if remaining == 1:
        plan["sa"] = "No SA"
        plan["sa_regions"] = []
    return plan


def resolve_winter_campaign(state, owner, card_id):
    """Resolve paid actions, querying a human again after each single action."""
    from fs_bot.engine.execute import (_execute_decision, _execute_sa,
                                       _apply_end_of_action_capabilities)
    remaining, results = 2, []
    while remaining:
        player = owner not in state.get("non_player_factions", set())
        plan = (consult_agent(state, owner, {
            "kind": "winter_campaign", "card_id": card_id,
            "remaining_actions": remaining,
        }) if player else None)
        uses_bot = plan is None
        if uses_bot:
            plan = _bot_plan(state, owner, remaining)
        used = validate_plan(state, owner, plan, remaining)
        if used == 0:
            break
        command = plan.get("command")
        if command in (None, "None"):
            result = _execute_sa(state, owner, plan) or {"executed": False}
            _apply_end_of_action_capabilities(state)
        else:
            # The card overrides normal Command/SA compatibility. Execute
            # the already validated structure directly, retaining normal
            # resource costs and the player's chosen before/after order.
            result = _execute_decision(
                state, owner, {"bot_action" if uses_bot else "player_action": plan})
        results.append({"plan": plan, "actions": used, "result": result})
        remaining -= used
    return {"owner": owner, "card_id": card_id, "actions": results,
            "remaining_actions": remaining,
            "result": {"executed": any(e["result"].get("executed") for e in results)}}


def winter_campaign_after_harvest(state):
    """Return the active card's result, or None if there is no eligible owner."""
    from fs_bot.cards.capabilities import is_capability_active, get_capability_owner
    cards = ("A63", 63) if state["scenario"] in ARIOVISTUS_SCENARIOS else (63,)
    for card_id in cards:
        if is_capability_active(state, card_id, EVENT_SHADED):
            owner = get_capability_owner(state, card_id)
            if owner is not None and owner != ROMANS:
                return resolve_winter_campaign(state, owner, card_id)
    return None
