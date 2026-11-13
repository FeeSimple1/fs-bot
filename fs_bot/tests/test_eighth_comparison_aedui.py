"""NP8-01 and NP8-02 through public dispatch and execution."""

from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.cards.capabilities import activate_capability, set_capability_owner
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cli.dispatcher import make_decision_func
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import (
    ACTION_COMMAND, ACTION_COMMAND_SA, ACTION_EVENT, ACTION_LIMITED_COMMAND,
    ACTION_PASS, resolve_card_turn,
)
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state


def _board(*, scenario=rc.SCENARIO_GREAT_REVOLT, resources=10, with_sa=True):
    state = build_initial_state(scenario, seed=6)
    state['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE,
        rc.GERMANS if scenario in rc.ARIOVISTUS_SCENARIOS else rc.ARVERNI}
    state['can_play_event'] = False
    state['_command_with_sa'] = with_sa
    state['resources'].update({faction: 10 for faction in state['non_player_factions']})
    state['resources'][rc.AEDUI] = resources
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    return state


def _integrity(state):
    assert validate_state(state) == check_structural_integrity(state) == []


def _execute(state, action):
    _integrity(state)
    result = execute_decision(state, rc.AEDUI, {
        'action': ACTION_COMMAND if action['sa'] == 'No SA' else ACTION_COMMAND_SA,
        'bot_action': action,
    })
    assert result['executed'] and not result['errors'], result
    _integrity(state)
    return result


def _opening_battle(state, warbands=2):
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, warbands, piece_state=rc.REVEALED)
    assert _ally_tribe(state, rc.TRIBE_CARNUTES, rc.BELGAE)


