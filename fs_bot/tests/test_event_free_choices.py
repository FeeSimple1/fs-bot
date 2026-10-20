"""Event text grants remain explicit, scoped, free, and available to humans."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.board.control import refresh_all_control
from fs_bot.commands.rally import validate_rally_region, validate_recruit_region
from fs_bot.engine.execute import _resolve_free_command, _resolve_free_rally
from fs_bot.engine.free_actions import (validate_free_action_response,
                                        execute_free_action_plan)
from fs_bot.engine.event_britannia import resolve_britannia
from fs_bot.state.state_schema import build_initial_state


def state():
    st = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=7)
    st['non_player_factions'] = set()
    return st


def rally_ally(faction, region=rc.MANDUBII, tribe=rc.TRIBE_MANDUBII):
    if faction == rc.ROMANS:
        details = {'recruit_plan': [{'region': region, 'tribe': tribe,
                                     'action': 'place_ally'}]}
    else:
        details = {'rally_plan': {'allies': [{'region': region, 'tribe': tribe}]}}
    return {'command': 'Recruit' if faction == rc.ROMANS else 'Rally',
            'regions': [], 'sa': 'No SA', 'sa_regions': [], 'details': details}


@pytest.mark.parametrize('faction', [rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE])
def test_acco_human_ally_in_devastated_enemy_controlled_empty_region(faction):
    st = state()
    enemy = rc.BELGAE if faction != rc.BELGAE else rc.ROMANS
    place_piece(st, rc.MANDUBII, enemy,
                rc.WARBAND if enemy == rc.BELGAE else rc.AUXILIA, 4)
    refresh_all_control(st)
    control = st['spaces'][rc.MANDUBII]['control']
    st['markers'].setdefault(rc.MANDUBII, {})[rc.MARKER_DEVASTATED] = True
    requests = []
    def agent(board, actor, request):
        requests.append(request)
        return rally_ally(faction)
    st['decision_agent'] = agent
    result = _resolve_free_rally(st, faction, max_regions=3,
                                as_if_control=True, allow_devastated=True)
    assert result['executed'] and not result['errors']
    assert requests[0]['as_if_control'] and requests[0]['max_regions'] == 3
    assert count_pieces(st, rc.MANDUBII, faction, rc.ALLY) == 1
    assert st['resources'][faction] == 0
    assert st['spaces'][rc.MANDUBII]['control'] == control
    assert rc.MARKER_DEVASTATED in st['markers'][rc.MANDUBII]
    assert '_rally_event_grant' not in st
    assert '_free_action_factions' not in st
    valid = (validate_recruit_region(st, rc.MANDUBII) if faction == rc.ROMANS
             else validate_rally_region(st, rc.MANDUBII, faction))
    assert not valid[0]


def test_acco_bot_places_allies_under_event_control_without_faking_control():
    st = state()
    st['non_player_factions'] = {rc.BELGAE}
    result = _resolve_free_rally(st, rc.BELGAE, max_regions=3,
                                as_if_control=True, allow_devastated=True)
    assert result['executed'] and not result['errors']
    placed = [r for r in st['spaces'] if count_pieces(st, r, rc.BELGAE, rc.ALLY)]
    assert len(placed) == 3
    assert st['resources'][rc.BELGAE] == 0
    assert any(st['spaces'][r]['control'] == rc.NO_CONTROL for r in st['spaces'] if r not in placed)


def test_human_free_command_is_selected_instead_of_refused():
    st = state()
    place_piece(st, rc.MORINI, rc.BELGAE, rc.WARBAND)
    def agent(board, faction, request):
        assert request['kind'] == 'free_action'
        return {'command': 'Raid', 'regions': [], 'sa': 'No SA', 'sa_regions': [],
                'details': {'raid_plan': [{'region': rc.MORINI, 'target': None}]}}
    st['decision_agent'] = agent
    result = _resolve_free_command(st, rc.BELGAE, allowed_regions={rc.MORINI})
    assert result['executed']
    assert st['resources'][rc.BELGAE] == 1


@pytest.mark.parametrize('problem', ['region', 'max', 'sa', 'malformed', 'illegal'])
def test_invalid_free_plan_rejected_without_board_or_rng_changes(problem):
    st = state()
    request = {'kind': 'free_action', 'request_type': 'event_rally',
               'allowed_commands': ['Rally'], 'allowed_regions': [rc.MANDUBII],
               'max_regions': 1, 'with_sa': False, 'free': True,
               'as_if_control': True, 'allow_devastated': True}
    action = rally_ally(rc.BELGAE)
    if problem == 'region':
        request['allowed_regions'] = [rc.MORINI]
    elif problem == 'max':
        request['max_regions'] = 0
    elif problem == 'sa':
        action['sa'] = 'Rampage'
    elif problem == 'malformed':
        action['details']['rally_plan'] = 99
    else:
        action['details']['rally_plan']['allies'][0]['tribe'] = rc.TRIBE_MORINI
    before = deepcopy(st['spaces']); rng = st['rng'].getstate()
    assert validate_free_action_response(st, rc.BELGAE, request, action)
    assert st['spaces'] == before and st['rng'].getstate() == rng
    assert '_rally_event_grant' not in st and '_free_action_factions' not in st


@pytest.mark.parametrize('timing,expected', [('before', ['sa', 'command']),
                                             ('after', ['command', 'sa']),
                                             ('during', ['command', 'sa', 'command'])])
def test_human_free_command_preserves_selected_sa_timing(monkeypatch, timing, expected):
    import fs_bot.engine.execute as ex
    st = state(); calls = []
    monkeypatch.setattr(ex, '_execute_raid', lambda *args: calls.append('command') or {'executed': True})
    monkeypatch.setattr(ex, '_execute_sa', lambda *args: calls.append('sa') or {'executed': True})
    action = {'command': 'Raid', 'sa': 'Trade', 'sa_timing': timing,
              'sa_regions': [], 'details': {}}
    if timing == 'during':
        action['details']['command_parts'] = [
            {'command': 'Raid', 'details': {'raid_plan': [{'region': rc.MORINI}]}},
            {'command': 'Raid', 'details': {'raid_plan': [{'region': rc.NERVII}]}}]
    request = {'request_type': 'event_command', 'with_sa': True}
    execute_free_action_plan(st, rc.AEDUI, request, action)
    assert calls == expected


def test_britannia_already_present_may_suborn_free_then_get_bonus():
    st = state()
    place_piece(st, rc.BRITANNIA, rc.AEDUI, rc.WARBAND)
    requests = []
    def agent(board, faction, request):
        requests.append(request)
        if request['request_type'] == 'event_command':
            return {'decline': True}
        assert board['resources'][rc.AEDUI] == 0  # bonus follows the SA
        return {'command': None, 'sa': 'Suborn', 'sa_regions': [rc.BRITANNIA],
                'details': {'suborn_plan': [{'region': rc.BRITANNIA,
                              'actions': [{'action': 'place_warband'}] * 3}]}}
    st['decision_agent'] = agent
    result = resolve_britannia(st, rc.AEDUI)[0]
    assert result['sa_execution']['executed']
    assert result['resources_bonus'] == 4
    assert count_pieces(st, rc.BRITANNIA, rc.AEDUI, rc.WARBAND) == 4
    assert st['resources'][rc.AEDUI] == 4
    assert len(requests) == 2
    assert 'sa_deferred' not in result


def test_britannia_bot_sa_uses_britannia_even_when_other_region_has_priority():
    st = state(); st['non_player_factions'] = {rc.AEDUI, rc.ROMANS}
    place_piece(st, rc.BRITANNIA, rc.AEDUI, rc.WARBAND)
    place_piece(st, rc.MANDUBII, rc.AEDUI, rc.WARBAND)
    # No Supply Line to Britannia, so NP Trade falls through to Suborn there.
    st['decision_agent'] = lambda *args: None
    result = resolve_britannia(st, rc.AEDUI)[0]
    assert result['sa_execution']['executed']
    assert count_pieces(st, rc.BRITANNIA, rc.AEDUI) > 1
    assert count_pieces(st, rc.MANDUBII, rc.AEDUI) == 1
    assert result['resources_bonus'] == 4


def test_britannia_suborn_elsewhere_and_ungranted_sa_are_rejected():
    st = state(); place_piece(st, rc.MANDUBII, rc.AEDUI, rc.WARBAND)
    request = {'request_type': 'event_sa', 'allowed_regions': [rc.BRITANNIA],
               'allowed_sas': ['Suborn'], 'with_sa': True}
    action = {'command': None, 'sa': 'Suborn', 'sa_regions': [],
              'details': {'suborn_plan': [{'region': rc.MANDUBII,
                            'actions': [{'action': 'place_warband'}]}]}}
    assert 'Regions' in validate_free_action_response(st, rc.AEDUI, request, action)
    action = {'command': None, 'sa': 'Trade', 'details': {}}
    assert 'not granted' in validate_free_action_response(st, rc.AEDUI, request, action)


def test_britannia_march_destination_constraint_checks_extra_groups():
    st = state()
    request = {'request_type': 'event_command', 'allowed_commands': ['March'],
               'required_destinations': [rc.BRITANNIA], 'with_sa': False}
    action = {'command': 'March', 'sa': 'No SA', 'details': {
        'origins': [rc.MORINI], 'routes': {rc.MORINI: [rc.BRITANNIA]},
        'extra_groups': [{'origin': rc.MORINI, 'route': [rc.NERVII]}]}}
    assert 'destination' in validate_free_action_response(st, rc.AEDUI, request, action)


def test_event_scoped_trade_does_not_collect_outside_region(monkeypatch):
    from fs_bot.commands import sa_trade
    st = state()
    for region, tribe in [(rc.BRITANNIA, rc.TRIBE_CATUVELLAUNI),
                           (rc.MANDUBII, rc.TRIBE_MANDUBII)]:
        place_piece(st, region, rc.AEDUI, rc.ALLY)
        st['tribes'][tribe]['allied_faction'] = rc.AEDUI
    monkeypatch.setattr(sa_trade, 'has_supply_line', lambda *args: True)
    result = sa_trade.trade(st, roman_agreed=False, allowed_regions={rc.BRITANNIA})
    assert result['resources_gained'] == 1
    assert result['per_item'] == [('aedui_ally', rc.BRITANNIA, 1)]
