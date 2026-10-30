"""Reproducible experiments with a heuristic human seat against the NP bots.

Successful records resume only under the same source, Python, edition and
policy identity. Failed attempts remain in the log and are retried; any new
unsuccessful attempt makes the command exit nonzero. Historical unversioned
logs are read-only evidence: choose a new output path for a new experiment.

    python -m fs_bot.tools.heuristic_selfplay --scenario "Ariovistus" \
        --profiles G-GROW,BOTS --seeds 1-20 --out results.jsonl
"""
from __future__ import annotations

import argparse
from collections import Counter
import contextlib
import hashlib
import io
import json
import platform
import time
from pathlib import Path

import fs_bot.rules_consts as rc
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import validate_state, check_structural_integrity
from fs_bot.state.serialize import encode
from fs_bot.engine.game_engine import start_game, play_card, ACTION_EVENT, get_sop_factions
from fs_bot.engine.victory import determine_final_ranking, check_victory
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.cli.dispatcher import _translate_bot_action
from fs_bot.cards.edition import CARD_EDITIONS
from fs_bot.agents.heuristic import PROFILES, plan_turn, make_reactive, RandomPlanPolicy
from fs_bot.tools.error_census import census_result, _severity
from fs_bot.tools.validation_metadata import parse_seed_range, source_identity

RECORD_VERSION = 2
POLICY_VERSION = 3
REACTIVE_POLICY = "retreat-first-region; refuse-agreements; engine-default-other"


def _active_seat(state, initial):
    if initial == rc.GERMANS and state.get("interlude_completed"):
        return rc.ARVERNI
    return initial


def play_game(scenario, seed, agent_faction=None, planner=None, *,
              card_edition="legacy"):
    """Play and audit one experiment; completed means it passed the audit.

    Only the policy seat is human. Reactive choices not implemented by the
    heuristic explicitly defer to the raw callback defaults, with counts
    recorded separately. This is not a model of expert human play.
    """
    humans = () if agent_faction is None else (agent_faction,)
    st = setup_scenario(scenario, seed=seed, card_edition=card_edition,
                        human_factions=humans)
    seats = set(get_sop_factions(st))
    if agent_faction is not None and agent_faction not in seats:
        raise ValueError(f"{agent_faction!r} is not a playable seat in {scenario}")
    if agent_faction is not None and not callable(planner):
        raise ValueError("A policy seat requires a callable planner")
    st["non_player_factions"] = seats - {agent_faction}
    decisions, reactions, faults = Counter(), Counter(), set()

    def reactive(state, faction, request):
        active = _active_seat(state, agent_faction)
        if faction != active:
            return None
        response = make_reactive(active)(state, faction, request)
        # Previews are speculative; count only decisions on the actual board.
        if state is st:
            reactions[(faction, request["kind"],
                       "default" if response is None else "policy")] += 1
        return response

    if agent_faction is not None:
        st["decision_agent"] = reactive

    def inspect():
        faults.update(validate_state(st))
        faults.update(check_structural_integrity(st))
        faults.update(f"{f} Resources exceed cap: {n}"
                      for f, n in st["resources"].items() if n > rc.MAX_RESOURCES)

    def decision_func(state, faction, options, position):
        inspect()
        if agent_faction is not None and faction == _active_seat(state, agent_faction):
            if faction in state["non_player_factions"]:
                raise RuntimeError("Policy seat unexpectedly became non-player")
            decisions[faction] += 1
            return planner(state, faction, options, position)
        state["current_card_id"] = state.get("current_card")
        state["is_second_eligible"] = position == "2nd_eligible"
        state["can_play_event"] = ACTION_EVENT in options
        ba = dispatch_bot_turn(state, faction)
        return {"action": _translate_bot_action(ba, options), "bot_action": ba}

    cards = []
    with contextlib.redirect_stdout(io.StringIO()):
        inspect()
        start_game(st)
        while st["current_card"] is not None:
            if len(cards) >= 200:
                raise RuntimeError("Study safety limit of 200 resolved cards exceeded")
            card = play_card(st, decision_func, execute=True)
            cards.append(card)
            inspect()
            if card.get("game_over"):
                break

    last = cards[-1] if cards else {}
    ranking = determine_final_ranking(st)
    if len(ranking) != 4 or len({f for f, _ in ranking}) != 4:
        faults.add("Final ranking does not contain four distinct factions")
    for faction, margin in ranking:
        if (margin > 0) != check_victory(st, faction):
            faults.add(f"{faction} margin/threshold mismatch")
    winner = last.get("winner")
    if winner not in {f for f, _ in ranking}:
        faults.add("Missing or ineligible winner")
    if agent_faction is not None and not decisions:
        faults.add("Policy seat made no turn decisions")

    counts, examples = Counter(), {}
    census_result({"card_results": cards}, counts, examples, scenario, seed)
    diagnostics = [dict(faction=k[0], command=k[1], kind=k[2], message=k[3],
                        severity=_severity(k[2], k[3]), count=n)
                   for k, n in counts.items()]
    nonlegal = [d for d in diagnostics if d["severity"] != "legal-decline"]
    snapshot = encode({k: v for k, v in st.items() if k != "decision_agent"})
    game_completed = bool(last.get("game_over") and winner)
    return {
        "winner": winner, "cards": len(cards), "winters": st["winter_count"],
        "decisions": sum(decisions.values()), "decisions_by_faction": dict(decisions),
        "ranking": ranking, "game_completed": game_completed,
        "completed": game_completed and not faults and not nonlegal,
        "integrity_findings": sorted(faults), "diagnostics": diagnostics,
        "ending_scenario": st["scenario"],
        "interlude_completed": bool(st.get("interlude_completed")),
        "ending_agent_faction": _active_seat(st, agent_faction),
        "reactive_decisions": [dict(faction=f, kind=k, response=r, count=n)
                               for (f, k, r), n in sorted(reactions.items())],
        "final_state_sha256": hashlib.sha256(
            json.dumps(snapshot, sort_keys=True).encode()).hexdigest(),
    }


