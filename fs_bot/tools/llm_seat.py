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
import io
import json
import os
import sys

import fs_bot.rules_consts as rc
from fs_bot.state.setup import setup_scenario
from fs_bot.state.serialize import save_game, load_game
from fs_bot.engine.game_engine import (start_game, play_card, ACTION_EVENT,
                                       get_sop_factions)
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.cli.dispatcher import _translate_bot_action
from fs_bot.engine.agent import RETREAT, LOSS_ORDER, AGREEMENT
from fs_bot.engine.victory import calculate_victory_score, VictoryError
from fs_bot.board.pieces import count_pieces, get_leader_in_region
from fs_bot.cards.card_data import get_card


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


def render_board(state, scenario, options=None, position=None):
    out = []
    out.append(f"card={state['current_card']} next={state['next_card']} "
               f"winters={state['winter_count']}")
    try:
        c = get_card(state["current_card"], scenario)
        out.append(f"  [{c.title}] "
                   f"order={'>'.join(f[:2] for f in c.faction_order)}")
    except Exception:
        pass
    res = state["resources"]
    out.append("res:   " + "  ".join(
        f"{f[:2]}={res.get(f, 0)}" for f in rc.FACTIONS
        if f in res))
    scores = []
    for f in rc.FACTIONS:
        try:
            scores.append(f"{f[:2]}={calculate_victory_score(state, f)}")
        except (VictoryError, Exception):
            pass
    out.append("score: " + "  ".join(scores))
    out.append(f"senate: {state.get('senate')}  "
               f"track={state.get('legions_track')} "
               f"fallen={state.get('fallen_legions', 0)}")
    for r in sorted(state["spaces"]):
        sp = state["spaces"][r]
        bits = []
        for f in rc.FACTIONS:
            t = []
            for pt, tag in ((rc.WARBAND, "w"), (rc.AUXILIA, "x"),
                            (rc.LEGION, "L"), (rc.ALLY, "A"),
                            (rc.CITADEL, "C"), (rc.FORT, "F"),
                            (rc.SETTLEMENT, "S")):
                n = count_pieces(state, r, f, pt)
                if n:
                    t.append(f"{n}{tag}")
            if get_leader_in_region(state, r, f):
                t.append("Ldr")
            if t:
                bits.append(f"{f[:2]}:{'+'.join(t)}")
        ctrl = (sp.get("control") or "")[:2]
        subdued = [t_ for t_, ti in state["tribes"].items()
                   if ti.get("allied_faction") is None
                   and ti.get("status") is None
                   and rc.TRIBE_TO_REGION.get(t_) == r]
        out.append(f"  {r:12s} [{ctrl:2s}] {'  '.join(bits)}"
                   + (f"  subdued:{','.join(subdued)}" if subdued else ""))
    markers = state.get("markers") or {}
    marked = {r: m for r, m in markers.items() if m}
    if marked:
        out.append(f"markers: {json.dumps(marked, default=str)}")
    if options:
        out.append(f"YOUR TURN ({position}): options={options}")
    return "\n".join(out)


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
    save_game(st, os.path.join(args.dir, "save.json"),
              meta={"scenario": args.scenario, "seed": args.seed,
                    "seat": args.seat})
    json.dump([], open(os.path.join(args.dir, "queue.json"), "w"))
    print(f"initialised {args.scenario!r} seed={args.seed} "
          f"seat={args.seat}; first card: {st['current_card']}")
    print("run 'play' to advance to your first decision")


def cmd_play(args):
    save_path = os.path.join(args.dir, "save.json")
    queue_path = os.path.join(args.dir, "queue.json")
    state, meta, _log = load_game(save_path)
    scenario, seat = meta["scenario"], meta["seat"]
    state["decision_agent"] = reactive_policy(seat)
    queue = (json.load(open(queue_path))
             if os.path.exists(queue_path) else [])
    halted = {}

    def dfunc(st, faction, options, position):
        # Gallic War Interlude seat swap (A2.1): German seat -> Arverni.
        nonlocal seat
        if st.get("interlude_completed") and seat == rc.GERMANS:
            seat = rc.ARVERNI
            meta["seat"] = seat
            st["non_player_factions"] = (
                set(get_sop_factions(st)) - {seat})
            st["decision_agent"] = reactive_policy(seat)
        if faction == seat:
            if queue:
                dec = queue.pop(0)
                print(f">>> applying: {json.dumps(dec)[:110]}")
                return dec
            halted["board"] = render_board(st, scenario, options, position)
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

    while state["current_card"] is not None:
        try:
            cr = play_card(state, dfunc, execute=True)
        except _Halt:
            save_game(state, save_path, meta=meta)
            json.dump(queue, open(queue_path, "w"))
            print("=" * 60)
            print(halted["board"])
            return
        if cr.get("type") == "winter":
            print(f"  ~~~ WINTER {state['winter_count']} ~~~")
            wr = (cr.get("winter_result") or {}).get("winter_result") or {}
            v = (wr.get("phases") or {}).get("victory") or {}
            if v.get("game_over"):
                print(f"*** GAME OVER: winner={v.get('winner')} "
                      f"rankings={v.get('rankings')}")
                save_game(state, save_path, meta=meta)
                return
        if cr.get("game_over"):
            print("*** GAME OVER (deck exhausted or outright win)")
            save_game(state, save_path, meta=meta)
            return
        save_game(state, save_path, meta=meta)
        json.dump(queue, open(queue_path, "w"))
    print("*** deck exhausted")


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
    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
