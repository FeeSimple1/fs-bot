# Sixth comparison repairs, Batch 1 · 11 November 2026

Batch 1 closes three Event findings and leaves 11 of 14 open.
[Finding ledger](comparison-audit-round6-2026-11-11.json) ·
[Validation evidence](sixth-comparison-batch1-2026-11-11-evidence.zip)

| Finding | Repaired behavior |
|---|---|
| BE6-01, Land of Mist and Mystery (57) | Shaded 57 requires a Britannia removal when a target exists and a Gallic Ally placement when possible on the resulting board. Each check runs after its timing window. An incomplete plan rolls back and remains pending in an assistant session. The executor can place zero to four Warbands. The Belgic bot checks for a net Ally gain before choosing the Event. |
| BE6-02, Nasua & Cimberius (A35) and Iccius & Andecomborius (A60) | The A35 shaded plan places one Settlement in a legal Region with space and uses up to eight Available German Warbands. Romans choose the unshaded side with four Auxilia or continue down their flowchart. A60 replaces up to five Roman Allies and Auxilia at Atrebates, with Allies and Hidden Auxilia taking priority. The Event removes selected pieces when the Belgic replacement pool runs short. |
| BE6-03, Flight of Ambiorix (56) | The shaded side uses the same available destinations as execution. A Successor or an Available Leader allows the return. A bot continues down its flowchart when Ambiorix is already on the map. |

Card 57's required stages follow the printed removal and placement clauses
and the partial execution rule in §5.1.3. The directed cases include a
Britannia Ally removal when all Gallic Ally pools are empty and a saved
assistant turn that accepts a corrected plan after reloading.
[Card 57](../../Reference%20Documents/Card%20Reference#L577) ·
[Event rules](../../Reference%20Documents/Chapter%205#L25) ·
[Belgic instructions](../../Reference%20Documents/belgae_bot_event_instructions.txt#L31)

A35 uses the same playable Regions in its planner and executor. German
placements prioritize the Settlement, with seeded ties among equal Regions.
The Roman directive requires four Auxilia and the human choice permits fewer.
A60's bot plans use the named Allied Tribe and the Auxilia's actual visibility.
[Expansion cards](../../Reference%20Documents/Ariovistus/A%20Card%20Reference#L152) ·
[Card A60](../../Reference%20Documents/Ariovistus/A%20Card%20Reference#L272) ·
[Roman instructions](../../Reference%20Documents/Ariovistus/roman_bot_event_instructions_ariovistus.txt#L31) ·
[Non-player Event priorities](../../Reference%20Documents/Chapter%208#L122) ·
[Settlement priority](../../Reference%20Documents/Ariovistus/Chapter%20A8#L26)

The shaded Flight example in §8.1.1 gives the exact decline case. The
regression checks named Ambiorix on the Pax Gallica board and verifies both
legal returns from the same position.
[Card 56](../../Reference%20Documents/Card%20Reference#L567) ·
[Non-player decline example](../../Reference%20Documents/Chapter%208#L43)

## Verification

Tests ran on Python 3.12.14 against parent
`6946a274407b38aebd6f27b8b6d60a1c6dc60b12`. The repaired Python source
SHA-256 is `09142109dba91e116889900e85b10d03e52500840adf8039cd54012094f5f4f5`
across 598 files.

| Check | Result |
|---|---|
| Full suite | 9,918 passed. Fourteen new cases reproduced the defects on the parent and four controls passed on both revisions. |
| Audited bot games | 100 legacy and 20 second-edition games completed with full rankings, clean piece and structure checks, and only legal declines. Twelve reached the Interlude. |
| Mixed-player replay | All 20 second-edition cases matched across hash seeds 0 and 987. Each run had 555 human turns, 156 Event attempts, 142 executed Events, zero hard findings and one partial plan. |
| Balance | A fresh 100-game run matched every winner and game length in the refreshed baseline with the 15-point band. |

The legacy matrix uses seeds 1–20 and the second-edition matrices use seeds
41–44, across all five scenarios. The first full suite found one older 57
fixture that removed a Dispersed marker without naming the required Ally.
That fixture now chooses the Ally and checks that both effects occur. The
final suite and gameplay matrices use the resulting source identity.

## Paired outcomes and balance

Fifteen legacy games and five second-edition games changed winner. Each of
the 20 replays matched its audited outcome and identified the first changed
action from the same board and RNG state. Nine first diverged at the
Britannia Event, five at Flight of Ambiorix, four at A35 and two at A60.

| Reconquest seed | Prior winner | Repaired winner | First changed action |
|---|---|---|---|
| 2 | Aedui | Romans | Arverni decline a Flight return while Ambiorix is already present. |
| 7 | Aedui | Romans | Belgae place their Ally and four Warbands in Britannia. |
| 10 | Aedui | Belgae | Arverni decline the same ineffective Flight return. |
| 20 | Aedui | Romans | Arverni place their Ally and four Warbands in Britannia. |

The four Reconquest changes took Aedui wins from 9 to 5 of 20, crossing
the 15-point band by five points. The reviewed refresh updates 22 of the
100 records, including 15 winners. The same 100 scenario and seed pairs
and 15-point band govern the subsequent passing check. The evidence
includes both baselines, the flagged comparison and the fresh verification.
