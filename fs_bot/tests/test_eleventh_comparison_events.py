"""Exercise the eleventh audit's Event fixes through bot dispatch and execution."""

from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (
    count_pieces, find_leader, get_available, get_leader_in_region, place_piece, remove_piece,
)
from fs_bot.bots.bot_common import should_decline_event
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.cards.capabilities import get_active_capabilities
from fs_bot.cards.card_effects import _ally_tribe, _unally_tribe
from fs_bot.cli.dispatcher import _translate_bot_action
from fs_bot.cli.human_plan import _collect_event_params
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT, get_first_eligible_options, get_sop_factions
from fs_bot.map.map_data import get_playable_regions_for_state
from fs_bot.state.serialize import encode
from fs_bot.state.setup import _set_tribe_dispersed, _set_tribe_dispersed_gathering, setup_scenario
from fs_bot.state.state_schema import check_structural_integrity, validate_state


def check(state):
    assert validate_state(state) == check_structural_integrity(state) == []


def position(scenario, card, bots=None, *, seed=1):
    state = setup_scenario(scenario, seed=seed)
    state.update(current_card=card, current_card_id=card, can_play_event=True,
                 non_player_factions=set(get_sop_factions(state) if bots is None else bots))
    return state


def bot_event(state, faction, *, shaded=False):
    check(state)
    before = encode(state)
    assert not should_decline_event(state, state['current_card'], faction)
    assert encode(state) == before
    plan = dispatch_bot_turn(state, faction)
    assert plan['command'] == rc.FIRST_DID_EVENT, plan
    result = execute_decision(state, faction, {'action': ACTION_EVENT, 'bot_action': plan})
    assert result['executed'] and result['shaded'] is shaded and not result.get('errors'), result
    check(state)
    return result


def assert_declines(state, faction):
    check(state)
    before = encode(state)
    assert should_decline_event(state, state['current_card'], faction)
    assert encode(state) == before
    control = deepcopy(state)
    control['can_play_event'] = False
    plan = dispatch_bot_turn(state, faction)
    assert plan['command'] != rc.FIRST_DID_EVENT
    assert plan == dispatch_bot_turn(control, faction)
    result = execute_decision(state, faction, {
        'action': _translate_bot_action(plan, get_first_eligible_options()), 'bot_action': plan,
    })
    assert result['executed'] and not result.get('errors'), result
    check(state)


def player_event(state, faction, card, params=None, *, shaded=False):
    state.update(current_card=card, current_card_id=card)
    check(state)
    result = execute_decision(state, faction, {'action': ACTION_EVENT, 'player_action': {
        'command': rc.FIRST_DID_EVENT, 'details': {
            'card_id': card, 'text_preference': rc.EVENT_SHADED if shaded else rc.EVENT_UNSHADED,
            'event_params': params if params is not None else {},
        },
    }})
    assert result['executed'] and not result.get('errors'), result
    check(state)
    return result


def make_successor(state, on_map=True):
    origin = find_leader(state, rc.ARVERNI)
    remove_piece(state, origin, rc.ARVERNI, rc.LEADER)
    if on_map:
        place_piece(state, origin, rc.ARVERNI, rc.LEADER, leader_name=rc.SUCCESSOR)
    return origin


@pytest.mark.parametrize('scenario', [rc.SCENARIO_RECONQUEST, rc.SCENARIO_GREAT_REVOLT])
@pytest.mark.parametrize('on_map', [True, False])
def test_lucterius_restores_bot_leader_among_the_most_arverni_pieces(scenario, on_map):
    state = position(scenario, 19)
    make_successor(state, on_map)
    regions = get_playable_regions_for_state(state, rc.ARVERNI)
    most = max(count_pieces(state, r, rc.ARVERNI) for r in regions)
    choices = {r for r in regions if count_pieces(state, r, rc.ARVERNI) == most}

    bot_event(state, rc.ARVERNI, shaded=True)

    destination = find_leader(state, rc.ARVERNI)
    assert destination in choices
    assert get_leader_in_region(state, destination, rc.ARVERNI) == rc.VERCINGETORIX
    assert get_available(state, rc.ARVERNI, rc.LEADER) == 0


@pytest.mark.parametrize('scenario', rc.BASE_SCENARIOS)
def test_lucterius_declines_when_vercingetorix_is_on_map_or_in_spring_box(scenario):
    assert_declines(position(scenario, 19), rc.ARVERNI)


def test_lucterius_player_can_restore_the_successor_in_the_same_region():
    state = position(rc.SCENARIO_RECONQUEST, 19, bots=())
    origin = make_successor(state)
    player_event(state, rc.ARVERNI, 19, {'target_region': origin}, shaded=True)
    assert get_leader_in_region(state, origin, rc.ARVERNI) == rc.VERCINGETORIX
    assert get_available(state, rc.ARVERNI, rc.LEADER) == 0


