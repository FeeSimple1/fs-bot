"""Regression coverage for resumable faction actions and mandatory phases."""

import copy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.engine import game_engine as ge
from fs_bot.state.serialize import encode, load_game, save_game
from fs_bot.state.setup import setup_scenario


def _state(card=1, scenario=rc.SCENARIO_PAX_GALLICA):
    state = setup_scenario(scenario, seed=42)
    state["current_card"] = card
    state["next_card"] = 2
    for faction in ge.get_sop_factions(state):
        state["eligibility"][faction] = rc.ELIGIBLE
    return state


def test_resume_preserves_completed_pass_and_position(tmp_path):
    state = _state()
    initial = state["resources"][rc.ROMANS]

    def pause(st, faction, options, position):
        if faction == rc.ROMANS:
            return {"action": ge.ACTION_PASS}
        raise EOFError

    with pytest.raises(EOFError):
        ge.resolve_card_turn(state, pause)
    save_game(state, tmp_path / "turn.json")
    state, _, _ = load_game(tmp_path / "turn.json")
    called = []

    def finish(st, faction, options, position):
        called.append((faction, position))
        return {"action": ge.ACTION_PASS}

    result = ge.resolve_card_turn(state, finish)
    assert called[0] == (rc.ARVERNI, "1st_eligible")
    assert rc.ROMANS not in [f for f, _ in called]
    assert state["resources"][rc.ROMANS] == initial + 2
    assert result["passes"] == [rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE]
    assert "_card_turn" not in state


def test_resume_preserves_first_action_and_second_options(tmp_path):
    state = _state()

    def pause(st, faction, options, position):
        if faction == rc.ROMANS:
            return {"action": ge.ACTION_COMMAND}
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        ge.resolve_card_turn(state, pause)
    save_game(state, tmp_path / "turn.json")
    state, _, _ = load_game(tmp_path / "turn.json")

    def finish(st, faction, options, position):
        assert faction == rc.ARVERNI
        assert position == "2nd_eligible"
        assert options == [ge.ACTION_LIMITED_COMMAND, ge.ACTION_PASS]
        return {"action": ge.ACTION_LIMITED_COMMAND}

    result = ge.resolve_card_turn(state, finish)
    assert list(result["actions_taken"]) == [rc.ROMANS, rc.ARVERNI]
    assert state["eligibility"][rc.ROMANS] == rc.INELIGIBLE


def test_interrupt_rolls_back_partial_execution_rng_and_frontend(monkeypatch):
    from fs_bot.engine import execute

    state = _state()
    initial = copy.deepcopy(state)
    log = []

    def decision(st, faction, options, position):
        log.append(faction)
        return {"action": (ge.ACTION_PASS if faction == rc.ROMANS
                           else ge.ACTION_COMMAND)}

    decision.transaction_checkpoint = lambda: len(log)
    decision.transaction_restore = lambda n: log.__delitem__(slice(n, None))

    def interrupted_execution(st, faction, plan):
        st["resources"][faction] -= 5
        st["rng"].randint(1, 6)
        # A reactive human prompt can interrupt a partially resolved action.
        raise KeyboardInterrupt

    monkeypatch.setattr(execute, "execute_decision", interrupted_execution)
    with pytest.raises(KeyboardInterrupt):
        ge.resolve_card_turn(state, decision, execute=True)
    assert log == [rc.ROMANS]
    assert state["resources"][rc.ROMANS] == initial["resources"][rc.ROMANS] + 2
    assert state["resources"][rc.ARVERNI] == initial["resources"][rc.ARVERNI]
    assert state["rng"].getstate() == initial["rng"].getstate()
    assert state["_card_turn"]["idx"] == 1
    assert list(state["_card_turn"]["actions_taken"]) == [rc.ROMANS]


