"""Reproduce these fixtures using an unmodified checkout of source 8ef88e2.

Run from that checkout with its directory as the first argument, and a new
output directory as the second. These are controlled compatibility fixtures
generated with the old engine, not recovered user saves. Keep their original
bytes and provenance when making future engine changes.
"""
from pathlib import Path
import contextlib
import copy
import hashlib
import io
import json
import sys

SOURCE_COMMIT = "8ef88e21b437d23bb82f7b404df79bbabeb11d9b"
SOURCE_SHA256 = "56f041efb20a1d90f3b713973911ce0ba1216dc0a1aa1d4173ef6238c125c024"


def digest(value):
    from fs_bot.state.serialize import encode
    body = json.dumps(encode(value), separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def bot_decision():
    from fs_bot.cli.dispatcher import make_decision_func
    return make_decision_func({}, stdin=io.StringIO(),
                              stdout=io.StringIO(), pause=False)


def resume_funding(state, meta, log):
    from fs_bot import rules_consts as rc
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.engine.frumentum import resolve_frumentum
    from fs_bot.tools.seat_session import SeatSession
    session = SeatSession(state, meta, log, HumanTurnDisplay(io.StringIO()))

    def agent(board, faction, request):
        if request["kind"] == "frumentum_amount":
            return {"amount": 4}
        return session.reactive(board, faction, request)

    state["decision_agent"] = agent
    driver = lambda *_: None
    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    pending = session.data["pending"]
    session.import_inbox({"decision_id": pending["id"],
                          "response": {"decline": True}})
    with _action_transaction(state, driver):
        resolve_frumentum(state)
    session.finish()
    state.pop("decision_agent", None)
    return {"state": state, "meta": meta, "log": log}


def continue_fixture(kind, state, meta, log):
    from fs_bot.engine import game_engine as ge
    if kind == "pending-frumentum":
        return resume_funding(state, meta, log)
    if kind == "pending-card-turn":
        result = ge.resolve_card_turn(
            state, lambda *_: {"action": ge.ACTION_PASS}, execute=True)
    else:
        result = ge.play_card(state, bot_decision(), execute=True)
    # The saved board includes exact RNG, pending cursors and any persisted
    # results. Ephemeral result diagnostics in the old engine sometimes used
    # set order, so their display ordering is not a compatibility contract.
    return {"state": state}


def generate(source, output):
    sys.path.insert(0, str(source))
    from fs_bot import rules_consts as rc
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.engine import game_engine as ge
    from fs_bot.engine.frumentum import resolve_frumentum
    from fs_bot.state.serialize import save_game, load_game
    from fs_bot.state.setup import setup_scenario
    from fs_bot.tools.seat_session import SeatSession, DecisionPending
    assert source in Path(rc.__file__).resolve().parents
    source_digest = hashlib.sha256()
    for path in sorted((source / "fs_bot").rglob("*.py")):
        source_digest.update(str(path.relative_to(source)).encode() + b"\0" + path.read_bytes())
    if source_digest.hexdigest() != SOURCE_SHA256:
        raise ValueError("Fixture generation requires the exact recorded old source")
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"source_commit": SOURCE_COMMIT,
                "source_sha256": source_digest.hexdigest(),
                "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "comparison": "Exact continued board including RNG/cursors; assistant fixture also compares metadata and decision log. Excludes unpersisted diagnostic order.",
                "origin": "Generated using an unmodified archive of the specified commit; controlled positions, not user saves.",
                "fixtures": {}}

    def preserve(name, kind, state, meta=None, log=None):
        path = output / name
        save_game(state, path, meta=meta, log=log)
        resumed, saved_meta, saved_log = load_game(path, validate=True)
        with contextlib.redirect_stdout(io.StringIO()):
            expected = continue_fixture(kind, resumed, saved_meta, saved_log)
        manifest["fixtures"][name] = {
            "kind": kind,
            "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "continued_sha256": digest(expected),
            "scenario": state["scenario"],
            "seed": (meta or {}).get("seed"),
        }

    state = setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=42)
    state["current_card"], state["next_card"] = 1, 2
    for faction in ge.get_sop_factions(state):
        state["eligibility"][faction] = rc.ELIGIBLE

    def pause(board, faction, options, position):
        if faction == rc.ROMANS:
            return {"action": ge.ACTION_PASS}
        raise EOFError()

    try:
        ge.resolve_card_turn(state, pause, execute=True)
    except EOFError:
        pass
    preserve("pending-card-turn.json", "pending-card-turn", state,
             {"scenario": rc.SCENARIO_PAX_GALLICA, "seed": 42})

    state = setup_scenario(rc.SCENARIO_ARIOVISTUS, seed=17)
    state["non_player_factions"] = {rc.BELGAE, rc.GERMANS}
    meta = {"seat": rc.ROMANS, "scenario": state["scenario"], "seed": 17}
    session = SeatSession(state, meta, [], HumanTurnDisplay(io.StringIO()))

    def agent(board, faction, request):
        if request["kind"] == "frumentum_amount":
            return {"amount": 4}
        return session.reactive(board, faction, request)

    state["decision_agent"] = agent
    driver = lambda *_: None
    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    session.import_inbox([{"response": {
        "command": "March", "sa": "No SA", "details": {
            "origins": [rc.PROVINCIA], "destinations": [rc.SEQUANI],
            "routes": {rc.PROVINCIA: [rc.SEQUANI]},
            "groups": {rc.PROVINCIA: {rc.AUXILIA: 1, rc.LEADER: False}}}}}])
    try:
        with ge._action_transaction(state, driver):
            resolve_frumentum(state)
    except DecisionPending:
        pass
    assert len(session.data["journal"]) == 1
    assert session.data["pending"]["id"] == "d000002"
    preserve("pending-frumentum.json", "pending-frumentum", state,
             meta, session.log)

    # Capture a real bot game's boundaries around its automatic Interlude.
    found = False
    for seed in range(1, 21):
        state = setup_scenario(rc.SCENARIO_GALLIC_WAR, seed=seed)
        state["non_player_factions"] = set(ge.get_sop_factions(state))
        ge.start_game(state)
        decision = bot_decision()
        while state["current_card"] is not None:
            before = copy.deepcopy(state)
            with contextlib.redirect_stdout(io.StringIO()):
                result = ge.play_card(state, decision, execute=True)
            if state.get("interlude_completed") and not before.get("interlude_completed"):
                meta = {"scenario": rc.SCENARIO_GALLIC_WAR, "seed": seed}
                preserve("pre-interlude.json", "pre-interlude", before, meta)
                preserve("post-interlude.json", "post-interlude", state, meta)
                found = True
                break
            if result.get("game_over"):
                break
        if found:
            break
    assert found, "Fixture seed search did not reach the Interlude"
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    generate(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
