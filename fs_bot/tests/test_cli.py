"""Tests for fs_bot.cli — Phase 6.

Covers:
- Setup wizard scenario picker and faction-mode picker.
- prompt_choice / prompt_action / prompt_yes_no input validation.
- Dispatcher: bot path calls the actual bot; human path reads stdin.
- format_action covers Pass, Event, Battle, March, Rally, Raid.
- format_state_summary renders all 5 scenarios without exceptions.
- 2nd-Eligible LIMITED_COMMAND downgrade.
- Smoke test: non-interactive all-bot game plays through without crashing
  on the CLI/display side.
"""

import io
import sys

import pytest

from fs_bot.rules_consts import (
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    FACTIONS,
    SCENARIO_PAX_GALLICA, SCENARIO_RECONQUEST, SCENARIO_GREAT_REVOLT,
    SCENARIO_ARIOVISTUS, SCENARIO_GALLIC_WAR,
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS, ALL_SCENARIOS,
    MORINI, NERVII, ATREBATES, TREVERI,
)
from fs_bot.state.setup import setup_scenario
from fs_bot.engine.game_engine import (
    start_game, run_game,
    ACTION_COMMAND, ACTION_COMMAND_SA, ACTION_LIMITED_COMMAND,
    ACTION_EVENT, ACTION_PASS,
    get_first_eligible_options, get_second_eligible_options,
)
from fs_bot.cli.app import (
    main, setup_wizard, get_assignable_factions,
    display_card_result, _parse_args, _parse_bots_arg,
)
from fs_bot.cli.display import (
    format_state_summary, format_region_table, format_tribes_table,
    format_legions_track, format_card, format_action, format_victory_state,
)
from fs_bot.cli.menus import (
    prompt_choice, prompt_yes_no, prompt_action, ACTION_LABELS,
)
from fs_bot.cli.dispatcher import (
    make_decision_func, _translate_bot_action,
)


# ============================================================================
# get_assignable_factions — scenario isolation
# ============================================================================

class TestAssignableFactions:
    """get_assignable_factions excludes game-run factions per scenario."""

    def test_base_excludes_germans(self):
        for sc in BASE_SCENARIOS:
            assignable = get_assignable_factions(sc)
            assert GERMANS not in assignable, (
                f"Germans should be excluded in base scenario {sc} "
                f"(game-run via §6.2)"
            )
            assert ARVERNI in assignable, (
                f"Arverni should be assignable in base scenario {sc}"
            )

    def test_ariovistus_excludes_arverni(self):
        for sc in ARIOVISTUS_SCENARIOS:
            assignable = get_assignable_factions(sc)
            assert ARVERNI not in assignable, (
                f"Arverni should be excluded in Ariovistus {sc} "
                f"(game-run via A6.2)"
            )
            assert GERMANS in assignable, (
                f"Germans should be assignable in Ariovistus {sc}"
            )


# ============================================================================
# Setup wizard
# ============================================================================

