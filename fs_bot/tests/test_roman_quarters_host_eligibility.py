"""§6.3.3/A6.3.3: a willing German cannot host Roman relocation."""
import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece
from fs_bot.bots.roman_bot import build_np_winter_relocations
from fs_bot.engine.quarters import validate_quarters_plan
from fs_bot.state.state_schema import build_initial_state


@pytest.mark.parametrize('scenario,host,allowed', [
    (rc.SCENARIO_GREAT_REVOLT, rc.GERMANS, False),
    (rc.SCENARIO_ARIOVISTUS, rc.GERMANS, False),
    (rc.SCENARIO_GALLIC_WAR, rc.GERMANS, False),
    (rc.SCENARIO_ARIOVISTUS, rc.ARVERNI, False),
    (rc.SCENARIO_GREAT_REVOLT, rc.AEDUI, True),
    (rc.SCENARIO_ARIOVISTUS, rc.AEDUI, True),
    (rc.SCENARIO_GREAT_REVOLT, rc.BELGAE, True),
    (rc.SCENARIO_ARIOVISTUS, rc.BELGAE, True),
])
def test_roman_planner_checks_host_eligibility_before_requesting_agreement(
        monkeypatch, scenario, host, allowed):
    st = build_initial_state(scenario, seed=7)
    st['resources'][rc.ROMANS] = 10
    place_piece(st, rc.MORINI, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(st, rc.ATREBATES, host, rc.WARBAND)
    calls = []
    def agree(state, faction, request):
        calls.append((faction, request['request_type']))
        return True
    st['decision_agent'] = agree
    # Isolate the adjacent-hop decision: only the candidate host has supply.
    supplied = lambda state, region, faction, **kwargs: region == rc.ATREBATES
    monkeypatch.setattr('fs_bot.commands.rally.has_supply_line', supplied)
    monkeypatch.setattr('fs_bot.engine.quarters.has_supply_line', supplied)
    plan = build_np_winter_relocations(st)
    assert calls == ([(host, 'quarters')] if allowed else [])
    assert plan[rc.ROMANS] == ([(rc.LEGION, rc.MORINI, rc.ATREBATES, 1),
                                (rc.LEGION, rc.ATREBATES, rc.PROVINCIA, 1)]
                               if allowed else [])
    assert validate_quarters_plan(st, plan, faction=rc.ROMANS) == []
    if not allowed:
        assert plan[rc.ROMANS + '_quartering'][rc.MORINI] == {'pay': 1}


