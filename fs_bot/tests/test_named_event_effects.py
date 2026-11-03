"""BE-04: literal named ownership, optional effects and exact source choices."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece, remove_piece, get_available
from fs_bot.cards.card_effects import execute_event, _ally_tribe
from fs_bot.cards.named_event_effects import (options, preview, request, validate_response,
                                             default_params, np_available)
from fs_bot.engine.execute import _execute_event, _derive_event_params
from fs_bot.engine.free_actions import validate_free_action_response
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state


def board(card=2, actor=None, scenario=None):
    state = build_initial_state(scenario or (rc.SCENARIO_ARIOVISTUS if card == 'A18' else rc.SCENARIO_GREAT_REVOLT), seed=816)
    state['senate'] = {'position': rc.INTRIGUE, 'firm': False}
    state['resources'][rc.ROMANS] = 12
    state['executing_faction'] = actor or (rc.ARVERNI if card == 26 else rc.ROMANS)
    state['non_player_factions'] = set()
    state['event_params'] = {}
    return state


def apply(state, card, params):
    action = {'command': rc.FIRST_DID_EVENT, 'details': {'card_id': card,
        'text_preference': rc.EVENT_SHADED if card == 26 else rc.EVENT_UNSHADED,
        'event_params': params}}
    return _execute_event(state, state['executing_faction'], action, human=True)


def fallen(state, n):
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION, n, from_legions_track=True)
    remove_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION, n, to_fallen=True)


def german_region(state, region=rc.SUGAMBRI, leader=None):
    for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        place_piece(state, region, rc.GERMANS, rc.WARBAND, 1, piece_state=visibility)
    _ally_tribe(state, rc.TRIBE_SUGAMBRI if region == rc.SUGAMBRI else rc.TRIBE_UBII, rc.GERMANS)
    if state['scenario'] in rc.ARIOVISTUS_SCENARIOS:
        place_piece(state, region, rc.GERMANS, rc.SETTLEMENT)
        if leader:
            place_piece(state, region, rc.GERMANS, rc.LEADER, leader_name=leader)
    place_piece(state, region, rc.ROMANS, rc.AUXILIA, 8)


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
def test_legiones_np_default_places_two_instead_of_shifting_without_placement(scenario):
    state = board(scenario=scenario)
    state['non_player_factions'] = {rc.ROMANS}
    params = _derive_event_params(state, rc.ROMANS, 2, False)
    assert params == {'legions_from_track': 2, 'legions_from_fallen': 0}
    result = _execute_event(state, rc.ROMANS, {'command': rc.FIRST_DID_EVENT,
        'details': {'card_id': 2, 'text_preference': rc.EVENT_UNSHADED}})
    assert result['executed']
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == 2
    assert state['senate']['position'] == rc.UPROAR


@pytest.mark.parametrize('track,fall', [(2, 0), (1, 1), (0, 2)])
def test_legiones_human_can_choose_each_complete_source_allocation(track, fall):
    state = board()
    fallen(state, 2)
    assert apply(state, 2, {'legions_from_track': track, 'legions_from_fallen': fall})['executed']
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == 2
    assert state['fallen_legions'] == 2 - fall
    assert validate_state(state) == []


@pytest.mark.parametrize('params', [
    {'legions_from_track': 1}, {'legions_from_track': 3},
    {'legions_from_track': True}, {'legions_from_track': -1},
    {'legions_from_track': 1.0}, {'legions_from_fallen': 2},
    {'legions_from_track': 2, 'acting_faction': rc.BELGAE},
    {'decline': 1}, {'decline': True, 'legions_from_track': 2},
])
def test_legiones_invalid_or_incomplete_sources_reject_atomically(params):
    state = board()
    before = encode(state)
    result = apply(state, 2, params)
    assert result['rejected'] and not result['executed']
    assert encode(state) == before


@pytest.mark.parametrize('remaining', [0, 1])
def test_legiones_human_may_accept_available_shortage_but_np_requires_two(remaining):
    state = board()
    total = sum(state['legions_track'].values())
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEGION, total - remaining, from_legions_track=True)
    assert not np_available(state, 2)
    assert default_params(state, 2) == {'decline': True}
    result = apply(state, 2, {'legions_from_track': remaining, 'legions_from_fallen': 0})
    assert result['executed']
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == remaining
    assert state['senate']['position'] == rc.UPROAR


@pytest.mark.parametrize('position,firm,expected_position,expected_firm,placed', [
    (None, False, None, False, 0),
    (rc.UPROAR, True, rc.UPROAR, True, 0),
    (rc.UPROAR, False, rc.UPROAR, True, 2),
    (rc.ADULATION, True, rc.ADULATION, False, 2),
    (rc.INTRIGUE, True, rc.INTRIGUE, False, 2),
])
def test_legiones_senate_shift_prerequisite_and_firm_flips(position, firm, expected_position, expected_firm, placed):
    state = board()
    state['senate'] = {'position': position, 'firm': firm}
    assert apply(state, 2, {'legions_from_track': 2})['executed']
    assert state['senate'] == {'position': expected_position, 'firm': expected_firm}
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == placed


def test_legiones_equal_source_allocations_are_seeded_not_fallen_first():
    state = board()
    fallen(state, 2)
    clone = deepcopy(state)
    seen = set()
    for _ in range(20):
        result = default_params(state, 2)
        assert result == default_params(clone, 2)
        seen.add((result['legions_from_track'], result['legions_from_fallen']))
    assert seen == {(2, 0), (1, 1), (0, 2)}


@pytest.mark.parametrize('card', [18, 'A18'])
def test_rhenus_removes_all_exact_visibility_and_structures(card):
    state = board(card)
    german_region(state, leader=rc.SUCCESSOR if card == 'A18' else None)
    assert apply(state, card, {'target_region': rc.SUGAMBRI})['executed']
    assert count_pieces(state, rc.SUGAMBRI, rc.GERMANS) == 0
    assert state['tribes'][rc.TRIBE_SUGAMBRI]['allied_faction'] is None
    assert validate_state(state) == []


def test_a18_named_ariovistus_protects_entire_region_but_successor_does_not():
    state = board('A18')
    german_region(state, leader=rc.ARIOVISTUS_LEADER)
    assert rc.SUGAMBRI not in options(state, 'A18')['target_regions']
    before = encode(state)
    result = apply(state, 'A18', {'target_region': rc.SUGAMBRI})
    assert result['rejected'] and encode(state) == before


@pytest.mark.parametrize('params', [{'target_region': rc.PROVINCIA}, {'target_region': None},
                                  {'target_region': []}, {'target_region': rc.SUGAMBRI, 'region': rc.UBII}])
def test_rhenus_illegal_or_malformed_targets_are_rejected(params):
    state = board(18)
    german_region(state)
    before = encode(state)
    assert apply(state, 18, params)['rejected']
    assert encode(state) == before


def test_a18_legacy_region_alias_retains_exact_roman_owned_selection():
    state = board('A18')
    german_region(state, leader=rc.SUCCESSOR)
    assert apply(state, 'A18', {'region': rc.SUGAMBRI})['executed']
    assert count_pieces(state, rc.SUGAMBRI, rc.GERMANS) == 0


@pytest.mark.parametrize('status', [None, rc.DISPERSED, rc.DISPERSED_GATHERING, rc.MARKER_RAZED])
def test_sacking_accepts_replace_anything_city_including_existing_razed(status):
    state = board(23)
    place_piece(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA, 2)
    state['tribes'][rc.TRIBE_ARVERNI]['status'] = status
    if status is None:
        _ally_tribe(state, rc.TRIBE_ARVERNI, rc.ARVERNI)
    assert rc.CITY_GERGOVIA in options(state, 23)['target_cities']
    assert apply(state, 23, {'target_city': rc.CITY_GERGOVIA})['executed']
    assert state['tribes'][rc.TRIBE_ARVERNI]['status'] == rc.MARKER_RAZED
    assert state['tribes'][rc.TRIBE_ARVERNI]['allied_faction'] is None
    assert state['resources'][rc.ROMANS] == 20
    assert validate_state(state) == []


def test_sacking_roman_own_ally_is_valid_human_choice():
    state = board(23)
    _ally_tribe(state, rc.TRIBE_BITURIGES, rc.ROMANS)
    assert apply(state, 23, {'target_city': rc.CITY_AVARICUM})['executed']
    assert count_pieces(state, rc.BITURIGES, rc.ROMANS, rc.ALLY) == 0
    assert state['tribes'][rc.TRIBE_BITURIGES]['status'] == rc.MARKER_RAZED


def test_sacking_named_city_required_and_lack_of_roman_control_rejects():
    state = board(23)
    before = encode(state)
    assert apply(state, 23, {'target_city': rc.CITY_GERGOVIA})['rejected']
    assert encode(state) == before
    place_piece(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA)
    assert apply(state, 23, {'target_city': rc.TRIBE_ARVERNI})['rejected']


def test_sacking_np_prefers_enemy_citadel_to_more_common_empty_city():
    state = board(23)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.CITADEL)
    state['tribes'][rc.TRIBE_ARVERNI]['allied_faction'] = rc.ARVERNI
    place_piece(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.BITURIGES, rc.ROMANS, rc.AUXILIA)
    assert default_params(state, 23) == {'target_city': rc.CITY_GERGOVIA}


def test_sacking_no_effect_at_resource_cap_on_only_already_razed_city_is_np_decline():
    state = board(23)
    place_piece(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA)
    state['tribes'][rc.TRIBE_ARVERNI]['status'] = rc.MARKER_RAZED
    state['resources'][rc.ROMANS] = rc.MAX_RESOURCES
    assert not np_available(state, 23)
    assert default_params(state, 23) == {'decline': True}


def test_gobannitio_exact_any_faction_allies_removable_and_only_arverni_placements():
    state = board(26)
    _ally_tribe(state, rc.TRIBE_CADURCI, rc.AEDUI)
    _ally_tribe(state, rc.TRIBE_VOLCAE, rc.BELGAE)
    _ally_tribe(state, rc.TRIBE_ARVERNI, rc.ARVERNI)
    params = {'ally_removals': [rc.TRIBE_CADURCI, rc.TRIBE_ARVERNI],
              'ally_placements': [rc.TRIBE_CADURCI]}
    assert apply(state, 26, params)['executed']
    assert state['tribes'][rc.TRIBE_CADURCI]['allied_faction'] == rc.ARVERNI
    assert state['tribes'][rc.TRIBE_VOLCAE]['allied_faction'] == rc.BELGAE
    assert state['tribes'][rc.TRIBE_ARVERNI]['allied_faction'] is None
    assert validate_state(state) == []


@pytest.mark.parametrize('params', [
    {'ally_removals': [rc.TRIBE_BITURIGES]},
    {'ally_removals': [rc.TRIBE_CADURCI, rc.TRIBE_CADURCI]},
    {'ally_removals': [rc.TRIBE_CADURCI], 'ally_placements': [rc.TRIBE_VOLCAE]},
    {'ally_removals': 'Cadurci'}, {'ally_placements': [{'tribe': rc.TRIBE_CADURCI}]},
    {'ally_placements': [rc.TRIBE_SEQUANI]}, {'place_faction': rc.AEDUI},
])
def test_gobannitio_illegal_plan_rolls_back_prior_valid_removals(params):
    state = board(26)
    _ally_tribe(state, rc.TRIBE_CADURCI, rc.AEDUI)
    state['tribes'][rc.TRIBE_VOLCAE]['status'] = rc.DISPERSED
    before = encode(state)
    assert apply(state, 26, params)['rejected']
    assert encode(state) == before


def test_gobannitio_citadel_is_not_an_ally_target():
    state = board(26)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.CITADEL)
    state['tribes'][rc.TRIBE_ARVERNI]['allied_faction'] = rc.ARVERNI
    before = encode(state)
    assert apply(state, 26, {'ally_removals': [rc.TRIBE_ARVERNI]})['rejected']
    assert encode(state) == before


@pytest.mark.parametrize('card,params', [(2, {'legions_from_track': 2}),
    (18, {'target_region': rc.SUGAMBRI}), ('A18', {'target_region': rc.SUGAMBRI}),
    (23, {'target_city': rc.CITY_GERGOVIA}), (26, {'ally_removals': [], 'ally_placements': []})])
def test_foreign_executor_cannot_supply_named_owner_decisions(card, params):
    state = board(card, rc.BELGAE)
    before = encode(state)
    assert apply(state, card, params)['rejected']
    assert encode(state) == before


@pytest.mark.parametrize('card', [2, 18, 'A18', 23, 26])
def test_response_owner_forgery_and_malformed_sentinels_reject(card):
    state = board(card)
    req = request(state, card)
    actor = req['acting_faction']
    for response in (None, {'use_default': 1}, {'decline': False}, {'decline': True, 'acting_faction': actor}):
        assert validate_free_action_response(state, actor, req, response)
    assert validate_free_action_response(state, rc.BELGAE, req, {'decline': True})
    assert validate_free_action_response(state, actor, req, {'decline': True}) is None


def test_preview_and_response_validation_never_mutate_live_state_or_rng():
    state = board(26, rc.BELGAE)
    _ally_tribe(state, rc.TRIBE_CADURCI, rc.AEDUI)
    params = {'ally_removals': [rc.TRIBE_CADURCI], 'ally_placements': [rc.TRIBE_CADURCI]}
    before = encode(state)
    result = preview(state, 26, params)
    assert result['tribes'][rc.TRIBE_CADURCI]['allied_faction'] == rc.ARVERNI
    assert encode(state) == before
    validate_response(state, rc.ARVERNI, request(state, 26), params)
    assert encode(state) == before


def test_empty_germania_region_is_a_legal_human_target():
    state = board(18)
    german_region(state)
    assert rc.UBII in options(state, 18)['target_regions']
    assert apply(state, 18, {'target_region': rc.UBII})['executed']
    assert count_pieces(state, rc.SUGAMBRI, rc.GERMANS) == 4


def test_sacking_np_at_cap_chooses_new_raze_over_ineffective_repeat():
    state = board(23)
    for region in (rc.ARVERNI_REGION, rc.BITURIGES):
        place_piece(state, region, rc.ROMANS, rc.AUXILIA)
    state['tribes'][rc.TRIBE_ARVERNI]['status'] = rc.MARKER_RAZED
    state['resources'][rc.ROMANS] = rc.MAX_RESOURCES
    assert np_available(state, 23)
    for _ in range(5):
        assert default_params(state, 23) == {'target_city': rc.CITY_AVARICUM}


@pytest.mark.parametrize('target', [rc.BELGAE, rc.ARVERNI])
def test_foreign_owner_cannot_forge_reclamation_of_executor_or_own_pieces(target):
    state = board(26, rc.BELGAE)
    _ally_tribe(state, rc.TRIBE_VOLCAE, target)
    params = {'ally_removals': [], 'ally_placements': [],
              'stage_timing_actions': {'26.removals:0': [
                  {'kind': 'voluntary_removal', 'response': {'pieces': [
                      {'region': rc.ARVERNI_REGION, 'piece_type': rc.ALLY,
                       'tribe': rc.TRIBE_VOLCAE, 'count': 1}]}}]}}
    before = encode(state)
    error = validate_free_action_response(state, rc.ARVERNI, request(state, 26), params)
    assert error and 'Only the executing player' in error
    assert encode(state) == before


def test_foreign_executor_cannot_sneak_authored_effect_stages_into_owner_plan():
    state = board(26, rc.BELGAE)
    before = encode(state)
    result = apply(state, 26, {'stage_timing_actions': {'26.removals:0': [
        {'kind': 'spring_leader', 'response': {'defer': True}}]}})
    assert result['rejected'] and encode(state) == before


@pytest.mark.parametrize('stages', [[], {'unknown': []}, {'2.legions': {}},
                                   {'2.legions:0': []}, {'handler_complete': []}])
def test_owner_response_rejects_unconsumed_or_malformed_stage_timing(stages):
    state = board(2)
    response = {'legions_from_track': 2, 'stage_timing_actions': stages}
    assert validate_free_action_response(state, rc.ROMANS, request(state, 2), response)


def test_owner_response_rejects_unconsumed_top_level_timing_actions():
    state = board(2)
    response = {'legions_from_track': 2, 'timing_actions': []}
    assert validate_free_action_response(state, rc.ROMANS, request(state, 2), response)


@pytest.mark.parametrize('key', ['26.removals:1', '26.placements:1', '26.removals:-1', '26.removals:00'])
def test_gobannitio_timing_indices_must_name_an_entry_or_exact_tail(key):
    state = board(26)
    response = {'ally_removals': [], 'ally_placements': [], 'stage_timing_actions': {key: []}}
    assert validate_free_action_response(state, rc.ARVERNI, request(state, 26), response)


def test_original_executor_outer_handler_complete_window_stays_supported():
    state = board(26, rc.BELGAE)
    assert apply(state, 26, {'stage_timing_actions': {'handler_complete': []}})['executed']


def test_impossible_track_allocation_after_late_window_rejects_without_partial_placement():
    state = board(2)
    total = sum(state['legions_track'].values())
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEGION, total - 1, from_legions_track=True)
    before = encode(state)
    result = apply(state, 2, {'legions_from_track': 2, 'legions_from_fallen': 0,
                            'stage_timing_actions': {'2.fallen_legions': []}})
    assert result['rejected'] and encode(state) == before



def test_gobannitio_outer_executor_rally_grant_window_stays_supported():
    state = board(26, rc.BELGAE)
    result = apply(state, 26, {'stage_timing_actions': {'grant.card_26_arverni_rally': []}})
    assert result['executed']
    assert result['free_actions'][0]['declined_no_effect']


def test_gobannitio_owner_response_cannot_author_the_outer_rally_grant_stage():
    state = board(26, rc.BELGAE)
    response = {'ally_removals': [], 'ally_placements': [],
                'stage_timing_actions': {'grant.card_26_arverni_rally': []}}
    assert validate_free_action_response(state, rc.ARVERNI, request(state, 26), response)
