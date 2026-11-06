"""Shaded Card 57 authors a legal Britannia removal and its later placements."""
import random
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, get_available, place_piece
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cards.land_of_mist import removal_options
from fs_bot.cards.param_schema import card_param_schema, generate_params, kind_values
from fs_bot.cli.human_plan import _collect_event_params
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import board_copy


TRIBE = rc.TRIBE_CATUVELLAUNI


def position():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=57)
    state.update(current_card=57, current_card_id=57, event_params=None, executing_faction=None)
    return state


def collect(state, choices, output=None):
    return _collect_event_params(state, rc.BELGAE, 57, True, StringIO(choices),
                                 output if output is not None else StringIO())


def play(state, params):
    action = {'command': rc.FIRST_DID_EVENT, 'regions': [], 'details': {
        'card_id': 57, 'text_preference': rc.EVENT_SHADED, 'event_params': params}}
    return execute_decision(state, rc.BELGAE, {'action': ACTION_EVENT, 'player_action': action})


def test_schema_generates_exact_removal_objects_and_none_when_empty():
    state = position()
    spec = card_param_schema(57, state['scenario'])['removal']
    assert kind_values(state, spec['kind'], spec) == [None]
    assert _ally_tribe(state, TRIBE, rc.ROMANS)
    expected = {'type': 'ally', 'tribe': TRIBE}
    assert kind_values(state, spec['kind'], spec) == [expected]
    params = generate_params(state, 57, random.Random(57), include_p=1.0)
    assert params['removal'] == expected
    expansion = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=57)
    assert 'removal' not in card_param_schema('A57', expansion['scenario'])
    assert removal_options(expansion) == []


@pytest.mark.parametrize('status', [None, rc.MARKER_DISPERSED, rc.MARKER_DISPERSED_GATHERING])
def test_terminal_removes_the_selected_piece_then_places_different_gallic_factions(status):
    state = position()
    if status is None:
        assert _ally_tribe(state, TRIBE, rc.ROMANS)
    else:
        state['tribes'][TRIBE]['status'] = status
    before = encode(board_copy(state))
    output = StringIO()
    params = collect(state, 'board\n1\n2\n4\n3\n', output)
    assert encode(board_copy(state)) == before
    label = f'{rc.ROMANS} Ally' if status is None else status
    assert f'Remove {label} at {TRIBE}' in output.getvalue()
    assert params == {'removal': {'type': 'ally' if status is None else 'dispersed', 'tribe': TRIBE},
                      'ally_tribe': TRIBE, 'ally_faction': rc.AEDUI,
                      'warband_faction': rc.BELGAE, 'warband_count': 3}
    assert play(state, params)['executed']
    assert state['tribes'][TRIBE]['status'] is None
    assert state['tribes'][TRIBE]['allied_faction'] == rc.AEDUI
    assert count_pieces(state, rc.BRITANNIA, rc.ROMANS, rc.ALLY) == 0
    assert count_pieces(state, rc.BRITANNIA, rc.BELGAE, rc.WARBAND) == 3
    assert validate_state(state) == []


def test_colony_and_original_tribe_are_distinct_removal_targets():
    state = position()
    from fs_bot.cards.card_effects import execute_event
    colony = f'Colony_{rc.BRITANNIA}'
    state.update(event_params={'region': rc.BRITANNIA}, executing_faction=rc.BELGAE)
    execute_event(state, 71, shaded=True)
    assert state['tribes'][colony]['allied_faction'] == rc.BELGAE
    assert _ally_tribe(state, TRIBE, rc.ROMANS)
    expected = {'type': 'ally', 'tribe': colony}
    choice = removal_options(state).index(expected) + 1
    params = collect(state, f'{choice}\n2\n1\n')
    assert params['removal'] == expected
    assert params['ally_tribe'] == colony and params['ally_faction'] == rc.AEDUI
    assert play(state, params)['executed']
    assert state['tribes'][TRIBE]['allied_faction'] == rc.ROMANS
    assert state['tribes'][colony]['allied_faction'] == rc.AEDUI
    assert validate_state(state) == []


@pytest.mark.parametrize('target', [
    rc.BRITANNIA,
    {'type': 'ally', 'tribe': rc.TRIBE_MORINI},
    {'type': 'dispersed', 'tribe': rc.TRIBE_MENAPII},
    {'type': 'dispersed', 'tribe': TRIBE},
])
def test_invalid_removal_is_rejected_without_applying_later_placements(target):
    state = position()
    assert _ally_tribe(state, rc.TRIBE_MORINI, rc.BELGAE)
    state['tribes'][rc.TRIBE_MENAPII]['status'] = rc.MARKER_DISPERSED
    state['tribes'][TRIBE]['status'] = rc.MARKER_RAZED
    before = encode(board_copy(state))
    result = play(state, {'removal': target, 'warband_faction': rc.BELGAE, 'warband_count': 4})
    assert result['rejected']
    assert encode(board_copy(state)) == before


def test_no_target_skips_removal_and_limits_warband_quantities_to_available():
    state = position()
    for faction in (rc.ARVERNI, rc.BELGAE):
        place_piece(state, rc.ATREBATES, faction, rc.WARBAND, get_available(state, faction, rc.WARBAND))
    place_piece(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND, get_available(state, rc.AEDUI, rc.WARBAND) - 2)
    output = StringIO()
    params = collect(state, '1\n2\n2\n', output)
    assert 'which Ally or Dispersed marker' not in output.getvalue()
    assert 'removal' not in params
    assert params['warband_faction'] == rc.AEDUI and params['warband_count'] == 2
    assert play(state, params)['executed']
    assert count_pieces(state, rc.BRITANNIA, rc.AEDUI, rc.WARBAND) == 2
    assert validate_state(state) == []


def test_timing_updates_the_removal_pool_and_replays_before_placement(monkeypatch):
    from fs_bot.cli import voluntary_removal

    state = position()
    state['_cli_action_windows'] = True
    assert _ally_tribe(state, TRIBE, rc.BELGAE)
    before = encode(board_copy(state))
    operation = {'action': 'remove', 'region': rc.BRITANNIA, 'piece_type': rc.ALLY,
                 'tribe': TRIBE, 'count': 1}

    def removals(board, faction, request, stdin, stdout):
        return ({'operations': [operation]} if request['window']['step'] == '57.removal'
                else {'done': True})

    monkeypatch.setattr(voluntary_removal, 'collect_removals', removals)
    params = collect(state, '2\n1\n')
    assert encode(board_copy(state)) == before
    assert 'removal' not in params
    assert params['stage_timing_actions']['57.removal'] == [
        {'kind': 'voluntary_removal', 'response': {'operations': [operation]}}]
    assert play(state, params)['executed']
    assert state['tribes'][TRIBE]['allied_faction'] == rc.AEDUI
    assert count_pieces(state, rc.BRITANNIA, rc.BELGAE, rc.ALLY) == 0
    assert validate_state(state) == []
