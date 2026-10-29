"""Spring applies §6.6's legal destinations before §§8.3.2–8.3.4 ranking."""

from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (
    count_pieces, find_leader, get_leader_in_region, place_piece, remove_piece,
)
from fs_bot.bots.bot_common import get_leader_placement_region
from fs_bot.bots.roman_bot import node_r_spring
from fs_bot.bots.arverni_bot import node_v_spring
from fs_bot.bots.belgae_bot import node_b_spring
from fs_bot.bots.german_bot import node_g_spring
from fs_bot.engine.spring import (
    np_spring_plan, place_successors, successor_regions, successor_request,
    unlock_spring_box_entry,
)
from fs_bot.map.map_data import get_playable_regions_for_state
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity


CASES = [
    (rc.SCENARIO_GREAT_REVOLT, rc.ROMANS, rc.AUXILIA,
     rc.ROMAN_HOME_REGIONS, rc.CAESAR, node_r_spring),
    (rc.SCENARIO_GREAT_REVOLT, rc.ARVERNI, rc.WARBAND,
     rc.ARVERNI_HOME_REGIONS_BASE, rc.VERCINGETORIX, node_v_spring),
    (rc.SCENARIO_GREAT_REVOLT, rc.BELGAE, rc.WARBAND,
     rc.BELGAE_HOME_REGIONS, rc.AMBIORIX, node_b_spring),
    (rc.SCENARIO_ARIOVISTUS, rc.GERMANS, rc.WARBAND,
     rc.GERMAN_HOME_REGIONS_ARIOVISTUS_STATIC, rc.ARIOVISTUS_LEADER, node_g_spring),
    (rc.SCENARIO_ARIOVISTUS, rc.ROMANS, rc.AUXILIA,
     rc.ROMAN_HOME_REGIONS, rc.CAESAR, node_r_spring),
    (rc.SCENARIO_ARIOVISTUS, rc.BELGAE, rc.WARBAND,
     rc.BELGAE_HOME_REGIONS, rc.BODUOGNATUS, node_b_spring),
]


@pytest.mark.parametrize('scenario,faction,troop,homes,named,node', CASES)
def test_np_spring_places_successor_with_most_own_pieces(scenario, faction, troop,
                                                       homes, named, node):
    state = build_initial_state(scenario, seed=3)
    place_piece(state, homes[0], faction, troop, 2)
    place_piece(state, rc.MANDUBII, faction, troop, 5)
    enemy = rc.BELGAE if faction != rc.BELGAE else rc.GERMANS
    place_piece(state, rc.SEQUANI, enemy, rc.WARBAND, 12)
    before = deepcopy({key: value for key, value in state.items() if key != 'rng'})
    assert set(successor_regions(state, faction)) == {*homes, rc.MANDUBII}
    assert node(state) == {'place_leader': rc.SUCCESSOR, 'region': rc.MANDUBII}
    assert {key: value for key, value in state.items() if key != 'rng'} == before


@pytest.mark.parametrize('scenario,faction,troop,homes,named,node', CASES)
def test_equal_own_piece_regions_have_seeded_order_independent_ties(
        scenario, faction, troop, homes, named, node):
    state = build_initial_state(scenario, seed=4)
    place_piece(state, rc.SEQUANI, faction, troop, 3)
    place_piece(state, rc.CARNUTES, faction, troop, 3)
    clone = deepcopy(state)
    clone['spaces'] = dict(reversed(list(clone['spaces'].items())))
    before_rng = state['rng'].getstate()
    assert np_spring_plan(state, faction) == np_spring_plan(clone, faction)
    assert state['rng'].getstate() == clone['rng'].getstate() != before_rng
    seen = set()
    for seed in range(20):
        state['rng'].seed(seed)
        seen.add(node(state)['region'])
    assert seen == {rc.CARNUTES, rc.SEQUANI}


@pytest.mark.parametrize('scenario,faction,troop,homes,named,node', CASES)
def test_empty_board_still_places_at_legal_home_symbols_only(
        scenario, faction, troop, homes, named, node):
    state = build_initial_state(scenario, seed=7)
    assert set(successor_request(state, faction)['legal_regions']) == set(homes)
    seen = set()
    for seed in range(20):
        state['rng'].seed(seed)
        plan = node(state)
        assert plan['place_leader'] == rc.SUCCESSOR
        seen.add(plan['region'])
    assert seen == set(homes)


def test_piece_count_includes_legions_and_forts_not_just_auxilia():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=8)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.FORT)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEGION, 2, from_legions_track=True)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 2)
    assert node_r_spring(state) == {'place_leader': rc.SUCCESSOR, 'region': rc.SEQUANI}


@pytest.mark.parametrize('scenario,faction,troop,homes,named,node', CASES)
@pytest.mark.parametrize('leader_form', ['named', 'successor'])
def test_bot_nodes_do_not_replace_existing_leader_or_consume_rng(
        scenario, faction, troop, homes, named, node, leader_form):
    state = build_initial_state(scenario, seed=3)
    place_piece(state, homes[0], faction, rc.LEADER,
                leader_name=named if leader_form == 'named' else rc.SUCCESSOR)
    before = state['rng'].getstate()
    assert node(state) is None
    assert state['rng'].getstate() == before


