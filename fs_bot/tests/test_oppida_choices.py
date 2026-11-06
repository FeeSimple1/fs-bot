"""Oppida plans with named Cities and live post-placement Citadel options."""
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, get_available, place_piece
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cards.oppida import ally_options
from fs_bot.cards.param_schema import card_param_schema, kind_values
from fs_bot.cli.base_event_limits import collect_params
from fs_bot.cli.human_plan import _collect_event_params
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import board_copy


def position():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=28)
    state.update(current_card=28, current_card_id=28, event_params=None, executing_faction=None)
    return state


def play(state, params, *, faction=rc.ROMANS, shaded=False):
    action = {'command': rc.FIRST_DID_EVENT, 'regions': [], 'details': {
        'card_id': 28, 'text_preference': rc.EVENT_SHADED if shaded else rc.EVENT_UNSHADED,
        'event_params': params}}
    return execute_decision(state, faction, {'action': ACTION_EVENT, 'player_action': action})


@pytest.mark.parametrize('card,key,expected_kind,cities', [
    (23, 'target_city', 'city', tuple(rc.CITY_TO_TRIBE)),
    (28, 'citadel_upgrades', 'list:city', tuple(rc.CITY_TO_TRIBE)),
    (68, 'target_city', 'city', (rc.CITY_ALESIA, rc.CITY_CENABUM)),
])
def test_city_schema_exposes_city_names_instead_of_tribe_names(card, key, expected_kind, cities):
    state = position()
    spec = card_param_schema(card, state['scenario'])[key]
    assert spec['kind'] == expected_kind
    assert kind_values(state, 'city', spec) == list(cities)


@pytest.mark.parametrize('shaded', [False, True])
def test_terminal_upgrades_existing_bibracte_ally_even_under_roman_control(shaded):
    state = position()
    assert _ally_tribe(state, rc.TRIBE_AEDUI, rc.AEDUI)
    place_piece(state, rc.AEDUI_REGION, rc.ROMANS, rc.FORT)
    place_piece(state, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA, 2)
    before = encode(board_copy(state))
    output = StringIO()
    params = _collect_event_params(state, rc.ROMANS, 28, shaded, StringIO('1\nboard\n2\n'), output)
    assert encode(board_copy(state)) == before
    assert f'{rc.CITY_BIBRACTE} ({rc.AEDUI})' in output.getvalue()
    assert params == {'ally_placements': [], 'citadel_upgrades': [rc.CITY_BIBRACTE]}
    assert play(state, params, shaded=shaded)['executed']
    assert count_pieces(state, rc.AEDUI_REGION, rc.AEDUI, rc.CITADEL) == 1
    assert state['tribes'][rc.TRIBE_AEDUI]['allied_faction'] == rc.AEDUI
    assert validate_state(state) == []


def test_menu_offers_citadel_in_the_city_selected_in_the_previous_step():
    state = position()
    position_in_menu = ally_options(state).index((rc.CITY_BIBRACTE, rc.AEDUI)) + 2
    params = _collect_event_params(state, rc.ROMANS, 28, False,
                                   StringIO(f'{position_in_menu}\n1\n2\n'), StringIO())
    assert params == {'ally_placements': [{'tribe': rc.TRIBE_AEDUI, 'faction': rc.AEDUI}],
                      'citadel_upgrades': [rc.CITY_BIBRACTE]}
    before = get_available(state, rc.AEDUI, rc.ALLY)
    assert play(state, params)['executed']
    assert get_available(state, rc.AEDUI, rc.ALLY) == before
    assert count_pieces(state, rc.AEDUI_REGION, rc.AEDUI, rc.CITADEL) == 1
    assert validate_state(state) == []


def test_placements_respect_city_control_tribe_stacking_and_marker_status():
    state = position()
    state['tribes'][rc.TRIBE_CARNUTES]['status'] = rc.MARKER_DISPERSED
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.FORT)
    options = ally_options(state)
    assert (rc.CITY_BIBRACTE, rc.AEDUI) in options
    assert (rc.CITY_BIBRACTE, rc.BELGAE) not in options
    assert not any(city in (rc.CITY_CENABUM, rc.CITY_VESONTIO) for city, _ in options)
    params = {'ally_placements': [
        {'tribe': rc.TRIBE_AEDUI, 'faction': rc.BELGAE},
        {'tribe': rc.TRIBE_CARNUTES, 'faction': rc.AEDUI},
        {'tribe': rc.TRIBE_SEQUANI, 'faction': rc.ARVERNI}]}
    before = encode(board_copy(state))
    assert play(state, params)['executed']
    assert encode(board_copy(state)) == before


def test_timed_reclamation_opens_a_city_upgrade_and_replays_at_the_same_step(monkeypatch):
    from fs_bot.cli import voluntary_removal

    state = position()
    state['_cli_action_windows'] = True
    assert _ally_tribe(state, rc.TRIBE_AEDUI, rc.AEDUI)
    assert _ally_tribe(state, rc.TRIBE_CARNUTES, rc.AEDUI)
    assert _ally_tribe(state, rc.TRIBE_MANDUBII, rc.AEDUI)
    assert play(state, {'citadel_upgrades': [rc.CITY_CENABUM, rc.CITY_ALESIA]})['executed']
    assert get_available(state, rc.AEDUI, rc.CITADEL) == 0
    before = encode(board_copy(state))
    operation = {'action': 'remove', 'region': rc.CARNUTES, 'piece_type': rc.CITADEL,
                 'tribe': rc.TRIBE_CARNUTES, 'count': 1}

    def removals(board, faction, request, stdin, stdout):
        window = request['window']
        if window['step'] == '28.citadels' and window['index'] == 0:
            return {'operations': [operation]}
        return {'done': True}

    monkeypatch.setattr(voluntary_removal, 'collect_removals', removals)
    params = collect_params(state, rc.AEDUI, 28, False, StringIO('1\n2\n'), StringIO())
    assert encode(board_copy(state)) == before
    assert params['citadel_upgrades'] == [rc.CITY_BIBRACTE]
    assert params['stage_timing_actions']['28.citadels:0'] == [
        {'kind': 'voluntary_removal', 'response': {'operations': [operation]}}]
    assert play(state, params, faction=rc.AEDUI)['executed']
    assert state['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] is None
    assert count_pieces(state, rc.AEDUI_REGION, rc.AEDUI, rc.CITADEL) == 1
    assert validate_state(state) == []
