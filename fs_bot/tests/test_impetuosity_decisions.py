"""Card 72 preserves both human choices across pauses, saves, and replay."""
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece
from fs_bot.cards.card_effects import execute_card_72
from fs_bot.cards.card_text import get_card_text
from fs_bot.cli.display import HumanTurnDisplay, format_board
from fs_bot.commands.sa_enlist import FREE_FORCE_KEY
from fs_bot.engine.execute import _resolve_free_actions
from fs_bot.engine.game_engine import _action_transaction
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state
from fs_bot.tools.seat_session import SeatSession, DecisionPending, board_copy


FLAG = 'card_72_hidden_march_battle'


def _state():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=7)
    state['current_card'], state['next_card'] = 72, 4
    state['non_player_factions'] = {rc.ROMANS, rc.ARVERNI, rc.AEDUI}
    place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND, 3)
    place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND, 2,
                piece_state=rc.REVEALED)
    # The origin becomes uncontrolled after March, so the isolated Battle
    # has no unrelated request for permission to Retreat into Belgic Control.
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 3)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 4)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.LEADER,
                leader_name=rc.AMBIORIX)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA)
    execute_card_72(state, shaded=True)
    return state


def _session(state, meta=None, log=None):
    output = io.StringIO()
    view = HumanTurnDisplay(output)
    view.remember(state, [rc.BELGAE])
    session = SeatSession(state, meta or {'seat': rc.BELGAE},
                          [] if log is None else log, view)
    state['decision_agent'] = session.reactive
    return session, output


def _driver(session):
    def callback(*args):
        pass
    callback.transaction_checkpoint = session.checkpoint
    callback.transaction_restore = session.restore
    return callback


def _resolve(session):
    with _action_transaction(session.state, _driver(session)):
        return _resolve_free_actions(session.state, rc.BELGAE)


@pytest.mark.parametrize('battle', [False, True], ids=['decline-battle', 'battle'])
def test_impetuosity_pauses_saves_resumes_and_replays_only_selected_force(tmp_path, battle):
    state = _state()
    session, output = _session(state)
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending):
        _resolve(session)
    assert encode(board_copy(state)) == before
    march_pending = session.data['pending']
    assert decode(march_pending['request'])['request_type'] == 'impetuosity_march'
    assert session.data['journal'] == []
    # Both full card texts precede even the first choice.
    first_display = output.getvalue()
    for card_id in (72, 4):
        for line in get_card_text(card_id, state['scenario']).splitlines():
            assert line in first_display

    march = {'origin': rc.MORINI, 'destination': rc.NERVII, 'warbands': 2}
    session.import_inbox({'decision_id': march_pending['id'], 'response': march})
    with pytest.raises(DecisionPending):
        _resolve(session)
    assert encode(board_copy(state)) == before
    assert state['event_modifiers'][FLAG]
    assert FREE_FORCE_KEY not in state
    assert len(session.data['journal']) == 1
    assert session.log == []
    pending = session.data['pending']
    request = decode(pending['request'])
    assert request['request_type'] == 'event_command'
    assert request['allowed_commands'] == [rc.CMD_BATTLE]
    assert request['allowed_regions'] == [rc.NERVII]
    pending_board = decode(pending['board'])
    assert count_pieces(pending_board, rc.NERVII, rc.BELGAE, rc.WARBAND) == 2
    assert count_pieces(pending_board, rc.NERVII, rc.BELGAE, rc.LEADER) == 0
    physical = pending_board['spaces'][rc.NERVII]['pieces'][rc.BELGAE]
    assert physical[rc.HIDDEN][rc.WARBAND] == 6
    assert physical[rc.LEADER] == rc.AMBIORIX
    displayed_board = format_board(pending_board)
    assert f'L({rc.AMBIORIX}),W:6[H6/R0/S0]' in displayed_board
    assert f'Impetuosity free Battle in {rc.NERVII}' in displayed_board
    assert f"{rc.BELGAE}' 2 {rc.WARBAND} [H2/R0/S0] participate." in displayed_board
    # The pending Battle exposes actual movement/flips, not fictitious losses
    # caused by restricting the Battle force to the two marched Warbands.
    second_display = output.getvalue()[len(first_display):]
    assert f'{rc.BELGAE} {rc.HIDDEN} {rc.WARBAND}: 4 -> 6' in second_display
    assert f'{rc.BELGAE} {rc.REVEALED} {rc.WARBAND}: 2 -> 0' in second_display
    assert f'{rc.BELGAE} {rc.HIDDEN} {rc.WARBAND}: 4 -> 2' not in second_display
    for card_id in (72, 4):
        for line in get_card_text(card_id, state['scenario']).splitlines():
            assert line in second_display

    saved = tmp_path / 'impetuosity.json'
    save_game(state, saved, meta=session.meta, log=session.log)
    restored, meta, log = load_game(saved)
    resumed, resumed_output = _session(restored, meta, log)
    chosen = ({'command': rc.CMD_BATTLE, 'regions': [rc.NERVII],
               'sa': 'No SA', 'sa_regions': [], 'details': {'battle_plan': [
                   {'region': rc.NERVII, 'target': rc.ROMANS}]}}
              if battle else {'decline': True})
    resumed.import_inbox({'decision_id': pending['id'], 'response': chosen})
    result = _resolve(resumed)
    resumed.finish()
    assert result[0]['executed']
    assert result[0]['warbands_marched'] == 2
    assert FLAG not in restored['event_modifiers']
    assert FREE_FORCE_KEY not in restored
    assert count_pieces_by_state(restored, rc.MORINI, rc.BELGAE,
                                 rc.WARBAND, rc.HIDDEN) == 3
    assert count_pieces_by_state(restored, rc.NERVII, rc.BELGAE,
                                 rc.WARBAND, rc.HIDDEN) == (4 if battle else 6)
    assert count_pieces_by_state(restored, rc.NERVII, rc.BELGAE,
                                 rc.WARBAND, rc.REVEALED) == (2 if battle else 0)
    assert count_pieces(restored, rc.NERVII, rc.BELGAE, rc.LEADER) == 1
    assert count_pieces(restored, rc.NERVII, rc.ROMANS, rc.AUXILIA) == (0 if battle else 1)
    assert len(log) == 2
    assert [decode(entry['assistant_response']) for entry in log] == [march, chosen]
    assert [entry['assistant_id'] for entry in log] == ['d000001', 'd000002']
    assert not resumed.data['journal'] and not resumed.data['queue']
    # March replays from its journal rather than reopening a third decision.
    assert resumed_output.getvalue().count('changes since your last decision') == 1
    committed = encode(board_copy(restored))
    assert _resolve(resumed) == []
    resumed.finish()
    assert encode(board_copy(restored)) == committed
    assert len(log) == 2

    # A fresh replay checks the same request/board signatures and exact RNG.
    replay, _ = _session(decode(before))
    replay.data['expected'] = [{'id': entry['assistant_id'],
                               'signature': entry['assistant_signature']}
                              for entry in log]
    replay.import_inbox([{'decision_id': entry['assistant_id'],
                         'response': decode(entry['assistant_response'])}
                        for entry in log])
    assert _resolve(replay) == result
    replay.finish()
    assert encode(board_copy(replay.state)) == committed
    assert replay.log == log
