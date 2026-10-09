"""Players can inspect the public cards and every tactical board change."""

import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import flip_piece, place_piece
from fs_bot.cards.card_text import get_card_text
from fs_bot.cli.display import (
    HumanTurnDisplay, format_board, format_decision_context,
    format_region_table, format_state_delta, snapshot_state,
)
from fs_bot.cli.menus import prompt_action, prompt_choice, prompt_yes_no, set_board_hook
from fs_bot.engine.game_engine import ACTION_COMMAND, ACTION_PASS, start_game
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.setup import setup_scenario


def _state(scenario=rc.SCENARIO_PAX_GALLICA):
    state = setup_scenario(scenario, seed=13)
    start_game(state)
    return state


def test_piece_flips_and_markers_appear_in_board_and_delta():
    state = _state()
    before = snapshot_state(state)
    board_before = format_board(state)
    flip_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND,
               from_state=rc.HIDDEN, to_state=rc.SCOUTED)
    state["markers"][rc.MORINI] = {rc.MARKER_DEVASTATED: True}
    delta = "\n".join(format_state_delta(before, snapshot_state(state)))
    assert f"{rc.BELGAE} {rc.HIDDEN} {rc.WARBAND}" in delta
    assert f"{rc.BELGAE} {rc.SCOUTED} {rc.WARBAND}: 0 -> 1" in delta
    assert rc.MARKER_DEVASTATED in delta
    board_after = format_board(state)
    assert board_before != board_after
    assert "/S1]" in board_after
    assert rc.MARKER_DEVASTATED in board_after
    assert "TRIBES" in board_after
    assert "AVAILABLE PIECES" in board_after


def test_delta_covers_control_capability_side_holder_and_tracks():
    state = _state()
    state["capabilities"][8] = rc.EVENT_UNSHADED
    state["capability_owners"] = {8: rc.ROMANS}
    state["markers"][rc.MORINI] = {rc.MARKER_DEVASTATED: True}
    before = snapshot_state(state)
    state["capabilities"][8] = rc.EVENT_SHADED
    state["capability_owners"][8] = rc.AEDUI
    state["spaces"][rc.MORINI]["control"] = rc.NO_CONTROL
    state["senate"]["firm"] = not state["senate"]["firm"]
    state["legions_track"][rc.LEGIONS_ROW_BOTTOM] += 1
    state["eligibility"][rc.BELGAE] = rc.INELIGIBLE
    state["tribes"][rc.MORINI]["status"] = rc.MARKER_DISPERSED
    state["markers"][rc.MORINI].clear()
    delta = "\n".join(format_state_delta(before, snapshot_state(state)))
    for expected in ("Capability card 8", "Capability holders", "Control",
                     "firm:", "Legions track", "Eligibility", "Markers",
                     rc.MARKER_DISPERSED):
        assert expected in delta
    # Nested marker mutation must not modify the detached baseline.
    assert before["markers"][rc.MORINI] == {rc.MARKER_DEVASTATED: True}


def test_both_face_up_cards_displayed_before_action_choice():
    state = _state()
    out = io.StringIO()
    assert prompt_action(state, rc.BELGAE, [ACTION_PASS], "1st_eligible",
                         io.StringIO("1\n"), out) == {"action": ACTION_PASS}
    before_prompt = out.getvalue().split("Choose your action:")[0]
    for card in (state["current_card"], state["next_card"]):
        for line in get_card_text(card, state["scenario"]).splitlines():
            assert line in before_prompt
    assert "Current card:" in before_prompt
    assert "Upcoming card:" in before_prompt


def test_upcoming_winter_displays_frost_and_winter_instruction():
    state = _state()
    state["next_card"] = rc.WINTER_CARD
    context = format_decision_context(state)
    assert "Frost: YES" in context
    assert "resolve the Winter Round" in context
    assert "(unknown)" not in context


