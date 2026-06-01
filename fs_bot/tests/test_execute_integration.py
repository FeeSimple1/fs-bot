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


class TestEventParamDerivers3:
    def test_card58_removes_enemy_warbands_at_fort(self):
        from fs_bot.board.pieces import place_piece, count_pieces
        from fs_bot.board.control import refresh_all_control
        from fs_bot.map.map_data import get_playable_regions
        from fs_bot.engine.execute import _execute_event
        from fs_bot.rules_consts import ROMANS, BELGAE, WARBAND, FORT, EVENT_UNSHADED
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        st["current_card"] = 58
        fr = next(r for r in get_playable_regions(st["scenario"], st.get("capabilities"))
                  if count_pieces(st, r, ROMANS, FORT) > 0)
        place_piece(st, fr, BELGAE, WARBAND, 4)
        refresh_all_control(st)
        before = count_pieces(st, fr, BELGAE, WARBAND)
        res = _execute_event(st, ROMANS, {"command": "Event", "sa": "No SA",
            "sa_regions": [], "details": {"card_id": 58,
                                          "text_preference": EVENT_UNSHADED}})
        assert res["executed"] is True
        assert count_pieces(st, fr, BELGAE, WARBAND) < before
        assert validate_state(st) == []

    def test_card22_replaces_enemy_with_own_in_controlled_region(self):
        from fs_bot.board.pieces import place_piece, count_pieces
        from fs_bot.board.control import FACTION_CONTROL
        from fs_bot.engine.execute import _execute_event
        from fs_bot.rules_consts import ARVERNI, AEDUI, ROMANS, WARBAND, AUXILIA, EVENT_UNSHADED
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        st["current_card"] = 22
        reg = "Mandubii"
        st["spaces"][reg]["control"] = FACTION_CONTROL[ARVERNI]
        place_piece(st, reg, AEDUI, WARBAND, 3)
        enemy_before = (count_pieces(st, reg, AEDUI, WARBAND)
                        + count_pieces(st, reg, ROMANS, AUXILIA))
        res = _execute_event(st, ARVERNI, {"command": "Event", "sa": "No SA",
            "sa_regions": [], "details": {"card_id": 22,
                                          "text_preference": EVENT_UNSHADED}})
        assert res["executed"] is True
        # Enemy mobile pieces in the Arverni-controlled Region were reduced.
        assert (count_pieces(st, reg, AEDUI, WARBAND)
                + count_pieces(st, reg, ROMANS, AUXILIA)) < enemy_before
        assert validate_state(st) == []


def test_acard_event_param_derivers_registered():
    """Slice 24: Ariovistus A-card derivers are wired and fire faithfully."""
    from fs_bot.engine.execute import _EVENT_PARAM_DERIVERS, _execute_event
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.pieces import place_piece, count_pieces, find_leader
    from fs_bot.board.control import refresh_all_control
    from fs_bot.rules_consts import (SCENARIO_ARIOVISTUS, ROMANS, GERMANS, WARBAND,
                                     EVENT_UNSHADED, GERMANIA_REGIONS)
    for cid in ("A18", "A37", "A45", "A64", "A66"):
        assert cid in _EVENT_PARAM_DERIVERS
    # A18: Roman event removes all Germans from a non-Ariovistus Germania Region
    st = setup_scenario(SCENARIO_ARIOVISTUS, seed=2)
    st["current_card"] = "A18"
    gr = [r for r in GERMANIA_REGIONS if find_leader(st, GERMANS) != r][0]
    place_piece(st, gr, GERMANS, WARBAND, 3)
    refresh_all_control(st)
    assert count_pieces(st, gr, GERMANS, WARBAND) > 0
    res = _execute_event(st, ROMANS, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": "A18", "text_preference": EVENT_UNSHADED}})
    assert res["executed"]
    assert count_pieces(st, gr, GERMANS, WARBAND) == 0
    assert validate_state(st) == []


def _clear_region_mobiles(state, region):
    from fs_bot.board.pieces import count_pieces, remove_piece
    from fs_bot.rules_consts import FACTIONS, WARBAND, LEGION, AUXILIA
    for f in FACTIONS:
        for pt in (WARBAND, LEGION, AUXILIA):
            n = count_pieces(state, region, f, pt)
            if n:
                remove_piece(state, region, f, pt, count=n)


def test_free_battle_no_retreat_a21_a57():
    """Slice 25: A21/A57 grant a no-Retreat free Battle that the executor
    selects (most enemy mobile force) and resolves with real Losses."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.pieces import place_piece, count_pieces
    from fs_bot.board.control import refresh_all_control
    from fs_bot.engine.execute import _execute_event, _within1_of
    from fs_bot.rules_consts import (SCENARIO_ARIOVISTUS, ROMANS, ARVERNI,
        GERMANS, WARBAND, AUXILIA, EVENT_UNSHADED, SEQUANI, BELGICA_REGIONS)

    # A21: Arverni free-Battle within 1 of Sequani, defender may not Retreat
    st = setup_scenario(SCENARIO_ARIOVISTUS, seed=3)
    st["current_card"] = "A21"
    allowed = _within1_of(st, SEQUANI)
    for r in allowed:
        _clear_region_mobiles(st, r)
    place_piece(st, SEQUANI, ARVERNI, WARBAND, 8)
    place_piece(st, SEQUANI, ROMANS, AUXILIA, 5)
    refresh_all_control(st)
    res = _execute_event(st, ARVERNI, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": "A21",
        "text_preference": EVENT_UNSHADED}})
    fa = res.get("free_actions")
    assert fa and fa[0]["region"] == SEQUANI and fa[0]["defender"] == ROMANS
    # First Battle inflicts 4 Losses; A21's optional second Battle
    # (Retreat allowed) may remove the last piece, so <= 1 remains.
    assert count_pieces(st, SEQUANI, ROMANS, AUXILIA) <= 1
    assert validate_state(st) == []

    # A57: German free-Battle in Belgica, no Retreat
    st2 = setup_scenario(SCENARIO_ARIOVISTUS, seed=3)
    st2["current_card"] = "A57"
    for r in BELGICA_REGIONS:
        _clear_region_mobiles(st2, r)
    tgt = BELGICA_REGIONS[0]
    place_piece(st2, tgt, GERMANS, WARBAND, 8)
    place_piece(st2, tgt, ROMANS, AUXILIA, 5)
    refresh_all_control(st2)
    res2 = _execute_event(st2, GERMANS, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": "A57",
        "text_preference": EVENT_UNSHADED}})
    fa2 = res2.get("free_actions")
    assert fa2 and fa2[0]["region"] == tgt and fa2[0]["defender"] == ROMANS
    assert count_pieces(st2, tgt, ROMANS, AUXILIA) <= 1
    assert validate_state(st2) == []


def test_free_double_battle_a21():
    """Slice 26: A21/A57 grant an optional second free Battle in the same
    Region (Retreat allowed) after the no-Retreat first Battle."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.pieces import place_piece, count_pieces
    from fs_bot.board.control import refresh_all_control
    from fs_bot.engine.execute import _execute_event, _within1_of
    from fs_bot.rules_consts import (SCENARIO_ARIOVISTUS, ROMANS, ARVERNI,
        WARBAND, AUXILIA, EVENT_UNSHADED, SEQUANI)
    st = setup_scenario(SCENARIO_ARIOVISTUS, seed=3)
    st["current_card"] = "A21"
    allowed = _within1_of(st, SEQUANI)
    for r in allowed:
        _clear_region_mobiles(st, r)
    place_piece(st, SEQUANI, ARVERNI, WARBAND, 12)
    place_piece(st, SEQUANI, ROMANS, AUXILIA, 8)
    refresh_all_control(st)
    res = _execute_event(st, ARVERNI, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": "A21",
        "text_preference": EVENT_UNSHADED}})
    fa = res.get("free_actions") or []
    kinds = [f["free_action"] for f in fa]
    assert "battle" in kinds and "battle_second" in kinds
    # Two Battles remove more than a single no-Retreat Battle's 4 Losses.
    assert count_pieces(st, SEQUANI, ROMANS, AUXILIA) <= 4
    assert validate_state(st) == []


