# Build plan and maintenance roadmap

Updated 4 November 2026. The original pre-implementation plan is retained in
Git history. The engine now has implementations for all eight original build
phases; those phase labels are an architectural map, not a list of unbuilt
features or a certification that every rule interaction is correct.

Start with [current engineering status](docs/current-status.md) for corrected
behavior and adopted provisional rulings. The
[human-choice audit](docs/reviews/human-choice-audit-2026-10-29.md) now defines
the open repair backlog and its evidence limits. Consult the
[Recruit/Rally report](docs/reviews/recruit-rally-2026-10-29.md)
for the latest placement repairs and their validation status. The earlier
[23 October validation report](docs/reviews/outstanding-fixes-2026-10-23.md)
retains its exact tested revision and reproducible results. Use
[PLAYING.md](PLAYING.md) for terminal play and
[AGENT_INTERFACE.md](AGENT_INTERFACE.md) for external controllers.

The [4 November Build repair](docs/reviews/build-order-2026-11-04.md) closes
CMD-BUILD-ORDER with explicit player Region order, preserving NP passes and
legacy controller plans. At that checkpoint the original bundle was 26/50 closed (52%), 24 open.

The [4 November March stay repair](docs/reviews/march-stay-2026-11-04.md)
closes MARCH-HIDE-IN-PLACE: explicit empty routes select paid origins for their
visibility procedure without movement. At that checkpoint original progress was 27/50
closed (54%), 23 open.

The [4 November Besiege repair](docs/reviews/besiege-choice-2026-11-04.md)
closes BATTLE-BESIEGE-CHOICE with exact Roman physical targets, decline,
terminal/durable requests and replay. At that checkpoint original progress was 28/50 closed
(56%), 22 open.

The [4 November Harvest repair](docs/reviews/harvest-legions-2026-11-04.md)
closes WS-F03 with exact Belgica allocations and repairs positive post-Interlude
reserves remaining stranded. At that checkpoint original progress was 29/50 closed (58%),
21 open; Interlude expedition ownership itself remains WS-F02.

The [4 November Gallic Shouts peek repair](docs/reviews/gallic-shouts-peek-2026-11-04.md)
closes BE-10 with Roman-owned private card data before the benefit decision.
At that checkpoint original progress was 30/50 closed (60%), 20 open.

The [4 November Devastate repair](docs/reviews/devastate-losses-2026-11-04.md)
closes CMD-DEVASTATE-LOSSES with exact physical-owner casualty requests,
whole-plan validation and source-correct default visibility priorities.
At that checkpoint original progress was 31/50 closed (62%), 19 open.

The [4 November Quarters repair](docs/reviews/quarters-visibility-2026-11-04.md)
closes WS-F05 with exact visibility cohorts for adjacent and Provincia moves,
terminal/durable support, original-piece capacity and continuation validation.
At that checkpoint original progress was 32/50 closed (64%), 18 open.

The [4 November expansion quantity batch](docs/reviews/expansion-up-to-2026-11-04.md)
closes EXP-08 with executor-owned A40S/A51U/A60U live choices, exact physical
removals, zero quantities, actual-placement compensation and durable replay.
At that checkpoint original progress was 33/50 closed (66%), 17 open.

The [4 November Drought batch](docs/reviews/drought-losses-2026-11-04.md)
closes BE-05 with physical-owner casualties, exact Tribes/visibility/Leaders,
source-correct default losses and durable later-Region replay. Drought's part
of BE-08 is repaired; its other generated-schema defects remain open.
At that checkpoint original progress was 34/50 closed (68%), 16 open.

The [4 November Scout repair](docs/reviews/scout-allocations-2026-11-04.md)
closes CMD-SCOUT-ALLOCATION with shared Auxilia capacity across exact factions
and visibility cohorts, physical-owner choices and atomic grouped execution.
At that checkpoint original progress was 35/50 closed (70%), 15 open.

The [4 November Roman Interlude repair](docs/reviews/interlude-roman-choices-2026-11-04.md)
closes WS-F02 with exact expedition forces and marker preservation, including
transactional Winter retries. At that checkpoint original progress was 36/50 closed (72%), 14 open.

The [4 November Battle casualty identity repair](docs/reviews/battle-loss-identity-2026-11-04.md)
closes BATTLE-LOSS-IDENTITY with exact ordinary visibility and named Ally discs.
At that checkpoint original progress was 37/50 closed (74%), 13 open.

The [4 November Rampage victim repair](docs/reviews/rampage-victims-2026-11-04.md) closes
BATTLE-RAMPAGE-VICTIM with exact pieces and mixed dispositions.
Current original progress is 38/50 closed (76%), 12 open.

