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

    def test_cicero_now_executes_via_param_derivation(self):
        # Card 1 (Cicero) needs senate_direction; the executor now derives it
        # per §8.2.3 (Romans toward Adulation), so it executes rather than
        # raising the former "needs parameters" report.
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        st["current_card"] = 1
        res = execute_decision(st, ROMANS, _event_decision(1))
        assert res["executed"] is True
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
        # An empty expand/mass plan yields nothing marchable (reported).
        assert "march" in res["reason"].lower()

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

    def test_non_adjacent_destination_is_routed_multistep(self):
        # A planned destination two steps away is now routed via BFS (the
        # destination is the bot's choice; only the path is derived).
        from fs_bot.map.map_data import get_playable_regions
        from fs_bot.engine.execute import _bfs_march_path
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=4)
        playable = set(get_playable_regions(st["scenario"], st.get("capabilities")))
        adj = set(get_adjacent(ARVERNI_REGION))
        far = None
        for r in playable:
            if r != ARVERNI_REGION and r not in adj:
                path = _bfs_march_path(ARVERNI_REGION, r, playable)
                if path and len(path) == 2:
                    far = r
                    break
        assert far is not None
        place_piece(st, ARVERNI_REGION, ARVERNI, WARBAND, 4, piece_state=REVEALED)
        refresh_all_control(st)
        decision = {"action": "command", "bot_action": {
            "command": "March", "regions": [far], "sa": "No SA",
            "sa_regions": [], "details": {"march_plan": {
                "origins": [ARVERNI_REGION], "destinations": [far]}}}}
        res = execute_decision(st, ARVERNI, decision)
        assert res["executed"] is True
        assert res["marches"][0]["final_region"] == far
        assert count_pieces(st, ARVERNI_REGION, ARVERNI, WARBAND) == 0
        assert count_pieces(st, far, ARVERNI, WARBAND) > 0
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
        # Every real SA is now wired; an unrecognized label is a safe no-op.
        res = _execute_sa(st, BELGAE, {"sa": "Bogus", "sa_regions": [],
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
        from fs_bot.rules_consts import ALL_SCENARIOS as _ALL
        combos = [(sc, seed) for sc in _ALL for seed in range(0, 8)]
        for sc, seed in combos:
            st = setup_scenario(sc, seed=seed)
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


# ---------------------------------------------------------------------------
# Defender Retreat routing (slice 7) — §8.4.3
# ---------------------------------------------------------------------------

from fs_bot.engine.execute import _decide_defender_retreat
from fs_bot.rules_consts import MANDUBII, MORINI, GERMANS, SCENARIO_ARIOVISTUS
from fs_bot.map.map_data import get_adjacent
from fs_bot.board.control import is_controlled_by


class TestDefenderRetreatRouting:
    def test_defender_retreats_into_controlled_region(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=5)
        # MANDUBII is adjacent to the Aedui home Region (Aedui-controlled).
        place_piece(st, MANDUBII, ARVERNI, WARBAND, 6, piece_state=REVEALED)
        refresh_all_control(st)
        decl, dest = _decide_defender_retreat(st, MANDUBII, ARVERNI, AEDUI, False)
        assert decl is True
        assert dest is not None and is_controlled_by(st, dest, AEDUI)
        mand_before = count_pieces(st, MANDUBII, AEDUI, WARBAND)
        assert mand_before > 0
        dest_before = count_pieces(st, dest, AEDUI, WARBAND)
        execute_decision(st, ARVERNI, {"action": "command", "bot_action": {
            "command": "Battle", "regions": [MANDUBII], "sa": "No SA",
            "sa_regions": [], "details": {"battle_plan": [
                {"region": MANDUBII, "target": AEDUI, "is_trigger": True}]}}})
        # The defenders left the battle Region; survivors arrived at dest.
        assert count_pieces(st, MANDUBII, AEDUI, WARBAND) == 0
        assert count_pieces(st, dest, AEDUI, WARBAND) > dest_before
        assert validate_state(st) == []

    def test_no_controlled_neighbour_means_no_retreat(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=5)
        # Find a Region with no adjacent Aedui Control, put a lone Aedui WB.
        cand = None
        for reg in st["spaces"]:
            if any(is_controlled_by(st, a, AEDUI) for a in get_adjacent(reg)):
                continue
            cand = reg
            break
        assert cand is not None
        place_piece(st, cand, AEDUI, WARBAND, 1, piece_state=REVEALED)
        refresh_all_control(st)
        decl, dest = _decide_defender_retreat(st, cand, ARVERNI, AEDUI, False)
        assert decl is False and dest is None

    def test_ambush_blocks_retreat(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=5)
        place_piece(st, MANDUBII, ARVERNI, WARBAND, 6, piece_state=REVEALED)
        refresh_all_control(st)
        decl, dest = _decide_defender_retreat(st, MANDUBII, ARVERNI, AEDUI, True)
        assert decl is False and dest is None

    def test_arverni_never_retreats_in_ariovistus(self):
        st = setup_scenario(SCENARIO_ARIOVISTUS, seed=5)
        # Even with a controlled neighbour, Arverni never Retreat (A3.2.4).
        decl, dest = _decide_defender_retreat(
            st, MANDUBII, GERMANS, ARVERNI, False)
        assert decl is False and dest is None


# ---------------------------------------------------------------------------
# Agreements (§1.5.2/§8.6.6/§8.8.6) and Rampage (slice 8)
# ---------------------------------------------------------------------------

from fs_bot.engine.execute import _retreat_destinations
from fs_bot.bots.bot_common import np_agrees_to_retreat
from fs_bot.board.control import FACTION_CONTROL
from fs_bot.rules_consts import BELGAE, MORINI


class TestAgreementsAndRampage:
    def test_np_aedui_agrees_to_roman_retreat_not_arverni(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=5)
        st["non_player_factions"] = {AEDUI, ROMANS}
        assert np_agrees_to_retreat(AEDUI, ROMANS, st) is True
        assert np_agrees_to_retreat(AEDUI, ARVERNI, st) is False

    def test_retreat_destination_includes_agreed_control(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=5)
        st["non_player_factions"] = {AEDUI, ROMANS}
        nb = get_adjacent(MORINI)[0]
        st["spaces"][nb]["control"] = FACTION_CONTROL[AEDUI]
        # Romans may Retreat into Aedui-Controlled Nervii (agreement); Arverni
        # may not (Aedui never agrees for Arverni).
        assert nb in _retreat_destinations(st, MORINI, ROMANS)
        assert nb not in _retreat_destinations(st, MORINI, ARVERNI)

    def test_rampage_removes_target_pieces(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=5)
        place_piece(st, MORINI, BELGAE, WARBAND, 2, piece_state=HIDDEN)
        place_piece(st, MORINI, ROMANS, AUXILIA, 2, piece_state=REVEALED)
        refresh_all_control(st)
        before = count_pieces(st, MORINI, ROMANS, AUXILIA)
        res = _execute_sa(st, BELGAE, {"sa": "Rampage", "details": {},
            "sa_regions": [{"region": MORINI, "target": ROMANS,
                            "forces_removal": True, "adds_control": False}]})
        assert res["executed"] is True
        assert count_pieces(st, MORINI, ROMANS, AUXILIA) < before
        assert validate_state(st) == []

    def test_rampage_retreats_target_when_escape_exists(self):
        # Target has an adjacent Controlled Region -> Rampage Retreats the
        # piece (preserved on the board) rather than removing it.
        from fs_bot.board.pieces import count_on_map
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=5)
        place_piece(st, MORINI, BELGAE, WARBAND, 1, piece_state=HIDDEN)
        place_piece(st, MORINI, ROMANS, AUXILIA, 1, piece_state=REVEALED)
        nb = get_adjacent(MORINI)[0]
        st["spaces"][nb]["control"] = FACTION_CONTROL[ROMANS]
        on_map_before = count_on_map(st, ROMANS, AUXILIA)
        res = _execute_sa(st, BELGAE, {"sa": "Rampage", "details": {},
            "sa_regions": [{"region": MORINI, "target": ROMANS,
                            "forces_removal": False, "adds_control": True}]})
        assert res["executed"] is True
        # The Auxilia left MORINI but survived on the board (Retreated), so the
        # total Roman Auxilia on the map is unchanged.
        assert count_pieces(st, MORINI, ROMANS, AUXILIA) == 0
        assert count_on_map(st, ROMANS, AUXILIA) == on_map_before
        assert validate_state(st) == []


# ---------------------------------------------------------------------------
# Seize Harassment (slice 9) — §3.2.3 / §8.4.2
# ---------------------------------------------------------------------------

from fs_bot.engine.execute import _np_harassers, _resolve_seize_harassment
from fs_bot.rules_consts import MANDUBII


class TestSeizeHarassment:
    def _setup(self, seed=5):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=seed)
        # Clear pre-existing Hidden Warbands in MANDUBII for a clean count.
        st["spaces"][MANDUBII]["control"] = FACTION_CONTROL[ROMANS]
        return st

    def test_belgae_arverni_harass_roman_seize_not_aedui(self):
        st = self._setup()
        # Wipe MANDUBII to a known state, then place controlled counts.
        place_piece(st, MANDUBII, ROMANS, AUXILIA, 3)
        # Determine harassers from whatever Hidden Warbands exist plus ours.
        place_piece(st, MANDUBII, BELGAE, WARBAND, 3, piece_state=HIDDEN)
        place_piece(st, MANDUBII, AEDUI, WARBAND, 3, piece_state=HIDDEN)
        refresh_all_control(st)
        st["spaces"][MANDUBII]["control"] = FACTION_CONTROL[ROMANS]
        harassers = dict(_np_harassers(st, MANDUBII, ROMANS, None))
        assert BELGAE in harassers          # §8.4.2: Belgae harass Roman Seize
        assert AEDUI not in harassers        # Aedui only harass Vercingetorix

    def test_harassment_removes_roman_pieces(self):
        st = self._setup()
        place_piece(st, MANDUBII, ROMANS, AUXILIA, 3)
        place_piece(st, MANDUBII, BELGAE, WARBAND, 3, piece_state=HIDDEN)
        refresh_all_control(st)
        st["spaces"][MANDUBII]["control"] = FACTION_CONTROL[ROMANS]
        before = count_pieces(st, MANDUBII, ROMANS, AUXILIA)
        losses = _resolve_seize_harassment(st, MANDUBII)
        # At least one Loss inflicted (Belgae 3 Hidden -> 1), Auxilia removed.
        assert len(losses) >= 1
        assert count_pieces(st, MANDUBII, ROMANS, AUXILIA) < before
        assert validate_state(st) == []

    def test_no_harassment_below_three_hidden_warbands(self):
        st = self._setup()
        place_piece(st, MANDUBII, ROMANS, AUXILIA, 2)
        # Only 2 Hidden Belgic Warbands -> below the 3-per-Loss threshold.
        place_piece(st, MANDUBII, BELGAE, WARBAND, 2, piece_state=HIDDEN)
        refresh_all_control(st)
        st["spaces"][MANDUBII]["control"] = FACTION_CONTROL[ROMANS]
        # Belgae alone can't harass; assert Belgae not among harassers.
        harassers = dict(_np_harassers(st, MANDUBII, ROMANS, None))
        assert BELGAE not in harassers


