"""A36 unshaded: the Event executor chooses the exact German removals."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_available, place_piece
from fs_bot.cards.base_piece_choices import KIND, a36_removal_request
from fs_bot.cards.event_eval import is_event_effective
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT, _action_transaction
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def position(scenario=rc.SCENARIO_ARIOVISTUS, *, seed=36, populated=True):
    state = build_initial_state(scenario, seed=seed)
    state['current_card'] = 'A36'
    if populated:
        for region in (rc.MORINI, rc.NERVII, rc.TREVERI):
            place_piece(state, region, rc.GERMANS, rc.SETTLEMENT)
            for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
                place_piece(state, region, rc.GERMANS, rc.WARBAND, 3, piece_state=visibility)
        place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.SETTLEMENT)
        place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, 3)
    return state


def entry(region, kind, count=1, visibility=None):
    return {'region': region, 'target_faction': rc.GERMANS, 'piece_type': kind,
            'piece_state': visibility, 'count': count}


def choices():
    return [
        entry(rc.NERVII, rc.SETTLEMENT), entry(rc.TREVERI, rc.SETTLEMENT),
        entry(rc.NERVII, rc.WARBAND, 2, rc.REVEALED),
        entry(rc.NERVII, rc.WARBAND, 3, rc.SCOUTED),
        entry(rc.TREVERI, rc.WARBAND, 3, rc.SCOUTED),
    ]


def play(state, executor=rc.ROMANS, params=None, *, npc=False):
    action = {'command': rc.FIRST_DID_EVENT, 'regions': [],
              'details': {'card_id': 'A36', 'text_preference': rc.EVENT_UNSHADED,
                          'event_params': params or {}}}
    return execute_decision(state, executor, {'action': ACTION_EVENT,
                            ('bot_action' if npc else 'player_action'): action})


@pytest.mark.parametrize('scenario', rc.ARIOVISTUS_SCENARIOS)
@pytest.mark.parametrize('executor', [rc.ROMANS, rc.GERMANS])
def test_exact_plan_splits_settlements_and_warbands_across_regions(scenario, executor):
    state = position(scenario)
    before = {kind: get_available(state, rc.GERMANS, kind) for kind in (rc.SETTLEMENT, rc.WARBAND)}
    assert play(state, executor, {'piece_choices': choices()})['executed']
    for region, warbands in ((rc.MORINI, 9), (rc.SUGAMBRI, 3)):
        assert count_pieces(state, region, rc.GERMANS, rc.SETTLEMENT) == 1
        assert count_pieces(state, region, rc.GERMANS, rc.WARBAND) == warbands
    assert count_pieces(state, rc.NERVII, rc.GERMANS, rc.SETTLEMENT) == 0
    assert count_pieces(state, rc.TREVERI, rc.GERMANS, rc.SETTLEMENT) == 0
    assert count_pieces_by_state(state, rc.NERVII, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 3
    assert count_pieces_by_state(state, rc.NERVII, rc.GERMANS, rc.WARBAND, rc.REVEALED) == 1
    assert count_pieces_by_state(state, rc.NERVII, rc.GERMANS, rc.WARBAND, rc.SCOUTED) == 0
    assert count_pieces_by_state(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, rc.SCOUTED) == 0
    assert get_available(state, rc.GERMANS, rc.SETTLEMENT) == before[rc.SETTLEMENT] + 2
    assert get_available(state, rc.GERMANS, rc.WARBAND) == before[rc.WARBAND] + 8
    assert validate_state(state) == []


@pytest.mark.parametrize('bad', [
    choices()[:-1],
    [dict(choices()[0], region=rc.SUGAMBRI), *choices()[1:]],
    [choices()[0], choices()[0], *choices()[2:]],
    [dict(choices()[0], piece_state=rc.HIDDEN), *choices()[1:]],
    [*choices()[:2], dict(choices()[2], target_faction=rc.BELGAE), *choices()[3:]],
])
def test_illegal_plans_do_not_remove_anything(bad):
    state = position()
    before = encode(board_copy(state))
    assert play(state, params={'piece_choices': bad})['rejected']
    assert encode(board_copy(state)) == before


@pytest.mark.parametrize('exact', [True, False])
def test_partial_execution_takes_every_eligible_scouted_piece(exact):
    state = position(populated=False)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.SETTLEMENT)
    place_piece(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, 3, piece_state=rc.SCOUTED)
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, 8)
    params = {'piece_choices': [entry(rc.NERVII, rc.SETTLEMENT),
                                entry(rc.TREVERI, rc.WARBAND, 3, rc.SCOUTED)]} if exact else None
    assert play(state, params=params, npc=not exact)['executed']
    assert count_pieces(state, rc.NERVII, rc.GERMANS, rc.SETTLEMENT) == 0
    assert count_pieces(state, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 0
    assert count_pieces(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND) == 8
    assert validate_state(state) == []


@pytest.mark.parametrize('executor,remaining', [(rc.ROMANS, rc.SCOUTED), (rc.GERMANS, rc.HIDDEN)])
def test_delegated_visibility_priority_depends_on_piece_owner(executor, remaining):
    state = position(populated=False)
    for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 4, piece_state=visibility)
    assert play(state, executor)['executed']
    assert count_pieces(state, rc.NERVII, rc.GERMANS, rc.WARBAND) == 4
    assert count_pieces_by_state(state, rc.NERVII, rc.GERMANS, rc.WARBAND, remaining) == 4


def test_tied_delegated_regions_use_seeded_choice():
    survivors = set()
    for seed in range(6):
        state = position(seed=seed)
        twin = decode(encode(state))
        assert play(state, npc=True)['executed']
        assert play(twin, npc=True)['executed']
        assert encode(board_copy(state)) == encode(board_copy(twin))
        survivors.add(tuple(r for r in (rc.MORINI, rc.NERVII, rc.TREVERI)
                            if count_pieces(state, r, rc.GERMANS, rc.SETTLEMENT)))
    assert len(survivors) > 1
    assert all(len(remaining) == 1 for remaining in survivors)


def test_effectiveness_requires_an_eligible_german_piece_and_no_empty_prompt():
    state = position(populated=False)
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.SETTLEMENT)
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, 8)
    place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND, 5)
    assert not is_event_effective(state, 'A36', shaded=False)
    state['decision_agent'] = lambda *args: pytest.fail('No pieces were eligible for an A36 choice')
    assert play(state)['executed']
    place_piece(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, piece_state=rc.SCOUTED)
    assert is_event_effective(state, 'A36', shaded=False)


def test_terminal_menu_uses_executors_seat_and_can_select_scouted_warbands():
    from fs_bot.cli.human_plan import _collect_event_params
    state = position(populated=False)
    place_piece(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, 3, piece_state=rc.SCOUTED)
    output = StringIO()
    assert _collect_event_params(state, rc.AEDUI, 'A36', False, StringIO(), output) == {}
    state['decision_agent'] = make_cli_reactive({rc.AEDUI}, StringIO('board\n1\n3\n'), output)
    assert play(state, rc.AEDUI)['executed']
    assert 'Aedui: remove 3 Warband' in output.getvalue()
    assert count_pieces(state, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 0


def test_pending_choice_survives_save_and_retry(tmp_path):
    state = position()
    initial = encode(board_copy(state))

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
            return play(session.state, rc.AEDUI)

    session = session_for(state)
    with pytest.raises(DecisionPending):
        attempt(session)
    pending = deepcopy(session.data['pending'])
    assert decode(pending['request'])['owner'] == rc.AEDUI
    session.import_inbox({'decision_id': pending['id'], 'response': {'selections': []}})
    with pytest.raises(DecisionPending):
        attempt(session)
    assert session.error and session.data['pending'] == pending
    assert encode(board_copy(state)) == initial
    path = tmp_path / 'a36.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session_for(restored, meta, log)
    with pytest.raises(DecisionPending):
        attempt(resumed)
    assert resumed.data['pending'] == pending
    resumed.import_inbox({'decision_id': pending['id'], 'response': {'selections': choices()}})
    assert attempt(resumed)['executed']
    resumed.finish()
    reference = decode(initial)
    assert play(reference, rc.AEDUI, {'piece_choices': choices()})['executed']
    assert encode(board_copy(restored)) == encode(board_copy(reference))
    assert len(log) == 1 and validate_state(restored) == []


def test_request_lists_settlement_identity_by_region():
    state = position()
    request = a36_removal_request(state)
    assert [row for row in request['available'] if row['piece_type'] == rc.SETTLEMENT] == [
        entry(region, rc.SETTLEMENT) for region in (rc.MORINI, rc.NERVII, rc.TREVERI)]


def test_choice_is_built_after_the_authored_event_timing_window():
    state = position(populated=False)
    place_piece(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, 2, piece_state=rc.SCOUTED)
    params = {'stage_timing_actions': {'A36.piece_choice': [{
        'kind': 'voluntary_removal', 'response': {'operations': [
            {'action': 'remove', 'region': rc.TREVERI, 'piece_type': rc.WARBAND,
             'piece_state': rc.SCOUTED, 'count': 1}
        ]}}]}}
    requests = []

    def agent(board, faction, request):
        if request['kind'] == KIND:
            requests.append((faction, request['required'][rc.WARBAND]))
            return {'selections': [entry(rc.TREVERI, rc.WARBAND, 1, rc.SCOUTED)]}

    state['decision_agent'] = agent
    assert play(state, rc.GERMANS, params)['executed']
    assert requests == [(rc.GERMANS, 1)]
    assert count_pieces(state, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 0
