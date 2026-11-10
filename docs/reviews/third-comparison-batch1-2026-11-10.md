# Third comparison repairs, Batch 1 — 10 November 2026

Batch 1 repairs FE3-01, CM3-02, and CM3-04. The third-audit ledger now records
**3 of 15 groups repaired (20%), with 12 remaining**.

[Finding ledger](comparison-audit-round3-2026-11-10.json) · [Validation evidence](third-comparison-batch1-2026-11-10-evidence.zip)

## Corrected behavior

Human turns accept the chosen action and its player plan. The durable frontend
and raw turn coordinator validate that envelope, and the engine constructs its
execution record. Journal identifiers, responses, eligibility flags, and other
engine fields come from the engine. Extra authored fields leave the current
decision pending. A normal initialized-session test rejects both audited forms,
then accepts the corrected Recruit, preserves it through reactive pauses and
save/reload, marks Rome Ineligible after card 16, and verifies exact replay.

Saved turn responses are compared with their accepted action and plan before
resume or replay. The comparison uses their JSON representation so supported
older tuple-form March choices survive plain-JSON display history. A journal
containing contradictory accepted choices pauses with an explanation. A
constructed older conflict exercised both file commands and preserved board,
RNG, and committed history.

Entreat validates the named physical Ally disc before accepting an authored
turn and again before payment or removal. Taking Helvetii's disc beside a
Sequani Citadel clears Helvetii's allegiance and leaves Sequani's Citadel and
allegiance consistent. Both terminal menu paths select eligible discs. The
replacement still follows Available-piece and stacking rules, including
removal when an Arverni counterpart is unavailable (§4.3.1).

Ordinary Battle rejects the four audited Event-only plan fields. The Battle
executor obtains printed Retreat prohibitions through an internal argument
from Joined Ranks, Vosegus, Sabis, and Admagetobriga. Specialized combined-force
and cohort paths retain their printed effects. Existing Event tests cover
permitted lender choices, first and second Battles, revised Joined Ranks,
Diviciacus consent, and A31 cancellation.

The supplied rules governing these repairs are Chapter 2 §§2.3.4–2.3.6,
Chapter 3 §3.1.2, Chapter 4 §4.3.1, Chapter 5 §§5.1.1 and 5.4,
Card Reference 54, and A Card Reference A21, A28, revised 54, and A57.

## Verification

| Check | Result |
|---|---|
| Full suite | 9,473 passed, zero failures, errors, or skips |
| New source-derived cases | 62 passed |
| Same new cases on audit engine | 58 failed and four positive controls passed |
| Audited all-bot games | 20 completed, clean audits, all records match the parent |
| Mixed-player cases | 20 match the parent and each other across hash seeds 0 and 987 |
| Mixed-player findings | Zero hard findings and four soft partial plans per hash run |
| Balance matrix | All 100 winners and game lengths match the parent |
| Balance guardrail | Passed the existing 15-point band |

All-bot and mixed-player samples use seeds 21–24 in all five scenarios with
the legacy edition profile. Mixed-player replay remains enabled, giving 80
executions across the two hash runs and their internal repeats. Each hash run
records 626 human turns, 146 Event attempts, and 130 executed Events. Their
complete JSON results match.

The balance comparison uses seeds 1–20 in all five scenarios. Both the parent
and this repair differ from the stored baseline in the same 31 winners. The
repair changes zero winners or game lengths relative to its parent. The
baseline file retains SHA-256 `207a62e367e31caec165617b8f62fb5f5b0af82a114c4aaf3aee39f140d37d46`.

The accepted source was the working repair tree over
`06487b417f0c32d3e0830ea453a00acb2a81978a`, with Python-source SHA-256
`42da33aca92ecd23c750e2ea17e29f3f71d50c66e2e50db03a0f325966c12069` across 579 Python files. The parent archive's
source digest is `7f75a00ebd5200960a71fa822bdfddb47f2e092f5edbf58c145f6f70a5db226e`.
Only `final3` supplies accepted integrated results. Earlier attempts retain
their test-double failures, raw-callback validation correction, tuple
compatibility investigation, and a corrected March test fixture. The archive
also preserves the audit-revision regression run and the parent matrices.

The original source documents and adopted rulings govern the repairs.
The ledger tracks the other twelve third-audit findings separately.
