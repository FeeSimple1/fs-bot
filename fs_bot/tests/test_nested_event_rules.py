"""Rules defects exposed by recursively auditing Event-granted actions."""
import random

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, count_pieces_by_state, get_available
from fs_bot.engine.execute import _execute_event
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.error_census import census_result
from collections import Counter


def _state(card):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=19)
    state['current_card'] = card
    state['non_player_factions'] = set()
    return state


def _event(state, faction, params=None):
    result = _execute_event(state, faction, {'command': 'Event', 'sa': 'No SA',
        'sa_regions': [], 'details': {'card_id': state['current_card'],
            'text_preference': rc.EVENT_SHADED, 'event_params': params or {}}}, human=True)
    assert result['executed']
    assert validate_state(state) == []
    counts, examples, occurrences = Counter(), {}, []
    census_result({'card_results': [{'card': state['current_card'], 'turn_result': {
        'actions_taken': {faction: {'bot_action': {'command': 'Event'},
                                    'execution': result}}}}]}, counts, examples,
                  state['scenario'], 19, occurrences)
    assert not [row for row in occurrences if row['severity'] == 'illegal']
    return result['free_actions']


def _bellovaci(state, leader_region):
    place_piece(state, rc.ATREBATES, rc.BELGAE, rc.ALLY)
    state['tribes'][rc.TRIBE_BELLOVACI]['allied_faction'] = rc.BELGAE
    if leader_region:
        place_piece(state, leader_region, rc.BELGAE, rc.LEADER,
                    leader_name=rc.BODUOGNATUS)


@pytest.mark.parametrize('leader_region', [None, rc.PROVINCIA])
def test_a69_keeps_placements_but_never_falls_back_to_battle_without_legal_ambush(leader_region):
    state = _state('A69')
    _bellovaci(state, leader_region)
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, 4, piece_state=rc.REVEALED)
    actions = _event(state, rc.BELGAE)
    assert count_pieces(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND) == 6
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 4
    assert actions[0]['declined_no_effect']
    assert count_pieces_by_state(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, rc.HIDDEN) == 6


@pytest.mark.parametrize('placed,fort,expected_losses', [(6, False, 8), (1, False, 3), (1, True, 1)])
def test_a69_only_new_warbands_gain_full_loss_residents_and_fort_use_normal_rules(placed, fort, expected_losses):
    state = _state('A69')
    _bellovaci(state, rc.NERVII)  # adjacent Leader validates Ambush, contributes no Loss
    place_piece(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 4)
    if placed < 6:
        place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND,
                    get_available(state, rc.BELGAE, rc.WARBAND) - placed)
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, 12, piece_state=rc.REVEALED)
    if fort:
        place_piece(state, rc.ATREBATES, rc.ROMANS, rc.FORT)
    actions = _event(state, rc.BELGAE)
    assert actions[0]['defender'] == rc.ROMANS
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 12 - expected_losses
    assert count_pieces_by_state(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, rc.REVEALED) == 4 + placed
    assert 'card_A69_loss_per_warband' not in state['event_modifiers']


def test_a69_caesar_counterattack_uses_surviving_roman_force_without_event_bonus():
    state = _state('A69')
    _bellovaci(state, rc.NERVII)
    place_piece(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 4)
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, 20, piece_state=rc.REVEALED)
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    state['rng'] = random.Random(19)  # Caesar rolls 6, preserving Counterattack.
    _event(state, rc.BELGAE)
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 12
    # 12 surviving Auxilia at half a Loss, plus Caesar's one Loss.
    assert count_pieces(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND) == 3


def test_a29_raids_only_placed_cohort_and_never_unrelated_revealed_forces():
    state = _state('A29')
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 3, piece_state=rc.REVEALED)
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 3)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 4)
    actions = _event(state, rc.GERMANS, {'placements': [
        {'region': rc.NERVII, 'piece_type': rc.WARBAND, 'count': 1},
        {'region': rc.TREVERI, 'piece_type': rc.WARBAND, 'count': 3}]})
    assert state['resources'][rc.GERMANS] == 3  # one Nervii raider, max2 Treveri
    assert count_pieces_by_state(state, rc.NERVII, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 4
    assert count_pieces_by_state(state, rc.UBII, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 3
    assert count_pieces_by_state(state, rc.UBII, rc.GERMANS, rc.WARBAND, rc.REVEALED) == 3
    assert actions[0]['faction'] == rc.GERMANS
    assert 'card_A29_raid_cohort' not in state['event_modifiers']


def test_a29_places_no_more_than_one_settlement():
    state = _state('A29')
    _event(state, rc.GERMANS, {'placements': [
        {'region': rc.NERVII, 'piece_type': rc.SETTLEMENT},
        {'region': rc.TREVERI, 'piece_type': rc.SETTLEMENT}]})
    assert count_pieces(state, rc.NERVII, rc.GERMANS, rc.SETTLEMENT) == 1
    assert count_pieces(state, rc.TREVERI, rc.GERMANS, rc.SETTLEMENT) == 0
