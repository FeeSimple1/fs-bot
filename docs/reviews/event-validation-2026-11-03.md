# Event limits and German Allegiances — 3 November 2026

This batch closes **BE-11, BE-12 and EXP-09** from the
[29 October human-choice audit](human-choice-audit-2026-10-29.md). It repairs
printed Event limits, physical replacements and the decision paths that
enforce them, completing the audit's mandatory-Event/illegal-plan repair group.

The [progress register](../human-choice-progress.json) now records **17 of 50
findings closed (34%), with 33 open**. This three-finding batch is **3/3 complete
(100%)**. These percentages count grouped findings, whose sizes differ; they do
not measure overall rules accuracy or work-hours remaining. Original audit
measurements remain historical.

## Repaired behavior

| Finding | Scope and resulting behavior |
|---|---|
| BE-11 | Alpine Tribes (40 unshaded) permits one placement type per adjacent Region, within its printed cap. Avaricum (41, both sides) limits optional Allies and validates own-piece replacements and Roman Fort placement. Roman Wine (42 unshaded) enforces its alternative quotas/areas; related shaded validation now enforces Supply Lines and its minimum. Surus (51 unshaded) replaces four actual original Warbands as possible in one permitted Region. |
| BE-12 | German Allegiances (65 shaded) selects five actual German Warbands and one German Ally as possible where the executor has Control. Each selected piece can be removed or replaced; Romans receive Auxilia and Gallic executors their own Warbands. Exact visibility, Tribe identity and selected resolution order are preserved. |
| EXP-09 | A29 unshaded validates its Gallic/Roman beneficiary and Settlement areas; A30 unshaded stays within one Region of Sequani; A36 shaded enforces its placement/removal totals and area; A43 unshaded enforces the Arverni target types, totals and Bibracte area; A45 unshaded limits non-German Ally placements to the printed Celtica/Intimidated-marker area. |

A29's named beneficiary owns its placements. A36's German subject governs
both placements and Ally removals. A foreign executor selects A29's beneficiary
and then awaits that owner's choices; a foreign A36 executor awaits the Germans.
Expansion Arverni resolve automatically. Human legality is distinct from the
non-player preferences used to construct defaults.

Fixed effects occur as possible, while explicit up-to choices retain smaller
legal quantities. Replacement instructions follow §5.1.1: an unavailable or
stacking-illegal incoming piece still causes removal of its selected source.
This is a legal partial effect, not an invalid plan. Avaricum therefore permits
a human's own Ally-to-Citadel replacement even where no own Citadel can enter;
it removes that Ally without creating an illegal piece. NPC defaults do not
voluntarily sacrifice their own Ally. Mere placement does not receive the
replacement exception. Avaricum's ownership condition requires the executor's
Ally or Citadel at the named City, not merely Regional Control.

A selected empty legal Surus Region remains permitted and still grants the
Aedui Command. Its replacements track original physical Warbands, so newly
placed Aedui counters cannot be reused as targets. Roman Wine determines its
controlled/adjacent area before removals change Control. Shaded Wine requires
one to three eligible Roman/Aedui Allies, or zero if none exist, in Supply Lines
computed as if both factions agree.

## Related defects and compatibility

An explicitly supplied human `event_params` value must be an object. Empty
lists, false, zero, null and empty strings no longer collapse into an
empty/default plan. Omitting the field retains its existing supported meaning.

Previously an invalid Event could roll back its board effects but still consume
human eligibility and record the bad choice. Engine-marked rejections now keep
the decision pending for correction. Legal ineffective Events remain permitted;
`executed: false` alone is not a blanket rejection. Bot decisions retain their
separate decline/error handling. Regression tests cover stable pending IDs,
board/RNG/journal preservation, save/load and deterministic response replay.

The new terminal collectors expose current legal targets and quantities and
retain card/change display, `board`/`b`, timing windows and clean EOF handling.
Detached previews do not mutate the live state or random generator. A29/A36
owner requests accept explicit defaults; missing durable input remains pending.
Voluntary-removal timing authority remains with the original Event executor,
even when another faction owns a placement decision.

