"""NP6-01 through NP6-03 at the public bot dispatcher and Battle executor."""

from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.battle.resolve import resolve_battle
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.bots.roman_bot import _has_roman_threat
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.commands.sa_rampage import rampage
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_COMMAND
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state


def _integrity(state):
    assert validate_state(state) == check_structural_integrity(state) == []


def _board(scenario=rc.SCENARIO_GREAT_REVOLT):
    state = build_initial_state(scenario, seed=6)
    state['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE,
        rc.GERMANS if scenario in rc.ARIOVISTUS_SCENARIOS else rc.ARVERNI}
    state['can_play_event'] = False
    state['_command_with_sa'] = False
    for faction in state['non_player_factions']:
        state['resources'][faction] = 10
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    return state


def _battle_board(faction, warbands, auxilia, *, scenario=rc.SCENARIO_GREAT_REVOLT,
                  leader=None, legions=0, warband_visibility=rc.REVEALED):
    state = _board(scenario)
    place_piece(state, rc.CARNUTES, faction, rc.WARBAND, warbands, piece_state=warband_visibility)
    if auxilia:
        place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, auxilia, piece_state=rc.REVEALED)
    if legions:
        place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEGION, legions, from_legions_track=True)
    if leader:
        place_piece(state, rc.CARNUTES, faction, rc.LEADER, leader_name=leader)
    _integrity(state)
    return state


def _execute(state, faction, action):
    result = execute_decision(state, faction, {'action': ACTION_COMMAND, 'bot_action': action})
    assert result['executed'] and not result.get('errors'), result
    _integrity(state)


@pytest.mark.parametrize('scenario,faction,warbands,auxilia,leader,losses,expected', [
    (rc.SCENARIO_GREAT_REVOLT, rc.BELGAE, 6, 6, None, (3, 1), rc.CMD_BATTLE),
    (rc.SCENARIO_ARIOVISTUS, rc.BELGAE, 6, 6, None, (3, 1), rc.CMD_BATTLE),
    (rc.SCENARIO_GREAT_REVOLT, rc.ARVERNI, 10, 10, None, (5, 2), rc.CMD_BATTLE),
    (rc.SCENARIO_GREAT_REVOLT, rc.BELGAE, 2, 6, rc.AMBIORIX, (3, 1), rc.CMD_BATTLE),
    (rc.SCENARIO_GREAT_REVOLT, rc.BELGAE, 2, 6, rc.SUCCESSOR, (2, 2), rc.CMD_MARCH),
    (rc.SCENARIO_GREAT_REVOLT, rc.ARVERNI, 10, 20, None, (5, 7), rc.CMD_MARCH),
])
def test_battle_forecast_uses_survivors_and_the_named_leader_rate(
        scenario, faction, warbands, auxilia, leader, losses, expected):
    state = _battle_board(faction, warbands, auxilia, scenario=scenario, leader=leader)
    trial = deepcopy(state)
    battle = resolve_battle(trial, rc.CARNUTES, faction, rc.ROMANS, retreat_declaration=False)
    assert (battle['attack']['losses_requested'], battle['counterattack']['losses_requested']) == losses
    _integrity(trial)

    action = dispatch_bot_turn(state, faction)
    assert action['command'] == expected
    _execute(state, faction, action)
    if expected == rc.CMD_BATTLE:
        assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == auxilia - losses[0]
        assert count_pieces(state, rc.CARNUTES, faction, rc.WARBAND) == warbands - losses[1]


@pytest.mark.parametrize('auxilia,expected', [(20, rc.CMD_MARCH), (0, rc.CMD_BATTLE)])
def test_arverni_legion_trigger_requires_a_loss_to_reach_the_legion(auxilia, expected):
    state = _battle_board(rc.ARVERNI, 10, auxilia, legions=1)
    action = dispatch_bot_turn(state, rc.ARVERNI)
    assert action['command'] == expected
    _execute(state, rc.ARVERNI, action)
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.LEGION) == (1 if auxilia else 0)


@pytest.mark.parametrize('fort', [True, False])
def test_aedui_fort_can_absorb_the_only_loss_ahead_of_a_human_ally(fort):
    state = _battle_board(rc.AEDUI, 4, 0)
    state['non_player_factions'].remove(rc.ROMANS)
    assert _ally_tribe(state, rc.TRIBE_CARNUTES, rc.ROMANS)
    for tribe in (rc.TRIBE_AEDUI, rc.TRIBE_VENETI):
        assert _ally_tribe(state, tribe, rc.AEDUI)
    if fort:
        place_piece(state, rc.CARNUTES, rc.ROMANS, rc.FORT)
    _integrity(state)

    asked = []

    def defend(_state, owner, request):
        if owner == rc.ROMANS and request['kind'] == 'loss_order':
            asked.append(request)
            return [(rc.FORT, None)]

    state['decision_agent'] = defend
    rng_state = state['rng'].getstate()
    action = dispatch_bot_turn(state, rc.AEDUI)
    assert not asked and state['rng'].getstate() == rng_state
    assert action['command'] == (rc.CMD_RALLY if fort else rc.CMD_BATTLE)
    _execute(state, rc.AEDUI, action)
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.ALLY) == int(fort)


@pytest.mark.parametrize('warbands,auxilia,nearby,fort,threat', [
    (3, 2, True, False, True),
    (2, 2, True, False, False),
    (2, 1, False, False, False),
    (2, 1, True, False, True),
    (2, 1, True, True, False),
])
def test_roman_threat_uses_legal_rampage_and_full_victim_capacity(
        warbands, auxilia, nearby, fort, threat):
    state = _battle_board(rc.BELGAE, warbands, auxilia, legions=3, warband_visibility=rc.HIDDEN)
    if nearby:
        place_piece(state, rc.BITURIGES, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    if fort:
        place_piece(state, rc.CARNUTES, rc.ROMANS, rc.FORT)
    _integrity(state)

    assert _has_roman_threat(state, rc.CARNUTES, state['scenario']) is threat
    if nearby and not fort:
        trial = deepcopy(state)
        victims = [{'action': 'remove', 'piece_type': rc.AUXILIA, 'piece_state': rc.REVEALED}
                   for _ in range(min(auxilia, warbands))]
        victims += [{'action': 'remove', 'piece_type': rc.LEGION}
                    for _ in range(max(0, warbands - auxilia))]
        rampage(trial, rc.CARNUTES, rc.ROMANS, warbands, victims)
        assert count_pieces(trial, rc.CARNUTES, rc.ROMANS, rc.LEGION) == 3 - int(threat)
        _integrity(trial)

    action = dispatch_bot_turn(state, rc.ROMANS)
    assert action['command'] == (rc.CMD_BATTLE if threat else rc.CMD_RECRUIT)
    _execute(state, rc.ROMANS, action)
