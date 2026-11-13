"""NP10-01 and NP10-02 through dispatch, Command execution and scoped grants."""

from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_available, move_piece, place_piece
from fs_bot.bots.arverni_bot import (
    MARCH_MASS, MARCH_SPREAD, MARCH_THREAT, node_v_march_mass, node_v_march_spread,
)
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cli.dispatcher import _translate_bot_action, make_decision_func
from fs_bot.commands.sa_devastate import devastate_region, validate_devastate_region
from fs_bot.engine.execute import _resolve_free_command, execute_decision
from fs_bot.engine.game_engine import (
    ACTION_COMMAND, ACTION_COMMAND_SA, ACTION_EVENT, ACTION_PASS,
    get_first_eligible_options, get_second_eligible_options, play_card,
)
from fs_bot.engine.winter_campaign import resolve_winter_campaign
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state
from fs_bot.tools.seat_session import board_copy


def _position(resources=4):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=6)
    state['non_player_factions'] = {rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE}
    state['can_play_event'] = False
    state['resources'][rc.ARVERNI] = resources
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    return state


def _integrity(state):
    assert validate_state(state) == check_structural_integrity(state) == []


def _march_position(resources=4, *, origin=rc.MANDUBII, destination=rc.CARNUTES, target=True):
    state = _position(resources)
    place_piece(state, origin, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(state, origin, rc.ARVERNI, rc.WARBAND, 9)
    if target:
        place_piece(state, destination, rc.ROMANS, rc.AUXILIA)
    return state


def _execute_bot(state, *, action=None, action_type=None, options=None):
    _integrity(state)
    before = encode(board_copy(state))
    action = dispatch_bot_turn(state, rc.ARVERNI) if action is None else action
    assert encode(board_copy(state)) == before
    if action_type is None:
        action_type = _translate_bot_action(action, options or get_first_eligible_options())
    result = execute_decision(state, rc.ARVERNI, {'action': action_type, 'bot_action': action})
    assert result['executed'] and not result.get('errors'), result
    assert not (result.get('sa_execution') or {}).get('errors'), result
    _integrity(state)
    return action, action_type, result


def _assert_entreat(state, result, destination=rc.CARNUTES):
    sa = result['sa_execution']
    assert sa['executed'] and sa['sa'] == rc.SA_ENTREAT and sa['rederived_at_sa_time']
    assert sa['actions'] == [{'region': destination, 'action': 'replace_piece'}]
    assert count_pieces(state, destination, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces_by_state(state, destination, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 9


@pytest.mark.parametrize('options', [None, get_second_eligible_options(ACTION_COMMAND)])
def test_dispatched_spread_march_entreats_after_moving_and_paying(options):
    state = _march_position()
    action, action_type, result = _execute_bot(state, options=options)
    assert action['details']['march_plan']['type'] == MARCH_SPREAD
    if options is None:
        assert action_type == ACTION_COMMAND_SA
    else:
        # §8.1.2 upgrades the non-player's Sequence-of-Play Limited Command.
        assert action_type in options
    assert result['total_cost'] == 1 and result['sa_timing'] == 'after'
    assert result['marches'][0]['final_region'] == rc.CARNUTES
    _assert_entreat(state, result)
    assert state['resources'][rc.ARVERNI] == 2


@pytest.mark.parametrize('resources,target,command_only', [
    (4, True, True), (1, True, False), (4, False, False),
])
def test_spread_march_respects_sa_allowance_resources_and_targets(resources, target, command_only):
    state = _march_position(resources, target=target)
    action, _, result = _execute_bot(state, action_type=ACTION_COMMAND if command_only else None)
    assert action['details']['march_plan']['type'] == MARCH_SPREAD
    assert not (result.get('sa_execution') or {}).get('executed')
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == int(target)
    assert state['resources'][rc.ARVERNI] == resources - 1


@pytest.mark.parametrize('legions', [3, 5])
def test_mass_march_checks_live_devastate_before_entreat(legions):
    state = _march_position()
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEGION, legions, from_legions_track=True)
    before = encode(board_copy(state))
    action = node_v_march_mass(state)
    assert encode(board_copy(state)) == before
    assert action['details']['march_plan']['type'] == MARCH_MASS
    _, _, result = _execute_bot(state, action=action)
    if legions == 3:
        # Rome can take its one forced loss on the Auxilium, so this
        # position falls through to Entreat with the Legions still there.
        _assert_entreat(state, result)
        assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.LEGION) == legions
        assert state['resources'][rc.ARVERNI] == 2
    else:
        sa = result['sa_execution']
        assert sa['executed'] and sa['sa'] == rc.SA_DEVASTATE
        assert sa['regions'] == [rc.CARNUTES]
        assert state['markers'][rc.CARNUTES][rc.MARKER_DEVASTATED]
        assert count_pieces(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND) == 6
        assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.LEGION) == legions - 1
        assert state['resources'][rc.ARVERNI] == 3


