"""A City Razed by Sacking remains permanently Dispersed (Card 23 Tip)."""
import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece
from fs_bot.commands.seize import calculate_forage, get_dispersible_tribes
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.winter import spring_phase
from fs_bot.state.serialize import encode
from fs_bot.tests.test_colony_consumers import board, clean, play, seize


def razed(scenario):
    state = board(scenario)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA, 4)
    play(state, 23, rc.ROMANS, {'target_city': rc.CITY_ALESIA})
    assert state['tribes'][rc.TRIBE_MANDUBII]['status'] == rc.MARKER_RAZED
    return state


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
def test_razed_city_is_not_offered_or_counted_for_forage(scenario):
    state = razed(scenario)
    assert rc.TRIBE_MANDUBII not in get_dispersible_tribes(state, rc.MANDUBII)
    assert calculate_forage(state, rc.MANDUBII, []) == 4  # Senones and Lingones
    result = execute_decision(state, rc.ROMANS, seize(rc.MANDUBII, []))
    assert result['executed'] and result['forage_resources_total'] == 4
    assert state['tribes'][rc.TRIBE_MANDUBII]['status'] == rc.MARKER_RAZED
    clean(state)


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
def test_authored_redispersal_rejects_atomically_and_spring_preserves_razed(scenario):
    state = razed(scenario)
    before = encode(state)
    result = execute_decision(state, rc.ROMANS, seize(rc.MANDUBII, [rc.TRIBE_MANDUBII]))
    assert not result['executed'] and result['errors'] and result['rolled_back'], result
    assert encode(state) == before
    for _ in range(2):
        spring_phase(state)
        assert state['tribes'][rc.TRIBE_MANDUBII]['status'] == rc.MARKER_RAZED
        clean(state)


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
def test_seizing_another_tribe_preserves_the_razed_city(scenario):
    state = razed(scenario)
    state['decision_agent'] = lambda _s, _f, req: (
        {'decline': True} if req['kind'] == 'free_action' else None)
    result = execute_decision(state, rc.ROMANS, seize(rc.MANDUBII, [rc.TRIBE_SENONES]))
    assert result['executed'] and not result['errors'], result
    assert result['forage_resources_total'] == 8  # 6 Senones, 2 Lingones, 0 Razed
    spring_phase(state)
    assert state['tribes'][rc.TRIBE_SENONES]['status'] == rc.DISPERSED_GATHERING
    spring_phase(state)
    assert state['tribes'][rc.TRIBE_SENONES]['status'] is None
    assert state['tribes'][rc.TRIBE_MANDUBII]['status'] == rc.MARKER_RAZED
    clean(state)
