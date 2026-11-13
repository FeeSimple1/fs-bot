"""LC10-01: adjacent Roman Quarters in Provincia precedes the Supply step."""

from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import calculate_control
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.quarters import collect_quarters_plan
from fs_bot.commands.rally import has_supply_line
from fs_bot.engine.game_engine import _action_transaction
from fs_bot.engine.quarters import (
    ADJACENT_STEP, SUPPLY_STEP, QuartersError, apply_relocations, validate_quarters_plan,
)
from fs_bot.engine.winter import quarters_phase, run_winter_round
from fs_bot.map.map_data import get_adjacent_for_state
from fs_bot.state.player_ownership import install
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession


def _position(scenario=rc.SCENARIO_GREAT_REVOLT, host=rc.AEDUI, origin=rc.ARVERNI_REGION):
    state = build_initial_state(scenario, seed=11)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    place_piece(state, origin, rc.ROMANS, rc.LEGION, from_legions_track=True)
    blocker = rc.GERMANS if scenario in rc.BASE_SCENARIOS else rc.ARVERNI
    place_piece(state, origin, blocker, rc.WARBAND, 2)
    if host is not None:
        place_piece(state, rc.PROVINCIA, host, rc.WARBAND, 2)
    state['resources'][rc.ROMANS] = 10
    assert not has_supply_line(state, origin, agreements=dict.fromkeys(rc.FACTIONS, True))
    return state


def _body(state):
    return encode({key: value for key, value in state.items() if key != 'decision_agent'})


def _assert_integrity(state):
    assert validate_state(state) == []
    assert check_structural_integrity(state) == []


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
@pytest.mark.parametrize('willing', [True, False])
def test_adjacent_provincia_checks_quarters_consent_in_public_phase(scenario, willing):
    state = _position(scenario)
    calls = []

    def choose(board, faction, request):
        calls.append((faction, request['request_type'], request['context']['region']))
        return willing

    state['decision_agent'] = choose
    moves = [(rc.LEGION, rc.ARVERNI_REGION, rc.PROVINCIA, 1)]
    plan = {rc.ROMANS: moves}
    before = _body(state)
    _assert_integrity(state)
    assert validate_quarters_plan(state, plan) == []
    assert calls == [] and _body(state) == before
    if willing:
        result = quarters_phase(state, relocations=plan)
        assert result['roman_relocation'] == moves
        assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == 1
        assert count_pieces(state, rc.ARVERNI_REGION, rc.ROMANS, rc.LEGION) == 0
        assert state['resources'][rc.ROMANS] == 10
    else:
        with pytest.raises(QuartersError, match='Aedui did not agree to Quarters in Provincia'):
            quarters_phase(state, relocations=plan)
        assert _body(state) == before
    assert calls == [(rc.AEDUI, 'quarters', rc.PROVINCIA)]
    _assert_integrity(state)


@pytest.mark.parametrize('scenario,host', [
    (rc.SCENARIO_GREAT_REVOLT, rc.GERMANS),
    (rc.SCENARIO_ARIOVISTUS, rc.GERMANS),
    (rc.SCENARIO_ARIOVISTUS, rc.ARVERNI),
    (rc.SCENARIO_GREAT_REVOLT, None),
])
def test_unsupplied_adjacent_move_requires_eligible_provincia_control(scenario, host):
    state = _position(scenario, host)
    if host is None:
        # The permanent Fort and one Warband tie.
        place_piece(state, rc.PROVINCIA, rc.AEDUI, rc.WARBAND)
        assert calculate_control(state, rc.PROVINCIA) == rc.NO_CONTROL
    calls = []
    state['decision_agent'] = lambda *args: calls.append(args) or True
    before = _body(state)
    moves = [(rc.LEGION, rc.ARVERNI_REGION, rc.PROVINCIA, 1)]
    assert validate_quarters_plan(state, {rc.ROMANS: moves})
    with pytest.raises(QuartersError, match='no agreed Supply Line'):
        apply_relocations(state, rc.ROMANS, moves)
    assert calls == [] and _body(state) == before
    _assert_integrity(state)


