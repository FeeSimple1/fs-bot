# Tenth Falling Sky / Liberty or Death comparison audit

**13 November 2026. Nine additional repair groups, all medium priority. Batches 1–3 close four, with five open.**
[Batch 1 repairs and validation](tenth-comparison-batch1-2026-11-13.md) ·
[Batch 2 repair and validation](tenth-comparison-batch2-2026-11-13.md) ·
[Batch 3 repair and validation](tenth-comparison-batch3-2026-11-13.md)
The ninth audit remains complete with all eight of its scoped groups repaired. This audit records additional affected paths, including the ordinary spread-March extension of the earlier post-Command Special Ability defect. Production code and supplied references are unchanged.

Audited commit: `ae238c6482a792dda98af4f1f9b11abf820a3964`. Python source SHA-256: `39076dca68ec449cf766e40256c765d2d36693c50989a2b0552745f208f94d45` across **620 Python files**, Python 3.12.14. Comparator: `FeeSimple1/lod-bot` at `2991ea279062773548ec390a1da75f3e85381702`.

[Finding ledger](comparison-audit-round10-2026-11-13.json) · [Portable evidence](comparison-audit-round10-2026-11-13-evidence.zip) · [Current status](../current-status.md)

## Method and coverage

Repeated the authorized engineering comparison across combat, bot flowcharts, Events, lifecycle, and human frontends, with an independent validation lane. Reviewed actual Liberty or Death action simulation, actual-effect accounting, immediate free-action execution and rollback diagnostics, as recorded in `comparator-review.md` in the archive. Game-rule conclusions use supplied Falling Sky/Ariovistus sources and the thirteen adopted project rulings. All 47 reference files plus canonical constants were hashed and remain unchanged.

Each counted group has source/code review, executable public-path evidence, positive and negative controls, and independent reruns. The lead reran the finalized witness scripts at hash seeds 0 and 987 against the preserved results. Four original lane outputs are byte-identical. The whole-Winter lifecycle control exposes hash-dependent Supply Line prompt Regions while its complete final board and RNG digests remain equal. Both raw outputs are preserved without normalization. The separate durable replay witness establishes the functional consequence counted as UI10-03. Fixtures use canonical piece operations and complete physical/structural checks. Controlled current-card metadata, sparse positions and direct public phase entry are disclosed per finding. These witnesses do not measure natural encounter frequency.

Prior ledgers and repairs were checked for duplicates. BM10-01 promotes an explicitly excluded seventh-round lead only after demonstrating its public A34 consequence. NP10-01 extends the known stale-forecast mechanism to a different Command consumer; it is not counted as a newly discovered defect class. UI10-01 concerns completed output, separate from correct live execution and Sequence of Play accounting.

## Confirmed findings

| ID | Priority | Finding |
|---|---|---|
| EV10-01 | Medium | Bots play conditional Bellovaci and Siege of Bibrax Events when their prerequisite is false |
| EV10-02 | Medium | Non-player Aedui give Siege of Bibrax troops to Romans despite Available Aedui Warbands |
| BM10-01 | Medium | Canceled Abatis makes Divination skip a required Aedui Battle |
| LC10-01 | Medium | Roman Quarters rejects legal adjacent relocation into an agreeing faction's Provincia |
| UI10-01 | Medium | Completed CLI summaries report forecast Special Abilities instead of actual execution |
| UI10-02 | Medium | Base Enlist March substitutes an unselected Hidden Warband for the accepted Scouted selection |
| UI10-03 | Medium | Hash-dependent Quarters Supply request blocks replay of an accepted human decision |
| NP10-01 | Medium | Ordinary Arverni spread March omits newly enabled Entreat |
| NP10-02 | Medium | Existing Devastated marker incorrectly blocks a later bot Devastate |

## Validation

