"""NP11-01 and NP11-02 through live Belgic and German March execution."""

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import is_controlled_by
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, find_leader, get_available, move_piece, place_piece,
)
from fs_bot.bots.belgae_bot import _check_enlist_after_command
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.bots.german_bot import node_g1b, node_g5, node_g_march_expand
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cli.dispatcher import _translate_bot_action
from fs_bot.engine.execute import _resolve_free_command, execute_decision
from fs_bot.engine.game_engine import (
    ACTION_COMMAND, ACTION_COMMAND_SA, ACTION_EVENT, ACTION_LIMITED_COMMAND, ACTION_PASS,
    get_first_eligible_options, get_sop_factions, resolve_card_turn,
)
from fs_bot.engine.victory import check_any_victory
from fs_bot.engine.winter_campaign import resolve_winter_campaign
from fs_bot.map.map_data import get_adjacent_for_state, get_tribes_in_region
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state
from fs_bot.tools.seat_session import board_copy


def _check(state):
    assert validate_state(state) == check_structural_integrity(state) == []


def _position(scenario, seed=6):
    state = build_initial_state(scenario, seed=seed)
    state['non_player_factions'] = set(get_sop_factions(state))
    state['can_play_event'] = False
    state['resources'].update({faction: 10 for faction in state['non_player_factions']})
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    return state


def _belgic_position(target=True):
    state = _position(rc.SCENARIO_PAX_GALLICA)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    place_piece(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND, 5)
    if target:
        place_piece(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, 2, piece_state=rc.REVEALED)
    # The documented witness needs Rally to be unavailable without exhausting pieces.
    for region in (*rc.BELGAE_HOME_REGIONS, rc.CARNUTES, rc.MANDUBII):
        state['markers'].setdefault(region, {})[rc.MARKER_DEVASTATED] = True
    _check(state)
    return state


def _hidden(state, region=rc.TREVERI):
    return count_pieces_by_state(state, region, rc.GERMANS, rc.WARBAND, rc.HIDDEN)


@pytest.mark.parametrize('target', [True, False], ids=['new-enlist', 'no-effect'])
def test_belgic_march_enlists_after_arrival_and_records_effective_action(target):
    state = _belgic_position(target)
    state['current_card'] = state['current_card_id'] = 55  # Belgae first.
    second_options = []

    def decide(board, faction, options, position):
        if faction == rc.BELGAE:
            board['can_play_event'] = False
            before = encode(board_copy(board))
            action = dispatch_bot_turn(board, faction)
            assert encode(board_copy(board)) == before
            return {'action': _translate_bot_action(action, options), 'bot_action': action}
        second_options.append(options)
        return {'action': ACTION_PASS}

    result = resolve_card_turn(state, decide, execute=True)

    record = result['actions_taken'][rc.BELGAE]
    execution = record['execution']
    assert execution['executed'] and execution['total_cost'] == 4 and not execution['errors']
    assert state['resources'][rc.BELGAE] == 6 and find_leader(state, rc.BELGAE) == rc.ATREBATES
    assert count_pieces(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND) == 4
    assert _hidden(state) == (2 if target else 0)
    assert bool(execution['sa_execution']['executed']) is target
    assert execution['sa_execution']['sa'] == rc.SA_ENLIST
    assert record['action'] == (ACTION_COMMAND_SA if target else ACTION_COMMAND)
    assert second_options and ACTION_LIMITED_COMMAND in second_options[0]
    assert (ACTION_EVENT in second_options[0]) is target
    _check(state)


@pytest.mark.parametrize('with_sa,include_target', [(False, True), (True, False), (True, True)])
def test_belgic_free_march_applies_enlist_only_when_granted_and_in_scope(with_sa, include_target):
    state = _belgic_position()
    scope = {rc.CARNUTES, rc.MANDUBII}
    if include_target:
        scope.add(rc.TREVERI)

    result = _resolve_free_command(
        state, rc.BELGAE, allowed_regions=scope,
        exclude_commands={rc.CMD_RALLY, rc.CMD_RAID, rc.CMD_BATTLE}, with_sa=with_sa)

    assert result['executed'] and not result['errors'] and result['total_cost'] == 0
    assert find_leader(state, rc.BELGAE) == rc.ATREBATES
    assert _hidden(state) == (2 if with_sa and include_target else 0)
    _check(state)


