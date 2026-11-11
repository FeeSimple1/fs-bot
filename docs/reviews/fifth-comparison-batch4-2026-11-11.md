# Fifth comparison repairs, Batch 4 · 11 November 2026

| Finding | Repaired behavior |
|---|---|
| BM5-01, Stalwart | Both final Legio X adjustments are cancelled in Roman–German Battles while Stalwart is active. This applies to the Attack and Counterattack. Legio X still applies against other Factions when a Roman Leader and Legion participate. |
| BM5-02, Abatis | Defending Abatis joins the current casualty tier as a Fort. The player can choose it or another eligible casualty. A surviving marker can absorb another Loss, and Diviciacus waits until all other eligible casualties are gone. |

[Finding ledger](comparison-audit-round5-2026-11-11.json) ·
[Validation evidence](fifth-comparison-batch4-2026-11-11-evidence.zip)

Stalwart cancels harmful Event effects against Germans. Legio X's Roman
bonus and Roman saving adjustment both harm Germans in that matchup.
One shared adjustment applies after rounding in the Attack and Counterattack.
Abatis uses the existing Fort roll and sits with static casualties. The default
uses Abatis first in that tier, except when standing Germans already defaulted
to a Settlement. A player can choose either target when both are eligible.
[German Phalanx](../../Reference%20Documents/Ariovistus/A%20Card%20Reference#L126) ·
[Legio X](../../Reference%20Documents/Card%20Reference#L147) ·
[Abatis](../../Reference%20Documents/Ariovistus/A%20Card%20Reference#L288) ·
[Battle Losses](../../Reference%20Documents/Chapter%203#L159) ·
[Ariovistus Battle Losses](../../Reference%20Documents/Ariovistus/Chapter%20A3#L49)

The terminal menu shows Abatis and the named Ally. An assistant session
can save and reload the choice, reject an ineligible response under the same
decision ID, and resume with the selected Ally. A pre-repair transcript using
the default Abatis casualty and a new transcript choosing the Ally both replay
to their recorded board, RNG and decision log.

## Verification

Tests ran on Python 3.12.14 against parent
`e3786c46fe451ac1ea66115cc862eca43f52d900`. The repaired Python source
SHA-256 is `4670feb0915211adda720adbf31bcef3dede23830f5f7c1e9e177e653daef96a`
across 595 files.

| Check | Result |
|---|---|
| Full suite | 9,879 tests passed. |
| Focused checks | 522 passed. Eleven new cases reproduced the defects on the parent, and five new controls passed on both revisions. |
| Audited bot games | 100 legacy and 20 second-edition games passed with complete rankings, clean integrity checks and zero nonlegal diagnostics. All recorded game results matched the parent. |
| Mixed-player replay | Twenty second-edition cases matched across hash seeds 0 and 987 with zero hard findings and two partial plans. |
| Balance | The 100-game check passed within the existing 15-point band. The largest shift from the reviewed baseline was five percentage points. |

The legacy matrix uses seeds 1–20. The second-edition matrices use seeds
29–32. Each matrix covers all five scenarios. The directed Battles separately
verify the changed rules and human choices.

Eight of the fifth audit's eleven findings are closed. The three open
findings concern bot Battle target and survival forecasts.
