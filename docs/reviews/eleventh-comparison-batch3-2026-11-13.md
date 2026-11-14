# Eleventh comparison repairs, Batch 3 · 13 November 2026

Batch 3 closes LC11-01. Five of eight findings in the eleventh comparison
audit are closed.
[Finding ledger](comparison-audit-round11-2026-11-13.json) ·
[Validation evidence](eleventh-comparison-batch3-2026-11-13-evidence.zip)

At the Gallic War Interlude, the German bot randomizes Regions for Arverni
Ally and Warband removals, with the Arverni Region last. Veneti, Carnutes
and Pictones enter the same draw as other Regions outside Arverni. The bot
can take the Cadurci and Volcae Ally discs early. The same Interlude priority
governs the human allocation and the bot fallback.
[Interlude rules](../../Reference%20Documents/Ariovistus/A%20Scenario%20-%20The%20Gallic%20War#L24) ·
[Arverni adjustment](../../Reference%20Documents/Ariovistus/A%20Scenario%20-%20The%20Gallic%20War#L53)

## Verification

The published parent is `fbd3126290df2794593847c9a4f4e30a6dfe97d3`. Local
matrix logs record `5c7171a123571ea036351d7651ba0c51203b1591`, which
has the same Git tree as the published parent. Validation used Python
3.12.14 and a repaired Python source SHA-256 of
`c22251669bf85ddc8726ffeb16b94f373be09abae5f10af6ae80ee41f02746c0`
across 628 files. The 47 supplied references and canonical constants
match the audit hashes.

| Check | Result |
|---|---|
| Public Interlude witness | The parent reproduces all 54 audit cases. With the repair, each of the three Regions is selected ahead of Sequani on seven of twelve seeds. The 18 ordinary-Region, Arverni-last and human-choice controls agree with the parent. The repaired observations match at hash seeds 0 and 987. |
| Directed regressions | The parent fails the three new cases and passes two priority controls. The repair passes 233 Interlude tests at each hash seed. The new tests cover both Allies and Warbands, exact quotas, and Gergovia restoration and reinforcement. |
| Full suite | 10,426 pass. The first run flagged the prior Interlude continuation digest and the balance canary. The final run uses the reviewed expectations below. |
| Audited bot games | All 120 complete across five scenarios on legacy seeds 1–20 and second-edition seeds 57–60. Nine reach the Interlude. All 1,983 diagnostic occurrences are legal declines. Nine end-state digests change, all in games reaching the Interlude. |
| Mixed-seat replay | All 20 second-edition cases match across hash seeds 0 and 987 with zero hard findings and four partial plans. Only The Gallic War seed 59 changes from Batch 2. Its German seat uses the bot, which removes one Warband from Carnutes and seventeen from Sequani. The parent takes all eighteen from Sequani. |
| Balance | The previous 100-game baseline passes the 15-point band. The 15-game canary flags a change because the Gallic War winners on all three of its seeds change. The reviewed baseline records four changed winners and four changed card counts across six games. Both checks pass with their existing seeds and thresholds. |

## Paired game outcomes

The trace captures identical boards and RNG before the Arverni adjustment
in all ten changed bot and mixed-seat cases. The same quantities are
removed on both revisions. In legacy seed 5 the board after adjustment
matches and the merged draw changes the RNG position. In the other nine
cases different cohorts remain on the board.

| Legacy Gallic War seed | Batch 2 winner | Batch 3 winner | Cards, Batch 2 → Batch 3 | Difference in Arverni Warband removals |
|---|---|---|---|---|
| 1 | Arverni | Aedui | 101 → 85 | Two Veneti and one Pictones Warband replace three removals in Cisalpina. |
| 2 | Romans | Belgae | 83 → 83 | One Carnutes Warband replaces one removal in Veneti. |
| 3 | Romans | Belgae | 70 → 69 | Ten Carnutes Warbands and one Cisalpina Warband replace eleven removals in the Aedui Region. |
| 17 | Aedui | Romans | 70 → 70 | Thirteen Carnutes Warbands replace eleven removals in Mandubii and two in Sequani. |

Legacy seeds 5 and 12 also have different card counts. The new reference
matrix uses all 100 paired games.

## Saved game continuation

The archived third-Winter fixture loads to the same board and passes the
post-Interlude inventory and structure checks. The reduction still returns
twelve Warbands to Available. The three extra Warbands taken from Mandubii
leave ten in Atrebates where the prior continuation left seven. The save
and generator hashes match the original manifest. The manifest retains the
prior continuation digest and records the new digest, reproduced at both
hash seeds.
[Fixture manifest](../../fs_bot/tests/fixtures/compatibility_8ef88e2/manifest.json)
