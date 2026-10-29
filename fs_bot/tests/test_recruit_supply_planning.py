"""§3.2.1/§8.8.4: agree Supply before forecasting committed Build/Recruit."""
import gzip
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from fs_bot import rules_consts as rc
from fs_bot.bots.roman_bot import node_r_recruit
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.board.pieces import place_piece, move_piece, count_pieces
from fs_bot.map.map_data import get_tribes_in_region
from fs_bot.engine.execute import execute_decision, _execute_build
from fs_bot.commands.rally import has_supply_line
from fs_bot.engine.recruit_planning import (
    ANSWERS, QUERIES, CONFIRMATIONS, CANDIDATE, plan_with_recruit_supply,
)
from fs_bot.state.serialize import decode, encode
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity
from fs_bot.state.setup import setup_scenario
from fs_bot.engine.victory import calculate_victory_score


def captured_state():
    path = Path(__file__).parent / 'fixtures/recruit_supply_before/gallic-war-9.json.gz'
    with gzip.open(path, 'rt') as stream:
        fixture = json.load(stream)
    assert hashlib.sha256(json.dumps(fixture['state'], sort_keys=True).encode()).hexdigest() == (
        fixture['provenance']['state_sha256'])
    return decode(fixture['state'])


def test_captured_card13_refusal_replans_before_build_or_recruit():
    state = captured_state()
    requests = []

    def agent(board, faction, request):
        if request.get('request_type') == 'supply_line':
            assert board is state  # A real declaration, not a speculative callback.
            requests.append((faction, request['context']['region']))
            if 'proposed_action' in request['context']:
                assert request['context']['proposed_action']['command'] == rc.CMD_RECRUIT
            return False
        return None

    state['decision_agent'] = agent
    before = encode({k: v for k, v in state.items() if k != 'decision_agent'})
    optimistic = node_r_recruit(state)
    assert optimistic['command'] == rc.CMD_RECRUIT
    assert optimistic['details']['potential_allies'] == 2
    assert requests == []
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before

    action = plan_with_recruit_supply(state, node_r_recruit)
    assert action['command'] == rc.CMD_SEIZE
    # Supply refusal changes the decision before a Fort, Ally, Scout or cost
    # is committed. Only the chosen plan's RNG/confirmation may change.
    for key in ('spaces', 'tribes', 'available', 'resources'):
        assert encode(state[key]) == before[key]
    assert requests and all(faction == rc.GERMANS for faction, _ in requests)
    assert len(requests) == len(set(requests))
    agreed_requests = list(requests)
    result = execute_decision(state, rc.ROMANS, {'bot_action': action})
    assert result['executed'] and result['command'] == rc.CMD_SEIZE
    assert result['errors'] == result['sa_execution']['errors'] == []
    # The canceled Recruit's refusals are not binding on its alternative
    # Seize Command; Build may ask anew under that action.
    assert requests[:len(agreed_requests)] == agreed_requests
    assert check_structural_integrity(state) == []
    for key in (ANSWERS, QUERIES, CONFIRMATIONS,
                '_supply_line_agreements', '_supply_line_query'):
        assert key not in state


def test_nonplayer_refusal_is_resolved_without_a_live_callback():
    state = captured_state()
    state['non_player_factions'].add(rc.GERMANS)
    state['decision_agent'] = lambda *_: pytest.fail('A non-player must use its agreement rule')
    action = plan_with_recruit_supply(state, node_r_recruit)
    assert action['command'] == rc.CMD_SEIZE
    assert CONFIRMATIONS not in state


def test_no_agent_nonplayer_supply_refusal_also_governs_build_after_march():
    state = captured_state()
    state['non_player_factions'].add(rc.GERMANS)
    before = encode(state)
    assert has_supply_line(state, rc.ATREBATES) is False
    result = _execute_build(state, rc.ROMANS, {
        'command': rc.CMD_MARCH, 'sa': rc.SA_BUILD, 'details': {}})
    assert not result['executed'] and result['actions'] == []
    assert result['errors'] == []
    assert encode(state) == before


