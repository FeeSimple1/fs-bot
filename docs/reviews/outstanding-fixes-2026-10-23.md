# Outstanding fixes and validation — 23 October 2026

**Later disposition, 24 October 2026:** the owner subsequently adopted
[six provisional project rulings](../provisional-rulings.md), all subject to
possible later authoritative correction. This report's original source,
measurements, and then-open question dispositions remain historical evidence;
they do not validate that later adoption.

This review continues the rules, human-interface, Vassal comparison, and
automated-game work. The [current engineering status](../current-status.md)
lists the corrected behavior and regression files. Earlier audit reports
describe their own revisions; their outcome statistics do not describe this
revision.

## What the larger game sample found

An initial 1,000-game run on `fe770da` covered seeds 1–200 in each of the five
scenarios. It completed 993 games, with seven Quarters crashes and sixteen
refused Event actions. No piece-integrity failures or completed-game
ranking/hash failures were found.

| Failure | Incidents | Cause and correction |
|---|---:|---|
| Quarters | 7 crashes | Relocations were validated after earlier arrivals had changed Control. Validate the complete adjacent relocation step against its starting board, preserve the original moving groups, then use the resulting board for Supply Lines. |
| Morasses, shaded Card 36 | 6 refusals | The generic March path did not implement the Belgic instruction to March in place, and its Battle selection could attack Germans. Use the printed beneficiary instructions, eligible targets, Ambush exceptions, and complete Battle Command. Decline a wholly ineffective Event before selection. |
| Impetuosity, unshaded Card 72 | 4 refusals | Roman selection attempted an Event without the required adjacent March and resulting enemy Battle. Apply Roman March priorities and availability before selection; support human multi-origin movement and attacker choices. |
| Publius Licinius Crassus, A17 | 6 refusals | The old path allowed invalid groups, omitted two-step routes, and could filter destinations too late. Form the printed group, execute a real Roman March with drop-offs and Harassment, and Battle only at the chosen Caesar-free endpoint. |

A second 1,000-game run on `0e4ebda` completed 997 games, with no refused
Event actions or integrity findings. Its only failures were Reconquest seed
75 and Great Revolt seeds 92 and 96: after-Harvest Winter Campaign Marches
looked up faction order on the Winter marker as if it were an Event. The
fix recognizes this boundary and preserves the existing fallback order;
the references leave the correct Winter order unresolved. Regression tests
exercise the actual after-Harvest human action and all three full-game seeds.

Focused review also found defects that a bot-only completion count would
not reveal: independent human Retreat agreements could eliminate every
predicted Battle outcome, Harassment losses could be subtracted twice,
and human Harassment choices were missing. The regression work checks
actual piece identity, visibility, decision ownership, and saved RNG state
in addition to totals and game completion.

The final baseline refresh retains the same 100 games (seeds 1–20 in each
scenario) and the same 15-percentage-point drift threshold. Relative to
the `fe770da` baseline, 26 records changed, including 23 winners. The
corrections change actual Harassment eligibility, casualty selection,
movement and Event resolution; no bot priorities were tuned to obtain
preferred win rates. The evidence archive includes every before/after
record and the scenario-level counts.

## Final verification

The corrected 1,000-game batch on `c7264cb3d2afbf08ccfce140af6e03b0f17138ae`
completed all games. Every scenario has exactly 200 unique seeds, 1–200.
There were **zero crashes, rejected actions, integrity findings, missing
rankings, or final-state hash failures**. The 9,678 recorded diagnostics
were legal declines. The source digest remained unchanged during the run.

The local full suite passed **4,067 tests** on Python 3.12.14. The subsequent
100-game balance check matched the reviewed baseline exactly, without
another refresh or threshold change.

The 25-game bot repeat (seeds 1–5 in each scenario) matched hash seeds 0
and 7 across all twelve compared fields, including final-state hashes,
rankings, diagnostics, and Interlude results. Mixed-seat fuzzing covered
200 cases at each hash seed with replay enabled: 800 game executions in
all. Both runs reported 6,610 human turns, 1,714 Event turns, zero hard
findings, and identical output and digest `a2c5dc6af82a365a`.

Each mixed-seat run also recorded 586 partial plans from its deliberately
noisy random policy. Their sub-action results matched between preview and
live execution. These are reported separately from crashes, corruption,
mutation on rejected actions, and nondeterministic results; the sample is
not described as 200 games in which every generated human plan succeeded.

The strict census covered 100 games at each hash seed. Both JSON reports
were identical: 944 legal declines and no other diagnostic severities.
The combined matrix verifier and independent extractor both passed every
acceptance check, with no source changes during any stage.

