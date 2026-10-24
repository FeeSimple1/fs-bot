# Follow-up repairs and validation — 24 October 2026

**Later disposition, 24 October 2026:** the owner subsequently adopted
[six provisional project rulings](../provisional-rulings.md), all subject to
possible later authoritative correction. This report's original source,
measurements, and then-open question dispositions remain historical evidence;
they do not validate that later adoption.

This review follows the [23 October checkpoint](outstanding-fixes-2026-10-23.md).
It covers the remaining Diviciacus mechanics and human choices, Suborn,
validation tools, installation, and saved-game compatibility. The earlier
report's measurements remain tied to its source revision.

**Local validation passed on the third attempt:** 4,431 tests, 2,500 audited
bot games, 90 optional-Diviciacus games, and 1,000 mixed-seat game executions.
The independent aggregate verifier accepted the full matrix. Earlier failed
attempts are preserved separately. Remote CI is recorded separately below.

## Gameplay and human decisions

Diviciacus cooperation previously lacked the shared physical-piece handling
needed to make all permitted Commands, Special Activities and defense work.
The new action context treats consenting Roman Auxilia and Aedui Warbands
as the effective type for that action while retaining their physical owners,
visibility, Available pools and contribution to Control. Original card 38
and the Leader's A1.4 effect have distinct scopes; the latter also permits
Special Activities within the Leader's range. A permission for a Command
does not silently authorize an accompanying Special Activity.

Humans choose whether to request cooperation and then answer the lender's
agreement request. Formation, drop-off, placement and casualty prompts
identify physical owners. Fixed Event Battles also obtain the acting
human's opt-in. Previews may show a plan conditional on human agreement,
but do not consume that decision or the live RNG. Invalid assistant replies
remain pending. The board continues to show physical ownership and identifies
the temporary treatment separately.

Bots plan with eligible cooperating forces. If agreement is refused, they
replan from the original RNG position with the actual available force.
Borrowed pieces remain in the moving cohort when it leaves the original
Region; residents cannot replace lost or departed pieces. Diviciacus cannot
absorb a Battle loss until he is the last possible piece. A borrowed Scouted
Warband loses its Scouted marker when Roman March would hide it but remains
Revealed, as the supplied Diviciacus rule requires.

| Repair | Result | Principal coverage |
|---|---|---|
| Optional Diviciacus setup | Original scenarios can independently select O38 and the Leader; the choice survives save/load and replay. Replacement after deck shuffling preserves the shuffled order. The existing canonical Interlude A38 replacement remains unchanged. | `test_diviciacus_option.py` |
| Multi-step cooperating March | A native-only selected cohort, or native survivors after borrowed pieces leave or are lost, retain the ownership context needed for later steps. The empty lender ledger does not borrow residents in transit Regions. | `test_diviciacus_forces.py` and Reconquest seed 148 |
| Camulogenus (70) | The printed selected Roman force makes an actual March to one destination, with its range and maximum four Legions. Stationary pieces are not flipped. The March and subsequent Battle obtain their own cooperation. | `test_diviciacus_consent.py` |
| Suborn | Human menus expose physical owners, types, visibility and exact Allied Tribes. Ordered choices update cumulative cost and availability, with undo/cancel. The complete Special Activity is validated before mutation. A placement or removal cannot invalidate a later step without detection. | `test_suborn_choices.py` |
| Vergobret and bot Suborn | Unshaded A38 permits four pieces, including two Allies, per eligible Region. Bot Ally priorities follow §8.6.3. Both A38 sides are tracked and removable as capabilities; older modifier-only saves remain readable. Dynamic Colony tribes are selectable when actually present. | `test_suborn_bot_limits.py`, `test_vergobret_capability.py` |
| Capability selection | Shifting Loyalties selects an actual active capability, including legacy A38. Board and change displays use the same effective capability list. | `test_legacy_capability_display.py`, `test_param_schema.py` |
| Roman Quarters hosts | The planner checks legal host factions before requesting consent. German agreement cannot permit a Roman relocation prohibited by §6.3.3/A6.3.3. | `test_roman_quarters_host_eligibility.py` |
| Supply-Line agreements | Accepted consent holds for the Command or Event under §1.5.2. Recruit's budget check and execution share the same answer. Refusal does not become an agreement for a later distinct request. | `test_recruit_supply_consent.py` |

