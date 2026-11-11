"""FE5-01 and FE5-02: ordinary March rules under Event grants."""

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.free_actions import validate_free_action_response
from fs_bot.engine.game_engine import ACTION_COMMAND, ACTION_EVENT, get_sop_factions
from fs_bot.engine.march_choices import MARCH_DROPOFF
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state
from fs_bot.tests.test_action_window_frontends import leave_timing_unchanged
from fs_bot.tools import llm_seat
from fs_bot.tools.seat_session import SeatSession, board_copy


def _board(actor, card=52):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=4)
    state.update(current_card=card, current_card_id=card, played_cards=[card], next_card=None,
                 card_edition='second-edition', executing_faction=None, event_params=None,
                 non_player_factions=set())
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    place_piece(state, rc.CARNUTES, actor, rc.WARBAND if actor == rc.AEDUI else rc.AUXILIA)
    state['resources'][actor] = 10
    assert validate_state(state) == check_structural_integrity(state) == []
    return state


def _event(card=52):
    return {'action': ACTION_EVENT, 'player_action': {
        'command': rc.FIRST_DID_EVENT, 'sa': 'No SA', 'details': {
            'card_id': card, 'event_params': {},
            'text_preference': rc.EVENT_SHADED if card == 52 else rc.EVENT_UNSHADED}}}


def _march(origin, route, group):
    return {'command': rc.CMD_MARCH, 'sa': 'No SA', 'details': {
        'origins': [origin], 'destinations': route[-1:],
        'routes': {origin: route}, 'groups': {origin: group}}}


def _suborn(region):
    return [{'region': region, 'actions': [{'action': 'place_warband'}]}]


def _crossing(origin, destination, form, timing):
    group = {rc.WARBAND: 1}
    action = _march(origin, [destination], group)
    details = action['details']
    if form == 'explicit':
        action['details'] = details = {'explicit_moves': [
            {'origin': origin, 'path': [destination], 'group': group}]}
    elif form == 'additional-group':
        details['destinations'] = [rc.NERVII]
        details['routes'][origin] = [rc.NERVII]
        details['extra_groups'] = [{'origin': origin, 'route': [destination], 'group': group}]
    elif form == 'implicit':
        details.pop('routes')
    if timing is not None:
        action.update(sa=rc.SA_SUBORN, sa_timing=timing)
        details['suborn_plan'] = _suborn(rc.CARNUTES)
    return action


@pytest.mark.parametrize('origin,destination,form,timing', [
    (rc.MORINI, rc.BRITANNIA, 'ordinary', 'after'),
    (rc.BRITANNIA, rc.MORINI, 'ordinary', 'before'),
    (rc.MORINI, rc.BRITANNIA, 'explicit', 'after'),
    (rc.MORINI, rc.BRITANNIA, 'additional-group', 'before'),
    (rc.MORINI, rc.BRITANNIA, 'implicit', 'after'),
])
def test_assembly_rejects_crossing_with_an_ability_without_changes(origin, destination, form, timing):
    state = _board(rc.AEDUI)
    place_piece(state, origin, rc.AEDUI, rc.WARBAND, 2)
    plan = _crossing(origin, destination, form, timing)
    before = encode(state)
    requests = []

    def agent(live, faction, request):
        if request['kind'] == 'free_action':
            requests.append(deepcopy(request))
            return plan

    state['decision_agent'] = agent
    result = execute_decision(state, rc.AEDUI, _event())

    assert result.get('rejected') and 'Britannia' in result['reason'], result
    assert 'Britannia' in validate_free_action_response(state, rc.AEDUI, requests[0], plan)
    assert encode(board_copy(state)) == before


