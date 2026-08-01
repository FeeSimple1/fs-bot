# Playing Falling Sky against the bots

This is a complete, rules-faithful engine for GMT's **Falling Sky:
The Gallic Revolt Against Caesar** (2nd Edition) and the
**Ariovistus** expansion, with non-player bots for every faction.
You pick any seat (or several); the bots play the rest using the
published non-player flowcharts.

## Requirements

Python 3.10 or newer. Nothing else — no packages to install, no
internet needed.

- **Windows**: install from https://www.python.org/downloads/ and
  tick **"Add python.exe to PATH"** during setup.
- macOS/Linux: `python3` is usually already present.

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

## How a turn works

Each Event card shows the initiative order. When it is your turn the
CLI walks you through menus: pick Command / Command + Special
Ability / Event / Pass (as eligibility allows), then the regions and
pieces involved. Every plan is validated by the rules engine — an
illegal choice is refused with the rule reason and you simply pick
again, so you can explore freely without breaking the game. You will
also be consulted for in-battle decisions on other factions' turns:
Retreats, loss order, Supply-Line and Trade agreements, harassment.

## The rules

The full rulebook transcriptions ship in `Reference Documents/`
(base chapters 1-8, Ariovistus A-chapters, card texts, non-player
flowcharts), with all published errata applied inline as
`[ERRATA ...]` notes. The engine implements the 2nd Edition rules,
every capability card, and the designer rulings collected on BGG —
see QUESTIONS.md for the complete decision ledger.

## Scenarios

| Scenario | Factions | Length |
|---|---|---|
| Pax Gallica? | Ro / Ar / Ae / Be | medium |
| The Great Revolt | Ro / Ar / Ae / Be | medium — the classic |
| Reconquest of Gaul | Ro / Ar / Ae / Be | short |
| Ariovistus | Ro / Ge / Ae / Be | medium (expansion) |
| The Gallic War | both sets | epic two-act (a German seat becomes the Arverni after the Interlude) |

Fair warning from playtesting: the Roman bot garrisons its origins,
consolidates its Legions when threatened, and subdue-farms whatever
the table ignores. Good luck.
