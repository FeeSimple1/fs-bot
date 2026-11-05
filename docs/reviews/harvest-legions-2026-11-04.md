# First-Harvest Legion allocation — 4 November 2026

Client date: America/Chicago. Parent `d1ecfcda97d8a582500742b5776832f619c6754e`.
Tested working Python digest:
`a18ff10f42b7be8f71f9531f4fe131019d65cfccb7c429332ce720fab1535a81`
(489 Python files). The publishing commit includes this frozen source.

## Source and correction

The supplied Pax Gallica scenario's first-Winter rules require Romans to place
the three Winter Track Legions into any Belgica Region(s) at the start of
Harvest. The supplied A Scenario – The Gallic War repeats the Pax first Winter
after Interlude, except that an empty Winter Track places no Belgica Legions
and the Senate stays put. This also makes a positive expedition reserve subject
to the normal Harvest placement. Region ownership, Supply and Roman presence
are not placement requirements here.

Previously, every first-Pax-Harvest placement concentrated automatically in the
Region with the most Roman Legions plus Auxilia, using sorted-first ties. The
new `harvest_legions` request lets the Roman allocate the entire offered reserve
among any Belgica Regions. Invalid, partial, overlarge, outside, zero-entry,
Boolean and non-integer allocations are rejected before placement. A new
`place_piece(from_winter_track=True)` source debits the real Winter box, credits
map Legions, and refreshes Control without touching the Senate's Legions Track
or Fallen. It rejects overdraw and conflicting/wrong source types.

The terminal supports allocation and board inspection. Durable missing or
invalid responses retain their pending ID, inbox, board, RNG and unconsumed
first-Winter flags across rollback/save/resume. Accepted allocations replay
identically. All ten integer distributions of three Legions across three
Regions are covered. No decline is offered: placement is mandatory.

A related mechanics defect was exposed by the real post-Interlude integration
tests: Interlude installs first-Winter flags without the Pax placement count;
the old Harvest gate consumed its exception flag but never released a positive
reserve. The engine now uses that actual reserve once, while an empty box makes
no placement or request. Both human and NPC expedition paths are covered. This
is a source-backed correction, not a new provisional ruling.

## Compatibility and limits

Raw None or explicit delegation preserves the existing concentrated NPC
selection and `{region,legions}` result. Human allocations return
`{placements,legions}`. Smaller legacy reserves place only actual held Legions;
no counters are created to reach three. Without the first-Harvest rule/flag,
a held reserve is not released automatically. The new piece source cannot be
combined with Fallen or Senate-track sources and only places Roman Legions.

WS-F03 closes. WS-F02 remains open for Roman Interlude expedition and marker
choices, as do the other Interlude force/relocation ownership findings.
CV-PERSISTENCE, full Rampage victim choices, NPC Intimidate targeting and other
open findings retain their dispositions. All 47 references, canonical constants
and the balance baseline remain protected (49 inputs). No bot priorities or
balance thresholds were tuned.

## Validation

**7,963 tests pass** in the final full suite (218.93 seconds), with zero failures, errors or skips. **250 targeted tests pass**, including 46 new cases.
An isolated parent runs the unchanged new test file using existing Winter and
Interlude APIs: three behavioral failures reproduce the missing Roman choice
and human/NPC positive-reserve omission; three controls pass, with 40 other
cases deselected. Missing new APIs are not counted as proof. The first full run found seven
Spring frontend fixtures that delegated Quarters but assumed no earlier human
Harvest choice. They now explicitly delegate the mandatory allocation, verify
that it is logged once, and continue their Spring rejection/resume/replay
checks. The superseded run retains its original source digest and is separated
in the evidence archive; accepted results use the final digest above.

Ten native-bot games cover all five scenarios and seeds 1–2. Both mixed-seat
matrices use that seed set, hash seeds 0/987, reactions, Events and internal
replay (40 executions total). Their complete JSON outputs agree. The human
allocation policy changes only the two Pax cases relative to the previous
mixed checkpoint: total human turns remain 247 and Event attempts 77;
successful Events rise from 74 to 75. This is a changed synthetic trajectory,
not evidence of improved win rates. New mixed digest: `5dd20da48e8e672b`.

All ten native-bot records complete and audit successfully, with no errors or
integrity findings, four ranked factions, consistent winner/ranking fields and
nonempty final hashes. Every gameplay field and final hash matches the parent;
only elapsed seconds, commit and source digest are excluded from comparison.
Both mixed-seat outputs agree in complete JSON, with zero hard findings and
zero partials. The 100-game balance smoke passes; its largest absolute win-rate
difference from the stored historical baseline is 15 percentage points, with
35 winner changes versus that historical baseline. These are not 35 changes
versus this repair's parent. The
balance study retains seeds 1–20, all five scenarios, the same stored historical
baseline and the 15-percentage-point band. It must not be described as a
parent-vs-current comparison or a full rules proof.

## Progress

WS-F03 closes one original finding: **29/50 closed (58%), 21 open**. The
post-Interlude mechanics repair closes no additional original finding. The
separate defects, 34 unverified inventory rows, two source questions and twelve
provisional rulings are not absorbed into the denominator.

[Machine-readable results](harvest-legions-2026-11-04-results.json) ·
[Evidence archive](harvest-legions-2026-11-04-evidence.zip)
