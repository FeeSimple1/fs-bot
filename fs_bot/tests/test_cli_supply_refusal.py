"""Supply reconsideration menus keep completed Commands and granted scope."""
from copy import deepcopy
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.cli import supply
from fs_bot.cli.menus import set_board_hook
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.game_engine import ACTION_LIMITED_COMMAND
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state
from fs_bot.tools.seat_session import validate_response


def _state():
    return build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=5)


def _request(action_type="special_ability"):
    return {"kind": "supply_refusal", "action_type": action_type,
            "action": {"command": rc.CMD_MARCH, "regions": [],
                       "sa": rc.SA_BUILD, "sa_regions": [rc.SEQUANI],
                       "sa_timing": "after", "details": {
                           "march_plan": {"explicit_moves": []},
                           "build_plan": {"forts": [rc.SEQUANI]}}},
            "allowed_commands": list(rc.ROMAN_COMMANDS),
            "allowed_special_abilities": [rc.SA_BUILD, rc.SA_SCOUT, "No SA"],
            "limited": False, "context": {"answer": False}}


def test_continue_refused_action_allows_board_inspection_without_effects():
    state, output, shown = _state(), io.StringIO(), []
    before = encode(state)
    set_board_hook(lambda: shown.append("board"))
    try:
        agent = make_cli_reactive({rc.ROMANS}, io.StringIO("board\n1\n"), output)
        assert agent(state, rc.ROMANS, _request()) == {"continue": True}
    finally:
        set_board_hook(None)
    assert shown == ["board"]
    assert encode(state) == before
    assert "completed Command effects stay in place" in output.getvalue()


def test_declining_refused_build_preserves_preceding_command():
    state, request = _state(), _request()
    original = deepcopy(request)
    response = supply.collect_supply_refusal(state, rc.ROMANS, request,
                                             io.StringIO("4\n"), io.StringIO())
    replacement = response["replacement"]
    assert replacement["command"] == request["action"]["command"]
    assert replacement["details"]["march_plan"] == request["action"]["details"]["march_plan"]
    assert replacement["sa"] == "No SA" and replacement["sa_regions"] == []
    assert "build_plan" not in replacement["details"]
    assert request == original
    assert validate_response(state, request, response) == response


def test_scout_replacement_uses_post_command_board_and_keeps_march(monkeypatch):
    state, request = _state(), _request()
    before = encode(state)
    seen = []

    def collect(board, faction, action, stdin, stdout, **kwargs):
        seen.append((board, faction, deepcopy(action), kwargs))
        action["sa"] = rc.SA_SCOUT
        action["details"]["scout_plan"] = {"auxilia_moves": [], "scout_targets": []}
        return action

    monkeypatch.setattr(supply, "_collect_sa_plan", collect)
    monkeypatch.setattr("fs_bot.engine.supply_reconsideration.validate_response", lambda *args: args[-1])
    response = supply.collect_supply_refusal(state, rc.ROMANS, request,
                                             io.StringIO("3\n"), io.StringIO())
    board, faction, selected, kwargs = seen[0]
    assert board is not state and board["_diviciacus_preview"]
    assert selected["details"]["march_plan"] == request["action"]["details"]["march_plan"]
    assert "build_plan" not in selected["details"]
    assert kwargs["sa"] == rc.SA_SCOUT and kwargs["standalone"]
    assert response["replacement"]["sa"] == rc.SA_SCOUT
    assert encode(state) == before


def test_replacement_command_collector_receives_limited_grant(monkeypatch):
    state, request = _state(), _request("command")
    request.update(limited=True, allowed_commands=[rc.CMD_RECRUIT],
                   allowed_special_abilities=["No SA"],
                   allowed_regions=[rc.SEQUANI], max_regions=1)
    seen = []

    def collect(*args, **kwargs):
        seen.append((args, kwargs))
        return {"command": rc.CMD_RECRUIT, "sa": "No SA", "details": {}}

    monkeypatch.setattr(supply, "_collect_command", collect)
    monkeypatch.setattr("fs_bot.engine.supply_reconsideration.validate_response", lambda *args: args[-1])
    response = supply.collect_supply_refusal(state, rc.ROMANS, request,
                                             io.StringIO("2\n"), io.StringIO())
    args, kwargs = seen[0]
    assert args[2] == ACTION_LIMITED_COMMAND
    assert kwargs["allowed_commands"] == [rc.CMD_RECRUIT]
    assert kwargs["allowed_regions"] == [rc.SEQUANI]
    assert kwargs["max_regions"] == 1 and kwargs["allowed_sas"] == ["No SA"]
    assert response["replacement"]["command"] == rc.CMD_RECRUIT


