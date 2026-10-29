"""
Bot dispatch — Route NP faction turns to the correct bot module.

Enforces scenario isolation per CLAUDE.md:
- German bot never called in base game (Germans are game-run via §6.2).
- Arverni bot never called in Ariovistus (Arverni are game-run via A6.2).
"""

from fs_bot.rules_consts import (
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
)


class BotDispatchError(Exception):
    """Raised when dispatch encounters an invalid faction/scenario combination."""
    pass


def _get_bot_factions(scenario):
    """Return which factions can be bot-controlled in a scenario.

    Base game: Romans, Arverni, Aedui, Belgae (NOT Germans — §6.2).
    Ariovistus: Romans, Germans, Aedui, Belgae (NOT Arverni — A6.2).

    Args:
        scenario: Scenario constant.

    Returns:
        Tuple of faction constants that can be NP in this scenario.
    """
    if scenario in ARIOVISTUS_SCENARIOS:
        return (ROMANS, GERMANS, AEDUI, BELGAE)
    return (ROMANS, ARVERNI, AEDUI, BELGAE)


def dispatch_bot_turn(state, faction):
    """Route a Non-Player faction's turn to the correct bot module.

    Args:
        state: Game state dict.
        faction: Faction constant — the NP faction taking its turn.

    Returns:
        Action dict from the bot module.

    Raises:
        BotDispatchError: If the faction cannot be bot-controlled in this
            scenario, or if no bot module is implemented for it yet.
    """
    scenario = state["scenario"]
    valid_factions = _get_bot_factions(scenario)

    # Scenario isolation assertions
    if faction == GERMANS and scenario in BASE_SCENARIOS:
        raise BotDispatchError(
            f"Germans cannot be bot-controlled in base game scenario "
            f"'{scenario}'. Germans are game-run via §6.2."
        )

    if faction == ARVERNI and scenario in ARIOVISTUS_SCENARIOS:
        raise BotDispatchError(
            f"Arverni cannot be bot-controlled in Ariovistus scenario "
            f"'{scenario}'. Arverni are game-run via A6.2."
        )

    if faction not in valid_factions:
        raise BotDispatchError(
            f"Faction '{faction}' is not a valid bot faction in scenario "
            f"'{scenario}'. Valid: {valid_factions}"
        )

    # Verify faction is actually marked as a Non-Player
    non_players = state.get("non_player_factions", set())
    if faction not in non_players:
        raise BotDispatchError(
            f"Faction '{faction}' is not marked as a Non-Player in state. "
            f"Current NPs: {non_players}"
        )

    from fs_bot.engine.diviciacus_planning import plan_with_diviciacus

    # Dispatch to the appropriate bot module
    if faction == ROMANS:
        from fs_bot.bots.roman_bot import execute_roman_turn, node_r_recruit
        from fs_bot.engine.recruit_planning import plan_with_recruit_supply, REQUESTS
        from fs_bot.rules_consts import CMD_RECRUIT
        action = plan_with_diviciacus(state, faction, execute_roman_turn)
        if (action.get('command') == CMD_RECRUIT
                or REQUESTS in (action.get('details') or {})):
            # Confirm this process before its SA/effects, retaining earlier
            # flowchart decisions. A refused Recruit falls through to Seize;
            # it does not rerun R1 or change other Commands' live callbacks.
            return plan_with_recruit_supply(
                state, lambda planning: plan_with_diviciacus(
                    planning, faction, node_r_recruit))
        return action

    if faction == BELGAE:
        from fs_bot.bots.belgae_bot import execute_belgae_turn
        return execute_belgae_turn(state)

    if faction == AEDUI:
        from fs_bot.bots.aedui_bot import execute_aedui_turn
        return plan_with_diviciacus(state, faction, execute_aedui_turn)

    if faction == ARVERNI:
        from fs_bot.bots.arverni_bot import execute_arverni_turn
        return execute_arverni_turn(state)

    if faction == GERMANS:
        from fs_bot.bots.german_bot import execute_german_turn
        return execute_german_turn(state)

    raise BotDispatchError(f"Unknown faction: {faction}")
