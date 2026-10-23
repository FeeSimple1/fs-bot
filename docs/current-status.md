# Current engineering status

This document supersedes older completion claims in `QUESTIONS.md` and the
build plan. It distinguishes verified engineering fixes from unresolved
source conflicts. The historical audit reports retain their original results;
their game outcomes are not a baseline for a later rules revision.

## Corrections in this review

| Area | Corrected behavior | Regression coverage |
|---|---|---|
| Human decisions | Current/upcoming card text and changes are shown before decisions; `board` is available at prompts. Commands and Special Abilities can be selected in either order, including scoped Event grants. | `test_turn_visibility.py`, `test_human_action_order.py`, `test_cli_free_actions.py` |
| Card editions | Saved original, Second Edition, or legacy profile consistently controls cards 11/30/39/44/54. Revised Vercingetorix's Elite and River Commerce use their printed limits/effects. | `test_card_edition.py` |
| Marcus Antonius (6) | Romans choose optional Scout and Battle separately, even when another faction plays the Event. Battle keeps the doubled-Auxilia bonus and normal capability effects; bots decline the whole Event when neither action can have an effect. | `test_marcus_antonius.py` |
| Morasses (36), shaded | Humans choose the Gallic beneficiary, Battle plan and March, including in-place hiding. Belgae target Romans then Gauls where Losses are possible and then hide in place. Aedui retain their one-Region Ambush limit. Actual Command capabilities, pre-fire and Frost outcomes are checked; wholly ineffective Events are declined before selection. | `test_morasses.py`, `test_morasses_decisions.py` |
| Joined Ranks (54) | Optional March respects distance and eight-piece limit, including Leaders. Battles use the same defender; a second human faction chooses whether to participate, and a second non-player faction does not Battle. | `test_joined_ranks_choices.py` |
| Dumnorix (44) | Replacements respect counts and owners; Scout/Raid uses only the newly placed cohort. Revised free Commands stay in placement Regions. | `test_dumnorix.py` |
| Impetuosity (72), shaded | Humans choose one original Hidden Warband group for an adjacent or in-place March and separately choose optional Battle with that group alone. Bots respect player targets, physical Control, Frost and the Belgic Leader’s post-Battle escort. The one-use grant cannot leak into later Events. | `test_impetuosity.py`, `test_impetuosity_decisions.py`, `test_cli_impetuosity.py`, `test_free_action_lifetime.py` |
| Impetuosity (72), unshaded | Humans choose groups from adjacent origins to one destination, then the eligible Arverni or Belgic attacker. March is mandatory when possible. Romans apply their printed March priorities before checking for the resulting Battle, and decline the Event before selection when instructed. | `test_impetuosity_unshaded.py` |
| Resources | Normal Battles pay their printed costs. Free Event actions waive costs and include a Special Ability only when granted. | `test_free_action_costs.py` |
| Arverni Battle timing | Non-player Battles are paid before Devastate/Entreat, as instructed by §8.7.1; the accompanying ability cannot spend those reserved Resources. | `test_arverni_battle_payment.py` |
| Raid | Bots exhaust each target priority before moving to the next. Steals require sufficient victim Resources and validate the complete Region plan before revealing pieces. | `test_raid_priority_regressions.py` |
| Raid Intimidate | Ariovistus’s actual Raiders can free Intimidate as part of Raid, independently of an accompanying Special Ability. Human choices support decline, marker-only, removals, pause/save/replay, and exact Raider credit; Card 8 can use its third Raider. | `test_raid_intimidate.py`, `test_raid_intimidate_decisions.py`, `test_cli_raid_counts.py` |
| Acco (34) and Britannia (57) | Human beneficiaries choose free actions. Acco applies its Control/Devastated exceptions and Region limit; Britannia resolves its optional scoped Special Ability and checks the Resource bonus afterward. | `test_event_free_choices.py` |
| Enlist | Borrowed German Warbands retain physical ownership through movement, control, actions and losses. Both Enlist options respect base/expansion restrictions. | `test_enlist_borrowed.py`, `test_enlist_free.py` |
| Human movement menus | March can split an origin into multiple groups, include a remaining Leader, and plan full Roman/Vercingetorix routes. Subsets recheck Leader range, Alps and Abatis stops; previewing does not roll future Harassment. Base German Rally offers its Ally-then-Warbands sequence. | `test_cli_march_groups.py`, `test_cli_march_routes.py`, `test_migration.py` |
| Marching piece choices | Humans choose the actual Hidden/Revealed pieces when forming a subset or leaving pieces behind. Split groups flip an origin only once per Command. Divination's chosen player controls German piece selection while physical ownership stays German; previews do not prompt or change the live board. | `test_march_visibility_choices.py` |
| Scoped bot planning | Event Region limits are applied before target selection and piece allocation. Each faction follows its own Command branches and exclusions; German Settlement placement can create legal placement chains. | `test_free_flowchart_scope.py`, `test_roman_german_command_scope.py` |
| Movement and Rally | Normal March distance is checked before spending/flipping. Rally respects faction- and scenario-specific option limits, including Vercingetorix’s exception and base German Ally-then-Warbands placement; German home bonuses execute. Free Enlist Marches respect Event Region limits, cost waivers, and the Frost exception. | `test_march.py`, `test_rally_prevalidation.py`, `test_free_enlisted_march.py` |
| Admagetobriga (A28) | All selected eligible Regions resolve. Combined Warbands/Auxilia retain ownership through loss calculations, casualties, and Reveal; humans choose targets and consent. Non-player Romans refuse as specified. | `test_admagetobriga.py` |
| Divination (A34) | A chosen beneficiary commands the actual German force, choosing March or Battle in/from up to three Regions. Bots use their own strategic priorities with German movement and Battle mechanics; Frost checks possible outcomes. | `test_divination.py`, `test_divination_np.py`, `test_divination_frost.py` |
| Publius Licinius Crassus (A17) | Romans form the printed Legion/Auxilia group, then choose a legal route, drop-offs, and Battle at the Caesar-free destination. Real March handles Harassment and partial execution; a destroyed group cannot redirect Battle into its transit Region. Bots apply March priorities within legal origins and destinations. Auxilia receive the printed Battle bonus. | `test_publius.py` |
| March after Harassment | Actual losses are applied to the carried group once. A visibility ledger prevents residents from replacing departing pieces. Drop-offs remain behind, surviving pieces continue, and losing Caesar or Vercingetorix removes the extra movement they grant. A successful Leader saving roll no longer removes that Leader from the moving group. | `test_publius.py`, `test_march_cohort.py` |
| Harassment decisions and order | Humans choose soft casualties or a die roll, then the required hard casualty on a failed roll. Visibility and exact Allied tribes are selectable. Later harassers see prior losses; base-game announcements during Event-card turns follow card order then Germans. Roman Hidden Auxilia and Ariovistus German bots now Harass when instructed. Game-run factions cannot be prompted to waive mandatory Harassment. | `test_harassment_decisions.py` |
| Battle outcome prediction | Independent human Retreat agreements retain their own Region and response history. The shared predictor checks the complete Battle Command and rejects an empty outcome set, preventing an unsafe Frost action from passing without any simulated outcomes. | `test_divination_frost.py`, `test_impetuosity_unshaded.py` |
| Gallia Togata (5/A5) | The actual marker governs geography and Roman-only stacking. March, Recruit and Alps effects follow the selected card, including lingering A5 effects after Interlude and save/load. | `test_gallia_map.py` |
| Arduenna (A67) | German forces gather the safe surplus from controlled origins, account for departing Leaders and all opposition, and choose a target where Control is achievable. | `test_arduenna_surplus.py` |
| War Fleet (62) | All four non-player factions derive the printed coastal relocations and follow-on Command. Arverni Battle the selected player target; Roman distribution respects origin, Legion/Leader and final-force priorities. Availability and Frost checks preview the complete actual Command, including capabilities and human outcomes. | `test_war_fleet.py`, `test_war_fleet_roman.py` |
| Kinship (A65) | A human Event executor chooses Belgae or Germans to Battle in any selected legal Regions. One Command applies its limits once, without costs or an accompanying ability. The attacker’s Leader remains physically present but does not fight or absorb losses. Non-players obey the beneficiary and opposing-player restrictions before choosing the Event. | `test_kinship.py`, `test_kinship_decisions.py` |
| Migration (66) | The executing player chooses real German Rally and March separately, each limited to two Regions/origins. Roman bots follow the printed movement instructions and maximize Rally placement. | `test_migration.py` |
| Frumentum (A53) | Aedui specify funding; Romans choose paid Recruit, March and one Special Ability in any order. Roman personal funds are reserved, and non-player funding follows A8.6.6. | `test_frumentum.py` |
| Savage Dictates and Intimidate | A45 waives only its printed Leader/Control restrictions. Targets follow non-player priorities, retain the one-Faction/two-Warband limits, and validate all removals before changing pieces. | `test_intimidate_grants.py` |
| Harudes (A29) and Bellovaci (A69) | Harudes Raids use the newly placed Warbands and respect the Settlement limit. Bellovaci checks Ambush legality and gives its attack bonus only to newly placed Warbands. | `test_nested_event_rules.py` |
| Successor and Litaviccus (45) | Threat March uses the actual Leader’s movement allowance. Pooled Aedui Warbands count for Ambush strength without bypassing Leader range; ordinary Battle remains available when Ambush is not. | `test_census_planner_regressions.py` |
| Winter Uprising and Interlude | The Interlude executes Uprising and Winter Campaign before changing Forces and scenario. Forced Arverni phases handle an empty target set; Aedui/Belgic A63 ownership remains effective afterward. | `test_winter_uprising_regressions.py` |
| Winter Campaign | Humans can take up to two paid actions, including standalone Special Abilities. A63 records and activates its proper owner. Bot plans honor the remaining action budget before selecting dependent actions such as Settle/Rally. After-Harvest Harassment no longer tries to look up the Winter marker as an Event. | `test_winter_campaign_decisions.py`, `test_winter_harassment_order.py` |
| Quarters | All human factions choose relocations and payments. Complete adjacent relocation groups are validated against pre-step Control, and original visibility is preserved so arrivals cannot move again. Supply Lines use the resulting board. Invalid destinations, static-piece movement and negative payments are rejected; losses apply to the actual unpaid pieces. | `test_quarters_decisions.py`, `test_quarters_relocation_step.py` |
| Saves | Production loading validates board structure and pending-turn cursors before resuming, with readable errors for malformed saves. | `test_save_validation.py` |
| Human replay | Default reactive responses are recorded. Actual terminal games from every playable seat replay to the same final state. | `test_cli_playthroughs.py` |
| Morbihan display | During A20’s “as if there” Ambush, human loss choices show physical Arverni Warband origins and actual Roman losses, with the temporary battle calculation identified separately. | `test_morbihan_display.py` |
| Borrowed-force display | Board views and per-seat changes show physical ownership during Enlist and Admagetobriga; active borrowed forces are identified separately. Actual Control, losses, and piece visibility remain visible. | `test_borrowed_force_display.py` |
| Assistant play | Human reactions pause explicitly; a single saved session records inbox consumption, pending decisions and prior choices. Resume/replay does not silently choose or reroll earlier responses. | `test_assistant_session.py` |
| Game diagnostics | The census inspects nested Event grants, Winter Campaign, and game-run Winter phases. Explicit declines remain distinct from rejected actions; duplicate result aliases do not inflate counts. | `test_census_nested_actions.py` |
| Event instructions and effects | Actor-specific target checks, mandatory piece types and scope, missing Gobannitio/Correus plans, and local optional declines are corrected. Aedui use the printed shaded-text instruction group from each scenario’s own table; Remi’s condition and City/Remi loss priorities apply in the proper scenarios. | `test_event_grant_outcomes.py` |
| All Gaul Gathers (A37) | Humans choose scoped Ally placements and direct movement of their Leader/Warbands/Auxilia, with all choices validated before mutation. Eligibility uses the pre-Event board. Non-player Aedui maximize their Ally placements and move no pieces; ineffective and out-of-scope Events are declined before selection. | `test_all_gaul_gathers_np.py`, `test_all_gaul_gathers_choices.py` |
| Correus (64) validation | Shaded human choices must remove the required number of distinct eligible Allies before optional placement or Rally; invalid choices roll back. | `test_event_grant_outcomes.py` |
| Balance checks | All five scenarios and all eligible winners are covered; missing baseline games fail explicitly. Exact threshold comparisons avoid rejecting an allowed 15% change because of floating-point rounding. | `test_balance_guardrail_coverage.py` |
| Event selection | Non-players check actual eligible targets and the supplied instructions before choosing Mons Cevenna, Assembly of Gaul, or Sabis. | `test_event_conditional_declines.py` |

