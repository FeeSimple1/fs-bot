# Twelfth comparison repairs, Batch 1 · 14 November 2026

Batch 1 closes EV12-01 and EV12-02. Five of the audit's seven findings
remain open. [Finding ledger](comparison-audit-round12-2026-11-13.json) ·
[Validation evidence](twelfth-comparison-batch1-2026-11-14-evidence.zip)

## Unshaded Sappers

The Roman bot chooses an Arverni Citadel owner with Resources to lose
before considering the Belgae. The Aedui bot uses the same faction
priority within eligible player seats. The Event drains up to ten
Resources from one eligible faction. If no instructed target owns a
Citadel and has positive Resources, the bot continues down its Command
flowchart. A player can choose any Gallic faction with a Citadel,
including the Aedui. [Sappers](../../Reference%20Documents/Card%20Reference#L238) ·
[Roman instructions](../../Reference%20Documents/roman_bot_event_instructions.txt#L18) ·
[Aedui instructions](../../Reference%20Documents/aedui_bot_event_instructions.txt#L30)

## Drought

Roman and Aedui bots select the new Devastated Region at the marker
step. The instructed player opponents are Arverni and Belgae in the base
game and Germans and Belgae in Ariovistus. The Roman selection excludes
any Region with a removable Roman piece or a casualty for a non-player
seat of the named opponents. The Aedui selection requires that every
casualty belong to an instructed player opponent. Shared loss options
account for the permanent Provincia Fort and German casualty restrictions.
[Drought](../../Reference%20Documents/Card%20Reference#L487) ·
[Base Roman instructions](../../Reference%20Documents/roman_bot_event_instructions.txt#L27) ·
[Base Aedui instructions](../../Reference%20Documents/aedui_bot_event_instructions.txt#L30) ·
[Expansion Roman instructions](../../Reference%20Documents/Ariovistus/roman_bot_event_instructions_ariovistus.txt#L25) ·
[Expansion Aedui instructions](../../Reference%20Documents/Ariovistus/aedui_bot_event_instructions_ariovistus.txt#L30)

The bot ranks casualties each owner can be made to take under the Event
location priorities. Owners can sacrifice another eligible piece to
retain a Citadel or Settlement. Tied Regions use the game RNG. When
the instructions yield no new Region, §5.1.3 supplies the fallback used
here. Halve Resources and resolve casualties in already Devastated
Regions. A bot declines if none of these steps can have an effect.
[Partial execution §5.1.3](../../Reference%20Documents/Chapter%205#L52) ·
[Non-player Event locations and ties §§8.3.1, 8.3.4](../../Reference%20Documents/Chapter%208#L149) ·
[Expansion Settlement priority §A8.3.1](../../Reference%20Documents/Ariovistus/Chapter%20A8#L28)

## Verification

Python 3.12.14 tested the repair to parent
`7313c9d96436b5602323d1299ba34a904bd6514d`. The repaired Python source
SHA-256 is `f7c8439d35b50bb0c00488cf86e211fd94c2dfb4804b3585b8e638420777e452`
across 630 files. All 47 supplied references and the canonical constants
match the audit hashes. The parent reproduces the 43 original Event
witnesses and controls byte for byte.

| Check | Result |
|---|---|
| Directed regressions | All 41 new cases pass. The parent fails 37 and passes four controls. The broader set of 332 focused tests passes at hash seeds 0 and 987. |
| Full suite | 10,490 passed. Five external anyio deprecation warnings. |
| Audited bot games | All 120 finish across five scenarios using legacy seeds 1–20 and second-edition seeds 71–74. Nine reach the Interlude. Zero engine errors, integrity findings or ranking disagreements. All 2,027 diagnostics are legal declines. |
| Mixed-seat replays | All 20 finish at both hash seeds with matching JSON and stdout. The sample records 614 human turns, 149 Event turns, zero hard findings, and five partial plans. Two cases differ from the audit baseline. |
| Balance | The reviewed 100-game baseline and 15-game canary pass using the existing seeds and tolerances. The independent balance driver agrees on every winner and card count. |

## Paired outcomes

| Edition | Seeds per scenario | Games | Changed final states | Changed winners | Changed card counts |
|---|---|---|---|---|---|
| Legacy | 1–20 | 100 | 38 | 16 | 12 |
| Second edition | 71–74 | 20 | 5 | 2 | 1 |

All 43 changed games enter their first differing card with matching
boards and RNG states. Five first differ at Sappers and 38 at Drought.
Three and fifteen of those cases change the winner, respectively.
For example, on Great Revolt seed 1, the Aedui Rally after finding that
the only eligible opponent Citadels belong to non-player Arverni.
The winner changes from Romans to Belgae. On Gallic War seed 1, both
versions halve Resources after the Interlude. The repair leaves the
three non-player Belgic pieces at Morini, and the winner changes from
Arverni to Belgae.

The 100-game baseline records 18 changed winner or card-count entries.
The Gallic War Aedui win count moves from one to seven of 20, exceeding
the old reference's 15-percentage-point tolerance. The archive preserves
the original check, the paired Event effects, and the passing check of
the reviewed reference. These are outcomes for the fixed regression
sample. [Paired evidence](twelfth-comparison-batch1-2026-11-14-evidence.zip)
