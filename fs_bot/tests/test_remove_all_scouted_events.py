"""A25/A26/A30/A56 remove all eligible Warbands, including Scouted (§1.4.3)."""
from copy import deepcopy
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board import pieces
from fs_bot.cards.card_effects import _ally_tribe, execute_event
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT, _action_transaction
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import (
    build_initial_state, check_structural_integrity, validate_state,
)
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


CASES = [
    ('A25', rc.GERMANS, (rc.CISALPINA,), rc.TRIBE_NORI, 6),
    ('A26', rc.ARVERNI, (rc.SEQUANI, rc.AEDUI_REGION), rc.TRIBE_HELVETII, 0),
    ('A30', rc.ARVERNI, (rc.SEQUANI,), rc.TRIBE_SEQUANI, 0),
    ('A56', rc.BELGAE, (rc.ATREBATES,), rc.TRIBE_ATREBATES, 4),
]


def position(case, scenario=rc.SCENARIO_ARIOVISTUS, mixed=True):
    card, faction, regions, tribe, cost = case
    state = build_initial_state(scenario, seed=22)
    state['non_player_factions'] = set()
    state['executing_faction'] = rc.ROMANS
    if cost:
        state['resources'][faction] = 10
    state['event_params'] = {'region': regions[0]} if card == 'A30' else {}
    for region in regions:
        for visibility, count in ((rc.HIDDEN, 1), (rc.REVEALED, 2), (rc.SCOUTED, 3)):
            if mixed or visibility == rc.SCOUTED:
                pieces.place_piece(state, region, faction, rc.WARBAND,
                                   count, piece_state=visibility)
        # These belong to another faction, even though they share the Region.
        pieces.place_piece(state, region, rc.AEDUI, rc.WARBAND,
                           piece_state=rc.SCOUTED)
    pieces.place_piece(state, rc.VENETI, faction, rc.WARBAND,
                       piece_state=rc.SCOUTED)
    pieces.place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA)
    assert _ally_tribe(state, tribe, faction)
    if card == 'A25':
        pieces.place_piece(state, rc.CISALPINA, faction, rc.SETTLEMENT)
        pieces.place_piece(state, rc.CISALPINA, faction, rc.LEADER,
                           leader_name=rc.ARIOVISTUS_LEADER)
    elif card == 'A56':
        pieces.place_piece(state, rc.ATREBATES, faction, rc.LEADER,
                           leader_name=rc.AMBIORIX)
    elif card == 'A26':
        # Divico removes the Helvetii Ally, not every Ally in those Regions.
        assert _ally_tribe(state, rc.TRIBE_SEQUANI, faction)
    assert validate_state(state) == []
    assert check_structural_integrity(state) == []
    return state


def assert_removals(state, before, case):
    card, faction, regions, tribe, cost = case
    removed = sum(pieces.count_pieces(before, r, faction, rc.WARBAND) for r in regions)
    assert pieces.get_available(state, faction, rc.WARBAND) == (
        pieces.get_available(before, faction, rc.WARBAND) + removed)
    for region in regions:
        assert pieces.count_pieces(state, region, faction, rc.WARBAND) == 0
        assert state['spaces'][region]['pieces'][rc.AEDUI] == before['spaces'][region]['pieces'][rc.AEDUI]
        assert pieces.get_leader_in_region(state, region, faction) == pieces.get_leader_in_region(before, region, faction)
    for region in state['spaces']:
        if region not in regions:
            assert state['spaces'][region] == before['spaces'][region]
    assert state['tribes'][tribe]['allied_faction'] is None
    assert pieces.get_available(state, faction, rc.ALLY) == pieces.get_available(before, faction, rc.ALLY) + 1
    if card == 'A25':
        assert pieces.count_pieces(state, rc.CISALPINA, faction, rc.SETTLEMENT) == 0
        assert pieces.get_available(state, faction, rc.SETTLEMENT) == pieces.get_available(before, faction, rc.SETTLEMENT) + 1
    elif card == 'A26':
        assert state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] == faction
        assert pieces.count_pieces(state, rc.SEQUANI, faction, rc.ALLY) == 1
    assert state['resources'][faction] == before['resources'][faction] - cost
    assert state['rng'].getstate() == before['rng'].getstate()
    assert validate_state(state) == []
    assert check_structural_integrity(state) == []


@pytest.mark.parametrize('case', CASES, ids=lambda case: case[0])
@pytest.mark.parametrize('scenario', [rc.SCENARIO_ARIOVISTUS, rc.SCENARIO_GALLIC_WAR])
@pytest.mark.parametrize('mixed', [False, True], ids=['scouted_only', 'all_visibilities'])
def test_remove_all_includes_scouted_and_preserves_other_pieces(case, scenario, mixed):
    state = position(case, scenario, mixed)
    before = deepcopy(state)
    execute_event(state, case[0], shaded=False)
    assert_removals(state, before, case)


def session_for(state, meta=None, log=None):
    session = SeatSession(state, meta if meta is not None else {'seat': rc.ROMANS},
                          log if log is not None else [], HumanTurnDisplay(io.StringIO()))
    state['decision_agent'] = session.reactive
    return session


def run_session(session, card):
    def driver(*args):
        pass
    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    driver.transaction_complete = session.transaction_complete
    action = {'command': rc.FIRST_DID_EVENT, 'details': {
        'card_id': card, 'text_preference': rc.EVENT_UNSHADED,
        'event_params': session.state['event_params']}}
    with _action_transaction(session.state, driver):
        result = execute_decision(session.state, rc.ROMANS, {
            'action': ACTION_EVENT, 'player_action': action})
    session.finish()
    return result


@pytest.mark.parametrize('case', CASES, ids=lambda case: case[0])
def test_durable_event_save_resume_and_exact_replay(case, tmp_path):
    state = position(case)
    state['_card_turn'] = {'idx': 0}
    before = deepcopy(state)
    initial = encode(state)
    session = session_for(state)
    with pytest.raises(DecisionPending):
        run_session(session, case[0])
    pending = deepcopy(session.data['pending'])
    assert decode(pending['request'])['kind'] == 'voluntary_removal'
    assert encode(board_copy(state)) == initial
    path = tmp_path / 'pending-event.json'
    save_game(state, path, meta=session.meta, log=session.log)
    saved, meta, log = load_game(path)
    resumed = session_for(saved, meta, log)
    assert resumed.data['pending'] == pending
    for _ in range(10):
        pending = resumed.data['pending']
        assert decode(pending['request'])['kind'] == 'voluntary_removal'
        resumed.import_inbox({'decision_id': pending['id'], 'response': {'done': True}})
        try:
            result = run_session(resumed, case[0])
            break
        except DecisionPending:
            continue
    else:
        pytest.fail('Event did not complete after its optional timing windows')
    assert result['executed'], result
    assert_removals(resumed.state, before, case)
    replay = session_for(decode(initial))
    replay.data['expected'] = [
        {'id': e['assistant_id'], 'signature': e['assistant_signature'],
         'request': e['assistant_request'],
         'action_windows_version': e.get('assistant_action_windows_version', 0)}
        for e in resumed.log]
    replay.import_inbox([replay._inbox_entry(e) for e in resumed.log])
    assert run_session(replay, case[0]) == result
    assert replay.log == resumed.log
    assert encode(board_copy(replay.state)) == encode(board_copy(resumed.state))