def test_remaining_command_menu_preserves_event_destinations_and_excludes_used_regions(monkeypatch):
    state, request = _state(), _request('command')
    request.update(allowed_special_abilities=['No SA'],
                   allowed_regions=[rc.PROVINCIA, rc.SEQUANI],
                   excluded_regions=[rc.PROVINCIA],
                   grant={'required_destinations': [rc.UBII]})
    seen = []

    def collect(*args, **kwargs):
        seen.append(kwargs)
        return {'command': rc.CMD_RECRUIT, 'sa': 'No SA', 'details': {}}

    monkeypatch.setattr(supply, '_collect_command', collect)
    monkeypatch.setattr('fs_bot.engine.supply_reconsideration.validate_response', lambda *args: args[-1])
    supply.collect_supply_refusal(state, rc.ROMANS, request,
                                 io.StringIO('2\n'), io.StringIO())
    assert seen[0]['allowed_regions'] == [rc.SEQUANI]
    assert seen[0]['required_destinations'] == [rc.UBII]


def test_frumentum_refusal_menu_can_skip_its_unaffordable_recruit():
    state, request = _state(), _request('command')
    request['action'] = {'command': rc.CMD_RECRUIT, 'sa': 'No SA', 'details': {}}
    request['frumentum'] = {'kind': 'frumentum_action', 'remaining_actions': [rc.CMD_RECRUIT],
                            'remaining_resources': 0}
    output = io.StringIO()
    before = encode(state)
    response = supply.collect_supply_refusal(state, rc.ROMANS, request,
                                             io.StringIO('3\n'), output)
    assert response == {'replacement': {'skip': rc.CMD_RECRUIT}}
    assert 'Skip this Frumentum Command' in output.getvalue()
    assert encode(state) == before


@pytest.mark.parametrize("timing,answers", [("before", "2\n1\n1\n"),
                                          ("after", "1\ny\n1\n"),
                                          ("during", "3\n1\n1\n")])
def test_command_collector_filters_sa_without_removing_order_choices(monkeypatch, timing, answers):
    from fs_bot.cli import human_plan
    from fs_bot.engine.game_engine import ACTION_COMMAND_SA
    state, output = _state(), io.StringIO()
    before = encode(state)
    calls = []

    def command(*args, **kwargs):
        return {"command": rc.CMD_RECRUIT, "regions": [], "sa": "No SA",
                "sa_regions": [], "details": {"recruit_plan": []}}

    def ability(board, faction, action, stdin, stdout, sa, before_state):
        calls.append(sa)
        action["sa"] = sa
        return action

    monkeypatch.setattr(human_plan, "_collect_command_plan", command)
    monkeypatch.setattr(human_plan, "_collect_sa_details", ability)
    monkeypatch.setattr(human_plan, "_preview_command", lambda st, *args: human_plan._planning_copy(st))
    monkeypatch.setattr("fs_bot.engine.execute._execute_sa", lambda *args: {})
    action = human_plan._collect_command(
        state, rc.ROMANS, ACTION_COMMAND_SA, io.StringIO(answers), output,
        allowed_commands=[rc.CMD_RECRUIT], allowed_sas=[rc.SA_SCOUT])
    assert action["sa_timing"] == timing
    assert calls == [rc.SA_SCOUT]
    assert rc.SA_BUILD not in output.getvalue() and rc.SA_BESIEGE not in output.getvalue()
    assert encode(state) == before


@pytest.mark.parametrize("response", [None, {}, {"continue": False}, {"continue": 1},
                                     {"continue": True, "replacement": {}}])
def test_durable_supply_refusal_does_not_accept_malformed_response(response):
    with pytest.raises(ValueError):
        validate_response(_state(), _request(), response)
