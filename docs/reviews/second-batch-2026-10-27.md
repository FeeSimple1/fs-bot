# Second comparison repair batch — 27 October 2026

This batch addresses The Province (21), Ambacti (16), and Chieftains'
Council (47), following the confirmed human-play gaps in the
[first batch](first-batch-2026-10-27.md). Falling Sky's supplied references
govern the implementation. Protected references and canonical constants
remain unchanged; no new provisional ruling is introduced.

## Repairs and source evidence

| Area | Corrected behavior | Authority and regression coverage |
|---|---|---|
| The Province: human benefit | Offer Auxilia or Resources with the actual Available pool and Resource-cap limits; reject malformed explicit alternatives before mutation. | Card Reference 21; §§5.1–5.1.3; `test_province.py` |
| The Province: Senate and bot execution | Treat the two-box shift as one Event when Firm, apply the scoped Fort exception to Arverni Battle prediction, and enforce the Roman non-player instruction to place all five Auxilia. | Card Reference 21 and Tip; §5.1.1; §8.7.1; Roman Event instructions; `test_province.py` |
| Ambacti: human timing and physical pieces | Show the actual die roll before choosing three or the rolled number, then remove the exact selected Auxilia by Region and visibility. Unshaded placement requires Roman pieces and grants six only with named Caesar. | Card Reference 16 and Tip; §§5.1, 5.1.3; `test_ambacti_choices.py`, `test_ambacti_sessions.py` |
| Ambacti: non-player decisions | Correct placement, bare-Legion, Belgica, and German geographic priorities, use seeded tie-breaking, and permit Aedui's fixed Roman benefit when its printed conditions allow. | Scenario-specific Event instructions; §§8.2.3, 8.3.1, 8.4.1; `test_ambacti_np.py` |
| Council: selections and actions | Let the executor select the Region and 2+ player beneficiaries, resolve in printed scenario order, and offer each a free Limited Command anywhere, Eligible or decline. Preserve Eligible through cleanup and override earlier conflicting Event penalties. | Card Reference 47 and Tip; §§1.5, 2.3.5, 5.1, 5.1.2, 5.4; A1.5/A2.3.2; `test_council.py`, `test_council_sessions.py` |
| Council: private information | Show the next two face-down cards, skipping the public upcoming card; handle Winter and a short deck. Include full available card text and scenario-correct metadata only in the beneficiary's request, not public board snapshots, changes or results. | Card Reference 47; §§2.2, 5.1.3; `test_council.py`, `test_council_sessions.py` |
| Explicit free-action answers | Reject numeric, string or mixed-object defaults/declines before consuming durable input or applying an action. Only the exact Boolean sentinel is accepted. | Agent-interface explicit-response contract; `test_free_action_sentinels.py` |
| Ariovistus card display | Show Germans in the Arverni initiative/NP-symbol slot on retained base cards, without changing the underlying reference text or card metadata. | A2.3.2; public-display and Council metadata regressions |
| Aedui conditional Events | Evaluate the existing typed conditional instruction for each listed Event: decline with human Romans or a Roman victory score above 12. Use the current scenario's score, including German Settlements in Ariovistus and the base formula after Interlude. | Both supplied Aedui Event instruction sheets; §§7.2/A7.2; source-group, boundary and production-selection regressions |
| Winter Uprising target | Require a legal Region before creating the delayed trigger; non-player Belgae/Germans choose their printed Belgica/Germania Regions without an own-piece prerequisite. Treat A66 as a marker Event, not a Capability. | A Card Reference A66; both NP instruction sheets; A5.1.4; exact seed-8 reproduction and target/atomicity regressions |
| Winter Uprising delayed choices | Track the holder, offer activation after normal Quarters, force it at Interlude, and expose exact within-one-Region placements to the specified chooser. Apply NP location/piece priorities and require the following Command when possible. Preserve the full transaction through later pending decisions. | A66; §5.1/5.1.3; §§8.2.3/8.3.1/8.4.1; Gallic War Winter Events; `test_winter_uprising_resolution.py`, `test_winter_uprising_sessions.py`, `test_winter_uprising_np.py` |
| Last-year restrictions | Use the actual Winter calendar consistently for Capability declines and A66's specific instruction, preserving the Gallic War's continuation before Interlude. | §8.1.1; A66 NP instructions; Gallic War scenario and existing Winter-engine counting; live-deck and transition regressions |
| Nervii bot prerequisite | Roman/Aedui bots decline A70 when Belgae are non-player, in both expansion scenarios and every year. Preserve player-Belgae opportunities and explicit human Events. | Both expansion bot instruction sheets; actual R4/A3/full-dispatch and human/base-isolation regressions in `test_nervii_np.py` |
| Scoped German Rally + Settle | Preserve permitted Settlement entries when an Event limits action Regions, including the valid case where only Settle places a piece. Keep out-of-scope entries excluded. | A8.7.4's "doing either" condition; exact failed Winter trace and scoped-plan regressions |

