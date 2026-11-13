"""NP9-01 and NP9-02 through bot dispatch and live Command execution."""

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, flip_piece, place_piece
from fs_bot.bots.arverni_bot import node_v_rally
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cli.dispatcher import _translate_bot_action
from fs_bot.engine.execute import _resolve_free_command, execute_decision
from fs_bot.engine.game_engine import (
    ACTION_COMMAND, ACTION_COMMAND_SA, ACTION_EVENT, ACTION_LIMITED_COMMAND, ACTION_PASS,
    get_faction_order, get_first_eligible_options, resolve_card_turn,
)
from fs_bot.engine.winter_campaign import resolve_winter_campaign
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state
from fs_bot.tools.seat_session import board_copy


def check(state):
    assert validate_state(state) == check_structural_integrity(state) == []


def position(seed=6):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=seed)
    state['non_player_factions'] = {rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE}
    state['can_play_event'] = False
    state['resources'].update({faction: 10 for faction in state['non_player_factions']})
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    return state


def devastate_position(own, legions, auxilia, aedui):
    state = position()
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(state, rc.BITURIGES, rc.ARVERNI, rc.WARBAND, own, piece_state=rc.REVEALED)
    for faction, piece, count in ((rc.ROMANS, rc.LEGION, legions),
                                 (rc.ROMANS, rc.AUXILIA, auxilia),
                                 (rc.AEDUI, rc.WARBAND, aedui)):
        if count:
            place_piece(state, rc.BITURIGES, faction, piece, count,
                        from_legions_track=piece == rc.LEGION)
    return state


def execute_turn(state, faction, *, action_type=None, planner=dispatch_bot_turn):
    check(state)
    action = planner(state, faction)
    if action_type is None:
        action_type = _translate_bot_action(action, get_first_eligible_options())
    result = execute_decision(state, faction, {'action': action_type, 'bot_action': action})
    assert result['executed'] and not result.get('errors'), result
    check(state)
    return action, result


