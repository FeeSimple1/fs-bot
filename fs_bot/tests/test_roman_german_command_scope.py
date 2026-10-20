"""§8.2.3 applies flowchart conditions to the Event's relevant Regions."""
from copy import deepcopy

import pytest

from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import place_piece, get_available
from fs_bot.bots import roman_bot as roman, german_bot as german
from fs_bot.commands.common import free_action_scope
from fs_bot.map.map_data import get_tribes_in_region
from fs_bot.rules_consts import (
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS, ALLY, WARBAND, AUXILIA,
    LEGION, LEADER, CAESAR, ARIOVISTUS_LEADER, SETTLEMENT, FORT, MARKER_GALLIA_TOGATA,
    PROVINCIA, AEDUI_REGION, SEQUANI, MANDUBII, UBII, SUGAMBRI, TREVERI, NERVII, CISALPINA,
    SCENARIO_PAX_GALLICA, SCENARIO_ARIOVISTUS, CARD_NAMES_BASE, CARD_NAMES_ARIOVISTUS,
)
from fs_bot.state.state_schema import build_initial_state


def state_for(faction, regions):
    scenario = SCENARIO_ARIOVISTUS if faction == GERMANS else SCENARIO_PAX_GALLICA
    state = build_initial_state(scenario, seed=4)
    state.update(non_player_factions={ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS},
                 can_play_event=False, _planning_free_command=True,
                 _command_region_scope=set(regions), _command_with_sa=False)
    state['resources'][faction] = 0
    return state


def ally_all_tribes(state, region, faction):
    for tribe in get_tribes_in_region(region, state['scenario']):
        if state['tribes'][tribe].get('allied_faction') is None:
            place_piece(state, region, faction, ALLY)
            state['tribes'][tribe]['allied_faction'] = faction


def test_roman_threat_and_march_origin_conditions_ignore_other_regions():
    state = state_for(ROMANS, [PROVINCIA])
    place_piece(state, SEQUANI, ROMANS, LEADER, leader_name=CAESAR)
    place_piece(state, SEQUANI, ROMANS, LEGION, 2, from_legions_track=True)
    place_piece(state, SEQUANI, ROMANS, AUXILIA, 4)
    place_piece(state, SEQUANI, BELGAE, ALLY)
    place_piece(state, PROVINCIA, ROMANS, AUXILIA, 2)
    refresh_all_control(state)
    assert roman.node_r1(state) == ('No', [])
    assert roman.node_r2(state) == 'No'
    origins = roman._select_march_origins(
        state, [SEQUANI], [(AEDUI_REGION, AEDUI)], state['scenario'])
    assert origins == [PROVINCIA]


def test_roman_scope_is_origins_not_march_destinations():
    state = state_for(ROMANS, [PROVINCIA])
    place_piece(state, PROVINCIA, ROMANS, AUXILIA, 4)
    place_piece(state, AEDUI_REGION, ARVERNI, ALLY)
    refresh_all_control(state)
    with free_action_scope(state, ROMANS):
        action = roman.node_r_march(state)
    assert action['command'] == roman.ACTION_MARCH
    assert action['details']['origins'] == [PROVINCIA]
    assert action['details']['destinations'][0][0] == AEDUI_REGION
    assert action['sa'] == roman.SA_ACTION_NONE


def test_recruit_qualification_counts_only_permitted_regions():
    state = state_for(ROMANS, [SEQUANI])
    place_piece(state, PROVINCIA, ROMANS, LEADER, leader_name=CAESAR)
    place_piece(state, SEQUANI, ROMANS, FORT)
    refresh_all_control(state)
    with free_action_scope(state, ROMANS):
        action = roman.node_r_recruit(state)
    # The Provincia home cap cannot make the one scoped Auxilia qualify
    # for the optional §8.8.4 2-Allies/6-pieces branch.
    assert action['command'] != roman.ACTION_RECRUIT
    state['_planning_forced_command'] = roman.ACTION_RECRUIT
    with free_action_scope(state, ROMANS):
        forced = roman.node_r_recruit(state)
    assert forced['command'] == roman.ACTION_RECRUIT
    assert {e['region'] for e in forced['details']['recruit_plan']} == {SEQUANI}
    assert forced['sa'] == roman.SA_ACTION_NONE


def test_roman_excluded_battle_and_march_follow_if_none_edges():
    state = state_for(ROMANS, [PROVINCIA])
    place_piece(state, PROVINCIA, ROMANS, AUXILIA, 4)
    state['_command_exclusions'] = {roman.ACTION_BATTLE, roman.ACTION_MARCH,
                                     roman.ACTION_RECRUIT}
    refresh_all_control(state)
    with free_action_scope(state, ROMANS):
        action = roman.node_r_battle(state)
    assert action['command'] == roman.ACTION_SEIZE
    assert action['regions'] == [PROVINCIA]
    state['_command_exclusions'].add(roman.ACTION_SEIZE)
    assert roman.node_r_battle(state)['command'] == roman.ACTION_PASS


