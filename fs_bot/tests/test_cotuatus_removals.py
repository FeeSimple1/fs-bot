"""Shaded Cotuatus selects three named Allied Tribes as the Event resolves."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.cards.base_piece_choices import KIND
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.human_plan import _collect_event_params
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT, _action_transaction
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


SELECTIONS = {'roman': rc.TRIBE_REMI, 'aedui': rc.TRIBE_HELVETII,
              'third': rc.TRIBE_BELLOVACI}


def position(scenario=rc.SCENARIO_GREAT_REVOLT, *, populate=True):
    state = build_initial_state(scenario, seed=31)
    state['current_card'] = state['current_card_id'] = 31
    if populate:
        for tribe in (rc.TRIBE_ATREBATES, rc.TRIBE_BELLOVACI, rc.TRIBE_REMI):
            assert _ally_tribe(state, tribe, rc.ROMANS)
        for tribe in (rc.TRIBE_AEDUI, rc.TRIBE_HELVETII):
            assert _ally_tribe(state, tribe, rc.AEDUI)
        place_piece(state, rc.SEQUANI, rc.AEDUI, rc.CITADEL)
        state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] = rc.AEDUI
    return state


def play(state, params=None, executor=rc.BELGAE):
    action = {'command': rc.FIRST_DID_EVENT, 'regions': [], 'details': {
        'card_id': 31, 'text_preference': rc.EVENT_SHADED, 'event_params': params or {}}}
    return execute_decision(state, executor, {'action': ACTION_EVENT, 'player_action': action})


def remaining_tribes(state):
    return {tribe for tribe, info in state['tribes'].items() if info['allied_faction']}


def authored():
    return {f'{slot}_ally_tribe': tribe for slot, tribe in SELECTIONS.items()}


@pytest.mark.parametrize('scenario', rc.BASE_SCENARIOS)
def test_remove_named_tribes_and_preserve_citadel(scenario):
    state = position(scenario)
    assert play(state, authored())['executed']
    assert remaining_tribes(state) == {rc.TRIBE_ATREBATES, rc.TRIBE_AEDUI, rc.TRIBE_SEQUANI}
    assert count_pieces(state, rc.SEQUANI, rc.AEDUI, rc.CITADEL) == 1
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.ALLY) == 1
    assert validate_state(state) == []


@pytest.mark.parametrize('overrides', [
    {'roman_ally_tribe': rc.TRIBE_AEDUI},
    {'aedui_ally_tribe': rc.TRIBE_SEQUANI},
    {'third_ally_tribe': rc.TRIBE_REMI},
    {'third_ally_faction': rc.BELGAE},
    {'roman_ally_region': rc.ATREBATES},
])
def test_illegal_authored_choices_roll_back_all_removals(overrides):
    state = position()
    before = encode(board_copy(state))
    assert play(state, authored() | overrides)['rejected']
    assert encode(board_copy(state)) == before


def test_live_choice_follows_timing_window():
    state = position()
    seen = []

    def agent(board, faction, request):
        if request['kind'] == KIND:
            seen.append((request['slot'], faction, {row['tribe'] for row in request['targets']}))
            return {'tribe': SELECTIONS[request['slot']]}

    state['decision_agent'] = agent
    params = {'stage_timing_actions': {'31.aedui_ally': [{'kind': 'voluntary_removal',
        'response': {'operations': [{'action': 'remove', 'region': rc.AEDUI_REGION,
                                     'piece_type': rc.ALLY, 'tribe': rc.TRIBE_AEDUI,
                                     'count': 1}]}}]}}
    assert play(state, params, rc.AEDUI)['executed']
    assert seen == [('roman', rc.AEDUI, {rc.TRIBE_ATREBATES, rc.TRIBE_BELLOVACI, rc.TRIBE_REMI}),
                    ('aedui', rc.AEDUI, {rc.TRIBE_HELVETII}),
                    ('third', rc.AEDUI, {rc.TRIBE_ATREBATES, rc.TRIBE_BELLOVACI})]
    assert remaining_tribes(state) == {rc.TRIBE_ATREBATES, rc.TRIBE_SEQUANI}


def test_missing_roman_ally_still_removes_two_aedui_allies():
    state = position(populate=False)
    for tribe in (rc.TRIBE_AEDUI, rc.TRIBE_HELVETII):
        assert _ally_tribe(state, tribe, rc.AEDUI)
    seen = []

    def agent(board, faction, request):
        if request['kind'] == KIND:
            seen.append(request['slot'])
            return {'use_default': True}

    state['decision_agent'] = agent
    assert play(state)['executed']
    assert seen == ['aedui', 'third']
    assert not remaining_tribes(state)


def test_terminal_selects_named_tribes_in_each_slot():
    state = position()
    output = StringIO()
    assert _collect_event_params(state, rc.BELGAE, 31, True, StringIO(), output) == {}
    terminal = make_cli_reactive({rc.BELGAE}, StringIO('board\n3\n2\n3\n'), output)
    state['decision_agent'] = lambda b, f, r: terminal(b, f, r) if r['kind'] == KIND else None
    assert play(state)['executed']
    assert output.getvalue().count('remove which Allied Tribe?') >= 3
    assert remaining_tribes(state) == {rc.TRIBE_ATREBATES, rc.TRIBE_AEDUI, rc.TRIBE_SEQUANI}


def test_later_choice_keeps_earlier_choice_across_rejection_and_save(tmp_path):
    state = position()
    initial = encode(board_copy(state))

    def session_for(board, meta=None, log=None):
        session = SeatSession(board, meta or {'seat': rc.BELGAE}, [] if log is None else log,
                              HumanTurnDisplay(StringIO()))
        board['decision_agent'] = lambda b, f, r: session.reactive(b, f, r) if r['kind'] == KIND else None
        return session

    def attempt(session):
        def driver(*args):
            pass

        driver.transaction_checkpoint = session.checkpoint
        driver.transaction_restore = session.restore
        with _action_transaction(session.state, driver):
            return play(session.state)

    def answer(session, tribe):
        session.import_inbox({'decision_id': session.data['pending']['id'], 'response': {'tribe': tribe}})

    session = session_for(state)
    with pytest.raises(DecisionPending):
        attempt(session)
    answer(session, rc.TRIBE_REMI)
    with pytest.raises(DecisionPending):
        attempt(session)
    pending = deepcopy(session.data['pending'])
    assert decode(pending['request'])['slot'] == 'aedui'
    answer(session, rc.TRIBE_SEQUANI)
    with pytest.raises(DecisionPending):
        attempt(session)
    assert session.error and session.data['pending'] == pending
    assert encode(board_copy(state)) == initial

    path = tmp_path / 'cotuatus.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session_for(restored, meta, log)
    with pytest.raises(DecisionPending):
        attempt(resumed)
    assert resumed.data['pending'] == pending
    answer(resumed, rc.TRIBE_HELVETII)
    with pytest.raises(DecisionPending):
        attempt(resumed)
    request = decode(resumed.data['pending']['request'])
    assert request['slot'] == 'third' and rc.TRIBE_REMI not in {row['tribe'] for row in request['targets']}
    answer(resumed, rc.TRIBE_BELLOVACI)
    assert attempt(resumed)['executed']
    resumed.finish()
    reference = decode(initial)
    assert play(reference, authored())['executed']
    assert encode(board_copy(restored)) == encode(board_copy(reference))
    assert len(log) == 3 and validate_state(restored) == []
