"""§6.3/A6.3: owners select physical Quarters cohorts without changing visibility."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces_by_state, place_piece
from fs_bot.engine.quarters import (QuartersError, apply_relocations, preview_relocations,
                                    validate_quarters_plan, validate_provincia_response)
from fs_bot.state.serialize import encode, decode, save_game, load_game
from fs_bot.state.state_schema import build_initial_state, validate_state

STATES = (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)
SEATS = [(scenario, faction) for scenario, factions in (
    (rc.SCENARIO_GREAT_REVOLT, (rc.BELGAE, rc.AEDUI, rc.ARVERNI, rc.ROMANS)),
    (rc.SCENARIO_ARIOVISTUS, (rc.BELGAE, rc.AEDUI, rc.GERMANS, rc.ROMANS)))
    for faction in factions]


def position(faction=rc.BELGAE, scenario=rc.SCENARIO_GREAT_REVOLT):
    state = build_initial_state(scenario, seed=1)
    state['non_player_factions'] = set(rc.FACTIONS)
    piece = rc.AUXILIA if faction == rc.ROMANS else rc.WARBAND
    for visibility in STATES:
        place_piece(state, rc.MORINI, faction, piece, 2, piece_state=visibility)
    place_piece(state, rc.ATREBATES, faction, piece)
    return state, piece


def counts(state, region, faction, piece):
    return tuple(count_pieces_by_state(state, region, faction, piece, ps) for ps in STATES)


@pytest.mark.parametrize('scenario,faction', SEATS)
@pytest.mark.parametrize('visibility', STATES)
def test_owner_selects_exact_adjacent_visibility(scenario, faction, visibility):
    state, piece = position(faction, scenario)
    move = (piece, rc.MORINI, rc.ATREBATES, 1, visibility)
    before = encode(state)
    assert validate_quarters_plan(state, {faction: [move]}, faction=faction) == []
    preview = preview_relocations(state, faction, [move])
    assert encode(state) == before
    result = apply_relocations(state, faction, [move])
    expected = tuple(2 - (ps == visibility) for ps in STATES)
    assert counts(state, rc.MORINI, faction, piece) == expected
    assert counts(state, rc.ATREBATES, faction, piece) == tuple(
        (ps == rc.HIDDEN) + (ps == visibility) for ps in STATES)
    assert encode(state) == encode(preview)
    assert result['moves'] == [move] and validate_state(state) == []


def test_legacy_four_entries_keep_hidden_first_selection():
    state, piece = position()
    apply_relocations(state, rc.BELGAE, [(piece, rc.MORINI, rc.ATREBATES, 3)])
    assert counts(state, rc.MORINI, rc.BELGAE, piece) == (0, 1, 2)
    assert counts(state, rc.ATREBATES, rc.BELGAE, piece) == (3, 1, 0)


@pytest.mark.parametrize('moves', [
    [(rc.WARBAND, rc.MORINI, rc.ATREBATES, 3, rc.REVEALED)],
    [(rc.WARBAND, rc.MORINI, rc.ATREBATES, 2, rc.REVEALED)] * 2,
    [(rc.WARBAND, rc.MORINI, rc.ATREBATES, 3),
     (rc.WARBAND, rc.MORINI, rc.ATREBATES, 2, rc.REVEALED)],
    [(rc.WARBAND, rc.MORINI, rc.ATREBATES, 1, None)],
    [(rc.WARBAND, rc.MORINI, rc.ATREBATES, 1, 'invisible')],
    [(rc.WARBAND, rc.MORINI, rc.ATREBATES, True, rc.HIDDEN)],
    [(rc.WARBAND, rc.MORINI, rc.ATREBATES, 1.5, rc.HIDDEN)],
    [(rc.WARBAND, rc.MORINI, rc.ATREBATES, 0, rc.HIDDEN)],
    [(rc.WARBAND, rc.MORINI, rc.ATREBATES, 1, rc.HIDDEN, None)],
    [(rc.LEADER, rc.MORINI, rc.ATREBATES, 1, rc.HIDDEN)],
    [(rc.ALLY, rc.MORINI, rc.ATREBATES, 1, rc.HIDDEN)],
])
def test_invalid_or_overclaimed_cohorts_are_atomic(moves):
    state, _ = position(); before = encode(state)
    assert validate_quarters_plan(state, {rc.BELGAE: moves})
    with pytest.raises(QuartersError):
        apply_relocations(state, rc.BELGAE, moves)
    assert encode(state) == before


def test_arriving_visibility_cannot_replace_an_original_adjacent_cohort():
    state, piece = position()
    place_piece(state, rc.MANDUBII, rc.BELGAE, piece)
    moves = [(piece, rc.MORINI, rc.ATREBATES, 2, rc.REVEALED),
             (piece, rc.ATREBATES, rc.MANDUBII, 1, rc.REVEALED)]
    before = encode(state)
    with pytest.raises(QuartersError):
        apply_relocations(state, rc.BELGAE, moves)
    assert encode(state) == before


def test_original_cohort_departure_does_not_take_same_type_arrivals():
    state, piece = position()
    place_piece(state, rc.MANDUBII, rc.BELGAE, piece)
    apply_relocations(state, rc.BELGAE, [
        (piece, rc.MORINI, rc.ATREBATES, 2, rc.REVEALED),
        (piece, rc.ATREBATES, rc.MANDUBII, 1, rc.HIDDEN)])
    assert counts(state, rc.ATREBATES, rc.BELGAE, piece) == (0, 2, 0)
    assert counts(state, rc.MANDUBII, rc.BELGAE, piece) == (2, 0, 0)


def test_exact_preview_never_consults_host_or_live_rng_and_refusal_moves_nothing():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=1)
    state['non_player_factions'] = set()
    place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND, piece_state=rc.SCOUTED)
    place_piece(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND, 4)
    calls = []
    def refuse(board, faction, request):
        calls.append((faction, request['request_type']))
        return False
    state['decision_agent'] = refuse
    from fs_bot.tools.seat_session import board_copy
    before = encode(board_copy(state))
    moves = [(rc.WARBAND, rc.MORINI, rc.ATREBATES, 1, rc.SCOUTED)]
    assert validate_quarters_plan(state, {rc.BELGAE: moves}) == []
    assert not calls and encode(board_copy(state)) == before
    with pytest.raises(QuartersError, match='did not agree'):
        apply_relocations(state, rc.BELGAE, moves)
    assert calls == [(rc.AEDUI, 'quarters')] and encode(board_copy(state)) == before


@pytest.mark.parametrize('visibility', STATES)
def test_roman_supplied_provincia_step_preserves_selected_visibility(visibility):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=1)
    state['non_player_factions'] = set(rc.FACTIONS)
    for ps in STATES:
        place_piece(state, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA, piece_state=ps)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    apply_relocations(state, rc.ROMANS, [
        (rc.AUXILIA, rc.AEDUI_REGION, rc.PROVINCIA, 1, visibility)])
    assert counts(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == tuple(ps == visibility for ps in STATES)
    assert counts(state, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA) == tuple(ps != visibility for ps in STATES)


def test_roman_adjacent_arrival_may_take_later_provincia_step_in_same_visibility():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=1)
    state['non_player_factions'] = set(rc.FACTIONS)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA, piece_state=rc.SCOUTED)
    place_piece(state, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    apply_relocations(state, rc.ROMANS, [
        (rc.AUXILIA, rc.MANDUBII, rc.AEDUI_REGION, 1, rc.SCOUTED),
        (rc.AUXILIA, rc.AEDUI_REGION, rc.PROVINCIA, 1, rc.SCOUTED)])
    assert counts(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == (0, 0, 1)
    assert counts(state, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA) == (1, 0, 0)


@pytest.mark.parametrize('moves,valid', [
    ([(rc.AUXILIA, rc.MORINI, rc.PROVINCIA, 2, rc.REVEALED)], True),
    ([(rc.AUXILIA, rc.MORINI, rc.PROVINCIA, 3, rc.REVEALED)], False),
    ([(rc.AUXILIA, rc.MORINI, rc.PROVINCIA, 2, rc.REVEALED)] * 2, False),
    ([(rc.AUXILIA, rc.MORINI, rc.PROVINCIA, 3),
      (rc.AUXILIA, rc.MORINI, rc.PROVINCIA, 2, rc.REVEALED)], False),
    ([(rc.AUXILIA, rc.MORINI, rc.PROVINCIA, 2, rc.REVEALED),
      (rc.AUXILIA, rc.MORINI, rc.PROVINCIA, 2, rc.SCOUTED)], False),
])
def test_continuation_enforces_both_visibility_and_offered_total(moves, valid):
    state, _ = position(rc.ROMANS); before = encode(state)
    request = {'legal_moves': [[rc.AUXILIA, rc.MORINI, rc.PROVINCIA, 3]]}
    if valid:
        assert validate_provincia_response(state, request, {'moves': moves}) == {'moves': moves}
    else:
        with pytest.raises(QuartersError):
            validate_provincia_response(state, request, {'moves': moves})
    assert encode(state) == before


@pytest.mark.parametrize('visibility,expected', [(rc.REVEALED, 1), (rc.SCOUTED, 0)])
def test_continuation_default_never_substitutes_a_different_visibility(visibility, expected):
    from fs_bot.engine.quarters import _reconsider_provincia
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=1)
    state['non_player_factions'] = set(rc.FACTIONS)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, piece_state=rc.REVEALED)
    move = (rc.AUXILIA, rc.MORINI, rc.PROVINCIA, 2, visibility)
    request = {'legal_moves': [[rc.AUXILIA, rc.MORINI, rc.PROVINCIA, 3]], 'original_moves': [move]}
    before = encode(state)
    result = _reconsider_provincia(state, request)
    assert result == ([(*move[:3], expected, visibility)] if expected else [])
    assert encode(state) == before


def test_terminal_authors_exact_cohort_and_allows_board_inspection():
    from fs_bot.cli.quarters import collect_quarters_plan
    from fs_bot.cli.menus import set_board_hook
    state, piece = position(); output = StringIO(); inspected = []
    before = encode(state)
    set_board_hook(lambda: inspected.append(True))
    try:
        plan = collect_quarters_plan(state, rc.BELGAE, {}, StringIO(
            f'board\n2\n{piece} ({rc.SCOUTED}) from {rc.MORINI}\n{rc.ATREBATES}\n1\n1\n'), output)
    finally:
        set_board_hook(None)
    assert plan == {rc.BELGAE: [(piece, rc.MORINI, rc.ATREBATES, 1, rc.SCOUTED)]}
    assert inspected == [True] and encode(state) == before
    assert f'({rc.SCOUTED})' in output.getvalue()


def test_terminal_provincia_authors_exact_cohort():
    from fs_bot.cli.quarters import collect_provincia
    state, piece = position(rc.ROMANS); before = encode(state)
    request = {'legal_moves': [[piece, rc.MORINI, rc.PROVINCIA, 3]]}
    response = collect_provincia(state, rc.ROMANS, request, StringIO(
        f'1\n{piece} ({rc.REVEALED}) from {rc.MORINI} (up to 2)\n2\n1\n'), StringIO())
    assert response == {'moves': [(piece, rc.MORINI, rc.PROVINCIA, 2, rc.REVEALED)]}
    assert validate_provincia_response(state, request, response) == response
    assert encode(state) == before


@pytest.mark.parametrize('bad', [None, {rc.BELGAE: [(rc.WARBAND, rc.MORINI, rc.ATREBATES, 3, rc.SCOUTED)]}])
def test_exact_plan_pending_save_resume_and_identical_replay(tmp_path, bad):
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.engine.winter import quarters_phase
    from fs_bot.tools.seat_session import SeatSession, DecisionPending, board_copy
    state, piece = position(); origin = deepcopy(state)
    state['non_player_factions'].discard(rc.BELGAE)
    origin['non_player_factions'].discard(rc.BELGAE)
    def session_for(board, meta=None, log=None):
        session = SeatSession(board, meta or {'seat': rc.BELGAE}, log if log is not None else [],
                              HumanTurnDisplay(StringIO()))
        board['decision_agent'] = session.reactive
        return session
    def attempt(session):
        def driver(*args): pass
        driver.transaction_checkpoint = session.checkpoint
        driver.transaction_restore = session.restore
        with _action_transaction(session.state, driver):
            return quarters_phase(session.state)
    session = session_for(state); before = encode(board_copy(state))
    with pytest.raises(DecisionPending): attempt(session)
    pending = deepcopy(session.data['pending'])
    assert decode(pending['request'])['kind'] == 'quarters_plan'
    session.import_inbox({'decision_id': pending['id'], 'response': bad})
    with pytest.raises(DecisionPending): attempt(session)
    assert session.data['pending']['id'] == pending['id'] and not session.data['journal']
    assert encode(board_copy(state)) == before
    path = tmp_path / 'quarters.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session_for(restored, meta, log)
    answer = {rc.BELGAE: [(piece, rc.MORINI, rc.ATREBATES, 2, rc.SCOUTED)]}
    resumed.import_inbox({'decision_id': pending['id'], 'response': answer})
    result = attempt(resumed); resumed.finish()
    assert counts(restored, rc.MORINI, rc.BELGAE, piece) == (2, 2, 0)
    assert counts(restored, rc.ATREBATES, rc.BELGAE, piece) == (1, 0, 2)
    replay = session_for(origin)
    replay.data['queue'] = [SeatSession._inbox_entry(entry) for entry in resumed.log]
    replay.data['expected'] = [
        {'id': e['assistant_id'], 'signature': e['assistant_signature'],
         'request': e['assistant_request'],
         'action_windows_version': e.get('assistant_action_windows_version', 0)}
        for e in resumed.log]
    assert attempt(replay) == result
    replay.finish()
    assert replay.log == resumed.log and encode(board_copy(origin)) == encode(board_copy(restored))
    assert validate_state(restored) == []


def interrupted_position():
    """A real Pax entry removes Supply only after the adjacent step commits."""
    from fs_bot.engine.spring import UNLOCK_KEY
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=91)
    state['spring_box_leaders'] = [rc.VERCINGETORIX]
    state['available'][rc.ARVERNI][rc.LEADER] -= 1
    state[UNLOCK_KEY] = True
    state['non_player_factions'] = {rc.AEDUI, rc.BELGAE}
    state['current_card'] = rc.WINTER_CARD
    state['winter_count'] = 1
    place_piece(state, rc.MORINI, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(state, rc.MORINI, rc.ARVERNI, rc.WARBAND)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, piece_state=rc.REVEALED)
    moves = [(rc.AUXILIA, rc.NERVII, rc.ATREBATES, 1, rc.HIDDEN),
             (rc.LEGION, rc.MORINI, rc.PROVINCIA, 1)]
    return state, moves


def test_live_supply_reconsideration_selects_exact_visibility_after_committed_adjacent_step():
    state, moves = interrupted_position(); requests = []
    def agent(board, faction, request):
        requests.append(request['kind'])
        if request['kind'] == 'spring_leader':
            return {'region': rc.MORINI}
        if request['kind'] == 'agreement':
            return False
        assert request['kind'] == 'quarters_provincia'
        assert counts(board, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == (2, 1, 0)
        return {'moves': [(rc.AUXILIA, rc.ATREBATES, rc.PROVINCIA, 1, rc.REVEALED)]}
    agent.supports_action_windows = True
    state['decision_agent'] = agent
    result = apply_relocations(state, rc.ROMANS, moves)
    assert result['moves'] == [moves[0], (rc.AUXILIA, rc.ATREBATES, rc.PROVINCIA, 1, rc.REVEALED)]
    assert result['reconsider_quartering']
    assert requests == ['spring_leader', 'agreement', 'quarters_provincia']
    assert counts(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == (0, 1, 0)
    assert counts(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == (2, 0, 0)
    assert validate_state(state) == []


def test_exact_continuation_pending_save_resume_and_identical_replay(tmp_path):
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.tools.seat_session import SeatSession, DecisionPending, board_copy
    state, moves = interrupted_position(); origin = deepcopy(state); before = encode(state)
    def session_for(board, meta=None, log=None):
        session = SeatSession(board, meta or {'seat': rc.ROMANS}, log if log is not None else [],
                              HumanTurnDisplay(StringIO()))
        def agent(current, faction, request):
            if request['kind'] == 'spring_leader':
                return {'region': rc.MORINI}
            if request['kind'] == 'agreement':
                return False
            return session.reactive(current, faction, request)
        agent.supports_action_windows = True
        board['decision_agent'] = agent
        return session
    def attempt(session):
        def driver(*args): pass
        driver.transaction_checkpoint = session.checkpoint
        driver.transaction_restore = session.restore
        with _action_transaction(session.state, driver):
            return apply_relocations(session.state, rc.ROMANS, moves)
    session = session_for(state)
    with pytest.raises(DecisionPending): attempt(session)
    pending = deepcopy(session.data['pending'])
    assert decode(pending['request'])['kind'] == 'quarters_provincia'
    assert counts(decode(pending['board']), rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == (2, 1, 0)
    bad = {'moves': [(rc.AUXILIA, rc.ATREBATES, rc.PROVINCIA, 2, rc.REVEALED)]}
    session.import_inbox({'decision_id': pending['id'], 'response': bad})
    with pytest.raises(DecisionPending): attempt(session)
    assert session.data['pending']['id'] == pending['id']
    assert encode(board_copy(state)) == before and not session.data['journal']
    path = tmp_path / 'continuation.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session_for(restored, meta, log)
    answer = {'moves': [(rc.AUXILIA, rc.ATREBATES, rc.PROVINCIA, 1, rc.REVEALED)]}
    resumed.import_inbox({'decision_id': pending['id'], 'response': answer})
    result = attempt(resumed); resumed.finish()
    replay = session_for(origin)
    replay.data['queue'] = [SeatSession._inbox_entry(e) for e in resumed.log]
    replay.data['expected'] = [
        {'id': e['assistant_id'], 'signature': e['assistant_signature'],
         'request': e['assistant_request'],
         'action_windows_version': e.get('assistant_action_windows_version', 0)}
        for e in resumed.log]
    assert attempt(replay) == result
    replay.finish()
    assert replay.log == resumed.log and encode(board_copy(origin)) == encode(board_copy(restored))
    assert counts(restored, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == (0, 1, 0)
    assert validate_state(restored) == []
