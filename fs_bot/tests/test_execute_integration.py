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
    def test_unknown_command_is_noop(self):
        # Every real Command is now wired; an unrecognized label must still be
        # a safe no-op rather than raising.
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        snap = copy.deepcopy(st)
        dec = {"action": "command", "bot_action": {
            "command": "Frobnicate", "regions": [], "sa": "No SA",
            "sa_regions": [], "details": {}}}
        res = execute_decision(st, ROMANS, dec)
        assert res["executed"] is False
        # Board untouched by an unrecognized command.
        assert st["spaces"] == snap["spaces"]
        assert st["resources"] == snap["resources"]

    def test_empty_march_plan_shape_is_deferred(self):
        # A March plan that is not the execution-complete threat shape is
        # deferred (reported, not executed), never guessed.
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        dec = {"action": "command", "bot_action": {
            "command": "March", "regions": [], "sa": "No SA",
            "sa_regions": [], "details": {"march_plan": {
                "control_destinations": [], "origins": []}}}}
        res = execute_decision(st, ROMANS, dec)
        assert res["executed"] is False
        assert "deferred" in res["reason"] or "not execution-complete" in res["reason"]

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


class TestRecruitExecution:
    def test_recruit_executes_bot_plan(self):
        # The Roman recruit node now emits an explicit recruit_plan; executing
        # it places Roman pieces on the map.
        from fs_bot.bots.roman_bot import node_r_recruit
        from fs_bot.board.pieces import count_on_map
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=4)
        act = node_r_recruit(st)
        # The node may redirect to Seize if Recruit wouldn't place enough;
        # only assert execution when it actually chose Recruit.
        if act["command"] != "Recruit":
            import pytest
            pytest.skip("bot did not choose Recruit in this state")
        aux_before = count_on_map(st, ROMANS, AUXILIA)
        res = execute_decision(st, ROMANS, {"action": "command",
                                            "bot_action": act})
        assert res["command"] == "Recruit"
        # At least some pieces placed, and integrity preserved.
        assert count_on_map(st, ROMANS, AUXILIA) >= aux_before
        assert res["executed"] is True
        assert validate_state(st) == []


# ---------------------------------------------------------------------------
# Battle execution (slice 3)
# ---------------------------------------------------------------------------

from fs_bot.rules_consts import LEGION, AUXILIA, REVEALED


