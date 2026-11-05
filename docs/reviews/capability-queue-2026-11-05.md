# Mandatory capabilities in prospective Battles — 5 November 2026

Client date follows America/Chicago. Parent
`502749f7341da46d8b7108043fbb8de22184bae6`.
Frozen Python digest
`9f1e25a3b40487698e087aab9287d73564a63f7c0a2df9eb432810352ba132f6`
across 526 files. The publishing commit includes that source.

## Provisional adoption and behavior

The owner adopted the preceding queue-timing recommendation, expressly subject
to official correction. [PR-13](../provisional-rulings.md#pr-13) and the
[question ledger](../../QUESTIONS.md#q-capability-queue-timing--reserving-mandatory-one-region-capabilities-5-november-2026)
record the gap, adopted procedure and provisional status. No external research
was performed. The supplied Card Reference 13/59, §5.1.3 and §8.3.3 remain the
sources for the printed effects and non-player priority.

`capability_window` asks Card 13 unshaded's Roman owner or Card 59 shaded's
recorded combatant owner to activate here or reserve while later queue
candidates remain. The final candidate, if it becomes a Battle, offers only
activation. There is no general decline. Reservation consumes no use and can
expire if no later eligible Battle occurs, without rewinding or inventing
combat. Activation consumes the capability's one use for that Command.

The window occurs after actual target selection, cooperation and payment,
before pre-fire. Absent candidates offer nothing. Real Retreat arrivals can
create a later window. Slingers can select a third-party Battle and a
zero-Auxilia Region; shaded Horse can select a protected Region without
bypassing its live restrictions. The two capabilities track independent uses.
Both terminal and durable sessions support live board inspection, validation,
rollback, accepted earlier reservation, save/resume and deterministic replay.
Horse's existing scope restores outer selections on interruption.

Non-player/raw delegation retains first-applicable use. The prospective
shaded-Horse default now consults the shared Abatis protection predicate as
well as Fort/Citadel protection, matching the ordinary-plan repair. A blocked
Battle does not waste its default use. This default behavior is distinct from
a human's explicit choice to consume the use in that Region.

PR-11 forecasts branch legal human actions using the existing isolated
reaction-history mechanism and lower Legion-Loss evaluation. NPC responses
still delegate. Forecasts consume no live input or random state. Numeric 67
always forecasts its attacker as NPC; the shaded-Horse human adapter test uses
a different human owner to exercise that shared response path independently.

## Verification

**8,769 tests pass**, with zero failures, errors or skips (247.06 seconds).

There are 53 new cases and 279 passing focused tests. Coverage includes all
five scenarios, one-use limits, final-candidate activation, malformed/decline/
reservation rejection, absent candidates, reservation expiry, real Retreat
arrivals and live pre-fire, third-party zero-Auxilia selection, protected and
defensive Horse ownership, independent capability uses, stale Battles,
terminal inspection, rollback, invalid saved final responses, accepted earlier
reservation, save/load/replay, exception cleanup, pure forecasts and NPC controls.

Five unchanged probes use only parent APIs. Three fail behaviorally on the
parent (two human reservation paths and missing human forecast branching),
while two first-applicable NPC controls pass. All five pass on the repair.
They do not fail because the parent lacks a new import or request helper.

All ten standard NPC records complete and audit cleanly with four ranked
Factions, consistent winner/ranking output, no integrity findings and only
legal-decline diagnostics. Every gameplay field and final board hash matches
the parent, excluding elapsed seconds, commit and source identity.

The complete mixed-seat JSON outputs match across hash seeds 0 and 987. They
cover 312 human turns, 86 Event attempts and 82 successful Events, with zero hard
findings and zero partial games. Their digest is `86d111a84d18a59c`.
Internal replay gives 40 executions total. The historical 100-game balance
check passes the existing band, with a maximum difference of
15 percentage points and 36 winner changes versus the historical baseline. Those
historical comparisons are separate from the ten exact parent/current NPC
comparisons.

All 49 protected inputs match the parent byte for byte, comprising 47 supplied
references, canonical constants and the historical balance baseline. Archive
checksums and reconstruction of all 526 Python files verify the accepted source
digest. All directed and focused runs pass. BE-09 closes under owner-adopted
provisional PR-13, subject to official correction.

## Disposition and compatibility

BE-09 closes after the preceding Ballistae, ordinary/free Slingers/Horse and
optional Horse queue repairs. **Original audit: 40/50 closed (80%), 10 open.**
Two unadopted source questions, thirteen provisional rulings and 34 separate
unverified inventory rows remain outside that closed-finding count. Separate
mechanics leads retain their dispositions.

PR-13 remains provisional, subject to official correction. Older cross-revision
histories can pause at the newly required capability window or diverge under
expanded human-response forecasts. Existing same-revision save/load and replay
are covered; this does not claim cross-revision transcript equivalence.

The companion [results JSON](capability-queue-2026-11-05-results.json) and
[evidence archive](capability-queue-2026-11-05-evidence.zip) preserve the
measurements, commands, raw outputs, source reconstruction and checksums.
