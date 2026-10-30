"""Ordered Rally and exact quantities retain whole-action/session constraints."""

import copy
import io
import json
from types import SimpleNamespace
from pathlib import Path

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine.action_validation import command_regions, validate_human_structure
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.free_actions import (execute_free_action_plan,
                                       validate_free_action_response)
from fs_bot.engine.game_engine import (
    ACTION_COMMAND, ACTION_COMMAND_SA, ACTION_LIMITED_COMMAND, ACTION_EVENT,
)
from fs_bot.engine.moves import preview_player_action
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state
from fs_bot.tools import llm_seat
from fs_bot.tools.seat_session import SeatSession, board_copy


def _state(faction=rc.ARVERNI, scenario=rc.SCENARIO_GREAT_REVOLT):
    state = build_initial_state(scenario, seed=11)
    state['resources'][faction] = 10
    state['non_player_factions'] = set(rc.FACTIONS) - {faction}
    state['current_card'] = state['current_card_id'] = 16
    state['played_cards'], state['deck'], state['next_card'] = [16], [], None
    for other in state['eligibility']:
        state['eligibility'][other] = rc.ELIGIBLE if other == faction else rc.INELIGIBLE
    if faction == rc.ARVERNI:
        place_piece(state, rc.MANDUBII, faction, rc.LEADER,
                    leader_name=rc.VERCINGETORIX)
    elif faction == rc.ROMANS:
        place_piece(state, rc.PROVINCIA, faction, rc.LEADER, leader_name=rc.CAESAR)
        place_piece(state, rc.SEQUANI, faction, rc.FORT)
    refresh_all_control(state)
    return state


def _rally(steps):
    return {'command': 'Rally', 'regions': [], 'sa': 'No SA',
            'details': {'rally_plan': {'steps': steps}}}


def _warbands(region=rc.MANDUBII, count=1):
    return {'region': region, 'action': 'place_warbands', 'count': count}


def _ally():
    return {'region': rc.MANDUBII, 'action': 'place_ally', 'tribe': rc.TRIBE_MANDUBII}


def _recruit(count=1):
    return {'command': 'Recruit', 'regions': [], 'sa': 'No SA', 'details': {
        'recruit_plan': [{'region': rc.PROVINCIA, 'action': 'place_auxilia', 'count': count}]}}


def _grant(**kwargs):
    return {'kind': 'free_action', 'request_type': 'event_rally',
            'allowed_commands': ['Rally'], 'allowed_regions': [rc.MANDUBII],
            'max_regions': 1, 'free': True, **kwargs}


def test_command_regions_uses_step_order_and_counts_combined_region_once():
    action = _rally([_warbands(rc.NERVII), _warbands(), _ally()])
    assert command_regions(action) == [rc.NERVII, rc.MANDUBII]


@pytest.mark.parametrize('warbands_first', [False, True])
def test_scoped_free_rally_accepts_both_vercingetorix_orders_in_one_region(warbands_first):
    state = _state()
    troop_step = _warbands(count=2 if warbands_first else 3)
    steps = [troop_step, _ally()] if warbands_first else [_ally(), troop_step]
    action, grant = _rally(steps), _grant()
    before = encode(state)
    assert validate_free_action_response(state, rc.ARVERNI, grant, action) is None
    assert encode(state) == before
    result = execute_free_action_plan(state, rc.ARVERNI, grant, action)
    assert result['executed'] and not result['errors']
    assert count_pieces(state, rc.MANDUBII, rc.ARVERNI, rc.WARBAND) == troop_step['count']
    assert count_pieces(state, rc.MANDUBII, rc.ARVERNI, rc.ALLY) == 1
    assert state['resources'][rc.ARVERNI] == 10


@pytest.mark.parametrize('allowed,max_regions,reason', [
    ([rc.MANDUBII], 2, 'Regions granted'),
    ([rc.MANDUBII, rc.ARVERNI_REGION], 1, 'at most 1'),
])
def test_free_rally_scope_sees_every_step(allowed, max_regions, reason):
    state = _state()
    action = _rally([_warbands(), _ally(), _warbands(rc.ARVERNI_REGION)])
    before = encode(state)
    error = validate_free_action_response(state, rc.ARVERNI,
        _grant(allowed_regions=allowed, max_regions=max_regions), action)
    assert reason in error
    assert encode(state) == before


