"""Event prerequisites and exact targets through the accepted turn path."""

from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import is_controlled_by
from fs_bot.board.pieces import count_pieces, find_leader, get_leader_in_region, place_piece
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT
from fs_bot.engine.moves import validate_player_action
from fs_bot.engine.victory import calculate_victory_score
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state
from fs_bot.tools.seat_session import board_copy, validate_response


def board(scenario=rc.SCENARIO_GREAT_REVOLT, edition='original'):
    state = build_initial_state(scenario, seed=4)
    state['card_edition'] = edition
    return state


def play(state, card, params, *, shaded=False, actor=rc.BELGAE, rejected=False):
    state['current_card'] = card
    decision = {'action': ACTION_EVENT, 'player_action': {
        'command': rc.FIRST_DID_EVENT,
        'details': {'card_id': card, 'event_params': params,
                    'text_preference': rc.EVENT_SHADED if shaded else rc.EVENT_UNSHADED},
    }}
    validate_response(state, {'kind': 'turn', 'faction': actor,
                              'options': [ACTION_EVENT]}, decision)
    before = encode(board_copy(state))
    ok, info = validate_player_action(state, actor, decision['player_action'])
    assert ok is not rejected, info
    assert encode(board_copy(state)) == before
    result = execute_decision(state, actor, decision)
    if rejected:
        assert result['rejected'] and not result['executed'], result
        assert encode(board_copy(state)) == before
    else:
        assert result['executed'] and not result.get('errors'), result
    assert validate_state(state) == []
    assert check_structural_integrity(state) == []
    return result


def citadel(state, region, tribe, faction):
    place_piece(state, region, faction, rc.CITADEL)
    state['tribes'][tribe]['allied_faction'] = faction


def test_sacking_requires_the_executors_citadel():
    state = board()
    citadel(state, rc.SEQUANI, rc.TRIBE_SEQUANI, rc.AEDUI)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEGION, 2, from_legions_track=True)
    play(state, 23, {'target_region': rc.SEQUANI}, shaded=True, rejected=True)

    play(state, 23, {'target_region': rc.SEQUANI}, shaded=True, actor=rc.AEDUI)

    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.LEGION) == 1
    assert state['fallen_legions'] == 1
    assert state['eligibility'][rc.ROMANS] == rc.INELIGIBLE
    assert state['forced_ineligible'][rc.ROMANS] == 1


def test_assembly_drains_each_selected_gallic_faction_once():
    state = board()
    state['resources'].update({rc.ARVERNI: 20, rc.AEDUI: 20, rc.BELGAE: 7, rc.ROMANS: 20})

    play(state, 52, {'target_factions': [rc.ARVERNI, rc.BELGAE, rc.ARVERNI, rc.ROMANS]})

    assert state['resources'][rc.ARVERNI] == 12
    assert state['resources'][rc.BELGAE] == 0
    assert state['resources'][rc.AEDUI] == state['resources'][rc.ROMANS] == 20


@pytest.mark.parametrize('card,faction,name,origin,target', [
    (19, rc.ARVERNI, rc.VERCINGETORIX, rc.ARVERNI_REGION, rc.ARVERNI_REGION),
    (19, rc.ARVERNI, rc.VERCINGETORIX, None, rc.BRITANNIA),
    (56, rc.BELGAE, rc.AMBIORIX, rc.ATREBATES, rc.TREVERI),
    (56, rc.BELGAE, rc.AMBIORIX, rc.MORINI, rc.MORINI),
    (56, rc.BELGAE, rc.AMBIORIX, None, rc.SEQUANI),
])
def test_returned_leader_is_named_even_in_its_current_region(card, faction, name, origin, target):
    state = board()
    if origin is not None:
        place_piece(state, origin, faction, rc.LEADER, leader_name=rc.SUCCESSOR)

    play(state, card, {'target_region': target}, shaded=True)

    assert find_leader(state, faction) == target
    assert get_leader_in_region(state, target, faction) == name


@pytest.mark.parametrize('card,faction,name,origin,target', [
    (19, rc.ARVERNI, rc.VERCINGETORIX, rc.ARVERNI_REGION, rc.BRITANNIA),
    (56, rc.BELGAE, rc.AMBIORIX, rc.ATREBATES, rc.TREVERI),
])
def test_return_event_has_no_effect_with_named_leader_present(card, faction, name, origin, target):
    state = board()
    place_piece(state, origin, faction, rc.LEADER, leader_name=name)

    play(state, card, {'target_region': target}, shaded=True)

    assert find_leader(state, faction) == origin
    assert get_leader_in_region(state, origin, faction) == name


def test_ambiorix_return_rejects_britannia_before_removing_successor():
    state = board()
    place_piece(state, rc.MORINI, rc.BELGAE, rc.LEADER, leader_name=rc.SUCCESSOR)
    play(state, 56, {'target_region': rc.BRITANNIA}, shaded=True, rejected=True)


