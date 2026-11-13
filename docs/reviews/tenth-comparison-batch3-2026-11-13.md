# Tenth comparison repairs, Batch 3 · 13 November 2026

Batch 3 closes LC10-01. Four of the nine tenth-audit groups are closed.
[Finding ledger](comparison-audit-round10-2026-11-13.json) ·
[Validation evidence](tenth-comparison-batch3-2026-11-13-evidence.zip)

Roman troops can now quarter directly in adjacent, undevastated Provincia
under Roman Control or with an eligible controller's Quarters agreement.
The engine checks all adjacent destinations and reserves the original
pieces before moving them. This lets a Legion and Auxilia move together
even if their arrival removes the host's Control. Supply Lines are fixed
after the entire adjacent step, then Legions and Auxilia can transfer to
Provincia from supplied Regions. The Roman Leader can transfer from anywhere.
[Base Quarters §6.3.3](../../Reference%20Documents/Chapter%206#L84) ·
[Ariovistus Quarters A6.3.3](../../Reference%20Documents/Ariovistus/Chapter%20A6#L139)

The terminal offers adjacent Quarters and Supply transfer as separate
Provincia choices. Assistant plans can append the corresponding step to
a relocation row. Untagged moves retain the Supply transfer when the
declared adjacent moves leave a possible Supply route. This preserves
plans that depend on the departing troops keeping a Supply Region open
until the later step. If no Supply route is possible, an eligible untagged
move can use adjacent Quarters. The default Roman planner also uses the
direct route for unsupplied troops when allowed.
[Assistant Quarters plans](../../AGENT_INTERFACE.md#quarters) ·
[Non-player Roman Quarters §8.8.7](../../Reference%20Documents/Chapter%208#L974)

In the audit's Pax Gallica position, the Roman Legion in German-controlled
Arverni reaches Aedui-controlled Provincia after a Quarters declaration.
The full first Winter completes with its Victory and Germans skips.
The directed cases also cover host refusal, ineligible and Devastated
destinations, exact Auxilia visibility, preserved Supply corridors,
restrictions on arriving pieces, and save/resume with separate declarations.
The saved-session case uses one Aedui-controlled Region. The multi-Region
Supply-request replay defect remains open as UI10-03 in Batch 4.

## Verification

Python 3.12.14 tested the repair to parent
`6faed3125b53959bada75eb368947eda7f04d99a`. The repaired Python source
SHA-256 is `2e12f8ee077efec1d87e9b0d2661c078619b4fc3ea22c31eceae69aa51ae177c`
across 623 files. All 47 supplied reference documents and canonical
constants match their audit hashes.

| Check | Result |
|---|---|
| Directed cases | 21 pass at each of hash seeds 0 and 987. The parent fails 12 of 19 cases that exercise the untagged plan format and passes seven controls. |
| Related Quarters and Winter tests | 176 pass. |
| Full suite | 10,329 pass, including the balance canary. |
| Audited bot games | All 120 finish with valid rankings and clean conservation and structural checks. All 2,041 diagnostic occurrences are legal declines. The sample covers all five scenarios on legacy seeds 1–20 and second-edition seeds 53–56. |
| Mixed-seat replay | All 20 second-edition cases match across hash seeds 0 and 987 and match Batch 2. One soft partial plan recurs. Zero hard findings. |
| Balance | The 100-game check passes. The largest winner-share difference from the reviewed baseline is 10 percentage points against the 15-point band. |

All winners match Batch 2. Three legacy games have different final boards.
Paired traces reach identical boards and RNG states before the first
changed Roman Quarters decision.

| Scenario and seed | First changed Quarters | Resolved cards |
|---|---|---|
| The Great Revolt 3 | Winter 2. Two Auxilia from Arverni take the direct route to Provincia, skipping the hop through Bituriges. | 45 → 45 |
| Ariovistus 16 | Winter 1. Two Legions from Arverni and one from Cisalpina take the direct route to Provincia, saving two Resources in Cisalpina. | 43 → 30 |
| The Gallic War 16 | Winter 1. The same three Legions use the direct route and save two Resources in Cisalpina. Belgae win before Interlude. | 85 → 30 |
