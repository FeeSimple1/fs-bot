"""A Card Reference A37: one chosen Region and direct, optional own moves."""
from copy import deepcopy
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import calculate_control, refresh_all_control
from fs_bot.board.pieces import (
    PieceError, count_pieces, count_pieces_by_state, get_leader_in_region, place_piece,
)
from fs_bot.cards.card_effects import execute_event
from fs_bot.cards.all_gaul_gathers import collect_params, derive_params, eligible_regions
from fs_bot.cards.event_conditions import np_event_available
from fs_bot.cli.human_plan import _collect_event_params
from fs_bot.cli.menus import set_board_hook
from fs_bot.engine.execute import _execute_event, execute_decision
from fs_bot.engine.moves import validate_player_action
from fs_bot.state.serialize import encode, save_game, load_game
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity


def _state(faction=rc.AEDUI, scenario=rc.SCENARIO_ARIOVISTUS):
    state = build_initial_state(scenario, seed=37)
    state['current_card'] = 'A37'
    state['executing_faction'] = faction
    state['non_player_factions'] = set(rc.FACTIONS) - {faction}
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 4)
    refresh_all_control(state)
    return state


def _move(faction=rc.AEDUI, **overrides):
    return {'from_region': rc.PICTONES, 'to_region': rc.SEQUANI,
            'piece_type': rc.AUXILIA if faction == rc.ROMANS else rc.WARBAND,
            'piece_state': rc.HIDDEN, 'count': 1, **overrides}


def _params(**overrides):
    return {'target_region': rc.SEQUANI, 'ally_placements': [
        {'tribe': rc.TRIBE_SEQUANI, 'faction': rc.AEDUI}], 'moves': [], **overrides}


def _action(params):
    return {'command': 'Event', 'sa': 'No SA', 'regions': [], 'sa_regions': [],
            'details': {'card_id': 'A37', 'text_preference': rc.EVENT_UNSHADED,
                        'event_params': params}}


@pytest.mark.parametrize('scenario', rc.ARIOVISTUS_SCENARIOS)
@pytest.mark.parametrize('faction,leader', [(rc.AEDUI, rc.DIVICIACUS), (rc.ROMANS, rc.CAESAR)])
def test_selected_region_and_nonadjacent_origins_allow_only_own_card_piece_types(scenario, faction, leader):
    state = _state(faction, scenario)
    kind = rc.AUXILIA if faction == rc.ROMANS else rc.WARBAND
    place_piece(state, rc.PICTONES, faction, kind, 2, piece_state=rc.REVEALED)
    place_piece(state, rc.VENETI, faction, kind, 1)
    place_piece(state, rc.PICTONES, faction, rc.LEADER, leader_name=leader)
    if faction == rc.ROMANS:
        place_piece(state, rc.PICTONES, rc.ROMANS, rc.LEGION, from_legions_track=True)
    # An older Ally in the first eligible Region must not divert movement.
    place_piece(state, rc.TREVERI, faction, rc.ALLY)
    state['tribes'][rc.TRIBE_TREVERI]['allied_faction'] = faction
    state['event_params'] = _params(moves=[
        _move(faction, count=2, piece_state=rc.REVEALED),
        _move(faction, from_region=rc.VENETI),
        _move(faction, piece_type=rc.LEADER, piece_state=None)])
    resources, rng = deepcopy(state['resources']), state['rng'].getstate()
    result = _execute_event(state, faction, _action(state['event_params']), human=True)
    assert result['executed'], result
    assert count_pieces_by_state(state, rc.SEQUANI, faction, kind, rc.REVEALED) == 2
    assert count_pieces_by_state(state, rc.SEQUANI, faction, kind, rc.HIDDEN) == 1
    assert get_leader_in_region(state, rc.SEQUANI, faction) == leader
    assert count_pieces(state, rc.TREVERI, faction, kind) == 0
    if faction == rc.ROMANS:
        assert count_pieces(state, rc.PICTONES, faction, rc.LEGION) == 1
    assert state['resources'] == resources and state['rng'].getstate() == rng
    assert 'card_A37_place_allies_move' not in state.get('event_modifiers', {})
    assert check_structural_integrity(state) == []


