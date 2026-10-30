"""One selection per Seize/Entreat Region — §§3.1, 4.1, 4.3.1.

Repeated operation entries can be legal for other actions (§§3.2.2, 3.3.1,
3.3.3, 4.2.1); rejecting duplicate Region labels indiscriminately is wrong.
"""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine.action_validation import validate_human_structure
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.free_actions import (
    consult_free_action, execute_free_action_plan, validate_free_action_response,
)
from fs_bot.engine.game_engine import ACTION_COMMAND_SA, _action_transaction
from fs_bot.engine.moves import validate_player_action
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def position(faction, scenario=rc.SCENARIO_GREAT_REVOLT):
    state = build_initial_state(scenario, seed=61)
    state['non_player_factions'] = set()
    state['resources'][faction] = 10
    if faction == rc.ROMANS:
        place_piece(state, rc.CARNUTES, faction, rc.AUXILIA)
        place_piece(state, rc.MANDUBII, faction, rc.AUXILIA)
    else:
        place_piece(state, rc.CARNUTES, faction, rc.LEADER, leader_name=rc.VERCINGETORIX)
        for region in (rc.CARNUTES, rc.MANDUBII):
            place_piece(state, region, faction, rc.WARBAND, 2)
            place_piece(state, region, rc.BELGAE, rc.WARBAND, 2)
    assert validate_state(state) == []
    return state


def seize(*regions):
    return {'command': rc.CMD_SEIZE, 'regions': list(regions), 'sa': 'No SA',
            'details': {'disperse_regions': []}}


def entreat(*regions, timing='before'):
    return {'command': rc.CMD_RAID, 'sa': rc.SA_ENTREAT, 'sa_timing': timing,
            'sa_regions': [{'region': r, 'action': 'replace_piece',
                            'target_faction': rc.BELGAE, 'target_type': rc.WARBAND,
                            'target_state': rc.HIDDEN} for r in regions],
            'details': {'raid_plan': [{'region': rc.CARNUTES, 'target': None}]}}


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
def test_repeated_seize_is_rejected_by_preview_and_execution_before_forage(scenario):
    state = position(rc.ROMANS, scenario)
    action = seize(rc.CARNUTES, rc.CARNUTES)
    before = encode(state)
    ok, preview = validate_player_action(state, rc.ROMANS, action)
    assert not ok and '§3.1' in preview['reason']
    result = execute_decision(state, rc.ROMANS, {'player_action': action})
    assert not result['executed'] and '§3.1' in result['reason']
    assert encode(state) == before


@pytest.mark.parametrize('timing', ['before', 'after'])
def test_repeated_entreat_is_rejected_before_command_or_sa_mutation(timing):
    state = position(rc.ARVERNI)
    action = entreat(rc.CARNUTES, rc.CARNUTES, timing=timing)
    before = encode(state)
    result = execute_decision(state, rc.ARVERNI, {'player_action': action})
    assert not result['executed'] and '§4.1' in result['reason']
    assert encode(state) == before


@pytest.mark.parametrize('parts', [
    [seize(rc.CARNUTES, rc.CARNUTES), seize(rc.MANDUBII)],
    [seize(rc.CARNUTES), seize(rc.CARNUTES)],
])
def test_seize_repetition_within_or_across_interrupted_portions_is_rejected(parts):
    state = position(rc.ROMANS)
    action = {'command': rc.CMD_SEIZE, 'sa': rc.SA_BUILD, 'sa_timing': 'during',
              'details': {'command_parts': parts}}
    before = encode(state)
    result = execute_decision(state, rc.ROMANS, {'player_action': action})
    assert not result['executed'] and '§3.1' in result['reason']
    assert encode(state) == before


def test_entreat_region_names_and_target_entries_share_one_selection_limit():
    state = position(rc.ARVERNI)
    action = entreat(rc.CARNUTES)
    action['sa_regions'].append(rc.CARNUTES)
    assert '§4.1' in validate_human_structure(state, rc.ARVERNI, action)


