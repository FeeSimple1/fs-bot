# Sixth comparison repairs, Batch 5 · 11 November 2026

Batch 5 closes the three bot forecast findings and completes all 14 repairs
from the sixth comparison audit.
[Finding ledger](comparison-audit-round6-2026-11-11.json) ·
[Validation evidence](sixth-comparison-batch5-2026-11-11-evidence.zip)

| Finding | Repaired behavior |
|---|---|
| NP6-01 | The Belgic and Arverni bots calculate Counterattack from the pieces that survive the Attack, using the flowcharts' assumption that defending Loss rolls remove pieces. Ambiorix's attacking Warbands each inflict one Loss. The Successor uses the ordinary rate. |
| NP6-02 | The Arverni Legion trigger checks whether a Loss reaches a Legion under the standing-Battle forecast. Aedui opening Battles check the legal loss tiers and possible Retreat. A defending player can use a Fort in the current tier to absorb the Loss and spare an Ally. |
| NP6-03 | The Roman bot uses the Rampage executor's Region and target checks and counts one victim per eligible Hidden Warband up to the available victim count. Three Hidden Warbands can reach a Legion behind two Auxilia. A Fort or an out-of-range Belgic Leader blocks that Rampage. |

[Battle Losses](../../Reference%20Documents/Chapter%203#L297) ·
[Belgae §8.5.1](../../Reference%20Documents/Chapter%208#L244) ·
[Aedui §8.6.2](../../Reference%20Documents/Chapter%208#L448) ·
[Arverni §8.7.1](../../Reference%20Documents/Chapter%208#L583) ·
[Romans §8.8.1](../../Reference%20Documents/Chapter%208#L785) ·
[Rampage §4.5.2](../../Reference%20Documents/Chapter%204#L223)

## Verification

Tests ran on Python 3.12.14 against parent
`e5ad1a6009286e8b1ae2dd749f319d476fb35f58`. The repaired Python source
SHA-256 is `2ae5b3cedb16cfed6969442ebe9fefba99ed0f03933cd30c78a4deb6c002e801`
across 602 files.

| Check | Result |
|---|---|
| Full suite | 9,991 passed. The 15 public bot regression cases all pass. Running them against Batch 4 produces nine failures and six passing controls. |
| Audited bot games | All 100 legacy and 20 second-edition games completed with four-faction rankings, clean inventories and structure, and only legal declines. Twelve reached the Interlude. |
| Mixed-player replay | Twenty second-edition cases matched byte-for-byte across hash seeds 0 and 987. Each run had 558 human turns, 153 Event attempts, 142 executed Events, zero hard findings and one partial plan. |
| Balance | All 100 winners and game lengths match the refreshed baseline. The 15-point guardrail passes. |

The four Aduatuci retry cases now use two Belgic Warbands to create a legal
Battle threat to the unescorted Legions. Removing those Warbands in the
Battle window still exercises both retry outcomes, with and without a
second legal Region.

## Paired outcomes and balance

The legacy matrix uses seeds 1–20 and the second-edition matrices use
seeds 41–44 across all five scenarios. The traces reproduce the Batch 4
outcomes and verify matching starting boards and RNG states at each first
divergence. Every changed final board first diverges on a card with a
changed Belgic or Arverni Battle comparison, Aedui high-value target check,
or Roman threat check.

| Edition | Games | Changed final boards from Batch 4 | Changed winners from Batch 4 |
|---|---:|---:|---:|
| Legacy | 100 | 70 | 35 |
| Second edition | 20 | 13 | 7 |

The earlier stored baseline showed the Belgae winning 25% of the Great
Revolt games. The repaired code wins 45% as the Belgae on those same 20
seeds. The 20-point change exceeded the 15-point band. Across the five
scenarios, 43 of the 100 winners differ from the earlier stored baseline.
The same-seed traces identify the changed bot checks, including the Roman
change from Battle to March on card 51 in Great Revolt seed 8. The refreshed
baseline uses the verified winners and game lengths for the same 100 games.
