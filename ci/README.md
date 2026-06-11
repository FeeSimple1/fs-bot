# CI workflow (manual install required)

`github-ci.yml` runs three jobs: the full test suite, the tribe/piece sync
sweep across all four scenarios (seeds 1-8), and the balance guardrail.

The push token for this repo lacks the `workflow` scope GitHub requires to
create `.github/workflows/` files. To activate CI, copy this file to
`.github/workflows/ci.yml` via the GitHub web UI, or push it with a
workflow-scoped token that covers this repository.