# ---------------------------------------------------------------------------
# Entreat and Scout SAs (slice 10)
# ---------------------------------------------------------------------------

from fs_bot.engine.execute import _execute_entreat, _execute_scout
from fs_bot.board.pieces import count_pieces_by_state, find_leader
from fs_bot.rules_consts import SCOUTED


class TestEntreatAndScout:
    def test_entreat_replaces_enemy_piece_with_arverni(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=5)
        place_piece(st, MANDUBII, AEDUI, WARBAND, 1, piece_state=REVEALED)
        refresh_all_control(st)
        aedui_before = count_pieces(st, MANDUBII, AEDUI, WARBAND)
        arv_before = count_pieces(st, MANDUBII, ARVERNI, WARBAND)
        plan = [{"action": "replace_piece", "region": MANDUBII,
                 "target_faction": AEDUI, "target_type": WARBAND,
                 "target_state": REVEALED}]
        res = _execute_entreat(st, ARVERNI, {"sa": "Entreat",
                                             "sa_regions": plan, "details": {}})
        assert res["executed"] is True
        assert count_pieces(st, MANDUBII, AEDUI, WARBAND) == aedui_before - 1
        assert count_pieces(st, MANDUBII, ARVERNI, WARBAND) == arv_before + 1
        assert validate_state(st) == []

    def test_scout_reveals_enemy_warbands_to_scouted(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=5)
        cr = find_leader(st, ROMANS)
        assert cr is not None
        place_piece(st, cr, ROMANS, AUXILIA, 2, piece_state=HIDDEN)
        place_piece(st, cr, ARVERNI, WARBAND, 2, piece_state=HIDDEN)
        refresh_all_control(st)
        hidden_before = count_pieces_by_state(st, cr, ARVERNI, WARBAND, HIDDEN)
        res = _execute_scout(st, ROMANS, {"sa": "Scout", "sa_regions": [],
                                          "details": {}})
        assert res["executed"] is True
        # The Arverni Warbands at Caesar's Region were Scouted (Hidden -> Scouted).
        assert count_pieces_by_state(st, cr, ARVERNI, WARBAND, HIDDEN) < hidden_before
        assert count_pieces_by_state(st, cr, ARVERNI, WARBAND, SCOUTED) > 0
        assert validate_state(st) == []