@pytest.mark.parametrize('reverse', [False, True])
def test_adjacent_provincia_group_uses_prearrival_control_and_exact_cohorts(reverse):
    state = _position()
    for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        place_piece(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA, piece_state=visibility)
    place_piece(state, rc.ARVERNI_REGION, rc.GERMANS, rc.WARBAND, 3)
    calls = []

    def choose(board, faction, request):
        calls.append((faction, request['request_type'], calculate_control(board, rc.PROVINCIA)))
        return True

    state['decision_agent'] = choose
    moves = [(rc.LEGION, rc.ARVERNI_REGION, rc.PROVINCIA, 1),
             (rc.AUXILIA, rc.ARVERNI_REGION, rc.PROVINCIA, 1, rc.SCOUTED)]
    if reverse:
        moves.reverse()
    assert validate_quarters_plan(state, {rc.ROMANS: moves}) == []
    apply_relocations(state, rc.ROMANS, moves)
    assert calls == [(rc.AEDUI, 'quarters', rc.AEDUI_CONTROL)]
    assert calculate_control(state, rc.PROVINCIA) == rc.ROMAN_CONTROL
    assert count_pieces_by_state(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, rc.SCOUTED) == 1
    assert count_pieces_by_state(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 1
    assert count_pieces_by_state(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 1
    _assert_integrity(state)


def test_adjacent_provincia_uses_quarters_before_supply_window():
    state = _position()
    place_piece(state, rc.PROVINCIA, rc.AEDUI, rc.WARBAND)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.LEGION, from_legions_track=True)
    moves = [(rc.LEGION, rc.ARVERNI_REGION, rc.PROVINCIA, 1),
             (rc.LEGION, rc.MORINI, rc.PROVINCIA, 1)]
    declarations = []

    def choose(board, faction, request):
        if request['kind'] == 'agreement':
            declarations.append((request['request_type'],
                                 count_pieces(board, rc.PROVINCIA, rc.ROMANS, rc.LEGION)))
            return True
        return None

    choose.supports_action_windows = True
    state['decision_agent'] = choose
    assert validate_quarters_plan(state, {rc.ROMANS: moves}) == []
    apply_relocations(state, rc.ROMANS, moves)
    assert declarations == [('quarters', 0), ('supply_line', 1)]
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == 2
    _assert_integrity(state)


def test_supplied_provincia_legacy_plan_does_not_require_destination_consent():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=11)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    place_piece(state, rc.PROVINCIA, rc.AEDUI, rc.WARBAND, 2)
    place_piece(state, rc.ARVERNI_REGION, rc.ROMANS, rc.LEGION, from_legions_track=True)
    declarations = []

    def choose(board, faction, request):
        declarations.append(request['request_type'])
        return request['request_type'] == 'supply_line'

    state['decision_agent'] = choose
    moves = [(rc.LEGION, rc.ARVERNI_REGION, rc.PROVINCIA, 1)]
    assert validate_quarters_plan(state, {rc.ROMANS: moves}) == []
    apply_relocations(state, rc.ROMANS, moves)
    assert declarations == ['supply_line']
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == 1
    _assert_integrity(state)


def test_legacy_provincia_rows_keep_supply_for_other_origins():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=11)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.SEQUANI, rc.GERMANS, rc.WARBAND)
    for region in get_adjacent_for_state(state, rc.TREVERI, rc.ROMANS):
        if region != rc.SEQUANI:
            place_piece(state, region, rc.GERMANS, rc.WARBAND)
    moves = [(rc.AUXILIA, rc.SEQUANI, rc.PROVINCIA, 2),
             (rc.LEGION, rc.TREVERI, rc.PROVINCIA, 1)]
    assert validate_quarters_plan(state, {rc.ROMANS: moves}) == []
    # An early departure from Sequani would expose Germanic Control before
    # Supply is frozen and cut off Treveri.
    assert validate_quarters_plan(state, {rc.ROMANS: [(*moves[0], ADJACENT_STEP), moves[1]]})
    apply_relocations(state, rc.ROMANS, moves)
    assert calculate_control(state, rc.SEQUANI) == rc.GERMANIC_CONTROL
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == 1
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 2
    _assert_integrity(state)


