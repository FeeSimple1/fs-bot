"""Action timing survives planning, pending decisions and old transcripts."""
import copy
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, get_leader_in_region
from fs_bot.cli import human_plan, action_windows as planning
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine import action_windows, voluntary_removal, spring
from fs_bot.engine.game_engine import ACTION_COMMAND, ACTION_PASS
from fs_bot.state.serialize import encode
from fs_bot.state.setup import setup_scenario
from fs_bot.tools.seat_session import (
    SeatSession, DecisionPending, board_copy, fingerprint, validate_response,
    _decision_signatures,
)


def _state(scenario=rc.SCENARIO_GREAT_REVOLT, faction=rc.ARVERNI):
    state = setup_scenario(scenario, seed=13)
    state['non_player_factions'] = {rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE} - {faction}
    return state


def _session(state, faction=rc.ARVERNI):
    session = SeatSession(state, {'seat': faction}, [], HumanTurnDisplay(io.StringIO()))
    state['decision_agent'] = session.reactive
    return session


def test_preparation_reclaims_empty_pool_before_command_menu_and_preserves_live_state(monkeypatch):
    state = _state()
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND,
                state['available'][rc.ARVERNI][rc.WARBAND])
    assert state['available'][rc.ARVERNI][rc.WARBAND] == 0
    state['decision_agent'] = make_cli_reactive([rc.ARVERNI], io.StringIO(), io.StringIO())
    before = encode(board_copy(state))
    request = voluntary_removal.make_request(state, rc.ARVERNI)
    index = next(i for i, option in enumerate(request['options'])
                 if option['piece_type'] == rc.WARBAND and option['region'] == rc.CARNUTES)
    seen = []
    def collect(sim, faction, action, stdin, stdout):
        seen.append(sim['available'][faction][rc.WARBAND])
        return {'command': 'Rally', 'regions': [rc.CARNUTES], 'details': {}}
    monkeypatch.setattr(human_plan, '_collect_player_action', collect)
    output = io.StringIO()
    plan = human_plan.collect_player_action(state, rc.ARVERNI, ACTION_COMMAND,
        io.StringIO(f'board\n{index + 3}\n1\n1\n'), output)
    assert seen == [1]
    assert plan['details']['timing_actions'][0]['response']['operations'][0]['count'] == 1
    assert encode(board_copy(state)) == before
    assert 'REGIONS' in output.getvalue()
    assert 'Current card:' in output.getvalue() and 'Upcoming card:' in output.getvalue()
    assert 'changes since your last decision' in output.getvalue()


def test_pass_has_no_timing_prompt_or_planned_removal():
    state = _state()
    state['decision_agent'] = make_cli_reactive([rc.ARVERNI], io.StringIO(), io.StringIO())
    output = io.StringIO()
    assert human_plan.collect_player_action(state, rc.ARVERNI, ACTION_PASS,
                                           io.StringIO(), output) is None
    assert output.getvalue() == ''


def test_planning_entry_is_explicit_and_does_not_consume_rng():
    state = _state(rc.SCENARIO_PAX_GALLICA)
    spring.unlock_spring_box_entry(state)
    state['decision_agent'] = make_cli_reactive([rc.ARVERNI], io.StringIO(), io.StringIO())
    before = encode(board_copy(state))
    request = spring.spring_box_request(state)
    selection = request['legal_regions'].index(rc.CARNUTES) + 2
    sim, actions = planning.prepare(state, rc.ARVERNI,
        io.StringIO(f'1\n{selection}\n'), io.StringIO(), stage='rally_option')
    assert get_leader_in_region(sim, rc.CARNUTES, rc.ARVERNI) == rc.VERCINGETORIX
    assert actions[-1] == {'kind': spring.KIND, 'response': {'region': rc.CARNUTES}}
    assert encode(board_copy(state)) == before
    assert sim['rng'].getstate() == state['rng'].getstate()


