"""An empty Supply scope is not a new promise or a changed human decision."""
import contextlib
import hashlib
import importlib.util
import io
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fs_bot import rules_consts as rc
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.state.serialize import encode, load_game
from fs_bot.state.state_schema import build_initial_state
from fs_bot.tools.seat_session import (
    DecisionPending, SeatSession, board_copy, fingerprint,
)


KEY = '_supply_line_agreements'
MISSING = object()


def _state(cache=MISSING):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=19)
    if cache is not MISSING:
        state[KEY] = deepcopy(cache)
    return state


def _request():
    return {'kind': 'agreement', 'request_type': 'supply_line',
            'requesting_faction': rc.ROMANS,
            'context': {'region': rc.SEQUANI}, 'faction': rc.AEDUI}


def _session(state, saved_state, mode, *, saved_request=None):
    request = _request() if saved_request is None else saved_request
    signature = fingerprint({'board': board_copy(saved_state), 'request': request})
    session = SeatSession(state, {'seat': rc.AEDUI}, [], HumanTurnDisplay(io.StringIO()))
    entry = {'assistant_id': 'd000001', 'assistant_signature': signature,
             'assistant_request': encode(request), 'assistant_response': True}
    if mode == 'journal':
        session.data['journal'] = [deepcopy(entry)]
    else:
        session.data['expected'] = [{'id': entry['assistant_id'], 'signature': signature}]
        session.data['queue'] = [{'decision_id': entry['assistant_id'], 'response': True}]
    return session, entry


@pytest.mark.parametrize('mode', ['journal', 'expected'])
@pytest.mark.parametrize('saved_empty', [False, True])
@pytest.mark.parametrize('live_empty', [False, True])
def test_absent_and_empty_supply_cache_preserve_old_decision_identity(
        mode, saved_empty, live_empty):
    saved = _state({} if saved_empty else MISSING)
    live = _state({} if live_empty else MISSING)
    session, entry = _session(live, saved, mode)
    before = encode(live)
    assert session.ask(live, rc.AEDUI, _request()) is True
    assert session.data['journal'][0]['assistant_id'] == entry['assistant_id']
    assert session.data['journal'][0]['assistant_signature'] == entry['assistant_signature']
    assert session.cursor == 1 and encode(live) == before


@pytest.mark.parametrize('mode', ['journal', 'expected'])
@pytest.mark.parametrize('saved_cache,live_cache', [
    (MISSING, {(rc.ROMANS, rc.AEDUI, rc.SEQUANI): True}),
    ({(rc.ROMANS, rc.AEDUI, rc.SEQUANI): True}, MISSING),
    ({(rc.ROMANS, rc.AEDUI, rc.SEQUANI): True},
     {(rc.ROMANS, rc.AEDUI, rc.PROVINCIA): True}),
    (None, MISSING), (False, {}), ([], {}),
])
def test_nonempty_or_malformed_cache_is_never_equivalent_to_empty(
        mode, saved_cache, live_cache):
    saved, live = _state(saved_cache), _state(live_cache)
    session, _ = _session(live, saved, mode)
    before = encode(live), deepcopy(session.data)
    with pytest.raises(DecisionPending):
        session.ask(live, rc.AEDUI, _request())
    assert session.cursor == 0
    assert (encode(live), session.data) == before
    assert session.error


@pytest.mark.parametrize('mode', ['journal', 'expected'])
@pytest.mark.parametrize('change', ['request', 'resources', 'rng'])
def test_empty_cache_compatibility_does_not_hide_stale_board_or_request(mode, change):
    saved, live = _state(), _state({})
    session, _ = _session(live, saved, mode)
    request = _request()
    if change == 'request':
        request['context']['region'] = rc.PROVINCIA
    elif change == 'resources':
        live['resources'][rc.ROMANS] += 1
    else:
        live['rng'].randint(1, 6)
    before = encode(live), deepcopy(session.data)
    with pytest.raises(DecisionPending):
        session.ask(live, rc.AEDUI, request)
    assert session.cursor == 0
    assert (encode(live), session.data) == before


def test_archived_frumentum_replays_without_rewriting_any_old_evidence():
    fixtures = Path(__file__).parent / 'fixtures/compatibility_8ef88e2'
    manifest = json.loads((fixtures / 'manifest.json').read_text())
    path = fixtures / 'pending-frumentum.json'
    evidence = manifest['fixtures'][path.name]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == evidence['file_sha256']
    spec = importlib.util.spec_from_file_location('old_frumentum_driver', fixtures / 'generate.py')
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    state, meta, log = load_game(path, validate=True)
    accepted = deepcopy(meta['assistant_session']['journal'])
    with contextlib.redirect_stdout(io.StringIO()):
        result = driver.continue_fixture(evidence['kind'], state, meta, log)
    assert driver.digest(result) == evidence['continued_sha256']
    assert result['log'][:len(accepted)] == accepted
    assert hashlib.sha256(path.read_bytes()).hexdigest() == evidence['file_sha256']
