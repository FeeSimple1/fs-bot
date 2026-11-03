"""Original-cohort visibility and Diviciacus regressions from BE-03 matrix."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces_by_state, count_pieces
from fs_bot.cards.arduenna import march_request
from fs_bot.cards.capabilities import activate_capability
from fs_bot.engine.diviciacus import force_scope
from fs_bot.engine.free_actions import execute_free_action_plan, validate_free_action_response
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import encode


def plan(origin, count=None, piece=rc.WARBAND):
    result = {'command': rc.CMD_MARCH, 'regions': [origin], 'sa': 'No SA', 'sa_regions': [],
              'details': {'march_plan': {'origins': [origin], 'destinations': [rc.TREVERI],
                                        'routes': {origin: [rc.TREVERI]}}}}
    if count is not None:
        result['details']['march_plan']['groups'] = {origin: {piece: count}}
    return result


@pytest.mark.parametrize('card', [67, 'A67'])
@pytest.mark.parametrize('visibility', [rc.HIDDEN, rc.REVEALED, rc.SCOUTED])
def test_cooperation_elsewhere_cannot_attach_physical_owner_to_native_march(card, visibility):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=201)
    state['non_player_factions'] = {rc.AEDUI, rc.ROMANS}
    activate_capability(state, 38, rc.EVENT_UNSHADED)
    place_piece(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND)
    place_piece(state, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND, 2, piece_state=visibility)
    before = encode(state)
    action = plan(rc.SEQUANI)
    assert validate_free_action_response(state, rc.AEDUI, march_request(card), action) is None
    assert encode(state) == before
    result = execute_free_action_plan(state, rc.AEDUI, march_request(card), action)
    expected = rc.REVEALED if visibility == rc.SCOUTED else rc.HIDDEN
    assert result['executed'] and count_pieces_by_state(state, rc.TREVERI, rc.AEDUI, rc.WARBAND, expected) == 2
    assert count_pieces(state, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA) == 1
    assert '_diviciacus_force' not in state and '_action_window_cohorts' not in state
    assert validate_state(state) == []


@pytest.mark.parametrize('card', [67, 'A67'])
@pytest.mark.parametrize('actor,piece', [(rc.AEDUI, rc.WARBAND), (rc.BELGAE, rc.WARBAND),
                                      (rc.ROMANS, rc.AUXILIA)])
def test_mixed_visibility_merges_within_one_origin_cohort_after_hiding(card, actor, piece):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=12)
    for visibility, count in [(rc.HIDDEN, 1), (rc.REVEALED, 2), (rc.SCOUTED, 1)]:
        place_piece(state, rc.ATREBATES, actor, piece, count, piece_state=visibility)
    before = deepcopy(state['available'])
    result = execute_free_action_plan(state, actor, march_request(card), plan(rc.ATREBATES))
    assert result['executed']
    assert count_pieces_by_state(state, rc.TREVERI, actor, piece, rc.HIDDEN) == 3
    assert count_pieces_by_state(state, rc.TREVERI, actor, piece, rc.REVEALED) == 1
    assert count_pieces_by_state(state, rc.TREVERI, actor, piece, rc.SCOUTED) == 0
    assert state['available'] == before and '_action_window_cohorts' not in state
    assert validate_state(state) == []


def test_hiding_shared_force_keeps_physical_owners_and_scouted_members_separate():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=38)
    for owner, piece in [(rc.ROMANS, rc.AUXILIA), (rc.AEDUI, rc.WARBAND)]:
        place_piece(state, rc.ATREBATES, owner, piece, piece_state=rc.HIDDEN)
        place_piece(state, rc.ATREBATES, owner, piece, piece_state=rc.REVEALED)
    place_piece(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND, piece_state=rc.SCOUTED)
    before = deepcopy(state['available'])
    with force_scope(state, rc.ROMANS, [rc.ATREBATES]):
        result = execute_free_action_plan(state, rc.ROMANS, march_request(67), plan(rc.ATREBATES, 5, rc.AUXILIA))
    assert result['executed']
    assert count_pieces_by_state(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 2
    assert count_pieces_by_state(state, rc.TREVERI, rc.AEDUI, rc.WARBAND, rc.HIDDEN) == 2
    assert count_pieces_by_state(state, rc.TREVERI, rc.AEDUI, rc.WARBAND, rc.REVEALED) == 1
    assert state['available'] == before and validate_state(state) == []


def test_visibility_merging_does_not_merge_distinct_initial_groups():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=12)
    state['non_player_factions'] = {rc.BELGAE}
    place_piece(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 2, piece_state=rc.HIDDEN)
    place_piece(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 2, piece_state=rc.REVEALED)
    action = plan(rc.ATREBATES, 2)
    action['details']['march_plan']['extra_groups'] = [
        {'origin': rc.ATREBATES, 'route': [rc.NERVII], 'group': {rc.WARBAND: 2}}]
    result = execute_free_action_plan(state, rc.BELGAE, march_request(67), action)
    assert result['executed'] and len(result['marches']) == 2
    for region in (rc.NERVII, rc.TREVERI):
        assert count_pieces_by_state(state, region, rc.BELGAE, rc.WARBAND, rc.HIDDEN) == 2
    assert validate_state(state) == []