def test_mid_action_spring_default_remains_distinct_from_defer():
    state = _state(rc.SCENARIO_PAX_GALLICA)
    spring.unlock_spring_box_entry(state)
    request = spring.mid_action_request(state, {'stage': 'rally_option'})
    assert validate_response(state, request, {'use_default': True}) == {'use_default': True}
    assert validate_response(state, spring.spring_box_request(state), {'use_default': True}) is None


@pytest.mark.parametrize('response', [None, {'operations': [{'count': 999}]}, {'unknown': True}])
def test_bad_window_response_keeps_same_pending_id_and_board(response):
    state = _state()
    session = _session(state)
    request = voluntary_removal.make_request(state, rc.ARVERNI, window={'stage': 'rally_option'})
    session.import_inbox([{'response': response}])
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending):
        session.reactive(state, rc.ARVERNI, request)
    assert session.data['pending']['id'] == 'd000001'
    assert session.data['pending']['action_windows_version'] == 1
    assert len(session.data['queue']) == 1 and not session.data['journal']
    assert encode(board_copy(state)) == before


def test_only_old_pending_history_skips_new_window_then_fresh_choice_stays_pending():
    state = _state()
    session = _session(state)
    old_request = {'kind': 'agreement', 'faction': rc.ARVERNI}
    session.data['pending'] = {'id': 'd000001', 'request': old_request,
                               'board': encode(board_copy(state))}
    session.import_inbox({'decision_id': 'd000001', 'response': False})
    request = voluntary_removal.make_request(state, rc.ARVERNI, window={'stage': 'before'})
    assert session.reactive(state, rc.ARVERNI, request) is None
    assert session.cursor == 0 and len(session.data['queue']) == 1
    assert session.reactive(state, rc.ARVERNI, old_request) is False
    with pytest.raises(DecisionPending):
        session.reactive(state, rc.ARVERNI, request)
    assert session.data['pending']['id'] == 'd000002'
    assert session.data['pending']['request']['kind'] == voluntary_removal.KIND


def test_old_replay_tail_is_scoped_to_recorded_transaction():
    state = _state()
    session = _session(state)
    old_request = {'kind': 'agreement', 'faction': rc.ARVERNI}
    signature = fingerprint({'board': board_copy(state), 'request': old_request})
    session.data['expected'] = [{'id': 'd000001', 'signature': signature,
                                'request': old_request, 'action_windows_version': 0}]
    session.data['queue'] = [{'response': False}]
    session.checkpoint()
    request = voluntary_removal.make_request(state, rc.ARVERNI, window={'stage': 'before'})
    assert session.reactive(state, rc.ARVERNI, request) is None
    assert session.reactive(state, rc.ARVERNI, old_request) is False
    assert session.reactive(state, rc.ARVERNI, request) is None
    session.finish()
    session.checkpoint()
    with pytest.raises(DecisionPending):
        session.reactive(state, rc.ARVERNI, request)


def test_ephemeral_frames_do_not_change_old_signatures_but_window_and_board_do():
    state = _state()
    request = {'kind': 'agreement'}
    before = _decision_signatures(state, request)
    state[action_windows.SCOPE] = {'actor': rc.ARVERNI, 'phase': 'sequence_of_play'}
    state[action_windows.BUSY] = True
    assert _decision_signatures(state, request) == before
    assert _decision_signatures(state, dict(request, window={'stage': 'after'})) != before
    state['resources'][rc.ARVERNI] += 1
    assert _decision_signatures(state, request) != before


def _roman_planning_state():
    from fs_bot.state.state_schema import build_initial_state
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=9)
    state['non_player_factions'] = {rc.ARVERNI, rc.AEDUI, rc.BELGAE}
    state['resources'][rc.ROMANS] = 20
    state['_cli_action_windows'] = True
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    return state


def _decline_removal(monkeypatch):
    from fs_bot.cli import voluntary_removal as cli_removal
    monkeypatch.setattr(cli_removal, 'collect_removals', lambda *args: {'done': True})


