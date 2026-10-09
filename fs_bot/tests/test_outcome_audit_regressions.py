"""Regressions for the seed-1..200 outcome audit at 22099ac.

Rule anchors: §§1.4.2, 3.2.2/3.3.2, 4.2.1, 4.3.1, 4.3.3, 7.1–7.3,
8.5.1, 8.7.1, 8.9 and A4.4.2/A6.2.1. Fixtures use actual piece helpers.
"""
from copy import deepcopy

import pytest

import fs_bot.rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, count_pieces_by_state
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity
from fs_bot.commands.common import CommandError
from fs_bot.commands.sa_build import build_subdue
from fs_bot.engine.execute import (_execute_march, _execute_expand_march,
    _execute_bot_command, _execute_arverni_threat_march, _execute_rampage)
from fs_bot.engine.victory import _count_allies_and_citadels
from fs_bot.tools.run_batch import play_one


def empty(scenario=rc.SCENARIO_PAX_GALLICA):
    return build_initial_state(scenario, seed=43)


def march_action(faction, *, group=None):
    details = {'origins': [rc.ARVERNI_REGION], 'destinations': [rc.BITURIGES]}
    if group is not None:
        details['groups'] = {rc.ARVERNI_REGION: group}
    return {'command': rc.CMD_MARCH, 'sa': None, 'details': details}


@pytest.mark.parametrize('scenario,faction,cost', [
    (rc.SCENARIO_PAX_GALLICA, rc.ROMANS, 2),
    (rc.SCENARIO_PAX_GALLICA, rc.ARVERNI, 1),
    (rc.SCENARIO_PAX_GALLICA, rc.AEDUI, 1),
    (rc.SCENARIO_PAX_GALLICA, rc.BELGAE, 1),
    (rc.SCENARIO_PAX_GALLICA, rc.GERMANS, 0),
    (rc.SCENARIO_ARIOVISTUS, rc.GERMANS, 1),
])
def test_engine_march_pays_origin_cost(scenario, faction, cost):
    state = empty(scenario)
    state['resources'][faction] = 9
    piece = rc.AUXILIA if faction == rc.ROMANS else rc.WARBAND
    place_piece(state, rc.ARVERNI_REGION, faction, piece, 2)
    result = _execute_march(state, faction, march_action(faction))
    assert result['executed'] and not result['errors']
    assert result['total_cost'] == cost
    assert state['resources'][faction] == 9 - cost
    assert count_pieces(state, rc.BITURIGES, faction, piece) == 2


def test_multiple_groups_pay_same_origin_once():
    state = empty()
    state['resources'][rc.ARVERNI] = 1
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, 4)
    action = march_action(rc.ARVERNI, group={rc.WARBAND: 2})
    action['details']['extra_groups'] = [{'origin': rc.ARVERNI_REGION,
        'route': [rc.BITURIGES], 'group': {rc.WARBAND: 2}}]
    result = _execute_march(state, rc.ARVERNI, action)
    assert len(result['marches']) == 2
    assert result['total_cost'] == 1
    assert state['resources'][rc.ARVERNI] == 0
    assert count_pieces(state, rc.BITURIGES, rc.ARVERNI, rc.WARBAND) == 4


def test_multistep_march_pays_once_not_per_hop():
    state = empty()
    state['resources'][rc.ROMANS] = 2
    place_piece(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA, 3)
    action = march_action(rc.ROMANS)
    action['details']['routes'] = {rc.ARVERNI_REGION: [rc.BITURIGES, rc.CARNUTES]}
    result = _execute_march(state, rc.ROMANS, action)
    assert result['executed'] and result['total_cost'] == 2
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 3


def test_unaffordable_march_does_not_flip_or_move():
    state = empty()
    state['resources'][rc.ARVERNI] = 0
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, 3,
                piece_state=rc.SCOUTED)
    result = _execute_march(state, rc.ARVERNI, march_action(rc.ARVERNI))
    assert not result['executed'] and result['total_cost'] == 0
    assert count_pieces_by_state(state, rc.ARVERNI_REGION, rc.ARVERNI,
                                rc.WARBAND, rc.SCOUTED) == 3


def test_free_event_march_still_free_at_zero_resources():
    state = empty()
    state['resources'][rc.ARVERNI] = 0
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, 2)
    result = _execute_bot_command(state, rc.ARVERNI, march_action(rc.ARVERNI))
    assert result['executed'] and result['total_cost'] == 0
    assert state['resources'][rc.ARVERNI] == 0


