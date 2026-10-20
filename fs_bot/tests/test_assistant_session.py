"""Human decisions survive pauses and crashes without automatic policy choices."""
import copy
import io
import json
from types import SimpleNamespace

import pytest

import fs_bot.rules_consts as rc
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine.agent import consult_agent, RETREAT, LOSS_ORDER, AGREEMENT
from fs_bot.engine.game_engine import _action_transaction
from fs_bot.state.setup import setup_scenario
from fs_bot.state.serialize import save_game, load_game, encode, decode
from fs_bot.tools.seat_session import (SeatSession, DecisionPending,
                                       validate_response, board_copy)
from fs_bot.tools import llm_seat


def _session():
    st = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=7)
    meta = {"seat": rc.ROMANS, "scenario": st["scenario"], "seed": 7}
    view = HumanTurnDisplay(io.StringIO())
    view.remember(st, [rc.ROMANS])
    session = SeatSession(st, meta, [], view)
    st["decision_agent"] = session.reactive
    return session


def _driver(session):
    def callback(*args):
        pass
    callback.transaction_checkpoint = session.checkpoint
    callback.transaction_restore = session.restore
    return callback


def test_reaction_pause_replays_previous_choice_and_roll_without_reprompt(tmp_path):
    session = _session()
    st = session.state
    before = encode(board_copy(st))
    request1 = {"kind": AGREEMENT, "request_type": "harassment"}
    request2 = {"kind": RETREAT, "legal_regions": [rc.PROVINCIA]}
    session.import_inbox([{"reactive": AGREEMENT, "response": False}])
    rolls = []

    def action(s):
        assert consult_agent(s, rc.ROMANS, request1) is False
        rolls.append(s["rng"].randint(1, 6))
        s["resources"][rc.ROMANS] -= 1
        return consult_agent(s, rc.ROMANS, request2)

    with pytest.raises(DecisionPending):
        with _action_transaction(st, _driver(session)):
            action(st)
    assert encode(board_copy(st)) == before
    assert len(session.data["journal"]) == 1
    assert session.log == []
    pending = session.data["pending"]
    assert decode(pending["board"])["resources"][rc.ROMANS] == st["resources"][rc.ROMANS] - 1
    save_game(st, tmp_path / "save.json", meta=session.meta, log=session.log)
    restored, meta, log = load_game(tmp_path / "save.json")
    resumed = SeatSession(restored, meta, log, HumanTurnDisplay(io.StringIO()))
    restored["decision_agent"] = resumed.reactive
    resumed.import_inbox({"decision_id": pending["id"],
                          "response": {"retreat": True, "region": rc.PROVINCIA}})
    with _action_transaction(restored, _driver(resumed)):
        assert action(restored) == {"retreat": True, "region": rc.PROVINCIA}
    resumed.finish()
    assert rolls[0] == rolls[1]
    assert len(log) == 2
    assert [entry["reactive"] for entry in log] == [AGREEMENT, RETREAT]
    assert not resumed.data["queue"]
    assert not resumed.data["journal"]


@pytest.mark.parametrize("req,response", [
    ({"kind": RETREAT, "legal_regions": [rc.AEDUI_REGION]}, {"retreat": True, "region": rc.BRITANNIA}),
    ({"kind": RETREAT, "legal_regions": []}, {"retreat": "false"}),
    ({"kind": AGREEMENT}, "false"),
    ({"kind": LOSS_ORDER, "pieces": [(rc.LEGION, None)]}, [[rc.WARBAND, None]]),
    ({"kind": LOSS_ORDER, "pieces": [(rc.LEGION, None)]}, [[rc.LEGION, None], [rc.LEGION, None]]),
    ({"kind": "turn", "options": ["pass"]}, {"action": "event"}),
])
def test_bad_response_keeps_same_decision_and_input(req, response):
    session = _session()
    session.import_inbox([{"response": response}])
    before = encode(board_copy(session.state))
    with pytest.raises(DecisionPending):
        with _action_transaction(session.state, _driver(session)):
            session.ask(session.state, rc.ROMANS, req)
    assert session.error
    assert session.data["queue"] == [{"response": response}]
    assert encode(board_copy(session.state)) == before
    assert session.data["pending"]["id"] == "d000001"


def test_invalid_paid_winter_plan_keeps_pending_id_board_rng_and_input():
    from fs_bot.board.pieces import place_piece
    session = _session()
    state = session.state
    state['resources'][rc.ROMANS] = 0
    # A Roman group pays for this Winter Campaign March, even when a free
    # Event March would have succeeded with the same empty treasury.
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 2)
    response = {'command': 'March', 'sa': 'No SA', 'details': {
        'origins': [rc.MORINI], 'destinations': [rc.BRITANNIA],
        'routes': {rc.MORINI: [rc.BRITANNIA]}}}
    session.import_inbox([{'response': response}])
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending):
        with _action_transaction(state, _driver(session)):
            session.ask(state, rc.ROMANS, {'kind': 'winter_campaign',
                                          'remaining_actions': 2})
    assert session.error
    assert session.data['queue'] == [{'response': response}]
    assert session.data['pending']['id'] == 'd000001'
    assert session.data['journal'] == []
    assert encode(board_copy(state)) == before


