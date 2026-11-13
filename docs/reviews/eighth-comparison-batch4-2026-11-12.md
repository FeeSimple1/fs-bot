# Eighth comparison repairs, Batch 4 · 12 November 2026

Batch 4 closes EV8-01 through EV8-03. Nine of the eleven audit groups are
closed. [Finding ledger](comparison-audit-round8-2026-11-12.json) ·
[Validation evidence](eighth-comparison-batch4-2026-11-12-evidence.zip)

The Belgic bot declines shaded Legiones when no legal Battle forecasts a
Legion Loss. The forecast uses the live Battle procedure on a detached
board, including the automatic first Legion removal, opening fire, and the
published Roman bot Retreat policy. For a human Roman defender, the
forecast uses the standing Battle and default casualty priorities. The
player's actual Retreat and loss choices still resolve live. Equal positive
Legion-Loss forecasts use the seeded Region selection. The human Event can
still target Romans in a Region that has no Legion.
[Legiones text](../../Reference%20Documents/Card%20Reference#L14) ·
[Belgae instructions](../../Reference%20Documents/belgae_bot_event_instructions.txt#L37) ·
[Ariovistus instructions](../../Reference%20Documents/Ariovistus/belgae_bot_event_instructions_ariovistus.txt#L20) ·
[Roman bot Retreat](../../Reference%20Documents/Chapter%208#L207)

The Event check shares Pompey's four-or-fewer track Legion prerequisite
and Gallia Togata's Senate prerequisite with the removal handlers. At
least one printed removal must be possible. Partial removals remain
effective. A5 uses the shared shaded prerequisite and retains its own
unshaded placement and evacuation.
[Pompey and Gallia Togata](../../Reference%20Documents/Card%20Reference#L25) ·
[Gallia Togata A5](../../Reference%20Documents/Ariovistus/A%20Card%20Reference#L9)

Roman Forced Marches uses the existing War Fleet movement planner with
Forced Marches' endpoints. The planner applies Roman March priorities to
the direct relocations. The Event uses playable Regions outside Britannia,
including Cisalpina when Gallia Togata opens it in the base game. It moves
original counters, Hides the Auxilia it relocates, and charges no Resources.
The ordinary March and Recruit decision after declining an Event has its own
Auxilia threshold. Forced Marches grants only relocation. The availability
check leaves the live board and RNG untouched.
[Forced Marches](../../Reference%20Documents/Card%20Reference#L318) ·
[Roman instructions](../../Reference%20Documents/roman_bot_event_instructions.txt#L30) ·
[Roman March priorities](../../Reference%20Documents/Chapter%208#L818)

## Verification

The runs used Python 3.12.14 against parent
`0443eecba4d717bbfc6a89fc9d83e1645e13807b`. The repaired Python source
digest is `f966e191008ca5591d88f39f92da973d8a3fdc6674d53c18f2c32040fac7c46d`
across 615 files.

| Check | Result |
|---|---|
| Full suite | All 10,178 tests pass with the reviewed baseline. |
| Directed and related cases | All 18 directed cases and 861 focused tests pass. The parent reproduces 15 failures and passes three controls. |
| Audited bot games | All 120 complete with clean integrity checks, valid rankings, and only legal-decline diagnostics. Eleven reach the Interlude. |
| Mixed-player replay | Twenty second-edition cases match at hash seeds 0 and 987. Each run has 583 human turns, 140 Event attempts, 128 executed Events, and zero hard findings or partial plans. Three cases differ from Batch 3 and first diverge on Legiones, Pompey, and Forced Marches. |
| Additional second-edition CI sample | Fifteen cases on seeds 201–203 match at hash seeds 0 and 7. Zero hard findings and two partial plans. |
| Balance | The refreshed 100-game check and 15-game canary pass on their existing seed sets and bands. |

## Paired outcomes

The bot matrices use legacy seeds 1–20 and second-edition seeds 45–48
across all five scenarios. The primary mixed comparison uses second-edition
seeds 45–48. Every changed bot game starts its first differing card with
matching board and RNG fingerprints. Four diverge when the Belgae decline
Legiones, eight at Pompey with more than four Legions on the track, two at
Gallia Togata during Adulation, and five when Roman Forced Marches moves
pieces.

| Edition | Games | Changed final states | Changed winners | Changed lengths |
|---|---:|---:|---:|---:|
| Legacy | 100 | 14 | 7 | 6 |
| Second edition | 20 | 5 | 3 | 2 |

The first full suite failed only the three-seed balance canary. Against
the prior baseline, Belgic Gallic War wins in that sample rose from one
to three. Seed 1's change comes from reaching the fifth post-Interlude
Winter in Batch 1. Seed 3 first changes at shaded Pompey with five Legions
on the track. The Belgae choose a Command and eventually win on card 84.
The prior run ended with an Arverni win on card 102. The full 100-game
guardrail passed before the refresh.

The reviewed baseline updates ten of its 100 records, with nine winner
changes and eight game-length changes. It incorporates the two previously
traced final-Winter changes from Batch 1. The 100-game balance runner and
the audited game runner independently agree on every winner and length.
The 15-point full band and 40-point canary band remain in use.
[Batch 1 final-Winter traces](eighth-comparison-batch1-2026-11-12.md#paired-outcomes)
