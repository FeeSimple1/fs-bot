"""A28's Region scope, consenting shared force and physical ownership."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (
    place_piece, count_pieces, count_pieces_by_state, get_available,
)
from fs_bot.board.control import calculate_control
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity
from fs_bot.state.serialize import encode
from fs_bot.engine.execute import _execute_event, execute_decision
from fs_bot.cards.admagetobriga import collect_battle_plan
from fs_bot.battle.combined import combined_force, COMBINED_KEY
from fs_bot.battle.losses import calculate_losses


def state():
    st = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=28)
    st['current_card'] = 'A28'
    st['non_player_factions'] = set()
    st['resources'][rc.AEDUI] = 0
    st['event_params'] = None
    st['executing_faction'] = None
    return st


def event(st, plan=None, faction=rc.AEDUI):
    details = {'card_id': 'A28'}
    if plan is not None:
        details['event_params'] = {'battle_plan': plan}
    return _execute_event(st, faction, {'details': details}, human=True)


def battle(region=rc.SEQUANI, target=rc.GERMANS, **extra):
    return {'region': region, 'target_faction': target, **extra}


def test_shared_view_counts_only_warbands_auxilia_and_preserves_control():
    st = state()
    place_piece(st, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 2)
    place_piece(st, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(st, rc.SEQUANI, rc.ROMANS, rc.LEGION, 3, from_legions_track=True)
    place_piece(st, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    before = deepcopy(st['spaces'])
    control = calculate_control(st, rc.SEQUANI)
    with combined_force(st, rc.GERMANS, {rc.SEQUANI: [rc.ROMANS]}):
        assert calculate_losses(st, rc.SEQUANI, rc.GERMANS, rc.AEDUI) == 2
        assert count_pieces(st, rc.SEQUANI, rc.GERMANS, rc.LEGION) == 0
        assert count_pieces(st, rc.SEQUANI, rc.ROMANS, rc.LEGION) == 3
        assert count_pieces(st, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 0
        assert calculate_control(st, rc.SEQUANI) == control
    assert st['spaces'] == before and COMBINED_KEY not in st


def test_arverni_only_force_can_battle_in_multiple_granted_regions():
    st = state()
    for region in (rc.SEQUANI, rc.AEDUI_REGION):
        place_piece(st, region, rc.ARVERNI, rc.WARBAND, 4)
        place_piece(st, region, rc.GERMANS, rc.WARBAND, 2)
    requests = []
    st['decision_agent'] = lambda s, f, r: requests.append((f, r))
    result = event(st, [battle(), battle(rc.AEDUI_REGION)])
    assert result['executed']
    for region in (rc.SEQUANI, rc.AEDUI_REGION):
        assert count_pieces(st, region, rc.GERMANS, rc.WARBAND) == 0
        assert count_pieces_by_state(st, region, rc.ARVERNI, rc.WARBAND, rc.REVEALED) == 4
        assert count_pieces(st, region, rc.AEDUI, rc.WARBAND) == 0
    assert not any(r['kind'] == 'retreat' for _, r in requests)
    assert st['resources'][rc.AEDUI] == 0
    assert COMBINED_KEY not in st and check_structural_integrity(st) == []


@pytest.mark.parametrize('legions', [0, 1])
def test_caesar_retains_borrowed_warband_losses_with_or_without_legions(legions):
    st = state()
    place_piece(st, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    if legions:
        place_piece(st, rc.SEQUANI, rc.ROMANS, rc.LEGION, legions, from_legions_track=True)
    place_piece(st, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 4)
    place_piece(st, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 12)
    with combined_force(st, rc.ROMANS, {rc.SEQUANI: [rc.ARVERNI]}):
        assert calculate_losses(st, rc.SEQUANI, rc.ROMANS, rc.GERMANS) == 3 + 2 * legions
    result = event(st, [battle()], faction=rc.ROMANS)
    assert result['executed']
    assert count_pieces(st, rc.SEQUANI, rc.GERMANS, rc.WARBAND) == 9 - 2 * legions
    assert COMBINED_KEY not in st and check_structural_integrity(st) == []


def test_consenting_auxilia_take_counterattack_losses_but_legions_do_not_join():
    st = state()
    place_piece(st, rc.SEQUANI, rc.AEDUI, rc.WARBAND, 2)
    place_piece(st, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(st, rc.SEQUANI, rc.ROMANS, rc.LEGION, 2, from_legions_track=True)
    place_piece(st, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(st, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 8)
    roman_pool = get_available(st, rc.ROMANS, rc.AUXILIA)
    requests = []
    def choose(board, faction, request):
        requests.append((faction, request))
        if request['kind'] == 'agreement':
            return faction == rc.ROMANS
        if request['kind'] == 'loss_order' and faction == rc.AEDUI:
            return [(rc.AUXILIA, rc.HIDDEN, rc.ROMANS)]
    st['decision_agent'] = choose
    result = event(st, [battle(allied_factions=[rc.ROMANS])])
    assert result['executed']
    assert count_pieces(st, rc.SEQUANI, rc.GERMANS, rc.WARBAND) == 6
    assert count_pieces(st, rc.SEQUANI, rc.ROMANS, rc.LEGION) == 2
    assert count_pieces(st, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(st, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == 1
    assert get_available(st, rc.ROMANS, rc.AUXILIA) == roman_pool + 2
    consent = [r for f, r in requests if f == rc.ROMANS and r['kind'] == 'agreement']
    assert consent[0]['context']['may_take_losses'] is True
    assert not any(r['kind'] == 'retreat' for _, r in requests)
    assert check_structural_integrity(st) == []


@pytest.mark.parametrize('agrees,expected', [(False, 2), (True, 1)])
def test_lender_decides_whether_its_auxilia_join_and_reveal(agrees, expected):
    st = state()
    place_piece(st, rc.SEQUANI, rc.AEDUI, rc.WARBAND, 2)
    place_piece(st, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(st, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 3)
    st['decision_agent'] = lambda s, f, r: agrees if r['kind'] == 'agreement' else None
    assert event(st, [battle(allied_factions=[rc.ROMANS])])['executed']
    assert count_pieces(st, rc.SEQUANI, rc.GERMANS, rc.WARBAND) == expected
    visibility = rc.REVEALED if agrees else rc.HIDDEN
    assert count_pieces_by_state(st, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, visibility) == 2


@pytest.mark.parametrize('bad', [
    [battle(rc.MORINI)], [battle(), battle()],
    [battle(target=rc.AEDUI)], [battle(allied_factions=[rc.ROMANS, rc.ROMANS])],
    [battle(allied_factions=[rc.ARVERNI])], 'invalid',
])
def test_invalid_plan_rejected_before_agreements_board_or_rng_changes(bad):
    st = state()
    place_piece(st, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 4)
    place_piece(st, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 3)
    before = encode(st)
    result = event(st, bad)
    assert result['executed'] is False
    assert encode(st) == before


def test_empty_explicit_plan_declines_without_mutation():
    st = state()
    place_piece(st, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 4)
    place_piece(st, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 3)
    before = deepcopy(st['spaces'])
    event(st, [])
    assert st['spaces'] == before


def test_nonplayer_romans_refuse_and_aedui_belgae_conflict_is_reported():
    st = state()
    st['non_player_factions'] = {rc.ROMANS, rc.BELGAE}
    place_piece(st, rc.SEQUANI, rc.AEDUI, rc.WARBAND, 2)
    place_piece(st, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(st, rc.SEQUANI, rc.BELGAE, rc.WARBAND, 2)
    place_piece(st, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 1)
    result = event(st, [battle()])
    assert result['executed']
    assert 'A8.6.6' in repr(result)
    assert count_pieces_by_state(st, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 2
    assert count_pieces_by_state(st, rc.SEQUANI, rc.BELGAE, rc.WARBAND, rc.HIDDEN) == 2


def test_interrupted_loss_choice_rolls_back_event_and_removes_force_scope():
    st = state()
    place_piece(st, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 2)
    place_piece(st, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 8)
    def stop(board, faction, request):
        if request['kind'] == 'loss_order' and faction == rc.AEDUI:
            raise EOFError
    before = encode(st)
    st['decision_agent'] = stop
    with pytest.raises(EOFError):
        execute_decision(st, rc.AEDUI, {'player_action': {
            'command': 'Event', 'details': {'card_id': 'A28',
                'event_params': {'battle_plan': [battle()]}}}})
    assert COMBINED_KEY not in st
    assert encode({k: v for k, v in st.items() if k != 'decision_agent'}) == before


def test_terminal_selects_two_targets_without_requiring_own_pieces():
    st = state()
    for region in (rc.SEQUANI, rc.AEDUI_REGION):
        place_piece(st, region, rc.ARVERNI, rc.WARBAND, 4)
        place_piece(st, region, rc.GERMANS, rc.WARBAND, 2)
    plan = collect_battle_plan(st, rc.AEDUI, StringIO('2\n1\n2\n1\n'), StringIO())
    assert {b['region'] for b in plan['battle_plan']} == {rc.SEQUANI, rc.AEDUI_REGION}
    assert all(b['target_faction'] == rc.GERMANS for b in plan['battle_plan'])