class TestSetupWizard:
    """Setup wizard scenario picker + faction-mode picker."""

    def test_scenario_picker_accepts_legal_input(self):
        # Pax Gallica is option 1
        stdin = io.StringIO("1\n" + "2\n" * 4)  # scenario + 4 faction modes
        stdout = io.StringIO()
        sc, modes = setup_wizard(stdin, stdout)
        assert sc == SCENARIO_PAX_GALLICA
        # All 4 assignable picked option 2 = bot
        assert modes == {ROMANS: "bot", ARVERNI: "bot",
                         AEDUI: "bot", BELGAE: "bot"}

    def test_scenario_picker_rejects_bad_input_then_accepts(self):
        # First "abc" rejected, then "99" out of range, then "1" accepted
        stdin = io.StringIO("abc\n99\n1\n" + "2\n" * 4)
        stdout = io.StringIO()
        sc, _modes = setup_wizard(stdin, stdout)
        assert sc == SCENARIO_PAX_GALLICA
        text = stdout.getvalue()
        assert "Please enter" in text  # re-prompt happened

    def test_ariovistus_excludes_arverni_in_wizard(self):
        # Scenario 4 = Ariovistus; assignable = Romans, Germans, Aedui, Belgae
        stdin = io.StringIO("4\n" + "2\n" * 4)
        stdout = io.StringIO()
        sc, modes = setup_wizard(stdin, stdout)
        assert sc == SCENARIO_ARIOVISTUS
        assert ARVERNI not in modes
        assert GERMANS in modes
        assert set(modes.keys()) == {ROMANS, GERMANS, AEDUI, BELGAE}

    def test_base_excludes_germans_in_wizard(self):
        stdin = io.StringIO("1\n" + "2\n" * 4)
        stdout = io.StringIO()
        sc, modes = setup_wizard(stdin, stdout)
        assert sc == SCENARIO_PAX_GALLICA
        assert GERMANS not in modes
        assert ARVERNI in modes

    def test_preset_scenario_skips_question(self):
        stdin = io.StringIO("2\n" * 4)  # 4 faction modes only
        stdout = io.StringIO()
        sc, modes = setup_wizard(
            stdin, stdout, preset_scenario=SCENARIO_RECONQUEST,
        )
        assert sc == SCENARIO_RECONQUEST
        assert set(modes.keys()) == {ROMANS, ARVERNI, AEDUI, BELGAE}

    def test_preset_scenario_invalid_raises(self):
        with pytest.raises(ValueError):
            setup_wizard(
                io.StringIO(), io.StringIO(),
                preset_scenario="Not A Scenario",
            )

    def test_preset_faction_modes_skips_questions(self):
        stdin = io.StringIO("")  # no input needed
        stdout = io.StringIO()
        preset = {ROMANS: "human", ARVERNI: "bot",
                  AEDUI: "bot", BELGAE: "bot"}
        sc, modes = setup_wizard(
            stdin, stdout,
            preset_scenario=SCENARIO_PAX_GALLICA,
            preset_faction_modes=preset,
        )
        assert modes[ROMANS] == "human"
        assert modes[BELGAE] == "bot"


# ============================================================================
# prompt_choice
# ============================================================================

class TestPromptChoice:
    """prompt_choice validates input range and re-prompts on garbage."""

    def test_accepts_valid_choice(self):
        stdin = io.StringIO("2\n")
        stdout = io.StringIO()
        v = prompt_choice(stdin, stdout, "Pick:", [("a", 10), ("b", 20)])
        assert v == 20

    def test_rejects_out_of_range_then_accepts(self):
        stdin = io.StringIO("99\n1\n")
        stdout = io.StringIO()
        v = prompt_choice(stdin, stdout, "Pick:", [("a", 10), ("b", 20)])
        assert v == 10
        assert "Please enter 1-2" in stdout.getvalue()

    def test_rejects_non_numeric(self):
        stdin = io.StringIO("xyz\n1\n")
        stdout = io.StringIO()
        v = prompt_choice(stdin, stdout, "Pick:", [("a", 10), ("b", 20)])
        assert v == 10
        assert "Please enter 1-2" in stdout.getvalue()

    def test_rejects_zero(self):
        stdin = io.StringIO("0\n1\n")
        stdout = io.StringIO()
        v = prompt_choice(stdin, stdout, "Pick:", [("a", 10)])
        assert v == 10

    def test_empty_choices_raises(self):
        with pytest.raises(ValueError):
            prompt_choice(io.StringIO(""), io.StringIO(), "x", [])


# ============================================================================
# prompt_yes_no
# ============================================================================

class TestPromptYesNo:
    def test_yes_variants(self):
        for s in ("y", "Y", "yes", "YES"):
            assert prompt_yes_no(
                io.StringIO(s + "\n"), io.StringIO(), "?"
            ) is True

    def test_no_variants(self):
        for s in ("n", "N", "no", "NO"):
            assert prompt_yes_no(
                io.StringIO(s + "\n"), io.StringIO(), "?"
            ) is False

    def test_rejects_then_accepts(self):
        v = prompt_yes_no(io.StringIO("maybe\ny\n"), io.StringIO(), "?")
        assert v is True

    def test_default_on_empty(self):
        v = prompt_yes_no(
            io.StringIO("\n"), io.StringIO(), "?", default=True,
        )
        assert v is True


