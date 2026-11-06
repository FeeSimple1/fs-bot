"""Both shaded Numidians editions let the executor choose four physical Auxilia."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_available, place_piece
from fs_bot.cards.base_piece_choices import KIND
from fs_bot.cards.event_conditions import np_event_available
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.human_plan import _collect_event_params
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT, _action_transaction
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def position(edition='original', scenario=rc.SCENARIO_GREAT_REVOLT, *, populate=True):
    state = build_initial_state(scenario, seed=11)
    state['card_edition'] = edition
    state['current_card'] = state['current_card_id'] = 11
    if populate:
        for visibility, count in ((rc.HIDDEN, 3), (rc.REVEALED, 2), (rc.SCOUTED, 4)):
            place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, count, piece_state=visibility)
    return state


def play(state, params=None, executor=rc.BELGAE, *, npc=False):
    action = {'command': rc.FIRST_DID_EVENT, 'regions': [], 'details': {
        'card_id': 11, 'text_preference': rc.EVENT_SHADED, 'event_params': params or {}}}
    actor_key = 'bot_action' if npc else 'player_action'
    return execute_decision(state, executor, {'action': ACTION_EVENT, actor_key: action})


def selection(visibility, count, region=rc.SEQUANI, faction=rc.ROMANS):
    return {'region': region, 'target_faction': faction, 'piece_type': rc.AUXILIA,
            'piece_state': visibility, 'count': count}


def counts(state):
    return tuple(count_pieces_by_state(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, visibility)
                 for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED))


@pytest.mark.parametrize('edition,scenario,executor', [
    ('original', rc.SCENARIO_GREAT_REVOLT, rc.BELGAE),
    ('second-edition', rc.SCENARIO_GREAT_REVOLT, rc.AEDUI),
    ('legacy', rc.SCENARIO_ARIOVISTUS, rc.GERMANS),
])
def test_authored_selection_spans_regions_and_leaves_other_cohorts(edition, scenario, executor):
    state = position(edition, scenario)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 2, piece_state=rc.REVEALED)
    before = get_available(state, rc.ROMANS, rc.AUXILIA)
    choices = [selection(rc.SCOUTED, 3), selection(rc.REVEALED, 1, rc.PROVINCIA)]
    assert play(state, {'piece_choices': choices}, executor)['executed']
    assert counts(state) == (3, 2, 1)
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 1
    assert get_available(state, rc.ROMANS, rc.AUXILIA) == before + 4
    assert validate_state(state) == []


@pytest.mark.parametrize('params', [
    {'piece_choices': [selection(rc.SCOUTED, 3)]},
    {'piece_choices': [selection(rc.REVEALED, 1), selection(rc.REVEALED, 3)]},
    {'piece_choices': [selection(rc.SCOUTED, 4, faction=rc.BELGAE)]},
    {'piece_choices': [selection(rc.SCOUTED, 4)], 'removals': []},
    {'removals': [{'region': rc.SEQUANI, 'faction': rc.BELGAE}]},
])
def test_invalid_plan_rolls_back(params):
    state = position('second-edition')
    before = encode(board_copy(state))
    assert play(state, params)['rejected']
    assert encode(board_copy(state)) == before


@pytest.mark.parametrize('edition,params', [
    ('original', {'auxilia_removal_regions': [[rc.SEQUANI, 1]]}),
    ('second-edition', {'removals': [{'region': rc.SEQUANI}]}),
])
def test_legacy_region_preferences_keep_their_order_and_fill_the_remainder(edition, params):
    state = position(edition)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 4)
    assert play(state, params)['executed']
    assert counts(state) == (2, 2, 4)
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 1


def test_revised_nonplayer_removes_available_scouted_auxilia_even_without_a_plan():
    state = position('second-edition', populate=False)
    state['non_player_factions'] = {rc.BELGAE}
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 2, piece_state=rc.SCOUTED)
    assert play(state, npc=True)['executed']
    assert counts(state) == (0, 0, 0)


def test_belgic_bot_removes_from_belgica_first_and_completes_the_total():
    state = position(populate=False)
    state['non_player_factions'] = {rc.BELGAE}
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 4)
    assert play(state, npc=True)['executed']
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 1


def test_german_bot_needs_an_in_scope_target_and_prioritizes_both_tiers():
    from fs_bot.bots.german_bot import node_g3b

    state = position('legacy', rc.SCENARIO_ARIOVISTUS, populate=False)
    state['non_player_factions'] = {rc.GERMANS}
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 4)
    assert np_event_available(state, 11, rc.GERMANS, True) is False
    assert node_g3b(state) == 'Yes'
    place_piece(state, rc.SUGAMBRI, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA)
    assert np_event_available(state, 11, rc.GERMANS, True) is True
    assert play(state, executor=rc.GERMANS, npc=True)['executed']
    assert count_pieces(state, rc.SUGAMBRI, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 2


def test_arverni_bot_maximizes_legions_left_without_auxilia():
    state = position(populate=False)
    state['non_player_factions'] = {rc.ARVERNI}
    for region, count in ((rc.CARNUTES, 3), (rc.MANDUBII, 2), (rc.SEQUANI, 2)):
        place_piece(state, region, rc.ROMANS, rc.LEGION, from_legions_track=True)
        place_piece(state, region, rc.ROMANS, rc.AUXILIA, count)
    assert play(state, executor=rc.ARVERNI, npc=True)['executed']
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 3
    for region in (rc.MANDUBII, rc.SEQUANI):
        assert count_pieces(state, region, rc.ROMANS, rc.AUXILIA) == 0


def test_empty_board_needs_no_removal_choice():
    state = position(populate=False)

    def agent(board, faction, request):
        if request['kind'] == KIND:
            pytest.fail('No Auxilia were on the map')

    state['decision_agent'] = agent
    assert play(state)['executed']


def test_live_request_uses_post_window_quantities_and_executor_ownership():
    state = position('second-edition', populate=False)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 4, piece_state=rc.SCOUTED)
    offered = []

    def agent(board, faction, request):
        if request['kind'] == KIND:
            offered.append((faction, request['required'], request['available']))
            return {'selections': request['available']}

    state['decision_agent'] = agent
    params = {'stage_timing_actions': {'11.piece_choice': [{'kind': 'voluntary_removal',
        'response': {'operations': [{'action': 'remove', 'region': rc.SEQUANI,
                                     'piece_type': rc.AUXILIA, 'piece_state': rc.SCOUTED,
                                     'count': 1}]}}]}}
    assert play(state, params, rc.ROMANS)['executed']
    assert offered == [(rc.ROMANS, {rc.AUXILIA: 3}, [selection(rc.SCOUTED, 3)])]
    assert counts(state) == (0, 0, 0)


def test_terminal_selects_scouted_auxilia():
    state = position('second-edition')
    output = StringIO()
    assert _collect_event_params(state, rc.BELGAE, 11, True, StringIO(), output) == {}
    terminal = make_cli_reactive({rc.BELGAE}, StringIO('board\n3\n4\n'), output)
    state['decision_agent'] = lambda b, f, r: terminal(b, f, r) if r['kind'] == KIND else None
    assert play(state)['executed']
    assert rc.SCOUTED in output.getvalue()
    assert counts(state) == (3, 2, 0)


def test_saved_assistant_choice_keeps_id_and_rejects_shortfall(tmp_path):
    state = position('second-edition')
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
    assert request['owner'] == rc.BELGAE and request['required'] == {rc.AUXILIA: 4}
    session.import_inbox({'decision_id': pending['id'], 'response': {'selections': []}})
    with pytest.raises(DecisionPending):
        attempt(session)
    assert session.error and session.data['pending'] == pending
    assert encode(board_copy(state)) == initial

    path = tmp_path / 'numidians.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session_for(restored, meta, log)
    with pytest.raises(DecisionPending):
        attempt(resumed)
    assert resumed.data['pending'] == pending
    choices = [selection(rc.SCOUTED, 4)]
    resumed.import_inbox({'decision_id': pending['id'], 'response': {'selections': choices}})
    assert attempt(resumed)['executed']
    resumed.finish()
    reference = decode(initial)
    assert play(reference, {'piece_choices': choices})['executed']
    assert encode(board_copy(restored)) == encode(board_copy(reference))
    assert len(log) == 1 and validate_state(restored) == []
