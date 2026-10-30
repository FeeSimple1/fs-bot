"""SA menus use authored timing, live targets and shared Resources/pools."""
from copy import deepcopy
from io import StringIO

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import count_pieces, get_available, get_leader_in_region, place_piece
from fs_bot.cli.human_plan import _collect_sa_plan, _preview_sa
from fs_bot.cli.sa_timing import (
    collect_entreat, collect_scalar, collect_suborn, collect_intimidate, collect_rampage)
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tests.test_rally_option_interruption import boxed_position_and_plan


DONE = 'Finish voluntary removal'


def entreat_position():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=9)
    state['non_player_factions'] = set()
    state['_cli_action_windows'] = True
    state['resources'][rc.ARVERNI] = 3
    place_piece(state, rc.PICTONES, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND, 2)
    place_piece(state, rc.PICTONES, rc.ROMANS, rc.AUXILIA)
    refresh_all_control(state)
    return state


def test_sa_start_entry_enables_devastate_and_keeps_per_region_metadata():
    state, command = boxed_position_and_plan()
    state['_cli_action_windows'] = True
    state['_cli_allowed_regions'] = [rc.ARVERNI_REGION]
    before = encode(state)
    answers = '\n'.join([DONE, rc.ARVERNI_REGION, DONE, rc.ARVERNI_REGION, DONE, ''])
    action = _collect_sa_plan(state, rc.ARVERNI, command, StringIO(answers),
                              StringIO(), sa=rc.SA_DEVASTATE)
    details = action['details']['sa_details']
    assert details['timing_actions'][-1] == {
        'kind': 'spring_leader', 'response': {'region': rc.ARVERNI_REGION}}
    assert 'devastate_region:0' in details['stage_timing_actions']
    assert details['after_sa_timing_actions']
    assert encode(state) == before
    sim = deepcopy(state)
    sim['_diviciacus_preview'] = True
    result = _preview_sa(sim, rc.ARVERNI, action)
    assert result['executed'] and not result['errors']
    assert get_leader_in_region(sim, rc.ARVERNI_REGION, rc.ARVERNI) == rc.VERCINGETORIX
    assert sim['markers'][rc.ARVERNI_REGION][rc.MARKER_DEVASTATED]
    assert validate_state(sim) == []


def test_entreat_step_reclaims_a_counter_before_target_and_pool_choices():
    state = entreat_position()
    count = get_available(state, rc.ARVERNI, rc.WARBAND)
    place_piece(state, rc.PROVINCIA, rc.ARVERNI, rc.WARBAND, count)
    before = encode(state)
    answers = '\n'.join([
        f'Remove {rc.WARBAND} {rc.HIDDEN} in {rc.PROVINCIA} [up to {count}]',
        '1', DONE, rc.PICTONES,
        f'replace a {rc.ROMANS} {rc.AUXILIA} ({rc.HIDDEN}) with your Warband', DONE, ''])
    entries, extra = collect_entreat(state, rc.ARVERNI, StringIO(answers), StringIO())
    assert len(entries) == 1 and entries[0]['timing_actions'][0]['response']['operations']
    assert encode(state) == before
    action = {'command': rc.CMD_RALLY, 'sa': rc.SA_ENTREAT,
              'sa_regions': entries, 'details': extra}
    sim = deepcopy(state)
    sim['_diviciacus_preview'] = True
    result = _preview_sa(sim, rc.ARVERNI, action)
    assert result['executed'] and not result['errors']
    assert count_pieces(sim, rc.PICTONES, rc.ARVERNI, rc.WARBAND) == 3
    assert count_pieces(sim, rc.PROVINCIA, rc.ARVERNI, rc.WARBAND) == count - 1
    assert count_pieces(sim, rc.PICTONES, rc.ROMANS, rc.AUXILIA) == 0
    assert get_available(sim, rc.ARVERNI, rc.WARBAND) == 0
    assert validate_state(sim) == []


def test_entreat_reserves_resources_and_never_reselects_completed_region():
    state = entreat_position()
    state['resources'][rc.ARVERNI] = 1
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND)
    place_piece(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA)
    before = encode(state)
    answers = '\n'.join([DONE, rc.PICTONES,
        f'replace a {rc.ROMANS} {rc.AUXILIA} ({rc.HIDDEN}) with your Warband', DONE, ''])
    entries, _ = collect_entreat(state, rc.ARVERNI, StringIO(answers), StringIO())
    assert len(entries) == 1 and entries[0]['region'] == rc.PICTONES
    assert encode(state) == before


