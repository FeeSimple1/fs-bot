# Fifth comparison repairs, Batch 3 · 11 November 2026

| Finding | Repaired behavior |
|---|---|
| FE5-01, Britannia | An Event-granted March rejects any accompanying Special Ability when a group would move into or out of Britannia. Validation checks the ordinary route forms and execution checks the actual moves. |
| FE5-02, transit choices | A standard free March offers the player the existing `march_dropoff` choice before the next hop. Assembly of Gaul offers it with zero, one or two abilities. The remaining pieces continue together and the Command costs no Resources. |

[Finding ledger](comparison-audit-round5-2026-11-11.json) ·
[Validation evidence](fifth-comparison-batch3-2026-11-11-evidence.zip)

Chapter 5 §5.4 retains the ordinary March rules when an Event grants a free
Command. Chapter 3 provides the drop-off choice, and Chapter 4 §4.1.3
prohibits an accompanying ability when crossing to or from Britannia.
Land of Mist and Mystery grants an independent ability in Britannia.
Marches with an Event-required destination follow their own procedure.
[Chapter 3](../../Reference%20Documents/Chapter%203#L52) ·
[Chapter 4](../../Reference%20Documents/Chapter%204#L38) ·
[Chapter 5](../../Reference%20Documents/Chapter%205#L78) ·
[Card reference](../../Reference%20Documents/Card%20Reference#L518)

An illegal crossing plan leaves the free Command pending under its existing
decision ID. A drop-off can also pause, save and reload while the committed
board and RNG stay at the start of the action. The tests correct invalid
responses and replay both completed actions. Older legal transcripts that
used the default keep their groups together at the added prompt.

## Verification

Tests ran on Python 3.12.14 against parent
`e9a4088376619ee3b59f6d4fdd13b9a3a2f4db0b`. The repaired Python source
SHA-256 is `d53c63e94fefe02d91b1c8c9339b071bca3bdc9472f263aa4f68b0d8a89b9d02`
across 594 files.

| Check | Result |
|---|---|
| Full suite | 9,863 tests passed. |
| Focused checks | 40 passed on the final revision. Ten new cases reproduced the defects on the parent, and eight new controls passed on both revisions. |
| Audited bot games | 100 legacy and 20 second-edition games passed with complete rankings, clean integrity checks and zero nonlegal diagnostics. All match the parent in winners, lengths and final boards. |
| Mixed-player replay | Twenty second-edition cases match across hash seeds 0 and 987 with zero hard findings and two partial plans. |
| Balance | The 100-game check passed the existing 15-point band. |

The legacy matrix uses seeds 1–20 and the second-edition matrices use
seeds 29–32 in all five scenarios. The directed tests cover exact, inferred
and extra-group routes, both crossing directions, legal in-place flips in
Britannia, and the independent Land of Mist and Mystery ability. The
Roman transit test leaves one Auxilia in Sequani and moves the other to
Mandubii without paying Resources.

Six of the fifth audit's eleven findings are closed.