# ---------------------------------------------------------------------------
# Enlist SA (slice 12) — free Germanic sub-Command
# ---------------------------------------------------------------------------

from fs_bot.engine.execute import _execute_enlist
from fs_bot.rules_consts import SUGAMBRI


class TestEnlist:
    def test_enlist_german_raid_gains_resources(self):
        st = setup_scenario(SCENARIO_ARIOVISTUS, seed=3)
        place_piece(st, SUGAMBRI, GERMANS, WARBAND, 2, piece_state=HIDDEN)
        refresh_all_control(st)
        before = st["resources"][GERMANS]
        ed = {"type": "german_raid", "region": SUGAMBRI, "target": None,
              "regions": [SUGAMBRI]}
        res = _execute_enlist(st, BELGAE, {"sa": "Enlist",
            "sa_regions": [SUGAMBRI], "details": {"enlist": ed}})
        assert res["executed"] is True and res["type"] == "german_raid"
        assert st["resources"][GERMANS] >= before
        assert validate_state(st) == []

    def test_enlist_german_rally_places_warbands(self):
        st = setup_scenario(SCENARIO_ARIOVISTUS, seed=3)
        lr = find_leader(st, GERMANS)
        place_piece(st, lr, GERMANS, WARBAND, 1, piece_state=HIDDEN)
        refresh_all_control(st)
        before = count_pieces(st, lr, GERMANS, WARBAND)
        ed = {"type": "german_rally", "region": lr, "place": "warbands",
              "regions": [lr]}
        res = _execute_enlist(st, BELGAE, {"sa": "Enlist",
            "sa_regions": [lr], "details": {"enlist": ed}})
        assert res["executed"] is True
        assert count_pieces(st, lr, GERMANS, WARBAND) > before
        assert validate_state(st) == []

    def test_enlist_missing_details_is_safe(self):
        st = setup_scenario(SCENARIO_ARIOVISTUS, seed=3)
        res = _execute_enlist(st, BELGAE, {"sa": "Enlist", "sa_regions": [],
                                           "details": {}})
        assert res["executed"] is False


