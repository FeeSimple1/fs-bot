"""§4.5.1/A4.5.1 retain the human German Rally's optional troop quantity."""

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.commands.common import CommandError
from fs_bot.commands.enlist_free import execute_free_enlist
from fs_bot.engine.execute import _execute_enlist
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state


def _state(scenario=rc.SCENARIO_PAX_GALLICA, region=rc.MANDUBII):
    state = build_initial_state(scenario, seed=11)
    place_piece(state, region, rc.BELGAE, rc.LEADER,
                leader_name=rc.AMBIORIX if scenario in rc.BASE_SCENARIOS else rc.BODUOGNATUS)
    place_piece(state, region, rc.GERMANS, rc.WARBAND, 3)
    refresh_all_control(state)
    return state


def _plan(region=rc.MANDUBII, **kwargs):
    return {'type': 'german_rally', 'region': region, **kwargs}


@pytest.mark.parametrize('count', [0, 1])
def test_base_ally_followon_has_exact_optional_warband_count(count):
    state = _state()
    before = state['rng'].getstate()
    result = execute_free_enlist(state, _plan(place='ally', tribe=rc.TRIBE_MANDUBII, count=count))
    assert count_pieces(state, rc.MANDUBII, rc.GERMANS, rc.ALLY) == 1
    assert count_pieces(state, rc.MANDUBII, rc.GERMANS, rc.WARBAND) == 3 + count
    assert result['rally'][1]['pieces_placed'][rc.WARBAND] == count
    assert state['rng'].getstate() == before


@pytest.mark.parametrize('bad_count', [True, 1.0, '1', None, -1, 2])
def test_invalid_base_ally_followon_restores_ally_pool_control_resources_and_rng(bad_count):
    state = _state()
    before = encode(state)
    with pytest.raises(CommandError):
        execute_free_enlist(state, _plan(place='ally', tribe=rc.TRIBE_MANDUBII, count=bad_count))
    assert encode(state) == before


@pytest.mark.parametrize('place', ['ally', 'warbands'])
def test_base_germania_keeps_required_one_warband_floor(place):
    state = _state(region=rc.SUGAMBRI)
    plan = _plan(rc.SUGAMBRI, place=place, count=0)
    if place == 'ally':
        plan['tribe'] = rc.TRIBE_SUGAMBRI
    before = encode(state)
    with pytest.raises(CommandError):
        execute_free_enlist(state, plan)
    assert encode(state) == before
    plan['count'] = 1
    execute_free_enlist(state, plan)
    assert count_pieces(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND) == 4


@pytest.mark.parametrize('count', [1, 2])
def test_expansion_requested_total_includes_mandatory_home_bonus(count):
    state = _state(rc.SCENARIO_ARIOVISTUS, rc.SUGAMBRI)
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.ALLY)
    state['tribes'][rc.TRIBE_SUGAMBRI].update(allied_faction=rc.GERMANS, status=None)
    action = {'details': {'enlist': _plan(rc.SUGAMBRI, place='warbands', count=count)}}
    result = _execute_enlist(state, rc.BELGAE, action)
    assert result['executed']
    assert count_pieces(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND) == 3 + count


@pytest.mark.parametrize('place,count', [('warbands', 0), ('ally', 0)])
def test_expansion_cannot_decline_mandatory_bonus_with_zero_count(place, count):
    state = _state(rc.SCENARIO_ARIOVISTUS, rc.SUGAMBRI)
    before = encode(state)
    with pytest.raises(CommandError):
        execute_free_enlist(state, _plan(rc.SUGAMBRI, place=place, count=count,
                                        tribe=rc.TRIBE_SUGAMBRI))
    assert encode(state) == before


def test_expansion_four_piece_limit_counts_home_bonus():
    state = _state(rc.SCENARIO_ARIOVISTUS)
    for tribe in (rc.TRIBE_MANDUBII, rc.TRIBE_SENONES, rc.TRIBE_LINGONES):
        place_piece(state, rc.MANDUBII, rc.GERMANS, rc.ALLY)
        state['tribes'][tribe].update(allied_faction=rc.GERMANS, status=None)
    place_piece(state, rc.MANDUBII, rc.GERMANS, rc.SETTLEMENT)
    before = encode(state)
    with pytest.raises(CommandError):
        execute_free_enlist(state, _plan(place='warbands', count=5))
    assert encode(state) == before
    execute_free_enlist(state, _plan(place='warbands', count=4))
    assert count_pieces(state, rc.MANDUBII, rc.GERMANS, rc.WARBAND) == 7
