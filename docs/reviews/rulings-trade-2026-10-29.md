# Rules adoption and human Trade choice — 29 October 2026

Starting revision: `724af60017b4ba959d402168b238065b43f22708`.
Dates use America/Chicago. The preceding Recruit/Rally report retains its
own source identities and results; they do not validate this revision.

## Authority and scope

The owner supplied photographs of both Diviciacus cards and authorized
external research into four outstanding questions. After receiving the
findings, the owner instructed: “Let's go with your recommendations on all
these and continue with the next task on this.”

The replacement O38 photograph places **CAPABILITY** on the boundary between
its effects. [Section 5.3 of the published rules][base-rules] expressly makes both sides Capabilities in this
layout. This resolves the printed-label question and requires the usual
non-player final-year restriction on both sides. The original card 38 has
the same boundary layout but a different unshaded effect. A 2016
[designer interview][interview] described the replacement as placing the
Leader instead of adding a Capability; the finished card and published rule
govern over that pre-release description. No original artwork is
redistributed in this report.

The narrower interaction with Shifting Loyalties remains open: removing
the recorded O38 Capability does not itself instruct removal of Diviciacus.
Existing presence-based Leader rules are retained, without inferring missing
Capability history in old saves. See the [O38 question](../../QUESTIONS.md#q-o38--optional-diviciacus-capability-label-27-october-2026)
for the scope and compatibility limits; this is not a tenth adopted ruling.

The other three questions received adopted provisional project rulings:

| Ruling | Adopted procedure | Evidence and remaining uncertainty |
|---|---|---|
| [PR-07](../provisional-rulings.md#pr-07) | One non-player Aedui Supply roll for the human Roman action, including its accompanying Special Ability; retain the answer during that decision's replanning. | The official base playbook, p.11, binds one agreement over March + Trade and multiple Regions. It does not explicitly specify the bot's die granularity. |
| [PR-08](../provisional-rulings.md#pr-08) | Check the ordinary Rally/Recruit option's prerequisites before its bonus pieces. | Aquitani's notes allow additions even when normal placement is zero; they do not expressly grant bonus-first timing. Explicit printed exceptions still apply. |
| [PR-09](../provisional-rulings.md#pr-09) | For A20, preserve Scouted, other Revealed, Hidden casualty priority; choose uniformly among eligible origin Regions for each tied casualty. | A3.2.4 supplies visibility priority. Equal-origin selection is the adopted interpretation, borrowing the game's equal-Region convention. |

All three remain subject to possible later correction if an authoritative
source is found. Focused searches of GMT materials and indexed discussion
did not locate a direct ruling; this is not a claim that none exists.
The protected references and canonical constants are unchanged.

## Repairs

- Apply the adopted Supply scope without altering human factions' specific
  permission choices or the printed approval thresholds. After a real die
  refusal, rechoose the current Recruit or Build at its actual boundary;
  retain completed effects, the fixed refusal and its replayable RNG receipt.
  Event grants retain their action, Region and funding restrictions, including
  Frost exceptions and the prohibition on an SA with a Britannia March.
- Keep the existing bonus-prerequisite interpretation and add direct
  regression coverage for Aquitani, Nervii and Gallia Togata.
- Apply the O38 final-year classification and capability bookkeeping while
  retaining the physical Leader's separately governed A1.4 rules.
- Preserve exact physical origins of A20 survivors. The review also found
  that a Counterattack could remove local Arverni Allies or Citadels after
  exhausting the projected Warbands. Only participating Warbands may suffer
  these projected losses.
- Expose the human Aedui's single Trade Region under shaded River Commerce,
  with the actual permission, geography and Resource consequences visible
  before the choice. Event-granted Command + Special Ability plans now also
  retain the Event's Region restrictions when the Trade choice is deferred.
  Existing non-player selection remains separate, with the open policy
  question recorded below.

The Supply regressions cover first and later interrupted Recruit portions,
replacement SAs with their actual Diviciacus borrowing choices, and a
completed Build's restrictions on a later Seize. A53 can skip the refused
action without spending or reissuing its allocation. Human Trade previews
use actual possible income, including Subdued Tribes, while the real choice
remains binding even when it earns less than the planned Command needs.

## Validation

Accepted attempt: **attempt3**. All measurements below use the final frozen
source; the rejected attempts are recorded separately.

| Check | Result |
|---|---|
| Full suite, Python 3.12 | **5,777 passed**, no failures or skips; 45.92 seconds reported by pytest |
| Audited bot games | **150/150 completed**: legacy seeds 1–20, original and second-edition seeds 201–205, each across all five scenarios |
| Mixed-seat runs | **80 executions including replay**: 20 cases at hash seeds 0 and 7, each replayed; zero hard or partial findings |
| Strict census | **50 executions**: 25 cases at each hash seed; zero defects |
| Original outcome guard | **Passed**, unchanged 15-percentage-point band and unchanged baseline |

Mixed-seat reports match across hash seeds, with seven rejected random
plans per hash disclosed separately. Census reports also match, recording
345 allowed legal-decline occurrences per hash. Census coverage uses tool
metadata and aggregate completion because it does not emit per-game success
rows. These checks are not complete coverage of human choices or proof of
game balance.

All 150 bot records have completed audits, valid final rankings and no
unexpected diagnostic or integrity findings. The legacy100 comparison
reuses those same audited games; it does not add another run. Against the
older original baseline, 63 winner/card-count records differ (47 winners,
42 card counts), with maximum faction win-rate change exactly 15 points.
Against the immediately preceding source, all 100 winners and card counts
match. That comparison does not establish complete board-state equivalence
or isolate the effects of individual repairs.

Legacy seed 1–20 outcomes, 20 games per scenario:

| Scenario | Romans | Aedui | Arverni | Belgae | Germans |
|---|---:|---:|---:|---:|---:|
| Pax Gallica? | 10 | 6 | 2 | 2 | 0 |
| Reconquest of Gaul | 13 | 4 | 1 | 2 | 0 |
| The Great Revolt | 3 | 3 | 9 | 5 | 0 |
| Ariovistus | 7 | 3 | 0 | 5 | 5 |
| The Gallic War | 10 | 2 | 2 | 6 | 0 |

The [machine-readable results](rulings-trade-2026-10-29.json) include each
edition's summaries and the original-baseline comparison. The
[evidence archive](rulings-trade-2026-10-29-evidence.zip) contains raw games,
replay/census reports, all frozen attempts, independent reviews, fixtures,
source snapshots and runner commands. Archive SHA-256:
`32264630306ba63a73f5117de156081de0fa0599ce3f8205d2f7c1d76a5aade8`
(7,128,802 bytes); member contents were verified after writing.

- Parent: `724af60017b4ba959d402168b238065b43f22708`; fresh baseline full suite:
  **5,622 passed**.
- Final Python source: **349 files**, SHA-256
  `e19896b1e07bbf425ca5e1f7d1db5113e4db6843c3302bc0ef1eb1bd32304bd0`.
- Original balance baseline: SHA-256
  `815b6f363134159b4cf5772abd4dc76a5e8e0be8fd0bb852dc571390504814f5`.
- Digest procedure: sorted repository-relative Python path, NUL, then raw
  file bytes for every `fs_bot/**/*.py` file, concatenated into SHA-256.

All 48 protected reference/constant files, nine non-Python fixture files,
and three runtime configuration files retained their frozen bytes. The
historical compatibility manifest remains
`0e1609c9158d2a2e635eca578681442764b05637200f7000ae5554ccceb060ef`.
The earlier parent-source game records retain their original dirty
`15417ff` run metadata; all 335 Python hashes were independently matched to
committed parent `724af60`. They are comparison evidence, not newly run games.

To reproduce the scoped checks from a configured checkout:

```sh
python -m pytest -q
PYTHONHASHSEED=0 python -m fs_bot.tools.run_batch --seeds 1-20 --card-edition legacy --workers 2 --out /tmp/fs-legacy
PYTHONHASHSEED=0 python -m fs_bot.tools.run_batch --seeds 201-205 --card-edition original --workers 2 --out /tmp/fs-original
PYTHONHASHSEED=0 python -m fs_bot.tools.run_batch --seeds 201-205 --card-edition second-edition --workers 2 --out /tmp/fs-second
```

Run each command below under both `PYTHONHASHSEED=0` and
`PYTHONHASHSEED=7`, using separate output files, and compare their JSON:

```sh
python -m fs_bot.tools.player_fuzz --seeds 1-4 --card-edition legacy --out /tmp/fs-fuzz.json
python -m fs_bot.tools.error_census --seeds 1-5 --card-edition legacy --strict --out /tmp/fs-census.json
```

## Rejected implementation candidates

The second full-suite attempt on digest
`fe3321fdca3645393db61e180caa6b72612cd4ae541c05acbc7dcc6f68896b2c`
reported **5,775 passed and 1 failed** in 46.32 seconds. The earlier approval
fix returned before recording a forecast dependency. During free Recruit
replanning, that omission discarded the confirmation of a genuine approval.
The final repair preserves both the binding permission and dependency
registration, with the original failing test unchanged and an added purity
regression. `attempt2` retains its exact source and raw results; no simulation
matrix ran on it.

The first full-suite attempt on digest
`2ac9bf0ebdc8a8eacd9a1d705f65381a1851ffd69cad6aa48c1310910389874b`
reported **5,769 passed and 5 failed** in 46.20 seconds. Two failures exposed
a real compatibility regression: reconsideration's dependency forecast
discarded an already accepted Supply permission and could replace it with
a new refusal. Three failures were timing-test mocks that did not accept
the newly forwarded Event-grant keyword. The existing timing assertions
remain unchanged. The exact source, fixtures, raw test output and earlier
focused-review result are preserved under `attempt1`. No simulation matrix
ran on that failed source.

The first Supply reconsideration candidate, Python digest
`f4d20480172a4ea13d8b26e58a2c1b5993e6238a476486308c7c4e711cc6be70`,
passed its focused checks but failed independent review before any full
suite or simulation matrix ran. Its forecast included an accompanying
Build's dependencies and could therefore offer a whole Command replacement
when only Build needed permission. It also resolved the permission before
a preceding Special Ability could change the actual board and Roman score.
All 347 Python files from that candidate and the review disposition are
retained in the evidence as `attempt0-boundary-review`; its focused results
do not validate the final implementation.

Review of the subsequent refactor reproduced two further defects: replacing
one interrupted Recruit portion could duplicate a Region in the other
portion, and changing Build to Scout could execute with the original
Build's Diviciacus borrowing context. Both are fixed and have regressions in
the final implementation. The exact intermediate source for those two failures was
not frozen before edits continued; reproduction notes and the correction
record are retained separately, without claiming a reconstructed snapshot.

## Remaining implementation work

The separate voluntary-removal review found that §1.4.1 is broader than
reclaiming a piece when its pool is empty. A player faction executing its
Sequence-of-Play Command/Event may remove its own pieces, return Legions
to their track, or downgrade a Citadel to an Allied Tribe. The permanent
Provincia Fort and borrowed German pieces are excluded; non-players never
voluntarily remove their pieces. Diviciacus follows his special removal
rule. Physical ownership must remain distinct from effective borrowed
forces.

A start-of-action-only menu would leave the printed within-action freedom
unfinished. This batch therefore closes the discrete River Commerce choice
and leaves voluntary removal for its own implementation, with those source
findings recorded here. Three known interface gaps remain:

1. Voluntary own-piece removal and Citadel downgrades throughout the legal
   Command/Event timing windows.
2. Vercingetorix entering from the Spring box during a resolving action.
3. A Special Activity between Vercingetorix's two Rally options within one
   Region.

The source-derived completeness audit also remains. This is a list of known
gaps, not a claim that every other position or interaction is correct.

The Trade review also identified a separate non-player policy question:
whether §8.3.3's first-applicable Region under a limited-Region Capability
can be a zero-income Region when §8.6.3 calls for all obtainable Trade
Resources. Existing non-player selection is preserved pending review; see
[Q-TRADE-NP-REGION](../../QUESTIONS.md#q-trade-np-region--shaded-river-commerce-selection-29-october-2026).
This is not an additional adopted provisional ruling.

[interview]: https://theplayersaid.com/2016/10/03/interview-with-volko-ruhnke-co-designer-of-ariovistus-a-falling-sky-expansion-by-gmt-games/
[base-rules]: https://gmtwebsiteassets.s3-us-west-2.amazonaws.com/FallingSky/FS_Rules_2018.pdf
