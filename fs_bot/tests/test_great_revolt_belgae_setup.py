"""Great Revolt's sole human Belgae seat gets its mandatory named Leader."""

import io
from types import SimpleNamespace

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import get_leader_in_region
from fs_bot.cli import app
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine.game_engine import start_game
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import validate_state
from fs_bot.tools import llm_seat
from fs_bot.tools.seat_session import SeatSession, board_copy


@pytest.mark.parametrize("humans,leader", [
    ((), rc.SUCCESSOR),
    ((rc.BELGAE,), rc.AMBIORIX),
    ((rc.ARVERNI,), rc.SUCCESSOR),
    ((rc.ARVERNI, rc.BELGAE), rc.SUCCESSOR),
    ((rc.ROMANS, rc.AEDUI), rc.SUCCESSOR),
    ((rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE), rc.SUCCESSOR),
])
def test_setup_applies_only_the_known_single_belgae_player(humans, leader):
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=1,
                           human_factions=humans)
    default = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=1)
    assert get_leader_in_region(state, rc.SUGAMBRI, rc.BELGAE) == leader
    assert state["available"] == default["available"]
    assert state["deck"] == default["deck"]
    assert state["rng"].getstate() == default["rng"].getstate()
    assert validate_state(state) == []


@pytest.mark.parametrize("scenario", [
    rc.SCENARIO_PAX_GALLICA, rc.SCENARIO_RECONQUEST,
    rc.SCENARIO_ARIOVISTUS, rc.SCENARIO_GALLIC_WAR,
])
def test_single_belgae_seat_does_not_change_other_scenarios(scenario):
    default = setup_scenario(scenario, seed=1)
    human = setup_scenario(scenario, seed=1, human_factions=(rc.BELGAE,))
    assert encode(human) == encode(default)


@pytest.fixture
def pause_cli_at_first_card(monkeypatch):
    def pause(*args, **kwargs):
        raise EOFError
    monkeypatch.setattr(app, "play_card", pause)


@pytest.mark.parametrize("bots,leader", [
    ((rc.ROMANS, rc.ARVERNI, rc.AEDUI), rc.AMBIORIX),
    ((rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE), rc.SUCCESSOR),
    ((rc.ROMANS, rc.ARVERNI), rc.SUCCESSOR),
    ((rc.ARVERNI, rc.BELGAE), rc.SUCCESSOR),
])
def test_cli_new_setup_and_replay_preserve_leader(
        tmp_path, pause_cli_at_first_card, bots, leader):
    saved, replayed = tmp_path / "new.json", tmp_path / "replay.json"
    assert app.main([
        "--scenario", rc.SCENARIO_GREAT_REVOLT, "--seed", "1",
        "--bots", ",".join(bots), "--save", str(saved),
    ], stdin=io.StringIO(), stdout=io.StringIO()) == 0
    state, meta, _ = load_game(saved)
    assert get_leader_in_region(state, rc.SUGAMBRI, rc.BELGAE) == leader
    assert meta["setup_human_factions"] == [
        faction for faction, mode in meta["initial_faction_modes"].items()
        if mode == "human"
    ]
    assert app.main(["--replay", str(saved), "--save", str(replayed)],
                    stdin=io.StringIO(), stdout=io.StringIO()) == 0
    after, _, _ = load_game(replayed)
    assert encode(board_copy(after)) == encode(board_copy(state))


def test_cli_wizard_single_belgae_setup(tmp_path, pause_cli_at_first_card):
    saved = tmp_path / "wizard.json"
    assert app.main([
        "--scenario", rc.SCENARIO_GREAT_REVOLT, "--seed", "1",
        "--save", str(saved),
    ], stdin=io.StringIO("2\n2\n2\n1\n"), stdout=io.StringIO()) == 0
    state, _, _ = load_game(saved)
    assert get_leader_in_region(state, rc.SUGAMBRI, rc.BELGAE) == rc.AMBIORIX


@pytest.mark.parametrize("mode", ["--load", "--replay"])
def test_historical_cli_successor_is_not_retroactively_flipped(
        tmp_path, pause_cli_at_first_card, mode):
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=1)
    modes = {f: "human" if f == rc.BELGAE else "bot"
             for f in app.get_assignable_factions(state["scenario"])}
    state["non_player_factions"] = {f for f, m in modes.items() if m == "bot"}
    start_game(state)
    old, saved = tmp_path / "old.json", tmp_path / "saved.json"
    save_game(state, old, meta={"scenario": state["scenario"], "seed": 1,
                               "faction_modes": modes})
    assert app.main([mode, str(old), "--save", str(saved)],
                    stdin=io.StringIO(), stdout=io.StringIO()) == 0
    after, meta, _ = load_game(saved)
    assert get_leader_in_region(after, rc.SUGAMBRI, rc.BELGAE) == rc.SUCCESSOR
    assert "setup_human_factions" not in meta
    assert encode(board_copy(after)) == encode(board_copy(state))


@pytest.mark.parametrize("historical", [False, True])
def test_durable_init_resume_and_replay_preserve_the_setup_origin(
        tmp_path, capsys, pause_cli_at_first_card, historical):
    directory = tmp_path / "live"
    args = SimpleNamespace(dir=str(directory), scenario=rc.SCENARIO_GREAT_REVOLT,
                           seed=1, seat=rc.BELGAE,
                           output_dir=str(tmp_path / "replay"))
    if historical:
        directory.mkdir()
        state = setup_scenario(args.scenario, seed=args.seed)
        state["non_player_factions"] = {rc.ROMANS, rc.ARVERNI, rc.AEDUI}
        start_game(state)
        meta = {"scenario": args.scenario, "seed": args.seed, "seat": args.seat}
        SeatSession(state, meta, [], HumanTurnDisplay(io.StringIO()))
        save_game(state, directory / "save.json", meta=meta, log=[])
    else:
        llm_seat.cmd_init(args)
    expected = rc.SUCCESSOR if historical else rc.AMBIORIX
    initial, meta, _ = load_game(directory / "save.json")
    assert get_leader_in_region(initial, rc.SUGAMBRI, rc.BELGAE) == expected
    assert meta.get("setup_human_factions") == (None if historical else [rc.BELGAE])
    origin = decode(meta["assistant_session"]["origin"])
    assert get_leader_in_region(origin, rc.SUGAMBRI, rc.BELGAE) == expected
    # The same saved setup can also seed the CLI's reconstruction.
    cli_replay = tmp_path / "cli-replay.json"
    assert app.main(["--replay", str(directory / "save.json"),
                     "--save", str(cli_replay)],
                    stdin=io.StringIO(), stdout=io.StringIO()) == 0
    cli_state, _, _ = load_game(cli_replay)
    assert encode(cli_state) == encode(initial)
    assert llm_seat.cmd_play(args) == 0
    paused, meta, _ = load_game(directory / "save.json")
    pending = meta["assistant_session"]["pending"]
    assert decode(pending["request"])["kind"] == "turn"
    assert llm_seat.cmd_play(args) == 0
    resumed, meta, _ = load_game(directory / "save.json")
    assert encode(resumed) == encode(paused)
    assert meta["assistant_session"]["pending"] == pending
    assert llm_seat.cmd_replay(args) == 0
    replayed, replay_meta, _ = load_game(tmp_path / "replay" / "save.json")
    assert encode(replayed) == encode(paused)
    assert replay_meta.get("setup_human_factions") == (
        None if historical else [rc.BELGAE])
    assert "Replay verified" in capsys.readouterr().out
