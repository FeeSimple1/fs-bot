"""BM5-01 and BM5-02: German Phalanx and Abatis Battle losses."""

from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.battle.losses import calculate_losses, compatible_loss_request, resolve_losses
from fs_bot.board.pieces import count_pieces, get_leader_in_region, place_piece
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine.agent import LOSS_ORDER, RETREAT
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_COMMAND, ACTION_EVENT, _action_transaction
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy, validate_response


REGION = rc.CARNUTES
ABATIS = (rc.MARKER_ABATIS, None)
AULERCI = (rc.ALLY, None, None, rc.TRIBE_AULERCI)


def _board(seed=1):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=seed)
    state['non_player_factions'] = set()
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    for faction in (rc.ROMANS, rc.GERMANS, rc.AEDUI):
        state['resources'][faction] = 20
    return state


def _event(state, card, actor, *, shaded=False, **params):
    state['current_card'] = card
    result = execute_decision(state, actor, {'action': ACTION_EVENT, 'player_action': {
        'command': rc.FIRST_DID_EVENT, 'sa': 'No SA', 'details': {
            'card_id': card, 'text_preference': rc.EVENT_SHADED if shaded else rc.EVENT_UNSHADED,
            'event_params': params}}})
    assert result['executed'] and not result.get('errors'), result


def _battle(state, attacker, defender):
    response = {'action': ACTION_COMMAND, 'player_action': {
        'command': rc.CMD_BATTLE, 'sa': 'No SA', 'regions': [REGION],
        'details': {'battle_plan': [{'region': REGION, 'target': defender}]}}}
    validate_response(state, {'kind': 'turn', 'faction': attacker, 'options': [ACTION_COMMAND]},
                      response)
    result = execute_decision(state, attacker, response)
    assert result['executed'] and not result['errors'], result
    assert validate_state(state) == check_structural_integrity(state) == []