@pytest.mark.parametrize('step', [ADJACENT_STEP, SUPPLY_STEP])
def test_terminal_offers_both_ways_to_quarter_exact_provincia_cohort(step):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=11)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    place_piece(state, rc.PROVINCIA, rc.AEDUI, rc.WARBAND, 2)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, piece_state=rc.SCOUTED)
    output = StringIO()
    destination = 1 if step == ADJACENT_STEP else 2
    plan = collect_quarters_plan(
        state, rc.ROMANS, {}, StringIO(f'2\n2\n{destination}\n1\n1\n'), output)
    move = (rc.AUXILIA, rc.SEQUANI, rc.PROVINCIA, 1, rc.SCOUTED, step)
    assert plan[rc.ROMANS] == [move]
    assert 'Provincia (adjacent Quarters)' in output.getvalue()
    assert 'Provincia (Supply transfer)' in output.getvalue()
    requests = []

    def choose(board, faction, request):
        requests.append(request['request_type'])
        return request['request_type'] == ('quarters' if step == ADJACENT_STEP else 'supply_line')

    state['decision_agent'] = choose
    result = quarters_phase(state, relocations=plan)
    assert result['roman_relocation'] == [move[:-1]]
    assert requests == ['quarters' if step == ADJACENT_STEP else 'supply_line']
    assert count_pieces_by_state(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, rc.SCOUTED) == 1
    _assert_integrity(state)


def test_later_supply_continuation_keeps_adjacent_move_and_excludes_unsupplied_troops():
    state = _position(host=None)
    place_piece(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.ARVERNI_REGION, rc.GERMANS, rc.WARBAND)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(state, rc.MORINI, rc.AEDUI, rc.WARBAND, 2)
    moves = [(rc.LEGION, rc.ARVERNI_REGION, rc.PROVINCIA, 1),
             (rc.LEGION, rc.MORINI, rc.PROVINCIA, 1)]
    calls = []

    def choose(board, faction, request):
        calls.append(request['kind'])
        if request['kind'] == 'agreement':
            return False
        assert request['kind'] == 'quarters_provincia'
        assert request['original_moves'] == [list(moves[1])]
        assert request['legal_moves'] == []
        assert count_pieces(board, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == 1
        return {'decline': True}

    choose.supports_action_windows = True
    state['decision_agent'] = choose
    result = apply_relocations(state, rc.ROMANS, moves)
    assert calls == ['agreement', 'quarters_provincia']
    assert result == {'moves': [moves[0]], 'reconsider_quartering': True}
    assert count_pieces(state, rc.ARVERNI_REGION, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.MORINI, rc.ROMANS, rc.LEGION) == 1
    _assert_integrity(state)


def test_saved_adjacent_provincia_consent_replays_before_later_supply(tmp_path):
    state = _position()
    place_piece(state, rc.PROVINCIA, rc.AEDUI, rc.WARBAND)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.LEGION, from_legions_track=True)
    install(state, {rc.ROMANS: 'Player 1', rc.AEDUI: 'Player 1'})
    before = _body(state)
    moves = [(rc.LEGION, rc.ARVERNI_REGION, rc.PROVINCIA, 1),
             (rc.LEGION, rc.MORINI, rc.PROVINCIA, 1)]

    def open_session(board, meta, log):
        session = SeatSession(board, meta, log, HumanTurnDisplay(StringIO()))
        board['decision_agent'] = session.reactive
        return session

    def attempt(session):
        def driver(*args):
            pass
        driver.transaction_checkpoint = session.checkpoint
        driver.transaction_restore = session.restore
        driver.transaction_complete = session.transaction_complete
        with _action_transaction(session.state, driver):
            return apply_relocations(session.state, rc.ROMANS, moves)

    session = open_session(state, {'seat': rc.ROMANS, 'player_id': 'Player 1'}, [])
    with pytest.raises(DecisionPending):
        attempt(session)
    first = session.data['pending']
    request = decode(first['request'])
    assert request['request_type'] == 'quarters'
    assert request['context']['region'] == rc.PROVINCIA
    assert _body(state) == before
    session.import_inbox({'decision_id': first['id'], 'response': True})
    with pytest.raises(DecisionPending):
        attempt(session)
    later = session.data['pending']
    assert decode(later['request'])['request_type'] == 'supply_line'
    assert count_pieces(decode(later['board']), rc.PROVINCIA, rc.ROMANS, rc.LEGION) == 1
    assert len(session.data['journal']) == 1 and _body(state) == before

    path = tmp_path / 'adjacent-province.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = open_session(restored, meta, log)
    with pytest.raises(DecisionPending):
        attempt(resumed)
    assert resumed.data['pending'] == later
    for player in (session, resumed):
        player.import_inbox({'decision_id': later['id'], 'response': True})
        assert attempt(player)['moves'] == moves
        assert count_pieces(player.state, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == 2
        _assert_integrity(player.state)
    assert _body(restored) == _body(state)
    assert resumed.log == session.log


@pytest.mark.parametrize('willing', [True, False])
def test_roman_default_uses_adjacent_provincia_when_origin_lacks_supply(willing):
    state = _position()
    state['non_player_factions'] = {rc.ROMANS}
    calls = []

    def choose(board, faction, request):
        if request['kind'] == 'agreement':
            calls.append((faction, request['request_type'], request['context']['region']))
            return willing if request['request_type'] == 'quarters' else False
        return None

    state['decision_agent'] = choose
    result = quarters_phase(state)
    moves = [(rc.LEGION, rc.ARVERNI_REGION, rc.PROVINCIA, 1)] if willing else []
    assert result['roman_relocation'] == moves
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == int(willing)
    assert state['resources'][rc.ROMANS] == (10 if willing else 8)
    assert calls.count((rc.AEDUI, 'quarters', rc.PROVINCIA)) == 1
    _assert_integrity(state)


def test_arriving_cohort_needs_supply_for_second_move_to_provincia():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=11)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA, piece_state=rc.SCOUTED)
    place_piece(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND, 4)
    calls = []

    def choose(board, faction, request):
        calls.append((faction, request['request_type'], request['context']['region']))
        return request['request_type'] == 'quarters'

    state['decision_agent'] = choose
    moves = [(rc.AUXILIA, rc.MANDUBII, rc.SEQUANI, 1, rc.SCOUTED),
             (rc.AUXILIA, rc.SEQUANI, rc.PROVINCIA, 1, rc.SCOUTED)]
    before = _body(state)
    assert validate_quarters_plan(state, {rc.ROMANS: moves}) == []
    assert validate_quarters_plan(state, {rc.ROMANS: [moves[0], (*moves[1], ADJACENT_STEP)]})
    with pytest.raises(QuartersError, match='no agreed Supply Line'):
        apply_relocations(state, rc.ROMANS, moves)
    assert calls == [(rc.AEDUI, 'quarters', rc.SEQUANI),
                     (rc.AEDUI, 'supply_line', rc.SEQUANI)]
    assert _body(state) == before
    _assert_integrity(state)


