"""Play-quality telemetry — is a rules-legal bot behaving sensibly?

The error census guarantees legality; this instrument measures BEHAVIOUR
across bot-only games and flags patterns that suggest a malfunctioning
(flowchart-unfaithful or degenerate) bot rather than the published design:

  - command/SA usage mix per faction (a subsystem never used, e.g. a
    faction that never Trades/Devastates/Ambushes, is a smell)
  - no-effect commands (the bot chose a Command that then did nothing —
    the flowchart's IF-NONE should usually have routed elsewhere)
  - pass rates and event play/decline rates
  - resource dynamics: turns spent at 0 and at MAX_RESOURCES (income
    wasted at the cap)
  - win distribution and game lengths per scenario

Nothing here tunes the bots; every flag is a pointer back to the §8.x
flowchart text for a fidelity check.

    python -m fs_bot.tools.play_quality --seeds 1-20
    python -m fs_bot.tools.play_quality --seeds 1-20 --scenario "Pax Gallica?"
"""
from __future__ import annotations

import argparse
import contextlib
import io
from collections import Counter, defaultdict

import fs_bot.rules_consts as rc
from fs_bot.state.setup import setup_scenario
from fs_bot.engine.game_engine import run_game, ACTION_EVENT, get_sop_factions
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.cli.dispatcher import _translate_bot_action

ALL_SCENARIOS = (rc.SCENARIO_PAX_GALLICA, rc.SCENARIO_GREAT_REVOLT,
                 rc.SCENARIO_RECONQUEST, rc.SCENARIO_ARIOVISTUS,
                 rc.SCENARIO_GALLIC_WAR)


def play_game(scenario, seed, stats):
    st = setup_scenario(scenario, seed=seed)
    st["non_player_factions"] = set(get_sop_factions(st))
    sc = stats[scenario]

    def decision_func(state, faction, options, position):
        state["current_card_id"] = state.get("current_card")
        state["is_second_eligible"] = (position == "2nd_eligible")
        state["can_play_event"] = (ACTION_EVENT in options)
        ba = dispatch_bot_turn(state, faction)
        cmd = ba.get("command") or "None"
        sa = ba.get("sa") or "No SA"
        sc["commands"][(faction, cmd)] += 1
        if sa != "No SA":
            sc["sas"][(faction, sa)] += 1
        if cmd == "Event":
            sc["events_played"][faction] += 1
        elif state.get("can_play_event"):
            sc["events_declined"][faction] += 1
        res = state["resources"].get(faction)
        if res is not None:
            sc["res_turns"][faction] += 1
            if res == 0:
                sc["res_zero"][faction] += 1
            if res >= rc.MAX_RESOURCES:
                sc["res_cap"][faction] += 1
        return {"action": _translate_bot_action(ba, options),
                "bot_action": ba}

    with contextlib.redirect_stdout(io.StringIO()):
        res = run_game(st, decision_func=decision_func, execute=True)

    winner = None
    for cr in res["card_results"]:
        if cr.get("winner"):
            winner = cr["winner"]
        tr = cr.get("turn_result") or {}
        for faction, rec in (tr.get("actions_taken") or {}).items():
            ex = rec.get("execution")
            if not isinstance(ex, dict):
                continue
            cmd = (rec.get("bot_action") or {}).get("command")
            sx = ex.get("sa_execution")
            sa_did = isinstance(sx, dict) and sx.get("executed")
            # A no-effect TURN: the Command did nothing AND no SA salvaged
            # it (e.g. the German A8.7.4 Settle riding an empty Rally is
            # fine — the turn accomplished its purpose).
            if (ex.get("executed") is False and not sa_did
                    and cmd not in ("Event", None, "Pass")):
                sc["no_effect"][(faction, cmd)] += 1
        for f in (tr.get("passes") or []):
            sc["passes"][f] += 1
    sc["wins"][winner or "none"] += 1
    sc["games"] += 1
    sc["cards"].append(res["total_cards_played"])
    return res


def _new_scenario_stats():
    return {"commands": Counter(), "sas": Counter(), "no_effect": Counter(),
            "passes": Counter(), "events_played": Counter(),
            "events_declined": Counter(), "res_zero": Counter(),
            "res_cap": Counter(), "res_turns": Counter(),
            "wins": Counter(), "games": 0, "cards": []}


def report(stats):
    for scenario, sc in stats.items():
        if not sc["games"]:
            continue
        n = sc["games"]
        cards = sc["cards"]
        print(f"\n=== {scenario} ({n} games; cards/game "
              f"min={min(cards)} avg={sum(cards)/len(cards):.0f} "
              f"max={max(cards)}) ===")
        print("wins: " + "  ".join(
            f"{f}={w}" for f, w in sc["wins"].most_common()))
        factions = sorted({f for f, _ in sc["commands"]})
        for f in factions:
            cmds = {c: v for (ff, c), v in sc["commands"].items() if ff == f}
            total = sum(cmds.values())
            sas = {a: v for (ff, a), v in sc["sas"].items() if ff == f}
            noeff = {c: v for (ff, c), v in sc["no_effect"].items()
                     if ff == f}
            zero = sc["res_zero"][f]
            cap = sc["res_cap"][f]
            rt = sc["res_turns"][f] or 1
            print(f"  {f:8s} turns={total:4d} "
                  f"pass={sc['passes'][f]:3d} "
                  f"ev={sc['events_played'][f]:3d}/"
                  f"{sc['events_played'][f] + sc['events_declined'][f]:3d} "
                  f"res0={100 * zero // rt:2d}% cap={100 * cap // rt:2d}%")
            print("           cmds: " + "  ".join(
                f"{c}={v}" for c, v in sorted(cmds.items(),
                                              key=lambda kv: -kv[1])))
            if sas:
                print("           sas:  " + "  ".join(
                    f"{a}={v}" for a, v in sorted(sas.items(),
                                                  key=lambda kv: -kv[1])))
            if noeff:
                print("           NO-EFFECT: " + "  ".join(
                    f"{c}={v}" for c, v in sorted(noeff.items(),
                                                  key=lambda kv: -kv[1])))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default=None)
    ap.add_argument("--seeds", default="1-10")
    args = ap.parse_args(argv)
    lo, _, hi = args.seeds.partition("-")
    seeds = range(int(lo), int(hi or lo) + 1)
    scenarios = (args.scenario,) if args.scenario else ALL_SCENARIOS

    stats = defaultdict(_new_scenario_stats)
    for sc in scenarios:
        for seed in seeds:
            play_game(sc, seed, stats)
    report(stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