@pytest.mark.parametrize('budget', [4, 5])
def test_belgic_enlist_is_barred_only_by_an_actual_britannia_crossing(budget):
    state = _belgic_position()
    state['resources'][rc.BELGAE] = budget
    action = dispatch_bot_turn(state, rc.BELGAE)
    assert action['command'] == rc.CMD_MARCH
    place_piece(state, rc.BRITANNIA, rc.BELGAE, rc.WARBAND)
    action['details']['march_plan']['explicit_moves'] = [
        {'origin': rc.CARNUTES, 'path': [rc.ATREBATES], 'group': {rc.LEADER: True}},
        {'origin': rc.MANDUBII, 'path': [rc.ATREBATES], 'group': {rc.WARBAND: 4}},
        {'origin': rc.BRITANNIA, 'path': [rc.MORINI], 'group': {rc.WARBAND: 1}},
    ]

    result = execute_decision(state, rc.BELGAE, {'action': ACTION_COMMAND_SA, 'bot_action': action})

    assert result['executed'] and not result['errors'] and result['total_cost'] == budget
    assert result['deferred_origins'] == ([rc.BRITANNIA] if budget == 4 else [])
    assert _hidden(state) == (2 if budget == 4 else 0)
    assert bool((result.get('sa_execution') or {}).get('executed')) is (budget == 4)
    _check(state)


def test_belgic_winter_march_and_live_enlist_cost_two_actions():
    state = _belgic_position()
    result = resolve_winter_campaign(state, rc.BELGAE, 63)
    action, = result['actions']
    assert action['plan']['command'] == rc.CMD_MARCH
    assert action['actions'] == 2 and result['remaining_actions'] == 0
    assert _hidden(state) == 2 and state['resources'][rc.BELGAE] == 6
    _check(state)


def test_belgic_threat_march_uses_the_same_live_enlist_window():
    state = _position(rc.SCENARIO_PAX_GALLICA)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    place_piece(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND)
    place_piece(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, 2, piece_state=rc.REVEALED)
    assert _ally_tribe(state, rc.TRIBE_CARNUTES, rc.ROMANS)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 4)
    action = dispatch_bot_turn(state, rc.BELGAE)
    assert action['details']['march_plan']['type'] == 'March (threat)'
    kind = _translate_bot_action(action, get_first_eligible_options())

    result = execute_decision(state, rc.BELGAE, {'action': kind, 'bot_action': action})

    assert result['executed'] and not result['errors'] and result['total_cost'] == 1
    assert find_leader(state, rc.BELGAE) == rc.ATREBATES
    assert result['sa_execution']['executed'] and _hidden(state) == 2
    _check(state)


def test_belgic_enlist_march_respects_gallia_togata_stacking():
    state = _position(rc.SCENARIO_ARIOVISTUS)
    place_piece(state, rc.UBII, rc.BELGAE, rc.LEADER, leader_name=rc.BODUOGNATUS)
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 2, piece_state=rc.REVEALED)
    place_piece(state, rc.CISALPINA, rc.ROMANS, rc.AUXILIA, 3)
    state['markers'].setdefault(rc.CISALPINA, {})[rc.MARKER_GALLIA_TOGATA] = {'card_id': 'A5'}
    _check(state)

    plan = _check_enlist_after_command(state, state['scenario'])

    assert plan['type'] == 'german_march_hide' and plan['region'] == rc.UBII


def _german_position(seed):
    state = _position(rc.SCENARIO_ARIOVISTUS, seed)
    place_piece(state, rc.UBII, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    for region in get_adjacent_for_state(state, rc.UBII, rc.GERMANS):
        place_piece(state, region, rc.GERMANS, rc.WARBAND)
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, get_available(state, rc.GERMANS, rc.WARBAND))
    for region in (rc.UBII, rc.SUGAMBRI, rc.TREVERI, rc.SEQUANI):
        for tribe in get_tribes_in_region(region, state['scenario']):
            if get_available(state, rc.GERMANS, rc.ALLY):
                assert _ally_tribe(state, tribe, rc.GERMANS)
    for region in (rc.TREVERI, rc.SEQUANI, rc.CISALPINA, rc.NERVII, rc.MANDUBII, rc.ATREBATES):
        place_piece(state, region, rc.GERMANS, rc.SETTLEMENT)
    for region in (rc.CARNUTES, rc.PICTONES):
        for tribe in get_tribes_in_region(region, state['scenario']):
            assert _ally_tribe(state, tribe, rc.AEDUI)
    for region in (rc.NERVII, rc.MANDUBII, rc.ATREBATES):
        place_piece(state, region, rc.ROMANS, rc.AUXILIA, 2)
    assert check_any_victory(state) is None
    assert node_g1b(state) == node_g5(state) == 'No'
    _check(state)
    return state


