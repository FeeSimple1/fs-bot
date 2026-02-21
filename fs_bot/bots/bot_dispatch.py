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

    # Dispatch to the appropriate bot module
    if faction == ROMANS:
        from fs_bot.bots.roman_bot import execute_roman_turn
        return execute_roman_turn(state)

    # Placeholder stubs for unimplemented bots
    if faction == BELGAE:
        raise BotDispatchError(
            f"Belgae bot not yet implemented. See BUILD_PLAN.md Phase C."
        )

    if faction == AEDUI:
        raise BotDispatchError(
            f"Aedui bot not yet implemented. See BUILD_PLAN.md Phase C."
        )

    if faction == ARVERNI:
        from fs_bot.bots.arverni_bot import execute_arverni_turn
        return execute_arverni_turn(state)

    if faction == GERMANS:
        raise BotDispatchError(
            f"German bot not yet implemented. See BUILD_PLAN.md Phase C."
        )

    raise BotDispatchError(f"Unknown faction: {faction}")
