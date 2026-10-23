"""Card72's one-group restriction and printed NP Event instructions."""
from copy import deepcopy
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control, is_controlled_by
from fs_bot.board.pieces import (place_piece, count_pieces, count_pieces_by_state,
                                 get_leader_in_region)
from fs_bot.cards.impetuosity import (march_choices, validate_march, np_choices,
                                      default_plan, resolve_impetuosity)
from fs_bot.cards.event_conditions import np_event_available
from fs_bot.cli.display import _active_force_context, _physical_piece_view
from fs_bot.commands.sa_enlist import scoped_free_force, FREE_FORCE_KEY
from fs_bot.engine.free_actions import validate_free_action_response
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state


def state(scenario=rc.SCENARIO_GREAT_REVOLT, players=(rc.ROMANS,)):
    s = build_initial_state(scenario, seed=9)
    s['non_player_factions'] = set(rc.FACTIONS) - set(players)
    s['current_card'] = s['current_card_id'] = 72
    return s


def march(origin=rc.MORINI, destination=rc.NERVII, n=2):
    return {'origin': origin, 'destination': destination, 'warbands': n}


def battle(region, target):
    return {'command': rc.CMD_BATTLE, 'regions': [region], 'sa': 'No SA',
            'sa_regions': [], 'details': {'battle_plan': [{'region': region, 'target': target}]}}


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
def test_all_bot_game_declines_whole_impetuosity_without_a_player_target(scenario):
    s = state(scenario, players=())
    place_piece(s, rc.MORINI, rc.BELGAE, rc.WARBAND, 6)
    place_piece(s, rc.NERVII, rc.ROMANS, rc.AUXILIA, 2)
    assert np_choices(s, rc.BELGAE) == []
    assert np_event_available(s, 72, rc.BELGAE, True) is False


def test_player_only_target_and_phase_faction_is_not_a_player():
    s = state(rc.SCENARIO_ARIOVISTUS, players=(rc.ARVERNI, rc.ROMANS))
    place_piece(s, rc.MORINI, rc.BELGAE, rc.WARBAND, 6)
    place_piece(s, rc.MORINI, rc.BELGAE, rc.LEADER, leader_name=rc.BODUOGNATUS)
    place_piece(s, rc.NERVII, rc.ARVERNI, rc.WARBAND, 8)
    assert np_choices(s, rc.BELGAE) == []
    place_piece(s, rc.MORINI, rc.ROMANS, rc.AUXILIA)
    assert {p['target'] for p in np_choices(s, rc.BELGAE)} == {rc.ROMANS}


def test_march_in_place_is_available_and_np_then_battles_player():
    s = state()
    place_piece(s, rc.MORINI, rc.BELGAE, rc.WARBAND, 4)
    place_piece(s, rc.MORINI, rc.ROMANS, rc.AUXILIA, 2)
    plan = default_plan(s, rc.BELGAE)
    assert plan == dict(march(rc.MORINI, rc.MORINI, 4), target=rc.ROMANS)
    result = resolve_impetuosity(s, rc.BELGAE)[0]
    assert result['executed'] and result['battle']['executed']
    assert count_pieces(s, rc.MORINI, rc.ROMANS, rc.AUXILIA) == 0


def test_belgic_expansion_leader_four_warband_floor_limits_moving_group():
    s = state(rc.SCENARIO_ARIOVISTUS)
    place_piece(s, rc.MORINI, rc.BELGAE, rc.WARBAND, 7)
    place_piece(s, rc.MORINI, rc.BELGAE, rc.LEADER, leader_name=rc.BODUOGNATUS)
    place_piece(s, rc.NERVII, rc.ROMANS, rc.AUXILIA)
    assert default_plan(s, rc.BELGAE)['warbands'] == 3
    result = resolve_impetuosity(s, rc.BELGAE)[0]
    assert result['warbands_marched'] == 3
    assert count_pieces(s, rc.MORINI, rc.BELGAE, rc.WARBAND) == 4
    assert get_leader_in_region(s, rc.MORINI, rc.BELGAE) == rc.BODUOGNATUS


def test_belgic_expansion_leader_four_warband_floor_applies_after_battle():
    s = state(rc.SCENARIO_ARIOVISTUS)
    place_piece(s, rc.MORINI, rc.BELGAE, rc.WARBAND, 4)
    place_piece(s, rc.MORINI, rc.BELGAE, rc.LEADER, leader_name=rc.BODUOGNATUS)
    place_piece(s, rc.MORINI, rc.ROMANS, rc.LEGION, 3,
                from_legions_track=True)
    assert not s.get('frost')
    # Roman player may stand; every cohort then loses at least one of the
    # four Warbands guarding the unselected Leader. Decline the whole Event.
    assert not np_choices(s, rc.BELGAE)
    assert np_event_available(s, 72, rc.BELGAE, True) is False


