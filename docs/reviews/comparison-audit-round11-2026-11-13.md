# Eleventh Falling Sky / Liberty or Death comparison audit

**13 November 2026. Eight additional medium-priority findings are open.** The tenth audit is complete with all nine of its findings repaired.

The audited revision is `702d60a3754ce94a73ead0d0148d647232ecd816`, with Python source SHA-256 `489efe1d5b60a36f47ac5b7b46fd47595246d770606e32f6fa78d5b5b8d6a9e0` across 626 files, tested on Python 3.12.14. The Liberty or Death comparison uses `2991ea279062773548ec390a1da75f3e85381702`. Both checkouts matched their fetched main branches when review began.

[Finding ledger](comparison-audit-round11-2026-11-13.json) · [Verification evidence](comparison-audit-round11-2026-11-13-evidence.zip) · [Current status](../current-status.md)

## Method and coverage

Reviewed combat, bot flowcharts, Events, lifecycle and human interfaces in five parallel lanes, with an independent validation lane and lead review. The comparison examined actual Liberty or Death code for shared battle calculations, action simulation, actual-effect accounting, immediate Event grants and transaction rollback. The archive records the inspected files and lines. Falling Sky rules conclusions use the 47 supplied references and thirteen adopted provisional rulings.

Each finding has a reproducible execution path, supplied-source justification, controls and an explicit comparison with prior findings. Canonical piece helpers keep the fixtures within physical stocks. Census and structural checks surround execution. The lead independently reran all five finalized probes at hash seeds 0 and 987 and matched the preserved JSON byte for byte. Controlled phase cursors, card identities and sparse boards are disclosed in the evidence. These probes establish the described failures without estimating how often they occur in ordinary play.

BM11-01 and NP11-01 extend previously observed defect classes to separate unrepaired consumers. The active-Abatis casualty choice remains correct in live combat, and the repaired Arverni post-March path remains covered. The new findings concern Divination’s guarantee check and the Belgic March consumer respectively. NP11-02 proves an unreachable German movement branch.

## Confirmed findings

| ID | Priority | Finding |
|---|---|---|
| EV11-01 | Medium | Non-player Lucterius never restores an eligible Arverni Leader and is selected with named Vercingetorix already present |
| EV11-02 | Medium | Unshaded Assembly of Gaul NP plans omit every Resource target |
| EV11-03 | Medium | Shifting Loyalties removes the first acquired Capability instead of the Roman bot’s instructed target |
| BM11-01 | Medium | Divination treats an Abatis-protected Ally as a guaranteed high-value Loss |
| LC11-01 | Medium | Interlude non-player reductions give three extra Arverni Regions unprinted protection |
| UI11-01 | Medium | Winter Campaign terminal cannot combine borrowed Enlist Warbands with their Belgic Command |
| NP11-01 | Medium | Belgic March omits Enlist newly enabled by the Leader's arrival |
| NP11-02 | Medium | Surrounded German Leader never takes the required expansion advance |

## Validation

| Check | Result |
|---|---|
| Full suite | 10,379 passed with five external anyio/pytest deprecation warnings. |
| Audited bot games | All 20 completed across five scenarios on second-edition seeds 57–60. Zero errors, inventory/structure findings or ranking issues. All 329 diagnostic occurrences were legal declines. Two games reached the Interlude. |
| Mixed-player replay | All 20 cases completed at both hash seeds, including internal replay (80 executions). JSON and stdout matched. Zero hard findings, 758 human turns and 171 Event turns per sample. Four soft partial plans were retained. |
| Audited revision on GitHub | All 14 checks succeeded, including the full balance guardrail and package installation across supported platforms. |
| Source integrity | All 47 references and canonical constants matched their recorded hashes. |

