"""Human Event menus plan timing against completed effects, without live mutation."""
from copy import deepcopy
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, get_available, place_piece
from fs_bot.cards.all_gaul_gathers import collect_params
from fs_bot.cards.card_effects import _ally_tribe, execute_event
from fs_bot.cards.event_preview import preview_event_prefix
from fs_bot.cards.param_schema import card_param_schema
from fs_bot.cli import human_plan, menus, voluntary_removal
from fs_bot.engine.action_windows import scope
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import board_copy


def _enable(state):
    def agent(*args):
        pytest.fail('Planning consumed a live reactive answer')
    agent.supports_action_windows = True
    state['decision_agent'] = agent


def _execute(state, faction, card, params):
    state.pop('decision_agent', None)
    state['executing_faction'] = faction
    state['event_params'] = params
    with scope(state, actor=faction, plan=params, force=True):
        execute_event(state, card)


def test_prefix_runs_previous_placement_but_stops_before_later_resources():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=40)
    state['resources'][rc.AEDUI] = 3
    _enable(state)
    before = encode(board_copy(state))
    params = {'placements': [{'region': rc.SEQUANI, 'piece_type': rc.WARBAND,
                              'faction': rc.AEDUI, 'count': 2}]}
    sim = preview_event_prefix(state, rc.AEDUI, 40, False, params,
                               step='40.placements', index=1)
    assert count_pieces(sim, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == 2
    assert sim['resources'][rc.AEDUI] == 3  # Card's later +4 has not happened.
    assert sim['rng'].getstate() == state['rng'].getstate()
    assert '_action_window_preview_checkpoint' not in sim and 'decision_agent' not in sim
    assert sim['_diviciacus_preview'] is True
    assert encode(board_copy(state)) == before
    assert params == {'placements': [{'region': rc.SEQUANI, 'piece_type': rc.WARBAND,
                                     'faction': rc.AEDUI, 'count': 2}]}


def test_prefix_checkpoint_precedes_the_next_entry_timing_and_survives_atomic_event():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=37)
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 4)
    params = {'target_region': rc.SEQUANI, 'ally_placements': [
        {'tribe': rc.TRIBE_SEQUANI, 'faction': rc.AEDUI},
        {'tribe': rc.TRIBE_HELVETII, 'faction': rc.AEDUI,
         'timing_actions': [{'kind': 'voluntary_removal', 'response': {'invalid': True}}]}],
        'moves': []}
    before = encode(state)
    sim = preview_event_prefix(state, rc.AEDUI, 'A37', False, params,
                               step='A37.allies', index=1)
    assert sim['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] == rc.AEDUI
    assert sim['tribes'][rc.TRIBE_HELVETII]['allied_faction'] is None
    assert encode(state) == before


def test_wrapped_event_loops_keep_typed_fields_step_names_and_limits():
    schema = card_param_schema(40, rc.SCENARIO_GREAT_REVOLT)['placements']
    assert schema['kind'] == 'entries'
    assert schema['entry_fields']['piece_type'] == 'piece_type'
    assert schema['event_step'] == '40.placements'
    limited = card_param_schema('A45', rc.SCENARIO_ARIOVISTUS)['placements']
    assert limited['kind'] == 'entries' and limited['max_entries'] == 3


def test_a37_menu_can_free_an_ally_before_computing_placement_options(monkeypatch):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=37)
    state['current_card'] = 'A37'
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 4)
    occupied = []
    for tribe in state['tribes']:
        if tribe in (rc.TRIBE_SEQUANI, rc.TRIBE_HELVETII):
            continue
        if get_available(state, rc.AEDUI, rc.ALLY) and _ally_tribe(state, tribe, rc.AEDUI):
            occupied.append(tribe)
    assert get_available(state, rc.AEDUI, rc.ALLY) == 0
    removed, placed = False, False
    def choose(stdin, stdout, prompt, choices):
        nonlocal removed, placed
        if prompt.startswith('A37: select'):
            return rc.SEQUANI
        if prompt == 'Voluntary removal?':
            if not removed:
                removed = True
                return next(value for _, value in choices if isinstance(value, dict)
                            and value.get('tribe') == occupied[0])
            return 'done'
        if prompt.startswith('A37: place'):
            if not placed:
                placed = True
                assert (rc.TRIBE_SEQUANI, rc.AEDUI) in [value for _, value in choices]
                return (rc.TRIBE_SEQUANI, rc.AEDUI)
            return None
        raise AssertionError(prompt)
    monkeypatch.setattr(menus, 'prompt_choice', choose)
    monkeypatch.setattr(voluntary_removal, 'prompt_choice', choose)
    _enable(state)
    before = encode(board_copy(state))
    params = collect_params(state, rc.AEDUI, False, io.StringIO(), io.StringIO())
    assert encode(board_copy(state)) == before
    assert params['ally_placements'][0]['timing_actions'][0]['kind'] == 'voluntary_removal'
    _execute(state, rc.AEDUI, 'A37', params)
    assert state['tribes'][occupied[0]]['allied_faction'] is None
    assert state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] == rc.AEDUI
    assert get_available(state, rc.AEDUI, rc.ALLY) == 0
    assert validate_state(state) == []


