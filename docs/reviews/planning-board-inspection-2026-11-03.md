# Planning-board inspection — 3 November 2026

Date convention: America/Chicago. Parent: `6238dddbb24bddfc3f610e18cfc1ef93a77d7392`.
This closes FE-01 in the 29 October human-choice audit.

## Behavior

After choosing Build before March, the Command collector already used the
post-Build detached board for legal choices, but `b`/`board` inherited the
outer action's earlier inspection hook. A Fort and its Resource cost could
therefore disappear from the displayed position while remaining in the
planning state.

The shared Command-plan collector now scopes inspection to the board passed
to it, including its cooperation prompts. More specific nested collectors
can still show their own evolving previews. The existing context manager
restores the outer inspection hook on normal exit or exceptions.

This is an interface correction, with no new game-rule interpretation.
Movement, execution, save formats, decisions and bot policy are unchanged.
The player guide no longer lists this repaired display bug as an open limit.

## Regression evidence

The witness uses the audit's Pax Gallica seed 13 position and real menus:
Romans choose SA-first Build, place a Fort in Atrebates, then choose March.
At its origin menu, inspection must show one Fort and six Roman Resources,
matching the actual planning board. Measurement wraps the Command collector
only to capture its input; it does not substitute Build, March or display.

All four combinations of `b`/`board` and legacy/action-window menus failed
on the parent at the displayed-board assertion. After the fix, all four
pass. They also verify that the live encoded state (including RNG) remains
unchanged, the preview validates, and an EOF exit restores the outer hook.
The targeted frontend suite passes 32 tests.

## Final verification

The full suite passes **7,489 tests**, with no failures, errors or skips,
on Python 3.12.14. Final Python source SHA-256:
`f07654d71ce309a9b1d0b347e42ee2a59a4e1d86c9c8f0348bf19ee7d6ec9e27`
(464 files). This is the frozen source used for the full and targeted suites.
The four added cases account for the increase from the parent checkpoint's
7,485 tests; the parent full suite was not rerun here. Whitespace validation
and repair-ledger counts also pass. See the [results JSON](planning-board-inspection-2026-11-03-results.json).

## Scope and remaining work

Original audit: **21/50 closed (42%), 29 open**. The grouped BE-01 Event
March grants on 4/9/17/58/65 remain open; this batch closes only FE-01.
The 34 unverified inventory rows, two unadopted source questions and twelve
provisional rulings remain separate. No bot-game matrix is claimed for
this display-only change. Supplied references, canonical constants and
the balance baseline are unchanged.
