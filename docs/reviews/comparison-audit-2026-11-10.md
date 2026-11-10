# Falling Sky comparison audit — 10 November 2026

Batch 1 closed six findings after this audit. Current dispositions and
validation are in the [finding ledger](comparison-audit-2026-11-10.json)
and the [repair report](../current-status.md#10-november-human-turn-plan-scope).

**21 confirmed open findings, comprising 15 high and 6 medium priority.** This follow-up compares Falling Sky with Liberty or Death’s approaches to human choices, validation, and effect verification. Each finding has an executable witness and a cited Falling Sky rule. No gameplay repairs are included in this audit.

Falling Sky was audited at `b23c8cd73c9747e6e39157a042a1af13cc703a48` with Python-source SHA-256 `9f48dc76fa0b171c71efa604ca7d486cd87daaf8817a7eda5aa34df67822dfa5`. Liberty or Death was inspected at `2991ea279062773548ec390a1da75f3e85381702`. The supplied Falling Sky references and thirteen adopted provisional rulings govern the rules conclusions.

The original 50 findings keep their recorded repair dispositions. These 21 groups cover additional instances and newly confirmed leads. Previously recorded Circumvallation persistence problems remain outside this count. Several findings share a bug class with earlier repairs but affect different paths or card effects.

[Finding ledger](comparison-audit-2026-11-10.json) · [Portable reproduction evidence](comparison-audit-2026-11-10-evidence.zip) · [Original repair ledger](../human-choice-progress.json)

## Comparison method

| Liberty or Death pattern | Falling Sky checks prompted by it |
|---|---|
| `engine.py` checks actual affected spaces and Special Activity use before committing an action | Offered action versus inner plan, inactive `command_parts`, alternate March shapes, and repeated Region effects |
| `interactive_cli.py` binds an Event runner to the current card and selected menu action | Off-card Event IDs and an Event disguised as a Limited Command |
| `docs/human_mode_audit.md` corrects its earlier reliance on existing hooks, and `event_choices.py` validates typed choices | Printed prerequisites, named Leaders, required quantities, exact Tribes, and omitted card effects |
| `docs/audit_set_but_never_applied_s76.md` traces effects to their final observation point | Ambush saving rolls, Scouted Warbands, duplicate score calculations, and Citadel allegiance after placement |
| `coin-implementation-lessons.md` records repeated effects and representation mismatches | Battle, Devastate, Assembly of Gaul, and multiple ways to encode March |

The review covered Commands and Special Abilities, Battle and movement, base/revised and expansion Events, terminal and durable sessions, ownership, saves, and seasonal routing. Close base-card witnesses concentrate on 7, 11, 19, 23, 52, 56, and 68. The expansion pass read all 39 A-prefix handlers and concentrated new witnesses on the earlier unverified rows. The archive preserves partition-specific coverage and limitations.

## Confirmed findings

High priority denotes an illegal action, materially wrong effect, or inconsistent game state. Medium priority denotes a narrower rule or player-choice failure. These are repair groups, so multiple affected card profiles or representations do not each add a finding.

| ID | Priority | Finding |
|---|---|---|
| FE2-01 | high | Assistant accepts an Event under a Limited Command and ungranted Special Abilities attached to Events |
| FE2-02 | high | Assistant Event submissions can execute any supplied card ID instead of the current Event |
| XC2-01 | high | A shadow command_parts list lets a Limited Command execute in multiple Regions |
| CM2-01 | high | Ordinary Battle accepts repeated Regions and the attacker as its own defender |
| CM2-02 | high | Alternate March forms bypass Limited Command and Britannia restrictions |
| CM2-03 | high | Repeated Devastate Regions apply extra rounds of casualties in one Special Ability |
| BM2-01 | high | Fort defense incorrectly restores Ambush saving rolls and suppresses Caesar’s test |
| BE2-01 | high | Shaded Sacking removes a Legion without the executor’s Citadel |
| BE2-02 | high | Assembly of Gaul drains the same Faction repeatedly in one Event |
| BE2-03 | medium | Remi Influence permits skipping its mandatory Allied Tribe replacement |
| BE2-04 | medium | Lucterius mishandles the Arverni Successor condition and same-Region restoration |
| BE2-05 | medium | Flight of Ambiorix rejects a live Successor and accepts forbidden return Regions |
| BE2-06 | medium | Flight of Ambiorix uses an inflated Belgic victory total |
| BE2-07 | high | Roman reinforcement Events accept placements outside their printed areas |
| EX2-01 | medium | Abatis silently fails when the qualifying Warband is Scouted |
| EX2-02 | medium | Siege of Bibrax shaded removes a different Allied Tribe than selected |
| EX2-03 | high | Seduni Uprising and shaded Dumnorix remove protected or unrelated Citadels |
| EX2-04 | high | Mandatory expansion Event quotas can be skipped while other effects commit |
| EX2-05 | high | Kinship shaded can convert Aedui pieces despite its Belgae/Germans restriction |
| EX2-06 | high | Procillus unshaded incorrectly treats the Roman Successor as Caesar |
| EX2-07 | high | Orgetorix shaded Citadel placement leaves its City Tribe unallied |

## Repair order

| Batch | Work | Findings |
|---|---|---|
| 1 | Bind human actions to their allowed scope | FE2-01, FE2-02, XC2-01, CM2-01, CM2-02, CM2-03 |
| 2 | Correct combat and Citadel state | BM2-01, EX2-07 |
| 3 | Enforce Event prerequisites, targets, and scores | BE2-01, BE2-02, BE2-04, BE2-05, BE2-06, BE2-07, EX2-03, EX2-05, EX2-06 |
| 4 | Complete mandatory and physical Event choices | BE2-03, EX2-01, EX2-02, EX2-04 |

Batch 1 should be split into focused changes to action identity, active plan parsing, movement footprint, and repeated selections. Each fix should turn its observed-defect witness into a desired-behavior regression, including rejection without changing a pending decision when applicable.

## Earlier unverified rows

All 34 earlier unverified rows were revisited. Their dispositions are recorded individually in the JSON ledger.

| Disposition | Rows |
|---|---:|
| Newly confirmed gap | 12 |
| Supported by limited checks in the reviewed path | 7 |
| Still unverified | 15 |

The retained rows concern ten base-card scarcity/allocation cases, four A27/A32 cases with unresolved scarcity or complete-phase coverage, and the advance Harassment promise. FE-NOPRUNING now has a confirmed action-contract defect while its broader specialized-menu completeness question remains. Limited positive checks establish only the tested paths.

## Validation

All **9,334 existing tests passed**, with zero failures, errors, or skips. A separate reviewer reran all nine probe scripts and checked the printed rules, fixture validity, and overlap with earlier findings. The archive contains executable witnesses, observed outputs, review hashes, and the fresh test log. The probe assertions deliberately describe the current defects and will need updating when those defects are repaired.

Two frontend witnesses start ordinary Great Revolt sessions at seed 46 through `init`, `play`, and `submit`, with no edited setup or save. The other witnesses use initialized or scenario-derived controlled positions and the public validation/execution routes named in their records. Terminal pickers can prevent inputs that remain accepted by the durable/API interface.

The Orgetorix Citadel witness starts structurally valid and ends with two structural errors, demonstrating the bug. Most other incorrect outcomes pass the board validators. Existing Ambush and Lucterius tests also encode incorrect expectations, which helps explain why the established suite passes.

No fresh bot balance matrix was run because the audit leaves gameplay code unchanged. This review provides targeted evidence and coverage records. It does not recertify every state combination or every row of the original 490-row inventory.

To rerun the evidence, extract the ZIP and run the following against the audited checkout. Python 3.10 or newer is sufficient. The output directory must be new.

```sh
python run_probes.py /path/to/fs-bot /path/to/new-results
```

## Evidence by finding

### FE2-01 — Assistant accepts an Event under a Limited Command and ungranted Special Abilities attached to Events

Reject the plan and keep d000002 pending with the board, Resources, RNG and eligibility unchanged.

The submission is committed as limited_command but executes Ambacti, adding six Roman Auxilia in Provincia (6→12). The same validator accepts Event16 with a standalone Scout, which moves an additional Auxilia from Provincia to Sequani even though the card grants no Scout.

Rule basis is Chapter 2 §§2.3.4–2.3.5; Chapter 4 §4.1; Card 16 unshaded.

Newly confirmed prior unverified lead in FE-NOPRUNING. Never part of the original 50 confirmed findings.

[fs_bot/tools/seat_session.py:91–113](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/tools/seat_session.py#L91) · [fs_bot/engine/action_validation.py:233–246](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/engine/action_validation.py#L233) · [fs_bot/engine/execute.py:495–512](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/engine/execute.py#L495) · [fs_bot/engine/game_engine.py:671–689](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/engine/game_engine.py#L671)

### FE2-02 — Assistant Event submissions can execute any supplied card ID instead of the current Event

Reject card13 while card16 is current and retain the same pending decision, or resolve only the current card when redundant identity is absent.

The submission commits a turn recorded against card16, but applies card13 Balearic Slingers and installs capability13 Unshaded. It then advances normally.

Rule basis is Chapter 2 §2.3.4, Event shown on the card; Chapter 5 §5.1.

New confirmed finding outside the original 50.

[fs_bot/engine/execute.py:3413–3415](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/engine/execute.py#L3413) · [fs_bot/engine/execute.py:3444–3467](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/engine/execute.py#L3444) · [fs_bot/tools/seat_session.py:91–113](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/tools/seat_session.py#L91)

### XC2-01 — A shadow command_parts list lets a Limited Command execute in multiple Regions

A Limited Command selects just one Region. Extra inactive representations of a Command must be rejected or excluded from its legality calculation.

The durable assistant accepts a Limited Recruit whose real recruit_plan names Provincia and Sequani when command_parts contains a single Provincia-only Recruit. It commits one new Auxilia to each Region and records the supplied plan in the decision log. Without the shadow command_parts field, the same two-Region plan is rejected.

Rule basis is Reference Documents/Chapter 2, lines 65-67, section 2.3.5.

New confirmed ordinary Sequence-of-Play gap. Related shadow-plan guards already exist for special Event grants and Seize, including test_roman_event_grants.py:339 and test_seize_tribes.py:95-105. The general Limited Command validator still accepts the shape. This is distinct from repeated Battle Region execution and outer action-label mismatches.

[fs_bot/engine/action_validation.py:50-51](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/engine/action_validation.py#L50) · [fs_bot/engine/action_validation.py:258-281](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/engine/action_validation.py#L258) · [fs_bot/engine/execute.py:503-505](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/engine/execute.py#L503) · [fs_bot/tools/seat_session.py:109-113](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/tools/seat_session.py#L109)

### CM2-01 — Ordinary Battle accepts repeated Regions and the attacker as its own defender

A Command selects a Region only once and Battles exactly one opposing Faction there. Durable human input must reject repeated Battle Regions and self-targets before accepting a turn.

A Limited Command with two Carnutes Battle entries, one against Arverni and one against Aedui, passes durable validation and executes two Battles, removing both defending Warbands. The legal one-entry control removes only the first defender. A separate Battle targeting the attacking Romans passes validation and reduces four Roman Auxilia to one by fighting themselves.

Rule basis is Reference Documents/Chapter 3:3-11 (§3.1); Reference Documents/Chapter 3:125-136 (§3.2.4).

New confirmed extension beyond the closed Seize/Entreat repetition finding. Duplicate and opposing-Faction checks currently exist only for the sa_after_step Battle form.

[fs_bot/engine/action_validation.py:29-47](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/engine/action_validation.py#L29) · [fs_bot/engine/action_validation.py:163-184](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/engine/action_validation.py#L163) · [fs_bot/engine/action_validation.py:267-274](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/engine/action_validation.py#L267) · [fs_bot/engine/execute.py:3873-3900](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/engine/execute.py#L3873)

### CM2-02 — Alternate March forms bypass Limited Command and Britannia restrictions

The one-origin Limited March and Britannia Special Ability prohibition must apply to every accepted March representation. Extra groups must use selected origins.

A Limited March moves Aedui Warbands from Carnutes to Veneti and Mandubii to Treveri and pays for both origins when encoded as explicit_moves or with an undeclared extra_groups origin. Equivalent canonical two-origin input is rejected. An explicit_moves March from Britannia to Morini then executes Trade for six Resources, while the equivalent origins/routes plan is rejected under §4.1.3.

Rule basis is Reference Documents/Chapter 2:65-67 (§2.3.5); Reference Documents/Chapter 4:38-39 (§4.1.3).

New confirmed normalization gap. Both origins/routes and alternate accepted plan representations reach the public human executor.

[fs_bot/engine/action_validation.py:34-36](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/engine/action_validation.py#L34) · [fs_bot/engine/action_validation.py:267-274](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/engine/action_validation.py#L267) · [fs_bot/engine/action_validation.py:290-305](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/engine/action_validation.py#L290) · [fs_bot/engine/execute.py:4274-4279](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/engine/execute.py#L4274) · [fs_bot/engine/execute.py:4334-4337](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/engine/execute.py#L4334)

### CM2-03 — Repeated Devastate Regions apply extra rounds of casualties in one Special Ability

A Devastate Special Ability may select Carnutes only once and applies one casualty fraction there.

Raid Veneti with sa_regions [Carnutes, Carnutes] for Devastate is accepted as a durable human turn. Carnutes begins with Vercingetorix, 12 Arverni Warbands and 9 Roman Auxilia. It ends with 7 Warbands and 4 Auxilia after two reductions. The legal one-Region control leaves 9 Warbands and 6 Auxilia. Execution reports success and no errors.

Rule basis is Reference Documents/Chapter 4:8-11 (§4.1); Reference Documents/Chapter 4:121-131 (§4.3.2).

New confirmed extension of the repetition family. The original closed finding explicitly covered Seize and Entreat, and the Devastate repair covered casualty ownership and physical selection.

[fs_bot/engine/action_validation.py:54-88](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/engine/action_validation.py#L54) · [fs_bot/engine/execute.py:5093-5111](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/engine/execute.py#L5093) · [fs_bot/commands/sa_devastate.py:34-62](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/commands/sa_devastate.py#L34)

### BM2-01 — Fort defense incorrectly restores Ambush saving rolls and suppresses Caesar’s test

A Fort halves the Attack Losses. Ambush still removes a piece for each resulting Loss without a saving roll. Caesar makes the printed exception test, and a successful test permits saving rolls and Counterattack.

An accepted Aedui Battle+Ambush with eight Warbands against three Roman Legions and a Fort inflicts two halved Losses but removes no Legions with seed0. With Caesar added, no Caesar test or Counterattack occurs. Both outcomes pass the board validator.

Rule basis is Reference Documents/Chapter 4 §§4.3.3, 4.4.3, 4.5.3; Chapter 3 §3.4.4.

The original inventory left BM-AMBUSH-FORT-SOURCE unverified. This audit promotes it to a confirmed mechanics defect. Existing tests encode the incorrect Fort interpretation.

[fs_bot/battle/resolve.py:195](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/battle/resolve.py#L195) · [fs_bot/battle/resolve.py:252](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/battle/resolve.py#L252) · [fs_bot/battle/resolve.py:269](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/battle/resolve.py#L269) · [fs_bot/tests/test_battle.py:842](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/tests/test_battle.py#L842)

### BE2-01 — Shaded Sacking removes a Legion without the executor’s Citadel

Only a Region with both a Legion and the executing Faction’s Citadel can trigger removal and Roman Ineligibility.

Great Revolt Belgae submits Treveri, which has two Roman Legions and no Belgic Citadel. One Legion moves to Fallen and Romans become forced Ineligible.

Rule basis is Reference Documents/Card Reference card 23 lines225-236; Chapter 5 §5.1.

New confirmed target-validation defect. The previous BE-11 repair expressly covered cards 40/41/42/51, not card 23. Existing positive Sacking test uses a Citadel and misses the illegal target.

[fs_bot/cards/card_effects.py:1104](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/cards/card_effects.py#L1104) · [fs_bot/cards/card_effects.py:1115](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/cards/card_effects.py#L1115)

### BE2-02 — Assembly of Gaul drains the same Faction repeatedly in one Event

Each selected Gallic Faction loses eight Resources once.

With Carnutes Subdued, target_factions=[Arverni,Arverni] drops Arverni from 20 to 4 instead of 12. The durable turn accepts the duplicate list.

Rule basis is Reference Documents/Card Reference card 52 lines518-526; Chapter 5 §§5.1,5.1.3.

New confirmed Event-specific duplicate-target defect, beyond original CMD-SEIZE-TRIBES/Entreat duplicate fixes and BE-11’s four frozen Event families. The CLI generic list avoids duplicates, but durable/API plans accept them.

[fs_bot/cards/card_effects.py:1960](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/cards/card_effects.py#L1960)

### BE2-03 — Remi Influence permits skipping its mandatory Allied Tribe replacement

If Remi is Roman/Subdued and eligible Allies exist, select one or two eligible Allies and perform the replacement as possible.

The standard Great Revolt setup has Roman Remi, eligible Belgic Bellovaci in Atrebates, and Available Roman Ally discs. replacements=[] is accepted as an executed Event with all Tribes unchanged.

Rule basis is Reference Documents/Card Reference card 68 lines699-708; Chapter 5 §5.1.3.

New mandatory-minimum defect. Previous BE-03/BE-08 Remi repairs addressed shaded beneficiary/City choices. Existing Boii and shaded Roman Wine minimum guards provide in-repo repair examples.

[fs_bot/cards/card_effects.py:2555](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/cards/card_effects.py#L2555)

### BE2-04 — Lucterius mishandles the Arverni Successor condition and same-Region restoration

The shaded effect requires an Arverni Successor and places that Leader symbol-up as Vercingetorix, including when selecting its current Region.

Selecting the on-map Successor’s current Region leaves it a Successor. Conversely a live Vercingetorix can be moved from his existing Region to Britannia because the handler never checks the Successor precondition.

Rule basis is Reference Documents/Card Reference card 19 lines181-190; Chapter 5 §5.1.

New shaded defect. Prior BE-06/07/08 Lucterius work was expressly unshaded. Existing test_card19_shaded_relocates_successor_on_map actually creates Vercingetorix and asserts the illegal relocation.

[fs_bot/cards/card_effects.py:927](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/cards/card_effects.py#L927) · [fs_bot/tests/test_card_effects.py:1470](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/tests/test_card_effects.py#L1470)

### BE2-05 — Flight of Ambiorix rejects a live Successor and accepts forbidden return Regions

When Ambiorix is absent, the Belgic Leader may be on its Successor side and must be placed symbol-up in Germania or Morini/Nervii/Treveri/Sequani.

An on-map Successor causes an immediate no-op even with legal Treveri selected. With the Leader Available, target_region=Britannia places Ambiorix there despite the printed geographic restriction.

Rule basis is Reference Documents/Card Reference card 56 lines567-575; Chapter 5 §5.1.

New confirmed shaded return defects. Existing test_card_56_shaded_place_ambiorix uses an Available Leader and a legal Germania destination only.

[fs_bot/cards/card_effects.py:2086](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/cards/card_effects.py#L2086) · [fs_bot/cards/card_effects.py:2095](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/cards/card_effects.py#L2095)

### BE2-06 — Flight of Ambiorix uses an inflated Belgic victory total

The card uses the ordinary Belgic Control-Allies victory total. A score below ten removes Ambiorix even outside Roman Control.

A census-valid board with real score 9 (calculated by engine.victory) retains Ambiorix because the Event counts a Citadel once through Tribe allegiance and again through Citadel pieces, producing 10.

Rule basis is Reference Documents/Card Reference card 56 lines567-575; Chapter 7 §§7.2–7.3; Chapter 1 §1.9.

New confirmed scoring divergence. Handler also omits normal Colony/Dispersed adjustments by static trace, but those additional boundaries were not dynamically claimed.

[fs_bot/cards/card_effects.py:2072](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/cards/card_effects.py#L2072) · [fs_bot/cards/card_effects.py:2077](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/cards/card_effects.py#L2077) · [fs_bot/cards/card_effects.py:2080](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/cards/card_effects.py#L2080)

### BE2-07 — Roman reinforcement Events accept placements outside their printed areas

Alaudae places only in a Roman Controlled Region. Numidians places only within one Region of the Roman Leader.

From standard Great Revolt setup, Alaudae puts one Legion and one Auxilia in empty Britannia. Original/revised Numidians puts three Auxilia in Britannia although Caesar is in Mandubii and Britannia is outside his range. Durable validation accepts both and normal execution commits.

Rule basis is Reference Documents/Card Reference cards 7 and11; revised 11 in Reference Documents/Ariovistus/A Card Reference; Chapter 5 §5.1.

New confirmed geographic validation errors. Prior BE-11 covered cards 40/41/42/51. Recent Alaudae and Numidians repairs addressed shaded losses, and BE-02 addressed the Numidians Battle after placement.

[fs_bot/cards/card_effects.py:616](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/cards/card_effects.py#L616) · [fs_bot/cards/card_effects.py:710](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/cards/card_effects.py#L710) · [fs_bot/cards/card_effects.py:4098](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/cards/card_effects.py#L4098)

### EX2-01 — Abatis silently fails when the qualifying Warband is Scouted

A Scouted Warband satisfies the card's unqualified Warband requirement and permits the marker.

A64_Scouted validates and executes successfully but places no marker. Hidden and Revealed controls place it.

Rule basis is A Card Reference A64; Chapter 1 §1.4.3; Chapter 4 §4.2.2.

Newly confirmed from a formerly not-verified row in the 29 October inventory. No original closed finding is being counted again.

[fs_bot/cards/card_effects.py:3854](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/cards/card_effects.py#L3854) · [fs_bot/engine/execute.py:6283](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/engine/execute.py#L6283)

### EX2-02 — Siege of Bibrax shaded removes a different Allied Tribe than selected

The executor selects which eligible physical Allied Tribe to remove.

With Roman Allies at both Atrebates and Remi, the accepted plan names Remi but removes Atrebates. Remi stays Roman. The handler never reads the tribe field and clear_allied_tribe falls back to sorted order.

Rule basis is A Card Reference A51 shaded; Chapter 5 §5.1.

Newly confirmed from a formerly not-verified row in the 29 October inventory. No original closed finding is being counted again.

[fs_bot/cards/card_effects.py:3618](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/cards/card_effects.py#L3618) · [fs_bot/cards/card_effects.py:3625](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/cards/card_effects.py#L3625) · [fs_bot/board/pieces.py:912](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/board/pieces.py#L912)

### EX2-03 — Seduni Uprising and shaded Dumnorix remove protected or unrelated Citadels

A24 removes Ally discs at the named Tribes. A43 removes structures only at its named Tribes, which include Helvetii but exclude Sequani.

A24 removes the Aedui Citadel at Sequani despite 20 defending Aedui Warbands surviving. A43 also removes this Citadel while processing Helvetii, a different Tribe in the same Region. Both accepted Events finish without structural violations.

Rule basis is A Card Reference A24; A Card Reference A43 shaded; Chapter 1 §1.4; Chapter 5 §§5.1–5.1.1.

Newly confirmed from a formerly not-verified row in the 29 October inventory. No original closed finding is being counted again.

[fs_bot/cards/card_effects.py:2955](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/cards/card_effects.py#L2955) · [fs_bot/cards/card_effects.py:3520](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/cards/card_effects.py#L3520)

### EX2-04 — Mandatory expansion Event quotas can be skipped while other effects commit

With ample Available pieces and eligible locations, require nine Arverni placements for A30, four Belgic Warbands plus two Allies for A56, and four Warband plus two Ally replacements for A65.

Empty lists pass validation and execute. A30 removes an Aedui Ally but places zero Arverni. A56 grants four Resources while placing zero pieces. A65 leaves all six eligible source pieces untouched despite full replacement supply.

Rule basis is A Card Reference A30 shaded; A Card Reference A56 shaded; A Card Reference A65 shaded; Chapter 5 §5.1.3.

Newly confirmed from a formerly not-verified row in the 29 October inventory. No original closed finding is being counted again.

[fs_bot/cards/card_effects.py:3180](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/cards/card_effects.py#L3180) · [fs_bot/cards/card_effects.py:3692](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/cards/card_effects.py#L3692) · [fs_bot/cards/card_effects.py:3882](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/cards/card_effects.py#L3882)

### EX2-05 — Kinship shaded can convert Aedui pieces despite its Belgae/Germans restriction

The source is exactly Belgae or Germans and the destination is the other of those two.

from_faction=Aedui is accepted. Four Aedui Warbands and two Aedui Allies in Morini become six Belgic pieces.

Rule basis is A Card Reference A65 shaded; Chapter 5 §5.1.

Newly confirmed from a formerly not-verified row in the 29 October inventory. No original closed finding is being counted again.

[fs_bot/cards/card_effects.py:3879](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/cards/card_effects.py#L3879) · [fs_bot/cards/card_effects.py:3880](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/cards/card_effects.py#L3880)

### EX2-06 — Procillus unshaded incorrectly treats the Roman Successor as Caesar

Only Caesar supplies the within-one-Region selection range named on the card.

With the Roman Leader showing Successor in Sequani, the accepted Event replaces the German Ally there with a Roman Ally. The Caesar control produces the same effect.

Rule basis is A Card Reference A19 unshaded; Chapter 1 §1.4.3; Chapter 5 §5.1.

Newly confirmed from a formerly not-verified row in the 29 October inventory. No original closed finding is being counted again.

[fs_bot/cards/card_effects.py:2816](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/cards/card_effects.py#L2816)

### EX2-07 — Orgetorix shaded Citadel placement leaves its City Tribe unallied

A Citadel occupies and allies its City Tribe, with consistent structure and allegiance records.

A complete nine-piece plan places one Arverni Citadel and eight Warbands at Sequani. The Event succeeds, but Sequani remains unallied. check_structural_integrity reports both missing City allegiance and mismatched backing pieces.

Rule basis is A Card Reference A30 shaded; Chapter 1 §1.4.2.

Newly confirmed from a formerly not-verified row in the 29 October inventory. No original closed finding is being counted again.

[fs_bot/cards/card_effects.py:3195](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/cards/card_effects.py#L3195) · [fs_bot/state/state_schema.py:428](https://github.com/FeeSimple1/fs-bot/blob/b23c8cd73c9747e6e39157a042a1af13cc703a48/fs_bot/state/state_schema.py#L428)
