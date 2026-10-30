# First small audit repairs — 29 October 2026

This batch closes **five of the audit's 50 grouped findings**. **45 remain
open**, tracked in [the progress register](../human-choice-progress.json).
It implements the audit's first repair batch with small shared rule checks,
plus propagation of the same mandatory setup rule to validation callers.

[Results JSON](cheap-fixes-2026-10-29-results.json) · [Evidence archive](cheap-fixes-2026-10-29-evidence.zip) ·
[Original audit](human-choice-audit-2026-10-29.md)

## Corrected behavior

| Finding | Correction and source |
|---|---|
| BATTLE-LOSS-TIERS | Battle prompts and explicit priorities enforce the current legal casualty tier: static pieces first when retreating, otherwise after other pieces; Diviciacus last. §§3.2.4/3.3.4 and A3.2.4. |
| CMD-REPEATED-REGION | Seize cannot repeat a Region within or across Command portions; Entreat cannot repeat a Region. Guards apply to ordinary plans and applicable free grants. §§3.1/4.1/4.3.1. |
| FE-02 | Malformed replacement `details` are rejected before nested access; the Supply decision remains pending with the same request, ID, queue and board/RNG. §8.6.6, PR-07 and the durable input contract. |
| WS-F07 | Game-run Arverni cannot give/receive Resources in Ariovistus. Menus and durable turn validation use shared participant restrictions; original-scenario Germans remain barred and post-Interlude Arverni are permitted. A1.5.2/A1.8 and Interlude Edge Track. |
| WS-F04 | New Great Revolt games with Belgae as the sole human faction start with Ambiorix. CLI/durable initialization and human-policy validation callers supply setup seats; new replay metadata/origins preserve them. Scenario “Players and Victory.” |

The Region guard distinguishes selections from operations. Two Raid flips,
Vercingetorix's two Rally options, March groups, and Build operations within
one legal selected Region remain supported. Human casualty requests use the
current tier; bot forecasts retain the full ordered list of potential later
losses. A legal explicit casualty preference preserves prior RNG sequencing,
including borrowed A28 pieces and required hard-piece dice.

## Validation

Every code commit below passed the full suite in an isolated checkout before
commit. Tests cover rules, real menus, invalid input, transaction rollback,
save/resume and deterministic replay where applicable. The final suite passes
**6,260 tests** after adding
**151 cases** to the audited 6,109-test baseline.
Focused reviewer counts overlap these totals and are not added to them.

| Change | Commit | Full-suite passes |
|---|---|---:|
| supply | `3a17d336cd861b6b1a0baebc2b6e4244ce9c1f6b` | 6,128 |
| transfers | `4e0126e77e1090cfc568b514cb584a44cbee2554` | 6,161 |
| regions | `82e65efd3afdebb501884daf11fa189448c042c5` | 6,177 |
| losses | `91b957ce02d93da5e2cc80fa25f966a0ca77c248` | 6,235 |
| setup | `380c14ff887f76c2712305df2d3b2073dd61be49` | 6,254 |
| policy-setup | `fa0ca1682ba055f3375ee09448f4cb419fb38770` | 6,260 |

Integrated checks on the final code revision:

- **110 audited bot games**, all completed without errors, integrity findings,
  nonlegal diagnostics, ranking discrepancies or missing final hashes:
  legacy seeds 1–20 in all five scenarios (100 games), plus seed 201 in all
  five scenarios for each other card profile (10 games).
- All **100 baseline winners and card counts match exactly**. The baseline
  file and 15-point guardrail remain unchanged; no outcome refresh was needed.
- **15 distinct mixed-seat cases**, seed 201 across five scenarios and three
  profiles, each replayed and repeated under hash seeds 0 and 7: **60 executions**.
  Zero hard findings; corresponding batch digests match across hash seeds.
  These are randomized policy/transport checks, not 60 independent human games.

| Mixed profile | Human turns per hash run | Event turns | Successful Events | Matching soft partial results |
|---|---:|---:|---:|---:|
| legacy | 149 | 34 | 32 | 0 |
| original | 149 | 34 | 32 | 0 |
| second-edition | 149 | 34 | 32 | 0 |

Soft partial results are matching preview/live outcomes from deliberately
imperfect random plans; they are not counted as complete successful human
actions. These bounded checks do not establish complete rules compliance.

The first casualty integration run found one correct Divination regression
test failing because a shared projection helper had been narrowed. The helper's
full-list contract was restored and 14 projection cases added. A later run
found an existing Interlude checkpoint test double lacked the new setup argument;
its signature and assertion were updated. Both failed attempts are preserved;
neither was committed. A separate review caught and corrected the explicit
casualty-priority RNG issue before the accepted loss commit.

## Compatibility and remaining limits

Existing saves are not retroactively given Ambiorix. New setup information is
preserved in CLI metadata and durable origins, including cross-frontend replay.
Multiple human faction switches do not identify shared players; the paired
Romans/Aedui trigger and shared victory rules remain under WS-F09. BOTS setup
is unchanged. Validation callers now apply the sole-human-Belgae rule too;
older experimental policy outcomes retain their historical source identity.

Historical casualty transcripts whose requests offered both tiers may stop
at strict replay verification and need a new decision. There is no signature
bypass that replays an illegal historical choice. Newly recorded pending
decisions, save/resume and replay pass the added tests.

The raw executor still reports a refused Resource gift and continues its
accompanying Command, as previously documented; the gift itself cannot execute.
Durable turn input rejects forbidden parties before acceptance. Transfer timing,
incoming/Winter windows, the CLI amount cap and shared-player ownership remain
separate findings. No Event grant routing, general during-Command interruption,
Interlude choice system or physical casualty-identity redesign was attempted.
The two existing non-player source questions and 34 unverified inventory rows
remain separate from the 45 open grouped findings.

## Evidence and source identity

The archive contains per-commit JUnit/full-suite logs, both rejected attempts,
raw bot records, mixed-seat outputs, command manifests and verification scripts.
The six new regression files and the updated checkpoint test are in the code
commits. `integration_checks.py` reruns the bounded matrix and verifies exact
coverage, diagnostics, baseline records and replay hashes; its sibling checkout
path is named `fs-cheap-validation` and output paths must be unused.

- Tested code commit: `fa0ca1682ba055f3375ee09448f4cb419fb38770`.
- Python source: 385 files; SHA-256 `f386da33458625e15a918eaaefedb96b2bcf1464c879b60d9b6fa8b180f4ebd0` (sorted relative path, NUL, raw bytes).
- All 47 supplied reference files and canonical constants unchanged.
- Balance baseline SHA-256: `207a129589d2bb17bec17319e70de7c8cf44d1572dc6aaca73cd0b39a9b5b8d3`.
- Archive SHA-256: `8c8f2fb81f6ec6a1e9bd441f9c279dabf7d39b0893144528d1c6697916bcb155` (952,778 bytes).

The documentation commit also passed all 6,260 tests before commit. It adds
this report and living status updates without
changing the tested Python bytes. GitHub checks are separate from the local
evidence above; no configured workflow is represented as a completed run.
