# Player Build Region order — 4 November 2026

Client date: America/Chicago. Parent `56a99cbf30f5692778b6371971940c3aaeff2a17`.
Tested working Python digest:
`1b860ce3d2df175c359dfedb25b016d0965f7efbb195804909e958738fcd1f81`
(482 Python files). The commit publishing this report includes this frozen
source; its own SHA cannot be embedded without changing that commit.

## Source and correction

Chapter 4 §4.1 gives the executing player choice of affected Regions and order,
selecting a Region only once. §4.2.1 resolves an optional Fort and then either
one Subdue or one Ally placement in each Region, using current Roman Control
including the new Fort. Chapter 8 §8.8.1 explicitly gives non-player Romans
all-Forts, then Subdue, then Allies. All 47 supplied reference files, canonical
constants and the balance baseline remain byte-identical to the parent.

Previously, both human collectors grouped choices by operation, and execution
ran all Forts first. With two Resources, an Ally selected in Sequani before a
Fort in Aedui lost its budget to that Fort. `build_plan.region_order` now carries
exact Region order while keeping the familiar category lists. The executor
completes each selected Region before the next. Both collectors emit this field;
the timing-aware collector previews the same evolving sequence without changing
the live board or RNG. Each timing operation retains its original category
index, even when Region order executes those indices out of numeric order.

Explicit orders must cover exactly the Regions with operations, uniquely, with
at most one Fort and one Tribe operation per Region. Validation precedes the
accompanying human Command. A multi-Region ordered plan under card 12 shaded is
rejected, not silently truncated. Invalid turn and standalone Event SA plans
remain pending across rollback and save/resume, retaining their decision IDs;
corrected responses execute and retain the accepted plan. Empty ordered plans
remain legal no-effect plans. Live resources, proximity, supply, Control, Tribe
identity, Seize exclusions and piece availability still govern each operation.

## Compatibility and limits

Plans without `region_order` retain grouped passes for existing controllers and
the published non-player procedure. Controllers must add the field to express
human order. No bot priorities, threshold, baseline or rules inputs were tuned.
This does not close the separate capability-selection finding BE-09, general
during-Command timing, CV-PERSISTENCE, full Rampage victim selection or the NPC
Intimidate targeting lead. The older collector's single-operation prompt remains
unchanged; the timing-aware collector already supports Fort plus Tribe.

## Validation

**7,840 tests pass** in the final full suite (247.08 seconds), with zero failures, errors or skips. **121 targeted tests pass**. There are 32 new regressions: resource budgets in both
editions, top-level/nested plans, Fort/Tribe timing indices, Subdue ordering,
legacy passes, malformed/duplicate plans, card 12, both collectors, save/load,
and durable turn/Event SA rejection and acceptance.

The parent proof runs the unchanged test file against an isolated parent
checkout: five behavioral failures reproduce the missing order and timing;
six controls pass, with 21 other cases deselected. An initial invocation from
the current checkout accidentally tested current imports; it was discarded and
rerun from the isolated parent directory. The evidence contains the accepted
parent run only. Earlier local full/matrix runs preceded the final four new
regressions; accepted evidence below uses the frozen digest listed above.

All ten native-bot records complete and audit successfully, with no errors or
integrity findings, four ranked factions, consistent winner/ranking fields and
nonempty final hashes. Every gameplay field and final hash matches the parent;
only elapsed seconds, commit and source digest are excluded from comparison.
Both mixed-seat outputs agree in complete JSON across hash seeds: 247 human
turns, 77 Event attempts, 74 successful Events, zero hard findings, zero partials,
batch digest `c7366266d0681cf4`. Internal replay makes 40 executions in total. Ten native-bot cases use
all five scenarios and seeds 1–2; mixed tests use seeds 1–2, both hash seeds
0/987, reactions, Events and internal replay. These small matrices are targeted
compatibility/determinism checks, not a new balance study or a full rules proof.

## Progress

CMD-BUILD-ORDER closes one original finding: **26/50 closed (52%), 24 open**.
The 34 unverified inventory rows, two source questions, twelve provisional
rulings and separately discovered defects are not absorbed into that count.

[Machine-readable results](build-order-2026-11-04-results.json) ·
[Evidence archive](build-order-2026-11-04-evidence.zip)
