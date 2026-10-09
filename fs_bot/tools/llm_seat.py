"""llm_seat — turn-by-turn harness for an LLM (or human) playing one seat.

Built for sandboxed assistants (ChatGPT Code Interpreter, Claude, etc.):
no interactive stdin — state persists in a save file, decisions arrive
via a JSON queue file, and each run advances the game until it is the
seat's turn again (then prints the board and halts) or the game ends.

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

The default reactive policy for the seat: stand where Allies/Citadels/
Settlements anchor, otherwise retreat; harass everyone; agree to
nothing. Override by editing reactive_policy() below if desired.
"""

import argparse
import copy
import json
import os
import sys

import fs_bot.rules_consts as rc
from fs_bot.state.setup import setup_scenario
from fs_bot.state.serialize import save_game, load_game, encode, decode
from fs_bot.engine.game_engine import (start_game, play_card, ACTION_EVENT,
                                       get_sop_factions, ActionRejected)
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.cli.dispatcher import _translate_bot_action
from fs_bot.cli.display import HumanTurnDisplay, format_board
from fs_bot.engine.agent import RETREAT, LOSS_ORDER, AGREEMENT
from fs_bot.board.pieces import count_pieces


def reactive_policy(seat):
    def reactive(state, faction, request):
        if faction != seat:
            return None
        kind = request.get("kind")
        if kind == RETREAT:
            region = request.get("region")
            anchors = 0
            for pt in (rc.ALLY, rc.CITADEL, rc.SETTLEMENT):
                try:
                    anchors += count_pieces(state, region, seat, pt)
                except Exception:
                    pass
            if anchors > 0:
                return {"retreat": False, "region": None}
            legal = request.get("legal_regions") or []
            return {"retreat": bool(legal),
                    "region": legal[0] if legal else None}
        if kind == LOSS_ORDER:
            return None                    # engine default order
        if kind == AGREEMENT:
            if request.get("request_type") == "harassment":
                return True                # harass everyone
            return False                   # agree to nothing
        return None
    return reactive


def render_board(state, scenario=None, options=None, position=None):
    """Full live board; scenario always comes from the current game state."""
    out = format_board(state)
    if options:
        out += f"\nYOUR TURN ({position}): options={options}"
    return out


class _Halt(Exception):
    pass


def cmd_init(args):
    os.makedirs(args.dir, exist_ok=True)
    st = setup_scenario(args.scenario, seed=args.seed)
    factions = set(get_sop_factions(st))
    if args.seat not in factions:
        raise SystemExit(f"seat {args.seat!r} not in {sorted(factions)}")
    st["non_player_factions"] = factions - {args.seat}
    start_game(st)
    display = HumanTurnDisplay(sys.stdout)
    display.remember(st, [args.seat])
    save_game(st, os.path.join(args.dir, "save.json"),
              meta={"scenario": args.scenario, "seed": args.seed,
                    "seat": args.seat,
                    "human_snapshots": encode(display.snapshots)})
    json.dump([], open(os.path.join(args.dir, "queue.json"), "w"))
    print(f"initialised {args.scenario!r} seed={args.seed} "
          f"seat={args.seat}; first card: {st['current_card']}")
    print("run 'play' to advance to your first decision")


def cmd_play(args):
    save_path = os.path.join(args.dir, "save.json")
    queue_path = os.path.join(args.dir, "queue.json")
    state, meta, _log = load_game(save_path)
    seat = meta["seat"]
    state["decision_agent"] = reactive_policy(seat)
    queue = (json.load(open(queue_path))
             if os.path.exists(queue_path) else [])
    halted = {}
    display = HumanTurnDisplay(
        sys.stdout, snapshots=decode(meta.get("human_snapshots") or {}))

    def sync_seat():
        nonlocal seat
        if state.get("interlude_completed") and seat == rc.GERMANS:
            old = seat
            seat = rc.ARVERNI
            meta["seat"] = seat
            state["non_player_factions"] = set(get_sop_factions(state)) - {seat}
            state["decision_agent"] = reactive_policy(seat)
            if old in display.snapshots:
                display.snapshots[seat] = display.snapshots.pop(old)
        display.remember(state, [seat])

    def persist():
        meta["human_snapshots"] = encode(display.snapshots)
        save_game(state, save_path, meta=meta)
        with open(queue_path, "w") as fh:
            json.dump(queue, fh)

    sync_seat()

    def dfunc(st, faction, options, position):
        if faction == seat:
            if queue:
                display.before_decision(st, faction)
                dec = queue.pop(0)
                print(f">>> applying: {json.dumps(dec)[:110]}")
                return dec
            halted.update(options=options, position=position)
            raise _Halt()
        st["current_card_id"] = st.get("current_card")
        st["is_second_eligible"] = (position == "2nd_eligible")
        st["can_play_event"] = (ACTION_EVENT in options)
        ba = dispatch_bot_turn(st, faction)
        act = _translate_bot_action(ba, options)
        sa = ba.get("sa")
        print(f"    bot {faction}: {act} {ba.get('command')}"
              f"{'+' + sa if sa not in (None, 'No SA') else ''}")
        return {"action": act, "bot_action": ba}

    def checkpoint():
        return copy.deepcopy(queue), copy.deepcopy(display.snapshots)

    def restore(token):
        queue[:] = token[0]
        display.snapshots.clear()
        display.snapshots.update(token[1])

    dfunc.transaction_checkpoint = checkpoint
    dfunc.transaction_restore = restore

    while state["current_card"] is not None:
        try:
            cr = play_card(state, dfunc, execute=True)
        except _Halt:
            display.before_decision(state, seat)
            print("=" * 60)
            print(render_board(state, options=halted["options"],
                               position=halted["position"]))
            persist()
            return
        except ActionRejected as exc:
            persist()
            print(f"Decision rejected: {exc} Edit queue.json and run play again.")
            return
        except (KeyboardInterrupt, EOFError):
            persist()
            print("Interrupted; completed actions saved. Run play to resume.")
            return
        sync_seat()
        if cr.get("type") == "winter":
            print(f"  ~~~ WINTER {state['winter_count']} ~~~")
            wr = (cr.get("winter_result") or {}).get("winter_result") or {}
            v = (wr.get("phases") or {}).get("victory") or {}
            if v.get("game_over"):
                print(f"*** GAME OVER: winner={v.get('winner')} "
                      f"rankings={v.get('rankings')}")
                persist()
                return
        if cr.get("game_over"):
            print("*** GAME OVER (deck exhausted or outright win)")
            persist()
            return
        persist()
    print("*** deck exhausted")


def cmd_board(args):
    state, _meta, _log = load_game(os.path.join(args.dir, "save.json"))
    print(render_board(state))


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
    pi.set_defaults(func=cmd_init)
    pp = sub.add_parser("play")
    pp.add_argument("--dir", default="llm_play")
    pp.set_defaults(func=cmd_play)
    pb = sub.add_parser("board", aliases=["b"],
                       help="show all card information and the live board")
    pb.add_argument("--dir", default="llm_play")
    pb.set_defaults(func=cmd_board)
    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
