# Expansion Event grants — 2 November 2026

This batch repairs **EXP-01 through EXP-06**, six grouped findings from the
[29 October audit](human-choice-audit-2026-10-29.md). It covers eight expansion
Events, their human ownership and choices, physical participating pieces,
terminal menus and durable decisions. The original audit and its measurements
remain historical. The task began 2 November; final validation continued on
3 November UTC.

The [progress register](../human-choice-progress.json) records **12 of 50
findings closed (24%) and 38 open**. This batch is **6/6 complete (100%)**.
These percentages count findings, whose effort varies; they do not measure
whole-engine rules compliance. The 34 unverified inventory rows and two
non-player source questions remain separate.

## What changed and why

| Finding | Printed source and repaired behavior |
|---|---|
| EXP-01 | A21 Vosegus / A57 Sabis: the executor selects the first legal Battle, with no Retreat; the optional second Battle offers current defenders in that same Region with normal Retreat. Static Forces and legal low-damage choices remain available to humans. NPC priorities remain delegation policy, not human legality. |
| EXP-02 | A19 shaded: any executor selects a whole mobile Roman force and its adjacent destination containing Germans. Roman static pieces stay. Ordinary March hiding and ineligibility apply. The German NPC's no-Fort/outnumber priorities no longer restrict human choices or suppress other executors. |
| EXP-03 | A67 Arduenna: executor chooses a playable non-Arverni beneficiary; that beneficiary may accept or decline the complete sequence. Accepted March into Nervii/Treveri and a subsequent non-March Command there are required when possible, then all friendly pieces there Hide. Separate stages use current boards. |
| EXP-04 | A29 shaded / A69 shaded: executor selects actual placed survivors' Raid choices or Ambush defender, even when another faction owns the pieces. A29's intrinsic offensive Intimidate follows that chooser; defensive reactions and physical ownership remain unchanged. A69 gives the one-Loss bonus only to surviving new Warbands, while residents retain ordinary participation. |
| EXP-05 | A20/A58: Romans decide the optional compound benefit regardless of executor. A20 acceptance precedes all Arverni removal in Veneti, including Scouted pieces; Seize follows if possible. A58 offers Battle then Seize in Belgica. The human chooses each legal component and exact Dispersal Tribes. |
| EXP-06 | Both Roman Seize grants apply their printed Control override and suppress enemy Rally rolls and grants. A58 also suppresses Harassment; A20 retains normal Harassment. Only engine-owned scoped requests authorize these exceptions. Ordinary Seize does not inherit them. |

Authorities are the supplied, unchanged
[Ariovistus card reference](../../Reference%20Documents/Ariovistus/A%20Card%20Reference),
[Chapter 5](../../Reference%20Documents/Chapter%205) §§5.1, 5.1.1, 5.1.3 and 5.4,
[Chapter 3](../../Reference%20Documents/Chapter%203) §§3.1, 3.2.2–3.2.4 and 3.3.3–3.3.4,
[Chapter 4](../../Reference%20Documents/Chapter%204) §§4.3.3/4.5.3,
[Chapter A1](../../Reference%20Documents/Ariovistus/Chapter%20A1) A1.4 and
[Chapter A3](../../Reference%20Documents/Ariovistus/Chapter%20A3) A3.4.3.
The Key Terms Index includes static pieces among Forces. The supplied Roman
and German NP flowcharts/Event instructions govern defaults, including
§§8.2.3, 8.3.4 and 8.8.5 for safe Roman Seize priorities and seeded ties.
No external rules or new project ruling were used; PR-01–09 remain provisional.

A67's single leading “may” permits refusal of the whole sequence. Once
accepted, §5.1.3 requires possible components and §3.1 requires at least one
selected Command Region. Base card 67's Tips and card 72's parallel “March
into” Tips establish actual relocation; card 6 separately repeats “may” for
independently optional components. This resolves the scope from supplied
sources rather than creating another provisional interpretation. A German
NPC/default with no safe Control/Battle plan still declines the whole grant
under its specific instructions; it receives no new hide-only benefit.

