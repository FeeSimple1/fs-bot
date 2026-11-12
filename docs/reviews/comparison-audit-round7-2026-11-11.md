# Seventh Falling Sky comparison audit — 11 November 2026

**The audit found nine repair groups, two high and seven medium priority.**
Batch 1 closes BM7-01 and BM7-02. Batch 2 closes WS7-01. Batch 3 closes
FE7-01. Batch 4 closes BE7-01, BE7-02, and BE7-03. Two groups remain open.
The findings below describe the audited revision.
[Batch 1 repairs and validation](seventh-comparison-batch1-2026-11-11.md) ·
[Batch 2 repairs and validation](seventh-comparison-batch2-2026-11-11.md) ·
[Batch 3 repairs and validation](seventh-comparison-batch3-2026-11-11.md) ·
[Batch 4 repairs and validation](seventh-comparison-batch4-2026-11-11.md)

Audited Falling Sky commit `c67d501711471bf790d805c017c2125b2c254639`. Python-source SHA-256 `2ae5b3cedb16cfed6969442ebe9fefba99ed0f03933cd30c78a4deb6c002e801` across 602 files. Liberty or Death was inspected at `2991ea279062773548ec390a1da75f3e85381702`. Its implementation patterns guided the search; Falling Sky's supplied references and thirteen adopted provisional rulings govern the findings.

[Finding ledger](comparison-audit-round7-2026-11-11.json) · [Portable evidence](comparison-audit-round7-2026-11-11-evidence.zip) · [Current status](../current-status.md)

## Method and coverage

| Comparison pattern | Seventh-pass checks |
|---|---|
| Implemented helpers reach real callers | Non-Roman Quarters plans through complete Winter; capability hooks through fixed Event and automatic Battles |
| Effects reach each decision consumer | Ambush before Battle rejection; Baggage Trains before Raid quantities; Stalwart during Fort casualty rolls |
| Free Commands retain unmodified restrictions | Base German group limits across canonical, explicit, terminal and durable Surus plans |
| Sequential Event plans use intermediate state | Oppida upgrades after its new Ally placements |
| Bot Event plans deliver actual effects | Procillus/Divico parameter production and Rhenus Bridge's conditional eligibility effect |

Five partitions checked the current source, printed rules and earlier ledgers. A separate review checked Battle/lifecycle and bot/frontend findings; root reviewed Event findings and independently reran all five final scripts under hash seeds 0 and 987. All ten reruns match the recorded JSON. Related symptoms are grouped by repair cause, including the four missing Raid-capacity consumers and the alternate Battle pathways.

Comparator material includes `coin-implementation-lessons.md`, `docs/audit_set_but_never_applied_s76.md`, `docs/human_mode_audit.md`, and `docs/audit_event_gain_priorities_cards1_16_21.md`. The evidence preserves bounded coverage and excluded leads for each partition.

## Confirmed findings

| ID | Priority | Finding |
|---|---|---|
| BM7-01 | high | Fixed Event Battles and the automatic Arverni Phase omit Battle capability hooks |
| BM7-02 | medium | Stalwart fails to cancel Ballistae protection of Roman Forts |
| FE7-01 | medium | Shaded Surus permits multiple base-game German March groups from one origin |
| WS7-01 | high | Non-Roman non-player Quarters never execute their evacuation or Leader-consolidation procedures |
| BE7-01 | medium | Oppida bot planning omits Citadels enabled by its own first-step Ally placements |
| BE7-02 | medium | Missing non-player parameters make Procillus and Divico execute without their available piece effects |
| BE7-03 | medium | Bots choose shaded Rhenus Bridge despite its unmet Legion prerequisite |
| NP7-01 | medium | Belgae, Arverni and German Battle gates disregard a legal Ambush before rejecting the Battle |
| NP7-02 | medium | All four Raid planners ignore shaded Baggage Trains' third Warband during ordinary turns |

## Validation

| Check | Fresh result on the audited source |
|---|---|
| Full test suite | 9,991 passed on Python 3.12.14 |
| Audited bot games | All 20 second-edition games completed; five scenarios, seeds 41–44, one Interlude, clean inventories/structure and only legal-decline diagnostics |
| Mixed-player replay | Twenty cases match byte-for-byte across hash seeds 0 and 987; 558 human turns, 153 Event attempts, 142 executed Events, one partial plan and zero hard findings |
| Directed witnesses | Five final scripts reproduce the nine groups with lawful controls; root reran each under both hash seeds |
| Previous repair CI | CI and Package installation both passed for the audited commit |

