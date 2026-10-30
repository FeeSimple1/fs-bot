"""§§8.8.1 and 8.3.4: exact die bands and random equal March destinations."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece
from fs_bot.bots import roman_bot as roman
from fs_bot.state.state_schema import build_initial_state


def ally(state, region, faction):
    place_piece(state, region, faction, rc.ALLY)
    tribe = next(t for t in state['tribes'] if rc.TRIBE_TO_REGION[t] == region)
    state['tribes'][tribe]['allied_faction'] = faction


@pytest.mark.parametrize('die,expected', [(1, rc.ARVERNI), (2, rc.ARVERNI),
                                          (3, rc.BELGAE), (4, rc.BELGAE),
                                          (5, rc.ARVERNI), (6, rc.ARVERNI)])
def test_failed_german_tier_does_not_apply_player_preference_on_one_or_two(monkeypatch, die, expected):
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=7)
    state['non_player_factions'] = {rc.ROMANS, rc.ARVERNI, rc.AEDUI}
    for region in (rc.MANDUBII, rc.CARNUTES, rc.SEQUANI):
        ally(state, region, rc.ARVERNI)
    ally(state, rc.NERVII, rc.BELGAE)
    monkeypatch.setattr(roman, 'calculate_victory_margin', lambda *_: -10)
    monkeypatch.setattr(roman, 'roll_die', lambda _: die)
    result = roman._rank_march_destinations(state, state['scenario'])
    assert result[0][1] == expected


@pytest.mark.parametrize('scenario', [rc.SCENARIO_PAX_GALLICA, rc.SCENARIO_ARIOVISTUS])
@pytest.mark.parametrize('tier', [1, 2, 3, 4])
def test_every_tier_randomizes_only_complete_ties_and_replays(monkeypatch, scenario, tier):
    target = (rc.GERMANS if scenario in rc.BASE_SCENARIOS else rc.ARVERNI) if tier == 2 else rc.BELGAE
    monkeypatch.setattr(roman, 'calculate_victory_margin', lambda *_: 0 if tier == 1 else -10)
    monkeypatch.setattr(roman, 'roll_die', lambda _: {2: 1, 3: 3}.get(tier, 5))
    from fs_bot.commands import rally
    monkeypatch.setattr(rally, 'has_supply_line', lambda *_: False)
    first = set()
    for seed in range(8):
        state = build_initial_state(scenario, seed=seed)
        state['non_player_factions'] = set(rc.FACTIONS) - {target}
        for region in (rc.NERVII, rc.ATREBATES):
            ally(state, region, target)
        other = deepcopy(state)
        before = state['rng'].getstate()
        result = roman._rank_march_destinations(state, scenario)
        assert result == roman._rank_march_destinations(other, scenario)
        assert state['rng'].getstate() == other['rng'].getstate()
        assert state['rng'].getstate() != before
        assert set(result) == {(rc.NERVII, target), (rc.ATREBATES, target)}
        first.add(result[0][0])
    assert first == {rc.NERVII, rc.ATREBATES}


def test_random_tiebreak_cannot_override_fewer_battle_losses(monkeypatch):
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=0)
    state['non_player_factions'] = set(rc.FACTIONS)
    for region in (rc.NERVII, rc.ATREBATES):
        ally(state, region, rc.BELGAE)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 2)
    monkeypatch.setattr(roman, 'calculate_victory_margin', lambda *_: -10)
    monkeypatch.setattr(roman, 'roll_die', lambda _: 5)
    result = roman._rank_march_destinations(state, state['scenario'])
    assert result[0] == (rc.ATREBATES, rc.BELGAE)
