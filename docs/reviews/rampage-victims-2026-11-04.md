# Rampage victim choices — 4 November 2026

Client date follows America/Chicago. Parent
`70587e632ab35cc1f7f8a44a0f0e8eefb81be23a`.
Frozen Python digest
`2747a7a23f8ffb0b5769caf2ef0c1b39fdb98f730076a142644ad3c7a720f987`
across 509 files. The publishing commit includes that source.

## Rule and implementation

Chapter 4 §4.5.2 assigns the target one mobile piece to remove or Retreat per
Belgic Warband flipped. Removed Legions go to Fallen without a roll. The
Retreating pieces use one adjacent Region under the target's Control or
another consenting Faction's Control, excluding No Control and Germanic
Control. Chapter A4's Rampage note forces Arverni removal in Ariovistus,
and A3.2.4 prohibits expansion Arverni consent to Retreat into their Control.

The old target hook offered all-or-none disposition of a fixed physical
subset. The existing retreat request now offers physical piece/state pairs.
A human target supplies one disposition per affected piece, with one common
Retreat destination. It can remove a Legion while Retreating a selected
Revealed Auxilia and leave other cohorts intact. Requests belong to the
target. The Belgic actor's quantity contract remains independent.

All selections reserve their physical cohorts before mutation. The primitive
validates the complete action list, including visibility, duplicate capacity,
Region/target eligibility and the shared legal destination, before flipping
Warbands. Its transaction restores any failed mutation. The direct low-level
Retreat path now checks Control as well as adjacency. The old low-level test
fixture has gained the friendly Ally that establishes its required destination
Control. The earlier quantity save/resume test now supplies exact victims.

Host agreement is collected once per candidate destination, avoiding the old
two-call discrepancy. The executor passes those agreed Regions to the
primitive so the same consent is honored throughout that operation. New
randomized reactive plans exercise physical subsets and mixed dispositions.

## Compatibility

Raw adapters retain their all-or-none boolean contract and default subset.
Fresh durable prompts require exact actions or explicit default delegation.
Recorded old durable requests, journals and replay expectations can use their
old contract only when the original board and legal options match. The same
signature checks used for older Battle casualty prompts guard this path.
Current second-Region pauses retain earlier accepted choices across saving,
loading and replay. Older terminal replays that contain two recorded rounds
of host consent may need that Rampage segment recorded again because consent
is now collected once. Cross-revision terminal replay has existing limits.

## Verification

**8,465 tests pass**, including 42 new cases, with zero failures, errors or skips (291.57 seconds). There are 42 new regression
cases and 469 passing focused tests. The cases cover every scenario's Roman
victim, all three visibility states, mixed dispositions, Legion Fallen, zero
loss rolls, shared destinations, duplicates, malformed payloads, host consent,
forbidden Control, forced Arverni removal, terminal inspection, invalid pending
responses, older durable prompts and a saved second-Region continuation.

Seven unchanged probes using only parent APIs produce five behavioral failures
on the parent and two passing controls. They expose the missing physical pool,
ignored mixed choice, partial low-level mutation, unrestricted destination
Control and duplicate host consent. All seven pass on the repaired source.

Paired audited NPC games use all five scenarios and seeds 1–2. Mixed-seat
matrices use those seeds under hash seeds 0 and 987, with Events, reactions and
internal replay. The historical balance guard uses seeds 1–20 in all five
scenarios with its existing baseline and 15-point band. All ten native NPC records complete and audit cleanly, with four ranked
factions, no errors or integrity findings, and consistent winner/ranking data.
Every gameplay field and final board hash matches the parent, excluding only
elapsed seconds, source digest and commit identity.

Both complete mixed-seat JSON outputs agree under hash seeds 0 and 987. They
cover 314 human turns, 91 Event attempts and 85 successful Events, with zero hard
findings and zero partial games. Their batch digest is `2d71a817ecdd8b56`.
Internal replay gives 40 executions total. The historical 100-game balance
check passes the existing band, with a maximum difference of 15 percentage
points and 35 winner changes versus the historical baseline. These are separate
from the paired parent/current NPC comparisons.

All 49 protected inputs match the parent byte for byte, including 47 supplied
references, canonical constants and the historical balance baseline. The
archive includes commands, raw results, source reconstruction data and verified
checksums. Earlier failed development/fixture logs are retained separately and
excluded from accepted totals.

## Progress

BATTLE-RAMPAGE-VICTIM closes one original finding, bringing the original bundle
to **38/50 closed (76%), 12 open**. Ordinary Battle Retreat survivor choices
remain open. Separate mechanics leads, 34 unverified inventory rows, two source
questions and twelve adopted provisional rulings retain their dispositions.

[Machine-readable results](rampage-victims-2026-11-04-results.json) ·
[Evidence archive](rampage-victims-2026-11-04-evidence.zip)
