"""Human ordering and SA legality against Chapters 2 and 4 of the references."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot.board.pieces import count_pieces
from fs_bot.cli.human_plan import collect_player_action
from fs_bot.engine.execute import execute_decision, _execute_enlist, _execute_march
from fs_bot.engine.game_engine import ACTION_COMMAND_SA
from fs_bot.engine.moves import validate_player_action
from fs_bot.rules_consts import (
    SCENARIO_GREAT_REVOLT, SCENARIO_ARIOVISTUS, ROMANS, AEDUI, ARVERNI,
    BELGAE, GERMANS, AEDUI_REGION, MANDUBII, ATREBATES, MORINI, PROVINCIA,
    BRITANNIA, FORT, WARBAND, AUXILIA, WINTER_CARD, MARKER_DEVASTATED,
)
from fs_bot.state.setup import setup_scenario


def state(scenario=SCENARIO_GREAT_REVOLT):
    st = setup_scenario(scenario, seed=3)
    st["non_player_factions"] = set()
    return st


def rally(region, sa="No SA", timing="after"):
    return {"command": "Rally", "regions": [], "sa": sa,
            "sa_regions": [], "sa_timing": timing,
            "details": {"rally_plan": {"warbands": [region]}}}


def march(origin=ATREBATES, destination=MORINI, sa="No SA"):
    return {"command": "March", "regions": [], "sa": sa, "sa_regions": [],
            "details": {"origins": [origin], "destinations": [destination],
                        "routes": {origin: [destination]}}}


def test_cli_sa_first_trade_funds_zero_resource_rally():
    # §4.1: SA may execute immediately before the Command.
    st = state()
    st["resources"][AEDUI] = 0
    out = StringIO()
    action = collect_player_action(st, AEDUI, ACTION_COMMAND_SA,
                                  StringIO("5\n1\n4\n1\n3\n3\n1\n"), out)
    assert action["sa_timing"] == "before"
    assert out.getvalue().index("Which Special Activity?") < out.getvalue().index("Which accompanying Command?")
    assert st["resources"][AEDUI] == 0  # planning did not execute the SA
    before = count_pieces(st, AEDUI_REGION, AEDUI, WARBAND)
    result = execute_decision(st, AEDUI, {"player_action": action})
    assert result["executed"] and result["sa_timing"] == "before"
    assert count_pieces(st, AEDUI_REGION, AEDUI, WARBAND) > before
    assert st["resources"][AEDUI] == 5


def test_cli_command_first_keeps_after_timing():
    st = state()
    st["resources"][AEDUI] = 1
    out = StringIO()
    action = collect_player_action(st, AEDUI, ACTION_COMMAND_SA,
                                  StringIO("1\n3\n3\n1\ny\n1\n4\nn\n"), out)
    assert action["sa_timing"] == "after"
    assert out.getvalue().index("Which Command?") < out.getvalue().index("Which Special Activity?")
    result = execute_decision(st, AEDUI, {"player_action": action})
    assert result["executed"] and result["sa_timing"] == "after"
    assert st["resources"][AEDUI] == 6


def test_cli_rally_trade_continue_rally_official_example():
    # The example printed in §4.1: run out of Resources, Trade, keep Rallying.
    st = state()
    st["resources"][AEDUI] = 1
    out = StringIO()
    action = collect_player_action(st, AEDUI, ACTION_COMMAND_SA,
                                  StringIO("6\n1\n1\n3\n1\n1\n4\n2\n2\n1\nn\n"), out)
    assert action["sa_timing"] == "during"
    assert st["resources"][AEDUI] == 1
    result = execute_decision(st, AEDUI, {"player_action": action})
    assert result["executed"] and result["sa_timing"] == "during"
    assert all(part["executed"] for part in result["command_parts"])
    assert st["resources"][AEDUI] == 5


def test_failed_command_rolls_back_prior_trade_and_rng_keeps_turn_identity():
    st = state()
    st["resources"][AEDUI] = 0
    st["markers"].setdefault(AEDUI_REGION, {})[MARKER_DEVASTATED] = True
    progress = st["_card_turn"] = {"actions_taken": []}
    before = deepcopy(st)
    result = execute_decision(st, AEDUI, {"player_action": rally(AEDUI_REGION, "Trade", "before")})
    assert not result["executed"] and result["rolled_back"]
    assert st["resources"] == before["resources"]
    assert st["spaces"] == before["spaces"]
    assert st["rng"].getstate() == before["rng"].getstate()
    assert st["_card_turn"] is progress


def test_build_at_illegal_march_destination_refused_at_execution():
    # §4.2.1: Morini remains far from Caesar in Provincia after this March.
    st = state()
    action = march(sa="Build")
    action["details"]["build_plan"] = {"forts": [MORINI]}
    action["sa_regions"] = [MORINI]
    ok, preview = validate_player_action(st, ROMANS, action)
    assert ok and preview["errors"]  # failed SA is visible even with valid March
    result = execute_decision(st, ROMANS, {"player_action": action})
    assert result["executed"] and not result["sa_execution"]["executed"]
    assert count_pieces(st, MORINI, ROMANS, FORT) == 0
    assert result["sa_execution"]["sa"] == "Build"  # no automatic human Scout


def test_command_first_build_choices_include_newly_legal_march_destination():
    # §4.2.1 example: March into an enemy Region, then immediately Build there.
    st = state()
    assert count_pieces(st, AEDUI_REGION, ROMANS) == 0
    action = collect_player_action(
        st, ROMANS, ACTION_COMMAND_SA,
        StringIO("2\n5\n5\n1\n1\ny\ny\n1\n2\n3\n1\nn\n"), StringIO())
    assert action["details"]["build_plan"]["forts"] == [AEDUI_REGION]
    assert count_pieces(st, AEDUI_REGION, ROMANS) == 0
    result = execute_decision(st, ROMANS, {"player_action": action})
    assert result["executed"] and result["sa_execution"]["executed"]
    assert count_pieces(st, AEDUI_REGION, ROMANS, FORT) == 1


def test_devastate_cannot_target_roman_controlled_region():
    st = state()
    from fs_bot.rules_consts import CARNUTES
    action = rally(CARNUTES, "Devastate")
    action["sa_regions"] = [MANDUBII]
    roman_before = deepcopy(st["spaces"][MANDUBII]["pieces"][ROMANS])
    result = execute_decision(st, ARVERNI, {"player_action": action})
    assert result["executed"] and not result["sa_execution"]["executed"]
    assert st["spaces"][MANDUBII]["pieces"][ROMANS] == roman_before
    assert MARKER_DEVASTATED not in st["markers"].get(MANDUBII, {})


@pytest.mark.parametrize("faction,command,sa,scenario", [
    (ROMANS, "Battle", "Build", SCENARIO_GREAT_REVOLT),
    (AEDUI, "Battle", "Suborn", SCENARIO_GREAT_REVOLT),
    (BELGAE, "March", "Rampage", SCENARIO_GREAT_REVOLT),
    (GERMANS, "Rally", "Intimidate", SCENARIO_ARIOVISTUS),
    (GERMANS, "Battle", "Settle", SCENARIO_ARIOVISTUS),
])
def test_forbidden_sa_command_pair_rejected_before_mutation(faction, command, sa, scenario):
    st = state(scenario)
    resources = dict(st["resources"])
    result = execute_decision(st, faction, {"player_action": {
        "command": command, "sa": sa, "details": {}}})
    assert not result["executed"] and "cannot accompany" in result["reason"]
    assert st["resources"] == resources


def test_sa_before_march_cannot_bypass_britannia_restriction():
    st = state()
    action = march(destination=BRITANNIA, sa="Scout")
    action["sa_timing"] = "before"
    result = execute_decision(st, ROMANS, {"player_action": action})
    assert not result["executed"] and "Britannia" in result["reason"]


def test_frost_blocks_human_march_but_not_event_internal_march():
    # §2.3.8 prohibits normal March, explicitly exempting Event March.
    st = state()
    st["current_card"], st["next_card"] = 1, WINTER_CARD
    before = count_pieces(st, ATREBATES, ROMANS, AUXILIA)
    result = execute_decision(st, ROMANS, {"player_action": march()})
    assert not result["executed"] and "Frost" in result["reason"]
    assert count_pieces(st, ATREBATES, ROMANS, AUXILIA) == before
    # Events call the mechanic executor directly, outside normal SoP validation.
    event_result = _execute_march(st, ROMANS, march())
    assert event_result["executed"]


def test_frost_also_blocks_free_enlist_march():
    st = state()
    st["current_card"], st["next_card"] = 1, WINTER_CARD
    result = _execute_enlist(st, BELGAE, {"details": {
        "enlist": {"type": "german_march", "origin": MORINI, "destination": ATREBATES}}})
    assert not result["executed"] and "Frost" in str(result)


def test_interrupted_command_cannot_select_same_region_twice():
    st = state()
    action = rally(AEDUI_REGION, "Trade", "during")
    action["details"]["command_parts"] = [rally(AEDUI_REGION), rally(AEDUI_REGION)]
    result = execute_decision(st, AEDUI, {"player_action": action})
    assert not result["executed"] and "only once" in result["reason"]
