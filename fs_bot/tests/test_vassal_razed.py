"""Rules regressions prompted by the Vassal module's Razed handling.

The expected results come from Card Reference 23 and §§6.6/7.2/7.3,
not the module's implementation. Sacking permanently Disperses its City.
"""

from copy import deepcopy

import pytest

from fs_bot.board.pieces import place_piece, remove_piece
from fs_bot.cards.card_effects import execute_card_23
from fs_bot.engine.victory import (
    calculate_victory_margin,
    calculate_victory_score,
)
from fs_bot.engine.winter import spring_phase
from fs_bot.rules_consts import (
    AEDUI, AMBIORIX, AUXILIA, BASE_SCENARIOS, BELGAE, BITURIGES,
    CITY_AVARICUM, LEADER,
    MARKER_DISPERSED, MARKER_DISPERSED_GATHERING, MARKER_RAZED,
    ROMANS, SCENARIO_PAX_GALLICA, TREVERI, TRIBE_BITURIGES, WARBAND,
)
from fs_bot.state.state_schema import build_initial_state


def _raze_avaricum(scenario, initial_status=None):
    state = build_initial_state(scenario, seed=29)
    place_piece(state, BITURIGES, ROMANS, AUXILIA)
    state["tribes"][TRIBE_BITURIGES]["status"] = initial_status
    state["event_params"] = {"target_city": CITY_AVARICUM}
    execute_card_23(state)
    return state


@pytest.mark.parametrize("scenario", BASE_SCENARIOS)
@pytest.mark.parametrize(
    "initial_status", [None, MARKER_DISPERSED, MARKER_DISPERSED_GATHERING]
)
def test_sacking_razed_city_retains_roman_victory_credit(scenario, initial_status):
    """Card23/§7.2: replacing Subdued or Dispersed still counts one tribe."""
    state = _raze_avaricum(scenario, initial_status)
    assert state["tribes"][TRIBE_BITURIGES]["status"] == MARKER_RAZED
    before = deepcopy(state)

    # Every tribe in this otherwise empty fixture counts for Rome: 30 total.
    assert calculate_victory_score(state, ROMANS) == 30
    assert calculate_victory_margin(state, ROMANS) == 15
    assert state["tribes"] == before["tribes"]
    assert state["spaces"] == before["spaces"]
    assert state["resources"] == before["resources"]
    assert state["rng"].getstate() == before["rng"].getstate()


@pytest.mark.parametrize("scenario", BASE_SCENARIOS)
@pytest.mark.parametrize("new_owner", [BELGAE, ROMANS, AEDUI])
def test_razed_city_contributes_no_belgic_control_value(scenario, new_owner):
    """Card23/§7.2: subtract Razed only inside Belgic-Controlled Regions."""
    state = _raze_avaricum(scenario)
    remove_piece(state, BITURIGES, ROMANS, AUXILIA)
    piece_type = AUXILIA if new_owner == ROMANS else WARBAND
    place_piece(state, BITURIGES, new_owner, piece_type)
    place_piece(state, TREVERI, BELGAE, WARBAND)

    # Treveri contributes 1. Bituriges' only tribe is Razed, so it adds
    # nothing even when the Belgae Control it; another owner's Razed City
    # must not reduce the unrelated Treveri contribution either.
    assert calculate_victory_score(state, BELGAE) == 1
    assert calculate_victory_margin(state, BELGAE) == -14
    assert calculate_victory_score(state, ROMANS) == 30


def test_spring_retains_razed_status_and_its_victory_effects():
    """Card23/§6.6: Spring leaves permanent Dispersal and its scores intact."""
    state = _raze_avaricum(SCENARIO_PAX_GALLICA)
    remove_piece(state, BITURIGES, ROMANS, AUXILIA)
    place_piece(state, BITURIGES, BELGAE, WARBAND, count=2)
    # Keep Spring from introducing a Belgic Successor in a different Home
    # Region, which would add unrelated Control Value to this fixture.
    place_piece(state, BITURIGES, BELGAE, LEADER, leader_name=AMBIORIX)

    spring_phase(state)

    assert state["tribes"][TRIBE_BITURIGES]["status"] == MARKER_RAZED
    assert calculate_victory_score(state, ROMANS) == 30
    assert calculate_victory_score(state, BELGAE) == 0