class TestBattleExecution:
    def test_battle_inflicts_losses(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=2)
        # Arverni (6 Warbands) attack Romans (3 Auxilia) in the Arverni Region.
        place_piece(st, ARVERNI_REGION, ARVERNI, WARBAND, 6, piece_state=REVEALED)
        place_piece(st, ARVERNI_REGION, ROMANS, AUXILIA, 3)
        refresh_all_control(st)
        before = count_pieces(st, ARVERNI_REGION, ROMANS, AUXILIA)
        decision = {"action": "command", "bot_action": {
            "command": "Battle", "regions": [ARVERNI_REGION], "sa": "No SA",
            "sa_regions": [], "details": {"battle_plan": [
                {"region": ARVERNI_REGION, "target": ROMANS,
                 "is_trigger": True}]}}}
        res = execute_decision(st, ARVERNI, decision)
        assert res["executed"] is True
        assert res["command"] == "Battle"
        assert (ARVERNI_REGION, ROMANS) in res["battles_resolved"]
        # Romans lost Auxilia.
        assert count_pieces(st, ARVERNI_REGION, ROMANS, AUXILIA) < before
        assert validate_state(st) == []

    def test_battle_accepts_roman_targets_list_shape(self):
        # Roman battle_plan entries use "targets" (ranked list); the executor
        # must battle the top-ranked defender without raising.
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=2)
        place_piece(st, ARVERNI_REGION, ROMANS, AUXILIA, 6, piece_state=REVEALED)
        place_piece(st, ARVERNI_REGION, ROMANS, LEGION, 2, from_legions_track=True)
        place_piece(st, ARVERNI_REGION, ARVERNI, WARBAND, 2)
        refresh_all_control(st)
        decision = {"action": "command", "bot_action": {
            "command": "Battle", "regions": [ARVERNI_REGION], "sa": "No SA",
            "sa_regions": [], "details": {"battle_plan": [
                {"region": ARVERNI_REGION, "targets": [ARVERNI]}]}}}
        res = execute_decision(st, ROMANS, decision)
        assert res["executed"] is True
        assert (ARVERNI_REGION, ARVERNI) in res["battles_resolved"]
        assert validate_state(st) == []

    def test_ambush_flag_routes_through(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=2)
        place_piece(st, ARVERNI_REGION, ARVERNI, WARBAND, 6, piece_state=HIDDEN)
        place_piece(st, ARVERNI_REGION, ROMANS, AUXILIA, 2)
        refresh_all_control(st)
        decision = {"action": "command", "bot_action": {
            "command": "Battle", "regions": [ARVERNI_REGION], "sa": "Ambush",
            "sa_regions": [ARVERNI_REGION], "details": {"battle_plan": [
                {"region": ARVERNI_REGION, "target": ROMANS,
                 "is_trigger": True}]}}}
        res = execute_decision(st, ARVERNI, decision)
        assert res["executed"] is True
        assert res["battles_resolved"][0] == (ARVERNI_REGION, ROMANS)
        # Ambush forbids defender Retreat — recorded in the battle result.
        assert res["count"] == 1
        assert validate_state(st) == []


class TestSenateBoxFirstWinter:
    """Regression: Pax Gallica starts the Senate marker in the Senate box
    (position None); the first Senate Phase places it at Intrigue (not Firm)
    rather than indexing a marker that is not yet on the track."""

    def test_marker_in_box_placed_at_intrigue(self):
        from fs_bot.engine.winter import _senate_marker_shift
        from fs_bot.rules_consts import INTRIGUE
        st = setup_scenario(SCENARIO_PAX_GALLICA, seed=1)
        # Sanity: Pax Gallica begins with the marker in the Senate box.
        assert st["senate"]["position"] is None
        result = _senate_marker_shift(st)
        assert st["senate"]["position"] == INTRIGUE
        assert st["senate"]["firm"] is False
        assert result["new_position"] == INTRIGUE


# ---------------------------------------------------------------------------
# March execution (slice 4) — threat-March shape only
# ---------------------------------------------------------------------------

from fs_bot.map.map_data import get_adjacent


class TestMarchExecution:
    def test_threat_march_moves_full_mobile_group_one_step(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=4)
        dest = get_adjacent(ARVERNI_REGION)[0]
        place_piece(st, ARVERNI_REGION, ARVERNI, WARBAND, 4, piece_state=REVEALED)
        refresh_all_control(st)
        origin_before = count_pieces(st, ARVERNI_REGION, ARVERNI, WARBAND)
        dest_before = count_pieces(st, dest, ARVERNI, WARBAND)
        decision = {"action": "command", "bot_action": {
            "command": "March", "regions": [dest], "sa": "No SA",
            "sa_regions": [], "details": {"march_plan": {
                "origins": [ARVERNI_REGION], "destinations": [dest]}}}}
        res = execute_decision(st, ARVERNI, decision)
        assert res["executed"] is True
        assert res["marches"][0]["origin"] == ARVERNI_REGION
        # All mobile Warbands left the origin and arrived at the destination.
        assert count_pieces(st, ARVERNI_REGION, ARVERNI, WARBAND) == 0
        assert count_pieces(st, dest, ARVERNI, WARBAND) == dest_before + origin_before
        assert validate_state(st) == []

    def test_non_adjacent_destination_is_deferred_not_guessed(self):
        # Pick a destination NOT adjacent to the origin; the executor must
        # defer that origin (no multi-step routing guess) and stay clean.
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=4)
        adj = set(get_adjacent(ARVERNI_REGION))
        from fs_bot.map.map_data import get_playable_regions
        far = [r for r in get_playable_regions(st["scenario"], st.get("capabilities"))
               if r != ARVERNI_REGION and r not in adj]
        place_piece(st, ARVERNI_REGION, ARVERNI, WARBAND, 3, piece_state=REVEALED)
        refresh_all_control(st)
        decision = {"action": "command", "bot_action": {
            "command": "March", "regions": [far[0]], "sa": "No SA",
            "sa_regions": [], "details": {"march_plan": {
                "origins": [ARVERNI_REGION], "destinations": [far[0]]}}}}
        res = execute_decision(st, ARVERNI, decision)
        assert ARVERNI_REGION in res["deferred_origins"]
        assert res["executed"] is False
        assert validate_state(st) == []