def test_surrounded_german_leader_advances_one_step_with_most_warbands():
    destinations = set()
    for seed in range(1, 9):
        state = _german_position(seed)
        nearby = get_adjacent_for_state(state, rc.UBII, rc.GERMANS)
        assert all(is_controlled_by(state, r, rc.GERMANS) for r in (rc.UBII, *nearby))
        initial = encode(board_copy(state))
        action = dispatch_bot_turn(state, rc.GERMANS)
        planned = encode(board_copy(state))
        assert {k: v for k, v in planned.items() if k != 'rng'} == {
            k: v for k, v in initial.items() if k != 'rng'}
        assert action['command'] == rc.CMD_MARCH
        kind = _translate_bot_action(action, get_first_eligible_options())

        result = execute_decision(state, rc.GERMANS, {'action': kind, 'bot_action': action})

        assert result['executed'] and not result['errors'] and result['total_cost'] == 1
        march, = result['marches']
        destination = march['final_region']
        assert march['origin'] == rc.UBII and destination in nearby
        assert any(not is_controlled_by(state, r, rc.GERMANS)
                   for r in get_adjacent_for_state(state, destination, rc.GERMANS))
        assert find_leader(state, rc.GERMANS) == destination
        assert count_pieces(state, destination, rc.GERMANS, rc.WARBAND) == 26
        assert count_pieces(state, rc.UBII, rc.GERMANS, rc.WARBAND) == 1
        assert is_controlled_by(state, rc.UBII, rc.GERMANS)
        assert state['resources'][rc.GERMANS] == 9
        destinations.add(destination)
        _check(state)
    assert len(destinations) > 1


def test_german_free_march_can_move_the_largest_group_to_the_leader_within_origin_scope():
    state = _german_position(seed=6)
    move_piece(state, rc.UBII, rc.CISALPINA, rc.GERMANS, rc.WARBAND)
    state['resources'][rc.GERMANS] = 0

    result = _resolve_free_command(
        state, rc.GERMANS, allowed_regions={rc.CISALPINA},
        exclude_commands={rc.CMD_RALLY, rc.CMD_RAID, rc.CMD_BATTLE})

    assert result['executed'] and not result['errors'] and result['total_cost'] == 0
    march, = result['marches']
    assert (march['origin'], march['final_region']) == (rc.CISALPINA, rc.UBII)
    assert find_leader(state, rc.GERMANS) == rc.UBII
    assert count_pieces(state, rc.CISALPINA, rc.GERMANS, rc.WARBAND) == 1
    assert state['resources'][rc.GERMANS] == 0
    _check(state)


def test_german_away_group_advances_toward_leader_after_control_move():
    state = _position(rc.SCENARIO_ARIOVISTUS)
    place_piece(state, rc.UBII, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 10)
    place_piece(state, rc.CISALPINA, rc.GERMANS, rc.WARBAND, 3)
    _check(state)

    action = node_g_march_expand(state)
    kind = _translate_bot_action(action, get_first_eligible_options())
    result = execute_decision(state, rc.GERMANS, {'action': kind, 'bot_action': action})

    assert result['executed'] and not result['errors'] and result['total_cost'] == 2
    assert [(move['origin'], move['final_region']) for move in result['marches']] == [
        (rc.UBII, rc.SUGAMBRI), (rc.CISALPINA, rc.UBII),
    ]
    assert find_leader(state, rc.GERMANS) == rc.SUGAMBRI
    assert count_pieces(state, rc.UBII, rc.GERMANS, rc.WARBAND) == 3
    assert count_pieces(state, rc.CISALPINA, rc.GERMANS, rc.WARBAND) == 1
    _check(state)


def test_german_leader_stays_when_he_is_needed_to_retain_origin_control():
    state = _position(rc.SCENARIO_ARIOVISTUS)
    place_piece(state, rc.UBII, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND)
    for region in get_adjacent_for_state(state, rc.UBII, rc.GERMANS):
        place_piece(state, region, rc.GERMANS, rc.WARBAND)
    place_piece(state, rc.UBII, rc.ROMANS, rc.AUXILIA)
    _check(state)
    assert is_controlled_by(state, rc.UBII, rc.GERMANS)

    action = node_g_march_expand(state)

    if action['command'] == rc.CMD_MARCH:
        kind = _translate_bot_action(action, get_first_eligible_options())
        result = execute_decision(state, rc.GERMANS, {'action': kind, 'bot_action': action})
        assert result['executed'] and not result['errors']
    assert find_leader(state, rc.GERMANS) == rc.UBII
    assert is_controlled_by(state, rc.UBII, rc.GERMANS)
    _check(state)
