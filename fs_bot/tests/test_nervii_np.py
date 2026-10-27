"""A70's Roman and Aedui instruction sheets condition the Event on Belgic seats."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.bots.aedui_bot import node_a3
from fs_bot.bots.bot_common import get_event_instruction, should_decline_event
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.bots.roman_bot import node_r4
from fs_bot.cards.event_eval import is_event_effective
from fs_bot.engine.execute import _execute_event
from fs_bot.engine.game_engine import next_winter_is_final
from fs_bot.state.serialize import encode
from fs_bot.state.setup import setup_scenario


def _state(scenario, belgae_np=True):
    state = setup_scenario(scenario, seed=3)
    state['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.GERMANS}
    if belgae_np:
        state['non_player_factions'].add(rc.BELGAE)
    state['current_card'] = state['current_card_id'] = 'A70'
    state['can_play_event'] = True
    state['is_second_eligible'] = False
    state['current_card_faction_order'] = [rc.BELGAE, rc.AEDUI, rc.GERMANS, rc.ROMANS]
    state['next_card_faction_order'] = [rc.ROMANS, rc.AEDUI]
    return state


@pytest.mark.parametrize('scenario', rc.ARIOVISTUS_SCENARIOS)
@pytest.mark.parametrize('faction,node', [(rc.ROMANS, node_r4), (rc.AEDUI, node_a3)])
@pytest.mark.parametrize('belgae_np', [True, False])
def test_earlier_year_nodes_and_full_dispatch_follow_printed_belgic_seat_condition(
        scenario, faction, node, belgae_np):
    state = _state(scenario, belgae_np)
    # No final-year or ineffective-Event decline can conceal this condition.
    assert not next_winter_is_final(state)
    assert is_event_effective(state, 'A70', False)
    assert get_event_instruction('A70', faction, scenario).instruction == (
        f"If Belgae Non-player, treat as 'No {faction}'.")
    before = encode(state)
    assert should_decline_event(state, 'A70', faction) is belgae_np
    assert node(state) == ('Yes' if belgae_np else 'No')
    assert encode(state) == before
    action = dispatch_bot_turn(deepcopy(state), faction)
    assert (action['command'] == 'Event') is not belgae_np
    if not belgae_np:
        assert action['details']['card_id'] == 'A70'


@pytest.mark.parametrize('scenario', rc.ARIOVISTUS_SCENARIOS)
@pytest.mark.parametrize('faction', [rc.ROMANS, rc.AEDUI])
@pytest.mark.parametrize('side', [rc.EVENT_UNSHADED, rc.EVENT_SHADED])
def test_human_explicit_nervii_event_remains_legal_with_nonplayer_belgae(scenario, faction, side):
    state = _state(scenario)
    state['non_player_factions'].remove(faction)
    result = _execute_event(state, faction, {'details': {
        'card_id': 'A70', 'text_preference': side}}, human=True)
    assert result['executed']
    assert state['capabilities']['A70'] == side


@pytest.mark.parametrize('scenario', rc.BASE_SCENARIOS)
@pytest.mark.parametrize('faction', [rc.ROMANS, rc.AEDUI])
def test_base_camulogenus_does_not_inherit_expansion_nervii_condition(scenario, faction):
    state = setup_scenario(scenario, seed=3)
    state['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE, rc.ARVERNI}
    assert not next_winter_is_final(state)
    assert should_decline_event(state, 70, faction) is False


@pytest.mark.parametrize('scenario', rc.ARIOVISTUS_SCENARIOS)
@pytest.mark.parametrize('faction,expected_decline', [(rc.BELGAE, False), (rc.GERMANS, True)])
def test_other_factions_keep_their_nervii_instructions(scenario, faction, expected_decline):
    state = _state(scenario)
    assert should_decline_event(state, 'A70', faction) is expected_decline


@pytest.mark.parametrize('faction,node', [(rc.ROMANS, node_r4), (rc.AEDUI, node_a3)])
def test_player_belgae_does_not_override_final_year_capability_decline(faction, node):
    state = _state(rc.SCENARIO_ARIOVISTUS, belgae_np=False)
    state['deck'] = [rc.WINTER_CARD]
    state['played_cards'] = [rc.WINTER_CARD, rc.WINTER_CARD]
    state['winter_count'] = 2
    assert next_winter_is_final(state)
    assert should_decline_event(state, 'A70', faction)
    assert node(state) == 'Yes'


@pytest.mark.parametrize('faction,node', [(rc.ROMANS, node_r4), (rc.AEDUI, node_a3)])
def test_gallic_war_interlude_continuation_does_not_bypass_belgic_seat_condition(faction, node):
    state = _state(rc.SCENARIO_GALLIC_WAR)
    state['deck'] = [rc.WINTER_CARD]
    state['played_cards'] = [rc.WINTER_CARD, rc.WINTER_CARD]
    state['winter_count'] = 2
    assert not next_winter_is_final(state)
    assert should_decline_event(state, 'A70', faction)
    assert node(state) == 'Yes'
