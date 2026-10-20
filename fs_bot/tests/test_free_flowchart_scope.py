"""Event-driven flowcharts retain native objectives and scope action candidates."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import place_piece, get_available, count_pieces
from fs_bot.state.state_schema import build_initial_state
from fs_bot.bots import aedui_bot as ae, belgae_bot as be, arverni_bot as ar
from fs_bot.bots.bot_common import (command_region_candidates, command_is_allowed,
                                    should_decline_event)


def position(scope=None, *, scenario=rc.SCENARIO_PAX_GALLICA):
    st = build_initial_state(scenario, seed=7)
    st.update(_command_region_scope=scope, _command_exclusions=set(),
              _planning_free_command=True, _command_with_sa=False,
              _free_action_factions=set(rc.FACTIONS), can_play_event=False,
              non_player_factions=set(rc.FACTIONS))
    return st


@pytest.mark.parametrize('faction,node', [(rc.AEDUI, ae.node_a1), (rc.BELGAE, be.node_b2)])
def test_granted_command_skips_sequence_pass_without_rolling(faction, node):
    st = position()
    st['current_card_faction_order'] = [rc.ROMANS, faction]
    st['next_card_faction_order'] = [faction, rc.ROMANS]
    before = st['rng'].getstate()
    assert node(st) == 'No'
    assert st['rng'].getstate() == before


def test_scope_preserves_global_warband_entry_condition():
    st = position({rc.SEQUANI})
    place_piece(st, rc.NERVII, rc.AEDUI, rc.WARBAND, 5)
    # Scoped board has zero Warbands; the explicitly global <5 test must
    # still see the five physical Aedui Warbands outside the action scope.
    assert ae.node_a5(st) == 'No'
    assert count_pieces(st, rc.NERVII, rc.AEDUI, rc.WARBAND) == 5


def test_battle_trigger_outside_grant_does_not_override_scoped_rally():
    st = position({rc.SEQUANI})
    place_piece(st, rc.NERVII, rc.AEDUI, rc.WARBAND, 6)
    place_piece(st, rc.NERVII, rc.ARVERNI, rc.ALLY)
    place_piece(st, rc.SEQUANI, rc.AEDUI, rc.WARBAND, 2)
    refresh_all_control(st)
    assert ae.node_a4(st) == 'No'
    action = ae.execute_aedui_turn(st)
    assert action['command'] == 'Rally'
    assert action['regions'] == [rc.SEQUANI]


def test_scoped_rally_allocates_available_pieces_only_inside_scope():
    st = position({rc.AEDUI_REGION})
    # Only one Warband remains Available. An out-of-scope Ally could
    # otherwise consume it before the allowed Aedui Home Region is visited.
    place_piece(st, rc.UBII, rc.AEDUI, rc.WARBAND,
                get_available(st, rc.AEDUI, rc.WARBAND) - 1)
    st['tribes'][rc.TRIBE_AULERCI]['allied_faction'] = rc.AEDUI
    place_piece(st, rc.CARNUTES, rc.AEDUI, rc.ALLY)
    place_piece(st, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 2)
    refresh_all_control(st)
    action = ae.node_a_rally(st)
    assert action['details']['rally_plan']['warbands'] == [rc.AEDUI_REGION]
    assert get_available(st, rc.AEDUI, rc.WARBAND) == 1


def test_aedui_excluded_battle_follows_next_flowchart_condition():
    st = position({rc.SEQUANI})
    place_piece(st, rc.SEQUANI, rc.AEDUI, rc.WARBAND, 6)
    place_piece(st, rc.SEQUANI, rc.ARVERNI, rc.ALLY)
    refresh_all_control(st)
    assert ae.node_a4(st) == 'Yes'
    st['_command_exclusions'] = {'Battle'}
    assert ae.execute_aedui_turn(st)['command'] == 'Rally'


def test_belgic_excluded_threat_battle_and_march_reach_rally():
    st = position({rc.SEQUANI})
    place_piece(st, rc.SEQUANI, rc.BELGAE, rc.WARBAND, 4)
    place_piece(st, rc.SEQUANI, rc.ARVERNI, rc.ALLY)
    refresh_all_control(st)
    st['_command_exclusions'] = {'Battle', 'March'}
    assert be.node_b1(st)[0] == 'Yes'
    assert be.execute_belgae_turn(st)['command'] == 'Rally'


def test_scope_constrains_march_origins_but_not_destinations():
    st = position({rc.SEQUANI})
    place_piece(st, rc.SEQUANI, rc.AEDUI, rc.WARBAND, 2)
    place_piece(st, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 4)
    refresh_all_control(st)
    action = ae.node_a_march(st)
    assert action['command'] == 'March'
    plan = action['details']['march_plan']
    assert plan['origin'] == rc.SEQUANI
    assert plan['spread_destinations']
    assert all(dest != rc.SEQUANI for dest in plan['spread_destinations'])
    assert set(plan.get('origins', [])) <= {rc.SEQUANI}


def test_empty_scope_exhausts_candidates_without_changing_board():
    st = position(set())
    place_piece(st, rc.SEQUANI, rc.AEDUI, rc.WARBAND, 6)
    before = deepcopy({k:v for k,v in st.items() if k != 'rng'})
    assert ae.execute_aedui_turn(st)['command'] == 'Pass'
    assert {k:v for k,v in st.items() if k != 'rng'} == before


def test_ungranted_ambush_does_not_trigger_aedui_high_value_battle():
    st = position({rc.SEQUANI})
    place_piece(st, rc.SEQUANI, rc.AEDUI, rc.WARBAND, 2)
    place_piece(st, rc.SEQUANI, rc.ARVERNI, rc.LEADER,
                leader_name=rc.VERCINGETORIX)
    assert ae.node_a4(st) == 'No'
    st['_command_with_sa'] = True
    assert ae.node_a4(st) == 'Yes'


def test_free_belgic_rally_can_qualify_at_zero_resources():
    st = position({rc.MORINI})
    st['resources'][rc.BELGAE] = 0
    refresh_all_control(st)
    before = st['rng'].getstate()
    assert be.node_b4(st) == 'Yes'  # placement adds physical Belgic Control
    assert st['rng'].getstate() == before
    assert be.execute_belgae_turn(st)['command'] == 'Rally'


def test_low_yield_raid_does_not_become_an_invented_fallback():
    st = position({rc.SEQUANI})
    place_piece(st, rc.SEQUANI, rc.AEDUI, rc.WARBAND)
    st['_command_exclusions'] = {'Battle', 'Rally', 'March'}
    assert ae.execute_aedui_turn(st)['command'] == 'Pass'


def test_arverni_assembly_requires_physical_control_of_benefit():
    st = position()
    place_piece(st, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 2)
    refresh_all_control(st)
    assert should_decline_event(st, 52, rc.ARVERNI)


def test_scope_helpers_do_not_reorder_or_delete_physical_regions():
    st = position({rc.SEQUANI})
    assert command_region_candidates(st, [rc.MORINI, rc.SEQUANI]) == [rc.SEQUANI]
    assert rc.MORINI in st['spaces']
    assert command_is_allowed(st, 'Battle')
    st['_command_exclusions'] = {'Battle'}
    assert not command_is_allowed(st, 'Battle')


def test_scoped_arverni_rally_gate_counts_one_option_per_region():
    st = position({rc.SEQUANI})
    place_piece(st, rc.NERVII, rc.ARVERNI, rc.WARBAND, 9)
    place_piece(st, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 2)
    refresh_all_control(st)
    # Two Subdued Tribes here still permit only one Ally placement this Rally;
    # that does not meet V3's two-Allies/Citadels or six-piece threshold.
    assert ar.node_v3(st) == 'No'


def test_scoped_suborn_replanning_cannot_select_an_outside_region():
    st = position({rc.SEQUANI})
    st['_command_with_sa'] = True
    for region in (rc.SEQUANI, rc.CARNUTES):
        place_piece(st, region, rc.AEDUI, rc.WARBAND)
        place_piece(st, region, rc.ROMANS, rc.AUXILIA, 2)
    refresh_all_control(st)
    sa, regions, details = ae._determine_suborn_sa(st, st['scenario'])
    assert sa == 'Suborn'
    assert regions == [rc.SEQUANI]
    assert details


def test_scoped_rally_estimate_neither_asks_player_nor_spends_rng():
    st = position({rc.SEQUANI})
    place_piece(st, rc.SEQUANI, rc.AEDUI, rc.WARBAND, 5)
    refresh_all_control(st)
    st['decision_agent'] = lambda *_: pytest.fail('planner asked a player')
    before = st['rng'].getstate()
    assert ae.node_a5(st) == 'Yes'
    assert st['rng'].getstate() == before
    assert count_pieces(st, rc.SEQUANI, rc.AEDUI, rc.ALLY) == 0


def test_scoped_arverni_threat_march_approaches_stationary_outside_leader():
    st = position({rc.SEQUANI})
    place_piece(st, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(st, rc.ARVERNI_REGION, rc.ARVERNI, rc.LEADER,
                leader_name=rc.VERCINGETORIX)
    place_piece(st, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, 10)
    refresh_all_control(st)
    action = ar.node_v_march_threat(st)
    plan = action['details']['march_plan']
    assert plan['origins'] == [rc.SEQUANI]
    assert plan['destinations'] == [rc.ARVERNI_REGION]
    from fs_bot.engine.execute import march_plan_has_effect
    assert march_plan_has_effect(st, rc.ARVERNI, plan)


@pytest.mark.parametrize('faction', [rc.AEDUI, rc.ROMANS])
def test_war_fleet_declines_empty_theatre_but_retains_static_presence(faction):
    st = position()
    assert should_decline_event(st, 62, faction)
    place_piece(st, rc.PICTONES, faction, rc.ALLY)
    assert not should_decline_event(st, 62, faction)


def test_war_fleet_empty_theatre_does_not_discard_gallic_home_rally():
    st = position()
    assert not should_decline_event(st, 62, rc.BELGAE)
