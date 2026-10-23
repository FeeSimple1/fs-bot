"""Morasses keeps beneficiary, Battle and March decisions across save/replay."""
from io import StringIO
import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces_by_state
from fs_bot.cards.card_effects import execute_card_36
from fs_bot.cards.card_text import get_card_text
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine.execute import _resolve_free_actions
from fs_bot.engine.game_engine import _action_transaction
from fs_bot.state.serialize import encode, decode, save_game, load_game
from fs_bot.state.state_schema import build_initial_state
from fs_bot.tools.seat_session import SeatSession, DecisionPending, board_copy


def state():
    st = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=36)
    st['current_card'], st['next_card'] = 36, 4
    st['non_player_factions'] = {rc.ROMANS, rc.ARVERNI, rc.AEDUI}
    place_piece(st, rc.MORINI, rc.BELGAE, rc.WARBAND, 4, piece_state=rc.REVEALED)
    place_piece(st, rc.MORINI, rc.ROMANS, rc.AUXILIA, 2)
    execute_card_36(st, shaded=True)
    return st


def session(st, meta=None, log=None):
    output = StringIO()
    view = HumanTurnDisplay(output)
    view.remember(st, [rc.BELGAE])
    ses = SeatSession(st, meta or {'seat': rc.BELGAE}, [] if log is None else log, view)
    st['decision_agent'] = ses.reactive
    return ses, output


def run(ses):
    def driver(*args): pass
    driver.transaction_checkpoint = ses.checkpoint
    driver.transaction_restore = ses.restore
    with _action_transaction(ses.state, driver):
        return _resolve_free_actions(ses.state, rc.BELGAE)


def test_all_three_choices_pause_save_resume_and_replay(tmp_path):
    st = state(); ses, output = session(st)
    before = encode(board_copy(st))
    beneficiary = {'faction': rc.BELGAE}
    battle = {'command': rc.CMD_BATTLE, 'sa': rc.SA_AMBUSH, 'sa_regions': [rc.MORINI],
              'regions': [rc.MORINI], 'details': {'battle_plan': [{'region': rc.MORINI, 'target': rc.ROMANS}]}}
    march = {'action': None, 'in_place': [rc.MORINI]}
    with pytest.raises(DecisionPending): run(ses)
    assert decode(ses.data['pending']['request'])['request_type'] == 'morasses_faction'
    for choice in (beneficiary, battle):
        ses.import_inbox({'decision_id': ses.data['pending']['id'], 'response': choice})
        with pytest.raises(DecisionPending): run(ses)
        assert encode(board_copy(st)) == before
    pending = ses.data['pending']
    assert decode(pending['request'])['request_type'] == 'morasses_march'
    assert len(ses.data['journal']) == 2
    preview = decode(pending['board'])
    assert count_pieces_by_state(preview, rc.MORINI, rc.BELGAE, rc.WARBAND, rc.REVEALED) == 4
    for card in (36, 4):
        for line in get_card_text(card, st['scenario']).splitlines():
            assert line in output.getvalue()
    assert 'changes since your last decision' in output.getvalue()
    save_game(st, tmp_path / 'morasses.json', meta=ses.meta, log=ses.log)
    restored, meta, log = load_game(tmp_path / 'morasses.json')
    resumed, _ = session(restored, meta, log)
    resumed.import_inbox({'decision_id': pending['id'], 'response': march})
    result = run(resumed); resumed.finish()
    assert result[0]['executed'] and result[0]['march']['executed']
    assert count_pieces_by_state(restored, rc.MORINI, rc.BELGAE, rc.WARBAND, rc.HIDDEN) == 4
    assert 'card_36_gallic_ambush_battle' not in restored['event_modifiers']
    assert [decode(e['assistant_response']) for e in log] == [beneficiary, battle, march]
    replay = state(); entries = iter(log)
    def recorded(board, faction, request):
        if request['kind'] != 'free_action' or faction != rc.BELGAE:
            return None
        entry = next(entries)
        assert decode(entry['assistant_request']) == dict(request, faction=faction)
        return decode(entry['assistant_response'])
    replay['decision_agent'] = recorded
    assert _resolve_free_actions(replay, rc.BELGAE) == result
    assert encode(board_copy(replay)) == encode(board_copy(restored))
    assert next(entries, None) is None


def test_invalid_beneficiary_keeps_pending_id_queue_and_board():
    st = state(); ses, _ = session(st)
    before = encode(board_copy(st))
    invalid = {'faction': rc.ROMANS}
    ses.import_inbox([{'response': invalid}])
    with pytest.raises(DecisionPending): run(ses)
    assert encode(board_copy(st)) == before
    assert ses.error and ses.data['pending']['id'] == 'd000001'
    assert not ses.data['journal'] and ses.data['queue'] == [{'response': invalid}]
