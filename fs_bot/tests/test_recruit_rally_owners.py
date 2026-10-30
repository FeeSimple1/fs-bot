"""A1.4 exact physical placements survive previews, consent and saved replay."""

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
from fs_bot.engine.diviciacus import (KEY, PLACEMENT_SELECTION, force_scope,
                                      placement_owner_request)
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_COMMAND
from fs_bot.engine.moves import preview_player_action
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state
from fs_bot.tools import llm_seat
from fs_bot.tools.seat_session import SeatSession, board_copy


def _state(faction):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=11)
    state['non_player_factions'] = {rc.BELGAE, rc.GERMANS}
    state['resources'][faction] = 10
    place_piece(state, rc.SEQUANI, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND)
    if faction == rc.ROMANS:
        place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 18)
        place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
        place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    else:
        place_piece(state, rc.MORINI, rc.AEDUI, rc.WARBAND, 18)
        for region, tribe in ((rc.SEQUANI, rc.TRIBE_SEQUANI), (rc.AEDUI_REGION, rc.TRIBE_AEDUI)):
            place_piece(state, region, rc.AEDUI, rc.ALLY)
            state['tribes'][tribe].update(allied_faction=rc.AEDUI, status=None)
        # Romans lend under §8.8.8 only when Aedui are not currently winning.
        for region, tribe in ((rc.MORINI, rc.TRIBE_MORINI), (rc.MORINI, rc.TRIBE_MENAPII),
                              (rc.NERVII, rc.TRIBE_NERVII)):
            place_piece(state, region, rc.GERMANS, rc.ALLY)
            state['tribes'][tribe].update(allied_faction=rc.GERMANS, status=None)
        state['non_player_factions'].add(rc.ROMANS)
    refresh_all_control(state)
    return state


def _action(faction, *, explicit=True):
    roman = faction == rc.ROMANS
    other = rc.AEDUI if roman else rc.ROMANS
    entries = [{'region': rc.SEQUANI, 'action': 'place_auxilia' if roman else 'place_warbands',
                'count': 1},
               {'region': rc.PROVINCIA if roman else rc.AEDUI_REGION,
                'action': 'place_auxilia' if roman else 'place_warbands', 'count': 1}]
    if explicit:
        entries[0]['placement_owners'] = {faction: 0, other: 1}
    plan = {'recruit_plan': entries} if roman else {'rally_plan': {'steps': entries}}
    return {'command': 'Recruit' if roman else 'Rally', 'sa': 'No SA',
            'details': dict(plan, diviciacus_regions=[rc.SEQUANI])}


def _decline_timing_windows(args):
    """Answer optional removal explicitly without bypassing durable requests."""
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


@pytest.mark.parametrize('faction,piece', [(rc.ROMANS, rc.AUXILIA), (rc.AEDUI, rc.WARBAND)])
def test_owner_request_is_pure_and_never_offers_unscoped_pool(faction, piece):
    state = _state(faction)
    before = encode(state)
    assert placement_owner_request(state, rc.SEQUANI, faction, piece, 1) is None
    with force_scope(state, faction, [rc.SEQUANI]):
        scoped = encode(state)
        request = placement_owner_request(state, rc.SEQUANI, faction, piece, 1)
        assert request['available'][faction] == 1
        assert request['kind'] == 'diviciacus_pieces' and request['phase'] == 'placement'
        assert placement_owner_request(state, rc.PROVINCIA, faction, piece, 1) is None
        assert encode(state) == scoped
    assert encode(state) == before


@pytest.mark.parametrize('faction', [rc.ROMANS, rc.AEDUI])
def test_explicit_owners_preserve_native_pool_for_later_region_in_preview_and_execution(faction):
    state = _state(faction)
    calls = []
    state['decision_agent'] = lambda st, actor, request: calls.append(request) or True
    before = encode(board_copy(state))
    action = _action(faction)
    ok, result, preview = preview_player_action(state, faction, action)
    assert ok and not result['errors']
    assert encode(board_copy(state)) == before and calls == []
    result = execute_decision(state, faction, {'action': ACTION_COMMAND, 'player_action': action})
    assert result['executed'] and not result['errors']
    assert all(request['kind'] != 'diviciacus_pieces' for request in calls)
    assert encode(board_copy(state)) == encode(board_copy(preview))
    own, other = ((rc.AUXILIA, rc.WARBAND) if faction == rc.ROMANS else (rc.WARBAND, rc.AUXILIA))
    partner = rc.AEDUI if faction == rc.ROMANS else rc.ROMANS
    later = rc.PROVINCIA if faction == rc.ROMANS else rc.AEDUI_REGION
    assert count_pieces(state, rc.SEQUANI, partner, other) == 2
    assert count_pieces(state, rc.SEQUANI, faction, own) == 1
    assert count_pieces(state, later, faction, own) == 1
    assert KEY not in state and PLACEMENT_SELECTION not in state


@pytest.mark.parametrize('owners', [None, True, 'Romans', {}, {rc.ROMANS: True},
    {rc.ROMANS: 1.0}, {rc.BELGAE: 1}, {rc.ROMANS: -1}, {rc.ROMANS: 2}, {rc.ROMANS: 99}])
