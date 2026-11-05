# Battle casualty identities — 4 November 2026

Client date follows America/Chicago. Parent
`b4613aeb3ed0664d85bf3d2f306b5dd07fd7be84`.
Accepted Python digest
`07631b40b8ce8a911c3b6ef8fc886dbd9435a2dced5601370f3c3510b8c6e99c`
across 506 files. The publishing commit includes this source.

## Rule and correction

Chapter 3 §§3.2.4/3.3.4 assigns the owner its physical casualty choices within
mandatory tiers. Chapter A3 adds the game-run faction priorities, Settlements
and Diviciacus restrictions. Chapter 1 §1.4.2 distinguishes Ally discs from
Cities represented by Citadels. Chapter 3 §3.1 gives human owners their legal
choices. Existing combined-force, Elite and Enlist representations already
carry physical identity for their special pieces.

Ordinary human casualties previously exposed identical generic entries for
Warbands/Auxilia with different visibility, and for different Allied Tribes.
The owner could not reliably name its intended piece. A final identity pass
now expands ordinary visibility and names Ally discs after the force-specific
conversions. It reuses the existing Tribe-disc predicate and exact removal
route. Cooperating Allies carry their physical owner and Tribe. Ordinary Ally
entries use a null owner slot, leaving the existing piece helper in charge of
the acting faction's own counters. The terminal displays the Tribe, owner and
visibility and permits live board inspection throughout selection.

The current mandatory tier still filters the actual request. Exact physical
choices cannot move a later-tier piece ahead of eligible earlier pieces.
Each new Loss rebuilds availability, including after a hard target saves.
Older raw positions with unattached Ally counters retain their generic entry
when no physical Tribe record exists.

## Save and replay compatibility

Fresh durable responses must select offered physical identities. Existing
raw generic priorities and callbacks retain their within-tier default meaning.
Recorded generic prompts require explicit saved evidence before adapting.
The durable session compares the saved journal, replay expectation or pending
request with the new physical request and verifies the original board signature.
Only the added ordinary visibility and Tribe distinctions can differ. A
recorded generic response then selects the same default physical cohort it
previously selected. An unrelated board, changed Resources or a different
request cannot invoke that compatibility path. New decisions keep their exact
physical contract.

The older loss-tier fixtures now name the new offered identities while keeping
their tier rejection, saving-roll and rollback assertions. The older Elite
replay test creates a genuine generic legacy request before replaying it with
the new engine. Litaviccus fixtures now include the Ally Tribe name.

## Verification

**8,423 tests pass**, including all 50 new cases, with zero failures, errors or skips (284.61 seconds). Fifty new regressions cover
base and expansion human owners, all three visibility states, named Ally
discs, City/Citadel exclusion, combined owners, complete Attack/Counterattack,
terminal board inspection, invalid/duplicate/stale identities, second-casualty
save/resume/replay, old generic journals and exact-board compatibility guards.
The 519 focused Battle, Diviciacus, Litaviccus and agent/session tests pass.

An unchanged subset of the new tests runs against the existing parent APIs.
It produces 28 behavioral failures, eight passing controls and 14 deselected
cases. The controls include the German expansion visibility choices that
already worked. The accepted new test file passes all 50 cases.

Validation uses ten audited NPC games across all five scenarios and seeds
1–2. Mixed-seat matrices use hash seeds 0 and 987, Events, reactions and
internal replay. The historical balance guard uses all five scenarios and
seeds 1–20 with its existing baseline and 15-point band. All ten NPC games complete and audit cleanly, with no errors or integrity
findings, four ranked factions and consistent winner/ranking fields. Their
complete gameplay records and final hashes match the parent. Only elapsed
seconds, commit and source digest are excluded from that comparison.

Both complete mixed-seat JSON outputs match across hash seeds, covering 356
human turns, 96 Event attempts and 90 successful Events. There are zero hard
findings and zero partial games, with batch digest `d899b5732da10db5` and 40
executions including internal replay. The historical 100-game balance guard
passes its existing band, with a maximum difference of 15 percentage points
and 35 winner changes versus the historical baseline. These are separate from
the ten directly paired parent/current records.

All 49 protected inputs match the parent byte for byte, including the 47 rule
references, canonical constants and balance baseline. The archive includes
commands, source reconstruction data, raw results and checksums. Earlier
failed development/fixture runs are stored separately from accepted results.

## Progress

BATTLE-LOSS-IDENTITY closes one original finding, bringing the original bundle
to **37/50 closed (74%), 13 open**. Retreat survivor disposition, full Rampage
victim choices and the other existing findings retain their recorded status.
Separate mechanics leads, 34 unverified inventory rows, two source questions
and twelve adopted provisional rulings retain their dispositions.

[Machine-readable results](battle-loss-identity-2026-11-04-results.json) ·
[Evidence archive](battle-loss-identity-2026-11-04-evidence.zip)
