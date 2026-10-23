# Self-play and outcome validation — Falling Sky

Use this workflow to investigate rules defects and compare explicitly defined
experimental policies. Start with [current status](docs/current-status.md) and
the [23 October 2026 validation report](docs/reviews/outstanding-fixes-2026-10-23.md).
The [strategy notes](selfplay-strategy-notes.md) preserve earlier studies; their
win rates and strategic interpretations do not describe the corrected engine.
See the [documentation index](docs/README.md) for the other project guides.

Follow [CLAUDE.md](CLAUDE.md): `Reference Documents/**` and
`fs_bot/rules_consts.py` are read-only. Rules corrections must follow those
sources. An unresolved rule goes into `QUESTIONS.md`; continue independent
work without inventing a ruling. This playbook does not authorize new external
research or access to other game repositories. The earlier Vassal comparison
was a separately authorized review, documented in its own report.

## Existing tools and their scope

These entry points already exist. Check their `--help` and implementation
before extending them.

| Tool | Purpose | Important limit |
|---|---|---|
| `fs_bot.tools.run_batch` | Audited zero-human outcomes across all five scenarios; JSONL records, summary, revision and source digest | `--games N` means N **per scenario**. Requires hash seed 0; overwrites its output files and does not resume. Exit 0 alone does not certify clean diagnostics or complete engine rankings. |
| `fs_bot.tools.error_census` | Classifies nested Command, Event and Winter results | Use `--strict`; inspect all severities, including `other-refused`. `legal-decline` is allowed. |
| `fs_bot.tools.player_fuzz` | Mixed human/bot seats, randomized reactions and Event parameters, preview/live checks, replay | Leave reactions, Events and determinism enabled. Randomly generated partial or refused plans are separate from hard engine findings. |
| `fs_bot.tools.sync_check` | Tribe/piece synchronization across complete games | Select a scenario explicitly; its default is only Reconquest. |
| `fs_bot.tools.balance_smoke` | Fixed-seed winner-rate drift against the reviewed baseline | A passing rate check is not a rule-compliance proof and does not require every individual winner to stay unchanged. |
| `fs_bot.tools.play_quality` | Command/resource telemetry for investigating mechanisms | Informational output; it is not an acceptance gate by itself. |
| `fs_bot.tools.heuristic_selfplay` | Experimental policy comparisons with resumable JSONL records | Read the policy and seat-classification limitations below before interpreting results. |
| `fs_bot.tools.llm_seat` | Human/assistant decisions, saved sessions and exact replay | Follow [AGENT_INTERFACE.md](AGENT_INTERFACE.md) and [CHATGPT_README.md](CHATGPT_README.md); do not substitute defaults for an unanswered human choice. |

The batch, heuristic and balance CLIs use the default `legacy` card edition;
they currently expose no edition selector. This profile uses the original
versions of the five optional revised cards in base scenarios and revised
versions in Ariovistus, following the scenario after the Interlude. Record that
profile with the results. An explicit-edition study requires a separately
identified harness change; do not label these commands as Second Edition runs.

## Establish and preserve a reproducible run

1. Record the commit, any uncommitted source changes, Python version, scenario
   and seat configuration, card profile, exact seeds, policy configuration,
   commands and hash seeds. Run the full test suite before engine work.
2. Use a fresh output directory for each engine revision or policy change.
   Preserve failed attempts. Do not overwrite evidence or combine results from
   different mechanics into one table.
3. Freeze the Python source during an accepted matrix. The October evidence
   archive contains `orchestrate.py` and `extract_results.py`, which verify
   source digests, exact coverage, outcomes and cross-hash agreement. Follow
   the archive's README to copy these into a fresh directory beside the repo.
4. Run the main batch, inspect its records, and investigate failures before
   expanding the matrix. A completed game can still contain refused actions;
   completion count alone is insufficient.

