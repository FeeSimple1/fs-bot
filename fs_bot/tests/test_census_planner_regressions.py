"""Rules regressions found by the expanded 50-game diagnostics census."""
from collections import Counter

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, find_leader, place_piece
from fs_bot.bots.arverni_bot import node_v_march_threat
from fs_bot.engine.execute import _execute_event, _execute_march
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.error_census import census_result


def _state():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=1)
    state['non_player_factions'] = set()
    state['resources'][rc.ARVERNI] = 10
    return state


@pytest.mark.parametrize('leader,destination,route', [
    (rc.SUCCESSOR, rc.CARNUTES, [rc.CARNUTES]),
    (rc.VERCINGETORIX, rc.MORINI, [rc.ATREBATES, rc.MORINI]),
])
def test_threat_march_uses_actual_leader_range_and_moves_to_reachable_largest_force(
        leader, destination, route):
    # §3.3.2 gives only Vercingetorix a second step. §8.7.1 joins the
    # most Arverni reachable, so the Successor joins the smaller close force.
    state = _state()
    place_piece(state, rc.MANDUBII, rc.ARVERNI, rc.LEADER, leader_name=leader)
    place_piece(state, rc.MANDUBII, rc.ARVERNI, rc.WARBAND, 4)
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 2)
    place_piece(state, rc.MORINI, rc.ARVERNI, rc.WARBAND, 6)
    action = node_v_march_threat(state)
    assert action['details']['march_plan']['routes'][rc.MANDUBII] == route
    result = _execute_march(state, rc.ARVERNI, action)
    assert not result['errors']
    assert find_leader(state, rc.ARVERNI) == destination
    assert count_pieces(state, destination, rc.ARVERNI, rc.WARBAND) >= 6
    assert validate_state(state) == []


@pytest.mark.parametrize('leader,leader_region,ambush', [
    (rc.SUCCESSOR, rc.ATREBATES, False),
    (rc.SUCCESSOR, rc.MORINI, True),
    (rc.VERCINGETORIX, rc.ATREBATES, True),
])
def test_card45_ambush_if_able_keeps_executing_leader_range(
        leader, leader_region, ambush):
    # Card45's use of Aedui pieces affects Hidden strength; it does not
    # waive §4.3.3's named-Leader/Successor proximity requirement.
    state = _state()
    state['current_card'] = 45
    state['resources'][rc.ARVERNI] = 0
    place_piece(state, leader_region, rc.ARVERNI, rc.LEADER, leader_name=leader)
    place_piece(state, rc.MORINI, rc.ARVERNI, rc.WARBAND, 1)
    place_piece(state, rc.MORINI, rc.AEDUI, rc.WARBAND, 4)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 2)
    result = _execute_event(state, rc.ARVERNI, {'command': 'Event',
        'details': {'card_id': 45, 'text_preference': rc.EVENT_SHADED}}, human=True)
    assert result['executed']
    battle = result['free_actions'][0]
    assert battle['ambush'] is ambush
    assert battle['result']['executed']
    assert not battle['result']['errors']
    assert battle['result']['battle_sa_executed'] is ambush
    assert state['resources'][rc.ARVERNI] == 0
    assert validate_state(state) == []


def test_carnyx_phase_errors_are_audited_even_without_eligible_faction_actions():
    result = {'card_results': [{'card': 'A15C', 'turn_result': {
        'actions_taken': {}, 'arverni_phase': {'rally': {}, 'march': {
            'marches': [{'result': {'error': 'illegal phase March'}}]}}}}]}
    counts, examples, occurrences = Counter(), {}, []
    census_result(result, counts, examples, rc.SCENARIO_ARIOVISTUS, 3, occurrences)
    assert len(occurrences) == 1
    assert occurrences[0]['faction'] == rc.ARVERNI
    assert occurrences[0]['command'] == rc.CMD_MARCH
    assert occurrences[0]['severity'] == 'illegal'


def test_carnyx_phase_at_peace_or_with_no_actions_is_not_a_failure():
    result = {'card_results': [{'card': 'A15C', 'turn_result': {
        'actions_taken': {}, 'arverni_phase': {'at_war': False,
            'rally': None, 'march': None, 'battle': None}}}]}
    counts, examples = Counter(), {}
    census_result(result, counts, examples, rc.SCENARIO_ARIOVISTUS, 3)
    assert not counts
