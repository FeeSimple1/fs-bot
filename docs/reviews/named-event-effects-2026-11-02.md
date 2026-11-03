# Named-faction Event choices — 2 November 2026

This task addresses **BE-04** from the [human-choice audit](human-choice-audit-2026-10-29.md):
optional effects assigned to a named faction must be decided by that faction,
even when someone else plays the Event. It covers base 2/18/23 unshaded and
26 shaded, plus the directly related expansion A18 unshaded.

The [progress register](../human-choice-progress.json) records **18 of 50 findings
closed (36%), with 32 open**. This one-finding task is **1/1 complete (100%)**.
These percentages count grouped findings, not equal effort units or overall
rules accuracy. This report uses America/Chicago dates; validation occurred
on 3 November UTC. The preceding report used its UTC date.

## Rules and behavior

| Event | Decision owner and permitted effect |
|---|---|
| Legiones XIIII et XV (2 unshaded) | Romans accept or decline the Senate shift and choose the two Legions' track/Fallen allocation, carried out as possible. The shift must move or flip the Senate marker; Firm Uproar and an off-track Senate do not qualify. |
| Rhenus Bridge (18 unshaded) | Romans accept or decline and select a Germania Region under or adjacent to Roman Control; all German pieces there are removed. |
| Rhenus Bridge (A18 unshaded) | Same Roman ownership, with the expansion's additional prohibition on a Region containing named Ariovistus. All German pieces includes Scouted Warbands, Settlements and a Successor. |
| Sacking (23 unshaded) | Romans accept or decline and select a City at Roman Control. Its contents are replaced with Razed status and Romans gain eight Resources, subject to the ordinary cap. Human choices include already-Dispersed or Razed Cities where otherwise legal. |
| Gobannitio (26 shaded) | Arverni decide whether to take the optional sequence, select any Allied Tribes to remove in Arverni Region, place their own Allies legally there, then receive the free Rally within one Region of actual Vercingetorix. An empty rearrangement remains legal; the subsequent Rally can be accepted or declined separately. |

The supplied [Card Reference](../../Reference%20Documents/Card%20Reference),
[A Card Reference](../../Reference%20Documents/Ariovistus/A%20Card%20Reference),
[Chapter 5](../../Reference%20Documents/Chapter%205) §§5.1–5.1.3 and 5.4,
[Chapter 8](../../Reference%20Documents/Chapter%208), and faction-specific
Event instructions govern these choices. No new provisional ruling or outside
source was introduced. The placing faction supplies its own Allies unless
explicitly stated otherwise; Gobannitio's shaded side does not override stacking
or permit removal of Citadels.

Non-player behavior uses the named faction's instructions and priorities.
Roman Card2 instructions require both Legions; a human may accept a legal
shortfall under partial execution. There is no printed track-versus-Fallen
preference, so equal complete allocations use seeded selection. Human target
legality is not narrowed to the non-player's preferred targets.

## Additional defects

The previous Card2 non-player path could shift the Senate yet supply no Legion
placement parameters. Accepting the effect now supplies its required placements.
A18 also previously left Scouted Warbands and a German Successor behind despite
its all-pieces removal text. The named Ariovistus remains protected by the card's
explicit targeting restriction.

An initial concern about Sacking removing an unrelated Citadel did not reproduce
on a legal board: normal City/Citadel stacking prevents that position. Any
simplification of that code is not counted as an additional confirmed bug.
The earlier EXP-12 repair covered four other named remove-all Events; A18's
newly verified case does not alter that historical scope or add an original
finding to the denominator.

## Human interfaces and compatibility

The new `free_action` request type is `named_event_effect`. It carries the
card identity, named `acting_faction`, legal options and explicit decline/default
support. Romans select Legion source counts, a Rhenus Region or a Sacking City;
Arverni supply ordered exact Tribe removal/placement lists. Unknown fields,
wrong owners, invalid targets and malformed counts reject. A18 retains its old
`region` alias when it agrees with `target_region`.

The initial terminal Event plan defers choices to the live named-owner request.
A same-owner typed Event may also supply its own choices directly. Another
executor cannot supply those choices. A sole strict `decline: true` skips the
optional effect; `use_default: true` explicitly requests the NPC policy.
Gobannitio offers a separate “skip Ally changes; decide Rally” route.
See [AGENT_INTERFACE.md](../../AGENT_INTERFACE.md) for complete response shapes.

Owner responses retain supported component timing steps, but reject ignored
reply-level timing fields, unknown step names and invalid indices. Original
Event timing still includes handler completion and the Gobannitio Rally grant
under the executor's authority. A later legal Legion reclamation can open a
new source allocation; the menu offers it and execution preserves the chosen
timing rather than moving the reclamation earlier. The full possible two-Legion
quota remains enforced.

Old affected transcripts may need newly required owner choices. There is no
persistent save-format version change; numeric26 remains distinct from A26.

