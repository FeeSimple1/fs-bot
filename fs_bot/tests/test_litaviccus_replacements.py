"""Unshaded Litaviccus selects exact Arverni replacement sources."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_available, place_piece
from fs_bot.cards.base_piece_choices import KIND
from fs_bot.cards.event_eval import is_event_effective
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.human_plan import _collect_event_params
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT, _action_transaction
from fs_bot.state.serialize import encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


FIRST = rc.ARVERNI_REGION
SECOND = rc.MANDUBII
THIRD = rc.TREVERI


def position():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=45)
    state.update(current_card=45, current_card_id=45)
    state['resources'].update({rc.ARVERNI: 8, rc.AEDUI: 5})
    place_piece(state, FIRST, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(state, FIRST, rc.ARVERNI, rc.WARBAND, 2, piece_state=rc.SCOUTED)
    place_piece(state, SECOND, rc.ARVERNI, rc.WARBAND, 1, piece_state=rc.REVEALED)
    place_piece(state, THIRD, rc.ARVERNI, rc.WARBAND, 1)
    return state


def selection(region, count=1, visibility=rc.HIDDEN, faction=rc.ARVERNI):
    return {'region': region, 'target_faction': faction, 'piece_type': rc.WARBAND,
            'piece_state': visibility, 'count': count}


def play(state, params=None, executor=rc.AEDUI, *, npc=False):
    action = {'command': rc.FIRST_DID_EVENT, 'regions': [], 'details': {
        'card_id': 45, 'text_preference': rc.EVENT_UNSHADED, 'event_params': params or {}}}
    actor_key = 'bot_action' if npc else 'player_action'
    return execute_decision(state, executor, {'action': ACTION_EVENT, actor_key: action})


def test_exact_sources_in_two_regions_leave_hidden_warbands_and_transfer_resources():
    state = position()
    picks = [selection(FIRST, 2, rc.SCOUTED), selection(SECOND, 1, rc.REVEALED)]
    assert play(state, {'piece_choices': picks})['executed']
    assert count_pieces_by_state(state, FIRST, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 3
    assert count_pieces_by_state(state, FIRST, rc.ARVERNI, rc.WARBAND, rc.SCOUTED) == 0
    assert count_pieces_by_state(state, FIRST, rc.AEDUI, rc.WARBAND, rc.HIDDEN) == 2
    assert count_pieces(state, SECOND, rc.ARVERNI, rc.WARBAND) == 0
    assert count_pieces(state, SECOND, rc.AEDUI, rc.WARBAND) == 1
    assert count_pieces(state, THIRD, rc.ARVERNI, rc.WARBAND) == 1
    assert (state['resources'][rc.ARVERNI], state['resources'][rc.AEDUI]) == (4, 9)
    assert validate_state(state) == []


def test_zero_replacements_still_transfers_resources_and_obeys_cap():
    state = position()
    state['resources'].update({rc.ARVERNI: 2, rc.AEDUI: rc.MAX_RESOURCES - 1})
    assert play(state, {'piece_choices': []})['executed']
    assert count_pieces(state, FIRST, rc.ARVERNI, rc.WARBAND) == 5
    assert count_pieces(state, FIRST, rc.AEDUI, rc.WARBAND) == 0
    assert (state['resources'][rc.ARVERNI], state['resources'][rc.AEDUI]) == (0, rc.MAX_RESOURCES)


@pytest.mark.parametrize('params', [
    {'piece_choices': [selection(FIRST, 2), selection(FIRST, 1, rc.SCOUTED)]},
    {'piece_choices': [selection(FIRST), selection(SECOND, 1, rc.REVEALED), selection(THIRD)]},
    {'piece_choices': [selection(FIRST, 2, rc.SCOUTED), selection(FIRST, 1, rc.SCOUTED)]},
    {'piece_choices': [selection(SECOND, faction=rc.BELGAE)]},
    {'piece_choices': [selection(rc.CISALPINA)]},
    {'regions': [{'region': FIRST}, {'region': FIRST}]},
    {'regions': [{'region': FIRST, 'count': 3}]},
])
def test_rejects_illegal_cohorts_and_regions_without_transferring_resources(params):
    state = position()
    before = encode(board_copy(state))
    assert play(state, params)['rejected']
    assert encode(board_copy(state)) == before


def test_unavailable_replacements_still_remove_the_selected_sources():
    state = position()
    place_piece(state, SECOND, rc.AEDUI, rc.WARBAND, get_available(state, rc.AEDUI, rc.WARBAND))
    assert play(state, {'piece_choices': [selection(FIRST, 1, rc.SCOUTED)]})['executed']
    assert count_pieces_by_state(state, FIRST, rc.ARVERNI, rc.WARBAND, rc.SCOUTED) == 1
    assert count_pieces(state, FIRST, rc.AEDUI, rc.WARBAND) == 0


def test_replacement_window_cannot_substitute_a_different_visibility():
    state = position()
    timing = {'kind': 'voluntary_removal', 'response': {'operations': [{
        'action': 'remove', 'region': FIRST, 'piece_type': rc.WARBAND,
        'piece_state': rc.SCOUTED, 'count': 2}]}}
    params = {'piece_choices': [selection(FIRST, 1, rc.SCOUTED)],
              'stage_timing_actions': {f'45.replacements.{FIRST}:0': [timing]}}
    assert play(state, params, rc.ARVERNI)['executed']
    assert count_pieces_by_state(state, FIRST, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 3
    assert count_pieces(state, FIRST, rc.AEDUI, rc.WARBAND) == 0
    assert state['resources'][rc.AEDUI] == 9


def test_legacy_counts_can_reach_scouted_pieces_after_their_old_timing_window():
    state = position()
    timing = {'kind': 'voluntary_removal', 'response': {'operations': [{
        'action': 'remove', 'region': FIRST, 'piece_type': rc.WARBAND,
        'piece_state': rc.HIDDEN, 'count': 3}]}}
    params = {'regions': [{'region': FIRST, 'count': 1, 'timing_actions': [timing]},
                          {'region': SECOND, 'count': 0}]}
    assert play(state, params, rc.ARVERNI)['executed']
    assert count_pieces_by_state(state, FIRST, rc.ARVERNI, rc.WARBAND, rc.SCOUTED) == 1
    assert count_pieces(state, FIRST, rc.AEDUI, rc.WARBAND) == 1
    assert count_pieces(state, SECOND, rc.ARVERNI, rc.WARBAND) == 1


def test_bot_maximizes_replacements_and_checks_the_independent_transfer():
    empty = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=45)
    empty['resources'][rc.ARVERNI] = 0
    assert not is_event_effective(empty, 45)
    empty['resources'][rc.ARVERNI] = 1
    assert is_event_effective(empty, 45)
    state = position()
    place_piece(state, THIRD, rc.ARVERNI, rc.WARBAND, 1)
    state['non_player_factions'] = {rc.AEDUI}
    assert play(state, npc=True)['executed']
    assert count_pieces(state, FIRST, rc.AEDUI, rc.WARBAND) == 2
    assert count_pieces(state, THIRD, rc.AEDUI, rc.WARBAND) == 2
    assert count_pieces(state, SECOND, rc.ARVERNI, rc.WARBAND) == 1


def test_terminal_offers_scouted_and_never_offers_a_third_region():
    state = position()
    output = StringIO()
    assert _collect_event_params(state, rc.AEDUI, 45, False, StringIO(), output) == {}
    terminal = make_cli_reactive({rc.AEDUI}, StringIO('board\n3\n1\n4\n1\n1\n'), output)
    state['decision_agent'] = lambda b, f, r: terminal(b, f, r) if r['kind'] == KIND else None
    assert play(state)['executed']
    assert f'{rc.SCOUTED} {rc.WARBAND}' in output.getvalue()
    final_menu = output.getvalue().rsplit('Litaviccus: select', 1)[-1]
    assert THIRD not in final_menu
    assert count_pieces(state, FIRST, rc.AEDUI, rc.WARBAND) == 1
    assert count_pieces(state, SECOND, rc.AEDUI, rc.WARBAND) == 1


def test_assistant_retries_and_resumes_the_exact_replacement(tmp_path):
    state = position()
    before = encode(board_copy(state))

    def session_for(board, meta=None, log=None):
        session = SeatSession(board, meta or {'seat': rc.AEDUI}, [] if log is None else log,
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

    session = session_for(state)
    with pytest.raises(DecisionPending):
        attempt(session)
    pending = deepcopy(session.data['pending'])
    session.import_inbox({'decision_id': pending['id'], 'response': {
        'selections': [selection(FIRST, 3)]}})
    with pytest.raises(DecisionPending):
        attempt(session)
    assert session.error and session.data['pending'] == pending
    assert encode(board_copy(state)) == before

    path = tmp_path / 'litaviccus.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session_for(restored, meta, log)
    with pytest.raises(DecisionPending):
        attempt(resumed)
    assert resumed.data['pending'] == pending
    picks = [selection(FIRST, 1, rc.SCOUTED)]
    resumed.import_inbox({'decision_id': pending['id'], 'response': {'selections': picks}})
    assert attempt(resumed)['executed']
    resumed.finish()
    assert play(state, {'piece_choices': picks})['executed']
    assert encode(board_copy(restored)) == encode(board_copy(state))
    assert len(log) == 1 and validate_state(restored) == []
