# Twelfth Falling Sky / Liberty or Death comparison audit

**13 November 2026. Seven new medium-priority findings, arranged into four repair batches.**

Batch 1 closed EV12-01 and EV12-02 on 14 November. Five findings remain open.
[Batch 1 repair and validation](twelfth-comparison-batch1-2026-11-14.md)

The eleventh audit is complete with all eight findings repaired. This review starts at Falling Sky commit `1563e41d84f61dfce43ce4008106eca2a1639aed`, with Python source SHA-256 `7cb64407ff5594eb2bbd671a8159c408410fa8cc26e7a784da7afe0fd47363db` across 629 files. The Liberty or Death comparison uses `2991ea279062773548ec390a1da75f3e85381702`. Both revisions matched their remote `main` branches at the start of review.

[Finding ledger](comparison-audit-round12-2026-11-13.json) · [Reproduction evidence](comparison-audit-round12-2026-11-13-evidence.zip) · [Current status](../current-status.md)

## Confirmed findings

| ID | Priority | Finding |
|---|---|---|
| EV12-01 | Medium | Unshaded Sappers ignores non-player target restrictions and admits Events without a Citadel target |
| EV12-02 | Medium | Non-player Drought places its marker by map order and removes forbidden targets |
| BM12-01 | Medium | Belgae, Arverni and German Battle gates omit Balearic Slingers opening fire |
| LC12-01 | Medium | Non-player Interlude evacuation removes every Cisalpina force despite legal Home destinations |
| LC12-02 | Medium | Non-player Interlude Ally reductions remove a City Ally before a non-City Ally |
| NP12-01 | Medium | Aedui spreading March collapses three one-Warband groups into one large move |
| NP12-02 | Medium | Aedui March drops the post-Command Trade opportunity when its initial Suborn choice is empty |

## Method and coverage

The review examined Events, bot decisions, Battle, lifecycle, and human interfaces in five parallel lanes, followed by an independent verification lane and lead review. Actual Liberty or Death implementation paths supplied comparisons for eligible-target ranking, semantic Event previews, shared Battle calculations, explicit movement groups, post-Command activities, seasonal piece priorities, and detached human planning. Every Falling Sky rules conclusion uses the supplied references and the thirteen adopted provisional rulings.

All seven findings have public dispatch or execution witnesses, canonical piece accounting, before-and-after census and structural checks, and matched controls. Six finalized scripts were independently copied and rerun at hash seeds 0 and 987. Their outputs match the authors’ results byte for byte. The evidence preserves 43 Event executions, 17 Battle cases, 24 Aedui cases, 26 complete third-Winter cases, and four passing terminal cases.

The positions deliberately isolate individual rules. Lane reports describe sparse boards, controlled card identities and Winter cursors, explicit diagnostic plan changes, and source limitations. The samples establish the listed failures without estimating ordinary-game frequency. Sappers was an unconfirmed lead in round five. This round supplies its missing reproduction and source evidence. Other findings extend known defect classes to separately unrepaired consumers.

The human-interface lane found no new confirmed defect in its focused review. Four terminal controls cover Build Fort-plus-Ally choices and physical Scout movement/targets in Great Revolt and Ariovistus, with detached planning, typed response validation, and serialized-state replay. A further 113 existing interface regressions pass. Additional interface coverage is identified as static review in the lane report.

## Verification

| Check | Result |
|---|---|
| Fresh full suite | 10,449 passed, zero failures/errors/skips. Five external anyio/pytest deprecation warnings. |
| Fresh audited bot games | 20 complete across all five scenarios, second-edition seeds 71–74. Zero engine errors, census/structure findings or ranking issues. One game reaches the Interlude. All 329 diagnostic occurrences classify as legal declines. |
| Fresh mixed-seat replay | 20 cases at each of two hash seeds, each with internal replay, for 80 executions. JSON and stdout match. 617 human turns, 152 Event turns, zero hard findings. Five partial plans across four completed cases are preserved. |
| Directed evidence | All six final scripts reproduce independently at hash seeds 0 and 987 with identical outputs. All seven groups survive source and prior-finding review. |
| Source integrity | All 47 supplied references and canonical constants match the recorded hashes. The 629-file Python digest matches the audited baseline. |
| Audited revision on GitHub | All 14 baseline checks passed, including platform tests, package installation, held-out card-edition games and the 100-game balance guardrail. |

The fresh suite includes the existing 15-game balance canary. The 100-game guardrail result belongs to the audited revision’s existing GitHub run. The five mixed-seat partial plans occur in Pax Gallica seed 71, Great Revolt seed 71, Reconquest seed 73, and Gallic War seed 74, with two partial plans in the last case. All four games finish. The raw validation records preserve these limits.

