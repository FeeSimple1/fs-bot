"""Ambacti's printed NP instructions, not dictionary order, choose Auxilia."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, get_available, remove_piece
from fs_bot.cards.ambacti_np import default_removals, derive_unshaded, np_available
from fs_bot.state.state_schema import build_initial_state


def position(scenario=rc.SCENARIO_GREAT_REVOLT, seed=1):
    return build_initial_state(scenario, seed=seed)


def add(state, region, count, *, legion=False, visibility=rc.HIDDEN):
    place_piece(state, region, rc.ROMANS, rc.AUXILIA, count, piece_state=visibility)
    if legion:
        place_piece(state, region, rc.ROMANS, rc.LEGION, from_legions_track=True)


def totals(plan):
    answer = {}
    for entry in plan:
        answer[entry['region']] = answer.get(entry['region'], 0) + entry['count']
    return answer


def test_arverni_maximize_regions_with_unescorted_legions():
    state = position()
    add(state, rc.PROVINCIA, 6, legion=True)
    add(state, rc.SEQUANI, 2, legion=True)
    add(state, rc.MANDUBII, 2, legion=True)
    add(state, rc.CARNUTES, 1, legion=True)
    assert totals(default_removals(state, rc.ARVERNI, 5)) == {
        rc.SEQUANI: 2, rc.MANDUBII: 2, rc.CARNUTES: 1}


def test_arverni_preserve_maximum_exposure_before_general_location_priority():
    state = position()
    add(state, rc.PROVINCIA, 1, legion=True)
    add(state, rc.SEQUANI, 2, legion=True)
    add(state, rc.MANDUBII, 3, legion=True)
    # Both 1+2 and 1+3 expose two Regions. Within that, choose the Region
    # removing the most before moving to another (§8.3.1).
    plan = default_removals(state, rc.ARVERNI, 4)
    assert [entry['region'] for entry in plan] == [rc.MANDUBII, rc.PROVINCIA]
    assert totals(plan) == {rc.MANDUBII: 3, rc.PROVINCIA: 1}


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
def test_belgae_exhaust_belgica_before_other_regions(scenario):
    state = position(scenario)
    add(state, rc.PROVINCIA, 5)
    add(state, rc.MORINI, 1)
    add(state, rc.NERVII, 2)
    plan = default_removals(state, rc.BELGAE, 4)
    assert [entry['region'] for entry in plan] == [rc.NERVII, rc.MORINI, rc.PROVINCIA]
    assert totals(plan) == {rc.NERVII: 2, rc.MORINI: 1, rc.PROVINCIA: 1}


def test_germans_remove_primary_then_adjacent_then_mandatory_remainder():
    state = position(rc.SCENARIO_ARIOVISTUS)
    add(state, rc.SUGAMBRI, 1)
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.SETTLEMENT)
    add(state, rc.CARNUTES, 2)
    # Treveri is adjacent to Germania. Provincia is in neither tier.
    add(state, rc.TREVERI, 1)
    add(state, rc.PROVINCIA, 5)
    plan = default_removals(state, rc.GERMANS, 5)
    assert [entry['region'] for entry in plan] == [
        rc.CARNUTES, rc.SUGAMBRI, rc.TREVERI, rc.PROVINCIA]
    assert totals(plan) == {rc.CARNUTES: 2, rc.SUGAMBRI: 1,
                            rc.TREVERI: 1, rc.PROVINCIA: 1}


def test_germans_no_event_outside_geographic_instruction_and_check_uses_no_rng():
    state = position(rc.SCENARIO_ARIOVISTUS)
    add(state, rc.PROVINCIA, 4)
    before = state['rng'].getstate()
    assert np_available(state, rc.GERMANS, True) is False
    assert np_available(state, rc.BELGAE, True) is True
    assert state['rng'].getstate() == before
    add(state, rc.TREVERI, 1)
    assert np_available(state, rc.GERMANS, True) is True
    assert state['rng'].getstate() == before


def test_base_german_default_does_not_use_expansion_geographic_priority():
    state = position()
    add(state, rc.SUGAMBRI, 1)
    add(state, rc.PROVINCIA, 5)
    assert totals(default_removals(state, rc.GERMANS, 3)) == {rc.PROVINCIA: 3}


def test_anywhere_includes_existing_pieces_outside_current_placement_geography():
    state = position()
    state['markers'].setdefault(rc.CISALPINA, {})[rc.MARKER_GALLIA_TOGATA] = True
    add(state, rc.CISALPINA, 2)
    del state['markers'][rc.CISALPINA][rc.MARKER_GALLIA_TOGATA]
    # Legacy/peripheral pieces remain valid removal targets; the unshaded
    # placement helper must still enforce currently playable geography.
    assert totals(default_removals(state, rc.BELGAE, 6)) == {rc.CISALPINA: 2}
    assert np_available(state, rc.BELGAE, True)
    assert derive_unshaded(state, rc.ROMANS) is None


@pytest.mark.parametrize('faction,order', [
    (rc.BELGAE, [rc.HIDDEN, rc.REVEALED, rc.SCOUTED]),
    (rc.ROMANS, [rc.SCOUTED, rc.REVEALED, rc.HIDDEN]),
])
def test_physical_visibility_priority_is_reversed_for_own_losses(faction, order):
    state = position()
    for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        add(state, rc.PROVINCIA, 1, visibility=visibility)
    plan = default_removals(state, faction, 6)
    assert [entry['piece_state'] for entry in plan] == order
    assert sum(entry['count'] for entry in plan) == 3


def test_seeded_ties_do_not_mutate_board_and_are_independent_of_space_order():
    state = position()
    add(state, rc.CARNUTES, 3)
    add(state, rc.SEQUANI, 3)
    clone = deepcopy(state)
    clone['spaces'] = dict(reversed(list(clone['spaces'].items())))
    before = deepcopy(state['spaces'])
    before_rng = state['rng'].getstate()
    assert default_removals(state, rc.AEDUI, 3) == default_removals(clone, rc.AEDUI, 3)
    assert state['rng'].getstate() == clone['rng'].getstate()
    assert state['rng'].getstate() != before_rng
    assert state['spaces'] == before


def test_unshaded_prefers_actual_six_with_named_caesar():
    state = position()
    add(state, rc.PROVINCIA, 8)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    assert derive_unshaded(state, rc.ROMANS) == {'target_region': rc.SEQUANI}


def test_successor_and_small_available_pool_do_not_gain_caesar_priority():
    successor = position(seed=0)
    place_piece(successor, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.SUCCESSOR)
    add(successor, rc.PROVINCIA, 1)
    caesar = deepcopy(successor)
    remove_piece(caesar, rc.SEQUANI, rc.ROMANS, rc.LEADER)
    place_piece(caesar, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    add(caesar, rc.PROVINCIA, get_available(caesar, rc.ROMANS, rc.AUXILIA) - 3)
    # All tied legal Regions are offered to the seeded selector in each
    # case; neither a successor nor a six-piece cap with only three
    # Available creates a placement advantage.
    seen = []
    class Picker:
        def randint(self, low, high):
            seen.append((low, high))
            return low
    successor['rng'] = Picker()
    caesar['rng'] = Picker()
    assert derive_unshaded(successor, rc.ROMANS) == {'target_region': rc.PROVINCIA}
    assert derive_unshaded(caesar, rc.ROMANS) == {'target_region': rc.PROVINCIA}
    assert seen == [(0, 1), (0, 1)]


def test_unshaded_no_legal_placement_declines_without_rng():
    state = position()
    before = state['rng'].getstate()
    assert derive_unshaded(state, rc.ROMANS) is None
    assert derive_unshaded(state, rc.AEDUI) is None
    assert state['rng'].getstate() == before


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
def test_aedui_can_execute_fixed_roman_benefit(scenario):
    from fs_bot.engine.execute import _execute_event
    from fs_bot.cards.event_conditions import np_event_available
    from fs_bot.board.pieces import count_pieces
    state = position(scenario)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    state['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE,
                                   rc.GERMANS if scenario in rc.ARIOVISTUS_SCENARIOS else rc.ARVERNI}
    assert np_event_available(state, 16, rc.AEDUI, False)
    result = _execute_event(state, rc.AEDUI, {'details': {
        'card_id': 16, 'text_preference': rc.EVENT_UNSHADED}})
    assert result['executed']
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 6
