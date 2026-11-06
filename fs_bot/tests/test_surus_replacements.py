"""Shaded Surus chooses exact Aedui sources for the scoped German Command."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_available, place_piece
from fs_bot.cards.base_piece_choices import KIND, choice_request
from fs_bot.cards.event_eval import is_event_effective
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.human_plan import _collect_event_params
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT, _action_transaction
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def position():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=51)
    state.update(current_card=51, current_card_id=51)
    place_piece(state, rc.TREVERI, rc.AEDUI, rc.WARBAND, 5)
    place_piece(state, rc.TREVERI, rc.AEDUI, rc.WARBAND, 1, piece_state=rc.SCOUTED)
    place_piece(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND, 1)
    place_piece(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, 2)
    return state


def selection(count=1, visibility=rc.SCOUTED, region=rc.TREVERI, faction=rc.AEDUI):
    return {'region': region, 'target_faction': faction, 'piece_type': rc.WARBAND,
            'piece_state': visibility, 'count': count}


def march(count=1):
    return {'command': rc.CMD_MARCH, 'sa': 'No SA', 'details': {'origins': [rc.TREVERI],
            'destinations': [rc.MANDUBII], 'routes': {rc.TREVERI: [rc.MANDUBII]},
            'groups': {rc.TREVERI: {rc.WARBAND: count}}}}


def play(state, params=None, executor=rc.BELGAE):
    action = {'command': rc.FIRST_DID_EVENT, 'regions': [], 'details': {
        'card_id': 51, 'text_preference': rc.EVENT_SHADED, 'event_params': params or {}}}
    return execute_decision(state, executor, {'action': ACTION_EVENT, 'player_action': action})


def test_live_choice_replaces_the_scouted_warband_and_only_its_replacement_marches():
    state = position()
    seen = []

    def agent(board, faction, request):
        if request['kind'] == KIND:
            seen.append((faction, 'replacement'))
            return {'selections': [selection()]}
        if request['kind'] == 'free_action':
            seen.append((faction, request['request_type']))
            return march()

    state['decision_agent'] = agent
    assert play(state)['executed']
    assert seen == [(rc.BELGAE, 'replacement'), (rc.BELGAE, 'event_command')]
    assert count_pieces_by_state(state, rc.TREVERI, rc.AEDUI, rc.WARBAND, rc.HIDDEN) == 5
    assert count_pieces_by_state(state, rc.TREVERI, rc.AEDUI, rc.WARBAND, rc.SCOUTED) == 0
    assert count_pieces(state, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 2
    assert count_pieces(state, rc.MANDUBII, rc.GERMANS, rc.WARBAND) == 1
    assert validate_state(state) == []


@pytest.mark.parametrize('params', [
    {'piece_choices': [selection(5, rc.HIDDEN)]},
    {'piece_choices': [selection(), selection()]},
    {'piece_choices': [selection(), selection(1, rc.HIDDEN, rc.MANDUBII)]},
    {'piece_choices': [selection(1, rc.HIDDEN, rc.PROVINCIA)]},
    {'piece_choices': [selection(1, rc.HIDDEN, faction=rc.GERMANS)]},
    {'piece_choices': [selection()], 'region': rc.TREVERI},
    {'region': rc.PROVINCIA, 'count': 1},
    {'region': rc.TREVERI, 'count': 5},
])
def test_invalid_exact_or_legacy_plan_leaves_the_entire_board_intact(params):
    state = position()
    place_piece(state, rc.PROVINCIA, rc.AEDUI, rc.WARBAND, 1)
    before = encode(board_copy(state))
    assert play(state, params)['rejected']
    assert encode(board_copy(state)) == before


@pytest.mark.parametrize('shortage', [False, True])
def test_zero_or_unavailable_replacements_never_let_resident_germans_act(shortage):
    state = position()
    if shortage:
        place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND,
                    get_available(state, rc.GERMANS, rc.WARBAND))
    result = play(state, {'piece_choices': [selection()] if shortage else []})
    assert result['executed'] and result['free_actions'][0]['declined_no_effect']
    assert count_pieces_by_state(state, rc.TREVERI, rc.AEDUI, rc.WARBAND, rc.SCOUTED) == (0 if shortage else 1)
    assert count_pieces(state, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 2
    assert count_pieces(state, rc.MANDUBII, rc.GERMANS, rc.WARBAND) == 0


def test_scarce_german_pool_limits_the_grant_to_actual_placements():
    state = position()
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND,
                get_available(state, rc.GERMANS, rc.WARBAND) - 1)
    state['decision_agent'] = lambda b, f, r: march(2) if r['kind'] == 'free_action' else None
    assert play(state, {'piece_choices': [selection(), selection(1, rc.HIDDEN)]})['executed']
    assert count_pieces(state, rc.TREVERI, rc.AEDUI, rc.WARBAND) == 4
    assert count_pieces(state, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 2
    assert count_pieces(state, rc.MANDUBII, rc.GERMANS, rc.WARBAND) == 1


def test_replacement_window_does_not_substitute_for_a_selected_source_that_leaves():
    state = position()
    timing = {'kind': 'voluntary_removal', 'response': {'operations': [{
        'action': 'remove', 'region': rc.TREVERI, 'piece_type': rc.WARBAND,
        'piece_state': rc.SCOUTED, 'count': 1}]}}
    params = {'piece_choices': [selection()],
              'stage_timing_actions': {'51.german_replacements:0': [timing]}}
    result = play(state, params, executor=rc.AEDUI)
    assert result['executed'] and result['free_actions'][0]['declined_no_effect']
    assert count_pieces(state, rc.TREVERI, rc.AEDUI, rc.WARBAND) == 5
    assert count_pieces(state, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 2


def test_effectiveness_requires_aedui_sources_within_scope_even_without_german_stock():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=51)
    place_piece(state, rc.PROVINCIA, rc.AEDUI, rc.WARBAND)
    assert not is_event_effective(state, 51, shaded=True)
    place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, get_available(state, rc.GERMANS, rc.WARBAND))
    place_piece(state, rc.UBII, rc.AEDUI, rc.WARBAND, piece_state=rc.SCOUTED)
    assert is_event_effective(state, 51, shaded=True)


def test_terminal_exposes_exact_visibility_and_locks_in_one_region():
    state = position()
    output = StringIO()
    assert _collect_event_params(state, rc.BELGAE, 51, True, StringIO(), output) == {}
    options = choice_request(state, 51)['available']
    number = next(i for i, row in enumerate(options, 2) if row['piece_state'] == rc.SCOUTED)
    terminal = make_cli_reactive({rc.BELGAE}, StringIO(f'board\n{number}\n1\n1\n'), output)
    state['decision_agent'] = lambda b, f, r: (terminal(b, f, r) if r['kind'] == KIND else
                                               march() if r['kind'] == 'free_action' else None)
    assert play(state)['executed']
    assert f'{rc.SCOUTED} {rc.WARBAND}' in output.getvalue()
    assert rc.MANDUBII not in output.getvalue().rsplit('Surus: select', 1)[-1]
    assert count_pieces_by_state(state, rc.TREVERI, rc.AEDUI, rc.WARBAND, rc.SCOUTED) == 0


def test_assistant_resumes_the_grant_without_losing_the_exact_replacement(tmp_path):
    state = position()
    initial = encode(board_copy(state))

    def session_for(board, meta=None, log=None):
        session = SeatSession(board, meta or {'seat': rc.BELGAE}, [] if log is None else log,
                              HumanTurnDisplay(StringIO()))
        board['decision_agent'] = lambda b, f, r: session.reactive(b, f, r) if r['kind'] in (KIND, 'free_action') else None
        return session

    def attempt(session):
        def driver(*args):
            pass

        driver.transaction_checkpoint = session.checkpoint
        driver.transaction_restore = session.restore
        with _action_transaction(session.state, driver):
            return play(session.state)

    session = session_for(state)
    with pytest.raises(DecisionPending):
        attempt(session)
    first = session.data['pending']['id']
    session.import_inbox({'decision_id': first, 'response': {'selections': [selection()]}})
    with pytest.raises(DecisionPending):
        attempt(session)
    pending = deepcopy(session.data['pending'])
    assert pending['id'] != first
    assert decode(pending['request'])['acting_faction'] == rc.GERMANS
    assert encode(board_copy(state)) == initial

    path = tmp_path / 'surus.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session_for(restored, meta, log)
    with pytest.raises(DecisionPending):
        attempt(resumed)
    assert resumed.data['pending'] == pending
    resumed.import_inbox({'decision_id': pending['id'], 'response': march()})
    assert attempt(resumed)['executed']
    resumed.finish()
    reference = decode(initial)
    reference['decision_agent'] = lambda b, f, r: march() if r['kind'] == 'free_action' else None
    assert play(reference, {'piece_choices': [selection()]})['executed']
    assert encode(board_copy(restored)) == encode(board_copy(reference))
    assert len(log) == 2 and validate_state(restored) == []
