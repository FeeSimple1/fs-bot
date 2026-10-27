# Build plan and maintenance roadmap

Updated 27 October 2026. The original pre-implementation plan is retained in
Git history. The engine now has implementations for all eight original build
phases; those phase labels are an architectural map, not a list of unbuilt
features or a certification that every rule interaction is correct.

Start with [current engineering status](docs/current-status.md) for corrected
behavior and adopted provisional rulings, and the
[27 October second-batch report](docs/reviews/second-batch-2026-10-27.md)
for the latest Event-choice repairs and their validation status. The earlier
[23 October validation report](docs/reviews/outstanding-fixes-2026-10-23.md)
retains its exact tested revision and reproducible results. Use
[PLAYING.md](PLAYING.md) for terminal play and
[AGENT_INTERFACE.md](AGENT_INTERFACE.md) for external controllers.

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

The follow-up implementation adds Diviciacus cooperation and its optional
original-scenario setup, repairs strategy-runner acceptance/resume, exposes
edition matrices, expands real terminal journeys, and adds local packaging
and historical save fixtures. These are now implemented maintenance items;
the [current status](docs/current-status.md#follow-up-repairs) distinguishes
them from the older validation checkpoint above.

1. **Revisit the six provisional rulings if authoritative answers are found.**
   The owner adopted [PR-01 through PR-06](docs/provisional-rulings.md) on
   24 October 2026. These govern A30's Belgic cue, A28 lending by both
   non-player factions, unused A53 funding, German-owned A63 after Interlude,
   Arverni-last Harassment, and the preceding Event's order during Winter.
   Each is subject to possible later correction if an authoritative source
   is found. [QUESTIONS.md](QUESTIONS.md) retains the source conflicts;
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
