# Provisional rulings: implementation and validation, 24 October 2026

The owner adopted all six recommended interpretations on 24 October 2026
(America/Chicago). They now govern this project's behavior. **Every ruling
remains subject to possible later correction if an authoritative source is
found.** This is an implementation decision, not new official errata or
designer confirmation. The [ruling register](../provisional-rulings.md)
preserves the policies, rationale and source references; the
[question ledger](../../QUESTIONS.md#current-open-source-questions) preserves
the external questions.

## Implementation

| Ruling | Adopted behavior and regression coverage |
|---|---|
| [PR-01: A30 Orgetorix](../provisional-rulings.md#pr-01) | Ignore the extra Belgic laurels and use ordinary shaded Event instructions. Existing behavior retained and the cue pinned by regression. |
| [PR-02: A28 agreements](../provisional-rulings.md#pr-02) | Non-player Aedui and Belgae lend only in Regions where the executor contributes its own participating pieces. Planning, preview and execution share the policy. Non-player Romans refuse; humans choose; Arverni participation remains automatic. |
| [PR-03: A53 funding](../provisional-rulings.md#pr-03) | Romans retain unused transferred funding, subject to the Resource cap. Existing behavior retained; zero, fully unused and capped funding cases covered. The public `legacy_roman_retention` result label remains compatible. |
| [PR-04: German-owned A63](../provisional-rulings.md#pr-04) | Resolve the final German activation before the Interlude transition, retain German ownership, then leave it dormant in the base-game half. A regression performs both paid Marches, the actual transition, and save/resume. |
| [PR-05: Ariovistus Harassment](../provisional-rulings.md#pr-05) | Follow the current Event's printed order with Germans in their proper slot, then automatic Arverni last. All Harassment callers share the ordering helper. |
| [PR-06: Winter Harassment](../provisional-rulings.md#pr-06) | Use the last actually played non-Winter card, including all-pass cards, with the game-run faction last. Recover it from saved `played_cards`; never use an unplayed upcoming card. |

The A28 work exposed an additional defender-lender bug: an explicit plan could
borrow Warbands belonging to the very faction being attacked. Default and
explicit plans now reject that combination. Focused regressions also cover
the preview when the only potential lenders must refuse, so Event selection
cannot promise a Battle that execution will decline.

Winter ordering does not replace `current_card`, change eligibility, consume
randomness or add a save field. If an old or manually built state has no
recoverable non-Winter card, the explicit compatibility fallback is the
current scenario's Winter Campaign order (63/A63), with the game-run faction
last. This fallback does not claim to reconstruct missing history. The
Interlude's Winter actions use the first half's history before the deck
rebuild clears it; the next half then uses its own played cards.

## Tested source

Validation ran with Python 3.12.14 on a working tree based on commit
`aea03e574868499eece5a11070b9b09f9b50b76b`, with `dirty: true` because the
adopted changes had not yet been committed. The base commit alone therefore
does not identify the tested implementation.

| Identity | SHA-256 |
|---|---|
| Validation source, all `fs_bot/**/*.py` including tests | `647b8bcf316d536f1b4ea6a1b81b692a473f824d244c6dac53e3a48c198a5e46` |
| Engine compatibility identity | `b7d52b16211a0d910c942a6e019d0ab2d160b88460e1566cd1d126ab9cf52cc4` |

Both identities were unchanged across validation. The validation digest
hashes sorted repository-relative Python paths and their bytes. The engine
identity instead excludes tests, uses package-relative paths, and includes
protected reference documents; these are intentionally different digests.

## Completed validation

Every game matrix below covers **Pax Gallica?**, **The Great Revolt**,
**Reconquest of Gaul**, **Ariovistus**, and **The Gallic War**.

| Check | Scope | Result |
|---|---|---|
| Full test suite | Entire repository suite | **4,481 passed**, 115.35 seconds |
| Audited bot matrix | 200 games across five scenarios and three edition profiles | **200/200 completed**; no errors, integrity findings, nonlegal diagnostics or winner/ranking disagreements |
| Mixed-seat execution and replay | 80 scenario/seed/edition cases, each at hash seeds 0 and 7 and replayed: 320 executions | **320/320 completed**; no hard findings or soft partial plans; complete JSON, stdout and stderr byte-identical between hash seeds for each profile |
| Strict census | Seeds 1–4 in five scenarios at hash seeds 0 and 7: 40 executions | **40/40 completed**; no failures or defect incidents; full reports byte-identical |
| Balance guardrail | Seeds 1–20 in five scenarios: 100 games | **Passed**; all win rates unchanged and the baseline was not updated |

The audited bot matrix comprises these separate samples, all launched with
`PYTHONHASHSEED=0`:

| Card edition | Seeds per scenario | Games | Cards | Decisions | Completed Interludes |
|---|---|---:|---:|---:|---:|
| `legacy` | 1–20 | 100 | 4,102 | 7,630 | 12 |
| `original` | 201–210 | 50 | 2,147 | 3,986 | 7 |
| `second-edition` | 201–210 | 50 | 2,169 | 4,026 | 8 |
| Total | | **200** | **8,418** | **15,642** | **27** |

Exact scenario/seed coverage and every game record were inspected, and each
summary was independently recalculated. All processes exited successfully
with empty stderr. The 1,985 legal declines are permitted choices, not
rejected illegal actions. All 100 legacy `(winner, cards)` pairs also exactly
match the existing baseline; that read-only comparison is separate from the
completed balance command.

Mixed-seat runs used legacy seeds 1–10 and original/second-edition seeds
201–203. Their 160 primary executions include both hash seeds; the matching
replays bring the total to 320. The census recorded 143 legal declines per
hash-seed run and no defect-severity incidents. These overlapping seeded
checks are not pooled into a count of independent statistical observations.

The [machine-readable results](provisional-rulings-2026-10-24-results.json)
record the acceptance checks and exact source identity. The
[raw evidence archive](provisional-rulings-2026-10-24-evidence.zip) contains
55 entries with commands, logs, per-game records, summaries and audits.
The 115,282-byte archive has SHA-256
`7bf2ab56f07147c709a7486e541f1b3b6a3fb75f2bf58ba5a726444ab39b3884`.

## Reproduction

From the repository root, using the tested revision and an environment with
the development requirements installed, write outputs to a new directory:

```sh
python -m pytest -q
mkdir provisional-rulings-validation
PYTHONHASHSEED=0 python -m fs_bot.tools.run_batch --seeds 1-20 --card-edition legacy --workers 4 --out provisional-rulings-validation/bots-legacy
PYTHONHASHSEED=0 python -m fs_bot.tools.run_batch --seeds 201-210 --card-edition original --workers 4 --out provisional-rulings-validation/bots-original
PYTHONHASHSEED=0 python -m fs_bot.tools.run_batch --seeds 201-210 --card-edition second-edition --workers 4 --out provisional-rulings-validation/bots-second-edition
python -m fs_bot.tools.balance_smoke --seeds 1-20
for hash_seed in 0 7; do
    PYTHONHASHSEED="$hash_seed" python -m fs_bot.tools.error_census --seeds 1-4 --strict --out "provisional-rulings-validation/census-hash${hash_seed}.json"
    PYTHONHASHSEED="$hash_seed" python -m fs_bot.tools.player_fuzz --seeds 1-10 --card-edition legacy --out "provisional-rulings-validation/fuzz-legacy-hash${hash_seed}.json" > "provisional-rulings-validation/fuzz-legacy-hash${hash_seed}.stdout" 2> "provisional-rulings-validation/fuzz-legacy-hash${hash_seed}.stderr"
    for edition in original second-edition; do
        PYTHONHASHSEED="$hash_seed" python -m fs_bot.tools.player_fuzz --seeds 201-203 --card-edition "$edition" --out "provisional-rulings-validation/fuzz-${edition}-hash${hash_seed}.json" > "provisional-rulings-validation/fuzz-${edition}-hash${hash_seed}.stdout" 2> "provisional-rulings-validation/fuzz-${edition}-hash${hash_seed}.stderr"
    done
done
cmp provisional-rulings-validation/census-hash0.json provisional-rulings-validation/census-hash7.json
for edition in legacy original second-edition; do
    for suffix in json stdout stderr; do
        cmp "provisional-rulings-validation/fuzz-${edition}-hash0.${suffix}" "provisional-rulings-validation/fuzz-${edition}-hash7.${suffix}"
    done
done
```

Default `player_fuzz` settings enable Events, reactive decisions and replay.
After rerunning the bot matrix, inspect record-level errors, integrity,
diagnostics and rankings as well as completion counts; exit status alone
does not establish acceptance. See the [self-play workflow](../../SELFPLAY_PLAYBOOK.md)
for the audit contract.

## Scope and limits

These results validate the identified implementation on the named cases;
they do not establish that the six interpretations are official or that
every legal position has been exercised. Seeded bots and generated human
choices are not expert play, and these small samples are not a new balance
study. The prior [24 October follow-up report](followup-repairs-2026-10-24.md)
and [23 October report](outstanding-fixes-2026-10-23.md) retain their own
measurements, including older installation and remote-CI checks.

This report records local checks before publication. Remote CI is not part
of that local acceptance claim; the [GitHub Actions runs](https://github.com/FeeSimple1/fs-bot/actions)
for the commit introducing these changes are the authoritative record of
its remote checks. A later passing workflow should not be inferred from
this report or from an older commit's result.
