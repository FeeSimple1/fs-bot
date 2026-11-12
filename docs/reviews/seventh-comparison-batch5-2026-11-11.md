# Seventh comparison repairs, Batch 5 · 11 November 2026

Batch 5 closes NP7-01 and NP7-02. All nine findings in the seventh audit
are closed.
[Finding ledger](comparison-audit-round7-2026-11-11.json) ·
[Validation evidence](seventh-comparison-batch5-2026-11-11-evidence.zip)

Belgae, Arverni, and Germans now forecast legal Ambushes while evaluating
Battle targets. The first affordable selected Battle determines whether
the Command uses Ambush. The opening test checks whether a Counterattack
could inflict a Loss or a Retreat out of the Region could spare pieces.
Later Battles use the Ambush forecast only when the opening Battle chose
Ambush and their own Hidden forces and Leader proximity qualify. Defending
Caesar can still Counterattack in the forecast. A threatened Leader must
have a Battle in the selected plan for the Command to proceed.
[Belgae](../../Reference%20Documents/Chapter%208#L244) ·
[Arverni](../../Reference%20Documents/Chapter%208#L583) ·
[Germans](../../Reference%20Documents/Ariovistus/Chapter%20A8#L78) ·
[Ambush](../../Reference%20Documents/Chapter%204#L138)

All four Raid bots use the executor's Warband limit. Shaded Baggage
Trains gives its owner up to three Raiders in each Region, subject to
eligible Hidden participants and available Resources when stealing.
German free Intimidate counts the Warbands that actually Raided.
[Baggage Trains](../../Reference%20Documents/Card%20Reference#L75)

## Verification

Tests ran on Python 3.12.14 against parent
`a0f58ad97b6b9fd38a64472f6e8747609f78be2e`. The repaired Python source
SHA-256 is `3c047ebcfef915efef8e1da308cd63484b1e6c735b8aba8e5c095de2c5d106b9`
across 611 files.

| Check | Result |
|---|---|
| Full suite | 10,116 passed. |
| Directed cases | 49 passed, including the retreat-refuge control. On the parent, 17 cases reproduce defects and 30 controls pass. The 17 original audit witnesses and controls were replayed before and after the repair. |
| Audited bot games | All 100 legacy and 20 second-edition games finished with clean integrity checks and valid four-faction rankings. |
| Mixed-player replay | Twenty second-edition cases matched byte-for-byte across hash seeds 0 and 987. Each run had 593 human turns, 160 Event attempts, 143 executed Events, two partial plans, and zero hard findings. |
| Balance | The refreshed baseline matches all 100 legacy winners and game lengths on the same seeds. The 15-point guardrail and 40-point canary pass. |

## Paired outcomes

The legacy matrix uses seeds 1–20 and the second-edition matrix uses
seeds 41–44 across all five scenarios. Every changed game reached its
first differing card with an identical board and RNG state.

| Edition | Games | Changed final states | Changed winners | Changed lengths |
|---|---:|---:|---:|---:|
| Legacy | 100 | 75 | 44 | 31 |
| Second edition | 20 | 15 | 7 | 3 |

Forty-two first differences come from declining Ambush on the same opening
Battle. Ambush enables Battle in 24 games, adds a Region or target to 18
existing Ambush plans, and accompanies three Battles that previously used
other plans. An added Ambush target creates one equal-choice roll. Skipping
an unaffordable Battle avoids another. Baggage Trains adds two Raiders in
Great Revolt seed 12, one each in Morini and Atrebates.

In Reconquest seed 1, the Belgae open the game with a four-Region Battle
with Ambush. They previously chose March with Enlist. Arverni win where
Belgae previously won. In Ariovistus seed 3, the first change occurs in
Winter. The Belgae add Morini to an Ambush plan that previously included
only Nervii. Germans win where Aedui previously won.

The prior baseline matched all 100 parent outcomes. The repaired games
move four win rates outside the 15-point band.

| Scenario | Faction | Prior | Repaired |
|---|---|---:|---:|
| Pax Gallica? | Romans | 75% | 55% |
| Pax Gallica? | Belgae | 5% | 25% |
| Reconquest of Gaul | Romans | 60% | 20% |
| Reconquest of Gaul | Belgae | 15% | 45% |

The three-seed Ariovistus canary also flags Aedui wins moving from two to
zero. After review of the first changed plans, the baseline refresh updates
51 outcome records, including 44 winners and 31 card counts. Both checks
retain their seed coverage and thresholds.
