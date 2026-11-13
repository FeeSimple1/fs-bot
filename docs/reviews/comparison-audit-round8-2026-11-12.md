# Eighth Falling Sky / Liberty or Death comparison audit

**12 November 2026. The audit found eleven repair groups, four high and seven medium.**
Batch 1 closes LC8-01 and LC8-02. Batch 2 closes BM8-01 and BM8-02.
Seven groups remain open.
The findings and validation below describe the audited revision.
[Batch 1 repairs and validation](eighth-comparison-batch1-2026-11-12.md) ·
[Batch 2 repairs and validation](eighth-comparison-batch2-2026-11-12.md)

Audited Falling Sky commit: `e62b0360c1b91032741ef8f6afa4d247c8ea2437`. Python source SHA-256: `3c047ebcfef915efef8e1da308cd63484b1e6c735b8aba8e5c095de2c5d106b9` across **611 Python files**, Python 3.12.14. Comparator: `FeeSimple1/lod-bot` at `2991ea279062773548ec390a1da75f3e85381702`.

[Finding ledger](comparison-audit-round8-2026-11-12.json) · [Portable evidence](comparison-audit-round8-2026-11-12-evidence.zip) · [Current status](../current-status.md)

## Method and coverage

Repeated the authorized comparison using Liberty or Death engineering patterns: missing consumers, alternate execution paths, late-state decisions, complete Event effects, phase counters, ownership policy, and durable human decisions. Game-rule conclusions use only the supplied Falling Sky/Ariovistus references and the thirteen adopted provisional rulings. The full reference inventory and original plus second-through-seventh ledgers were checked. Similar bug families are distinguished by their newly proven consumers; no repaired finding is counted again.

Five focused review lanes produced executable public-path witnesses and controls. A separate validation lane ran the existing suite and held-out games. Each finding received independent source/code review and a second run; the lead reviewer additionally inspected every witness and reran all five scripts under hash seeds 0 and 987. Outputs match exactly. Physical fixtures use canonical piece helpers and check inventory and structure before and after. Controlled positions and supplied phase metadata are described below, rather than represented as naturally encountered games.

## Confirmed findings

| ID | Priority | Finding |
|---|---|---|
| LC8-01 | High | Gallic War ends at its fourth post-Interlude Winter while the fifth remains in the deck |
| LC8-02 | High | A sole human player wins immediately at a non-final Winter despite the standard solitaire rule |
| BM8-01 | High | Fixed Event Battles and the automatic Arverni Phase still omit shaded Massed Gallic Archers |
| BM8-02 | Medium | Both sides of German Phalanx fail to cancel the corresponding Massed Gallic Archers effect |
| UI8-01 | High | Winter Campaign accepts repeated Battle Regions as one of its two actions |
| UI8-02 | Medium | Winter Campaign March silently omits the intermediate drop-off decision |
| EV8-01 | Medium | Belgae play Legiones despite the absence of any possible Legion Loss |
| EV8-02 | Medium | Arverni choose ineffective Pompey and Gallia Togata when their removal prerequisites fail |
| EV8-03 | Medium | Roman Forced Marches has no non-player movement producer |
| NP8-01 | Medium | Aedui omit favorable additional Battles by counting defenders already removed by the Attack |
| NP8-02 | Medium | Aedui never reconsider an initially empty Special Ability after Rally enables Suborn |

## Validation

