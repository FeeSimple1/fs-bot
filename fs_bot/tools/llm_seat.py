"""llm_seat — turn-by-turn harness for an LLM (or human) playing one seat.

Built for sandboxed assistants (ChatGPT Code Interpreter, Claude, etc.):
no interactive stdin — state persists in a save file, decisions arrive
via a JSON queue file, and each run advances the game until it is the
next human decision (including reactions), or the game ends.

Usage:
    python -m fs_bot.tools.llm_seat init --scenario "The Great Revolt" \
        --seat Arverni --seed 11 [--dir PLAYDIR]
    # write PLAYDIR/queue.json with a list of decisions, then:
    python -m fs_bot.tools.llm_seat play [--dir PLAYDIR]

Decision format (one list entry per pending decision; see
AGENT_INTERFACE.md for every plan shape):
    {"action": "command"|"command_sa"|"limited_command"|"event"|"pass",
     "player_action": {"command": ..., "regions": [...], "sa": ...,
                       "sa_regions": [...], "details": {...}}}

Every pending decision has a stable id. Submit its JSON response with:
    python -m fs_bot.tools.llm_seat submit --response '{"action":"pass"}'
For reactions, responses are a Retreat object, loss-priority list or agreement
boolean. The full request and board print before each choice. An explicit
{"use_default": true} selects the engine default for a reaction.
"""

import argparse
import json
import os
import sys
import tempfile

import fs_bot.rules_consts as rc
from fs_bot.state.setup import setup_scenario
from fs_bot.state.serialize import save_game, load_game, encode, decode
from fs_bot.engine.game_engine import (start_game, play_card, ACTION_EVENT,
                                       get_sop_factions, ActionRejected)
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.cli.dispatcher import _translate_bot_action
from fs_bot.cli.display import HumanTurnDisplay, format_board
from fs_bot.tools.seat_session import (SeatSession, DecisionPending, board_copy,
                                      fingerprint)


def render_board(state, scenario=None, options=None, position=None):
    """Full live board; scenario always comes from the current game state."""
    out = format_board(state)
    if options:
        out += f"\nYOUR TURN ({position}): options={options}"
    return out


def cmd_init(args):
    os.makedirs(args.dir, exist_ok=True)
    setup_args = {"seed": args.seed}
    if getattr(args, "card_edition", "legacy") != "legacy":
        setup_args["card_edition"] = args.card_edition
    if getattr(args, "diviciacus_option", False):
        setup_args["diviciacus_option"] = True
    st = setup_scenario(args.scenario, **setup_args)
    factions = set(get_sop_factions(st))
    if args.seat not in factions:
        raise SystemExit(f"seat {args.seat!r} not in {sorted(factions)}")
    st["non_player_factions"] = factions - {args.seat}
    start_game(st)
    display = HumanTurnDisplay(sys.stdout)
    display.remember(st, [args.seat])
    meta = {"scenario": args.scenario, "seed": args.seed, "seat": args.seat,
            "initial_seat": args.seat,
            "card_edition": st.get("card_edition", "legacy"),
            "diviciacus_option": st.get("diviciacus_option", False),
            "initial_faction_modes": {f: "human" if f == args.seat else "bot"
                                      for f in factions},
            "human_snapshots": encode(display.snapshots)}
    SeatSession(st, meta, [], display)
    save_game(st, os.path.join(args.dir, "save.json"), meta=meta, log=[])
    _write_inbox(os.path.join(args.dir, "queue.json"), [])
    print(f"initialised {args.scenario!r} seed={args.seed} "
          f"seat={args.seat}; first card: {st['current_card']}")
    print("run 'play' to advance to your first decision")


