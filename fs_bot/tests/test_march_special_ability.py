"""§§3.2.2, 3.3.2 and 4.1 permit one Special Ability within a March."""

from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_leader_in_region, place_piece
from fs_bot.cli.human_plan import collect_player_action
from fs_bot.engine import action_windows
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.free_actions import execute_free_action_plan, validate_free_action_response
from fs_bot.engine.game_engine import ACTION_COMMAND_SA, ACTION_LIMITED_COMMAND
from fs_bot.engine.march_interruption import PAUSE
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import validate_response


def roman_position(scenario=rc.SCENARIO_GREAT_REVOLT):
    state = build_initial_state(scenario, seed=24)
    state['resources'][rc.ROMANS] = 4
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION, from_legions_track=True)
    return state


def march(sa=rc.SA_BUILD, *, routes=None, group=1, hop=1, **details):
    if routes is None:
        routes = {rc.PROVINCIA: [rc.SEQUANI, rc.MANDUBII]}
    return {'command': rc.CMD_MARCH, 'sa': sa, 'sa_timing': 'during', 'details': {
        'origins': list(routes), 'routes': routes, 'sa_after_step': {'group': group, 'hop': hop},
        **details}}


def run(state, faction, action):
    return execute_decision(state, faction, {'action': ACTION_COMMAND_SA, 'player_action': action})


def checked(state, result):
    assert result['executed'] and not result['errors'], result
    assert result['sa_timing'] == 'during' and result['sa_execution']['executed'], result
    assert validate_state(state) == []
    assert PAUSE not in state and action_windows.COHORTS not in state


def test_build_only_legal_while_caesar_passes_through_sequani():
    state = roman_position()
    action = march(build_plan={'forts': [rc.SEQUANI]})
    for timing in ('before', 'after'):
        trial = deepcopy(state)
        ordinary = deepcopy(action)
        del ordinary['details']['sa_after_step']
        ordinary['sa_timing'] = timing
        ordinary['details']['destinations'] = [rc.MANDUBII]
        assert not run(trial, rc.ROMANS, ordinary)['sa_execution']['executed']
    result = run(state, rc.ROMANS, action)
    checked(state, result)
    assert result['origin_costs'] == {rc.PROVINCIA: 2}
    assert get_leader_in_region(state, rc.MANDUBII, rc.ROMANS) == rc.CAESAR
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.LEGION) == 1
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.FORT) == 1
    assert state['resources'][rc.ROMANS] == 0


def test_terminal_offers_sequani_build_on_detached_march_board():
    state = roman_position()
    before = encode(state)
    answers = StringIO('Command, Special Activity, then continue Command\n'
        'March (between hops or groups)\nProvincia\nSequani → Mandubii\n'
        'all 1\ny\nGroup 1 after hop 1 into Sequani\nBuild\nSequani\n'
        'place a Fort\nn\n')
    output = StringIO()
    try:
        action = collect_player_action(state, rc.ROMANS, ACTION_COMMAND_SA, answers, output)
    except EOFError:
        pytest.fail(output.getvalue())
    assert encode(state) == before
    assert action['details']['sa_after_step'] == {'group': 1, 'hop': 1}
    checked(state, run(state, rc.ROMANS, action))