def test_german_threat_and_largest_group_use_permitted_origins():
    state = state_for(GERMANS, [UBII])
    place_piece(state, SEQUANI, GERMANS, LEADER, leader_name=ARIOVISTUS_LEADER)
    place_piece(state, SEQUANI, GERMANS, WARBAND, 12)
    place_piece(state, SEQUANI, ROMANS, ALLY)
    place_piece(state, SUGAMBRI, GERMANS, WARBAND, 8)
    place_piece(state, UBII, GERMANS, WARBAND, 4)
    refresh_all_control(state)
    assert german.node_g1(state) == ('No', [])
    assert german.node_g1b(state) == 'No'
    assert german._find_largest_german_warband_group_leaderless(
        state, state['scenario']) == (UBII, 4)


def test_german_free_command_cannot_take_strategic_sequence_pass():
    state = state_for(GERMANS, [UBII])
    state['current_card_faction_order'] = [ROMANS, GERMANS]
    state['next_card_faction_order'] = [GERMANS, ROMANS]
    before = state['rng'].getstate()
    assert german.node_g2(state) == 'No'
    assert state['rng'].getstate() == before
    state.pop('_planning_free_command')
    assert german.node_g2(state) == 'Yes'  # Seed 4 rolls 2 normally.


def test_german_excluded_raid_does_not_roll_or_take_branch():
    state = state_for(GERMANS, [UBII])
    state['_command_exclusions'] = {german.ACTION_RAID}
    before = state['rng'].getstate()
    assert german.node_g4(state) == 'No'
    assert state['rng'].getstate() == before
    assert german.node_g_raid(state)['command'] == german.ACTION_PASS


def test_german_raid_scope_preserves_resource_pool_for_allowed_region():
    state = state_for(GERMANS, [UBII])
    for region in (SEQUANI, UBII):
        place_piece(state, region, GERMANS, WARBAND, 2)
        place_piece(state, region, ROMANS, AUXILIA)
    state['resources'][ROMANS] = 2
    enough, plan = german._would_raid_gain_enough(state, state['scenario'])
    assert enough
    assert plan == [{'region': UBII, 'target': ROMANS}] * 2


def test_german_rally_estimate_uses_single_option_and_home_bonus():
    state = state_for(GERMANS, [UBII])
    before = deepcopy(state)
    with free_action_scope(state, GERMANS):
        count = german._count_placeable_warbands(
            state, state['scenario'], 0, get_available(state, GERMANS, WARBAND))
    # Empty Germania has no Ally or Settlement cap; it adds its one home WB.
    assert count == 1
    assert state['spaces'] == before['spaces']
    assert state['available'] == before['available']
    assert state['rng'].getstate() == before['rng'].getstate()


def test_german_no_sa_grant_cannot_qualify_rally_from_settle():
    state = state_for(GERMANS, [SEQUANI])
    place_piece(state, SEQUANI, GERMANS, LEADER, leader_name=ARIOVISTUS_LEADER)
    place_piece(state, SEQUANI, GERMANS, WARBAND, 5)
    ally_all_tribes(state, SEQUANI, ROMANS)
    refresh_all_control(state)
    with free_action_scope(state, GERMANS):
        assert not german._any_settle_destination(state, state['scenario'])
        assert german.node_g5(state) == 'No'
        state['_command_with_sa'] = True
        assert german._any_settle_destination(state, state['scenario'])
        assert german.node_g5(state) == 'Yes'


def test_german_march_scope_keeps_destinations_outside_scope():
    state = state_for(GERMANS, [UBII])
    place_piece(state, UBII, GERMANS, WARBAND, 6)
    place_piece(state, UBII, ROMANS, ALLY)
    place_piece(state, SEQUANI, GERMANS, LEADER, leader_name=ARIOVISTUS_LEADER)
    refresh_all_control(state)
    with free_action_scope(state, GERMANS):
        action = german.node_g_march_threat(state)
    assert action['command'] == german.ACTION_MARCH
    plan = action['details']['march_plan']
    assert plan['origins'] == [UBII]
    assert all(r != UBII for r in plan['destinations'])
    assert action['sa'] == german.SA_ACTION_NONE


@pytest.mark.parametrize('name', ['Germanic Horse', 'Remi Influence', 'War Fleet'])
def test_explicit_no_germans_instruction_refuses_event(name):
    state = state_for(GERMANS, [UBII])
    state['current_card_id'] = next(
        cid for cid, title in (CARD_NAMES_BASE | CARD_NAMES_ARIOVISTUS).items() if title == name)
    assert german.node_g3b(state) == 'Yes'


