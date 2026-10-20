# Falling Sky Vassal module comparison

Review date: 2026-10-20 UTC. Repository starting point:
`d34e3f358e3435394a5c4b6c60f22bed2ebf59e9`.

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

This is a focused comparison against the current GitHub main branch. It is not
the final report for the earlier comprehensive source-first audit. Workspace
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

### Unresolved differences

1. **A30 Orgetorix:** its physical face has Belgic laurels, but the transcribed
   header and supplied Belgic instructions provide no corresponding special
   instruction. No instruction or new bot behavior was invented.
2. **Card edition policy:** Vassal uses revised cards 11/30/39/44/54 globally.
   A Setup recommends doing so regardless of scenario, while the bot ties
   amendments to Ariovistus. This leaves base games using original versions
   despite the project's Second Edition description. A saved edition policy
   would need to cover display, effects, previews, targeting, capabilities
   and Interlude consistently. No default was silently changed.

Both issues are recorded in `QUESTIONS.md` with sources, alternatives,
consequences and blocked decisions. A65's physical wording still says
“without Leader”; the module does not resolve that earlier wording ambiguity.

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
  identified missing borrowed-Warband Enlist option on current main. That
  broader Command-ownership implementation remains unfinished; a cosmetic
  marker would not repair it.
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

## Verification

Starting main: 2,509 tests passed. The 1,000-game baseline (five scenarios,
seeds 1–200, hash seed 0) completed without crashes, integrity findings,
diagnostics, or winner/ranking disagreements. All 61 new regression cases
were also run against unchanged main: 43 failed and 18 passed, confirming
that the tests detect the original defects and preserve unaffected branches.

The corrected engine passed **2,570 tests**, including **61 new parameterized
regression cases** (32 Senate, 19 Razed, 10 card cues). The revised 1,000-game
set and held-out 100 games all completed with zero crashes, illegal-action
diagnostics, conservation/structural findings, missing rankings or
winner/ranking disagreements. Every record includes a final-state SHA-256.

### Before/after outcomes: 200 bot-only games per scenario

| Scenario | Original wins | Corrected wins | Mean cards, original → corrected |
| --- | --- | --- | --- |
| Pax Gallica? | Aedui 4, Arverni 14, Belgae 25, Romans 157 | Aedui 6, Arverni 9, Belgae 27, Romans 158 | 34.040 → 33.740 |
| Reconquest of Gaul | Aedui 8, Arverni 18, Belgae 27, Romans 147 | Aedui 9, Arverni 7, Belgae 33, Romans 151 | 29.705 → 29.140 |
| The Great Revolt | Aedui 14, Arverni 75, Belgae 60, Romans 51 | Aedui 13, Arverni 71, Belgae 61, Romans 55 | 43.315 → 43.395 |
| Ariovistus | Aedui 21, Belgae 27, Germans 46, Romans 106 | Aedui 28, Belgae 20, Germans 34, Romans 118 | 36.870 → 36.785 |
| The Gallic War | Aedui 17, Arverni 32, Belgae 55, Romans 96 | Aedui 14, Arverni 24, Belgae 47, Romans 115 | 55.155 → 57.460 |

These are frequencies for this deterministic bot implementation, not estimates
of human-game balance. The source-correct reinforcement/scoring changes alter
game trajectories. The same 60-game CI baseline was regenerated exactly,
without changing tolerances: five winners and six game records changed. An
isolated Senate-only run reproduced every changed baseline record, confirming
that the baseline drift is explained by the reinforcement correction.

Nineteen fixed representative replays matched winner, card count, final
ranking, diagnostics and final-state hash exactly. They cover all scenarios,
short/long games, Interlude, simultaneous qualifiers, final Winter, Optimates
and changed trajectories. The full case list is in the outcome-summary JSON.

All 32 CI synchronization games passed. Mixed-seat seeds 1–40 (200 games
per hash seed) produced byte-identical output under hash seeds 0 and 7:
digest `e9993af920d81523`, 6,440 human turns, 1,746 Event turns, 1,717
successful Events, zero hard findings, 507 soft partial-action notices.
Soft telemetry was preserved.

The three code commits passed all four GitHub CI jobs on Python 3.10:
tests, balance-guardrail, sync-sweep and player-fuzz
([run 39351571390](https://github.com/FeeSimple1/fs-bot/actions/runs/39351571390)).
Local verification used Python 3.12.14. The final 1,000-game batch was run
before committing the tested working tree; its metadata therefore records
the starting commit plus a dirty flag. Its source SHA-256
`f4734c26a8cd44226b5e3074fd380a67a2107d7566355f03ee90893506ce23ec`
matches the committed engine exactly.

The scheduled-depth strict census completed 2,500 bot-only games under each
of hash seeds 0 and 7 (five scenarios, game seeds 1–500). Both runs reported
zero incidents of any severity, exited successfully, and produced identical
logs and detailed JSON. Their common log SHA-256 is
`91b5fa60266791b0e4e3716edc2dbd1cc211d9db894ddc5ffaf41d159909cc82`.
Source digests remained unchanged throughout both runs.

The extended mixed-seat soak (seeds 1–300 under both hash seeds, with each
case internally replayed), informational telemetry, and final integration
results are recorded on [pull request #35](https://github.com/FeeSimple1/fs-bot/pull/35)
and in the accompanying raw verification archive. The archive retains
commands, exit statuses, source digests and unfiltered diagnostic totals.

### Reproduction

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
match `.github/workflows/ci.yml` and `deep-soak.yml` exactly, with both
hash-seed outputs compared. No assertion, legality guard or tolerance was
weakened. Reproduction helper operates on existing audited `run_batch.play_one`.

### Commits and integration

- A24/A70 cues: `8cca43322f1625c740d88671228e1cd9dc0c86c7`.
- Senate corrections and exact baseline: `f44707a1ecb781be02e2040414f477fc5ec6d61e`.
- Razed scoring: `04ced84db28224e077b4b9a038c8c977a241eecd`.
- [Pull request #35](https://github.com/FeeSimple1/fs-bot/pull/35).
- Final report-head CI and merge verification are recorded on the pull request
  and in the accompanying raw verification archive's `integration.json`.