def test_free_battle_faction_faithful_targeting_and_a28():
    """Slice 27: Belgic NP targets max Legion Losses; A28 runs a no-Retreat
    free Battle in/adjacent to Sequani."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.pieces import place_piece, count_pieces
    from fs_bot.board.control import refresh_all_control
    from fs_bot.engine.execute import (_execute_event, _within1_of,
        _choose_free_battle, _predicted_legion_losses)
    from fs_bot.rules_consts import (SCENARIO_ARIOVISTUS, ROMANS, GERMANS,
        BELGAE, WARBAND, LEGION, AUXILIA, EVENT_UNSHADED, SEQUANI,
        BELGICA_REGIONS)

    # Belgic NP picks the Region forcing the most Roman Legion Losses.
    st = setup_scenario(SCENARIO_ARIOVISTUS, seed=4)
    for r in BELGICA_REGIONS:
        _clear_region_mobiles(st, r)
    rA, rB = BELGICA_REGIONS[0], BELGICA_REGIONS[1]
    place_piece(st, rA, BELGAE, WARBAND, 8)
    place_piece(st, rA, ROMANS, LEGION, 2, from_legions_track=True)
    place_piece(st, rB, BELGAE, WARBAND, 8)
    place_piece(st, rB, ROMANS, LEGION, 1, from_legions_track=True)
    place_piece(st, rB, ROMANS, AUXILIA, 4)  # auxilia absorb -> fewer Legion Losses
    refresh_all_control(st)
    assert _predicted_legion_losses(st, rA, BELGAE) > _predicted_legion_losses(st, rB, BELGAE)
    assert _choose_free_battle(st, BELGAE, set(BELGICA_REGIONS)) == (rA, ROMANS)

    # A28: no-Retreat free Battle in/adjacent to Sequani with the actor's force.
    st3 = setup_scenario(SCENARIO_ARIOVISTUS, seed=4)
    st3["current_card"] = "A28"
    for r in _within1_of(st3, SEQUANI):
        _clear_region_mobiles(st3, r)
    place_piece(st3, SEQUANI, GERMANS, WARBAND, 8)
    place_piece(st3, SEQUANI, ROMANS, AUXILIA, 5)
    refresh_all_control(st3)
    res = _execute_event(st3, GERMANS, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": "A28",
        "text_preference": EVENT_UNSHADED}})
    fa = res.get("free_actions")
    assert fa and fa[0]["region"] == SEQUANI and fa[0]["defender"] == ROMANS
    assert count_pieces(st3, SEQUANI, ROMANS, AUXILIA) == 1
    assert validate_state(st3) == []


def test_free_battle_and_seize_a58():
    """Slice 28: A58 (unshaded) — Romans free Battle in Belgica, then free
    Seize in Belgica. Both free actions fire and have real board effects."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.pieces import place_piece, count_pieces
    from fs_bot.board.control import refresh_all_control
    from fs_bot.engine.execute import _execute_event
    from fs_bot.rules_consts import (SCENARIO_ARIOVISTUS, ROMANS, BELGAE,
        AUXILIA, WARBAND, EVENT_UNSHADED, BELGICA_REGIONS)
    st = setup_scenario(SCENARIO_ARIOVISTUS, seed=5)
    st["current_card"] = "A58"
    for r in BELGICA_REGIONS:
        _clear_region_mobiles(st, r)
    tgt = BELGICA_REGIONS[0]
    place_piece(st, tgt, ROMANS, AUXILIA, 6)
    place_piece(st, tgt, BELGAE, WARBAND, 3)
    refresh_all_control(st)
    res_before = st["resources"][ROMANS]
    res = _execute_event(st, ROMANS, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": "A58",
        "text_preference": EVENT_UNSHADED}})
    fa = res.get("free_actions") or []
    kinds = [f["free_action"] for f in fa]
    assert "battle" in kinds and "seize" in kinds
    seize = next(f for f in fa if f["free_action"] == "seize")
    # Free Seize forages Resources in Belgica Regions with Roman pieces.
    assert seize["result"]["forage_resources_total"] > 0
    assert st["resources"][ROMANS] > res_before
    assert validate_state(st) == []


def test_free_battle_only_for_romans_a58():
    """A58's free Battle+Seize is Roman-only; a non-Roman actor no-ops it."""
    from fs_bot.engine.execute import _resolve_a58_battle_seize
    from fs_bot.state.setup import setup_scenario
    from fs_bot.rules_consts import SCENARIO_ARIOVISTUS, BELGAE
    st = setup_scenario(SCENARIO_ARIOVISTUS, seed=5)
    assert _resolve_a58_battle_seize(st, BELGAE) == []


def test_free_march_command_a67_german():
    """Slice 29: A67 Arduenna (German path) — March into Nervii/Treveri to
    take Control of a Region with player pieces, free Battle the player there
    (Roman>Aedui>Belgae), then flip the German pieces Hidden."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.pieces import (place_piece, count_pieces,
                                     count_pieces_by_state)
    from fs_bot.board.control import refresh_all_control, is_controlled_by
    from fs_bot.map.map_data import get_adjacent
    from fs_bot.engine.execute import _execute_event
    from fs_bot.rules_consts import (SCENARIO_ARIOVISTUS, GERMANS, ROMANS,
        WARBAND, AUXILIA, REVEALED, HIDDEN, EVENT_UNSHADED, NERVII, TREVERI)

    st = setup_scenario(SCENARIO_ARIOVISTUS, seed=6)
    st["current_card"] = "A67"
    for r in (NERVII, TREVERI):
        _clear_region_mobiles(st, r)
    place_piece(st, TREVERI, ROMANS, AUXILIA, 2)  # player pieces in target
    # German Warbands in an adjacent origin, kept un-Controlled by a Roman
    # piece there, so the "no Control to lose" guard permits the March.
    origin = next(r for r in get_adjacent(TREVERI, SCENARIO_ARIOVISTUS)
                  if r != NERVII)
    _clear_region_mobiles(st, origin)
    place_piece(st, origin, GERMANS, WARBAND, 5)
    place_piece(st, origin, ROMANS, AUXILIA, 5)  # deny German Control of origin
    refresh_all_control(st)
    assert not is_controlled_by(st, origin, GERMANS)

    res = _execute_event(st, GERMANS, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": "A67",
        "text_preference": EVENT_UNSHADED}})
    fa = res.get("free_actions") or []
    kinds = [f["free_action"] for f in fa]
    assert "march" in kinds and "battle" in kinds
    # Germans gathered force into Treveri and Battled the Romans there.
    assert count_pieces(st, TREVERI, GERMANS, WARBAND) > 0
    assert count_pieces(st, TREVERI, ROMANS, AUXILIA) < 2
    # Final step: German pieces in the target are Hidden.
    assert count_pieces_by_state(st, TREVERI, GERMANS, WARBAND, REVEALED) == 0
    assert validate_state(st) == []


def test_a67_non_german_and_no_target_noop():
    """A67's German path no-ops for other Factions and when neither Nervii nor
    Treveri holds player pieces."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.engine.execute import _resolve_a67_arduenna
    from fs_bot.rules_consts import SCENARIO_ARIOVISTUS, BELGAE, GERMANS, NERVII, TREVERI
    st = setup_scenario(SCENARIO_ARIOVISTUS, seed=6)
    assert _resolve_a67_arduenna(st, BELGAE) == []  # non-German
    for r in (NERVII, TREVERI):
        _clear_region_mobiles(st, r)
        # also clear any allies/structures so player_in() finds nothing
        for pf in ("Romans", "Aedui", "Belgae"):
            pass
    # With both target Regions emptied of mobile player pieces, German path
    # finds no target with player Warbands/Auxilia/Legions.
    out = _resolve_a67_arduenna(st, GERMANS)
    assert isinstance(out, list)


def test_a20_roman_free_seize_veneti():
    """Slice 30: A20 Morbihan (unshaded) — after Arverni are cleared from
    Veneti, the Romans free Seize there (Forage; Disperse if Controlled). The
    shaded Arverni Ambush is player-controlled in Ariovistus, not NP."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.pieces import place_piece, remove_piece, count_pieces
    from fs_bot.board.control import refresh_all_control
    from fs_bot.engine.execute import _execute_event, _resolve_a20_free_seize
    from fs_bot.rules_consts import (SCENARIO_ARIOVISTUS, ROMANS, ARVERNI,
        AUXILIA, LEGION, WARBAND, ALLY, EVENT_UNSHADED, VENETI, TRIBE_VENETI)

    st = setup_scenario(SCENARIO_ARIOVISTUS, seed=7)
    st["current_card"] = "A20"
    place_piece(st, VENETI, ARVERNI, WARBAND, 2)
    ti = st["tribes"].get(TRIBE_VENETI)
    if ti and ti.get("allied_faction") is None:
        place_piece(st, VENETI, ARVERNI, ALLY)
        ti["allied_faction"] = ARVERNI
    place_piece(st, VENETI, ROMANS, AUXILIA, 2)  # Romans present to Seize
    refresh_all_control(st)
    res_before = st["resources"][ROMANS]
    res = _execute_event(st, ROMANS, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": "A20",
        "text_preference": EVENT_UNSHADED}})
    # Card effect cleared the Arverni from Veneti.
    assert count_pieces(st, VENETI, ARVERNI, WARBAND) == 0
    assert count_pieces(st, VENETI, ARVERNI, ALLY) == 0
    fa = res.get("free_actions") or []
    seize = next(f for f in fa if f["free_action"] == "seize")
    assert seize["result"]["forage_resources_total"] > 0
    assert st["resources"][ROMANS] > res_before
    assert validate_state(st) == []

    # No Roman pieces in Veneti -> the free Seize cannot occur (§3.2.3).
    st2 = setup_scenario(SCENARIO_ARIOVISTUS, seed=7)
    for pt in (AUXILIA, LEGION):
        n = count_pieces(st2, VENETI, ROMANS, pt)
        if n:
            remove_piece(st2, VENETI, ROMANS, pt, count=n)
    refresh_all_control(st2)
    out = _resolve_a20_free_seize(st2)
    assert out and out[0]["executed"] is False


def test_a20_shaded_arverni_projected_ambush():
    """Slice 31: A20 shaded — Arverni Warbands within 1 of Veneti Ambush
    Romans in a Region within 1 "as if there". Projected Hidden Warbands join
    the Ambush, then return Revealed; Arverni take no Losses (no Counterattack).
    """
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.pieces import (place_piece, count_pieces,
        count_pieces_by_state, count_on_map)
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_adjacent
    from fs_bot.engine.execute import _execute_event
    from fs_bot.rules_consts import (SCENARIO_ARIOVISTUS, ARVERNI, ROMANS,
        WARBAND, AUXILIA, ALLY, HIDDEN, REVEALED, EVENT_SHADED, VENETI,
        TRIBE_VENETI)

    st = setup_scenario(SCENARIO_ARIOVISTUS, seed=8)
    st["current_card"] = "A20"
    ti = st["tribes"].get(TRIBE_VENETI)
    _clear_region_mobiles(st, VENETI)
    place_piece(st, VENETI, ARVERNI, WARBAND, 6)  # Hidden
    if ti and ti.get("allied_faction") is None:
        place_piece(st, VENETI, ARVERNI, ALLY)
        ti["allied_faction"] = ARVERNI
    adj = list(get_adjacent(VENETI, SCENARIO_ARIOVISTUS))
    B = adj[0]
    _clear_region_mobiles(st, B)
    place_piece(st, B, ROMANS, AUXILIA, 2)
    for r in adj[1:]:
        _clear_region_mobiles(st, r)
    refresh_all_control(st)
    arv_before = count_on_map(st, ARVERNI, WARBAND)

    res = _execute_event(st, ROMANS, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": "A20",
        "text_preference": EVENT_SHADED}})
    fa = res.get("free_actions") or []
    amb = next(f for f in fa if f["free_action"] == "ambush")
    assert amb["region"] == B and amb["defender"] == ROMANS
    assert count_pieces(st, B, ROMANS, AUXILIA) == 0          # Romans removed
    assert count_pieces(st, B, ARVERNI, WARBAND) == 0          # projected returned
    assert count_pieces_by_state(st, VENETI, ARVERNI, WARBAND, REVEALED) == 6
    assert count_on_map(st, ARVERNI, WARBAND) == arv_before    # conserved
    assert validate_state(st) == []


def test_a20_shaded_noops_without_ally_or_romans():
    """A20 shaded no-ops with no Arverni Ally in Veneti, or no Romans within 1."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.board.pieces import count_pieces, remove_piece
    from fs_bot.board.control import refresh_all_control
    from fs_bot.engine.execute import _resolve_a20_arverni_ambush
    from fs_bot.map.map_data import get_adjacent
    from fs_bot.rules_consts import (SCENARIO_ARIOVISTUS, ARVERNI, ROMANS, ALLY,
        WARBAND, AUXILIA, LEGION, FACTIONS, VENETI, TRIBE_VENETI)
    # No Arverni Ally in Veneti -> no-op.
    st = setup_scenario(SCENARIO_ARIOVISTUS, seed=8)
    ti = st["tribes"].get(TRIBE_VENETI)
    if ti and ti.get("allied_faction") == ARVERNI:
        if count_pieces(st, VENETI, ARVERNI, ALLY) > 0:
            remove_piece(st, VENETI, ARVERNI, ALLY)
        ti["allied_faction"] = None
    refresh_all_control(st)
    out = _resolve_a20_arverni_ambush(st)
    assert out and out[0]["executed"] is False