## Existing implementation

| Original phase | Implemented components | Main locations |
|---|---|---|
| 0 — Foundation | Canonical labels, development requirements, and decision ledger | `fs_bot/rules_consts.py`, [CLAUDE.md](CLAUDE.md), [QUESTIONS.md](QUESTIONS.md) |
| 1 — Map, state, and pieces | Board topology, piece operations, Control, five scenario setups, validation, saves | `fs_bot/board/`, `fs_bot/state/` |
| 2 — Cards and deck | Card metadata/text, effects, capabilities, bot instructions, deck construction, saved edition selection | `fs_bot/cards/`, `fs_bot/state/setup.py` |
| 3 — Commands, Special Abilities, and Battle | Shared action execution, actual movement cohorts, costs, Battle resolution, borrowed pieces, and human reactions | `fs_bot/commands/`, `fs_bot/battle/`, `fs_bot/engine/execute.py` |
| 4 — Game engine, Winter, and victory | Sequence of Play, pending actions, Winter/Quarters, Winter Campaign, victory and rankings | `fs_bot/engine/game_engine.py`, `winter.py`, `quarters.py`, `winter_campaign.py`, `victory.py` in that directory |
| 5 — Bot flowcharts | Scenario-dependent Roman, Arverni, Aedui, Belgic, and German bots, plus shared priorities | `fs_bot/bots/` |
| 6 — Human interfaces | Terminal menus, card/board/delta display, either action order, scoped Event decisions, persistent assistant sessions and replay | `fs_bot/cli/`, `fs_bot/tools/llm_seat.py`, `fs_bot/tools/seat_session.py` |
| 7 — Ariovistus and the Gallic War | Expansion setup, German player/bot and game-run Arverni roles, expansion cards, Interlude and seat transition | `fs_bot/state/setup.py`, `fs_bot/engine/arverni_phase.py`, `fs_bot/engine/interlude.py`, scenario branches in the shared modules |

The current sources and interfaces supersede the old plan's speculative rule
summaries. Consult the supplied rules for faction abilities, costs, Winter
ordering, and card composition; do not implement rules from a roadmap table.
The protected references and canonical constants remain read-only.

## Follow-up verified checkpoint

The 24 October source snapshot passes 4,431 tests, 2,500 audited bot games
across all scenarios and three card-edition profiles, 90 optional-Diviciacus
games, 75 bot hash-seed repeats, and 1,000 mixed-seat game executions with
replay. Strict nested census, baseline checks, strategy-runner smoke and
isolated installation checks pass. The
[follow-up report](docs/reviews/followup-repairs-2026-10-24.md) records the
source digest, detailed counts, failed attempts and separate remote CI status.

## Earlier verified checkpoint

The 23 October review tested source commit
`c7264cb3d2afbf08ccfce140af6e03b0f17138ae` and recorded:

- 4,067 passing local tests, plus all eight remote CI jobs for that revision.
- 1,000 completed bot-only games, 200 per scenario, with no crashes,
  rejected-action diagnostics, integrity findings, or ranking/hash failures.
- 25 bot games repeated across hash seeds with matching results; 200
  mixed-seat cases per hash seed with replay, matching outputs and zero hard
  findings; two matching 100-game strict censuses.
- A reviewed 100-game balance baseline using seeds 1–20 in all five
  scenarios, retaining the 15-percentage-point drift threshold.

The report preserves the failing earlier runs as well as the accepted run.
Both checkpoints predate the later adoption of PR-01 through PR-06.
These checks establish the tested positions and paths. They do not establish
exhaustive rules compliance or human-game balance. New code revisions need
their own relevant checks; old counts must not be relabeled as new evidence.

## Continuing work