@pytest.mark.parametrize("all_pass", [True, False])
def test_carnyx_phase_runs_after_passes_or_no_eligible_factions(all_pass):
    state = _state("A5", rc.SCENARIO_ARIOVISTUS)
    assert ge.check_arverni_at_war(state)[0]
    if not all_pass:
        for faction in ge.get_sop_factions(state):
            state["eligibility"][faction] = rc.INELIGIBLE
    result = ge.resolve_card_turn(
        state, lambda *_: {"action": ge.ACTION_PASS}, execute=True)
    assert result["arverni_phase"] is not None
    assert len(result["passes"]) == (4 if all_pass else 0)


def test_event_immediately_removes_later_factions_from_card():
    state = _state(46)
    called = []
    resources = dict(state["resources"])

    def decision(st, faction, options, position):
        called.append(faction)
        if faction == rc.AEDUI:
            return {"action": ge.ACTION_EVENT, "player_action": {
                "command": "Event", "details": {
                    "shaded": False, "event_params": {
                        "target_factions": [rc.ARVERNI, rc.BELGAE]}}}}
        return {"action": ge.ACTION_PASS}

    result = ge.resolve_card_turn(state, decision, execute=True)
    assert rc.ARVERNI not in called
    assert rc.BELGAE not in called
    for faction in (rc.ARVERNI, rc.BELGAE):
        assert state["resources"][faction] == resources[faction] - 3
        assert faction not in result["passes"]
        assert state["eligibility"][faction] == rc.INELIGIBLE


def test_no_selected_sa_gives_second_faction_command_only_options():
    state = _state()

    def decision(st, faction, options, position):
        if faction == rc.ROMANS:
            return {"action": ge.ACTION_COMMAND_SA, "player_action": {
                "command": "Recruit", "regions": [rc.PROVINCIA],
                "sa": "No SA", "sa_regions": [], "details": {
                    "recruit_plan": [{"region": rc.PROVINCIA,
                                      "action": "place_auxilia"}]}}}
        assert ge.ACTION_EVENT not in options
        return {"action": ge.ACTION_PASS}

    result = ge.resolve_card_turn(state, decision, execute=True)
    assert result["actions_taken"][rc.ROMANS]["action"] == ge.ACTION_COMMAND


def test_interrupted_winter_rolls_back_board_and_rng(monkeypatch):
    state = _state(rc.WINTER_CARD)
    initial = encode(state)

    def interrupted_winter(st):
        st["winter_count"] += 1
        st["rng"].random()
        raise EOFError

    monkeypatch.setattr(ge, "resolve_winter_card", interrupted_winter)
    with pytest.raises(EOFError):
        ge.play_card(state, lambda *_: {"action": ge.ACTION_PASS})
    assert encode(state) == initial


def test_failed_serialization_preserves_previous_save(tmp_path):
    path = tmp_path / "game.json"
    save_game({"ok": True}, path)
    with pytest.raises(TypeError):
        save_game({"unsupported": object()}, path)
    assert load_game(path)[0] == {"ok": True}


def test_save_preserves_mapping_iteration_order(tmp_path):
    # Phase/agent request order depends on faction and region insertion
    # order; alphabetizing keys on save changes choices after resume.
    state = {"resources": {rc.ROMANS: 1, rc.ARVERNI: 2, rc.BELGAE: 3,
                            rc.AEDUI: 4}}
    path = tmp_path / "ordered.json"
    save_game(state, path)
    resumed, _, _ = load_game(path)
    assert list(resumed["resources"]) == list(state["resources"])


def test_resume_after_resolution_does_not_repeat_completed_card(monkeypatch):
    state = _state()
    original_advance = ge.advance_to_next_card
    calls = []

    def decision(st, faction, options, position):
        calls.append(faction)
        return {"action": ge.ACTION_PASS}

    def interrupted_advance(st):
        original_advance(st)
        raise KeyboardInterrupt

    monkeypatch.setattr(ge, "advance_to_next_card", interrupted_advance)
    with pytest.raises(KeyboardInterrupt):
        ge.play_card(state, decision)
    assert len(calls) == 4
    assert state["current_card"] == 1
    resources = dict(state["resources"])
    monkeypatch.setattr(ge, "advance_to_next_card", original_advance)
    ge.play_card(state, decision)
    assert len(calls) == 4
    assert state["resources"] == resources
    assert "_resolved_card" not in state


