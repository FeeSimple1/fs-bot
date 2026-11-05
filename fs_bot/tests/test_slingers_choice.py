"""Card 13's Roman Region selection and the printed Card 59 pre-fire Tip."""
from copy import deepcopy
from io import StringIO
import pytest
from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, remove_piece, count_pieces
from fs_bot.cards.capabilities import activate_capability
from fs_bot.engine.execute import _execute_battle, execute_decision
from fs_bot.engine.slingers_choice import KIND, selection_request, validate_response
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import encode, decode

REGIONS = (rc.TREVERI, rc.MANDUBII)


def position(scenario=rc.SCENARIO_GREAT_REVOLT, defender=rc.AEDUI, auxiliaries=(6, 2)):
    state = build_initial_state(scenario, seed=11)
    state['non_player_factions'] = set(rc.FACTIONS) - {rc.ROMANS}
    state['resources'][rc.BELGAE] = 10
    for region, n in zip(REGIONS, auxiliaries):
        place_piece(state, region, rc.BELGAE, rc.WARBAND, 6)
        if n:
            place_piece(state, region, rc.ROMANS, rc.AUXILIA, n)
        if defender != rc.ROMANS:
            place_piece(state, region, defender, rc.WARBAND, 6)
    activate_capability(state, 13, rc.EVENT_UNSHADED)
    return state


def plan(defender=rc.AEDUI, regions=REGIONS, ambush=False):
    return {'command': rc.CMD_BATTLE, 'sa': rc.SA_AMBUSH if ambush else None,
            'sa_regions': list(regions) if ambush else [],
            'details': {'battle_plan': [{'region': r, 'target': defender} for r in regions]}}


def agent_for(state, response, seen=None):
    seen = seen if seen is not None else []
    def agent(board, faction, request):
        if request['kind'] != KIND:
            return None
        assert faction == rc.ROMANS
        assert board['resources'][rc.BELGAE] == 10
        assert all(count_pieces(board, r, rc.BELGAE, rc.WARBAND) == 6 for r in REGIONS)
        seen.append(deepcopy(request))
        return response
    state['decision_agent'] = agent
    return seen


def record_battles(monkeypatch):
    seen = []
    def combat(state, region, attacker, defender, **kwargs):
        seen.append((region, count_pieces(state, region, attacker, rc.WARBAND)))
        return {}
    monkeypatch.setattr('fs_bot.engine.execute.resolve_battle', combat)
    return seen


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
@pytest.mark.parametrize('selected', REGIONS)
def test_roman_chooses_third_party_prefire_region_once(scenario, selected, monkeypatch):
    state = position(scenario)
    seen = agent_for(state, {'region': selected})
    combat = record_battles(monkeypatch)
    result = _execute_battle(state, rc.BELGAE, plan())
    assert result['executed'] and not result['errors']
    assert len(seen) == 1 and seen[0]['legal_regions'] == list(REGIONS)
    assert seen[0]['defenders'] == {r: rc.AEDUI for r in REGIONS}
    assert seen[0]['auxilia'] == dict(zip(REGIONS, (6, 2)))
    assert combat == [(r, 6 - ((3 if r == REGIONS[0] else 1) if r == selected else 0))
                      for r in REGIONS]
    assert count_pieces(state, REGIONS[0], rc.AEDUI, rc.WARBAND) == 6
    assert validate_state(state) == []


@pytest.mark.parametrize('n', [0, 1])
def test_can_choose_legal_region_with_zero_prefire_losses(n, monkeypatch):
    state = position(auxiliaries=(6, n))
    seen = agent_for(state, {'region': REGIONS[1]})
    combat = record_battles(monkeypatch)
    _execute_battle(state, rc.BELGAE, plan())
    assert len(seen) == 1 and seen[0]['auxilia'][REGIONS[1]] == n
    assert combat == [(r, 6) for r in REGIONS]


@pytest.mark.parametrize('defender', [rc.ROMANS, rc.AEDUI])
@pytest.mark.parametrize('ambush', [False, True])
def test_defensive_or_third_party_use_includes_event_ambush(defender, ambush, monkeypatch):
    from fs_bot.engine.free_actions import execute_free_action_plan
    state = position(defender=defender)
    seen = agent_for(state, {'region': REGIONS[1]})
    combat = record_battles(monkeypatch)
    result = execute_free_action_plan(state, rc.BELGAE,
        {'request_type': 'event_command', 'morasses_ambush': True},
        plan(defender=defender, ambush=ambush))
    assert result['executed'] and not result['errors']
    assert len(seen) == 1 and combat == [(REGIONS[0], 6), (REGIONS[1], 5)]
    assert state['resources'][rc.BELGAE] == 10