Ambacti's accepted post-roll choice survives interrupted execution,
save/resume and replay. Previewing does not consume live responses or RNG.
Explicit pre-roll removal parameters remain a compatibility interface for
direct callers without a decision agent; live decisions take precedence.

Council's non-player Event-selection instructions remain "No Event". If a
human selects a non-player beneficiary, its unprioritized Command/Eligible
choice uses seeded randomness (§8.2.3), followed by its actual limited
flowchart when Command is selected. An ineffective Command does not silently
grant Eligible. For raw callers omitting a selection, the documented
compatibility default chooses a seeded qualifying Region and all player
Factions present. Durable missing human input remains pending.

Private Council requests are recipient-specific, but a shared terminal,
trusted save file, request journal or raw callback is not an access-control
boundary. These interfaces already contain trusted full-state information.

The outcome investigation found that the Aedui's conditional instruction
flag was stored but never evaluated. The repair uses that existing flag for
the exact 16 base and 17 expansion card entries, rather than parsing prose
or adding new priorities. Boundary and production-node checks cover Roman
scores 12/13, human/non-player Romans, Settlement subtraction, and actual
Interlude transition. This restriction applies to bots, not human Events.

## Validation

The final tested working tree is based on commit
`04b4b70bedae78a07723340aa4ed401b3a77dd29`, with Python source SHA-256
`071485179ff2949ba9e2163ca48f6761c52f617084f90a0a60ee521f35926d8b`.
The recorded dirty flag is true because testing preceded the commit. This
digest includes Python tests; documentation, baseline JSON and evidence do
not affect it. Protected references and canonical constants are unchanged.

| Check | Final attempt 5 result |
|---|---|
| Full pytest suite | 5,112 passed; actual exit 0 |
| Legacy bot matrix | 100 audited games: all five scenarios, seeds 1–20 |
| Original and Second Edition | 50 audited games each: all five scenarios, seeds 201–210 |
| Mixed human/bot seats | 80 executions including replay; seeds 1–4 in every scenario, hash seeds 0/7; matching reports, no hard or partial findings |
| Strict diagnostic census | 50 executions; seeds 1–5 in every scenario, hash seeds 0/7; matching reports, zero defects |
| Original balance comparison | Failed: Great Revolt Aedui wins 1/20 → 5/20 (+20 points), beyond the unchanged 15-point band |

All 200 bot records completed with valid emitted/recomputed rankings, no
integrity findings and no nonlegal diagnostics. Mixed-seat testing rejected
two generated random plans per hash, separately from hard findings. The
strict census recorded 245 legal declines per hash. Its success evidence
is aggregate; that tool does not emit individual successful-game records.
All seven matrix processes exited 0. The independent verifier exited 1
solely for the original balance comparison, which remains preserved.

The outcome review preserves a chain of evidence across source revisions.
Attempt 4's 37 changed-winner games versus `04b4b70` had source-backed
first behavioral divergences: 20 typed Aedui exclusions, nine final-year
Capability restrictions, six A66 marker choices, and two mandatory Ambacti
placements. Those traces retain source digest `6155e2b5…`; they are not
relabeled as final-source games.

The final 100-game legacy run reproduces 97 of attempt 4's full final-state
hashes. The three changed states are Ariovistus seed 5 and Gallic War seeds
5/12. Immediate before/after traces reproduce all six old/new hashes and
first diverge at Aedui's A70 Event choice with non-player Belgae: card 4 in
the first two cases and card 31 in the third. The preceding board and RNG
match; the next Winter is not final. The corrected flowchart declines the
Event as its printed instruction requires. The Roman branch is separately
covered by actual-node/dispatcher regression tests in both scenarios.