def test_german_rally_keeps_available_warbands_for_later_legal_region():
    state = state_for(GERMANS, [UBII, SUGAMBRI])
    # Both empty Germania Regions receive their home bonus, one option each.
    # Repeated first-Region planning must not exhaust the planning pool.
    with free_action_scope(state, GERMANS):
        action = german.node_g_rally(state)
        from fs_bot.engine.execute import _execute_rally
        result = _execute_rally(state, GERMANS, action)
    assert action['command'] == german.ACTION_RALLY
    assert {p['region'] for p in result['placements']} == {UBII, SUGAMBRI}
    assert not result.get('errors')


def test_german_excluded_threat_actions_continue_below_threat_box():
    state = state_for(GERMANS, [UBII])
    place_piece(state, UBII, GERMANS, WARBAND, 6)
    place_piece(state, UBII, ROMANS, ALLY)
    state['_command_exclusions'] = {german.ACTION_BATTLE, german.ACTION_MARCH}
    refresh_all_control(state)
    with free_action_scope(state, GERMANS):
        action = german.execute_german_turn(state)
    assert action['command'] == german.ACTION_RAID


def test_no_sa_grant_preserves_intrinsic_ariovistus_raid_intimidate():
    # A3.4.3: the accompanying free Intimidate does not count as an SA.
    state = state_for(GERMANS, [UBII])
    place_piece(state, UBII, GERMANS, LEADER, leader_name=ARIOVISTUS_LEADER)
    place_piece(state, UBII, GERMANS, WARBAND, 3)
    refresh_all_control(state)
    sa, regions, details = german._determine_intimidate_after_raid(
        state, [{'region': UBII, 'target': None}])
    assert (sa, regions, details) == (german.SA_ACTION_NONE, [], {})
    # The free effect belongs to Raid itself, so it survives a grant with
    # no accompanying SA and reveals only the actual Raider.
    from fs_bot.engine.execute import _execute_raid
    from fs_bot.board.pieces import count_pieces_by_state
    from fs_bot.rules_consts import HIDDEN, REVEALED, MARKER_INTIMIDATED
    result = _execute_raid(state, GERMANS, {
        'details': {'raid_plan': [{'region': UBII, 'target': None}]}})
    assert result['executed'] and not result['errors']
    assert result['raids'][0]['raid_intimidate']['executed']
    assert MARKER_INTIMIDATED in state['markers'][UBII]
    assert count_pieces_by_state(state, UBII, GERMANS, WARBAND, HIDDEN) == 2
    assert count_pieces_by_state(state, UBII, GERMANS, WARBAND, REVEALED) == 1


def test_roman_build_scope_applies_before_fort_pool_selection():
    state = state_for(ROMANS, [AEDUI_REGION])
    state['_command_with_sa'] = True
    place_piece(state, PROVINCIA, ROMANS, LEADER, leader_name=CAESAR)
    place_piece(state, PROVINCIA, ROMANS, AUXILIA)
    place_piece(state, AEDUI_REGION, ROMANS, AUXILIA)
    place_piece(state, AEDUI_REGION, ROMANS, ALLY)
    refresh_all_control(state)
    with free_action_scope(state, ROMANS):
        plan = roman.node_r_build(state)
    assert plan['forts']
    assert all((entry if isinstance(entry, str) else entry['region']) == AEDUI_REGION
               for entries in plan.values() for entry in entries)


def test_scout_scope_limits_sources_but_preserves_destinations():
    state = state_for(ROMANS, [AEDUI_REGION])
    state['_command_with_sa'] = True
    place_piece(state, PROVINCIA, ROMANS, LEADER, leader_name=CAESAR)
    place_piece(state, AEDUI_REGION, ROMANS, AUXILIA, 4)
    place_piece(state, AEDUI_REGION, ROMANS, ALLY)
    refresh_all_control(state)
    moves = roman._scout_auxilia_moves(state)
    assert moves
    assert all(m['from_region'] == AEDUI_REGION for m in moves)
    assert all(m['to_region'] == PROVINCIA for m in moves)
    assert roman._scout_auxilia_moves(state, allowed_regions={SEQUANI}) == []


def test_scoped_roman_march_reaches_lower_tier_when_top_tier_is_remote(monkeypatch):
    state = state_for(ROMANS, [PROVINCIA])
    place_piece(state, PROVINCIA, ROMANS, AUXILIA, 4)
    place_piece(state, NERVII, BELGAE, ALLY)
    place_piece(state, AEDUI_REGION, ARVERNI, ALLY)
    monkeypatch.setattr(roman, 'calculate_victory_margin',
                        lambda board, faction: 0 if faction == BELGAE else -10)
    refresh_all_control(state)
    assert roman._rank_march_destinations(state, state['scenario']) == [(NERVII, BELGAE)]
    with free_action_scope(state, ROMANS):
        action = roman.node_r_march(state)
    assert action['command'] == roman.ACTION_MARCH
    assert action['details']['origins'] == [PROVINCIA]
    assert action['details']['destinations'] == [(AEDUI_REGION, ARVERNI)]