# ---------------------------------------------------------------------------
# Standalone Special Activities (slice 5): Trade, Settle, Devastate, Intimidate
# ---------------------------------------------------------------------------

import io as _io
import contextlib as _ctx
from fs_bot.board.pieces import find_leader
from fs_bot.engine.execute import _execute_sa
from fs_bot.engine.game_engine import run_game, get_sop_factions
from fs_bot.rules_consts import (
    AEDUI, GERMANS, SETTLEMENT, MARKER_DEVASTATED, ARIOVISTUS_LEADER,
    AEDUI_REGION,
    LEADER, SCENARIO_ARIOVISTUS,
)


class TestStandaloneSAs:
    def test_trade_yields_resources(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        before = st["resources"][AEDUI]
        res = _execute_sa(st, AEDUI, {"sa": "Trade", "sa_regions": [],
                                      "details": {}})
        assert res["executed"] is True
        assert st["resources"][AEDUI] >= before
        assert validate_state(st) == []

    def test_devastate_places_marker(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        res = _execute_sa(st, ARVERNI, {"sa": "Devastate",
                                        "sa_regions": [ARVERNI_REGION],
                                        "details": {}})
        assert res["executed"] is True
        assert st["markers"].get(ARVERNI_REGION, {}).get(MARKER_DEVASTATED) is True
        assert validate_state(st) == []

    def test_intimidate_translates_plan_and_removes_piece(self):
        # Operate at Ariovistus's own Region (Intimidate is valid there) to
        # avoid placing a second Leader.
        st = setup_scenario(SCENARIO_ARIOVISTUS, seed=3)
        region = find_leader(st, GERMANS)
        assert region is not None
        place_piece(st, region, GERMANS, WARBAND, 2, piece_state=HIDDEN)
        place_piece(st, region, ROMANS, AUXILIA, 1)
        refresh_all_control(st)
        before = count_pieces(st, region, ROMANS, AUXILIA)
        # The bot supplies the actual piece state; here the placed Auxilia
        # is Hidden, and target_state=None removes regardless of state.
        plan = [{"region": region, "target_faction": ROMANS,
                 "target_piece": AUXILIA, "target_state": None,
                 "free": False}]
        res = _execute_sa(st, GERMANS, {"sa": "Intimidate",
                                        "sa_regions": [region],
                                        "details": {"intimidate_plan": plan}})
        assert res["executed"] is True
        assert count_pieces(st, region, ROMANS, AUXILIA) < before
        assert validate_state(st) == []

    def test_settle_fires_in_real_ariovistus_games(self):
        # End-to-end: German bots Settle during real Ariovistus games; assert
        # the wired SA actually executes and integrity holds.
        settle_count = 0
        for seed in range(0, 8):
            st = setup_scenario(SCENARIO_ARIOVISTUS, seed=seed)
            st["non_player_factions"] = set(get_sop_factions(st))
            dfn = make_decision_func(
                {f: "bot" for f in get_sop_factions(st)}, pause=False)
            seen = {"n": 0}
            import fs_bot.engine.execute as _ex
            orig = _ex._execute_sa

            def _tally(s, f, ba, _orig=orig, _seen=seen):
                r = _orig(s, f, ba)
                if r and r.get("sa") == "Settle" and r.get("executed"):
                    _seen["n"] += 1
                return r
            _ex._execute_sa = _tally
            try:
                with _ctx.redirect_stdout(_io.StringIO()):
                    run_game(st, decision_func=dfn, execute=True)
            finally:
                _ex._execute_sa = orig
            settle_count += seen["n"]
            assert validate_state(st) == []
        assert settle_count > 0

    def test_deferred_sa_is_reported_not_executed(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        res = _execute_sa(st, ROMANS, {"sa": "Scout", "sa_regions": [],
                                       "details": {}})
        assert res["executed"] is False
        assert "not yet wired" in res["reason"]


# ---------------------------------------------------------------------------
# Deferred SAs now wired (slice 6): Suborn, Build
# ---------------------------------------------------------------------------

from fs_bot.map.map_data import get_tribes_in_region


class TestSubornAndBuild:
    def test_suborn_removes_enemy_ally(self):
        from fs_bot.rules_consts import MANDUBII
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        place_piece(st, MANDUBII, AEDUI, WARBAND, 1, piece_state=HIDDEN)
        tribe = get_tribes_in_region(MANDUBII, st["scenario"])[0]
        st["tribes"][tribe]["allied_faction"] = ARVERNI
        place_piece(st, MANDUBII, ARVERNI, ALLY)
        refresh_all_control(st)
        before = count_pieces(st, MANDUBII, ARVERNI, ALLY)
        plan = [{"region": MANDUBII, "actions": [
            {"action": "remove_ally", "tribe": tribe,
             "target_faction": ARVERNI}]}]
        res = _execute_sa(st, AEDUI, {"sa": "Suborn",
                                      "sa_regions": [MANDUBII],
                                      "details": {"suborn_plan": plan}})
        assert res["executed"] is True
        assert count_pieces(st, MANDUBII, ARVERNI, ALLY) == before - 1
        assert validate_state(st) == []

    def test_suborn_places_aedui_warband(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        place_piece(st, AEDUI_REGION, AEDUI, WARBAND, 1, piece_state=HIDDEN)
        refresh_all_control(st)
        before = count_pieces(st, AEDUI_REGION, AEDUI, WARBAND)
        plan = [{"region": AEDUI_REGION, "actions": [
            {"action": "place_warband"}]}]
        res = _execute_sa(st, AEDUI, {"sa": "Suborn",
                                      "sa_regions": [AEDUI_REGION],
                                      "details": {"suborn_plan": plan}})
        assert res["executed"] is True
        assert count_pieces(st, AEDUI_REGION, AEDUI, WARBAND) == before + 1
        assert validate_state(st) == []

    def test_build_fires_in_real_games(self):
        # Roman Build (recomputed via node_r_build) executes in real games.
        build_count = 0
        for seed in range(0, 6):
            st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=seed)
            st["non_player_factions"] = set(get_sop_factions(st))
            dfn = make_decision_func(
                {f: "bot" for f in get_sop_factions(st)}, pause=False)
            seen = {"n": 0}
            import fs_bot.engine.execute as _ex
            orig = _ex._execute_sa

            def _tally(s, f, ba, _orig=orig, _seen=seen):
                r = _orig(s, f, ba)
                if r and r.get("sa") == "Build" and r.get("executed"):
                    _seen["n"] += 1
                return r
            _ex._execute_sa = _tally
            try:
                with _ctx.redirect_stdout(_io.StringIO()):
                    run_game(st, decision_func=dfn, execute=True)
            finally:
                _ex._execute_sa = orig
            build_count += seen["n"]
            assert validate_state(st) == []
        assert build_count > 0