- **10,279 existing tests pass**, no failures, errors or skips; 126.34 seconds, four workers. Five external anyio/pytest deprecation warnings are preserved.
- **20/20 audited bot games complete**, second-edition seeds 53–56 across all five scenarios. Three Gallic War Interludes; zero errors, inventory/structure findings or ranking issues. All 150 diagnostic groups / 388 occurrences are legal declines.
- **20 mixed-player cases** repeated at hash seeds 0/987 with internal replay: 80 executions, byte-identical JSON and stdout, 560 human turns and 130 Event turns per sample, 118 completed Events, zero hard findings. One matching soft partial plan is retained: The Gallic War seed 54. Its game completes; it is not counted as a successful complete human plan.
- Both audited-parent GitHub checks passed: [CI](https://github.com/FeeSimple1/fs-bot/actions/runs/43456831173) and [Package installation](https://github.com/FeeSimple1/fs-bot/actions/runs/43456831204). These identify the audited source revision, preceding the documentation commit.
- No new balance matrix or baseline refresh. The full suite includes the existing 15-game balance canary. Sampled games and general tests do not establish complete rules coverage.

## Suggested repair sequence

| Batch | Findings | Scope |
|---|---|---|
| 1 | EV10-01, EV10-02 | Closed. [Bellovaci and Siege of Bibrax](tenth-comparison-batch1-2026-11-13.md). |
| 2 | BM10-01 | Closed. [Abatis protection in Battle forecasts](tenth-comparison-batch2-2026-11-13.md). |
| 3 | LC10-01 | Closed. [Adjacent Roman Quarters in Provincia](tenth-comparison-batch3-2026-11-13.md). |
| 4 | UI10-01, UI10-02, UI10-03 | Open. Completed Special Ability summaries, exact Enlist March cohorts and durable Quarters decisions. |
| 5 | NP10-01, NP10-02 | Open. Arverni post-spread-March abilities and repeated Devastate. |

Turn each confirmed failure into a source-derived regression and retain its controls. Run the full suite and appropriate bot, human-session and replay checks after repairs. Explain any changed game outcomes before revising a balance baseline.

## Finding details

### EV10-01 — Bots play conditional Bellovaci and Siege of Bibrax Events when their prerequisite is false

Closed in [Batch 1](tenth-comparison-batch1-2026-11-13.md). Medium priority.

**Expected:** Per §8.1.1, NP Belgae decline A69 shaded unless Bellovaci is a Belgic Ally. NP Romans/Aedui decline A51 unshaded unless Remi is Roman/Aedui Allied or Subdued. With either printed prerequisite false, the entire chosen side has no effect and its ordinary flowchart must continue.

**Observed:** In both Ariovistus and the first half of Gallic War, public dispatch_bot_turn selects A69 shaded with Bellovaci Subdued or Aedui Allied, and A51 unshaded for Romans/Aedui with Remi Belgic Allied. Public execute_decision reports executed=true with no tracked game-effect field changed. Eight canonical scenario-based failing cases pass complete pre/post census and structural checks. All eight matched Event-disabled controls execute an ordinary non-Pass Command with effects.

**Cause:** should_decline_event consults np_event_available and generic flags. Neither conditional side has a specific prerequisite guard. A69 FREE_BATTLE yields unconditional true; A51 Available Auxilia yields true regardless of Remi. Both handlers themselves correctly return before effects when the printed Tribe condition fails.

**Sources:** [Reference Documents/Ariovistus/Chapter A8:1–10](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/Ariovistus/Chapter%20A8#L1); [Reference Documents/Chapter 8:30–46](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/Chapter%208#L30); [Reference Documents/Ariovistus/A Card Reference:231–236](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/Ariovistus/A%20Card%20Reference#L231); [Reference Documents/Ariovistus/A Card Reference:316–321](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/Ariovistus/A%20Card%20Reference#L316)

**Implementation:** [fs_bot/bots/bot_common.py:373–381](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/bots/bot_common.py#L373); [fs_bot/cards/event_conditions.py:13–137](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/cards/event_conditions.py#L13); [fs_bot/cards/event_eval.py:746–751](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/cards/event_eval.py#L746); [fs_bot/cards/event_eval.py:813–818](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/cards/event_eval.py#L813); [fs_bot/cards/event_eval.py:1073–1081](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/cards/event_eval.py#L1073); [fs_bot/cards/event_eval.py:1139–1146](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/cards/event_eval.py#L1139); [fs_bot/cards/card_effects.py:3346–3357](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/cards/card_effects.py#L3346); [fs_bot/cards/card_effects.py:3691–3702](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/cards/card_effects.py#L3691)

**Controls:** Six original-physical-setup positive cases across both scenarios: A69 adds six Warbands and resolves its Ambush; A51 places four troops and a Fort, removes the existing Belgic Warband. Eight matched can_play_event=False controls execute their normal non-Event Commands and preserve census/structure. Availability queries are asserted board/RNG pure. Both sides are executed via their natural public NP plan, not manual handler invocation.

**Earlier-audit distinction:** BE7-03 was the A18 nearby-Legion condition; EV9-02 was numeric33 Fallen/destination/Warband applicability. Neither covers A51/A69. Original EXP-08 fixed human A51 optional removal quantities, not NP Event admission. EX2-02 fixed exact A51 shaded Allied-Tribe removal. EX4-02 covered A69 unshaded owner/type consistency; EXP-04 covered shaded A69 Ambush target choice. No prior finding is reopened.

**Repair scope:** Share these printed prerequisite predicates between handler and NP effectiveness checks, and add public dispatch/execution regressions for both expansion scenarios. Preserve humans' legal choices and optional/partial execution. Treat A51 recipient planning separately (EV10-02).

**Limits:** Only the named prerequisite-false cases are proven; no universal Event-effectiveness claim, natural encounter frequency, end-to-end full-game claim, or exhausted-stock policy claim. Census-valid physical positions start from production setup_scenario; changes use _unally_tribe/_ally_tribe. The no-effect comparison includes spaces, tribes, pools, resources, Senate, Legion track/Fallen/removed, markers, capabilities/owners, eligibility, forced/stay eligibility and Event modifiers.

**Evidence:** `events/probe_events.py`; `events/results.json` in the archive.

### EV10-02 — Non-player Aedui give Siege of Bibrax troops to Romans despite Available Aedui Warbands

Closed in [Batch 1](tenth-comparison-batch1-2026-11-13.md). Medium priority.

**Expected:** A51 unshaded offers four Roman Auxilia or Aedui Warbands. §8.2.3 requires NP Aedui to choose their own Event benefit. With at least four own Warbands Available and Remi legal, they must place four Aedui Warbands, while retaining the printed Roman Fort and enemy removals.

**Observed:** On original physical Ariovistus and Gallic War setups, natural NP Aedui Event dispatch/execution places four Roman Auxilia and zero Aedui Warbands, with 17 Aedui Warbands Available. This reproduces with Romans either NP or human. Four matched explicit human A51 Warband choices each place four Aedui Warbands and zero Roman Auxilia. All before/after census/structure checks pass.

**Cause:** _derive_event_params has no unshaded A51 producer, and the deriver table omits A51. The handler uses params.get(piece_type, AUXILIA), converting a human-compatible legacy default into the NP Aedui recipient choice. The optional-quantity resolver only chooses later removals and cannot correct the compulsory prefix.

**Sources:** [Reference Documents/Ariovistus/Chapter A8:1–10](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/Ariovistus/Chapter%20A8#L1); [Reference Documents/Chapter 8:120–135](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/Chapter%208#L120); [Reference Documents/Ariovistus/A Card Reference:231–236](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/Ariovistus/A%20Card%20Reference#L231); [Reference Documents/Ariovistus/aedui_bot_event_instructions_ariovistus.txt:1–49](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/Ariovistus/aedui_bot_event_instructions_ariovistus.txt#L1)

**Implementation:** [fs_bot/engine/execute.py:5967–6012](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/engine/execute.py#L5967); [fs_bot/engine/execute.py:6568–6609](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/engine/execute.py#L6568); [fs_bot/cards/card_effects.py:3358–3369](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/cards/card_effects.py#L3358); [fs_bot/cards/expansion_up_to.py:15–28](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/cards/expansion_up_to.py#L15)

**Controls:** Four explicit human Warband plans on identical boards place four Aedui Warbands; the whole Event remains otherwise functional. NP Romans on original setup correctly receive four Auxilia; this distinguishes missing Aedui derivation from a generic placement failure. Both expansion scenarios and Roman human/NP seat variants reproduce; no A51 exception appears in the supplied Aedui instruction table.

**Earlier-audit distinction:** BE6-02 A35/A60 and BE7-02 A19/A26 were missing NP parameter producers on different Events. EV9-01 was A40 Allied-Tribe-first priority and EV9-03 its Cisalpina recipient stacking. Original EXP-08 A51 work intentionally addressed human optional removal quantities and Scouted casualties; its compulsory prefix remained unchanged. EX2-02 was the other, shaded A51 side. EV10-01 only addresses when A51 can act; fixing that admission predicate cannot fix this wrong recipient on a legal Event.

**Repair scope:** Derive unshaded A51 troop ownership explicitly for NP Romans/Aedui before the mandatory prefix, retaining human choice and correct Roman Fort/removal behavior. Cover both expansion scenarios and Roman seat variants, and inspect own-stock boundaries under §§5.1.3 and 8.2.3 without silently selecting another faction.

**Limits:** Proves adequate own stock (17 Available) only. Does not independently classify zero/scarce-stock A51 behavior or human legacy-default semantics. No claim of natural frequency or broader NP Event-benefit completeness.

**Evidence:** `events/probe_events.py`; `events/results.json` in the archive.

### BM10-01 — Canceled Abatis makes Divination skip a required Aedui Battle

Closed in [Batch 2](tenth-comparison-batch2-2026-11-13.md). Medium priority.

**Expected:** After public A64 Belgic Abatis then shaded A31 Stalwart, A34 unshaded naming non-player Aedui must select German Battle: Ariovistus plus two Warbands inflicts four standing or two Retreat Losses on two Belgic Warbands plus the Aulerci Ally, guaranteeing a high-value Loss in either stance.

**Observed:** Accepted public A34 instead Marches one German Warband from Carnutes to Pictones and preserves both Belgic Warbands and Aulerci. The raw formula predicts two standing/one Retreat Losses while actual public Battle executes four/two and removes Aulerci.

**Cause:** calculate_losses treats the raw enemy Abatis marker as an active Fort when suppressing Ariovistus doubling, bypassing defender_abatis_active. Divination's A4 high-value gate consumes this stale forecast and returns no Battle before reaching the accurate resolver-backed forecast.

**Sources:** [Reference Documents/Ariovistus/A Card Reference:126–131](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/Ariovistus/A%20Card%20Reference#L126); [Reference Documents/Ariovistus/A Card Reference:146–150](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/Ariovistus/A%20Card%20Reference#L146); [Reference Documents/Ariovistus/A Card Reference:288–292](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/Ariovistus/A%20Card%20Reference#L288); [Reference Documents/Ariovistus/Chapter A3:118–131](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/Ariovistus/Chapter%20A3#L118); [Reference Documents/Chapter 3:311–323](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/Chapter%203#L311); [Reference Documents/Chapter 8:105–118](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/Chapter%208#L105); [Reference Documents/Chapter 8:448–462](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/Chapter%208#L448)

**Implementation:** [fs_bot/battle/losses.py:267–282](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/battle/losses.py#L267); [fs_bot/battle/losses.py:69–78](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/battle/losses.py#L69); [fs_bot/cards/divination_np.py:69–83](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/cards/divination_np.py#L69); [fs_bot/cards/divination_np.py:105–110](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/cards/divination_np.py#L105); [fs_bot/cards/divination_np.py:714–720](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/cards/divination_np.py#L714); [fs_bot/battle/resolve.py:413–414](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/battle/resolve.py#L413); [fs_bot/battle/resolve.py:459–462](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/battle/resolve.py#L459)

**Controls:** No Abatis with Stalwart: A34 correctly selects Battle and removes all three Belgae. Neither Abatis nor Stalwart: A34 correctly selects Battle and removes all three Belgae. Abatis without Stalwart: effective protection correctly gives one Loss and selects March. Abatis then Stalwart without Ariovistus: one Loss correctly selects March. Public ordinary Battle standing: four Losses, Aulerci removed, inert Abatis remains. Public ordinary Battle with legal Retreat declaration: two Losses, Aulerci removed first, inert Abatis remains. All before/after census and structure checks clean; public Event/Command responses validate; no piece-count mutations or mocks.

**Earlier-audit distinction:** docs/reviews/comparison-audit-round7-2026-11-11.md:290–292 explicitly excluded A31/Abatis forecast drift for lack of a finalized public consequence. This finding supplies that consequence in public A34 dispatch. BM5-02 concerns human casualty selection, while BM5-01/BM6-01/BM7-02 concern different capability consumers; none counted this forecast gate.

**Repair scope:** Use effective defender Abatis protection, including A31 cancellation, in calculate_losses' Ariovistus-doubling branch. Preserve real Fort/Citadel and counterattack rules. Add public A34 decision regression and parity controls; review other callers without pre-counting unproved symptoms.

**Limits:** Controlled legal Ariovistus state, not natural-game frequency. Confirms A34's Aedui beneficiary with earlier enemy Abatis/later Stalwart. No new ruling or broader capability, ownership, chronology or event-consumer claim.

**Evidence:** `battle/probe_battle.py`; `battle/results.json`; `battle/report.md` in the archive.

### LC10-01 — Roman Quarters rejects legal adjacent relocation into an agreeing faction's Provincia

Closed in [Batch 3](tenth-comparison-batch3-2026-11-13.md). Medium priority.

**Expected:** Under Chapter 6 §6.3.3, Romans may first move mobile pieces to any adjacent undevastated Region controlled by Rome or an agreeing eligible faction. This includes Aedui-controlled Provincia. The later transfer from Supply Line Regions to Provincia is a separate permission. A Roman Legion in German-controlled Arverni may therefore move directly to adjacent Aedui-controlled Provincia if the Aedui agrees, without a Supply Line through its German-controlled origin.

**Observed:** Both public validate_quarters_plan and quarters_phase reject the canonical willing-host fixture with 'Arverni has no agreed Supply Line to Provincia'. No host agreement request occurs. The Legion stays in Arverni and Roman Resources remain 10. The same blocked origin can relocate to Roman-controlled Provincia or to agreeing Aedui-controlled Sequani. A supplied origin can reach Aedui-controlled Provincia. A second pair starts from actual Pax setup and invokes public run_winter_round: the willing-Aedui Provincia position raises the same error and rolls back the complete Winter, while Roman-controlled Provincia completes all Winter phases. Both retain the printed first-Winter Victory/Germans skips.

**Cause:** preview_relocations classifies every Roman move whose destination is Provincia as the later Provincia step, bypassing the ordinary adjacent-step host validation and agreement branch. Its direct-adjacent escape clause only recognizes Roman Control at Provincia. _provincia_options repeats the same Roman-only fallback for live continuation choices.

**Sources:** [Reference Documents/Chapter 6:84–98](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/Chapter%206#L84); [Reference Documents/Chapter 3:29–37](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/Chapter%203#L29)

**Implementation:** [fs_bot/engine/quarters.py:224–231](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/engine/quarters.py#L224); [fs_bot/engine/quarters.py:245–258](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/engine/quarters.py#L245); [fs_bot/engine/quarters.py:312–323](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/engine/quarters.py#L312); [fs_bot/engine/quarters.py:365–376](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/engine/quarters.py#L365); [fs_bot/engine/winter.py:370–374](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/engine/winter.py#L370); [fs_bot/engine/winter.py:409–428](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/engine/winter.py#L409)

**Controls:** Roman-controlled Provincia with the same German-controlled adjacent origin: validation succeeds and phase moves the Legion, Resources stay 10. Aedui-controlled Sequani, an ordinary adjacent destination, with agreeing host: validation succeeds, quarters agreement is requested, Legion moves and pays two Resources. The same Sequani destination with refusing host: validation admits the conditional move, actual phase asks and rejects it; state and RNG restore. Aedui-controlled Provincia with refusing host: rejected before consent is asked, showing the willing/denying host distinction is erased at validation. Nonadjacent German-controlled Nervii origin to Aedui-controlled Provincia: correctly rejected without a Supply Line. Roman-controlled supplied Arverni origin to Aedui-controlled Provincia: validation and execution succeed under the later Supply Line route. Actual Pax setup, seed 11, plus canonical one Legion/five German Warbands in Arverni and four Aedui Warbands in Provincia (failure) or Veneti (Roman-control success): public run_winter_round confirms the failure is reachable under printed first-Winter rules; full-Winter success consumes Winter 1 and moves the Legion. Both clean before/after; failure restores the entire board and RNG.

**Earlier-audit distinction:** WS-F05 covered choosing exact Quarters visibility cohorts; WS7-01 connected non-Roman NP Quarters planning; LC9-01 fixed Roman NP destination-payment overwrite after arrival. LC10-01 is the separate core legality/consent distinction between an adjacent move into Provincia and the later supply-based Provincia transfer. It does not depend on NP planning or payment allocation.

**Repair scope:** Represent or resolve Provincia's adjacent-step permission separately from its later Supply Line transfer. Permit eligible agreeing destination controllers in the adjacent step, obtain that host's Quarters agreement, preserve its original-cohort and simultaneous destination-Control checks, then freeze Supply Lines after all adjacent moves. Apply equivalent legality to normal validation, execution, and live Provincia continuation choices; retain negative controls for refusal, No/German Control and unsupplied nonadjacent origins.

**Fixture:** Canonical build_initial_state(Great Revolt, seed=11), permanent Roman Fort in Provincia, one tracked Legion placed at Arverni, two German Warbands there for Germanic Control, two Aedui Warbands in Provincia for Aedui Control, 10 Roman Resources, all human seats, explicit no-relocation plans for the other factions. No Devastation, capabilities, leaders, Harassment, monkeypatches, test doubles, or noncanonical piece counts. All seven before/after census and structural checks pass; rejected cases restore board and RNG. Added actual Pax setup whole-Winter pair preserves every original setup piece and first_winter_special flag; the only changes are canonical placements of one tracked Legion and five German Warbands in Arverni and four Aedui Warbands in Provincia or Veneti.

**Limits:** One core defect group proven through public Quarters validation, phase execution and a complete run_winter_round entry point on actual Pax first-Winter setup with canonical extra pieces. No encounter-rate claim or terminal/assistant UI menu reproduction. Expansion behavior was inspected but not separately reproduced. No production edits.

**Evidence:** `lifecycle/probe_lifecycle.py`; `lifecycle/results.json`; `lifecycle/results.hash0.json`; `lifecycle/results.hash987.json`; `lifecycle/report.md` in the archive.

### UI10-01 — Completed CLI summaries report forecast Special Abilities instead of actual execution

**Status:** Open. **Priority:** medium.

**Expected:** Resolved-card output names the executed Entreat in Carnutes and does not claim a declined Build occurred.

**Observed:** Ordinary make_decision_func/play_card/display_card_result Card20 omits the actually executed post-Raid Entreat and prints forecast Build despite sa_execution.executed=false. Physical results and effective sequence options are correct.

**Cause:** display_card_result renders the original action via format_action, which reads forecast sa/sa_regions; execution SA fields are never consumed.

**Sources:** [Reference Documents/Chapter 8:732–744](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/Chapter%208#L732); [CLAUDE.md:176–186](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/CLAUDE.md#L176)

**Implementation:** [fs_bot/cli/app.py:146–202](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/cli/app.py#L146); [fs_bot/cli/display.py:626–649](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/cli/display.py#L626); [fs_bot/cli/app.py:670–671](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/cli/app.py#L670)

**Controls:** Funded Rally forecast Entreat matches execution and prints correctly Targetless Raid has no actual Entreat and prints none All before/after census and structure clean Hash seeds 0/987 outputs identical

**Earlier-audit distinction:** NP9-02 repaired actual post-Command SA chaining; this is its stale completed CLI consumer. UI9-02 was pending Morbihan physical-board presentation.

**Repair scope:** Render actual completed SA outcome/regions and distinguish no-effect forecast from execution; preserve forecasts, Event text, Battle-integrated abilities, and human-authored plans.

**Limits:** Curated legal sparse Card20 fixtures; final summary reporting defect only. No incorrect physical resolution, durable-result loss, natural frequency or balance claim.

**Evidence:** `frontend/probe_frontend.py`; `frontend/results.json`; `frontend/results.hash0.json`; `frontend/results.hash987.json`; `frontend/report.md` in the archive.

### UI10-02 — Base Enlist March substitutes an unselected Hidden Warband for the accepted Scouted selection

**Status:** Open. **Priority:** medium.

**Expected:** Explicitly selected Scouted German moves Carnutes→Mandubii Revealed after losing its marker; unselected Hidden German stays Hidden at origin.

**Observed:** All three base scenarios validate and accept the explicit selection, then move the unselected Hidden German and leave the selected de-Scouted Revealed German behind. Same choice works in both expansion scenarios. Base terminal menu offers only a total.

**Cause:** Base _force_scope is null; execute_free_enlist validates visibility counts but after flipping discards them for a total, so march_group uses Hidden-first legacy fallback. Base terminal collector also lacks visibility choices.

**Sources:** [Reference Documents/Chapter 3:354–358](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/Chapter%203#L354); [Reference Documents/Chapter 4:83–86](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/Chapter%204#L83); [Reference Documents/Chapter 4:215–222](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/Chapter%204#L215)

**Implementation:** [fs_bot/commands/enlist_free.py:17–60](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/commands/enlist_free.py#L17); [fs_bot/commands/enlist_free.py:159–175](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/commands/enlist_free.py#L159); [fs_bot/commands/march.py:832–860](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/commands/march.py#L832); [fs_bot/cli/human_plan.py:927–930](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/cli/human_plan.py#L927)

**Controls:** Seven validated/session-accepted public-execution cases: three base failures, two expansion successes, base Hidden selection success, base lone-Scouted success Pending decision ID retained after save/load and exact visibility choice retained in committed journal Exact saved-choice execution repeat returns same result and board Terminal planning board unchanged Before/after census and structure clean; hash seeds 0/987 outputs identical

**Earlier-audit distinction:** FE6-02 added multiple Ariovistus Enlist destinations; FE7-01 rejected multiple base groups despite Surus. This is the facing of a counter in one legal base group, not group count or borrowing.

**Repair scope:** Translate selected pre-flip counts into post-flip movement visibility, preserving the mandatory flip of every base origin Warband, including stayers. Expose base CLI visibility choices. Retain one-group base limit, expansion four-piece budget, geography and legacy integer/default compatibility.

**Limits:** Curated legal sparse fixtures. Session pending/save-load/validation/acceptance followed by public execute_decision; saved-choice repeat is not the full verified-replay CLI. Terminal witness is production Enlist collector. No natural frequency or balance claim.

**Evidence:** `frontend/probe_frontend.py`; `frontend/results.json`; `frontend/results.hash0.json`; `frontend/results.hash987.json`; `frontend/report.md` in the archive.

### UI10-03 — Hash-dependent Quarters Supply request blocks replay of an accepted human decision

**Status:** Open. **Priority:** medium.

**Expected:** A saved accepted Supply agreement replays and returns to the same later pending transfer request after process restart, independent of PYTHONHASHSEED.

**Observed:** Hash0 records accepted d000002 Supply agreement with representative Veneti and pauses at real d000003 after-payments transfer. Save/load hash0 resumes; hash987 fails replaying d000002 with Saved decision no longer matches its board/request; replay stopped. A one-host-Region legal control resumes under both hashes.

**Cause:** quarters.py selects regions[0] from a host list built from a playable Region set. context.region enters the full durable request fingerprint; no agreement-region compatibility normalization exists.

**Sources:** [Reference Documents/Chapter 6:84–90](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/Chapter%206#L84); [CLAUDE.md:183–186](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/CLAUDE.md#L183)

**Implementation:** [fs_bot/engine/quarters.py:59–69](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/engine/quarters.py#L59); [fs_bot/engine/quarters.py:221–221](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/engine/quarters.py#L221); [fs_bot/engine/quarters.py:274–281](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/engine/quarters.py#L274); [fs_bot/tools/seat_session.py:41–70](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/tools/seat_session.py#L41); [fs_bot/tools/seat_session.py:518–537](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/tools/seat_session.py#L518)

**Controls:** Same-hash actual session journal/save-load resumes to d000003 Single controlled host Region succeeds across hash0/987 without production request normalization Actual later resource-transfer prompt creates transaction interruption; no injected exception Every record/resume retains exact board/RNG and clean census/structure

**Earlier-audit distinction:** Earlier Trade determinism repair (docs/current-status.md:2844; test_trade_determinism.py) concerns visible earnings list order. LC10-01 concerns Provincia adjacent hosting. No earlier comparison finding covers Quarters Supply request representative selection and durable signature mismatch.

**Repair scope:** Use stable semantically defined Supply request context and narrowly support already saved equivalent Quarters consent signatures. Preserve real board/host/action mismatch checks and region-specific agreements; do not globally ignore context.region.

**Limits:** Sparse legal paired Roman+Aedui player fixture with public quarters_phase, SeatSession and existing _action_transaction hooks. Demonstrates actual saved-journal resume failure, not a full llm_seat replay CLI or naturally sampled Winter. Physical outcomes remain correct and rollback clean.

**Evidence:** `frontend/probe_quarters_replay.py`; `frontend/quarters-replay-results.json`; `frontend/report.md` in the archive.

### NP10-01 — Ordinary Arverni spread March omits newly enabled Entreat

**Status:** Open. **Priority:** medium.

**Expected:** After spread March creates a Hidden Warband and leader-range opportunity at Carnutes, Devastate then Entreat must be evaluated after movement and cost; one Auxilium becomes an Arverni Warband for one Resource.

**Observed:** Full dispatch chooses March with No SA, translation selects command, and execution moves Vercingetorix plus eight Warbands Mandubii to Carnutes for one Resource. It leaves eight Hidden Warbands, one Roman Auxilium and three Resources, although the resulting live chooser selects Entreat. The source-required action yields nine Warbands, zero Auxilia and two Resources.

**Cause:** Ordinary spread March chooses the SA on the pre-movement state and carries no post-command marker. Translation chooses Command only; the post-command helper only rederives Rally/Raid and generic SA execution returns immediately for No SA.

**Sources:** [Reference Documents/Chapter 8:730–731](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/Chapter%208#L730); [Reference Documents/Chapter 8:645–675](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/Chapter%208#L645); [Reference Documents/Chapter 4:107–120](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/Chapter%204#L107)

**Implementation:** [fs_bot/bots/arverni_bot.py:1063–1075](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/bots/arverni_bot.py#L1063); [fs_bot/cli/dispatcher.py:87–105](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/cli/dispatcher.py#L87); [fs_bot/engine/execute.py:164–177](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/engine/execute.py#L164); [fs_bot/engine/execute.py:4806–4808](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/engine/execute.py#L4806)

**Controls:** Same dispatch-produced March with authored source-required Entreat succeeds through public execution. Command-only, one Resource exhausted by March, and absent target controls do no SA. Every case passes pre/post census and structure; planning leaves board and RNG unchanged.

**Earlier-audit distinction:** NP9-02 fixed Arverni Rally and Belgic Raid; this is an uncorrected ordinary March consumer. NP8-02 was Aedui Rally. FE5-01 was Britannia prohibition and FE5-02 drop-offs. Threat March already has its own before/after chain and is not counted.

**Repair scope:** Carry authorized live post-Command SA intent through ordinary Arverni March planning, translation and execution, preserving genuine Command-only, actual movement/cost, regional grants, one-SA and Britannia restrictions. Inspect mass/Belgic March neighbors without claiming them proved here.

**Limits:** Controlled Great Revolt seed6 fixture, permanent Provincia Fort, canonical physical helpers. No combat/capabilities/Event/Britannia/human callback/whole-game frequency claim. Positive authored-SA control is distinguished from natural dispatch.

**Evidence:** `bots/probe_bots.py`; `bots/results.json`; `bots/report.md` in the archive.

### NP10-02 — Existing Devastated marker incorrectly blocks a later bot Devastate

**Status:** Open. **Priority:** medium.

**Expected:** A new Command's Devastate may select a previously Devastated, Arverni-Controlled in-range Region and apply mandatory losses without adding another marker. Six Arverni Warbands versus four Legions force one Legion loss and meet the bot priority.

**Observed:** Canonical prior Devastate turns eight Warbands/six Legions into six/four and sets the Bituriges marker. Full later Rally dispatch and live SA chain decline Devastate. A legal canonical repeat removes one Warband and one Legion with devastated_placed=false; the matched no-marker public turn executes those losses normally.

**Cause:** _check_devastate skips already-Devastated Regions before canonical control/range validation and mandatory casualty calculation. Persistent marker presence is incorrectly used as an ability prohibition.

**Sources:** [Reference Documents/Chapter 4:121–131](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/Chapter%204#L121); [Reference Documents/Chapter 8:645–655](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/Chapter%208#L645); [Reference Documents/arverni_bot_flowchart.txt:258–277](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/Reference%20Documents/arverni_bot_flowchart.txt#L258)

**Implementation:** [fs_bot/bots/arverni_bot.py:1254–1270](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/bots/arverni_bot.py#L1254); [fs_bot/commands/sa_devastate.py:29–57](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/commands/sa_devastate.py#L29); [fs_bot/commands/sa_devastate.py:103–109](https://github.com/FeeSimple1/fs-bot/blob/ae238c6482a792dda98af4f1f9b11abf820a3964/fs_bot/commands/sa_devastate.py#L103)

**Controls:** Matched no-marker full public turn executes one Warband/one Legion loss. Command-only and out-of-range controls retain the pieces. A clone of the post-Rally state, with Arverni switched to a human seat, publicly executes authored Raid+Devastate and removes one Warband/one Legion from the marked Region. Additional canonical repeat is valid and places no duplicate marker. All fixture preparation and pre/post checks have clean census/structure, and dispatch is board/RNG-pure.

**Earlier-audit distinction:** NP9-01 fixed casualty quota forecasting and kept the existing-marker exclusion outside scope. CM2-03 forbids duplicate Region entries within a single ability. This finding concerns a different later ability, not repeated entries, marker duplication, or casualty ownership.

**Repair scope:** Remove the extra marker-based bot exclusion; preserve canonical control/range checks, forced casualty thresholds, marker idempotence and per-ability Region uniqueness. Add previous-Devastate then later-Command regression with controls.

**Limits:** Controlled base-game fixture; canonical previous Devastate is fixture setup, not a full narrated prior turn. The defective later turn uses real dispatch/translation/public executor. No expansion, frequency or balance claim.

**Evidence:** `bots/probe_bots.py`; `bots/results.json`; `bots/report.md` in the archive.

## Reproduction and exclusions

Extract the evidence and run `python run_witnesses.py --repo /path/to/fs-bot` with the audited Python source bytes. The runner verifies the source digest and protected files, runs six probes at hash seeds 0/987 in temporary working directories and compares their output with the preserved JSON for each hash. The lifecycle raw variation is retained; the separate replay probe explicitly records and resumes across both hash seeds. These assertions characterize the observed defects and should change after repair. `SHA256SUMS` covers every other archive member. Each lane report gives its bounds and excluded leads; validation logs and full game records are preserved.

Known Circumvallation persistence work, the documented Aedui subsidy approximation and existing unresolved source questions remain separate. No new ruling is needed for these nine findings. A delegated-human late-ability gate lead lacked a demonstrated failure and is excluded. Other inspected Winter, victory, automatic-phase and capability boundaries produced no additional counted defect in this pass. The earlier current-Event/Stalwart exclusion remains valid; BM10-01 uses an earlier Abatis followed by later Stalwart and then Divination.

No engine repair, encounter-rate estimate, balance conclusion or bug-free claim follows from this audit.
