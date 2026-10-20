"""A3.4.3 human choices remain explicit, visible, and replayable."""
import io
import random

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, flip_piece, place_piece
from fs_bot.cards.card_text import get_card_text
from fs_bot.cli import app
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.commands.raid import raid_in_region
from fs_bot.engine.agent import consult_agent
from fs_bot.engine.game_engine import _action_transaction
from fs_bot.engine.raid_intimidate import target_options
from fs_bot.state.serialize import encode, decode, save_game, load_game
from fs_bot.state.state_schema import build_initial_state
from fs_bot.tools.player_fuzz import make_random_reactive
from fs_bot.tools.seat_session import (
    SeatSession, DecisionPending, board_copy, validate_response,
)


def _state():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=7)
    state['current_card'], state['next_card'] = 'A3', 4
    state['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE}
    place_piece(state, rc.SEQUANI, rc.GERMANS, rc.LEADER,
                leader_name=rc.ARIOVISTUS_LEADER)
    place_piece(state, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 3)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.SEQUANI, rc.BELGAE, rc.WARBAND)
    return state


def _request(state, raiders=2):
    return {'kind': 'raid_intimidate', 'region': rc.SEQUANI,
            'raiders': raiders, 'max_removals': min(2, raiders),
            'targets': target_options(state, rc.SEQUANI)}


def _target(owner=rc.ROMANS, piece=rc.AUXILIA, visibility=rc.HIDDEN):
    return {'target_faction': owner, 'target_piece': piece,
            'target_state': visibility}


@pytest.mark.parametrize('choice,response', [
    ('Decline free Intimidate', {'decline': True}),
    ('Use bot default', {'use_default': True}),
    ('Place an Intimidated marker only', {'targets': []}),
])
def test_menu_requires_explicit_decline_default_or_marker_choice(choice, response):
    state = _state()
    before = encode(state)
    agent = make_cli_reactive([rc.GERMANS], io.StringIO(choice + '\n'), io.StringIO())
    assert agent(state, rc.GERMANS, _request(state)) == response
    assert encode(state) == before


def test_menu_reserves_repeated_targets_and_stays_with_one_faction():
    state = _state()
    agent = make_cli_reactive([rc.GERMANS], io.StringIO(
        f'Remove {rc.ROMANS} pieces and place the marker\n'
        f'{rc.AUXILIA} ({rc.HIDDEN})\n{rc.AUXILIA} ({rc.HIDDEN})\n'), io.StringIO())
    assert agent(state, rc.GERMANS, _request(state)) == {
        'targets': [_target(), _target()]}
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 2


def test_menu_cannot_reselect_the_only_physical_piece_or_exceed_actual_raiders():
    state = _state()
    # One enemy piece cannot be selected a second time, even with two raiders.
    stream = io.StringIO(f'Remove {rc.BELGAE} pieces and place the marker\n'
                         f'{rc.WARBAND} ({rc.HIDDEN})\nunused\n')
    response = make_cli_reactive([rc.GERMANS], stream, io.StringIO())(
        state, rc.GERMANS, _request(state))
    assert response == {'targets': [_target(rc.BELGAE, rc.WARBAND)]}
    assert stream.readline() == 'unused\n'
    # Two physically available Auxilia still allow only one removal when
    # just one Hidden German Warband actually carried out the Raid.
    stream = io.StringIO(f'Remove {rc.ROMANS} pieces and place the marker\n'
                         f'{rc.AUXILIA} ({rc.HIDDEN})\nunused\n')
    response = make_cli_reactive([rc.GERMANS], stream, io.StringIO())(
        state, rc.GERMANS, _request(state, raiders=1))
    assert response == {'targets': [_target()]}
    assert stream.readline() == 'unused\n'


def test_raid_reaction_eof_interrupts_instead_of_choosing_default():
    state = _state()
    state['decision_agent'] = make_cli_reactive(
        [rc.GERMANS], io.StringIO(''), io.StringIO())
    with pytest.raises(EOFError):
        consult_agent(state, rc.GERMANS, _request(state))


def _driver(session):
    def callback(*args):
        pass
    callback.transaction_checkpoint = session.checkpoint
    callback.transaction_restore = session.restore
    return callback


def _session(state):
    output = io.StringIO()
    view = HumanTurnDisplay(output)
    view.remember(state, [rc.GERMANS])
    session = SeatSession(state, {'seat': rc.GERMANS}, [], view)
    state['decision_agent'] = session.reactive
    return session, output


