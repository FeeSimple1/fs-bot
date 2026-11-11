# Third comparison repairs, Batch 4 — 10 November 2026

Batch 4 repairs XC3-01, XC3-02, and EX3-04, closing all 15 groups in the
third comparison audit. The earlier 50- and 21-finding ledgers remain closed.

[Finding ledger](comparison-audit-round3-2026-11-10.json) ·
[Source-derived expectations](third-comparison-batch4-oracle-2026-11-10.md) ·
[Validation evidence](third-comparison-batch4-2026-11-10-evidence.zip)

| Finding | Corrected behavior |
|---|---|
| XC3-01 — Colony | Live Region queries include the Colony's saved name and Region alongside printed Tribes. Seize, Build, Entreat, and Trade use the same identity in execution, human choices, and non-player plans. Shaded Acco and unshaded Procillus can replace the Colony Ally. Dispersal reduces Belgic Control Value under the ordinary Control rule. The Colony remains a non-City with no printed stacking restriction. Its recorded Region also works when its custom name matches a Tribe from a different scenario. |
| XC3-02 — Razed Cities | Seize skips Razed Cities for ordinary Forage and dispersal. An authored attempt to disperse one again rolls back. The permanent marker survives repeated Springs, while ordinary Dispersed markers still progress and clear. |
| EX3-04 — Stalwart | A31 shaded suppresses both sides of Germanic Horse when they would add Losses to Germans. Attack and Counterattack use the same restriction. The stored owner and Region selection stay intact, and Horse still works against other Factions or after Stalwart is removed. |

The shared live query replaces duplicated Colony enumeration in Recruit,
Rally, Suborn, and the Tribe display. The printed map query remains available
for scenario data. Source rules are Card Reference 23, 34, 59, and 71;
A Card Reference A19 and A31; §§3.2.3, 4.2.1, 4.3.1, 4.4.1, 5.1–5.3,
6.6, and 7.2; and the established A31 interpretation in `QUESTIONS.md`.
Protected references, canonical labels, and the balance baseline are unchanged.

## Verification

| Check | Accepted result |
|---|---|
| Full suite | 9,686 passed; no failures, errors, or skips |
| New cases on the repaired tree | 104 passed, covering both rule sets and all five scenarios where applicable |
| Same cases on the parent | 68 fail; 36 positive controls pass |
| Audited bot games | 20 complete, zero audit failures, no winner changes; one final-state hash changes |
| Mixed-player cases | 20 match across hash seeds 0 and 987 with replay, zero hard findings, four soft partial plans |
| Balance | 100 games pass the unchanged 15-point band; no winners change from the parent and one game length changes |

The accepted Python-source SHA-256 is
`fb0bbf5af4a7513bbac1157f17054948d2ec5b3724ab612296b10a1d017ea51b`
over 585 Python files, based on parent
`9c180986c5bde4f56c5a92e7ed2173bfc7603f82`. The new cases include a Colony
Seize paused after its Rally roll, saved, resumed, and replayed with the same
board, random state, and decision log. They also verify terminal choices and
non-player plans, exact costs, pool integrity, and foreign-Region refusal.

Bot and mixed samples use seeds 21–24 in all five scenarios. Each mixed run
has 662 human turns, 155 Event attempts, and 134 executed Events, and replays
each case. A single Great Revolt seed 23 mixed digest changes from the
parent, with the same completion status, turn counts, and findings. The paired
parent game records come from Batch 3's accepted archive; its source digest
`407a932c9ded7d54facf434fff2c24c1e0837af3f565166ae51604ae0308851c`
matches the clean parent checkout.

The balance sample uses seeds 1–20 in all five scenarios. Reconquest of Gaul
seed 1 is the only outcome difference: Rome wins in 46 cards instead of 59.
Paired replays match the board and random stream before the 44th card, 43
(Convictolitavis). On that card, the repaired Roman Seize in Atrebates also
Disperses the Subdued Colony. It earns 20 rather than 14 Resources there
and triggers its two Gallic Rally rolls. The updated random stream and
Resource total precede the earlier Roman win. The guardrail still sees the
three winner differences already present in Batch 3 versus its older baseline.

The [ledger](comparison-audit-round3-2026-11-10.json) is **15 of 15 closed**.
Separate Circumvallation persistence work and the open source questions retain
their prior dispositions.