The terminal regressions exercise actual menus and completed games, including
both Command/Special Activity orders, `board`, exact physical-piece choices,
multi-human reactions, saved pending decisions, replay, and a forced
Interlude handover. They supplement bot samples with decisions bots do not
exercise. They are functional tests, not models of expert human strategy.

## Validation and distribution repairs

The strategy runner now removes its experimental policy seat from the
non-player faction set, supports scenario-valid German policies, and records
the German-to-Arverni player handover. Resume checks the actual source,
policy and settings manifest; failed records are retried rather than reused
as successes. Candidate plans reject nested illegal outcomes. Historical
strategy studies retain their limitations and have not been relabeled as
measurements of this repaired runner.

Audited bot outcomes require real completion, eligible and complete final
rankings, agreement with recomputed results, an eligible winner, intact
piece inventories and valid final-state hashes. Illegal action diagnostics
make a record fail even when the game reaches an ending. Output directories
cannot silently overwrite earlier evidence. Fuzzing includes the entire
state, RNG and returned trajectory in determinism checks; replay-only errors
and unfinished games fail explicitly. The tools record card edition and
seed ranges, and CI includes all three edition profiles.

The repository now builds a local `falling-sky-bot` distribution, with
`fs-bot` and `python -m fs_bot` entry points. The wheel bundles the unchanged
reference inputs and balance baseline needed by installed tools. New saves
record their writing engine's version and digest without changing save
format 1. Valid older saves without writer metadata still load. Four
fixtures generated by the unmodified `8ef88e2` engine exercise a pending
card turn, interrupted Frumentum and real pre/post-Interlude boundaries.
These fixtures establish those continuations, not universal replay
compatibility between engine revisions.

Fresh-process setup/Battle imports no longer fail through circular imports.
Trade's earnings detail has stable ordering across Python hash seeds.
The [release guide](../../RELEASES.md) describes isolated installation checks
and the separate Linux, Windows and macOS package workflow. No package
registry upload or public release is implied by the local package version.

## Rejected attempts and discovered bugs

All follow-up work started from commit
`8ef88e21b437d23bb82f7b404df79bbabeb11d9b`. The validation manifests record
that base commit and the dirty working tree's exact source digest. Source
changes require fresh evidence; passing results from separate digests are
not combined into an accepted revision.

| Attempt | Python source SHA-256 | Disposition |
|---|---|---|
| First follow-up | `190ac6925ac2a6cff5df491cb02fea1858880c0d4ba8854887f49c3a8174be0f` | Rejected. Mixed-seat Gallic War seed 7 exposed the Roman Quarters host bug. The legacy bot process became unavailable after 934 of 1,000 records; no final summary was produced and the cause was not established. |
| Second follow-up | `0a7549580f45adaab6e249abbf885292f7f16d2306fcd41e19204eca0b5b4899` | Rejected. Reconquest seed 148 completed, but an illegal ordinary Roman March while Card 54 was current was recorded: `Physical-owner selection requires Enlist`. Record-level acceptance correctly rejected it and the batch exited nonzero. |

The second attempt’s March failure was caused by losing the physical-owner
context between movement steps when a selected cohort contained only native
pieces, or when it lost or dropped off its last borrowed piece. It was not a
Joined Ranks Event-handler error. Preserving the cohort’s empty lender ledger
allows native survivors to continue without borrowing unrelated transit
residents. Six focused regressions cover these cases; the exact failing game
now completes with 61 cards, Aedui winning, and no illegal diagnostics.

The first attempt also exposed duplicate live Supply-Line requests in
Recruit. A human could approve the budget check and refuse the immediately
repeated question during execution, changing the cost of the same planned
action. The Supply agreement fix above addresses that cause independently
of the Quarters correction.

