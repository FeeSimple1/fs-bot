"""Cards 63/A63 grant two paid actions with explicit human control."""
import io

import pytest

import fs_bot.rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces
from fs_bot.board.control import refresh_all_control
from fs_bot.state.state_schema import build_initial_state
from fs_bot.cards.card_effects import execute_card_A63
from fs_bot.cards.capabilities import get_capability_owner, is_capability_active
from fs_bot.engine.winter_campaign import resolve_winter_campaign, validate_plan, winter_campaign_after_harvest


def _state(faction=rc.ARVERNI, scenario=rc.SCENARIO_GREAT_REVOLT):
    st = build_initial_state(scenario, seed=4)
    st["resources"][faction] = 10
    return st


def _march(origin, destination):
    return {"command": "March", "sa": "No SA", "regions": [],
            "details": {"origins": [origin], "destinations": [destination],
                        "routes": {origin: [destination]}}}


def test_two_human_marches_pay_twice_and_second_sees_first_result():
    st = _state()
    place_piece(st, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 4)
    refresh_all_control(st)
    requests = []
    def agent(board, faction, request):
        assert request["kind"] == "winter_campaign"
        requests.append(request)
        if len(requests) == 1:
            return _march(rc.CARNUTES, rc.MANDUBII)
        assert count_pieces(board, rc.MANDUBII, faction, rc.WARBAND) == 4
        assert board["resources"][faction] == 9
        return _march(rc.MANDUBII, rc.CARNUTES)
    st["decision_agent"] = agent
    result = resolve_winter_campaign(st, rc.ARVERNI, 63)
    assert [r["remaining_actions"] for r in requests] == [2, 1]
    assert st["resources"][rc.ARVERNI] == 8
    assert count_pieces(st, rc.CARNUTES, rc.ARVERNI, rc.WARBAND) == 4
    assert result["remaining_actions"] == 0
    assert all(e["result"]["executed"] for e in result["actions"])


def test_np_march_also_pays_normal_cost(monkeypatch):
    st = _state()
    st["non_player_factions"] = {rc.ARVERNI}
    place_piece(st, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 4)
    refresh_all_control(st)
    plans = iter([_march(rc.CARNUTES, rc.MANDUBII), {"command": "Pass"}])
    monkeypatch.setattr("fs_bot.bots.bot_dispatch.dispatch_bot_turn",
                        lambda board, faction: next(plans))
    resolve_winter_campaign(st, rc.ARVERNI, 63)
    assert st["resources"][rc.ARVERNI] == 9


@pytest.mark.parametrize("scenario,faction", [
    (rc.SCENARIO_GREAT_REVOLT, rc.ARVERNI),
    (rc.SCENARIO_GREAT_REVOLT, rc.BELGAE),
    (rc.SCENARIO_ARIOVISTUS, rc.AEDUI),
    (rc.SCENARIO_ARIOVISTUS, rc.GERMANS),
])
def test_human_may_delegate_campaign_without_changing_seat(scenario, faction):
    from fs_bot.state.setup import setup_scenario
    st = setup_scenario(scenario, seed=2)
    st["non_player_factions"] = {rc.ROMANS, rc.AEDUI, rc.BELGAE} - {faction}
    seats = set(st["non_player_factions"])
    st["decision_agent"] = lambda *_: None
    result = resolve_winter_campaign(st, faction, 63)
    assert result["owner"] == faction
    assert st["non_player_factions"] == seats


def test_winter_campaign_does_not_swallow_interrupted_choice():
    st = _state()
    def stop(*args):
        raise EOFError("player paused")
    st["decision_agent"] = stop
    with pytest.raises(EOFError):
        resolve_winter_campaign(st, rc.ARVERNI, 63)


