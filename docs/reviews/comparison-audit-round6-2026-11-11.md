# Sixth Falling Sky comparison audit — 11 November 2026

**The audit found 14 new repair groups, 7 high and 7 medium priority.** Batch 1
closed BE6-01 through BE6-03. Batch 2 closed WS6-01 through WS6-03. Batch 3
closed BM6-01 through BM6-03, leaving five open.
[Batch 1 repairs and validation](sixth-comparison-batch1-2026-11-11.md) ·
[Batch 2 repairs and validation](sixth-comparison-batch2-2026-11-11.md) ·
[Batch 3 repairs and validation](sixth-comparison-batch3-2026-11-11.md)

Audited Falling Sky commit: `86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad`. Python-source SHA-256: `2423cb1f410650da300914e6569c1637675894cc43a9bd8284dfd92bd3b3ecb7` across 596 files. Liberty or Death was inspected at `2991ea279062773548ec390a1da75f3e85381702`. Its implementation patterns guided the search; Falling Sky's supplied references and thirteen adopted provisional rulings govern the findings.

[Finding ledger](comparison-audit-round6-2026-11-11.json) · [Portable evidence](comparison-audit-round6-2026-11-11-evidence.zip) · [Current status](../current-status.md)

## Method and coverage

| Comparison pattern | Sixth-pass checks |
|---|---|
| Scheduled actions preserve ordinary rules | German phase Rally quotas, original March groups, destination priorities, Battle effects |
| Parallel forecasts match real execution | Surviving defenders, named leaders, forced target losses, Rampage legality and capacity |
| Free actions retain all unmodified restrictions | Aedui Ambush limit and expansion Enlist group choices |
| Stored effects reach every consumer | Both sides of German Phalanx, pre-Battle fire and automatic Battles |
| Bot Event plans cause the prescribed gains | Mandatory human effects, derived NPC parameters, ineffective-Event rejection |

Five partitions investigated candidates, followed by independent source review, fixture checks, duplicate screening and reruns. Root independently reran all seven final scripts and checked their recorded JSON. The comparator material includes `coin-implementation-lessons.md`, `docs/human_mode_audit.md`, `docs/audit_set_but_never_applied_s76.md` and `lod_ai/event_choices.py`.

Related symptoms share a repair group. Remaining German Phalanx consumers are grouped together; A35/A60 bot parameters form one group; Belgic/Arverni comparative forecasts form one group; Arverni/Aedui forced-target guarantees form one group. Earlier corrections are not reopened merely because another independent consumer remains wrong.

## Confirmed findings

| ID | Priority | Finding |
|---|---|---|
| BE6-01 | high | Shaded Land of Mist and Mystery skips mandatory removal and Ally placement while granting Warbands |
| BE6-02 | medium | Non-player Event execution omits A35 and A60 placement/replacement parameters |
| BE6-03 | medium | Belgae choose ineffective Flight of Ambiorix when named Ambiorix is already on the map |
| FE6-01 | high | Event-granted Aedui Battle accepts Ambush in multiple Regions |
| FE6-02 | medium | Ariovistus Enlist March cannot divide four Warbands into multiple destination groups |
| BM6-01 | high | German Phalanx still misses shaded Legio X protection and Slingers initial fire |
| BM6-02 | high | Alternate German Ambush paths bypass Balearic Slingers |
| BM6-03 | high | Consuetudine Battles multiple defenders in the same Region |
| NP6-01 | medium | Belgic and Arverni offensive Battle forecasts still use pre-Attack defenders and miss Ambiorix strength |
| NP6-02 | medium | Arverni and Aedui high-value Battle triggers mistake target presence for a forced Loss |
| NP6-03 | medium | Roman threat gate caps Rampage at two victims and treats impossible Rampages as threats |
| WS6-01 | high | Germans Phase Rally places multiple Allies in one Region and compounds their Warband gain |
| WS6-02 | high | Germans Phase March moves arriving Warbands a second time |
| WS6-03 | medium | Germans Phase March omits player-Control priority among newly controllable destinations |

High means an illegal action or material wrong effect. Medium means a missed legal choice or incorrect bot decision. Priority does not estimate encounter frequency. The group count is not a comparable defect-rate measurement across audits because their focused paths differ.

## Validation and limits

- **9,900 tests passed**, with no failures or skips; the existing suite was unchanged. The independent reviewer also reran 94 fifth-round regression cases successfully.
- **Seven final witness scripts reproduced their observations and matched the recorded JSON.** They intentionally assert the current defects and include legal controls. Repairs must turn the observations into source-correct regressions.
- **20 audited bot games passed**: second-edition seeds 41–44 in all five scenarios. Every requested record has completed game/audit flags, clean inventory and structure, a four-faction engine ranking, no errors, and no diagnostics beyond legal declines. One game reached the Interlude.
- **20 mixed-player cases matched byte-for-byte across hash seeds 0 and 987**, with replay enabled: 80 executions of 20 distinct cases. Each hash run recorded 534 human turns, 152 Event attempts, 139 executed Events, zero hard findings and one soft partial plan.
- No fresh balance matrix was run; no baseline was changed. Code, tests, supplied references and canonical constants remain unchanged.

Passing broad tests and sample games do not exercise every targeted boundary. Most witnesses are controlled positions assembled with canonical piece helpers; some use actual scenario setups with a selected current Event. Each discloses its scope and includes applicable census/structure checks, permanent Provincia Fort and physical ownership. No sampled encounter frequency is claimed.