@pytest.mark.parametrize('visibility', [rc.HIDDEN, rc.REVEALED, rc.SCOUTED])
def test_direct_relocation_preserves_warband_orientation(visibility):
    state = _state()
    place_piece(state, rc.PICTONES, rc.AEDUI, rc.WARBAND, 2, piece_state=visibility)
    state['event_params'] = _params(moves=[_move(piece_state=visibility, count=2)])
    execute_event(state, 'A37')
    assert count_pieces_by_state(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND, visibility) == 2
    assert count_pieces(state, rc.PICTONES, rc.AEDUI, rc.WARBAND) == 0


def test_any_allies_can_have_different_owners_and_change_control_before_direct_move():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=37)
    state['executing_faction'] = rc.AEDUI
    place_piece(state, rc.SEQUANI, rc.GERMANS, rc.WARBAND)
    place_piece(state, rc.PICTONES, rc.AEDUI, rc.WARBAND, 3)
    refresh_all_control(state)
    state['event_params'] = _params(ally_placements=[
        {'tribe': rc.TRIBE_SEQUANI, 'faction': rc.ROMANS},
        {'tribe': rc.TRIBE_HELVETII, 'faction': rc.BELGAE}], moves=[_move(count=3)])
    execute_event(state, 'A37')
    assert state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] == rc.ROMANS
    assert state['tribes'][rc.TRIBE_HELVETII]['allied_faction'] == rc.BELGAE
    assert rc.SEQUANI not in eligible_regions(state)
    assert count_pieces(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == 3
    assert calculate_control(state, rc.SEQUANI) == rc.NO_CONTROL


def test_movement_can_be_declined_or_selected_without_placing_an_ally():
    state = _state()
    place_piece(state, rc.PICTONES, rc.AEDUI, rc.WARBAND)
    result = _execute_event(state, rc.AEDUI, _action(_params()), human=True)
    assert result['executed'] and result['free_actions'][0]['declined_no_effect']
    assert count_pieces(state, rc.PICTONES, rc.AEDUI, rc.WARBAND) == 1
    result = _execute_event(state, rc.AEDUI, _action(_params(
        ally_placements=[], moves=[_move()])), human=True)
    assert result['executed'] and result['free_actions'][0]['executed']
    assert count_pieces(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == 1


@pytest.mark.parametrize('bad', [
    {'target_region': rc.PICTONES},
    {'target_region': rc.UBII},
    {'target_region': rc.BRITANNIA},
    {'ally_placements': [{'tribe': rc.TRIBE_SEQUANI}, {'tribe': rc.TRIBE_TREVERI}]},
    {'ally_placements': [{'tribe': rc.TRIBE_SEQUANI}, {'tribe': rc.TRIBE_SEQUANI}]},
    {'moves': [_move(), _move(piece_type=rc.LEGION)]},
    {'moves': [_move(), _move(piece_type=rc.ALLY)]},
    {'moves': [_move(), _move(piece_type=rc.AUXILIA)]},
    {'moves': [_move(), {**_move(), 'faction': rc.BELGAE}]},
    {'moves': [_move(), _move(to_region=rc.TREVERI)]},
    {'moves': [_move(), _move(count=-1)]},
    {'moves': [_move(), _move(count=True)]},
    {'moves': [_move(), _move(count=0)]},
    {'moves': [_move(), _move(piece_state='unknown')]},
    {'moves': [_move(), _move()]},
    {'moves': 'not a list'},
    {'ally_placements': [None]},
])
def test_invalid_complete_selection_is_atomic_even_via_direct_event_dispatch(bad):
    state = _state()
    place_piece(state, rc.PICTONES, rc.AEDUI, rc.WARBAND)
    state['event_params'] = _params(**bad)
    before = encode(state)
    with pytest.raises((ValueError, PieceError)):
        execute_event(state, 'A37')
    assert encode(state) == before


def test_tribe_stacking_and_available_disc_limits_are_checked_before_mutation():
    state = _state(rc.ROMANS)
    place_piece(state, rc.MANDUBII, rc.GERMANS, rc.WARBAND, 2)
    refresh_all_control(state)
    state['event_params'] = {'target_region': rc.AEDUI_REGION,
        'ally_placements': [{'tribe': rc.TRIBE_AEDUI, 'faction': rc.ROMANS}]}
    before = encode(state)
    with pytest.raises(ValueError):
        execute_event(state, 'A37')
    assert encode(state) == before
    # One remaining Aedui Ally cannot satisfy two selected placements.
    place_piece(state, rc.VENETI, rc.AEDUI, rc.ALLY, 5)
    state['event_params'] = _params(ally_placements=[
        {'tribe': rc.TRIBE_SEQUANI, 'faction': rc.AEDUI},
        {'tribe': rc.TRIBE_HELVETII, 'faction': rc.AEDUI}])
    before = encode(state)
    with pytest.raises(ValueError):
        execute_event(state, 'A37')
    assert encode(state) == before


@pytest.mark.parametrize('block', ['no_control', 'no_available', 'occupied', 'dispersed'])
def test_np_aedui_declines_whole_event_when_no_legal_own_ally_can_be_placed(block):
    state = _state()
    if block == 'no_control':
        from fs_bot.board.pieces import remove_piece
        remove_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, count=4)
    elif block == 'no_available':
        place_piece(state, rc.VENETI, rc.AEDUI, rc.ALLY, 6)
    else:
        for tribe in (rc.TRIBE_TREVERI, rc.TRIBE_SEQUANI, rc.TRIBE_HELVETII):
            state['tribes'][tribe]['status'] = rc.MARKER_DISPERSED
            if block == 'occupied':
                state['tribes'][tribe]['status'] = None
                state['tribes'][tribe]['allied_faction'] = rc.BELGAE
                place_piece(state, rc.TRIBE_TO_REGION[tribe], rc.BELGAE, rc.ALLY)
    refresh_all_control(state)
    place_piece(state, rc.PICTONES, rc.AEDUI, rc.WARBAND, 4)
    state['non_player_factions'].add(rc.AEDUI)
    before = encode(state)
    assert np_event_available(state, 'A37', rc.AEDUI, False) is False
    assert encode(state) == before
    params = derive_params(deepcopy(state), rc.AEDUI, False)
    assert params is None


def test_shaded_scope_rejects_distant_allies_atomically():
    state = _state(rc.BELGAE)
    for tribe in (rc.TRIBE_SEQUANI, rc.TRIBE_PICTONES):
        place_piece(state, rc.TRIBE_TO_REGION[tribe], rc.AEDUI, rc.ALLY)
        state['tribes'][tribe]['allied_faction'] = rc.AEDUI
    state['event_params'] = {'removals': [
        {'tribe': rc.TRIBE_SEQUANI, 'faction': rc.AEDUI},
        {'tribe': rc.TRIBE_PICTONES, 'faction': rc.AEDUI}]}
    before = encode(state)
    with pytest.raises(ValueError):
        execute_event(state, 'A37', shaded=True)
    assert encode(state) == before
    state['event_params']['removals'].pop()
    execute_event(state, 'A37', shaded=True)
    assert count_pieces(state, rc.SEQUANI, rc.AEDUI, rc.ALLY) == 0
    assert count_pieces(state, rc.PICTONES, rc.AEDUI, rc.ALLY) == 1


@pytest.mark.parametrize('faction', [rc.BELGAE, rc.GERMANS])
def test_np_shaded_availability_requires_an_ally_in_the_actual_removal_scope(faction):
    state = _state(faction)
    place_piece(state, rc.PICTONES, rc.AEDUI, rc.ALLY)
    state['tribes'][rc.TRIBE_PICTONES]['allied_faction'] = rc.AEDUI
    assert np_event_available(state, 'A37', faction, True) is False
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.ALLY)
    state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] = rc.ROMANS
    assert np_event_available(state, 'A37', faction, True) is True


