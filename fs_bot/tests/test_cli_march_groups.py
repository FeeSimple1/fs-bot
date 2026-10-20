"""Terminal March groups: 3.2.2/3.3.2 and A3.4.2 permit multiple groups."""
from copy import deepcopy
from io import StringIO

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, get_leader_in_region
from fs_bot.cli.free_actions import collect_free_action
from fs_bot.engine.free_actions import execute_free_action_plan
from fs_bot.state.state_schema import build_initial_state


def collect(state, lines, *, chooser=rc.AEDUI, actor=rc.GERMANS):
    request = {'kind': 'free_action', 'request_type': 'event_command',
               'card_id': 'A34', 'acting_faction': actor,
               'allowed_commands': ['March'], 'max_regions': 3,
               'with_sa': False, 'free': True}
    before = deepcopy({k: v for k, v in state.items() if k != 'rng'})
    rng, output = state['rng'].getstate(), StringIO()
    plan = collect_free_action(state, chooser, request,
        StringIO('\n'.join(['Plan the action', 'March'] + lines) + '\n'), output)
    assert {k: v for k, v in state.items() if k != 'rng'} == before
    assert state['rng'].getstate() == rng
    result = execute_free_action_plan(state, chooser, request, plan)
    assert result['executed'] and not result.get('errors'), result
    return plan, output.getvalue()


def test_a34_menu_splits_one_origin_among_three_destinations_and_leaves_one():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=7)
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, 4)
    plan, output = collect(state, [
        rc.SUGAMBRI, rc.MORINI, '4',  # first group: 1 of 4
        'y', rc.NERVII, '3',          # second group: 1 of remaining 3
        'y', rc.UBII, '2',            # third group: 1 of remaining 2
        'n'])                         # retain the last Warband
    assert plan['details']['origins'] == [rc.SUGAMBRI]
    assert len(plan['details']['extra_groups']) == 2
    for region in (rc.SUGAMBRI, rc.MORINI, rc.NERVII, rc.UBII):
        assert count_pieces(state, region, rc.GERMANS, rc.WARBAND) == 1
    assert 'March group 3' in output and 'March group 4' in output


def test_a34_menu_marches_remaining_leader_after_all_warbands_depart():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=7)
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, 2)
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.LEADER,
                leader_name=rc.ARIOVISTUS_LEADER)
    plan, output = collect(state, [
        rc.SUGAMBRI, rc.MORINI, 'all 2', 'n',
        'y', rc.NERVII, 'y'])
    assert plan['details']['extra_groups'] == [
        {'origin': rc.SUGAMBRI, 'route': [rc.NERVII], 'group': {rc.LEADER: True}}]
    assert count_pieces(state, rc.MORINI, rc.GERMANS, rc.WARBAND) == 2
    assert get_leader_in_region(state, rc.NERVII, rc.GERMANS) == rc.ARIOVISTUS_LEADER
    assert count_pieces(state, rc.SUGAMBRI, rc.GERMANS) == 0


def test_empty_extra_group_can_be_cancelled_without_spending_remaining_pieces():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=7)
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, 2)
    plan, output = collect(state, [
        rc.SUGAMBRI, rc.MORINI, '2',
        'y', rc.NERVII, '0', 'n'])
    assert 'extra_groups' not in plan['details']
    assert 'No pieces selected for this group.' in output
    assert count_pieces(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND) == 1
    assert count_pieces(state, rc.MORINI, rc.GERMANS, rc.WARBAND) == 1


def test_repeated_groups_track_remaining_borrowed_and_belgic_warbands():
    from fs_bot.commands.sa_enlist import begin_borrow, end_borrow
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=7)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 4)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 2)
    begin_borrow(state, {'command': rc.CMD_MARCH, 'sa': rc.SA_ENLIST,
                        'details': {'enlist': {'type': 'borrow', 'regions': [rc.NERVII]}}})
    try:
        plan, output = collect(state, [
            rc.NERVII, rc.MORINI, '5', 'y', '2',  # 2 WB: 1 Belgic + 1 German
            'y', rc.ATREBATES, '3', '1',           # another 1 Belgic + 1 German
            'y', rc.TREVERI, '1', '0'],           # final 2 Belgic, no Germans
            chooser=rc.BELGAE, actor=rc.BELGAE)
        assert [g['group']['german_warbands'] for g in plan['details']['extra_groups']] == [1, 0]
    finally:
        end_borrow(state)
    for region in (rc.MORINI, rc.ATREBATES):
        assert count_pieces(state, region, rc.BELGAE, rc.WARBAND) == 1
        assert count_pieces(state, region, rc.GERMANS, rc.WARBAND) == 1
    assert count_pieces(state, rc.TREVERI, rc.BELGAE, rc.WARBAND) == 2
    assert count_pieces(state, rc.NERVII, rc.BELGAE) == 0
    assert count_pieces(state, rc.NERVII, rc.GERMANS) == 0
