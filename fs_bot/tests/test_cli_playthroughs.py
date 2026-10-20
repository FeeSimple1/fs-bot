"""Complete games through real terminal menus for every scenario/seat.

These complement engine-plan fuzzing: stdin chooses actual menu labels,
plays Commands (rather than passing throughout), requests the board, makes
one invalid input, and replays the saved human decisions to the same board.
They are functional journeys, not strategic play-quality measurements.
"""
import io
import re
import pytest
from fs_bot import rules_consts as rc
from fs_bot.cli.app import main, get_assignable_factions
from fs_bot.state.serialize import load_game
from fs_bot.tests.test_cli_game import _digest_state


class MenuPlayer:
    def __init__(self, output):
        self.output = output
        self.position = 0
        self.reads = 0
        self.failed_plan = False
        self.region_pick = 0
        self.replies = []
        self.probed_input = False

    def readline(self):
        self.reads += 1
        assert self.reads < 3000, self.output.getvalue()[-2500:]
        text = self.output.getvalue()
        delta, self.position = text[self.position:], len(text)
        if self.replies:
            return self.replies.pop(0) + '\n'
        if 'Your turn is still pending' in delta:
            self.failed_plan = True
        options = re.findall(r'^\s*(\d+)\) (.*)$', delta, re.M)
        if options:
            labels = {label.strip(): number for number, label in options}
            if 'Choose your action:' in delta:
                preferred = (['Pass'] if self.failed_plan else [
                    'Command (no Special Ability)',
                    'Limited Command (one region, no SA)', 'Pass'])
                self.failed_plan = False
            elif 'Which Command?' in delta:
                preferred = ['Seize', 'Raid']
            elif 'Raid in which' in delta and '(done)' not in labels:
                self.region_pick += 1
                return options[(self.region_pick - 1) % len(options)][0] + '\n'
            else:
                # Exercise the explicit delegation menu for reactive Event
                # grants. Blindly choosing the first paid Frumentum action
                # can repeat an unaffordable March forever; ordinary turns
                # above still make actual human Seize/Raid plans.
                preferred = ['Use bot default for the next action',
                             'Use bot default', 'gain 1 Resource', '(done)',
                             'No Retreat (take Losses in place)',
                             '(default order for the rest)']
            reply = next((labels[x] for x in preferred if x in labels), options[0][0])
            if 'Choose your action:' in delta and not self.probed_input:
                self.probed_input = True
                self.replies = ['board', reply]
                return 'not-a-menu-choice\n'
            return reply + '\n'
        if '[y/' in delta or '[Y/' in delta or 'y/n' in delta:
            return 'n\n'
        return '\n'


SEATS = [(scenario, seat) for scenario in rc.ALL_SCENARIOS
         for seat in get_assignable_factions(scenario)]


@pytest.mark.parametrize('scenario,seat', SEATS)
def test_full_menu_command_game_replays(tmp_path, scenario, seat):
    saved = tmp_path / 'played.json'
    output = io.StringIO()
    player = MenuPlayer(output)
    code = main(['--scenario', scenario, '--seed', '13', '--bots',
                 ','.join(f for f in get_assignable_factions(scenario) if f != seat),
                 '--save', str(saved)], stdin=player, stdout=output)
    assert code == 0, output.getvalue()[-1500:]
    assert 'Game ended' in output.getvalue()
    assert "got 'not-a-menu-choice'" in output.getvalue()
    state, _, log = load_game(saved, validate=True)
    commands = [entry for entry in log if entry.get('player_action')
                and not entry.get('reactive')]
    assert commands, 'The menu journey must execute a Command, not only Pass'
    assert all(entry['player_action']['command'] in ('Seize', 'Raid') for entry in commands)

    replayed = tmp_path / 'replayed.json'
    replay_output = io.StringIO()
    replay_code = main(['--replay', str(saved), '--save', str(replayed)],
                       stdin=io.StringIO(''), stdout=replay_output)
    assert replay_code == 0, replay_output.getvalue()[-1500:]
    assert 'Game ended' in replay_output.getvalue()
    replay_state, _, _ = load_game(replayed, validate=True)
    assert _digest_state(replay_state) == _digest_state(state)
