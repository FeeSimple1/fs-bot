# Germanic Chieftains choices — 4 November 2026

Date convention: America/Chicago. Parent: `7e3a4afaa719c3dd1698997c3d270edff19833f8`.
This is a partial repair of BE-01, covering numeric17 unshaded.

## Source and behavior

Card Reference 17 and its Tips assign the German action to Romans: March
up to three German groups, then Ambush in any one Region. This does not
follow the Germans Phase sequence. Chapter 3 §3.4.2 permits at most one
German moving group per origin, allows pieces to stay behind, and changes
visibility at selected origins. Section 3.4.4 governs German Ambush, with
§§5.1, 5.1.3 and 5.4 governing ownership, partial execution and free actions.

Romans now receive both live decisions even if another faction, human or
NPC, executes the Event. The first request accepts up to three distinct
original moving groups, exact positive Warband quantities and adjacent
destinations. An empty list moves none. The card grants moving groups,
not an extra selection of hide-only Regions; card65's separate Region grant
continues to permit hide-only origins. Normal visibility changes still
apply to counters left behind at a selected origin.

The existing physical-cohort executor reserves original counters, so arrivals
cannot join another departing group or receive a second origin flip. Roman
players also own the exact visibility formation choices, with Germans
identified as the acting physical force. After March, Romans select one
able Region and defender. Only that Region Ambushes, even if others remain
able. No independent decline or arbitrary target is accepted. Legal zero-Loss
Ambushes remain available, and defensive cooperation is checked before
combat; Germans cannot switch to an ordinary Battle if their Hidden
superiority disappears. Defenders retain their own live reactions.

Native Roman NPCs keep their previous complete planner. Explicit first-stage
bot delegation now applies Roman card instructions even for a human Roman
seat: setup March from Romans toward no Romans, with Roman target priorities.
Raw callback deferral preserves the established legacy contract. Shaded
Germanic Chieftains' immediate Germans Phase is unchanged.

## Interfaces and durability

The terminal labels the Roman whole-grant default, offers positive moving
group quantities, and preserves `b`/`board` inspection. The initial Event menu
does not pre-author the Romans' German groups for another executor.

Durable missing or invalid replies remain pending with stable identity and
board/RNG rollback. A save at the Ambush request preserves accepted March
choices and completes after resuming. The complete Event remains atomic
while awaiting later input. The save schema is unchanged, but old transcripts
may encounter new requests; exact cross-revision replay is not promised.

## Verification

Frozen Python source: 474 files, SHA-256
`dab238eebb414d6ea0eb24acd9ac36b304e7a5c1c30c5eacfbb7912ff7f32bd9`.
Python 3.12.14. Supplied references, canonical constants and balance baseline
remain unchanged. No new provisional ruling is introduced.

- **7,594 tests pass** in the final full suite, with no failures, errors or
  skips. The parent checkpoint had 7,567 tests; its full suite was not rerun.
- 27 added regressions cover ownership across four executors, the three-group
  budget, invalid quantities/routes, original physical cohorts, exact Roman
  formation choices, the single Ambush, native and explicitly delegated Roman
  bot priorities, zero-Loss Ambush, defensive cooperation, terminal inspection,
  actual Event routing and durable save/resume.
- Twenty-one behavioral cases fail against the parent; a native Roman-bot
  control passes. Five new cases are excluded from that parent witness.
  Existing resolver signatures and physical boards are used, with no failure
  caused by an absent newly added API or module.
- The final targeted Chieftains/guidance/CLI suite passes 71 tests.
- Ten accepted legacy-edition bot games (seeds 1–2 in all five scenarios)
  match fresh same-runtime parent gameplay records and final-state hashes,
  excluding runtime/source metadata. This is not a full trajectory comparison.
- Ten mixed-player cases, each replayed under hash seeds 0 and 987, produce
  40 executions with zero hard findings and zero partial plans. Complete JSON
  results match across hashes. Each ten-case pass records 276 human turns,
  85 attempted Events and 81 successful Events; rejected generated inputs
  are not reported as successful Events.
- Fixed-seed checks are bounded evidence, not exhaustive rules certification.
  Prior balance baselines and tolerances remain unchanged.

## Remaining scope

**21/50 original findings remain closed (42%); 29 remain open.** BE-01 now
remains open for numeric4. Two unadopted source questions, twelve provisional
rulings and 34 unverified inventory rows remain separate. Card65's human
all-able Ambush behavior remains covered by its regressions after sharing
this guidance implementation with card17.

Machine-readable [results](germanic-chieftains-2026-11-04-results.json) and
[evidence archive](germanic-chieftains-2026-11-04-evidence.zip) retain full-suite
logs, parent witnesses, paired bot records, mixed runs and the exact patch.