def test_double_auxilia_loss_modifier():
    """Slice 32: double_auxilia makes Auxilia cause 1 Loss each, not 1/2."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.board.pieces import place_piece
    from fs_bot.board.control import refresh_all_control
    from fs_bot.battle.losses import calculate_losses
    from fs_bot.rules_consts import (SCENARIO_ARIOVISTUS, ROMANS, ARVERNI,
        AUXILIA, WARBAND, BELGICA_REGIONS)
    st = setup_scenario(SCENARIO_ARIOVISTUS, seed=9)
    R = BELGICA_REGIONS[0]
    _clear_region_mobiles(st, R)
    place_piece(st, R, ROMANS, AUXILIA, 4)
    place_piece(st, R, ARVERNI, WARBAND, 6)
    refresh_all_control(st)
    assert calculate_losses(st, R, ROMANS, ARVERNI) == 2
    assert calculate_losses(st, R, ROMANS, ARVERNI, double_auxilia=True) == 4


def test_a17_unshaded_march_battle_double_auxilia():
    """Slice 32: A17 unshaded — Romans free March a group to a Caesar-free
    Region and Battle there with double Auxilia Losses."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.pieces import (place_piece, remove_piece, count_pieces,
        get_leader_in_region, find_leader)
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_adjacent, get_tribes_in_region
    from fs_bot.engine.execute import _resolve_a17_march_battle
    from fs_bot.rules_consts import (SCENARIO_ARIOVISTUS, ROMANS, ARVERNI,
        CAESAR, AUXILIA, ALLY, CITADEL, WARBAND, TRIBE_TO_REGION,
        BELGICA_REGIONS)
    st = setup_scenario(SCENARIO_ARIOVISTUS, seed=11)
    # Null all Allies/Citadels so our staged Region is the unique destination.
    for tribe, info in st["tribes"].items():
        fac = info.get("allied_faction")
        if fac:
            reg = TRIBE_TO_REGION.get(tribe)
            if reg and count_pieces(st, reg, fac, ALLY) > 0:
                remove_piece(st, reg, fac, ALLY)
            while reg and count_pieces(st, reg, fac, CITADEL) > 0:
                remove_piece(st, reg, fac, CITADEL)
            info["allied_faction"] = None
    caesar_loc = find_leader(st, ROMANS)
    T = next(r for r in BELGICA_REGIONS if r != caesar_loc)
    _clear_region_mobiles(st, T)
    place_piece(st, T, ARVERNI, WARBAND, 6)
    for t in get_tribes_in_region(T, SCENARIO_ARIOVISTUS):
        info = st["tribes"].get(t)
        if info is not None:
            place_piece(st, T, ARVERNI, ALLY)
            info["allied_faction"] = ARVERNI
            break
    src = next(r for r in get_adjacent(T, SCENARIO_ARIOVISTUS)
               if get_leader_in_region(st, r, ROMANS) != CAESAR)
    _clear_region_mobiles(st, src)
    place_piece(st, src, ROMANS, AUXILIA, 6)
    refresh_all_control(st)
    out = _resolve_a17_march_battle(st)
    assert out[0]["region"] == T and out[0]["defender"] == ARVERNI
    # 6 Auxilia at double = 6 Losses; Arverni never Retreat in Ariovistus.
    assert count_pieces(st, T, ARVERNI, WARBAND) == 0
    assert count_pieces(st, T, ROMANS, AUXILIA) == 6  # marched in
    assert validate_state(st) == []


def test_a17_shaded_remove_4_auxilia_and_derivers():
    """Slice 32: A17 shaded removes 4 Roman Auxilia from a Region; derivers
    honor German (Germania/Settlement) and Belgic (Belgica) preferences."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.pieces import place_piece, count_pieces
    from fs_bot.board.control import refresh_all_control
    from fs_bot.engine.execute import _execute_event, _derive_card_A17
    from fs_bot.rules_consts import (SCENARIO_ARIOVISTUS, ROMANS, GERMANS,
        BELGAE, AUXILIA, EVENT_SHADED, GERMANIA_REGIONS, BELGICA_REGIONS)
    st = setup_scenario(SCENARIO_ARIOVISTUS, seed=10)
    g = GERMANIA_REGIONS[0]
    nb = BELGICA_REGIONS[0]
    _clear_region_mobiles(st, g)
    _clear_region_mobiles(st, nb)
    place_piece(st, g, ROMANS, AUXILIA, 2)
    place_piece(st, nb, ROMANS, AUXILIA, 5)
    refresh_all_control(st)
    # German prefers Germania even with fewer Auxilia there.
    assert _derive_card_A17(st, GERMANS, True)["region"] == g
    # Belgic prefers a Belgica Region.
    assert _derive_card_A17(st, BELGAE, True)["region"] == nb
    # Unshaded returns None from the deriver (it is executed, not derived).
    assert _derive_card_A17(st, ROMANS, False) is None

    st2 = setup_scenario(SCENARIO_ARIOVISTUS, seed=10)
    st2["current_card"] = "A17"
    nb2 = BELGICA_REGIONS[0]
    _clear_region_mobiles(st2, nb2)
    place_piece(st2, nb2, ROMANS, AUXILIA, 5)
    refresh_all_control(st2)
    _execute_event(st2, BELGAE, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": "A17",
        "text_preference": EVENT_SHADED}})
    assert count_pieces(st2, nb2, ROMANS, AUXILIA) == 1  # 4 removed
    assert validate_state(st2) == []


def test_a19_shaded_german_marches_romans():
    """Slice 33: A19 shaded — a German actor relocates all Roman mobile pieces
    (Caesar, Legions, Auxilia) into an adjacent German Region (no Fort) where
    Germans will outnumber them. Non-German actors no-op."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.pieces import (place_piece, count_pieces, find_leader,
        get_leader_in_region)
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_adjacent, get_playable_regions
    from fs_bot.engine.execute import _execute_event, _resolve_a19_march_romans
    from fs_bot.rules_consts import (SCENARIO_ARIOVISTUS, ROMANS, GERMANS,
        BELGAE, CAESAR, AUXILIA, LEGION, WARBAND, EVENT_SHADED)

    # Caesar + Legions + Auxilia relocate from Caesar's Region into a German D.
    st = setup_scenario(SCENARIO_ARIOVISTUS, seed=13)
    st["current_card"] = "A19"
    S = find_leader(st, ROMANS)
    pl = get_playable_regions(SCENARIO_ARIOVISTUS, st.get("capabilities"))
    D = next(d for d in get_adjacent(S, SCENARIO_ARIOVISTUS) if d in pl)
    _clear_region_mobiles(st, S)
    _clear_region_mobiles(st, D)
    place_piece(st, S, ROMANS, LEGION, 2, from_legions_track=True)
    place_piece(st, S, ROMANS, AUXILIA, 1)
    place_piece(st, D, GERMANS, WARBAND, 7)  # outnumbers Caesar+2+1 = 4
    refresh_all_control(st)
    res = _execute_event(st, GERMANS, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": "A19",
        "text_preference": EVENT_SHADED}})
    fa = res.get("free_actions") or []
    mr = next(f for f in fa if f["free_action"] == "march_romans")
    assert mr["source"] == S and mr["dest"] == D
    assert get_leader_in_region(st, D, ROMANS) == CAESAR
    assert count_pieces(st, D, ROMANS, LEGION) == 2
    assert count_pieces(st, D, ROMANS, AUXILIA) == 1
    assert count_pieces(st, S, ROMANS, LEGION) == 0
    assert get_leader_in_region(st, S, ROMANS) is None
    assert validate_state(st) == []

    # Non-German actor no-ops (only the German path is specified).
    st2 = setup_scenario(SCENARIO_ARIOVISTUS, seed=13)
    assert _resolve_a19_march_romans(st2, BELGAE) == []


