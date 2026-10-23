"""Card36 text, printed NP instructions, and complete granted Commands."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, count_pieces_by_state
from fs_bot.cards.morasses import (default_battle, default_march, resolve_morasses,
    march_request, battle_request, np_available, execute_march)
from fs_bot.cards.event_conditions import np_event_available
from fs_bot.bots.bot_common import should_decline_event
from fs_bot.cli.free_actions import collect_free_action
from fs_bot.engine.free_actions import validate_free_action_response, execute_free_action_plan
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import encode


def state():
    st = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=36)
    st['current_card'] = st['current_card_id'] = 36
    st['non_player_factions'] = {rc.ROMANS, rc.ARVERNI, rc.BELGAE, rc.AEDUI}
    return st


def force(st, region, faction=rc.BELGAE, n=4, visibility=rc.HIDDEN):
    place_piece(st, region, faction, rc.WARBAND, n, piece_state=visibility)


def battle(region, enemy=rc.ROMANS):
    return {'command': rc.CMD_BATTLE, 'sa': rc.SA_AMBUSH, 'sa_regions': [region], 'regions': [region],
            'details': {'battle_plan': [{'region': region, 'target': enemy}]}}


def test_belgae_ambush_romans_then_gauls_never_germans_then_hide_without_moving():
    st = state()
    for region in (rc.MORINI, rc.NERVII, rc.TREVERI):
        force(st, region, visibility=rc.REVEALED)
        force(st, region, rc.GERMANS, 5)
    place_piece(st, rc.MORINI, rc.ROMANS, rc.AUXILIA, 2)
    force(st, rc.MORINI, rc.ARVERNI, 5)
    force(st, rc.NERVII, rc.AEDUI, 2)
    force(st, rc.NERVII, rc.ARVERNI, 4)
    before_resources = dict(st['resources'])
    result = resolve_morasses(st, rc.BELGAE)[0]
    assert result['battle']['battles_resolved'] == [(rc.MORINI, rc.ROMANS), (rc.NERVII, rc.AEDUI)]
    assert result['battle']['battle_sa_executed'] and result['march']['executed']
    assert all(count_pieces_by_state(st, r, rc.BELGAE, rc.WARBAND, rc.HIDDEN) == 4
               for r in (rc.MORINI, rc.NERVII, rc.TREVERI))
    assert all(count_pieces(st, r, rc.GERMANS, rc.WARBAND) == 5
               for r in (rc.MORINI, rc.NERVII, rc.TREVERI))
    assert st['resources'] == before_resources and validate_state(st) == []


def test_ineffective_event_is_declined_before_selection_without_rng_or_human_calls():
    st = state()
    force(st, rc.MORINI, n=1)
    force(st, rc.NERVII, n=4)
    force(st, rc.NERVII, rc.GERMANS, n=2)
    st['decision_agent'] = lambda *_: pytest.fail('Hypothetical planning asked a player')
    before = encode({k:v for k,v in st.items() if k != 'decision_agent'})
    assert np_event_available(st, 36, rc.BELGAE, True) is False
    assert should_decline_event(st, 36, rc.BELGAE)
    assert encode({k:v for k,v in st.items() if k != 'decision_agent'}) == before


def test_only_hide_is_effective_and_scouted_warbands_remain_revealed():
    st = state()
    force(st, rc.MORINI, n=2, visibility=rc.REVEALED)
    force(st, rc.MORINI, n=1, visibility=rc.SCOUTED)
    assert np_available(st, rc.BELGAE)
    result = resolve_morasses(st, rc.BELGAE)[0]
    assert result['battle']['declined_no_effect'] and result['march']['executed']
    assert count_pieces_by_state(st, rc.MORINI, rc.BELGAE, rc.WARBAND, rc.HIDDEN) == 2
    assert count_pieces_by_state(st, rc.MORINI, rc.BELGAE, rc.WARBAND, rc.REVEALED) == 1


@pytest.mark.parametrize('faction', [rc.ROMANS, rc.GERMANS])
def test_nonplayer_cannot_choose_another_factions_benefit(faction):
    st = state(); force(st, rc.MORINI, visibility=rc.REVEALED)
    assert not np_available(st, faction)


def test_arverni_retain_threat_condition_but_account_for_guaranteed_ambush():
    st = state(); force(st, rc.MORINI, rc.ARVERNI, 9, rc.REVEALED)
    force(st, rc.MORINI, rc.AEDUI, 20)
    assert default_battle(st, rc.ARVERNI) is None
    force(st, rc.MORINI, rc.ARVERNI, 1)
    plan = default_battle(st, rc.ARVERNI)
    assert plan['details']['battle_plan'][0]['target'] == rc.AEDUI
    assert plan['details']['battle_plan'][0]['region'] == rc.MORINI


def test_aedui_require_high_value_trigger_and_target_only_player_gauls():
    st = state(); st['non_player_factions'].remove(rc.ARVERNI)
    force(st, rc.MORINI, rc.AEDUI, 4, rc.REVEALED)
    force(st, rc.MORINI, rc.ARVERNI, 1)
    assert default_battle(st, rc.AEDUI) is None
    place_piece(st, rc.MORINI, rc.ARVERNI, rc.ALLY)
    plan = default_battle(st, rc.AEDUI)
    assert plan['details']['battle_plan'][0]['target'] == rc.ARVERNI
    st['non_player_factions'].add(rc.ARVERNI)
    assert default_battle(st, rc.AEDUI) is None


def test_human_executor_selects_other_gallic_beneficiary_who_selects_both_actions():
    st = state(); st['non_player_factions'] = {rc.ARVERNI, rc.BELGAE}
    force(st, rc.MORINI, rc.AEDUI, 4, rc.REVEALED)
    force(st, rc.MORINI, rc.GERMANS, 5)
    calls = []
    def agent(board, faction, request):
        kind = request.get('request_type')
        if kind == 'morasses_faction':
            calls.append((faction, kind)); return {'faction': rc.AEDUI}
        if kind == 'event_command':
            calls.append((faction, kind)); return battle(rc.MORINI, rc.GERMANS)
        if kind == 'morasses_march':
            calls.append((faction, kind)); return {'action': None, 'in_place': [rc.MORINI]}
        return None
    st['decision_agent'] = agent
    result = resolve_morasses(st, rc.ROMANS)[0]
    assert calls == [(rc.ROMANS, 'morasses_faction'), (rc.AEDUI, 'event_command'), (rc.AEDUI, 'morasses_march')]
    assert result['battle']['battle_sa_executed'] and not result['battle']['errors']
    assert count_pieces(st, rc.MORINI, rc.GERMANS, rc.WARBAND) == 3
    assert count_pieces_by_state(st, rc.MORINI, rc.AEDUI, rc.WARBAND, rc.HIDDEN) == 4


def test_one_battle_command_preserves_once_per_command_capability():
    from fs_bot.cards.capabilities import activate_capability, set_capability_owner
    st = state()
    for r in (rc.NERVII, rc.MORINI):
        force(st, r, n=4, visibility=rc.REVEALED)
        place_piece(st, r, rc.ROMANS, rc.AUXILIA, 6)
    activate_capability(st, 59, rc.EVENT_SHADED)
    set_capability_owner(st, 59, rc.BELGAE)
    plan = default_battle(st, rc.BELGAE)
    result = execute_free_action_plan(st, rc.BELGAE, battle_request(), plan)
    assert result['count'] == 2
    assert sorted(count_pieces(st, r, rc.ROMANS, rc.AUXILIA) for r in (rc.NERVII, rc.MORINI)) == [2, 4]
    assert not any(k.startswith('card59_') for k in st['event_modifiers'])


def test_human_march_combines_in_place_and_moving_groups():
    st = state()
    force(st, rc.MORINI, visibility=rc.REVEALED)
    force(st, rc.NERVII, n=2, visibility=rc.SCOUTED)
    action = {'command': rc.CMD_MARCH, 'sa': 'No SA', 'regions': [rc.MORINI],
              'details': {'march_plan': {'origins': [rc.MORINI], 'routes': {rc.MORINI: [rc.NERVII]}, 'destinations': [rc.NERVII],
                                         'groups': {rc.MORINI: {rc.WARBAND: 2}}}}}
    response = {'action': action, 'in_place': [rc.NERVII]}
    assert validate_free_action_response(st, rc.BELGAE, march_request(), response) is None
    result = execute_march(st, rc.BELGAE, response)
    assert result['executed'] and result['moving']['executed']
    assert count_pieces(st, rc.MORINI, rc.BELGAE, rc.WARBAND) == 2
    assert count_pieces(st, rc.NERVII, rc.BELGAE, rc.WARBAND) == 4
    assert count_pieces_by_state(st, rc.NERVII, rc.BELGAE, rc.WARBAND, rc.REVEALED) == 2


@pytest.mark.parametrize('response', [
    {'action': None, 'in_place': []}, {'action': None, 'in_place': [rc.NERVII]},
    {'action': None, 'in_place': [rc.MORINI, rc.MORINI]},
    {'action': None, 'in_place': [rc.MORINI], 'free': True},
    {'action': battle(rc.MORINI), 'in_place': [rc.MORINI]},
])
def test_invalid_march_is_atomic(response):
    st = state(); force(st, rc.MORINI, visibility=rc.REVEALED)
    before = encode(st)
    assert validate_free_action_response(st, rc.BELGAE, march_request(), response)
    assert encode(st) == before


def test_terminal_allows_beneficiary_and_in_place_choice():
    st = state(); force(st, rc.MORINI, visibility=rc.REVEALED)
    out = StringIO()
    response = collect_free_action(st, rc.ROMANS, {'request_type': 'morasses_faction'},
                                   StringIO('Belgae\n'), out)
    assert response == {'faction': rc.BELGAE}
    response = collect_free_action(st, rc.BELGAE, march_request(),
                                   StringIO('Plan the action\nMorini\nDone\n'), out)
    assert response == {'action': None, 'in_place': [rc.MORINI]}


def test_aedui_one_ambush_region_limit_is_independent_of_hidden_waiver():
    st = state()
    for r in (rc.MORINI, rc.NERVII):
        force(st, r, rc.AEDUI, 4, rc.REVEALED)
        force(st, r, rc.GERMANS, 6)
    action = {'command': rc.CMD_BATTLE, 'sa': rc.SA_AMBUSH,
              'sa_regions': [rc.MORINI, rc.NERVII], 'regions': [rc.MORINI, rc.NERVII],
              'details': {'battle_plan': [{'region': r, 'target': rc.GERMANS}
                                           for r in (rc.MORINI, rc.NERVII)]}}
    before = encode(st)
    assert 'one Region' in validate_free_action_response(st, rc.AEDUI, battle_request(), action)
    assert encode(st) == before
    action['sa_regions'] = [rc.MORINI]
    assert validate_free_action_response(st, rc.AEDUI, battle_request(), action) is None
    result = execute_free_action_plan(st, rc.AEDUI, battle_request(), action)
    assert result['count'] == 2 and not result['errors']
    assert count_pieces(st, rc.MORINI, rc.AEDUI, rc.WARBAND) == 4
    assert count_pieces(st, rc.NERVII, rc.AEDUI, rc.WARBAND) == 2


def test_prefire_cannot_be_ignored_when_arverni_leader_is_at_risk():
    from fs_bot.cards.capabilities import activate_capability
    st = state(); force(st, rc.MORINI, rc.ARVERNI, 2)
    place_piece(st, rc.MORINI, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(st, rc.MORINI, rc.ROMANS, rc.AUXILIA, 6)
    assert default_battle(st, rc.ARVERNI)
    activate_capability(st, 13, rc.EVENT_UNSHADED)
    assert default_battle(st, rc.ARVERNI) is None


def test_frost_declines_battle_that_can_advance_human_roman_victory():
    from fs_bot.cards.capabilities import activate_capability
    st = state(); st['non_player_factions'].remove(rc.ROMANS); st['frost'] = True
    # An Ally's removal can advance the Romans' Subdued count. Roman
    # pre-fire against its enemy Command can remove this last defending base.
    from fs_bot.engine.victory import calculate_victory_margin
    # A Battle directly destroys a rival Ally, benefiting the player Romans.
    force(st, rc.MORINI, n=4)
    place_piece(st, rc.MORINI, rc.ARVERNI, rc.ALLY)
    st["tribes"][rc.TRIBE_MORINI]["allied_faction"] = rc.ARVERNI
    # All remaining Tribes begin Subdued in the empty fixture, so Romans
    # are already beyond threshold before this one additional removal.
    assert calculate_victory_margin(st, rc.ROMANS) > 0
    assert default_battle(st, rc.BELGAE) is None


def test_arverni_follow_the_threat_march_box_when_first_command_redirects():
    from fs_bot.cards.capabilities import activate_capability
    from fs_bot.board.pieces import find_leader
    st = state()
    force(st, rc.MORINI, rc.ARVERNI, 2)
    force(st, rc.NERVII, rc.ARVERNI, 6)
    place_piece(st, rc.MORINI, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(st, rc.MORINI, rc.ROMANS, rc.AUXILIA, 6)
    activate_capability(st, 13, rc.EVENT_UNSHADED)
    # No Legion exists for the bottom mass-March box. The actual Battle
    # trigger instead points to withdrawal toward the largest Arverni group.
    assert default_battle(st, rc.ARVERNI) is None
    assert default_march(st, rc.ARVERNI) is None
    assert np_available(st, rc.ARVERNI)
    result = resolve_morasses(st, rc.ARVERNI)[0]
    assert result['battle']['declined_no_effect'] and result['march']['executed']
    assert find_leader(st, rc.ARVERNI) == rc.NERVII
    assert count_pieces(st, rc.NERVII, rc.ARVERNI, rc.WARBAND) == 8


def test_terminal_aedui_choose_one_ambush_region_for_the_multi_region_battle():
    st = state()
    for r in (rc.MORINI, rc.NERVII):
        force(st, r, rc.AEDUI, 4, rc.REVEALED)
        force(st, r, rc.GERMANS, 6)
    output = StringIO()
    response = collect_free_action(st, rc.AEDUI, battle_request(),
        StringIO('Plan the action\nBattle\nMorini\nNervii\nGermans\nGermans\nNervii\n'), output)
    assert response['sa'] == rc.SA_AMBUSH and response['sa_regions'] == [rc.NERVII]
    assert len(response['details']['battle_plan']) == 2
    assert validate_free_action_response(st, rc.AEDUI, battle_request(), response) is None


@pytest.mark.parametrize('scenario,player_choices', [(rc.SCENARIO_GREAT_REVOLT, True),
                                                    (rc.SCENARIO_ARIOVISTUS, False)])
def test_outcome_enumerator_does_not_give_game_run_arverni_player_casualty_choices(
        scenario, player_choices, monkeypatch):
    from fs_bot.cards import morasses_np
    requested = []
    choices = morasses_np._legal_loss_choices
    def record(board, region, actor, request):
        requested.append(actor)
        return choices(board, region, actor, request)
    monkeypatch.setattr(morasses_np, '_legal_loss_choices', record)
    st = build_initial_state(scenario, seed=36)
    st['non_player_factions'] = {rc.BELGAE, rc.ROMANS, rc.AEDUI, rc.GERMANS}
    force(st, rc.MORINI, n=2)
    force(st, rc.MORINI, rc.ARVERNI, 1, rc.HIDDEN)
    force(st, rc.MORINI, rc.ARVERNI, 1, rc.REVEALED)
    result = list(morasses_np.outcomes(st, rc.BELGAE, lambda board: execute_free_action_plan(
        board, rc.BELGAE, battle_request(), battle(rc.MORINI, rc.ARVERNI))))
    assert result
    assert (rc.ARVERNI in requested) == player_choices


def test_frost_filter_cannot_leave_aedui_battling_without_its_high_value_trigger():
    st = state(); st['frost'] = True
    st['non_player_factions'] -= {rc.ROMANS, rc.ARVERNI}
    for r in (rc.MORINI, rc.NERVII):
        force(st, r, rc.AEDUI, 4)
    place_piece(st, rc.MORINI, rc.ARVERNI, rc.ALLY)
    st['tribes'][rc.TRIBE_MORINI]['allied_faction'] = rc.ARVERNI
    force(st, rc.NERVII, rc.ARVERNI, 4)
    # Morini is the sole high-value trigger. Its removal would further
    # advance the already-winning human Romans. Safe additional ordinary
    # Battles cannot survive by themselves after this trigger is rejected.
    assert default_battle(st, rc.AEDUI) is None
