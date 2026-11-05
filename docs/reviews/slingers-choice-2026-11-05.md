# Balearic Slingers Region choice — 5 November 2026

Client date follows America/Chicago. Parent
`12097614a156f17b9252ac057337c0198f697a6b`.
Frozen Python digest
`c3d6381742446be9489e203652053fe1596fdb0f5eac7a4f1c33c1afce87e205`
across 517 files. The publishing commit includes that source.

## Sources and behavior

Card Reference 13 unshaded assigns Romans one Region per enemy Battle Command
for initial Auxilia fire, including Ambush and an attacker fighting a third
Faction. The executor formerly chose the Region with the most Roman Auxilia
without asking. Ordinary and free Battle plans now present `slingers_region`
to the Roman seat before payments or pre-fire. The request lists selected
Battles with both combatants still present, their actual defending Factions
and Roman Auxilia counts. Ranked target lists use their actual first target.

Romans select one offered Region. Card 13 says to choose one and does not
provide a decline. A selected Battle with zero or one Auxilia remains a legal
choice even when it causes zero Losses. If no selected Battle has any Roman
Auxilia, the zero-effect capability creates no prompt. The selected Region
is used only once. Its Auxilia count is read again when pre-fire resolves.
Missing or stale combatants cannot be selected in the live response.

Both Card 13 and Card 59's printed Tips say that, when both capabilities are
unshaded, Auxilia inflict one initial Loss each instead of one-half. The old
pre-fire calculation ignored this. It now uses the printed rate, rounded down
at one-half otherwise. This initial-fire bonus follows possession of both
capabilities, independently of which Region receives Horse's separate ordinary
Battle bonus. Card 59's own human Region selections remain outside this repair.

Chapter 8 §8.3.3 directs a Non-player's limited-Region Capability to the first
applicable Region. The ordinary Slingers default now follows the selected
Battle order instead of maximizing Auxilia. Raw `None` or explicit delegation
uses that corrected default. The private prospective queue already uses first
applicable activation; its automatic Roman choice remains a separate open
part of BE-09. No new source question or provisional ruling is introduced.

## Interfaces and scope

Terminal play provides ordered Regions with counts and target identities,
with live `b`/`board` inspection. Durable human sessions require one valid
Region or explicit default. Invalid/missing answers remain pending, restoring
board, payment and random state. The accepted Region survives a subsequent
Roman casualty prompt, save/load and replay. Previews do not consume live
input or RNG. Ordinary/free Battle plans in all five scenarios and free
Event Ambushes use the new choice, including third-party Roman fire.

The private prospective Battle queue used by numeric 67's NPC branch can
select a later Region only after arrivals from an earlier Retreat. It retains
its existing automatic Slingers activation in this scoped repair. It is not
covered by the new Roman menu. BE-09 also retains Card 59's own Region choices.
Older cross-revision histories can stop at the new request or diverge from the
corrected default priority and combined pre-fire rate.

## Verification

**8,624 tests pass**, with zero failures, errors or skips (277.28 seconds).

There are 44 new regression cases and 235 passing focused tests. Coverage
includes every scenario, non-default Region choice, zero-Loss choices,
defense and third-party fire, Event Ambush, independent Horse selection,
combined-capability rates, exact Command-order NPC priority, malformed/stale
responses, inactive cases, ranked targets, terminal inspection, preview
isolation, pending/save/resume and replay after later Roman casualties.
A control explicitly records the prospective queue's remaining automatic use.

Six unchanged probes use only parent APIs. The parent fails two Roman-choice
probes, the combined-capability fire-rate probe and the first-applicable NPC
probe. Its two standard/default controls pass. All six pass on the repair.

Audited NPC comparisons cover all five scenarios and seeds 1–2. Mixed-seat
matrices use those seeds under hash seeds 0 and 987, including internal replay.
The historical balance guard uses seeds 1–20 in all five scenarios with its
unchanged baseline and 15-percentage-point band. These are bounded general
regressions; the directed tests exercise the new decision and the changed
rules, including the saved later-casualty continuation.

All ten standard NPC records complete and audit cleanly with four ranked
Factions, consistent winner/ranking output, no integrity findings and only
legal-decline diagnostics. Every gameplay field and final board hash matches
the parent, excluding elapsed seconds, commit and source identity.

The complete mixed-seat JSON outputs match across hash seeds 0 and 987. They
cover 314 human turns, 91 Event attempts and 85 successful Events, with zero hard
findings and zero partial games. Their digest is `2d71a817ecdd8b56`.
Internal replay gives 40 executions total. The historical 100-game balance
check passes the existing band, with a maximum difference of
15 percentage points and 35 winner changes versus the historical baseline. Those
historical comparisons are separate from the ten exact parent/current NPC
comparisons.

All 49 protected inputs match the parent byte for byte, comprising 47 supplied
references, canonical constants and the historical balance baseline. Archive
checksums and reconstruction of all 517 Python files verify the accepted source
digest. The first directed run paused the later-casualty fixture at its earlier
Retreat request. The fixture now delegates Retreat and retains its casualty
continuation assertions. The superseded development log is retained separately.

## Progress

This advances BE-09 for ordinary/free Battle Card 13 selection. **BE-09 stays
open** for the prospective queue's Roman Slingers selection and Card 59's
both-side Region choices. Original progress remains **39/50 closed (78%),
11 open**. Separate mechanics leads, 34 unverified inventory rows, two source
questions and twelve owner-adopted provisional rulings retain their dispositions.

[Machine-readable results](slingers-choice-2026-11-05-results.json) ·
[Raw evidence archive](slingers-choice-2026-11-05-evidence.zip) ·
[Current status](../current-status.md) · [Progress](../human-choice-progress.json)
