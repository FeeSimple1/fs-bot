"""Camulogenus choices cross real terminal and durable human boundaries."""

from copy import deepcopy
from io import StringIO
import json
from types import SimpleNamespace

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece
from fs_bot.cards.card_text import get_card_text
from fs_bot.cli.display import HumanTurnDisplay, format_board
from fs_bot.cli.free_actions import collect_free_action
from fs_bot.engine.execute import _execute_event
from fs_bot.engine.game_engine import ACTION_EVENT, _action_transaction
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools import llm_seat
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def position():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=7003)
    state.update(current_card=70, next_card=35, card_edition='original',
                 executing_faction=rc.BELGAE,
                 non_player_factions={rc.ARVERNI, rc.AEDUI, rc.BELGAE})
    state['resources'][rc.ROMANS] = 0
    for region in (rc.NERVII, rc.MORINI):
        place_piece(state, region, rc.ROMANS, rc.LEGION, 2, from_legions_track=True)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, 1)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, 2, piece_state=rc.REVEALED)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 1)
    place_piece(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND, 1)
    place_piece(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 1)
    assert validate_state(state) == []
    return state


def plan():
    return {'destination': rc.ATREBATES, 'marches': [
        {'origin': rc.NERVII, 'route': [rc.ATREBATES],
         'legions': 1, 'auxilia': 1, 'caesar': False},
        {'origin': rc.MORINI, 'route': [rc.ATREBATES],
         'legions': 1, 'auxilia': 0, 'caesar': False},
    ]}


def event(state, executor=rc.BELGAE):
    action = {'command': rc.FIRST_DID_EVENT, 'regions': [], 'sa': 'No SA',
              'sa_regions': [], 'details': {'card_id': 70,
                  'text_preference': rc.EVENT_UNSHADED, 'event_params': {}}}
    return _execute_event(state, executor, action,
                          human=executor not in state.get('non_player_factions', ()))


def session(state, meta=None, log=None):
    output = StringIO()
    ses = SeatSession(state, {'seat': rc.ROMANS} if meta is None else meta,
                      [] if log is None else log, HumanTurnDisplay(output))
    state['decision_agent'] = ses.reactive
    ses.output = output
    return ses


def step(ses):
    def driver(*args):
        pass
    driver.transaction_checkpoint = ses.checkpoint
    driver.transaction_restore = ses.restore
    with _action_transaction(ses.state, driver):
        return event(ses.state)


def pending(ses):
    with pytest.raises(DecisionPending):
        step(ses)
    return decode(ses.data['pending']['request'])


def submit(ses, response):
    ses.import_inbox({'decision_id': ses.data['pending']['id'], 'response': response})


def test_terminal_two_origins_share_legion_limit_and_allow_board_at_every_menu():
    from fs_bot.cards.camulogenus import make_request
    state = position()
    before = encode(state)
    output = StringIO()
    response = collect_free_action(state, rc.ROMANS, make_request(state), StringIO(
        'board\nChoose destination and March groups\nb\nAtrebates\n'
        'Nervii\n2 Legions\n1 Auxilia\nNervii → Atrebates\n'
        'Morini\n2 Legions\n0 Auxilia\nMorini → Atrebates\n'
        'board\nFinish March selection; continue to Battle\n'), output)
    expected = plan()
    expected['marches'][0]['legions'] = expected['marches'][1]['legions'] = 2
    assert response == expected
    assert output.getvalue().count('AVAILABLE PIECES') == 3
    assert '0 Legions remaining in the limit' in output.getvalue()
    assert ') Decline' not in output.getvalue()
    assert 'No pieces may be dropped off' in output.getvalue()
    assert encode(state) == before


def test_terminal_whole_benefit_decline_and_named_destination_text():
    from fs_bot.cards.roman_event_grants import accept_request
    state = position()
    output = StringIO()
    response = collect_free_action(state, rc.ROMANS, accept_request(70),
                                   StringIO('b\nDecline\n'), output)
    assert response == {'decline': True}
    assert 'free March up to 4 Legions and any Auxilia' in output.getvalue()
    assert 'Atrebates, Carnutes, or Mandubii' in output.getvalue()
    assert 'AVAILABLE PIECES' in output.getvalue()