@pytest.mark.parametrize('shaded', [False, True])
def test_horse_prefire_bonus_only_when_both_capabilities_unshaded(shaded, monkeypatch):
    state = position()
    activate_capability(state, 59, rc.EVENT_SHADED if shaded else rc.EVENT_UNSHADED)
    agent_for(state, {'region': REGIONS[1]})
    combat = record_battles(monkeypatch)
    _execute_battle(state, rc.BELGAE, plan())
    # Horse's existing ordinary-Battle selection goes to Treveri (most Auxilia).
    # The printed 13/59 Tip still grants full pre-fire in chosen Mandubii.
    assert combat == [(REGIONS[0], 6), (REGIONS[1], 5 if shaded else 4)]
    assert 'card59_unshaded_region' not in state.get('event_modifiers', {})


@pytest.mark.parametrize('response', [None, {'use_default': True}])
def test_raw_default_keeps_existing_region_selection(response, monkeypatch):
    state = position()
    agent_for(state, response)
    combat = record_battles(monkeypatch)
    _execute_battle(state, rc.BELGAE, plan())
    assert combat == [(REGIONS[0], 3), (REGIONS[1], 6)]


@pytest.mark.parametrize('bad', [None, {}, {'decline': True}, {'region': rc.PROVINCIA},
    {'region': None}, {'region': []}, {'region': REGIONS[0], 'extra': True},
    {'use_default': 1}, {'use_default': False}])
def test_validator_rejects_invalid_or_missing_choice_without_mutation(bad):
    state = position()
    request = selection_request(state, rc.BELGAE, plan()['details']['battle_plan'])
    before = encode(state)
    with pytest.raises(ValueError):
        validate_response(state, request, bad)
    assert encode(state) == before


@pytest.mark.parametrize('side', [rc.BELGAE, rc.AEDUI])
def test_stale_battle_is_not_a_valid_selection(side):
    state = position()
    request = selection_request(state, rc.BELGAE, plan()['details']['battle_plan'])
    remove_piece(state, REGIONS[0], side, rc.WARBAND, 6)
    with pytest.raises(ValueError):
        validate_response(state, request, {'region': REGIONS[0]})


@pytest.mark.parametrize('mode', ['no_auxilia', 'shaded', 'roman_command'])
def test_no_new_request_when_capability_does_not_apply(mode, monkeypatch):
    state = position(auxiliaries=(0, 0) if mode == 'no_auxilia' else (6, 2))
    seen = agent_for(state, {'region': REGIONS[0]})
    if mode == 'shaded':
        activate_capability(state, 13, rc.EVENT_SHADED)
    record_battles(monkeypatch)
    _execute_battle(state, rc.ROMANS if mode == 'roman_command' else rc.BELGAE, plan())
    assert not seen


def test_terminal_board_inspection_then_second_region():
    from fs_bot.cli.reactive import make_cli_reactive
    state = position()
    request = selection_request(state, rc.BELGAE, plan()['details']['battle_plan'])
    out = StringIO()
    before = encode(state)
    response = make_cli_reactive({rc.ROMANS}, StringIO('board\n2\n'), out)(state, rc.ROMANS, request)
    assert response == {'region': REGIONS[1]}
    assert 'Roman Auxilia' in out.getvalue() and rc.MANDUBII in out.getvalue()
    assert encode(state) == before


def test_ranked_defenders_only_offer_the_actual_first_target():
    state = position()
    rows = [dict(region=r, targets=[rc.AEDUI, rc.ROMANS]) for r in REGIONS]
    request = selection_request(state, rc.BELGAE, rows)
    assert request['defenders'] == {r: rc.AEDUI for r in REGIONS}
    rows += [dict(region=rc.PROVINCIA, target=rc.ROMANS), rows[0]]
    assert selection_request(state, rc.BELGAE, rows) == request


def test_preview_never_consumes_live_roman_input_or_rng():
    from fs_bot.engine.moves import validate_player_action
    state = position()
    state['non_player_factions'].discard(rc.BELGAE)
    state['decision_agent'] = lambda *args: pytest.fail('Preview consumed live input')
    before = encode({k: v for k, v in state.items() if k != 'decision_agent'})
    assert validate_player_action(state, rc.BELGAE, plan())[0]
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before


