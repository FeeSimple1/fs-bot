"""Card62 movement precedes the faction's one-Region free Command."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import is_controlled_by, refresh_all_control
from fs_bot.board.pieces import (place_piece, count_pieces, count_pieces_by_state,
                                 get_available)
from fs_bot.cards.war_fleet import (derive_war_fleet, np_war_fleet_available,
                                   coastal_regions, _apply)
from fs_bot.engine.execute import _execute_event
from fs_bot.map.map_data import get_tribes_in_region
from fs_bot.state.state_schema import build_initial_state


def position(scenario=rc.SCENARIO_PAX_GALLICA, seed=1):
    state = build_initial_state(scenario, seed=seed)
    state['non_player_factions'] = {rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE}
    state['current_card'] = state['current_card_id'] = 62
    return state


def execute(state, faction):
    return _execute_event(state, faction, {'details': {
        'card_id': 62, 'text_preference': rc.EVENT_SHADED}})


def ally(state, region, faction):
    for tribe in get_tribes_in_region(region, state['scenario']):
        if state['tribes'][tribe].get('allied_faction') is None:
            place_piece(state, region, faction, rc.ALLY)
            state['tribes'][tribe]['allied_faction'] = faction
            return
    raise AssertionError('no unallied tribe')


def test_arverni_all_bot_game_has_no_printed_player_target():
    # All five recorded Arverni Card62 failures had this same missing
    # instruction prerequisite. Enemy NP pieces cannot substitute for players.
    state = position()
    place_piece(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND, 8)
    place_piece(state, rc.VENETI, rc.ROMANS, rc.AUXILIA, 2)
    assert derive_war_fleet(state, rc.ARVERNI) == {'moves': []}
    assert not np_war_fleet_available(state, rc.ARVERNI)


def test_arverni_gathers_visibility_and_leader_then_battles_chosen_player():
    state = position()
    state['non_player_factions'].remove(rc.ROMANS)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.LEADER,
                leader_name=rc.VERCINGETORIX)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, 3,
                piece_state=rc.REVEALED)
    place_piece(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND, 4,
                piece_state=rc.SCOUTED)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA)
    # A stronger NP target is not the player selected by the instruction.
    place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND, 2)
    result = execute(state, rc.ARVERNI)
    assert result['executed']
    battle = result['free_actions'][0]['result']
    assert battle['executed'] and not battle.get('errors')
    assert battle['battles_resolved'] == [(rc.MORINI, rc.ROMANS)]
    assert count_pieces(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.LEADER) == 0
    assert count_pieces(state, rc.MORINI, rc.ARVERNI, rc.LEADER) == 1
    assert count_pieces(state, rc.MORINI, rc.BELGAE, rc.WARBAND) == 2
    assert not state.get('event_params')


def test_arverni_player_priority_precedes_larger_nonroman_target():
    state = position()
    state['non_player_factions'] -= {rc.ROMANS, rc.AEDUI}
    place_piece(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND, 7)
    place_piece(state, rc.VENETI, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.MORINI, rc.AEDUI, rc.WARBAND, 3)
    params = derive_war_fleet(state, rc.ARVERNI)
    assert params['_war_fleet_battle'] == {'region': rc.VENETI, 'target': rc.ROMANS}
    assert {move['to_region'] for move in params['moves']} == {rc.VENETI}


def test_arverni_insufficient_force_cannot_take_required_control():
    state = position()
    state['non_player_factions'].remove(rc.ROMANS)
    place_piece(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 4)
    assert not np_war_fleet_available(state, rc.ARVERNI)


def test_arverni_leader_can_relocate_and_battle_without_warbands():
    state = position()
    state['non_player_factions'].remove(rc.ROMANS)
    place_piece(state, rc.PICTONES, rc.ARVERNI, rc.LEADER,
                leader_name=rc.VERCINGETORIX)
    ally(state, rc.MORINI, rc.ARVERNI)
    ally(state, rc.MORINI, rc.ROMANS)
    params = derive_war_fleet(state, rc.ARVERNI)
    assert params['_war_fleet_battle'] == {'region': rc.MORINI, 'target': rc.ROMANS}
    assert [m['piece_type'] for m in params['moves']] == [rc.LEADER]


@pytest.mark.parametrize('scenario', [rc.SCENARIO_PAX_GALLICA, rc.SCENARIO_ARIOVISTUS])
def test_aedui_moves_only_single_largest_original_group_preserving_visibility(scenario):
    state = position(scenario)
    place_piece(state, rc.PICTONES, rc.AEDUI, rc.WARBAND, 3, piece_state=rc.REVEALED)
    place_piece(state, rc.PICTONES, rc.AEDUI, rc.WARBAND, 2, piece_state=rc.SCOUTED)
    place_piece(state, rc.MORINI, rc.AEDUI, rc.WARBAND, 2)
    before = deepcopy(state['spaces'])
    params = derive_war_fleet(state, rc.AEDUI)
    assert state['spaces'] == before
    assert {m['from_region'] for m in params['moves']} == {rc.PICTONES}
    assert sum(m['count'] for m in params['moves']) == 5
    assert len({m['to_region'] for m in params['moves']}) == 1
    destination = params['moves'][0]['to_region']
    assert destination in coastal_regions(state, rc.AEDUI)
    _apply(state, rc.AEDUI, params['moves'])
    assert count_pieces_by_state(state, destination, rc.AEDUI, rc.WARBAND, rc.REVEALED) == 3
    assert count_pieces_by_state(state, destination, rc.AEDUI, rc.WARBAND, rc.SCOUTED) == 2
    if scenario == rc.SCENARIO_ARIOVISTUS:
        assert rc.BRITANNIA not in coastal_regions(state, rc.AEDUI)


def test_belgae_movement_makes_rally_available_with_empty_warband_pool():
    # The recorded Gallic War seed7 state had full Home tribes and no
    # Available Warbands. Coastal surplus can still gain Control and an Ally.
    state = position()
    for _ in get_tribes_in_region(rc.MORINI, state['scenario']):
        ally(state, rc.MORINI, rc.BELGAE)
    place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND)
    place_piece(state, rc.SUGAMBRI, rc.BELGAE, rc.WARBAND,
                get_available(state, rc.BELGAE, rc.WARBAND))
    refresh_all_control(state)
    before_allies = get_available(state, rc.BELGAE, rc.ALLY)
    assert np_war_fleet_available(state, rc.BELGAE)
    params = derive_war_fleet(state, rc.BELGAE)
    assert sum(m['count'] for m in params['moves']) == 1
    assert {m['from_region'] for m in params['moves']} == {rc.MORINI}
    result = execute(state, rc.BELGAE)
    assert result['executed']
    rally = result['free_actions'][0]['result']
    assert rally['executed'] and not rally.get('errors')
    assert is_controlled_by(state, rc.MORINI, rc.BELGAE)
    assert get_available(state, rc.BELGAE, rc.ALLY) == before_allies - 1


def test_belgae_never_spends_control_or_leader_escort_for_movement():
    state = position()
    place_piece(state, rc.MORINI, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND, 4)
    place_piece(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 3)
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, 2)
    refresh_all_control(state)
    assert not derive_war_fleet(state, rc.BELGAE)['moves']


def test_availability_preview_is_detached_from_player_and_live_rng():
    state = position()
    place_piece(state, rc.PICTONES, rc.AEDUI, rc.WARBAND, 3)
    def forbidden(*args):
        raise AssertionError('availability consulted a human')
    state['decision_agent'] = forbidden
    before = deepcopy({k: v for k, v in state.items() if k != 'decision_agent'})
    assert np_war_fleet_available(state, rc.AEDUI)
    assert state['spaces'] == before['spaces']
    assert state['available'] == before['available']
    assert state['rng'].getstate() == before['rng'].getstate()
    assert state['decision_agent'] is forbidden


def test_arverni_frost_rejects_player_victory_advance_from_counterattack():
    # Three Arverni Allies plus three incoming Warbands take Control from
    # five Legions. The ensuing Counterattack can remove an Arverni Ally,
    # increasing already-winning player Rome's Subdued+Allied total.
    state = position()
    state['non_player_factions'].remove(rc.ROMANS)
    for _ in range(3):
        ally(state, rc.ATREBATES, rc.ARVERNI)
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.LEGION, 5,
                from_legions_track=True)
    place_piece(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND, 3)
    refresh_all_control(state)
    assert derive_war_fleet(state, rc.ARVERNI).get('_war_fleet_battle')
    state['frost'] = True
    before = deepcopy(state['spaces'])
    assert derive_war_fleet(state, rc.ARVERNI) == {'moves': []}
    assert not np_war_fleet_available(state, rc.ARVERNI)
    assert state['spaces'] == before


def test_belgae_cannot_move_enough_to_only_subdued_destination():
    state = position()
    # Reproduce the decisive constraints of Gallic War seed7: only
    # Atrebates can accept an Ally, nine incoming WB are needed there,
    # and the two coastal Warbands cannot produce that Control.
    for region in coastal_regions(state, rc.BELGAE):
        if region != rc.ATREBATES:
            for tribe in get_tribes_in_region(region, state['scenario']):
                state['tribes'][tribe]['status'] = rc.DISPERSED
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, 8)
    for region in (rc.MORINI, rc.BRITANNIA):
        place_piece(state, region, rc.BELGAE, rc.WARBAND)
    place_piece(state, rc.SUGAMBRI, rc.BELGAE, rc.WARBAND,
                get_available(state, rc.BELGAE, rc.WARBAND))
    refresh_all_control(state)
    assert not derive_war_fleet(state, rc.BELGAE)['moves']
    assert not np_war_fleet_available(state, rc.BELGAE)


def test_belgae_adds_multiple_controls_without_moving_arrivals_again():
    state = position()
    ally(state, rc.MORINI, rc.BELGAE)
    place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND, 6)
    refresh_all_control(state)
    params = derive_war_fleet(state, rc.BELGAE)
    assert len({m['to_region'] for m in params['moves']}) > 1
    assert {m['from_region'] for m in params['moves']} == {rc.MORINI}
    assert all(m['count'] == 1 for m in params['moves'])
    _apply(state, rc.BELGAE, params['moves'])
    assert is_controlled_by(state, rc.MORINI, rc.BELGAE)
    assert all(is_controlled_by(state, m['to_region'], rc.BELGAE)
               for m in params['moves'])


def test_human_arverni_keeps_explicit_movement_and_free_command_choice():
    state = position()
    state['non_player_factions'].remove(rc.ARVERNI)
    place_piece(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND)
    def human(board, faction, request):
        assert faction == rc.ARVERNI
        assert request['request_type'] == 'event_command'
        assert count_pieces(board, rc.MORINI, rc.ARVERNI, rc.WARBAND) == 1
        return {'command': rc.CMD_RALLY, 'sa': 'No SA', 'regions': [rc.ARVERNI_REGION],
                'details': {'rally_plan': {'warbands': [{'region': rc.ARVERNI_REGION}]}}}
    state['decision_agent'] = human
    result = _execute_event(state, rc.ARVERNI, {'details': {
        'card_id': 62, 'event_params': {'moves': [{
            'from_region': rc.PICTONES, 'to_region': rc.MORINI,
            'piece_type': rc.WARBAND, 'count': 1}]}}}, human=True)
    assert result['executed']
    assert result['free_actions'][0]['result']['command'] == rc.CMD_RALLY
    assert count_pieces(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND) == 1


@pytest.mark.parametrize('card', [13, 59])
def test_arverni_frost_includes_command_prefire_and_germanic_horse(card):
    # One incoming Warband takes Control with two Allies. An ordinary
    # Counterattack only removes that Warband. Slingers' pre-fire or
    # Germanic Horse's full Auxilia Losses also remove an Ally, improving
    # already-winning player Rome's score: §8.4.4 forbids the Event.
    from fs_bot.cards.capabilities import activate_capability
    state = position()
    state['non_player_factions'].remove(rc.ROMANS)
    for _ in range(2):
        ally(state, rc.ATREBATES, rc.ARVERNI)
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND)
    refresh_all_control(state)
    state['frost'] = True
    assert derive_war_fleet(state, rc.ARVERNI).get('_war_fleet_battle')
    activate_capability(state, card, rc.EVENT_UNSHADED)
    assert derive_war_fleet(state, rc.ARVERNI) == {'moves': []}


def test_command_frost_outcomes_include_massed_archers_before_attack():
    from fs_bot.cards.capabilities import activate_capability
    from fs_bot.cards.divination_np import _battle_frost_outcomes
    state = position()
    state['non_player_factions'].remove(rc.ROMANS)
    place_piece(state, rc.ATREBATES, rc.ARVERNI, rc.WARBAND, 6)
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, 4)
    activate_capability(state, 27, rc.EVENT_SHADED)
    outcomes = list(_battle_frost_outcomes(
        state, rc.ATREBATES, rc.ROMANS, attacker=rc.ARVERNI, command=True))
    assert outcomes
    # One preliminary Loss plus three Attack Losses removes all four.
    assert all(count_pieces(outcome, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 0
               for outcome in outcomes)
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 4


def test_arverni_bot_declines_war_fleet_without_player_target():
    from fs_bot.bots.bot_common import should_decline_event
    state = position()
    place_piece(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND, 8)
    place_piece(state, rc.VENETI, rc.ROMANS, rc.AUXILIA, 2)
    assert should_decline_event(state, 62, rc.ARVERNI)
