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

## Documentation

| Need | Start here |
|---|---|
| Play in the terminal | [Playing guide](PLAYING.md) |
| Play with an AI assistant | [Assistant guide](CHATGPT_README.md) |
| Integrate a human or software agent | [Agent interface](AGENT_INTERFACE.md) |
| Review fixes and remaining limitations | [Current engineering status](docs/current-status.md) |
| Inspect outcomes and reproducible evidence | [23 October validation report](docs/reviews/outstanding-fixes-2026-10-23.md) |
| Find source questions and prior decisions | [Question ledger](QUESTIONS.md#current-open-source-questions) |
| Develop and validate changes | [Developer instructions](CLAUDE.md), [maintenance roadmap](BUILD_PLAN.md), [self-play workflow](SELFPLAY_PLAYBOOK.md) |
| Browse all project documentation | [Documentation index](docs/README.md) |

## Verified checkpoint

The [23 October report](docs/reviews/outstanding-fixes-2026-10-23.md) records
the exact tested revision: **4,067 passing tests**, **1,000 completed bot
games** across all five scenarios, no crashes or nonlegal action diagnostics
in that batch, and matching cross-hash/replay results. All eight CI jobs
passed for its [publication commit](https://github.com/FeeSimple1/fs-bot/actions/runs/40036918602).
Those results belong to that checkpoint; they are not a claim that every
possible position or later revision has been verified.

Six source questions remain documented. Historical strategy studies use
older mechanics and have additional harness limitations; consult their
dated caveats before using their numbers as play advice.

## Development

Install the test dependency, then run the full suite:

```sh
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Read [CLAUDE.md](CLAUDE.md) before editing. `Reference Documents/**` and
`fs_bot/rules_consts.py` are protected, read-only sources. Project guides,
reports, and strategy notes describe the implementation; they do not replace
the supplied rules. The [self-play workflow](SELFPLAY_PLAYBOOK.md) documents
batch, census, determinism, and balance checks.