def test_actual_raid_pauses_then_saves_resumes_and_journals_exact_choice(tmp_path):
    state = _state()
    session, output = _session(state)
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending):
        with _action_transaction(state, _driver(session)):
            raid_in_region(state, rc.SEQUANI, rc.GERMANS, [{'type': 'gain'}] * 2)
    assert encode(board_copy(state)) == before
    pending = session.data['pending']
    request = decode(pending['request'])
    assert request['kind'] == 'raid_intimidate' and request['raiders'] == 2
    pending_board = decode(pending['board'])
    assert count_pieces_by_state(pending_board, rc.SEQUANI, rc.GERMANS,
                                 rc.WARBAND, rc.REVEALED) == 2
    # Central display exposes both card texts and the Raid's changes before
    # this decision; a pause does not commit those changes to the live board.
    shown = output.getvalue()
    assert f'{rc.GERMANS} Resources: 0 -> 2' in shown
    assert f'{rc.GERMANS} {rc.REVEALED} {rc.WARBAND}: 0 -> 2' in shown
    for card in (state['current_card'], state['next_card']):
        for line in get_card_text(card, state['scenario']).splitlines():
            assert line in shown
    save_game(state, tmp_path / 'raid.json', meta=session.meta, log=session.log)
    restored, meta, log = load_game(tmp_path / 'raid.json')
    resumed = SeatSession(restored, meta, log, HumanTurnDisplay(io.StringIO()))
    restored['decision_agent'] = resumed.reactive
    chosen = {'targets': [_target(), _target()]}
    resumed.import_inbox({'decision_id': pending['id'], 'response': chosen})
    with _action_transaction(restored, _driver(resumed)):
        result = raid_in_region(restored, rc.SEQUANI, rc.GERMANS,
                                [{'type': 'gain'}] * 2)
    resumed.finish()
    assert result['raid_intimidate']['executed']
    assert count_pieces(restored, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces_by_state(restored, rc.SEQUANI, rc.GERMANS,
                                 rc.WARBAND, rc.HIDDEN) == 1
    assert restored['resources'][rc.GERMANS] == 2
    assert len(log) == 1 and log[0]['reactive'] == 'raid_intimidate'
    assert decode(log[0]['assistant_response']) == chosen
    assert not resumed.data['journal'] and not resumed.data['queue']


@pytest.mark.parametrize('response,raiders', [
    ({'targets': [_target(), _target(rc.BELGAE, rc.WARBAND)]}, 2),
    ({'targets': [_target(rc.BELGAE, rc.WARBAND)] * 2}, 2),
    ({'targets': [_target()] * 2}, 1),
    ({'targets': [{'target_faction': rc.ROMANS}]}, 2),
])
def test_invalid_assistant_choice_retains_pending_input_and_live_board(response, raiders):
    state = _state()
    flip_piece(state, rc.SEQUANI, rc.GERMANS, rc.WARBAND, count=raiders,
               from_state=rc.HIDDEN, to_state=rc.REVEALED)
    session, _ = _session(state)
    session.import_inbox([{'response': response}])
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending):
        with _action_transaction(state, _driver(session)):
            consult_agent(state, rc.GERMANS, _request(state, raiders))
    assert session.error
    assert session.data['queue'] == [{'response': response}]
    assert session.data['pending']['id'] == 'd000001'
    assert session.data['journal'] == []
    assert encode(board_copy(state)) == before


def test_cli_default_is_displayed_recorded_and_replayed_without_input(monkeypatch, tmp_path):
    responses = []
    observed_cards = []
    def card(state, decision, *, execute):
        state['resources'][rc.GERMANS] += 1
        observed_cards.append((state['current_card'], state['next_card']))
        responses.append(consult_agent(state, rc.GERMANS, _request(state)))
        return {'card': state['current_card'], 'game_over': True}
    monkeypatch.setattr(app, 'play_card', card)
    saved = tmp_path / 'game.json'
    out = io.StringIO()
    assert app.main(['--scenario', rc.SCENARIO_ARIOVISTUS, '--seed', '7',
                     '--bots', 'Romans,Aedui,Belgae', '--save', str(saved)],
                    stdin=io.StringIO('board\nUse bot default\n'), stdout=out) == 0
    _, _, log = load_game(saved)
    assert log == [{'reactive': 'raid_intimidate', 'faction': rc.GERMANS,
                    'card': observed_cards[0][0], 'response': {'use_default': True}}]
    before_prompt = out.getvalue().split('Use the raiders to Intimidate?')[0]
    assert 'changes since your last decision' in before_prompt
    assert f'{rc.GERMANS} Resources:' in before_prompt
    for card_id in observed_cards[0]:
        for line in get_card_text(card_id, rc.SCENARIO_ARIOVISTUS).splitlines():
            assert line in before_prompt
    assert out.getvalue().count('AVAILABLE PIECES') >= 2  # initial + board command
    assert app.main(['--replay', str(saved)],
                    stdin=io.StringIO(''), stdout=io.StringIO()) == 0
    assert responses == [{'use_default': True}] * 2


def test_random_reactions_reserve_physical_counts_and_validate_actual_raid_budget():
    state = _state()
    flip_piece(state, rc.SEQUANI, rc.GERMANS, rc.WARBAND,
               from_state=rc.HIDDEN, to_state=rc.REVEALED)
    request = _request(state, raiders=1)
    agent = make_random_reactive([rc.GERMANS], random.Random(27))
    responses = [agent(state, rc.GERMANS, request) for _ in range(40)]
    assert {'decline': True} in responses and {'targets': []} in responses
    assert any(response.get('targets') for response in responses)
    for response in responses:
        assert validate_response(state, request, response) == response
