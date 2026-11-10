"""Ordinary March offers exact transit choices before the next departure."""
from copy import deepcopy
from io import StringIO
import json
from types import SimpleNamespace

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_leader_in_region, place_piece
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.diviciacus import force_scope
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_COMMAND, get_sop_factions
from fs_bot.engine.march_choices import MARCH_COHORT, MARCH_DROPOFF
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tests.test_action_window_frontends import leave_timing_unchanged
from fs_bot.tools import llm_seat
from fs_bot.tools.seat_session import SeatSession


def position(faction=rc.ROMANS):
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=41)
    state.update(current_card=4, current_card_id=4, played_cards=[4], deck=[], next_card=None)
    state['non_player_factions'] = set(get_sop_factions(state)) - {faction}
    state['resources'][faction] = 10
    return state


def march(path, group=None):
    details = {'origins': [rc.MORINI], 'destinations': [path[-1]], 'routes': {rc.MORINI: path}}
    if group is not None:
        details['groups'] = {rc.MORINI: group}
    return {'action': ACTION_COMMAND, 'player_action': {'command': rc.CMD_MARCH, 'details': details}}


def run(state, faction, path, group=None):
    result = execute_decision(state, faction, march(path, group))
    assert result['executed'] and not result['errors'], result
    assert result['origin_costs'] == {rc.MORINI: 2 if faction == rc.ROMANS else 1}
    assert validate_state(state) == []
    return result['marches'][0]


def row(faction, piece, visibility, count):
    return dict(faction=faction, piece_type=piece, piece_state=visibility, count=count)


def use_agent(state, agent):
    agent.supports_march_dropoffs = True
    state['decision_agent'] = agent


def test_harassment_uses_the_remainder_and_later_offer_uses_actual_survivors():
    state = position()
    place_piece(state, rc.MORINI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 3)
    requests = []
    leave = row(rc.ROMANS, rc.AUXILIA, rc.HIDDEN, 1)

    def agent(board, faction, request):
        if request['kind'] == MARCH_DROPOFF:
            requests.append(deepcopy(request))
            return {'dropoffs': [leave]}
        return None

    use_agent(state, agent)
    result = run(state, rc.ROMANS, [rc.NERVII, rc.ATREBATES, rc.CARNUTES])
    assert [q['region'] for q in requests] == [rc.NERVII, rc.ATREBATES]
    assert requests[0]['pieces'] == [row(rc.ROMANS, rc.LEADER, None, 1),
                                     row(rc.ROMANS, rc.AUXILIA, rc.HIDDEN, 4)]
    assert requests[1]['pieces'] == [row(rc.ROMANS, rc.AUXILIA, rc.HIDDEN, 2)]
    assert count_pieces(state, rc.NERVII, rc.ROMANS, rc.AUXILIA) == 3  # two residents, one dropped
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 1
    assert get_leader_in_region(state, rc.CARNUTES, rc.ROMANS) == rc.CAESAR
    assert result['dropoffs'] == [dict(region=region, step=i, pieces=[leave])
                                  for i, region in enumerate((rc.NERVII, rc.ATREBATES), 1)]


def test_leaving_caesar_can_shorten_a_route_when_the_next_hop_is_still_legal():
    state = position()
    place_piece(state, rc.MORINI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.LEGION, from_legions_track=True)
    calls = []

    def agent(board, faction, request):
        if request['kind'] == MARCH_DROPOFF:
            calls.append(request['region'])
            return {'dropoffs': [row(rc.ROMANS, rc.LEADER, None, 1)]}
        return None

    use_agent(state, agent)
    result = run(state, rc.ROMANS, [rc.NERVII, rc.ATREBATES, rc.CARNUTES])
    assert calls == [rc.NERVII]
    assert get_leader_in_region(state, rc.NERVII, rc.ROMANS) == rc.CAESAR
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.LEGION) == 1
    assert result['final_region'] == rc.ATREBATES