def test_actual_roman_dispatch_confirms_the_captured_recruit_before_effects():
    state = captured_state()
    requests = []

    def agent(board, faction, request):
        if request.get('request_type') == 'supply_line':
            requests.append((faction, request['context']['region']))
            return False
        return None

    state['decision_agent'] = agent
    pieces = encode(state['spaces'])
    action = dispatch_bot_turn(state, rc.ROMANS)
    assert action['command'] == rc.CMD_SEIZE
    assert requests and encode(state['spaces']) == pieces
    assert execute_decision(state, rc.ROMANS, {'bot_action': action})['errors'] == []


def test_canceled_recruit_agreement_does_not_authorize_its_alternative_seize():
    state = captured_state()
    state['non_player_factions'].discard(rc.BELGAE)
    requests = []

    def agent(board, faction, request):
        if request.get('request_type') == 'supply_line' and faction == rc.BELGAE:
            return True
        if request.get('request_type') == 'supply_line' and faction == rc.GERMANS:
            context = request['context']
            for_recruit = 'proposed_action' in context
            requests.append((context['region'], for_recruit))
            return context['region'] == rc.SUGAMBRI and for_recruit
        return None

    state['decision_agent'] = agent
    action = plan_with_recruit_supply(state, node_r_recruit)
    assert action['command'] == rc.CMD_SEIZE
    assert (rc.SUGAMBRI, True) in requests
    assert CONFIRMATIONS not in state
    result = execute_decision(state, rc.ROMANS, {'bot_action': action})
    assert result['executed'] and not result['errors']
    # The human's earlier yes was to Recruit. Its replacement Seize/SA
    # consults again, and the new refusal is honored before any Build.
    assert (rc.SUGAMBRI, False) in requests
    assert result['sa_execution']['sa'] == rc.SA_SCOUT


@pytest.mark.parametrize('seed,accepted', [(1, True), (5, False)])
@pytest.mark.parametrize('explicit_plan', [False, True])
def test_actual_aedui_supply_die_is_not_decided_by_preview_or_repeated_build_passes(
        seed, accepted, explicit_plan, monkeypatch):
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=1)
    state['non_player_factions'] = {rc.AEDUI, rc.BELGAE, rc.ARVERNI}
    state['resources'][rc.ROMANS] = 10
    state['_command_region_scope'] = {rc.SEQUANI}
    place_piece(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND, 6)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA)
    move_piece(state, rc.PROVINCIA, rc.SEQUANI, rc.ROMANS, rc.LEADER)
    assert state['spaces'][rc.SEQUANI]['control'] == rc.AEDUI_CONTROL
    assert calculate_victory_score(state, rc.ROMANS) == 12
    assert check_structural_integrity(state) == []
    state['rng'].seed(seed)
    calls = []

    def roll(board):
        value = board['rng'].randint(1, 6)
        calls.append(value)
        return value

    monkeypatch.setattr('fs_bot.bots.bot_common.roll_die', roll)
    before = encode(state)
    preview = deepcopy(state)
    preview['_diviciacus_preview'] = True
    assert has_supply_line(preview, rc.SEQUANI)
    assert preview['rng'].getstate() == state['rng'].getstate()
    assert calls == [] and encode(state) == before

    details = {}
    if explicit_plan:
        details['build_plan'] = {
            'forts': [rc.SEQUANI],
            'allies': [{'region': rc.SEQUANI, 'tribe': rc.TRIBE_SEQUANI}],
        }
    result = _execute_build(state, rc.ROMANS, {
        'command': rc.CMD_MARCH, 'sa': rc.SA_BUILD, 'details': details})
    assert result['executed'] is accepted
    # In the explicit plan the Ally also needs Roman Control; accepting
    # Supply does not waive that separate requirement. A refused Fort
    # must not buy another agreement die when this second entry is checked.
    assert len(result['errors']) == (int(not accepted) + 1 if explicit_plan else 0)
    assert len(calls) == 1  # Fort/Subdue/Ally passes and execution share the result.
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.FORT) == int(accepted)
    assert check_structural_integrity(state) == []