def test_belgic_expansion_off_map_leader_cannot_end_with_four_warbands():
    s = state(rc.SCENARIO_ARIOVISTUS)
    place_piece(s, rc.MORINI, rc.BELGAE, rc.WARBAND, 6)
    place_piece(s, rc.MORINI, rc.ROMANS, rc.AUXILIA)
    assert not np_choices(s, rc.BELGAE)


def test_belgic_expansion_smaller_cohort_limits_losses_to_preserve_escort():
    s = state(rc.SCENARIO_ARIOVISTUS)
    place_piece(s, rc.MORINI, rc.BELGAE, rc.WARBAND, 7)
    place_piece(s, rc.MORINI, rc.BELGAE, rc.LEADER, leader_name=rc.BODUOGNATUS)
    place_piece(s, rc.MORINI, rc.ROMANS, rc.LEGION, 8,
                from_legions_track=True)
    assert default_plan(s, rc.BELGAE) == dict(march(rc.MORINI, rc.MORINI, 3), target=rc.ROMANS)
    s['decision_agent'] = lambda _, __, request: (
        {'retreat': False} if request['kind'] == 'retreat' else None)
    result = resolve_impetuosity(s, rc.BELGAE)[0]
    assert result['warbands_marched'] == 3
    assert count_pieces(s, rc.MORINI, rc.BELGAE, rc.WARBAND) == 4
    assert get_leader_in_region(s, rc.MORINI, rc.BELGAE) == rc.BODUOGNATUS


