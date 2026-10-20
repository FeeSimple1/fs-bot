"""Human information, interruption, and Interlude ownership regressions."""

import io

from fs_bot.cli import app
from fs_bot.engine.agent import AGREEMENT, consult_agent
from fs_bot.rules_consts import (
    ARVERNI, GERMANS, ROMANS, SCENARIO_GALLIC_WAR,
    SCENARIO_GREAT_REVOLT, SCENARIO_PAX_GALLICA,
)
from fs_bot.state.serialize import encode, load_game
from fs_bot.tests.test_cli_game import ScriptedPlayer


def _run(args, *, interrupt_after=None):
    out = io.StringIO()
    player = ScriptedPlayer(out, interrupt_after=interrupt_after)
    return app.main(args, stdin=player, stdout=out), out.getvalue()


def test_first_prompt_shows_current_and_upcoming_cards():
    out = io.StringIO()
    assert app.main(
        ["--scenario", SCENARIO_GREAT_REVOLT, "--seed", "1", "--bots", ""],
        stdin=io.StringIO(""), stdout=out) == 0
    before_choice = out.getvalue().split("Choose your action:")[0]
    assert "Remi Influence" in before_choice  # current card 68
    assert "Morasses" in before_choice       # upcoming card 36
    assert "Card: (none)" not in before_choice


def test_midcard_cli_resume_preserves_completed_pass_and_final_state(tmp_path):
    args = ["--scenario", SCENARIO_GREAT_REVOLT, "--seed", "1", "--bots", ""]
    whole, resumed = tmp_path / "whole.json", tmp_path / "resumed.json"
    code, text = _run(args + ["--save", str(whole)])
    assert code == 0 and "Game ended" in text
    code, _ = _run(args + ["--save", str(resumed)], interrupt_after=1)
    assert code == 0
    state, _, log = load_game(resumed)
    assert state["current_card"] == 68
    assert len([e for e in log if e.get("action") == "pass"]) == 1
    code, text = _run(["--load", str(resumed), "--save", str(resumed)])
    assert code == 0 and "Game ended" in text
    actual, _, actual_log = load_game(resumed)
    expected, _, expected_log = load_game(whole)
    assert encode(actual) == encode(expected)
    assert actual_log == expected_log


def test_eof_during_human_plan_preserves_turn(tmp_path):
    save = tmp_path / "incomplete.json"
    out = io.StringIO()
    # Choose Command, then input ends before selecting which Command.
    assert app.main(
        ["--scenario", SCENARIO_GREAT_REVOLT, "--seed", "1", "--bots", "",
         "--save", str(save)], stdin=io.StringIO("1\n"), stdout=out) == 0
    state, _, log = load_game(save)
    assert state["current_card"] == 68
    assert state["_card_turn"]["actions_taken"] == {}
    assert log == []


def test_eof_during_reactive_choice_interrupts_instead_of_deferring():
    from fs_bot.cli.reactive import make_cli_reactive
    state = {"decision_agent": make_cli_reactive([ROMANS], io.StringIO(""),
                                                io.StringIO())}
    import pytest
    with pytest.raises(EOFError):
        consult_agent(state, ROMANS, {"kind": AGREEMENT,
                                     "request_type": "trade_roman_agreement"})


def test_interlude_saves_current_seats_and_loads(tmp_path):
    class StopAtInterlude(io.StringIO):
        def write(self, text):
            result = super().write(text)
            if "*** Interlude:" in text:
                raise KeyboardInterrupt()
            return result

    save = tmp_path / "interlude.json"
    out = StopAtInterlude()
    assert app.main(
        ["--scenario", SCENARIO_GALLIC_WAR, "--seed", "4",
         "--non-interactive", "--save", str(save)],
        stdin=io.StringIO(""), stdout=out) == 0
    state, meta, _ = load_game(save)
    assert state["interlude_completed"]
    assert ARVERNI in meta["faction_modes"]
    assert GERMANS not in meta["faction_modes"]
    assert GERMANS in meta["initial_faction_modes"]
    assert ARVERNI not in meta["initial_faction_modes"]
    code, text = _run(["--load", str(save), "--non-interactive"])
    assert code == 0 and "Game ended" in text
    code, text = _run(["--replay", str(save), "--non-interactive"])
    assert code == 0 and "Game ended" in text


def test_human_german_seat_keeps_reactive_control_after_interlude(monkeypatch):
    calls = []

    def play_card(state, decision, *, execute):
        if not state.get("interlude_completed"):
            state["interlude_completed"] = True
            state["scenario"] = SCENARIO_PAX_GALLICA
            return {"card": "Winter", "type": "winter", "game_over": False}
        response = consult_agent(state, ARVERNI, {
            "kind": AGREEMENT, "request_type": "retreat_into_control",
            "requesting_faction": ROMANS,
            "context": {"region": "Arverni"},
        })
        calls.append(response)
        return {"card": state["current_card"], "game_over": True}

    monkeypatch.setattr(app, "play_card", play_card)
    out = io.StringIO()
    code = app.main(
        ["--scenario", SCENARIO_GALLIC_WAR, "--seed", "11",
         "--bots", "Romans,Aedui,Belgae"],
        stdin=io.StringIO("y\n"), stdout=out)
    assert code == 0
    assert calls == [True]
    assert "want to RETREAT" in out.getvalue()
