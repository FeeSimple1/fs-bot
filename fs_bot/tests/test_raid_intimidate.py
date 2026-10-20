"""A3.4.3/A4.6.2: simultaneous Raid Intimidate uses the same Warbands."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import place_piece, count_pieces, count_pieces_by_state
from fs_bot.commands.raid import raid_in_region
from fs_bot.engine.execute import _execute_raid, _execute_decision, _execute_bot_command
from fs_bot.engine.raid_intimidate import validate_response, RAID_INTIMIDATE
from fs_bot.state.state_schema import build_initial_state


def position(*, hidden=2, successor=False, scenario=rc.SCENARIO_ARIOVISTUS):
    state = build_initial_state(scenario, seed=4)
    state['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE, rc.GERMANS}
    state['resources'][rc.GERMANS] = 0
    if scenario in rc.ARIOVISTUS_SCENARIOS:
        place_piece(state, rc.UBII, rc.GERMANS, rc.LEADER,
                    leader_name=rc.SUCCESSOR if successor else rc.ARIOVISTUS_LEADER)
    if hidden:
        place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, hidden)
    refresh_all_control(state)
    return state


def removal(faction=rc.ROMANS, piece=rc.AUXILIA, visibility=rc.HIDDEN):
    return {'target_faction': faction, 'target_piece': piece, 'target_state': visibility}


def action(*, sa='No SA'):
    return {'command': rc.CMD_RAID, 'regions': [rc.UBII], 'sa': sa,
            'sa_regions': [rc.UBII] if sa != 'No SA' else [],
            'details': {'raid_plan': [{'region': rc.UBII, 'target': None}] * 2}}


def signature(state):
    return deepcopy({k: v for k, v in state.items() if k not in ('rng', 'decision_agent')})


def test_actual_raiders_intimidate_without_another_hidden_flip():
    state = position()
    place_piece(state, rc.UBII, rc.ROMANS, rc.AUXILIA, 2)
    result = raid_in_region(state, rc.UBII, rc.GERMANS, [{'type': 'gain'}] * 2)
    assert result['warbands_flipped'] == 2
    assert result['raid_intimidate']['executed']
    assert count_pieces(state, rc.UBII, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces_by_state(state, rc.UBII, rc.GERMANS, rc.WARBAND, rc.REVEALED) == 2
    assert count_pieces_by_state(state, rc.UBII, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 0
    assert state['resources'][rc.GERMANS] == 2


def test_intrinsic_marker_only_does_not_need_a_special_ability():
    state = position()
    result = _execute_bot_command(state, rc.GERMANS, action(), with_sa=False)
    assert result['executed']
    assert rc.MARKER_INTIMIDATED in state['markers'][rc.UBII]
    assert result['raids'][0]['raid_intimidate']['intrinsic_raid']
    assert not result.get('sa_execution')


def test_human_can_decline_intrinsic_effect_without_cancelling_raid():
    state = position()
    seen = []
    def agent(board, faction, request):
        assert request['kind'] == RAID_INTIMIDATE and faction == rc.GERMANS
        seen.append(request)
        # Decision is presented after the Raid's changes are visible.
        assert board['resources'][rc.GERMANS] == 2
        assert count_pieces_by_state(board, rc.UBII, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 0
        return {'decline': True}
    state['decision_agent'] = agent
    result = _execute_raid(state, rc.GERMANS, action())
    assert len(seen) == 1 and seen[0]['raiders'] == 2
    assert result['raids'][0]['raid_intimidate']['declined']
    assert rc.MARKER_INTIMIDATED not in state['markers'].get(rc.UBII, {})
    assert state['resources'][rc.GERMANS] == 2


@pytest.mark.parametrize('response', [
    {'targets': [removal(), removal()]},
    {'targets': [removal(), removal(rc.AEDUI, rc.WARBAND)]},
    {'targets': [dict(removal(), region=rc.SEQUANI)]},
])
def test_invalid_reactive_choice_rolls_back_whole_raid_region(response):
    state = position(hidden=1)
    place_piece(state, rc.UBII, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.UBII, rc.AEDUI, rc.WARBAND)
    state['decision_agent'] = lambda *args: response
    before = signature(state)
    with pytest.raises(ValueError):
        raid_in_region(state, rc.UBII, rc.GERMANS, [{'type': 'gain'}])
    assert signature(state) == before


def test_pause_during_reactive_choice_rolls_back_and_preserves_agent():
    state = position()
    def paused(*args):
        raise EOFError
    state['decision_agent'] = paused
    before = signature(state)
    with pytest.raises(EOFError):
        raid_in_region(state, rc.UBII, rc.GERMANS, [{'type': 'gain'}] * 2)
    assert signature(state) == before
    assert state['decision_agent'] is paused


def test_successor_cannot_use_ariovistus_intrinsic_raid_effect():
    state = position(successor=True)
    state['decision_agent'] = lambda *args: pytest.fail('Successor must not be offered this choice')
    result = raid_in_region(state, rc.UBII, rc.GERMANS, [{'type': 'gain'}] * 2)
    assert 'raid_intimidate' not in result
    assert rc.MARKER_INTIMIDATED not in state['markers'].get(rc.UBII, {})


def test_base_german_raid_has_no_intrinsic_ariovistus_effect():
    state = position(scenario=rc.SCENARIO_PAX_GALLICA)
    place_piece(state, rc.UBII, rc.ROMANS, rc.AUXILIA)
    state['resources'][rc.ROMANS] = 2
    result = raid_in_region(state, rc.UBII, rc.GERMANS,
                            [{'type': 'steal', 'target': rc.ROMANS}], free=True)
    assert 'raid_intimidate' not in result
    assert count_pieces(state, rc.UBII, rc.ROMANS, rc.AUXILIA) == 1


def test_intrinsic_and_ordinary_intimidate_are_separate_applications():
    state = position(hidden=4)
    place_piece(state, rc.UBII, rc.ROMANS, rc.AUXILIA, 4)
    response = {'targets': [removal()] * 2}
    state['decision_agent'] = lambda *args: response
    declared = action(sa=rc.SA_INTIMIDATE)
    declared['details']['intimidate_plan'] = [dict(removal(), region=rc.UBII)] * 2
    state['non_player_factions'].remove(rc.GERMANS)
    result = _execute_decision(state, rc.GERMANS, {'player_action': declared})
    assert result['executed'] and not result.get('errors')
    assert result['sa_execution']['executed'] and not result['sa_execution']['errors']
    assert count_pieces(state, rc.UBII, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces_by_state(state, rc.UBII, rc.GERMANS, rc.WARBAND, rc.REVEALED) == 4


def test_free_only_np_raid_does_not_choose_normal_special_ability():
    from fs_bot.bots.german_bot import node_g_raid
    state = position()
    place_piece(state, rc.UBII, rc.ROMANS, rc.AUXILIA, 2)
    before = signature(state)
    planned = node_g_raid(state)
    assert planned['sa'] == 'No SA'
    assert signature(state) == before
    result = _execute_decision(state, rc.GERMANS, {'bot_action': planned})
    assert result['executed'] and not result.get('errors')
    assert count_pieces(state, rc.UBII, rc.ROMANS, rc.AUXILIA) == 0
    assert not result.get('sa_execution')


def test_np_raid_additional_sa_uses_remaining_hidden_warbands_once():
    from fs_bot.bots.german_bot import node_g_raid
    state = position(hidden=4)
    place_piece(state, rc.UBII, rc.ROMANS, rc.AUXILIA, 4)
    planned = node_g_raid(state)
    assert planned['sa'] == rc.SA_INTIMIDATE
    assert all(not p['free'] for p in planned['details']['intimidate_plan'])
    result = _execute_decision(state, rc.GERMANS, {'bot_action': planned})
    assert not result.get('errors') and not result['sa_execution']['errors']
    assert count_pieces(state, rc.UBII, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces_by_state(state, rc.UBII, rc.GERMANS, rc.WARBAND, rc.REVEALED) == 4


def test_failed_raid_cannot_grant_intimidate_credit():
    state = position(hidden=0)
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 2, piece_state=rc.REVEALED)
    place_piece(state, rc.UBII, rc.ROMANS, rc.AUXILIA)
    before = signature(state)
    result = _execute_raid(state, rc.GERMANS, action())
    assert not result['executed'] and result['errors']
    assert signature(state) == before


def test_enemy_leader_blocks_intrinsic_removals_but_not_marker():
    state = position()
    place_piece(state, rc.UBII, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, rc.UBII, rc.ROMANS, rc.AUXILIA, 2)
    result = _execute_raid(state, rc.GERMANS, action())
    assert result['executed']
    assert count_pieces(state, rc.UBII, rc.ROMANS, rc.AUXILIA) == 2
    assert rc.MARKER_INTIMIDATED in state['markers'][rc.UBII]


def test_event_cohort_raid_uses_same_intrinsic_primitive():
    from fs_bot.cards.dumnorix import raid_cohort
    state = position()
    place_piece(state, rc.UBII, rc.ROMANS, rc.AUXILIA, 2)
    cohort = [{'region': rc.UBII, 'faction': rc.GERMANS, 'count': 2}]
    choices = [{'region': rc.UBII, 'faction': rc.GERMANS, 'target_faction': None}] * 2
    result = raid_cohort(state, cohort, choices)
    assert result['regions'][0]['raid_intimidate']['executed']
    assert count_pieces(state, rc.UBII, rc.ROMANS, rc.AUXILIA) == 0


def test_three_raider_capability_still_limits_intimidate_to_two():
    from fs_bot.cards.capabilities import activate_capability, set_capability_owner
    state = position(hidden=3)
    activate_capability(state, 8, rc.EVENT_SHADED)
    set_capability_owner(state, 8, rc.GERMANS)
    place_piece(state, rc.UBII, rc.ROMANS, rc.AUXILIA, 3)
    result = raid_in_region(state, rc.UBII, rc.GERMANS, [{'type': 'gain'}] * 3)
    assert result['warbands_flipped'] == 3
    assert result['raid_intimidate']['executed']
    assert count_pieces(state, rc.UBII, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces_by_state(state, rc.UBII, rc.GERMANS, rc.WARBAND, rc.REVEALED) == 3


@pytest.mark.parametrize('owner,expected', [(rc.GERMANS, 3), (rc.BELGAE, 2), (None, 2)])
def test_raid_executor_honors_only_capability_owners_three_raiders(owner, expected):
    from fs_bot.cards.capabilities import activate_capability, set_capability_owner
    state = position(hidden=3)
    if owner is not None:
        activate_capability(state, 8, rc.EVENT_SHADED)
        set_capability_owner(state, 8, owner)
    place_piece(state, rc.UBII, rc.ROMANS, rc.AUXILIA, 3)
    planned = action()
    planned['details']['raid_plan'].append({'region': rc.UBII, 'target': None})
    result = _execute_raid(state, rc.GERMANS, planned)
    assert result['executed'] and not result['errors']
    assert result['raids'][0]['warbands_flipped'] == expected
    assert state['resources'][rc.GERMANS] == expected
    assert count_pieces_by_state(state, rc.UBII, rc.GERMANS, rc.WARBAND, rc.REVEALED) == expected
    assert count_pieces(state, rc.UBII, rc.ROMANS, rc.AUXILIA) == 1


@pytest.mark.parametrize('scope,with_sa,marked', [
    (None, True, {rc.UBII, rc.TREVERI, rc.SUGAMBRI}),
    ({rc.UBII, rc.TREVERI}, True, {rc.UBII, rc.TREVERI}),
    (None, False, {rc.UBII}),
])
def test_regular_intimidate_after_raid_uses_sa_geography_and_marker_phase(scope, with_sa, marked):
    """A8.7.1: ordinary removals/markers need not be in Raided Regions."""
    from fs_bot.bots.german_bot import _determine_intimidate_after_raid
    state = position()
    # Both non-Raid Regions are adjacent to Ariovistus and German Controlled.
    place_piece(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, 2)
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND)
    state['_command_with_sa'] = with_sa
    if scope is not None:
        state['_command_region_scope'] = scope
    planned = action()
    before = signature(state)
    sa, regions, details = _determine_intimidate_after_raid(
        state, planned['details']['raid_plan'])
    assert signature(state) == before
    planned.update(sa=sa, sa_regions=regions)
    planned['details'].update(details)
    result = _execute_decision(state, rc.GERMANS, {'bot_action': planned})
    assert result['executed'] and not result.get('errors')
    assert not result.get('sa_execution', {}).get('errors')
    assert {region for region in (rc.UBII, rc.TREVERI, rc.SUGAMBRI)
            if rc.MARKER_INTIMIDATED in state['markers'].get(region, {})} == marked
    assert count_pieces(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA) == (0 if with_sa else 1)
    assert count_pieces_by_state(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND,
                                 rc.HIDDEN) == (0 if rc.SUGAMBRI in marked else 1)