## Source conflicts still open

1. **A30 Orgetorix:** the Vassal card face shows Belgic laurels, while the
   supplied Belgic Event instructions contain no corresponding instruction.
   An icon does not establish the missing targeting or No Event rule. The
   implementation retains the supplied behavior pending an authoritative
   instruction or correction of the icon.
2. **A8.6.6 and A28 agreements:** the heading names non-player Aedui, while
   the body names non-player Belgae. Applying that policy to both factions
   would invent a ruling. The unambiguous Roman refusal, human choices and
   combined-force mechanics are implemented independently of this conflict.
3. **A53 Frumentum's unused human allocation:** the card says Romans may
   spend an amount specified by the Aedui, while the non-player instruction
   explicitly describes a transfer. The human text does not settle who
   retains an unspent allocation. The existing disposition (Romans retain
   the unused transferred amount) remains a documented legacy policy;
   it is not presented as a new source-derived ruling.

4. **German-owned A63 after the Interlude:** the sources transfer the player
   seat to Arverni but preserve Germanic capabilities in place. They do not
   specify whether ownership of this neutral benefit follows the player or
   how the now game-run Germans use its paid actions. Existing ownership and
   non-activation are preserved; the clear Aedui/Belgic carry-over is fixed.
5. **Ariovistus Harassment order:** playable Germans acquire a card-order
   position, while automatic Arverni Harassment has no stated insertion
   point. The base game's card-order-then-Germans rule is fixed; expansion
   timing retains the existing fixed faction order pending clarification.
   Eligibility, casualty choices and sequential resolution are corrected
   independently.

