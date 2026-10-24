# Self-play and outcome validation — Falling Sky

Use this workflow to investigate rules defects and compare explicitly defined
experimental policies. Start with [current status](docs/current-status.md) and
the [24 October 2026 follow-up report](docs/reviews/followup-repairs-2026-10-24.md).
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
| `fs_bot.tools.run_batch` | Audited zero-human outcomes across all five scenarios; JSONL records, summary, revision and source digest | `--games N` means seeds 1–N **per scenario**; `--seeds N-M` selects another range. Requires hash seed 0; refuses an output directory containing prior files and does not resume. Nonlegal diagnostics now fail the audit and exit status. Inspect ranking output and exact coverage too. |
| `fs_bot.tools.error_census` | Classifies nested Command, Event and Winter results | Use `--strict`; inspect all severities, including `other-refused`. `legal-decline` is allowed. |
| `fs_bot.tools.player_fuzz` | Mixed human/bot seats, randomized reactions and Event parameters, preview/live checks, replay | Leave reactions, Events and determinism enabled. Randomly generated partial or refused plans are separate from hard engine findings. |
| `fs_bot.tools.sync_check` | Tribe/piece synchronization across complete games | Select a scenario explicitly; its default is only Reconquest. |
| `fs_bot.tools.balance_smoke` | Fixed-seed winner-rate drift against the reviewed baseline | A passing rate check is not a rule-compliance proof and does not require every individual winner to stay unchanged. |
| `fs_bot.tools.play_quality` | Command/resource telemetry for investigating mechanisms | Informational output; it is not an acceptance gate by itself. |
| `fs_bot.tools.heuristic_selfplay` | Experimental human-policy seats against bots, with audited outcomes and compatible resume | Scenario-valid profiles and explicit Interlude handover; failed attempts remain recorded and retryable. Reactive defaults and coarse strategy limits remain disclosed below. |
| `fs_bot.tools.llm_seat` | Human/assistant decisions, saved sessions and exact replay | Follow [AGENT_INTERFACE.md](AGENT_INTERFACE.md) and [CHATGPT_README.md](CHATGPT_README.md); do not substitute defaults for an unanswered human choice. |

The batch, census, mixed-seat fuzz, synchronization and heuristic runners accept
`--card-edition legacy`, `original`, or `second-edition` and record the selected
profile. `legacy` remains the default: it uses the original versions of the five
optional revised cards in base scenarios and revised versions in Ariovistus,
following the scenario after the Interlude. Explicit profiles persist through
the transition. The balance guardrail still checks its reviewed `legacy`
baseline; telemetry also defaults to that profile. Keep different editions in
separate output directories and summaries.

## Establish and preserve a reproducible run

1. Record the commit, any uncommitted source changes, Python version, scenario
   and seat configuration, card profile, exact seeds, policy configuration,
   commands and hash seeds. Run the full test suite before engine work.
2. Use a fresh output directory for each engine revision or policy change.
   Preserve failed attempts. Do not overwrite evidence or combine results from
   different mechanics into one table.
3. Freeze the Python source during an accepted matrix. The 23 October evidence
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

To extend coverage beyond the old seeds 1–200, use an explicit edition and a
held-out range. For example, repeat this pair for `legacy`, `original`, and
`second-edition`, using a different directory for each:

```bash
PYTHONHASHSEED=0 python -m fs_bot.tools.run_batch --seeds 201-220 --card-edition second-edition --workers 4 --out new-validation/second-edition-bots
PYTHONHASHSEED=0 python -m fs_bot.tools.player_fuzz --seeds 201-220 --card-edition second-edition --out new-validation/second-edition-fuzz0.json > new-validation/second-edition-fuzz0.txt
PYTHONHASHSEED=7 python -m fs_bot.tools.player_fuzz --seeds 201-220 --card-edition second-edition --out new-validation/second-edition-fuzz7.json > new-validation/second-edition-fuzz7.txt
```

The batch also accepts `--scenario` for one scenario. Otherwise each command
above covers all five. Census and synchronization accept the same edition
selector. JSON output includes source identity and exact seeds; the fuzz JSON
also retains individual case records. The examples prescribe checks, not
completed-run statistics.

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

For the historical October-sized batch, require exactly 1,000 unique
`(scenario, seed)` records: seeds 1–200 in each of the five scenarios. For new
matrices, require the exact requested `(scenario, seed, card_edition)` keys;
do not pool different editions into one winner distribution. Check every game for all
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

The 23 October refresh changed 26 records and 23 winners while retaining all 100
keys and the same threshold. Those changes and the subsequent unchanged-baseline
check are preserved in the validation evidence. Do not infer a new target win
rate from that refresh. The 24 October follow-up refresh changes 17 records
and 13 winners relative to `8ef88e2`, with the same 100 keys and unchanged
15-point threshold. The subsequent balance run matches every reviewed winner
and card count. Both comparisons remain tied to their own source revisions.

