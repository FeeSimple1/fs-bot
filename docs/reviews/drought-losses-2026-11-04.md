# Drought owner-casualty batch — 4 November 2026

Client date: America/Chicago. Parent `e42b213dcfd57105f13f9ae44674fdd20b243a6a`.
Tested working Python digest:
`b33a8d39c1fcb3ba138527c95393986493eccf847b3193356d7c706249306037`
(501 Python files). The publishing commit includes this frozen source.

## Sources and repairs

Card Reference 49/Tips halves each Faction's Resources, rounded down, places
one new Devastated marker in a Region without one, then has each Faction
remove one of its own pieces from every Devastated Region. Owners choose
which exact piece. Legions go to Fallen, and German Warbands precede German
Allied Tribes. Chapter 1 §1.4.2 protects the permanent Provincia Fort;
A1.4 removes Diviciacus from play when lost. §8.4.1 reverses piece priorities
for own losses; §8.3.4 randomizes equal candidates. A8.2.3 gives Settlements
the same Event priority as Citadels.

Previously the handler silently chose losses, prioritizing Roman Legions over
Auxilia and Hidden before other soft pieces. Its only override was an
executor-authored Python tuple-keyed map, which could commandeer another
owner's loss and could not travel safely in ordinary JSON.

The new `drought_loss` request goes to the physical owner in each affected
Region, offering exact type/visibility, named Allied Tribe/Citadel, named
Leader, or hard piece. Owners cannot select another faction's pieces, decline
a required casualty, or remove an unavailable/stale target. German Allied
Tribes are withheld while German Warbands remain; other legal German piece
types remain selectable. The permanent Fort is excluded, including when it
is the only Roman piece. Empty/protected-only owners are not prompted.
Base Germans and expansion Arverni remain game-run and receive no human request.

Removals use piece helpers; named Tribe removals update the exact physical
backing and allegiance together. Legions go to Fallen without a roll; ordinary
Leaders return to Available and Diviciacus leaves play. Default losses remove
Scouted/Revealed/Hidden soft pieces before ordinary Allies, then City/Remi
Allies, structures, Legions and Leaders. Equal-priority Tribe candidates use
state RNG. This source correction can change future trajectories; it is not
bot tuning. Broader NPC marker-target policy is not reviewed by this batch.

## Frontends and compatibility

The terminal collects one legal marker location, then presents each owner's
live exact casualty menu with board inspection. Specified marker Regions must
be playable and not already Devastated. Existing per-owner Event timing windows
remain in place. Missing/invalid durable responses preserve pending identity
and earlier accepted choices through whole-Event rollback/save/resume, including
a second Region. Replay does not halve Resources or apply an earlier loss twice.
Previews consult no live human input and do not change the live RNG.

The old `piece_removals` override is explicitly rejected before mutation;
clients must answer the JSON-safe owner request. Silently importing a foreign
executor's old choice would bypass the owner's authority. Event parameters
accept `devastate_region` and existing `stage_timing_actions`; an omitted marker
retains the legacy automatic fallback. Older transcripts without the new
casualty decisions can require additional responses. The Drought portion of
BE-08's inferred-schema defect is repaired, but its other listed shapes remain
open. BE-07/EXP-11, ordinary Battle/Retreat/Rampage, CV-PERSISTENCE and NPC
Intimidate targeting retain their dispositions. No provisional ruling changes.
All 47 references, canonical constants and balance baseline are unchanged
(49 protected inputs).

## Validation

**8,260 tests pass** in the final full suite (211.39 seconds), with zero failures, errors or skips. **69 new cases** and **284 targeted tests** cover all
playable owners in both editions; exact visibility/Tribes/Leaders, Legion Fallen,
Diviciacus and Settlements; German restrictions, permanent Fort, corrected
NPC priority/ties, invalid/stale/foreign choices and markers, terminal inspection
and EOF, preview isolation, later-owner rollback and second-Region durable
pending/save/resume with identical replay.

An isolated parent runs the unchanged new test file through existing APIs:
**35 behavioral failures** reproduce missing owner choices and incorrect default
casualties; **one game-run control passes**, with 33 cases deselected. Failures
are behavior assertions, not missing helper imports.

Ten audited native-bot games cover all five scenarios and seeds 1–2. Mixed-seat
matrices use those seeds, hash seeds 0/987, Events, reactions and internal replay
(40 executions total). All ten native-bot games complete and audit successfully, with no errors or
integrity findings, four ranked factions, consistent winner/ranking fields and
nonempty final hashes. Nine gameplay records/final hashes match parent exactly,
excluding only elapsed seconds, commit and source digest. Reconquest seed 2
changes play but retains the Belgae winner. An instrumented replay matches the
batch final hashes and locates its first divergence at the seventh card, Drought
(49), with identical pre-card and pre-Event boards and identical marker maps.
At Morini, the parent removes a Roman Legion and retains a Revealed Auxilia;
the repair removes that Auxilia and retains the Legion, as §8.4.1 requires.
The raw before/after Event boards and per-card trace are archived.

Both mixed-seat outputs agree in complete JSON across hash seeds: 356 human
turns, 96 Event attempts, 90 successful Events, zero hard findings, zero partials,
batch digest `d899b5732da10db5`. Internal replay makes 40 executions in total.

The 100-game historical balance smoke uses all five scenarios, seeds 1–20,
the unchanged baseline and a 15-percentage-point band. The check passes, with a largest absolute difference of 15 percentage points and 35 winner changes versus the historical baseline. These are not changes versus the parent.
These bounded checks are not a full rules-compliance or unrestricted balance proof.

## Progress

BE-05 closes one original finding: **34/50 closed (68%), 16 open**.
Its partial BE-08 repair does not close another finding. The separate defects,
34 unverified inventory rows, two source questions and twelve adopted provisional
rulings keep their dispositions.

[Machine-readable results](drought-losses-2026-11-04-results.json) ·
[Evidence archive](drought-losses-2026-11-04-evidence.zip)