# ============================================================================
# prompt_action — hard-blocks illegal moves
# ============================================================================

class TestPromptAction:
    """prompt_action only shows legal options; bad input re-prompts."""

    def _state(self):
        s = setup_scenario(SCENARIO_PAX_GALLICA, seed=42)
        start_game(s)
        return s

    def test_first_eligible_legal(self):
        state = self._state()
        opts = get_first_eligible_options()
        # Pass is the 4th option in get_first_eligible_options
        idx = opts.index(ACTION_PASS) + 1
        stdin = io.StringIO(f"{idx}\n")
        stdout = io.StringIO()
        d = prompt_action(state, BELGAE, opts, "1st_eligible", stdin, stdout)
        assert d == {"action": ACTION_PASS}
        # Confirm only the legal options were displayed
        text = stdout.getvalue()
        assert "BELGAE" in text.upper() or "Belgae" in text
        for o in opts:
            assert ACTION_LABELS[o] in text

    def test_rejects_illegal_index(self):
        state = self._state()
        opts = [ACTION_COMMAND, ACTION_PASS]
        # "99" rejected, "1" accepted
        stdin = io.StringIO("99\n1\n")
        stdout = io.StringIO()
        d = prompt_action(state, AEDUI, opts, "1st_eligible", stdin, stdout)
        assert d["action"] == ACTION_COMMAND
        assert "Please enter 1-2" in stdout.getvalue()

    def test_rejects_non_numeric(self):
        state = self._state()
        opts = [ACTION_COMMAND, ACTION_PASS]
        stdin = io.StringIO("hello\n2\n")
        stdout = io.StringIO()
        d = prompt_action(state, AEDUI, opts, "1st_eligible", stdin, stdout)
        assert d["action"] == ACTION_PASS

    def test_second_eligible_position_label(self):
        state = self._state()
        opts = get_second_eligible_options(ACTION_COMMAND)
        # Options are [LIMITED_COMMAND, PASS]
        stdin = io.StringIO("1\n")
        stdout = io.StringIO()
        d = prompt_action(state, AEDUI, opts, "2nd_eligible", stdin, stdout)
        assert d["action"] == ACTION_LIMITED_COMMAND


# ============================================================================
# Dispatcher
# ============================================================================

class TestDispatcher:
    """make_decision_func routes human vs bot correctly."""

    def _state(self):
        s = setup_scenario(SCENARIO_PAX_GALLICA, seed=42)
        start_game(s)
        s["non_player_factions"] = {ROMANS, ARVERNI, AEDUI, BELGAE}
        return s

    def test_human_reads_stdin(self):
        state = self._state()
        fm = {BELGAE: "human"}
        stdin = io.StringIO("1\n")  # pick option 1
        stdout = io.StringIO()
        df = make_decision_func(fm, stdin=stdin, stdout=stdout, pause=False)
        opts = get_first_eligible_options()
        d = df(state, BELGAE, opts, "1st_eligible")
        assert d["action"] == opts[0]

    def test_bot_returns_engine_action(self):
        state = self._state()
        fm = {f: "bot" for f in (ROMANS, ARVERNI, AEDUI, BELGAE)}
        df = make_decision_func(
            fm, stdin=io.StringIO(""), stdout=io.StringIO(), pause=False,
        )
        opts = get_first_eligible_options()
        d = df(state, BELGAE, opts, "1st_eligible")
        # Engine action must be one of the legal options
        assert d["action"] in opts
        # Bot's full action dict must be attached
        assert "bot_action" in d
        assert "command" in d["bot_action"]


