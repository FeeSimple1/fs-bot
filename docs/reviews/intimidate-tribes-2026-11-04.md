# Intimidate: exact Allied Tribe identity — 4 November 2026

Date convention: America/Chicago. Parent:
`70c571cca14380c33f310b45c02cf615143b3ed0`.
Closes original **CMD-INTIMIDATE-TRIBE**. Original bundle:
**23/50 closed (46%), 27 open**.

## Source and repaired behavior

A4.6.2 removes selected Warbands, Auxilia and/or Allies of one Faction with
no Leader in the selected Region. Section 1.4.2 distinguishes each Tribe's
Ally disc from a City's Citadel; a Citadel is not an eligible Intimidate
removal. A3.4.3 provides the intrinsic Raid use. A22 shaded permits an extra
Warband/removal, and A45 shaded waives selection geography for its free use.
These source distinctions govern the same physical target choices through
each execution path. No provisional ruling or external rule source is added.

Human `intimidate_plan` Ally entries now identify the disc with
`target_tribe`. The engine preserves this field through ordinary, Raid-linked
and A45-granted Intimidate. It validates and reserves the complete Region's
physical removals before any Reveal or marker placement, rejecting duplicate,
foreign, absent, wrong-Region, null, non-Ally and Citadel identities. Multiple
Regions remain separate applications; this is not a new whole-Command atomicity
contract. Earlier authorized timing-window actions retain their own effects.

Both terminal planning paths offer named discs, and the live planning path
reserves earlier choices on its detached board. Raid reaction options name
each Ally with availability one, preserve the exact field in the response,
and retain board inspection. A29's Event executor still directs its granted
Raid's intrinsic Intimidate; the physical force remains Germanic.

Ordinary human submissions, Event-grant plans, and durable Raid responses
must name each Ally disc. Missing or invalid durable choices stay pending,
without consuming the queued response or mutating the live board. Save/resume
and the journal preserve the accepted Tribe identity. Save schema is unchanged;
older human submissions may require the new field. Cross-revision transcript
replay is not promised.

Unnamed NPC plans, direct low-level pairs and legacy raw Raid callbacks retain
their existing default. The low-level helper also accepts `(ALLY, None, tribe)`.
Where named and legacy unspecified discs coexist, named discs are reserved
first, preventing a default removal from consuming an explicitly selected
later target. Results retain `target_removed` and add `target_details` with
resolved piece type, visibility and Tribe. This does not redesign NPC priorities.

## Scope boundaries

Circumvallation's original physical-group tracking, movement restrictions,
virtual Fort protection, attack/elimination boundaries and exact marked-only
Interlude cleanup remain open. This batch fixes a physical Tribe selection
prerequisite; it does not implement persistent cohort bookkeeping. The prior
no-Romans marker-boundary repair remains in force. The separate NPC Intimidate
lead about excluding a whole prospective Battle defender is also unchanged.
Two source questions, twelve adopted provisional rulings and 34 unverified
inventory rows retain their separate accounting.

## Verification

Frozen Python source: **479 files**, SHA-256
`5179ad47b36917a8447e1e4dbe8b122f7e795e1d499736e68b0b66eb0e019d76`.
Parent plus these frozen changes identifies the tested candidate. All 49
protected inputs (47 supplied references, canonical constants, balance baseline)
byte-match the parent.

- **7,706 tests pass** in the final full suite (207.26
  seconds), with zero failures, errors or skips.
- **229 targeted tests pass**, including **44 new cases**. Coverage includes
  both expansion scenarios, Roman/Arverni victims, all three execution adapters,
  Dread's third removal, distinct Ally/Citadel identity, named/default reservation,
  invalid atomic Region plans, both ordinary menus, Raid menu/board/EOF,
  missing human identities, pending invalid input, actual Raid save/resume,
  A29 chooser ownership and randomized named-target generation.
- Against the parent, **23 behavior witnesses fail and two controls pass**;
  19 other new cases are outside that bounded proof. The selected witnesses
  use existing entry points and fail on behavior, not missing APIs/imports.
- Ten bot games, seeds 1–2 across all five scenarios, complete and audit with
  no errors, integrity findings or nonlegal diagnostics. Every gameplay record
  field and final-state hash matches the parent, excluding only elapsed seconds
  and source/commit provenance. This is a bounded comparison, not a new balance
  baseline or a claim of identical complete trajectories.
- Ten mixed-seat cases run twice for replay under each of hash seeds 0 and 987:
  **40 executions**, complete JSON equality across hash seeds, zero hard findings.
  Each ten-case matrix has 296 human turns, 88 attempted Events, 86 successful
  Events and **one soft partial**, not zero. Batch digest `7414a45e7c1adbb7`.

The soft partial is the same traced generated plan: Pax Gallica seed 2,
Belgae on card 13, Rally gives two Resources to Aedui, then a Treveri placement
requires two Resources when only one remains. Dry/live outcomes agree; the
case digest is `8365e5ea883096b8`. It is not an Intimidate failure. The evidence
records its full execution and current source identity.

Earlier candidate checks lacked the final missing-human-identity guards.
Their runs are retained as superseded evidence and are not attributed to the
accepted frozen source. The final full suite and both validation matrices
were rerun after those guards and their regressions were added.

[Machine results](intimidate-tribes-2026-11-04-results.json) ·
[Evidence](intimidate-tribes-2026-11-04-evidence.zip)
