"""A Card Reference A20/A58; §§3.2.3–4, 5.1.3, 8.2.3, 8.8.5."""
import io
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.cards.roman_event_grants import (
    SEIZE_GRANT, accept_request, command_request, default_seize_plan, resolve,
)
from fs_bot.cli.free_actions import collect_free_action
from fs_bot.cli.menus import set_board_hook
from fs_bot.engine.execute import _execute_event, _execute_seize
from fs_bot.engine.free_actions import execute_free_action_plan, validate_free_action_response
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import board_copy


def state(card='A20', scenario=rc.SCENARIO_ARIOVISTUS):
    st = build_initial_state(scenario, seed=7)
    st['current_card'] = st['current_card_id'] = card
    st['non_player_factions'] = {rc.BELGAE, rc.AEDUI, rc.GERMANS, rc.ARVERNI}
    return st


def event(st, card, executor=rc.ROMANS):
    return _execute_event(st, executor, {'command': 'Event', 'details': {
        'card_id': card, 'text_preference': rc.EVENT_UNSHADED}}, human=True)


def seize(regions, tribes=None):
    return {'command': rc.CMD_SEIZE, 'regions': regions, 'sa': 'No SA',
            'sa_regions': [], 'details': {'disperse_tribes': tribes or {r: [] for r in regions}}}


def battle(region, target=rc.BELGAE):
    return {'command': rc.CMD_BATTLE, 'regions': [region], 'sa': 'No SA',
            'sa_regions': [], 'details': {'battle_plan': [{'region': region, 'target': target}]}}


