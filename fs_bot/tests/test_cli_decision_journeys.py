"""Real terminal journeys through tactical decisions and scenario transitions.

The small legal-position fixtures select the cards and pieces needed to reach
rare interactions. Menus, action execution, reactions, saves and replay are
real; no game-resolution function is replaced. Full scenario journeys remain
in test_cli_playthroughs.py.
"""
import copy
import io
import re

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.cards.card_text import get_card_text
from fs_bot.cli import app
from fs_bot.state.serialize import load_game
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tests.test_cli_game import _digest_state


class TacticalPlayer:
    """Choose labels from real prompts; optionally stop at a Battle reaction."""

    def __init__(self, output, *, interrupt_retreat=False, commands_done=0):
        self.output = output
        self.position = 0
        self.reads = 0
        self.faction = None
        self.commands_done = commands_done
        self.interrupt_retreat = interrupt_retreat
        self.board_pending = None
        self.contexts = []

    def readline(self):
        self.reads += 1
        assert self.reads < 500, self.output.getvalue()[-3000:]
        text = self.output.getvalue()
        delta, self.position = text[self.position:], len(text)
        if self.board_pending is not None:
            answer, self.board_pending = self.board_pending, None
            return answer + '\n'
        match = re.search(r'You are (.*?), the ', delta)
        if match:
            self.faction = match.group(1)
        options = re.findall(r'^\s*(\d+)\) (.*)$', delta, re.M)
        labels = {label.strip(): number for number, label in options}
        if 'Retreat?' in delta and self.interrupt_retreat:
            raise KeyboardInterrupt
        if 'Choose your action:' in delta:
            self.contexts.append(delta)
            preferred = (['Command (no Special Ability)']
                         if self.faction == rc.ROMANS and self.commands_done < 2
                         else ['Pass'])
        elif 'Which Command?' in delta:
            preferred = ['March' if self.commands_done == 0 else 'Battle']
            self.commands_done += 1
        elif 'March OUT' in delta:
            preferred = [rc.PROVINCIA, '(done)']
        elif 'along which route?' in delta:
            preferred = [rc.SEQUANI]
        elif 'Battle in which' in delta:
            preferred = [rc.SEQUANI, '(done)']
        elif 'Defender in' in delta:
            preferred = [rc.ARVERNI]
        else:
            preferred = ['No Retreat (take Losses in place)', '(done)']
        if labels:
            answer = next((labels[label] for label in preferred if label in labels),
                          options[0][0])
            # Board inspection during both planning and actual defending must
            # preserve the pending menu and not consume an action or die roll.
            if 'along which route?' in delta or 'Retreat?' in delta:
                self.board_pending = answer
                return 'board\n'
            return answer + '\n'
        if 'March the Leader' in delta:
            return 'y\n'
        return 'n\n'


def _combat_position():
    # §§3.2.2 and 3.2.4: a paid Roman March followed on a later eligible
    # card by Battle, with both attacking and defending factions human.
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=23)
    state['card_edition'] = 'second-edition'
    state['deck'] = [1, 2, 3, 4]
    state['resources'] = {f: 20 for f in state['resources']}
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION, 3,
                from_legions_track=True)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEADER,
                leader_name=rc.CAESAR)
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 12)
    assert validate_state(state) == []
    return state


def _install_position(monkeypatch, state):
    # Replay normally rebuilds scenario+seed. Rebuild this same legal test
    # position instead, without replacing start_game or any resolution path.
    monkeypatch.setattr(app, 'setup_scenario', lambda *args, **kwargs: copy.deepcopy(state))


def _play(path, *, output=None, player=None, load=False,
          scenario=rc.SCENARIO_GREAT_REVOLT):
    output = output or io.StringIO()
    player = player or TacticalPlayer(output)
    args = (['--load', str(path)] if load else
            ['--scenario', scenario, '--seed', '23',
             '--card-edition', 'second-edition', '--bots', ''])
    code = app.main(args + ['--save', str(path)], stdin=player, stdout=output)
    assert code == 0, output.getvalue()[-3000:]
    return output.getvalue(), load_game(path, validate=True)


