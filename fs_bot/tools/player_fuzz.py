"""Player-action fuzzer — random-legal players in random seats vs the NP bots.

The error census exercises only BOT decisions. This tool fuzzes the
human-facing surface: each game seats a random subset of factions as
"players" driven by RandomPlanPolicy (random command, random regions,
pre-validated via moves.validate_player_action) with fully randomized
reactive decisions (Retreat, Loss order, Agreements) through the
decision-agent hook. Seated factions are removed from
state["non_player_factions"], so player-vs-NP code paths (e.g. the Aedui
Trade Roman-agreement consult, German player-target priorities, the Quarters
roll-all default for a player Rome) are genuinely exercised.

Oracles, per game:
  crash          — run_game raised. Hard defect.
  structural     — check_structural_integrity violation at any turn boundary
                   or at game end (silent-corruption class). Hard defect.
  divergence     — a seated player's chosen plan was dry-run at decision
                   time (moves.validate_player_action) and the LIVE execution
                   produced a different outcome signature (executed flag,
                   error set, SA outcome). Dry-run and live see the same
                   state and rng, so any divergence means hidden global
                   state or set-iteration nondeterminism. Hard defect.
                   (Sub-action errors present in BOTH dry-run and live are
                   the random policy's own sloppiness — partial-execution
                   semantics, reported as the soft "partial" count.)
                   The dry-run installs a CLONE of the reactive agent with a
                   cloned rng state — moves.validate_player_action's own
                   agent-stripped dry-run would legitimately diverge wherever
                   resolution consults an agreement (e.g. Recruit supply-line
                   cost, Harassment), which is table-accurate behaviour, not
                   a defect.
  nondeterminism — the same (scenario, seed) replayed from scratch produced a
                   different end digest. Hard defect (CLAUDE.md determinism).

All seat/reactive randomness derives from random.Random(str) (sha512-based),
so results are reproducible across processes and PYTHONHASHSEED values; the
printed batch digest must be identical across hashseeds.

Not yet fuzzed here: player EVENT execution (RandomPlanPolicy builds Command
plans only; card-specific event params need a per-card param fuzzer).

    python -m fs_bot.tools.player_fuzz --seeds 1-20
    python -m fs_bot.tools.player_fuzz --seeds 1-20 --scenario "The Great Revolt"
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import io
import json
import random
from collections import Counter

import fs_bot.rules_consts as rc
from fs_bot.state.setup import setup_scenario
from fs_bot.engine.game_engine import run_game, ACTION_EVENT, get_sop_factions
from fs_bot.engine.agent import RETREAT, LOSS_ORDER, AGREEMENT
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.cli.dispatcher import _translate_bot_action
from fs_bot.agents.heuristic import RandomPlanPolicy
from fs_bot.state.state_schema import check_structural_integrity

ALL_SCENARIOS = (rc.SCENARIO_PAX_GALLICA, rc.SCENARIO_GREAT_REVOLT,
                 rc.SCENARIO_RECONQUEST, rc.SCENARIO_ARIOVISTUS,
                 rc.SCENARIO_GALLIC_WAR)


def _pick_seats(factions, rng):
    """Random non-empty subset of ``factions`` (order-stable draw)."""
    seats = [f for f in factions if rng.random() < 0.5]
    if not seats:
        seats = [factions[rng.randrange(len(factions))]]
    return seats


def make_random_reactive(seats, rng):
    """Randomized reactive decisions for the seated factions.

    RETREAT: uniformly no-retreat or one of the legal regions.
    LOSS_ORDER: a random permutation; 25% of the time a random truncation
        (exercises the engine's fill-in default for unlisted pieces).
    AGREEMENT: coin flip (exercises both branches of every negotiation).
    """
    seatset = set(seats)

    def reactive(state, faction, request):
        if faction not in seatset:
            return None
        kind = request.get("kind")
        if kind == RETREAT:
            legal = list(request.get("legal_regions") or [])
            choices = [None] + legal
            pick = choices[rng.randrange(len(choices))]
            return {"retreat": pick is not None, "region": pick}
        if kind == LOSS_ORDER:
            pieces = list(request.get("pieces") or [])
            rng.shuffle(pieces)
            if pieces and rng.random() < 0.25:
                pieces = pieces[:rng.randrange(1, len(pieces) + 1)]
            return pieces
        if kind == AGREEMENT:
            return rng.random() < 0.5
        return None

    return reactive


def _sanitize(obj):
    """Recursively convert state into JSON-stable primitives (sets sorted,
    unknown leaves stringified) for digesting."""
    if isinstance(obj, dict):
        return {str(k): _sanitize(v) for k, v in sorted(
            obj.items(), key=lambda kv: str(kv[0]))}
    if isinstance(obj, (set, frozenset)):
        return sorted(str(x) for x in obj)
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    return f"<{type(obj).__name__}>"


def _digest(state, res):
    """Order-independent digest of the end position + game trajectory."""
    body = {
        "spaces": _sanitize(state.get("spaces")),
        "tribes": _sanitize(state.get("tribes")),
        "resources": _sanitize(state.get("resources")),
        "markers": _sanitize(state.get("markers")),
        "cards": None if res is None else res.get("total_cards_played"),
        "winters": None if res is None else res.get("winter_count"),
    }
    if res is not None:
        for cr in res.get("card_results", ()):
            if cr.get("winner"):
                body["winner"] = cr["winner"]
    blob = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _sig(ex):
    """Outcome signature of an execution result: executed flag, sorted
    error strings, and the SA execution's flag + errors."""
    if not isinstance(ex, dict):
        return None
    sa = ex.get("sa_execution")
    return (bool(ex.get("executed")),
            tuple(sorted(str(e) for e in ex.get("errors") or [])),
            None if not isinstance(sa, dict) else
            (bool(sa.get("executed")),
             tuple(sorted(str(e) for e in sa.get("errors") or []))))


def _compare_dry_vs_live(res, seats, expected):
    """Divergences ((faction, card, message)) and the soft partial count."""
    divergences, partial = [], 0
    if res is None:
        return divergences, partial
    seatset = set(seats)
    for cr in res.get("card_results", ()):
        tr = cr.get("turn_result") or {}
        for faction, rec in (tr.get("actions_taken") or {}).items():
            if faction not in seatset:
                continue
            key = (cr.get("card"), faction)
            if key not in expected:
                continue
            live = _sig(rec.get("execution"))
            if live is None:
                continue
            want = expected[key]
            if live != want:
                divergences.append(
                    (faction, cr.get("card"),
                     f"dry-run {want} != live {live}"))
            elif want[1] or (want[2] and want[2][1]):
                partial += 1
    return divergences, partial


def play_game(scenario, seed, *, reactive=True):
    """One fuzzed game. Returns a result dict incl. findings and digest."""
    st = setup_scenario(scenario, seed=seed)
    sop = sorted(get_sop_factions(st))
    frng = random.Random(f"player_fuzz|{scenario}|{seed}")
    seats = _pick_seats(sop, frng)
    st["non_player_factions"] = set(sop) - set(seats)
    if reactive:
        st["decision_agent"] = make_random_reactive(seats, frng)
    policies = {f: RandomPlanPolicy(f, seed=seed * 1000 + i)
                for i, f in enumerate(seats)}

    findings = []
    human_turns = [0]
    expected = {}   # (card, faction) -> dry-run outcome signature

    def decision_func(state, faction, options, position):
        for e in check_structural_integrity(state)[:3]:
            findings.append(("structural", state.get("current_card"), e))
        if faction in policies:
            human_turns[0] += 1
            dec = policies[faction].plan_turn(
                state, faction, options, position)
            pa = (dec or {}).get("player_action")
            if pa is not None:
                # Dry-run under IDENTICAL reactive decisions: clone the
                # fuzz rng so the sim's agent answers exactly as the live
                # agent is about to.
                from fs_bot.engine.execute import execute_decision
                sim = copy.deepcopy(state)
                sim.pop("decision_agent", None)
                if reactive:
                    clone_rng = random.Random()
                    clone_rng.setstate(frng.getstate())
                    sim["decision_agent"] = make_random_reactive(
                        seats, clone_rng)
                try:
                    info = execute_decision(
                        sim, faction, {"player_action": pa})
                except Exception as exc:
                    info = {"executed": False, "errors": [repr(exc)]}
                expected[(state.get("current_card"), faction)] = _sig(info)
            return dec
        state["current_card_id"] = state.get("current_card")
        state["is_second_eligible"] = (position == "2nd_eligible")
        state["can_play_event"] = (ACTION_EVENT in options)
        ba = dispatch_bot_turn(state, faction)
        return {"action": _translate_bot_action(ba, options),
                "bot_action": ba}

    res, crash = None, None
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            res = run_game(st, decision_func=decision_func, execute=True)
        except Exception as exc:
            crash = f"{type(exc).__name__}: {exc}"
    if crash:
        findings.append(("crash", st.get("current_card"), crash))
    for e in check_structural_integrity(st)[:3]:
        findings.append(("structural", "end", e))
    divergences, partial = _compare_dry_vs_live(res, seats, expected)
    for f, card, msg in divergences:
        findings.append(("divergence", card, f"{f}: {msg}"))

    return {"scenario": scenario, "seed": seed, "seats": seats,
            "human_turns": human_turns[0], "findings": findings,
            "partial": partial, "digest": _digest(st, res)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default=None,
                    help="single scenario (default: all five)")
    ap.add_argument("--seeds", default="1-10")
    ap.add_argument("--no-reactive", action="store_true",
                    help="skip the randomized reactive decision agent")
    ap.add_argument("--no-determinism", action="store_true",
                    help="skip the replay determinism double-run")
    args = ap.parse_args(argv)

    lo, _, hi = args.seeds.partition("-")
    seeds = range(int(lo), int(hi or lo) + 1)
    scenarios = (args.scenario,) if args.scenario else ALL_SCENARIOS

    games, turns, partial = 0, 0, 0
    by_kind = Counter()
    examples = []
    batch = hashlib.sha256()
    for sc in scenarios:
        for seed in seeds:
            r = play_game(sc, seed, reactive=not args.no_reactive)
            games += 1
            turns += r["human_turns"]
            partial += r["partial"]
            if not args.no_determinism:
                r2 = play_game(sc, seed, reactive=not args.no_reactive)
                if r2["digest"] != r["digest"]:
                    r["findings"].append(
                        ("nondeterminism", "-",
                         f"replay digest {r['digest']} != {r2['digest']}"))
            for kind, card, msg in r["findings"]:
                by_kind[kind] += 1
                if len(examples) < 40:
                    examples.append((sc, seed, r["seats"], kind, card, msg))
            batch.update(f"{sc}|{seed}|{r['digest']}".encode())

    hard = sum(by_kind.values())
    print(f"games={games}  human-turns={turns}  hard-findings={hard}  "
          f"(soft: partial={partial})")
    print("findings: " + ("  ".join(
        f"{k}={n}" for k, n in sorted(by_kind.items())) or "none"))
    print(f"batch-digest={batch.hexdigest()[:16]}  "
          f"(must match across PYTHONHASHSEED values)")
    for sc, seed, seats, kind, card, msg in examples:
        print(f"  [{kind}] {sc} seed={seed} seats={','.join(seats)} "
              f"card={card}: {str(msg)[:140]}")
    return min(hard, 250)


if __name__ == "__main__":
    raise SystemExit(main())
