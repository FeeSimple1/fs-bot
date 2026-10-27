"""§8.1.1's next-final-Winter rule uses the actual scenario's remaining deck.

The Gallic War first half continues through its third Winter into a rebuilt
Pax Gallica deck (A Scenario). Ariovistus also explicitly permits a shorter
two-Winter deck. Neither situation can be inferred from a fixed year count.
"""
import copy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.bots.aedui_bot import node_a3
from fs_bot.bots.arverni_bot import node_v2b
from fs_bot.bots.belgae_bot import node_b3b
from fs_bot.bots.bot_common import is_final_year_capability
from fs_bot.bots.german_bot import node_g3b
from fs_bot.bots.roman_bot import node_r4
from fs_bot.cards.event_eval import is_capability_final_year
from fs_bot.engine.game_engine import next_winter_is_final
from fs_bot.state.serialize import encode
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state


def _before_winter(state, ordinal):
    """A real draw-history snapshot just before the specified setup Winter."""
    deck = list(state['deck'])
    positions = [i for i, card in enumerate(deck) if card == rc.WINTER_CARD]
    winter_index = positions[ordinal - 1]
    state['played_cards'] = deck[:winter_index]
    state['current_card'] = state['current_card_id'] = deck[winter_index - 1]
    state['deck'] = deck[winter_index:]
    state['next_card'] = rc.WINTER_CARD
    state['winter_count'] = ordinal - 1
    return state


@pytest.mark.parametrize('scenario', (*rc.BASE_SCENARIOS, *rc.ARIOVISTUS_SCENARIOS))
def test_real_scenario_deck_without_final_year_flag_agrees_across_consumers(scenario):
    setup = setup_scenario(scenario, seed=8)
    assert 'final_year' not in setup
    winters = setup['deck'].count(rc.WINTER_CARD)
    assert winters >= 2
    first = _before_winter(copy.deepcopy(setup), 1)
    last = _before_winter(copy.deepcopy(setup), winters)
    for state, expected in ((first, False), (last, scenario != rc.SCENARIO_GALLIC_WAR)):
        before = encode(state)
        assert next_winter_is_final(state) is expected
        # Baggage Trains is a retained Capability in both game systems.
        assert is_final_year_capability(state, 8) is expected
        assert is_capability_final_year(state, 8) is expected
        assert is_final_year_capability(state, 1) is False
        assert is_capability_final_year(state, 1) is False
        assert encode(state) == before


def test_short_ariovistus_deck_detects_second_winter_as_final():
    # The Ariovistus scenario explicitly offers 30 Events in six five-card
    # piles, with Winters in piles three and six.
    state = setup_scenario(rc.SCENARIO_ARIOVISTUS, seed=8)
    state['deck'] = [1] * 15 + [rc.WINTER_CARD] + [2] * 15 + [rc.WINTER_CARD]
    first = _before_winter(copy.deepcopy(state), 1)
    second = _before_winter(copy.deepcopy(state), 2)
    assert next_winter_is_final(first) is False
    assert next_winter_is_final(second) is True
    assert second['winter_count'] == 1


@pytest.mark.parametrize('remaining,completed,expected', [(5, 3, False), (2, 6, False), (1, 7, True)])
def test_post_interlude_count_survives_cleared_played_cards(remaining, completed, expected):
    # The Interlude changes scenario to Pax Gallica and rebuilds/clears the
    # deck and played pile, while retaining the first half's Winter count.
    state = setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=8)
    state.update(scenario_phase='second_half', interlude_completed=True,
                 winter_count=completed, played_cards=[8], current_card=8)
    state['deck'] = [card for _ in range(remaining) for card in (1, rc.WINTER_CARD)]
    before = encode(state)
    assert next_winter_is_final(state) is expected
    assert is_final_year_capability(state, 8) is expected
    assert is_capability_final_year(state, 8) is expected
    assert encode(state) == before


@pytest.mark.parametrize('remaining', [1, 2, 3])
def test_gallic_war_pre_interlude_is_never_final_even_with_stale_true_flag(remaining):
    state = setup_scenario(rc.SCENARIO_GALLIC_WAR, seed=8)
    state['deck'] = [card for _ in range(remaining) for card in (1, rc.WINTER_CARD)]
    state['winter_count'] = 3 - remaining
    state['final_year'] = True
    assert next_winter_is_final(state) is False
    assert is_final_year_capability(state, 8) is False
    assert is_capability_final_year(state, 8) is False


