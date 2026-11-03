# Gallic Event ownership and action choices — 2 November 2026

This batch repairs the beneficiary, Command order and placement defects on
numeric cards 35 shaded, 46 shaded, 67 and 68 shaded. It closes BE-03 and
repairs numeric 67's part of BE-01; other BE-01 March grants remain open.
The owner adopted the researched policies as PR-10/PR-11, subject to official
correction. Their implementation and the associated repairs pass the final
validation below. **19 of the original 50 findings are closed (38%); 31
remain open.** This is a finding count, not an estimate of remaining effort.

## Corrections

Gallic Shouts now lets the Event executor select a Gallic beneficiary. That
beneficiary chooses whether its full or Limited Command comes first and
chooses each action on the resulting board. Both are free, without Battle
or a Special Ability. Celtic Rites similarly gives the Command to the
selected Gallic faction while keeping the original Event executor Eligible.
The prior implementation commanded the Event executor's faction and always
put the full Command first on Gallic Shouts.

Numeric Arduenna lets the executor select Romans or a Gallic faction. The
recipient accepts or declines the whole sequence, then chooses its March
into Nervii/Treveri and its non-March Command in either or both Regions.
Possible components are required after acceptance. Final hiding treats
Scouted pieces correctly: Marching pieces first lose the marker and can Hide
after the Command, while nonmoving Scouted residents lose their marker and
remain Revealed. Expansion A67 retains its different beneficiary list.

Remi Influence belongs to the Gallic faction allied with Remi, regardless
of Event executor. That owner may decline or choose Alesia/Cenabum, clearing
the City's occupant/status and placing its own Citadel plus four Warbands
as available. The previous handler placed the Event executor's pieces.
Replacement shortfalls still permit the printed removal; removing an own
Citadel can make it available for replacement. Other forces, Forts and Abatis
in the Region remain. The correction also clears a City Razed marker stored
at Region level by Sacking, preserving unrelated Dispersed markers.

The supplied Card References and Chapters 3/5 establish these ownership,
scope and partial-execution rules. Chapters 8/A8 govern non-player choices.
No protected reference, canonical label or existing provisional ruling is
changed. Bot-only target priorities do not narrow human legality.

The shared Arduenna default also now breaks equal origin-strength ties with
the seeded random selector. Planning no longer contaminates its returned
group with private March bookkeeping. Mechanical Command detection rejects
a Battle with no acting-faction pieces while preserving legal static-only
and cooperating-force Battles. Numeric 67 retains the established public
`card_67` result flag.

## Human decisions and compatibility

Terminal menus and durable sessions route each decision to its actual owner.
They display current/upcoming card information and per-seat changes, and
permit `board`/`b` inspection before choices and within action planning.
Detached previews preserve live input and RNG. Original-executor voluntary
removal remains distinct from a beneficiary's independent Spring-entry right.

Invalid or missing durable responses retain the pending decision and do not
commit a substitute bot choice. Saved sessions resume between Gallic Shouts'
two Commands and between Arduenna's March and Command; replay preserves the
accepted choices and resulting state. Explicit defaults use the implemented
non-player policies and differ from missing input. Numeric 67 uses the
newly adopted PR-11 prediction policy described below. Older affected transcripts may
need the newly introduced decisions. Initial typed parameters now separate
the executor's beneficiary choice from the recipient's action choices; a
foreign executor cannot preauthor Remi's City decision.

## Adopted rules and remaining limits

