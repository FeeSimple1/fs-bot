"""Provisional PR-05/PR-06: printed Harassment order survives Winter/save/load.

These adopted rulings remain subject to authoritative later correction.
"""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, get_leader_in_region
from fs_bot.cards.capabilities import activate_capability, set_capability_owner
from fs_bot.engine.agent import HARASSMENT_LOSS
from fs_bot.engine.game_engine import (
    ACTION_PASS, advance_to_next_card, draw_card, get_harassment_order,
    get_sop_factions, resolve_card_turn,
)
from fs_bot.engine.winter_campaign import winter_campaign_after_harvest
from fs_bot.state.serialize import encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.run_batch import play_one


@pytest.mark.parametrize('current_card', [rc.WINTER_CARD, 'W1'])
@pytest.mark.parametrize('played_cards,expected', [
    ([4], [rc.ROMANS, rc.BELGAE, rc.AEDUI]),
    ([], [rc.BELGAE, rc.ROMANS, rc.AEDUI]),
])
def test_actual_after_harvest_campaign_uses_previous_event_or_compatibility_order(
        current_card, played_cards, expected):
    st = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=75)
    st['current_card'], st['next_card'] = current_card, 4
    st['played_cards'] = [*played_cards, current_card]
    st['non_player_factions'] = set(get_sop_factions(st)) - {rc.ARVERNI, rc.BELGAE}
    st['resources'][rc.ARVERNI] = 10
    activate_capability(st, 63, rc.EVENT_SHADED)
    set_capability_owner(st, 63, rc.ARVERNI)
    place_piece(st, rc.MORINI, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(st, rc.MORINI, rc.ARVERNI, rc.WARBAND, 5)
    place_piece(st, rc.NERVII, rc.ROMANS, rc.AUXILIA, 3)
    place_piece(st, rc.NERVII, rc.AEDUI, rc.WARBAND, 3)
    place_piece(st, rc.NERVII, rc.BELGAE, rc.WARBAND, 3)
    plan = {'command': rc.CMD_MARCH, 'sa': 'No SA', 'details': {
        'origins': [rc.MORINI], 'destinations': [rc.ATREBATES],
        'routes': {rc.MORINI: [rc.NERVII, rc.ATREBATES]}}}
    campaigns, harassers = [], []
    def agent(board, faction, request):
        if request['kind'] == 'winter_campaign':
            campaigns.append(request)
            return plan if len(campaigns) == 1 else {'decline': True}
        if request.get('request_type') == 'harassment':
            return True
        if request['kind'] == HARASSMENT_LOSS:
            harassers.append(request['harasser'])
            return {'choice': rc.WARBAND}
        return None
    st['decision_agent'] = agent
    result = winter_campaign_after_harvest(st)
    assert result['result']['executed'] and result['remaining_actions'] == 1
    assert len(campaigns) == 2
    assert harassers == expected
    assert st['current_card'] == current_card
    assert count_pieces(st, rc.ATREBATES, rc.ARVERNI, rc.WARBAND) == 2
    assert get_leader_in_region(st, rc.ATREBATES, rc.ARVERNI) == rc.VERCINGETORIX
    assert st['resources'][rc.ARVERNI] == 9
    assert validate_state(st) == []


@pytest.mark.parametrize('scenario,event,expected', [
    (rc.SCENARIO_GREAT_REVOLT, 4,
     (rc.ROMANS, rc.ARVERNI, rc.BELGAE, rc.AEDUI, rc.GERMANS)),
    (rc.SCENARIO_ARIOVISTUS, 4,
     (rc.ROMANS, rc.GERMANS, rc.BELGAE, rc.AEDUI, rc.ARVERNI)),
    (rc.SCENARIO_ARIOVISTUS, 'A63',
     (rc.BELGAE, rc.GERMANS, rc.ROMANS, rc.AEDUI, rc.ARVERNI)),
])
@pytest.mark.parametrize('winter', [None, rc.WINTER_CARD, 'W1'])
def test_harassment_order_uses_current_event_or_last_played_event_without_mutation(
        scenario, event, expected, winter):
    st = build_initial_state(scenario, seed=41)
    st['current_card'] = event if winter is None else winter
    st['played_cards'] = [1, rc.WINTER_CARD, event]
    if winter is not None:
        st['played_cards'].extend([rc.WINTER_CARD, winter])
    # Upcoming/undealt cards are not historical context, including when a
    # premature Winter is inserted into a deck rather than normally drawn.
    st['next_card'], st['deck'] = 2, [2, 3, 63]
    before = encode(deepcopy(st))
    assert get_harassment_order(st) == expected
    assert encode(st) == before


@pytest.mark.parametrize('scenario,expected', [
    (rc.SCENARIO_GREAT_REVOLT,
     (rc.BELGAE, rc.ARVERNI, rc.ROMANS, rc.AEDUI, rc.GERMANS)),
    (rc.SCENARIO_ARIOVISTUS,
     (rc.BELGAE, rc.GERMANS, rc.ROMANS, rc.AEDUI, rc.ARVERNI)),
])
def test_incomplete_legacy_history_uses_scenario_winter_campaign_fallback(scenario, expected):
    st = build_initial_state(scenario, seed=41)
    st['current_card'] = rc.WINTER_CARD
    # A history containing only Winter cards also has no recoverable Event.
    for history in (None, [], [rc.WINTER_CARD, 'W1']):
        if history is None:
            st.pop('played_cards', None)
        else:
            st['played_cards'] = history
        assert get_harassment_order(st) == expected


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
def test_all_pass_card_is_retained_through_winter_and_old_save_round_trip(scenario, tmp_path):
    import json
    st = build_initial_state(scenario, seed=41)
    st['deck'] = [4, rc.WINTER_CARD, 1]
    draw_card(st)
    result = resolve_card_turn(st, lambda *_: {'action': ACTION_PASS})
    assert len(result['passes']) == 4
    expected = get_harassment_order(st)
    advance_to_next_card(st)
    assert st['played_cards'] == [4, rc.WINTER_CARD]
    assert get_harassment_order(st) == expected
    path = tmp_path / 'historical-save.json'
    save_game(st, path)
    # Historical v1 saves have played_cards but no writer identity. No new
    # state field or migration is needed to recover their preceding Event.
    payload = json.loads(path.read_text())
    payload.pop('engine')
    path.write_text(json.dumps(payload))
    restored, _, _ = load_game(path, validate=True)
    assert get_harassment_order(restored) == expected
    assert encode(restored) == encode(st)


def test_interlude_deck_rebuild_starts_fresh_harassment_history():
    from fs_bot.engine.interlude import _build_pax_gallica_deck_for_interlude
    st = build_initial_state(rc.SCENARIO_GALLIC_WAR, seed=41)
    st['current_card'] = rc.WINTER_CARD
    st['played_cards'] = [4, rc.WINTER_CARD]
    # Winter Campaign precedes Interlude's step-10 deck replacement and uses
    # its first-half Event. The rebuild must not carry this into the new half.
    assert get_harassment_order(st) == (
        rc.ROMANS, rc.GERMANS, rc.BELGAE, rc.AEDUI, rc.ARVERNI)
    _build_pax_gallica_deck_for_interlude(st)
    assert st['played_cards'] == []
    st['scenario'] = rc.SCENARIO_PAX_GALLICA
    # The actual second-half draws supply history under base-game ordering.
    st['deck'] = [1, rc.WINTER_CARD]
    draw_card(st)
    resolve_card_turn(st, lambda *_: {'action': ACTION_PASS})
    advance_to_next_card(st)
    assert get_harassment_order(st) == (
        rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE, rc.GERMANS)


@pytest.mark.parametrize('scenario,seed', [
    (rc.SCENARIO_RECONQUEST, 75),
    (rc.SCENARIO_GREAT_REVOLT, 92),
    (rc.SCENARIO_GREAT_REVOLT, 96),
])
def test_batch_winter_campaign_harassment_crash_seeds_complete(scenario, seed):
    result = play_one((scenario, seed))
    assert result['completed'], result['errors']
    assert result['game_completed'] and result['audit_completed']
    assert result['errors'] == [] and result['integrity_findings'] == []
