"""Deferred Pax entry remains available at durable, complete-action windows."""
import copy
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import find_leader, remove_piece
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine import game_engine as ge
from fs_bot.engine.moves import preview_player_action
from fs_bot.engine.spring import resolve_spring_box_entry, spring_box_request
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.setup import setup_scenario
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def _state():
    state = setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=31)
    state['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE}
    state['vercingetorix_entry_unlocked'] = True
    state.pop('first_winter_special', None)
    state['winter_count'] = 1
    state['played_cards'] = [rc.WINTER_CARD, 10]
    state['current_card'] = state['current_card_id'] = 10
    state['next_card'], state['deck'] = 11, [11, 12, rc.WINTER_CARD]
    return state


def _eligible(state, factions):
    for faction in ge.get_sop_factions(state):
        state['eligibility'][faction] = rc.ELIGIBLE if faction in factions else rc.INELIGIBLE


def test_ineligible_arverni_can_defer_then_arrive_before_another_factions_action():
    state = _state()
    actors = [f for f in ge.get_faction_order(state) if f != rc.ARVERNI][:2]
    _eligible(state, actors)
    answers = iter([{'defer': True}, {'region': rc.SEQUANI}])
    requests, decisions = [], []

    def agent(board, faction, request):
        assert faction == rc.ARVERNI and request['kind'] == 'spring_leader'
        requests.append(request)
        return next(answers)

    def decision(board, faction, options, position):
        decisions.append((faction, find_leader(board, rc.ARVERNI)))
        return {'action': ge.ACTION_PASS}

    state['decision_agent'] = agent
    arverni_resources = state['resources'][rc.ARVERNI]
    result = ge.resolve_card_turn(state, decision, execute=True)
    assert decisions == [(actors[0], None), (actors[1], rc.SEQUANI)]
    assert len(requests) == 2 and result['passes'] == actors
    assert rc.ARVERNI not in result['actions_taken']
    assert state['resources'][rc.ARVERNI] == arverni_resources
    assert state['spaces'][rc.SEQUANI]['pieces'][rc.ARVERNI][rc.LEADER] == rc.VERCINGETORIX
    assert '_spring_box_entry_window' not in state


def test_final_action_has_one_entry_window_before_advancing():
    state = _state()
    _eligible(state, [rc.ROMANS])
    seen = []

    def agent(board, faction, request):
        completed = list(board['_card_turn']['actions_taken'])
        seen.append(completed)
        return {'defer': True} if not completed else {'region': rc.SEQUANI}

    state['decision_agent'] = agent
    result = ge.play_card(state, lambda *args: {'action': ge.ACTION_PASS}, execute=True)
    assert seen == [[], [rc.ROMANS]]
    assert list(result['turn_result']['actions_taken']) == [rc.ROMANS]
    assert find_leader(state, rc.ARVERNI) == rc.SEQUANI
    assert state['current_card'] == 11


def test_no_eligible_factions_still_offers_entry_before_advance():
    state = _state()
    _eligible(state, [])
    requests = []
    state['decision_agent'] = lambda board, faction, request: (
        requests.append(request) or {'region': rc.SEQUANI})
    result = ge.play_card(state, lambda *args: pytest.fail('No faction should act'), execute=True)
    assert len(requests) == 1
    assert result['turn_result']['actions_taken'] == {}
    assert find_leader(state, rc.ARVERNI) == rc.SEQUANI


def test_completed_card_resume_does_not_reoffer_deferred_advance_window(monkeypatch):
    state = _state()
    _eligible(state, [])
    requests = []
    state['decision_agent'] = lambda board, faction, request: (
        requests.append(request) or {'defer': True})
    advance = ge.advance_to_next_card
    monkeypatch.setattr(ge, 'advance_to_next_card', lambda board: (_ for _ in ()).throw(EOFError()))
    with pytest.raises(EOFError):
        ge.play_card(state, lambda *args: pytest.fail('No faction should act'), execute=True)
    assert len(requests) == 1 and '_resolved_card' in state
    token = copy.deepcopy(state['_spring_box_entry_window'])
    monkeypatch.setattr(ge, 'advance_to_next_card', advance)
    ge.play_card(state, lambda *args: pytest.fail('Completed card must not repeat'), execute=True)
    assert len(requests) == 1 and state['_spring_box_entry_window'] == token
    assert rc.VERCINGETORIX in state['spring_box_leaders']


def test_deferred_entry_is_offered_before_winter_resolution(monkeypatch):
    state = _state()
    state['current_card'] = rc.WINTER_CARD
    state['decision_agent'] = lambda *args: {'region': rc.SEQUANI}
    seen = []

    def winter(board):
        seen.append(find_leader(board, rc.ARVERNI))
        return {'winter_result': {'phases': {}}}

    monkeypatch.setattr(ge, 'resolve_winter_card', winter)
    ge.play_card(state, lambda *args: pytest.fail('Winter has no normal turn'), execute=True)
    assert seen == [rc.SEQUANI]


def test_first_spring_offer_is_not_immediately_repeated_after_winter():
    state = setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=31)
    state['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE}
    state['current_card'] = rc.WINTER_CARD
    state['played_cards'] = [rc.WINTER_CARD]
    state['next_card'], state['deck'] = 10, [10, 11, rc.WINTER_CARD]
    requests = []
    def agent(board, faction, request):
        if request['kind'] == 'spring_leader':
            requests.append(request)
            return {'defer': True}
        return None
    state['decision_agent'] = agent
    ge.play_card(state, lambda *args: pytest.fail('Winter has no normal turn'), execute=True)
    assert [r['kind'] for r in requests] == ['spring_leader']
    assert state['vercingetorix_entry_unlocked'] is True
    assert rc.VERCINGETORIX in state['spring_box_leaders']
    assert state['current_card'] == 10


def _session(state, meta=None, log=None):
    meta = meta if meta is not None else {'seat': rc.ARVERNI, 'scenario': state['scenario'], 'seed': 31}
    session = SeatSession(state, meta, log if log is not None else [], HumanTurnDisplay(io.StringIO()))
    state['decision_agent'] = session.reactive

    def decision(board, faction, options, position):
        return session.ask(board, faction, {'kind': 'turn', 'options': options, 'position': position})

    decision.transaction_checkpoint = session.checkpoint
    decision.transaction_restore = session.restore
    return session, decision


@pytest.mark.parametrize('entry_response', [{'defer': True}, {'use_default': True}])
def test_accepted_entry_response_save_resume_and_exact_replay(tmp_path, entry_response):
    state = _state()
    _eligible(state, [rc.ARVERNI])
    origin = copy.deepcopy(state)
    session, driver = _session(state)
    session.import_inbox([{'response': entry_response}])
    with pytest.raises(DecisionPending):
        ge.play_card(state, driver, execute=True)
    assert len(session.log) == 1 and not session.data['journal']
    pending = copy.deepcopy(session.data['pending'])
    assert decode(pending['request'])['kind'] == 'turn'
    # Placement/deferral is committed; a missing ordinary turn cannot undo
    # it or consume that already accepted reactive answer a second time.
    assert session.log[0]['reactive'] == 'spring_leader'
    deferred = 'defer' in entry_response
    assert (find_leader(state, rc.ARVERNI) is None) is deferred
    if deferred:
        assert state['_spring_box_entry_window']['boundary'] == 'before_faction'
    save_game(state, tmp_path / 'paused.json', meta=session.meta, log=session.log)
    restored, meta, log = load_game(tmp_path / 'paused.json', validate=True)
    resumed, resumed_driver = _session(restored, meta, log)
    resumed.import_inbox({'decision_id': pending['id'], 'response': {'action': ge.ACTION_PASS}})
    if deferred:
        with pytest.raises(DecisionPending):
            ge.play_card(restored, resumed_driver, execute=True)
        later = resumed.data['pending']
        assert decode(later['request'])['kind'] == 'spring_leader'
        assert len(resumed.log) == 2  # one defer and the completed Pass
        resumed.import_inbox({'decision_id': later['id'], 'response': {'region': rc.SEQUANI}})
    result = ge.play_card(restored, resumed_driver, execute=True)
    resumed.finish()
    assert result['turn_result']['passes'] == [rc.ARVERNI]
    assert find_leader(restored, rc.ARVERNI) is not None
    replay, replay_driver = _session(origin)
    replay.data['queue'] = [SeatSession._inbox_entry(e) for e in resumed.log]
    replay.data['expected'] = [{'id': e['assistant_id'], 'signature': e['assistant_signature']} for e in resumed.log]
    assert ge.play_card(origin, replay_driver, execute=True) == result
    replay.finish()
    assert encode(board_copy(origin)) == encode(board_copy(restored))
    assert replay.log == resumed.log


def test_interrupted_entry_does_not_consume_window_or_mutate_board_rng():
    state = _state()
    state['decision_agent'] = lambda *args: (_ for _ in ()).throw(EOFError())
    before = encode(board_copy(state))
    with pytest.raises(EOFError):
        ge._offer_spring_box_entry(state, lambda *args: None, 'before_faction', cursor=0)
    assert encode(board_copy(state)) == before
    assert '_spring_box_entry_window' not in state


def test_planning_and_preview_do_not_offer_or_place_optional_entry():
    state = _state()
    _eligible(state, [rc.ROMANS])
    calls = []
    state['decision_agent'] = lambda *args: calls.append(args)
    before = encode(board_copy(state))
    trial = copy.deepcopy(state)
    ge.resolve_card_turn(trial, lambda *args: {'action': ge.ACTION_PASS}, execute=False)
    assert spring_box_request(trial) is not None
    action = {'command': rc.CMD_RECRUIT, 'regions': [rc.PROVINCIA], 'details': {}}
    preview_player_action(state, rc.ROMANS, action)
    assert not calls and encode(board_copy(state)) == before


def test_later_windows_do_not_revive_removed_named_vercingetorix():
    state = _state()
    resolve_spring_box_entry(state, {'region': rc.SEQUANI})
    remove_piece(state, rc.SEQUANI, rc.ARVERNI, rc.LEADER)
    _eligible(state, [])
    state['decision_agent'] = lambda *args: pytest.fail('Removed Leader is not a Spring-box piece')
    ge.play_card(state, lambda *args: pytest.fail('No faction should act'), execute=True)
    assert find_leader(state, rc.ARVERNI) is None
    assert rc.VERCINGETORIX not in state['spring_box_leaders']