def test_devastated_march_origin_charges_double():
    state = empty()
    state['resources'][rc.ARVERNI] = 5
    state['markers'].setdefault(rc.ARVERNI_REGION, {})[rc.MARKER_DEVASTATED] = True
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, 2)
    result = _execute_march(state, rc.ARVERNI, march_action(rc.ARVERNI))
    assert result['total_cost'] == 2
    assert state['resources'][rc.ARVERNI] == 3


def test_expand_march_uses_same_billing():
    state = empty()
    state['resources'][rc.ARVERNI] = 3
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.LEADER,
                leader_name=rc.VERCINGETORIX)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, 4)
    result = _execute_expand_march(state, rc.ARVERNI,
                                   {'destination': rc.BITURIGES})
    assert result['executed'] and result['total_cost'] == 1
    assert state['resources'][rc.ARVERNI] == 2


def test_threat_march_pays_before_sa_can_devastate_origin():
    state = empty()
    state['resources'][rc.ARVERNI] = 1
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, 3)
    seen = []
    def before_move():
        seen.append((state['resources'][rc.ARVERNI],
                     count_pieces(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND)))
        state['markers'].setdefault(rc.ARVERNI_REGION, {})[rc.MARKER_DEVASTATED] = True
        return {'executed': True, 'sa': rc.SA_DEVASTATE}
    result = _execute_march(state, rc.ARVERNI, march_action(rc.ARVERNI),
                            before_move=before_move)
    assert seen == [(0, 3)]
    assert result['executed'] and result['total_cost'] == 1


def city_and_other_ally(scenario=rc.SCENARIO_ARIOVISTUS):
    state = empty(scenario)
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.CITADEL)
    state['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] = rc.ARVERNI
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.ALLY)
    state['tribes'][rc.TRIBE_AULERCI]['allied_faction'] = rc.ARVERNI
    return state


def test_build_cannot_subdue_a_citadel_by_spending_another_tribes_disc():
    state = city_and_other_ally()
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 4)
    state['resources'][rc.ROMANS] = 20
    before = deepcopy(state)
    with pytest.raises(CommandError, match='Citadel is not a disc'):
        build_subdue(state, rc.CARNUTES, rc.TRIBE_CARNUTES, rc.ARVERNI)
    assert state['tribes'] == before['tribes']
    assert state['spaces'] == before['spaces']
    assert state['resources'] == before['resources']
    assert state['available'] == before['available']


def test_build_subdues_the_other_tribe_and_leaves_city_allied():
    state = city_and_other_ally()
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 4)
    state['resources'][rc.ROMANS] = 20
    build_subdue(state, rc.CARNUTES, rc.TRIBE_AULERCI, rc.ARVERNI)
    assert state['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] == rc.ARVERNI
    assert state['tribes'][rc.TRIBE_AULERCI]['allied_faction'] is None
    assert count_pieces(state, rc.CARNUTES, rc.ARVERNI, rc.CITADEL) == 1
    assert count_pieces(state, rc.CARNUTES, rc.ARVERNI, rc.ALLY) == 0
    assert not check_structural_integrity(state)


def test_integrity_finds_equal_totals_but_wrong_city_allegiance():
    state = city_and_other_ally()
    from fs_bot.board.pieces import remove_piece
    remove_piece(state, rc.CARNUTES, rc.ARVERNI, rc.ALLY)
    state['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] = None
    assert any('Citadel' in e for e in check_structural_integrity(state))


def test_arverni_phase_does_not_upgrade_an_existing_citadel():
    from fs_bot.engine.arverni_phase import _arverni_phase_rally
    state = city_and_other_ally()
    result = _arverni_phase_rally(state, [rc.CARNUTES])
    assert result['citadels_placed'] == []
    assert count_pieces(state, rc.CARNUTES, rc.ARVERNI, rc.CITADEL) == 1
    assert state['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] == rc.ARVERNI
    assert not check_structural_integrity(state)


def test_city_is_counted_once_by_victory_bots_and_display():
    from fs_bot.bots.bot_common import count_faction_allies_and_citadels
    from fs_bot.cli.display import _faction_total_allies_citadels
    state = city_and_other_ally(rc.SCENARIO_PAX_GALLICA)
    assert _count_allies_and_citadels(state, rc.ARVERNI) == 2
    assert count_faction_allies_and_citadels(state, rc.ARVERNI) == 2
    assert _faction_total_allies_citadels(state, rc.ARVERNI) == (1, 1)


@pytest.mark.parametrize('faction', [rc.ARVERNI, rc.BELGAE])
def test_ambush_counts_hidden_roman_auxilia(faction):
    import importlib
    bot = importlib.import_module('fs_bot.bots.' + ('arverni_bot' if faction == rc.ARVERNI else 'belgae_bot'))
    state = empty()
    leader = rc.VERCINGETORIX if faction == rc.ARVERNI else rc.AMBIORIX
    place_piece(state, rc.CARNUTES, faction, rc.LEADER, leader_name=leader)
    place_piece(state, rc.CARNUTES, faction, rc.WARBAND, 2)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEGION, from_legions_track=True)
    assert bot._check_ambush(state, [{'region': rc.CARNUTES, 'target': rc.ROMANS}], state['scenario']) == []


def test_arverni_successor_cannot_entreat_adjacent_region():
    from fs_bot.bots.arverni_bot import _is_within_one_of_vercingetorix, _check_entreat
    state = empty()
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.LEADER, leader_name=rc.SUCCESSOR)
    place_piece(state, rc.BITURIGES, rc.ARVERNI, rc.WARBAND, 2)
    place_piece(state, rc.BITURIGES, rc.AEDUI, rc.WARBAND, 1)
    state['resources'][rc.ARVERNI] = 5
    assert not _is_within_one_of_vercingetorix(state, rc.BITURIGES, state['scenario'])
    assert _check_entreat(state, state['scenario']) == []


def test_suborn_cannot_ignore_diviciacus_range():
    from fs_bot.bots.aedui_bot import _determine_suborn_sa
    state = empty(rc.SCENARIO_ARIOVISTUS)
    place_piece(state, rc.AEDUI_REGION, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    place_piece(state, rc.MORINI, rc.AEDUI, rc.WARBAND, 2)
    state['resources'][rc.AEDUI] = 10
    sa, regions, _ = _determine_suborn_sa(state, state['scenario'])
    assert rc.MORINI not in regions


def test_besiege_does_not_follow_ineligible_secondary_defender():
    from fs_bot.bots.roman_bot import _determine_battle_sa
    state = empty()
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 1)
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.CITADEL)
    sa, regions = _determine_battle_sa(state, [{'region': rc.CARNUTES,
        'targets': [rc.AEDUI, rc.ARVERNI]}], state['scenario'])
    assert rc.CARNUTES not in regions


