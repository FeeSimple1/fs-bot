# Quarters visibility choices — 4 November 2026

Client date: America/Chicago. Parent `0a006caca41b297ec8842d51d973bcf2c9f29e55`.
Tested working Python digest:
`8dc4932e3aef23aa039773d005d44c7a492f1618d4b44d054f1b2fa68254c13d`
(495 Python files). The publishing commit includes this frozen source.

## Source and correction

Chapter 6 §6.3.2 lets each Gallic owner relocate any Warbands and Leader to
adjacent eligible agreed-Control Regions that are not Devastated. §6.3.3 gives
Romans the adjacent step followed by movement to Provincia: supplied Legions
and Auxilia, plus the Leader from anywhere. Supply is determined after the
adjacent step. A6.3.2 substitutes playable Germans for game-run Arverni;
A6.3.3 retains Roman Quartering. Quarters does not perform March's hiding or
Scouted conversion. Existing host eligibility and agreement rules remain.

Previously the engine accepted only four-entry relocation rows and silently
selected Hidden, then Revealed, then Scouted pieces. Owners could choose a
count but could not select the physical visibility cohort. A fifth entry now
selects exact Hidden/Revealed/Scouted Warbands or Auxilia, preserving visibility
through adjacent and Roman Provincia moves. Hard pieces retain four entries.
The terminal offers separate cohorts and legal quantities; durable responses
use the same contract without introducing a new request kind.

Adjacent capacity is frozen by original Region/type/visibility before any
pieces move. Arrivals cannot supply a second adjacent move, including cases
where another visibility cohort originally occupied the intermediate Region.
Romans may take the separate, later Provincia step with eligible arrivals.
Every mixed legacy/exact plan reserves actual cohorts in submitted order.

An invalidated Provincia plan reopens only that unfinished step. Continuation
validation reserves both offered aggregate totals and live visibility cohorts,
so duplicates and mixed legacy/exact rows cannot overclaim either. Explicit
default retains an original exact visibility, trimming/dropping unavailable
pieces without silently substituting another cohort. Adjacent moves remain
committed within the action; a pending continuation rolls the outer transaction
back while retaining accepted decisions for deterministic replay.

## Compatibility and limits

Existing four-entry Warband/Auxilia rows retain Hidden/Revealed/Scouted selection
and result shape. NPC planners continue to emit those rows. Provincia request
`legal_moves` keeps four-entry maximum-count summaries; responses can add the
fifth visibility entry. Terminal menus inspect live cohorts and validate each
selection against aggregate maxima. Payment, Supply agreement, host consent,
visibility preservation and Spring-entry timing retain their existing rules.
Previews consume neither live human choices nor RNG. Missing/invalid durable
answers retain pending IDs through rollback/save/resume and exact replay.

This closes only WS-F05. CV-PERSISTENCE, full Rampage victim choices, NPC
Intimidate targeting, 34 unverified inventory rows, two source questions and
twelve adopted provisional rulings keep their dispositions. No new rule
interpretation is introduced. All 47 reference files, canonical constants and
the balance baseline remain unchanged (49 protected inputs).

## Validation

**8,104 tests pass** in the final full suite (342.00 seconds), with zero failures, errors or skips. **129 targeted tests pass**. **56 new cases** cover both base and expansion seats,
all three visibility states, legacy controls, duplicate/mixed capacity, invalid
rows, original-cohort arrival restrictions, host refusal and preview isolation,
Roman supplied/second-step movement, continuation maxima/default intent, terminal
inspection, live Spring-triggered reconsideration and durable full-plan plus
continuation rollback/save/resume with identical replay.

The isolated parent runs the unchanged test file through existing engine APIs:
**29 behavioral failures** demonstrate rejected exact physical selections;
**12 controls pass**, with 15 cases deselected. Missing helper imports are not
counted as behavioral evidence.

Ten audited native-bot games cover all five scenarios and seeds 1–2. Mixed-seat
matrices use those seeds, hash seeds 0/987, Events, reactions and internal replay
(40 executions total). All ten native-bot records complete and audit successfully, with no errors or
integrity findings, four ranked factions, consistent winner/ranking fields and
nonempty final hashes. Every gameplay field and final hash matches the parent;
only elapsed seconds, commit and source digest are excluded from comparison.
Both mixed-seat outputs agree in complete JSON across hash seeds: 247 human
turns, 77 Event attempts, 75 successful Events, zero hard findings, zero partials,
batch digest `5dd20da48e8e672b`. Internal replay makes 40 executions in total.

Legacy NPC selection is unchanged. This task does not rerun the 100-game
historical balance smoke; it checks exact parent/current native-bot gameplay
records and final hashes instead. These bounded cases are not a full rules
compliance proof or an unrestricted balance claim.

## Progress

WS-F05 closes one original finding: **32/50 closed (64%), 18 open**.
Counts are findings, not equal effort units. Historical inventory remains intact.

[Machine-readable results](quarters-visibility-2026-11-04-results.json) ·
[Evidence archive](quarters-visibility-2026-11-04-evidence.zip)
