# Ordinary Seize: exact Tribe dispersals — 4 November 2026

Date convention: America/Chicago. Parent:
`f05e1f3662094d7f9b693e5986396ffe0e1286f4`.
Closes original **CMD-SEIZE-TRIBES**: **25/50 closed (50%), 25 open**.
These are finding counts, not equal effort or overall rules compliance.

## Sources and repaired behavior

Section 3.2.3 lets Romans choose Subdued Tribe circles to Disperse in each
Roman-Controlled Seize Region, subject to the shared four-marker inventory.
Gathering markers also occupy that inventory. Forage follows Dispersal and
its reactive Rally checks. Ariovistus A3.2.3 retains Seize with its specified
Harassment differences. No external rule source or new provisional ruling
is introduced.

The ordinary executor previously ignored exact Tribe lists, honoring them
only within trusted Roman Event Seize grants. Ordinary human plans now use
the same `details.disperse_tribes` map: every selected Region maps to an
ordered list of its exact Tribes, and an empty list explicitly chooses Forage
without Dispersal. These lists are used as written, rather than replaced with
a default prefix/all Tribes. Actual Control, Subdued status and marker capacity
are rechecked at each Region after preceding effects. This preserves the
existing per-Region resolution contract; it does not introduce whole-multiple-
Region atomicity or predict intervening Rally outcomes.

Human structure validation rejects missing/malformed maps, duplicate/foreign
Tribe identities, extra/missing Region keys and ambiguous mixed exact/legacy
plans before execution. Real interrupted Command portions carry their own
maps; fictitious or nested portions cannot conceal an unnamed plan. Mechanical
Region validation now also rejects duplicate Tribe lists, preventing one
physical marker from generating two dispersals, two Rally sets and excess
Forage. Scoped action clipping retains only in-scope map keys.

Both terminal paths share a detached planner. It offers all legal Tribe
identities even when fewer markers remain than candidates, reserves selected
markers across ordered Regions, permits stopping after a subset or selecting
none, and preserves board inspection. It estimates Forage without rolling
live Rally/Harassment dice or consuming live input/RNG. Pending malformed
choices remain pending, and accepted exact lists persist through a Rally pause,
rollback, save/resume and journal replay. Trusted Event Control/Rally/Harassment
exceptions retain their existing scope; ordinary fields cannot invent them.

Native NPC `disperse_regions` plans and their bounded automatic candidate
selection remain supported. The synthetic human-policy builder now emits a
valid exact map, reserves markers across its Regions and puts actual selected
Regions in `regions`; previously it left them unused in `details._regions`.
Arduenna's mechanical human Seize witness uses the same contract so the new
validator does not lose that legal Command. This is an adapter correction,
not a redesign of NPC Seize priorities.

Save schema remains unchanged. Older human submissions need the exact map;
exact cross-revision transcript replay is not promised. Event-specific Seize
already using exact maps retains that interface.

## Verification

Frozen Python source: **481 files**, SHA-256
`2b7e97d346ddd9772c0b8945d02a75e9cfaa0806535584d9a0eb91e8dc96d757`.
Parent plus these frozen changes identifies the tested candidate. All 49
protected inputs (47 references, canonical constants and balance baseline)
byte-match the parent.

- **7,808 tests pass** in the final full suite (227.57
  seconds), with zero failures, errors or skips.
- **312 targeted tests pass**, including **54 new cases**. Coverage includes
  all five scenarios, nondefault one/two-Tribe subsets, last-marker identity,
  Gathering-marker accounting, no-marker Forage-only, malformed/static and
  changed live targets, mechanical duplicates, both menus/inspection,
  cross-Region reservation, scoped/interrupted plans, native defaults, synthetic
  policies, Arduenna witness, durable invalid input and actual actor save/resume.
- Against the parent, **27 behavioral witnesses fail and five controls pass**;
  22 other new cases are outside that bounded proof. Selected witnesses use
  existing APIs and fail on behavior, not missing methods/imports.
- Ten bot games, seeds 1–2 in all five scenarios, complete and audit without
  errors, integrity findings or nonlegal diagnostics. Every gameplay record
  field and final-state hash matches the parent, excluding elapsed seconds and
  source/commit provenance. This bounded comparison is not a new balance study
  or a claim that complete trajectories were compared.
- Ten mixed-seat cases replay under each of hash seeds 0 and 987: **40
  executions**, complete JSON equality across hashes, all games completed,
  **zero hard findings and zero partials**. Each reported ten-case matrix has
  247 human turns, 77 attempted Events and 74 successful Events. Batch digest
  `c7366266d0681cf4`. The synthetic policy's now-valid Seize choices change
  these trajectories; earlier mixed-run measurements are not relabeled.

Existing human fixtures were migrated to named plans, including the lender
interruption case. The synthetic Recruit-consent regression retains its
no-live-input/no-copy sentinel through all preview and policy construction
checks, then removes it before intentionally executing live play: the newly
valid Seize fallback may legitimately trigger a reactive Rally. Earlier failed
runs using old fixture assumptions are retained separately, not counted as
accepted evidence. The final suite and final matrices use the frozen source
above.

## Remaining scope

The separate Circumvallation mechanics, full Rampage victim choices and NPC
Intimidate targeting lead remain open. Two source questions, twelve adopted
provisional rulings and 34 unverified inventory rows keep separate accounting.

[Machine results](seize-tribes-2026-11-04-results.json) ·
[Evidence](seize-tribes-2026-11-04-evidence.zip)
