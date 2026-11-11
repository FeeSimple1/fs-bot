# Fifth Falling Sky comparison audit — 11 November 2026

**The audit confirmed 11 additional repair groups, 7 high and 4 medium priority.** All 11 were open when audited. The earlier 50-, 21-, 15- and 16-group ledgers remain closed. The audit commit changed documentation only.

Batch 1 repaired Event recipients and geography, closing BE5-01, BE5-02 and BE5-03. [Batch 1 repairs and validation](fifth-comparison-batch1-2026-11-11.md)

Falling Sky was audited at `bd30d522e8baa2d303b9e372d7d9c550351e91a5`, with Python-source SHA-256 `31e50801e3a187cf7c9def52e09df7ef5b39a895f55d32a4abfe0a08a42d2341` across 591 files. Liberty or Death was inspected at `2991ea279062773548ec390a1da75f3e85381702`. Its implementation patterns guided the search. Falling Sky's supplied references and thirteen adopted provisional rulings govern the conclusions.

[Finding ledger](comparison-audit-round5-2026-11-11.json) · [Portable evidence](comparison-audit-round5-2026-11-11-evidence.zip) · [Current status](../current-status.md)

## Method and coverage

| Comparison pattern | Fifth-pass checks |
|---|---|
| Match the action actually executed | Ordinary versus Event-granted March restrictions, live drop-offs, durable save/resume/replay |
| Trace stored effects to their consumers | Required Capability recipients through Battle and after-Harvest use; Gallia Togata's marker through Event movement |
| Apply the printed scope | Playable Region versus stored map area; home City/Tribe versus its containing Region |
| Use the actual combatants and surviving forces | Diviciacus safety, German offensive forecasts, nonexistent high-value targets |
| Integrate exceptional markers and modifiers | Abatis casualty choices and Diviciacus priority; Stalwart cancellation of Legio X |

The comparator material includes `coin-implementation-lessons.md`, `lod_ai/event_choices.py`, `lod_ai/util/eligibility.py`, `docs/human_mode_audit.md`, and `docs/audit_set_but_never_applied_s76.md`. Five partitions investigated candidates. A separate reviewer checked sources, fixture legality and earlier-ledger overlap, and reran the final probes. The root reviewer independently ran all five portable scripts and matched their recorded JSON.

Related symptoms are grouped by repair mechanism. Cards 10 and 63 share one recipient-acquisition group. Both home-City restoration branches share one scope group. Abatis's missing human choice and premature Diviciacus casualty share one marker-integration group. Diviciacus's unrelated-opponent veto and omitted Ariovistus multiplier share one safety-gate group. Prior fixes remain closed for their recorded scope; additional untested consumers are identified explicitly below.

## Confirmed findings

| ID | Priority | Finding |
|---|---|---|
| BE5-01 | high | Shaded Ballistae and Winter Campaign can be activated without their required Gallic recipient |
| BE5-02 | high | Colony creates a Tribe and Ally in nonplayable map areas |
| BE5-03 | medium | Forced Marches rejects legal Cisalpina movement after Gallia Togata |
| FE5-01 | high | Event-granted March accepts a forbidden Britannia crossing with an accompanying Special Ability |
| FE5-02 | medium | Human Event-granted March silently omits the transit drop-off decision |
| BM5-01 | high | Stalwart leaves Legio X bonus Losses active against Germans |
| BM5-02 | high | Abatis bypasses casualty choices and can force Diviciacus to absorb before his defensive marker |
| NP5-01 | high | Diviciacus protection evaluates unrelated opponents and omits Ariovistus Counterattack doubling |
| NP5-02 | medium | Aedui high-value Battle trigger succeeds when no high-value defender exists |
| NP5-03 | medium | German Battle selection uses pre-Attack Counterattack forces and omits Ariovistus attack doubling |
| WS5-01 | high | Interlude home-City restoration clears all Forces in the containing Region |

High indicates an illegal action, material wrong effect, forbidden exposure of a piece, or inconsistent state. Medium indicates a missed legal choice or narrower bot-selection failure. These priorities do not estimate frequency. Comparing this count with earlier passes does not establish a defect-rate trend because the focused paths differ.

## Verification and limits

