"""Balance-drift guardrail: bot-only games on fixed seeds vs a stored baseline.

The engine is deterministic for a given (scenario, seed), so any change in a
game's winner is real code drift, not sampling noise. This tool replays a fixed
matrix of bot-only games, diffs winners against ``balance_baseline.json``, and
fails when any faction's win rate moves more than ``--band`` within a scenario.
After an *intended* change, refresh with ``--update``.

    python -m fs_bot.tools.balance_smoke              # check (exit 1 on drift)
    python -m fs_bot.tools.balance_smoke --update     # rebaseline
    python -m fs_bot.tools.balance_smoke --seeds 1-5  # quicker spot check

Caught during bring-up: The Great Revolt is Arverni-won in every bot-only game
(see QUESTIONS.md Q12). A guardrail makes any future shift in that pattern
visible immediately.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
from collections import Counter
from pathlib import Path

# Pin the hash seed for reproducibility (re-exec once). lod-bot's analogous
# engine had set/dict-iteration-order sensitivity that reached bot decisions;
# pinning makes this guardrail exact regardless of whether fs-bot shares it.
_HASHSEED = "0"
if os.environ.get("PYTHONHASHSEED") != _HASHSEED and __name__ == "__main__":
    os.environ["PYTHONHASHSEED"] = _HASHSEED
    os.execv(sys.executable, [sys.executable, "-m",
                              "fs_bot.tools.balance_smoke"] + sys.argv[1:])

import fs_bot.rules_consts as rc
from fs_bot.state.setup import setup_scenario
from fs_bot.engine.game_engine import run_game, ACTION_EVENT, get_sop_factions
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.cli.dispatcher import _translate_bot_action

BASELINE_PATH = Path(__file__).resolve().parent / "balance_baseline.json"
SCENARIOS = (rc.SCENARIO_PAX_GALLICA, rc.SCENARIO_RECONQUEST,
             rc.SCENARIO_GREAT_REVOLT)
FACTIONS = (rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE)


def play_bot_game(scenario, seed):
    st = setup_scenario(scenario, seed=seed)
    st["non_player_factions"] = set(get_sop_factions(st))

    def decision_func(state, faction, options, position):
        state["current_card_id"] = state.get("current_card")
        state["is_second_eligible"] = (position == "2nd_eligible")
        state["can_play_event"] = (ACTION_EVENT in options)
        ba = dispatch_bot_turn(state, faction)
        return {"action": _translate_bot_action(ba, options), "bot_action": ba}

    with contextlib.redirect_stdout(io.StringIO()):
        res = run_game(st, decision_func=decision_func, execute=True)
    winner = None
    for cr in res["card_results"]:
        if cr.get("winner"):
            winner = cr["winner"]
    return {"winner": winner or "none", "cards": res["total_cards_played"]}


def _seed_range(spec):
    lo, _, hi = spec.partition("-")
    return range(int(lo), int(hi or lo) + 1)


def _rates(games, scenario):
    wins = Counter(v["winner"] for k, v in games.items()
                   if k.startswith(scenario + "|"))
    n = sum(wins.values())
    return {f: wins.get(f, 0) / n for f in FACTIONS} if n else {}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1-20")
    ap.add_argument("--scenarios", default="|".join(SCENARIOS))
    ap.add_argument("--band", type=float, default=0.15)
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--baseline", default=str(BASELINE_PATH))
    args = ap.parse_args(argv)

    scenarios = [s for s in args.scenarios.split("|") if s]
    seeds = _seed_range(args.seeds)
    bpath = Path(args.baseline)
    baseline = json.loads(bpath.read_text()) if bpath.exists() else {"games": {}}

    current = {}
    for scen in scenarios:
        for seed in seeds:
            key = f"{scen}|{seed}"
            r = play_bot_game(scen, seed)
            current[key] = r
            print(f"[{scen} seed={seed:2d}] winner={r['winner']} "
                  f"({r['cards']} cards)")

    if args.update:
        baseline["games"].update(current)
        bpath.write_text(json.dumps(baseline, indent=1, sort_keys=True) + "\n")
        print(f"\nBaseline updated: {bpath} ({len(baseline['games'])} games)")
        return 0

    base_games = {k: v for k, v in baseline["games"].items() if k in current}
    if not base_games:
        print("\nNo overlapping baseline games. Run with --update first.")
        return 2

    changed = [k for k in base_games
               if base_games[k]["winner"] != current[k]["winner"]]
    drift = False
    print("\n=== Win rates: baseline -> current ===")
    for scen in scenarios:
        b, c = _rates(base_games, scen), _rates(current, scen)
        if not b:
            continue
        for f in FACTIONS:
            d = c[f] - b[f]
            flag = ""
            if abs(d) > args.band:
                flag = f"  <-- DRIFT > ±{args.band:.0%}"
                drift = True
            if b[f] or c[f]:
                print(f"  {scen:20s} {f:<8} {b[f]:>5.0%} -> {c[f]:>5.0%} "
                      f"({d:+.0%}){flag}")
    if changed:
        print(f"\n{len(changed)} game(s) changed winner: {', '.join(sorted(changed))}")
        print("(Deterministic engine: every change is caused by a code change.)")
    if drift:
        print("\nFAIL: a faction win rate moved beyond the band.")
        print("If intended: python -m fs_bot.tools.balance_smoke --update")
        return 1
    print("\nOK: balance within band"
          + (f" ({len(changed)} winner changes)" if changed else "."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
