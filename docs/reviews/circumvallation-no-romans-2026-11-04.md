# Circumvallation: no-Romans marker boundary — 4 November 2026

Date convention: America/Chicago. Parent:
`f5a4a1a568d45462892a36902291d179d0c51eee`.
This is a **partial repair of separate CV-PERSISTENCE**, not its closure.
Original bundle remains **22/50 closed (44%), 28 open**.

## Source and scope

Card Reference 4 requires removal of the marker “if no Romans there”. This
boundary does not depend on knowing the original marked opponent cohort.
Any physical Roman piece counts: Auxilia in any visibility, a Legion, a
Leader, an Allied Tribe or a Fort. A Command's temporary effective-force
view does not redefine physical Roman presence.

Successful physical removal/movement now clears an expired marker as part
of the piece helper's Region refresh. Actual Battle casualties and March
departures use that path. Other Region markers and opposing Forces remain
untouched. Returning Romans do not recreate an expired marker. Failed and
zero-count operations do not change it. Dictionary and set marker containers
are supported, including legacy Boolean marker values. No save schema or
new decision fields are introduced, and no original cohort is inferred.

The detached automatic Quarters path previously committed only `spaces`.
It now commits the accepted relocation's marker effects too. Validation
previews stay detached. Interlude final marker deletion is idempotent when
an earlier physical removal in that procedure has already cleared it.

**Remaining defects:** original marked-group tracking, movement restriction,
virtual Fort protection, attack/elimination cleanup, and exact marked-only
Interlude removal remain open. Old Boolean markers cannot identify mixed
original and arriving pieces. The [follow-up](circumvallation-persistence-followup-2026-11-04.md)
retains those requirements; this patch does not implement them. It also does
not attempt to repair an already stale legacy marker at load time.

## Validation

Frozen Python source: 478 files, SHA-256
`58371d2b62bc410b3d070fd14cab047da3b8f69728c62e7eb4bbfcd3aad675ca`.
The parent plus these frozen modifications defines the tested candidate.
All 49 protected inputs (47 references, canonical constants and balance
baseline) byte-match the parent. No provisional ruling changes.

- **7,662 tests pass** in the final full suite (226.03 seconds),
  with zero failures, errors or skips.
- **153 targeted tests pass**, including Circumvallation, Interlude and
  Quarters relocation coverage. **39 new regression cases** cover all five
  scenarios, both marker containers, every Roman piece kind, departure and
  removal, actual March/Battle, deterministic serialization/resume, failed
  operations and detached/committed Quarters effects.
- Against the parent, **36 behavioral tests fail and three controls pass**;
  these tests exercise existing APIs, with no missing-import/API failures.
- Ten accepted bot games, seeds 1–2 in all five scenarios, complete with
  no errors, integrity findings or nonlegal diagnostics. All winners match
  the parent; this is a bounded comparison, not a balance study.
- Six records match in all gameplay fields/final hashes. Three differ only
  in their recorded final-state hash. Gallic War seed 1 changes more fields:
  71 to 88 cards, final ranking and Resources differ, winner remains Belgae.
  Timing and source/commit provenance are excluded from record comparison.

The Gallic War trace first differs only in markers after Winter at index 28:
Romans have left Sequani, so the candidate expires its marker. The parent
retains it. Board/Resource/RNG snapshots remain equal through index 44,
except for that marker. At the Interlude (index 45), the parent's stale marker
incorrectly drains later German arrivals before German force adjustment;
subsequent adjustment and play diverge. Disabling only the new cleanup in a
controlled candidate replay reproduces every parent snapshot and all parent
record fields except elapsed seconds. This attributes the change to the
intended expired-marker boundary; it does not assert correct handling of a
still-active marker at the Interlude.

The first candidate passed 7,657 tests, but its game trace exposed discarded
Quarters marker effects. That source and its bot runs are superseded, kept
separately in the evidence; no results from it are attributed to this source.

[Machine results](circumvallation-no-romans-2026-11-04-results.json) ·
[Evidence](circumvallation-no-romans-2026-11-04-evidence.zip)