@pytest.mark.parametrize('own,legions,auxilia,aedui,enemy_losses', [
    (4, 1, 0, 0, 0),
    (4, 0, 2, 0, 0),
    (4, 0, 1, 0, 0),
    (4, 3, 0, 0, 1),
    (4, 0, 0, 3, 1),
    (6, 0, 2, 2, 0),
    (8, 1, 2, 0, 0),
    (8, 2, 1, 0, 0),
    (9, 0, 6, 0, 2),
    (12, 2, 4, 0, 2),
    (12, 0, 3, 3, 0),
    (8, 0, 3, 3, 2),
])
def test_devastate_uses_required_losses_and_owners_can_choose_their_pieces(
        own, legions, auxilia, aedui, enemy_losses):
    state = devastate_position(own, legions, auxilia, aedui)
    # The largest Roman force would trigger Battle in full dispatch. Use
    # the same Rally node directly to isolate the post-Rally casualty test.
    planner = (lambda board, _: node_v_rally(board)) if legions == 2 and auxilia == 4 else dispatch_bot_turn
    action, result = execute_turn(state, rc.ARVERNI, planner=planner)
    assert action['command'] == rc.CMD_RALLY
    assert action['sa'] == (rc.SA_DEVASTATE if enemy_losses else 'No SA')
    sa = result.get('sa_execution') or {}
    assert bool(sa.get('executed')) == bool(enemy_losses)
    assert not sa.get('errors')
    assert bool(state['markers'].get(rc.BITURIGES, {}).get(rc.MARKER_DEVASTATED)) == bool(enemy_losses)
    assert count_pieces(state, rc.BITURIGES, rc.ARVERNI, rc.WARBAND) == (
        own - (own // 4 if enemy_losses else 0))
    assert sum(count_pieces(state, rc.BITURIGES, f, p) for f, p in (
        (rc.ROMANS, rc.LEGION), (rc.ROMANS, rc.AUXILIA), (rc.AEDUI, rc.WARBAND),
    )) == legions + auxilia + aedui - enemy_losses


def test_bot_devastate_uses_the_roman_players_actual_casualty_choice():
    state = devastate_position(12, 2, 4, 0)
    state['non_player_factions'].remove(rc.ROMANS)
    requests = []

    def choose_losses(board, faction, request):
        if request['kind'] == 'devastate_losses' and faction == rc.ROMANS:
            assert board is state
            requests.append(request)
            return {'removals': [
                {'piece_type': rc.LEGION, 'piece_state': None, 'count': 1},
                {'piece_type': rc.AUXILIA, 'piece_state': rc.HIDDEN, 'count': 1},
            ]}
        return None

    state['decision_agent'] = choose_losses
    action, result = execute_turn(state, rc.ARVERNI, planner=lambda board, _: node_v_rally(board))
    assert action['command'] == rc.CMD_RALLY
    assert result['sa_execution']['sa'] == rc.SA_DEVASTATE
    assert [request['count'] for request in requests] == [2]
    assert count_pieces(state, rc.BITURIGES, rc.ROMANS, rc.LEGION) == 1
    assert count_pieces(state, rc.BITURIGES, rc.ROMANS, rc.AUXILIA) == 3
    assert state['fallen_legions'] == 1


def entreat_position(resources=10, with_sa=True):
    state = position()
    state['_command_with_sa'] = with_sa
    state['resources'][rc.ARVERNI] = resources
    place_piece(state, rc.MANDUBII, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    assert _ally_tribe(state, rc.TRIBE_AULERCI, rc.ARVERNI)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    return state


@pytest.mark.parametrize('resources,with_sa,forced_type,entreat', [
    (10, True, None, True),
    (3, True, None, False),
    (10, False, None, False),
    (10, True, ACTION_COMMAND, False),
])
def test_arverni_rally_rechecks_entreat_after_placements_and_cost(
        resources, with_sa, forced_type, entreat):
    state = entreat_position(resources, with_sa)
    before = encode(board_copy(state))
    assert dispatch_bot_turn(state, rc.ARVERNI)['command'] == rc.CMD_RALLY
    assert encode(board_copy(state)) == before

    action, result = execute_turn(state, rc.ARVERNI, action_type=forced_type)
    assert action['sa'] == (rc.SA_ENTREAT if with_sa and resources > 3 else 'No SA')
    assert bool((result.get('sa_execution') or {}).get('executed')) == entreat
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == (0 if entreat else 1)
    assert count_pieces_by_state(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == (
        3 if entreat else 2)
    assert state['resources'][rc.ARVERNI] == resources - 3 - entreat


@pytest.mark.parametrize('allowance,include_target', [(False, True), (True, False), (True, True)])
def test_free_rally_respects_event_scope_and_special_ability_grant(allowance, include_target):
    state = entreat_position(resources=0)
    regions = {rc.CARNUTES} if include_target else {rc.MANDUBII}
    result = _resolve_free_command(
        state, rc.ARVERNI, allowed_regions=regions, limited=True, with_sa=allowance,
        _planner=node_v_rally)
    expected = allowance and include_target
    assert result['executed'] and not result.get('errors')
    assert bool((result.get('sa_execution') or {}).get('executed')) == expected
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == (0 if expected else 1)
    assert state['resources'][rc.ARVERNI] == 0
    check(state)


def test_human_rally_retains_the_authored_no_special_ability():
    state = entreat_position()
    state['non_player_factions'].remove(rc.ARVERNI)
    action = {'command': rc.CMD_RALLY, 'sa': 'No SA',
              'details': {'rally_plan': {'warbands': [rc.CARNUTES]}}}
    result = execute_decision(state, rc.ARVERNI, {'action': ACTION_COMMAND, 'player_action': action})
    assert result['executed'] and not result.get('errors')
    assert 'sa_execution' not in result
    assert count_pieces(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND) == 2
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 1
    check(state)


def raid_entreat_position():
    state = entreat_position(resources=0)
    state['rng'].seed(1)
    place_piece(state, rc.BITURIGES, rc.ARVERNI, rc.WARBAND, 2)
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 3)
    return state


def test_arverni_raid_can_fund_entreat_in_another_region():
    state = raid_entreat_position()
    action, result = execute_turn(state, rc.ARVERNI)
    assert action['command'] == rc.CMD_RAID
    assert action['sa'] == 'No SA'
    assert result['sa_execution']['sa'] == rc.SA_ENTREAT
    assert result['sa_execution']['executed']
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 0
    assert state['resources'][rc.ARVERNI] == result['resources_gained_total'] - 1


def test_raid_and_late_entreat_use_both_winter_campaign_actions():
    state = raid_entreat_position()
    result = resolve_winter_campaign(state, rc.ARVERNI, 63)
    assert result['remaining_actions'] == 0
    assert len(result['actions']) == 1
    step = result['actions'][0]
    assert step['actions'] == 2 and step['plan']['command'] == rc.CMD_RAID
    assert step['result']['sa_execution']['sa'] == rc.SA_ENTREAT
    assert step['result']['sa_execution']['executed']
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 0
    check(state)


def belgic_position(hidden=2, german=2):
    state = position(seed=1)
    state['resources'][rc.BELGAE] = 0
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, hidden)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 3)
    if german:
        place_piece(state, rc.BITURIGES, rc.GERMANS, rc.WARBAND, german, piece_state=rc.REVEALED)
    return state


@pytest.mark.parametrize('hidden,german,sa', [
    (2, 2, rc.SA_ENLIST),
    (3, 2, rc.SA_RAMPAGE),
    (2, 0, None),
])
def test_belgic_raid_resolves_one_live_ability_and_reports_actual_sequence_option(hidden, german, sa):
    state = belgic_position(hidden, german)
    state['current_card'] = 55
    assert get_faction_order(state)[0] == rc.BELGAE
    other_options = []

    def decide(board, faction, options, slot):
        if faction == rc.BELGAE:
            # Isolate the Raid/Rampage choice while retaining the real card
            # loop, translation and Second Eligible options.
            board['can_play_event'] = False
            action = dispatch_bot_turn(board, faction)
            return {'action': _translate_bot_action(action, options), 'bot_action': action}
        other_options.append(options)
        return {'action': ACTION_PASS}

    before_rng = state['rng'].getstate()
    result = resolve_card_turn(state, decide, execute=True)
    assert before_rng != state['rng'].getstate()
    record = result['actions_taken'][rc.BELGAE]
    assert record['bot_action']['command'] == rc.CMD_RAID
    assert record['bot_action']['sa'] == (sa or 'No SA')
    ability = record['execution'].get('sa_execution') or {}
    assert (ability.get('sa') if ability.get('executed') else None) == sa
    assert record['action'] == (ACTION_COMMAND_SA if sa else ACTION_COMMAND)
    assert other_options and all(ACTION_LIMITED_COMMAND in opts for opts in other_options)
    assert all((ACTION_EVENT in opts) == bool(sa) for opts in other_options)
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == (2 if sa == rc.SA_RAMPAGE else 3)
    assert count_pieces_by_state(state, rc.BITURIGES, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == (
        2 if sa == rc.SA_ENLIST else 0)
    check(state)


@pytest.mark.parametrize('with_sa', [False, True])
def test_belgic_rally_prefers_rampage_enabled_by_its_new_warbands(with_sa):
    state = belgic_position()
    state['_command_with_sa'] = with_sa
    state['resources'][rc.BELGAE] = 10
    flip_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, count=2,
               from_state=rc.HIDDEN, to_state=rc.REVEALED)
    assert _ally_tribe(state, rc.TRIBE_AULERCI, rc.BELGAE)
    assert _ally_tribe(state, rc.TRIBE_CARNUTES, rc.BELGAE, citadel=True)
    action, result = execute_turn(state, rc.BELGAE)
    assert action['command'] == rc.CMD_RALLY
    assert action['sa'] == (rc.SA_RAMPAGE if with_sa else 'No SA')
    remaining = count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    assert (remaining < 3) is with_sa
    assert count_pieces_by_state(state, rc.BITURIGES, rc.GERMANS, rc.WARBAND, rc.REVEALED) == 2
    if with_sa:
        assert result['sa_execution']['sa'] == rc.SA_RAMPAGE
        assert result['sa_execution']['executed']
    else:
        assert 'sa_execution' not in result
