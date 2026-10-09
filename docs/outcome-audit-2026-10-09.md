# Outcome audit repairs — 2026-10-09

## Baseline and scope

This change addresses the uploaded outcome study and audit of engine commit
`22099ac74bee2ec87fe5400f568b77c9dadccd8f`. The original study attempted
200 games per scenario, seeds 1–200, across all five supported scenarios.
It reported 998 completions, two duplicate-Citadel crashes, 897 rejected
sub-action incidents, 24 winner/margin disagreements, and missing top-level
rankings in every completed game. Those counts overlap other diagnostic
categories and must not be added together as independent defects.

Rules were checked against the repository's `Reference Documents/` only.
Neither those documents nor `rules_consts.py` was modified.

## Confirmed causes and changes

### March Resources and flowchart fallbacks

The turn executor called movement-only `march_group` helpers but never paid
`march_cost`. This affected ordinary human and bot Marches, including expansion
Marches. Resource totals alone and piece-conservation checks could not detect it.

March now selects affordable origins in plan order and pays the canonical
per-origin cost before movement. Multiple groups from one origin and multi-hop
routes pay only once. Devastation, Abatis and owner-scoped Baggage Trains costs
continue through the existing canonical cost function. Event-granted free
Marches and base-game German movement remain free. Unaffordable origins do not
move or flip; Resources cannot go negative from selection. A crossing stop now
terminates a multi-step route in the crossing destination.

Adding the missing fees exposed a second defect: several bot March branches
ignored affordability and consumed a turn on an empty Command. A non-mutating
preflight now uses the same origin-selection logic, leaving both the board and
RNG unchanged. An unavailable March follows the faction's actual IF NONE branch:
Romans Recruit, threatened Gauls/Germans continue to Event/Pass consideration,
other Gallic Marches Raid, and German expansion falls back to Rally. This is not
a blanket conversion of failed actions into Pass. Free-Command planning is
identified separately rather than making normal Marches free at zero Resources.

Arverni threatened March follows §8.7.1's specific sequence: pay March, attempt
Devastate/Entreat before moving, then move; when no SA occurred, consider it after
movement. Human before/during/after selection remains separate and intact.

### Build, Tribe identity, and duplicate Citadels

A Region can contain an allied City backed by a Citadel and a different Tribe
backed by an Ally disc. Build checked the Region's disc count, removed a disc,
and cleared the selected Tribe's allegiance even when that selected Tribe was
the Citadel-backed City. This could remove Aulerci's disc while clearing the
Carnutes City's allegiance. Aggregate per-Region totals still matched, so the
old integrity checks missed the corruption.

`tribe_has_ally_disc` validates the selected Tribe itself. Both Build planning
and execution use it; a rejected Citadel target spends no Resources and changes
no pieces or allegiance. Build also enforces one Ally placement/subdual per
Region, excludes Seize Regions for those actions, and does not place an Ally
at a Dispersed Tribe (§4.2.1).

Arverni-phase Rally checks the same identity when collecting and rechecking
Citadel candidates (A6.2.1). The one-Citadel-per-Region safeguard remains in the
piece layer. Structural validation now additionally requires each Citadel to
have the correct allied City Tribe; matching regional totals are insufficient.
The old Ariovistus/Gallic War seed-43 failure cases have regression coverage.

### Victory totals, winner choice, and result propagation

An allied City's metadata remains allied when its disc is replaced by a
Citadel. Counting every allied record and then adding all Citadels double-counted
those Cities. The engine, bot comparison helpers, and board display now share
a count of actual disc-backed allied records plus Citadels (§1.4.2, §7.2–7.3).

When multiple Non-players exceed their thresholds, the winner is chosen by
margin, with faction precedence used only for an actual tie. A qualifying
Non-player still defeats a human player even with a lower margin (§7.1).
The explicit highest-margin Non-player language is in §8.9 (1-player victory);
the zero-player harness applies that same Non-player ranking rather than
inventing a fixed-precedence winner for its outcome study. The printed section
is not being represented as a separately stated zero-player rule.

`play_card` now propagates the Winter victory result's `rankings` key to its
public `final_ranking` field instead of looking up a nonexistent nested
`final_ranking` key.

### Special Activity selection and timing

- Ambush candidates use the executor's shared Hidden-piece and leader-range
  validation, including Hidden Roman Auxilia and every subsequent Battle.
- Besiege checks the actual selected defender and presence of a Legion; choosing
  Besiege in one Battle does not enable it in an ineligible other Battle.
- Aedui Suborn selection respects Diviciacus/Successor range and the A38
  restriction. Arverni Entreat respects Successor range, one piece per Region,
  and the live Resource budget.
- Arverni Devastate/Entreat and German Intimidate/Settle are reselected at their
  prescribed execution point rather than from a stale pre-Command board.
- Roman Build rederivation carries the accompanying Seize exclusions.
- Belgic Rampage occurs before Battle and leaves the last target piece in a
  Battle Region, as explicitly required by §8.5.1.