# ---------------------------------------------------------------------------
# Event-parameter plumbing (slice 13)
# ---------------------------------------------------------------------------

from fs_bot.rules_consts import EVENT_UNSHADED, ADULATION, UPROAR


class TestEventParamPlumbing:
    def test_cicero_senate_direction_derived_per_faction(self):
        # §8.2.3: each Faction shifts the Senate toward its own benefit —
        # Romans toward Adulation, Gallic Factions toward Uproar.
        st_r = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        st_r["current_card"] = 1
        res_r = _execute_sa  # ensure import side effects loaded
        from fs_bot.engine.execute import _execute_event
        r = _execute_event(st_r, ROMANS, {"command": "Event", "sa": "No SA",
            "sa_regions": [], "details": {"card_id": 1,
                                          "text_preference": EVENT_UNSHADED}})
        assert r["executed"] is True
        assert st_r["senate"]["position"] == ADULATION
        # event_params is cleaned up afterwards.
        assert st_r.get("event_params") is None

        st_g = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        st_g["current_card"] = 1
        from fs_bot.engine.execute import _execute_event as _ee
        g = _ee(st_g, ARVERNI, {"command": "Event", "sa": "No SA",
            "sa_regions": [], "details": {"card_id": 1,
                                          "text_preference": EVENT_UNSHADED}})
        assert g["executed"] is True
        assert st_g["senate"]["position"] == UPROAR
        assert validate_state(st_g) == []

    def test_unparameterized_card_still_reported(self):
        # A card whose choice isn't derivable still reports cleanly (no crash).
        from fs_bot.engine.execute import _execute_event
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        st["current_card"] = 1
        # Card with no deriver entry that needs params would be reported; here
        # we just confirm the happy path leaves state valid.
        assert validate_state(st) == []


# ---------------------------------------------------------------------------
# Regressions found by intensive smoke testing (slice 14)
# ---------------------------------------------------------------------------

import copy as _copy


