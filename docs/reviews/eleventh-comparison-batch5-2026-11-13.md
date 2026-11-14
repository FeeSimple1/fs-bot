# Eleventh comparison repairs, Batch 5 · 13 November 2026

Batch 5 closes NP11-01 and NP11-02, the final two findings of the eleventh
comparison audit.
[Finding ledger](comparison-audit-round11-2026-11-13.json) ·
[Validation evidence](eleventh-comparison-batch5-2026-11-13-evidence.zip)

## Belgic Enlist after March

The Belgic bot can choose a free Germanic Command after either type of Belgic
March. It uses the Leader's position after movement to determine range. On the
audit board, Ambiorix reaches Atrebates, where he can order two Revealed German
Warbands at Treveri to March in place and Hide. The card records a Special
Ability only when Enlist executes. The shared execution path checks the
completed routes for Britannia crossings and honors Event scope and the
Winter Campaign action allowance. Enlist now applies the same Gallia Togata
stacking restriction as the March executor. An intermediate replay exposed
that omission on Ariovistus seed 7.
[Non-player Belgae §8.5.1](../../Reference%20Documents/Chapter%208#L304) ·
[Enlist §4.5.1](../../Reference%20Documents/Chapter%204#L195) ·
[Ariovistus Enlist A8.5.1](../../Reference%20Documents/Ariovistus/Chapter%20A8#L37) ·
[Gallia Togata A5](../../Reference%20Documents/Ariovistus/A%20Card%20Reference#L9)

## German expansion March

When the Leader and his neighboring Regions are under German Control,
the bot can move him one adjacent Region along a shortest route toward
a Region outside German Control. The bot chooses among equally short legal
steps using the seeded game RNG. The moving group leaves a Warband and any
additional Warbands needed to hold the origin. In the audit position,
Ariovistus leaves Ubii for Cisalpina with 25 Warbands and spends one Resource.
Cisalpina is an intermediate Region toward Provincia.

The companion option moves an away group toward the Leader. The March plan
identifies the group's origin and uses the Leader's destination if the
earlier Control move already moved him. The bot takes the earlier moves
into account when checking Resources and origins available for the extra
step. The authored Treveri route, directly adjacent expansion, Frost and
no-Leader cases provide controls.
[Expansion March A8.7.5](../../Reference%20Documents/Ariovistus/Chapter%20A8#L221) ·
[Germanic March A3.4.2](../../Reference%20Documents/Ariovistus/Chapter%20A3#L108)

## Verification

Validation used Python 3.12.14 and parent
`2e7fe17af7aa1a18e29ea69a90b886887c2fe331`. The repaired Python source
SHA-256 is `7cb64407ff5594eb2bbd671a8159c408410fa8cc26e7a784da7afe0fd47363db`
across 629 files. All 47 supplied references and the canonical constants
match their audit hashes.

| Check | Result |
|---|---|
| Audit reproduction | All 12 parent cases match the audit byte for byte. The two repaired witness runs match across hash seeds 0 and 987. |
| Regression tests | The parent fails 10 of 14 cases and passes four controls. The repair passes 642 focused tests at both hash seeds and 10,449 in the full suite. The Interlude tests use legacy seed 1, which reaches the Interlude with the repaired bots. |
| Audited bot games | All 120 complete across five scenarios on legacy seeds 1–20 and second-edition seeds 57–60. Eleven reach the Interlude. There are zero engine errors, integrity findings or ranking inconsistencies. All 2,128 diagnostics are legal declines. |
| Mixed-seat replay | All 20 cases finish and match across both hash seeds. They record 715 human turns and 167 Event turns, with zero hard findings and four partial plans. |
| Balance | The 100-game check and 15-game canary pass against the reviewed results for their existing seeds and thresholds. |

## Paired outcomes and balance

The two cohorts have 21 changed winners. Each replay starts its first
different card with the same board and RNG. Belgic March Enlist is the
first difference in two games, and the German expansion March is the
first difference in nineteen. The evidence records executed moves and
planning RNG for each case.

| Legacy game | First difference | Result, Batch 4 → Batch 5 |
|---|---|---|
| Pax Gallica? seed 19 | The Belgic March reaches Nervii. Enlist adds two German Warbands in Sugambri. | Aedui → Belgae |
| The Great Revolt seed 12 | After a March in Winter Campaign, Enlist Hides five German Warbands in Treveri. | Arverni → Aedui |
| Ariovistus seed 7 | Ariovistus accompanies the Control move to Sequani. Two Warbands from Sugambri also move to Treveri, one step toward him. | Aedui → Romans |
| Gallic War seed 1 | Three Warbands in Cisalpina advance to Ubii to join the Leader after the two Control moves. | Aedui → Arverni |

In the legacy balance sample, 19 winners and 12 card counts change across
22 records. Aedui wins in The Gallic War fall from five of twenty to one
of twenty. This exceeds the 15-percentage-point band against the old
reference. The new baseline records the audited outcomes and agrees
with the independently run balance driver on all 100 games. The sample
measures regression behavior for these bots on fixed seeds.