def test_arverni_menu_leaves_a_revealed_counter_and_keeps_vercingetorix():
    state = position(rc.ARVERNI)
    place_piece(state, rc.MORINI, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(state, rc.MORINI, rc.ARVERNI, rc.WARBAND)
    place_piece(state, rc.MORINI, rc.ARVERNI, rc.WARBAND, piece_state=rc.SCOUTED)
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.WARBAND, 2)
    stdin = StringIO('board\nLeave Arverni Revealed Warband (up to 1)\nKeep the remaining pieces moving\n')
    stdout = StringIO()
    agent = make_cli_reactive({rc.ARVERNI}, stdin, stdout)
    agent.supports_action_windows = False
    state['decision_agent'] = agent
    result = run(state, rc.ARVERNI, [rc.NERVII, rc.ATREBATES])
    assert result['dropoffs'][0]['pieces'] == [row(rc.ARVERNI, rc.WARBAND, rc.REVEALED, 1)]
    assert 'Leave Arverni Vercingetorix' not in stdout.getvalue()
    assert 'before Marching to Atrebates' in stdout.getvalue()
    assert count_pieces_by_state(state, rc.NERVII, rc.ARVERNI, rc.WARBAND, rc.REVEALED) == 1
    assert count_pieces_by_state(state, rc.ATREBATES, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 1
    assert get_leader_in_region(state, rc.ATREBATES, rc.ARVERNI) == rc.VERCINGETORIX


@pytest.mark.parametrize('loan_at_origin', [False, True])
def test_diviciacus_dropoffs_keep_physical_owner_and_exclude_residents(loan_at_origin):
    state = position()
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.NERVII, rc.AEDUI, rc.WARBAND, 3)
    if loan_at_origin:
        place_piece(state, rc.MORINI, rc.AEDUI, rc.WARBAND)
    expected = (row(rc.AEDUI, rc.WARBAND, rc.HIDDEN, 1) if loan_at_origin else
                row(rc.ROMANS, rc.AUXILIA, rc.HIDDEN, 1))
    offers = []
    regions = [rc.MORINI, rc.NERVII] if loan_at_origin else [rc.NERVII]

    def agent(board, faction, request):
        if request['kind'] == MARCH_DROPOFF:
            offers.append(deepcopy(request['pieces']))
            return {'dropoffs': [expected]}
        return None

    use_agent(state, agent)
    with force_scope(state, rc.ROMANS, regions):
        result = run(state, rc.ROMANS, [rc.NERVII, rc.ATREBATES])
    assert offers == [[row(rc.ROMANS, rc.AUXILIA, rc.HIDDEN, 2)]
                       + ([expected] if loan_at_origin else [])]
    assert result['dropoffs'][0]['pieces'] == [expected]
    assert count_pieces(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND) == 0
    assert count_pieces(state, rc.NERVII, rc.AEDUI, rc.WARBAND) == 3 + loan_at_origin
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 1 + loan_at_origin


@pytest.mark.parametrize('force_stop', [False, True])
def test_no_dropoff_request_when_the_group_cannot_continue(force_stop):
    state = position()
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 2 if force_stop else 1)
    if force_stop:
        state['markers'].setdefault(rc.NERVII, {})[rc.MARKER_DEVASTATED] = True
    calls = []

    def agent(board, faction, request):
        calls.append(request['kind'])
        return None

    use_agent(state, agent)
    result = run(state, rc.ROMANS, [rc.NERVII, rc.ATREBATES])
    assert MARCH_DROPOFF not in calls
    assert result['final_region'] == (rc.NERVII if force_stop else rc.ATREBATES)


@pytest.mark.parametrize('legacy', [False, True])
def test_durable_choices_survive_invalid_submission_reload_and_replay(tmp_path, monkeypatch, legacy):
    state = position()
    for faction in state['eligibility']:
        state['eligibility'][faction] = rc.ELIGIBLE if faction == rc.ROMANS else rc.INELIGIBLE
    place_piece(state, rc.MORINI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 3)
    args = SimpleNamespace(dir=str(tmp_path / 'live'), output_dir=str(tmp_path / 'replay'))
    path = tmp_path / 'live' / 'save.json'
    path.parent.mkdir()
    save_game(state, path, meta={'seat': rc.ROMANS, 'scenario': state['scenario'], 'seed': 41}, log=[])

    def submit(response, decision_id=None):
        assert llm_seat.cmd_submit(SimpleNamespace(
            dir=args.dir, decision_id=decision_id, response=json.dumps(response))) == 0
        leave_timing_unchanged(args)

    def saved_pending():
        board, meta, log = load_game(path, validate=True)
        return board, meta['assistant_session']['pending'], log

    if legacy:
        monkeypatch.setattr(SeatSession, 'supports_march_dropoffs', False)
    assert llm_seat.cmd_play(args) == 0
    initial, _, _ = saved_pending()
    submit(march([rc.NERVII, rc.ATREBATES, rc.CARNUTES]))
    if not legacy:
        board, first, log = saved_pending()
        request = decode(first['request'])
        assert request['kind'] == MARCH_DROPOFF and request['region'] == rc.NERVII
        assert count_pieces(decode(first['board']), rc.NERVII, rc.ROMANS, rc.AUXILIA) == 3
        assert encode(board) == encode(initial) and not log
        leave = row(rc.ROMANS, rc.AUXILIA, rc.HIDDEN, 1)
        submit({'dropoffs': [dict(leave, count=True)]}, first['id'])
        assert saved_pending()[1] == first
        submit({'dropoffs': [leave]}, first['id'])
        board, second, log = saved_pending()
        assert encode(board) == encode(initial) and not log
        assert decode(second['request'])['pieces'] == [dict(leave, count=2)]
        assert llm_seat.cmd_play(args) == 0 and saved_pending()[1] == second
        submit({'dropoffs': [leave, leave]}, second['id'])
        assert saved_pending()[1] == second
        submit({'dropoffs': [leave]}, second['id'])
    final, pending, log = saved_pending()
    assert pending is None
    assert count_pieces(final, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == (3 if legacy else 1)
    dropoffs = [entry for entry in log if entry.get('reactive') == MARCH_DROPOFF]
    assert len(dropoffs) == (0 if legacy else 2)
    assert all(entry.get('reactive') != MARCH_COHORT for entry in log)
    monkeypatch.setattr(SeatSession, 'supports_march_dropoffs', True)
    assert llm_seat.cmd_replay(args) == 0
    replayed, _, replay_log = load_game(tmp_path / 'replay' / 'save.json', validate=True)
    assert encode(replayed) == encode(final) and replay_log == log
