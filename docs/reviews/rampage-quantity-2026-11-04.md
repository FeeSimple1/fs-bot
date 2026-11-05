# Rampage quantity — 4 November 2026

Date convention: America/Chicago. Parent:
`4cfeb2c4e58685f96a2287490d405d37df553558`.
Closes original **CMD-RAMPAGE-COUNT**: **24/50 closed (48%), 26 open**.

## Source and repair

Section 4.5.2 requires one affected Warband, Auxilia or Legion per Hidden
Belgic Warband selected to Reveal. There is no two-Warband ceiling. Section
8.5.1 and the Belgic flowchart require NPCs to use all able Warbands, while
not taking the enemy's last piece before Battle. Section 4.1 permits selecting
a Region only once for a Special Ability. Ariovistus A4.5 retains Rampage's
Germanic exclusion and requires removal of Arverni rather than Retreat.

Human `sa_regions` entries now specify `{region, target, count}`. A selected
Region is a nonempty application: choose a positive integer through the
current Hidden Warbands and eligible enemy mobile pieces; omit the Region
to decline there. Counts above two are supported. Only the chosen number
Reveal, leaving the others Hidden. A count that exceeds the current pool is
rejected rather than silently reduced, before any victim reaction, agreement
or quantity-dependent removal. Both quantities are checked after the preceding
Command and authorized timing actions, when Rampage actually resolves.
Earlier authorized timing actions remain separate effects; this is not a new
whole-multiple-Region atomicity guarantee.

Ordinary and detached timing menus author the exact count, retain board
inspection, and preview the selected quantity without mutating the live board.
Human ordinary turns and Event-grant plans require the field; durable missing
choices remain pending. Duplicate Region entries cannot split the quantity
across repeated applications or target two Factions in one Region.
Accepted actor counts, including a full Rally followed by Rampage, persist
through pause/save/resume and journal replay. The existing victim request
receives the exact `context.num_pieces` and retains pending-input rollback.

The former default also capped NPCs at two, contrary to the supplied flowchart.
Legacy/default entries without `count` now use all able Warbands. NPCs' default
before-Battle quantity still leaves an enemy piece; this NPC restriction does
not clamp explicit human quantities. This is an intended bot behavior change,
not a promise of unchanged game states. Save schema is unchanged; older human
submissions need a count and cross-revision replay is not promised. No new
provisional interpretation or external rule source is introduced.

## Remaining scope

BATTLE-RAMPAGE-VICTIM remains open: the victim's full physical-piece and
per-piece remove/Retreat interface is not repaired here. The existing reaction
and automatic piece priorities remain. Circumvallation's remaining marked-group
mechanics and the separate NPC Intimidate targeting lead also remain open.
Two source questions, twelve provisional rulings and 34 unverified inventory
rows keep their separate accounting.

## Verification

Frozen Python source: **480 files**, SHA-256
`dacec83d00c491620202ef3253150227ec68addb7bae6793a6241891a18583f0`.
The parent plus these frozen changes identifies the tested candidate.
All 49 protected inputs (47 references, canonical constants and the balance
baseline) byte-match the parent.

- **7,754 tests pass** in the final full suite, with zero errors, failures or
  skips. **348 targeted tests pass**, including **48 new cases**. One existing
  timing-menu regression supplies the newly required quantity input.
- Coverage includes every scenario and explicit counts one, three and five;
  invalid quantity types; both capacity bounds; NPC all-able/default and
  last-piece policy; human before-Battle freedom; Ariovistus Arverni/Scouted
  handling; both menus and inspection; missing ordinary/durable/grant input;
  actual actor and victim save/resume; post-Command rechecking and duplicates.
- Against the parent, **35 behavior witnesses fail and two controls pass**;
  11 other new cases are outside that bounded proof. Selected witnesses use
  existing APIs and fail on behavior, not missing imports or methods.
- Ten audited bot games, seeds 1–2 across all five scenarios, complete with
  no errors, integrity findings or nonlegal diagnostics. All ten winners and
  all gameplay record fields match the parent, except one final-state hash.
  Timing and commit/source provenance are excluded from comparison. Nine
  records match in full including their final hashes.
- The changed game is Reconquest seed 2. Paired completed-card traces match
  before index 24, card 37. At that card's post-Rally Rampage, the same
  preapplication board has 14 Hidden Belgic Warbands and three Aedui Warbands
  at Atrebates. The parent affects two; the corrected NPC affects all three.
  Veneti's other application remains two. Winner stays Belgae, with 30 cards
  played in both runs. The trace reproduces the audited final hashes.
- Ten mixed-seat cases replay under each of hash seeds 0 and 987: **40
  executions**, complete JSON equality across hashes and zero hard findings.
  Each ten-case matrix records 296 human turns, 88 attempted Events, 86
  successful Events and **one soft partial**. Batch digest `d3ba4d586cc98f17`.
- **100-game balance guard passes**, seeds 1–20 in all five scenarios, using
  the unchanged 15-percentage-point band and unchanged stored baseline.
  Maximum absolute drift is exactly 15 points. There are 35 winner changes
  versus that historical baseline, which also spans earlier engine repairs;
  these are not claimed as 35 changes caused by this patch. No baseline was
  refreshed and no policy/band was tuned to obtain a pass.

The mixed partial is the separately traced generated Rally: Pax Gallica seed
2, Belgae on card 13, gives two Resources to Aedui then tries a Treveri step
requiring two Resources with only one left. Dry/live outcomes agree; case
digest `8365e5ea883096b8`. It is not a Rampage failure. Evidence includes the
current source identity, complete execution and verification scripts.

[Machine results](rampage-quantity-2026-11-04-results.json) ·
[Evidence](rampage-quantity-2026-11-04-evidence.zip)