- **9,806 existing tests passed**, with no failures, in 170.25 seconds on Python 3.12.14.
- **Five final portable witness scripts passed** independent review and the root runner. Each root result matches its recorded JSON. Most assertions intentionally reproduce the audited defects; repairs must replace them with source-correct regressions and retain the controls.
- **20 audited all-bot games passed**, covering second-edition seeds 29–32 in all five scenarios. Every record has complete four-faction rankings, clean inventory/structure checks, no errors and no nonlegal diagnostics. Two games reached the Interlude.
- **20 mixed-seat cases** on the same scenario/seed/edition matrix completed and matched byte-for-byte across hash seeds 0 and 987, with internal replay enabled. That represents 80 executions, not 80 distinct cases. Each hash run records 768 human turns, 176 Event attempts, 166 executed Events, zero hard findings and two soft partial plans.
- No fresh balance matrix was run. Production code, tests, supplied references, canonical constants and balance baselines remain unchanged.

The general tests and game samples do not exercise every targeted boundary. Some witnesses use full ordinary setup boards; others use controlled positions assembled with piece helpers. All retain Provincia's permanent Fort and pass the applicable inventory/structure checks, with source-specific fixture review beyond those validators. Controlled card/phase selection is disclosed. No claim is made that every witness arose in sampled natural play.