def test_besiege_requires_a_legion_even_when_citadel_needs_removal():
    from fs_bot.bots.roman_bot import _determine_battle_sa
    state = empty()
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.CITADEL)
    sa, regions = _determine_battle_sa(state, [{'region': rc.CARNUTES,
        'targets': [rc.ARVERNI]}], state['scenario'])
    assert rc.CARNUTES not in regions


def test_rampage_before_battle_leaves_one_defender():
    state = empty()
    state['non_player_factions'] = {rc.BELGAE, rc.ROMANS}
    place_piece(state, rc.ATREBATES, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    place_piece(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 4)
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, 2)
    result = _execute_rampage(state, rc.BELGAE, {'command': rc.CMD_BATTLE,
        'sa_regions': [{'region': rc.ATREBATES, 'target': rc.ROMANS}]})
    assert result['executed'] and not result['errors']
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS) == 1


@pytest.mark.parametrize('scenario,seed', [
    (rc.SCENARIO_ARIOVISTUS, 43), (rc.SCENARIO_GALLIC_WAR, 43),
    (rc.SCENARIO_GALLIC_WAR, 68), (rc.SCENARIO_ARIOVISTUS, 11),
    (rc.SCENARIO_ARIOVISTUS, 12), (rc.SCENARIO_PAX_GALLICA, 47),
    (rc.SCENARIO_PAX_GALLICA, 116),
])
def test_report_replays_finish_with_rankings_and_no_rejected_actions(scenario, seed):
    record = play_one((scenario, seed))
    assert record['completed'], record.get('errors')
    assert not record['integrity_findings']
    assert not record['engine_ranking_output_missing']
    assert not record['winner_differs_from_highest_margin']
    assert not [d for d in record['diagnostics'] if d['severity'] == 'illegal']


@pytest.mark.parametrize('scenario', [rc.SCENARIO_PAX_GALLICA, rc.SCENARIO_ARIOVISTUS])
def test_np_winner_uses_margin_not_faction_precedence(monkeypatch, scenario):
    from fs_bot.engine import victory
    state = empty(scenario)
    state['non_player_factions'] = {rc.ROMANS, rc.BELGAE}
    monkeypatch.setattr(victory, 'check_victory', lambda state, faction:
                        faction in (rc.ROMANS, rc.BELGAE))
    monkeypatch.setattr(victory, 'calculate_victory_margin', lambda state, faction:
                        {rc.ROMANS: 1, rc.BELGAE: 7}[faction])
    assert victory.check_any_victory(state) == rc.BELGAE


