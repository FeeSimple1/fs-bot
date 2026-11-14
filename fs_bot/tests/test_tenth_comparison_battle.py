"""A34 Battle planning with active and canceled Abatis (BM10-01, BM11-01)."""

import pytest

from fs_bot import rules_consts as rc
from fs_bot.battle.losses import calculate_losses
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.bots.bot_common import predict_battle
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.engine.agent import LOSS_ORDER, RETREAT, RETREAT_DISPOSITION
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state
from fs_bot.tools.seat_session import validate_response


REGION = rc.CARNUTES


def play_event(state, card, actor, *, shaded=False, **params):
    state['current_card'] = state['current_card_id'] = card
    action = {'action': ACTION_EVENT, 'player_action': {
        'command': rc.FIRST_DID_EVENT, 'details': {
            'card_id': card, 'text_preference': rc.EVENT_SHADED if shaded else rc.EVENT_UNSHADED,
            'event_params': params,
        },
    }}
    validate_response(state, {'kind': 'turn', 'faction': actor, 'options': [ACTION_EVENT]}, action)
    result = execute_decision(state, actor, action)
    assert result['executed'] and not result.get('errors'), result
    assert validate_state(state) == check_structural_integrity(state) == []
    return result


def position(*, abatis=True, stalwart=True, citadel=False, leader=True, warbands=2):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=13)
    state['non_player_factions'] = {rc.AEDUI}
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    if leader:
        place_piece(state, REGION, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    place_piece(state, REGION, rc.GERMANS, rc.WARBAND, warbands)
    place_piece(state, REGION, rc.BELGAE, rc.WARBAND, 2)
    assert _ally_tribe(state, rc.TRIBE_AULERCI, rc.BELGAE)
    if citadel:
        assert _ally_tribe(state, rc.TRIBE_CARNUTES, rc.BELGAE, citadel=True)
    if abatis:
        play_event(state, 'A64', rc.BELGAE, region=REGION)
    if stalwart:
        play_event(state, 'A31', rc.GERMANS, shaded=True)
    assert validate_state(state) == check_structural_integrity(state) == []
    return state


def forecast(state, retreat):
    return calculate_losses(state, REGION, rc.GERMANS, rc.BELGAE, is_retreat=retreat)


@pytest.mark.parametrize('retreat,expected', [(False, 4), (True, 2)])
def test_aedui_divination_battles_through_cancelled_abatis(retreat, expected):
    state = position()
    before = encode(state)
    estimate = forecast(state, retreat)
    prediction = predict_battle(state, REGION, rc.GERMANS, rc.BELGAE, is_retreat=retreat)
    assert encode(state) == before
    losses = []

    def defend(_board, faction, request):
        if faction == rc.BELGAE:
            if request['kind'] == RETREAT:
                return {'retreat': retreat}
            if request['kind'] == LOSS_ORDER:
                losses.append(request['num_losses'])
            if request['kind'] == RETREAT_DISPOSITION:
                return {'region': None, 'stay_leader': False, 'stay_hidden_warbands': 0}

    state['decision_agent'] = defend
    result = play_event(state, 'A34', rc.ROMANS, faction=rc.AEDUI)['free_actions'][0]
    assert result['chooser'] == rc.AEDUI and result['acting_faction'] == rc.GERMANS
    assert result['result']['command'] == rc.CMD_BATTLE
    assert result['result']['battles_resolved'] == [(REGION, rc.BELGAE)]
    assert not result['result']['battle_sa_executed']
    assert losses[0] == prediction['inflicted'] == estimate == expected
    assert state['tribes'][rc.TRIBE_AULERCI]['allied_faction'] is None
    assert state['markers'][REGION][rc.MARKER_ABATIS] == rc.BELGAE


@pytest.mark.parametrize('conditions,expected,command', [
    ({'stalwart': False}, (1, 1), rc.CMD_MARCH),
    ({'citadel': True}, (1, 1), rc.CMD_MARCH),
    ({'leader': False}, (1, 0), rc.CMD_MARCH),
    ({'abatis': False}, (4, 2), rc.CMD_BATTLE),
])
def test_divination_retains_ariovistus_and_fortification_rules(conditions, expected, command):
    state = position(**conditions)
    assert tuple(forecast(state, retreat) for retreat in (False, True)) == expected
    result = play_event(state, 'A34', rc.ROMANS, faction=rc.AEDUI)['free_actions'][0]['result']
    assert result['executed'] and not result.get('errors'), result
    assert result['command'] == command
    if command == rc.CMD_MARCH:
        assert count_pieces(state, REGION, rc.BELGAE, rc.WARBAND) == 2
        assert state['tribes'][rc.TRIBE_AULERCI]['allied_faction'] == rc.BELGAE
    else:
        assert state['tribes'][rc.TRIBE_AULERCI]['allied_faction'] is None


@pytest.mark.parametrize('leader,warbands', [(True, 10), (False, 12)])
def test_aedui_divination_marches_when_abatis_can_spare_ally(leader, warbands):
    state = position(stalwart=False, leader=leader, warbands=warbands)
    state['resources'][rc.GERMANS] = 20
    assert forecast(state, False) == 3
    defender_requests = []

    def defend(_board, faction, request):
        if faction == rc.BELGAE and request['kind'] in (RETREAT, LOSS_ORDER):
            defender_requests.append(request['kind'])

    state['decision_agent'] = defend
    action = play_event(state, 'A34', rc.ROMANS, faction=rc.AEDUI)['free_actions'][0]
    assert action['chooser'] == rc.AEDUI and action['acting_faction'] == rc.GERMANS
    assert action['result']['executed'] and action['result']['command'] == rc.CMD_MARCH
    assert defender_requests == []
    assert state['resources'][rc.GERMANS] == 20
    assert count_pieces(state, REGION, rc.BELGAE, rc.WARBAND) == 2
    assert state['tribes'][rc.TRIBE_AULERCI]['allied_faction'] == rc.BELGAE
    assert state['markers'][REGION][rc.MARKER_ABATIS] == rc.BELGAE


def test_aedui_divination_prioritizes_forced_ally_over_abatis_defense():
    state = position(stalwart=False, warbands=10)
    assert _ally_tribe(state, rc.TRIBE_CARNUTES, rc.ARVERNI)
    assert validate_state(state) == check_structural_integrity(state) == []

    result = play_event(state, 'A34', rc.ROMANS, faction=rc.AEDUI)['free_actions'][0]['result']
    assert result['executed'] and result['command'] == rc.CMD_BATTLE
    assert result['battles_resolved'] == [(REGION, rc.ARVERNI)]
    assert not result['battle_sa_executed']
    assert state['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] is None
    assert count_pieces(state, REGION, rc.BELGAE, rc.WARBAND) == 2
    assert state['tribes'][rc.TRIBE_AULERCI]['allied_faction'] == rc.BELGAE
