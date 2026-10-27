"""Council private decisions survive real human/session execution boundaries.

Card Reference 47 grants its selected beneficiaries the next two *facedown*
cards. Chapter 2.2 already reveals the draw deck's first card to everyone.
These tests keep the trusted save/journal separate from public board output.
"""
import copy
import io
import json
import re

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.cards.card_data import get_card
from fs_bot.cards.card_text import get_card_text
from fs_bot.cli.display import HumanTurnDisplay, format_board, snapshot_state
from fs_bot.cli.human_plan import _collect_event_params
from fs_bot.cli.menus import set_board_hook
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.execute import _execute_event
from fs_bot.engine.game_engine import _action_transaction
from fs_bot.engine.moves import preview_player_action, validate_player_action
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state
from fs_bot.tools.llm_seat import _show_pending
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def _state():
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=47)
    state['current_card'] = state['current_card_id'] = 47
    state['next_card'], state['deck'], state['played_cards'] = 1, [1, 35, 62, 3], [47]
    state['non_player_factions'] = set()
    place_piece(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND, 1)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 1)
    place_piece(state, rc.PROVINCIA, rc.AEDUI, rc.WARBAND, 2)
    return state


def _selection():
    return {'region': rc.SEQUANI, 'target_factions': [rc.ROMANS, rc.AEDUI]}


def _event(params=None):
    details = {'card_id': 47, 'text_preference': rc.EVENT_UNSHADED}
    if params is not None:
        details['event_params'] = params
    return {'command': 'Event', 'regions': [], 'sa': 'No SA',
            'sa_regions': [], 'details': details}


def _session(state=None, meta=None, log=None):
    state = state if state is not None else _state()
    meta = meta if meta is not None else {'seat': rc.AEDUI, 'scenario': state['scenario'], 'seed': 47}
    session = SeatSession(state, meta, log if log is not None else [],
                          HumanTurnDisplay(io.StringIO()))

    def agent(board, faction, request):
        if faction == rc.AEDUI:
            return session.reactive(board, faction, request)
        # Another human beneficiary makes an explicit legal choice. Only the
        # Aedui seat is persisted by this particular file-based frontend.
        return {'decline': True}

    state['decision_agent'] = agent
    return session


def _driver(session):
    def callback(*args):
        pass
    callback.transaction_checkpoint = session.checkpoint
    callback.transaction_restore = session.restore
    return callback


def _run(session, params=None):
    with _action_transaction(session.state, _driver(session)):
        return _execute_event(session.state, rc.AEDUI, _event(params), human=True)


def _private_ids(request):
    return [entry['card_id'] for entry in request['private_cards']]


def _assert_public_without_peek(state, result=None):
    public = format_board(state) + json.dumps(encode(snapshot_state(state)), sort_keys=True)
    if result is not None:
        public += json.dumps(encode(result), sort_keys=True)
    assert 'private_cards' not in public
    for card_id in (35, 62):
        assert get_card(card_id, state['scenario']).title not in public


def test_selection_pending_contains_no_private_cards_and_preserves_live_state():
    session = _session()
    before = encode(board_copy(session.state))
    with pytest.raises(DecisionPending):
        _run(session)
    assert encode(board_copy(session.state)) == before
    pending = session.data['pending']
    request = decode(pending['request'])
    assert request['kind'] == 'council_selection'
    assert request['faction'] == rc.AEDUI
    assert 'private_cards' not in request
    assert not session.data['journal'] and not session.log
    _assert_public_without_peek(decode(pending['board']))


