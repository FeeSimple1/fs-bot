"""A66's marker must exist, and NP targets follow the supplied Event sheets.

The Gallic War seed 8 exposed the old markerless trigger after Belgae had no
pieces anywhere: the deriver invented an own-piece prerequisite, returned
None, and the handler nevertheless committed the delayed Event.
"""
import copy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.bots.belgae_bot import node_b3b
from fs_bot.bots.german_bot import node_g3b
from fs_bot.bots.bot_common import should_decline_event
from fs_bot.cards.card_effects import execute_card_A66
from fs_bot.cards.event_conditions import np_event_available
from fs_bot.cards.event_eval import IS_CAPABILITY, get_event_flags, should_skip_event
from fs_bot.cards.param_schema import card_param_schema, region_pool
from fs_bot.cards.winter_uprising import (
    derive_params, np_regions, placement_regions,
)
from fs_bot.engine.execute import _derive_card_A66, _execute_event, _resolve_winter_uprising
from fs_bot.engine.game_engine import get_sop_factions, next_winter_is_final
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state


def _state(scenario=rc.SCENARIO_ARIOVISTUS, seed=8):
    state = build_initial_state(scenario, seed=seed)
    state['non_player_factions'] = set(get_sop_factions(state))
    state['current_card'] = state['current_card_id'] = 'A66'
    state['deck'] = [1, rc.WINTER_CARD, 35, rc.WINTER_CARD]
    state['next_card'] = 1
    state['event_modifiers'] = {}
    return state


@pytest.mark.parametrize('scenario', rc.ARIOVISTUS_SCENARIOS)
@pytest.mark.parametrize('faction,regions', [
    (rc.BELGAE, rc.BELGICA_REGIONS), (rc.GERMANS, rc.GERMANIA_REGIONS),
])
def test_np_can_place_without_any_own_pieces_and_uses_printed_area(scenario, faction, regions):
    state = _state(scenario)
    assert all(not count_pieces(state, region, faction) for region in state['spaces'])
    assert np_regions(state, faction) == sorted(regions)
    assert not should_decline_event(state, 'A66', faction)
    result = _execute_event(state, faction, {'command': 'Event', 'details': {
        'card_id': 'A66', 'text_preference': rc.EVENT_SHADED}})
    assert result['executed']
    region = state['event_modifiers']['card_A66_uprising_region']
    assert region in regions
    assert rc.MARKER_WINTER_UPRISING in state['markers'][region]


@pytest.mark.parametrize('faction,regions', [
    (rc.BELGAE, rc.BELGICA_REGIONS), (rc.GERMANS, rc.GERMANIA_REGIONS),
])
def test_own_forces_and_settlements_outside_printed_area_do_not_move_marker_pool(faction, regions):
    state = _state()
    place_piece(state, rc.TREVERI, faction, rc.WARBAND, 4)
    if faction == rc.GERMANS:
        place_piece(state, rc.TREVERI, faction, rc.SETTLEMENT, 1)
    assert np_regions(state, faction) == sorted(regions)
    assert _derive_card_A66(state, faction, False)['region'] in regions


def test_marker_ties_use_seeded_rng_instead_of_alphabetic_first():
    state = _state(seed=3)
    same = copy.deepcopy(state)
    assert derive_params(state, rc.BELGAE) == derive_params(same, rc.BELGAE)
    assert state['rng'].getstate() == same['rng'].getstate()
    selected = {derive_params(_state(seed=seed), rc.BELGAE)['region'] for seed in range(12)}
    assert selected == set(rc.BELGICA_REGIONS)


@pytest.mark.parametrize('region', [None, '', 'not a Region', rc.BRITANNIA, [], False])
def test_missing_or_nonplayable_target_rejects_before_mutating_existing_effect(region):
    state = _state()
    state['markers'][rc.MORINI] = {rc.MARKER_WINTER_UPRISING: True}
    state['event_modifiers'].update(card_A66_winter_uprising=True,
                                    card_A66_uprising_region=rc.MORINI)
    state['event_params'] = {'region': region}
    before = encode(state)
    with pytest.raises(ValueError, match='playable Region'):
        execute_card_A66(state)
    assert encode(state) == before