def _faction(label):
    if not isinstance(label, str):
        raise ValueError("Profile label must be a string")
    if label == "BOTS":
        return None
    if label.startswith("RANDOM:"):
        faction = label.removeprefix("RANDOM:")
        if faction not in rc.FACTIONS:
            raise ValueError(f"Unknown faction in profile {label!r}")
        return faction
    if label not in PROFILES:
        raise ValueError(f"Unknown profile {label!r}")
    return PROFILES[label]["faction"]


def _make(label, seed):
    faction = _faction(label)
    if faction is None:
        return None, None
    if label.startswith("RANDOM:"):
        policy = RandomPlanPolicy(faction, seed=seed)
        return faction, policy.plan_turn
    profile = PROFILES[label]

    def planner(state, acting_faction, options, position):
        selected = profile
        if acting_faction != faction:
            target = profile.get("interlude_profile")
            if faction != rc.GERMANS or acting_faction != rc.ARVERNI or target is None:
                raise ValueError(f"{label} has no policy for {acting_faction}")
            selected = PROFILES[target]
        custom = selected.get("planner")
        return (custom(state, acting_faction, options, position) if custom else
                plan_turn(state, acting_faction, selected, options, position))

    return faction, planner


def _labels(scenario, requested):
    seats = set(get_sop_factions({"scenario": scenario}))
    if requested is None:
        labels = [name for name, profile in PROFILES.items() if profile["faction"] in seats]
        labels += [f"RANDOM:{f}" for f in rc.FACTIONS if f in seats] + ["BOTS"]
    else:
        labels = [label.strip() for label in requested.split(",") if label.strip()]
        if not labels:
            raise ValueError("At least one profile is required")
    for label in labels:
        faction = _faction(label)
        if faction is not None and faction not in seats:
            raise ValueError(f"Profile {label!r} has no playable seat in {scenario}")
    return list(dict.fromkeys(labels))


def _identity(scenario, card_edition):
    return dict(record_version=RECORD_VERSION, policy_version=POLICY_VERSION,
                source=source_identity(), python=platform.python_version(),
                scenario=scenario, card_edition=card_edition,
                seat_semantics="human-policy-seat", reactive_policy=REACTIVE_POLICY,
                interlude_profiles={name: p["interlude_profile"] for name, p in PROFILES.items()
                                    if "interlude_profile" in p})


