"""Shaded Sappers selects two physical Roman pieces in one Citadel Region."""
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
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def position(*, populate=True):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=24)
    state['current_card'] = state['current_card_id'] = 24
    for region, tribe in ((rc.ARVERNI_REGION, rc.TRIBE_ARVERNI),
                          (rc.MANDUBII, rc.TRIBE_MANDUBII)):
        place_piece(state, region, rc.ARVERNI, rc.CITADEL)
        state['tribes'][tribe].update(allied_faction=rc.ARVERNI, citadel=True)
    if populate:
        place_piece(state, rc.ARVERNI_REGION, rc.ROMANS, rc.LEGION, 2, from_legions_track=True)
        for visibility in (rc.HIDDEN, rc.SCOUTED):
            place_piece(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA, 2, piece_state=visibility)
        place_piece(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA, 1, piece_state=rc.REVEALED)
    return state


def selection(kind, count, visibility=None, region=rc.ARVERNI_REGION):
    return {'region': region, 'target_faction': rc.ROMANS, 'piece_type': kind,
            'piece_state': visibility, 'count': count}


def play(state, params=None, executor=rc.BELGAE, *, npc=False):
    action = {'command': rc.FIRST_DID_EVENT, 'regions': [], 'details': {
        'card_id': 24, 'text_preference': rc.EVENT_SHADED, 'event_params': params or {}}}
    actor_key = 'bot_action' if npc else 'player_action'
    return execute_decision(state, executor, {'action': ACTION_EVENT, actor_key: action})


@pytest.mark.parametrize('legions', [0, 1, 2])
def test_exact_mix_preserves_other_cohorts_and_sends_legions_to_fallen(legions):
    state = position()
    choices = [row for row in (selection(rc.LEGION, legions),
                                selection(rc.AUXILIA, 2 - legions, rc.SCOUTED)) if row['count']]
    track = dict(state['legions_track'])
    pool = get_available(state, rc.ROMANS, rc.AUXILIA)
    assert play(state, {'target_region': rc.ARVERNI_REGION, 'piece_choices': choices})['executed']
    assert count_pieces_by_state(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 2
    assert count_pieces_by_state(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA, rc.SCOUTED) == legions
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 1
    assert state['fallen_legions'] == legions and state['legions_track'] == track
    assert get_available(state, rc.ROMANS, rc.AUXILIA) == pool + 2 - legions
    assert validate_state(state) == []


@pytest.mark.parametrize('target,choices', [
    (rc.ARVERNI_REGION, [selection(rc.LEGION, 1)]),
    (rc.ARVERNI_REGION, [selection(rc.LEGION, 1), selection(rc.AUXILIA, 1, rc.REVEALED, rc.MANDUBII)]),
    (rc.ARVERNI_REGION, [selection(rc.AUXILIA, 2, rc.REVEALED)]),
    (rc.PROVINCIA, [selection(rc.LEGION, 1, region=rc.PROVINCIA)]),
])
def test_invalid_selection_rolls_back(target, choices):
    state = position()
    before = encode(board_copy(state))
    assert play(state, {'target_region': target, 'piece_choices': choices})['rejected']
    assert encode(board_copy(state)) == before


def test_exact_selection_can_take_one_piece_from_chosen_region():
    state = position()
    assert play(state, {'target_region': rc.MANDUBII, 'piece_choices': [
        selection(rc.AUXILIA, 1, rc.REVEALED, rc.MANDUBII)]})['executed']
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(state, rc.ARVERNI_REGION, rc.ROMANS, rc.LEGION) == 2


def test_legacy_quantities_get_first_choice_and_complete_the_total():
    state = position()
    assert play(state, {'target_region': rc.ARVERNI_REGION, 'auxilia_to_remove': 1})['executed']
    assert state['fallen_legions'] == 1
    assert count_pieces_by_state(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 1


def test_bot_checks_citadel_scope_and_prioritizes_legions():
    state = position(populate=False)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION, from_legions_track=True)
    assert not is_event_effective(state, 24, shaded=True)
    place_piece(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA, 1, piece_state=rc.SCOUTED)
    state['non_player_factions'] = {rc.BELGAE}
    assert is_event_effective(state, 24, shaded=True)
    assert play(state, npc=True)['executed']
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS) == 0
    assert count_pieces(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == 1


def test_live_request_uses_the_board_after_timing_removals():
    state = position(populate=False)
    place_piece(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA, 2, piece_state=rc.SCOUTED)
    offered = []

    def agent(board, faction, request):
        if request['kind'] == KIND:
            offered.append((faction, request['required_by_region'][rc.ARVERNI_REGION]))
            return {'region': rc.ARVERNI_REGION, 'selections': request['available']}

    state['decision_agent'] = agent
    timing = {'kind': 'voluntary_removal', 'response': {'operations': [{
        'action': 'remove', 'region': rc.ARVERNI_REGION, 'piece_type': rc.AUXILIA,
        'piece_state': rc.SCOUTED, 'count': 1}]}}
    assert play(state, {'stage_timing_actions': {'24.piece_choice': [timing]}}, rc.ROMANS)['executed']
    assert offered == [(rc.ROMANS, 1)]
    assert count_pieces(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA) == 0


def test_terminal_combines_a_legion_with_a_scouted_auxilia():
    state = position()
    output = StringIO()
    assert _collect_event_params(state, rc.BELGAE, 24, True, StringIO(), output) == {}
    terminal = make_cli_reactive({rc.BELGAE}, StringIO('board\n1\n1\n1\n3\n1\n'), output)
    state['decision_agent'] = lambda b, f, r: terminal(b, f, r) if r['kind'] == KIND else None
    assert play(state)['executed']
    assert 'Scouted Auxilia' in output.getvalue()
    assert state['fallen_legions'] == 1
    assert count_pieces_by_state(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA, rc.SCOUTED) == 1


def test_assistant_resume_rejects_shortfall_and_preserves_the_exact_choice(tmp_path):
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

    session = session_for(state)
    with pytest.raises(DecisionPending):
        attempt(session)
    pending = deepcopy(session.data['pending'])
    request = decode(pending['request'])
    assert request['owner'] == rc.BELGAE and request['required_by_region'][rc.ARVERNI_REGION] == 2
    session.import_inbox({'decision_id': pending['id'], 'response': {
        'region': rc.ARVERNI_REGION, 'selections': [selection(rc.LEGION, 1)]}})
    with pytest.raises(DecisionPending):
        attempt(session)
    assert session.error and session.data['pending'] == pending
    assert encode(board_copy(state)) == initial

    path = tmp_path / 'sappers.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session_for(restored, meta, log)
    with pytest.raises(DecisionPending):
        attempt(resumed)
    assert resumed.data['pending'] == pending
    choices = [selection(rc.LEGION, 1), selection(rc.AUXILIA, 1, rc.SCOUTED)]
    resumed.import_inbox({'decision_id': pending['id'], 'response': {
        'region': rc.ARVERNI_REGION, 'selections': choices}})
    assert attempt(resumed)['executed']
    resumed.finish()
    reference = decode(initial)
    assert play(reference, {'target_region': rc.ARVERNI_REGION, 'piece_choices': choices})['executed']
    assert encode(board_copy(restored)) == encode(board_copy(reference))
    assert len(log) == 1 and validate_state(restored) == []
