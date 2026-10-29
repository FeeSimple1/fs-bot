"""Humans can exercise scoped Event grants without a silent bot choice."""
import io
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.cli.free_actions import collect_free_action
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.free_actions import execute_free_action_plan
from fs_bot.state.state_schema import build_initial_state


def _state():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=7)
    state['non_player_factions'] = set()
    return state


def _collect(state, faction, request, lines):
    out = io.StringIO()
    before = deepcopy({k: v for k, v in state.items() if k not in ('rng', 'decision_agent')})
    rng = state['rng'].getstate()
    result = collect_free_action(state, faction, request,
                                io.StringIO('\n'.join(lines) + '\n'), out)
    assert {k: v for k, v in state.items() if k not in ('rng', 'decision_agent')} == before
    assert state['rng'].getstate() == rng
    return result, out.getvalue()


@pytest.mark.parametrize('faction', [rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE])
def test_acco_menu_allows_empty_devastated_enemy_controlled_region(faction):
    state = _state()
    enemy = rc.BELGAE if faction != rc.BELGAE else rc.AEDUI
    place_piece(state, rc.MANDUBII, enemy, rc.WARBAND, 4)
    refresh_all_control(state)
    state['markers'].setdefault(rc.MANDUBII, {})[rc.MARKER_DEVASTATED] = True
    command = 'Recruit' if faction == rc.ROMANS else 'Rally'
    request = {'kind': 'free_action', 'request_type': 'event_rally',
               'allowed_commands': [command], 'allowed_regions': [rc.MANDUBII],
               'max_regions': 3, 'with_sa': False, 'free': True,
               'as_if_control': True, 'allow_devastated': True}
    action, output = _collect(state, faction, request, [
        'Plan the action', command, rc.MANDUBII,
        'an Ally at a Subdued Tribe',
        rc.TRIBE_MANDUBII])
    assert 'March' not in output
    assert execute_free_action_plan(state, faction, request, action)['executed']
    assert count_pieces(state, rc.MANDUBII, faction, rc.ALLY) == 1
    assert state['resources'][faction] == 0


def test_standalone_free_sa_scopes_special_ability_and_region():
    state = _state()
    for region in (rc.BRITANNIA, rc.MANDUBII):
        place_piece(state, region, rc.AEDUI, rc.WARBAND)
    request = {'kind': 'free_action', 'request_type': 'event_sa',
               'allowed_sas': ['Suborn'], 'allowed_regions': [rc.BRITANNIA],
               'free': True}
    action, output = _collect(state, rc.AEDUI, request, [
        'Plan the action', 'Suborn', rc.BRITANNIA, 'place a Warband', '(done)'])
    assert 'Trade' not in output and rc.MANDUBII not in output
    assert action['command'] is None
    assert execute_free_action_plan(state, rc.AEDUI, request, action)['executed']
    assert count_pieces(state, rc.BRITANNIA, rc.AEDUI, rc.WARBAND) == 2
    assert state['resources'][rc.AEDUI] == 0


@pytest.mark.parametrize('choice,response', [
    ('Use bot default', {'use_default': True}), ('Decline', {'decline': True})])
def test_reactive_free_action_requires_explicit_default_or_decline(choice, response):
    state = _state()
    agent = make_cli_reactive([rc.AEDUI], io.StringIO(choice + '\n'), io.StringIO())
    assert agent(state, rc.AEDUI, {'kind': 'free_action'}) == response


def test_free_action_eof_interrupts_instead_of_defaulting():
    state = _state()
    agent = make_cli_reactive([rc.AEDUI], io.StringIO(''), io.StringIO())
    with pytest.raises(EOFError):
        agent(state, rc.AEDUI, {'kind': 'free_action'})


def test_no_legal_entreat_region_returns_to_explicit_menu():
    state = _state()
    request = {'kind': 'free_action', 'request_type': 'event_sa',
               'allowed_sas': ['Entreat'], 'allowed_regions': [rc.BRITANNIA],
               'free': True}
    result, output = _collect(state, rc.ARVERNI, request,
                              ['Plan the action', 'Entreat', 'Decline'])
    assert result == {'decline': True}
    assert 'Cannot use this plan:' in output


def test_skipped_placement_returns_to_explicit_menu():
    state = _state()
    request = {'kind': 'free_action', 'request_type': 'event_rally',
               'allowed_commands': ['Rally'], 'allowed_regions': [rc.MANDUBII],
               'max_regions': 1, 'as_if_control': True, 'free': True}
    result, output = _collect(state, rc.AEDUI, request, [
        'Plan the action', 'Rally', rc.MANDUBII, 'Skip this Region', 'Decline'])
    assert result == {'decline': True}
    assert output.count('Aedui: Event grants a free action.') == 2
    assert 'Warbands' not in output  # No base for that Rally option here.