def test_bad_physical_owner_mapping_cannot_partially_place(owners):
    state = _state(rc.AEDUI)
    action = _action(rc.AEDUI)
    action['details']['rally_plan']['steps'][0]['placement_owners'] = owners
    before = encode(state)
    result = execute_decision(state, rc.AEDUI, {'action': ACTION_COMMAND, 'player_action': action})
    assert not result['executed']
    assert encode(state) == before
    assert PLACEMENT_SELECTION not in state


def test_explicit_owners_never_bypass_refused_cooperation():
    state = _state(rc.ROMANS)
    calls = []
    state['decision_agent'] = lambda st, faction, request: calls.append(request) or False
    before = encode(board_copy(state))
    result = execute_decision(state, rc.ROMANS,
        {'action': ACTION_COMMAND, 'player_action': _action(rc.ROMANS)})
    assert not result['executed'] and 'refused' in result['reason']
    assert len(calls) == 1 and calls[0]['request_type'] == 'diviciacus'
    assert encode(board_copy(state)) == before


def test_unscoped_owner_mapping_rejected_before_placement():
    state = _state(rc.AEDUI)
    action = _action(rc.AEDUI)
    action['details']['diviciacus_regions'] = []
    before = encode(state)
    result = execute_decision(state, rc.AEDUI, {'action': ACTION_COMMAND, 'player_action': action})
    assert not result['executed']
    assert encode(state) == before


@pytest.mark.parametrize('explicit', [False, True])
def test_owner_choice_saved_session_rollback_resume_and_replay(tmp_path, capsys, explicit):
    state = _state(rc.AEDUI)
    state['current_card'] = state['current_card_id'] = 16
    state['played_cards'], state['deck'], state['next_card'] = [16], [], None
    for faction in state['eligibility']:
        state['eligibility'][faction] = rc.ELIGIBLE if faction == rc.AEDUI else rc.INELIGIBLE
    live = tmp_path / 'live'
    live.mkdir()
    display = HumanTurnDisplay(io.StringIO())
    display.remember(state, [rc.AEDUI])
    meta = {'seat': rc.AEDUI, 'scenario': state['scenario'], 'seed': 11,
            'human_snapshots': encode(display.snapshots)}
    SeatSession(state, meta, [], display)
    save_game(state, live / 'save.json', meta=meta, log=[])
    args = SimpleNamespace(dir=str(live))
    assert llm_seat.cmd_play(args) == 0
    before, before_meta, _ = load_game(live / 'save.json')
    action = _action(rc.AEDUI, explicit=explicit)
    if explicit:
        stale = copy.deepcopy(action)
        stale['details']['rally_plan']['steps'][0]['placement_owners'] = {rc.ROMANS: 2}
        args.response = json.dumps({'action': ACTION_COMMAND, 'player_action': stale})
        assert llm_seat.cmd_submit(args) == 0
        _decline_timing_windows(args)
        rejected, rejected_meta, rejected_log = load_game(live / 'save.json')
        assert encode(rejected) == encode(before)
        assert rejected_meta['assistant_session']['pending'] == before_meta['assistant_session']['pending']
        assert rejected_meta['assistant_session']['journal'] == [] and rejected_log == []
    args.response = json.dumps({'action': ACTION_COMMAND, 'player_action': action})
    assert llm_seat.cmd_submit(args) == 0
    _decline_timing_windows(args)
    if not explicit:
        paused, meta, log = load_game(live / 'save.json')
        pending = copy.deepcopy(meta['assistant_session']['pending'])
        request = decode(pending['request'])
        assert request['kind'] == 'diviciacus_pieces' and request['phase'] == 'placement'
        assert encode(paused) == encode(before)
        assert meta['assistant_session']['journal'][0]['player_action'] == action
        assert all(entry.get('reactive') == 'voluntary_removal'
                   for entry in meta['assistant_session']['journal'][1:])
        assert log == []
        args.response = json.dumps({'counts': {rc.ROMANS: 1.0, rc.AEDUI: 0}})
        assert llm_seat.cmd_submit(args) == 0
        rejected, rejected_meta, _ = load_game(live / 'save.json')
        assert encode(rejected) == encode(paused)
        assert rejected_meta['assistant_session']['pending'] == pending
        args.response = json.dumps({'counts': {rc.ROMANS: 1, rc.AEDUI: 0}})
        assert llm_seat.cmd_submit(args) == 0
        _decline_timing_windows(args)
    final, meta, log = load_game(live / 'save.json')
    assert count_pieces(final, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(final, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == 1
    assert log[0]['player_action'] == action
    owner_choices = [entry for entry in log if entry.get('reactive') == 'diviciacus_pieces']
    assert len(owner_choices) == (0 if explicit else 1)
    assert all(entry.get('reactive') in (None, 'voluntary_removal', 'diviciacus_pieces')
               for entry in log)
    assert not meta['assistant_session']['pending'] and not meta['assistant_session']['journal']
    assert KEY not in final and PLACEMENT_SELECTION not in final
    args.output_dir = str(tmp_path / 'replay')
    assert llm_seat.cmd_replay(args) == 0
    replayed, _, _ = load_game(tmp_path / 'replay' / 'save.json')
    assert encode(replayed) == encode(final)
    assert 'Replay verified' in capsys.readouterr().out
