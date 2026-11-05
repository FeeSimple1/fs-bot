# Lucterius and Hostages quantities and physical choices — 5 November 2026

Client date follows America/Chicago. Parent
`4789ba3f594889b145148f75130eecca153dbee0`.
Frozen Python digest
`d8a561bf3092f6fc210910f69c7db3433135dfc325338608c649414dc2b16eb2`
across 529 files. The publishing commit includes that source.

## Sources and repaired choices

Supplied Card Reference 19 permits either up to six Arverni Warband removals
within one Region of Provincia, or up to five Auxilia placements in Provincia.
The previous handler always took the maximum of the selected branch and its
inferred CLI schema could not express those branch values correctly.

Card Reference 22 permits removing or replacing up to four Warbands/Auxilia
among Regions the executor Controls. The previous replacement-only contract
could not express removal when a replacement was Available. It also attempted
to replace Roman Auxilia with Gallic Auxilia, placing no Warband even when the
executor had one Available. Chapter 5 §§5.1–5.1.3 governs the executor's choices,
partial execution and removal when replacements are unavailable. Canonical
physical piece types remain those in the protected constants/inventories.

`event_piece_choice` now offers live optional quantities and exact Region,
physical faction, piece type and Hidden/Revealed/Scouted cohort counts. Lucterius
can choose zero, a partial total or its printed maximum, and choose exactly
which nearby Arverni Warbands leave. Hostages can select zero-to-four physical
pieces, mixing removal-only and replacement actions, including own pieces.
Its eligible Controlled Regions are selected before applying the aggregate
removals; an accepted group can finish even if its own removals lose Control.
Replacement places the executor's Auxilia if Roman, otherwise Warbands, and
never requires an unavailable piece. This corrects the legacy Gallic path too.

Authored new params use `choice`/`count`/`removals` (19) or `piece_choices` (22).
Legacy explicit region/removal and replacement lists remain supported; this
report does not claim those older formats express exact physical identities.
Raw deferral and explicit default preserve the existing delegated plan, apart
from the source-required Gallic replacement-type correction.

The new live choice follows an Event timing window (`19.piece_choice` or
`22.piece_choice`). Complete selections are validated before their aggregate
operation. The terminal supports board inspection, explicit zero, exact cohort
counts and each Hostages action. Durable sessions retain missing/invalid input
as pending, restore board/RNG, preserve stable IDs through save/load and replay
accepted responses exactly. Preview boards consume no live input or RNG.
Explicit voluntary reclamation before a Lucterius placement is covered.

## Verification

**8,858 tests pass**, with zero failures, errors or skips (232.55 seconds).

There are 89 new cases and 294 passing focused tests. Coverage includes all
five scenarios, zero and partial totals, exact physical visibility, mixed
Hostages actions across Regions, Roman/Gallic replacement types, scarce
Available, own-piece removal and loss of Control, original scope, malformed
and duplicate/overcounted selections, stale cohorts/Control, terminal menus,
invalid transactional plans, pending/save/resume/replay, live reclamation,
legacy compatibility and pure previews.

Eight unchanged probes use only parent APIs. Six fail behaviorally on the
parent: two smaller Auxilia totals, exact smaller Warband removal, both live
Hostages actions, and Gallic replacement of Roman Auxilia. The maximum
Lucterius default and ordinary Warband replacement controls pass. All eight
pass on the repair; no failures depend on importing a new helper.

All ten paired NPC games finish and audit cleanly, with four ranked factions,
consistent winner/ranking output, no integrity findings and only legal-decline
diagnostics. Every gameplay field and final state hash matches the parent,
excluding elapsed seconds, commit and source identity. The Gallic War seed 1
completes its Interlude.

Complete mixed-seat JSON matches across hash seeds 0/987: ten completed games,
313 human turns, 86 Event attempts and 81 successful Events, zero hard findings
and zero partials. Internal replay gives 40 executions. Digest:
`49711d2b842841b9`. The historical 100-game balance guard passes its
unchanged 15-point band, maximum drift 15 percentage points, with
36 historical winner changes. These historical comparisons are separate from
the ten exact parent/current pairs.

All 49 protected inputs match the parent byte for byte: 47 supplied references,
canonical constants and the balance baseline. Archive checksums and exact
529-file source reconstruction verify the accepted digest.

## Disposition and compatibility

BE-06 advances for 19U/22U; numeric 3S/5S mandatory Roman split allocations remain.
BE-07 physical-choice and BE-08 schema findings retain other cards. Original
bundle remains **40/50 closed (80%), 10 open**, with two unadopted source
questions, thirteen provisional rulings and 34 separately unverified inventory
rows. Shaded 19/22 and unrelated mechanics leads retain their dispositions.
No additional ruling or outside research was needed.

Older cross-revision histories can stop at the new live request or differ
under the corrected Gallic Hostages replacement. Same-revision pending,
save/load and replay are tested. Expanded human choices also change the fuzz
agent's own decision RNG sequence; mixed outcomes are a new bounded regression
run, not a claim of equality with the preceding revision's human games.

The [results JSON](base-piece-choices-2026-11-05-results.json) and
[evidence archive](base-piece-choices-2026-11-05-evidence.zip) preserve commands,
raw outputs, source reconstruction and checksums.
