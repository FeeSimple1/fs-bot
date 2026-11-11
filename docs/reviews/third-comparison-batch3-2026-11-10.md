# Third comparison repairs, Batch 3 — 10 November 2026

Batch 3 repairs BE3-01, BE3-03, BE3-04, EX3-01, and EX3-03. The third-audit
ledger now records **12 of 15 groups repaired (80%), with 3 remaining**.

[Finding ledger](comparison-audit-round3-2026-11-10.json) ·
[Source-derived expectations](third-comparison-batch3-oracle-2026-11-10.md) ·
[Validation evidence](third-comparison-batch3-2026-11-10-evidence.zip)

## Corrected behavior

| Finding | Result |
|---|---|
| BE3-01 — Consuetudine | The printed Ambush exception reaches candidate selection, reactive additions and the final combat check. German Scouted Warbands receive one hide attempt, clearing their marker while staying Revealed. The Event still skips March; ordinary Germans Phase Hidden-superiority requirements remain separate. |
| BE3-03 — Colony | Marker placement creates the Tribe even with no executing Ally Available. It remains Subdued if the Ally cannot be placed, contributes its Control Value and counts in Roman victory. Name collisions are rejected with or without supply. Default Region selection no longer disappears solely because the Ally pool is empty. |
| BE3-04 — Migration | A possible post-movement Ally is mandatory. A blocked Tribe cannot evade another legal circle in the Region. Movement remains legal when scarcity or the absence of a legal circle makes placement impossible. The terminal chooses on the post-move board after its reclamation window and records those timing choices. |
| EX3-01 — Harudes | Shaded placements use the shared exact-piece planner, with independent four-Warband and one-Settlement limits, attainable mandatory quantities, exact ordering and live timing. Later losses do not refill a completed placement quota. Only the surviving newly placed Warbands receive the free Raid. |
| EX3-03 — Nasua & Cimberius | Treveri replacement clears its Dispersed or Gathering status and the actual reminder, including the older set representation. An unavailable replacement does not preserve the displaced marker. Other Region markers remain in place. |

Harudes's terminal menu and German non-player default use the same placement
choices as execution. Its default places the Settlement first, then completes
the Warbands in that selected Region, following §§8.3.1/A8.3.1. Other non-player
factions retain their instructions and do not choose the German-only shaded
benefit through this default. Unshaded Harudes retains its separate validated
beneficiary choices.

The supplied authorities are Card Reference 53, 66 and 71; A Card Reference A29
and A35; Chapters 1 §1.4.3, 3 §3.4.4, 5 §§5.1–5.1.3, 6 §6.2, and 8 §8.3.1;
Chapter A8 §A8.3.1; and the scenario-specific non-player Event instructions.
Protected references and canonical constants are unchanged.

## Verification

| Check | Accepted result |
|---|---|
| Full suite | 9,582 passed; zero failures, errors or skips |
| New source-derived cases | 60 passed |
| Same cases on clean parent | 37 fail; 23 positive controls pass |
| Related Event suite | 1,139 passed |
| Audited bot games | 20 completed; zero audit failures; all winners and final-state hashes match the parent |
| Mixed-player cases | 20 match exactly across hash seeds 0 and 987 with replay enabled |
| Mixed findings | Zero hard findings; four soft partial plans per hash run |
| Balance | 100-game check passes the existing 15-point band; baseline unchanged |

The accepted working tree is over parent
`c6ed9dd43597cbe4958821c2474ed9e5f9fbb406`, with Python-source SHA-256
`407a932c9ded7d54facf434fff2c24c1e0837af3f565166ae51604ae0308851c`
across 582 Python files. All final integrated records use that source digest.

Bot and mixed samples use seeds 21–24 in all five scenarios, legacy card profile.
Internal mixed-player replay gives 80 executions across both hash runs. Each
hash run records 662 human turns, 155 Event attempts and 134 executed Events.
One mixed case changes from the parent, and the two new hash runs are identical.

The balance sample retains seeds 1–20 in all five scenarios. Three winners and
three game lengths change from the parent: Pax Gallica? seeds 11 and 15, and The
Gallic War seed 7. These deterministic changes remain within the existing band.
The baseline retains SHA-256
`5c14af61d455068527ed2032857192f849eb854b7e0bf4793d475e2974ab262a`.
No baseline, threshold or bot strategic priority was adjusted to obtain a pass.
Harudes's new default follows its printed mandatory quantities and placement order.

Fresh parent regressions use clean `c6ed9dd`. Parent game records come from the
preceding repair's accepted archive; its Python-source digest
`e0c0f1e5dd86bf95978cb6f3226c82d5e46859fb006424b7374f8137aa515f24`
exactly matches that parent. Complete game measurements use the named legacy
profile; source regressions also exercise original and second-edition cases.

The legacy Harudes grant tests now include the mandatory Settlement. Their
two-Warband Dread fixture uses actual supply scarcity, and the extra-Settlement
test checks atomic rejection. The Migration partial-execution fixture now blocks
both Pictones and Santones; leaving Santones Subdued would still permit the
mandatory Ally. A separate regression requires that legal alternative.

Earlier candidate and fixture-investigation results retain their own source
identities and are not combined with the accepted final records. The evidence
archive preserves the old failures, source-derived parent regressions, and the
final validation script.

## Remaining work

XC3-01, XC3-02 and EX3-04 remain: dynamic Colony consumers, permanent Razed
markers, and Stalwart's cancellation of Germanic Horse against Germans. The
earlier 50-finding and 21-finding ledgers remain closed. Separate Circumvallation
work and unresolved source questions retain their recorded dispositions.
