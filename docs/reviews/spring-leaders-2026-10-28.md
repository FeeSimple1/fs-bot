# Spring Leader placement repair — 28 October 2026

Later disposition: the [29 October Recruit/Rally batch](recruit-rally-2026-10-29.md)
addresses two further menu items listed below. This report retains the
Spring revision's original measurements and balance evidence.

This task starts from `a537511a1220ea4d2b0e94e63ab5cc581ef3a605`.
It addresses the Spring placement item from the second comparison batch,
including related named-Leader defects found in the Gallic War Interlude.
The supplied references and canonical constants are unchanged. PR-01 through
PR-06 remain provisional; Q-O38 retains its existing unresolved disposition.

## Source and implementation

| Source | Corrected behavior |
|---|---|
| Chapter 6 §6.6; Chapter 1 §1.4.3 | Available Successors enter a playable Region containing an own piece or a printed Home Rally/Recruit symbol. Humans choose among all legal destinations; placement cannot be declined. |
| Chapter 8 §§8.3.2–8.3.4; Chapter A8 | Every eligible non-player faction places its Leader where it has the most pieces, with seeded equal-chance ties. Spring bot nodes return a Successor rather than resurrecting the dead named Leader. |
| Chapter A1 §A1.4; Chapter A6 §A6.6; A Setup | Diviciacus has no Successor, including in the optional original-scenario setup. Game-run Arverni do not gain an expansion Leader. |
| Pax Gallica scenario, first-Winter instructions | Vercingetorix can enter symbol-up from the Spring box beginning the first Spring, or the human can defer. The unlock persists through saves; later action-boundary prompts do not consume a turn or Eligibility. |
| Gallic War scenario, Interlude and first-Winter instructions | The Interlude's Spring does not unlock boxed Vercingetorix; the following Winter's Spring does. Ambiorix replaces even an on-map Successor, where the most other Belgic pieces. Available Caesar uses Roman-Controlled Provincia first, otherwise the most Romans. Humans select among tied permitted Regions. |

The shared placement selector accepts an explicit legal candidate set. Its
Event callers retain their own placement scope; Spring's Home/piece restriction
is not applied globally to every Leader Event. Scenario-aware geography also
honors Gallia Togata's Roman-only Cisalpina restriction.

`spring_leader` requests carry the actual named Leader or Successor, source,
legal Regions, and whether deferral is allowed. Replies are exact single-field
Region, permitted deferral, or explicit-default objects. Missing/invalid
durable answers remain pending. Single mandatory destinations resolve without
an unnecessary choice. Bot defaults consume dice in the engine, not in the
menu, preserving replay.

Spring placements roll back together on interruption, including earlier
factions' placements and RNG. Terminal prompts retain current/upcoming card
information, changes and `board`/`b` inspection. Saved assistant sessions retain
accepted responses and resume the pending decision. Preview boards cannot
consume the live session's inbox.

## Direct before/after evidence

The same existing engine calls were run against the clean parent checkout and
the repaired tree. The parent placed the Belgic Successor in Morini despite
four Belgic Warbands in Sequani, ignored a human's Britannia selection, retained
a Successor instead of restoring Ambiorix at Interlude, and always selected
Sequani in a two-Region Roman tie across seeds 1–12. The repaired calls satisfy
the destination/name assertions and select both tied Roman Regions. These
small probes demonstrate the defects and seeded variation; they are not a
statistical test of fairness. Source-derived unit tests cover legality and
tie handling separately.

## Validation

The repaired Python source digest is
`32fc2e1f0c2eb2e005db4c7638884a6d2022246c5eda9d87b7ade87da4caeb74`
(315 Python files, including tests). The clean parent digest is
`071485179ff2949ba9e2163ca48f6761c52f617084f90a0a60ee521f35926d8b`.
All 48 protected reference/constants files remain byte-identical. The parent
full suite passed 5,112 tests before edits.

| Check | Recorded result |
|---|---|
| Final full suite | 5,226 passed, exit 0; pytest reported 53.43 seconds after the reviewed fixture expectation and baseline updates |
| Legacy bot matrix | 100 games: seeds 1–20 in each of five scenarios |
| Original card edition | 25 games: seeds 201–205 in each scenario |
| Second-edition cards | 25 games: seeds 201–205 in each scenario |
| Mixed human/bot sessions | 20 cases per hash seed, each executed and replayed: 80 executions across hash seeds 0 and 7; matching reports, no hard or partial findings; three rejected random plans per hash reported separately |
| Strict diagnostic census | 25 cases per hash seed: 50 executions, matching reports, zero diagnostic defects; 253 legal declines per hash |
| Same-call rule probes | All four before/after checks pass on the repaired source |
| Fresh balance command | 100 games, exit 0; every winner and card count exactly matches the installed reviewed baseline; unchanged 15-point limit |

