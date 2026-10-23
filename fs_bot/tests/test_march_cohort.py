"""§3.2.2/3.3.2 move and Harass the original group, never resident troops."""

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (
    count_pieces_by_state, get_leader_in_region, place_piece, remove_piece,
)
from fs_bot.commands import march
from fs_bot.engine import execute as ex
from fs_bot.state.state_schema import build_initial_state, validate_state


def board():
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=3)
    place_piece(state, rc.MORINI, rc.ARVERNI, rc.LEADER,
                leader_name=rc.VERCINGETORIX)
    place_piece(state, rc.MORINI, rc.ARVERNI, rc.WARBAND, 2,
                piece_state=rc.SCOUTED)
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.WARBAND, 3,
                piece_state=rc.HIDDEN)
    return state


def visibility(state, region, faction=rc.ARVERNI, piece=rc.WARBAND):
    return tuple(count_pieces_by_state(state, region, faction, piece, ps)
                 for ps in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED))


@pytest.mark.parametrize("losses", [0, 1, 2])
def test_scouted_group_retains_its_visibility_and_residents_through_harassment(losses):
    """Scouted→Revealed at origin; only those departing WB suffer Losses."""
    state = board()
    if losses:
        place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, 3 * losses)
    final = ex._march_with_harassment(
        state, rc.ARVERNI, rc.MORINI, [rc.NERVII, rc.ATREBATES],
        harassers_by_region={rc.NERVII: [(rc.ROMANS, 3 * losses)]})
    assert final == rc.ATREBATES
    assert visibility(state, rc.MORINI) == (0, 0, 0)
    assert visibility(state, rc.NERVII) == (3, 0, 0)
    assert visibility(state, rc.ATREBATES) == (0, 2 - losses, 0)
    assert get_leader_in_region(state, rc.ATREBATES, rc.ARVERNI) == rc.VERCINGETORIX
    assert validate_state(state) == []


def test_mechanical_multihop_march_preserves_original_group_visibility():
    """The public per-origin mechanic also carries one group through its route."""
    state = board()
    group = {rc.LEADER: rc.VERCINGETORIX, rc.WARBAND: 2}
    march.march_from_origin(state, rc.ARVERNI, rc.MORINI,
                            [(group, [rc.NERVII, rc.ATREBATES])])
    assert visibility(state, rc.NERVII) == (3, 0, 0)
    assert visibility(state, rc.ATREBATES) == (0, 2, 0)
    assert validate_state(state) == []


def test_subset_group_uses_own_visibility_for_np_loss_priority():
    """§8.4.1 moves Hidden first but takes own Losses in reverse order."""
    state = board()
    place_piece(state, rc.MORINI, rc.ARVERNI, rc.WARBAND, 1)
    ex._march_with_harassment(
        state, rc.ARVERNI, rc.MORINI, [rc.NERVII, rc.ATREBATES],
        group_cap={rc.LEADER: True, rc.WARBAND: 2},
        harassers_by_region={rc.NERVII: [(rc.ROMANS, 3)]})
    assert visibility(state, rc.MORINI) == (0, 1, 0)
    assert visibility(state, rc.NERVII) == (3, 0, 0)
    assert visibility(state, rc.ATREBATES) == (1, 0, 0)
    assert validate_state(state) == []


def test_dropoffs_leave_the_carried_cohort_before_harassment():
    """§3.2.2 excludes dropped pieces as well as residents from Losses."""
    state = board()
    place_piece(state, rc.MORINI, rc.ARVERNI, rc.WARBAND, 3)
    ex._march_with_harassment(
        state, rc.ARVERNI, rc.MORINI, [rc.NERVII, rc.ATREBATES],
        dropoffs_by_region={rc.NERVII: {rc.WARBAND: 1}},
        harassers_by_region={rc.NERVII: [(rc.ROMANS, 3)]})
    assert visibility(state, rc.NERVII) == (4, 0, 0)
    assert visibility(state, rc.ATREBATES) == (2, 1, 0)
    assert validate_state(state) == []


def test_empty_carried_group_does_not_move_residents_or_continue_route():
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=3)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 1)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, 3,
                piece_state=rc.REVEALED)
    final = ex._march_with_harassment(
        state, rc.ROMANS, rc.MORINI, [rc.NERVII, rc.ATREBATES],
        harassers_by_region={rc.NERVII: [(rc.ARVERNI, 3)]})
    assert final == rc.NERVII
    assert visibility(state, rc.NERVII, rc.ROMANS, rc.AUXILIA) == (0, 3, 0)
    assert visibility(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == (0, 0, 0)
    assert validate_state(state) == []


def test_surviving_caesar_still_grants_third_hop():
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=3)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 2)
    final = ex._march_with_harassment(
        state, rc.ROMANS, rc.MORINI, [rc.NERVII, rc.ATREBATES, rc.MANDUBII],
        harassers_by_region={rc.NERVII: [], rc.ATREBATES: []})
    assert final == rc.MANDUBII
    assert visibility(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == (2, 0, 0)
    assert get_leader_in_region(state, rc.MANDUBII, rc.ROMANS) == rc.CAESAR
    assert validate_state(state) == []


@pytest.mark.parametrize("faction,leader,path,expected", [
    (rc.ARVERNI, rc.VERCINGETORIX, [rc.NERVII, rc.ATREBATES], rc.NERVII),
    (rc.ROMANS, rc.CAESAR, [rc.NERVII, rc.ATREBATES, rc.MANDUBII], rc.ATREBATES),
])
def test_lost_leader_cannot_grant_an_extra_step_to_survivors(
        monkeypatch, faction, leader, path, expected):
    """§3.2.2/3.3.2's extra step requires pieces still moving with the Leader."""
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=3)
    piece = rc.AUXILIA if faction == rc.ROMANS else rc.WARBAND
    place_piece(state, rc.MORINI, faction, rc.LEADER, leader_name=leader)
    place_piece(state, rc.MORINI, faction, piece, 2)

    # Isolate the executor after a legal player choice to roll for the
    # Leader and lose him. Typed loss-choice integration is tested separately.
    harassed = []
    def leader_casualty(state, region, faction, group, **kwargs):
        harassed.append(region)
        remove_piece(state, region, faction, rc.LEADER)
        group[rc.LEADER] = None

    monkeypatch.setattr(march, "resolve_harassment", leader_casualty)
    final = ex._march_with_harassment(
        state, faction, rc.MORINI, path,
        harassers_by_region={rc.NERVII: [(rc.BELGAE, 3)],
                            rc.ATREBATES: [(rc.BELGAE, 3)]})
    assert final == expected
    # After losing Caesar's extra step, the second Region is now the final
    # stop. Its residents cannot Harass pieces that will not depart it.
    assert harassed == [rc.NERVII]
    assert visibility(state, expected, faction, piece) == (2, 0, 0)
    assert visibility(state, path[-1], faction, piece) == (0, 0, 0)
    assert validate_state(state) == []