These results show that the directed rules failures survive a passing existing suite and clean sampled games. They do not establish natural encounter frequency, winner impact or exhaustive rules coverage. The audit made no balance-baseline change and did not repeat the legacy balance matrix. All gameplay/reference bytes remain at the audited revision.

The shared evidence runner checks the source digest before running defect witnesses. Those scripts assert the observed failures and their controls; after repairs, their defect assertions should stop passing. They are evidence scripts, not tests asking production to preserve incorrect behavior.

## Suggested repair sequence

| Batch | Scope | Findings |
|---|---|---|
| 1 | Restore Battle capability integration | BM7-01, BM7-02 |
| 2 | Execute non-Roman bot Quarters | WS7-01 |
| 3 | Enforce base German free-March groups | FE7-01 |
| 4 | Complete and filter bot Events | BE7-01, BE7-02, BE7-03 |
| 5 | Use Ambush and Raid capabilities in bot planning | NP7-01, NP7-02 |

The Battle batch restores capability behavior across affected execution paths. Quarters addresses avoidable piece losses and missed Leader consolidation. The third batch enforces the German March group limit. The last two batches cover Event selection and plans, then bot Command planning.

## Finding details

### BM7-01 — Fixed Event Battles and the automatic Arverni Phase omit Battle capability hooks

**Expected:** Every enemy Battle Command, including free Event Battles and automatic Arverni Ambushes, applies Balearic Slingers once. A holder of shaded Germanic Horse doubles the enemy Losses in a selected eligible Region of its Event-granted Battle. The printed Event exceptions remain intact.

**Observed:** With Card13 active, public numeric2 shaded at Carnutes resolves four Aedui Warbands versus two Roman Auxilia into four Aedui/no Auxilia, with no Slingers request. No Legions are present, so card2 adds no live combat modifier; the matched ordinary Battle asks Slingers and leaves three Aedui/one Auxilia. Card25 and36 likewise ignore third-party Roman Slingers. Card36 with shaded Horse owned by its Aedui executor leaves six of eight Belgic Warbands instead of four, and never asks Horse. Full run_arverni_phase in an At War Carnutes position adds its legal Ally during Rally, skips March on Frost and cannot Raid zero Roman Resources, then Ambushes without Slingers: four Arverni/no Auxilia survive instead of three Arverni/one Auxilia.

**Cause:** _resolve_fixed_event_battle and _arverni_phase_battle call resolve_battle directly; neither supplies the Command-level Slingers/Horse choice and execution hooks installed in _execute_battle. The capability calculations depend on that orchestration. All confirmed symptoms are grouped as one remaining alternate-path integration defect.