def test_march_battle_multiple_humans_resume_and_replay(monkeypatch, tmp_path):
    initial = _combat_position()
    _install_position(monkeypatch, initial)
    whole = tmp_path / 'whole.json'
    text, (finished, _, log) = _play(whole)
    assert 'Game ended' in text
    commands = [e['player_action']['command'] for e in log
                if e.get('player_action')]
    assert commands == ['March', 'Battle']
    assert count_pieces(finished, rc.PROVINCIA, rc.ROMANS) == 0
    assert count_pieces(finished, rc.SEQUANI, rc.ARVERNI, rc.WARBAND) == 3
    assert count_pieces(finished, rc.SEQUANI, rc.ROMANS, rc.LEGION) == 3
    assert {e['faction'] for e in log if e.get('reactive')} >= {rc.ROMANS, rc.ARVERNI}
    assert 'TRIBES' in text and text.count('AVAILABLE PIECES') >= 3
    assert 'changes since' in text.lower()
    for card in (1, 2):
        for line in get_card_text(card, initial['scenario'], 'second-edition').splitlines():
            assert line in text.split('Choose your action:', 1)[0]

    interrupted = tmp_path / 'interrupted.json'
    output = io.StringIO()
    player = TacticalPlayer(output, interrupt_retreat=True)
    paused_text, (paused, _, paused_log) = _play(interrupted, output=output, player=player)
    assert 'Interrupted -- game saved' in paused_text
    assert count_pieces(paused, rc.SEQUANI, rc.ARVERNI, rc.WARBAND) == 12
    assert [e['player_action']['command'] for e in paused_log
            if e.get('player_action')] == ['March']
    assert paused.get('_card_turn') is not None

    resumed_output = io.StringIO()
    resumed_player = TacticalPlayer(resumed_output, commands_done=1)
    resumed_text, (resumed, _, resumed_log) = _play(
        interrupted, output=resumed_output, player=resumed_player, load=True)
    assert 'Game ended' in resumed_text
    assert _digest_state(resumed) == _digest_state(finished)
    assert resumed_log == log

    replayed = tmp_path / 'replayed.json'
    replay_output = io.StringIO()
    assert app.main(['--replay', str(interrupted), '--save', str(replayed)],
                    stdin=io.StringIO(''), stdout=replay_output) == 0
    assert 'Game ended' in replay_output.getvalue()
    assert 'desynced' not in replay_output.getvalue()
    assert _digest_state(load_game(replayed, validate=True)[0]) == _digest_state(finished)


class TradePlayer(TacticalPlayer):
    def __init__(self, output, timing):
        super().__init__(output)
        self.timing = timing
        self.answers = []
        self.planned = False

    def readline(self):
        text = self.output.getvalue()
        delta, self.position = text[self.position:], len(text)
        self.reads += 1
        assert self.reads < 150, text[-3000:]
        if self.answers:
            return self.answers.pop(0) + '\n'
        match = re.search(r'You are (.*?), the ', delta)
        if match:
            self.faction = match.group(1)
        options = re.findall(r'^\s*(\d+)\) (.*)$', delta, re.M)
        labels = {label.strip(): number for number, label in options}
        if 'Choose your action:' in delta:
            return labels['Command + Special Ability' if self.faction == rc.AEDUI
                          and not self.planned else 'Pass'] + '\n'
        if 'Which Command?' in delta:
            self.planned = True
            # Follow the real Rally/Trade menus used by §4.1's timing example.
            self.answers = (['5', '1', '1', '3', '3', '1', '1']
                            if self.timing == 'before' else
                            ['1', '3', '3', '1', '1', 'y', '1', 'n'])
            return self.answers.pop(0) + '\n'
        assert not options, delta
        # The other human seat explicitly approves the actual Trade, after
        # the planner's non-mutating preview has completed.
        return 'y\n'


@pytest.mark.parametrize('timing,starting_resources,ending_resources', [
    ('before', 0, 5), ('after', 1, 6),
])
def test_trade_rally_orders_with_human_agreement_replay(
        monkeypatch, tmp_path, timing, starting_resources, ending_resources):
    initial = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=3)
    initial['card_edition'] = 'second-edition'
    initial['deck'] = [46, 47]
    initial['resources'][rc.AEDUI] = starting_resources
    _install_position(monkeypatch, initial)
    saved = tmp_path / 'trade.json'
    output = io.StringIO()
    player = TradePlayer(output, timing)
    text, (finished, _, log) = _play(saved, output=output, player=player)
    assert 'Game ended' in text
    action = next(e['player_action'] for e in log if e.get('player_action'))
    assert action['command'] == 'Rally' and action['sa'] == 'Trade'
    assert action['sa_timing'] == timing
    assert finished['resources'][rc.AEDUI] == ending_resources
    assert count_pieces(finished, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) > count_pieces(
        initial, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND)
    assert any(e.get('reactive') == 'agreement' and e['faction'] == rc.ROMANS
               and e['response'] is True for e in log)
    replayed = tmp_path / 'trade-replayed.json'
    replay_output = io.StringIO()
    assert app.main(['--replay', str(saved), '--save', str(replayed)],
                    stdin=io.StringIO(''), stdout=replay_output) == 0
    assert 'Game ended' in replay_output.getvalue()
    assert _digest_state(load_game(replayed, validate=True)[0]) == _digest_state(finished)


