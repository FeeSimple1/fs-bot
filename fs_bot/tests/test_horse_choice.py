"""Card 59 Region selection, Fort/Abatis limits, and Command-local flags."""
from copy import deepcopy
from io import StringIO

import pytest
from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, remove_piece, count_pieces
from fs_bot.cards.capabilities import activate_capability, set_capability_owner
from fs_bot.engine.execute import _execute_battle
from fs_bot.engine.horse_choice import KIND, FLAGS, selection_request, validate_response
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import encode, decode

REGIONS = (rc.TREVERI, rc.MANDUBII)


def position(side=rc.EVENT_UNSHADED, role='attack', scenario=rc.SCENARIO_GREAT_REVOLT):
    state = build_initial_state(scenario, seed=23)
    owner = rc.ROMANS if side == rc.EVENT_UNSHADED else rc.BELGAE
    enemy = rc.BELGAE if owner == rc.ROMANS else rc.ROMANS
    attacker, defender = (owner, enemy) if role == 'attack' else (enemy, owner)
    state['non_player_factions'] = set(rc.FACTIONS) - {owner}
    state['resources'][attacker] = 10
    for i, region in enumerate(REGIONS):
        place_piece(state, region, rc.ROMANS, rc.AUXILIA, 6 if i == 0 else 4)
        place_piece(state, region, rc.BELGAE, rc.WARBAND, 8 if i == 0 else 6)
    activate_capability(state, 59, side)
    if side == rc.EVENT_SHADED:
        set_capability_owner(state, 59, owner)
    action = {'command': rc.CMD_BATTLE, 'sa': None, 'sa_regions': [],
              'details': {'battle_plan': [{'region': r, 'target': defender} for r in REGIONS]}}
    return state, owner, attacker, defender, action


def request_for(state, attacker, action, side):
    return selection_request(state, attacker, action['details']['battle_plan'], side)


def agent_for(state, response, seen=None):
    seen = seen if seen is not None else []
    def agent(board, faction, request):
        if request['kind'] == KIND:
            assert faction == request['owner']
            seen.append(deepcopy(request))
            return response
    state['decision_agent'] = agent
    return seen


def record_combat(monkeypatch):
    from fs_bot.battle.resolve import _calculate_attack_losses
    from fs_bot.battle.losses import calculate_losses
    seen = []
    def combat(state, region, attacker, defender, **kwargs):
        attack = _calculate_attack_losses(state, region, attacker, defender,
            is_retreat=False, had_citadel_at_start=kwargs['citadel_at_start'],
            had_fort_at_start=kwargs['fort_at_start'])
        assert attack == calculate_losses(state, region, attacker, defender)
        counter = calculate_losses(state, region, defender, attacker, is_counterattack=True)
        seen.append((region, attack, counter, state.get('event_modifiers', {}).get(FLAGS[0]),
                     state.get('event_modifiers', {}).get(FLAGS[1])))
        return {}
    monkeypatch.setattr('fs_bot.engine.execute.resolve_battle', combat)
    return seen


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
@pytest.mark.parametrize('role', ['attack', 'defense'])
@pytest.mark.parametrize('side', [rc.EVENT_UNSHADED, rc.EVENT_SHADED])
def test_owner_selects_a_region_for_attack_or_counterattack(side, role, scenario, monkeypatch):
    state, owner, attacker, defender, action = position(side, role, scenario)
    seen = agent_for(state, {'region': REGIONS[1]})
    combat = record_combat(monkeypatch)
    result = _execute_battle(state, attacker, action)
    assert result['executed'] and not result['errors']
    assert len(seen) == 1 and seen[0]['owner'] == owner
    assert seen[0]['legal_regions'] == list(REGIONS)
    assert seen[0]['may_decline'] == (side == rc.EVENT_UNSHADED)
    for region, attack, counter, uflag, sflag in combat:
        chosen = region == REGIONS[1]
        assert (uflag == REGIONS[1]) == (side == rc.EVENT_UNSHADED)
        assert (sflag == REGIONS[1]) == (side == rc.EVENT_SHADED)
        romans = 6 if region == REGIONS[0] else 4
        belgae = 8 if region == REGIONS[0] else 6
        normal_owner = romans // 2 if owner == rc.ROMANS else belgae // 2
        boosted_owner = romans if owner == rc.ROMANS else belgae
        assert (attack if role == 'attack' else counter) == (boosted_owner if chosen else normal_owner)
    assert all(key not in state.get('event_modifiers', {}) for key in FLAGS)
    assert validate_state(state) == []


