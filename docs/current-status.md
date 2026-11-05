# Current engineering status

This document supersedes older completion claims in `QUESTIONS.md` and the
build plan. It distinguishes verified engineering fixes, adopted provisional
project rulings, and unresolved external source questions. The historical audit reports retain their original results;
their game outcomes are not a baseline for a later rules revision.

[Documentation index](README.md) · [Playing guide](../PLAYING.md) ·
[Current question index](../QUESTIONS.md#current-open-source-questions)

This page includes the 24 October adoption of six and 29 October adoption
of three additional rulings, the 2 November adoption of PR-10/PR-11,
and the 3 November adoption of PR-12
([provisional register](provisional-rulings.md)), the follow-up
repairs, and the 23 October implementation review. The
[provisional-ruling report](reviews/provisional-rulings-2026-10-24.md)
records validation of the first six rulings on its 24 October revision.
Each dated report keeps
its own revision, source digest and outcome evidence; earlier checkpoint
measurements have not been relabeled as results of later changes.

## Follow-up repairs

### 4 November Devastate casualties — CMD-DEVASTATE-LOSSES closed

The [casualty repair](reviews/devastate-losses-2026-11-04.md) asks each affected
owner for exact physical losses, including visibility and Roman Legion choices.
All owner plans are validated before mutation; malformed/short/overlarge
supplied maps no longer silently truncate or omit losses. Non-player/default
own-piece removal now follows §8.4.1's Scouted/Revealed/Hidden priority. Legions
still go to Fallen. Terminal, preview isolation and durable later-Region
rollback/save/resume/replay are covered. Ariovistus still excludes Devastate.

**Original bundle is now 31/50 closed (62%), 19 open.** Counts measure findings,
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

Earlier verified rows below describe their tested paths, not complete coverage
of every related rule. General during-March/Battle Special Ability timing,
several Event grants, some physical casualty choices, and Interlude selections
remain incomplete. Board inspection can show the pre-SA board during later
March planning. The two existing non-player source questions remain separate.

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
| Quarters | All human factions choose relocations and payments. Complete adjacent relocation groups are validated against pre-step Control, and original visibility is preserved so arrivals cannot move again. Supply Lines use the resulting board. Invalid destinations, static-piece movement and negative payments are rejected; losses apply to the actual unpaid pieces. | `test_quarters_decisions.py`, `test_quarters_relocation_step.py` |
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

On 24/29 October and 2/3 November 2026 (America/Chicago), the owner adopted the following
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