def test_distinct_seize_and_entreat_regions_still_resolve_once_each():
    # Map Transcription: Carnutes has two Tribes, Mandubii three;
    # all are Subdued here, so §3.2.3 yields 4 + 6.
    state = position(rc.ROMANS)
    result = execute_decision(state, rc.ROMANS, {
        'player_action': seize(rc.CARNUTES, rc.MANDUBII)})
    assert result['executed'] and not result['errors']
    assert state['resources'][rc.ROMANS] == 20
    state = position(rc.ARVERNI)
    result = execute_decision(state, rc.ARVERNI, {
        'player_action': entreat(rc.CARNUTES, rc.MANDUBII)})
    assert result['executed'] and not result['errors']
    assert result['sa_execution']['executed'] and not result['sa_execution']['errors']
    for region in (rc.CARNUTES, rc.MANDUBII):
        assert count_pieces(state, region, rc.ARVERNI, rc.WARBAND) == 3
        assert count_pieces(state, region, rc.BELGAE, rc.WARBAND) == 1
    assert state['resources'][rc.ARVERNI] == 9  # two Entreat costs, one Raid gain
    assert validate_state(state) == []


def session_for(state, faction, meta=None, log=None):
    session = SeatSession(state, meta or {'seat': faction}, log or [],
                          HumanTurnDisplay(StringIO()))
    state['decision_agent'] = session.reactive
    return session


def attempt(session, request):
    def driver(*args):
        pass
    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    state, faction = session.state, session.seat
    with _action_transaction(state, driver):
        # A granted choice can follow prior Event effects and a die. A rejected
        # input must retain the same pending board and restore the retry point.
        state['rng'].randint(rc.DIE_MIN, rc.DIE_MAX)
        state['resources'][faction] += 1
        if request['kind'] == 'turn':
            decision = session.ask(state, faction, request)
            return execute_decision(state, faction, decision)
        action = consult_free_action(state, faction, request)
        return execute_free_action_plan(state, faction, request, action)


@pytest.mark.parametrize('case', ['seize_turn', 'seize_free', 'entreat_turn', 'entreat_sa'])
def test_duplicate_durable_plans_stay_pending_across_rollback_and_save_resume(tmp_path, case):
    faction = rc.ROMANS if case.startswith('seize') else rc.ARVERNI
    action = (seize(rc.CARNUTES, rc.CARNUTES) if faction == rc.ROMANS
              else entreat(rc.CARNUTES, rc.CARNUTES))
    if case.endswith('turn'):
        request = {'kind': 'turn', 'options': [ACTION_COMMAND_SA], 'position': '1st_eligible'}
        response = {'action': ACTION_COMMAND_SA, 'player_action': action}
    else:
        request = {'kind': 'free_action', 'request_type': 'event_command',
                   'allowed_commands': [rc.CMD_SEIZE], 'with_sa': False,
                   'allowed_regions': [rc.CARNUTES], 'free': True}
        if case == 'entreat_sa':
            request.update(request_type='event_sa', allowed_sas=[rc.SA_ENTREAT])
            action.pop('command')
            action['details'] = {}
        response = action
    session = session_for(position(faction), faction)
    before = encode(board_copy(session.state))
    with pytest.raises(DecisionPending):
        attempt(session, request)
    pending = deepcopy(session.data['pending'])
    payload = {'decision_id': pending['id'], 'response': response}
    session.import_inbox(payload)
    with pytest.raises(DecisionPending):
        attempt(session, request)
    assert 'only once' in session.error
    assert session.data['pending'] == pending
    assert session.data['queue'] == [payload] and not session.data['journal']
    assert encode(board_copy(session.state)) == before
    path = tmp_path / 'pending.json'
    save_game(session.state, path, meta=session.meta, log=session.log)
    state, meta, log = load_game(path)
    resumed = session_for(state, faction, meta, log)
    with pytest.raises(DecisionPending):
        attempt(resumed, request)
    assert resumed.data['pending'] == pending
    assert resumed.data['queue'] == [payload]
    assert encode(board_copy(state)) == before
    corrected = deepcopy(response)
    plan = corrected['player_action'] if case.endswith('turn') else corrected
    plan['regions' if faction == rc.ROMANS else 'sa_regions'] = [
        rc.CARNUTES if faction == rc.ROMANS else plan['sa_regions'][0]]
    resumed.import_inbox({'decision_id': pending['id'], 'response': corrected})
    for _ in range(20):
        try:
            result = attempt(resumed, request)
            break
        except DecisionPending:
            next_pending = resumed.data['pending']
            assert decode(next_pending['request'])['kind'] == 'voluntary_removal'
            resumed.import_inbox({'decision_id': next_pending['id'],
                                  'response': {'done': True}})
    else:
        pytest.fail('Corrected plan did not finish its removal windows')
    assert result['executed'] and not result.get('errors'), result
    resumed.finish()
    assert not resumed.data['pending'] and not resumed.data['queue']
    assert resumed.log[0]['assistant_id'] == pending['id']
    assert decode(resumed.log[0]['assistant_response']) == corrected