@pytest.mark.parametrize('role', ['attack', 'defense'])
def test_romans_can_decline_horse(role, monkeypatch):
    state, _, attacker, _, action = position(role=role)
    seen = agent_for(state, {'decline': True})
    combat = record_combat(monkeypatch)
    _execute_battle(state, attacker, action)
    assert len(seen) == 1
    assert all(row[3] is None for row in combat)
    assert all((row[1] if role == 'attack' else row[2]) == n
               for row, n in zip(combat, (3, 2)))


@pytest.mark.parametrize('side,role', [(rc.EVENT_UNSHADED, 'attack'),
    (rc.EVENT_SHADED, 'attack'), (rc.EVENT_SHADED, 'defense')])
def test_default_uses_first_applicable_battle_not_old_priorities(side, role, monkeypatch):
    state, _, attacker, _, action = position(side, role)
    if role == 'defense' or side == rc.EVENT_UNSHADED:
        action['details']['battle_plan'].reverse()
    expected = action['details']['battle_plan'][0]['region']
    combat = record_combat(monkeypatch)
    _execute_battle(state, attacker, action)
    flag_index = 3 if side == rc.EVENT_UNSHADED else 4
    assert all(row[flag_index] == expected for row in combat)


@pytest.mark.parametrize('guard', [rc.FORT, rc.CITADEL])
def test_attacking_shaded_owner_cannot_double_against_defending_guard(guard, monkeypatch):
    state, _, attacker, defender, action = position(rc.EVENT_SHADED)
    # A physical Citadel belongs to a Gallic defender, so use the Aedui here.
    if guard == rc.CITADEL:
        for row in action['details']['battle_plan']:
            row['target'] = rc.AEDUI
        for region in REGIONS:
            place_piece(state, region, rc.AEDUI, rc.WARBAND, 6)
        defender = rc.AEDUI
    place_piece(state, REGIONS[0], defender, guard)
    seen = agent_for(state, {'region': REGIONS[0]})
    combat = record_combat(monkeypatch)
    _execute_battle(state, attacker, action)
    assert seen[0]['blocked'] == {REGIONS[0]: True, REGIONS[1]: False}
    assert combat[0][1] == 2  # 8 Warbands * 1/2, then guard's halving.
    assert combat[1][1] == 3


def test_defending_shaded_owner_citadel_blocks_counterattack_doubling(monkeypatch):
    state, owner, attacker, _, action = position(rc.EVENT_SHADED, 'defense')
    place_piece(state, REGIONS[0], owner, rc.CITADEL)
    seen = agent_for(state, {'region': REGIONS[0]})
    combat = record_combat(monkeypatch)
    _execute_battle(state, attacker, action)
    assert seen[0]['blocked'][REGIONS[0]]
    assert combat[0][2] == 4


def test_abatis_as_a_fort_blocks_shaded_attack_in_both_loss_calculators(monkeypatch):
    state, _, attacker, _, action = position(rc.EVENT_SHADED, scenario=rc.SCENARIO_ARIOVISTUS)
    defender = rc.AEDUI
    for region, row in zip(REGIONS, action['details']['battle_plan']):
        place_piece(state, region, defender, rc.WARBAND, 6)
        row['target'] = defender
    state.setdefault('markers', {}).setdefault(REGIONS[0], {})[rc.MARKER_ABATIS] = defender
    seen = agent_for(state, {'region': REGIONS[0]})
    combat = record_combat(monkeypatch)
    _execute_battle(state, attacker, action)
    assert seen[0]['blocked'][REGIONS[0]]
    assert combat[0][1] == 2  # Guard halves four Losses, without Horse doubling.


def test_npc_skips_protected_region_for_first_applicable_bonus(monkeypatch):
    state, _, attacker, defender, action = position(rc.EVENT_SHADED)
    place_piece(state, REGIONS[0], defender, rc.FORT)
    combat = record_combat(monkeypatch)
    _execute_battle(state, attacker, action)
    assert all(row[4] == REGIONS[1] for row in combat)
    assert combat[1][1] == 6