@pytest.mark.parametrize('roman_attack,opponent,stalwart,legio,attack,counterattack', [
    (True, rc.GERMANS, True, True, 2, 3),
    (True, rc.GERMANS, True, False, 2, 3),
    (True, rc.GERMANS, False, True, 5, 0),
    (False, rc.GERMANS, True, True, 2, 2),
    (False, rc.GERMANS, False, True, 1, 4),
    (True, rc.AEDUI, True, True, 5, 0),
    (False, rc.AEDUI, True, True, 1, 4),
])
def test_stalwart_cancels_legio_x_in_both_steps_only_against_germans(
        roman_attack, opponent, stalwart, legio, attack, counterattack):
    state = _board()
    place_piece(state, REGION, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, REGION, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(state, REGION, opponent, rc.WARBAND, 8 if roman_attack else 4)
    if not roman_attack:
        place_piece(state, REGION, rc.ROMANS, rc.AUXILIA, 2)
    if stalwart:
        _event(state, 'A31', rc.GERMANS, shaded=True)
    if legio:
        _event(state, 15, rc.ROMANS)
    assert validate_state(state) == check_structural_integrity(state) == []
    attacker, defender = (rc.ROMANS, opponent) if roman_attack else (opponent, rc.ROMANS)
    predicted = calculate_losses(state, REGION, attacker, defender)
    first_loss = {}

    def agent(board, faction, request):
        if request['kind'] == RETREAT:
            return {'retreat': False}
        if request['kind'] == LOSS_ORDER:
            first_loss.setdefault(faction, request['num_losses'])
            return [p for p in request['pieces'] if p[0] == rc.AUXILIA]

    state['decision_agent'] = agent
    _battle(state, attacker, defender)

    assert predicted == attack
    assert first_loss.get(defender, 0) == attack
    assert first_loss.get(attacker, 0) == counterattack


def _defending_abatis(seed=1, *, ally=False, diviciacus=False, legions=4):
    state = _board(seed)
    place_piece(state, REGION, rc.ROMANS, rc.LEGION, legions, from_legions_track=True)
    place_piece(state, REGION, rc.AEDUI, rc.WARBAND)
    if ally:
        assert _ally_tribe(state, rc.TRIBE_AULERCI, rc.AEDUI)
    if diviciacus:
        place_piece(state, REGION, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    _event(state, 'A64', rc.AEDUI, region=REGION)
    assert state['markers'][REGION][rc.MARKER_ABATIS] == rc.AEDUI
    assert validate_state(state) == check_structural_integrity(state) == []
    return state


@pytest.mark.parametrize('choice', [AULERCI, ABATIS])
def test_abatis_and_named_ally_are_alternatives_after_the_warband(choice):
    state = _defending_abatis(ally=True)
    requests = []

    def agent(board, faction, request):
        if request['kind'] == RETREAT:
            return {'retreat': False}
        if request['kind'] == LOSS_ORDER and faction == rc.AEDUI:
            requests.append(deepcopy(request))
            return [choice] if choice in request['pieces'] else []

    state['decision_agent'] = agent
    _battle(state, rc.ROMANS, rc.AEDUI)

    assert [r['pieces'] for r in requests] == [[(rc.WARBAND, rc.HIDDEN)], [ABATIS, AULERCI]]
    assert count_pieces(state, REGION, rc.AEDUI, rc.WARBAND) == 0
    assert state['tribes'][rc.TRIBE_AULERCI]['allied_faction'] == (
        None if choice == AULERCI else rc.AEDUI)
    assert state['markers'][REGION].get(rc.MARKER_ABATIS) == (
        rc.AEDUI if choice == AULERCI else None)


@pytest.mark.parametrize('seed,legions,leader_survives', [(2, 4, True), (5, 6, True), (2, 6, False)])
def test_diviciacus_waits_for_abatis_including_after_a_saving_roll(seed, legions, leader_survives):
    state = _defending_abatis(seed, diviciacus=True, legions=legions)
    marker_when_leader_offered = []

    def agent(board, faction, request):
        if request['kind'] == RETREAT:
            return {'retreat': False}
        if (request['kind'] == LOSS_ORDER and faction == rc.AEDUI
                and any(piece[0] == rc.LEADER for piece in request['pieces'])):
            marker_when_leader_offered.append(rc.MARKER_ABATIS in board['markers'][REGION])

    state['decision_agent'] = agent
    _battle(state, rc.ROMANS, rc.AEDUI)

    assert rc.MARKER_ABATIS not in state['markers'][REGION]
    assert get_leader_in_region(state, REGION, rc.AEDUI) == (
        rc.DIVICIACUS if leader_survives else None)
    assert marker_when_leader_offered == ([] if leader_survives else [False])


@pytest.mark.parametrize('retreat', [False, True])
def test_abatis_respects_an_explicit_ally_priority_in_the_current_tier(retreat):
    state = _defending_abatis(ally=True)
    result = resolve_losses(state, REGION, rc.AEDUI, 1 if retreat else 2,
                            is_retreat=retreat, abatis_defender=True, loss_order=[AULERCI])

    assert result['removed'] == ([(rc.ALLY, 1)] if retreat else [(rc.WARBAND, 1), (rc.ALLY, 1)])
    assert state['markers'][REGION][rc.MARKER_ABATIS] == rc.AEDUI
    assert result['rolls'] == []


def test_german_settlement_prompt_keeps_its_default_and_can_offer_abatis():
    state = _board()
    place_piece(state, REGION, rc.GERMANS, rc.SETTLEMENT)
    place_piece(state, REGION, rc.GERMANS, rc.WARBAND)
    _event(state, 'A64', rc.GERMANS, region=REGION)
    requests = []

    def agent(board, faction, request):
        requests.append(deepcopy(request))
        return None

    state['decision_agent'] = agent
    result = resolve_losses(state, REGION, rc.GERMANS, 2, abatis_defender=True)

    settlement = (rc.SETTLEMENT, None)
    assert requests[-1]['pieces'] == [settlement, ABATIS]
    assert compatible_loss_request(requests[-1], dict(requests[-1], pieces=[settlement]))
    assert result['removed'] == [(rc.WARBAND, 1), (rc.SETTLEMENT, 1)]
    assert state['markers'][REGION][rc.MARKER_ABATIS] == rc.GERMANS
    assert validate_state(state) == check_structural_integrity(state) == []


def _session(state, meta=None, log=None):
    session = SeatSession(state, {'seat': rc.AEDUI} if meta is None else meta,
                          [] if log is None else log, HumanTurnDisplay(StringIO()))
    state['decision_agent'] = session.reactive
    return session


def _attempt(session):
    def driver(*args):
        pass

    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    with _action_transaction(session.state, driver):
        return resolve_losses(session.state, REGION, rc.AEDUI, 2, abatis_defender=True)


def test_abatis_choice_saves_reloads_and_rejects_an_unoffered_loss(tmp_path):
    state = _defending_abatis(ally=True)
    session = _session(state)
    before = encode(board_copy(state))
    session.import_inbox([{'response': [[rc.WARBAND, rc.HIDDEN]]}])
    with pytest.raises(DecisionPending):
        _attempt(session)
    pending = deepcopy(session.data['pending'])
    assert decode(pending['request'])['pieces'] == [ABATIS, AULERCI]
    assert len(session.data['journal']) == 1 and encode(board_copy(state)) == before

    path = tmp_path / 'abatis-loss.json'
    save_game(state, path, meta=session.meta, log=session.log)
    state, meta, log = load_game(path, validate=True)
    session = _session(state, meta, log)
    session.import_inbox({'decision_id': pending['id'], 'response': [[rc.LEADER, None]]})
    with pytest.raises(DecisionPending):
        _attempt(session)
    assert session.data['pending'] == pending and encode(board_copy(state)) == before
    session.import_inbox({'decision_id': pending['id'], 'response': [list(AULERCI)]})
    result = _attempt(session)
    session.finish()

    assert result['removed'] == [(rc.WARBAND, 1), (rc.ALLY, 1)]
    assert [entry['assistant_id'] for entry in log] == ['d000001', pending['id']]
    assert session.data['pending'] is None and not session.data['journal']
    assert state['markers'][REGION][rc.MARKER_ABATIS] == rc.AEDUI
    assert validate_state(state) == check_structural_integrity(state) == []