def test_build_preview_allows_fort_and_ally_in_same_region_and_replays(monkeypatch):
    from fs_bot.cli import roman_timing
    from fs_bot.engine.execute import _execute_sa
    from fs_bot.board.pieces import count_pieces
    state = _roman_planning_state()
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.ALLY)
    state['tribes'][rc.SEQUANI]['allied_faction'] = rc.ROMANS
    _decline_removal(monkeypatch)
    monkeypatch.setattr(human_plan, '_pick_regions', lambda *args, **kwargs: [rc.SEQUANI])
    def pick(stdin, stdout, prompt, choices):
        return next(value for label, value in choices if value is not None)
    monkeypatch.setattr(roman_timing, 'prompt_choice', pick)
    before = encode(board_copy(state))
    regions, extra = roman_timing.collect_build(state, rc.ROMANS, io.StringIO(), io.StringIO())
    assert encode(board_copy(state)) == before
    assert extra['build_plan']['forts'] == [rc.SEQUANI]
    assert extra['build_plan']['allies'][0]['tribe'] == rc.TRIBE_HELVETII
    action = {'command': 'Recruit', 'sa': 'Build', 'sa_regions': regions, 'details': extra}
    with action_windows.scope(state, actor=rc.ROMANS, plan=action):
        result = _execute_sa(state, rc.ROMANS, action)
    assert result['executed']
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.FORT) == 1
    assert state['tribes'][rc.TRIBE_HELVETII]['allied_faction'] == rc.ROMANS
    assert state['resources'][rc.ROMANS] == 16


def test_scout_preview_excludes_arrivals_from_second_move_but_allows_reveal(monkeypatch):
    from fs_bot.cli import roman_timing
    from fs_bot.engine.execute import _execute_sa
    from fs_bot.board.pieces import count_pieces_by_state
    state = _roman_planning_state()
    place_piece(state, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 2)
    _decline_removal(monkeypatch)
    movement, reveal = [0], [0]
    def pick(stdin, stdout, prompt, choices):
        if prompt == 'Scout movement?':
            movement[0] += 1
            if movement[0] == 1:
                return next(v for _, v in choices if v and v[0] == rc.AEDUI_REGION)
            assert not any(v and v[0] == rc.SEQUANI for _, v in choices)
            return None
        if prompt == 'Move Auxilia INTO:':
            return rc.SEQUANI
        if prompt.startswith('How many'):
            return 2
        if prompt == 'Scout Reveal?':
            reveal[0] += 1
            if reveal[0] == 1:
                return next(v for _, v in choices if v and v[:2] == (rc.SEQUANI, rc.ARVERNI))
            return None
        raise AssertionError(prompt)
    monkeypatch.setattr(roman_timing, 'prompt_choice', pick)
    before = encode(board_copy(state))
    regions, extra = roman_timing.collect_scout(state, rc.ROMANS, io.StringIO(), io.StringIO())
    assert encode(board_copy(state)) == before
    assert len(extra['scout_plan']['auxilia_moves']) == 1
    action = {'command': 'Recruit', 'sa': 'Scout', 'sa_regions': regions, 'details': extra}
    with action_windows.scope(state, actor=rc.ROMANS, plan=action):
        result = _execute_sa(state, rc.ROMANS, action)
    assert result['executed']
    assert count_pieces_by_state(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, rc.SCOUTED) == 2
    assert count_pieces_by_state(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 1


def test_accepted_removal_survives_rollback_save_resume_and_exact_replay(tmp_path):
    from fs_bot.engine.agent import consult_agent
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.state.serialize import load_game, save_game, decode
    state = _state()
    origin = copy.deepcopy(state)
    session = _session(state)
    request = voluntary_removal.make_request(state, rc.ARVERNI)
    selected = next(option for option in request['options']
                    if option['piece_type'] == rc.WARBAND and option['region'] == rc.CARNUTES)
    response = {'operations': [voluntary_removal.operation(selected, 1)]}

    def run(current):
        def driver(*args):
            pass
        driver.transaction_checkpoint = current.checkpoint
        driver.transaction_restore = current.restore
        with _action_transaction(current.state, driver):
            with action_windows.scope(current.state, actor=rc.ARVERNI):
                action_windows.window(current.state, 'rally_option')
                return consult_agent(current.state, rc.ARVERNI, {'kind': 'agreement'})

    session.import_inbox([{'response': response}])
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending):
        run(session)
    assert encode(board_copy(state)) == before
    assert len(session.data['journal']) == 1
    pending = session.data['pending']
    assert pending['id'] == 'd000002'
    assert action_windows.SCOPE not in decode(pending['board'])
    save_game(state, tmp_path / 'timing.json', meta=session.meta, log=session.log)
    loaded, meta, log = load_game(tmp_path / 'timing.json', validate=True)
    resumed = SeatSession(loaded, meta, log, HumanTurnDisplay(io.StringIO()))
    loaded['decision_agent'] = resumed.reactive
    resumed.import_inbox([{'decision_id': pending['id'], 'response': {'done': True}},
                          {'response': False}])
    assert run(resumed) is False
    resumed.finish()
    assert loaded['available'][rc.ARVERNI][rc.WARBAND] == origin['available'][rc.ARVERNI][rc.WARBAND] + 1
    replay = _session(origin)
    replay.data['queue'] = [SeatSession._inbox_entry(entry) for entry in resumed.log]
    replay.data['expected'] = [
        {'id': entry['assistant_id'], 'signature': entry['assistant_signature'],
         'request': entry['assistant_request'],
         'action_windows_version': entry.get('assistant_action_windows_version', 0)}
        for entry in resumed.log]
    assert run(replay) is False
    replay.finish()
    assert encode(board_copy(replay.state)) == encode(board_copy(resumed.state))
    assert replay.log == resumed.log


