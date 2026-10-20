"""NP Event entry conditions from Card9 Tips and Ariovistus instructions.

A recursive census exposed these as nested Event refusals. Preventing an
ineffective/forbidden Event selection is the fix; executor error diagnostics
must remain visible if an invalid Event is forced directly.
"""
import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece
from fs_bot.bots.german_bot import node_g3b
from fs_bot.bots.belgae_bot import node_b3b
from fs_bot.engine.execute import _execute_event
from fs_bot.state.state_schema import build_initial_state


def state_for(card):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=12)
    state['current_card_id'] = state['current_card'] = card
    state['non_player_factions'] = {rc.ROMANS, rc.GERMANS, rc.AEDUI, rc.BELGAE}
    return state


def test_mons_cevenna_declined_without_germans_in_its_actual_theatre():
    state = state_for(9)
    # A healthy force elsewhere does not satisfy the card's geographic grant.
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, 10)
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.SETTLEMENT)
    assert node_g3b(state) == 'Yes'
    # Do not disguise a forced executor refusal as an intentional no-op.
    result = _execute_event(state, rc.GERMANS, {'details': {
        'card_id': 9, 'text_preference': rc.EVENT_SHADED}}, human=True)
    command = next(e for e in result['free_actions'] if e['free_action'] == 'free_command')
    assert not command['result']['executed']
    assert 'no Command available' in command['result']['reason']


@pytest.mark.parametrize('region', [rc.PROVINCIA, rc.SEQUANI, rc.ARVERNI_REGION])
@pytest.mark.parametrize('piece', [rc.WARBAND, rc.ALLY, rc.SETTLEMENT, rc.LEADER])
def test_mons_cevenna_guard_preserves_mobile_and_static_presence(region, piece):
    state = state_for(9)
    kwargs = {'leader_name': rc.ARIOVISTUS_LEADER} if piece == rc.LEADER else {}
    place_piece(state, region, rc.GERMANS, piece, **kwargs)
    assert node_g3b(state) == 'No'


@pytest.mark.parametrize('controller,belgae_np,decline', [
    (None, True, True), (rc.ARVERNI, True, True), (rc.ROMANS, True, True),
    (rc.AEDUI, True, True), (rc.BELGAE, False, True),
    (rc.BELGAE, True, False), (rc.GERMANS, True, False),
])
def test_assembly_of_gaul_german_instruction_checks_fixed_beneficiary(controller, belgae_np, decline):
    state = state_for(52)
    if not belgae_np:
        state['non_player_factions'].remove(rc.BELGAE)
    if controller:
        place_piece(state, rc.CARNUTES, controller,
                    rc.AUXILIA if controller == rc.ROMANS else rc.WARBAND, 2)
    assert (node_g3b(state) == 'Yes') is decline


@pytest.mark.parametrize('region,warbands,auxilia,legions,decline', [
    (rc.NERVII, 4, 1, 1, False),
    (rc.NERVII, 2, 2, 1, True),  # Auxilia absorb all predicted Losses.
    (rc.NERVII, 4, 1, 0, True),  # No Legion can be forced to take a Loss.
    (rc.CARNUTES, 4, 1, 1, True),  # A legal Battle outside Belgica is irrelevant.
])
def test_sabis_belgae_declines_unless_legion_losses_can_be_forced(region, warbands, auxilia, legions, decline):
    state = state_for('A57')
    place_piece(state, region, rc.BELGAE, rc.WARBAND, warbands)
    place_piece(state, region, rc.ROMANS, rc.AUXILIA, auxilia)
    if legions:
        place_piece(state, region, rc.ROMANS, rc.LEGION, legions, from_legions_track=True)
    assert (node_b3b(state) == 'Yes') is decline


def test_sabis_declines_enemy_warbands_without_any_roman_legion_target():
    state = state_for('A57')
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 10)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 2)
    assert node_b3b(state) == 'Yes'


@pytest.mark.parametrize('faction', [rc.AEDUI, rc.BELGAE])
def test_mons_cevenna_definitely_empty_theatre_declined_for_other_gauls(faction):
    from fs_bot.bots.bot_common import should_decline_event
    state = state_for(9)
    place_piece(state, rc.NERVII, faction, rc.WARBAND, 4)
    assert should_decline_event(state, 9, faction)


def test_mons_cevenna_preserves_possible_sa_first_enlist_case():
    from fs_bot.bots.bot_common import should_decline_event
    state = state_for(9)
    place_piece(state, rc.MANDUBII, rc.BELGAE, rc.LEADER, leader_name=rc.BODUOGNATUS)
    place_piece(state, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 4)
    assert not should_decline_event(state, 9, rc.BELGAE)


def test_sabis_germans_decline_when_force_and_enemy_do_not_overlap():
    state = state_for('A57')
    place_piece(state, rc.MORINI, rc.GERMANS, rc.WARBAND, 5)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 2)
    assert node_g3b(state) == 'Yes'


@pytest.mark.parametrize('warbands,decline', [(3, True), (8, False)])
def test_sabis_germans_obey_ariovistus_warband_floor(warbands, decline):
    state = state_for('A57')
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, warbands)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 2)
    assert (node_g3b(state) == 'Yes') is decline


@pytest.mark.parametrize('faction', [rc.AEDUI, rc.ROMANS])
@pytest.mark.parametrize('own_region,enemy_region,decline', [
    (rc.MORINI, rc.NERVII, True),  # No actual Battle target.
    (rc.CARNUTES, rc.CARNUTES, True),  # Outside the Event's Belgica grant.
    (rc.NERVII, rc.NERVII, False),
])
def test_sabis_general_ineffectiveness_uses_actual_belgica_target(
        faction, own_region, enemy_region, decline):
    from fs_bot.bots.bot_common import should_decline_event
    state = state_for('A57')
    place_piece(state, own_region, faction,
                rc.AUXILIA if faction == rc.ROMANS else rc.WARBAND, 4)
    place_piece(state, enemy_region, rc.BELGAE, rc.WARBAND, 2)
    assert should_decline_event(state, 'A57', faction) is decline
