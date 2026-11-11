# Fourth Falling Sky comparison audit — 10 November 2026

**The audit confirmed 16 additional repair groups, 11 high and 5 medium priority.**
[Batch 1](fourth-comparison-batch1-2026-11-10.md) repairs six of them. The
earlier 50-, 21-, and 15-group ledgers are closed. The results below record
the original audit revision.

Audited Falling Sky at `b951908af2b21cc87a7e27d9a5314b3f257d0147`, Python SHA-256 `fb0bbf5af4a7513bbac1157f17054948d2ec5b3724ab612296b10a1d017ea51b` across 585 Python files. Liberty or Death was inspected at `2991ea279062773548ec390a1da75f3e85381702`. Its implementation lessons guided the search. Falling Sky's supplied references and adopted provisional rulings govern every rules conclusion.

[Finding ledger](comparison-audit-round4-2026-11-10.json) · [Reproducible evidence](comparison-audit-round4-2026-11-10-evidence.zip) · [Current status](../current-status.md)

## Method and coverage

| Comparison pattern | Fourth-pass focus |
|---|---|
| Validate the action that will actually execute | Alternate SA representations, Event Region scope, prerequisites after preceding movement |
| Preserve the complete human choice | Assembly's second SA, mandatory grants, ordered distinct beneficiaries |
| Apply the exact printed Event | Tribe/Region identity, native piece types, mandatory targets, Capability ownership |
| Forecast actual surviving forces | Counterattack bonuses after elimination, non-player Retreat decisions, Diviciacus safety |
| Apply scenario adjustments everywhere | Roman Settlement targeting, negative Roman earnings, Interlude Tribe and deck conversion |
| Trace stored effects to their consumers | Horse acquisition through real Battle, obsolete Nori through victory and Harvest, active A38 through deck construction |

Comparator material included `coin-implementation-lessons.md`, `lod_ai/engine.py`, `lod_ai/event_choices.py`, `lod_ai/util/eligibility.py`, and the lifecycle and human-mode audit documents. Six partitions produced candidate probes, followed by independent source review and reruns. The root verifier ran all ten final witness scripts against the frozen audited source. Coverage and rejected leads are retained with the evidence.

Related symptoms are grouped by repair mechanism. Druids' beneficiary and grant errors form one group. Non-player Retreat forecasting and its destination veto form one group. Interlude's two deck-exclusion errors form one group. Earlier Circumvallation persistence work is not recounted. The 16 versus 15 groups in the previous pass is not a frequency or severity trend measurement; this pass added focused bot and transition checks.

## Confirmed findings

| ID | Priority | Finding |
|---|---|---|
| FE4-01 | medium | Event-granted Battle rejects a legal Scout-before-Battle that supplies the attacker |
| FE4-02 | high | A null top-level SA plan hides the executed nested Scout from Event Region restrictions |
| FE4-03 | medium | Assembly of Gaul gives human controllers only one of the two permitted Special Abilities |
| BM4-01 | high | Motivation inflicts a Counterattack Loss after every German defender has been removed |
| BM4-02 | high | Non-player Retreat decisions use pre-Attack strength and require an unnecessary escape destination |
| BE4-01 | high | Shaded Hostages accepts mismatched Tribe/Region and a non-Gallic Ally recipient |
| BE4-02 | high | Celtic Rites applies repeated Resource losses and permits omitting its mandatory target |
| BE4-03 | high | Druids ignores beneficiary restrictions, distinctness, initiative order and mandatory Commands |
| BE4-04 | high | Shaded Germanic Horse can be gifted to a different Faction instead of the Gallic executor |
| EX4-01 | medium | Abatis accepts a missing or impossible target and silently skips mandatory marker placement |
| EX4-02 | high | Bellovaci accepts incompatible piece owner and type, omitting four mandatory troops while other effects commit |
| WS4-01 | high | Ariovistus Harvest can drive Roman Resources below zero |
| WS4-02 | high | Interlude rebuild excludes inactive Events and reinserts an active A38 Capability |
| WS4-03 | high | Interlude leaves Nori as a phantom Tribe that inflates Roman score and Harvest |
| NP4-01 | medium | Roman March target ranking omits Germanic Settlements from total Allied strength |
| NP4-02 | medium | Diviciacus safety gate turns a guaranteed safe Aedui Battle into Pass |

High marks an illegal action, material wrong effect, or inconsistent state. Medium marks a narrower missed legal choice or bot decision. These are repair priorities, not estimates of encounter frequency.

## Verification and limits

