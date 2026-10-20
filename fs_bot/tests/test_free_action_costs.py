"""Source-derived Resource/SA grants: §§3.2.4, 3.3.4, 5.4 and A3.4.4."""
import copy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces
from fs_bot.cards.capabilities import activate_capability
from fs_bot.commands.common import free_action_scope, battle_cost, is_free_action
from fs_bot.commands.rally import rally_cost, recruit_cost
from fs_bot.engine.execute import (_execute_battle, _execute_bot_command,
                                   _resolve_free_command)
from fs_bot.state.state_schema import build_initial_state


def empty(scenario=rc.SCENARIO_GREAT_REVOLT):
    return build_initial_state(scenario, seed=7)


def battle_action(faction, region=rc.MANDUBII):
    target = rc.BELGAE if faction == rc.ROMANS else rc.ROMANS
    return {"command": "Battle", "sa": "No SA", "sa_regions": [],
            "details": {"battle_plan": [{"region": region, "target": target}],
                        "no_retreat": True}}


def battle_state(faction, scenario, devastated=False):
    st = empty(scenario)
    pt = rc.AUXILIA if faction == rc.ROMANS else rc.WARBAND
    place_piece(st, rc.MANDUBII, faction, pt, 4)
    enemy = rc.BELGAE if faction == rc.ROMANS else rc.ROMANS
    ept = rc.WARBAND if enemy == rc.BELGAE else rc.AUXILIA
    place_piece(st, rc.MANDUBII, enemy, ept, 1)
    st["resources"][faction] = 8
    if devastated:
        st["markers"].setdefault(rc.MANDUBII, {})[rc.MARKER_DEVASTATED] = True
    return st


@pytest.mark.parametrize("faction,scenario,base_cost", [
    (rc.ROMANS, rc.SCENARIO_GREAT_REVOLT, 2),
    (rc.ARVERNI, rc.SCENARIO_GREAT_REVOLT, 1),
    (rc.AEDUI, rc.SCENARIO_GREAT_REVOLT, 1),
    (rc.BELGAE, rc.SCENARIO_GREAT_REVOLT, 1),
    (rc.GERMANS, rc.SCENARIO_ARIOVISTUS, 1),
])
@pytest.mark.parametrize("devastated", [False, True])
def test_normal_battle_charges_exact_region_cost(faction, scenario, base_cost, devastated):
    st = battle_state(faction, scenario, devastated)
    res = _execute_battle(st, faction, battle_action(faction))
    assert res["executed"]
    assert not res["errors"]
    assert st["resources"][faction] == 8 - base_cost * (2 if devastated else 1)


def test_battle_cannot_run_without_resources_or_change_board():
    st = battle_state(rc.BELGAE, rc.SCENARIO_GREAT_REVOLT)
    st["resources"][rc.BELGAE] = 0
    before = copy.deepcopy(st["spaces"])
    rng = st["rng"].getstate()
    res = _execute_battle(st, rc.BELGAE, battle_action(rc.BELGAE))
    assert not res["executed"]
    assert res["errors"]
    assert st["spaces"] == before
    assert st["rng"].getstate() == rng


def test_convictolitavis_doubles_paid_battle_but_not_free_battle():
    st = battle_state(rc.AEDUI, rc.SCENARIO_GREAT_REVOLT, True)
    activate_capability(st, 43, rc.EVENT_SHADED)
    assert battle_cost(st, rc.MANDUBII, rc.AEDUI) == 4
    st["resources"][rc.AEDUI] = 0
    with free_action_scope(st, rc.AEDUI):
        assert battle_cost(st, rc.MANDUBII, rc.AEDUI) == 0
        res = _execute_battle(st, rc.AEDUI, battle_action(rc.AEDUI))
    assert res["executed"]
    assert st["resources"][rc.AEDUI] == 0
    assert "_free_action_factions" not in st


def test_free_battle_scope_covers_nested_grants_and_restores_after_error():
    st = empty()
    with free_action_scope(st, rc.ROMANS):
        assert is_free_action(st, rc.ROMANS)
        assert not is_free_action(st, rc.BELGAE)
        with pytest.raises(RuntimeError):
            with free_action_scope(st, rc.BELGAE):
                assert is_free_action(st, rc.ROMANS)
                assert is_free_action(st, rc.BELGAE)
                raise RuntimeError("interrupt")
        assert is_free_action(st, rc.ROMANS)
        assert not is_free_action(st, rc.BELGAE)
    assert "_free_action_factions" not in st


