# Third comparison repairs, Batch 2 — 10 November 2026

Batch 2 repairs CM3-01, CM3-03, WS3-01, and WS3-02. Together with Batch 1,
the third-audit ledger records **7 of 15 groups repaired (47%), with 8 remaining**.

[Finding ledger](comparison-audit-round3-2026-11-10.json) ·
[Source-derived expectations](third-comparison-batch2-oracle-2026-11-10.md) ·
[Validation evidence](third-comparison-batch2-2026-11-10-evidence.zip)

## Corrected behavior

Scout checks both movement endpoints against the current playable Regions,
including the actual Gallia Togata marker and its retained A5 identity after
Interlude. Base Cisalpina is unavailable without that Event. Ordinary adjacent
movement, expansion Cisalpina, Gallia Togata access, and the Britannia prohibition
retain their supplied rules. Both supported authored SA-plan layouts use the
same check as the movement primitive. Invalid native sequences roll back earlier
moves; invalid durable submissions retain the pending turn and original board.

Every Battle requires attacking Forces in its Region before paying or resolving
combat. The check uses the actual board after preceding Scout movement and timing
choices, so an initially empty Region can become a legal Battle Region. Own
structure-only Forces remain valid under the printed presence condition.
Bellovaci's separate partial-execution handling still completes prior Event
placements when its entire newly placed Ambush cohort disappears.

Gallic Harvest counts each physical Ally disc and Citadel once. The allegiance
record retained by a City Citadel no longer earns a second payment. Initialized
Reconquest Aedui earns 10 Resources; Great Revolt Arverni earns 20 and Aedui 10.
The normal 45-Resource cap, four Aedui River Tolls, and expansion earnings rules
remain in effect.

Lost Eagle restricts only the upcoming Senate Phase. Intervening Cicero and
Pompey Events carry out their printed shifts. The restriction expires during
that Senate even when Pax forces Intrigue, the marker starts off-track, or the
first post-Interlude Senate does not shift. Normal upcoming-Senate downward
shifts and Firm flips remain blocked; subsequent Senate Phases are unrestricted
by the expired marker.

Authorities are Chapter 1 §1.4.2; Chapter 3 §§3.2.4 and 3.3.4; Chapter 4 §4.2.2;
Chapter 5 §§5.1.1, 5.1.3 and 5.4; Chapter 6 §§6.4.2–6.4.3 and 6.5.1; Card
Reference 1, 3, 5 and 33; Chapter A1 §§A1.3.2 and A1.4.2; Chapter A6 §§A6.4.2,
A6.4.4 and A6.5.1; A Card Reference A5 and A69; and the first-Winter rules in
Scenario - Pax Gallica and A Scenario - The Gallic War.

## Verification

| Check | Accepted result |
|---|---|
| Full suite | 9,522 passed; zero failures, errors or skips |
| Added cases | 49, plus one corrected legacy expectation |
| Changed cases on the parent | 28 fail and 22 positive controls pass |
| Focused action, Winter, Bellovaci and legacy assertion checks | 94 passed |
| Audited bot games | 20 completed; zero audit or integrity failures |
| Mixed-player cases | 20 match exactly across hash seeds 0 and 987; replay enabled |
| Mixed-player findings | Zero hard findings; four soft partial plans per hash run |
| Reviewed balance check | All 100 outcomes match the refreshed baseline; unchanged 15-point band |
| Seasonal causal check | Restoring only old seasonal behavior reproduces all 100 parent winners and lengths |

The accepted repair working tree is over
`8b7227054fe520e05f74646a622296140e3d0f70`, with Python-source SHA-256
`e0c0f1e5dd86bf95978cb6f3226c82d5e46859fb006424b7374f8137aa515f24`.
The bot and mixed samples use seeds 21–24 in all five scenarios and the legacy
card profile. Mixed-player replay gives 80 executions across both hash runs
and their internal repeats. Each hash run records 681 human turns, 159 Event
attempts and 138 executed Events.

Five bot winners and 17 bot final-state hashes change from the parent;
eight mixed-player case records change. These samples remain legal and
replay consistently. Parent game records come from the preceding batch's
accepted archive: its Python-source digest
`42da33aca92ecd23c750e2ea17e29f3f71d50c66e2e50db03a0f325966c12069`
exactly matches clean revision `8b72270`. Fresh changed-case regressions run
against that clean parent.

The one full-suite failure investigated during development was an existing
integration test explicitly expecting Lost Eagle to suppress an Event shift.
It now expects the printed Event shift and retention of the flag for the upcoming
Senate. Earlier incomplete runs and the preliminary import-path investigation
are retained separately; only the root final XML, source identity and game
records supply these accepted results.

## Balance review

The first fixed-seed check exceeds the stored baseline's 15-percentage-point
band: Aedui wins in The Gallic War change from 0/20 in that older stored sample
to 6/20. The immediate parent already has 2/20 Aedui wins. Compared with that
parent, this repair changes 22 of 100 winners and 17 game lengths. This is
deterministic implementation drift, not random rerun noise or evidence of
expert human balance.

A separate process restores only the parent's Harvest earnings, Senate Phase
and Event-shift helper functions. Repaired Scout and ordinary Battle behavior
remain active. All 100 winners and game lengths then match the immediate parent
exactly. This establishes that the observed outcome drift comes from the
source-supported seasonal corrections.

The reviewed baseline now records the corrected outcomes for exactly the same
100 scenario/seed keys: seeds 1–20 in all five scenarios, legacy profile. No bot
priorities or thresholds changed. A fresh 100-game check passes with every winner
and game length matching the refreshed file. The older baseline remains in the
evidence archive, including its initial failed comparison.

Old baseline SHA-256:
`207a62e367e31caec165617b8f62fb5f5b0af82a114c4aaf3aee39f140d37d46`.
Reviewed baseline SHA-256:
`5c14af61d455068527ed2032857192f849eb854b7e0bf4793d475e2974ab262a`.
The correction changes 42 winners relative to that older stored sample; 31
winners already differed before this batch. These measurements cover the named
seeds and card profile, not every rules combination or human strategy.

## Remaining work

Eight third-audit groups remain: BE3-01, BE3-03, BE3-04, EX3-01, EX3-03,
XC3-01, XC3-02, and EX3-04. The prior 50-finding and 21-finding ledgers remain
closed. Known Circumvallation work and unresolved source questions retain their
separate dispositions. Protected references and canonical constants are unchanged.
