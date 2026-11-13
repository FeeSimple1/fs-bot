"""Round-four Battle and Non-player priority regressions."""

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, get_leader_in_region, place_piece,
)
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.cards.capabilities import activate_capability
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.engine.execute import _decide_defender_retreat, execute_decision
from fs_bot.engine.game_engine import ACTION_COMMAND, ACTION_COMMAND_SA
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import (
    build_initial_state, check_structural_integrity, validate_state,
)
from fs_bot.tools.seat_session import validate_response


def _board(scenario, *, seed=1, non_players=()):
    state = build_initial_state(scenario, seed=seed)
    state['non_player_factions'] = set(non_players)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    return state


def _assert_integrity(state):
    assert validate_state(state) == check_structural_integrity(state) == []


def _human_battle(state, attacker, defender):
    _assert_integrity(state)
    state['resources'][attacker] = 20
    response = {'action': ACTION_COMMAND, 'player_action': {
        'command': rc.CMD_BATTLE, 'sa': 'No SA', 'regions': [rc.CARNUTES],
        'details': {'battle_plan': [{'region': rc.CARNUTES, 'target': defender}]},
    }}
    validate_response(state, {'kind': 'turn', 'faction': attacker,
                              'options': [ACTION_COMMAND]}, response)
    result = execute_decision(state, attacker, response)
    assert result['executed'] and not result.get('errors'), result
    _assert_integrity(state)


@pytest.mark.parametrize('german_warbands,settlement,belgic_survivors', [
    (2, False, 8), (3, False, 7), (2, True, 7),
])
def test_motivation_requires_a_surviving_defending_force(
        german_warbands, settlement, belgic_survivors):
    state = _board(rc.SCENARIO_ARIOVISTUS)
    activate_capability(state, 'A33', rc.EVENT_SHADED)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 8)
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND, german_warbands)
    if settlement:
        place_piece(state, rc.CARNUTES, rc.GERMANS, rc.SETTLEMENT)

    _human_battle(state, rc.BELGAE, rc.GERMANS)

    assert count_pieces(state, rc.CARNUTES, rc.GERMANS) == german_warbands - 2 + int(settlement)
    assert count_pieces(state, rc.CARNUTES, rc.BELGAE) == belgic_survivors


@pytest.mark.parametrize('defenders,remaining,refuge,attackers', [
    (6, 0, 5, 8), (4, 0, 3, 8), (8, 4, 1, 6),
])
def test_guaranteed_counterattack_counts_only_surviving_defenders(
        defenders, remaining, refuge, attackers):
    state = _board(rc.SCENARIO_GREAT_REVOLT, non_players=(rc.AEDUI,))
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 8)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, defenders)
    place_piece(state, rc.VENETI, rc.AEDUI, rc.WARBAND)
    before = encode(state)

    assert _decide_defender_retreat(
        state, rc.CARNUTES, rc.BELGAE, rc.AEDUI, False
    ) == ((True, rc.VENETI) if not remaining else (False, None))
    assert encode(state) == before
    _human_battle(state, rc.BELGAE, rc.AEDUI)

    assert count_pieces(state, rc.CARNUTES, rc.AEDUI) == remaining
    assert count_pieces(state, rc.VENETI, rc.AEDUI) == refuge
    assert count_pieces(state, rc.CARNUTES, rc.BELGAE) == attackers


@pytest.mark.parametrize('warbands,visibility,retreats', [
    (2, rc.HIDDEN, True), (2, rc.REVEALED, False), (1, rc.REVEALED, False),
])
def test_retreat_without_destination_can_save_hidden_defender(warbands, visibility, retreats):
    state = _board(rc.SCENARIO_GREAT_REVOLT, non_players=(rc.AEDUI,))
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, warbands, piece_state=visibility)
    before = encode(state)

    assert _decide_defender_retreat(
        state, rc.CARNUTES, rc.ROMANS, rc.AEDUI, False
    ) == (retreats, None)
    assert encode(state) == before
    _human_battle(state, rc.ROMANS, rc.AEDUI)

    assert count_pieces(state, rc.CARNUTES, rc.AEDUI) == int(retreats)
    assert count_pieces_by_state(
        state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == (0 if retreats else 4)


def test_a_saving_roll_cannot_make_a_no_destination_retreat_lossless():
    state = _board(rc.SCENARIO_GREAT_REVOLT, non_players=(rc.BELGAE,))
    # Even if the lone Leader saves against the Attack, a Gallic attacker
    # prevents him from staying in the Region at Step 6.
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 4)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    _assert_integrity(state)
    assert _decide_defender_retreat(
        state, rc.CARNUTES, rc.ARVERNI, rc.BELGAE, False
    ) == (False, None)


