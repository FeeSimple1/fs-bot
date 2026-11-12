# Sixth comparison repairs, Batch 4 · 11 November 2026

Batch 4 closes both free-action findings. Eleven of the 14 sixth-audit
findings are repaired. The three bot forecast findings remain open for
Batch 5.
[Finding ledger](comparison-audit-round6-2026-11-11.json) ·
[Validation evidence](sixth-comparison-batch4-2026-11-11-evidence.zip)

| Finding | Repaired behavior |
|---|---|
| FE6-01 | Aedui may Ambush in at most one Region of a Battle Command. The same check covers ordinary Battle and Event-granted Battle, including both plan formats for shaded Assembly of Gaul. |
| FE6-02 | Ariovistus Enlist can split up to four Warbands from one origin among groups, each moving to one adjacent Region or staying at the origin to hide. The terminal and assistant plans select each group's Warbands by visibility. |

## Aedui Ambush

The free Command rejects an excessive selection before Battle starts. A
saved assistant choice remains pending for correction and replays with
the same board and RNG. With a legal Ambush in Carnutes, the separate
Battle in Mandubii still resolves its normal Counterattack and removes
one Aedui Warband in the directed fixture.
[Aedui Ambush §4.4.3](../../Reference%20Documents/Chapter%204#L188) ·
[Assembly of Gaul](../../Reference%20Documents/Card%20Reference#L518)

## Enlist March

The grouped plan validates the shared four-Warband limit and the origin's
Enlist eligibility. It checks the total requested at each visibility
before flipping pieces, then performs the origin flip once on the selected
Warbands. A formerly Scouted Warband moves Revealed. A later group failure
rolls back the whole free German March. Existing single-destination plans
remain valid, and base-game Enlist retains its single-group procedure.

The terminal tests send two Warbands from Sugambri to Nervii and two to
Treveri in both Ariovistus and The Gallic War. The saved Event grant test
replays the accepted split through the durable assistant session.
[Limited Command §2.3.5](../../Reference%20Documents/Chapter%202#L65) ·
[Gallic March §3.3.2](../../Reference%20Documents/Chapter%203#L244) ·
[Base German March §3.4.2](../../Reference%20Documents/Chapter%203#L354) ·
[Ariovistus German March §A3.4.2](../../Reference%20Documents/Ariovistus/Chapter%20A3#L108) ·
[Enlist §§4.5.1 and A4.5.1](../../Reference%20Documents/Chapter%204#L195) ·
[Ariovistus Enlist limit](../../Reference%20Documents/Ariovistus/Chapter%20A4#L44)

## Verification

Tests ran on Python 3.12.14 against parent
`8491880e6e2e01454824aba8e6babb08b3932a36`. The repaired Python source
SHA-256 is `8c125c9a9fb19d821790e951b2974f3bd7e751b4584e8f2ac676a902c890bd10`
across 601 files.

| Check | Result |
|---|---|
| Full suite | 9,975 passed, including 19 directed cases. Running those cases on the parent produced 16 failures and three passing controls. |
| Audited bot games | 100 legacy and 20 second-edition games completed with full rankings, clean piece and structure checks, and only legal declines. Eleven reached the Interlude. All gameplay fields in the 120 records matched Batch 3. |
| Mixed-player replay | 20 second-edition cases matched across hash seeds 0 and 987. Each run had 562 human turns, 153 Event attempts, 141 executed Events, zero hard findings and one partial plan. |
| Balance | The 100-game check passed against the reviewed 15-point band. The largest win-rate shift against that baseline was 10 percentage points. |

The legacy matrix uses seeds 1–20 and the second-edition matrices use
seeds 41–44 across all five scenarios.
