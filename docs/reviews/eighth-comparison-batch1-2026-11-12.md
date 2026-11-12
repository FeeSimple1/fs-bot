# Eighth comparison repairs, Batch 1 · 12 November 2026

Batch 1 closes LC8-01 and LC8-02. Nine of the eleven audit groups remain open.
[Finding ledger](comparison-audit-round8-2026-11-12.json) ·
[Validation evidence](eighth-comparison-batch1-2026-11-12-evidence.zip)

Once a Winter card is drawn, the engine checks for any remaining Winters in
the draw deck. After the Gallic War Interlude, the fifth Winter in the rebuilt
deck triggers final scoring if play reaches it. The cumulative count still
tracks the entire game. The third first-half Winter can lead into Interlude,
and the fifth second-half Winter ends play even with a postponed Event in
the deck under Sudden Frost. Bot decisions about the upcoming final Winter
use the same draw deck before the draw.
[Winter and Sudden Frost](../../Reference%20Documents/Chapter%202#L88) ·
[Gallic War deck](../../Reference%20Documents/Ariovistus/A%20Scenario%20-%20The%20Gallic%20War#L114)

With one human Faction and three Non-players, a human threshold crossing
before the final Winter lets the Victory Phase continue. A qualifying
Non-player can win immediately. Frost checks continue to read threshold
status, and Optimates can trigger final scoring. The same solo timing
applies when loading an unresolved Winter from a legacy save with bot seats.
The printed solo setup is used for the check, and Spare Factions keeps its
own victory rules.
[Victory Phase](../../Reference%20Documents/Chapter%206#L7) ·
[Solitaire](../../Reference%20Documents/Chapter%208#L992) ·
[Ariovistus solitaire](../../Reference%20Documents/Ariovistus/Chapter%20A8#L1) ·
[Optimates](../../Reference%20Documents/Card%20Reference#L193)

## Verification

The tests ran with Python 3.12.14 against parent
`33c722e941292f8cb0a66e3cedc0d5efa995b0e2`. The repaired Python source digest is
`a9af09027132d567150a5d6c7d8a32abbfbfc5e73e0b14d3a77700d00cb034c2` across 612 files.

| Check | Result |
|---|---|
| Full suite | 10,126 passed. |
| Directed cases | All ten passed after the repair. Five fail on the parent and five controls pass. The wider group of 103 Winter, final-year, paired-player and victory tests also passes. |
| Audited bot games | All 100 legacy and 20 second-edition games completed. Each has clean integrity checks, a valid four-faction ranking and only legal-decline diagnostics. Twelve complete the Interlude. |
| Mixed-player replay | Twenty second-edition cases match byte-for-byte at hash seeds 0 and 987. Each sample records 623 human turns, 152 Event attempts and 138 executed Events, with zero hard findings or partial plans. The case records also match the audit sample. |
| Balance | The 100 legacy games pass the existing 15-point band. The largest change is 10 points in The Gallic War. |

The directed cases use controlled boards with the production deck, Interlude,
Winter resolution and saved-game loader. They cover standard solo play in
Reconquest and Ariovistus, both seat formats, bot and multiplayer victories,
solo final scoring at a margin of zero, and an Optimates ending. The fifth
Winter case uses Sudden Frost. The fourth Winter case verifies that play
continues through Spring and that the saved position produces the same result.

## Paired outcomes

The legacy comparison uses seeds 1–20 in all five scenarios. The second-edition
bot and mixed-player comparisons use seeds 45–48 in all five scenarios. The
parent game records come from the seventh Batch 5 and eighth audit archives.
Both record the same Python source digest as the parent of this repair.

Six legacy Gallic War cases first differ on the fourth Winter after Interlude.
Every pair has identical board and RNG fingerprints entering that Winter and
one Winter remaining in the deck. In seeds 3, 6, 12 and 20, a qualifying
Faction still wins that Winter. Only the result's final-Winter flag changes.
The second-edition bot cases have matching final states.

Seeds 1 and 7 reach that Winter with no threshold winner. The old engine
awarded Aedui victory by margins. The repaired games complete the remaining
Winter phases and play the next year. Belgae cross their threshold on the
fifth Winter after Interlude.

| Legacy Gallic War seed | Parent result | Repaired result |
|---|---|---|
| 1 | Aedui, 103 cards, 7 Winters | Belgae, 120 cards, 8 Winters |
| 7 | Aedui, 101 cards, 7 Winters | Belgae, 118 cards, 8 Winters |

Aedui move from 25% to 15% of the 20 legacy Gallic War wins. Belgae move
from 30% to 40%. The balance check uses the reviewed baseline for those seeds.
