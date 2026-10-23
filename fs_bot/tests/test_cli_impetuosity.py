"""Card 72's real menus select only the one permitted Hidden group."""
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece
from fs_bot.cli.free_actions import collect_free_action
from fs_bot.cli.menus import set_board_hook
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state


REQUEST = {'kind': 'free_action', 'request_type': 'impetuosity_march'}


def _state():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=7)
    state['non_player_factions'] = set()
    return state


def _collect(state, lines):
    before = encode(state)
    output = io.StringIO()
    result = collect_free_action(state, rc.BELGAE, REQUEST,
        io.StringIO('\n'.join(lines) + '\n'), output)
    assert encode(state) == before
    return result, output.getvalue()


@pytest.mark.parametrize('destination', [rc.MORINI, rc.NERVII])
def test_human_can_select_adjacent_or_in_place_hidden_group(destination):
    state = _state()
    place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND, 3)
    place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND, 2,
                piece_state=rc.REVEALED)
    place_piece(state, rc.MORINI, rc.BELGAE, rc.LEADER,
                leader_name=rc.AMBIORIX)
    response, shown = _collect(state,
        ['Plan the action', rc.MORINI, destination, '2'])
    assert response == {'origin': rc.MORINI, 'destination': destination,
                        'warbands': 2}
    assert 'no Leader' in shown
    assert '  3) 3\n' in shown
    assert '  4) 4\n' not in shown


def test_invalid_count_and_board_command_preserve_the_pending_choice():
    state = _state()
    place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND, 2)
    calls = []
    set_board_hook(lambda: calls.append('board'))
    try:
        response, shown = _collect(state, ['Plan the action', 'board',
            rc.MORINI, rc.MORINI, '3', '0', 'b', '2'])
    finally:
        set_board_hook(None)
    assert response['warbands'] == 2
    assert calls == ['board', 'board']
    assert "got '3'" in shown and "got '0'" in shown


@pytest.mark.parametrize('choice,response', [
    ('Use bot default', {'use_default': True}), ('Decline', {'decline': True})])
def test_reactive_march_requires_explicit_default_or_decline(choice, response):
    state = _state()
    agent = make_cli_reactive([rc.BELGAE], io.StringIO(choice + '\n'), io.StringIO())
    assert agent(state, rc.BELGAE, REQUEST) == response


def test_no_hidden_group_returns_to_explicit_menu():
    state = _state()
    place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND, 2,
                piece_state=rc.REVEALED)
    response, shown = _collect(state, ['Plan the action', 'Decline'])
    assert response == {'decline': True}
    assert 'No Hidden-Warband group can March' in shown


def test_eof_does_not_select_default_march():
    state = _state()
    agent = make_cli_reactive([rc.BELGAE], io.StringIO(''), io.StringIO())
    with pytest.raises(EOFError):
        agent(state, rc.BELGAE, REQUEST)