## Related defects caught during implementation and review

A67 now tracks each original origin's physical owners and visibility through
formation, split groups, transit dropoffs, Harassment and voluntary removals.
An arrival cannot be moved or hidden again as a later origin's original piece.
A removed original cannot be replaced by an unrelated resident or recreated
from a stale count. Shared March receives a trusted optional initial group;
ordinary calls retain their existing behavior.

After later removals invalidate A69's Ambush prerequisites, the grant skips
the impossible action instead of silently running an ordinary Battle. If all
new pieces disappear, residents cannot inherit the grant. The explicit
Diviciacus defensive cancellation rule remains applicable. Earlier valid
placements and removals remain part of partial Event execution.

An actual refused Diviciacus loan no longer swallows a required accepted
Battle, March or Command. Only the unfinished stage reopens. Roman retries
rebuild current targets: removing the last enemy cannot leave the player
stuck at an impossible mandatory Battle prompt. Retry metadata, accepted
choices and the actual refusal survive save/load/replay without rerolling or
repeating completed effects.

Specialized validators reject forged scope/modifier fields, duplicate or
unavailable targets, excessive pieces and `command_parts`/movement forms
that could bypass these grants' limits. Detached previews do not consume
live input or RNG. Explicit human defaults are validated and preserved in
the journal; if NPC policy supplies no mandatory legal action, the request
stays pending. Raw callback `None` remains its separate documented fallback.

## Implementation and review record

Four isolated implementation worktrees handled Battles, movement, cohort
Raid/Ambush and Roman grants. A fifth agent independently checked supplied
sources, ownership, shared validation boundaries and final retry corrections.
The parent resolved shared dispatcher changes, retaining each namespaced
branch and one common durable-default gate, then reran the entire suite
before each integration commit.

## Accepted validation