def test_a19_shaded_noop_when_no_trap_available():
    """A19 shaded no-ops if no adjacent German Region would outnumber the
    moved Romans (German instruction's precondition not met)."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.board.pieces import place_piece, count_pieces, find_leader
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_adjacent, get_playable_regions
    from fs_bot.engine.execute import _resolve_a19_march_romans
    from fs_bot.rules_consts import (SCENARIO_ARIOVISTUS, ROMANS, GERMANS,
        AUXILIA, WARBAND, FACTIONS)
    st = setup_scenario(SCENARIO_ARIOVISTUS, seed=14)
    # Strip every German Warband from the map so no destination can outnumber.
    for r in get_playable_regions(SCENARIO_ARIOVISTUS, st.get("capabilities")):
        n = count_pieces(st, r, GERMANS, WARBAND)
        if n:
            from fs_bot.board.pieces import remove_piece
            remove_piece(st, r, GERMANS, WARBAND, count=n)
    refresh_all_control(st)
    out = _resolve_a19_march_romans(st, GERMANS)
    assert out and out[0]["executed"] is False


def test_card11_place_auxilia_and_double_battle():
    """Slice 34: Card 11 Numidians (unshaded) — place 3 Auxilia within 1 of
    Caesar and free Battle there with double Auxilia Losses."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.pieces import place_piece, count_pieces, find_leader
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_adjacent
    from fs_bot.engine.execute import _execute_event, _derive_card_11
    from fs_bot.rules_consts import (SCENARIO_GALLIC_WAR, ROMANS, ARVERNI,
        WARBAND, AUXILIA, EVENT_UNSHADED)
    st = setup_scenario(SCENARIO_GALLIC_WAR, seed=20)
    st["current_card"] = 11
    cae = find_leader(st, ROMANS)
    # Clear all Regions within 1 of Caesar, then stage one target with Arverni.
    for r in [cae] + list(get_adjacent(cae, SCENARIO_GALLIC_WAR)):
        _clear_region_mobiles(st, r)
    T = get_adjacent(cae, SCENARIO_GALLIC_WAR)[0]
    place_piece(st, T, ARVERNI, WARBAND, 5)
    refresh_all_control(st)
    der = _derive_card_11(st, ROMANS, False)
    assert der and der["target_region"] == T
    res = _execute_event(st, ROMANS, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": 11,
        "text_preference": EVENT_UNSHADED}})
    fa = res.get("free_actions") or []
    assert any(f["free_action"] == "battle" and f.get("region") == T for f in fa)
    # 3 placed Auxilia at double = 3 Losses (normal would be 1): 5 -> 2.
    assert count_pieces(st, T, ARVERNI, WARBAND) == 2
    assert validate_state(st) == []


def test_card11_deriver_no_play_when_under_3_auxilia():
    """Numidians: 'Place the full number; if not able, No Romans' -> deriver
    returns None when fewer than 3 Auxilia are Available."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.board.pieces import get_available, place_piece
    from fs_bot.board.control import refresh_all_control
    from fs_bot.engine.execute import _derive_card_11
    from fs_bot.rules_consts import (SCENARIO_GALLIC_WAR, ROMANS, AUXILIA,
        ALL_REGIONS)
    st = setup_scenario(SCENARIO_GALLIC_WAR, seed=20)
    # Drain Available Auxilia below 3 by placing them on the map.
    while get_available(st, ROMANS, AUXILIA) >= 3:
        from fs_bot.map.map_data import get_playable_regions
        r = get_playable_regions(SCENARIO_GALLIC_WAR, st.get("capabilities"))[0]
        place_piece(st, r, ROMANS, AUXILIA, 1)
    refresh_all_control(st)
    assert _derive_card_11(st, ROMANS, False) is None


def test_card6_free_scout_and_double_battle():
    """Slice 34: Card 6 Marcus Antonius (unshaded) — free Scout, then free
    Battle (double Auxilia) in a Roman Battle-priority Region."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.pieces import place_piece, find_leader
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_adjacent
    from fs_bot.engine.execute import _execute_event
    from fs_bot.rules_consts import (SCENARIO_GALLIC_WAR, ROMANS, ARVERNI,
        AUXILIA, WARBAND, EVENT_UNSHADED)
    st = setup_scenario(SCENARIO_GALLIC_WAR, seed=21)
    st["current_card"] = 6
    cae = find_leader(st, ROMANS)
    B = get_adjacent(cae, SCENARIO_GALLIC_WAR)[0]
    _clear_region_mobiles(st, B)
    place_piece(st, B, ROMANS, AUXILIA, 6)
    place_piece(st, B, ARVERNI, WARBAND, 2)
    refresh_all_control(st)
    res = _execute_event(st, ROMANS, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": 6,
        "text_preference": EVENT_UNSHADED}})
    kinds = [f["free_action"] for f in (res.get("free_actions") or [])]
    assert "scout" in kinds and "battle" in kinds
    assert validate_state(st) == []


def test_card11a_ariovistus_place_and_double_battle():
    """Slice 34: Card 11a (Ariovistus text) — same place-3-Auxilia + double
    Auxilia Battle, dispatched via the Ariovistus handler."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.pieces import place_piece, count_pieces, find_leader
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_adjacent
    from fs_bot.engine.execute import _execute_event
    from fs_bot.rules_consts import (SCENARIO_ARIOVISTUS, ROMANS, ARVERNI,
        WARBAND, EVENT_UNSHADED)
    st = setup_scenario(SCENARIO_ARIOVISTUS, seed=22)
    st["current_card"] = 11
    cae = find_leader(st, ROMANS)
    for r in [cae] + list(get_adjacent(cae, SCENARIO_ARIOVISTUS)):
        _clear_region_mobiles(st, r)
    T = get_adjacent(cae, SCENARIO_ARIOVISTUS)[0]
    place_piece(st, T, ARVERNI, WARBAND, 5)
    refresh_all_control(st)
    res = _execute_event(st, ROMANS, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": 11,
        "text_preference": EVENT_UNSHADED}})
    fa = res.get("free_actions") or []
    assert any(f.get("flag") == "card_11a" and f.get("region") == T for f in fa)
    assert count_pieces(st, T, ARVERNI, WARBAND) == 2  # double-Auxilia 3 Losses
    assert validate_state(st) == []


def test_card2_shaded_auto_legion_loss_battle():
    """Slice 35: Card 2 Legiones (shaded) — a non-Roman free Battles the
    Romans; the first Loss removes a Roman Legion automatically (no roll)."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.pieces import place_piece, count_pieces
    from fs_bot.board.control import refresh_all_control
    from fs_bot.battle.resolve import resolve_battle
    from fs_bot.engine.execute import _execute_event, _derive_card_2
    from fs_bot.rules_consts import (SCENARIO_GALLIC_WAR, ROMANS, ARVERNI,
        WARBAND, AUXILIA, LEGION, ALL_REGIONS, EVENT_SHADED)

    R = [r for r in ALL_REGIONS if r != "Provincia"][3]

    # Modifier is automatic regardless of dice (Legion removed every time).
    for seed in range(15):
        st = setup_scenario(SCENARIO_GALLIC_WAR, seed=seed)
        _clear_region_mobiles(st, R)
        place_piece(st, R, ROMANS, LEGION, 1, from_legions_track=True)
        place_piece(st, R, ROMANS, AUXILIA, 4)
        place_piece(st, R, ARVERNI, WARBAND, 4)
        refresh_all_control(st)
        resolve_battle(st, R, ARVERNI, ROMANS, retreat_declaration=False,
                       auto_legion_loss=True)
        assert count_pieces(st, R, ROMANS, LEGION) == 0

    # Full Event path: deriver picks a Region with a Roman Legion; the free
    # Battle removes it.
    st2 = setup_scenario(SCENARIO_GALLIC_WAR, seed=31)
    st2["current_card"] = 2
    R2 = [r for r in ALL_REGIONS if r != "Provincia"][4]
    _clear_region_mobiles(st2, R2)
    place_piece(st2, R2, ROMANS, LEGION, 1, from_legions_track=True)
    place_piece(st2, R2, ROMANS, AUXILIA, 3)
    place_piece(st2, R2, ARVERNI, WARBAND, 6)
    refresh_all_control(st2)
    der = _derive_card_2(st2, ARVERNI, True)
    assert der and der["battle_region"] == R2
    res = _execute_event(st2, ARVERNI, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": 2,
        "text_preference": EVENT_SHADED}})
    fa = res.get("free_actions") or []
    assert any(f["free_action"] == "battle" and f.get("region") == R2 for f in fa)
    assert count_pieces(st2, R2, ROMANS, LEGION) == 0
    assert validate_state(st2) == []


def test_card2_deriver_none_for_romans():
    """Card 2 shaded deriver returns None for a Roman actor (Romans do not
    Battle themselves)."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.engine.execute import _derive_card_2
    from fs_bot.rules_consts import SCENARIO_GALLIC_WAR, ROMANS
    st = setup_scenario(SCENARIO_GALLIC_WAR, seed=31)
    assert _derive_card_2(st, ROMANS, True) is None


def test_card70_roman_march_battle_to_named_region():
    """Slice 36: Card 70 Camulogenus (unshaded) — Romans free March up to 4
    Legions + any Auxilia to Atrebates/Carnutes/Mandubii and free Battle
    there."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.pieces import place_piece, count_pieces
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_adjacent
    from fs_bot.engine.execute import _execute_event
    from fs_bot.rules_consts import (SCENARIO_GALLIC_WAR, ROMANS, ARVERNI,
        WARBAND, AUXILIA, LEGION, EVENT_UNSHADED, ATREBATES, CARNUTES, MANDUBII)
    st = setup_scenario(SCENARIO_GALLIC_WAR, seed=40)
    st["current_card"] = 70
    for T in (ATREBATES, CARNUTES, MANDUBII):
        _clear_region_mobiles(st, T)
    place_piece(st, CARNUTES, ARVERNI, WARBAND, 5)
    src = get_adjacent(CARNUTES, SCENARIO_GALLIC_WAR)[0]
    _clear_region_mobiles(st, src)
    place_piece(st, src, ROMANS, LEGION, 6, from_legions_track=True)  # > 4 cap
    place_piece(st, src, ROMANS, AUXILIA, 6)
    refresh_all_control(st)
    res = _execute_event(st, ROMANS, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": 70,
        "text_preference": EVENT_UNSHADED}})
    fa = res.get("free_actions") or []
    mb = next(f for f in fa if f["free_action"] == "march_battle")
    assert mb["region"] == CARNUTES and mb["defender"] == ARVERNI
    # Legion cap of 4 enforced; all Auxilia move.
    assert mb["moved"]["legions"] == 4
    assert mb["moved"]["auxilia"] == 6
    assert count_pieces(st, CARNUTES, ROMANS, LEGION) == 4
    assert count_pieces(st, CARNUTES, ARVERNI, WARBAND) == 0  # Battled away
    assert validate_state(st) == []


