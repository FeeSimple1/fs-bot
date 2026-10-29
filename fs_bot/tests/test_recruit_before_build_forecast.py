"""§8.8.4 forecasts Recruit after its preceding Build, excluding SA pieces."""
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.bots.roman_bot import node_r_recruit
from fs_bot.commands.common import CommandError
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.recruit_planning import CONFIRMATIONS, plan_with_recruit_supply
from fs_bot.state.serialize import decode, encode
from fs_bot.state.state_schema import check_structural_integrity


CASES = ('ariovistus-15', 'the-gallic-war-15')


def captured_state(case):
    path = Path(__file__).parent / 'fixtures' / 'recruit_build_before' / (case + '.json.gz')
    with gzip.open(path, 'rt') as stream:
        fixture = json.load(stream)
    assert hashlib.sha256(json.dumps(fixture['state'], sort_keys=True).encode()).hexdigest() == (
        fixture['provenance']['state_sha256'])
    return decode(fixture['state'])


class LiveAgent:
    def __call__(self, *_):
        raise EOFError('A forecast must not request live input')

    def __deepcopy__(self, _):
        pytest.fail('A forecast must not copy the live agent')


def pure_plan(state):
    before = encode(state)
    agent = LiveAgent()
    state['decision_agent'] = agent
    try:
        action = node_r_recruit(state)
        assert state['decision_agent'] is agent
    finally:
        del state['decision_agent']
    assert encode(state) == before  # Includes resources, contexts and RNG.
    return action


def confirm_plan(state, *, human_consent):
    """Resolve the real policy after an input-free hypothetical forecast."""
    before = encode(state)
    requests = []

    def agree(board, faction, request):
        assert board is state and human_consent
        assert faction in (rc.BELGAE, rc.GERMANS)
        assert request['request_type'] == 'supply_line'
        requests.append(request)
        return True

    state['decision_agent'] = agree
    action = plan_with_recruit_supply(state, node_r_recruit)
    del state['decision_agent']
    assert encode({k: v for k, v in state.items() if k != CONFIRMATIONS}) == before
    assert bool(requests) is human_consent
    return action


@pytest.mark.parametrize('case', CASES)
@pytest.mark.parametrize('human_consent', [False, True])
def test_captured_seed15_build_creates_six_legal_recruit_placements(case, human_consent):
    """Six Recruit pieces are legal; refused Supply adds the printed cost."""
    state = captured_state(case)
    if human_consent:
        # Explicit legal-consent control; preserve the original all-NP
        # capture in the other case, without altering either fixture.
        state['non_player_factions'] -= {rc.BELGAE, rc.GERMANS}
    action = pure_plan(state)
    assert action['command'] == rc.CMD_RECRUIT
    assert action['sa'] == rc.SA_BUILD
    assert action['details']['potential_allies'] == 0  # Build's Ally is not Recruit.
    assert action['details']['potential_auxilia'] == 6
    action = confirm_plan(state, human_consent=human_consent)
    assert action['details']['potential_allies'] == 0
    assert action['details']['potential_auxilia'] == 6
    order = ([rc.ATREBATES, rc.PROVINCIA] if human_consent
             else [rc.PROVINCIA, rc.ATREBATES])
    assert action['details']['recruit_plan'] == [
        {'region': region, 'action': 'place_auxilia'} for region in order]
    before_auxilia = state['available'][rc.ROMANS][rc.AUXILIA]
    before_resources = state['resources'][rc.ROMANS]
    result = execute_decision(state, rc.ROMANS, {'bot_action': action})
    assert result['executed'] and result['errors'] == []
    assert result['sa_timing'] == 'before'
    assert result['sa_execution']['errors'] == []
    assert result['sa_execution']['actions'] == [
        ('fort', rc.ATREBATES), ('ally', rc.PROVINCIA, rc.TRIBE_HELVII)]
    assert state['available'][rc.ROMANS][rc.AUXILIA] == before_auxilia - 6
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 12
    # Atrebates already has a Roman Ally, so its Fort can be Built without
    # Supply (§4.2.1). NP Belgae still refuse its Supply Line (§8.4.2),
    # making Recruit there cost two (§3.2.1), in addition to four for Build.
    assert state['resources'][rc.ROMANS] == before_resources - (4 if human_consent else 6)
    assert check_structural_integrity(state) == []


@pytest.mark.parametrize('case', CASES)
def test_no_sa_grant_cannot_forecast_a_build(case, monkeypatch):
    state = captured_state(case)
    state['_command_with_sa'] = False
    monkeypatch.setattr('fs_bot.engine.execute._execute_sa',
                        lambda *_: pytest.fail('No-SA Recruit simulated an SA'))
    assert pure_plan(state)['command'] != rc.CMD_RECRUIT


