"""Integration tests for the command/event execution layer (Phase-4b slice).

These exercise fs_bot/engine/execute.py end to end: a recorded decision is
applied to the board via the real mechanic functions, and state integrity
(validate_state) is preserved. Covers the slice's two wired paths (Seize,
Event) plus the opt-in engine integration and the no-op guarantee for
not-yet-wired commands.
"""

import copy
import io
import contextlib

from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import validate_state
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import run_game, get_sop_factions
from fs_bot.cli.dispatcher import make_decision_func
from fs_bot.commands.seize import count_dispersed_on_map, get_dispersible_tribes
from fs_bot.map.map_data import get_playable_regions
from fs_bot.rules_consts import (
    SCENARIO_GREAT_REVOLT, SCENARIO_RECONQUEST, SCENARIO_PAX_GALLICA,
    SCENARIO_ARIOVISTUS, SCENARIO_GALLIC_WAR, ALL_SCENARIOS,
    ROMANS, EVENT_SHADED, EVENT_UNSHADED,
)


def _first_dispersible_region(state):
    for r in get_playable_regions(state["scenario"], state.get("capabilities")):
        if get_dispersible_tribes(state, r):
            return r
    return None


def _seize_decision(region):
    return {"action": "command", "bot_action": {
        "command": "Seize", "regions": [region], "sa": "Build",
        "sa_regions": [], "details": {"disperse_regions": [region]}}}


def _event_decision(card_id, preference=EVENT_UNSHADED):
    return {"action": "event", "bot_action": {
        "command": "Event", "regions": [], "sa": "No SA", "sa_regions": [],
        "details": {"card_id": card_id, "text_preference": preference,
                    "instruction": None}}}