- Standalone Enlist selects its free sub-Command after the main Command. Its
  candidates respect leader range, Frost and actual Rally eligibility/capacity.
- German Intimidate selection respects the A22 Roman protection.

These repairs target the reported planning/execution disagreements; they are
not a claim that every possible Event, interaction, or remaining Enlist mechanic
has been independently verified against the published rules.

## Cross-version replay ordering

An independent Python 3.10 run matched all 1,000 Python 3.13 outcome records
apart from two full-state hashes (Ariovistus and Gallic War seed 55). Direct
snapshot comparison isolated both differences to the ordering of
`event_modifiers.card_44a_command_regions`: the same two Regions were stored
as `list(placed_regions)` from a set. Board, Resources and RNG states matched.
The Event now stores `sorted(placed_regions)`; the consumer already treats it
as a set, so this changes no legal choices or gameplay. Two regressions require
the same canonical order regardless of replacement order.

## Diagnostic and runner repairs

The maintained runner is `fs_bot.tools.run_batch`:

```sh
PYTHONHASHSEED=0 python -m fs_bot.tools.run_batch --games 200 --workers 4 --out results
```

Setup, bot initialization, gameplay, post-game audit, diagnostic extraction,
and serialization failures produce records instead of escaping `play_one`.
Worker exceptions also become records. `game_completed` records an engine
completion; `completed` additionally requires successful auditing and no
integrity findings. Failed records are never counted as validated wins, even
when ingesting an older contradictory `completed=true` plus `error` record.

The census preserves error text and every requested raw occurrence, with card,
faction and scenario/seed context. It also reads singular `error` fields that
were previously omitted. Therefore intermediate new-census counts are not
directly comparable to the old instrument. Diagnostic coverage is explicitly
returned cards only; failed cards retain their exception/card context separately.
Metadata includes both the Git revision and a SHA-256 source digest.

## Validation

Full suite: **2,509 passing tests**, including **58 new regression cases**,
verified locally on Python 3.13.5 and independently on GitHub on Python 3.10.22.
The added cases cover cost selection, free movement, multi-group/multi-origin
billing, Baggage Trains, preflight immutability, zero-Resource fallbacks, Build
identity and atomic rejection, Citadel/City invariants, correct scoring, shared
SA legality, both crash reproductions, winner precedence, and injected runner
failures.

The deterministic 1–20 balance baseline was refreshed for the intended rules
changes, not by widening its permitted drift band. Two Interlude smoke fixtures
now use seed 4, which actually reaches the second half after these changes;
their assertions remain intact. A March unit fixture now supplies its required
origin cost, and two victory fixtures no longer expect a City to count twice.

Full all-bot replay: **1,000/1,000 completed**, zero crashes, zero recorded
sub-action/ineffective-action diagnostics, zero structural/conservation flags,
zero missing rankings and zero winner/margin disagreements.

| Scenario | Games | Romans | Arverni | Aedui | Belgae | Germans |
|---|---:|---:|---:|---:|---:|---:|
| Pax Gallica? | 200 | 157 | 14 | 4 | 25 | — |
| Reconquest of Gaul | 200 | 147 | 18 | 8 | 27 | — |
| The Great Revolt | 200 | 51 | 75 | 14 | 60 | — |
| Ariovistus | 200 | 106 | — | 21 | 27 | 46 |
| The Gallic War | 200 | 96 | 32 | 17 | 55 | — |

These are program outcome frequencies for these fixed seeds, not validated
human-game balance estimates or a guarantee of perfect rules fidelity. Changes
to legal costs, scoring, timing and fallbacks intentionally change trajectories.
Ariovistus and Gallic War first halves share paired seeds and are not independent
samples. Mixed-seat random-legal player fuzzing completed 200 games for each of
PYTHONHASHSEED 0 and 7, with zero hard findings and identical batch digest
`dbe7bb91adad5c08`. Each fuzz run also recorded 501 soft partial-action flags;
these are retained, not reclassified as hard failures or erased. Twenty-five
independently replayed study cases matched
winner, length, rankings, diagnostics and final-state hash exactly. CI also
repeats the mixed-seat and cross-hash-seed checks.

A further 100 held-out all-bot games (seeds 201–220 in all five scenarios)
completed without diagnostics, integrity findings, or ranking discrepancies.

After the canonical-order fix, all 1,000 independently generated GitHub records
match the local records exactly apart from wall-clock execution time, including
all final-state hashes. Both environments tested Python source digest
`f6b24aeb024b15b41eff8c181f89ef0b96621fb4737f4d8bd60ab3cbcee79e67`.
GitHub verification run `37997267484` passed the full suite and the complete
study before committing the tested source as
`00c0a0515043f3656a2aa489250f0ecf314e6450`. Runner metadata correctly records
the pre-commit checkout as dirty; the source digest identifies the exact tested
contents independently of that checkout revision.
