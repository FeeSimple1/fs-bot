# Tenth comparison repairs, Batch 1 · 13 November 2026

Batch 1 closes EV10-01 and EV10-02. Seven of the nine audit groups remain
open. [Finding ledger](comparison-audit-round10-2026-11-13.json) ·
[Validation evidence](tenth-comparison-batch1-2026-11-13-evidence.zip)

The Belgae bot plays shaded Bellovaci only while Bellovaci is a Belgic Ally
and it has Warbands available to place. The placed Warbands can Ambush.
Roman and Aedui bots check that Remi is Roman Allied, Aedui Allied, or Subdued
before playing unshaded Siege of Bibrax. When the printed condition fails,
the bot continues through its normal Command flowchart. The Event handlers
and the effectiveness checks use the same Tribe conditions.
[Bellovaci](../../Reference%20Documents/Ariovistus/A%20Card%20Reference#L316) ·
[Siege of Bibrax](../../Reference%20Documents/Ariovistus/A%20Card%20Reference#L231) ·
[Ineffective Events](../../Reference%20Documents/Chapter%208#L30)

For unshaded Siege of Bibrax, the Aedui bot places Aedui Warbands and the
Roman bot places Auxilia. Each places up to four of its own available troops
and declines the Event when its troop pool is empty. The printed Roman Fort
and Belgic Warband removals resolve under the card's ordinary rules. A human
player can choose either troop recipient and specify any legal quantity of
Belgic Warband removals, including zero.
[Partial execution](../../Reference%20Documents/Chapter%205#L52) ·
[Non-player Event benefits](../../Reference%20Documents/Chapter%208#L120)

## Verification

Python 3.12.14 ran the tests on the repair to parent
`62cb21484da257600c6ebddc04d2e531d545965e`. The repaired Python source
SHA-256 is `d0d118327578839fecd34ec27849f7226f022ce020df135332004843bf4db8e7`
across 621 files. All 47 supplied reference documents and the canonical
constants match their audit hashes.

| Check | Result |
|---|---|
| Directed regressions | All 23 pass. The parent fails 18 and passes five controls. Both expansion scenarios, alternate Remi allegiances, Dispersed and Dispersed-Gathering markers, troop shortages and explicit human choices are covered. |
| Related Event tests | 366 pass, including the directed cases. |
| Full suite | 10,302 pass, including the balance canary. |
| Audited bot games | 100 legacy games on seeds 1–20 and 20 second-edition games on seeds 53–56 across all five scenarios. All complete with clean integrity checks and valid rankings. Thirteen reach the Interlude. |
| Mixed-seat replay | Twenty second-edition cases on seeds 53–56 match at hash seeds 0 and 987 and match their audit trajectories. The cases record 560 human turns, 130 Event turns, 118 executed Events, one partial plan and zero hard findings. |
| Balance | The 100-game check passes against the reviewed baseline. Its winners and game lengths agree with the audited runner on every seed. |

## Paired outcomes

| Edition | Games | Changed final states | Changed winners | Changed card counts |
|---|---|---|---|---|
| Legacy | 100 | 15 | 6 | 5 |
| Second edition | 20 | 0 | 0 | 0 |

Every changed game starts its first differing card with identical board and
RNG fingerprints. Eight first differ when the Aedui receive Warbands from
Siege of Bibrax. Four first differ when the Aedui skip Siege of Bibrax with
Belgic Remi. Three first differ when the Belgae skip shaded Bellovaci with
no Belgic Ally there. The traces record the pieces immediately before and
after each Event.

On Ariovistus seed 12, the first change comes on card 16. The Aedui place
four Warbands at Atrebates. Both runs also place the Fort and remove the
Belgic Warband. On Ariovistus seed 6, the Aedui choose Rally after declining
Siege of Bibrax on card 28.
The Belgae's Gallic War wins move from 4/20 to 6/20, the largest shift at 10
percentage points against the 15-point band.
