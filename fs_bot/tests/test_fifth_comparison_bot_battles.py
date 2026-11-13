"""NP5-01 through NP5-03 through the public bot dispatcher."""

from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.battle.resolve import resolve_battle
from fs_bot.board.pieces import count_pieces, get_leader_in_region, place_piece
from fs_bot.bots.aedui_bot import node_a4
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.bots.german_bot import _estimate_battle_losses
from fs_bot.cards.capabilities import activate_capability
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_COMMAND, ACTION_COMMAND_SA
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state


def _integrity(state):
    assert validate_state(state) == check_structural_integrity(state) == []


def _board(scenario=rc.SCENARIO_ARIOVISTUS, seed=6):
    state = build_initial_state(scenario, seed=seed)
    state['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE,
        rc.GERMANS if scenario in rc.ARIOVISTUS_SCENARIOS else rc.ARVERNI}
    state['can_play_event'] = False
    state['_command_with_sa'] = False
    state['resources'][rc.AEDUI] = 10
    if scenario in rc.ARIOVISTUS_SCENARIOS:
        state['resources'][rc.GERMANS] = 10
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    _integrity(state)
    return state


def _execute(state, faction, action):
    sop = ACTION_COMMAND_SA if state['_command_with_sa'] else ACTION_COMMAND
    result = execute_decision(state, faction, {'action': sop, 'bot_action': action})
    assert result['executed'] and not result.get('errors'), result
    _integrity(state)
    return result


def _targets(action):
    return [(row['region'], row['target']) for row in action['details']['battle_plan']]


@pytest.mark.parametrize('unrelated_warbands', [0, 10])
def test_diviciacus_safety_uses_only_the_selected_defender(unrelated_warbands):
    state = _board()
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND)
    assert _ally_tribe(state, rc.TRIBE_CARNUTES, rc.BELGAE)
    if unrelated_warbands:
        place_piece(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND, unrelated_warbands)
    _integrity(state)

    action = dispatch_bot_turn(state, rc.AEDUI)
    assert action['command'] == rc.CMD_BATTLE
    assert _targets(action) == [(rc.CARNUTES, rc.BELGAE)]
    _execute(state, rc.AEDUI, action)
    assert get_leader_in_region(state, rc.CARNUTES, rc.AEDUI) == rc.DIVICIACUS
    assert state['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] is None
    assert count_pieces(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND) == unrelated_warbands


@pytest.mark.parametrize('defender,counterattack', [(rc.ARIOVISTUS_LEADER, 2), (rc.SUCCESSOR, 1)])
def test_diviciacus_safety_counts_the_named_leader_multiplier(
        defender, counterattack):
    state = _board()
    # Prevent a Retreat from halving the one-Loss Attack to zero.
    activate_capability(state, 'A33', rc.EVENT_UNSHADED)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, piece_state=rc.REVEALED)
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.LEADER, leader_name=defender)
    place_piece(state, rc.VENETI, rc.AEDUI, rc.WARBAND, 2)
    assert _ally_tribe(state, rc.TRIBE_VENETI, rc.BELGAE)
    _integrity(state)
    witness = resolve_battle(deepcopy(state), rc.CARNUTES, rc.AEDUI, rc.GERMANS,
                             retreat_declaration=False)
    assert witness['counterattack']['losses_requested'] == counterattack

    action = dispatch_bot_turn(state, rc.AEDUI)
    expected = [(rc.VENETI, rc.BELGAE)]
    if defender == rc.SUCCESSOR:
        expected.insert(0, (rc.CARNUTES, rc.GERMANS))
    assert _targets(action) == expected
    _execute(state, rc.AEDUI, action)
    assert get_leader_in_region(state, rc.CARNUTES, rc.AEDUI) == rc.DIVICIACUS


def test_unsafe_high_value_battle_falls_through_to_rally():
    state = _board()
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 2, piece_state=rc.REVEALED)
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    # Motivation adds one Loss to Ariovistus's two when he survives the Attack.
    activate_capability(state, 'A33', rc.EVENT_SHADED)
    place_piece(state, rc.VENETI, rc.AEDUI, rc.WARBAND, 2)
    _integrity(state)
    witness = resolve_battle(deepcopy(state), rc.CARNUTES, rc.AEDUI, rc.GERMANS,
                             retreat_declaration=False)
    assert witness['counterattack']['losses_requested'] == 3

    assert node_a4(state) == 'No'
    action = dispatch_bot_turn(state, rc.AEDUI)
    assert action['command'] == rc.CMD_RALLY
    _execute(state, rc.AEDUI, action)
    assert state['tribes'][rc.TRIBE_VENETI]['allied_faction'] == rc.AEDUI
    assert get_leader_in_region(state, rc.CARNUTES, rc.AEDUI) == rc.DIVICIACUS


@pytest.mark.parametrize('defending_warbands,ally,safe', [
    (2, False, True), (3, True, True), (3, False, False),
])
def test_diviciacus_safety_accounts_for_attack_casualties_and_own_allies(
        defending_warbands, ally, safe):
    state = _board()
    activate_capability(state, 'A33', rc.EVENT_UNSHADED)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND, defending_warbands)
    if ally:
        assert _ally_tribe(state, rc.TRIBE_AULERCI, rc.AEDUI)
    place_piece(state, rc.VENETI, rc.AEDUI, rc.WARBAND, 2)
    assert _ally_tribe(state, rc.TRIBE_VENETI, rc.BELGAE)
    _integrity(state)

    action = dispatch_bot_turn(state, rc.AEDUI)
    expected = [(rc.VENETI, rc.BELGAE)]
    if safe:
        expected.append((rc.CARNUTES, rc.GERMANS))
    assert _targets(action) == expected
    _execute(state, rc.AEDUI, action)
    assert get_leader_in_region(state, rc.CARNUTES, rc.AEDUI) == rc.DIVICIACUS