class TestSeizeExecution:
    def test_seize_disperses_tribe_and_forages(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        region = _first_dispersible_region(st)
        assert region is not None
        before = count_dispersed_on_map(st)
        res = execute_decision(st, ROMANS, _seize_decision(region))
        assert res["executed"] is True
        assert res["command"] == "Seize"
        # A Subdued tribe became Dispersed: marker count rose.
        assert count_dispersed_on_map(st) == before + res["tribes_dispersed_total"]
        assert res["tribes_dispersed_total"] >= 1
        # Forage yields Resources (>= 0; non-negative integer).
        assert res["forage_resources_total"] >= 0
        # State stays internally consistent.
        assert validate_state(st) == []

    def test_seize_reports_build_sa_as_unwired(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        region = _first_dispersible_region(st)
        res = execute_decision(st, ROMANS, _seize_decision(region))
        # The accompanying Build SA is not part of this slice.
        assert res["sa_not_wired"] == "Build"


class TestEventExecution:
    def test_param_free_event_executes_and_changes_state(self):
        # Card 5 (Gallia Togata) executes without event_params and mutates state.
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        st["current_card"] = 5
        snap = copy.deepcopy(st)
        res = execute_decision(st, ROMANS, _event_decision(5))
        assert res["executed"] is True
        assert res["shaded"] is False
        changed = (st["resources"] != snap["resources"]
                   or st["spaces"] != snap["spaces"]
                   or st.get("capabilities") != snap.get("capabilities")
                   or st.get("senate") != snap.get("senate"))
        assert changed
        assert validate_state(st) == []

    def test_shaded_preference_maps_through(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        st["current_card"] = 5
        res = execute_decision(st, ROMANS, _event_decision(5, EVENT_SHADED))
        assert res["shaded"] is True
        assert res["executed"] is True

    def test_parameter_requiring_event_is_reported_not_raised(self):
        # Card 1 (Cicero) needs senate_direction in event_params; the decision
        # layer doesn't supply it yet, so execution reports rather than crashes.
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        st["current_card"] = 1
        res = execute_decision(st, ROMANS, _event_decision(1))
        assert res["executed"] is False
        assert "parameter" in res["reason"].lower() or "needs" in res["reason"].lower()
        assert validate_state(st) == []


class TestUnwiredAndGuards:
    def test_unwired_command_is_noop(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        snap = copy.deepcopy(st)
        dec = {"action": "command", "bot_action": {
            "command": "March", "regions": [], "sa": "No SA",
            "sa_regions": [], "details": {}}}
        res = execute_decision(st, ROMANS, dec)
        assert res["executed"] is False
        assert "not yet wired" in res["reason"]
        # Board untouched by an unwired command.
        assert st["spaces"] == snap["spaces"]
        assert st["resources"] == snap["resources"]

    def test_missing_bot_action_is_handled(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        res = execute_decision(st, ROMANS, {"action": "command"})
        assert res["executed"] is False


class TestEngineIntegration:
    def test_execute_flag_off_is_default_and_record_only(self):
        # With execute=False (default) a full game runs and ends cleanly.
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=5)
        st["non_player_factions"] = set(get_sop_factions(st))
        dfn = make_decision_func({f: "bot" for f in get_sop_factions(st)},
                                 pause=False)
        with contextlib.redirect_stdout(io.StringIO()):
            run_game(st, decision_func=dfn)  # execute defaults False
        assert validate_state(st) == []

    def test_full_game_with_execution_stays_integrity_clean(self):
        # With execute=True, the wired Commands/Events fire during real games
        # across every scenario/seed without breaking state integrity.
        for sc in ALL_SCENARIOS:
            for seed in (1, 4, 9):
                st = setup_scenario(sc, seed=seed)
                st["non_player_factions"] = set(get_sop_factions(st))
                dfn = make_decision_func(
                    {f: "bot" for f in get_sop_factions(st)}, pause=False)
                with contextlib.redirect_stdout(io.StringIO()):
                    run_game(st, decision_func=dfn, execute=True)
                errs = validate_state(st)
                assert errs == [], f"{sc} seed={seed}: {errs[:3]}"


# ---------------------------------------------------------------------------
# Raid and Rally execution (second slice)
# ---------------------------------------------------------------------------

from fs_bot.board.pieces import place_piece, count_pieces, get_available
from fs_bot.board.control import refresh_all_control
from fs_bot.rules_consts import (
    ARVERNI, AEDUI, BELGAE, WARBAND, ALLY, HIDDEN,
    ARVERNI_REGION,
)


class TestRaidExecution:
    def test_raid_gains_resources(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=2)
        place_piece(st, ARVERNI_REGION, ARVERNI, WARBAND, 2, piece_state=HIDDEN)
        refresh_all_control(st)
        before = st["resources"][ARVERNI]
        decision = {"action": "command", "bot_action": {
            "command": "Raid", "regions": [ARVERNI_REGION], "sa": "No SA",
            "sa_regions": [], "details": {"raid_plan": [
                {"region": ARVERNI_REGION, "target": None},
                {"region": ARVERNI_REGION, "target": None}]}}}
        res = execute_decision(st, ARVERNI, decision)
        assert res["executed"] is True
        assert res["command"] == "Raid"
        assert st["resources"][ARVERNI] == before + res["resources_gained_total"]
        assert res["resources_gained_total"] >= 1
        assert validate_state(st) == []

    def test_raid_caps_two_flips_per_region(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=2)
        place_piece(st, ARVERNI_REGION, ARVERNI, WARBAND, 4, piece_state=HIDDEN)
        refresh_all_control(st)
        # Plan lists 4 gain flips in one region; rules cap at 2.
        decision = {"action": "command", "bot_action": {
            "command": "Raid", "regions": [ARVERNI_REGION], "sa": "No SA",
            "sa_regions": [], "details": {"raid_plan": [
                {"region": ARVERNI_REGION, "target": None}] * 4}}}
        res = execute_decision(st, ARVERNI, decision)
        assert res["resources_gained_total"] <= 2
        assert validate_state(st) == []


class TestRallyExecution:
    def test_rally_places_warbands(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=2)
        # Arverni Home Region qualifies for warband placement (§3.3.1).
        avail_before = get_available(st, ARVERNI, WARBAND)
        on_map_before = count_pieces(st, ARVERNI_REGION, ARVERNI, WARBAND)
        decision = {"action": "command", "bot_action": {
            "command": "Rally", "regions": [ARVERNI_REGION], "sa": "No SA",
            "sa_regions": [], "details": {"rally_plan": {
                "citadels": [], "allies": [],
                "warbands": [ARVERNI_REGION]}}}}
        res = execute_decision(st, ARVERNI, decision)
        assert res["executed"] is True
        assert res["command"] == "Rally"
        # Warbands were placed in the region.
        assert count_pieces(st, ARVERNI_REGION, ARVERNI, WARBAND) > on_map_before
        assert get_available(st, ARVERNI, WARBAND) < avail_before
        assert validate_state(st) == []

    def test_rally_handles_german_dict_warband_entries(self):
        # German rally_plan uses {"region","cost"} warband entries; the
        # executor must accept dict entries as well as plain strings.
        st = setup_scenario(SCENARIO_ARIOVISTUS, seed=2)
        from fs_bot.rules_consts import GERMANS, SUGAMBRI
        decision = {"action": "command", "bot_action": {
            "command": "Rally", "regions": [SUGAMBRI], "sa": "No SA",
            "sa_regions": [], "details": {"rally_plan": {
                "allies": [], "warbands": [{"region": SUGAMBRI, "cost": 0}]}}}}
        res = execute_decision(st, GERMANS, decision)
        # Either it placed warbands or recorded a clean per-region error;
        # crucially it must not raise and state stays consistent.
        assert res["command"] == "Rally"
        assert validate_state(st) == []


class TestRecruitStillUnwired:
    def test_recruit_is_reported_unwired(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=2)
        decision = {"action": "command", "bot_action": {
            "command": "Recruit", "regions": [], "sa": "Build",
            "sa_regions": [], "details": {"potential_allies": 2,
                                          "potential_auxilia": 4}}}
        res = execute_decision(st, ROMANS, decision)
        assert res["executed"] is False
        assert "not yet wired" in res["reason"]
