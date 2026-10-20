"""Event-driven action restrictions and planning isolation — §§5.4, 8.2.3."""
from copy import deepcopy
import random

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces
from fs_bot.engine import execute as ex
from fs_bot.state.state_schema import build_initial_state
from fs_bot.state.serialize import encode


def fresh(faction=rc.AEDUI):
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=19)
    state['non_player_factions'] = {faction}
    return state


def raid(*regions):
    return {'command': rc.CMD_RAID, 'sa': 'None', 'regions': list(regions),
            'details': {'raid_plan': [{'region': r, 'target': None} for r in regions]}}


def test_limited_command_intersects_event_regions_before_selecting_primary(monkeypatch):
    state = fresh()
    for region in (rc.NERVII, rc.SEQUANI, rc.ARVERNI_REGION):
        place_piece(state, region, rc.AEDUI, rc.WARBAND)
    monkeypatch.setattr('fs_bot.bots.bot_dispatch.dispatch_bot_turn',
                        lambda *_: raid(rc.NERVII, rc.SEQUANI, rc.ARVERNI_REGION))
    result = ex._resolve_free_command(state, rc.AEDUI,
        allowed_regions={rc.SEQUANI, rc.ARVERNI_REGION}, limited=True)
    assert result['executed']
    assert result['regions_resolved'] == [rc.SEQUANI]
    assert not result['errors']


def test_detached_planning_has_no_live_callback_or_stale_turn_context(monkeypatch):
    state = fresh()
    place_piece(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND)
    state['is_second_eligible'] = state['is_limited'] = True
    state['can_play_event'] = True
    def forbidden(*_):
        raise AssertionError('live player consulted during detached planning')
    state['decision_agent'] = forbidden
    seen = []
    def plan(board, faction):
        seen.append(board)
        assert 'decision_agent' not in board
        assert board['is_second_eligible'] is False
        assert board['is_limited'] is False
        assert board['can_play_event'] is False
        assert board['_command_with_sa'] is False
        board['resources'][faction] = 0
        return raid(rc.AEDUI_REGION)
    monkeypatch.setattr('fs_bot.bots.bot_dispatch.dispatch_bot_turn', plan)
    resources = state['resources'][rc.AEDUI]
    result = ex._resolve_free_command(state, rc.AEDUI)
    assert result['executed']
    assert seen[0] is not state
    assert state['resources'][rc.AEDUI] == resources + 1
    assert state['decision_agent'] is forbidden
    assert state['is_second_eligible'] and state['can_play_event']


def test_chosen_tie_advances_authoritative_rng_exactly_once(monkeypatch):
    state = fresh()
    place_piece(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND)
    expected = random.Random()
    expected.setstate(state['rng'].getstate())
    expected.choice([1, 2, 3])
    def plan(board, faction):
        board['rng'].choice([1, 2, 3])
        return raid(rc.AEDUI_REGION)
    monkeypatch.setattr('fs_bot.bots.bot_dispatch.dispatch_bot_turn', plan)
    result = ex._resolve_free_command(state, rc.AEDUI)
    assert result['executed']
    assert state['rng'].getstate() == expected.getstate()


@pytest.mark.parametrize('failure', ['exception', 'excluded', 'event'])
def test_bad_planner_results_remain_errors_without_committing_preview(monkeypatch, failure):
    state = fresh()
    before = encode(state)
    def plan(board, faction):
        board['rng'].random()
        if failure == 'exception':
            raise ValueError('planner regression')
        return {'command': rc.CMD_BATTLE if failure == 'excluded' else ex._CMD_EVENT}
    monkeypatch.setattr('fs_bot.bots.bot_dispatch.dispatch_bot_turn', plan)
    result = ex._resolve_free_command(state, rc.AEDUI, exclude_commands={rc.CMD_BATTLE})
    assert not result['executed']
    assert not result.get('declined_no_effect')
    assert encode(state) == before


def test_march_scope_handles_singular_origin_and_cannot_borrow_leader_elsewhere():
    state = fresh()
    place_piece(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND, 4)
    action = {'command': rc.CMD_MARCH, 'details': {'march_plan': {
        'origin': rc.SEQUANI, 'spread_destinations': [rc.ARVERNI_REGION]}}}
    constrained = ex._constrain_bot_action(action, {rc.SEQUANI}, state=state, faction=rc.AEDUI)
    assert constrained
    moves, _ = ex._collect_march_moves(state, rc.AEDUI, constrained)
    assert moves and {m['origin'] for m in moves} == {rc.SEQUANI}
    assert moves[0]['path'] == [rc.ARVERNI_REGION]


