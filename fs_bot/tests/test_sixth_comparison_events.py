"""Sixth comparison audit: Event completeness and non-player choices."""

from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, find_leader, get_available,
    get_leader_in_region, place_piece, remove_piece,
)
from fs_bot.bots.bot_common import should_decline_event
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.cards.boii import eligible_allies
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cards.event_eval import is_event_effective
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT, ACTION_PASS, ActionRejected, _action_transaction
from fs_bot.engine.moves import validate_player_action
from fs_bot.map.map_data import get_adjacent_for_state, get_playable_regions_for_state
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


TRIBE = rc.TRIBE_CATUVELLAUNI
BRITANNIA_REMOVAL = {'type': 'ally', 'tribe': TRIBE}


def clean(state):
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.FORT) == 1
    assert validate_state(state) == check_structural_integrity(state) == []


def position(card, scenario=rc.SCENARIO_GREAT_REVOLT):
    state = build_initial_state(scenario, seed=1)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    state.update(current_card=card, current_card_id=card, can_play_event=True,
                 non_player_factions=set())
    for faction in state['resources']:
        if faction != rc.ARVERNI or scenario not in rc.ARIOVISTUS_SCENARIOS:
            state['resources'][faction] = 10
    clean(state)
    return state


def human_event(card, params, *, shaded=True):
    return {'action': ACTION_EVENT, 'player_action': {
        'command': rc.FIRST_DID_EVENT, 'details': {
            'card_id': card, 'event_params': params,
            'text_preference': rc.EVENT_SHADED if shaded else rc.EVENT_UNSHADED}}}


def bot_event(state, faction, card):
    state.update(current_card=card, current_card_id=card, can_play_event=True)
    state.setdefault('non_player_factions', set()).add(faction)
    clean(state)
    action = dispatch_bot_turn(state, faction)
    assert action['command'] == rc.FIRST_DID_EVENT, action
    result = execute_decision(state, faction, {'action': ACTION_EVENT, 'bot_action': action})
    assert result['executed'] and not result.get('errors'), result
    clean(state)


@pytest.mark.parametrize('params,choice', [
    ({}, 'Ally or Dispersed marker'),
    ({'ally_tribe': TRIBE, 'ally_faction': rc.BELGAE}, 'Ally or Dispersed marker'),
    ({'removal': BRITANNIA_REMOVAL}, 'Gallic Ally'),
    ({'removal': BRITANNIA_REMOVAL, 'ally_tribe': TRIBE, 'ally_faction': rc.ROMANS},
     'Gallic Ally'),
])
def test_britannia_required_choices_rollback_before_optional_warbands(params, choice):
    state = position(57)
    assert _ally_tribe(state, TRIBE, rc.ROMANS)
    clean(state)
    before = encode(board_copy(state))
    response = human_event(57, dict(params, warband_faction=rc.BELGAE, warband_count=1))
    ok, preview = validate_player_action(state, rc.BELGAE, response['player_action'])
    assert not ok and choice in preview['reason'], preview
    assert encode(board_copy(state)) == before
    result = execute_decision(state, rc.BELGAE, response)
    assert result['rejected'] and choice in result['reason'], result
    assert encode(board_copy(state)) == before
    clean(state)


def test_britannia_removes_ally_even_when_no_gallic_ally_can_replace_it():
    state = position(57)
    assert _ally_tribe(state, TRIBE, rc.ROMANS)
    regions = tuple(r for r in get_playable_regions_for_state(state) if r != rc.BRITANNIA)
    for faction in rc.GALLIC_FACTIONS:
        count = get_available(state, faction, rc.ALLY)
        for tribe in eligible_allies(state, regions, faction)[:count]:
            assert _ally_tribe(state, tribe, faction)
        assert get_available(state, faction, rc.ALLY) == 0
    clean(state)
    result = execute_decision(state, rc.BELGAE, human_event(57, {'removal': BRITANNIA_REMOVAL}))
    assert result['executed'], result
    assert state['tribes'][TRIBE]['allied_faction'] is None
    assert not count_pieces(state, rc.BRITANNIA, rc.ROMANS)
    assert not count_pieces(state, rc.BRITANNIA, rc.BELGAE)
    clean(state)


