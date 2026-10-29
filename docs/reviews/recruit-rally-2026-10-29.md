# Recruit and Rally repair — 29 October 2026

This batch addresses two items from the preceding comparison backlog:
optional human Recruit/Rally quantities and Vercingetorix's combined Rally
menu. The parent is `15417ff1b3e6f29b6bc3b6738efcbfb964bce10b`; its clean
baseline passed 5,226 tests before implementation began. All gameplay
conclusions use the supplied, unchanged reference documents.

## Behavior repaired

Human players can choose exact Auxilia and Warband quantities, including
zero where permitted. Region costs still apply to a selected zero placement.
Fixed placements and compulsory bonuses are included in the requested total.
Legacy plans without a count continue to use maximum placement.

Ordered Rally steps preserve named Vercingetorix's Ally-or-Citadel plus
Warbands in either order, with a single Region payment. The second option
uses the actual board and Available pool after the first. Successors gain
no such privilege. All Gallic factions, including Belgae, can select a
legal Citadel replacement. Free German Rally through Enlist accepts exact
quantities and retains the distinction between base Ally-then-Warbands and
Ariovistus's alternative options plus its compulsory Home addition.

Submitted plans validate their full shape and quantity types before
placement. Ordered/exact plans roll back on later Command-placement errors, preserving live
turn identity and RNG. Region extraction, Event restrictions, ordinary
Limited Commands, durable pending decisions, save/resume and replay use the
new plan shape. Previews neither consult a live decision agent nor advance
the live RNG. Diviciacus placements can reserve exact physical owners before
later Region menus compute their remaining pools; consent remains required.

The source audit also found related engine defects:

- Roman bots could select both Ally and Auxilia Recruit in one Region.
  §3.2.1 permits one option; §8.8.4's priorities do not override that rule.
  The planner uses a detached mechanical preview of the prescribed preceding
  Build/Scout and then Recruit, skipping Regions already selected by that
  Recruit. Build placements remain separate and do not count toward the
  Recruit threshold.
- Roman Build's budget check stopped a purchase early. Section 8.8.1 stops
  further spending once Resources are below six; a payment starting at six
  is allowed. The forecast now observes that cutoff and actual affordability.
- Aquitani's shaded Rally additions were missing, and its “your Rally”
  owner was not stored. New activations record the actual executor and
  apply two extra Warbands only to that owner in the named Regions.
- Nervii's shaded addition was lost with a bare Home Region or a static
  placement option. Compulsory Rally additions now apply once per Region,
  including Ally/Citadel placements and normal placement of zero.
- Gallic bot entry tests used separate estimates that could miss these
  additions and actual placement totals. They now measure the legal Rally
  mechanically while retaining their printed thresholds and priorities.
- Original Gallia Togata fixes each Cisalpina Recruit at two Auxilia;
  A5 instead adds one. These additions also apply to a legal Ally option,
  subject to physical availability. A real dynamic Colony can provide that
  option; the shared eligible-Tribe helper now includes it.
- An empty Region's normal presence check could also block Aquitani or
  Gallia's independently effective placement. Those exceptions now preserve
  the applicable geography, Devastation, Intimidation and Supply Line rules.
- Razed Tribes were incorrectly treated as Subdued by the same helper.
  Sacking's printed Dispersed equivalence now prevents those placements.
- Roman forecasts could assume a Supply Line permission that a human then
  refused during the actual Build/Recruit, including under shaded Card 13.
  Concrete permissions are now confirmed before effects and the bot replans
  after refusal. Accepted replies remain binding, pending human replies
  survive save/resume, and speculative planning does not replace live consent
  dice. Event grants keep their Region restrictions and remaining SA allowance.
  The shared Supply resolver also incorrectly granted permission to non-player
  controllers when no callback supplied a reply. It now applies their printed
  agreement policy, including refusals for standalone Build paths.
