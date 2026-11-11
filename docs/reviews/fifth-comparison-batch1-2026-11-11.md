# Fifth comparison repairs, Batch 1 · 11 November 2026

Batch 1 closes three of the fifth audit's eleven findings. [Finding ledger](comparison-audit-round5-2026-11-11.json) · [Validation evidence](fifth-comparison-batch1-2026-11-11-evidence.zip)

| Finding | Repaired behavior |
|---|---|
| BE5-01, Capability recipients | The executor names a Gallic recipient before shaded Ballistae or Winter Campaign takes effect. A missing or invalid human choice leaves the turn pending. A Gallic Non-player selects itself under §8.2.3. |
| BE5-02, Colony geography | Colony requires a playable Region under the executor's Control or with No Control. The terminal and Non-player planner use that same rule. The Tribe still forms when the Ally supply is empty. |
| BE5-03, Forced Marches geography | Forced Marches accepts Roman movement into and out of Cisalpina with Gallia Togata in effect. It reads both the regional marker and the legacy saved representation. The move endpoints follow the acting Faction's stacking restrictions. |

Cards 10 and 63 assign their shaded effects to a Gallic Faction. A legal
gift can go to Arverni, Aedui or Belgae. Playing the unshaded side clears
the shaded recipient. The terminal presents the recipient choice on the
shaded side. Preview and durable submission validate that choice before
activation. The durable test corrects a rejected choice under the same
decision ID after saving and reloading.

Card 71's stacking exception permits the new Tribe circle in an eligible
Region. Card 32 selects playable Regions other than Britannia. Cisalpina
follows the live scenario and Gallia Togata rules for both Events. The
printed instructions are in [Card Reference](../../Reference%20Documents/Card%20Reference),
[Chapter 1](../../Reference%20Documents/Chapter%201),
[Chapter A1](../../Reference%20Documents/Ariovistus/Chapter%20A1),
[Chapter 5](../../Reference%20Documents/Chapter%205) and
[Chapter 8](../../Reference%20Documents/Chapter%208).

## Verification

Tests ran on Python 3.12.14 with parent
`9257837240f9cf78d39feb553a6419d73b708f6e`. The tested Python source
SHA-256 is `b3e251be9d703fada9c38235f04e4f69b772cebb2d49def2bc2156090054b8c9`
across 592 files.

| Check | Result |
|---|---|
| Full suite | 9,837 passed. |
| Focused checks | 447 passed. The 31 new cases include 26 expected failures and five passing controls on the parent. All 31 pass on the repair. |
| Capability effects | A Roman gift to Belgae produces their Ballistae choice after Ambush and their Winter Campaign choice at the after-Harvest handler. The Battle removes the selected Citadel. Both boards pass inventory and structure checks. |
| Audited bot games | All 100 legacy and 20 second-edition games completed with valid four-faction rankings, clean inventory and structure, and zero nonlegal diagnostics. Each game matches the parent in final board, ranking, winner and card count. |
| Mixed-player replay | Twenty second-edition cases match byte for byte across hash seeds 0 and 987 with internal replay. Each run records 772 human turns, 171 Event attempts, 161 executed Events, zero hard findings and two partial plans. |
| Balance | The 100-game check passed the existing 15-point band. The largest shift against the stored baseline was five percentage points. The five Gallic War winner changes match the preceding Interlude repair's comparison to that baseline. |

Legacy seeds 1–20 and second-edition seeds 29–32 cover all five scenarios.
The paired comparison uses the fourth repair batch's legacy records and the
fifth audit's second-edition records. Both parent matrices have the parent
Python source digest `31e50801e3a187cf7c9def52e09df7ef5b39a895f55d32a4abfe0a08a42d2341`.
Ten bot games reach the Interlude across the two profiles. Both mixed runs
complete all 20 distinct cases, with 80 game executions including internal
replays and the second hash seed.

An older test fixture had sent a human gift through the bot executor. The
corrected fixture exercises player gifts through `player_action` and bot
self-selection through `bot_action`. The evidence contains the initial
full-suite failure and the final results with their respective source
identities.