@pytest.mark.parametrize("scenario", rc.ALL_SCENARIOS)
def test_full_board_renders_each_scenario_without_mutation(scenario):
    state = _state(scenario)
    before = encode(state)
    rendered = format_board(state)
    assert "Upcoming card:" in rendered
    assert "H=Hidden / R=Revealed / S=Scouted" in rendered
    assert encode(state) == before


def test_gallia_togata_makes_cisalpina_visible():
    state = _state()
    assert rc.CISALPINA not in format_region_table(state)
    state["capabilities"][rc.MARKER_GALLIA_TOGATA] = True
    place_piece(state, rc.CISALPINA, rc.ROMANS, rc.AUXILIA, 2)
    table = format_region_table(state)
    assert rc.CISALPINA in table
    assert "A:2[H2/R0/S0]" in table


@pytest.mark.parametrize("command", ["b", "board"])
def test_board_command_repeats_numeric_and_reactive_prompts(command):
    state = _state()
    out = io.StringIO()
    set_board_hook(lambda: out.write(format_board(state) + "\n"))
    try:
        assert prompt_choice(io.StringIO(f"{command}\n1\n"), out,
                             "Pick:", [("Pass", ACTION_PASS)]) == ACTION_PASS
        assert prompt_yes_no(io.StringIO(f"{command}\ny\n"), out,
                             "Agree?") is True
    finally:
        set_board_hook(None)
    assert out.getvalue().count("AVAILABLE PIECES") == 2
    assert out.getvalue().count("Upcoming card:") == 2


def test_human_snapshots_are_per_seat_and_survive_resume(tmp_path):
    state = _state()
    out = io.StringIO()
    view = HumanTurnDisplay(out)
    view.remember(state, [rc.ROMANS, rc.AEDUI])
    roman_start = state["resources"][rc.ROMANS]
    state["resources"][rc.ROMANS] += 1
    view.before_decision(state, rc.ROMANS, show_context=False)
    saved = tmp_path / "visible.json"
    save_game(state, saved, meta={"human_snapshots": encode(view.snapshots)})
    loaded, meta, _ = load_game(saved)
    resumed = HumanTurnDisplay(out, decode(meta["human_snapshots"]))
    resumed.remember(loaded, [rc.ROMANS, rc.AEDUI])
    out.seek(0)
    out.truncate()
    resumed.before_decision(loaded, rc.AEDUI, show_context=False)
    assert f"{rc.ROMANS} Resources: {roman_start} -> {roman_start + 1}" \
        in out.getvalue()
    out.seek(0)
    out.truncate()
    resumed.before_decision(loaded, rc.ROMANS, show_context=False)
    assert "No board changes" in out.getvalue()


def test_reactive_context_contains_current_and_upcoming_effects():
    state = _state()
    out = io.StringIO()
    view = HumanTurnDisplay(out)
    view.remember(state, [rc.ROMANS])
    state["resources"][rc.AEDUI] += 2
    view.before_decision(state, rc.ROMANS)
    assert f"{rc.AEDUI} Resources:" in out.getvalue()
    assert format_decision_context(state) in out.getvalue()


def test_eof_during_command_collection_keeps_turn_pending():
    with pytest.raises(EOFError):
        prompt_action(_state(), rc.AEDUI, [ACTION_COMMAND], "1st_eligible",
                      io.StringIO("1\n"), io.StringIO())


def test_eof_during_validation_does_not_submit_unconfirmed_plan(monkeypatch):
    monkeypatch.setattr("fs_bot.cli.human_plan.collect_player_action",
                        lambda *args: {"command": "Rally", "regions": []})
    monkeypatch.setattr("fs_bot.engine.moves.validate_player_action",
                        lambda *args: (False, {"reason": "No Regions"}))
    with pytest.raises(EOFError):
        prompt_action(_state(), rc.AEDUI, [ACTION_COMMAND], "1st_eligible",
                      io.StringIO("1\n"), io.StringIO())
