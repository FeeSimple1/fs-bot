"""A2.1 Belgic force selection precedes the named Ambiorix placement."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board import pieces
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cli.display import HumanTurnDisplay, format_board
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.game_engine import _action_transaction, resolve_winter_card
from fs_bot.engine.interlude import _adjust_belgae_forces
from fs_bot.engine.interlude_reductions import BELGIC_HALF, KIND, reduction_request
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy, validate_response

BELGAE = rc.BELGAE
OTHER_SEATS = {rc.ROMANS, rc.AEDUI, rc.GERMANS}


def _position():
    state = build_initial_state(rc.SCENARIO_GALLIC_WAR, seed=41)
    state['non_player_factions'] = set(OTHER_SEATS)
    for tribe in (rc.TRIBE_MENAPII, rc.TRIBE_MORINI, rc.TRIBE_PICTONES, rc.TRIBE_MANDUBII):
        assert _ally_tribe(state, tribe, BELGAE)
    pieces.remove_piece(state, rc.MANDUBII, BELGAE, rc.ALLY)
    pieces.place_piece(state, rc.MANDUBII, BELGAE, rc.CITADEL)
    for region, visibility, count in ((rc.MANDUBII, rc.HIDDEN, 1),
                                      (rc.PICTONES, rc.REVEALED, 2),
                                      (rc.MORINI, rc.SCOUTED, 3),
                                      (rc.MORINI, rc.HIDDEN, 1),
                                      (rc.NERVII, rc.HIDDEN, 3)):
        pieces.place_piece(state, region, BELGAE, rc.WARBAND, count, piece_state=visibility)
    pieces.place_piece(state, rc.MORINI, BELGAE, rc.LEADER, leader_name=rc.SUCCESSOR)
    return state


def _cohort(request, count, **identity):
    row = next(row for row in request['cohorts']
               if all(row[key] == value for key, value in identity.items()))
    return dict(row, count=count)


def _removals(request):
    return [
        _cohort(request, 1, tribe=rc.TRIBE_PICTONES),
        _cohort(request, 1, tribe=rc.TRIBE_MORINI),
        _cohort(request, 1, region=rc.MANDUBII, piece_state=rc.HIDDEN),
        _cohort(request, 2, region=rc.PICTONES, piece_state=rc.REVEALED),
        _cohort(request, 3, region=rc.MORINI, piece_state=rc.SCOUTED),
    ]


def test_belgic_removal_is_exact_above_minimum_and_ambiorix_counts_survivors():
    state = _position()
    seen = []
    rng = state['rng'].getstate()

    def agent(board, faction, request):
        seen.append((faction, request))
        assert request['minimums'] == {rc.ALLY: 2, rc.WARBAND: 5}
        assert all(row['tribe'] != rc.TRIBE_MANDUBII for row in request['cohorts'])
        return {'removals': _removals(request)}

    state['decision_agent'] = agent
    result = _adjust_belgae_forces(state)
    assert [(faction, request['kind'], request['stage']) for faction, request in seen] == [
        (BELGAE, KIND, BELGIC_HALF)]
    assert result == {'allies_to_available': 2, 'warbands_to_available': 6,
                      'ambiorix_placed': rc.NERVII}
    assert state['tribes'][rc.TRIBE_MORINI]['allied_faction'] is None
    assert state['tribes'][rc.TRIBE_MENAPII]['allied_faction'] == BELGAE
    assert state['tribes'][rc.TRIBE_MANDUBII]['allied_faction'] == BELGAE
    assert pieces.count_pieces(state, rc.MANDUBII, BELGAE, rc.CITADEL) == 1
    assert pieces.count_pieces_by_state(state, rc.MORINI, BELGAE, rc.WARBAND, rc.HIDDEN) == 1
    assert pieces.count_pieces_by_state(state, rc.MORINI, BELGAE, rc.WARBAND, rc.SCOUTED) == 0
    assert pieces.get_leader_in_region(state, rc.NERVII, BELGAE) == rc.AMBIORIX
    assert state['rng'].getstate() == rng and validate_state(state) == []


@pytest.mark.parametrize('case', ['ally home early', 'warband home early', 'below minimum',
                                  'citadel', 'overspend', 'available', 'other faction'])
def test_illegal_belgic_selection_cannot_change_the_board(case):
    state = _position()
    request = dict(reduction_request(state, BELGIC_HALF), faction=BELGAE)
    rows = _removals(request)
    if case == 'ally home early':
        rows[0], rows[1] = rows[1], rows[0]
    elif case == 'warband home early':
        rows[3], rows[4] = rows[4], rows[3]
    elif case == 'below minimum':
        rows[-1]['count'] = 1
    elif case == 'citadel':
        rows[0] = dict(rows[0], region=rc.MANDUBII, tribe=rc.TRIBE_MANDUBII)
    elif case == 'overspend':
        rows.append(dict(rows[-1], count=1))
    elif case == 'available':
        rows[-1] = dict(rows[-1], region=None, piece_state=None)
    else:
        request['faction'] = rc.GERMANS
    before = encode(state)
    with pytest.raises(ValueError):
        validate_response(state, request, {'removals': rows})
    assert encode(state) == before


def test_belgic_npc_ignores_agent_and_explicit_delegation_matches_default():
    state = _position()
    npc = deepcopy(state)
    npc['non_player_factions'].add(BELGAE)
    calls = []
    npc['decision_agent'] = lambda *args: calls.append(args)
    state['decision_agent'] = lambda *args: {'use_default': True}
    assert _adjust_belgae_forces(state) == _adjust_belgae_forces(npc)
    assert not calls
    npc['non_player_factions'].remove(BELGAE)
    assert encode(board_copy(state)) == encode(board_copy(npc))


def test_belgic_terminal_collects_exact_plan_with_board_inspection():
    state = _position()
    request = reduction_request(state, BELGIC_HALF)
    output = StringIO()
    answers = '\n'.join([
        'board', 'y', 'Pictones Ally (Pictones)', 'Morini Ally (Morini)',
        'Mandubii Hidden Warbands (1)', 'Pictones Revealed Warbands (2)', '2',
        'Morini Scouted Warbands (3)', '3', 'Finish selection', '',
    ])
    agent = make_cli_reactive({BELGAE}, StringIO(answers), output)
    before = encode(state)
    assert agent(state, BELGAE, request) == {'removals': _removals(request)}
    assert format_board(state) in output.getvalue() and encode(state) == before


def _winter_position():
    state = setup_scenario(rc.SCENARIO_GALLIC_WAR, seed=41)
    state['non_player_factions'] = set(OTHER_SEATS)
    state['winter_count'] = 2
    state['current_card'] = rc.WINTER_CARD
    pieces.place_piece(state, rc.MORINI, BELGAE, rc.WARBAND, 3)
    return state


def _session(state, meta=None, log=None):
    session = SeatSession(state, {'seat': BELGAE} if meta is None else meta,
                          [] if log is None else log, HumanTurnDisplay(StringIO()))
    state['decision_agent'] = session.reactive
    return session


def _attempt(session):
    def driver(*args):
        pass

    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    with _action_transaction(session.state, driver):
        return resolve_winter_card(session.state)


def test_full_winter_keeps_belgic_plan_when_paused_for_ambiorix(tmp_path):
    session = _session(_winter_position())
    before = encode(board_copy(session.state))
    with pytest.raises(DecisionPending):
        _attempt(session)
    first = deepcopy(session.data['pending'])
    request = decode(first['request'])
    assert request['stage'] == BELGIC_HALF and request['faction'] == BELGAE
    session.import_inbox({'decision_id': first['id'], 'response': {'removals': []}})
    with pytest.raises(DecisionPending):
        _attempt(session)
    assert session.error and session.data['pending'] == first
    assert encode(board_copy(session.state)) == before and not session.data['journal']

    plan = {'removals': [_cohort(request, 1, tribe=rc.TRIBE_MORINI),
                         _cohort(request, 1, tribe=rc.TRIBE_NERVII),
                         _cohort(request, 3, region=rc.MORINI, piece_type=rc.WARBAND)]}
    session.import_inbox({'decision_id': first['id'], 'response': plan})
    with pytest.raises(DecisionPending):
        _attempt(session)
    second = deepcopy(session.data['pending'])
    leader = decode(second['request'])
    assert leader['kind'] == 'spring_leader' and leader['reason'] == 'interlude_ambiorix'
    assert set(leader['legal_regions']) == {rc.ATREBATES, rc.NERVII}
    assert len(session.data['journal']) == 1 and encode(board_copy(session.state)) == before
    assert second['id'] != first['id']

    path = tmp_path / 'belgic-winter.json'
    save_game(session.state, path, meta=session.meta, log=session.log)
    state, meta, log = load_game(path, validate=True)
    resumed = _session(state, meta, log)
    destination = {'region': rc.NERVII}
    resumed.import_inbox({'decision_id': second['id'], 'response': destination})
    result = _attempt(resumed)
    resumed.finish()
    assert len(log) == 2 and state['interlude_completed'] and validate_state(state) == []
    assert pieces.get_leader_in_region(state, rc.NERVII, BELGAE) == rc.AMBIORIX

    replay = _winter_position()
    plans = {KIND: plan, 'spring_leader': destination}
    replay['decision_agent'] = lambda board, faction, request: (
        plans.get(request['kind']) if faction == BELGAE else None)
    assert resolve_winter_card(replay) == result
    assert encode(board_copy(replay)) == encode(board_copy(state))
