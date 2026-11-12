"""BE7-01 through BE7-03 through non-player selection and Event execution."""

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import get_controlled_regions, is_controlled_by
from fs_bot.board.pieces import count_pieces, get_available, move_piece, place_piece
from fs_bot.bots.bot_common import should_decline_event
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cards.event_eval import is_event_effective
from fs_bot.engine.execute import _derive_event_params, execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT, get_sop_factions
from fs_bot.state.serialize import encode
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state
from fs_bot.tools.seat_session import board_copy


def ready(state, card):
    state.update(current_card=card, current_card_id=card, can_play_event=True,
                 non_player_factions=set(get_sop_factions(state)))
    return state


def position(card, seed=1):
    scenario = rc.SCENARIO_ARIOVISTUS if isinstance(card, str) else rc.SCENARIO_GREAT_REVOLT
    state = build_initial_state(scenario, seed=seed)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    for faction in get_sop_factions(state):
        state['resources'][faction] = 10
    return ready(state, card)


def event(state, faction, *, shaded, params=None):
    action = {'command': 'Event', 'details': {
        'card_id': state['current_card'],
        'text_preference': rc.EVENT_SHADED if shaded else rc.EVENT_UNSHADED}}
    if params is not None:
        action['details']['event_params'] = params
        state['non_player_factions'].discard(faction)
    actor = 'bot_action' if params is None else 'player_action'
    return execute(state, faction, actor, action)


def execute(state, faction, actor, action):
    check(state)
    result = execute_decision(state, faction, {'action': ACTION_EVENT, actor: action})
    assert result['executed'] and not result.get('errors'), result
    check(state)
    return result


def bot_event(state, faction):
    action = dispatch_bot_turn(state, faction)
    assert action['command'] == 'Event', action
    return execute(state, faction, 'bot_action', action)


def check(state):
    assert validate_state(state) == []
    assert check_structural_integrity(state) == []


def unexpected_input(*args):
    pytest.fail('Event availability and planning must not consult a live agent')


def test_oppida_bot_upgrades_ally_placed_in_the_first_step():
    state = position(28)
    for tribe in rc.CITY_TO_TRIBE.values():
        if tribe != rc.TRIBE_BITURIGES:
            assert _ally_tribe(state, tribe, rc.ARVERNI if tribe == rc.TRIBE_ARVERNI else rc.AEDUI)
    available = get_available(state, rc.BELGAE, rc.ALLY)

    bot_event(state, rc.BELGAE)

    assert count_pieces(state, rc.BITURIGES, rc.BELGAE, rc.CITADEL) == 1
    assert count_pieces(state, rc.BITURIGES, rc.BELGAE, rc.ALLY) == 0
    assert get_available(state, rc.BELGAE, rc.ALLY) == available


def test_oppida_upgrade_ties_use_rng_on_the_detached_placement_board():
    upgrades = set()
    for seed in range(8):
        state = position(28, seed=seed)
        state['decision_agent'] = unexpected_input
        before = encode(board_copy(state))
        rng_before = state['rng'].getstate()
        assert not should_decline_event(state, 28, rc.BELGAE)
        assert encode(board_copy(state)) == before

        plan = _derive_event_params(state, rc.BELGAE, 28, True)

        assert len(plan['citadel_upgrades']) == 1
        assert rc.CITY_TO_TRIBE[plan['citadel_upgrades'][0]] in {
            entry['tribe'] for entry in plan['ally_placements']}
        assert all(entry['faction'] == rc.BELGAE for entry in plan['ally_placements'])
        assert state['rng'].getstate() != rng_before
        assert {k: v for k, v in encode(board_copy(state)).items() if k != 'rng'} == {
            k: v for k, v in before.items() if k != 'rng'}
        upgrades.update(plan['citadel_upgrades'])
    assert len(upgrades) > 1


def test_oppida_bot_declines_when_only_other_factions_can_benefit():
    state = position(28)
    for region in (rc.CARNUTES, rc.MANDUBII, rc.BITURIGES, rc.SEQUANI):
        place_piece(state, region, rc.ROMANS, rc.AUXILIA)
    assert should_decline_event(state, 28, rc.BELGAE)
    check(state)


