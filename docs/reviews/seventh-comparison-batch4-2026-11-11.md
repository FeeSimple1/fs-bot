# Seventh comparison repairs, Batch 4 · 11 November 2026

Batch 4 closes BE7-01, BE7-02, and BE7-03. Two of the nine audit groups remain open.
[Finding ledger](comparison-audit-round7-2026-11-11.json) ·
[Validation evidence](seventh-comparison-batch4-2026-11-11-evidence.zip)

Oppida's bot plan previews its Ally placements before choosing Citadel
upgrades. Newly allied Cities join the existing own City Allies as upgrade
options. The bot chooses among equally ranked Cities with the game RNG
when the Available pool limits selection. It continues its flowchart if
it can place neither an Ally nor a Citadel of its own.
[Oppida](../../Reference%20Documents/Card%20Reference#L281) ·
[Non-player Event priorities](../../Reference%20Documents/Chapter%208#L120)

The Roman bot replaces up to three enemy Ally discs within one Region of
named Caesar. It prioritizes actual replacements, then City and Remi discs
and the printed faction order. A selected source is removed when the Roman
replacement is unavailable or stacking forbids placement, such as at
Bibracte. The effectiveness check uses the same eligible discs as execution.
[Procillus](../../Reference%20Documents/Ariovistus/A%20Card%20Reference#L45) ·
[Event replacements](../../Reference%20Documents/Chapter%205#L16) ·
[Target priorities](../../Reference%20Documents/Chapter%208#L179)

Shaded Divico places up to twelve Available Arverni Warbands in Aedui and
Sequani. German bots use each Region's capacity to keep existing German
Control, splitting the placement if needed and declining when the safe
total is zero. With equal placement totals, the bot prefers a Region that
keeps its Control, then uses the game RNG for ties. Human players can still
choose any printed amount, including zero.
[Divico](../../Reference%20Documents/Ariovistus/A%20Card%20Reference#L88) ·
[German Event instruction](../../Reference%20Documents/Ariovistus/german_bot_event_instructions_ariovistus.txt#L37) ·
[Control](../../Reference%20Documents/Chapter%201#L192)

Both versions of shaded Rhenus Bridge now use the same Legion requirement
in bot selection and execution. A Legion in Germania or an adjacent Region
enables both Roman penalties. Availability checks and the detached Oppida
placement preview consume no live input or RNG.
[Rhenus Bridge](../../Reference%20Documents/Card%20Reference#L172) ·
[Ariovistus Rhenus Bridge](../../Reference%20Documents/Ariovistus/A%20Card%20Reference#L35)

## Verification

Tests ran on Python 3.12.14 against parent
`5cd57e5fe88f6f4dc9f2fbef1b40bbdb4f970d1d`. The repaired Python source
SHA-256 is `3f3b46987e4552b46f22931a7904f5c36c158d5c867ced64544e5e113beae640`
across 609 files.

| Check | Result |
|---|---|
| Full suite | 10,068 passed, including 25 new Event cases. The parent reproduces 21 failures and passes four controls. |
| Audited bot games | All 100 legacy and 20 second-edition games completed with clean integrity checks and valid four-faction rankings. |
| Mixed-player replay | Twenty second-edition cases matched byte-for-byte across hash seeds 0 and 987. Each run had 539 human turns, 143 Event attempts, 130 executed Events, three partial plans and zero hard findings. |
| Balance | The previous baseline flagged a 25-point shift in Pax Gallica Roman wins. The rerun matches all 100 reviewed winners and game lengths on the original seeds and 15-point band. |

## Paired outcomes

The legacy matrix uses seeds 1–20 and the second-edition matrix uses seeds
41–44 across all five scenarios. Each changed game first diverged at one
of the repaired Events from an identical pre-card board and RNG state.

| Edition | Games | Changed final states | Changed winners | Changed lengths |
|---|---:|---:|---:|---:|
| Legacy | 100 | 37 | 16 | 17 |
| Second edition | 20 | 10 | 6 | 5 |

Oppida accounts for 29 first differences. Fifteen add Citadels, ten decline
an Event with no own effect, and four change an equal-choice tie-break.
Procillus applies its replacement plan in two cases. Divico places its
Warbands in six. Bots decline ten ineffective Rhenus Bridge Events, six
on the base card and four on A18.

All five Pax Gallica games that changed winner first diverged at Oppida.
In legacy seed 4 the Belgae upgrade the new Ally at Avaricum to a Citadel
on card 14. Romans win at card 70, where Belgae previously won at card 27.
In Ariovistus second-edition seed 43 the Germans place twelve Arverni
Warbands in Sequani on card 13 and win where Romans previously won.

The prior 100-game baseline matched the parent outcomes exactly. Roman
wins in its 20-game Pax Gallica sample rose from 50% to 75%. The reviewed
refresh updates 23 outcome records, including 16 winners and 17 card
counts. The seed coverage and both the 15-point guardrail and 40-point
canary bands remain the same.
