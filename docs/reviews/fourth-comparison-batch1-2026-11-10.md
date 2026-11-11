# Fourth comparison repairs, Batch 1 · 10 November 2026

This batch closes six of the fourth audit's sixteen findings.
[Finding ledger](comparison-audit-round4-2026-11-10.json) ·
[Validation evidence](fourth-comparison-batch1-2026-11-10-evidence.zip)

| Finding | Repaired behavior |
|---|---|
| BE4-01, Hostages | Shaded Hostages places a Gallic Ally and a separately chosen Warband at each of one or two distinct Subdued Tribes with Roman pieces. The live Tribe determines both placements' Region. The plan rejects an inconsistent Region, illegal piece owner, or repeated Tribe. Available pieces still place when the other pool runs short. The terminal offers the live Tribe and owner choices. |
| BE4-02, Celtic Rites | Unshaded play requires a nonempty Gallic selection. Repeated entries represent one selected faction. Each loses up to three Resources and becomes Ineligible through the next card. The Roman bot targets Arverni then Belgae in the original scenarios and Belgae in Ariovistus, as instructed. Automatic Arverni in Ariovistus track neither effect. |
| BE4-04, Germanic Horse | Shaded play activates the Capability for the Gallic executor. Existing plans that name the executor still work. A non-Gallic executor can play the shaded text with no effect. Unshaded activation clears the former shaded ownership record. |
| EX4-01, Abatis | A64 requires a playable Region with an executor-owned Warband if one exists. Hidden, Revealed and Scouted Warbands qualify. An invalid selection returns a saved human turn to its existing decision ID. A corrected response resumes that turn. |
| EX4-02, Bellovaci | The unshaded Ally and troop owners remain independent choices. A troop choice must resolve to Roman Auxilia or Aedui Warbands before any victim is removed. Legacy plans using only the owner or only the type still work. |
| WS4-01, Harvest | The resulting Resource total stays on the 0–45 track. The Ariovistus Roman earnings calculation continues to use the printed victory score, including a negative score. |

Rules used are Card Reference 22, 46 and 59, A Card Reference A64 and A69,
§§1.4.2, 1.8 and 5.1–5.3, A1.8, A5.1.1, A5.1.4, A6.4.1 and A7.2, and
the original and expansion Roman non-player instructions for Celtic Rites.
The existing arithmetic for an already positive Roman balance is preserved.

## Verification

The parent is `ee05f5f33754aa0362632a965a2249cf00ecc381`. The accepted
Python-source SHA-256 is
`bc5631828c67b6b02de07e5c3065d3defd3e4714bd08a367aa6fb1037e755eb9`
across 586 files.

| Check | Result |
|---|---|
| Full suite | 9,722 passed |
| New regression cases | 36 passed on the repair. The same cases produce 34 failures and two positive controls on the parent. |
| Audited second-edition bot games | 20 completed with zero audit failures. Every winner matches the parent. |
| Second-edition mixed-player games | 20 cases match across hash seeds 0 and 987, with replay, zero hard findings and one soft partial plan. |
| Legacy balance matrix | All 100 games completed within the existing 15-point band. Two winners differ from the parent. |

The second-edition matrices use seeds 25–28 across all five scenarios.
Each mixed-player run records 629 human turns, 144 Event attempts and
132 executed Events. Two hash runs with replay account for 80 game
executions. The full suite includes an Abatis saved turn that rejects an
empty Region choice, retains the original pending ID and board, and then
accepts the corrected Region after reload.

The paired traces start from identical boards at each first differing card.

| Scenario and seed | First difference | Outcome |
|---|---|---|
| Reconquest of Gaul, 1, legacy | On the 31st draw, Hostages places at Helvetii and Ubii. The Arverni Home Tribe is reserved for Arverni. The parent had placed a Belgic Ally there. | Arverni wins in 46 cards. The parent had a Roman win in 46 cards. |
| Ariovistus, 17, legacy | On the 38th draw, Rome's unshaded Celtic Rites reduces Belgae from four Resources to one and makes them Ineligible. The parent had omitted the target and effect. | Aedui wins in 47 cards. The parent had a German win in 47 cards. |
| The Gallic War, 25, second edition | On the 58th draw, Arverni declines shaded Hostages. The parent had placed Allies at the obsolete Nori circle and German-only Suebi. Arverni and Aedui Rally. | Aedui wins in 72 cards. The parent also had an Aedui win in 106 cards. |

The balance matrix uses seeds 1–20 across all five scenarios. Its largest
win-rate shift against the reviewed baseline is ten percentage points.
The baseline has five winner differences, including three already present
on the parent. The validation archive records exact outcomes and rerun
commands.