- **9,686 existing tests passed**, with no failures. One installed pytest-plugin deprecation warning is recorded.
- **Ten final witness scripts passed** the portable runner. Their assertions deliberately freeze the defects; repairs must reverse those expectations and add source-derived regressions.
- **20 audited all-bot games passed** on seeds 25–28 in all five scenarios using the second-edition card profile. Every record was checked for completion, diagnostics, census/structure, ranking, and final state identity. No nonlegal diagnostic appeared.
- **20 mixed-seat cases** on the same scenario/seed/profile matrix matched exactly under hash seeds 0 and 987, including their internal replay runs. This is 80 game executions, not 80 distinct cases. Each hash run recorded 599 human turns, 148 Event attempts, 133 executed Events, zero hard findings, and one soft partial plan.
- No new balance matrix was run. The existing passing tests and general game samples do not exercise all targeted boundaries above.

Some probes begin at ordinary complete scenario setups; others use controlled positions assembled with piece helpers. The frontend timing witness uses actual saved-session play and submission. The audit does not claim that every controlled position occurred in a sampled game. Inventory and structure checks alone do not prove source legality.

Independent review rejected two fixture assumptions before final acceptance. Controlled boards needed Provincia's permanent Fort; Assembly's second-SA witness now Builds an Ally at Helvii instead of adding a second Fort. The negative-Harvest fixture now reserves the restricted Aedui and Arverni Home Tribes for their proper owners. All corrected final probes reproduce the findings. Superseded output remains identified in the archive, and the portable runner uses only the corrected scripts.

One source question remains separate from the count: A33 Wailing Women's undefined comparison for “outnumbered” Warbands. The current formula was not declared defective. See the new question entry in `QUESTIONS.md`. WS4-01 likewise claims only that Resources cannot become negative; it does not resolve how a negative award should affect an already positive balance.

## Suggested repair order

1. **Event target validation and Resource bounds** — BE4-01, BE4-02, BE4-04, EX4-01, EX4-02, WS4-01.
2. **Free Command scope, timing and complete choices** — FE4-01, FE4-02, FE4-03, BE4-03.
3. **Battle survival forecasts and bot priorities** — BM4-01, BM4-02, NP4-01, NP4-02.
4. **Interlude deck and Tribe conversion** — WS4-02, WS4-03.

Convert each relevant witness into a rule-correct regression, run the focused checks and full suite, then perform the appropriate integrated checks in `SELFPLAY_PLAYBOOK.md`. Preserve prior failed evidence and explain any changed outcomes before updating a baseline.

## Evidence by finding

### FE4-01 — Event-granted Battle rejects a legal Scout-before-Battle that supplies the attacker

**Expected.** Assembly52 permits the controlling human Romans to Scout two Auxilia Provincia to empty-of-Romans Sequani, then Battle Belgae there, all free. Battle prerequisites apply after the preceding Scout.

**Observed.** Real saved session accepts Event52, then rejects the legal free-action response at d000008 with Battle requires the acting Faction's pieces in every selected Region. Board, RNG, pending ID and accepted journal remain unchanged. Same ordinary Command+Scout executes (2 Auxilia move, 1 of 2 Belgic Warbands dies, 2 Resources paid). Free Event control with one initially present Auxilia executes free.

**Relation to earlier work.** New free-Event timing restriction. CM3-03 closed no-attacker ordinary Battles, including an explicit positive Scout-before-Battle regression. This grant precheck is separate and rejects a legal action before simulation. Not a save-corruption finding.

