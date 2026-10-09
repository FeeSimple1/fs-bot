"""Reproducible, failure-isolated bot-only outcome study.

Run from the repository root with::

    PYTHONHASHSEED=0 python -m fs_bot.tools.run_batch --games 200 --workers 4 --out results

``game_completed`` describes the engine result. ``completed`` additionally
requires all audit/serialization stages to succeed and no integrity findings.
An errored record is never counted as a validated win. Diagnostic occurrences
cover returned cards only; a failing card is identified by the crash context.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import platform
import statistics
import subprocess
import time
import traceback
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import fs_bot.rules_consts as rc
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import validate_state, check_structural_integrity
from fs_bot.engine.game_engine import start_game, play_card, get_sop_factions
from fs_bot.engine.victory import determine_final_ranking, check_victory
from fs_bot.cli.dispatcher import make_decision_func
from fs_bot.tools.error_census import census_result, _severity
from fs_bot.state.serialize import encode

SCENARIOS = (rc.SCENARIO_PAX_GALLICA, rc.SCENARIO_RECONQUEST,
             rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS,
             rc.SCENARIO_GALLIC_WAR)


def _new_record(task):
    scenario, seed = task
    return dict(scenario=scenario, seed=seed, completed=False,
                game_completed=False, audit_completed=False, errors=[],
                diagnostics=[], diagnostic_occurrences=[], integrity_findings=[],
                decisions=0, commands=[], special_activities=[], cards=0, winters=0,
                diagnostic_coverage="returned-cards-only")


def _record_error(result, stage, exc):
    error = dict(stage=stage, error_type=type(exc).__name__, error=str(exc),
                 traceback=traceback.format_exc())
    result['errors'].append(error)
    # Preserve the first failure; later audit errors must not conceal it.
    if 'error' not in result:
        result.update(error)
    result['completed'] = False


def play_one(task):
    """Return one record even if setup, gameplay, or postprocessing raises."""
    scenario, seed = task
    began = time.monotonic()
    result = _new_record(task)
    state = None
    cards, faults = [], {}
    commands, sas = Counter(), Counter()
    last_faction = None
    stage = 'setup'

    def inspect(boundary):
        errors = [('conservation', e) for e in validate_state(state)]
        errors += [('structural', e) for e in check_structural_integrity(state)]
        errors += [('resource-cap', f'{f}: {n}')
                   for f, n in state['resources'].items() if n > rc.MAX_RESOURCES]
        for kind, error in errors:
            faults.setdefault((kind, error), dict(kind=kind, message=error,
                              first_boundary=boundary,
                              current_card=state.get('current_card')))

    try:
        with contextlib.redirect_stdout(io.StringIO()):
            state = setup_scenario(scenario, seed=seed)
            state['non_player_factions'] = set(get_sop_factions(state))
            stage = 'bot-initialization'
            bot = make_decision_func({}, stdin=io.StringIO(),
                                     stdout=io.StringIO(), pause=False)

            def decide(st, faction, options, position):
                nonlocal last_faction
                inspect('before-decision')
                last_faction = faction
                decision = bot(st, faction, options, position)
                result['decisions'] += 1
                action = decision['bot_action']
                commands[(faction, action.get('command'))] += 1
                if action.get('sa') not in (None, 'No SA'):
                    sas[(faction, action['sa'])] += 1
                return decision

            stage = 'gameplay'
            inspect('setup')
            start_game(state)
            while state['current_card'] is not None:
                if len(cards) >= 200:
                    raise RuntimeError('Study safety limit of 200 resolved cards exceeded')
                card = play_card(state, decide, execute=True)
                cards.append(card)
                # Record engine completion before auditing the final card.
                result['game_completed'] = bool(card.get('game_over') and card.get('winner'))
                result['winner'] = card.get('winner')
                stage = 'after-card-audit'
                inspect('after-card')
                stage = 'gameplay'
                if card.get('game_over'):
                    break

            stage = 'outcome-audit'
            last = cards[-1] if cards else {}
            winter = last.get('winter_result') or {}
            victory = (winter.get('winter_result') or {}).get('phases', {}).get('victory', {})
            ranks = determine_final_ranking(state)
            qualifiers = [f for f, _ in ranks if check_victory(state, f)]
            winner = last.get('winner')
            termination = ('optimates' if victory.get('optimates_end') else
                           'threshold' if winner and qualifiers else
                           'final-winter-margin' if winner and winter.get('is_final') else
                           'deck-exhausted' if last.get('game_over') else 'unfinished')
            result.update(winner=winner, ending_scenario=state['scenario'],
                          interlude_completed=bool(state.get('interlude_completed')),
                          termination=termination, ended_on_final_winter=bool(winter.get('is_final')),
                          final_ranking=ranks, threshold_qualifiers=qualifiers,
                          highest_margin_leader=ranks[0][0] if ranks else None,
                          winner_differs_from_highest_margin=bool(winner and ranks and winner != ranks[0][0]),
                          engine_ranking_output_missing=bool(winner and last.get('final_ranking') is None),
                          final_resources=dict(state['resources']))
            if len(ranks) != 4:
                faults[('ranking', 'size')] = dict(kind='ranking', message=str(ranks))
            for faction, margin in ranks:
                if (margin > 0) != check_victory(state, faction):
                    faults[('victory', faction)] = dict(kind='victory', message=f'{faction} margin/threshold mismatch')
    except Exception as exc:
        _record_error(result, stage, exc)

    result.update(cards=len(cards), last_faction=last_faction,
                  current_card=state.get('current_card') if state is not None else None,
                  winters=state.get('winter_count', 0) if state is not None else 0,
                  integrity_findings=list(faults.values()),
                  commands=[dict(faction=f, command=c, count=n) for (f, c), n in commands.items()],
                  special_activities=[dict(faction=f, activity=s, count=n) for (f, s), n in sas.items()])
    try:
        counts, examples = Counter(), {}
        census_result({'card_results': cards}, counts, examples, scenario, seed,
                      occurrences=result['diagnostic_occurrences'])
        result['diagnostics'] = [dict(faction=k[0], command=k[1], kind=k[2], message=k[3],
                                     severity=_severity(k[2], k[3]), count=n, example=examples[k])
                                 for k, n in counts.items()]
    except Exception as exc:
        _record_error(result, 'diagnostics', exc)
    if state is not None:
        try:
            snapshot = encode({k: v for k, v in state.items() if k != 'decision_agent'})
            result['final_state_sha256'] = hashlib.sha256(
                json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
        except Exception as exc:
            _record_error(result, 'serialization', exc)
    result['audit_completed'] = not result['errors'] and not faults
    result['completed'] = result['game_completed'] and result['audit_completed']
    result['seconds'] = round(time.monotonic() - began, 4)
    return result


def summarize(records):
    output = {}
    for scenario in SCENARIOS:
        rows = [r for r in records if r['scenario'] == scenario]
        if not rows:
            continue
        completed = [r for r in rows if r.get('completed') and not r.get('error')
                     and not r.get('errors') and not r.get('integrity_findings')]
        diagnostics, diagnostic_games = Counter(), Counter()
        for record in rows:
            found = set()
            for diagnostic in record.get('diagnostics', []):
                diagnostics[diagnostic['severity']] += diagnostic['count']
                found.add(diagnostic['severity'])
            diagnostic_games.update(found)
        output[scenario] = dict(
            attempted=len(rows), completed=len(completed),
            engine_completed=sum(r.get('game_completed', False) for r in rows),
            crashes=sum(bool(r.get('error') or r.get('errors')) for r in rows),
            wins=dict(Counter(r['winner'] for r in completed)),
            highest_margin_leaders=dict(Counter(r['highest_margin_leader'] for r in completed)),
            winner_margin_disagreements=sum(r['winner_differs_from_highest_margin'] for r in completed),
            simultaneous_threshold_games=sum(len(r['threshold_qualifiers']) > 1 for r in completed),
            terminations=dict(Counter(r['termination'] for r in completed)),
            interlude_games=sum(r.get('interlude_completed', False) for r in rows),
            cards_mean=statistics.mean(r['cards'] for r in completed) if completed else None,
            cards_median=statistics.median(r['cards'] for r in completed) if completed else None,
            cards_range=[min(r['cards'] for r in completed), max(r['cards'] for r in completed)] if completed else None,
            winters=dict(Counter(r['winters'] for r in completed)),
            integrity_flagged_games=sum(bool(r.get('integrity_findings')) for r in rows),
            diagnostic_incidents=dict(diagnostics), diagnostic_games=dict(diagnostic_games),
            decisions=sum(r.get('decisions', 0) for r in rows))
    return output


def collect_future(future, task):
    """A failed worker must become a record, not terminate the entire study."""
    try:
        return future.result()
    except Exception as exc:
        result = _new_record(task)
        _record_error(result, 'worker', exc)
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--games', type=int, default=200)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.games < 1 or args.workers < 1:
        parser.error('--games and --workers must be positive')
    if os.environ.get('PYTHONHASHSEED') != '0':
        parser.error('Launch with PYTHONHASHSEED=0 for reproducibility')
    args.out.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[2]
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
        dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True).strip())
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = None, None
    # A source digest identifies uncommitted tested content as well as the Git ref.
    digest = hashlib.sha256()
    for path in sorted((root / 'fs_bot').rglob('*.py')):
        digest.update(str(path.relative_to(root)).encode() + b'\0' + path.read_bytes())
    meta = dict(commit=commit, dirty=dirty, source_sha256=digest.hexdigest(),
                started_utc=datetime.now(timezone.utc).isoformat(), python=platform.python_version(),
                hash_seed=0, seeds=[1, args.games], games_per_scenario=args.games,
                scenarios=SCENARIOS, workers=args.workers, all_factions_bots=True)
    (args.out / 'metadata.json').write_text(json.dumps(meta, indent=2) + '\n')
    tasks = [(s, seed) for s in SCENARIOS for seed in range(1, args.games + 1)]
    records = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool, (args.out / 'games.jsonl').open('w') as log:
        futures = {pool.submit(play_one, task): task for task in tasks}
        for future in as_completed(futures):
            record = collect_future(future, futures[future])
            records.append(record)
            log.write(json.dumps(record) + '\n')
            log.flush()
            if len(records) % 50 == 0 or record.get('error'):
                print(f'{len(records)}/{len(tasks)} games; errors={sum(bool(r.get("error")) for r in records)}', flush=True)
    records.sort(key=lambda r: (SCENARIOS.index(r['scenario']), r['seed']))
    (args.out / 'games.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in records))
    summary = summarize(records)
    (args.out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2), flush=True)
    return 0 if all(r['completed'] for r in records) else 1


if __name__ == '__main__':
    raise SystemExit(main())
