"""Sixth comparison audit: automatic Germanic Rally and March (§6.2)."""

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import calculate_control, is_controlled_by
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.commands.march import germans_phase_march
from fs_bot.commands.rally import germans_phase_rally
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state


def _position(seed=0):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=seed)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    state['non_player_factions'] = {rc.ARVERNI, rc.AEDUI, rc.BELGAE}
    return state


def _check_board(state):
    assert validate_state(state) == []
    assert check_structural_integrity(state) == []


@pytest.mark.parametrize('existing_ally', [False, True])
def test_rally_adds_one_ally_per_region_and_counts_existing_allies(existing_ally):
    state = _position(seed=1)
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, 2)
    place_piece(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, 1)
    if existing_ally:
        assert _ally_tribe(state, rc.TRIBE_SUGAMBRI, rc.GERMANS)
    _check_board(state)

    result = germans_phase_rally(state)

    assert result['allies_placed'] == [
        (rc.SUGAMBRI, rc.TRIBE_SUEBI_NORTH), (rc.TREVERI, rc.TRIBE_TREVERI),
    ]
    assert result['warbands_placed'][rc.SUGAMBRI] == 1 + existing_ally
    assert result['warbands_placed'][rc.TREVERI] == 1
    _check_board(state)


@pytest.mark.parametrize('visibility', [rc.HIDDEN, rc.SCOUTED])
def test_march_moves_the_original_group_instead_of_its_arrivals(visibility):
    state = _position()
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 5)
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, 3, piece_state=visibility)
    place_piece(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, 1)
    place_piece(state, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 1)
    _check_board(state)

    result = germans_phase_march(state)

    assert result['groups_moved'] == [(rc.UBII, rc.SUGAMBRI, 4), (rc.SUGAMBRI, rc.NERVII, 2)]
    assert count_pieces(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND) == 5
    # The two formerly Scouted originals remain Revealed after they move.
    # A live-stack selection would send the newly arrived Hidden Warbands.
    final_visibility = rc.REVEALED if visibility == rc.SCOUTED else rc.HIDDEN
    assert count_pieces_by_state(state, rc.NERVII, rc.GERMANS, rc.WARBAND, final_visibility) == 2
    assert count_pieces_by_state(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, rc.SCOUTED) == 0
    assert is_controlled_by(state, rc.UBII, rc.GERMANS)
    assert is_controlled_by(state, rc.SUGAMBRI, rc.GERMANS)
    _check_board(state)


def test_march_visibility_applies_once_even_where_warbands_stay():
    state = _position()
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND, 1, piece_state=rc.REVEALED)
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND, 1, piece_state=rc.SCOUTED)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 2)
    _check_board(state)

    result = germans_phase_march(state)

    assert result['groups_moved'] == []
    assert result['flipped_regions'] == [rc.CARNUTES]
    assert count_pieces_by_state(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND, rc.REVEALED) == 1
    assert count_pieces_by_state(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 1
    assert count_pieces_by_state(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND, rc.SCOUTED) == 0
    _check_board(state)


@pytest.mark.parametrize('human_romans,auxilia,destination', [
    (True, 1, rc.TREVERI),
    (False, 1, rc.SUGAMBRI),
    (True, 5, rc.SUGAMBRI),
])
def test_march_prefers_player_control_within_the_best_control_tier(human_romans, auxilia, destination):
    state = _position()
    if not human_romans:
        state['non_player_factions'].add(rc.ROMANS)
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 5)
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA, auxilia)
    _check_board(state)

    result = germans_phase_march(state)

    assert result['groups_moved'] == [(rc.UBII, destination, 4)]
    assert is_controlled_by(state, destination, rc.GERMANS)
    _check_board(state)


def test_march_prefers_player_control_when_no_destination_adds_german_control():
    state = _position()
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 5)
    assert _ally_tribe(state, rc.TRIBE_SUEBI_NORTH, rc.GERMANS)
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 5)
    _check_board(state)

    result = germans_phase_march(state)

    assert result['groups_moved'] == [(rc.UBII, rc.TREVERI, 4)]
    assert calculate_control(state, rc.TREVERI) == rc.NO_CONTROL
    _check_board(state)


def test_later_group_ranks_destinations_by_control_after_the_first_move():
    state = _position()
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 5)
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, 3)
    place_piece(state, rc.MORINI, rc.GERMANS, rc.WARBAND, 1)
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA, 1)
    _check_board(state)

    result = germans_phase_march(state)

    assert result['groups_moved'] == [(rc.UBII, rc.TREVERI, 4), (rc.SUGAMBRI, rc.NERVII, 2)]
    assert is_controlled_by(state, rc.TREVERI, rc.GERMANS)
    assert is_controlled_by(state, rc.NERVII, rc.GERMANS)
    _check_board(state)


def test_shaded_germanic_chieftains_uses_the_repaired_full_phase():
    state = _position()
    state['current_card'] = 17
    for region, count in ((rc.UBII, 5), (rc.SUGAMBRI, 3), (rc.TREVERI, 1), (rc.SEQUANI, 1)):
        place_piece(state, region, rc.GERMANS, rc.WARBAND, count)
    _check_board(state)

    result = execute_decision(state, rc.ROMANS, {'action': ACTION_EVENT, 'player_action': {
        'command': rc.FIRST_DID_EVENT,
        'details': {'card_id': 17, 'text_preference': rc.EVENT_SHADED},
    }})

    assert result['executed'], result
    grant, = result['free_actions']
    assert grant['executed'], grant
    phase = grant['result']
    allies = phase['rally']['allies_placed']
    assert set(allies[:2]) == {
        (rc.UBII, rc.TRIBE_SUEBI_SOUTH), (rc.SUGAMBRI, rc.TRIBE_SUEBI_NORTH),
    }
    assert {region for region, _ in allies} == {rc.SUGAMBRI, rc.UBII, rc.TREVERI, rc.SEQUANI}
    assert len(allies) == 4
    assert phase['rally']['warbands_placed'] == {
        rc.SUGAMBRI: 1, rc.UBII: 1, rc.TREVERI: 1, rc.SEQUANI: 1,
    }
    groups = phase['march']['groups_moved']
    assert [count for _, _, count in groups] == [6, 4, 2, 2]
    assert {origin: count for origin, _, count in groups} == {
        rc.UBII: 6, rc.SUGAMBRI: 4, rc.TREVERI: 2, rc.SEQUANI: 2,
    }
    _check_board(state)
