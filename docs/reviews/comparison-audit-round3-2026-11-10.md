# Third Falling Sky comparison audit — 10 November 2026

Batches 1 and 2 repair seven findings. The [latest repair report](third-comparison-batch2-2026-11-10.md)
and [ledger](comparison-audit-round3-2026-11-10.json) record **7 of 15 repaired
(47%), with 8 remaining**. The [Batch 1 report](third-comparison-batch1-2026-11-10.md)
retains its original measurements.

**The audit confirmed 15 additional repair groups — 14 high and 1 medium priority.** The evidence below records the audit revision. The previous 50-finding and 21-finding ledgers remain fully closed. Known Circumvallation persistence work and unresolved source questions are tracked separately.

Falling Sky was audited at `3c23a3414c3e870e274ef63c278db8cb3f1ee747` with Python-source SHA-256 `7f75a00ebd5200960a71fa822bdfddb47f2e092f5edbf58c145f6f70a5db226e` across 578 Python files. Liberty or Death was inspected at `2991ea279062773548ec390a1da75f3e85381702`. Its engineering patterns guided the search; Falling Sky’s supplied references and adopted provisional rulings govern the conclusions.

[Finding ledger](comparison-audit-round3-2026-11-10.json) · [Portable evidence](comparison-audit-round3-2026-11-10-evidence.zip) · [Current status](../current-status.md#10-november-third-comparison-audit)

## Method and coverage

| Comparison pattern | Checks in this pass |
|---|---|
| Engine-owned action history and eligibility | Submitted turn metadata, accepted choices after a pause, actual end-of-card eligibility |
| Validate the actual executed action | Scenario geography, physical attacker presence, exact Ally identity, ungranted Battle modifiers |
| Read printed effects rather than only existing hooks | Mandatory placement minima, forced Ambush exceptions, Scouted pieces, marker replacement |
| Trace writes to final consumers | Harvest arithmetic, Lost Eagle lifetime, dynamic Colony Tribes, permanent Razed markers, capability cancellation |

Relevant comparator material includes `lod_ai/engine.py`, `lod_ai/event_choices.py`, `lod_ai/util/eligibility.py`, `coin-implementation-lessons.md`, `docs/human_mode_audit.md`, and `docs/audit_set_but_never_applied_s76.md`. The archive contains partition coverage and rejected leads.

Related symptoms are counted together. Eligibility and journal collisions form one input-metadata group. Consuetudine’s missed Ambush and Scouted clauses form one Event group. Colony consumers across Commands, Events, and scoring form one group; partition IDs BE3-02 and EX3-02 are absorbed into XC3-01. Failure to create the Colony under scarce supply remains separate.

## Confirmed findings

| ID | Priority | Finding |
|---|---|---|
| FE3-01 | high | Authored turn metadata can override Eligibility and accepted decisions during resume |
| CM3-01 | high | Scout moves Roman Auxilia into nonplayable base-game Cisalpina |
| CM3-02 | high | Entreat can target a Citadel City and remove a different Tribe’s Ally disc |
| CM3-03 | high | Ordinary Battle accepts a Region with no attacking pieces and Reveals enemies there |
| CM3-04 | high | Authored ordinary Battle plans can grant themselves Event-only combat powers |
| WS3-01 | high | Harvest counts each Gallic Citadel twice |
| WS3-02 | high | Lost Eagle restricts Senate changes outside its printed window |
| BE3-01 | high | Consuetudine omits its forced Ambush exception and Scouted hide step |
| BE3-03 | high | Colony fails to create its Tribe when the executing Ally pool is empty |
| BE3-04 | high | Shaded Migration allows relocation while omitting its mandatory possible Ally |
| EX3-01 | high | Harudes shaded accepts omitted mandatory reinforcements |
| EX3-03 | medium | Nasua and Cimberius fails to replace a Dispersed marker at Treveri |
| EX3-04 | high | Stalwart does not cancel Germanic Horse doubling against Germans |
| XC3-01 | high | Existing Colony Tribes are ignored by Commands, Events, and Belgic scoring |
| XC3-02 | high | Seize treats Razed Cities as Subdued and replaces their permanent marker |

High means an illegal action, material wrong effect, lost accepted choice, or inconsistent state. Medium marks a narrower printed-effect failure. These labels prioritize repairs; they are not estimates of frequency.

## Verification

- All **9,411 existing tests passed**, with no failures, errors or skips.
- All **eight final witness scripts** passed independent reruns and the portable runner. Their assertions freeze observed defects and should become source-derived regression assertions during repairs.
- **20 mixed-seat cases**, seeds 21–24 in all five scenarios, matched exactly under hash seeds 0 and 987 with replay enabled. This represents 80 game executions across the two hash runs and their internal replays.
- Each hash run recorded **626 human turns**, **146 Event attempts**, **130 executed Events**, **zero hard findings**, and **four soft partial plans**. These are general fuzz results; they do not exercise every authored boundary in this audit.
- No new balance or all-bot matrix was run. Engine and reference files are unchanged.

The frontend witnesses initialize ordinary file sessions. Other probes use controlled initialized positions, with fixture adjustments disclosed. The Entreat witness begins with clean inventory and structure and ends with the expected allegiance corruption. The Dispersed Colony scoring witness assigns a rules-legal marker because Seize currently rejects that Tribe. Some Colony checks call production action primitives after validating their prerequisites.

The journal witness does **not** report a replay failure. The accepted Recruit becomes Pass during resume, and replay faithfully repeats the substituted action. The Lost Eagle expiry witness exercises the first Pax Senate; the analogous post-Interlude early return is static corroboration only. An exploratory eligibility assertion about the next offered card was corrected; both the superseded attempt and final end-card observation are preserved.

## Suggested repair batches

1. Protect authored input and board integrity — FE3-01, CM3-02, CM3-04.
2. Correct action boundaries and seasonal calculations — CM3-01, CM3-03, WS3-01, WS3-02.
3. Complete printed Event effects — BE3-01, BE3-03, BE3-04, EX3-01, EX3-03.
4. Unify dynamic Tribe and persistent effect handling — XC3-01, XC3-02, EX3-04.

Each repair needs its failing witness converted to legal expected behavior, focused checks, and the required integrated validation. The audit does not certify unexamined combinations.

## Evidence by finding

### FE3-01 — Authored turn metadata can override Eligibility and accepted decisions during resume

**Expected.** Only player-owned action fields may influence a submitted turn. An ordinary Recruit makes its executor Ineligible. A pause and resume must preserve the exact accepted Command and its engine-owned journal identity.

**Observed.** validate_response returns an arbitrary top-level turn object unchanged. resolve_card_turn stores that object as action history, where free_action is trusted for Eligibility. SeatSession.ask also merges the object over its freshly constructed journal entry, allowing assistant_response to replace the accepted response that will be replayed on resume.

**Rule basis.** Reference Documents/Chapter 2, §§2.3.1 and 2.3.6, lines 27-31 and 68-76; Reference Documents/Chapter 3, §3.1.2, lines 15-19; CHATGPT_README.md lines 251-262, documented accepted-choice and durable-history contract.

**Relation to earlier work.** New boundary within the same general authored-input class as FE2-01/FE2-02 and XC2-01. Those repairs bind inner plan type/current card and command scope; they do not reserve top-level execution/journal metadata. No earlier closed finding or Circumvallation follow-up is recounted. Both effects are conservatively grouped because they share arbitrary top-level metadata admission.

- `unauthorized_free_action` — With top-level free_action=true, the same ordinary Recruit places the same Auxilia but Romans become Eligible at completion of card 16.
- `journal_response_collision` — The initial Recruit is accepted, but its normal pause and resume reads the caller-overwritten journal assistant_response and executes Pass instead. Provincia remains at 6 Auxilia. End-card16 action is Pass, next human turn is card45, and the durable log still presents action=command with the Recruit player_action while assistant_response={action:pass}. Replay verifies the substituted behavior because it trusts that altered journal.

[fs_bot/tools/seat_session.py:87](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/tools/seat_session.py#L87) · [fs_bot/engine/game_engine.py:682](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/engine/game_engine.py#L682) · [fs_bot/engine/game_engine.py:488](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/engine/game_engine.py#L488) · [fs_bot/tools/seat_session.py:546](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/tools/seat_session.py#L546) · [fs_bot/tools/seat_session.py:501](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/tools/seat_session.py#L501)

### CM3-01 — Scout moves Roman Auxilia into nonplayable base-game Cisalpina

**Expected.** Without a qualifying Event, base-game Cisalpina is not a Region and holds no pieces. Reject ordinary Scout movement there.

**Observed.** Untouched Great Revolt setup accepts a Seize+Scout plan moving one Hidden Auxilia Provincia to Cisalpina. Both durable turn validation and normal execution accept it; the illegal Auxilia remains in Cisalpina. Census and structural validators return no errors.

**Rule basis.** Reference Documents/Chapter 1 §1.4.2 lines 132-133; Reference Documents/Chapter 4 §4.2.2 lines 69-80.

**Relation to earlier work.** New scenario-isolation path. Original CMD-SCOUT-ALLOCATION fixed per-Auxilia target allocation and visibility, not Scout movement geography. Not a replay of prior Circumvallation work.

[fs_bot/commands/sa_scout.py:54](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/commands/sa_scout.py#L54) · [fs_bot/engine/execute.py:5912](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/engine/execute.py#L5912) · [fs_bot/board/pieces.py:57](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/board/pieces.py#L57)

### CM3-02 — Entreat can target a Citadel City and remove a different Tribe’s Ally disc

**Expected.** Entreat may replace an Allied Tribe disc, not a Citadel. Check that the named Tribe is backed by an actual eligible Ally disc before removing anything.

**Observed.** A prepared census/structurally valid Great Revolt position has a Belgic Citadel at Sequani and a Belgic Ally at Helvetii. Arverni Entreat naming Sequani is accepted. It removes Helvetii’s physical Ally disc, changes Sequani allegiance to Arverni, leaves Helvetii Belgic, and retains the Belgic Citadel. The structural validator reports the Citadel has no matching allied City Tribe. Legal Helvetii control succeeds and remains clean.

**Rule basis.** Reference Documents/Chapter 4 §4.3.1 lines 107-120; Reference Documents/Chapter 1 §1.4.2.

**Relation to earlier work.** New Entreat target-identity defect. Original duplicate Entreat repair and second-audit EX2-02/EX2-03 physical Event target repairs concern other paths. Existing test_arverni_bot.py::test_entreat_skips_citadel_allied_tribe checks only planner with Citadel and no other Ally.

[fs_bot/commands/sa_entreat.py:206](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/commands/sa_entreat.py#L206) · [fs_bot/engine/execute.py:5844](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/engine/execute.py#L5844)

### CM3-03 — Ordinary Battle accepts a Region with no attacking pieces and Reveals enemies there

**Expected.** Select Battle Regions with both own and enemy Forces. Missing attacker must reject before costs or Battle effects.

**Observed.** In untouched Great Revolt setup, Romans have no pieces in Morini. An ordinary Roman Battle naming Belgic defender passes durable validation and executes. Rome pays two Resources and all four Belgic Hidden Warbands become Revealed. Census and structural validators remain clean.

**Rule basis.** Reference Documents/Chapter 3 §3.2.4 lines 125-136; Reference Documents/Chapter 3 §3.3.4 lines 277-303.

**Relation to earlier work.** Additional precondition error, not recount of CM2-01 duplicate-Region and self-target fixes. Those validations now work but leave missing attacker unchecked.

[fs_bot/engine/execute.py:3893](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/engine/execute.py#L3893) · [fs_bot/engine/execute.py:3929](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/engine/execute.py#L3929) · [fs_bot/engine/action_validation.py:123](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/engine/action_validation.py#L123)

### CM3-04 — Authored ordinary Battle plans can grant themselves Event-only combat powers

**Expected.** Only trusted Event resolution may grant modified Battle strength, combined forces, prohibited Retreat or forced Retreat. Ordinary player plan fields cannot confer those powers.

**Observed.** Without active Event modifiers, durable validation accepts details.warband_full_loss, allied_factions, no_retreat and force_retreat. Four Aedui Warbands kill two of eight Germans normally, four with full-loss flag, and six with allied_factions=[Aedui,Aedui]. A declared refusal to Retreat is overridden by force_retreat, removing all five opposing Arverni Warbands; no_retreat suppresses the defender’s Retreat question entirely. All resulting positions pass census and structure.

**Rule basis.** Reference Documents/Chapter 3 §3.3.4 lines 286-323; Reference Documents/Chapter 5 §5.1.1 lines 25-28.

**Relation to earlier work.** New inner-plan privilege defect. FE2-01/02 bound selected action and card ID, and XC2-01 rejected shadow Command portions; none governed these Battle modifiers. Frontend agent’s top-level receipt/eligibility finding is a distinct path.

[fs_bot/engine/execute.py:3825](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/engine/execute.py#L3825) · [fs_bot/engine/execute.py:4091](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/engine/execute.py#L4091) · [fs_bot/engine/execute.py:5406](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/engine/execute.py#L5406) · [fs_bot/engine/action_validation.py:317](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/engine/action_validation.py#L317) · [fs_bot/tools/seat_session.py:86](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/tools/seat_session.py#L86)

### WS3-01 — Harvest counts each Gallic Citadel twice

**Expected.** Count physical Ally discs plus Citadels once, then add Aedui River Tolls. Untouched Reconquest Aedui earns 10; Great Revolt Arverni earns 20 and Aedui earns 10.

**Observed.** Reconquest Aedui earns 12; Great Revolt Arverni earns 22 and Aedui earns 12. Each Citadel yields two extra Resources until the 45 cap.

**Rule basis.** Reference Documents/Chapter 6 §§6.4.2–6.4.3; Chapter 1 §1.4.2.

**Relation to earlier work.** New seasonal consumer. BE2-06 fixed the same representation class in Flight of Ambiorix scoring, not Harvest. Original WS findings concerned player choices and phase routing.

[fs_bot/engine/winter.py:644](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/engine/winter.py#L644) · [fs_bot/board/pieces.py:898](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/board/pieces.py#L898)

### WS3-02 — Lost Eagle restricts Senate changes outside its printed window

**Expected.** The restriction applies only to the upcoming Senate Phase, leaves intervening Cicero/Pompey Events unaffected, and expires even if the first Pax Senate sets Intrigue instead of shifting.

**Observed.** 33S followed by either 1U or 3U reports execution but blocks their legal downward shift. After the first Pax Senate, the flag remains and wrongly blocks the next Senate Phase too.

**Rule basis.** Reference Documents/Card Reference 33 and Tip; cards 1 and 3; Chapter 6 §6.5.1; Scenario - Pax Gallica first Winter.

**Relation to earlier work.** New group. Existing tests verify ordinary upcoming-Senate consumption only. Two scope/lifetime witnesses are one repair group.

[fs_bot/cards/card_effects.py:188](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/cards/card_effects.py#L188) · [fs_bot/engine/winter.py:724](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/engine/winter.py#L724) · [fs_bot/engine/winter.py:769](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/engine/winter.py#L769) · [fs_bot/engine/winter.py:808](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/engine/winter.py#L808)

### BE3-01 — Consuetudine omits its forced Ambush exception and Scouted hide step

**Expected.** Four German Warbands in Pictones must Ambush five Hidden Aedui Warbands, inflicting two Losses and removing two Warbands. No German Rally placement is available in Pictones and no Raid occurs because Resources are zero. Separately, The Scouted German Warband in Pictones loses its marker and remains Revealed.

**Observed.** Accepted Event leaves all five Aedui Warbands and all four Hidden Germans untouched. Separately, The accepted Event leaves the German Warband Scouted. No subsequent Rally placement, Raid or Battle occurs at Pictones.

**Rule basis.** Reference Documents/Card Reference 53, lines 528–534; Chapter 5 §5.1.1; Chapter 4 §4.2.2.

**Relation to earlier work.** Original inventory base-53-original-unshaded and revised aliases were marked supported by static trace, with no finding. Not an Ambush Fort duplicate; no Fort or Citadel in witness.

[fs_bot/cards/card_effects.py:1990](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/cards/card_effects.py#L1990) · [fs_bot/cards/card_effects.py:2002](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/cards/card_effects.py#L2002) · [fs_bot/engine/germans_battle.py:206](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/engine/germans_battle.py#L206) · [fs_bot/engine/germans_battle.py:75](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/engine/germans_battle.py#L75)

### BE3-03 — Colony fails to create its Tribe when the executing Ally pool is empty

**Expected.** With zero Roman Ally discs Available, card 71 still creates the Colony marker and a Subdued Colony Tribe. Rome gains one Subdued Tribe in its victory count.

**Observed.** A valid Great Revolt setup with all Roman Allies deployed accepts Colony at unoccupied Britannia and adds its marker, but creates no Tribe. Tribe count remains30 and Roman victory score remains12 instead of13.

**Rule basis.** Reference Documents/Card Reference 71, lines 729–733; Chapter 5 §5.1.3; Chapter 1 §1.7; Chapter 7 §7.2.

**Relation to earlier work.** Not the previously repaired Colony name collision or bot target-default issue. This is the initial Event scarce-pool partial-execution path; downstream scoring merely demonstrates the missing Tribe.

[fs_bot/cards/card_effects.py:2626](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/cards/card_effects.py#L2626) · [fs_bot/engine/victory.py:112](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/engine/victory.py#L112)

### BE3-04 — Shaded Migration allows relocation while omitting its mandatory possible Ally

**Expected.** After selecting unoccupied Britannia and moving an Arverni Warband there, a complete legal plan must place an Available Arverni Ally at the Subdued Catuvellauni Tribe.

**Observed.** In ordinary Great Revolt setup, a plan with no ally_tribe passes durable validation, commits the relocation and leaves Catuvellauni Subdued despite one Ally being Available.

**Rule basis.** Reference Documents/Card Reference 66, lines 676–684; Chapter 5 §5.1.3.

**Relation to earlier work.** BE-12 fixed relocation ownership/geography/cohort validation. This surviving mandatory post-relocation placement was not a previous recorded finding, and is separate from EX2-04 mandatory A-card quotas.

[fs_bot/cards/card_effects.py:2450](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/cards/card_effects.py#L2450) · [fs_bot/cards/card_effects.py:2493](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/cards/card_effects.py#L2493)

### EX3-01 — Harudes shaded accepts omitted mandatory reinforcements

**Expected.** With pieces and legal space available, require four German Warbands and one Settlement before resolving their Raid; incomplete human plans must not commit.

**Observed.** placements=[] passes durable-response validation and ordinary validation, executes A29 shaded, places no pieces, and reports the Raid as declined_no_effect. Four Warbands and one Settlement can be placed in the control case.

**Rule basis.** Reference Documents/Ariovistus/A Card Reference:108-109, A29 shaded; Reference Documents/Chapter 5:5.1.3.

**Relation to earlier work.** A29 unshaded placement validation was EXP-09; EXP-02 restored its shaded Raid choices. EX2-04 covered A30/A56/A65 mandatory quotas, not shaded A29. This is a new card-specific occurrence, not a reopened old ID.

[fs_bot/cards/card_effects.py:3077](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/cards/card_effects.py#L3077) · [fs_bot/engine/execute.py:6483](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/engine/execute.py#L6483) · [fs_bot/cards/expansion_validation.py:15](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/cards/expansion_validation.py#L15)

### EX3-03 — Nasua and Cimberius fails to replace a Dispersed marker at Treveri

**Expected.** The printed replacement of anything at Treveri removes its Dispersed or Gathering marker and places the selected Gallic/Roman Ally if available.

**Observed.** A35 unshaded executes successfully with an available Belgic Ally but leaves Treveri Dispersed and unallied. It also leaves Dispersed-Gathering untouched after an actual Spring. The Subdued control places the Ally.

**Rule basis.** Reference Documents/Ariovistus/A Card Reference:152-154, A35 unshaded; Reference Documents/Chapter 5:5.1 and5.1.3; Reference Documents/Chapter 1:1.4.2.

**Relation to earlier work.** A35 unshaded was a not-verified inventory row, including in second audit earlier-unverified dispositions. No previous confirmed finding covered replacement of its Dispersed marker.

[fs_bot/cards/card_effects.py:3265](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/cards/card_effects.py#L3265) · [fs_bot/cards/card_effects.py:309](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/cards/card_effects.py#L309)

### EX3-04 — Stalwart does not cancel Germanic Horse doubling against Germans

**Expected.** After A31 shaded is played, its cancellation of harmful Event effects suppresses an earlier enemy Germanic Horse capability. Six Belgic Warbands inflict three ordinary Losses against Germans.

**Observed.** In an accepted ordinary Battle, six Belgic Warbands inflict six Losses against eight German Warbands with shaded59 active, whether or not shadedA31 is then activated. Four controls yield German losses [3,3,6,6] for neither/A31 only/Horse only/Horse followed by A31.

**Rule basis.** Reference Documents/Ariovistus/A Card Reference:126-131, A31 shaded; Reference Documents/Card Reference:602-618, card59 shaded; Reference Documents/Chapter 5:5.1.2 and5.3; QUESTIONS.md:2795-2845 preserves prior interpretation that Event effects includes Capabilities.

**Relation to earlier work.** Historical A31 repairs handled named enemy Leaders, Abatis, Wailing Women and no-retreat. The earlier 50/21 finding ledgers did not count this surviving Horse interaction.

[fs_bot/battle/resolve.py:495](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/battle/resolve.py#L495) · [fs_bot/battle/losses.py:276](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/battle/losses.py#L276)

### XC3-01 — Existing Colony Tribes are ignored by Commands, Events, and Belgic scoring

**Expected.** Card 71's Colony is a real Tribe in its recorded Region. A Roman-Allied/Subdued Colony contributes +2 Seize Forage; a Subdued Colony is dispersible, Build can subdue/place its disc, Entreat can replace an eligible enemy disc, Trade includes a Subdued/Roman-Allied Colony under Aedui Control, and its Dispersed marker reduces Belgic Control Value. Acco and Procillus also include otherwise eligible Colony Allies.

**Observed.** After real Colony Event creation, a full accepted Roman Seize in Mandubii earns 2 instead of 4; its Subdued Colony is absent from the dispersal menu and rejected by authored-plan validation. Valid Build/Entreat Regions reject the named physical Colony as not in its actual Region. Aedui Trade earns 6 instead of 8 with a Subdued Colony in Aedui. A valid controlled Dispersed Colony fixture leaves Belgic victory score 6 instead of 5. Shaded Acco leaves a Colony Ally unchanged; Procillus accepts a selected Colony Ally near Caesar and silently ignores it.

**Rule basis.** Reference Documents/Card Reference §71 Colony lines 729-733; Reference Documents/Chapter 3 §3.2.3 Seize lines 89-123; Reference Documents/Chapter 4 §4.2.1 Build lines 43-66; Reference Documents/Chapter 4 §4.3.1 Entreat lines 107-120; Reference Documents/Chapter 4 §4.4.1 Trade lines 158-174; Reference Documents/Chapter 7 §7.2 Belgic Control Value, including non-Suebi Dispersed adjustments; Reference Documents/Card Reference 34, lines 338–344 and 71, lines 729–733; Chapter 5 §5.1.3; Reference Documents/Ariovistus/A Card Reference:45-47, A19 unshaded; Reference Documents/Card Reference:729-733, card71; Reference Documents/Chapter 5:5.1.

**Relation to earlier work.** Additional static-map consumers beyond repaired Colony Event defaults, Rally/Recruit and Suborn support. Separate from BE2-06 Flight score repair. Grouped with the new Acco and Procillus consumers of the same static Tribe model; Colony creation when supply is exhausted remains separate.

[fs_bot/commands/seize.py:156](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/commands/seize.py#L156) · [fs_bot/commands/seize.py:218](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/commands/seize.py#L218) · [fs_bot/commands/seize.py:247](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/commands/seize.py#L247) · [fs_bot/commands/seize.py:571](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/commands/seize.py#L571) · [fs_bot/commands/sa_build.py:174](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/commands/sa_build.py#L174) · [fs_bot/commands/sa_build.py:248](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/commands/sa_build.py#L248) · [fs_bot/commands/sa_entreat.py:207](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/commands/sa_entreat.py#L207) · [fs_bot/commands/sa_trade.py:321](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/commands/sa_trade.py#L321) · [fs_bot/engine/victory.py:256](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/engine/victory.py#L256) · [fs_bot/cards/card_effects.py:1502](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/cards/card_effects.py#L1502) · [fs_bot/cards/card_effects.py:2777](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/cards/card_effects.py#L2777) · [fs_bot/cards/card_effects.py:254](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/cards/card_effects.py#L254)

### XC3-02 — Seize treats Razed Cities as Subdued and replaces their permanent marker

**Expected.** A City Razed by Sacking is Dispersed for Seize, yields no ordinary Forage, cannot be Dispersed again, and retains its Razed marker through Spring.

**Observed.** An accepted Sacking Event Razes Roman-controlled Alesia. Seize's menu offers Mandubii for dispersal and its Forage calculator returns 4 instead of 2. A full authored Seize is accepted, earns 8, and changes Razed to ordinary Dispersed. Two Spring phases then clear the status, whereas a matched control remains Razed. State and structural validation report no errors throughout.

**Rule basis.** Reference Documents/Card Reference §23 Sacking lines 225-236; Reference Documents/Chapter 3 §3.2.3 Seize lines 89-123; Reference Documents/Chapter 6 §6.6 Spring, preserve Razed.

**Relation to earlier work.** New downstream unshaded Sacking/Seize interaction. BE2-01 repaired shaded Sacking prerequisites, not this marker lifecycle. Unrelated to known Circumvallation persistence.

[fs_bot/commands/seize.py:168](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/commands/seize.py#L168) · [fs_bot/commands/seize.py:258](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/commands/seize.py#L258) · [fs_bot/commands/seize.py:582](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/commands/seize.py#L582) · [fs_bot/commands/seize.py:590](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/commands/seize.py#L590) · [fs_bot/engine/winter.py:1094](https://github.com/FeeSimple1/fs-bot/blob/3c23a3414c3e870e274ef63c278db8cb3f1ee747/fs_bot/engine/winter.py#L1094)