def test_planning_removal_updates_carried_scout_ledger_across_temporary_scope():
    from fs_bot.commands.sa_scout import scout_movement_step, scout_moved_count
    state = planning.planning_copy(_roman_planning_state())
    place_piece(state, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA, 2)
    scout_movement_step(state, {'from_region': rc.AEDUI_REGION, 'to_region': rc.SEQUANI,
                               'count': 2, 'piece_state': rc.HIDDEN})
    cohorts = action_windows._combined_cohorts(state, rc.ROMANS, None)
    request = voluntary_removal.make_request(state, rc.ROMANS, cohorts=cohorts)
    selected = next(option for option in request['options'] if option.get('cohort'))
    planning.apply_planned(state, rc.ROMANS, [{
        'kind': 'voluntary_removal',
        'response': {'operations': [voluntary_removal.operation(selected, 1)]},
    }], stage='scout_move')
    assert scout_moved_count(state, rc.SEQUANI, rc.HIDDEN) == 1
    assert action_windows.SCOPE not in state
    # Building the next menu must see exactly the one surviving moved counter.
    remaining = voluntary_removal.make_request(state, rc.ROMANS,
        cohorts=action_windows._combined_cohorts(state, rc.ROMANS, None))
    assert next(option for option in remaining['options'] if option.get('cohort'))['max_count'] == 1


def test_raid_planning_applies_between_flip_removal_once_then_replays(monkeypatch):
    from fs_bot.cli import command_timing, voluntary_removal as cli_removal
    from fs_bot.board.pieces import count_pieces_by_state
    from fs_bot.engine.execute import execute_decision
    from fs_bot.state.state_schema import build_initial_state
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=4)
    state['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE}
    state['_cli_action_windows'] = True
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 2)
    calls = []
    def removals(sim, faction, request, stdin, stdout):
        calls.append(True)
        if len(calls) == 2:
            revealed = next(option for option in request['options']
                            if option.get('piece_state') == rc.REVEALED)
            return {'operations': [voluntary_removal.operation(revealed, 1)]}
        return {'done': True}
    monkeypatch.setattr(cli_removal, 'collect_removals', removals)
    monkeypatch.setattr(human_plan, '_pick_regions', lambda *args, **kwargs: [rc.CARNUTES])
    monkeypatch.setattr(command_timing, 'prompt_choice', lambda *args: None)  # gain one
    before = encode(board_copy(state))
    details = command_timing.collect_raid(state, rc.ARVERNI, io.StringIO(), io.StringIO(), False)
    assert encode(board_copy(state)) == before
    assert len(details['raid_plan']) == 2
    assert details['raid_plan'][1]['timing_actions'][0]['response']['operations'][0]['piece_state'] == rc.REVEALED
    action = {'command': 'Raid', 'regions': [], 'sa': 'No SA', 'details': details}
    result = execute_decision(state, rc.ARVERNI, {'player_action': action})
    assert result['executed']
    assert count_pieces_by_state(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, rc.REVEALED) == 1
    assert state['resources'][rc.ARVERNI] == 2