**Rules.** [52 shaded grants free Command with up to two SAs (Reference Documents/Card Reference:518)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Card%20Reference#L518) · [SA may precede Command (Reference Documents/Chapter 4:13)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Chapter%204#L13) · [Scout moves Auxilia to adjacent Regions with any Command (Reference Documents/Chapter 4:69)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Chapter%204#L69) · [Roman Battle requires own and enemy Forces when selected (Reference Documents/Chapter 3:125)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Chapter%203#L125) · [Free actions retain normal procedures (Reference Documents/Chapter 5:78)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Chapter%205#L78)

**Code.** [fs_bot/engine/free_actions.py (fs_bot/engine/free_actions.py:363)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/engine/free_actions.py#L363) · [fs_bot/engine/free_actions.py (fs_bot/engine/free_actions.py:426)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/engine/free_actions.py#L426)

**Evidence.** `frontend/findings.json` and the named probe/output in the archive. Census-valid controlled Great Revolt board from build_initial_state, manually sets current52 and deck and places Roman Carnutes/Provincia forces and two Belgic Sequani Warbands using piece helpers. No altered reference files. Includes the permanent Roman Fort in Provincia required by Chapter1.

### FE4-02 — A null top-level SA plan hides the executed nested Scout from Event Region restrictions

**Expected.** Mons Cevenna follow-on Scout must originate in the March destination, Sequani. Reject a Scout from Carnutes before any Event effect commits.

**Observed.** Full public Event9 resolves March Provincia→Sequani, then Seize Sequani and Scout Carnutes→Veneti despite allowed_regions=[Sequani]. Response uses details.scout_plan=null and nested details.sa_details.scout_plan with real movement. Canonical top-level version correctly rejects atomically; legal Sequani→Mandubii control succeeds. Board census and structure remain clean.

**Relation to earlier work.** New Event SA-scope representation mismatch. Earlier XC2-01 concerned command_parts hiding multiple Limited-Command Regions; this uses null-versus-nested fallback for an actual Event-granted SA. No prior closed finding covers this lookup mismatch.

**Rules.** [Card9 follow-on Command and SA in/from destination Region (Reference Documents/Card Reference:84)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Card%20Reference#L84) · [Free Scout in a Region allows movement out of that Region (Reference Documents/Chapter 5:93)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Chapter%205#L93)

**Code.** [fs_bot/engine/free_actions.py (fs_bot/engine/free_actions.py:49)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/engine/free_actions.py#L49) · [fs_bot/engine/free_actions.py (fs_bot/engine/free_actions.py:395)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/engine/free_actions.py#L395) · [fs_bot/engine/execute.py (fs_bot/engine/execute.py:4741)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/engine/execute.py#L4741)

**Evidence.** `frontend/findings.json` and the named probe/output in the archive. Census-valid controlled Great Revolt board, current9, three Roman Auxilia in Provincia and Carnutes. Public execute_decision drives actual requests. Canonical invalid, shadow invalid, and legal control run independently. Includes the permanent Roman Fort in Provincia required by Chapter1.

### FE4-03 — Assembly of Gaul gives human controllers only one of the two permitted Special Abilities

**Expected.** A human Roman controller may Recruit then execute both Scout and Build (a Roman Ally at Helvii), each normally legal and free. Event should expose the optional second SA and its legal timing.

**Observed.** Complete public Event52 requests a single generic free Command with_sa=True, executes that Command and its one SA, then returns. No second-SA request occurs. Controlled Rome has Caesar and four Auxilia in Provincia, controls Carnutes, and can both Build a Roman Ally at Subdued Helvii in Provincia and Scout one Auxilia to Sequani after Recruit. Scout-first event finishes with moved Auxilia and Helvii still Subdued; Build-first control finishes with a Roman Helvii Ally and no moved Auxilia. Both one-SA plans validate and census stays clean.

**Relation to earlier work.** Original inventory rows base-52-original-shaded and base-52-second-edition-shaded were marked supported and claimed controller second-SA prompt, but no corresponding finding/repair exists. QUESTIONS.md 3053 and3099 explicitly justify one SA only for Non-players; this finding concerns human controllers and does not reopen that NP conclusion.

**Rules.** [52 shaded explicitly grants up to two accompanying SAs (Reference Documents/Card Reference:518)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Card%20Reference#L518) · [SA timing choice (Reference Documents/Chapter 4:13)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Chapter%204#L13) · [Build with Recruit; Caesar and supply requirements (Reference Documents/Chapter 4:43)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Chapter%204#L43) · [Scout with any Command (Reference Documents/Chapter 4:69)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Chapter%204#L69)

**Code.** [fs_bot/engine/execute.py (fs_bot/engine/execute.py:2431)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/engine/execute.py#L2431) · [fs_bot/engine/execute.py (fs_bot/engine/execute.py:951)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/engine/execute.py#L951)

**Evidence.** `frontend/findings.json` and the named probe/output in the archive. Census-valid controlled Great Revolt board from build_initial_state, current52, Romans control Carnutes, Caesar/four Auxilia in Provincia. All factions human; callback supplies one choice and is ready for another if requested. Includes the permanent Roman Fort in Provincia required by Chapter1.

### BM4-01 — Motivation inflicts a Counterattack Loss after every German defender has been removed

**Expected.** After eight Belgic Warbands inflict two halved Losses on the only two German Warbands, no German Forces survive to Counterattack; all eight Belgae survive. Motivation still adds one Loss when a German defender survives.

**Observed.** Accepted ordinary Battle kills both Germans but also one Belgic Warband. Counterattack resolver still runs on the empty defending force and Motivation adds one Loss to zero.

**Relation to earlier work.** Neither prior 50/21/15 inventories cover nonexistent German Counterattack. Prior A33 lifecycle/Retreat restrictions and EX3-04 Stalwart/Horse are different consumers and clauses.

**Rules.** [Reference Documents/Chapter 3:144-146 (§3.2.4 Step 4, surviving Defending Forces cause Counterattack Losses)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Chapter%203#L144) · [Reference Documents/Ariovistus/A Card Reference:138-144 (A33 shaded Motivation +1 Counterattack Loss)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Ariovistus/A%20Card%20Reference#L138)

**Code.** [fs_bot/battle/resolve.py:259-286](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/battle/resolve.py#L259) · [fs_bot/battle/losses.py:301-309](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/battle/losses.py#L301)

**Evidence.** `commands/findings.json` and the named probe/output in the archive. build_initial_state(Ariovistus, seed=1), all factions human, 20 Belgic Resources, 8 Belgic and 2 German Warbands at Carnutes, A33 shaded activated. All piece placements use helpers. Permanent Roman Fort explicitly placed in Provincia per §1.4.2; fixture corrected and all final witnesses rerun, outcomes unchanged.

### BM4-02 — Non-player Retreat decisions use pre-Attack strength and require an unnecessary escape destination

**Expected.** 8 Belgic Warbands attacking 6 NP Aedui with a safe Aedui-controlled Veneti destination require Aedui Retreat: a stand loses four Warbands and two survivors can inflict only one Loss, below half of four. Retreat leaves four Aedui surviving in Veneti (five including resident), all eight Belgae survive. Separately, 2 Hidden NP Aedui attacked by 4 Roman Auxilia must Retreat to save the last piece even without a legal destination, because the one surviving Hidden Warband stays in Carnutes.

**Observed.** First case stands, leaves 2 Aedui in Carnutes and inflicts only 1 Loss on Belgae. Second case stands and loses both Hidden Aedui; adding otherwise irrelevant safe Veneti control causes legal Retreat and leaves one Hidden survivor in Carnutes.

**Relation to earlier work.** Earlier BATTLE-RETREAT-CHOICES addressed human declarations/dispositions; prior Roman Legion forecast corrections concerned §8.4.3 second bullet. This finding concerns NPC third-bullet pre-casualty forecast and first-bullet destination veto.

**Rules.** [Reference Documents/Chapter 8:207-219 (§8.4.3 save last Defending piece, guarantee half the Losses, Gauls leave all Hidden Warbands when Retreating from Romans)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Chapter%208#L207) · [Reference Documents/Chapter 3:144-146 (§3.2.4 surviving Defending Forces Counterattack)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Chapter%203#L144) · [Reference Documents/Chapter 3:150-159 (§3.2.4 Retreat survivor movement and Hidden Warband/Leader exception)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Chapter%203#L150)

**Code.** [fs_bot/engine/execute.py:5457-5474](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/engine/execute.py#L5457) · [fs_bot/engine/execute.py:5526-5529](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/engine/execute.py#L5526)

**Evidence.** `commands/findings.json` and the named probe/output in the archive. Census/structurally valid controlled positions built with piece helpers. Great Revolt seed=1, only Aedui marked non-player. Carnutes/Veneti adjacent and safe destination controlled through one Aedui Warband. No saving-roll or choice uncertainty in the primary guarantee witness. Permanent Roman Fort explicitly placed in Provincia per §1.4.2; fixture corrected and all final witnesses rerun, outcomes unchanged.

### BE4-01 — Shaded Hostages accepts mismatched Tribe/Region and a non-Gallic Ally recipient

**Expected.** Card 22 shaded places a Gallic Ally and any one Warband at each of one or two Subdued Tribes in Regions containing Roman pieces. Tribe and Region must identify the same place, and the Ally must be Arverni, Aedui, or Belgic.

**Observed.** Accepted target Catuvellauni plus supplied Region Provincia allies Catuvellauni in empty Britannia to Belgae while placing the Warband in Provincia. A separate accepted Helvii target with faction Romans places a Roman Ally despite the Gallic restriction. The legal Helvii/Provincia/Belgae control places both pieces together.

**Relation to earlier work.** Earlier BE-06/07/08 Hostages work and base-piece-choices report covered unshaded physical removal/replacement choices. Original inventory base-22-*-shaded was marked supported. BE-11 was specifically 40/41/42/51. No previous closed group reported 22 shaded target geography or Ally owner.

**Rules.** [Card 22 shaded (Reference Documents/Card Reference:219)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Card%20Reference#L219) · [5.1 literal Event execution (Reference Documents/Chapter 5:5)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Chapter%205#L5)

**Code.** [fs_bot/cards/card_effects.py (fs_bot/cards/card_effects.py:1062)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/cards/card_effects.py#L1062)

**Evidence.** `base-events/findings.json` and the named probe/output in the archive. Great Revolt setup seed 4, remove Helvii Roman Ally via _unally_tribe to create legal Subdued target; Roman garrison stays in Provincia; Britannia has zero Romans.

### BE4-02 — Celtic Rites applies repeated Resource losses and permits omitting its mandatory target

**Expected.** Card 46 unshaded selects one or more distinct Gallic Factions; each selected Faction loses three Resources once and is Ineligible through next card.

**Observed.** With Arverni at 20 Resources, target_factions=[Arverni,Arverni] is accepted and reduces Resources to 14. The single-entry control leaves17. An empty list executes successfully without affecting any faction, despite legal targets.

**Relation to earlier work.** Prior BE2-02 was specifically Assembly of Gaul52 and its duplicate drain, now repaired. BE-03 concerned Celtic Rites shaded beneficiary/eligibility. Original 46 unshaded inventory rows were supported; this is a separate still-open card-specific consumer of that repeated-selection family.

**Rules.** [Card 46 unshaded (Reference Documents/Card Reference:459)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Card%20Reference#L459) · [5.1.3 mandatory attainable effects (Reference Documents/Chapter 5:52)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Chapter%205#L52)

**Code.** [fs_bot/cards/card_effects.py (fs_bot/cards/card_effects.py:1792)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/cards/card_effects.py#L1792)

**Evidence.** `base-events/findings.json` and the named probe/output in the archive. Great Revolt setup seed4; Arverni Resources set to20, all-human seats.

### BE4-03 — Druids ignores beneficiary restrictions, distinctness, initiative order and mandatory Commands

**Expected.** Card48 selects one to three distinct Gallic Factions, which execute one free Limited Command each in printed Aedui-Arverni-Belgae order. Possible Commands cannot be waived as optional.

**Observed.** An accepted Roman target gets free Recruit and places an Auxilia. Repeating Aedui gives two free Rally Commands and two new Warbands instead of the control one. [Belgae,Aedui,Arverni] executes in submitted order. Empty targets in an all-human state commit no grant; a selected Aedui can explicitly decline even though the legal control Rally is available.

**Relation to earlier work.** Original base-48 inventory rows marked supported with no finding. Earlier Command duplicate fixes govern Regions, not distinct Event beneficiaries. Council47 has explicit validators and initiative normalization but Druids48 does not. Previous BE-03 covers35/46/67/68, not48.

**Rules.** [Card48 (Reference Documents/Card Reference:478)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Card%20Reference#L478) · [5.1 and5.1.3 (Reference Documents/Chapter 5:5)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Chapter%205#L5)

**Code.** [fs_bot/cards/card_effects.py (fs_bot/cards/card_effects.py:1848)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/cards/card_effects.py#L1848) · [fs_bot/engine/execute.py (fs_bot/engine/execute.py:2065)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/engine/execute.py#L2065) · [fs_bot/engine/execute.py (fs_bot/engine/execute.py:927)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/engine/execute.py#L927)

**Evidence.** `base-events/findings.json` and the named probe/output in the archive. Unchanged Great Revolt setup seed4 with all-human seats; callback supplies a legal one-piece Recruit/Rally in own normal Region.

### BE4-04 — Shaded Germanic Horse can be gifted to a different Faction instead of the Gallic executor

**Expected.** Card59 shaded says If Gallic, take this card. The Gallic executing Faction takes it; the Event does not authorize selecting another beneficiary.

**Observed.** Belgae executing59S with faction=Aedui makes Aedui the recorded owner. Roman executor can also award it to Aedui. A subsequent ordinary Aedui Battle with four Warbands removes four of eight German Warbands. The legal Belgic self-acquisition control removes only two in the same Aedui Battle.

**Relation to earlier work.** BE-09 and Horse5November repairs cover owner-scoped Battle Region decisions, activation timing, and Fort/Abatis limits. EX3-04 covers Stalwart cancellation. Neither covers how59S is acquired. Original inventory correctly described If Gallic executor takes Capability, but tied its reported gap to BE-09 Region choice only.

**Rules.** [Card59 shaded and combat Tip (Reference Documents/Card Reference:602)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Card%20Reference#L602) · [5.1 literal Event recipient (Reference Documents/Chapter 5:5)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Chapter%205#L5)

**Code.** [fs_bot/cards/card_effects.py (fs_bot/cards/card_effects.py:2162)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/cards/card_effects.py#L2162)

**Evidence.** `base-events/findings.json` and the named probe/output in the archive. Great Revolt setup seed4; use Available pools to place4 Aedui and8 German Warbands at Pictones; all-human seats. Base Germans do not Retreat.

### EX4-01 — Abatis accepts a missing or impossible target and silently skips mandatory marker placement

**Expected.** When own Warbands exist, a human A64 Event must select one qualifying Region and place the marker. Missing or ineligible authored selection must be rejected or remain pending.

**Observed.** Unmodified Ariovistus setup has two Aedui Warbands in Aedui. A64 unshaded by Aedui with {} or region Provincia passes durable response validation and action preview, executes successfully, and leaves no Abatis marker. The Aedui-region control places the marker.

**Relation to earlier work.** EX2-01 corrected recognition of Scouted Warbands at a valid target. It did not validate the mandatory Region selection. Original EXP-09 covered A29U/A30U/A36S/A43U/A45U, not A64. This witness uses ordinary Hidden Warbands and no source ambiguity.

**Rules.** [A64 mandatory marker at a Region with an own Warband (Reference Documents/Ariovistus/A Card Reference:288)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Ariovistus/A%20Card%20Reference#L288) · [5.1 selections and 5.1.3 mandatory possible partial execution (Reference Documents/Chapter 5:5)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Chapter%205#L5)

**Code.** [fs_bot/cards/card_effects.py (fs_bot/cards/card_effects.py:3663)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/cards/card_effects.py#L3663) · [fs_bot/tools/seat_session.py (fs_bot/tools/seat_session.py:88)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/tools/seat_session.py#L88)

**Evidence.** `expansion/findings.json` and the named probe/output in the archive. setup_scenario(Ariovistus, seed=317), human seats; current card A64, next A67; board pieces unchanged

**Limit.** Observed unshaded path; handler is identical for either side of this single-text Event. No whole-game frequency claim.

### EX4-02 — Bellovaci accepts incompatible piece owner and type, omitting four mandatory troops while other effects commit

**Expected.** A69 must use a real mobile force pairing: Roman Auxilia or Aedui Warbands, carrying out the four-piece placement as far as possible. An impossible owner/type pair is not a legal player selection and must not commit partial Event effects.

**Observed.** Unmodified Ariovistus setup has 11 Roman Auxilia and 17 Aedui Warbands Available. A69U parameters piece_faction=Romans,piece_type=Warband or piece_faction=Aedui,piece_type=Auxilia pass durable validation and preview and execute. One Belgic Warband is removed and Bellovaci changes from Belgae to Romans, but no mobile pieces are placed. The matching Roman/Auxilia and Aedui/Warband controls each place four.

**Relation to earlier work.** The earlier A35/A51/A69 type-allowlist repair rejected structural piece types and forbidden faction values individually (QUESTIONS.md 1909-1916). It never checked native owner/type compatibility. EXP-11 covered A69 exact Belgic removals. EX2-04 mandatory quota fixes covered A30/A56/A65, not this A69 path.

**Rules.** [A69 unshaded mandatory placements (Reference Documents/Ariovistus/A Card Reference:316)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Ariovistus/A%20Card%20Reference#L316) · [1.4 identifies Roman Auxilia versus Gallic/Germanic Warbands and availability limits (Reference Documents/Chapter 1:80)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Chapter%201#L80) · [5.1 legal selections and 5.1.3 carry out possible text (Reference Documents/Chapter 5:5)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Chapter%205#L5)

**Code.** [fs_bot/cards/card_effects.py (fs_bot/cards/card_effects.py:3778)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/cards/card_effects.py#L3778)

**Evidence.** `expansion/findings.json` and the named probe/output in the archive. setup_scenario(Ariovistus, seed=317), human seats; current card A69, next A67; board pieces unchanged

**Limit.** Typed durable/API Event plans demonstrated. CLI cross-field menus were not claimed to generate these invalid pairs.

### WS4-01 — Ariovistus Harvest can drive Roman Resources below zero

**Expected.** Roman Resources must remain within 0–45 even when the Ariovistus Roman victory formula is negative. This finding requires a nonnegative result and does not decide whether negative earnings may reduce a positive balance.

**Observed.** A valid board with 26 non-Roman Allies and 6 Settlements has Roman victory -2 and no faction passing victory. Public harvest_phase changes starting Roman Resources0 to-2 and1 to-1. Public run_winter_round with no relocations also ends at-2 and a structural error. Removing all Settlements produces score4, Resources4, clean structure.

**Relation to earlier work.** WS3-01 repaired counting physical Gallic Allies/Citadels. This is a distinct Ariovistus Roman negative-score boundary and missing Resource floor; absent from all earlier ledgers.

**Rules.** [§1.8 Resources between0 and45 at any moment (Reference Documents/Chapter 1:212)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Chapter%201#L212) · [A6.4.1 Harvest equals Roman victory (Reference Documents/Ariovistus/Chapter A6:143)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Ariovistus/Chapter%20A6#L143) · [A7.2 subtract Settlements (Reference Documents/Ariovistus/Chapter A7:7)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Ariovistus/Chapter%20A7#L7)

**Code.** [fs_bot/engine/winter.py (fs_bot/engine/winter.py:639)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/engine/winter.py#L639) · [fs_bot/engine/winter.py (fs_bot/engine/winter.py:683)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/engine/winter.py#L683)

**Evidence.** `seasonal/findings.json` and the named probe/output in the archive. Built from initialized Ariovistus state with legal piece helpers and matching Tribe records.26 non-Roman Allied Tribes,6 Settlements and enough Romans to prevent Belgic victory. All leaders/pools accounted. Census/structure clean; no winner before full Winter. Corrected after independent review to reserve Aedui and Arverni Tribes for their own factions, with an explicit TRIBE_FACTION_RESTRICTION assertion for every placement. Corrected fixture reproduces all outcomes. Initial illegal ownership fixture is retained under superseded filenames and is not accepted evidence.

### WS4-02 — Interlude rebuild excludes inactive Events and reinserts an active A38 Capability

**Expected.** Keep each in-effect Capability outside the new deck, including substituted A38. Gallia Togata and Colony are excluded for their in-effect status; otherwise remain in the shuffled Event pool.

**Observed.** Executing A38 unshaded and running the complete Interlude retains A38 as active and adds one A38 to the new deck. With no active Gallia Togata/Colony, both5 and71 are always excluded. InactiveA38 is included once and active numeric8 is excluded correctly. Ordinary Pax setup seed21 includes inactive5 and71.

**Relation to earlier work.** Earlier repair covered which replacement identity is used, A38 versusO38, and Capability registry/side lifecycle. It did not exclude the already active substituted card or condition5/71 exclusion. Related deck membership symptoms grouped once.

**Rules.** [Lingering Events and Deck, explicitly useA38 and keep in-effect cards outside deck (Reference Documents/Ariovistus/A Scenario - The Gallic War:110)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Ariovistus/A%20Scenario%20-%20The%20Gallic%20War#L110) · [Shuffle Event cards, deal specified piles, set remaining aside (Reference Documents/Setup:21)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Setup#L21) · [Deal70 Events (Reference Documents/Scenario - Pax Gallica:19)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Scenario%20-%20Pax%20Gallica#L19)

**Code.** [fs_bot/engine/interlude.py (fs_bot/engine/interlude.py:1364)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/engine/interlude.py#L1364)

**Evidence.** `seasonal/findings.json` and the named probe/output in the archive. Untouched Gallic War setup seed21; all four seats marked NPC for normal Interlude choices; execute Capability by production Event API, then run_interlude(britannia_decision=False). Census/structure clean before and after.

### WS4-03 — Interlude leaves Nori as a phantom Tribe that inflates Roman score and Harvest

**Expected.** Remove Nori when returning to original geography and add Catuvellauni. Without Colony there must be30 real Tribes. Roman score follows30 minus non-Roman Allies and Citadels.

**Observed.** Full Interlude from valid Gallic War setup21 retains SubduedNori and adds Catuvellauni, yielding31 Tribe entries without Colony. Roman score and next Harvest are24; the printed physical-piece oracle is30 minus7=23. Removing only the obsoleteNori record in a diagnostic clone yields score/Harvest23. Both bad and corrected states pass current census/structure validators.

**Relation to earlier work.** Different mechanism from XC3-01 dynamic Colony consumers. This removes an obsolete expansion Tribe at scenario transition; no Colony exists in the witness. Earlier Interlude choices/marker reports did not count this.

**Rules.** [Markers remove NoriTribe (Reference Documents/Ariovistus/A Scenario - The Gallic War:86)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Ariovistus/A%20Scenario%20-%20The%20Gallic%20War#L86) · [Original Falling Sky rules in second half (Reference Documents/Ariovistus/A Scenario - The Gallic War:126)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Ariovistus/A%20Scenario%20-%20The%20Gallic%20War#L126) · [§7.2 physical score shortcut,30 Tribes unlessColony (Reference Documents/Chapter 7:28)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Chapter%207#L28) · [§6.4.1 Harvest from Roman score (Reference Documents/Chapter 6:100)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Chapter%206#L100)

**Code.** [fs_bot/engine/interlude.py (fs_bot/engine/interlude.py:1140)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/engine/interlude.py#L1140) · [fs_bot/engine/interlude.py (fs_bot/engine/interlude.py:1532)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/engine/interlude.py#L1532) · [fs_bot/engine/victory.py (fs_bot/engine/victory.py:112)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/engine/victory.py#L112)

**Evidence.** `seasonal/findings.json` and the named probe/output in the archive. Untouched Gallic War setup21, all seats NPC; full production run_interlude with expedition declined. No Gallia Togata or Colony. Census/structure clean on both sides.

### NP4-01 — Roman March target ranking omits Germanic Settlements from total Allied strength

**Expected.** In Ariovistus, all Settlements count as Allies for Roman Battle/March conditions and priorities. With a tier-four die roll, Germans with one Ally plus two Settlements outrank Aedui with two Allies.

**Observed.** A census/structure-valid seed-5 initialized position reaches Roman March through the complete public bot dispatcher. It chooses Carnutes/Aedui and moves all four Roman Legions there. German total_ac is one although it should be three. Replacing the two Settlements by two physical Allies makes the same dispatcher choose Germans. With only the one German Ally, the Aedui choice is correct.

**Relation to earlier work.** Not in original 50 or second/third comparison ledgers. Unlike WS3-01 Harvest or XC3-01 Colony consumers, this is a scenario-specific Settlement-as-Ally rule in Roman bot strategic targeting. Local Settlement recognition already works.

**Rules.** [A8.8.1 (Reference Documents/Ariovistus/Chapter A8:251)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Ariovistus/Chapter%20A8#L251) · [8.8.1 (Reference Documents/Chapter 8:848)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Chapter%208#L848) · [8.8.3 (Reference Documents/Chapter 8:939)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Chapter%208#L939)

**Code.** [fs_bot/bots/roman_bot.py (fs_bot/bots/roman_bot.py:346)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/bots/roman_bot.py#L346) · [fs_bot/bots/bot_common.py (fs_bot/bots/bot_common.py:1066)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/bots/bot_common.py#L1066)

**Evidence.** `bots-review/findings.json` and the named probe/output in the archive. Controlled initialized Ariovistus board using canonical piece helpers, valid physical inventory and Tribe structures before and after. No claim of naturally sampled reach. Final accepted fixtures include the permanent Roman Fort in Provincia per Chapter 1:122–124.

**Limit.** Dynamically confirmed for tier-four Roman March. The same generic helper is used by Roman Battle ranking, but that additional path is static corroboration only. Do not globally add Settlements for every consumer without each consumer source rule.

### NP4-02 — Diviciacus safety gate turns a guaranteed safe Aedui Battle into Pass

**Expected.** A lone Diviciacus in Carnutes with a Belgic Ally and ten Aedui Resources must Battle after declining/no access to Event. The Leader inflicts one Loss and the Ally has zero Counterattack. Diviciacus cannot take a Loss.

**Observed.** node_a4 recognizes the guaranteed high-value Loss, but dispatch_bot_turn returns Pass. Executing the ordinary source-required Battle through execute_decision removes the Belgic Ally and leaves Diviciacus alive, with clean census/structure. Adding one Aedui Warband makes the complete bot dispatcher select Battle.

**Relation to earlier work.** Not in prior 50/21/15 ledgers. Separate from current commands agent Retreat forecast group: this is active Aedui bot Battle selection with Diviciacus, no Retreat or uncertain rolls and no enemy troops.

**Rules.** [8.6.2 (Reference Documents/Chapter 8:448)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Chapter%208#L448) · [A8.6.2 (Reference Documents/Ariovistus/Chapter A8:53)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Ariovistus/Chapter%20A8#L53) · [A3.2.4 (Reference Documents/Ariovistus/Chapter A3:63)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/Reference%20Documents/Ariovistus/Chapter%20A3#L63)

**Code.** [fs_bot/bots/aedui_bot.py (fs_bot/bots/aedui_bot.py:707)](https://github.com/FeeSimple1/fs-bot/blob/b951908af2b21cc87a7e27d9a5314b3f257d0147/fs_bot/bots/aedui_bot.py#L707)

**Evidence.** `bots-review/findings.json` and the named probe/output in the archive. Controlled initialized Ariovistus board using canonical piece helpers and named Tribe allegiance, valid census and structure before/after the legal Battle. Final accepted fixtures include the permanent Roman Fort in Provincia per Chapter 1:122–124.

**Limit.** Dynamically confirmed for zero counterattack Losses/zero supporting troops. Other equality and unrelated-enemy safety cases remain uncounted.