def test_generic_menu_can_remove_a_just_placed_piece_for_a_later_placement(monkeypatch):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=40)
    state['current_card'] = 40
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND,
                get_available(state, rc.AEDUI, rc.WARBAND))
    assert get_available(state, rc.AEDUI, rc.WARBAND) == 0
    _enable(state)
    before = encode(board_copy(state))
    entries, removal_count, batch_done = 0, 0, False
    def yes_no(stdin, stdout, prompt, default=False):
        nonlocal entries, batch_done
        if prompt == 'Use them?':
            return False
        assert prompt == 'Add a placements entry?'
        if entries == 2:
            return False
        entries += 1
        batch_done = False
        return True
    def choose(stdin, stdout, prompt, choices):
        nonlocal removal_count, batch_done
        if prompt == 'Voluntary removal?':
            if batch_done:
                return 'done'
            batch_done = True
            removal_count += 1
            origin = rc.CARNUTES if removal_count == 1 else rc.SEQUANI
            return next(value for _, value in choices if isinstance(value, dict)
                        and value['region'] == origin and value['piece_type'] == rc.WARBAND)
        if prompt == 'How many pieces?':
            return 3 if removal_count == 1 else 1
        values = {'  region:': rc.SEQUANI if entries == 1 else rc.UBII,
                  '  piece_type:': rc.WARBAND, '  count:': 2,
                  '  faction:': rc.AEDUI, '  tribe:': rc.TRIBE_SEQUANI}
        assert prompt in values, prompt
        return values[prompt]
    monkeypatch.setattr(human_plan, 'prompt_yes_no', yes_no)
    monkeypatch.setattr(human_plan, 'prompt_choice', choose)
    monkeypatch.setattr(voluntary_removal, 'prompt_choice', choose)
    params = human_plan._collect_event_params(state, rc.AEDUI, 40, False,
                                             io.StringIO(), io.StringIO())
    assert encode(board_copy(state)) == before
    assert len(params['placements']) == 2 and removal_count == 2
    assert all('timing_actions' in entry for entry in params['placements'])
    _execute(state, rc.AEDUI, 40, params)
    assert count_pieces(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == 1
    assert count_pieces(state, rc.UBII, rc.AEDUI, rc.WARBAND) == 2
    assert state['resources'][rc.AEDUI] == 4
    assert validate_state(state) == []


def test_generic_menu_finishes_an_exhausted_quota_and_retains_confirmed_tail(monkeypatch):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=30)
    place_piece(state, rc.VENETI, rc.GERMANS, rc.WARBAND)
    _enable(state)
    before = encode(board_copy(state))
    number, removed = 0, False
    def yes_no(stdin, stdout, prompt, default=False):
        nonlocal number
        number += 1
        assert number <= 2, 'Exhausted entry collection did not finish'
        return True
    def choose(stdin, stdout, prompt, choices):
        nonlocal removed
        if prompt == 'Voluntary removal?':
            if number == 2 and not removed:
                removed = True
                return next(value for _, value in choices if isinstance(value, dict)
                            and value['region'] == rc.VENETI)
            return 'done'
        values = {'  region:': rc.SEQUANI, '  piece_type:': rc.WARBAND,
                  '  count:': 9 if number == 1 else 1, '  tribe:': rc.TRIBE_SEQUANI}
        return values[prompt]
    monkeypatch.setattr(human_plan, 'prompt_yes_no', yes_no)
    monkeypatch.setattr(human_plan, 'prompt_choice', choose)
    monkeypatch.setattr(voluntary_removal, 'prompt_choice', choose)
    params = {}
    params['placements'] = human_plan._collect_timed_event_entries(
        state, rc.GERMANS, 'A30', True, params, 'placements',
        card_param_schema('A30', state['scenario'])['placements'], io.StringIO(), io.StringIO())
    assert len(params['placements']) == 1 and number == 2
    assert 'A30.placements:1' in params['stage_timing_actions']
    assert encode(board_copy(state)) == before
    state.pop('decision_agent')
    state['executing_faction'], state['event_params'] = rc.GERMANS, params
    with scope(state, actor=rc.GERMANS, plan=params, force=True):
        execute_event(state, 'A30', shaded=True)
    assert count_pieces(state, rc.VENETI, rc.GERMANS, rc.WARBAND) == 0
    assert count_pieces(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND) == 9
    assert validate_state(state) == []
