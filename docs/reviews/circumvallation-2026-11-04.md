# Circumvallation choices — 4 November 2026

Date convention: America/Chicago. Parent: `947bf814129cfc135b49d2babbbbf740bb46f356`.
This closes original BE-01's human Event-March/guidance choice bundle.
**Persistent Circumvallation mechanics remain broken:** see the separately
verified [CV-PERSISTENCE follow-up](circumvallation-persistence-followup-2026-11-04.md).

## Source and repaired behavior

Card Reference 4 and its Tips assign Romans the optional free March to an
adjacent enemy Citadel and marker placement; ordinary Roman March visibility
applies at selected origins. Sections 3.2.2, 5.1.3 and 5.4 govern movement,
partial execution and free actions. The reference has one effect, so both
legacy text-side inputs continue to execute that effect.

Romans now choose or decline the whole benefit before a new marker or
movement, regardless of which faction executes the Event. Their explicit
plan chooses the destination, ordered adjacent original groups, exact Legions
and Auxilia, and a Boolean Leader selection. Multiple groups from an origin
are supported without reusing original counters or a Leader. No artificial
four-Legion limit or Caesar-only restriction applies. Only one-edge routes
into the chosen enemy Citadel are permitted; other pieces, routes, dropoffs,
unknown fields and unavailable quantities are rejected.

The shared physical-cohort executor preserves original counters, origin
visibility and consenting cooperation. A refused loan returns to the Roman
plan with the marker still absent. Formation choices identify actual owner
and visibility; the physical board and inventories retain those owners.

An empty March leaves the remaining placement effect to resident Romans.
A new marker is placed after accepted movement, only while an enemy Citadel
and Roman pieces remain there. Legacy target parameters are validated and
seed automatic planning; human Romans own the actual choice. Native automatic
movement retains the existing largest-adjacent-group planner. The beneficiary
now also receives a grant when another executor supplied no Roman target.

Terminal inspection and durable invalid/missing input are supported. A save
at physical formation retains the accepted plan; the marker remains absent
until the resumed March finishes. Whole-grant rollback preserves board/RNG
and pending identity. Save schema is unchanged; old transcripts may encounter
new requests and exact cross-revision replay is not promised.

## Verification

Frozen Python source: 477 files, SHA-256
`66f26c1ad50c0ef45d4ecb45fd45fb463381f51670e6c800545a281fc0dcffc1`.
Python 3.12.14. Supplied references, canonical constants and balance baseline
remain unchanged. No new provisional interpretation is introduced.

- **7,623 tests pass** in the final full suite, with no failures, errors or
  skips. The parent checkpoint had 7,594 tests; its full suite was not rerun.
- 29 added regressions cover four executors, whole-benefit decline, marker
  ordering, exact/split forces, more than four Legions, Successor movement,
  origin visibility, malformed plans, legacy target limits, resident-only
  partial execution, cooperation/refusal, terminal and durable save/resume.
- Twenty-three behavioral cases fail against the parent; the native Roman
  largest-group control passes. Five cases were excluded from that witness;
  existing APIs and physical boards establish the parent failures.
- The targeted Circumvallation/Camulogenus/CLI suite passes 68 tests.
- Ten accepted legacy-edition bot games (seeds 1–2, all five scenarios) retain
  the parent gameplay records and final-state hashes, excluding runtime/source
  metadata. This is not a complete trajectory comparison.
- Ten mixed-player cases, each replayed under hash seeds 0 and 987, produce
  40 executions with zero hard findings and identical complete JSON. Each
  ten-case pass records 296 human turns, 88 attempted Events and 86 successes.
- One generated soft partial is reported per ten-case pass, not hidden: on
  card13 in Pax Gallica seed2, the random Belgic plan gives two Resources to
  Aedui and lacks Resources for its later Treveri Rally placement. Dry-run and
  live agree. A focused trace reproduces the recorded digest and identifies
  this policy-generated partial; it is not a Circumvallation execution failure.
- Executable candidate/parent probes separately confirm CV-PERSISTENCE. They
  are retained as known-defect evidence, not counted as passing acceptance.

Fixed-seed checks are bounded evidence, not exhaustive rules certification.
Balance baselines and tolerances are unchanged.

## Scope and accounting

**22/50 original findings are closed (44%); 28 remain open.** BE-01 now closes
human choices on 4/9/17/58/65/67/70. Additional high-priority CV-PERSISTENCE is
separately open: persistent marked-group restrictions, virtual Fort protection,
cleanup and Interlude cohort removal are not repaired here. The two source
questions, twelve provisional rulings and 34 unverified inventory rows also
remain separate. This is not a claim that card4 is rules-complete.

Machine-readable [results](circumvallation-2026-11-04-results.json) and
[evidence archive](circumvallation-2026-11-04-evidence.zip) retain full-suite
logs, parent witnesses, bot records, mixed runs, the soft-partial trace and
known persistent-defect probes, plus the exact implementation patch.
