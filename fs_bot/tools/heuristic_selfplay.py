"""Batch self-play: heuristic strategy profiles vs the NP bots.

One JSON line per game; reruns skip already-recorded games, so interrupted
batches resume for free.

    python -m fs_bot.tools.heuristic_selfplay --scenario "The Great Revolt" \
        --seeds 1-20 --out results.jsonl
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import time
from pathlib import Path

import fs_bot.rules_consts as rc
from fs_bot.state.setup import setup_scenario
from fs_bot.engine.game_engine import run_game, ACTION_EVENT, get_sop_factions
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.cli.dispatcher import _translate_bot_action
from fs_bot.agents.heuristic import (PROFILES, plan_turn, make_reactive,
                                     RandomPlanPolicy)

FACTIONS = (rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE)


def play_game(scenario, seed, agent_faction=None, planner=None):
    st = setup_scenario(scenario, seed=seed)
    st["non_player_factions"] = set(get_sop_factions(st))
    if agent_faction:
        st["decision_agent"] = make_reactive(agent_faction)

    decisions = [0]

    def decision_func(state, faction, options, position):
        if agent_faction and faction == agent_faction:
            decisions[0] += 1
            return planner(state, faction, options, position)
        state["current_card_id"] = state.get("current_card")
        state["is_second_eligible"] = (position == "2nd_eligible")
        state["can_play_event"] = (ACTION_EVENT in options)
        ba = dispatch_bot_turn(state, faction)
        return {"action": _translate_bot_action(ba, options), "bot_action": ba}

    with contextlib.redirect_stdout(io.StringIO()):
        res = run_game(st, decision_func=decision_func, execute=True)
    winner = None
    ranking = None
    for cr in res["card_results"]:
        if cr.get("winner"):
            winner = cr["winner"]
        if cr.get("final_ranking"):
            ranking = cr["final_ranking"]
    return {"winner": winner, "cards": res["total_cards_played"],
            "winters": res["winter_count"], "decisions": decisions[0],
            "ranking": ranking}


def _make(label, seed):
    if label == "BOTS":
        return None, None
    if label.startswith("RANDOM:"):
        fac = label.split(":")[1]
        pol = RandomPlanPolicy(fac, seed=seed)
        return fac, pol.plan_turn
    prof = PROFILES[label]
    custom = prof.get("planner")
    if custom is not None:
        return prof["faction"], custom
    return prof["faction"], (lambda s, f, o, p, _pr=prof:
                             plan_turn(s, f, _pr, o, p))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default=rc.SCENARIO_GREAT_REVOLT)
    ap.add_argument("--seeds", default="1-20")
    ap.add_argument("--profiles", default=None,
                    help="Comma list of profile names, RANDOM:FACTION, BOTS. "
                         "Default: all profiles + RANDOM per faction + BOTS.")
    ap.add_argument("--out", default="selfplay_results.jsonl")
    args = ap.parse_args(argv)

    lo, _, hi = args.seeds.partition("-")
    seeds = range(int(lo), int(hi or lo) + 1)
    labels = ([s.strip() for s in args.profiles.split(",") if s.strip()]
              if args.profiles else
              list(PROFILES) + [f"RANDOM:{f}" for f in FACTIONS] + ["BOTS"])

    out = Path(args.out)
    done = set()
    if out.exists():
        for line in out.read_text().splitlines():
            try:
                rec = json.loads(line)
                done.add((rec["label"], rec["scenario"], rec["seed"]))
            except Exception:
                pass

    with out.open("a") as fh:
        for label in labels:
            for seed in seeds:
                if (label, args.scenario, seed) in done:
                    continue
                fac, planner = _make(label, seed)
                t0 = time.time()
                try:
                    r = play_game(args.scenario, seed, fac, planner)
                    rec = {"label": label, "faction": fac,
                           "scenario": args.scenario, "seed": seed, **r,
                           "secs": round(time.time() - t0, 2)}
                except Exception as exc:
                    rec = {"label": label, "faction": fac,
                           "scenario": args.scenario, "seed": seed,
                           "winner": None,
                           "error": f"{type(exc).__name__}: {exc}",
                           "secs": round(time.time() - t0, 2)}
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                won = rec.get("winner") == fac
                print(f"[{label:>14s} seed={seed:2d}] winner={rec.get('winner')}"
                      f" {'WIN' if won else ''} {rec.get('error', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
