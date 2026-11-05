"""A2.1 gives Romans the expedition force and one preserved Spring marker."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece, remove_piece, PieceError
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.game_engine import _action_transaction, resolve_winter_card
from fs_bot.engine.interlude import _step3_britannia, _step5_spring, run_interlude
from fs_bot.engine.interlude_choices import expedition_request, marker_request, validate_response
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy

EXPEDITION = 'interlude_expedition'
MARKER = 'interlude_marker'


def position():
    state = build_initial_state(rc.SCENARIO_GALLIC_WAR, seed=41)
    state['non_player_factions'] = {rc.AEDUI, rc.BELGAE, rc.GERMANS}
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION, 4, from_legions_track=True)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.LEGION, 4, from_legions_track=True)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 3, piece_state=rc.REVEALED)
    state['tribes'][rc.TRIBE_VENETI]['status'] = rc.MARKER_DISPERSED
    state['tribes'][rc.TRIBE_MORINI]['status'] = rc.MARKER_DISPERSED_GATHERING
    return state


def allocation():
    return {'conduct': True, 'harvest': {rc.PROVINCIA: 2, rc.MORINI: 1},
            'legions': {rc.PROVINCIA: 1, rc.MORINI: 3},
            'auxilia': [{'region': rc.MORINI, 'piece_state': rc.REVEALED, 'count': 2}]}


def test_exact_expedition_origins_and_above_minimum_quantities():
    state = position()
    before_rng = state['rng'].getstate()
    before_track = deepcopy(state['legions_track'])
    seen = []

    def agent(board, faction, request):
        assert faction == rc.ROMANS
        seen.append(deepcopy(request))
        return allocation()

    state['decision_agent'] = agent
    result = _step3_britannia(state, None)
    assert len(seen) == 1 and seen[0]['kind'] == EXPEDITION
    assert result['decision_source'] == 'player_dict' and result['conducted']
    assert result['legions_to_harvest_box'] == state['winter_track_legions'] == 3
    assert result['legions_to_britannia'] == count_pieces(state, rc.BRITANNIA, rc.ROMANS, rc.LEGION) == 4
    assert result['auxilia_to_britannia'] == 2
    assert count_pieces_by_state(state, rc.BRITANNIA, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 2
    assert count_pieces_by_state(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 2
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == 1
    assert count_pieces(state, rc.MORINI, rc.ROMANS, rc.LEGION) == 0
    assert state['legions_track'] == before_track and state['fallen_legions'] == 0
    assert state['rng'].getstate() == before_rng
    assert validate_state(state) == []


@pytest.mark.parametrize('visibility', [rc.HIDDEN, rc.REVEALED, rc.SCOUTED])
def test_selects_each_auxilia_visibility_without_substitution(visibility):
    state = position()
    if visibility != rc.REVEALED:
        place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 2, piece_state=visibility)
    plan = allocation()
    plan['auxilia'][0]['piece_state'] = visibility
    _step3_britannia(state, plan)
    assert count_pieces_by_state(state, rc.BRITANNIA, rc.ROMANS, rc.AUXILIA, visibility) == 2
    assert validate_state(state) == []


BAD_PLANS = [
    None, {}, {'conduct': True}, {'conduct': 1}, {'conduct': 0}, {'conduct': False, 'legions': {}},
    {'use_default': 1}, {'conduct': True, 'legions_from': {rc.MORINI: 3}},
]
for field, value in [
    ('harvest', {rc.PROVINCIA: 2}), ('harvest', {rc.PROVINCIA: 4}),
    ('harvest', {rc.PROVINCIA: True, rc.MORINI: 2}),
    ('harvest', {rc.BRITANNIA: 3}), ('harvest', {rc.PROVINCIA: 3.0}),
    ('legions', {rc.MORINI: 2}), ('legions', {rc.PROVINCIA: 4}), ('legions', []),
    ('auxilia', []), ('auxilia', [{'region': rc.MORINI, 'piece_state': rc.HIDDEN, 'count': 1}]),
    ('auxilia', [{'region': rc.MORINI, 'piece_state': rc.REVEALED, 'count': True}]),
    ('auxilia', [{'region': rc.MORINI, 'piece_state': rc.REVEALED, 'count': 4}]),
    ('auxilia', [{'region': rc.MORINI, 'piece_state': rc.REVEALED, 'count': 2}] * 2),
    ('auxilia', [{'region': [], 'piece_state': rc.REVEALED, 'count': 1}]),
]:
    plan = allocation()
    plan[field] = value
    BAD_PLANS.append(plan)


@pytest.mark.parametrize('response', BAD_PLANS)
def test_invalid_durable_expedition_contract(response):
    from fs_bot.tools.seat_session import validate_response as validate_durable
    state = position()
    request = dict(expedition_request(state), faction=rc.ROMANS)
    before = encode(state)
    with pytest.raises(ValueError):
        validate_durable(state, request, response)
    assert encode(state) == before


def test_explicit_default_and_raw_bool_preserve_existing_minimums():
    for decision in (None, True, {'conduct': True}, {'use_default': True}):
        state = position()
        result = _step3_britannia(state, decision)
        assert result['conducted'] and result['legions_to_britannia'] == 3
        assert result['auxilia_to_britannia'] == 1
        assert state['winter_track_legions'] == 3 and validate_state(state) == []


def test_unable_still_declines_without_fabricating_forces():
    state = position()
    remove_piece(state, rc.MORINI, rc.ROMANS, rc.LEGION, 4, to_track=True)
    before = count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION)
    result = _step3_britannia(state, True)
    assert not result['conducted'] and result['decision_source'] == 'player_unable'
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == before
    assert result['belgic_in_britannia'] and result['senate_shift'] == 'up'
    assert validate_state(state) == []


def test_human_decline_is_roman_owned_and_uses_printed_alternative():
    state = position()
    seen = []
    state['decision_agent'] = lambda board, faction, request: seen.append(faction) or {'conduct': False}
    result = _step3_britannia(state, None)
    assert seen == [rc.ROMANS] and not result['conducted']
    assert count_pieces(state, rc.BRITANNIA, rc.BELGAE, rc.ALLY) == 1
    assert count_pieces(state, rc.BRITANNIA, rc.BELGAE, rc.WARBAND) == 2
    assert state.get('winter_track_legions', 0) == 0


@pytest.mark.parametrize('tribe,status,counter', [
    (rc.TRIBE_VENETI, rc.MARKER_DISPERSED, 'dispersed_flipped'),
    (rc.TRIBE_MORINI, rc.MARKER_DISPERSED_GATHERING, 'dispersed_gathering_removed'),
])
def test_roman_marker_choice_preserves_either_face_and_correct_spring_counts(tribe, status, counter):
    state = position()
    seen = []

    def agent(board, faction, request):
        if request['kind'] == MARKER:
            seen.append((faction, request))
            return {'tribe': tribe}
        return None

    state['decision_agent'] = agent
    result = _step5_spring(state)
    assert len(seen) == 1 and seen[0][0] == rc.ROMANS
    assert result['roman_dispersed_kept'] == tribe and state['tribes'][tribe]['status'] == status
    assert result['spring_phase'][counter] == 0
    assert validate_state(state) == []


@pytest.mark.parametrize('response', [None, {}, {'tribe': rc.TRIBE_NORI}, {'tribe': []},
                                     {'tribe': rc.TRIBE_VENETI, 'extra': True}, {'use_default': 1}])
def test_invalid_marker_response_cannot_become_default(response):
    from fs_bot.tools.seat_session import validate_response as validate_durable
    state = position()
    with pytest.raises(ValueError):
        validate_durable(state, dict(marker_request(state), faction=rc.ROMANS), response)


def test_declining_marker_preservation_cycles_both_faces():
    state = position()
    state['decision_agent'] = lambda board, faction, request: {'tribe': None} if request['kind'] == MARKER else None
    result = _step5_spring(state)
    assert result['roman_dispersed_kept'] is None
    assert state['tribes'][rc.TRIBE_VENETI]['status'] == rc.MARKER_DISPERSED_GATHERING
    assert state['tribes'][rc.TRIBE_MORINI]['status'] is None


def test_stale_force_and_stale_marker_requests_are_rejected():
    state = position()
    request = expedition_request(state)
    remove_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 1, piece_state=rc.REVEALED)
    with pytest.raises(ValueError):
        validate_response(state, request, allocation())
    request = marker_request(state)
    state['tribes'][rc.TRIBE_VENETI]['status'] = rc.MARKER_DISPERSED_GATHERING
    with pytest.raises(ValueError):
        validate_response(state, request, {'tribe': rc.TRIBE_VENETI})


@pytest.mark.parametrize('decision', [True, False])
def test_npc_never_calls_the_human_and_replays_deterministically(decision):
    state = position()
    state['non_player_factions'].add(rc.ROMANS)
    if not decision:
        remove_piece(state, rc.MORINI, rc.ROMANS, rc.LEGION, 4, to_track=True)
    replay = deepcopy(state)
    calls = []
    state['decision_agent'] = lambda *args: calls.append(args)
    result = _step3_britannia(state, None)
    assert result == _step3_britannia(replay, None) and not calls
    assert encode(board_copy(state)) == encode(replay)
    assert result['conducted'] is decision


def test_cli_allocates_extra_forces_with_board_inspection_and_no_mutation():
    state = position()
    request = expedition_request(state)
    before = encode(state)
    output = StringIO()
    # Reserve 3 from Provincia, send all 4 Morini Legions and 2 Revealed Auxilia.
    response = make_cli_reactive({rc.ROMANS}, StringIO('board\ny\n2\n3\n1\n4\n1\n1\n2\n1\n'), output)(
        state, rc.ROMANS, request)
    assert response['harvest'] == {rc.PROVINCIA: 3}
    assert response['legions'] == {rc.MORINI: 4}
    assert response['auxilia'] == [{'region': rc.MORINI, 'piece_state': rc.REVEALED, 'count': 2}]
    assert encode(state) == before and 'Britannia' in output.getvalue()


def test_cli_marker_choice_and_other_seat_isolation():
    state = position()
    request = marker_request(state)
    index = next(i for i, row in enumerate(request['markers'], 2) if row['tribe'] == rc.TRIBE_VENETI)
    output = StringIO()
    agent = make_cli_reactive({rc.ROMANS}, StringIO(f'board\n{index}\n'), output)
    assert agent(state, rc.ROMANS, request) == {'tribe': rc.TRIBE_VENETI}
    assert agent(state, rc.AEDUI, request) is None


def full_position():
    state = setup_scenario(rc.SCENARIO_GALLIC_WAR, seed=41)
    state['non_player_factions'] = {rc.AEDUI, rc.BELGAE, rc.GERMANS}
    state['winter_count'] = 2
    state['current_card'] = rc.WINTER_CARD
    state['tribes'][rc.TRIBE_VENETI]['status'] = rc.MARKER_DISPERSED
    return state


def session_for(state, meta=None, log=None):
    session = SeatSession(state, meta if meta is not None else {'seat': rc.ROMANS},
                          log if log is not None else [], HumanTurnDisplay(StringIO()))
    state['decision_agent'] = lambda board, faction, request: (
        session.reactive(board, faction, request) if request['kind'] in (EXPEDITION, MARKER) else None)
    return session


def attempt(session):
    def driver(*args):
        pass
    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    with _action_transaction(session.state, driver):
        return resolve_winter_card(session.state)


@pytest.mark.parametrize('bad', [None, {}, {'conduct': True}, {'conduct': 1}])
def test_missing_or_invalid_expedition_stays_pending_and_rolls_back_full_winter(bad):
    session = session_for(full_position())
    before = encode(board_copy(session.state))
    with pytest.raises(DecisionPending):
        attempt(session)
    pending = deepcopy(session.data['pending'])
    assert decode(pending['request'])['kind'] == EXPEDITION
    session.import_inbox({'decision_id': pending['id'], 'response': bad})
    with pytest.raises(DecisionPending):
        attempt(session)
    assert session.data['pending'] == pending and session.error
    assert encode(board_copy(session.state)) == before and not session.data['journal']


@pytest.mark.parametrize('conduct', [False, True])
def test_later_marker_pause_saves_accepted_expedition_and_replays_exactly_once(tmp_path, conduct):
    from fs_bot.engine.interlude_choices import default_expedition
    session = session_for(full_position())
    before = encode(board_copy(session.state))
    with pytest.raises(DecisionPending):
        attempt(session)
    first = deepcopy(session.data['pending'])
    request = decode(first['request'])
    plan = default_expedition(request) if conduct else {'conduct': False}
    session.import_inbox({'decision_id': first['id'], 'response': plan})
    with pytest.raises(DecisionPending):
        attempt(session)
    second = deepcopy(session.data['pending'])
    assert decode(second['request'])['kind'] == MARKER and second['id'] != first['id']
    assert len(session.data['journal']) == 1 and encode(board_copy(session.state)) == before
    session.import_inbox({'decision_id': second['id'], 'response': {'tribe': rc.TRIBE_NORI}})
    with pytest.raises(DecisionPending):
        attempt(session)
    assert session.error and session.data['pending'] == second
    path = tmp_path / 'interlude.json'
    save_game(session.state, path, meta=session.meta, log=session.log)
    state, meta, log = load_game(path, validate=True)
    resumed = session_for(state, meta, log)
    with pytest.raises(DecisionPending):
        attempt(resumed)
    assert resumed.data['pending'] == second and len(resumed.data['journal']) == 1
    response = {'tribe': rc.TRIBE_VENETI}
    resumed.import_inbox({'decision_id': second['id'], 'response': response})
    result = attempt(resumed)
    resumed.finish()
    assert len(log) == 2 and state['interlude_completed']
    assert state.get('winter_track_legions', 0) == (3 if conduct else 0)
    assert state['tribes'][rc.TRIBE_VENETI]['status'] == rc.MARKER_DISPERSED
    assert validate_state(state) == []
    replay = full_position()
    replay['decision_agent'] = lambda board, faction, request: (
        plan if request['kind'] == EXPEDITION else response if request['kind'] == MARKER else None)
    assert resolve_winter_card(replay) == result
    assert encode(board_copy(replay)) == encode(board_copy(state))


def test_invalid_raw_preserved_tribe_restores_all_interlude_changes_and_rng():
    state = full_position()
    before = encode(state)
    with pytest.raises(ValueError):
        run_interlude(state, britannia_decision=True, roman_dispersed_keep=rc.TRIBE_NORI)
    assert encode(state) == before


def test_winter_transfer_primitive_counts_once_and_rejects_conflicting_destinations():
    state = position()
    before = encode(state)
    with pytest.raises(PieceError):
        remove_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION, to_winter_track=True, to_fallen=True)
    assert encode(state) == before
    with pytest.raises(PieceError):
        remove_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, to_winter_track=True)
    assert encode(state) == before
    remove_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION, 3, to_winter_track=True)
    assert state['winter_track_legions'] == 3 and state['fallen_legions'] == 0
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == 1
    assert validate_state(state) == []


@pytest.mark.parametrize('pause_at', [EXPEDITION, MARKER])
def test_direct_winter_api_retries_without_incrementing_counter_twice(pause_at):
    state = full_position()
    before = encode(state)

    def agent(board, faction, request):
        if request['kind'] == pause_at:
            raise EOFError('Pause Interlude')
        return {'use_default': True}

    state['decision_agent'] = agent
    with pytest.raises(EOFError):
        resolve_winter_card(state)
    assert encode(board_copy(state)) == before
    state['decision_agent'] = lambda *args: {'use_default': True}
    result = resolve_winter_card(state)
    assert result['winter_result']['winter_count'] == 3
    assert state['winter_count'] == 3 and state['interlude_completed']
    assert state['winter_track_legions'] == 3 and validate_state(state) == []
