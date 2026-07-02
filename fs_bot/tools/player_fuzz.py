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

Player EVENT fuzzing: seated players also play Events (~50% of turns where
the SoP allows) with fuzzed ``event_params``: NP-derived (well-formed),
mutated-derived, or generated from scratch against the param-key inventory
harvested from card_effects.py source. Every generated param set is dry-run
in an isolated sim first with two extra oracles:
  event-crash — the handler raised outside the _EVENT_SAFE_ERRORS contract
                ("report, do not crash"). Hard defect.
  dirty-event — the handler reported not-applicable (executed=False) but
                MUTATED the board (half-applied event). Hard defect: the
                report-don't-crash contract requires validate-before-mutate.
Dud param sets (dry-run not-applicable) are still submitted live ~30% of
the time to fuzz the live not-applicable path; otherwise the policy falls
back to a random Command.

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

import re

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
    """Outcome signature of an execution result: executed flag, refusal
    reason, sorted error strings, and the SA execution's flag + errors."""
    if not isinstance(ex, dict):
        return None
    sa = ex.get("sa_execution")
    return (bool(ex.get("executed")),
            str(ex.get("reason") or ""),
            tuple(sorted(str(e) for e in ex.get("errors") or [])),
            None if not isinstance(sa, dict) else
            (bool(sa.get("executed")),
             tuple(sorted(str(e) for e in sa.get("errors") or []))))


# --------------------------------------------------------------------- #
# Event-param fuzzing
# --------------------------------------------------------------------- #

_PARAM_KEY_RE = re.compile(r'params\.get\("([a-z_0-9]+)"')


def _param_key_pool():
    """Harvest the event-param key inventory from card_effects.py source,
    so the from-scratch generator tracks new cards automatically."""
    import inspect
    import fs_bot.cards.card_effects as ce
    try:
        keys = sorted(set(_PARAM_KEY_RE.findall(inspect.getsource(ce))))
    except Exception:
        keys = []
    return keys or ["region", "target_region", "placements", "removals"]


def _value_pools(state):
    """(regions, factions, tribes) value pools for param generation."""
    return (sorted(state.get("spaces") or ()),
            sorted(rc.FACTIONS),
            sorted(state.get("tribes") or ()))


_PIECE_TYPES = (rc.WARBAND, rc.AUXILIA, rc.LEGION, rc.ALLY, rc.CITADEL,
                rc.FORT)


def _rand_value(key, pools, rng):
    """A random value plausibly typed for ``key`` (by name heuristics)."""
    regions, factions, tribes = pools

    def region():
        return regions[rng.randrange(len(regions))]

    def faction():
        return factions[rng.randrange(len(factions))]

    def tribe():
        return tribes[rng.randrange(len(tribes))]

    k = key.lower()
    if "direction" in k:
        return (rc.SENATE_UP if rng.random() < 0.5 else rc.SENATE_DOWN)
    if "factions" in k:
        return [faction() for _ in range(rng.randrange(1, 3))]
    if "faction" in k:
        return faction()
    if "tribe" in k or "city" in k or "colony" in k:
        return tribe()
    if "piece_type" in k or "place_type" in k:
        return _PIECE_TYPES[rng.randrange(len(_PIECE_TYPES))]
    if ("count" in k or "to_remove" in k or k.startswith("legions_")
            or "from_track" in k or "from_fallen" in k):
        return rng.randrange(0, 5)
    if k.endswith("s") and ("placement" in k or "removal" in k
                            or "replacement" in k or "move" in k
                            or "upgrade" in k):
        return [{"region": region(), "faction": faction(),
                 "piece_type": _PIECE_TYPES[rng.randrange(len(_PIECE_TYPES))],
                 "count": rng.randrange(1, 3), "tribe": tribe()}
                for _ in range(rng.randrange(1, 3))]
    if "regions" in k:
        return [region() for _ in range(rng.randrange(1, 4))]
    return region()


def _scratch_params(key_pool, pools, rng):
    """1-4 random keys with random typed values."""
    n = rng.randrange(1, 5)
    keys = list(key_pool)
    out = {}
    for _ in range(n):
        k = keys[rng.randrange(len(keys))]
        out[k] = _rand_value(k, pools, rng)
    return out


def _mutate_params(params, key_pool, pools, rng):
    """Drop / retype / extend keys of a derived param dict."""
    out = dict(params)
    for k in list(out):
        r = rng.random()
        if r < 0.25:
            out.pop(k)
        elif r < 0.5:
            out[k] = _rand_value(k, pools, rng)
    if rng.random() < 0.25 and key_pool:
        k = key_pool[rng.randrange(len(key_pool))]
        out[k] = _rand_value(k, pools, rng)
    return out


_BOARD_KEYS = ("spaces", "tribes", "resources", "markers", "available",
               "capabilities", "eligibility", "fallen_legions",
               "legions_track", "removed_legions", "removed_pieces",
               "senate", "at_war", "diviciacus_in_play",
               "winter_track_legions", "spring_box_leaders",
               "event_modifiers")


