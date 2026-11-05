# Roman Interlude decisions — 4 November 2026

Client date follows America/Chicago. Parent `aec38386839b7a6e3653c9b6b12812cf36de6657`.
The accepted Python digest is `0f1171979d2ee624a2697545a6f68054f23e8e05a4e5dce025f843af66fe0f39`
across 505 files. The publishing commit includes that source.

## Rules and implementation

The supplied A Scenario - The Gallic War, Britannia Expedition and Spring
sections assign these choices to Romans. Conducting reserves exactly three
map Legions in the Harvest box and relocates the Roman Leader, three or more
additional Legions and one or more Auxilia to Britannia. Declining or being
unable applies the printed Belgic placement and Senate shift. Before Spring,
Romans may preserve one Dispersed or Dispersed-Gathering marker as it is.
The supplied scenario includes the designer clarification that the cited
A8.8.9 reference is spurious and that this instruction is self-contained.

The old handler accepted a conduct flag while ignoring physical allocations.
The normal Winter path silently conducted an expedition and omitted marker
preservation. Two Roman-owned requests now expose these choices to terminal
and durable sessions. Allocations validate exact origins, visibility, positive
integer counts, minimum totals and combined Legion capacity before movement.
Legions reserved for Harvest use the piece-operation helper so conservation
and Region Control update together. Spring counters exclude the preserved
marker's unperformed transition.

A pause at the marker request preserves the earlier accepted expedition in
the durable journal. The Interlude and Winter round restore on failure, with
the latter also restoring the Winter counter. The direct Winter API can be
retried after EOF without incrementing twice or skipping the Interlude.
Board inspection is available at every terminal allocation prompt.

## Compatibility

NPC defaults retain the existing minimum force and physical selection order.
Explicit raw booleans and conduct-only true dictionaries retain their older
minimum-force contract. Exact raw dictionaries now honor their selections,
and unknown fields are rejected. Human sessions require the complete choice
or explicit default delegation. Older transcripts that previously passed the
Interlude automatically may need the new Roman responses. Saved game data
continues using the existing journal and pending-decision representation.

## Verification

**8,373 tests pass**, with no failures, errors or skips, in 430.12 seconds. All 330 focused tests pass. The new regression file contains
53 cases. Focused coverage includes both marker faces, extra expedition
quantities, exact Auxilia visibility, repeated-cohort overclaims, malformed
payloads, insufficient forces, Roman ownership, terminal board inspection,
NPC defaults and direct Winter retries. Full Winter tests pause at each new
request, reject invalid input and preserve the accepted expedition across a
later pause, saved-game reload and replay for both conduct and decline.

The same six baseline-API probes run on the parent and repaired tree.
Four parent behavioral failures reproduce the missing request, ignored
physical force, skipped marker preservation and unchecked invalid marker.
Two legacy controls pass. All six pass on the repair.

Validation uses all five scenarios and seeds 1–2 for paired audited NPC games
and mixed-seat runs under hash seeds 0 and 987 with internal replay. The
historical balance guard uses all five scenarios and seeds 1–20, with its
existing baseline and 15-point band. All ten audited NPC records and final board hashes match the parent, excluding
only elapsed seconds, source digest and commit identity. The Gallic War seed-1
record completes the Interlude. Every record completes and audits cleanly,
with four ranked factions, no errors, no integrity findings and consistent
winner/ranking fields.

Both complete mixed-seat JSON outputs match across hash seeds, covering 356
human turns and 96 Event attempts, with 90 successful Events, zero hard
findings and zero partial games. Their batch digest is
`d899b5732da10db5`. Internal replay yields 40 executions in total.
The 100-game historical guard passes with a maximum difference of 15
percentage points and 35 different winners versus its historical baseline.
All 49 protected inputs, comprising 47 game references, canonical constants
and the balance baseline, match the parent byte for byte.
Frozen source and protected inputs are verified by the archived script. The earlier full-suite run was superseded when
the direct Winter retry repair was added, and its available logs are kept in
the superseded evidence section. A separate initial batch launched from the
wrong working directory is also marked superseded, with its actual metadata.

## Progress

WS-F02 closes one original finding, bringing the bundle to **36/50 closed
(72%), 14 open**. WS-F01 covers the remaining Interlude force reductions and
Cisalpina relocations. Separate mechanics leads, 34 unverified inventory rows,
two source questions and twelve adopted provisional rulings retain their
recorded dispositions.

[Machine-readable results](interlude-roman-choices-2026-11-04-results.json) ·
[Evidence archive](interlude-roman-choices-2026-11-04-evidence.zip)