class TestTranslateBotAction:
    """_translate_bot_action handles all bot command labels."""

    def test_pass(self):
        a = {"command": "Pass", "sa": "No SA"}
        opts = [ACTION_COMMAND, ACTION_PASS]
        assert _translate_bot_action(a, opts) == ACTION_PASS

    def test_event(self):
        a = {"command": "Event", "sa": "No SA"}
        opts = [ACTION_EVENT, ACTION_COMMAND, ACTION_PASS]
        assert _translate_bot_action(a, opts) == ACTION_EVENT

    def test_command_only(self):
        a = {"command": "Battle", "sa": "No SA"}
        opts = [ACTION_COMMAND, ACTION_COMMAND_SA, ACTION_EVENT, ACTION_PASS]
        assert _translate_bot_action(a, opts) == ACTION_COMMAND

    def test_command_with_sa(self):
        a = {"command": "Rally", "sa": "Suborn"}
        opts = [ACTION_COMMAND, ACTION_COMMAND_SA, ACTION_EVENT, ACTION_PASS]
        assert _translate_bot_action(a, opts) == ACTION_COMMAND_SA

    def test_downgrade_to_limited_when_2nd_eligible(self):
        """2nd Eligible after 1st-Command-only: bot Battle/SA must downgrade."""
        a = {"command": "Battle", "sa": "Ambush"}
        # Engine's options when 1st did command-only: [LIMITED, PASS]
        opts = [ACTION_LIMITED_COMMAND, ACTION_PASS]
        assert _translate_bot_action(a, opts) == ACTION_LIMITED_COMMAND

    def test_downgrade_to_limited_with_no_sa(self):
        a = {"command": "March", "sa": "No SA"}
        opts = [ACTION_LIMITED_COMMAND, ACTION_PASS]
        assert _translate_bot_action(a, opts) == ACTION_LIMITED_COMMAND


# ============================================================================
# format_action
# ============================================================================

class TestFormatAction:
    """format_action handles all bot command shapes."""

    def test_pass(self):
        s = format_action({"command": "Pass"}, faction=BELGAE)
        assert "Belgae" in s
        assert "Pass" in s

    def test_event(self):
        s = format_action({"command": "Event"}, faction=AEDUI)
        assert "Event" in s

    def test_battle(self):
        s = format_action(
            {"command": "Battle", "regions": [MORINI], "sa": "No SA"},
            faction=BELGAE,
        )
        assert "Battle" in s
        assert "Morini" in s

    def test_march(self):
        s = format_action(
            {"command": "March", "regions": [TREVERI, NERVII]},
            faction=BELGAE,
        )
        assert "March" in s
        assert "Treveri" in s
        assert "Nervii" in s

    def test_rally_with_sa(self):
        s = format_action(
            {"command": "Rally",
             "regions": [TREVERI, MORINI],
             "sa": "Enlist",
             "sa_regions": [TREVERI]},
            faction=BELGAE,
        )
        assert "Rally" in s
        assert "SA: Enlist" in s
        assert "Treveri" in s

    def test_raid(self):
        s = format_action(
            {"command": "Raid", "regions": [MORINI], "sa": "No SA"},
            faction=BELGAE,
        )
        assert "Raid" in s

    def test_sa_regions_with_dicts(self):
        """Some bots return dict objects in sa_regions — format must not crash."""
        s = format_action(
            {"command": "Rally",
             "regions": [MORINI],
             "sa": "Rampage",
             "sa_regions": [{"region": MORINI, "target": ROMANS}]},
            faction=BELGAE,
        )
        assert "Morini" in s
        assert "Rampage" in s

    def test_none_action(self):
        s = format_action(None)
        assert "no action" in s.lower()


# ============================================================================
# format_state_summary across all scenarios
# ============================================================================

