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
| [Current status](current-status.md) | Corrected behavior, regression coverage, unresolved source questions, and limits |
| [Question ledger](../QUESTIONS.md#current-open-source-questions) | Current open-question index followed by the historical decision record |
| [Developer instructions](../CLAUDE.md) | Source hierarchy, implementation constraints, tests, and commit discipline |
| [Maintenance roadmap](../BUILD_PLAN.md) | Existing components and further validation work |
| [Self-play workflow](../SELFPLAY_PLAYBOOK.md) | Reproducible bot batches, mixed-seat fuzzing, census, and reviewed baselines |

## Dated evidence and research

| Document or artifact | Scope |
|---|---|
| [23 October fixes and validation](reviews/outstanding-fixes-2026-10-23.md) | Accepted 1,000-game rerun, corrections, outcomes, exact tested revision, and CI |
| [23 October results JSON](reviews/outstanding-fixes-2026-10-23-results.json) | Machine-readable acceptance, per-scenario statistics, commands, and hashes |
| [23 October evidence archive](reviews/outstanding-fixes-2026-10-23-evidence.zip) | All three attempts, diagnostics, replay/census results, baseline changes, and JUnit files |
| [20 October Vassal comparison](reviews/vassal-module-2026-10-20.md) | Authorized visual cross-check, source conflicts, and results on that revision |
| [Vassal outcome summary](reviews/vassal-outcome-summary.json) | Historical comparison's machine-readable results |
| [Vassal batch verifier](reviews/verify_vassal_batches.py) | Verification utility for that historical study's data |
| [9 October outcome audit](outcome-audit-2026-10-09.md) | Earlier March-cost, Tribe-identity, scoring, and execution repairs |
| [Historical strategy notes](../selfplay-strategy-notes.md) | Older heuristic experiments, with revision and harness caveats |

The accepted October batch contains 200 games per scenario. The committed
balance guardrail instead uses seeds 1–20 in each scenario, for 100 games
total. The historical strategy-profile matrices are a third experiment;
their results should not be combined with either of those samples.

## Maintaining these documents

- Update the affected player or API guide when behavior or response shapes
  change. Check examples against implementation and regression coverage.
- Keep current dispositions in [current status](current-status.md). Record
  source quotations, uncertainty, and eventual rulings in the
  [question ledger](../QUESTIONS.md).
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
