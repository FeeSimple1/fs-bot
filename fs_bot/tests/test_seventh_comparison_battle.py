"""Battle capability regressions from the seventh comparison audit."""

from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine.arverni_phase import run_arverni_phase
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_COMMAND, ACTION_EVENT, _action_transaction
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def check(state):
    assert validate_state(state) == []
    assert check_structural_integrity(state) == []


def position(scenario=rc.SCENARIO_GREAT_REVOLT):
    state = build_initial_state(scenario, seed=7)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    state['non_player_factions'] = set()
    for faction in (rc.ROMANS, rc.AEDUI, rc.BELGAE, rc.GERMANS, rc.ARVERNI):
        if faction in state['resources']:
            state['resources'][faction] = 20
    check(state)
    return state


def event(state, card, actor, *, shaded=False, params=None):
    state['current_card'] = card
    result = execute_decision(state, actor, {'action': ACTION_EVENT, 'player_action': {
        'command': rc.FIRST_DID_EVENT, 'details': {
            'card_id': card, 'text_preference': rc.EVENT_SHADED if shaded else rc.EVENT_UNSHADED,
            'event_params': params or {}}}})
    assert result['executed'] and not result.get('errors'), result
    check(state)
    return result


def choose_fixed_target(region, defender, seen):
    def agent(_state, owner, request):
        seen.append((owner, deepcopy(request)))
        if request.get('request_type') == 'fixed_event_battle':
            return {'region': region, 'defender': defender}
        if request['kind'] == 'retreat':
            return {'retreat': False}
        if request['kind'] in ('slingers_region', 'horse_region'):
            return {'region': region}
    return agent


@pytest.mark.parametrize('card,region,defender,with_fire,without_fire', [
    (2, rc.CARNUTES, rc.ROMANS, (3, 1), (4, 0)),
    (25, rc.PICTONES, rc.BELGAE, (1, 4), (3, 3)),
    (36, rc.PICTONES, rc.BELGAE, (3, 7), (4, 6)),
])
@pytest.mark.parametrize('slingers', [False, True])
def test_fixed_event_battle_applies_slingers_before_losses(
        card, region, defender, with_fire, without_fire, slingers):
    state = position()
    place_piece(state, region, rc.AEDUI, rc.WARBAND, 4)
    place_piece(state, region, rc.ROMANS, rc.AUXILIA, 2)
    defending_piece = rc.AUXILIA if defender == rc.ROMANS else rc.WARBAND
    if defender != rc.ROMANS:
        place_piece(state, region, defender, defending_piece, 8)
    if slingers:
        event(state, 13, rc.ROMANS)
    seen = []
    state['decision_agent'] = choose_fixed_target(region, defender, seen)
    resources = deepcopy(state['resources'])

    result = event(state, card, rc.AEDUI, shaded=card == 2,
                   params={'battle_region': region} if card != 36 else None)

    assert (count_pieces(state, region, rc.AEDUI, rc.WARBAND),
            count_pieces(state, region, defender, defending_piece)) == (
                with_fire if slingers else without_fire)
    requests = [(owner, req) for owner, req in seen if req['kind'] == 'slingers_region']
    assert len(requests) == int(slingers)
    if slingers:
        owner, request = requests[0]
        assert owner == rc.ROMANS and request['defenders'] == {region: defender}
        assert request['auxilia'] == {region: 2}
        assert next(i for i, pair in enumerate(seen) if pair == requests[0]) < next(
            i for i, (_, req) in enumerate(seen) if req['kind'] == 'loss_order')
    assert state['resources'] == resources
    if card == 36:
        assert result['free_actions'][0]['result']['counterattack'] is None
        assert count_pieces_by_state(state, region, rc.AEDUI, rc.WARBAND, rc.HIDDEN) == (
            with_fire[0] if slingers else without_fire[0])


