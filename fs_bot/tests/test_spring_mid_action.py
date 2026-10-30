"""Pax entry helpers preserve human timing, live gates, and pure previews."""
from copy import deepcopy
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import find_leader, get_leader_in_region, remove_piece
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine.agent import AGREEMENT, consult_agent
from fs_bot.engine.game_engine import _action_transaction
from fs_bot.engine.spring import (
    UNLOCK_KEY, atomic, mid_action_request, preview_mid_action_entry,
    resolve_mid_action_entry, resolve_spring_box_entry, spring_box_request,
)
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def _state():
    state = setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=31)
    state['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE}
    state[UNLOCK_KEY] = True
    state.pop('first_winter_special', None)
    state['winter_count'] = 1
    state['current_card'] = state['current_card_id'] = 10
    return state


def _window():
    return {'phase': 'command', 'faction': rc.ROMANS,
            'command': rc.CMD_BATTLE, 'region': rc.SEQUANI, 'step': 'losses'}


def _board(state):
    return encode({key: value for key, value in state.items()
                   if key != 'decision_agent'})


def test_nested_atomic_pause_restores_live_card_cursor_identity_and_contents():
    state = _state()
    cursor = {'phase': 'actions', 'decisions': [{'faction': rc.ROMANS}]}
    state['_card_turn'] = cursor
    agent = object()
    state['decision_agent'] = agent
    before = _board(state)

    class Paused(BaseException):
        pass

    with pytest.raises(Paused):
        with atomic(state):
            state['rng'].random()
            cursor['decisions'].append({'faction': rc.ARVERNI})
            with atomic(state):
                state['_card_turn'] = {'phase': 'changed'}
                state['resources'][rc.ROMANS] = 0
                raise Paused()

    assert state['_card_turn'] is cursor
    assert cursor == {'phase': 'actions', 'decisions': [{'faction': rc.ROMANS}]}
    assert state['decision_agent'] is agent
    assert _board(state) == before


def test_entry_offer_is_pure_and_does_not_change_legacy_request_shape():
    state = _state()
    state['decision_agent'] = lambda *args: pytest.fail('Offer consumed human input')
    before, window = _board(state), _window()
    request = mid_action_request(state, window)
    assert request == dict(spring_box_request(state), window=window)
    assert 'window' not in spring_box_request(state)
    window['step'] = 'changed by caller'
    assert request['window']['step'] == 'losses'
    assert request['faction'] == rc.ARVERNI and request['can_defer']
    assert rc.CARNUTES in request['legal_regions']
    assert _board(state) == before


@pytest.mark.parametrize('context', [
    {'phase': 'command', 'faction': rc.ROMANS, 'step': 'region'},
    {'phase': 'event', 'faction': rc.BELGAE, 'step': 'effect'},
    {'phase': 'winter', 'step': 'victory'},
    {'phase': 'winter', 'step': 'quarters'},
    {'phase': 'winter', 'step': 'harvest'},
    {'phase': 'winter', 'step': 'spring'},
])
def test_unlocked_human_entry_is_not_limited_to_own_turn_or_non_winter(context):
    state = _state()
    state['eligibility'][rc.ARVERNI] = rc.INELIGIBLE
    if context['phase'] == 'winter':
        state['current_card'] = rc.WINTER_CARD
    request = mid_action_request(state, context)
    resources, eligibility = deepcopy(state['resources']), deepcopy(state['eligibility'])
    rng = state['rng'].getstate()
    result = resolve_mid_action_entry(state, request, {'region': rc.CARNUTES})
    assert result['region'] == rc.CARNUTES
    assert get_leader_in_region(state, rc.CARNUTES, rc.ARVERNI) == rc.VERCINGETORIX
    assert state['resources'] == resources and state['eligibility'] == eligibility
    assert state['rng'].getstate() == rng
    assert mid_action_request(state, context) is None
    assert validate_state(state) == []


def test_no_response_defers_without_consulting_agent_or_using_bot_tie_break():
    state = _state()
    state['decision_agent'] = lambda *args: pytest.fail('Resolver consulted human input')
    before = _board(state)
    result = resolve_mid_action_entry(state, mid_action_request(state, _window()))
    assert result['deferred'] is True
    assert _board(state) == before
    assert mid_action_request(state, dict(_window(), step='counterattack')) is not None


def test_explicit_default_retains_existing_placement_priorities_and_rng():
    state = _state()
    legacy = deepcopy(state)
    result = resolve_mid_action_entry(
        state, mid_action_request(state, _window()), {'use_default': True})
    assert result == resolve_spring_box_entry(legacy, {'use_default': True})
    assert encode(state) == encode(legacy)


@pytest.mark.parametrize('gate', ['first_spring', 'first_winter', 'interlude',
                                 'interlude_spring', 'expansion', 'np',
                                 'preview', 'ended', 'removed'])
def test_illegal_or_non_human_windows_do_not_offer_or_mutate(gate):
    state = _state()
    if gate in {'first_spring', 'first_winter'}:
        state = setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=31)
        state['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE}
        state['winter_count'] = 1
        if gate == 'first_winter':
            state['current_card'] = rc.WINTER_CARD
    elif gate in {'interlude', 'interlude_spring'}:
        state.pop(UNLOCK_KEY)
        state['winter_count'] = 3
        state['interlude_completed'] = True
        state['first_winter_special'] = {'place_vercingetorix_in_spring': True}
        if gate == 'interlude_spring':
            state['current_card'] = rc.WINTER_CARD
        else:
            state['scenario'] = rc.SCENARIO_GALLIC_WAR
    elif gate == 'expansion':
        state['scenario'] = rc.SCENARIO_ARIOVISTUS
    elif gate == 'np':
        state['non_player_factions'].add(rc.ARVERNI)
    elif gate == 'preview':
        state['_diviciacus_preview'] = True
    elif gate == 'ended':
        state['_resolved_card'] = {'game_over': True}
    elif gate == 'removed':
        resolve_spring_box_entry(state, {'region': rc.SEQUANI})
        remove_piece(state, rc.SEQUANI, rc.ARVERNI, rc.LEADER)
    before = encode(state)
    assert mid_action_request(state, _window()) is None
    assert encode(state) == before


def test_legacy_later_pax_entry_can_materialize_unlock_without_entering():
    state = _state()
    state.pop(UNLOCK_KEY)
    request = mid_action_request(state, _window())
    assert request is not None
    assert resolve_mid_action_entry(state, request)['deferred']
    assert state[UNLOCK_KEY] is True
    state['current_card'] = rc.WINTER_CARD
    assert mid_action_request(state, {'phase': 'winter', 'step': 'victory'}) is not None


@pytest.mark.parametrize('response', [
    {'region': rc.CISALPINA}, {'region': 'not a Region'}, {'defer': 1},
    {'region': rc.CARNUTES, 'defer': True}, {'use_default': 1},
])
def test_rejected_response_preserves_state_and_rng(response):
    state = _state()
    request = mid_action_request(state, _window())
    before = encode(state)
    with pytest.raises(ValueError):
        resolve_mid_action_entry(state, request, response)
    assert encode(state) == before


@pytest.mark.parametrize('change', ['unlock', 'seat', 'request', 'placed'])
def test_stale_or_forged_request_cannot_place(change):
    state = _state()
    request = mid_action_request(state, _window())
    if change == 'unlock':
        state[UNLOCK_KEY] = False
    elif change == 'seat':
        state['non_player_factions'].add(rc.ARVERNI)
    elif change == 'request':
        request['legal_regions'].append(rc.CISALPINA)
    else:
        resolve_spring_box_entry(state, {'region': rc.SEQUANI})
    before = encode(state)
    with pytest.raises(ValueError, match='opportunity has changed'):
        resolve_mid_action_entry(state, request, {'region': rc.CARNUTES})
    assert encode(state) == before


def test_gallia_togata_never_admits_arverni_to_cisalpina():
    state = _state()
    state['markers'].setdefault(rc.CISALPINA, {})[rc.MARKER_GALLIA_TOGATA] = True
    assert rc.CISALPINA not in mid_action_request(state, _window())['legal_regions']


@pytest.mark.parametrize('preview_flag', [False, True])
@pytest.mark.parametrize('response', [{'region': rc.CARNUTES}, {'defer': True}])
def test_explicit_preview_simulates_only_on_detached_state_without_input_or_rng(
        preview_flag, response):
    state = _state()
    request = mid_action_request(state, _window())
    state['decision_agent'] = lambda *args: pytest.fail('Preview consumed input')
    if preview_flag:
        state['_diviciacus_preview'] = True
    before, rng = _board(state), state['rng'].getstate()
    preview, result = preview_mid_action_entry(state, request, response)
    assert _board(state) == before
    assert preview is not state and 'decision_agent' not in preview
    assert preview['rng'].getstate() == rng
    assert preview.get('_diviciacus_preview', False) is preview_flag
    if 'region' in response:
        assert result['region'] == rc.CARNUTES
        assert find_leader(preview, rc.ARVERNI) == rc.CARNUTES
        assert find_leader(state, rc.ARVERNI) is None
        assert validate_state(preview) == []
    else:
        assert result['deferred'] is True
        assert encode(preview) == before


def test_preview_requires_an_explicit_choice_instead_of_default_rng():
    state = _state()
    request = mid_action_request(state, _window())
    before = encode(state)
    with pytest.raises(ValueError, match='explicit Region or deferral'):
        preview_mid_action_entry(state, request, {'use_default': True})
    assert encode(state) == before


def _session(state, meta=None, log=None):
    meta = meta if meta is not None else {'seat': rc.ARVERNI,
                                         'scenario': state['scenario'], 'seed': 31}
    session = SeatSession(state, meta, log if log is not None else [],
                          HumanTurnDisplay(io.StringIO()))
    state['decision_agent'] = session.reactive
    def driver(*args):
        pass
    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    return session, driver


def _entry_then_reactive_choice(state, driver):
    """Exercise the caller-owned transaction without a command-specific hook."""
    with _action_transaction(state, driver):
        state['resources'][rc.ROMANS] -= 1
        request = mid_action_request(state, _window())
        response = consult_agent(state, rc.ARVERNI, request)
        result = resolve_mid_action_entry(state, request, response)
        agreement = consult_agent(state, rc.ARVERNI, {
            'kind': AGREEMENT, 'request_type': 'retreat_into_control',
            'requesting_faction': rc.ROMANS, 'context': {'region': rc.SEQUANI}})
        return result, agreement


@pytest.mark.parametrize('response', [{'region': rc.CARNUTES}, {'defer': True}])
def test_accepted_mid_action_entry_survives_later_pending_save_and_exact_replay(
        tmp_path, response):
    state = _state()
    origin, before = deepcopy(state), encode(state)
    session, driver = _session(state)
    session.import_inbox([{'response': response}])
    with pytest.raises(DecisionPending):
        _entry_then_reactive_choice(state, driver)
    assert encode(board_copy(state)) == before
    assert len(session.data['journal']) == 1 and not session.log
    accepted = deepcopy(session.data['journal'][0])
    assert decode(accepted['assistant_request'])['window'] == _window()
    pending = deepcopy(session.data['pending'])
    assert pending['id'] == 'd000002'
    assert decode(pending['request'])['kind'] == AGREEMENT
    # The paused board describes the point after the already accepted entry;
    # the action state remains rolled back until all choices can finish.
    paused_board = decode(pending['board'])
    assert paused_board['resources'][rc.ROMANS] == state['resources'][rc.ROMANS] - 1
    assert (find_leader(paused_board, rc.ARVERNI) == rc.CARNUTES) is ('region' in response)
    save_game(state, tmp_path / 'entry.json', meta=session.meta, log=session.log)
    restored, meta, log = load_game(tmp_path / 'entry.json', validate=True)
    resumed, resumed_driver = _session(restored, meta, log)
    resumed.import_inbox({'decision_id': pending['id'], 'response': True})
    result = _entry_then_reactive_choice(restored, resumed_driver)
    resumed.finish()
    assert resumed.log[0] == accepted
    assert len(resumed.log) == 2 and not resumed.data['pending']
    replay, replay_driver = _session(origin)
    replay.data['queue'] = [SeatSession._inbox_entry(e) for e in resumed.log]
    replay.data['expected'] = [{'id': e['assistant_id'], 'signature': e['assistant_signature'],
                               'request': e['assistant_request'],
                               'action_windows_version': e.get('assistant_action_windows_version', 0)}
                               for e in resumed.log]
    assert _entry_then_reactive_choice(origin, replay_driver) == result
    replay.finish()
    assert encode(board_copy(origin)) == encode(board_copy(restored))
    assert replay.log == resumed.log


def test_invalid_mid_action_destination_stays_pending_without_state_or_rng_change():
    state = _state()
    before = encode(state)
    session, driver = _session(state)
    session.import_inbox([{'response': {'region': rc.CISALPINA}}])
    with pytest.raises(DecisionPending):
        _entry_then_reactive_choice(state, driver)
    assert encode(board_copy(state)) == before
    assert not session.data['journal'] and not session.log
    assert session.data['pending']['id'] == 'd000001'
    assert decode(session.data['pending']['request'])['window'] == _window()
    session.import_inbox({'decision_id': 'd000001', 'response': {'region': rc.CARNUTES}})
    with pytest.raises(DecisionPending):
        _entry_then_reactive_choice(state, driver)
    assert session.data['pending']['id'] == 'd000002'
    assert encode(board_copy(state)) == before
