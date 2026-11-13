# Ninth comparison repairs, Batch 4 · 13 November 2026

Batch 4 closes NP9-01 and NP9-02. All eight ninth-audit groups are complete.
[Finding ledger](comparison-audit-round9-2026-11-12.json) ·
[Validation evidence](ninth-comparison-batch4-2026-11-13-evidence.zip)

## Arverni Devastate

The bot uses the same casualty quotas as the Devastate procedure. A Roman
owner must lose a Legion or two Auxilia when every legal casualty choice
would meet at least one of those two conditions. The other trigger needs
at least one enemy casualty and at least as many Roman and Aedui losses
combined as Arverni losses. Owners still choose their exact casualties.
In the audit positions, four Arverni Warbands now stay intact against one
Legion or two Auxilia. Against three Aedui Warbands, each side loses one.
[Devastate procedure](../../Reference%20Documents/Chapter%204#L121) ·
[Arverni flowchart](../../Reference%20Documents/Chapter%208#L645)

## Special Abilities after Rally and Raid

The Arverni check Devastate and then Entreat after the Command's placements,
flips and Resource changes. The Belgae check Rampage and then Enlist. In
the audit positions, Rally places the Hidden Warbands that let the Arverni
Entreat, and Raid reveals the last Hidden Belgic Warbands so the Belgae
Enlist for a German March. The next eligible faction's options use the
ability that actually executed. The live checks respect Command-only and
regional grants. If Winter Campaign Raid enables an unforecast Entreat,
the Command and ability consume both paid actions.
[Arverni Rally](../../Reference%20Documents/Chapter%208#L701) ·
[Arverni Raid](../../Reference%20Documents/Chapter%208#L732) ·
[Belgic priorities](../../Reference%20Documents/Chapter%208#L304) ·
[Winter Campaign](../../Reference%20Documents/Card%20Reference#L645)

## Verification

The runs used Python 3.12.14 against parent
`6611fabab1fda6a6e4e8b71e537bd544458a8ff5`. The repaired Python source
SHA-256 is `39076dca68ec449cf766e40256c765d2d36693c50989a2b0552745f208f94d45`
across 620 files. The earlier Battle-payment regression now uses three
Auxilia, so Devastate has a mandatory Roman loss and exercises the timing
assertion on a legal position.

| Check | Result |
|---|---|
| Directed cases | All 28 pass. Batch 3 fails 15 and passes 13 controls. The original and repaired audit witnesses each repeat byte-for-byte at hash seeds 0 and 987. |
| Related tests | 437 pass. |
| Full suite | 10,279 pass. |
| Audited bot games | 100 legacy games on seeds 1–20 and 20 second-edition games on seeds 49–52, across all five scenarios. All complete with valid rankings, clean integrity and only legal declines. Eleven reach the Interlude. |
| Mixed-player replay | 20 second-edition cases match at hash seeds 0 and 987, and 15 match at 0 and 7. Zero hard findings. The same three partial plans recur. Twelve and nine trajectory digests respectively change from Batch 3. |
| Legacy mixed-player replay | All 200 cases on seeds 1–40 complete and match at hash seeds 0 and 7, with zero hard findings and 19 partial plans. |
| Balance | The refreshed baseline matches an independent 100-game run on every winner and card count. The original seed set and 15-point guardrail band apply. |

## Paired outcomes and balance

| Edition | Games | Changed final states | Changed winners | Changed card counts |
|---|---:|---:|---:|---:|
| Legacy | 100 | 62 | 28 | 23 |
| Second edition | 20 | 17 | 10 | 7 |

The first difference in each paired game starts from matching board and
RNG fingerprints. The evidence records 77 first card differences involving
the board and two involving only RNG. Both RNG-only differences came from
moving a speculative Enlist tie-break onto the detached forecast board.
The evidence includes the first different choices inside Winter Campaign
and a Belgic Rally granted by Druids.
[Druids](../../Reference%20Documents/Card%20Reference#L478)

Rome's Great Revolt wins moved from 5/20 to 1/20. All 11 changed winners
in that scenario first diverge at the Arverni Devastate decision. On
seed 1, the old bot lost two Warbands at Treveri without an enemy loss
before Battle on card 17. The repaired bot skips the ability and keeps
both. On seed 3, the old bot lost four Warbands at Treveri to one Roman
and one German casualty on card 27. The Roman casualty could be an
Auxilium. The repaired bot Entreats instead. Two runners independently
reproduced the revised outcomes before the baseline was refreshed.
These are fixed-seed bot outcomes for this revision.
