"""Event selections remain valid when timing removes their chosen counters."""
import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece, PieceError
from fs_bot.cards.card_effects import _ally_tribe, execute_event
from fs_bot.engine.action_windows import scope, COHORTS
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state


def _timing(region, kind=rc.WARBAND, **fields):
    operation = {'action': 'remove', 'region': region,
                 'piece_type': kind, 'count': 1, **fields}
    if kind == rc.WARBAND:
        operation['piece_state'] = rc.HIDDEN
    return [{'kind': 'voluntary_removal', 'response': {'operations': [operation]}}]


def _a37():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=37)
    state['executing_faction'] = rc.AEDUI
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 4)
    return state


def _play(state, card, params, shaded=False):
    state['event_params'] = params
    with scope(state, actor=state['executing_faction'], force=True):
        execute_event(state, card, shaded)


@pytest.mark.parametrize('selected', [False, True])
def test_a37_removal_distinguishes_selected_group_from_resident(selected):
    state = _a37()
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 3)
    fields = {'cohort': 'event.A37.moves.0'} if selected else {}
    params = {'target_region': rc.SEQUANI, 'moves': [{
        'from_region': rc.CARNUTES, 'to_region': rc.SEQUANI,
        'piece_type': rc.WARBAND, 'piece_state': rc.HIDDEN, 'count': 2,
        'timing_actions': _timing(rc.CARNUTES, **fields)}]}
    _play(state, 'A37', params)
    assert count_pieces(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == (1 if selected else 2)
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == int(selected)
    assert COHORTS not in state and validate_state(state) == []


def test_a37_rejects_original_overcount_before_any_timing_or_placement():
    state = _a37()
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND)
    params = {'target_region': rc.SEQUANI, 'ally_placements': [
        {'tribe': rc.TRIBE_SEQUANI, 'faction': rc.AEDUI}], 'moves': [{
        'from_region': rc.CARNUTES, 'to_region': rc.SEQUANI,
        'piece_type': rc.WARBAND, 'piece_state': rc.HIDDEN, 'count': 2}]}
    state['event_params'] = params
    before = encode(state)
    with pytest.raises(PieceError, match='original pieces'):
        _play(state, 'A37', params)
    assert encode(state) == before


def test_a37_completed_arrival_can_be_removed_before_the_next_group():
    state = _a37()
    for region in (rc.CARNUTES, rc.MANDUBII):
        place_piece(state, region, rc.AEDUI, rc.WARBAND)
    params = {'target_region': rc.SEQUANI, 'moves': [
        {'from_region': rc.CARNUTES, 'to_region': rc.SEQUANI,
         'piece_type': rc.WARBAND, 'piece_state': rc.HIDDEN},
        {'from_region': rc.MANDUBII, 'to_region': rc.SEQUANI,
         'piece_type': rc.WARBAND, 'piece_state': rc.HIDDEN,
         'timing_actions': _timing(rc.SEQUANI)}]}
    _play(state, 'A37', params)
    assert count_pieces(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == 1
    assert validate_state(state) == []


def test_shaded31_skips_initially_legal_targets_removed_at_an_earlier_window():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=31)
    state['executing_faction'] = rc.AEDUI
    _ally_tribe(state, rc.TRIBE_AEDUI, rc.AEDUI)
    _ally_tribe(state, rc.TRIBE_SEQUANI, rc.AEDUI)
    actions = _timing(rc.AEDUI_REGION, rc.ALLY, tribe=rc.TRIBE_AEDUI)
    actions += _timing(rc.SEQUANI, rc.ALLY, tribe=rc.TRIBE_SEQUANI)
    params = {'aedui_ally_region': rc.AEDUI_REGION,
              'third_ally_faction': rc.AEDUI, 'third_ally_region': rc.SEQUANI,
              'stage_timing_actions': {'31.aedui_ally': actions}}
    _play(state, 31, params, True)
    assert state['tribes'][rc.TRIBE_AEDUI]['allied_faction'] is None
    assert state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] is None
    assert validate_state(state) == []


def test_shaded31_does_not_accept_an_originally_absent_explicit_target():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=31)
    state['executing_faction'] = rc.AEDUI
    with pytest.raises(PieceError):
        _play(state, 31, {'aedui_ally_region': rc.AEDUI_REGION}, True)
