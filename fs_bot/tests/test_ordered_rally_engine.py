"""Exact Rally order, once-per-Region additions, and rollback boundaries."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, get_available, place_piece
from fs_bot.bots.bot_common import prevalidate_rally_plan
from fs_bot.cards.capabilities import activate_capability, set_capability_owner
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.commands.common import CommandError
from fs_bot.commands.rally import recruit_in_region, rally_in_region
from fs_bot.engine import execute as ex
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state


def position():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=4)
    state['resources'][rc.ARVERNI] = 10
    place_piece(state, rc.PICTONES, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    activate_capability(state, 25, rc.EVENT_SHADED)
    set_capability_owner(state, 25, rc.ARVERNI)
    return state


def action(steps):
    return {'command': rc.CMD_RALLY, 'details': {'rally_plan': {'steps': steps}}}


@pytest.mark.parametrize('troops_first,expected', [(False, 5), (True, 4)])
def test_vercingetorix_order_changes_cap_and_applies_bonus_exactly_once(troops_first, expected):
    state = position()
    ally = {'region': rc.PICTONES, 'action': 'place_ally', 'tribe': rc.TRIBE_PICTONES}
    warbands = {'region': rc.PICTONES, 'action': 'place_warbands', 'count': 4 if troops_first else 3}
    steps = [warbands, ally] if troops_first else [ally, warbands]
    result = ex._execute_rally(state, rc.ARVERNI, action(steps))
    assert result['executed'] and not result['errors']
    assert count_pieces(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND) == expected
    assert count_pieces(state, rc.PICTONES, rc.ARVERNI, rc.ALLY) == 1
    assert state['resources'][rc.ARVERNI] == 9
    assert validate_state(state) == []


def test_late_overallocation_rolls_back_pieces_rng_and_preserves_live_turn_identity():
    state = position()
    turn = {'card': 16, 'faction': rc.ARVERNI, 'accepted': []}
    state['_card_turn'] = turn
    agent = lambda *args: None
    state['decision_agent'] = agent
    before = encode({k: v for k, v in state.items() if k != 'decision_agent'})
    result = ex._execute_rally(state, rc.ARVERNI, action([
        {'region': rc.PICTONES, 'action': 'place_ally', 'tribe': rc.TRIBE_PICTONES},
        # Bonus already occurred on the Ally option: second troop option cap3.
        {'region': rc.PICTONES, 'action': 'place_warbands', 'count': 4},
    ]))
    assert not result['executed'] and result['rolled_back'] and result['errors']
    assert state['_card_turn'] is turn and state['decision_agent'] is agent
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before


def test_np_prevalidation_does_not_spend_bonus_twice_before_later_regions():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=5)
    state['resources'][rc.ARVERNI] = 10
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    _ally_tribe(state, rc.TRIBE_ARVERNI, rc.ARVERNI)
    _ally_tribe(state, rc.TRIBE_MANDUBII, rc.ARVERNI)
    activate_capability(state, 25, rc.EVENT_SHADED)
    set_capability_owner(state, 25, rc.ARVERNI)
    place_piece(state, rc.PROVINCIA, rc.ARVERNI, rc.WARBAND,
                get_available(state, rc.ARVERNI, rc.WARBAND) - 7)
    plan = {'citadels': [{'region': rc.ARVERNI_REGION, 'tribe': rc.TRIBE_ARVERNI}],
            'allies': [], 'warbands': [rc.ARVERNI_REGION, {'region': rc.MANDUBII, 'count': 2}]}
    before = encode(state)
    validated = prevalidate_rally_plan(state, rc.ARVERNI, plan)
    assert validated['warbands'] == plan['warbands'] and encode(state) == before
    result = ex._execute_rally(state, rc.ARVERNI,
        {'command': rc.CMD_RALLY, 'details': {'rally_plan': validated}})
    assert result['executed'] and not result['errors']
    assert count_pieces(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND) == 5
    assert count_pieces(state, rc.MANDUBII, rc.ARVERNI, rc.WARBAND) == 2
    assert get_available(state, rc.ARVERNI, rc.WARBAND) == 0


def test_scope_filter_preserves_chosen_order_and_exact_counts_without_live_mutation():
    state = position()
    plan = action([
        {'region': rc.ARVERNI_REGION, 'action': 'place_warbands', 'count': 2},
        {'region': rc.PICTONES, 'action': 'place_warbands', 'count': 3},
        {'region': rc.PICTONES, 'action': 'place_ally', 'tribe': rc.TRIBE_PICTONES},
    ])
    original = deepcopy(plan)
    constrained = ex._constrain_bot_action(plan, {rc.PICTONES}, state=state, faction=rc.ARVERNI)
    assert constrained['details']['rally_plan']['steps'] == original['details']['rally_plan']['steps'][1:]
    assert ex._primary_command_region(constrained) == rc.PICTONES
    assert ex._plan_region_order(constrained) == [rc.PICTONES]
    assert plan == original


def test_duplicate_recruit_regions_are_rejected_even_for_legacy_np_plans():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=4)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    before = encode(state)
    result = ex._execute_recruit(state, rc.ROMANS, {'details': {'recruit_plan': [
        {'region': rc.SEQUANI, 'action': 'place_ally', 'tribe': rc.TRIBE_SEQUANI},
        {'region': rc.SEQUANI, 'action': 'place_auxilia'},
    ]}})
    assert not result['executed'] and result['errors']
    assert encode(state) == before


@pytest.mark.parametrize('invalid', [[], 'Rally', True, 1])
def test_malformed_human_action_container_is_refused_without_board_or_rng_change(invalid):
    state = position()
    before = encode(state)
    result = ex.execute_decision(state, rc.ARVERNI, {'player_action': invalid})
    assert not result['executed'] and result['errors']
    assert result['reason'] == 'The Command plan must be an object'
    assert encode(state) == before


@pytest.mark.parametrize('scenario,card,total', [
    (rc.SCENARIO_GREAT_REVOLT, 5, 2),
    (rc.SCENARIO_ARIOVISTUS, 'A5', 1),
])
def test_gallia_bonus_only_recruit_survives_roman_departure(scenario, card, total):
    state = build_initial_state(scenario, seed=4)
    state['markers'].setdefault(rc.CISALPINA, {})[rc.MARKER_GALLIA_TOGATA] = {'card_id': card}
    result = recruit_in_region(state, rc.CISALPINA, 'place_auxilia', count=total)
    assert result['pieces_placed'] == {rc.AUXILIA: total}
    assert count_pieces(state, rc.CISALPINA, rc.ROMANS, rc.AUXILIA) == total


def test_owned_aquitani_can_rally_two_warbands_into_empty_pictones():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=4)
    state['resources'][rc.AEDUI] = 3
    activate_capability(state, 25, rc.EVENT_SHADED)
    set_capability_owner(state, 25, rc.AEDUI)
    result = rally_in_region(state, rc.PICTONES, rc.AEDUI, 'place_warbands', count=2)
    assert result['pieces_placed'] == {rc.WARBAND: 2}
    assert count_pieces(state, rc.PICTONES, rc.AEDUI, rc.WARBAND) == 2
    assert state['resources'][rc.AEDUI] == 2


@pytest.mark.parametrize('scenario,marker', [
    (rc.SCENARIO_GREAT_REVOLT, rc.MARKER_DEVASTATED),
    (rc.SCENARIO_ARIOVISTUS, rc.MARKER_INTIMIDATED),
])
@pytest.mark.parametrize('command', [rc.CMD_RECRUIT, rc.CMD_RALLY])
def test_bonus_only_placement_retains_devastation_and_intimidation_restrictions(scenario, marker, command):
    state = build_initial_state(scenario, seed=4)
    if command == rc.CMD_RECRUIT:
        region = rc.CISALPINA
        card = 'A5' if scenario == rc.SCENARIO_ARIOVISTUS else 5
        state['markers'].setdefault(region, {})[rc.MARKER_GALLIA_TOGATA] = {'card_id': card}
        call = lambda: recruit_in_region(state, region, 'place_auxilia')
    else:
        region = rc.PICTONES
        activate_capability(state, 25, rc.EVENT_SHADED)
        set_capability_owner(state, 25, rc.AEDUI)
        call = lambda: rally_in_region(state, region, rc.AEDUI, 'place_warbands')
    state['markers'].setdefault(region, {})[marker] = True
    before = encode(state)
    with pytest.raises(CommandError, match='Devastated|Intimidated'):
        call()
    assert encode(state) == before


def test_empty_bonus_region_requires_actual_active_owner_and_playable_geography():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=4)
    activate_capability(state, 25, rc.EVENT_SHADED)
    set_capability_owner(state, 25, rc.ARVERNI)
    before = encode(state)
    with pytest.raises(CommandError):
        rally_in_region(state, rc.PICTONES, rc.AEDUI, 'place_warbands')
    with pytest.raises(CommandError, match='not playable'):
        recruit_in_region(state, rc.CISALPINA, 'place_auxilia')
    assert encode(state) == before


@pytest.mark.parametrize('ordered', [True, False])
@pytest.mark.parametrize('invalid_first', [False, True])
def test_interrupted_exact_rally_error_rolls_back_both_portions_and_suborn(ordered, invalid_first):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=4)
    state['resources'][rc.AEDUI] = 10
    for tribe in (rc.TRIBE_AEDUI, rc.TRIBE_SEQUANI):
        assert _ally_tribe(state, tribe, rc.AEDUI)
    place_piece(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND)
    def part(region, count):
        entry = {'region': region, 'action': 'place_warbands', 'count': count}
        return {'command': rc.CMD_RALLY, 'details': {'rally_plan': {
            'steps' if ordered else 'warbands': [entry]}}}
    first, second = (99, 1) if invalid_first else (1, 99)
    command = {'command': rc.CMD_RALLY, 'sa': rc.SA_SUBORN, 'sa_timing': 'during',
               'sa_regions': [rc.MANDUBII], 'details': {
        'command_parts': [part(rc.AEDUI_REGION, first), part(rc.SEQUANI, second)],
        'suborn_plan': [{'region': rc.MANDUBII, 'actions': [
            {'action': 'place', 'piece_type': rc.WARBAND, 'faction': rc.AEDUI}]}],
    }}
    progress = state['_card_turn'] = {'actions_taken': []}
    agent = state['decision_agent'] = lambda *_: None
    before = encode({k: v for k, v in state.items() if k != 'decision_agent'})
    result = ex.execute_decision(state, rc.AEDUI, {'player_action': command})
    assert not result['executed'] and result['rolled_back'] and result['errors']
    assert result['sa_execution']['executed']  # the attempted intervening SA was legal
    assert state['_card_turn'] is progress and state['decision_agent'] is agent
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before
