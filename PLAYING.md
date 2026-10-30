# Playing Falling Sky against the bots

This engine supports GMT's **Falling Sky:
The Gallic Revolt Against Caesar** (2nd Edition) and the
**Ariovistus** expansion, with non-player bots for every faction.
You pick any seat (or several); the bots play the rest using the
published non-player flowcharts. See [current status](docs/current-status.md)
for verified fixes, test coverage, and provisional source interpretations. The
[documentation index](docs/README.md) also links assistant play and API guides.

## Requirements

Python 3.10 or newer. Nothing else — no packages to install, no
internet needed.

- **Windows**: install from https://www.python.org/downloads/ and
  tick **"Add python.exe to PATH"** during setup.
- macOS/Linux: `python3` is usually already present.

You can also install this checkout with `python -m pip install .` and use
`fs-bot --save autosave.json` outside the source directory. See
[RELEASES.md](RELEASES.md) for local distribution and compatibility checks.

## Starting a game

**Windows**: double-click **`play.bat`**.

**Any platform**, from a terminal in this folder:

    python -m fs_bot.cli.app --save autosave.json

A setup wizard asks for the scenario and, for each faction, Human or
Bot. Recommended first game: **The Great Revolt**, you as the
**Arverni** (Vercingetorix's grand revolt — the scenario the game is
named for).

`--save autosave.json` writes a snapshot after every card. Resume any
time with:

    python -m fs_bot.cli.app --load autosave.json --save autosave.json

Other options: `--scenario "Name"` and `--bots Romans,Aedui,Belgae`
skip the wizard; `--seed N` makes the deck deterministic; see
`python -m fs_bot.cli.app --help`.

Choose card versions when starting a game with
`--card-edition second-edition` or `--card-edition original`. This choice
governs the five optional revised cards (11, 30, 39, 44, and 54), including
their displayed text and effects. It does not change the expansion deck or
scenario rules. The default, `legacy`, preserves the previous behavior:
original versions in base scenarios and revised versions in Ariovistus.
Explicit editions remain unchanged through the Gallic War Interlude;
`legacy` continues to follow the current scenario. Older saves without a
choice use `legacy`. A loaded game cannot change editions.

To use the published optional Diviciacus Leader rule in an original
scenario, add `--diviciacus-option` when starting the game. It replaces
card 38 with O38; Diviciacus starts off-map and can be placed by that Event.
This is separate from the five-card edition choice. It does not change the
Gallic War Interlude's existing A38 replacement. The option cannot change
when loading or replaying a game.

## How a turn works

Each Event card shows the initiative order. When it is your turn the
CLI walks you through menus: pick Command / Command + Special
Ability / Event / Pass (as eligibility allows), then the regions and
pieces involved. With Command + Special Ability, the Command menu also
offers **Special Activity first, then Command**. You can instead choose
the Command first and add its Special Activity afterward. The interrupt
option allows Rally, Recruit, Raid, or Seize in some Regions, then the
Special Activity, then the rest of that Command in other Regions.
For base-game Arverni Rally, it also allows the Special Activity between
Vercingetorix's two options in the same Region.
Ambush and Besiege resolve within their accompanying Battle.

Recruit and Rally now ask how many Auxilia or Warbands to place. The
quantity menu includes zero where the rules allow it, and includes any
compulsory additions in the displayed total. Choosing zero still selects
and pays for the Region; use **Skip this Region** to omit it. Later choices
use the pieces and Resources left after your earlier placements.

With named Vercingetorix, Rally can place an Ally or Citadel and Warbands
in either order. Choose the first placement, then the second or **Finish
this Region**. The Region costs Resources only once. A Successor does not
have this ability. All three Gallic factions can choose a Citadel at a
City where they have an Ally. Enlist's free German Rally also offers its
legal quantities, including the base game's Warbands after placing an Ally.
When using Diviciacus cooperation, choose the physical Roman/Aedui pieces
before planning the next Region; this preserves the correct remaining pools.
In an interrupted Rally, choose the Special Activity after completing the
first option, then continue from the resulting position. The second option
must still be legal when reached; entering or removing Vercingetorix can
change that permission. You do not pay for the Region twice.

