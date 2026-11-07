"""A2.1 Aedui Citadel selection precedes exact force reduction."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board import pieces
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cli.display import HumanTurnDisplay, format_board
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.game_engine import _action_transaction, resolve_winter_card
from fs_bot.engine.interlude import _adjust_aedui_forces
from fs_bot.engine.interlude_choices import (
    AEDUI_CITADEL, aedui_citadel_request, choose_aedui_citadel,
)
from fs_bot.engine.interlude_reductions import AEDUI_HALF, KIND, reduction_request
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy, validate_response

AEDUI = rc.AEDUI
OTHER_SEATS = {rc.ROMANS, rc.BELGAE, rc.GERMANS}


def _place_citadel(state, region, tribe):
    assert _ally_tribe(state, tribe, AEDUI)
    pieces.remove_piece(state, region, AEDUI, rc.ALLY)
    pieces.place_piece(state, region, AEDUI, rc.CITADEL)


def _position():
    state = build_initial_state(rc.SCENARIO_GALLIC_WAR, seed=41)
    state['non_player_factions'] = set(OTHER_SEATS)
    _place_citadel(state, rc.MANDUBII, rc.TRIBE_MANDUBII)
    _place_citadel(state, rc.CARNUTES, rc.TRIBE_CARNUTES)
    for tribe in (rc.TRIBE_AEDUI, rc.TRIBE_SENONES, rc.TRIBE_HELVETII):
        assert _ally_tribe(state, tribe, AEDUI)
    for region, visibility, count in ((rc.CARNUTES, rc.SCOUTED, 3),
                                      (rc.CARNUTES, rc.HIDDEN, 1),
                                      (rc.SEQUANI, rc.REVEALED, 1),
                                      (rc.AEDUI_REGION, rc.HIDDEN, 2)):
        pieces.place_piece(state, region, AEDUI, rc.WARBAND, count, piece_state=visibility)
    pieces.place_piece(state, rc.AEDUI_REGION, AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    return state


def _cohort(request, count, **identity):
    row = next(row for row in request['cohorts']
               if all(row[key] == value for key, value in identity.items()))
    return dict(row, count=count)


def test_aedui_choose_citadel_then_exact_allies_and_visibility_on_new_board():
    state = _position()
    requests = []
    rng = state['rng'].getstate()

    def agent(board, faction, request):
        requests.append((faction, request['kind']))
        if request['kind'] == AEDUI_CITADEL:
            assert pieces.find_leader(board, AEDUI) is None
            assert set(request['regions']) == {rc.MANDUBII, rc.CARNUTES}
            assert request['ally_available'] is True
            return {'region': rc.MANDUBII}
        assert request['stage'] == AEDUI_HALF
        assert request['minimums'] == {rc.ALLY: 2, rc.WARBAND: 4}
        assert all(row['tribe'] != rc.TRIBE_CARNUTES for row in request['cohorts'])
        return {'removals': [
            _cohort(request, 1, tribe=rc.TRIBE_MANDUBII),
            _cohort(request, 1, tribe=rc.TRIBE_HELVETII),
            _cohort(request, 3, region=rc.CARNUTES, piece_state=rc.SCOUTED),
            _cohort(request, 1, region=rc.SEQUANI, piece_state=rc.REVEALED),
        ]}

    state['decision_agent'] = agent
    result = _adjust_aedui_forces(state)
    assert requests == [(AEDUI, AEDUI_CITADEL), (AEDUI, KIND)]
    assert result == {'diviciacus_removed': True, 'citadel_replaced_region': rc.MANDUBII,
                      'citadel_removed_region': None, 'allies_to_available': 2,
                      'warbands_to_available': 4, 'bibracte_replaced': False}
    assert state['tribes'][rc.TRIBE_MANDUBII]['allied_faction'] is None
    assert state['tribes'][rc.TRIBE_SENONES]['allied_faction'] == AEDUI
    assert pieces.count_pieces(state, rc.CARNUTES, AEDUI, rc.CITADEL) == 1
    assert pieces.count_pieces_by_state(state, rc.CARNUTES, AEDUI, rc.WARBAND, rc.HIDDEN) == 1
    assert pieces.count_pieces_by_state(state, rc.CARNUTES, AEDUI, rc.WARBAND, rc.SCOUTED) == 0
    assert pieces.count_pieces(state, rc.AEDUI_REGION, AEDUI, rc.WARBAND) == 2
    assert state['rng'].getstate() == rng and validate_state(state) == []


def test_citadel_choice_without_available_ally_removes_only_named_city():
    state = _position()
    for tribe in (rc.TRIBE_NERVII, rc.TRIBE_TREVERI, rc.TRIBE_PICTONES):
        assert _ally_tribe(state, tribe, AEDUI)
    assert not pieces.get_available(state, AEDUI, rc.ALLY)
    seen = []

    def agent(board, faction, request):
        if request['kind'] == AEDUI_CITADEL:
            assert request['ally_available'] is False
            return {'region': rc.MANDUBII}
        seen.append({row['tribe'] for row in request['cohorts']})
        return None

    state['decision_agent'] = agent
    result = _adjust_aedui_forces(state)
    assert result['citadel_removed_region'] == rc.MANDUBII
    assert result['citadel_replaced_region'] is None
    assert rc.TRIBE_MANDUBII not in seen[0] and rc.TRIBE_SENONES in seen[0]
    assert state['tribes'][rc.TRIBE_MANDUBII]['allied_faction'] is None
    assert pieces.count_pieces(state, rc.CARNUTES, AEDUI, rc.CITADEL) == 1
    assert validate_state(state) == []


@pytest.mark.parametrize('outside', [False, True])
def test_citadel_target_takes_bibracte_last_and_forced_choice_is_automatic(outside):
    state = build_initial_state(rc.SCENARIO_GALLIC_WAR, seed=41)
    _place_citadel(state, rc.AEDUI_REGION, rc.TRIBE_AEDUI)
    if outside:
        _place_citadel(state, rc.CARNUTES, rc.TRIBE_CARNUTES)
    state['decision_agent'] = lambda *args: pytest.fail('Only one legal Citadel')
    target = rc.CARNUTES if outside else rc.AEDUI_REGION
    request = aedui_citadel_request(state)
    assert request['regions'] == [target] and choose_aedui_citadel(state) == target
    if outside:
        with pytest.raises(ValueError, match='offered Regions'):
            validate_response(state, request, {'region': rc.AEDUI_REGION})


def test_aedui_home_last_is_validated_for_each_piece_type():
    state = _position()
    request = reduction_request(state, AEDUI_HALF)
    for home_piece in (_cohort(request, 1, tribe=rc.TRIBE_AEDUI),
                       _cohort(request, 2, region=rc.AEDUI_REGION, piece_type=rc.WARBAND)):
        with pytest.raises(ValueError, match='Home Regions last'):
            validate_response(state, request, {'removals': [home_piece]})


def test_bibracte_is_restored_when_only_a_colony_ally_survives_in_its_region():
    state = build_initial_state(rc.SCENARIO_GALLIC_WAR, seed=41)
    colony = 'Colony at Bibracte'
    state['tribes'][colony] = {'region': rc.AEDUI_REGION, 'status': None, 'allied_faction': None}
    state['markers'].setdefault(rc.AEDUI_REGION, {})[rc.MARKER_COLONY] = True
    for tribe in (colony, rc.TRIBE_CARNUTES, rc.TRIBE_HELVETII):
        assert _ally_tribe(state, tribe, AEDUI)
    result = _adjust_aedui_forces(state)
    assert result['allies_to_available'] == 2 and result['bibracte_replaced']
    assert state['tribes'][colony]['allied_faction'] is None
    assert state['tribes'][rc.TRIBE_AEDUI]['allied_faction'] == AEDUI
    assert state['markers'][rc.AEDUI_REGION][rc.MARKER_COLONY]
    assert validate_state(state) == []


def test_aedui_citadel_cli_allows_board_inspection_and_delegation():
    state = _position()
    request = aedui_citadel_request(state)
    output = StringIO()
    before = encode(state)
    agent = make_cli_reactive({AEDUI}, StringIO(f'board\n{rc.MANDUBII}\n'), output)
    assert agent(state, AEDUI, request) == {'region': rc.MANDUBII}
    assert format_board(state) in output.getvalue() and encode(state) == before
    agent = make_cli_reactive({AEDUI}, StringIO('Use bot selection\n'), output)
    assert agent(state, AEDUI, request) == {'use_default': True}


def _winter_position():
    state = setup_scenario(rc.SCENARIO_GALLIC_WAR, seed=41)
    state['non_player_factions'] = set(OTHER_SEATS)
    state['winter_count'] = 2
    state['current_card'] = rc.WINTER_CARD
    _place_citadel(state, rc.MANDUBII, rc.TRIBE_MANDUBII)
    _place_citadel(state, rc.CARNUTES, rc.TRIBE_CARNUTES)
    return state


def _session(state, meta=None, log=None):
    session = SeatSession(state, {'seat': AEDUI} if meta is None else meta,
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


def test_full_winter_keeps_citadel_choice_when_paused_for_aedui_reduction(tmp_path):
    session = _session(_winter_position())
    before = encode(board_copy(session.state))
    with pytest.raises(DecisionPending):
        _attempt(session)
    first = deepcopy(session.data['pending'])
    request = decode(first['request'])
    assert request['kind'] == AEDUI_CITADEL and request['faction'] == AEDUI
    session.import_inbox({'decision_id': first['id'], 'response': {'region': rc.AEDUI_REGION}})
    with pytest.raises(DecisionPending):
        _attempt(session)
    assert session.error and session.data['pending'] == first
    assert encode(board_copy(session.state)) == before and not session.data['journal']

    downgrade = {'region': rc.MANDUBII}
    session.import_inbox({'decision_id': first['id'], 'response': downgrade})
    with pytest.raises(DecisionPending):
        _attempt(session)
    second = deepcopy(session.data['pending'])
    request = decode(second['request'])
    assert request['stage'] == AEDUI_HALF and request['faction'] == AEDUI
    assert second['id'] != first['id']
    assert len(session.data['journal']) == 1 and encode(board_copy(session.state)) == before
    plan = {'removals': [
        _cohort(request, 1, tribe=rc.TRIBE_MANDUBII),
        _cohort(request, 1, tribe=rc.TRIBE_TREVERI),
        _cohort(request, 1, region=rc.SEQUANI, piece_type=rc.WARBAND),
        _cohort(request, 1, region=rc.AEDUI_REGION, piece_type=rc.WARBAND),
    ]}

    path = tmp_path / 'aedui-winter.json'
    save_game(session.state, path, meta=session.meta, log=session.log)
    state, meta, log = load_game(path, validate=True)
    resumed = _session(state, meta, log)
    resumed.import_inbox({'decision_id': second['id'], 'response': plan})
    result = _attempt(resumed)
    resumed.finish()
    assert len(log) == 2 and state['interlude_completed'] and validate_state(state) == []
    assert result['winter_result']['interlude']['step2_aedui']['citadel_replaced_region'] == rc.MANDUBII

    replay = _winter_position()
    plans = {AEDUI_CITADEL: downgrade, KIND: plan}
    replay['decision_agent'] = lambda board, faction, request: (
        plans.get(request['kind']) if faction == AEDUI else None)
    assert resolve_winter_card(replay) == result
    assert encode(board_copy(replay)) == encode(board_copy(state))
