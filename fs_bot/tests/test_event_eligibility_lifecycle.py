"""Printed Event eligibility survives §2.3.6, then expires after next card."""
import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece
from fs_bot.cards.card_effects import execute_event
from fs_bot.engine.game_engine import (
    ACTION_EVENT, ACTION_PASS, adjust_eligibility, get_sop_factions, resolve_card_turn,
)
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import check_structural_integrity


@pytest.mark.parametrize('scenario,card,actor,params,expected', [
    (rc.SCENARIO_GREAT_REVOLT, 6, rc.ROMANS, {},
     {rc.ROMANS: rc.ELIGIBLE}),
    (rc.SCENARIO_GREAT_REVOLT, 14, rc.ROMANS, {},
     {rc.ROMANS: rc.ELIGIBLE}),
    (rc.SCENARIO_GREAT_REVOLT, 40, rc.BELGAE, {},
     {rc.BELGAE: rc.ELIGIBLE}),
    (rc.SCENARIO_GREAT_REVOLT, 48, rc.BELGAE,
     {'target_factions': [rc.AEDUI]}, {rc.BELGAE: rc.ELIGIBLE}),
    (rc.SCENARIO_ARIOVISTUS, 'A40', rc.BELGAE, {},
     {rc.BELGAE: rc.ELIGIBLE}),
    (rc.SCENARIO_ARIOVISTUS, 'A53', rc.BELGAE, {},
     {rc.BELGAE: rc.ELIGIBLE, rc.ROMANS: rc.INELIGIBLE,
      rc.AEDUI: rc.INELIGIBLE}),
    (rc.SCENARIO_ARIOVISTUS, 'A53', rc.ROMANS, {},
     {rc.ROMANS: rc.ELIGIBLE, rc.AEDUI: rc.INELIGIBLE}),
    (rc.SCENARIO_ARIOVISTUS, 'A53', rc.AEDUI, {},
     {rc.AEDUI: rc.ELIGIBLE, rc.ROMANS: rc.INELIGIBLE}),
    (rc.SCENARIO_ARIOVISTUS, 'A19', rc.GERMANS, {},
     {rc.ROMANS: rc.INELIGIBLE}),
])
def test_event_effect_is_visible_on_next_card_and_then_expires(
        scenario, card, actor, params, expected):
    state = setup_scenario(scenario, seed=21)
    state['current_card'] = card
    state['next_card'] = 1
    state['non_player_factions'] = set(get_sop_factions(state)) - {actor}
    if card == 'A19':
        place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA)

    def choose(board, faction, options, position):
        if faction != actor:
            return {'action': ACTION_PASS}
        return {'action': ACTION_EVENT, 'player_action': {
            'command': 'Event', 'sa': 'No SA', 'sa_regions': [], 'details': {
                'card_id': card, 'text_preference': rc.EVENT_SHADED,
                'event_params': params,
            },
        }}

    turn = resolve_card_turn(state, choose, execute=True)
    assert turn['actions_taken'][actor]['execution']['executed']
    assert {f: state['eligibility'][f] for f in expected} == expected
    assert check_structural_integrity(state) == []
    assert not state.get('stay_eligible')

    # Ineligible factions do not even receive a decision on the next card.
    state['current_card'] = state['next_card']
    state['next_card'] = 2
    prompted = []

    def pass_next(board, faction, options, position):
        prompted.append(faction)
        return {'action': ACTION_PASS}

    resolve_card_turn(state, pass_next, execute=True)
    blocked = {f for f, eligibility in expected.items()
               if eligibility == rc.INELIGIBLE}
    assert blocked.isdisjoint(prompted)
    assert all(state['eligibility'][f] == rc.ELIGIBLE for f in expected)
    assert not state.get('forced_ineligible')


def test_later_event_can_override_previous_cards_ineligibility():
    """§5.1.2: A34's selected beneficiary overrides earlier Celtic Rites."""
    state = setup_scenario(rc.SCENARIO_ARIOVISTUS, seed=21)
    state['executing_faction'] = rc.AEDUI
    state['event_params'] = {'target_factions': [rc.BELGAE]}
    execute_event(state, 46)
    adjust_eligibility(state, {rc.AEDUI: {'action': ACTION_EVENT}})
    assert state['eligibility'][rc.BELGAE] == rc.INELIGIBLE
    state['executing_faction'] = rc.GERMANS
    state['event_params'] = {'faction': rc.BELGAE}
    execute_event(state, 'A34', shaded=True)
    assert state['eligibility'][rc.BELGAE] == rc.ELIGIBLE
    adjust_eligibility(state, {rc.GERMANS: {'action': ACTION_EVENT}})
    assert state['eligibility'][rc.BELGAE] == rc.ELIGIBLE
