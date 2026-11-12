"""NP7-01 and NP7-02 through the ordinary dispatcher and executor."""

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece
from fs_bot.bots import aedui_bot, arverni_bot, belgae_bot, german_bot
from fs_bot.bots.bot_common import predict_battle
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.cards.capabilities import activate_capability, set_capability_owner
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_COMMAND, ACTION_COMMAND_SA
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state


BATTLE_FACTIONS = (
    (rc.BELGAE, rc.AMBIORIX, 4, 12, 2),
    (rc.ARVERNI, rc.VERCINGETORIX, 10, 20, 5),
    (rc.GERMANS, rc.ARIOVISTUS_LEADER, 6, 18, 3),
)
RAID_FACTIONS = (
    (rc.BELGAE, belgae_bot),
    (rc.ARVERNI, arverni_bot),
    (rc.AEDUI, aedui_bot),
    (rc.GERMANS, german_bot),
)


def _board(faction, *, resources=10, sa=True, seed=6):
    expansion = faction == rc.GERMANS
    scenario = rc.SCENARIO_ARIOVISTUS if expansion else rc.SCENARIO_GREAT_REVOLT
    state = build_initial_state(scenario, seed=seed)
    state['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE,
                                    rc.GERMANS if expansion else rc.ARVERNI}
    state['can_play_event'] = False
    state['_command_with_sa'] = sa
    for seat in state['non_player_factions']:
        state['resources'][seat] = resources
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    return state


def _integrity(state):
    assert validate_state(state) == check_structural_integrity(state) == []


def _execute(state, faction, action):
    _integrity(state)
    sop = ACTION_COMMAND_SA if state['_command_with_sa'] else ACTION_COMMAND
    result = execute_decision(state, faction, {'action': sop, 'bot_action': action})
    assert result['executed'] and not result.get('errors'), result
    _integrity(state)
    return result


def _forces(state, region, faction, warbands, auxilia, *, hidden=True):
    place_piece(state, region, faction, rc.WARBAND, warbands,
                piece_state=rc.HIDDEN if hidden else rc.REVEALED)
    place_piece(state, region, rc.ROMANS, rc.AUXILIA, auxilia, piece_state=rc.REVEALED)


@pytest.mark.parametrize('faction,leader,warbands,auxilia,losses', BATTLE_FACTIONS)
@pytest.mark.parametrize('condition', ['eligible', 'revealed', 'command_only',
                                      'out_of_range', 'successor_adjacent', 'caesar'])
def test_battle_gate_uses_the_legal_ambush_forecast(
        faction, leader, warbands, auxilia, losses, condition):
    state = _board(faction, sa=condition != 'command_only')
    _forces(state, rc.CARNUTES, faction, warbands, auxilia, hidden=condition != 'revealed')
    leader_region = rc.PROVINCIA if condition == 'out_of_range' else rc.BITURIGES
    own_leader = rc.SUCCESSOR if condition == 'successor_adjacent' else leader
    place_piece(state, leader_region, faction, rc.LEADER, leader_name=own_leader)
    if condition == 'caesar':
        place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
        ambush = predict_battle(state, rc.CARNUTES, faction, rc.ROMANS, is_ambush=True)
        assert ambush['taken'] >= ambush['inflicted']

    action = dispatch_bot_turn(state, faction)
    if condition != 'eligible':
        assert action['command'] == rc.CMD_MARCH
        _execute(state, faction, action)
        return

    assert (action['command'], action['sa'], action['sa_regions']) == (
        rc.CMD_BATTLE, rc.SA_AMBUSH, [rc.CARNUTES])
    result = _execute(state, faction, action)
    assert result['battles_resolved'] == [(rc.CARNUTES, rc.ROMANS)]
    assert count_pieces(state, rc.CARNUTES, faction, rc.WARBAND) == warbands
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == auxilia - losses