@pytest.mark.parametrize('citadel', [False, True])
def test_morasses_horse_doubles_attack_with_printed_citadel_exception(citadel):
    state = position()
    region = rc.CARNUTES
    place_piece(state, region, rc.AEDUI, rc.WARBAND, 4)
    place_piece(state, region, rc.BELGAE, rc.WARBAND, 8)
    if citadel:
        assert _ally_tribe(state, rc.TRIBE_CARNUTES, rc.BELGAE, citadel=True)
    event(state, 59, rc.AEDUI, shaded=True)
    seen = []
    select_target = choose_fixed_target(region, rc.BELGAE, seen)

    def agent(board, owner, request):
        response = select_target(board, owner, request)
        return {'use_default': True} if request['kind'] == 'horse_region' else response

    state['decision_agent'] = agent
    event(state, 36, rc.AEDUI)

    requests = [(owner, req) for owner, req in seen if req['kind'] == 'horse_region']
    assert len(requests) == 1
    assert requests[0][0] == rc.AEDUI and requests[0][1]['blocked'] == {region: False}
    assert count_pieces(state, region, rc.BELGAE, rc.WARBAND) == 4
    assert count_pieces(state, region, rc.BELGAE, rc.CITADEL) == int(citadel)
    assert count_pieces_by_state(state, region, rc.AEDUI, rc.WARBAND, rc.HIDDEN) == 4
    assert 'card59_shaded_region' not in state.get('event_modifiers', {})


def arverni_position(regions):
    state = position(rc.SCENARIO_ARIOVISTUS)
    state['resources'][rc.ROMANS] = 0
    for region in regions:
        place_piece(state, region, rc.ARVERNI, rc.WARBAND, 4)
        place_piece(state, region, rc.ROMANS, rc.AUXILIA, 2)
    event(state, 13, rc.ROMANS)
    return state


def test_morbihan_prefire_removes_a_projected_warband_from_its_origin():
    state = position(rc.SCENARIO_ARIOVISTUS)
    assert _ally_tribe(state, rc.TRIBE_VENETI, rc.ARVERNI)
    origins = (rc.VENETI, rc.PICTONES)
    for origin in origins:
        place_piece(state, origin, rc.ARVERNI, rc.WARBAND, 2)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 2,
                piece_state=rc.REVEALED)
    event(state, 13, rc.ROMANS)
    seen = []
    state['decision_agent'] = choose_fixed_target(rc.CARNUTES, rc.ROMANS, seen)

    result = event(state, 'A20', rc.GERMANS, shaded=True)

    assert result['free_actions'][0]['result']['attack']['losses_requested'] == 1
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND) == 0
    assert sorted(count_pieces_by_state(state, origin, rc.ARVERNI, rc.WARBAND, rc.REVEALED)
                  for origin in origins) == [1, 2]
    assert [owner for owner, req in seen if req['kind'] == 'slingers_region'] == [rc.ROMANS]


@pytest.mark.parametrize('regions,reserve', [
    ((rc.CARNUTES,), False),
    ((rc.CARNUTES, rc.PICTONES), False),
    ((rc.CARNUTES, rc.PICTONES), True),
])
def test_arverni_phase_slingers_use_is_shared_across_the_phase(regions, reserve):
    state = arverni_position(regions)
    seen = []

    def agent(_state, owner, request):
        if request['kind'] == 'capability_window':
            assert owner == rc.ROMANS and request['card_id'] == 13
            seen.append(deepcopy(request))
            return {'action': 'reserve' if reserve and 'reserve' in request['actions']
                    else 'activate'}

    state['decision_agent'] = agent
    result = run_arverni_phase(state, is_frost=True)
    order = [battle['region'] for battle in result['battle']['battles']]
    assert set(order) == set(regions) and len(order) == len(regions)
    assert [request['region'] for request in seen] == (order if reserve else order[:1])
    assert seen[0]['potential_regions'] == order[1:]
    assert seen[0]['actions'] == (['activate', 'reserve'] if order[1:] else ['activate'])
    if reserve:
        assert seen[1]['actions'] == ['activate'] and seen[1]['potential_regions'] == []
    firing_region = order[-1] if reserve else order[0]
    for region in regions:
        fired = region == firing_region
        assert count_pieces(state, region, rc.ARVERNI, rc.WARBAND) == 4 - int(fired)
        assert count_pieces(state, region, rc.ROMANS, rc.AUXILIA) == int(fired)
    check(state)


def battle(state, attacker, defender, region):
    return execute_decision(state, attacker, {'action': ACTION_COMMAND, 'player_action': {
        'command': rc.CMD_BATTLE, 'sa': 'No SA', 'regions': [region],
        'details': {'battle_plan': [{'region': region, 'target': defender}]}}})