def test_missing_target_at_event_boundary_does_not_install_markerless_trigger():
    state = _state()
    result = _execute_event(state, rc.ROMANS, {'command': 'Event', 'details': {
        'card_id': 'A66', 'event_params': {}, 'text_preference': rc.EVENT_UNSHADED}}, human=True)
    assert not result['executed']
    assert 'card_A66_winter_uprising' not in state['event_modifiers']
    assert 'card_A66_uprising_region' not in state['event_modifiers']
    assert not any(rc.MARKER_WINTER_UPRISING in markers for markers in state['markers'].values())


@pytest.mark.parametrize('params', [[], [rc.MORINI], rc.MORINI, False, None])
def test_malformed_target_container_rejects_cleanly_at_event_boundary(params):
    state = _state()
    before = encode(state)
    result = _execute_event(state, rc.ROMANS, {'command': 'Event', 'details': {
        'card_id': 'A66', 'event_params': params}}, human=True)
    assert not result['executed']
    assert encode(state) == before


def test_human_can_place_in_empty_cisalpina_even_when_next_winter_is_final():
    state = _state()
    state['deck'] = [1, rc.WINTER_CARD]
    state['event_params'] = {'region': rc.CISALPINA}
    state['markers'][rc.CISALPINA] = set()
    assert next_winter_is_final(state)
    execute_card_A66(state)
    assert rc.MARKER_WINTER_UPRISING in state['markers'][rc.CISALPINA]
    assert state['event_modifiers']['card_A66_uprising_region'] == rc.CISALPINA


@pytest.mark.parametrize('faction,node', [(rc.BELGAE, node_b3b), (rc.GERMANS, node_g3b)])
def test_real_final_winter_declines_without_needing_unpopulated_final_year_flag(faction, node):
    state = _state()
    state['deck'] = [1, rc.WINTER_CARD]
    assert 'final_year' not in state
    assert next_winter_is_final(state)
    assert not np_regions(state, faction)
    assert np_event_available(state, 'A66', faction, True) is False
    assert should_decline_event(state, 'A66', faction)
    assert should_skip_event(state, 'A66', faction)
    assert node(state) == 'Yes'


@pytest.mark.parametrize('faction,node', [(rc.BELGAE, node_b3b), (rc.GERMANS, node_g3b)])
def test_gallic_war_third_winter_continues_and_still_allows_uprising(faction, node):
    state = _state(rc.SCENARIO_GALLIC_WAR)
    state['winter_count'] = 2
    state['played_cards'] = [rc.WINTER_CARD, rc.WINTER_CARD, 'A66']
    state['deck'] = [1, rc.WINTER_CARD]
    assert not next_winter_is_final(state)
    assert np_regions(state, faction)
    assert not should_skip_event(state, 'A66', faction)
    assert node(state) == 'No'


def test_interlude_continuation_count_matches_existing_winter_engine():
    state = _state(rc.SCENARIO_PAX_GALLICA)
    state['interlude_completed'] = True
    state['winter_count'] = 3
    state['played_cards'] = [1]
    state['deck'] = [2, rc.WINTER_CARD, 3, rc.WINTER_CARD]
    assert not next_winter_is_final(state)
    state['winter_count'] = 4
    state['deck'] = [2, rc.WINTER_CARD]
    assert next_winter_is_final(state)
    # Counting a final Winter does not introduce expansion Events into base play.
    assert not placement_regions(state)


def test_empty_faction_marker_resolves_once_without_missing_marker_diagnostic():
    state = _state(rc.SCENARIO_GALLIC_WAR)
    state['event_params'] = derive_params(state, rc.BELGAE)
    execute_card_A66(state)
    region = state['event_params']['region']
    state['decision_agent'] = lambda *args: {'use_default': True}
    results = _resolve_winter_uprising(state)
    assert results[0]['faction'] == rc.BELGAE
    assert results[0]['warbands'] == 4 and results[0]['allies'] == 2
    assert all(result.get('reason') != 'no Uprising marker region' for result in results)
    assert rc.MARKER_WINTER_UPRISING not in state['markers'][region]
    assert 'card_A66_winter_uprising' not in state['event_modifiers']
    assert 'card_A66_uprising_region' not in state['event_modifiers']


def test_a66_schema_requires_scenario_region_pool_and_classifies_marker_not_capability():
    state = _state()
    schema = card_param_schema('A66', state['scenario'])
    assert region_pool(state, schema['region']['region_pool']) == placement_regions(state)
    assert rc.CISALPINA in placement_regions(state) and rc.BRITANNIA not in placement_regions(state)
    for shaded in (False, True):
        assert IS_CAPABILITY not in get_event_flags('A66', shaded, state['scenario'])
