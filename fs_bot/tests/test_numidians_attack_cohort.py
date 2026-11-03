"""Revised Numidians: only Auxilia enter its Battle (A Card Reference 11).

§3.2.4 Counterattack removes attacking Forces. A Leader or Legion merely
sharing the Region cannot enter this Battle, absorb its Losses, or satisfy
Legio X's requirement for a Battle with both a Roman Leader and Legion.
"""
import pytest

from fs_bot import rules_consts as rc
from fs_bot.battle.resolve import resolve_battle
from fs_bot.board.control import calculate_control
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, get_available, get_leader_in_region,
    place_piece,
)
from fs_bot.cards.capabilities import activate_capability
from fs_bot.engine.diviciacus import KEY, force_scope
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tests.test_diviciacus_forces import board as cooperating_board


SCENARIOS = (rc.SCENARIO_PAX_GALLICA, rc.SCENARIO_RECONQUEST,
             rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS,
             rc.SCENARIO_GALLIC_WAR)


def battlefield(scenario=rc.SCENARIO_GREAT_REVOLT, *, enemy=9, auxiliaries=2):
    state = build_initial_state(scenario, seed=1)
    state['non_player_factions'] = {rc.ROMANS, rc.BELGAE}
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, auxiliaries)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEGION,
                from_legions_track=True)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, enemy)
    return state


def battle(state, *, revised=True, double=True, **kwargs):
    return resolve_battle(state, rc.CARNUTES, rc.ROMANS, rc.BELGAE,
                          retreat_declaration=False, double_auxilia=double,
                          auxilia_only_attack=revised, **kwargs)


@pytest.mark.parametrize('scenario', SCENARIOS)
@pytest.mark.parametrize('revised', [False, True])
def test_revised_battle_excludes_legion_but_original_numidians_includes_it(
        scenario, revised):
    state = battlefield(scenario)
    result = battle(state, revised=revised)
    # Original 11: 2 Auxilia + 1 Legion inflict 3 Losses. Revised 11:
    # the 2 Auxilia inflict 2; the Legion cannot take the Counterattack.
    assert result['attack']['losses_taken'] == (2 if revised else 3)
    assert result['counterattack']['losses_taken'] == (2 if revised else 3)
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.LEGION) == int(revised)
    assert result['counterattack']['rolls'] == ([] if revised else [(rc.LEGION, 2, True)])
    assert '_battle_auxilia_only' not in state
    assert validate_state(state) == []


@pytest.mark.parametrize('scenario', SCENARIOS)
def test_ordinary_battle_retains_all_roman_attackers(scenario):
    state = battlefield(scenario)
    result = battle(state, revised=False, double=False)
    assert result['attack']['losses_taken'] == 2
    assert result['counterattack']['losses_taken'] == 3
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.LEGION) == 0
    assert validate_state(state) == []


@pytest.mark.parametrize('scenario', SCENARIOS)
def test_excess_counterattack_cannot_remove_excluded_leader_legion_fort_or_ally(scenario):
    state = battlefield(scenario, enemy=25)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.FORT)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.ALLY)
    state['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] = rc.ROMANS
    result = battle(state)
    assert result['attack']['losses_taken'] == 2
    assert result['counterattack']['losses_taken'] == 2
    assert result['counterattack']['rolls'] == []
    for piece in (rc.LEADER, rc.LEGION, rc.FORT, rc.ALLY):
        assert count_pieces(state, rc.CARNUTES, rc.ROMANS, piece) == 1
    assert get_leader_in_region(state, rc.CARNUTES, rc.ROMANS) == rc.CAESAR
    assert validate_state(state) == []


@pytest.mark.parametrize('scenario', SCENARIOS)
def test_legio_x_requires_participating_leader_and_legion_for_both_modifiers(scenario):
    # A three-Warband survivor inflicts 1 Loss. Nonparticipating Legio X
    # cannot add 2 to the Attack or reduce that Counterattack to zero.
    state = battlefield(scenario, enemy=5)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    activate_capability(state, 15, rc.EVENT_UNSHADED)
    result = battle(state)
    assert result['attack']['losses_taken'] == 2
    assert result['counterattack']['losses_taken'] == 1
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces_by_state(state, rc.CARNUTES, rc.ROMANS,
                                 rc.AUXILIA, rc.REVEALED) == 1
    assert get_leader_in_region(state, rc.CARNUTES, rc.ROMANS) == rc.CAESAR
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.LEGION) == 1
    assert validate_state(state) == []