def test_march_scope_filters_extra_groups_and_preserves_legal_destinations():
    state = fresh(rc.ARVERNI)
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 4)
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.WARBAND, 4)
    action = {'command': rc.CMD_MARCH, 'details': {'march_plan': {
        'origins': [rc.SEQUANI], 'destinations': [rc.ARVERNI_REGION],
        'routes': {rc.SEQUANI: [rc.ARVERNI_REGION]},
        'extra_groups': [{'origin': rc.NERVII, 'route': [rc.ATREBATES],
                          'group': {rc.WARBAND: 2}}]}}}
    original = deepcopy(action)
    constrained = ex._constrain_bot_action(action, {rc.SEQUANI}, state=state, faction=rc.ARVERNI)
    moves, _ = ex._collect_march_moves(state, rc.ARVERNI, constrained)
    assert {m['origin'] for m in moves} == {rc.SEQUANI}
    assert moves[0]['path'] == [rc.ARVERNI_REGION]
    assert action == original


def test_march_scope_rejects_implicit_leader_outside_allowed_origins():
    state = fresh(rc.ARVERNI)
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.WARBAND, 4)
    action = {'command': rc.CMD_MARCH, 'details': {
        'destination': rc.ATREBATES, 'origins': []}}
    assert ex._constrain_bot_action(action, {rc.SEQUANI}, state=state, faction=rc.ARVERNI) is None
    state['_command_region_scope'] = {rc.SEQUANI}
    state['_planning_free_command'] = True
    assert not ex.march_plan_has_effect(state, rc.ARVERNI, action['details'])


def test_limited_command_does_not_narrow_a_separately_permitted_sa():
    action = raid(rc.SEQUANI, rc.ARVERNI_REGION)
    action['sa_regions'] = [rc.AEDUI_REGION]
    constrained = ex._constrain_bot_action(action, {rc.SEQUANI}, constrain_sa=False)
    assert constrained['sa_regions'] == [rc.AEDUI_REGION]


def test_assembly_without_carnutes_controller_is_ineffective():
    from fs_bot.cards.event_eval import is_event_effective
    state = fresh(rc.ARVERNI)
    assert not is_event_effective(state, 52, shaded=True)
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND)
    assert is_event_effective(state, 52, shaded=True)


def test_missing_vercingetorix_only_declines_gobannitio_follow_on_rally():
    state = fresh(rc.ARVERNI)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.ALLY)
    before = encode(state)
    result = ex._resolve_card26_arverni_rally(state)[0]
    assert result['declined_no_effect'] and not result['executed']
    assert encode(state) == before


def test_live_execution_scope_is_restored_even_on_exception(monkeypatch):
    state = fresh()
    state['_command_region_scope'] = {rc.NERVII}
    state['_command_with_sa'] = False
    before = encode(state)
    with pytest.raises(RuntimeError):
        with ex._command_execution_scope(state, {rc.SEQUANI}, True):
            assert state['_command_region_scope'] == {rc.SEQUANI}
            assert state['_command_with_sa']
            raise RuntimeError('reactive pause')
    assert encode(state) == before


def test_recruit_supply_preview_cannot_consult_a_live_human(monkeypatch):
    from fs_bot.bots.roman_bot import node_r_recruit
    from fs_bot.commands import rally
    state = fresh(rc.ROMANS)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    calls = []
    def human(*args):
        raise AssertionError('detached Supply Line preview consulted a human')
    state['decision_agent'] = human
    original = rally.has_supply_line
    def preview(board, region, *args, **kwargs):
        if board is not state:
            calls.append(region)
            assert 'decision_agent' not in board
        return original(board, region, *args, **kwargs)
    monkeypatch.setattr(rally, 'has_supply_line', preview)
    ex._resolve_free_command(state, rc.ROMANS, _planner=node_r_recruit)
    assert calls


@pytest.mark.parametrize('scenario, card', [
    (rc.SCENARIO_GREAT_REVOLT, 67), (rc.SCENARIO_ARIOVISTUS, 'A67')])
def test_arduenna_declines_only_aedui_without_presence_or_reachable_force(scenario, card):
    from fs_bot.bots.bot_common import should_decline_event
    state = build_initial_state(scenario, seed=1)
    state['non_player_factions'] = {rc.AEDUI}
    place_piece(state, rc.PROVINCIA, rc.AEDUI, rc.WARBAND, 5)
    assert should_decline_event(state, card, rc.AEDUI)
    # Static pieces outside the theatre cannot March into it.
    place_piece(state, rc.SEQUANI, rc.AEDUI, rc.ALLY)
    assert should_decline_event(state, card, rc.AEDUI)
    # A mobile group within one Region gives the Event a possible effect.
    place_piece(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND)
    assert not should_decline_event(state, card, rc.AEDUI)


