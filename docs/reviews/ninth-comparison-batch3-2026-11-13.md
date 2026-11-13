# Ninth comparison repairs, Batch 3 · 13 November 2026

Batch 3 closes UI9-01 and UI9-02. Six of the eight ninth-audit groups
are complete.
[Finding ledger](comparison-audit-round9-2026-11-12.json) ·
[Validation evidence](ninth-comparison-batch3-2026-11-13-evidence.zip)

## Enlist Raid

The terminal and compact Enlist plan use the acting German faction's Raid
limit, the Hidden German Warbands in the Region, and Ariovistus's Enlist
cap. With German-owned shaded Baggage Trains and three Hidden Warbands,
the menu and compact plan let all three take part in the same Raid. The
terminal uses the Raid rules to filter targets and reserves stolen
Resources as choices are made. In the audit position, all three Warbands
reveal and German Resources rise from 10 to 13.
[Baggage Trains](../../Reference%20Documents/Card%20Reference#L75) ·
[Raid](../../Reference%20Documents/Chapter%203#L267) ·
[Ariovistus Enlist](../../Reference%20Documents/Ariovistus/Chapter%20A4#L44)

## Pending Morbihan Battle

The board and change summary use the surviving Arverni Warbands at their
physical origins. The Region table reads pieces and Control from the
same view, and the active-forces line identifies the temporary combined
Battle. After Slingers removes one of the four Warbands, the display
shows two at Pictones and one at Veneti. That loss leaves Veneti tied for
Control. Carnutes shows the two Roman Auxilia and Roman Control while the
Romans choose their casualties there.
[Morbihan](../../Reference%20Documents/Ariovistus/A%20Card%20Reference#L51) ·
[Slingers](../../Reference%20Documents/Card%20Reference#L125) ·
[Control](../../Reference%20Documents/Chapter%201#L192)

The recorded pending IDs, requests, and final game states match the
parent. Saved pending boards from Batch 2 display the corrected position
when opened with this revision.

## Verification

The runs used Python 3.12.14 on the repair to parent
`db2ca384fe794e825f5467f2f0933aedfeb6a242`. The repaired Python source
SHA-256 is `21b1da2b94672957df175909954981a6af82802055d52c072ae9a689fceb4ebf`
across 619 files.

| Check | Result |
|---|---|
| Directed cases | All 11 pass. The parent fails six and passes five controls. |
| Related tests | 408 pass. |
| Full suite | 10,251 pass. |
| Audited bot games | All 120 match Batch 2, with 100 legacy games on seeds 1–20 and 20 second-edition games on seeds 49–52 across all five scenarios. Eleven reach the Interlude. |
| Mixed-player replay | All 35 second-edition cases match Batch 2 and match across hash seeds. The two samples record one and two partial plans respectively, with zero hard findings. |
| Balance | All 100 winners and game lengths match the existing baseline. |

The next batch covers Arverni Devastate forecasts and the Arverni and
Belgic post-Command Special Ability transitions.
