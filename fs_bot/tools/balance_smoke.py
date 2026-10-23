"""Balance-drift guardrail: bot-only games on fixed seeds vs a stored baseline.

The engine is deterministic for a given (scenario, seed), so any change in a
game's winner is real code drift, not sampling noise. This tool replays a fixed
matrix of bot-only games, diffs winners against ``balance_baseline.json``, and
fails when any faction's win rate moves more than ``--band`` within a scenario.
After an *intended* change, refresh with ``--update``.

    python -m fs_bot.tools.balance_smoke              # check (exit 1 on drift)
    python -m fs_bot.tools.balance_smoke --update     # rebaseline
    python -m fs_bot.tools.balance_smoke --seeds 1-5  # quicker spot check

All five scenarios and all five factions are included. A requested game missing
from the baseline is an error, never silently excluded from the comparison.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
from collections import Counter
from fractions import Fraction
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
             rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS,
             rc.SCENARIO_GALLIC_WAR)
FACTIONS = (rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE, rc.GERMANS)


def _valid_outcome(record, scenario):
    # Gallic War can end in either half: Germans can win before Interlude,
    # Arverni after it. Standalone base/expansion scenarios have only four
    # victory factions even though the board contains all five factions.
    if scenario == rc.SCENARIO_GALLIC_WAR:
        winners = FACTIONS
    elif scenario == rc.SCENARIO_ARIOVISTUS:
        winners = (rc.ROMANS, rc.AEDUI, rc.BELGAE, rc.GERMANS)
    else:
        winners = (rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE)
    return (isinstance(record, dict) and record.get("winner") in winners
            and type(record.get("cards")) is int and record["cards"] > 0)


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
    low, high = int(lo), int(hi or lo)
    if low < 1 or high < low:
        raise ValueError("seed range must contain positive, ascending integers")
    return range(low, high + 1)


def _rates(games, scenario):
    wins = Counter(v["winner"] for k, v in games.items()
                   if k.startswith(scenario + "|"))
    n = sum(wins.values())
    # Compare exact count ratios: 16/20 - 13/20 equals the 15% band,
    # although subtraction of their binary float rates exceeds 0.15.
    return {f: Fraction(wins.get(f, 0), n) for f in FACTIONS} if n else {}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1-20")
    ap.add_argument("--scenarios", default="|".join(SCENARIOS))
    ap.add_argument("--band", type=float, default=0.15)
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--baseline", default=str(BASELINE_PATH))
    args = ap.parse_args(argv)

    scenarios = [s for s in args.scenarios.split("|") if s]
    if not scenarios or len(set(scenarios)) != len(scenarios):
        ap.error("select one or more distinct scenarios")
    unknown = [s for s in scenarios if s not in SCENARIOS]
    if unknown:
        ap.error(f"unknown scenario(s): {', '.join(unknown)}")
    try:
        seeds = _seed_range(args.seeds)
    except ValueError as exc:
        ap.error(f"invalid --seeds: {exc}")
    if not 0 <= args.band <= 1:
        ap.error("--band must be between 0 and 1")
    bpath = Path(args.baseline)
    try:
        baseline = (json.loads(bpath.read_text(encoding="utf-8"))
                    if bpath.exists() else {"games": {}})
    except (OSError, ValueError) as exc:
        print(f"Cannot read baseline: {exc}")
        return 2
    if not isinstance(baseline, dict) or not isinstance(baseline.get("games"), dict):
        print("Invalid baseline: expected a games object.")
        return 2
    requested = {f"{scen}|{seed}" for scen in scenarios for seed in seeds}
    if not args.update:
        missing = sorted(requested - baseline["games"].keys())
        if missing:
            print(f"Missing {len(missing)} requested baseline game(s): {', '.join(missing)}")
            print("No comparison performed. Review and populate the full requested baseline first.")
            return 2
        for key in sorted(requested):
            record = baseline["games"][key]
            scenario = key.rsplit("|", 1)[0]
            if not _valid_outcome(record, scenario):
                print(f"Invalid baseline game: {key}; expected an eligible winner for this scenario and positive card count.")
                return 2

    current = {}
    for scen in scenarios:
        for seed in seeds:
            key = f"{scen}|{seed}"
            r = play_bot_game(scen, seed)
            if not _valid_outcome(r, scen):
                print(f"Invalid game outcome: {key}: {r!r}")
                return 2
            current[key] = r
            print(f"[{scen} seed={seed:2d}] winner={r['winner']} "
                  f"({r['cards']} cards)")

    if args.update:
        baseline["games"].update(current)
        bpath.write_text(json.dumps(baseline, indent=1, sort_keys=True) + "\n",
                         encoding="utf-8")
        print(f"\nBaseline updated: {bpath} ({len(baseline['games'])} games)")
        return 0

    # Coverage was checked before running: both denominators contain exactly
    # the same requested (scenario, seed) pairs.
    base_games = {k: baseline["games"][k] for k in current}

    changed = [k for k in base_games
               if base_games[k]["winner"] != current[k]["winner"]]
    drift = False
    print("\n=== Win rates: baseline -> current ===")
    for scen in scenarios:
        b, c = _rates(base_games, scen), _rates(current, scen)
        for f in FACTIONS:
            d = c[f] - b[f]
            flag = ""
            if abs(d) > Fraction(str(args.band)):
                flag = f"  <-- DRIFT > ±{args.band:.0%}"
                drift = True
            if b[f] or c[f]:
                print(f"  {scen:20s} {f:<8} {float(b[f]):>5.0%} -> {float(c[f]):>5.0%} "
                      f"({float(d):+.0%}){flag}")
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
