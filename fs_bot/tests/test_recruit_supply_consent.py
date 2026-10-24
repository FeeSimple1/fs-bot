"""A Supply agreement binds through its Command, not a second cost call (§1.5.2)."""
import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import place_piece, count_pieces
from fs_bot.commands.rally import (
    recruit_cost, supply_agreement_scope, supply_query_scope)
from fs_bot.engine.execute import _execute_recruit, execute_decision
from fs_bot.engine.moves import validate_player_action
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state
from fs_bot.tools.player_fuzz import play_game


def _state(resources=4):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=12)
    state['non_player_factions'] = set()
    state['resources'][rc.ROMANS] = resources
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    # Remain under German Control through several Roman Auxilia placements.
    place_piece(state, rc.PROVINCIA, rc.GERMANS, rc.WARBAND, 12)
    refresh_all_control(state)
    return state


def _action(region=rc.PROVINCIA):
    return {'command': 'Recruit', 'regions': [], 'sa': 'No SA',
            'details': {'recruit_plan': [
                {'region': region, 'action': 'place_auxilia'}]}}


def _changing_agent(first):
    calls = []
    def agent(state, faction, request):
        assert request['request_type'] == 'supply_line'
        calls.append((faction, request['context']['region']))
        return first if len(calls) == 1 else not first
    return calls, agent


def _no_cache(state):
    assert '_supply_line_agreements' not in state
    assert '_supply_line_query' not in state


@pytest.mark.parametrize('first,cost', [(True, 0), (False, 2)])
def test_recruit_precheck_and_placement_share_first_live_supply_response(first, cost):
    state = _state()
    calls, state['decision_agent'] = _changing_agent(first)
    result = _execute_recruit(state, rc.ROMANS, _action())
    assert result['executed'] and not result['errors'], result
    assert calls == [(rc.GERMANS, rc.PROVINCIA)]
    assert state['resources'][rc.ROMANS] == 4 - cost
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) > 0
    _no_cache(state)


def test_separate_recruit_commands_request_supply_agreement_again():
    state = _state()
    calls, state['decision_agent'] = _changing_agent(True)
    first = execute_decision(state, rc.ROMANS, {'player_action': _action()})
    assert first['executed'] and state['resources'][rc.ROMANS] == 4
    _no_cache(state)
    second = execute_decision(state, rc.ROMANS, {'player_action': _action()})
    assert second['executed'] and state['resources'][rc.ROMANS] == 2
    assert calls == [(rc.GERMANS, rc.PROVINCIA)] * 2
    _no_cache(state)


def test_refusal_is_reused_for_duplicate_checks_but_can_change_on_later_request():
    state = _state()
    calls, state['decision_agent'] = _changing_agent(False)
    with supply_agreement_scope(state):
        with supply_query_scope(state):
            assert recruit_cost(state, rc.PROVINCIA) == 2
            assert recruit_cost(state, rc.PROVINCIA) == 2
        with supply_query_scope(state):
            assert recruit_cost(state, rc.PROVINCIA) == 0
        with supply_query_scope(state):
            assert recruit_cost(state, rc.PROVINCIA) == 0
    assert calls == [(rc.GERMANS, rc.PROVINCIA)] * 2
    _no_cache(state)


def test_accepted_supply_survives_recruit_split_around_actual_build():
    state = _state(resources=10)
    # Cisalpina is permanently blocked by game-run Arverni. Every other
    # route must ask the German player for Provincia, the only endpoint.
    place_piece(state, rc.CISALPINA, rc.ARVERNI, rc.WARBAND)
    for region in (rc.CARNUTES, rc.MANDUBII):
        place_piece(state, region, rc.ROMANS, rc.FORT)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    refresh_all_control(state)
    calls, state['decision_agent'] = _changing_agent(True)
    action = {'command': 'Recruit', 'regions': [], 'sa': 'Build',
              'sa_regions': [rc.SEQUANI], 'sa_timing': 'during', 'details': {
                  'command_parts': [_action(rc.CARNUTES), _action(rc.MANDUBII)],
                  'build_plan': {'forts': [rc.SEQUANI], 'subdue': [], 'allies': []}}}
    result = execute_decision(state, rc.ROMANS, {'player_action': action})
    assert result['executed'] and not result.get('errors'), result
    assert calls == [(rc.GERMANS, rc.PROVINCIA)]
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) > 0
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) > 0
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.FORT) == 1
    _no_cache(state)


def test_plan_validation_consumes_no_live_supply_response_or_cache():
    state = _state()
    calls, state['decision_agent'] = _changing_agent(True)
    before = encode({key: value for key, value in state.items() if key != 'decision_agent'})
    valid, result = validate_player_action(state, rc.ROMANS, _action())
    assert valid, result
    assert calls == []
    assert encode({key: value for key, value in state.items() if key != 'decision_agent'}) == before
    _no_cache(state)


def test_interrupted_supply_query_does_not_leak_cache_or_consume_next_command():
    state = _state()
    calls = []
    def interrupt(board, faction, request):
        calls.append(request)
        raise KeyboardInterrupt
    state['decision_agent'] = interrupt
    before = encode({key: value for key, value in state.items() if key != 'decision_agent'})
    with pytest.raises(KeyboardInterrupt):
        execute_decision(state, rc.ROMANS, {'player_action': _action()})
    assert len(calls) == 1
    assert encode({key: value for key, value in state.items() if key != 'decision_agent'}) == before
    _no_cache(state)
    resumed, state['decision_agent'] = _changing_agent(True)
    assert execute_decision(state, rc.ROMANS, {'player_action': _action()})['executed']
    assert resumed == [(rc.GERMANS, rc.PROVINCIA)]
    _no_cache(state)


@pytest.mark.parametrize('scenario,seed', [
    (rc.SCENARIO_ARIOVISTUS, 12), (rc.SCENARIO_GALLIC_WAR, 7)])
def test_real_mixed_seat_recruit_failures_complete_and_replay(scenario, seed):
    first = play_game(scenario, seed, card_edition='legacy')
    assert first['game_completed'] and first['findings'] == [], first
    assert first['partial'] == 0, first
    second = play_game(scenario, seed, card_edition='legacy')
    assert second == first