@pytest.mark.parametrize('enemy,ballistae,stalwart,counterattack,remaining', [
    (rc.GERMANS, True, True, False, 0),
    (rc.GERMANS, True, False, False, 1),
    (rc.GERMANS, False, True, False, 0),
    (rc.BELGAE, True, True, False, 1),
    (rc.GERMANS, True, True, True, 0),
    (rc.GERMANS, True, False, True, 1),
])
def test_stalwart_cancels_ballistae_for_german_losses_only(
        enemy, ballistae, stalwart, counterattack, remaining):
    state = position(rc.SCENARIO_ARIOVISTUS)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.FORT)
    place_piece(state, rc.CARNUTES, enemy, rc.WARBAND, 2 if counterattack else 4)
    if ballistae:
        event(state, 10, rc.ROMANS)
    if stalwart:
        event(state, 'A31', rc.GERMANS, shaded=True)
    after_roll = deepcopy(state['rng'])
    assert after_roll.randint(rc.DIE_MIN, rc.DIE_MAX) == 3
    state['decision_agent'] = choose_fixed_target(rc.CARNUTES, enemy, [])
    attacker, defender = (rc.ROMANS, enemy) if counterattack else (enemy, rc.ROMANS)

    result = battle(state, attacker, defender, rc.CARNUTES)

    assert result['executed'] and not result['errors'], result
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.FORT) == remaining
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.FORT) == 1
    assert state['rng'].getstate() == after_roll.getstate()
    check(state)


@pytest.mark.parametrize('phase', [False, True])
def test_new_slingers_choices_survive_durable_save_and_replay(tmp_path, phase):
    region = rc.CARNUTES
    if phase:
        state = arverni_position((region,))
        run = lambda board: run_arverni_phase(board, is_frost=True)
        kind, response = 'capability_window', {'action': 'activate'}
        bad_response = {'action': 'reserve'}
    else:
        state = position()
        place_piece(state, region, rc.AEDUI, rc.WARBAND, 4)
        place_piece(state, region, rc.BELGAE, rc.WARBAND, 8)
        place_piece(state, region, rc.ROMANS, rc.AUXILIA, 2)
        event(state, 13, rc.ROMANS)
        state['current_card'] = 36
        run = lambda board: event(board, 36, rc.AEDUI)
        kind, response = 'slingers_region', {'region': region}
        bad_response = {'region': rc.PROVINCIA}

    def session(board, meta=None, log=None):
        result = SeatSession(board, {'seat': rc.ROMANS} if meta is None else meta,
                             [] if log is None else log, HumanTurnDisplay(StringIO()))
        board['decision_agent'] = lambda live, owner, request: (
            result.reactive(live, owner, request) if request['kind'] == kind else None)
        return result

    def step(current):
        def driver(*_args):
            pass
        driver.transaction_checkpoint = current.checkpoint
        driver.transaction_restore = current.restore
        with _action_transaction(current.state, driver):
            return run(current.state)

    initial = deepcopy(state)
    original = session(state)
    with pytest.raises(DecisionPending):
        step(original)
    pending = deepcopy(original.data['pending'])
    assert decode(pending['request'])['kind'] == kind
    assert encode(board_copy(state)) == encode(initial)
    original.import_inbox({'decision_id': pending['id'], 'response': bad_response})
    with pytest.raises(DecisionPending):
        step(original)
    assert original.error and original.data['pending'] == pending
    assert encode(board_copy(state)) == encode(initial)
    save = tmp_path / 'pending.json'
    save_game(state, save, meta=original.meta, log=original.log)
    restored, meta, log = load_game(save, validate=True)
    resumed = session(restored, meta, log)
    assert resumed.data['pending'] == pending
    resumed.import_inbox({'decision_id': pending['id'], 'response': response})
    result = step(resumed)
    resumed.finish()

    def replay_agent(_state, owner, request):
        if request['kind'] == kind:
            assert decode(log[-1]['assistant_request']) == dict(request, faction=owner)
            return decode(log[-1]['assistant_response'])

    initial['decision_agent'] = replay_agent
    assert run(initial) == result
    assert encode(board_copy(initial)) == encode(board_copy(restored))
    assert count_pieces(restored, region, rc.ARVERNI if phase else rc.AEDUI, rc.WARBAND) == 3
    check(restored)
