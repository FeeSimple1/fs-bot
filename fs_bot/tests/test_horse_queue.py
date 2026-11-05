"""Optional Horse activation in actual prospective Battles, Card 59 unshaded."""
from copy import deepcopy
from io import StringIO

import pytest
from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces
from fs_bot.cards.capabilities import activate_capability
from fs_bot.commands.common import free_action_scope
from fs_bot.engine.execute import _execute_battle
from fs_bot.engine.horse_queue import KIND, choose_window, validate_response
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import encode, decode

REGIONS = (rc.NERVII, rc.TREVERI)


def position(scenario=rc.SCENARIO_GREAT_REVOLT, *, arrival=False):
    state = build_initial_state(scenario, seed=23)
    state['non_player_factions'] = {rc.ARVERNI, rc.BELGAE}
    for region in REGIONS:
        place_piece(state, region, rc.ARVERNI, rc.WARBAND, 6)
    place_piece(state, REGIONS[0], rc.ROMANS, rc.AUXILIA, 6)
    if arrival:
        place_piece(state, REGIONS[0], rc.ROMANS, rc.LEGION, 2, from_legions_track=True)
        place_piece(state, REGIONS[1], rc.AEDUI, rc.WARBAND, 8)
    else:
        place_piece(state, REGIONS[1], rc.ROMANS, rc.AUXILIA, 4)
    activate_capability(state, 59, rc.EVENT_UNSHADED)
    return state


def action(regions=REGIONS):
    return {'command': rc.CMD_BATTLE, 'sa': None, 'sa_regions': [],
            'details': {'battle_plan': [{'region': r, 'target': rc.ROMANS} for r in regions]}}


def run(state, regions=REGIONS):
    with free_action_scope(state, rc.ARVERNI):
        return _execute_battle(state, rc.ARVERNI, action(regions), _skip_absent_targets=True)


def recorder(monkeypatch):
    rows = []
    def combat(state, region, *args, **kwargs):
        rows.append((region, state.get('event_modifiers', {}).get('card59_unshaded_region')))
        return {}
    monkeypatch.setattr('fs_bot.engine.execute.resolve_battle', combat)
    return rows


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
def test_owner_reserves_then_uses_only_one_later_region(scenario, monkeypatch):
    state = position(scenario)
    seen = []
    def agent(board, faction, request):
        if request['kind'] == KIND:
            assert faction == rc.ROMANS
            seen.append(deepcopy(request))
            return {'action': 'reserve' if request['region'] == REGIONS[0] else 'activate'}
    state['decision_agent'] = agent
    rows = recorder(monkeypatch)
    result = run(state)
    assert result['executed'] and not result['errors']
    assert [r['region'] for r in seen] == list(REGIONS)
    assert seen[0]['potential_regions'] == [REGIONS[1]]
    assert seen[0]['actions'] == ['activate', 'reserve', 'decline']
    assert seen[1]['actions'] == ['activate', 'decline']
    assert rows == [(REGIONS[0], None), (REGIONS[1], REGIONS[1])]
    assert 'card59_unshaded_region' not in state.get('event_modifiers', {})
    assert validate_state(state) == []


@pytest.mark.parametrize('choice', ['activate', 'decline'])
def test_activation_or_whole_command_decline_stops_later_requests(choice, monkeypatch):
    state = position()
    seen = []
    def agent(board, faction, request):
        if request['kind'] == KIND:
            seen.append(request)
            return {'action': choice}
    state['decision_agent'] = agent
    rows = recorder(monkeypatch)
    run(state)
    assert len(seen) == 1
    selected = REGIONS[0] if choice == 'activate' else None
    assert rows == [(r, selected) for r in REGIONS]


@pytest.mark.parametrize('response', [None, {'use_default': True}])
def test_raw_default_still_uses_first_applicable_region(response, monkeypatch):
    state = position()
    state['decision_agent'] = lambda board, faction, request: response if request['kind'] == KIND else None
    rows = recorder(monkeypatch)
    run(state)
    assert rows == [(r, REGIONS[0]) for r in REGIONS]