Missing or invalid durable replies must remain pending, preserving the stable
decision ID, live board, random state and accepted history. Explicit defaults
are distinct from absent input. The terminal menus retain current card/change
information, `board`/`b`, detached planning and clean EOF handling. Voluntary
piece-removal authority remains distinct from the named effect's decision owner.

## Validation and source identity

| Check | Accepted result |
|---|---|
| New regression cases | 144: 77 engine, 42 terminal, 25 durable-session cases |
| Combined focused check | 430 passed |
| Independent focused review | 320 passed with source unchanged throughout |
| Full suite before implementation commit | 6,872 passed; zero failures, errors or skips |
| Full suite before documentation commit | 6,872 passed; zero failures, errors or skips |
| Final bot matrix | 150 audited games across five scenarios: legacy seeds1–20, original and second-edition seeds201–205 |
| Mixed-seat replay | 30 distinct cases, seeds201–202 in all three profiles; 120 executions including replay and hash seeds0/7; zero hard findings or partial actions |
| Strict census | 20 executions; only119 legal declines per hash, no errors; matching results across hashes |
| Protected inputs | All49 unchanged: 47 supplied references, rules_consts.py and balance baseline |

Every bot game completed its integrity audit, emitted four rankings and matched
the reported winner. Cross-hash mixed-seat digests match. Focused/full suites
and repeated games overlap and must not be added as independent samples.

Implementation commit: `9e9191bc1c0eb5de13a5d578475d4f85042d2a6b`. The tested tree has **422 Python files**,
SHA-256 `9d4cc73f2efaa33b8e6ad871fb432ae43c7471d5222b1c13d9c9b571c0c3c4a8`. The first full suite and matrix measured
these exact bytes as prepared changes over `2edf53e`; the source commit and
later documentation suite use the same bytes. Per-file manifests and the
prepared patch preserve that distinction.

The existing Gobannitio Citadel-as-Ally test now expects rejection of that
illegal target and retains its original unchanged-Citadel assertions. No test
threshold or scenario seed was relaxed. Earlier focused failures are retained,
including witnesses for foreign Spring timing, a reclaimed Legion's late source
choices and an initially rejected outer Rally timing point. Clean-parent
mechanical witnesses demonstrate Card2's missing Legions and A18's remaining
Scouted Warband/Successor; corrected witnesses preserve state integrity.

## Outcomes and evidence

The original100-game balance comparison passes without a baseline refresh.
Its largest faction win-rate change is **10 percentage points**, within the
unchanged15-point guard. Baseline SHA-256 remains
`cbdfc7883ea0137fd5bf414ebc3bf847ec1774f42bd447d81a74ed268f9496c3`.

**Sixteen games changed winner or length: ten changed winners and six changed
length only.** The bounded causal review ran32 diagnostic games, exactly16
parent/candidate pairs, reproducing their recorded outcomes. The raw first
trace differences have identical complete prefixes and pre-states/RNG.
Eight first causes are Card2 Legion placements; two are Card18 removals; six
change bot decisions under corrected Event availability. Independent source
review verified all 16 first causes and all 32 trace hashes, with no new blocker.

New accepted/acting-faction return metadata is distinguished from gameplay
changes. None of these16 first rows differs only in that metadata. In the two
Gallic War A18 cases, the first difference changes the chosen action without
changing the immediate post-state. Their state changes follow at the next
execution; only the earlier decision has the identical-prestate claim.

The source commit overlapped the diagnostic run. All32 games completed and
matched their expected outcomes, and all422 candidate Python hashes passed
both boundary checks. The original final whole-identity check failed because
the Git commit changed. That failure and the real start/end identities remain
in the archive; separate manifest/committed-tree verification confirms no
Python change. These records are not relabeled as an originally clean command,
and no diagnostic games were rerun merely to erase the metadata failure.

Initial captured-row replays matched exactly in 31 of 32 cases. The remaining
candidate snapshot lost map insertion order when diagnostic JSON sorted its
keys, changing an unused Trade detail list and its confirmation signature.
Restoring the original map order reproduced the exact decision, complete
post-state/RNG and following execution. Independent review reproduced both the
original mismatch and its resolution. The failed attempts remain in the
archive; this is a diagnostic serialization limitation, not a production fix.

[Machine-readable results](named-event-effects-2026-11-02-results.json) and the
[evidence archive](named-event-effects-2026-11-02-evidence.zip) retain source
reviews, witnesses, logs, JUnit results, per-game records, paired traces and
source manifests. The archive is verified against its per-file SHA-256 index
and ZIP integrity checks. These checks
explain bounded first divergences, not every later move or statistical balance.

## Remaining scope

Other base Event grants, Battle selections, Drought losses, Capability choices
and Gallic Shouts' private peek remain separately tracked. This repair does not
complete general Command/Special Activity timing, exact physical casualty
choices, seasonal decisions or shared-player/setup support. The 34 unverified
inventory rows, two source questions, nine provisional rulings and separate
NPC pre-Battle Intimidate projection lead retain their current status.
