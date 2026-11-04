"""Board inspection must follow the detached board used for Command choices."""
import io
import re
from unittest.mock import patch

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces
from fs_bot.cli import human_plan, menus
from fs_bot.cli.display import format_board
from fs_bot.engine.game_engine import ACTION_COMMAND_SA, start_game
from fs_bot.state.serialize import encode
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import validate_state


@pytest.mark.parametrize('inspection', ['b', 'board'])
@pytest.mark.parametrize('action_windows', [False, True])
def test_build_before_march_inspects_post_build_preview(inspection, action_windows):
    state = setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=13)
    state['non_player_factions'] = {rc.ARVERNI, rc.AEDUI, rc.BELGAE}
    start_game(state)
    if action_windows:
        state['_cli_action_windows'] = True
    before = encode(state)
    out = io.StringIO()
    observations = {}
    original = human_plan._collect_command_plan

    def measured(board, faction, command, *args, **kwargs):
        assert command == 'March'
        assert count_pieces(board, rc.ATREBATES, rc.ROMANS, rc.FORT) == 1
        assert board['resources'][rc.ROMANS] == 6
        assert validate_state(board) == []
        observations['expected'] = format_board(board)
        return original(board, faction, command, *args, **kwargs)

    class Player:
        pos = 0
        picked_region = False
        inspected = False

        def readline(self):
            text = out.getvalue()
            delta, self.pos = text[self.pos:], len(text)
            if self.inspected:
                observations['displayed'] = delta
                return ''  # Deliberately exit the menu after inspecting it.
            options = re.findall(r'^\s*(\d+)\) (.*)$', delta, re.M)
            if 'March OUT of which Region' in delta:
                self.inspected = True
                return inspection + '\n'
            if 'Build in which Region' in delta:
                wanted = '(done)' if self.picked_region else rc.ATREBATES
                self.picked_region = True
            elif 'Which accompanying Command?' in delta:
                wanted = 'March'
            else:
                wanted = next((label for label in (
                    'Finish voluntary removal', 'Special Activity first, then Command',
                    'Build', 'Place a Fort', 'place a Fort', 'Skip this Build option')
                    if any(option[1] == label for option in options)), None)
            match = next((number for number, label in options if label == wanted), None)
            assert match is not None, delta
            return match + '\n'

    outer = lambda: out.write(format_board(state))
    previous = menus._BOARD_HOOK[0]
    menus.set_board_hook(outer)
    try:
        with patch.object(human_plan, '_collect_command_plan', measured):
            with pytest.raises(EOFError):
                human_plan.collect_player_action(
                    state, rc.ROMANS, ACTION_COMMAND_SA, Player(), out)
        assert menus._BOARD_HOOK[0] is outer
    finally:
        menus.set_board_hook(previous)
    assert observations['expected'] in observations['displayed']
    assert format_board(state) not in observations['displayed']
    assert encode(state) == before