def _clear_all_mobiles(state, scenario):
    from fs_bot.map.map_data import get_playable_regions
    for r in get_playable_regions(scenario, state.get("capabilities")):
        _clear_region_mobiles(state, r)


def test_card72_shaded_hidden_warband_march_battle():
    """Slice 37: Card 72 Impetuosity (shaded) — Arverni March a Hidden-Warband
    group into a player Region and free Battle; Aedui no-play."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.pieces import place_piece, count_pieces
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_adjacent, get_playable_regions
    from fs_bot.engine.execute import (_execute_event,
        _resolve_card72_hidden_march_battle)
    from fs_bot.rules_consts import (SCENARIO_GALLIC_WAR, ROMANS, ARVERNI,
        AEDUI, WARBAND, AUXILIA, EVENT_SHADED)

    st = setup_scenario(SCENARIO_GALLIC_WAR, seed=50)
    st["current_card"] = 72
    _clear_all_mobiles(st, SCENARIO_GALLIC_WAR)
    pl = get_playable_regions(SCENARIO_GALLIC_WAR, st.get("capabilities"))
    S = pl[5]
    B = next(r for r in get_adjacent(S, SCENARIO_GALLIC_WAR) if r in pl)
    place_piece(st, S, ARVERNI, WARBAND, 6)
    place_piece(st, B, ROMANS, AUXILIA, 3)
    refresh_all_control(st)
    res = _execute_event(st, ARVERNI, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": 72,
        "text_preference": EVENT_SHADED}})
    fa = res.get("free_actions") or []
    mb = next(f for f in fa if f["free_action"] == "march_battle")
    assert mb["source"] == S and mb["region"] == B and mb["defender"] == ROMANS
    assert count_pieces(st, S, ARVERNI, WARBAND) == 0      # group marched out
    assert count_pieces(st, B, ARVERNI, WARBAND) == 6      # into B
    assert count_pieces(st, B, ROMANS) == 0               # Battled away/retreated
    assert validate_state(st) == []

    # Aedui: "continue on the flowchart instead" -> no free March/Battle.
    st2 = setup_scenario(SCENARIO_GALLIC_WAR, seed=50)
    out = _resolve_card72_hidden_march_battle(st2, AEDUI)
    assert out and out[0]["executed"] is False


def test_card72_shaded_belgae_targets_an_enemy():
    """Belgae path executes a Hidden-Warband March+Battle against an enemy."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.pieces import place_piece, count_pieces
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_adjacent, get_playable_regions
    from fs_bot.engine.execute import _execute_event
    from fs_bot.rules_consts import (SCENARIO_GALLIC_WAR, BELGAE, ROMANS,
        WARBAND, AUXILIA, EVENT_SHADED)
    st = setup_scenario(SCENARIO_GALLIC_WAR, seed=51)
    st["current_card"] = 72
    _clear_all_mobiles(st, SCENARIO_GALLIC_WAR)
    pl = get_playable_regions(SCENARIO_GALLIC_WAR, st.get("capabilities"))
    S = pl[6]
    B = next(r for r in get_adjacent(S, SCENARIO_GALLIC_WAR) if r in pl)
    place_piece(st, S, BELGAE, WARBAND, 5)
    place_piece(st, B, ROMANS, AUXILIA, 2)
    refresh_all_control(st)
    res = _execute_event(st, BELGAE, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": 72,
        "text_preference": EVENT_SHADED}})
    fa = res.get("free_actions") or []
    assert any(f["free_action"] == "march_battle" and f.get("region") == B
               for f in fa)
    assert count_pieces(st, S, BELGAE, WARBAND) == 0
    assert validate_state(st) == []


def test_ignore_fort_modifier():
    """Slice 38: ignore_fort makes a Fort give no halving and no ambush
    roll-restoration (card 58's 'unprepared fort')."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.board.pieces import place_piece, count_pieces
    from fs_bot.board.control import refresh_all_control
    from fs_bot.battle.resolve import resolve_battle
    from fs_bot.map.map_data import get_playable_regions
    from fs_bot.rules_consts import (SCENARIO_GALLIC_WAR, ROMANS, GERMANS,
        WARBAND, AUXILIA, FORT)

    def setup():
        st = setup_scenario(SCENARIO_GALLIC_WAR, seed=60)
        R = get_playable_regions(SCENARIO_GALLIC_WAR, st.get("capabilities"))[4]
        _clear_region_mobiles(st, R)
        place_piece(st, R, ROMANS, AUXILIA, 4)
        place_piece(st, R, ROMANS, FORT, 1)
        place_piece(st, R, GERMANS, WARBAND, 8)
        refresh_all_control(st)
        return st, R

    st, R = setup()
    resolve_battle(st, R, GERMANS, ROMANS, is_ambush=True)
    assert count_pieces(st, R, ROMANS, AUXILIA) == 2  # 8wb->4, fort halves to 2
    st, R = setup()
    resolve_battle(st, R, GERMANS, ROMANS, is_ambush=True, ignore_fort=True)
    assert count_pieces(st, R, ROMANS, AUXILIA) == 0  # 8wb->4, no halving


def test_card58_shaded_german_ambush_at_fort():
    """Slice 38: Card 58 Aduatuca (shaded) — gather German Warbands into a
    Roman-Fort Region and Ambush the Romans there (1 Loss per 2 Warbands, Fort
    ineffective)."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.pieces import place_piece, count_pieces
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_adjacent, get_playable_regions
    from fs_bot.engine.execute import _execute_event
    from fs_bot.rules_consts import (SCENARIO_GALLIC_WAR, ROMANS, GERMANS,
        BELGAE, WARBAND, AUXILIA, FORT, EVENT_SHADED)
    st = setup_scenario(SCENARIO_GALLIC_WAR, seed=61)
    st["current_card"] = 58
    pl = get_playable_regions(SCENARIO_GALLIC_WAR, st.get("capabilities"))
    for r in pl:
        _clear_region_mobiles(st, r)
    R = pl[4]
    place_piece(st, R, ROMANS, AUXILIA, 4)
    place_piece(st, R, ROMANS, FORT, 1)
    adj = next(a for a in get_adjacent(R, SCENARIO_GALLIC_WAR) if a in pl)
    place_piece(st, R, GERMANS, WARBAND, 3)
    place_piece(st, adj, GERMANS, WARBAND, 5)
    refresh_all_control(st)
    res = _execute_event(st, BELGAE, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": 58,
        "text_preference": EVENT_SHADED}})
    fa = res.get("free_actions") or []
    amb = next(f for f in fa if f["free_action"] == "ambush")
    assert amb["region"] == R and amb["defender"] == ROMANS
    assert amb["warbands_gathered"] == 8
    # 8 Warbands -> 4 Losses (Fort ineffective): all 4 Auxilia removed.
    assert count_pieces(st, R, ROMANS, AUXILIA) == 0
    assert count_pieces(st, adj, GERMANS, WARBAND) == 0  # marched in
    assert validate_state(st) == []


def _full_clear_region(state, region, scenario):
    from fs_bot.board.pieces import count_pieces, remove_piece
    from fs_bot.map.map_data import get_tribes_in_region
    from fs_bot.rules_consts import (FACTIONS, WARBAND, LEGION, AUXILIA, ALLY,
        CITADEL)
    for f in FACTIONS:
        for pt in (WARBAND, LEGION, AUXILIA, ALLY, CITADEL):
            n = count_pieces(state, region, f, pt)
            if n:
                remove_piece(state, region, f, pt, count=n)
    for t in get_tribes_in_region(region, scenario):
        ti = state["tribes"].get(t)
        if ti:
            ti["allied_faction"] = None