def test_absent_candidate_is_skipped_without_asking(monkeypatch):
    state = position(arrival=True)
    seen = []
    def agent(board, faction, request):
        if request['kind'] == KIND:
            seen.append(request)
            return {'action': 'decline'}
    state['decision_agent'] = agent
    recorder(monkeypatch)
    run(state, tuple(reversed(REGIONS)))
    assert len(seen) == 1 and seen[0]['region'] == REGIONS[0]
    assert seen[0]['potential_regions'] == []
    assert seen[0]['actions'] == ['activate', 'decline']


def test_reservation_is_unused_if_no_later_actual_battle(monkeypatch):
    state = position(arrival=True)
    seen = []
    def agent(board, faction, request):
        if request['kind'] == KIND:
            seen.append(request)
            return {'action': 'reserve'}
    state['decision_agent'] = agent
    rows = recorder(monkeypatch)
    result = run(state)
    assert result['count'] == 1 and len(seen) == 1
    assert rows == [(REGIONS[0], None)]


def test_retreat_arrivals_create_live_later_horse_window(monkeypatch):
    from fs_bot.battle.resolve import resolve_battle
    state = position(arrival=True)
    assert count_pieces(state, REGIONS[1], rc.ROMANS) == 0
    seen, before_battles = [], []
    def agent(board, faction, request):
        kind = request['kind']
        if kind == KIND:
            seen.append(deepcopy(request))
            return {'action': 'reserve' if request['region'] == REGIONS[0] else 'activate'}
        if kind == 'agreement' and request['request_type'] == 'retreat_into_control':
            return True
        if kind == 'retreat':
            return {'retreat': request['region'] == REGIONS[0],
                    'region': REGIONS[1] if request['region'] == REGIONS[0] else None}
    def combat(board, region, *args, **kwargs):
        before_battles.append((region, count_pieces(board, region, rc.ROMANS, rc.AUXILIA),
                               board.get('event_modifiers', {}).get('card59_unshaded_region')))
        return resolve_battle(board, region, *args, **kwargs)
    state['decision_agent'] = agent
    monkeypatch.setattr('fs_bot.engine.execute.resolve_battle', combat)
    result = run(state)
    assert result['executed'] and result['count'] == 2 and not result['errors']
    assert [r['region'] for r in seen] == list(REGIONS)
    assert seen[1]['auxilia'] == 5
    assert before_battles == [(REGIONS[0], 6, None), (REGIONS[1], 5, REGIONS[1])]
    assert validate_state(state) == []


def offered(state, potential=()):
    seen = []
    state['decision_agent'] = lambda board, faction, request: seen.append(deepcopy(request))
    choose_window(state, REGIONS[0], rc.ARVERNI, rc.ROMANS, potential)
    state.pop('decision_agent')
    return seen[0]


@pytest.mark.parametrize('bad', [None, {}, {'action': 'reserve'}, {'action': 'unknown'},
    {'action': None}, {'action': []}, {'use_default': 1}, {'action': 'activate', 'extra': True}])
def test_invalid_or_impossible_action_does_not_mutate_state(bad):
    state = position()
    request = offered(state)
    before = encode(state)
    with pytest.raises(ValueError): validate_response(state, request, bad)
    assert encode(state) == before


def test_stale_live_battle_response_is_rejected():
    from fs_bot.board.pieces import remove_piece
    state = position()
    request = offered(state, [REGIONS[1]])
    remove_piece(state, REGIONS[0], rc.ROMANS, rc.AUXILIA, 6)
    with pytest.raises(ValueError): validate_response(state, request, {'action': 'activate'})


def test_terminal_inspection_and_reservation():
    from fs_bot.cli.reactive import make_cli_reactive
    state = position()
    request = offered(state, [REGIONS[1]])
    output = StringIO()
    before = encode(state)
    response = make_cli_reactive({rc.ROMANS}, StringIO('board\n2\n'), output)(state, rc.ROMANS, request)
    assert response == {'action': 'reserve'}
    assert 'one may not occur' in output.getvalue()
    assert encode(state) == before


def session_for(state, meta=None, log=None):
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.tools.seat_session import SeatSession
    session = SeatSession(state, meta or {'seat': rc.ROMANS}, log if log is not None else [],
                          HumanTurnDisplay(StringIO()))
    state['decision_agent'] = lambda board, faction, request: (
        session.reactive(board, faction, request) if request['kind'] == KIND else None)
    return session


