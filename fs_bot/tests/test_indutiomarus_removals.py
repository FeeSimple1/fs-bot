"""Card 60 unshaded removes six Belgic Warbands and/or named Allies."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_available, place_piece
from fs_bot.cards.base_piece_choices import KIND, indutiomarus_request
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cards.event_eval import is_event_effective
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.human_plan import _collect_event_params
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT, _action_transaction
from fs_bot.state.serialize import encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def position():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=60)
    state.update(current_card=60, current_card_id=60)
    return state


def populated():
    state = position()
    assert _ally_tribe(state, rc.TRIBE_MANDUBII, rc.BELGAE)
    assert _ally_tribe(state, rc.TRIBE_SENONES, rc.BELGAE)
    place_piece(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND, 6)
    place_piece(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND, 5, piece_state=rc.SCOUTED)
    return state


def warbands(count, visibility=rc.HIDDEN, region=rc.MANDUBII):
    return {'region': region, 'target_faction': rc.BELGAE, 'piece_type': rc.WARBAND,
            'piece_state': visibility, 'count': count}


def ally(tribe):
    return {**warbands(1, None, rc.TRIBE_TO_REGION[tribe]), 'piece_type': rc.ALLY, 'tribe': tribe}


def play(state, params=None, executor=rc.ROMANS, *, npc=False):
    action = {'command': rc.FIRST_DID_EVENT, 'regions': [], 'details': {
        'card_id': 60, 'text_preference': rc.EVENT_UNSHADED, 'event_params': params or {}}}
    actor_key = 'bot_action' if npc else 'player_action'
    return execute_decision(state, executor, {'action': ACTION_EVENT, actor_key: action})


def test_exact_mix_preserves_unselected_allied_tribe_and_hidden_warbands():
    state = populated()
    place_piece(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND, 2, piece_state=rc.REVEALED)
    ally_pool = get_available(state, rc.BELGAE, rc.ALLY)
    warband_pool = get_available(state, rc.BELGAE, rc.WARBAND)
    picks = [ally(rc.TRIBE_SENONES), warbands(1, rc.REVEALED), warbands(4, rc.SCOUTED)]
    assert play(state, {'region': rc.MANDUBII, 'piece_choices': picks})['executed']
    assert state['tribes'][rc.TRIBE_SENONES]['allied_faction'] is None
    assert state['tribes'][rc.TRIBE_MANDUBII]['allied_faction'] == rc.BELGAE
    assert count_pieces(state, rc.MANDUBII, rc.BELGAE, rc.ALLY) == 1
    for visibility, count in ((rc.HIDDEN, 6), (rc.REVEALED, 1), (rc.SCOUTED, 1)):
        assert count_pieces_by_state(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND, visibility) == count
    assert get_available(state, rc.BELGAE, rc.ALLY) == ally_pool + 1
    assert get_available(state, rc.BELGAE, rc.WARBAND) == warband_pool + 5
    assert validate_state(state) == []


@pytest.mark.parametrize('region,selections', [
    (rc.PROVINCIA, [warbands(1, region=rc.PROVINCIA)]),
    (rc.MANDUBII, [warbands(5), warbands(1, region=rc.TREVERI)]),
    (rc.MANDUBII, [ally(rc.TRIBE_SENONES), ally(rc.TRIBE_SENONES), warbands(4)]),
    (rc.MANDUBII, [{k: v for k, v in ally(rc.TRIBE_SENONES).items() if k != 'tribe'}, warbands(5)]),
    (rc.MANDUBII, [warbands(5)]),
    (rc.MANDUBII, [warbands(6), ally(rc.TRIBE_SENONES)]),
])
def test_rejects_out_of_scope_duplicate_unnamed_or_wrong_total(region, selections):
    state = populated()
    place_piece(state, rc.TREVERI, rc.BELGAE, rc.WARBAND)
    place_piece(state, rc.PROVINCIA, rc.BELGAE, rc.WARBAND)
    before = encode(board_copy(state))
    assert play(state, {'region': region, 'piece_choices': selections})['rejected']
    assert encode(board_copy(state)) == before


def test_partial_region_selection_excludes_a_citadel_and_leaves_other_regions():
    state = position()
    place_piece(state, rc.MANDUBII, rc.BELGAE, rc.CITADEL)
    state['tribes'][rc.TRIBE_MANDUBII].update(allied_faction=rc.BELGAE, citadel=True)
    assert _ally_tribe(state, rc.TRIBE_SENONES, rc.BELGAE)
    place_piece(state, rc.TREVERI, rc.BELGAE, rc.WARBAND, 6)
    place_piece(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND, 1, piece_state=rc.SCOUTED)
    request = indutiomarus_request(state)
    assert request['required_by_region'][rc.MANDUBII] == 2
    assert play(state, {'region': rc.MANDUBII, 'piece_choices': [
        ally(rc.TRIBE_MANDUBII), warbands(1, rc.SCOUTED)]})['rejected']
    assert play(state, {'region': rc.MANDUBII, 'piece_choices': [
        ally(rc.TRIBE_SENONES), warbands(1, rc.SCOUTED)]})['executed']
    assert count_pieces(state, rc.MANDUBII, rc.BELGAE, rc.CITADEL) == 1
    assert state['tribes'][rc.TRIBE_MANDUBII]['allied_faction'] == rc.BELGAE
    assert count_pieces(state, rc.TREVERI, rc.BELGAE, rc.WARBAND) == 6
    assert validate_state(state) == []


def test_bot_checks_region_scope_and_prefers_enemy_allies():
    state = position()
    place_piece(state, rc.PROVINCIA, rc.BELGAE, rc.WARBAND, 7)
    assert not is_event_effective(state, 60)
    place_piece(state, rc.TREVERI, rc.BELGAE, rc.WARBAND, 6)
    assert _ally_tribe(state, rc.TRIBE_SENONES, rc.BELGAE)
    place_piece(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND, 3, piece_state=rc.SCOUTED)
    state['non_player_factions'] = {rc.ROMANS}
    assert is_event_effective(state, 60)
    assert play(state, npc=True)['executed']
    assert count_pieces(state, rc.MANDUBII, rc.BELGAE) == 0
    assert count_pieces(state, rc.TREVERI, rc.BELGAE, rc.WARBAND) == 6
    assert count_pieces(state, rc.PROVINCIA, rc.BELGAE, rc.WARBAND) == 7


def test_legacy_single_piece_entries_keep_timing_and_complete_removals():
    state = populated()
    timing = {'kind': 'voluntary_removal', 'response': {'operations': [{
        'action': 'remove', 'region': rc.MANDUBII, 'piece_type': rc.WARBAND,
        'piece_state': rc.HIDDEN, 'count': 1}]}}
    params = {'region': rc.MANDUBII, 'removals': [
        {'type': rc.ALLY, 'tribe': rc.TRIBE_SENONES, 'timing_actions': [timing]}]}
    assert play(state, params, executor=rc.BELGAE)['executed']
    assert state['tribes'][rc.TRIBE_SENONES]['allied_faction'] is None
    assert state['tribes'][rc.TRIBE_MANDUBII]['allied_faction'] == rc.BELGAE
    assert count_pieces(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND) == 5


def test_live_menu_reflects_warbands_removed_in_timing_window():
    state = position()
    place_piece(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND, 3, piece_state=rc.SCOUTED)
    requests = []

    def agent(board, faction, request):
        if request['kind'] == KIND:
            requests.append((faction, request['required_by_region'][rc.MANDUBII]))
            return {'region': rc.MANDUBII, 'selections': request['available']}

    state['decision_agent'] = agent
    timing = {'kind': 'voluntary_removal', 'response': {'operations': [{
        'action': 'remove', 'region': rc.MANDUBII, 'piece_type': rc.WARBAND,
        'piece_state': rc.SCOUTED, 'count': 1}]}}
    assert play(state, {'stage_timing_actions': {'60.piece_choice': [timing]}},
                executor=rc.BELGAE)['executed']
    assert requests == [(rc.BELGAE, 2)]
    assert count_pieces(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND) == 0


def test_terminal_lists_the_named_allies_and_plays_the_exact_mix():
    state = populated()
    output = StringIO()
    assert _collect_event_params(state, rc.ROMANS, 60, False, StringIO(), output) == {}
    regions = list(indutiomarus_request(state)['required_by_region'])
    region_number = regions.index(rc.MANDUBII) + 1
    terminal = make_cli_reactive({rc.ROMANS}, StringIO(f'board\n{region_number}\n2\n1\n3\n5\n'), output)
    state['decision_agent'] = lambda b, f, r: terminal(b, f, r) if r['kind'] == KIND else None
    assert play(state)['executed']
    assert f'{rc.ALLY} at {rc.TRIBE_SENONES}' in output.getvalue()
    assert f'{rc.ALLY} at {rc.TRIBE_MANDUBII}' in output.getvalue()
    assert state['tribes'][rc.TRIBE_SENONES]['allied_faction'] is None
    assert count_pieces(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND) == 6


def test_assistant_retries_and_resumes_the_same_named_removal_choice(tmp_path):
    state = populated()
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
        'region': rc.MANDUBII, 'selections': [ally(rc.TRIBE_SENONES), warbands(4)]}})
    with pytest.raises(DecisionPending):
        attempt(session)
    assert session.error and session.data['pending'] == pending
    assert encode(board_copy(state)) == before

    path = tmp_path / 'indutiomarus.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session_for(restored, meta, log)
    with pytest.raises(DecisionPending):
        attempt(resumed)
    assert resumed.data['pending'] == pending
    picks = [ally(rc.TRIBE_SENONES), warbands(5, rc.SCOUTED)]
    resumed.import_inbox({'decision_id': pending['id'], 'response': {
        'region': rc.MANDUBII, 'selections': picks}})
    assert attempt(resumed)['executed']
    resumed.finish()
    assert play(state, {'region': rc.MANDUBII, 'piece_choices': picks})['executed']
    assert encode(board_copy(restored)) == encode(board_copy(state))
    assert len(log) == 1 and validate_state(restored) == []
