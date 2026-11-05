# Devastate owner casualties — 4 November 2026

Client date: America/Chicago. Parent `9230d5dbafbd5b5d38909e51158028c868449e34`.
Tested working Python digest:
`74e4310e2a919068cfe64db4630968bcc2941f16223e0f64de0e3d9ef4b52cf7`
(494 Python files). The publishing commit includes this frozen source.

## Source and correction

Chapter 4 §4.3.2 removes one in four Arverni Warbands and one in three other
Factions' total Warbands/Auxilia/Legions, rounded down, with owners choosing
which candidates to remove and Legions going to Fallen. Leaders and static
pieces are not candidates. §8.4.1 removes own pieces in reverse priority:
Scouted before Revealed before Hidden soft pieces, ahead of Legions. A4.3
excludes Devastate from Ariovistus; the normal engine gate remains in place.

Previously, no live owner choice was requested. Generic soft-piece removal
silently used Hidden-first ordering. Supplied tuple lists could under-remove,
truncate excess casualties, or try ineligible piece types. The new
`devastate_losses` request gives each affected physical owner its exact count
and available type/visibility cohorts. A player can sacrifice a Legion instead
of Auxilia, or choose a particular Warband visibility. Every owner count is
frozen and every selected plan validated before any Region casualty or marker
mutation. Zero-loss owners are not prompted.

Positive integer quantities must sum to the exact rounded requirement and fit
both offered and live physical cohorts, including aggregate duplicate entries.
The acting Arverni plan cannot substitute for another owner's response.
All removals use piece helpers; Legions go directly to Fallen without rolls.
Results keep grouped type totals and add physical removal details for authored
choices. The terminal supports bounded cohort quantities and board inspection.
Previews never consult live input. Invalid or missing durable responses retain
pending IDs, inbox, board/RNG and earlier accepted choices through whole-action
rollback/save/resume, including a pause in a second Region. Accepted choices
replay without applying the first Region twice.

## Compatibility and limits

Raw None or explicit delegation uses the source-required NPC priority. That
corrects a real default visibility defect and can change future trajectories;
it is not bot tuning. The older grouped `removed` result shape remains for
pure defaults. Trusted pre-authorized tuple maps remain available to low-level
callers, now with exact totals and whole-map validation before any removal.
An explicitly supplied soft-piece None visibility retains its legacy H/R/S
selection semantics; named human responses always specify a physical cohort.

Ordinary Devastate actor plans select Regions while each physical owner answers
its own casualty request. Existing Region eligibility and Command timing remain
unchanged. CV-PERSISTENCE, ordinary Battle casualty/Retreat choices, full
Rampage victim choice, NPC Intimidate targeting and other open findings retain
their dispositions. No new provisional interpretation is introduced. All 47
references, canonical constants and the balance baseline are protected (49 inputs).

## Validation

**8,048 tests pass** in the final full suite (215.61 seconds), with zero failures, errors or skips. **283 targeted tests pass**. **283 targeted tests pass**, including 50 new cases.
Coverage includes all five physical owner Factions, type/visibility choice,
Legions to Fallen, exact rounding, protected pieces, default priority,
malformed/duplicate casualty capacity, whole-map validation, terminal
inspection/EOF, preview isolation, Ariovistus exclusion, actor/victim ownership
and two-Region pending save/resume with identical replay.

An isolated parent runs the unchanged new test file through existing APIs:
five behavioral failures reproduce missing owner prompts and wrong NPC
visibility priority; two controls pass, with 43 other cases deselected. Missing
new helper APIs are not counted as proof.

Ten native-bot games cover all five scenarios and seeds 1–2. Mixed-seat matrices
use that seed set, hash seeds 0/987, reactions, Events and internal replay (40
executions total). All ten native-bot records complete and audit successfully, with no errors or
integrity findings, four ranked factions, consistent winner/ranking fields and
nonempty final hashes. Every gameplay field and final hash matches the parent;
only elapsed seconds, commit and source digest are excluded from comparison.
Both mixed-seat outputs agree in complete JSON across hash seeds: 247 human
turns, 77 Event attempts, 75 successful Events, zero hard findings, zero partials,
batch digest `5dd20da48e8e672b`. Internal replay makes 40 executions in total. The 100-game balance smoke
passes the unchanged historical baseline and 15-point band, with a largest
absolute win-rate difference of 15 percentage points and 35 winner changes
versus that historical baseline. These are not 35 changes versus the parent. The 100-game balance
smoke retains seeds 1–20, all five scenarios, the unchanged historical baseline
and a 15-percentage-point band. That historical comparison is not a
parent-vs-current comparison or a full rules-compliance proof.

## Progress

CMD-DEVASTATE-LOSSES closes one original finding: **31/50 closed (62%), 19 open**.
Related default-priority and trusted-plan validation corrections do not add to
the original denominator. The separate defects, 34 unverified inventory rows,
two source questions and twelve provisional rulings retain their dispositions.

[Machine-readable results](devastate-losses-2026-11-04-results.json) ·
[Evidence archive](devastate-losses-2026-11-04-evidence.zip)
