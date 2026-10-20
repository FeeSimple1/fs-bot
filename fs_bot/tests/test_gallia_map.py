"""Actual Card 5/A5 markers govern geography and Roman Commands."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.state.state_schema import build_initial_state
from fs_bot.state.setup import setup_scenario
from fs_bot.state.serialize import save_game, load_game
from fs_bot.board.pieces import place_piece, count_pieces
from fs_bot.cards.card_effects import execute_event
from fs_bot.commands.march import march_group, march_cost, MarchError
from fs_bot.commands.rally import recruit_in_region, rally_in_region
from fs_bot.commands.common import CommandError
from fs_bot.engine.execute import _execute_march_moves, _execute_march
from fs_bot.engine.free_actions import rally_event_scope
from fs_bot.map.map_data import (
    get_map_capabilities, get_playable_regions_for_state,
    get_adjacent_for_state, is_region_playable,
)


def gallia(scenario=rc.SCENARIO_GREAT_REVOLT):
    state = build_initial_state(scenario, seed=4)
    execute_event(state, 'A5' if scenario in rc.ARIOVISTUS_SCENARIOS else 5)
    assert rc.MARKER_GALLIA_TOGATA not in state['capabilities']
    return state


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
def test_actual_gallia_marker_enables_free_roman_march_out_and_paid_return(scenario):
    state = gallia(scenario)
    state['resources'][rc.ROMANS] = 0
    result = _execute_march_moves(state, rc.ROMANS, [{
        'origin': rc.CISALPINA, 'path': [rc.SEQUANI], 'group': {rc.AUXILIA: 1}}])
    assert result['executed'] and result['total_cost'] == 0
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 1
    state['resources'][rc.ROMANS] = 2
    result = _execute_march_moves(state, rc.ROMANS, [{
        'origin': rc.SEQUANI, 'path': [rc.CISALPINA], 'group': {rc.AUXILIA: 1}}])
    assert result['executed'] and result['total_cost'] == 2
    assert state['resources'][rc.ROMANS] == 0
    assert count_pieces(state, rc.CISALPINA, rc.ROMANS, rc.AUXILIA) == 3


def test_roman_bot_plans_zero_resource_gallia_origin():
    from fs_bot.bots.roman_bot import node_r_march
    state = gallia()
    state['resources'][rc.ROMANS] = 0
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.ALLY)
    action = node_r_march(state)
    assert action['command'] == 'March'
    assert rc.CISALPINA in action['details']['origins']
    result = _execute_march(state, rc.ROMANS, action)
    assert result['executed'] and result['total_cost'] == 0


@pytest.mark.parametrize('scenario,amount', [
    (rc.SCENARIO_GREAT_REVOLT, 2), (rc.SCENARIO_ARIOVISTUS, 2)])
def test_actual_gallia_recruit_uses_scenario_specific_card_text(scenario, amount):
    state = gallia(scenario)
    if scenario in rc.ARIOVISTUS_SCENARIOS:
        place_piece(state, rc.CISALPINA, rc.ROMANS, rc.FORT)
    state['resources'][rc.ROMANS] = 0
    result = recruit_in_region(state, rc.CISALPINA, 'place_auxilia')
    assert result['pieces_placed'] == {rc.AUXILIA: amount}
    assert result['cost'] == 0


def test_base_gallia_recruit_is_fixed_two_even_with_leader_and_fort():
    state = gallia()
    place_piece(state, rc.CISALPINA, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, rc.CISALPINA, rc.ROMANS, rc.FORT)
    assert recruit_in_region(state, rc.CISALPINA, 'place_auxilia')['pieces_placed'] == {rc.AUXILIA: 2}


def test_a5_recruit_bonus_does_not_waive_normal_recruitment_base():
    state = gallia(rc.SCENARIO_ARIOVISTUS)
    before = deepcopy(state['spaces'])
    with pytest.raises(CommandError, match='Leader, Ally, or Fort'):
        recruit_in_region(state, rc.CISALPINA, 'place_auxilia')
    assert state['spaces'] == before


@pytest.mark.parametrize('legacy_marker', [False, True])
def test_a5_recruit_bonus_survives_actual_interlude_and_save(tmp_path, legacy_marker):
    from fs_bot.engine.interlude import run_interlude
    from fs_bot.map.map_data import get_gallia_togata_card
    from fs_bot.engine.execute import _execute_event
    from fs_bot.board.pieces import find_leader, move_piece
    state = setup_scenario(rc.SCENARIO_GALLIC_WAR, seed=3)
    assert _execute_event(state, rc.ROMANS, {'details': {
        'card_id': 'A5', 'text_preference': rc.EVENT_UNSHADED}}, human=True)['executed']
    if legacy_marker:
        state['markers'][rc.CISALPINA][rc.MARKER_GALLIA_TOGATA] = True
    run_interlude(state, britannia_decision=False)
    assert state['scenario'] == rc.SCENARIO_PAX_GALLICA
    place_piece(state, rc.CISALPINA, rc.ROMANS, rc.FORT)
    move_piece(state, find_leader(state, rc.ROMANS), rc.CISALPINA,
               rc.ROMANS, rc.LEADER)
    path = tmp_path / 'second-half.json'
    save_game(state, path)
    state, _, _ = load_game(path, validate=True)
    assert get_gallia_togata_card(state) == 'A5'
    # Leader + Fort + lingering A5 bonus: three, not base Card 5's fixed two.
    assert recruit_in_region(state, rc.CISALPINA, 'place_auxilia')['pieces_placed'] == {rc.AUXILIA: 3}


@pytest.mark.parametrize('active', [False, True])
def test_ariovistus_alps_stop_removed_only_by_actual_a5(active):
    state = gallia(rc.SCENARIO_ARIOVISTUS) if active else build_initial_state(rc.SCENARIO_ARIOVISTUS)
    if not active:
        place_piece(state, rc.CISALPINA, rc.ROMANS, rc.AUXILIA)
    assert march_cost(state, rc.CISALPINA, rc.ROMANS) == (0 if active else 2)
    result = march_group(state, rc.ROMANS, rc.CISALPINA,
                         [rc.SEQUANI, rc.AEDUI_REGION], {rc.AUXILIA: 1})
    assert result['final_region'] == (rc.AEDUI_REGION if active else rc.SEQUANI)


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
@pytest.mark.parametrize('faction', [rc.AEDUI, rc.GERMANS])
def test_gallia_blocks_nonroman_march_and_as_if_control_rally(scenario, faction):
    state = gallia(scenario)
    place_piece(state, rc.SEQUANI, faction, rc.WARBAND)
    before = deepcopy(state['spaces'])
    with pytest.raises(MarchError):
        march_group(state, faction, rc.SEQUANI, [rc.CISALPINA], {rc.WARBAND: 1})
    with rally_event_scope(state, faction, as_if_control=True, regions={rc.CISALPINA}):
        with pytest.raises(CommandError):
            rally_in_region(state, rc.CISALPINA, faction, 'place_warbands', free=True)
    assert state['spaces'] == before
    assert rc.CISALPINA not in get_adjacent_for_state(state, rc.SEQUANI, faction)


def test_ariovistus_without_marker_keeps_nonroman_cisalpina_playable():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS)
    place_piece(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND)
    assert is_region_playable(state, rc.CISALPINA, rc.AEDUI)
    assert march_group(state, rc.AEDUI, rc.SEQUANI, [rc.CISALPINA],
                       {rc.WARBAND: 1})['final_region'] == rc.CISALPINA


@pytest.mark.parametrize('legacy_capability', [False, True])
def test_old_saved_gallia_marker_remains_visible_and_usable(tmp_path, legacy_capability):
    from fs_bot.cli.display import format_region_table
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=3)
    execute_event(state, 5)
    if legacy_capability:
        state['markers'][rc.CISALPINA].pop(rc.MARKER_GALLIA_TOGATA)
        state['capabilities'][rc.MARKER_GALLIA_TOGATA] = True
    path = tmp_path / 'old-save.json'
    save_game(state, path)
    state, _, _ = load_game(path, validate=True)
    before = deepcopy(state['capabilities'])
    assert rc.MARKER_GALLIA_TOGATA in get_map_capabilities(state)
    assert rc.CISALPINA in get_playable_regions_for_state(state, rc.ROMANS)
    assert rc.CISALPINA in format_region_table(state)
    assert march_cost(state, rc.CISALPINA, rc.ROMANS) == 0
    assert state['capabilities'] == before


def test_no_marker_does_not_open_base_cisalpina():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT)
    assert not is_region_playable(state, rc.CISALPINA, rc.ROMANS)
    assert rc.CISALPINA not in get_adjacent_for_state(state, rc.SEQUANI, rc.ROMANS)
