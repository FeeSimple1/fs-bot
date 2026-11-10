"""Declare Retreat before Attack, then dispose of actual survivors."""

from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_leader_in_region, place_piece
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine import action_windows, voluntary_removal
from fs_bot.engine.agent import AGREEMENT, LOSS_ORDER, RETREAT, RETREAT_DISPOSITION
from fs_bot.engine.execute import _execute_battle
from fs_bot.engine.game_engine import _action_transaction, get_sop_factions
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tests.test_assistant_session import _driver
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def position(defender=rc.ARVERNI, attacker=rc.ROMANS):
    scenario = rc.SCENARIO_ARIOVISTUS if defender == rc.GERMANS else rc.SCENARIO_GREAT_REVOLT
    board = build_initial_state(scenario, seed=81)
    board['resources'][attacker] = 10
    board['non_player_factions'] = set(get_sop_factions(board)) - {defender}
    return board


def battle(board, defender=rc.ARVERNI, attacker=rc.ROMANS):
    results = []

    def observe(stage, state, region, target, result):
        if stage == 'after':
            results.append(result)

    result = _execute_battle(board, attacker, {'command': rc.CMD_BATTLE, 'sa': 'No SA',
        'details': {'battle_plan': [{'region': rc.CARNUTES, 'target': defender}]}},
        _battle_observer=observe)
    assert result['executed'] and not result['errors'], result
    assert validate_state(board) == []
    return results[0]


@pytest.mark.parametrize('defender, leader', [(rc.ARVERNI, rc.VERCINGETORIX),
                                             (rc.GERMANS, rc.ARIOVISTUS_LEADER)])
