# Germanic Horse Region choices — 5 November 2026

Client date follows America/Chicago. Parent
`1322980ee13241feba3057cdb04a2cd8a00349a5`.
Frozen Python digest
`693cfe397282ec48411d56011afbf5c600f836858376ddd08430e1eb2fc190a2`
across 520 files. The publishing commit includes that source.

## Sources and behavior

Card Reference 59 unshaded lets Romans use the full Auxilia Loss rate in one
Battle Region per Command, attacking or counterattacking. Shaded gives its
Gallic owner doubling in one Battle Region, attacking or defending, subject
to its printed protection exceptions. The old executor selected Regions using
most Roman Auxilia, alphabetic attacking Region, or most defending owner
pieces, without consulting the player.

Ordinary and free Battle plans now ask the owning Roman/Gallic seat through
`horse_region`. Requests list actual participating Battles, the actual first
ranked defender, ordered Regions, Auxilia counts and current shaded protection.
Unshaded may decline. Shaded says to select one Region and has no unprinted
decline; a currently protected Region can still be selected without bypassing
its protection. Zero-Auxilia choices remain legal. Third-party Roman presence
alone does not create an ordinary Horse bonus, independently of Slingers'
already implemented combined-capability pre-fire Tip.

Shaded attack doubling is blocked by a defending Fort or Citadel. Counterattack
doubling is blocked by the owning defender's Citadel, while its Abatis alone
allows doubling. A64 says Abatis acts as a Fort when defending. Both the actual
Battle loss calculation and the general loss estimator formerly halved Losses
for Abatis but still doubled them for attacking Horse. Both now suppress that
doubling. Existing A31 cancellation of Abatis is honored. Rates and doubling
still apply before the existing halving/rounding procedures.

Chapter 8 §8.3.3 supplies the first applicable selected Region for default
Non-player use, replacing the old role-specific heuristics. Each Battle Command
now scopes its own two Horse flags. Completion and interruption remove that
Command's flags, and an inner Battle restores its outer Command's selection.
Raw execution cleans its flags before propagating an interruption; full board,
payment and RNG rollback remains the enclosing human transaction's job.

## Interfaces and scope

Terminal play offers live Regions, current protection, permitted decline and
`b`/`board` inspection. Durable sessions validate offered Regions and current
combatants. Missing, malformed or stale responses remain pending across
rollback/save/resume. An accepted Region survives a later casualty pause and
replays with the same final board and random state. Previews consume no live
human input or RNG. Free Event Battles use the same owner-scoped choice.

The private prospective Battle queue still activates Card 13 and Card 59
automatically as actual targets arrive. That human-choice gap remains under
BE-09 and is explicitly retained by a regression control. Older cross-revision
histories can stop at the new request or diverge from the corrected default
selection and Abatis interaction. No source question or provisional ruling is
added by this repair.

## Verification

**8,688 tests pass**, with zero failures, errors or skips (408.94 seconds).

There are 64 new cases and 364 passing focused tests. They cover every scenario,
both sides and combat roles, decline rules, all three former priority branches,
Fort/Citadel protection, active/cancelled Abatis, current ranked defenders,
forged and stale responses, terminal inspection, free Event execution, preview
isolation, interrupted/nested flags, actual combat, invalid pending responses
and accepted choices through later casualties and save/load/replay.

Nine unchanged probes use only parent APIs. The parent fails seven behavioral
checks for owner choices, Roman decline, first-applicable selection, Abatis
protection and interrupted flags, while two controls pass. All nine pass on
the repaired source.

Paired native NPC games cover all five scenarios and seeds 1–2. Mixed-seat runs
use those seeds under hash seeds 0 and 987 with internal replay. The historical
balance guard uses seeds 1–20 in all five scenarios, its unchanged baseline
and the existing 15-percentage-point band. Directed tests exercise the new
choices; these game matrices are bounded general regression evidence.

All ten native NPC records complete and audit cleanly, with four ranked
Factions, consistent winner/ranking output and only legal-decline diagnostics.
Nine match every parent gameplay field and final board hash, excluding elapsed
seconds, commit and source identity. The Great Revolt seed 2 has the same
winner but different margins, Resources and surviving forces.

A paired trace finds its first differing Battle on card 20: the parent flags
Nervii for shaded Horse while the first selected Battle is Pictones. The repair
flags Pictones, increasing that attack from two Losses to four. Before the
Battle, the complete position excluding only Horse flags is identical.
Restoring only the old Horse selection policy on the accepted code reproduces
every parent gameplay field and final board hash for that game. Supplemental
trace reruns and the labeled counterfactual are separate from native totals.

The complete mixed-seat JSON outputs match across hash seeds 0 and 987. They
cover 312 human turns, 86 Event attempts and 82 successful Events, with zero hard
findings and zero partial games. Their digest is `86d111a84d18a59c`.
Internal replay gives 40 executions total. The historical 100-game balance
check passes the existing band, with a maximum difference of
15 percentage points and 36 winner changes versus the historical baseline. Those
historical comparisons are separate from the paired parent/current NPC
comparisons.

All 49 protected inputs match the parent byte for byte, comprising 47 supplied
references, canonical constants and the historical balance baseline. Archive
checksums and reconstruction of all 520 Python files verify the accepted source
digest. The first directed run exposed a test harness that left later casualties
unanswered after its accepted decline. That fixture now controls Horse alone;
a separate test retains the full later-casualty continuation. Superseded
development logs are retained separately.

## Progress

Ordinary/free Battle Card 59 choices are repaired. **BE-09 remains open** only
for the private prospective queue's Card 13/59 human choices. Original bundle
progress remains **39/50 closed (78%), 11 open**. Separate mechanics leads,
34 unverified inventory rows, two source questions and twelve owner-adopted
provisional rulings retain their dispositions.

[Machine-readable results](horse-choice-2026-11-05-results.json) ·
[Raw evidence archive](horse-choice-2026-11-05-evidence.zip) ·
[Current status](../current-status.md) · [Progress](../human-choice-progress.json)
