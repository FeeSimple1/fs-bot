"""Published NP consent and replanning keep live decisions out of previews."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces
from fs_bot.board.control import calculate_control
from fs_bot.cards.card_effects import execute_event
from fs_bot.engine.diviciacus import KEY, _np_agrees, _targets, command_scope
from fs_bot.engine.diviciacus_planning import (
    CONFIRMATIONS, plan_with_diviciacus, planning_sa_view, planning_event_view)
from fs_bot.engine.execute import execute_decision, _resolve_free_command
from fs_bot.state.state_schema import build_initial_state


def board(*, leader=False, actor=rc.ROMANS, np_partner=False):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS if leader else rc.SCENARIO_GREAT_REVOLT, seed=39)
    state['non_player_factions'] = {actor}
    if np_partner:
        state['non_player_factions'].update((rc.ROMANS, rc.AEDUI))
    state['resources'][rc.ROMANS] = state['resources'][rc.AEDUI] = 10
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 2)
    if leader:
        place_piece(state, rc.CARNUTES, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    else:
        execute_event(state, 38)
    return state


def march_plan(state):
    return {'command': 'March', 'sa': 'No SA', 'regions': [rc.CARNUTES],
            'details': {'origins': [rc.CARNUTES], 'destinations': [rc.MANDUBII],
                        'routes': {rc.CARNUTES: [rc.MANDUBII]},
                        'groups': {rc.CARNUTES: {rc.AUXILIA: count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)}}}}


@pytest.mark.parametrize('nested', [False, True])
def test_scout_consent_uses_executable_target_shape(monkeypatch, nested):
    state = board(leader=True, np_partner=True)
    monkeypatch.setattr('fs_bot.engine.victory.calculate_victory_score', lambda *_: 12)
    scout = {'scout_targets': [{'region': rc.CARNUTES, 'enemy': rc.AEDUI, 'hidden': 2}]}
    details = {'sa_details': {'scout_plan': scout}} if nested else {'scout_plan': scout}
    action = {'command': 'March', 'sa': 'Scout', 'details': details}
    assert _targets(action, rc.CARNUTES) == [rc.AEDUI]
    assert not _np_agrees(state, rc.AEDUI, rc.ROMANS, rc.CARNUTES, action, 'special_ability')
    scout['scout_targets'][0]['hidden'] = 0
    assert _np_agrees(state, rc.AEDUI, rc.ROMANS, rc.CARNUTES, action, 'special_ability')


def test_implicit_scout_consent_checks_post_command_plan_without_live_input(monkeypatch):
    state = board(leader=True, np_partner=True)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    monkeypatch.setattr('fs_bot.engine.victory.calculate_victory_score', lambda *_: 12)
    state['decision_agent'] = lambda *_: pytest.fail('preview consulted live human')
    rng = state['rng'].getstate()
    action = {'command': 'March', 'sa': 'Scout', 'details': {}}
    assert not _np_agrees(state, rc.AEDUI, rc.ROMANS, rc.CARNUTES, action, 'special_ability')
    assert state['rng'].getstate() == rng


@pytest.mark.parametrize('score,agrees', [(12, True), (13, False)])
def test_aedui_lender_score_threshold(monkeypatch, score, agrees):
    state = board(np_partner=True)
    monkeypatch.setattr('fs_bot.engine.victory.calculate_victory_score', lambda *_: score)
    assert _np_agrees(state, rc.AEDUI, rc.ROMANS, rc.CARNUTES, {'command': 'March'}, 'command') is agrees


@pytest.mark.parametrize('command,key', [('Battle', 'battle_plan'), ('Raid', 'raid_plan')])
@pytest.mark.parametrize('target,agrees', [(rc.ROMANS, False), (rc.BELGAE, True)])
def test_roman_lender_refuses_only_actions_targeting_romans(command, key, target, agrees):
    state = board(actor=rc.AEDUI, np_partner=True)
    action = {'command': command, 'details': {key: [{'region': rc.CARNUTES, 'target': target}]}}
    assert _np_agrees(state, rc.ROMANS, rc.AEDUI, rc.CARNUTES, action, 'command') is agrees


@pytest.mark.parametrize('agree', [True, False])
def test_live_refusal_replans_same_rng_and_executes_without_second_request(agree):
    state = board()
    calls, counts, randoms = [], [], []
    def consent(s, faction, request):
        if request['kind'] == 'agreement':
            calls.append((faction, request))
            return agree
        return None
    state['decision_agent'] = consent
    before_board = deepcopy(state['spaces'])
    control = calculate_control(state, rc.CARNUTES)
    expected_rng = deepcopy(state['rng'])
    expected_rng.random()
    def planner(sim):
        counts.append(count_pieces(sim, rc.CARNUTES, rc.ROMANS, rc.AUXILIA))
        randoms.append(sim['rng'].random())
        return march_plan(sim)
    action = plan_with_diviciacus(state, rc.ROMANS, planner)
    assert counts == ([3] if agree else [3, 1])
    assert len(set(randoms)) == 1
    assert state['rng'].getstate() == expected_rng.getstate()
    assert state['spaces'] == before_board
    assert calculate_control(state, rc.CARNUTES) == control
    assert action['details']['diviciacus_regions'] == ([rc.CARNUTES] if agree else [])
    result = execute_decision(state, rc.ROMANS, {'bot_action': action})
    assert result['executed'] and not result.get('errors')
    assert len(calls) == 1
    assert CONFIRMATIONS not in state and KEY not in state
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == (2 if agree else 0)


def test_detached_planning_never_consumes_human_consent():
    state = board()
    state['_diviciacus_preview'] = True
    state['decision_agent'] = lambda *_: pytest.fail('preview consulted live human')
    action = plan_with_diviciacus(state, rc.ROMANS, march_plan)
    assert action['details']['groups'][rc.CARNUTES][rc.AUXILIA] == 3
    assert CONFIRMATIONS not in state


@pytest.mark.parametrize('leader,sa_count', [(False, 1), (True, 3)])
def test_command_sa_and_event_planners_have_separate_force_views(leader, sa_count):
    state = board(leader=leader)
    state['_diviciacus_preview'] = True
    @planning_sa_view
    def sa(sim):
        return count_pieces(sim, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    @planning_event_view
    def event(sim):
        return count_pieces(sim, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    def planner(sim):
        assert count_pieces(sim, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 3
        assert sa(sim) == sa_count
        assert event(sim) == 1
        assert count_pieces(sim, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 3
        return march_plan(sim)
    plan_with_diviciacus(state, rc.ROMANS, planner)
    assert KEY not in state


def test_free_grant_refusal_replans_scoped_command_and_is_still_free():
    state = board()
    calls, observed = [], []
    def consent(s, faction, request):
        if request['kind'] == 'agreement':
            calls.append(request)
            return False
        return None
    state['decision_agent'] = consent
    def planner(sim):
        observed.append((count_pieces(sim, rc.CARNUTES, rc.ROMANS, rc.AUXILIA), sim['rng'].random()))
        assert sim['_command_region_scope'] == {rc.CARNUTES}
        assert sim['_command_exclusions'] == {'Battle'}
        assert not sim['_command_with_sa']
        return march_plan(sim)
    before = state['resources'][rc.ROMANS]
    result = _resolve_free_command(state, rc.ROMANS, allowed_regions={rc.CARNUTES},
                                   exclude_commands={'Battle'}, limited=True, _planner=planner)
    assert result['executed'], result
    assert [count for count, _ in observed] == [3, 1]
    assert observed[0][1] == observed[1][1]
    assert state['resources'][rc.ROMANS] == before
    assert len(calls) == 1
    assert CONFIRMATIONS not in state and KEY not in state
    assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == 0


def test_published_aedui_flowchart_can_choose_battle_only_with_agreed_auxilia():
    from fs_bot.bots.bot_dispatch import dispatch_bot_turn
    from fs_bot.board.pieces import remove_piece
    state = board(actor=rc.AEDUI)
    state['can_play_event'] = False
    state['current_card_faction_order'] = []
    state['next_card_faction_order'] = []
    remove_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 3)
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.ALLY)
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND)
    state['decision_agent'] = lambda *_: True
    accepted = dispatch_bot_turn(state, rc.AEDUI)
    assert accepted['command'] == 'Battle', accepted
    assert accepted['details']['battle_plan'][0]['target'] == rc.ARVERNI
    state['decision_agent'] = lambda *_: False
    refused = dispatch_bot_turn(state, rc.AEDUI)
    assert refused['command'] == 'Rally', refused
    assert refused['details']['diviciacus_regions'] == []


def test_human_default_plans_do_not_implicitly_opt_in_to_a_loan():
    state = board()
    state['non_player_factions'] = set()
    state['decision_agent'] = lambda *_: pytest.fail('unsolicited loan request')
    action = plan_with_diviciacus(state, rc.ROMANS, march_plan)
    assert action['details']['groups'][rc.CARNUTES][rc.AUXILIA] == 1
    assert 'diviciacus_regions' not in action['details']


@pytest.mark.parametrize('agree', [False, True])
def test_free_battle_refusal_reselects_from_actual_opposing_forces(agree):
    from fs_bot.engine.execute import _plan_free_battle_command, _execute_battle
    state = board()
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    requests = []
    def consent(s, f, request):
        if request['kind'] == 'agreement':
            requests.append(request)
            return agree
    state['decision_agent'] = consent
    action = _plan_free_battle_command(state, rc.ROMANS, {rc.CARNUTES}, no_retreat=True)
    target = action['details']['battle_plan'][0]['target']
    assert target == (rc.BELGAE if agree else rc.AEDUI)
    assert action['details']['no_retreat'] is True
    assert action['details']['diviciacus_regions'] == ([rc.CARNUTES] if agree else [])
    result = _execute_battle(state, rc.ROMANS, action)
    assert result['executed'], result
    commands = [r for r in requests if r['context']['phase'] == 'command']
    assert len(commands) == 1 and CONFIRMATIONS not in state


def test_free_rally_refusal_retains_forced_command_and_region(monkeypatch):
    from fs_bot.engine.execute import _resolve_free_rally
    state = board(actor=rc.AEDUI)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.ALLY)
    observed, requests = [], []
    def consent(s, f, request):
        if request['kind'] == 'agreement':
            requests.append(request)
            return False
    state['decision_agent'] = consent
    def rally(sim):
        observed.append((count_pieces(sim, rc.CARNUTES, rc.AEDUI, rc.WARBAND), sim['rng'].random()))
        assert sim['_command_region_scope'] == {rc.CARNUTES}
        return {'command': 'Rally', 'sa': 'No SA', 'regions': [rc.CARNUTES],
                'details': {'rally_plan': {'warbands': [rc.CARNUTES]}}}
    monkeypatch.setattr('fs_bot.bots.aedui_bot.node_a_rally', rally)
    before = state['resources'][rc.AEDUI]
    result = _resolve_free_rally(state, rc.AEDUI, {rc.CARNUTES}, max_regions=1)
    assert result['executed'], result
    assert [n for n, _ in observed] == [3, 2]
    assert observed[0][1] == observed[1][1]
    assert len(requests) == 1
    assert state['resources'][rc.AEDUI] == before
    assert CONFIRMATIONS not in state and KEY not in state


def test_card70_march_and_followup_battle_obtain_separate_agreements():
    from fs_bot.engine.execute import _resolve_card70_march_battle
    state = board()
    place_piece(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND, 2)
    requests = []
    def consent(s, f, request):
        if request['kind'] == 'agreement' and request.get('request_type') == 'diviciacus':
            requests.append(request['context'])
            return request['context']['command'] == 'March'
        return None
    state['decision_agent'] = consent
    result = _resolve_card70_march_battle(state, [rc.MANDUBII], 4)
    assert result[0]['moved']['auxilia'] == 3
    assert [r['command'] for r in requests] == ['March', 'Battle']
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 0
    assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == 2
    assert CONFIRMATIONS not in state and KEY not in state


@pytest.mark.parametrize('leader,expected', [(False, None), (True, rc.CARNUTES)])
def test_aedui_ambush_eligibility_uses_sa_force_view(leader, expected):
    from fs_bot.bots.aedui_bot import _check_ambush
    from fs_bot.board.pieces import flip_piece
    state = board(leader=leader, actor=rc.AEDUI)
    state['_diviciacus_preview'] = True
    flip_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 2,
               from_state=rc.HIDDEN, to_state=rc.REVEALED)
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, piece_state=rc.REVEALED)
    def planner(sim):
        assert _check_ambush(sim, [{'region': rc.CARNUTES, 'target': rc.ARVERNI}], sim['scenario']) == expected
        return {'command': 'Battle', 'sa': 'No SA', 'details': {
            'battle_plan': [{'region': rc.CARNUTES, 'target': rc.ARVERNI}]}}
    plan_with_diviciacus(state, rc.AEDUI, planner)


@pytest.mark.parametrize('origin,leader,steps', [
    (rc.MORINI, False, 2), (rc.PROVINCIA, True, 3)])
def test_card70_reaches_printed_second_or_caesars_third_region(origin, leader, steps):
    from fs_bot.engine.execute import _resolve_card70_march_battle, _card70_route
    from fs_bot.board.pieces import get_leader_in_region
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=90)
    state['non_player_factions'] = {rc.ROMANS}
    place_piece(state, origin, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, origin, rc.ROMANS, rc.LEGION, 5, from_legions_track=True)
    if leader:
        place_piece(state, origin, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND)
    assert len(_card70_route(state, origin, rc.CARNUTES, steps)) == steps
    result = _resolve_card70_march_battle(state, [rc.CARNUTES], 4)
    assert result[0]['region'] == rc.CARNUTES
    assert result[0]['moved'] == {'legions': 4, 'auxilia': 2}
    assert count_pieces(state, origin, rc.ROMANS, rc.LEGION) == 1
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 2
    assert get_leader_in_region(state, rc.CARNUTES, rc.ROMANS) == (rc.CAESAR if leader else None)


def test_card70_route_cannot_continue_through_crossing_stop():
    from fs_bot.engine.execute import _card70_route
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT)
    # Every two-step Morini-Carnutes route enters Atrebates first.
    state['markers'].setdefault(rc.ATREBATES, {})[rc.MARKER_DEVASTATED] = True
    assert _card70_route(state, rc.MORINI, rc.CARNUTES, 2) is None
    assert _card70_route(state, rc.PROVINCIA, rc.CARNUTES, 2) is None


def test_card70_keeps_transit_residents_and_their_visibility_out_of_moving_cohort():
    from fs_bot.engine.execute import _resolve_card70_march_battle
    from fs_bot.board.pieces import count_pieces_by_state
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=90)
    state['non_player_factions'] = {rc.ROMANS}
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 5, piece_state=rc.REVEALED)
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, piece_state=rc.REVEALED)
    place_piece(state, rc.ATREBATES, rc.GERMANS, rc.WARBAND, 3)
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND)
    result = _resolve_card70_march_battle(state, [rc.CARNUTES], 4)
    assert result[0]['region'] == rc.CARNUTES
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 4
    assert count_pieces_by_state(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 1
    assert count_pieces(state, rc.MORINI, rc.ROMANS, rc.AUXILIA) == 0


def test_card70_moving_only_flip_leaves_unselected_origin_pieces_revealed():
    from fs_bot.engine.execute import _execute_march
    from fs_bot.board.pieces import count_pieces_by_state
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=90)
    state['non_player_factions'] = {rc.ROMANS}
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 3, piece_state=rc.REVEALED)
    action = {'command': 'March', 'details': {
        'origins': [rc.MORINI], 'destinations': [rc.CARNUTES],
        'routes': {rc.MORINI: [rc.ATREBATES, rc.CARNUTES]},
        'groups': {rc.MORINI: {rc.AUXILIA: 1}}}}
    result = _execute_march(state, rc.ROMANS, action, free=True, moving_only=True)
    assert result['executed'] and not result['errors']
    assert count_pieces_by_state(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 2
    assert count_pieces_by_state(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 1