During your Sequence-of-Play Command or Event, the menus offer voluntary
removal of your own physical pieces and replacement of your Citadels with
Allies. These choices appear before planning quantities, so an empty
Available pool need not prevent reclaiming a piece for the next placement.
Choose **Finish voluntary removal** to confirm the selected removals, or
leave the position unchanged if none were selected.
Legions return to their track; the permanent Provincia Fort cannot be
removed. A Citadel replacement needs an Available Ally; without one, the
Citadel is simply removed. Lending pieces does not transfer ownership.
Where it matters, menus distinguish moving, already moved, borrowed, and
Event-selected counters from other pieces in the same Region.

With shaded River Commerce (Card 39), choose the one Region that will
Trade. The menu appears after Supply Line declarations and after any
preceding Command, so its income estimates use the actual position. It
includes every legal Region, even one yielding no Resources, and permits
declining Trade. The ordinary Command still takes effect if Trade is
declined or earns nothing. Use `board` or `b` at the choice as usual.

When a Roman bot needs your Supply Line permission for Recruit and its
preceding activity, it asks before making changes. A refusal makes it
reconsider the plan; accepted permissions hold for the Command or Event
you agreed to. You can still inspect the board at the prompt.

When an Event grants an action, its menu lets you plan the permitted action,
request the bot default, or decline where the card allows. Region and piece
limits still apply. Paid grants, such as Winter Campaign and Frumentum,
use their own action and Resource budgets.
Shaded Surus lets the Event executor direct the newly placed German Warbands
in a free March, Raid, or Battle; existing German residents stay outside that
selected group. Seize's successful Rally checks resolve their free Rally
choices immediately, before the next roll or Forage.

The Province offers its printed Auxilia or Resources choice, showing the
Available pool and Resource-cap limits. Ambacti asks for its removal choice
after showing the die roll, then lets you select the exact Auxilia by Region
and visibility. Its unshaded menu offers Regions containing Roman pieces;
only the named Caesar increases the placement from four to six.

Chieftains' Council lets the executor select a qualifying Region and at
least two participating player Factions there. Each participant acts in the
card's initiative order, sees the next two face-down cards, and may choose
a free Limited Command anywhere, become Eligible, or decline. The look
skips the already face-up upcoming card. Private prompts name their
recipient; people sharing one terminal must manage who can see that screen.

Winter Uprising records who took the card. After a normal Quarters Phase,
its human holder can activate it or keep it for a later Quarters Phase.
The Gallic War Interlude requires activation. The selected beneficiary
chooses the printed Allies and Warbands within one Region of the marker;
for Arverni, the holder chooses their placements. Menus show the full held
card and allow Warbands to be split among legal Regions. The following
Command is required when possible, with normal Special Activity ordering.

Spring prompts let you choose where an Available Successor returns. Every
legal destination is offered, including empty Home Regions with your printed
Rally or Recruit symbol. Placement is required; Diviciacus has no Successor.
Bots place Leaders with the most of their own pieces and break equal ties
using the game's seeded randomness.

In Pax Gallica, you can place Vercingetorix from the Spring box beginning
the first Spring, or leave him there for later. Placement opportunities
continue between completed operations inside Commands, Events, and Winter,
including other factions' actions. He may enter any playable Region without
using a turn or changing Eligibility. In the Gallic War, this begins in the
first Winter after the Interlude. Each opportunity lets you defer again;
it does not automatically place him. **Use bot placement priorities** is an
explicit placement choice. Planning menus ask for a specific Region instead.

Boii has dedicated menus for its beneficiary, Allied Tribes and troop
placements. The remaining allowance follows each choice across Regions.
Parley offers complete legal meetings, including either direction when the
named Leaders are adjacent. Wailing Women and Nervii appear in the active
capability list on either side, including in older saves that recorded their
unshaded effects only as internal modifiers.

Before your decisions, the display shows the current and upcoming card
texts and changes since your previous decision. Type **`b`** or **`board`**
at a menu or yes/no prompt to inspect the full board, including piece
states, Tribes, markers, available forces, and active capabilities.
Planning displays are labelled as previews; inspecting them does not alter
the live game. Seize planning reserves markers and estimates Forage, while
Rally checks and Harassment resolve during execution. Later decisions use
the actual changes, including intervening Leader entry.

Every plan is checked by the rules engine. A Command with no legal effect
leaves your turn pending so you can choose again; a partly legal plan
shows which portions would have no effect before you confirm it. You will
also be consulted for in-battle decisions on other factions' turns:
Retreats, loss order, Supply-Line and Trade agreements, and Harassment.
When Harassment causes a loss, you can choose an offered soft casualty or a
saving roll, then choose a hard casualty if the roll requires one. The menus
also distinguish piece visibility and specific Allied Tribes when relevant.
March subset and drop-off prompts let you choose the actual Hidden/Revealed
pieces from the selected group; pieces already in the destination remain
separate.

