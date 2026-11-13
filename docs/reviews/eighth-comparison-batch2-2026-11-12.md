# Eighth comparison repairs, Batch 2 · 12 November 2026

Batch 2 closes BM8-01 and BM8-02. Four of the eleven audit groups are closed.
[Finding ledger](comparison-audit-round8-2026-11-12.json) ·
[Validation evidence](eighth-comparison-batch2-2026-11-12-evidence.zip)

Shaded Massed Gallic Archers applies one opening Loss when at least six
Arverni Warbands participate, whether they Attack or defend. Paid Battles,
fixed Event Battles, and the Arverni and Germans Phase Ambushes share the
same rule. Slingers fire in the selected Region first. Archers then use
the remaining participating Warbands and resolve the Loss before Retreat
and Attack. The affected owner can choose the absorbing piece through the
ordinary Battle casualty prompt.
[Massed Gallic Archers](../../Reference%20Documents/Card%20Reference#L271) ·
[Free actions](../../Reference%20Documents/Chapter%205#L77) ·
[Arverni Battle](../../Reference%20Documents/Ariovistus/Chapter%20A6#L112)

Stalwart protects a German participant from the opening Loss. Inflexible
cancels the unshaded Archers reduction when Germans defend against an
Arverni Attack. Live resolution and the applicable forecasts use the same
conditions. Both sides retain their normal effect against other opponents.
[German Phalanx](../../Reference%20Documents/Ariovistus/A%20Card%20Reference#L126)

If the opening Loss removes the last participant on one side, ordinary
combat ends before Reveal. Aquitani can still inflict its printed extra
Losses against a remaining defender. Legiones applies its automatic first
Legion removal once, including when Archers cause that first Loss.
Morasses keeps its printed Retreat, Counterattack, Citadel and visibility
exceptions. If the opening Loss ends a Morbihan Ambush, the projected
Warbands return to their physical origins with their current visibility.
[Legiones](../../Reference%20Documents/Card%20Reference#L14) ·
[Aquitani](../../Reference%20Documents/Card%20Reference#L247) ·
[Morasses](../../Reference%20Documents/Card%20Reference#L357) ·
[Morbihan](../../Reference%20Documents/Ariovistus/A%20Card%20Reference#L51)

## Verification

The tests used Python 3.12.14 against parent
`54e7eb89b75d7282febca16b672176d740d470bb`. The repaired Python source digest is
`dc70177dad775609cf18849dfe3c598be3b00cc892c0787ad4f348ad5f32ccd2` across 613 files.

| Check | Result |
|---|---|
| Full suite | 10,151 passed. |
| Directed cases | All 25 passed. On the parent, 13 reproduce the defects and 12 controls pass. The wider Battle and compatibility selection passed all 175 tests. |
| Saved decision | A Roman opening casualty choice can pause a fixed Event Battle, save and reload, and replay to the same result and board. |
| Audited bot games | All 120 completed with clean integrity checks, valid rankings and only legal-decline diagnostics. Final boards, winners, game lengths and diagnostics match the paired Batch 1 records. |
| Mixed-player replay | Twenty second-edition cases match at hash seeds 0 and 987 and agree with the paired Batch 1 records. Each run records 623 human turns, 152 Event attempts, 138 executed Events, and zero hard findings or partial plans. |
| Balance | The 100 legacy games pass the 15-point band. The two winner changes from the reviewed baseline are the Gallic War continuations from Batch 1. |

The bot comparisons use legacy seeds 1–20 and second-edition seeds 45–48
across all five scenarios. The mixed-player comparison uses second-edition
seeds 45–48. The controlled Battle tests establish the changed behavior at
the six-Warband threshold, with both German Phalanx sides, and in the listed
Event combinations. The paired game sample saw no changes to final outcomes.
