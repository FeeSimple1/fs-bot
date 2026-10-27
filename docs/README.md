# Documentation index

Use the living guides for current behavior. Dated reports and archived
results describe their named revision and seed sets. The supplied game
references and canonical constants remain read-only.

## Current guides

| Document | Purpose |
|---|---|
| [Repository overview](../README.md) | Launch commands, supported interfaces, and verified checkpoint |
| [Playing](../PLAYING.md) | Human decisions, action order, board display, card editions, saves and resume |
| [Assistant play](../CHATGPT_README.md) | File-based pending decisions, responses, board inspection, and replay |
| [Agent interface](../AGENT_INTERFACE.md) | Turn plans, typed decision requests, validation, and session contracts |
| [Current status](current-status.md) | Corrected behavior, regression coverage, adopted provisional rulings, and limits |
| [Provisional rulings](provisional-rulings.md) | Six owner-adopted interpretations, each subject to later authoritative correction |
| [Question ledger](../QUESTIONS.md#current-open-source-questions) | Source questions, current provisional dispositions, and historical decisions |
| [Developer instructions](../CLAUDE.md) | Source hierarchy, implementation constraints, tests, and commit discipline |
| [Maintenance roadmap](../BUILD_PLAN.md) | Existing components and further validation work |
| [Self-play workflow](../SELFPLAY_PLAYBOOK.md) | Reproducible bot batches, mixed-seat fuzzing, census, and reviewed baselines |
| [Release guide](../RELEASES.md) | Local installation, distribution builds, historical save fixtures, and engine identity |
| [Change history](../CHANGELOG.md) | Versioned engineering changes |

## Dated evidence and research

| Document or artifact | Scope |
|---|---|
| [27 October first repair batch](reviews/first-batch-2026-10-27.md) | Event integrity/lifecycle repairs, related discoveries, 4,715 tests, 200 bot games, mixed-seat replay, strict census and remaining comparison findings |
| [First-batch results JSON](reviews/first-batch-2026-10-27-results.json) | Exact accepted coverage, source digest, diagnostic/replay checks and unchanged balance-band comparison |
| [First-batch evidence archive](reviews/first-batch-2026-10-27-evidence.zip) | Accepted and superseded attempts, raw records, JUnit, logs and independent verification scripts |
| [24 October provisional-ruling validation](reviews/provisional-rulings-2026-10-24.md) | Adopted policies: 4,481 tests, 200 audited bot games, 320 mixed-seat executions, strict census and unchanged balance baseline |
| [Provisional-ruling results JSON](reviews/provisional-rulings-2026-10-24-results.json) | Machine-readable acceptance checks, exact coverage and source identity |
| [Provisional-ruling evidence archive](reviews/provisional-rulings-2026-10-24-evidence.zip) | Commands, logs, per-game records, source identities and independent audits |
| [24 October follow-up repairs](reviews/followup-repairs-2026-10-24.md) | Accepted follow-up repairs: 4,431 tests, 2,500 bot games, 90 optional-setup games, mixed-seat replay, installation and compatibility |
| [24 October results JSON](reviews/followup-repairs-2026-10-24-results.json) | Machine-readable final acceptance and scenario/edition summaries |
| [24 October evidence archive](reviews/followup-repairs-2026-10-24-evidence.zip) | Raw outcomes, rejected attempts, source manifests, replay/census results and package checks |
| [23 October fixes and validation](reviews/outstanding-fixes-2026-10-23.md) | Accepted 1,000-game rerun, corrections, outcomes, exact tested revision, and CI |
| [23 October results JSON](reviews/outstanding-fixes-2026-10-23-results.json) | Machine-readable acceptance, per-scenario statistics, commands, and hashes |
| [23 October evidence archive](reviews/outstanding-fixes-2026-10-23-evidence.zip) | All three attempts, diagnostics, replay/census results, baseline changes, and JUnit files |
| [20 October Vassal comparison](reviews/vassal-module-2026-10-20.md) | Authorized visual cross-check, source conflicts, and results on that revision |
| [Vassal outcome summary](reviews/vassal-outcome-summary.json) | Historical comparison's machine-readable results |
| [Vassal batch verifier](reviews/verify_vassal_batches.py) | Verification utility for that historical study's data |
| [9 October outcome audit](outcome-audit-2026-10-09.md) | Earlier March-cost, Tribe-identity, scoring, and execution repairs |
| [Historical strategy notes](../selfplay-strategy-notes.md) | Older heuristic experiments, with revision and harness caveats |

The 24 October provisional-ruling matrix contains 100 legacy games (seeds
1–20 per scenario) and 50 each with original and second-edition cards
(seeds 201–210 per scenario). It is separate from the earlier follow-up
report's default-setup matrix, which separates the 200-game-per-scenario
legacy sample from three held-out 100-game-per-scenario edition samples.
The optional-Diviciacus sample and hash-seed repeats remain separate. The
accepted 23 October batch contains 200 games per scenario on its older source.
The committed
balance guardrail instead uses seeds 1–20 in each scenario, for 100 games
total. The historical strategy-profile matrices are a third experiment;
their results should not be combined with either of those samples.

## Maintaining these documents

- Update the affected player or API guide when behavior or response shapes
  change. Check examples against implementation and regression coverage.
- Keep current dispositions in [current status](current-status.md). Record
  source quotations, uncertainty, and eventual rulings in the
  [question ledger](../QUESTIONS.md). Keep the [provisional rulings](provisional-rulings.md)
  identified as owner-adopted policies subject to later authoritative correction.
- Keep historical measurements and evidence intact. Add a dated correction
  or supersession notice when later work changes their interpretation.
- Record the commit, scenario/edition, seeds, coverage, failures, and
  diagnostics with each new outcome study. A source digest includes Python
  docstrings, so even a documentation-only Python edit changes that digest;
  do not relabel an older run as a measurement of a newer commit.
- Keep verified results separate from planned checks and configured CI
  schedules. A scheduled workflow is not evidence that a particular run
  completed successfully.
- Leave `Reference Documents/**` and `fs_bot/rules_consts.py` untouched.
  Follow the test-before-commit requirements in [CLAUDE.md](../CLAUDE.md),
  including documentation commits.