6. **Winter Campaign Harassment order:** Card 63/A63 allows actions after
   Harvest, when the current Winter card has no faction symbols. The
   references do not specify a substitute order. The lookup crash is fixed;
   the existing fixed faction order is preserved pending clarification.

These are source questions, not reasons to silently substitute a preferred
strategy. Protected references and `rules_consts.py` are unchanged.

## Verification and limits

The [23 October validation report](reviews/outstanding-fixes-2026-10-23.md)
records the tested revision, completed checks, outcome statistics, and
reproducible evidence. Its accepted batch contains 1,000 completed bot
games across all five scenarios, with no crashes, rejected actions, or
integrity/ranking/hash findings. The local full suite has 4,067 passing
tests. Read the report for the exact scope of determinism and mixed-seat
checks and the separate remote CI results.

The full-game terminal tests exercise real menus, invalid input, the `board`
command, Commands and exact replay across all twenty scenario/seat pairs.
They are functional journeys, not evidence of expert human strategy, and do
not by themselves guarantee that a Gallic War game reaches the Interlude.
Dedicated tests cover the transition separately.

Seeded bot games and mixed-seat fuzzing complement source-derived rule tests.
A clean run demonstrates the tested paths and seeds, not proof that every
published rule is correct. Win-rate baselines are refreshed only after
explaining rules-driven changes; no bot priorities are tuned to obtain
preferred faction win rates.

The CI matrix covers Ubuntu Python 3.10/3.12, Windows Python 3.12 and macOS
Python 3.12. Linux also runs synchronization, nested Event/Winter census, mixed-seat
determinism and balance checks. Local results and remote CI results must be reported
separately.