def _write_inbox(path, payload):
    """Replace an inbox only after the whole JSON document is written."""
    parent = os.path.dirname(os.path.abspath(path))
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=parent,
                                         prefix=".fsbot-inbox-", delete=False) as fh:
            temporary = fh.name
            json.dump(payload, fh)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def cmd_play(args):
    save_path = os.path.join(args.dir, "save.json")
    queue_path = os.path.join(args.dir, "queue.json")
    state, meta, log = load_game(save_path, validate=True)
    display = HumanTurnDisplay(
        sys.stdout, snapshots=decode(meta.get("human_snapshots") or {}))
    session = SeatSession(state, meta, log, display)
    state["decision_agent"] = session.reactive

    def sync_seat():
        if state.get("interlude_completed") and session.seat == rc.GERMANS:
            meta["seat"] = rc.ARVERNI
            state["non_player_factions"] = set(get_sop_factions(state)) - {rc.ARVERNI}
            if rc.GERMANS in display.snapshots:
                display.snapshots[rc.ARVERNI] = display.snapshots.pop(rc.GERMANS)
        meta["faction_modes"] = {f: "human" if f == session.seat else "bot"
                                 for f in get_sop_factions(state)}
        display.remember(state, [session.seat])

    def persist():
        # If interruption happened between engine transactions, the last
        # action already committed; its journal must commit with its board.
        session.finish()
        meta["human_snapshots"] = encode(display.snapshots)
        save_game(state, save_path, meta=meta, log=log)

    sync_seat()
    if os.path.exists(queue_path):
        try:
            with open(queue_path) as fh:
                imported = session.import_inbox(json.load(fh))
        except (ValueError, TypeError) as exc:
            print(f"Submission rejected: {exc}")
            return 2
        if imported:
            # Import receipt and queue become authoritative together before
            # executing anything. No later queue.json rewrite is necessary.
            persist()

    def dfunc(st, faction, options, position):
        if faction == session.seat:
            return session.ask(st, faction, {"kind": "turn", "options": options,
                                             "position": position})
        st["current_card_id"] = st.get("current_card")
        st["is_second_eligible"] = (position == "2nd_eligible")
        st["can_play_event"] = (ACTION_EVENT in options)
        ba = dispatch_bot_turn(st, faction)
        act = _translate_bot_action(ba, options)
        sa = ba.get("sa")
        print(f"    bot {faction}: {act} {ba.get('command')}"
              f"{'+' + sa if sa not in (None, 'No SA') else ''}")
        return {"action": act, "bot_action": ba}

    dfunc.transaction_checkpoint = session.checkpoint
    dfunc.transaction_restore = session.restore

    while state["current_card"] is not None:
        try:
            cr = play_card(state, dfunc, execute=True)
            session.finish()
        except DecisionPending:
            persist()
            if session.error:
                print(f"Decision rejected: {session.error}")
            _show_pending(session.data.get("pending"))
            return 0
        except ActionRejected as exc:
            persist()
            print(f"Decision rejected: {exc} Edit queue.json and run play again.")
            return 0
        except (KeyboardInterrupt, EOFError):
            persist()
            print("Interrupted; completed actions and earlier choices saved. Run play to resume.")
            return 0
        except Exception:
            persist()
            raise
        sync_seat()
        persist()
        if cr.get("type") == "winter":
            print(f"  ~~~ WINTER {state['winter_count']} ~~~")
        if cr.get("game_over"):
            print("*** GAME OVER")
            return 0
    persist()
    print("*** deck exhausted")
    return 0


def _show_pending(pending):
    if not pending:
        return
    request = decode(pending["request"])
    print("=" * 60)
    print(format_board(decode(pending["board"])))
    print(f"PENDING DECISION {pending['id']}: {request['kind']}")
    print(json.dumps(request, indent=2))
    print("Submit its response with: python -m fs_bot.tools.llm_seat submit "
          "--response '<JSON>' [--dir PLAYDIR]")


def cmd_board(args):
    state, meta, _log = load_game(os.path.join(args.dir, "save.json"), validate=True)
    pending = (meta.get("assistant_session") or {}).get("pending")
    if pending:
        # The durable board is at the transaction boundary, while this is
        # exactly the live board on which the pending choice must be made.
        _show_pending(pending)
    else:
        print(render_board(state))


def cmd_submit(args):
    _state, meta, _log = load_game(os.path.join(args.dir, "save.json"), validate=True)
    pending = (meta.get("assistant_session") or {}).get("pending")
    if not pending:
        print("No pending decision. Run play first.")
        return 2
    try:
        response = json.loads(args.response)
    except ValueError as exc:
        print(f"Invalid JSON response: {exc}")
        return 2
    decision_id = getattr(args, "decision_id", None) or pending["id"]
    if decision_id != pending["id"]:
        print("Submission rejected: decision_id is stale.")
        return 2
    _write_inbox(os.path.join(args.dir, "queue.json"),
                 {"decision_id": decision_id, "response": response})
    return cmd_play(args)