@pytest.mark.parametrize('origin,route,ability', [
    (rc.MORINI, [rc.BRITANNIA], False),
    (rc.BRITANNIA, [rc.MORINI], False),
    (rc.MORINI, [rc.NERVII], True),
    (rc.BRITANNIA, [], True),
])
def test_assembly_allows_crossing_alone_and_special_abilities_without_crossing(origin, route, ability):
    state = _board(rc.AEDUI)
    place_piece(state, origin, rc.AEDUI, rc.WARBAND, piece_state=rc.REVEALED)
    action = _march(origin, route, {rc.WARBAND: 1})
    if ability:
        action.update(sa=rc.SA_SUBORN, sa_timing='after')
        action['details']['suborn_plan'] = _suborn(rc.CARNUTES)
    state['decision_agent'] = lambda st, f, req: action if req['kind'] == 'free_action' else None

    result = execute_decision(state, rc.AEDUI, _event())

    assert result['executed'], result
    assert result['free_actions'][0]['sa_count'] == int(ability)
    assert count_pieces_by_state(state, route[-1] if route else origin,
                                 rc.AEDUI, rc.WARBAND, rc.HIDDEN) == 1
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 1 + int(ability)
    assert state['resources'][rc.AEDUI] == 10
    assert validate_state(state) == check_structural_integrity(state) == []


def test_land_of_mist_crossing_still_has_its_separate_free_ability():
    state = _board(rc.AEDUI, card=57)
    place_piece(state, rc.MORINI, rc.AEDUI, rc.WARBAND)

    def agent(live, faction, request):
        if request.get('request_type') == 'event_command':
            return _march(rc.MORINI, [rc.BRITANNIA], {rc.WARBAND: 1})
        if request.get('request_type') == 'event_sa':
            return {'sa': rc.SA_SUBORN, 'details': {'suborn_plan': _suborn(rc.BRITANNIA)}}

    state['decision_agent'] = agent
    result = execute_decision(state, rc.AEDUI, _event(57))
    assert result['executed'], result
    assert result['free_actions'][0]['sa_execution']['executed']
    assert count_pieces(state, rc.BRITANNIA, rc.AEDUI, rc.WARBAND) == 2
    assert state['resources'][rc.AEDUI] == 14


LEAVE = {'faction': rc.ROMANS, 'piece_type': rc.AUXILIA, 'piece_state': rc.HIDDEN, 'count': 1}


def _roman_march():
    return _march(rc.PROVINCIA, [rc.SEQUANI, rc.MANDUBII], {rc.AUXILIA: 2})


@pytest.mark.parametrize('mode', ['ordinary', 'zero', 'one', 'two', 'legacy-agent'])
def test_live_march_dropoff_moves_the_remainder_at_the_printed_cost(mode):
    state = _board(rc.ROMANS)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 3 if mode == 'two' else 2)
    plan = _roman_march()
    if mode in ('one', 'two'):
        place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
        build = {'sa': rc.SA_BUILD, 'sa_timing': 'before', 'details': {'build_plan': {
            'allies': [{'region': rc.PROVINCIA, 'tribe': rc.TRIBE_HELVII}]}}}
        if mode == 'one':
            plan.update(sa=build['sa'], sa_timing=build['sa_timing'])
            plan['details'].update(build['details'])
        else:
            plan['special_abilities'] = [build, {'sa': rc.SA_SCOUT, 'sa_timing': 'after',
                'details': {'scout_plan': {'auxilia_moves': [{'from_region': rc.PROVINCIA,
                    'to_region': rc.AEDUI_REGION, 'count': 1, 'piece_state': rc.HIDDEN}],
                    'scout_targets': []}}}]
    requests = []

    def agent(live, faction, request):
        if request['kind'] == 'free_action':
            return plan
        if request['kind'] == MARCH_DROPOFF:
            requests.append(deepcopy(request))
            return {'dropoffs': [LEAVE]}

    agent.supports_march_dropoffs = mode != 'legacy-agent'
    state['decision_agent'] = agent
    decision = {'action': ACTION_COMMAND, 'player_action': plan} if mode == 'ordinary' else _event()
    result = execute_decision(state, rc.ROMANS, decision)

    assert result['executed'], result
    if mode != 'ordinary':
        assert result['free_actions'][0]['sa_count'] == {'one': 1, 'two': 2}.get(mode, 0)
        result = result['free_actions'][0]['result']
    assert result['executed'] and not result['errors']
    if mode == 'legacy-agent':
        assert requests == []
    else:
        assert len(requests) == 1 and requests[0]['region'] == rc.SEQUANI
        assert requests[0]['pieces'] == [dict(LEAVE, count=2)]
        assert result['marches'][0]['dropoffs'] == [dict(region=rc.SEQUANI, step=1, pieces=[LEAVE])]
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == int(mode != 'legacy-agent')
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == (2 if mode == 'legacy-agent' else 1)
    cost = 2 if mode == 'ordinary' else 0
    assert result['total_cost'] == cost and state['resources'][rc.ROMANS] == 10 - cost
    assert validate_state(state) == check_structural_integrity(state) == []