class TestFormatStateSummary:
    """format_state_summary renders all 5 scenarios without exception."""

    @pytest.mark.parametrize("scenario", list(ALL_SCENARIOS))
    def test_renders_each_scenario(self, scenario):
        state = setup_scenario(scenario, seed=42)
        start_game(state)
        out = format_state_summary(state)
        # Required fields per the spec
        assert "Scenario:" in out
        assert "Current card:" in out
        assert "Upcoming card:" in out
        assert "Frost:" in out
        assert "Senate:" in out
        assert "Legions track:" in out
        assert "Capabilities:" in out
        # Ariovistus-specific fields
        if scenario in ARIOVISTUS_SCENARIOS:
            assert "At War" in out
            assert "Diviciacus" in out
        # Faction rows
        assert ROMANS in out
        # Region table renders too
        rt = format_region_table(state)
        assert "REGIONS" in rt
        # Tribes table renders
        tt = format_tribes_table(state)
        assert "TRIBES" in tt
        # Legions visual
        lt = format_legions_track(state)
        assert "Legions Track" in lt
        # Victory state — should NOT raise on any scenario
        vs = format_victory_state(state)
        assert "VICTORY" in vs


# ============================================================================
# format_card
# ============================================================================

class TestFormatCard:
    def test_none(self):
        assert "none" in format_card(None, SCENARIO_PAX_GALLICA).lower()

    def test_base_card(self):
        s = format_card(27, SCENARIO_PAX_GALLICA)
        assert "Massed Gallic Archers" in s
        assert "Faction order" in s

    def test_unknown_card(self):
        # No exception; returns a fallback string
        s = format_card(9999, SCENARIO_PAX_GALLICA)
        assert "9999" in s


# ============================================================================
# Argument parsing
# ============================================================================

class TestArgParsing:
    def test_parse_scenario(self):
        a = _parse_args(["--scenario", "Pax Gallica?", "--seed", "7"])
        assert a.scenario == SCENARIO_PAX_GALLICA
        assert a.seed == 7

    def test_parse_bots_arg(self):
        modes = _parse_bots_arg("Romans,Aedui", (ROMANS, ARVERNI, AEDUI, BELGAE))
        assert modes[ROMANS] == "bot"
        assert modes[AEDUI] == "bot"
        assert modes[ARVERNI] == "human"
        assert modes[BELGAE] == "human"

    def test_parse_bots_arg_case_insensitive(self):
        modes = _parse_bots_arg("romans,aedui", (ROMANS, ARVERNI, AEDUI, BELGAE))
        assert modes[ROMANS] == "bot"

    def test_parse_bots_arg_unknown_raises(self):
        with pytest.raises(ValueError):
            _parse_bots_arg("NotAFaction", (ROMANS, ARVERNI, AEDUI, BELGAE))

    def test_parse_bots_arg_non_assignable_raises(self):
        # Germans not assignable in base
        with pytest.raises(ValueError):
            _parse_bots_arg("Germans", (ROMANS, ARVERNI, AEDUI, BELGAE))


# ============================================================================
# Smoke test: end-to-end non-interactive
# ============================================================================

class TestSmokeNonInteractive:
    """All-bot game plays at least one card without crashing on the CLI side."""

    @pytest.mark.parametrize("scenario", [
        SCENARIO_PAX_GALLICA, SCENARIO_ARIOVISTUS,
    ])
    def test_non_interactive_runs(self, scenario):
        """main() with --non-interactive should not raise on CLI/display."""
        argv = [
            "--scenario", scenario,
            "--seed", "42",
            "--non-interactive",
        ]
        stdin = io.StringIO("")
        stdout = io.StringIO()
        # Should return 0 or 1 — not raise SystemExit on CLI side
        code = main(argv, stdin=stdin, stdout=stdout)
        out = stdout.getvalue()
        # Must have rendered the initial state summary
        assert "Scenario:" in out
        assert "REGIONS" in out
        # Engine may halt because resolve_card_turn doesn't execute
        # commands — that's expected per the task spec. The CLI must
        # NOT crash on its own display/translation layer.
        # The exit code is 0 (game completed) or 1 (engine raised).
        assert code in (0, 1)