@pytest.mark.parametrize('split_off', [False, True])
def test_scout_chooses_a_moving_auxilia_instead_of_an_identical_resident(split_off):
    state = roman_position()
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.SEQUANI, rc.BELGAE, rc.WARBAND, 2 if split_off else 3)
    if split_off:
        scout = {'auxilia_moves': [{'from_region': rc.SEQUANI, 'to_region': rc.PROVINCIA,
                                    'piece_state': rc.HIDDEN, 'count': 1}]}
    else:
        scout = {'scout_targets': [{'region': rc.SEQUANI, 'auxilia_count': 1,
                 'targets': [{'faction': rc.BELGAE, 'piece_state': rc.HIDDEN, 'count': 2}]}]}
    offered = []

    def agent(board, faction, request):
        if request.get('request_type') == 'harassment':
            pytest.fail('Harassment used the board before Scout Reveal')
        if request['kind'] == 'force_cohort':
            assert faction == rc.ROMANS and request['physical_owner'] == rc.ROMANS
            offered.append(request['available'])
            return {'counts': {'selected': 1}}

    state['decision_agent'] = agent
    checked(state, run(state, rc.ROMANS, march(rc.SA_SCOUT, scout_plan=scout)))
    assert offered == [{'selected': 1, 'other': 1}]
    assert count_pieces_by_state(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 1
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == int(split_off)
    assert count_pieces_by_state(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA,
                                rc.REVEALED) == int(not split_off)


def test_scout_arrivals_are_excluded_from_a_later_origin_even_after_its_hide():
    state = roman_position()
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA, piece_state=rc.REVEALED)
    action = march(rc.SA_SCOUT, routes={rc.PROVINCIA: [rc.SEQUANI, rc.MANDUBII],
        rc.SEQUANI: [rc.AEDUI_REGION]}, scout_plan={'auxilia_moves': [
            {'from_region': rc.TREVERI, 'to_region': rc.SEQUANI,
             'piece_state': rc.REVEALED, 'count': 1}]})
    result = run(state, rc.ROMANS, action)
    checked(state, result)
    assert result['origin_costs'] == {rc.PROVINCIA: 2, rc.SEQUANI: 2}
    assert count_pieces_by_state(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 1
    assert count_pieces(state, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA) == 1


def test_scout_cannot_choose_an_already_scouted_auxilia_from_a_later_origin():
    state = roman_position()
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA)
    action = march(rc.SA_SCOUT, routes={rc.PROVINCIA: [rc.SEQUANI, rc.MANDUBII],
        rc.SEQUANI: [rc.AEDUI_REGION]}, scout_plan={'auxilia_moves': [
            {'from_region': rc.TREVERI, 'to_region': rc.SEQUANI, 'piece_state': rc.HIDDEN, 'count': 1},
            {'from_region': rc.SEQUANI, 'to_region': rc.TREVERI, 'piece_state': rc.HIDDEN, 'count': 1}]})
    state['decision_agent'] = lambda board, actor, req: (
        pytest.fail('Scout exposed a counter that already Scouted') if req['kind'] == 'force_cohort' else None)
    checked(state, run(state, rc.ROMANS, action))
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA) == 1


@pytest.mark.parametrize('scout_moving', [False, True])
def test_march_keeps_exact_command_loan_after_separate_scout_agreement(scout_moving):
    state = roman_position(rc.SCENARIO_ARIOVISTUS)
    place_piece(state, rc.SEQUANI, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA)
    for region in (rc.PROVINCIA, rc.SEQUANI):
        place_piece(state, region, rc.AEDUI, rc.WARBAND)
    action = march(rc.SA_SCOUT, diviciacus_regions=[rc.PROVINCIA],
        diviciacus_sa_regions=[rc.SEQUANI], scout_plan={'auxilia_moves': [
            {'from_region': rc.SEQUANI, 'to_region': rc.AEDUI_REGION, 'piece_state': rc.HIDDEN,
             'count': 1, 'physical_owners': {rc.AEDUI: 1}}]})
    phases = []

    def agent(board, faction, request):
        if request.get('request_type') == 'diviciacus':
            assert faction == rc.AEDUI
            phases.append(request['context']['phase'])
            return {'agree': True}
        if request['kind'] == 'force_cohort':
            assert faction == rc.ROMANS and request['physical_owner'] == rc.AEDUI
            return {'counts': {'selected': int(scout_moving), 'other': int(not scout_moving)}}

    state['decision_agent'] = agent
    checked(state, run(state, rc.ROMANS, action))
    assert phases == ['command', 'special_ability']
    assert count_pieces(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == int(scout_moving)
    assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == int(not scout_moving)
    assert count_pieces(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == 1


def test_devastate_losses_apply_to_the_chosen_carried_warband():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=24)
    state['resources'][rc.ARVERNI] = 1
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(state, rc.BITURIGES, rc.ARVERNI, rc.WARBAND)

    def agent(board, faction, request):
        if request['kind'] == 'force_cohort':
            assert faction == rc.ARVERNI
            assert request['available'] == {'selected': 3, 'other': 1}
            return {'counts': {'selected': 1}}

    state['decision_agent'] = agent
    action = march(rc.SA_DEVASTATE, routes={rc.ARVERNI_REGION: [rc.BITURIGES, rc.CARNUTES]})
    action['sa_regions'] = [rc.BITURIGES]
    checked(state, run(state, rc.ARVERNI, action))
    assert state['markers'][rc.BITURIGES][rc.MARKER_DEVASTATED]
    assert count_pieces(state, rc.BITURIGES, rc.ARVERNI, rc.WARBAND) == 1
    assert count_pieces(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND) == 2


def test_trade_can_pay_for_the_next_selected_origin():
    from fs_bot.cards.card_effects import _ally_tribe

    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=24)
    state['resources'][rc.AEDUI] = 1
    place_piece(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND)
    assert _ally_tribe(state, rc.TRIBE_MANDUBII, rc.AEDUI)
    state['decision_agent'] = lambda board, faction, request: False if request['kind'] == 'agreement' else None
    action = march(rc.SA_TRADE, routes={rc.MANDUBII: [rc.AEDUI_REGION], rc.CARNUTES: [rc.BITURIGES]})
    result = run(state, rc.AEDUI, action)
    checked(state, result)
    assert result['origin_costs'] == {rc.MANDUBII: 1, rc.CARNUTES: 1}
    assert count_pieces(state, rc.BITURIGES, rc.AEDUI, rc.WARBAND) == 1


