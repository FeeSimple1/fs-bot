# Seventh comparison repairs, Batch 2 · 11 November 2026

Batch 2 closes WS7-01. Six of the nine audit groups remain open.
[Finding ledger](comparison-audit-round7-2026-11-11.json) ·
[Validation evidence](seventh-comparison-batch2-2026-11-11-evidence.zip)

The Winter engine now executes non-Roman bot Quarters plans in faction
order. Belgae, base-game Arverni, and Ariovistus Germans leave unprotected
Devastated Regions for adjacent safe Regions they Control. Aedui only
evacuate and can use eligible foreign Control with consent. The existing
agreement window can suspend for a human host and reuse the answer when
executing the move. The save-and-resume tests cover consent, refusal, and
exact replay. Older replay histories can encounter a new agreement or
diverge at the corrected Winter.
[Base Quarters](../../Reference%20Documents/Chapter%206#L64) ·
[Ariovistus Quarters](../../Reference%20Documents/Ariovistus/Chapter%20A6#L125) ·
[Aedui priorities](../../Reference%20Documents/Chapter%208#L559)

After evacuation, Belgae, Arverni, and Germans can move the Leader and
one Warband group, including from separate origins. The planner chooses
the largest reachable Warband stack, then considers proximity to friendly
Forces. For an increase tied on stack size in Ariovistus, the Belgae
prefer Morini, Nervii, or Treveri over proximity. The planner leaves a
Warband at any consolidation origin that sends Warbands and retains
existing Control during consolidation. It reserves the original piece
cohorts, so evacuation arrivals cannot relocate a second time.
[Belgic priorities](../../Reference%20Documents/Chapter%208#L413) ·
[Arverni priorities](../../Reference%20Documents/Chapter%208#L767) ·
[Ariovistus Belgic priorities](../../Reference%20Documents/Ariovistus/Chapter%20A8#L46) ·
[German priorities](../../Reference%20Documents/Ariovistus/Chapter%20A8#L242)

## Verification

Tests ran on Python 3.12.14 against parent
`8c76446ea746d68f9494bdb1baf2e0f858ad708e`. The repaired Python source
SHA-256 is `24870872dee301461d07ddef30e0c706f4e2817b3a43cc63bc385896478bbefd`
across 606 files.

| Check | Result |
|---|---|
| Full suite | 10,032 passed, including all 21 new Quarters cases. The parent reproduces 16 failures and passes five controls. |
| Audited bot games | All 100 legacy and 20 second-edition games completed with clean integrity checks and valid four-faction rankings. |
| Mixed-player replay | Twenty second-edition cases matched byte-for-byte across hash seeds 0 and 987. Each run had 553 human turns, 145 Event attempts, 132 executed Events, three partial plans and zero hard findings. |
| Balance | The previous baseline flagged two 20-point shifts. The rerun matches all 100 reviewed winners and game lengths with the original seed matrix and 15-point band. |

## Paired outcomes

The legacy matrix uses seeds 1–20 and the second-edition matrix uses seeds
41–44 across all five scenarios. Each changed game first diverged in
Quarters with the same pre-phase board and RNG state. In 100 games a bot
relocated pieces. In Great Revolt legacy seed 20, a tie-break kept the
Leader in Mandubii and advanced the RNG. Quarters desertion results changed
in 13 games at the point of first divergence.

| Edition | Games | Changed final states | Changed winners | Changed lengths |
|---|---:|---:|---:|---:|
| Legacy | 100 | 84 | 46 | 37 |
| Second edition | 20 | 17 | 9 | 9 |

In Great Revolt legacy seed 1, Vercingetorix and 23 Warbands evacuate
Treveri for Sequani in the first Winter. The parent rolled for all 23 and
removed eight. The Belgae also consolidate in Morini. Romans win at card
46 on the repaired revision, where Belgae previously won. In Gallic War
legacy seed 2, Ariovistus moves from Cisalpina to Ubii, and eight Warbands
join him from Sugambri. Aedui win where Romans previously won.

The full guardrail reported German wins rising from 20% to 40% in
Ariovistus and Roman wins falling from 65% to 45% in Gallic War. The first
suite run flagged only the balance canary. The paired trace and independent
balance run account for each changed record, so the baseline refresh updates
59 of its 100 records, including 46 winners and 37 card counts. The seed
coverage, 15-point band, and 40-point canary band remain the same.
