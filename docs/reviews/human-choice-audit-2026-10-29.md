# Human-choice audit — 29 October 2026

The audit found **50 grouped open findings: 21 high, 28 medium and one low** at
commit `7e72fe7eda33c58b2f83457c39edf5b295a04f77`. These include rule errors, unavailable human choices,
previously documented limits, and optional features. They are not 50 newly
introduced regressions, nor 50 equally sized repairs. No engine fixes were made
in this audit. Verification completed on 30 October UTC.

The most urgent problems let players take illegal losses or repeat effects,
apply Events to the wrong faction, omit mandatory Event rules, or substitute
bot decisions for human decisions. Some omissions also affect bot play; a
balanced piece census and a completed game cannot detect all of them.

[Machine-readable inventory](human-choice-audit-2026-10-29-inventory.json) ·
[Reproduction evidence](human-choice-audit-2026-10-29-evidence.zip) ·
[Current status](../current-status.md)

## Scope and evidence

The review used the supplied Reference Documents, canonical constants and
the nine adopted provisional rulings. It did not reopen those rulings or
use outside interpretations. Seven partitions covered Commands/Special
Abilities, March/Battle, base/revised Events, expansion Events, seasonal/setup
decisions, shared frontends and general action timing.

There are **490 inventory rows**. These include every numeric base card and
O38 under original and second-edition profiles (292 side/profile rows), all
39 canonical A-prefix cards (78 side rows), and 120 other choice-family or
transport rows. Single-text cards have their two API aliases identified;
they do not acquire a fictional second printed effect. Legacy selects the
corresponding effective original/revised text, not a third rules version.
The expected identity/side/profile sets were checked programmatically.

| Inventory disposition | Rows | Meaning |
|---|---:|---|
| Supported in reviewed path | 286 | Source trace and/or existing regression evidence; not exhaustive verification |
| Confirmed gap | 169 | Rows linked to the 50 grouped findings; some findings affect multiple cards/profiles |
| Not verified | 34 | Bounded coverage limits, not 34 additional confirmed bugs |
| Existing source question | 1 | Physical non-player Elite designation; no new ruling adopted |

The inventory explicitly separates source inspection, existing regression
coverage and new executable witnesses. Representative findings were rerun
independently in **11 probe scripts**, all exiting successfully. Assertions
in these witnesses describe the observed defects; they should be converted
to desired-behavior regression tests during repair. The evidence includes
valid initialized positions, real menu traces, durable requests, a saved
pending casualty choice, raw outputs and source hashes. A representative
witness does not prove every statically related card subcase was executed.

The unchanged engine passes **6,109 tests** (zero failures/errors/skips).
Focused reviewers' test counts overlap this suite and must not be added
together. No new bot balance matrix was run for this documentation audit.
The previous repair's 150-game/mixed-seat/census results remain measurements
of that repair, not evidence that the newly identified gaps are absent.

Shared transport checks found all 26 reactive request kinds plus turn routed,
and stable missing-input pending behavior for those kinds. Display checks
rendered complete current/upcoming supplied card text for **1,080 card pairs**
across five scenarios and three saved profiles. These checks do not certify
every request's legal option set. FE-01 finds a stale `b` board after SA-first
planning; BE-10 finds a missing private Event peek; FE-02 finds malformed
Supply input that corrupts a pending boundary. The full Command in FE-02
still rolls back at a later window; committed illegal play was not demonstrated.

## Recommended repair order

Each finding is assigned once below. Batches are work groupings, not time or
token estimates. Batch 4 is intentionally broad and should be split into
small fixes with one shared physical-choice/timing design. The Interlude
batch can be prioritized sooner for Gallic War players.

| Batch | Work | Finding groups |
|---|---|---:|
| 1 | Enforce core rules and preserve pending decisions | 5 |
| 2 | Correct mandatory Event effects and reject illegal plans | 7 |
| 3 | Give Event choices to the correct human | 12 |
| 4 | Complete ordinary action choices, quantities and information | 19 |
| 5 | Complete Interlude and Winter decisions | 5 |
| 6 | Add optional setup and shared-player modes | 2 |

Start with Battle loss tiers, repeated Seize/Entreat Regions, strict Supply
response validation, expansion Arverni transfer rejection and the mandatory
single-seat Belgae setup correction. These have clear sources and narrow
reproducers. Event limits and mandatory effects follow before larger human
grant routing changes. For every repair, first preserve the desired rule in
a regression, then verify both interfaces, invalid-input rollback and any
affected save/replay path. Run relevant seeded scenario/edition comparisons
when mechanics change; investigate drift before changing a balance baseline.

## Finding register

All entries below are open. High means a substantial rule/ownership/effect
error; medium is a material choice, information or validation gap; low is an
optional feature omission. Detailed source quotations, exact locations,
interface distinctions, probes and repair recommendations are in the linked
JSON inventory and archived partition reports.

### General Special Ability timing

| ID | Priority | Batch | Finding |
|---|---|---:|---|
| TIMING-SA-DURING | medium | 4 | General during-Command Special Ability timing remains restricted |

### Human Commands and Special Abilities (non-March/non-Battle internals), both rulesets