Remote CI is recorded separately in [the source revision's GitHub Actions
run](https://github.com/FeeSimple1/fs-bot/actions/runs/40035956541). All eight
jobs passed for the tested code revision. The jobs
cover Ubuntu Python 3.10/3.12, Windows Python 3.12, macOS Python 3.12,
synchronization, strict census, mixed-seat cross-hash replay, and the
reviewed balance baseline. Local matrix results above do not substitute
for those remote job conclusions.

## Bot outcome sample

These are zero-human games using the default `legacy` card profile:
original versions of the five optional revised cards in base scenarios,
revised versions in Ariovistus. The profile follows the scenario after the
Gallic War Interlude. All rates below use 200 completed games per row;
entries show wins and percentage. A dash means the faction cannot win that
scenario. Gallic War records the faction at game end, including Arverni
after the German player's Interlude transition.

| Scenario | Romans | Arverni | Aedui | Belgae | Germans |
|---|---:|---:|---:|---:|---:|
| Pax Gallica? | 139 (69.5%) | 14 (7%) | 15 (7.5%) | 32 (16%) | — |
| Reconquest of Gaul | 125 (62.5%) | 11 (5.5%) | 30 (15%) | 34 (17%) | — |
| The Great Revolt | 40 (20%) | 77 (38.5%) | 24 (12%) | 59 (29.5%) | — |
| Ariovistus | 93 (46.5%) | — | 19 (9.5%) | 26 (13%) | 62 (31%) |
| The Gallic War | 101 (50.5%) | 36 (18%) | 12 (6%) | 51 (25.5%) | 0 (0%) |

| Scenario | Ended before final Winter | Ended on final Winter | Mean cards processed | Interlude reached |
|---|---:|---:|---:|---:|
| Pax Gallica? | 173 | 27 | 36.42 | — |
| Reconquest of Gaul | 151 | 49 | 32.71 | — |
| The Great Revolt | 25 | 175 | 43.23 | — |
| Ariovistus | 58 | 142 | 38.40 | — |
| The Gallic War | 163 | 37 | 61.66 | 126 |

Ending on the final Winter does not necessarily mean victory by final
margin: a threshold or Optimates result can also occur on that card. The
machine-readable evidence separates those reasons from timing. These
seeds are a reproducible software sample, not a random survey of human
play or an independent estimate of each faction's intrinsic strength.

## Reproduction and evidence

Tested source: [`c7264cb3d2afbf08ccfce140af6e03b0f17138ae`](https://github.com/FeeSimple1/fs-bot/commit/c7264cb3d2afbf08ccfce140af6e03b0f17138ae).
SHA-256 over sorted paths and contents of every `fs_bot/**/*.py` file:
`a7332a944ec34e2c9b802958fdbf926361985528044f799814a54e42827083af`.
The matrix checks this digest before and after each stage. Subsequent
publication changes contain documentation and evidence only.

The [results JSON](outstanding-fixes-2026-10-23-results.json) contains
scenario counts, acceptance checks, and artifact hashes. The
[evidence archive](outstanding-fixes-2026-10-23-evidence.zip) includes all
three 1,000-game attempts, their manifests and diagnostics, the completed
matrix, baseline changes, and JUnit results. Remote CI is linked above.
`CONTENTS.sha256` lists hashes for the archived evidence files. Failed attempts are preserved
separately and are not pooled into the final win rates.

The archive includes an orchestrator and an independent result extractor.
To repeat the matrix, copy those scripts into a fresh directory beside a
checkout named `fs-bot`; inspect `orchestrate.py commands`, then run its
`batch`, `bots-hash7`, `fuzz-hash0`, `fuzz-hash7`, `census-hash0`, and
`census-hash7` stages followed by `verify`. Do not overwrite the archived
results. The principal repository commands are:

```sh
python -m pytest -q
PYTHONHASHSEED=0 python -m fs_bot.tools.run_batch --games 200 --workers 4 --out new-results
PYTHONHASHSEED=0 python -m fs_bot.tools.player_fuzz --seeds 1-40
PYTHONHASHSEED=7 python -m fs_bot.tools.player_fuzz --seeds 1-40
PYTHONHASHSEED=0 python -m fs_bot.tools.error_census --seeds 1-20 --strict
PYTHONHASHSEED=7 python -m fs_bot.tools.error_census --seeds 1-20 --strict
python -m fs_bot.tools.balance_smoke --seeds 1-20
```

## Source limits

Six source questions remain documented in [current status](../current-status.md#source-conflicts-still-open):
A30's missing Belgic instruction, the A8.6.6/A28 faction-name conflict,
unused human Frumentum funding, German-owned A63 after Interlude, the
position of automatic Arverni Harassment in Ariovistus's resolution order,
and Harassment order during after-Harvest Winter Campaign actions.
The clear surrounding mechanics are fixed; the unresolved text is not
silently replaced by an invented ruling. The supplied reference documents
and `fs_bot/rules_consts.py` remain unchanged.

Seeded results measure this implementation of the published bot policies.
They do not establish balance among expert human players, and passing the
listed tests does not prove that every possible game position is correct.
