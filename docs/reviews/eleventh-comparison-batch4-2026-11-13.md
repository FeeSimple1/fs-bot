# Eleventh comparison repairs, Batch 4 · 13 November 2026

Batch 4 closes UI11-01. Six of eight findings in the eleventh comparison
audit are closed.
[Finding ledger](comparison-audit-round11-2026-11-13.json) ·
[Validation evidence](eleventh-comparison-batch4-2026-11-13-evidence.zip)

With two Winter Campaign actions available, Belgae can select **Command +
Enlist (both actions)**, choose a Command, and select the German Warbands
before planning its Regions and pieces. The terminal uses the ordinary
borrowed-Command collector on a detached board. In Ariovistus, the four-piece
limit applies across the selected Regions. The pieces stay German and return
to German treatment when the Command ends.
[Enlist §4.5.1](../../Reference%20Documents/Chapter%204#L195) ·
[Ariovistus Enlist A4.5.1](../../Reference%20Documents/Ariovistus/Chapter%20A4#L44)

Standalone Enlist spends one action on a free German Command. A paired
Belgic Command spends two actions and pays its usual Resource cost. The
base-game terminal allows the pair on a March into Britannia under card 63.
[Winter Campaign 63](../../Reference%20Documents/Card%20Reference#L645) ·
[Winter Campaign A63](../../Reference%20Documents/Ariovistus/A%20Card%20Reference#L279)

## Verification

Python 3.12.14 tested parent `0c2e6fa8098480ac84676d5e61dcb119ae8a3a4d` and
repaired Python source SHA-256
`95e58d60023a24eec5f2ca576b9d010f20faf4e23b4cacc2ae3e7c034a4c152d`
across 628 files. All 47 supplied references and the canonical constants
match their recorded hashes.

| Check | Result |
|---|---|
| Public terminal witness | The parent reproduces all 14 audit cases byte for byte. The repaired terminal reveals two German Warbands and gains two Belgic Resources in all five scenarios. Each Command uses both actions. Planning preserves the live board and RNG. The nine controls match the audit, including five assistant save/resume cases. Both repaired hash-seed outputs match. |
| Directed regressions | All nine added cases fail on the parent. The repair passes 187 focused tests at each of hash seeds 0 and 987. The regressions also cover the single-action menu, a four-piece loan across two Regions, and a borrowed March into Britannia that costs one Resource. |
| Full suite | 10,435 pass with seven external anyio/pytest deprecation warnings. |
| Audited bot games | All 120 complete across five scenarios on legacy seeds 1–20 and second-edition seeds 57–60. The game records, including final states, rankings and card counts, match Batch 3. All 1,983 diagnostics are legal declines. |
| Mixed-seat replay | The 20 second-edition cases on seeds 57–60 match at hash seeds 0 and 987 and match Batch 3. Zero hard findings and four partial plans. |
| Balance | The 100-game check matches every winner and card count in the reviewed Batch 3 baseline. The 15-game canary passes. |
