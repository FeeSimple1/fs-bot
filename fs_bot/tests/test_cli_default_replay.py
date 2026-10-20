"""Human menu choices must not consume unrecorded planning input or dice."""
import copy
import io

from fs_bot.cli import app
from fs_bot.cli.quarters import collect_quarters_plan
from fs_bot.engine.agent import AGREEMENT, consult_agent
from fs_bot.rules_consts import ROMANS, SCENARIO_RECONQUEST
from fs_bot.state.serialize import encode, load_game
from fs_bot.state.state_schema import build_initial_state


def test_default_quarters_choice_defers_planning_to_replayable_engine(monkeypatch):
    state = build_initial_state(SCENARIO_RECONQUEST, seed=13)
    before = encode(state)
    calls = []

    def planner(board):
        calls.append(board['rng'].randint(1, 6))
        return {ROMANS: []}

    monkeypatch.setattr('fs_bot.bots.roman_bot.build_np_winter_relocations', planner)
    response = collect_quarters_plan(state, ROMANS, {}, io.StringIO('1\n'), io.StringIO())
    assert response is None  # the logged default reruns the engine planner
    assert calls == []
    assert encode(state) == before


def test_bot_preview_cannot_consume_live_cli_response(monkeypatch, tmp_path):
    answers = []

    def card(state, decision, *, execute):
        request = {'kind': AGREEMENT, 'request_type': 'trade_roman_agreement'}
        preview = copy.deepcopy(state)
        assert consult_agent(preview, ROMANS, request) is None
        answers.append(consult_agent(state, ROMANS, request))
        return {'card': state['current_card'], 'game_over': True}

    monkeypatch.setattr(app, 'play_card', card)
    saved = tmp_path / 'game.json'
    assert app.main(['--scenario', SCENARIO_RECONQUEST, '--seed', '13',
                     '--bots', 'Arverni,Aedui,Belgae', '--save', str(saved)],
                    stdin=io.StringIO('y\n'), stdout=io.StringIO()) == 0
    assert answers == [True]
    _, _, log = load_game(saved)
    assert len(log) == 1 and log[0]['response'] is True
