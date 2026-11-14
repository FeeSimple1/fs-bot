# Eleventh comparison repairs, Batch 2 · 13 November 2026

Batch 2 closes BM11-01. Four of the eight eleventh-audit findings are closed.
[Finding ledger](comparison-audit-round11-2026-11-13.json) ·
[Validation evidence](eleventh-comparison-batch2-2026-11-13-evidence.zip)

Unshaded Divination applies the Aedui bot's Battle condition to the actual
German force. Both the Battle decision and target priority use the shared
Aedui forecast. It checks whether defenders can avoid a Loss on a Leader,
Legion, Ally, Citadel or Settlement by standing or by making a legal Retreat.
Divination's Battle has no Ambush.
[Divination](../../Reference%20Documents/Ariovistus/A%20Card%20Reference#L146) ·
[Event-driven actions §8.2.3](../../Reference%20Documents/Chapter%208#L105) ·
[Aedui Battle §8.6.2](../../Reference%20Documents/Chapter%208#L448)

In the audit position, the Belgae can stand in Carnutes, remove two Warbands
and roll to absorb the third Loss with Abatis. The Aulerci Ally survives
either die result. The Aedui bot now orders a free German March in this
position, both with Ariovistus and ten Warbands and with twelve Warbands
alone. If an Arverni Ally is also in Carnutes, the bot Battles the Arverni
because a Loss on their Ally is guaranteed. With Abatis canceled by
Stalwart, the existing controls still Battle the Belgae and remove Aulerci.
[Abatis](../../Reference%20Documents/Ariovistus/A%20Card%20Reference#L288) ·
[Germanic Battle §A3.4.4](../../Reference%20Documents/Ariovistus/Chapter%20A3#L118) ·
[Defender Loss choices §3.2.4](../../Reference%20Documents/Chapter%203#L311)

## Verification

Python 3.12.14 tested the repair to parent
`52821136c4aa07d2df79dee48edbb1ec09945c12`. The repaired Python SHA-256 is
`4bb6812831b996cdb8941c6684650ff1e6661e5db0963bd1733f802188711a31` across
628 files. All 47 supplied references and the canonical constants match
the audit hashes.

| Check | Result |
|---|---|
| Public Event witness | The parent reproduces the six audit cases byte for byte. The repair changes the two active-Abatis Battle choices to March and reproduces the four controls. All six repaired cases match at hash seeds 0 and 987. |
| Directed regressions | The parent fails the three new tests and passes six existing controls. All 52 related tests pass on the repair at both hash seeds. |
| Full suite | 10,423 pass with five external anyio/pytest deprecation warnings. |
| Audited bot games | All 120 complete across five scenarios on legacy seeds 1–20 and second-edition seeds 57–60. All 1,999 diagnostics are legal declines. Nine games reach the Interlude. Every final state, ranking and card count matches Batch 1. |
| Mixed-seat replay | All 20 second-edition cases on seeds 57–60 match across hash seeds 0 and 987 and match Batch 1. Zero hard findings and four partial plans. |
| Balance | The 100-game check passes with the existing 15-point tolerance. All winners and card counts match the reviewed Batch 1 baseline. |