def test_lucterius_terminal_leaves_the_destination_to_the_arverni():
    state = position(rc.SCENARIO_RECONQUEST, 19, bots=())
    make_successor(state)
    params = _collect_event_params(state, rc.BELGAE, 19, True, StringIO(), StringIO())
    assert params == {}

    requests = []

    def choose(board, faction, request):
        if request['kind'] == 'spring_leader':
            requests.append((faction, request))
            return {'region': rc.BITURIGES}

    state['decision_agent'] = choose
    player_event(state, rc.BELGAE, 19, params, shaded=True)
    assert [(f, req['leader']) for f, req in requests] == [(rc.ARVERNI, rc.VERCINGETORIX)]
    assert get_leader_in_region(state, rc.BITURIGES, rc.ARVERNI) == rc.VERCINGETORIX


@pytest.mark.parametrize('scenario,faction,targets', [
    (rc.SCENARIO_PAX_GALLICA, rc.ROMANS, (rc.ARVERNI, rc.BELGAE)),
    (rc.SCENARIO_PAX_GALLICA, rc.AEDUI, (rc.ARVERNI, rc.BELGAE)),
    (rc.SCENARIO_GREAT_REVOLT, rc.AEDUI, (rc.ARVERNI, rc.BELGAE)),
    (rc.SCENARIO_ARIOVISTUS, rc.ROMANS, (rc.BELGAE,)),
    (rc.SCENARIO_ARIOVISTUS, rc.AEDUI, (rc.BELGAE,)),
    (rc.SCENARIO_GALLIC_WAR, rc.AEDUI, (rc.BELGAE,)),
])
def test_assembly_bot_drains_the_instructed_gallic_factions(scenario, faction, targets):
    state = position(scenario, 52, bots={faction})
    _unally_tribe(state, rc.TRIBE_CARNUTES)
    state['resources'][rc.BELGAE] = 3
    before = state['resources'].copy()
    bot_event(state, faction)
    assert state['resources'] == {
        f: max(0, amount - 8) if f in targets else amount for f, amount in before.items()
    }


@pytest.mark.parametrize('disperse', [_set_tribe_dispersed, _set_tribe_dispersed_gathering])
def test_assembly_both_dispersed_sides_allow_the_drain(disperse):
    state = position(rc.SCENARIO_PAX_GALLICA, 52, bots={rc.ROMANS})
    _unally_tribe(state, rc.TRIBE_CARNUTES)
    disperse(state, rc.TRIBE_CARNUTES)
    before = state['resources'][rc.BELGAE]
    bot_event(state, rc.ROMANS)
    assert state['resources'][rc.BELGAE] == max(0, before - 8) < before


def test_assembly_roman_ally_allows_a_drain_of_non_player_belgae():
    state = position(rc.SCENARIO_PAX_GALLICA, 52)
    _unally_tribe(state, rc.TRIBE_CARNUTES)
    assert _ally_tribe(state, rc.TRIBE_CARNUTES, rc.ROMANS)
    before = state['resources'][rc.BELGAE]
    bot_event(state, rc.ROMANS)
    assert state['resources'][rc.BELGAE] == max(0, before - 8) < before


def test_assembly_aedui_spares_bot_arverni_and_drains_player_belgae():
    state = position(rc.SCENARIO_PAX_GALLICA, 52, bots={rc.AEDUI, rc.ARVERNI})
    _unally_tribe(state, rc.TRIBE_CARNUTES)
    before = state['resources'].copy()
    bot_event(state, rc.AEDUI)
    assert state['resources'] == {**before, rc.BELGAE: max(0, before[rc.BELGAE] - 8)}


@pytest.mark.parametrize('scenario,faction,blocked', [
    (rc.SCENARIO_PAX_GALLICA, rc.ROMANS, 'allied_carnutes'),
    (rc.SCENARIO_PAX_GALLICA, rc.ROMANS, 'no_resources'),
    (rc.SCENARIO_PAX_GALLICA, rc.AEDUI, 'no_player'),
    (rc.SCENARIO_ARIOVISTUS, rc.AEDUI, 'only_german_player'),
])
def test_assembly_bots_decline_without_a_legal_effect(scenario, faction, blocked):
    state = position(scenario, 52, bots={faction})
    _unally_tribe(state, rc.TRIBE_CARNUTES)
    if blocked == 'allied_carnutes':
        assert _ally_tribe(state, rc.TRIBE_CARNUTES, rc.ARVERNI)
    elif blocked == 'no_resources':
        state['resources'].update({rc.ARVERNI: 0, rc.BELGAE: 0})
    elif blocked == 'no_player':
        state['non_player_factions'].update((rc.ARVERNI, rc.BELGAE))
    else:
        state['non_player_factions'].update((rc.ROMANS, rc.BELGAE))
        assert state['resources'][rc.GERMANS] > 0
    assert_declines(state, faction)


def test_assembly_player_still_selects_the_exact_gallic_faction():
    state = position(rc.SCENARIO_PAX_GALLICA, 52, bots=())
    _unally_tribe(state, rc.TRIBE_CARNUTES)
    before = state['resources'].copy()
    player_event(state, rc.ROMANS, 52, {'target_factions': [rc.AEDUI, rc.AEDUI]})
    assert state['resources'] == {**before, rc.AEDUI: max(0, before[rc.AEDUI] - 8)}


