"""A real Supply refusal is reproducible history, unlike invalid input.

These frontend tests use the engine's reconsideration receipt contract;
mechanical consent and command legality are covered by the Supply tests.
"""
from copy import deepcopy
import io
import json
from types import SimpleNamespace

import pytest

from fs_bot import rules_consts as rc
from fs_bot.cli import app
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine.game_engine import (
    ACTION_COMMAND, ACTION_PASS, ActionRejected, _action_transaction,
)
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.setup import setup_scenario
from fs_bot.tools import llm_seat
from fs_bot.tools.seat_session import SeatSession, board_copy, validate_response


def _plan():
    return {"action": ACTION_COMMAND, "player_action": {
        "command": rc.CMD_RECRUIT, "regions": [], "sa": "No SA",
        "details": {"recruit_plan": [{"region": rc.PROVINCIA,
                                       "action": "place_auxilia", "count": 1}]}}}


def _receipt(state):
    before = state["rng"].getstate()
    state["rng"].randint(1, 6)
    return {"answer": False, "actor_index": state["_card_turn"]["idx"],
            "rng_before": before, "rng_after": state["rng"].getstate()}


def _session(state=None, meta=None, log=None):
    if state is None:
        state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=5)
        state["_card_turn"] = {"idx": 0}
    if meta is None:
        meta = {"seat": rc.ROMANS, "scenario": state["scenario"], "seed": 5}
    return SeatSession(state, meta, [] if log is None else log,
                       HumanTurnDisplay(io.StringIO()))


def _driver(session):
    def driver(*args):
        return session.ask(session.state, rc.ROMANS, {
            "kind": "turn", "options": [ACTION_COMMAND, ACTION_PASS],
            "position": "1st_eligible"})
    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    driver.transaction_complete = session.transaction_complete
    return driver


@pytest.mark.parametrize("key", ["assistant_rejected", "supply_reconsideration"])
def test_player_cannot_submit_engine_refusal_history(key):
    with pytest.raises(ValueError, match="engine history"):
        validate_response(_session().state, {
            "kind": "turn", "faction": rc.ROMANS, "options": [ACTION_PASS]},
            {"action": ACTION_PASS, key: {"answer": False}})


def _attempt(session, *, refuse=True, with_reaction=False):
    driver = _driver(session)
    with _action_transaction(session.state, driver):
        response = driver()
        if response["action"] == ACTION_COMMAND:
            if with_reaction:
                assert session.ask(session.state, rc.ROMANS, {
                    "kind": "agreement", "request_type": "harassment"}) is False
            receipt = _receipt(session.state)
            if refuse:
                session.state["resources"][rc.ROMANS] -= 3
                raise ActionRejected({"reason": "Aedui refused Supply",
                                      "supply_reconsideration": receipt})
        session.state["resources"][rc.ROMANS] += 1
    session.finish()


def test_refused_attempt_keeps_reactions_new_id_and_save_resume(tmp_path):
    session = _session()
    initial = encode(board_copy(session.state))
    session.import_inbox([{"response": _plan()}, {"response": False}])
    with pytest.raises(ActionRejected):
        _attempt(session, with_reaction=True)
    assert session.state["resources"] == decode(initial)["resources"]
    assert len(session.log) == 2
    assert "assistant_rejected" in session.log[0]
    assert "assistant_rejected" not in session.log[1]
    assert session.data["pending"]["id"] == "d000003"
    assert session.data["journal"] == session.data["queue"] == []
    save_game(session.state, tmp_path / "refused.json", meta=session.meta, log=session.log)
    state, meta, log = load_game(tmp_path / "refused.json")
    resumed = _session(state, meta, log)
    resumed.import_inbox({"decision_id": "d000003", "response": {"action": ACTION_PASS}})
    _attempt(resumed)
    assert resumed.log[-1]["assistant_id"] == "d000003"
    assert not resumed.data["pending"]

    replay = _session(decode(initial))
    replay.data["expected"] = [
        {"id": e["assistant_id"], "signature": e["assistant_signature"],
         **({"assistant_rejected": e["assistant_rejected"]}
            if "assistant_rejected" in e else {})} for e in resumed.log]
    replay.data["queue"] = [replay._inbox_entry(e) for e in resumed.log]
    with pytest.raises(ActionRejected):
        _attempt(replay, with_reaction=True)
    assert replay.replayed_rejection
    assert len(replay.data["queue"]) == 1
    _attempt(replay)
    assert replay.log == resumed.log
    assert encode(board_copy(replay.state)) == encode(board_copy(resumed.state))