def attempt(session):
    from fs_bot.engine.game_engine import _action_transaction
    def driver(*args): pass
    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    with _action_transaction(session.state, driver): return run(session.state)


@pytest.mark.parametrize('bad', [None, {}, {'action': 'unknown'}])
def test_invalid_durable_window_stays_pending_after_save_load(tmp_path, bad, monkeypatch):
    from fs_bot.tools.seat_session import DecisionPending, board_copy
    from fs_bot.state.serialize import save_game, load_game
    state = position()
    session = session_for(state)
    recorder(monkeypatch)
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending): attempt(session)
    pending = deepcopy(session.data['pending'])
    session.import_inbox({'decision_id': pending['id'], 'response': bad})
    with pytest.raises(DecisionPending): attempt(session)
    assert session.error and session.data['pending'] == pending
    assert encode(board_copy(state)) == before
    path = tmp_path / 'queue.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session_for(restored, meta, log)
    with pytest.raises(DecisionPending): attempt(resumed)
    assert resumed.data['pending'] == pending
    resumed.import_inbox({'decision_id': pending['id'], 'response': {'action': 'decline'}})
    assert attempt(resumed)['executed']
    resumed.finish()
    assert len(log) == 1 and validate_state(restored) == []


def test_reserved_first_window_survives_second_pending_save_and_replay(tmp_path, monkeypatch):
    from fs_bot.tools.seat_session import DecisionPending, board_copy
    from fs_bot.state.serialize import save_game, load_game
    state = position()
    origin = decode(encode(state))
    session = session_for(state)
    recorder(monkeypatch)
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending): attempt(session)
    first = deepcopy(session.data['pending'])
    session.import_inbox({'decision_id': first['id'], 'response': {'action': 'reserve'}})
    with pytest.raises(DecisionPending): attempt(session)
    second = deepcopy(session.data['pending'])
    assert second['id'] != first['id'] and decode(second['request'])['region'] == REGIONS[1]
    assert len(session.data['journal']) == 1 and encode(board_copy(state)) == before
    path = tmp_path / 'later.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session_for(restored, meta, log)
    with pytest.raises(DecisionPending): attempt(resumed)
    assert resumed.data['pending'] == second
    resumed.import_inbox({'decision_id': second['id'], 'response': {'action': 'activate'}})
    result = attempt(resumed)
    resumed.finish()
    assert len(log) == 2 and 'card59_unshaded_region' not in restored.get('event_modifiers', {})
    origin['decision_agent'] = lambda board, faction, request: (
        {'action': 'reserve' if request['region'] == REGIONS[0] else 'activate'} if request['kind'] == KIND else None)
    assert run(origin) == result
    assert encode(board_copy(origin)) == encode(board_copy(restored))


@pytest.mark.parametrize('npc', [False, True])
def test_pr11_forecast_branches_optional_human_windows_without_live_input(npc, monkeypatch):
    from fs_bot.cards import base_arduenna_np as policy
    from fs_bot.engine.agent import consult_agent
    state = position()
    if npc: state['non_player_factions'].add(rc.ROMANS)
    state['decision_agent'] = lambda *args: pytest.fail('Forecast used live input')
    before = encode({k: v for k, v in state.items() if k != 'decision_agent'})
    def controlled_battles(board, *args, **kwargs):
        choice = choose_window(board, REGIONS[0], rc.ARVERNI, rc.ROMANS, [REGIONS[1]])
        if choice == 'reserve':
            later = choose_window(board, REGIONS[1], rc.ARVERNI, rc.ROMANS, [])
            score = 0 if later == 'activate' else 3
        else: score = 1 if choice == 'activate' else 2
        for _ in range(score):
            consult_agent(board, rc.ROMANS, {'kind': 'loss_order', 'region': REGIONS[0],
                'num_losses': 1, 'pieces': [(rc.LEGION, None)]})
        return {'executed': True, 'errors': []}
    monkeypatch.setattr('fs_bot.engine.execute._execute_battle', controlled_battles)
    outcomes = list(policy._outcomes(state, REGIONS))
    assert {score for score, _, _ in outcomes} == ({1} if npc else {0, 1, 2, 3})
    assert policy.predicted_legion_losses(state, REGIONS) == (1 if npc else 0)
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before
