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
    ACTION_COMMAND, ACTION_EVENT, get_sop_factions,
)
from fs_bot.cli.human_plan import collect_player_action, _regions_with_pieces
from fs_bot.cli.menus import prompt_action
from fs_bot.commands.seize import count_dispersed_on_map, get_dispersible_tribes
from fs_bot.map.map_data import get_playable_regions
from fs_bot.board.pieces import count_pieces
from fs_bot.rules_consts import (
    SCENARIO_GREAT_REVOLT, ROMANS, AEDUI, EVENT_SHADED,
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

    def test_pass_returns_no_plan(self):
        st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=3)
        from fs_bot.engine.game_engine import ACTION_PASS
        action = collect_player_action(st, AEDUI, ACTION_PASS,
                                       io.StringIO(), io.StringIO())
        assert action is None