## Proposed repair order

| Batch | Findings | Scope |
|---|---|---|
| 1 | EV12-01, EV12-02 | Closed. [Sappers and Drought non-player target selection](twelfth-comparison-batch1-2026-11-14.md). |
| 2 | BM12-01 | Slingers opening fire in three bot Battle forecasts |
| 3 | LC12-01, LC12-02 | Interlude Cisalpina relocation and exact Allied Tribe removals |
| 4 | NP12-01, NP12-02 | Aedui March groups and post-March Trade or Suborn |

Convert each witness and its controls into regressions during repair. Resolve Aedui movement quantities before finalizing its post-March Trade expectations, because the corrected destinations can change the resulting Trade income. Trace changed full-game outcomes before considering a balance baseline update.

## Finding details

### EV12-01 — Unshaded Sappers ignores non-player target restrictions and admits Events without a Citadel target

**Expected behavior.** Base Roman Sappers targets Arverni then Belgae and excludes Aedui. Base Aedui Sappers targets player Arverni or Belgae only. If no legal Citadel target can lose Resources, the Non-player must continue its Command flowchart.

**Observed behavior.** Seven natural dispatch/execution cases drain the wrong Faction. Romans and Aedui drain Aedui instead of player Belgae in four cases. Aedui drain Non-player Arverni instead of player Belgae in three cases. Two no-Citadel Pax Gallica cases select and execute an Event with no game effect.

**Cause.** _EVENT_PARAM_DERIVERS has no numeric24 producer. The handler falls back to the first Citadel faction in GALLIC_FACTIONS, ordered Arverni, Aedui, Belgae. Generic REMOVES_RESOURCES effectiveness returns true without checking the Citadel or printed target conditions.