- Trade checked Supply as if Romans were acting. It now uses Aedui, with
  the Roman declaration governing both Roman-controlled routes and income.
  Actual non-player Trade selection confirms declarations before its
  greater-than-two-Resources test; speculative forecasts remain detached.
  Dispersed and Razed Tribes no longer count as Subdued income.
- Winter Quarters planning bypassed its own permission cache after the
  shared NPC policy correction, allowing application to reroll a previously
  accepted route. The internal cache now serves both paths, retains actual
  player seats and uses the live permission die exactly once. Human
  callbacks cannot override the printed NPC Supply policy.

The synthetic human-policy tests exposed a separate planning assumption:
possible Aedui consent was treated as certain. Roman heuristic Recruit
candidates now also have to remain viable if the uncertain score-10–12
permission is refused. They may still pay for an unsupplied Region; the
policy does not inspect a future die. The real human validator retains
permission-dependent options. This is recorded as an experimental policy
change, separate from the published non-player flowcharts.

An archived pending Frumentum save also exposed a signature-only compatibility
change from the new empty permission cache. Absent and exactly empty caches
are now equivalent for this check, with legacy decision identities retained.
Nonempty permissions, every other board field and the request still compare
exactly. The original saved fixture and its completed result remain unchanged.

The held-out games exposed a further A28/Diviciacus defect. Aedui non-player
consent to Roman defense bypassed the restriction against lending when
Romans Battle against Aedui. Overlapping force views could also assign
physical counters to both sides, leaving stale borrowing counts for losses
or Reveal. The repair preserves the existing human agreement choices and
PR-02 while requiring operations to use each actual counter only once.
An earlier A28 loan remains binding for that Event under §1.5.2; its
pieces cannot subsequently be lent to the opposing force through Diviciacus.
Battle's Reveal step also preserves Scouted markers: it flips Hidden
survivors, while the printed hide/Winter procedures govern marker removal.
A20's temporary “as if there” force must likewise return surviving Scouted
Warbands to their original Regions with their markers intact.

## Compatibility and unresolved source timing

Old active Aquitani saves without an owner do not contain enough information
to identify one. They remain owner-unknown; the engine does not grant the
bonus to an invented faction. New activations and owner-bearing saves have
the correct ownership. This is an explicit historical-save limitation.

