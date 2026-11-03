"""Durable Roman A20/A58 acceptance, staged current-board choices, and replay."""
import io
import json
from types import SimpleNamespace

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine.game_engine import ACTION_EVENT
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.tools import llm_seat
from fs_bot.tools.seat_session import SeatSession
from fs_bot.tests.test_roman_event_grants import state, battle, seize


@pytest.mark.parametrize('card', ['A20', 'A58'])
@pytest.mark.parametrize('scenario', rc.ARIOVISTUS_SCENARIOS)
def test_file_session_staged_invalid_default_stale_save_resume_and_replay(tmp_path, capsys, card, scenario):
    st = state(card, scenario)
    st['next_card'], st['played_cards'], st['deck'] = None, [card], []
    for faction in st['eligibility']:
        st['eligibility'][faction] = rc.ELIGIBLE if faction == rc.ROMANS else rc.INELIGIBLE
    region = rc.VENETI if card == 'A20' else rc.NERVII
    place_piece(st, region, rc.ROMANS, rc.FORT)
    target = rc.ARVERNI if card == 'A20' else rc.BELGAE
    place_piece(st, region, target, rc.WARBAND)
    directory = tmp_path / 'live'
    directory.mkdir()
    display = HumanTurnDisplay(io.StringIO())
    display.remember(st, [rc.ROMANS])
    meta = {'seat': rc.ROMANS, 'scenario': scenario, 'seed': 7,
            'human_snapshots': encode(display.snapshots)}
    SeatSession(st, meta, [], display)
    save_game(st, directory / 'save.json', meta=meta, log=[])
    args = SimpleNamespace(dir=str(directory))

    def saved():
        return load_game(directory / 'save.json')
    def pending():
        return saved()[1]['assistant_session']['pending']
    def submit(response, decision_id=None):
        args.response = json.dumps(response)
        args.decision_id = decision_id if decision_id is not None else pending()['id']
        assert llm_seat.cmd_submit(args) == 0
    def decline_windows():
        while pending() and decode(pending()['request'])['kind'] == 'voluntary_removal':
            submit({'done': True})

    assert llm_seat.cmd_play(args) == 0
    before = encode(saved()[0])
    submit({'action': ACTION_EVENT, 'player_action': {'command': 'Event', 'details': {
        'card_id': card, 'text_preference': rc.EVENT_UNSHADED}}})
    decline_windows()
    first = pending()
    assert decode(first['request'])['request_type'] == 'roman_event_accept'
    assert count_pieces(decode(first['board']), region, target) == 1
    assert encode(saved()[0]) == before
    # Missing and malformed acceptance preserve the stable pending ID.
    assert llm_seat.cmd_play(args) == 0
    assert pending() == first
    submit({'accept': 1})
    assert pending() == first and encode(saved()[0]) == before
    args.decision_id, args.response = 'd999999', json.dumps({'accept': True})
    bytes_before = (directory / 'save.json').read_bytes()
    assert llm_seat.cmd_submit(args) == 2
    assert (directory / 'save.json').read_bytes() == bytes_before
    submit({'accept': True})
    decline_windows()
    second = pending()
    request = decode(second['request'])
    assert second['id'] != first['id']
    assert request['request_type'] == ('roman_event_seize' if card == 'A20' else 'roman_event_battle')
    assert encode(saved()[0]) == before
    if card == 'A20':
        assert count_pieces(decode(second['board']), region, rc.ARVERNI) == 0
    else:
        # Static-only Roman Battle is legal; NP priorities select none, so
        # an explicit default cannot silently skip the accepted component.
        submit({'use_default': True})
        assert pending() == second
    submit({'decline': True})
    assert pending() == second
    submit({'command': rc.CMD_BATTLE, 'regions': [rc.PROVINCIA],
            'details': {'battle_plan': [{'region': rc.PROVINCIA, 'target': rc.GERMANS}]}})
    assert pending() == second and encode(saved()[0]) == before
    if card == 'A58':
        submit(battle(region))
        decline_windows()
        second = pending()
        assert decode(second['request'])['request_type'] == 'roman_event_seize'
    request = decode(second['request'])
    selected = request['dispersible_tribes'][region][-1:]
    submit(seize([region], {region: selected}))
    decline_windows()
    resolved, final_meta, log = saved()
    assert not final_meta['assistant_session']['pending']
    assert not final_meta['assistant_session']['journal']
    assert resolved['tribes'][selected[0]]['status'] == rc.DISPERSED
    accepted = [decode(entry['assistant_request']).get('request_type') for entry in log
                if entry.get('reactive') == 'free_action']
    assert accepted == (['roman_event_accept', 'roman_event_seize'] if card == 'A20'
                        else ['roman_event_accept', 'roman_event_battle', 'roman_event_seize'])
    args.output_dir = str(tmp_path / 'replayed')
    assert llm_seat.cmd_replay(args) == 0
    replayed, _, _ = load_game(tmp_path / 'replayed' / 'save.json')
    assert encode(replayed) == encode(resolved)
    assert 'Replay verified' in capsys.readouterr().out
