"""Supply confirmation respects Event scopes and A53's separate actions."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import count_pieces, place_piece, remove_piece
from fs_bot.cards.capabilities import activate_capability
from fs_bot.engine import execute as ex
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity


def position(scenario=rc.SCENARIO_ARIOVISTUS):
    state = build_initial_state(scenario, seed=17)
    state['non_player_factions'] = {rc.ROMANS}
    state['resources'][rc.ROMANS] = 10
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    place_piece(state, rc.PROVINCIA, rc.GERMANS, rc.WARBAND, 12)
    # Every supply route must use the controlled Provincia endpoint.
    place_piece(state, rc.CISALPINA, rc.ARVERNI, rc.WARBAND)
    activate_capability(state, 13, rc.EVENT_SHADED)
    refresh_all_control(state)
    return state


def agent_with_answer(state, first):
    calls = []
    def agent(board, faction, request):
        assert board is state
        if request['kind'] == 'free_action':
            return {'use_default': True}
        assert request['kind'] == 'agreement'
        assert request['request_type'] == 'supply_line'
        calls.append((faction, request['context']['region']))
        # A repeated live query would change both legality and placement.
        return first if len(calls) == 1 else not first
    state['decision_agent'] = agent
    return calls


def no_private_context(state):
    assert not [key for key in state if key.startswith(('_supply_line_', '_recruit_supply'))]
    assert '_diviciacus_confirmations' not in state


@pytest.mark.parametrize('scenario', [rc.SCENARIO_ARIOVISTUS, rc.SCENARIO_GALLIC_WAR])
@pytest.mark.parametrize('accepted', [True, False])
def test_forced_free_recruit_confirms_before_placement_and_preserves_scope(scenario, accepted):
    state = position(scenario)
    calls = agent_with_answer(state, accepted)
    rng = state['rng'].getstate()
    resources = state['resources'][rc.ROMANS]
    result = ex._resolve_free_rally(state, rc.ROMANS,
                                   allowed_regions={rc.PROVINCIA}, max_regions=1)
    assert calls == [(rc.GERMANS, rc.PROVINCIA)]
    assert result['executed'] is accepted, result
    if accepted:
        assert [entry['region'] for entry in result['placements']] == [rc.PROVINCIA]
        assert result['errors'] == []
    else:
        assert result['declined_no_effect'], result
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == (2 if accepted else 0)
    assert state['resources'][rc.ROMANS] == resources  # Free despite shaded 13.
    assert state['rng'].getstate() == rng
    assert check_structural_integrity(state) == []
    no_private_context(state)


def test_no_agent_np_controller_refuses_card13_free_recruit():
    state = position()
    state['non_player_factions'].add(rc.GERMANS)
    before = encode(state)
    result = ex._resolve_free_rally(state, rc.ROMANS, allowed_regions={rc.PROVINCIA})
    assert not result['executed'] and result['declined_no_effect'], result
    assert encode(state) == before


def test_refused_supply_replans_before_consulting_a_loan_for_discarded_recruit(monkeypatch):
    state = position()
    state['non_player_factions'].add(rc.GERMANS)
    monkeypatch.setattr('fs_bot.engine.diviciacus_planning.confirm_plan',
                        lambda *_: pytest.fail('Loan requested for a refused Recruit'))
    result = ex._resolve_free_rally(state, rc.ROMANS, allowed_regions={rc.PROVINCIA})
    assert not result['executed'] and result['declined_no_effect']
    no_private_context(state)


@pytest.mark.parametrize('seed,accepted', [(1, True), (17, False)])
def test_free_grant_keeps_real_aedui_consent_roll_when_replanning(seed, accepted, monkeypatch):
    from random import Random
    state = position()
    state['non_player_factions'] = {rc.AEDUI}
    remove_piece(state, rc.PROVINCIA, rc.GERMANS, rc.WARBAND, 12)
    place_piece(state, rc.PROVINCIA, rc.AEDUI, rc.WARBAND, 12)
    refresh_all_control(state)
    state['rng'].seed(seed)
    monkeypatch.setattr('fs_bot.bots.bot_common.calculate_victory_score', lambda *_: 10)
    calls = []
    def human(board, faction, request):
        calls.append(request['kind'])
        assert faction == rc.ROMANS and request['kind'] == 'free_action'
        return {'use_default': True}
    state['decision_agent'] = human
    expected = Random(seed)
    assert (expected.randint(1, 6) <= 4) is accepted
    result = ex._resolve_free_rally(state, rc.ROMANS, allowed_regions={rc.PROVINCIA})
    assert result['executed'] is accepted, result
    assert state['rng'].getstate() == expected.getstate()
    assert calls == ['free_action']
    no_private_context(state)


def test_paused_free_grant_keeps_board_and_rng_for_supply_resume():
    state = position()
    before = encode(state)
    def pause(board, faction, request):
        if request['kind'] == 'free_action':
            return {'use_default': True}
        raise EOFError('await Supply consent')
    state['decision_agent'] = pause
    with pytest.raises(EOFError, match='await Supply'):
        ex._resolve_free_rally(state, rc.ROMANS, allowed_regions={rc.PROVINCIA})
    assert encode({key: value for key, value in state.items() if key != 'decision_agent'}) == before
    calls = agent_with_answer(state, True)
    result = ex._resolve_free_rally(state, rc.ROMANS, allowed_regions={rc.PROVINCIA})
    assert result['executed'] and result['errors'] == []
    assert calls == [(rc.GERMANS, rc.PROVINCIA)]
    no_private_context(state)


@pytest.mark.parametrize('accepted', [True, False])
def test_free_command_replans_recruit_before_live_execution(accepted):
    from fs_bot.bots.roman_bot import node_r_recruit
    state = position()
    for region in (rc.ATREBATES, rc.SEQUANI):
        place_piece(state, region, rc.ROMANS, rc.FORT)
    refresh_all_control(state)
    calls = agent_with_answer(state, accepted)
    result = ex._resolve_free_command(
        state, rc.ROMANS, allowed_regions={rc.ATREBATES, rc.SEQUANI, rc.PROVINCIA},
        _planner=node_r_recruit)
    assert calls == [(rc.GERMANS, rc.PROVINCIA)]
    assert result.get('errors', []) == [], result
    assert (result['command'] == rc.CMD_RECRUIT) is accepted
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == (2 if accepted else 0)
    assert check_structural_integrity(state) == []
    no_private_context(state)


def test_narrowed_recruit_keeps_its_own_supply_dependencies(monkeypatch):
    old = {'requesting_faction': rc.ROMANS, 'faction': rc.BELGAE, 'region': rc.NERVII}
    kept = {'requesting_faction': rc.ROMANS, 'faction': rc.GERMANS, 'region': rc.PROVINCIA}
    def action(request):
        return {'command': rc.CMD_RECRUIT, 'regions': [rc.PROVINCIA], 'sa': 'No SA',
                'details': {'recruit_plan': [{'region': rc.PROVINCIA, 'action': 'place_auxilia'}],
                            'supply_line_requests': [request]}}
    monkeypatch.setattr('fs_bot.bots.roman_bot.node_r_recruit', lambda _: action(kept))
    _, plan = ex._replan_placement_regions(
        position(), rc.ROMANS, rc.CMD_RECRUIT, {rc.PROVINCIA}, action(old))
    assert plan['details']['supply_line_requests'] == [kept]


def test_frumentum_used_sa_cannot_be_forecast_again(monkeypatch):
    from fs_bot.engine.frumentum import _default_action
    from fs_bot.tests.test_recruit_before_build_forecast import captured_state
    state = captured_state('ariovistus-15')
    before = encode({key: value for key, value in state.items() if key != 'rng'})
    monkeypatch.setattr(ex, '_execute_sa',
                        lambda *_: pytest.fail('Frumentum forecast repeated its used SA'))
    request = {'kind': 'frumentum_action', 'remaining_actions': ['Recruit'],
               'remaining_resources': 10, 'reserved_roman_resources': 0,
               'allocated_resources': 10}
    assert _default_action(state, request) == {'decline': True}
    assert encode({key: value for key, value in state.items() if key != 'rng'}) == before


@pytest.mark.parametrize('accepted', [True, False])
def test_frumentum_standalone_build_confirms_only_current_action(accepted, monkeypatch):
    from fs_bot.engine.frumentum import _default_action, _execute, ACTION_SA
    state = position()
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    refresh_all_control(state)
    calls = agent_with_answer(state, accepted)
    request = {'kind': 'frumentum_action', 'remaining_actions': [ACTION_SA],
               'remaining_resources': 10, 'reserved_roman_resources': 0,
               'allocated_resources': 10}
    # The Command branch is irrelevant once both paid Commands are used.
    monkeypatch.setattr('fs_bot.bots.bot_dispatch.dispatch_bot_turn',
                        lambda *_: {'command': rc.CMD_BATTLE, 'sa': 'Besiege'})
    plan = _default_action(state, request)
    assert calls == [(rc.GERMANS, rc.PROVINCIA)]
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.FORT) == 0
    if accepted:
        assert plan['command'] is None and plan['sa'] == rc.SA_BUILD
        result, spent = _execute(state, plan, 10)
        assert result['executed'] and not result.get('errors'), result
        assert spent == 4
        assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.FORT) == 1
    else:
        assert plan == {'decline': True}
    assert calls == [(rc.GERMANS, rc.PROVINCIA)]
    assert check_structural_integrity(state) == []
    no_private_context(state)


def inverse_position():
    """Build consumes two Allies; denied Build leaves a qualifying Recruit."""
    from fs_bot.map.map_data import get_tribes_in_region
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=17)
    state['non_player_factions'] = {rc.ROMANS}
    state['resources'][rc.ROMANS] = 10
    regions = {rc.ATREBATES, rc.MORINI}
    state['_command_region_scope'] = regions
    for region in regions:
        place_piece(state, region, rc.ROMANS, rc.FORT)
        for tribe in get_tribes_in_region(region, state['scenario'])[1:]:
            state['tribes'][tribe]['status'] = rc.MARKER_DISPERSED
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    for region in state['spaces']:
        if region not in (*regions, rc.BRITANNIA):
            place_piece(state, region, rc.GERMANS, rc.WARBAND,
                        4 if region == rc.CISALPINA else 1)
    return state, regions


@pytest.mark.parametrize('exclude_seize', [False, True])
def test_free_command_refusal_can_enable_recruit_before_fallback_exit(exclude_seize):
    from fs_bot.bots.roman_bot import node_r_recruit
    from fs_bot.engine.recruit_planning import CANDIDATE
    state, regions = inverse_position()
    excludes = {rc.CMD_SEIZE} if exclude_seize else set()
    preview = ex._free_command_planning_state(state, rc.ROMANS, regions, excludes, with_sa=True)
    optimistic = node_r_recruit(preview)
    assert optimistic['command'] == ('Pass' if exclude_seize else rc.CMD_SEIZE)
    assert optimistic['details'][CANDIDATE]['details']['potential_auxilia'] == 5
    requests = []
    def refuse(board, faction, request):
        if request['kind'] == 'free_action':
            return {'use_default': True}
        requests.append(request)
        assert request['context']['proposed_action']['command'] == rc.CMD_RECRUIT
        return False
    state['decision_agent'] = refuse
    result = ex._resolve_free_command(
        state, rc.ROMANS, allowed_regions=regions, exclude_commands=excludes,
        with_sa=True, _planner=node_r_recruit)
    assert requests and result['executed'] and result['command'] == rc.CMD_RECRUIT
    assert result['errors'] == []
    assert not (result.get('sa_execution') or {}).get('errors')
    assert {entry['region'] for entry in result['placements']} == regions
    assert all(count_pieces(state, region, rc.ROMANS, rc.ALLY) == 1 for region in regions)
    assert state['resources'][rc.ROMANS] == 10
    assert check_structural_integrity(state) == []
    no_private_context(state)


def test_frumentum_refused_standalone_build_can_enable_recruit():
    from fs_bot.engine.frumentum import _default_action, _execute, ACTION_SA
    state, regions = inverse_position()
    calls = []
    state['decision_agent'] = lambda board, faction, request: calls.append(request) or False
    request = {'kind': 'frumentum_action', 'remaining_actions': ['Recruit', ACTION_SA],
               'remaining_resources': 10, 'reserved_roman_resources': 0,
               'allocated_resources': 10}
    action = _default_action(state, request)
    assert calls and action['command'] == rc.CMD_RECRUIT
    assert action['sa'] == 'No SA'
    result, spent = _execute(state, action, 10)
    assert result['executed'] and result['errors'] == []
    assert spent == 4
    assert all(count_pieces(state, region, rc.ROMANS, rc.ALLY) == 1 for region in regions)
    assert check_structural_integrity(state) == []
    no_private_context(state)


def abandoned_candidate():
    from fs_bot.engine.recruit_planning import REQUESTS, CANDIDATE
    requests = [
        {'requesting_faction': rc.ROMANS, 'faction': rc.GERMANS, 'region': rc.PROVINCIA},
        {'requesting_faction': rc.ROMANS, 'faction': rc.AEDUI, 'region': rc.SEQUANI},
    ]
    candidate = {'command': rc.CMD_RECRUIT, 'sa': 'No SA', 'details': {'recruit_plan': [
        {'region': region, 'action': 'place_auxilia'} for region in (rc.PROVINCIA, rc.SEQUANI)]}}
    return {'command': 'Pass', 'sa': 'No SA', 'details': {REQUESTS: requests, CANDIDATE: candidate}}


def test_accepted_supply_binds_later_event_choice_after_other_refusal_discards_candidate():
    from fs_bot.commands.rally import supply_agreement_scope, has_supply_line
    state = position()
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.FORT)
    place_piece(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND, 3)
    calls = []
    def answer(board, faction, request):
        if request['kind'] == 'free_action':
            return {'use_default': True}
        calls.append(faction)
        return faction == rc.GERMANS and calls.count(rc.GERMANS) == 1
    state['decision_agent'] = answer
    with supply_agreement_scope(state):
        result = ex._resolve_free_command(state, rc.ROMANS,
            _planner=lambda _: deepcopy(abandoned_candidate()))
        assert result['declined_no_effect']
        assert calls == [rc.GERMANS, rc.AEDUI]
        assert has_supply_line(state, rc.PROVINCIA)
        assert calls == [rc.GERMANS, rc.AEDUI]  # Earlier yes still binds this Event.
    no_private_context(state)


def test_pending_confirmation_restores_preexisting_event_agreement_cache():
    from fs_bot.commands.rally import supply_agreement_scope
    from fs_bot.engine.recruit_planning import plan_with_recruit_supply
    state = position()
    calls = []
    def answer(board, faction, request):
        calls.append(faction)
        if faction == rc.GERMANS:
            return True
        raise EOFError('later Event Supply reply pending')
    state['decision_agent'] = answer
    with supply_agreement_scope(state):
        agreements = state['_supply_line_agreements']
        agreements[(rc.AEDUI, rc.ROMANS, rc.MANDUBII)] = True
        before = encode({key: value for key, value in state.items() if key != 'decision_agent'})
        with pytest.raises(EOFError, match='later Event Supply'):
            plan_with_recruit_supply(state, lambda _: deepcopy(abandoned_candidate()))
        assert calls == [rc.GERMANS, rc.AEDUI]
        assert state['_supply_line_agreements'] is agreements
        assert encode({key: value for key, value in state.items() if key != 'decision_agent'}) == before
    no_private_context(state)