def test_intimidate_between_german_groups_keeps_arrivals_out_of_the_next_origin():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=24)
    state['resources'][rc.GERMANS] = 2
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    for region in (rc.CARNUTES, rc.MANDUBII):
        place_piece(state, region, rc.GERMANS, rc.WARBAND)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA)
    action = march(rc.SA_INTIMIDATE, routes={rc.CARNUTES: [rc.MANDUBII], rc.MANDUBII: [rc.TREVERI]},
        intimidate_plan=[{'region': rc.MANDUBII, 'target_faction': rc.ROMANS,
                          'target_piece': rc.AUXILIA, 'target_state': rc.HIDDEN}])
    state['decision_agent'] = lambda board, faction, request: (
        {'counts': {'selected': 1}} if request['kind'] == 'force_cohort' else None)
    result = run(state, rc.GERMANS, action)
    checked(state, result)
    assert result['origin_costs'] == {rc.CARNUTES: 1, rc.MANDUBII: 1}
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces_by_state(state, rc.MANDUBII, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 1
    assert count_pieces(state, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 1
    assert get_leader_in_region(state, rc.MANDUBII, rc.GERMANS) == rc.ARIOVISTUS_LEADER


def test_return_to_original_region_does_not_reuse_the_group_or_bill_its_origin_twice():
    state = roman_position()
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 2)
    action = march(routes={rc.PROVINCIA: [rc.SEQUANI, rc.PROVINCIA]},
        groups={rc.PROVINCIA: {rc.LEADER: True, rc.LEGION: 1, rc.AUXILIA: 1}},
        extra_groups=[{'origin': rc.PROVINCIA, 'route': [rc.AEDUI_REGION],
                       'group': {rc.AUXILIA: 1}}], build_plan={'forts': [rc.SEQUANI]})
    result = run(state, rc.ROMANS, action)
    checked(state, result)
    assert result['origin_costs'] == {rc.PROVINCIA: 2}
    assert [entry['final_region'] for entry in result['marches']] == [rc.PROVINCIA, rc.AEDUI_REGION]
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA) == 1


def test_scoped_free_march_and_build_use_the_same_boundary():
    state = roman_position()
    state['resources'][rc.ROMANS] = 0
    action = march(build_plan={'forts': [rc.SEQUANI]})
    request = {'request_type': 'event_command', 'allowed_commands': [rc.CMD_MARCH],
               'with_sa': True, 'max_regions': 1, 'allowed_regions': [rc.PROVINCIA, rc.SEQUANI]}
    before = encode(state)
    assert validate_free_action_response(state, rc.ROMANS, request, action) is None
    assert validate_free_action_response(state, rc.ROMANS, dict(request, with_sa=False), action)
    assert encode(state) == before
    result = execute_free_action_plan(state, rc.ROMANS, request, action)
    checked(state, result)
    assert result['total_cost'] == state['resources'][rc.ROMANS] == 0