def test_resume_between_interlude_and_next_card(monkeypatch):
    state = _state(rc.WINTER_CARD, rc.SCENARIO_GALLIC_WAR)
    original_advance = ge.advance_to_next_card
    calls = []

    def completed_interlude(st):
        calls.append("winter")
        st["scenario"] = rc.SCENARIO_PAX_GALLICA
        st["current_card"] = None
        st["played_cards"] = []
        st["deck"] = [1, 2]
        return {"winter_result": {"phases": {}}}

    monkeypatch.setattr(ge, "resolve_winter_card", completed_interlude)
    monkeypatch.setattr(ge, "advance_to_next_card",
                        lambda st: (_ for _ in ()).throw(EOFError()))
    with pytest.raises(EOFError):
        ge.play_card(state, lambda *_: {"action": ge.ACTION_PASS})
    assert state["current_card"] == rc.WINTER_CARD
    monkeypatch.setattr(ge, "advance_to_next_card", original_advance)
    ge.play_card(state, lambda *_: {"action": ge.ACTION_PASS})
    assert calls == ["winter"]
    assert state["current_card"] == 1


def test_resuming_finished_deck_does_not_repeat_last_card():
    state = _state()
    state["deck"] = []
    decision = lambda *_: {"action": ge.ACTION_PASS}
    assert ge.play_card(state, decision)["game_over"]
    resources = dict(state["resources"])
    assert ge.play_card(state, decision)["game_over"]
    assert state["resources"] == resources


def test_invalid_human_action_is_retried_without_spending_turn():
    state = _state()
    rejected = []
    calls = []

    def decision(st, faction, options, position):
        calls.append(faction)
        if len(calls) == 1:
            return {"action": ge.ACTION_COMMAND, "player_action": {
                "command": "Recruit", "regions": [], "details": {}}}
        return {"action": ge.ACTION_PASS}

    decision.decision_rejected = lambda st, faction, result: rejected.append(faction)
    result = ge.resolve_card_turn(state, decision, execute=True)
    assert rejected == [rc.ROMANS]
    assert calls[:2] == [rc.ROMANS, rc.ROMANS]
    assert result["actions_taken"][rc.ROMANS]["action"] == ge.ACTION_PASS


def test_command_type_without_plan_cannot_spend_human_turn():
    state = _state()
    with pytest.raises(ge.ActionRejected, match="no executable plan"):
        ge.resolve_card_turn(state, lambda *_: {"action": ge.ACTION_COMMAND},
                             execute=True)
    assert state["_card_turn"]["idx"] == 0
    assert state["_card_turn"]["actions_taken"] == {}
    assert state["eligibility"][rc.ROMANS] == rc.ELIGIBLE


def test_ineffective_human_event_remains_permitted(monkeypatch):
    from fs_bot.engine import execute

    state = _state()
    monkeypatch.setattr(execute, "execute_decision",
                        lambda *args: {"executed": False, "command": "Event"})

    def decision(st, faction, options, position):
        if faction == rc.ROMANS:
            return {"action": ge.ACTION_EVENT,
                    "player_action": {"command": "Event"}}
        return {"action": ge.ACTION_PASS}

    result = ge.resolve_card_turn(state, decision, execute=True)
    assert result["actions_taken"][rc.ROMANS]["action"] == ge.ACTION_EVENT
    assert state["eligibility"][rc.ROMANS] == rc.INELIGIBLE


