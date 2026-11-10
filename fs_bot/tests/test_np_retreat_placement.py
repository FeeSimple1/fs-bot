"""§8.4.3: Non-player Leaders join the most friendly pieces after Retreat."""

from copy import deepcopy
from random import Random

import pytest

from fs_bot import rules_consts as rc
from fs_bot.battle.resolve import resolve_battle
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_leader_in_region, place_piece
from fs_bot.cards.divination_np import _battle_frost_outcomes
from fs_bot.engine import action_windows, voluntary_removal
from fs_bot.engine.agent import AGREEMENT, RETREAT_DISPOSITION
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import validate_state
from fs_bot.tests.test_battle_retreat_disposition import battle, position


def belgic_position(*, auxilia=6, hidden=1):
    board = position(rc.BELGAE)
    board['non_player_factions'].add(rc.BELGAE)
    place_piece(board, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, auxilia)
    place_piece(board, rc.CARNUTES, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    place_piece(board, rc.CARNUTES, rc.BELGAE, rc.WARBAND, hidden)
    return board


def test_ambiorix_leaves_carnutes_to_join_more_friendly_pieces_after_attack():
    board = belgic_position()
    place_piece(board, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 5)
    result = battle(board, rc.BELGAE)
    assert result['attack']['losses_taken'] == 1 and result['defender_retreated']
    assert result['retreat']['moved'] == [(rc.LEADER, 1)]
    assert get_leader_in_region(board, rc.ATREBATES, rc.BELGAE) == rc.AMBIORIX
    assert count_pieces(board, rc.CARNUTES, rc.BELGAE) == 0


@pytest.mark.parametrize('defender,leader', [(rc.BELGAE, rc.AMBIORIX),
                                            (rc.GERMANS, rc.ARIOVISTUS_LEADER)])
@pytest.mark.parametrize('local,adjacent,stays', [(3, 2, False), (4, 1, True)])
def test_roman_attack_scores_both_groups_after_revealed_warbands_leave(
        defender, leader, local, adjacent, stays):
    board = position(defender)
    board['non_player_factions'].add(defender)
    place_piece(board, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    place_piece(board, rc.CARNUTES, defender, rc.LEADER, leader_name=leader)
    place_piece(board, rc.CARNUTES, defender, rc.WARBAND, local)
    place_piece(board, rc.CARNUTES, defender, rc.WARBAND, 2, piece_state=rc.REVEALED)
    place_piece(board, rc.ATREBATES, defender, rc.WARBAND, adjacent)
    rng = board['rng'].getstate()

    result = resolve_battle(board, rc.CARNUTES, rc.ROMANS, defender,
                            retreat_declaration=True, retreat_region=rc.ATREBATES)
    expected = rc.CARNUTES if stays else rc.ATREBATES
    assert result['defender_retreated'] and get_leader_in_region(board, expected, defender) == leader
    assert count_pieces_by_state(board, rc.CARNUTES, defender, rc.WARBAND, rc.HIDDEN) == local
    assert count_pieces_by_state(board, rc.ATREBATES, defender, rc.WARBAND, rc.REVEALED) == 2
    assert board['rng'].getstate() == rng  # A unique best Region needs no roll.
    assert validate_state(board) == []


def test_npc_survivors_join_an_existing_leader_instead_of_a_larger_stack():
    board = position(rc.ARVERNI, attacker=rc.BELGAE)
    board['non_player_factions'].add(rc.ARVERNI)
    place_piece(board, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    place_piece(board, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 2)
    place_piece(board, rc.ATREBATES, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(board, rc.MANDUBII, rc.ARVERNI, rc.WARBAND, 4)
    result = resolve_battle(board, rc.CARNUTES, rc.BELGAE, rc.ARVERNI,
                            retreat_declaration=True, retreat_region=rc.MANDUBII,
                            retreat_agreements={})
    assert result['retreat']['moved'] == [(rc.WARBAND, 2)]
    assert count_pieces(board, rc.ATREBATES, rc.ARVERNI, rc.WARBAND) == 2
    assert count_pieces(board, rc.MANDUBII, rc.ARVERNI, rc.WARBAND) == 4
    assert validate_state(board) == []


@pytest.mark.parametrize('attacker', [rc.ROMANS, rc.AEDUI])
def test_local_allies_count_but_cannot_enable_staying_against_a_gallic_attack(attacker):
    board = position(rc.BELGAE, attacker=attacker)
    board['non_player_factions'].add(rc.BELGAE)
    attacker_piece = rc.AUXILIA if attacker == rc.ROMANS else rc.WARBAND
    place_piece(board, rc.CARNUTES, attacker, attacker_piece)
    place_piece(board, rc.CARNUTES, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    place_piece(board, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 2)
    place_piece(board, rc.CARNUTES, rc.BELGAE, rc.ALLY)
    board['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] = rc.BELGAE
    place_piece(board, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 2)
    rng = board['rng'].getstate()

    result = resolve_battle(board, rc.CARNUTES, attacker, rc.BELGAE,
                            retreat_declaration=True, retreat_region=rc.ATREBATES)
    assert result['defender_retreated']
    # The Ally makes three local companions rather than a tie against Rome.
    expected = rc.CARNUTES if attacker == rc.ROMANS else rc.ATREBATES
    assert get_leader_in_region(board, expected, rc.BELGAE) == rc.AMBIORIX
    assert count_pieces(board, rc.CARNUTES, rc.BELGAE, rc.ALLY) == 1
    assert board['rng'].getstate() == rng
    assert validate_state(board) == []


def test_live_npc_retreat_checks_host_control_after_losses_and_timing_actions():
    board = belgic_position()
    place_piece(board, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(board, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 2)
    place_piece(board, rc.ATREBATES, rc.AEDUI, rc.WARBAND)
    place_piece(board, rc.MANDUBII, rc.BELGAE, rc.WARBAND)
    board['non_player_factions'].remove(rc.ROMANS)
    hosts = []
    dispositions = []

    def choose(state, who, request):
        if request['kind'] == AGREEMENT:
            hosts.append((who, request['context']['region']))
            return True
        if request['kind'] == RETREAT_DISPOSITION:
            dispositions.append(who)
        if request['kind'] == voluntary_removal.KIND:
            if request['window']['stage'] == 'battle_retreat' and who == rc.ROMANS:
                option = next((op for op in request['options']
                               if op['region'] == rc.ATREBATES and op['max_count'] == 4), None)
                if option:
                    return {'operations': [voluntary_removal.operation(option, 2)]}
            return {'done': True}

    choose.supports_action_windows = True
    board['decision_agent'] = choose
    with action_windows.scope(board, actor=rc.ROMANS):
        result = battle(board, rc.BELGAE)
    assert result['defender_retreated'] and hosts == [(rc.ROMANS, rc.ATREBATES)]
    assert not dispositions
    assert get_leader_in_region(board, rc.MANDUBII, rc.BELGAE) == rc.AMBIORIX
    assert get_leader_in_region(board, rc.ATREBATES, rc.BELGAE) is None


def test_equal_companion_counts_use_the_seeded_choice_and_frost_checks_all_results():
    original = belgic_position(hidden=2)
    destinations = [rc.ATREBATES, rc.CARNUTES, rc.MANDUBII]
    place_piece(original, rc.ATREBATES, rc.BELGAE, rc.WARBAND)
    place_piece(original, rc.MANDUBII, rc.BELGAE, rc.WARBAND)
    selected = set()
    for seed in (0, 1, 5):
        board = deepcopy(original)
        board['rng'].seed(seed)
        expected = Random(seed).choice(destinations)
        result = battle(board, rc.BELGAE)
        assert result['attack']['losses_taken'] == 1
        assert get_leader_in_region(board, expected, rc.BELGAE) == rc.AMBIORIX
        selected.add(expected)
    assert selected == set(destinations)

    before = encode(original)
    outcomes = list(_battle_frost_outcomes(original, rc.CARNUTES, rc.BELGAE, attacker=rc.ROMANS))
    actual = {dest for sim in outcomes for dest in destinations
              if get_leader_in_region(sim, dest, rc.BELGAE) == rc.AMBIORIX}
    assert actual == set(destinations)
    assert encode(original) == before
