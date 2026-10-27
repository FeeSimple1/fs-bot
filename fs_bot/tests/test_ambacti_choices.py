"""Card 16/§5.1: exact post-roll choices and bounded legal placement."""

from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, get_available, place_piece
from fs_bot.cards.ambacti import execute, removal_request, validate_response
from fs_bot.cards.param_schema import card_param_schema, generate_params, kind_values
from fs_bot.state.state_schema import build_initial_state
from fs_bot.tools.seat_session import fingerprint


def position(seed=5, scenario=rc.SCENARIO_PAX_GALLICA):
    state = build_initial_state(scenario, seed=seed)
    state['executing_faction'] = rc.BELGAE
    state['non_player_factions'] = set()
    return state


def removal(region=rc.SEQUANI, count=1, visibility=rc.HIDDEN):
    return {'region': region, 'piece_state': visibility, 'count': count}


@pytest.mark.parametrize('scenario', [rc.SCENARIO_PAX_GALLICA, rc.SCENARIO_ARIOVISTUS])
@pytest.mark.parametrize('leader,expected', [(rc.CAESAR, 6), (rc.SUCCESSOR, 4)])
def test_unshaded_uses_named_caesar_and_only_available_pool(scenario, leader, expected):
    state = position(scenario=scenario)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=leader)
    state['event_params'] = {'target_region': rc.SEQUANI}
    execute(state)
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == expected
    remaining = get_available(state, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, remaining - 2)
    execute(state)
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == expected + 2
    assert get_available(state, rc.ROMANS, rc.AUXILIA) == 0


def test_unshaded_accepts_fort_and_schema_offers_only_roman_regions():
    state = position()
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.FORT)
    place_piece(state, rc.PROVINCIA, rc.BELGAE, rc.WARBAND)
    schema = card_param_schema(16, state['scenario'])
    assert set(schema) == {'target_region'}
    assert kind_values(state, 'region', schema['target_region']) == [rc.SEQUANI]
    state['event_params'] = {'target_region': rc.SEQUANI}
    execute(state)
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 4


def test_schema_generator_handles_no_eligible_placement_region():
    state = position()
    assert generate_params(state, 16, deepcopy(state['rng']), include_p=1) == {}


@pytest.mark.parametrize('response', [
    {'use_default': 1},
    {'use_default': 1.0},
    {'removal_choice': 'max', 'removals': [removal(count=3)]},
    {'removal_choice': 'three', 'removals': [removal(count=2)]},
    {'removal_choice': 'three', 'removals': [removal(count=4)]},
    {'removal_choice': 'three', 'removals': [removal(count=True)]},
    {'removal_choice': 'three', 'removals': [removal(count=3.0)]},
    {'removal_choice': 'three', 'removals': [removal(count=-1)]},
    {'removal_choice': 'three', 'removals': [removal(count=3, visibility=None)]},
    {'removal_choice': 'three', 'removals': [removal(count=3, visibility=rc.REVEALED)]},
    {'removal_choice': 'three', 'removals': [removal(rc.PROVINCIA, 3)]},
    {'removal_choice': 'three', 'removals': [removal(count=2), removal(count=2)]},
    {'removal_choice': 'three', 'removals': [dict(removal(count=3), faction=rc.AEDUI)]},
])
def test_invalid_choice_is_atomic_including_roll(response):
    state = position()
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 3)
    state.setdefault('event_modifiers', {})['card_16_die_roll'] = 2
    before = fingerprint(state)
    state['decision_agent'] = lambda *args: response
    with pytest.raises(ValueError):
        execute(state, shaded=True)
    assert fingerprint({key: value for key, value in state.items()
                        if key != 'decision_agent'}) == before


def test_live_roll_precedes_human_selection_and_overrides_legacy_params():
    state = position()
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 3)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 3, piece_state=rc.REVEALED)
    state['event_params'] = {'removal_choice': 'three', 'auxilia_removal_regions': [(rc.SEQUANI, 3)]}
    def agent(board, faction, request):
        assert request['roll'] == board['event_modifiers']['card_16_die_roll'] == 5
        assert faction == rc.BELGAE
        assert request['removal_counts'] == {'roll': 5, 'three': 3}
        return {'removal_choice': 'roll', 'removals': [
            removal(rc.PROVINCIA, 3, rc.REVEALED), removal(count=2)]}
    state['decision_agent'] = agent
    execute(state, shaded=True)
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 1


def test_partial_shaded_execution_requires_all_remaining_auxilia():
    state = position()
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 1, piece_state=rc.REVEALED)
    request = removal_request(state, 5)
    assert request['removal_counts'] == {'roll': 1, 'three': 1}
    response = {'removal_choice': 'roll', 'removals': [removal(visibility=rc.REVEALED)]}
    before = fingerprint(state)
    assert validate_response(state, request, response) == response
    assert fingerprint(state) == before
    state['decision_agent'] = lambda *args: response
    execute(state, shaded=True)
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 0


def test_zero_auxilia_still_rolls_and_permits_only_empty_removals():
    state = position()
    rng = deepcopy(state['rng'])
    expected = rng.randint(rc.DIE_MIN, rc.DIE_MAX)
    state['decision_agent'] = lambda *args: {'removal_choice': 'three', 'removals': []}
    result = execute(state, shaded=True)
    assert result['roll'] == expected
    assert state['rng'].getstate() == rng.getstate()


def test_direct_legacy_pairs_preserve_count_and_region_priorities():
    state = position(seed=2)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 3)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 3)
    state['event_params'] = {'removal_choice': 'three',
                             'auxilia_removal_regions': [(rc.SEQUANI, 2)]}
    execute(state, shaded=True)
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 3


def test_bad_legacy_region_list_rejected_without_spending_roll():
    state = position()
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 3)
    state['event_params'] = {'auxilia_removal_regions': [rc.SEQUANI]}
    before = fingerprint(state)
    with pytest.raises(ValueError, match='pairs'):
        execute(state, shaded=True)
    assert fingerprint(state) == before
