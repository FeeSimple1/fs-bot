"""A2.1 routes the Arverni adjustment through the German seat before handover."""
from copy import deepcopy
from io import StringIO
from random import Random

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board import pieces
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cli.display import HumanTurnDisplay, format_board
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.game_engine import _action_transaction, resolve_winter_card
from fs_bot.engine.interlude import _adjust_arverni_forces
from fs_bot.engine.interlude_choices import (
    ARVERNI_CITADELS, arverni_citadel_request, choose_arverni_citadels,
)
from fs_bot.engine.interlude_reductions import ARVERNI_HALF, PERMANENT, QUARTER, reduction_request
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state
from fs_bot.tools.player_fuzz import make_random_reactive
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy, validate_response

ARVERNI = rc.ARVERNI
GERMANS = rc.GERMANS
OTHER_SEATS = {rc.ROMANS, rc.BELGAE, rc.AEDUI}
HOME = rc.ARVERNI_REGION


def _state():
    state = build_initial_state(rc.SCENARIO_GALLIC_WAR, seed=41)
    state['non_player_factions'] = set(OTHER_SEATS)
    return state


def _validate_mid_interlude(state):
    # The new Leader is staged before the scenario gains its second-half cap.
    assert state['spring_box_leaders'] == [rc.VERCINGETORIX]
    assert validate_state(dict(state, spring_box_leaders=[])) == []


def _place_citadel(state, region, tribe):
    assert _ally_tribe(state, tribe, ARVERNI)
    pieces.remove_piece(state, region, ARVERNI, rc.ALLY)
    pieces.place_piece(state, region, ARVERNI, rc.CITADEL)


def _cohort(request, count, **identity):
    row = next(row for row in request['cohorts']
               if all(row[key] == value for key, value in identity.items()))
    return dict(row, count=count)


def _scarce_position():
    state = _state()
    _place_citadel(state, rc.MANDUBII, rc.TRIBE_MANDUBII)
    _place_citadel(state, rc.CARNUTES, rc.TRIBE_CARNUTES)
    _place_citadel(state, HOME, rc.TRIBE_ARVERNI)
    for tribe in (rc.TRIBE_MORINI, rc.TRIBE_MENAPII, rc.TRIBE_NERVII, rc.TRIBE_EBURONES,
                  rc.TRIBE_ATREBATES, rc.TRIBE_BELLOVACI, rc.TRIBE_HELVETII,
                  rc.TRIBE_CADURCI, rc.TRIBE_VOLCAE):
        assert _ally_tribe(state, tribe, ARVERNI)
    return state


def test_german_seat_orders_scarce_arverni_replacements_and_reductions():
    state = _scarce_position()
    seen = []

    def agent(board, faction, request):
        seen.append((faction, request['kind']))
        if request['kind'] == ARVERNI_CITADELS:
            assert request['available_allies'] == 1
            assert request['count'] == 2 and set(request['regions']) == {rc.CARNUTES, rc.MANDUBII}
            assert rc.VERCINGETORIX in board['spring_box_leaders']
            return {'regions': [rc.CARNUTES, rc.MANDUBII]}
        assert request['stage'] == ARVERNI_HALF and request['minimums'][rc.ALLY] == 5
        assert all(row['tribe'] not in (rc.TRIBE_ARVERNI, rc.TRIBE_MANDUBII)
                   for row in request['cohorts'])
        targets = (rc.TRIBE_CADURCI, rc.TRIBE_VOLCAE, rc.TRIBE_CARNUTES,
                   rc.TRIBE_MORINI, rc.TRIBE_EBURONES)
        return {'removals': [_cohort(request, 1, tribe=tribe) for tribe in targets]}

    state['decision_agent'] = agent
    result = _adjust_arverni_forces(state)
    assert seen == [(GERMANS, ARVERNI_CITADELS), (GERMANS, 'interlude_reduction')]
    assert result['citadels_replaced'] == [rc.CARNUTES] and result['citadels_removed'] == [rc.MANDUBII]
    assert result['allies_to_available'] == 5 and not result['gergovia_replaced']
    assert state['tribes'][rc.TRIBE_MANDUBII]['allied_faction'] is None
    assert state['tribes'][rc.TRIBE_MENAPII]['allied_faction'] == ARVERNI
    assert pieces.count_pieces(state, HOME, ARVERNI, rc.CITADEL) == 1
    _validate_mid_interlude(state)