def test_accepted_selection_private_pending_save_resume_and_replay(tmp_path, capsys):
    session = _session()
    origin = copy.deepcopy(board_copy(session.state))
    session.import_inbox([{'response': _selection()}])
    with pytest.raises(DecisionPending):
        _run(session)
    assert encode(board_copy(session.state)) == encode(origin)
    assert len(session.data['journal']) == 1 and session.log == []
    pending = copy.deepcopy(session.data['pending'])
    request = decode(pending['request'])
    assert request['kind'] == 'council_choice' and request['faction'] == rc.AEDUI
    assert _private_ids(request) == [35, 62]
    for card in request['private_cards']:
        assert card['text'] == get_card_text(card['card_id'], session.state['scenario'])
    assert request['max_regions'] == 1 and request['with_sa'] is False and request['free'] is True
    _assert_public_without_peek(decode(pending['board']))
    _show_pending(pending)
    shown = capsys.readouterr().out
    assert get_card(35, session.state['scenario']).title in shown
    assert get_card(62, session.state['scenario']).title in shown

    save_game(session.state, tmp_path / 'paused.json', meta=session.meta, log=session.log)
    restored, meta, log = load_game(tmp_path / 'paused.json')
    resumed = _session(restored, meta, log)
    resumed.import_inbox({'decision_id': pending['id'], 'response': {'choice': 'eligible'}})
    result = _run(resumed)
    resumed.finish()
    assert result['executed']
    assert resumed.state['eligibility'][rc.AEDUI] == rc.ELIGIBLE
    assert [entry['reactive'] for entry in resumed.log] == ['council_selection', 'council_choice']
    assert not resumed.data['pending'] and not resumed.data['journal'] and not resumed.data['queue']
    _assert_public_without_peek(resumed.state, result)

    replay = _session(origin)
    replay.data['queue'] = [SeatSession._inbox_entry(entry) for entry in resumed.log]
    replay.data['expected'] = [{'id': entry['assistant_id'], 'signature': entry['assistant_signature']}
                               for entry in resumed.log]
    assert _run(replay) == result
    replay.finish()
    assert encode(board_copy(replay.state)) == encode(board_copy(resumed.state))
    assert replay.log == resumed.log


@pytest.mark.parametrize('response', [None, {}, {'choice': 'not an option'},
                                     {'choice': 'eligible', 'decline': True},
                                     {'decline': 1}, {'decline': 1.0},
                                     {'use_default': 1}, {'use_default': 1.0},
                                     {'command': rc.CMD_MARCH, 'sa': rc.SA_SUBORN,
                                      'regions': [rc.PROVINCIA], 'details': {}}])
def test_bad_beneficiary_response_retains_pending_id_input_board_and_rng(response):
    session = _session()
    before = encode(board_copy(session.state))
    with pytest.raises(DecisionPending):
        _run(session, _selection())
    pending = copy.deepcopy(session.data['pending'])
    session.import_inbox({'decision_id': pending['id'], 'response': response})
    queued = copy.deepcopy(session.data['queue'])
    with pytest.raises(DecisionPending):
        _run(session, _selection())
    assert session.error
    assert session.data['pending'] == pending
    assert session.data['queue'] == queued
    assert session.data['journal'] == [] and session.log == []
    assert encode(board_copy(session.state)) == before


@pytest.mark.parametrize('response', [
    {'region': rc.SEQUANI, 'target_factions': [rc.AEDUI]},
    {'region': rc.SEQUANI, 'target_factions': [rc.AEDUI, rc.AEDUI]},
    {'region': rc.PROVINCIA, 'target_factions': [rc.AEDUI, rc.ROMANS]},
])
def test_bad_selection_keeps_pending_without_revealing_cards(response):
    session = _session()
    before = encode(board_copy(session.state))
    with pytest.raises(DecisionPending):
        _run(session)
    pending = copy.deepcopy(session.data['pending'])
    session.import_inbox({'decision_id': pending['id'], 'response': response})
    queued = copy.deepcopy(session.data['queue'])
    with pytest.raises(DecisionPending):
        _run(session)
    assert session.error and session.data['pending'] == pending
    assert session.data['queue'] == queued and not session.data['journal']
    assert 'private_cards' not in decode(pending['request'])
    assert encode(board_copy(session.state)) == before


