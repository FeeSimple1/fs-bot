"""FE7-01 through generic Event March, the terminal, and a saved session."""

from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.free_actions import collect_free_action
from fs_bot.commands.march import MarchError, execute_march, march_from_origin
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT, _action_transaction
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def position(edition='second-edition'):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=7)
    state.update(current_card=51, current_card_id=51, next_card=49,
                 card_edition=edition, non_player_factions=set())
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    place_piece(state, rc.TREVERI, rc.AEDUI, rc.WARBAND, 4)
    return state


def play(state):
    return execute_decision(state, rc.BELGAE, {'action': ACTION_EVENT, 'player_action': {
        'command': rc.FIRST_DID_EVENT, 'details': {'card_id': 51,
        'text_preference': rc.EVENT_SHADED,
        'event_params': {'region': rc.TREVERI, 'count': 4}}}})


def action(plan):
    return {'command': rc.CMD_MARCH, 'sa': 'No SA', 'details': {'march_plan': plan}}


def move(destination, number):
    return {'origin': rc.TREVERI, 'path': [destination], 'group': {rc.WARBAND: number}}


def split(format_='extra_groups', destination=rc.SEQUANI):
    if format_ == 'explicit_moves':
        return action({'explicit_moves': [move(rc.NERVII, 2), move(destination, 2)]})
    return action({'origins': [rc.TREVERI], 'destinations': [rc.NERVII],
                   'routes': {rc.TREVERI: [rc.NERVII]}, 'groups': {rc.TREVERI: {rc.WARBAND: 2}},
                   'extra_groups': [{'origin': rc.TREVERI, 'route': [destination],
                                     'group': {rc.WARBAND: 2}}]})


def answer(state, response):
    state['decision_agent'] = lambda board, faction, request: (
        response if request['kind'] == 'free_action' else None)


def counts(state):
    return tuple(count_pieces(state, r, rc.GERMANS, rc.WARBAND)
                 for r in (rc.TREVERI, rc.NERVII, rc.SEQUANI))


def check(state):
    assert validate_state(state) == []
    assert check_structural_integrity(state) == []


@pytest.mark.parametrize('format_,edition,destination', [
    ('extra_groups', 'second-edition', rc.SEQUANI),
    ('explicit_moves', 'legacy', rc.SEQUANI),
    ('explicit_moves', 'second-edition', rc.NERVII),
])
def test_surus_rejects_two_moving_groups_and_rolls_back_replacements(format_, edition, destination):
    state = position(edition)
    initial = encode(board_copy(state))
    answer(state, split(format_, destination))

    result = play(state)

    assert not result['executed'] and result['rejected'], result
    assert 'one moving group per origin' in result['reason']
    assert encode(board_copy(state)) == initial
    check(state)


@pytest.mark.parametrize('number', [0, 2, 4])
def test_surus_allows_one_group_or_a_stay(number):
    state = position()
    destinations = [rc.NERVII] if number else []
    answer(state, action({'origins': [rc.TREVERI], 'destinations': destinations,
                          'routes': {rc.TREVERI: destinations},
                          'groups': {rc.TREVERI: {rc.WARBAND: number}}}))

    result = play(state)

    assert result['executed'] and result['free_actions'][0]['result']['executed'], result
    assert counts(state) == (4 - number, number, 0)
    check(state)


def test_explicit_stay_does_not_count_as_a_second_moving_group():
    state = position()
    answer(state, action({'explicit_moves': [move(rc.NERVII, 2),
                                             {'origin': rc.TREVERI, 'path': [], 'stay': True}]}))

    result = play(state)

    assert result['executed'], result
    assert counts(state) == (2, 2, 0)
    check(state)


def test_surus_terminal_offers_a_subset_without_a_second_group():
    state = position()
    later_input = 'y\nSequani\n1\n'
    stdin = StringIO('Plan the action\nMarch\nTreveri\nNervii\n3\n' + later_input)
    stdout = StringIO()
    state['decision_agent'] = lambda board, faction, request: (
        collect_free_action(board, faction, request, stdin, stdout)
        if request['kind'] == 'free_action' else None)

    result = play(state)

    assert result['executed'], result
    assert 'March a SECOND group' not in stdout.getvalue()
    assert stdin.read() == later_input
    assert counts(state) == (2, 2, 0)
    check(state)


def test_surus_save_resume_rejects_split_then_replays_corrected_choice(tmp_path):
    state = position()
    initial = encode(board_copy(state))

    def session_for(board, meta, log):
        session = SeatSession(board, meta, log, HumanTurnDisplay(StringIO()))
        board['decision_agent'] = lambda b, f, r: (
            session.reactive(b, f, r) if r['kind'] == 'free_action' else None)
        return session

    def attempt(session):
        def driver(*args):
            pass

        driver.transaction_checkpoint = session.checkpoint
        driver.transaction_restore = session.restore
        with _action_transaction(session.state, driver):
            return play(session.state)

    session = session_for(state, {'seat': rc.BELGAE}, [])
    with pytest.raises(DecisionPending):
        attempt(session)
    pending = deepcopy(session.data['pending'])
    assert decode(pending['request'])['acting_faction'] == rc.GERMANS
    assert encode(board_copy(state)) == initial

    path = tmp_path / 'surus-pending.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session_for(restored, meta, log)
    resumed.import_inbox({'decision_id': pending['id'], 'response': split()})
    with pytest.raises(DecisionPending):
        attempt(resumed)
    assert resumed.data['pending'] == pending
    assert 'one moving group per origin' in resumed.error
    assert encode(board_copy(restored)) == initial
    assert not log

    resumed.import_inbox({'decision_id': pending['id'],
                          'response': action({'explicit_moves': [move(rc.NERVII, 2)]})})
    result = attempt(resumed)
    resumed.finish()
    assert result['executed'] and len(log) == 1
    assert counts(restored) == (2, 2, 0)
    replay = decode(initial)
    answer(replay, decode(log[0]['assistant_response']))
    assert play(replay) == result
    assert encode(board_copy(replay)) == encode(board_copy(restored))
    check(restored)


@pytest.mark.parametrize('api', ['single_origin', 'repeated_origin'])
def test_movement_api_rejects_split_before_hiding_or_moving(api):
    state = position()
    place_piece(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, 4, piece_state=rc.REVEALED)
    groups = [({rc.WARBAND: 2}, [destination]) for destination in (rc.NERVII, rc.SEQUANI)]
    initial = encode(state)

    with pytest.raises(MarchError, match='one moving group per origin'):
        if api == 'single_origin':
            march_from_origin(state, rc.GERMANS, rc.TREVERI, groups, free=True)
        else:
            execute_march(state, rc.GERMANS,
                          [{'origin': rc.TREVERI, 'groups': [group]} for group in groups], free=True)

    assert encode(state) == initial
    check(state)