## Experimental strategy policies

The repaired `heuristic_selfplay` runner removes the policy-controlled seat from
`non_player_factions`; opponent targeting and NP-sensitive rules therefore see
an actual human seat. Its defaults include only profiles whose factions are
playable in the selected scenario, plus a `RANDOM` policy for each playable seat
and `BOTS`. An explicit ineligible profile is rejected before play, preventing
an Arverni profile from producing an Ariovistus result without taking a turn.

Eleven named profiles exist across the two rule sets. The two German profiles,
`G-GROW` and `G-BATTLE`, are simple growth and Battle hypotheses. During the
Gallic War Interlude their player changes to Arverni and explicitly adopts
`A-DEVASTATE` or `A-BATTLE`, respectively. `RANDOM:Germans` continues its generic
random policy as Arverni. Records identify the ending seat and count decisions
by faction, so second-half wins can be attributed to the original player.
The random policy samples command builders; it is not uniform over every legal
move. No `FIRST` policy is implemented.

These policies remain experiments, not expert human play. They do not have an
Event-aware strategy, and Special Activity targeting is coarse. Their reactive
policy takes the first offered Retreat destination, refuses agreement requests,
and explicitly defers other choices to the raw callback's engine defaults.
Records count policy and default reactive responses separately. A real human
session must still wait for its user's answer; this experiment's defaults do not
change the durable assistant interface.

Policies in `fs_bot/agents/heuristic.py` build typed plans and validate them through
`moves.validate_player_action`; they do not need to scrape terminal wording.
The validator's `ok` flag means an action had some legal effect, so policies also
inspect nested diagnostics and reject candidates containing refused sub-actions
or ineffective attached Special Activities. Partial success alone no longer
qualifies a candidate as clean.
Define each proposed strategy as a falsifiable command/SA/target preference and
keep the experimental policy separate from the published bot flowcharts. A
heuristic's fallback to Pass must not conceal a rejected published-bot action or
silently answer a real human decision.

For deliberately scoped experiments:

```bash
PYTHONHASHSEED=0 python -m fs_bot.tools.heuristic_selfplay --scenario "The Great Revolt" --seeds 1-20 --profiles BOTS,R-PACIFY,R-HUNT,RANDOM:Romans --out new-validation/roman-experiment.jsonl
PYTHONHASHSEED=0 python -m fs_bot.tools.heuristic_selfplay --scenario "The Gallic War" --seeds 201-220 --card-edition second-edition --profiles BOTS,G-GROW,G-BATTLE,RANDOM:Germans --out new-validation/german-experiment.jsonl
```

Each output has an adjacent `.jsonl.manifest.json` file. The manifest and records
identify the engine commit/source digest, Python version, policy version,
scenario, edition, human-seat semantics, reactive defaults and named Interlude
handover. Resume requires compatible identities; Git's dirty flag is retained as
provenance but does not alone make identical source bytes incompatible.

Only successful audited `(label, scenario, seed)` records are skipped. Failed
attempts are preserved and retried, and any new unsuccessful attempt makes the
command exit nonzero. Success requires a completed game, an eligible winner,
actual policy participation when a policy is selected, valid state/rankings,
and no diagnostic severity except `legal-decline`. A final-state digest supports
repeat comparisons. Historical unversioned logs, incompatible manifests and
malformed records are refused without rewriting them; use a fresh output path.

When analyzing a retried log, retain every attempt but count each requested key
only once in the accepted sample. Check exact coverage rather than counting
lines. Repairs to this tool do not retroactively validate the old strategy
tables, and its policy comparisons remain separate from zero-human bot studies.

## Publishing and ongoing checks

Write results for the exact tested revision, with commands, seed coverage, card
profile, source digest and raw evidence. Separate bot-only outcomes, experimental
policy comparisons and actual human-path tests. Mark earlier interpretations
historical when mechanics change; do not silently replace their measured numbers.
Keep reproducible evidence with the corresponding review, as the October archive
does, while leaving disposable exploratory output outside the tracked tree.

The per-push CI runs four OS/Python test jobs plus synchronization, strict census,
mixed-seat cross-hash replay and balance checks. Its edition matrix adds bot
games and mixed-seat replay for `legacy`, `original`, and `second-edition` on
held-out seeds across all five scenarios. The separately configured
[deep-soak workflow](.github/workflows/deep-soak.yml) schedules larger census/fuzz
runs and informational telemetry, and also supports manual dispatch. A workflow's
configuration is not proof it ran successfully; cite its actual run and revision.
Run the full test suite before each commit as required by `CLAUDE.md`.
