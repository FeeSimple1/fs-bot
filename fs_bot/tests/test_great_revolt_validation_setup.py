"""Validation human-policy seats receive the mandatory Great Revolt Leader."""

import random

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import get_leader_in_region
from fs_bot.cli import app
from fs_bot.state.serialize import encode
from fs_bot.state.setup import setup_scenario


class SetupObserved(Exception):
    """Stop a validation caller before any game actions are executed."""


@pytest.mark.parametrize("seat,leader", [
    (None, rc.SUCCESSOR), (rc.BELGAE, rc.AMBIORIX), (rc.ARVERNI, rc.SUCCESSOR),
])
def test_heuristic_policy_seat_informs_setup(monkeypatch, seat, leader):
    from fs_bot.tools import heuristic_selfplay
    observed = []

    def inspect(state):
        observed.append(state)
        raise SetupObserved

    monkeypatch.setattr(heuristic_selfplay, "start_game", inspect)
    with pytest.raises(SetupObserved):
        heuristic_selfplay.play_game(rc.SCENARIO_GREAT_REVOLT, 1, seat,
                                    None if seat is None else lambda *args: None)
    state = observed[0]
    assert get_leader_in_region(state, rc.SUGAMBRI, rc.BELGAE) == leader
    assert (rc.BELGAE in state["non_player_factions"]) == (seat != rc.BELGAE)
    if seat is None:
        default = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=1)
        default["non_player_factions"] = set(app.get_assignable_factions(state["scenario"]))
        assert encode(state) == encode(default)


@pytest.mark.parametrize("seed", [1, 3, 13])
def test_fuzz_seats_inform_setup_without_changing_policy_rng(monkeypatch, seed):
    from fs_bot.tools import player_fuzz
    scenario = rc.SCENARIO_GREAT_REVOLT
    expected_rng = random.Random(f"player_fuzz|{scenario}|{seed}")
    expected_seats = player_fuzz._pick_seats(
        sorted(app.get_assignable_factions(scenario)), expected_rng)
    observed = []

    def capture_setup(*args, **kwargs):
        state = setup_scenario(*args, **kwargs)
        observed.append(state)
        return state

    def inspect(seats, rng):
        assert seats == expected_seats
        assert rng.getstate() == expected_rng.getstate()
        raise SetupObserved

    monkeypatch.setattr(player_fuzz, "setup_scenario", capture_setup)
    monkeypatch.setattr(player_fuzz, "make_random_reactive", inspect)
    with pytest.raises(SetupObserved):
        player_fuzz.play_game(scenario, seed)
    state = observed[0]
    expected = rc.AMBIORIX if expected_seats == [rc.BELGAE] else rc.SUCCESSOR
    assert get_leader_in_region(state, rc.SUGAMBRI, rc.BELGAE) == expected
    assert state["non_player_factions"] == (
        set(app.get_assignable_factions(scenario)) - set(expected_seats))
