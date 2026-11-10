"""A March cannot use an earlier group's arrivals to form a later group."""

import json
from types import SimpleNamespace

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_leader_in_region, place_piece
from fs_bot.commands.march import MarchError, execute_march
from fs_bot.commands.sa_enlist import BORROW_KEY
from fs_bot.engine import action_windows, voluntary_removal
from fs_bot.engine.diviciacus import DIVICIACUS_PIECES, force_scope
from fs_bot.engine.execute import _execute_march_moves, execute_decision
from fs_bot.engine.game_engine import ACTION_COMMAND
from fs_bot.engine.march_choices import MARCH_COHORT, MARCH_DROPOFF
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tests.test_action_window_frontends import TIMING_DEFAULTS
from fs_bot.tests.test_ordinary_march_dropoffs import position, row, use_agent
from fs_bot.tools import llm_seat


def two_origins(first_path, destination=rc.TREVERI):
    return {'action': ACTION_COMMAND, 'player_action': {'command': rc.CMD_MARCH,
        'details': {'origins': [rc.MORINI, rc.NERVII],
                    'destinations': [first_path[-1], destination],
                    'routes': {rc.MORINI: first_path, rc.NERVII: [destination]}}}}


def checked(state, result):
    assert result['executed'] and result['errors'] == [], result
    assert action_windows.COHORTS not in state
    assert validate_state(state) == []


@pytest.mark.parametrize('devastated', [False, True])
def test_roman_arrivals_stop_at_their_destination_and_origins_pay_once(devastated):
    state = position()
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA)
    path = [rc.NERVII]
    if devastated:
        state['markers'].setdefault(rc.NERVII, {})[rc.MARKER_DEVASTATED] = True
        path.append(rc.ATREBATES)
    result = execute_decision(state, rc.ROMANS, two_origins(path))
    checked(state, result)
    assert count_pieces(state, rc.NERVII, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA) == 1
    assert result['origin_costs'] == {rc.MORINI: 2, rc.NERVII: 4 if devastated else 2}
    assert state['resources'][rc.ROMANS] == (4 if devastated else 6)


def test_arverni_later_origin_hides_all_but_selects_only_original_warband():
    state = position(rc.ARVERNI)
    place_piece(state, rc.MORINI, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(state, rc.MORINI, rc.ARVERNI, rc.WARBAND)
    place_piece(state, rc.MORINI, rc.ARVERNI, rc.WARBAND, piece_state=rc.SCOUTED)
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.WARBAND, piece_state=rc.SCOUTED)

    def agent(board, faction, request):
        assert request['kind'] != MARCH_COHORT  # No other eligible Warband there.

    state['decision_agent'] = agent
    result = execute_decision(state, rc.ARVERNI, two_origins([rc.NERVII]))
    checked(state, result)
    assert get_leader_in_region(state, rc.NERVII, rc.ARVERNI) == rc.VERCINGETORIX
    assert count_pieces_by_state(state, rc.NERVII, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 2
    assert count_pieces_by_state(state, rc.TREVERI, rc.ARVERNI, rc.WARBAND, rc.REVEALED) == 1


def test_ariovistus_german_command_leaves_prior_arrivals_in_place():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=41)
    state['resources'][rc.GERMANS] = 6
    place_piece(state, rc.MORINI, rc.GERMANS, rc.WARBAND, 2)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND)
    result = execute_decision(state, rc.GERMANS, two_origins([rc.NERVII]))
    checked(state, result)
    assert count_pieces(state, rc.NERVII, rc.GERMANS, rc.WARBAND) == 2
    assert count_pieces(state, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 1
    assert result['origin_costs'] == {rc.MORINI: 1, rc.NERVII: 1}


@pytest.mark.parametrize('removed', [None, 'marched_pieces'])
def test_dropoff_and_resident_removals_are_distinct_after_harassment(removed):
    state = position()
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 3)
    leave = row(rc.ROMANS, rc.AUXILIA, rc.HIDDEN, 1)
    removals = []

    def agent(board, faction, request):
        if request['kind'] == MARCH_DROPOFF:
            return {'dropoffs': [leave]}
        if request['kind'] == voluntary_removal.KIND:
            window = request['window']
            if not removals and window['stage'] == 'march_origin' and window['region'] == rc.NERVII:
                choices = {c.get('cohort'): c for c in request['options']
                           if c['region'] == rc.NERVII and c['piece_type'] == rc.AUXILIA}
                assert {cohort: c['max_count'] for cohort, c in choices.items()} == {
                    None: 1, 'marched_pieces': 1}
                removals.append(voluntary_removal.operation(choices[removed]))
                return {'operations': removals}
            return {'done': True}

    agent.supports_action_windows = True
    use_agent(state, agent)
    result = execute_decision(state, rc.ROMANS, two_origins([rc.NERVII, rc.ATREBATES]))
    checked(state, result)
    assert len(removals) == 1
    assert result['total_cost'] == 4
    assert result['marches'][0]['dropoffs'][0]['pieces'] == [leave]
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(state, rc.NERVII, rc.ROMANS, rc.AUXILIA) == int(removed is None)
    assert count_pieces(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA) == int(removed is not None)