@pytest.mark.parametrize('scenario', rc.ARIOVISTUS_SCENARIOS)
@pytest.mark.parametrize('executor', [rc.ROMANS, rc.AEDUI, rc.BELGAE, rc.GERMANS])
def test_morbihan_roman_decline_precedes_all_removals(scenario, executor):
    st = state(scenario=scenario)
    place_piece(st, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        place_piece(st, rc.VENETI, rc.ARVERNI, rc.WARBAND, piece_state=visibility)
    requests = []
    def agent(board, faction, request):
        requests.append((faction, request))
        assert count_pieces(board, rc.VENETI, rc.ARVERNI) == 3
        return {'decline': True}
    st['decision_agent'] = agent
    rng = st['rng'].getstate()
    result = event(st, 'A20', executor)
    assert result['executed'] and len(requests) == 1
    assert requests[0][0] == rc.ROMANS and requests[0][1]['request_type'] == 'roman_event_accept'
    assert count_pieces(st, rc.VENETI, rc.ARVERNI) == 3
    assert st['rng'].getstate() == rng


def test_morbihan_no_nearby_romans_has_no_benefit_request():
    st = state()
    place_piece(st, rc.VENETI, rc.ARVERNI, rc.WARBAND)
    st['decision_agent'] = lambda *_: pytest.fail('ineligible Morbihan grant')
    event(st, 'A20', rc.GERMANS)
    assert count_pieces(st, rc.VENETI, rc.ARVERNI) == 1


def test_morbihan_removes_all_physical_arverni_then_requests_seize(monkeypatch):
    st = state()
    place_piece(st, rc.VENETI, rc.ROMANS, rc.AUXILIA)
    place_piece(st, rc.VENETI, rc.ARVERNI, rc.ALLY)
    st['tribes'][rc.TRIBE_VENETI]['allied_faction'] = rc.ARVERNI
    for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        place_piece(st, rc.VENETI, rc.ARVERNI, rc.WARBAND, piece_state=visibility)
    # Opposing Revealed Warbands deny actual Roman Control, with no Harassment.
    place_piece(st, rc.VENETI, rc.BELGAE, rc.WARBAND, 4, piece_state=rc.REVEALED)
    seen = []
    def agent(board, faction, request):
        if request['kind'] != 'free_action':
            return None
        seen.append(request)
        assert faction == rc.ROMANS
        if request['request_type'] == 'roman_event_accept':
            assert count_pieces(board, rc.VENETI, rc.ARVERNI) == 4
            return {'accept': True}
        assert count_pieces(board, rc.VENETI, rc.ARVERNI) == 0
        return seize([rc.VENETI], {rc.VENETI: [rc.TRIBE_VENETI]})
    st['decision_agent'] = agent
    monkeypatch.setattr('fs_bot.commands.seize.seize_rally_roll', lambda *_: pytest.fail('A20 forbids Rally rolls'))
    before_rng = st['rng'].getstate()
    result = event(st, 'A20', rc.GERMANS)
    assert result['executed'] and len(seen) == 2
    assert st['tribes'][rc.TRIBE_VENETI]['status'] == rc.DISPERSED
    assert st['rng'].getstate() == before_rng and validate_state(st) == []
    assert SEIZE_GRANT not in st


def test_morbihan_keeps_harassment_and_np_safety_but_human_may_seize():
    st = state()
    place_piece(st, rc.VENETI, rc.ROMANS, rc.AUXILIA)
    place_piece(st, rc.VENETI, rc.GERMANS, rc.WARBAND, 3)
    req = command_request(st, 'A20', rc.CMD_SEIZE)
    assert default_seize_plan(st, req) is None
    assert validate_free_action_response(st, rc.ROMANS, req, {'use_default': True})
    plan = seize([rc.VENETI], {rc.VENETI: [rc.TRIBE_VENETI]})
    assert validate_free_action_response(st, rc.ROMANS, req, plan) is None
    result = execute_free_action_plan(st, rc.ROMANS, req, plan)
    assert result['executed'] and count_pieces(st, rc.VENETI, rc.ROMANS) == 0
    assert 'harassment' in result['regions'][0]


@pytest.mark.parametrize('executor', [rc.AEDUI, rc.BELGAE, rc.GERMANS])
def test_aduatuci_battle_then_seize_are_roman_choices_on_updated_board(executor):
    st = state('A58')
    for r in (rc.NERVII, rc.MORINI):
        place_piece(st, r, rc.ROMANS, rc.LEGION, 3, from_legions_track=True)
        place_piece(st, r, rc.BELGAE, rc.WARBAND)
    seen = []
    def agent(board, faction, req):
        if req['kind'] != 'free_action':
            return None
        assert faction == rc.ROMANS
        seen.append(req['request_type'])
        if req['request_type'] == 'roman_event_accept':
            return {'accept': True}
        if req['request_type'] == 'roman_event_battle':
            plan = battle(rc.NERVII)
            plan['regions'].append(rc.MORINI)
            plan['details']['battle_plan'].append({'region': rc.MORINI, 'target': rc.BELGAE})
            return plan
        assert all(count_pieces(board, r, rc.BELGAE) == 0 for r in (rc.NERVII, rc.MORINI))
        return seize([rc.NERVII], {rc.NERVII: [rc.TRIBE_NERVII]})
    st['decision_agent'] = agent
    before = st['resources'][rc.ROMANS]
    outcome = event(st, 'A58', executor)
    assert outcome['executed'] and seen == ['roman_event_accept', 'roman_event_battle', 'roman_event_seize']
    assert st['resources'][rc.ROMANS] == before + 8  # +6 Nervii, +2 Subdued Eburones
    assert st['tribes'][rc.TRIBE_NERVII]['status'] == rc.DISPERSED
    assert st['tribes'][rc.TRIBE_MORINI]['status'] is None
    assert validate_state(st) == []


def test_aduatuci_suppresses_harassment_and_all_rally_rolls_in_preview_and_live(monkeypatch):
    st = state('A58')
    place_piece(st, rc.NERVII, rc.ROMANS, rc.AUXILIA)
    place_piece(st, rc.NERVII, rc.GERMANS, rc.WARBAND, 3)
    request = command_request(st, 'A58', rc.CMD_SEIZE)
    plan = seize([rc.NERVII], {rc.NERVII: [rc.TRIBE_NERVII]})
    monkeypatch.setattr('fs_bot.commands.seize.seize_rally_roll', lambda *_: pytest.fail('A58 forbids Rally'))
    monkeypatch.setattr('fs_bot.engine.execute._resolve_seize_harassment', lambda *_: pytest.fail('A58 forbids Harassment'))
    st['decision_agent'] = lambda *_: pytest.fail('preview consumed live agent')
    before, rng = encode(board_copy(st)), st['rng'].getstate()
    assert validate_free_action_response(st, rc.ROMANS, request, plan) is None
    assert encode(board_copy(st)) == before
    execute_free_action_plan(st, rc.ROMANS, request, plan)
    assert count_pieces(st, rc.NERVII, rc.ROMANS, rc.AUXILIA) == 1
    assert st['rng'].getstate() == rng and SEIZE_GRANT not in st


@pytest.mark.parametrize('response', [None, {}, {'accept': 1}, {'accept': True, 'decline': True}, {'use_default': 1}])
def test_acceptance_is_explicit(response):
    assert validate_free_action_response(state(), rc.ROMANS, accept_request('A20'), response)


@pytest.mark.parametrize('bad', [
    {'decline': True},
    seize([rc.PROVINCIA]),
    seize([rc.NERVII, rc.NERVII]),
    seize([rc.NERVII], {rc.NERVII: [rc.TRIBE_NERVII, rc.TRIBE_NERVII]}),
    seize([rc.NERVII], {rc.NERVII: [rc.TRIBE_MORINI]}),
    {'command': rc.CMD_SEIZE, 'regions': [rc.NERVII], 'details': {'as_if_control': True}},
])
def test_invalid_seize_plan_never_mutates_board_or_rng(bad):
    st = state('A58')
    place_piece(st, rc.NERVII, rc.ROMANS, rc.AUXILIA)
    request = command_request(st, 'A58', rc.CMD_SEIZE)
    before = encode(st)
    assert validate_free_action_response(st, rc.ROMANS, request, bad)
    assert encode(st) == before


def test_ordinary_seize_ignores_client_exception_flags_and_still_rolls(monkeypatch):
    st = state()
    place_piece(st, rc.VENETI, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(st, rc.VENETI, rc.GERMANS, rc.WARBAND, 3)
    calls = []
    def roll(board, faction):
        calls.append(faction)
        return {'faction': faction, 'roll': 6, 'can_rally': False}
    monkeypatch.setattr('fs_bot.commands.seize.seize_rally_roll', roll)
    result = _execute_seize(st, rc.ROMANS, {'command': rc.CMD_SEIZE,
        'regions': [rc.VENETI], 'details': {'disperse_regions': [rc.VENETI],
         'no_rally': True, 'no_harassment': True, 'as_if_control': True}})
    assert calls == [rc.ARVERNI, rc.BELGAE] * len(result['regions'][0]['tribes_dispersed'])
    assert 'harassment' in result['regions'][0]
    assert count_pieces(st, rc.VENETI, rc.ROMANS, rc.AUXILIA) == 3


def test_static_roman_forces_can_choose_battle_but_default_must_be_effective():
    st = state('A58')
    place_piece(st, rc.NERVII, rc.ROMANS, rc.FORT)
    place_piece(st, rc.NERVII, rc.BELGAE, rc.WARBAND)
    req = command_request(st, 'A58', rc.CMD_BATTLE)
    assert rc.NERVII in req['allowed_regions']
    assert validate_free_action_response(st, rc.ROMANS, req, battle(rc.NERVII)) is None
    assert validate_free_action_response(st, rc.ROMANS, req, {'use_default': True})
    output = io.StringIO()
    action = collect_free_action(st, rc.ROMANS, req, io.StringIO('2\n1\n1\n1\n'), output)
    assert action == battle(rc.NERVII)
    assert 'supply a legal plan' in output.getvalue()


def test_cli_acceptance_board_inspection_eof_and_exact_seize_choices():
    st = state()
    place_piece(st, rc.VENETI, rc.ROMANS, rc.AUXILIA)
    before, inspections = encode(st), []
    set_board_hook(lambda: inspections.append(encode(st)))
    try:
        with pytest.raises(EOFError):
            collect_free_action(st, rc.ROMANS, accept_request('A20'), io.StringIO('board\n'), io.StringIO())
    finally:
        set_board_hook(None)
    assert inspections == [before] and encode(st) == before
    req = command_request(st, 'A20', rc.CMD_SEIZE)
    plan = collect_free_action(st, rc.ROMANS, req, io.StringIO('1\n1\n1\n2\n'), io.StringIO())
    assert plan == seize([rc.VENETI], {rc.VENETI: [rc.TRIBE_VENETI]})
    assert encode(st) == before


def test_raw_missing_callback_defers_but_invalid_later_response_rolls_back():
    st = state()
    place_piece(st, rc.VENETI, rc.ROMANS, rc.AUXILIA)
    place_piece(st, rc.VENETI, rc.ARVERNI, rc.WARBAND)
    st['decision_agent'] = lambda board, faction, req: (
        {'accept': True} if req['request_type'] == 'roman_event_accept' else {'decline': True})
    before = encode(board_copy(st))
    with pytest.raises(ValueError):
        resolve(st, 'A20')
    assert encode(board_copy(st)) == before
    st['decision_agent'] = lambda *_: None
    assert resolve(st, 'A20')[-1]['result']['executed']
    assert count_pieces(st, rc.VENETI, rc.ARVERNI) == 0


def test_aduatuci_refused_optional_loan_reopens_mandatory_battle_before_seize():
    st = state('A58')
    st['non_player_factions'].discard(rc.AEDUI)
    place_piece(st, rc.NERVII, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(st, rc.NERVII, rc.AEDUI, rc.WARBAND)
    place_piece(st, rc.NERVII, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    place_piece(st, rc.NERVII, rc.BELGAE, rc.WARBAND)
    requests = []
    def agent(board, faction, req):
        if req['kind'] == 'agreement' and req['request_type'] == 'diviciacus':
            assert faction == rc.AEDUI
            return False
        if req['kind'] != 'free_action':
            return None
        requests.append(req['request_type'])
        if req['request_type'] == 'roman_event_accept':
            return {'accept': True}
        if req['request_type'] == 'roman_event_battle':
            action = battle(rc.NERVII)
            if req.get('attempt', 1) == 1:
                action['details']['diviciacus_regions'] = [rc.NERVII]
            else:
                assert req['previous_error'] == 'Diviciacus agreement was refused; choose a new plan'
                assert count_pieces(board, rc.NERVII, rc.BELGAE) == 1
            return action
        assert count_pieces(board, rc.NERVII, rc.BELGAE) == 0
        return seize([rc.NERVII])
    st['decision_agent'] = agent
    result = event(st, 'A58')
    assert result['executed'] and requests == [
        'roman_event_accept', 'roman_event_battle', 'roman_event_battle', 'roman_event_seize']
    assert count_pieces(st, rc.NERVII, rc.AEDUI, rc.WARBAND) == 1


def test_unrelated_free_grants_do_not_materialize_roman_seize_frame():
    from fs_bot.cards.roman_event_grants import seize_scope
    st = state()
    with seize_scope(st, {'request_type': 'event_command'}):
        assert SEIZE_GRANT not in st
    outer = {'request_type': 'roman_event_seize', 'allowed_regions': [rc.VENETI]}
    with seize_scope(st, outer):
        with seize_scope(st, {'request_type': 'event_command'}):
            assert SEIZE_GRANT not in st
        assert st[SEIZE_GRANT] is outer
    assert SEIZE_GRANT not in st


def test_cli_battle_keeps_optional_diviciacus_selection_without_live_consent():
    st = state('A58')
    st['non_player_factions'].discard(rc.AEDUI)
    place_piece(st, rc.NERVII, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(st, rc.NERVII, rc.AEDUI, rc.WARBAND, 2)
    place_piece(st, rc.NERVII, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    place_piece(st, rc.NERVII, rc.BELGAE, rc.WARBAND)
    st['decision_agent'] = lambda *_: pytest.fail('planning consumed live consent')
    req = command_request(st, 'A58', rc.CMD_BATTLE)
    before = encode(board_copy(st))
    output = io.StringIO()
    # Plan; request cooperation; choose Nervii; Battle Nervii; target Belgae.
    action = collect_free_action(st, rc.ROMANS, req, io.StringIO('1\ny\n1\n1\n2\n'), output)
    assert action['details']['diviciacus_regions'] == [rc.NERVII]
    assert action['details']['battle_plan'] == [{'region': rc.NERVII, 'target': rc.BELGAE}]
    assert encode(board_copy(st)) == before
    assert 'Request Diviciacus cooperation' in output.getvalue()


def test_exact_seize_can_choose_any_tribe_when_only_one_marker_remains():
    st = state()
    place_piece(st, rc.VENETI, rc.ROMANS, rc.FORT)
    for tribe in (rc.TRIBE_NERVII, rc.TRIBE_MORINI, rc.TRIBE_SEQUANI):
        st['tribes'][tribe]['status'] = rc.DISPERSED
    request = command_request(st, 'A20', rc.CMD_SEIZE)
    choices = request['dispersible_tribes'][rc.VENETI]
    assert len(choices) > 1 and request['available_markers'] == 1
    action = seize([rc.VENETI], {rc.VENETI: [choices[-1]]})
    assert validate_free_action_response(st, rc.ROMANS, request, action) is None
    execute_free_action_plan(st, rc.ROMANS, request, action)
    assert st['tribes'][choices[-1]]['status'] == rc.DISPERSED
    assert st['tribes'][choices[0]]['status'] is None


def test_ordinary_seize_cannot_claim_roman_control_from_response_details():
    st = state()
    place_piece(st, rc.VENETI, rc.ROMANS, rc.AUXILIA)
    place_piece(st, rc.VENETI, rc.GERMANS, rc.WARBAND, 2)
    result = _execute_seize(st, rc.ROMANS, {'command': rc.CMD_SEIZE,
        'regions': [rc.VENETI], 'details': {'disperse_regions': [rc.VENETI], 'as_if_control': True}})
    assert result['executed'] and result['tribes_dispersed_total'] == 0


def test_aduatuci_battle_cannot_hide_out_of_scope_top_level_behind_command_parts():
    st = state('A58')
    for region in (rc.NERVII, rc.SEQUANI):
        place_piece(st, region, rc.ROMANS, rc.AUXILIA, 4)
        place_piece(st, region, rc.BELGAE, rc.WARBAND)
    request = command_request(st, 'A58', rc.CMD_BATTLE)
    action = battle(rc.SEQUANI)
    action['details']['command_parts'] = [battle(rc.NERVII)]
    before = encode(st)
    assert validate_free_action_response(st, rc.ROMANS, request, action)
    assert encode(st) == before


@pytest.mark.parametrize('explicit_default', [True, False])
def test_aduatuci_default_live_loan_refusal_distinguishes_explicit_from_raw_fallback(explicit_default):
    st = state('A58')
    st['non_player_factions'].discard(rc.AEDUI)
    place_piece(st, rc.NERVII, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(st, rc.NERVII, rc.ROMANS, rc.AUXILIA)
    place_piece(st, rc.NERVII, rc.AEDUI, rc.WARBAND, 6)
    place_piece(st, rc.NERVII, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    place_piece(st, rc.NERVII, rc.BELGAE, rc.WARBAND, 4)
    stages, refused = [], []
    def agent(board, faction, request):
        if request['kind'] == 'agreement' and request['request_type'] == 'diviciacus':
            refused.append(faction)
            return False
        if request['kind'] != 'free_action':
            return None
        stages.append(request['request_type'])
        if request['request_type'] == 'roman_event_accept':
            return {'accept': True}
        if request['request_type'] == 'roman_event_battle':
            if request.get('attempt', 1) == 1:
                return {'use_default': True} if explicit_default else None
            assert 'refused' in request['previous_error']
            return battle(rc.NERVII)
        return seize([rc.NERVII])
    st['decision_agent'] = agent
    result = event(st, 'A58')
    assert result['executed'] and refused == [rc.AEDUI]
    assert stages.count('roman_event_battle') == (2 if explicit_default else 1)
    assert bool(result['free_actions'][0]['result']['executed']) == explicit_default


@pytest.mark.parametrize('scenario', rc.ARIOVISTUS_SCENARIOS)
@pytest.mark.parametrize('remaining_battle', [False, True])
def test_aduatuci_default_retry_refreshes_targets_after_live_battle_window(scenario, remaining_battle):
    """§5.1.3: a legal outer-executor removal can end the required Battle."""
    from fs_bot.engine.action_windows import scope
    st = state('A58', scenario)
    st['non_player_factions'].discard(rc.BELGAE)
    place_piece(st, rc.NERVII, rc.ROMANS, rc.LEGION, 3, from_legions_track=True)
    place_piece(st, rc.NERVII, rc.BELGAE, rc.WARBAND)
    if remaining_battle:
        # A legal human Battle remains, but not one Roman NP priorities use.
        place_piece(st, rc.MORINI, rc.ROMANS, rc.FORT)
        place_piece(st, rc.MORINI, rc.GERMANS, rc.WARBAND)
    battles, removed_at = [], []
    def agent(board, faction, request):
        if request['kind'] == 'voluntary_removal':
            if (request['window']['stage'] == 'battle_command'
                    and count_pieces(board, rc.NERVII, rc.BELGAE, rc.WARBAND)):
                assert faction == rc.BELGAE
                removed_at.append(request['window']['stage'])
                return {'operations': [{'action': 'remove', 'region': rc.NERVII,
                    'piece_type': rc.WARBAND, 'piece_state': rc.HIDDEN, 'count': 1}]}
            return {'done': True}
        if request['kind'] != 'free_action':
            return None
        if request['request_type'] == 'roman_event_accept':
            return {'accept': True}
        if request['request_type'] == 'roman_event_battle':
            battles.append(deepcopy(request))
            if len(battles) == 1:
                return {'use_default': True}
            # Returning raw None in the failing old path prevents a test hang;
            # the assertions below diagnose the stale request directly.
            if not remaining_battle or request['allowed_regions'] != [rc.MORINI]:
                return None
            return battle(rc.MORINI, rc.GERMANS)
        return seize([rc.NERVII])
    agent.supports_action_windows = True
    st['decision_agent'] = agent
    with scope(st, actor=rc.BELGAE, force=True):
        result = event(st, 'A58', rc.BELGAE)
    assert result['executed'] and removed_at == ['battle_command']
    assert count_pieces(st, rc.NERVII, rc.BELGAE) == 0
    assert len(battles) == (2 if remaining_battle else 1)
    if remaining_battle:
        assert battles[1]['allowed_regions'] == [rc.MORINI]
        assert battles[1]['battle_targets'] == {rc.MORINI: [rc.GERMANS]}
        assert battles[1]['attempt'] == 2 and battles[1]['previous_error']
        assert result['free_actions'][0]['result']['executed']
    else:
        assert result['free_actions'][0]['result']['reason'] == 'No legal Battle Region.'
    assert result['free_actions'][-1]['result']['executed']
    assert validate_state(st) == []