def test_ranked_defenders_do_not_offer_the_unselected_owner():
    state, _, attacker, _, action = position(rc.EVENT_SHADED, 'defense')
    for region, row in zip(REGIONS, action['details']['battle_plan']):
        place_piece(state, region, rc.AEDUI, rc.WARBAND, 2)
        row.pop('target')
        row['targets'] = [rc.AEDUI, rc.BELGAE]
    assert request_for(state, attacker, action, rc.EVENT_SHADED) is None


def test_third_party_romans_get_no_ordinary_horse_bonus_request():
    state, _, _, _, action = position()
    for region, row in zip(REGIONS, action['details']['battle_plan']):
        place_piece(state, region, rc.AEDUI, rc.WARBAND, 2)
        row['target'] = rc.AEDUI
    assert request_for(state, rc.BELGAE, action, rc.EVENT_UNSHADED) is None


@pytest.mark.parametrize('side', [rc.EVENT_UNSHADED, rc.EVENT_SHADED])
@pytest.mark.parametrize('bad', [None, {}, {'region': None}, {'region': []},
    {'region': rc.PROVINCIA}, {'region': REGIONS[0], 'extra': 1}, {'use_default': 1}])
def test_invalid_response_rejected_without_board_changes(side, bad):
    state, _, attacker, _, action = position(side)
    request = request_for(state, attacker, action, side)
    before = encode(state)
    with pytest.raises(ValueError): validate_response(state, request, bad)
    assert encode(state) == before


def test_shaded_has_no_unprinted_decline():
    state, _, attacker, _, action = position(rc.EVENT_SHADED)
    with pytest.raises(ValueError):
        validate_response(state, request_for(state, attacker, action, rc.EVENT_SHADED), {'decline': True})


@pytest.mark.parametrize('remove_attacker', [False, True])
def test_stale_combatant_invalidates_selected_region(remove_attacker):
    state, _, attacker, defender, action = position()
    request = request_for(state, attacker, action, rc.EVENT_UNSHADED)
    faction = attacker if remove_attacker else defender
    piece = rc.AUXILIA if faction == rc.ROMANS else rc.WARBAND
    remove_piece(state, REGIONS[0], faction, piece, count_pieces(state, REGIONS[0], faction, piece))
    with pytest.raises(ValueError): validate_response(state, request, {'region': REGIONS[0]})


def test_terminal_board_inspection_then_decline():
    from fs_bot.cli.reactive import make_cli_reactive
    state, owner, attacker, _, action = position()
    request = request_for(state, attacker, action, rc.EVENT_UNSHADED)
    out = StringIO()
    before = encode(state)
    response = make_cli_reactive({owner}, StringIO('board\n3\n'), out)(state, owner, request)
    assert response == {'decline': True}
    assert 'Roman Auxilia' in out.getvalue()
    assert encode(state) == before


def test_terminal_shaded_named_region():
    from fs_bot.cli.reactive import make_cli_reactive
    state, owner, attacker, _, action = position(rc.EVENT_SHADED)
    request = request_for(state, attacker, action, rc.EVENT_SHADED)
    assert make_cli_reactive({owner}, StringIO('2\n'), StringIO())(
        state, owner, request) == {'region': REGIONS[1]}


def test_exception_clears_command_flags_even_for_raw_executor(monkeypatch):
    state, _, attacker, _, action = position()
    agent_for(state, {'region': REGIONS[0]})
    def pause(*args, **kwargs): raise EOFError
    monkeypatch.setattr('fs_bot.engine.execute.resolve_battle', pause)
    with pytest.raises(EOFError): _execute_battle(state, attacker, action)
    assert all(key not in state.get('event_modifiers', {}) for key in FLAGS)