**Sources:** [Reference Documents/Card Reference:126](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Card%20Reference#L126); [Reference Documents/Card Reference:132](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Card%20Reference#L132); [Reference Documents/Card Reference:606](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Card%20Reference#L606); [Reference Documents/Card Reference:18](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Card%20Reference#L18); [Reference Documents/Card Reference:248](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Card%20Reference#L248); [Reference Documents/Card Reference:358](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Card%20Reference#L358); [Reference Documents/Ariovistus/Chapter A6:114](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Ariovistus/Chapter%20A6#L114); [Reference Documents/Chapter 5:25](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Chapter%205#L25).

**Implementation:** [fs_bot/engine/execute.py:2149](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/engine/execute.py#L2149); [fs_bot/engine/execute.py:3075](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/engine/execute.py#L3075); [fs_bot/engine/execute.py:2186](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/engine/execute.py#L2186); [fs_bot/engine/execute.py:2240](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/engine/execute.py#L2240); [fs_bot/engine/arverni_phase.py:835](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/engine/arverni_phase.py#L835).

**Controls:** Nine fixed/ordinary cases and two full Arverni phases. For every failing Event/phase witness, omitting the capability gives the identical casualty outcome. The ordinary public numeric2-matched Battle does apply Slingers; ordinary Aedui Battle with shaded Horse doubles its Attack and asks the owner. Event exception clauses are exercised without inventing additional exemptions.

**Earlier-audit distinction:** BM6-02 proved direct German-guidance/Germans-Phase omissions and repaired those consumers; its report explicitly says Arverni Phase and other Event direct resolver callsites remained uncounted static risks. Those risks now have independent public witnesses. Original BE-09 and prior owner-choice repairs addressed ordinary/free _execute_battle paths. The fixed Event target-choice work supplied target menus without proving Command capability integration.

**Repair scope:** Route all modified/free Battle callsites and automatic Arverni Battles through shared Command capability orchestration while preserving each Event exception, one-use limits, PR-13 reservation, ownership decisions, physical participating forces and action windows. Audit direct resolve_battle consumers systematically. Add public Event and full-phase regression controls.

**Fixture:** Controlled build_initial_state positions, seed 7, canonical place_piece only, permanent Provincia Fort retained. Human seats except scenario game-run factions. Every capability acquired through execute_decision Event. Complete pre/post census and structure checks pass. No natural encounter frequency claim.

**Limits:** Proves only numeric2/25/36 Slingers, numeric36 shaded Horse, and automatic Arverni Slingers. Other fixed Event handlers and Archers are static leads, not additional confirmed findings. No claim of all capability combinations or automatic-phase multi-Region reservations.

**Evidence:** `PYTHONPATH=<fs-bot-root> python battle/probe_battle.py`; `battle/probe_battle-output.json`.

### BM7-02 — Stalwart fails to cancel Ballistae protection of Roman Forts

**Expected:** After shaded A31 is acquired, earlier Ballistae unshaded cannot protect a Roman Fort from German Battle Losses. A Fort absorbing a Loss on die roll3 must be removed under the ordinary 1–3 rule.

**Observed:** Four German Warbands attacking a lone Roman Fort in Carnutes generate one Loss after halving. At seed7 the next and only RNG roll is3. Ballistae+Stalwart leaves the Fort standing; Ballistae without Stalwart does the same. With Stalwart but no Ballistae the Fort is removed. A matched non-German Belgic attacker correctly leaves the Ballistae-protected Fort standing.

**Cause:** resolve_losses changes every FORT absorption threshold to2 whenever unshaded Ballistae is active. It has no inflicting-faction context and does not apply shaded A31 cancellation. The recent A31 repairs reached named-leader rates, LegioX and Slingers, but not this casualty consumer.

**Sources:** [Reference Documents/Ariovistus/A Card Reference:130](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Ariovistus/A%20Card%20Reference#L130); [Reference Documents/Card Reference:95](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Card%20Reference#L95); [Reference Documents/Chapter 3:326](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Chapter%203#L326); [Reference Documents/Chapter 5:50](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Chapter%205#L50).

**Implementation:** [fs_bot/battle/losses.py:525](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/battle/losses.py#L525).

**Controls:** Four cases toggle Ballistae, Stalwart and German versus Belgic attacker. A31 is always acquired after Ballistae to avoid played-later precedence ambiguity. A copied RNG predicts roll3 without consuming live state, and the final RNG is verified to have consumed exactly that one roll.

**Earlier-audit distinction:** BM6-01 was explicitly shaded LegioX and Slingers; BM5-01 was unshaded LegioX final Loss adjustments; EX3-04 was Germanic Horse. BE5-01 addressed shaded Ballistae recipient selection. None covered unshaded Ballistae casualty saves against Germans.

**Repair scope:** Carry Battle participants/effect-cancellation context into casualty resolution and suppress Ballistae’s Fort protection when it harms Germans protected by Stalwart. Preserve ordinary Fort saves, Belgic/other attacks, and Provincia Fort immunity. Add public Battle regressions with the fixed seeded roll and effect-off controls.

**Fixture:** Controlled build_initial_state positions, seed 7, canonical place_piece only, permanent Provincia Fort retained. Human seats except scenario game-run factions. Every capability acquired through execute_decision Event. Complete pre/post census and structure checks pass. No natural encounter frequency claim.

**Limits:** Confirmed only ordinary Ariovistus German Attack against a Roman Fort. Other A31 interactions (Archers, Elite and one-shot modifiers) remain separate unproved leads; no new count is claimed for them.

**Evidence:** `PYTHONPATH=<fs-bot-root> python battle/probe_battle.py`; `battle/probe_battle-output.json`.

### FE7-01 — Shaded Surus permits multiple base-game German March groups from one origin

**Expected:** Shaded Surus grants March, Raid or Battle using its newly placed German Warbands. Base Germanic March may form at most one moving group per origin; a subset may stay. A split into two moving groups must be rejected before any replacements or moves commit.

**Observed:** The public shaded Surus Event replaces four Aedui Warbands at Treveri, then accepts a two-Warband group to Nervii plus a two-Warband extra group to Sequani. Both destinations gain German Control. The same forbidden split succeeds via explicit_moves, a production terminal-collected plan, and a durable pending/save/load/resume response that replays exactly. All pre/post schema and structural checks pass.

**Cause:** Surus routes its base-game German Command through the generic free-action validator/executor. The shared validator counts distinct selected origins, and _collect_march_moves appends extra_groups or returns explicit_moves without enforcing the original-game German one-moving-group rule. The terminal also offers further groups without a base-German gate.

**Sources:** [Reference Documents/Chapter 3:340](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Chapter%203#L340); [Reference Documents/Chapter 3:354](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Chapter%203#L354); [Reference Documents/Card Reference:511](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Card%20Reference#L511); [Reference Documents/Card Reference:514](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Card%20Reference#L514).

**Implementation:** [fs_bot/cards/surus.py:145](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/cards/surus.py#L145); [fs_bot/engine/free_actions.py:394](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/engine/free_actions.py#L394); [fs_bot/engine/execute.py:4285](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/engine/execute.py#L4285); [fs_bot/engine/execute.py:4345](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/engine/execute.py#L4345); [fs_bot/engine/execute.py:4470](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/engine/execute.py#L4470); [fs_bot/cli/human_plan.py:359](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/cli/human_plan.py#L359).

**Controls:** On the identical source board, a single group of all four moves legally to Nervii. A single two-Warband group moves to Nervii while two remain legally at Treveri. The tested split representations instead create two separate moving groups. No resident Germans, Leaders, Harassment or timing actions complicate the witness.

**Earlier-audit distinction:** The 29 October action-timing Surus repair restricted the physical grant to replacement Warbands and exposed executor choice. BE-11 covered numeric51 unshaded replacement geography/quotas. Original BE-01 covered separate Germanic Chieftains/German Allegiances/Aduatuca guidance pipelines. FE6-02 allowed multiple groups for ARIOVISTUS Enlist under A3.4.2; its base Enlist control remains single-group. WS6-02 concerned the separate automatic Germans Phase moving arrivals twice. None reports this original-game Surus group-count validation gap; this does not reopen those closed findings.

**Repair scope:** Enforce at most one moving group per origin for base-game Germans after normalizing all supported March representations, including generic Event grants, and suppress the terminal extra-group option for that actor/ruleset. Preserve legal subsets/stays and Ariovistus multiple-group behavior. Keep durable invalid responses pending and roll back the outer Event.

**Fixture:** Controlled build_initial_state Great Revolt seed7, second-edition numeric51 current, all player seats human; permanent Provincia Fort and four Hidden Aedui Warbands at Treveri placed with canonical helpers. No pre-existing German Warbands. All schema and structural checks pass before and after each case.

**Limits:** Constructed legal sparse positions prove the mechanism; no natural-game frequency or winner impact estimate. The durable path preserves and replays the illegal accepted move correctly; no independent serialization defect is claimed. The same mechanism is one repair group across four interface representations.

**Evidence:** `PYTHONPATH=<fs-bot-root> python frontend/probe_surus.py`; `frontend/probe_surus-output.json`.

### WS7-01 — Non-Roman non-player Quarters never execute their evacuation or Leader-consolidation procedures

**Expected:** Non-player Belgae, Aedui, and base-game Arverni evacuate eligible Devastated Regions when a legal refuge exists; expansion Germans likewise evacuate when lacking an Ally or Settlement. Belgae, Arverni, and Germans also consolidate their Leader with the largest reachable Warband group under their printed priorities and leave-behind restrictions.

**Observed:** Public quarters_phase returns empty non-Roman relocation lists in every NPC case. Each evacuation witness leaves three Warbands at Devastated Carnutes and rolls [2,5,1], removing two, although the legal matched move puts all three into their own non-Devastated Bituriges (four Warbands there, zero losses). Leader cases leave each Leader with three Warbands when a legal relocation can join ten. An actual Pax Gallica setup first Winter reproduces the Aedui omission through run_winter_round: the Germans Phase is properly skipped, Aedui lose two Carnutes Warbands on [2,5,2], and the explicit-relocation control preserves all four.

**Cause:** winter._quarters_phase invokes build_np_winter_relocations only for Romans; every other NPC receives {faction: []}. Existing node_b_quarters/node_a_quarters/node_v_quarters/node_g_quarters are referenced only by definitions and tests, and their legacy descriptive payloads do not match the executable relocation tuple schema.

**Sources:** [Reference Documents/Chapter 8:413](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Chapter%208#L413); [Reference Documents/Chapter 8:559](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Chapter%208#L559); [Reference Documents/Chapter 8:767](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Chapter%208#L767); [Reference Documents/Ariovistus/Chapter A8:242](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Ariovistus/Chapter%20A8#L242); [Reference Documents/Chapter 6:77](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Chapter%206#L77).

**Implementation:** [fs_bot/engine/winter.py:389](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/engine/winter.py#L389); [fs_bot/bots/belgae_bot.py:1702](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/bots/belgae_bot.py#L1702); [fs_bot/bots/aedui_bot.py:1445](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/bots/aedui_bot.py#L1445); [fs_bot/bots/arverni_bot.py:1639](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/bots/arverni_bot.py#L1639); [fs_bot/bots/german_bot.py:2015](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/bots/german_bot.py#L2015).

**Controls:** For each of four NPC evacuation fixtures, the public validator accepts exact Hidden Warband relocation to the sole own-Control non-Devastated refuge and the same public phase executes it without desertion. A Devastated-refuge control correctly rejects that move and rolls desertion. Three Leader fixtures have valid consolidation controls that retain one origin Warband and move Leader plus two Warbands to the existing stack of eight. The full Winter pair starts from setup_scenario(Pax Gallica?,seed1), preserving its actual first-Winter rules, and adds only the four Aedui Warbands and a Devastated marker.

**Earlier-audit distinction:** Original WS-F05 concerns owners selecting visibility cohorts; that repair left the non-Roman NPC default empty and did not report or repair automated Quarters planning. WS-F06 concerns Resource transfer windows. Sixth WS6-01/02/03 concern the game-run base Germans Phase Rally/March, which is separate from Quarters and is skipped by the full-Winter witness under Pax rules. No earlier comparison ledger lists this orphaned non-Roman Quarters path.

**Repair scope:** Build executable non-Roman NPC Quarters plans under each faction's source rules and call them from the real Winter phase, including devastation escape, legal hosts, available original pieces, Leader/group combination, leave-behind Control requirements, scenario priorities, and deterministic random ties. Do not simply wire the legacy descriptive nodes without checking destination legality and payload shape. Preserve human chosen plans and canonical relocation validation.

**Fixture:** Lawful controlled build_initial_state positions (Great Revolt for Belgae/Aedui/Arverni; Ariovistus for Germans), seed1, all playable seats NP, Provincia permanent Fort, physical pieces placed with canonical helpers and pre/post census and structure clean. Public full-Winter pair starts from actual Pax setup, seed1, with Germans legally skipped. No input stubs or monkeypatches.

**Limits:** Seventeen directed cases establish the dead routing and concrete consequences. They do not measure encounter frequency or aggregate win-rate effects. The explicit relocation controls establish lawful available actions; they are not offered as a complete implementation of all NPC tie-breaks or multi-origin planning. Aedui human agreement alternatives and expansion Belgic geographic secondary priorities are for repair coverage rather than additional counted findings.

**Evidence:** `PYTHONPATH=<fs-bot-root> python lifecycle/probe_lifecycle.py`; `lifecycle/probe_lifecycle-output.json`.

### BE7-01 — Oppida bot planning omits Citadels enabled by its own first-step Ally placements

**Expected:** With Bituriges the only eligible Subdued City for Belgae and a Belgic Ally plus Citadel Available, Oppida must place the Ally and replace it with the Available Belgic Citadel under the NP maximize-placement priorities.

**Observed:** Public Belgic flowchart chooses Oppida, and public execution returns executed=true but places only one Ally at Bituriges. Its sole Citadel stays Available.

**Cause:** _derive_card_28 computes upgrade_options against the pre-Event board before applying its ally_placements. Newly placed City Allies never enter citadel_upgrades even though the handler applies upgrades after placements.

**Sources:** [Reference Documents/Card Reference:281](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Card%20Reference#L281); [Reference Documents/Card Reference:286](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Card%20Reference#L286); [Reference Documents/Chapter 8:129](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Chapter%208#L129); [Reference Documents/Chapter 8:149](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Chapter%208#L149).

**Implementation:** [fs_bot/engine/execute.py:5998](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/engine/execute.py#L5998); [fs_bot/engine/execute.py:6011](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/engine/execute.py#L6011); [fs_bot/cards/card_effects.py:1266](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/cards/card_effects.py#L1266); [fs_bot/cards/card_effects.py:1271](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/cards/card_effects.py#L1271).

**Controls:** On the identical original board, an explicit public plan supplying Bituriges Ally then Avaricum Citadel produces the Citadel. In the matched existing-Ally variant, the actual bot correctly upgrades Bituriges to a Citadel. Both controls pass conservation and structure.

**Earlier-audit distinction:** Original BE-08 / 6 November Oppida work repaired human menu shapes, live City eligibility, and owner restriction. It did not report the NP derived plan's failure to include newly enabled upgrades. No comparison ledger through round6 contains this sequential NP plan failure.

**Repair scope:** Derive the upgrade portion against an isolated board after proposed legal Ally placements, including newly created own City Allies and normal NP priorities. Preserve copy-only RNG and human input isolation.

**Fixture:** Sparse Great Revolt build_initial_state, seed1, permanent Provincia Fort. All Cities except Bituriges have other factions' Allies; original City stacking restrictions respected. One eligible Belgic City and one Available Citadel remove all tie/quantity ambiguity. Pieces created via canonical helpers. Pre/post census and structure pass.

**Limits:** Controlled reproducible cases establish mechanisms, not sampled encounter frequency or exhaustive Event coverage. No production mutations or source-rule changes.

**Evidence:** `PYTHONPATH=<fs-bot-root> python events/probe_events.py`; `events/probe_events-output.json`.

### BE7-02 — Missing non-player parameters make Procillus and Divico execute without their available piece effects

**Expected:** Roman A19 unshaded replaces the one eligible Belgic Ally within one Region of named Caesar. Shaded A26 places twelve available Arverni Warbands; the German plan preserves existing German Allies and Control per its special instruction.

**Observed:** Public Roman A19 execution and public Belgic/German A26 executions all return executed=true with no board, inventory, Resource, Eligibility or effect changes. A19 leaves the target Belgic Ally unchanged; A26 places zero Warbands.

**Cause:** Neither A19 nor A26 is registered with a parameter deriver or any preceding supported dispatcher branch. _derive_event_params returns None; both handlers default their replacements/placements to empty lists and report successful execution.

**Sources:** [Reference Documents/Ariovistus/A Card Reference:45](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Ariovistus/A%20Card%20Reference#L45); [Reference Documents/Ariovistus/A Card Reference:88](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Ariovistus/A%20Card%20Reference#L88); [Reference Documents/Chapter 8:129](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Chapter%208#L129); [Reference Documents/Ariovistus/german_bot_event_instructions_ariovistus.txt:37](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Ariovistus/german_bot_event_instructions_ariovistus.txt#L37).

**Implementation:** [fs_bot/engine/execute.py:5943](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/engine/execute.py#L5943); [fs_bot/engine/execute.py:5982](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/engine/execute.py#L5982); [fs_bot/engine/execute.py:6540](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/engine/execute.py#L6540); [fs_bot/cards/card_effects.py:2744](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/cards/card_effects.py#L2744); [fs_bot/cards/card_effects.py:2964](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/cards/card_effects.py#L2964).

**Controls:** Identical-start explicit public plans replace the Bituriges Ally with Roman for A19 and add twelve Arverni Warbands in Aedui for A26. The latter preserves every pre-existing German-controlled Region and every German Ally, making it valid for both Belgae and the German special instruction. All pre/post validators pass.

**Earlier-audit distinction:** BE6-02 enumerated A35/A60 missing parameter producers, now fixed. This is the same engineering family in two additional independent handlers. EX2-06 was A19 named Caesar versus Successor legality, XC3-01 was Colony recognition, and the original scouted-Event repair concerned A26 unshaded removals. None supplied these NP plans. A26 shaded was explicitly not-verified with no finding in the original inventory.

**Repair scope:** Add A19 unshaded and A26 shaded NP derivation/availability checks following their actual target priorities and German no-loss-of-Control instruction. Keep explicit human optional amounts and legal zero selections intact.

**Fixture:** A19 uses sparse census-valid Ariovistus seed1 with permanent Provincia Fort, named Caesar in Aedui and one Belgic Ally in adjacent Bituriges. A26 uses the untouched original Ariovistus physical setup, seed1, changing only current-card metadata and NP seats.

**Limits:** Controlled reproducible cases establish mechanisms, not sampled encounter frequency or exhaustive Event coverage. No production mutations or source-rule changes.

**Evidence:** `PYTHONPATH=<fs-bot-root> python events/probe_events.py`; `events/probe_events-output.json`.

### BE7-03 — Bots choose shaded Rhenus Bridge despite its unmet Legion prerequisite

**Expected:** Without a Legion within one Region of Germania, neither the Resource loss nor the Eligibility penalty applies. Non-player Belgae and Germans must decline this ineffective Event and continue their flowcharts.

**Observed:** On untouched Ariovistus setup (Legions at Provincia), both bots choose A18 shaded. Execution reports success and changes none of the tracked game effects; both have an available non-Event, non-Pass flowchart continuation.

**Cause:** A18 is flagged AFFECTS_ELIGIBILITY, which is_event_effective treats as always effective. np_event_available has no shaded A18 prerequisite override. The handler itself correctly guards both the -6 Resources and Ineligible-through-next-card effects behind nearby Legion presence.

**Sources:** [Reference Documents/Ariovistus/A Card Reference:39](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Ariovistus/A%20Card%20Reference#L39); [Reference Documents/Chapter 8:30](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Chapter%208#L30); [Reference Documents/Ariovistus/Chapter A8:5](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Ariovistus/Chapter%20A8#L5).

**Implementation:** [fs_bot/cards/event_eval.py:1095](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/cards/event_eval.py#L1095); [fs_bot/cards/event_conditions.py:13](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/cards/event_conditions.py#L13); [fs_bot/cards/card_effects.py:2712](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/cards/card_effects.py#L2712); [fs_bot/cards/card_effects.py:2723](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/cards/card_effects.py#L2723).

**Controls:** Move one existing Legion from Provincia to Treveri via move_piece on a copy, and public A18 execution correctly removes six Roman Resources and sets forced_ineligible[Romans]=1. Original-board flowchart continuation with can_play_event=False selects an actual Command for each faction.

**Earlier-audit distinction:** BE6-03 addressed numeric56 named-Ambiorix availability, not A18. Original named-event-effects work addressed 18/A18 unshaded removal ownership and targeting. No prior ledger reports shaded A18 conditional eligibility effectiveness.

**Repair scope:** Make shaded A18 availability share the real nearby-Legion predicate; both its Resource and Eligibility clauses are conditional. Verify absent, one-away and too-distant cases for Belgae/Germans without consuming live RNG or input.

**Fixture:** Untouched original Ariovistus physical setup, seed1. Only current Event and NP seat metadata injected. All Legions begin in Provincia, beyond one Region of Germania. Census/structure pass before and after.

**Limits:** Controlled reproducible cases establish mechanisms, not sampled encounter frequency or exhaustive Event coverage. No production mutations or source-rule changes.

**Evidence:** `PYTHONPATH=<fs-bot-root> python events/probe_events.py`; `events/probe_events-output.json`.

### NP7-01 — Belgae, Arverni and German Battle gates disregard a legal Ambush before rejecting the Battle

**Expected:** With legal Ambush and no defending Caesar, the Battle has positive Attack Losses and zero Counterattack Losses. Belgae, Arverni and Germans must include that Special Ability when evaluating whether to Battle, and select Battle plus Ambush in the controlled fixtures.

**Observed:** Public bot dispatch and execution select March for Belgae4 Hidden versus12 Revealed Roman Auxilia, Arverni10 Hidden versus20 Auxilia, and Germans6 Hidden versus18 Auxilia; the named attacking Leader is adjacent in Bituriges. Public authored Battle+Ambush succeeds from each identical starting board, removing2/5/3 Auxilia respectively and no attackers. Each ordinary no-Ambush forecast is unfavorable (Attack/Counterattack2/5,5/7,3/7).

**Cause:** The three ordinary _can_battle_in_region consumers filter candidates with predict_battle in its default no-Ambush mode. Their _determine_battle_sa runs only after a nonempty accepted Battle plan, so Ambush cannot rescue a candidate that it would make satisfy the printed requirements.

**Sources:** [Reference Documents/Chapter 8:244](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Chapter%208#L244); [Reference Documents/Chapter 8:583](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Chapter%208#L583); [Reference Documents/Ariovistus/Chapter A8:78](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Ariovistus/Chapter%20A8#L78); [Reference Documents/Chapter 4:138](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Chapter%204#L138).

**Implementation:** [fs_bot/bots/belgae_bot.py:235](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/bots/belgae_bot.py#L235); [fs_bot/bots/belgae_bot.py:275](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/bots/belgae_bot.py#L275); [fs_bot/bots/belgae_bot.py:740](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/bots/belgae_bot.py#L740); [fs_bot/bots/arverni_bot.py:198](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/bots/arverni_bot.py#L198); [fs_bot/bots/arverni_bot.py:751](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/bots/arverni_bot.py#L751); [fs_bot/bots/german_bot.py:224](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/bots/german_bot.py#L224); [fs_bot/bots/german_bot.py:970](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/bots/german_bot.py#L970).

**Controls:** Nine cases: three legal-Ambush failure witnesses plus the same three with all attacking Warbands Revealed and the same three with Command-only planning. Both control variants correctly March. Three public authored legal Ambush alternatives independently prove exact casualties, unchanged attacker counts and valid board accounting.

**Earlier-audit distinction:** NP5-03 and NP6-01 repaired ordinary surviving-defender Counterattack estimates and named Attack multipliers; their recorded cases deliberately disabled Special Abilities. This is the distinct plan dependency that rejects a candidate before Ambush is considered; the ordinary arithmetic itself now agrees with execution. Human Ambush caps/alternate German Ambush resolution findings address different callers and rules.

**Repair scope:** Evaluate legal/allowed first-Battle Ambush and its printed decision rule while constructing candidates, preserve Command-wide SA selection and first-Battle restrictions, and use that forecast in comparative/leader-safety gates. Keep no-SA and hidden/Leader-range controls; handle defending Caesar conservatively under the printed condition.

**Fixture:** Sparse build_initial_state controlled positions, canonical piece placement, permanent Provincia Fort retained. All relevant pre/post states pass validate_state and check_structural_integrity. No physical counts directly edited.

**Limits:** Controlled lawful witnesses prove mechanism, not naturally sampled frequency. No claim of exhaustive capability, flowchart, casualty-choice or action-path coverage. No production changes.

**Evidence:** `PYTHONPATH=<fs-bot-root> python bots/probe_bots.py`; `bots/probe_bots-output.json`.

### NP7-02 — All four Raid planners ignore shaded Baggage Trains' third Warband during ordinary turns

**Expected:** The owning Non-player with three Hidden Warbands in a non-Devastated Region and no eligible stealing target must execute the gain-from-no-Faction Raid priority to its legal three-Warband capacity, gaining3 Resources and Revealing all3.

**Observed:** Belgae, Arverni, Aedui and Germans each publicly choose and execute Raid but plan only2 flips, gain2 Resources, and leave1 Warband Hidden despite owning card8 shaded. The same states accept and execute authored three-flip Raid, yielding3 Resources and zero Hidden Warbands. Without the capability, each ordinary bot correctly gains2 and leaves1 Hidden.

**Cause:** Each _would_raid_gain_enough sets raid_limit=2 and only tests Baggage Trains inside `if raiders is not None`. Ordinary node_*_raid calls omit that optional participant argument, so capability capacity is never consulted. The actual executor max_raiders_per_region already returns3 for the owner.

**Sources:** [Reference Documents/Card Reference:75](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Card%20Reference#L75); [Reference Documents/Chapter 8:57](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Chapter%208#L57); [Reference Documents/Chapter 8:137](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Chapter%208#L137); [Reference Documents/Chapter 8:376](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Chapter%208#L376); [Reference Documents/Chapter 8:503](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Chapter%208#L503); [Reference Documents/Chapter 8:732](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Chapter%208#L732); [Reference Documents/Ariovistus/Chapter A8:196](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/Reference%20Documents/Ariovistus/Chapter%20A8#L196).

**Implementation:** [fs_bot/bots/belgae_bot.py:326](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/bots/belgae_bot.py#L326); [fs_bot/bots/arverni_bot.py:315](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/bots/arverni_bot.py#L315); [fs_bot/bots/aedui_bot.py:507](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/bots/aedui_bot.py#L507); [fs_bot/bots/german_bot.py:1197](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/bots/german_bot.py#L1197); [fs_bot/commands/raid.py:53](https://github.com/FeeSimple1/fs-bot/blob/c67d501711471bf790d805c017c2125b2c254639/fs_bot/commands/raid.py#L53).

**Controls:** Eight cases across all four playable Raid bots, each with and without the owned Capability. Capacity helper, response validator and public execution agree on3 versus2. Every input/output pool and structure check passes. Resources start0 for all seats; four Revealed Roman Auxilia prevent local Control, Roman Resources0 exclude stealing, and no Leader or SA affects the fixture.

**Earlier-audit distinction:** Earlier Baggage Trains tests cover the mechanics accepting three Raiders and stealing through Forts; original EXP-06 repair dealt with the German free-Intimidate count from actual Raiders. No prior comparison finding records ordinary NPC Raid quantity plans. Optional physical cohort logic supports card8 already but is not called by these ordinary policy nodes.

**Repair scope:** Use shared max_raiders_per_region in each ordinary and restricted-cohort Raid plan, then cap by actual eligible Hidden participants. Preserve Resource limits, target priority, and any free-Intimidate accounting from actual Raiders.

**Fixture:** Sparse build_initial_state controlled positions, canonical piece placement, permanent Provincia Fort retained. All relevant pre/post states pass validate_state and check_structural_integrity. No physical counts directly edited.

**Limits:** Controlled lawful witnesses prove mechanism, not naturally sampled frequency. No claim of exhaustive capability, flowchart, casualty-choice or action-path coverage. No production changes.

**Evidence:** `PYTHONPATH=<fs-bot-root> python bots/probe_bots.py`; `bots/probe_bots-output.json`.

## Excluded leads and unresolved sources

The exploratory no-op scan was a search aid, not an automatic finding list. A31/Abatis forecast drift, other Archers/Elite interactions, other fixed Event handlers, and additional German flowchart suspicions lacked a finalized public consequence in this pass and are excluded. Fixture mistakes were corrected or discarded before final evidence. Existing open source questions remain in `QUESTIONS.md`; this audit adds none.
