"""PR-13 mandatory queue choices, real effects, pending replay and forecasts."""
from copy import deepcopy
from io import StringIO

import pytest
from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece, remove_piece
from fs_bot.cards.capabilities import activate_capability, set_capability_owner
from fs_bot.commands.common import free_action_scope
from fs_bot.engine.capability_queue import KIND, choose_window, validate_response
from fs_bot.engine.execute import _execute_battle
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import encode, decode

REGIONS = (rc.NERVII, rc.TREVERI)


def position(card, scenario=rc.SCENARIO_GREAT_REVOLT, *, arrival=False, defender=rc.ROMANS):
    state = build_initial_state(scenario, seed=23)
    state['non_player_factions'] = {rc.BELGAE}
    for region in REGIONS:
        place_piece(state, region, rc.ARVERNI, rc.WARBAND, 6)
        if defender != rc.ROMANS:
            place_piece(state, region, defender, rc.WARBAND, 4)
    place_piece(state, REGIONS[0], rc.ROMANS, rc.AUXILIA, 6)
    if not arrival:
        place_piece(state, REGIONS[1], rc.ROMANS, rc.AUXILIA, 4)
    else:
        place_piece(state, REGIONS[0], rc.ROMANS, rc.LEGION, 2, from_legions_track=True)
        place_piece(state, REGIONS[1], rc.AEDUI, rc.WARBAND, 8)
    activate_capability(state, card, rc.EVENT_UNSHADED if card == 13 else rc.EVENT_SHADED)
    if card == 59: set_capability_owner(state, 59, rc.ARVERNI)
    return state


def run(state, regions=REGIONS, defender=rc.ROMANS):
    decision = {'command': rc.CMD_BATTLE, 'sa': None, 'sa_regions': [],
                'details': {'battle_plan': [{'region': r, 'target': defender} for r in regions]}}
    with free_action_scope(state, rc.ARVERNI):
        return _execute_battle(state, rc.ARVERNI, decision, _skip_absent_targets=True)


def record(monkeypatch):
    combat, prefire = [], []
    monkeypatch.setattr('fs_bot.engine.execute.resolve_battle', lambda board, region, *args, **kwargs:
        combat.append((region, board.get('event_modifiers', {}).get('card59_shaded_region'))) or {})
    monkeypatch.setattr('fs_bot.battle.losses.resolve_losses', lambda board, region, faction, losses, *args, **kwargs:
        prefire.append((region, faction, losses)) or {})
    return combat, prefire


def agent_for(state, action):
    seen = []
    def agent(board, faction, request):
        if request['kind'] == KIND:
            assert faction == request['owner']
            seen.append(deepcopy(request))
            return action(request)
    state['decision_agent'] = agent
    return seen


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
@pytest.mark.parametrize('card', [13, 59])
def test_owner_reserves_then_uses_final_candidate_once(card, scenario, monkeypatch):
    state = position(card, scenario)
    seen = agent_for(state, lambda r: {'action': 'reserve' if r['region'] == REGIONS[0] else 'activate'})
    combat, prefire = record(monkeypatch)
    result = run(state)
    assert result['executed'] and not result['errors']
    assert [r['region'] for r in seen] == list(REGIONS)
    assert seen[0]['potential_regions'] == [REGIONS[1]]
    assert seen[0]['actions'] == ['activate', 'reserve']
    assert seen[1]['potential_regions'] == [] and seen[1]['actions'] == ['activate']
    assert seen[0]['card_id'] == card
    assert seen[0]['owner'] == (rc.ROMANS if card == 13 else rc.ARVERNI)
    assert prefire == ([(REGIONS[1], rc.ARVERNI, 2)] if card == 13 else [])
    assert combat == [(r, REGIONS[1] if card == 59 and r == REGIONS[1] else None) for r in REGIONS]
    assert 'card59_shaded_region' not in state.get('event_modifiers', {})
    assert validate_state(state) == []


@pytest.mark.parametrize('card', [13, 59])
def test_activation_stops_requests_for_command(card, monkeypatch):
    state = position(card)
    seen = agent_for(state, lambda r: {'action': 'activate'})
    combat, prefire = record(monkeypatch)
    run(state)
    assert len(seen) == 1
    assert prefire == ([(REGIONS[0], rc.ARVERNI, 3)] if card == 13 else [])
    assert combat == [(r, REGIONS[0] if card == 59 else None) for r in REGIONS]


