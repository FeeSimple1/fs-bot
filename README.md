# Falling Sky bot engine

A Python engine for **Falling Sky: The Gallic Revolt Against Caesar** and
**Ariovistus**, with interactive human play, published non-player flowcharts,
assistant-controlled seats, and reproducible automated games.

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

## Documentation

| Need | Start here |
|---|---|
| Play in the terminal | [Playing guide](PLAYING.md) |
| Play with an AI assistant | [Assistant guide](CHATGPT_README.md) |
| Integrate a human or software agent | [Agent interface](AGENT_INTERFACE.md) |
| Review fixes and remaining limitations | [Current engineering status](docs/current-status.md) |
| Inspect outcomes and reproducible evidence | [Provisional-ruling validation](docs/reviews/provisional-rulings-2026-10-24.md), [earlier follow-up report](docs/reviews/followup-repairs-2026-10-24.md) |
| Review adopted provisional rulings | [Six project rulings](docs/provisional-rulings.md), [question ledger](QUESTIONS.md#current-open-source-questions) |
| Develop and validate changes | [Developer instructions](CLAUDE.md), [maintenance roadmap](BUILD_PLAN.md), [self-play workflow](SELFPLAY_PLAYBOOK.md) |
| Install or check a release | [Release guide](RELEASES.md), [change history](CHANGELOG.md) |
| Browse all project documentation | [Documentation index](docs/README.md) |

## Current validation

The [provisional-ruling validation report](docs/reviews/provisional-rulings-2026-10-24.md)
records **4,481 passing tests**, **200 audited bot games**, **320 mixed-seat
executions with replay**, and **40 strict-census executions** on the adopted
implementation. All completed without defect findings; mixed-seat and census
reports matched across hash seeds. The 100-game balance check passed without
changing its baseline. The report gives exact source identities and scope.

All [six adopted project rulings](docs/provisional-rulings.md) remain subject
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
the supplied rules. The six expressly adopted provisional rulings govern
their listed source gaps until corrected. The [self-play workflow](SELFPLAY_PLAYBOOK.md) documents
batch, census, determinism, and balance checks.