def test_np_threshold_still_defeats_higher_margin_player(monkeypatch):
    from fs_bot.engine import victory
    state = empty()
    state['non_player_factions'] = {rc.ROMANS}
    monkeypatch.setattr(victory, 'check_victory', lambda state, faction:
                        faction in (rc.ROMANS, rc.BELGAE))
    monkeypatch.setattr(victory, 'calculate_victory_margin', lambda state, faction:
                        {rc.ROMANS: 1, rc.BELGAE: 7}[faction])
    assert victory.check_any_victory(state) == rc.ROMANS


def test_multiple_origins_each_pay_before_any_moves():
    state = empty()
    state['resources'][rc.ARVERNI] = 2
    for region in (rc.ARVERNI_REGION, rc.CARNUTES):
        place_piece(state, region, rc.ARVERNI, rc.WARBAND, 2)
    action = march_action(rc.ARVERNI)
    action['details']['origins'].append(rc.CARNUTES)
    result = _execute_march(state, rc.ARVERNI, action)
    assert len(result['marches']) == 2
    assert result['total_cost'] == 2
    assert state['resources'][rc.ARVERNI] == 0
    assert count_pieces(state, rc.BITURIGES, rc.ARVERNI, rc.WARBAND) == 4


def test_budget_limits_selected_origins_without_negative_resources():
    state = empty()
    state['resources'][rc.ARVERNI] = 1
    for region in (rc.ARVERNI_REGION, rc.CARNUTES):
        place_piece(state, region, rc.ARVERNI, rc.WARBAND, 2)
    action = march_action(rc.ARVERNI)
    action['details']['origins'].append(rc.CARNUTES)
    result = _execute_march(state, rc.ARVERNI, action)
    assert len(result['marches']) == 1
    assert result['total_cost'] == 1
    assert state['resources'][rc.ARVERNI] == 0
    assert count_pieces(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND) == 2


@pytest.mark.parametrize('scenario,faction', [
    (rc.SCENARIO_PAX_GALLICA, rc.ROMANS),
    (rc.SCENARIO_PAX_GALLICA, rc.ARVERNI),
    (rc.SCENARIO_PAX_GALLICA, rc.AEDUI),
    (rc.SCENARIO_PAX_GALLICA, rc.BELGAE),
    (rc.SCENARIO_ARIOVISTUS, rc.GERMANS),
])
def test_zero_resource_bots_take_flowchart_fallback(scenario, faction):
    from fs_bot.state.setup import setup_scenario
    from fs_bot.engine.game_engine import get_sop_factions
    from fs_bot.bots.bot_dispatch import dispatch_bot_turn
    state = setup_scenario(scenario, seed=43)
    state['non_player_factions'] = set(get_sop_factions(state))
    state['resources'][faction] = 0
    state['can_play_event'] = False
    action = dispatch_bot_turn(state, faction)
    assert action['command'] != rc.CMD_MARCH


def test_march_preflight_is_read_only_including_rng():
    from fs_bot.engine.execute import march_plan_has_effect
    from fs_bot.state.serialize import encode
    state = empty()
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, 4)
    state['resources'][rc.ARVERNI] = 2
    before = encode(state)
    assert march_plan_has_effect(state, rc.ARVERNI, march_action(rc.ARVERNI)['details'])
    assert encode(state) == before


def test_baggage_trains_zero_cost_is_valid_in_preflight_and_execution():
    from fs_bot.engine.execute import march_plan_has_effect
    from fs_bot.cards.capabilities import activate_capability, set_capability_owner
    state = empty()
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, 2)
    state['resources'][rc.ARVERNI] = 0
    activate_capability(state, 8, rc.EVENT_UNSHADED)
    set_capability_owner(state, 8, rc.ARVERNI)
    action = march_action(rc.ARVERNI)
    assert march_plan_has_effect(state, rc.ARVERNI, action['details'])
    result = _execute_march(state, rc.ARVERNI, action)
    assert result['executed'] and result['total_cost'] == 0
    assert state['resources'][rc.ARVERNI] == 0


def test_free_command_planning_ignores_cost_without_making_normal_march_free():
    from fs_bot.engine.execute import march_plan_has_effect
    state = empty()
    place_piece(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA, 2)
    state['resources'][rc.ROMANS] = 0
    plan = march_action(rc.ROMANS)['details']
    assert not march_plan_has_effect(state, rc.ROMANS, plan)
    state['_planning_free_command'] = True
    assert march_plan_has_effect(state, rc.ROMANS, plan)
    del state['_planning_free_command']
    assert not march_plan_has_effect(state, rc.ROMANS, plan)
