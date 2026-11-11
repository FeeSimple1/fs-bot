# Sixth comparison repairs, Batch 2 · 11 November 2026

Batch 2 closes all three automatic Germans Phase findings. Six of the
14 sixth-audit findings are repaired and eight remain open.
[Finding ledger](comparison-audit-round6-2026-11-11.json) ·
[Validation evidence](sixth-comparison-batch2-2026-11-11-evidence.zip)

| Finding | Repaired behavior |
|---|---|
| WS6-01 | Rally places at most one new Ally per Region across all three priority tiers. Suebi comes first, followed by other Tribes in Germania and then elsewhere. The Warband cap uses the actual Allied Tribes after Rally and allows one Warband in un-Devastated Germania even without an Ally. |
| WS6-02 | March forms the groups and records their visibility before any move. The largest groups go first and may enter one adjacent Region. Each origin retains Germanic Control and earlier arrivals stay with the group that brought them. |
| WS6-03 | March ranks destinations by whether the group can gain new Germanic Control. Within either tier, Regions Controlled by human players have priority. The procedure checks live Control after each move and uses the game RNG for ties. |

The March applies one visibility change to each Warband, including those
that stay in place. A Revealed Warband hides. A Scouted Warband loses its
marker and stays Revealed. The regression suite tests both kinds of pieces
and exercises Rally and March together through shaded Germanic Chieftains.
[Rally and March](../../Reference%20Documents/Chapter%206#L19) ·
[One Ally per Region](../../Reference%20Documents/Chapter%203#L212) ·
[Germanic Command rules](../../Reference%20Documents/Chapter%203#L340) ·
[Scouted markers](../../Reference%20Documents/Chapter%204#L83) ·
[Germanic Chieftains](../../Reference%20Documents/Card%20Reference#L163)

## Camulogenus follow-up

In the first audited matrix, Reconquest of Gaul seed 20 reached shaded
Camulogenus on draw 58. The Arverni bot selected a free March from
Atrebates into Britannia and attached Entreat, so the Event was refused.
The bot grant now checks the selected routes after applying the Event
scope. The March and the Event's Warband placement resolve, with Entreat
omitted on the Britannia crossing. A directed land-route control still
executes both the free March and Entreat. The final audit of seed 20
completes in 62 cards with no hard findings.
[Camulogenus](../../Reference%20Documents/Card%20Reference#L716) ·
[Britannia restriction](../../Reference%20Documents/Chapter%204#L38) ·
[Partial execution](../../Reference%20Documents/Chapter%205#L52) ·
[Non-player Event actions](../../Reference%20Documents/Chapter%208#L105)

## Verification

Tests ran on Python 3.12.14 against parent
`1e8cfbd604d19950fdc68664ccc14e87750735ee`. The repaired Python source
SHA-256 is `e2cb669886c9db5e6ef51e807fecd25ae34d491631c89b526a32729c78e6ee24`
across 599 files.

| Check | Result |
|---|---|
| Full suite | 9,931 passed. Of 13 added cases, seven reproduced defects on the parent and six controls passed there. |
| Audited bot games | All 100 legacy and 20 second-edition games completed with full rankings, clean piece and structure checks, and only legal declines. Twelve reached the Interlude. |
| Mixed-player replay | All 20 cases matched across hash seeds 0 and 987. Each run had 562 human turns, 152 Event attempts, 140 executed Events, zero hard findings and one partial plan. |
| Balance | All 100 games stayed within the 15-point band. The largest change in any faction's win rate was 10 percentage points. |

The legacy matrix uses seeds 1–20 and the second-edition matrices use
seeds 41–44 across all five scenarios. The 24 standalone Ariovistus bot
games matched the parent in game length, winner, final board and audit
output.

## Paired outcomes

Twenty legacy games and six second-edition games changed final board.
Eleven legacy games and three second-edition games changed winner. Every
changed-board replay first diverged within Rally or March from the same
board and RNG state. The first difference was formerly Scouted Warbands
staying Revealed in 13 games, a second Ally in one Region prevented in 12,
and March moving only the original group in one. The evidence contains the
original failed Camulogenus audit, the clean final game record and paired
traces for all 26 changed boards.