@pytest.mark.parametrize('card', [13, 59])
def test_reservation_expires_when_later_candidate_never_becomes_battle(card, monkeypatch):
    state = position(card, arrival=True)
    seen = agent_for(state, lambda r: {'action': 'reserve'})
    combat, prefire = record(monkeypatch)
    result = run(state)
    assert result['count'] == 1 and len(seen) == 1
    assert combat == [(REGIONS[0], None)] and prefire == []


@pytest.mark.parametrize('card', [13, 59])
def test_absent_first_candidate_gets_no_window_final_actual_candidate_must_use(card, monkeypatch):
    state = position(card, arrival=True)
    seen = agent_for(state, lambda r: {'action': 'activate'})
    record(monkeypatch)
    assert run(state, tuple(reversed(REGIONS)))['count'] == 1
    assert len(seen) == 1 and seen[0]['region'] == REGIONS[0]
    assert seen[0]['actions'] == ['activate']


@pytest.mark.parametrize('card', [13, 59])
def test_retreat_arrivals_offer_new_live_window(card, monkeypatch):
    from fs_bot.battle.resolve import resolve_battle
    state = position(card, arrival=True)
    seen, combat = [], []
    def agent(board, faction, request):
        kind = request['kind']
        if kind == KIND:
            seen.append(deepcopy(request))
            return {'action': 'reserve' if request['region'] == REGIONS[0] else 'activate'}
        if kind == 'agreement' and request['request_type'] == 'retreat_into_control': return True
        if kind == 'retreat':
            return {'retreat': request['region'] == REGIONS[0],
                    'region': REGIONS[1] if request['region'] == REGIONS[0] else None}
    def battle(board, region, *args, **kwargs):
        combat.append((region, count_pieces(board, region, rc.ARVERNI, rc.WARBAND),
                       board.get('event_modifiers', {}).get('card59_shaded_region')))
        return resolve_battle(board, region, *args, **kwargs)
    state['decision_agent'] = agent
    monkeypatch.setattr('fs_bot.engine.execute.resolve_battle', battle)
    result = run(state)
    assert result['count'] == 2 and not result['errors']
    assert [r['region'] for r in seen] == list(REGIONS)
    assert seen[1]['auxilia'] == 5
    assert combat[0] == (REGIONS[0], 6, None)
    assert combat[1] == (REGIONS[1], 4 if card == 13 else 6, REGIONS[1] if card == 59 else None)
    assert validate_state(state) == []


def test_slingers_third_party_zero_auxilia_selection_consumes_use(monkeypatch):
    state = position(13, defender=rc.AEDUI)
    remove_piece(state, REGIONS[0], rc.ROMANS, rc.AUXILIA, 6)
    seen = agent_for(state, lambda r: {'action': 'activate'})
    _, prefire = record(monkeypatch)
    run(state, defender=rc.AEDUI)
    assert len(seen) == 1 and seen[0]['auxilia'] == 0 and prefire == []


@pytest.mark.parametrize('card', [13, 59])
@pytest.mark.parametrize('response', [None, {'use_default': True}])
def test_delegation_uses_first_applicable_battle(card, response, monkeypatch):
    state = position(card, defender=rc.AEDUI)
    if card == 13: remove_piece(state, REGIONS[0], rc.ROMANS, rc.AUXILIA, 6)
    else: place_piece(state, REGIONS[0], rc.AEDUI, rc.CITADEL)
    agent_for(state, lambda r: response)
    combat, prefire = record(monkeypatch)
    run(state, defender=rc.AEDUI)
    assert prefire == ([(REGIONS[1], rc.ARVERNI, 2)] if card == 13 else [])
    assert combat[-1] == (REGIONS[1], REGIONS[1] if card == 59 else None)


def offered(state, card, potential=()):
    seen = agent_for(state, lambda r: None)
    choose_window(state, card, rc.ROMANS if card == 13 else rc.ARVERNI,
                  REGIONS[0], rc.ARVERNI, rc.ROMANS, potential, applicable=True)
    state.pop('decision_agent')
    return seen[0]