The base-game Enlist split-group lead was rejected because §3.4.2 expressly allows one moving group; the confirmed omission is expansion-only. An early Flight of Ambiorix probe used Great Revolt's Successor and was corrected to the actual named Ambiorix in Pax Gallica before acceptance. Other unverified Event applicability and Capability combinations remain uncounted. Existing source questions, including Optimates/Pax Gallica, remain separate.

## Suggested repair order

| Batch | Scope | Findings |
|---|---|---|
| 1 | Event completeness and bot Event decisions | BE6-01, BE6-02, BE6-03 |
| 2 | Automatic German Rally and March | WS6-01, WS6-02, WS6-03 |
| 3 | Battle Capability integration and repeated targets | BM6-01, BM6-02, BM6-03 |
| 4 | Free-action legality and Enlist choices | FE6-01, FE6-02 |
| 5 | Bot loss forecasts, target guarantees and Rampage threats | NP6-01, NP6-02, NP6-03 |

## Finding evidence

### BE6-01 — Shaded Land of Mist and Mystery skips mandatory removal and Ally placement while granting Warbands

**Expected:** An implementable removal and post-removal Gallic Ally placement must both occur; absent required choices must not permit the later optional grant to commit.

**Observed:** Event succeeds; Roman Ally remains, requested replacement cannot occur, and 1 Belgic Warband is placed; Event succeeds; Roman Ally is removed, Catuvellauni remains Subdued, and 1 Belgic Warband is placed; Event succeeds; Roman Ally remains and 1 Belgic Warband is placed.

**Cause:** The shaded handler takes optional removal and Ally parameters, skips absent/invalid Ally selections, then places the selected Warbands. remove_target(None) silently returns even when removal_options is nonempty.