def _bot_board():
    state = _board(rc.SCENARIO_ARIOVISTUS, seed=5,
                   non_players=(rc.ROMANS, rc.AEDUI, rc.BELGAE, rc.GERMANS))
    state['can_play_event'] = False
    state['resources'][rc.ROMANS] = 30
    state['resources'][rc.AEDUI] = 10
    return state


@pytest.mark.parametrize('settlements,expected_enemy', [(True, rc.GERMANS), (False, rc.AEDUI)])
def test_roman_march_ranks_the_factions_total_including_settlements(settlements, expected_enemy):
    state = _bot_board()
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION, 4, from_legions_track=True)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 17)
    _ally_tribe(state, rc.TRIBE_CARNUTES, rc.AEDUI)
    _ally_tribe(state, rc.TRIBE_AULERCI, rc.AEDUI)
    _ally_tribe(state, rc.TRIBE_SEQUANI, rc.GERMANS)
    if settlements:
        for region in (rc.SEQUANI, rc.TREVERI):
            place_piece(state, region, rc.GERMANS, rc.SETTLEMENT)
    _assert_integrity(state)

    action = dispatch_bot_turn(state, rc.ROMANS)
    assert action['command'] == rc.CMD_MARCH
    destination, enemy = action['details']['destinations'][0]
    assert enemy == expected_enemy
    result = execute_decision(state, rc.ROMANS, {'action': ACTION_COMMAND_SA,
                                                'bot_action': action})
    assert result['executed'] and not result.get('errors'), result
    assert count_pieces(state, destination, rc.ROMANS, rc.LEGION) == 4
    _assert_integrity(state)


def test_roman_battle_uses_the_same_total_when_ranking_enemies():
    state = _bot_board()
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEGION, 4, from_legions_track=True)
    _ally_tribe(state, rc.TRIBE_CARNUTES, rc.AEDUI)
    _ally_tribe(state, rc.TRIBE_AEDUI, rc.AEDUI)
    _ally_tribe(state, rc.TRIBE_AULERCI, rc.GERMANS)
    for region in (rc.SEQUANI, rc.TREVERI):
        place_piece(state, region, rc.GERMANS, rc.SETTLEMENT)
    _assert_integrity(state)

    action = dispatch_bot_turn(state, rc.ROMANS)
    assert action['command'] == rc.CMD_BATTLE
    assert action['details']['battle_plan'][0]['targets'] == [rc.GERMANS, rc.AEDUI]


@pytest.mark.parametrize('support', [0, 1])
def test_aedui_bot_battles_with_diviciacus_when_counterattack_cannot_reach_him(support):
    state = _bot_board()
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    if support:
        place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, support)
    _ally_tribe(state, rc.TRIBE_CARNUTES, rc.BELGAE)
    _assert_integrity(state)

    action = dispatch_bot_turn(state, rc.AEDUI)
    assert action['command'] == rc.CMD_BATTLE
    result = execute_decision(state, rc.AEDUI, {'action': ACTION_COMMAND_SA,
                                               'bot_action': action})
    assert result['executed'] and not result.get('errors'), result
    assert get_leader_in_region(state, rc.CARNUTES, rc.AEDUI) == rc.DIVICIACUS
    assert state['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] is None
    _assert_integrity(state)


@pytest.mark.parametrize('support', [0, 1])
def test_diviciacus_safety_also_applies_to_additional_battles(support):
    state = _bot_board()
    state['_command_with_sa'] = False
    # A33 prevents a Retreat from reducing this one-Loss Attack to zero.
    activate_capability(state, 'A33', rc.EVENT_UNSHADED)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    if support:
        place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, support)
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND, 3, piece_state=rc.REVEALED)
    place_piece(state, rc.VENETI, rc.AEDUI, rc.WARBAND, 2)
    _ally_tribe(state, rc.TRIBE_VENETI, rc.BELGAE)
    _assert_integrity(state)

    action = dispatch_bot_turn(state, rc.AEDUI)
    assert action['command'] == rc.CMD_BATTLE
    assert [(row['region'], row['priority']) for row in action['details']['battle_plan']] == (
        [(rc.VENETI, 'high_value'), (rc.CARNUTES, 'favorable')] if support
        else [(rc.VENETI, 'high_value')]
    )