@pytest.mark.parametrize('scenario', [rc.SCENARIO_PAX_GALLICA, *rc.ARIOVISTUS_SCENARIOS])
@pytest.mark.parametrize('acquisition_order', [(12, 55), (55, 12)])
def test_loyalties_roman_priority_ignores_capability_acquisition_order(scenario, acquisition_order):
    state = position(scenario, 50, bots={rc.ROMANS})
    for card in acquisition_order:
        player_event(state, rc.ROMANS if card == 12 else rc.BELGAE, card, shaded=card == 55)
    state.update(current_card=50, current_card_id=50)
    bot_event(state, rc.ROMANS)
    assert get_active_capabilities(state) == {12: rc.EVENT_UNSHADED}


@pytest.mark.parametrize('belgae_bot,removed', [(False, 59), (True, 12)])
def test_loyalties_uses_recorded_horse_holder_and_roman_fallback(belgae_bot, removed):
    bots = {rc.ROMANS, rc.BELGAE} if belgae_bot else {rc.ROMANS}
    state = position(rc.SCENARIO_PAX_GALLICA, 50, bots=bots)
    player_event(state, rc.ROMANS, 12, shaded=True)
    player_event(state, rc.BELGAE, 59, shaded=True)
    state.update(current_card=50, current_card_id=50)
    bot_event(state, rc.ROMANS)
    assert set(get_active_capabilities(state)) == {12, 59} - {removed}
    assert state['capability_owners'].get(59) == (rc.BELGAE if belgae_bot else None)


@pytest.mark.parametrize('scenario,faction,first,preferred,shaded', [
    (rc.SCENARIO_PAX_GALLICA, rc.AEDUI, (39, True, rc.AEDUI), (55, True, rc.BELGAE), False),
    (rc.SCENARIO_PAX_GALLICA, rc.AEDUI, (12, True, rc.ROMANS), (39, True, rc.AEDUI), False),
    (rc.SCENARIO_PAX_GALLICA, rc.BELGAE, (8, False, rc.BELGAE), (12, False, rc.ROMANS), True),
    (rc.SCENARIO_GREAT_REVOLT, rc.ARVERNI, (30, False, rc.ROMANS), (12, False, rc.ROMANS), True),
    (rc.SCENARIO_ARIOVISTUS, rc.GERMANS, ('A31', False, rc.ROMANS), (12, False, rc.ROMANS), True),
    (rc.SCENARIO_ARIOVISTUS, rc.ROMANS, (12, True, rc.ROMANS), ('A31', True, rc.GERMANS), False),
])
def test_loyalties_uses_each_factions_printed_priority(scenario, faction, first, preferred, shaded):
    state = position(scenario, 50, bots={faction})
    for card, side, owner in (first, preferred):
        player_event(state, owner, card, shaded=side)
    state.update(current_card=50, current_card_id=50)
    bot_event(state, faction, shaded=shaded)
    assert set(get_active_capabilities(state)) == {first[0]}


def test_loyalties_roman_declines_without_a_matching_capability_and_player_can_remove_it():
    state = position(rc.SCENARIO_PAX_GALLICA, 50, bots={rc.ROMANS})
    player_event(state, rc.ROMANS, 12)
    state.update(current_card=50, current_card_id=50)
    human = deepcopy(state)
    human['non_player_factions'].clear()
    assert_declines(state, rc.ROMANS)
    assert get_active_capabilities(state) == {12: rc.EVENT_UNSHADED}
    player_event(human, rc.ROMANS, 50, {'target_capability': 12})
    assert not get_active_capabilities(human)


def test_loyalties_ties_use_game_rng_with_a_stable_candidate_order():
    outcomes = set()
    for seed in (1, 3, 4, 5):
        remaining = []
        for cards in ((55, 27), (27, 55)):
            state = position(rc.SCENARIO_PAX_GALLICA, 50, bots={rc.ROMANS}, seed=seed)
            for card in cards:
                player_event(state, rc.BELGAE if card == 55 else rc.ARVERNI, card, shaded=True)
            state.update(current_card=50, current_card_id=50)
            bot_event(state, rc.ROMANS)
            remaining.append(tuple(get_active_capabilities(state)))
        assert remaining[0] == remaining[1]
        outcomes.update(remaining[0])
    assert outcomes == {27, 55}


def test_loyalties_removes_a_legacy_vergobret_capability_and_its_modifier():
    state = position(rc.SCENARIO_ARIOVISTUS, 50, bots={rc.GERMANS})
    state.setdefault('event_modifiers', {})['card_A38_suborn_enhanced'] = True
    player_event(state, rc.BELGAE, 55, shaded=True)
    state.update(current_card=50, current_card_id=50)
    bot_event(state, rc.GERMANS, shaded=True)
    assert get_active_capabilities(state) == {55: rc.EVENT_SHADED}
    assert 'card_A38_suborn_enhanced' not in state['event_modifiers']