class TransitionPlayer(TacticalPlayer):
    def __init__(self, output, *, interrupt_arverni=False):
        super().__init__(output)
        self.interrupt_arverni = interrupt_arverni

    def readline(self):
        text = self.output.getvalue()
        delta, self.position = text[self.position:], len(text)
        self.reads += 1
        assert self.reads < 1000, text[-3000:]
        if 'You are Arverni,' in delta and self.interrupt_arverni:
            raise KeyboardInterrupt
        options = re.findall(r'^\s*(\d+)\) (.*)$', delta, re.M)
        labels = {label.strip(): number for number, label in options}
        if labels:
            preferred = ['Pass', 'Use bot default',
                         'No Retreat (take Losses in place)', '(done)']
            return next((labels[label] for label in preferred if label in labels),
                        options[0][0]) + '\n'
        return 'n\n'


def test_real_interlude_human_seat_handover_resume_and_replay(monkeypatch, tmp_path):
    # A Scenario: The Gallic War: the third Winter changes the German
    # player's seat to Arverni. Preserve the actual Winter/Interlude rules;
    # select that Winter as this position's next card to guarantee coverage.
    initial = setup_scenario(rc.SCENARIO_GALLIC_WAR, seed=23)
    initial['card_edition'] = 'second-edition'
    initial['winter_count'] = 2
    initial['deck'] = [rc.WINTER_CARD, 1]
    _install_position(monkeypatch, initial)
    whole = tmp_path / 'interlude-whole.json'
    output = io.StringIO()
    text, (finished, meta, log) = _play(
        whole, output=output, player=TransitionPlayer(output),
        scenario=rc.SCENARIO_GALLIC_WAR)
    assert 'Game ended' in text
    assert 'German player now plays the Arverni' in text
    assert finished['interlude_completed']
    assert finished['scenario_phase'] == 'second_half'
    assert finished['scenario'] == rc.SCENARIO_PAX_GALLICA
    assert meta['initial_faction_modes'][rc.GERMANS] == 'human'
    assert rc.GERMANS not in meta['faction_modes']
    assert meta['faction_modes'][rc.ARVERNI] == 'human'
    assert any(e['faction'] == rc.ARVERNI and not e.get('reactive') for e in log)

    paused = tmp_path / 'interlude-paused.json'
    output = io.StringIO()
    text, (pending, pending_meta, _) = _play(
        paused, output=output,
        player=TransitionPlayer(output, interrupt_arverni=True),
        scenario=rc.SCENARIO_GALLIC_WAR)
    assert 'Interrupted -- game saved' in text
    assert pending['interlude_completed']
    assert pending_meta['faction_modes'][rc.ARVERNI] == 'human'
    output = io.StringIO()
    text, (resumed, _, resumed_log) = _play(
        paused, output=output, player=TransitionPlayer(output), load=True)
    assert 'Game ended' in text
    assert _digest_state(resumed) == _digest_state(finished)
    assert resumed_log == log

    replayed = tmp_path / 'interlude-replayed.json'
    output = io.StringIO()
    assert app.main(['--replay', str(paused), '--save', str(replayed)],
                    stdin=io.StringIO(''), stdout=output) == 0
    assert 'Game ended' in output.getvalue()
    assert 'desynced' not in output.getvalue()
    assert _digest_state(load_game(replayed, validate=True)[0]) == _digest_state(finished)


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
@pytest.mark.parametrize('edition', ['original', 'second-edition'])
def test_full_scenario_tactical_human_game_replays(tmp_path, scenario, edition):
    # Use the actual scenario setup and shuffled deck here, without fixtures.
    # All human seats allow the Roman player to make a real March and Battle;
    # remaining turns Pass to finish the full Winter sequence deterministically.
    saved = tmp_path / 'full-tactical.json'
    output = io.StringIO()
    player = TacticalPlayer(output)
    assert app.main(['--scenario', scenario, '--seed', '23', '--bots', '',
                     '--card-edition', edition, '--save', str(saved)],
                    stdin=player, stdout=output) == 0, output.getvalue()[-3000:]
    assert 'Game ended' in output.getvalue()
    finished, _, log = load_game(saved, validate=True)
    commands = [e['player_action']['command'] for e in log if e.get('player_action')]
    assert commands == ['March', 'Battle']
    assert finished['winter_count'] > 0
    replayed = tmp_path / 'full-tactical-replayed.json'
    output = io.StringIO()
    assert app.main(['--replay', str(saved), '--save', str(replayed)],
                    stdin=io.StringIO(''), stdout=output) == 0
    assert 'Game ended' in output.getvalue()
    assert 'desynced' not in output.getvalue()
    assert _digest_state(load_game(replayed, validate=True)[0]) == _digest_state(finished)
