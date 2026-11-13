"""Massed Gallic Archers through paid, granted, and automatic Battles."""

from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.battle.losses import calculate_losses
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece
from fs_bot.bots.bot_common import card27_shaded_absorption, predict_battle
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine.arverni_phase import run_arverni_phase
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_COMMAND, _action_transaction
from fs_bot.engine.germans_battle import germans_phase_battle
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.tests.test_assistant_session import _driver
from fs_bot.tests.test_seventh_comparison_battle import check, event, position
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


REGION = rc.CARNUTES


def _battle(state, attacker, defender):
    state['current_card'] = 1
    result = execute_decision(state, attacker, {'action': ACTION_COMMAND, 'player_action': {
        'command': rc.CMD_BATTLE, 'sa': 'No SA', 'regions': [REGION], 'details': {
            'battle_plan': [{'region': REGION, 'target': defender}]}}})
    assert result['executed'] and not result['errors'], result
    check(state)
    return result


def _arverni_phase(state):
    # Frost skips March. With no enemy Resources, Raid cannot change the board.
    for faction in state['resources']:
        state['resources'][faction] = 0
    check(state)
    result = run_arverni_phase(state, is_frost=True)
    check(state)
    return result['battle']['battles']


def _choose_target(defender):
    def agent(_board, _owner, request):
        if request.get('request_type') == 'fixed_event_battle':
            return {'region': REGION, 'defender': defender}
        if request['kind'] == 'retreat':
            return {'retreat': False}
    return agent


@pytest.mark.parametrize('mode', ['paid', 'legiones', 'arverni-phase'])
@pytest.mark.parametrize('warbands', [5, 6])
def test_opening_archers_loss_uses_six_participating_warbands(mode, warbands):
    scenario = rc.SCENARIO_ARIOVISTUS if mode == 'arverni-phase' else rc.SCENARIO_GREAT_REVOLT
    state = position(scenario)
    place_piece(state, REGION, rc.ARVERNI, rc.WARBAND, warbands)
    place_piece(state, REGION, rc.ROMANS, rc.AUXILIA, 4)
    event(state, 27, rc.AEDUI, shaded=True)
    state['decision_agent'] = _choose_target(rc.ROMANS)

    if mode == 'paid':
        _battle(state, rc.ARVERNI, rc.ROMANS)
    elif mode == 'legiones':
        event(state, 2, rc.ARVERNI, shaded=True, params={'battle_region': REGION})
    else:
        assert len(_arverni_phase(state)) == 1

    assert count_pieces(state, REGION, rc.ROMANS, rc.AUXILIA) == (0 if warbands == 6 else 2)
    assert count_pieces(state, REGION, rc.ARVERNI, rc.WARBAND) == warbands - (
        1 if warbands == 5 and mode != 'arverni-phase' else 0)


def test_morasses_applies_archers_to_attacker_and_keeps_printed_exceptions():
    state = position()
    place_piece(state, REGION, rc.ARVERNI, rc.WARBAND, 6)
    place_piece(state, REGION, rc.AEDUI, rc.WARBAND, 4)
    event(state, 27, rc.AEDUI, shaded=True)
    state['decision_agent'] = _choose_target(rc.ARVERNI)

    result = event(state, 36, rc.AEDUI)['free_actions'][0]['result']

    assert result['attack']['losses_requested'] == 1
    assert result['counterattack'] is None and not result['defender_retreated']
    assert count_pieces_by_state(state, REGION, rc.AEDUI, rc.WARBAND, rc.HIDDEN) == 3
    assert count_pieces(state, REGION, rc.ARVERNI, rc.WARBAND) == 5


@pytest.mark.parametrize('attacker_warbands', [0, 1])
def test_aquitani_retains_event_losses_without_an_attacking_force(attacker_warbands):
    state = position()
    place_piece(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND, 6)
    if attacker_warbands:
        place_piece(state, rc.PICTONES, rc.AEDUI, rc.WARBAND, attacker_warbands)
    event(state, 27, rc.AEDUI, shaded=True)

    def stand(_board, _owner, request):
        if request['kind'] == 'retreat':
            return {'retreat': False}

    state['decision_agent'] = stand
    result = event(state, 25, rc.AEDUI, params={'battle_region': rc.PICTONES})

    assert result['free_actions'][0]['result']['attack']['losses_requested'] == 3
    assert count_pieces(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND) == 3
    assert count_pieces(state, rc.PICTONES, rc.AEDUI, rc.WARBAND) == 0


def test_legiones_removes_its_first_legion_once_when_archers_fire():
    state = position()
    place_piece(state, REGION, rc.ARVERNI, rc.WARBAND, 6)
    place_piece(state, REGION, rc.ROMANS, rc.LEGION, 2, from_legions_track=True)
    place_piece(state, REGION, rc.ROMANS, rc.AUXILIA, 4)
    event(state, 27, rc.AEDUI, shaded=True)
    state['decision_agent'] = _choose_target(rc.ROMANS)
    rng = state['rng'].getstate()

    event(state, 2, rc.ARVERNI, shaded=True, params={'battle_region': REGION})

    assert state['fallen_legions'] == 1
    assert count_pieces(state, REGION, rc.ROMANS, rc.LEGION) == 1
    assert count_pieces(state, REGION, rc.ROMANS, rc.AUXILIA) == 1
    assert state['rng'].getstate() == rng