def session_for(state, meta=None, log=None):
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.tools.seat_session import SeatSession
    session = SeatSession(state, meta or {'seat': rc.ROMANS},
                          log if log is not None else [], HumanTurnDisplay(StringIO()))
    state['decision_agent'] = lambda board, faction, req: (
        session.reactive(board, faction, req)
        if faction == rc.ROMANS and req['kind'] in (KIND, 'loss_order') else None)
    return session


def attempt(session, defender=rc.AEDUI):
    from fs_bot.engine.game_engine import _action_transaction
    def driver(*args): pass
    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    with _action_transaction(session.state, driver):
        return _execute_battle(session.state, rc.BELGAE, plan(defender=defender))


@pytest.mark.parametrize('bad', [None, {}, {'decline': True}, {'region': rc.PROVINCIA}])
def test_invalid_durable_selection_stays_pending_across_save_load(tmp_path, bad):
    from fs_bot.state.serialize import save_game, load_game
    from fs_bot.tools.seat_session import DecisionPending, board_copy
    state = position()
    session = session_for(state)
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending): attempt(session)
    pending = deepcopy(session.data['pending'])
    assert decode(pending['request'])['kind'] == KIND
    assert encode(board_copy(state)) == before
    session.import_inbox({'decision_id': pending['id'], 'response': bad})
    with pytest.raises(DecisionPending): attempt(session)
    assert session.error and session.data['pending'] == pending
    assert encode(board_copy(state)) == before
    path = tmp_path / 'slingers.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session_for(restored, meta, log)
    with pytest.raises(DecisionPending): attempt(resumed)
    assert resumed.data['pending'] == pending
    resumed.import_inbox({'decision_id': pending['id'], 'response': {'region': REGIONS[1]}})
    assert attempt(resumed)['executed']
    resumed.finish()
    assert len(log) == 1 and validate_state(restored) == []


def test_accepted_region_survives_later_roman_casualty_pause_and_replays(tmp_path):
    from fs_bot.state.serialize import save_game, load_game
    from fs_bot.tools.seat_session import DecisionPending, board_copy
    state = position(defender=rc.ROMANS, auxiliaries=(6, 4))
    origin = decode(encode(state))
    session = session_for(state)
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending): attempt(session, rc.ROMANS)
    first = deepcopy(session.data['pending'])
    chosen = {'region': REGIONS[1]}
    session.import_inbox({'decision_id': first['id'], 'response': chosen})
    with pytest.raises(DecisionPending): attempt(session, rc.ROMANS)
    later = deepcopy(session.data['pending'])
    assert decode(later['request'])['kind'] == 'loss_order'
    assert len(session.data['journal']) == 1 and encode(board_copy(state)) == before
    path = tmp_path / 'later.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session_for(restored, meta, log)
    with pytest.raises(DecisionPending): attempt(resumed, rc.ROMANS)
    assert resumed.data['pending'] == later
    for _ in range(40):
        resumed.import_inbox({'decision_id': resumed.data['pending']['id'],
                             'response': {'use_default': True}})
        try:
            result = attempt(resumed, rc.ROMANS)
            resumed.finish()
            break
        except DecisionPending:
            continue
    else: pytest.fail('Battle never completed')
    assert result['executed'] and not result['errors']
    assert restored['resources'][rc.BELGAE] == 8
    assert len(log) > 1
    origin['decision_agent'] = lambda board, faction, req: chosen if req['kind'] == KIND else None
    assert _execute_battle(origin, rc.BELGAE, plan(defender=rc.ROMANS)) == result
    assert encode(board_copy(origin)) == encode(board_copy(restored))


def test_prospective_queue_preserves_existing_automatic_use(monkeypatch):
    state = position()
    seen = agent_for(state, {'region': REGIONS[1]})
    combat = record_battles(monkeypatch)
    _execute_battle(state, rc.BELGAE, plan(), _skip_absent_targets=True)
    assert seen == [] and combat == [(REGIONS[0], 3), (REGIONS[1], 6)]


def test_npc_uses_first_applicable_region_in_command_order(monkeypatch):
    state = position()
    combat = record_battles(monkeypatch)
    _execute_battle(state, rc.BELGAE, plan(regions=tuple(reversed(REGIONS))))
    assert combat == [(REGIONS[1], 5), (REGIONS[0], 6)]