@pytest.mark.parametrize('bad', [1, {'group': 0, 'hop': 1}, {'group': 1, 'hop': True},
                                 {'group': 1, 'hop': 2}, {'group': 1, 'hop': 3}])
def test_durable_turn_rejects_invalid_march_boundary(bad):
    state = roman_position()
    action = march(build_plan={'forts': [rc.SEQUANI]})
    action['details']['sa_after_step'] = bad
    request = {'kind': 'turn', 'faction': rc.ROMANS, 'options': [ACTION_COMMAND_SA]}
    with pytest.raises(ValueError, match='March'):
        validate_response(state, request, {'action': ACTION_COMMAND_SA, 'player_action': action})


def test_britannia_and_limited_command_still_restrict_special_ability():
    state = roman_position()
    action = march(routes={rc.MORINI: [rc.BRITANNIA]}, hop=0,
                   build_plan={'forts': [rc.SEQUANI]})
    assert 'Britannia' in run(state, rc.ROMANS, action)['reason']
    action = march(build_plan={'forts': [rc.SEQUANI]})
    result = execute_decision(state, rc.ROMANS,
                              {'action': ACTION_LIMITED_COMMAND, 'player_action': action})
    assert result['rejected'] and 'Limited Command' in result['reason']


def test_assistant_reloads_a_march_ability_pause_and_replays_exactly(tmp_path):
    import json
    from types import SimpleNamespace

    from fs_bot.engine import voluntary_removal
    from fs_bot.state.serialize import decode, load_game, save_game
    from fs_bot.tests.test_action_window_frontends import TIMING_DEFAULTS
    from fs_bot.tools import llm_seat

    state = roman_position()
    state['current_card'] = state['current_card_id'] = 16
    state['next_card'] = 17
    for faction in state['eligibility']:
        state['eligibility'][faction] = rc.ELIGIBLE if faction == rc.ROMANS else rc.INELIGIBLE
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA)
    path = tmp_path / 'live' / 'save.json'
    path.parent.mkdir()
    save_game(state, path, meta={'seat': rc.ROMANS, 'scenario': state['scenario'], 'seed': 24}, log=[])
    args = SimpleNamespace(dir=str(path.parent), output_dir=str(tmp_path / 'replay'))
    assert llm_seat.cmd_play(args) == 0
    initial, _, _ = load_game(path, validate=True)
    removal = None
    for _ in range(60):
        current, meta, log = load_game(path, validate=True)
        pending = meta['assistant_session']['pending']
        if not pending:
            break
        request = decode(pending['request'])
        kind = request['kind']
        if kind == 'turn':
            response = {'action': ACTION_COMMAND_SA,
                        'player_action': march(build_plan={'forts': [rc.SEQUANI]})}
        elif (removal is None and kind == voluntary_removal.KIND
              and request['window']['stage'] == 'special_ability'):
            assert encode(current) == encode(initial) and not log
            board = decode(pending['board'])
            assert PAUSE not in board and board['resources'][rc.ROMANS] == 2
            assert get_leader_in_region(board, rc.SEQUANI, rc.ROMANS) == rc.CAESAR
            option = next(entry for entry in request['options']
                          if entry.get('cohort') == 'moving_group' and entry['piece_type'] == rc.AUXILIA)
            assert llm_seat.cmd_play(args) == 0
            assert load_game(path)[1]['assistant_session']['pending'] == pending
            removal = voluntary_removal.operation(option)
            response = {'operations': [removal]}
        elif kind == 'march_dropoff':
            response = {'dropoffs': []}
        else:
            response = TIMING_DEFAULTS[kind]
        assert llm_seat.cmd_submit(SimpleNamespace(
            dir=args.dir, decision_id=pending['id'], response=json.dumps(response))) == 0
    else:
        pytest.fail('The interrupted March did not complete')

    assert removal is not None and validate_state(current) == []
    assert count_pieces(current, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(current, rc.SEQUANI, rc.ROMANS, rc.FORT) == 1
    assert count_pieces(current, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 0
    assert get_leader_in_region(current, rc.MANDUBII, rc.ROMANS) == rc.CAESAR
    assert llm_seat.cmd_replay(args) == 0
    replayed, _, replay_log = load_game(tmp_path / 'replay' / 'save.json', validate=True)
    assert encode(replayed) == encode(current) and replay_log == log
