"""Tribe/piece sync checker.

``state["tribes"]`` (authoritative for victory) and per-space ALLY/CITADEL
pieces can drift apart: several Event handlers in cards/card_effects.py set
``allied_faction`` without placing/removing the corresponding piece (or vice
versa). This tool replays bot-only games and reports, per Event card, the
desyncs it introduces, to scope the cleanup.

    python -m fs_bot.tools.sync_check --scenario "Reconquest of Gaul" --seeds 1-5
"""
from __future__ import annotations

import argparse
import collections
import contextlib
import io

import fs_bot.rules_consts as rc
from fs_bot.state.setup import setup_scenario
from fs_bot.engine.game_engine import (play_card, start_game, ACTION_EVENT,
                                       get_sop_factions, is_winter_card)
from fs_bot.engine.victory import TRIBE_TO_REGION
from fs_bot.board.pieces import count_pieces
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.cli.dispatcher import _translate_bot_action


def desyncs(state):
    """Set of (region, faction, allied_tribes, ally+citadel_pieces) where
    the tribes dict and the space pieces disagree.

    Checks BOTH directions: every (region, faction) with allied tribes, and
    every (region, faction) with ALLY/CITADEL pieces on the map. Dynamic
    tribes (Card 71 Colony) carry their Region in the tribes-dict entry.
    """
    per = {}
    for tribe, info in state["tribes"].items():
        fac = info.get("allied_faction")
        reg = info.get("region") or TRIBE_TO_REGION.get(tribe)
        if fac and reg:
            per[(reg, fac)] = per.get((reg, fac), 0) + 1
    keys = set(per)
    for reg in state["spaces"]:
        for fac in rc.FACTIONS:
            if (count_pieces(state, reg, fac, rc.ALLY)
                    + count_pieces(state, reg, fac, rc.CITADEL)) > 0:
                keys.add((reg, fac))
    out = set()
    for (reg, fac) in keys:
        n = per.get((reg, fac), 0)
        pieces = (count_pieces(state, reg, fac, rc.ALLY)
                  + count_pieces(state, reg, fac, rc.CITADEL))
        if pieces != n:
            out.add((reg, fac, n, pieces))
    return out


def _bot_func(state, faction, options, position):
    state["current_card_id"] = state.get("current_card")
    state["is_second_eligible"] = (position == "2nd_eligible")
    state["can_play_event"] = (ACTION_EVENT in options)
    ba = dispatch_bot_turn(state, faction)
    return {"action": _translate_bot_action(ba, options), "bot_action": ba}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default=rc.SCENARIO_RECONQUEST)
    ap.add_argument("--seeds", default="1-5")
    args = ap.parse_args(argv)
    lo, _, hi = args.seeds.partition("-")

    by_card = collections.defaultdict(set)
    for seed in range(int(lo), int(hi or lo) + 1):
        st = setup_scenario(args.scenario, seed=seed)
        st["non_player_factions"] = set(get_sop_factions(st))
        with contextlib.redirect_stdout(io.StringIO()):
            start_game(st)
        prev = desyncs(st)
        if prev:
            print(f"[seed {seed}] desyncs AT SETUP: {sorted(prev)}")
        while st["current_card"] is not None:
            cid = st["current_card"]
            with contextlib.redirect_stdout(io.StringIO()):
                cr = play_card(st, _bot_func, execute=True)
            now = desyncs(st)
            for d in now - prev:
                tag = "WINTER" if is_winter_card(cid) else f"card {cid}"
                by_card[tag].add((seed,) + d)
            prev = now
            if cr["game_over"]:
                break

    if not by_card:
        print("No tribe/piece desyncs found.")
        return 0
    print(f"\n{len(by_card)} distinct cards/phases introduced desyncs:")
    for tag in sorted(by_card, key=str):
        print(f"  {tag}: {len(by_card[tag])} occurrence(s)")
        for occ in sorted(by_card[tag])[:3]:
            print(f"     seed={occ[0]} region={occ[1]} faction={occ[2]} "
                  f"tribes={occ[3]} pieces={occ[4]}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
