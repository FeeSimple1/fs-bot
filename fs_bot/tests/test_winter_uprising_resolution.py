"""A66 physical placement, ownership, partial execution and local atomicity."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import get_available, place_piece, count_pieces
from fs_bot.cards.card_effects import execute_card_A66, _ally_tribe
from fs_bot.cards.winter_uprising_resolution import (
    HOLDER_KEY, TIMING, PLACEMENT, active, holder, placement_request, resolve,
    validate_response,
)
from fs_bot.engine.game_engine import get_sop_factions
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state


def position(region=rc.MORINI, owner=rc.ROMANS, scenario=rc.SCENARIO_ARIOVISTUS):
    state = build_initial_state(scenario, seed=3)
    state['non_player_factions'] = set(get_sop_factions(state)) - {rc.ROMANS, rc.BELGAE}
    state['executing_faction'] = owner
    state['event_params'] = {'region': region}
    execute_card_A66(state)
    state.pop('executing_faction')
    state.pop('event_params')
    return state


def default_placement(state, request):
    from fs_bot.cards.winter_uprising_np import np_placements
    trial = deepcopy(state)
    trial.pop('decision_agent', None)
    return np_placements(trial, request['beneficiary'], request['regions'], request['tribes'],
                         request['allies'], request['warbands'])


def test_holder_is_the_actual_executor_not_the_future_beneficiary():
    state = position()
    assert holder(state) == rc.ROMANS
    assert state['event_modifiers'][HOLDER_KEY] == rc.ROMANS
    request = placement_request(state, rc.MORINI, holder(state))
    assert request['beneficiary'] == rc.BELGAE
    assert request['holder'] == rc.ROMANS
    assert 'After any Quarters Phase' in request['card_text']


def test_human_holder_can_keep_marker_without_rng_or_board_changes():
    state = position()
    before = encode(state)
    state['decision_agent'] = lambda *args: {'activate': False}
    result = resolve(state)
    assert result[0]['deferred']
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before
    assert active(state)


@pytest.mark.parametrize('region,beneficiary,allies,warbands', [
    (rc.MORINI, rc.BELGAE, 2, 4), (rc.SUGAMBRI, rc.GERMANS, 2, 4),
    (rc.CISALPINA, rc.ARVERNI, 4, 8),
])
def test_printed_quantities_and_scope_allow_empty_adjacent_regions(region, beneficiary, allies, warbands):
    state = position(region)
    request = placement_request(state, region, rc.ROMANS)
    assert request['beneficiary'] == beneficiary
    assert request['allies'] == allies and request['warbands'] == warbands
    assert len(request['regions']) > 1 and region in request['regions']
    # Empty Regions require neither existing forces nor Control.
    assert all(count_pieces(state, selected) == 0 for selected in request['regions'])
    plan = default_placement(state, request)
    first, second = request['regions'][:2]
    plan['warbands'] = [{'region': first, 'count': 1}, {'region': second, 'count': warbands - 1}]
    before = encode(state)
    validate_response(state, request, plan)
    assert encode(state) == before


def test_allied_home_tribe_restrictions_and_dispersed_markers_still_apply():
    state = position(rc.TREVERI)
    # Arverni placement near Treveri includes Remi and Sequani, but never
    # German-only Suebi or already Allied/Dispersed Tribes.
    _ally_tribe(state, rc.TRIBE_REMI, rc.AEDUI)
    state['tribes'][rc.TRIBE_SEQUANI]['status'] = rc.MARKER_DISPERSED
    request = placement_request(state, rc.TREVERI, rc.ROMANS)
    assert request['beneficiary'] == rc.ARVERNI
    assert rc.TRIBE_REMI not in request['tribes']
    assert rc.TRIBE_SEQUANI not in request['tribes']
    assert not set(rc.SUEBI_TRIBES) & set(request['tribes'])


def test_partial_pool_counts_require_every_available_piece():
    state = position(rc.MORINI)
    place_piece(state, rc.PROVINCIA, rc.BELGAE, rc.WARBAND,
                get_available(state, rc.BELGAE, rc.WARBAND) - 2)
    # Use physical Allies at eligible Subdued Tribes outside the effect area.
    from fs_bot.cards.card_effects import _tribe_region
    initial = placement_request(state, rc.MORINI, rc.ROMANS)
    for tribe in sorted(state['tribes']):
        if get_available(state, rc.BELGAE, rc.ALLY) <= 1:
            break
        if (_tribe_region(state, tribe) not in initial['regions']
                and rc.TRIBE_FACTION_RESTRICTION.get(tribe, rc.BELGAE) == rc.BELGAE):
            _ally_tribe(state, tribe, rc.BELGAE)
    request = placement_request(state, rc.MORINI, rc.ROMANS)
    assert request['allies'] == 1 and request['warbands'] == 2
    plan = default_placement(state, request)
    validate_response(state, request, plan)
    plan['warbands'] = []
    with pytest.raises(ValueError, match='entire'):
        validate_response(state, request, plan)


@pytest.mark.parametrize('bad', [
    {'activate': 1}, {'activate': 1.0}, {'activate': 'true'},
    {'use_default': 1}, {'use_default': 1.0}, {'activate': True, 'extra': True},
])
def test_invalid_timing_rolls_back_and_retains_holder(bad):
    state = position()
    before = encode(state)
    state['decision_agent'] = lambda *args: bad
    with pytest.raises(ValueError):
        resolve(state)
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before


@pytest.mark.parametrize('change', [
    lambda p: p.update(allies=[]),
    lambda p: p.update(allies=[p['allies'][0]] * 2),
    lambda p: p.update(warbands=[]),
    lambda p: p.update(warbands=[{'region': rc.BRITANNIA, 'count': 4}]),
    lambda p: p.update(warbands=[{'region': rc.MORINI, 'count': True}]),
    lambda p: p.update(warbands=[{'region': rc.MORINI, 'count': 4.0}]),
    lambda p: p.update(warbands=[{'region': rc.MORINI, 'count': 5}]),
    lambda p: p.update(warbands=[{'region': rc.MORINI, 'count': -1}]),
    lambda p: p.update(warbands=[{'region': rc.MORINI, 'count': 4, 'piece_state': rc.REVEALED}]),
])
def test_invalid_physical_allocation_is_atomic(change):
    state = position()
    request = placement_request(state, rc.MORINI, rc.ROMANS)
    plan = default_placement(state, request)
    change(plan)
    before = encode(state)
    state['decision_agent'] = lambda board, actor, req: {'activate': True} if req['kind'] == TIMING else plan
    with pytest.raises(ValueError):
        resolve(state)
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before


def test_np_holder_removes_at_first_window_without_human_timing():
    state = position(owner=rc.GERMANS)
    seen = []
    def agent(board, actor, request):
        seen.append(request['kind'])
        return {'use_default': True}
    state['decision_agent'] = agent
    result = resolve(state)
    assert TIMING not in seen and PLACEMENT in seen
    assert result[0]['holder'] == rc.GERMANS
    assert not active(state)
    assert validate_state(state) == []


@pytest.mark.parametrize('marker', [rc.MARKER_WINTER_UPRISING, 'Uprising'])
def test_legacy_marker_without_holder_never_invents_a_human_owner(marker):
    state = build_initial_state(rc.SCENARIO_GALLIC_WAR, seed=3)
    state['markers'][rc.CISALPINA] = {marker: True}
    state['capabilities']['A66'] = rc.EVENT_SHADED
    calls = []
    state['decision_agent'] = lambda *args: calls.append(args[1:])
    result = resolve(state)
    assert calls == []
    assert result[0]['holder'] is None and result[0]['legacy_holder_unknown']
    assert not active(state)
    assert validate_state(state) == []


def test_legacy_recorded_owner_is_recovered_without_guessing_from_geography():
    state = build_initial_state(rc.SCENARIO_GALLIC_WAR, seed=3)
    state['markers'][rc.MORINI] = {rc.MARKER_WINTER_UPRISING: True}
    state['capabilities']['A66'] = rc.EVENT_SHADED
    state['capability_owners'] = {'A66': rc.AEDUI}
    assert holder(state) == rc.AEDUI
    state['decision_agent'] = lambda *args: {'activate': False}
    assert resolve(state)[0]['deferred']
    assert active(state)