def cmd_replay(args):
    state, meta, log = load_game(os.path.join(args.dir, "save.json"), validate=True)
    saved = meta.get("assistant_session")
    if not saved:
        print("This older save has no assistant replay origin/history.")
        return 2
    if os.path.abspath(args.output_dir) == os.path.abspath(args.dir):
        print("Replay needs a separate output directory.")
        return 2
    if os.path.exists(args.output_dir) and os.listdir(args.output_dir):
        print("Replay output is not empty; choose an empty directory.")
        return 2
    os.makedirs(args.output_dir, exist_ok=True)
    target = os.path.join(args.output_dir, "save.json")
    origin = decode(saved["origin"])
    replay_meta = {"scenario": meta["scenario"], "seed": meta.get("seed"),
                   "seat": saved["origin_seat"],
                   "initial_seat": meta.get("initial_seat", saved["origin_seat"]),
                   "card_edition": meta.get("card_edition", "legacy"),
                   "diviciacus_option": origin.get("diviciacus_option", False)}
    view = HumanTurnDisplay(sys.stdout)
    view.remember(origin, [replay_meta["seat"]])
    replay_meta["human_snapshots"] = encode(view.snapshots)
    replay_log = log[:saved.get("origin_log_count", 0)]
    replay_session = SeatSession(origin, replay_meta, replay_log, view)
    # Older saves can first acquire an origin midway through a game. Their
    # existing CLI log predates that origin and must not be re-executed.
    origin_log_count = saved.get("origin_log_count", 0)
    entries = log[origin_log_count:] + saved["journal"]
    replay_session.data["queue"] = [SeatSession._inbox_entry(e) for e in entries]
    replay_session.data["expected"] = [
        {"id": e["assistant_id"], "signature": e["assistant_signature"]}
        for e in entries]
    save_game(origin, target, meta=replay_meta, log=replay_log)
    from argparse import Namespace
    status = cmd_play(Namespace(dir=args.output_dir))
    replayed, _meta, _log = load_game(target, validate=True)
    if fingerprint(board_copy(replayed)) != fingerprint(board_copy(state)):
        print("Replay stopped at a different checkpoint; inspect its pending decision.")
        return 1
    print("Replay verified: board and random-number state match the saved checkpoint.")
    return status


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("init")
    pi.add_argument("--scenario", required=True,
                    choices=[rc.SCENARIO_PAX_GALLICA,
                             rc.SCENARIO_GREAT_REVOLT,
                             rc.SCENARIO_RECONQUEST,
                             rc.SCENARIO_ARIOVISTUS,
                             rc.SCENARIO_GALLIC_WAR])
    pi.add_argument("--seat", required=True)
    pi.add_argument("--seed", type=int, default=1)
    pi.add_argument("--dir", default="llm_play")
    pi.add_argument("--card-edition", choices=("legacy", "original", "second-edition"),
                    default="legacy")
    pi.add_argument("--diviciacus-option", action="store_true",
                    help="Enable the optional Leader in an original scenario")
    pi.set_defaults(func=cmd_init)
    pp = sub.add_parser("play")
    pp.add_argument("--dir", default="llm_play")
    pp.set_defaults(func=cmd_play)
    pb = sub.add_parser("board", aliases=["b"],
                       help="show all card information and the live board")
    pb.add_argument("--dir", default="llm_play")
    pb.set_defaults(func=cmd_board)
    ps = sub.add_parser("submit", help="answer the pending decision and continue")
    ps.add_argument("--dir", default="llm_play")
    ps.add_argument("--decision-id", default=None)
    ps.add_argument("--response", required=True, help="JSON response to the pending request")
    ps.set_defaults(func=cmd_submit)
    pr = sub.add_parser("replay", help="replay saved human decisions into a separate directory")
    pr.add_argument("--dir", default="llm_play")
    pr.add_argument("--output-dir", required=True)
    pr.set_defaults(func=cmd_replay)
    args = p.parse_args(argv)
    try:
        return args.func(args)
    except (OSError, ValueError) as exc:
        print(f"Cannot continue: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