def test_britannia_durable_turn_can_correct_missing_ally_after_reload(tmp_path):
    from fs_bot.cli.display import HumanTurnDisplay

    state = position(57)
    assert _ally_tribe(state, TRIBE, rc.ROMANS)
    before = encode(board_copy(state))
    request = {'kind': 'turn', 'options': [ACTION_EVENT], 'position': '1st_eligible'}
    incomplete = human_event(57, {'removal': BRITANNIA_REMOVAL, 'warband_faction': rc.BELGAE,
                                  'warband_count': 1})
    complete = human_event(57, {'removal': BRITANNIA_REMOVAL, 'ally_tribe': TRIBE,
                                'ally_faction': rc.AEDUI})

    def step(session):
        def driver(*args):
            return None

        driver.transaction_checkpoint = session.checkpoint
        driver.transaction_restore = session.restore
        with _action_transaction(session.state, driver):
            response = session.ask(session.state, rc.BELGAE, request)
            result = execute_decision(session.state, rc.BELGAE, response)
            if result.get('rejected'):
                raise ActionRejected(result)
        session.finish()
        return result

    session = SeatSession(state, {'seat': rc.BELGAE}, [], HumanTurnDisplay(StringIO()))
    with pytest.raises(DecisionPending):
        step(session)
    pending = session.data['pending']['id']
    session.import_inbox({'decision_id': pending, 'response': incomplete})
    with pytest.raises(ActionRejected, match='Gallic Ally'):
        step(session)
    assert session.data['pending']['id'] == pending
    assert not session.log and not session.data['journal']
    assert encode(board_copy(state)) == before

    path = tmp_path / 'britannia.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = SeatSession(restored, meta, log, HumanTurnDisplay(StringIO()))
    resumed.import_inbox({'decision_id': pending, 'response': complete})
    assert step(resumed)['executed']
    assert resumed.data['pending'] is None
    assert len(log) == 1
    assert decode(log[0]['assistant_response']) == complete
    assert restored['tribes'][TRIBE]['allied_faction'] == rc.AEDUI
    assert count_pieces(restored, rc.BRITANNIA, rc.BELGAE, rc.WARBAND) == 0
    replay = decode(before)
    assert execute_decision(replay, rc.BELGAE, decode(log[0]['assistant_response']))['executed']
    assert encode(board_copy(replay)) == encode(board_copy(restored))
    clean(restored)


def test_belgae_select_a_britannia_ally_gain_and_maximum_available_warbands():
    state = position(57)
    assert _ally_tribe(state, TRIBE, rc.ROMANS)
    bot_event(state, rc.BELGAE, 57)
    assert state['tribes'][TRIBE]['allied_faction'] == rc.BELGAE
    assert count_pieces(state, rc.BRITANNIA, rc.ROMANS, rc.ALLY) == 0
    assert count_pieces(state, rc.BRITANNIA, rc.BELGAE, rc.WARBAND) == 4


def test_belgae_decline_britannia_when_they_can_only_restore_their_existing_ally():
    state = position(57)
    state['non_player_factions'].add(rc.BELGAE)
    assert _ally_tribe(state, TRIBE, rc.BELGAE)
    before = encode(state)
    assert should_decline_event(state, 57, rc.BELGAE)
    assert encode(state) == before


def test_german_nasua_places_seven_available_warbands_and_a_settlement():
    state = setup_scenario(rc.SCENARIO_ARIOVISTUS, seed=1)
    near = set(rc.GERMANIA_REGIONS)
    for region in rc.GERMANIA_REGIONS:
        near.update(get_adjacent_for_state(state, region, rc.GERMANS))
    regions = get_playable_regions_for_state(state, rc.GERMANS)
    before = {r: (count_pieces(state, r, rc.GERMANS, rc.WARBAND),
                  count_pieces(state, r, rc.GERMANS, rc.SETTLEMENT)) for r in regions}
    assert get_available(state, rc.GERMANS, rc.WARBAND) == 7
    bot_event(state, rc.GERMANS, 'A35')
    assert get_available(state, rc.GERMANS, rc.WARBAND) == 0
    changed = [r for r in regions if before[r] != (
        count_pieces(state, r, rc.GERMANS, rc.WARBAND),
        count_pieces(state, r, rc.GERMANS, rc.SETTLEMENT))]
    assert len(changed) == 1 and changed[0] in near
    region = changed[0]
    assert count_pieces(state, region, rc.GERMANS, rc.WARBAND) == before[region][0] + 7
    assert before[region][1] == 0 and count_pieces(state, region, rc.GERMANS, rc.SETTLEMENT) == 1


