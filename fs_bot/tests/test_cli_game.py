"""End-to-end CLI games: full execution, human seats via a scripted player,
save/resume equivalence, and replay. Complements test_cli.py (which unit-
tests the menus/collectors) by driving cli.app.main for entire games."""

import io
import json
import re

import pytest

import fs_bot.rules_consts as rc
from fs_bot.cli.app import main
from fs_bot.state.serialize import load_game, save_game, encode, decode
from fs_bot.tools.player_fuzz import _sanitize


def _digest_state(state):
    body = {k: _sanitize(v) for k, v in state.items()
            if k not in ("decision_agent",)}
    return json.dumps(body, sort_keys=True)


class ScriptedPlayer:
    """A fake stdin that reads the menus just written to stdout and answers
    deterministically: numbered menus pick the option labeled ``prefer``
    (else option 1), yes/no prompts answer yes. Optionally raises
    KeyboardInterrupt after N reads to simulate a mid-game interrupt."""

    def __init__(self, out, prefer="Pass", interrupt_after=None):
        self.out = out
        self.prefer = prefer
        self.pos = 0
        self.reads = 0
        self.interrupt_after = interrupt_after

    def readline(self):
        self.reads += 1
        if (self.interrupt_after is not None
                and self.reads > self.interrupt_after):
            raise KeyboardInterrupt()
        text = self.out.getvalue()
        delta, self.pos = text[self.pos:], len(text)
        options = re.findall(r"^\s*(\d+)\) (.*)$", delta, re.M)
        if options:
            for num, label in options:
                if label.strip() == self.prefer:
                    return num + "\n"
            return options[0][0] + "\n"
        return "y\n"   # yes/no prompt (or default)


def _run(argv, *, prefer="Pass", interrupt_after=None):
    out = io.StringIO()
    player = ScriptedPlayer(out, prefer=prefer,
                            interrupt_after=interrupt_after)
    code = main(argv, stdin=player, stdout=out)
    return code, out.getvalue()


BASE = ["--scenario", rc.SCENARIO_PAX_GALLICA, "--seed", "13",
        "--bots", "Romans,Arverni,Belgae"]     # Aedui human


def test_bot_game_executes_and_replays(tmp_path):
    save = str(tmp_path / "bots.json")
    code, text = _run(["--scenario", rc.SCENARIO_PAX_GALLICA, "--seed", "9",
                       "--non-interactive", "--save", save])
    assert code == 0 and "Game ended" in text
    # Execution is wired: the board changed (some card shows an action).
    assert "=== Card" in text
    state, meta, log = load_game(save)
    assert meta["scenario"] == rc.SCENARIO_PAX_GALLICA
    assert meta["seed"] == 9
    assert state["played_cards"]
    code2, text2 = _run(["--replay", save, "--non-interactive"])
    assert code2 == 0
    assert (text[text.index("Game ended"):]
            == text2[text2.index("Game ended"):])


def test_human_pass_game_full_run(tmp_path):
    save = str(tmp_path / "human.json")
    code, text = _run(BASE + ["--save", save])
    assert code == 0, text[-400:]
    assert "Game ended" in text
    state, meta, log = load_game(save)
    assert meta["faction_modes"][rc.AEDUI] == "human"
    # The human's SoP decisions were logged.
    assert any(e.get("faction") == rc.AEDUI and "reactive" not in e
               for e in log)


def test_resume_after_interrupt_matches_uninterrupted(tmp_path):
    save_a = str(tmp_path / "a.json")
    code, text_a = _run(BASE + ["--save", save_a])
    assert code == 0 and "Game ended" in text_a
    end_a = text_a[text_a.index("Game ended"):]

    # Same game, interrupted mid-play, then resumed from the autosave.
    save_b = str(tmp_path / "b.json")
    code, text_b1 = _run(BASE + ["--save", save_b], interrupt_after=12)
    assert code == 0 and "saved" in text_b1
    code, text_b2 = _run(["--load", save_b, "--save", save_b])
    assert code == 0, text_b2[-400:]
    assert "Game ended" in text_b2
    assert text_b2[text_b2.index("Game ended"):] == end_a

    # End states are byte-identical, not just the summary line.
    sa, _, _ = load_game(save_a)
    sb, _, _ = load_game(save_b)
    assert _digest_state(sa) == _digest_state(sb)


def test_replay_human_game_reproduces_end_state(tmp_path):
    save = str(tmp_path / "h.json")
    code, text = _run(BASE + ["--save", save])
    assert code == 0 and "Game ended" in text
    sa, _, _ = load_game(save)

    # Replay is log-driven: stdin yields nothing.
    out = io.StringIO()
    save2 = str(tmp_path / "h2.json")
    code2 = main(["--replay", save, "--save", save2],
                 stdin=io.StringIO(""), stdout=out)
    assert code2 == 0, out.getvalue()[-400:]
    assert "Game ended" in out.getvalue()
    assert "[replay]" in out.getvalue()
    sb, _, _ = load_game(save2)
    assert _digest_state(sa) == _digest_state(sb)