The initial local test launcher rejected a relative pytest cache path before collection. The preserved retry used an absolute path and completed the full suite. The four mixed-player partial plans were Pax Gallica seeds 58 and 60, Reconquest seed 59 and Ariovistus seed 58. Their games completed and their records identify the partial results. The local suite includes the existing 15-game canary. The 100-game balance guardrail success is attributed to the audited revision’s GitHub run. The audit retains the existing balance baseline. [CI](https://github.com/FeeSimple1/fs-bot/actions/runs/43504093315) · [Package installation](https://github.com/FeeSimple1/fs-bot/actions/runs/43504093342)

## Suggested repair sequence

| Batch | Findings | Scope |
|---|---|---|
| 1 | EV11-01, EV11-02, EV11-03 | Lucterius, Assembly of Gaul and Shifting Loyalties bot choices |
| 2 | BM11-01 | Divination forecast with active Abatis |
| 3 | LC11-01 | Arverni removal priorities at the Gallic War Interlude |
| 4 | UI11-01 | Winter Campaign terminal choice for Command plus borrowed Enlist |
| 5 | NP11-01, NP11-02 | Belgic Enlist after March and German Leader movement |

Convert the directed failures into source-derived regressions with their controls. Run the full suite and relevant bot, human-session and replay checks after each repair. Explain changed game outcomes before considering any balance baseline refresh.

## Finding details

### EV11-01 — Non-player Lucterius never restores an eligible Arverni Leader and is selected with named Vercingetorix already present

Open, medium priority.

When the Successor is Available or on-map, NP Arverni executing shaded numeric19 must select a legal destination and place the Leader symbol-up as Vercingetorix. If named Vercingetorix is already on-map, the Event has no effect and must be declined before the Auto1–4 decision.

On Reconquest and Great Revolt scenario-based boards, natural Arverni dispatch chooses shaded Lucterius in all three Leader states: named Vercingetorix, Available Successor, and on-map Successor. Public execution reports success with no tracked game effects in all six cases. Available Leaders remain off-map and live Successors remain Successors. Four explicit target controls restore Vercingetorix; two explicit named-Leader controls correctly do nothing. Six Event-disabled controls execute non-Pass Commands.

No numeric19 entry in the NP parameter derivation table supplies target_region. execute_card_19 returns on a missing target even when successor_regions has legal destinations. Separately, the generic PLACES_LEADER flag returns true without checking the Successor prerequisite, and numeric19 has no corresponding NP applicability override. These are grouped as one incomplete shaded-Lucterius NP contract; a producer-only repair would still waste the Event with named Vercingetorix.

[Reference Documents/Card Reference, line 181](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Card%20Reference#L181) · [Reference Documents/Chapter 5, line 5](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Chapter%205#L5) · [Reference Documents/Chapter 5, line 52](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Chapter%205#L52) · [Reference Documents/Chapter 8, line 30](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Chapter%208#L30) · [Reference Documents/Chapter 8, line 120](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Chapter%208#L120) · [Reference Documents/Chapter 8, line 678](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Chapter%208#L678) · [Reference Documents/arverni_bot_event_instructions.txt, line 18](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/arverni_bot_event_instructions.txt#L18)

[fs_bot/engine/execute.py, line 3534](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/engine/execute.py#L3534) · [fs_bot/engine/execute.py, line 5984](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/engine/execute.py#L5984) · [fs_bot/engine/execute.py, line 6585](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/engine/execute.py#L6585) · [fs_bot/cards/card_effects.py, line 905](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/cards/card_effects.py#L905) · [fs_bot/cards/event_targets.py, line 122](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/cards/event_targets.py#L122) · [fs_bot/cards/event_eval.py, line 253](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/cards/event_eval.py#L253) · [fs_bot/cards/event_eval.py, line 1176](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/cards/event_eval.py#L1176) · [fs_bot/bots/bot_common.py, line 373](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/bots/bot_common.py#L373)

Both production Reconquest and Great Revolt setups; only canonical remove_piece/place_piece change Leader form. Four explicit target_region controls restore the Available or on-map Successor to Vercingetorix at the original Region. Two named-Leader controls preserve named Vercingetorix unchanged. Six matched can_play_event=False controls execute their normal non-Pass Command with clean integrity. should_decline_event is asserted board/RNG pure. All public executions pass pre/post census and structural checks.

BE2-04 fixed human/direct shaded-Lucterius Successor prerequisites and same-Region symbol-up restoration; those explicit paths now pass. Original BE-06/07/08 Lucterius work concerned unshaded quantities/physical choices/menu shape. BE6-03 fixed numeric56 Flight of Ambiorix effectiveness, not numeric19. BE7-02 and EV10-02 were absent NP producers for other cards. No earlier repair is reopened.

Add a shaded numeric19 NP destination producer under applicable NP selection priorities and use the actual Successor prerequisite for admission. Preserve human target choice, legal same-Region restoration, and the named-Leader guard. Auto1–4 must remain after the ineffectiveness gate.

Controlled scenario-derived positions, not a frequency estimate. Explicit human destinations prove a legal benefit exists, not the unique NP-priority destination. Pax Gallica Spring-box timing, expansion replacement A19 and arbitrary author-invalid plans are excluded. No deferred free action exists here: the missing mandatory placement is not a legal no-plan decline.

Evidence files are `events/probe_events.py`, `events/results.json`.

### EV11-02 — Unshaded Assembly of Gaul NP plans omit every Resource target

Open, medium priority.

With Carnutes Subdued and eligible opponents holding Resources, NP Romans/Aedui executing numeric52 must select eligible Factions and apply the printed eight-Resource drain, using the scenario-specific target instructions. Romans target Arverni then Belgae in base, Belgae in Ariovistus; Aedui target eligible player foes. German targets remain excluded by the printed Gallic scope.

Six natural NP Events across Pax Gallica, Great Revolt, Ariovistus and Gallic War report executed=true and leave all game-effect fields unchanged despite positive Resources on legal targets. Six identical-board explicit-target controls drain the intended Arverni/Belgae (base) or Belgae (expansion), while preserving other Resources. Six blocked-condition controls with Carnutes Arverni Allied correctly produce no effect.

The NPC action includes the printed instruction string but no concrete target_factions. _derive_event_params has no numeric52 producer. execute_card_52 defaults missing targets to an empty list, so its otherwise functional drain loop visits no selected Faction. Generic REMOVES_RESOURCES effectiveness accepts the Event.

[Reference Documents/Card Reference, line 518](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Card%20Reference#L518) · [Reference Documents/Chapter 5, line 5](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Chapter%205#L5) · [Reference Documents/Chapter 5, line 52](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Chapter%205#L52) · [Reference Documents/Chapter 8, line 69](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Chapter%208#L69) · [Reference Documents/Chapter 8, line 136](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Chapter%208#L136) · [Reference Documents/roman_bot_event_instructions.txt, line 17](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/roman_bot_event_instructions.txt#L17) · [Reference Documents/aedui_bot_event_instructions.txt, line 30](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/aedui_bot_event_instructions.txt#L30) · [Reference Documents/Ariovistus/roman_bot_event_instructions_ariovistus.txt, line 18](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Ariovistus/roman_bot_event_instructions_ariovistus.txt#L18) · [Reference Documents/Ariovistus/aedui_bot_event_instructions_ariovistus.txt, line 30](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Ariovistus/aedui_bot_event_instructions_ariovistus.txt#L30) · [Reference Documents/Ariovistus/Chapter A5, line 34](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Ariovistus/Chapter%20A5#L34)

[fs_bot/engine/execute.py, line 3534](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/engine/execute.py#L3534) · [fs_bot/engine/execute.py, line 5984](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/engine/execute.py#L5984) · [fs_bot/engine/execute.py, line 6585](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/engine/execute.py#L6585) · [fs_bot/cards/card_effects.py, line 1903](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/cards/card_effects.py#L1903) · [fs_bot/cards/event_eval.py, line 453](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/cards/event_eval.py#L453) · [fs_bot/cards/event_eval.py, line 1122](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/cards/event_eval.py#L1122)

Six explicit target_factions plans on identical physical boards drain exactly eight Resources per target, floored at zero. Six canonical Carnutes-Arverni-Ally negative controls with the same explicit selectors leave effects unchanged, preserving the printed prerequisite. Both player-target rulesets are covered; all other factions are human in these fixtures so Aedui has permitted opponents. All pieces begin from production setup; Carnutes allegiance is changed through _unally_tribe/_ally_tribe. Pre/post integrity checks pass.

BE2-02 fixed duplicate numeric52 target entries draining the same Faction repeatedly. FE4-03/FE5-01/FE5-02/FE6-01 and UI8 findings address shaded Assembly free Command/Special Ability paths. Original generic Event schema work enabled authored arrays. None supplied the unshaded NP Resource-target producer. The present explicit-target controls confirm that the drain itself works.

Derive unshaded numeric52 target_factions from current legal text, Resources and scenario-specific NPC instructions; decline if no legal instructed target can be affected. Preserve human authored target lists, the corrected no-duplicate drain, the Carnutes guard and shaded free-action handling.

The six no-target cases are established; no exhaustive no-Resources, Dispersed, mixed player/NP target policy or free-Command coverage is claimed. Expansion Aedui instructions mention Germans, but A5.1.1 preserves Gallic meaning, so these witnesses use legally eligible Belgae only. The two base Roman setups whose flowchart begins with Battle were not used as Event witnesses.

Evidence files are `events/probe_events.py`, `events/results.json`.

### EV11-03 — Shifting Loyalties removes the first acquired Capability instead of the Roman bot’s instructed target

Open, medium priority.

With unshaded Titus Labienus (12) and shaded Commius (55) active and Belgae a player, Roman NP Shifting Loyalties must remove shaded55, the eligible player-Belgae Capability. It must not remove beneficial unshaded12 merely because it entered the active table first.

After public acquisition of unshaded12 then shaded55, natural Roman NP Event50 removes12 and leaves55 in Pax Gallica, Ariovistus and Gallic War. Reversing the acquisition order yields the correct removal55, proving insertion-order dependence. All six explicit target_capability=55 controls remove55 and retain12. Integrity passes throughout.

The NP derivation hook has no numeric50 selector. execute_card_50 falls back to next(iter(get_active_capabilities(state))), disregarding the instruction carried by the bot plan. The action is materially effective but chooses the wrong side/beneficiary, so a no-op admission check cannot repair it.

[Reference Documents/Card Reference, line 500](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Card%20Reference#L500) · [Reference Documents/Card Reference, line 114](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Card%20Reference#L114) · [Reference Documents/Card Reference, line 553](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Card%20Reference#L553) · [Reference Documents/Chapter 8, line 69](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Chapter%208#L69) · [Reference Documents/roman_bot_event_instructions.txt, line 42](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/roman_bot_event_instructions.txt#L42) · [Reference Documents/Ariovistus/roman_bot_event_instructions_ariovistus.txt, line 49](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Ariovistus/roman_bot_event_instructions_ariovistus.txt#L49)

[fs_bot/engine/execute.py, line 3534](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/engine/execute.py#L3534) · [fs_bot/engine/execute.py, line 5984](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/engine/execute.py#L5984) · [fs_bot/engine/execute.py, line 6585](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/engine/execute.py#L6585) · [fs_bot/cards/card_effects.py, line 1852](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/cards/card_effects.py#L1852)

Both Capabilities are acquired through public player Event execution; no raw capability injection. All three scenario cases are repeated with reversed acquisition order: only dictionary ordering changes the removal result. Six explicit55 controls correctly preserve beneficial12; player Belgae is constant. Public natural Roman dispatch selects Event50 and includes the relevant printed instruction. All pre/post integrity checks pass.

The 24 October capability-selection repair fixed CLI/schema selection of actual active Capabilities (including legacy A38) and display; it did not supply NP printed-priority selection. EV10-02 addressed A51 troop beneficiaries, not Capability removal. No earlier counted numeric50 NP-priority group was found in rounds1–10.

Derive target_capability using the acting faction’s scenario-specific instruction and applicable NP tie rules. Retain human selectors and legal removal machinery. Audit other factions’ individual printed instructions as a scoped follow-up, without assuming the Roman witness proves each.

Confirmed for Roman primary priority with a single eligible player-Belgae target. Other faction selectors, absent-priority fallback, ties, owner-scoped capabilities, Interlude survivors and live Trade/Suborn capability-removal timing are not claimed. The latter existing source/timing issue remains separate.

Evidence files are `events/probe_events.py`, `events/results.json`.

### BM11-01 — Divination treats an Abatis-protected Ally as a guaranteed high-value Loss

Open, medium priority.

A34 unshaded with a non-player Aedui beneficiary should March when Germans can inflict only three Losses on two Belgic Warbands plus Aulerci and active Abatis: the Belgae may stand and assign the third Loss to Abatis, so no high-value target is guaranteed to take a Loss.

Public A34 selects and executes Battle. The legal human defender removes two Warbands and assigns the last Loss to Abatis; Aulerci remains Belgic. Reproduces with Ariovistus plus ten German Warbands and without Ariovistus using twelve Warbands. Raw and live formulas agree on three Losses in both cases.

divination_np._high_value_forced calls _build_loss_priority without the abatis_defender flag and slices the first N entries as forced casualties. The marker is omitted, making the Ally appear forced even though live resolution correctly offers Abatis as an alternative. A34 retains a separate approximate guarantee gate from the ordinary repaired Aedui predicate.

[Reference Documents/Ariovistus/A Card Reference, line 146](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Ariovistus/A%20Card%20Reference#L146) · [Reference Documents/Ariovistus/A Card Reference, line 288](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Ariovistus/A%20Card%20Reference#L288) · [Reference Documents/Ariovistus/Chapter A3, line 118](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Ariovistus/Chapter%20A3#L118) · [Reference Documents/Chapter 3, line 311](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Chapter%203#L311) · [Reference Documents/Chapter 8, line 105](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Chapter%208#L105) · [Reference Documents/Chapter 8, line 448](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Chapter%208#L448)

[fs_bot/cards/divination_np.py, line 69](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/cards/divination_np.py#L69) · [fs_bot/cards/divination_np.py, line 105](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/cards/divination_np.py#L105) · [fs_bot/cards/divination_np.py, line 139](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/cards/divination_np.py#L139) · [fs_bot/battle/losses.py, line 615](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/battle/losses.py#L615) · [fs_bot/battle/losses.py, line 474](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/battle/losses.py#L474) · [fs_bot/battle/losses.py, line 794](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/battle/losses.py#L794) · [fs_bot/bots/aedui_bot.py, line 232](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/bots/aedui_bot.py#L232)

Defect repeats without Ariovistus: twelve German Warbands against the same active Abatis cause three Losses and wrongly Battle, proving independence from BM10's doubling bug. Equal-three-Loss no-Abatis control: Ariovistus and one German Warband correctly trigger Battle and remove Aulerci. Active Abatis with only two Losses correctly selects March. Active Abatis without any high-value enemy target correctly selects March. Round10 canceled-Abatis control: A64 then shaded A31 with Ariovistus and two Warbands correctly gives four Losses and Battles, removing Aulerci. The resolver-backed ordinary Aedui target predicate correctly rejects both new defect fixtures with the same German force. All public responses validate and all before/after census and structure checks are clean; no mocks or direct physical count changes.

Newly demonstrated unrepaired A34 consumer of the known target-guarantee defect class. NP6-02 (round6 report256–276) fixed ordinary Aedui/Arverni target guarantees, not A34's separate list-slicing gate. BM10-01 (round10 report107–127) repaired canceled-Abatis loss arithmetic, which agrees with live results in every new case and remains correct in a retained positive control. BM5-02's live Abatis casualty choices work correctly here.

Bring A34's Aedui high-value gate onto the resolver-backed guaranteed-target calculation, preserving physical German force, active/canceled Abatis, legal alternative casualty choices and Retreat. Add public A34 active-marker and canceled-marker controls. Do not alter correct live Battle arithmetic or casualty options.

Controlled legal Ariovistus states, not measured natural-game frequency. Primary witness preserves Aulerci regardless of the Abatis saving roll. One additional consumer group, not a new defect class. Other inspected Morasses/Frost direct consumers remain uncounted without a finalized public failure. No new ruling or general Elite/capability claim.

Evidence files are `battle/probe_battle.py`, `battle/results.json`, `battle/report.md`.

### LC11-01 — Interlude non-player reductions give three extra Arverni Regions unprinted protection

Open, medium priority.

The Gallic War Interlude specifically removes Arverni pieces from the Arverni Region last, with a separate early exception for Cadurci/Volcae Allies. Non-player removal order is random among otherwise equal Regions. Veneti, Carnutes and Pictones must compete with other non-Arverni Regions rather than receive an additional protected tier.

Public run_winter_round reaches and completes the Interlude from legal Gallic War setup-derived positions. Equal four-Warband groups at Veneti/Sequani, Carnutes/Sequani and Pictones/Sequani always lose all four in Sequani and preserve the expansion Home, for seeds1–12 each. Code makes the probability of removing the expansion Home first zero. Ordinary Mandubii/Sequani controls remove either (7/5), while a human German's explicit removal of each of the three expansion Homes is accepted by the same full Interlude.

_np_arverni_reductions builds other from Regions outside ARVERNI_HOME_REGIONS_ARIOVISTUS, then a separate shuffled home list of Veneti/Carnutes/Pictones, then Arverni. It applies other+home+[Arverni] to the Warband quota, retaining an extra expansion-Home tier despite the narrower Interlude rule and human authored cohort legality.

[Reference Documents/Ariovistus/A Scenario - The Gallic War, line 24](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Ariovistus/A%20Scenario%20-%20The%20Gallic%20War#L24) · [Reference Documents/Ariovistus/A Scenario - The Gallic War, line 53](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Ariovistus/A%20Scenario%20-%20The%20Gallic%20War#L53) · [Reference Documents/Chapter 8, line 163](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Chapter%208#L163) · [Reference Documents/Chapter 8, line 179](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Chapter%208#L179)

[fs_bot/engine/interlude.py, line 669](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/engine/interlude.py#L669) · [fs_bot/engine/interlude.py, line 758](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/engine/interlude.py#L758) · [fs_bot/engine/interlude.py, line 1418](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/engine/interlude.py#L1418) · [fs_bot/engine/interlude_reductions.py, line 18](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/engine/interlude_reductions.py#L18) · [fs_bot/engine/interlude_reductions.py, line 79](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/engine/interlude_reductions.py#L79) · [fs_bot/engine/winter.py, line 1261](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/engine/winter.py#L1261)

36 primary cases: each of Veneti/Carnutes/Pictones versus Sequani, four Hidden Warbands each, seeds1–12; all preserve the expansion Home and empty Sequani. 12 ordinary-Region controls: Mandubii versus Sequani, equal groups; removal selects Mandubii7 and Sequani5. 3 printed-priority controls: Arverni Region versus Sequani, seeds1–3; only Sequani is emptied. 3 human-German controls explicitly remove the Veneti/Carnutes/Pictones cohort; full Interlude accepts each and preserves Sequani. All54 fixtures have no threshold winner and pass census/structural checks before and after public run_winter_round. Hash0/987 JSON output is byte-identical.

WS5-01 restored only the named home City rather than clearing its Region; earlier Interlude choices gave humans exact allocations. WS7-01 wired NP Quarters planners, LC9-01 corrected Roman Quarters arrival payments and LC10-01 admitted adjacent agreed Provincia moves. None addresses the NP Interlude Arverni removal-tier definition. The human Interlude validator already uses only the base Arverni Home Region while the NP fallback preserves the extra expansion tier.

Use the specific Interlude Arverni-last tier for NP reductions, sharing priority definitions with authored human cohort legality where practical. Preserve Cadurci/Volcae Ally exception, exact minimum quotas, appropriate piece priorities, seeded random equal-Region choices and mandatory Gergovia restoration/reinforcement. Keep normal Ariovistus Arverni Home definitions unchanged.

Actual setup_scenario(The Gallic War, seed); canonical remove_piece returns all original Arverni Warbands to Available, then place_piece places equal groups of four in two legal Regions. All other setup pieces remain. Supply third-Winter metadata winter_count2/current Winter, mark human Rome to legally decline Britannia expedition and other playable seats NP. Human controls additionally make Germans human and supply an engine-authored legal Arverni reduction allocation. No private reducer invocation, mocks, monkeypatches or production edits.

One constructed full-Winter integration defect group, not natural full-game frequency evidence. Multiple seeds support the code-level zero-selection proof; no particular random result is asserted mandatory for any individual seed. Dynamic proof isolates Hidden Warband removals; the same Region order feeds Allies but no separate Ally-priority finding is counted. Results summarize affected cohorts and validators, not complete-state hash independence. No terminal or saved-session reproduction claimed.

Evidence files are `lifecycle/probe_lifecycle.py`, `lifecycle/results.json`, `lifecycle/results.hash987.json`, `lifecycle/report.md`.

### UI11-01 — Winter Campaign terminal cannot combine borrowed Enlist Warbands with their Belgic Command

Open, medium priority.

With two actions remaining, allow a combined Belgic Command plus Enlist borrowing; the demonstrated borrowed Raid Reveals two German Warbands and gives Belgae two Resources, consuming both actions.

All five scenario terminal menus lack combined Enlist+Command. The offered standalone Enlist loan is rejected as Unknown free Enlist sub-Command and returns to the menu. The same combined plan validates, survives actual SeatSession pending/save-load/acceptance, and executes successfully.

Winter menu provides paired forms only for Battle+Ambush/Besiege; standalone SA collection sets command=None but still offers borrow, while Command-only collection cannot add borrowing. Standalone execution correctly routes to a free German subcommand rather than the combined loan scope.

[Reference Documents/Card Reference, line 645](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Card%20Reference#L645) · [Reference Documents/Ariovistus/A Card Reference, line 279](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Ariovistus/A%20Card%20Reference#L279) · [Reference Documents/Chapter 4, line 195](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Chapter%204#L195) · [Reference Documents/Ariovistus/Chapter A4, line 44](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Ariovistus/Chapter%20A4#L44) · [AGENT_INTERFACE.md, line 2263](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/AGENT_INTERFACE.md#L2263)

[fs_bot/cli/winter_campaign.py, line 13](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/cli/winter_campaign.py#L13) · [fs_bot/cli/human_plan.py, line 749](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/cli/human_plan.py#L749) · [fs_bot/cli/human_plan.py, line 1242](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/cli/human_plan.py#L1242) · [fs_bot/engine/winter_campaign.py, line 67](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/engine/winter_campaign.py#L67) · [fs_bot/engine/execute.py, line 602](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/engine/execute.py#L602) · [fs_bot/engine/execute.py, line 5952](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/engine/execute.py#L5952)

Five terminal failures after actual shaded63/A63 activation and public after-Harvest hook; each preserves exact board/RNG Five actual SeatSession pending/save-load/combined-plan acceptance controls execute two-action borrowed Raid and retain exact accepted plan Great Revolt and Ariovistus ordinary terminal borrowed Command controls succeed with unchanged planning board Great Revolt and Ariovistus standalone Winter Enlist free German March controls succeed and consume only one action All 14 cases have clean physical conservation and structural checks before/after; hash0/987 output identical

UI8-01/02 concern repeated Winter Battle Regions and March drop-offs. UI10-02 concerns physical visibility in Enlist's free German March; FE6-02/FE7-01 concern March groups. This is Winter terminal construction of a combined borrowed-force Command already supported by the ordinary collector and durable API.

Provide combined borrowed Enlist+Command while two Winter actions remain, using existing physical selection and detached planning. Preserve two-action accounting, single-action limit, standalone free German Commands, costs, geography and expansion four-piece limits. Hiding the broken standalone loan alone is insufficient.

Curated sparse positions with public Event activation then direct post-Harvest capability hook, not naturally sampled full Winters. Terminal availability defect; documented assistant/API combined-plan execution succeeds. No board corruption, balance claim, full-suite claim or production edits.

Evidence files are `frontend/probe_frontend.py`, `frontend/results.json`, `frontend/results.hash987.json`, `frontend/report.md`.

### NP11-01 — Belgic March omits Enlist newly enabled by the Leader's arrival

Open, medium priority.

After March, evaluate Enlist using the resulting Leader range. Two Revealed Germans at Treveri become eligible when Ambiorix arrives in adjacent Atrebates and must March in place to Hide.

Full Pax Gallica dispatch selects March with No SA and translates it as Command only. Ambiorix and four Warbands move to Atrebates for four Resources; both Germans remain Revealed even though the live chooser then selects Enlist german_march_hide at Treveri.

node_b_march chooses Enlist before movement and emits no live post-Command intent. The translation treats No SA as Command only; the post-Command helper includes Belgic Rally/Raid but not March, and generic execution returns immediately for No SA.

[Reference Documents/Chapter 8, line 314](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Chapter%208#L314) · [Reference Documents/Chapter 8, line 390](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Chapter%208#L390) · [Reference Documents/Chapter 4, line 215](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Chapter%204#L215)

[fs_bot/bots/belgae_bot.py, line 1153](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/bots/belgae_bot.py#L1153) · [fs_bot/cli/dispatcher.py, line 87](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/cli/dispatcher.py#L87) · [fs_bot/engine/execute.py, line 164](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/engine/execute.py#L164) · [fs_bot/engine/execute.py, line 4823](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/engine/execute.py#L4823) · [fs_bot/engine/execute.py, line 4977](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/engine/execute.py#L4977)

Source-required authored Enlist on the identical March succeeds; natural preexisting Enlist succeeds; stale positive now-out-of-range Enlist correctly declines; genuine Command-only and absent-Germans controls do no SA; public scoped free Command excludes Treveri from SA scope and correctly leaves Germans Revealed. Seven cases, clean inventory/structure and unchanged planning board/RNG.

New consumer of the known post-Command forecast class: NP9-02 covered Rally/Raid, NP10-01 only Arverni March and explicitly excluded unproven Belgic March. FE6-02 and UI10-02 concern Enlist subcommand representation/physical selection after choosing Enlist.

Carry authorized after-March Enlist intent through planning, translation and execution. Respect actual arrival, Command-only, Event scope, one-SA limit and actual Britannia crossings. March's fallback is Enlist only, never Rampage.

Synthetic legal Pax Gallica board with named Ambiorix and five persistent base-game Devastated marker flags modeling prior Arverni actions; not a claimed full history or untouched setup. No Britannia or natural encounter-rate claim. Authored-SA control distinguished from natural dispatch. Canonical piece helpers throughout.

Evidence files are `bots/probe_bots.py`, `bots/results.json`, `bots/report.md`.

### NP11-02 — Surrounded German Leader never takes the required expansion advance

Open, medium priority.

If the German Leader is in and adjacent only to German Control, expansion March advances him with the most movable Warbands toward a noncontrolled Region via a friendly adjacent step, retaining one origin Warband and Control.

Full Ariovistus dispatch with G1b/G5 No falls through to Raid, gaining six Resources and retaining Ariovistus plus twenty-six Warbands at Ubii. The public authored legal March Ubii to Treveri advances Leader plus twenty-five Warbands toward Roman-Controlled Mandubii, leaves one in Ubii and pays one Resource.

The option_b branch requires all adjacent playable Regions to be German Controlled, then searches those same adjacent Regions for non-German Control. The candidate list is necessarily empty; an immobile one-Warband alternative causes has-effect fallback to Rally/Raid.

[Reference Documents/Ariovistus/Chapter A8, line 208](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/Reference%20Documents/Ariovistus/Chapter%20A8#L208)

[fs_bot/bots/german_bot.py, line 1465](https://github.com/FeeSimple1/fs-bot/blob/702d60a3754ce94a73ead0d0148d647232ecd816/fs_bot/bots/german_bot.py#L1465)

All real German Warband/Ally/Settlement pools placed canonically to disable Rally and Settle; no initial victory and no markers. Public authored advance works. A directly adjacent noncontrolled Treveri makes natural March work; Frost and no-Leader controls correctly Raid. Five cases have clean pre/post census/structure and planning board/RNG purity.

No rounds1-10 finding covers the unreachable Ariovistus ordinary expansion Leader branch. WS6-02/03 were the base-game automatic Germans Phase; NP7-03 Winter consolidation; NP4-01 Roman target strength; BM10-01 Divination Battle forecasting.

Separate a remote noncontrolled target from legal adjacent steps toward it, retaining the all-controlled condition and printed movement, largest group, leave-one, Control, scope and random-choice rules. Preserve Frost/no-movement fallbacks.

Constructed Ariovistus board with exhausted placement pools, no winner, Event, Capability, Drought, Battle or callback. Treveri is a legal intermediate step, not asserted to be the unique correct choice. Earlier multiple-Drought-marker sketch discarded. No natural frequency/balance claim.

Evidence files are `bots/probe_bots.py`, `bots/results.json`, `bots/report.md`.

## Reproduction and limits

Extract the archive and run `python run_witnesses.py --repo /path/to/fs-bot` with the audited Python source bytes. The runner verifies source and protected-file hashes, runs all five probes in temporary directories at hash seeds 0 and 987, and compares each output with the preserved record. Its assertions characterize the observed defects and will need updating after repair. `SHA256SUMS` covers every other archive member. The README gives commands for the full test suite, audited games and mixed-player replay.

The reports document excluded leads and tested boundaries. The lifecycle review inspected Winter gates, victory, automatic phases and Interlude conversion. The frontend review checked exact cohorts, grants and replay. Existing unresolved source questions retain their recorded status. These eight findings require no additional provisional ruling. The passing general suite and sampled games coexist with the failures reproduced by the directed probes. Repair implementation is the next stage.