@pytest.mark.parametrize("req", [
    {"kind": RETREAT, "legal_regions": []},
    {"kind": LOSS_ORDER, "pieces": [(rc.LEGION, None)]},
    {"kind": AGREEMENT, "request_type": "harassment"},
    {"kind": AGREEMENT, "request_type": "supply_line"},
    {"kind": AGREEMENT, "request_type": "quarters"},
    {"kind": AGREEMENT, "request_type": "trade_roman_agreement"},
    {"kind": AGREEMENT, "request_type": "retreat_into_control"},
    {"kind": "quarters_plan"},
    {"kind": "winter_campaign"},
])
def test_every_human_reaction_pauses_without_an_answer(req):
    session = _session()
    with pytest.raises(DecisionPending):
        with _action_transaction(session.state, _driver(session)):
            consult_agent(session.state, rc.ROMANS, req)
    assert decode(session.data["pending"]["request"])["kind"] == req["kind"]
    assert session.log == []


def test_loss_order_accepts_repeated_present_pieces_and_enlist_owner():
    req = {"kind": LOSS_ORDER, "pieces": [(rc.WARBAND, None),
        (rc.WARBAND, None), (rc.WARBAND, rc.HIDDEN, rc.GERMANS)]}
    response = [[rc.WARBAND, None], [rc.WARBAND, None],
                [rc.WARBAND, rc.HIDDEN, rc.GERMANS]]
    assert validate_response({}, req, response) == response


def test_stale_inbox_cannot_repeat_a_consumed_decision(tmp_path):
    args = SimpleNamespace(dir=str(tmp_path), scenario=rc.SCENARIO_GREAT_REVOLT,
                           seat=rc.BELGAE, seed=1)
    llm_seat.cmd_init(args)
    llm_seat.cmd_play(args)
    _, meta, _ = load_game(tmp_path / "save.json")
    decision_id = meta["assistant_session"]["pending"]["id"]
    payload = {"decision_id": decision_id, "response": {"action": "pass"}}
    (tmp_path / "queue.json").write_text(json.dumps(payload))
    llm_seat.cmd_play(args)
    saved1, meta1, log1 = load_game(tmp_path / "save.json")
    # The old submitted file deliberately remains on disk: the save's receipt
    # is authoritative even if a process died immediately after its replace.
    assert json.loads((tmp_path / "queue.json").read_text()) == payload
    llm_seat.cmd_play(args)
    saved2, meta2, log2 = load_game(tmp_path / "save.json")
    assert encode(saved1) == encode(saved2)
    assert log1 == log2
    assert meta1["assistant_session"]["journal"] == meta2["assistant_session"]["journal"]


def test_failed_save_does_not_consume_submission_on_disk(tmp_path, monkeypatch):
    args = SimpleNamespace(dir=str(tmp_path), scenario=rc.SCENARIO_GREAT_REVOLT,
                           seat=rc.BELGAE, seed=1)
    llm_seat.cmd_init(args)
    llm_seat.cmd_play(args)
    old = (tmp_path / "save.json").read_bytes()
    _, meta, _ = load_game(tmp_path / "save.json")
    inbox = {"decision_id": meta["assistant_session"]["pending"]["id"],
             "response": {"action": "pass"}}
    (tmp_path / "queue.json").write_text(json.dumps(inbox))
    real = llm_seat.save_game
    calls = []
    def fail_after_import(*a, **kw):
        calls.append(1)
        if len(calls) > 1:
            raise OSError("simulated disk failure")
        return real(*a, **kw)
    monkeypatch.setattr(llm_seat, "save_game", fail_after_import)
    with pytest.raises(OSError):
        llm_seat.cmd_play(args)
    st, meta, log = load_game(tmp_path / "save.json")
    assert meta["assistant_session"]["queue"] == [inbox]
    assert log == []
    monkeypatch.setattr(llm_seat, "save_game", real)
    llm_seat.cmd_play(args)
    _, meta, log = load_game(tmp_path / "save.json")
    entries = log + meta["assistant_session"]["journal"]
    assert sum(e["assistant_id"] == inbox["decision_id"] for e in entries) == 1