@pytest.mark.parametrize('resources,allies,auxilia,build_actions', [
    (5, 1, 1, []),
    (6, 1, 2, [('fort', rc.ATREBATES)]),
    (7, 1, 2, [('fort', rc.ATREBATES)]),
    (8, 0, 6, [('fort', rc.ATREBATES), ('ally', rc.PROVINCIA, rc.TRIBE_HELVII)]),
    (10, 0, 6, [('fort', rc.ATREBATES), ('ally', rc.PROVINCIA, rc.TRIBE_HELVII)]),
])
@pytest.mark.parametrize('human_consent', [False, True])
def test_before_build_spending_stops_after_crossing_below_six(
        resources, allies, auxilia, build_actions, human_consent):
    state = captured_state(CASES[0])
    if human_consent:
        state['non_player_factions'] -= {rc.BELGAE, rc.GERMANS}
    state['resources'][rc.ROMANS] = resources
    ordinary = pure_plan(state)
    assert (ordinary['command'] == rc.CMD_RECRUIT) is (auxilia >= 6)
    # Force the Command to inspect legal sub-threshold plans too. This is
    # the existing Event-grant contract, without relaxing the ordinary gate.
    state['_planning_forced_command'] = rc.CMD_RECRUIT
    pure_plan(state)
    action = confirm_plan(state, human_consent=human_consent)
    assert action['details']['potential_allies'] == allies
    assert action['details']['potential_auxilia'] == auxilia
    plan = action['details']['recruit_plan']
    assert len({entry['region'] for entry in plan}) == len(plan)
    before = state['available'][rc.ROMANS][rc.AUXILIA]
    result = execute_decision(state, rc.ROMANS, {'bot_action': action})
    assert result['executed'] and result['errors'] == []
    assert result['sa_execution']['actions'] == build_actions
    assert result['sa_execution']['errors'] == []
    assert state['available'][rc.ROMANS][rc.AUXILIA] == before - auxilia
    # §8.8.1 permits the payment that crosses below six, then stops Build.
    # §3.2.1 still charges the later Recruit in an unsupplied Region.
    assert state['resources'][rc.ROMANS] == (
        resources - 2 * len(build_actions) - (0 if human_consent else 2))
    assert check_structural_integrity(state) == []


def test_free_build_and_recruit_do_not_spend_below_six():
    from fs_bot.commands.common import free_action_scope
    state = captured_state(CASES[0])
    state['resources'][rc.ROMANS] = 0
    with free_action_scope(state, rc.ROMANS):
        action = confirm_plan(state, human_consent=False)
        assert action['command'] == rc.CMD_RECRUIT
        assert action['details']['potential_auxilia'] == 6
        result = execute_decision(state, rc.ROMANS, {'bot_action': action})
    assert result['executed'] and result['errors'] == []
    assert result['sa_execution']['actions'] == [
        ('fort', rc.ATREBATES), ('ally', rc.PROVINCIA, rc.TRIBE_HELVII)]
    assert not result['sa_execution']['errors']
    assert state['resources'][rc.ROMANS] == 0
    assert check_structural_integrity(state) == []


def test_failed_fort_placement_does_not_invent_recruit_capacity(monkeypatch):
    state = captured_state(CASES[0])

    def refused(*_):
        raise CommandError('Test refusal: the proposed Fort was not placed')

    monkeypatch.setattr('fs_bot.engine.execute._sa_build_fort', refused)
    assert pure_plan(state)['command'] != rc.CMD_RECRUIT
    state['_planning_forced_command'] = rc.CMD_RECRUIT
    action = pure_plan(state)
    # The actual Build executor still places the Provincia Ally. Its piece
    # does not count as Recruit, and the absent Fort leaves only five Auxilia.
    assert action['details']['potential_allies'] == 0
    assert action['details']['potential_auxilia'] == 5


def test_before_build_cannot_count_more_auxilia_than_the_shared_pool():
    state = captured_state(CASES[0])
    state['_command_region_scope'] = {rc.ATREBATES, rc.PROVINCIA}
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA,
                state['available'][rc.ROMANS][rc.AUXILIA] - 5)
    assert pure_plan(state)['command'] != rc.CMD_RECRUIT
    state['_planning_forced_command'] = rc.CMD_RECRUIT
    action = pure_plan(state)
    assert action['details']['potential_allies'] == 0
    assert action['details']['potential_auxilia'] == 5