@pytest.mark.parametrize('arverni_attack', [False, True])
def test_fixed_battle_ends_when_archers_remove_the_last_participant(arverni_attack):
    state = position()
    place_piece(state, REGION, rc.ARVERNI, rc.WARBAND, 6)
    opponent = rc.ROMANS if arverni_attack else rc.AEDUI
    place_piece(state, REGION, opponent, rc.AUXILIA if arverni_attack else rc.WARBAND)
    event(state, 27, rc.AEDUI, shaded=True)
    seen = []
    select = _choose_target(rc.ROMANS if arverni_attack else rc.ARVERNI)

    def agent(board, owner, request):
        seen.append((owner, request['kind']))
        return select(board, owner, request)

    state['decision_agent'] = agent
    result = (event(state, 2, rc.ARVERNI, shaded=True, params={'battle_region': REGION})
              if arverni_attack else event(state, 36, rc.AEDUI))

    assert result['free_actions'][0]['result']['card27_wiped']
    assert count_pieces(state, REGION, opponent) == 0
    assert count_pieces_by_state(state, REGION, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 6
    assert [r for r in seen if r[1] in ('loss_order', 'retreat')] == [(opponent, 'loss_order')]


def test_base_germans_phase_takes_archers_loss_before_ambush():
    state = position()
    place_piece(state, REGION, rc.ARVERNI, rc.WARBAND, 6, piece_state=rc.REVEALED)
    place_piece(state, REGION, rc.GERMANS, rc.WARBAND, 4)
    event(state, 27, rc.AEDUI, shaded=True)

    result = germans_phase_battle(state)

    assert result['regions'] == [REGION]
    assert count_pieces(state, REGION, rc.GERMANS, rc.WARBAND) == 3
    assert count_pieces(state, REGION, rc.ARVERNI, rc.WARBAND) == 5
    check(state)


def test_morbihan_archers_wipe_returns_unrevealed_warbands_to_their_origins():
    state = position(rc.SCENARIO_ARIOVISTUS)
    assert _ally_tribe(state, rc.TRIBE_VENETI, rc.ARVERNI)
    place_piece(state, rc.VENETI, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(state, REGION, rc.ROMANS, rc.AUXILIA)
    event(state, 27, rc.AEDUI, shaded=True)

    result = event(state, 'A20', rc.GERMANS, shaded=True)

    assert result['free_actions'][0]['result']['card27_wiped']
    assert count_pieces(state, REGION, rc.ARVERNI, rc.WARBAND) == 0
    assert count_pieces(state, REGION, rc.ROMANS, rc.AUXILIA) == 0
    for origin in (rc.VENETI, rc.PICTONES):
        assert count_pieces_by_state(state, origin, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 3
    assert '_morbihan_projection' not in state


@pytest.mark.parametrize('opponent,stalwart', [
    (rc.GERMANS, True), (rc.GERMANS, False), (rc.BELGAE, True),
])
def test_stalwart_cancels_archers_against_german_attackers(opponent, stalwart):
    state = position(rc.SCENARIO_ARIOVISTUS)
    place_piece(state, REGION, rc.ARVERNI, rc.WARBAND, 6)
    place_piece(state, REGION, opponent, rc.WARBAND, 4)
    event(state, 27, rc.AEDUI, shaded=True)
    if stalwart:
        event(state, 'A31', rc.ROMANS, shaded=True)
    opening_loss = int(not (opponent == rc.GERMANS and stalwart))

    assert card27_shaded_absorption(state, REGION, opponent, rc.ARVERNI) == opening_loss
    _battle(state, opponent, rc.ARVERNI)

    assert count_pieces(state, REGION, opponent, rc.WARBAND) == 2 - opening_loss
    assert count_pieces(state, REGION, rc.ARVERNI, rc.WARBAND) == 4 + opening_loss


@pytest.mark.parametrize('stalwart', [False, True])
def test_archers_against_german_defenders_respects_stalwart(stalwart):
    state = position(rc.SCENARIO_ARIOVISTUS)
    place_piece(state, REGION, rc.ARVERNI, rc.WARBAND, 6)
    place_piece(state, REGION, rc.GERMANS, rc.WARBAND, 4)
    event(state, 27, rc.AEDUI, shaded=True)
    if stalwart:
        event(state, 'A31', rc.ROMANS, shaded=True)

    assert len(_arverni_phase(state)) == 1
    assert count_pieces(state, REGION, rc.GERMANS, rc.WARBAND) == int(stalwart)


@pytest.mark.parametrize('defender,inflexible', [
    (rc.GERMANS, True), (rc.GERMANS, False), (rc.BELGAE, True),
])
def test_inflexible_cancels_unshaded_archers_in_attack_and_forecast(defender, inflexible):
    state = position(rc.SCENARIO_ARIOVISTUS)
    place_piece(state, REGION, rc.ARVERNI, rc.WARBAND, 6)
    place_piece(state, REGION, defender, rc.WARBAND, 4)
    event(state, 27, rc.AEDUI)
    if inflexible:
        event(state, 'A31', rc.ROMANS)
    expected = 3 if defender == rc.GERMANS and inflexible else 2

    before = encode(state)
    assert calculate_losses(state, REGION, rc.ARVERNI, defender) == expected
    assert predict_battle(state, REGION, rc.ARVERNI, defender, is_ambush=True)['inflicted'] == expected
    assert encode(state) == before
    battle, = _arverni_phase(state)

    assert battle['result']['attack']['losses_requested'] == expected
    assert count_pieces(state, REGION, defender, rc.WARBAND) == 4 - expected


@pytest.mark.parametrize('warbands', [6, 7])
def test_arverni_phase_counts_warbands_after_slingers_fire(warbands):
    state = position(rc.SCENARIO_ARIOVISTUS)
    place_piece(state, REGION, rc.ARVERNI, rc.WARBAND, warbands)
    place_piece(state, REGION, rc.ROMANS, rc.FORT)
    place_piece(state, REGION, rc.ROMANS, rc.AUXILIA, 2)
    # Slingers remove one Warband. The Fort halves the eventual Attack,
    # and the Archers threshold uses the Warbands still in the Battle.
    event(state, 13, rc.ROMANS)
    event(state, 27, rc.AEDUI, shaded=True)
    battle, = _arverni_phase(state)
    assert battle['result']['attack']['losses_requested'] == 1
    assert count_pieces(state, REGION, rc.ARVERNI, rc.WARBAND) == warbands - 1
    assert count_pieces(state, REGION, rc.ROMANS, rc.AUXILIA) == 7 - warbands
    assert count_pieces(state, REGION, rc.ROMANS, rc.FORT) == 1


def test_fixed_battle_opening_loss_survives_pending_save_and_replay(tmp_path):
    state = position()
    place_piece(state, REGION, rc.ARVERNI, rc.WARBAND, 6)
    place_piece(state, REGION, rc.ROMANS, rc.AUXILIA, 2, piece_state=rc.REVEALED)
    place_piece(state, REGION, rc.ROMANS, rc.AUXILIA, 2)
    event(state, 27, rc.AEDUI, shaded=True)
    state['current_card'] = 2
    initial = deepcopy(state)

    def make_session(board, meta=None, log=None):
        session = SeatSession(board, {'seat': rc.ROMANS} if meta is None else meta,
                              [] if log is None else log, HumanTurnDisplay(StringIO()))

        def agent(live, owner, request):
            if (request['kind'] == 'loss_order'
                    and count_pieces(live, REGION, rc.ROMANS, rc.AUXILIA) == 4):
                return session.reactive(live, owner, request)
            return _choose_target(rc.ROMANS)(live, owner, request)

        board['decision_agent'] = agent
        return session

    def run(session):
        with _action_transaction(session.state, _driver(session)):
            return event(session.state, 2, rc.ARVERNI, shaded=True, params={'battle_region': REGION})

    original = make_session(state)
    with pytest.raises(DecisionPending):
        run(original)
    pending = deepcopy(original.data['pending'])
    request = decode(pending['request'])
    assert request['kind'] == 'loss_order' and request['num_losses'] == 1
    assert encode(board_copy(state)) == encode(initial)
    path = tmp_path / 'archers.json'
    save_game(state, path, meta=original.meta, log=original.log)
    loaded, meta, log = load_game(path, validate=True)
    resumed = make_session(loaded, meta, log)
    assert resumed.data['pending'] == pending
    chosen = next(piece for piece in request['pieces'] if piece[:2] == (rc.AUXILIA, rc.REVEALED))
    resumed.import_inbox({'decision_id': pending['id'], 'response': [chosen]})
    result = run(resumed)
    resumed.finish()

    def replay_agent(board, owner, live_request):
        if (live_request['kind'] == 'loss_order'
                and count_pieces(board, REGION, rc.ROMANS, rc.AUXILIA) == 4):
            assert decode(log[0]['assistant_request']) == dict(live_request, faction=owner)
            return decode(log[0]['assistant_response'])
        return _choose_target(rc.ROMANS)(board, owner, live_request)

    initial['decision_agent'] = replay_agent
    assert event(initial, 2, rc.ARVERNI, shaded=True, params={'battle_region': REGION}) == result
    assert encode(board_copy(initial)) == encode(board_copy(loaded))
    assert count_pieces(loaded, REGION, rc.ROMANS, rc.AUXILIA) == 0