These three comparisons required five diagnostic simulations, with one old
trace reused. Diagnostic replays are separate from the final game matrix.
Identical final hashes establish identical outcomes, not identical paths;
a first behavioral difference does not prove that it alone determines a
winner. The broader source-derived human-choice inventory remains open.

Independent review checked all 100 final candidate records, rankings,
diagnostics, source identities and preserved original evidence. The approved
refresh retains the same 100 scenario/seed keys and the **15-percentage-point
band**. It changes 50 records, 43 winners and 32 card counts versus the stored
baseline. These are rule-correction outcomes, not targets for bot strength.
The original baseline SHA-256 is
`29149c3e5d01c7cf18a27ab7c18fbb528f7f23b43aa81fa1f986c4316281eb54`;
the reviewed final baseline is
`15dd335d71fb38288348651c158462a1db8ca42868393ac4fcee4ce682c364bf`.

After installation, a **fresh 100-game balance check passed** at the unchanged
band and matched every reviewed winner and card count. The **full 5,112-test
suite passed again** with exit 0. Both checks retained the same Python source
digest and baseline bytes. These are separate post-refresh results; they do
not turn the original failed guardrail into a pass. The final matrix plus
this fresh balance check contains 300 bot executions.

The [results JSON](second-batch-2026-10-27-results.json) distinguishes the
original failed guardrail from the reviewed refresh and fresh checks.
The [evidence archive](second-batch-2026-10-27-evidence.zip) includes raw
records, JUnit, commands and actual exit statuses, source manifests, causal
traces, independent audits and all superseded attempts. Its manifest checks
every archived file. The prior commit's 14 GitHub checks passed before this
batch; remote checks on the eventual new commit have their own GitHub run.

### Superseded first attempt

Attempt 1 used source digest
`6a104c1fd391446cd9485aa20adc3c94862923e4fa624e5d48c68a99dd475b64`.
It passed 4,921 tests and its game-integrity checks, but the original
balance comparison failed: The Gallic War Roman wins moved from 12/20 to
8/20, a 20-point decrease against the unchanged 15-point band.

Four paired Gallic War traces (seeds 3, 10, 16, 20) reproduced the exact
final hashes from the first batch and attempt 1. Seeds 10/20 first diverged
when Aedui correctly executed Ambacti's fixed Roman benefit instead of a
no-op. Seed 16 diverged when Romans correctly declined The Province because
Provincia contained enemies. Seed 3 exposed the missing conditional rule:
Aedui played Ambacti with a Roman victory score of 16. Both the previous
version and attempt 1 allowed that illegal non-player choice.

That finding prompted the shared conditional-instruction repair above.
Attempt 1, its traces and its review-only baseline candidate remain
preserved as **superseded, not accepted**. Its candidate was never installed;
the defect was repaired before new validation. Diagnostic replays and
counterfactual experiments are separate from the final accepted game matrix.

### Superseded second attempt

Attempt 2 used source digest
`642435abc92b12f7286afeb7fe4f21545f69e3baa397cdd3679e4f5f8ad58710`.
All 4,945 tests passed. Its initial 100 legacy games completed, but only
99 passed the diagnostic audit. The Gallic War seed 8 reported a delayed
Winter Uprising without a marker Region, so the gate stopped the remaining
edition, mixed-seat and census runs.

An exact-hash replay traced the defect to card 40: Belgae had no pieces,
the old A66 planner incorrectly required their presence to select a Region,
and the handler created a delayed trigger without placing its marker.
The supplied Event permits placement in any Region, subject to the
non-player faction's printed geographic instruction. The resulting target
selection and prevalidation repair is included in the final source. This
attempt and its targeted replay are retained separately, not accepted as
the final validation matrix. The baseline was not changed.

### Superseded third attempt

Attempt 3 used source digest
`e3d8795d5922cd93a9192f9393d821902e4c428c0ee57b60dc64ac65c2296e74`.
All 5,075 tests passed. Its initial 100 legacy games completed, but four
records failed the diagnostic audit: seeds 14/16 in both Ariovistus and
The Gallic War reported a scoped follow-on Command with no selected action.
The gate stopped the remaining runs. These results remain superseded and
the original baseline remains preserved.