Every bot record has completion/audit flags, an audited four-faction ranking,
a final-state hash, and no errors, integrity findings or nonlegal diagnostics.
Edition results are separate, not pooled into one win-rate estimate.

The first repaired full-suite run had **5,225 passes and one failure**: an
archived pre-Interlude save's expected continuation digest. Paired probes load
the exact same old saved board, metadata and log on both revisions. At Belgic
Leader placement the old code keeps a Successor; the correction restores
Ambiorix. Both select uniquely maximal Nervii, but the old singleton random
choice also consumed RNG, affecting later tied removals and the rebuilt deck.
The original save and fixture generator stay unchanged; only that fixture's
reviewed continuation expectation changes, retaining the old hash and reason.
This is a changed continuation under corrected rules, not a save-format change.

The unchanged original balance comparison **failed**: Gallic War Arverni
wins fell from 4/20 to 0/20, exceeding the 15-percentage-point band. Across all
100 standard games, nine winners and six card counts changed across eleven
records. The original failed comparison is retained.

All nine changed-winner games were replayed on the clean parent and repaired
source, reproducing both recorded final hashes. Independent review identified
the first meaningful placement or RNG difference in each pair:

| Games | First meaningful difference |
|---|---|
| Pax Gallica seed 3; Gallic War seed 4 | Non-player Successors now use the most-own-pieces destination rather than the first Home Region. |
| Pax Gallica seed 5 | Equal Vercingetorix entry destinations now receive the required seeded random choice. |
| Gallic War seeds 1, 3, 14, 18 | The shared Interlude chooser no longer consumes a random draw for a unique destination, changing subsequent seeded choices. |
| Gallic War seeds 8, 12 | Sorting the equal-priority Ambiorix destinations changes which legal destination receives the same random draw. The old mapping was not a rule violation. |

These are first-divergence localizations, not proof that one isolated choice
alone determined each final winner. The nine pairs plus one recaptured trace
are 19 diagnostic game executions, separate from the accepted matrix. The
initial truncated Gallic War 14 trace and its recovery provenance are retained;
the recaptured full trace reproduces the same recorded final hash.

The reviewed candidate retains all 100 standard keys and the unchanged
15-percentage-point limit. Its SHA-256 is
`815b6f363134159b4cf5772abd4dc76a5e8e0be8fd0bb852dc571390504814f5`;
the original baseline hash was
`15dd335d71fb38288348651c158462a1db8ca42868393ac4fcee4ce682c364bf`.
Root and independent review both matched every candidate winner/card count
to the raw game records before installation. Final suite and fresh balance
checks then passed with the same Python digest, the final compatibility
manifest hash
`0e1609c9158d2a2e635eca578681442764b05637200f7000ae5554ccceb060ef`,
and the installed candidate bytes unchanged throughout both commands. The
fresh balance command took 65.06 seconds. The matrix and fresh balance check
total 250 bot executions; the second 100 repeat the standard keys and are
not an additional set of distinct sampled games.

The compatibility expectation changed only in JSON; the game matrix and both
full-suite runs use the same Python source. The first failed suite remains
separate from the final passing run. Historical parent outcome records retain
their original validation base-commit metadata; the new clean `a537511` traces
reproduce their exact hashes rather than relabeling those older files.

The scratch verifier initially made an incorrect assumption about Optimates
winners. The supplied Card 20 text and §7.3 require normal victory evaluation,
which can produce another winner. That verifier-only assumption was corrected;
its initial output is preserved. Independent raw-record review confirms the
engine rankings. No game result was altered to satisfy the verifier.

The [machine-readable results](spring-leaders-2026-10-28-results.json) and
[evidence archive](spring-leaders-2026-10-28-evidence.zip) preserve commands,
actual exit codes, source manifests/snapshot, raw games, failed comparisons,
JUnit, compatibility probes, paired traces and independent reviews. These are
local results; remote CI is verified separately on the pushed commit.

## Remaining work

The automated frontends now offer boxed Vercingetorix at Spring, before an
eligible faction's action, after the card's faction actions, and before a later
Winter resolves. A saved boundary token prevents the same deferred window from
being offered again merely because the next decision paused. Arbitrary
interruption **inside** a resolving Command or Event is still unsupported.
These windows do not exhaust the scenario's printed “at any time” freedom;
the lower-level explicit entry resolver is not a substitute for that missing
human interface.

Other known comparison work remains optional Recruit/Rally quantities,
Vercingetorix's combined Rally menu, voluntary own-piece reclamation under
§1.4.1, and a source-derived inventory of every printed human choice. Passing
the tests and sampled games does not establish exhaustive rules compliance
or human strategic balance.
