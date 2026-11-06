"""Shaded Alaudae resolves exact Roman removals in two timing windows."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, get_available, move_piece, place_piece, remove_piece,
)
from fs_bot.bots.german_bot import node_g3b
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


def position(scenario=rc.SCENARIO_GREAT_REVOLT, *, track=7, populate=True):
    state = build_initial_state(scenario, seed=7)
    state['current_card'] = state['current_card_id'] = 7
    if populate:
        place_piece(state, rc.MANDUBII, rc.ROMANS, rc.LEGION, 11 - track, from_legions_track=True)
        place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEGION, from_legions_track=True)
        for visibility in (rc.HIDDEN, rc.SCOUTED):
            place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, piece_state=visibility)
    return state


def selection(kind, visibility=None, region=rc.SEQUANI):
    return {'region': region, 'target_faction': rc.ROMANS, 'piece_type': kind,
            'piece_state': visibility, 'count': 1}


def play(state, params=None, executor=rc.BELGAE, *, npc=False):
    action = {'command': rc.FIRST_DID_EVENT, 'regions': [], 'details': {
        'card_id': 7, 'text_preference': rc.EVENT_SHADED, 'event_params': params or {}}}
    actor_key = 'bot_action' if npc else 'player_action'
    return execute_decision(state, executor, {'action': ACTION_EVENT, actor_key: action})


def test_seven_on_track_excludes_fallen_and_completes_both_removals():
    state = position()
    remove_piece(state, rc.MANDUBII, rc.ROMANS, rc.LEGION, to_fallen=True)
    pool = get_available(state, rc.ROMANS, rc.AUXILIA)
    choices = [selection(rc.LEGION), selection(rc.AUXILIA, rc.SCOUTED)]
    assert play(state, {'piece_choices': choices})['executed']
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.LEGION) == 0
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.LEGION) == 3
    assert count_pieces_by_state(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 1
    assert count_pieces_by_state(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, rc.SCOUTED) == 0
    assert sum(state['legions_track'].values()) == 8 and state['fallen_legions'] == 1
    assert get_available(state, rc.ROMANS, rc.AUXILIA) == pool + 1
    assert validate_state(state) == []


def test_above_track_limit_has_no_effect_or_choice():
    state = position(track=8)
    state['event_params'] = state['executing_faction'] = None
    seen = []

    state['decision_agent'] = lambda board, faction, request: seen.append(request['kind'])
    before = encode(board_copy(state))
    assert not is_event_effective(state, 7, shaded=True)
    assert play(state)['executed']
    assert KIND not in seen
    assert encode(board_copy(state)) == before


@pytest.mark.parametrize('kind', [rc.LEGION, rc.AUXILIA])
def test_removes_the_available_type_when_other_type_is_absent(kind):
    state = position()
    if kind == rc.AUXILIA:
        remove_piece(state, rc.MANDUBII, rc.ROMANS, rc.LEGION, 4, to_fallen=True)
        remove_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEGION, to_fallen=True)
    else:
        remove_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 2)
    seen = []

    def choose(board, faction, request):
        if request['kind'] == KIND:
            seen.append((faction, request['required']))
            return {'selections': [dict(request['available'][0], count=1)]}

    state['decision_agent'] = choose
    assert play(state)['executed']
    assert seen == [(rc.BELGAE, {kind: 1})]


@pytest.mark.parametrize('choices', [
    [selection(rc.LEGION)],
    [selection(rc.LEGION), selection(rc.AUXILIA, rc.REVEALED)],
    [selection(rc.LEGION), selection(rc.AUXILIA, rc.SCOUTED, rc.PROVINCIA)],
])
def test_illegal_second_removal_rolls_back_first(choices):
    state = position()
    before = encode(board_copy(state))
    assert play(state, {'piece_choices': choices})['rejected']
    assert encode(board_copy(state)) == before


def test_legacy_region_keys_still_work():
    state = position()
    assert play(state, {'legion_removal_region': rc.SEQUANI,
                        'auxilia_removal_region': rc.SEQUANI})['executed']
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.LEGION) == 0
    assert count_pieces_by_state(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, rc.SCOUTED) == 1


def test_auxilia_choice_sees_the_first_removal_and_the_intervening_window():
    state = position()
    seen = []

    def choose(board, faction, request):
        if request['kind'] == KIND:
            seen.append((sum(board['legions_track'].values()), request['available']))
            return {'selections': [dict(request['available'][-1], count=1)]}

    state['decision_agent'] = choose
    timing = {'kind': 'voluntary_removal', 'response': {'operations': [{
        'action': 'remove', 'region': rc.SEQUANI, 'piece_type': rc.AUXILIA,
        'piece_state': rc.SCOUTED, 'count': 1}]}}
    assert play(state, {'stage_timing_actions': {'7.auxilia_removal': [timing]}}, rc.ROMANS)['executed']
    assert seen[0][0] == 7 and seen[1] == (8, [selection(rc.AUXILIA, rc.HIDDEN)])
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 0


def test_german_bot_checks_geographic_tiers_and_fills_remaining_removal():
    state = position(rc.SCENARIO_ARIOVISTUS, populate=False)
    state['non_player_factions'] = {rc.GERMANS}
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION, 5, from_legions_track=True)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA)
    assert is_event_effective(state, 7, shaded=True) and node_g3b(state) == 'Yes'
    move_piece(state, rc.PROVINCIA, rc.UBII, rc.ROMANS, rc.LEGION)
    assert node_g3b(state) == 'No'
    assert play(state, executor=rc.GERMANS, npc=True)['executed']
    assert count_pieces(state, rc.UBII, rc.ROMANS, rc.LEGION) == 0
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == 4
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 0


def test_terminal_selects_legion_and_scouted_auxilia():
    state = position()
    output = StringIO()
    assert _collect_event_params(state, rc.BELGAE, 7, True, StringIO(), output) == {}
    terminal = make_cli_reactive({rc.BELGAE}, StringIO('board\n2\n1\n2\n1\n'), output)
    state['decision_agent'] = lambda b, f, r: terminal(b, f, r) if r['kind'] == KIND else None
    assert play(state)['executed']
    assert 'Scouted Auxilia' in output.getvalue()
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.LEGION) == 0
    assert count_pieces_by_state(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, rc.SCOUTED) == 0


def test_assistant_resumes_the_second_choice_after_saving(tmp_path):
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
    first = session.data['pending']['id']
    legion, auxilia = selection(rc.LEGION), selection(rc.AUXILIA, rc.SCOUTED)
    session.import_inbox({'decision_id': first, 'response': {'selections': [legion]}})
    with pytest.raises(DecisionPending):
        attempt(session)
    pending = deepcopy(session.data['pending'])
    assert pending['id'] != first
    assert decode(pending['request'])['required'] == {rc.AUXILIA: 1}
    assert encode(board_copy(state)) == initial

    path = tmp_path / 'alaudae.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session_for(restored, meta, log)
    with pytest.raises(DecisionPending):
        attempt(resumed)
    assert resumed.data['pending'] == pending
    resumed.import_inbox({'decision_id': pending['id'], 'response': {'selections': [auxilia]}})
    assert attempt(resumed)['executed']
    resumed.finish()
    reference = decode(initial)
    assert play(reference, {'piece_choices': [legion, auxilia]})['executed']
    assert encode(board_copy(restored)) == encode(board_copy(reference))
    assert len(log) == 2 and validate_state(restored) == []
