"""Kinship decisions survive interruption, save/load and exact replay."""
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.battle.excluded_leader import EXCLUDED_LEADER_KEY
from fs_bot.board.pieces import place_piece, get_leader_in_region
from fs_bot.cards.card_text import get_card_text
from fs_bot.cards.kinship import resolve_kinship, legal_regions
from fs_bot.cli import app
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine.agent import consult_agent
from fs_bot.engine.game_engine import _action_transaction
from fs_bot.state.serialize import encode, decode, save_game, load_game
from fs_bot.state.state_schema import build_initial_state
from fs_bot.tools.seat_session import SeatSession, DecisionPending, board_copy


def state():
    st = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=65)
    st['current_card'], st['next_card'] = 'A65', 4
    st['non_player_factions'] = {rc.ROMANS, rc.GERMANS, rc.AEDUI}
    place_piece(st, rc.MORINI, rc.BELGAE, rc.WARBAND, 2)
    place_piece(st, rc.MORINI, rc.BELGAE, rc.LEADER, leader_name=rc.BODUOGNATUS)
    place_piece(st, rc.MORINI, rc.GERMANS, rc.WARBAND, 8)
    return st


def driver(session):
    def callback(*args):
        pass
    callback.transaction_checkpoint = session.checkpoint
    callback.transaction_restore = session.restore
    return callback


def test_actual_battle_pause_saves_selected_plan_and_resumes_without_exposing_leader(tmp_path):
    st = state()
    output = StringIO()
    view = HumanTurnDisplay(output)
    view.remember(st, [rc.BELGAE])
    session = SeatSession(st, {'seat': rc.BELGAE}, [], view)
    st['decision_agent'] = session.reactive
    chosen = {'faction': rc.BELGAE, 'regions': [rc.MORINI]}
    session.import_inbox([{'response': chosen}])
    before = encode(board_copy(st))
    with pytest.raises(DecisionPending):
        with _action_transaction(st, driver(session)):
            resolve_kinship(st, rc.BELGAE)
    assert encode(board_copy(st)) == before and EXCLUDED_LEADER_KEY not in st
    assert len(session.data['journal']) == 1
    pending = session.data['pending']
    request = decode(pending['request'])
    assert request['kind'] == 'loss_order'
    assert all(piece[0] != rc.LEADER for piece in request['pieces'])
    displayed = output.getvalue()
    assert 'changes since your last decision' in displayed
    for card in (st['current_card'], st['next_card']):
        assert get_card_text(card, st['scenario']).splitlines()[0] in displayed
    save_game(st, tmp_path / 'kinship.json', meta=session.meta, log=session.log)
    restored, meta, log = load_game(tmp_path / 'kinship.json')
    resumed = SeatSession(restored, meta, log, HumanTurnDisplay(StringIO()))
    restored['decision_agent'] = resumed.reactive
    resumed.import_inbox([{'response': {'use_default': True}}] * 2)
    with _action_transaction(restored, driver(resumed)):
        result = resolve_kinship(restored, rc.BELGAE)
    resumed.finish()
    assert result[0]['result']['executed']
    assert get_leader_in_region(restored, rc.MORINI, rc.BELGAE) == rc.BODUOGNATUS
    assert EXCLUDED_LEADER_KEY not in restored
    assert len(log) == 3 and decode(log[0]['assistant_response']) == chosen
    # Replay the committed journal from the original board. No second live
    # choice or hidden RNG draw may be inserted during the saved-plan replay.
    replay = state()
    entries = iter(log)
    def recorded(board, faction, request):
        if faction != rc.BELGAE:
            return None
        entry = next(entries)
        assert decode(entry['assistant_request']) == dict(request, faction=faction)
        return decode(entry['assistant_response'])
    replay['decision_agent'] = recorded
    assert resolve_kinship(replay, rc.BELGAE) == result
    assert encode(board_copy(replay)) == encode(board_copy(restored))
    assert next(entries, None) is None


def test_invalid_assistant_plan_preserves_pending_id_board_and_input():
    st = state()
    session = SeatSession(st, {'seat': rc.BELGAE}, [], HumanTurnDisplay(StringIO()))
    st['decision_agent'] = session.reactive
    response = {'faction': rc.ROMANS, 'regions': [rc.MORINI]}
    session.import_inbox([{'response': response}])
    before = encode(board_copy(st))
    with pytest.raises(DecisionPending):
        with _action_transaction(st, driver(session)):
            resolve_kinship(st, rc.BELGAE)
    assert session.error and session.data['pending']['id'] == 'd000001'
    assert not session.data['journal'] and session.data['queue'] == [{'response': response}]
    assert encode(board_copy(st)) == before


def test_terminal_default_displays_cards_changes_board_and_replays(monkeypatch, tmp_path):
    responses, observed = [], []
    def card(st, decision, *, execute):
        st['resources'][rc.AEDUI] += 1
        observed.append((st['current_card'], st['next_card']))
        responses.append(consult_agent(st, rc.AEDUI, {
            'kind': 'kinship', 'card_id': 'A65', 'attackers': [rc.BELGAE, rc.GERMANS],
            'regions_by_faction': {f: legal_regions(st, f) for f in (rc.BELGAE, rc.GERMANS)}}))
        return {'card': st['current_card'], 'game_over': True}
    monkeypatch.setattr(app, 'play_card', card)
    saved, output = tmp_path / 'terminal.json', StringIO()
    assert app.main(['--scenario', rc.SCENARIO_ARIOVISTUS, '--seed', '65',
                     '--bots', 'Romans,Belgae,Germans', '--save', str(saved)],
                    stdin=StringIO('board\nUse bot default\n'), stdout=output) == 0
    _, _, log = load_game(saved)
    assert len(log) == 1 and log[0]['reactive'] == 'kinship'
    before = output.getvalue().split('Kinship Battle?')[0]
    assert 'changes since your last decision' in before and f'{rc.AEDUI} Resources:' in before
    for card_id in observed[0]:
        for line in get_card_text(card_id, rc.SCENARIO_ARIOVISTUS).splitlines():
            assert line in before
    assert output.getvalue().count('AVAILABLE PIECES') >= 2
    assert app.main(['--replay', str(saved)], stdin=StringIO(''), stdout=StringIO()) == 0
    assert responses == [{'use_default': True}] * 2
