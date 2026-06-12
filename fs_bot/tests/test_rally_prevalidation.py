"""Regression tests: Rally planners propose only executor-legal plans.

QUESTIONS.md "OPEN — planner quality" backlog: the published-bot Rally
planners proposed sub-actions the executor legally refused (Rally regions
with no Control/Ally/Citadel/Leader/Rally-symbol, Ally placement without
Control, plans with 0 Resources). The fix routes every draft rally_plan
through bot_common.prevalidate_rally_plan, which applies the executor's own
checks (fs_bot.commands.rally) in execution order.
"""
import pytest

from fs_bot.rules_consts import (
    SCENARIO_PAX_GALLICA, SCENARIO_ARIOVISTUS,
    AEDUI, ARVERNI, BELGAE, GERMANS, ROMANS,
    AEDUI_REGION, ARVERNI_REGION, MANDUBII, SEQUANI, TREVERI, ATREBATES,
    SUGAMBRI, UBII,
    WARBAND, ALLY, CITADEL, HIDDEN,
    VERCINGETORIX,
)
from fs_bot.state.state_schema import build_initial_state
from fs_bot.board.pieces import place_piece, count_pieces, get_available
from fs_bot.board.control import refresh_all_control
from fs_bot.bots.bot_common import prevalidate_rally_plan
from fs_bot.bots.aedui_bot import ACTION_RALLY
from fs_bot.engine.execute import execute_decision


def _state(scenario=SCENARIO_PAX_GALLICA, seed=7):
    st = build_initial_state(scenario, seed=seed)
    st["non_player_factions"] = {ROMANS, ARVERNI, BELGAE, AEDUI, GERMANS}
    st["can_play_event"] = False
    st["current_card_id"] = 1
    st["final_year"] = False
    st["frost"] = False
    st["is_second_eligible"] = False
    return st


class TestPrevalidateRallyPlan:
    def test_zero_resources_drops_all_paid_entries(self):
        st = _state()
        st["resources"][AEDUI] = 0
        place_piece(st, AEDUI_REGION, AEDUI, ALLY)
        st["tribes"]["Aedui"]["allied_faction"] = AEDUI
        refresh_all_control(st)
        plan = prevalidate_rally_plan(
            st, AEDUI, {"citadels": [], "allies": [],
                        "warbands": [AEDUI_REGION]})
        assert plan["warbands"] == []

    def test_ally_without_control_dropped(self):
        st = _state()
        st["resources"][BELGAE] = 10
        # Mandubii: no Belgic pieces at all -> no Control, illegal region
        plan = prevalidate_rally_plan(
            st, BELGAE,
            {"citadels": [],
             "allies": [{"region": MANDUBII, "tribe": "Mandubii"}],
             "warbands": []})
        assert plan["allies"] == []

    def test_budget_spent_in_plan_order(self):
        st = _state()
        st["resources"][AEDUI] = 1
        for region, tribe in ((AEDUI_REGION, "Aedui"), (SEQUANI, "Sequani")):
            place_piece(st, region, AEDUI, ALLY)
            st["tribes"][tribe]["allied_faction"] = AEDUI
        refresh_all_control(st)
        plan = prevalidate_rally_plan(
            st, AEDUI, {"citadels": [], "allies": [],
                        "warbands": [AEDUI_REGION, SEQUANI]})
        # 1 Resource pays for exactly the first region
        assert plan["warbands"] == [AEDUI_REGION]

    def test_citadel_frees_ally_for_reuse(self):
        st = _state()
        st["resources"][ARVERNI] = 10
        # Allied City tribe (Arverni @ Gergovia is a City tribe)
        place_piece(st, ARVERNI_REGION, ARVERNI, ALLY)
        st["tribes"]["Arverni"]["allied_faction"] = ARVERNI
        place_piece(st, ARVERNI_REGION, ARVERNI, WARBAND, 4,
                    piece_state=HIDDEN)
        refresh_all_control(st)
        # Drain the Available Ally pool so only the freed Ally can serve
        avail = get_available(st, ARVERNI, ALLY)
        spare_tribes = [t for t, info in st["tribes"].items()
                        if info.get("allied_faction") is None][:avail]
        for t in spare_tribes:
            st["tribes"][t]["allied_faction"] = "parked"
        st["available"][ARVERNI][ALLY] = 0
        plan_in = {
            "citadels": [{"region": ARVERNI_REGION, "tribe": "Arverni"}],
            "allies": [{"region": ARVERNI_REGION, "tribe": "Cadurci"}],
            "warbands": [],
        }
        plan = prevalidate_rally_plan(st, ARVERNI, plan_in)
        assert plan["citadels"] == plan_in["citadels"]
        # The Citadel replacement frees its Ally back to Available,
        # funding the Cadurci placement
        assert plan["allies"] == plan_in["allies"]

    def test_citadel_not_reproposed_when_tribe_allied_via_citadel(self):
        st = _state()
        st["resources"][ARVERNI] = 10
        # City tribe allied via a CITADEL (Ally already replaced earlier)
        place_piece(st, ARVERNI_REGION, ARVERNI, CITADEL)
        st["tribes"]["Arverni"]["allied_faction"] = ARVERNI
        refresh_all_control(st)
        plan = prevalidate_rally_plan(
            st, ARVERNI,
            {"citadels": [{"region": ARVERNI_REGION, "tribe": "Arverni"}],
             "allies": [], "warbands": []})
        # No Ally disc to replace — executor would refuse; entry dropped
        assert plan["citadels"] == []

    def test_german_home_minimum_kept_without_ally(self):
        st = _state(SCENARIO_ARIOVISTUS)
        st["resources"][GERMANS] = 10
        plan = prevalidate_rally_plan(
            st, GERMANS, {"citadels": [], "allies": [],
                          "warbands": [SUGAMBRI]})
        # Sugambri is a Germania home region: 1 Warband min — §3.4.1
        assert plan["warbands"] == [SUGAMBRI]

    def test_non_home_no_base_warbands_dropped(self):
        st = _state()
        st["resources"][BELGAE] = 10
        place_piece(st, TREVERI, BELGAE, WARBAND, 6, piece_state=HIDDEN)
        refresh_all_control(st)  # Control but no Ally/Citadel, not home
        plan = prevalidate_rally_plan(
            st, BELGAE, {"citadels": [], "allies": [],
                         "warbands": [TREVERI]})
        assert plan["warbands"] == []


