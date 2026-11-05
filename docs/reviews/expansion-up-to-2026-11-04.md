# Expansion optional-quantity batch — 4 November 2026

Client date: America/Chicago. Parent `feaed4bce9f1be8ebe2a514f074332958e091ee6`.
Tested working Python digest:
`e81fb7e8e9c8db1965ce44ebcb13b4f3d40f6d6507341ada0a0b6d6d25652c58`
(498 Python files). The publishing commit includes this frozen source.

## Sources and repairs

A Card Reference A40 shaded drains five Roman Resources for each of **up to
three** non-Roman-Control Regions within one of Cisalpina, then stays Eligible.
A51 unshaded, if Remi is a Roman/Aedui Ally or Subdued, places four Auxilia or
Aedui Warbands and a Fort, then removes **up to six** Belgic Warbands there.
A60 unshaded places the Roman Ally at Remi and **up to four** Auxilia there,
adding two Roman Resources for each unplaced piece. Chapter 5 §5.1 gives the
executor all selections unless otherwise specified; §5.1.1 retains Available
forces and the 45-Resource cap; §5.1.3 requires partial execution within those
selections. Chapter 8 §8.4.1's enemy-removal priority is Hidden/Revealed/Scouted.

Previously all three optional quantities silently used their maximum. A51
also omitted Scouted Warbands entirely. The batch adds one `event_up_to`
request owned by the executor and three authoritative shapes:

- A40: an exact list of zero to three distinct eligible Regions. Zero still
  receives Stay Eligible, and the drain stops at zero Roman Resources.
- A51: exact Hidden/Revealed/Scouted removal counts totaling zero to six.
  The compulsory troop/Fort prefix executes before the live request.
- A60: zero to four Auxilia. The Ally prefix executes first, and actual
  unplaced Auxilia plus any unavailable Ally independently yield Resources.

The same choices may be authored in Event parameters as `regions`,
`warband_removals`, or `auxilia_count`. Invalid quantities, wrong-side keys,
ineligible Regions, duplicate Regions and aggregate cohort overclaims reject
atomically. Live validation checks both offered and present physical cohorts.
A60 authored quantities are targets capped by Available forces on execution;
compensation counts actual placements. Terminal choices use current availability.
Existing action windows remain before Fort/removal/Auxilia/resource operations.
Reclamation before placement is honored; stale cohorts after timing reject.

## Frontends, defaults and limits

Terminal planning collects A51's compulsory troop type and leaves quantities
for their actual live board. Every live prompt supports board inspection.
Durable missing/invalid input retains pending identity and compulsory-prefix
board snapshots while rolling the whole Event back. Save/resume/replay applies
that prefix once. Previews consult no live agent or RNG. Existing transcripts
that omitted these decisions can require new responses.

Raw None or explicit default retains maximum behavior. A51 defaults now also
reach Scouted Warbands, in the existing H/R/S enemy priority. This corrects a
source defect and can change trajectories; it is not heuristic tuning. The
mixed-seat policy now exercises the new request shapes. Other sides of A40,
A51 and A60, broader BE-06/BE-07/EXP-11 Event work, ordinary Battle choices,
CV-PERSISTENCE and NPC Intimidate targeting retain their dispositions.
No new provisional interpretation is introduced. All 47 reference files,
canonical constants and balance baseline are unchanged (49 protected inputs).

## Validation

**8,191 tests pass** in the final full suite (429.60 seconds), with zero failures, errors or skips. **87 new cases** and **292 targeted tests** cover all
three optional effects, exact zero/partial/max selections, both expansion
scenarios, every playable executor, mandatory prefixes and Remi prerequisites,
Scouted/default removal, malformed/duplicate/stale cohorts, Resource floors/caps,
actual scarce placement and unavailable Ally refunds, live reclamation, preview
isolation, terminal inspection/EOF and durable invalid/missing save/resume with
identical replay after compulsory-prefix rollback.

An isolated parent runs the unchanged test file through existing engine APIs:
**17 behavioral failures** reproduce ignored authored quantities/physical choices
and omitted Scouted removals; **eight controls pass**, with 62 cases deselected.
All failures are behavior assertions, not missing new helper imports.

Ten audited native-bot games cover all five scenarios and seeds 1–2. Mixed-seat
matrices use those seeds, hash seeds 0/987, Events, reactions and internal replay
(40 executions total). All ten native-bot records complete and audit successfully, with no errors or
integrity findings, four ranked factions, consistent winner/ranking fields and
nonempty final hashes. Every gameplay field and final hash matches the parent;
only elapsed seconds, commit and source digest are excluded from comparison.
Both mixed-seat outputs agree in complete JSON across hash seeds: 247 human
turns, 77 Event attempts, 75 successful Events, zero hard findings, zero partials,
batch digest `5dd20da48e8e672b`. Internal replay makes 40 executions in total.
The focused regressions explicitly exercise the new request; unchanged mixed
outcomes alone do not establish that those particular Events were reached.

The 100-game historical balance smoke uses all five scenarios, seeds 1–20,
the unchanged baseline and a 15-percentage-point band. The check passes, with a largest absolute difference of 15 percentage points and 35 winner changes versus the historical baseline. These are not changes versus the parent.
These bounded tests are not a full rules-compliance or unrestricted balance proof.

## Progress

The three-card batch closes **one** original finding, EXP-08:
**33/50 closed (66%), 17 open**. Related Scouted handling adds no denominator.
The separate defects, 34 unverified inventory rows, two source questions and
twelve adopted provisional rulings keep their dispositions.

[Machine-readable results](expansion-up-to-2026-11-04-results.json) ·
[Evidence archive](expansion-up-to-2026-11-04-evidence.zip)