def test_shaded_cannot_remove_a_citadel_or_a_duplicate_ally():
    state = _state(rc.BELGAE)
    place_piece(state, rc.SEQUANI, rc.AEDUI, rc.CITADEL)
    state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] = rc.AEDUI
    state['event_params'] = {'removals': [{'tribe': rc.TRIBE_SEQUANI, 'faction': rc.AEDUI}]}
    before = encode(state)
    with pytest.raises(ValueError):
        execute_event(state, 'A37', shaded=True)
    assert encode(state) == before
    place_piece(state, rc.SEQUANI, rc.AEDUI, rc.ALLY)
    state['tribes'][rc.TRIBE_HELVETII]['allied_faction'] = rc.AEDUI
    state['event_params'] = {'removals': [{'tribe': rc.TRIBE_HELVETII, 'faction': rc.AEDUI}] * 2}
    before = encode(state)
    with pytest.raises(ValueError):
        execute_event(state, 'A37', shaded=True)
    assert encode(state) == before


def test_typed_choice_board_command_preview_save_and_replay(tmp_path):
    state = _state()
    place_piece(state, rc.PICTONES, rc.AEDUI, rc.WARBAND, 2, piece_state=rc.SCOUTED)
    output, board_calls = io.StringIO(), []
    set_board_hook(lambda: board_calls.append(True))
    before = encode(state)
    try:
        params = _collect_event_params(state, rc.AEDUI, 'A37', False, io.StringIO(
            f'board\n{rc.SEQUANI}\n{rc.TRIBE_SEQUANI}: {rc.ROMANS}\n'
            f'Finish placing Allies\n{rc.PICTONES}: 2 {rc.SCOUTED} {rc.WARBAND}\n2\n'), output)
    finally:
        set_board_hook(None)
    assert board_calls == [True]
    assert encode(state) == before
    assert params['moves'] == [_move(piece_state=rc.SCOUTED, count=2)]
    assert params['ally_placements'] == [{'tribe': rc.TRIBE_SEQUANI, 'faction': rc.ROMANS}]
    action = _action(params)
    ok, result = validate_player_action(state, rc.AEDUI, action)
    assert ok, result
    assert encode(state) == before
    save_game(state, tmp_path / 'a37.json', log=[{'faction': rc.AEDUI, 'player_action': action}])
    live_result = execute_decision(state, rc.AEDUI, {'player_action': action})
    replayed, _, log = load_game(tmp_path / 'a37.json')
    replay_result = execute_decision(replayed, rc.AEDUI, log[0])
    assert live_result == replay_result
    assert encode(state) == encode(replayed)


def test_closed_input_midplan_leaves_no_partial_placements_or_moves():
    state = _state()
    place_piece(state, rc.PICTONES, rc.AEDUI, rc.WARBAND)
    before = encode(state)
    with pytest.raises(EOFError):
        collect_params(state, rc.AEDUI, False, io.StringIO(
            f'{rc.SEQUANI}\n{rc.TRIBE_SEQUANI}: {rc.AEDUI}\nFinish placing Allies\n'), io.StringIO())
    assert encode(state) == before


@pytest.mark.parametrize('scenario', rc.BASE_SCENARIOS)
def test_a37_cannot_apply_ariovistus_event_text_in_a_base_scenario(scenario):
    state = _state(scenario=scenario)
    state['event_params'] = _params()
    before = encode(state)
    with pytest.raises(ValueError, match='Ariovistus'):
        execute_event(state, 'A37')
    assert encode(state) == before