The Ariovistus seed-14 trace reproduced the exact failed final hash. It
showed a legal German Rally + Settle at allowed Treveri, with a Settlement
placement but no Rally Ally/Warband placement. The scope filter discarded
the Settlement fields and rejected the action as empty. The repair
preserves those legal entries; it does not suppress the diagnostic or
invent an alternative action for an exhausted flowchart.

### Superseded fourth attempt

This superseded working tree was based on commit
`04b4b70bedae78a07723340aa4ed401b3a77dd29`, with Python source SHA-256
`6155e2b5be0d2910ad47aacab2ae8489962375ed8091ed54a503cfe6165ae352`.
The recorded dirty flag is true because the repairs were tested before
commit. The digest includes the Python tests; documentation and evidence
files do not affect it. The prior commit's 14 GitHub checks passed before
this work began.

Attempt 4 passed the implementation checks on that frozen source:

| Check | Result |
|---|---|
| Full pytest suite | 5,082 passed; actual exit 0 |
| Legacy bot matrix | 100 audited games: all five scenarios, seeds 1–20 |
| Original and Second Edition | 50 audited games each: all five scenarios, seeds 201–210 |
| Mixed human/bot seats | 80 executions including replay, seeds 1–4 in all scenarios, hash seeds 0/7; matching reports, no hard or partial findings |
| Strict diagnostic census | 50 executions, seeds 1–5 in all scenarios, hash seeds 0/7; matching reports, zero defects |
| Original balance comparison | Failed: Great Revolt Aedui wins 1/20 → 5/20 (+20 points), beyond the unchanged 15-point band |

All 200 bot records completed with valid emitted/recomputed rankings, no
integrity findings and no nonlegal diagnostics. Mixed-seat testing rejected
two generated random plans per hash; these are disclosed separately from
hard findings. The strict census recorded 243 legal declines per hash.
Census success is reported in aggregate; unlike the bot matrix, that tool
does not emit an individual success record for every game.

The four earlier scoped-command failures also passed their separate full
replays on this digest. They are diagnostic evidence, not extra games in
the accepted matrix. All seven matrix processes and the full test suite
exited 0. The independent verifier exited 1 solely for the original balance
comparison; that failure remains preserved.

Attempt 4 was subsequently superseded when final source review found one
more conditional instruction omitted from execution: Roman and Aedui bots
could choose A70 Nervii with non-player Belgae before the final year.
The reproduction covers both expansion scenarios and player-Belgae controls.
Its 200-game matrix and 5,082-test results remain evidence for that source,
not the final accepted version.

Before that discovery, all 37 changed-winner games versus the first-batch
source were traced to their exact old/new final hashes. First behavioral
differences were 20 typed Aedui exclusions, nine final-year Capability
restrictions, six A66 marker choices, and two mandatory Ambacti placements.
Pax Gallica seed 12's earlier Ambacti reporting-only change was separated
from its later actual Aedui decision change. These localizations identify
the first changed decision, not the sole cause of a final winner.

The review-only candidate passed independent data review and was briefly
installed. A fresh 100-game balance check matched every winner/card count,
and a second full 5,082-test run passed. Both are retained. The original
baseline was then restored before fixing A70; this intermediate candidate
is not the final baseline. Its difference from the stored baseline was
50 records, 42 winners and 32 card counts, distinct from the 37 winner
changes against the more recent first-batch source.

## Remaining work

The comparison still identifies Spring Leader placement priorities and
choices, optional Recruit/Rally quantities, Vercingetorix's combined Rally
menu, and human voluntary own-piece reclamation under §1.4.1. A
source-derived inventory of all printed human choices remains necessary.
Complete bot games and existing-hook inventories do not establish that
every human choice is exposed or that every rules interaction is correct.

The six [owner-adopted rulings](../provisional-rulings.md) retain their
provisional status, subject to later correction if an authoritative source
is found. Earlier reports remain evidence for their original revisions.

[Q-O38](../../QUESTIONS.md#q-o38--optional-diviciacus-capability-label-27-october-2026)
records a separate unresolved layout question: whether optional Diviciacus's
Capability label covers its unshaded side too. The shaded final-year check is
repaired; the pre-existing unshaded exemption is preserved pending reliable
printed-layout evidence or authoritative clarification. An independent
72-case comparison confirmed unchanged unshaded bot routing. No new
provisional ruling was adopted.