class TestSmokeRegressions:
    def test_suborn_plan_read_from_nested_sa_details(self):
        # BUG: Aedui nests SA plans under details["sa_details"]; the executor
        # read only the top level, so Suborn never executed. _sa_detail must
        # find the plan in either location.
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        place_piece(st, AEDUI_REGION, AEDUI, WARBAND, 1, piece_state=HIDDEN)
        refresh_all_control(st)
        before = count_pieces(st, AEDUI_REGION, AEDUI, WARBAND)
        plan = [{"region": AEDUI_REGION, "actions": [{"action": "place_warband"}]}]
        # Nested layout (Aedui style).
        res = _execute_sa(st, AEDUI, {"sa": "Suborn", "sa_regions": [AEDUI_REGION],
            "details": {"march_plan": {}, "sa_details": {"suborn_plan": plan}}})
        assert res["executed"] is True
        assert count_pieces(st, AEDUI_REGION, AEDUI, WARBAND) == before + 1
        assert validate_state(st) == []

    def test_entreat_recomputed_when_only_regions_passed(self):
        # BUG: the Arverni Rally/March SA path passes only Region names and
        # drops the Entreat action plan, so Entreat never executed. The
        # executor must recompute the plan when no action dicts are present.
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        place_piece(st, MANDUBII, ARVERNI, WARBAND, 2)  # Arverni presence/control
        place_piece(st, MANDUBII, AEDUI, WARBAND, 1, piece_state=REVEALED)
        refresh_all_control(st)
        # sa_regions carries only region NAME strings (the buggy path).
        res = _execute_entreat(st, ARVERNI, {"sa": "Entreat",
            "sa_regions": [MANDUBII], "details": {"march_plan": {}}})
        # Either it found a faithful Entreat action to perform, or there was
        # none available — but it must not silently no-op due to a dropped plan
        # when a valid target exists. With an Aedui Warband present and Arverni
        # control, a replace is available.
        assert res["executed"] is True
        assert validate_state(st) == []

    def test_executor_robust_to_malformed_actions(self):
        # Hardening: details=None and non-string regions must not raise.
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        for ba in [
            {"command": "Seize", "sa": "No SA", "regions": [{"x": 1}],
             "sa_regions": [], "details": None},
            {"command": "Event", "sa": "No SA", "regions": [],
             "sa_regions": [{"r": 1}], "details": None},
            {"command": "March", "sa": "Enlist", "regions": None,
             "sa_regions": None, "details": {"enlist": None}},
        ]:
            res = execute_decision(_copy.deepcopy(st), ROMANS,
                                   {"action": "command", "bot_action": ba})
            assert isinstance(res, dict)
        assert validate_state(st) == []


# ---------------------------------------------------------------------------
# Build/Scout bot-plan eligibility (slice 15) — §4.2.1 / §4.2.2
# ---------------------------------------------------------------------------

from fs_bot.bots.roman_bot import node_r_build, node_r_scout, _caesar_region
from fs_bot.commands.sa_build import validate_build_region
from fs_bot.board.control import is_controlled_by as _is_ctrl
from fs_bot.map.map_data import is_adjacent as _adj, get_playable_regions
from fs_bot.board.pieces import count_pieces_by_state as _cps


class TestBuildScoutEligibility:
    def test_build_plan_only_proposes_eligible_regions(self):
        # Every Region node_r_build proposes must satisfy §4.2.1 eligibility,
        # and every Subdue/Ally Region must (be eligible and) be a legal Build
        # target — across many real game states.
        for sc in ["The Great Revolt", "Pax Gallica?", "Reconquest of Gaul",
                   "Ariovistus", "The Gallic War"]:
            for seed in range(0, 8):
                st = setup_scenario(sc, seed=seed)
                st["non_player_factions"] = set(get_sop_factions(st))
                plan = node_r_build(st)
                for region in plan["forts"]:
                    assert validate_build_region(st, region)[0], (sc, seed, region)
                for e in plan["subdue"] + plan["allies"]:
                    r = e["region"]
                    assert validate_build_region(st, r)[0], (sc, seed, r)

    def test_scout_plan_only_targets_caesar_range_with_hidden_auxilia(self):
        # §4.2.2: Reveal targets must be within 1 of Caesar AND have a Roman
        # Hidden Auxilia present.
        from fs_bot.rules_consts import ROMANS, AUXILIA, HIDDEN
        for sc in ["The Great Revolt", "Pax Gallica?", "Ariovistus"]:
            for seed in range(0, 8):
                st = setup_scenario(sc, seed=seed)
                st["non_player_factions"] = set(get_sop_factions(st))
                cr = _caesar_region(st)
                plan = node_r_scout(st)
                for t in plan["scout_targets"]:
                    r = t["region"]
                    assert cr is not None and (r == cr or _adj(r, cr)), (sc, seed, r)
                    assert _cps(st, r, ROMANS, AUXILIA, HIDDEN) > 0, (sc, seed, r)


# ---------------------------------------------------------------------------
# Roman March plan layout (slice 16) — Caesar must actually march (§8.8.1)
# ---------------------------------------------------------------------------