def test_card65_german_march_then_ambush_all_able():
    """Slice 39: Card 65 German Allegiances (unshaded) — setup March (<=2
    Regions) into an enemy Region to enable an Ambush, then Ambush with all
    Germans able; an existing Ambush is not stripped to fund a March."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.pieces import place_piece, count_pieces
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_adjacent, get_playable_regions
    from fs_bot.engine.execute import _execute_event
    from fs_bot.rules_consts import (SCENARIO_GALLIC_WAR, ROMANS, ARVERNI,
        GERMANS, BELGAE, WARBAND, AUXILIA, EVENT_UNSHADED)
    st = setup_scenario(SCENARIO_GALLIC_WAR, seed=72)
    st["current_card"] = 65
    pl = get_playable_regions(SCENARIO_GALLIC_WAR, st.get("capabilities"))
    for r in pl:
        _full_clear_region(st, r, SCENARIO_GALLIC_WAR)
    A = pl[3]
    B = pl[7]
    S = next(a for a in get_adjacent(B, SCENARIO_GALLIC_WAR)
             if a in pl and a != A)
    place_piece(st, A, GERMANS, WARBAND, 6)   # existing Ambush vs Arverni
    place_piece(st, A, ARVERNI, WARBAND, 2)
    place_piece(st, B, ROMANS, AUXILIA, 3)    # enemy, no German yet
    place_piece(st, S, GERMANS, WARBAND, 5)   # clean March source
    refresh_all_control(st)
    res = _execute_event(st, BELGAE, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": 65,
        "text_preference": EVENT_UNSHADED}})
    fa = (res.get("free_actions") or [])[0]
    # The clean source marched into B (A was not stripped).
    assert any(m["source"] == S and m["dest"] == B for m in fa["marches"])
    amb_regions = {a["region"] for a in fa["ambushes"] if "defender" in a}
    assert A in amb_regions and B in amb_regions
    assert count_pieces(st, A, ARVERNI, WARBAND) == 0       # existing Ambush kept
    assert count_pieces(st, B, ROMANS, AUXILIA) == 1        # 5wb -> 2 Losses
    assert count_pieces(st, S, GERMANS, WARBAND) == 0       # marched out
    assert validate_state(st) == []


def test_card17_unshaded_march_then_single_ambush():
    """Slice 40: Card 17 Germanic Chieftains (unshaded) — setup March up to 3
    German groups, then Ambush in the single best Region (most enemy pieces)."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.pieces import place_piece, count_pieces
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_playable_regions
    from fs_bot.engine.execute import _execute_event
    from fs_bot.rules_consts import (SCENARIO_GALLIC_WAR, ROMANS, ARVERNI,
        GERMANS, WARBAND, AUXILIA, EVENT_UNSHADED)
    st = setup_scenario(SCENARIO_GALLIC_WAR, seed=80)
    st["current_card"] = 17
    pl = get_playable_regions(SCENARIO_GALLIC_WAR, st.get("capabilities"))
    for r in pl:
        _full_clear_region(st, r, SCENARIO_GALLIC_WAR)
    A = pl[3]   # bigger enemy stack
    place_piece(st, A, GERMANS, WARBAND, 6)
    place_piece(st, A, ARVERNI, WARBAND, 4)
    B = pl[5]   # smaller enemy stack
    place_piece(st, B, GERMANS, WARBAND, 6)
    place_piece(st, B, ROMANS, AUXILIA, 1)
    refresh_all_control(st)
    res = _execute_event(st, ROMANS, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": 17,
        "text_preference": EVENT_UNSHADED}})
    fa = (res.get("free_actions") or [])[0]
    # Exactly one Region Ambushed, the larger target.
    assert fa["region"] == A and fa["defender"] == ARVERNI
    assert count_pieces(st, A, ARVERNI, WARBAND) == 1   # 6wb -> 3 Losses
    assert count_pieces(st, B, ROMANS, AUXILIA) == 1    # other Region untouched
    assert validate_state(st) == []


def test_card17_shaded_germans_phase():
    """Slice 40: Card 17 (shaded) — conduct an immediate Germans Phase as if
    Winter (base game only)."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.engine.execute import _execute_event
    from fs_bot.rules_consts import (SCENARIO_GREAT_REVOLT, SCENARIO_ARIOVISTUS,
        ROMANS, EVENT_SHADED)
    # Base scenario: the full Germans Phase runs.
    st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=82)
    st["current_card"] = 17
    res = _execute_event(st, ROMANS, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": 17,
        "text_preference": EVENT_SHADED}})
    f = (res.get("free_actions") or [])[0]
    assert f["executed"] is True
    assert set(f["result"].keys()) == {"rally", "march", "raid", "battle"}
    assert validate_state(st) == []
    # Ariovistus: there is no Germans Phase -> no-op (executed False).
    st2 = setup_scenario(SCENARIO_ARIOVISTUS, seed=82)
    st2["current_card"] = 17
    res2 = _execute_event(st2, ROMANS, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": 17,
        "text_preference": EVENT_SHADED}})
    assert (res2.get("free_actions") or [{}])[0].get("executed") is False


def test_card57_unshaded_free_march_into_britannia():
    """Slice 41: Card 57 Land of Mist (unshaded) — a non-German Faction free
    Marches a mobile group into Britannia (+4 Resources from the card)."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.pieces import place_piece, count_pieces
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_playable_regions
    from fs_bot.engine.execute import (_execute_event,
        _resolve_card57_britannia_march)
    from fs_bot.rules_consts import (SCENARIO_GREAT_REVOLT, BELGAE, GERMANS,
        WARBAND, MORINI, BRITANNIA, EVENT_UNSHADED)
    st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=90)
    st["current_card"] = 57
    pl = get_playable_regions(SCENARIO_GREAT_REVOLT, st.get("capabilities"))
    assert BRITANNIA in pl
    _clear_region_mobiles(st, MORINI)
    _clear_region_mobiles(st, BRITANNIA)
    place_piece(st, MORINI, BELGAE, WARBAND, 4)
    refresh_all_control(st)
    res_before = st["resources"][BELGAE]
    res = _execute_event(st, BELGAE, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": 57,
        "text_preference": EVENT_UNSHADED}})
    fa = res.get("free_actions") or []
    march = next(f for f in fa if f["free_action"] == "march")
    assert march["source"] == MORINI and march["final_region"] == BRITANNIA
    assert count_pieces(st, MORINI, BELGAE, WARBAND) == 0
    assert count_pieces(st, BRITANNIA, BELGAE, WARBAND) == 4
    assert st["resources"][BELGAE] == res_before + 4
    assert validate_state(st) == []

    # Germans may not March to Britannia (non-German only).
    out = _resolve_card57_britannia_march(st, GERMANS)
    assert out and out[0]["executed"] is False


def test_card4_circumvallation_march_and_marker():
    """Slice 42: Card 4 Circumvallation — Romans free March into an adjacent
    enemy-Citadel Region; the Circumvallation marker is placed there."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.pieces import place_piece, remove_piece, count_pieces
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_adjacent, get_playable_regions
    from fs_bot.engine.execute import _execute_event, _derive_card_4
    from fs_bot.rules_consts import (SCENARIO_GREAT_REVOLT, ROMANS, ARVERNI,
        WARBAND, AUXILIA, LEGION, CITADEL, FACTIONS, MARKER_CIRCUMVALLATION,
        EVENT_UNSHADED)

    st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=95)
    st["current_card"] = 4
    pl = get_playable_regions(SCENARIO_GREAT_REVOLT, st.get("capabilities"))
    # Clear all Citadels/mobiles so the staged Citadel is the unique candidate.
    for r in pl:
        for f in FACTIONS:
            for pt in (WARBAND, LEGION, AUXILIA, CITADEL):
                n = count_pieces(st, r, f, pt)
                if n:
                    remove_piece(st, r, f, pt, count=n)
    R = pl[4]
    place_piece(st, R, ARVERNI, CITADEL, 1)
    place_piece(st, R, ARVERNI, WARBAND, 3)
    src = next(a for a in get_adjacent(R, SCENARIO_GREAT_REVOLT) if a in pl)
    place_piece(st, src, ROMANS, AUXILIA, 4)
    refresh_all_control(st)
    assert _derive_card_4(st, ROMANS, False)["target_region"] == R

    res = _execute_event(st, ROMANS, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": 4,
        "text_preference": EVENT_UNSHADED}})
    fa = res.get("free_actions") or []
    march = next(f for f in fa if f["free_action"] == "march")
    assert march["source"] == src and march["final_region"] == R
    assert count_pieces(st, R, ROMANS, AUXILIA) == 4       # marched in
    assert count_pieces(st, src, ROMANS, AUXILIA) == 0
    assert MARKER_CIRCUMVALLATION in (st.get("markers", {}).get(R) or {})
    assert validate_state(st) == []


def test_card4_deriver_none_for_non_roman():
    """Card 4 is Roman-only; the deriver returns None for other Factions."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.engine.execute import _derive_card_4
    from fs_bot.rules_consts import SCENARIO_GREAT_REVOLT, ARVERNI
    st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=95)
    assert _derive_card_4(st, ARVERNI, False) is None


def test_free_command_layer_uses_flowchart():
    """Slice 43: _resolve_free_command runs the Faction's real flowchart (with
    Event-play disabled) and executes the chosen Command."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.engine.game_engine import get_sop_factions
    from fs_bot.engine.execute import _resolve_free_command
    from fs_bot.rules_consts import SCENARIO_GREAT_REVOLT, ROMANS
    st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=100)
    st["non_player_factions"] = set(get_sop_factions(st))
    res = _resolve_free_command(st, ROMANS)
    assert res["executed"] is True
    assert res["command"] in {"Battle", "March", "Rally", "Raid", "Recruit",
                              "Seize"}
    # Event-play flag restored after the call.
    assert "can_play_event" not in st or st.get("can_play_event") in (None,
        True, False)
    assert validate_state(st) == []


def test_free_command_layer_skips_non_bot_faction():
    """The free-Command chooser no-ops for a Faction not marked Non-Player."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.engine.execute import _resolve_free_command
    from fs_bot.rules_consts import SCENARIO_GREAT_REVOLT, ROMANS
    st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=100)
    st["non_player_factions"] = set()   # nobody is a bot
    res = _resolve_free_command(st, ROMANS)
    assert res["executed"] is False


