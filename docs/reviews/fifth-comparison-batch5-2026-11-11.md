# Fifth comparison repairs, Batch 5 · 11 November 2026

| Finding | Repaired behavior |
|---|---|
| NP5-01, Diviciacus | Both Aedui Battle priorities check the selected defender. The forecast applies Attack casualties, considers successful defender rolls, and checks whether the remaining Counterattack can reach Diviciacus after the other Aedui pieces absorb Losses. Only the Region assigned Ambush gets its protection. |
| NP5-02, Aedui target | The opening Battle requires an actual enemy Leader, Ally, Citadel, Legion, or Ariovistus Settlement that would take a Loss. The initial check and the Battle plan share the Resource budget and target selection. If none qualifies, the bot continues down its flowchart. |
| NP5-03, German forecast | The German bot applies the Attack formula, including named Ariovistus and the ordinary Successor contribution. It assumes defender Loss rolls remove pieces and forecasts Counterattack from the survivors. |

[Finding ledger](comparison-audit-round5-2026-11-11.json) ·
[Validation evidence](fifth-comparison-batch5-2026-11-11-evidence.zip)

Ariovistus's doubled Counterattack can reach Diviciacus and his lone
escort. A Successor inflicts one Loss in the same position, which the
escort can absorb. An uninvolved German force has no bearing on a Battle
against a Belgic Ally. The regression cases also cover a player defender's
option to assign Losses to a hard piece and the single Aedui Ambush.
[Aedui Battle](../../Reference%20Documents/Chapter%208#L448) ·
[Diviciacus and German Battle selection](../../Reference%20Documents/Ariovistus/Chapter%20A8#L53) ·
[Battle procedure](../../Reference%20Documents/Chapter%203#L132) ·
[Ariovistus Battle Losses](../../Reference%20Documents/Ariovistus/Chapter%20A3#L49)

Six German Warbands forecast three Attack Losses against six Roman
Auxilia. Three survive and inflict one Counterattack Loss. Ariovistus
with four Warbands instead inflicts six Losses and leaves zero to
Counterattack. A larger Roman force still makes the Germans March when
their projected losses are greater. Forecasts use detached boards and
leave the live random state and reaction requests alone.

The directed German cases isolate the ordinary Attack and Counterattack
with Special Abilities unavailable.

## Verification

Tests ran on Python 3.12.14 against parent
`61c7587caa586bc430723f0b5fde5b5f80a5ef2f`. The repaired Python source
SHA-256 is `2423cb1f410650da300914e6569c1637675894cc43a9bd8284dfd92bd3b3ecb7`
across 596 files.

| Check | Result |
|---|---|
| Full suite | 9,900 tests passed. |
| Focused checks | 517 passed. Fourteen new cases reproduced the defects on the parent, and seven new controls passed on both revisions. |
| Audited bot games | 100 legacy and 20 second-edition games passed with complete rankings, clean integrity checks and zero nonlegal diagnostics. |
| Mixed-player replay | Twenty second-edition cases matched across hash seeds 0 and 987 with zero hard findings and two partial plans. |
| Balance | All 100 winners and game lengths match the refreshed baseline. |

The legacy matrix uses seeds 1–20. The second-edition matrices use seeds
29–32. Each matrix covers all five scenarios. An existing Diviciacus loan
test now uses a legal Command-only setup that can force the Ally Loss with
agreed Auxilia even when the defender Retreats.

## Paired outcomes and balance

Thirty legacy games and two second-edition games changed winner from
Batch 4. All 32 replays agree on the board and random state before the
first differing decision. In each case the old Aedui Battle targeted no
high-value piece. The repaired bot instead Rallies in 31 games and Marches
in Great Revolt seed 14.

| Ariovistus, legacy seeds 1–20 | Prior wins | Repaired wins | Change |
|---|---:|---:|---:|
| Romans | 9 | 14 | +25 percentage points |
| Aedui | 2 | 1 | −5 percentage points |
| Belgae | 5 | 0 | −25 percentage points |
| Germans | 4 | 5 | +5 percentage points |

The old guardrail flagged the Roman and Belgic shifts. The first-divergence
traces identify the corrected Aedui trigger in those games. The reviewed
refresh uses the same 100 games and the 15-point band. The evidence includes
both baselines, the failed comparison and the passing run.

All eleven findings from the fifth comparison are closed.