@pytest.mark.parametrize('plan', [
    {'regions': [rc.CARNUTES, HOME]},
    {'regions': [rc.CARNUTES, rc.CARNUTES]},
    {'regions': [rc.CARNUTES]},
    {'regions': [rc.CARNUTES, []]},
])
def test_arverni_citadel_rejects_illegal_sets(plan):
    state = _scarce_position()
    request = arverni_citadel_request(state)
    before = encode(state)
    with pytest.raises(ValueError, match='distinct Arverni Citadels'):
        validate_response(state, dict(request, faction=GERMANS), plan)
    assert encode(state) == before


def test_gergovia_citadel_only_comes_after_remaining_outside_city():
    state = _state()
    _place_citadel(state, HOME, rc.TRIBE_ARVERNI)
    _place_citadel(state, rc.CARNUTES, rc.TRIBE_CARNUTES)
    state['decision_agent'] = lambda *args: pytest.fail('Only one legal order')
    request = arverni_citadel_request(state)
    assert choose_arverni_citadels(state) == [rc.CARNUTES, HOME]
    with pytest.raises(ValueError, match='Gergovia last'):
        validate_response(state, request, {'regions': [HOME, rc.CARNUTES]})


def _early_position():
    state = _state()
    for tribe in (rc.TRIBE_ARVERNI, rc.TRIBE_CADURCI, rc.TRIBE_VOLCAE, rc.TRIBE_PICTONES):
        assert _ally_tribe(state, tribe, ARVERNI)
    pieces.place_piece(state, HOME, ARVERNI, rc.WARBAND, 4, piece_state=rc.SCOUTED)
    pieces.place_piece(state, rc.PICTONES, ARVERNI, rc.WARBAND, 5, piece_state=rc.REVEALED)
    return state


def test_early_ally_exception_excludes_gergovia_and_arverni_region_warbands():
    state = _early_position()
    request = reduction_request(state, ARVERNI_HALF)
    early = [_cohort(request, 1, tribe=tribe) for tribe in (rc.TRIBE_CADURCI, rc.TRIBE_VOLCAE)]
    outside = _cohort(request, 5, region=rc.PICTONES, piece_state=rc.REVEALED)
    gergovia = _cohort(request, 1, tribe=rc.TRIBE_ARVERNI)
    home_warband = _cohort(request, 1, region=HOME, piece_state=rc.SCOUTED)
    plan = {'removals': [*early, outside]}
    assert validate_response(state, dict(request, faction=GERMANS), plan) == plan
    with pytest.raises(ValueError, match='has changed'):
        validate_response(state, dict(request, faction=ARVERNI), plan)
    for early_home in (gergovia, home_warband):
        with pytest.raises(ValueError, match='Home Regions last'):
            validate_response(state, request, {'removals': [*early, early_home, outside]})


def test_np_arverni_removes_the_exact_early_allies_and_keeps_home_warbands_last():
    state = _early_position()
    state['non_player_factions'].add(GERMANS)
    state['decision_agent'] = lambda *args: pytest.fail('German seat is a bot')
    result = _adjust_arverni_forces(state)
    assert result['allies_to_available'] == 2 and result['warbands_to_available'] == 5
    assert not result['gergovia_replaced'] and not result['warbands_placed_in_arverni']
    for tribe in (rc.TRIBE_CADURCI, rc.TRIBE_VOLCAE):
        assert state['tribes'][tribe]['allied_faction'] is None
    for tribe in (rc.TRIBE_ARVERNI, rc.TRIBE_PICTONES):
        assert state['tribes'][tribe]['allied_faction'] == ARVERNI
    assert pieces.count_pieces_by_state(state, HOME, ARVERNI, rc.WARBAND, rc.SCOUTED) == 4
    _validate_mid_interlude(state)


def test_cadurci_does_not_prevent_gergovia_restoration_and_reinforcement():
    state = _state()
    for tribe in (rc.TRIBE_CADURCI, rc.TRIBE_CARNUTES, rc.TRIBE_PICTONES):
        assert _ally_tribe(state, tribe, ARVERNI)
    pieces.place_piece(state, HOME, rc.ROMANS, rc.AUXILIA, 1)
    state['decision_agent'] = lambda board, faction, request: {'removals': [
        _cohort(request, 1, tribe=rc.TRIBE_CARNUTES),
        _cohort(request, 1, tribe=rc.TRIBE_PICTONES),
    ]}
    result = _adjust_arverni_forces(state)
    assert result['gergovia_replaced'] and result['warbands_placed_in_arverni'] == 3
    assert state['tribes'][rc.TRIBE_CADURCI]['allied_faction'] is None
    assert state['tribes'][rc.TRIBE_ARVERNI]['allied_faction'] == ARVERNI
    assert not pieces.count_pieces(state, HOME, rc.ROMANS, rc.AUXILIA)
    assert pieces.count_pieces_by_state(state, HOME, ARVERNI, rc.WARBAND, rc.HIDDEN) == 3
    _validate_mid_interlude(state)


