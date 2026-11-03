"""A19 Captured follows A Card Reference, §§3.2.2, 5.1 and 5.1.3."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, count_pieces_by_state
from fs_bot.cards.procillus import moves, resolve
from fs_bot.cli.free_actions import collect_free_action
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine.execute import _execute_event
from fs_bot.engine.free_actions import validate_free_action_response
from fs_bot.engine.game_engine import _action_transaction
from fs_bot.state.serialize import encode, decode, save_game, load_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import SeatSession, DecisionPending, board_copy


def state():
    st = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=19)
    st['current_card'], st['next_card'] = 'A19', 'A67'
    st['non_player_factions'] = set()
    place_piece(st, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 2, piece_state=rc.REVEALED)
    place_piece(st, rc.UBII, rc.GERMANS, rc.WARBAND)
    place_piece(st, rc.UBII, rc.ROMANS, rc.FORT)
    return st


def event(st, faction=rc.AEDUI):
    return _execute_event(st, faction, {'command': 'Event', 'details': {
        'card_id': 'A19', 'text_preference': rc.EVENT_SHADED}}, human=True)


def choice():
    return {'origin': rc.SEQUANI, 'destination': rc.UBII}


@pytest.mark.parametrize('faction', [rc.ROMANS, rc.AEDUI, rc.BELGAE, rc.GERMANS])
def test_every_executor_selects_whole_force_despite_fort_and_fewer_germans(faction):
    st = state()
    place_piece(st, rc.SEQUANI, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(st, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(st, rc.SEQUANI, rc.ROMANS, rc.FORT)
    requests = []
    def agent(board, owner, request):
        requests.append((owner, request))
        return choice() if request['kind'] == 'free_action' else None
    st['decision_agent'] = agent
    assert event(st, faction)['executed']
    assert requests[0][0] == faction
    assert requests[0][1]['acting_faction'] == rc.ROMANS
    assert count_pieces(st, rc.SEQUANI, rc.ROMANS) == 1
    assert count_pieces(st, rc.UBII, rc.ROMANS) == 5
    assert count_pieces_by_state(st, rc.UBII, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 2
    assert st['eligibility'][rc.ROMANS] == rc.INELIGIBLE
    assert st['forced_ineligible'][rc.ROMANS] == 1
    assert validate_state(st) == []


def test_npc_germans_keep_no_fort_and_outnumber_restrictions():
    st = state(); st['non_player_factions'] = {rc.GERMANS}
    assert resolve(st, rc.GERMANS)[0]['declined_no_effect']
    assert count_pieces(st, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 2


@pytest.mark.parametrize('invalid', [
    {'origin': rc.SEQUANI, 'destination': rc.NERVII},
    {'origin': rc.SEQUANI, 'destination': rc.UBII, 'auxilia': 1},
    {'decline': True}, {'decline': 1}, {'acting_faction': rc.AEDUI}])
def test_invalid_move_rolls_back_event_and_rng(invalid):
    st = state(); before = encode(board_copy(st))
    st['decision_agent'] = lambda *args: invalid
    assert not event(st)['executed']
    # Event transaction's legacy cleanup materializes these null fields.
    st.pop('event_params', None); st.pop('executing_faction', None)
    assert encode(board_copy(st)) == before


def session(st, meta=None, log=None):
    view = HumanTurnDisplay(StringIO())
    view.remember(st, [rc.AEDUI])
    ses = SeatSession(st, meta or {'seat': rc.AEDUI}, [] if log is None else log, view)
    st['decision_agent'] = ses.reactive
    return ses


def run(ses):
    def driver(*args): pass
    driver.transaction_checkpoint, driver.transaction_restore = ses.checkpoint, ses.restore
    with _action_transaction(ses.state, driver):
        return event(ses.state)


def test_pending_invalid_save_load_and_exact_replay(tmp_path):
    st = state(); ses = session(st); before = encode(board_copy(st))
    with pytest.raises(DecisionPending): run(ses)
    pending = deepcopy(ses.data['pending'])
    assert decode(pending['request'])['request_type'] == 'procillus_march'
    assert decode(pending['request'])['faction'] == rc.AEDUI
    assert encode(board_copy(st)) == before
    ses.import_inbox({'decision_id': pending['id'], 'response': {'decline': True}})
    with pytest.raises(DecisionPending): run(ses)
    assert ses.data['pending']['id'] == pending['id'] and ses.error
    assert encode(board_copy(st)) == before
    ses.import_inbox({'decision_id': pending['id'], 'response': choice()})
    save_game(st, tmp_path / 'procillus.json', meta=ses.meta, log=ses.log)
    restored, meta, log = load_game(tmp_path / 'procillus.json')
    resumed = session(restored, meta, log)
    result = run(resumed); resumed.finish()
    assert result['executed']
    replay = state(); replay['decision_agent'] = lambda *args: decode(log[0]['assistant_response'])
    assert event(replay) == result
    assert encode(board_copy(replay)) == encode(board_copy(restored))


def test_terminal_exposes_legal_pairs_without_npc_restrictions():
    st = state()
    request = {'kind': 'free_action', 'request_type': 'procillus_march',
               'acting_faction': rc.ROMANS, 'allow_decline': False, 'moves': moves(st)}
    before = encode(board_copy(st)); out = StringIO()
    assert collect_free_action(st, rc.AEDUI, request, StringIO('1\n'), out) == choice()
    assert validate_free_action_response(st, rc.AEDUI, request, choice()) is None
    assert encode(board_copy(st)) == before
    assert rc.SEQUANI in out.getvalue() and rc.UBII in out.getvalue()
