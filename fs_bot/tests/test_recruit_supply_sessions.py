"""Supply consent precedes NP Recruit effects and survives durable pauses.

§§1.5.2/3.2.1 allow refusal before Recruit; accepted agreements bind for
the action. §8.8.4 evaluates the actual Build plus Recruit continuation.
"""
import copy
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.bots.roman_bot import node_r_recruit
from fs_bot.cards.capabilities import activate_capability, deactivate_capability
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_COMMAND_SA, _action_transaction
from fs_bot.engine.recruit_planning import ANSWERS, CANDIDATE, CONFIRMATIONS, QUERIES
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def _state(*, second_controller=False):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=17)
    state['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE}
    state['resources'][rc.ROMANS] = 20
    state['current_card'] = state['current_card_id'] = 'A34'
    state['_command_with_sa'] = True
    state['_command_region_scope'] = {rc.SEQUANI, rc.MANDUBII}
    for region in (rc.SEQUANI, rc.MANDUBII):
        place_piece(state, region, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    # All Supply chains must reach human German-controlled Provincia:
    # game-run Arverni never consent at the other Ariovistus endpoint.
    place_piece(state, rc.PROVINCIA, rc.GERMANS, rc.WARBAND, 12)
    place_piece(state, rc.CISALPINA, rc.ARVERNI, rc.WARBAND)
    if second_controller:
        place_piece(state, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 4)
    refresh_all_control(state)
    activate_capability(state, 13, rc.EVENT_SHADED)
    return state


def _session(state=None, meta=None, log=None):
    state = _state() if state is None else state
    meta = {'seat': rc.GERMANS, 'scenario': state['scenario'], 'seed': 17} if meta is None else meta
    session = SeatSession(state, meta, [] if log is None else log, HumanTurnDisplay(io.StringIO()))
    state['decision_agent'] = session.reactive
    return session


def _driver(session):
    def driver(*args):
        pass
    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    return driver


def _run(session):
    from fs_bot.engine.recruit_planning import plan_with_recruit_supply
    with _action_transaction(session.state, _driver(session)):
        action = plan_with_recruit_supply(session.state, node_r_recruit)
        result = execute_decision(session.state, rc.ROMANS, {
            'action': ACTION_COMMAND_SA, 'bot_action': action})
    session.finish()
    return result


def _board(state):
    return encode(board_copy(state))


def _pending(session, before, *, potential_allies=2):
    assert _board(session.state) == before
    pending = session.data['pending']
    request = decode(pending['request'])
    assert request['kind'] == 'agreement'
    assert request['request_type'] == 'supply_line'
    assert request['requesting_faction'] == rc.ROMANS
    assert request['faction'] == rc.GERMANS
    assert request['context']['region'] in (rc.PROVINCIA, rc.SEQUANI)
    proposed = request['context']['proposed_action']
    assert proposed['command'] == rc.CMD_RECRUIT and proposed['sa'] == rc.SA_BUILD
    assert proposed['details']['potential_allies'] == potential_allies
    shown = decode(pending['board'])
    original = decode(before)
    # The pending board must precede every Build/Scout/Recruit effect.
    for field in ('spaces', 'tribes', 'available', 'resources'):
        assert shown[field] == original[field]
    assert shown['rng'].getstate() == original['rng'].getstate()
    return copy.deepcopy(pending)


def _assert_clean(state):
    assert '_supply_line_agreements' not in state
    assert '_supply_line_query' not in state
    assert not any(key in state for key in (ANSWERS, CONFIRMATIONS, QUERIES))
    assert check_structural_integrity(state) == []


def _replay(initial, entries):
    replay = _session(decode(initial))
    replay.data['expected'] = [{'id': entry['assistant_id'], 'signature': entry['assistant_signature']}
                               for entry in entries]
    replay.import_inbox([replay._inbox_entry(entry) for entry in entries])
    result = _run(replay)
    assert replay.log == entries
    assert not replay.data['pending'] and not replay.data['queue'] and not replay.data['journal']
    return replay, result


def test_recruit_forecast_never_consumes_live_supply_input_or_rng():
    session = _session()
    calls = []
    def observed(board, faction, request):
        calls.append((board is session.state, faction, request))
        return session.reactive(board, faction, request)
    session.state['decision_agent'] = observed
    session.import_inbox([{'response': False}])
    before, queue = _board(session.state), copy.deepcopy(session.data['queue'])
    first = node_r_recruit(session.state)
    second = node_r_recruit(session.state)
    assert first == second and first['command'] == rc.CMD_RECRUIT
    assert first['details']['potential_allies'] == 2
    assert _board(session.state) == before
    assert calls == []
    assert session.data['queue'] == queue
    assert session.data['pending'] is None and session.data['journal'] == session.log == []


@pytest.mark.parametrize('response', [None, 1, 1.0, 'true', {'agree': True}, {'use_default': 1}])
def test_invalid_supply_consent_keeps_pending_board_rng_and_inbox(response):
    session = _session()
    before = _board(session.state)
    with pytest.raises(DecisionPending):
        _run(session)
    pending = _pending(session, before)
    with pytest.raises(ValueError, match='current pending decision'):
        session.import_inbox({'decision_id': 'd999999', 'response': True})
    assert session.data['pending'] == pending
    payload = {'decision_id': pending['id'], 'response': response}
    session.import_inbox(payload)
    with pytest.raises(DecisionPending):
        _run(session)
    assert session.error
    assert _pending(session, before) == pending
    assert session.data['queue'] == [payload]
    assert session.data['journal'] == session.log == []
    _assert_clean(session.state)


@pytest.mark.parametrize('response', [True, False, {'use_default': True}])
def test_supply_consent_save_resume_replays_once_before_effects(tmp_path, response):
    session = _session()
    initial = _board(session.state)
    with pytest.raises(DecisionPending):
        _run(session)
    pending = _pending(session, initial)
    save_game(session.state, tmp_path / 'pending.json', meta=session.meta, log=session.log)
    state, meta, log = load_game(tmp_path / 'pending.json')
    resumed = _session(state, meta, log)
    resumed.import_inbox({'decision_id': pending['id'], 'response': response})
    result = _run(resumed)
    assert result['executed'] and not result.get('errors'), result
    assert not (result.get('sa_execution') or {}).get('errors'), result
    assert len(resumed.log) == 1
    assert not resumed.data['pending'] and not resumed.data['queue'] and not resumed.data['journal']
    if response is False:
        assert result['command'] != rc.CMD_RECRUIT
        assert all(count_pieces(state, region, rc.ROMANS, rc.ALLY) == 0
                   for region in (rc.SEQUANI, rc.MANDUBII))
    else:
        assert result['command'] == rc.CMD_RECRUIT
        assert all(count_pieces(state, region, rc.ROMANS, rc.FORT) == 1
                   for region in (rc.SEQUANI, rc.MANDUBII))
        assert all(count_pieces(state, region, rc.ROMANS, rc.ALLY) == 2
                   for region in (rc.SEQUANI, rc.MANDUBII))
    _assert_clean(state)
    replay, replay_result = _replay(initial, resumed.log)
    assert replay_result == result
    assert _board(replay.state) == _board(state)


def test_first_supply_acceptance_survives_second_pending_and_saved_resume(tmp_path):
    session = _session(_state(second_controller=True))
    initial = _board(session.state)
    session.import_inbox([{'response': True}])
    with pytest.raises(DecisionPending):
        _run(session)
    pending = _pending(session, initial)
    assert pending['id'] == 'd000002'
    assert len(session.data['journal']) == 1 and session.log == []
    first_request = decode(session.data['journal'][0]['assistant_request'])
    assert first_request['context']['region'] != decode(pending['request'])['context']['region']
    save_game(session.state, tmp_path / 'two-consents.json', meta=session.meta, log=session.log)
    state, meta, log = load_game(tmp_path / 'two-consents.json')
    resumed = _session(state, meta, log)
    resumed.import_inbox({'decision_id': pending['id'], 'response': True})
    result = _run(resumed)
    assert result['executed'] and result['command'] == rc.CMD_RECRUIT
    assert not result.get('errors') and not (result.get('sa_execution') or {}).get('errors')
    assert len(resumed.log) == 2
    assert [entry['assistant_id'] for entry in resumed.log] == ['d000001', 'd000002']
    assert not resumed.data['queue'] and not resumed.data['journal'] and not resumed.data['pending']
    _assert_clean(state)
    replay, replay_result = _replay(initial, resumed.log)
    assert replay_result == result and _board(replay.state) == _board(state)


def test_refusing_supply_can_enable_paid_recruit_after_optimistic_seize(tmp_path):
    state = _state()
    deactivate_capability(state, 13)
    state['resources'][rc.ROMANS] = 10
    for region in (rc.SEQUANI, rc.MANDUBII):
        place_piece(state, region, rc.ROMANS, rc.FORT)
    for tribe in (rc.TRIBE_SENONES, rc.TRIBE_LINGONES, rc.TRIBE_HELVETII):
        state['tribes'][tribe]['status'] = rc.DISPERSED
    # With consent, Build consumes the sole Subdued Tribe in each Region.
    # The remaining five Recruit Auxilia miss §8.8.4's six-piece threshold.
    optimistic = node_r_recruit(state)
    assert optimistic['command'] == rc.CMD_SEIZE
    candidate = optimistic['details'][CANDIDATE]
    assert candidate['details']['potential_allies'] == 0
    assert candidate['details']['potential_auxilia'] == 5
    session = _session(state)
    initial = _board(state)
    with pytest.raises(DecisionPending):
        _run(session)
    pending = _pending(session, initial, potential_allies=0)
    proposed = decode(pending['request'])['context']['proposed_action']
    assert proposed['details']['potential_auxilia'] == 5
    assert pending['id'] == 'd000001' and session.log == session.data['journal'] == []
    save_game(state, tmp_path / 'inverse-pending.json', meta=session.meta, log=session.log)
    restored, meta, log = load_game(tmp_path / 'inverse-pending.json')
    resumed = _session(restored, meta, log)
    resumed.import_inbox({'decision_id': pending['id'], 'response': False})
    result = _run(resumed)
    # Refusal prevents Build, leaving two legal paid Recruit Allies.
    assert result['executed'] and result['command'] == rc.CMD_RECRUIT
    assert not result.get('errors') and not (result.get('sa_execution') or {}).get('errors')
    assert restored['resources'][rc.ROMANS] == 6
    for region in (rc.SEQUANI, rc.MANDUBII):
        assert count_pieces(restored, region, rc.ROMANS, rc.ALLY) == 1
    # The fallback Scout may move the four existing Auxilia before Recruit.
    assert sum(count_pieces(restored, region, rc.ROMANS, rc.AUXILIA)
               for region in restored['spaces']) == 4
    assert len(resumed.log) == 1 and decode(resumed.log[0]['assistant_response']) is False
    assert not resumed.data['queue'] and not resumed.data['journal'] and not resumed.data['pending']
    _assert_clean(restored)
    replay, replay_result = _replay(initial, resumed.log)
    assert replay_result == result and _board(replay.state) == _board(restored)
