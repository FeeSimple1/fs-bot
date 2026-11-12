# Seventh comparison repairs, Batch 3 · 11 November 2026

Batch 3 closes FE7-01. Five of the nine audit groups remain open.
[Finding ledger](comparison-audit-round7-2026-11-11.json) ·
[Validation evidence](seventh-comparison-batch3-2026-11-11-evidence.zip)

Base-game German March permits one moving group from each origin to one
adjacent Region. The executor now checks normalized routes before hiding
or moving pieces. The same check applies to `extra_groups` and
`explicit_moves`, including two moving groups with the same destination.
A single group can leave Warbands behind, and a hide-only stay remains
legal. The terminal offers those choices for a base-game German origin.
Ariovistus Germans and Gallic Marches retain their multiple-group rules.
[Base Germanic March](../../Reference%20Documents/Chapter%203#L340) ·
[Ariovistus Germanic March](../../Reference%20Documents/Ariovistus/Chapter%20A3#L108)

Shaded Surus applies the rule to the German Warbands acting under the
Event executor's guidance. An illegal split rolls back the replacements,
movement and RNG. In a saved session the same choice stays pending until
corrected, and the accepted single-group plan replays exactly. A transcript
that replays a formerly accepted split will encounter a rejected choice.
[Surus](../../Reference%20Documents/Card%20Reference#L507)

## Verification

Tests ran on Python 3.12.14 against parent
`0e0f4efd1f224db1b726fe47c92af8a8c8318603`. The repaired Python source
SHA-256 is `ac18759d7d7e4fafc72f8e7dd1fa11aef895253e21c84b82616190b0f08bfd3d`
across 607 files.

| Check | Result |
|---|---|
| Full suite | 10,043 passed, including 11 new March cases. The parent reproduces seven failures and passes four controls. |
| Audited bot games | All 100 legacy and 20 second-edition games completed cleanly and matched their paired Batch 2 outcomes, including final states, rankings, game lengths and diagnostics. |
| Mixed-player replay | Twenty second-edition cases matched byte-for-byte across hash seeds 0 and 987. Each run had 553 human turns, 145 Event attempts, 132 executed Events, three partial plans and zero hard findings. The replay digest matches Batch 2. |
| Balance | All 100 legacy winners and game lengths match the reviewed baseline. The 15-point band passes. |

The legacy matrix uses seeds 1–20 and the second-edition matrix uses seeds
41–44 across all five scenarios. Thirteen Gallic War games reached the
Interlude, including one in the second-edition matrix.
