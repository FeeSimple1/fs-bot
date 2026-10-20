"""Senate row geometry from the board, governed by §6.5.2 / A6.5.2.

The board in FallingSky4.0.0.vmod aligns the Legion rows with the Senate:
Top/Uproar, Middle/Intrigue, Bottom/Adulation. Its XML places those Legion
rows at y=1914, 2062, 2211 inside the respective Senate row y ranges.
See docs/reviews/vassal-module-2026-10-20.md for artifact hashes and evidence.
"""

from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece, remove_piece
from fs_bot.engine.winter import senate_phase
from fs_bot.state.state_schema import build_initial_state, validate_state


@pytest.mark.parametrize("scenario", rc.BASE_SCENARIOS)
@pytest.mark.parametrize(
    "position, expected_count, expected_track",
    [
        (rc.UPROAR, 4, (4, 4, 0)),
        (rc.INTRIGUE, 8, (4, 0, 0)),
        (rc.ADULATION, 12, (0, 0, 0)),
    ],
)
def test_6_5_2_board_rows_release_at_and_above_senate(
    scenario, position, expected_count, expected_track
):
    state = build_initial_state(scenario, seed=82)
    resources = deepcopy(state["resources"])
    eligibility = deepcopy(state["eligibility"])
    available = deepcopy(state["available"])
    rng_before = state["rng"].getstate()

    result = senate_phase(state, force_position=position)

    assert result["legions_placed"] == expected_count
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == expected_count
    assert tuple(state["legions_track"][row] for row in rc.LEGIONS_ROWS) == expected_track
    assert state["spaces"][rc.PROVINCIA]["control"] == rc.ROMAN_CONTROL
    assert state["resources"] == resources
    assert state["eligibility"] == eligibility
    assert state["available"] == available  # No Leader: no Senate Auxilia.
    assert state["rng"].getstate() == rng_before
    assert not validate_state(state)


@pytest.mark.parametrize("scenario", rc.ALL_SCENARIOS)
@pytest.mark.parametrize("position", (rc.UPROAR, rc.INTRIGUE))
def test_6_5_2_legions_below_senate_remain_unavailable(scenario, position):
    state = build_initial_state(scenario, seed=82)
    # Normal piece placement takes the topmost eight Legions, leaving the
    # Bottom four. Those four are below both Uproar and Intrigue.
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEGION, 8,
                from_legions_track=True)
    before = deepcopy(state["legions_track"])

    result = senate_phase(state, force_position=position)

    assert result["legions_placed"] == 0
    assert state["legions_track"] == before
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == 0
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.LEGION) == 8
    assert not validate_state(state)


@pytest.mark.parametrize("scenario", rc.ARIOVISTUS_SCENARIOS)
@pytest.mark.parametrize(
    "position, on_map_count, expected_count, expected_track",
    [
        # All four Top-row Legions are uncapped at every Senate position.
        (rc.UPROAR, 0, 4, (4, 4, 0)),
        (rc.INTRIGUE, 0, 6, (4, 2, 0)),
        (rc.ADULATION, 0, 6, (4, 2, 0)),
        # The two-Legion budget is shared by Middle and Bottom rows.
        (rc.INTRIGUE, 4, 2, (4, 2, 0)),
        (rc.ADULATION, 8, 2, (2, 0, 0)),
        (rc.ADULATION, 7, 2, (3, 0, 0)),
    ],
)
def test_A6_5_2_caps_lower_rows_together_without_capping_top_row(
    scenario, position, on_map_count, expected_count, expected_track
):
    state = build_initial_state(scenario, seed=82)
    if on_map_count:
        place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEGION, on_map_count,
                    from_legions_track=True)

    result = senate_phase(state, force_position=position)

    assert result["legions_placed"] == expected_count
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == expected_count
    assert tuple(state["legions_track"][row] for row in rc.LEGIONS_ROWS) == expected_track
    assert not validate_state(state)


def test_6_5_2_fallen_recover_to_bottom_then_release_at_adulation():
    state = build_initial_state(rc.SCENARIO_RECONQUEST, seed=82)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEGION, 12,
                from_legions_track=True)
    remove_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEGION, 5)
    assert state["fallen_legions"] == 5

    result = senate_phase(state, force_position=rc.ADULATION)

    assert result["legions_from_fallen"] == 3
    assert result["legions_placed"] == 3
    assert state["fallen_legions"] == 2
    assert sum(state["legions_track"].values()) == 0
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == 3
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.LEGION) == 7
    assert not validate_state(state)