def test_terminal_accepts_battle_destination_without_moving_or_flipping_residents():
    from fs_bot.cards.camulogenus import make_request
    state = position()
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, piece_state=rc.REVEALED)
    before = encode(state)
    response = collect_free_action(state, rc.ROMANS, make_request(state), StringIO(
        'Choose destination and March groups\nAtrebates\n'
        'Finish March selection; continue to Battle\n'), StringIO())
    assert response == {'destination': rc.ATREBATES, 'marches': []}
    assert encode(state) == before


def test_terminal_cooperation_applies_only_to_origins_actually_selected():
    from fs_bot.cards.camulogenus import make_request
    from fs_bot.cards.card_effects import execute_event
    state = position()
    for region in (rc.NERVII, rc.MORINI):
        place_piece(state, region, rc.AEDUI, rc.WARBAND, 2)
    execute_event(state, 38)
    before = encode(state)
    response = collect_free_action(state, rc.ROMANS, make_request(state), StringIO(
        'Choose destination and March groups\ny\nNervii\nMorini\nAtrebates\n'
        'Nervii\n0 Legions\n4 Auxilia\nNervii → Atrebates\n'
        'Finish March selection; continue to Battle\n'), StringIO())
    assert response['diviciacus_regions'] == [rc.NERVII]
    assert response['marches'] == [{'origin': rc.NERVII, 'route': [rc.ATREBATES],
                                   'legions': 0, 'auxilia': 4, 'caesar': False}]
    assert encode(state) == before


def test_durable_other_executor_roman_may_decline_before_movement():
    state = position()
    before = encode(board_copy(state))
    ses = session(state)
    request = pending(ses)
    assert request['request_type'] == 'roman_event_accept'
    assert request['faction'] == rc.ROMANS and request['card_id'] == 70
    assert encode(board_copy(state)) == before
    submit(ses, {'decline': True})
    result = step(ses)
    ses.finish()
    assert result['executed']
    assert count_pieces(state, rc.NERVII, rc.ROMANS, rc.LEGION) == 2
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS) == 0
    assert len(ses.log) == 1


def test_durable_invalid_inputs_keep_request_board_rng_and_journal_stable():
    state = position()
    ses = session(state)
    ses.display.remember(state, [rc.ROMANS])
    state['resources'][rc.ROMANS] = 1
    before = encode(board_copy(state))
    pending(ses)
    original = deepcopy(ses.data['pending'])
    for response in (None, {'accept': 1}, {'accept': False}, {'accept': True, 'extra': 1}):
        submit(ses, response)
        pending(ses)
        assert ses.error and ses.data['pending'] == original
        assert encode(board_copy(state)) == before
        assert not ses.data['journal'] and not ses.log
    text = ses.output.getvalue()
    assert 'Romans Resources: 0 -> 1' in text
    for card in (70, 35):
        assert all(line in text for line in get_card_text(
            card, state['scenario'], 'original').splitlines())
    submit(ses, {'accept': True})
    request = pending(ses)
    assert request['request_type'] == 'camulogenus_march'
    original = deepcopy(ses.data['pending'])
    journal = deepcopy(ses.data['journal'])
    illegal = [None, {'decline': True}, {'use_default': 1},
               dict(plan(), destination=rc.PROVINCIA), dict(plan(), sa=rc.SA_SCOUT)]
    too_many = plan()
    too_many['marches'][0]['legions'] = 5
    illegal.append(too_many)
    dropoff = plan()
    dropoff['marches'][0]['dropoffs'] = {rc.NERVII: {rc.LEGION: 1}}
    illegal.append(dropoff)
    for response in illegal:
        submit(ses, response)
        pending(ses)
        assert ses.error and ses.data['pending'] == original
        assert ses.data['journal'] == journal
        assert encode(board_copy(state)) == before


