"""§5.4 Resource waivers cover borrowed Enlist March and its planning paths."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces
from fs_bot.board.control import refresh_all_control
from fs_bot.commands.common import free_action_scope
from fs_bot.commands.march import march_cost
from fs_bot.commands.sa_enlist import BORROW_KEY
from fs_bot.engine.execute import _execute_bot_command, march_plan_has_effect
from fs_bot.state.state_schema import build_initial_state


@pytest.mark.parametrize('scenario', [rc.SCENARIO_PAX_GALLICA, rc.SCENARIO_ARIOVISTUS])
@pytest.mark.parametrize('resources,devastated', [(0, False), (0, True), (5, True)])
def test_free_event_march_with_borrowed_enlist_waives_belgic_cost(scenario, resources, devastated):
    st = build_initial_state(scenario, seed=2)
    st['resources'][rc.BELGAE] = resources
    place_piece(st, rc.NERVII, rc.BELGAE, rc.LEADER,
                leader_name=rc.AMBIORIX if scenario == rc.SCENARIO_PAX_GALLICA else rc.BODUOGNATUS)
    place_piece(st, rc.NERVII, rc.GERMANS, rc.WARBAND, 2)
    if devastated:
        st['markers'].setdefault(rc.NERVII, {})[rc.MARKER_DEVASTATED] = True
    pools = deepcopy(st['available'])
    action = {'command': 'March', 'sa': 'Enlist', 'sa_timing': 'before',
              'sa_regions': [rc.NERVII], 'details': {
                  'enlist': {'type': 'borrow', 'regions': [rc.NERVII]},
                  'origins': [rc.NERVII], 'destinations': [rc.TREVERI],
                  'routes': {rc.NERVII: [rc.TREVERI]},
                  'groups': {rc.NERVII: {rc.WARBAND: 2, 'german_warbands': 2}}}}
    result = _execute_bot_command(st, rc.BELGAE, action, with_sa=True)
    assert result['executed'] and not result['errors']
    assert result['sa_execution']['executed']
    assert result['total_cost'] == 0
    assert st['resources'][rc.BELGAE] == resources
    assert count_pieces(st, rc.NERVII, rc.GERMANS, rc.WARBAND) == 0
    assert count_pieces(st, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 2
    assert count_pieces(st, rc.TREVERI, rc.BELGAE, rc.WARBAND) == 0
    assert st['available'] == pools
    assert BORROW_KEY not in st and '_free_action_factions' not in st
    assert march_cost(st, rc.NERVII, rc.BELGAE) == (2 if devastated else 1)


@pytest.mark.parametrize('faction,cost', [(rc.ROMANS, 2), (rc.ARVERNI, 1),
                                         (rc.AEDUI, 1), (rc.BELGAE, 1), (rc.GERMANS, 1)])
def test_shared_march_cost_waiver_is_scoped_and_visible_to_callers(faction, cost):
    st = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=2)
    assert march_cost(st, rc.NERVII, faction) == cost
    with free_action_scope(st, faction):
        assert march_cost(st, rc.NERVII, faction) == 0
    assert march_cost(st, rc.NERVII, faction) == cost


def test_free_march_preview_at_zero_resources_does_not_move_or_spend():
    st = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=2)
    place_piece(st, rc.NERVII, rc.BELGAE, rc.WARBAND, 3)
    plan = {'origins': [rc.NERVII], 'destinations': [rc.TREVERI],
            'routes': {rc.NERVII: [rc.TREVERI]}}
    spaces = deepcopy(st['spaces']); rng = st['rng'].getstate()
    assert not march_plan_has_effect(st, rc.BELGAE, plan)
    with free_action_scope(st, rc.BELGAE):
        assert march_plan_has_effect(st, rc.BELGAE, plan)
    assert st['spaces'] == spaces and st['rng'].getstate() == rng
    assert st['resources'][rc.BELGAE] == 0


@pytest.mark.parametrize('faction', [rc.BELGAE, rc.GERMANS])
@pytest.mark.parametrize('frost', [False, True])
def test_march_node_does_not_apply_paid_resource_gate_to_free_event(faction, frost):
    st = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=2)
    st['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE, rc.GERMANS}
    st['frost'] = frost
    origin = rc.NERVII if faction == rc.BELGAE else rc.UBII
    place_piece(st, origin, faction, rc.WARBAND, 6)
    refresh_all_control(st)
    from fs_bot.bots.belgae_bot import node_b_march
    from fs_bot.bots.german_bot import node_g_march_expand
    node = node_b_march if faction == rc.BELGAE else node_g_march_expand
    with free_action_scope(st, faction):
        action = node(st)
    assert action['command'] == 'March'


def test_free_march_preview_allows_frost_but_normal_preview_does_not():
    st = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=2)
    st['frost'] = True
    st['resources'][rc.BELGAE] = 10
    place_piece(st, rc.NERVII, rc.BELGAE, rc.WARBAND, 3)
    plan = {'origins': [rc.NERVII], 'destinations': [rc.TREVERI],
            'routes': {rc.NERVII: [rc.TREVERI]}}
    assert not march_plan_has_effect(st, rc.BELGAE, plan)
    with free_action_scope(st, rc.BELGAE):
        assert march_plan_has_effect(st, rc.BELGAE, plan)
    assert not march_plan_has_effect(st, rc.BELGAE, plan)
