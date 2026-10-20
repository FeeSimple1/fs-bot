"""§8.2.3 A34: beneficiary priorities, physical German command mechanics."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, count_pieces_by_state
from fs_bot.board.control import refresh_all_control
from fs_bot.cards.divination_np import choose_divination_action, _battle
from fs_bot.engine.free_actions import validate_free_action_response, execute_free_action_plan
from fs_bot.state.state_schema import build_initial_state
from fs_bot.state.serialize import encode


def state(seed=7):
    st = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=seed)
    st['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE, rc.GERMANS}
    return st


def request():
    return {'kind': 'free_action', 'request_type': 'event_command',
            'acting_faction': rc.GERMANS, 'allowed_commands': ['March', 'Battle'],
            'max_regions': 3, 'with_sa': False, 'free': True}


def execute(st, chooser, plan):
    assert plan is not None
    assert validate_free_action_response(st, chooser, request(), plan) is None
    result = execute_free_action_plan(st, chooser, request(), plan)
    assert result['executed'], result
    return result


def test_belgae_choose_german_battle_not_own_force_or_german_bot_policy():
    st = state()
    place_piece(st, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 4)
    place_piece(st, rc.SEQUANI, rc.ROMANS, rc.ALLY)
    # A native Belgian army elsewhere is never added to German damage.
    place_piece(st, rc.AEDUI_REGION, rc.BELGAE, rc.WARBAND, 8)
    place_piece(st, rc.AEDUI_REGION, rc.ROMANS, rc.ALLY)
    refresh_all_control(st)
    plan = choose_divination_action(st, rc.BELGAE)
    assert plan['command'] == 'Battle'
    assert plan['sa'] == 'No SA'
    assert plan['details']['battle_plan'] == [{'region': rc.SEQUANI, 'target': rc.ROMANS}]
    execute(st, rc.BELGAE, plan)
    assert count_pieces(st, rc.SEQUANI, rc.ROMANS, rc.ALLY) == 0
    assert count_pieces(st, rc.AEDUI_REGION, rc.BELGAE, rc.WARBAND) == 8
    assert count_pieces(st, rc.AEDUI_REGION, rc.ROMANS, rc.ALLY) == 1


def test_belgic_battle_cap_is_three_regions_with_repeatable_ties():
    st = state()
    for r in (rc.SEQUANI, rc.TREVERI, rc.UBII, rc.NERVII):
        place_piece(st, r, rc.GERMANS, rc.WARBAND, 4)
        place_piece(st, r, rc.ROMANS, rc.ALLY)
    refresh_all_control(st)
    other = deepcopy(st)
    plan = choose_divination_action(st, rc.BELGAE)
    assert plan == choose_divination_action(other, rc.BELGAE)
    assert len(plan['details']['battle_plan']) == 3
    assert len({e['region'] for e in plan['details']['battle_plan']}) == 3
    execute(st, rc.BELGAE, plan)


def test_aedui_roman_battle_permission_uses_native_aedui_victory():
    st = state()
    place_piece(st, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 6)
    place_piece(st, rc.SEQUANI, rc.ROMANS, rc.ALLY)
    refresh_all_control(st)
    action, _ = _battle(st, rc.AEDUI, 3)
    assert action is None
    # German force size must never be treated as Aedui Allies/victory.
    from fs_bot.bots.aedui_bot import _aedui_at_victory
    assert not _aedui_at_victory(st)


def test_aedui_forced_high_value_battle_does_not_assume_ambush():
    st = state()
    place_piece(st, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 4)
    place_piece(st, rc.SEQUANI, rc.BELGAE, rc.WARBAND, 1)
    place_piece(st, rc.SEQUANI, rc.BELGAE, rc.ALLY)
    refresh_all_control(st)
    action, _ = _battle(st, rc.AEDUI, 3)
    # Retreat has Allies first: its 1 loss still forces the high-value Ally.
    assert action and action['command'] == 'Battle'
    assert action['sa'] == 'No SA'
    # Against an all-mobile force, Retreat can prevent the high-value Loss.
    st = state()
    place_piece(st, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 4)
    place_piece(st, rc.SEQUANI, rc.BELGAE, rc.WARBAND, 1)
    place_piece(st, rc.SEQUANI, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    refresh_all_control(st)
    action, _ = _battle(st, rc.AEDUI, 3)
    assert action is None


def test_aedui_march_splits_one_german_origin_to_three_and_retains_ownership():
    st = state()
    place_piece(st, rc.TREVERI, rc.GERMANS, rc.WARBAND, 4, piece_state=rc.REVEALED)
    place_piece(st, rc.TREVERI, rc.AEDUI, rc.WARBAND, 8)
    refresh_all_control(st)
    controls = {r:s['control'] for r,s in st['spaces'].items()}
    plan = choose_divination_action(st, rc.AEDUI, limit=1)
    assert plan['command'] == 'March'
    assert plan['details']['origins'] == [rc.TREVERI]
    assert len(plan['details']['destinations']) == 3
    assert len(plan['details']['extra_groups']) == 2
    assert all(len(route) == 1 for route in plan['details']['routes'].values())
    execute(st, rc.AEDUI, plan)
    assert count_pieces(st, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 1
    assert count_pieces(st, rc.TREVERI, rc.AEDUI, rc.WARBAND) == 8
    assert st['spaces'][rc.TREVERI]['control'] == controls[rc.TREVERI]
    for r in plan['details']['destinations']:
        assert count_pieces_by_state(st, r, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 1
        assert count_pieces(st, r, rc.AEDUI, rc.WARBAND) == 0


def test_aedui_cannot_spread_scouted_warbands_as_hidden():
    st = state()
    place_piece(st, rc.TREVERI, rc.GERMANS, rc.WARBAND, 4, piece_state=rc.SCOUTED)
    refresh_all_control(st)
    assert choose_divination_action(st, rc.AEDUI) is None


def test_roman_march_uses_german_one_step_and_keeps_caesar_legions_at_home():
    st = state()
    place_piece(st, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 3)
    place_piece(st, rc.AEDUI_REGION, rc.ARVERNI, rc.ALLY)
    place_piece(st, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(st, rc.SEQUANI, rc.ROMANS, rc.LEGION, 2, from_legions_track=True)
    refresh_all_control(st)
    plan = choose_divination_action(st, rc.ROMANS)
    assert plan['command'] == 'March'
    assert plan['details']['groups'] == {rc.SEQUANI: {rc.WARBAND: 3}}
    assert plan['details']['routes'] == {rc.SEQUANI: [rc.AEDUI_REGION]}
    execute(st, rc.ROMANS, plan)
    assert count_pieces(st, rc.SEQUANI, rc.ROMANS, rc.LEGION) == 2
    assert count_pieces(st, rc.SEQUANI, rc.ROMANS, rc.LEADER) == 1
    assert count_pieces(st, rc.AEDUI_REGION, rc.GERMANS, rc.WARBAND) == 3


def test_roman_cannot_use_own_two_step_march_for_germans():
    st = state()
    place_piece(st, rc.UBII, rc.GERMANS, rc.WARBAND, 3)
    place_piece(st, rc.AEDUI_REGION, rc.ARVERNI, rc.ALLY)
    refresh_all_control(st)
    assert choose_divination_action(st, rc.ROMANS) is None


def test_german_leader_keeps_ariovistus_damage_not_beneficiary_bonus():
    st = state()
    place_piece(st, rc.SEQUANI, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    place_piece(st, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 2)
    place_piece(st, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(st, rc.SEQUANI, rc.ARVERNI, rc.ALLY)
    refresh_all_control(st)
    plan = choose_divination_action(st, rc.ROMANS)
    assert plan['command'] == 'Battle'
    result = execute(st, rc.ROMANS, plan)
    assert count_pieces(st, rc.SEQUANI, rc.ARVERNI) == 0
    assert count_pieces(st, rc.SEQUANI, rc.GERMANS, rc.LEADER) == 1


def test_belgic_bottom_march_never_fabricates_belgic_control():
    st = state()
    place_piece(st, rc.TREVERI, rc.GERMANS, rc.WARBAND, 6)
    place_piece(st, rc.MORINI, rc.BELGAE, rc.WARBAND, 1)
    refresh_all_control(st)
    before = deepcopy({k:v for k,v in st.items() if k != 'rng'})
    assert choose_divination_action(st, rc.BELGAE) is None
    assert {k:v for k,v in st.items() if k != 'rng'} == before
    assert count_pieces(st, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 6
    assert count_pieces(st, rc.MORINI, rc.BELGAE, rc.WARBAND) == 1


def test_planning_never_asks_reactions_or_changes_board_resources_pools():
    st = state()
    place_piece(st, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 4)
    place_piece(st, rc.SEQUANI, rc.ROMANS, rc.ALLY)
    st['decision_agent'] = lambda *_: pytest.fail('planning called a human')
    before = deepcopy({k:v for k,v in st.items() if k not in ('rng','decision_agent')})
    assert choose_divination_action(st, rc.BELGAE)
    assert {k:v for k,v in st.items() if k not in ('rng','decision_agent')} == before


def test_roman_march_ranks_only_reachable_german_destinations():
    st = state()
    place_piece(st, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 3)
    place_piece(st, rc.AEDUI_REGION, rc.ARVERNI, rc.ALLY)
    # An unreachable enemy at victory must not suppress a reachable lower tier.
    place_piece(st, rc.MORINI, rc.BELGAE, rc.ALLY)
    from fs_bot.map.map_data import get_playable_regions
    for r in get_playable_regions(st['scenario']):
        if r not in (rc.SEQUANI, rc.AEDUI_REGION):
            place_piece(st, r, rc.BELGAE, rc.WARBAND, 1)
    refresh_all_control(st)
    from fs_bot.engine.victory import calculate_victory_margin
    assert calculate_victory_margin(st, rc.BELGAE) >= 0
    plan = choose_divination_action(st, rc.ROMANS)
    assert plan['details']['routes'] == {rc.SEQUANI: [rc.AEDUI_REGION]}
    execute(st, rc.ROMANS, plan)


def test_march_keeps_german_bases_as_native_enemy_objectives():
    st = state()
    place_piece(st, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 3)
    place_piece(st, rc.AEDUI_REGION, rc.GERMANS, rc.ALLY)
    refresh_all_control(st)
    plan = choose_divination_action(st, rc.ROMANS)
    assert plan['command'] == 'March'
    assert plan['details']['routes'] == {rc.SEQUANI: [rc.AEDUI_REGION]}
    execute(st, rc.ROMANS, plan)


def test_belgic_leader_only_consolidation_is_not_threat_withdrawal():
    st = state()
    place_piece(st, rc.SEQUANI, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    place_piece(st, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 2)
    place_piece(st, rc.AEDUI_REGION, rc.GERMANS, rc.WARBAND, 5)
    refresh_all_control(st)
    plan = choose_divination_action(st, rc.BELGAE)
    assert plan['details']['groups'] == {rc.SEQUANI: {rc.LEADER: True}}
    execute(st, rc.BELGAE, plan)
    assert count_pieces(st, rc.SEQUANI, rc.GERMANS, rc.WARBAND) == 2


def test_priority_order_does_not_roll_when_no_tie():
    from fs_bot.cards.divination_np import _shuffle_sort
    st = state()
    before = st['rng'].getstate()
    assert _shuffle_sort(st, [3, 1, 2], lambda x:x) == [1, 2, 3]
    assert st['rng'].getstate() == before


def test_aedui_spread_prioritizes_native_enemy_bases_over_empty_regions():
    st = state()
    place_piece(st, rc.NERVII, rc.GERMANS, rc.WARBAND, 2)
    place_piece(st, rc.CISALPINA, rc.GERMANS, rc.WARBAND, 4)
    place_piece(st, rc.MORINI, rc.ROMANS, rc.ALLY)
    refresh_all_control(st)
    plan = choose_divination_action(st, rc.AEDUI)
    assert plan['details']['origins'] == [rc.NERVII]
    assert plan['details']['destinations'] == [rc.MORINI]
    execute(st, rc.AEDUI, plan)


def test_roman_selects_an_origin_that_can_reach_a_native_enemy_base():
    st = state()
    place_piece(st, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 3)
    place_piece(st, rc.MORINI, rc.GERMANS, rc.WARBAND, 3)
    place_piece(st, rc.AEDUI_REGION, rc.ARVERNI, rc.ALLY)
    refresh_all_control(st)
    plan = choose_divination_action(st, rc.ROMANS)
    assert plan['details']['origins'] == [rc.SEQUANI]
    execute(st, rc.ROMANS, plan)


def test_frost_checks_combined_battles_before_advancing_a_player_to_victory():
    st = state()
    st['frost'] = True
    st['non_player_factions'].remove(rc.GERMANS)
    for region in (rc.MORINI, rc.NERVII, rc.ATREBATES, rc.TREVERI, rc.CARNUTES):
        place_piece(st, region, rc.GERMANS, rc.SETTLEMENT)
    for region in (rc.SUGAMBRI, rc.UBII):
        place_piece(st, region, rc.GERMANS, rc.WARBAND, 4)
        place_piece(st, region, rc.ROMANS, rc.ALLY, 3)
        place_piece(st, region, rc.ROMANS, rc.FORT)
    refresh_all_control(st)
    from fs_bot.engine.victory import calculate_victory_score
    assert calculate_victory_score(st, rc.GERMANS) == 5
    plan = choose_divination_action(st, rc.BELGAE)
    assert plan['command'] == 'Battle'
    assert len(plan['details']['battle_plan']) == 1
    execute(st, rc.BELGAE, plan)
    assert calculate_victory_score(st, rc.GERMANS) == 6