def test_settle_reserves_shared_resources_before_offering_later_regions():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=3)
    state['non_player_factions'] = set()
    state['_cli_action_windows'] = True
    state['resources'][rc.GERMANS] = 2
    place_piece(state, rc.TREVERI, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    for region in (rc.TREVERI, rc.NERVII):
        place_piece(state, region, rc.GERMANS, rc.WARBAND, 2)
    refresh_all_control(state)
    before = encode(state)
    regions, extra = collect_scalar(state, rc.GERMANS, rc.SA_SETTLE,
                                    StringIO(f'{DONE}\n{rc.TREVERI}\n{DONE}\n'), StringIO())
    assert regions == [rc.TREVERI]
    assert 'settle_region:0' in extra['sa_details']['stage_timing_actions']
    assert encode(state) == before


def suborn_position():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=8)
    state['non_player_factions'] = set()
    state['_cli_action_windows'] = True
    state['resources'][rc.AEDUI] = 10
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND)
    refresh_all_control(state)
    return state


def test_suborn_reclaims_between_operations_and_replays_each_timing_once():
    state = suborn_position()
    count = get_available(state, rc.AEDUI, rc.WARBAND) - 1
    place_piece(state, rc.PROVINCIA, rc.AEDUI, rc.WARBAND, count)
    before = encode(state)
    answers = '\n'.join([DONE, rc.CARNUTES, DONE, 'place Aedui Warband',
        f'Remove {rc.WARBAND} {rc.HIDDEN} in {rc.PROVINCIA} [up to {count}]',
        '1', DONE, 'place Aedui Warband', DONE, '(done)', ''])
    regions, extra = collect_suborn(state, rc.AEDUI, StringIO(answers), StringIO())
    assert regions == [rc.CARNUTES]
    operations = extra['suborn_plan'][0]['actions']
    assert len(operations) == 2
    assert operations[1]['timing_actions'][0]['response']['operations']
    assert encode(state) == before
    action = {'command': rc.CMD_RALLY, 'sa': rc.SA_SUBORN,
              'sa_regions': regions, 'details': extra}
    sim = deepcopy(state)
    sim['_diviciacus_preview'] = True
    result = _preview_sa(sim, rc.AEDUI, action)
    assert result['executed'] and not result['errors'], result
    assert count_pieces(sim, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 3
    assert count_pieces(sim, rc.PROVINCIA, rc.AEDUI, rc.WARBAND) == count - 1
    assert get_available(sim, rc.AEDUI, rc.WARBAND) == 0
    assert sim['resources'][rc.AEDUI] == 8
    assert validate_state(sim) == []


def test_suborn_undo_explicitly_reverses_the_operation_and_its_planning_choices():
    state = suborn_position()
    before = encode(state)
    answers = '\n'.join([DONE, rc.CARNUTES, DONE, 'place Aedui Warband',
        DONE, '(undo last operation and its timing choices)', DONE,
        'place Romans Auxilia', DONE, '(done)', ''])
    regions, extra = collect_suborn(state, rc.AEDUI, StringIO(answers), StringIO())
    operations = extra['suborn_plan'][0]['actions']
    assert len(operations) == 1 and operations[0]['faction'] == rc.ROMANS
    assert encode(state) == before
    sim = deepcopy(state)
    sim['_diviciacus_preview'] = True
    result = _preview_sa(sim, rc.AEDUI, {'command': rc.CMD_RALLY,
        'sa': rc.SA_SUBORN, 'sa_regions': regions, 'details': extra})
    assert result['executed'] and not result['errors'], result
    assert count_pieces(sim, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 1
    assert count_pieces(sim, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 1


def test_intimidate_exact_visibility_and_first_entry_timing_are_preserved():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=3)
    state['non_player_factions'] = set()
    state['_cli_action_windows'] = True
    place_piece(state, rc.TREVERI, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    place_piece(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, 2)
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA, 2)
    refresh_all_control(state)
    before = encode(state)
    answers = '\n'.join([DONE, rc.TREVERI, rc.ROMANS,
                          f'{rc.AUXILIA} {rc.HIDDEN}', f'{rc.AUXILIA} {rc.HIDDEN}', DONE, ''])
    regions, extra = collect_intimidate(state, rc.GERMANS, StringIO(answers), StringIO())
    entries = extra['intimidate_plan']
    assert len(entries) == 2 and entries[0]['timing_actions']
    assert 'timing_actions' not in entries[1]
    assert encode(state) == before
    sim = deepcopy(state)
    sim['_diviciacus_preview'] = True
    result = _preview_sa(sim, rc.GERMANS, {'command': rc.CMD_RAID,
        'sa': rc.SA_INTIMIDATE, 'sa_regions': regions, 'details': extra})
    assert result['executed'] and not result['errors'], result
    assert count_pieces(sim, rc.TREVERI, rc.ROMANS, rc.AUXILIA) == 0
    assert sim['markers'][rc.TREVERI][rc.MARKER_INTIMIDATED]


def test_rampage_timing_preview_and_execution_include_scouted_warbands():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=3)
    state['non_player_factions'] = set()
    state['_cli_action_windows'] = True
    place_piece(state, rc.TREVERI, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    place_piece(state, rc.TREVERI, rc.BELGAE, rc.WARBAND, 2)
    place_piece(state, rc.TREVERI, rc.ARVERNI, rc.WARBAND, piece_state=rc.SCOUTED)
    refresh_all_control(state)
    before = encode(state)
    entries, extra = collect_rampage(state, rc.BELGAE,
        StringIO(f'{DONE}\n{rc.TREVERI}\n{rc.ARVERNI}\n{DONE}\n'), StringIO())
    assert len(entries) == 1 and entries[0]['timing_actions']
    assert encode(state) == before
    sim = deepcopy(state)
    sim['_diviciacus_preview'] = True
    result = _preview_sa(sim, rc.BELGAE, {'command': rc.CMD_RALLY,
        'sa': rc.SA_RAMPAGE, 'sa_regions': entries, 'details': extra})
    assert result['executed'] and not result['errors'], result
    assert count_pieces(sim, rc.TREVERI, rc.ARVERNI, rc.WARBAND) == 0
    assert validate_state(sim) == []


def test_enlist_borrow_preparation_uses_precommand_board_and_runs_each_tail_once():
    from fs_bot.cli.human_plan import _collect_enlist
    from fs_bot.commands.sa_enlist import BORROW_KEY
    from fs_bot.engine.execute import execute_decision
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=3)
    state['non_player_factions'] = set()
    state['_cli_action_windows'] = True
    state['resources'][rc.BELGAE] = 10
    place_piece(state, rc.NERVII, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 2)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 3)
    refresh_all_control(state)
    before = encode(state)
    after = deepcopy(state)
    place_piece(after, rc.NERVII, rc.BELGAE, rc.WARBAND)
    after_before = encode(after)
    answers = '\n'.join([
        f'Remove {rc.WARBAND} {rc.HIDDEN} in {rc.NERVII} [up to 2]', '1', DONE,
        rc.NERVII, '(done)', ''])
    regions, details = _collect_enlist(after, rc.BELGAE, StringIO(answers), StringIO(),
                                       before_state=state, borrow_only=True)
    assert encode(state) == before and encode(after) == after_before
    details['rally_plan'] = {'steps': [
        {'region': rc.NERVII, 'action': 'place_ally', 'tribe': rc.TRIBE_NERVII}]}
    details['after_command_timing_actions'] = [{'kind': 'voluntary_removal', 'response': {
        'operations': [{'action': 'remove', 'region': rc.NERVII, 'piece_type': rc.WARBAND,
                        'piece_state': rc.HIDDEN, 'count': 1}]}}]
    details['sa_details']['after_sa_timing_actions'] = [{'kind': 'voluntary_removal', 'response': {
        'operations': [{'action': 'remove', 'region': rc.NERVII, 'piece_type': rc.LEADER,
                        'count': 1}]}}]
    result = execute_decision(state, rc.BELGAE, {'player_action': {
        'command': rc.CMD_RALLY, 'sa': rc.SA_ENLIST, 'sa_timing': 'before',
        'sa_regions': regions, 'details': details}})
    assert result['executed'] and not result.get('errors'), result
    assert count_pieces(state, rc.NERVII, rc.BELGAE, rc.WARBAND) == 0
    assert count_pieces(state, rc.NERVII, rc.BELGAE, rc.ALLY) == 1
    assert get_leader_in_region(state, rc.NERVII, rc.BELGAE) is None
    assert count_pieces(state, rc.NERVII, rc.GERMANS, rc.WARBAND) == 3
    assert BORROW_KEY not in state
    assert validate_state(state) == []