@pytest.mark.parametrize('scenario, card', [
    (rc.SCENARIO_GREAT_REVOLT, 67), (rc.SCENARIO_ARIOVISTUS, 'A67')])
def test_arduenna_keeps_aedui_static_presence_and_belgic_home_rally(scenario, card):
    from fs_bot.bots.bot_common import should_decline_event
    state = build_initial_state(scenario, seed=1)
    state['non_player_factions'] = {rc.AEDUI, rc.BELGAE}
    place_piece(state, rc.TREVERI, rc.AEDUI, rc.ALLY)
    assert not should_decline_event(state, card, rc.AEDUI)
    assert not should_decline_event(state, card, rc.BELGAE)


def test_limited_rally_reallocates_last_warband_inside_selected_region():
    from fs_bot.bots.arverni_bot import node_v_rally
    state = fresh(rc.ARVERNI)
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND)
    place_piece(state, rc.SUGAMBRI, rc.ARVERNI, rc.WARBAND, 33)
    for region, faction, tribe in (
        (rc.SUGAMBRI, rc.ROMANS, rc.TRIBE_SUGAMBRI),
        (rc.NERVII, rc.ARVERNI, rc.TRIBE_NERVII),
        (rc.NERVII, rc.ROMANS, rc.TRIBE_EBURONES),
    ):
        place_piece(state, region, faction, rc.ALLY)
        state['tribes'][tribe]['allied_faction'] = faction
    # Sequani is the sole Ally-placement Region. A board-wide draft spends
    # the last Available Warband in earlier Nervii, which the limit discards.
    result = ex._resolve_free_command(state, rc.ARVERNI, limited=True,
                                      _planner=node_v_rally)
    assert result['executed'] and not result['errors']
    assert {entry['region'] for entry in result['placements']} == {rc.SEQUANI}
    assert count_pieces(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND) == 2
    assert count_pieces(state, rc.NERVII, rc.ARVERNI, rc.WARBAND) == 0


@pytest.mark.parametrize('command', [None, ex._CMD_EVENT])
def test_malformed_rally_fallthrough_remains_a_planner_error(monkeypatch, command):
    state = fresh()
    before = encode(state)
    monkeypatch.setattr('fs_bot.bots.aedui_bot.node_a_rally',
                        lambda _: {'command': command})
    result = ex._resolve_free_rally(state, rc.AEDUI)
    assert not result['executed'] and not result.get('declined_no_effect')
    assert 'invalid action' in result['reason']
    assert encode(state) == before


@pytest.mark.parametrize('active', [False, True])
def test_expand_march_destination_uses_actual_gallia_marker(active):
    from fs_bot.cards.card_effects import execute_event
    state = fresh(rc.ROMANS)
    if active:
        execute_event(state, 5)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    moves = ex.plan_expand_march_moves(state, rc.ROMANS,
                                      {'leader_destination': rc.CISALPINA})
    assert bool(moves) is active
    if active:
        assert moves[0]['path'] == [rc.CISALPINA]


def test_expand_march_accepts_actual_gallia_origin():
    from fs_bot.cards.card_effects import execute_event
    state = fresh(rc.ROMANS)
    execute_event(state, 5)
    place_piece(state, rc.CISALPINA, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    moves = ex.plan_expand_march_moves(state, rc.ROMANS,
                                      {'leader_destination': rc.SEQUANI})
    assert moves and moves[0]['origin'] == rc.CISALPINA
    assert moves[0]['path'] == [rc.SEQUANI]


@pytest.mark.parametrize('enemy_control', [False, True])
def test_mons_cevenna_static_romans_decline_only_if_scoped_flowchart_exhausted(enemy_control):
    from fs_bot.bots.bot_common import should_decline_event
    state = fresh(rc.ROMANS)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    if enemy_control:
        place_piece(state, rc.PROVINCIA, rc.AEDUI, rc.WARBAND, 8)
    before = encode(state)
    # A Fort under Roman Control permits Seize; the same static presence
    # under enemy Control has no March or applicable follow-on Command.
    assert should_decline_event(state, 9, rc.ROMANS) is enemy_control
    assert encode(state) == before