def test_arverni_take_control_and_target_players_in_printed_order():
    s = state(players=(rc.ROMANS, rc.AEDUI))
    place_piece(s, rc.MORINI, rc.ARVERNI, rc.WARBAND, 5)
    place_piece(s, rc.NERVII, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(s, rc.ATREBATES, rc.AEDUI, rc.WARBAND)
    assert default_plan(s, rc.ARVERNI)['target'] == rc.ROMANS
    place_piece(s, rc.NERVII, rc.ROMANS, rc.AUXILIA, 2)
    plan = default_plan(s, rc.ARVERNI)
    assert plan['target'] == rc.AEDUI and plan['destination'] == rc.ATREBATES


def test_germans_keep_origin_control_and_cannot_use_resident_leader_in_battle():
    s = state(rc.SCENARIO_ARIOVISTUS)
    place_piece(s, rc.MORINI, rc.GERMANS, rc.WARBAND, 7)
    place_piece(s, rc.MORINI, rc.BELGAE, rc.WARBAND, 3)
    place_piece(s, rc.NERVII, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(s, rc.NERVII, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    refresh_all_control(s)
    plan = default_plan(s, rc.GERMANS)
    assert plan['warbands'] == 3
    result = resolve_impetuosity(s, rc.GERMANS)[0]
    assert is_controlled_by(s, rc.MORINI, rc.GERMANS)
    # Three cohort Warbands cause one loss; Ariovistus cannot double it.
    assert count_pieces(s, rc.NERVII, rc.ROMANS, rc.AUXILIA) == 1
    assert result['battle']['executed']


@pytest.mark.parametrize('faction,scenario', [(rc.BELGAE,rc.SCENARIO_GREAT_REVOLT),
                                            (rc.GERMANS,rc.SCENARIO_ARIOVISTUS),
                                            (rc.AEDUI,rc.SCENARIO_GREAT_REVOLT)])
def test_human_may_march_without_enemy_and_decline_optional_battle(faction, scenario):
    s = state(scenario, players=(faction,))
    place_piece(s, rc.MORINI, faction, rc.WARBAND, 2)
    requests = []
    def agent(board, actor, request):
        if request['kind'] != 'free_action': return None
        requests.append(request)
        return march() if request['request_type'] == 'impetuosity_march' else {'decline': True}
    s['decision_agent'] = agent
    result = resolve_impetuosity(s, faction)[0]
    assert result['executed'] and result['battle']['declined_no_effect']
    assert count_pieces(s, rc.NERVII, faction, rc.WARBAND) == 2
    assert len(requests) == 2


def test_only_original_hidden_group_qualifies_but_march_hides_other_origin_pieces():
    s = state(players=(rc.BELGAE,))
    place_piece(s, rc.MORINI, rc.BELGAE, rc.WARBAND, 2)
    place_piece(s, rc.MORINI, rc.BELGAE, rc.WARBAND, 3, piece_state=rc.REVEALED)
    place_piece(s, rc.MORINI, rc.BELGAE, rc.WARBAND, 1, piece_state=rc.SCOUTED)
    with pytest.raises(ValueError): validate_march(s, rc.BELGAE, march(n=3))
    s['decision_agent'] = lambda _,__,req: march() if req['request_type']=='impetuosity_march' else {'decline':True}
    resolve_impetuosity(s, rc.BELGAE)
    assert count_pieces_by_state(s, rc.MORINI, rc.BELGAE, rc.WARBAND, rc.HIDDEN) == 3
    assert count_pieces_by_state(s, rc.MORINI, rc.BELGAE, rc.WARBAND, rc.REVEALED) == 1


def test_cohort_battle_ignores_residents_for_damage_losses_and_reveal():
    s = state(players=(rc.BELGAE,))
    place_piece(s, rc.MORINI, rc.BELGAE, rc.WARBAND, 2)
    place_piece(s, rc.NERVII, rc.BELGAE, rc.WARBAND, 8)
    place_piece(s, rc.NERVII, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    place_piece(s, rc.NERVII, rc.ROMANS, rc.AUXILIA, 5)
    snapshots = []
    def agent(board, actor, request):
        if request['kind'] == 'free_action':
            if request['request_type']=='impetuosity_march': return march()
            snapshots.append((deepcopy(_physical_piece_view(board)), _active_force_context(board)))
            assert count_pieces(board, rc.NERVII, rc.BELGAE) == 2
            assert get_leader_in_region(board, rc.NERVII, rc.BELGAE) is None
            assert is_controlled_by(board, rc.NERVII, rc.BELGAE)
            return battle(rc.NERVII,rc.ROMANS)
        if request['kind'] == 'retreat': return {'retreat':False}
        return None
    s['decision_agent'] = agent
    result = resolve_impetuosity(s, rc.BELGAE)[0]
    assert result['battle']['executed']
    assert count_pieces(s, rc.NERVII, rc.ROMANS, rc.AUXILIA) == 4
    assert count_pieces_by_state(s, rc.NERVII, rc.BELGAE, rc.WARBAND, rc.HIDDEN) == 8
    assert get_leader_in_region(s, rc.NERVII, rc.BELGAE) == rc.AMBIORIX
    assert FREE_FORCE_KEY not in s
    physical, lines = snapshots[0]
    assert count_pieces(physical, rc.NERVII, rc.BELGAE, rc.WARBAND) == 10
    assert get_leader_in_region(physical, rc.NERVII, rc.BELGAE) == rc.AMBIORIX
    assert 'Impetuosity free Battle' in '\n'.join(lines)


@pytest.mark.parametrize('response',[march(n=0),march(n=True),march(n=99),
                                    dict(march(),leader=rc.AMBIORIX),
                                    march(destination=rc.PROVINCIA)])
def test_invalid_human_plan_is_rejected_without_mutation(response):
    s=state();place_piece(s,rc.MORINI,rc.BELGAE,rc.WARBAND,2)
    before=encode(s)
    error=validate_free_action_response(s,rc.BELGAE,{'request_type':'impetuosity_march'},response)
    assert error and encode(s)==before


def test_np_preview_does_not_consume_live_rng_or_ask_human():
    s=state();place_piece(s,rc.MORINI,rc.BELGAE,rc.WARBAND,2)
    place_piece(s,rc.NERVII,rc.ROMANS,rc.AUXILIA,1)
    s['decision_agent']=lambda *_: pytest.fail('preview consumed player input')
    rng=s['rng'].getstate()
    assert np_event_available(s,72,rc.BELGAE,True)
    assert s['rng'].getstate()==rng


def test_german_impetuosity_group_is_not_capped_by_enlist_four_piece_limit():
    s = state(rc.SCENARIO_ARIOVISTUS)
    place_piece(s, rc.MORINI, rc.GERMANS, rc.WARBAND, 6)
    place_piece(s, rc.MORINI, rc.ROMANS, rc.AUXILIA)
    result = resolve_impetuosity(s, rc.GERMANS)[0]
    assert result['warbands_marched'] == 6
    assert result['battle']['executed']
    assert count_pieces(s, rc.MORINI, rc.ROMANS) == 0
    assert FREE_FORCE_KEY not in s


def test_generalized_cohort_preserves_existing_enlist_saved_request_shape():
    s = state(rc.SCENARIO_ARIOVISTUS)
    place_piece(s, rc.MORINI, rc.GERMANS, rc.WARBAND, 3)
    with scoped_free_force(s, rc.MORINI, {rc.HIDDEN: 2}):
        assert s[FREE_FORCE_KEY] == {
            'region': rc.MORINI, 'pieces': {rc.MORINI: {rc.HIDDEN: 2}}}
        assert count_pieces(s, rc.MORINI, rc.GERMANS, rc.WARBAND) == 2


def test_frost_uses_smaller_group_when_the_largest_advances_player_control():
    from fs_bot.engine.victory import calculate_victory_margin
    from fs_bot.map.map_data import get_playable_regions_for_state
    s = state(players=(rc.ROMANS, rc.BELGAE))
    for region in get_playable_regions_for_state(s, rc.BELGAE):
        if region != rc.NERVII:
            place_piece(s, region, rc.BELGAE, rc.WARBAND)
    place_piece(s, rc.MORINI, rc.ARVERNI, rc.WARBAND, 5)
    place_piece(s, rc.NERVII, rc.ROMANS, rc.AUXILIA)
    assert calculate_victory_margin(s, rc.BELGAE) > 0
    assert default_plan(s, rc.ARVERNI)['warbands'] == 5
    s['frost'] = True
    plan = default_plan(s, rc.ARVERNI)
    assert plan == dict(march(n=4), target=rc.ROMANS)
    assert not is_controlled_by(s, rc.MORINI, rc.BELGAE)


def test_frost_counts_resident_citadel_for_player_victory_but_not_battle():
    from fs_bot.engine.victory import calculate_victory_margin
    from fs_bot.map.map_data import get_tribes_in_region
    s = state(players=(rc.ROMANS, rc.AEDUI))
    place_piece(s, rc.MORINI, rc.ARVERNI, rc.WARBAND, 2)
    place_piece(s, rc.NERVII, rc.ARVERNI, rc.CITADEL)
    place_piece(s, rc.NERVII, rc.ROMANS, rc.AUXILIA)
    place_piece(s, rc.AEDUI_REGION, rc.AEDUI, rc.ALLY)
    tribe = get_tribes_in_region(rc.AEDUI_REGION, s['scenario'])[0]
    s['tribes'][tribe]['allied_faction'] = rc.AEDUI
    assert calculate_victory_margin(s, rc.AEDUI) == 0
    s['frost'] = True
    assert default_plan(s, rc.ARVERNI) == dict(march(), target=rc.ROMANS)
    result = resolve_impetuosity(s, rc.ARVERNI)[0]
    assert result['battle']['executed']
    assert calculate_victory_margin(s, rc.AEDUI) == 0
    assert count_pieces(s, rc.NERVII, rc.ARVERNI, rc.CITADEL) == 1


def test_frost_counterattack_cannot_remove_unselected_resident_allies():
    from fs_bot.map.map_data import get_tribes_in_region
    s = state()
    place_piece(s, rc.MORINI, rc.ARVERNI, rc.WARBAND, 3)
    for tribe in get_tribes_in_region(rc.ATREBATES, s['scenario']):
        place_piece(s, rc.ATREBATES, rc.ARVERNI, rc.ALLY)
        s['tribes'][tribe]['allied_faction'] = rc.ARVERNI
    place_piece(s, rc.ATREBATES, rc.ROMANS, rc.LEGION, 5,
                from_legions_track=True)
    s['frost'] = True
    plan = default_plan(s, rc.ARVERNI)
    assert plan == dict(march(destination=rc.ATREBATES, n=3), target=rc.ROMANS)


def test_human_default_battle_uses_impetuosity_highest_player_margin():
    from fs_bot.map.map_data import get_tribes_in_region
    from fs_bot.engine.victory import calculate_victory_margin
    s = state(players=(rc.BELGAE, rc.ROMANS, rc.AEDUI))
    place_piece(s, rc.MORINI, rc.BELGAE, rc.WARBAND, 4)
    place_piece(s, rc.NERVII, rc.ROMANS, rc.LEGION, 1,
                from_legions_track=True)
    place_piece(s, rc.NERVII, rc.AEDUI, rc.WARBAND, 2)
    # Allied Tribes put player Aedui ahead of Rome's victory margin.
    for region in (rc.AEDUI_REGION, rc.SEQUANI, rc.MANDUBII):
        for tribe in get_tribes_in_region(region, s['scenario']):
            place_piece(s, region, rc.AEDUI, rc.ALLY)
            s['tribes'][tribe]['allied_faction'] = rc.AEDUI
    cities = [tribe for tribe in rc.TRIBE_TO_CITY
              if s['tribes'][tribe]['allied_faction'] is None][:2]
    for tribe in cities:
        place_piece(s, rc.TRIBE_TO_REGION[tribe], rc.AEDUI, rc.CITADEL)
        s['tribes'][tribe]['allied_faction'] = rc.AEDUI
    assert calculate_victory_margin(s, rc.AEDUI) > calculate_victory_margin(s, rc.ROMANS)
    s['decision_agent'] = lambda _, __, request: (
        march(n=4) if request.get('request_type') == 'impetuosity_march'
        else {'use_default': True} if request['kind'] == 'free_action' else None)
    result = resolve_impetuosity(s, rc.BELGAE)[0]
    assert result['battle']['battles_resolved'] == [(rc.NERVII, rc.AEDUI)]
