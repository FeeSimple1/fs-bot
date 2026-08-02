"""Human plan-collection menu — Phase 6 mixed human/bot turns.

Drives collect_player_action / prompt_action with scripted stdin (io.StringIO),
asserts the collected player_action plan shape, and confirms execute_decision
runs it through the same machinery as a bot turn.
"""

import io

from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import validate_state
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import (
    ACTION_COMMAND, ACTION_COMMAND_SA, ACTION_EVENT, get_sop_factions,
)
from fs_bot.cli.human_plan import collect_player_action, _regions_with_pieces
from fs_bot.cli.menus import prompt_action
from fs_bot.commands.seize import count_dispersed_on_map, get_dispersible_tribes
from fs_bot.map.map_data import get_playable_regions
from fs_bot.board.pieces import count_pieces
from fs_bot.rules_consts import (
    SCENARIO_GREAT_REVOLT, ROMANS, AEDUI, EVENT_UNSHADED, EVENT_SHADED,
)


def _io(lines):
    return io.StringIO("".join(l + "\n" for l in lines)), io.StringIO()


class TestHumanPlanCollection:
    def test_gallic_rally_warbands_plan_executes(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        st["non_player_factions"] = set(get_sop_factions(st))
        st["resources"][AEDUI] = 10
        regions = _regions_with_pieces(st, AEDUI)
        region = regions[0]
        # Rally(1); pick first Region(1); (done) if >1 Region; Warbands(1).
        seq = ["1", "1"] + ([str(len(regions))] if len(regions) > 1 else []) + ["1"]
        stdin, stdout = _io(seq)
        action = collect_player_action(st, AEDUI, ACTION_COMMAND, stdin, stdout)
        assert action["command"] == "Rally"
        assert region in action["details"]["rally_plan"]["warbands"]
        before = count_pieces(st, region, AEDUI, "Warband")
        res = execute_decision(st, AEDUI, {"player_action": action})
        assert res["executed"] is True
        assert count_pieces(st, region, AEDUI, "Warband") > before
        assert validate_state(st) == []

    def test_roman_seize_plan_executes(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        st["non_player_factions"] = set(get_sop_factions(st))
        # First Region (option 1) where Romans have pieces & a dispersible tribe.
        cand = [r for r in get_playable_regions(st["scenario"], st.get("capabilities"))
                if count_pieces(st, r, ROMANS) > 0 and get_dispersible_tribes(st, r)]
        assert cand
        target = cand[0]
        rom_regions = [r for r in get_playable_regions(st["scenario"], st.get("capabilities"))
                       if count_pieces(st, r, ROMANS) > 0]
        pick_idx = rom_regions.index(target) + 1
        # Seize(3); pick target Region; (done)=len after one pick if >1; disperse y.
        seq = ["3", str(pick_idx)]
        if len(rom_regions) > 1:
            seq.append(str(len(rom_regions)))
        seq.append("y")
        stdin, stdout = _io(seq)
        action = collect_player_action(st, ROMANS, ACTION_COMMAND, stdin, stdout)
        assert action["command"] == "Seize"
        assert target in action["regions"]
        before = count_dispersed_on_map(st)
        res = execute_decision(st, ROMANS, {"player_action": action})
        assert res["executed"] is True
        assert count_dispersed_on_map(st) >= before
        assert validate_state(st) == []

    def test_event_side_choice(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        stdin, stdout = _io(["2"])  # Shaded = option 2
        action = collect_player_action(st, AEDUI, ACTION_EVENT, stdin, stdout)
        assert action["command"] == "Event"
        assert action["details"]["text_preference"] == EVENT_SHADED
        assert action["details"]["card_id"] == st.get("current_card")

    def test_prompt_action_attaches_player_action(self):
        # End to end: prompt_action returns the engine action + the plan.
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        st["non_player_factions"] = set(get_sop_factions(st))
        st["resources"][AEDUI] = 10
        options = [ACTION_COMMAND, ACTION_EVENT]
        regions = _regions_with_pieces(st, AEDUI)
        # Action=Command(1); Rally(1); first Region(1); (done) if >1; Warbands(1).
        seq = ["1", "1", "1"] + ([str(len(regions))] if len(regions) > 1 else []) + ["1"]
        stdin, stdout = _io(seq)
        decision = prompt_action(st, AEDUI, options, "1st_eligible", stdin, stdout)
        assert decision["action"] == ACTION_COMMAND
        assert "player_action" in decision
        assert decision["player_action"]["command"] == "Rally"

    def test_march_routes_chained_origins(self):
        # Per-origin destination prompts emit exact routes, including a
        # chained march (A -> B while B -> C) that the pooled-destination
        # shape could not express.
        import fs_bot.rules_consts as rc
        from fs_bot.map.map_data import get_adjacent
        from fs_bot.cli.human_plan import _collect_march
        from fs_bot.board.pieces import place_piece
        st = setup_scenario(rc.SCENARIO_ARIOVISTUS, seed=5)
        st["non_player_factions"] = set(get_sop_factions(st))
        st["resources"][rc.GERMANS] = 20
        a, b = rc.UBII, rc.TREVERI
        place_piece(st, a, rc.GERMANS, "Warband", count=3)
        place_piece(st, b, rc.GERMANS, "Warband", count=3)
        origins = [r for r in _regions_with_pieces(st, rc.GERMANS)]
        ia = origins.index(a) + 1
        rem = [r for r in origins if r != a]          # menu renumbers
        ib = rem.index(b) + 1
        done = (len(origins) - 2) + 1                 # remaining + "(done)"
        adj_a = sorted(get_adjacent(a, st["scenario"]))
        adj_b = sorted(get_adjacent(b, st["scenario"]))
        da = adj_a.index(b) + 1                       # Ubii -> Treveri
        c = [r for r in adj_b if r != a][0]           # Treveri -> not-Ubii
        db = adj_b.index(c) + 1
        # pick origins a, b, done; dest per origin; all pieces, no partials.
        seq = [str(ia), str(ib), str(done), str(da), str(db)]
        # group prompts: for each origin, one count prompt per present piece
        # type ("all") + leader y/n where present.
        for o in (a, b):
            for pt in ("Legion", "Auxilia", "Warband"):
                if count_pieces(st, o, rc.GERMANS, pt) > 0:
                    seq.append("1")  # "all N"
            from fs_bot.board.pieces import get_leader_in_region
            if get_leader_in_region(st, o, rc.GERMANS) is not None:
                seq.append("y")
        stdin, stdout = _io(seq)
        plan = _collect_march(st, rc.GERMANS, stdin, stdout, single=False)
        assert plan is not None
        assert plan["routes"][a] == [b]
        assert plan["routes"][b] == [c]
        assert b in plan["destinations"]  # an origin can be a destination

    def test_pass_returns_no_plan(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        from fs_bot.engine.game_engine import ACTION_PASS
        action = collect_player_action(st, AEDUI, ACTION_PASS,
                                       io.StringIO(), io.StringIO())
        assert action is None

    def test_player_build_plan_overrides_bot(self):
        # The executor must honor a player-supplied build_plan instead of
        # recomputing node_r_build (the old Quarters-class gap).
        import fs_bot.rules_consts as rc
        from fs_bot.engine.execute import _execute_build
        from fs_bot.board.pieces import place_piece, count_pieces
        from fs_bot.board.control import refresh_all_control
        st = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=3)
        st["non_player_factions"] = set()
        from fs_bot.board.pieces import find_leader
        from fs_bot.map.map_data import get_adjacent
        caesar = find_leader(st, rc.ROMANS)          # Provincia (has Fort)
        r = sorted(get_adjacent(caesar, st["scenario"]))[0]
        # Roman Ally makes the region Build-eligible (§4.2.1) regardless
        # of Supply Lines; tribe record kept in sync.
        for t, ti in st["tribes"].items():
            if (ti.get("allied_faction") is None and ti.get("status") is None
                    and rc.TRIBE_TO_REGION.get(t) == r):
                ti["allied_faction"] = rc.ROMANS
                place_piece(st, r, rc.ROMANS, rc.ALLY)
                break
        refresh_all_control(st)
        forts0 = count_pieces(st, r, rc.ROMANS, rc.FORT)
        res = _execute_build(st, rc.ROMANS, {
            "sa": "Build", "details": {"build_plan": {
                "forts": [r], "subdue": [], "allies": []}}})
        assert res["executed"], res
        assert count_pieces(st, r, rc.ROMANS, rc.FORT) == forts0 + 1
        assert ("fort", r) in res["actions"]

    def test_player_scout_plan_overrides_bot(self):
        import fs_bot.rules_consts as rc
        from fs_bot.engine.execute import _execute_scout
        from fs_bot.board.pieces import place_piece, count_pieces
        st = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=3)
        st["non_player_factions"] = set()
        a, b = rc.MANDUBII, rc.ATREBATES
        place_piece(st, a, rc.ROMANS, rc.AUXILIA, 3)
        n0 = count_pieces(st, b, rc.ROMANS, rc.AUXILIA)
        res = _execute_scout(st, rc.ROMANS, {
            "sa": "Scout", "details": {"scout_plan": {
                "auxilia_moves": [{"from_region": a, "to_region": b,
                                   "count": 2, "piece_state": "Hidden"}],
                "scout_targets": []}}})
        assert res["executed"], res
        assert count_pieces(st, b, rc.ROMANS, rc.AUXILIA) == n0 + 2

    def test_march_extra_group_splits_one_origin(self):
        # §3.3.2: two groups from one origin to different destinations.
        import fs_bot.rules_consts as rc
        from fs_bot.engine.execute import execute_decision
        from fs_bot.board.pieces import place_piece, count_pieces
        from fs_bot.board.control import refresh_all_control
        st = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=5)
        st["non_player_factions"] = set()
        st["resources"][rc.BELGAE] = 10
        o = rc.MORINI
        place_piece(st, o, rc.BELGAE, rc.WARBAND, 6)
        refresh_all_control(st)
        n_atr = count_pieces(st, rc.ATREBATES, rc.BELGAE, rc.WARBAND)
        n_ner = count_pieces(st, rc.NERVII, rc.BELGAE, rc.WARBAND)
        res = execute_decision(st, rc.BELGAE, {"player_action": {
            "command": "March", "regions": [], "sa": "No SA",
            "sa_regions": [], "details": {
                "origins": [o], "destinations": [rc.ATREBATES],
                "routes": {o: [rc.ATREBATES]},
                "groups": {o: {"Warband": 3}},
                "extra_groups": [{"origin": o, "route": [rc.NERVII],
                                  "group": {"Warband": 2}}]}}})
        assert res["executed"], res
        assert (count_pieces(st, rc.ATREBATES, rc.BELGAE, rc.WARBAND)
                == n_atr + 3)
        assert (count_pieces(st, rc.NERVII, rc.BELGAE, rc.WARBAND)
                == n_ner + 2)

    def test_sa_collector_contract_build_scout(self):
        # Regression: Build/Scout collectors crashed live with
        # "_collect_build() missing 1 required positional argument" —
        # every _SA_COLLECTORS entry must accept (state, faction, stdin,
        # stdout) and return a (sa_regions, extra) tuple.
        import io as _io
        import inspect
        import fs_bot.rules_consts as rc
        from fs_bot.cli.human_plan import _SA_COLLECTORS
        from fs_bot.board.pieces import place_piece
        from fs_bot.board.control import refresh_all_control
        st = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=3)
        st["non_player_factions"] = set()
        for name, fn in _SA_COLLECTORS.items():
            sig = inspect.signature(fn)
            assert len(sig.parameters) == 4, (name, sig)
        # Drive Build end-to-end: pick 1st region, done, fort action.
        from fs_bot.board.pieces import find_leader
        from fs_bot.map.map_data import get_adjacent
        caesar = find_leader(st, rc.ROMANS)
        r = sorted(get_adjacent(caesar, st["scenario"]))[0]
        for t, ti in st["tribes"].items():
            if (ti.get("allied_faction") is None and ti.get("status") is None
                    and rc.TRIBE_TO_REGION.get(t) == r):
                ti["allied_faction"] = rc.ROMANS
                place_piece(st, r, rc.ROMANS, rc.ALLY)
                break
        refresh_all_control(st)
        stdin = _io.StringIO("1\n" * 8)
        out = _io.StringIO()
        result = _SA_COLLECTORS["Build"](st, rc.ROMANS, stdin, out)
        assert isinstance(result, tuple) and len(result) == 2
        sa_regions, extra = result
        if sa_regions is not None:
            assert isinstance(extra, dict) and "build_plan" in extra
        # Scout with no moves/targets must return the (None, None) shape.
        stdin = _io.StringIO("n\n" * 6)
        result = _SA_COLLECTORS["Scout"](st, rc.ROMANS, stdin, out)
        assert isinstance(result, tuple) and len(result) == 2