def test_nested_battle_restores_outer_horse_selection(monkeypatch):
    state, _, attacker, _, action = position()
    def agent(board, faction, request):
        if request['kind'] == KIND: return {'region': request['legal_regions'][0]}
    state['decision_agent'] = agent
    seen = []
    nested = False
    def combat(board, region, actor, defender, **kwargs):
        nonlocal nested
        seen.append((region, board['event_modifiers'][FLAGS[0]]))
        if region == REGIONS[0] and not nested:
            nested = True
            inner = deepcopy(action)
            inner['details']['battle_plan'] = inner['details']['battle_plan'][1:]
            _execute_battle(board, actor, inner)
            assert board['event_modifiers'][FLAGS[0]] == REGIONS[0]
        return {}
    monkeypatch.setattr('fs_bot.engine.execute.resolve_battle', combat)
    _execute_battle(state, attacker, action)
    assert seen == [(REGIONS[0], REGIONS[0]), (REGIONS[1], REGIONS[1]), (REGIONS[1], REGIONS[0])]
    assert all(key not in state.get('event_modifiers', {}) for key in FLAGS)


def test_free_event_uses_owner_choice_and_costs_no_resources(monkeypatch):
    from fs_bot.engine.free_actions import execute_free_action_plan
    state, _, attacker, _, action = position()
    state['resources'][attacker] = 0
    seen = agent_for(state, {'region': REGIONS[1]})
    combat = record_combat(monkeypatch)
    result = execute_free_action_plan(state, attacker, {'request_type': 'event_command'}, action)
    assert result['executed'] and not result['errors']
    assert len(seen) == 1 and combat[1][1] == 4 and state['resources'][attacker] == 0


def test_preview_does_not_consume_live_owner_response_or_rng():
    from fs_bot.engine.moves import validate_player_action
    state, _, attacker, _, action = position()
    state['decision_agent'] = lambda *args: pytest.fail('Preview consumed live input')
    before = encode({k: v for k, v in state.items() if k != 'decision_agent'})
    assert validate_player_action(state, attacker, action)[0]
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before


def session_for(state, owner, meta=None, log=None, *, losses=False):
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.tools.seat_session import SeatSession
    session = SeatSession(state, meta or {'seat': owner}, log if log is not None else [],
                          HumanTurnDisplay(StringIO()))
    state['decision_agent'] = lambda board, faction, request: (
        session.reactive(board, faction, request)
        if faction == owner and (request['kind'] == KIND
                                 or losses and request['kind'] == 'loss_order') else None)
    return session


def attempt(session, attacker, action):
    from fs_bot.engine.game_engine import _action_transaction
    def driver(*args): pass
    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    with _action_transaction(session.state, driver):
        return _execute_battle(session.state, attacker, action)


@pytest.mark.parametrize('bad', [None, {}, {'region': rc.PROVINCIA}])
def test_durable_invalid_choice_rolls_back_and_survives_save_resume(tmp_path, bad):
    from fs_bot.tools.seat_session import DecisionPending, board_copy
    from fs_bot.state.serialize import save_game, load_game
    state, owner, attacker, _, action = position()
    session = session_for(state, owner)
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending): attempt(session, attacker, action)
    pending = deepcopy(session.data['pending'])
    assert decode(pending['request'])['kind'] == KIND
    session.import_inbox({'decision_id': pending['id'], 'response': bad})
    with pytest.raises(DecisionPending): attempt(session, attacker, action)
    assert session.error and session.data['pending'] == pending
    assert encode(board_copy(state)) == before
    path = tmp_path / 'horse.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session_for(restored, owner, meta, log)
    with pytest.raises(DecisionPending): attempt(resumed, attacker, action)
    assert resumed.data['pending'] == pending
    resumed.import_inbox({'decision_id': pending['id'], 'response': {'decline': True}})
    assert attempt(resumed, attacker, action)['executed']
    resumed.finish()
    assert len(log) == 1 and validate_state(restored) == []