@pytest.mark.parametrize('faction,leader,warbands,auxilia,losses', BATTLE_FACTIONS)
@pytest.mark.parametrize('opening', ['ordinary', 'unaffordable', 'ambush'])
def test_first_affordable_battle_controls_ambush_for_the_command(
        faction, leader, warbands, auxilia, losses, opening):
    state = _board(faction, resources=1 if opening == 'unaffordable' else 10)
    place_piece(state, rc.BITURIGES, faction, rc.LEADER, leader_name=leader)
    _forces(state, rc.CARNUTES, faction, warbands, auxilia)
    if opening == 'ambush':
        place_piece(state, rc.MANDUBII, faction, rc.WARBAND, warbands)
        place_piece(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND, auxilia,
                    piece_state=rc.REVEALED)
        expected_regions = [rc.CARNUTES, rc.MANDUBII]
    else:
        place_piece(state, rc.ATREBATES, faction, rc.WARBAND, 10, piece_state=rc.REVEALED)
        assert _ally_tribe(state, rc.TRIBE_ATREBATES, rc.AEDUI)
        if opening == 'unaffordable':
            state['markers'].setdefault(rc.ATREBATES, {})[rc.MARKER_DEVASTATED] = True
        expected_regions = [rc.ATREBATES if opening == 'ordinary' else rc.CARNUTES]

    action = dispatch_bot_turn(state, faction)
    assert action['command'] == rc.CMD_BATTLE
    assert action['regions'] == expected_regions
    if opening == 'ordinary':
        assert action['sa'] != rc.SA_AMBUSH
    else:
        assert action['sa'] == rc.SA_AMBUSH and action['sa_regions'] == expected_regions
    result = _execute(state, faction, action)
    assert [region for region, _ in result['battles_resolved']] == expected_regions
    if opening != 'ordinary':
        assert count_pieces(state, rc.CARNUTES, faction, rc.WARBAND) == warbands
        assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == auxilia - losses
    if opening == 'ambush':
        assert count_pieces(state, rc.MANDUBII, faction, rc.WARBAND) == warbands
        assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == auxilia - losses


@pytest.mark.parametrize('faction,leader,warbands,auxilia,losses', BATTLE_FACTIONS)
def test_threatened_leader_can_battle_with_ambush(faction, leader, warbands, auxilia, losses):
    state = _board(faction)
    _forces(state, rc.CARNUTES, faction, warbands, 20)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.FORT)
    place_piece(state, rc.CARNUTES, faction, rc.LEADER, leader_name=leader)
    ordinary = predict_battle(state, rc.CARNUTES, faction, rc.ROMANS)
    assert ordinary['taken'] >= ordinary['inflicted'] > 0

    action = dispatch_bot_turn(state, faction)
    assert (action['command'], action['sa'], action['sa_regions']) == (
        rc.CMD_BATTLE, rc.SA_AMBUSH, [rc.CARNUTES])
    _execute(state, faction, action)
    assert count_pieces(state, rc.CARNUTES, faction, rc.LEADER) == 1
    assert count_pieces(state, rc.CARNUTES, faction, rc.WARBAND) == warbands


@pytest.mark.parametrize('faction,bot', RAID_FACTIONS)
@pytest.mark.parametrize('capability', ['owned', 'absent', 'other_owner', 'unshaded'])
def test_ordinary_raid_uses_the_owned_shaded_capacity(faction, bot, capability):
    state = _board(faction, resources=0, sa=False, seed=1)
    _forces(state, rc.CARNUTES, faction, 3, 4)
    if capability != 'absent':
        owner = faction
        if capability == 'other_owner':
            owner = rc.AEDUI if faction == rc.BELGAE else rc.BELGAE
        side = rc.EVENT_UNSHADED if capability == 'unshaded' else rc.EVENT_SHADED
        activate_capability(state, 8, side)
        set_capability_owner(state, 8, owner)
        if capability == 'unshaded':
            state['frost'] = True  # Keep the free March capability from changing the command.

    enough, restricted = bot._would_raid_gain_enough(
        state, state['scenario'], raiders={rc.CARNUTES: 2})
    assert enough and restricted == [{'region': rc.CARNUTES, 'target': None}] * 2
    expected = 3 if capability == 'owned' else 2
    action = dispatch_bot_turn(state, faction)
    assert action['command'] == rc.CMD_RAID
    assert action['details']['raid_plan'] == [{'region': rc.CARNUTES, 'target': None}] * expected
    result = _execute(state, faction, action)
    assert result['resources_gained_total'] == state['resources'][faction] == expected
    assert count_pieces_by_state(state, rc.CARNUTES, faction, rc.WARBAND, rc.HIDDEN) == 3 - expected


def test_third_german_raider_can_join_intrinsic_intimidate():
    state = _board(rc.GERMANS, resources=0, sa=False, seed=1)
    _forces(state, rc.CARNUTES, rc.GERMANS, 3, 3)
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    activate_capability(state, 8, rc.EVENT_SHADED)
    set_capability_owner(state, 8, rc.GERMANS)
    activate_capability(state, 'A22', rc.EVENT_SHADED)
    action = dispatch_bot_turn(state, rc.GERMANS)
    assert action['command'] == rc.CMD_RAID
    result = _execute(state, rc.GERMANS, action)
    assert result['raids'][0]['warbands_flipped'] == 3
    assert result['raids'][0]['raid_intimidate']['executed']
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces_by_state(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND, rc.REVEALED) == 3