The Optimates/Pax Gallica phase-counting observation is **not a confirmed defect**. The references do not expressly decide whether a skipped first Victory Phase retains its ordinal position. The question and both interpretations are recorded in [QUESTIONS.md](../../QUESTIONS.md#q-optimates-pax-phase-count--whether-paxs-skipped-victory-phase-counts-for-optimates). Its witness records current behavior without prescribing a repair. The Interlude deck-size lead was rejected after source review. Earlier unresolved questions and separately tracked Circumvallation work are not recounted.

The evidence includes bounded coverage and rejected/held leads. In particular, Balearic Slingers prefire timing under Stalwart, additional coarse forecast interactions, and exploratory Cicero/Sappers target cases are not included as confirmed groups.

## Suggested repair order

| Batch | Scope | Findings |
|---|---|---|
| 1 | Event ownership and state-aware geography | BE5-01, BE5-02, BE5-03 |
| 2 | Interlude home-City restoration | WS5-01 |
| 3 | Free March restrictions and choices | FE5-01, FE5-02 |
| 4 | Battle capability cancellation and casualty choices | BM5-01, BM5-02 |
| 5 | Bot target and survival forecasts | NP5-01, NP5-02, NP5-03 |

For each batch, convert the relevant witnesses to source-correct regression tests, prove they fail on this audited revision, then run the focused and full checks. Use the appropriate integrated validation in `SELFPLAY_PLAYBOOK.md`. Explain any changed game outcomes before changing an outcome baseline. Optimates is outside this repair queue pending clarification.

To reproduce, extract the evidence ZIP and run against the audited checkout. The runner requires an unused output directory and verifies the Python source digest. Documentation-only commits with the same Python sources are also accepted.

```sh
python run_probes.py /path/to/fs-bot /path/to/new-results
```

## Evidence by finding

### BE5-01 — Shaded Ballistae and Winter Campaign can be activated without their required Gallic recipient

**Expected.** The executor must assign the shaded Capability to a Gallic Faction. A Roman executor submitting no recipient or an explicitly Roman recipient must correct the selection before the Event commits. The selected Gallic Faction receives the actual ongoing effect.

**Observed.** On unmodified Great Revolt setup, the durable turn shape validator and public preview accept both missing and Roman recipient, and execute_decision installs the shaded Capability with no owner. This occurs with original and second-edition profiles. Card 63's production after-Harvest consumer returns None and asks no Faction. A separate source-valid Battle fixture proves ownerless Card 10 gives no post-Ambush removal request, leaving the defending Citadel alive; the same public acquisition with Belgae selected gives the request and removes the Citadel.

**Controls.** Both cards accept Belgae as recipient and record Belgae. Card 63 offers Belgae the Winter Campaign choice. Public Belgic Battle+Ambush under properly assigned Card 10 removes the exact surviving Arverni Citadel at Sequani. All before/after pool and structure checks pass; previews leave live state/RNG unchanged.

**Relation to earlier work.** Not a repeat of fourth-audit BE4-04: shaded Germanic Horse belongs to its Gallic executor and previously could be gifted. Cards 10/63 instead require an independently selected Gallic recipient even when the executor is Roman. Original Battle/Winter Campaign human-choice repairs repaired consumers, not this acquisition validation.

**Fixture.** Acquisition uses ordinary setup_scenario Great Revolt seed 17 boards, selecting the audited current card without claiming a naturally sampled sequence. Ballistae follow-through uses a controlled initialized position assembled with piece helpers and the permanent Provincia Fort, an exact Sequani Citadel allegiance, one Belgic Warband plus Ambiorix, and four Revealed defending Arverni Warbands. Winter Campaign is the production consumer invoked directly at its after-Harvest boundary, not a claimed full Winter run.

**Rules.** [Reference Documents/Card Reference:94](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Card%20Reference#L94) · [Reference Documents/Card Reference:645](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Card%20Reference#L645) · [Reference Documents/Chapter 5:5](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Chapter%205#L5) · [Reference Documents/Chapter 5:50](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Chapter%205#L50)

**Code.** [fs_bot/cards/card_effects.py:681](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/cards/card_effects.py#L681) · [fs_bot/cards/card_effects.py:2328](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/cards/card_effects.py#L2328) · [fs_bot/engine/execute.py:4108](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/engine/execute.py#L4108) · [fs_bot/engine/winter_campaign.py:141](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/engine/winter_campaign.py#L141)

**Evidence.** `events/findings.json`, its portable probe and recorded output in the archive.

### BE5-02 — Colony creates a Tribe and Ally in nonplayable map areas

**Expected.** Colony selects a playable Region under the executing Faction's Control or No Control. Its exception creates an additional Tribe circle in that Region; it does not turn a nonplayable area into a Region. Reject base Cisalpina without Gallia Togata and Ariovistus Britannia before adding any Tribe, marker or Ally.

**Observed.** From ordinary Great Revolt seed 17 setup, a Roman public Event71 naming Cisalpina succeeds and creates Colony_Cisalpina, its marker and one Roman Ally despite no Gallia Togata. From ordinary Ariovistus seed 17 setup, the same plan naming Britannia succeeds and creates Colony_Britannia and its Roman Ally. is_region_playable is false in both cases; durable shape validation, public mechanical preview and live execution all accept. Census and structural checks remain clean.

**Controls.** Roman Colony in Provincia succeeds in both scenarios. A real Card 5 Gallia Togata followed by Roman Colony in Cisalpina succeeds legally. Each control creates exactly one matching named Tribe and Ally with clean inventory/structure.

**Relation to earlier work.** Third-audit BE3-03 fixed creating a legal Colony under scarce Ally supply; XC3-01 fixed existing dynamic Tribe consumers. This finding concerns the location of new Colony creation and reaches both base and expansion nonplayable areas. CM3-01 was ordinary Scout geography, a different execution path.

**Fixture.** All main witnesses and controls start from full setup_scenario boards. The current card is selected explicitly for the probe. Both numeric 71 and the geography rules are valid in the stated scenario. No forbidden off-deck numeric replacement card is used.

**Rules.** [Reference Documents/Card Reference:729](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Card%20Reference#L729) · [Reference Documents/Chapter 1:115](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Chapter%201#L115) · [Reference Documents/Ariovistus/Chapter A1:78](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Ariovistus/Chapter%20A1#L78) · [Reference Documents/Chapter 5:25](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Chapter%205#L25)

**Code.** [fs_bot/cards/card_effects.py:2627](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/cards/card_effects.py#L2627) · [fs_bot/map/map_data.py:390](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/map/map_data.py#L390)

**Evidence.** `events/findings.json`, its portable probe and recorded output in the archive.

### BE5-03 — Forced Marches rejects legal Cisalpina movement after Gallia Togata

**Expected.** After Gallia Togata makes Cisalpina a playable Roman Region, Forced Marches may relocate the executor's Roman mobile pieces into or out of it. The card's sole geographic exclusion is Britannia, subject to ordinary current stacking rules.

**Observed.** On a full Great Revolt seed 17 board, public Card 5 correctly installs the marker and three Auxilia. A subsequent public Card 32 selecting one Auxilia Cisalpina to Provincia is rejected with 'Forced Marches requires playable Regions'. A separate identical board rejects the legal reverse move from Provincia to Cisalpina. Both original and second-edition profiles fail, and the atomic rollback preserves the pieces and RNG.

**Controls.** Card 32 Provincia to Sequani succeeds, moving exactly one Auxilia. Without Card 5, Provincia to Cisalpina is correctly rejected. In the failing Card 5 cases, the production is_region_playable helper returns true for both endpoints.

**Relation to earlier work.** New legal-choice failure in numeric 32. Third-audit CM3-01 admitted illegal ordinary Scout into inactive Cisalpina; this is the opposite effect in a separate Event path after a real marker writer. Not a repeat of Interlude deck/Nori repairs.

**Fixture.** Main witnesses are full Great Revolt scenario setups followed by an actual public Gallia Togata Event. Card order is controlled, not claimed to have arisen in a sampled game. No numeric 32 claim is made in Ariovistus, whose ordinary deck replaces it with A32.

**Rules.** [Reference Documents/Card Reference:43](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Card%20Reference#L43) · [Reference Documents/Card Reference:318](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Card%20Reference#L318) · [Reference Documents/Chapter 5:25](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Chapter%205#L25)

**Code.** [fs_bot/cards/card_effects.py:1375](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/cards/card_effects.py#L1375) · [fs_bot/map/map_data.py:344](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/map/map_data.py#L344) · [fs_bot/map/map_data.py:390](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/map/map_data.py#L390)

**Evidence.** `events/findings.json`, its portable probe and recorded output in the archive.

### FE5-01 — Event-granted March accepts a forbidden Britannia crossing with an accompanying Special Ability

**Expected.** Assembly of Gaul's free Command follows normal restrictions. Aedui may March Morini to Britannia, or combine a mainland March with Suborn, but may not combine the Britannia crossing with any accompanying Special Ability.

**Observed.** Full public execution of shaded card 52 accepts the canonical origins/destinations/routes plan, moves one Aedui Warband from Morini to Britannia, and places another Aedui Warband by Suborn at Carnutes. Both execute free. Ordinary execution of the identical March + Suborn rejects before changing board or RNG. Durable SeatSession validation also accepts the prohibited free action, commits it after a save/load, clears its pending decision, and replays the same incorrect result exactly.

**Controls.** Identical ordinary March+Suborn rejects atomically Free Britannia crossing with No SA succeeds Free Morini-to-Nervii March+Suborn succeeds Validation leaves live board and RNG unchanged Durable save/load and replay preserve the observed accepted action

**Relation to earlier work.** CM2-02 repaired alternate representations of ordinary human March. Its ordinary canonical/alternate path now rejects this crossing. This is a separate unchecked Event-grant pipeline, using the canonical shape. FE4-01/02/03 concerned free Battle timing, nested SA Region scope and Assembly's second ability, respectively. No previous ledger records this free March path.

**Fixture.** Controlled Great Revolt state from build_initial_state(seed=4), all human factions, permanent Roman Fort in Provincia, Aedui Warbands in Carnutes and Morini, 10 Aedui Resources, current52/next49. All physical placements use place_piece. Census and structure pass before and after. Carnutes is Aedui controlled. Not claimed naturally sampled.

**Limit.** Dynamically confirmed for the single-ability free Command path on Assembly52. The generic helper serves other Event grants; those additional callers were not individually sampled. Two-ability Assembly has its own _with_sa=True check. No source ambiguity.

**Rules.** [Reference Documents/Chapter 4:38](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Chapter%204#L38) · [Reference Documents/Chapter 5:78](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Chapter%205#L78) · [Reference Documents/Card Reference:518](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Card%20Reference#L518)

**Code.** [fs_bot/engine/free_actions.py:386](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/engine/free_actions.py#L386) · [fs_bot/engine/execute.py:713](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/engine/execute.py#L713) · [fs_bot/engine/execute.py:4406](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/engine/execute.py#L4406)

**Evidence.** `frontend/findings.json`, its portable probe and recorded output in the archive.

### FE5-02 — Human Event-granted March silently omits the transit drop-off decision

**Expected.** A Roman player receiving Assembly52's free March may leave one of two marching Auxilia in Sequani before continuing from Provincia through Sequani to Mandubii. The existing live march_dropoff interface should be offered just as it is for an ordinary March.

**Observed.** The public Event executor requests the human free Command and then moves both Auxilia to Mandubii without any march_dropoff request, leaving Sequani empty. The same plan and same callback advertised as supports_march_dropoffs in ordinary public execution receives the request and successfully leaves one Auxilia in Sequani while the other reaches Mandubii. Both executions have clean census and structure.

**Controls.** Identical ordinary public March requests one live drop-off and preserves the player's selected piece Callback explicitly declares supports_march_dropoffs=True in both cases No Special Ability, enemy harassment or capability complicates the witness Both before/after board census and structure are valid

**Relation to earlier work.** The original MARCH-DROPOFF finding expressly covered ordinary March and its repaired ordinary path passes this paired control. This is the missed generic Event-granted human Command integration. FE5-01 is a separate illegal-combination validation failure; this group concerns omitted legal player choice and a different required execution flag.

**Fixture.** Controlled Great Revolt state from build_initial_state(seed=4), permanent Provincia Fort, one Roman Auxilia controlling Carnutes, two Roman Auxilia in Provincia, 10 Resources, current52/next49, all factions human. Route Provincia-Sequani-Mandubii is a legal two-step Roman March without Caesar. place_piece creates every physical fixture piece. No claim of natural sampled reach.

**Limit.** Dynamic witness covers Assembly52's ordinary zero-ability free Command. Static inspection also shows its two-ability path uses choose_dropoffs=bool(interruption_steps), but that additional path is not included in the dynamic claim. Card-specific movement-only grants may have distinct printed rules and need individual review during repair.

**Rules.** [Reference Documents/Chapter 3:52](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Chapter%203#L52) · [Reference Documents/Chapter 5:78](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Chapter%205#L78) · [Reference Documents/Card Reference:518](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Card%20Reference#L518)

**Code.** [fs_bot/engine/execute.py:713](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/engine/execute.py#L713) · [fs_bot/engine/execute.py:367](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/engine/execute.py#L367) · [fs_bot/engine/execute.py:4406](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/engine/execute.py#L4406) · [fs_bot/engine/march_choices.py:202](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/engine/march_choices.py#L202)

**Evidence.** `frontend/findings.json`, its portable probe and recorded output in the archive.

### BM5-01 — Stalwart leaves Legio X bonus Losses active against Germans

**Expected.** With A31 shaded and Card 15 unshaded active, Roman Caesar plus one Legion attacking Germans inflicts two Losses: the named-leader doubling and the harmful +2 Event modifier are both cancelled.

**Observed.** Full authored ordinary Battle in Carnutes removes four of eight German Warbands. Stalwart cancels Caesar doubling but the later Legio X block still adds two Losses. Both public Events activate successfully beforehand.

**Controls.** A31 shaded with no15 removes two Germans. 15 unshaded with noA31 removes five Germans (Caesar doubling and +2 apply). Runtime deck IDs confirm15,A31,A64 coexist; supplied setup replacement list corroborates this independently.

**Relation to earlier work.** EX3-04 covered Germanic Horse doubling against Germans. This newly demonstrated consumer is the independent Legio X final flat bonus, left active after that repair. It is one additional cancellation repair group, not separate counts for every potential A31 interaction.

**Fixture.** Controlled initial Ariovistus state, seed 1, permanent Provincia Fort, canonical placement helpers. Caesar and one Legion plus eight German Warbands in Carnutes. Human Germans decline Retreat. Capability acquisitions use execute_decision ACTION_EVENT, battle uses validate_response and execute_decision ACTION_COMMAND.

**Limit.** Confirmed +2 Attack modifier only. The same code shows ungated Roman -1 and Counterattack consumers but those additional manifestations are not separately counted; Balearic prefire timing was not resolved or counted.

**Rules.** [Reference Documents/Ariovistus/A Card Reference:126](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Ariovistus/A%20Card%20Reference#L126) · [Reference Documents/Card Reference:147](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Card%20Reference#L147) · [Reference Documents/Chapter 3:159](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Chapter%203#L159) · [Reference Documents/Ariovistus/A Setup:36](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Ariovistus/A%20Setup#L36)

**Code.** [fs_bot/battle/resolve.py:388](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/battle/resolve.py#L388) · [fs_bot/battle/resolve.py:502](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/battle/resolve.py#L502) · [fs_bot/battle/losses.py:312](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/battle/losses.py#L312)

**Evidence.** `battle/findings.json`, its portable probe and recorded output in the archive.

### BM5-02 — Abatis bypasses casualty choices and can force Diviciacus to absorb before his defensive marker

**Expected.** Abatis acts as a Fort while its owner defends. Once ordinary Warbands are removed, the human may choose an eligible Ally instead of rolling for the marker. Diviciacus cannot absorb while the Abatis can still absorb.

**Observed.** In the Ally witness, four Roman Legions cause two halved Losses to one Aedui Warband plus an Ally and Abatis. The Warband is offered, then the engine rolls/removes Abatis without a second loss-order request and preserves the Ally. In the Diviciacus witness, replacing the Ally with Diviciacus makes the engine offer and remove Diviciacus on seed 2 while leaving Abatis in place.

**Controls.** Without marker and with two Legions producing the same two Losses, two requests remove Warband then the chosen named Ally. The two-Loss Diviciacus plus Warband plus Ally control removes Warband/Ally and keeps Diviciacus. Both marker positions acquire Abatis through an actual validA64 Event with an Aedui Warband present.

**Relation to earlier work.** Original BATTLE-LOSS-IDENTITY repaired physical Warband/Auxilia visibility and named Allied Tribe selection. Historical Abatis absorption implementation established saving rolls, but the marker still sits outside ordinary choice/last-piece handling. These two new manifestations share one missing marker-in-casualty-selection mechanism and count as one group.

**Fixture.** Controlled initial Ariovistus states, seeds1/2, permanent Provincia Fort, four Roman Legions and one Aedui Warband at Carnutes, Aedui Ally at Aulerci or Diviciacus. Explicit no Retreat. No unit mocks, altered RNG, or invalid piece identities. Actual public A64 then public normal Battle.

**Limit.** Controlled legal positions rather than sampled natural games. No claim that all Abatis interactions were reviewed; no new Fort threshold or prefire timing ruling proposed.

**Rules.** [Reference Documents/Ariovistus/A Card Reference:288](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Ariovistus/A%20Card%20Reference#L288) · [Reference Documents/Chapter 3:159](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Chapter%203#L159) · [Reference Documents/Ariovistus/Chapter A3:63](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Ariovistus/Chapter%20A3#L63)

**Code.** [fs_bot/battle/losses.py:440](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/battle/losses.py#L440) · [fs_bot/battle/losses.py:491](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/battle/losses.py#L491) · [fs_bot/battle/losses.py:783](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/battle/losses.py#L783)

**Evidence.** `battle/findings.json`, its portable probe and recorded output in the archive.

### NP5-01 — Diviciacus protection evaluates unrelated opponents and omits Ariovistus Counterattack doubling

**Expected.** Apply A8.6.2 to the actual selected defender and actual possible Counterattack. Diviciacus plus one Warband may safely Battle a lone Belgic Ally regardless of ten unrelated German Warbands sharing the Region. Conversely, with one escort he may not Battle Ariovistus, who can survive the Attack and inflict two Counterattack Losses.

**Observed.** The public Aedui dispatcher returns Pass in the safe Belgic-Ally case when unrelated Germans are present, but Battle when they are absent. In a second fixture it Battles at Veneti to remove a Belgic Ally and adds the Carnutes Battle against Ariovistus. Seed 6 leaves Ariovistus alive and removes both the Aedui escort and Diviciacus. Changing only Ariovistus to his Successor leaves Diviciacus alive, as one Counterattack Loss is absorbed by the escort.

**Controls.** Same safe battle without uninvolved Germans is chosen and executes. Same dangerous Battle with German Successor loses only escort. Correct human-authored Belgic Battle validates and executes with both Diviciacus and escort intact.

**Relation to earlier work.** NP4-02 fixed only the equality boundary for zero/equal Counterattack versus escort capacity. Its report expressly left unrelated-enemy cases uncounted. These fifth-pass witnesses still fail after that repair and identify target scoping and an omitted named-Leader multiplier. BM4-02 concerns defensive Retreat policy, not this offensive safety gate.

**Fixture.** Controlled build_initial_state position; pieces placed with canonical helpers and named Tribe helper; permanent Provincia Fort retained; pre/post inventory and structural integrity pass. No claim of natural sampled-game reachability.

**Limit.** No claim about all possible Capability, Ambush, Retreat or casualty-choice forecasts. The seed-6 removal demonstrates one legal outcome; A8.6.2 forbids the Battle whenever such a Loss is possible, even on a saving roll.

**Rules.** [Reference Documents/Ariovistus/Chapter A8:53](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Ariovistus/Chapter%20A8#L53) · [Reference Documents/Chapter 8:448](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Chapter%208#L448) · [Reference Documents/Chapter 3:132](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Chapter%203#L132) · [Reference Documents/Ariovistus/Chapter A3:57](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Ariovistus/Chapter%20A3#L57)

**Code.** [fs_bot/bots/aedui_bot.py:332](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/bots/aedui_bot.py#L332) · [fs_bot/bots/aedui_bot.py:704](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/bots/aedui_bot.py#L704) · [fs_bot/bots/aedui_bot.py:202](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/bots/aedui_bot.py#L202)

**Evidence.** `bots/findings.json`, its portable probe and recorded output in the archive.

### NP5-02 — Aedui high-value Battle trigger succeeds when no high-value defender exists

**Expected.** With only eight Aedui and one Belgic Warband at Carnutes, and no enemy Leader, Ally, Citadel or Legion elsewhere, 8.6.2 does not trigger Battle. The next 8.6.3 branch Rallies because Carnutes Control permits placing an Ally.

**Observed.** In both The Great Revolt and Ariovistus, the public dispatcher labels the lone Belgic Warband a high_value target, chooses Battle, and executes it. The source-required Rally branch validates/executed separately from the identical initial position and places the Carnutes Aedui Ally.

**Controls.** Adding a Belgic Carnutes Ally makes Battle correctly satisfy the high-value prerequisite. Both variants run in base and Ariovistus. The fixture uses Command-only planning to avoid Ambush eligibility affecting the proof.

**Relation to earlier work.** None of the earlier 50/21/15/16 ledgers covers nonexistent high-value targets. This is separate from NP4-02 Diviciacus protection and NP4-01 Roman Settlement ranking.

**Fixture.** Controlled build_initial_state position; pieces placed with canonical helpers and named Tribe helper; permanent Provincia Fort retained; pre/post inventory and structural integrity pass. No claim of natural sampled-game reachability.

**Limit.** The alternate legal Rally plan is obtained from node_a_rally and executed through public execute_decision. The audit does not alter the bot decision tree or claim sampled-game frequency.

**Rules.** [Reference Documents/Chapter 8:448](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Chapter%208#L448) · [Reference Documents/Chapter 8:469](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Chapter%208#L469) · [Reference Documents/Ariovistus/Chapter A8:53](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Ariovistus/Chapter%20A8#L53)

**Code.** [fs_bot/bots/aedui_bot.py:270](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/bots/aedui_bot.py#L270) · [fs_bot/bots/aedui_bot.py:299](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/bots/aedui_bot.py#L299) · [fs_bot/bots/aedui_bot.py:411](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/bots/aedui_bot.py#L411)

**Evidence.** `bots/findings.json`, its portable probe and recorded output in the archive.

### NP5-03 — German Battle selection uses pre-Attack Counterattack forces and omits Ariovistus attack doubling

**Expected.** Six Revealed German Warbands versus six Revealed Roman Auxilia must Battle under A8.7.1: three Attack Losses leave three Auxilia for one Counterattack Loss, so 3 > 1. Ariovistus with four Warbands versus six Auxilia is also favorable: six Attack Losses remove every Auxilia and leave zero Counterattack.

**Observed.** The public German dispatcher predicts 3 versus 3 in both cases and chooses/executes March to Veneti. A normal validated public Battle from the identical initial board produces the source-derived 3/1 or 6/0 losses with clean post-state integrity.

**Controls.** Six Germans versus four Auxilia correctly selects Battle (3 Attack, 0 Counterattack). Six Germans versus twelve Auxilia correctly selects March (3 Attack, 4 Counterattack). All witnesses disable SA through the standard Command-only planning flag and use no saving-roll pieces among defenders, avoiding forecast-policy ambiguity.

**Relation to earlier work.** BM4-02 repaired defensive NPC Retreat forecasts in execute.py. It did not change german_bot.py's independent offensive Battle-selection estimate. No original/second/third/fourth ledger lists this active German flowchart consumer.

**Fixture.** Controlled build_initial_state position; pieces placed with canonical helpers and named Tribe helper; permanent Provincia Fort retained; pre/post inventory and structural integrity pass. No claim of natural sampled-game reachability.

**Limit.** Confirmed for the two clean no-SA cases above. Other German Capability, Ambush, Intimidate and Successor estimates are statically suspicious but remain uncounted.

**Rules.** [Reference Documents/Ariovistus/Chapter A8:72](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Ariovistus/Chapter%20A8#L72) · [Reference Documents/Chapter 3:144](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Chapter%203#L144) · [Reference Documents/Ariovistus/Chapter A3:57](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Ariovistus/Chapter%20A3#L57)

**Code.** [fs_bot/bots/german_bot.py:224](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/bots/german_bot.py#L224) · [fs_bot/bots/german_bot.py:265](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/bots/german_bot.py#L265) · [fs_bot/bots/german_bot.py:895](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/bots/german_bot.py#L895)

**Evidence.** `bots/findings.json`, its portable probe and recorded output in the archive.

### WS5-01 — Interlude home-City restoration clears all Forces in the containing Region

**Expected.** Restoring the Aedui Tribe at Bibracte or Arverni Tribe at Gergovia removes what occupies that Tribe circle/City. Roman Legions and other Forces elsewhere in the containing Region remain subject to their own Interlude instructions. Roman reductions expressly exclude Legions, and a declined expedition changes no Roman Forces.

**Observed.** Both mirrored branches iterate every faction and piece type across the entire Aedui/Arverni Region. Full third-Winter resolution restores a vacant home Tribe but also sends a colocated Roman Legion to the Legions Track. Six on-map Legions become five. The matched controls with the home Tribe occupied retain all six. Census/structure checks pass before and after every case.

**Controls.** Occupied home Tribe controls retain the Legion in its Region and leave six on-map Legions; vacant cases restore the same Tribe but remove the Legion. No monkeypatches or engine edits.

**Relation to earlier work.** Earlier Interlude choice findings fixed human selection and bookkeeping. WS4-03 removes obsolete Nori at scenario change. Neither covers the Bibracte/Gergovia Region-wide wipe. Existing test_interlude_aedui_choices:test_bibracte_is_restored_when_only_a_colony_ally_survives_in_its_region and test_interlude_arverni_choices:test_cadurci_does_not_prevent_gergovia_restoration_and_reinforcement currently assert collateral clearing; those tests need source-correct expectations, not preservation.

**Fixture.** Controlled Gallic War setup, seed 21. One Roman Legion moves from Provincia to the selected home Region with the normal piece helper. One Belgic Namnetes Ally is placed legally from Available so neither vacant-home witness passes Roman victory. Home Ally removed with _unally_tribe only in defect variants. All restricted Tribe ownership and permanent Provincia Fort assertions pass. Set winter_count2/current Winter to enter third Victory Phase. Romans are human and explicitly decline Britannia expedition; other seats are NP. Other human Interlude choices use the documented raw API default policy. This is a controlled phase integration, not a claim of sampled gameplay reach.

**Limit.** Controlled integration cases; no encounter-frequency claim.

**Rules.** [Reference Documents/Ariovistus/A Scenario - The Gallic War:51](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Ariovistus/A%20Scenario%20-%20The%20Gallic%20War#L51) · [Reference Documents/Ariovistus/A Scenario - The Gallic War:61](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Ariovistus/A%20Scenario%20-%20The%20Gallic%20War#L61) · [Reference Documents/Ariovistus/A Scenario - The Gallic War:65](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Ariovistus/A%20Scenario%20-%20The%20Gallic%20War#L65) · [Reference Documents/Ariovistus/A Scenario - The Gallic War:82](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Ariovistus/A%20Scenario%20-%20The%20Gallic%20War#L82) · [Reference Documents/Chapter 1:117](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/Reference%20Documents/Chapter%201#L117)

**Code.** [fs_bot/engine/interlude.py:640](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/engine/interlude.py#L640) · [fs_bot/engine/interlude.py:793](https://github.com/FeeSimple1/fs-bot/blob/bd30d522e8baa2d303b9e372d7d9c550351e91a5/fs_bot/engine/interlude.py#L793)

**Evidence.** `lifecycle/findings.json`, its portable probe and recorded output in the archive.
