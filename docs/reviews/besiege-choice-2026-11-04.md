# Besiege physical target choice — 4 November 2026

Client date: America/Chicago. Parent `45568e3f98c21fd27e400d7177fe028e9837e02a`.
Tested working Python digest:
`fd297a94d10e34ff52875da001f4ba6f97e739e2b027e4846b2972d9bd2bddbe`
(486 Python files). The publishing commit includes this frozen source.

## Source and correction

Chapter 4 §4.2.3 lets the Roman Attacker choose a defending Citadel or Allied
Tribe to remove before and in addition to Losses, even zero Losses and regardless
of Retreat. It is optional. A4.2.3 also permits a German Settlement instead of
an Ally. A Citadel present originally still halves that Battle's Losses after
removal; card 10 unshaded Ballistae cancels Citadel halving with Besiege.

Previously, the executor selected the first piece type (Citadel, else Ally,
else Settlement); removal then cleared the default sorted allied Tribe. A human
could select neither another type nor a specific Ally disc. The engine now
presents `besiege_target` to the Roman at the actual pre-Loss step, after Retreat
declaration. It names each available physical Citadel or disc by Tribe, plus
German Settlements in Ariovistus. An explicit decline leaves every piece.

Responses select a whole offered `{piece_type, tribe}` object. Validation checks
both the trusted request and current board before removal. Only the chosen
Tribe's allegiance clears; a Settlement clears none. City Citadels are not also
offered as Ally discs. Separate Battle Regions receive separate live requests.
The announced Besiege/active Ballistae effect remains when its optional removal
is declined. Citadel halving is tracked from Battle start as before.

The terminal supports exact choices, decline and board inspection. Durable
responses cannot silently fall back: malformed or missing choices retain their
pending decision, board, RNG and inbox through rollback and save/resume.
Accepted choices replay with the same physical result. Detached previews use
existing defaults without consulting a live agent. The synthetic human policy
also chooses an offered physical target.

## Compatibility and limits

Raw callback None or explicit delegation keeps the established type priority
and sorted identity. Native all-bot play takes that path without additional RNG.
Low-level legacy fixtures with unbacked counters keep their old mechanics;
no Tribe identity is invented for an invalid legacy board. Existing direct
`resolve_battle(besiege_target=<piece type>)` calls still supply that default.
The named choice adds `tribe` to the Besiege result only for a named removal.

No bot priorities, baseline, reference files or canonical constants were tuned.
This closes BATTLE-BESIEGE-CHOICE only; ordinary Battle casualty identity,
Retreat choices, full Rampage victim choice, CV-PERSISTENCE, NPC Intimidate
pre-Battle targeting and other findings remain open.

## Validation

**7,917 tests pass** in the final full suite (332.11 seconds), with zero failures, errors or skips. **398 targeted tests pass**. There are 37 new regressions: both editions, Citadel
versus Ally, two physical Ally discs, Settlement, decline/default, malformed or
stale identities, zero Losses, Retreat declaration, Ballistae, terminal board
inspection, preview isolation, save/load, multiple Battle Regions and durable
rollback/save/resume with identical replay.

The unchanged new test file runs against an isolated parent using only existing
Battle APIs for the behavioral proof: 11 expected failures reproduce missing
target/decline choices; two legacy-default controls pass and 24 other tests are
deselected. Lazy imports for new-validator-only cases prevent missing APIs from
being mistaken for behavioral proof.

Ten native-bot cases use all five scenarios and seeds 1–2. Mixed-seat tests use
that seed set, hash seeds 0/987, reactions, Events and internal replay (40
executions total). All ten native-bot records complete and audit successfully, with no errors or
integrity findings, four ranked factions, consistent winner/ranking fields and
nonempty final hashes. Every gameplay field and final hash matches the parent;
only elapsed seconds, commit and source digest are excluded from comparison.
Both mixed-seat outputs agree in complete JSON across hash seeds: 247 human
turns, 77 Event attempts, 74 successful Events, zero hard findings, zero partials,
batch digest `c7366266d0681cf4`. Internal replay makes 40 executions in total. These bounded checks are
not a new balance study or full rules proof. The 47 supplied references,
canonical constants and balance baseline are protected (49 inputs).

## Progress

BATTLE-BESIEGE-CHOICE closes one original finding: **28/50 closed (56%), 22 open**.
The separate defects, 34 unverified inventory rows, two source questions and
twelve provisional rulings are not absorbed into that denominator.

[Machine-readable results](besiege-choice-2026-11-04-results.json) ·
[Evidence archive](besiege-choice-2026-11-04-evidence.zip)