[AGENT_INTERFACE.md](../../AGENT_INTERFACE.md) lists all changed typed contracts.
Card 65's previous aggregate replacement fields are no longer silently converted
to physical choices. Affected saved transcripts may need new input where a
choice or decision signature changed; there is no new persistent save-format
version. Integer card 65 is distinct from expansion A65.

Source review also corrected NPC Event availability and defaults. These include
Aedui Wine's player-enemy restriction, Belgae Wine's Belgica-first priority,
German Allegiances' ineffective/Ally-benefit checks, A43's self-benefit and
maximum-effect policy, and missing mandatory A30/A36/A43 effects. A30 selects
a Region by Citadels, then Allies, then other Arverni pieces; a Leader does not
supersede those Region priorities. Seeded ties and scenario-specific faction
priorities remain in effect.

## Source basis

The supplied [card reference](../../Reference%20Documents/Card%20Reference),
[Ariovistus card reference](../../Reference%20Documents/Ariovistus/A%20Card%20Reference),
[Chapter 5](../../Reference%20Documents/Chapter%205) §§5.1, 5.1.1 and 5.1.3,
[Chapter 8](../../Reference%20Documents/Chapter%208),
[Chapter A8](../../Reference%20Documents/Ariovistus/Chapter%20A8) and each
faction's supplied Event instructions govern this work. All 47 supplied
reference files and `rules_consts.py` remain byte-identical. No outside rules
source or new provisional ruling was introduced.

A29's “up to” modifies its two Allies; its five-Warband/three-Auxilia phrase is
fixed as possible. Parallel wording in A35, A51 and base 19 supports this
reading. Roman NPC instructions separately require all three Auxilia. A36's
named subject governs both clauses. A43 applies the human recipient selection
before the normal replacement fallback; NPC selection policy considers feasible
alternatives without imposing its preferences on a human. These are reviewed
readings of supplied text, not claims of new designer clarifications.

## Validation and source identity

| Check | Accepted result |
|---|---|
| New regression cases | 177: 84 base validation, 39 German Allegiances, 54 expansion validation/CLI |
| Integrated focused suite | 202 passed on the final prepared source |
| Combined full suite before source commit | 6,728 passed; zero failures, errors or skips |
| Full suite before documentation commit | 6,728 passed; zero failures, errors or skips |
| Final audited bot matrix | 150 games: five scenarios, legacy seeds 1–20, original and second-edition seeds 201–205 |
| Mixed-seat replay | 30 distinct cases across five scenarios and three profiles, seeds 201–202; 120 executions including replay and hash seeds 0/7; no hard findings or partial actions |
| Strict error census | 20 executions, five scenarios and seeds 201–202 at both hash seeds; only 116 legal declines per hash, no errors |
| Reviewed baseline refresh | 100 fresh games exactly reproduced the final matrix's 100 legacy winner/card-count records; existing seed set and 15-point band retained |
| Immutable source inputs | 48/48 unchanged: 47 supplied references plus canonical constants |

Every final bot record completed its game and integrity audit, emitted four
rankings and agreed with the reported winner. Mixed-seat batch digests and
census results match across hash seeds. The counts above overlap; they are not
independent balance samples or totals to add together.

German Allegiances source commit: `b17e2f6d8297501c16288cfd5de04ae61b19a774`.
Combined Event validation and reviewed baseline commit: `d9fc7a3eb4bafea8f89fd881dd900bb2f353b90b`.
Final tested Python tree: **417 files**, SHA-256
`ed4c0d64f358e0f71a3852520d94ee71c6e561a46b8f8a53fc52b1edff23af9f`.
The final matrix and first combined full suite tested those bytes as prepared
changes over `b17e2f6`; the source commit and later documentation suite preserve
the identical Python tree. Patch and per-file manifests retain that provenance.

