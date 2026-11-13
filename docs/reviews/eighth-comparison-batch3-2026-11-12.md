# Eighth comparison repairs, Batch 3 · 12 November 2026

Batch 3 closes UI8-01 and UI8-02. Six of the eleven audit groups are closed.
[Finding ledger](comparison-audit-round8-2026-11-12.json) ·
[Validation evidence](eighth-comparison-batch3-2026-11-12-evidence.zip)

Winter Campaign applies the normal Region selection check before previewing
a human plan. A duplicate Battle Region leaves the same decision pending
with the full action budget. The owner can select that Region again in a
separate paid Battle. The card still allows standalone Special Abilities,
its printed pairing and Britannia exceptions, and normal paid costs.
[Command selection](../../Reference%20Documents/Chapter%203#L2) ·
[Card 63](../../Reference%20Documents/Card%20Reference#L645) ·
[Card A63](../../Reference%20Documents/Ariovistus/A%20Card%20Reference#L279)

During a paid human March, the terminal and assistant can offer
`march_dropoff` after the group arrives at an intermediate Region. The
choice applies to the traveling pieces before Harassment and the next hop.
The same March still spends one Campaign action and pays per selected
origin. The dispatcher enables the March choice independently of ordinary
Sequence-of-Play gifts and Command pairing restrictions. The detached
preview uses no live choices.
[Roman March procedure](../../Reference%20Documents/Chapter%203#L61) ·
[Vercingetorix's March](../../Reference%20Documents/Chapter%203#L261)

The saved tests run complete nonfinal Winter rounds from controlled
checkpoints. They verify stable decision IDs after invalid input, board
and RNG rollback, reload, and matching final board, RNG, and log on
verified replay. On the March route, the two chosen Warbands stay at
Mandubii. Harassment affects the group still moving with Vercingetorix
before it reaches Sequani. An older transcript with no drop-off uses the
original keep-moving default. Historical logs that used an invalid
repeated Battle selection are subject to the usual rule-correction replay
checks.

## Verification

The runs used Python 3.12.14 against parent
`21c699a63b0cf5e199dd5750c4abdb3c7d82c5ff`. The repaired Python source digest
is `bcad6fe110ef49ed588afd657e09cdbb9bb908679f4a7a08fda8c4a214f740cd` across
614 files.

| Check | Result |
|---|---|
| Full suite | All 10,160 tests pass. |
| Directed cases | Seven failures reproduce the defects on the parent. Both positive controls pass there. All nine pass on the repair, including complete saved Winters in the base game and Ariovistus. |
| Focused regressions | All 184 Winter, March, and assistant tests pass. |
| Audited bot games | All 120 complete with clean integrity checks and only legal-decline diagnostics. Final boards, rankings, winners, lengths and diagnostics match the paired Batch 2 games. Twelve games reach the Interlude. |
| Mixed-player replay | Twenty second-edition cases match at hash seeds 0 and 987 and agree with Batch 2. The sample covers 623 human turns, 152 Event attempts, 138 executed Events, and zero hard findings or partial plans. |
| Balance | The 100 legacy games pass the 15-point band. The two winner differences from the reviewed baseline come from the Gallic War continuations in Batch 1. |

Bot games use legacy seeds 1–20 and second-edition seeds 45–48 across
all five scenarios. The mixed-player comparison uses second-edition
seeds 45–48. The directed tests cover the new human choices with
controlled positions.