@pytest.mark.parametrize('deck,expected', [
    ([1, rc.WINTER_CARD, 2, rc.WINTER_CARD], False),
    ([1, rc.WINTER_CARD], True),
    (['W1', 1, 'W2'], False),
    ([1, 'W5'], True),
    ([1, rc.WINTER_CARD, 'W99'], True),
])
def test_actual_winter_cards_override_stale_synthetic_flag(deck, expected):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=8)
    state['deck'] = deck
    state['final_year'] = not expected
    assert next_winter_is_final(state) is expected
    assert is_final_year_capability(state, 8) is expected
    assert is_capability_final_year(state, 8) is expected


@pytest.mark.parametrize('flag', [False, True])
@pytest.mark.parametrize('deck', [[], [1, 2]])
def test_legacy_explicit_flag_is_only_a_fallback_without_winter_cards(flag, deck):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=8)
    state['deck'], state['final_year'] = deck, flag
    assert next_winter_is_final(state) is flag
    assert is_final_year_capability(state, 8) is flag
    assert is_capability_final_year(state, 8) is flag


def test_unstarted_empty_state_and_post_final_event_only_deck_are_distinct():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=8)
    assert next_winter_is_final(state) is False
    assert is_final_year_capability(state, 8) is False
    assert is_capability_final_year(state, 8) is False
    state['deck'] = [1, 2]
    assert next_winter_is_final(state) is True
    assert is_final_year_capability(state, 8) is True
    assert is_capability_final_year(state, 8) is True


@pytest.mark.parametrize('scenario', (*rc.BASE_SCENARIOS, rc.SCENARIO_ARIOVISTUS))
def test_real_ordinary_np_event_nodes_decline_capability_only_in_final_year(scenario):
    state = setup_scenario(scenario, seed=8)
    state['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE, rc.ARVERNI, rc.GERMANS}
    state['current_card'] = state['current_card_id'] = 8
    nodes = [node_r4, node_a3, node_b3b]
    if scenario in rc.BASE_SCENARIOS:
        nodes.append(node_v2b)
    state['deck'] = [1, rc.WINTER_CARD, 2, rc.WINTER_CARD]
    state['final_year'] = True  # A stale compatibility hint must not override play.
    assert [node(state) for node in nodes] == ['No'] * len(nodes)
    state['deck'] = [1, rc.WINTER_CARD]
    state['final_year'] = False
    assert [node(state) for node in nodes] == ['Yes'] * len(nodes)


@pytest.mark.parametrize('card_id', [13, 'A66'])
def test_german_event_node_uses_live_deck_for_capability_and_uprising(card_id):
    state = setup_scenario(rc.SCENARIO_ARIOVISTUS, seed=8)
    # Romans human avoids Balearic Slingers' independent "No Germans if
    # Romans Non-player" instruction; both cards otherwise apply here.
    state['non_player_factions'] = {rc.GERMANS, rc.AEDUI, rc.BELGAE}
    state['current_card'] = state['current_card_id'] = card_id
    state['deck'], state['final_year'] = [1, rc.WINTER_CARD, 2, rc.WINTER_CARD], True
    assert node_g3b(state) == 'No'
    state['deck'], state['final_year'] = [1, rc.WINTER_CARD], False
    assert node_g3b(state) == 'Yes'


def test_german_capability_and_uprising_remain_available_before_gallic_war_interlude():
    state = setup_scenario(rc.SCENARIO_GALLIC_WAR, seed=8)
    state['non_player_factions'] = {rc.GERMANS, rc.AEDUI, rc.BELGAE}
    state['winter_count'], state['deck'] = 2, [1, rc.WINTER_CARD]
    state['final_year'] = True
    for card_id in (13, 'A66'):
        state['current_card'] = state['current_card_id'] = card_id
        assert node_g3b(state) == 'No'


def test_optional_diviciacus_preserves_unshaded_compatibility_pending_q_o38():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=8, diviciacus_option=True)
    state['deck'] = [1, rc.WINTER_CARD]
    assert is_capability_final_year(state, rc.CARD_O38, shaded=False) is False
    assert is_capability_final_year(state, rc.CARD_O38, shaded=True) is True
    assert not is_final_year_capability(state, rc.CARD_O38, shaded=False)
    assert is_final_year_capability(state, rc.CARD_O38, shaded=True)
    from fs_bot.bots.bot_common import should_decline_event
    from fs_bot.cards.card_data import is_capability_card
    assert is_capability_card(rc.CARD_O38, state['scenario'])
    # Preserve the previous unshaded opportunity pending Q-O38's unresolved
    # CAPABILITY boundary; the shaded prohibition is clearly a Capability.
    assert not should_decline_event(state, rc.CARD_O38, rc.AEDUI)
    assert not should_decline_event(state, rc.CARD_O38, rc.ROMANS)
    assert should_decline_event(state, rc.CARD_O38, rc.ARVERNI)
    assert should_decline_event(state, rc.CARD_O38, rc.BELGAE)