def test_event_march_can_reach_only_required_destination_during_frost():
    state = _state()
    place_piece(state, rc.MORINI, rc.AEDUI, rc.WARBAND, 2)
    state['current_card'], state['next_card'] = 57, rc.WINTER_CARD
    from fs_bot.engine.game_engine import is_frost
    assert is_frost(state)
    from fs_bot.cli.human_plan import _collect_command
    from fs_bot.engine.game_engine import ACTION_COMMAND
    assert _collect_command(state, rc.AEDUI, ACTION_COMMAND,
                            io.StringIO(''), io.StringIO(),
                            allowed_commands=['March']) is None
    request = {'kind': 'free_action', 'request_type': 'event_command',
               'allowed_commands': ['March'], 'allowed_regions': [rc.MORINI],
               'required_destinations': [rc.BRITANNIA], 'free': True}
    action, output = _collect(state, rc.AEDUI, request, [
        'Plan the action', 'March', rc.MORINI, rc.BRITANNIA, 'all 2'])
    assert action['details']['routes'] == {rc.MORINI: [rc.BRITANNIA]}
    assert rc.NERVII not in output
    assert execute_free_action_plan(state, rc.AEDUI, request, action)['executed']
    assert count_pieces(state, rc.BRITANNIA, rc.AEDUI, rc.WARBAND) == 2


def test_britannia_grant_offers_roman_two_step_route_from_inland_origin():
    state = _state()
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, 2)
    request = {'kind': 'free_action', 'request_type': 'event_command',
               'allowed_commands': ['March'], 'allowed_regions': [rc.NERVII],
               'required_destinations': [rc.BRITANNIA], 'free': True}
    action, _ = _collect(state, rc.ROMANS, request, [
        'Plan the action', 'March', rc.NERVII,
        f'{rc.MORINI} → {rc.BRITANNIA}', 'all 2'])
    assert action['details']['routes'] == {rc.NERVII: [rc.MORINI, rc.BRITANNIA]}
    assert execute_free_action_plan(state, rc.ROMANS, request, action)['executed']
    assert count_pieces(state, rc.BRITANNIA, rc.ROMANS, rc.AUXILIA) == 2


@pytest.mark.parametrize('timing', ['before', 'after', 'during'])
def test_free_command_keeps_human_sa_timing_and_region_budget(timing):
    state = _state()
    for region in (rc.MORINI, rc.NERVII, rc.MANDUBII):
        place_piece(state, region, rc.AEDUI, rc.WARBAND, 3)
    request = {'kind': 'free_action', 'request_type': 'event_command',
               'allowed_commands': ['Raid'], 'allowed_regions': [rc.MORINI, rc.NERVII],
               'max_regions': 2, 'with_sa': True, 'free': True}
    sa = ['Suborn', rc.MORINI, 'place a Warband', '(done)']
    raid = [rc.MORINI, '(done)', '1', 'gain 1 Resource']
    if timing == 'before':
        lines = ['Special Activity first, then Command'] + sa + ['Raid'] + raid
    elif timing == 'after':
        lines = ['Raid'] + raid + ['y'] + sa
    else:
        lines = ['Command, Special Activity, then continue Command', 'Raid'] + raid + sa
        lines += [rc.NERVII, '1', 'gain 1 Resource']
    action, output = _collect(state, rc.AEDUI, request, ['Plan the action'] + lines)
    assert action['sa_timing'] == timing
    assert rc.MANDUBII not in output
    assert execute_free_action_plan(state, rc.AEDUI, request, action)['executed']
    assert count_pieces(state, rc.MORINI, rc.AEDUI, rc.WARBAND) == 4
    assert state['resources'][rc.AEDUI] == (2 if timing == 'during' else 1)


def test_command_region_limit_stops_selection_at_granted_count():
    state = _state()
    for region in (rc.MORINI, rc.NERVII):
        place_piece(state, region, rc.AEDUI, rc.WARBAND)
    request = {'kind': 'free_action', 'request_type': 'event_command',
               'allowed_commands': ['Raid'], 'allowed_regions': [rc.MORINI, rc.NERVII],
               'max_regions': 1, 'free': True}
    action, _ = _collect(state, rc.AEDUI, request,
                         ['Plan the action', 'Raid', rc.MORINI, 'gain 1 Resource'])
    assert action['details']['raid_plan'] == [{'region': rc.MORINI, 'target': None}]
