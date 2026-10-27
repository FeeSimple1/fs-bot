"""Card 16 human decisions occur after the die and retain physical choices."""
import copy
import io
import json
from types import SimpleNamespace

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece
from fs_bot.cards.card_text import get_card_text
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.human_plan import _collect_event_params
from fs_bot.cli.menus import prompt_action, set_board_hook
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.execute import _execute_event
from fs_bot.engine.game_engine import ACTION_EVENT, _action_transaction
from fs_bot.engine.moves import preview_player_action, validate_player_action
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state
from fs_bot.tools import llm_seat
from fs_bot.tools.seat_session import SeatSession, board_copy


def _state(scenario=rc.SCENARIO_PAX_GALLICA, seed=5):
    state = build_initial_state(scenario, seed=seed)
    state['current_card'], state['current_card_id'] = 16, 16
    state['next_card'], state['played_cards'], state['deck'] = None, [16], []
    state['non_player_factions'] = {rc.ARVERNI, rc.AEDUI, rc.BELGAE, rc.GERMANS}
    for faction in state['eligibility']:
        state['eligibility'][faction] = rc.ELIGIBLE if faction == rc.ROMANS else rc.INELIGIBLE
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 3,
                piece_state=rc.REVEALED)
    return state


def _event():
    return {'command': 'Event', 'regions': [], 'sa': 'No SA', 'sa_regions': [],
            'details': {'card_id': 16, 'text_preference': rc.EVENT_SHADED}}


def _choice(count=3, visibility=rc.REVEALED, region=rc.PROVINCIA):
    return {'removal_choice': 'three', 'removals': [
        {'region': region, 'piece_state': visibility, 'count': count}]}


def test_actual_shaded_turn_menu_defers_choices_and_rng_until_execution():
    state = _state()
    output = io.StringIO()
    stream = io.StringIO('Event\n2\nuntouched\n')
    before = encode(state)
    decision = prompt_action(state, rc.ROMANS, [ACTION_EVENT],
                             '1st_eligible', stream, output)
    assert decision == {'action': ACTION_EVENT, 'player_action': _event()}
    assert stream.readline() == 'untouched\n'
    assert encode(state) == before
    assert 'auxilia_removal_regions' not in output.getvalue()
    assert 'removal_choice:' not in output.getvalue()
    assert get_card_text(16, state['scenario']).splitlines()[0] in output.getvalue()


@pytest.mark.parametrize('seed,menu,roll,number', [(5, 2, 5, 3), (5, 1, 5, 5), (2, 1, 1, 1)])
def test_reactive_cli_shows_roll_then_selects_exact_visibility_anywhere(seed, menu, roll, number):
    state = _state(seed=seed)
    output = io.StringIO()
    # Select the exact physical losses after the actual roll. Exhausting
    # Provincia offers the remaining Region's pieces for the fifth loss.
    stream = io.StringIO(f'{menu}\n' + '1\n' * number + 'untouched\n')
    state['decision_agent'] = make_cli_reactive([rc.ROMANS], stream, output)
    result = _execute_event(state, rc.ROMANS, _event(), human=True)
    assert result['executed']
    assert state['event_modifiers']['card_16_die_roll'] == roll
    assert count_pieces_by_state(state, rc.PROVINCIA, rc.ROMANS,
                                 rc.AUXILIA, rc.REVEALED) == 3 - min(number, 3)
    assert count_pieces_by_state(state, rc.SEQUANI, rc.ROMANS,
                                 rc.AUXILIA, rc.HIDDEN) == 4 - max(number - 3, 0)
    assert stream.readline() == 'untouched\n'
    shown = output.getvalue()
    assert f'die roll: {roll}' in shown and rc.REVEALED in shown and rc.PROVINCIA in shown
    assert shown.index(f'die roll: {roll}') < shown.index('Remove the rolled number')


def test_reactive_cli_board_inspection_and_eof_preserve_live_board_and_rng():
    state = _state()
    output = io.StringIO()
    inspections = []
    state['decision_agent'] = make_cli_reactive(
        [rc.ROMANS], io.StringIO('board\n'), output)
    before = encode(board_copy(state))
    set_board_hook(lambda: inspections.append(encode(board_copy(state))))
    try:
        with pytest.raises(EOFError):
            with _action_transaction(state, lambda *args: None):
                _execute_event(state, rc.ROMANS, _event(), human=True)
    finally:
        set_board_hook(None)
    assert len(inspections) == 1
    assert inspections[0] != before  # the displayed decision follows the roll
    assert encode(board_copy(state)) == before


@pytest.mark.parametrize('scenario', [rc.SCENARIO_PAX_GALLICA, rc.SCENARIO_ARIOVISTUS])
def test_preview_does_not_consume_live_reactive_input_or_rng(scenario):
    state = _state(scenario)
    display = HumanTurnDisplay(io.StringIO())
    session = SeatSession(state, {'seat': rc.ROMANS}, [], display)
    state['decision_agent'] = session.reactive
    session.import_inbox([{'response': _choice()}])
    before = encode(board_copy(state))
    queued = copy.deepcopy(session.data)
    assert validate_player_action(state, rc.ROMANS, _event())[0]
    ok, _, preview = preview_player_action(state, rc.ROMANS, _event())
    assert ok
    assert encode(board_copy(state)) == before
    assert session.data == queued and session.log == []
    assert encode(board_copy(preview)) != before