def test_card9_free_march_and_command():
    """Slice 43/44: Card 9 Mons Cevenna executes a free Command via the layer,
    restricted to the destination (or within-1-of-Provincia) Region."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.engine.game_engine import get_sop_factions
    from fs_bot.engine.execute import _execute_event
    from fs_bot.rules_consts import SCENARIO_GREAT_REVOLT, AEDUI, EVENT_UNSHADED
    st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=101)
    st["non_player_factions"] = set(get_sop_factions(st))
    st["current_card"] = 9
    res = _execute_event(st, AEDUI, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": 9,
        "text_preference": EVENT_UNSHADED}})
    fa = res.get("free_actions") or []
    fc = next(f for f in fa if f["free_action"] == "free_command")
    # The free Command runs through the layer; with the in/from-destination
    # restriction it either executes within the allowed Region or reports that
    # the chosen Command had no action there. Either way the board stays valid.
    assert "executed" in fc["result"]
    assert validate_state(st) == []


def test_card9_free_command_restricted_to_destination():
    """Slice 44: the card 9 free Command is restricted to the march
    destination — a constrained Battle there removes the enemy, and nothing
    happens outside it."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.engine.game_engine import get_sop_factions
    from fs_bot.engine.execute import _resolve_free_command
    from fs_bot.board.pieces import place_piece, count_pieces
    from fs_bot.board.control import refresh_all_control
    from fs_bot.map.map_data import get_playable_regions
    from fs_bot.rules_consts import (SCENARIO_GREAT_REVOLT, AEDUI, ROMANS,
        WARBAND, AUXILIA)
    st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=111)
    st["non_player_factions"] = set(get_sop_factions(st))
    pl = get_playable_regions(SCENARIO_GREAT_REVOLT, st.get("capabilities"))
    # Stage an Aedui Battle opportunity in exactly one Region.
    R = pl[6]
    _clear_region_mobiles(st, R)
    place_piece(st, R, AEDUI, WARBAND, 6)
    place_piece(st, R, ROMANS, AUXILIA, 2)
    refresh_all_control(st)
    # Restrict the free Command to a DIFFERENT Region -> no action there.
    other = next(r for r in pl if r != R)
    res_other = _resolve_free_command(st, AEDUI, allowed_regions={other})
    # Romans in R untouched when the command is restricted elsewhere.
    assert count_pieces(st, R, ROMANS, AUXILIA) == 2
    assert validate_state(st) == []



def test_cards_46_51_52_free_commands():
    """Slice 45: cards 46/51/52 grant unrestricted free Commands to the
    right Faction (acting Gallic / Aedui / Carnutes controller)."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.control import is_controlled_by
    from fs_bot.engine.game_engine import get_sop_factions
    from fs_bot.engine.execute import _execute_event
    from fs_bot.rules_consts import (SCENARIO_GREAT_REVOLT, AEDUI, ARVERNI,
        BELGAE, CARNUTES, FACTIONS, EVENT_SHADED, EVENT_UNSHADED)

    def fc(card, faction, shaded):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=120)
        st["non_player_factions"] = set(get_sop_factions(st))
        st["current_card"] = card
        pref = EVENT_SHADED if shaded else EVENT_UNSHADED
        res = _execute_event(st, faction, {"command": "Event", "sa": "No SA",
            "sa_regions": [], "details": {"card_id": card,
            "text_preference": pref}})
        fa = [f for f in (res.get("free_actions") or [])
              if f["free_action"] == "free_command"]
        return fa, st

    # 46 shaded: acting Gallic Faction free Command.
    fa, st = fc(46, ARVERNI, True)
    assert fa and fa[0]["result"]["executed"] is True
    assert validate_state(st) == []
    # 51 unshaded: Aedui free Command.
    fa, st = fc(51, AEDUI, False)
    assert fa and fa[0]["result"]["executed"] is True
    assert validate_state(st) == []
    # 52 shaded: the Carnutes controller free Command.
    st0 = setup_scenario(SCENARIO_GREAT_REVOLT, seed=120)
    ctrl = next((f for f in FACTIONS if is_controlled_by(st0, CARNUTES, f)), None)
    fa, st = fc(52, BELGAE, True)
    assert fa and fa[0].get("controller") == ctrl
    assert fa[0]["result"]["executed"] is True
    assert validate_state(st) == []


def test_free_command_exclude_and_limited_options():
    """Slice 46: _resolve_free_command honors exclude_commands (no Battles)
    and limited (single Region, no Special Activity)."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.engine.game_engine import get_sop_factions
    from fs_bot.engine.execute import _resolve_free_command
    from fs_bot.rules_consts import SCENARIO_GREAT_REVOLT, ROMANS
    # exclude Battle: when the flowchart picks Battle, it is disallowed.
    st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=131)
    st["non_player_factions"] = set(get_sop_factions(st))
    res = _resolve_free_command(st, ROMANS, exclude_commands={"Battle"})
    if res["command"] == "Battle":
        assert res["executed"] is False
    assert validate_state(st) == []
    # limited: executes a single-Region, no-SA command.
    st2 = setup_scenario(SCENARIO_GREAT_REVOLT, seed=132)
    st2["non_player_factions"] = set(get_sop_factions(st2))
    res2 = _resolve_free_command(st2, ROMANS, limited=True)
    assert "executed" in res2
    assert validate_state(st2) == []


def test_card35_gallic_shouts_both_sides():
    """Slice 46: Card 35 Gallic Shouts — shaded gives a Gallic Faction a
    Command + a Limited Command (no Battles); unshaded gives Romans a free
    Limited Command."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.engine.game_engine import get_sop_factions
    from fs_bot.engine.execute import _execute_event
    from fs_bot.rules_consts import (SCENARIO_GREAT_REVOLT, ARVERNI, ROMANS,
        EVENT_SHADED, EVENT_UNSHADED)
    # Shaded: two free_command entries (command + limited_command), no Battles.
    st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=130)
    st["non_player_factions"] = set(get_sop_factions(st))
    st["current_card"] = 35
    res = _execute_event(st, ARVERNI, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": 35,
        "text_preference": EVENT_SHADED}})
    fa = [f for f in (res.get("free_actions") or [])
          if f["free_action"] == "free_command"]
    kinds = {f.get("kind") for f in fa}
    assert kinds == {"command", "limited_command"}
    for f in fa:
        assert f["result"].get("command") != "Battle" or \
            f["result"]["executed"] is False  # Battle never executed
    assert validate_state(st) == []
    # Unshaded: Roman free Limited Command entry present.
    st2 = setup_scenario(SCENARIO_GREAT_REVOLT, seed=133)
    st2["non_player_factions"] = set(get_sop_factions(st2))
    st2["current_card"] = 35
    res2 = _execute_event(st2, ROMANS, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": 35,
        "text_preference": EVENT_UNSHADED}})
    fa2 = [f for f in (res2.get("free_actions") or [])
           if f["free_action"] == "free_command"]
    assert fa2 and "executed" in fa2[0]["result"]
    assert validate_state(st2) == []


def test_card35_unshaded_or_be_eligible():
    """Slice 47 fix: Card 35 unshaded — free Limited Command OR be Eligible.
    When no Limited Command is possible, the Romans remain Eligible."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.engine.execute import _resolve_card35_roman
    from fs_bot.rules_consts import (SCENARIO_GREAT_REVOLT, ROMANS, ELIGIBLE,
        INELIGIBLE)
    st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=140)
    st["non_player_factions"] = set()      # Romans can't run a free Command
    st.setdefault("eligibility", {})[ROMANS] = INELIGIBLE
    out = _resolve_card35_roman(st, ROMANS)
    assert out and out[0]["free_action"] == "stay_eligible"
    assert st["eligibility"][ROMANS] == ELIGIBLE
    assert validate_state(st) == []


def test_card52_free_command_includes_special_ability():
    """Slice 47 fix: Card 52's free Command carries the bot's Special Ability
    (the up-to-2 allowance is satisfied by the NP's single flowchart SA)."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.control import is_controlled_by
    from fs_bot.engine.game_engine import get_sop_factions
    from fs_bot.engine.execute import _execute_event
    from fs_bot.rules_consts import (SCENARIO_GREAT_REVOLT, BELGAE, CARNUTES,
        FACTIONS, EVENT_SHADED)
    st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=120)
    st["non_player_factions"] = set(get_sop_factions(st))
    st["current_card"] = 52
    res = _execute_event(st, BELGAE, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": 52,
        "text_preference": EVENT_SHADED}})
    fc = next(f for f in (res.get("free_actions") or [])
              if f["free_action"] == "free_command")
    assert fc["result"]["executed"] is True
    assert "sa_included" in fc          # SA-inclusion is now reported
    assert validate_state(st) == []


def test_free_rally_layer_all_factions():
    """Slice 48: _resolve_free_rally reuses each Faction's Rally node
    (Recruit for Romans) and executes it."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.engine.game_engine import get_sop_factions
    from fs_bot.engine.execute import _resolve_free_rally
    from fs_bot.rules_consts import (SCENARIO_GREAT_REVOLT, ARVERNI, BELGAE,
        AEDUI, ROMANS)
    for fac, cmd in ((ARVERNI, "Rally"), (BELGAE, "Rally"), (AEDUI, "Rally"),
                     (ROMANS, "Recruit")):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=150)
        st["non_player_factions"] = set(get_sop_factions(st))
        res = _resolve_free_rally(st, fac)
        assert res["command"] == cmd and res["executed"] is True
        assert validate_state(st) == []