[Reference Documents/Chapter 8 L30](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Chapter%208#L30) · [Reference Documents/Chapter 8 L69](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Chapter%208#L69) · [Reference Documents/Chapter 8 L129](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Chapter%208#L129) · [Reference Documents/Card Reference L238](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Card%20Reference#L238) · [Reference Documents/roman_bot_event_instructions.txt L18](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/roman_bot_event_instructions.txt#L18) · [Reference Documents/aedui_bot_event_instructions.txt L30](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/aedui_bot_event_instructions.txt#L30)

[fs_bot/engine/execute.py L3540](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/engine/execute.py#L3540) · [fs_bot/engine/execute.py L6028](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/engine/execute.py#L6028) · [fs_bot/engine/execute.py L6607](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/engine/execute.py#L6607) · [fs_bot/cards/card_effects.py L1119](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/cards/card_effects.py#L1119) · [fs_bot/cards/event_eval.py L1122](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/cards/event_eval.py#L1122)

**Controls and reproduction.** Run probe_events.py --repo <audited checkout>. EV12-01 includes four Aedui-versus-Belgae cases (Pax Romans and Aedui in all three base scenarios), three NP-Arverni-versus-player-Belgae cases, and two empty-target cases. All actions originate in dispatch_bot_turn and resolve through execute_decision. Seven identical-board explicit Belgae target plans remove the correct Resources. One Roman Arverni-over-Belgae priority control succeeds. Two can_play_event=False controls execute normal non-Pass Commands. Every public execution passes pre/post census and structural validation. should_decline_event preserves the complete encoded board and RNG.

**Relationship to prior work.** Round5 report line63 explicitly held exploratory Sappers targeting leads outside its confirmed count. This audit supplies the missing public reproductions, source proof and controls. It extends the missing NP selector class of BE7-02 and EV11-02/03 to numeric24. Earlier human Sappers casualty/choice work concerns authored and shaded effects. No closed finding is reopened.

**Comparison implementation.** Liberty or Death base_bot._is_ineffective_event executes a copied Event and checks semantic effects. Waxhaws ranks eligible targets under its printed priorities while preserving explicit targets. These patterns expose the distinction between a legal generic fallback and a legal Non-player choice. Falling Sky source text supplies the actual target rules.

[lod_ai/bots/base_bot.py L459](https://github.com/FeeSimple1/lod-bot/blob/2991ea279062773548ec390a1da75f3e85381702/lod_ai/bots/base_bot.py#L459) · [lod_ai/bots/base_bot.py L530](https://github.com/FeeSimple1/lod-bot/blob/2991ea279062773548ec390a1da75f3e85381702/lod_ai/bots/base_bot.py#L530) · [lod_ai/cards/effects/late_war.py L110](https://github.com/FeeSimple1/lod-bot/blob/2991ea279062773548ec390a1da75f3e85381702/lod_ai/cards/effects/late_war.py#L110) · [lod_ai/cards/effects/late_war.py L123](https://github.com/FeeSimple1/lod-bot/blob/2991ea279062773548ec390a1da75f3e85381702/lod_ai/cards/effects/late_war.py#L123)

**Repair direction.** Add a numeric24 Non-player target selector and matching pure availability check based on current Citadels, Resources and printed Roman/Aedui instructions. Keep human exact targets available and preserve shaded casualty handling. Treat target selection and admission as one card contract repair.

**Limits.** Scenario-derived legal synthetic positions. Citadels are placed at canonical Cities through _unally_tribe/_ally_tribe(citadel=True), using physical stock. No full gameplay history or natural encounter rate is claimed. Only base numeric24 unshaded targeting is counted. Expansion A24 and shaded Sappers are excluded. The no-target admission cases have zero Citadels, avoiding any ambiguity about faction priorities when Resources are zero.

The evidence archive contains `events/report.md`, its finding ledger, executable probes and results.

### EV12-02 — Non-player Drought places its marker by map order and removes forbidden targets

**Expected behavior.** Romans place Drought to remove player Arverni/Belgae in base or player Germans/Belgae in expansion, with no Roman loss. Aedui select only player Arverni/Belgae in base or player Germans/Belgae in expansion. A legal player-only Carnutes target exists in every witness.

**Observed behavior.** All twelve natural Event executions place Devastated at Morini, removing a Non-player Belgic piece and leaving the eligible player piece at Carnutes. The six Roman cases also remove their own Auxilia at Morini, contrary to the explicit instruction. All twelve exact Carnutes controls remove the player opponent and preserve Morini.

**Cause.** Numeric49 has no NP parameter deriver. execute_card_49 defaults missing devastate_region to marker_regions(state)[0], which is Morini on these maps, ignoring the instruction text already carried by the bot action.

[Reference Documents/Chapter 8 L30](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Chapter%208#L30) · [Reference Documents/Chapter 8 L69](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Chapter%208#L69) · [Reference Documents/Chapter 8 L129](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Chapter%208#L129) · [Reference Documents/Card Reference L487](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Card%20Reference#L487) · [Reference Documents/roman_bot_event_instructions.txt L27](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/roman_bot_event_instructions.txt#L27) · [Reference Documents/aedui_bot_event_instructions.txt L30](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/aedui_bot_event_instructions.txt#L30) · [Reference Documents/Ariovistus/roman_bot_event_instructions_ariovistus.txt L25](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Ariovistus/roman_bot_event_instructions_ariovistus.txt#L25) · [Reference Documents/Ariovistus/aedui_bot_event_instructions_ariovistus.txt L30](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Ariovistus/aedui_bot_event_instructions_ariovistus.txt#L30)

[fs_bot/engine/execute.py L3540](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/engine/execute.py#L3540) · [fs_bot/engine/execute.py L6028](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/engine/execute.py#L6028) · [fs_bot/engine/execute.py L6607](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/engine/execute.py#L6607) · [fs_bot/cards/card_effects.py L1848](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/cards/card_effects.py#L1848) · [fs_bot/cards/drought.py L14](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/cards/drought.py#L14)

**Controls and reproduction.** Run probe_events.py --repo <audited checkout>. EV12-02 covers Romans/Aedui in Pax Gallica, Ariovistus and Gallic War at game seeds1/7. Each board has NP Belgae at Morini and an eligible player enemy at Carnutes. Roman cases add one Auxilia at Morini. Twelve identical-board explicit devastate_region=Carnutes controls remove exactly one legal player piece, preserving Roman and NP Belgic pieces at Morini. All Resources halve correctly in natural and control executions. All pre-existing markers match exactly with only the selected Devastated marker added. All public executions pass census and structural integrity before and after. Natural Event admission leaves the encoded board/RNG unchanged. Outputs match byte for byte at PYTHONHASHSEED=0 and987.

**Relationship to prior work.** The earlier human-choice Drought finding repaired casualty ownership and requests. Those owner choices remain functional in these probes. This concerns the separate NP marker-location producer. Earlier German Drought movement work concerns Command priorities after devastation. EV11-03 is a similar missing printed selector on another card, whose repair remains complete.

**Comparison implementation.** Liberty or Death handlers build eligible targets and rank them before seeded tie selection. Its ineffective-event preview alone would not catch this Drought error because both a wrong and a correct target cause effects. The comparison directs review toward preserving target priorities as well as actual-effect checks.

[lod_ai/bots/base_bot.py L459](https://github.com/FeeSimple1/lod-bot/blob/2991ea279062773548ec390a1da75f3e85381702/lod_ai/bots/base_bot.py#L459) · [lod_ai/bots/base_bot.py L530](https://github.com/FeeSimple1/lod-bot/blob/2991ea279062773548ec390a1da75f3e85381702/lod_ai/bots/base_bot.py#L530) · [lod_ai/cards/effects/late_war.py L110](https://github.com/FeeSimple1/lod-bot/blob/2991ea279062773548ec390a1da75f3e85381702/lod_ai/cards/effects/late_war.py#L110) · [lod_ai/cards/effects/late_war.py L123](https://github.com/FeeSimple1/lod-bot/blob/2991ea279062773548ec390a1da75f3e85381702/lod_ai/cards/effects/late_war.py#L123) · [lod_ai/cards/effects/early_war.py L313](https://github.com/FeeSimple1/lod-bot/blob/2991ea279062773548ec390a1da75f3e85381702/lod_ai/cards/effects/early_war.py#L313)

**Repair direction.** Derive the Drought marker Region using the executor-specific base/expansion opponent and player-seat filters, Roman casualty exclusion, then the existing general NP priority and seeded tie helpers. Preserve owner casualty selection and Resource halving. Add controls for legal remaining targets before addressing any absent-target policy.

**Limits.** Curated scenario-derived legal positions, with no existing Devastated markers. In Pax, one Available Arverni Warband is placed in Carnutes. In expansion, the original German Warband moves from Morini to Carnutes, and the original Arverni Warband there moves to Arverni. Roman cases place one Available Auxilia at Morini. Helpers preserve stock, tribe synchronization and Control. These probes do not prescribe the ambiguous fallback when no instructed player-only Region exists, and do not estimate ordinary-play frequency.

The evidence archive contains `events/report.md`, its finding ledger, executable probes and results.

### BM12-01 — Belgae, Arverni and German Battle gates omit Balearic Slingers opening fire

**Expected behavior.** Decline the threat Battle when four Roman Auxilia with unshaded Slingers would first assign two Losses to a named Leader and his sole Warband. Apply the printed no-Leader-Loss gate and continue to the faction’s March path.

**Observed behavior.** At seeds 1 and 7 all three bots dispatch Battle. Belgae and Arverni add Ambush. Public execution removes the sole Warband and named Leader before their Attack, preserves all four Roman Auxilia, and charges one Resource. The logged casualty requests explicitly offer the Leader Loss.

**Cause.** The three ordinary bot gates call predict_battle without earlier_battles, so its conditional opening-fire stage is skipped. Existing Command-aware prediction identifies the possible Leader Loss. Live Slingers execution is correct.

[Reference Documents/Chapter 8 L237](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Chapter%208#L237) · [Reference Documents/Chapter 8 L576](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Chapter%208#L576) · [Reference Documents/Ariovistus/Chapter A8 L72](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Ariovistus/Chapter%20A8#L72) · [Reference Documents/Card Reference L125](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Card%20Reference#L125) · [Reference Documents/Ariovistus/A Card Reference L126](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Ariovistus/A%20Card%20Reference#L126)

[fs_bot/bots/belgae_bot.py L270](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/bots/belgae_bot.py#L270) · [fs_bot/bots/arverni_bot.py L234](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/bots/arverni_bot.py#L234) · [fs_bot/bots/german_bot.py L227](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/bots/german_bot.py#L227) · [fs_bot/bots/bot_common.py L1192](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/bots/bot_common.py#L1192) · [fs_bot/bots/bot_common.py L1275](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/bots/bot_common.py#L1275) · [fs_bot/engine/execute.py L4081](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/engine/execute.py#L4081) · [fs_bot/bots/aedui_bot.py L606](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/bots/aedui_bot.py#L606)

**Controls and reproduction.** Run probe_battle.py with the Falling Sky checkout path. Six primary public dispatch/execution cases cover Belgae, Arverni and Germans at seeds1,7 after public Card13 acquisition. Every fixture uses canonical physical placement and permanent Provincia Fort. Seventeen cases total. Six capability-absent matched controls preserve Leader/Warband and inflict forecast casualties. Three eight-Warband Command-only controls survive initial fire with Leader/six Warbands and remove all four Auxilia. Two German Stalwart controls cancel initial fire. Empty census/structure throughout. Dispatch/forecasts board-and-RNG pure; hash0/987 byte-identical.

**Relationship to prior work.** NP6-01 corrected pre-Attack defenders/Ambiorix strength; NP7-01 incorporated legal Ambush; NP8-01 corrected the Aedui additional-Battle consumer. BM6-01/02 and BM7-01 corrected live cancellation/alternate Slingers execution. This is newly demonstrated ordinary bot forecast wiring with live Slingers already correct.

**Comparison implementation.** The referenced Liberty or Death paths provide the implementation comparison described in the lane report.

[lod_ai/commands/battle.py L383](https://github.com/FeeSimple1/lod-bot/blob/2991ea279062773548ec390a1da75f3e85381702/lod_ai/commands/battle.py#L383) · [lod_ai/commands/battle.py L788](https://github.com/FeeSimple1/lod-bot/blob/2991ea279062773548ec390a1da75f3e85381702/lod_ai/commands/battle.py#L788)

**Repair direction.** Supply prospective Command context and prior selected Battles to all affected gates, include opening losses and actual remaining force in Leader safety, and preserve once-per-Command Roman choice and Stalwart cancellation. Add public dispatch regressions with controls.

**Limits.** Constructed sparse boards and controlled Event metadata, no natural frequency or saved-session claim. Only Slingers is dynamically established; other Capability omissions remain static leads. German Command-aware diagnostic also includes hypothetical Counterattack after the attackers are gone; the public casualty requests prove the two opening Losses, which alone violate the Leader-safety rule.

The evidence archive contains `battle/report.md`, its finding ledger, executable probes and results.

### LC12-01 — Non-player Interlude evacuation removes every Cisalpina force despite legal Home destinations

**Expected behavior.** Apply the general Non-player move-own priorities and maximum execution guideline to the scenario relocation. Move Roman Legions from Cisalpina to their legal Home Region Provincia. With all six on-map Legions preserved, the otherwise-equipped NP Romans must conduct the Britannia expedition.

**Observed behavior.** In three full third-Winter cases, NPC Rome removes three Cisalpina Legions to the Legions Track despite Provincia being a legal destination. Only three Legions remain on map, so the expedition fails, Belgae receive Britannia forces and the Senate moves to Uproar. Three human default-delegation cases repeat this. Three explicit legal relocation controls and three already-home controls conduct the expedition, put three Legions in the Harvest box and three in Britannia, and move the Senate to Adulation.

**Cause.** _cisalpina_relocation calls the human agent when appropriate but defaults every remaining allocation to destination=None. It bypasses the existing gallia_evacuation.default_response, which prioritizes relocating own pieces and uses removal only when legal destinations are exhausted.

[Reference Documents/Ariovistus/A Scenario - The Gallic War L70](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Ariovistus/A%20Scenario%20-%20The%20Gallic%20War#L70) · [Reference Documents/Ariovistus/A Scenario - The Gallic War L74](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Ariovistus/A%20Scenario%20-%20The%20Gallic%20War#L74) · [Reference Documents/Chapter 8 L174](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Chapter%208#L174) · [Reference Documents/Chapter 8 L179](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Chapter%208#L179) · [Reference Documents/Ariovistus/Chapter A8 L5](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Ariovistus/Chapter%20A8#L5)

[fs_bot/engine/interlude.py L900](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/engine/interlude.py#L900) · [fs_bot/engine/interlude.py L929](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/engine/interlude.py#L929) · [fs_bot/cards/gallia_evacuation.py L177](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/cards/gallia_evacuation.py#L177) · [fs_bot/engine/interlude_choices.py L232](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/engine/interlude_choices.py#L232)

**Controls and reproduction.** python probe_lifecycle.py --repo /absolute/path/to/fs-bot. 12 cases across seeds 1,7,19. All use actual Gallic War setup, a supplied third-Winter cursor, and public run_winter_round. Move three of the setup six Roman Legions Provincia to Cisalpina with move_piece. No other physical edits. All enter below every victory threshold and finish with clean census/structure. Human Roman callback supplies the existing shared default_response only for Cisalpina relocation and delegates other choices. The returned plan validates and preserves all Legions. Human Roman use_default repeats the loss. All-NP setup with the six Legions still in Provincia conducts the expedition. All 12 outcomes match byte for byte at PYTHONHASHSEED 0 and 987.

**Relationship to prior work.** WS-F01/WS-C30 fixed human Cisalpina allocation choices and deliberately retained the remove-all bot fallback, documented at docs/current-status.md lines1103–1128. EXP-07 fixed A5 evacuation, whose bot default now supplies a working control. LC11-01 addressed Region priority for Arverni force reductions. This finding covers the remaining NP/delegated Interlude consumer.

**Comparison implementation.** The referenced Liberty or Death paths provide the implementation comparison described in the lane report.

[lod_ai/util/year_end.py L846](https://github.com/FeeSimple1/lod-bot/blob/2991ea279062773548ec390a1da75f3e85381702/lod_ai/util/year_end.py#L846) · [lod_ai/bots/indians.py L1668](https://github.com/FeeSimple1/lod-bot/blob/2991ea279062773548ec390a1da75f3e85381702/lod_ai/bots/indians.py#L1668)

**Repair direction.** Use the shared priority-aware allocation planner for Non-player and delegated Interlude Cisalpina moves, validating the complete plan before applying it. Retain human removal options, forced removal when no Home slot exists, faction order, Roman Legion Track destination on actual removal, Gallia Togata bypass and the expedition check on surviving forces.

**Limits.** The scenario permits human removal. The NP conclusion combines the scenario relocation with §8.4 maximum execution and move-own priorities. The §8.4.1 parenthetical prohibition on voluntary removal references §1.4.1 reclamation and is not used as a standalone prohibition on all scenario removals. Public dynamic proof covers Roman Legions and the expedition consequence. No natural encounter frequency, broad bot-balance, terminal, or saved-session failure is claimed. The phase cursor is controlled.

The evidence archive contains `lifecycle/report.md`, its finding ledger, executable probes and results.

### LC12-02 — Non-player Interlude Ally reductions remove a City Ally before a non-City Ally

**Expected behavior.** After choosing a Region under the Interlude ordering, apply §8.4.1 reverse own-removal priority. When removing two of three own Allies at Mandubii, Lingones and Senones, retain the Mandubii City Ally and remove the two ordinary Allied Tribes.

**Observed behavior.** Across three seeds each for NP Belgae and NP Romans, whole third-Winter execution removes Lingones then Mandubii and retains Senones. The six identical-board human allocation controls retain Mandubii. Two Carnutes/Aulerci controls happen to retain the City because the ordinary Tribe sorts first.

**Cause.** The general and Roman NP reduction loops remove an anonymous ALLY then call clear_allied_tribe without a Tribe selection. That bookkeeping helper iterates alphabetical Tribe names and only protects a City when a Citadel remains. It does not implement own-loss priorities, so the second mandatory removal clears Mandubii before Senones.

[Reference Documents/Chapter 8 L179](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Chapter%208#L179) · [Reference Documents/Ariovistus/A Scenario - The Gallic War L24](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Ariovistus/A%20Scenario%20-%20The%20Gallic%20War#L24) · [Reference Documents/Ariovistus/A Scenario - The Gallic War L40](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Ariovistus/A%20Scenario%20-%20The%20Gallic%20War#L40) · [Reference Documents/Ariovistus/A Scenario - The Gallic War L65](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Ariovistus/A%20Scenario%20-%20The%20Gallic%20War#L65) · [Reference Documents/Ariovistus/Chapter A8 L5](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Ariovistus/Chapter%20A8#L5)

[fs_bot/engine/interlude.py L281](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/engine/interlude.py#L281) · [fs_bot/engine/interlude.py L820](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/engine/interlude.py#L820) · [fs_bot/board/pieces.py L937](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/board/pieces.py#L937) · [fs_bot/board/pieces.py L964](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/board/pieces.py#L964)

**Controls and reproduction.** python probe_ally_priority.py --repo /absolute/path/to/fs-bot. 14 public run_winter_round cases. Actual Gallic War setups use canonical _unally_tribe/_ally_tribe to put the acting faction’s three Allied discs at Mandubii, Lingones, Senones. One supplementary German Allied disc at Atrebates keeps Rome below its early victory threshold in the primary cases. Third-Winter metadata is supplied. Full census and structural integrity pass before and after; no fixture has a threshold winner. Six human exact-allocation controls on the same physical boards remove Lingones and Senones and retain Mandubii. Two NPC Carnutes/Aulerci controls retain Carnutes, where alphabetical order happens to match the rule. All 14 cases are byte-identical under PYTHONHASHSEED 0 and 987.

**Relationship to prior work.** LC11-01 changed which Regions were protected during Arverni reductions. This finding concerns which physical Allied Tribe is removed within an already-selected Region in the Belgic and Roman reducers. Existing human force-reduction APIs accept the correct allocation. No prior finding in the reviewed comparison ledgers accounts for this City-versus-ordinary Ally priority.

**Comparison implementation.** The referenced Liberty or Death paths provide the implementation comparison described in the lane report.

[lod_ai/util/year_end.py L1030](https://github.com/FeeSimple1/lod-bot/blob/2991ea279062773548ec390a1da75f3e85381702/lod_ai/util/year_end.py#L1030) · [lod_ai/util/year_end.py L1101](https://github.com/FeeSimple1/lod-bot/blob/2991ea279062773548ec390a1da75f3e85381702/lod_ai/util/year_end.py#L1101)

**Repair direction.** Choose exact Allied Tribe discs under NP reverse own-removal priority within each selected Region, then remove/synchronize that selected Tribe explicitly. Preserve regional order and exact quotas, seed equal-priority choices, the separate Arverni early-Cadurci/Volcae exception and human allocations. Avoid making the generic bookkeeping helper impose a global tactical choice.

**Limits.** Two Non-player reducers are dynamically proven. Shared Arverni/German/Aedui consumers and Remi preference are inspected leads only. Visibility removal order is excluded because the later full Spring erases that distinction in these fixtures. No claim about natural frequency, battle casualty ordering, or aggregate Ally quantity failure.

The evidence archive contains `lifecycle/report.md`, its finding ledger, executable probes and results.

### NP12-01 — Aedui spreading March collapses three one-Warband groups into one large move

**Expected behavior.** Section 8.6.5 first sends one Hidden Aedui from one origin into each of up to three eligible adjacent Regions, while keeping one Warband and existing Aedui Control at the origin. On the witness board four Hidden Aedui at Mandubii can send one each to the three destinations already chosen by their own planner, retaining one. No Warbands remain movable for an additional Control step.

**Observed behavior.** Public dispatch selects March and spread_destinations Atrebates, Treveri and Carnutes. Public execution sends all three movable Warbands only to Atrebates. Treveri and Carnutes remain empty. All four natural command-only cases (two scenarios, two seeds) do this. Four matched explicit three-group player controls place one in each destination for the same two-Resource origin charge and retain Mandubii Control.

**Cause.** node_a_march records destinations without concrete one-Warband groups. The shared plan_expand_march_moves combines Control and spread destinations, visits each origin once, chooses one nearest destination and sends every Warband beyond the leave-behind. Its nonempty-effect check only asks whether any group can move, so the malformed allocation passes.

[Reference Documents/Chapter 8 L516](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Chapter%208#L516) · [Reference Documents/Chapter 3 L245](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Chapter%203#L245)

[fs_bot/bots/aedui_bot.py L920](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/bots/aedui_bot.py#L920) · [fs_bot/bots/aedui_bot.py L999](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/bots/aedui_bot.py#L999) · [fs_bot/engine/execute.py L6702](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/engine/execute.py#L6702) · [fs_bot/engine/execute.py L6759](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/engine/execute.py#L6759)

**Controls and reproduction.** PYTHONHASHSEED=0 python probe_bots.py --repo /absolute/fs-bot. Cases spread_collapsed and explicit_three_groups_control, Pax Gallica? and The Great Revolt, seeds 6 and 19. Four explicit three-group controls use normal execute_decision player_action, charge exactly two Resources once at Devastated Mandubii, preserve one origin Warband and Control, and add Hidden Aedui plus Control at all three destinations. Every probe has clean pre/post census and structural checks. Dispatch preserves board and RNG on these fixtures. All 24 output records are identical across hash seeds 0 and 987.

**Relationship to prior work.** Prior comparative ledgers through round11 inspected. NP11-02 concerns a German expansion advance and was repaired using explicit groups. Existing Aedui unit tests inspect node plans, including spread_destinations, without asserting the three resulting arrivals. NP8-02 addressed Aedui Rally ability timing. FE6-02 concerned human Enlist split German March. This newly proved ordinary Aedui allocation path is distinct.

**Comparison implementation.** The referenced Liberty or Death paths provide the implementation comparison described in the lane report.

[lod_ai/bots/patriot.py L658](https://github.com/FeeSimple1/lod-bot/blob/2991ea279062773548ec390a1da75f3e85381702/lod_ai/bots/patriot.py#L658) · [lod_ai/bots/patriot.py L709](https://github.com/FeeSimple1/lod-bot/blob/2991ea279062773548ec390a1da75f3e85381702/lod_ai/bots/patriot.py#L709)

**Repair direction.** Build executable Aedui groups in printed phase order on a projected board. Reserve one eligible Hidden-arrival Warband per spread destination, retain source Control and leave-behinds, then compute the additional minimum Control move from remaining unmoved pieces. Preserve origin billing and separate expansion Leader rules. Add result-level regressions rather than asserting only planner destination lists.

**Limits.** Sparse canonical mid-year boards initialized through build_initial_state, not untouched setup_scenario boards or a reconstructed full game history. The single Devastated marker represents a prior Arverni action. The probe does not invoke Winter victory or estimate natural frequency/balance. No Event, terminal, saved-session, expansion Leader or human Supply-disagreement claims. No independent allegation about additional Control movement, Scouted spreading, Diviciacus ordering or other faction expander consumers is counted.

The evidence archive contains `bots/report.md`, its finding ledger, executable probes and results.

### NP12-02 — Aedui March drops the post-Command Trade opportunity when its initial Suborn choice is empty

**Expected behavior.** Section 8.6.5 requires Trade or Suborn after March, following the current-state test in 8.6.3. Here March reduces Aedui Resources from 10 to 8, enabling the below-ten Trade condition. Non-player Roman agreement and the resulting Aedui Control yield twelve Resources under 4.4.1, producing 20 Resources after the demonstrated move.

**Observed behavior.** With only Revealed Aedui present, public dispatch emits March with No SA and translates it as command-only. March executes and pays two Resources, then stops at eight Resources. The current ordinary Trade chooser returns Trade worth twelve. Changing only the preselected SA label to Suborn opens existing live rederivation, which itself chooses Trade and produces twenty Resources. Starting with Hidden Aedui also naturally reaches this correct live rederivation.

**Cause.** node_a_march calls only _determine_suborn_sa on the pre-March board. It carries no deferred Aedui post-Command intent when the returned label is No SA. The translator therefore chooses command-only. _execute_sa_confirmed returns on No SA, before the existing Aedui current-state Trade/Suborn branch can run.

[Reference Documents/Chapter 8 L478](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Chapter%208#L478) · [Reference Documents/Chapter 8 L533](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Chapter%208#L533) · [Reference Documents/Chapter 4 L158](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/Reference%20Documents/Chapter%204#L158)

[fs_bot/bots/aedui_bot.py L1023](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/bots/aedui_bot.py#L1023) · [fs_bot/cli/dispatcher.py L89](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/cli/dispatcher.py#L89) · [fs_bot/engine/execute.py L166](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/engine/execute.py#L166) · [fs_bot/engine/execute.py L4825](https://github.com/FeeSimple1/fs-bot/blob/1563e41d84f61dfce43ce4008106eca2a1639aed/fs_bot/engine/execute.py#L4825)

**Controls and reproduction.** PYTHONHASHSEED=0 python probe_bots.py --repo /absolute/fs-bot. Cases new_trade_omitted, live_trade_dispatch_control, existing_hidden_sa_control and command_only_control across Pax Gallica? and The Great Revolt at seeds 6 and 19. Four source-required SA-label controls retain exact March moves and allow existing live rederivation to choose actual Trade, yielding twelve Resources. Four natural Hidden-force positive controls reach the same Trade without label changes. Four command-only controls correctly execute only the March at two Resources. Ordinary Trade forecasting and dispatch are board/RNG pure in these fixtures. All before/after census and structural checks pass.

**Relationship to prior work.** Newly demonstrated ordinary Aedui March consumer of the post-Command opportunity defect class. NP8-02 repaired Aedui Rally, NP9-02 Arverni Rally/Belgic Raid, NP10-01 Arverni March and NP11-01 Belgic March. Those repair paths remain covered. This finding does not reopen their repaired consumers.

**Comparison implementation.** The referenced Liberty or Death paths provide the implementation comparison described in the lane report.

[lod_ai/bots/patriot.py L238](https://github.com/FeeSimple1/lod-bot/blob/2991ea279062773548ec390a1da75f3e85381702/lod_ai/bots/patriot.py#L238) · [lod_ai/bots/patriot.py L280](https://github.com/FeeSimple1/lod-bot/blob/2991ea279062773548ec390a1da75f3e85381702/lod_ai/bots/patriot.py#L280)

**Repair direction.** Carry an authorized deferred Aedui post-March ability decision or reliably forecast the completed board. Reuse the existing current-state Trade-to-Suborn choice and actual Supply declarations even if no pre-Command Suborn exists. Preserve true command-only restrictions and apply Britannia exclusion to actual executed crossings.

**Limits.** Sparse canonical mid-year boards initialized through build_initial_state, not untouched setup_scenario boards or a reconstructed full game history. The single Devastated marker represents a prior Arverni action. The probe does not invoke Winter victory or estimate natural frequency/balance. No Event, terminal, saved-session, expansion Leader or human Supply-disagreement claims. This proof uses the existing movement result to isolate the missing SA. NP12-01 may change that board and Trade yield when repaired, so a repair regression should compute the correct post-March yield. The public natural failure alone establishes the bug. The label control is an explicit diagnostic, not a claimed unmodified dispatch.

The evidence archive contains `bots/report.md`, its finding ledger, executable probes and results.
