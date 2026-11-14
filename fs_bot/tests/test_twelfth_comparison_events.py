"""EV12-01 and EV12-02 through bot dispatch and Event execution."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.bots.bot_common import should_decline_event
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.cards.card_effects import _ally_tribe, _tribe_piece_type, _unally_tribe
from fs_bot.cli.dispatcher import _translate_bot_action
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT, get_first_eligible_options, get_sop_factions
from fs_bot.state.serialize import encode
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state
from fs_bot.tools.seat_session import board_copy


def check(state):
    assert validate_state(state) == check_structural_integrity(state) == []


def prepare(state, card, faction, other_bots=()):
    state.update(current_card=card, current_card_id=card, can_play_event=True,
                 non_player_factions={faction, *other_bots})
    return state


def bot_event(state, faction):
    check(state)
    before = encode(board_copy(state))
    assert not should_decline_event(state, state['current_card'], faction)
    assert encode(board_copy(state)) == before
    plan = dispatch_bot_turn(state, faction)
    assert plan['command'] == rc.FIRST_DID_EVENT, plan
    outcome = execute_decision(state, faction, {'action': ACTION_EVENT, 'bot_action': plan})
    assert outcome['executed'] and not outcome.get('errors'), outcome
    check(state)


def assert_command_fallback(state, faction):
    check(state)
    before = encode(board_copy(state))
    assert should_decline_event(state, state['current_card'], faction)
    assert encode(board_copy(state)) == before
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


def set_citadels(state, placements):
    for tribe in state['tribes']:
        if _tribe_piece_type(state, tribe) == rc.CITADEL:
            _unally_tribe(state, tribe)
    for tribe, faction in placements:
        _unally_tribe(state, tribe)
        assert _ally_tribe(state, tribe, faction, citadel=True)


@pytest.mark.parametrize('faction,scenario', [
    (rc.ROMANS, rc.SCENARIO_PAX_GALLICA),
    *((rc.AEDUI, scenario) for scenario in rc.BASE_SCENARIOS),
])
def test_sappers_targets_belgae_over_an_aedui_citadel(faction, scenario):
    state = prepare(setup_scenario(scenario, seed=1), 24, faction)
    set_citadels(state, [(rc.TRIBE_AEDUI, rc.AEDUI), (rc.TRIBE_MANDUBII, rc.BELGAE)])
    before = state['resources'].copy()
    bot_event(state, faction)
    assert state['resources'] == {**before, rc.BELGAE: max(0, before[rc.BELGAE] - 10)}


@pytest.mark.parametrize('scenario', rc.BASE_SCENARIOS)
def test_sappers_aedui_spares_non_player_arverni(scenario):
    state = prepare(setup_scenario(scenario, seed=1), 24, rc.AEDUI, (rc.ARVERNI,))
    set_citadels(state, [(rc.TRIBE_ARVERNI, rc.ARVERNI), (rc.TRIBE_MANDUBII, rc.BELGAE)])
    before = state['resources'].copy()
    bot_event(state, rc.AEDUI)
    assert state['resources'] == {**before, rc.BELGAE: max(0, before[rc.BELGAE] - 10)}


@pytest.mark.parametrize('faction,arverni_resources,target', [
    (rc.ROMANS, 3, rc.ARVERNI),
    (rc.ROMANS, 0, rc.BELGAE),
    (rc.AEDUI, 3, rc.ARVERNI),
])
def test_sappers_uses_first_effective_priority(faction, arverni_resources, target):
    state = prepare(setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=1), 24, faction)
    set_citadels(state, [(rc.TRIBE_ARVERNI, rc.ARVERNI), (rc.TRIBE_MANDUBII, rc.BELGAE)])
    state['resources'].update({rc.ARVERNI: arverni_resources, rc.BELGAE: 12})
    before = state['resources'].copy()
    bot_event(state, faction)
    assert state['resources'] == {**before, target: max(0, before[target] - 10)}


@pytest.mark.parametrize('faction,blocked', [
    (rc.ROMANS, 'no_citadel'), (rc.AEDUI, 'no_citadel'),
    (rc.ROMANS, 'aedui_citadel'), (rc.AEDUI, 'bot_citadel'),
    (rc.ROMANS, 'no_resources'),
])
def test_sappers_declines_when_no_allowed_citadel_can_lose_resources(faction, blocked):
    state = prepare(setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=1), 24, faction)
    placements = []
    if blocked == 'aedui_citadel':
        placements.append((rc.TRIBE_AEDUI, rc.AEDUI))
    elif blocked in ('bot_citadel', 'no_resources'):
        placements.append((rc.TRIBE_MANDUBII, rc.BELGAE))
        if blocked == 'bot_citadel':
            state['non_player_factions'].add(rc.BELGAE)
        else:
            state['resources'][rc.BELGAE] = 0
    set_citadels(state, placements)
    assert_command_fallback(state, faction)


def test_player_sappers_can_choose_aedui():
    state = prepare(setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=1), 24, rc.ROMANS)
    state['non_player_factions'].clear()
    set_citadels(state, [(rc.TRIBE_AEDUI, rc.AEDUI), (rc.TRIBE_MANDUBII, rc.BELGAE)])
    before = state['resources'].copy()
    result = execute_decision(state, rc.ROMANS, {'action': ACTION_EVENT, 'player_action': {
        'command': rc.FIRST_DID_EVENT, 'details': {
            'card_id': 24, 'text_preference': rc.EVENT_UNSHADED,
            'event_params': {'target_faction': rc.AEDUI},
        },
    }})
    assert result['executed'] and not result.get('errors'), result
    assert state['resources'] == {**before, rc.AEDUI: max(0, before[rc.AEDUI] - 10)}
    check(state)


def drought_board(scenario, faction, seed):
    state = prepare(build_initial_state(scenario, seed=seed), 49, faction, (rc.BELGAE,))
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    state['resources'].update({rc.ROMANS: 9, rc.AEDUI: 7, rc.BELGAE: 11})
    return state


@pytest.mark.parametrize('scenario', [rc.SCENARIO_PAX_GALLICA, *rc.ARIOVISTUS_SCENARIOS])
@pytest.mark.parametrize('faction', [rc.ROMANS, rc.AEDUI])
@pytest.mark.parametrize('seed', [1, 7])
def test_drought_marks_the_eligible_player_enemy_region(scenario, faction, seed):
    state = drought_board(scenario, faction, seed)
    enemy = rc.GERMANS if scenario in rc.ARIOVISTUS_SCENARIOS else rc.ARVERNI
    place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.CARNUTES, enemy, rc.WARBAND)
    before = state['resources'].copy()
    bot_event(state, faction)

    assert state['markers'][rc.CARNUTES][rc.MARKER_DEVASTATED]
    assert rc.MARKER_DEVASTATED not in state['markers'].get(rc.MORINI, {})
    assert count_pieces(state, rc.CARNUTES, enemy, rc.WARBAND) == 0
    assert count_pieces(state, rc.MORINI, rc.BELGAE, rc.WARBAND) == 1
    assert count_pieces(state, rc.MORINI, rc.ROMANS, rc.AUXILIA) == 1
    assert state['resources'] == {owner: amount // 2 for owner, amount in before.items()}


@pytest.mark.parametrize('faction', [rc.ROMANS, rc.AEDUI])
def test_drought_skips_a_region_with_an_unpermitted_casualty(faction):
    state = drought_board(rc.SCENARIO_PAX_GALLICA, faction, 1)
    assert _ally_tribe(state, rc.TRIBE_MANDUBII, rc.ARVERNI, citadel=True)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND)
    bot_event(state, faction)
    assert state['markers'][rc.CARNUTES][rc.MARKER_DEVASTATED]
    assert count_pieces(state, rc.MANDUBII, rc.ARVERNI, rc.CITADEL) == 1
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 1


def test_drought_prioritizes_a_guaranteed_citadel_over_warbands():
    state = drought_board(rc.SCENARIO_PAX_GALLICA, rc.ROMANS, 1)
    state['non_player_factions'].remove(rc.BELGAE)
    place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND)
    place_piece(state, rc.MORINI, rc.ARVERNI, rc.WARBAND)
    assert _ally_tribe(state, rc.TRIBE_MANDUBII, rc.ARVERNI, citadel=True)
    bot_event(state, rc.ROMANS)
    assert state['markers'][rc.MANDUBII][rc.MARKER_DEVASTATED]
    assert count_pieces(state, rc.MANDUBII, rc.ARVERNI, rc.CITADEL) == 0
    assert count_pieces(state, rc.MORINI, rc.BELGAE, rc.WARBAND) == 1


def test_drought_roman_selector_allows_the_permanent_fort_without_a_casualty():
    state = drought_board(rc.SCENARIO_PAX_GALLICA, rc.ROMANS, 1)
    place_piece(state, rc.PROVINCIA, rc.ARVERNI, rc.WARBAND)
    bot_event(state, rc.ROMANS)
    assert state['markers'][rc.PROVINCIA][rc.MARKER_DEVASTATED]
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.FORT) == 1
    assert count_pieces(state, rc.PROVINCIA, rc.ARVERNI, rc.WARBAND) == 0


def test_drought_marker_ranking_allows_the_owner_to_spare_a_citadel():
    state = drought_board(rc.SCENARIO_PAX_GALLICA, rc.AEDUI, 1)
    state['non_player_factions'].remove(rc.BELGAE)
    place_piece(state, rc.MANDUBII, rc.ARVERNI, rc.WARBAND)
    assert _ally_tribe(state, rc.TRIBE_MANDUBII, rc.ARVERNI, citadel=True)
    place_piece(state, rc.MORINI, rc.ARVERNI, rc.WARBAND)
    place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND)
    bot_event(state, rc.AEDUI)
    assert state['markers'][rc.MORINI][rc.MARKER_DEVASTATED]
    assert count_pieces(state, rc.MANDUBII, rc.ARVERNI, rc.CITADEL) == 1


def test_drought_bot_keeps_the_human_owners_exact_choice():
    state = drought_board(rc.SCENARIO_ARIOVISTUS, rc.AEDUI, 1)
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND)
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.SETTLEMENT)
    seen = []

    def choose(_board, actor, request):
        if request['kind'] == 'drought_loss':
            seen.append((actor, request['region']))
            return {'piece': {'piece_type': rc.SETTLEMENT}}

    state['decision_agent'] = choose
    bot_event(state, rc.AEDUI)
    assert seen == [(rc.GERMANS, rc.CARNUTES)]
    assert count_pieces(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND) == 1
    assert count_pieces(state, rc.CARNUTES, rc.GERMANS, rc.SETTLEMENT) == 0


def test_drought_ties_are_seeded_and_independent_of_space_insertion_order():
    selected = set()
    for seed in range(1, 9):
        state = drought_board(rc.SCENARIO_PAX_GALLICA, rc.ROMANS, seed)
        for region in (rc.CARNUTES, rc.AEDUI_REGION):
            place_piece(state, region, rc.ARVERNI, rc.WARBAND)
        reordered = deepcopy(state)
        reordered['spaces'] = dict(reversed(list(reordered['spaces'].items())))
        bot_event(state, rc.ROMANS)
        bot_event(reordered, rc.ROMANS)
        assert encode(state) == encode(reordered)
        dest, = [r for r, markers in state['markers'].items() if rc.MARKER_DEVASTATED in markers]
        selected.add(dest)
    assert selected == {rc.CARNUTES, rc.AEDUI_REGION}


@pytest.mark.parametrize('faction', [rc.ROMANS, rc.AEDUI])
@pytest.mark.parametrize('with_existing_marker', [False, True])
def test_drought_without_a_new_eligible_region_resolves_remaining_effects(faction, with_existing_marker):
    state = drought_board(rc.SCENARIO_PAX_GALLICA, faction, 1)
    state['non_player_factions'] = set(get_sop_factions(state))
    place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    if with_existing_marker:
        state['markers'][rc.CARNUTES] = {rc.MARKER_DEVASTATED: True}
        state['resources'] = dict.fromkeys(state['resources'], 0)
    before_markers = deepcopy(state['markers'])
    before_resources = state['resources'].copy()
    bot_event(state, faction)
    assert state['markers'] == before_markers
    assert state['resources'] == {owner: amount // 2 for owner, amount in before_resources.items()}
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == (not with_existing_marker)
    assert count_pieces(state, rc.MORINI, rc.BELGAE, rc.WARBAND) == 1


@pytest.mark.parametrize('faction', [rc.ROMANS, rc.AEDUI])
def test_drought_declines_without_a_marker_resource_or_casualty_effect(faction):
    state = prepare(setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=1), 49, faction)
    state['non_player_factions'] = set(get_sop_factions(state))
    state['resources'] = dict.fromkeys(state['resources'], 0)
    assert_command_fallback(state, faction)
