"""A66 delayed placements use printed NP priorities within trusted scope."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import get_available, place_piece
from fs_bot.cards.winter_uprising_np import np_placements
from fs_bot.state.state_schema import build_initial_state


def position(seed=5, scenario=rc.SCENARIO_ARIOVISTUS):
    return build_initial_state(scenario, seed=seed)


def test_most_allies_select_region_before_city_priority_and_all_warbands_follow():
    state = position()
    # Mandubii has two offered non-City Tribes; Atrebates has only Remi.
    # Region quantity precedes the within-Region City/Remi priority.
    plan = np_placements(state, rc.BELGAE, [rc.ATREBATES, rc.MANDUBII],
                         [rc.TRIBE_REMI, rc.TRIBE_SENONES, rc.TRIBE_LINGONES], 2, 4)
    assert set(plan['allies']) == {rc.TRIBE_SENONES, rc.TRIBE_LINGONES}
    assert plan['warbands'] == [{'region': rc.MANDUBII, 'count': 4}]


@pytest.mark.parametrize('faction,scenario', [
    (rc.BELGAE, rc.SCENARIO_ARIOVISTUS),
    (rc.GERMANS, rc.SCENARIO_ARIOVISTUS),
    (rc.ARVERNI, rc.SCENARIO_ARIOVISTUS),
    (rc.BELGAE, rc.SCENARIO_GALLIC_WAR),
])
def test_complete_first_region_then_next_and_city_first_locally(faction, scenario):
    state = position(scenario=scenario)
    plan = np_placements(state, faction, [rc.MANDUBII, rc.TREVERI],
                         [rc.TRIBE_MANDUBII, rc.TRIBE_SENONES,
                          rc.TRIBE_LINGONES, rc.TRIBE_TREVERI], 4, 8)
    assert plan['allies'][0] == rc.TRIBE_MANDUBII
    assert set(plan['allies'][:3]) == {
        rc.TRIBE_MANDUBII, rc.TRIBE_SENONES, rc.TRIBE_LINGONES}
    assert plan['allies'][3] == rc.TRIBE_TREVERI
    assert plan['warbands'] == [{'region': rc.MANDUBII, 'count': 8}]


def test_remi_precedes_other_tribes_within_selected_region():
    state = position()
    plan = np_placements(state, rc.BELGAE, [rc.ATREBATES],
                         [rc.TRIBE_ATREBATES, rc.TRIBE_BELLOVACI, rc.TRIBE_REMI], 1, 4)
    assert plan == {'allies': [rc.TRIBE_REMI],
                    'warbands': [{'region': rc.ATREBATES, 'count': 4}]}


def test_uses_bounded_available_counts_without_mutating_board_or_inputs():
    state = position()
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND,
                get_available(state, rc.GERMANS, rc.WARBAND) - 2)
    regions, tribes = [rc.UBII, rc.SUGAMBRI], [rc.TRIBE_SUEBI_SOUTH]
    before = deepcopy({key: value for key, value in state.items() if key != 'rng'})
    plan = np_placements(state, rc.GERMANS, regions, tribes, 1,
                         get_available(state, rc.GERMANS, rc.WARBAND))
    assert plan == {'allies': [rc.TRIBE_SUEBI_SOUTH],
                    'warbands': [{'region': rc.UBII, 'count': 2}]}
    assert {key: value for key, value in state.items() if key != 'rng'} == before
    assert regions == [rc.UBII, rc.SUGAMBRI]
    assert tribes == [rc.TRIBE_SUEBI_SOUTH]


def test_seeded_ties_ignore_input_order_and_existing_leader_and_troops():
    state = position(seed=0)
    place_piece(state, rc.UBII, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 4)
    clone = deepcopy(state)
    first = np_placements(state, rc.GERMANS, [rc.UBII, rc.SUGAMBRI], [], 0, 4)
    second = np_placements(clone, rc.GERMANS, [rc.SUGAMBRI, rc.UBII], [], 0, 4)
    assert first == second
    assert state['rng'].getstate() == clone['rng'].getstate()
    # Across ordinary seeds both equal Regions remain possible, including
    # the Region without the Leader; no invented placement priority applies.
    chosen = set()
    for seed in range(10):
        state['rng'].seed(seed)
        chosen.add(np_placements(state, rc.GERMANS, [rc.UBII, rc.SUGAMBRI], [], 0, 4)
                   ['warbands'][0]['region'])
    assert chosen == {rc.UBII, rc.SUGAMBRI}


def test_ally_cap_limits_regional_comparison_before_tie_break():
    state = position()
    seen = []
    class Rng:
        def randint(self, low, high):
            seen.append((low, high))
            return low
    state['rng'] = Rng()
    # One available Ally makes a two-slot Region and a one-slot Region equal.
    plan = np_placements(state, rc.BELGAE, [rc.MANDUBII, rc.ATREBATES],
                         [rc.TRIBE_SENONES, rc.TRIBE_LINGONES, rc.TRIBE_REMI], 1, 0)
    assert plan['allies'] == [rc.TRIBE_REMI]
    assert seen == [(0, 1)]


def test_no_placements_does_not_consume_rng():
    state = position()
    before = state['rng'].getstate()
    assert np_placements(state, rc.BELGAE, [rc.ATREBATES], [rc.TRIBE_REMI], 0, 0) == {
        'allies': [], 'warbands': []}
    assert np_placements(state, rc.BELGAE, [], [], 0, 0) == {
        'allies': [], 'warbands': []}
    assert state['rng'].getstate() == before


def test_trusted_scope_never_expands_to_other_regions_or_tribes():
    state = position()
    # The caller omits Cisalpina and every ineligible Tribe. The planner must
    # not regenerate a broader candidate list based on the marker or map.
    plan = np_placements(state, rc.ARVERNI, [rc.SEQUANI], [rc.TRIBE_HELVETII], 1, 8)
    assert plan == {'allies': [rc.TRIBE_HELVETII],
                    'warbands': [{'region': rc.SEQUANI, 'count': 8}]}
