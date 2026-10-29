"""Physical Spring Leaders, scenario gates, strict choices and atomicity."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, get_leader_in_region, place_piece
from fs_bot.engine.game_engine import get_sop_factions
from fs_bot.engine.spring import (
    UNLOCK_KEY, successor_request, spring_box_request, resolve_spring_box_entry,
    unlock_spring_box_entry, place_successors, validate_response,
)
from fs_bot.engine.winter import spring_phase, run_winter_round
from fs_bot.state.serialize import encode, save_game, load_game
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state, validate_state


def boxed_state():
    state = setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=8)
    state['non_player_factions'] = set(get_sop_factions(state)) - {rc.ARVERNI}
    return state


def test_human_successor_can_choose_own_piece_outside_home():
    state = build_initial_state(rc.SCENARIO_RECONQUEST, seed=1)
    state['non_player_factions'] = {rc.ROMANS, rc.ARVERNI}
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    offered = []
    def choose(board, faction, request):
        offered.append(request)
        return {'region': rc.CARNUTES}
    state['decision_agent'] = choose
    result = spring_phase(state)
    assert (rc.BELGAE, rc.CARNUTES) in result['successors_placed']
    assert offered[0]['leader'] == rc.SUCCESSOR and not offered[0]['can_defer']
    assert set(offered[0]['legal_regions']) == {*rc.BELGAE_HOME_REGIONS, rc.CARNUTES}
    assert get_leader_in_region(state, rc.CARNUTES, rc.BELGAE) == rc.SUCCESSOR
    assert validate_state(state) == []


@pytest.mark.parametrize('bad', [
    {'defer': True}, {'defer': 1}, {'region': rc.PROVINCIA}, {'region': None},
    {'use_default': 1}, {'use_default': 1.0}, {'region': rc.MORINI, 'extra': True},
])
def test_invalid_later_successor_rolls_back_prior_seats_and_rng(bad):
    state = build_initial_state(rc.SCENARIO_RECONQUEST, seed=4)
    state['non_player_factions'] = {rc.ROMANS, rc.ARVERNI}
    before = encode(state)
    state['decision_agent'] = lambda *args: bad
    with pytest.raises(ValueError):
        spring_phase(state)
    assert encode({key: value for key, value in state.items() if key != 'decision_agent'}) == before


def test_later_pending_restores_np_tie_draw_and_completed_successors():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=11)
    state['non_player_factions'] = {rc.ROMANS, rc.BELGAE}
    before = encode(state)
    def pause(*args):
        raise EOFError('next player')
    state['decision_agent'] = pause
    with pytest.raises(EOFError):
        place_successors(state)
    assert encode({key: value for key, value in state.items() if key != 'decision_agent'}) == before
    assert state['decision_agent'] is pause


def test_boxed_named_leader_does_not_become_ordinary_successor():
    state = boxed_state()
    assert successor_request(state, rc.ARVERNI) is None
    assert spring_box_request(state) is None
    assert resolve_spring_box_entry(state, {'region': rc.CARNUTES}) is None
    assert rc.VERCINGETORIX in state['spring_box_leaders']


def test_first_pax_spring_allows_deferral_then_any_playable_empty_region():
    state = boxed_state()
    calls = []
    def choose(board, faction, request):
        calls.append(request)
        return {'defer': True}
    state['decision_agent'] = choose
    result = spring_phase(state, unlock_vercingetorix=True)
    assert result['spring_box_entry']['deferred']
    assert state[UNLOCK_KEY] is True
    assert calls[0]['source'] == 'spring_box' and calls[0]['can_defer']
    assert rc.CARNUTES in calls[0]['legal_regions']
    assert count_pieces(state, rc.CARNUTES) == 0
    state['_spring_box_entry_window'] = ['old-boundary']
    result = resolve_spring_box_entry(state, {'region': rc.CARNUTES})
    assert result['leader'] == rc.VERCINGETORIX
    assert get_leader_in_region(state, rc.CARNUTES, rc.ARVERNI) == rc.VERCINGETORIX
    assert not state['spring_box_leaders'] and UNLOCK_KEY not in state
    assert '_spring_box_entry_window' not in state
    assert resolve_spring_box_entry(state) is None
    assert validate_state(state) == []


@pytest.mark.parametrize('bad', [
    {'defer': 1}, {'defer': False}, {'use_default': 1.0},
    {'region': rc.CISALPINA}, {'region': rc.CARNUTES, 'defer': True},
])
def test_invalid_optional_entry_restores_box_unlock_and_rng(bad):
    state = boxed_state()
    unlock_spring_box_entry(state)
    before = encode(state)
    with pytest.raises(ValueError):
        resolve_spring_box_entry(state, bad)
    assert encode(state) == before


def test_request_and_validation_are_nonconsuming():
    state = boxed_state()
    unlock_spring_box_entry(state)
    state['decision_agent'] = lambda *args: pytest.fail('preview consumed input')
    before = encode({key: value for key, value in state.items() if key != 'decision_agent'})
    request = spring_box_request(state)
    validate_response(state, request, {'region': rc.CARNUTES})
    validate_response(state, request, {'defer': True})
    validate_response(state, request, {'use_default': True})
    assert encode({key: value for key, value in state.items() if key != 'decision_agent'}) == before


def test_failed_first_spring_does_not_leave_unlock_or_placement():
    state = boxed_state()
    before = encode(state)
    def pause(*args):
        raise EOFError()
    state['decision_agent'] = pause
    with pytest.raises(EOFError):
        spring_phase(state, unlock_vercingetorix=True)
    assert encode({key: value for key, value in state.items() if key != 'decision_agent'}) == before


def test_real_first_winter_keeps_box_locked_until_spring():
    state = boxed_state()
    seen = []
    def choose(board, faction, request):
        if request['kind'] == 'spring_leader':
            assert board[UNLOCK_KEY] is True
            seen.append(request)
            return {'defer': True}
        assert spring_box_request(board) is None
        return None
    state['decision_agent'] = choose
    result = run_winter_round(state)
    assert result['phases']['spring']['spring_box_entry']['deferred']
    assert len(seen) == 1


def test_legacy_unlock_inference_excludes_interlude_and_live_winter():
    state = boxed_state()
    state['winter_count'] = 3
    assert spring_box_request(state) is None  # first Spring still ahead
    state.pop('first_winter_special')
    state['scenario'] = rc.SCENARIO_GALLIC_WAR
    assert spring_box_request(state) is None
    state['scenario'] = rc.SCENARIO_PAX_GALLICA
    state['current_card'] = rc.WINTER_CARD
    assert spring_box_request(state) is None
    state['current_card'] = 10
    assert spring_box_request(state) is not None
    resolve_spring_box_entry(state, {'defer': True})
    assert state[UNLOCK_KEY] is True


@pytest.mark.parametrize('flag', [True, False, 1, 1.0, 'true', None])
def test_unlock_save_field_requires_strict_boolean(tmp_path, flag):
    state = boxed_state()
    state[UNLOCK_KEY] = flag
    path = tmp_path / 'spring.json'
    save_game(state, path)
    if type(flag) is bool:
        loaded, _, _ = load_game(path, validate=True)
        assert loaded[UNLOCK_KEY] is flag
    else:
        with pytest.raises(ValueError, match='must be boolean'):
            load_game(path, validate=True)