def test_a63_records_nonroman_executing_owner_and_fires(monkeypatch):
    st = _state(rc.GERMANS, rc.SCENARIO_ARIOVISTUS)
    st["executing_faction"] = rc.GERMANS
    execute_card_A63(st, shaded=True)
    assert get_capability_owner(st, "A63") == rc.GERMANS
    requests = []
    def agent(board, faction, request):
        requests.append((faction, request))
        return {"decline": True}
    st["decision_agent"] = agent
    result = winter_campaign_after_harvest(st)
    assert result["owner"] == rc.GERMANS
    assert requests[0][1]["card_id"] == "A63"


def test_roman_cannot_take_a63_shaded():
    st = _state(rc.ROMANS, rc.SCENARIO_ARIOVISTUS)
    st["executing_faction"] = rc.ROMANS
    execute_card_A63(st, shaded=True)
    assert not is_capability_active(st, "A63")


def test_card_exception_allows_standalone_sa_and_otherwise_incompatible_pair():
    st = _state(rc.AEDUI)
    assert validate_plan(st, rc.AEDUI, {"sa": "Suborn"}) == 1
    assert validate_plan(st, rc.AEDUI, {"command": "Battle", "sa": "Suborn"}) == 2
    with pytest.raises(ValueError, match="pair with Battle"):
        validate_plan(st, rc.AEDUI, {"sa": "Ambush"})
    with pytest.raises(ValueError, match="remaining"):
        validate_plan(st, rc.AEDUI, {"command": "Battle", "sa": "Ambush"}, 1)


def test_cli_can_explicitly_decline_campaign():
    from fs_bot.cli.reactive import make_cli_reactive
    out = io.StringIO()
    st = _state()
    agent = make_cli_reactive([rc.ARVERNI], io.StringIO("Finish Winter Campaign\n"), out)
    assert agent(st, rc.ARVERNI, {"kind": "winter_campaign", "remaining_actions": 2}) == {"decline": True}
    assert "pay costs" in out.getvalue()


def test_unaffordable_human_campaign_plan_retries_without_spending_action_budget():
    from fs_bot.state.serialize import encode
    st = _state(rc.AEDUI)
    st['resources'][rc.AEDUI] = 0
    place_piece(st, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 3)
    before = encode(st)
    requests = []
    def agent(board, faction, request):
        requests.append(request)
        if len(requests) == 1:
            return _march(rc.CARNUTES, rc.MANDUBII)
        assert encode({k: v for k, v in board.items() if k != 'decision_agent'}) == before
        assert request['remaining_actions'] == 2
        assert request['errors']
        return {'decline': True}
    st['decision_agent'] = agent
    result = resolve_winter_campaign(st, rc.AEDUI, 63)
    assert result['remaining_actions'] == 2
    assert result['actions'] == []


def test_partial_invalid_campaign_is_rejected_without_mutation_or_reactive_input():
    from fs_bot.engine.winter_campaign import validate_human_plan
    from fs_bot.state.serialize import encode
    st = _state(rc.AEDUI)
    place_piece(st, rc.MORINI, rc.AEDUI, rc.WARBAND, 3)
    st['decision_agent'] = lambda *_: pytest.fail('validation must not consume human input')
    before = encode({k: v for k, v in st.items() if k != 'decision_agent'})
    plan = {'command': 'Raid', 'sa': 'No SA', 'details': {
        'raid_plan': [{'region': rc.MORINI}, {'region': rc.MANDUBII}]}}
    with pytest.raises(ValueError, match='Invalid Winter Campaign'):
        validate_human_plan(st, rc.AEDUI, plan)
    assert encode({k: v for k, v in st.items() if k != 'decision_agent'}) == before