@pytest.mark.parametrize('allowance,include_target', [(False, True), (True, False), (True, True)])
def test_granted_spread_march_keeps_its_origin_cap_and_ability_scope(allowance, include_target):
    state = _march_position(resources=0)
    scope = {rc.MANDUBII, rc.CARNUTES} if include_target else {rc.MANDUBII}
    result = _resolve_free_command(state, rc.ARVERNI, allowed_regions=scope, limited=True,
                                   with_sa=allowance, _planner=node_v_march_spread)
    assert result['executed'] and not result.get('errors'), result
    assert result['origin_costs'] == {rc.MANDUBII: 0}
    if allowance and include_target:
        _assert_entreat(state, result)
    else:
        assert not (result.get('sa_execution') or {}).get('executed')
        assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 1
    assert state['resources'][rc.ARVERNI] == 0
    _integrity(state)


@pytest.mark.parametrize('origin,destination', [(rc.BRITANNIA, rc.MORINI), (rc.MORINI, rc.BRITANNIA)])
def test_spread_march_crossing_britannia_executes_command_without_ability(origin, destination):
    state = _march_position(origin=origin, destination=destination)
    action, _, result = _execute_bot(state)
    assert action['details']['march_plan']['type'] == MARCH_SPREAD
    assert result['marches'][0]['origin'] == origin
    assert result['marches'][0]['final_region'] == destination
    assert 'sa_execution' not in result
    assert count_pieces(state, destination, rc.ROMANS, rc.AUXILIA) == 1
    assert state['resources'][rc.ARVERNI] == 3


def test_unaffordable_britannia_group_does_not_block_post_march_ability():
    state = _march_position(resources=1)
    place_piece(state, rc.BRITANNIA, rc.ARVERNI, rc.WARBAND, 2)
    action = node_v_march_spread(state)
    action['details']['march_plan']['explicit_moves'] = [
        {'origin': rc.MANDUBII, 'path': [rc.CARNUTES],
         'group': {rc.LEADER: rc.VERCINGETORIX, rc.WARBAND: 8}},
        {'origin': rc.BRITANNIA, 'path': [rc.MORINI], 'group': {rc.WARBAND: 1}},
    ]
    # A free move is not needed to demonstrate the restriction. Devastate
    # can still act with zero Resources after the only paid group moves.
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEGION, 5, from_legions_track=True)
    _, _, result = _execute_bot(state, action=action)
    assert result['deferred_origins'] == [rc.BRITANNIA]
    assert result['origin_costs'] == {rc.MANDUBII: 1}
    assert result['sa_execution']['regions'] == [rc.CARNUTES]
    assert result['sa_execution']['sa'] == rc.SA_DEVASTATE
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.LEGION) == 4


def test_threat_march_still_entreats_after_payment_before_moving():
    state = _march_position(destination=rc.MANDUBII)
    action = {'command': rc.CMD_MARCH, 'regions': [rc.CARNUTES],
              'sa': rc.SA_ENTREAT, 'sa_regions': [rc.MANDUBII],
              'details': {'march_plan': {
                  'type': MARCH_THREAT, 'origins': [rc.MANDUBII],
                  'destinations': [rc.CARNUTES], 'routes': {rc.MANDUBII: [rc.CARNUTES]}}}}
    _, _, result = _execute_bot(state, action=action)
    assert result['sa_timing'] == 'during-before-movement'
    assert result['sa_execution']['actions'] == [{'region': rc.MANDUBII, 'action': 'replace_piece'}]
    assert result['total_cost'] == 1 and state['resources'][rc.ARVERNI] == 2
    assert count_pieces(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND) == 10


