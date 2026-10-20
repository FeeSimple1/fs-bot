"""Verification only: run engine's existing audited game runner on held-out/replay sets."""
import argparse
import json, os, sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from fs_bot.tools.run_batch import play_one, summarize, SCENARIOS


def hard_findings(rows):
    failures = []
    for row in rows:
        bad = []
        if not row.get('completed'): bad.append('incomplete')
        if row.get('errors'): bad.append('crash/audit error')
        if row.get('integrity_findings'): bad.append('integrity')
        if any(d.get('severity') == 'illegal' for d in row.get('diagnostics', [])): bad.append('illegal')
        if row.get('engine_ranking_output_missing') or len(row.get('final_ranking', [])) != 4: bad.append('rankings')
        if row.get('winner_differs_from_highest_margin'): bad.append('winner/ranking')
        if not row.get('final_state_sha256'): bad.append('missing hash')
        if bad: failures.append({'scenario':row['scenario'],'seed':row['seed'],'findings':bad})
    return failures

SIG = ('winner','cards','final_ranking','diagnostics','diagnostic_occurrences',
       'final_state_sha256','termination','interlude_completed','integrity_findings')
def signature(row): return {key:row.get(key) for key in SIG}

if __name__ == '__main__':
    assert os.environ.get('PYTHONHASHSEED') == '0'
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('heldout', 'replay', 'check'))
    parser.add_argument('--data-dir', type=Path, required=True)
    args = parser.parse_args()
    OUT = args.data_dir
    OUT.mkdir(parents=True, exist_ok=True)
    mode = args.mode
    if mode == 'heldout':
        tasks = [(sc, seed) for sc in SCENARIOS for seed in range(201,221)]
        with ProcessPoolExecutor(max_workers=4) as pool: rows = list(pool.map(play_one,tasks))
        (OUT/'heldout-100.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        result = {'games':len(rows),'hard_findings':hard_findings(rows),'summary':summarize(rows)}
        (OUT/'heldout-summary.json').write_text(json.dumps(result,indent=2)+'\n')
    elif mode == 'replay':
        allrows = [json.loads(line) for line in (OUT/'final-1000/games.jsonl').read_text().splitlines()]
        chosen = {}
        for sc in SCENARIOS:
            rows = [r for r in allrows if r['scenario']==sc]
            for r in (rows[0],min(rows,key=lambda r:r['cards']),max(rows,key=lambda r:r['cards'])):
                chosen[(sc,r['seed'])] = r
        for predicate in (
            lambda r:r.get('interlude_completed'),
            lambda r:len(r.get('threshold_qualifiers',[]))>1,
            lambda r:r.get('termination')=='final-winter-margin',
            lambda r:r.get('termination')=='optimates',
        ):
            match = next((r for r in allrows if predicate(r)),None)
            if match: chosen[(match['scenario'],match['seed'])] = match
        # Include specific trajectory changes from the fixed rules.
        base = {(r['scenario'],r['seed']):r for r in map(json.loads,(OUT/'baseline-1000/games.jsonl').read_text().splitlines())}
        for sc in SCENARIOS:
            changed = next((r for r in allrows if r['scenario']==sc and signature(r)!=signature(base[(sc,r['seed'])])),None)
            if changed: chosen[(sc,changed['seed'])] = changed
        with ProcessPoolExecutor(max_workers=4) as pool: repeated = list(pool.map(play_one,chosen))
        mismatches = []
        for r in repeated:
            before = chosen[(r['scenario'],r['seed'])]
            if json.dumps(signature(r),sort_keys=True)!=json.dumps(signature(before),sort_keys=True):
                mismatches.append({'scenario':r['scenario'],'seed':r['seed']})
        result = {'games':len(repeated),'cases':[list(k) for k in chosen],
                  'hard_findings':hard_findings(repeated),'mismatches':mismatches}
        (OUT/'replay-summary.json').write_text(json.dumps(result,indent=2)+'\n')
    elif mode == 'check':
        rows = list(map(json.loads,(OUT/'final-1000/games.jsonl').read_text().splitlines()))
        result = {'games':len(rows),'hard_findings':hard_findings(rows)}
    else: raise ValueError(mode)
    print(json.dumps(result,indent=2))
    raise SystemExit(bool(result['hard_findings'] or result.get('mismatches')))
