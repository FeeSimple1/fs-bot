"""A8.7.4's combined Rally/Settle remains legal inside A66's grant."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, get_available, place_piece
from fs_bot.cards.card_effects import _ally_tribe, execute_card_A66
from fs_bot.cards.winter_uprising_resolution import resolve
from fs_bot.engine import execute as ex
from fs_bot.engine.game_engine import get_sop_factions
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state


def settlement_only_position():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=14)
    state['non_player_factions'] = set(get_sop_factions(state))
    state['resources'][rc.GERMANS] = 20
    place_piece(state, rc.TREVERI, rc.GERMANS, rc.LEADER,
                leader_name=rc.ARIOVISTUS_LEADER)
    place_piece(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, 3)
    place_piece(state, rc.PROVINCIA, rc.GERMANS, rc.WARBAND,
                get_available(state, rc.GERMANS, rc.WARBAND))
    for tribe in sorted(state['tribes']):
        if not get_available(state, rc.GERMANS, rc.ALLY):
            break
        _ally_tribe(state, tribe, rc.GERMANS)
    assert get_available(state, rc.GERMANS, rc.ALLY) == 0
    assert validate_state(state) == []
    return state


def test_real_a66_keeps_settlement_only_german_rally_and_its_zero_cost():
    state = settlement_only_position()
    state['executing_faction'] = rc.GERMANS
    state['event_params'] = {'region': rc.UBII}
    execute_card_A66(state)
    state.pop('executing_faction')
    state.pop('event_params')
    resources = state['resources'][rc.GERMANS]
    result = resolve(state)
    assert result[0]['allies'] == result[0]['warbands'] == 0
    grant = result[1]
    assert grant['command'] == rc.CMD_RALLY
    assert grant['placements'] == [] and grant['errors'] == []
    assert grant['sa_execution']['executed']
    assert count_pieces(state, rc.TREVERI, rc.GERMANS, rc.SETTLEMENT) == 1
    assert state['resources'][rc.GERMANS] == resources
    assert validate_state(state) == []


def test_true_scoped_flowchart_exhaustion_remains_a_legal_no_command():
    state = settlement_only_position()
    # Every mobile German and the only legal Settlement destination are
    # outside this scope. The published Rally -> Raid -> Pass path exhausts.
    result = ex._resolve_free_command(state, rc.GERMANS,
        allowed_regions={rc.SUGAMBRI}, with_sa=True, allow_decline=False)
    assert result['declined_no_effect'] and not result['executed']
    assert result['command'] is None
    assert count_pieces(state, rc.TREVERI, rc.GERMANS, rc.SETTLEMENT) == 0


@pytest.mark.parametrize('invalid', ['outside', 'wrong_faction', 'no_sa', 'ungranted_sa', 'missing_sa_region'])
def test_scope_filter_does_not_accept_unrelated_or_ungranted_empty_rally(invalid):
    state = settlement_only_position()
    planning = ex._free_command_planning_state(state, rc.GERMANS,
        {rc.TREVERI}, with_sa=True)
    from fs_bot.bots.german_bot import node_g_rally
    action = node_g_rally(planning)
    assert action['details']['rally_plan']['settlements_before']
    assert not action['details']['rally_plan']['allies']
    assert not action['details']['rally_plan']['warbands']
    allowed, faction = {rc.TREVERI}, rc.GERMANS
    if invalid == 'outside':
        allowed = {rc.SUGAMBRI}
    elif invalid == 'wrong_faction':
        faction = rc.BELGAE
    elif invalid == 'no_sa':
        action['sa'] = 'None'
    elif invalid == 'ungranted_sa':
        planning['_command_with_sa'] = False
    else:
        action['sa_regions'] = []
    before, original = encode(planning), deepcopy(action)
    assert ex._constrain_bot_action(action, allowed, state=planning, faction=faction) is None
    assert action == original and encode(planning) == before