@pytest.mark.parametrize('command,faction', [('Rally', rc.ARVERNI), ('Recruit', rc.ROMANS)])
def test_limited_command_rejects_multiple_placement_regions_before_mutation(command, faction):
    state = _state(faction)
    if command == 'Rally':
        action = _rally([_warbands(), _ally(), _warbands(rc.ARVERNI_REGION)])
    else:
        action = _recruit()
        action['details']['recruit_plan'].append(
            {'region': rc.SEQUANI, 'action': 'place_auxilia', 'count': 1})
    before = encode(state)
    result = execute_decision(state, faction,
        {'action': ACTION_LIMITED_COMMAND, 'player_action': action})
    assert not result['executed'] and 'Limited Command' in result['reason']
    assert encode(state) == before


def test_limited_march_counts_origins_and_not_destinations():
    state = _state(rc.ROMANS)
    action = {'command': 'March', 'sa': 'No SA',
              'details': {'origins': [rc.PROVINCIA], 'destinations': [rc.SEQUANI, rc.UBII]}}
    assert validate_human_structure(state, rc.ROMANS, action, limited=True) is None
    action['details']['origins'].append(rc.SEQUANI)
    assert 'Limited Command' in validate_human_structure(state, rc.ROMANS, action, limited=True)


def test_ordinary_limited_command_cannot_smuggle_an_sa_while_event_grant_can():
    state = _state(rc.AEDUI)
    place_piece(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND)
    action = _rally([_warbands(rc.AEDUI_REGION)])
    action.update(sa='Suborn', sa_regions=[rc.MANDUBII])
    action['details']['suborn_plan'] = [{'region': rc.MANDUBII, 'actions': [
        {'action': 'place', 'piece_type': rc.WARBAND, 'faction': rc.AEDUI}]}]
    before = encode(state)
    result = execute_decision(state, rc.AEDUI,
        {'action': ACTION_LIMITED_COMMAND, 'player_action': action})
    assert not result['executed'] and 'Special Ability' in result['reason']
    assert encode(state) == before
    grant = _grant(with_sa=True, allowed_regions=[rc.AEDUI_REGION, rc.MANDUBII])
    assert validate_free_action_response(state, rc.AEDUI, grant, action) is None


def test_interrupted_rally_cannot_reselect_vercingetorix_region():
    state = _state()
    action = _rally([])
    action.update(sa='Entreat', sa_timing='during')
    action['details']['command_parts'] = [_rally([_warbands()]), _rally([_ally()])]
    assert 'only once' in validate_human_structure(state, rc.ARVERNI, action)
    assert 'only once' in validate_free_action_response(
        state, rc.ARVERNI, _grant(with_sa=True), action)