The second attempt's mixed-seat gate completed 1,000 game executions with
no hard findings and identical replay/hash-seed outputs. One deliberately
injected Resource gift left a later German Rally step unaffordable in
Ariovistus seed 26. Preview and execution agreed, other Regions resolved,
and the game completed without state corruption. This was recorded as a
soft partial plan, not hidden or counted as a successful full human plan.
Those component results belong to the second attempt only.

The second attempt's first optional-Diviciacus output had 90 per-game
artifacts and a 90-game summary but only 88 index entries. It was not
accepted by reconstructing missing records. A fresh 90-game run produced
a consistent index and artifacts; both outputs are preserved. This evidence
issue does not establish a gameplay failure, and its cause was not confirmed.

## Final verification

The third attempt uses Python source SHA-256
`c9a6e890ede62f6315234a1b7a4ef9b5f97d256b735171bf468aef741482c7a1`.
The manifests correctly retain the checkout's base commit `8ef88e2` and
`dirty: true`: they identify an uncommitted source snapshot, not a run of
unmodified `8ef88e2`. The engine and distribution code snapshot is
[`a434a6a33eb004758ae919e8afd201a99cc8e2f9`](https://github.com/FeeSimple1/fs-bot/commit/a434a6a33eb004758ae919e8afd201a99cc8e2f9);
its Python source matches that tested digest exactly. The preceding logical
commits are `812f3fa` (gameplay) and `fc67b04` (validation), followed by
`a434a6a` (distribution and compatibility). The Git attributes correction
is committed as
[`53d795ccee5a85e69b19062091b70010a59f0e97`](https://github.com/FeeSimple1/fs-bot/commit/53d795ccee5a85e69b19062091b70010a59f0e97);
it preserves these same source bytes on Windows. Documentation and evidence
are published separately. The original run metadata remains unchanged.

The completed components below all use that same frozen source. The
independent aggregate verifier accepted the matrix after checking exact
coverage, record-level outcomes, hashes, baseline agreement, package evidence
and unchanged source. The archive establishes these local results; remote
workflow conclusions belong to their publication commits in GitHub Actions.

| Check | Coverage | Result |
|---|---|---|
| Full local suite | Python 3.12.14 | 4,431 passed |
| Main legacy bot batch | Seeds 1–200 × five scenarios | 1,000/1,000 accepted; 9,824 legal declines |
| Held-out legacy bot batch | Seeds 201–300 × five scenarios | 500/500 accepted; 4,829 legal declines |
| Held-out original-card batch | Seeds 201–300 × five scenarios | 500/500 accepted; 4,846 legal declines |
| Held-out Second Edition batch | Seeds 201–300 × five scenarios | 500/500 accepted; 4,794 legal declines |
| Bot hash-seed repeat | Seeds 201–205 × five scenarios × three editions | All 75 repeats match hash seed 0; no result differences |
| Mixed-seat replay and hash seeds | 250 cases, each executed and replayed at hash seeds 0 and 7 | 1,000 completed executions; zero hard findings; complete JSON and stdout match for each edition pair |
| Optional Diviciacus | Seeds 201–210 × three original scenarios × three editions | 90/90 accepted; consistent index and per-game artifacts |
| Strict nested census | Seeds 1–20 × five scenarios at hash seeds 0 and 7 | 200 game executions; matching complete outputs, 967 legal declines per run and no other severities |
| Balance baseline review | Seeds 1–20 × five scenarios | 100 audited games; 17 records and 13 winners changed from `8ef88e2` |
| Actual balance smoke | Same 100 baseline games | Exact winner and card-count agreement with reviewed baseline |
| Strategy runner smoke | All 11 named policies in valid scenarios, plus German Interlude cases | 20/20 accepted; actual German-to-Arverni handovers observed |
| Installed distribution | Isolated environment outside checkout | Entry points, card text, references, saves and completed base/expansion games passed |

All 2,500 main bot records completed and passed their outcome audit, with
no crashes, illegal diagnostics, integrity findings, ranking disagreement
or missing/invalid final-state hashes. Their 24,293 diagnostic incidents
were legal declines. These records inspect returned-card diagnostics;
the separate strict census checks nested Event, Winter Campaign and
game-run Winter paths. Completion alone is not the acceptance criterion.
The 75 hash-seed repeats compare every recorded result field except elapsed
time, commit label and source label; both runs independently verify the
same source digest.

The optional-setup sample includes 51 O38 card resolutions, 33 unshaded
O38 executions, and 66 Commands planned with cooperation in 15 games.
This establishes exercised feature paths, rather than merely 90 games
that happened to enable an option. The sample's outcome records are kept
separate from the default-setup samples.

### Mixed-seat decisions and replay

The mixed-seat gate uses 200 `legacy` cases (seeds 1–40 in all five
scenarios), plus 25 cases for each explicit edition (seeds 201–205 in all
five). Each case executes and replays at Python hash seeds 0 and 7:
250 distinct scenario/edition/seed cases and 1,000 game executions. All
complete; both the full JSON report and stdout match within each edition
pair, with no hard findings.

| Edition | Cases per hash seed | Human turns per run | Event turns per run | Successful Events per run | Soft partial plans per run |
|---|---:|---:|---:|---:|---:|
| legacy | 200 | 6,465 | 1,652 | 1,607 | 1 |
| original | 25 | 693 | 182 | 171 | 0 |
| second-edition | 25 | 633 | 171 | 164 | 0 |

The one soft partial is Ariovistus seed 26, Card A67. The deliberately noisy
fuzzer gives one Resource to Belgae, leaving one when the later Cisalpina
Rally step needs two. Other selected Regions execute. The preserved action
artifact confirms matching preview/live results and no mutation on rejected
actions, integrity finding or replay divergence. The game completes. This
is disclosed as a partial generated plan, not counted as a full successful
human plan or suppressed to make the gate appear cleaner.

### Cross-platform checkout correction

The first remote Windows test job on `a434a6a` reported 4,430 passes and
one failure: the compatibility fixture generator's SHA-256 differed from
its preserved manifest. Git's automatic CRLF checkout conversion changed
the Python file bytes. This was a provenance failure, not a different saved
outcome, and the failed run is retained rather than described as passing.

Repository attributes now require LF checkouts for Python files and disable
text conversion for the supplied reference files and archived compatibility
JSON. The correction changes no Python or reference content. A checkout
with `core.autocrlf=true` verifies all 326 checked files against their Git
bytes, with no mismatches; the generator again matches its recorded SHA-256
`2423f59b84c1f2de419ec032115d86a11cacf1faf7e3bace4aab9c7e06f615be`.
The accepted local matrix's Python digest therefore remains unchanged.
The full 4,431-test local suite also passes after the attributes correction.
The failed first remote run is preserved separately from subsequent workflow
runs on publication commits.

### Remote workflow records

GitHub Actions attaches checks and logs to each publication commit:
[engine CI](https://github.com/FeeSimple1/fs-bot/actions/workflows/ci.yml)
and [installed-package checks](https://github.com/FeeSimple1/fs-bot/actions/workflows/package.yml).
The configured coverage is 11 engine/validation jobs and three installed
package jobs. Select the publication revision when reviewing conclusions;
the failed Windows job on `a434a6a` remains part of the history. The accepted
local archive does not substitute for a remote job's actual conclusion.

### Reviewed baseline

The refresh retains seeds 1–20 in all five scenarios, all 100 keys, and the
15-percentage-point threshold. Relative to the baseline in `8ef88e2`,
17 winner/card-count records change, including 13 winners. The largest
scenario/faction shift is 15 percentage points. The follow-up corrections
change actual cooperating forces, casualty choices, Suborn limits and
Event movement; the record comparison does not claim to isolate one fix's
causal contribution to each changed outcome. No bot priorities were tuned
to obtain preferred faction win rates, and the threshold was not widened.
The subsequent actual balance check matches all 100 winners and card counts.

### Installation and compatibility

The source archive was built locally, then its wheel was installed without
an index or dependencies into a fresh environment. Checks ran outside the
checkout. All 47 bundled reference files are byte-identical to the supplied
inputs, and the bundled balance baseline matches the reviewed repository
file. Both entry points work, every card has its display text, all five
scenarios save/load, and base-game and Ariovistus bot games complete.
Additional installed checks place and save the optional Diviciacus Leader
in all three original scenarios. Source and installed engine identities
match. Historical save-fixture regressions are part of the full test suite.

| Local build artifact | SHA-256 |
|---|---|
| `falling_sky_bot-0.1.0.tar.gz` | `9beeed2d55b15d139bb3dd2e6c729f29407d4d0d5ca5aba0dab9809e0aed4fc7` |
| `falling_sky_bot-0.1.0-py3-none-any.whl` | `03edb13111a505730b1ede440da8c8623c212a69cf29ae4da09d3fd2113ef848` |

These hashes identify the retained local builds. A later build can differ
in archive metadata or included documentation while using the same engine
source. Package version `0.1.0` is not a claim of publication to a registry.

## Bot outcome samples

The first table uses the main 1,000-game default-setup batch: 200 completed
games per scenario, seeds 1–200, `legacy` card edition. Entries show wins
and percentages. A dash marks a faction that cannot win that scenario.
Gallic War records the winning faction at game end, including Arverni after
the German player's Interlude transition.

| Scenario | Romans | Arverni | Aedui | Belgae | Germans |
|---|---:|---:|---:|---:|---:|
| Pax Gallica? | 137 (68.5%) | 16 (8%) | 13 (6.5%) | 34 (17%) | — |
| Reconquest of Gaul | 123 (61.5%) | 15 (7.5%) | 29 (14.5%) | 33 (16.5%) | — |
| The Great Revolt | 39 (19.5%) | 72 (36%) | 27 (13.5%) | 62 (31%) | — |
| Ariovistus | 92 (46%) | — | 19 (9.5%) | 31 (15.5%) | 58 (29%) |
| The Gallic War | 93 (46.5%) | 36 (18%) | 16 (8%) | 55 (27.5%) | 0 (0%) |

| Scenario | Ended before final Winter | Ended on final Winter | Mean cards processed | Interlude reached |
|---|---:|---:|---:|---:|
| Pax Gallica? | 169 | 31 | 37.06 | — |
| Reconquest of Gaul | 149 | 51 | 33.01 | — |
| The Great Revolt | 25 | 175 | 43.19 | — |
| Ariovistus | 59 | 141 | 38.16 | — |
| The Gallic War | 166 | 34 | 61.13 | 124 |

Ending on the final Winter can still involve a threshold or Optimates
result; timing is distinct from the recorded termination reason.

The next table keeps the held-out samples separate. Each row contains
100 games using seeds 201–300; counts therefore also equal percentages.
Different edition rows reuse the same seeds, and some profiles share card
versions in a given scenario. They are paired software checks, not independent
samples to pool into a larger statistical estimate.

| Card edition | Scenario | Romans | Arverni | Aedui | Belgae | Germans |
|---|---|---:|---:|---:|---:|---:|
| legacy | Pax Gallica? | 75 | 5 | 7 | 13 | — |
| legacy | Reconquest of Gaul | 56 | 6 | 19 | 19 | — |
| legacy | The Great Revolt | 22 | 36 | 13 | 29 | — |
| legacy | Ariovistus | 51 | — | 17 | 10 | 22 |
| legacy | The Gallic War | 52 | 16 | 10 | 22 | 0 |
| original | Pax Gallica? | 75 | 5 | 7 | 13 | — |
| original | Reconquest of Gaul | 56 | 6 | 19 | 19 | — |
| original | The Great Revolt | 22 | 36 | 13 | 29 | — |
| original | Ariovistus | 52 | — | 17 | 8 | 23 |
| original | The Gallic War | 55 | 15 | 11 | 18 | 1 |
| second-edition | Pax Gallica? | 74 | 4 | 7 | 15 | — |
| second-edition | Reconquest of Gaul | 59 | 6 | 19 | 16 | — |
| second-edition | The Great Revolt | 24 | 36 | 12 | 28 | — |
| second-edition | Ariovistus | 51 | — | 17 | 10 | 22 |
| second-edition | The Gallic War | 50 | 18 | 9 | 23 | 0 |

The 20 policy games establish that the repaired strategy runner functions,
including actual Interlude handover. They are too limited to establish new
strategy rankings. They do not rehabilitate the older journal's measurements.

## Reproduction and evidence

The [results JSON](followup-repairs-2026-10-24-results.json) preserves
acceptance checks and revision-specific summaries. The
[evidence archive](followup-repairs-2026-10-24-evidence.zip) retains raw
records, manifests, commands, failed attempts and verification outputs.
Earlier failures are not pooled into the accepted outcome tables.


Every accepted outcome sample must record the scenario, card edition,
setup options, exact seeds, source digest, command, process exit status and
per-game acceptance. Repeats across hash seeds and replay executions are
reported separately from distinct game cases. Legal declines are counted
separately from rejected actions. Samples using different card editions or
the optional Leader rule are not pooled into one set of faction win rates.

Principal repository commands are:

```sh
python -m pytest -q
PYTHONHASHSEED=0 python -m fs_bot.tools.run_batch --seeds 1-200 --card-edition legacy --workers 4 --out new-legacy-results
PYTHONHASHSEED=0 python -m fs_bot.tools.run_batch --seeds 201-300 --card-edition legacy --workers 4 --out new-heldout-legacy-results
PYTHONHASHSEED=0 python -m fs_bot.tools.run_batch --seeds 201-300 --card-edition original --workers 4 --out new-original-results
PYTHONHASHSEED=0 python -m fs_bot.tools.run_batch --seeds 201-300 --card-edition second-edition --workers 4 --out new-revised-results
PYTHONHASHSEED=0 python -m fs_bot.tools.player_fuzz --seeds 1-40 --card-edition legacy
PYTHONHASHSEED=7 python -m fs_bot.tools.player_fuzz --seeds 1-40 --card-edition legacy
PYTHONHASHSEED=0 python -m fs_bot.tools.error_census --seeds 1-20 --strict
PYTHONHASHSEED=7 python -m fs_bot.tools.error_census --seeds 1-20 --strict
python -m fs_bot.tools.balance_smoke --seeds 1-20
```

The archive retains the complete stage commands and the independent
`verify_matrix.py` extractor. `run_optional_diviciacus.py` supplies the
optional-setup matrix, while the fuzz and census runners retain both hash
seeds and edition-specific outputs. Use fresh output directories and inspect
local interpreter/checkout paths before repeating those scripts.

The validation source digest covers sorted paths and contents of every
`fs_bot/**/*.py` file, including tests. The installed/save engine identity
has a different purpose: it covers engine Python sources excluding tests,
plus the supplied reference bytes. These two digests must not be substituted
for one another. See the [self-play workflow](../../SELFPLAY_PLAYBOOK.md)
and [release guide](../../RELEASES.md) for the tool contracts.

## Unresolved source questions and limits

The same six source questions remain indexed in
[current status](../current-status.md#source-conflicts-still-open) and
[QUESTIONS.md](../../QUESTIONS.md#current-open-source-questions): A30's
missing Belgic instruction; the A8.6.6/A28 faction-name conflict; unused
human Frumentum funding; German-owned A63 after Interlude; automatic Arverni
Harassment order in Ariovistus; and Harassment order during after-Harvest
Winter Campaign actions. Clear surrounding mechanics can be repaired
without inventing answers to those conflicts. Existing documented policies
remain in place. `Reference Documents/**` and `fs_bot/rules_consts.py`
remain unchanged.

Seeded games measure this implementation of the published bot policies.
They do not establish expert-human balance or prove correctness in every
possible position. A clean validation gate supports the tested revision,
seed sets and decisions; later changes need their own checks.