def test_accepted_region_survives_later_casualty_pause_and_replay(tmp_path):
    from fs_bot.tools.seat_session import DecisionPending, board_copy
    from fs_bot.state.serialize import save_game, load_game
    state, owner, attacker, _, action = position(role='defense')
    origin = decode(encode(state))
    session = session_for(state, owner, losses=True)
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending): attempt(session, attacker, action)
    first = deepcopy(session.data['pending'])
    chosen = {'region': REGIONS[1]}
    session.import_inbox({'decision_id': first['id'], 'response': chosen})
    with pytest.raises(DecisionPending): attempt(session, attacker, action)
    later = deepcopy(session.data['pending'])
    assert decode(later['request'])['kind'] == 'loss_order'
    assert len(session.data['journal']) == 1 and encode(board_copy(state)) == before
    path = tmp_path / 'later.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session_for(restored, owner, meta, log, losses=True)
    with pytest.raises(DecisionPending): attempt(resumed, attacker, action)
    assert resumed.data['pending'] == later
    for _ in range(40):
        resumed.import_inbox({'decision_id': resumed.data['pending']['id'], 'response': {'use_default': True}})
        try:
            result = attempt(resumed, attacker, action)
            resumed.finish()
            break
        except DecisionPending: continue
    else: pytest.fail('Battle did not complete')
    origin['decision_agent'] = lambda board, faction, request: chosen if request['kind'] == KIND else None
    assert _execute_battle(origin, attacker, action) == result
    assert encode(board_copy(origin)) == encode(board_copy(restored))
    assert all(key not in restored.get('event_modifiers', {}) for key in FLAGS)


def test_prospective_queue_raw_delegation_retains_first_use(monkeypatch):
    state, _, attacker, _, action = position()
    seen = agent_for(state, {'decline': True})
    combat = record_combat(monkeypatch)
    _execute_battle(state, attacker, action, _skip_absent_targets=True)
    assert not seen and all(row[3] == REGIONS[0] for row in combat)


@pytest.mark.parametrize('decline', [False, True])
def test_real_battle_uses_selected_roman_loss_rate(decline, monkeypatch):
    from fs_bot.battle.resolve import resolve_battle
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=23)
    state['resources'][rc.ROMANS] = 2
    state['non_player_factions'] = {rc.BELGAE, rc.AEDUI, rc.ARVERNI}
    place_piece(state, REGIONS[0], rc.ROMANS, rc.AUXILIA, 3)
    # Five survivors can Counterattack for two, so Horse does not prompt
    # the separate poor-Counterattack Retreat rule.
    place_piece(state, REGIONS[0], rc.BELGAE, rc.WARBAND, 8)
    activate_capability(state, 59, rc.EVENT_UNSHADED)
    agent_for(state, {'decline': True} if decline else {'region': REGIONS[0]})
    records = []
    def combat(*args, **kwargs):
        result = resolve_battle(*args, **kwargs)
        records.append(result)
        return result
    monkeypatch.setattr('fs_bot.engine.execute.resolve_battle', combat)
    _execute_battle(state, rc.ROMANS, {'details': {'battle_plan': [{'region': REGIONS[0], 'target': rc.BELGAE}]}})
    assert records[0]['attack']['losses_requested'] == (1 if decline else 3)
    assert validate_state(state) == []


def test_defending_abatis_does_not_block_owner_counterattack_doubling(monkeypatch):
    state, owner, attacker, _, action = position(rc.EVENT_SHADED, 'defense', rc.SCENARIO_ARIOVISTUS)
    state.setdefault('markers', {}).setdefault(REGIONS[0], {})[rc.MARKER_ABATIS] = owner
    seen = agent_for(state, {'region': REGIONS[0]})
    combat = record_combat(monkeypatch)
    _execute_battle(state, attacker, action)
    assert not seen[0]['blocked'][REGIONS[0]]
    assert combat[0][1] == 0 and combat[0][2] == 8


def test_cancelled_german_abatis_does_not_block_horse(monkeypatch):
    state, _, attacker, _, action = position(rc.EVENT_SHADED, scenario=rc.SCENARIO_ARIOVISTUS)
    for region, row in zip(REGIONS, action['details']['battle_plan']):
        place_piece(state, region, rc.GERMANS, rc.WARBAND, 6)
        row['target'] = rc.GERMANS
    activate_capability(state, 'A31', rc.EVENT_UNSHADED)
    state.setdefault('event_modifiers', {})['card_A31_cancel_german_benefits'] = True
    state.setdefault('markers', {}).setdefault(REGIONS[0], {})[rc.MARKER_ABATIS] = rc.GERMANS
    seen = agent_for(state, {'region': REGIONS[0]})
    combat = record_combat(monkeypatch)
    _execute_battle(state, attacker, action)
    assert not seen[0]['blocked'][REGIONS[0]]
    assert combat[0][1] == 8
