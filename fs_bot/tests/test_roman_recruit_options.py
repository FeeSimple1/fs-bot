"""§§3.2.1/8.8.4 retain one Recruit option per Region, including NP plans."""

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import count_pieces, get_available, place_piece
from fs_bot.bots.roman_bot import node_r_recruit
from fs_bot.cards.capabilities import activate_capability
from fs_bot.cards.card_effects import _ally_tribe, execute_event
from fs_bot.engine.execute import _execute_recruit, execute_decision
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity


def board(scenario=rc.SCENARIO_GREAT_REVOLT, *, regions=None, forced=False):
    state = build_initial_state(scenario, seed=17)
    state['resources'][rc.ROMANS] = 20
    state['non_player_factions'] = set(rc.FACTIONS)
    state['_command_with_sa'] = False
    if regions is not None:
        state['_command_region_scope'] = set(regions)
    if forced:
        state['_planning_forced_command'] = 'Recruit'
    return state


def execute_plan(state, action):
    result = _execute_recruit(state, rc.ROMANS, action)
    assert result['executed'], result
    assert not result['errors'], result
    assert check_structural_integrity(state) == []
    return result


@pytest.mark.parametrize('scenario', rc.BASE_SCENARIOS + rc.ARIOVISTUS_SCENARIOS)
def test_np_allies_then_auxilia_priorities_do_not_reuse_recruit_regions(scenario):
    state = board(scenario, regions=[rc.PROVINCIA, rc.SEQUANI])
    for region in (rc.PROVINCIA, rc.SEQUANI):
        place_piece(state, region, rc.ROMANS, rc.FORT)
    refresh_all_control(state)
    before = encode(state)
    state['decision_agent'] = lambda *_: pytest.fail('planning requested live input')
    action = node_r_recruit(state)
    del state['decision_agent']
    assert encode(state) == before  # Including the live RNG and Resource pool.
    assert action['command'] == 'Recruit'
    assert action['sa'] == 'No SA'
    plan = action['details']['recruit_plan']
    assert len(plan) == 2 and {entry['region'] for entry in plan} == {rc.PROVINCIA, rc.SEQUANI}
    assert all(entry['action'] == 'place_ally' for entry in plan)
    assert action['details']['potential_allies'] == 2
    assert action['details']['potential_auxilia'] == 0
    execute_plan(state, action)
    assert all(count_pieces(state, region, rc.ROMANS, rc.ALLY) == 1
               for region in (rc.PROVINCIA, rc.SEQUANI))
    assert all(count_pieces(state, region, rc.ROMANS, rc.AUXILIA) == 0
               for region in (rc.PROVINCIA, rc.SEQUANI))


def test_np_recruit_threshold_does_not_count_auxilia_after_its_own_ally():
    state = board(regions=[rc.NERVII])
    place_piece(state, rc.NERVII, rc.ROMANS, rc.FORT)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    assert _ally_tribe(state, rc.TRIBE_EBURONES, rc.ROMANS)
    activate_capability(state, 55, rc.EVENT_UNSHADED)
    # The old forecast counted one new Ally plus five Auxilia in this same
    # Region. The legal priority is the Ally alone, below either NP threshold.
    before = encode(state)
    assert node_r_recruit(state)['command'] != 'Recruit'
    assert encode(state) == before


@pytest.mark.parametrize('available,expected_auxilia', [(1, 1), (3, 3)])
def test_a5_ally_bonus_is_forecast_before_later_region_uses_shared_pool(available, expected_auxilia):
    state = board(rc.SCENARIO_ARIOVISTUS,
                  regions=[rc.CISALPINA, rc.PROVINCIA], forced=True)
    execute_event(state, 'A5')
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    assert _ally_tribe(state, rc.TRIBE_HELVII, rc.ROMANS)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA,
                get_available(state, rc.ROMANS, rc.AUXILIA) - available)
    refresh_all_control(state)
    action = node_r_recruit(state)
    assert action['command'] == 'Recruit'
    assert action['details']['potential_allies'] == 1
    assert action['details']['potential_auxilia'] == expected_auxilia
    plan = action['details']['recruit_plan']
    assert plan[0] == {'region': rc.CISALPINA, 'action': 'place_ally', 'tribe': rc.TRIBE_NORI}
    assert len(plan) == (1 if available == 1 else 2)
    execute_plan(state, action)
    assert count_pieces(state, rc.CISALPINA, rc.ROMANS, rc.AUXILIA) == 4
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == available - 1
    assert get_available(state, rc.ROMANS, rc.AUXILIA) == 0


@pytest.mark.parametrize('scenario,card,amount', [
    (rc.SCENARIO_GREAT_REVOLT, 5, 2),
    (rc.SCENARIO_ARIOVISTUS, 'A5', 1),
])
def test_scoped_forced_recruit_forecasts_gallia_without_ordinary_auxilia_base(scenario, card, amount):
    state = board(scenario, regions=[rc.CISALPINA], forced=True)
    execute_event(state, card)
    if card == 'A5':
        # Prevent an Allied-Tribe option without creating a Roman Auxilia base.
        assert _ally_tribe(state, rc.TRIBE_NORI, rc.AEDUI)
    state['resources'][rc.ROMANS] = 0
    action = node_r_recruit(state)
    assert action['command'] == 'Recruit'
    assert action['details']['potential_auxilia'] == amount
    assert action['details']['recruit_plan'] == [
        {'region': rc.CISALPINA, 'action': 'place_auxilia'}]
    execute_plan(state, action)
    assert count_pieces(state, rc.CISALPINA, rc.ROMANS, rc.AUXILIA) == 3 + amount
    assert state['resources'][rc.ROMANS] == 0


def test_separate_build_ally_can_enable_recruit_auxilia_in_same_region():
    state = board(regions=[rc.SEQUANI])
    state.pop('_command_with_sa')
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    refresh_all_control(state)
    action = {'command': 'Recruit', 'sa': 'Build', 'details': {
        'build_plan': {'forts': [], 'subdue': [], 'allies': [
            {'region': rc.SEQUANI, 'tribe': rc.TRIBE_SEQUANI}]},
        'recruit_plan': [{'region': rc.SEQUANI, 'action': 'place_auxilia'}],
    }}
    result = execute_decision(state, rc.ROMANS, {'bot_action': action})
    assert result['executed'] and not result.get('errors'), result
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.ALLY) == 1
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 2
    assert state['resources'][rc.ROMANS] == 18
    assert check_structural_integrity(state) == []