def _assistant(tmp_path, state, actor):
    state['non_player_factions'] = set(get_sop_factions(state)) - {actor}
    for faction in state['eligibility']:
        state['eligibility'][faction] = rc.ELIGIBLE if faction == actor else rc.INELIGIBLE
    path = tmp_path / 'live' / 'save.json'
    path.parent.mkdir()
    save_game(state, path, meta={'seat': actor, 'scenario': state['scenario'], 'seed': 4}, log=[])
    args = SimpleNamespace(dir=str(path.parent), output_dir=str(tmp_path / 'replay'))
    assert llm_seat.cmd_play(args) == 0
    leave_timing_unchanged(args)
    return path, args


def _saved(path):
    state, meta, log = load_game(path, validate=True)
    return state, meta['assistant_session']['pending'], log


def _submit(path, args, response):
    _, pending, _ = _saved(path)
    assert pending is not None
    assert llm_seat.cmd_submit(SimpleNamespace(
        dir=args.dir, decision_id=pending['id'], response=json.dumps(response))) == 0
    leave_timing_unchanged(args)


def _replay(path, args):
    assert llm_seat.cmd_replay(args) == 0
    final, pending, log = _saved(path)
    replayed, _, replay_log = load_game(args.output_dir + '/save.json', validate=True)
    assert pending is None and encode(replayed) == encode(final) and replay_log == log


def test_illegal_grant_stays_pending_through_reload_and_can_be_corrected(tmp_path):
    state = _board(rc.AEDUI)
    place_piece(state, rc.MORINI, rc.AEDUI, rc.WARBAND, 2)
    path, args = _assistant(tmp_path, state, rc.AEDUI)
    initial, _, _ = _saved(path)
    _submit(path, args, _event())
    _, grant, _ = _saved(path)
    assert decode(grant['request'])['request_type'] == 'event_command'
    _submit(path, args, _crossing(rc.MORINI, rc.BRITANNIA, 'ordinary', 'after'))
    board, retry, log = _saved(path)
    assert retry == grant and encode(board) == encode(initial) and not log
    assert llm_seat.cmd_play(args) == 0 and _saved(path)[1] == grant

    _submit(path, args, _crossing(rc.MORINI, rc.BRITANNIA, 'ordinary', None))

    final, _, _ = _saved(path)
    assert count_pieces(final, rc.BRITANNIA, rc.AEDUI, rc.WARBAND) == 1
    assert count_pieces(final, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 1
    _replay(path, args)


@pytest.mark.parametrize('legacy', [False, True])
def test_free_march_dropoff_and_older_default_replay(tmp_path, monkeypatch, legacy):
    state = _board(rc.ROMANS)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 2)
    if legacy:
        monkeypatch.setattr(SeatSession, 'supports_march_dropoffs', False)
    path, args = _assistant(tmp_path, state, rc.ROMANS)
    initial, _, _ = _saved(path)
    _submit(path, args, _event())
    _submit(path, args, _roman_march())
    if not legacy:
        board, pending, log = _saved(path)
        assert pending is not None and decode(pending['request'])['kind'] == MARCH_DROPOFF
        assert count_pieces(decode(pending['board']), rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 2
        assert encode(board) == encode(initial) and not log
        _submit(path, args, {'dropoffs': [dict(LEAVE, count=2)]})
        assert _saved(path)[1] == pending
        assert llm_seat.cmd_play(args) == 0 and _saved(path)[1] == pending
        _submit(path, args, {'dropoffs': [LEAVE]})

    final, pending, log = _saved(path)
    assert pending is None and final['resources'][rc.ROMANS] == 10
    assert count_pieces(final, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == (2 if legacy else 1)
    assert count_pieces(final, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == int(not legacy)
    assert len([entry for entry in log if entry.get('reactive') == MARCH_DROPOFF]) == int(not legacy)
    monkeypatch.setattr(SeatSession, 'supports_march_dropoffs', True)
    _replay(path, args)
