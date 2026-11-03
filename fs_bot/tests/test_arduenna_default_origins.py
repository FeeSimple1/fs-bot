"""Card67 Tips: initial target-region pieces may March; arriving pieces may not."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, count_pieces_by_state
from fs_bot.cards.arduenna import default_march, march_request
from fs_bot.engine.diviciacus import force_scope
from fs_bot.engine.free_actions import execute_free_action_plan
from fs_bot.state.state_schema import build_initial_state, validate_state


@pytest.mark.parametrize('card', [67, 'A67'])
def test_default_march_may_choose_initial_target_force_over_smaller_outside_origin(card):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=6)
    state['non_player_factions'] = {rc.BELGAE}
    for visibility, number in ((rc.HIDDEN, 3), (rc.REVEALED, 1), (rc.SCOUTED, 1)):
        place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, number, piece_state=visibility)
    place_piece(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 2)
    action = default_march(state, rc.BELGAE)
    assert action['regions'] == [rc.NERVII]
    assert action['details']['march_plan']['groups'][rc.NERVII][rc.WARBAND] == 5
    result = execute_free_action_plan(state, rc.BELGAE, march_request(card), action)
    assert result['executed']
    assert count_pieces(state, rc.NERVII, rc.BELGAE, rc.WARBAND) == 0
    assert count_pieces(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND) == 2
    assert count_pieces_by_state(state, rc.TREVERI, rc.BELGAE, rc.WARBAND, rc.HIDDEN) == 4
    assert count_pieces_by_state(state, rc.TREVERI, rc.BELGAE, rc.WARBAND, rc.REVEALED) == 1
    assert validate_state(state) == []


@pytest.mark.parametrize('card', [67, 'A67'])
def test_default_never_marches_fresh_target_arrivals_as_a_second_original_group(card):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=6)
    state['non_player_factions'] = {rc.BELGAE}
    place_piece(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 5)
    place_piece(state, rc.SEQUANI, rc.BELGAE, rc.WARBAND, 2)
    action = default_march(state, rc.BELGAE)
    assert action['regions'] == [rc.ATREBATES, rc.SEQUANI]
    result = execute_free_action_plan(state, rc.BELGAE, march_request(card), action)
    assert result['executed']
    assert count_pieces(state, rc.NERVII, rc.BELGAE, rc.WARBAND) == 5
    assert count_pieces(state, rc.TREVERI, rc.BELGAE, rc.WARBAND) == 2
    assert validate_state(state) == []


def test_initial_target_force_snapshot_preserves_borrowed_physical_owners():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=38)
    state['non_player_factions'] = {rc.AEDUI, rc.ROMANS}
    place_piece(state, rc.NERVII, rc.AEDUI, rc.WARBAND, 3)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, 2, piece_state=rc.REVEALED)
    place_piece(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND, 4)
    available = deepcopy(state['available'])
    with force_scope(state, rc.AEDUI, [rc.NERVII]):
        action = default_march(state, rc.AEDUI)
        assert action['regions'] == [rc.NERVII]
        assert action['details']['march_plan']['groups'][rc.NERVII][rc.WARBAND] == 5
        result = execute_free_action_plan(state, rc.AEDUI, march_request(67), action)
    assert result['executed']
    assert count_pieces(state, rc.TREVERI, rc.AEDUI, rc.WARBAND) == 3
    assert count_pieces(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND) == 4
    assert state['available'] == available and validate_state(state) == []
