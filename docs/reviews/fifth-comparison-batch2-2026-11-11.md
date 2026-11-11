# Fifth comparison repairs, Batch 2 · 11 November 2026

This batch closes **WS5-01**. If Bibracte or Gergovia lacks its faction's
Ally or Citadel after the force reductions, the Interlude clears that
City's occupant and places the home Ally there. Legions, Warbands, Forts
and other Tribe circles remain subject to their own Interlude instructions.
Gergovia's reinforcement counts the Arverni Warbands that survived the
reductions. [Finding ledger](comparison-audit-round5-2026-11-11.json) ·
[Validation evidence](fifth-comparison-batch2-2026-11-11-evidence.zip)

The Gallic War scenario distinguishes each City from the surrounding
Region in its Adjust Forces steps. Chapter 1 §1.4.2 defines the pieces
that occupy the Tribe circle and City. Shaded Dumnorix and Orgetorix can
place an Arverni Ally or Citadel at Bibracte, so the repair uses the actual
City occupant when it clears that space.
[Gallic War scenario](../../Reference%20Documents/Ariovistus/A%20Scenario%20-%20The%20Gallic%20War#L45) ·
[Chapter 1](../../Reference%20Documents/Chapter%201#L117) ·
[Ariovistus card reference](../../Reference%20Documents/Ariovistus/A%20Card%20Reference)

## Verification

Tests ran on Python 3.12.14 against parent
`5661bf08db76eda71b73102665068d62e23daa83`. The repaired Python source
SHA-256 is `b3ececdaf2aab27ff58b3d908162c916ea6918c6bbe30cdb6b8536ebd1a807a9`
across 593 files.

| Check | Result |
|---|---|
| Full suite | 9,837 tests passed on the parent and 9,845 passed with the repair. |
| Focused checks | 300 passed. Six new cases and two amended tests reproduced the defect on the parent. Two new controls passed on both revisions. |
| Audited bot games | 100 legacy and 20 second-edition games completed with four-faction rankings, clean inventory and structure, and zero nonlegal diagnostics. Ten reached the Interlude. |
| Mixed-player replay | Twenty second-edition cases match across hash seeds 0 and 987. Each run has 776 human turns, zero hard findings, two partial plans and two Interludes. |
| Balance | The existing 100-game check passed. The largest change against its baseline was five percentage points, within the 15-point band. |

The third-Winter regressions restore both vacant and Dispersed Cities and
keep all six Roman Legions on the map when Rome declines the expedition.
Other cases exercise an Arverni Ally and Citadel at Bibracte, a surviving
Colony Ally, and reinforcement with two Scouted Warbands already in the
Arverni Region.

The bot comparison uses legacy seeds 1–20 and second-edition seeds 29–32
in each scenario. All ten paired games that reached the Interlude had
identical entry boards. The nine pairs with different final boards first
diverge during the Bibracte or Gergovia adjustment, with identical RNG state
at that point. Five of those games change winner.
[Parent game records](fifth-comparison-batch1-2026-11-11.md)

| Legacy Gallic War seed | Winner before | Winner after | Example of Forces preserved during the City adjustment |
|---|---|---|---|
| 1 | Romans | Arverni | Caesar, two Legions and five Auxilia near Bibracte |
| 5 | Belgae | Romans | Two Arverni Warbands near Bibracte and ten Germanic Warbands near Gergovia |
| 8 | Aedui | Romans | A Roman Fort and Auxilia near Gergovia |
| 18 | Aedui | Romans | Seven Legions and the Cadurci and Volcae Roman Allies near Gergovia |
| 20 | Romans | Aedui | Eighteen Arverni Warbands near Bibracte |

Four of the fifth audit's eleven findings are closed.