@pytest.mark.parametrize('command', [rc.CMD_RAID, rc.CMD_RALLY, rc.CMD_MARCH, rc.CMD_RECRUIT])
def test_legal_same_region_operations_are_not_repeated_selections(command):
    # §§3.3.3, 3.3.1, 3.2.2, 4.2.1 respectively permit these operation groups.
    faction = rc.ROMANS if command in (rc.CMD_MARCH, rc.CMD_RECRUIT) else rc.ARVERNI
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=73)
    state['resources'][faction] = 10
    state['non_player_factions'] = set()
    region = rc.SEQUANI
    action = {'command': command, 'sa': 'No SA', 'details': {}}
    if command == rc.CMD_RAID:
        place_piece(state, region, faction, rc.WARBAND, 2)
        action['details']['raid_plan'] = [{'region': region, 'target': None}] * 2
    elif command == rc.CMD_RALLY:
        place_piece(state, region, faction, rc.LEADER, leader_name=rc.VERCINGETORIX)
        action['details']['rally_plan'] = {'steps': [
            {'region': region, 'action': 'place_ally', 'tribe': rc.TRIBE_SEQUANI},
            {'region': region, 'action': 'place_warbands', 'count': 3}]}
    elif command == rc.CMD_MARCH:
        place_piece(state, region, faction, rc.AUXILIA, 2)
        action['details']['march_plan'] = {
            'origins': [region], 'destinations': [rc.PROVINCIA],
            'routes': {region: [rc.PROVINCIA]},
            'groups': {region: {rc.AUXILIA: 1, rc.LEADER: False}},
            'extra_groups': [{'origin': region, 'route': [rc.AEDUI_REGION],
                              'group': {rc.AUXILIA: 1, rc.LEADER: False}}]}
    else:
        place_piece(state, region, faction, rc.LEADER, leader_name=rc.CAESAR)
        place_piece(state, region, faction, rc.AUXILIA)
        action.update(sa=rc.SA_BUILD, sa_timing='before', sa_regions=[region])
        action['details'].update(
            recruit_plan=[{'region': region, 'action': 'place_auxilia', 'count': 1}],
            build_plan={'forts': [region], 'allies': [{'region': region, 'tribe': rc.TRIBE_SEQUANI}]})
    request = {'kind': 'free_action', 'request_type': 'event_command',
               'allowed_commands': [command], 'allowed_regions': [region],
               'with_sa': True, 'free': True}
    assert validate_human_structure(state, faction, action) is None
    assert validate_free_action_response(state, faction, request, action) is None
    result = execute_decision(state, faction, {'player_action': action})
    assert result['executed'] and not result['errors'], result
    assert validate_state(state) == []