**Sources:** [Reference Documents/Card Reference:577](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Card%20Reference#L577); [Reference Documents/Chapter 5:52](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%205#L52).

**Implementation:** [fs_bot/cards/card_effects.py:2103](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/cards/card_effects.py#L2103); [fs_bot/cards/land_of_mist.py:25](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/cards/land_of_mist.py#L25).

**Controls:** For each exact same starting board, supplying removal=Catuvellauni, ally_tribe=Catuvellauni, ally_faction=Belgae and the same Warband choice removes the Roman Ally and places the Belgic Ally plus 1 Warband. All post-state oracles pass.

**Earlier audit distinction:** Original BE-08 concerned unrepresentable CLI Event parameter shapes; its 6 November numeric57 repair supplied structured removal and legal post-removal menus. This finding is the surviving engine mandatory-effect guard. EX2-04 enumerates A30 shaded, A56 shaded and A65 shaded quotas only; BE2-03 concerns Remi Influence 68 unshaded. Neither reports numeric57 omission. This is a separate card/handler occurrence, not reopening those IDs.

**Evidence:** `PYTHONPATH=<fs-bot-root> python events/probe_events.py`; `events/probe_events-output.json`.

**Fixture and limits:** Sparse census-valid Great Revolt board, permanent Provincia Fort, a Roman Ally at Catuvellauni in Britannia, complete Available Belgic Ally/Warband supply. No claim of a naturally reached game transcript. Only witnessed cards and paths are confirmed; no natural-play frequency or exhaustive scenario/edition coverage claim.

### BE6-02 — Non-player Event execution omits A35 and A60 placement/replacement parameters

**Expected:** Non-player choice generation must implement the maximized own gains required by the Event priorities and the explicit full-Auxilia Roman instruction. Human up-to choices remain optional.

**Observed:** Bot chooses shaded Event; execution succeeds with all recorded material game state unchanged; Bot chooses unshaded Event; execution places Roman Ally at Treveri and zero Auxilia; Bot chooses shaded Event; execution succeeds without replacing any piece.

**Cause:** A bot receives _derive_event_params output, with absent derivation converted to an empty dict. A35 and A60 have neither a registered deriver nor support in the routed card planner modules. A35 unshaded defaults to Roman Warbands when executed by Romans; shaded defaults placements to []. A60 shaded defaults replacements to [].

**Sources:** [Reference Documents/Ariovistus/A Card Reference:152](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Ariovistus/A%20Card%20Reference#L152); [Reference Documents/Ariovistus/A Card Reference:272](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Ariovistus/A%20Card%20Reference#L272); [Reference Documents/Ariovistus/roman_bot_event_instructions_ariovistus.txt:31](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Ariovistus/roman_bot_event_instructions_ariovistus.txt#L31); [Reference Documents/Chapter 8:129](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%208#L129); [Reference Documents/Chapter 8:149](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%208#L149).

**Implementation:** [fs_bot/engine/execute.py:3447](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/engine/execute.py#L3447); [fs_bot/engine/execute.py:5936](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/engine/execute.py#L5936); [fs_bot/cards/card_effects.py:3185](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/cards/card_effects.py#L3185); [fs_bot/cards/card_effects.py:3583](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/cards/card_effects.py#L3583).

**Controls:** On the identical physical board, a complete legal player-authored placement plan places the seven Available German Warbands and one Settlement at Treveri; On the identical starting board, explicit Roman beneficiary/Auxilia/count4 places the same Ally and four Auxilia; On the identical starting board, five explicit replacements convert the Ally and four Auxilia to the Belgic Ally and four Warbands.

**Earlier audit distinction:** Original EXP-08 repaired human up-to choices/refunds including A60 unshaded, not shaded non-player plans. EXP-09 repaired the enumerated expansion placement limits. EX3-03 repaired A35 unshaded Dispersed/Gathering marker replacement, not non-player choice generation. Grouping these three cases reflects one producer-to-consumer parameter seam; no additional cards inferred.

**Evidence:** `PYTHONPATH=<fs-bot-root> python events/probe_events.py`; `events/probe_events-output.json`.

**Fixture and limits:** Physical Ariovistus setup_scenario(seed=1), active factions marked non-player, current card A35 injected. Seven German Warbands Available, legal Settlement space and pool; Sparse census-valid Ariovistus board with full Roman Auxilia supply and legal Treveri Ally placement, permanent Provincia Fort; Sparse census-valid Ariovistus board with Roman Ally at Remi and four Hidden Roman Auxilia in Atrebates, ample Available Belgic replacement pieces and permanent Provincia Fort. Only witnessed cards and paths are confirmed; no natural-play frequency or exhaustive scenario/edition coverage claim.

### BE6-03 — Belgae choose ineffective Flight of Ambiorix when named Ambiorix is already on the map

**Expected:** Decline the ineffective Event and follow the Command/Special Ability flowchart, exactly as the printed 8.1.1 example specifies.

**Observed:** should_decline_event returns False; dispatcher selects shaded Flight of Ambiorix; execute_decision reports success with all recorded material game state unchanged.

**Cause:** PLACES_LEADER returns effective unconditionally. Decline logic trusts card-specific availability and generic effectiveness; no card56 guard corrects the unconditional result. Execution target helper already correctly distinguishes an on-map named Leader from a missing Leader or Successor; availability does not reuse the distinction.

**Sources:** [Reference Documents/Chapter 8:30](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%208#L30); [Reference Documents/Card Reference:567](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Card%20Reference#L567).

**Implementation:** [fs_bot/cards/event_eval.py:1149](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/cards/event_eval.py#L1149); [fs_bot/bots/bot_common.py:369](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/bots/bot_common.py#L369); [fs_bot/cards/event_targets.py:77](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/cards/event_targets.py#L77).

**Controls:** Removing the named Leader using remove_piece on the same board makes the selected Event restore named Ambiorix and change material state. On the original physical board with Event access disabled, the dispatcher returns Rally rather than Event or Pass, demonstrating an available command fallback. Every initial/completed state passes pool and structure checks.

**Earlier audit distinction:** BE2-05 repaired shaded Flight execution for an on-map Successor and forbade illegal return destinations; BE2-06 repaired unshaded Belgic victory counting. This finding concerns the non-player availability consumer with named Ambiorix already present, a different path. EX2-05 is Kinship and is unrelated.

**Evidence:** `PYTHONPATH=<fs-bot-root> python events/probe_events.py`; `events/probe_events-output.json`.

**Fixture and limits:** Physical Pax Gallica setup_scenario(seed=1), named Ambiorix at Nervii, active factions non-player, current card56 injected and can_play_event=True. Only witnessed cards and paths are confirmed; no natural-play frequency or exhaustive scenario/edition coverage claim.

### FE6-01 — Event-granted Aedui Battle accepts Ambush in multiple Regions

**Expected:** Aedui may Ambush in only one Region per Battle Command, including Assembly of Gaul’s free Command; both ordinary and Event interfaces must reject a two-Region Ambush before it executes.

**Observed:** Card 52 shaded accepts a human single-SA plan with Ambush in Carnutes and Mandubii. Each Region begins with six Hidden Aedui and five Revealed Belgae. Both finish at six Aedui/two Belgae, avoiding the second Region’s otherwise required one-Warband Counterattack loss. The one-Ambush control finishes Mandubii at five Aedui/two Belgae. The ordinary Command+SA validator and Assembly’s two-ability schema both reject the same excessive Ambush scope.

**Cause:** free_actions._plan_structure_error checks Aedui Ambush scope only for Morasses; its generic free Command+SA route omits the normal action validator’s one-Region guard. _execute_battle validates each Ambush locally without enforcing the Command-wide cap.

**Sources:** [Reference Documents/Chapter 4:188](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%204#L188); [Reference Documents/Card Reference:521](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Card%20Reference#L521); [Reference Documents/Card Reference:523](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Card%20Reference#L523); [Reference Documents/Chapter 3:15](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%203#L15).

**Implementation:** [fs_bot/engine/free_actions.py:358](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/engine/free_actions.py#L358); [fs_bot/engine/free_actions.py:375](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/engine/free_actions.py#L375); [fs_bot/engine/action_validation.py:463](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/engine/action_validation.py#L463); [fs_bot/cards/assembly_of_gaul.py:102](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/cards/assembly_of_gaul.py#L102); [fs_bot/engine/execute.py:3996](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/engine/execute.py#L3996).

**Controls:** Same two-Region plan is rejected unchanged under an ordinary Command+SA. Assembly two-ability schema also rejects it. One-Ambush free Battle succeeds and incurs the expected second-Battle Counterattack loss. Durable SeatSession pauses before the grant, accepts the illegal response after save/load, and replays identically with board/RNG equality. Preview leaves live state/RNG untouched.

**Earlier audit distinction:** FE4-03 exposed only one of Assembly’s two allowed abilities and was fixed by the new multi-ability schema. FE5-01 covered Britannia crossing with an accompanying SA. This is a separate Aedui-specific Command-wide Battle cap in the still-supported single-ability Event response.

**Evidence:** `PYTHONPATH=<fs-bot-root> python frontend/probe_frontend.py`; `frontend/probe_frontend-output.json`.

**Fixture and limits:** Controlled Great Revolt seed4 second-edition position using build_initial_state and place_piece; permanent Provincia Fort retained, six Aedui versus five Revealed Belgae in each of two Regions, Aedui Control Carnutes. Pre/post census and structural integrity clean. No NPC decisions or stochastic hard-piece saves needed. Defenders explicitly choose to stand in legal normal-Battle control. Confirmed for numeric52 shaded single-ability human response. No claimed encounter frequency; no claim that NPC Aedui choose this illegal plan.

### FE6-02 — Ariovistus Enlist March cannot divide four Warbands into multiple destination groups

**Expected:** Ariovistus Enlist’s one free German Limited March may select one origin and split its total of at most four affected Warbands into different groups bound for different adjacent Regions, following A3.4.2 and §3.3.2.

**Observed:** The production Enlist collector asks for exactly one origin and destination, then one total/visibility allocation, and returns. execute_free_enlist invokes march_group exactly once with all selected Warbands. Four Germans in Sugambri can be sent entirely to Nervii or partly left behind, but cannot be divided two to Nervii and two to Treveri in the free Command. On the identical Ariovistus board, a public ordinary German Limited Command supports and executes that exact 2+2 split with clean integrity.

**Cause:** enlist_free.py unconditionally retains the base-game one-moving-group schema and implementation for Ariovistus. Its CLI likewise has no group/destination list or continuation. The base single-group rule is replaced by A3.4.2 in the expansion.

**Sources:** [Reference Documents/Ariovistus/Chapter A3:108](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Ariovistus/Chapter%20A3#L108); [Reference Documents/Chapter 3:249](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%203#L249); [Reference Documents/Chapter 3:250](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%203#L250); [Reference Documents/Chapter 4:215](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%204#L215); [Reference Documents/Ariovistus/Chapter A4:43](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Ariovistus/Chapter%20A4#L43); [Reference Documents/Chapter 3:354](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%203#L354).

**Implementation:** [fs_bot/commands/enlist_free.py:83](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/commands/enlist_free.py#L83); [fs_bot/commands/enlist_free.py:98](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/commands/enlist_free.py#L98); [fs_bot/cli/human_plan.py:817](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/cli/human_plan.py#L817); [fs_bot/cli/human_plan.py:831](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/cli/human_plan.py#L831).

**Controls:** Base Great Revolt version uses Ambiorix and correctly permits one group only under §3.4.2. Ariovistus public German Limited March moves two each to Nervii/Treveri. Production terminal collection returns after one destination/total. Both actual Enlist cases execute cleanly and send all selected Germans to the single destination.

**Earlier audit distinction:** Original human-choice inventory SA-ENLIST-FREE verified Rally/Raid and explicitly delegated March/Battle internals. Earlier ledgers address borrowed-force identities and Event-granted transit drop-offs, not Ariovistus’s multiple groups within the free Enlist subcommand. No matching open/closed issue found in rounds1–5.

**Evidence:** `PYTHONPATH=<fs-bot-root> python frontend/probe_enlist.py`; `frontend/probe_enlist-output.json`.

**Fixture and limits:** Controlled Ariovistus seed7 position built with piece helpers: permanent Provincia Fort, Belgic Boduognatus/one Belgic Warband at Sugambri, four Hidden Germans there; no German Leader/Settlement present and both destinations empty. Full public Belgic Raid+Enlist executes the terminal-collected single-destination plan. Comparison ordinary German Limited March uses one origin and exactly four Warbands. Pre/post census/structure clean. This is a legal-choice omission demonstrated by the production menu/consumed schema and a source-backed same-board legal split control, not a claim that arbitrary unsupported input must be accepted. It applies only to Ariovistus; base single-group behavior is correct. No frequency estimate or durable replay defect claimed.

### BM6-01 — German Phalanx still misses shaded Legio X protection and Slingers initial fire

**Expected:** A31 unshaded played after shaded card 15 must cancel the benefit to German defenders: Caesar plus two Legions inflicts five Losses, leaving three of eight German Warbands. A31 shaded played after card 13 unshaded must cancel its harmful initial fire on German attackers: four German Warbands then remove two Roman Auxilia and all four Germans survive.

**Observed:** The accepted Roman Battle predicts and inflicts only four Losses whether Inflexible is present or absent; four Germans survive. The control without card 15 inflicts five. The accepted German Battle with Stalwart and Slingers still loses one German before Attack, removes only one Auxilia and ends with three Germans and one Auxilia, exactly as without Stalwart; without card 13, four Germans and no Auxilia survive. Adding card 59 unshaded makes the still-uncancelled initial fire remove two Germans. Non-German Belgic controls correctly retain the effects of card 15 shaded and card 13 unshaded.

**Cause:** Both Attack calculators apply shaded 15 Caesar limitation without inspecting A31 unshaded cancellation. execute.py computes and resolves card 13 initial Losses (and its card 59 combined rate) without inspecting A31 shaded. Existing A31 support is manually distributed among individual consumers.

**Sources:** [Reference Documents/Ariovistus/A Card Reference:127](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Ariovistus/A%20Card%20Reference#L127); [Reference Documents/Ariovistus/A Card Reference:131](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Ariovistus/A%20Card%20Reference#L131); [Reference Documents/Card Reference:147](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Card%20Reference#L147); [Reference Documents/Card Reference:125](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Card%20Reference#L125); [QUESTIONS.md:2859](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/QUESTIONS.md#L2859).

**Implementation:** [fs_bot/battle/losses.py:192](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/battle/losses.py#L192); [fs_bot/battle/resolve.py:418](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/battle/resolve.py#L418); [fs_bot/engine/execute.py:4031](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/engine/execute.py#L4031).

**Controls:** Four shaded-Legio cases and five Slingers cases; A31 acquired last when present to avoid any played-later precedence question. All four involved cards are verified members of Ariovistus deck. Both ordinary calculation and live casualty prompts included.

**Earlier audit distinction:** EX3-04 fixed card 59 ordinary Battle doubling. BM5-01 fixed card 15 UNSHADED final +2 and -1 modifiers vs A31 SHADED. This witness uses card 15 SHADED Caesar limitation vs A31 UNSHADED, plus card 13 initial fire and its card 59 combination. These are newly confirmed consumers after those fixes, grouped once for Phalanx cancellation rather than separate counts per clause.

**Evidence:** `battle/probe_battle.py`; `battle/probe_battle-output.json`.

**Fixture and limits:** Controlled build_initial_state positions, canonical piece helpers, permanent Provincia Fort retained, human seats except scenario game-run factions, actual execute_decision Event acquisition. Census and structural checks empty before/after each witness. These are legal constructed positions, not sampled encounter-frequency claims. No new claim for card 27 across Interlude or every possible Event interaction. The extra card 59 row is one prefire variant, not another finding.

### BM6-02 — Alternate German Ambush paths bypass Balearic Slingers

**Expected:** Card 13 unshaded applies once in an enemy Battle Command, including any Ambush and third-party Roman Auxilia. In the public card 17 unshaded witness, four German Warbands Ambush two Aedui Warbands beside two Roman Auxilia; Slingers first removes one German, then one Aedui is removed, leaving three Germans, one Aedui Warband and two Auxilia.

**Observed:** Public card 17 unshaded with explicit Roman empty March and explicit Carnutes/Aedui Ambush never requests Slingers and removes both Aedui, leaving four Germans, no Aedui Warbands and two Auxilia. A control without card 13 is identical. Ordinary Germans Phase Battle similarly leaves four Germans and none of the two Auxilia; ordinary engine Battle pipeline control asks Slingers and leaves three Germans and one Auxilia. Public card 53 with three Germans and four Auxilia (no German Control/Rally there) leaves three Germans and three Auxilia; correct initial fire would leave one German and four Auxilia.

**Cause:** german_guidance and germans_battle call low-level resolve_battle directly, bypassing the Command-scoped card 13 Region choice and prefire implemented only in _execute_battle. Other bypass routes are statically similar but not counted separately.

**Sources:** [Reference Documents/Card Reference:125](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Card%20Reference#L125); [Reference Documents/Card Reference:132](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Card%20Reference#L132); [Reference Documents/Card Reference:163](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Card%20Reference#L163); [Reference Documents/Chapter 6:55](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%206#L55); [Reference Documents/Card Reference:528](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Card%20Reference#L528).

**Implementation:** [fs_bot/cards/german_guidance.py:178](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/cards/german_guidance.py#L178); [fs_bot/engine/germans_battle.py:219](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/engine/germans_battle.py#L219); [fs_bot/engine/execute.py:4031](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/engine/execute.py#L4031).

**Controls:** Six cases: phase with card 13 active/inactive, normal engine command pipeline with card 13, public card 17 with card 13 on/off, public card 53 with card 13. The ordinary-command control is an engine API comparison only; it does not claim base Germans have a player turn. Public cards 17 and 53 are full legal Event entrypoints. No A31 capability in these base-game cases.

**Earlier audit distinction:** Original BE-09 and 5 November Slingers work fixed owner Region choices/combined rates in ordinary/free _execute_battle pathways, and later queued candidates. Neither reports direct German-guidance/Germans-Phase low-level resolver omissions. Distinct from BM6-01, where the ordinary pipeline fires a Capability that Phalanx should suppress.

**Evidence:** `battle/probe_battle.py`; `battle/probe_battle-output.json`.

**Fixture and limits:** Controlled build_initial_state positions, canonical piece helpers, permanent Provincia Fort retained, human seats except scenario game-run factions, actual execute_decision Event acquisition. Census and structural checks empty before/after each witness. These are legal constructed positions, not sampled encounter-frequency claims. Arverni Phase and other Event direct resolver callsites have the same static risk but no separate counted findings or proof of all card 59 effects. No full Winter cadence claim beyond the public phase procedure and full Events.

### BM6-03 — Consuetudine Battles multiple defenders in the same Region

**Expected:** 53 changes the Hidden-enemy prerequisite but retains one defender per selected Battle Region. With four German Warbands, two Roman Auxilia and two Aedui Warbands at Carnutes, Germans choose one defending Faction; the other two-piece faction survives this Command.

**Observed:** Public card 53 conducts separate two-Loss Ambushes first against Aedui then against Romans in Carnutes, removing both entire stacks. Ordinary Germans Phase control on the same position removes Aedui only and leaves both Auxilia. All four Germans survive both runs. The fixture has no German Control and no German Ally in Carnutes, so Rally/raid do not change the local combatants.

**Cause:** force_ambush=True disables Hidden-superiority and zero-Hidden guards inside a loop over all candidate defenders. Normal Reveal happens to stop the later defenders, but no explicit one-Battle-per-Region stop remains when the Event bypasses that condition.

**Sources:** [Reference Documents/Card Reference:528](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Card%20Reference#L528); [Reference Documents/Chapter 3:362](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%203#L362); [Reference Documents/Chapter 6:55](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%206#L55); [Reference Documents/Chapter 5:25](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%205#L25).

**Implementation:** [fs_bot/cards/card_effects.py:2013](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/cards/card_effects.py#L2013); [fs_bot/engine/germans_battle.py:191](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/engine/germans_battle.py#L191); [fs_bot/engine/germans_battle.py:204](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/engine/germans_battle.py#L204); [fs_bot/engine/germans_battle.py:219](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/engine/germans_battle.py#L219).

**Controls:** Paired public card 53 versus ordinary Germans Phase from identical constructed position; deterministic seed 1; both pre/post inventories clean. Loss-choice trace identifies two distinct physical defenders in one Region in card 53, one in the ordinary phase.

**Earlier audit distinction:** CM2-01 fixed authored ordinary Battle plans with repeated Regions/self-targets. BE3-01 fixed card 53 failure to waive Hidden superiority and the Scouted hide attempt. This is the resulting phase executor target loop, which still Battles every candidate after the repaired exception; it survives current main.

**Evidence:** `battle/probe_battle.py`; `battle/probe_battle-output.json`.

**Fixture and limits:** Controlled build_initial_state positions, canonical piece helpers, permanent Provincia Fort retained, human seats except scenario game-run factions, actual execute_decision Event acquisition. Census and structural checks empty before/after each witness. These are legal constructed positions, not sampled encounter-frequency claims. Only the public card 53 double-defender instance is counted; no claim of repeated Region behavior in unaffected ordinary phases.

### NP6-01 — Belgic and Arverni offensive Battle forecasts still use pre-Attack defenders and miss Ambiorix strength

**Expected:** Six Belgic Warbands versus six Roman Auxilia should Battle (3 Attack Losses and 1 Counterattack Loss); ten Arverni Warbands versus ten Auxilia should Battle (5 Attack Losses and 2 Counterattack Losses). Ambiorix with two Warbands versus six Auxilia should Battle (3 Attack Losses and 1 Counterattack Loss), whereas a Successor with two Warbands produces 2 Losses on each side and should March. All cases are Command only, with Revealed troops and no relevant Capability or Special Ability.

**Observed:** Public dispatch instead selects and executes March in the favorable equal-starting-troop cases, in both base and Ariovistus for Belgae, and with named Ambiorix. Validated public Battle from the same original states executes with the source-derived losses and clean piece counts.

**Cause:** Each _can_battle_in_region separately estimates Counterattack from the entire initial defender stack. Belgae also value every Warband at one-half even with Ambiorix attacking. Their duplicate _estimate_battle_losses repeats the same arithmetic. Neither consumer uses the corrected surviving-defender forecast already used by Germans.

**Sources:** [Reference Documents/Chapter 8:244](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%208#L244); [Reference Documents/Chapter 8:583](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%208#L583); [Reference Documents/Chapter 3:297](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%203#L297); [Reference Documents/Chapter 3:315](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%203#L315).

**Implementation:** [fs_bot/bots/belgae_bot.py:268](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/bots/belgae_bot.py#L268); [fs_bot/bots/belgae_bot.py:280](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/bots/belgae_bot.py#L280); [fs_bot/bots/arverni_bot.py:254](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/bots/arverni_bot.py#L254).

**Controls:** Six Belgic Warbands versus four Auxilia and ten Arverni Warbands versus six Auxilia correctly Battle. Six Belgic Warbands versus twelve Auxilia and ten Arverni Warbands versus twenty Auxilia correctly March. Comparing Ambiorix with a Successor isolates the named Leader rate: correcting survivor counts alone still produces an incorrect estimate of 2 Losses on each side for Ambiorix. Eleven probe cases in total.

**Earlier audit distinction:** NP5-03 fixed German bot _estimate_battle_losses only. These Belgic and Arverni consumers remain unchanged and are not regressions of that repaired German helper. Grouping both consumers and named-rate omission as one estimate repair group avoids counting each arithmetic symptom separately.

**Evidence:** `PYTHONPATH=<fs-bot-root> python bots/probe_bots.py`; `bots/probe_bots-output.json`.

**Fixture and limits:** Controlled build_initial_state positions; seed 6; pieces placed through canonical helpers, Legions explicitly taken from Track, permanent Provincia Fort retained. All pre/post schema census and structural checks pass. No claim of natural sampled-game encounter frequency. Confirmed bounded controlled cases only; no claim to exhaust all bot priorities, Capability or SA forecasts. No production changes.

### NP6-02 — Arverni and Aedui high-value Battle triggers mistake target presence for a forced Loss

**Expected:** Ten Arverni Warbands versus twenty Roman Auxilia and one Legion must March: 5 Attack Losses remove only Auxilia, 8 Counterattack Losses exceed the 5 inflicted, and no Legion absorbs a Loss. Four Aedui Warbands versus a Roman Ally and Fort must not trigger a high-value Battle: the single Attack Loss can be assigned to the Fort while the Ally survives. Forts are absent from the high-value target list in section 8.6.2.

**Observed:** Arverni publicly selects and executes Battle, losing eight Warbands while the Legion remains untouched. Independently, Aedui selects a high_value Battle and the human Roman defender assigns its only Loss to the Fort; the Ally survives. Both execute cleanly and satisfy census checks.

**Cause:** The Arverni can_hit_legion predicate is true whenever any Legion exists and Attack Losses exceed zero, regardless of intervening Auxilia. The Aedui predicate checks high-value target presence and compares losses only with Warbands plus Auxilia, omitting the Fort as a legal alternative loss target.

**Sources:** [Reference Documents/Chapter 8:583](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%208#L583); [Reference Documents/Chapter 8:448](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%208#L448); [Reference Documents/Chapter 8:180](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%208#L180); [Reference Documents/Chapter 3:324](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%203#L324); [Reference Documents/Chapter 3:333](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%203#L333).

**Implementation:** [fs_bot/bots/arverni_bot.py:250](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/bots/arverni_bot.py#L250); [fs_bot/bots/arverni_bot.py:280](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/bots/arverni_bot.py#L280); [fs_bot/bots/aedui_bot.py:276](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/bots/aedui_bot.py#L276).

**Controls:** Arverni correctly Marches in the control with the same twenty Auxilia and no Legion (see the NP6-01 table), and correctly Battles the unshielded Legion control. The reviewer's Aedui control without a Fort removes the Ally. The Aedui fixture has two Allies versus one Roman Ally, meeting the victory condition for targeting Romans, and no enemy mobile pieces to introduce Retreat ambiguity.

**Earlier audit distinction:** NP5-02 corrected an Aedui trigger when no high-value piece existed at all; these positions contain real high-value pieces but a Loss is not guaranteed to reach them. NP5-01/NP5-03 concern Diviciacus safety and German comparative forecasts, not forced target identity. Arverni screened-Legion and Aedui Fort-protected Ally share this trigger-guarantee repair group.

**Evidence:** `PYTHONPATH=<fs-bot-root> python bots/probe_bots.py`; `bots/probe_bots-output.json`.

**Fixture and limits:** Controlled build_initial_state positions; seed 6; pieces placed through canonical helpers, Legions explicitly taken from Track, permanent Provincia Fort retained. All pre/post schema census and structural checks pass. No claim of natural sampled-game encounter frequency. Confirmed bounded controlled cases only; no claim to exhaust all bot priorities, Capability or SA forecasts. No production changes.

**Additional evidence:** `PYTHONPATH=<fs-bot-root> python review/probe_aedui_fort.py`; `review/probe_aedui_fort-output.json`.

### NP6-03 — Roman threat gate caps Rampage at two victims and treats impossible Rampages as threats

**Expected:** With three Hidden Belgic Warbands, adjacent Ambiorix, and three Roman Legions plus two Auxilia, a legal Rampage can force a Legion casualty, so R1 should take the Battle/March branch. With two Hidden Belgic Warbands versus three Legions and one Auxilia, Rampage cannot trigger R1 when the Belgic Leader is absent or the Romans have a Fort.

**Observed:** The legal Rampage affecting three victims is ignored, and Romans select and execute Recruit. In both illegal-Rampage variants, Romans select and execute Battle. The matched control with two Hidden Warbands versus two Auxilia correctly does not trigger. The unfortified control with nearby Ambiorix and two Hidden Warbands versus one Auxilia does trigger. Actual Rampage execution from the legal fixtures removes a Legion exactly when required.

**Cause:** roman_bot._has_roman_threat uses min(2, belgic_hidden) without checking Leader range or the exclusion of targets with a Leader, Fort or Citadel. The actual Rampage executor already uses the full available capacity and checks legality.

**Sources:** [Reference Documents/Chapter 8:785](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%208#L785); [Reference Documents/Chapter 4:223](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%204#L223); [Reference Documents/Chapter 4:230](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%204#L230).

**Implementation:** [fs_bot/bots/roman_bot.py:198](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/bots/roman_bot.py#L198); [fs_bot/commands/sa_rampage.py:52](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/commands/sa_rampage.py#L52); [fs_bot/commands/sa_rampage.py:82](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/commands/sa_rampage.py#L82); [fs_bot/commands/sa_rampage.py:119](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/commands/sa_rampage.py#L119).

**Controls:** Five cases differ only in Hidden Warband count, Roman Auxilia count, adjacent Ambiorix or a local Fort. Roman Control is retained throughout; no enemy Ally, Leader or Control independently triggers R1. Ordinary enemy Battle Losses are no greater than the Auxilia count in every case. No adjacent Roman-controlled refuge exists in the legal casualty witnesses.

**Earlier audit distinction:** The original CMD-RAMPAGE-COUNT finding fixed actor quantity and the NPC execution cap on 4 November. This distinct Roman threat consumer still retains the old two-victim assumption. Neither that ledger nor the subsequent comparison ledgers of 21, 15, 16 and 11 findings lists Roman threat eligibility or capacity.

**Evidence:** `PYTHONPATH=<fs-bot-root> python bots/probe_bots.py`; `bots/probe_bots-output.json`.

**Fixture and limits:** Controlled build_initial_state positions; seed 6; pieces placed through canonical helpers, Legions explicitly taken from Track, permanent Provincia Fort retained. All pre/post schema census and structural checks pass. No claim of natural sampled-game encounter frequency. Confirmed bounded controlled cases only; no claim to exhaust all bot priorities, Capability or SA forecasts. No production changes.

### WS6-01 — Germans Phase Rally places multiple Allies in one Region and compounds their Warband gain

**Expected:** With two German Warbands controlling Sugambri and both its Tribes Subdued, place exactly one German Ally at Suebi (North), then one German Warband in Sugambri. The ordinary one-Ally-per-Region rule still applies to the Germans Phase.

**Observed:** Both the public Germans Phase Rally and complete public germans_phase place Allies at Suebi (North) and Sugambri in the same Rally. Sugambri then receives two Warbands. The extra Ally persists through the complete phase.

**Cause:** germans_phase_rally creates one candidate per Tribe and visits the Suebi/Germania/elsewhere lists without a Region-already-used guard. Its second phase then computes the Warband quota from the inflated Ally count.

**Sources:** [Reference Documents/Chapter 6:19](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%206#L19); [Reference Documents/Chapter 3:213](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%203#L213); [Reference Documents/Chapter 3:345](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%203#L345).

**Implementation:** [fs_bot/commands/rally.py:1536](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/commands/rally.py#L1536); [fs_bot/commands/rally.py:1547](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/commands/rally.py#L1547); [fs_bot/commands/rally.py:1592](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/commands/rally.py#L1592).

**Controls:** With Sugambri Tribe already German-allied, the same routine places only Suebi (North), which is legal. Running the ordinary Rally helper's Ally and Warbands options on the original fixture produces the required single Ally and single new Warband.

**Earlier audit distinction:** Earlier original/second/third/fourth/fifth audit ledgers contain no Germans Phase per-Region Rally quota finding. BE3-01 concerns Consuetudine Ambush eligibility and Scouted hiding; ordinary Arverni Phase Rally repairs concern a different faction and command implementation.

**Evidence:** `PYTHONPATH=<fs-bot-root> python lifecycle/probe_lifecycle.py`; `lifecycle/probe_lifecycle.json`.

**Fixture and limits:** Controlled build_initial_state position in The Great Revolt, seed1, canonical place_piece and named Ally helper only. Permanent Provincia Fort retained. Pre/post validate_state and check_structural_integrity pass, including named Tribe restrictions. No sampled-game frequency claim. The primary witness proves one Germanic Region with two Subdued Tribes. Similar multi-Tribe Regions follow the same loop but are not separately counted.

### WS6-02 — Germans Phase March moves arriving Warbands a second time

**Expected:** Form original moving groups at March start. From Ubii5 and Sugambri3 (no German Allies), the original groups are four and two; each can move only into one adjacent Region. An arrival at Sugambri cannot join Sugambri's later group.

**Observed:** Seed0 marches four Warbands Ubii to Sugambri, then six Sugambri to Nervii. Sugambri started with only three Warbands, so at least three arriving pieces moved a second time. The complete Germans Phase also reproduces: after Rally Sugambri has five original Warbands, receives six from Ubii, and then sends eleven to Nervii.

**Cause:** candidate_origins saves each original warband_count, but actual_send recomputes the full current surplus after previous groups have arrived. The movement loop consumes current physical stacks without an original-piece cohort limit.

**Sources:** [Reference Documents/Chapter 6:31](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%206#L31); [Reference Documents/Chapter 6:38](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%206#L38); [Reference Documents/Chapter 3:354](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%203#L354).

**Implementation:** [fs_bot/commands/march.py:1170](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/commands/march.py#L1170); [fs_bot/commands/march.py:1243](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/commands/march.py#L1243); [fs_bot/commands/march.py:1250](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/commands/march.py#L1250).

**Controls:** The identical original position at seed1 routes the first group elsewhere, so later groups do not exceed their original inventories; census and structure remain clean in both versions. Both isolated public March and complete public germans_phase reproduce seed0.

**Earlier audit distinction:** Original BE-01 Germanic Chieftains/German Allegiances/Aduatuca repairs established original cohorts for human Event-guided movement. Their reports explicitly distinguish those guided Commands from the game-run Germans Phase. FE5-02 concerns transit drop-off decisions, not this separate automatic March implementation.

**Evidence:** `PYTHONPATH=<fs-bot-root> python lifecycle/probe_lifecycle.py`; `lifecycle/probe_lifecycle.json`.

**Fixture and limits:** Controlled Great Revolt build_initial_state seed0: German Warbands Ubii5, Sugambri3, Treveri1, Sequani1, permanent Provincia Fort. No piece counts directly edited. Pre/post inventories and structure pass. Complete Germans Phase variant uses the actual Rally output to establish each origin's March-start inventory. The no-Rally witness independently isolates the March defect; the complete-phase witness also contains WS6-01's extra Allies, but its double-movement proof is relative to the actual post-Rally inventory and does not depend on the Rally expectation.

### WS6-03 — Germans Phase March omits player-Control priority among newly controllable destinations

**Expected:** A four-Warband group at Ubii can add Germanic Control at empty Sugambri, empty Sequani, or Treveri with one human Roman Auxilia. It must select Treveri: within destinations that add Control, prioritize player-controlled Regions.

**Observed:** At seed0 the public Germans Phase March selects empty Sugambri instead. In a complete phase on seed1, Germans instead move seven Warbands to empty Sequani while leaving the human Roman Treveri force untouched. The add-Control tier gives player-controlled and empty Regions equal random chances.

**Cause:** add_control candidates are appended before the human-control test, which runs only in the branch for destinations where the moving group cannot gain Control. Thus the printed secondary priority never applies within the highest tier.

**Sources:** [Reference Documents/Chapter 6:39](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/Reference%20Documents/Chapter%206#L39).

**Implementation:** [fs_bot/commands/march.py:1209](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/commands/march.py#L1209); [fs_bot/commands/march.py:1214](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/commands/march.py#L1214); [fs_bot/commands/march.py:1232](https://github.com/FeeSimple1/fs-bot/blob/86fb0c2d8ddf86a4548a863dc9c9da27d0c708ad/fs_bot/commands/march.py#L1232).

**Controls:** Changing Romans to NP removes the mandatory player preference, making the same empty-Sugambri selection legal. Giving human Romans twelve Auxilia makes Treveri unconquerable, so newly controllable empty Sugambri correctly has priority. Seed1 on the direct fixture happens to select Treveri, showing the current result depends on random selection rather than the source-required preference.

**Earlier audit distinction:** No earlier finding addresses this game-run German destination secondary priority. NP4-01 concerns Roman March opponent-strength ranking, and WS6-02 concerns original movement participants rather than destination ranking.

**Evidence:** `PYTHONPATH=<fs-bot-root> python lifecycle/probe_lifecycle.py`; `lifecycle/probe_lifecycle.json`.

**Fixture and limits:** Controlled Great Revolt build_initial_state: Ubii5 German Warbands, Treveri1 Roman Auxilia (human), permanent Provincia Fort, other playable seats NP. Direct witness seed0, full phase seed1. All pieces placed through helpers; pre/post census/structure and named Tribe restrictions pass. No claims about occurrence frequency or aggregate winner drift. Complete phase uses actual post-Rally group size and still has a uniquely required player-controlled destination.
