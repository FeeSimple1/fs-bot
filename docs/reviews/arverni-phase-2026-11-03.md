# Ordinary Arverni Phase repairs — 3 November 2026

Date convention: America/Chicago. This batch repairs the five ordinary A6.2
defects identified during the [Gallic Event work](gallic-event-grants-2026-11-02.md),
plus two related errors in the same phase. It uses the supplied rules; no new
provisional ruling is introduced. PR-01 through PR-11 retain their existing
status, subject to later authoritative correction.

## Corrected behavior

| Defect | Correct behavior and source |
|---|---|
| Rally could add Warbands after placing an Ally or Citadel in that Region | A6.2.1 permits Warband placement only in remaining Regions where neither was placed. Each Region uses one placement category. |
| Rally could place an Ally without Arverni Control | A6.2.1 invokes ordinary 3.3.1. Ally placement requires Control; the expansion's automatic Arverni have no Vercingetorix exception. A Home Region may still allow a Warband. |
| A secondary March could leave enemy Control intact | A6.2.2 requires the combined remaining adjacent groups to remove Aedui or Roman Control. A tie suffices; the Arverni need not gain Control. The selected Target Region remains the first destination and origins retain Arverni Control. |
| Raid could use more than two Warbands in one Region | A6.2.3 invokes 3.3.3's maximum of two Hidden Warbands per Region, including when stealing from several factions. |
| Raid held Warbands back for an impossible Ambush | A6.2.3 reserves enough Hidden Warbands for an actually possible Ambush that causes a Loss against an enemy. It checks Hidden superiority and eligible Diviciacus cooperation, and does not reserve against an impossible attack. |
| Rally could place an Arverni Ally at a protected Tribe | 3.3.1 and 1.4.2 restrict the named home Tribes and Suebi. Being Subdued does not waive those restrictions. |
| Raid credited Arverni Resources | A1.5.2 prohibits Arverni receiving Resources and A1.8 removes their Resource track. Raided Resources leave the victim without being credited to Arverni. |

The first five are the preceding report's follow-up inventory. The last two
were confirmed during this repair. None is an additional closure from the
original 50-item human-choice audit: **19/50 closed (38%), 31 open**.
The 34 unverified inventory rows remain separate. Two source questions still
lack adopted policies; the eleven adopted project rulings are provisional.

## Scope and compatibility

The ordinary phase still performs Rally, March, Raid and Battle in sequence
when triggered, with its existing Target selection, At Peace and Frost
conditions. It remains distinct from PR-10's single Event-granted Command.
The same corrected Rally helper also serves the expansion's Seize-triggered
Arverni Rally under A3.2.3; that caller receives the legality fixes as well.
The base game's seated Arverni bot and Germans Phase retain their separate
rules. The Gallic War changes rules at its Interlude as before.

No save schema or decision contract is intentionally changed. Continuing an
older save uses the corrected mechanics, so future outcomes may differ.
Historical traces and result counts continue to describe their original
engine revision; replay comparisons require the same engine source.

The supplied Reference Documents and canonical constants are unchanged.
This repair is not an exhaustive audit of every phase interaction or proof
of human-game balance.

## Validation

The parent is `474a5929dfd54c06ecb3731c558493013c04c3de`. The final prepared
source contains 444 Python files, SHA-256
`e42af737c5a40fa54c8e45abb4c1e70290f28bae1c748dd3572a9f7dad2c7e54`.
The final full-suite result is recorded in the accompanying
[results JSON](arverni-phase-2026-11-03-results.json).

| Check | Coverage and result |
|---|---|
| Parent suite | 7,149 passed on Python 3.10.22 |
| Final full suite | 7,205 passed, zero failures or skips, on Python 3.10.22 |
| New source regressions | 56 cases across both expansion scenarios; independent reviewer supplied 24 |
| Python 3.12.14 focused check | 114 passed, including the corrected Seize test and existing Event adapter |
| Bot games | 150/150 completed and audited: legacy seeds 1–20, original and second-edition seeds 201–205, all five scenarios |
| Bot determinism | 25 additional hash-seed-7 repetitions of legacy seeds 1–5 match their hash-seed-0 records |
| Mixed-player games | 220 distinct cases, each replayed at hash seeds 0 and 7: 880 executions, exact cross-hash JSON/stdout agreement, zero hard findings and zero partial plans |
| Strict census | Seeds 201–202 across all scenarios at both hash seeds: 20 executions, no nonlegal severity; 97 legal declines in each hash run |
| Scenario isolation | All 60 base-game legacy records match the parent in every gameplay result field, including final state |
| Outcome review | 29 changed winner/card-count pairs reproduced in 58 independent full-game traces; no unexplained first divergence |
| Protected inputs | All 47 supplied reference files, canonical constants and balance baseline unchanged |