def test_other_roman_commands_keep_their_existing_live_planner(monkeypatch):
    state = captured_state()
    chosen = {'command': rc.CMD_SEIZE, 'regions': [rc.PROVINCIA],
              'sa': 'No SA', 'details': {}}

    def planner(board):
        assert board is state
        return chosen

    monkeypatch.setattr('fs_bot.bots.roman_bot.execute_roman_turn', planner)
    monkeypatch.setattr('fs_bot.bots.roman_bot.node_r_recruit',
                        lambda *_: pytest.fail('Seize must not re-enter Recruit'))
    monkeypatch.setattr('fs_bot.engine.diviciacus_planning.plan_with_diviciacus',
                        lambda board, faction, callback: callback(board))
    assert dispatch_bot_turn(state, rc.ROMANS) is chosen


@pytest.mark.parametrize('via_dispatch', [False, True])
def test_rejected_optimistic_recruit_still_confirms_supply_that_can_enable_it(
        via_dispatch, monkeypatch):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=17)
    state['non_player_factions'] = {rc.ROMANS}
    state['resources'][rc.ROMANS] = 10
    regions = (rc.ATREBATES, rc.MORINI)
    state['_command_region_scope'] = set(regions)
    for region in regions:
        place_piece(state, region, rc.ROMANS, rc.FORT)
        # Only one Subdued Tribe per Region; hypothetical Build would
        # consume both Allies, leaving only five Recruit Auxilia.
        for tribe in get_tribes_in_region(region, state['scenario'])[1:]:
            state['tribes'][tribe]['status'] = rc.MARKER_DISPERSED
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    for region in state['spaces']:
        if region not in (*regions, rc.BRITANNIA):
            place_piece(state, region, rc.GERMANS, rc.WARBAND,
                        4 if region == rc.CISALPINA else 1)
    assert check_structural_integrity(state) == []
    optimistic = node_r_recruit(state)
    assert optimistic['command'] == rc.CMD_SEIZE
    candidate = optimistic['details'][CANDIDATE]
    assert candidate['details']['potential_allies'] == 0
    assert candidate['details']['potential_auxilia'] == 5
    requests = []

    def refuse(board, faction, request):
        if request.get('request_type') == 'supply_line':
            requests.append(request)
            assert request['context']['proposed_action']['command'] == rc.CMD_RECRUIT
            return False
        return None

    state['decision_agent'] = refuse
    if via_dispatch:
        # Reach the same published process through the real dispatch
        # boundary; it must not skip consent because the forecast is Seize.
        monkeypatch.setattr('fs_bot.bots.roman_bot.execute_roman_turn', node_r_recruit)
        action = dispatch_bot_turn(state, rc.ROMANS)
    else:
        action = plan_with_recruit_supply(state, node_r_recruit)
    assert requests and action['command'] == rc.CMD_RECRUIT
    assert action['details']['potential_allies'] == 2
    assert action['details']['potential_auxilia'] == 0
    assert CANDIDATE not in action['details']
    before = state['available'][rc.ROMANS][rc.ALLY]
    result = execute_decision(state, rc.ROMANS, {'bot_action': action})
    assert result['executed'] and result['errors'] == []
    assert state['available'][rc.ROMANS][rc.ALLY] == before - 2
    assert state['resources'][rc.ROMANS] == 6
    assert check_structural_integrity(state) == []


def test_interrupted_raw_confirmation_restores_rng_and_private_contexts():
    state = captured_state()
    before = encode(state)

    def interrupt(*_):
        raise EOFError('Supply decision paused')

    state['decision_agent'] = interrupt
    with pytest.raises(EOFError):
        plan_with_recruit_supply(state, node_r_recruit)
    assert state['decision_agent'] is interrupt
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before


@pytest.mark.parametrize('response', [1, 1.0, 'yes', {}, {'use_default': 1}])
def test_malformed_raw_supply_reply_does_not_become_permission(response):
    state = captured_state()
    before = encode(state)
    state['decision_agent'] = lambda *_: response
    with pytest.raises(ValueError, match='true or false'):
        plan_with_recruit_supply(state, node_r_recruit)
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before
