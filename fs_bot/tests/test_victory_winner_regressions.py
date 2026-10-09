"""Victory Phase winners follow §7.1 / A7.1, not threshold-order ties."""

import pytest

from fs_bot.board.pieces import place_piece
from fs_bot.engine.victory import calculate_victory_margin, check_any_victory
from fs_bot.engine.winter import victory_phase
from fs_bot.rules_consts import (
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS, ALLY,
    SCENARIO_PAX_GALLICA, SCENARIO_ARIOVISTUS,
    TRIBE_AEDUI, TRIBE_SEQUANI, TRIBE_HELVETII, TRIBE_BITURIGES,
    TRIBE_MANDUBII, TRIBE_LINGONES,
    TRIBE_ARVERNI, TRIBE_CADURCI, TRIBE_VOLCAE, TRIBE_PICTONES,
    TRIBE_MENAPII, TRIBE_MORINI, TRIBE_EBURONES, TRIBE_NERVII,
    TRIBE_TO_REGION,
)
from fs_bot.state.state_schema import build_initial_state, validate_state


def _simultaneous_victory_state(scenario, *, tied=False):
    """14 non-Roman allies leave Rome at +1; Aedui have +2 (or +1)."""
    state = build_initial_state(scenario, seed=42)
    state["non_player_factions"] = set()
    allies = {
        AEDUI: (TRIBE_AEDUI, TRIBE_SEQUANI, TRIBE_HELVETII,
                TRIBE_BITURIGES, TRIBE_MANDUBII),
        ARVERNI: (TRIBE_ARVERNI, TRIBE_CADURCI, TRIBE_VOLCAE,
                  TRIBE_PICTONES),
        BELGAE: (TRIBE_MENAPII, TRIBE_MORINI, TRIBE_EBURONES,
                 TRIBE_NERVII),
    }
    sixth_ally_faction = GERMANS if tied else AEDUI
    allies[sixth_ally_faction] = (
        *allies.get(sixth_ally_faction, ()), TRIBE_LINGONES)
    for faction, tribes in allies.items():
        for tribe in tribes:
            place_piece(state, TRIBE_TO_REGION[tribe], faction, ALLY)
            state["tribes"][tribe]["allied_faction"] = faction
    assert validate_state(state) == []
    assert calculate_victory_margin(state, ROMANS) == 1
    assert calculate_victory_margin(state, AEDUI) == (1 if tied else 2)
    return state


@pytest.mark.parametrize("scenario", [SCENARIO_PAX_GALLICA,
                                     SCENARIO_ARIOVISTUS])
def test_higher_player_margin_wins_when_both_pass_victory_check(scenario):
    """§7.1: Rome's earlier tiebreak position cannot beat Aedui's +2."""
    state = _simultaneous_victory_state(scenario)

    result = victory_phase(state)

    assert result["game_over"] is True
    assert result["winner"] == AEDUI
    assert result["rankings"][0] == (AEDUI, 2)


@pytest.mark.parametrize("scenario", [SCENARIO_PAX_GALLICA,
                                     SCENARIO_ARIOVISTUS])
def test_equal_player_margins_still_use_faction_tiebreak(scenario):
    """§7.1 / A7.1: Rome wins the actual +1/+1 tie."""
    state = _simultaneous_victory_state(scenario, tied=True)

    assert check_any_victory(state) == ROMANS


@pytest.mark.parametrize("scenario", [SCENARIO_PAX_GALLICA,
                                     SCENARIO_ARIOVISTUS])
def test_non_player_victory_defeats_higher_player_margin(scenario):
    """§7.1: a Non-player passing its check makes all players lose."""
    state = _simultaneous_victory_state(scenario)
    state["non_player_factions"] = {ROMANS}

    assert victory_phase(state)["winner"] == ROMANS