class TestPlannersExecuteCleanly:
    """End-to-end: each bot's Rally node output executes with no errors."""

    @pytest.mark.parametrize("faction,module,node", [
        (AEDUI, "fs_bot.bots.aedui_bot", "node_a_rally"),
        (BELGAE, "fs_bot.bots.belgae_bot", "node_b_rally"),
        (ARVERNI, "fs_bot.bots.arverni_bot", "node_v_rally"),
    ])
    def test_rally_node_zero_resources_never_proposes_paid_rally(
            self, faction, module, node):
        import importlib
        st = _state()
        st["resources"][faction] = 0
        place_piece(st, ATREBATES, faction, ALLY)
        st["tribes"]["Atrebates"]["allied_faction"] = faction
        refresh_all_control(st)
        action = getattr(importlib.import_module(module), node)(st)
        if action.get("command") == ACTION_RALLY:
            rp = action["details"]["rally_plan"]
            assert not (rp.get("citadels") or rp.get("allies")
                        or rp.get("warbands"))
        # else: flowchart fell through to its IF-NONE branch — correct.

    def test_aedui_rally_plan_executes_without_errors(self):
        st = _state()
        st["resources"][AEDUI] = 6
        place_piece(st, AEDUI_REGION, AEDUI, ALLY)
        st["tribes"]["Aedui"]["allied_faction"] = AEDUI
        place_piece(st, AEDUI_REGION, AEDUI, WARBAND, 6, piece_state=HIDDEN)
        refresh_all_control(st)
        from fs_bot.bots.aedui_bot import node_a_rally
        action = node_a_rally(st)
        assert action.get("command") == ACTION_RALLY
        res = execute_decision(st, AEDUI, {"bot_action": action})
        assert res["executed"]
        assert res["errors"] == []


class TestControlFlagFreshness:
    """Piece operations keep space['control'] equal to calculate_control —
    §1.6 / CLAUDE.md 'Piece Operations'. Regression for the stale-flag
    family: the bot March path (march_group called directly) and many Event
    handlers mutated pieces without a refresh, so planners read stale
    Control (e.g. an Aedui Rally place_ally kept by prevalidation, then
    refused by the executor after an Arverni March had really flipped the
    Region)."""

    def test_place_remove_move_refresh_control(self):
        from fs_bot.board.control import calculate_control
        from fs_bot.board.pieces import remove_piece, move_piece
        st = _state()
        # place: empty region -> Belgae control
        place_piece(st, TREVERI, BELGAE, WARBAND, 2, piece_state=HIDDEN)
        assert st["spaces"][TREVERI]["control"] == \
            calculate_control(st, TREVERI)
        # move: both regions refreshed
        move_piece(st, TREVERI, ATREBATES, BELGAE, WARBAND, count=2,
                   piece_state=HIDDEN)
        for reg in (TREVERI, ATREBATES):
            assert st["spaces"][reg]["control"] == calculate_control(st, reg)
        # remove: refreshed again
        remove_piece(st, ATREBATES, BELGAE, WARBAND, 2)
        assert st["spaces"][ATREBATES]["control"] == \
            calculate_control(st, ATREBATES)

    def test_bot_game_control_flags_stay_fresh(self):
        """Canary: all-bot game, every decision boundary, every playable
        Region — stored flag matches recomputation."""
        import contextlib, io
        from fs_bot.state.setup import setup_scenario
        from fs_bot.engine.game_engine import (run_game, ACTION_EVENT,
                                               get_sop_factions)
        from fs_bot.bots.bot_dispatch import dispatch_bot_turn
        from fs_bot.cli.dispatcher import _translate_bot_action
        from fs_bot.board.control import calculate_control
        from fs_bot.map.map_data import get_playable_regions
        from fs_bot.rules_consts import SCENARIO_RECONQUEST

        stale = []
        st = setup_scenario(SCENARIO_RECONQUEST, seed=3)
        st["non_player_factions"] = set(get_sop_factions(st))

        def df(state, faction, options, position):
            for region in get_playable_regions(state["scenario"],
                                               state.get("capabilities")):
                sp = state["spaces"][region]
                calc = calculate_control(state, region)
                if sp.get("control") != calc:
                    stale.append((state.get("current_card"), region,
                                  sp.get("control"), calc))
            state["current_card_id"] = state.get("current_card")
            state["is_second_eligible"] = (position == "2nd_eligible")
            state["can_play_event"] = (ACTION_EVENT in options)
            ba = dispatch_bot_turn(state, faction)
            return {"action": _translate_bot_action(ba, options),
                    "bot_action": ba}

        with contextlib.redirect_stdout(io.StringIO()):
            run_game(st, decision_func=df, execute=True)
        assert stale == [], f"stale Control flags: {stale[:5]}"