def _additional_battle(state, defenders, enemy=rc.BELGAE):
    place_piece(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND, 4, piece_state=rc.REVEALED)
    place_piece(state, rc.AEDUI_REGION, enemy, rc.WARBAND, defenders, piece_state=rc.REVEALED)


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
@pytest.mark.parametrize('defenders,resources,player,own_after,enemy_after', [
    (4, 10, False, 3, 2),
    (6, 10, False, 2, 4),
    (6, 10, True, 2, 4),
    (8, 10, False, 4, 8),
    (6, 1, False, 4, 6),
])
def test_additional_battle_counts_only_surviving_defenders(
        scenario, defenders, resources, player, own_after, enemy_after):
    state = _board(scenario=scenario, resources=resources, with_sa=False)
    if player:
        state['non_player_factions'].remove(rc.BELGAE)
    _opening_battle(state)
    _additional_battle(state, defenders)

    action = dispatch_bot_turn(state, rc.AEDUI)
    expected = [rc.CARNUTES, rc.AEDUI_REGION] if enemy_after < defenders else [rc.CARNUTES]
    assert action['command'] == rc.CMD_BATTLE
    assert [entry['region'] for entry in action['details']['battle_plan']] == expected
    result = _execute(state, action)
    assert result['battles_resolved'] == [(region, rc.BELGAE) for region in expected]
    assert count_pieces(state, rc.CARNUTES, rc.BELGAE, rc.ALLY) == 0
    assert count_pieces(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == own_after
    assert count_pieces(state, rc.AEDUI_REGION, rc.BELGAE, rc.WARBAND) == enemy_after
    assert state['resources'][rc.AEDUI] == resources - len(expected)


@pytest.mark.parametrize('with_sa', [False, True])
def test_additional_battles_check_retreat_and_only_one_ambush(with_sa):
    state = _board(with_sa=with_sa)
    _opening_battle(state)
    for region in (rc.MANDUBII, rc.AEDUI_REGION):
        place_piece(state, region, rc.AEDUI, rc.WARBAND, 2)
        place_piece(state, region, rc.BELGAE, rc.WARBAND, 3, piece_state=rc.REVEALED)

    action = dispatch_bot_turn(state, rc.AEDUI)
    expected = [rc.CARNUTES, rc.MANDUBII] if with_sa else [rc.CARNUTES]
    assert [entry['region'] for entry in action['details']['battle_plan']] == expected
    assert action['sa'] == (rc.SA_AMBUSH if with_sa else 'No SA')
    assert action['sa_regions'] == ([rc.MANDUBII] if with_sa else [])
    result = _execute(state, action)
    assert result['battles_resolved'] == [(region, rc.BELGAE) for region in expected]
    assert result['battle_sa_executed'] is with_sa
    assert count_pieces(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND) == (2 if with_sa else 3)
    assert count_pieces(state, rc.AEDUI_REGION, rc.BELGAE, rc.WARBAND) == 3


@pytest.mark.parametrize('opening_slingers', [False, True])
def test_additional_battle_forecasts_slingers_once_per_command(opening_slingers):
    state = _board(with_sa=False)
    _opening_battle(state, warbands=4)
    _additional_battle(state, 6)
    activate_capability(state, 13, rc.EVENT_UNSHADED)
    place_piece(state, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA, 2)
    if opening_slingers:
        place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 2)

    action = dispatch_bot_turn(state, rc.AEDUI)
    expected = [rc.CARNUTES, rc.AEDUI_REGION] if opening_slingers else [rc.CARNUTES]
    assert [entry['region'] for entry in action['details']['battle_plan']] == expected
    result = _execute(state, action)
    assert result['battles_resolved'] == [(region, rc.BELGAE) for region in expected]
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == (3 if opening_slingers else 4)
    assert count_pieces(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == (2 if opening_slingers else 4)


@pytest.mark.parametrize('player', [False, True])
def test_additional_battle_forecasts_defensive_horse_use(player):
    state = _board(with_sa=False)
    if player:
        state['non_player_factions'].remove(rc.BELGAE)
    _opening_battle(state)
    _additional_battle(state, 6)
    activate_capability(state, 59, rc.EVENT_SHADED)
    set_capability_owner(state, 59, rc.BELGAE)

    action = dispatch_bot_turn(state, rc.AEDUI)
    expected = [rc.CARNUTES] if player else [rc.CARNUTES, rc.AEDUI_REGION]
    assert [entry['region'] for entry in action['details']['battle_plan']] == expected
    _execute(state, action)
    assert count_pieces(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == (4 if player else 2)


@pytest.mark.parametrize('archers', [False, True])
def test_additional_battle_forecasts_archers_before_the_attack(archers):
    state = _board(with_sa=False)
    _opening_battle(state)
    _additional_battle(state, 6, rc.ARVERNI)
    if archers:
        activate_capability(state, 27, rc.EVENT_SHADED)

    action = dispatch_bot_turn(state, rc.AEDUI)
    expected = [rc.CARNUTES] if archers else [rc.CARNUTES, rc.AEDUI_REGION]
    assert [entry['region'] for entry in action['details']['battle_plan']] == expected
    _execute(state, action)
    assert count_pieces(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == (4 if archers else 2)


@pytest.mark.parametrize('with_sa,resources,initial,allies,warbands,remaining', [
    (True, 10, 0, 1, 3, 5),
    (True, 10, 1, 1, 4, 6),
    (False, 10, 0, 0, 1, 9),
    (True, 1, 0, 0, 1, 0),
])
def test_rally_forecasts_suborn_after_placing_the_first_hidden_warband(
        with_sa, resources, initial, allies, warbands, remaining):
    state = _board(resources=resources, with_sa=with_sa)
    if initial:
        place_piece(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND, initial)
    action = dispatch_bot_turn(state, rc.AEDUI)
    assert action['command'] == rc.CMD_RALLY
    assert action['sa'] == (rc.SA_SUBORN if allies else 'No SA')
    assert count_pieces(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == initial
    assert state['resources'][rc.AEDUI] == resources
    result = _execute(state, action)
    if allies:
        assert result['sa_execution']['executed'] and result['sa_execution']['rederived_at_sa_time']
        assert result['sa_execution']['sa'] == rc.SA_SUBORN
        assert result['sa_timing'] == 'after'
    else:
        assert 'sa_execution' not in result
    assert count_pieces(state, rc.AEDUI_REGION, rc.AEDUI, rc.ALLY) == allies
    assert count_pieces(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == warbands
    assert state['resources'][rc.AEDUI] == remaining


@pytest.mark.parametrize('resources', [1, 10])
def test_rally_records_suborn_in_the_sequence_of_play(resources):
    state = _board(resources=resources)
    state['current_card'] = 37  # Aedui are first on Boii and decline it here.
    _integrity(state)
    bot_decide = make_decision_func({}, stdout=StringIO(), pause=False)
    offers = []

    def decide(board, faction, options, position):
        if faction == rc.AEDUI:
            return bot_decide(board, faction, options, position)
        offers.append(options)
        return {'action': ACTION_PASS}

    result = resolve_card_turn(state, decide, execute=True)
    record = result['actions_taken'][rc.AEDUI]
    assert record['execution']['command'] == rc.CMD_RALLY
    assert record['action'] == (ACTION_COMMAND_SA if resources == 10 else ACTION_COMMAND)
    assert offers and all(ACTION_LIMITED_COMMAND in options for options in offers)
    assert all((ACTION_EVENT in options) == (resources == 10) for options in offers)
    _integrity(state)


def test_human_rally_without_an_sa_does_not_suborn():
    state = _board()
    state['non_player_factions'].remove(rc.AEDUI)
    result = execute_decision(state, rc.AEDUI, {'action': ACTION_COMMAND, 'player_action': {
        'command': rc.CMD_RALLY, 'sa': 'No SA', 'regions': [rc.AEDUI_REGION],
        'details': {'rally_plan': {'warbands': [rc.AEDUI_REGION]}},
    }})
    assert result['executed'] and not result['errors']
    assert 'sa_execution' not in result
    assert count_pieces(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == 1
    assert state['resources'][rc.AEDUI] == 9
    _integrity(state)


@pytest.mark.parametrize('roman_agrees', [False, True])
def test_rally_spending_unlocks_trade_and_uses_live_roman_agreement(roman_agrees):
    state = _board()
    state['non_player_factions'].remove(rc.ROMANS)
    for region, tribe in ((rc.AEDUI_REGION, rc.TRIBE_AEDUI),
                          (rc.BITURIGES, rc.TRIBE_BITURIGES)):
        assert _ally_tribe(state, tribe, rc.AEDUI)
        place_piece(state, region, rc.AEDUI, rc.WARBAND)
    declarations = []

    def agent(board, faction, request):
        if request.get('request_type') == 'trade_roman_agreement':
            assert board is state and faction == rc.ROMANS
            declarations.append(state['resources'][rc.AEDUI])
            return roman_agrees
        return None

    state['decision_agent'] = agent
    rng_before = state['rng'].getstate()
    action = dispatch_bot_turn(state, rc.AEDUI)
    assert action['command'] == rc.CMD_RALLY and action['sa'] == rc.SA_TRADE
    assert action['details']['sa_details']['trade_resources'] == 4
    assert declarations == [] and state['rng'].getstate() == rng_before
    result = _execute(state, action)
    assert declarations == [8]
    assert result['sa_execution']['executed']
    assert result['sa_execution']['sa'] == (rc.SA_TRADE if roman_agrees else rc.SA_SUBORN)
    if roman_agrees:
        assert result['sa_execution']['result']['resources_gained'] == 4
        assert state['resources'][rc.AEDUI] == 12


@pytest.mark.parametrize('other_region', [None, rc.MANDUBII])
def test_druids_forecasts_suborn_after_the_retained_rally_region(other_region):
    from fs_bot.cards.gallic_event_grants import resolve_druids

    state = _board()
    if other_region is not None:
        assert _ally_tribe(state, rc.TRIBE_MANDUBII, rc.AEDUI)
    _integrity(state)
    [grant] = resolve_druids(state, [rc.AEDUI])
    result = grant['result']
    assert result['executed'] and not result['errors']
    assert [entry['region'] for entry in result['placements']] == [other_region or rc.AEDUI_REGION]
    if other_region is None:
        assert result['sa_execution']['executed'] and result['sa_execution']['sa'] == rc.SA_SUBORN
        assert count_pieces(state, rc.AEDUI_REGION, rc.AEDUI, rc.ALLY) == 1
        assert count_pieces(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == 3
    else:
        assert 'sa_execution' not in result
        assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.CITADEL) == 1
        assert count_pieces(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == 0
    assert state['resources'][rc.AEDUI] == 10
    _integrity(state)
