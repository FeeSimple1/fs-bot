"""A53 spending/ownership/order per A Card Reference and A8.6.6."""
from copy import deepcopy
from itertools import permutations
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces
from fs_bot.board.control import refresh_all_control
from fs_bot.commands.common import free_action_scope, is_free_action
from fs_bot.engine.frumentum import (resolve_frumentum, validate_response,
                                    ACTIONS, ACTION_SA, spending_scope)
from fs_bot.state.state_schema import build_initial_state
from fs_bot.state.serialize import encode


def _state():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=17)
    state['non_player_factions'] = set()
    state['resources'].update({rc.AEDUI: 10, rc.ROMANS: 7})
    return state


def _march(origin=rc.CARNUTES, destination=rc.MANDUBII):
    return {'command': 'March', 'sa': 'No SA', 'details': {
        'origins': [origin], 'destinations': [destination],
        'routes': {origin: [destination]},
        'groups': {origin: {rc.AUXILIA: 1, rc.LEADER: False}}}}


def _request(budget=6, remaining=ACTIONS):
    return {'kind': 'frumentum_action', 'remaining_actions': list(remaining),
            'remaining_resources': budget, 'reserved_roman_resources': 7,
            'allocated_resources': 6}


@pytest.mark.parametrize('order', list(permutations(ACTIONS)))
def test_humans_choose_all_six_paid_orders_without_eligibility_changes(order):
    state = _state()
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 3)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.FORT)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 2)
    refresh_all_control(state)
    eligibility = deepcopy(state['eligibility'])
    choices = {
        'March': _march(),
        'Recruit': {'command': 'Recruit', 'sa': 'No SA', 'details': {
            'recruit_plan': [{'region': rc.CARNUTES, 'action': 'place_auxilia'}]}},
        ACTION_SA: {'command': None, 'sa': 'Scout', 'sa_regions': [rc.CARNUTES],
                    'details': {'scout_plan': {'auxilia_moves': [], 'scout_targets': [
                        {'region': rc.CARNUTES, 'enemy': rc.ARVERNI, 'hidden': 2}]}}},
    }
    requests, left = [], list(order)
    def agent(board, faction, request):
        if request['kind'] == 'frumentum_amount':
            assert faction == rc.AEDUI
            return {'amount': 6}
        if request['kind'] != 'frumentum_action':
            return False
        assert faction == rc.ROMANS
        requests.append(request)
        return choices[left.pop(0)]
    state['decision_agent'] = agent
    # The enclosing Event dispatcher normally grants free costs globally.
    with free_action_scope(state):
        result = resolve_frumentum(state)[0]
        assert is_free_action(state, rc.ROMANS)
    assert [entry['action'] for entry in result['actions']] == list(order)
    assert result['spent'] == 2  # Recruit's normal Supply-Line discount remains legal.
    assert result['unused'] == 4
    assert state['resources'][rc.AEDUI] == 4
    assert state['resources'][rc.ROMANS] == 11  # explicit legacy unused-transfer retention
    assert state['eligibility'] == eligibility
    assert [len(req['remaining_actions']) for req in requests] == [3, 2, 1]
    assert '_frumentum_budget' not in state and '_free_action_factions' not in state


def test_recruit_without_supply_and_build_charge_allocation_not_roman_treasury():
    state = _state()
    place_piece(state, rc.MORINI, rc.ROMANS, rc.FORT)
    for region in (rc.NERVII, rc.ATREBATES, rc.SUGAMBRI):
        place_piece(state, region, rc.GERMANS, rc.WARBAND, 5)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    refresh_all_control(state)
    plans = iter([
        {'command': 'Recruit', 'sa': 'No SA', 'details': {
            'recruit_plan': [{'region': rc.MORINI, 'action': 'place_auxilia'}]}},
        {'command': None, 'sa': 'Build', 'sa_regions': [rc.SEQUANI],
         'details': {'build_plan': {'forts': [rc.SEQUANI]}}},
        {'decline': True},
    ])
    state['decision_agent'] = lambda board, faction, request: (
        {'amount': 4} if request['kind'] == 'frumentum_amount' else next(plans)
        if request['kind'] == 'frumentum_action' else False)
    with free_action_scope(state):
        result = resolve_frumentum(state)[0]
    assert [entry['spent'] for entry in result['actions']] == [2, 2]
    assert state['resources'][rc.ROMANS] == 7
    assert state['resources'][rc.AEDUI] == 6


