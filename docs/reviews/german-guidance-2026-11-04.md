# German Allegiances guidance — 4 November 2026

Date convention: America/Chicago. Parent: `72e0594e5d79d68b04208068e1b410666a930941`.
This is a partial repair of BE-01, covering numeric65 unshaded human choices.

## Source and behavior

Card Reference 65 and its Tips direct the executing Faction to guide Germans
Marching from up to two Regions, then Ambush with all Germans able. This is
not the Germans Phase sequence. Chapter 3 §§3.4.2 and 3.4.4 govern one German
moving group per origin, the origin visibility step, and German-only Ambush.
Sections 5.1, 5.1.3 and 5.4 govern choices, partial execution and free actions.

The human executor now chooses up to two original origin Regions, quantities
and adjacent destinations. A zero quantity with null destination selects an
origin only for hiding, still using one of the two Region selections. An
empty list selects no March. The shared Event March executor has an
engine-owned stationary-origin option, disabled for its existing callers.
Physical cohorts are reserved before movement: arrivals cannot join another
origin's departing group or receive another origin flip. This also preserves
Scouted handling when an arriving group crosses another selected origin.

After March, fresh requests expose all able Regions and their legal defenders.
The executor chooses Ambush order and targets; each able Region acts once,
and no independent decline or repeated Region is accepted. Forts retain
normal protection, Hidden superiority remains required, and zero predicted
Losses do not make an otherwise legal Ambush illegal. The old human path
had inherited an NP effectiveness filter as if it were a legality rule.

Defensive Roman/Aedui cooperation is obtained and checked before combat.
If it removes German Hidden superiority, that defender is withheld while
its physical position remains unchanged, and other able choices are offered.
This prevents the shared Battle decorator from converting the attempt into
an ordinary Battle that Germans cannot initiate. A later physical change
allows reconsideration of the blocked position. Defender reactions retain
their own owners; March visibility choices belong to the Event executor.

Native NPC callers, raw callback deferral and an explicit first-stage
whole-grant default retain the previous complete planner. A default at a
later Ambush request delegates only that next choice. This batch does
not audit or revise those priorities. Card17's Roman-owned guidance and
single Ambush remain separate work, as does card4.

## Frontends and durability

The terminal offers exact original groups and fresh Ambush order/target
menus, with `b`/`board` inspection. Durable invalid/missing responses stay
pending with stable identity, board/RNG rollback and preserved accepted
choices. Save/load at the Ambush stage replays the accepted March; rejecting
an already used Region cannot repeat a Battle. The save schema is unchanged,
but old transcripts may encounter new requests across revisions.

## Verification

Frozen Python source: 473 files, SHA-256
`b7f6503a9c85976edeac8e0c467a2a7191a525269f5b03086cc23701e66d28f1`.
Python 3.12.14. Supplied references, canonical constants and balance baseline
remain unchanged. No new provisional ruling is introduced.

- **7,567 tests pass** in the final full suite, with no failures, errors or
  skips. The parent checkpoint had 7,539 tests; its full suite was not rerun.
- 28 added regressions cover all four human executors, original physical
  groups, hide-only origins, limits, target/order choices, Hidden superiority,
  normal Fort protection, zero-Loss Ambush, defensive cooperation, terminal
  inspection, durable rejection and save/resume, and generated input.
- Twenty behavior cases fail against the parent without requiring a newly
  added API or module; the other eight cases were excluded from that witness.
- The final targeted frontend/adjacent Event suite passes 89 tests.
- Ten accepted legacy-edition bot games (seeds 1–2, all five scenarios)
  match fresh same-runtime parent gameplay records and final-state hashes,
  excluding runtime/source metadata. This is not a full trajectory comparison.
- Ten mixed-player cases, each replayed under both hash seeds 0 and 987,
  yield 40 executions with zero hard findings and zero partial plans.
  Complete JSON results match across hashes. Each ten-case pass records
  299 human turns and 86 attempted Events, with 83 successful Events;
  rejected generated inputs are not reported as successful Events.
- Fixed-seed checks are bounded evidence, not exhaustive rules certification.
  The prior balance baseline and tolerance remain unchanged.

The first full-suite attempt caught one compatibility regression in raw
callback deferral: it had continued through new human target validation
rather than delegating the complete grant to the established resolver.
That fallback was restored, its existing regression passes, and the full
suite and candidate gameplay checks were restarted on the final source.
The earlier full-suite failure is retained as development evidence, not
reported as accepted verification.

## Remaining scope

**21/50 original findings remain closed (42%); 29 remain open.** BE-01 now
remains open for numeric4/17. Two unadopted source questions, twelve
provisional rulings and 34 unverified inventory rows remain separate.

Machine-readable [results](german-guidance-2026-11-04-results.json) and
[evidence archive](german-guidance-2026-11-04-evidence.zip) retain full-suite
logs (including the superseded failure), parent witnesses, paired bot
records, mixed runs and the final implementation patch.