The 29 October Recruit/Rally batch closes optional quantities and the
combined Vercingetorix Rally menu. The subsequent
[action-timing repair](docs/reviews/action-timing-2026-10-29.md) adds voluntary
own-piece reclamation, mid-action Vercingetorix entry, and a Special Ability
between his two Rally options in one Region. The subsequent
[human-choice audit](docs/reviews/human-choice-audit-2026-10-29.md) records
50 grouped open findings across 490 inventory rows. It changes no engine
behavior. Its six repair batches cover core validation/setup, mandatory
Event effects, correct human grant ownership, exact ordinary choices and
timing, seasonal decisions, and optional setup/shared-player support.
The [first small repair batch](docs/reviews/cheap-fixes-2026-10-29.md) closes
Battle casualty tiers, repeated Seize/Entreat Regions, strict Supply responses,
expansion Arverni transfer rejection and sole-human-Belgae setup. The
[Scouted Event repair](docs/reviews/scouted-events-2026-11-02.md) closes EXP-12.
The [expansion Event-grant batch](docs/reviews/human-event-grants-2026-11-02.md)
closes EXP-01 through EXP-06. The
[Gallia Togata and Dread repair](docs/reviews/expansion-effects-2026-11-02.md)
closes EXP-07 and EXP-10. The
[Event validation batch](docs/reviews/event-validation-2026-11-03.md) closes
BE-11, BE-12 and EXP-09, completing the audit's mandatory-Event/illegal-plan
repair group. The [progress register](docs/human-choice-progress.json)
now records 38 of 50 closed (76%) and 12 open; these are finding counts, not
equal effort units. The [planning-board inspection repair](docs/reviews/planning-board-inspection-2026-11-03.md) closes FE-01. The [named-faction Event repair](docs/reviews/named-event-effects-2026-11-02.md) closes BE-04
(Roman and Arverni optional effects, plus related A18 removal corrections).
The [Colony follow-up](docs/reviews/colony-event-defaults-2026-11-02.md)
repairs dynamic Tribe geography in expansion defaults and detects rejected
bot Events during mixed-seat validation; it closes no extra original finding.
The [Gallic Event repair](docs/reviews/gallic-event-grants-2026-11-02.md)
closes BE-03: beneficiary/order decisions, correct Remi ownership and the
owner-adopted PR-10/PR-11 automatic policies are implemented and validated.
The [ordinary Arverni Phase repair](docs/reviews/arverni-phase-2026-11-03.md)
fixes all five additional follow-up defects and two related errors in protected
Tribe placement and Resource accounting. These remain separate from the
original audit findings; its denominator stays 50.
The [Event Battle repair](docs/reviews/event-battle-choices-2026-11-03.md)
closes BE-02, including printed participants and Event Loss modifiers in
Retreat forecasts. The subsequent
[Litaviccus follow-up](docs/reviews/litaviccus-targeting-2026-11-03.md)
implements adopted PR-12 targeting and repairs full Aedui Battle participation;
these remain separate from the original audit denominator.
The [Camulogenus repair](docs/reviews/camulogenus-2026-11-03.md) completes
numeric 70's Roman acceptance and March planning. BE-01
is now closed after the [Circumvallation choice repair](docs/reviews/circumvallation-2026-11-04.md); numeric 67 was repaired in the Gallic Event batch.
The [Mons Cevenna repair](docs/reviews/mons-cevenna-2026-11-03.md) restores
numeric 9's human first March and restricts the follow-on to its destination.
The [Aduatuca repair](docs/reviews/aduatuca-2026-11-04.md) restores numeric58's
executor-owned German March and Fort choices.
The [German guidance repair](docs/reviews/german-guidance-2026-11-04.md) restores
numeric65's executor-owned German March and all-able Ambush choices.
The [Germanic Chieftains repair](docs/reviews/germanic-chieftains-2026-11-04.md)
restores numeric17's Roman-owned German groups and single Ambush.
The [no-Romans cleanup repair](docs/reviews/circumvallation-no-romans-2026-11-04.md)
repairs one marker boundary. The [Intimidate Tribe repair](docs/reviews/intimidate-tribes-2026-11-04.md)
closes CMD-INTIMIDATE-TRIBE and makes those removals identify their physical
discs; it does not implement persistent marked-group tracking. The
[Rampage quantity repair](docs/reviews/rampage-quantity-2026-11-04.md) closes
CMD-RAMPAGE-COUNT and removes the artificial NPC two-Warband cap. The
[physical victim repair](docs/reviews/rampage-victims-2026-11-04.md) closes
BATTLE-RAMPAGE-VICTIM with owner-selected pieces and mixed dispositions. The [Seize Tribe repair](docs/reviews/seize-tribes-2026-11-04.md)
closes CMD-SEIZE-TRIBES and shares exact ordinary/Event dispersal contracts.
Next address the remaining [Circumvallation persistent-effect defects](docs/reviews/circumvallation-persistence-followup-2026-11-04.md).
Continue with the remaining Event ownership, quantity
and exact-choice findings, then ordinary physical choices/timing and
seasonal ownership. Base-card counterparts remain separate findings even
where an expansion card now has complete menus. Optional setup and shared
player modes remain separately scoped. An additional NPC audit lead concerns
pre-Battle Intimidate excluding the whole defender faction instead of only
guaranteed Battle losses. It needs a combat-projection witness and is tracked
separately from the original 50 findings; it is not claimed repaired.
Preserve each source-derived witness as a desired-behavior regression during
repair. The
[29 October rules and Trade repair](docs/reviews/rulings-trade-2026-10-29.md)
closes human selection of Trade's single Region under shaded River Commerce.
The [Recruit/Rally report](docs/reviews/recruit-rally-2026-10-29.md) retains
its placement scope and then-unresolved timing questions; the later rules
and Trade report records their adopted provisional answers. These known
items are not an exhaustive defect list. Two unadopted non-player source
questions remain: shaded Trade Region selection and the physical Warbands
designated by Vercingetorix's Elite. Litaviccus's response forecast now follows
PR-12, subject to authoritative correction. See the current question index.