Suborn offers each legal physical owner, piece type, visibility and Allied
Tribe. Choices update the remaining Resources and pieces as you build the
plan; you can undo a choice or cancel. Convictolitavis can permit a second
Region, and unshaded Vergobret permits a fourth piece, including a second
Ally, in each Region.

When Diviciacus permits cooperation, the menus offer Regions in which to
request it. Planning shows the possible combined forces; the other human
Faction agrees or refuses when the action resolves. Commands and eligible
Special Activities have their own selections. Defense also offers an
explicit request. Roman Auxilia and Aedui Warbands keep their physical
owners, and the board identifies their temporary treatment separately.
When selecting a subset or placing pieces, prompts distinguish their
physical owners as well as visibility where relevant.

Roman Build planning permits both a Fort and the legal Ally action in one
Region. Scout planning updates the position after each move, prevents the
same counter moving twice, and offers the arriving Hidden Auxilia for
Reveal. Under shaded Vercingetorix's Elite, the Arverni choose the actual
Warbands treated as Legions; casualty choices distinguish those counters.
If Vercingetorix's arrival changes Roman Quarters Supply, the Romans can
revise their remaining Provincia moves and payments after completed adjacent
moves, without repeating those moves.

When saving is enabled, Ctrl-C also saves between decisions on the same
card. Completed faction actions stay completed. If interrupted while
resolving an action or Winter phase, that unfinished action or phase is
restored to its starting board and random-number state and retried on
resume. Gallic War saves retain both the current seats and the original
seats needed for replay after the Interlude.

## The rules

The full rulebook transcriptions ship in `Reference Documents/`
(base chapters 1-8, Ariovistus A-chapters, card texts, non-player
flowcharts), including transcribed errata marked as `[ERRATA ...]` notes.
The implementation follows these supplied references and the rulings
recorded in QUESTIONS.md. That file is a historical decision ledger;
[current status](docs/current-status.md) supersedes older completion claims.
The owner adopted [nine provisional rulings](docs/provisional-rulings.md),
all subject to possible later correction if an authoritative source is found:

- A30 has no special Belgic instruction; bots use their normal shaded Event procedure.
- For A28, non-player Aedui and Belgae lend only where the executor contributes
  its own participating pieces. Human consent remains your choice.
- Romans retain unused Frumentum funding, subject to the Resource cap.
- German-owned A63 activates at the Interlude, then remains German-owned and
  dormant in the base-game half.
- Ariovistus Harassment follows printed faction order, with Arverni last.
- Winter Harassment uses the last non-Winter card actually played, including
  a card on which everyone passed. The game-run faction remains last.
- Non-player Aedui roll once for Supply permission for a human Roman action,
  covering its Command, accompanying Special Ability and relevant Regions.
  Replanning the same decision does not grant a new roll.
- Ordinary Rally/Recruit placement prerequisites are checked before the
  bonus pieces arrive. Bonuses still apply where the normal troop quantity
  would be zero, and explicit printed exceptions remain.
- A20 casualties follow the required visibility order, then choose an
  original Region at equal odds for each otherwise tied Warband loss.

These are project interpretations, not official errata. The ruling register
explains each source gap and the fallback for older saves without usable
card history.

## Scenarios

| Scenario | Factions | Length |
|---|---|---|
| Pax Gallica? | Ro / Ar / Ae / Be | medium |
| The Great Revolt | Ro / Ar / Ae / Be | medium — the classic |
| Reconquest of Gaul | Ro / Ar / Ae / Be | short |
| Ariovistus | Ro / Ge / Ae / Be | medium (expansion) |
| The Gallic War | both sets | epic two-act (a German seat becomes the Arverni after the Interlude) |

For measured outcomes by scenario, see the [23 October validation
report](docs/reviews/outstanding-fixes-2026-10-23.md). Those seeded bot games
check the implementation; they do not predict results against a human player.

The owner's replacement Diviciacus card photograph resolves a separate
printed-label question: both O38 sides are Capabilities under §5.3. Bots
therefore decline either side in the final year; this does not restrict a
human's Event selection. See the [29 October rules report](docs/reviews/rulings-trade-2026-10-29.md)
for the evidence and the narrower remaining Capability-removal question.
