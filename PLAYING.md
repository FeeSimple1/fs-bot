# Playing Falling Sky against the bots

This engine supports GMT's **Falling Sky:
The Gallic Revolt Against Caesar** (2nd Edition) and the
**Ariovistus** expansion, with non-player bots for every faction.
You pick any seat (or several); the bots play the rest using the
published non-player flowcharts. See [current status](docs/current-status.md)
for verified fixes, test coverage, and unresolved source conflicts. The
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
Ambush and Besiege resolve within their accompanying Battle.

When an Event grants an action, its menu lets you plan the permitted action,
request the bot default, or decline where the card allows. Region and piece
limits still apply. Paid grants, such as Winter Campaign and Frumentum,
use their own action and Resource budgets.

Before your decisions, the display shows the current and upcoming card
texts and changes since your previous decision. Type **`b`** or **`board`**
at a menu or yes/no prompt to inspect the full board, including piece
states, Tribes, markers, available forces, and active capabilities.

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
[current status](docs/current-status.md) identifies the remaining source
conflicts and supersedes older completion claims.

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