@pytest.mark.parametrize('card', [13, 59])
@pytest.mark.parametrize('bad', [None, {}, {'action': 'reserve'}, {'action': 'decline'},
    {'action': []}, {'use_default': 1}, {'action': 'activate', 'extra': True}])
def test_mandatory_final_window_rejects_missing_decline_and_reservation(card, bad):
    state = position(card)
    request = offered(state, card)
    before = encode(state)
    with pytest.raises(ValueError): validate_response(state, request, bad)
    assert encode(state) == before


@pytest.mark.parametrize('card', [13, 59])
def test_terminal_inspection_and_reservation(card):
    from fs_bot.cli.reactive import make_cli_reactive
    state = position(card)
    request = offered(state, card, [REGIONS[1]])
    output = StringIO()
    before = encode(state)
    response = make_cli_reactive({request['owner']}, StringIO('board\n2\n'), output)(
        state, request['owner'], request)
    assert response == {'action': 'reserve'} and 'one may not occur' in output.getvalue()
    assert encode(state) == before


def session_for(state, card, meta=None, log=None):
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.tools.seat_session import SeatSession
    session = SeatSession(state, meta or {'seat': rc.ROMANS if card == 13 else rc.ARVERNI},
                          log if log is not None else [], HumanTurnDisplay(StringIO()))
    state['decision_agent'] = lambda board, faction, request: (
        session.reactive(board, faction, request) if request['kind'] == KIND else None)
    return session


def attempt(session):
    from fs_bot.engine.game_engine import _action_transaction
    def driver(*args): pass
    driver.transaction_checkpoint, driver.transaction_restore = session.checkpoint, session.restore
    with _action_transaction(session.state, driver): return run(session.state)


@pytest.mark.parametrize('card', [13, 59])
def test_reserved_window_invalid_final_response_save_load_and_replay(card, tmp_path, monkeypatch):
    from fs_bot.tools.seat_session import DecisionPending, board_copy
    from fs_bot.state.serialize import save_game, load_game
    state = position(card)
    origin = decode(encode(state))
    session = session_for(state, card)
    record(monkeypatch)
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending): attempt(session)
    first = deepcopy(session.data['pending'])
    session.import_inbox({'decision_id': first['id'], 'response': {'action': 'reserve'}})
    with pytest.raises(DecisionPending): attempt(session)
    second = deepcopy(session.data['pending'])
    assert first['id'] != second['id'] and len(session.data['journal']) == 1
    for bad in (None, {'action': 'decline'}, {'action': 'reserve'}):
        session.import_inbox({'decision_id': second['id'], 'response': bad})
        with pytest.raises(DecisionPending): attempt(session)
        assert session.data['pending'] == second and session.error
        assert encode(board_copy(state)) == before
    path = tmp_path / 'mandatory.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session_for(restored, card, meta, log)
    with pytest.raises(DecisionPending): attempt(resumed)
    assert resumed.data['pending'] == second
    resumed.import_inbox({'decision_id': second['id'], 'response': {'action': 'activate'}})
    result = attempt(resumed)
    resumed.finish()
    agent_for(origin, lambda r: {'action': 'reserve' if r['region'] == REGIONS[0] else 'activate'})
    assert run(origin) == result and len(log) == 2
    assert encode(board_copy(origin)) == encode(board_copy(restored))
    assert validate_state(restored) == []


