# Falling Sky Vassal module comparison

Review date: 2026-10-20 UTC. Repository starting point:
`d34e3f358e3435394a5c4b6c60f22bed2ebf59e9`.

**Historical comparison.** Findings, test counts, outcome tables and source
digests below describe this review's revisions. See
[current engineering status](../current-status.md) and the
[23 October validation report](outstanding-fixes-2026-10-23.md) for current
behavior and results. The [dated addendum](#later-dispositions--23-october-2026)
below identifies which previously unresolved implementation items were fixed;
the original measurements remain unchanged.

## Scope and evidence

The owner explicitly requested this external comparison. Vassal is a secondary
cross-check; its automation is not a rules oracle. The printed board/card images
can supply visual details missing from the repository transcriptions. Confirmed
engine corrections below cite both the relevant visual evidence and the rules.
`Reference Documents/**` and `fs_bot/rules_consts.py` remain unchanged.

- [Module project and release notes](https://vassalengine.org/library/projects/Falling_Sky_The_Gallic_Revolt_Against_Caesar).
- [Examined package: FallingSky4.0.0.vmod](https://obj.vassalengine.org/gls/1/e/FallingSky4.0.0.vmod), published 2026-05-24.
- SHA-256: `1e5cc5aff7167720bfc47326a8acd5e44e31e0364587f1a69225b4257248ae27`.
- Internal name: Falling Sky (2nd Edition); module version 4.0.0; Vassal 3.7.19.
- Method: archive inspection, XML configuration analysis, visual inspection of
  extracted artwork, card OCR checked against images where relevant, and engine
  reproductions/regression tests. No claim of interactive play in Vassal.
- Artwork/module binaries are not redistributed in this repository.

This was a focused comparison against GitHub main as checked out for this
review. It is not the final report for the earlier comprehensive source-first audit. Workspace
maintenance removed that audit's local checkout and unpushed work; its branch
and checkpoint were not present in the fetched remote, and a Library search
did not recover them. The earlier audit must not be represented as completed
or merged on the strength of this review.

## Findings

### Corrected: Senate row alignment and Ariovistus release limit

The actual board (`images/FS_Map_VASSAL reize.jpg`, SHA-256
`12c3cfb4a361f844673d5d5642480a4f9db5e383119212ca8b80dc35d86df5d8`)
aligns the three Legion rows with Uproar, Intrigue and Adulation. XML
corroborates this: `buildFile.xml` lines 34–45 place the Legion rows at
y=1914/2062/2211; Senate zones at lines 96–98 encompass those respective
coordinates. There is no Legion row below Adulation.

Chapter 6 §6.5.2, lines 133–140, releases Legions on the marker's row or
above. Chapter A6 §A6.5.2, lines 163–165, limits releases from Intrigue
and/or Adulation to two combined. Uproar-row Legions are not capped.

| Senate position | Eligible rows | Base release from full track | Ariovistus release from full track |
| --- | --- | ---: | ---: |
| Uproar | Top | 4 | 4 |
| Intrigue | Top + Middle | 8 | 6 |
| Adulation | Top + Middle + Bottom | 12 | 6 |

Old behavior shifted the row map one position and capped the entire
Ariovistus release at two. Both defects could withhold Roman reinforcements.
`winter.py` now uses the printed alignment, releases all eligible Top-row
Legions, and shares a two-Legion budget across eligible lower rows.

Regression: `test_vassal_senate.py`, 32 cases, plus corrected obsolete
expectations in `test_winter.py`. Cases include all five scenarios, each
Senate position, ineligible lower rows, Fallen recovery, lower-row shared
budget, conservation, control, resources, eligibility, and RNG nonmutation.
The protected constants file retains stale explanatory comments at its
Legion cap/row declarations; canonical values were not changed.

### Corrected: Razed victory scoring

Vassal's Razed trait (`buildFile.xml` line 515, gpid1106) and its historical
Razed scoring fix prompted a check of Card 23. Card Reference lines 226–236
explicitly make Razed equivalent to Dispersed except for Spring cleanup.
Chapter 7 §7.2 defines the Roman and Belgic formulas; Chapter 6 §6.6 retains
Razed in Spring.

`victory.py` omitted Razed from both Roman Dispersed totals and the deduction
from Belgic-controlled population. Consequently razing a Subdued city could
reduce Rome's score by one and leave an extra Belgic control point. Both
formulas now include Razed. Nineteen new cases in `test_vassal_razed.py`
exercise the actual Sacking Event, all three base scenarios, previous tribe
statuses, changed control, unchanged scoring inputs/RNG and Spring persistence.

### Corrected: A24 and A70 card cues

All 72 base Event headers and 39 expansion Event headers were visually
compared with metadata. Faction orders match; all 24 separate expansion
Arverni-trigger carnyx symbols match. Three cards had NP-cue discrepancies.

| Card | Corrected cues | Corroborating repository source |
| --- | --- | --- |
| A24 Seduni Uprising! | Germans laurels; Romans swords; Belgae none; Aedui swords | German specific instruction; Roman/Aedui No Event lists; Belgic list |
| A70 Nervii | Added Aedui and Roman laurels; preserved German swords and separate carnyx | Roman/Aedui conditional Nervii instructions |

`card_data.py` and `card_text.py` reconcile these two inconsistent headers
with the faction instruction files and physical card faces. Full effect
paragraphs remain untouched. The bot instruction tables already prescribed
the correct choices; this fixes the information shown to humans, not a
demonstrated change in bot Event execution. Ten new cases in
`test_vassal_card_cues.py` check metadata, briefing text, body preservation,
instruction dispositions, trigger separation and base-card isolation.

### Corrected: relocation and human-menu defects found by the stress run

The initial extended mixed-seat run exposed 33 structural findings, all
following Card 32 in Great Revolt seed 213, with Arverni and Belgae human
seats. Both hash seeds reproduced the same failure. Forced Marches accepted
two Arverni Allies moving from Sequani to Aedui, leaving their Tribe records
behind. Card Reference lines 319–325 permits mobile forces only.

An isolated checkout containing only the Card 32 correction, retaining the
original menus and all other Event handlers, replayed those exact inputs
without corruption. Both hash seeds then reported zero hard findings, four
soft partial notices and digest `0ed0534c71bc9c1a`. The original failure and
before/after traces are retained in the verification archive.

The correction and a narrow review of the same relocation pattern cover:

- **Forced Marches (32):** only mobile forces move; counts and the complete
  movement list are validated before mutation. Original pieces are reserved
  before relocation, and visibility changes are deferred so an arriving
  Scouted Warband cannot be moved again to hide it in the same Event.
  Unmoved destination pieces retain their visibility.
- **War Fleet (62):** only the executing Faction's mobile forces move, between
  the card's allowed playable Regions; invalid later selections cannot leave
  earlier moves applied. Source: Card Reference lines 637–643 and A1.3.4.
- **Migration shaded (66):** the human may select a Gallic beneficiary;
  only its Warbands/Leader relocate to one initially uncontrolled Region.
  Earlier arrivals gaining Control do not stop subsequent arrivals. Leader
  identity is preserved, and the following Ally placement respects tribe
  restrictions. Sources: Card Reference lines 676–684, §§1.4.2/5.1.
- **Human parameter menus:** relocation menus restrict piece types and
  relevant Region choices. Hostages (22) and Alpine Tribes (40) had also
  applied piece-type restrictions to every field of an entry, offering such
  values as “Warband” for Regions and counts. Restrictions now apply only
  to their intended field kind, while handlers remain authoritative.

Ninety further regression cases were added: 33 for Card 32, 47 for Cards
62/66, and 10 for human/menu schema choices. The initial 19 Card 32 cases
gave 13 failures against its old implementation; the 47 Card 62/66 cases
gave 24 failures against their old handlers; all seven initial menu cases
failed before the menu correction. These are defects discovered during
verification of this review, not claims that Vassal automates these Events.

### Differences open at the time of this review

1. **A30 Orgetorix:** its physical face has Belgic laurels, but the transcribed
   header and supplied Belgic instructions provide no corresponding special
   instruction. No instruction or new bot behavior was invented.
2. **Card edition policy:** Vassal uses revised cards 11/30/39/44/54 globally.
   A Setup recommends doing so regardless of scenario, while the bot ties
   amendments to Ariovistus. This leaves base games using original versions
   despite the project's Second Edition description. A saved edition policy
   would need to cover display, effects, previews, targeting, capabilities
   and Interlude consistently. No default was silently changed.

Both issues were recorded in `QUESTIONS.md` with sources, alternatives,
consequences and blocked decisions. See the later dispositions below. A65's
physical wording still says “without Leader”; the module does not resolve that earlier wording ambiguity.

## What the module can and cannot establish

- It supplies useful board geometry, card faces, inventory artwork, and
  setup spot checks. German Settlement and Ally displays separately show
  six slots each. Belgic forces show ten Allies and one Citadel; raw XML
  counter maxima must not be mistaken for piece limits.
- Its four presets cover Great Revolt, Reconquest, Pax Gallica and Ariovistus.
  There is no distinct Gallic War save. Base presets retain older internal
  version metadata; they were not exhaustively equated to engine setup.
- It deliberately omits solitaire charts and does not implement the bot
  flowcharts. Aedui and Germanic victory require manual tracking.
- Enlist marking does not recalculate control automatically; the module
  offers a manual Belgic-control override. This corroborates the previously
  identified missing borrowed-Warband Enlist option at the review's starting
  revision. That broader Command-ownership implementation was unfinished then;
  its later correction is recorded in the addendum below.
- Combined-game transition requires manual card and Nori/Cisalpina cleanup.
  This suggests useful Interlude tests but does not prove the engine's full
  transition correct.
- Static Spring wiring does not automatically delete Intimidated markers;
  the bot already does so correctly under A6.6. Ordinary Dispersed/Gathering
  sequencing and strict-majority control agree with the rules and engine.
- Expansion Capability cards lack the same owner/side menus as base
  Capabilities, and the package lacks an O38 Diviciacus-Leader card slot.
  Those module limitations must not be copied into the bot.
- Existing `b`/`board`, current/upcoming full-card text, and per-human changes
  remain available in the CLI. Vassal's freely movable pieces do not validate
  all legal Command/Special Activity timing or human choice surfaces.

## Verification of the October 20 review revisions

Starting main: 2,509 tests passed. The 1,000-game baseline (five scenarios,
seeds 1–200, hash seed 0) completed without crashes, integrity findings,
diagnostics, or winner/ranking disagreements. All 61 new regression cases
were also run against unchanged main: 43 failed and 18 passed, confirming
that the tests detect the original defects and preserve unaffected branches.

The final engine passed **2,660 tests**, including **151 new parameterized
regression cases** (32 Senate, 19 Razed, 10 card cues, 90 relocation/menu).
The revised 1,000-game
set and held-out 100 games all completed with zero crashes, illegal-action
diagnostics, conservation/structural findings, missing rankings or
winner/ranking disagreements. Every record includes a final-state SHA-256.

### Before/after outcomes: 200 bot-only games per scenario

| Scenario | Original wins | Corrected wins | Mean cards, original → corrected |
| --- | --- | --- | --- |
| Pax Gallica? | Aedui 4, Arverni 14, Belgae 25, Romans 157 | Aedui 6, Arverni 9, Belgae 27, Romans 158 | 34.040 → 33.740 |
| Reconquest of Gaul | Aedui 8, Arverni 18, Belgae 27, Romans 147 | Aedui 9, Arverni 7, Belgae 33, Romans 151 | 29.705 → 29.140 |
| The Great Revolt | Aedui 14, Arverni 75, Belgae 60, Romans 51 | Aedui 13, Arverni 71, Belgae 60, Romans 56 | 43.315 → 43.395 |
| Ariovistus | Aedui 21, Belgae 27, Germans 46, Romans 106 | Aedui 28, Belgae 20, Germans 34, Romans 118 | 36.870 → 36.785 |
| The Gallic War | Aedui 17, Arverni 32, Belgae 55, Romans 96 | Aedui 14, Arverni 24, Belgae 47, Romans 115 | 55.155 → 57.460 |

These are frequencies for this deterministic bot implementation, not estimates
of human-game balance. The source-correct reinforcement/scoring changes alter
game trajectories. The same 60-game CI baseline was regenerated exactly,
without changing tolerances: five winners and six game records changed. An
isolated Senate-only run reproduced every changed baseline record, confirming
that the baseline drift is explained by the reinforcement correction.
The subsequent relocation/menu fixes preserve that exact 60-game baseline.
Across the 1,000-game comparison they change only Great Revolt seed 55's
final state, including its winner from Belgae to Romans.
The isolated Card 32-only correction reproduces that final state exactly.

Nineteen fixed representative replays matched winner, card count, final
ranking, diagnostics and final-state hash exactly. They cover all scenarios,
short/long games, Interlude, simultaneous qualifiers, final Winter, Optimates
and changed trajectories. The full case list is in the outcome-summary JSON.

Before the relocation/menu follow-up, all 32 CI synchronization games passed.
Mixed-seat seeds 1–40 (200 games
per hash seed) produced byte-identical output under hash seeds 0 and 7:
digest `e9993af920d81523`, 6,440 human turns, 1,746 Event turns, 1,717
successful Events, zero hard findings, 507 soft partial-action notices.
Soft telemetry was preserved.

The initial three code commits passed all four GitHub CI jobs on Python 3.10:
tests, balance-guardrail, sync-sweep and player-fuzz
([run 39351571390](https://github.com/FeeSimple1/fs-bot/actions/runs/39351571390)).
Local verification used Python 3.12.14. Batch metadata records the checked-out
commit, dirty flag and an independent digest of all engine/test Python files,
so results run before a commit still identify the exact tested content.
The first corrected batch's source SHA-256 was
`f4734c26a8cd44226b5e3074fd380a67a2107d7566355f03ee90893506ce23ec`;
the final relocation/menu-corrected source is
`3c129c2af14ff60add5e7dc568dcd8324fe1480e784d7437e5cd0f1082828aff`.

The first scheduled-depth strict census completed 2,500 bot-only games under each
of hash seeds 0 and 7 (five scenarios, game seeds 1–500). Both runs reported
zero incidents of any severity, exited successfully, and produced identical
logs and detailed JSON. Their common log SHA-256 is
`91b5fa60266791b0e4e3716edc2dbd1cc211d9db894ddc5ffaf41d159909cc82`.
Source digests remained unchanged throughout both runs.

The final extended mixed-seat soak uses the unchanged canonical runner,
split into the five scenarios: seeds 1–300 under both hash seeds, each case
internally replayed, each scenario's two outputs compared byte-for-byte.
Final strict census, mixed-seat, informational telemetry and integration
results are recorded on [pull request #35](https://github.com/FeeSimple1/fs-bot/pull/35)
and in the accompanying raw verification archive. It retains the original
failure as well as commands, exit statuses, source digests and unfiltered
diagnostic totals from the corrected runs.

### Reproduction

The commands below describe this historical workflow. Reproducing its tables
requires the review's original source revision and raw archive identified
above. Running the tools on a later checkout is a new experiment and needs a
fresh output directory. Use the [23 October report](outstanding-fixes-2026-10-23.md#reproduction-and-evidence)
for reproduction of the newer accepted matrix.

```sh
python -m pytest -q
PYTHONHASHSEED=0 python -m fs_bot.tools.run_batch --games 200 --workers 4 --out results/final-1000
PYTHONHASHSEED=0 python docs/reviews/verify_vassal_batches.py check --data-dir results
PYTHONHASHSEED=0 python docs/reviews/verify_vassal_batches.py heldout --data-dir results
PYTHONHASHSEED=0 python docs/reviews/verify_vassal_batches.py replay --data-dir results
python -m fs_bot.tools.balance_smoke --seeds 1-20
```

For replay selection, retain the original-main run in `results/baseline-1000`
using the same batch command on the starting commit. Sync/fuzz/soak commands
use the canonical tools and seed ranges from `.github/workflows/ci.yml` and
`deep-soak.yml`, with both hash-seed outputs compared. The final long fuzz
run adds `--scenario` to shard the same coverage for parallel execution.
No assertion, legality guard or tolerance was
weakened. Reproduction helper operates on existing audited `run_batch.play_one`.

### Commits and integration

- A24/A70 cues: `8cca43322f1625c740d88671228e1cd9dc0c86c7`.
- Senate corrections and exact baseline: `f44707a1ecb781be02e2040414f477fc5ec6d61e`.
- Razed scoring: `04ced84db28224e077b4b9a038c8c977a241eecd`.
- The subsequent relocation/menu corrections and their regressions are included
  in the same pull request; the final tested head is recorded there.
- [Pull request #35](https://github.com/FeeSimple1/fs-bot/pull/35).
- Final report-head CI and merge verification are recorded on the pull request
  and in the accompanying raw verification archive's `integration.json`.

## Later dispositions — 23 October 2026

| Earlier item | Current disposition | Implementation/regressions |
|---|---|---|
| Saved card-edition policy | Implemented. `--card-edition original`, `second-edition`, or `legacy` controls the five optional revised cards' text, effects and planning consistently. Explicit profiles persist through saves and Interlude; the default `legacy` retains scenario-based behavior. | `fs_bot/cards/edition.py`; `test_card_edition.py`; [playing guide](../../PLAYING.md) |
| Borrowed-Warband Enlist | Implemented. Borrowed German pieces keep physical ownership through Command execution, movement, Control and casualties; human board/delta views distinguish borrowed use from ownership. | `test_enlist_borrowed.py`, `test_enlist_free.py`, `test_borrowed_force_display.py` |
| A65 Kinship, “without Leader” | The corrected Battle grant leaves the attacking Leader physically present but excludes it from fighting and absorbing losses. A human executor chooses the beneficiary and selected Regions; non-player restrictions remain scoped to their printed instructions. | `fs_bot/battle/excluded_leader.py`; `test_kinship.py`, `test_kinship_decisions.py` |
| A30 Belgic laurels | Still unresolved. The icon does not supply the missing special instruction. | [Current source questions](../current-status.md#source-conflicts-still-open) and [decision ledger](../../QUESTIONS.md) |

Later work also corrected human action ownership, March/Harassment identity,
Quarters, Winter Campaign and additional Events. The
[23 October report](outstanding-fixes-2026-10-23.md) records those changes and
new test results. Its broader nested-action census detects paths the earlier
instrument did not cover, so this historical report's zero-diagnostic totals
are not a completeness claim about all Events or human choices.

The later corrections do not retroactively complete the earlier lost audit
mentioned under Scope and evidence. They have their own commits, regressions,
source digest and accepted matrix. No Vassal package or rules transcription was
modified as part of this documentation update.
