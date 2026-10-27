"""Only literal booleans select scoped Event defaults or decline choices."""
import copy
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine.free_actions import consult_free_action, validate_free_action_response
from fs_bot.engine.game_engine import _action_transaction
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def _state():
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=5)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA)
    return state


def _request(subtype):
    request = {'kind': 'free_action', 'request_type': subtype, 'allow_decline': True}
    if subtype == 'event_command':
        request.update(allowed_commands=[rc.CMD_MARCH], allowed_regions=[rc.MORINI],
                       free=True, with_sa=False)
    elif subtype == 'impetuosity_enemy_battle':
        request['attackers'] = [rc.ARVERNI, rc.BELGAE]
    return request


def _session():
    state = _state()
    session = SeatSession(state, {'seat': rc.ROMANS}, [], HumanTurnDisplay(io.StringIO()))
    state['decision_agent'] = session.reactive
    return session


def _attempt(session, request):
    def driver(*args):
        pass
    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    with _action_transaction(session.state, driver):
        # Event choices can follow changes and a die. Invalid input must
        # preserve that transaction's retry point, including the same roll.
        session.state['rng'].randint(rc.DIE_MIN, rc.DIE_MAX)
        session.state['resources'][rc.ROMANS] += 1
        return consult_free_action(session.state, rc.ROMANS, request)


@pytest.mark.parametrize('subtype', ['event_command', 'morasses_faction'])
@pytest.mark.parametrize('key', ['use_default', 'decline'])
@pytest.mark.parametrize('value', [1, 1.0, False, None, 'true'])
def test_invalid_sentinel_stays_pending_without_consuming_input_board_or_rng(subtype, key, value):
    session = _session()
    request = _request(subtype)
    before = encode(board_copy(session.state))
    with pytest.raises(DecisionPending):
        _attempt(session, request)
    pending = copy.deepcopy(session.data['pending'])
    payload = {'decision_id': pending['id'], 'response': {key: value}}
    session.import_inbox(payload)
    with pytest.raises(DecisionPending):
        _attempt(session, request)
    assert session.error
    assert session.data['pending'] == pending
    assert session.data['queue'] == [payload]
    assert session.data['journal'] == [] and session.log == []
    assert encode(board_copy(session.state)) == before


@pytest.mark.parametrize('subtype', ['event_command', 'morasses_faction'])
@pytest.mark.parametrize('key', ['use_default', 'decline'])
def test_literal_true_is_honored_and_recorded_by_durable_frontend(subtype, key):
    session = _session()
    before = session.state['rng'].getstate()
    response = {key: True}
    session.import_inbox([{'response': response}])
    result = _attempt(session, _request(subtype))
    session.finish()
    assert result == (None if key == 'use_default' else response)
    assert session.state['rng'].getstate() != before
    assert session.state['resources'][rc.ROMANS] == 1
    assert len(session.log) == 1
    assert not session.data['queue'] and not session.data['pending']


@pytest.mark.parametrize('subtype', ['event_command', 'morasses_faction', 'impetuosity_enemy_battle'])
@pytest.mark.parametrize('key', ['use_default', 'decline'])
@pytest.mark.parametrize('value', [1, 1.0])
def test_raw_callback_numeric_sentinel_raises_instead_of_using_policy(subtype, key, value):
    state = _state()
    state['decision_agent'] = lambda *args: {key: value}
    before = encode(board_copy(state))
    with pytest.raises(ValueError):
        consult_free_action(state, rc.ROMANS, _request(subtype))
    assert encode(board_copy(state)) == before


@pytest.mark.parametrize('key', ['use_default', 'decline'])
def test_sentinel_cannot_be_mixed_with_an_otherwise_legal_command(key):
    session = _session()
    request = _request('event_command')
    plan = {'command': rc.CMD_MARCH, 'regions': [rc.MORINI], 'sa': 'No SA',
            'sa_regions': [], 'details': {
                'origins': [rc.MORINI], 'destinations': [rc.NERVII],
                'routes': {rc.MORINI: [rc.NERVII]},
                'groups': {rc.MORINI: {rc.AUXILIA: 1, rc.LEADER: False}}}}
    assert validate_free_action_response(session.state, rc.ROMANS, request, plan) is None
    session.import_inbox([{'response': dict(plan, **{key: True})}])
    before = encode(board_copy(session.state))
    with pytest.raises(DecisionPending):
        _attempt(session, request)
    assert session.data['queue'][0]['response'] == dict(plan, **{key: True})
    assert session.data['pending']['id'] == 'd000001'
    assert session.data['journal'] == [] and session.log == []
    assert encode(board_copy(session.state)) == before


def test_specialized_required_attacker_still_cannot_decline_with_true():
    state = _state()
    request = _request('impetuosity_enemy_battle')
    state['decision_agent'] = lambda *args: {'use_default': True}
    assert consult_free_action(state, rc.ROMANS, request) is None
    state['decision_agent'] = lambda *args: {'decline': True}
    with pytest.raises(ValueError):
        consult_free_action(state, rc.ROMANS, request)