def test_procillus_roman_bot_replaces_ally_next_to_named_caesar():
    state = position('A19')
    place_piece(state, rc.AEDUI_REGION, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    assert _ally_tribe(state, rc.TRIBE_BITURIGES, rc.BELGAE)

    bot_event(state, rc.ROMANS)

    assert state['tribes'][rc.TRIBE_BITURIGES]['allied_faction'] == rc.ROMANS


@pytest.mark.parametrize('stock', [0, 1, 6])
def test_procillus_prioritizes_city_and_remi_discs_and_uses_up_to_three_targets(stock):
    state = position('A19')
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    for tribe, faction in ((rc.TRIBE_SEQUANI, rc.GERMANS), (rc.TRIBE_BITURIGES, rc.BELGAE),
                           (rc.TRIBE_REMI, rc.AEDUI), (rc.TRIBE_TREVERI, rc.GERMANS)):
        assert _ally_tribe(state, tribe, faction)
    reserves = (rc.TRIBE_MORINI, rc.TRIBE_NERVII, rc.TRIBE_EBURONES, rc.TRIBE_ATREBATES,
                rc.TRIBE_VENETI, rc.TRIBE_PICTONES)
    for tribe in reserves[:6 - stock]:
        assert _ally_tribe(state, tribe, rc.ROMANS)

    event(state, rc.ROMANS, shaded=False)

    for index, tribe in enumerate((rc.TRIBE_SEQUANI, rc.TRIBE_BITURIGES, rc.TRIBE_REMI)):
        assert state['tribes'][tribe]['allied_faction'] == (rc.ROMANS if index < stock else None)
    assert state['tribes'][rc.TRIBE_TREVERI]['allied_faction'] == rc.GERMANS


@pytest.mark.parametrize('human', [False, True])
def test_procillus_removes_ally_without_violating_bibracte_stacking(human):
    state = position('A19')
    place_piece(state, rc.AEDUI_REGION, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    assert _ally_tribe(state, rc.TRIBE_AEDUI, rc.AEDUI)
    params = {'replacements': [{'tribe': rc.TRIBE_AEDUI}]} if human else None

    event(state, rc.ROMANS, shaded=False, params=params)

    assert state['tribes'][rc.TRIBE_AEDUI]['allied_faction'] is None
    assert count_pieces(state, rc.AEDUI_REGION, rc.ROMANS, rc.ALLY) == 0


@pytest.mark.parametrize('leader', [None, rc.SUCCESSOR, rc.CAESAR])
def test_procillus_declines_without_a_replaceable_enemy_disc(leader):
    state = position('A19')
    if leader is not None:
        place_piece(state, rc.AEDUI_REGION, rc.ROMANS, rc.LEADER, leader_name=leader)
    assert _ally_tribe(state, rc.TRIBE_NERVII, rc.BELGAE)
    assert _ally_tribe(state, rc.TRIBE_BITURIGES, rc.BELGAE, citadel=True)
    assert _ally_tribe(state, rc.TRIBE_SEQUANI, rc.ROMANS)
    state['decision_agent'] = unexpected_input
    before = encode(board_copy(state))

    assert should_decline_event(state, 'A19', rc.ROMANS)
    assert encode(board_copy(state)) == before
    check(state)


@pytest.mark.parametrize('faction', [rc.BELGAE, rc.GERMANS])
def test_divico_bot_places_twelve_from_real_ariovistus_setup(faction):
    state = ready(setup_scenario(rc.SCENARIO_ARIOVISTUS, seed=1), 'A26')
    stock = get_available(state, rc.ARVERNI, rc.WARBAND)
    control = get_controlled_regions(state, rc.GERMANS)

    bot_event(state, faction)

    assert get_available(state, rc.ARVERNI, rc.WARBAND) == stock - 12
    if faction == rc.GERMANS:
        assert all(is_controlled_by(state, region, rc.GERMANS) for region in control)


def german_control(state, region, capacity):
    place_piece(state, region, rc.ROMANS, rc.AUXILIA)
    place_piece(state, region, rc.BELGAE, rc.WARBAND)
    place_piece(state, region, rc.GERMANS, rc.WARBAND, capacity + 3)


@pytest.mark.parametrize('capacities,stock,placed', [((7, 6), 35, (7, 5)), ((3, 4), 5, (1, 4))])
def test_divico_germans_split_the_maximum_without_losing_control(capacities, stock, placed):
    state = position('A26')
    regions = (rc.AEDUI_REGION, rc.SEQUANI)
    for region, capacity in zip(regions, capacities):
        german_control(state, region, capacity)
    if stock < 35:
        place_piece(state, rc.VENETI, rc.ARVERNI, rc.WARBAND, 35 - stock)

    event(state, rc.GERMANS, shaded=True)

    assert tuple(count_pieces(state, r, rc.ARVERNI, rc.WARBAND) for r in regions) == placed
    assert all(is_controlled_by(state, region, rc.GERMANS) for region in regions)


@pytest.mark.parametrize('faction', [rc.BELGAE, rc.GERMANS])
def test_divico_bots_decline_when_no_effective_placement_exists(faction):
    state = position('A26')
    if faction == rc.GERMANS:
        for region in (rc.AEDUI_REGION, rc.SEQUANI):
            german_control(state, region, 0)
    else:
        place_piece(state, rc.VENETI, rc.ARVERNI, rc.WARBAND,
                    get_available(state, rc.ARVERNI, rc.WARBAND))
    state['decision_agent'] = unexpected_input
    before = encode(board_copy(state))

    assert should_decline_event(state, 'A26', faction)
    assert encode(board_copy(state)) == before
    assert dispatch_bot_turn(state, faction)['command'] != 'Event'
    check(state)


@pytest.mark.parametrize('number', [0, 1])
def test_human_divico_can_choose_zero_or_lose_own_control(number):
    state = position('A26')
    german_control(state, rc.AEDUI_REGION, 0)
    placements = [{'region': rc.AEDUI_REGION, 'count': number}] if number else []

    event(state, rc.GERMANS, shaded=True, params={'placements': placements})

    assert count_pieces(state, rc.AEDUI_REGION, rc.ARVERNI, rc.WARBAND) == number
    assert is_controlled_by(state, rc.AEDUI_REGION, rc.GERMANS) == (number == 0)


@pytest.mark.parametrize('card,faction', [(18, rc.BELGAE), ('A18', rc.BELGAE), ('A18', rc.GERMANS)])
def test_rhenus_bots_decline_with_a_distant_legion(card, faction):
    state = position(card) if card == 18 else ready(setup_scenario(rc.SCENARIO_ARIOVISTUS, seed=1), card)
    if card == 18:
        place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION, from_legions_track=True)
    state['decision_agent'] = unexpected_input
    before = encode(board_copy(state))

    assert should_decline_event(state, card, faction)
    assert encode(board_copy(state)) == before
    assert dispatch_bot_turn(state, faction)['command'] != 'Event'
    check(state)


@pytest.mark.parametrize('card,faction,region,resources', [
    (18, rc.BELGAE, rc.UBII, 0), ('A18', rc.GERMANS, rc.TREVERI, 10),
])
def test_rhenus_legion_in_or_adjacent_to_germania_enables_both_effects(card, faction, region, resources):
    state = position(card)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION, from_legions_track=True)
    move_piece(state, rc.PROVINCIA, region, rc.ROMANS, rc.LEGION)
    state['resources'][rc.ROMANS] = resources

    assert is_event_effective(state, card, shaded=True)
    assert not should_decline_event(state, card, faction)
    event(state, faction, shaded=True)

    assert state['resources'][rc.ROMANS] == max(0, resources - 6)
    assert state['eligibility'][rc.ROMANS] == rc.INELIGIBLE
    assert state['forced_ineligible'][rc.ROMANS] == 1
