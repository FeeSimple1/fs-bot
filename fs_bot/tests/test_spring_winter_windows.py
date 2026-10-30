"""Unlocked Pax entry during Winter changes only unfinished procedures."""
from copy import deepcopy
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, find_leader, place_piece
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine import action_windows, winter
from fs_bot.engine.game_engine import _action_transaction
from fs_bot.engine.arverni_phase import run_arverni_phase
from fs_bot.engine.germans_battle import germans_phase_battle
from fs_bot.engine.quarters import (apply_relocations, validate_quarters_plan,
                                    validate_payment_response, validate_provincia_response)
from fs_bot.engine.spring import UNLOCK_KEY
from fs_bot.engine.winter_campaign import resolve_winter_campaign, validate_human_plan
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def _boxed_empty():
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=91)
    state['spring_box_leaders'] = [rc.VERCINGETORIX]
    state['available'][rc.ARVERNI][rc.LEADER] -= 1
    state[UNLOCK_KEY] = True
    state['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE}
    state['current_card'] = rc.WINTER_CARD
    state['winter_count'] = 1
    return state


def _agent(state, answer):
    answer.supports_action_windows = True
    state['decision_agent'] = answer


def test_first_winter_never_offers_entry_before_first_spring_but_allows_later_step():
    state = setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=31)
    state['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE}
    state['current_card'] = rc.WINTER_CARD
    offered = []
    def choose(board, faction, request):
        if request['kind'] == 'spring_leader' and request['leader'] == rc.VERCINGETORIX:
            assert board[UNLOCK_KEY] is True
            offered.append(request)
            return ({'region': rc.CARNUTES} if request.get('window', {}).get('stage')
                    == 'winter_spring_fallen' else {'defer': True})
        return None
    _agent(state, choose)
    result = winter.run_winter_round(state)
    assert result['phases']['spring']['spring_box_entry']['deferred']
    assert len(offered) == 2 and 'window' not in offered[0]
    assert offered[1]['window']['stage'] == 'winter_spring_fallen'
    assert find_leader(state, rc.ARVERNI) == rc.CARNUTES


def test_no_post_victory_window_can_change_a_finished_winter():
    state = _boxed_empty()
    offered = []
    def choose(board, faction, request):
        offered.append(request)
        return {'defer': True}
    _agent(state, choose)
    result = winter.run_winter_round(state, is_final=True)
    assert result['phases']['victory']['game_over']
    assert list(result['phases']) == ['victory']
    assert [r['window']['stage'] for r in offered] == ['winter_victory']
    assert find_leader(state, rc.ARVERNI) is None


def test_later_winter_entry_precedes_the_affected_quarters_choice():
    state = _boxed_empty()
    seen = []
    def choose(board, faction, request):
        seen.append((request['kind'], request.get('window'), find_leader(board, rc.ARVERNI)))
        if request['kind'] == 'spring_leader':
            window = request['window']
            return ({'region': rc.CARNUTES} if window['stage'] == 'winter_quarters_faction'
                    and window['faction'] == rc.ARVERNI else {'defer': True})
        if request['kind'] == 'quarters_plan':
            return {rc.ARVERNI: []}
        return None
    _agent(state, choose)
    winter.quarters_phase(state)
    assert [leader for kind, _, leader in seen if kind == 'quarters_plan'] == [rc.CARNUTES]
    assert find_leader(state, rc.ARVERNI) == rc.CARNUTES
    assert not any(kind == 'voluntary_removal' for kind, _, _ in seen)
    assert action_windows.SCOPE not in state


def test_winter_campaign_can_enter_between_its_two_paid_actions(monkeypatch):
    state = _boxed_empty()
    state['non_player_factions'].discard(rc.AEDUI)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 2)
    commands = []
    def choose(board, faction, request):
        if request['kind'] == 'spring_leader':
            return ({'region': rc.SEQUANI} if request['window']['remaining_actions'] == 1
                    else {'defer': True})
        if request['kind'] == 'winter_campaign':
            commands.append(find_leader(board, rc.ARVERNI))
            return {'command': 'Rally', 'regions': [rc.CARNUTES], 'details': {}}
        return None
    _agent(state, choose)
    # The real Campaign orchestration, including validation, is exercised;
    # isolate its two grants from unrelated bot Rally strategy.
    from fs_bot.engine import winter_campaign
    monkeypatch.setattr(winter_campaign, '_execute_plan',
                        lambda *args, **kwargs: {'executed': True})
    result = resolve_winter_campaign(state, rc.AEDUI, 63)
    assert len(result['actions']) == 2 and commands == [None, rc.SEQUANI]


