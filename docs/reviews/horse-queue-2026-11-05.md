# Optional Horse in prospective Battles — 5 November 2026

**Subsequent disposition, 5 November:** the owner adopted provisional PR-13.
The [mandatory queue follow-up](capability-queue-2026-11-05.md) implements it
and closes BE-09. The measurements below describe this earlier revision.

Client date follows America/Chicago. Parent
`fee12ab101a2aa079ed4c295295f39ac2ad1f02a`.
Frozen Python digest
`0b00cd086e6c6b5956ee0bdaa831617b168b67de39b2e3553abe1dfe65cfe958`
across 523 files. The publishing commit includes that source.

## Printed optional choice

Card Reference 59 unshaded says “Romans may” use full Auxilia Losses in one
Region per Battle Command. Numeric 67's private queue selects only actual
Battles as it reaches each candidate; an earlier Retreat can bring Romans
into a later Region. Its old capability path automatically spent Horse in the
first applicable Battle, even for a human Roman.

A live `horse_window` now lets Romans activate here, reserve for a later
Battle, or decline for the rest of the Command. Only an actually selected
Battle with both combatants and Roman Auxilia offers the choice. Future
queue candidates are shown as potential Regions, not promised Battles.
Reservation consumes no use. Activation or whole-Command decline prevents a
second request/use. The last candidate offers no reservation. If reservation
is followed by no further eligible Battle, the explicitly optional effect
expires unused. Raw/NPC deferral retains first-applicable activation.

## Actual play and prediction

The window follows target presence, cooperation and Battle payment. A Retreat
arrival can create a fresh later window with its live surviving Auxilia count.
The terminal supports inspection and labels reservation's uncertainty. Durable
missing/invalid responses remain pending, with enclosing action board/RNG
rollback. Earlier accepted reservation survives a saved second window and
replays with identical board/random state. Existing Horse Command scoping
clears activation flags at completion and protects nested Command boundaries.

PR-11's Arduenna forecast now branches these optional human responses and
uses the lower Legion-Loss prediction. NPC forecast behavior still delegates
to its ordinary first activation. Forecast signatures include the optional
choice history, and previews consume no live input or RNG. Directed policy
checks exercise all four activation/reservation/decline continuations using
a controlled Battle outcome, separately from the actual Retreat-arrival test.

## Source question kept open

Card 13 unshaded and Card 59 shaded lack unshaded Horse's “may”. Their existing
queue activation remains automatic. The supplied texts do not specify how a
mandatory one-Region choice can be reserved when unfinished combat/Retreat
can make later Battles appear or disappear. Chapter 5 §5.1.3 also requires
fulfilling possible Event effects.

[Q-CAPABILITY-QUEUE-TIMING](../../QUESTIONS.md#q-capability-queue-timing--reserving-mandatory-one-region-capabilities-5-november-2026)
records the sources, alternatives and a recommendation: allow use now or
reservation while later queue candidates remain, without guaranteeing another
chance or rewinding combat if none occurs. The final candidate permits use
here without a reservation or general decline. **That recommendation is not adopted or
implemented for those two capabilities.** No external research or additional
provisional ruling is claimed. The separate optional Horse path is complete.

Older cross-revision histories can stop at the new optional request or differ
under the expanded human-response forecast. Ordinary/free-plan Card 13/59
Region menus remain implemented.

## Verification

**8,716 tests pass**, with zero failures, errors or skips (469.03 seconds).

There are 28 new cases and 226 passing focused tests. They cover use/reserve/
decline, one-use limits, skipped candidates, reservation expiry, actual Retreat
arrivals, terminal inspection, malformed/stale input, pending/save/resume,
earlier acceptance, second-window replay, pure human forecast branching and
unchanged NPC delegation. Window mechanics are checked in all five scenarios;
the concrete numeric 67 Event queue remains subject to its scenario context.

Five unchanged probes use only parent APIs. The parent fails reservation,
whole-Command decline and human forecast branching; its two raw/inactive
controls pass. All five pass on the repair.

Audited NPC pairs use all five scenarios and seeds 1–2. Mixed-seat runs use
those seeds under hash seeds 0 and 987, with internal replay. The historical
100-game guard uses seeds 1–20, its unchanged baseline and 15-percentage-point
band. Directed tests exercise the new window and continuations; game matrices
are bounded general regression evidence.

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
checksums and reconstruction of all 523 Python files verify the accepted source
digest. All directed and focused runs pass. Q-CAPABILITY-QUEUE-TIMING explicitly
retains the two mandatory-capability paths as open, without claiming a
new ruling or closing the grouped finding.

## Progress

BE-09 remains open for mandatory Card 13/59-shaded queue timing. Original
progress stays **39/50 closed (78%), 11 open**. There are now three unresolved
source questions, twelve adopted provisional rulings and 34 unverified
inventory rows, separate from other mechanics leads and the original bundle.

[Machine-readable results](horse-queue-2026-11-05-results.json) ·
[Raw evidence archive](horse-queue-2026-11-05-evidence.zip) ·
[Current status](../current-status.md) · [Progress](../human-choice-progress.json)