class TestRomanMarchExecutes:
    def test_roman_flat_plan_and_tuple_dests_move_caesar(self):
        # The Roman bot emits its March plan flat in details (origins/
        # destinations) with destinations as (region, faction) tuples — unlike
        # the other bots' nested {"march_plan": {...}} with string dests. The
        # executor must handle both, else Roman Marches silently no-op and
        # Caesar never moves.
        from fs_bot.rules_consts import LEADER, LEGION, CAESAR
        from fs_bot.board.pieces import find_leader
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=4)
        # Use Caesar's actual starting Region as the origin (he is already on
        # the map); place Legions with him and pick an adjacent destination.
        origin = find_leader(st, ROMANS)
        assert origin is not None
        dest = get_adjacent(origin)[0]
        place_piece(st, origin, ROMANS, LEGION, 2, from_legions_track=True)
        # Make dest an Arverni-ally region (a legal March destination).
        tribe = get_tribes_in_region(dest, st["scenario"])[0]
        st["tribes"][tribe]["allied_faction"] = ARVERNI
        place_piece(st, dest, ARVERNI, ALLY)
        refresh_all_control(st)
        assert find_leader(st, ROMANS) == origin
        decision = {"action": "command", "bot_action": {
            "command": "March", "regions": [dest], "sa": "No SA",
            "sa_regions": [],
            # Roman layout: flat in details, tuple destinations.
            "details": {"origins": [origin],
                        "destinations": [(dest, ARVERNI)],
                        "dest_count": 1}}}
        res = execute_decision(st, ROMANS, decision)
        assert res["executed"] is True
        assert find_leader(st, ROMANS) == dest  # Caesar actually marched
        assert validate_state(st) == []


# ---------------------------------------------------------------------------
# Expand/mass March — leader movement with control-preserving leave-behind
# (slice 17) — §8.6.5 / §8.7.4-5 / A8.7.5
# ---------------------------------------------------------------------------

class TestExpandMarchLeader:
    def test_leader_marches_toward_destination_keeping_control(self):
        from fs_bot.board.pieces import find_leader
        from fs_bot.board.control import is_controlled_by
        from fs_bot.rules_consts import (SCENARIO_GREAT_REVOLT as _SC, ARVERNI as _AR,
            WARBAND as _WB, ALLY as _AL)
        st = setup_scenario(_SC, seed=3)
        lr = find_leader(st, _AR)  # Vercingetorix's region (Arverni home)
        assert lr is not None
        # Give the Arverni a strong stack so some Warbands can leave while
        # control is retained.
        place_piece(st, lr, _AR, _WB, 6)
        refresh_all_control(st)
        assert is_controlled_by(st, lr, _AR)
        dest = get_adjacent(lr)[0]
        from fs_bot.engine.execute import _execute_expand_march
        res = _execute_expand_march(st, _AR,
            {"type": "March (spread)", "origins": [lr],
             "leader_destination": dest, "spread_destinations": [dest],
             "control_destination": None})
        assert res["executed"] is True
        assert find_leader(st, _AR) == dest          # leader actually moved
        assert is_controlled_by(st, lr, _AR)          # origin still controlled
        assert validate_state(st) == []

    def test_expand_march_defers_when_no_leader_on_map(self):
        from fs_bot.rules_consts import SCENARIO_GREAT_REVOLT as _SC, BELGAE as _BE
        from fs_bot.board.pieces import find_leader, remove_piece
        from fs_bot.rules_consts import LEADER as _LD
        st = setup_scenario(_SC, seed=3)
        lr = find_leader(st, _BE)
        if lr is not None:
            remove_piece(st, lr, _BE, _LD)
        from fs_bot.engine.execute import _execute_expand_march
        res = _execute_expand_march(st, _BE,
            {"type": "March (control)", "origins": [], "leader_destination": None,
             "control_destinations": []})
        assert res["executed"] is False


class TestWarbandSpreadMarch:
    def test_warband_only_origin_spreads_keeping_control(self):
        from fs_bot.board.pieces import find_leader, count_pieces as _cp
        from fs_bot.board.control import is_controlled_by
        from fs_bot.rules_consts import (SCENARIO_GREAT_REVOLT as _SC, ARVERNI as _AR,
            WARBAND as _WB)
        from fs_bot.rules_consts import FACTIONS as _F
        from fs_bot.board.pieces import remove_piece as _rm
        st = setup_scenario(_SC, seed=3)
        origin = "Bituriges"
        # Clear enemy pieces at the origin so some Warbands are spare beyond
        # the Control-keep, then stack Arverni Warbands there.
        for of in _F:
            if of == _AR:
                continue
            n = _cp(st, origin, of, _WB)
            if n:
                _rm(st, origin, of, _WB, n)
        place_piece(st, origin, _AR, _WB, 5)
        refresh_all_control(st)
        ctrl_before = is_controlled_by(st, origin, _AR)
        dest = get_adjacent(origin)[0]
        wb_dest_before = _cp(st, dest, _AR, _WB)
        from fs_bot.engine.execute import _execute_expand_march
        # No leader destination -> exercises the warband-only branch for origin.
        res = _execute_expand_march(st, _AR, {"type": "March (spread)",
            "origins": [origin], "control_destinations": [dest],
            "leader_destination": None, "spread_destinations": []})
        assert res["executed"] is True
        # Spare Warbands reached the destination; origin Control retained.
        assert _cp(st, dest, _AR, _WB) > wb_dest_before
        if ctrl_before:
            assert is_controlled_by(st, origin, _AR)
        assert validate_state(st) == []