@pytest.mark.parametrize('romans_np,expected', [(True, 10), (False, 0)])
def test_np_aedui_transfer_half_only_to_np_romans(romans_np, expected):
    state = _state()
    state['resources'][rc.AEDUI] = 21
    state['non_player_factions'] = {rc.AEDUI} | ({rc.ROMANS} if romans_np else set())
    state['decision_agent'] = lambda board, faction, request: {'decline': True}
    result = resolve_frumentum(state)[0]
    assert result['allocated'] == expected
    assert state['resources'][rc.AEDUI] == 21 - expected
    assert result['spent'] <= expected


def test_np_fallback_preserves_build_before_recruit_flowchart_order(monkeypatch):
    from fs_bot.engine.frumentum import _default_action
    state = _state()
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    refresh_all_control(state)
    recruit = {'command': 'Recruit', 'sa': 'Build', 'sa_regions': [], 'details': {
        'recruit_plan': [{'region': rc.SEQUANI, 'action': 'place_auxilia'}]}}
    monkeypatch.setattr('fs_bot.bots.bot_dispatch.dispatch_bot_turn',
                        lambda *_: {'command': 'Battle', 'sa': 'Besiege'})
    monkeypatch.setattr('fs_bot.bots.roman_bot.node_r_march', lambda *_: recruit)
    monkeypatch.setattr('fs_bot.bots.roman_bot.node_r_recruit', lambda *_: recruit)
    plan = _default_action(state, _request(budget=8))
    assert plan['command'] is None and plan['sa'] == 'Build'
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.FORT) == 0


@pytest.mark.parametrize('amount', [-1, 11, True, '4', None])
def test_malformed_or_unavailable_amount_does_not_consume_resources(amount):
    state = _state()
    before = encode(state)
    with pytest.raises(ValueError):
        validate_response(state, {'kind': 'frumentum_amount'}, {'amount': amount})
    assert encode(state) == before


def test_private_roman_resources_cannot_cover_overspending_or_inherited_free_scope():
    state = _state()
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    state['resources'][rc.ROMANS] = 40
    with free_action_scope(state):
        before = encode(state)
        with pytest.raises(ValueError):
            validate_response(state, _request(budget=1), _march())
        assert encode(state) == before


def test_repeated_command_and_second_sa_are_rejected_before_execution():
    state = _state()
    with pytest.raises(ValueError, match='unused'):
        validate_response(state, _request(remaining=['Recruit', ACTION_SA]), _march())
    with pytest.raises(ValueError, match='unused'):
        validate_response(state, _request(remaining=['March']),
                          {'command': None, 'sa': 'Build', 'details': {'build_plan': {}}})
    with pytest.raises(ValueError, match='own action'):
        validate_response(state, _request(), dict(_march(), sa='Build'))
    with pytest.raises(ValueError, match='exactly one'):
        validate_response(state, _request(), dict(_march(), skip='Battle'))


def test_invalid_human_action_retries_without_spending_or_using_slot():
    state = _state()
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    requests = []
    def agent(board, faction, request):
        if request['kind'] == 'frumentum_amount':
            return {'amount': 1}
        requests.append(request)
        return _march() if len(requests) == 1 else {'decline': True}
    state['decision_agent'] = agent
    result = resolve_frumentum(state)[0]
    assert len(requests) == 2 and requests[1]['errors']
    assert requests[1]['remaining_actions'] == list(ACTIONS)
    assert requests[1]['remaining_resources'] == 1
    assert result['actions'] == [] and result['spent'] == 0
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 1


def test_cli_amount_and_paid_action_keep_explicit_choices():
    from fs_bot.cli.reactive import make_cli_reactive
    state = _state()
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    out = io.StringIO()
    agent = make_cli_reactive([rc.AEDUI, rc.ROMANS], io.StringIO(
        '5\nCommand: March\nCarnutes\nMandubii\nall 1\n'), out)
    assert agent(state, rc.AEDUI, {'kind': 'frumentum_amount'}) == {'amount': 4}
    result = agent(state, rc.ROMANS, _request(4))
    assert result['command'] == 'March'
    assert result['details']['routes'] == {rc.CARNUTES: [rc.MANDUBII]}
    assert 'paid action next' in out.getvalue()
    assert state['resources'][rc.ROMANS] == 7


def test_nested_board_shows_actual_treasury_and_separate_funding_allowance():
    from fs_bot.cli.display import format_state_summary, snapshot_state
    state = _state()
    state['_frumentum_budget'] = {'allocated': 6, 'remaining': 6, 'reserved_treasury': 7}
    with spending_scope(state, 6):
        state['resources'][rc.ROMANS] -= 2
        board = format_state_summary(state)
        assert '4 of 6 Aedui Resources remain' in board
        assert snapshot_state(state)['resources'][rc.ROMANS] == 7
    assert state['resources'][rc.ROMANS] == 7