| ID | Priority | Batch | Finding |
|---|---|---:|---|
| CMD-REPEATED-REGION | high | 1 | Human plans may Seize and Entreat repeatedly in the same Region |
| CMD-DEVASTATE-LOSSES | medium | 4 | Devastate omits each human owner’s casualty choice |
| CMD-RAMPAGE-COUNT | medium | 4 | Rampage forces two Warbands instead of the actor’s chosen quantity |
| CMD-SCOUT-ALLOCATION | medium | 4 | Scout cannot allocate one Auxilia across factions or choose Warband visibility |
| CMD-SEIZE-TRIBES | medium | 4 | Seize only offers all-or-none dispersal for a Region |
| CMD-INTIMIDATE-TRIBE | medium | 4 | Intimidate removes a default Allied Tribe rather than a chosen Tribe |
| CMD-BUILD-ORDER | medium | 4 | Build reorders all Regions by operation type |

### March and Battle, including Retreat, Ambush, Besiege, Rampage victims, live Elite and Diviciacus participation

| ID | Priority | Batch | Finding |
|---|---|---:|---|
| BATTLE-LOSS-TIERS | high | 1 | Human Battle casualty choices can violate mandatory loss priority tiers |
| BATTLE-LOSS-IDENTITY | medium | 4 | Ordinary Battle casualties cannot select visibility or physical Allied Tribe |
| BATTLE-RETREAT-CHOICES | medium | 4 | Retreat forces all Hidden defenders and Leader to stay and omits removal-only Retreat |
| BATTLE-BESIEGE-CHOICE | medium | 4 | Besiege uses automatic target priority instead of Roman choice |
| BATTLE-RAMPAGE-VICTIM | medium | 4 | Rampage target cannot choose affected pieces or per-piece removal versus Retreat |
| MARCH-DROPOFF | medium | 4 | Ordinary March cannot author transit dropoffs |
| MARCH-HIDE-IN-PLACE | medium | 4 | March requires movement and cannot only hide at a selected origin |

### All numeric base Events 1–72, both sides and explicit original/second-edition profiles, plus optional O38; ongoing10/13/59 human decisions

| ID | Priority | Batch | Finding |
|---|---|---:|---|
| BE-01 | high | 3 | Several Event-granted Marches and German guidance still use automatic plans |
| BE-02 | high | 3 | Fixed Event Battle resolvers suppress human Region or defender selections |
| BE-03 | high | 3 | Gallic beneficiaries and command order are hardcoded; Remi Influence gives pieces to the wrong faction |
| BE-04 | high | 3 | Named factions never receive optional Event-effect decisions |
| BE-05 | high | 3 | Drought substitutes casualty priorities for every faction’s own selection |
| BE-06 | medium | 4 | Event contracts cannot express smaller quantities or removal-only choices |
| BE-07 | medium | 4 | Several direct Event removals cannot select physical visibility or exact Allied Tribe |
| BE-08 | medium | 4 | Generated CLI Event schema cannot express several legal handler inputs |
| BE-09 | high | 3 | Human Capability activation/Region choices use unconditional NPC priorities |
| BE-10 | medium | 3 | Gallic Shouts does not present its private two-card peek |
| BE-11 | high | 2 | Event plan validators accept selections outside printed quantity and target limits |
| BE-12 | high | 2 | German Allegiances cannot replace Warbands for a Gallic executor |

### Ariovistus A-prefix Events, both API sides including single-text aliases; human choices, free grants and capabilities

| ID | Priority | Batch | Finding |
|---|---|---:|---|
| EXP-01 | high | 3 | Vosegus/Sabis choose human Battles and the optional second Battle with NPC policy |
| EXP-02 | high | 3 | A19 shaded uses German NPC movement policy for human play and skips other executors |
| EXP-03 | high | 3 | A67 omits the beneficiary and March choices and forces German human NPC Battle policy |
| EXP-04 | high | 3 | A29 Raid and A69 Ambush targets are auto-derived for humans |
| EXP-05 | high | 3 | A20/A58 Roman may-grants are forced or omitted depending on executor |
| EXP-06 | high | 2 | A20/A58 Seize grants run forbidden enemy Rally rolls |
| EXP-07 | high | 2 | A5 eviction forces the first Home Region and leaves non-Roman structures in Cisalpina |
| EXP-08 | medium | 4 | Three explicit up-to effects have no human quantity choice |
| EXP-09 | high | 2 | Typed human Event plans bypass printed geographic, beneficiary and quantity limits |
| EXP-10 | high | 2 | A22 shaded Capability never permits the added Intimidating Warband |
| EXP-11 | medium | 4 | A36 and other removal effects replace human physical-piece selections with fixed priorities |
| EXP-12 | medium | 2 | Remove-all expansion Events leave Scouted Warbands behind |

### winter_setup

