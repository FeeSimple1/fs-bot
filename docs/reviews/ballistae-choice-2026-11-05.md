# Ballistae post-Ambush choice — 5 November 2026

Client date follows America/Chicago. Parent
`c3886d9df4e1ede47d4c10cd0948cd351ec358ba`.
Frozen Python digest
`586197007c4d62450434c5e1a37a904560b32098ad52bec979538fea47c9909a`
across 514 files. The publishing commit includes that source.

## Rule and implementation

Card Reference 10 shaded assigns its owning Gallic Faction an optional removal
of a defending Fort or Citadel after Ambush. The old executor always removed
one, preferring a Citadel. The owner now receives a live `ballistae_target`
request after Battle losses and Reveal. It can remove one exact offered target
or decline. This applies separately in every Ambush Region, including free
Event Ambushes, and belongs to the capability owner even when the Event
executor differs.

The request lists each surviving physical target's piece type, Tribe and
owner. Removal uses the board helpers and clears exactly the Citadel's Tribe.
Combined forces retain their physical counter's owner. No extra saving roll
is made. Targets removed during combat are absent from the offered list.
Older raw fixture Citadels without a Tribe record retain an unnamed target
rather than inventing an allegiance. Ordinary Battle, the wrong capability
side/owner and an empty eligible target list create no request.

Chapter 1 §1.4.2 requires Provincia's Roman Fort always to remain and says it
cannot be removed. The old post-Ambush code nevertheless attempted removal and
could raise a piece-operation error after combat. It is now excluded from the
candidate list, so both human and default paths preserve it.

## Human interfaces and compatibility

Terminal play offers the named physical target or decline and retains live
`b`/`board` inspection. Durable sessions require a valid target, decline or
explicit default delegation. Invalid or missing responses remain pending.
Their action transaction restores pre-Battle forces, payments and random state.
A saved second-Region prompt retains the accepted first-Region response and
its stable decision identifiers. Repeating the action after resume removes or
preserves each Citadel exactly once, with the same final board and RNG as replay.
Previews do not consume live human input or random state.

Raw callback `None` and explicit default retain Citadel-before-Fort removal.
All-bot behavior retains that priority, apart from the permanent Fort exclusion.
Older cross-revision terminal/durable histories that passed this formerly
automatic step may stop at the new choice. Existing accepted responses are
not invented to bypass it. This repair adds no provisional ruling or source
question.

## Verification

**8,580 tests pass**, with zero failures, errors or skips (281.53 seconds).

There are 47 new regression cases and 349 passing focused tests. They cover
all five scenarios, Gallic owners, exact Citadel identity, Fort removal or
decline, stale/forged responses, legacy raw defaults, physical ownership,
permanent Fort protection, targets consumed in combat, actual post-Reveal
requests, terminal inspection, Event-granted Ambush, preview isolation,
explicit delegation, pending invalid choices and saved later-Region replay.

Six unchanged probes use only APIs already present in the parent. The parent
fails three owner-decline probes and one permanent-Fort probe, while its two
raw-default/wrong-owner controls pass. All six pass on the repaired source.

Standard audited NPC games cover all five scenarios and seeds 1–2. Mixed-seat
matrices cover those seeds under hash seeds 0 and 987 and include internal
replay. The historical balance guard uses seeds 1–20 in all five scenarios,
its unchanged baseline and the existing 15-percentage-point band. These
bounded game runs are general regression evidence; the directed tests exercise
the new Ballistae decision and its interrupted Region sequence.

All ten standard NPC records complete and audit cleanly with four ranked
Factions, consistent winner/ranking output, no integrity findings and only
legal-decline diagnostics. Every gameplay field and final board hash matches
the parent, excluding elapsed seconds, commit and source identity.

The complete mixed-seat JSON outputs match across hash seeds 0 and 987. They
cover 314 human turns, 91 Event attempts and 85 successful Events, with zero hard
findings and zero partial games. Their digest is `2d71a817ecdd8b56`.
Internal replay gives 40 executions total. The historical 100-game balance
check passes the existing band, with a maximum difference of
15 percentage points and 35 winner changes versus the historical baseline. Those
historical comparisons are separate from the ten exact parent/current NPC
comparisons.

All 49 protected inputs match the parent byte for byte, comprising 47 supplied
references, canonical constants and the historical balance baseline. Archive
checksums and reconstruction of all 514 Python files verify the accepted source
digest. The first directed run exposed two mistaken test expectations about
ordinary combat casualties and the executor result envelope. Those fixtures
were corrected before acceptance; the superseded log is retained separately.

## Progress

This repairs Card 10 shaded's part of BE-09. **BE-09 remains open** for
Balearic Slingers (13 unshaded) and Germanic Horse (59, both sides) Region
choices. Original progress remains **39/50 closed (78%), 11 open**. Separate
mechanics leads, 34 unverified inventory rows, two source questions and twelve
owner-adopted provisional rulings retain their dispositions.

[Machine-readable results](ballistae-choice-2026-11-05-results.json) ·
[Raw evidence archive](ballistae-choice-2026-11-05-evidence.zip) ·
[Current status](../current-status.md) · [Progress](../human-choice-progress.json)
