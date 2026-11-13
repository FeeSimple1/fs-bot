# Eleventh comparison repairs, Batch 1 · 13 November 2026

Batch 1 closes EV11-01, EV11-02 and EV11-03. Five of the eight findings remain
open. [Finding ledger](comparison-audit-round11-2026-11-13.json) ·
[Validation evidence](eleventh-comparison-batch1-2026-11-13-evidence.zip)

## Lucterius

The Arverni bot restores an eligible Successor as Vercingetorix in a Region
with the most Arverni pieces. The same legal destinations govern the
effectiveness check and placement. An existing named Leader or a Leader
still waiting in the Spring box leaves no eligible Successor, so the bot
continues down its Command flowchart. When another faction plays shaded
Lucterius, the Arverni choose the Region. The terminal and assistant session
can collect that choice using the existing Leader placement request.
[Lucterius](../../Reference%20Documents/Card%20Reference#L181) ·
[Leader placement §8.3.2](../../Reference%20Documents/Chapter%208#L158) ·
[Arverni Event check §8.7.2](../../Reference%20Documents/Chapter%208#L678)

## Assembly of Gaul

Roman and Aedui bots play the unshaded Event when Carnutes qualifies and an
instructed Gallic faction has Resources to lose. In the base game the Romans
target Arverni and Belgae, and the Aedui target their player seats. In
Ariovistus, Belgae is the eligible target for both instructions. The
expansion Aedui sheet names Germans in its instruction covering several
Events. Card 52's Gallic wording and §A5.1.1 limit this drain to Gallic
factions. Each selected faction loses up to eight Resources, with zero as
the floor. Human-authored lists apply the drain once per selected faction.
[Assembly of Gaul](../../Reference%20Documents/Card%20Reference#L518) ·
[Base Roman instructions](../../Reference%20Documents/roman_bot_event_instructions.txt#L18) ·
[Base Aedui instructions](../../Reference%20Documents/aedui_bot_event_instructions.txt#L30) ·
[Expansion Aedui instructions](../../Reference%20Documents/Ariovistus/aedui_bot_event_instructions_ariovistus.txt#L30) ·
[Gallic scope §A5.1.1](../../Reference%20Documents/Ariovistus/Chapter%20A5#L29)

## Shifting Loyalties

Bots use the active Capability side, the factions named by the effect or
the recorded holder, and the opponent seats in the current scenario. For
example, the Roman bot removes shaded Commius when the Belgae are a player
and retains unshaded Titus Labienus. The Aedui fallback uses the printed
first faction symbol. Equal candidates use the game RNG in a stable order.
When neither instruction tier has a target, the bot declines the Event.
Legacy active Capabilities remain eligible through the existing lookup, and
the removal clears the selected Capability's holder and companion modifiers.
[Shifting Loyalties](../../Reference%20Documents/Card%20Reference#L500) ·
[Base Roman priority](../../Reference%20Documents/roman_bot_event_instructions.txt#L42) ·
[Expansion Roman priority](../../Reference%20Documents/Ariovistus/roman_bot_event_instructions_ariovistus.txt#L49) ·
[Tie selection §8.3.4](../../Reference%20Documents/Chapter%208#L163)

## Verification

Python 3.12.14 tested the repair to parent
`2963f7f1c8bcb0d2ded319477950b4e3117aba3e`. The repaired Python SHA-256 is
`b52ed2a155095cd5b75938a3a02b2cbfe5708b1cf5c6faffda0f77c042f44035` across
628 files. All 47 supplied references and the canonical constants match the
audit hashes. The parent reproduces the original Event witness byte for byte.

| Check | Result |
|---|---|
| Directed regressions | 41 pass on the repair. The parent fails 35 and passes six controls. The Leader choice also survives a pending reply, save and reload with matching results at hash seeds 0 and 987. |
| Full suite | 10,420 pass with five external anyio/pytest deprecation warnings. The 27 balance canary and guardrail tests pass with the reviewed baseline. |
| Audited bot games | All 120 complete across the five scenarios with clean piece conservation, structure and rankings. All 1,999 diagnostics are legal declines. Nine games reach the Interlude. |
| Mixed-seat replay | All 20 cases match at hash seeds 0 and 987, with zero hard findings and four partial plans. Four cases differ from their parent runs. |
| Balance | Independent runs agree on all 100 winners and card counts. The previous baseline reports a 20-point shift in Great Revolt Belgic wins. The reviewed baseline passes with the original seeds and 15-point tolerance. |

## Paired outcomes

| Edition | Seeds per scenario | Games | Changed final states | Changed winners | Changed card counts |
|---|---|---:|---:|---:|---:|
| Legacy | 1–20 | 100 | 49 | 22 | 20 |
| Second edition | 57–60 | 20 | 9 | 5 | 2 |

All 58 changed bot games and four changed mixed-seat cases begin their first
differing card with matching board and RNG fingerprints. The bot games first
differ on Lucterius in 10 cases, Shifting Loyalties in 21, and Assembly of
Gaul in 27. On Ariovistus seed 6, the Roman Assembly drains the five Belgic
Resources. On Great Revolt seed 5, the Aedui use Shifting Loyalties to remove
shaded Convictolitavis, which doubles their Command costs.

Across the 20 Great Revolt seeds, the Belgae win one game, down from five.
Their four changed wins first diverge when the Aedui decline an ineffective
Assembly on seeds 10, 13 and 15, or when the Belgae decline an ineffective
Lucterius on seed 11. The original and reviewed comparisons and the paired
traces are preserved. The refresh changes 24 of the 100 baseline records,
including 22 winners.