def test_durable_save_at_march_and_visibility_then_battle_replays_exactly(tmp_path, capsys):
    state = position()
    initial = deepcopy(state)
    ses = session(state)
    before = encode(board_copy(state))
    pending(ses)
    submit(ses, {'accept': True})
    assert pending(ses)['request_type'] == 'camulogenus_march'
    save_game(state, tmp_path / 'save.json', meta=ses.meta, log=ses.log)
    llm_seat.cmd_board(SimpleNamespace(dir=str(tmp_path)))
    assert format_board(decode(ses.data['pending']['board'])) in capsys.readouterr().out
    restored, meta, log = load_game(tmp_path / 'save.json', validate=True)
    resumed = session(restored, meta, log)
    assert resumed.data['pending'] == ses.data['pending']
    submit(resumed, plan())
    request = pending(resumed)
    assert request['kind'] == 'march_cohort' and request['region'] == rc.NERVII
    assert encode(board_copy(restored)) == before
    submit(resumed, {'counts': {rc.REVEALED: 1}})
    request = pending(resumed)
    assert request['request_type'] == 'fixed_event_battle'
    moved = decode(resumed.data['pending']['board'])
    assert count_pieces(moved, rc.ATREBATES, rc.ROMANS, rc.LEGION) == 2
    assert count_pieces_by_state(moved, rc.NERVII, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 1
    assert count_pieces_by_state(moved, rc.NERVII, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 1
    assert encode(board_copy(restored)) == before
    submit(resumed, {'region': rc.ATREBATES, 'defender': rc.AEDUI})
    while True:
        try:
            result = step(resumed)
            break
        except DecisionPending:
            request = decode(resumed.data['pending']['request'])
            assert request['request_type'] == 'retreat_into_control'
            submit(resumed, False)
    resumed.finish()
    assert result['executed'] and restored['resources'][rc.ROMANS] == 0
    assert count_pieces(restored, rc.ATREBATES, rc.BELGAE, rc.WARBAND) == 1
    records = iter(log)
    def replay(live, faction, request):
        record = next(records)
        assert decode(record['assistant_request']) == dict(request, faction=faction)
        return decode(record['assistant_response'])
    initial['decision_agent'] = replay
    assert event(initial) == result
    assert next(records, None) is None
    assert encode(board_copy(initial)) == encode(board_copy(restored))
    assert validate_state(restored) == []


def test_file_session_public_submit_and_replay_for_camulogenus(tmp_path, capsys):
    state = position()
    state.update(next_card=None, played_cards=[70], deck=[])
    for faction in state['eligibility']:
        state['eligibility'][faction] = rc.ELIGIBLE if faction == rc.ROMANS else rc.INELIGIBLE
    directory = tmp_path / 'live'
    directory.mkdir()
    meta = {'seat': rc.ROMANS, 'scenario': state['scenario'], 'seed': 7003}
    SeatSession(state, meta, [], HumanTurnDisplay(StringIO()))
    save_game(state, directory / 'save.json', meta=meta, log=[])
    args = SimpleNamespace(dir=str(directory))
    def saved():
        return load_game(directory / 'save.json')
    def current():
        return saved()[1]['assistant_session']['pending']
    def send(response):
        args.decision_id, args.response = current()['id'], json.dumps(response)
        assert llm_seat.cmd_submit(args) == 0
    def windows():
        while current() and decode(current()['request'])['kind'] == 'voluntary_removal':
            send({'done': True})
    assert llm_seat.cmd_play(args) == 0
    send({'action': ACTION_EVENT, 'player_action': {'command': 'Event', 'details': {
        'card_id': 70, 'text_preference': rc.EVENT_UNSHADED}}})
    windows()
    assert decode(current()['request'])['request_type'] == 'roman_event_accept'
    send({'accept': True})
    windows()
    assert decode(current()['request'])['request_type'] == 'camulogenus_march'
    old = deepcopy(current())
    assert llm_seat.cmd_play(args) == 0 and current() == old
    send({'decline': True})
    assert current() == old
    send(plan())
    windows()
    assert decode(current()['request'])['kind'] == 'march_cohort'
    send({'counts': {rc.REVEALED: 1}})
    windows()
    assert decode(current()['request'])['request_type'] == 'fixed_event_battle'
    send({'region': rc.ATREBATES, 'defender': rc.AEDUI})
    windows()
    while current():
        assert decode(current()['request'])['request_type'] == 'retreat_into_control'
        send(False)
        windows()
    final, final_meta, log = saved()
    assert not final_meta['assistant_session']['pending']
    assert not final_meta['assistant_session']['journal']
    assert any(decode(e.get('assistant_request', {})).get('request_type') == 'camulogenus_march'
               for e in log)
    args.output_dir = str(tmp_path / 'replayed')
    assert llm_seat.cmd_replay(args) == 0
    replayed, _, _ = load_game(tmp_path / 'replayed' / 'save.json')
    assert encode(replayed) == encode(final)
    assert 'Replay verified' in capsys.readouterr().out