| ID | Priority | Batch | Finding |
|---|---|---:|---|
| WS-F01 | high | 5 | Interlude force reductions and Cisalpina relocations bypass human owners |
| WS-F02 | high | 5 | Roman Interlude expedition and marker-preservation choices are unreachable in human sessions |
| WS-F03 | medium | 5 | Pax first-Harvest Legion placement is automatically concentrated in one Region |
| WS-F04 | medium | 1 | Human Belgae starts The Great Revolt with the wrong Leader |
| WS-F05 | medium | 5 | Quarters cannot select which visibility cohort relocates |
| WS-F06 | medium | 5 | Resource-transfer choices are limited to one early outgoing CLI gift and omit legal Winter/incoming windows |
| WS-F07 | medium | 1 | Ariovistus accepts Resource transfers to the game-run Arverni |
| WS-F08 | low | 6 | Three printed setup options have no selection or implementation |
| WS-F09 | medium | 6 | Shared player ownership is absent, so Spare Factions choices and consequences cannot be represented |

### shared human frontends and durable decision transport

| ID | Priority | Batch | Finding |
|---|---|---:|---|
| FE-01 | medium | 4 | Board inspection after SA-first Build shows the pre-SA board at the following March menu |
| FE-02 | medium | 1 | Malformed Supply replacement escapes durable validation and changes the pending request under the same decision ID |

## Important boundaries and examples

- **Timing:** Before/after ordering and the repaired same-Region Vercingetorix
  Rally boundary work in their reviewed paths. General during-March/Battle
  timing is still rejected. The new witness has Caesar March Provincia →
  Sequani → Mandubii and Build a Fort while passing through Sequani; Build is
  illegal both before and after because no Roman piece remains there.
- **Casualties:** Ordinary Battle offers pieces from both mandatory priority
  tiers, so a human can lose an Ally while a Warband remains. Retreat has the
  reverse tier defect. Exact visibility and Ally identity are separate gaps.
- **Events:** A20/A58 Seize triggers Rally rolls expressly forbidden by those
  cards. A22 shaded never allows the added Intimidating Warband. A5 can leave
  non-Roman structures in Cisalpina. Several remove-all effects omit Scouted
  Warbands. These are mandatory-effect errors, not optional menu polish.
- **Ownership:** A19's selections belong to the Event executor; A58's “may”
  actions belong to Romans. Other-executor A58 was proven to do nothing, but
  that particular probe used the executor's seat and does not separately
  prove Roman-seat durable prompting. The code gate establishes the omission.
  Base 68 shaded gives pieces to the executor even when another faction owns
  Remi. Drought and Devastate omit affected humans' casualty decisions.
- **Seasonal play:** Interlude automatically makes substantial reductions,
  relocation and expedition choices. First Pax Harvest concentrates the three
  Legions automatically. A sole human Belgae starts Great Revolt with the
  Successor instead of the required Ambiorix.
- **Known limits:** WS-F06 partly reconfirms documented transfer omissions;
  WS-F09 is the documented absence of shared player/faction ownership.
  WS-F08 covers optional Sudden Frost, Even Initiative and short Great Revolt
  setup, not failure of the standard deck. These are included in the 50.

## Remaining uncertainty

Q-TRADE-NP-REGION and Q-ELITE-NP-PIECES remain the two separate non-player
source questions in the existing ledger. No new rule choice is requested.
Thirty-four inventory rows remain explicitly not verified, including scarce
Available-piece placement order on selected Events, some ongoing expansion
interactions, advance Harassment promises and late Retreat Control changes.
Routing support alone is not substantive proof of all those decisions.

An adjacent mechanics concern deserves a focused check at the start of the
next repair: Ambush against a Fort/Citadel currently appears to retain normal
loss rolls without Caesar's exception. This audit did not execute that case
and does not count it among the 50. Resolve it using authoritative §§4.3.3/
4.5.3 and the source hierarchy; a misleading flowchart branch or existing
test is not a reason to ask the owner to invent a ruling.

## Reproduction and identity

Extract the evidence archive outside the checkout, install the repository's
test dependencies, and use its Python interpreter:

```sh
python /path/to/extracted/rerun_probes.py --repo /path/to/fs-bot --out /tmp/fs-human-audit-rerun
```

The output directory must not already exist. Run against the audited commit;
these are defect witnesses and may intentionally fail after corrections.
Use `PYTHONPATH=/path/to/fs-bot` to run any individual archived probe. No
credentials are needed for the probes. Full pytest evidence is in the JUnit
file; all engine/protected-file hashes are in `source-manifest.json`.

- Audited commit: `7e72fe7eda33c58b2f83457c39edf5b295a04f77`.
- Engine Python: 379 files, SHA-256 `c24adb23c9018071ed948e295a96fc4b17649e35fecabd985e77dedbfa32fcc5`.
- All 47 supplied reference files and `rules_consts.py` unchanged.
- Balance baseline unchanged: `207a129589d2bb17bec17319e70de7c8cf44d1572dc6aaca73cd0b39a9b5b8d3`.
- Evidence archive: 310,652 bytes; SHA-256 `82558ebb5bc9a3d695a85eaf146180ca7584f433e17dcadc3e2e0851b7c9290e`.

Only documentation and archived audit evidence are committed by this pass.
The live status/roadmap supersede earlier statements that the inventory was
still pending. Historical repair reports retain their original scope and
measurements. Passing CI on this documentation commit does not close these
findings.
