"""Card Reference 4: the marker ends when no physical Romans remain."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (place_piece, remove_piece, move_piece,
                                 count_pieces, PieceError)
from fs_bot.cards.circumvallation import place_marker
from fs_bot.state.serialize import encode, decode
from fs_bot.state.state_schema import build_initial_state, validate_state

R = rc.MANDUBII
D = rc.SEQUANI


def board(scenario=rc.SCENARIO_GREAT_REVOLT, representation=dict):
    state = build_initial_state(scenario, seed=41)
    place_piece(state, R, rc.ARVERNI, rc.CITADEL)
    place_piece(state, R, rc.ARVERNI, rc.WARBAND, 4, piece_state=rc.REVEALED)
    place_piece(state, R, rc.ROMANS, rc.AUXILIA)
    assert place_marker(state, R)
    if representation is set:
        state['markers'][R] = {rc.MARKER_CIRCUMVALLATION, rc.MARKER_RAZED}
    else:
        state['markers'][R][rc.MARKER_RAZED] = True
    assert not validate_state(state)
    return state


def marked(state):
    return rc.MARKER_CIRCUMVALLATION in state['markers'][R]


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
@pytest.mark.parametrize('representation', [dict, set])
@pytest.mark.parametrize('operation', ['remove', 'move'])
def test_last_roman_ends_marker_in_every_scenario(scenario, representation, operation):
    state = board(scenario, representation)
    if operation == 'remove':
        remove_piece(state, R, rc.ROMANS, rc.AUXILIA)
    else:
        move_piece(state, R, D, rc.ROMANS, rc.AUXILIA)
    assert not marked(state)
    assert rc.MARKER_RAZED in state['markers'][R]
    assert count_pieces(state, R, rc.ARVERNI, rc.WARBAND) == 4
    assert count_pieces(state, R, rc.ARVERNI, rc.CITADEL) == 1
    assert not validate_state(state)


@pytest.mark.parametrize('piece,kwargs', [
    (rc.AUXILIA, {'piece_state': rc.HIDDEN}),
    (rc.AUXILIA, {'piece_state': rc.REVEALED}),
    (rc.AUXILIA, {'piece_state': rc.SCOUTED}),
    (rc.LEGION, {'from_legions_track': True}),
    (rc.FORT, {}), (rc.ALLY, {}),
    (rc.LEADER, {'leader_name': rc.CAESAR}),
])
def test_every_kind_of_resident_roman_keeps_marker(piece, kwargs):
    state = board()
    place_piece(state, R, rc.ROMANS, piece, **kwargs)
    remove_piece(state, R, rc.ROMANS, rc.AUXILIA, piece_state=rc.HIDDEN)
    assert marked(state)
    removal = {'piece_state': kwargs['piece_state']} if 'piece_state' in kwargs else {}
    remove_piece(state, R, rc.ROMANS, piece, **removal)
    assert not marked(state)
    assert not validate_state(state)


def test_returning_romans_do_not_resurrect_marker():
    state = board()
    move_piece(state, R, D, rc.ROMANS, rc.AUXILIA)
    move_piece(state, D, R, rc.ROMANS, rc.AUXILIA)
    assert not marked(state)
    assert count_pieces(state, R, rc.ROMANS, rc.AUXILIA) == 1


def test_failure_and_zero_count_leave_marker_unchanged():
    state = board()
    before = encode(state)
    with pytest.raises(PieceError):
        remove_piece(state, R, rc.ROMANS, rc.AUXILIA, 2)
    assert encode(state) == before
    with pytest.raises(PieceError):
        move_piece(state, R, D, rc.ROMANS, rc.AUXILIA, 2)
    assert encode(state) == before
    remove_piece(state, R, rc.ROMANS, rc.AUXILIA, 0)
    assert encode(state) == before


def test_other_faction_departure_preserves_physical_roman_presence():
    state = board()
    place_piece(state, R, rc.AEDUI, rc.WARBAND, piece_state=rc.REVEALED)
    move_piece(state, R, D, rc.AEDUI, rc.WARBAND, piece_state=rc.REVEALED)
    assert marked(state)


def test_deterministic_round_trip_then_departure():
    state = board()
    resumed = decode(encode(deepcopy(state)))
    for current in (state, resumed):
        move_piece(current, R, D, rc.ROMANS, rc.AUXILIA)
        assert not marked(current)
    assert encode(state) == encode(resumed)


def test_actual_battle_casualty_clears_marker():
    from fs_bot.battle.resolve import resolve_battle
    state = board()
    result = resolve_battle(state, R, rc.ARVERNI, rc.ROMANS,
                            retreat_declaration=False)
    assert result
    assert count_pieces(state, R, rc.ROMANS) == 0
    assert not marked(state)
    assert not validate_state(state)


def test_actual_march_clears_marker_after_last_group_leaves():
    from fs_bot.commands.march import march_group
    state = board()
    march_group(state, rc.ROMANS, R, [D],
                {rc.AUXILIA: 1, rc.LEGION: 0, rc.WARBAND: 0, rc.LEADER: None}, free=True)
    assert count_pieces(state, R, rc.ROMANS) == 0
    assert not marked(state)
    assert not validate_state(state)


def test_interlude_tolerates_marker_already_cleared_by_roman_removal():
    from fs_bot.engine.interlude import _step0_circumvallation
    state = board()
    result = _step0_circumvallation(state)
    assert result['regions_cleared'] == [R]
    assert not marked(state)
    # Exact marked-only removal is deliberately not asserted: it is still open.
    assert not validate_state(state)


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
def test_quarters_preview_is_detached_and_accepted_step_commits_marker_effects(scenario):
    from fs_bot.engine.quarters import apply_relocations, preview_relocations
    state = board(scenario)
    place_piece(state, D, rc.ROMANS, rc.AUXILIA, 2)
    moves = [(rc.AUXILIA, R, D, 1)]
    before = encode(state)
    preview = preview_relocations(state, rc.ROMANS, moves)
    assert not marked(preview)
    assert encode(state) == before
    apply_relocations(state, rc.ROMANS, moves)
    assert count_pieces(state, R, rc.ROMANS) == 0
    assert not marked(state)
    assert rc.MARKER_RAZED in state['markers'][R]
    assert not validate_state(state)