@pytest.mark.parametrize('faction,troop,count', [(rc.ROMANS, rc.AUXILIA, 4),
                                                 (rc.AEDUI, rc.WARBAND, 8)])
def test_unshaded_nasua_uses_the_nonplayers_own_ally_and_troops(faction, troop, count):
    state = position('A35', rc.SCENARIO_ARIOVISTUS)
    bot_event(state, faction, 'A35')
    assert state['tribes'][rc.TRIBE_TREVERI]['allied_faction'] == faction
    assert count_pieces(state, rc.TREVERI, faction, troop) == count


def test_roman_bot_declines_nasua_when_fewer_than_four_auxilia_are_available():
    state = position('A35', rc.SCENARIO_ARIOVISTUS)
    state['non_player_factions'].add(rc.ROMANS)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA,
                get_available(state, rc.ROMANS, rc.AUXILIA) - 3)
    before = encode(state)
    assert should_decline_event(state, 'A35', rc.ROMANS)
    assert encode(state) == before
    assert dispatch_bot_turn(state, rc.ROMANS)['command'] != rc.FIRST_DID_EVENT

    state['non_player_factions'].remove(rc.ROMANS)
    result = execute_decision(state, rc.ROMANS, human_event('A35', {
        'ally_faction': rc.ROMANS, 'piece_faction': rc.ROMANS,
        'piece_type': rc.AUXILIA, 'count': 2}, shaded=False))
    assert result['executed'], result
    assert count_pieces(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA) == 2
    clean(state)


@pytest.mark.parametrize('warbands_available', [True, False])
def test_belgic_iccius_replaces_remi_then_hidden_auxilia_up_to_five(warbands_available):
    state = position('A60', rc.SCENARIO_ARIOVISTUS)
    assert _ally_tribe(state, rc.TRIBE_REMI, rc.ROMANS)
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, 2, piece_state=rc.REVEALED)
    if not warbands_available:
        place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND,
                    get_available(state, rc.BELGAE, rc.WARBAND))
    bot_event(state, rc.BELGAE, 'A60')
    assert state['tribes'][rc.TRIBE_REMI]['allied_faction'] == rc.BELGAE
    assert count_pieces_by_state(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 0
    assert count_pieces_by_state(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 2
    assert count_pieces(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND) == (4 if warbands_available else 0)


def test_belgae_decline_iccius_without_roman_replacement_targets_at_atrebates():
    state = position('A60', rc.SCENARIO_ARIOVISTUS)
    state['non_player_factions'].add(rc.BELGAE)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA)
    assert should_decline_event(state, 'A60', rc.BELGAE)


@pytest.mark.parametrize('leader', [rc.AMBIORIX, rc.SUCCESSOR, None])
def test_flight_event_selection_uses_the_live_leader_identity(leader):
    state = setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=1)
    state.update(current_card=56, current_card_id=56, can_play_event=True,
                 non_player_factions={rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE})
    origin = find_leader(state, rc.BELGAE)
    assert get_leader_in_region(state, origin, rc.BELGAE) == rc.AMBIORIX
    if leader != rc.AMBIORIX:
        remove_piece(state, origin, rc.BELGAE, rc.LEADER)
        if leader is not None:
            place_piece(state, origin, rc.BELGAE, rc.LEADER, leader_name=leader)
    clean(state)
    before = encode(state)
    effective = leader != rc.AMBIORIX
    assert is_event_effective(state, 56, shaded=True) == effective
    assert should_decline_event(state, 56, rc.BELGAE) != effective
    assert encode(state) == before
    if not effective:
        assert dispatch_bot_turn(state, rc.BELGAE)['command'] not in (rc.FIRST_DID_EVENT, ACTION_PASS)
    else:
        bot_event(state, rc.BELGAE, 56)
        assert get_leader_in_region(state, find_leader(state, rc.BELGAE), rc.BELGAE) == rc.AMBIORIX