@pytest.mark.parametrize('score', [9, 10])
def test_flight_uses_the_belgic_control_allies_total(score):
    state = board()
    for region in (rc.MORINI, rc.ATREBATES, rc.CARNUTES):
        place_piece(state, region, rc.BELGAE, rc.WARBAND)
    assert _ally_tribe(state, rc.TRIBE_BELLOVACI, rc.BELGAE)
    citadel(state, rc.CARNUTES, rc.TRIBE_CARNUTES, rc.BELGAE)
    if score == 10:
        assert _ally_tribe(state, rc.TRIBE_MORINI, rc.BELGAE)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    assert calculate_victory_score(state, rc.BELGAE) == score
    assert not is_controlled_by(state, rc.CARNUTES, rc.ROMANS)

    play(state, 56, {})

    assert find_leader(state, rc.BELGAE) == (None if score == 9 else rc.CARNUTES)


def test_alaudae_checks_roman_control_before_placing_either_piece():
    state = board()
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    play(state, 7, {'target_region': rc.BRITANNIA}, rejected=True)

    play(state, 7, {'target_region': rc.PROVINCIA})

    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == 1
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 1


@pytest.mark.parametrize('edition,key', [('original', 'target_region'), ('second-edition', 'region')])
def test_numidians_checks_roman_leader_range_in_each_edition(edition, key):
    state = board(edition=edition)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.SUCCESSOR)
    play(state, 11, {key: rc.BRITANNIA}, rejected=True)

    play(state, 11, {key: rc.PROVINCIA})

    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 3


@pytest.mark.parametrize('card,shaded', [('A24', False), ('A24', True), ('A43', True)])
def test_event_structure_removals_preserve_the_sequani_citadel(card, shaded):
    state = board(rc.SCENARIO_ARIOVISTUS)
    citadel(state, rc.SEQUANI, rc.TRIBE_SEQUANI, rc.AEDUI)
    assert _ally_tribe(state, rc.TRIBE_HELVETII, rc.AEDUI)
    place_piece(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND, 20)
    if card == 'A43':
        citadel(state, rc.AEDUI_REGION, rc.TRIBE_AEDUI, rc.AEDUI)

    play(state, card, {}, shaded=shaded)

    assert count_pieces(state, rc.SEQUANI, rc.AEDUI, rc.CITADEL) == 1
    assert state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] == rc.AEDUI
    assert state['tribes'][rc.TRIBE_HELVETII]['allied_faction'] == rc.ARVERNI
    if card == 'A43':
        assert count_pieces(state, rc.AEDUI_REGION, rc.AEDUI, rc.CITADEL) == 0
        assert state['tribes'][rc.TRIBE_AEDUI]['allied_faction'] == rc.ARVERNI


@pytest.mark.parametrize('source,destination', [
    (rc.AEDUI, None), (rc.GERMANS, rc.BELGAE), (rc.BELGAE, rc.GERMANS),
])
def test_kinship_converts_only_between_belgae_and_germans(source, destination):
    state = board(rc.SCENARIO_ARIOVISTUS)
    tribes = (rc.TRIBE_MORINI, rc.TRIBE_MENAPII)
    place_piece(state, rc.MORINI, source, rc.WARBAND, 4)
    for tribe in tribes:
        assert _ally_tribe(state, tribe, source)
    params = {'from_faction': source,
              'warband_replacements': [{'region': rc.MORINI}] * 4,
              'ally_replacements': [{'tribe': tribe} for tribe in tribes]}

    play(state, 'A65', params, shaded=True, rejected=destination is None)

    owner = destination or source
    assert count_pieces(state, rc.MORINI, owner, rc.WARBAND) == 4
    assert all(state['tribes'][tribe]['allied_faction'] == owner for tribe in tribes)


@pytest.mark.parametrize('leader,new_ally', [(rc.CAESAR, rc.ROMANS), (rc.SUCCESSOR, rc.GERMANS)])
def test_procillus_requires_caesar_by_name(leader, new_ally):
    state = board(rc.SCENARIO_ARIOVISTUS)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=leader)
    assert _ally_tribe(state, rc.TRIBE_SEQUANI, rc.GERMANS)

    play(state, 'A19', {'replacements': [{'tribe': rc.TRIBE_SEQUANI}]})

    assert state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] == new_ally
    assert count_pieces(state, rc.SEQUANI, new_ally, rc.ALLY) == 1


def test_terminal_numidians_shows_only_regions_near_the_roman_leader(monkeypatch):
    from fs_bot.cli import human_plan
    from fs_bot.map.map_data import get_adjacent_for_state

    state = board(edition='second-edition')
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    monkeypatch.setattr(human_plan, 'prompt_yes_no', lambda *args, **kw: False)

    def choose(stdin, stdout, prompt, choices):
        assert {region for _, region in choices} == {
            rc.SEQUANI, *get_adjacent_for_state(state, rc.SEQUANI, rc.ROMANS)}
        return rc.PROVINCIA

    monkeypatch.setattr(human_plan, 'prompt_choice', choose)
    assert human_plan._collect_event_params(
        state, rc.BELGAE, 11, False, StringIO(), StringIO()) == {'region': rc.PROVINCIA}
