# Fourth comparison repairs, Batch 3 · 11 November 2026

[Finding ledger](comparison-audit-round4-2026-11-10.json) ·
[Validation evidence](fourth-comparison-batch3-2026-11-11-evidence.zip)

| Finding | Repaired behavior |
|---|---|
| BM4-01, Motivation | Shaded A33 adds one Counterattack Loss if a German defender survives. A surviving Warband, Ally, or Settlement can qualify even if it contributes less than one Loss under the ordinary formula. |
| BM4-02, non-player Retreat | The bot compares the two stances using the Battle resolver on a copy of the board. It checks whether the last defending piece can survive, whether Roman Legion rolls decrease with refuge, and whether the survivors can guarantee half the Losses suffered. Without refuge, it evaluates whether defenders can stay under the Roman Battle exception. An active Abatis acts as a Fort for this calculation. A31 cancels its protection and its casualty roll where applicable. |
| NP4-01, Roman targeting | Roman Battle and March priorities count each Germanic Settlement as one Ally in Ariovistus. The Roman March ranking counts Settlements anywhere on the map, including those outside the reachable destinations. |
| NP4-02, Diviciacus | Both Aedui Battle priorities allow projected Counterattack Losses equal to the number of supporting Warbands and Auxilia. This includes a lone Diviciacus facing zero projected Losses. |

The controlling sources are §§3.2.4, 3.3.4, 8.4.3, 8.6.2, 8.8.1,
A3.2.4, A8.6.2 and A8.8.1, and expansion Cards A31, A33 and A64.
The Retreat forecast uses worst-case saving rolls to test survival.
Without a destination it also checks whether a successful save could
leave a piece that must be removed during Retreat. The forecast consumes
no live dice or player responses.

## Verification

Tests ran on Python 3.12.14 with parent
`37a087d5c37671c1f1109ccdbbcb0136c216cb5b`. The tested Python-source
SHA-256 is `82bb5f648cbfcd83fc35302435d0c4a7fcddb5ea9de947bd424dfcd510983bc5`
across 590 files.

| Check | Result |
|---|---|
| Full suite | 9,794 passed, including 17 new cases. |
| Parent regression run | Eight failures and 18 passing controls. The failures reproduce all four findings and the Abatis cancellation discrepancy. |
| Audited bot games | All 100 legacy games and 20 second-edition games completed with full rankings, zero integrity findings and zero nonlegal diagnostics. |
| Mixed-player replay | Twenty second-edition cases match across hash seeds 0 and 987. Both runs have zero hard findings and one soft partial plan. |
| Balance on the reviewed baseline | All 100 winners and game lengths match. |

## Paired game outcomes

The 100 legacy games use seeds 1–20 in all five scenarios. Thirty winners
differ from the parent. Nine winners differ in 20 second-edition games,
which use seeds 25–28 in all five scenarios. Every paired trace starts
from an identical board at the first differing draw.

| First difference | Changed winners |
|---|---:|
| Non-player Retreat declaration | 29 |
| Roman March target or availability | 9 |
| Motivation Counterattack after the last German piece is removed | 1 |

In The Great Revolt seed 8, eight Roman Legions would wipe out six
Hidden Belgic Warbands in Mandubii. The Belgae now Retreat and two
Hidden Warbands survive in place. In Ariovistus seed 3, the Romans
target Germanic Settlements in Treveri and Cisalpina on draw 42.
In The Gallic War seed 17, Aedui Battle removes the last German
Settlement in Treveri and the eliminated defenders inflict zero Losses.

Against the previous balance baseline, 36 winners changed and 49 records
changed in winner or duration. The Great Revolt's Arverni rate rose from
7/20 to 11/20, exceeding the 15-point guardrail. The three-seed canary
also flagged the Reconquest of Gaul. The reviewed refresh uses the same
100 game keys and the same guardrail. The archive includes both baselines,
the failed comparison against the previous baseline, and the paired traces.

Fourteen of sixteen findings in the fourth comparison are closed. Its
remaining findings concern the Gallic War Interlude's deck and Nori Tribe.