@pytest.mark.parametrize('player_defends', [False, True])
def test_diviciacus_safety_accounts_for_the_players_legal_saving_rolls(player_defends):
    # Three Attack Losses match the NPC's three-Loss Counterattack. A player
    # can absorb all three with the Ariovistus Leader and counter for six.
    state = _board(seed=11)
    if player_defends:
        state['non_player_factions'].remove(rc.GERMANS)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 4, piece_state=rc.REVEALED)
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND, 4)
    place_piece(state, rc.VENETI, rc.AEDUI, rc.WARBAND, 2)
    assert _ally_tribe(state, rc.TRIBE_VENETI, rc.BELGAE)
    _integrity(state)

    witness = resolve_battle(
        deepcopy(state), rc.CARNUTES, rc.AEDUI, rc.GERMANS,
        retreat_declaration=False, attack_loss_order=[(rc.LEADER, None)] if player_defends else None)
    assert witness['counterattack']['losses_requested'] == (6 if player_defends else 3)
    action = dispatch_bot_turn(state, rc.AEDUI)
    expected = [(rc.VENETI, rc.BELGAE)]
    if not player_defends:
        expected.append((rc.CARNUTES, rc.GERMANS))
    assert _targets(action) == expected
    _execute(state, rc.AEDUI, action)
    assert get_leader_in_region(state, rc.CARNUTES, rc.AEDUI) == rc.DIVICIACUS


@pytest.mark.parametrize('earlier_ambush', [False, True])
def test_diviciacus_can_rely_on_the_actual_ambush_region_only(earlier_ambush):
    state = _board()
    state['_command_with_sa'] = True
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND)
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    if earlier_ambush:
        place_piece(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND, 4)
        place_piece(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, piece_state=rc.REVEALED)
        assert _ally_tribe(state, rc.TRIBE_ATREBATES, rc.BELGAE)
    _integrity(state)

    action = dispatch_bot_turn(state, rc.AEDUI)
    target = (rc.ATREBATES, rc.BELGAE) if earlier_ambush else (rc.CARNUTES, rc.GERMANS)
    assert _targets(action) == [target]
    assert action['sa'] == rc.SA_AMBUSH and action['sa_regions'] == [target[0]]
    _execute(state, rc.AEDUI, action)
    assert get_leader_in_region(state, rc.CARNUTES, rc.AEDUI) == rc.DIVICIACUS


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
@pytest.mark.parametrize('defending_ally', [False, True])
def test_aedui_trigger_requires_a_real_high_value_target(scenario, defending_ally):
    state = _board(scenario)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 8)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    if defending_ally:
        assert _ally_tribe(state, rc.TRIBE_CARNUTES, rc.BELGAE)
    _integrity(state)

    assert node_a4(state) == ('Yes' if defending_ally else 'No')
    action = dispatch_bot_turn(state, rc.AEDUI)
    assert action['command'] == (rc.CMD_BATTLE if defending_ally else rc.CMD_RALLY)
    _execute(state, rc.AEDUI, action)
    assert state['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] == (
        None if defending_ally else rc.AEDUI)


@pytest.mark.parametrize('auxilia,warbands,leader,losses,command', [
    (4, 6, None, (3, 0), rc.CMD_BATTLE),
    (6, 6, None, (3, 1), rc.CMD_BATTLE),
    (12, 6, None, (3, 4), rc.CMD_MARCH),
    (6, 4, rc.ARIOVISTUS_LEADER, (6, 0), rc.CMD_BATTLE),
    (6, 6, rc.SUCCESSOR, (4, 1), rc.CMD_BATTLE),
])
def test_german_forecast_uses_post_attack_survivors_and_the_correct_leader(
        auxilia, warbands, leader, losses, command):
    state = _board()
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND, warbands, piece_state=rc.REVEALED)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, auxilia, piece_state=rc.REVEALED)
    if leader:
        place_piece(state, rc.CARNUTES, rc.GERMANS, rc.LEADER, leader_name=leader)
    _integrity(state)
    trial = deepcopy(state)
    result = resolve_battle(trial, rc.CARNUTES, rc.GERMANS, rc.ROMANS, retreat_declaration=False)
    _integrity(trial)
    assert (result['attack']['losses_requested'], result['counterattack']['losses_requested']) == losses
    rng_state = state['rng'].getstate()

    estimate = _estimate_battle_losses(state, rc.CARNUTES, rc.ROMANS)
    assert state['rng'].getstate() == rng_state
    action = dispatch_bot_turn(state, rc.GERMANS)
    assert (action['command'], estimate) == (command, losses)
    _execute(state, rc.GERMANS, action)
    if command == rc.CMD_BATTLE:
        assert _targets(action) == [(rc.CARNUTES, rc.ROMANS)]
        assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == auxilia - losses[0]
        assert count_pieces(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND) == warbands - losses[1]