The owner adopted [PR-10 and PR-11](../provisional-rulings.md#pr-10), explicitly
subject to official overruling if an authoritative source is found. The
[research note](gallic-event-rules-research-2026-11-02.md) records the scoped
external search, its limitations and the distinction between published
requirements and project adaptations. The original prototype and unsupported
path remain historical evidence, not accepted implementations of the rulings.

PR-10 gives an At War automatic Arverni beneficiary the first possible
permitted Command in Rally–March–Raid–Battle order, respecting the grant's
limits. Battle retains its inherent Ambush and Hidden-superiority condition;
At Peace gives no Command. Each grant reevaluates the actual board. No human
Command or order prompt belongs to this automatic faction.

PR-11 supplies numeric 67's non-player Arverni prediction model. Roman bots
follow their printed Retreat policy; against human Romans the planner
compares legal protective responses and maximizes the lower Legion-Loss
forecast. It retains the printed best-case Defender-roll convention and
ordinary Vercingetorix Harassment safety. Other uncertain own saving rolls
cannot inflate that conservative forecast or establish Leader safety. Live
decisions and dice still resolve normally. Scoring retains ordinary default
casualty priorities; the protective-response comparison is not a universal
minimax over every human casualty assignment. Frost separately checks legal
human casualties and dice. It does not supply a new physical Elite
designation policy.

The related Roman Retreat correction replaces an unconditional retreat on
any positive incoming Loss with a comparison of projected Legion Loss rolls.
Auxilia and cooperating troops can shield Legions; Retreat's static-first
loss order can change that exposure. Active Abatis counts as a Fort and
shaded German Phalanx cancels it. Preview priority inspection does not consume
live RNG or copy human callbacks. The independent last-piece and poor-
Counterattack criteria remain. Three of nine regression cases fail on the
parent, all nine pass after repair; 44 focused Battle/lifecycle checks pass.

The ordinary March menu still lacks a pure hide-without-movement choice,
which also limits 35/46 grants. That existing finding
(`MARCH-HIDE-IN-PLACE`), other BE-01 March grants and ordinary SA-first board
display (`FE-01`) remain separate. No claim is made that this batch closes
every action menu or every rule interaction. The original 34 unverified
inventory rows remain. Two source questions lack a project ruling; eleven
others now have provisional dispositions.

## Separate ordinary Arverni Phase follow-up

Reviewing A6.2 for the Event adapter exposed five defects in the existing
ordinary phase: Rally adds Warbands after an Ally in the same Region;
Rally can place an Ally without Arverni Control; a secondary March can leave
the targeted enemy's Control intact; Raid can use more than two Warbands in
a Region; and its Ambush reserve can block Raid even when no damage-causing
Ambush is possible. Reproducible source-based witnesses and the review note
are preserved in the evidence package. The new bounded Event adapter avoids
these defects; the ordinary phase requires a separate repair. These are
additional findings outside the original 50-item human-choice denominator.

Two initial suspicions were cleared: the shared piece helper correctly
leaves Scouted Marchers Revealed, and the ordinary Ambush reveals the
attackers before a second opponent could be attacked. They are not counted
as bugs.

## Validation and provenance

Public-call before/after witnesses reproduce all three wrong-beneficiary
paths and the Remi placement error on parent `e37b965`. Independent source
and implementation review supplements engine, real-menu and durable-session
regressions. The same-source parent suite and 100 bot records are reused
with their original provenance; they are not relabeled as fresh runs.

The first frozen integration matrix completed every game but was rejected:
two bot games failed their audits, and one distinct mixed-player case
recorded a hard bot Event rejection. All involved card67. One shared March
bug attached Diviciacus physical-owner metadata to an origin outside the
actual cooperation area. Another converted Hidden and Revealed members of
the same initial group into duplicate Hidden bookkeeping rows. Both are
repaired without merging different owners or March groups. Fourteen new
regressions reproduce thirteen failures on the frozen pre-fix snapshot and
all pass after repair; the remaining case checks preserved behavior.

The first full suite recorded 7,057 passes and two failures: the renamed
public card67 result flag, now restored, and the three-seed balance canary.
The larger 100-game comparison remained within its unchanged 15-point band,
but this did not excuse the smaller canary failure. Paired traces distinguish
new rule-driven changes from changes already present in the immediate parent;
the final outcome review is recorded below. Failed suites, games and
exploratory traces remain separate from accepted results.

The second matrix was runtime-clean, but was not accepted: causal review
found that the reused Arduenna default excluded original Nervii/Treveri
forces as March origins. The repaired default freezes the initial cohorts,
permits those origins, and still forbids marching new arrivals again. The
subsequent owner-adopted PR-10/PR-11 implementations require their own final
validation; neither older matrix is pooled into that acceptance sample.

The final candidate's focused set passes 263 tests. An independent bounded
oracle enumerated 210 allocations and matched the optimizer's result for
each tested position. Separate tests cover physical initial cohorts,
protective Retreat, contingent second-Region Battles, once-per-Command
Capabilities, Abatis rolls, human Diviciacus refusal, and intermediate Frost
victory checks. The exhaustive oracle is scoped evidence, not a proof of
every possible game position. The exact search uses no arbitrary cutoff;
its retained state distinctions cover the subsequent Battle/Retreat and
Control effects. The existing scalar non-player Elite designation remains
a separately unresolved policy.

The PR-11 timing checks recorded 4.23 seconds for a position with all 35
Warbands spread across seven origins, and 1.86 seconds for the initial Great
Revolt position, preserving live board/RNG. These are local measurements,
not a universal response-time guarantee. Saved-session coverage verifies
that a binding human no-Harassment promise survives save/load, is honored by
the actual March, and replays without repeating the promise.

A final focused-test failure was a fixture arithmetic error: Nervii's
Control value is two, not three. Its correction did not change production
Control handling; independent checks confirmed the existing piece helper
refreshes Control at that boundary. The earlier failed log is retained.

User-facing dates use America/Chicago; execution takes place on 3 November
UTC. The previous commit `e37b965` completed all 14 remote CI checks
successfully. That result belongs to the parent, not this repair.

## Final frozen-source validation

Candidate 3 contains 442 Python files with combined SHA-256
`cdd29718dab7ea7443f93dc225f192e3f31751aaa84c4e6e56d617a2b6c7b63c`,
prepared over parent `e37b965e5ce420e29e486c7221661e51b9803282`.
Exact Python 3.10.22 ran the complete suite: **7,149 passed**, no failures,
errors or skips, in 177.51 seconds. Source bytes remained fixed throughout.

The final game matrix contains 150 audit-clean bot games (100 legacy,
25 original and 25 second-edition), across all five scenarios. Mixed-seat
validation covers 220 distinct positions/seeds, executed with both hash seeds
and replay for 880 executions, with zero hard findings. The 20 strict-census
executions are also clean. Both hash seeds produce identical mixed/census
JSON and stdout. Replays, repeats, diagnostics and earlier revisions are
not counted as additional independent samples.

The sole mixed-seat soft partial was inspected in one extra diagnostic game:
a test player transferred four Resources to the Germans after constructing
an Aedui Rally plan. Mandubii resolved, leaving insufficient Resources for
Treveri and Aedui. Dry/live signatures and the complete final record matched;
this was not a missed mandatory Event effect.

All 49 protected input hashes are unchanged, including the 48 rule inputs
and the balance baseline. The full 100-game baseline comparison passes its
unchanged 15-percentage-point band; the three-seed canary passes its unchanged
40-point band. The largest changes are 15 and 33⅓ points respectively.
**No baseline was refreshed.** The earlier attempt2 baseline candidate was
never installed, and the conditional post-refresh 100-game plan was not run.

The [machine-readable results](gallic-event-grants-2026-11-02-results.json)
and [evidence archive](gallic-event-grants-2026-11-02-evidence.zip) retain exact
source manifests, patches, game records, tests, causal traces and separate
historical checkpoints. Reproducible source snapshots and caches are omitted
from the archive after reconstruction checks. One intermediate diagnostic
trace reports a source digest without a retained full manifest, and one
truncated historical GR5 capture was overwritten before preservation; those
limitations are disclosed rather than represented as complete source proof.

## Outcome review and acceptance

The final legacy matrix changes 23 winner/card-count records against the
immediate parent and 54 final state hashes. Fifteen changed-outcome cases
have exactly the same final state as previously reviewed attempt2 cases;
that earlier causal evidence is reused with explicit provenance. Eight
fresh paired traces were reviewed: six first diverge at the corrected Roman
Retreat decision and two at shaded Remi eligibility. All six Retreat cases
had equal board/RNG before the decision; four exposed no Legions in either
stance and two exposed both Legions in either stance. Neither the last-piece
nor weak-Counterattack criterion independently required Retreat.

The formerly blocked Great Revolt seed6 is also checked separately: the
original Nervii force again Marches to Treveri and Battles the Romans. Its
453 checkpoints match the parent after removing documented receipt-only,
write-only-marker and transient beneficiary annotations. First-divergence
review identifies the initial intended behavior change; it does not claim
that one change alone determines every later move or the final winner.

Against the older stored baseline, 28 records differ (21 winners and 16
card counts, with overlap). These comprise 16 new-only differences, nine
inherited-only differences and three prior/new overlaps; four older drifts
cancel back to the baseline. The inherited records reconcile with the
previous named-Event review. No unexplained first divergence remains in the
reviewed changed-outcome cases.

A truncated attempt3 GR6 trace was retained as rejected capture evidence and
successfully recaptured. The accepted traces reproduce the matrix outcomes;
the archive distinguishes the failed bytes from the checked recapture.
Final acceptance applies to candidate3 only. The five ordinary Arverni Phase
follow-ups, other audit findings and explicitly scoped policy limits remain
open as described above.