def _board_digest(state):
    """Digest of the persistent board (dirty-failure oracle)."""
    body = {k: _sanitize(state.get(k)) for k in _BOARD_KEYS}
    blob = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _build_event_action(state, faction, frng, key_pool):
    """A fuzzed Event player_action for the current card."""
    from fs_bot.engine.execute import _derive_event_params
    card = state.get("current_card")
    shaded = frng.random() < 0.5
    pools = _value_pools(state)
    mode = frng.random()
    derived = None
    try:
        derived = _derive_event_params(state, faction, card, shaded)
    except Exception:
        derived = None
    if derived is not None and mode < 0.4:
        params = dict(derived)
    elif derived is not None and mode < 0.75:
        params = _mutate_params(derived, key_pool, pools, frng)
    else:
        params = _scratch_params(key_pool, pools, frng)
    return {"command": "Event", "regions": [], "sa": "No SA",
            "sa_regions": [],
            "details": {"card_id": card,
                        "text_preference": (rc.EVENT_SHADED if shaded
                                            else rc.EVENT_UNSHADED),
                        "event_params": params}}


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
            elif want[2] or (want[3] and want[3][1]):
                partial += 1
    return divergences, partial


def play_game(scenario, seed, *, reactive=True, events=True):
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
    key_pool = _param_key_pool() if events else []

    findings = []
    human_turns = [0]
    event_turns = [0]
    expected = {}   # (card, faction) -> dry-run outcome signature

    def _dry_run(state, faction, pa):
        """Execute ``pa`` on an isolated sim under IDENTICAL reactive
        decisions (cloned fuzz rng). Returns (info, dirty) where dirty is
        True when a FAILED action mutated the persistent board."""
        from fs_bot.engine.execute import execute_decision
        sim = copy.deepcopy(state)
        sim.pop("decision_agent", None)
        if reactive:
            clone_rng = random.Random()
            clone_rng.setstate(frng.getstate())
            sim["decision_agent"] = make_random_reactive(seats, clone_rng)
        pre = _board_digest(sim)
        try:
            info = execute_decision(sim, faction, {"player_action": pa})
        except Exception as exc:
            findings.append(("event-crash" if pa.get("command") == "Event"
                             else "crash",
                             state.get("current_card"), repr(exc)))
            return None, False
        dirty = (not info.get("executed")) and _board_digest(sim) != pre
        return info, dirty

    def decision_func(state, faction, options, position):
        for e in check_structural_integrity(state)[:3]:
            findings.append(("structural", state.get("current_card"), e))
        if faction in policies:
            human_turns[0] += 1
            dec = None
            if events and ACTION_EVENT in options and frng.random() < 0.5:
                pa = _build_event_action(state, faction, frng, key_pool)
                info, dirty = _dry_run(state, faction, pa)
                if dirty:
                    findings.append(
                        ("dirty-event", state.get("current_card"),
                         f"{faction} failed Event mutated the board: "
                         f"params={pa['details']['event_params']}"))
                if info is not None and (info.get("executed")
                                         or frng.random() < 0.3):
                    expected[(state.get("current_card"), faction)] =                         _sig(info)
                    event_turns[0] += 1
                    dec = {"action": ACTION_EVENT, "player_action": pa}
            if dec is None:
                dec = policies[faction].plan_turn(
                    state, faction, options, position)
                pa = (dec or {}).get("player_action")
                if pa is not None:
                    info, dirty = _dry_run(state, faction, pa)
                    if dirty:
                        findings.append(
                            ("dirty-command", state.get("current_card"),
                             f"{faction} failed Command mutated the board"))
                    if info is not None:
                        expected[(state.get("current_card"), faction)] =                             _sig(info)
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
            "human_turns": human_turns[0], "event_turns": event_turns[0],
            "findings": findings, "partial": partial,
            "digest": _digest(st, res)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default=None,
                    help="single scenario (default: all five)")
    ap.add_argument("--seeds", default="1-10")
    ap.add_argument("--no-reactive", action="store_true",
                    help="skip the randomized reactive decision agent")
    ap.add_argument("--no-events", action="store_true",
                    help="skip player Event fuzzing")
    ap.add_argument("--no-determinism", action="store_true",
                    help="skip the replay determinism double-run")
    args = ap.parse_args(argv)

    lo, _, hi = args.seeds.partition("-")
    seeds = range(int(lo), int(hi or lo) + 1)
    scenarios = (args.scenario,) if args.scenario else ALL_SCENARIOS

    games, turns, ev_turns, partial = 0, 0, 0, 0
    by_kind = Counter()
    examples = []
    batch = hashlib.sha256()
    for sc in scenarios:
        for seed in seeds:
            r = play_game(sc, seed, reactive=not args.no_reactive,
                          events=not args.no_events)
            games += 1
            turns += r["human_turns"]
            ev_turns += r["event_turns"]
            partial += r["partial"]
            if not args.no_determinism:
                r2 = play_game(sc, seed, reactive=not args.no_reactive,
                               events=not args.no_events)
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
    print(f"games={games}  human-turns={turns}  event-turns={ev_turns}  "
          f"hard-findings={hard}  (soft: partial={partial})")
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