def test_interrupted_rally_keeps_quantities_and_distinct_region_budget():
    state = _state(rc.AEDUI)
    for region, tribe in ((rc.AEDUI_REGION, rc.TRIBE_AEDUI), (rc.SEQUANI, rc.TRIBE_SEQUANI)):
        place_piece(state, region, rc.AEDUI, rc.ALLY)
        state['tribes'][tribe].update(allied_faction=rc.AEDUI, status=None)
    place_piece(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND)
    refresh_all_control(state)
    action = _rally([])
    action.update(sa='Suborn', sa_timing='during', sa_regions=[rc.MANDUBII])
    action['details'].update(
        command_parts=[_rally([_warbands(rc.AEDUI_REGION, 0)]),
                       _rally([_warbands(rc.SEQUANI, 1)])],
        suborn_plan=[{'region': rc.MANDUBII,
                      'actions': [{'action': 'place', 'piece_type': rc.WARBAND,
                                   'faction': rc.AEDUI}]}])
    grant = _grant(with_sa=True, allowed_regions=[rc.AEDUI_REGION, rc.SEQUANI, rc.MANDUBII],
                   max_regions=2)
    assert validate_free_action_response(state, rc.AEDUI, grant, action) is None
    assert 'at most 1' in validate_free_action_response(
        state, rc.AEDUI, dict(grant, max_regions=1), action)
    result = execute_free_action_plan(state, rc.AEDUI, grant, action)
    assert result['executed'] and not result['errors']
    assert count_pieces(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == 0
    assert count_pieces(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == 1
    assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == 2
    assert state['resources'][rc.AEDUI] == 10


@pytest.mark.parametrize('bad_count', [True, 1.0, '1', None, -1])
@pytest.mark.parametrize('command,faction', [('Rally', rc.ARVERNI), ('Recruit', rc.ROMANS)])
def test_bad_quantity_types_reject_whole_plan_before_an_earlier_valid_region(command, faction, bad_count):
    state = _state(faction)
    if command == 'Rally':
        action = _rally([_warbands(rc.ARVERNI_REGION), _warbands(count=bad_count)])
    else:
        action = _recruit()
        action['details']['recruit_plan'].append(
            {'region': rc.SEQUANI, 'action': 'place_auxilia', 'count': bad_count})
    before = encode(state)
    result = execute_decision(state, faction, {'action': ACTION_COMMAND, 'player_action': action})
    assert not result['executed']
    assert encode(state) == before


def _save_session(path, state, faction):
    path.mkdir()
    display = HumanTurnDisplay(io.StringIO())
    display.remember(state, [faction])
    meta = {'seat': faction, 'scenario': state['scenario'], 'seed': 11,
            'human_snapshots': encode(display.snapshots)}
    SeatSession(state, meta, [], display)
    save_game(state, path / 'save.json', meta=meta, log=[])
    return SimpleNamespace(dir=str(path))


def _decline_timing_windows(args):
    """Leave the new optional windows unchanged, retaining their real history."""
    for _ in range(100):
        _, meta, _ = load_game(Path(args.dir) / 'save.json')
        pending = meta['assistant_session']['pending']
        if not pending or decode(pending['request'])['kind'] != 'voluntary_removal':
            return
        args.response = json.dumps({'done': True})
        assert llm_seat.cmd_submit(args) == 0
        _, updated, _ = load_game(Path(args.dir) / 'save.json')
        assert updated['assistant_session']['pending'] != pending, (
            'A fresh explicit response was suppressed at a reused timing decision ID')
    pytest.fail('Optional timing choices did not reach the next decision')


@pytest.mark.parametrize('warbands_first', [False, True])
def test_ordered_rally_file_session_rejects_bad_count_then_saves_and_replays(tmp_path, capsys, warbands_first):
    state = _state()
    args = _save_session(tmp_path / 'live', state, rc.ARVERNI)
    assert llm_seat.cmd_play(args) == 0
    initial, meta, log = load_game(tmp_path / 'live' / 'save.json')
    pending = meta['assistant_session']['pending']
    assert decode(pending['request'])['kind'] == 'turn'
    args.response = json.dumps({'action': ACTION_COMMAND, 'player_action': _rally([_warbands(count=True)])})
    assert llm_seat.cmd_submit(args) == 0
    rejected, rejected_meta, rejected_log = load_game(tmp_path / 'live' / 'save.json')
    assert encode(rejected) == encode(initial)
    assert rejected_meta['assistant_session']['pending'] == pending
    assert rejected_meta['assistant_session']['journal'] == [] and rejected_log == log
    troop_step = _warbands(count=1)
    steps = [troop_step, _ally()] if warbands_first else [_ally(), troop_step]
    action = _rally(steps)
    args.response = json.dumps({'action': ACTION_COMMAND, 'player_action': action})
    assert llm_seat.cmd_submit(args) == 0
    _decline_timing_windows(args)
    final, final_meta, final_log = load_game(tmp_path / 'live' / 'save.json')
    assert count_pieces(final, rc.MANDUBII, rc.ARVERNI, rc.WARBAND) == 1
    assert count_pieces(final, rc.MANDUBII, rc.ARVERNI, rc.ALLY) == 1
    assert final['resources'][rc.ARVERNI] == 9
    assert final_log[0]['player_action'] == action
    assert not final_meta['assistant_session']['pending']
    args.output_dir = str(tmp_path / 'replay')
    assert llm_seat.cmd_replay(args) == 0
    replayed, _, _ = load_game(tmp_path / 'replay' / 'save.json')
    assert encode(replayed) == encode(final)
    assert 'Replay verified' in capsys.readouterr().out


def test_ordered_rally_preview_keeps_live_agent_queue_board_and_rng():
    state = _state()
    session = SeatSession(state, {'seat': rc.ARVERNI}, [], HumanTurnDisplay(io.StringIO()))
    state['decision_agent'] = session.reactive
    session.import_inbox([{'response': {'use_default': True}}])
    before, queued = encode(board_copy(state)), copy.deepcopy(session.data)
    ok, result, preview = preview_player_action(state, rc.ARVERNI, _rally([_warbands(), _ally()]))
    assert ok and not result['errors']
    assert count_pieces(preview, rc.MANDUBII, rc.ARVERNI, rc.WARBAND) == 1
    assert encode(board_copy(state)) == before and session.data == queued


@pytest.mark.parametrize('plan', [
    {'steps': None}, {'steps': {}}, {'steps': 'Mandubii'},
    {'steps': [_warbands()], 'warbands': []},
    {'steps': [rc.MANDUBII]}, {'steps': [{'region': [], 'action': 'place_warbands'}]},
    {'steps': [dict(_ally(), count=1)]},
])
def test_malformed_ordered_plan_is_rejected_by_turn_and_free_action_boundaries(plan):
    state = _state()
    action = _rally([])
    action['details']['rally_plan'] = plan
    before = encode(state)
    result = execute_decision(state, rc.ARVERNI, {'action': ACTION_COMMAND, 'player_action': action})
    assert not result['executed']
    assert validate_free_action_response(state, rc.ARVERNI, _grant(), action)
    assert encode(state) == before


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
def test_event_recruit_count_pending_save_resume_and_exact_replay(tmp_path, capsys, scenario):
    state = _state(rc.ROMANS, scenario)
    state['current_card'] = state['current_card_id'] = 34
    state['played_cards'] = [34]
    args = _save_session(tmp_path / 'live', state, rc.ROMANS)
    assert llm_seat.cmd_play(args) == 0
    initial, _, _ = load_game(tmp_path / 'live' / 'save.json')
    event = {'command': 'Event', 'sa': 'No SA', 'details': {
        'card_id': 34, 'text_preference': rc.EVENT_UNSHADED,
        'event_params': {'faction': rc.ROMANS}}}
    args.response = json.dumps({'action': ACTION_EVENT, 'player_action': event})
    assert llm_seat.cmd_submit(args) == 0
    _decline_timing_windows(args)
    paused, paused_meta, log = load_game(tmp_path / 'live' / 'save.json')
    pending = paused_meta['assistant_session']['pending']
    request = decode(pending['request'])
    assert request['kind'] == 'free_action' and request['request_type'] == 'event_rally'
    assert request['max_regions'] == 3
    assert encode(paused) == encode(initial)
    assert paused_meta['assistant_session']['journal'][0]['player_action'] == event
    assert all(entry.get('reactive') == 'voluntary_removal'
               for entry in paused_meta['assistant_session']['journal'][1:])
    assert log == []
    args.response = json.dumps(_recruit(1.0))
    assert llm_seat.cmd_submit(args) == 0
    rejected, rejected_meta, rejected_log = load_game(tmp_path / 'live' / 'save.json')
    assert encode(rejected) == encode(paused)
    assert rejected_meta['assistant_session']['pending'] == pending
    assert rejected_meta['assistant_session']['journal'] == paused_meta['assistant_session']['journal']
    assert rejected_log == []
    args.response = json.dumps(_recruit(1))
    assert llm_seat.cmd_submit(args) == 0
    _decline_timing_windows(args)
    final, final_meta, final_log = load_game(tmp_path / 'live' / 'save.json')
    assert count_pieces(final, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 1
    assert final['resources'][rc.ROMANS] == 10
    grants = [entry for entry in final_log if entry.get('reactive') == 'free_action']
    assert len(grants) == 1
    assert decode(grants[0]['assistant_response']) == _recruit(1)
    assert all(entry.get('reactive') in (None, 'voluntary_removal', 'free_action')
               for entry in final_log)
    assert not final_meta['assistant_session']['pending'] and not final_meta['assistant_session']['journal']
    args.output_dir = str(tmp_path / 'replay')
    assert llm_seat.cmd_replay(args) == 0
    replayed, _, _ = load_game(tmp_path / 'replay' / 'save.json')
    assert encode(replayed) == encode(final)
    assert 'Replay verified' in capsys.readouterr().out


def test_interrupted_exact_rally_failure_keeps_whole_turn_pending_then_replays(tmp_path, capsys):
    state = _state(rc.AEDUI)
    for region, tribe in ((rc.AEDUI_REGION, rc.TRIBE_AEDUI), (rc.SEQUANI, rc.TRIBE_SEQUANI)):
        place_piece(state, region, rc.AEDUI, rc.ALLY)
        state['tribes'][tribe].update(allied_faction=rc.AEDUI, status=None)
    place_piece(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND)
    refresh_all_control(state)
    action = _rally([])
    action.update(sa='Suborn', sa_timing='during', sa_regions=[rc.MANDUBII])
    action['details'].update(
        command_parts=[_rally([_warbands(rc.AEDUI_REGION, 1)]),
                       _rally([_warbands(rc.SEQUANI, 99)])],
        suborn_plan=[{'region': rc.MANDUBII, 'actions': [
            {'action': 'place', 'piece_type': rc.WARBAND, 'faction': rc.AEDUI}]}])
    live = tmp_path / 'live'
    args = _save_session(live, state, rc.AEDUI)
    assert llm_seat.cmd_play(args) == 0
    before, meta, log = load_game(live / 'save.json')
    pending = copy.deepcopy(meta['assistant_session']['pending'])
    args.response = json.dumps({'action': ACTION_COMMAND_SA, 'player_action': action})
    assert llm_seat.cmd_submit(args) == 0
    _decline_timing_windows(args)
    rejected, rejected_meta, rejected_log = load_game(live / 'save.json')
    # The invalid later exact quantity cannot commit the first Region or the
    # intervening Suborn, consume their pieces/Resources, or advance the turn.
    assert encode(rejected) == encode(before)
    assert rejected_meta['assistant_session']['pending'] == pending
    assert rejected_meta['assistant_session']['journal'] == [] and rejected_log == log == []
    assert rejected['resources'][rc.AEDUI] == 10
    assert count_pieces(rejected, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == 0
    assert count_pieces(rejected, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == 1

    action['details']['command_parts'][1] = _rally([_warbands(rc.SEQUANI, 1)])
    args.response = json.dumps({'action': ACTION_COMMAND_SA, 'player_action': action})
    assert llm_seat.cmd_submit(args) == 0
    _decline_timing_windows(args)
    final, final_meta, final_log = load_game(live / 'save.json')
    assert count_pieces(final, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == 1
    assert count_pieces(final, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == 1
    assert count_pieces(final, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == 2
    assert final['resources'][rc.AEDUI] == 7
    assert final_log[0]['player_action'] == action
    assert all(entry.get('reactive') == 'voluntary_removal' for entry in final_log[1:])
    assert not final_meta['assistant_session']['pending'] and not final_meta['assistant_session']['journal']
    args.output_dir = str(tmp_path / 'replay')
    assert llm_seat.cmd_replay(args) == 0
    replayed, _, _ = load_game(tmp_path / 'replay' / 'save.json')
    assert encode(replayed) == encode(final)
    assert 'Replay verified' in capsys.readouterr().out
