"""A2.1 German Interlude choices use the owner's exact counters and Tribes."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board import pieces
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cli.display import HumanTurnDisplay, format_board
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.game_engine import _action_transaction, resolve_winter_card
from fs_bot.engine.interlude import _adjust_german_forces, run_interlude
from fs_bot.engine.interlude_choices import SETTLEMENTS, settlement_request
from fs_bot.engine.interlude_reductions import KIND, PERMANENT, QUARTER, reduction_request
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.player_fuzz import make_random_reactive
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy, validate_response

GERMANS = rc.GERMANS


def _position():
    state = build_initial_state(rc.SCENARIO_GALLIC_WAR, seed=41)
    for visibility, count in ((rc.HIDDEN, 4), (rc.REVEALED, 3), (rc.SCOUTED, 2)):
        pieces.place_piece(state, rc.MORINI, GERMANS, rc.WARBAND, count,
                           piece_state=visibility)
    pieces.place_piece(state, rc.SUGAMBRI, GERMANS, rc.WARBAND, 2)
    pieces.place_piece(state, rc.SEQUANI, GERMANS, rc.WARBAND, 2)
    pieces.place_piece(state, rc.SEQUANI, GERMANS, rc.SETTLEMENT)
    for tribe in (rc.TRIBE_MENAPII, rc.TRIBE_MORINI, rc.TRIBE_SUGAMBRI):
        assert _ally_tribe(state, tribe, GERMANS)
    return state


def _select(request, count, **identity):
    row = next(row for row in request['cohorts']
               if all(row[key] == value for key, value in identity.items()))
    return dict(row, count=count)


def test_exact_permanent_and_above_minimum_quarter_reductions():
    state = _position()
    stages = []

    def agent(board, faction, request):
        assert faction == GERMANS and request['kind'] == KIND
        stage = request['stage']
        stages.append(stage)
        if stage == PERMANENT:
            assert not pieces.get_available(board, GERMANS, rc.LEADER)
            return {'removals': [_select(request, 2, piece_state=rc.SCOUTED),
                                 _select(request, 13, region=None)]}
        assert not pieces.count_pieces(board, rc.SEQUANI, GERMANS, rc.SETTLEMENT)
        assert request['minimums'] == {rc.ALLY: 1, rc.WARBAND: 3}
        assert any(row['tribe'] == rc.TRIBE_SEQUANI for row in request['cohorts'])
        return {'removals': [_select(request, 1, tribe=rc.TRIBE_MORINI),
                             _select(request, 3, region=rc.MORINI, piece_state=rc.REVEALED),
                             _select(request, 1, region=rc.MORINI, piece_state=rc.HIDDEN)]}

    before_rng = state['rng'].getstate()
    state['decision_agent'] = agent
    result = _adjust_german_forces(state)
    assert stages == [PERMANENT, QUARTER]
    assert result['warbands_removed_from_play'] == state['removed_pieces'][GERMANS][rc.WARBAND] == 15
    assert result['allies_to_available'] == 1
    assert result['warbands_to_available'] == 4
    assert pieces.get_available(state, GERMANS, rc.WARBAND) == 8
    assert pieces.count_pieces_by_state(state, rc.MORINI, GERMANS, rc.WARBAND, rc.HIDDEN) == 3
    for visibility in (rc.SCOUTED, rc.REVEALED):
        assert not pieces.count_pieces_by_state(state, rc.MORINI, GERMANS, rc.WARBAND, visibility)
    assert state['tribes'][rc.TRIBE_MORINI]['allied_faction'] is None
    assert state['tribes'][rc.TRIBE_MENAPII]['allied_faction'] == GERMANS
    assert state['rng'].getstate() == before_rng
    assert validate_state(state) == []


@pytest.mark.parametrize('count', [14, 16, True, 15.0])
def test_permanent_requires_exact_positive_integer_quantity(count):
    state = _position()
    request = reduction_request(state, PERMANENT)
    with pytest.raises(ValueError):
        validate_response(state, dict(request, faction=GERMANS),
                          {'removals': [_select(request, count, region=None)]})


def test_quarter_germania_last_per_piece_type_and_repeated_cohort_capacity():
    state = _position()
    request = reduction_request(state, QUARTER)
    menapii = _select(request, 1, tribe=rc.TRIBE_MENAPII)
    morini = _select(request, 1, tribe=rc.TRIBE_MORINI)
    home_ally = _select(request, 1, tribe=rc.TRIBE_SUGAMBRI)
    home_warband = _select(request, 1, region=rc.SUGAMBRI, piece_type=rc.WARBAND)
    warbands = _select(request, 4, region=rc.MORINI, piece_state=rc.HIDDEN)
    for bad in ([menapii, warbands, home_ally], [menapii, warbands, home_warband],
                [menapii, dict(warbands, count=3)], [warbands],
                [menapii, warbands, dict(warbands, count=1)], [menapii, menapii, warbands]):
        with pytest.raises(ValueError):
            validate_response(state, request, {'removals': bad})
    plan = {'removals': [menapii, morini, home_ally, warbands]}
    assert validate_response(state, request, plan) == plan
    pieces.remove_piece(state, rc.MORINI, GERMANS, rc.WARBAND, 1, piece_state=rc.HIDDEN)
    with pytest.raises(ValueError, match='changed'):
        validate_response(state, request, plan)


@pytest.mark.parametrize('npc', [False, True])
def test_explicit_default_and_npc_keep_seeded_default_state(npc):
    state = _position()
    expected = deepcopy(state)
    seen = []
    state['decision_agent'] = lambda _, faction, request: (
        seen.append((faction, request['stage'])) or {'use_default': True})
    if npc:
        state['non_player_factions'] = expected['non_player_factions'] = {GERMANS}
    assert _adjust_german_forces(state) == _adjust_german_forces(expected)
    assert encode(board_copy(state)) == encode(expected)
    assert seen == ([] if npc else [(GERMANS, PERMANENT), (GERMANS, QUARTER)])


def test_cli_exact_plan_and_board_inspection():
    state = _position()
    request = reduction_request(state, QUARTER)
    before = encode(state)
    output = StringIO()
    # Germania choices are locked. Choose Menapii and four Hidden Morini Warbands.
    agent = make_cli_reactive({GERMANS}, StringIO('board\ny\n1\n2\n4\n1\n'), output)
    assert agent(state, GERMANS, request) == {'removals': [
        _select(request, 1, tribe=rc.TRIBE_MENAPII),
        _select(request, 4, region=rc.MORINI, piece_state=rc.HIDDEN),
    ]}
    assert 'Finish selection' in output.getvalue() and 'Available' in output.getvalue()
    assert encode(state) == before
    assert agent(state, rc.AEDUI, request) is None


def _winter_position():
    state = setup_scenario(rc.SCENARIO_GALLIC_WAR, seed=41)
    state['non_player_factions'] = {rc.ROMANS, rc.AEDUI, rc.BELGAE}
    state['winter_count'] = 2
    state['current_card'] = rc.WINTER_CARD
    return state


def _session(state, meta=None, log=None):
    session = SeatSession(state, {'seat': GERMANS} if meta is None else meta,
                          [] if log is None else log, HumanTurnDisplay(StringIO()))
    state['decision_agent'] = lambda board, faction, request: (
        session.reactive(board, faction, request)
        if request['kind'] == SETTLEMENTS or request.get('stage') in (PERMANENT, QUARTER)
        else None)
    return session


def _attempt(session):
    def driver(*args):
        pass

    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    with _action_transaction(session.state, driver):
        return resolve_winter_card(session.state)


def test_full_winter_saves_at_quarter_stage_and_replays_exactly_once(tmp_path):
    from random import Random

    session = _session(_winter_position())
    before = encode(board_copy(session.state))
    with pytest.raises(DecisionPending):
        _attempt(session)
    first = deepcopy(session.data['pending'])
    permanent = decode(first['request'])
    assert permanent['stage'] == PERMANENT and permanent['faction'] == GERMANS
    policy = make_random_reactive({GERMANS}, Random(41))
    plans = {PERMANENT: policy(session.state, GERMANS, permanent)}
    assert any(row['region'] in rc.GERMANIA_REGIONS for row in plans[PERMANENT]['removals'])
    session.import_inbox({'decision_id': first['id'], 'response': plans[PERMANENT]})
    with pytest.raises(DecisionPending):
        _attempt(session)
    second = deepcopy(session.data['pending'])
    quarter = decode(second['request'])
    assert quarter['stage'] == QUARTER and second['id'] != first['id']
    assert all(row['region'] is not None for row in quarter['cohorts'])
    assert len(session.data['journal']) == 1 and encode(board_copy(session.state)) == before

    session.import_inbox({'decision_id': second['id'], 'response': {'removals': []}})
    with pytest.raises(DecisionPending):
        _attempt(session)
    assert session.error and session.data['pending'] == second
    assert encode(board_copy(session.state)) == before
    path = tmp_path / 'german-interlude.json'
    save_game(session.state, path, meta=session.meta, log=session.log)
    state, meta, log = load_game(path, validate=True)
    resumed = _session(state, meta, log)
    plans[QUARTER] = policy(state, GERMANS, quarter)
    resumed.import_inbox({'decision_id': second['id'], 'response': plans[QUARTER]})
    result = _attempt(resumed)
    resumed.finish()

    assert len(log) == 2 and state['interlude_completed'] and state['winter_count'] == 3
    assert validate_state(state) == []
    replay = _winter_position()
    replay['decision_agent'] = lambda board, faction, request: plans.get(request.get('stage'))
    assert resolve_winter_card(replay) == result
    assert encode(board_copy(replay)) == encode(board_copy(state))


def test_invalid_raw_reduction_restores_entire_interlude():
    state = _winter_position()
    before = encode(state)
    state['decision_agent'] = lambda board, faction, request: (
        {'removals': []} if request.get('stage') == QUARTER else None)
    with pytest.raises(ValueError):
        run_interlude(state)
    assert encode(board_copy(state)) == before


def _settlement_position():
    state = build_initial_state(rc.SCENARIO_GALLIC_WAR, seed=41)
    for region in (rc.MANDUBII, rc.ARVERNI_REGION, rc.AEDUI_REGION, rc.NERVII):
        pieces.place_piece(state, region, GERMANS, rc.SETTLEMENT)
    pieces.place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 2)
    for tribe in (rc.TRIBE_MORINI, rc.TRIBE_MENAPII, rc.TRIBE_SUGAMBRI,
                  rc.TRIBE_SUEBI_NORTH, rc.TRIBE_SUEBI_SOUTH):
        assert _ally_tribe(state, tribe, GERMANS)
    state['tribes'][rc.TRIBE_VOLCAE]['status'] = rc.MARKER_DISPERSED
    state['tribes'][rc.TRIBE_SENONES]['status'] = rc.MARKER_DISPERSED_GATHERING
    return state


def test_scarce_settlement_ally_chooses_exact_region_and_tribe_before_quarter():
    state = _settlement_position()
    seen = []

    def agent(board, faction, request):
        seen.append((faction, request['kind'], request.get('stage')))
        if request['kind'] == SETTLEMENTS:
            assert board['removed_pieces'][GERMANS][rc.WARBAND] == 15
            assert request['options'] == {
                rc.MANDUBII: [rc.TRIBE_MANDUBII, rc.TRIBE_LINGONES],
                rc.ARVERNI_REGION: [rc.TRIBE_CADURCI],
            }
            assert request['required_allies'] == 1
            return {'allies': {rc.MANDUBII: rc.TRIBE_LINGONES}}
        if request.get('stage') == QUARTER:
            assert any(row['tribe'] == rc.TRIBE_LINGONES for row in request['cohorts'])
            assert request['minimums'] == {rc.ALLY: 2, rc.WARBAND: 3}
            return {'removals': [_select(request, 1, tribe=rc.TRIBE_MENAPII),
                                 _select(request, 1, tribe=rc.TRIBE_MORINI),
                                 _select(request, 3, region=rc.AEDUI_REGION)]}
        return None

    state['decision_agent'] = agent
    result = _adjust_german_forces(state)
    assert seen == [(GERMANS, KIND, PERMANENT), (GERMANS, SETTLEMENTS, None),
                    (GERMANS, KIND, QUARTER)]
    assert result['settlements_replaced_with_ally'] == [rc.MANDUBII]
    assert dict(result['settlements_replaced_with_warbands']) == {
        rc.ARVERNI_REGION: 3, rc.AEDUI_REGION: 3, rc.NERVII: 3}
    assert state['tribes'][rc.TRIBE_LINGONES]['allied_faction'] == GERMANS
    for tribe in (rc.TRIBE_MANDUBII, rc.TRIBE_ARVERNI, rc.TRIBE_AEDUI, rc.TRIBE_CADURCI):
        assert state['tribes'][tribe]['allied_faction'] is None
    assert pieces.count_pieces_by_state(state, rc.NERVII, GERMANS, rc.WARBAND, rc.HIDDEN) == 3
    assert result['settlements_removed_from_play'] == state['removed_pieces'][GERMANS][rc.SETTLEMENT] == 6
    assert validate_state(state) == []


@pytest.mark.parametrize('plan', [
    None,
    {'allies': []},
    {'allies': {}},
    {'allies': {rc.MANDUBII: rc.TRIBE_MANDUBII, rc.ARVERNI_REGION: rc.TRIBE_CADURCI}},
    {'allies': {rc.MANDUBII: rc.TRIBE_SENONES}},
    {'allies': {rc.ARVERNI_REGION: rc.TRIBE_ARVERNI}},
    {'allies': {rc.ARVERNI_REGION: rc.TRIBE_VOLCAE}},
    {'allies': {rc.AEDUI_REGION: rc.TRIBE_AEDUI}},
    {'allies': {rc.NERVII: rc.TRIBE_NERVII}},
    {'allies': {rc.ARVERNI_REGION: rc.TRIBE_LINGONES}},
])
def test_settlement_validation_rejects_illegal_or_incomplete_allocation(plan):
    state = _settlement_position()
    request = dict(settlement_request(state), faction=GERMANS)
    before = encode(state)
    with pytest.raises(ValueError, match='Assign exactly 1'):
        validate_response(state, request, plan)
    assert encode(state) == before


def test_settlement_validation_rechecks_live_control_and_ally_capacity():
    state = _settlement_position()
    request = settlement_request(state)
    plan = {'allies': {rc.MANDUBII: rc.TRIBE_LINGONES}}
    assert validate_response(state, request, plan) == plan
    controlled = deepcopy(state)
    pieces.place_piece(controlled, rc.MANDUBII, rc.AEDUI, rc.WARBAND, 1)
    assert rc.MANDUBII not in settlement_request(controlled)['options']
    assert _ally_tribe(state, rc.TRIBE_NERVII, GERMANS)
    for changed in (controlled, state):
        with pytest.raises(ValueError, match='changed'):
            validate_response(changed, request, plan)


def test_settlement_cli_shows_board_and_selects_scarce_ally_placement():
    state = _settlement_position()
    request = settlement_request(state)
    region = list(request['options']).index(rc.MANDUBII) + 1
    tribe = request['options'][rc.MANDUBII].index(rc.TRIBE_LINGONES) + 1
    output = StringIO()
    agent = make_cli_reactive({GERMANS}, StringIO(f'board\ny\n{region}\n{tribe}\n'), output)
    before = encode(state)
    assert agent(state, GERMANS, request) == {'allies': {rc.MANDUBII: rc.TRIBE_LINGONES}}
    assert 'Which Settlement gets an Ally?' in output.getvalue()
    assert rc.TRIBE_LINGONES in output.getvalue() and format_board(state) in output.getvalue()
    assert encode(state) == before


def test_npc_and_explicit_default_use_same_legal_settlement_allocations():
    state = _settlement_position()
    npc = deepcopy(state)
    npc['non_player_factions'] = {GERMANS}
    state['decision_agent'] = lambda *args: {'use_default': True}
    npc['decision_agent'] = lambda *args: pytest.fail('Bot consulted human decision agent')
    player_result = _adjust_german_forces(state)
    assert player_result == _adjust_german_forces(npc)
    assert rc.AEDUI_REGION in dict(player_result['settlements_replaced_with_warbands'])
    assert rc.NERVII in dict(player_result['settlements_replaced_with_warbands'])
    assert state['rng'].getstate() == npc['rng'].getstate()
    assert state['spaces'] == npc['spaces'] and state['tribes'] == npc['tribes']


def test_winter_retains_permanent_and_settlement_answers_through_quarter_resume(tmp_path):
    def position():
        state = _winter_position()
        pieces.place_piece(state, rc.MANDUBII, GERMANS, rc.SETTLEMENT)
        pieces.place_piece(state, rc.MANDUBII, GERMANS, rc.WARBAND, 3)
        return state

    session = _session(position())
    before = encode(board_copy(session.state))
    with pytest.raises(DecisionPending):
        _attempt(session)
    first = deepcopy(session.data['pending'])
    request = decode(first['request'])
    assert request['stage'] == PERMANENT
    permanent = {'removals': [_select(request, 3, region=None),
                              _select(request, 8, region=rc.UBII),
                              _select(request, 4, region=rc.SUGAMBRI)]}
    session.import_inbox({'decision_id': first['id'], 'response': permanent})
    with pytest.raises(DecisionPending):
        _attempt(session)
    second = deepcopy(session.data['pending'])
    request = decode(second['request'])
    assert request['kind'] == SETTLEMENTS and request['faction'] == GERMANS
    assert request['options'] == {rc.MANDUBII: [rc.TRIBE_MANDUBII, rc.TRIBE_SENONES]}
    session.import_inbox({'decision_id': second['id'], 'response': {'allies': {}}})
    with pytest.raises(DecisionPending):
        _attempt(session)
    assert session.error and session.data['pending'] == second
    assert len(session.data['journal']) == 1 and encode(board_copy(session.state)) == before

    conversion = {'allies': {rc.MANDUBII: rc.TRIBE_SENONES}}
    session.import_inbox({'decision_id': second['id'], 'response': conversion})
    with pytest.raises(DecisionPending):
        _attempt(session)
    third = deepcopy(session.data['pending'])
    request = decode(third['request'])
    assert request['stage'] == QUARTER and len({first['id'], second['id'], third['id']}) == 3
    assert any(row['tribe'] == rc.TRIBE_SENONES for row in request['cohorts'])
    assert len(session.data['journal']) == 2 and encode(board_copy(session.state)) == before

    path = tmp_path / 'settlement-winter.json'
    save_game(session.state, path, meta=session.meta, log=session.log)
    state, meta, log = load_game(path, validate=True)
    resumed = _session(state, meta, log)
    resumed.import_inbox({'decision_id': third['id'], 'response': {'use_default': True}})
    result = _attempt(resumed)
    resumed.finish()
    assert len(log) == 3 and state['interlude_completed'] and validate_state(state) == []
    german = result['winter_result']['interlude']['step2_germans']
    assert german['settlements_replaced_with_ally'] == [rc.MANDUBII]
    assert german['settlements_replaced_with_warbands'] == [(rc.SEQUANI, 1)]

    replay = position()
    plans = {PERMANENT: permanent, SETTLEMENTS: conversion}
    replay['decision_agent'] = lambda board, faction, request: plans.get(
        request.get('stage', request['kind']))
    assert resolve_winter_card(replay) == result
    assert encode(board_copy(replay)) == encode(board_copy(state))