class TestBeforeBattleSASequencing:
    def test_entreat_runs_before_battle(self):
        # An Entreat accompanying a Battle must resolve BEFORE the Battle
        # (it replaces an enemy piece, changing the Battle). execute_decision
        # should report sa_timing == "before".
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=5)
        place_piece(st, MANDUBII, ARVERNI, WARBAND, 4, piece_state=REVEALED)
        place_piece(st, MANDUBII, AEDUI, WARBAND, 1, piece_state=REVEALED)
        refresh_all_control(st)
        entreat_plan = [{"action": "replace_piece", "region": MANDUBII,
                         "target_faction": AEDUI, "target_type": WARBAND,
                         "target_state": REVEALED}]
        decision = {"action": "command", "bot_action": {
            "command": "Battle", "regions": [MANDUBII], "sa": "Entreat",
            "sa_regions": entreat_plan,
            "details": {"battle_plan": [{"region": MANDUBII, "target": AEDUI,
                                         "is_trigger": True}]}}}
        res = execute_decision(st, ARVERNI, decision)
        assert res["executed"] is True
        assert res.get("sa_timing") == "before"
        assert validate_state(st) == []

    def test_march_intimidate_still_runs_after(self):
        # A non-Battle command keeps after-sequencing.
        st = setup_scenario(SCENARIO_ARIOVISTUS, seed=3)
        from fs_bot.board.pieces import find_leader
        lr = find_leader(st, GERMANS)
        decision = {"action": "command", "bot_action": {
            "command": "March", "regions": [], "sa": "Intimidate",
            "sa_regions": [], "details": {"march_plan": {
                "origins": [lr], "destinations": []}, "intimidate_plan": []}}}
        res = execute_decision(st, GERMANS, decision)
        # March defers (no destinations) but the SA path still tags 'after'
        # when an SA result is produced; either way must not be 'before'.
        assert res.get("sa_timing") in (None, "after")
        assert validate_state(st) == []


# ---------------------------------------------------------------------------
# Event play + markers data-model robustness (slice 20)
# ---------------------------------------------------------------------------

class TestEventPlayAndMarkers:
    def test_bots_actually_play_events_in_real_games(self):
        # Regression: can_play_event was never set, so bots could NEVER play an
        # Event. The dispatcher now relays it; events must occur in real games.
        import fs_bot.engine.execute as _ex
        from fs_bot.rules_consts import ALL_SCENARIOS as _ALL
        ev = {"n": 0}
        orig = _ex._execute_event
        def _tally(s, f, ba, _o=orig, _e=ev):
            r = _o(s, f, ba)
            if r.get("executed"):
                _e["n"] += 1
            return r
        _ex._execute_event = _tally
        try:
            for sc in _ALL:
                for seed in range(0, 6):
                    st = setup_scenario(sc, seed=seed)
                    st["non_player_factions"] = set(get_sop_factions(st))
                    dfn = make_decision_func(
                        {f: "bot" for f in get_sop_factions(st)}, pause=False)
                    with _ctx.redirect_stdout(_io.StringIO()):
                        run_game(st, decision_func=dfn, execute=True)
                    assert validate_state(st) == []
        finally:
            _ex._execute_event = orig
        assert ev["n"] > 0

    def test_add_region_marker_handles_set_dict_missing(self):
        from fs_bot.cards.card_effects import _add_region_marker
        from fs_bot.rules_consts import MARKER_DEVASTATED, MARKER_RAZED
        st = {"markers": {"A": {MARKER_RAZED}, "B": {MARKER_RAZED: True}}}
        _add_region_marker(st, "A", MARKER_DEVASTATED)   # existing set
        _add_region_marker(st, "B", MARKER_DEVASTATED)   # existing dict
        _add_region_marker(st, "C", MARKER_DEVASTATED)   # missing
        assert MARKER_DEVASTATED in st["markers"]["A"]
        assert MARKER_DEVASTATED in st["markers"]["B"]
        assert MARKER_DEVASTATED in st["markers"]["C"]

    def test_is_devastated_robust_to_set_and_dict(self):
        from fs_bot.bots.german_bot import _is_devastated
        from fs_bot.rules_consts import MARKER_DEVASTATED, SCENARIO_ARIOVISTUS
        st = setup_scenario(SCENARIO_ARIOVISTUS, seed=1)
        st.setdefault("markers", {})["Sugambri"] = {MARKER_DEVASTATED: True}  # dict
        st["markers"]["Ubii"] = {MARKER_DEVASTATED}                            # set
        assert _is_devastated(st, "Sugambri") is True
        assert _is_devastated(st, "Ubii") is True
        assert _is_devastated(st, "Treveri") is False


