"""All-bot sub-action error census.

Plays bot-only games across scenarios/seeds and aggregates executor outcomes,
classified by SEVERITY so the headline reflects real defects, not the
flowchart legally declining:

  illegal           — the bot proposed a sub-action the executor must refuse
                      (command-error / sa-error). THE number to drive to zero.
  wasteful-sa       — an SA was attached but accomplished nothing
                      (sa-no-effect): play quality, no corruption.
  ineffective-event — the bot played an Event that did nothing
                      ("event not applicable"): play quality.
  legal-decline     — the published flowchart's own "If none ... no SA" /
                      IF-NONE fall-through (nothing marchable, command produced
                      no legal effect): NOT a defect.

This is the acceptance instrument for the planner-quality backlog in
QUESTIONS.md ("OPEN — planner quality").

    python -m fs_bot.tools.error_census --seeds 1-10
    python -m fs_bot.tools.error_census --seeds 1-10 --scenario "The Great Revolt"
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
from collections import Counter

import fs_bot.rules_consts as rc
from fs_bot.state.setup import setup_scenario
from fs_bot.engine.game_engine import run_game, ACTION_EVENT, get_sop_factions
from fs_bot.bots.bot_dispatch import dispatch_bot_turn
from fs_bot.cli.dispatcher import _translate_bot_action
from fs_bot.cards.edition import CARD_EDITIONS
from fs_bot.tools.validation_metadata import parse_seed_range, validation_metadata

ALL_SCENARIOS = (rc.SCENARIO_PAX_GALLICA, rc.SCENARIO_GREAT_REVOLT,
                 rc.SCENARIO_RECONQUEST, rc.SCENARIO_ARIOVISTUS,
                 rc.SCENARIO_GALLIC_WAR)


def _norm(msg):
    """Extract a cause without erasing quoted keys, messages, or numbers."""
    if isinstance(msg, dict):
        return str(msg.get("error", msg.get("reason", msg)))
    return str(msg)


def game_completion_error(result, ending_scenario):
    """Return why a claimed full game did not reach a valid terminal result.

    ``run_game.game_over`` alone is insufficient: it is also set when an
    empty or prematurely exhausted deck ends the loop.
    """
    if not isinstance(result, dict):
        return "Game result is not an object"
    cards = result.get("card_results")
    if not isinstance(cards, list) or not cards or not all(isinstance(c, dict) for c in cards):
        return "Game has no complete card-result sequence"
    if result.get("game_over") is not True or cards[-1].get("game_over") is not True:
        return "Game did not reach a terminal card"
    count = result.get("total_cards_played")
    if type(count) is not int or count != len(cards):
        return "Reported card count differs from resolved cards"
    if ending_scenario not in rc.ALL_SCENARIOS:
        return "Game has an unknown ending scenario"
    if cards[-1].get("winner") not in get_sop_factions({"scenario": ending_scenario}):
        return "Terminal card has no eligible winner"
    return None


def play_game(scenario, seed, *, card_edition="legacy"):
    st = setup_scenario(scenario, seed=seed, card_edition=card_edition)
    st["non_player_factions"] = set(get_sop_factions(st))

    def decision_func(state, faction, options, position):
        state["current_card_id"] = state.get("current_card")
        state["is_second_eligible"] = (position == "2nd_eligible")
        state["can_play_event"] = (ACTION_EVENT in options)
        ba = dispatch_bot_turn(state, faction)
        return {"action": _translate_bot_action(ba, options), "bot_action": ba}

    with contextlib.redirect_stdout(io.StringIO()):
        res = run_game(st, decision_func=decision_func, execute=True)
    if isinstance(res, dict):
        res["ending_scenario"] = st["scenario"]
    return res


def census_result(res, counts, examples, scenario, seed, occurrences=None):
    """Aggregate returned cards; optionally retain every raw diagnostic.

    Crashed cards that never returned are outside this function's coverage;
    the batch runner records that limitation and the crash separately.
    """
    for cr in res["card_results"]:
        tr = cr.get("turn_result") or {}
        for faction, rec in (tr.get("actions_taken") or {}).items():
            ex = rec.get("execution")
            ba = rec.get("bot_action") or {}
            if isinstance(ex, dict):
                _walk(ex, faction, ba.get("command"), ba.get("sa"),
                      counts, examples, scenario, seed, cr.get("card"), occurrences)
        phase = tr.get("arverni_phase")
        if isinstance(phase, dict):
            _walk(phase, rc.ARVERNI, "Arverni Phase", None,
                  counts, examples, scenario, seed, cr.get("card"), occurrences)
        winter = cr.get("winter_result")
        if isinstance(winter, dict):
            _walk(winter, "Winter", "Winter", None, counts, examples,
                  scenario, seed, cr.get("card"), occurrences)


_FREE_COMMAND_LABELS = {label.lower(): label for label in (
    rc.CMD_RECRUIT, rc.CMD_MARCH, rc.CMD_SEIZE, rc.CMD_BATTLE,
    rc.CMD_RALLY, rc.CMD_RAID)}
_FREE_SA_LABELS = {label.lower(): label for label in (
    rc.SA_BUILD, rc.SA_SCOUT, rc.SA_BESIEGE, rc.SA_ENTREAT, rc.SA_DEVASTATE,
    rc.SA_AMBUSH, rc.SA_TRADE, rc.SA_SUBORN, rc.SA_ENLIST, rc.SA_RAMPAGE,
    rc.SA_SETTLE, rc.SA_INTIMIDATE)}
_EXPLICIT_DECLINE_REASONS = frozenset((
    "free Command declined", "free Rally declined", "no March selected",
    "no Special Ability selected",
))


def _walk(ex, faction, cmd, sa, counts, examples, scenario, seed, card,
          occurrences=None, *, _is_sa=False, _seen=None):
    """Inspect every nested execution result, including Event-granted actions.

    Error payloads are recorded once, not recursively interpreted as another
    failed action. Split Commands expose an aggregate errors list as well as
    their actual portions; remove only that known duplication. Other refusals
    retain the existing severity policy, even when nested in a successful Event.
    """
    if _seen is None:
        _seen = set()
    if not isinstance(ex, dict) or id(ex) in _seen:
        return
    _seen.add(id(ex))
    faction = ex.get("faction") or ex.get("owner") or faction
    cmd = ex.get("command") or cmd
    sa = ex.get("sa") or sa
    free_kind = ex.get("free_action", "")
    if isinstance(free_kind, str):
        label = free_kind.removeprefix("free_")
        if label in _FREE_COMMAND_LABELS:
            cmd = _FREE_COMMAND_LABELS[label]
        elif label in _FREE_SA_LABELS:
            sa, _is_sa = _FREE_SA_LABELS[label], True
        elif free_kind == "free_sa":
            _is_sa = True
    command = f"{cmd}+{sa}" if _is_sa else cmd

    def record(kind, raw):
        message = _norm(raw)
        key = (faction, command, kind, message)
        counts[key] += 1
        examples.setdefault(key, (scenario, seed, card, str(raw)))
        if occurrences is not None:
            occurrences.append(dict(scenario=scenario, seed=seed, card=card,
                                    faction=faction, command=command, kind=kind,
                                    severity=_severity(kind, message),
                                    message=message, raw=raw))

    errors = list(ex.get("errors") or [])
    for part in ex.get("command_parts") or []:
        if isinstance(part, dict):
            for error in part.get("errors") or []:
                if error in errors:
                    errors.remove(error)
    for error in errors:
        record("sa-error" if _is_sa else "command-error", error)
    if ex.get("error"):
        record("sa-error" if _is_sa else "command-error", ex["error"])
    declined = (ex.get("decline") is True or ex.get("declined") is True
                or ex.get("declined_no_effect") is True
                or (isinstance(ex.get("reason"), str)
                    and ex["reason"] in _EXPLICIT_DECLINE_REASONS))
    if ex.get("executed") is False:
        if declined:
            record("action-declined", ex.get("reason") or "action declined")
        elif _is_sa:
            why = ex.get("reason") or ("no effect" if not ex.get("actions")
                                        and not ex.get("regions") else "?")
            record("sa-no-effect", why)
        elif ex.get("reason"):
            record("command-refused", ex["reason"])
    if ex.get("sa_skipped"):
        record("sa-skipped", ex["sa_skipped"])

    def descend(value, is_sa, acting_faction, action_command):
        if isinstance(value, dict):
            _walk(value, acting_faction, action_command, sa, counts, examples, scenario, seed,
                  card, occurrences, _is_sa=is_sa, _seen=_seen)
        elif isinstance(value, (list, tuple)):
            if id(value) in _seen:
                return
            _seen.add(id(value))
            for item in value:
                descend(item, is_sa, acting_faction, action_command)

    for key, value in ex.items():
        if key not in ("errors", "error", "reason", "sa_skipped"):
            phase_faction = {"germans": rc.GERMANS, "arverni": rc.ARVERNI,
                             "arverni_phase": rc.ARVERNI}.get(key, faction)
            if key in rc.FACTIONS:
                phase_faction = key
            phase_command = _FREE_COMMAND_LABELS.get(key, cmd)
            descend(value, _is_sa or key == "sa_execution",
                    phase_faction, phase_command)


_SEVERITY_ORDER = ("illegal", "wasteful-sa", "ineffective-event",
                  "legal-decline", "other-refused")

# Reason substrings (post-_norm) that mark a Command refusal as the published
# flowchart legally declining rather than a defect.
_LEGAL_DECLINE_REASONS = (
    "nothing marchable",          # expand/mass/spread March IF-NONE fall-through
    "no legal effect",            # "command produced no legal effect"
    "no trade or suborn at sa",   # Aedui §8.6.3 "at that moment" decline
    "no intimidate or settle",    # German A8.7.1 decline
    "if none",                    # generic flowchart IF-NONE text
)


def _severity(kind, msg):
    """Bucket one census incident by severity (see module docstring)."""
    if kind in ("command-error", "sa-error"):
        return "illegal"
    if kind == "sa-no-effect":
        return "wasteful-sa"
    if kind in ("sa-skipped", "action-declined"):
        return "legal-decline"
    if kind == "command-refused":
        low = str(msg).lower()
        if any(r in low for r in _LEGAL_DECLINE_REASONS):
            return "legal-decline"
        if "event not applicable" in low:
            return "ineffective-event"
        return "other-refused"   # an unexpected refusal — surfaced, not hidden
    return "other-refused"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", choices=ALL_SCENARIOS, default=None,
                    help="single scenario (default: all five)")
    ap.add_argument("--seeds", type=parse_seed_range, default="1-10")
    ap.add_argument("--card-edition", choices=CARD_EDITIONS, default="legacy")
    ap.add_argument("--out", default=None, help="write JSON detail here")
    ap.add_argument("--top", type=int, default=60)
    ap.add_argument("--illegal-only", action="store_true",
                    help="list only 'illegal' defects (hide wasteful/legal)")
    ap.add_argument("--strict", action="store_true",
                    help="exit nonzero if any defect-class incident exists "
                         "(illegal, wasteful-sa, ineffective-event, other-refused) — for "
                         "CI soak gating; legal-decline never fails")
    args = ap.parse_args(argv)

    seeds = args.seeds
    scenarios = (args.scenario,) if args.scenario else ALL_SCENARIOS

    metadata = validation_metadata("error_census", scenarios, seeds, args.card_edition,
                                   strict=args.strict)
    print("metadata=" + json.dumps(metadata, sort_keys=True))
    counts = Counter()
    examples = {}
    games, completed = 0, 0
    failures = []
    for sc in scenarios:
        for seed in seeds:
            games += 1
            try:
                result = play_game(sc, seed, card_edition=args.card_edition)
                ending = result.get("ending_scenario", sc) if isinstance(result, dict) else sc
                error = game_completion_error(result, ending)
                if error:
                    raise ValueError(error)
                census_result(result, counts, examples, sc, seed)
            except Exception as exc:
                failures.append(dict(scenario=sc, seed=seed,
                                     error=f"{type(exc).__name__}: {exc}"))
            else:
                completed += 1

    total = sum(counts.values())

    # Aggregate by severity tier.
    by_sev = Counter()
    for key, n in counts.items():
        by_sev[_severity(key[2], key[3])] += n
    illegal = by_sev.get("illegal", 0)

    print(f"games={games}  completed={completed}  failed-games={len(failures)}  total_incidents={total}  "
          f"illegal={illegal}  (defects to drive to zero)")
    print("severity: " + "  ".join(
        f"{sev}={by_sev.get(sev, 0)}" for sev in _SEVERITY_ORDER
        if by_sev.get(sev, 0)))
    for failure in failures:
        print(f"  [game-failure] {failure['scenario']} seed={failure['seed']}: {failure['error']}")

    # Optionally restrict the detailed list to genuine defects.
    items = counts.most_common()
    if args.illegal_only:
        items = [(k, n) for k, n in items
                 if _severity(k[2], k[3]) == "illegal"]
    for key, n in items[:args.top]:
        faction, cmd, kind, msg = key
        sev = _severity(kind, msg)
        print(f"{n:6d}  [{sev:15s}] {faction:8s} {cmd or '-':22s} "
              f"{kind:15s} {msg}")
        sc, seed, card, raw = examples[key]
        print(f"        e.g. {sc} seed={seed} card={card}: {raw[:110]}")
    if args.out:
        with open(args.out, "w") as f:
            json.dump({"metadata": metadata, "games": games, "total": total,
                       "completed": completed, "failed_games": len(failures),
                       "failures": failures,
                       "by_severity": dict(by_sev),
                       "illegal": illegal,
                       "counts": [{"faction": k[0], "command": k[1],
                                   "kind": k[2],
                                   "severity": _severity(k[2], k[3]),
                                   "msg": k[3], "n": n}
                                  for k, n in counts.most_common()]}, f,
                      indent=1)
    if args.strict:
        defects = (by_sev.get("illegal", 0) + by_sev.get("wasteful-sa", 0)
                   + by_sev.get("ineffective-event", 0)
                   + by_sev.get("other-refused", 0))
        return min(defects + len(failures), 250)
    return min(len(failures), 250)


if __name__ == "__main__":
    raise SystemExit(main())