def test_german_settle_before_rally_enables_that_regions_warband_option():
    # A8.7.4: Settle before Rally if a Settlement can be placed. Its home
    # cap then permits the same Command's Warband placement there.
    state = state_for(GERMANS, [SEQUANI])
    state['_command_with_sa'] = True
    place_piece(state, SEQUANI, GERMANS, LEADER, leader_name=ARIOVISTUS_LEADER)
    place_piece(state, SEQUANI, GERMANS, WARBAND, 5)
    ally_all_tribes(state, SEQUANI, ROMANS)
    refresh_all_control(state)
    from fs_bot.engine.execute import _execute_decision
    from fs_bot.board.pieces import count_pieces
    with free_action_scope(state, GERMANS):
        action = german.node_g_rally(state)
        assert action['sa_timing'] == 'before'
        result = _execute_decision(state, GERMANS, {'bot_action': action})
    assert not result.get('errors')
    assert result['sa_timing'] == 'before'
    assert count_pieces(state, SEQUANI, GERMANS, SETTLEMENT) == 1
    assert count_pieces(state, SEQUANI, GERMANS, WARBAND) > 5


def test_german_threat_march_respects_gallia_togata_roman_only_cisalpina():
    state = state_for(GERMANS, [UBII])
    state["markers"].setdefault(CISALPINA, {})[MARKER_GALLIA_TOGATA] = {"card_id": "A5"}
    place_piece(state, UBII, GERMANS, LEADER, leader_name=ARIOVISTUS_LEADER)
    place_piece(state, UBII, GERMANS, WARBAND, 6)
    place_piece(state, UBII, ROMANS, ALLY)
    refresh_all_control(state)
    from fs_bot.engine.execute import _execute_march
    with free_action_scope(state, GERMANS):
        for seed in range(10):
            state['rng'].seed(seed)
            action = german.node_g_march_threat(state)
            assert CISALPINA not in action['regions']
        result = _execute_march(state, GERMANS, action, free=True)
    assert result['executed'] and not result.get('errors')


def test_german_rally_new_control_enables_settle_after_command():
    state = state_for(GERMANS, [SEQUANI])
    state['_command_with_sa'] = True
    place_piece(state, UBII, GERMANS, LEADER, leader_name=ARIOVISTUS_LEADER)
    place_piece(state, SEQUANI, GERMANS, ALLY)
    tribe = get_tribes_in_region(SEQUANI, state['scenario'])[0]
    state['tribes'][tribe]['allied_faction'] = GERMANS
    place_piece(state, SEQUANI, GERMANS, WARBAND)
    place_piece(state, SEQUANI, ROMANS, AUXILIA, 2)
    refresh_all_control(state)
    assert not german._get_settle_destinations(state, state['scenario'])
    from fs_bot.engine.execute import _execute_decision
    from fs_bot.board.pieces import count_pieces
    with free_action_scope(state, GERMANS):
        action = german.node_g_rally(state)
        assert action['sa_timing'] == 'after'
        assert action['sa_regions'] == [SEQUANI]
        result = _execute_decision(state, GERMANS, {'bot_action': action})
    assert not result.get('errors')
    assert result['sa_timing'] == 'after'
    assert count_pieces(state, SEQUANI, GERMANS, SETTLEMENT) == 1


def test_german_rally_settlement_chain_qualifies_adjacent_region():
    # Mandubii is not adjacent to Germania; the new Sequani Settlement
    # must qualify it within this same A4.6.1 Special Ability.
    state = state_for(GERMANS, [SEQUANI, MANDUBII])
    state['_command_with_sa'] = True
    state['resources'][GERMANS] = 4
    place_piece(state, SEQUANI, GERMANS, LEADER, leader_name=ARIOVISTUS_LEADER)
    for region in (SEQUANI, MANDUBII):
        place_piece(state, region, GERMANS, WARBAND, 2)
    refresh_all_control(state)
    assert german._get_settle_destinations(state, state['scenario']) == [SEQUANI]
    from fs_bot.engine.execute import _execute_decision
    from fs_bot.board.pieces import count_pieces
    action = german.node_g_rally(state)
    assert action['sa_timing'] == 'before'
    assert action['sa_regions'] == [SEQUANI, MANDUBII]
    result = _execute_decision(state, GERMANS, {'bot_action': action})
    assert not result.get('errors')
    assert state['resources'][GERMANS] == 0
    assert all(count_pieces(state, region, GERMANS, SETTLEMENT) == 1
               for region in (SEQUANI, MANDUBII))
