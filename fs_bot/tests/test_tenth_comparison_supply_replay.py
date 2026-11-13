"""UI10-03 through a real interrupted Quarters phase and verified replay."""

from copy import deepcopy
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine.game_engine import _action_transaction
from fs_bot.engine.quarters import agreement_cache
from fs_bot.engine.winter import quarters_phase
from fs_bot.state.player_ownership import install
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, _decision_signatures, board_copy


def _position(multiple=True):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=11)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    place_piece(state, rc.ARVERNI_REGION, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND)
    if multiple:
        place_piece(state, rc.VENETI, rc.AEDUI, rc.WARBAND)
    state['resources'][rc.ROMANS] = 10
    install(state, {rc.ROMANS: 'Player 1', rc.AEDUI: 'Player 1'})
    return state


def _open(state, meta, log):
    session = SeatSession(state, meta, log, HumanTurnDisplay(StringIO()))
    state['decision_agent'] = session.reactive
    return session


def _attempt(session):
    def driver(*args):
        pass

    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    driver.transaction_complete = session.transaction_complete
    plan = {rc.ROMANS: [(rc.LEGION, rc.ARVERNI_REGION, rc.PROVINCIA, 1)]}
    with _action_transaction(session.state, driver):
        return quarters_phase(session.state, relocations=plan)


def _submit(session, response):
    session.import_inbox({'decision_id': session.data['pending']['id'], 'response': response})


def _pause_after_agreement(session):
    for _ in range(20):
        with pytest.raises(DecisionPending):
            _attempt(session)
        assert session.error is None
        if any(decode(entry['assistant_request']).get('request_type') == 'supply_line'
               for entry in session.data['journal']):
            return deepcopy(session.data['pending'])
        request = decode(session.data['pending']['request'])
        _submit(session, True if request.get('request_type') == 'supply_line'
                else {'use_default': True})
    pytest.fail('Quarters did not reach its post-agreement decision')


def _supply_entry(session):
    return next(entry for entry in session.data['journal']
                if decode(entry['assistant_request']).get('request_type') == 'supply_line')


def _worker(mode, path, multiple):
    if mode == 'record':
        state = _position(multiple)
        meta, log = {'seat': rc.ROMANS, 'player_id': 'Player 1'}, []
    else:
        state, meta, log = load_game(path, validate=True)
    before = encode(board_copy(state))
    session = _open(state, meta, log)
    if mode == 'record':
        pending = _pause_after_agreement(session)
        save_game(state, path, meta=meta, log=log)
    else:
        with pytest.raises(DecisionPending):
            _attempt(session)
        pending = session.data['pending']
    assert validate_state(state) == check_structural_integrity(state) == []
    assert encode(board_copy(state)) == before
    return {'error': session.error, 'pending': pending,
            'accepted': deepcopy(_supply_entry(session))}


@pytest.mark.parametrize('multiple', [True, False])
def test_quarters_supply_save_resumes_at_same_request_across_processes(tmp_path, multiple):
    root = Path(rc.__file__).resolve().parents[1]
    path = tmp_path / 'quarters.json'

    def run(mode, seed):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), mode, str(path), str(int(multiple))],
            cwd=root, env={**os.environ, 'PYTHONPATH': str(root), 'PYTHONHASHSEED': str(seed)},
            check=True, capture_output=True, text=True)
        return json.loads(result.stdout)

    first = run('record', 0)
    assert run('resume', 987) == run('resume', 0) == first
    request = decode(first['accepted']['assistant_request'])
    regions = [rc.VENETI, rc.AEDUI_REGION] if multiple else [rc.AEDUI_REGION]
    assert request['context'] == {'phase': 'quarters', 'region': regions[0], 'regions': regions}
    assert decode(first['pending']['request'])['window']['stage'] == 'after_payments'