def test_arverni_citadel_terminal_offers_board_and_scarce_ally_order_to_german():
    state = _scarce_position()
    request = arverni_citadel_request(state)
    before = encode(state)
    output = StringIO()
    answers = StringIO(f'board\ny\n{rc.MANDUBII}\n{rc.CARNUTES}\n')
    agent = make_cli_reactive({GERMANS}, answers, output)
    assert agent(state, ARVERNI, request) is None
    assert agent(state, GERMANS, request) == {'regions': [rc.MANDUBII, rc.CARNUTES]}
    assert format_board(state) in output.getvalue() and encode(state) == before
    assert 'Remove which Arverni Citadel?' in output.getvalue()


def _winter_position():
    state = setup_scenario(rc.SCENARIO_GALLIC_WAR, seed=41)
    state['non_player_factions'] = set(OTHER_SEATS)
    state['winter_count'] = 2
    state['current_card'] = rc.WINTER_CARD
    for region, tribe in ((rc.MANDUBII, rc.TRIBE_MANDUBII), (rc.CARNUTES, rc.TRIBE_CARNUTES),
                          (rc.BITURIGES, rc.TRIBE_BITURIGES)):
        _place_citadel(state, region, tribe)
    return state


def _session(state, meta=None, log=None):
    session = SeatSession(state, {'seat': GERMANS} if meta is None else meta,
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


def test_german_winter_journal_retains_arverni_citadels_until_reduction_and_handover(tmp_path):
    session = _session(_winter_position())
    before = encode(board_copy(session.state))
    for stage in (PERMANENT, QUARTER):
        with pytest.raises(DecisionPending):
            _attempt(session)
        pending = session.data['pending']
        assert decode(pending['request'])['stage'] == stage
        session.import_inbox({'decision_id': pending['id'], 'response': {'use_default': True}})
    with pytest.raises(DecisionPending):
        _attempt(session)
    first = deepcopy(session.data['pending'])
    request = decode(first['request'])
    assert request['kind'] == ARVERNI_CITADELS and request['faction'] == GERMANS
    session.import_inbox({'decision_id': first['id'], 'response': {'regions': [rc.MANDUBII]}})
    with pytest.raises(DecisionPending):
        _attempt(session)
    assert session.error and session.data['pending'] == first
    assert len(session.data['journal']) == 2 and encode(board_copy(session.state)) == before

    downgrade = {'regions': [rc.MANDUBII, rc.BITURIGES]}
    session.import_inbox({'decision_id': first['id'], 'response': downgrade})
    with pytest.raises(DecisionPending):
        _attempt(session)
    second = deepcopy(session.data['pending'])
    request = decode(second['request'])
    assert request['stage'] == ARVERNI_HALF and request['faction'] == GERMANS
    assert second['id'] != first['id']
    assert len(session.data['journal']) == 3 and encode(board_copy(session.state)) == before
    policy = make_random_reactive({GERMANS}, Random(41))
    plan = policy(session.state, GERMANS, request)

    path = tmp_path / 'arverni-winter.json'
    save_game(session.state, path, meta=session.meta, log=session.log)
    state, meta, log = load_game(path, validate=True)
    resumed = _session(state, meta, log)
    resumed.import_inbox({'decision_id': second['id'], 'response': plan})
    result = _attempt(resumed)
    resumed.finish()
    assert len(log) == 4 and state['interlude_completed'] and validate_state(state) == []
    assert state['non_player_factions'] == OTHER_SEATS and not check_structural_integrity(state)
    assert result['winter_result']['interlude']['step2_arverni']['citadels_replaced'] == [
        rc.MANDUBII, rc.BITURIGES]

    replay = _winter_position()
    plans = {ARVERNI_CITADELS: downgrade, ARVERNI_HALF: plan}
    replay['decision_agent'] = lambda board, faction, request: (
        plans.get(request.get('stage', request['kind'])) if faction == GERMANS else None)
    assert resolve_winter_card(replay) == result
    assert encode(board_copy(replay)) == encode(board_copy(state))