The mixed-player sample uses legacy seeds 1–40 and each explicit edition's
seeds 201–202 across all five scenarios, with reactions and Event decisions
enabled. These executions are separate from bot-only outcomes and from the
diagnostic traces. The existing 100-game balance comparison passes its
unchanged 15-percentage-point band; no baseline refresh or bot tuning was used.

Every changed winner/card-count pair first diverges at a corrected Rally
with identical incoming board and RNG state. Twenty-seven involve the old
extra Warbands after a City upgrade; four involve an Ally without Control
(two overlap). Eight also change RNG position because the forbidden
post-upgrade Regions no longer enter the Warband candidate shuffle. These
first-divergence checks explain why trajectories separate, not every later
decision. Four separate Seize Rally witnesses confirm the shared caller's
correction in both expansion scenarios.

### Preserved attempts and source equivalence

The gameplay matrix and causal traces ran on the fully frozen first source,
`f4fc78f95288b39beac4e8221f3197a2bcf2807614c7ee422d19e35bec52d910`.
Its full suite had 7,204 passes and one stale Seize test failure: that test
expected an Ally without Control. The fixture legally upgrades Bituriges'
existing Ally to a Citadel and places one Warband each in Pictones and Veneti.
The corrected assertion also prohibits Warbands accompanying the Citadel.

Only `test_seize_rally_actions.py` changed between that source and the final
full-suite snapshot. All 187 production Python files are byte-identical,
with production digest
`75c1f659b412ee2afceef28f6e0dedb48d100b8ed27efee775335dfd27ac1ee3`.
The evidence preserves both manifests and the file-by-file equivalence check.
Game records retain their actual first-source labels; they are not silently
relabeled as runs of the final test snapshot. The final full suite was rerun.

The [evidence archive](arverni-phase-2026-11-03-evidence.zip) retains the
initial failing suite, expected parent regression failures, two corrected
test-fixture mistakes and a disqualified parent-import attempt. The latter
accidentally imported candidate code; replacement parent runs verify the
module path. Neither those setup mistakes nor expected old-engine failures
are reported as successful repair validation.

The archive contains 313 indexed evidence files plus its manifest, with
per-file hash and ZIP integrity checks. Archive SHA-256:
`bd59ee093ef01a98357977bc916c30659168f4c70b5daa61ab460872ad6fdf6d`
(2,842,954 bytes).

The parent game comparison reuses the preceding accepted matrix only after
verifying every parent Python file against the bytes committed as `474a592`.
Its original metadata and provenance remain intact. Local acceptance
precedes publication; remote CI belongs to the subsequently published commit.

### Legacy outcome sample

These are 20 audited bot games per scenario, seeds 1–20. Counts identify the
winning faction at game end, not the original player seat. They are a small
regression sample, not an estimate of human-game balance.

| Scenario | Romans | Arverni | Aedui | Belgae | Germans | Ended on final Winter |
|---|---:|---:|---:|---:|---:|---:|
| Pax Gallica? | 13 | 2 | 3 | 2 | — | 2/20 |
| Reconquest of Gaul | 10 | 0 | 6 | 4 | — | 5/20 |
| The Great Revolt | 5 | 8 | 3 | 4 | — | 17/20 |
| Ariovistus | 12 | — | 2 | 2 | 4 | 12/20 |
| The Gallic War | 11 | 1 | 3 | 5 | 0 | 4/20 |

Ten of the 20 Gallic War games completed the Interlude. A game ending on
final Winter can still end by a victory threshold on that card. The two
other card editions use separate held-out seed samples and are not pooled
into this table.