def test_newly_eligible_roman_can_act_after_gallic_shouts(monkeypatch):
    state = _state(35)
    state["eligibility"][rc.ROMANS] = rc.INELIGIBLE
    # Exercise the Event's explicit "be Eligible" alternative.
    from fs_bot.engine import execute
    monkeypatch.setattr(execute, "_resolve_free_command",
                        lambda *a, **kw: {"executed": False})
    calls = []

    def decision(st, faction, options, position):
        calls.append(faction)
        if faction == rc.ARVERNI:
            return {"action": ge.ACTION_EVENT, "player_action": {
                "command": "Event", "details": {
                    "text_preference": rc.EVENT_UNSHADED, "event_params": {}}}}
        return {"action": ge.ACTION_PASS}

    ge.resolve_card_turn(state, decision, execute=True)
    assert rc.ROMANS in calls


def test_successful_ambush_keeps_second_faction_event_option():
    from fs_bot.board.pieces import place_piece, move_piece
    from fs_bot.board.control import refresh_all_control

    state = _state(35, rc.SCENARIO_GREAT_REVOLT)  # Arverni first.
    move_piece(state, rc.CARNUTES, rc.ARVERNI_REGION, rc.ARVERNI, rc.LEADER)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, 6,
                piece_state=rc.HIDDEN)
    place_piece(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA, 2)
    refresh_all_control(state)

    def decision(st, faction, options, position):
        if faction == rc.ARVERNI:
            return {"action": ge.ACTION_COMMAND_SA, "player_action": {
                "command": "Battle", "regions": [rc.ARVERNI_REGION],
                "sa": "Ambush", "sa_regions": [rc.ARVERNI_REGION],
                "details": {"battle_plan": [{"region": rc.ARVERNI_REGION,
                                             "target": rc.ROMANS}]}}}
        assert ge.ACTION_EVENT in options
        return {"action": ge.ACTION_PASS}

    result = ge.resolve_card_turn(state, decision, execute=True)
    assert result["actions_taken"][rc.ARVERNI]["action"] == ge.ACTION_COMMAND_SA


def test_llm_empty_queue_preserves_board_at_second_eligible(tmp_path, capsys):
    from types import SimpleNamespace
    from fs_bot.tools.llm_seat import cmd_init, cmd_play, cmd_board

    args = SimpleNamespace(dir=str(tmp_path), scenario=rc.SCENARIO_GREAT_REVOLT,
                           seat=rc.ROMANS, seed=1)
    cmd_init(args)
    cmd_play(args)
    original, meta, _ = load_game(tmp_path / "save.json")
    assert original["_card_turn"]["first_action"] is not None
    assert meta["human_snapshots"]
    capsys.readouterr()
    cmd_play(args)
    resumed, _, _ = load_game(tmp_path / "save.json")
    assert encode(resumed) == encode(original)
    assert "No board changes" in capsys.readouterr().out
    cmd_board(args)
    board = capsys.readouterr().out
    assert "CURRENT" in board.upper()
    assert "UPCOMING" in board.upper()
    from fs_bot.cards.card_text import format_card_text
    for card in (resumed["current_card"], resumed["next_card"]):
        printed = format_card_text(card, indent="  | ",
                                   scenario=resumed["scenario"])
        assert printed
        assert all(line.strip() in board for line in printed.splitlines())


def test_llm_rejected_queue_entry_survives_for_correction(tmp_path, capsys):
    import json
    from types import SimpleNamespace
    from fs_bot.tools.llm_seat import cmd_init, cmd_play

    args = SimpleNamespace(dir=str(tmp_path), scenario=rc.SCENARIO_GREAT_REVOLT,
                           seat=rc.BELGAE, seed=1)
    cmd_init(args)
    cmd_play(args)
    original, _, _ = load_game(tmp_path / "save.json")
    decision = {"action": ge.ACTION_COMMAND, "player_action": {
        "command": "Rally", "regions": [], "details": {}}}
    (tmp_path / "queue.json").write_text(json.dumps([decision]))
    cmd_play(args)
    resumed, _, _ = load_game(tmp_path / "save.json")
    assert encode(resumed) == encode(original)
    assert json.loads((tmp_path / "queue.json").read_text()) == [decision]
    assert "Decision rejected" in capsys.readouterr().out
