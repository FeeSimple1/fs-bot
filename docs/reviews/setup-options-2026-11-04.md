# Printed setup options — 4 November 2026

Client date follows America/Chicago. Parent
`7f13084de6658176a5ee10020f9345d9cbcd49e2`.
Frozen Python digest
`ac4fcb5a00dda78552ba079ee794aaa432211199e5d176629bb9e008ab0e3cf8`
across 511 files. The publishing commit includes that source.

## Sources and behavior

Chapter 2 §2.3.8's Sudden Frost option requires all players' agreement at setup.
When an Event would be shown immediately before Winter, switch those cards
and conduct Winter immediately. The postponed Event remains atop the deck for
the next Year unless that Winter ends the game. The engine performs the
switch while drawing, before any Event action or Arverni activation, and
records only Winter in played history. This also works on the opening draw.
Final-Winter detection remains correct with the postponed Event still in
the draw deck, without requiring another Winter. Ordinary Frost remains the default.

A Setup's Deck Preparation gives Even Initiative to all initial scenarios
except Pax Gallica?. The engine shuffles four piles of 18 physical Event
cards by their first Faction symbol. It deals complete four-card rounds into
a selection pool until the required count is reached or exceeded, then
shuffles that pool and deals the scenario's Event count. Thus 30 Events come
from 32 balanced cards, 45 from 48, and 60 from 60. The resulting 30/45-card
deck can have unequal initiative counts after truncation. Expansion
replacement cards retain their full identities, including carynx suffixes.
The optional original-scenario Diviciacus replacement remains O38, and card
edition choices remain independent.

The Great Revolt's Deck paragraph permits 30 Events in six five-Event piles,
with Winter shuffled into piles 3 and 6. The new short-deck option uses exactly
those piles and two Winter cards. Other scenario decks retain their printed
composition. Invalid scenario combinations and non-boolean setup arguments
are rejected before consuming RNG or placing pieces.

The Gallic War's Interlude explicitly replaces the first-half deck with its
Pax Gallica? deck, per its Deck paragraph. That existing replacement remains
in force, including the handling of unplayed first-half cards. Even Initiative
selects the initial deck only. Sudden Frost remains selected for second-half
play. This repair adds no new source interpretation or provisional ruling.

## Interfaces and compatibility

The setup API accepts `sudden_frost`, `even_initiative` and
`short_great_revolt`. Terminal startup and assistant `init` accept the matching
flags. Enabled options are displayed on the board and retained in state,
metadata and saved assistant origins. Terminal loading/replaying rejects any
attempt to change a selection. Older saves with absent fields retain the
standard rules. Disabled fields remain absent from gameplay state, preserving
standard-game RNG consumption, board hashes and pending signatures.

A durable human pause during a switched Winter restores the same already
switched board, keeps the deferred Event unplayed, and retains its pending
identifier after save/load. Completing the Winter advances to that Event
exactly once. Terminal full-game replay and durable accepted-choice replay
both retain the selected options and reproduce the board and random state.

## Verification

**8,533 tests pass**, with zero failures, errors or skips (435.34 seconds).

There are 68 new cases and 545 passing focused tests. Coverage includes every
legal setup combination, exact Winter piles, physical card uniqueness,
scenario isolation, malformed flags, both frontend restrictions, optional
Diviciacus/card editions, opening and successive Sudden Frost switches,
final-Winter termination, standard Frost, Interlude replacement, board display,
pending Winter rollback/save/resume and both frontend replay paths.

Six unchanged probes use only APIs present in the parent. They produce four
behavioral failures on the parent and two passing controls. The failures show
an unswitched Winter, unsorted base and expansion initiative piles, and the
ignored short-deck selection. All six pass on the repaired source.

Paired native NPC games cover all five scenarios and seeds 1–2. The separate
option matrix audits all 17 legal nonstandard option/scenario combinations
under seeds 1–2, including two completed Gallic War Interludes with Sudden
Frost. Mixed-seat matrices use hash seeds 0 and 987 and internal replay. The
historical balance guard uses seeds 1–20 in all five scenarios, its unchanged
baseline, and the existing 15-percentage-point band.

All ten standard NPC records complete and audit cleanly. Every gameplay field
and final board hash matches the parent, excluding elapsed seconds, commit and
source identity. All 34 optional-setup games complete and audit cleanly with
four ranked Factions, consistent winner/ranking output, no integrity findings
and only legal-decline diagnostics.

The complete mixed-seat JSON outputs match across hash seeds 0 and 987. They
cover 314 human turns, 91 Event attempts and 85 successful Events, with zero hard
findings and zero partial games. Their digest is `2d71a817ecdd8b56`.
Internal replay gives 40 executions total. The historical 100-game balance
check passes the existing band, with a maximum difference of
15 percentage points and
35 winner changes versus the historical baseline. Those historical comparisons
are separate from the ten exact parent/current NPC comparisons.

All 49 protected inputs match the parent byte for byte, comprising 47 supplied
references, canonical constants and the historical balance baseline. Archive
checksums and reconstruction of all 511 Python files verify the accepted source
digest. The first focused run exposed a mistaken test lookup of the pending
request envelope, corrected before acceptance. Its log remains in development
evidence and is excluded from accepted totals.

## Progress

WS-F08 closes one original finding, bringing the original bundle to
**39/50 closed (78%), 11 open**. Shared player ownership and ordinary Battle
Retreat choices remain open alongside the other recorded findings. Separate
mechanics leads, 34 unverified inventory rows, two source questions and twelve
owner-adopted provisional rulings retain their dispositions.

[Machine-readable results](setup-options-2026-11-04-results.json) ·
[Raw evidence archive](setup-options-2026-11-04-evidence.zip) ·
[Current status](../current-status.md) · [Progress](../human-choice-progress.json)
