# Scout allocation repair — 4 November 2026

Client date: America/Chicago. Parent `a7fc41005705d0255034b4239d9f5091d28176c0`.
Tested working Python digest:
`51e1c13b45ee217dcbeeaabea806ea094575b8cac1fe54258a1948b5ac5edf2c`
(502 Python files). The publishing commit includes this frozen source.

## Source and correction

Chapter 4 §4.2.2 permits each Hidden Auxilia flipped to Reveal up to two
Warbands in the same Region, including already Revealed Warbands. Place a
Scouted marker where none exists; §4.1 makes the executing faction's physical
selections its own. §4.1.2 governs Leader reach; Card 12 shaded restricts Scout
Reveal to one Region. §4.2.2 prohibits Scout movement into/out of Britannia,
while §4.1.3 concerns an accompanying March crossing its boundary. Reveal in
Britannia itself remains possible if its separate conditions are met.
A4.2 does not replace Scout's Reveal procedure. A1.4 and Card 38 cooperation
retain the physical owners of Roman Auxilia and Aedui Warbands.

Previously the primitive accepted multiple factions but chose Hidden targets
first, and the dispatcher/terminal spent a separate Auxilia per enemy row.
With one Auxilia, one Belgic and one Arverni target could not both be authored.
The new grouped row names one Auxilia count and exact faction/visibility/count
targets, reserving all physical cohorts before flipping. One Auxilia can Scout
one Belgic Hidden and one Arverni Revealed Warband; already-Scouted targets need
no additional marker. Duplicate targets share the available cohort. Malformed,
overlarge, stale or missing cohorts are rejected instead of substituted.

Terminal timing and ordinary menus share the same evolving-board planner.
Arrivals can Reveal, while the existing movement ledger blocks moving those
pieces again. Each group's authored timing runs before its complete allocation;
invalid grouped execution restores its earlier moves and flips. Card 12 rejects
multiple Regions in a grouped plan. Counts preserve physical owners through
Diviciacus, either explicitly or via the existing owner request. Its consent
check sees all grouped target factions, including targets of the proposed lender.

## Compatibility and validation bounds

Legacy bot/adapter rows still allocate per entry with Hidden-before-Revealed
fallback and partial fulfillment. The native bot planner is unchanged. The
separate restricted Card 44 Event procedure retains its existing contract.
There is no new request kind or save schema; existing physical-owner requests
support pending IDs, earlier accepted choices, save/resume and exact replay.
An older transcript that used the automatic borrowed-first Reveal default can
now require a physical-owner answer for mixed loans.
Previews consume neither live decisions nor live RNG. The old menu regression
for arrivals was updated to drive the new exact choices and retains its board
assertions. The first full run had one failure in an obsolete yes/no collector
script (8,319 passed). The accepted run uses explicit Finish choices and
checks that both declines return no plan; the old log is archived separately.
All 47 rule references, canonical constants and balance baseline
are unchanged (49 protected inputs).

**8,320 tests pass** in the final full suite (221.63 seconds), with zero failures, errors or skips. **60 new cases** and **337 targeted tests** cover
cross-faction capacity in both editions; exact visibility and aggregate counts;
invalid rows/movements and whole-Scout rollback; Card 12, Leader reach and
Britannia; legacy controls, physical-owner consent/selection, terminal board
inspection, preview isolation and later-owner pending/save/resume/replay.

The unchanged new tests run against existing APIs in an isolated parent:
**13 behavioral failures** reproduce ignored grouped targets, wrong visibility,
missing rejection and incomplete consent targeting; **seven controls pass**,
with 40 cases deselected. No missing helper import is counted as proof.

Ten audited native-bot games cover all five scenarios and seeds 1–2. Mixed-seat
matrices use those seeds, hash seeds 0/987, Events, reactions and internal replay
(40 executions total). All ten native-bot records complete and audit cleanly, with no errors or
integrity findings, four ranked factions, consistent winner/ranking fields and
nonempty final hashes. Every gameplay field and final hash matches the parent;
only elapsed seconds, commit and source digest are excluded from comparison.
Both mixed-seat outputs agree in complete JSON across hash seeds: 356 human
turns, 96 Event attempts, 90 successful Events, zero hard findings, zero partials,
batch digest `d899b5732da10db5`. Internal replay makes 40 executions in total.

The 100-game historical balance check covers all five scenarios and seeds 1–20. It passes the unchanged 15-point band, with a largest difference of 15 percentage points and 35 different winners versus the historical baseline. The ten directly paired games compare against the parent commit.

## Progress

CMD-SCOUT-ALLOCATION closes one original finding: **35/50 closed (70%), 15 open**.
The separate defects, 34 unverified inventory rows, two source questions and
twelve adopted provisional rulings retain their dispositions.

[Machine-readable results](scout-allocations-2026-11-04-results.json) ·
[Evidence archive](scout-allocations-2026-11-04-evidence.zip)