The following are Bash commands, run from the repository root with the desired
Python environment active. `new-validation` must be a new directory. In
PowerShell, set `$env:PYTHONHASHSEED = "0"` or `"7"` before the corresponding
Python commands instead of using Bash's assignment prefix.

```bash
python -m pytest -q
mkdir new-validation
PYTHONHASHSEED=0 python -m fs_bot.tools.run_batch --games 200 --workers 4 --out new-validation/bots
PYTHONHASHSEED=0 python -m fs_bot.tools.error_census --seeds 1-20 --strict --out new-validation/census0.json
PYTHONHASHSEED=7 python -m fs_bot.tools.error_census --seeds 1-20 --strict --out new-validation/census7.json
PYTHONHASHSEED=0 python -m fs_bot.tools.player_fuzz --seeds 1-40 > new-validation/fuzz0.txt
PYTHONHASHSEED=7 python -m fs_bot.tools.player_fuzz --seeds 1-40 > new-validation/fuzz7.txt
python -m fs_bot.tools.balance_smoke --seeds 1-20
```

Check every command's exit status. Compare the census JSON and fuzz output
between hash seeds; saving both files is not itself a comparison. If piping a
command through `tee`, enable Bash `set -o pipefail` so failures propagate.
The batch CLI itself requires hash seed 0; the archived orchestrator repeats
25 selected games by calling the same `play_one` function in a separate hash-7
process, then compares all recorded result fields used by its verifier.

For additional synchronization checks, repeat this command for every supported
scenario; telemetry can help explain a suspicious outcome distribution:

```bash
python -m fs_bot.tools.sync_check --scenario "The Great Revolt" --seeds 1-20
python -m fs_bot.tools.play_quality --seeds 1-20
```

## Acceptance and interpretation

For the October-sized batch, require exactly 1,000 unique `(scenario, seed)`
records: seeds 1–200 in each of the five scenarios. Check every game for all
three completion flags (`completed`, `game_completed`, `audit_completed`),
errors, integrity findings and a nonempty final-state hash. Require a four-entry
`final_ranking`, `engine_ranking_output_missing == false`, and
`winner_differs_from_highest_margin == false`. The batch recomputes its ranking
and separately records whether the engine emitted one; do not let that computed
ranking conceal a missing engine result.
Reject every diagnostic severity other than `legal-decline`; investigate unknown
categories too. Inspect failed records even if the aggregate command exited 0.

Compare selected bot results across hash seeds using final-state hashes,
winners, rankings, game length, diagnostics and Interlude state. Compare mixed-seat
fuzz outputs and replay digests, with zero hard findings. The default fuzz run
executes each case twice for replay; 200 cases at each of two hash seeds therefore
means 800 game executions, not 800 distinct scenario/seed cases. Its soft partial
count records matching preview/live results from imperfect random plans and must
be reported separately, not silently described as fully successful human actions.

Report attempted and completed games separately and identify the denominator of
every win rate. Distinguish ending before final Winter from ending on final
Winter: a threshold or Optimates result can occur on that last card. For The
Gallic War, report Interlude completion and label whether winners represent the
faction at game end or the original player seat. Germans can win before the
transition; Arverni represent that seat afterward.

A fixed-seed result change on corrected code is implementation drift, not random
rerun noise. A small seed sample still does not establish human balance or prove
one policy's general superiority. Use paired seed sets for comparisons, disclose
coverage and failures, and avoid interpreting a dramatic rate as proof of either
a defect or design intent without tracing its cause.

## Investigating an anomaly

Reproduce the exact scenario, seed, card and decision sequence. Compare setup
with the supplied scenario, then trace the suspected mechanism against its rule
or flowchart branch. Check physical piece ownership, visibility, Tribe identity,
Resources, Control, human decision ownership and RNG state as well as totals.
Keep game-run factions distinct from seated bots and humans in both rule sets.

A confirmed defect needs a source-derived regression that fails before the fix.
Rerun its reproducer and the affected checks, then the agreed integrated matrix.
Preserve before/after records and explain outcome changes. If the source leaves a
policy unresolved, document that narrow question and the existing disposition;
do not tune bot priorities to force a preferred winner distribution.