@pytest.mark.parametrize('card', [13, 59])
@pytest.mark.parametrize('npc', [False, True])
def test_pr11_forecast_branches_mandatory_human_actions_without_live_input(card, npc, monkeypatch):
    from fs_bot.cards import base_arduenna_np as policy
    from fs_bot.engine.agent import consult_agent
    state = position(card)
    # Arduenna always forecasts its attacker as NPC; use another human owner
    # to check the shared queue-response adapter independently of that seat.
    owner = rc.ROMANS if card == 13 else rc.AEDUI
    if npc: state['non_player_factions'].add(owner)
    state['decision_agent'] = lambda *args: pytest.fail('Forecast used live input')
    before = encode({k: v for k, v in state.items() if k != 'decision_agent'})
    def controlled(board, *args, **kwargs):
        choice = choose_window(board, card, owner, REGIONS[0], rc.ARVERNI, rc.ROMANS,
                               [REGIONS[1]], applicable=True)
        if choice == 'reserve':
            assert choose_window(board, card, owner, REGIONS[1], rc.ARVERNI, rc.ROMANS,
                                 [], applicable=True) == 'activate'
        if choice == 'activate':
            consult_agent(board, rc.ROMANS, {'kind': 'loss_order', 'region': REGIONS[0],
                          'num_losses': 1, 'pieces': [(rc.LEGION, None)]})
        return {'executed': True, 'errors': []}
    monkeypatch.setattr('fs_bot.engine.execute._execute_battle', controlled)
    outcomes = list(policy._outcomes(state, REGIONS))
    assert {score for score, _, _ in outcomes} == ({1} if npc else {0, 1})
    assert policy.predicted_legion_losses(state, REGIONS) == (1 if npc else 0)
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before


@pytest.mark.parametrize('card', [13, 59])
def test_stale_battle_is_rejected(card):
    state = position(card)
    request = offered(state, card)
    remove_piece(state, REGIONS[0], rc.ROMANS, rc.AUXILIA, 6)
    with pytest.raises(ValueError): validate_response(state, request, {'action': 'activate'})


@pytest.mark.parametrize('selected', REGIONS)
def test_shaded_owner_may_select_blocked_region_without_bypassing_protection(selected, monkeypatch):
    state = position(59)
    place_piece(state, REGIONS[0], rc.ROMANS, rc.FORT)
    seen = agent_for(state, lambda r: {'action': 'activate' if r['region'] == selected else 'reserve'})
    combat, _ = record(monkeypatch)
    run(state)
    assert seen[0]['blocked'] is True
    assert [r['region'] for r in seen] == list(REGIONS[:1] if selected == REGIONS[0] else REGIONS)
    assert combat[-1][1] == selected
    from fs_bot.engine.horse_choice import attack_blocked
    assert attack_blocked(state, REGIONS[0], rc.ARVERNI, rc.ROMANS)


def test_shaded_defensive_owner_gets_own_window(monkeypatch):
    state = position(59, defender=rc.AEDUI)
    set_capability_owner(state, 59, rc.AEDUI)
    seen = agent_for(state, lambda r: {'action': 'reserve' if r['region'] == REGIONS[0] else 'activate'})
    record(monkeypatch)
    run(state, defender=rc.AEDUI)
    assert [r['owner'] for r in seen] == [rc.AEDUI, rc.AEDUI]


def test_independent_slingers_and_shaded_horse_uses(monkeypatch):
    state = position(59)
    activate_capability(state, 13, rc.EVENT_UNSHADED)
    seen = agent_for(state, lambda r: {'action': 'activate' if r['card_id'] == 13 or r['region'] == REGIONS[1] else 'reserve'})
    combat, prefire = record(monkeypatch)
    run(state)
    assert [(r['card_id'], r['region']) for r in seen] == [(13, REGIONS[0]), (59, REGIONS[0]), (59, REGIONS[1])]
    assert prefire == [(REGIONS[0], rc.ARVERNI, 3)]
    assert combat == [(REGIONS[0], None), (REGIONS[1], REGIONS[1])]


def test_default_reserves_past_abatis(monkeypatch):
    state = position(59)
    state.setdefault('markers', {}).setdefault(REGIONS[0], {})[rc.MARKER_ABATIS] = rc.ROMANS
    combat, _ = record(monkeypatch)
    run(state)
    assert combat == [(REGIONS[0], None), (REGIONS[1], REGIONS[1])]


def test_exception_clears_current_horse_and_restores_outer_selection(monkeypatch):
    state = position(59)
    state.setdefault('event_modifiers', {})['card59_shaded_region'] = rc.MANDUBII
    agent_for(state, lambda r: {'action': 'activate'})
    def interrupted(*args, **kwargs): raise RuntimeError('interrupted')
    monkeypatch.setattr('fs_bot.engine.execute.resolve_battle', interrupted)
    with pytest.raises(RuntimeError, match='interrupted'): run(state)
    assert state['event_modifiers']['card59_shaded_region'] == rc.MANDUBII
