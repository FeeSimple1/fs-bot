# Tenth comparison repairs, Batch 2 · 13 November 2026

Batch 2 closes BM10-01. Three of the nine tenth-audit groups are closed.
[Finding ledger](comparison-audit-round10-2026-11-13.json) ·
[Validation evidence](tenth-comparison-batch2-2026-11-13-evidence.zip)

Battle forecasts use the same Abatis protection check as the resolver.
Stalwart German Phalanx cancels a defending enemy's Abatis effects against
German attackers. Ariovistus can then double Losses. An active Abatis, Fort
or Citadel blocks that doubling for the defender. When his doubling applies,
it increases Counterattack Losses even if the original attacker has a Fort
or Citadel.
[German Phalanx](../../Reference%20Documents/Ariovistus/A%20Card%20Reference#L126) ·
[Abatis](../../Reference%20Documents/Ariovistus/A%20Card%20Reference#L288) ·
[Battle Losses](../../Reference%20Documents/Ariovistus/Chapter%20A3#L52)

In the audit position, the Belgae place Abatis in Carnutes before the
Germans gain Stalwart. Divination then lets the Aedui bot command Ariovistus
and two German Warbands there. The old forecast gave two standing Losses or
one on Retreat, so the bot chose March. The corrected forecast gives four
standing Losses or two on Retreat. Both guarantee a Loss on the Aulerci
Ally, so the bot chooses Battle. Both public Event regressions remove that
Ally and leave the canceled Abatis marker on the board.
[Divination](../../Reference%20Documents/Ariovistus/A%20Card%20Reference#L146) ·
[Aedui Battle priorities](../../Reference%20Documents/Chapter%208#L448)

## Verification

Python 3.12.14 ran the tests on the repair to parent
`83e28d4e8f296ac0506552c9830dd26e0858f825`. The repaired Python source
SHA-256 is `9c5604c6ea038ced05ad35d4b67f7219b15be116f5c685acf178a8eea8a8b833`
across 622 files. The 47 supplied reference documents and the canonical
constants match their audit hashes.

| Check | Result |
|---|---|
| Directed regressions | Six pass. The parent chooses March in both canceled-Abatis cases and passes the four controls. The controls cover active Abatis, a real Citadel, absence of Ariovistus and absence of Abatis. |
| Related Battle and Event tests | 226 pass, including the directed cases and the existing Fort and Counterattack checks. |
| Full suite | 10,308 pass, including the balance canary. |
| Audited bot games | All 120 finish with clean integrity checks and valid rankings. Every final state, winner and card count matches Batch 1. The sample covers all five scenarios on legacy seeds 1–20 and second-edition seeds 53–56. |
| Mixed-seat replay | All 20 second-edition cases on seeds 53–56 match across hash seeds 0 and 987 and match their Batch 1 trajectories. The same partial plan recurs, with zero hard findings. |
| Balance | The 100-game check passes within the existing 15-point band. Its winners and game lengths match Batch 1 on all 100 seeds. |
