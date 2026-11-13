# Falling Sky bot engine

A Python engine for **Falling Sky: The Gallic Revolt Against Caesar** and
**Ariovistus**, with interactive human play, published non-player flowcharts,
assistant-controlled seats, and reproducible automated games.

The ninth comparison audit is complete with all eight groups closed. The
final batch corrects Arverni Devastate forecasts and the Special Abilities
the Arverni and Belgae choose after Rally and Raid.
[Audit and repair reports](docs/reviews/comparison-audit-round9-2026-11-12.md)

Roman Build now preserves the player's selected Region order, including
Ally/Subdue before a Fort elsewhere. [Repair and validation](docs/reviews/build-order-2026-11-04.md).

March also supports paying for an origin and hiding its pieces without moving.
[Stay-in-place repair and validation](docs/reviews/march-stay-2026-11-04.md).

Roman Besiege now offers exact Citadel, Ally Tribe and expansion Settlement
choices. [Repair and validation](docs/reviews/besiege-choice-2026-11-04.md).

The first Harvest now offers exact Legion allocations across Belgica, including
after Interlude when its Winter box holds Legions. [Repair and validation](docs/reviews/harvest-legions-2026-11-04.md).

Gallic Shouts now presents the Roman player's actual private two-card peek
before choosing its benefit. [Repair and validation](docs/reviews/gallic-shouts-peek-2026-11-04.md).

Devastate now asks each human owner for exact casualties, including visibility
and Legion choices. [Repair and validation](docs/reviews/devastate-losses-2026-11-04.md).

Quarters now lets owners select exact Hidden/Revealed/Scouted relocation cohorts,
including Roman Provincia continuations. [Repair and validation](docs/reviews/quarters-visibility-2026-11-04.md).

Three expansion Events now offer their printed optional quantities, exact
Warband targets, and the Auxilia/Resources tradeoff. [Batch repair and validation](docs/reviews/expansion-up-to-2026-11-04.md).

Drought now lets every human owner select exact casualties, including named
Tribes, visibility and Leaders. [Repair and validation](docs/reviews/drought-losses-2026-11-04.md).

Scout now allocates each Auxilia across exact Warband factions and visibility
cohorts. [Repair and validation](docs/reviews/scout-allocations-2026-11-04.md).

Romans now choose the Interlude expedition, its exact force and one Dispersed
marker to preserve through Spring. [Repair and validation](docs/reviews/interlude-roman-choices-2026-11-04.md).

Battle casualties now offer exact visibility and named Allied Tribes.
[Repair and validation](docs/reviews/battle-loss-identity-2026-11-04.md).

Rampage targets now choose exact pieces and can mix removal with Retreat.
[Repair and validation](docs/reviews/rampage-victims-2026-11-04.md).

Sudden Frost, Even Initiative and the shorter Great Revolt are selectable
at setup and retained through saves and replay.
[Repair and validation](docs/reviews/setup-options-2026-11-04.md).

Shaded Ballistae now asks its owner whether to remove a surviving defending
Fort or Citadel after each Ambush, with terminal and durable replay support.
[Repair and validation](docs/reviews/ballistae-choice-2026-11-05.md).

Balearic Slingers now offers the Roman Region choice for ordinary/free Battle
plans and applies the printed Germanic Horse pre-fire bonus.
[Repair and validation](docs/reviews/slingers-choice-2026-11-05.md).

Germanic Horse now offers its Roman/Gallic owner's ordinary/free Battle
Region choices, including defensive use and Roman decline. Abatis correctly
blocks its attacking bonus. [Repair and validation](docs/reviews/horse-choice-2026-11-05.md).