| Integrated change | Commit | Full suite before commit |
|---|---|---:|
| EXP-02 | [`e71a63a`](https://github.com/FeeSimple1/fs-bot/commit/e71a63a0893bd5eb0ed53cbcfcf3f4b320866484) | 6,292 |
| EXP-01 | [`1384552`](https://github.com/FeeSimple1/fs-bot/commit/1384552124ff32adde82514f47fbea498d4d3167) | 6,351 |
| EXP-05, EXP-06 | [`76c6eec`](https://github.com/FeeSimple1/fs-bot/commit/76c6eecff06d4c3828d5f561c8be62f66c8a1d7b) | 6,397 |
| EXP-04 | [`26e517a`](https://github.com/FeeSimple1/fs-bot/commit/26e517a68f0a6f565d54e203678a4f78f0c020fb) | 6,441 |
| EXP-03 | [`13e9637`](https://github.com/FeeSimple1/fs-bot/commit/13e96378e7f0960ffb6b4104d76cc75c5120d444) | 6,477 |

Final engine source: `13e96378e7f0960ffb6b4104d76cc75c5120d444`; **403 Python files**,
SHA-256 `db34eb720f500716c4c59b0946b5a91b78897bb45eb726bc351c60f91acb94ca`.
Documentation-only edits were uncommitted during the matrix. The Python
source stayed unchanged throughout; the later report commit does not change
it. Final combined suite: **6,477 passed**, zero failures/errors/skips,
**197 more test cases** than the 6,280-test parent. The documentation commit
also passed its required full-suite rerun: **6,477 passed**. An earlier
documentation-check process ended without a completion report at about 54%;
its incomplete log is retained and is not counted as a pass.

| Check | Coverage | Result |
|---|---|---|
| Bot games | 150: all five scenarios; legacy seeds 1–20, original and second-edition seeds 201–205 | Every game and audit completed; no errors, integrity findings or nonlegal diagnostics; emitted rankings verified |
| Mixed seats | 30 distinct cases: all scenarios × seeds 201–202 × three editions; hashes 0/7 and replay = 120 executions | Zero hard findings or soft partials; matching cross-hash digests |
| Strict census | All five scenarios × seeds 201–202 × hashes 0/7 = 20 executions | Complete; only 133 legal-decline incidents per hash; reports identical |
| Parent comparison | 100 parent games, legacy seeds 1–20 in all scenarios | Exactly reproduced the existing baseline before repair |
| Candidate balance | Same 100 paired legacy games | Passes unchanged 15-percentage-point band; largest absolute faction shift 5 points |
| Protected inputs | 47 supplied reference files, canonical constants and balance baseline | All 49 hashes unchanged |

Commands and exact seeds are in `integration-commands.json` and the archived
`integration_checks.py`; full suites use `python -m pytest -q -n 2` with
JUnit for integrated runs. Runtime: Python 3.12.14. The archive retains raw
records rather than inferring coverage from a runner's exit code.

### Changed outcomes

Six of the 100 paired games changed winner or card count; four changed
winner. All three original-game scenarios retained every paired winner and
card count. The six changed expansion-start games are:

| Scenario | Seed | Before: winner / cards | After: winner / cards |
|---|---:|---|---|
| Ariovistus | 2 | Belgae / 43 | Romans / 14 |
| Ariovistus | 4 | Romans / 32 | Romans / 15 |
| Ariovistus | 17 | Germans / 47 | Belgae / 47 |
| The Gallic War | 2 | Arverni / 68 | Romans / 14 |
| The Gallic War | 4 | Romans / 32 | Romans / 15 |
| The Gallic War | 17 | Belgae / 105 | Aedui / 69 |

The baseline was **not refreshed**. Its unchanged SHA-256 is
`207a129589d2bb17bec17319e70de7c8cf44d1572dc6aaca73cd0b39a9b5b8d3`.
Per-faction paired win counts are retained in the machine-readable results.
A passing drift band is a regression check, not evidence of ideal balance.

A bounded trace review reproduced all twelve parent/candidate outcomes. All
prior trace rows, declared decisions and incoming boards/RNG match. Both
seed-2 pairs first differ at card count 5 on Roman A58: the corrected flowchart
omits a lone-Auxilia attack, and the printed exception removes enemy Rally
rolls and placements. The RNG difference starts with omitting those forbidden
rolls. Both seed-4 pairs first differ at count 4 on Belgic A19: the whole Roman
force now Marches Provincia to Cisalpina. Both seed-17 pairs first differ at
count 29 on Belgic A19: Morini to Sugambri. Those A19 moves consume no RNG.
No unexplained first divergence was found; this does not attribute every
later outcome separately. The archive retains the scripts, twelve complete
traces and compact causal review. One interrupted parent trace is preserved
separately; its single-case rerun reproduced the expected result.


## Evidence and limits

[Machine-readable results](human-event-grants-2026-11-02-results.json) and the
[evidence archive](human-event-grants-2026-11-02-evidence.zip) retain the source
identity, commit ledger, commands, JUnit/logs, raw games, cross-hash reports,
protected-file manifest and implementation/review handoffs. The archive also
retains failed witnesses and superseded development runs, distinguished from
accepted final-source validation. No missing or failed output is treated as
success. In particular, the first Roman integration pass predates its final
retry fix; A67's first two full passes predate later refusal/default repairs.

The new regressions exercise real human selection and durable sessions,
including invalid/pending IDs, rollback, save/load/replay, CLI board/EOF,
physical ownership and actual timing windows. The random mixed-seat policy
still uses raw fallback for unfamiliar specialized free-action types; its
aggregate success is not evidence that it uniformly samples the new menus.
Source-derived dedicated regressions provide that direct coverage.

These changes introduce previously missing choices and correct affected
outcomes. Old affected transcripts may stop at verification and require new
input; unchanged backward replay is not promised. There is no new persistent
save-format version. Base-card counterparts, ordinary Seize's Tribe menu,
remaining Battle casualty identity choices, generic during-Command timing,
seasonal choices and optional/shared-player modes remain separately open.
The frozen matrix is bounded validation, not an exhaustive rules proof or a
statistically conclusive faction-balance study.