def test_complete_beneficiary_command_is_validated_and_executed_after_pending():
    session = _session()
    session.state['resources'][rc.AEDUI] = 0
    before = encode(board_copy(session.state))
    with pytest.raises(DecisionPending):
        _run(session, _selection())
    pending = session.data['pending']
    action = {'command': rc.CMD_MARCH, 'sa': 'No SA', 'regions': [rc.PROVINCIA],
              'sa_regions': [], 'details': {
                  'origins': [rc.PROVINCIA], 'destinations': [rc.SEQUANI],
                  'routes': {rc.PROVINCIA: [rc.SEQUANI]},
                  'groups': {rc.PROVINCIA: {rc.WARBAND: 2, rc.LEADER: False}}}}
    session.import_inbox({'decision_id': pending['id'], 'response': action})
    result = _run(session, _selection())
    session.finish()
    assert result['executed']
    assert count_pieces(session.state, rc.PROVINCIA, rc.AEDUI) == 0
    assert count_pieces(session.state, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == 3
    assert session.state['resources'][rc.AEDUI] == 0
    assert encode(board_copy(session.state)) != before
    assert decode(session.log[0]['assistant_response']) == action
    _assert_public_without_peek(session.state, result)


def test_later_beneficiary_pause_replays_earlier_np_action_and_rng(tmp_path):
    state = _state()
    state['non_player_factions'] = {rc.AEDUI}
    state['eligibility'][rc.AEDUI] = rc.INELIGIBLE
    origin = copy.deepcopy(state)
    meta = {'seat': rc.ROMANS, 'scenario': state['scenario'], 'seed': 47}
    session = SeatSession(state, meta, [], HumanTurnDisplay(io.StringIO()))
    state['decision_agent'] = session.reactive

    def execute(current):
        with _action_transaction(current.state, _driver(current)):
            return _execute_event(current.state, rc.ROMANS, _event(_selection()), human=True)

    with pytest.raises(DecisionPending):
        execute(session)
    pending = copy.deepcopy(session.data['pending'])
    request = decode(pending['request'])
    assert request['faction'] == rc.ROMANS and request['kind'] == 'council_choice'
    assert _private_ids(request) == [35, 62]
    # Aedui acts first by the card's printed order, using its real NP default.
    # The pending board has advanced, while the live transaction rolled back.
    assert decode(pending['board'])['rng'].getstate() != origin['rng'].getstate()
    assert encode(board_copy(state)) == encode(origin)
    save_game(state, tmp_path / 'later.json', meta=meta, log=session.log)
    restored, restored_meta, log = load_game(tmp_path / 'later.json')
    resumed = SeatSession(restored, restored_meta, log, HumanTurnDisplay(io.StringIO()))
    restored['decision_agent'] = resumed.reactive
    resumed.import_inbox({'decision_id': pending['id'], 'response': {'decline': True}})
    result = execute(resumed)
    resumed.finish()
    assert result['executed'] and len(resumed.log) == 1
    assert [entry['faction'] for entry in result['free_actions']] == [rc.AEDUI, rc.ROMANS]

    uninterrupted = copy.deepcopy(origin)
    uninterrupted['decision_agent'] = lambda board, faction, req: (
        {'decline': True} if faction == rc.ROMANS else None)
    assert _execute_event(uninterrupted, rc.ROMANS, _event(_selection()), human=True) == result
    assert encode(board_copy(restored)) == encode(board_copy(uninterrupted))
    _assert_public_without_peek(restored, result)


def test_only_selected_beneficiaries_receive_peek_and_public_result_omits_it():
    state = _state()
    requests = []

    def agent(board, faction, request):
        requests.append((faction, copy.deepcopy(request)))
        return {'decline': True}

    state['decision_agent'] = agent
    before_deck = list(state['deck'])
    before_rng = state['rng'].getstate()
    result = _execute_event(state, rc.BELGAE, _event(_selection()), human=True)
    assert result['executed']
    assert [faction for faction, request in requests] == [rc.AEDUI, rc.ROMANS]
    assert all(_private_ids(request) == [35, 62] for _, request in requests)
    assert state['deck'] == before_deck and state['next_card'] == 1
    assert state['rng'].getstate() == before_rng
    _assert_public_without_peek(state, result)


def test_previews_do_not_consume_live_private_decisions_or_change_rng():
    session = _session()
    session.import_inbox([{'response': {'choice': 'eligible'}}])
    before = encode(board_copy(session.state))
    saved_session = copy.deepcopy(session.data)
    action = _event(_selection())
    assert validate_player_action(session.state, rc.AEDUI, action)[0]
    ok, _, _ = preview_player_action(session.state, rc.AEDUI, action)
    assert ok
    assert encode(board_copy(session.state)) == before
    assert session.data == saved_session and session.log == []


class _DecliningReader:
    """Exercise actual terminal menus without depending on option numbering."""

    def __init__(self, output, inspect_board=False):
        self.output, self.inspect_board, self.reads = output, inspect_board, 0

    def readline(self):
        self.reads += 1
        assert self.reads < 10, self.output.getvalue()
        if self.inspect_board:
            self.inspect_board = False
            return 'board\n'
        options = re.findall(r'^\s*(\d+)\) (.*)$', self.output.getvalue(), re.M)
        return next(number for number, label in reversed(options)
                    if 'decline' in label.lower()) + '\n'


def test_event_menu_selects_two_of_three_present_factions_before_any_private_look():
    state = _state()
    place_piece(state, rc.SEQUANI, rc.BELGAE, rc.WARBAND, 1)
    before = encode(board_copy(state))
    output = io.StringIO()
    # Region; Aedui; Romans (skipping Belgae); stop after the legal minimum.
    stream = io.StringIO('1\n1\n2\n2\nuntouched\n')
    params = _collect_event_params(state, rc.AEDUI, 47, False, stream, output)
    assert params['region'] == rc.SEQUANI
    assert params['target_factions'] == [rc.AEDUI, rc.ROMANS]
    assert stream.readline() == 'untouched\n'
    assert encode(board_copy(state)) == before
    assert 'private_cards' not in output.getvalue()
    for card_id in (35, 62):
        assert get_card(card_id, state['scenario']).title not in output.getvalue()


def test_terminal_peek_is_beneficiary_owned_and_board_inspection_stays_public():
    state = _state()
    output, inspected = io.StringIO(), []
    state['decision_agent'] = make_cli_reactive(
        [rc.AEDUI, rc.ROMANS], _DecliningReader(output, inspect_board=True), output)
    before_rng, before_deck = state['rng'].getstate(), list(state['deck'])
    set_board_hook(lambda: inspected.append(format_board(state)))
    try:
        result = _execute_event(state, rc.BELGAE, _event(_selection()), human=True)
    finally:
        set_board_hook(None)
    assert result['executed'] and len(inspected) == 1
    assert state['rng'].getstate() == before_rng and state['deck'] == before_deck
    shown = output.getvalue()
    assert rc.AEDUI in shown and rc.ROMANS in shown
    for card_id in (35, 62):
        assert get_card(card_id, state['scenario']).title in shown
        assert get_card(card_id, state['scenario']).title not in inspected[0]
        for line in get_card_text(card_id, state['scenario']).splitlines():
            if line.strip():
                assert line.strip() in shown
    _assert_public_without_peek(state, result)


def test_terminal_private_prompt_eof_rolls_back_transaction():
    state = _state()
    output = io.StringIO()
    state['decision_agent'] = make_cli_reactive([rc.AEDUI], io.StringIO(''), output)
    before = encode(board_copy(state))
    with pytest.raises(EOFError):
        with _action_transaction(state, lambda *args: None):
            _execute_event(state, rc.AEDUI, _event(_selection()), human=True)
    assert encode(board_copy(state)) == before
    assert get_card(35, state['scenario']).title in output.getvalue()