def test_campaign_battle_validation_does_not_roll_live_rng_or_ask_defender():
    from copy import deepcopy
    from fs_bot.engine.winter_campaign import validate_human_plan, _execute_plan
    from fs_bot.state.serialize import encode
    st = _state(rc.BELGAE)
    place_piece(st, rc.MORINI, rc.BELGAE, rc.WARBAND, 8)
    place_piece(st, rc.MORINI, rc.ROMANS, rc.LEGION, 2, from_legions_track=True)
    refresh_all_control(st)
    plan = {'command': 'Battle', 'sa': 'No SA', 'details': {
        'battle_plan': [{'region': rc.MORINI, 'target': rc.ROMANS}]}}
    # Verify the fixture actually exercises hard-piece dice.
    comparison = deepcopy(st)
    _execute_plan(comparison, rc.BELGAE, plan)
    assert comparison['rng'].getstate() != st['rng'].getstate()
    before = encode(st)
    st['decision_agent'] = lambda *_: pytest.fail('preview asked the live defender')
    assert validate_human_plan(st, rc.BELGAE, plan) == 1
    assert encode({k: v for k, v in st.items() if k != 'decision_agent'}) == before


def test_cli_campaign_rejects_unaffordable_march_then_allows_decline():
    from fs_bot.cli.winter_campaign import collect_winter_campaign
    st = _state(rc.AEDUI)
    st['resources'][rc.AEDUI] = 0
    place_piece(st, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 3)
    out = io.StringIO()
    result = collect_winter_campaign(st, rc.AEDUI, {'remaining_actions': 2},
        io.StringIO('\n'.join(['Command: March', rc.CARNUTES, rc.MANDUBII,
                              'all 3', 'Finish Winter Campaign']) + '\n'), out)
    assert result == {'decline': True}
    assert 'Cannot use this plan:' in out.getvalue()
    assert count_pieces(st, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 3
    assert st['resources'][rc.AEDUI] == 0


@pytest.mark.parametrize('remaining', [1, 2])
def test_np_last_campaign_command_does_not_depend_on_ungranted_settle(remaining):
    from fs_bot.engine.winter_campaign import _bot_plan, _execute_plan
    state = _state(rc.GERMANS, rc.SCENARIO_ARIOVISTUS)
    state['non_player_factions'] = {rc.GERMANS}
    # Override an ambient grant's opposite allowance at the new budget.
    state['_command_with_sa'] = remaining == 1
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.LEADER,
                leader_name=rc.ARIOVISTUS_LEADER)
    place_piece(state, rc.MORINI, rc.GERMANS, rc.WARBAND, 5)
    # German Control permits Settle, but no German Ally permits Rally here.
    for tribe in (rc.TRIBE_MENAPII, rc.TRIBE_MORINI):
        place_piece(state, rc.MORINI, rc.BELGAE, rc.ALLY)
        state['tribes'][tribe]['allied_faction'] = rc.BELGAE
    plan = _bot_plan(state, rc.GERMANS, remaining)
    assert plan['command'] == rc.CMD_RALLY
    assert validate_plan(state, rc.GERMANS, plan, remaining) == remaining
    assert bool(plan['details']['rally_plan']['settlements_before']) is (remaining == 2)
    result = _execute_plan(state, rc.GERMANS, plan, uses_bot=True)
    assert result['executed'] and not result['errors']
    assert count_pieces(state, rc.MORINI, rc.GERMANS, rc.SETTLEMENT) == (remaining == 2)
    assert count_pieces(state, rc.MORINI, rc.GERMANS, rc.WARBAND) == (7 if remaining == 2 else 5)
    assert state['resources'][rc.GERMANS] == (7 if remaining == 2 else 10)
    assert state['_command_with_sa'] is (remaining == 1)


def test_campaign_bot_planning_excludes_live_agent_and_sets_budget_before_dispatch(monkeypatch):
    from fs_bot.engine.winter_campaign import _bot_plan
    state = _state()
    agent = lambda *_: pytest.fail('planning consulted live player')
    state['decision_agent'] = agent
    def dispatch(planning, faction):
        assert 'decision_agent' not in planning
        assert planning['_command_with_sa'] is False
        assert planning['resources'][faction] == 10
        return {'command': 'Pass'}
    monkeypatch.setattr('fs_bot.bots.bot_dispatch.dispatch_bot_turn', dispatch)
    assert _bot_plan(state, rc.ARVERNI, 1) == {'decline': True}
    assert state['decision_agent'] is agent