The follow-up implementation adds Diviciacus cooperation and its optional
original-scenario setup, repairs strategy-runner acceptance/resume, exposes
edition matrices, expands real terminal journeys, and adds local packaging
and historical save fixtures. These are now implemented maintenance items;
the [current status](docs/current-status.md#follow-up-repairs) distinguishes
them from the older validation checkpoint above.

1. **Revisit the provisional rulings if authoritative answers are found.**
   The owner adopted [PR-01 through PR-06](docs/provisional-rulings.md) on
   24 October 2026. These govern A30's Belgic cue, A28 lending by both
   non-player factions, unused A53 funding, German-owned A63 after Interlude,
   Arverni-last Harassment, and the preceding Event's order during Winter.
   PR-07 through PR-09 were adopted on 29 October for Aedui Supply dice,
   placement-bonus timing, and A20 casualty origins. PR-10/PR-11 were adopted
   on 2 November for automatic Arverni Event Commands and numeric Arduenna
   predictions. PR-12 was adopted on 3 November for Litaviccus's human
   Roman response forecast. Each is subject to
   possible later correction if an authoritative source is found. [QUESTIONS.md](QUESTIONS.md) retains the source conflicts;
   they are not current implementation blockers or designer-confirmed rules.
2. **Extend position and interaction coverage as defects or gaps are found.**
   Prioritize multiple-faction human decisions, scoped Event combinations,
   physical piece ownership/visibility, and interruptions within Winter or
   Interlude. Preserve the failing seed or minimal position before a fix,
   add a source-derived regression, and rerun affected scenarios and editions.
   The runners and CI now support held-out seeds and explicit edition
   matrices. Record actual results for the tested revision; configured
   coverage alone is not evidence that a run passed.
3. **Keep the human interface reviewable.** Validate full card information,
   per-seat changes, `board`, all legal choices, exact decision ownership, and
   save/resume/replay whenever a new action or reaction is added. A passing
   bot-only batch does not cover choices a human never received.
4. **Maintain reproducible validation and release evidence.** Preserve source
   revision/digest, scenario, edition, seats, seeds, commands, exit status and
   raw findings. Maintain fresh-environment installation/play and the archived
   saved-game compatibility fixtures for each release. Treat the scheduled deep-soak workflow as
   configured coverage; verify its run and artifacts before claiming it passed
   on a particular revision.
5. **Re-evaluate strategy separately from rules fidelity.** Historic heuristic
   results may no longer describe the corrected engine. Use the
   [self-play playbook](SELFPLAY_PLAYBOOK.md) for new measured comparisons.
   Diagnose outcome drift against the rules before refreshing a baseline;
   never change bot priorities or widen tolerances to obtain preferred wins.

## Maintenance requirements

[CLAUDE.md](CLAUDE.md) governs implementation and source handling. In particular:

- Keep `Reference Documents/**` and `fs_bot/rules_consts.py` unchanged.
  A specifically authorized external comparison does not make that source a
  substitute for the supplied rules or authorize broader research.
- If the sources are ambiguous, record the exact question and alternatives,
  leave that issue unresolved, and continue independent work unless an
  expressly adopted owner ruling already covers it.
- Use canonical labels, piece helpers, and seeded game RNG. Check both sides
  of scenario-dependent behavior, including after the Gallic War Interlude.
- Add a regression for each bug and run the full suite before every commit.
  Use the existing `run_batch`, `error_census`, `player_fuzz`, `sync_check`,
  and `balance_smoke` tools for the changes they exercise; detailed commands
  and acceptance criteria belong in the validation report and playbook.
- Keep historical reports tied to their original revisions. Add a dated
  supersession note when later work changes an outcome or resolves a question;
  retain the original measurements and failed-run evidence.
