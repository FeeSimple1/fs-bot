"""All-bot sub-action error census.

Plays bot-only games across scenarios/seeds and aggregates every executor
rejection: plan components the executor legally refused (``errors`` lists),
Special Activities that executed with no effect, and Commands that produced
no legal effect. This is the acceptance instrument for the planner-quality
backlog in QUESTIONS.md ("OPEN — planner quality").

    python -m fs_bot.tools.error_census --seeds 1-10
    python -m fs_bot.tools.error_census --seeds 1-10 --scenario "The Great Revolt"
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
from collections import Counter

import fs_bot.rules_consts as rc
from fs_bot.state.setup import setup_scenario
from fs_bot.engine.game_engine import run_game, ACTION_EVENT, get_sop_factions
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.cli.dispatcher import _translate_bot_action

ALL_SCENARIOS = (rc.SCENARIO_PAX_GALLICA, rc.SCENARIO_GREAT_REVOLT,
                 rc.SCENARIO_RECONQUEST, rc.SCENARIO_ARIOVISTUS,
                 rc.SCENARIO_GALLIC_WAR)


def _norm(msg):
    """Collapse region/tribe/number specifics so identical defect classes
    aggregate together."""
    s = str(msg)
    s = re.sub(r"'[^']*'", "'*'", s)
    s = re.sub(r"\d+", "N", s)
    return s


def play_game(scenario, seed):
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
    return res


def census_result(res, counts, examples, scenario, seed):
    for cr in res["card_results"]:
        tr = cr.get("turn_result") or {}
        for faction, rec in (tr.get("actions_taken") or {}).items():
            ex = rec.get("execution")
            ba = rec.get("bot_action") or {}
            if not isinstance(ex, dict):
                continue
            _walk(ex, faction, ba.get("command"), ba.get("sa"),
                  counts, examples, scenario, seed, cr.get("card"))


def _walk(ex, faction, cmd, sa, counts, examples, scenario, seed, card):
    for e in ex.get("errors") or []:
        key = (faction, cmd, "command-error", _norm(e))
        counts[key] += 1
        examples.setdefault(key, (scenario, seed, card, str(e)))
    if ex.get("executed") is False and ex.get("reason"):
        key = (faction, cmd, "command-refused", _norm(ex["reason"]))
        counts[key] += 1
        examples.setdefault(key, (scenario, seed, card, str(ex["reason"])))
    if ex.get("sa_skipped"):
        key = (faction, cmd, "sa-skipped", _norm(ex["sa_skipped"]))
        counts[key] += 1
        examples.setdefault(key, (scenario, seed, card, str(ex["sa_skipped"])))
    sx = ex.get("sa_execution")
    if isinstance(sx, dict):
        for e in sx.get("errors") or []:
            key = (faction, f"{cmd}+{sa}", "sa-error", _norm(e))
            counts[key] += 1
            examples.setdefault(key, (scenario, seed, card, str(e)))
        if sx.get("executed") is False:
            why = sx.get("reason") or ("no effect" if not sx.get("actions")
                                       and not sx.get("regions") else "?")
            key = (faction, f"{cmd}+{sa}", "sa-no-effect", _norm(why))
            counts[key] += 1
            examples.setdefault(key, (scenario, seed, card, str(why)))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default=None,
                    help="single scenario (default: all five)")
    ap.add_argument("--seeds", default="1-10")
    ap.add_argument("--out", default=None, help="write JSON detail here")
    ap.add_argument("--top", type=int, default=60)
    args = ap.parse_args(argv)

    lo, _, hi = args.seeds.partition("-")
    seeds = range(int(lo), int(hi or lo) + 1)
    scenarios = (args.scenario,) if args.scenario else ALL_SCENARIOS

    counts = Counter()
    examples = {}
    games = 0
    for sc in scenarios:
        for seed in seeds:
            census_result(play_game(sc, seed), counts, examples, sc, seed)
            games += 1

    total = sum(counts.values())
    print(f"games={games}  total_incidents={total}")
    for key, n in counts.most_common(args.top):
        faction, cmd, kind, msg = key
        print(f"{n:6d}  {faction:8s} {cmd or '-':22s} {kind:15s} {msg}")
        sc, seed, card, raw = examples[key]
        print(f"        e.g. {sc} seed={seed} card={card}: {raw[:110]}")
    if args.out:
        with open(args.out, "w") as f:
            json.dump({"games": games, "total": total,
                       "counts": [{"faction": k[0], "command": k[1],
                                   "kind": k[2], "msg": k[3], "n": n}
                                  for k, n in counts.most_common()]}, f,
                      indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
