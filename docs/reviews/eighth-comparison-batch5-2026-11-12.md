# Eighth comparison repairs, Batch 5 · 12 November 2026

Batch 5 closes NP8-01 and NP8-02, completing all 11 findings.
[Finding ledger](comparison-audit-round8-2026-11-12.json) ·
[Validation evidence](eighth-comparison-batch5-2026-11-12-evidence.zip)

The Aedui bot forecasts Counterattack from the forces that survive its
Attack. Additional Regions must yield at least one Loss and a favorable
exchange both standing and under any legal Retreat. The forecast uses the
selected Ambush, the available Resources, and the shared Battle mechanics.
It includes opening fire and the Region selected for Germanic Horse.
Conservative forecasts let defenders keep their saving rolls and allow an
opposing human to direct applicable opening Capabilities to the candidate
Region. Diviciacus's safety uses the same forecast. In the audit position,
four Aedui Warbands now Battle six Belgic Warbands after the Carnutes
Battle, inflicting two Losses and taking two against a standing defender.
[Aedui Battle](../../Reference%20Documents/Chapter%208#L448) ·
[Gallic Battle](../../Reference%20Documents/Chapter%203#L277) ·
[Diviciacus](../../Reference%20Documents/Ariovistus/Chapter%20A8#L53)

The Rally planner uses its detached, validated placements and remaining
Resources to forecast Trade or Suborn. The live executor still evaluates
the actual board and Supply declarations when the Special Ability resolves.
Aedui with no pieces and 10 Resources can now Rally one Hidden Warband,
then Suborn the home Ally and two Warbands, finishing with 5 Resources.
The completed Suborn is recorded as Command plus Special Ability for the
next eligible faction. Druids forecasts the Special Ability after its
retained one-Region Rally and applies the Event's free-action scope.
[Aedui Rally and Trade](../../Reference%20Documents/Chapter%208#L469) ·
[Druids](../../Reference%20Documents/Card%20Reference#L478)

## Verification

The runs used Python 3.12.14 against parent
`2a91f8104b1454bdbb9770d69ff7499cdaad250a`. The repaired Python source
digest is `57a94d20440986063d7f86224a6074fa0ea2ce471e58e24e9c5dd349ec799033`
across 616 files.

| Check | Result |
|---|---|
| Full suite | All 10,207 tests pass, including the 15-game balance canary. |
| Directed regressions | 29 cases. The parent fails 14 and passes 15 controls. |
| Focused suite | All 326 tests pass, including the directed cases. |
| Audited bot games | 120 games across all five scenarios complete with clean integrity checks, valid rankings, and legal-decline diagnostics. Eleven reach the Interlude. |
| Mixed-player replay | Twenty cases on second-edition seeds 45–48 match across hash seeds 0 and 987. The sample has 588 human turns, 142 Event attempts, 131 executed Events, zero hard findings, and zero partial plans. |
| Additional mixed sample | Fifteen second-edition cases on seeds 201–203 match across hash seeds 0 and 7. The sample has zero hard findings and the same two partial plans as the parent. |
| Balance | The existing 100-game baseline passes its 15-point band. The largest win-rate change is 10 points. |

The first full run exposed five older Diviciacus cases whose Battles fell
outside the revised favorable-exchange condition. A legal Retreat could
reduce some Attacks to zero. Another case counted on a three-Loss
Counterattack against a two-Loss Attack. Updated fixtures isolate
Diviciacus's safety using A33's Retreat restriction or a stronger Attack.
[Ariovistus Retreat](../../Reference%20Documents/Ariovistus/Chapter%20A3#L49) ·
[A33 Wailing Women](../../Reference%20Documents/Ariovistus/A%20Card%20Reference#L138)

## Paired outcomes

The bot matrices use legacy seeds 1–20 and second-edition seeds 45–48.
Each first changed board starts from matching board and RNG fingerprints.
Nine first change when the Aedui select a different set of Battle Regions,
including three under unshaded Surus. Eight first change when a Rally is
followed by Suborn or Trade. Four legacy winners and three game lengths
change. The separate balance runner agrees with the audited runner on all
100 winners and lengths. The current baseline stays in use.

| Edition | Games | Changed final states | Changed winners | Changed lengths |
|---|---:|---:|---:|---:|
| Legacy | 100 | 16 | 4 | 3 |
| Second edition | 20 | 1 | 0 | 0 |

| Legacy game | First changed board | Winner and length before → after |
|---|---|---|
| Gallic War 1 | Turn 81, Marcus Antonius (6). The Aedui skip the additional Battle in Aedui, where Retreat could reduce their Attack to zero. | Belgae, 120 → Aedui, 120 |
| Great Revolt 3 | Turn 23, Clodius Pulcher (14). The Aedui skip the additional Battle in Veneti, where Retreat could reduce their Attack to zero. | Aedui, 45 → Romans, 45 |
| Great Revolt 8 | Turn 24, Lucterius (19). Rally enables Trade for eight Resources. | Romans, 31 → Arverni, 31 |
| Great Revolt 14 | Turn 6, Surus (51). The free Command keeps its first Battle and skips the additional Battle in Mandubii. | Romans, 31 → Arverni, 46 |

Fourteen mixed-player trajectory digests change relative to the parent.
Twelve changes are in recorded Rally plans and leave every post-card board
equal. Two games first change boards when the Aedui Suborn after Rally,
including delegated Druids in Gallic War seed 203.
