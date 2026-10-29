"""Printed Spring choices survive the human menus and durable frontend."""

import copy
import io
import json
from types import SimpleNamespace

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import find_leader, get_leader_in_region, remove_piece
from fs_bot.cli import app
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.menus import set_board_hook
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.cli.spring import collect_leader
from fs_bot.engine.spring import (successor_request, spring_box_request,
                                 resolve_spring_box_entry, unlock_spring_box_entry)
from fs_bot.engine.game_engine import _action_transaction
from fs_bot.engine.winter import spring_phase
from fs_bot.state.setup import setup_scenario
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.tools import llm_seat
from fs_bot.tools.seat_session import SeatSession, board_copy


def _state():
    state = setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=13)
    state['non_player_factions'] = {rc.ARVERNI, rc.AEDUI, rc.BELGAE}
    remove_piece(state, find_leader(state, rc.ROMANS), rc.ROMANS, rc.LEADER)
    state['current_card'] = state['current_card_id'] = rc.WINTER_CARD
    state['played_cards'] = [rc.WINTER_CARD]
    state['next_card'], state['deck'] = 16, [16, rc.WINTER_CARD]
    return state


def test_cli_lists_every_legal_destination_without_choosing_or_rolling():
    state = _state()
    request = successor_request(state, rc.ROMANS)
    output = io.StringIO()
    before = encode(state)
    choice = request['legal_regions'].index(rc.PROVINCIA) + 1
    response = collect_leader(state, rc.ROMANS, request,
                              io.StringIO(f'bad\n999\n{choice}\n'), output)
    assert response == {'region': rc.PROVINCIA}
    assert encode(state) == before
    shown = output.getvalue()
    assert all(region in shown for region in request['legal_regions'])
    assert 'Placement is required' in shown and 'Leave in the Spring box' not in shown
    assert rc.SUCCESSOR in shown


def test_explicit_menu_default_does_not_consume_placement_randomness():
    state = _state()
    request = successor_request(state, rc.ROMANS)
    before = encode(state)
    default = len(request['legal_regions']) + 1
    assert collect_leader(state, rc.ROMANS, request, io.StringIO(f'{default}\n'),
                          io.StringIO()) == {'use_default': True}
    assert encode(state) == before