## Reviewing a baseline change

`fs_bot/tools/balance_baseline.json` contains 100 reviewed games: seeds 1–20 in
all five scenarios. The default threshold is **15 percentage points** per
faction per scenario. The comparison uses exact fractions, so exactly 15 points
passes; a change beyond that fails. Missing or invalid requested records fail
rather than silently reducing coverage.

A failed guardrail triggers investigation. Keep the seed matrix and threshold
fixed while diagnosing the change. An intended rules correction may justify a
new baseline only after reviewing the before/after records, explaining the
mechanism and checking the new results. `--update` writes the requested game
keys and retains other keys; it skips the drift comparison. It is never a repair
for an unexplained failure or evidence that the old baseline passed. Prefer
writing a candidate with `--baseline` to a separate file, reviewing it against
the committed baseline, and only then replacing the reviewed records.

The October refresh changed 26 records and 23 winners while retaining all 100
keys and the same threshold. Those changes and the subsequent unchanged-baseline
check are preserved in the validation evidence. Do not infer a new target win
rate from that refresh.

## Experimental strategy policies

The current `heuristic_selfplay` runner defaults to nine named profiles for
Romans, Arverni, Aedui and Belgae, plus a `RANDOM` policy per base faction and
`BOTS`. It has no named German profile and no `FIRST` policy. Its random policy
samples command builders; it is not uniform over every legal move. Use the base
scenarios for that default matrix. Expansion-specific strategy experiments need
explicit active-seat and policy handling, including the Gallic War transition.

A significant current limitation is that `heuristic_selfplay.play_game` leaves
the overridden seat in `non_player_factions`. The policy changes its own-turn
plans, but NP-sensitive rules and targeting still see it as a non-player.
Its results therefore do not demonstrate genuine human-seat strength. Use
`player_fuzz`, assistant sessions and terminal journeys for human-path validation;
correct and validate the experimental harness before making new human-strategy
claims from it.

Policies in `fs_bot/agents/heuristic.py` build typed plans and validate them through
`moves.validate_player_action`; they do not need to scrape terminal wording.
Define each proposed strategy as a falsifiable command/SA/target preference and
keep the experimental policy separate from the published bot flowcharts. A
heuristic's fallback to Pass must not conceal a rejected published-bot action or
silently answer a real human decision.

For a deliberately scoped experiment after reviewing those limitations:

```bash
PYTHONHASHSEED=0 python -m fs_bot.tools.heuristic_selfplay --scenario "The Great Revolt" --seeds 1-20 --profiles BOTS,R-PACIFY,R-HUNT,RANDOM:Romans --out new-validation/roman-experiment.jsonl
```

The runner skips existing `(label, scenario, seed)` keys, including error records;
its resume key contains no source or policy identity. Use a fresh file after any
change and retain the old one. It catches game exceptions into records but can
still exit 0, so check every `error`, winner, key and expected count yourself.
Do not use this experimental runner as a substitute for the audited batch gate.

## Publishing and ongoing checks

Write results for the exact tested revision, with commands, seed coverage, card
profile, source digest and raw evidence. Separate bot-only outcomes, experimental
policy comparisons and actual human-path tests. Mark earlier interpretations
historical when mechanics change; do not silently replace their measured numbers.
Keep reproducible evidence with the corresponding review, as the October archive
does, while leaving disposable exploratory output outside the tracked tree.

The per-push CI runs four OS/Python test jobs plus synchronization, strict census,
mixed-seat cross-hash replay and balance checks. The separately configured
[deep-soak workflow](.github/workflows/deep-soak.yml) schedules larger census/fuzz
runs and informational telemetry, and also supports manual dispatch. A workflow's
configuration is not proof it ran successfully; cite its actual run and revision.
Run the full test suite before each commit as required by `CLAUDE.md`.