def test_pax_first_winter_completes_with_agreed_adjacent_provincia_move():
    state = setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=11)
    place_piece(state, rc.ARVERNI_REGION, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(state, rc.ARVERNI_REGION, rc.GERMANS, rc.WARBAND, 5)
    place_piece(state, rc.PROVINCIA, rc.AEDUI, rc.WARBAND, 4)
    _assert_integrity(state)
    assert not has_supply_line(state, rc.ARVERNI_REGION, agreements=dict.fromkeys(rc.FACTIONS, True))
    calls = []

    def choose(board, faction, request):
        if request['kind'] == 'agreement':
            calls.append((faction, request['request_type'], request['context']['region']))
            return True
        return None

    state['decision_agent'] = choose
    moves = [(rc.LEGION, rc.ARVERNI_REGION, rc.PROVINCIA, 1)]
    result = run_winter_round(state, relocations={rc.ROMANS: moves})
    assert state['winter_count'] == 1
    assert result['phases']['victory']['skipped']
    assert result['phases']['germans']['skipped']
    assert result['phases']['quarters']['roman_relocation'] == moves
    assert count_pieces(state, rc.ARVERNI_REGION, rc.ROMANS, rc.LEGION) == 0
    assert calls == [(rc.AEDUI, 'quarters', rc.PROVINCIA)]
    _assert_integrity(state)