def test_post_march_entreat_skips_roman_ally_even_with_no_available_warbands():
    state = _march_position(target=False)
    state['non_player_factions'].remove(rc.ROMANS)
    assert _ally_tribe(state, rc.TRIBE_AULERCI, rc.ROMANS)
    place_piece(state, rc.VENETI, rc.ARVERNI, rc.WARBAND,
                get_available(state, rc.ARVERNI, rc.WARBAND))
    action = node_v_march_spread(state)
    action['details']['march_plan']['explicit_moves'] = [
        {'origin': rc.MANDUBII, 'path': [rc.CARNUTES],
         'group': {rc.LEADER: rc.VERCINGETORIX, rc.WARBAND: 8}},
    ]
    _, _, result = _execute_bot(state, action=action)
    assert result['sa_execution']['declined_no_effect']
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.ALLY) == 1
    assert state['resources'][rc.ARVERNI] == 3


def test_winter_campaign_allows_entreat_after_britannia_crossing_with_two_actions():
    state = _march_position(origin=rc.BRITANNIA, destination=rc.MORINI)
    campaign = resolve_winter_campaign(state, rc.ARVERNI, 63)
    assert campaign['remaining_actions'] == 0
    step, = campaign['actions']
    assert step['actions'] == 2
    assert step['result']['marches'][0]['origin'] == rc.BRITANNIA
    _assert_entreat(state, step['result'], rc.MORINI)
    assert state['resources'][rc.ARVERNI] == 2
    _integrity(state)


@pytest.mark.parametrize('resources,expected', [(1, ACTION_COMMAND), (4, ACTION_COMMAND_SA)])
def test_spread_march_effective_ability_controls_second_eligible_options(resources, expected):
    state = _march_position(resources)
    state.update(current_card=20, next_card=21, deck=[21, 22])
    choose_bot = make_decision_func({}, StringIO(), StringIO(), pause=False)
    second = []

    def choose(board, faction, options, position):
        if faction == rc.ARVERNI:
            return choose_bot(board, faction, options, position)
        second.append((faction, list(options)))
        return {'action': ACTION_PASS}

    result = play_card(state, choose, execute=True)
    action = result['turn_result']['actions_taken'][rc.ARVERNI]
    assert action['action'] == expected
    assert (ACTION_EVENT in second[0][1]) == (expected == ACTION_COMMAND_SA)
    if expected == ACTION_COMMAND:
        assert action['declared_action'] == ACTION_COMMAND_SA
    _integrity(state)


@pytest.mark.parametrize('marker,command_only,in_range', [
    (True, False, True), (False, False, True), (False, True, True), (True, False, False),
])
def test_later_bot_rally_can_devastate_same_region_again(marker, command_only, in_range):
    state = _position(resources=10)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(state, rc.BITURIGES, rc.ARVERNI, rc.WARBAND, 8, piece_state=rc.REVEALED)
    place_piece(state, rc.BITURIGES, rc.ROMANS, rc.LEGION, 6, from_legions_track=True)
    assert validate_devastate_region(state, rc.BITURIGES)[0]
    assert devastate_region(state, rc.BITURIGES)['devastated_placed']
    assert count_pieces(state, rc.BITURIGES, rc.ARVERNI, rc.WARBAND) == 6
    assert count_pieces(state, rc.BITURIGES, rc.ROMANS, rc.LEGION) == 4
    if not marker:
        del state['markers'][rc.BITURIGES][rc.MARKER_DEVASTATED]
    if not in_range:
        move_piece(state, rc.ARVERNI_REGION, rc.VENETI, rc.ARVERNI, rc.LEADER)
    assert validate_devastate_region(state, rc.BITURIGES)[0] is in_range
    action, _, result = _execute_bot(state, action_type=ACTION_COMMAND if command_only else None)
    assert action['command'] == rc.CMD_RALLY
    repeat = in_range and not command_only
    if repeat:
        sa = result['sa_execution']
        assert sa['executed'] and sa['sa'] == rc.SA_DEVASTATE
        assert sa['regions'] == [rc.BITURIGES]
    else:
        assert not (result.get('sa_execution') or {}).get('executed')
    assert state['markers'][rc.BITURIGES] == ({rc.MARKER_DEVASTATED: True} if marker or repeat else {})
    assert count_pieces(state, rc.BITURIGES, rc.ARVERNI, rc.WARBAND) == 6 - repeat
    assert count_pieces(state, rc.BITURIGES, rc.ROMANS, rc.LEGION) == 4 - repeat
    assert state['fallen_legions'] == 2 + repeat
