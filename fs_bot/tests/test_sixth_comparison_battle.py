"""Sixth-audit Battle effects and the Germans Phase defender limit."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.battle.losses import calculate_losses
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.commands.common import free_action_scope
from fs_bot.commands.enlist_free import execute_free_enlist
from fs_bot.engine.execute import _execute_battle, execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT
from fs_bot.engine.germans_battle import germans_phase_battle
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state

REGION = rc.CARNUTES
SECOND = rc.MANDUBII


def _position(scenario=rc.SCENARIO_GREAT_REVOLT):
    state = build_initial_state(scenario, seed=1)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    state['non_player_factions'] = set()
    for faction in (rc.ROMANS, rc.GERMANS, rc.AEDUI, rc.BELGAE):
        state['resources'][faction] = 12
    return state


def _check_board(state):
    assert validate_state(state) == check_structural_integrity(state) == []


def _event(state, card, faction, *, shaded=False, params=None):
    state['current_card'] = card
    result = execute_decision(state, faction, {'action': ACTION_EVENT, 'player_action': {
        'command': rc.FIRST_DID_EVENT, 'details': {'card_id': card, 'event_params': params or {},
        'text_preference': rc.EVENT_SHADED if shaded else rc.EVENT_UNSHADED},
    }})
    assert result['executed'], result
    return result


def _battle(state, attacker, defender, *, prospective=False):
    with free_action_scope(state, attacker):
        result = _execute_battle(state, attacker, {
            'command': rc.CMD_BATTLE,
            'details': {'battle_plan': [{'region': REGION, 'target': defender}]},
        }, _skip_absent_targets=prospective)
    assert result['executed'] and not result['errors'], result


@pytest.mark.parametrize('defender,legio,inflexible,losses', [
    (rc.GERMANS, True, True, 5),
    (rc.GERMANS, True, False, 4),
    (rc.GERMANS, False, True, 5),
    (rc.BELGAE, True, True, 4),
])
def test_inflexible_cancels_shaded_legio_x_in_forecast_and_resolution(defender, legio, inflexible, losses):
    state = _position(rc.SCENARIO_ARIOVISTUS)
    place_piece(state, REGION, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, REGION, rc.ROMANS, rc.LEGION, 2, from_legions_track=True)
    place_piece(state, REGION, defender, rc.WARBAND, 8)
    if legio:
        _event(state, 15, defender, shaded=True)
    if inflexible:
        _event(state, 'A31', rc.ROMANS)
    _check_board(state)

    def stand(board, faction, request):
        if request['kind'] == 'retreat':
            return {'retreat': False}

    state['decision_agent'] = stand
    predicted = calculate_losses(state, REGION, rc.ROMANS, defender)
    _battle(state, rc.ROMANS, defender)

    assert (predicted, count_pieces(state, REGION, defender, rc.WARBAND)) == (losses, 8 - losses)
    _check_board(state)


@pytest.mark.parametrize('prospective', [False, True])
@pytest.mark.parametrize('attacker,stalwart,horse,prefire', [
    (rc.GERMANS, True, False, 0),
    (rc.GERMANS, True, True, 0),
    (rc.GERMANS, False, False, 1),
    (rc.BELGAE, True, False, 1),
])
def test_stalwart_cancels_slingers_before_any_region_choice(attacker, stalwart, horse, prefire, prospective):
    state = _position(rc.SCENARIO_ARIOVISTUS)
    place_piece(state, REGION, attacker, rc.WARBAND, 4)
    place_piece(state, REGION, rc.ROMANS, rc.AUXILIA, 2)
    _event(state, 13, rc.ROMANS)
    if horse:
        _event(state, 59, rc.ROMANS)
    if stalwart:
        _event(state, 'A31', rc.GERMANS, shaded=True)
    _check_board(state)
    requests = []

    def choose(board, faction, request):
        if request.get('card_id') == 13:
            requests.append(request['kind'])
        if request['kind'] == 'retreat':
            return {'retreat': False}

    state['decision_agent'] = choose
    _battle(state, attacker, rc.ROMANS, prospective=prospective)

    kind = 'capability_window' if prospective else 'slingers_region'
    assert requests == ([kind] if prefire else [])
    assert count_pieces(state, REGION, attacker, rc.WARBAND) == 4 - prefire
    assert count_pieces(state, REGION, rc.ROMANS, rc.AUXILIA) == prefire
    _check_board(state)


@pytest.mark.parametrize('card', [17, 65])
def test_guided_german_ambush_uses_third_party_roman_slingers(card):
    state = _position()
    place_piece(state, REGION, rc.GERMANS, rc.WARBAND, 4)
    place_piece(state, REGION, rc.AEDUI, rc.WARBAND, 2)
    place_piece(state, REGION, rc.ROMANS, rc.AUXILIA, 2)
    _event(state, 13, rc.ROMANS)
    _check_board(state)
    slingers = []

    def choose(board, faction, request):
        if request.get('request_type') == 'german_guided_march':
            return {'marches': []}
        if request.get('request_type') == 'german_guided_ambush':
            return {'region': REGION, 'defender': rc.AEDUI}
        if request.get('card_id') == 13:
            slingers.append((faction, deepcopy(request)))

    state['decision_agent'] = choose
    _event(state, card, rc.BELGAE)

    (owner, request), = slingers
    assert owner == rc.ROMANS
    assert request['attacker'] == rc.GERMANS
    assert count_pieces(state, REGION, rc.GERMANS, rc.WARBAND) == 3
    assert count_pieces(state, REGION, rc.AEDUI, rc.WARBAND) == 1
    assert count_pieces(state, REGION, rc.ROMANS, rc.AUXILIA) == 2
    _check_board(state)


def test_germans_phase_roman_reservation_applies_slingers_once_in_later_region():
    state = _position()
    for region in (REGION, SECOND):
        place_piece(state, region, rc.GERMANS, rc.WARBAND, 4)
        place_piece(state, region, rc.ROMANS, rc.AUXILIA, 2)
    _event(state, 13, rc.ROMANS)
    _event(state, 59, rc.ROMANS)
    _check_board(state)
    requests = []

    def choose(board, faction, request):
        if request['kind'] == 'capability_window':
            assert faction == rc.ROMANS and request['card_id'] == 13
            requests.append(deepcopy(request))
            return {'action': 'reserve' if len(requests) == 1 else 'activate'}

    state['decision_agent'] = choose
    result = germans_phase_battle(state)

    assert len(result['battles']) == 2
    first, second = result['regions']
    assert [r['region'] for r in requests] == [first, second]
    assert requests[0]['potential_regions'] == [second]
    assert requests[1]['actions'] == ['activate']
    assert count_pieces(state, first, rc.GERMANS, rc.WARBAND) == 4
    assert count_pieces(state, second, rc.GERMANS, rc.WARBAND) == 2
    assert count_pieces(state, first, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(state, second, rc.ROMANS, rc.AUXILIA) == 1
    _check_board(state)


def test_consuetudine_resolves_slingers_before_its_forced_ambush():
    state = _position()
    place_piece(state, REGION, rc.GERMANS, rc.WARBAND, 3)
    place_piece(state, REGION, rc.ROMANS, rc.AUXILIA, 4)
    _event(state, 13, rc.ROMANS)
    _check_board(state)

    _event(state, 53, rc.AEDUI)

    assert count_pieces(state, REGION, rc.GERMANS, rc.WARBAND) == 1
    assert count_pieces(state, REGION, rc.ROMANS, rc.AUXILIA) == 4
    _check_board(state)


@pytest.mark.parametrize('player,other', [(rc.AEDUI, rc.ROMANS), (rc.ROMANS, rc.AEDUI)])
def test_consuetudine_chooses_only_one_defender_with_player_priority(player, other):
    state = _position()
    state['non_player_factions'] = {other}
    place_piece(state, REGION, rc.GERMANS, rc.WARBAND, 4)
    place_piece(state, REGION, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, REGION, rc.AEDUI, rc.WARBAND, 2)
    _check_board(state)

    _event(state, 53, rc.BELGAE)

    assert count_pieces(state, REGION, player) == 0
    assert count_pieces(state, REGION, other) == 2
    assert count_pieces(state, REGION, rc.GERMANS, rc.WARBAND) == 4
    _check_board(state)


def test_enlist_german_battle_is_an_enemy_command_for_slingers():
    state = _position()
    place_piece(state, REGION, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    place_piece(state, REGION, rc.GERMANS, rc.WARBAND, 4)
    place_piece(state, REGION, rc.ROMANS, rc.AUXILIA, 2)
    _event(state, 13, rc.ROMANS)
    _check_board(state)

    execute_free_enlist(state, {'type': 'german_battle', 'region': REGION, 'target': rc.ROMANS})

    assert count_pieces(state, REGION, rc.GERMANS, rc.WARBAND) == 3
    assert count_pieces(state, REGION, rc.ROMANS, rc.AUXILIA) == 1
    _check_board(state)


@pytest.mark.parametrize('card', [17, 58, 65])
def test_delegated_german_event_ambush_uses_slingers(card):
    state = _position()
    place_piece(state, REGION, rc.GERMANS, rc.WARBAND, 4)
    place_piece(state, REGION, rc.AEDUI, rc.WARBAND, 2)
    place_piece(state, REGION, rc.ROMANS, rc.AUXILIA, 2)
    if card == 58:
        place_piece(state, REGION, rc.ROMANS, rc.FORT)
    _event(state, 13, rc.ROMANS)
    _check_board(state)

    _event(state, card, rc.BELGAE, shaded=card == 58)

    assert count_pieces(state, REGION, rc.GERMANS, rc.WARBAND) == 3
    _check_board(state)


def test_guided_aduatuca_retains_its_fort_exception_after_slingers():
    state = _position()
    place_piece(state, REGION, rc.GERMANS, rc.WARBAND, 4)
    place_piece(state, REGION, rc.ROMANS, rc.FORT)
    place_piece(state, REGION, rc.ROMANS, rc.AUXILIA, 2)
    _event(state, 13, rc.ROMANS)
    _check_board(state)

    def choose(board, faction, request):
        if request.get('request_type') == 'aduatuca_march':
            return {'destination': REGION, 'marches': []}

    state['decision_agent'] = choose
    _event(state, 58, rc.BELGAE, shaded=True)

    assert count_pieces(state, REGION, rc.GERMANS, rc.WARBAND) == 3
    assert count_pieces(state, REGION, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, REGION, rc.ROMANS, rc.FORT) == 1
    _check_board(state)


def test_aduatuci_slingers_reads_auxilia_after_replacements():
    state = _position(rc.SCENARIO_ARIOVISTUS)
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, 5, piece_state=rc.REVEALED)
    _event(state, 13, rc.ROMANS)
    _check_board(state)

    _event(state, 'A58', rc.GERMANS, shaded=True, params={'region': rc.NERVII})

    assert count_pieces(state, rc.NERVII, rc.GERMANS, rc.WARBAND) == 3
    assert count_pieces(state, rc.NERVII, rc.ROMANS, rc.AUXILIA) == 1
    _check_board(state)


def test_germans_phase_slingers_reservation_survives_save_and_resume(tmp_path):
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.state.serialize import encode, load_game, save_game
    from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy

    state = _position()
    for region in (REGION, SECOND):
        place_piece(state, region, rc.GERMANS, rc.WARBAND, 4)
        place_piece(state, region, rc.ROMANS, rc.AUXILIA, 4)
    _event(state, 13, rc.ROMANS)
    state['current_card'] = 53
    initial = deepcopy(state)

    def open_session(board, meta, log):
        session = SeatSession(board, meta, log, HumanTurnDisplay(StringIO()))
        board['decision_agent'] = lambda live, faction, request: (
            session.reactive(live, faction, request) if request['kind'] == 'capability_window' else None)
        return session

    def attempt(session):
        def driver(*args):
            pass

        driver.transaction_checkpoint = session.checkpoint
        driver.transaction_restore = session.restore
        with _action_transaction(session.state, driver):
            return _event(session.state, 53, rc.AEDUI)

    before = encode(initial)
    session = open_session(state, {'seat': rc.ROMANS}, [])
    with pytest.raises(DecisionPending):
        attempt(session)
    first = deepcopy(session.data['pending'])
    session.import_inbox({'decision_id': first['id'], 'response': {'action': 'reserve'}})
    with pytest.raises(DecisionPending):
        attempt(session)
    second = deepcopy(session.data['pending'])
    assert first['id'] != second['id'] and len(session.data['journal']) == 1
    session.import_inbox({'decision_id': second['id'], 'response': {'action': 'reserve'}})
    with pytest.raises(DecisionPending):
        attempt(session)
    assert session.error and session.data['pending'] == second
    assert encode(board_copy(state)) == before

    path = tmp_path / 'consuetudine.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = open_session(restored, meta, log)
    with pytest.raises(DecisionPending):
        attempt(resumed)
    assert resumed.data['pending'] == second
    resumed.import_inbox({'decision_id': second['id'], 'response': {'action': 'activate'}})
    assert attempt(resumed)['executed']
    resumed.finish()

    def replay(board, faction, request):
        if request['kind'] == 'capability_window':
            return {'action': 'reserve' if request['potential_regions'] else 'activate'}

    initial['decision_agent'] = replay
    _event(initial, 53, rc.AEDUI)
    assert encode(board_copy(initial)) == encode(board_copy(restored))
    assert sorted(count_pieces(restored, region, rc.GERMANS, rc.WARBAND)
                  for region in (REGION, SECOND)) == [2, 4]
    _check_board(restored)