def test_serialize_round_trip_tagged_types():
    st = {"s": {"b", "a"}, "t": (1, ("x", 2)), "d": {3: "int-key",
          ("A", 1): "tuple-key"}, "n": None, "f": 1.5,
          "__set__": "collision"}
    assert decode(encode(st)) == st
    import random
    r = random.Random(4)
    r.random()
    r2 = decode(encode(r))
    assert r2.getstate() == r.getstate()
    assert r2.random() == r.random()


class _Script:
    """stdin fed by an explicit list of lines."""

    def __init__(self, *lines):
        self.lines = list(lines)

    def readline(self):
        return self.lines.pop(0) + "\n" if self.lines else ""


def _mk_state(scenario=rc.SCENARIO_PAX_GALLICA, seed=13):
    from fs_bot.state.setup import setup_scenario
    st = setup_scenario(scenario, seed=seed)
    st["non_player_factions"] = set()
    return st


def test_event_param_derived_default_accepted():
    """Card 1 (Cicero) has an NP deriver; the human is offered the standard
    choice and accepts it."""
    from fs_bot.cli.human_plan import collect_player_action
    from fs_bot.engine.game_engine import ACTION_EVENT
    st = _mk_state()
    st["current_card"] = 1
    out = io.StringIO()
    pa = collect_player_action(st, rc.ROMANS, ACTION_EVENT,
                               _Script("1", "y"), out)
    assert pa["details"]["card_id"] == 1
    assert pa["details"]["event_params"]["senate_direction"] == rc.SENATE_DOWN
    assert "Standard choices" in out.getvalue()


def test_event_param_prompted_when_derived_declined():
    """Declining the standard choice prompts the typed picker per key."""
    from fs_bot.cli.human_plan import collect_player_action
    from fs_bot.engine.game_engine import ACTION_EVENT
    st = _mk_state()
    st["current_card"] = 1
    # unshaded; decline derived; pick option 2 = Adulation (down)
    pa = collect_player_action(st, rc.ROMANS, ACTION_EVENT,
                               _Script("1", "n", "2"), io.StringIO())
    assert pa["details"]["event_params"]["senate_direction"] == rc.SENATE_DOWN


def test_event_param_keys_extracted_from_handler_source():
    from fs_bot.cli.human_plan import _card_param_keys
    st = _mk_state()
    assert _card_param_keys(st, 1) == ["senate_direction"]
    a = _mk_state(rc.SCENARIO_ARIOVISTUS)
    assert "moves" in _card_param_keys(a, 62)
    assert _card_param_keys(st, "no-such-card") == []


def test_suborn_collector_builds_executor_plan():
    """The Suborn collector emits the executor's suborn_plan shape and the
    resulting Rally+Suborn player_action validates."""
    from fs_bot.cli.human_plan import (_collect_suborn, _subdued_tribes)
    from fs_bot.board.pieces import place_piece
    from fs_bot.board.control import refresh_all_control
    from fs_bot.engine.moves import validate_player_action
    st = _mk_state()
    region = next(r for r in st["spaces"]
                  if _subdued_tribes(st, r))
    place_piece(st, region, rc.AEDUI, rc.WARBAND, 3,
                piece_state=rc.HIDDEN)
    refresh_all_control(st)
    st["resources"][rc.AEDUI] = 10
    out = io.StringIO()
    player = ScriptedPlayer(out, prefer="(done)")
    regions, extra = _collect_suborn(st, rc.AEDUI, player, out)
    assert regions and extra
    plan = extra["suborn_plan"]
    assert plan[0]["region"] == regions[0]
    assert plan[0]["actions"], plan
    # Rally Warbands at the Aedui home Region (Ally present at setup);
    # the Suborn SA accompanies it (§4.4.1).
    pa = {"command": "Rally", "regions": [], "sa": "Suborn",
          "sa_regions": regions,
          "details": {"rally_plan": {"citadels": [], "allies": [],
                                     "warbands": [rc.AEDUI_REGION]},
                      **extra}}
    ok, info = validate_player_action(st, rc.AEDUI, pa)
    assert ok, info


def test_rampage_collector_targets_enemy():
    from fs_bot.cli.human_plan import _collect_rampage
    from fs_bot.board.pieces import place_piece
    from fs_bot.cli.human_plan import _enemies_in_region
    from fs_bot.board.pieces import count_pieces_by_state
    st = _mk_state()
    region = sorted(st["spaces"])[0]
    place_piece(st, region, rc.BELGAE, rc.WARBAND, 2,
                piece_state=rc.HIDDEN)
    place_piece(st, region, rc.ROMANS, rc.AUXILIA, 2)
    out = io.StringIO()
    player = ScriptedPlayer(out, prefer="(done)")
    entries, extra = _collect_rampage(st, rc.BELGAE, player, out)
    assert extra is None
    assert entries
    # Every entry is a Region with Hidden Belgic Warbands and its target
    # is an enemy actually present there (the executor's plan shape).
    for e in entries:
        assert count_pieces_by_state(st, e["region"], rc.BELGAE,
                                     rc.WARBAND, rc.HIDDEN) > 0
        assert e["target"] in _enemies_in_region(st, e["region"],
                                                 rc.BELGAE)