@pytest.mark.parametrize('scenario,faction,troop,homes,named,node', CASES)
def test_removed_named_leader_reenters_as_successor_in_actual_spring(
        scenario, faction, troop, homes, named, node):
    state = build_initial_state(scenario, seed=3)
    state['non_player_factions'] = set(rc.FACTIONS)
    consulted = []
    state['decision_agent'] = lambda *args: consulted.append(args)
    place_piece(state, rc.SEQUANI, faction, rc.LEADER, leader_name=named)
    remove_piece(state, rc.SEQUANI, faction, rc.LEADER)
    place_piece(state, rc.CARNUTES, faction, troop, 2)
    assert node(state) == {'place_leader': rc.SUCCESSOR, 'region': rc.CARNUTES}
    assert (faction, rc.CARNUTES) in place_successors(state)
    assert get_leader_in_region(state, rc.CARNUTES, faction) == rc.SUCCESSOR
    assert consulted == []
    assert check_structural_integrity(state) == []


def test_spring_box_named_vercingetorix_is_not_replaced_by_successor():
    state = setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=3)
    before = state['rng'].getstate()
    assert successor_request(state, rc.ARVERNI) is None
    assert node_v_spring(state) is None
    assert state['rng'].getstate() == before
    unlock_spring_box_entry(state)
    plan = node_v_spring(state)
    assert plan['place_leader'] == rc.VERCINGETORIX
    most = max(count_pieces(state, region, rc.ARVERNI)
               for region in get_playable_regions_for_state(state, rc.ARVERNI))
    assert count_pieces(state, plan['region'], rc.ARVERNI) == most
    assert rc.VERCINGETORIX in state['spring_box_leaders']


@pytest.mark.parametrize('scenario', rc.ARIOVISTUS_SCENARIOS)
def test_ariovistus_has_neither_arverni_leader_nor_diviciacus_successor(scenario):
    state = build_initial_state(scenario, seed=9)
    state['non_player_factions'] = set(rc.FACTIONS)
    place_piece(state, rc.AEDUI_REGION, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    remove_piece(state, rc.AEDUI_REGION, rc.AEDUI, rc.LEADER)
    assert successor_request(state, rc.AEDUI) is None
    assert np_spring_plan(state, rc.AEDUI) is None
    assert successor_request(state, rc.ARVERNI) is None
    assert node_v_spring(state) is None
    placed = place_successors(state)
    assert {faction for faction, _ in placed} == {rc.ROMANS, rc.BELGAE, rc.GERMANS}
    assert find_leader(state, rc.AEDUI) is None
    assert find_leader(state, rc.ARVERNI) is None
    assert check_structural_integrity(state) == []


def test_base_spring_does_not_create_a_german_leader_or_optional_diviciacus_successor():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=9, diviciacus_option=True)
    assert node_g_spring(state) is None
    assert successor_request(state, rc.AEDUI) is None
    assert np_spring_plan(state, rc.AEDUI) is None


def test_shared_selector_default_retains_unrestricted_event_destinations():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=1)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 4)
    assert get_leader_placement_region(state, rc.ROMANS) == rc.CARNUTES
    assert get_leader_placement_region(state, rc.ROMANS,
                                       candidates=[rc.PROVINCIA]) == rc.PROVINCIA
    # An Event may place a Leader in any playable Region even when no own
    # piece or Home symbol is there. Spring supplies its narrower candidate set.
    remove_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 4)
    selected = {get_leader_placement_region(state, rc.ROMANS) for _ in range(50)}
    assert selected - set(rc.ROMAN_HOME_REGIONS)
    assert selected <= set(get_playable_regions_for_state(state, rc.ROMANS))
    assert np_spring_plan(state, rc.ROMANS)['region'] == rc.PROVINCIA


def test_shared_selector_empty_or_inactive_candidates_return_none_without_rng():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=3)
    before = state['rng'].getstate()
    assert get_leader_placement_region(state, rc.ROMANS, candidates=[]) is None
    assert get_leader_placement_region(state, rc.ROMANS,
                                       candidates=[rc.BRITANNIA]) is None
    assert state['rng'].getstate() == before


def test_spring_and_shared_selector_honor_active_gallia_togata_geography():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=3)
    state['markers'].setdefault(rc.CISALPINA, {})[rc.MARKER_GALLIA_TOGATA] = {'card_id': 5}
    place_piece(state, rc.CISALPINA, rc.ROMANS, rc.AUXILIA, 3)
    assert rc.CISALPINA in successor_regions(state, rc.ROMANS)
    assert node_r_spring(state)['region'] == rc.CISALPINA
    del state['markers'][rc.CISALPINA][rc.MARKER_GALLIA_TOGATA]
    assert rc.CISALPINA not in successor_regions(state, rc.ROMANS)
    assert get_leader_placement_region(state, rc.ROMANS,
                                       candidates=[rc.CISALPINA]) is None
    assert node_r_spring(state)['region'] == rc.PROVINCIA


def test_active_gallia_togata_does_not_offer_cisalpina_to_non_roman_leaders():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=3)
    # Test an already present force across a change in active map permissions.
    place_piece(state, rc.CISALPINA, rc.BELGAE, rc.WARBAND, 4)
    assert node_b_spring(state)['region'] == rc.CISALPINA
    state['markers'].setdefault(rc.CISALPINA, {})[rc.MARKER_GALLIA_TOGATA] = {'card_id': 'A5'}
    assert rc.CISALPINA not in successor_regions(state, rc.BELGAE)
    assert get_leader_placement_region(state, rc.BELGAE,
                                       candidates=[rc.CISALPINA]) is None
    assert node_b_spring(state)['region'] in rc.BELGAE_HOME_REGIONS
