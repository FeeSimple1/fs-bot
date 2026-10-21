"""A37 Aedui Event instruction: place Allies, but move no pieces."""
from collections import Counter
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import place_piece, count_pieces, get_leader_in_region
from fs_bot.engine.execute import _execute_event, _resolve_card_A37_move
from fs_bot.state.state_schema import build_initial_state
from fs_bot.tools.error_census import play_game, census_result


@pytest.mark.parametrize('scenario', [rc.SCENARIO_ARIOVISTUS, rc.SCENARIO_GALLIC_WAR])
def test_np_aedui_actual_a37_places_ally_but_does_not_move_adjacent_force(scenario):
    state = build_initial_state(scenario, seed=3)
    state['non_player_factions'] = {rc.AEDUI}
    state['current_card'] = 'A37'
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 4)
    place_piece(state, rc.NERVII, rc.AEDUI, rc.WARBAND, 4)
    place_piece(state, rc.NERVII, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    refresh_all_control(state)
    result = _execute_event(state, rc.AEDUI, {'command': 'Event', 'details': {
        'card_id': 'A37', 'text_preference': rc.EVENT_UNSHADED}})
    assert result['executed']
    assert state['tribes'][rc.TRIBE_TREVERI]['allied_faction'] == rc.AEDUI
    assert count_pieces(state, rc.TREVERI, rc.AEDUI, rc.ALLY) == 1
    assert count_pieces(state, rc.NERVII, rc.AEDUI, rc.WARBAND) == 4
    assert get_leader_in_region(state, rc.NERVII, rc.AEDUI) == rc.DIVICIACUS
    assert count_pieces(state, rc.TREVERI, rc.AEDUI, rc.WARBAND) == 0
    assert result['free_actions'][0]['declined_no_effect']
    counts, examples, occurrences = Counter(), {}, []
    census_result({'card_results': [{'card': 'A37', 'turn_result': {
        'actions_taken': {rc.AEDUI: {'bot_action': {'command': 'Event'}, 'execution': result}}
    }}]}, counts, examples, scenario, 3, occurrences)
    assert [row['severity'] for row in occurrences] == ['legal-decline']


def test_np_instruction_does_not_control_a_human_aedui_choice():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=3)
    state['non_player_factions'] = {rc.GERMANS, rc.BELGAE, rc.ROMANS}
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 4)
    place_piece(state, rc.TREVERI, rc.AEDUI, rc.ALLY)
    state['tribes'][rc.TRIBE_TREVERI]['allied_faction'] = rc.AEDUI
    refresh_all_control(state)
    before = deepcopy(state['spaces'])
    result = _resolve_card_A37_move(state, rc.AEDUI)
    assert 'Aedui Event instruction' not in result[0].get('reason', '')
    assert state['spaces'] == before


@pytest.mark.parametrize('scenario', [rc.SCENARIO_ARIOVISTUS, rc.SCENARIO_GALLIC_WAR])
def test_seed3_a37_refusal_is_a_legal_partial_event(scenario):
    # Exact pair from the combined 50-game census; fix the decision, not the
    # census severity table. The Ally placement remains an executed Event.
    game = play_game(scenario, 3)
    records = [record for card in game['card_results'] if card.get('card') == 'A37'
               for faction, record in (card.get('turn_result', {}).get('actions_taken') or {}).items()
               if faction == rc.AEDUI and record.get('execution', {}).get('command') == 'Event']
    assert len(records) == 1
    result = records[0]['execution']
    assert result['executed']
    assert result['free_actions'][0]['declined_no_effect']
    counts, examples, occurrences = Counter(), {}, []
    census_result(game, counts, examples, scenario, 3, occurrences)
    a37 = [row for row in occurrences if row['card'] == 'A37' and row['faction'] == rc.AEDUI]
    assert a37 and all(row['severity'] == 'legal-decline' for row in a37)
    assert not any(row['message'] == 'no adjacent group to move' for row in a37)
