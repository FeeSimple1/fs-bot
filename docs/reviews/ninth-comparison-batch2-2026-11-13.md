# Ninth comparison repairs, Batch 2 · 13 November 2026

Batch 2 closes LC9-01. Four of the eight ninth-audit groups are complete.
[Finding ledger](comparison-audit-round9-2026-11-12.json) ·
[Validation evidence](ninth-comparison-batch2-2026-11-13-evidence.zip)

The Roman bot counts every arriving Legion and Auxilia alongside the
troops already in a refuge. It pays for troops outside Provincia after
free Fort and Ally slots, subject to available Resources. Payment starts
at Roman Allies, then covers Regions without Devastation, then Devastated
Regions.
[Quarters](../../Reference%20Documents/Chapter%206#L84) ·
[Roman bot priorities](../../Reference%20Documents/Chapter%208#L974) ·
[Ariovistus Quarters](../../Reference%20Documents/Ariovistus/Chapter%20A6#L139)

In the audit position, two Auxilia move from Devastated Morini to Nervii,
where one Auxilia is already quartering. With 20 Resources, the bot now
spends six and keeps all three without rolling. The old plan spent two,
rolled for the remaining two and lost one. The public Quarters phase
reproduces the corrected result across all five scenarios, including
after saving and reloading the position.

## Verification

The runs used Python 3.12.14 on the repair to parent
`1299b41ad4d1dac7db68dde4a4628bb9410c2d40`. The repaired Python source
SHA-256 is `9c2c9c927fc544966796c9fac5ff086e9152dec48148966ba41c88672a379144`
across 618 files.

| Check | Result |
|---|---|
| Directed cases | All 10 pass. The parent fails eight and passes two controls. Cases cover arrivals in either Region order, multiple origins, mixed cohorts, free garrisons, payment order and limited funds. |
| Related tests | 249 pass, including the directed cases. |
| Full suite | 10,240 pass. |
| Audited bot games | 100 legacy games on seeds 1–20 and 20 second-edition games on seeds 49–52 across all five scenarios. All match the parent on final state, winner, card count and diagnostics. Eleven reach the Interlude. |
| Mixed-player replay | Twenty second-edition cases on seeds 49–52 match at hash seeds 0 and 987. Fifteen more on seeds 201–203 match at hash seeds 0 and 7. Both samples match the parent and have zero hard findings, with one and two partial plans respectively. |
| Balance | The 100-game check passes against the existing baseline. Its winners and lengths agree with the independent legacy audit. |

The paired Batch 1 records were captured before its commit and match the
parent checkout's Python source digest. The evidence preserves those
original run identities and the fresh parent reproduction.

Batch 3 covers the Enlist Raid quantity and Morbihan pending display.