@pytest.mark.parametrize("change", ["receipt", "success", "unmarked_rejection"])
def test_replay_checks_refusal_instead_of_trusting_recorded_receipt(change):
    session = _session()
    initial = encode(board_copy(session.state))
    session.import_inbox([{"response": _plan()}])
    with pytest.raises(ActionRejected):
        _attempt(session)
    entry = deepcopy(session.log[0])
    if change == "receipt":
        entry["assistant_rejected"]["answer"] = True
    replay = _session(decode(initial))
    replay.data["expected"] = [{"id": entry["assistant_id"],
        "signature": entry["assistant_signature"],
        "assistant_rejected": entry["assistant_rejected"]}]
    replay.data["queue"] = [replay._inbox_entry(entry)]
    with pytest.raises(RuntimeError, match="Replay"):
        if change == "unmarked_rejection":
            driver = _driver(replay)
            with _action_transaction(replay.state, driver):
                driver()
                raise ActionRejected({"reason": "Different invalid plan"})
        else:
            _attempt(replay, refuse=change != "success")
    assert replay.log == []


def _fake_card(state, decision, *, execute):
    """Exercise the real transaction/frontend contract without game mechanics."""
    state.setdefault("_card_turn", {
        "card": state["current_card"], "idx": 0, "frost": False,
        "arverni_phase": None, "eligible": [rc.ROMANS], "first_action": None,
        "actions_taken": {}, "passes": [], "factions_done": False,
    })
    with _action_transaction(state, decision):
        response = decision(state, rc.ROMANS, [ACTION_COMMAND, ACTION_PASS], "1st_eligible")
        if response["action"] == ACTION_COMMAND:
            raise ActionRejected({"reason": "Aedui refused Supply",
                                  "supply_reconsideration": _receipt(state)})
        state.pop("_card_turn", None)
        state["current_card"] = None
    return {"card": 1, "game_over": True}


def test_file_frontend_replay_continues_past_verified_refused_attempt(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(llm_seat, "play_card", _fake_card)
    args = SimpleNamespace(dir=str(tmp_path / "game"), scenario=rc.SCENARIO_GREAT_REVOLT,
                           seat=rc.ROMANS, seed=5)
    llm_seat.cmd_init(args)
    llm_seat.cmd_play(args)
    args.response = json.dumps(_plan())
    llm_seat.cmd_submit(args)
    _, meta, log = load_game(tmp_path / "game/save.json")
    assert len(log) == 1 and log[0]["assistant_rejected"]
    assert meta["assistant_session"]["pending"]["id"] == "d000002"
    args.response = json.dumps({"action": ACTION_PASS})
    llm_seat.cmd_submit(args)
    args.output_dir = str(tmp_path / "replay")
    assert llm_seat.cmd_replay(args) == 0
    live, _, original_log = load_game(tmp_path / "game/save.json")
    replayed, _, replay_log = load_game(tmp_path / "replay/save.json")
    assert encode(live) == encode(replayed)
    assert original_log == replay_log


def test_cli_records_refusal_and_replays_it_before_correction(tmp_path, monkeypatch):
    choices = iter([_plan(), {"action": ACTION_PASS}])
    monkeypatch.setattr(app, "make_decision_func", lambda *a, **kw: lambda *args: next(choices))

    def card(state, decision, *, execute):
        while True:
            try:
                return _fake_card(state, decision, execute=execute)
            except ActionRejected as error:
                decision.decision_rejected(state, rc.ROMANS, error.result)

    monkeypatch.setattr(app, "play_card", card)
    saved = tmp_path / "game.json"
    assert app.main(["--scenario", rc.SCENARIO_GREAT_REVOLT, "--seed", "5",
                     "--bots", "Arverni,Aedui,Belgae", "--save", str(saved)],
                    stdin=io.StringIO(), stdout=io.StringIO()) == 0
    original, _, log = load_game(saved)
    assert len(log) == 2 and log[0]["supply_reconsideration"]
    replayed_path = tmp_path / "replayed.json"
    assert app.main(["--replay", str(saved), "--save", str(replayed_path)],
                    stdin=io.StringIO(), stdout=io.StringIO()) == 0
    replayed, _, replay_log = load_game(replayed_path)
    assert encode(original) == encode(replayed)
    assert replay_log == log
