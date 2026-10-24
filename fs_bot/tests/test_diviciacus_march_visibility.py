"""Card 38/A1.4 cooperation preserves the physical Scout marker (§4.2.2)."""

from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces_by_state, place_piece
from fs_bot.cards.card_effects import execute_event
from fs_bot.commands.march import march_from_origin
from fs_bot.engine.diviciacus import force_scope
from fs_bot.state.state_schema import build_initial_state, validate_state


def _state(leader):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS if leader
                                else rc.SCENARIO_GREAT_REVOLT, seed=11)
    state['non_player_factions'] = set()
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA,
                piece_state=rc.REVEALED)
    place_piece(state, rc.MORINI, rc.AEDUI, rc.WARBAND,
                piece_state=rc.REVEALED)
    place_piece(state, rc.MORINI, rc.AEDUI, rc.WARBAND,
                piece_state=rc.SCOUTED)
    if leader:
        place_piece(state, rc.MORINI, rc.AEDUI, rc.LEADER,
                    leader_name=rc.DIVICIACUS)
    else:
        execute_event(state, 38)
    return state


@pytest.mark.parametrize('leader', [False, True])
def test_roman_march_clears_borrowed_scout_marker_without_hiding_piece(leader):
    state = _state(leader)
    pools = deepcopy(state['available'])
    with force_scope(state, rc.ROMANS, [rc.MORINI]):
        result = march_from_origin(state, rc.ROMANS, rc.MORINI,
            [({rc.AUXILIA: 3}, [rc.NERVII])])
    assert result['flip_result'] == {'flipped_to_hidden': 2,
                                     'scouted_to_revealed': 1}
    assert count_pieces_by_state(state, rc.NERVII, rc.AEDUI, rc.WARBAND,
                                 rc.SCOUTED) == 0
    assert count_pieces_by_state(state, rc.NERVII, rc.AEDUI, rc.WARBAND,
                                 rc.REVEALED) == 1
    assert count_pieces_by_state(state, rc.NERVII, rc.AEDUI, rc.WARBAND,
                                 rc.HIDDEN) == 1
    assert count_pieces_by_state(state, rc.NERVII, rc.ROMANS, rc.AUXILIA,
                                 rc.HIDDEN) == 1
    assert state['available'] == pools
    assert validate_state(state) == []


@pytest.mark.parametrize('leader', [False, True])
def test_borrowed_pieces_that_stay_at_origin_also_clear_scout_marker(leader):
    state = _state(leader)
    state['decision_agent'] = lambda s, f, request: (
        {'counts': {rc.ROMANS: 1}} if request['kind'] == 'diviciacus_pieces'
        else None)
    with force_scope(state, rc.ROMANS, [rc.MORINI]):
        march_from_origin(state, rc.ROMANS, rc.MORINI,
            [({rc.AUXILIA: 1}, [rc.NERVII])])
    assert count_pieces_by_state(state, rc.MORINI, rc.AEDUI, rc.WARBAND,
                                 rc.SCOUTED) == 0
    assert count_pieces_by_state(state, rc.MORINI, rc.AEDUI, rc.WARBAND,
                                 rc.REVEALED) == 1
    assert count_pieces_by_state(state, rc.MORINI, rc.AEDUI, rc.WARBAND,
                                 rc.HIDDEN) == 1
    assert count_pieces_by_state(state, rc.NERVII, rc.ROMANS, rc.AUXILIA,
                                 rc.HIDDEN) == 1
    assert validate_state(state) == []
