"""Card 58 unshaded: remove nine exact Warbands from one Fort Region."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_available, place_piece
from fs_bot.cards.base_piece_choices import KIND, aduatuca_request
from fs_bot.cards.event_eval import is_event_effective
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.human_plan import _collect_event_params
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT, _action_transaction
from fs_bot.state.serialize import encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


FORT_REGION = rc.ARVERNI_REGION


def position(*, populate=True):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=58)
    state.update(current_card=58, current_card_id=58)
    place_piece(state, FORT_REGION, rc.ROMANS, rc.FORT)
    if populate:
        place_piece(state, FORT_REGION, rc.BELGAE, rc.WARBAND, 9)
        place_piece(state, FORT_REGION, rc.GERMANS, rc.WARBAND, 2, piece_state=rc.SCOUTED)
    return state


def selection(faction, count, visibility=rc.HIDDEN, region=FORT_REGION):
    return {'region': region, 'target_faction': faction, 'piece_type': rc.WARBAND,
            'piece_state': visibility, 'count': count}


def play(state, params=None, executor=rc.ROMANS, *, npc=False):
    action = {'command': rc.FIRST_DID_EVENT, 'regions': [], 'details': {
        'card_id': 58, 'text_preference': rc.EVENT_UNSHADED, 'event_params': params or {}}}
    actor_key = 'bot_action' if npc else 'player_action'
    return execute_decision(state, executor, {'action': ACTION_EVENT, actor_key: action})


def test_exact_mix_preserves_other_pieces_and_returns_each_to_its_pool():
    state = position()
    place_piece(state, FORT_REGION, rc.BELGAE, rc.WARBAND, 2, piece_state=rc.REVEALED)
    before = {f: get_available(state, f, rc.WARBAND) for f in (rc.BELGAE, rc.GERMANS)}
    choices = [selection(rc.BELGAE, 6), selection(rc.BELGAE, 1, rc.REVEALED),
               selection(rc.GERMANS, 2, rc.SCOUTED)]
    assert play(state, {'region': FORT_REGION, 'piece_choices': choices})['executed']
    assert count_pieces_by_state(state, FORT_REGION, rc.BELGAE, rc.WARBAND, rc.HIDDEN) == 3
    assert count_pieces_by_state(state, FORT_REGION, rc.BELGAE, rc.WARBAND, rc.REVEALED) == 1
    assert count_pieces(state, FORT_REGION, rc.GERMANS, rc.WARBAND) == 0
    assert get_available(state, rc.BELGAE, rc.WARBAND) == before[rc.BELGAE] + 7
    assert get_available(state, rc.GERMANS, rc.WARBAND) == before[rc.GERMANS] + 2
    assert validate_state(state) == []


@pytest.mark.parametrize('region,choices', [
    (rc.MANDUBII, [selection(rc.BELGAE, 1, region=rc.MANDUBII)]),
    (FORT_REGION, [selection(rc.BELGAE, 8)]),
    (FORT_REGION, [selection(rc.BELGAE, 9), selection(rc.GERMANS, 1, rc.SCOUTED)]),
    (FORT_REGION, [selection(rc.BELGAE, 8), selection(rc.BELGAE, 1, region=rc.PROVINCIA)]),
    (FORT_REGION, [selection(rc.BELGAE, 8), selection(rc.AEDUI, 1)]),
])
def test_rejects_illegal_region_total_or_cohort_atomically(region, choices):
    state = position()
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    place_piece(state, rc.PROVINCIA, rc.BELGAE, rc.WARBAND)
    place_piece(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND)
    place_piece(state, FORT_REGION, rc.AEDUI, rc.WARBAND)
    before = encode(board_copy(state))
    assert play(state, {'region': region, 'piece_choices': choices})['rejected']
    assert encode(board_copy(state)) == before


def test_shortfall_in_selected_region_does_not_spill_into_another_fort():
    state = position()
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    place_piece(state, rc.PROVINCIA, rc.GERMANS, rc.WARBAND, piece_state=rc.SCOUTED)
    choices = [selection(rc.GERMANS, 1, rc.SCOUTED, rc.PROVINCIA)]
    assert play(state, {'region': rc.PROVINCIA, 'piece_choices': choices})['executed']
    assert count_pieces(state, rc.PROVINCIA, rc.GERMANS, rc.WARBAND) == 0
    assert count_pieces(state, FORT_REGION, rc.BELGAE, rc.WARBAND) == 9


def test_legacy_preferences_keep_their_timing_and_fill_any_shortfall():
    state = position()
    timing = {'kind': 'voluntary_removal', 'response': {'operations': [{
        'action': 'remove', 'region': FORT_REGION, 'piece_type': rc.WARBAND,
        'piece_state': rc.HIDDEN, 'count': 1}]}}
    params = {'region': FORT_REGION, 'removals': [
        {'faction': rc.GERMANS, 'count': 2, 'timing_actions': [timing]}]}
    assert play(state, params, executor=rc.BELGAE)['executed']
    assert count_pieces(state, FORT_REGION, rc.BELGAE, rc.WARBAND) == 1
    assert count_pieces(state, FORT_REGION, rc.GERMANS, rc.WARBAND) == 0


def test_bot_requires_a_target_at_a_fort_and_uses_visibility_before_faction():
    state = position(populate=False)
    place_piece(state, rc.PROVINCIA, rc.GERMANS, rc.WARBAND, 2)
    assert not is_event_effective(state, 58)
    place_piece(state, FORT_REGION, rc.BELGAE, rc.WARBAND, 9, piece_state=rc.REVEALED)
    place_piece(state, FORT_REGION, rc.GERMANS, rc.WARBAND, 2)
    state['non_player_factions'] = {rc.ROMANS}
    assert is_event_effective(state, 58)
    assert play(state, npc=True)['executed']
    assert count_pieces(state, FORT_REGION, rc.BELGAE, rc.WARBAND) == 2
    assert count_pieces(state, FORT_REGION, rc.GERMANS, rc.WARBAND) == 0
    assert count_pieces(state, rc.PROVINCIA, rc.GERMANS, rc.WARBAND) == 2


def test_live_choice_excludes_a_fort_removed_during_the_timing_window():
    state = position()
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    place_piece(state, rc.PROVINCIA, rc.GERMANS, rc.WARBAND, piece_state=rc.SCOUTED)
    offers = []

    def agent(board, faction, request):
        if request['kind'] == KIND:
            offers.append(request['required_by_region'])
            return {'region': rc.PROVINCIA, 'selections': request['available']}

    state['decision_agent'] = agent
    timing = {'kind': 'voluntary_removal', 'response': {'operations': [{
        'action': 'remove', 'region': FORT_REGION, 'piece_type': rc.FORT, 'count': 1}]}}
    assert play(state, {'stage_timing_actions': {'58.piece_choice': [timing]}})['executed']
    assert offers == [{rc.PROVINCIA: 1}]
    assert count_pieces(state, FORT_REGION, rc.BELGAE, rc.WARBAND) == 9
    assert count_pieces(state, rc.PROVINCIA, rc.GERMANS, rc.WARBAND) == 0


def test_terminal_names_both_factions_and_resolves_the_exact_choices():
    state = position()
    output = StringIO()
    assert _collect_event_params(state, rc.ROMANS, 58, False, StringIO(), output) == {}
    terminal = make_cli_reactive({rc.ROMANS}, StringIO('board\n1\n1\n7\n2\n2\n'), output)
    state['decision_agent'] = lambda b, f, r: terminal(b, f, r) if r['kind'] == KIND else None
    assert play(state)['executed']
    assert f'{rc.BELGAE} {rc.HIDDEN} {rc.WARBAND}' in output.getvalue()
    assert f'{rc.GERMANS} {rc.SCOUTED} {rc.WARBAND}' in output.getvalue()
    assert count_pieces(state, FORT_REGION, rc.BELGAE, rc.WARBAND) == 2
    assert count_pieces(state, FORT_REGION, rc.GERMANS, rc.WARBAND) == 0


def test_assistant_pending_choice_resumes_and_rejects_an_incomplete_reply(tmp_path):
    state = position()
    before = encode(board_copy(state))

    def session_for(board, meta=None, log=None):
        session = SeatSession(board, meta or {'seat': rc.ROMANS}, [] if log is None else log,
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
        'region': FORT_REGION, 'selections': [selection(rc.BELGAE, 8)]}})
    with pytest.raises(DecisionPending):
        attempt(session)
    assert session.error and session.data['pending'] == pending
    assert encode(board_copy(state)) == before

    path = tmp_path / 'aduatuca.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session_for(restored, meta, log)
    with pytest.raises(DecisionPending):
        attempt(resumed)
    assert resumed.data['pending'] == pending
    choices = [selection(rc.BELGAE, 7), selection(rc.GERMANS, 2, rc.SCOUTED)]
    resumed.import_inbox({'decision_id': pending['id'], 'response': {
        'region': FORT_REGION, 'selections': choices}})
    assert attempt(resumed)['executed']
    resumed.finish()
    assert play(state, {'region': FORT_REGION, 'piece_choices': choices})['executed']
    assert encode(board_copy(restored)) == encode(board_copy(state))
    assert aduatuca_request(restored)['required_by_region'] == {FORT_REGION: 2}
    assert len(log) == 1 and validate_state(restored) == []