def test_human_casualty_menu_only_offers_participants_with_physical_control_unchanged():
    state = battlefield(enemy=25)
    state['non_player_factions'] = {rc.BELGAE}
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.FORT)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.ALLY)
    state['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] = rc.ROMANS
    requests = []

    def choose(board, faction, request):
        if faction == rc.ROMANS and request['kind'] == 'loss_order':
            requests.append(request)
            assert {entry[0] for entry in request['pieces']} == {rc.AUXILIA}
            assert get_leader_in_region(board, rc.CARNUTES, rc.ROMANS) is None
            assert count_pieces(board, rc.CARNUTES, rc.ROMANS, rc.LEGION) == 0
            physical = dict(board)
            physical.pop('_battle_auxilia_only', None)
            assert count_pieces(physical, rc.CARNUTES, rc.ROMANS, rc.LEGION) == 1
            assert get_leader_in_region(physical, rc.CARNUTES, rc.ROMANS) == rc.CAESAR
            assert calculate_control(board, rc.CARNUTES) == calculate_control(physical, rc.CARNUTES)
            assert validate_state(board) == []
        return None

    state['decision_agent'] = choose
    result = battle(state)
    assert len(requests) == 2
    assert result['counterattack']['losses_taken'] == 2
    assert '_battle_auxilia_only' not in state
    assert validate_state(state) == []


@pytest.mark.parametrize('leader', [False, True])
def test_borrowed_aedui_warbands_are_participating_auxilia_and_return_to_their_owner(leader):
    state = cooperating_board(leader=leader)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEGION,
                from_legions_track=True)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 12)
    before_aedui = get_available(state, rc.AEDUI, rc.WARBAND)
    before_romans = get_available(state, rc.ROMANS, rc.AUXILIA)
    with force_scope(state, rc.ROMANS, [rc.CARNUTES]):
        result = battle(state)
    assert result['attack']['losses_taken'] == 3
    assert result['counterattack']['losses_taken'] == 3
    assert result['counterattack']['rolls'] == []
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.LEGION) == 1
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 0
    assert get_available(state, rc.AEDUI, rc.WARBAND) == before_aedui + 2
    assert get_available(state, rc.ROMANS, rc.AUXILIA) == before_romans + 1
    if leader:
        assert get_leader_in_region(state, rc.CARNUTES, rc.AEDUI) == rc.DIVICIACUS
    assert KEY not in state and '_battle_auxilia_only' not in state
    assert validate_state(state) == []


@pytest.mark.parametrize('leader', [False, True])
def test_surviving_borrowed_auxilia_reveal_their_physical_aedui_warbands(leader):
    state = cooperating_board(leader=leader)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEGION,
                from_legions_track=True)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    with force_scope(state, rc.ROMANS, [rc.CARNUTES]):
        result = battle(state)
    assert result['attack']['losses_taken'] == 1
    assert count_pieces_by_state(state, rc.CARNUTES, rc.ROMANS,
                                 rc.AUXILIA, rc.REVEALED) == 1
    assert count_pieces_by_state(state, rc.CARNUTES, rc.AEDUI,
                                 rc.WARBAND, rc.REVEALED) == 2
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.LEGION) == 1
    assert KEY not in state and '_battle_auxilia_only' not in state
    assert validate_state(state) == []


def test_interrupted_loss_choice_removes_temporary_participant_view():
    state = battlefield(enemy=9)
    state['non_player_factions'] = {rc.BELGAE}

    def pause(_board, faction, request):
        if faction == rc.ROMANS and request['kind'] == 'loss_order':
            raise EOFError('paused casualty choice')

    state['decision_agent'] = pause
    with pytest.raises(EOFError, match='paused casualty choice'):
        battle(state)
    assert '_battle_auxilia_only' not in state
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.LEGION) == 1
    assert validate_state(state) == []
