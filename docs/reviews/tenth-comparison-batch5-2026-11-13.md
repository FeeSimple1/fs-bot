# Tenth comparison repairs, Batch 5 · 13 November 2026

Batch 5 closes NP10-01 and NP10-02. All nine tenth-audit groups are closed.
[Finding ledger](comparison-audit-round10-2026-11-13.json) ·
[Validation evidence](tenth-comparison-batch5-2026-11-13-evidence.zip)

## Arverni Special Abilities after March

After a spread or mass March, the bot checks the board and remaining
Resources for Devastate, then Entreat. In the audit position, one Resource
moves Vercingetorix and eight Warbands from Mandubii to Carnutes. The
newly eligible Entreat spends a second Resource and replaces a Roman
Auxilium with a ninth Hidden Warband. The Sequence of Play offers the
second Eligible faction its Event option only if the ability takes effect.
[Arverni timing §8.7.1](../../Reference%20Documents/Chapter%208#L645) ·
[Spread §8.7.4](../../Reference%20Documents/Chapter%208#L711) ·
[Mass §8.7.6](../../Reference%20Documents/Chapter%208#L747)

The live check uses the ability allowance and Region scope of the grant.
An actual Britannia crossing bars an accompanying ability under the
ordinary rule. Winter Campaign's printed exception allows the crossing
and the ability when it has both paid actions available. A group deferred
before movement does not count as a crossing. The threat March retains
its ability check after payment and before movement.
[Britannia §4.1.3](../../Reference%20Documents/Chapter%204#L38) ·
[Winter Campaign](../../Reference%20Documents/Card%20Reference#L645)

Mixed-seat replay exposed a late Entreat attempt against a Roman Ally
when Arverni Warbands were exhausted. The bot's removal fallback now
considers eligible player Allies. The test retains the Roman Ally and
charges only the March.
[Entreat §4.3.1](../../Reference%20Documents/Chapter%204#L107)

## Repeated Devastate

A marked Region can qualify again if Arverni Control, Leader range and
the bot's casualty priority still hold. The earlier Devastate in the
Bituriges fixture leaves six Arverni Warbands and four Legions. A later
Rally's Devastate removes one of each, sends the Legion to Fallen and
keeps the single marker. Each use selects the Region once.
[Devastate §4.3.2](../../Reference%20Documents/Chapter%204#L121) ·
[Bot casualty priorities](../../Reference%20Documents/Chapter%208#L645)

## Verification

Python 3.12.14 tested the repair to parent
`d27e774bd90c5c6c172d5b69dbce574fd176702c`. The repaired Python source
SHA-256 is `489efe1d5b60a36f47ac5b7b46fd47595246d770606e32f6fa78d5b5b8d6a9e0`
across 626 files. All 47 supplied reference documents and canonical
constants match their audit hashes.

| Check | Result |
|---|---|
| Directed and focused tests | 22 new cases pass at hash seeds 0 and 987. The parent fails 11 and passes 11. The wider Arverni, Winter and scoped Command checks pass all 212 tests. |
| Full suite | 10,379 pass. The 27 balance canary and guardrail checks also pass with the refreshed baseline. |
| Audited bot games | All 120 complete with clean conservation, structure and rankings. All 2,120 diagnostic occurrences are legal declines. Twelve games reach the Interlude. The sample covers all five scenarios on legacy seeds 1–20 and second-edition seeds 53–56. |
| Mixed-seat replay | All 20 second-edition cases agree byte for byte at hash seeds 0 and 987. Zero hard findings and one recurring soft partial plan. Five cases have gameplay changes from Batch 4, and two record the new legal decline after March with matching gameplay. |
| Balance | The old baseline reports a 20-point shift in Reconquest Aedui wins. After review of the paired games, the refreshed baseline matches an independent run on all 100 winners and card counts. The original seeds and 15-point band apply. |

## Paired outcomes

| Edition | Games | Changed final states | Changed winners | Changed card counts |
|---|---:|---:|---:|---:|
| Legacy | 100 | 44 | 16 | 13 |
| Second edition | 20 | 9 | 3 | 1 |

All 53 changed bot games start their first differing card on matching
board and RNG fingerprints. Fifty first differ at the Special Ability
after a March. Three first differ when the bot Devastates an already
marked Region after Rally or before Battle. On Pax Gallica seed 5, a
repeat Devastate after Rally removes one Arverni and two Aedui Warbands
from Mandubii. The recorded changes include the preceding Command,
affected Regions, Resources and losses.

All eight changed Reconquest winners first diverge after March. On seed 7,
the Arverni spend their last Resource moving, then Devastate Mandubii
and remove one Warband each from Arverni and Aedui. On the other seven
seeds, the first difference is Entreat. Across these 20 fixed seeds the
Aedui win 3 games, down from 7. The evidence retains the prior baseline,
the failed comparison, the paired traces, and the independently verified
new baseline.