@pytest.mark.parametrize('remove_arrived', [False, True])
def test_diviciacus_arrival_cannot_supply_the_later_origins_physical_owner_choice(remove_arrived):
    state = position()
    place_piece(state, rc.MORINI, rc.AEDUI, rc.WARBAND, piece_state=rc.SCOUTED)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA)
    if remove_arrived:
        place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA)
    removed = []

    def agent(board, faction, request):
        assert request['kind'] != DIVICIACUS_PIECES  # Only the Roman counter can March.
        if request['kind'] == voluntary_removal.KIND:
            if remove_arrived and not removed and request['window']['stage'] == 'march_origin':
                for option in request['options']:
                    if option.get('cohort') == 'marched_pieces':
                        removed.append(voluntary_removal.operation(option))
                        return {'operations': removed}
            return {'done': True}

    agent.supports_action_windows = True
    state['decision_agent'] = agent
    with (force_scope(state, rc.ROMANS, [rc.MORINI, rc.NERVII]),
          action_windows.scope(state, actor=rc.ROMANS)):
        result = _execute_march_moves(state, rc.ROMANS, [
            {'origin': rc.MORINI, 'path': [rc.NERVII]},
            {'origin': rc.NERVII, 'path': [rc.TREVERI], 'group': {rc.AUXILIA: 1}},
        ])
    checked(state, result)
    assert count_pieces_by_state(state, rc.NERVII, rc.AEDUI, rc.WARBAND, rc.HIDDEN) == 1
    assert len(removed) == int(remove_arrived)
    assert count_pieces(state, rc.NERVII, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(state, rc.TREVERI, rc.AEDUI, rc.WARBAND) == 0
    assert count_pieces(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA) == 1


def test_enlist_bot_preserves_owners_across_later_groups_from_one_origin():
    state = position(rc.BELGAE)
    state['non_player_factions'].add(rc.BELGAE)
    place_piece(state, rc.MORINI, rc.GERMANS, rc.WARBAND)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 2)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND)
    state[BORROW_KEY] = {'pieces': {rc.MORINI: {rc.HIDDEN: 1}, rc.NERVII: {rc.HIDDEN: 2}}}
    result = _execute_march_moves(state, rc.BELGAE, [
        {'origin': rc.MORINI, 'path': [rc.NERVII]},
        {'origin': rc.NERVII, 'path': [rc.ATREBATES], 'group': {rc.WARBAND: 2, 'german_warbands': 2}},
        {'origin': rc.NERVII, 'path': [rc.TREVERI], 'group': {rc.WARBAND: 2, 'german_warbands': 1}},
    ])
    state.pop(BORROW_KEY)
    checked(state, result)
    assert result['origin_costs'] == {rc.MORINI: 1, rc.NERVII: 1}
    assert count_pieces(state, rc.NERVII, rc.GERMANS, rc.WARBAND) == 1
    assert count_pieces(state, rc.ATREBATES, rc.GERMANS, rc.WARBAND) == 2
    assert count_pieces(state, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 0
    assert count_pieces(state, rc.TREVERI, rc.BELGAE, rc.WARBAND) == 1


def test_group_that_returns_to_its_origin_is_unavailable_to_a_later_group():
    state = position()
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 3)
    result = _execute_march_moves(state, rc.ROMANS, [
        {'origin': rc.MORINI, 'path': [rc.NERVII, rc.MORINI], 'group': {rc.AUXILIA: 2}},
        {'origin': rc.MORINI, 'path': [rc.NERVII]},
    ])
    checked(state, result)
    assert result['origin_costs'] == {rc.MORINI: 2}
    assert count_pieces(state, rc.MORINI, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(state, rc.NERVII, rc.ROMANS, rc.AUXILIA) == 1


@pytest.mark.parametrize('requested', [1, 2])
def test_explicit_march_command_uses_original_visibility_and_capacity(requested):
    state = position(rc.AEDUI)
    place_piece(state, rc.MORINI, rc.AEDUI, rc.WARBAND, 2)
    place_piece(state, rc.NERVII, rc.AEDUI, rc.WARBAND, piece_state=rc.SCOUTED)
    origins = [
        {'origin': rc.MORINI, 'groups': [({rc.WARBAND: 2}, [rc.NERVII])]},
        {'origin': rc.NERVII, 'groups': [({rc.WARBAND: requested}, [rc.TREVERI])]},
    ]
    if requested == 1:
        result = execute_march(state, rc.AEDUI, origins)
        assert result['total_cost'] == 2
        assert count_pieces_by_state(state, rc.TREVERI, rc.AEDUI, rc.WARBAND, rc.REVEALED) == 1
    else:
        with pytest.raises(MarchError, match='Only 1 Aedui Warband in Nervii'):
            execute_march(state, rc.AEDUI, origins)
        assert count_pieces(state, rc.TREVERI, rc.AEDUI, rc.WARBAND) == 0
    assert count_pieces_by_state(state, rc.NERVII, rc.AEDUI, rc.WARBAND, rc.HIDDEN) == 2
    assert action_windows.COHORTS not in state
    assert validate_state(state) == []


def test_arrived_removal_window_survives_durable_reload_and_replay(tmp_path):
    state = position()
    for faction in state['eligibility']:
        state['eligibility'][faction] = rc.ELIGIBLE if faction == rc.ROMANS else rc.INELIGIBLE
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA)
    path = tmp_path / 'live' / 'save.json'
    path.parent.mkdir()
    save_game(state, path, meta={'seat': rc.ROMANS, 'scenario': state['scenario'], 'seed': 41}, log=[])
    args = SimpleNamespace(dir=str(path.parent), output_dir=str(tmp_path / 'replay'))
    assert llm_seat.cmd_play(args) == 0
    initial, _, _ = load_game(path, validate=True)

    parked = None
    for _ in range(60):
        current, meta, log = load_game(path, validate=True)
        pending = meta['assistant_session']['pending']
        if not pending:
            break
        request = decode(pending['request'])
        kind = request['kind']
        if kind == 'turn':
            response = two_origins([rc.NERVII])
        elif (parked is None and kind == voluntary_removal.KIND
              and request['window'].get('stage') == 'march_origin'
              and request['window'].get('region') == rc.NERVII):
            assert encode(current) == encode(initial) and not log
            assert action_windows.COHORTS not in decode(pending['board'])
            parked = next(c for c in request['options'] if c.get('cohort') == 'marched_pieces')
            assert parked['max_count'] == 2
            assert llm_seat.cmd_play(args) == 0
            assert load_game(path)[1]['assistant_session']['pending'] == pending
            response = {'operations': [voluntary_removal.operation(parked)]}
        else:
            response = TIMING_DEFAULTS[kind]
        assert llm_seat.cmd_submit(SimpleNamespace(
            dir=args.dir, decision_id=pending['id'], response=json.dumps(response))) == 0
    else:
        pytest.fail('The March did not complete')

    assert parked is not None
    assert count_pieces(current, rc.NERVII, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(current, rc.TREVERI, rc.ROMANS, rc.AUXILIA) == 1
    assert llm_seat.cmd_replay(args) == 0
    replayed, _, replay_log = load_game(tmp_path / 'replay' / 'save.json', validate=True)
    assert encode(replayed) == encode(current) and replay_log == log