The references do not specify whether the Aquitani, Nervii or A5 addition
can occur first to establish Control for an otherwise illegal Ally option.
[Q-RALLY-BONUS-TIMING](../../QUESTIONS.md#q-rally-bonus-timing--additions-before-ordinary-placement-29-october-2026)
records that narrow question. Existing prerequisite checks are retained;
no new tactical ordering rule is inferred. Q-O38 and PR-01 through PR-06
retain their existing dispositions and provisional status.

[Q-A20-ORIGIN](../../QUESTIONS.md#q-a20-origin--counterattack-losses-among-projected-origins-29-october-2026)
records a separate limit: A20 specifies casualty visibility priority but not
which physical Region loses an otherwise identical projected Warband. The
existing deterministic source-allocation convention is retained. The repair
does not claim that convention is settled by the supplied rules.

[Q-SUPPLY-AEDUI-DIE-SCOPE](../../QUESTIONS.md#q-supply-aedui-die-scope--agreement-across-multiple-regions-29-october-2026)
records the unspecified scope of non-player Aedui agreement dice when human
Romans need multiple controlled Regions. Existing Region-keyed declarations
remain; no new action-wide or per-line ruling is adopted.

## Final local validation

The final candidate, attempt 8, contains **335 Python files** with SHA-256
`49e26161e6b49b0f8a28921258e6ebf417d0f2040f8d0551f8f43f05c7c0a296`,
tested as uncommitted changes over parent
`15417ff1b3e6f29b6bc3b6738efcbfb964bce10b`. Its complete suite passes
**5,622 tests**, with no failures, errors or skips (60.81 seconds reported
by pytest). Source bytes and all nine non-Python fixture files stayed
unchanged during the run. The original compatibility fixtures and all 48
protected reference/constant files remain byte-identical to the parent.

The fresh game matrix passes all audits:

- **150 bot games:** legacy seeds 1–20 in every scenario, plus original
  and second-edition seeds 201–205 in every scenario. All completed with
  valid rankings and no execution errors, integrity findings or nonlegal
  diagnostics.
- **80 mixed-seat executions including replay:** 20 cases under hash seeds
  0 and 7, with matching results, no hard or partial findings, and seven
  rejected random plans per hash seed disclosed separately.
- **50 strict-census executions:** 25 cases under both hash seeds, with
  matching results, 331 allowed legal-decline occurrences per hash seed
  and no defects. This tool supplies aggregate completion metadata rather
  than individual successful-game records.

The independent record verifier passes **5,702 checks**. The original
100-game outcome guardrail also passes, with a maximum absolute change of
exactly **15 percentage points**, its existing allowed limit. The baseline
remains unchanged at SHA-256
`815b6f363134159b4cf5772abd4dc76a5e8e0be8fd0bb852dc571390504814f5`.
No replacement baseline, relaxed band or extra post-refresh game run was
needed. There are 63 changed winner/card-count records, including 47 changed
winners and 42 changed card counts; passing the aggregate guardrail does
not mean individual outcomes are unchanged.

Final legacy winners, 20 games per scenario:

| Scenario | Romans | Aedui | Arverni | Belgae | Germans |
|---|---:|---:|---:|---:|---:|
| Pax Gallica? | 10 | 6 | 2 | 2 | — |
| Reconquest of Gaul | 13 | 4 | 1 | 2 | — |
| The Great Revolt | 3 | 3 | 9 | 5 | — |
| Ariovistus | 7 | 3 | — | 5 | 5 |
| The Gallic War | 10 | 2 | 2 | 6 | 0 |

Gallic War names the winning faction at game end, including the Interlude's
German-to-Arverni handover. These deterministic samples describe the tested
engine and bot procedures; they do not estimate human-game balance.
Final-source per-winner causality was not isolated. The earlier paired
traces below remain evidence for their own superseded source, not causal
proof for these 47 changed winners.

The [machine-readable results](recruit-rally-2026-10-29-results.json) and
[evidence archive](recruit-rally-2026-10-29-evidence.zip) preserve the final
raw results, source snapshots, fixture bytes, source reviews and every
failed candidate described below. They record local validation; GitHub CI
has its own results on the pushed commit.

## Superseded validation attempts

The fourth candidate contains 326 Python files with SHA-256
`55a2974400c54957f281bb0343fb899e4ae7389a76da5990330d90312b66d829`.
Its complete suite passed **5,491 tests**, with no failures, errors or skips
(70.36 seconds reported by pytest). The exact source bytes were captured
before the suite and remained unchanged. All 48 protected reference/constant
files remain byte-identical to the parent.

Its matrix audited **150/150 complete bot games**: 100 legacy-profile
games (seeds 1–20 in every scenario), plus 25 original-profile and 25
second-edition-profile games (seeds 201–205 in every scenario). No game
reported execution errors, integrity findings or nonlegal diagnostics. All
four formerly failing A28 held-out cases passed on the repaired source.
The 80 mixed-seat executions and 50 strict-census executions matched across
hash seeds 0 and 7. Mixed-seat runs had no hard or partial findings and
five rejected random plans per hash seed; each census recorded 279 allowed
legal-decline occurrences and no defects.

The original 15-percentage-point balance comparison failed in two places:
Gallic War Aedui wins increased from 2 to 6 out of 20, and Great Revolt
Belgae wins from 4 to 8 out of 20. These +20-point failures are retained.
There were 66 changed winner/card-count records, including 44 changed
winners and 45 changed card counts. The source changes are deterministic;
these differences are not rerun noise. This candidate is superseded: the
paired review found a further Roman forecast defect despite its clean
execution audits. Ariovistus seed 15 and Gallic War seed 15 can Build
a Fort in Atrebates and an Ally in Provincia before Recruiting six Auxilia;
the new planner had checked the pre-Build position and chosen Seize.
The later shared-consent review also corrected the cost: Atrebates already
has a Roman Ally, permitting Build without a Supply Line, but non-player
Belgic refusal makes its Recruit cost two Resources. The older execution's
free Recruit was wrong. Its exact-state replay remains a factual historical
comparison, with the earlier full source-validity conclusion superseded.
Current regressions distinguish the confirmed non-player refusal and an
explicit consenting-human variant on the same physical position.
All 88 paired captures and the failed original comparison are
preserved; no baseline was replaced on this candidate.

Superseded fourth-candidate legacy winners, 20 games per scenario:

| Scenario | Romans | Aedui | Arverni | Belgae | Germans |
|---|---:|---:|---:|---:|---:|
| Pax Gallica? | 12 | 3 | 0 | 5 | — |
| Reconquest of Gaul | 12 | 5 | 0 | 3 | — |
| The Great Revolt | 3 | 2 | 7 | 8 | — |
| Ariovistus | 7 | 4 | — | 4 | 5 |
| The Gallic War | 8 | 6 | 1 | 5 | 0 |

Gallic War counts name the faction at game end; Arverni occupy the former
German player seat after the Interlude. These small deterministic samples
describe this revision and its printed bot procedures, not human balance.

The second validation candidate contains 325 Python files with SHA-256
`58630cc9ad4b55cfa7ce0e3652f1502f9089981ac0953dd88b16909d03999416`.
Its complete suite passed **5,447 tests**, with no failures, errors or skips
(59.54 seconds reported by pytest). Source bytes, the original balance
baseline and compatibility manifest stayed unchanged throughout the run.
All 48 protected reference/constant files remain byte-identical to the
parent. Earlier reports retain their own tested revisions and outcomes.

That candidate's matrix completed all 150 games but passed audit for only
146. Ariovistus seed 205 and Gallic War seed 205, in both original and
second-edition profiles, reported the A28 physical-piece error. All 100
legacy games passed their audits; the original balance comparison still
failed at +20 percentage points for Great Revolt Belgae and Gallic War
Aedui. The 80 mixed-seat executions and 50 strict-census executions passed
their checks and matched across hash seeds. All of these results are
preserved as a superseded attempt, not pooled into the final acceptance.
The baseline stayed unchanged and none of the proposed 43 paired winner
traces ran before the defect was identified.

The first formal suite, on Python digest
`d3101143bbc436dd5fa9d544eb4c0ccc30830bd7767ca46f57fdac7c92a9d7c2`,
reported 5,431 passes and nine failures. Its log, JUnit, exact file manifest
and exit status are retained. Its 325 frozen source files were recovered
and verified against every recorded hash and the aggregate digest; the
recovery record preserves the initial incomplete inventory and methods.
No game matrix ran on that source. Seven
failures concerned changed menu scripts or the old internal A70 cap helper.
The A53 fixture had relied on the now-illegal repeated Recruit Region to
meet its non-player threshold; it now has an explicit legal Fort-supported
position, with a separate regression for the original subthreshold state.

The remaining failure expected a seeded Gallic War policy game to reach the
Interlude. The corrected engine instead gives Rome a legal first-half
victory: score 17 against the expansion threshold of 15. The scenario ends
before its conditional Interlude. That seed remains an early-victory
regression; seed 7 was then selected for the policy-handoff test, before
the fifth candidate exposed its own legitimate early ending. Diagnostic
captures preserve the parent result and every candidate considered for this
test fixture. This changes test coverage, not production play or a balance
sample.

A separate review also exposed interrupted-action rollback: an invalid
later exact Rally portion could leave its earlier portion and SA applied.
The repair restores the whole human action and leaves the same decision
pending. A file-session regression covers correction, save/resume and
deterministic replay. Archived saved-game compatibility expectations did
not fail in the first suite.

The third candidate, Python digest
`0946a507986c4e223d11ccecb02a30d4f3e064d95b96699e0b3c33ecc89dd320`,
passed 5,486 tests and failed one (69.22 seconds). Its A20 regression exposed
a return loop that assumed every projected survivor was Revealed; the corrected
Battle behavior left Scouted Warbands behind at the temporary target. That
failure led to the return-path repair. No game matrix ran on this candidate.
The subsequent test-fixture correction also keeps Roman Auxilia Revealed in
mixed-visibility tests, since Scouted markers apply to Warbands.

The fifth candidate, Python digest
`6608afd6b4f50c42563b3cf2dd3270f8847593affb54b60b799a9ad1b70cf530`,
passed 5,499 tests and failed the seeded Interlude-handoff assertion. Its
seed 7 game legally ends at the third Winter after 47 cards: Roman score 17,
margin +2. No matrix ran on that candidate. The recorded search through
seeds 0–10 found no completed handoff and preserved every result, including
seed 9's shaded-Card-13 Supply refusal error; that error prompted the consent
repair described above.

The handoff test now resumes the unchanged archived pre-Interlude save and
executes its real Victory Phase, Interlude and subsequent policies. It
observes a German Winter Campaign reaction and Arverni ordinary turns;
separate full-game tests retain early-victory seeds 3 and 7. The checkpoint
uses its stored legacy edition, while those new games use second-edition
cards. No victory override or altered deck is used to force the handoff.
The exploratory checkpoint capture is labeled separately from the controlled
test run and the final game matrix.

The sixth candidate, Python digest
`df4912cf6b018797372ea8c391ba037adbdd46793c9cfc4d97d1bb58918b651d`,
passed 5,584 tests and failed four (93.13 seconds). Three Trade failures
exposed a Supply lookup made for Romans instead of the acting Aedui and
the need to bind the Roman declaration to both routing and income. The
Winter failure exposed inconsistent permission handling between Quarters
planning and validation. Its source and all eight non-Python fixture files
were frozen and unchanged throughout the suite. No matrix or baseline
candidate ran on this source; the failures are preserved separately from
the focused checks that had passed.

The seventh candidate, Python digest
`018042b77427cfc2a414558435d6496d11e2de1aea992b42c0786c0a65c0d59e`,
passed 5,611 tests and failed the all-profile human-seat game test
(131.10 seconds). A Recruit/Scout action was rejected in Great Revolt seed
1. The captured R-HUNT position has Roman score 10 and no Resources;
the Aedui die result of 5 refuses Supply, making the planned Recruit cost
two. The engine correctly rejected it. The heuristic had treated possible
permission in the public validator as guaranteed. Its exact source and
fixtures remain preserved, and no matrix or baseline candidate ran on that
source. The same profile and seed remain part of the required coverage.

## Remaining comparison work

Two of the four previously listed implementation items are addressed by this
batch. The two original items left are voluntary own-piece reclamation under
§1.4.1 and boxed Vercingetorix's arrival inside a resolving Command or Event.
The source-derived inventory of every printed human choice also remains.

The review identified a further existing interface limit: an interrupted
Command currently requires different Regions before and after its Special
Activity. The new menu supports both Vercingetorix placement orders but does
not yet split his two placements within one Region around an intervening
Special Activity. This belongs in the remaining within-action interface
work; it is not covered by the completed menu change.

The Trade review confirmed another human-choice gap: shaded River Commerce
(Card 39) limits Trade to one Region, but the human frontend supplies no
Region selection and execution still uses a highest-yield proxy. Exposing
that legal choice is separate from this batch's Supply and income repairs.
There are therefore two original implementation items left and two further
confirmed interface gaps, in addition to the completeness audit.

These are known gaps, not a guarantee that the completeness audit will find
no others. Sampled bot games cannot establish exhaustive human-choice or
rules compliance.