Unshaded Horse now offers live use/reserve/decline windows in prospective
Battles, including after Retreat arrivals. Slingers and shaded Horse now offer
mandatory use/reserve windows under [provisional PR-13](docs/provisional-rulings.md#pr-13).
[Mandatory queue repair and validation](docs/reviews/capability-queue-2026-11-05.md).

Lucterius and Hostages now offer their optional quantities and exact physical
piece choices, including Hostages removal without replacement.
[Repair and validation](docs/reviews/base-piece-choices-2026-11-05.md).

Shaded Pompey and base Gallia Togata give Rome exact removal choices across
Regions, including Auxilia visibility. [Repair and validation](docs/current-status.md#5-november-roman-event-removals).
The expansion Gallia Togata (A5) also offers the Roman choice and completes
delegated removals. [Ariovistus repair and validation](docs/current-status.md#5-november-shaded-gallia-togata-a5).

Unshaded Usipetes & Tencteri (A36) offers exact choices of German Settlements
and Warbands across its three Regions. [Repair and validation](docs/current-status.md#5-november-unshaded-usipetes--tencteri-a36).

Shaded Publius Licinius Crassus (A17) offers exact Auxilia choices in one
Region and applies the German bot's geographic limits. [Repair and validation](docs/current-status.md#6-november-shaded-publius-licinius-crassus-a17).

Shaded Aduatuci (A58) offers exact Roman replacements and resolves the
Ambush in the selected Belgica Region. [Repair and validation](docs/current-status.md#6-november-shaded-aduatuci-a58).

Unshaded Bellovaci (A69) offers exact Belgic Warband removals and separate
Ally and troop choices. [Repair and validation](docs/current-status.md#6-november-unshaded-bellovaci-a69).

## Play

Python 3.10 or newer is required. Playing uses only the standard library.
From the repository directory:

```sh
python -m fs_bot --save autosave.json
```

For an installed command, run `python -m pip install .` from a checkout,
then `fs-bot --save autosave.json` from your game directory. Installation
includes the unchanged reference inputs needed to display card text. See
[release and compatibility checks](RELEASES.md) for building and verifying
a local distribution.

The setup wizard offers the five scenarios and lets you choose human or bot
control for each playable faction. On Windows, `play.bat` starts the same
interface. Resume a saved game with:

```sh
python -m fs_bot --load autosave.json --save autosave.json
```

During human decisions, the display provides current/upcoming card text and
changes since your previous decision. Enter `board` or `b` at a prompt to
inspect the board. Command and Special Activity can be chosen in either
order, subject to the action's rules; Battle modifiers resolve within Battle.

Use `--card-edition original`, `second-edition`, or `legacy` when starting a
game. The saved choice governs the five optional revised cards. The default
`legacy` uses original versions in base scenarios and revised versions in
Ariovistus; explicit editions persist through the Gallic War Interlude.
See [Playing](PLAYING.md) for timing, decisions, saves, and edition details.

Original scenarios also support `--diviciacus-option`, independently of
card edition. This replaces card 38 with O38 and enables the optional
Diviciacus Leader rules. The choice is saved with the game.

Additional setup flags are `--sudden-frost`, `--even-initiative` (except Pax
Gallica?), and `--short-great-revolt` (Great Revolt only). Sudden Frost requires
all players' agreement at setup. The same flags are available to assistant
`init`; see [Playing](PLAYING.md) for their deck and timing effects.

## Documentation

| Need | Start here |
|---|---|
| Play in the terminal | [Playing guide](PLAYING.md) |
| Play with an AI assistant | [Assistant guide](CHATGPT_README.md) |
| Integrate a human or software agent | [Agent interface](AGENT_INTERFACE.md) |
| Review fixes and remaining limitations | [Current engineering status](docs/current-status.md) |
| Inspect outcomes and reproducible evidence | [Rules adoption and Trade choice](docs/reviews/rulings-trade-2026-10-29.md), [Recruit/Rally repairs](docs/reviews/recruit-rally-2026-10-29.md), [Spring Leader repairs](docs/reviews/spring-leaders-2026-10-28.md), [Event-choice repairs](docs/reviews/second-batch-2026-10-27.md), [first comparison batch](docs/reviews/first-batch-2026-10-27.md) |
| Review adopted provisional rulings | [Project rulings](docs/provisional-rulings.md), [question ledger](QUESTIONS.md#current-open-source-questions) |
| Develop and validate changes | [Developer instructions](CLAUDE.md), [maintenance roadmap](BUILD_PLAN.md), [self-play workflow](SELFPLAY_PLAYBOOK.md) |
| Install or check a release | [Release guide](RELEASES.md), [change history](CHANGELOG.md) |
| Browse all project documentation | [Documentation index](docs/README.md) |

## Current validation

The ninth comparison repairs pass **10,279 tests** and complete all 120
audited bot games and 35 mixed-player replay cases. The 100-game balance
baseline records the verified outcomes of the corrected bot decisions.
[Final batch repairs and validation](docs/reviews/ninth-comparison-batch4-2026-11-13.md)

Batches 1–5 close **all 11 findings** from the eighth comparison audit.
Batch 5 corrects the Aedui bot's additional Battles and its Trade or Suborn
selection after Rally.
All **10,207 tests** pass, along with 120 audited bot games, 35 mixed-player
replay cases, and the 100-game balance check.
[Audit report](docs/reviews/comparison-audit-round8-2026-11-12.md) ·
[Batch 1 repairs and validation](docs/reviews/eighth-comparison-batch1-2026-11-12.md) ·
[Batch 2 repairs and validation](docs/reviews/eighth-comparison-batch2-2026-11-12.md) ·
[Batch 3 repairs and validation](docs/reviews/eighth-comparison-batch3-2026-11-12.md) ·
[Batch 4 repairs and validation](docs/reviews/eighth-comparison-batch4-2026-11-12.md) ·
[Batch 5 repairs and validation](docs/reviews/eighth-comparison-batch5-2026-11-12.md) ·
[Finding ledger](docs/reviews/comparison-audit-round8-2026-11-12.json)

The seventh comparison audit is complete with **all nine repair groups closed**.
The final batch accounts for legal Ambushes before selecting Battles and
uses shaded Baggage Trains' three-Warband limit when planning Raids.
[Audit report](docs/reviews/comparison-audit-round7-2026-11-11.md) ·
[Batch 5 repair and validation](docs/reviews/seventh-comparison-batch5-2026-11-11.md) ·
[Batch 4 repair and validation](docs/reviews/seventh-comparison-batch4-2026-11-11.md) ·
[Batch 3 repair and validation](docs/reviews/seventh-comparison-batch3-2026-11-11.md) ·
[Batch 2 repair and validation](docs/reviews/seventh-comparison-batch2-2026-11-11.md) ·
[Batch 1 repair and validation](docs/reviews/seventh-comparison-batch1-2026-11-11.md)

The sixth comparison audit is complete with **14 of 14 findings repaired**.
The final batch corrects bot Battle forecasts, high-value target checks,
and Roman Rampage threat detection. All **9,991 tests pass**, 120 audited
bot games complete cleanly, and 20 mixed-player cases match across two hash
seeds with zero hard findings and one partial plan. The refreshed 100-game
balance check passes within the 15-point band.
[Repair and validation](docs/reviews/sixth-comparison-batch5-2026-11-11.md) ·
[Current status](docs/current-status.md)

The [fourth comparison's final repair batch](docs/reviews/fourth-comparison-batch4-2026-11-11.md)
corrects the Gallic War Interlude's deck rebuild and retires Nori when
Britannia opens. All 16 findings in the fourth audit are closed.
The report records the fixed-seed outcomes and saved-game checks.

The [third comparison's final repair batch](docs/reviews/third-comparison-batch4-2026-11-10.md)
fixes Colony Tribe handling, Razed City protection, and Stalwart's cancellation
of Germanic Horse against Germans. At that revision **9,686 tests passed**, including 104 new
cases. Twenty audited bot games are clean, and twenty mixed-player cases match
across hash seeds with replay and zero hard findings. The 100-game balance
check passes the unchanged 15-point band, with no winner changes from the parent.

The [third-audit ledger](docs/reviews/comparison-audit-round3-2026-11-10.json)
records **all 15 groups repaired** after the original 50 and next 21 findings
were repaired. Earlier repair reports and dated
checkpoints below retain their original measurements.

The [first small audit repairs](docs/reviews/cheap-fixes-2026-10-29.md) close
five findings: mandatory Battle casualty tiers, repeated Seize/Entreat,
malformed Supply replans, game-run Arverni transfers and sole-human-Belgae
Great Revolt setup. The [Scouted Event repair](docs/reviews/scouted-events-2026-11-02.md)
also closes omitted mandatory removals on A25, A26, A30 and A56. The
[expansion Event-grant batch](docs/reviews/human-event-grants-2026-11-02.md)
closes EXP-01 through EXP-06: human Battle, March, Raid and beneficiary
choices, optional Roman benefits, and the printed Seize exceptions.
The [Gallia Togata and Dread repair](docs/reviews/expansion-effects-2026-11-02.md)
closes EXP-07 and EXP-10: owner-directed Cisalpina evacuation, the additional
Intimidating Warband, and unshaded Dread's Roman Recruit immunity.
The [Event validation batch](docs/reviews/event-validation-2026-11-03.md)
closes BE-11, BE-12 and EXP-09: printed target/quantity limits, correct German
Allegiances replacements and pending retries for invalid human Events.
The [named-faction Event repair](docs/reviews/named-event-effects-2026-11-02.md) closes BE-04, including
Roman and Arverni decisions when another faction plays the Event.
The [Colony follow-up](docs/reviews/colony-event-defaults-2026-11-02.md) fixes
dynamic Tribe locations in Event defaults and catches rejected bot Events
in mixed-player validation.
The [Gallic Event repair](docs/reviews/gallic-event-grants-2026-11-02.md)
adds beneficiary and Command-order choices on 35/46/67 and correct Remi
ownership on 68. The owner adopted PR-10/PR-11 for automatic Arverni
Commands and numeric Arduenna prediction. This validated repair closes BE-03;
other grouped Event March grants remain open.
The [ordinary Arverni Phase repair](docs/reviews/arverni-phase-2026-11-03.md)
fixes the five follow-up Rally, March and Raid defects, plus protected-Tribe
placement and untracked Arverni Resources. These additional defects are
outside the original audit denominator.
The [Event Battle repair](docs/reviews/event-battle-choices-2026-11-03.md)
restores human targets on 11/25/36/45/70, enforces revised Numidians'
Auxilia-only participation, removes Litaviccus's Aedui double-count and
includes printed Event Loss modifiers in non-player Retreat decisions.
The [Litaviccus follow-up](docs/reviews/litaviccus-targeting-2026-11-03.md)
implements provisional PR-12 targeting and full Aedui Battle participation.
This separate follow-up is outside the original audit denominator.
The [Camulogenus repair](docs/reviews/camulogenus-2026-11-03.md) adds the
Roman-owned acceptance and exact March planning on numeric 70. It is a
partial repair of BE-01. The [Mons Cevenna repair](docs/reviews/mons-cevenna-2026-11-03.md)
adds numeric 9's exact human March and destination-scoped follow-on;
The [Aduatuca repair](docs/reviews/aduatuca-2026-11-04.md) restores numeric58's
executor-owned Fort and German March choices. The [German guidance repair](docs/reviews/german-guidance-2026-11-04.md) restores
numeric65's human March and Ambush choices. The [Germanic Chieftains repair](docs/reviews/germanic-chieftains-2026-11-04.md)
restores numeric17's Roman-owned groups and single Ambush. The [Circumvallation choice repair](docs/reviews/circumvallation-2026-11-04.md)
completes BE-01. [Persistent marker mechanics](docs/reviews/circumvallation-persistence-followup-2026-11-04.md)
remain a separate verified high-priority follow-up. The
[no-Romans cleanup repair](docs/reviews/circumvallation-no-romans-2026-11-04.md)
now clears the marker after the last physical Roman leaves; the other
persistent effects remain open.
The [planning-board inspection repair](docs/reviews/planning-board-inspection-2026-11-03.md)
closes FE-01: `b`/`board` at Command menus show the position after the preceding SA.
The [Intimidate Tribe repair](docs/reviews/intimidate-tribes-2026-11-04.md)
closes CMD-INTIMIDATE-TRIBE with exact disc choices across ordinary, Raid-linked
and A45 uses.
The [Rampage quantity repair](docs/reviews/rampage-quantity-2026-11-04.md)
closes CMD-RAMPAGE-COUNT and restores the source-required full NPC quantity.
The [Seize Tribe repair](docs/reviews/seize-tribes-2026-11-04.md) closes
CMD-SEIZE-TRIBES with exact ordinary dispersals and Forage-only choices.
**All 50 original findings are closed** in the
[progress register](docs/human-choice-progress.json). This counts findings,
not effort or overall rules compliance. The reports record fresh validation,
source identity, outcome changes and compatibility limits.

The [human-choice audit](docs/reviews/human-choice-audit-2026-10-29.md) records
**50 grouped findings at its audited revision** across 490 inventory rows, including rule errors,
missing decisions and previously documented or optional feature limits.
Eleven representative probe scripts were independently rerun; the unchanged
engine still passes **6,109 tests**. The audit makes no engine fixes and
does not certify every rule interaction. Its ordered repair backlog supersedes
earlier statements that the broader choice inventory was still pending.

The [29 October action-timing report](docs/reviews/action-timing-2026-10-29.md)
describes voluntary piece reclamation, Vercingetorix's mid-action entry,
same-Region Rally interruption, and the related fixes found during their
integration. It records **6,109 passing tests**, **150 audited bot games**,
**80 mixed-seat executions including replay**, and **50 strict-census
executions**. It preserves the original balance failure, the paired causal
review and the independently reviewed baseline refresh at the unchanged
15-point limit. Fresh games exactly reproduce that reviewed baseline.
These measurements are separate from the earlier checkpoints below.

The [29 October rules and Trade report](docs/reviews/rulings-trade-2026-10-29.md)
records **5,777 passing tests**, **150 audited bot games**, **80 mixed-seat
executions including replay**, and **50 strict-census executions**. Cross-hash
reports match and the original balance guardrail passes without a baseline
refresh. The report records the approved rulings, fixes, failed candidates
and remaining interface gaps.

The [29 October Recruit/Rally report](docs/reviews/recruit-rally-2026-10-29.md)
records 5,622 passing tests for exact quantities, ordered placements and related
bot, bonus and permission corrections. Its evidence distinguishes each
superseded candidate from the final source and remaining interface gaps.

The [28 October Spring Leader report](docs/reviews/spring-leaders-2026-10-28.md)
records 5,226 passing tests, 150 audited bot games and the separately reviewed
balance refresh. It identified the mid-action Vercingetorix entry gap
addressed by the later action-timing repair above.

The [27 October second-batch report](docs/reviews/second-batch-2026-10-27.md)
records **5,112 passing tests**, **200 audited bot games**, **80 mixed-seat
executions including replay**, and **50 strict-census executions** for the
Province, Ambacti, Council and Winter Uprising repairs. It preserves the
superseded failures, the bugs found through game traces, and the separate
reviewed baseline refresh at the unchanged 15-point limit. Cross-hash replay
and diagnostic reports match.

## First comparison checkpoint

The [27 October first-batch report](docs/reviews/first-batch-2026-10-27.md)
records **4,715 passing tests**, **200 audited bot games**, **80 mixed-seat
executions including replay**, and **50 strict-census executions** on the
Event integrity repairs. Cross-hash reports match and the unchanged balance
guardrail passes. The report also identifies the confirmed human-interface
and Spring-placement findings then outstanding.

## Earlier validation

The [provisional-ruling validation report](docs/reviews/provisional-rulings-2026-10-24.md)
records **4,481 passing tests**, **200 audited bot games**, **320 mixed-seat
executions with replay**, and **40 strict-census executions** on the adopted
implementation. All completed without defect findings; mixed-seat and census
reports matched across hash seeds. The 100-game balance check passed without
changing its baseline. The report gives exact source identities and scope.

All [twelve adopted project rulings](docs/provisional-rulings.md) remain subject
to possible later correction if an authoritative source is found.

## Earlier verified checkpoint

The [24 October follow-up report](docs/reviews/followup-repairs-2026-10-24.md)
records **4,431 passing tests**, **2,500 accepted bot games** across the
five scenarios and three card-edition profiles, **90 optional-Diviciacus
games**, and **1,000 mixed-seat executions** with replay. The accepted
bot matrix has no crashes, illegal diagnostics, integrity failures or
ranking/hash findings. The report identifies the exact source digest,
seeds, outcome statistics, installation checks and remote CI status.

The [23 October report](docs/reviews/outstanding-fixes-2026-10-23.md)
preserves the earlier checkpoint. Results apply to their tested revision
and paths; they do not establish that every possible position is correct.
The owner subsequently adopted [six provisional project rulings](docs/provisional-rulings.md).
Each is subject to possible later correction if an authoritative source is
found. The earlier checkpoint measurements do not validate that later
adoption. Historical strategy studies use older mechanics and have additional
harness limitations; consult their dated caveats before using their numbers
as play advice.

## Development

Install the test dependency, then run the full suite:

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Read [CLAUDE.md](CLAUDE.md) before editing. `Reference Documents/**` and
`fs_bot/rules_consts.py` are protected, read-only sources. Project guides,
reports, and strategy notes describe the implementation; they do not replace
the supplied rules. The twelve expressly adopted provisional rulings govern
their listed source gaps until corrected. The [self-play workflow](SELFPLAY_PLAYBOOK.md) documents
batch, census, determinism, and balance checks.