def test_roman_attack_offers_only_survivors_and_moves_chosen_hidden_and_leader(defender, leader):
    board = position(defender)
    place_piece(board, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(board, rc.CARNUTES, defender, rc.LEADER, leader_name=leader)
    place_piece(board, rc.CARNUTES, defender, rc.WARBAND, 3)
    place_piece(board, rc.CARNUTES, defender, rc.WARBAND, piece_state=rc.SCOUTED)
    place_piece(board, rc.ATREBATES, defender, rc.WARBAND)
    seen = []

    def agent(state, who, request):
        assert who == defender
        seen.append(request)
        if request['kind'] == RETREAT:
            return {'retreat': True}
        if request['kind'] == LOSS_ORDER:
            return [next(p for p in request['pieces'] if p[:2] == (rc.WARBAND, rc.HIDDEN))]
        return {'region': rc.ATREBATES, 'stay_hidden_warbands': 1, 'stay_leader': False}

    board['decision_agent'] = agent
    result = battle(board, defender)
    assert [request['kind'] for request in seen] == [RETREAT, LOSS_ORDER, RETREAT_DISPOSITION]
    assert seen[0]['stage'] == 'declare'
    final = seen[-1]
    assert final['max_hidden_warbands'] == 2 and final['can_stay_leader']
    assert final['legal_regions'] == [rc.ATREBATES]
    assert result['attack']['losses_taken'] == 1 and result['counterattack'] is None
    assert not result['reveal'] and result['defender_retreated']
    assert result['retreat']['stayed'] == [(rc.WARBAND, 1)]
    assert get_leader_in_region(board, rc.ATREBATES, defender) == leader
    assert count_pieces_by_state(board, rc.CARNUTES, defender, rc.WARBAND, rc.HIDDEN) == 1
    assert count_pieces_by_state(board, rc.ATREBATES, defender, rc.WARBAND, rc.HIDDEN) == 2
    assert count_pieces_by_state(board, rc.ATREBATES, defender, rc.WARBAND, rc.SCOUTED) == 1


@pytest.mark.parametrize('has_destination', [False, True])
def test_terminal_can_declare_retreat_and_remove_survivors_instead_of_moving(has_destination):
    board = position()
    place_piece(board, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    place_piece(board, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 2)
    place_piece(board, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, piece_state=rc.REVEALED)
    if has_destination:
        place_piece(board, rc.ATREBATES, rc.ARVERNI, rc.WARBAND)
    stdout = StringIO()
    board['decision_agent'] = make_cli_reactive({rc.ARVERNI}, StringIO('2\n2\nRemove them\n'), stdout)
    result = battle(board)
    assert result['defender_retreated']
    assert result['retreat']['stayed'] == [(rc.WARBAND, 1)]
    assert sum(n for _, n in result['retreat']['removed']) == 2
    assert ('Retreat to Atrebates' in stdout.getvalue()) == has_destination
    assert 'How many Hidden Warbands stay?' in stdout.getvalue()


def test_gallic_attack_with_no_destination_removes_every_survivor_including_legion():
    board = position(rc.ROMANS, attacker=rc.BELGAE)
    place_piece(board, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    place_piece(board, rc.CARNUTES, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(board, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    requests = []

    def agent(state, who, request):
        requests.append(request['kind'])
        return {'retreat': True, 'region': None}

    board['decision_agent'] = agent
    result = battle(board, rc.ROMANS, rc.BELGAE)
    assert requests == [RETREAT]  # All survivors must be removed.
    assert result['defender_retreated'] and not result['reveal']
    assert result['retreat']['removed'] == [(rc.LEGION, 1), (rc.AUXILIA, 1)]
    assert board['fallen_legions'] == 1


def test_static_only_defender_cannot_declare_retreat():
    board = position(rc.ROMANS, attacker=rc.BELGAE)
    place_piece(board, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    place_piece(board, rc.CARNUTES, rc.ROMANS, rc.FORT)
    place_piece(board, rc.ATREBATES, rc.ROMANS, rc.AUXILIA)
    seen = []

    def agent(state, who, request):
        seen.append(request['kind'])
        return {'retreat': True}

    board['decision_agent'] = agent
    result = battle(board, rc.ROMANS, rc.BELGAE)
    assert RETREAT not in seen and RETREAT_DISPOSITION not in seen
    assert not result['defender_retreated'] and result['retreat'] is None


@pytest.mark.parametrize('new_controller', [None, rc.AEDUI, rc.ARVERNI])
def test_step6_uses_live_control_and_requires_the_current_hosts_permission(new_controller):
    board = position()
    place_piece(board, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    place_piece(board, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, piece_state=rc.REVEALED)
    place_piece(board, rc.CARNUTES, rc.ARVERNI, rc.WARBAND)
    place_piece(board, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, 2)
    if new_controller:
        place_piece(board, rc.ATREBATES, new_controller, rc.WARBAND)
    requests = []

    def choose(state, who, request):
        kind = request['kind']
        if kind == voluntary_removal.KIND:
            if request['window']['stage'] == 'battle_retreat':
                options = [op for op in request['options'] if op['region'] == rc.ATREBATES]
                if options:
                    return {'operations': [voluntary_removal.operation(options[0], 2)]}
            return {'done': True}
        requests.append(request)
        if kind == AGREEMENT:
            return new_controller != rc.ARVERNI
        if kind == RETREAT:
            return {'retreat': True}
        return {'region': rc.ATREBATES if new_controller == rc.ARVERNI else None,
                'stay_hidden_warbands': 1, 'stay_leader': False}

    choose.supports_action_windows = True
    board['non_player_factions'].remove(rc.ROMANS)
    board['decision_agent'] = choose
    with action_windows.scope(board, actor=rc.ROMANS):
        result = battle(board)
    assert [request['kind'] for request in requests] == [AGREEMENT, RETREAT, RETREAT_DISPOSITION]
    now_friendly = new_controller == rc.ARVERNI
    assert requests[1]['legal_regions'] == ([] if now_friendly else [rc.ATREBATES])
    assert requests[2]['legal_regions'] == ([rc.ATREBATES] if now_friendly else [])
    assert result['retreat']['moved' if now_friendly else 'removed'] == [(rc.WARBAND, 1)]


def test_no_disposition_is_offered_if_the_attack_kills_all_mobile_defenders():
    board = position()
    place_piece(board, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(board, rc.CARNUTES, rc.ARVERNI, rc.WARBAND)
    place_piece(board, rc.ATREBATES, rc.ARVERNI, rc.WARBAND)
    seen = []

    def agent(state, who, request):
        seen.append(request['kind'])
        return {'retreat': True} if request['kind'] == RETREAT else None

    board['decision_agent'] = agent
    result = battle(board)
    assert RETREAT in seen and RETREAT_DISPOSITION not in seen
    assert result['defender_retreated'] and result['attack']['losses_taken'] == 1
    assert result['retreat'] == {'stayed': [], 'moved': [], 'removed': []}


def test_detached_frost_forecast_includes_all_legal_hidden_stay_counts():
    from fs_bot.cards.divination_np import _battle_frost_outcomes
    board = position()
    place_piece(board, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    place_piece(board, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 2)
    place_piece(board, rc.ATREBATES, rc.ARVERNI, rc.WARBAND)
    initial = encode(board)
    outcomes = list(_battle_frost_outcomes(board, rc.CARNUTES, rc.ARVERNI, attacker=rc.ROMANS))
    assert {count_pieces_by_state(sim, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, rc.HIDDEN)
            for sim in outcomes} == {0, 1, 2}
    assert encode(board) == initial


@pytest.mark.parametrize('legacy', [False, True])
def test_save_reload_replays_the_declaration_and_losses_before_survivor_choice(tmp_path, legacy):
    board = position()
    place_piece(board, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(board, rc.CARNUTES, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(board, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 2)
    if legacy:
        place_piece(board, rc.ATREBATES, rc.ARVERNI, rc.WARBAND)
    before = encode(board_copy(board))
    meta = {'seat': rc.ARVERNI, 'scenario': board['scenario'], 'seed': 81}
    session = SeatSession(board, meta, [], HumanTurnDisplay(StringIO()))

    def initial_agent(state, who, request):
        if legacy and request['kind'] == RETREAT:
            request = {key: value for key, value in request.items() if key != 'stage'}
        return session.reactive(state, who, request)

    board['decision_agent'] = initial_agent

    def pause(current, kind):
        with pytest.raises(DecisionPending):
            with _action_transaction(current.state, _driver(current)):
                battle(current.state)
        assert encode(board_copy(current.state)) == before
        pending = current.data['pending']
        request = decode(pending['request'])
        assert request['kind'] == kind, current.error
        return pending, request

    path = tmp_path / 'save.json'

    def reload(current):
        save_game(current.state, path, meta=current.meta, log=current.log)
        saved, saved_meta, log = load_game(path, validate=True)
        loaded = SeatSession(saved, saved_meta, log, HumanTurnDisplay(StringIO()))
        saved['decision_agent'] = loaded.reactive
        return loaded

    declaration, request = pause(session, RETREAT)
    assert (request.get('stage') == 'declare') is not legacy
    session = reload(session)
    session.import_inbox({'decision_id': declaration['id'], 'response': {
        'retreat': True, 'region': rc.ATREBATES if legacy else None}})
    loss, request = pause(session, LOSS_ORDER)
    session.import_inbox({'decision_id': loss['id'], 'response': [
        next(p for p in request['pieces'] if p[0] == rc.WARBAND)]})
    if not legacy:
        survivors, request = pause(session, RETREAT_DISPOSITION)
        assert request['legal_regions'] == [] and request['max_hidden_warbands'] == 1
        assert [e['reactive'] for e in session.data['journal']] == [RETREAT, LOSS_ORDER]
        session = reload(session)
        session.import_inbox({'decision_id': survivors['id'], 'response': {
            'region': rc.ATREBATES, 'stay_hidden_warbands': 1, 'stay_leader': True}})
        assert pause(session, RETREAT_DISPOSITION)[0] == survivors
        assert session.error and session.data['pending'] == survivors
        session.data['queue'].clear()
        session.import_inbox({'decision_id': survivors['id'], 'response': {
            'region': None, 'stay_hidden_warbands': 1, 'stay_leader': False}})
    with _action_transaction(session.state, _driver(session)):
        result = battle(session.state)
    session.finish()
    assert result['defender_retreated']
    assert result['retreat']['stayed'] == ([(rc.LEADER, 1), (rc.WARBAND, 1)] if legacy
                                           else [(rc.WARBAND, 1)])
    assert count_pieces(session.state, rc.CARNUTES, rc.ARVERNI, rc.LEADER) == int(legacy)
