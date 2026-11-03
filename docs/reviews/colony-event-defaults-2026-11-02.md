# Colony Event defaults and rejected-bot detection — 2 November 2026

Post-publication CI for `3873ff9` passed 13 checks but failed the mixed-player
cross-hash comparison. This follow-up repairs the underlying Event failure
and the validation gap that hid it. No additional original finding closes:
**18 of 50 remain closed (36%), 32 open**.

## Defect and correction

In Ariovistus seed 17, non-player Aedui selected unshaded A45, Savage Dictates.
Its three candidate Tribes included a Colony in Mandubii. The default chooser
looked up Tribe locations only in the printed map, obtaining no Region for the
Colony. Sorting that missing value with ordinary Region names raised a
TypeError. Event execution caught it, rolled back and reported the Event as
inapplicable. Its intended Ally placements did not happen.

Four lookups now use the existing state-aware Tribe resolver: Region grouping,
continuation within the chosen Region, target selection and remembering the
previous Region. The shared A36 shaded default had the same defect when
removing a Colony Ally; a separate regression confirms its repair. Ordinary
Tribe geography, priority scores and seeded tie selection are retained.

The supplied Card Reference 71 expressly makes a Colony a Tribe. A Card
Reference A45 permits non-German Allies in its specified Celtic area; A36
shaded removes Allies in its specified area. Chapter 8 §§8.2.3, 8.3.1 and
8.3.4 govern Event priorities, Region continuation and random ties. No new
ruling or protected reference/constant change is needed.

## Detection gap

CI used Python 3.10.22. Its two 200-game runs had identical counts, zero
reported hard findings and two soft partial plans, but different history
digests. Local Python 3.12.14 matched across hash seeds and passed all 6,872
then-existing tests. The exact CI Python version reproduced the failing
hash-7 digest.

Only Ariovistus seed 17 differed. Its complete final state and RNG were
identical; the sole differing history leaf was which operand type appeared
first in the caught TypeError's text. Both executions were wrong in the same
way. The fix corrects Colony geography; it does not normalize away the error
or weaken the history comparison.

The fuzzer now reports `bot-event-rejected` when a recorded bot Event has both
`executed: false` and `rejected: true`. It uses the individual action's bot
record, avoiding misclassification when seats change at the Gallic War
Interlude. Intentional malformed human plans and legal optional declines
remain separate. Applying this check to the retained pre-fix trajectory
produces one hard finding without changing its digest or rerunning the game.

Regular and scheduled fuzz CI now retain per-game JSON alongside stdout,
compare both between hash seeds, and upload available files even after
failure. The edition matrix already retained equivalent evidence. Updating
the scheduled soak is not a claim that a fresh soak has run.

## Validation and provenance

Five new Colony regressions fail against the parent implementation and pass
after repair. They create actual Colonies, verify legal placement/removal,
check continuation after Colony selection, preserve integrity and verify
that a sole continuation consumes no RNG. Nine new fuzzer tests cover the
hard finding, per-action ownership, exclusions and nonzero CLI failure status.
Independent review cleared the code, tests and CI changes.

Final acceptance on Python 3.10.22:

- **6,886 tests passed**, including 14 new cases; no failures, errors or skips.
- **200 distinct mixed-seat cases**, all five scenarios, legacy seeds 1–40,
  two hash seeds with replay: **800 executions**, zero hard findings, exact
  JSON and stdout agreement. Two explained soft partial plans remain.
- **100 audited bot-only games**, all five scenarios, legacy seeds 1–20;
  all completed with valid rankings and no integrity/nonlegal diagnostics.
  Winners, card counts and final-state hashes match the prior same-source
  parent records. Those parent records are reused, not rerun or relabeled.
- The existing balance baseline remains unchanged and passes its 15-point
  guard. The largest faction-rate difference from that older baseline remains
  10 percentage points; no bot tuning or tolerance change was made.
- All 49 protected inputs remain byte-identical.

Only the repaired Ariovistus seed 17 changes among the 200 mixed-seat cases.
Its first 36 complete card results match; the next card, A45, now executes
instead of being rejected. Both histories run 47 cards; later play and the
final state change. This identifies the first repaired divergence, not the
contribution of every later action. Independent replay of the captured A45
boundary places exactly three Aedui Allies (Lingones, the Mandubii Colony
and Senones), spends three Available Allies and leaves valid state. That
focused review used Python 3.12.14; acceptance above used Python 3.10.22. These mixed
human-policy cases are different from the 100 zero-player balance games.

The two soft partials were inspected: Ariovistus seed 39 and Gallic War seed
1. The generator injected Resource gifts after constructing Region-only Rally
plans, leaving later Regions unaffordable. Dry/live results match exactly and
both games complete without hard findings. They remain reported as partials.

The accepted source is prepared over `3873ff97505194557e1ed63b833d7bf2e5317fdc`,
with **424 Python files**, SHA-256
`c3c3cd4fd4370f4367db759106b7418449bcc0c27b34ceae2e93c014c64b3bf4`.
Acceptance runs precede the commit; their metadata correctly retains the
parent commit and dirty-tree status. Source manifests and the prepared patch
identify the tested bytes. User-facing dates use America/Chicago; runs took
place on 3 November UTC.

[Results](colony-event-defaults-2026-11-02-results.json) and the
[evidence archive](colony-event-defaults-2026-11-02-evidence.zip) retain the
failed CI log, exact-runtime reproduction, captured histories, before/after
regressions and acceptance records. Exploratory fixtures remain labeled;
the final five failing-parent tests are the accepted regression evidence.
Repeated suites, hash runs and diagnostic games overlap and are not extra
independent statistical samples.

The human-choice backlog, 34 unverified inventory rows, two source questions,
nine provisional rulings and separate Intimidate projection lead remain
unchanged. These checks establish bounded behavior, not complete rules
fidelity or statistical faction balance.