Earlier failures are retained rather than relabeled as successes. German
Allegiances' first full run exposed legitimate ineffective-Event compatibility;
its corrected standalone suite passed 6,590 tests. The base-only and expansion-only
full suites still failed the old balance canary. Expansion's first run also
exposed two A37 tests dependent on a now-changed earlier game trajectory. Those
tests now execute the exact original pre-A37 states and decisions captured from
`8db858b`, with their original assertions preserved and actual Ally placement
checked. An independent reviewer regenerated both fixtures. The old count-five
Alpine Tribes acceptance and Aedui Wine enemy expectation were corrected against
the supplied text, not relaxed to accommodate a failure.

## Changed game outcomes and reviewed baseline

Both integration attempts failed their comparison with the old baseline: the
largest faction win-rate shift was **20 percentage points**, above the existing
15-point guard. This was investigated before refreshing the baseline.

Against the immediate parent, **50 of 100 legacy games changed winner or length:
40 changed winners and 10 changed length only**. All 50 were traced in paired
parent/candidate games, with identical complete prefixes and state/RNG before
the first divergence. Their first causes were source-reviewed:

| First-cause family | Pairs | Explanation |
|---|---:|---|
| Base Event limits/defaults | 20 | Wine eligibility, legal target removals and Belgica priority; Avaricum legal seeded ties |
| German Allegiances | 13 | Declining ineffective Events or missing required NPC Ally benefit; obsolete Event dice no longer consumed |
| Expansion validation/defaults | 17 | A45 eligibility; mandatory A43/A36/A30 effects; A29's legal two Allies in one Region |

The causal review ran 100 diagnostic games: 50 parent games at `8db858b`
(Python SHA `d78d921cdb2db2c60bd433270bca2a80fb92462888610e8199522de41b749797`)
and 50 candidate games on pre-final Python SHA
`29f477d5382d87fac2abc4fe9e93ff4b8ca7abcfbad08e5bd0abb9bff2dfb9b5`.
All 50 parent captured-row replays match exactly; 47 candidate rows do too.
Three candidate decisions differ only in an unused nested Trade-region list's
ordering after sorted-JSON reload. Executing both variants produces identical
complete results, post-states and RNG; no production normalization masked this.
Some first divergences change the bot's decision, not just its execution.

The final A30 priority correction was made after those traces. A fresh final
matrix matches all 150 earlier final-state hashes, winners and lengths; mixed
and census results also match. Both captured A30 executions replay exactly on
the final source, and neither position contained an Arverni Leader. A separate
synthetic regression demonstrates the corrected Citadel-versus-Leader priority.
Old traces retain their actual source identity; the final-source equivalence
record provides the bridge rather than falsely relabeling them.

Independent review cleared all first causes and the baseline refresh. Updating
all 100 stored records changed 52 winner/length records relative to the older
stored baseline, which also includes prior accepted drift. The immediate-parent
comparison above isolates this batch. The old baseline and both failed matrix
comparisons remain archived. The baseline SHA-256 changed from
`207a129589d2bb17bec17319e70de7c8cf44d1572dc6aaca73cd0b39a9b5b8d3` to
`cbdfc7883ea0137fd5bf414ebc3bf847ec1774f42bd447d81a74ed268f9496c3`.
No guardrail threshold or test seed set changed. This is bounded causal evidence,
not an audit of every subsequent move or proof of balanced faction strength.

## Evidence and remaining scope

[Machine-readable results](event-validation-2026-11-03-results.json) and the
[verified evidence archive](event-validation-2026-11-03-evidence.zip) contain
raw tests, matrices, paired traces, source manifests, source reviews, exact A37
fixture capture, final A30 replay, baseline before/after records, and retained
earlier failures. The archive includes a per-file hash index and passed CRC
and content verification.

Other Event choice families remain separately tracked. This batch does not
close EXP-08's up-to choices, EXP-11's physical removals, base Event grant
ownership, ordinary action timing/physical choices, or seasonal decisions.
The separate NPC pre-Battle Intimidate projection lead remains unverified.
The 34 unverified inventory rows, two source questions and nine provisional
rulings retain their existing status. No overall game-correctness or statistical
balance certification is implied.
