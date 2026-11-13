# Tenth comparison repairs, Batch 4 · 13 November 2026

Batch 4 closes UI10-01, UI10-02 and UI10-03. Seven of the nine tenth-audit
groups are closed. [Finding ledger](comparison-audit-round10-2026-11-13.json) ·
[Validation evidence](tenth-comparison-batch4-2026-11-13-evidence.zip)

## Completed card summaries

The terminal reports the Special Ability that resolved and uses the
successful operations to name its Regions when the result provides them.
In the audit position, Raid earns the Resources for Entreat, and the
completed summary names Entreat in Carnutes. The Roman Command line omits
the declined Build. The live forecast continues to describe the plan.
[Completed formatter](../../fs_bot/cli/display.py)

Battle records the Regions where Ambush or Besiege took effect. The
formatter can still show the recorded plan's ability for older Battle
results that carry only the execution flag. Verified replay compares
the board, RNG and execution history with the new Battle display field
omitted from the checkpoint fingerprint. An older save paused between
two Eligible Factions on the same card verifies through the assistant
replay command.

## Base Enlist March

The terminal lets Belgae choose the German group by Hidden, Revealed and
Scouted counts. The engine translates the chosen counts through the origin
flip. A selected Scouted Warband loses its marker and moves Revealed.
Every base-game Warband at the origin still flips as required, including
those that stay. The base option allows one group and one adjacent Region.
The Ariovistus four-piece limit and grouped option still apply. Integer
and omitted counts retain the legacy movement order.
[Germanic March §3.4.2](../../Reference%20Documents/Chapter%203#L354) ·
[Enlist §4.5.1](../../Reference%20Documents/Chapter%204#L215) ·
[Assistant Enlist plans](../../AGENT_INTERFACE.md#1-top-level-turns--decision_func)

## Quarters Supply replay

A controller's Quarters Supply declaration now lists its playable Regions
in map order. The declaration applies to that controller during Quarters,
including when the Roman standard planner asks while exploring an origin.
An older decision signature can match a representative Region controlled
by the same faction on the same board. Ordinary Supply and Quarters
hosting retain their Region-specific signatures. Changing the board, RNG,
controller, requester, Region eligibility, or request type still stops
replay.
[Roman Quarters §6.3.3](../../Reference%20Documents/Chapter%206#L84) ·
[Assistant Quarters requests](../../AGENT_INTERFACE.md#quarters)

The old engine recorded `Veneti` at hash seed 0 and `Aedui` at hash seed
987 for the same position. Both actual saves resume on the repaired
engine under the opposite seed at the identical after-payments request,
with the accepted agreement intact.

## Verification

Python 3.12.14 tested the repair to parent
`4cef37157157c3b3ec04886d3b6713bacd1605cb`. The repaired Python source
SHA-256 is `4a50d48f9557eb793bd746cdfd4e1c2d815d56675ba9eda49223a29a054c1240`
across 625 files. All 47 supplied reference documents and canonical
constants match their audit hashes.

| Check | Result |
|---|---|
| Directed tests | 28 new cases pass at both hash seeds. The focused run includes 19 existing free-action cases. The parent fails nine of the 19 new cases run against it. |
| Full suite | 10,357 pass. |
| Audited bot games | All 120 complete with clean integrity and valid rankings. All winners, card counts and final states match Batch 3. The sample covers all five scenarios on legacy seeds 1–20 and second-edition seeds 53–56. |
| Mixed-seat replay | All 20 second-edition cases agree byte for byte across hash seeds 0 and 987, with one recurring soft partial plan and zero hard findings. Fourteen raw trajectory digests change with the added Battle display field. Removing that field reproduces all 20 Batch 3 digests, including the boards and RNG. |
| Balance | All 100 games match Batch 3. The largest winner-share difference from the reviewed baseline is 10 percentage points against the 15-point band. |