def test_campaign_validation_does_not_offer_entry_or_mutate_live_state():
    state = _boxed_empty()
    state['non_player_factions'].discard(rc.AEDUI)
    state['resources'][rc.AEDUI] = 10
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 2)
    _agent(state, lambda *args: pytest.fail('Preview consulted a human'))
    before = encode(board_copy(state))
    validate_human_plan(state, rc.AEDUI,
                        {'command': 'March', 'regions': [],
                         'details': {'origins': [rc.CARNUTES],
                                     'destinations': [rc.MANDUBII],
                                     'routes': {rc.CARNUTES: [rc.MANDUBII]}}})
    assert encode(board_copy(state)) == before


def _relocation_state():
    state = _boxed_empty()
    state['non_player_factions'].discard(rc.ROMANS)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(state, rc.MORINI, rc.ARVERNI, rc.WARBAND)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA)
    moves = [(rc.AUXILIA, rc.NERVII, rc.ATREBATES, 1),
             (rc.LEGION, rc.MORINI, rc.PROVINCIA, 1)]
    assert validate_quarters_plan(state, {rc.ROMANS: moves}) == []
    return state, moves


@pytest.mark.parametrize('answer', [{'decline': True}, {'use_default': True},
    {'moves': [[rc.AUXILIA, rc.ATREBATES, rc.PROVINCIA, 1]]}])
def test_entry_between_adjacent_step_and_supply_reconsiders_only_unfinished_moves(answer):
    state, moves = _relocation_state()
    calls = []
    def choose(board, faction, request):
        assert board is state
        calls.append(request)
        if request['kind'] == 'spring_leader':
            assert request['window']['stage'] == 'quarters_before_supply'
            assert count_pieces(board, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 2
            return {'region': rc.MORINI}
        if request['kind'] == 'agreement':
            return False
        assert request['kind'] == 'quarters_provincia'
        assert find_leader(board, rc.ARVERNI) == rc.MORINI
        assert not any(move[1] == rc.MORINI for move in request['legal_moves'])
        return answer
    _agent(state, choose)
    apply_relocations(state, rc.ROMANS, moves)
    assert [r['kind'] for r in calls] == ['spring_leader', 'agreement', 'quarters_provincia']
    assert count_pieces(state, rc.MORINI, rc.ROMANS, rc.LEGION) == 1
    assert count_pieces(state, rc.NERVII, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == (1 if 'moves' in answer else 2)
    assert find_leader(state, rc.ARVERNI) == rc.MORINI
    assert validate_state(state) == []


def test_invalidated_provincia_pending_rolls_back_live_entry_and_adjacent_step():
    state, moves = _relocation_state()
    before = encode(state)
    def choose(board, faction, request):
        if request['kind'] == 'spring_leader':
            return {'region': rc.MORINI}
        if request['kind'] == 'agreement':
            return False
        raise EOFError('Roman continuation pending')
    _agent(state, choose)
    with pytest.raises(EOFError):
        apply_relocations(state, rc.ROMANS, moves)
    assert encode(board_copy(state)) == before


def test_changed_provincia_plan_reports_actual_moves_and_reasks_payments():
    state, moves = _relocation_state()
    state['resources'][rc.ROMANS] = 10
    requests = []
    def choose(board, faction, request):
        requests.append(request)
        if request['kind'] == 'spring_leader':
            return ({'region': rc.MORINI} if request['window']['stage'] == 'quarters_before_supply'
                    else {'defer': True})
        if request['kind'] == 'agreement':
            return False
        if request['kind'] == 'quarters_plan':
            return ({rc.ARVERNI: []} if faction == rc.ARVERNI else
                    {rc.ROMANS: moves, rc.ROMANS + '_quartering': {rc.ATREBATES: {'pay': 2}}})
        if request['kind'] == 'quarters_provincia':
            return {'decline': True}
        assert request['kind'] == 'quarters_payment'
        assert count_pieces(board, rc.MORINI, rc.ROMANS, rc.LEGION) == 1
        return {'payments': {rc.ATREBATES: {'pay': 2}, rc.MORINI: {'pay': 1}}}
    _agent(state, choose)
    rng = state['rng'].getstate()
    result = winter.quarters_phase(state)
    assert result['roman_relocation'] == [moves[0]]
    assert len([r for r in requests if r['kind'] == 'quarters_payment']) == 1
    assert result['roman_quartering']['total_cost'] == 6
    assert not result['roman_quartering']['rolls']
    assert state['resources'][rc.ROMANS] == 4 and state['rng'].getstate() == rng
    before = encode(board_copy(state))
    with pytest.raises(ValueError):
        validate_payment_response(state, {}, {'payments': {
            rc.MORINI: {'pay_pieces': [[rc.LEGION, None, 2]]}}})
    assert encode(board_copy(state)) == before


@pytest.mark.parametrize('response', [
    {'use_default': 1}, {'decline': 1}, {'moves': [[rc.LEGION, rc.MORINI, rc.PROVINCIA, 2]]},
    {'moves': [[rc.LEGION, rc.MORINI, rc.PROVINCIA, 1]] * 2},
    {'moves': [[rc.LEGION, rc.MORINI, rc.PROVINCIA, True]]},
])
def test_provincia_continuation_validation_is_strict_and_pure(response):
    state, _ = _relocation_state()
    request = {'legal_moves': [[rc.LEGION, rc.MORINI, rc.PROVINCIA, 1]]}
    before = encode(state)
    with pytest.raises(ValueError):
        validate_provincia_response(state, request, response)
    assert encode(state) == before


def test_ariovistus_game_run_arverni_never_receives_pax_entry():
    state = setup_scenario(rc.SCENARIO_ARIOVISTUS, seed=91)
    state[UNLOCK_KEY] = True  # A stale flag cannot enable cross-scenario entry.
    seen = []
    def choose(board, faction, request):
        seen.append(request['kind'])
        return None
    _agent(state, choose)
    run_arverni_phase(state)
    assert 'spring_leader' not in seen
    assert action_windows.SCOPE not in state


def test_german_battle_includes_a_newly_occupied_region_after_initial_selection():
    state = _boxed_empty()
    place_piece(state, rc.MANDUBII, rc.GERMANS, rc.WARBAND, 2)
    place_piece(state, rc.MORINI, rc.GERMANS, rc.WARBAND, 2)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA,
                piece_state=rc.REVEALED)
    def choose(board, faction, request):
        if request['kind'] == 'spring_leader':
            return ({'region': rc.MORINI} if request['window']['stage'] == 'germans_battle_target'
                    else {'defer': True})
        return None
    _agent(state, choose)
    result = germans_phase_battle(state)
    assert [(battle['region'], battle['defender']) for battle in result['battles']] == [
        (rc.MANDUBII, rc.ROMANS), (rc.MORINI, rc.ARVERNI)]
    assert validate_state(state) == []


def test_deferred_german_battle_windows_preserve_legacy_results_and_rng():
    state = _boxed_empty()
    place_piece(state, rc.MANDUBII, rc.GERMANS, rc.WARBAND, 2)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA,
                piece_state=rc.REVEALED)
    legacy = deepcopy(state)
    def choose(board, faction, request):
        return {'defer': True} if request['kind'] == 'spring_leader' else None
    _agent(state, choose)
    assert germans_phase_battle(state) == germans_phase_battle(legacy)
    assert encode(board_copy(state)) == encode(legacy)