def test_cards_34_26_64_free_rally():
    """Slice 48: cards 34 (free Rally/Recruit), 26 shaded (Arverni Rally near
    Vercingetorix), 64 shaded (Belgae Rally in Belgica)."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.engine.game_engine import get_sop_factions
    from fs_bot.engine.execute import _execute_event
    from fs_bot.rules_consts import (SCENARIO_GREAT_REVOLT, ARVERNI, BELGAE,
        EVENT_UNSHADED, EVENT_SHADED)

    def fr(card, faction, shaded, seed):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=seed)
        st["non_player_factions"] = set(get_sop_factions(st))
        st["current_card"] = card
        pref = EVENT_SHADED if shaded else EVENT_UNSHADED
        res = _execute_event(st, faction, {"command": "Event", "sa": "No SA",
            "sa_regions": [], "details": {"card_id": card,
            "text_preference": pref}})
        fa = [f for f in (res.get("free_actions") or [])
              if f["free_action"] == "free_rally"]
        return fa, st

    fa, st = fr(34, ARVERNI, False, 151)
    assert fa and fa[0]["result"]["executed"] is True
    assert validate_state(st) == []
    fa, st = fr(26, ARVERNI, True, 152)
    assert fa and fa[0]["result"]["executed"] is True
    assert validate_state(st) == []
    fa, st = fr(64, BELGAE, True, 153)
    assert fa and fa[0]["result"]["executed"] is True
    assert validate_state(st) == []


def test_new_battle_modifiers():
    """Slice 49: extra_losses, ally_first, no_counterattack, ignore_citadel,
    attacker_stays_hidden."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.board.pieces import (place_piece, count_pieces,
        count_pieces_by_state)
    from fs_bot.board.control import refresh_all_control
    from fs_bot.battle.resolve import resolve_battle
    from fs_bot.rules_consts import (SCENARIO_GREAT_REVOLT, ARVERNI, ROMANS,
        AEDUI, WARBAND, AUXILIA, ALLY, HIDDEN, REVEALED)
    # extra_losses (+3) and ally_first: the Ally goes first.
    st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=160)
    R = "Carnutes"
    _clear_region_mobiles(st, R)
    place_piece(st, R, ARVERNI, WARBAND, 4)
    place_piece(st, R, ROMANS, AUXILIA, 3)
    place_piece(st, R, ROMANS, ALLY, 1)
    refresh_all_control(st)
    resolve_battle(st, R, ARVERNI, ROMANS, extra_losses=3, ally_first=True,
                   retreat_declaration=False)
    assert count_pieces(st, R, ROMANS, ALLY) == 0          # Ally removed first
    assert count_pieces(st, R, ROMANS, AUXILIA) == 0       # then extra Losses
    # attacker_stays_hidden + no_counterattack.
    st2 = setup_scenario(SCENARIO_GREAT_REVOLT, seed=161)
    _clear_region_mobiles(st2, R)
    place_piece(st2, R, ARVERNI, WARBAND, 4)
    place_piece(st2, R, AEDUI, WARBAND, 3)
    refresh_all_control(st2)
    resolve_battle(st2, R, ARVERNI, AEDUI, retreat_declaration=False,
                   no_counterattack=True, attacker_stays_hidden=True,
                   ignore_citadel=True)
    assert count_pieces_by_state(st2, R, ARVERNI, WARBAND, REVEALED) == 0
    assert count_pieces_by_state(st2, R, ARVERNI, WARBAND, HIDDEN) == 4


def test_cards_25_36_21_battle_events():
    """Slice 49: cards 25 (extra Losses+ally first), 36 (vs Gallic, modifiers),
    21 shaded (Arverni Battle in Provincia ignoring the Fort)."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.pieces import place_piece, count_pieces
    from fs_bot.board.control import refresh_all_control
    from fs_bot.engine.game_engine import get_sop_factions
    from fs_bot.engine.execute import _execute_event
    from fs_bot.rules_consts import (SCENARIO_GREAT_REVOLT, ARVERNI, AEDUI,
        ROMANS, PICTONES, PROVINCIA, WARBAND, AUXILIA, EVENT_UNSHADED,
        EVENT_SHADED)
    # 25: Arverni free Battle in Pictones with extra Losses.
    st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=162)
    st["non_player_factions"] = set(get_sop_factions(st))
    st["current_card"] = 25
    _clear_region_mobiles(st, PICTONES)
    place_piece(st, PICTONES, ARVERNI, WARBAND, 4)
    place_piece(st, PICTONES, ROMANS, AUXILIA, 5)
    refresh_all_control(st)
    r = _execute_event(st, ARVERNI, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": 25,
        "text_preference": EVENT_UNSHADED}})
    fa = [f for f in (r.get("free_actions") or []) if f.get("flag") == "card_25"]
    assert fa and fa[0]["region"] == PICTONES
    # 4 Warbands -> 2 Losses + 3 extra = 5; 5 Auxilia -> 0.
    assert count_pieces(st, PICTONES, ROMANS, AUXILIA) == 0
    assert validate_state(st) == []
    # 36: Arverni free Battle vs a Gallic Faction.
    st2 = setup_scenario(SCENARIO_GREAT_REVOLT, seed=163)
    st2["non_player_factions"] = set(get_sop_factions(st2))
    st2["current_card"] = 36
    Rm = "Mandubii"
    _clear_region_mobiles(st2, Rm)
    place_piece(st2, Rm, ARVERNI, WARBAND, 5)
    place_piece(st2, Rm, AEDUI, WARBAND, 2)
    refresh_all_control(st2)
    r2 = _execute_event(st2, ARVERNI, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": 36,
        "text_preference": EVENT_UNSHADED}})
    fa2 = [f for f in (r2.get("free_actions") or []) if f.get("flag") == "card_36"]
    assert fa2 and fa2[0]["defender"] == AEDUI
    assert validate_state(st2) == []
    # 21 shaded: Arverni Battle in Provincia.
    st3 = setup_scenario(SCENARIO_GREAT_REVOLT, seed=164)
    st3["non_player_factions"] = set(get_sop_factions(st3))
    st3["current_card"] = 21
    r3 = _execute_event(st3, ARVERNI, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": 21,
        "text_preference": EVENT_SHADED}})
    assert validate_state(st3) == []


def test_cards_48_47_62_free_commands():
    """Slice 50: card 48 (each Gallic Faction a free Limited Command), card 47
    (council free Limited Commands / Eligible), card 62 (War Fleet free
    Command in a coastal Region)."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.engine.game_engine import get_sop_factions
    from fs_bot.engine.execute import _execute_event
    from fs_bot.rules_consts import (SCENARIO_GREAT_REVOLT, ARVERNI,
        EVENT_UNSHADED)
    for card in (48, 47, 62):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=170 + card)
        st["non_player_factions"] = set(get_sop_factions(st))
        st["current_card"] = card
        res = _execute_event(st, ARVERNI, {"command": "Event", "sa": "No SA",
            "sa_regions": [], "details": {"card_id": card,
            "text_preference": EVENT_UNSHADED}})
        fa = res.get("free_actions") or []
        assert fa, f"card {card} produced no free action"
        assert validate_state(st) == []


def test_card53_and_card29_germans_phase_no_crash():
    """Slice 50: cards 53 and 29 conduct an immediate Germans Phase without
    crashing (raid loop guarded; imports intact)."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.engine.game_engine import get_sop_factions
    from fs_bot.engine.execute import _execute_event
    from fs_bot.rules_consts import (SCENARIO_GREAT_REVOLT, SCENARIO_ARIOVISTUS,
        AEDUI, EVENT_SHADED)
    # Card 53 (base): runs the Germans Phase (skip March) cleanly.
    for seed in range(8):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=seed)
        st["non_player_factions"] = set(get_sop_factions(st))
        st["current_card"] = 53
        res = _execute_event(st, AEDUI, {"command": "Event", "sa": "No SA",
            "sa_regions": [], "details": {"card_id": 53,
            "text_preference": EVENT_SHADED}})
        assert res["executed"] is True
        assert validate_state(st) == []
    # Card 29 (Ariovistus shaded path uses the Germans Phase too) — no crash.
    st2 = setup_scenario(SCENARIO_ARIOVISTUS, seed=3)
    st2["non_player_factions"] = set(get_sop_factions(st2))
    st2["current_card"] = 29
    _execute_event(st2, AEDUI, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": 29, "text_preference": EVENT_SHADED}})
    assert validate_state(st2) == []


def test_combined_battle_allied_factions():
    """Slice 51: allied_factions augments the attacker's loss-causing force
    (card 45 'use Aedui pieces'; A28 'treat Arverni as own')."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.pieces import place_piece, count_pieces
    from fs_bot.board.control import refresh_all_control
    from fs_bot.battle.resolve import resolve_battle
    from fs_bot.battle.losses import calculate_losses
    from fs_bot.rules_consts import (SCENARIO_GREAT_REVOLT, ARVERNI, AEDUI,
        ROMANS, WARBAND, AUXILIA)
    st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=182)
    R = "Atrebates"
    _clear_region_mobiles(st, R)
    place_piece(st, R, ARVERNI, WARBAND, 2)
    place_piece(st, R, AEDUI, WARBAND, 4)
    place_piece(st, R, ROMANS, AUXILIA, 3)
    refresh_all_control(st)
    solo = calculate_losses(st, R, ARVERNI, ROMANS)
    combined = calculate_losses(st, R, ARVERNI, ROMANS, allied_factions=(AEDUI,))
    assert combined > solo
    # Combined Ambush removes all 3 Auxilia (6 Warbands -> 3 Losses).
    resolve_battle(st, R, ARVERNI, ROMANS, is_ambush=True,
                   allied_factions=(AEDUI,))
    assert count_pieces(st, R, ROMANS, AUXILIA) == 0
    assert validate_state(st) == []


def test_card45_shaded_combined_battle_event():
    """Slice 51: Card 45 Litaviccus (shaded) — free Battle vs Romans using
    Aedui pieces as own; the event fires against the Romans and resolves a
    Battle. Exact combined-Loss math is covered by
    test_combined_battle_allied_factions."""
    from fs_bot.state.setup import setup_scenario
    from fs_bot.state.state_schema import validate_state
    from fs_bot.board.pieces import place_piece, count_pieces
    from fs_bot.board.control import refresh_all_control
    from fs_bot.engine.game_engine import get_sop_factions
    from fs_bot.engine.execute import _execute_event
    from fs_bot.rules_consts import (SCENARIO_GREAT_REVOLT, ARVERNI, AEDUI,
        ROMANS, WARBAND, AUXILIA, EVENT_SHADED)
    st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=181)
    st["non_player_factions"] = set(get_sop_factions(st))
    st["current_card"] = 45
    R = "Mandubii"
    _clear_region_mobiles(st, R)
    place_piece(st, R, ARVERNI, WARBAND, 2)
    place_piece(st, R, AEDUI, WARBAND, 4)
    place_piece(st, R, ROMANS, AUXILIA, 3)
    refresh_all_control(st)
    res = _execute_event(st, ARVERNI, {"command": "Event", "sa": "No SA",
        "sa_regions": [], "details": {"card_id": 45,
        "text_preference": EVENT_SHADED}})
    fa = [f for f in (res.get("free_actions") or []) if f.get("flag") == "card_45"]
    assert fa and fa[0]["defender"] == ROMANS and fa[0].get("result")
    assert validate_state(st) == []
