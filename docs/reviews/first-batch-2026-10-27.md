# First comparison repair batch — 27 October 2026

This batch repairs Event state integrity and effect lifetimes identified by
the owner-authorized Liberty or Death comparison. The other repository's
engineering lessons guided the investigation; Falling Sky's supplied
references alone govern these gameplay corrections. Protected references
and `fs_bot/rules_consts.py` are unchanged.

## Repairs and source evidence

| Area | Corrected behavior | Authority and regression coverage |
|---|---|---|
| Physical quantities | Public piece operations reject negative, fractional, Boolean and malformed counts before routing or changing physical inventory. Zero-count calls are exact no-ops. Rejected Leader, Legion, visibility, Region and excessive removal requests preserve the state. | §1.4.1; `test_piece_operation_safety.py` |
| Live state checks | Invalid map counts cannot cancel excess Available counts and pass conservation. Both validators check numeric inventory domains before arithmetic; Legions-track rows cannot exceed four. Structural checks enforce Resource count domains and the 45 cap. | §§1.4.1, 1.8; `test_live_count_validation.py`, including strict save/reload |
| Boii | Validate the whole plan, beneficiary, native troops, aggregate two-Allies/two-troops limit, Subdued Tribes and initial Control scope. Perform all possible placements; pool shortages permit partial execution. Shaded replaces one or two distinct eligible Aedui Allies, removing without replacement when required. Human menus and non-player plans now supply those choices. | Card Reference 37; §§5.1.1–5.1.3, 8.2.3, 8.3.1, 8.4.1; `test_boii.py`, `test_boii_np.py` |
| Next-card eligibility | Preserve the effects of 40, 48, A19, A23, A40 and A53 after ordinary card cleanup. The final executor-specific clause in shaded 6/14/A53 preserves that executor, including Romans or Aedui where applicable. Penalties expire after their printed duration. | Respective card references; §2.3.6; Card 14 Tip; `test_event_eligibility_lifecycle.py`, `test_parley_lifecycle.py` |
| A33/A70 capabilities | Register both unshaded sides, expose them to display/removal, and clear their effects when removed or replaced. Read older modifier-only saves; an explicit shaded registry entry takes precedence over stale unshaded flags. Actual Battle/Retreat behavior follows the active side. | §5.3; A Card Reference A33/A70; `test_retreat_capability_lifecycle.py` |
| Parley | Supply complete legal human meetings and non-player plans. Move the named Leaders and all specified troops, including Scouted Warbands, without unsupported helper arguments. Validate the meeting before mutation and apply the independent eligibility clause even when no meeting is possible. Roman/German bots enforce their printed selection conditions. | A Card Reference A23; Ariovistus Roman/German Event instructions; `test_parley_lifecycle.py` |
| Related discoveries | Explicit default visibility now records converted Diviciacus placements as Hidden in the physical-owner ledger. Wailing Women's post-Counterattack exemption requires named Ariovistus, rather than any Germanic Leader. | A1.4; A33; `test_diviciacus_placement_defaults.py`, `test_retreat_capability_lifecycle.py` |
| Capability interactions | Parley cannot move Germans into Roman-only Cisalpina while Gallia Togata restricts stacking; the legal reverse meeting remains available. German Phalanx shaded suppresses Wailing Women's harmful Battle effects, which resume when that suppression is removed. | A5, A23, A31, A33; §5.1.1; `test_parley_lifecycle.py`, `test_retreat_capability_lifecycle.py` |

Existing plan shapes remain supported where legal. Incomplete Boii plans
that omit mandatory available placements now reject instead of silently
executing a subset. Invalid Boii or Parley actions preserve board, inventory,
Resources, eligibility and RNG through the production transaction boundary.

The two historical eligibility explanations in `QUESTIONS.md` retain their
original text and now carry dated corrections. No new provisional rule was
introduced; PR-01 through PR-06 retain their existing provisional status.

## Validation

The accepted working tree is based on commit
`538c13d097eda535b54dd0ecee0e7a9d2404bda7`, with Python source SHA-256
`7228099f14b047788c81189f97f0eb434a321dc7e47f835ba548695920bc711f`.
The recorded dirty flag is true because these repairs were tested before
their commit. The digest includes tests and was checked again after all
runs; subsequent documentation/evidence changes do not change it.

| Check | Accepted result |
|---|---|
| Unmodified baseline suite | 4,481 passed on `538c13d` |
| Full repaired suite | **4,715 passed**, zero failed/skipped; Python 3.12.14, `pytest -q -n 6` using the already available optional xdist runner |
| Legacy bot games | 100/100 accepted: seeds 1–20 in all five scenarios |
| Original-edition bot games | 50/50 accepted: seeds 201–210 in all five scenarios |
| Second-edition bot games | 50/50 accepted: seeds 201–210 in all five scenarios |
| Mixed seats and replay | 20 unique scenario/seed cases, replayed twice at each of hash seeds 0/7: 80 executions; zero hard findings or partial plans; JSON reports identical across hashes |
| Strict nested diagnostic census | 25 cases at each hash seed 0/7: 50 executions; all completed, zero defect-class findings; JSON reports identical |
| Balance guardrail | Compared the 100 audited legacy records with the unchanged committed baseline using the exact inclusive 15-percentage-point band; passed |
| Independent review | Reproduced and verified the A5/Parley and A31/A33 repairs; independently accepted all 200 bot records and the balance comparison |

Every accepted bot record has all three completion flags, no errors or
integrity findings, no diagnostics other than legal declines, a final-state
hash and four eligible ranked factions. Computed and emitted rankings agree
with the recorded winner. Exact scenario/seed/edition coverage was checked.

The balance comparison changed 25 individual winners out of 100. Its largest
faction rate change was exactly 15 percentage points, which passes the
existing inclusive band. Neither the baseline nor tolerance was changed;
the sample is a regression guardrail, not a human-balance estimate.

The mixed-seat fuzzer recorded seven rejected randomly generated plans per
hash run. Those are distinct from hard findings and do not establish that
all attempted human actions succeeded. This harness is not a substitute for
the source-derived terminal regressions or an exhaustive choice inventory.

See [machine-readable results](first-batch-2026-10-27-results.json) and the
[evidence archive](first-batch-2026-10-27-evidence.zip) for raw game records,
JUnit results, exact source identities, comparison scripts and logs. Only
attempt 3 is accepted. Attempts 1 and 2 were superseded when independent
review found the additional capability interactions; their interrupted
full-suite runs and exploratory outcomes are retained separately.

These are local results. Remote CI is recorded by GitHub for the resulting
commit; this report does not predeclare its outcome.

## Remaining comparison findings

This batch does not claim complete human-play coverage. The following
confirmed findings remain for later batches:

- The Province's resource choice and Ambacti's roll/removal menu.
- Chieftains' Council's human beneficiaries, information and decisions.
- Spring Leader placement priorities, legal destinations, human choices
  and randomized non-player ties.
- Optional Recruit/Rally quantities and Vercingetorix's combined Rally menu.
- Voluntary own-piece removal/reclamation for humans under §1.4.1.

A source-derived inventory of printed human choices is still needed.
Passing existing-hook inventories, unit tests, and complete bot games does
not establish that every printed choice is exposed or every rule is correct.
Historical outcome measurements remain evidence for their original source
revisions, not measurements of these repairs.