def test_seize_planning_reserves_markers_without_rolling_any_dice(monkeypatch):
    from fs_bot.cli import command_timing
    from fs_bot.state.state_schema import build_initial_state
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=4)
    state['_cli_action_windows'] = True
    state['non_player_factions'] = {rc.ARVERNI, rc.AEDUI, rc.BELGAE}
    for region in (rc.CARNUTES, rc.MANDUBII):
        place_piece(state, region, rc.ROMANS, rc.AUXILIA, 2)
    _decline_removal(monkeypatch)
    monkeypatch.setattr(human_plan, '_pick_regions', lambda *args, **kwargs: [rc.CARNUTES, rc.MANDUBII])
    monkeypatch.setattr(command_timing, 'prompt_yes_no', lambda *args, **kwargs: True)
    captured = []
    original = command_timing.prepare
    def prepare(sim, *args, **kwargs):
        captured.append(copy.deepcopy(sim))
        return original(sim, *args, **kwargs)
    monkeypatch.setattr(command_timing, 'prepare', prepare)
    before = encode(board_copy(state))
    details = command_timing.collect_seize(state, rc.ROMANS, io.StringIO(), io.StringIO(), False)
    assert details['_regions'] == [rc.CARNUTES, rc.MANDUBII]
    assert details['disperse_regions'] == [rc.CARNUTES, rc.MANDUBII]
    assert encode(board_copy(state)) == before
    assert captured[1]['rng'].getstate() == state['rng'].getstate()
    assert sum(info.get('status') == rc.DISPERSED for info in captured[1]['tribes'].values()) == 2


def test_german_raid_tail_removal_keeps_exact_credit_until_intrinsic_window(monkeypatch):
    from fs_bot.cli import command_timing, voluntary_removal as cli_removal
    from fs_bot.board.pieces import count_pieces_by_state
    from fs_bot.engine.execute import execute_decision
    from fs_bot.state.state_schema import build_initial_state
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=4)
    state['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE}
    state['_cli_action_windows'] = True
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 2)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    calls = []
    def removals(sim, faction, request, stdin, stdout):
        calls.append(True)
        if len(calls) == 2:
            selected = next(option for option in request['options'] if option.get('cohort'))
            return {'operations': [voluntary_removal.operation(selected, 1)]}
        return {'done': True}
    monkeypatch.setattr(cli_removal, 'collect_removals', removals)
    monkeypatch.setattr(human_plan, '_pick_regions', lambda *args, **kwargs: [rc.NERVII])
    choices = iter([None, 'done'])
    monkeypatch.setattr(command_timing, 'prompt_choice', lambda *args: next(choices))
    details = command_timing.collect_raid(state, rc.GERMANS, io.StringIO(), io.StringIO(), False)
    assert len(details['raid_plan']) == 1
    assert details['raid_timing_actions'][rc.NERVII][0]['response']['operations'][0]['cohort'] == f'raid_credit:{rc.NERVII}'
    result = execute_decision(state, rc.GERMANS, {'player_action': {
        'command': 'Raid', 'regions': [], 'sa': 'No SA', 'details': details}})
    assert result['executed']
    assert count_pieces_by_state(state, rc.NERVII, rc.GERMANS, rc.WARBAND, rc.REVEALED) == 0
    assert count_pieces_by_state(state, rc.NERVII, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 1
    assert action_windows.COHORTS not in state