def test_saved_human_game_replays_identically(tmp_path, capsys):
    args = SimpleNamespace(dir=str(tmp_path / "live"),
                           scenario=rc.SCENARIO_GREAT_REVOLT,
                           seat=rc.ROMANS, seed=1)
    llm_seat.cmd_init(args)
    llm_seat.cmd_play(args)
    for _ in range(12):
        _, meta, _ = load_game(tmp_path / "live" / "save.json")
        pending = meta["assistant_session"]["pending"]
        req = decode(pending["request"])
        args.response = json.dumps({"action": "pass"} if req["kind"] == "turn"
                                   else {"use_default": True})
        assert llm_seat.cmd_submit(args) == 0
    args.output_dir = str(tmp_path / "replay")
    assert llm_seat.cmd_replay(args) == 0
    assert "Replay verified" in capsys.readouterr().out


def test_complete_assistant_game_includes_real_command_and_replays(tmp_path, capsys):
    args = SimpleNamespace(dir=str(tmp_path / "live"),
                           scenario=rc.SCENARIO_GREAT_REVOLT,
                           seat=rc.BELGAE, seed=1)
    llm_seat.cmd_init(args)
    llm_seat.cmd_play(args)
    args.response = json.dumps({"action": "command", "player_action": {
        "command": "Rally", "regions": [], "sa": "No SA", "details": {
            "rally_plan": {"citadels": [], "allies": [], "warbands": [rc.NERVII]}}}})
    assert llm_seat.cmd_submit(args) == 0
    for _ in range(400):
        st, meta, log = load_game(tmp_path / "live" / "save.json")
        pending = meta["assistant_session"]["pending"]
        if pending is None:
            break
        req = decode(pending["request"])
        args.response = json.dumps({"action": "pass"} if req["kind"] == "turn"
                                   else {"use_default": True})
        assert llm_seat.cmd_submit(args) == 0
        capsys.readouterr()
    else:
        raise AssertionError("Assistant game did not finish")
    assert log[0]["action"] == "command"
    assert any("reactive" in e for e in log)
    assert not meta["assistant_session"]["journal"]
    assert len(st["played_cards"]) > 10
    args.output_dir = str(tmp_path / "replay")
    assert llm_seat.cmd_replay(args) == 0


def test_bot_preview_cannot_consume_live_human_input():
    from fs_bot.bots.bot_common import predict_battle
    from fs_bot.board.pieces import place_piece
    session = _session()
    # The predictor copies the board and calls resolve_losses; the copied
    # frontend must neither attempt to copy terminal I/O nor ask a player.
    from fs_bot.rules_consts import WARBAND, ARVERNI, MANDUBII
    place_piece(session.state, MANDUBII, ARVERNI, WARBAND, 2)
    predict_battle(session.state, MANDUBII, ARVERNI, rc.ROMANS)
    assert session.data["pending"] is None
    assert session.log == []


def test_interrupt_between_actions_commits_completed_journal(tmp_path, monkeypatch):
    args = SimpleNamespace(dir=str(tmp_path), scenario=rc.SCENARIO_GREAT_REVOLT,
                           seat=rc.BELGAE, seed=1)
    llm_seat.cmd_init(args)
    llm_seat.cmd_play(args)
    _, meta, _ = load_game(tmp_path / "save.json")
    pending = meta["assistant_session"]["pending"]
    payload = {"decision_id": pending["id"], "response": {"action": "pass"}}
    (tmp_path / "queue.json").write_text(json.dumps(payload))
    def interrupt_after_action(state, decision, execute):
        with _action_transaction(state, decision):
            assert decision(state, rc.BELGAE, ["pass"], "1st_eligible")["action"] == "pass"
            state["resources"][rc.BELGAE] += 1
        raise KeyboardInterrupt()
    monkeypatch.setattr(llm_seat, "play_card", interrupt_after_action)
    llm_seat.cmd_play(args)
    _, meta, log = load_game(tmp_path / "save.json")
    assert len(log) == 1
    assert meta["assistant_session"]["journal"] == []


def test_rejected_command_can_be_corrected_by_submit(tmp_path, capsys):
    args = SimpleNamespace(dir=str(tmp_path), scenario=rc.SCENARIO_GREAT_REVOLT,
                           seat=rc.BELGAE, seed=1)
    llm_seat.cmd_init(args)
    llm_seat.cmd_play(args)
    st, meta, _ = load_game(tmp_path / "save.json")
    original_id = meta["assistant_session"]["pending"]["id"]
    args.response = json.dumps({"action": "command", "player_action": {
        "command": "Rally", "regions": [], "details": {}}})
    llm_seat.cmd_submit(args)
    rejected, meta, log = load_game(tmp_path / "save.json")
    assert encode(rejected) == encode(st)
    assert meta["assistant_session"]["pending"]["id"] == original_id
    args.response = '{"action":"pass"}'
    llm_seat.cmd_submit(args)
    corrected, meta, log = load_game(tmp_path / "save.json")
    assert log[0]["action"] == "pass"
    assert log[0]["assistant_id"] == original_id
    assert all(e.get("action") != "command" for e in log)