- **10,116 existing tests pass**, zero failures, errors or skips; JUnit 80.202 seconds, five workers. Six external anyio/pytest deprecation warnings are preserved in the log.
- **20/20 audited bot games complete**, second-edition seeds 45–48 across all five scenarios; two Interludes. All inventory/structure, completion flags, rankings and winner checks pass. There are 115 grouped diagnostic rows / 220 incidents, all `legal-decline`.
- **20 distinct mixed-player cases** match byte-for-byte in JSON and stdout at hash seeds 0/987, including internal replay: 80 executions, 623 human turns and 152 Event turns per hash sample, 138 Events completed, zero partials and zero hard findings.
- Both GitHub checks on the audited parent passed: [CI](https://github.com/FeeSimple1/fs-bot/actions/runs/43164981413) and [Package installation](https://github.com/FeeSimple1/fs-bot/actions/runs/43164981430).
- No new legacy balance matrix or baseline refresh was needed for unchanged production sources. These clean general checks coexist with the directed rule failures below; the new Winter findings limit what the clean game-completion flags establish.

## Suggested repair sequence

| Batch | Findings | Work |
|---|---|---|
| 1 | LC8-01, LC8-02 | Correct post-Interlude final-Winter detection and standard solo victory policy. |
| 2 | BM8-01, BM8-02 | Share Archers Battle orchestration and apply both German Phalanx cancellation effects. |
| 3 | UI8-01, UI8-02 | Validate Winter Campaign Command scope and restore live human March drop-offs. |
| 4 | EV8-01, EV8-02, EV8-03 | Repair Event decline conditions and the Roman Forced Marches producer. |
| 5 | NP8-01, NP8-02 | Correct Aedui additional-Battle forecasting and post-Rally Special Ability selection. |

Fixes should turn the relevant defective witness into a regression test, preserve its positive controls, run the full suite and appropriate game/replay checks, and update this ledger. Game-outcome changes require causal review before any balance-baseline refresh. Batch 2 should share the Archers hook before applying cancellation so the two fixes cover the same execution paths.

## Finding details

### LC8-01 — Gallic War ends at its fourth post-Interlude Winter while the fifth remains in the deck

**Expected:** With no Faction passing a victory threshold, the fourth of five second-half Winter cards must continue through the remaining Winter phases and into the final year. The fifth second-half Winter is the last Winter and forces final scoring.

**Observed:** At the fourth second-half Winter, cumulative winter_count is 6, rebuilt played_cards contains 4 Winters, and the deck still contains 1 Winter. play_card reports is_final=true and game_over=true, performs only Victory, and leaves that fifth Winter unplayed. No Faction passes its threshold: Romans 15; Arverni 6 off-map Legions and 7 Allies/Citadels; Aedui 1; Belgae 8. Validated save/load reproduces the same outcome.

**Cause:** _count_winter_cards_in_game subtracts the rebuilt played-Winter count, then substitutes max(played Winters, cumulative resolved winter_count). Once cumulative winter_count dominates after Interlude, that substitution omits the newly drawn but unresolved current Winter. At the witnessed boundary it returns 1 + max(4,6) = 7, so resolve_winter_card's 6+1 >= 7 check ends the game even though one Winter remains in the deck.

**Sources:** [Reference Documents/Ariovistus/A Scenario - The Gallic War:14-17](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Ariovistus/A%20Scenario%20-%20The%20Gallic%20War#L14); [Reference Documents/Ariovistus/A Scenario - The Gallic War:114-129](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Ariovistus/A%20Scenario%20-%20The%20Gallic%20War#L114); [Reference Documents/Chapter 2:94-102](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Chapter%202#L94); [Reference Documents/Chapter 6:7-12](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Chapter%206#L7).

**Implementation:** [fs_bot/engine/game_engine.py:763-764](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/game_engine.py#L763); [fs_bot/engine/game_engine.py:790-810](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/game_engine.py#L790); [fs_bot/engine/interlude.py:1351-1354](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/interlude.py#L1351); [fs_bot/engine/winter.py:195-197](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/winter.py#L195).

**Controls:** Third of five second-half Winters: is_final=false, game_over=false. Fifth of five second-half Winters: is_final=true, game_over=true. Ordinary Pax fourth of five Winters with no threshold winner: is_final=false, game_over=false. Saved penultimate boundary loaded with load_game(validate=True) reproduces the direct outcome exactly. validate_state and check_structural_integrity are empty before and after every branch.

**Earlier-audit distinction:** Not WS4-02's deck membership issue: the rebuilt deck correctly contains five Winters here. Not WS4-03's Nori cleanup, WS5-01's home-City restoration, or the earlier first-half Interlude-unreachable fix. The Interlude actually completes; this defect is the later fourth-Winter finality calculation. No Optimates capability is present, so the open skipped-Victory-ordinal question is irrelevant. No prior ledger through round7 records this boundary.

**Repair scope:** Correct the distinction between resolved Winters, the currently drawn unresolved Winter, and future Winters when deciding finality after Interlude. Review the shared next_winter_is_final consumer without changing its pre-Winter planning semantics. Preserve first-half Interlude continuation, ordinary scenario finality, and saved cumulative history compatibility.

**Fixture:** See limitations and the preserved lane ledger.

**Limits:** Controlled phase integration, not a natural full-game trace or frequency estimate. Starts with real Gallic War setup seed 21 and runs the complete production Interlude through run_winter_round with no threshold winner. The first-half third-Winter cursor and earlier resolved count are supplied as boundary metadata. The later board adds eight legal, unrestricted Allied Tribes using the canonical _ally_tribe helper solely to keep every threshold unmet. Later card history is obtained by production draw_card in the actual rebuilt deck order; the cumulative number of earlier Winters and consumed first-Winter flags are supplied explicitly instead of executing those earlier years. No piece counts are directly edited, no engine functions are patched, and the failing action is production play_card.

**Evidence:** `lifecycle/witness_lifecycle.py`; `lifecycle/results.json` in the portable archive. The original lane ledger preserves additional source annotations.

### LC8-02 — A sole human player wins immediately at a non-final Winter despite the standard solitaire rule

**Expected:** Under standard §8.9, a sole human player does not win before final Winter. A human threshold crossing alone must leave this non-final Victory Phase open, while a Non-player threshold winner still ends the game. Multiplayer threshold victories and final-Winter ranking retain their ordinary behavior.

**Observed:** A supported setup with only Romans assigned to a human and the other three seats Non-player has Roman score16 at the first Reconquest Winter; three Winter cards remain. play_card reports is_final=false but game_over=true and winner=Romans, then stops after Victory. No Easy option was selected or represented. The validated save/load repeat has exactly the same result.

**Cause:** victory_phase immediately finalizes any faction returned by check_any_victory. Winner selection recognizes thresholds and NP precedence but does not distinguish a sole human player's pre-final victory policy. The threshold predicate itself is valid and also needed by Frost planning; the missing guard belongs to Victory Phase/end-of-game policy.

**Sources:** [Reference Documents/Chapter 8:992-999](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Chapter%208#L992); [Reference Documents/Chapter 6:7-12](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Chapter%206#L7); [Reference Documents/Chapter 8:220-228](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Chapter%208#L220).

**Implementation:** [fs_bot/engine/winter.py:175-181](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/winter.py#L175); [fs_bot/engine/victory.py:479-511](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/victory.py#L479); [fs_bot/state/player_ownership.py:73-88](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/state/player_ownership.py#L73).

**Controls:** Same board with two different human owners: Roman threshold win remains valid. Same board with all four seats Non-player: Roman threshold win remains valid. Same board with only human Arverni and NP Romans: Roman NP threshold win remains valid. Same board with human Romans at the actual final fourth Reconquest Winter: finality and Roman win are valid. Saved sole-human non-final boundary loaded with load_game(validate=True) exactly repeats the direct outcome. validate_state and check_structural_integrity are empty before and after every branch.

**Earlier-audit distinction:** The October9 outcome audit fixed Allied-City double counting, simultaneous winner ranking, NP precedence and result propagation; none adds the standard sole-human pre-final exception. WS-F09 added shared-player representation and paired victory but did not apply §8.9 here. All original and comparison ledgers through round7 were checked; this policy boundary is not recorded as a known source question or prior repaired finding.

**Repair scope:** Apply standard solitaire eligibility to Victory Phase/end-of-game selection while preserving threshold scoring for Frost, bot heuristics and displays. Preserve NP wins, multiplayer wins, final-Winter scoring, and legacy ownership compatibility. This finding does not request implementation of optional Easy/Difficult modes or settle their interactions with unrelated Events.

**Fixture:** See limitations and the preserved lane ledger.

**Limits:** Controlled Victory Phase integration, not a sampled full-game trace. Uses supported setup_scenario faction_owners for one human Roman. Two existing Belgic Ally discs return to Available through canonical _unally_tribe, raising Roman score14 to16 and reducing Belgic score15 to13; Aedui and Arverni remain tied at three Allies/Citadels, so no NP passes a threshold. The production deck is consumed with draw_card to the selected Winter and its earlier resolved count is supplied explicitly. The failing path is play_card(execute=True), with no monkeypatches or direct piece-count writes. No claim is made about optional difficulty modes or paired-human solitaire interpretation.

**Evidence:** `lifecycle/witness_lifecycle.py`; `lifecycle/results.json` in the portable archive. The original lane ledger preserves additional source annotations.

### BM8-01 — Fixed Event Battles and the automatic Arverni Phase still omit shaded Massed Gallic Archers

**Expected:** With shaded Card 27 active, every Battle involving six Arverni Warbands first gives the other side one Loss. Six Arverni versus four Roman Auxilia should remove all four Romans through either public numeric2 shaded or the full Arverni Phase. Aedui four Warbands executing numeric36 unshaded against six Arverni should first lose one Aedui, then inflict one Attack Loss, leaving three Hidden Aedui and five Arverni; the printed no-Counterattack exception remains.

**Observed:** Numeric2 shaded and the full Arverni Phase both leave one Roman Auxilia; turning Archers off gives exactly the same outcome. The matched ordinary public Battle correctly removes all four Romans. Numeric36 leaves four Hidden Aedui and four Arverni with or without Archers, and retains no Counterattack.

**Cause:** The sole shaded Archers pre-Battle hook remains inside _execute_battle at execute.py:4008-4022. The recent shared battle_capabilities.resolve_single integrates Slingers and Horse, but calls resolve_battle without Archers; the Arverni Phase likewise adds only queue/Slingers hooks before its direct resolve_battle call.

**Sources:** [Reference Documents/Card Reference:274-279](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Card%20Reference#L274); [Reference Documents/Card Reference:18-19](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Card%20Reference#L18); [Reference Documents/Card Reference:358-360](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Card%20Reference#L358); [Reference Documents/Ariovistus/Chapter A6:112-124](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Ariovistus/Chapter%20A6#L112); [Reference Documents/Chapter 5:25-28](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Chapter%205#L25).

**Implementation:** [fs_bot/engine/execute.py:4008-4022](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/execute.py#L4008); [fs_bot/engine/battle_capabilities.py:53-73](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/battle_capabilities.py#L53); [fs_bot/engine/execute.py:2148-2161](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/execute.py#L2148); [fs_bot/engine/execute.py:3064-3068](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/execute.py#L3064); [fs_bot/engine/execute.py:2233-2238](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/execute.py#L2233); [fs_bot/engine/arverni_phase.py:845-850](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/arverni_phase.py#L845).

**Controls:** Six-versus-four ordinary public Battle, capability on/off. Numeric2 and full Arverni Phase, each with identical capability-off position. Numeric36 defending-Arverni fixed grant, capability on/off; Hidden attackers and no Counterattack verified.

**Earlier-audit distinction:** BM7-01 confirmed Slingers and shaded Horse, and its Limits explicitly listed Archers as an unproved static lead. Batch1 repaired only Slingers/Horse plumbing. This now dynamically confirms the distinct Card27 hook left outside that shared repair, without claiming the earlier proven capability failures remain. No earlier ledger through round7 counted this Archers execution omission.

**Repair scope:** Centralize the per-Battle shaded Archers start effect in orchestration shared by ordinary, fixed Event, and automatic Battles, preserving Event exceptions, casualty-owner requests, participating-force views, empty-force handling and temporary-state cleanup. Verify defending as well as attacking Arverni and leave one-use Slingers/Horse semantics intact.

**Fixture:** Controlled build_initial_state positions at seed 7, using place_piece for every counter and retaining the permanent Provincia Fort. Capabilities are acquired via public execute_decision Events. Human player seats use a raw decision callback that declines Retreat and otherwise delegates; game-run Arverni use run_arverni_phase, never a fictitious player turn. Frost skips March and zero enemy Resources prevents Raid. The Arverni Phase lawfully adds its Carnutes Ally; Warband counts remain six. Every public action/phase is bracketed by validate_state and check_structural_integrity. No production code/test writes, patches, mocks, or direct piece-count mutations.

**Limits:** Constructed lawful sparse positions, not naturally encountered game traces. Eighteen directed cases establish these consumers and controls only; no frequency, winner-impact or exhaustive capability-combination claim. Script asserts the audited defective behavior and should fail after a correct repair.

**Evidence:** `battle/probe_battle.py`; `battle/probe_battle-output.json` in the portable archive. The original lane ledger preserves additional source annotations.

### BM8-02 — Both sides of German Phalanx fail to cancel the corresponding Massed Gallic Archers effect

**Expected:** After A31 shaded is acquired later than Card27 shaded, four attacking German Warbands versus six Arverni should receive no initial Archers Loss, leaving two Germans and four Arverni. After A31 unshaded is acquired later than Card27 unshaded, a full Arverni Phase with six Arverni versus four Germans should inflict three Attack Losses, leaving one German; the Archers reduction benefits Germans and must be cancelled.

**Observed:** Stalwart plus shaded Archers leaves one German and five Arverni, identical to Archers without Stalwart. Removing Archers leaves two Germans and four Arverni. Inflexible plus unshaded Archers still leaves two Germans after the full phase, identical to Archers without Inflexible; omitting Archers leaves one German. The non-German Belgic controls correctly retain both Archers effects.

**Cause:** The shaded Archers initial-loss block has no A31/participant cancellation gate. The unshaded Archers subtraction is unconditional for Arverni attack in both _calculate_attack_losses and calculate_losses, although adjacent Motivation/Horse blocks apply A31 cancellation. Group both sides as one missing Card27 cancellation consumer family.

**Sources:** [Reference Documents/Ariovistus/A Card Reference:126-131](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Ariovistus/A%20Card%20Reference#L126); [Reference Documents/Card Reference:272-279](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Card%20Reference#L272); [Reference Documents/Chapter 5:50-51](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Chapter%205#L50); [Reference Documents/Chapter 5:66-73](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Chapter%205#L66); [Reference Documents/Ariovistus/Chapter A6:112-124](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Ariovistus/Chapter%20A6#L112).

**Implementation:** [fs_bot/engine/execute.py:4013-4022](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/execute.py#L4013); [fs_bot/battle/resolve.py:474-477](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/battle/resolve.py#L474); [fs_bot/battle/losses.py:293-297](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/battle/losses.py#L293).

**Controls:** Each side: neither capability, Archers only, A31 only, both with A31 acquired last. Matched Belgic attacker/defender with both capabilities retains the corresponding Archers effect. Both full Arverni Phase variants add only their ordinary Ally before the identical six-Warband Ambush.

**Earlier-audit distinction:** EX3-04 covered Horse; BM5-01 unshaded LegioX; BM6-01 shaded LegioX and Slingers; BM7-02 Ballistae saves. Round7 expressly excluded Archers/Elite cancellation as unproved. This is a newly witnessed Card27 consumer, grouped once across the two A31 sides. Elite, one-shot Event conflicts, and unresolved non-player Elite designation remain excluded.

**Repair scope:** Apply Phalanx cancellation to both Card27 effects using the actual opposing faction: Stalwart suppresses the extra Loss against Germans; Inflexible suppresses the reduction benefiting a German defender. Update both forecast and live Attack arithmetic, and apply the same context in the shared initial-Archers hook from BM8-01. Preserve non-German Battles and ordinary effects when A31 is absent.

**Fixture:** Controlled build_initial_state positions at seed 7, using place_piece for every counter and retaining the permanent Provincia Fort. Capabilities are acquired via public execute_decision Events. Human player seats use a raw decision callback that declines Retreat and otherwise delegates; game-run Arverni use run_arverni_phase, never a fictitious player turn. Frost skips March and zero enemy Resources prevents Raid. The Arverni Phase lawfully adds its Carnutes Ally; Warband counts remain six. Every public action/phase is bracketed by validate_state and check_structural_integrity. No production code/test writes, patches, mocks, or direct piece-count mutations.

**Limits:** Constructed lawful sparse positions, not naturally encountered game traces. Eighteen directed cases establish these consumers and controls only; no frequency, winner-impact or exhaustive capability-combination claim. Script asserts the audited defective behavior and should fail after a correct repair.

**Evidence:** `battle/probe_battle.py`; `battle/probe_battle-output.json` in the portable archive. The original lane ledger preserves additional source annotations.

### UI8-01 — Winter Campaign accepts repeated Battle Regions as one of its two actions

**Expected:** Each Battle Command selects Carnutes once. Winter Campaign may repeat Battle as its second Command, but each Command consumes one of the two granted actions. A response selecting the same Region twice within one Battle must remain pending for correction with board and RNG restored.

**Observed:** The public Winter Campaign validator accepts an Aedui Battle plan containing Carnutes twice and returns an action cost of 1. The public after-Harvest consumer resolves both entries, charging 2 Resources, leaving its second action available. Starting with 12 Aedui and 10 Revealed Belgae, it leaves 10 Aedui and 0 Belgae. The legal one-entry control leaves 10 Aedui and 4 Belgae and charges 1 Resource. The bad and good plans both report remaining_actions=1. A real saved SeatSession accepts and journals the repeated plan, pauses for casualty choices and its remaining action, resumes after save/load, and reproduces exactly under signature-verified replay. This reproduces with both numeric-card edition profiles and A63 in Ariovistus.

**Cause:** Winter Campaign intentionally bypasses the ordinary action wrapper to allow its printed compatibility exceptions. Its separate validator validates ownership, budget and mechanical success, but omits the unchanged Command-wide Region uniqueness constraint. The lower Battle executor treats the entries as independent Battles.

**Sources:** [Reference Documents/Chapter 3:2-11](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Chapter%203#L2); [Reference Documents/Card Reference:645-655](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Card%20Reference#L645); [Reference Documents/Ariovistus/A Card Reference:279-286](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Ariovistus/A%20Card%20Reference#L279).

**Implementation:** [fs_bot/engine/winter_campaign.py:14-38](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/winter_campaign.py#L14); [fs_bot/engine/winter_campaign.py:66-98](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/winter_campaign.py#L66); [fs_bot/engine/winter_campaign.py:119-137](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/winter_campaign.py#L119); [fs_bot/tools/seat_session.py:270-274](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/tools/seat_session.py#L270); [fs_bot/engine/action_validation.py:157-175](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/action_validation.py#L157); [fs_bot/engine/execute.py:3832-3839,3875-3888](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/execute.py#L3832).

**Controls:** Ordinary validate_player_action rejects the identical repeated Battle plan with Select each Battle Region only once (§3.1), without changing live state or RNG. One Battle entry is accepted and produces the expected 10 Aedui / 4 Belgae / 19 Resources versus repeated-plan 10 / 0 / 18. A separate Winter Campaign Aedui two-Region Ambush is rejected by the executor's existing one-Region guard. This is a narrowing control, not another finding. Missing and invalid-command durable submissions keep d000001 pending and retain its exact board. Every later pause rolls the engine board and RNG back while preserving accepted journal entries on disk. All fixture, pending live-board, final-state and replay validate_state/check_structural_integrity checks return empty lists. The issue is action legality, not inventory corruption. The strengthened fixture asserts check_any_victory(state) is None, preventing an unrelated prior Victory Phase winner.

**Earlier-audit distinction:** CM2-01 was the ordinary Sequence-of-Play repeated-Battle/self-target boundary; that path now rejects the plan and is the paired control. FE6-01 concerned Aedui Ambush scope in free Event Commands and its guard remains effective here. BE5-01 concerned Winter Campaign acquisition without a Gallic recipient; acquisition is legal in these fixtures. None records this paid after-Harvest budget/admission boundary. No old finding is reopened.

**Repair scope:** Apply unchanged whole-Command selection validation to Winter Campaign before preview and durable admission, while preserving its paid action budget and explicit SA/accompanying-Command/Britannia exceptions. Preserve ordinary and Aedui Ambush checks; do not infer that every shared restriction is currently bypassed in effect. Add focused base/Ariovistus saved-session coverage for the rejection and a legal two-separate-Battle continuation.

**Fixture:** See limitations and the preserved lane ledger.

**Limits:** Controlled build_initial_state positions at seed 19, not a naturally sampled full game or full Winter replay. Includes Provincia's permanent Roman Fort, legal 12/10 troop placements through piece helpers, Aedui Resources 20, and legal public acquisition of shaded 63/A63 with the proper owner. The current card is then selected as Winter to exercise the production after-Harvest consumer directly. Real SeatSession and the engine's same action transaction used by play_card provide persistence/rollback; no mock rule handlers or monkeypatches. CLI menus are not claimed to generate duplicate Regions. This is an authored durable/API validation defect. Sixteen additional off-route Allied Tribes (six German, five Arverni, five Aedui) are placed with canonical Tribe identities, physical helpers, exact allegiance links and asserted faction restrictions. All resource-using Factions begin at 20. check_any_victory is asserted None before the consumer; Romans have 14, Aedui trail the German ally total, Arverni have only five Allies, Belgae have no Control, and expansion German control remains below threshold. This avoids an unrelated already-ended Winter fixture.

**Evidence:** `frontend/probe_winter_campaign.py`; `frontend/probe_winter_campaign-output.json` in the portable archive. The original lane ledger preserves additional source annotations.

### UI8-02 — Winter Campaign March silently omits the intermediate drop-off decision

**Expected:** A human Arverni player Marching Vercingetorix and Warbands through a first Region may leave selected Warbands there before the group continues to the second Region. The paid Winter Campaign Command retains that normal March choice.

**Observed:** A saved Arverni Winter Campaign session accepts the legal Carnutes→Mandubii→Sequani March of Vercingetorix and four Warbands. It immediately advances to the second Winter Campaign action without any march_dropoff request and leaves all four Warbands at Sequani. On the otherwise identical ordinary Command control, the engine offers march_dropoff at Mandubii and accepts leaving two there, producing two at Mandubii and two at Sequani. Both paths cost one Resource. The durable Winter transcript contains only two winter_campaign responses; missing/invalid-input controls, rollback, save/load and signature-verified replay all pass.

**Cause:** The Winter Campaign dispatcher reuses the lower command execution path without enabling human March drop-offs. All existing physical choice/persistence machinery is present, but this paid Command entry point never invokes it.

**Sources:** [Reference Documents/Chapter 3:61-68](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Chapter%203#L61); [Reference Documents/Chapter 3:261-266](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Chapter%203#L261); [Reference Documents/Card Reference:645-655](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Card%20Reference#L645).

**Implementation:** [fs_bot/engine/winter_campaign.py:66-75](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/winter_campaign.py#L66); [fs_bot/engine/execute.py:357-376](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/execute.py#L357); [fs_bot/engine/execute.py:4379-4397,4447-4459](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/execute.py#L4379); [fs_bot/engine/execute.py:4684-4695](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/execute.py#L4684); [fs_bot/engine/march_choices.py:201-250](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/march_choices.py#L201).

**Controls:** Ordinary public execute_decision on the same pieces and route offers exactly one march_dropoff; the chosen two Warbands remain at Mandubii, while Vercingetorix and two continue to Sequani. Winter and ordinary paths both charge one Resource, and the Winter action budget decreases by one; this is choice loss, not free-cost accounting. The Winter validator preview leaves live board and RNG unchanged. Missing and invalid-command durable responses retain d000001 and its board; the accepted first March persists in the journal while engine board/RNG roll back at the second-action prompt. Save/load and signature-verified replay preserve board, RNG and exact log; all before, pending, after and replay census/structural checks pass. The strengthened fixture asserts check_any_victory(state) is None, preventing an unrelated prior Victory Phase winner.

**Earlier-audit distinction:** Original MARCH-DROPOFF addressed ordinary March; that repaired path is the passing control. FE5-02 addressed generic free Event-granted March and Assembly of Gaul. This is the separate paid after-Harvest Winter Campaign entry point. UI8-01 shares its use of the lower dispatcher, but the repairs are independent: rejecting repeated Region selections does not enable a live drop-off request, and enabling the request does not validate action scope.

**Repair scope:** Enable the normal live drop-off integration for human paid Winter Campaign Marches without enabling Sequence-of-Play-only gifts or stripping Winter Campaign's explicit exceptions. Preserve actual physical cohorts and deterministic pause/retry. Add a durable Winter prompt/save/load witness plus the existing ordinary/free-grant controls.

**Fixture:** See limitations and the preserved lane ledger.

**Limits:** Controlled base Great Revolt seed-19 initialized position, with permanent Provincia Fort, Vercingetorix plus four Hidden Arverni Warbands in Carnutes, no intermediate enemy/Devastated/Rhenus/Britannia impediment, and Resources 20. Shaded 63 is acquired through public execute_decision for Arverni before the after-Harvest context is selected. This directly tests the production consumer and durable session, not a full sampled Winter. A two-group preplanned route might reproduce this empty-board final distribution, but it does not supply the missing live intermediate physical choice. No claim is made that every final distribution is otherwise unrepresentable. Sixteen additional off-route Allied Tribes (six German, five Arverni, five Aedui) are placed with canonical Tribe identities, physical helpers, exact allegiance links and asserted faction restrictions. All resource-using Factions begin at 20. check_any_victory is asserted None before the consumer; Romans have 14, Aedui trail the German ally total, Arverni have only five Allies, Belgae have no Control, and expansion German control remains below threshold. This avoids an unrelated already-ended Winter fixture.

**Evidence:** `frontend/probe_winter_campaign.py`; `frontend/probe_winter_campaign-output.json` in the portable archive. The original lane ledger preserves additional source annotations.

### EV8-01 — Belgae play Legiones despite the absence of any possible Legion Loss

**Expected:** Numeric2 shaded is No Belgae when no Loss can be forced on a Legion. With no Legion anywhere on the map, the bot must decline the Event and continue its flowchart, even though it could remove an Auxilia.

**Observed:** Actual dispatch chooses Event2 and includes the exact instruction saying if none, No Belgae. Public execution Battles at Carnutes and removes its one Roman Auxilia, while no Legion Loss was possible. Disabling only the Event option on the original position produces a Rally continuation.

**Cause:** The instruction text is stored/displayed, but should_decline_event has no numeric2 Belgic gate. np_event_available returns None for numeric2 and is_event_effective treats its FREE_BATTLE flag as effective. The independent _derive_card_2 permits a Region without a Legion and ranks generic Roman presence.

**Sources:** [Reference Documents/belgae_bot_event_instructions.txt:37](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/belgae_bot_event_instructions.txt#L37); [Reference Documents/Chapter 8:30](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Chapter%208#L30); [Reference Documents/Card Reference:18](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Card%20Reference#L18).

**Implementation:** [fs_bot/cards/bot_instructions.py:395](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/cards/bot_instructions.py#L395); [fs_bot/bots/bot_common.py:369](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/bots/bot_common.py#L369); [fs_bot/cards/event_conditions.py:113](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/cards/event_conditions.py#L113); [fs_bot/cards/event_eval.py:1075](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/cards/event_eval.py#L1075); [fs_bot/engine/execute.py:6207](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/execute.py#L6207).

**Controls:** A matched board adds one Legion at Carnutes from the track through place_piece. The same public bot path then plays Event2 and removes that Legion automatically. The original board with can_play_event=False chooses Rally. All pre/post checks pass.

**Earlier-audit distinction:** PR-12 and the numeric45 repair concern Litaviccus forecasting; PR-12 explicitly does not cover other card procedures. BM7-01 repaired fixed Event Battle capability hooks, including numeric2; it did not enforce numeric2 selection instructions. This finding claims only the unambiguous zero-Legion condition, not an unsettled prediction model or ranking among possible Legion Battles.

**Repair scope:** Apply the numeric2 Belgic no-Legion-Loss condition before Event commitment and keep the Event target producer consistent with it. Preserve the first-Loss automatic-Legion modifier and other factions’ distinct instructions; do not mechanically transplant PR-12 beyond its stated scope.

**Fixture:** Sparse canonical Great Revolt seed1: permanent Provincia Fort, two Belgic Warbands and one Roman Auxilia at Carnutes, no Legion on the map, all four seats NPC. The small Belgic group avoids the earlier four-Warband/Leader threat gate.

**Limits:** Controlled lawful witnesses establish the reported mechanisms, not sampled encounter frequency or exhaustive Event coverage. All physical pieces use canonical helpers. Every relevant pre/post census and structural check passes. No production code or rule sources changed; no repository tests run by the Event review lane (the separate validation lane ran the full suite).

**Evidence:** `events/probe_events.py`; `events/probe_events-output.json` in the portable archive. The original lane ledger preserves additional source annotations.

### EV8-02 — Arverni choose ineffective Pompey and Gallia Togata when their removal prerequisites fail

**Expected:** Arverni must decline shaded numeric3 while more than four Legions remain on the track, and shaded numeric5 while the Senate is in Adulation. Both Events have no effect under those printed conditions, despite the presence of Roman pieces.

**Observed:** In each controlled position actual Arverni dispatch selects the Auto1-4 Event; public execution reports executed=true and changes no game effect. Each position has two Roman Legions and two Auxilia at Provincia, ten track Legions, and Adulation. The Event-disabled flowchart instead selects Rally.

**Cause:** Generic REMOVES_LEGIONS/REMOVES_AUXILIA checks establish effectiveness from pieces anywhere on the map, without applying numeric3’s track count or numeric5’s Senate prerequisite. There is a dedicated A5 shaded Adulation guard, but no corresponding numeric5 guard. The actual two handlers correctly enforce their prerequisites, causing the chosen Events to do nothing.

**Sources:** [Reference Documents/Card Reference:28](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Card%20Reference#L28); [Reference Documents/Card Reference:47](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Card%20Reference#L47); [Reference Documents/Chapter 8:30](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Chapter%208#L30); [Reference Documents/Chapter 8:685](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Chapter%208#L685).

**Implementation:** [fs_bot/cards/event_eval.py:1001](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/cards/event_eval.py#L1001); [fs_bot/cards/event_eval.py:1164](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/cards/event_eval.py#L1164); [fs_bot/cards/event_conditions.py:113](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/cards/event_conditions.py#L113); [fs_bot/cards/card_effects.py:449](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/cards/card_effects.py#L449); [fs_bot/cards/card_effects.py:523](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/cards/card_effects.py#L523).

**Controls:** For numeric3, canonical placement moves six additional track Legions into Provincia, reducing the track to four: the same public Arverni path removes two Legions. For numeric5, changing Senate to Intrigue produces one Legion plus two Auxilia removed. With the Event disabled, each original board has a non-Pass Rally continuation. All checks pass.

**Earlier-audit distinction:** BE7-03 covered the distinct nearby-Legion prerequisite for shaded Rhenus Bridge18/A18, now fixed. BE6-03 covered named Ambiorix presence. This is a new pair of conditional Roman-removal consumers, conservatively grouped under the same ineffective-Event mechanism. Existing BE5-03 Gallia Togata geography work concerns unshaded map access, not shaded availability.

**Repair scope:** Share the actual numeric3 track and numeric5 Senate prerequisites with Event effectiveness checks, including the ordinary potential removable-piece requirement. Keep A5 scenario identity separate, preserve Auto1-4’s position after ineffectiveness checks, and cover both positive and unmet-prerequisite boundaries.

**Fixture:** Two sparse canonical Great Revolt seed1 boards with permanent Provincia Fort, two map Legions, two Auxilia, ten track Legions, and Senate Adulation. All four seats NPC. Only current card differs, numeric3 versus numeric5.

**Limits:** Controlled lawful witnesses establish the reported mechanisms, not sampled encounter frequency or exhaustive Event coverage. All physical pieces use canonical helpers. Every relevant pre/post census and structural check passes. No production code or rule sources changed; no repository tests run by the Event review lane (the separate validation lane ran the full suite).

**Evidence:** `events/probe_events.py`; `events/probe_events-output.json` in the portable archive. The original lane ledger preserves additional source annotations.

### EV8-03 — Roman Forced Marches has no non-player movement producer

**Expected:** Numeric32 must relocate Roman Forces using the printed Roman March priorities. In the controlled board, Provincia is the sole mobile origin and Bituriges the sole enemy-base destination; Caesar, two Legions and eighteen Auxilia can relocate there, and the Auxilia become Hidden.

**Observed:** Actual Roman dispatch selects numeric32 with its correct Roman March instruction, but public execution returns success with all twenty-one mobile pieces stationary and no game effect. The untouched Pax Gallica physical setup independently chooses and executes the same no-op. An explicit public numeric32 plan from the controlled starting board relocates all twenty-one pieces and Hides the eighteen Auxilia.

**Cause:** _derive_card_32 returns an empty dict immediately whenever faction is not Arverni. Its docstring incorrectly claims that every other NPC has No Faction instructions. The card handler defaults missing moves to an empty list and successfully finishes that empty relocation.

**Sources:** [Reference Documents/roman_bot_event_instructions.txt:30](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/roman_bot_event_instructions.txt#L30); [Reference Documents/Card Reference:318](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Card%20Reference#L318); [Reference Documents/Chapter 8:136](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Chapter%208#L136); [Reference Documents/Chapter 8:939](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Chapter%208#L939).

**Implementation:** [fs_bot/engine/execute.py:3464](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/execute.py#L3464); [fs_bot/engine/execute.py:6400](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/execute.py#L6400); [fs_bot/engine/execute.py:6413](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/execute.py#L6413); [fs_bot/cards/card_effects.py:1355](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/cards/card_effects.py#L1355).

**Controls:** On the identical controlled board, a player_action submitted to public execute_decision supplies the three physical move rows; it moves twenty-one pieces into Bituriges, Hides eighteen Auxilia, and leaves the permanent Fort at Provincia. All pre/post census and structural checks pass. The explicit control demonstrates the exact eligible movement, not an alternate human-only power.

**Earlier-audit distinction:** BE5-03 fixed numeric32 rejecting legal Cisalpina movement after Gallia Togata; that was the handler’s playable-map consumer. Earlier Arverni numeric32 work supplied an Arverni producer. Neither supplied the missing Roman producer. No geography, Arverni forecasting, or prior Oppida/Procillus/Divico fix is recounted.

**Repair scope:** Supply a numeric32 Roman relocation plan following its specific Roman instructions, with scenario-aware non-Britannia endpoints, exact original physical counters and visibility, and proper random tie handling. Preserve the card’s relocation freedoms rather than imposing ordinary March range/cost/Harassment. Derive availability from the resulting legal plan without consuming live preview choices.

**Fixture:** Sparse canonical Great Revolt seed1: permanent Provincia Fort; Caesar, two track-sourced Legions and eighteen Revealed Auxilia in Provincia; sole enemy Ally at Bituriges. Two Auxilia remain Available, satisfying the explicit section8.8.3 gate. A second witness uses untouched Pax setup seed1, changing only current Event and NPC-seat metadata.

**Limits:** Controlled lawful witnesses establish the reported mechanisms, not sampled encounter frequency or exhaustive Event coverage. All physical pieces use canonical helpers. Every relevant pre/post census and structural check passes. No production code or rule sources changed; no repository tests run by the Event review lane (the separate validation lane ran the full suite).

**Evidence:** `events/probe_events.py`; `events/probe_events-output.json` in the portable archive. The original lane ledger preserves additional source annotations.

### NP8-01 — Aedui omit favorable additional Battles by counting defenders already removed by the Attack

**Expected:** After the guaranteed Allied Tribe Loss at Carnutes triggers Battle, Aedui must also Battle four of their Revealed Warbands against six Revealed Belgic Warbands in Aedui. Standing causes 2 Attack Losses and 2 Counterattack Losses from the four survivors. Retreat causes 1 Attack Loss and no Counterattack. Both satisfy section 8.6.2's additional-Battle condition; two Regions cost only 2 of 10 Resources.

**Observed:** Unmodified dispatch_bot_turn chooses Battle only at Carnutes in both Great Revolt and Ariovistus. execute_decision removes the Carnutes Ally, leaves all four Aedui and all six Belgic Warbands in Aedui, and leaves 9 Resources. The additional gate's legacy estimate is (2 inflicted, 3 taken), whereas predict_battle and direct live standing resolution both report (2, 2). Supplying the source-required second Battle to the same public executor succeeds, leaves two Aedui and four Belgic Warbands, and costs the second Resource.

**Cause:** A separate, still-active Aedui favorable-Battle consumer retains pre-Attack Counterattack arithmetic after other factions and Aedui's high-value trigger were repaired.

**Sources:** [Reference Documents/Chapter 8:448-462](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Chapter%208#L448); [Reference Documents/Chapter 3:277-300](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Chapter%203#L277).

**Implementation:** [fs_bot/bots/aedui_bot.py:202-219](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/bots/aedui_bot.py#L202); [fs_bot/bots/aedui_bot.py:625-647](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/bots/aedui_bot.py#L625).

**Controls:** Four defending Warbands: dispatcher includes the additional Battle; real Losses 2/1. Eight defending Warbands: dispatcher correctly omits additional Battle; standing Losses 2/3. Both standing and legal removal-only Retreat executed on detached valid copies for all three defender counts, in both scenarios. One Resource: only Carnutes executes even with the favorable four-defender control. Source-required complete two-Region plan executes through execute_decision with no errors.

**Earlier-audit distinction:** Original 50-item docs/human-choice-progress.json and comparative ledgers through round7 inspected. NP5-03 addressed German offense; NP6-01 addressed Belgic/Arverni offense; NP5-02 and NP6-02 addressed Aedui high-value entry conditions; NP5-01 addressed Diviciacus safety. NP7-01's new command-wide Ambush planner expressly covers Belgae, Arverni and Germans. None repairs this Aedui favorable/additional-Region consumer.

**Repair scope:** Use the shared surviving-defender combat forecast for Aedui's favorable additional-Battle predicate, preserving the Aedui-specific guarantee, possible Retreat, selected legal Ambush, single-Region Ambush limit, Diviciacus safety, and remaining Resource budget. The bounded witness requires no change to game rules or casualty mechanics.

**Fixture:** build_initial_state, seed 6; all active seats non-player; no Event; Command only; 10 Resources each; permanent Roman Fort in Provincia; two Revealed Aedui Warbands and named Belgic Carnutes Ally at Carnutes; four Revealed Aedui versus six Revealed Belgic Warbands in Aedui. All pieces placed through helpers.

**Limits:** Controlled positions, not sampled encounter frequency. No Leader, Legion, Fort in either Battle, Capability, Special Ability, human casualty choice, or saving roll enters the primary witness. Ambush and Capability interactions are repair considerations, not additional confirmed symptoms. These are valid constructed boards, not claimed untouched scenario setups.

**Evidence:** `bots/probe_bots.py`; `bots/probe_bots-output.json` in the portable archive. The original lane ledger preserves additional source annotations.

### NP8-02 — Aedui never reconsider an initially empty Special Ability after Rally enables Suborn

**Expected:** With no Aedui pieces on the map and 10 Resources, Rally places one Hidden Warband in the Aedui Home Region for 1 Resource. Section 8.6.3 then checks Trade/Suborn against the current board. Trade does not meet its threshold in this fixture, but Suborn can and must place the Aedui Ally and two Warbands for 4 more Resources. Expected final Aedui Region: one Ally, three Warbands, 5 Resources.

**Observed:** Unmodified public dispatch chooses Rally with No SA from the pre-Rally board. Public execution places only the home Warband, leaves the Tribe Subdued and 9 Resources, and reports no sa_execution. Immediately invoking the current ordinary SA chooser on that resulting state returns the required Suborn plan. A source-required execution control changes only the dispatched SA label to Suborn; the existing live rederivation itself selects and executes Ally plus two Warbands, producing the expected final counts and 5 Resources.

**Cause:** The live-state repair is gated by a nonempty provisional SA selection. A Command that creates the first qualifying Hidden Warband cannot reach that repair, because its earlier snapshot correctly had no eligible Suborn Region.

**Sources:** [Reference Documents/Chapter 8:469-502](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Chapter%208#L469); [Reference Documents/aedui_bot_flowchart.txt:100-106](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/aedui_bot_flowchart.txt#L100); [Reference Documents/Chapter 4:173-184](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/Reference%20Documents/Chapter%204#L173).

**Implementation:** [fs_bot/bots/aedui_bot.py:743-765](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/bots/aedui_bot.py#L743); [fs_bot/engine/execute.py:4760-4780](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/engine/execute.py#L4760); [fs_bot/bots/aedui_bot.py:1115-1155](https://github.com/FeeSimple1/fs-bot/blob/e62b0360c1b91032741ef8f6afa4d247c8ea2437/fs_bot/bots/aedui_bot.py#L1115).

**Controls:** Start with one Hidden Aedui home Warband: dispatch selects Suborn and existing live reevaluation executes after Rally, finishing with one Ally and four Warbands at 6 Resources. Command-only flag: the same empty-board Rally correctly adds no SA and the post-command chooser remains No SA. Start with only one Resource: Rally uses it and the post-command chooser correctly cannot Suborn. Identical initial board with the source-required Suborn SA label: actual executor derives and completes Ally+2 Warbands after Rally, with clean integrity and no errors.

**Earlier-audit distinction:** Original 50-item docs/human-choice-progress.json, comparative ledgers through round7, October outcome-audit report, and relevant October/November timing and Suborn repair summaries inspected. Earlier repairs rederive an already selected SA, enforce legal Suborn targets/limits, or expose human timing; this is the unhandled transition from no eligible pre-Command SA to a required post-Command opportunity. It is not NP7-02's Raid participant cap and does not reopen a human timing finding.

**Repair scope:** Forecast the post-Command SA opportunity, or carry a deferred NPC SA choice that is resolved at the printed timing even when the initial snapshot had No SA. Preserve true Command-only restrictions, the actual Sequence-of-Play action type, Britannia restrictions, existing Ambush commitments, Resource affordability, and human authored no-SA choices. Audit the same selection/empty-plan boundary without counting unproved sibling paths as findings.

**Fixture:** build_initial_state Great Revolt, seed 6; all active seats non-player; no Event; ordinary Command+SA allowed; 10 Resources each; no Aedui pieces; permanent Roman Fort in Provincia. Physical placements and pre/post census/structure use canonical helpers and validators.

**Limits:** Confirmed for ordinary base-game Aedui Rally in a controlled legal position. No blanket claim about every faction, March/Raid, expansion Leader range, Events, or human SA choice. Source-required execution control explicitly supplies an SA label; the unmodified dispatcher witness alone is the reported bug. No encounter-rate or balance claim.

**Evidence:** `bots/probe_bots.py`; `bots/probe_bots-output.json` in the portable archive. The original lane ledger preserves additional source annotations.

## Reproduction and exclusions

Extract the evidence archive, then run `python run_witnesses.py --repo /path/to/fs-bot` using the audited Python sources. The runner verifies the exact source digest, repeats each witness at both hash seeds in temporary directories, and checks the preserved output. These assertions deliberately describe the defects and should fail after their repair. `SHA256SUMS` covers archive files; validation logs and independent reviews are included.

No additional Elite, virtual-force, alternate empty-SA, or speculative Event-priority issue was promoted without a lawful public witness. Existing Optimates, Elite-designation and other recorded source questions remain separate. Winter Campaign coverage is the real after-Harvest consumer with saved SeatSession/transaction/replay, not a claim of terminal-menu reachability. No new source ruling was required.