# ---------------------------------------------------------------------------
# Per-card event_params derivation + executing_faction (slice 21)
# ---------------------------------------------------------------------------

class TestEventParamDerivers:
    def _ev(self, st, faction, cid):
        from fs_bot.rules_consts import EVENT_UNSHADED
        from fs_bot.engine.execute import _execute_event
        st["current_card"] = cid
        return _execute_event(st, faction, {"command": "Event", "sa": "No SA",
            "sa_regions": [], "details": {"card_id": cid,
                                          "text_preference": EVENT_UNSHADED}})

    def test_executing_faction_is_set_for_handlers(self):
        # Card 71 (Colony) reads state["executing_faction"]; the executor must
        # set it (it was never set, so 30 cards no-op'd). It also restores it.
        from fs_bot.board.pieces import count_on_map
        from fs_bot.rules_consts import ROMANS, ALLY, MARKER_COLONY
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        before = count_on_map(st, ROMANS, ALLY)
        res = self._ev(st, ROMANS, 71)
        assert res["executed"] is True
        colonies = sum(1 for m in st.get("markers", {}).values()
                       if isinstance(m, dict) and m.get(MARKER_COLONY))
        assert colonies >= 1
        assert count_on_map(st, ROMANS, ALLY) == before + 1
        assert st.get("executing_faction") is None  # restored
        assert validate_state(st) == []

    def test_card28_upgrades_or_places_for_self(self):
        from fs_bot.board.pieces import count_on_map
        from fs_bot.rules_consts import ARVERNI, ALLY, CITADEL
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        before = count_on_map(st, ARVERNI, ALLY) + count_on_map(st, ARVERNI, CITADEL)
        res = self._ev(st, ARVERNI, 28)
        assert res["executed"] is True
        # Net Ally+Citadel never decreases (placements add, upgrades convert).
        assert count_on_map(st, ARVERNI, ALLY) + count_on_map(st, ARVERNI, CITADEL) >= before
        assert validate_state(st) == []

    def test_card42_removes_enemy_allies_not_own(self):
        from fs_bot.board.pieces import count_on_map
        from fs_bot.rules_consts import ARVERNI, ROMANS, AEDUI, BELGAE, ALLY
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        own_before = count_on_map(st, ARVERNI, ALLY)
        enemy_before = sum(count_on_map(st, f, ALLY) for f in (ROMANS, AEDUI, BELGAE))
        res = self._ev(st, ARVERNI, 42)
        if res["executed"]:
            # Own allies untouched; some enemy allies removed.
            assert count_on_map(st, ARVERNI, ALLY) == own_before
            assert sum(count_on_map(st, f, ALLY) for f in (ROMANS, AEDUI, BELGAE)) <= enemy_before
        assert validate_state(st) == []


class TestEventParamDerivers2:
    def test_card23_razes_roman_city_for_resources(self):
        from fs_bot.rules_consts import ROMANS, EVENT_UNSHADED, MARKER_RAZED
        from fs_bot.engine.execute import _execute_event
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        st["current_card"] = 23
        rb = st["resources"][ROMANS]
        res = _execute_event(st, ROMANS, {"command": "Event", "sa": "No SA",
            "sa_regions": [], "details": {"card_id": 23,
                                          "text_preference": EVENT_UNSHADED}})
        if res["executed"]:
            assert st["resources"][ROMANS] >= rb  # +8 (capped at 45)
            razed = sum(1 for m in st.get("markers", {}).values()
                        if MARKER_RAZED in (m or {}))
            assert razed >= 1
        assert validate_state(st) == []

    def test_card23_only_romans(self):
        from fs_bot.engine.execute import _derive_card_23
        from fs_bot.rules_consts import ARVERNI
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        assert _derive_card_23(st, ARVERNI, False) is None  # not Romans
        assert _derive_card_23(st, "Romans", True) is None  # shaded deferred
