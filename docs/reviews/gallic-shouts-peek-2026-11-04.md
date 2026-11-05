# Gallic Shouts private peek — 4 November 2026

Client date: America/Chicago. Parent `6e1b04d53c639d7503925d57dafdff22b01e4471`.
Tested working Python digest:
`61faa08aa203d0af35e2c934093898fc5c5ed6836c100643d3fc21c3b097bdd8`
(491 Python files). The publishing commit includes this frozen source.

## Source and correction

Card Reference 35 unshaded gives Romans the next two facedown cards before
a free Limited Command or becoming Eligible. Chapter 2.2 already exposes the
next card: the live draw deck's first entry is face up, so the peek uses entries
1 and 2. The Roman benefit belongs to Romans even when another Faction executes
the Event, as the card's Tip expressly contemplates.

Previously, Card 35 stored a Boolean peek flag, while its Roman free-action
request contained no actual future cards. The flag did not show human players
anything. The existing Roman free-action request now carries card ID 35,
`alternative:"eligible"`, and complete private card entries, using Council's
already tested two-facedown-card query. Entries include active edition/scenario
text, title, initiative, NP symbols, Winter and carnyx metadata. Short decks
return only the remaining facedown cards; Winter has no invented Event text.

The terminal prints this private briefing before the decision, explicitly
labels Become Eligible, and retains board inspection. Council's existing
private presentation uses the same extracted renderer. The existing decline
response takes Eligible; an explicit Limited Command remains limited to one
Region/origin, free, with no SA. Presentation context is internally authored
and cannot override free-action legality, price or Region scope.

## Privacy, compatibility and limits

Only the Roman beneficiary's request/session record receives the private
presentation, regardless of executor. Public Event receipts/modifiers and
board snapshots do not receive hidden card entries. The legacy Boolean receipt
remains for compatibility; it contains no hidden information. Normal game
saves still contain the full deck, and raw agents retain the existing trusted,
read-only full-state API. This change is owner routing and display, not a new
adversarial isolation mechanism.

The peek does not draw, reorder, publicly reveal or advance RNG. Missing or
malformed durable responses preserve pending IDs, inbox and board/RNG state
through rollback and save/resume. Accepted private requests/choices replay.
Raw/default bot benefit selection is unchanged; the public note now accurately
records an explicit Eligible choice. Request metadata is additive, so historical
records remain tied to their original engine revision. Shaded Card 35 and all
other grant rules are unchanged. No new provisional interpretation is introduced.

BE-10 closes only this private-peek finding. Other Event contracts, casualty/
Retreat choices, general timing, CV-PERSISTENCE, full Rampage victim choices and
NPC Intimidate targeting retain their dispositions. All 47 references,
canonical constants and the balance baseline are protected (49 inputs).

## Validation

**7,998 tests pass** in the final full suite (325.83 seconds), with zero failures, errors or skips. **120 targeted tests pass**. **120 targeted tests pass**, including 35 new cases.
Coverage spans all five scenarios, original/second editions, both executor
ownership cases, exact facedown bounds, short/Winter decks, explicit command
and Eligible choices, other-seat/public exclusion, preview isolation, terminal
inspection/EOF rollback, invalid input, save/resume and identical replay.
Council's existing terminal/session suite also passes.

An isolated parent runs the unchanged new test file against existing APIs:
25 behavioral failures reproduce absent card/context data; two controls pass,
with eight other cases deselected. Missing modules/APIs are not counted as
proof. Ten native-bot games cover seeds 1–2 in all five scenarios. Mixed-seat
matrices use that seed set, hash seeds 0/987, reactions, Events and internal
replay (40 executions total). All ten native-bot records complete and audit successfully, with no errors or
integrity findings, four ranked factions, consistent winner/ranking fields and
nonempty final hashes. Every gameplay field and final hash matches the parent;
only elapsed seconds, commit and source digest are excluded from comparison.
Both mixed-seat outputs agree in complete JSON across hash seeds: 247 human
turns, 77 Event attempts, 75 successful Events, zero hard findings, zero partials,
batch digest `5dd20da48e8e672b`. Internal replay makes 40 executions in total. These are
bounded compatibility/determinism checks, not a new balance study or a full
rules-compliance proof.

## Progress

BE-10 closes one original finding: **30/50 closed (60%), 20 open**. The separate
defects, 34 unverified inventory rows, two source questions and twelve
provisional rulings are not absorbed into the denominator.

[Machine-readable results](gallic-shouts-peek-2026-11-04-results.json) ·
[Evidence archive](gallic-shouts-peek-2026-11-04-evidence.zip)
