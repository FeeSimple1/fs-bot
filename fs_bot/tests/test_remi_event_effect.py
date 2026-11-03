"""BE-03: Remi's Gallic Ally owns Card 68's shaded choices and pieces."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (count_pieces, count_pieces_by_state,
                                 get_available, get_leader_in_region, place_piece)
from fs_bot.cards import remi_event_effect as remi
from fs_bot.cards.card_effects import _ally_tribe, execute_event
from fs_bot.commands.common import CommandError
from fs_bot.engine.execute import _execute_event
from fs_bot.engine.spring import UNLOCK_KEY
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state


def board(owner=rc.AEDUI, executor=None, scenario=rc.SCENARIO_GREAT_REVOLT):
    state = build_initial_state(scenario, seed=612)
    state['executing_faction'] = executor or owner or rc.ROMANS
    state['non_player_factions'] = set()
    state['event_params'] = {}
    if owner:
        _ally_tribe(state, rc.TRIBE_REMI, owner)
    return state


def citadel(state, city, faction):
    tribe = rc.CITY_TO_TRIBE[city]
    place_piece(state, rc.TRIBE_TO_REGION[tribe], faction, rc.CITADEL)
    state['tribes'][tribe]['allied_faction'] = faction


def apply(state, params):
    return _execute_event(state, state['executing_faction'], {
        'command': rc.FIRST_DID_EVENT, 'details': {'card_id': 68,
            'text_preference': rc.EVENT_SHADED, 'event_params': params}}, human=True)


def encoded(state):
    return encode({k: v for k, v in state.items() if k != 'decision_agent'})


@pytest.mark.parametrize('actor', rc.GALLIC_FACTIONS)
@pytest.mark.parametrize('city', [rc.CITY_ALESIA, rc.CITY_CENABUM])
def test_foreign_executor_asks_remi_owner_and_places_only_owners_pieces(actor, city):
    state = board(actor, rc.ROMANS)
    calls = []
    def choose(s, faction, request):
        calls.append((faction, request))
        return {'target_city': city}
    state['decision_agent'] = choose
    resources, eligibility = deepcopy(state['resources']), deepcopy(state['eligibility'])
    assert apply(state, {})['executed']
    assert len(calls) == 1 and calls[0][0] == actor
    assert calls[0][1]['request_type'] == 'remi_event_effect'
    tribe = rc.CITY_TO_TRIBE[city]
    region = rc.TRIBE_TO_REGION[tribe]
    assert state['tribes'][tribe]['allied_faction'] == actor
    assert count_pieces(state, region, actor, rc.CITADEL) == 1
    assert count_pieces_by_state(state, region, actor, rc.WARBAND, rc.HIDDEN) == 4
    assert count_pieces(state, region, rc.ROMANS) == 0
    assert state['resources'] == resources and state['eligibility'] == eligibility
    assert state['executing_faction'] == rc.ROMANS
    assert validate_state(state) == []


@pytest.mark.parametrize('kind', [rc.ALLY, rc.CITADEL])
@pytest.mark.parametrize('occupant', [rc.AEDUI, rc.ARVERNI])
def test_removes_city_structure_but_retains_all_region_mobile_pieces(kind, occupant):
    state = board()
    if kind == rc.CITADEL:
        citadel(state, rc.CITY_ALESIA, occupant)
    else:
        _ally_tribe(state, rc.TRIBE_MANDUBII, occupant)
    stock = get_available(state, occupant, kind)
    for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        place_piece(state, rc.MANDUBII, rc.ARVERNI, rc.WARBAND, 1, piece_state=visibility)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA, 2)
    assert apply(state, {'target_city': rc.CITY_ALESIA})['executed']
    expected = stock + 1 - int(occupant == rc.AEDUI and kind == rc.CITADEL)
    assert get_available(state, occupant, kind) == expected
    for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        assert count_pieces_by_state(state, rc.MANDUBII, rc.ARVERNI, rc.WARBAND, visibility) == 1
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS) == 3
    assert validate_state(state) == []


@pytest.mark.parametrize('status', [rc.MARKER_DISPERSED, rc.MARKER_DISPERSED_GATHERING, rc.MARKER_RAZED])
@pytest.mark.parametrize('marker_form', [dict, set])
def test_city_status_and_legacy_marker_forms_are_cleared(status, marker_form):
    state = board()
    state['tribes'][rc.TRIBE_MANDUBII]['status'] = status
    state['markers'][rc.TRIBE_MANDUBII] = ({status: True} if marker_form is dict else {status})
    state['markers'][rc.MANDUBII] = {rc.MARKER_DEVASTATED: True}
    assert apply(state, {'target_city': rc.CITY_ALESIA})['executed']
    assert state['tribes'][rc.TRIBE_MANDUBII]['status'] is None
    assert status not in state['markers'][rc.TRIBE_MANDUBII]
    assert state['markers'][rc.MANDUBII][rc.MARKER_DEVASTATED]
    assert validate_state(state) == []


def test_sacking_then_remi_clears_city_raze_from_both_records():
    state = board(executor=rc.ROMANS)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA, 2)
    state['event_params'] = {'target_city': rc.CITY_ALESIA}
    execute_event(state, 23)
    assert state['markers'][rc.MANDUBII][rc.MARKER_RAZED]
    state['executing_faction'] = rc.AEDUI
    remi.execute(state)
    assert rc.MARKER_RAZED not in state['markers'][rc.MANDUBII]
    assert state['tribes'][rc.TRIBE_MANDUBII]['status'] is None
    assert validate_state(state) == []


@pytest.mark.parametrize('available_warbands', [0, 1, 3, 4, 8])
def test_fixed_four_warbands_uses_available_shortfall_only(available_warbands):
    state = board()
    place_piece(state, rc.VENETI, rc.AEDUI, rc.WARBAND,
                get_available(state, rc.AEDUI, rc.WARBAND) - available_warbands)
    assert apply(state, {'target_city': rc.CITY_ALESIA})['executed']
    assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == min(4, available_warbands)
    assert validate_state(state) == []


def test_no_available_citadel_still_removes_enemy_and_places_owners_warbands():
    state = board()
    for city in (rc.CITY_BIBRACTE, rc.CITY_AVARICUM):
        citadel(state, city, rc.AEDUI)
    _ally_tribe(state, rc.TRIBE_MANDUBII, rc.BELGAE)
    assert get_available(state, rc.AEDUI, rc.CITADEL) == 0
    assert apply(state, {'target_city': rc.CITY_ALESIA})['executed']
    assert state['tribes'][rc.TRIBE_MANDUBII]['allied_faction'] is None
    assert count_pieces(state, rc.MANDUBII, rc.BELGAE, rc.ALLY) == 0
    assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.CITADEL) == 0
    assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == 4
    assert get_available(state, rc.BELGAE, rc.CITADEL) == 1
    assert validate_state(state) == []


def test_removed_own_citadel_can_supply_its_replacement():
    state = board(rc.BELGAE)
    citadel(state, rc.CITY_ALESIA, rc.BELGAE)
    assert get_available(state, rc.BELGAE, rc.CITADEL) == 0
    assert apply(state, {'target_city': rc.CITY_ALESIA})['executed']
    assert count_pieces(state, rc.MANDUBII, rc.BELGAE, rc.CITADEL) == 1
    assert count_pieces(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND) == 4
    assert validate_state(state) == []


@pytest.mark.parametrize('params', [
    {}, {'target_city': None}, {'target_city': []}, {'target_city': rc.CITY_GERGOVIA},
    {'target_city': rc.CITY_ALESIA, 'warbands': 1}, {'decline': False},
    {'decline': 1}, {'use_default': 1}, {'decline': True, 'target_city': rc.CITY_ALESIA},
    {'target_city': rc.CITY_ALESIA, 'timing_actions': []},
    {'target_city': rc.CITY_ALESIA, 'stage_timing_actions': []},
    {'target_city': rc.CITY_ALESIA, 'stage_timing_actions': {'handler_complete': []}},
    {'target_city': rc.CITY_ALESIA, 'stage_timing_actions': {'68.warbands:0': []}},
    {'target_city': rc.CITY_ALESIA, 'stage_timing_actions': {'68.citadel': {}}},
])
def test_owner_responses_require_exact_consumed_choices(params):
    state = board()
    before = encoded(state)
    with pytest.raises(ValueError):
        remi.validate_response(state, rc.AEDUI, remi.request(state), params)
    assert encoded(state) == before


@pytest.mark.parametrize('params', [{'decline': True}, {'use_default': True},
                                  {'target_city': rc.CITY_ALESIA}])
def test_owner_response_is_not_authorized_for_foreign_faction(params):
    state = board(executor=rc.ROMANS)
    with pytest.raises(ValueError, match='Only the Gallic Ally'):
        remi.validate_response(state, rc.ROMANS, remi.request(state), params)


@pytest.mark.parametrize('params', [{'target_city': rc.CITY_ALESIA}, {'decline': True},
    {'use_default': True}, {'stage_timing_actions': {'68.citadel': []}}])
def test_foreign_executor_cannot_supply_owner_selections_atomically(params):
    state = board(executor=rc.ROMANS)
    before = encoded(state)
    result = apply(state, params)
    assert result['rejected'] and not result['executed']
    assert encoded(state) == before


def test_decline_preserves_entire_board_and_default_uses_owner_policy():
    state = board(executor=rc.ROMANS)
    state['decision_agent'] = lambda *_: {'decline': True}
    before = encoded(state)
    assert apply(state, {})['executed']
    assert encoded(state) == before
    state['decision_agent'] = lambda *_: {'use_default': True}
    assert apply(state, {})['executed']
    assert sum(count_pieces(state, r, rc.AEDUI, rc.CITADEL)
               for r in (rc.MANDUBII, rc.CARNUTES)) == 1


@pytest.mark.parametrize('non_gallic_owner', [None, rc.ROMANS, rc.GERMANS])
def test_remi_without_gallic_ally_has_no_optional_effect(non_gallic_owner):
    state = board(non_gallic_owner)
    before = encoded(state)
    state['decision_agent'] = lambda *_: pytest.fail('No Gallic owner to consult')
    assert not remi.execute(state)['accepted']
    assert encoded(state) == before
    assert remi.default_params(state) == {'decline': True}
    assert not remi.np_available(state, rc.AEDUI)


def test_preview_shows_exact_boundaries_without_mutating_or_consulting_live_state():
    state = board()
    _ally_tribe(state, rc.TRIBE_MANDUBII, rc.BELGAE)
    state['decision_agent'] = lambda *_: pytest.fail('Preview consumed live input')
    before = encoded(state)
    params = {'target_city': rc.CITY_ALESIA}
    removed = remi.preview(state, params, stage='68.citadel')
    assert removed['tribes'][rc.TRIBE_MANDUBII]['allied_faction'] is None
    placed = remi.preview(state, params, stage='68.warbands')
    assert count_pieces(placed, rc.MANDUBII, rc.AEDUI, rc.CITADEL) == 1
    assert count_pieces(placed, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == 0
    final = remi.preview(state, params, complete=True)
    assert count_pieces(final, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == 4
    final['rng'].random()
    assert encoded(state) == before


def test_np_defaults_require_own_remi_and_belgae_net_structural_gain():
    state = board(rc.BELGAE)
    _ally_tribe(state, rc.TRIBE_MANDUBII, rc.BELGAE)
    assert remi.default_params(state) == {'target_city': rc.CITY_CENABUM}
    assert remi.np_available(state, rc.BELGAE)
    assert not remi.np_available(state, rc.AEDUI)
    assert remi.derive_params(state, rc.AEDUI) is None
    _ally_tribe(state, rc.TRIBE_CARNUTES, rc.BELGAE)
    assert remi.default_params(state) == {'decline': True}
    assert not remi.np_available(state, rc.BELGAE)


def test_np_prefers_enemy_citadel_and_uses_seeded_equal_target_selection():
    state = board()
    citadel(state, rc.CITY_ALESIA, rc.ARVERNI)
    _ally_tribe(state, rc.TRIBE_CARNUTES, rc.BELGAE)
    assert remi.default_params(state) == {'target_city': rc.CITY_ALESIA}
    state = board()
    clone = deepcopy(state)
    seen = set()
    for _ in range(24):
        result = remi.default_params(state)
        assert result == remi.default_params(clone)
        seen.add(result['target_city'])
    assert seen == {rc.CITY_ALESIA, rc.CITY_CENABUM}


def test_ariovistus_game_run_arverni_resolves_without_a_human_seat():
    state = board(rc.ARVERNI, rc.ROMANS, rc.SCENARIO_ARIOVISTUS)
    state['decision_agent'] = lambda *_: pytest.fail('Game-run Arverni is not a human seat')
    eligibility = deepcopy(state['eligibility'])
    assert apply(state, {})['executed']
    assert sum(count_pieces(state, r, rc.ARVERNI, rc.CITADEL)
               for r in (rc.MANDUBII, rc.CARNUTES)) == 1
    assert state['eligibility'] == eligibility
    assert validate_state(state) == []


def reclaim(region, kind=rc.WARBAND, count=1, **extra):
    operation = {'action': 'remove', 'region': region, 'piece_type': kind, 'count': count, **extra}
    if kind == rc.WARBAND:
        operation['piece_state'] = rc.HIDDEN
    return [{'kind': 'voluntary_removal', 'response': {'operations': [operation]}}]


def test_same_executor_owner_can_reclaim_between_steps_and_fixed_count_rereads_stock():
    state = board()
    place_piece(state, rc.VENETI, rc.AEDUI, rc.WARBAND, get_available(state, rc.AEDUI, rc.WARBAND))
    params = {'target_city': rc.CITY_ALESIA, 'stage_timing_actions': {
        '68.warbands': reclaim(rc.VENETI, count=3)}}
    assert apply(state, params)['executed']
    assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == 3
    assert validate_state(state) == []


def test_owner_cannot_author_voluntary_removal_during_foreign_executors_event():
    state = board(executor=rc.ROMANS)
    place_piece(state, rc.VENETI, rc.AEDUI, rc.WARBAND)
    params = {'target_city': rc.CITY_ALESIA, 'stage_timing_actions': {
        '68.warbands': reclaim(rc.VENETI)}}
    with pytest.raises(CommandError, match='Only the executing player'):
        remi.validate_response(state, rc.AEDUI, remi.request(state), params)


def test_remi_owner_is_fixed_before_owner_reclaims_remi_at_component_window():
    state = board()
    params = {'target_city': rc.CITY_ALESIA, 'stage_timing_actions': {
        '68.citadel': reclaim(rc.ATREBATES, rc.ALLY, tribe=rc.TRIBE_REMI)}}
    assert apply(state, params)['executed']
    assert state['tribes'][rc.TRIBE_REMI]['allied_faction'] is None
    assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.CITADEL) == 1
    assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == 4
    assert validate_state(state) == []


def test_arverni_owner_may_author_spring_entry_during_foreign_event():
    state = board(rc.ARVERNI, rc.ROMANS, rc.SCENARIO_PAX_GALLICA)
    state['available'][rc.ARVERNI][rc.LEADER] -= 1
    state['spring_box_leaders'] = [rc.VERCINGETORIX]
    state[UNLOCK_KEY] = True
    state['winter_count'] = 1
    params = {'target_city': rc.CITY_ALESIA, 'stage_timing_actions': {
        '68.warbands': [{'kind': 'spring_leader', 'response': {'region': rc.MANDUBII}}]}}
    remi.validate_response(state, rc.ARVERNI, remi.request(state), params)
    state['decision_agent'] = lambda *_: params
    assert apply(state, {})['executed']
    assert get_leader_in_region(state, rc.MANDUBII, rc.ARVERNI) == rc.VERCINGETORIX
    assert validate_state(state) == []


def test_outer_handler_complete_remains_executors_window_and_input_is_restored():
    state = board(executor=rc.ROMANS)
    state['decision_agent'] = lambda *_: {'target_city': rc.CITY_ALESIA}
    params = {'stage_timing_actions': {'handler_complete': []}}
    state['event_params'] = deepcopy(params)
    assert apply(state, params)['executed']
    assert state['event_params'] == params
    assert state['executing_faction'] == rc.ROMANS


def test_live_component_reclamation_stays_with_foreign_executor_and_never_remi_owner():
    state = board(executor=rc.ROMANS)
    place_piece(state, rc.VENETI, rc.ROMANS, rc.AUXILIA)
    windows = []
    class Agent:
        supports_action_windows = True
        def __call__(self, current, faction, request):
            if request.get('request_type') == 'remi_event_effect':
                return {'target_city': rc.CITY_ALESIA}
            if request['kind'] == 'voluntary_removal':
                windows.append((faction, request['window']['step']))
                if request['window']['step'] == '68.warbands' and count_pieces(
                        current, rc.VENETI, rc.ROMANS, rc.AUXILIA):
                    return {'operations': [{'action': 'remove', 'region': rc.VENETI,
                        'piece_type': rc.AUXILIA, 'piece_state': rc.HIDDEN, 'count': 1}]}
                return {'done': True}
            return None
    state['decision_agent'] = Agent()
    assert apply(state, {})['executed']
    assert windows and {faction for faction, _ in windows} == {rc.ROMANS}
    assert {step for _, step in windows} >= {'68.citadel', '68.warbands'}
    assert count_pieces(state, rc.VENETI, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == 4
    assert validate_state(state) == []


def test_np_no_effect_city_replacement_declines_when_no_placements_or_enemy_removal():
    state = board()
    for city in (rc.CITY_ALESIA, rc.CITY_CENABUM):
        citadel(state, city, rc.AEDUI)
    place_piece(state, rc.VENETI, rc.AEDUI, rc.WARBAND, get_available(state, rc.AEDUI, rc.WARBAND))
    assert not remi.np_available(state, rc.AEDUI)
    assert remi.default_params(state) == {'decline': True}
    # The broad printed human permission still permits this harmless choice.
    before = encoded(state)
    assert apply(state, {'target_city': rc.CITY_ALESIA})['executed']
    assert encoded(state) == before