@pytest.mark.parametrize('change', [None, 'board', 'rng', 'host', 'requester', 'region', 'type'])
def test_legacy_quarters_signature_requires_same_board_host_and_action(change):
    state = _position()
    before = encode(board_copy(state))
    session = _open(state, {'seat': rc.ROMANS, 'player_id': 'Player 1'}, [])
    pending = _pause_after_agreement(session)
    entry = _supply_entry(session)
    request = decode(entry['assistant_request'])
    legacy = dict(request, context={'region': rc.AEDUI_REGION})
    if change == 'host':
        legacy['faction'] = rc.BELGAE
    elif change == 'requester':
        legacy['requesting_faction'] = rc.BELGAE
    elif change == 'region':
        legacy['context']['region'] = rc.CARNUTES
    elif change == 'type':
        legacy['request_type'] = 'quarters'
    # Reconstruct the actual board at the earlier declaration. The phase
    # rolled back to this board, after its opening gift of zero Resources.
    old_signature, _ = _decision_signatures(state, legacy)
    entry['assistant_signature'] = old_signature
    entry['assistant_request'] = encode(legacy)
    if change == 'board':
        state['resources'][rc.ROMANS] += 1
    elif change == 'rng':
        state['rng'].random()
    if change in ('board', 'rng'):
        # Keep the opening resource decision valid on the changed board so
        # this case reaches and exercises the mismatched Supply signature.
        opening = session.data['journal'][0]
        opening['assistant_signature'], _ = _decision_signatures(
            state, decode(opening['assistant_request']))
    restart = encode(board_copy(state))
    with pytest.raises(DecisionPending):
        _attempt(session)
    assert session.data['pending'] == pending
    assert encode(board_copy(state)) == restart
    if change:
        assert session.error == 'Saved decision no longer matches its board/request; replay stopped.'
    else:
        assert session.error is None and restart == before
        assert _supply_entry(session) == entry


def test_verified_legacy_quarters_replay_retains_accepted_signature():
    state = _position()
    session = _open(state, {'seat': rc.ROMANS, 'player_id': 'Player 1'}, [])
    pending = _pause_after_agreement(session)
    entry = _supply_entry(session)
    legacy = dict(decode(entry['assistant_request']), context={'region': rc.AEDUI_REGION})
    entry['assistant_signature'], _ = _decision_signatures(state, legacy)
    entry['assistant_request'] = encode(legacy)
    replay_state = _position()
    replay = _open(replay_state, {'seat': rc.ROMANS, 'player_id': 'Player 1'}, [])
    journal = session.data['journal']
    replay.data['queue'] = [SeatSession._inbox_entry(record) for record in journal]
    replay.data['expected'] = [
        {'id': record['assistant_id'], 'signature': record['assistant_signature'],
         'request': record['assistant_request'], 'action_windows_version': 1}
        for record in journal]
    with pytest.raises(DecisionPending):
        _attempt(replay)
    assert replay.error is None
    assert replay.data['pending'] == pending
    assert _supply_entry(replay)['assistant_signature'] == entry['assistant_signature']
    for live in (session, replay):
        _submit(live, {'use_default': True})
        result = _attempt(live)
        assert result['roman_relocation'] == [(rc.LEGION, rc.ARVERNI_REGION, rc.PROVINCIA, 1)]
        assert count_pieces(live.state, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == 1
        assert validate_state(live.state) == check_structural_integrity(live.state) == []
    assert encode(board_copy(replay_state)) == encode(board_copy(state))


def test_ordinary_supply_and_quarters_hosting_remain_region_specific():
    state = _position()
    with agreement_cache(state):
        for request_type in ('quarters', 'supply_line'):
            request = {'kind': 'agreement', 'request_type': request_type,
                       'requesting_faction': rc.ROMANS, 'faction': rc.AEDUI,
                       'context': {'region': rc.AEDUI_REGION}}
            alternative = dict(request, context={'region': rc.VENETI})
            signature, _ = _decision_signatures(state, alternative)
            _, compatible = _decision_signatures(state, request)
            assert signature not in compatible


if __name__ == '__main__':
    print(json.dumps(_worker(sys.argv[1], Path(sys.argv[2]), bool(int(sys.argv[3]))),
                     sort_keys=True))