def _roman_session(state, meta=None, log=None):
    session = SeatSession(state, meta if meta is not None else {'seat': rc.ROMANS},
                          log if log is not None else [], HumanTurnDisplay(io.StringIO()))
    # The separate Arverni agent deterministically exercises the interruption;
    # the Roman continuation uses the real durable seat frontend.
    def agent(board, faction, request):
        if request['kind'] == 'spring_leader':
            return {'region': rc.MORINI}
        if request['kind'] == 'agreement':
            return False
        return session.reactive(board, faction, request)
    _agent(state, agent)
    def driver(*args):
        pass
    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    return session, driver


def test_provincia_reconsideration_invalid_pending_save_resume_and_exact_replay(tmp_path):
    state, moves = _relocation_state()
    origin, before = deepcopy(state), encode(state)
    session, driver = _roman_session(state)
    def run(board, selected_driver):
        with _action_transaction(board, selected_driver):
            apply_relocations(board, rc.ROMANS, moves)
    with pytest.raises(DecisionPending):
        run(state, driver)
    pending = deepcopy(session.data['pending'])
    assert decode(pending['request'])['kind'] == 'quarters_provincia'
    assert pending['id'] == 'd000001'
    assert find_leader(decode(pending['board']), rc.ARVERNI) == rc.MORINI
    assert encode(board_copy(state)) == before
    session.import_inbox({'decision_id': pending['id'], 'response': {
        'moves': [[rc.LEGION, rc.MORINI, rc.PROVINCIA, 1]]}})
    with pytest.raises(DecisionPending):
        run(state, driver)
    assert session.data['pending']['id'] == pending['id']
    assert not session.data['journal'] and encode(board_copy(state)) == before
    save_game(state, tmp_path / 'quarters.json', meta=session.meta, log=session.log)
    restored, meta, log = load_game(tmp_path / 'quarters.json', validate=True)
    resumed, resumed_driver = _roman_session(restored, meta, log)
    resumed.import_inbox({'decision_id': pending['id'], 'response': {
        'moves': [[rc.AUXILIA, rc.ATREBATES, rc.PROVINCIA, 1]]}})
    run(restored, resumed_driver)
    resumed.finish()
    replay, replay_driver = _roman_session(origin)
    replay.data['queue'] = [SeatSession._inbox_entry(entry) for entry in resumed.log]
    replay.data['expected'] = [
        {'id': entry['assistant_id'], 'signature': entry['assistant_signature'],
         'request': entry['assistant_request'],
         'action_windows_version': entry.get('assistant_action_windows_version', 0)}
        for entry in resumed.log]
    run(origin, replay_driver)
    replay.finish()
    assert encode(board_copy(origin)) == encode(board_copy(restored))
    assert replay.log == resumed.log
