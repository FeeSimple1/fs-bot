# Current engineering status

This document supersedes older completion claims in `QUESTIONS.md` and the
build plan. It distinguishes verified engineering fixes, adopted provisional
project rulings, and unresolved external source questions. The historical audit reports retain their original results;
their game outcomes are not a baseline for a later rules revision.

[Documentation index](README.md) · [Playing guide](../PLAYING.md) ·
[Current question index](../QUESTIONS.md#current-open-source-questions)

This page includes the 24 October adoption of six and 29 October adoption
of three additional rulings, the 2 November adoption of PR-10/PR-11,
the 3 November adoption of PR-12, and the 5 November adoption of PR-13
([provisional register](provisional-rulings.md)), the follow-up
repairs, and the 23 October implementation review. The
[provisional-ruling report](reviews/provisional-rulings-2026-10-24.md)
records validation of the first six rulings on its 24 October revision.
Each dated report keeps
its own revision, source digest and outcome evidence; earlier checkpoint
measurements have not been relabeled as results of later changes.

## Follow-up repairs

### 10 November fourth comparison repair Batch 2

The [second repair batch](reviews/fourth-comparison-batch2-2026-11-10.md)
closes four groups. Free Battles check both forces at resolution, and
Event scope validation reads the ability plan the executor will use.
Shaded Assembly of Gaul accepts two free Special Activities with their
own timing. Druids validates the beneficiary list, then resolves the
mandatory Limited Commands in printed order.

All **9,777 tests pass**, including 55 new cases. Twenty second-edition
bot games pass audit. Twenty mixed-player cases match across two hash
seeds with replay, zero hard findings and one soft partial plan. The
100-game balance check passes its 15-point band. All 23 winner changes
across the bot matrices first diverge on Druids.

The [fourth-audit ledger](reviews/comparison-audit-round4-2026-11-10.json)
records **10 of 16 repaired, 6 open**.

### 10 November fourth comparison repair Batch 1

The [first repair batch](reviews/fourth-comparison-batch1-2026-11-10.md)
closes six groups. Shaded Hostages binds both pieces to the chosen Tribe.
Celtic Rites requires a Gallic selection and applies each loss once. Shaded
Germanic Horse goes to its Gallic executor. Abatis requires a qualifying
Region when available. Bellovaci checks the troop owner and type together.
Harvest keeps Resources within the printed 0–45 track.

All **9,722 tests pass**, including 36 added cases. The same cases produce
34 failures and two passing controls on the parent. Twenty second-edition
bot games are clean. Twenty mixed-player cases match across hash seeds with
replay, zero hard findings, and one soft partial plan. The 100-game balance
check passes its existing 15-point band. The report traces the two winner
changes from the parent to Hostages and Celtic Rites.

The [fourth-audit ledger](reviews/comparison-audit-round4-2026-11-10.json)
records **6 of 16 repaired, 10 open**.

### 10 November fourth comparison audit

The [fourth Liberty or Death comparison](reviews/comparison-audit-round4-2026-11-10.md)
confirmed **16 repair groups, 11 high and 5 medium priority**. These
cover Event target/beneficiary validation, free-action scope and choices,
Battle and bot forecasts, negative Harvest Resources, and Interlude deck/Tribe
conversion. Earlier 50-, 21-, and 15-group ledgers remain fully closed.

All 9,686 existing tests pass. Ten final witness scripts independently
reproduce the findings after fixture source review. Twenty audited bot games
are clean. Twenty mixed-seat cases match across hash seeds with replay, zero
hard findings, and one soft partial plan. Both matrices use second-edition
cards and seeds 25–28 in all five scenarios. No gameplay code changed and no
new balance matrix was run. The report provides a ledger, evidence and repair
order. All 16 findings were open at the audit revision.

A33 Wailing Women's undefined outnumbering comparison is recorded separately
in `QUESTIONS.md` and is not counted as a confirmed defect. Existing
Circumvallation persistence work remains separate too.

### 10 November third comparison repair Batch 4

The [final repair batch](reviews/third-comparison-batch4-2026-11-10.md)
closes XC3-01, XC3-02, and EX3-04. The Colony uses its recorded Region in
Seize, Build, Entreat, Trade, replacement Events, and Belgic Control Value.
Razed Cities earn no Seize Forage, cannot be Dispersed again, and retain
their marker through Spring. Stalwart cancels both sides of Germanic Horse's
additional Losses against Germans, including Counterattack.

All **9,686 tests pass**, including 104 added cases. The same cases produce
68 failures and 36 positive controls on the parent. Twenty audited bot
games are clean. Twenty mixed-player cases match across hash seeds with
replay, zero hard findings, and four soft partial plans. The 100-game
balance check passes its unchanged 15-point band. No winners change from
the parent; one Roman win ends earlier after a legal Colony dispersal.

The [third-audit ledger](reviews/comparison-audit-round3-2026-11-10.json)
records **15 of 15 groups repaired, 0 remaining**.

### 10 November third comparison repair Batch 3

The [third repair batch](reviews/third-comparison-batch3-2026-11-10.md)
closes BE3-01, BE3-03, BE3-04, EX3-01, and EX3-03. Consuetudine applies its
printed Ambush exception and Scouted hide step. Colony creates its Tribe despite
Ally scarcity. Migration requires possible Ally placement and preserves legal
partial movement. Harudes completes its attainable reinforcements before its
surviving cohort's Raid. Nasua & Cimberius replaces Treveri's actual marker.

All **9,582 tests pass**, including 60 new cases. Those cases produce 37 failures
and 23 positive controls on the parent. Twenty audited bot games match parent
winners and final states. Twenty mixed-player cases match across hash seeds with
replay, zero hard findings and four soft partial plans. The unchanged 100-game
balance baseline passes its existing 15-point band, with three winner changes.

The [third-audit ledger](reviews/comparison-audit-round3-2026-11-10.json)
recorded **12 of 15 groups repaired (80%), with 3 remaining** at the Batch 3 checkpoint.

### 10 November third comparison repair Batch 2

The [second repair batch](reviews/third-comparison-batch2-2026-11-10.md)
closes CM3-01, CM3-03, WS3-01, and WS3-02. Scout validates playable endpoints;
Battle requires attacking Forces after preceding movement and timing choices.
Harvest counts each physical Ally disc and Citadel once. Lost Eagle affects
only the upcoming Senate Phase and expires through scenario exceptions.

All **9,522 tests pass**, including 49 added cases and a corrected legacy
Senate expectation. The 50 changed cases produce 28 failures and 22 positive
controls on the parent. Twenty audited bot games are clean. Twenty mixed-player
cases match across hash seeds with replay, zero hard findings and four soft
partial plans. Restoring only the old seasonal behavior reproduces all 100
parent winners and game lengths. The corrected 100-game balance matrix passes
against a reviewed baseline with the same seeds and 15-point band.

The [third-audit ledger](reviews/comparison-audit-round3-2026-11-10.json)
recorded **7 of 15 groups repaired (47%), with 8 remaining** at the Batch 2 checkpoint.

### 10 November third comparison repair Batch 1

The [first repair batch](reviews/third-comparison-batch1-2026-11-10.md)
closes FE3-01, CM3-02, and CM3-04. Human turn fields and accepted journal
records now retain their assigned roles through pause, save, resume, and
replay. Entreat validates and removes the named physical Ally disc.
Ordinary Battle receives Event-specific modifiers from trusted Event
resolution.

All 9,473 tests passed, including 62 new cases. The same cases produced
58 failures and four passing controls on the audit engine. Valid older
tuple-form March choices resume after JSON save and reload. A conflicting
older journal pauses with an explanation and preserves board, RNG, and
committed history.

Twenty audited all-bot records match the parent. Twenty mixed-player
cases match across hash seeds 0 and 987 and match the audit revision,
with zero hard findings and four soft partial plans. All 100 balance
outcomes match the parent, and the existing guardrail passed.

The [third-audit ledger](reviews/comparison-audit-round3-2026-11-10.json)
recorded **3 of 15 groups repaired (20%), with 12 remaining** at the Batch 1 checkpoint.

### 10 November third comparison audit

The [third Liberty or Death comparison](reviews/comparison-audit-round3-2026-11-10.md)
confirms **15 additional open repair groups**, with executable witnesses and
independent source review. These cover authored turn metadata, Scout geography,
Entreat piece identity, ordinary Battle prerequisites and unauthorized modifiers,
Harvest counting, Lost Eagle timing, missed Event effects, Colony consumers,
and Razed-marker permanence. The report and machine-readable ledger retain
the precise affected paths and proposed repair batches.

All 9,411 existing tests passed. Twenty mixed-seat cases across five scenarios
matched under hash seeds 0 and 987, with replay enabled, zero hard findings,
and four soft partial plans. Eight targeted witness scripts independently
reproduced the newly confirmed defects. No gameplay code or references changed
in this audit, and no new balance matrix is claimed.

The earlier 50-finding and 21-finding ledgers remain fully closed. The new
ledger starts at **0 of 15 closed, 15 remaining**. Related symptoms are grouped
together; existing Circumvallation persistence work and unresolved source
questions remain separate.

### 10 November mandatory Event effects and physical targets

Unshaded Remi Influence requires at least one eligible Ally replacement
when its Remi condition applies. Shaded Siege of Bibrax retains its
optional zero to five removals and uses the selected Ally's Tribe. A
legacy entry without the Tribe resolves when one physical piece matches.
Abatis recognizes Scouted Warbands as qualifying pieces (§§1.4.3, 4.2.2).

Shaded Orgetorix, Galba, and Kinship require their printed quantities as
far as possible (§5.1.3). Orgetorix checks placement supply after clearing
the two Regions and preserves City slots needed to reach the attainable
total. Galba checks both placement stages before its Resource gain.
Kinship checks Warbands and Allies separately and removes eligible sources
even when the counterpart is unavailable or cannot stack (§5.1.1).
Terminal plans and non-player defaults use the same current-board choices
as execution. An incomplete plan rolls back its earlier removals and
placements.

All 9,411 tests passed, including 20 new regressions. An assistant session
rejected an incomplete Galba plan, kept the pending turn and board intact,
and replayed a corrected submission exactly. Twenty all-bot games
completed with clean audits. The 20 mixed-seat results matched across
both hash seeds with zero hard findings and three partial plans.

Both balance checks passed against the existing baseline. Across the
100-game matrix, 12 winners and nine game lengths changed across 13 games
relative to the parent. Paired replays of those games and the additional
changed all-bot records first diverged at Remi Influence, Orgetorix, or
Galba. The ledger records each case.

**Batch 4 closes the final four findings.** The
[comparison ledger](reviews/comparison-audit-2026-11-10.json) stands at
**21 of 21 closed, 0 remaining.**

### 10 November Event prerequisites, targets, and scoring

Shaded Sacking requires a Legion at the executor's Citadel. Assembly of
Gaul unshaded drains each selected Gallic faction once. Alaudae requires
Roman Control, and both Numidians editions require a Region within one of
the Roman Leader. Execution and the terminal use the same Region checks.
Invalid explicit selections roll back before any placement or removal.

Shaded Lucterius and Flight of Ambiorix restore a Successor symbol-up,
including in his current Region when legal. Flight enforces its printed
return area and reads the ordinary Belgic Control-Allies score for the
unshaded removal. Procillus unshaded requires the named Caesar.

Seduni Uprising preserves Citadels while replacing the named Allied Tribe
discs. Shaded Dumnorix removes only structures at Bituriges, Bibracte, and
Helvetii, preserving the Sequani Citadel. Shaded Kinship restricts the
replacement to Belgae and Germans.

The original 100-game check passed its 15-point band. The three-seed
canary exceeded its 40-point band in The Great Revolt. Across the full
matrix, four outcomes changed versus the parent. Paired replays matched
the boards before these first changed Events.

| Scenario and seed | Parent outcome | Repaired outcome | First changed Event |
|---|---|---|---|
| The Great Revolt 2 | Arverni in 43 cards | Aedui in 43 cards | Flight restores Ambiorix from the Successor at Nervii |
| The Great Revolt 18 | Arverni in 43 cards | Aedui in 43 cards | Flight restores Ambiorix from the Successor at Britannia |
| Ariovistus 3 | Belgae in 45 cards | Aedui in 45 cards | Dumnorix preserves the Arverni Citadel at Sequani |
| The Gallic War 3 | Aedui in 100 cards | Romans in 72 cards | Dumnorix preserves the Arverni Citadel at Sequani |

The baseline refresh updates those four records within the same 100-game
matrix. Both balance checks passed at their existing tolerances.

All 9,391 tests passed, including 24 new regressions. Twenty all-bot
games completed with clean audits. Twenty mixed-seat games agree across
both hash seeds, with zero hard findings and five partial plans.

**Batch 3 closes nine findings.** The
[comparison ledger](reviews/comparison-audit-2026-11-10.json) stands at
**17 of 21 closed, 4 remaining.**

### 10 November Orgetorix Citadel placement

Shaded Orgetorix records an Arverni Citadel and its City Tribe's allegiance
together. The Citadel represents the Allied Tribe under §1.4.2. The Event's
printed exception permits the Arverni placement at Bibracte (A Card
Reference A30 shaded and §A5.1.1). The regression cases cover placement at
an empty Sequani City in Ariovistus and replacement of an Aedui Citadel at
Bibracte in The Gallic War. Both verify City allegiance, piece inventory,
and structural integrity through the accepted human Event.

All 9,367 tests pass. The 20 all-bot records, 20 mixed-seat records and
100 balance-game outcomes match the parent. The mixed-seat results agree
across both hash seeds with zero hard findings and five partial plans.
The balance check passed its 15-point band.

**EX2-07 closes and Batch 2 is complete.** The
[comparison ledger](reviews/comparison-audit-2026-11-10.json) stands at
**8 of 21 closed, 13 remaining.**

### 10 November Forts, Citadels, and Ambush

Forts and Citadels halve Attack Losses, rounded down, during an Ambush.
Each resulting Loss removes a defending piece without a saving roll.
Roman defenders with Caesar regain their usual saving rolls and may
Counterattack on a 4–6 test, or on 5–6 against Belgae. The same procedure
applies to base-game German Battle. Ariovistus German Battle uses it only
when modified by Ambush (Chapters 3 and 4 §§3.3.4, 3.4.4, 4.3.3,
4.4.3, 4.5.3 and Ariovistus §§A3.4.4, A4.6.3).

All 9,365 tests pass, including 106 Battle tests. All 20 all-bot games
completed with clean audits. The 20 mixed-seat results match across both
hash seeds, with zero hard findings and five partial plans versus four
on the parent. The 100-game balance check passed its 15-point band.
Relative to the parent, 27 winners and 18 game lengths changed across
33 games. In paired replays of Reconquest of Gaul seed 3 and The Great
Revolt seed 6, the first differing Battle was a fortified Ambush in
Treveri. Both revisions removed the same Legion, and the repair skipped
its saving die, changing the subsequent random sequence.

**BM2-01 closes.** The
[comparison ledger](reviews/comparison-audit-2026-11-10.json) stands at
**7 of 21 closed, 14 remaining.**

### 10 November human turn plan scope

The first comparison repair batch binds a human submission to the offered
action and the current card (§2.3.4). A Command-only response cannot execute
an Event or add a Special Ability. An Event resolves its printed grants
through their own requests. Rejected responses retain the same pending
decision, board, random state, and committed log. Corrected responses can
resume and replay.

Only a valid during-Command interruption accepts two Command portions.
Limited March counts origins in the executable plan, including explicit
moves and implicit Leader routes. Extra groups use selected origins. All
routes enforce the Britannia restriction, and the executor rechecks scope
after timing effects and before paying or moving (§§2.3.5, 4.1.3).
Battle selects each Region once with one opposing defender. Devastate
applies one round of casualties per selected Region in each Special
Ability (§§3.1, 3.2.4, 4.1, 4.3.2).

All 9,357 tests pass, including 23 new regressions. The 20 all-bot gameplay
records and the winners and game lengths of all 100 balance games match
the parent. The balance guardrail passed. Twenty mixed-seat records match
the parent across both hash seeds, with zero hard findings and the same
four partial plans.

**FE2-01, FE2-02, XC2-01, CM2-01, CM2-02, and CM2-03 close.** The
[comparison ledger](reviews/comparison-audit-2026-11-10.json) stands at
**6 of 21 closed, 15 remaining.**

### 10 November second Liberty or Death comparison

The comparative audit confirms **21 additional open finding groups, with
15 high and 6 medium priority**. It covers human action contracts, Limited
Command scope, repeated effects, Ambush defense, and base/expansion Event
prerequisites, quantities, and physical targets. Two defects reproduce in
ordinary assistant sessions through initialization and submission.

All 9,334 existing tests pass. Independent review reproduced nine probe
scripts. The earlier 34 unverified rows now have 12 confirmed-gap, seven
limited-positive, and 15 still-unverified dispositions. The original
50-finding repair ledger retains its historical scope. The new repair
queue begins at **0/21 closed, 21 remaining**. Previously recorded
Circumvallation persistence work is tracked in its own report.

The report includes the comparison methods, exact sources, observed
behavior, repair order, and portable evidence.
[Comparison audit](reviews/comparison-audit-2026-11-10.md) ·
[New finding ledger](reviews/comparison-audit-2026-11-10.json)

### 10 November Spare Factions and shared-player ownership

Setup can assign both members of a printed Spare Factions pair to one
player (§1.5.1/A1.5.1). The terminal offers both pairs, and the assistant
can run a pair's turns and reactions in one session. A German player takes
over Arverni at the Gallic War Interlude and keeps Belgae if paired.
Assignments persist through save, resume, and replay.

A pair qualifies for early victory when both Factions pass and ranks by
its lower margin (§7.1/A7.1). Great Revolt's Arverni and Belgae pair
qualifies when either passes and ranks by its higher margin. A qualifying
Non-player still takes priority. Great Revolt starts Belgae with Ambiorix
if a player runs Belgae alone or a player runs the Romans and Aedui pair.
Legacy setups without ownership data retain their original setup rules.

Each outer Command or Event allows four Resources in combined gifts between
the pair (§1.5.2). Authored and live gifts use the same allowance in both
directions. Winter gifts and transfers specified by card text follow their
own rules. The assistant preserves the remaining allowance when it reloads
and replays an interrupted action.

All 9,334 tests pass, including 49 focused ownership, setup, and rules-trace
tests. All 20 all-bot gameplay records and all 100 seeded balance winners
and game lengths match the parent. The balance guardrail passed. Twenty
mixed-seat games match the parent and each other across hash seeds 0 and 987
with zero hard findings and the same four partial plans.

**WS-F09 closes. All 50 original human-choice audit findings are closed.**
See the [audit progress ledger](human-choice-progress.json) for the tested
source and individual dispositions. It tracks the 34 unverified inventory
rows separately.

### 10 November March Special Ability timing

One standalone Special Ability can resolve during an ordinary March (§4.1).
Pause after origin preparation, at a transit hop, or between groups. Caesar
can now Build in Sequani while Marching from Provincia to Mandubii (§§3.2.2,
4.2.1). A subsequent origin can use Trade proceeds and pays once when selected.

The same March resumes with the surviving moving counters. Scout can split
Auxilia off or change their visibility before Harassment. Devastate losses
can distinguish members of the group from identical residents. An arriving
counter stays out of later groups, even after an origin-wide visibility
change. Separate Diviciacus agreements retain the Command's exact loaned
counters. The terminal offers choices on a detached board, and the durable
assistant can reload a live choice and replay through the pause.

All 9,307 tests pass, including 20 directed March timing cases. The 20
mixed-seat games match across hash seeds with zero hard findings. All 20
all-bot gameplay records and all 100 paired balance winners and game
lengths match the parent. The balance guardrail passed.

TIMING-SA-DURING closed the 49th of the 50 original audit findings at
this checkpoint.

### 10 November Battle and Raid Special Ability timing

Human players can use a standalone Special Ability between Battle Regions
or between Raid flips (§4.1). Battle keeps one ordered plan, per-Region
payments, and Command-wide Capability selections. The Raid procedure can
resume in the same Region. It counts all flips against one limit and resolves
Ariovistus's intrinsic Intimidate once for that Region with the actual raiders.
The Battle and Raid executors retain their Command agreements separately
from any cooperation sought for the Special Ability (A1.4).

The terminal plans on a detached board. Its Raid menu can offer a target
that the intervening Special Ability just made legal. Typed plans identify
the interruption with `details.sa_after_step`. A durable save at a live
decision within the Special Ability resumes the same Command without
repeating a paid Battle or a Capability choice. Ambush and Besiege use the
existing Battle modifier procedure.

All 9,287 tests pass, including 16 directed timing cases. Twenty mixed-seat
games match across hash seeds with zero hard findings. The 20 all-bot
records match the parent revision on gameplay results. Winners and game
lengths match the parent in all 100 paired balance games. The balance
guardrail passed.

At this checkpoint the original audit stood at 48/50 closed (96%). The
March follow-up completes the timing finding.

### 10 November Non-player Retreat Leader placement

Non-players now choose where their Leader ends a Retreat after the Attack
and its losses (§8.4.3). They count the pieces that will actually end up
with the Leader, including surviving static pieces in place and mobile
survivors that would accompany the Leader to another Region. Against
Romans, eligible Hidden Warbands stay in place. Where the survivors can
join their Leader in an adjacent Region, they do so. Equal choices for
the Leader use the game's seeded random selection (§8.3.4).

The disposition uses current Control and the host agreements already
obtained before the Attack. Frost forecasts check every tied Leader
destination. The original human-choice audit remains at 48/50 closed
(96%), with two findings open.

The terminal and assistant replayed a tied NPC Leader destination exactly.
An older replay can diverge when the repaired choice moves a Leader or
uses a new tie roll. The seeded mixed-seat tests still check completion
and replay. A separate directed fixture now checks the opening gift and
partial Rally that the former seed no longer reaches.

All 9,271 tests pass, including ten directed Retreat placement cases.
Twenty mixed-seat games had zero hard findings and matched across hash
seeds. Five of 20 all-bot records changed. Against the prior revision,
nine of 100 balance outcomes changed in winner or game length, including
five winner changes. The existing balance guardrail passed.

### 10 November Battle Retreat choices

Human defenders now declare Retreat before the Attack and choose the
disposition of the actual surviving pieces afterward (§§3.2.4, 3.3.4,
A3.2.4). Against Romans the defender can leave any number of surviving
Hidden Warbands and choose whether the Leader stays. The rest move together
to one legal Region or are removed, even if there is no destination.
The destination check uses current Control and the specific host agreements
made before the Attack. No Counterattack or Reveal occurs after a Retreat.

The terminal and assistant offer both decisions. The assistant retains
accepted declarations and Loss choices across a reload. Verified old
declaration prompts retain their original contract. Older transcripts that
include now-ineligible declarations can diverge. The detached Battle
forecasts include removal-only Retreats and the legal Roman-attack stay
choices where applicable.

All 9,260 tests pass. Thirteen directed cases cover actual survivors, a
static-only defender, changes in Control, forecast choices and durable
reloads. Both frontends replayed a removal-only Retreat exactly. Twenty
paired all-bot records and 100 balance outcomes match the parent. Twenty
opt-in mixed games completed with zero hard findings and matched across
hash seeds, exercising 48 survivor choices per pass. The Gallic War
partial-Command regression now uses seed 21, which still reaches an
opening Resource gift followed by a partly affordable Command.

**BATTLE-RETREAT-CHOICES closes. The original audit stands at 48/50 closed
(96%), with two findings open.**

The [non-player placement repair](#10-november-non-player-retreat-leader-placement)
addresses a separate finding under §8.4.3. In the original Roman attack on
Carnutes, the Belgic bot Retreats
after losing its only local Warband, but Ambiorix stays in Carnutes even
though five Belgic Warbands are in the legal destination of Atrebates.

### 10 November March groups at later origins

Ordinary March now leaves earlier arrivals and transit drop-offs out of
every later group in the same Command (§§3.2.2, 3.3.2, A3.4.2). Later
origins still pay once and apply their normal hiding procedure. Physical
ownership and visibility determine which pieces can form each group,
including Diviciacus and Enlist loans. Voluntary removal can distinguish
already marched pieces from residents and the currently moving group.
The explicit-group March API also checks the remaining eligible pieces.

All 9,247 tests pass. Thirteen regression cases cover chained origins, a
forced stop, drop-offs, Harassment, same-origin groups, loan ownership and
durable reload and replay. The terminal replayed both a new March with an already marched
removal and an unaffected March recorded on the parent revision. Twenty
paired all-bot records and 100 balance outcomes match the parent. Twenty
mixed-seat games completed with zero hard findings and matched across hash
seeds.

The original audit remains at 47/50 closed (94%), with three findings open.
Earlier transcripts can diverge if their requests or results depended on
the previous grouping.

### 10 November Ordinary March drop-offs

The terminal and assistant now ask at a live intermediate stop which
carried pieces to leave before the group departs and faces Harassment.
They show exact visibility and physical owner, including for Diviciacus
loans. The next stop's offer uses the surviving group. A Leader can be
left if the next hop is legal for the remainder. Leaving Caesar at the
first stop can shorten a planned three-hop route to two.

Accepted choices are recorded by group and step. The action transaction
preserves pending choices across a save or reload. The private Event
Marches retain their card-specific movement and drop-off rules.

All 9,234 tests pass. Twenty directed Marches across the five scenarios
made 35 drop-offs and matched across hash seeds. The terminal replayed
both a March with two live drop-offs and a transcript from the parent
revision. The assistant preserved pending decisions through invalid
submissions and reproduced the saved board, history and RNG. Twenty
paired bot records and 100 balance outcomes match the parent. Twenty
mixed-seat games completed with zero hard findings.

An older multi-origin formation defect surfaced during this work. When
a later origin uses an implicit whole group, it can select earlier
arrivals. The parent revision reproduces this with two Roman Auxilia
entering Nervii and the later Nervii group moving all three Auxilia.
The [later-origin repair](#10-november-march-groups-at-later-origins) closes
that separate follow-up.

**MARCH-DROPOFF closes. The original audit stands at 47/50 closed (94%),
with three findings open.**

### 10 November Command and Event Resource transfers

The terminal and assistant offer exact donor-owned gifts at the opening,
at live Command and Event operation boundaries, and before the action closes.
Every gift involves the outer executor, including during Events that grant
other factions actions. The terminal opens before collecting the plan, so
incoming Resources can fund it. The assistant can fund a later planned step
with a live gift. Donors can choose to finish for the action or reserve
another offer. The legacy terminal plan collector now accepts multiple gifts
and the full legal amount.

Scenario rules, the Diviciacus prohibition and the separate non-player Aedui
subsidy still govern transfers. A53 grants use their own spending budget.
Ordinary gifts between its granted actions change the public Roman treasury.
Accepted gifts are replayed exactly once when a pending action resumes.

All 9,225 tests pass, including 83 focused transfer and Frumentum tests.
The terminal and assistant replayed live gifts and older transcripts to the
same board and random state. Twenty mixed-seat games matched across hash
seeds with zero hard findings. Three partial effects matched between
dry-run and live execution. Twenty paired bot runs match the parent revision's
final boards and diagnostics. All 100 balance winners and card counts match
the parent.

**WS-F06 closed the 46th of the 50 original audit findings.** The
[Spare Factions repair](#10-november-spare-factions-and-shared-player-ownership)
added the shared-player cap.

### 10 November Winter Resource transfers

Eligible human donors can give Resources before Quarters relocations and
after Roman payments, and before and after Harvest earnings. Opening gifts
can fund Roman quartering or make room for Harvest income. Later donors
see the live balances. Both frontends accept split or repeated gifts in
exact amounts within the donor's stock and the recipient's Resource cap.
The same scenario and Capability restrictions apply as for ordinary gifts.

The assistant validates a donor's entire list before applying it. A save
at a later decision retains accepted gifts, and earlier transcripts can
replay without a new gift at unrecorded windows.

All 9,218 tests pass, including 324 focused tests. Twenty directed
scenario-and-seat positions exercised every window and matched across hash
seeds. Twenty mixed-seat games completed and replayed without hard findings.
One unaffordable Arverni Rally sub-action was refused in both preview and
live play. Twenty paired bot games and all 100 balance outcomes match the
parent. A terminal transcript recorded without the gift windows replayed
to the same board and random state.

**WS-F06 advanced at this checkpoint, with 45/50 audit findings closed (90%).
The subsequent Command and Event repair completes the finding.**

### 10 November Interlude Cisalpina relocation

The Gallic War's Cisalpina step now offers each human controller a complete
allocation in the printed order. The German seat chooses for both German
and Arverni pieces. Moves go to legal first-half Home Regions and preserve
visibility and Leader identity. Allied Tribe slots must be Subdued and free.
The terminal and assistant share the allocation checks with the A5 Event.

Gallia Togata bypasses the step. Bot delegation keeps the remove-all
procedure, including the Legions Track destination for removed Legions.
A Fort remaining in Cisalpina must come off because Provincia's permanent
Fort occupies its only Home slot. The later Britannia expedition uses the
surviving Roman forces. Accepted allocations persist through a later Winter
pause, save, and replay.

All 9,211 tests pass, including 264 focused Interlude and Gallia Togata
tests. Twenty paired bot games match the parent revision's winners and
final states. Twenty mixed-seat games and twenty directed Interludes replay
identically across hash seeds without integrity findings. The 100-game
balance check passes and matches all winners and card counts to the parent.

**WS-C30 and WS-F01 are complete. The original audit stands at 45/50
closed (90%), with 5 open.**

### 10 November Roman Interlude force reductions

The Gallic War scenario's Adjust Forces step offers Romans the exact Forts,
Allies, and Auxilia to return to Available. The separate half minimums round
up. The permanent Provincia Fort and all Legions are protected. Provincia
comes last separately for Allies and Auxilia. The resulting board determines
Caesar's placement and the later expedition's available Auxilia.

The terminal and assistant support the same allocation and seeded bot
delegation. Saving at a later choice retains the accepted reduction. A save
that already reached a later Roman Interlude prompt under the previous
version retains its original seeded reduction and can resume at that prompt.

All 9,204 tests pass, including 203 Interlude tests. Twenty paired bot
games match the parent revision's winners and final states. Twenty mixed-seat
games and twenty directed Roman Interludes replay identically across hash
seeds without integrity findings. All 100 balance games match the parent's
winners and card counts and pass the reviewed balance guardrail.

**WS-C28 is complete. WS-F01 remains open for Cisalpina relocation.
The original audit stands at 44/50 closed (88%), with 6 open.**

### 10 November Arverni Interlude force adjustments

Under A2.1, the German controller selects two eligible Arverni Citadels,
taking Gergovia last. The response order determines which Citadel receives
a scarce Ally disc. The later half reductions use the resulting board,
with exact Ally Tribes and Warband visibility. Both choices belong to
the German seat until the scenario switches to its second half.

The Cadurci and Volcae exception now selects those named Ally discs.
The previous bot treated their entire Region as an early target,
including Gergovia and Warbands. Gergovia's restoration now checks its
own Tribe. Saving while awaiting the Arverni reduction retains the prior
German and Citadel answers and replays them once on resume.

All 9,197 tests passed on the recovered source. Twenty paired bot games
match the Aedui repair's final states and winners. Twenty mixed-seat games
and twenty directed Arverni Interludes match across hash seeds, with no
integrity findings in the mixed-seat runs. The 100-game balance check
passes. Every winner and card count matches the parent revision.

**WS-F01 and WS-C28 advance. Roman force adjustments and Cisalpina
relocation remain open. The original audit stands at 44/50 closed
(88%), with 6 open.**

### 6 November Aedui Interlude force adjustments

Under A2.1, the Aedui player chooses one eligible Citadel after Diviciacus
leaves play. Bibracte is eligible only when it is the sole Citadel.
The choice replaces the Citadel with an Ally if a disc is Available and
removes it otherwise. The subsequent half reductions use the new board
and offer exact Ally Tribes and Warband visibility, with the Aedui Region
last for each type.

If Bibracte lacks its own Aedui Ally or Citadel after the reductions,
the restoration now checks the named Tribe even when a Colony Ally
occupies the same Region. Saving at the reduction prompt retains the
accepted Citadel selection. The terminal and assistant support exact
choices and delegation to the seeded bot.

Twenty paired bot games match the previous final boards and winners.
Twenty mixed-seat games and twenty directed Aedui Interludes replay
identically across hash seeds without integrity findings. The 100-game
balance check passes, with the same winners as the parent revision.
Gallic War seed 17 lasts 88 cards instead of 69 after Bibracte is
restored. The targeted replay has no integrity findings.

**WS-F01 and WS-C28 advance. Arverni and Roman force adjustments and
Cisalpina relocation remain open. The original audit stands at 44/50
closed (88%), with 6 open.**

### 6 November Belgic Interlude force reduction

Under A2.1, Belgae choose at least half of the on-map Allies and half
of the on-map Warbands to return to Available. Each minimum rounds up.
The menu enforces Belgica last within each piece type. It names the
Tribe for every Ally disc and distinguishes Hidden, Revealed and
Scouted Warbands. Citadels are outside the reduction.

The surviving forces determine the candidates for Ambiorix's placement.
If the human seat pauses at a tie, Winter restores the board and
retains the accepted reduction in its journal. The terminal and
assistant support exact allocation and delegation to the seeded bot
default.

Twenty paired bot games match the previous final boards and winners.
Twenty-one mixed-seat games match across two hash seeds without hard
findings or partial actions. This includes Gallic War seed 13, which
reaches the new Belgic choice. All 100 balance results match the previous
revision by winner and card count.

**WS-F01 and WS-C28 advance. Aedui, Arverni and Roman force
adjustments and Cisalpina relocation remain open. The original audit
stands at 44/50 closed (88%), with 6 open.**

### 6 November German Interlude Settlement conversion

Under A2.1 and §§1.4.1–1.4.3, after the permanent Warband removal the
German player chooses which eligible Settlements receive Allies and
which Subdued Tribe each Ally occupies. The allocation uses as many
eligible Ally discs as the Available pool permits. This respects the
Aedui and Arverni Tribe stacking restrictions that the previous default
overlooked. Each remaining Settlement converts to up to three Hidden
Warbands from Available.

The terminal and assistant offer the choice when more than one allocation
is legal. The quarter reduction uses the resulting board and includes
the new Allies by Tribe. Saving while waiting for that reduction preserves
the prior removal and Settlement answers. The bot and explicit delegation
use the first legal allocations in the existing map order.

All 9,167 tests pass, including 15 new cases. Twenty paired bot games
match the previous final boards and winners. Twenty mixed-seat games
match across two hash seeds without hard findings or partial actions.
The 100-game balance check passes. Gallic War seed 15 shifts from a
Roman to a Belgic win after the bot stops placing a German Ally at
the reserved Aedui Tribe. Its targeted run completes without integrity
findings.

**WS-C27 is complete. WS-F01 remains open for the other factions' force
adjustments and Cisalpina relocation. The original audit stands at
44/50 closed (88%), with 6 open.**

### 6 November German Interlude force reductions

Under A2.1, the German player chooses the 15 Warbands removed from play
from the map and Available. After Settlement conversion, the player returns
at least one quarter of the on-map Allies and one quarter of the on-map
Warbands to Available. Each minimum rounds up. The second allocation
takes Germania last within each piece type. Warbands are selected by
Region and visibility. Allies are selected by Tribe.

The terminal and assistant offer both stages. The saved Winter transaction
restores the board when a response is pending, retains an accepted first
choice, and replays each allocation once. Either stage can use the seeded
bot procedure. Twenty paired bot games retain all final boards and winners,
including two completed Interludes. Twenty-one mixed-seat games match
across two hash seeds without hard findings or partial actions. This includes
Gallic War seed 13, which exercises both German decisions before the
Arverni handover. The 100-game balance check passes with every winner
and card count matching the previous revision.

**WS-F01 advances. Settlement conversion choices, other factions' force
adjustments and Cisalpina relocation remain open. The original audit stays
at 44/50 closed (88%), with 6 open.**

### 6 November shaded Land of Mist and Mystery 57

Under Card Reference 57 and §§5.1–5.1.3, the terminal authors a structured
Britannia removal with its type and exact Tribe. It offers named Allies
and either face of a Dispersed marker. A Colony Ally is distinct from
the original Tribe's Ally. The placement menus use the board after
the removal and its timing actions, with separate Gallic choices
and Available-pool limits for the Ally and Warbands.

The parent schema offered a Region string. The repaired schema offers
removal objects and the resolver rejects targets outside Britannia
before applying any placement. Existing authored plans can use the
same removal object and placement fields.

All 9,141 tests pass, including 11 new cases. Twenty paired bot games
match all previous final boards and winners without integrity errors.
Twenty mixed-seat games match across both hash seeds, with zero hard
findings and zero partial actions. The 100-game balance check passes
and matches every previous winner and card count.

**BE-08 closes. The original audit is 44/50 closed (88%), with 6 open.**

### 6 November Oppida 28 City choices

Under Card Reference 28 and §1.4.2, Oppida first offers eligible
Gallic Ally placements at Subdued Cities outside Roman Control. Its
second menu offers City Allies of factions with Available Citadels.
It uses the board after the first step and recalculates options at
each timing window, including when the executor reclaims a Citadel.
Both sides use City names and retain the authored plan format.

The parent schema offered the Aedui Tribe as a Citadel target and
omitted the City of Bibracte. The repaired menu submits Bibracte and
upgrades the chosen Ally. The City schemas for Sacking and shaded Remi
Influence now name the City type explicitly, matching their existing
owner menus. Oppida's bot defaults and resolver use the same legal
placement and upgrade options as the terminal.

All 9,130 tests pass, including eight new cases. Twenty paired bot
games match all previous final boards and winners without integrity
errors. Twenty mixed-seat games match across two hash seeds, with
zero hard findings and zero partial actions. The 100-game balance
check passes and matches every previous winner and card count.

**BE-08 advances. The remaining reported shape is shaded 57's Britannia
removal. The original audit remains 43/50 closed (86%), with 7 open.**

### 6 November shaded Surus 51

Under Card Reference 51 and §§5.1–5.1.3 and 5.4, the executor selects
zero to four Aedui Warbands by visibility in Treveri or one adjacent
Region. The terminal and assistant offer exact live cohorts. Each
source and its replacement resolve together. The Event skips a source
lost in the timing window and removes a surviving source even if its
German replacement is unavailable.

The parent probe offered neither a replacement nor a German Command.
The repaired probe replaces the selected Scouted Warband and Marches
the new German Warband, leaving the resident Germans in Treveri.
The assistant preserves the selected sources when saving at the German
Command. Legacy Region/count plans still delegate visibility and keep
their replacement timing windows. Bots decline shaded Surus if there
are no Aedui Warbands within scope. Older histories may pause for the
new choice or diverge under the corrected replacements.

All 9,122 tests pass, including 16 new cases. Twenty paired bot games
complete without integrity errors, retaining every winner and changing
one final board. Twenty mixed-seat games match across two hash seeds,
with zero hard findings and zero partial actions. The 100-game balance
check passes with a largest shift of five percentage points against
the reviewed baseline. One winner differs from the parent. In both
changed cases, the Belgae bot now declines an Event that previously
had no effect.

**BE-07 closes. The original audit is 43/50 closed (86%), with 7 open.**

### 6 November unshaded Catuvolcus 61

Under Card Reference 61 and §§5.1–5.1.3, the executor removes one or more
named Allied Tribes of a single faction from Nervii, then five Warbands
in any faction and visibility mix there, to the extent each step is
possible. The terminal and assistant show the choices separately.
The Warband offer uses the board after the Ally removals and intervening
timing window. The assistant preserves the accepted Ally choice when
saving and resuming at the Warband choice.

The parent probe offered neither choice. The repaired probe removes
the Nervii Ally and five Scouted Arverni Warbands, leaving the Eburones
Ally. The Aedui Non-player restricts both steps to player Arverni or
Belgae in the base game, or player Germans or Belgae in Ariovistus, and
declines if no such targets exist. Legacy Warband plans retain their
faction order and timing windows. Older histories may pause at the
new choices or diverge under the corrected removals.

All 9,106 tests pass, including 17 new cases. Twenty paired bot games
complete without integrity errors, with two changed final boards and
winners. Twenty mixed-seat games match across two hash seeds, with zero
hard findings and zero partial actions. The 100-game balance check
passes with a largest shift of 10 percentage points against the
reviewed baseline. The two changed winners relative to the parent
are Ariovistus seed 3 and The Gallic War seed 3. In both games the
Aedui bot now declines an Event it previously played without effect.

**BE-07 advances for unshaded 61. The original audit remains 42/50 closed
(84%), with 8 open.**

### 6 November unshaded Litaviccus 45

Under Card Reference 45 and §§5.1–5.1.3, the executor selects zero to
two Arverni Warbands in each of up to two Regions. The terminal and
assistant show Hidden, Revealed and Scouted sources on the live board.
Each replacement is a separate timed operation. If a selected cohort
is gone by that step, the operation leaves other cohorts alone. A
surviving source is removed even when no Aedui replacement can be
placed. The independent Arverni-to-Aedui Resource transfer applies
after the replacements, including when the executor selects zero.

The parent probe transferred Resources without offering a replacement
choice. The repaired probe replaces the selected Scouted Warband and
transfers the same Resources. Non-players apply the replacement
priorities in §§8.3.1 and 8.4.1 and use the seeded RNG for tied Regions.
Legacy Region/count plans retain their timing windows. Older histories
may pause at the new choice or diverge under the corrected replacements.

All 9,089 tests pass, including 15 new cases. Twenty paired bot games
complete without integrity errors, with six changed final boards and
three changed winners. Twenty mixed-seat games match across both hash
seeds, with zero hard findings and zero partial actions. The 100-game
balance check passes with a largest shift of 10 percentage points
against the reviewed baseline. Five winners differ from the parent.
Traces show four Arverni Warbands removed in each of those games,
with Aedui replacements limited by their Available pool. The previous
revision removed none. Tied Regions also consume seeded draws.

**BE-07 advances for unshaded 45. The original audit remains 42/50 closed
(84%), with 8 open.**

### 6 November unshaded Indutiomarus 60

Under Card Reference 60 and §§5.1–5.1.3, the executor chooses one Region,
Treveri or an adjacent Region, and removes six Belgic Warbands and/or
Allies, to the extent possible there. Each offered Ally names its Tribe
and excludes Citadels. Warbands retain exact Hidden, Revealed and Scouted
cohorts through selection. Both menus use the post-window board and the
assistant preserves the pending choice across save and resume.

The parent probe offered no choice and left both Allies and all
Warbands in place. The repaired probe removes the Senones Ally and five
Scouted Warbands while leaving the Mandubii Ally. Non-players check
for a target within scope and prioritize removing enemy Allies under
§§8.3.1 and 8.4.1. Legacy entry lists keep their order and timing windows.
Older histories may pause at the new choice or diverge under the
corrected removals.

All 9,074 tests pass, including 13 new cases. Twenty paired bot games
retain all winners and change two final boards, with no integrity errors.
Twenty mixed-seat games match across two hash seeds, with zero hard
findings and zero partial actions. The 100-game balance check passes
with a largest shift of 10 percentage points against the reviewed
baseline. Three winners change from the parent. In each case unshaded
Indutiomarus previously took no pieces and now removes Belgic Allies,
with Warbands also removed in two games.

**BE-07 advances for unshaded 60. The original audit remains 42/50 closed
(84%), with 8 open.**

### 6 November unshaded Aduatuca 58

Under Card Reference 58 and §§5.1–5.1.3, the executor selects one Region
with a Roman Fort and removes nine Belgic and/or Germanic Warbands, or
all eligible Warbands there if fewer are present. The terminal and
assistant offer exact faction and visibility choices from the board
after the timing window. Each faction's removals return to its own
Available pool. The assistant preserves the choice across save and resume.

The parent probe offered no choice and left all ten Warbands in place.
The repaired probe removes eight Hidden Belgic Warbands and one Scouted
Germanic Warband. Bots check for eligible Warbands at a Fort and use
§§8.3.1 and 8.4.1 for delegated removals. Existing faction/count plans
retain their entry order and timing windows. Older histories may pause
at the new choice or diverge under the corrected removals.

All 9,061 tests pass, including 12 new cases. Twenty paired bot games
retain every final board and winner with no integrity errors. Twenty mixed-seat games match across two hash seeds,
with zero hard findings and zero partial actions. The 100-game balance
check passes with every winner and card count matching the parent.

**BE-07 advances for unshaded 58. The original audit remains 42/50 closed
(84%), with 8 open.**

### 6 November shaded Alaudae 7

Under Card Reference 7 and §§5.1–5.1.3, the executor selects an on-map
Legion to send to the track and then an Auxilia to return to Available.
The threshold uses the track count at the start of resolution. A Legion
returned at seven can raise it to eight before the Auxilia choice. That
choice uses the current board after the intervening timing window.
The terminal shows exact cohorts, and an assistant session can save
after the Legion choice and resume with the Auxilia choice.

The parent probe removed a Hidden Auxilia and offered neither choice.
The repaired probe removes the selected Legion and Scouted Auxilia.
Bots skip an ineffective shaded Event. The German bot uses the printed
Germania and Settlement priority, then their neighboring Regions, with
an eligible piece in either tier required to execute. Region-only plans
delegate visibility, and older histories may pause for a new choice or
diverge under corrected delegated targeting.

All 9,049 tests pass, including 12 new cases. Twenty paired bot games
complete without integrity errors. Six final boards and four winners
change from the parent. Twenty mixed-seat games match across two hash
seeds, with zero hard findings and zero partial actions. The 100-game
balance check passes with a largest shift of 10 percentage points
against the reviewed baseline. Eleven winners differ from the parent.

**BE-07 advances for shaded 7. The original audit remains 42/50 closed
(84%), with 8 open.**

### 6 November shaded Sappers 24

Under Card Reference 24 and §§5.1–5.1.3, the executor selects one Region
with an Arverni Citadel and removes two Roman Legions and/or Auxilia,
or all eligible pieces there if fewer. The terminal and assistant offer
the current physical cohorts after the Event timing window. Legions go
to Fallen and Auxilia return to Available. The assistant preserves the
selection across save and resume.

The parent probe took a Hidden Auxilia when the executor wanted a
Scouted one. The repaired probe removes the selected Scouted Auxilia
and sends its accompanying Legion to Fallen. Delegated play applies
piece priorities and uses a seeded tie-break for equally ranked Regions.
Bots check for a Roman target in an Arverni Citadel Region before playing
the shaded Event. Legacy authored counts set the initial priorities
within their Region. Earlier histories may pause for the new choice or
diverge under corrected delegated targeting.

All 9,037 tests pass, including 13 new cases. Twenty paired bot games
complete without integrity errors, with three changed final boards and
one changed winner. Twenty mixed-seat games match across two hash seeds,
with zero hard findings and zero partial actions.

The 100-game balance check passes. The largest shift from the reviewed
baseline is 15 percentage points for Belgae in Reconquest of Gaul. Four
winners differ from the parent revision, in Pax Gallica? seeds 17 and 19
and Reconquest of Gaul seeds 1 and 17. Traces show the parent executing
shaded Sappers with no Roman pieces in any qualifying Region. The repair
lets the bot proceed to other actions in those positions.

**BE-07 advances for shaded 24. The original audit remains 42/50 closed
(84%), with 8 open.**

### 6 November shaded Marcus Antonius 6

Under Card Reference 6 and §§1.4.3 and 5.1, the executor chooses zero to
four Roman Auxilia outside Provincia and relocates them there with their
current visibility. The pieces stay on the map. The terminal and
assistant offer exact origin and visibility choices, and a selection
persists across save and resume. An intervening voluntary removal from a
selected group reduces the group. The eligibility clauses still apply
even when zero Auxilia move.

Non-players move as many Auxilia as possible under their printed
priorities, shared with the Numidians and Ambacti removal planners.
The German bot declines if neither its Germania or Settlement tier nor
the adjacent tier offers an eligible origin. Only Auxilia arriving from
other Regions count toward the movement allowance.

The parent live probe received no choice, and the legacy probe returned
Revealed Auxilia to play as Hidden. Both probes pass after the repair.
Legacy origin/count pairs retain their order. Older histories may pause
for the new choice or diverge under corrected movement.

All 9,024 tests pass, including 14 new cases. Twenty paired bot games
complete without integrity errors and retain all 20 winners. Four final
boards differ after four Auxilia move to Provincia in each game. The 20
mixed-seat games match across both hash seeds, with no hard findings and
one partial Rally due to an unaffordable placement.

The 100-game balance check passes with a maximum shift of 10 percentage
points. Six winners differ from the parent. Traces show the German bot
declining in Ariovistus seed 16 and four Auxilia moving in each of the
other five games.

**BE-07 and BE-08 advance for shaded 6. The original audit remains 42/50
closed (84%), with 8 open.**

### 6 November shaded Numidians 11

In both editions, the executor chooses exact Roman Auxilia by Region and
visibility on the current board after `11.piece_choice`. The Event removes
four, or every Auxilia on the map if fewer are present, under Card Reference
11, A Card Reference 11 and §§5.1–5.1.3. It returns those pieces to Available.
The terminal uses a live cohort menu in place of the original tuple input,
and the assistant preserves the choice across save, retry and replay.

The Non-players use their printed priorities. Belgae select in Belgica
first. Arverni leave Legions without Auxilia in as many Regions as
possible. Germans prioritize Germania and Settlement Regions, then their
neighbors, and decline the Event if neither tier has any Auxilia. A
German bot that qualifies carries out the remaining printed removals
after exhausting those tiers.

Both parent probes failed to offer the choice. The original text removed
Hidden pieces first and the revised text skipped removals without a plan.
The repair passes both probes, and revised defaults now carry out every
possible removal, including Scouted Auxilia. Legacy Region priorities still
work. Older histories may pause for the new choice or diverge under the
corrected revised default.

All 9,010 tests pass, including 18 new cases. Twenty paired bot games
complete without integrity errors. Fifteen match the parent's final state
and nineteen match its winner. Twenty mixed-seat games match across two
hash seeds, with zero hard findings or partial actions.

The original 100-game guardrail exceeds its 15-point band by 5 points
for Pax Gallica? Aedui and The Great Revolt Arverni. Each rate had been
at the band limit in the parent. The paired review found four changed
winners relative to that revision.

| Scenario and seed | Parent winner | Repaired winner | Numidians difference |
|---|---|---|---|
| Pax Gallica? 17 | Romans | Aedui | Belgae take all four Auxilia from Atrebates, the largest eligible Belgica group. |
| Reconquest of Gaul 3 | Aedui | Belgae | A seeded tie-break selects the same two remaining removals in Treveri and advances the random sequence. |
| The Great Revolt 16 | Aedui | Arverni | Seeded tie-breaks among three Belgica Regions retain the same removals and advance the random sequence. |
| The Gallic War 5 | Aedui | Arverni | Revised Numidians removes four Auxilia from Provincia. |

The reviewed refresh replaces 54 records, including 39 winners and 34
card counts against the prior baseline. It uses the same 100 scenario
and seed pairs and 15-point band. An independent run against the
candidate matches all 100 winners and card counts.

**BE-07 and BE-08 advance for shaded 11. The original audit remains 42/50
closed (84%), with 8 open.**

### 6 November shaded Cotuatus & Conconnetodumnus 31

The executor names one Roman Ally, one Aedui Ally, and a further Roman or
Aedui Ally, as available under Card Reference 31 and §§5.1–5.1.3. Each
choice uses the current board, excludes Citadels, and keeps the Tribe and
its disc in sync. The terminal and durable assistant can choose between
several Allies in one Region. A later pending choice survives save/load
and rejects invalid replies while preserving earlier accepted choices.

The parent probe reproduced automatic removal of different named Allies
from the same Region. The probe now receives the three live offers and
removes the selected Allies. Earlier histories may pause for the new
choice if they have no target recorded for the relevant slot.

All 8,992 tests pass, including 12 new cases. Twenty paired bot games
match the parent's gameplay and final-state hashes. Twenty mixed-seat
games match across both hash seeds, with zero hard findings and zero
partial actions. The 100-game balance check passes, and all winners
and card counts match the parent.

**BE-07 advances for shaded 31. The original audit remains 42/50 closed
(84%), with 8 open.**

### 6 November unshaded Bellovaci A69

Under A Card Reference A69 and §§5.1–5.1.3, the executor selects four
Belgic Warbands in Atrebates, or all present if fewer. Both player
interfaces expose Hidden, Revealed and Scouted cohorts after the
removal timing window. The named Belgic Ally is removed first. The
executor can choose a Roman or Aedui Ally and separately choose Roman
Auxilia or Aedui Warbands. An Aedui Non-player now chooses its own
pieces under §8.2.3. Delegation uses §8.4.1 visibility priorities.

Three parent probes reproduced the missing executor choice, omitted
Scouted removals and incorrect Aedui default beneficiary. All pass on the
repair. Older histories may pause for the new selection or diverge under
the corrected defaults.

All 8,980 tests pass, including 15 new cases. The 20 paired bot games
finish without integrity failures and keep all 20 winners. The two
expansion seed-1 games diverge after Aedui receives its own pieces. The
20 mixed-seat cases match across both hash seeds, with no hard findings
and the same partial action as the parent matrix. The 100-game balance
check passes within the existing band. Four winners change from the
parent, in Ariovistus seeds 5 and 17 and The Gallic War seeds 5 and 7.
All four games trace to the corrected Aedui placement.

**EXP-11 closes. The original bundle is 42/50 closed (84%), 8 open.**

### 6 November shaded Aduatuci A58

The executor selects one Belgica Region for the named Roman Ally disc
and three exact Auxilia, to the extent each type is present. The terminal
and assistant expose Hidden, Revealed and Scouted cohorts. An unavailable
replacement still removes its Roman source under §5.1.1. The granted
Ambush uses the post-replacement board, is confined to the chosen
Region and retains the executor's ordinary Ambush requirements under
§5.4. Partial delegated plays can now carry out an available replacement
or Ambush even when the Region lacks one of the printed target types.

Three parent probes reproduced the missing live choice, the Ambush
outside the selected Region, and omitted partial replacement of Scouted
Auxilia. All pass on the repair. Older histories may pause for the new
selection or diverge under the scoped Ambush.

All 8,965 tests pass, including 21 new cases. Twenty paired bot games
match the parent's gameplay and final state
hashes. Twenty mixed-seat cases match across both hash seeds, with no
hard findings and one partial action also present in the parent matrix.
The 100-game balance check passes within the existing band. Four winners
differ from the parent. In both expansion scenarios, seed 5 skips the
previously ineffective A58 and seed 14 replaces a Roman Ally in Atrebates
even though there are no Auxilia there.

**EXP-11 advances for A58. The original bundle is 41/50 closed (82%), 9 open.**

### 6 November shaded Publius Licinius Crassus A17

Under A Card Reference A17 and §§5.1 and 5.1.3, the executor selects one
playable Region and four Roman Auxilia there, or all present if fewer.
Both player interfaces expose the exact Hidden, Revealed and Scouted
cohorts. The selection is validated before removing pieces or setting
Roman ineligibility, which lasts through the next card even when there
are zero removals.

German bot instructions restrict its choices to Germania or Settlement
Regions, then their neighbors. With no target there, it declines the
Event. The Belgic bot still prioritizes Belgica. Ties on actual removals
use seeded choice. A legacy Region-only plan keeps its Region and can
now remove Scouted Auxilia. Older histories may encounter the new choice
or diverge under the corrected bot selection.

All 8,944 tests pass, including 18 new cases. Three probes against the
parent reproduced the missing player choice, the
failure to remove Scouted Auxilia on a Region-only plan, and the German
bot's acceptance of an out-of-scope target. All pass on this revision.
Twenty paired bot games match the parent's gameplay and final state hashes.
The 100-game balance check passes within its existing band and matches all
100 parent winners. Twenty mixed-seat cases match across both hash seeds
and match the parent's results apart from source metadata.

**EXP-11 advances for A17. The original bundle is 41/50 closed (82%), 9 open.**

### 5 November unshaded Usipetes & Tencteri A36

A Card Reference A36 and §§5.1 and 5.1.3 require the executing faction to
choose two German Settlements and eight German Warbands total from Morini,
Nervii and Treveri, to the extent each type is present. The terminal and
durable assistant offer exact Regions and visibility, including Scouted
Warbands, and validate the whole allocation before removing pieces.

On delegation, the engine uses seeded choices among tied Regions and the
own or enemy visibility order from §§8.3.1, 8.3.4 and 8.4.1. The bot
effectiveness check looks only at German Settlements and Warbands in the
three printed Regions. Older replays may encounter a new prompt or diverge
under the corrected delegated removals.

Three probes using the parent API reproduce the missed executor prompt,
Scouted Warbands surviving delegated play and a false effective result
with targets only outside the printed area. All pass on this repair.

All 8,926 tests pass, including 19 new cases. Twenty paired bot games match
the parent in gameplay and final state hashes. The 100-game historical
balance check passes within its existing 15-point band. Two winners differ
from the parent, both in expansion seed 14 after Aedui delegated A36.
Twenty mixed-seat cases match across hash seeds and match the parent's
results apart from source metadata, with no hard findings.

**EXP-11 advances for A36. The original bundle is 41/50 closed (82%), 9 open.**

### 5 November shaded Gallia Togata A5

Under A Card Reference A5 and §§5.1 and 5.1.3, the Romans select one Legion
to return to the track and two Auxilia to return to Available, to the extent
the map permits. The Roman-owned request offers exact visibility and allows
splits across Regions, including Cisalpina, in Ariovistus and the first half
of The Gallic War. The terminal and durable assistant use the shared live
request and validate the complete response before removing pieces.

The Senate's Adulation position suppresses the shaded effect, including
Non-player effectiveness evaluation (§8.1.1). When Rome delegates, the
engine completes the printed removals, using seeded random selection among
tied Regions and taking Scouted, Revealed and then Hidden Auxilia in the Region
(§§8.3.1, 8.3.4, 8.4.1). Roman legacy plans keep their selected Regions and
the default fills any remainder. Older histories may encounter a new Roman
prompt or differ when a delegated A5 now removes pieces.

Three probes using the parent API reproduce the missing Roman prompt, the
no-op delegated execution and the ineffective shaded Event being offered
in Adulation. All three pass on this repair.

All 8,907 tests pass, including 15 new cases. Twenty bot games match the
parent's gameplay and final state hashes. The 100-game historical balance
check passes within its existing 15-point band. Four winners differ from the
parent. In both expansion scenarios, seed 16 now executes the removals and
seed 17 now declines shaded A5 in Adulation. Twenty mixed-seat cases match
across hash seeds 0 and 987, with no hard findings and one planned Rally that
ran out of Resources after its first Region. Removing the obsolete inferred
A5 parameter menu changed the fuzzer's scratch key pool. Repeating the Rally
case with the parent key pool reproduced the parent result. The
[progress register](human-choice-progress.json) records the tested source.

**EXP-11 advances for A5. The original bundle is 41/50 closed (82%), 9 open.**

### 5 November Roman Event removals

Shaded Pompey (3) and base Gallia Togata (5) give Rome the choice of which
pieces to remove under Card Reference 3/5 and Chapter 5 §§5.1 and 5.1.3.
Pompey permits a split of two Legions between Regions when the track holds
four or fewer. Gallia Togata, outside Adulation, takes one Legion and two
exact Auxilia from any eligible Regions. Legions return to the track and
Auxilia to Available. The live choice requires each type's printed total
to the extent possible from the current map.

Rome receives the request even if another faction executes the Event. The
terminal and durable session validate the full plan before any selected
removals. Legacy Region-priority plans remain available on raw deferral.
Roman executors can still supply legacy Region parameters. Older sessions
may encounter a new pending Roman choice on replay.

**BE-06 closed at 41/50 (82%), with 9 open.**
The other physical selections in BE-07 and the expansion A5 selection
tracked by EXP-11 were still open at that checkpoint.

All 8,892 tests pass, including 34 new cases. Two behavior probes using the
parent API reproduce the missing Roman
request and concentrated removals on `6f91feb`; both pass on the repair.
Ten audited bot games (seeds 1–2 in each scenario) match the parent in
gameplay and final state hashes. Ten mixed-seat cases produce identical
JSON at hash seeds 0 and 987, with 314 human turns, zero hard findings and
zero partials. The 100-game historical balance check passes within its
existing 15-percentage-point band. See the [progress register](human-choice-progress.json)
for the tested source digest.

### 5 November Lucterius/Hostages quantities — BE-06/07/08 advanced

The [piece-choice repair](reviews/base-piece-choices-2026-11-05.md) adds live
executor choices for unshaded numeric 19/22. Lucterius allows zero-to-five
Auxilia or zero-to-six exact Arverni Warbands nearby; Hostages allows zero-to-four
exact physical pieces and mixed removal-only/replacement actions. Hidden,
Revealed and Scouted identities are preserved. Gallic Hostages replacements
of Roman Auxilia now correctly place their own Warbands. Unavailable
replacements still remove the original pieces under §5.1.1.

Both frontends support inspection, strict pending validation, board/RNG
rollback, save/load and deterministic replay. Choices use the actual Event-step
board after its timing window; previews consume no live input or RNG. Legacy
explicit plans and raw delegation remain supported.

**At that checkpoint, the original bundle was 40/50 closed (80%), 10 open.** BE-06 still included
mandatory Roman removal allocations on numeric 3/5. BE-07 physical-choice and
BE-08 schema findings retain other cards. Two unadopted source questions,
thirteen provisional rulings and 34 separate unverified inventory rows retain
their dispositions. No new source ruling was needed.

**8,858 tests pass**, including 89 new cases; 294 focused tests pass. Ten paired
NPC records/final hashes match the parent. Mixed-seat JSON matches across hash
seeds with zero hard findings or partials. The unchanged 100-game balance guard
passes. The report records the exact source, protected inputs, evidence and
cross-revision replay limit.

### 5 November mandatory queue capabilities — PR-13 adopted, BE-09 closed

The [mandatory queue repair](reviews/capability-queue-2026-11-05.md) implements
owner-adopted provisional PR-13, subject to official correction. Card 13
unshaded and Card 59 shaded offer use here or reservation while later queue
candidates remain. The final candidate, if it becomes a Battle, offers only
use here. A reservation can expire without a later actual eligible Battle;
combat never rewinds. Actual Retreat arrivals get fresh live windows.

Both frontends preserve pending choices, earlier reservation, rollback,
save/resume and replay. PR-11's isolated forecast branches offered human
responses. Default use retains first-applicable priorities, including skipping
attacking Horse where active Abatis prevents doubling.

**Original bundle is 40/50 closed (80%), 10 open.** This closes BE-09 after
the preceding Ballistae, Slingers and Horse repairs. Two unadopted source
questions, thirteen provisional rulings, 34 unverified inventory rows and
separate mechanics leads retain their own dispositions.

**8,769 tests pass**, including 53 new cases, with 279 focused tests passing.
Ten standard NPC records/final hashes match the parent, mixed-seat results
agree across hash seeds with zero hard findings or partials, and the historical
100-game balance guard passes its unchanged band. The report records the
frozen source, protected inputs, evidence and cross-revision replay limit.

### 5 November optional Horse queue — BE-09 advanced, mandatory timing unresolved

The [queue repair](reviews/horse-queue-2026-11-05.md) offers Romans use here,
reserve or decline for optional unshaded Horse as actual Battles become
selected. Reservation consumes no use; activation/decline ends the Command's
windows. Retreat arrivals can create a later window, and a reserved effect
can expire unused. Both frontends retain pending and earlier accepted choices
across save/load/replay. PR-11 forecasts branch the optional human responses.

**Original bundle remains 39/50 closed (78%), 11 open.** Mandatory Card 13 and
59-shaded queue choices remain open as
[Q-CAPABILITY-QUEUE-TIMING](../QUESTIONS.md#q-capability-queue-timing--reserving-mandatory-one-region-capabilities-5-november-2026).
The supplied text does not settle reservation when no later Battle occurs.
The recommendation is recorded, not adopted. There are now three open source
questions, twelve adopted provisional rulings and 34 unverified inventory rows,
separate from the original bundle and other mechanics leads.

**8,716 tests pass**, including 28 new cases, with 226 focused tests passing.
Ten standard NPC records/final hashes match the parent, mixed-seat results
agree across hash seeds with zero hard findings or partials, and the historical
100-game balance guard passes its unchanged band. The report records the
frozen source, protected inputs, evidence and cross-revision replay limit.

### 5 November Horse Region — BE-09 advanced, still open

The [Horse repair](reviews/horse-choice-2026-11-05.md) offers Card 59's owner
one ordinary/free Battle Region for attack or defense, with Roman unshaded
decline. Exact combatants, current protection and live choices are validated.
Active Abatis now blocks shaded attacking doubling in both loss calculators.
Each Command isolates and clears its flags, including interrupted and nested
Battles. Non-player/default selection follows first-applicable selected order.
Both frontends retain accepted Regions through later casualties and replay.

**Original bundle remains 39/50 closed (78%), 11 open.** BE-09 now retains
the private prospective queue's automatic Card 13/59 choices. Separate
mechanics leads, two source questions, twelve provisional rulings and 34
unverified inventory rows retain their dispositions.

**8,688 tests pass**, including 64 new cases, with 364 focused tests passing.
Nine of ten NPC records/final hashes match the parent; the changed game is
traced to corrected Horse selection and reproduced by restoring the old policy.
Mixed-seat results agree across hash seeds with zero hard findings or partials, and the historical
100-game balance guard passes its unchanged band. The report records the
frozen source, protected inputs, evidence and cross-revision replay limit.

### 5 November Slingers Region — BE-09 advanced, still open

The [Slingers repair](reviews/slingers-choice-2026-11-05.md) offers Romans one
Region in an enemy ordinary/free Battle plan, including third-party pre-fire.
It permits legal zero-Loss selections, validates live combatants and preserves
accepted Regions across later casualties, rollback/save/resume and replay.
The printed Card 13/59 Tip now supplies one initial Loss per Auxilia when both
capabilities are unshaded. The NPC default follows §8.3.3's first applicable
Region rather than the old most-Auxilia heuristic.

**Original bundle remains 39/50 closed (78%), 11 open.** BE-09 retains the
private prospective queue's Roman Slingers choice and Card 59's own Region
choices. Separate mechanics leads, two source questions, twelve provisional
rulings and 34 unverified inventory rows retain their dispositions.

**8,624 tests pass**, including 44 new cases, with 235 focused tests passing.
Ten standard NPC records/final hashes match the parent, mixed-seat results
agree across hash seeds with zero hard findings or partials, and the historical
100-game balance guard passes its unchanged band. The report records the
frozen source, protected inputs, evidence and cross-revision replay limit.

### 5 November Ballistae choice — BE-09 advanced, still open

The [Ballistae repair](reviews/ballistae-choice-2026-11-05.md) asks Card 10
shaded's owner whether to remove a surviving defending Fort or Citadel after
Ambush. Both human interfaces offer the live physical target or decline,
including after Event-granted Ambushes. Named Citadel allegiance and physical
ownership remain synchronized. Provincia's permanent Fort is excluded.
Later-Region pending choices retain accepted earlier responses across saving,
loading and replay.

**Original bundle remains 39/50 closed (78%), 11 open.** BE-09 still tracks
Balearic Slingers (13 unshaded) and Germanic Horse (59, both sides) Region
choices. Separate mechanics leads, two source questions, twelve provisional
rulings and 34 unverified inventory rows retain their dispositions.

**8,580 tests pass**, including 47 new cases, with 349 focused tests passing.
Ten standard NPC records/final hashes match the parent, mixed-seat results
agree across hash seeds with zero hard findings or partials, and the historical
100-game balance guard passes its unchanged band. The report records the
frozen source, protected inputs, evidence and cross-revision replay limit.

### 4 November printed setup options — WS-F08 closed

The [setup-option repair](reviews/setup-options-2026-11-04.md) adds Sudden
Frost, Even Initiative and the shorter Great Revolt to the setup API, terminal
flags and assistant initialization. Exact deck composition, pre-action Winter
switches, scenario restrictions and saved choices are validated. The Gallic War
retains its explicit Interlude deck replacement. Standard setups retain their
previous card order, RNG consumption and board hashes.

**Original bundle is now 39/50 closed (78%), 11 open.** Shared-player ownership,
ordinary Battle Retreat and other recorded findings remain open. Separate
mechanics leads, two source questions, twelve provisional rulings and 34
unverified inventory rows retain their dispositions.

**8,533 tests pass**, including 68 new cases, with 545 focused tests passing.
All 34 optional-setup games complete and audit cleanly. Ten standard NPC
records/final hashes match the parent, mixed-seat results agree across hash
seeds, and the historical 100-game balance guard passes its unchanged band.
The report records source identity, protected inputs and raw evidence.

### 4 November Rampage victims — BATTLE-RAMPAGE-VICTIM closed

The [Rampage victim repair](reviews/rampage-victims-2026-11-04.md) gives the target exact
Warband/Auxilia/Legion selection and a remove-or-Retreat choice for each piece.
All Retreating pieces use one legal destination. Complete validation precedes
Belgic flips and target mutations, and the low-level operation restores on
failure. Host consent is collected once. Forced expansion Arverni removals
retain their source priority. Terminal and durable sessions support physical
selection, earlier accepted Regions, save/resume and deterministic replay.

**At that checkpoint, 38/50 were closed (76%), 12 open.** Ordinary Battle Retreat
survivor choices remain open. Separate Circumvallation mechanics, the NPC
Intimidate targeting lead, two source questions, twelve provisional rulings
and 34 unverified inventory rows retain their recorded dispositions.

**8,465 tests pass**, including 42 new cases, with 469 focused tests passing.
Ten audited NPC records/final hashes match the parent. Mixed-seat runs agree
across hash seeds with zero hard findings or partials. The 100-game historical
balance guard passes its existing band. The report records source provenance,
raw evidence, protected inputs and the older terminal replay compatibility limit.

### 4 November physical Battle casualties — BATTLE-LOSS-IDENTITY closed

The [Battle casualty repair](reviews/battle-loss-identity-2026-11-04.md) offers exact ordinary
Warband/Auxilia visibility and named Allied Tribes within the current mandatory
loss tier. A City represented by a Citadel is excluded from the Ally-disc
choices. Cooperating Allied Tribes retain their physical owners and names.
Both frontends use the identities offered for that specific Loss, rebuilding
choices after each removal or saving roll. Recorded old generic prompts can
finish on their verified original board, including accepted earlier casualties
and saved second-loss prompts. New prompts require their actual offered entries.

**At that checkpoint, 37/50 were closed (74%), 13 open.** Full Retreat and
Rampage victim choices remain open. The separate Circumvallation mechanics,
NPC Intimidate targeting lead, two source questions, twelve provisional rulings
and 34 unverified inventory rows retain their recorded dispositions.

**8,423 tests pass**, including 50 new cases, and 519 focused tests pass.
Ten audited NPC records/final hashes match the parent. Mixed-seat replays agree
across hash seeds with zero hard findings or partials. The 100-game historical
balance guard passes its existing band. Source identity, compatibility checks
and raw evidence are recorded in the report.

### 4 November Roman Interlude choices — WS-F02 closed

The [Roman Interlude repair](reviews/interlude-roman-choices-2026-11-04.md) asks the Roman player
whether to conduct the expedition, which three Legions to reserve for Harvest,
which additional Legions and exact Auxilia cohorts to send to Britannia, and
which optional Dispersed marker to preserve through Spring. The full allocation
is checked before movement. Both human frontends retain board inspection,
pending decisions and accepted earlier choices across save/resume/replay.
The direct Winter API also restores its counter and board on interruption.

**At that checkpoint, 36/50 were closed (72%), 14 open.** WS-F01 still tracks
force reductions and Cisalpina relocations. Separate Circumvallation mechanics,
full Rampage victim choices, the NPC Intimidate targeting lead, two source
questions, twelve provisional rulings and 34 unverified inventory rows retain
their recorded dispositions.

**8,373 tests pass**, including 53 new cases, with 330 focused tests passing.
Ten audited NPC gameplay records and final hashes match the parent, including
an Interlude. Mixed-seat replays agree across hash seeds with zero hard findings
or partials. The 100-game historical balance check passes its existing band.
The report contains source identity, compatibility limits and archived evidence.

### 4 November Scout allocation — CMD-SCOUT-ALLOCATION closed

The [Scout repair](reviews/scout-allocations-2026-11-04.md) shares one Auxilia's
two-Warband capacity across exact factions and visibility cohorts. Terminal
and durable plans validate the full group and physical owners against the live
board. Invalid grouped plans restore prior moves and flips. Diviciacus consent
sees every selected faction, and later owner choices survive save/resume/replay.
Card 12 and movement restrictions remain in force; legacy bot rows still work.

**At that checkpoint, 35/50 were closed (70%), 15 open.** Counts measure findings,
not effort or full rules compliance. Separate CV-PERSISTENCE, full Rampage
victim choices, NPC Intimidate targeting, two source questions, twelve
provisional rulings and 34 unverified inventory rows retain their dispositions.

**8,320 tests pass**, including 60 new cases; 337 targeted tests pass. Ten
native-bot gameplay records/final hashes match parent. Forty mixed executions
agree across hash seeds with zero hard findings or partials. The 100-game
balance check passes its unchanged band. See the report
for frozen source provenance and evidence bounds.


### 4 November Drought casualties — BE-05 closed

The [Drought batch](reviews/drought-losses-2026-11-04.md) asks each eligible
physical owner for one exact loss in every Devastated Region. Visibility,
Tribes, Citadels, Leaders, Forts, Settlements and Legions are represented;
German Warbands-before-Allies and permanent Provincia Fort protection apply.
Default losses now preserve Roman Legions and Hidden pieces according to
own-piece priorities. Terminal and durable choices support later-owner/Region
rollback/save/resume and exact replay. Unsafe executor override maps are rejected.
Drought's BE-08 menu shape is repaired; that grouped finding remains open.

**At that checkpoint: 34/50 closed (68%), 16 open.** Counts measure findings,
not effort or full rules compliance. Separate CV-PERSISTENCE, full Rampage
victim choices, NPC Intimidate targeting, two source questions, twelve
provisional rulings and 34 unverified inventory rows retain their dispositions.

**8,260 tests pass**, including 69 new cases; 284 targeted tests pass. All ten
native-bot games audit cleanly: nine match parent, and the one changed game's
first divergence is traced to the corrected Drought casualty. Forty mixed
executions agree across hash seeds with zero hard findings or partials. The
100-game historical balance check passes its unchanged baseline and band.
See the report for frozen source provenance and evidence bounds.


### 4 November expansion optional quantities — EXP-08 closed

The [three-Event batch](reviews/expansion-up-to-2026-11-04.md) restores zero-to-
maximum choices on A40 shaded, A51 unshaded and A60 unshaded. The executor
selects Alpine Tribes Regions, exact Bibrax visibility cohorts and the Remi
Auxilia/Resources tradeoff. Live requests follow compulsory placements and
support terminal inspection, pending rollback/save/resume and identical replay.
Typed plans can pre-author the same choices. A51 now includes Scouted Warbands;
A60 refunds reflect actual unplaced pieces, including an unavailable Ally.

**At that checkpoint: 33/50 closed (66%), 17 open.** Counts measure findings,
not effort or full rules compliance. Separate CV-PERSISTENCE, full Rampage
victim choices, NPC Intimidate targeting, two source questions, twelve
provisional rulings and 34 unverified inventory rows retain their dispositions.

**8,191 tests pass**, including 87 new cases; 292 targeted tests pass. Ten
native-bot gameplay records/final hashes match parent. Forty mixed executions
agree across hash seeds with zero hard findings or partials. The 100-game
historical balance check passes its unchanged baseline and 15-point band.
See the report for the frozen source digest and evidence bounds.


### 4 November Quarters visibility — WS-F05 closed

The [Quarters repair](reviews/quarters-visibility-2026-11-04.md) lets owners
select exact Hidden/Revealed/Scouted Warband and Auxilia cohorts for adjacent
relocations and Roman Provincia moves. Original adjacent cohorts are reserved
before applying any arrivals. Provincia continuations check both offered totals
and live visibility capacity; defaults trim unavailable selected cohorts rather
than substitute another visibility. Terminal and durable interfaces support the
same choices, with pending/save/resume and exact replay. Legacy four-entry plans
retain their Hidden/Revealed/Scouted fallback.

**At that checkpoint: 32/50 closed (64%), 18 open.** Counts measure findings,
not effort or full rules compliance. Separate CV-PERSISTENCE, full Rampage
victim choices, NPC Intimidate targeting, two source questions, twelve
provisional rulings and 34 unverified inventory rows retain their dispositions.

**8,104 tests pass**, including 56 new cases; 129 targeted tests pass. Ten
native-bot gameplay records/final hashes match parent. Forty mixed executions
agree across hash seeds with zero hard findings or partials. See the report
for the frozen source digest and evidence bounds.


### 4 November Devastate casualties — CMD-DEVASTATE-LOSSES closed

The [casualty repair](reviews/devastate-losses-2026-11-04.md) asks each affected
owner for exact physical losses, including visibility and Roman Legion choices.
All owner plans are validated before mutation; malformed/short/overlarge
supplied maps no longer silently truncate or omit losses. Non-player/default
own-piece removal now follows §8.4.1's Scouted/Revealed/Hidden priority. Legions
still go to Fallen. Terminal, preview isolation and durable later-Region
rollback/save/resume/replay are covered. Ariovistus still excludes Devastate.

**At that checkpoint: 31/50 closed (62%), 19 open.** Counts measure findings,
not effort or full rules compliance. Separate CV-PERSISTENCE, full Rampage
victim choices, NPC Intimidate targeting, two source questions, twelve
provisional rulings and 34 unverified inventory rows retain their dispositions.

**8,048 tests pass**, including 50 new cases; 283 targeted tests pass. Ten
native-bot gameplay records/final hashes match parent. Forty mixed executions
agree across hash seeds with zero hard findings or partials. See the report
for the frozen source digest and evidence bounds.


### 4 November Gallic Shouts peek — BE-10 closed

The [peek repair](reviews/gallic-shouts-peek-2026-11-04.md) supplies the actual
next two facedown cards in the Roman Card 35 unshaded request, with active
edition/scenario text and initiative metadata. The face-up next card is excluded.
The terminal presents the briefing before a free Limited Command or Become
Eligible. Only the Roman beneficiary receives that private presentation;
public Event receipts/modifiers and board snapshots do not acquire hidden data.
Deck order and RNG are untouched. Durable missing/invalid input remains pending
across rollback/save/resume; Council's private rendering is preserved.

**At that checkpoint: 30/50 closed (60%), 20 open.** Counts measure findings,
not effort or full rules compliance. Separate CV-PERSISTENCE, full Rampage
victim choices, NPC Intimidate targeting, two source questions, twelve
provisional rulings and 34 unverified inventory rows retain their dispositions.

**7,998 tests pass**, including 35 new cases; 120 targeted tests pass. Ten
native-bot gameplay records/final hashes match parent. Forty mixed executions
agree across hash seeds with zero hard findings or partials. See the report
for the frozen source digest and evidence bounds.


### 4 November Harvest Legions — WS-F03 closed

The [Harvest repair](reviews/harvest-legions-2026-11-04.md) lets Romans allocate
all actual Winter Track Legions among any Belgica Regions, with a terminal
prompt and durable save/resume. Placement uses the piece helper rather than
changing map counters directly. Invalid/partial/outside allocations remain
pending. Legacy concentration and its result shape remain supported.
A related source correction releases a positive expedition reserve at the first
post-Interlude Harvest; the old path recorded only the empty-box exception and
never released nonempty reserves. WS-F02's expedition/marker choices remain open.

**At that checkpoint: 29/50 closed (58%), 21 open.** Counts measure findings,
not effort or full rules compliance. Separate CV-PERSISTENCE, full Rampage
victim choices, NPC Intimidate targeting, two source questions, twelve
provisional rulings and 34 unverified inventory rows retain their dispositions.

**7,963 tests pass**, including 46 new cases; 250 targeted tests pass. Ten
native-bot gameplay records/final hashes match parent. Forty mixed executions
agree across hash seeds with zero hard findings or partials. The 100-game
balance check passes against the unchanged historical baseline and 15-point
band. See the report for the frozen source digest and evidence bounds.


### 4 November Besiege physical targets — BATTLE-BESIEGE-CHOICE closed

The [Besiege repair](reviews/besiege-choice-2026-11-04.md) asks the Roman for
an exact Citadel/Allied Tribe or German Settlement, or an explicit decline,
at the pre-Loss step of each selected Battle. Terminal and durable sessions
support the choice; invalid or absent responses remain pending across rollback
and save/resume. Only the chosen Tribe's allegiance clears. Zero Losses,
Retreat declarations, Citadel halving and Ballistae retain their printed behavior.
Native NPC defaults remain supported.

**At that checkpoint: 28/50 closed (56%), 22 open.** Counts measure findings,
not effort or full rules compliance. Separate CV-PERSISTENCE, full Rampage
victim choices, NPC Intimidate targeting, two source questions, twelve
provisional rulings and 34 unverified inventory rows retain their dispositions.

**7,917 tests pass**, including 37 new cases; 398 targeted tests pass. Ten
native-bot gameplay records/final hashes match parent. Forty mixed executions
agree across hash seeds with zero hard findings or partials. See the report
for the frozen source digest and evidence bounds.


### 4 November March hide in place — MARCH-HIDE-IN-PLACE closed

The [March repair](reviews/march-stay-2026-11-04.md) accepts explicit empty
routes and offers a terminal stay choice. An affordable selected origin pays
its March cost and runs whole-origin hiding/Scouted handling without moving.
Results distinguish `stayed_origins` from actual `marches`; missing routes
keep legacy destination planning. Frost, Limited Commands and Event-required
destinations retain their constraints. Staying in Britannia does not cross it.
Accepted ordinary and free-Event choices survive durable save/resume.

**At that checkpoint: 27/50 closed (54%), 23 open.** Counts measure findings,
not effort or full rules compliance. Separate CV-PERSISTENCE, full Rampage
victim choices, NPC Intimidate targeting, two source questions, twelve
provisional rulings and 34 unverified inventory rows retain their dispositions.

**7,880 tests pass**, including 40 new cases; 203 targeted tests pass. Ten
native-bot gameplay records/final hashes match parent. Forty mixed executions
agree across hash seeds with zero hard findings or partials. See the report
for the frozen source digest and evidence bounds.


### 4 November player Build ordering — CMD-BUILD-ORDER closed

The [Build repair](reviews/build-order-2026-11-04.md) adds exact `region_order`
to player plans and both collectors. Each Region resolves its optional Fort
then one Tribe operation before the next Region. Category timing indices remain
stable. Legacy plans and the source-required §8.8.1 NP passes remain supported.
Malformed orders are rejected before an accompanying Command; pending turn and
Event SA responses survive rollback and save/resume.

**At that checkpoint: 26/50 closed (52%), 24 open.** This counts findings,
not effort or complete rules compliance. CV-PERSISTENCE, full Rampage victim
choices, NPC Intimidate targeting, two source questions, twelve provisional
rulings and 34 unverified inventory rows retain their separate dispositions.

**7,840 tests pass**, including 32 new cases; 121 targeted tests pass. Ten
native-bot gameplay records/final hashes match parent. Forty mixed executions
agree across hash seeds with zero hard findings or partials. See the report
for the frozen source digest and evidence bounds.


### 4 November ordinary Seize Tribes — CMD-SEIZE-TRIBES closed

The [Tribe repair](reviews/seize-tribes-2026-11-04.md) extends exact
`disperse_tribes` maps to ordinary Seize, including Forage-only, ordered Regions
and interrupted Command portions. Both menus offer every legal Tribe even
with one marker left, reserve the shared marker budget and consume no live
Rally/Harassment dice. Missing/malformed named choices are rejected; accepted
plans survive Rally pauses and save/resume. Legacy NPC selection is preserved.
The synthetic human-policy builder and Arduenna witness use the same contract.
**7,808 tests pass**, including 54 new cases; 312 targeted tests pass. Ten
bot gameplay records/final hashes match the parent. Forty mixed executions
agree across hash seeds with zero hard findings and zero partials.

**At that checkpoint: 25/50 closed (50%), 25 open.** This measures original
finding counts, not equal effort or complete rules compliance. The separate
Circumvallation mechanics, full Rampage victim choices and NPC Intimidate
lead remain open.


### 4 November Rampage quantity — CMD-RAMPAGE-COUNT closed

The [quantity repair](reviews/rampage-quantity-2026-11-04.md) carries a human's
exact positive `count` through both Rampage menus and execution. It rejects
invalid/overlarge counts before victim reactions, preserves unselected Hidden
Warbands, and supports accepted actor/victim save/resume. The artificial NPC
two-Warband cap is also corrected: §8.5.1 uses all able Warbands while leaving
the last enemy piece before Battle. Repeated Regions are rejected per §4.1.
**7,754 tests pass**, including 48 new cases; 348 targeted tests pass. Ten
audited bot games retain their winners, with one traced final-state change.
The unchanged 100-game/15-point balance guard passes; mixed runs have zero
hard findings and one traced generated Rally partial per ten-case matrix.

**Original bundle is now 24/50 closed (48%), 26 open.** Full victim piece
selection and per-piece remove/Retreat remain BATTLE-RAMPAGE-VICTIM. The separate
Circumvallation mechanics and NPC Intimidate targeting lead remain open.


### 4 November Intimidate Tribe identity — CMD-INTIMIDATE-TRIBE closed

The [Tribe repair](reviews/intimidate-tribes-2026-11-04.md) lets humans choose
the exact Allied Tribe disc for ordinary, intrinsic Raid and A45 Intimidate.
The complete Region's targets are reserved and validated before any Reveal
or marker. Named human choices cannot silently become an NPC default.
Terminal selection, board inspection, pending-input rollback and save/resume
are covered; legacy unnamed NPC/default selections remain supported.

**Original bundle is now 23/50 closed (46%), 27 open.** Circumvallation's
marked-group tracking, movement restrictions, virtual Fort and exact Interlude
removal remain open; this batch does not claim those mechanics repaired.
**7,706 tests pass**, including 44 new cases; 229 targeted tests pass.
Against the parent, 23 behavior witnesses fail and two controls pass. Ten bot
gameplay records/final hashes match, and 40 mixed executions have zero hard
findings plus one traced generated Rally partial per ten-case matrix.
The separate pre-Battle NPC Intimidate targeting lead is also unchanged.


### 4 November Circumvallation no-Romans cleanup — partial CV-PERSISTENCE

The [cleanup repair](reviews/circumvallation-no-romans-2026-11-04.md) removes
the marker after a successful piece operation leaves no physical Romans in
its Region, including March departures and Battle casualties. Any remaining
Roman piece keeps it, including an Ally, Fort or Leader. Other markers are
preserved. This applies to both marker representations and all five scenarios.

Marked-group tracking, movement restrictions, virtual Fort protection,
attack/elimination boundaries, and exact marked-only Interlude cleanup remain
open. Boolean-marker saves still do not identify their original marked group.
**Original bundle remains 22/50 closed (44%), 28 open.** CV-PERSISTENCE is a
separate high-priority finding and remains open after this partial repair.
**7,662 tests pass**, including 39 new cases; 153 targeted tests pass.
Against the parent, 36 new witnesses fail and three controls pass. Ten bot
games complete and retain the same winners; one traced Interlude trajectory
changes because a stale marker now expires.


### 4 November Circumvallation choices — BE-01 closed; persistent effects open

The [choice repair](reviews/circumvallation-2026-11-04.md) restores Roman
whole-benefit decline and exact adjacent groups/destination on numeric4,
whoever executes the Event. A new marker follows the accepted March and
requires a remaining enemy Citadel and Roman presence. Formation/cooperation,
terminal inspection and durable save/resume are covered. **7,623 tests pass**,
including 29 added cases; 23 behavior witnesses fail against the parent and
a native control passes. Ten bot gameplay records/final hashes match; mixed
runs have zero hard findings and one traced generated Resource-gift partial.

**22/50 original findings are closed (44%); 28 remain open.** The original
human Event-March/guidance finding BE-01 is complete. This counts original
findings, not complete card4 rules compliance. Executable probes separately
confirm **CV-PERSISTENCE**, a new high-priority open follow-up: marked pieces
can move, the virtual Fort is absent, marker cleanup is missing, and Interlude
removes unmarked Romans. See the [persistent-effect report](reviews/circumvallation-persistence-followup-2026-11-04.md).
Two source questions, twelve provisional rulings and 34 unverified inventory
rows remain separate as well.

### 4 November Germanic Chieftains — partial BE-01 repair

The [Germanic Chieftains report](reviews/germanic-chieftains-2026-11-04.md)
restores numeric17 unshaded's Roman-owned German groups and single Ambush,
regardless of which faction executes the Event. Up to three original moving
groups use exact quantities, ordinary origin visibility and the shared
physical-cohort safeguards. Only the chosen Region Ambushes. Roman bot
instructions govern explicit delegation; native Roman NPCs and raw legacy
deferral remain supported. Shaded Germans Phase behavior is unchanged.
Terminal inspection, pending-response rollback and save/resume are covered.
**7,594 tests pass**, including 27 added regressions; 21 behavioral witnesses
fail against the parent and its native Roman-bot control passes. Ten bot
gameplay records/final hashes match, and 40 mixed executions including
replay/hash repeats have zero hard findings.

**21/50 original findings remain closed (42%); 29 remain open.** BE-01
now remains open for card4. Two source questions, twelve provisional rulings
and 34 unverified inventory rows remain separate.

### 4 November German Allegiances — partial BE-01 repair

The [German guidance report](reviews/german-guidance-2026-11-04.md) covers
numeric65's human executor choices: up to two original German origins,
quantities/routes, then Ambush order and defenders in every able Region.
Original physical cohorts prevent arrivals from moving twice or receiving
another origin flip, including hide-only origins. Hidden superiority and
Fort protection remain in force; defensive cooperation is checked before
combat and a zero-Loss Ambush is not excluded merely by the NP heuristic.
Terminal inspection, durable rollback and save/resume are covered.
**7,567 tests pass**, including 28 added regressions; 20 behavior witnesses
fail against the parent. Ten bot gameplay records/final hashes match, and
40 mixed executions including replay/hash repeats have zero hard findings.
Native NPC planners are unchanged; this is not a new audit of their priorities.

**21/50 original findings remain closed (42%); 29 remain open.** BE-01
remains open for 4/17. Two source questions, twelve provisional rulings and
34 unverified inventory rows remain separate.

### 4 November Aduatuca — partial BE-01 repair

The [Aduatuca report](reviews/aduatuca-2026-11-04.md) covers numeric58
shaded's executor-owned Fort destination, German origins and exact quantities.
Origins undergo ordinary visibility changes, including zero-movement hiding;
resident Germans join the mandatory Roman Ambush with its printed Fort
exception. Roman defender choices remain with Romans. Terminal inspection,
durable rejection, rollback and save/resume are covered. **7,539 tests pass**;
13 behavioral witnesses fail against the parent. Ten bot records/final hashes
match, and 40 mixed executions including replay/hash repeats have zero hard
findings. Old transcripts
can encounter a new choice; cross-revision exact replay is not promised.

**21/50 original findings remain closed (42%); 29 remain open.** BE-01
remains open for 4/17/65. Two source questions, twelve provisional rulings
and 34 unverified inventory rows remain separate.

### 3 November Mons Cevenna — partial BE-01 repair

The [Mons Cevenna report](reviews/mons-cevenna-2026-11-03.md) covers
numeric 9's human first-March origin, exact moving force and adjacent
destination. Its follow-on Command and optional SA remain in/from that
Region, with separate cooperation consent. Legacy initial routes now obey
the printed geography, and unavailable movement cannot broaden the grant.
Terminal board inspection, durable rejection/rollback and save/resume are
covered. **7,517 tests pass**; 19 behavioral witnesses fail against the
parent. Ten bot records match the parent, and 40 mixed executions including
replay/hash repeats show zero hard findings. New decisions can change replay
requirements across revisions.

**21/50 original findings remain closed (42%); 29 remain open.** BE-01
now remains open for 4/17/58/65. Two source questions, twelve provisional
rulings and 34 unverified inventory rows remain separately tracked.

### 3 November planning-board inspection — FE-01 closed

The [inspection repair](reviews/planning-board-inspection-2026-11-03.md)
binds Command and cooperation inspection to the actual detached planning
board. After SA-first Build, `b`/`board` at the March origin menu now shows
the new Fort and spent Resources. Nested menu scopes restore the prior
inspection hook on exit; planning does not alter the live board or RNG.

The final source passes **7,489 tests**, including four regressions that
fail against the parent; the targeted frontend suite passes 32 tests.

**21/50 original findings are closed (42%); 29 remain open.** BE-01's
remaining Event March grants are still open. Historical results below retain
the counts and measurements of their own revisions.

### 3 November Camulogenus — partial BE-01 repair

The [Camulogenus report](reviews/camulogenus-2026-11-03.md) covers Roman
whole-benefit acceptance and exact March planning on numeric 70: multiple
original groups, one named destination, four Legions total, moving-only
visibility and separate cooperation. It also repairs default planners skipping
a possible resident Battle after the moving group is lost or removed.

The final source passes **7,485 tests** and 120 audited bot games,
with all 120 recorded results unchanged against a fresh same-runtime parent.
Five bot hash repeats, 30 mixed cases / 120 executions with replay and cross-hash
checks, and 60 strict-census executions pass. The balance baseline and band
remain unchanged. Rejected generated inputs are reported separately.

**20/50 original findings remain closed (40%); 30 remain open.** BE-01 remains
open for 4/9/17/58/65; 67 and 70 are repaired. Two unadopted source questions,
twelve provisional rulings and 34 unverified inventory rows remain separate.

### 3 November Litaviccus follow-up — PR-12 and full participation

The [Litaviccus report](reviews/litaviccus-targeting-2026-11-03.md) implements
owner-adopted PR-12: the Belgic bot chooses the Battle maximizing predicted
Legion Losses, accounting for actual NPC Roman Retreat or a human Roman's
safer legal standing/Retreat response. Zero-Loss or unsafe choices produce
the printed No Belgae fallback. The ruling remains provisional.

The same repair includes all Aedui pieces through the Battle, including
Counterattack and Reveal, while retaining physical ownership and native
Leader identity. It preserves City/Remi Allies across owners and uses the
actual Ambush timing and full requested Loss totals for forecasts. Human
choices, physical board inspection and durable save/replay remain supported.

Validation on the exact source: **7,427 tests passed**, with all 80 added
cases also passing on Python 3.12; 150 audited bot games, 25 cross-hash bot
repeats, 220 mixed-player cases/880 executions, and 20 strict-census
executions. Seven bot records changed, including two winners. All seven
first differences were traced to Litaviccus on identical preceding boards
and RNG; 14 paired trace games reproduce the matrix records. The existing
balance baseline passes unchanged, with maximum drift of 10 percentage
points inside its existing 15-point limit.

This follow-up sits outside the original audit denominator: **20/50 remain
closed (40%); 30 remain open.** There are now two unadopted source questions,
twelve provisional rulings and 34 separately unverified inventory rows.

### 3 November Event Battle choices — BE-02 closed

The [Event Battle repair](reviews/event-battle-choices-2026-11-03.md) restores
human Region and defender choices on 11/25/36/45/70 while retaining each
card's mandatory follow-on, printed exceptions and cooperation permissions.
It also protects revised Numidians' excluded Roman counters, removes Aedui
self-double-counting in Litaviccus, and includes Event Loss modifiers in
non-player Retreat forecasts. Board/card inspection and durable save/replay
are covered by the new regressions.

**20/50 original findings are closed (40%); 30 remain open.** The 34
unverified inventory rows, three unadopted source questions and eleven
existing provisional rulings remain separate. Non-player Litaviccus target
prediction is a newly documented follow-up; card 70's whole-benefit
acceptance and March planning remain part of BE-01.

The exact source passes **7,347 tests**, including 142 added cases, and all
142 added cases also pass on Python 3.12. Validation includes 150 bot games,
25 additional bot hash-seed repeats, 220 mixed-player cases with replay and
cross-hash repetition (880 executions), and 20 strict-census executions.
All recorded gameplay fields in the 150 bot games match the verified parent;
this is not a complete trajectory comparison. The existing balance baseline
and 15-percentage-point limit remain unchanged. See the report for source
identity, parent provenance, limitations and retained evidence.

### 3 November ordinary Arverni Phase — seven defects repaired

The [phase repair report](reviews/arverni-phase-2026-11-03.md) covers all five
follow-ups from the Gallic Event batch: one Rally placement category per
Region, Control for new Allies, a secondary March that actually removes
enemy Control, Raid's regional quantity limit and feasible Ambush reserves.
It also fixes protected-Tribe placement and Arverni receiving Raid Resources.
The rules are explicit; this batch introduces no additional provisional policy.

These seven defects sit outside the original human-choice audit denominator.
**19/50 original findings remain closed (38%); 31 remain open.** The 34
unverified inventory rows and two unadopted source questions remain separate.
The report records source identity, regressions, outcome review and validation.
The final suite passes 7,205 tests. The unchanged production code passes
150 audited bot games, 220 mixed-player cases with cross-hash replay and
20 strict-census executions. All 60 base-game comparison records are
unchanged, and the existing balance baseline passes without a refresh.

### 2 November Gallic Event ownership — BE-03 closed

The [repair report](reviews/gallic-event-grants-2026-11-02.md) separates the
Event executor from its chosen Gallic beneficiary on 35/46/67. The recipient
chooses its own actions, including Gallic Shouts' full/Limited order. Celtic
Rites keeps the original executor Eligible. Remi Influence's Gallic Remi
owner chooses the City and receives its own Citadel and four Warbands as
possible. Numeric Arduenna retains its distinct beneficiary list and scoped
March → Command → Hide sequence.

The owner adopted [PR-10/PR-11](provisional-rulings.md#pr-10) on 2 November,
subject to official overruling if an authoritative source is found. These
settle the project's automatic Arverni Command and numeric Arduenna
prediction policies. Both are implemented and validated, closing BE-03.
**19/50 findings are closed (38%); 31 remain open.** The final source passes
7,149 tests, 150 audited bot games, 880 mixed-seat executions covering 220
distinct cases, and 20 strict-census executions. The existing baseline and
its statistical limits remain unchanged.
The 34 unverified inventory rows remain separate. Two source questions still
lack an adopted project policy; eleven others have provisional rulings.
Ordinary March-to-Hide-only menu support and other BE-01 March grants remain
independently open. The A6.2 review also reproduced five separate ordinary
Arverni Phase defects (Rally Control/category, secondary March Control, Raid
quantity and Ambush reserve), tracked in the repair report outside the
original denominator and repaired in the subsequent 3 November phase batch.

### 2 November Colony defaults — post-publication CI repair

The [follow-up report](reviews/colony-event-defaults-2026-11-02.md) resolves
the prior revision's player-fuzz CI failure. Savage Dictates and Cross Rhenus
defaults now locate Colonies from current Tribe state, preserving Region
priorities and continuation. The fuzzer flags explicit bot Event rejections
even when replay hashes match; CI retains per-game evidence.

This corrects a newly exposed shared-helper defect and validation gap.
**The original audit remains 18/50 closed (36%), with 32 open.**

### 2 November named-faction Event choices — BE-04 closed

The [repair report](reviews/named-event-effects-2026-11-02.md) restores Romans'
optional choices on 2/18/23 unshaded and expansion A18, and Arverni's choices
on 26 shaded, even when another faction executes the Event. Explicit decline,
exact targets and source selections belong to the named faction. Gobannitio
can skip Ally changes and proceed to a separately chosen Rally; declining the
whole sequence skips both.

Card2 now actually places the non-player's required Legions. Expansion A18
removes Scouted Warbands and a German Successor along with the other Germans,
while its explicit named-Ariovistus protection remains. Non-player defaults
follow supplied priorities without narrowing human target legality. Terminal
menus and saved sessions retain card/board information, pending retries,
original-executor removal authority, independent Spring entry and replay.

**18 of 50 findings are closed (36%); 32 remain open.** This one-finding task
is complete. Finding counts are not an effort estimate or overall rules
certification. Other Event grants, physical choices, Capability decisions,
private peeks and seasonal decisions remain separately tracked. The report's
date uses America/Chicago; the preceding report used UTC.

### 3 November Event limits and German Allegiances — three findings closed

The [repair report](reviews/event-validation-2026-11-03.md) closes BE-11,
BE-12 and EXP-09, completing the audit's mandatory-Event/illegal-plan group.
The affected base and expansion Events enforce printed target, geographic,
beneficiary and quantity limits. Fixed effects occur as possible; valid
replacement shortfalls still remove the original piece under §5.1.1.

A29's selected beneficiary makes its own placements; Germans make A36's
placements and removals. Shaded German Allegiances now replaces German
Warbands with the executor's own Warbands, or Roman Auxilia, and supports
exact visibility/Tribe choices and ordered removal-only selections. Current
Control and physical targets are validated before mutation and after relevant
interruptions. NPC defaults follow their own source priorities.

An explicitly malformed human Event parameter object is rejected. Explicitly
rejected Events stay pending without consuming eligibility or committing the
bad choice; legal ineffective Events remain permitted. New regressions cover
real terminal decisions, detached previews and durable retry/save/replay.

At that checkpoint, **17 of 50 findings were closed (34%); 33 remained open.** This three-finding
batch is complete; percentages count findings, not effort or overall rules
accuracy. Other Event ownership/physical choices, ordinary timing and seasonal
decisions remain separate, as do the 34 unverified inventory rows, two source
questions and the NPC pre-Battle Intimidate projection lead.

### 2 November Gallia Togata and Dread — two findings closed

The [repair report](reviews/expansion-effects-2026-11-02.md) closes EXP-07 and
EXP-10. A5's executor chooses affected-owner order; each owner then chooses
legal Home destinations or removal for every prohibited Cisalpina piece,
including structures. Current-board choices preserve physical visibility,
Tribe metadata, Settlement limits and Diviciacus's removal rules.

Shaded Dread permits the added Intimidating Warband in ordinary actions,
A45 and intrinsic Raid Intimidate. With Baggage Trains, the actual third
Raider can also be the third Intimidator. An additional fresh Hidden Warband
is an explicit choice within the available physical cohort. Unshaded Dread
also correctly prevents Intimidated markers from blocking Roman Recruit.

At that checkpoint, **14 of 50 findings were closed (28%); 36 remained open.** This two-finding
batch is complete. The percentage counts findings, not effort or whole-game
compliance. A5 shaded removal choices, exact Intimidate Allied Tribe choices,
other Event validation/ownership and seasonal decisions remain separate.
The 34 unverified inventory rows, two source questions and nine provisional
rulings are unchanged. A separate NPC audit lead remains: pre-Battle
Intimidate excludes the entire defender faction instead of only guaranteed
Battle losses. Its combat-projection witness and repair are still pending;
it is outside the original 50-finding denominator.

### 2 November expansion Event grants — six findings closed

The [Event-grant report](reviews/human-event-grants-2026-11-02.md) closes
EXP-01 through EXP-06. Humans choose A21/A57 Battles, A19's whole Roman
March, A67's beneficiary and accepted action sequence, and A29/A69's Raid
and Ambush targets. Romans decide whether to accept A20/A58 regardless of
Event executor, then make current-board Battle/Seize choices. Both Seize
grants suppress enemy Rally; A58 also suppresses Harassment.

Selected pieces retain their physical identities through removals and March
interruptions. Required choices reopen after a refused troop loan; retry
targets are rebuilt from the current board. The report records source-derived
tests, independent review, terminal/durable coverage and combined validation.
Old affected transcripts may require the newly added human decisions.

At that checkpoint, **12 of 50 findings were closed (24%); 38 remained open.** This is a count of
resolved findings, not an effort estimate or certification of the whole game.
The six-finding batch is complete. Base-card counterparts, ordinary Seize's
Tribe menu, generic interruption timing, other physical choices, seasonal
decisions and optional player modes remain separately tracked. The 34
unverified inventory rows and two non-player source questions are unchanged.

### 2 November Scouted Event removals — one finding closed

The [Scouted Event report](reviews/scouted-events-2026-11-02.md) closes
`EXP-12`: A25, A26, A30 and A56 now include Scouted Warbands in their
mandatory unshaded removals. That checkpoint left **44 of 50 findings open**.
The [progress register](human-choice-progress.json) tracks later closures.
This narrow repair does not close A30's separate target-validation gap (`EXP-09`).

### 29 October first small audit repairs — five findings closed

The [small-repair report](reviews/cheap-fixes-2026-10-29.md) closes
`BATTLE-LOSS-TIERS`, `CMD-REPEATED-REGION`, `FE-02`, `WS-F07` and `WS-F04`.
Battle losses enforce their mandatory tiers, Seize/Entreat cannot repeat a
Region, malformed Supply replans remain pending, game-run Arverni cannot
transfer Resources, and new sole-human-Belgae Great Revolt games start with
Ambiorix. New regressions cover the rules and relevant menu, rollback and
save/replay paths. Each code fix has its own commit and full-suite check.

This batch left **45 of the audit's 50 grouped findings open** at that revision.
The [progress register](human-choice-progress.json) records later dispositions;
the original audit inventory remains a historical record of `7e72fe7`.
The 34 unverified inventory rows and two non-player source questions remain
separate. Event/Interlude choice routing, general interruption timing, exact
casualty identities, transfer windows and shared-player ownership are outside
this batch. The report records validation and compatibility limits.

### 29 October human-choice audit — open repair backlog

The [human-choice audit](reviews/human-choice-audit-2026-10-29.md) completes
the bounded inventory previously listed as pending. At `7e72fe7`, it records
**50 grouped open findings**: 21 high, 28 medium and one low. These include
rule errors, unavailable human choices, previously documented transfer/shared
player limits, and optional setup features. They are not all new regressions.
No production behavior was changed by the audit.

The 490-row inventory covers base/revised and expansion Event identities,
Commands, Special Abilities, seasonal decisions and both interfaces. Eleven
independently rerun probe scripts preserve representative failures; the
unchanged engine still passes 6,109 tests. Thirty-four inventory rows remain
explicitly unverified. Source inspection and routing support are distinguished
from executed semantic checks.

The audit's first repair priorities were illegal Battle casualty tiers, duplicate
Seize/Entreat Regions, malformed Supply responses, forbidden Arverni transfers
and Great Revolt Belgae setup; these are addressed above. Later batches cover Event constraints/effects,
correct human ownership, exact choices/timing, Interlude/Winter, and optional
player modes. The report assigns every finding once and records reproductions.

Earlier verified rows below describe their tested paths. The dated repairs
above and the [progress inventory](human-choice-progress.json) track later
coverage. The two existing non-player source questions remain separate.

### 29 October action timing and exact participating pieces

The [action-timing report](reviews/action-timing-2026-10-29.md) follows the
three interface gaps identified by the rules/Trade review. Players can
reclaim their own physical pieces or downgrade a Citadel during their
Sequence-of-Play Command/Event, including later steps and grants to another
faction. Vercingetorix can enter at procedure boundaries after his first
eligible Spring, including opponents' actions and later Winter. An ordered
Arverni Rally can insert its Special Ability between the two options in one
Region, with the Region's cost and bonuses applied once.

Planning previews expose these choices before computing Available pieces,
Control and Leader requirements. Live execution rechecks the next operation
without repeating completed dice or effects. Marching, Scout, Event-placed
and Elite pieces retain their exact identities through removals. Durable
sessions preserve pending choices and replay older accepted decisions without
silently defaulting new human decisions.

Related source checks corrected repeated Scout movement, overlapping
Diviciacus/Event-force bookkeeping, Scouted Rampage targets, and Event
participation limits. The report records the exact validation revision and
the further Seize/Surus corrections found during this review. A broader
source-derived inventory was subsequently completed by the audit above;
its confirmed findings remain repair work.
The non-player Trade question and the newly recorded physical Elite
designation question remain source questions, not new approved rulings.

Final local validation passes **6,109 tests**, **150 audited bot games**,
**80 mixed-seat executions including replay**, and **50 strict-census
executions**. Cross-hash reports match with zero hard defects. The original
balance comparison failed; all 100 paired parent/candidate games were
reviewed before refreshing 69 winner/card records. Fresh games exactly
match the reviewed baseline at the unchanged 15-point tolerance. The report
retains the failed comparison, diagnostic capture retries and the distinction
between corrected rules choices and implementation RNG sequencing.

### 29 October rules adoption and Trade choice

The [rules and Trade report](reviews/rulings-trade-2026-10-29.md) records the
owner's adoption of three additional provisional rulings, PR-07 through
PR-09, and the printed-card resolution of O38. Non-player Aedui Supply uses
one roll for the complete human Roman action; ordinary Rally/Recruit
prerequisites precede their bonuses; tied A20 casualties select an origin
Region at equal odds for each loss. The rulings remain subject to later
authoritative correction.

The replacement Diviciacus photograph confirms that both sides are
Capabilities under §5.3, so bots decline both in the final year. Human
choices remain available. O38's unshaded Capability is recorded separately
from original card 38's geographically unrestricted cooperation effect.
A20 now returns exact survivors to their original Regions and cannot take
projected losses on nonparticipating local Allies/Citadels.

Human Aedui can select the single Trade Region under shaded River Commerce
after the relevant Supply declarations. The choice uses the actual board
at the Special Activity, including a preceding Command, and preserves
pending decisions, save/resume and replay.

Final local validation: **5,777 tests passed**, **150 audited bot games**,
**80 mixed-seat executions including replay**, and **50 strict-census
executions**. The original 15-point balance guardrail passes without changing
its baseline. Cross-hash replay and census reports match. The report retains
the failed implementation attempts separately from the accepted source.

The actual Aedui die refusal now lets Rome reconsider a Recruit plan before
it executes, or reconsider Build at its own boundary while keeping an
earlier completed Command. Replanning retains the refusal, and saved
sessions preserve and verify rejected attempts that established it.

At that checkpoint, three known interface gaps remained: voluntary own-piece removal/Citadel
downgrades throughout legal action timing; Vercingetorix's mid-action
Spring-box entry; and a Special Activity between his two Rally options in
one Region. The action-timing repair above addresses these three gaps.
The subsequent human-choice audit above records the broader remaining gaps.
The report records why start-only reclamation would be incomplete.
The separate non-player shaded Trade selection question is recorded in
[Q-TRADE-NP-REGION](../QUESTIONS.md#q-trade-np-region--shaded-river-commerce-selection-29-october-2026);
this batch retains its existing policy pending source review.

### 29 October Recruit and Rally choices

The [Recruit/Rally report](reviews/recruit-rally-2026-10-29.md) closes the
optional troop-quantity menus and Vercingetorix's combined Rally menu from
the comparison backlog. It also records related bonus, Roman bot Recruit,
Belgic Citadel, Enlist, physical ownership and Tribe-eligibility corrections.
Ordered human plans preserve exact quantities, legal Region limits and
shared pools through pending decisions, rollback, save/resume and replay.
Validation also exposed overlapping A28/Diviciacus forces and Scouted-marker
handling in Battle and A20; the report traces those related repairs.

At that checkpoint, two original implementation items remained: voluntary own-piece reclamation
under §1.4.1 and Vercingetorix entry inside a resolving Command/Event. The
source-derived completeness audit was also pending. That review had confirmed
another within-action limitation: an SA could not interrupt the
two Vercingetorix Rally options in the same Region; the then-current interrupted
Command portions use different Regions.
The Trade review confirmed a second gap: human Aedui could not select the
single Trade Region under shaded River Commerce (Card 39); execution used
a highest-yield proxy. That choice remained part of the completeness
work. Four implementation gaps were known at that checkpoint. The later rules
and Trade repair above closes the Trade Region choice.

Final local validation passes 5,622 tests, 150 audited bot games, 80
mixed-seat executions with replay and 50 strict-census executions. The
original 15-point outcome guardrail passes without a baseline refresh;
the report retains the changed individual outcomes and failed candidates.
Old Aquitani saves lacking an owner remain owner-unknown. The newly recorded
[bonus-timing question](../QUESTIONS.md#q-rally-bonus-timing--additions-before-ordinary-placement-29-october-2026)
asks whether printed additions can establish Control before an ordinary
placement. [A20 casualty origins](../QUESTIONS.md#q-a20-origin--counterattack-losses-among-projected-origins-29-october-2026)
were also unresolved when projected Warbands have equal visibility. The
later owner adoption above settles their project behavior. The
[Aedui Supply agreement question](../QUESTIONS.md#q-supply-aedui-die-scope--agreement-across-multiple-regions-29-october-2026)
records the separate uncertainty about dice covering multiple Regions, now
governed by provisional PR-07.

### 28 October Spring Leader placement

The [Spring report](reviews/spring-leaders-2026-10-28.md) records mandatory
Successor destinations, human placement decisions, and non-player priorities
for every eligible faction. Bots choose the most own pieces among legal
Regions, using seeded equal ties. Their Spring nodes return Successors rather
than reviving named Leaders. Diviciacus never receives a Successor.

Pax Gallica's boxed Vercingetorix can enter beginning the first Spring or
remain boxed for a later action-boundary prompt. The first Winter after the
Gallic War Interlude unlocks this option; the Interlude's embedded Spring does
not. The Interlude now restores Ambiorix even when the first-half Leader was
a Successor and lets human owners choose equally preferred named-Leader
destinations. New choices preserve card/board/change information, pending
answers, rollback, saved sessions and replay.

The final local suite passes 5,226 tests. The accepted matrix contains 150
audited bot games across three editions, 80 mixed-seat executions with replay,
and 50 strict-census executions. The original balance comparison failed;
all nine changed winners were traced and reviewed before refreshing eleven
baseline records. A fresh 100-game check exactly matches the reviewed
winner/card counts with the same 15-point limit. The report preserves the
old-save expectation failure and all superseded verification evidence.

At this Spring checkpoint, Vercingetorix entry inside a resolving Command
or Event remained a human-interface gap: action-boundary prompts did not
fully implement the scenario's printed “at any time” right. Other
remaining comparison work was
optional Recruit/Rally quantities, Vercingetorix's combined Rally menu,
voluntary own-piece reclamation, and a source-derived inventory of every
printed human choice. The 29 October entry above updates those dispositions.
The later 29 October rules-adoption entry updates Q-O38 and the ruling register.

### 27 October human Event choices batch

The [second-batch report](reviews/second-batch-2026-10-27.md) records the
next repairs from the comparison: The Province, Ambacti and Chieftains'
Council. It covers the printed human choices, decision ownership,
information timing, and related non-player and execution defects. The
supplied Falling Sky references remain the gameplay authority.

The Province now offers Auxilia or Resources, applies a two-box Senate
shift as a single Event when Firm, and carries its Fort exception into the
Arverni Battle prediction. Roman bots enforce their full-five-Auxilia
instruction. Ambacti asks after the actual roll, exposes exact physical
removals, and preserves that pending decision through save/resume. Its
non-player placement/removal priorities and Aedui's permitted Roman benefit
are corrected.

Council now exposes the executor's Region and beneficiary subset, private
face-down card information, and each selected faction's Command, Eligible
or decline choice in scenario-correct initiative order. Eligible survives
card cleanup. Private peek data is kept out of public board/change output
and results. Shared free-action validation also rejects numeric defaults
and declines instead of treating them as explicit Boolean answers.
Public card summaries now map retained base-card initiative and non-player
symbols to the German player seat in Ariovistus.
The Aedui's conditional Event exclusions now apply to every flagged entry
in the current scenario's instruction table. Those bots decline when Romans
are human or the Roman victory score exceeds 12, including the expansion's
Settlement subtraction. Human Event choices retain their printed freedom.
The later bot-game run also exposed Winter Uprising's markerless trigger.
Its required Region now validates before mutation, and bots follow their
printed geographic target instructions without requiring existing pieces.
Last-year restrictions use the live Winter calendar and preserve the
Gallic War's pre-Interlude continuation.
Winter Uprising also records its holder, permits human deferral after normal
Quarters, forces activation at Interlude, and exposes exact within-one-Region
Allied Tribe and Warband placements to the proper chooser. Non-player
placements follow their priorities, and the subsequent Command is required
when possible. These decisions support full held-card text, board inspection,
pending input, save/resume and replay.
Scoped Event planning now preserves legal German Rally + Settle plans that
place only a Settlement, rather than discarding those fields as an empty
Rally.

Roman and Aedui bots also enforce Nervii's separate printed restriction: decline
A70 when Belgae are non-player, including before the final year. Human Events
and choices against player Belgae remain available.

The optional O38 shaded Capability now receives the same final-year check.
At that checkpoint its unshaded classification remained [Q-O38](../QUESTIONS.md#q-o38--optional-diviciacus-capability-label-27-october-2026): the flat
source transcription did not settle the label's placement. The owner's later
replacement-card photograph resolves the label; see the 29 October entry.

At this checkpoint, remaining comparison work included Spring Leader
placement, optional Recruit/Rally quantities and Vercingetorix's combined
Rally menu, voluntary own-piece reclamation, and a source-derived inventory
of every printed human choice. The 28 October entry above records subsequent
Spring repairs and their remaining interruption limit.

### 27 October Event integrity batch

The [first-batch report](reviews/first-batch-2026-10-27.md) records the repairs
from the owner-authorized Liberty or Death engineering comparison. Falling
Sky's supplied references govern every gameplay change; the other project
provided testing ideas, not game rules.

This batch addresses piece-operation/count validation, Boii's bounded plans,
Event eligibility at card cleanup, A33/A70 capability lifetimes, Parley's
meeting execution and planning, and related Diviciacus/Ariovistus defects.

The comparison confirmed the following gaps at the first-batch checkpoint:

- The Province and Ambacti human menus, and Chieftains' Council's human
  beneficiaries, information and decisions.
- Spring Leader placement priorities, legal destinations, human choices
  and randomized non-player ties.
- Optional Recruit/Rally quantities and Vercingetorix's combined Rally menu.
- Human voluntary own-piece removal/reclamation under §1.4.1.
- A source-derived inventory of every printed human choice, independent of
  the implementation's existing hooks.

The three Event gaps are addressed by the second batch above. Earlier
passing batches did not establish completeness in these areas.

### Earlier follow-up repairs

The following changes follow that checkpoint; its 1,000-game outcomes are
historical evidence for the earlier mechanics, not measurements of these
changes.

| Area | Follow-up behavior | Coverage |
|---|---|---|
| Diviciacus cooperation | Consenting Roman Auxilia and Aedui Warbands act as the other type for the permitted Command, Leader Special Activity, or defense. Physical owners, inventories and Control remain distinct; human consent and exact piece choices are exposed. | Diviciacus engine, interface and terminal journey regressions |
| Cooperating March cohorts | Native-only groups and native survivors retain the physical-owner context across later steps after borrowed pieces leave or are lost; transit residents are not silently added. | `test_diviciacus_forces.py` and Reconquest seed 148 |
| Cooperation planning and casualties | Bots plan with eligible borrowed forces and replan from the same RNG position after refusal. Diviciacus is the last possible casualty; borrowed Scouted Warbands lose their marker and remain Revealed when Roman March would hide them. | Consent, loss-legality and March-visibility regressions |
| Suborn and Vergobret | Human menus expose native owners and exact visibility. Complete ordered plans validate before mutation; capability limits permit four pieces and two Allies. Non-player Ally priorities follow §8.6.3. Both A38 sides replace/remove correctly and old modifier-only saves remain readable. | Suborn interface, atomicity, bot limits and Vergobret regressions |
| Event cooperation | Fixed Event Battles obtain the acting human's opt-in and lender's agreement. Camulogenus uses its printed selected force, single destination and movement range without flipping stationary pieces. | Event Battle and Camulogenus cooperation regressions |
| Capability selection | Shifting Loyalties offers actual active capabilities, including legacy A38, instead of Region names. The board and change display use the same effective capability list. | Legacy capability display and parameter-schema regressions |
| Roman Quarters destinations | The default planner checks the same eligible host factions as the validator before requesting consent. Human German agreement cannot authorize a prohibited Roman destination. | `test_roman_quarters_host_eligibility.py` and Gallic War seed 7 mixed-seat replay |
| Supply-Line agreements | Accepted consent holds for the Command or Event. Recruit's preliminary budget check and actual execution share the same answer, preventing duplicate prompts and contradictory costs. | Supply agreement regressions and mixed-seat replays |
| Optional Diviciacus setup | Original scenarios can select O38 and the Leader separately from card edition; setup, saves, replay, display and Roman bot restrictions retain that choice. The canonical Interlude A38 replacement remains unchanged. | `test_diviciacus_option.py` |
| Strategy experiments | Correct human-seat classification; scenario-valid German policies and Interlude handover; error/integrity/diagnostic checks; versioned compatible resume that retries failures. | `test_strategy_harness.py`, `test_selfplay_tools.py` |
| Outcome acceptance | Rejected actions fail audited batches and cannot count as validated wins. Output directories cannot silently overwrite earlier evidence. | `test_outcome_runner.py` |
| Fuzz and census acceptance | Unfinished games and replay-only failures fail explicitly. Determinism includes the full state, RNG and returned trajectory, including Available pools, eligibility, deck and capabilities. | `test_validation_integrity.py` |
| Editions and seeds | Full-game batch, census, fuzz and synchronization tools expose and record card editions and held-out seed ranges. CI exercises all three edition profiles. | `test_validation_options.py` and edition CI jobs |
| Human journeys | Real terminal March, Battle, both SA orders, multi-human reactions, pending resume and replay, plus forced Interlude handover. | `test_cli_decision_journeys.py`, `test_diviciacus_journeys.py` |
| Installation and compatibility | A local installable distribution includes unchanged runtime references. Saves identify their writer; fixtures from unmodified earlier source cover pending decisions and Interlude states. Fresh-process import cycles and hash-dependent Trade detail ordering are repaired. Git attributes preserve source/reference/fixture bytes on Windows checkouts. | Package workflow, `test_import_order.py`, `test_release_compatibility.py`, `test_trade_determinism.py` |

See [release checks](../RELEASES.md) and the [self-play workflow](../SELFPLAY_PLAYBOOK.md)
for reproduction commands and compatibility limits.

## Corrections in the 23 October review

| Area | Corrected behavior | Regression coverage |
|---|---|---|
| Human decisions | Current/upcoming card text and changes are shown before decisions; `board` is available at prompts. Commands and Special Abilities can be selected in either order, including scoped Event grants. | `test_turn_visibility.py`, `test_human_action_order.py`, `test_cli_free_actions.py` |
| Card editions | Saved original, Second Edition, or legacy profile consistently controls cards 11/30/39/44/54. Revised Vercingetorix's Elite and River Commerce use their printed limits/effects. | `test_card_edition.py` |
| Marcus Antonius (6) | Romans choose optional Scout and Battle separately, even when another faction plays the Event. Battle keeps the doubled-Auxilia bonus and normal capability effects; bots decline the whole Event when neither action can have an effect. | `test_marcus_antonius.py` |
| Morasses (36), shaded | Humans choose the Gallic beneficiary, Battle plan and March, including in-place hiding. Belgae target Romans then Gauls where Losses are possible and then hide in place. Aedui retain their one-Region Ambush limit. Actual Command capabilities, pre-fire and Frost outcomes are checked; wholly ineffective Events are declined before selection. | `test_morasses.py`, `test_morasses_decisions.py` |
| Joined Ranks (54) | Optional March respects distance and eight-piece limit, including Leaders. Battles use the same defender; a second human faction chooses whether to participate, and a second non-player faction does not Battle. | `test_joined_ranks_choices.py` |
| Dumnorix (44) | Replacements respect counts and owners; Scout/Raid uses only the newly placed cohort. Revised free Commands stay in placement Regions. | `test_dumnorix.py` |
| Base Event limits (40/41/42/51) | Placement alternatives, complete target quotas and printed areas are enforced. Roman Wine follows its Supply and NPC instructions; Avaricum replacement shortages remove the exact source Ally; Surus cannot recycle newly placed counters. | `test_base_event_limits.py` |
| German Allegiances (65), shaded | Exact German targets require executor Control; human entries select removal or native replacement in order. Scouted counters, Tribe records, scarce pools and timing interruptions remain physical. NPC defaults obey their specific availability instructions. | `test_german_allegiances.py` |
| Expansion Event limits (A29/A30/A36/A43/A45) | Repaired sides enforce beneficiaries, areas, types and totals; A29's beneficiary and A36's Germans own their choices. Partial replacements obey stacking/availability; NPC self-only policy is separate from human legality. | `test_expansion_event_validation.py`, `test_cli_expansion_validation.py` |
| Impetuosity (72), shaded | Humans choose one original Hidden Warband group for an adjacent or in-place March and separately choose optional Battle with that group alone. Bots respect player targets, physical Control, Frost and the Belgic Leader’s post-Battle escort. The one-use grant cannot leak into later Events. | `test_impetuosity.py`, `test_impetuosity_decisions.py`, `test_cli_impetuosity.py`, `test_free_action_lifetime.py` |
| Impetuosity (72), unshaded | Humans choose groups from adjacent origins to one destination, then the eligible Arverni or Belgic attacker. March is mandatory when possible. Romans apply their printed March priorities before checking for the resulting Battle, and decline the Event before selection when instructed. | `test_impetuosity_unshaded.py` |
| Resources | Normal Battles pay their printed costs. Free Event actions waive costs and include a Special Ability only when granted. | `test_free_action_costs.py` |
| Arverni Battle timing | Non-player Battles are paid before Devastate/Entreat, as instructed by §8.7.1; the accompanying ability cannot spend those reserved Resources. | `test_arverni_battle_payment.py` |
| Raid | Bots exhaust each target priority before moving to the next. Steals require sufficient victim Resources and validate the complete Region plan before revealing pieces. | `test_raid_priority_regressions.py` |
| Raid Intimidate | Ariovistus’s actual Raiders can free Intimidate independently of an accompanying Special Ability. Humans can decline, place only a marker, or select removals with pause/save/replay. Card 8's third Raider supplies a third Intimidator only with shaded Dread; Dread can instead spend one additional eligible Hidden Warband explicitly. | `test_raid_intimidate.py`, `test_raid_intimidate_decisions.py`, `test_cli_raid_counts.py`, `test_dread_intimidate.py` |
| Acco (34) and Britannia (57) | Human beneficiaries choose free actions. Acco applies its Control/Devastated exceptions and Region limit; Britannia resolves its optional scoped Special Ability and checks the Resource bonus afterward. | `test_event_free_choices.py` |
| Enlist | Borrowed German Warbands retain physical ownership through movement, control, actions and losses. Both Enlist options respect base/expansion restrictions. | `test_enlist_borrowed.py`, `test_enlist_free.py` |
| Human movement menus | March can split an origin into multiple groups, include a remaining Leader, and plan full Roman/Vercingetorix routes. Subsets recheck Leader range, Alps and Abatis stops; previewing does not roll future Harassment. Base German Rally offers its Ally-then-Warbands sequence. | `test_cli_march_groups.py`, `test_cli_march_routes.py`, `test_migration.py` |
| Marching piece choices | Humans choose the actual Hidden/Revealed pieces when forming a subset or leaving pieces behind. Split groups flip an origin only once per Command. Divination's chosen player controls German piece selection while physical ownership stays German; previews do not prompt or change the live board. | `test_march_visibility_choices.py` |
| Scoped bot planning | Event Region limits are applied before target selection and piece allocation. Each faction follows its own Command branches and exclusions; German Settlement placement can create legal placement chains. | `test_free_flowchart_scope.py`, `test_roman_german_command_scope.py` |
| Movement and Rally | Normal March distance is checked before spending/flipping. Rally respects faction- and scenario-specific option limits, including Vercingetorix’s exception and base German Ally-then-Warbands placement; German home bonuses execute. Free Enlist Marches respect Event Region limits, cost waivers, and the Frost exception. | `test_march.py`, `test_rally_prevalidation.py`, `test_free_enlisted_march.py` |
| Admagetobriga (A28) | All selected eligible Regions resolve. Combined Warbands/Auxilia retain ownership through loss calculations, casualties, and Reveal; humans choose targets and consent. Non-player Romans refuse as specified. | `test_admagetobriga.py` |
| Divination (A34) | A chosen beneficiary commands the actual German force, choosing March or Battle in/from up to three Regions. Bots use their own strategic priorities with German movement and Battle mechanics; Frost checks possible outcomes. | `test_divination.py`, `test_divination_np.py`, `test_divination_frost.py` |
| Publius Licinius Crassus (A17) | Romans form the printed Legion/Auxilia group, then choose a legal route, drop-offs, and Battle at the Caesar-free destination. Real March handles Harassment and partial execution; a destroyed group cannot redirect Battle into its transit Region. Bots apply March priorities within legal origins and destinations. Auxilia receive the printed Battle bonus. | `test_publius.py` |
| March after Harassment | Actual losses are applied to the carried group once. A visibility ledger prevents residents from replacing departing pieces. Drop-offs remain behind, surviving pieces continue, and losing Caesar or Vercingetorix removes the extra movement they grant. A successful Leader saving roll no longer removes that Leader from the moving group. | `test_publius.py`, `test_march_cohort.py` |
| Harassment decisions and order | Humans choose soft casualties or a die roll, then the required hard casualty on a failed roll. Visibility and exact Allied tribes are selectable. Later harassers see prior losses; base-game announcements during Event-card turns follow card order then Germans. Roman Hidden Auxilia and Ariovistus German bots now Harass when instructed. Game-run factions cannot be prompted to waive mandatory Harassment. | `test_harassment_decisions.py` |
| Battle outcome prediction | Independent human Retreat agreements retain their own Region and response history. The shared predictor checks the complete Battle Command and rejects an empty outcome set, preventing an unsafe Frost action from passing without any simulated outcomes. | `test_divination_frost.py`, `test_impetuosity_unshaded.py` |
| Gallia Togata (5/A5) | The actual marker governs geography and Roman-only stacking, including lingering A5 effects after Interlude. A5 unshaded gives the executor owner-order choice, then each owner allocates every prohibited piece to legal Homes or removal with exact visibility and Tribe metadata. | `test_gallia_map.py`, `test_gallia_evacuation.py` |
| Arduenna (A67) | German forces gather the safe surplus from controlled origins, account for departing Leaders and all opposition, and choose a target where Control is achievable. | `test_arduenna_surplus.py` |
| War Fleet (62) | All four non-player factions derive the printed coastal relocations and follow-on Command. Arverni Battle the selected player target; Roman distribution respects origin, Legion/Leader and final-force priorities. Availability and Frost checks preview the complete actual Command, including capabilities and human outcomes. | `test_war_fleet.py`, `test_war_fleet_roman.py` |
| Kinship (A65) | A human Event executor chooses Belgae or Germans to Battle in any selected legal Regions. One Command applies its limits once, without costs or an accompanying ability. The attacker’s Leader remains physically present but does not fight or absorb losses. Non-players obey the beneficiary and opposing-player restrictions before choosing the Event. | `test_kinship.py`, `test_kinship_decisions.py` |
| Migration (66) | The executing player chooses real German Rally and March separately, each limited to two Regions/origins. Roman bots follow the printed movement instructions and maximize Rally placement. | `test_migration.py` |
| Frumentum (A53) | Aedui specify funding; Romans choose paid Recruit, March and one Special Ability in any order. Roman personal funds are reserved, and non-player funding follows A8.6.6. | `test_frumentum.py` |
| Savage Dictates and Intimidate | A45 waives only its printed Leader/Control restrictions. Targets retain the one-Faction limit and normal two-Warband limit, increased to three with shaded Dread. Unshaded Dread also protects Roman Recruit from Intimidated markers. Removals validate before mutation. | `test_intimidate_grants.py`, `test_dread_intimidate.py` |
| Harudes (A29) and Bellovaci (A69) | Harudes Raids use the newly placed Warbands and respect the Settlement limit. Bellovaci checks Ambush legality and gives its attack bonus only to newly placed Warbands. | `test_nested_event_rules.py` |
| Successor and Litaviccus (45) | Threat March uses the actual Leader’s movement allowance. Pooled Aedui Warbands count for Ambush strength without bypassing Leader range; ordinary Battle remains available when Ambush is not. | `test_census_planner_regressions.py` |
| Winter Uprising and Interlude | The Interlude executes Uprising and Winter Campaign before changing Forces and scenario. Forced Arverni phases handle an empty target set; Aedui/Belgic A63 ownership remains effective afterward. | `test_winter_uprising_regressions.py` |
| Winter Campaign | Humans can take up to two paid actions, including standalone Special Abilities. A63 records and activates its proper owner. Bot plans honor the remaining action budget before selecting dependent actions such as Settle/Rally. After-Harvest Harassment no longer tries to look up the Winter marker as an Event. | `test_winter_campaign_decisions.py`, `test_winter_harassment_order.py` |
| Quarters | All human factions choose relocations and payments, including exact visibility cohorts and Roman Provincia continuations. Complete adjacent relocation groups are validated against pre-step Control, and original visibility is preserved so arrivals cannot move again. Supply Lines use the resulting board. Invalid destinations, static-piece movement and negative payments are rejected; losses apply to the actual unpaid pieces. | `test_quarters_decisions.py`, `test_quarters_relocation_step.py`, `test_quarters_visibility.py` |
| Saves | Production loading validates board structure and pending-turn cursors before resuming, with readable errors for malformed saves. | `test_save_validation.py` |
| Human replay | Default reactive responses are recorded. Actual terminal games from every playable seat replay to the same final state. Explicitly rejected human Events retain their pending turn; legal ineffective Events remain permitted. | `test_cli_playthroughs.py`, `test_german_allegiances.py`, `test_resumable_turns.py` |
| Morbihan display | During A20’s “as if there” Ambush, human loss choices show physical Arverni Warband origins and actual Roman losses, with the temporary battle calculation identified separately. | `test_morbihan_display.py` |
| Borrowed-force display | Board views and per-seat changes show physical ownership during Enlist and Admagetobriga; active borrowed forces are identified separately. Actual Control, losses, and piece visibility remain visible. | `test_borrowed_force_display.py` |
| Assistant play | Human reactions pause explicitly; a single saved session records inbox consumption, pending decisions and prior choices. Resume/replay does not silently choose or reroll earlier responses. | `test_assistant_session.py` |
| Game diagnostics | The census inspects nested Event grants, Winter Campaign, and game-run Winter phases. Explicit declines remain distinct from rejected actions; duplicate result aliases do not inflate counts. | `test_census_nested_actions.py` |
| Event instructions and effects | Actor-specific target checks, mandatory piece types and scope, missing Gobannitio/Correus plans, and local optional declines are corrected. Aedui use the printed shaded-text instruction group from each scenario’s own table; Remi’s condition and City/Remi loss priorities apply in the proper scenarios. | `test_event_grant_outcomes.py` |
| All Gaul Gathers (A37) | Humans choose scoped Ally placements and direct movement of their Leader/Warbands/Auxilia, with all choices validated before mutation. Eligibility uses the pre-Event board. Non-player Aedui maximize their Ally placements and move no pieces; ineffective and out-of-scope Events are declined before selection. | `test_all_gaul_gathers_np.py`, `test_all_gaul_gathers_choices.py` |
| Correus (64) validation | Shaded human choices must remove the required number of distinct eligible Allies before optional placement or Rally; invalid choices roll back. | `test_event_grant_outcomes.py` |
| Balance checks | All five scenarios and all eligible winners are covered; missing baseline games fail explicitly. Exact threshold comparisons avoid rejecting an allowed 15% change because of floating-point rounding. | `test_balance_guardrail_coverage.py` |
| Event selection | Non-players check actual eligible targets and the supplied instructions before choosing Mons Cevenna, Assembly of Gaul, or Sabis. | `test_event_conditional_declines.py` |

<a id="source-conflicts-still-open"></a>

## Adopted provisional rulings

On 24/29 October and 2/3/5 November 2026 (America/Chicago), the owner adopted the following
project policies. **Each is subject to possible later correction if an
authoritative source is found.** The [ruling register](provisional-rulings.md)
records their exact scope and rationale; the
[question ledger](../QUESTIONS.md#current-open-source-questions) preserves
the source ambiguities. Adoption settles implementation policy without
claiming official errata or designer confirmation.

| Ruling | Current behavior |
|---|---|
| [PR-01: A30 Orgetorix](provisional-rulings.md#pr-01) | Ignore the extra Belgic laurels and use the ordinary shaded Event procedure, with no invented special instruction. |
| [PR-02: A28 agreements](provisional-rulings.md#pr-02) | Non-player Aedui and Belgae lend only in selected Battles where the executor contributes its own participating pieces. Non-player Romans refuse; humans choose; Arverni participation is automatic. |
| [PR-03: A53 funding](provisional-rulings.md#pr-03) | Romans retain unused transferred funding, subject to the normal Resource cap. No automatic refund. |
| [PR-04: German-owned A63](provisional-rulings.md#pr-04) | Resolve its Interlude activation before transition, retain German ownership afterward, and leave it dormant in the base-game half. |
| [PR-05: Ariovistus Harassment](provisional-rulings.md#pr-05) | Follow printed faction order with Germans in their proper slot, then automatic Arverni last. |
| [PR-06: Winter Harassment](provisional-rulings.md#pr-06) | Retain the last actually played non-Winter card's order, including all-pass cards; keep the game-run faction last. |
| [PR-07: Aedui Supply dice](provisional-rulings.md#pr-07) | One roll for the human Roman action, including its Special Ability and all relevant Regions; retain the answer during replanning. |
| [PR-08: Placement bonus timing](provisional-rulings.md#pr-08) | The ordinary placement option must qualify before its additional pieces; explicit printed exceptions remain. |
| [PR-09: A20 casualty origins](provisional-rulings.md#pr-09) | Preserve visibility priority, then select equally among eligible origin Regions separately for each casualty. |
| [PR-10: Automatic Arverni Event Command](provisional-rulings.md#pr-10) | While At War, first possible permitted Command in phase order, retaining inherent Ambush. |
| [PR-11: Numeric Arduenna prediction](provisional-rulings.md#pr-11) | Conservative Legion Loss forecast, printed Roman NPC Retreat and Vercingetorix Harassment safety; actual choices/dice resolve live. |
| [PR-12: Litaviccus target prediction](provisional-rulings.md#pr-12) | Belgic bot maximizes predicted Legion Losses, using printed NPC Roman Retreat or the lower human standing/Retreat forecast; printed Battle/Frost restrictions remain. |
| [PR-13: Mandatory queue capabilities](provisional-rulings.md#pr-13) | Actual Battle use/reserve choices, compulsory use if the final queued candidate becomes a Battle, and unused expiry if no later eligible Battle occurs. |

PR-06 recovers the order from saved `played_cards` without changing
`current_card`. A state with no recoverable preceding Event uses the current
scenario's Winter Campaign card order (63/A63) as a documented compatibility
fallback. Protected references and `rules_consts.py` are unchanged.

## Verification and limits

The [27 October second-batch report](reviews/second-batch-2026-10-27.md)
records 5,112 passing tests, 200 audited bot games across three editions,
80 mixed-seat executions including replay, and 50 strict-census executions.
Cross-hash reports match, with no hard or partial mixed-seat findings and
zero diagnostic defects. Two rejected random plans per hash and 245 legal
census declines per hash are recorded separately. The report preserves
superseded runs, exact causal replays and the original failed balance
comparison. The reviewed baseline refresh keeps the same 100 seeds/scenarios
and 15-point limit. Superseded outcomes are not pooled with the final matrix.

The [27 October first-batch report](reviews/first-batch-2026-10-27.md)
records 4,715 passing tests, 200 accepted bot games across three card
editions, 80 mixed-seat executions including replay, and 50 strict-census
executions. Cross-hash reports match. The unchanged balance band passes;
25 individual legacy-game winners changed, with a maximum faction rate
movement of exactly 15 percentage points. The report distinguishes rejected
random plans and the remaining confirmed human-play gaps from accepted
engine validation.

The [provisional-ruling report](reviews/provisional-rulings-2026-10-24.md)
records 4,481 passing tests, 200 audited bot games, 320 mixed-seat executions
with replay, and 40 strict-census executions on the adopted implementation.
All completed without defect findings. Mixed-seat outputs and census reports
matched byte-for-byte between hash seeds 0 and 7. The 100-game balance check
passed with every win rate unchanged; the baseline was not updated. Exact
coverage, source identities and the local/remote validation boundary are in
that report.

The [24 October follow-up report](reviews/followup-repairs-2026-10-24.md)
preserves the preceding accepted source: 4,431 passing tests, 2,500 accepted
bot games across scenario/edition profiles, 90 optional-Diviciacus games,
75 matching bot hash-seed repeats and 1,000 completed mixed-seat executions
with replay. The main bot matrix has no crashes, illegal diagnostics,
integrity failures or ranking/hash findings. Mixed-seat runs have no hard
findings and disclose one repeatable partial plan from an intentionally
injected Resource gift. Strict census, reviewed balance and isolated
installation checks also pass. Consult the report for exact source identity,
seeds, denominators and separately reported remote CI status.

The historical [23 October validation report](reviews/outstanding-fixes-2026-10-23.md)
retains its original 4,067-test and 1,000-game checkpoint; those measurements
have not been relabeled as results of these repairs.

The full-game terminal tests exercise real menus, invalid input, the `board`
command, Commands and exact replay across all twenty scenario/seat pairs.
They are functional journeys, not evidence of expert human strategy, and do
not by themselves guarantee that a Gallic War game reaches the Interlude.
Dedicated tests cover the transition separately.

Seeded bot games and mixed-seat fuzzing complement source-derived rule tests.
A clean run demonstrates the tested paths and seeds, not proof that every
published rule is correct. Win-rate baselines are refreshed only after
explaining rules-driven changes; no bot priorities are tuned to obtain
preferred faction win rates.

The configured CI matrix covers Ubuntu Python 3.10/3.12, Windows Python
3.12 and macOS Python 3.12. Linux also runs synchronization, nested
Event/Winter census, mixed-seat determinism, balance checks and all three
card-edition profiles. A separate package workflow builds and checks installed
play on Linux, Windows and macOS. Local results and remote CI conclusions
are reported separately for the exact tested commit.

## Strategy-study limits

The current runner repairs the former non-player classification, missing
German participation, weak resume identity and false-success behavior.
Experimental policies still use their documented reactive defaults and
limited plan builders; their results are not expert human strategy or a
uniform sample of every legal choice. New comparisons need fresh,
revision-specific runs and record-level acceptance.

Those repairs do not retroactively validate the
[historical strategy notes](../selfplay-strategy-notes.md). Their original
runner retained the overridden seat in `non_player_factions`, omitted
German profiles and could reuse old or failed records. The earlier accepted
1,000-game bot batch used `run_batch`, independently of that runner. See the
[self-play workflow](../SELFPLAY_PLAYBOOK.md) for current contracts.