def _successful(record):
    cards, decisions = record.get("cards"), record.get("decisions")
    diagnostics = record.get("diagnostics", [])
    ending = record.get("ending_scenario")
    if (type(cards) is not int or cards < 1
            or ending not in rc.ALL_SCENARIOS
            or not isinstance(diagnostics, list)
            or not all(isinstance(d, dict) for d in diagnostics)):
        return False
    return (record.get("completed") is True and record.get("game_completed") is True
            and record.get("winner") in get_sop_factions({"scenario": ending})
            and (record.get("faction") is None or
                 (type(decisions) is int and decisions > 0))
            and not record.get("error") and not record.get("errors")
            and not record.get("integrity_findings")
            and not any(d.get("severity") != "legal-decline"
                        for d in diagnostics))


def _same_experiment(left, right):
    """Dirty describes the checkout, not a different engine or policy.

    Creating an output manifest inside a clean checkout can itself make Git
    dirty. Keep that provenance, but compare the actual source bytes and
    commit along with every experimental setting when resuming.
    """
    def comparable(identity):
        if not isinstance(identity, dict) or not isinstance(identity.get("source"), dict):
            return None
        return {**identity, "source": {k: v for k, v in identity["source"].items()
                                       if k != "dirty"}}
    return comparable(left) is not None and comparable(left) == comparable(right)


def _resume(out, identity):
    manifest = out.with_name(out.name + ".manifest.json")
    if manifest.exists():
        if not _same_experiment(json.loads(manifest.read_text(encoding="utf-8")), identity):
            raise ValueError("Output belongs to a different source/policy/configuration; use a new --out path")
    elif out.exists() and out.stat().st_size:
        raise ValueError("Unversioned historical output cannot be resumed; use a new --out path")
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        with manifest.open("x", encoding="utf-8") as fh:
            json.dump(identity, fh, indent=2, sort_keys=True)
            fh.write("\n")
    done = set()
    if out.exists():
        for number, line in enumerate(out.read_text(encoding="utf-8").splitlines(), 1):
            try:
                record = json.loads(line)
                if not _same_experiment(record["identity"], identity):
                    raise ValueError("record identity differs from manifest")
                if (record["scenario"] != identity["scenario"]
                        or record["card_edition"] != identity["card_edition"]):
                    raise ValueError("record configuration differs from manifest")
                if _faction(record["label"]) != record["faction"]:
                    raise ValueError("record faction differs from its profile")
                _labels(record["scenario"], record["label"])
                if type(record["seed"]) is not int or record["seed"] < 0:
                    raise ValueError("record seed must be a nonnegative integer")
                key = (record["label"], record["scenario"], record["seed"])
            except (ValueError, KeyError, TypeError) as exc:
                raise ValueError(f"Invalid result at line {number}; preserve this log and use a new --out path: {exc}") from exc
            if _successful(record):
                done.add(key)
    return done


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scenario", choices=rc.ALL_SCENARIOS, default=rc.SCENARIO_GREAT_REVOLT)
    ap.add_argument("--seeds", type=parse_seed_range, default="1-20")
    ap.add_argument("--profiles", help="Comma list of profiles, RANDOM:FACTION, BOTS; defaults to playable profiles only")
    ap.add_argument("--card-edition", choices=CARD_EDITIONS, default="legacy")
    ap.add_argument("--out", type=Path, default=Path("selfplay_results.jsonl"))
    args = ap.parse_args(argv)
    try:
        labels = _labels(args.scenario, args.profiles)
        identity = _identity(args.scenario, args.card_edition)
        done = _resume(args.out, identity)
    except (ValueError, OSError) as exc:
        ap.error(str(exc))

    failures = 0
    with args.out.open("a", encoding="utf-8") as fh:
        for label in labels:
            for seed in args.seeds:
                if (label, args.scenario, seed) in done:
                    continue
                faction, planner = _make(label, seed)
                t0 = time.monotonic()
                record = dict(identity=identity, label=label, faction=faction,
                              scenario=args.scenario, seed=seed, card_edition=args.card_edition)
                try:
                    record.update(play_game(args.scenario, seed, faction, planner,
                                            card_edition=args.card_edition))
                except Exception as exc:
                    record.update(completed=False, winner=None,
                                  error=f"{type(exc).__name__}: {exc}")
                record["secs"] = round(time.monotonic() - t0, 2)
                success = _successful(record)
                failures += not success
                fh.write(json.dumps(record, sort_keys=True) + "\n")
                fh.flush()
                won = success and faction is not None and record["winner"] == record.get("ending_agent_faction")
                print(f"[{label:>14s} seed={seed:2d}] winner={record.get('winner')}"
                      f" {'WIN' if won else ''} {'OK' if success else 'FAILED'} {record.get('error', '')}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
