# Seventh comparison repairs, Batch 1 · 11 November 2026

Batch 1 closes BM7-01 and BM7-02. Seven of the nine audit groups remain open.
[Finding ledger](comparison-audit-round7-2026-11-11.json) ·
[Validation evidence](seventh-comparison-batch1-2026-11-11-evidence.zip)

Fixed Event Battles use the same Slingers and Horse choices as planned
Battles. The shared path handles Legiones, Aquitani, Morasses, Numidians,
Camulogenus, Morbihan and the other single-Region grants that invoke Battle
directly. A third-party Roman can fire Slingers before the Attack. Morasses
uses its printed Citadel exception when displaying and applying the Horse
bonus. Aquitani adds its three extra Losses after the ordinary calculation.
[Event procedures](../../Reference%20Documents/Chapter%205#L25) ·
[Card 13](../../Reference%20Documents/Card%20Reference#L125) ·
[Card 25](../../Reference%20Documents/Card%20Reference#L247) ·
[Card 36](../../Reference%20Documents/Card%20Reference#L357) ·
[Card 59](../../Reference%20Documents/Card%20Reference#L602)

The Arverni Phase and other prospective Ambush queues share the one-use
capability windows. The Arverni Phase checks for later eligible Regions
without advancing the random Battle order. Romans can reserve Slingers
while a later candidate remains under provisional PR-13. Both new
Slingers entry points support pending choices, correction, save and resume,
and exact replay with the repaired rules. Older histories can encounter a
new decision or diverge at the corrected Battle.
[Arverni Phase](../../Reference%20Documents/Ariovistus/Chapter%20A6#L112) ·
[Provisional PR-13](../provisional-rulings.md#pr-13)

Stalwart uses the identity of the faction inflicting Losses to cancel
Ballistae's 1–2 Fort removal threshold. Forts taking German Attack or
Counterattack Losses use the ordinary 1–3 threshold. The directed controls
cover both directions, other attackers, and the permanent Provincia Fort.
[Stalwart](../../Reference%20Documents/Ariovistus/A%20Card%20Reference#L130) ·
[Ballistae](../../Reference%20Documents/Card%20Reference#L94) ·
[Ordinary Fort rolls](../../Reference%20Documents/Chapter%203#L326)

## Verification

Tests ran on Python 3.12.14 against parent
`5c1fdb002f3c98909f515e021958ecd16249608c`. The repaired Python source
SHA-256 is `c277de1a2afd03746f16a257867917bcf544e525b49ef1c1a44f2227595532e8`
across 604 files.

| Check | Result |
|---|---|
| Full suite | 10,011 passed, including all 20 new Battle cases. The parent reproduces 13 failures and passes seven controls. |
| Audited bot games | All 100 legacy and 20 second-edition games completed cleanly with legal declines, valid inventories and four-faction rankings. |
| Mixed-player replay | Twenty second-edition cases matched byte-for-byte across hash seeds 0 and 987. Each run had 558 human turns, 153 Event attempts, 142 executed Events, one partial plan and zero hard findings. |
| Balance | All 100 legacy winners match the reviewed baseline. The 15-point band passes with one changed game length. |

## Paired outcomes

The legacy matrix uses seeds 1–20 and the second-edition matrix uses seeds
41–44 across all five scenarios. Every changed final board first diverged
with the same starting board and RNG state. Five cases changed when
Slingers fired before an automatic or Morbihan Battle. Four changed when
Horse applied to a Battle that had skipped its choice.

| Edition | Games | Changed final boards | Changed winners | Changed lengths |
|---|---:|---:|---:|---:|
| Legacy | 100 | 7 | 0 | 1 |
| Second edition | 20 | 2 | 1 | 1 |

In second-edition Gallic War seed 44, Card 2 first diverges at Provincia.
Germanic Horse increases the Roman Counterattack from zero to one Loss.
Belgae win at card 97, where Arverni previously won at card 100. In legacy
Gallic War seed 15, Slingers remove three of twelve projected Warbands in
Morbihan, reducing the Attack from three to two Losses. Aedui still win,
at card 71 instead of 47. The balance check uses the original 100 seed
pairs and tolerance.