@pytest.mark.parametrize("faction", [rc.ARVERNI, rc.AEDUI, rc.BELGAE])
def test_event_rally_costs_zero_at_zero_resources(faction):
    st = empty()
    region = {rc.ARVERNI: rc.ARVERNI_REGION, rc.AEDUI: rc.AEDUI_REGION,
              rc.BELGAE: rc.MORINI}[faction]
    action = {"command": "Rally", "sa": "No SA", "sa_regions": [],
              "details": {"rally_plan": {"warbands": [region]}}}
    res = _execute_bot_command(st, faction, action)
    assert res["executed"] and not res["errors"]
    assert count_pieces(st, region, faction, rc.WARBAND) >= 1
    assert st["resources"][faction] == 0
    assert rally_cost(st, region, faction) > 0


def test_free_recruit_overrides_capability_cost_and_does_not_add_build():
    st = empty()
    place_piece(st, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    activate_capability(st, 13, rc.EVENT_SHADED)
    action = {"command": "Recruit", "sa": "Build", "sa_regions": [],
              "details": {"recruit_plan": [{"region": rc.PROVINCIA,
                                              "action": "place_auxilia"}]}}
    res = _execute_bot_command(st, rc.ROMANS, action)
    assert res["executed"] and not res["errors"]
    assert st["resources"][rc.ROMANS] == 0
    assert "sa_execution" not in res
    assert recruit_cost(st, rc.PROVINCIA) == 2


def test_free_command_requires_explicit_sa_grant(monkeypatch):
    import fs_bot.engine.execute as ex
    st = empty()
    action = {"command": "Raid", "sa": "Trade", "details": {}}
    monkeypatch.setattr(ex, "_execute_raid", lambda *a: {"executed": True})
    calls = []
    monkeypatch.setattr(ex, "_execute_sa", lambda *a: calls.append(a[-1]["sa"]))
    ex._execute_bot_command(st, rc.AEDUI, action)
    assert calls == ["No SA"]
    calls.clear()
    ex._execute_bot_command(st, rc.AEDUI, action, with_sa=True)
    assert calls == ["Trade"]


def test_free_battle_planner_ignores_budget_but_paid_planner_does_not():
    from fs_bot.bots.bot_common import affordable_battle_plan
    st = empty()
    plan = [{"region": rc.MANDUBII, "target": rc.BELGAE},
            {"region": rc.CARNUTES, "target": rc.BELGAE}]
    st["resources"][rc.ROMANS] = 3
    assert affordable_battle_plan(st, rc.ROMANS, plan) == plan[:1]
    with free_action_scope(st, rc.ROMANS):
        assert affordable_battle_plan(st, rc.ROMANS, plan) == plan


@pytest.mark.parametrize("faction", [rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.GERMANS])
def test_free_paid_special_activity_is_not_blocked_at_zero_resources(faction):
    st = empty(rc.SCENARIO_ARIOVISTUS if faction == rc.GERMANS else rc.SCENARIO_GREAT_REVOLT)
    if faction == rc.ROMANS:
        from fs_bot.commands.sa_build import build_fort
        action = lambda: build_fort(st, rc.MANDUBII)
    elif faction == rc.ARVERNI:
        from fs_bot.commands.sa_entreat import entreat_replace_piece
        place_piece(st, rc.MANDUBII, rc.AEDUI, rc.WARBAND)
        action = lambda: entreat_replace_piece(st, rc.MANDUBII, rc.AEDUI, rc.WARBAND)
    elif faction == rc.AEDUI:
        from fs_bot.commands.sa_suborn import suborn
        place_piece(st, rc.MANDUBII, rc.AEDUI, rc.WARBAND)
        action = lambda: suborn(st, rc.MANDUBII, [
            {"action": "place", "faction": rc.AEDUI, "piece_type": rc.WARBAND}])
    else:
        from fs_bot.commands.sa_settle import settle
        action = lambda: settle(st, rc.MANDUBII)
    with free_action_scope(st, faction):
        result = action()
    assert result["cost"] == 0
    assert st["resources"][faction] == 0