def test_cli_can_defer_named_entry_then_choose_an_empty_region_later():
    state = _state()
    state['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE}
    unlock_spring_box_entry(state)
    request = spring_box_request(state)
    output = io.StringIO()
    original_card = state['current_card']
    original_eligibility = copy.deepcopy(state['eligibility'])
    defer = len(request['legal_regions']) + 1
    later = request['legal_regions'].index(rc.BITURIGES) + 1
    stream = io.StringIO(f'{defer}\n{later}\n')
    state['decision_agent'] = make_cli_reactive([rc.ARVERNI], stream, output)
    assert resolve_spring_box_entry(state)['deferred']
    assert rc.VERCINGETORIX in state['spring_box_leaders']
    assert find_leader(state, rc.ARVERNI) is None
    assert resolve_spring_box_entry(state)['region'] == rc.BITURIGES
    assert get_leader_in_region(state, rc.BITURIGES, rc.ARVERNI) == rc.VERCINGETORIX
    assert rc.VERCINGETORIX not in state['spring_box_leaders']
    assert state['current_card'] == original_card
    assert state['eligibility'] == original_eligibility
    assert 'Leave in the Spring box for now' in output.getvalue()


def test_copied_spring_preview_does_not_consume_live_input_or_randomness():
    state = _state()
    session = SeatSession(state, {'seat': rc.ROMANS}, [], HumanTurnDisplay(io.StringIO()))
    state['decision_agent'] = session.reactive
    session.import_inbox([{'response': {'region': rc.PROVINCIA}}])
    before, queued = encode(board_copy(state)), copy.deepcopy(session.data)
    spring_phase(copy.deepcopy(state))
    assert encode(board_copy(state)) == before and session.data == queued
    def driver(*args):
        pass
    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    with _action_transaction(state, driver):
        spring_phase(state)
    session.finish()
    assert get_leader_in_region(state, rc.PROVINCIA, rc.ROMANS) == rc.SUCCESSOR
    assert len(session.log) == 1 and not session.data['queue']


def test_cli_inspection_then_eof_preserves_spring_board_and_rng():
    state = _state()
    state['decision_agent'] = make_cli_reactive([rc.ROMANS], io.StringIO('board\nb\n'),
                                               io.StringIO())
    before = encode(board_copy(state))
    inspected = []
    set_board_hook(lambda: inspected.append(encode(board_copy(state))))
    try:
        with pytest.raises(EOFError):
            spring_phase(state)
    finally:
        set_board_hook(None)
    assert len(inspected) == 2 and all(board == before for board in inspected)
    assert encode(board_copy(state)) == before


def test_real_cli_wrapper_displays_cards_and_changes_before_spring_choice(
        monkeypatch, tmp_path):
    state = _state()
    source, saved = tmp_path / 'source.json', tmp_path / 'saved.json'
    view = HumanTurnDisplay(io.StringIO())
    view.remember(state, [rc.ROMANS])
    save_game(state, source, meta={
        'scenario': state['scenario'], 'seed': 13,
        'faction_modes': {f: 'human' if f == rc.ROMANS else 'bot'
                          for f in (rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE)},
        'human_snapshots': encode(view.snapshots)}, log=[])
    def card(board, decision, *, execute):
        # Production app wrapper must show changes before its real collector.
        board['resources'][rc.ROMANS] += 1
        spring_phase(board)
        return {'card': board['current_card'], 'game_over': True}
    monkeypatch.setattr(app, 'play_card', card)
    output = io.StringIO()
    selected = successor_request(state, rc.ROMANS)['legal_regions'].index(rc.PROVINCIA) + 1
    assert app.main(['--load', str(source), '--save', str(saved)],
                    stdin=io.StringIO(f'board\n{selected}\n'), stdout=output) == 0
    final, _, log = load_game(saved)
    assert get_leader_in_region(final, rc.PROVINCIA, rc.ROMANS) == rc.SUCCESSOR
    assert any(entry.get('reactive') == 'spring_leader' for entry in log)
    shown = output.getvalue()
    assert 'Ambacti' in shown
    assert shown.index('Ambacti') < shown.index('Leader destination?')
    assert 'Resources' in shown and '+1' in shown


@pytest.mark.parametrize('invalid', [
    None, {}, {'defer': True}, {'region': rc.CISALPINA},
    {'use_default': 1}, {'use_default': 1.0},
    {'region': rc.PROVINCIA, 'use_default': True},
])
def test_file_frontend_spring_pending_invalid_save_resume_and_replay(
        tmp_path, capsys, invalid):
    state = _state()
    directory = tmp_path / 'live'
    directory.mkdir()
    display = HumanTurnDisplay(io.StringIO())
    display.remember(state, [rc.ROMANS])
    meta = {'seat': rc.ROMANS, 'scenario': state['scenario'], 'seed': 13,
            'human_snapshots': encode(display.snapshots)}
    session = SeatSession(state, meta, [], display)
    # Quarters is the earlier human decision in this actual Winter.
    session.data['queue'] = [{'response': {'use_default': True}}]
    save_game(state, directory / 'save.json', meta=meta, log=[])
    args = SimpleNamespace(dir=str(directory))
    assert llm_seat.cmd_play(args) == 0
    paused, paused_meta, log = load_game(directory / 'save.json')
    pending = copy.deepcopy(paused_meta['assistant_session']['pending'])
    request = decode(pending['request'])
    assert request['kind'] == 'spring_leader' and request['leader'] == rc.SUCCESSOR
    assert request['can_defer'] is False
    assert encode(paused) == encode(state)
    assert log == [] and paused_meta['assistant_session']['journal']
    shown = capsys.readouterr().out
    assert 'Ambacti' in shown and 'spring_leader' in shown

    args.decision_id = pending['id']
    args.response = json.dumps(invalid)
    assert llm_seat.cmd_submit(args) == 0
    refused, refused_meta, refused_log = load_game(directory / 'save.json')
    assert encode(refused) == encode(paused) and refused_log == log
    assert refused_meta['assistant_session']['pending'] == pending
    args.response = json.dumps({'region': rc.PROVINCIA})
    assert llm_seat.cmd_submit(args) == 0
    resolved, final_meta, final_log = load_game(directory / 'save.json')
    assert get_leader_in_region(resolved, rc.PROVINCIA, rc.ROMANS) == rc.SUCCESSOR
    choices = [entry for entry in final_log if entry.get('reactive') == 'spring_leader']
    assert len(choices) == 1 and decode(choices[0]['response']) == {'region': rc.PROVINCIA}
    assert not final_meta['assistant_session']['journal']
    args.output_dir = str(tmp_path / 'replayed')
    assert llm_seat.cmd_replay(args) == 0
    replayed, _, _ = load_game(tmp_path / 'replayed' / 'save.json')
    assert encode(replayed) == encode(resolved)
    assert 'Replay verified' in capsys.readouterr().out
