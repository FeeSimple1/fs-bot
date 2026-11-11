# Sixth comparison repairs, Batch 3 · 11 November 2026

Batch 3 closes the three Battle findings. Nine of the 14 sixth-audit findings
are repaired and five remain open.
[Finding ledger](comparison-audit-round6-2026-11-11.json) ·
[Validation evidence](sixth-comparison-batch3-2026-11-11-evidence.zip)

| Finding | Repaired behavior |
|---|---|
| BM6-01 | Inflexible German Phalanx cancels the shaded Legio X restriction against German defenders. Both the forecast and actual Attack give each of Caesar's Legions its normal rate. Stalwart cancels Slingers initial fire against German attackers, including the increased rate from unshaded Germanic Horse. |
| BM6-02 | Roman Slingers can fire before a German Ambush in the Germans Phase, Germanic Chieftains, German Allegiances, Aduatuca, Aduatuci and the free German Limited Battle used by Enlist. The initial fire can come from Roman Auxilia when another Faction is defending. |
| BM6-03 | Consuetudine can Ambush despite the defender's Hidden pieces and chooses one defender per Region. The Germans Phase gives human defenders priority and uses the game RNG among equal candidates. |

Slingers applies once to the whole Battle Command. A fixed Battle offers
the Roman Region choice. The Germans Phase and German Allegiances use the
existing provisional PR-13 window, so Romans can use it at a live Battle
or reserve it while candidates remain. The directed cases exercise Roman
ownership during another Faction's Event, a third-party defender, the
combined Slingers and Horse rate, and a saved reservation resumed through
the final Battle.
[Balearic Slingers](../../Reference%20Documents/Card%20Reference#L125) ·
[German Phalanx](../../Reference%20Documents/Ariovistus/A%20Card%20Reference#L127) ·
[Legio X](../../Reference%20Documents/Card%20Reference#L147) ·
[PR-13](../provisional-rulings.md#pr-13)

Consuetudine retains the rest of the Germans Phase Battle procedure. In the
two-defender fixture, the selected human defender takes the Losses and the
other Faction's pieces survive. A separate fixture confirms Slingers can
reduce the German Attack after the defender has been selected.
[Consuetudine](../../Reference%20Documents/Card%20Reference#L528) ·
[Germanic Battle](../../Reference%20Documents/Chapter%203#L362) ·
[Germans Phase](../../Reference%20Documents/Chapter%206#L55)

## Verification

Tests ran on Python 3.12.14 against parent
`9ab48e08fd42e040bd8857d96ff15b540a34e08b`. The repaired Python source
SHA-256 is `9e46909f7b5665b3f2c10f2ee8c50759176aa8959c1bdbd16ac8d256796a3fd3`
across 600 files.

| Check | Result |
|---|---|
| Full suite | 9,956 passed. Of 25 added cases, 18 reproduced defects on the parent and seven controls passed there. |
| Audited bot games | All 100 legacy and 20 second-edition games completed with full rankings, clean piece and structure checks, and only legal declines. Eleven reached the Interlude. |
| Mixed-player replay | All 20 second-edition cases matched across hash seeds 0 and 987. Each run had 562 human turns, 153 Event attempts, 141 executed Events, zero hard findings and one partial plan. |
| Balance | All 100 games stayed within the 15-point band against the reviewed baseline. The largest win-rate shift was 10 percentage points. |

The legacy matrix uses seeds 1–20 and the second-edition matrices use
seeds 41–44 across all five scenarios.

## Paired outcomes

Eight games changed final board compared with Batch 2, including four
changed winners. The replays match the audited winners, game lengths
and final boards. They share the same starting position and RNG state at
the first changed Command in each game. Five first diverged when Slingers
fired on a free German Limited Battle. Three first diverged when Consuetudine
resolved one defender in its Region, including one where Slingers also fired.

| Legacy scenario and seed | Prior winner | Repaired winner | First changed Battle |
|---|---|---|---|
| Ariovistus 12 | Germans | Romans | Slingers removes the four selected Warbands before Battle in Sugambri. |
| The Great Revolt 14 | Arverni | Romans | Germans Ambush the Belgae once in Morini and the Romans survive. |
| The Gallic War 12 | Aedui | Romans | Slingers removes the four selected Warbands before Battle in Sugambri. |
| The Gallic War 15 | Romans | Aedui | Slingers removes one German Warband before Battle in Sequani. |
