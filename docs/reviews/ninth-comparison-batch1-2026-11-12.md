# Ninth comparison repairs, Batch 1 · 12 November 2026

Batch 1 closes EV9-01 through EV9-03. Three of the eight ninth-audit groups
are complete. [Finding ledger](comparison-audit-round9-2026-11-12.json) ·
[Validation evidence](ninth-comparison-batch1-2026-11-12-evidence.zip)

The Alpine Tribes bot places its own Allies in distinct legal Regions
before filling the remaining slots with its own Auxilia or Warbands. It
prefers City Allies within the chosen Region and uses the game RNG for
equal choices. If no legal own placement is possible, it declines the
Event. The availability check leaves the board and RNG at their original
positions.
[Alpine Tribes](../../Reference%20Documents/Ariovistus/A%20Card%20Reference#L196) ·
[Non-player placement priorities](../../Reference%20Documents/Chapter%208#L120)

The live Alpine Tribes handler checks the selected recipient's stacking
rights before each placement. Gallia Togata limits Cisalpina to Roman
pieces. The restriction applies to the bot's plan and to authored Allies,
Warbands and Auxilia. A rejected placement rolls back the Event. Players
can still choose any permitted recipient and an optional quantity,
including zero, and can reclaim pieces at the existing placement windows.
[Gallia Togata](../../Reference%20Documents/Ariovistus/A%20Card%20Reference#L9) ·
[Event stacking rules](../../Reference%20Documents/Chapter%205#L24)

Unshaded Lost Eagle requires a Fallen Legion and a playable Region with
both a Legion and a non-Aedui Warband. Bot selection, the terminal and
execution all check the same destinations. The bot uses the seeded tie
break when several destinations qualify. An authored choice can select
any eligible destination. The shaded side still applies its next-Senate
restriction even when the Fallen box is empty.
[Lost Eagle](../../Reference%20Documents/Card%20Reference#L327) ·
[Ineffective Events](../../Reference%20Documents/Chapter%208#L30)

## Verification

The runs used Python 3.12.14 on the repair to parent
`5f7d0583f29784812f65eca9829c9b631ce43820`. The repaired Python source
SHA-256 is `4504d842ed230694a914f640a63900bd630243701805b3ea70d483129eac8217`
across 617 files.

| Check | Result |
|---|---|
| Directed cases | 23 pass. The prior revision reproduces 21 failures and passes two controls. |
| Related Event tests | 317 pass, including the directed cases. |
| Full suite | 10,230 pass with the reviewed balance baseline. |
| Audited bot games | 120 complete with clean inventory and structure, valid rankings and only legal declines. Eleven reach the Interlude. |
| Mixed-player replay | Twenty second-edition cases match at hash seeds 0 and 987. Each run has 747 human turns, 208 Event attempts, 186 executed Events, one partial plan and zero hard findings. |
| Additional replay sample | Fifteen second-edition cases on seeds 201–203 match at hash seeds 0 and 7. Two partial plans and zero hard findings. |
| Balance | The 100-game check and the 15-game canary pass with the reviewed outcomes. Both use their existing seeds and limits. |

The directed cases use normal bot dispatch, the public Event executor,
terminal choice collection, and a save and reload after Gallia Togata.
The evidence archive includes the parent failures, the repaired suite,
paired game records, and the scripts used to check them.

## Paired outcomes

The legacy sample uses seeds 1–20 in all five scenarios. The second-edition
sample uses seeds 49–52 in the same scenarios. Each changed game starts
its first differing card with matching board and RNG fingerprints.

| Edition | Games | Changed final states | Changed winners | Changed lengths |
|---|---:|---:|---:|---:|
| Legacy | 100 | 23 | 13 | 8 |
| Second edition | 20 | 4 | 2 | 1 |

Twenty-two bot games first change when Alpine Tribes places an Ally.
Two first change when a troop placement uses the seeded Region tie break.
Gallic War legacy seed 1 first changes when the Aedui place three Warbands
in Sequani after Gallia Togata closes Cisalpina to them. In Gallic War
second-edition seed 50, the Aedui decline an Alpine Tribes with no legal
own placements. In Reconquest legacy seed 18, the Aedui decline Lost Eagle
with an empty Fallen box. Three mixed games first differ on Alpine Tribes.
They cover a different legal troop destination, an Ally placement, and
rejection of an authored placement outside the Event area.

The first full run passed 10,229 tests and failed the balance canary. All
three legacy Gallic War canary games had been recorded as Belgic wins.
The earlier Aedui Battle repair had already changed seed 1's winner, and
the Alpine Tribes changes now affect all three games. The 100-game check
against the old baseline passed, with the largest change at exactly its
15-point limit. The reviewed baseline updates 20 of its 100 outcomes,
including 17 winner changes and 11 length changes. Six of the 20 entries
incorporate already traced changes from the eighth audit's final batch.
The audited and independent balance runners agree on all 100 winners and
game lengths. The 15-point full and 40-point canary limits stay in use.
[Earlier Aedui outcome review](eighth-comparison-batch5-2026-11-12.md#paired-outcomes)