@pytest.mark.parametrize('response', [
    {'use_default': True},
    {'removal_choice': 'roll', 'removals': [
        {'region': rc.PROVINCIA, 'piece_state': rc.REVEALED, 'count': 3},
        {'region': rc.SEQUANI, 'piece_state': rc.HIDDEN, 'count': 2}]},
])
def test_durable_postroll_choice_overrides_predeclared_legacy_params(response):
    state = _state()
    session = SeatSession(state, {'seat': rc.ROMANS}, [], HumanTurnDisplay(io.StringIO()))
    state['decision_agent'] = session.reactive
    session.import_inbox([{'response': response}])
    action = _event()
    action['details']['event_params'] = {
        'removal_choice': 'three', 'auxilia_removal_regions': [[rc.SEQUANI, 3]]}

    def callback(*args):
        pass
    callback.transaction_checkpoint = session.checkpoint
    callback.transaction_restore = session.restore
    with _action_transaction(state, callback):
        result = _execute_event(state, rc.ROMANS, action, human=True)
    session.finish()
    assert result['executed']
    assert sum(count_pieces(state, region, rc.ROMANS, rc.AUXILIA)
               for region in (rc.PROVINCIA, rc.SEQUANI)) == 2
    assert len(session.log) == 1
    request = decode(session.log[0]['assistant_request'])
    assert request['kind'] == 'ambacti_removal' and request['roll'] == 5


@pytest.mark.parametrize('invalid_response', [
    _choice(count=4), {'use_default': 1}, {'use_default': 1.0},
])
def test_file_frontend_postroll_pause_invalid_stale_resume_and_replay(
        tmp_path, capsys, invalid_response):
    state = _state()
    path = tmp_path / 'live'
    path.mkdir()
    display = HumanTurnDisplay(io.StringIO())
    display.remember(state, [rc.ROMANS])
    meta = {'seat': rc.ROMANS, 'scenario': state['scenario'], 'seed': 5,
            'human_snapshots': encode(display.snapshots)}
    SeatSession(state, meta, [], display)
    save_game(state, path / 'save.json', meta=meta, log=[])
    args = SimpleNamespace(dir=str(path))
    assert llm_seat.cmd_play(args) == 0
    before, _, _ = load_game(path / 'save.json')
    args.response = json.dumps({'action': ACTION_EVENT, 'player_action': _event()})
    assert llm_seat.cmd_submit(args) == 0
    paused, paused_meta, paused_log = load_game(path / 'save.json')
    pending = paused_meta['assistant_session']['pending']
    request = decode(pending['request'])
    assert request['kind'] == 'ambacti_removal'
    assert request['roll'] == 5 and request['removal_counts'] == {'roll': 5, 'three': 3}
    assert encode(paused) == encode(before)
    assert paused_log == []
    assert len(paused_meta['assistant_session']['journal']) == 1
    assert decode(pending['board'])['rng'].getstate() != paused['rng'].getstate()
    shown = capsys.readouterr().out
    assert 'Ambacti' in shown and '"roll": 5' in shown

    args.decision_id = 'd999999'
    args.response = json.dumps(_choice())
    old_save = (path / 'save.json').read_bytes()
    assert llm_seat.cmd_submit(args) == 2
    assert (path / 'save.json').read_bytes() == old_save
    args.decision_id = pending['id']
    args.response = json.dumps(invalid_response)
    assert llm_seat.cmd_submit(args) == 0
    rejected, rejected_meta, rejected_log = load_game(path / 'save.json')
    assert encode(rejected) == encode(paused)
    assert rejected_meta['assistant_session']['pending'] == pending
    assert rejected_log == []
    assert len(rejected_meta['assistant_session']['journal']) == 1

    args.response = json.dumps(_choice())
    assert llm_seat.cmd_submit(args) == 0
    resolved, final_meta, log = load_game(path / 'save.json')
    assert count_pieces(resolved, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(resolved, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 4
    assert resolved['event_modifiers']['card_16_die_roll'] == 5
    assert len(log) == 2
    assert decode(log[1]['assistant_response']) == _choice()
    assert not final_meta['assistant_session']['pending']
    assert not final_meta['assistant_session']['journal']
    args.output_dir = str(tmp_path / 'replayed')
    assert llm_seat.cmd_replay(args) == 0
    replayed, _, _ = load_game(tmp_path / 'replayed' / 'save.json')
    assert encode(replayed) == encode(resolved)
    assert 'Replay verified' in capsys.readouterr().out


def test_unshaded_menu_offers_only_present_roman_regions():
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=5)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.FORT)
    output = io.StringIO()
    before = encode(state)
    result = _collect_event_params(state, rc.BELGAE, 16, False,
                                   io.StringIO('1\n'), output)
    assert result['target_region'] in (rc.PROVINCIA, rc.SEQUANI)
    shown = output.getvalue()
    assert rc.PROVINCIA in shown and rc.SEQUANI in shown
    assert rc.BRITANNIA not in shown and rc.AEDUI_REGION not in shown
    assert '6' in shown and '4' in shown
    assert encode(state) == before


@pytest.mark.parametrize('leader,limit', [(rc.CAESAR, 6), (rc.SUCCESSOR, 4)])
def test_unshaded_menu_names_caesar_and_shows_partial_available_pool(leader, limit):
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=5)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 18)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=leader)
    output = io.StringIO()
    params = _collect_event_params(state, rc.ROMANS, 16, False,
                                   io.StringIO('2\n'), output)
    assert params == {'target_region': rc.SEQUANI}
    assert f'{limit} allowed; 2 Available' in output.getvalue()
    if leader == rc.SUCCESSOR:
        assert 'with Caesar' not in output.getvalue()
    action = _event()
    action['details'] = {'card_id': 16, 'text_preference': rc.EVENT_UNSHADED,
                         'event_params': params}
    assert _execute_event(state, rc.ROMANS, action, human=True)['executed']
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 2
