"""Card72: enforce the actual unshaded grant before selection and at execution."""
from copy import deepcopy
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, count_pieces_by_state
from fs_bot.cards.event_conditions import np_event_available
from fs_bot.cards.impetuosity_unshaded import (roman_plan, default_attacker,
    resolve_impetuosity_unshaded, validate_march, MARCH_REQUEST, BATTLE_REQUEST)
from fs_bot.cli.free_actions import collect_free_action
from fs_bot.engine.free_actions import validate_free_action_response
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state


def state(scenario=rc.SCENARIO_GREAT_REVOLT):
    s = build_initial_state(scenario, seed=7)
    s['non_player_factions'] = set(rc.FACTIONS)
    s['current_card'] = s['current_card_id'] = 72
    return s


def plan(destination=rc.NERVII, origins=(rc.MORINI,), count=2):
    return {'destination': destination, 'groups': [
        {'origin': r, 'group': {rc.AUXILIA: count}} for r in origins]}


def choose(s, movement, attacker=rc.BELGAE):
    requests = []
    def agent(board, faction, request):
        requests.append((faction, request))
        if request.get('request_type') == MARCH_REQUEST:
            return movement
        if request.get('request_type') == BATTLE_REQUEST:
            return {'attacker': attacker}
        if request['kind'] == 'retreat':
            return {'retreat': False, 'region': None}
        return None
    s['decision_agent'] = agent
    return requests


@pytest.mark.parametrize('scenario', [rc.SCENARIO_ARIOVISTUS, rc.SCENARIO_GALLIC_WAR])
@pytest.mark.parametrize('origin', [rc.CISALPINA, rc.PROVINCIA])
def test_reported_census_positions_decline_before_selecting_unreachable_event(scenario, origin):
    s = state(scenario)
    place_piece(s, origin, rc.ROMANS, rc.AUXILIA, 3)
    place_piece(s, origin, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(s, rc.MORINI, rc.BELGAE, rc.WARBAND, 8)
    before = encode(s)
    s['decision_agent'] = lambda *args: pytest.fail('Availability consulted a human')
    assert np_event_available(s, 72, rc.ROMANS, False) is False
    assert encode({k:v for k,v in s.items() if k != 'decision_agent'}) == before


def test_roman_priority_does_not_skip_higher_priority_march_without_battle(monkeypatch):
    from fs_bot.cards import war_fleet_roman as roman
    s = state()
    place_piece(s, rc.MORINI, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(s, rc.NERVII, rc.BELGAE, rc.WARBAND, 4)
    monkeypatch.setattr(roman, '_destination_sequence', lambda *a: iter([rc.ATREBATES, rc.NERVII]))
    assert roman_plan(s) is None
    assert np_event_available(s, 72, rc.ROMANS, False) is False


def test_roman_priority_applies_normal_piece_subset_and_adjacent_origins(monkeypatch):
    from fs_bot.cards import war_fleet_roman as roman
    from fs_bot.bots.roman_bot import _march_group_8_8_1
    s = state()
    place_piece(s, rc.MORINI, rc.ROMANS, rc.AUXILIA, 5)
    place_piece(s, rc.MORINI, rc.BELGAE, rc.WARBAND, 2)
    place_piece(s, rc.NERVII, rc.BELGAE, rc.WARBAND, 4)
    monkeypatch.setattr(roman, '_destination_sequence', lambda *a: iter([rc.NERVII]))
    result = roman_plan(s)
    assert result == {'destination': rc.NERVII, 'groups': [
        {'origin': rc.MORINI, 'group': _march_group_8_8_1(s, rc.MORINI)}]}
    assert result['groups'][0]['group'][rc.AUXILIA] == 2  # retain Roman Control


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
def test_human_moves_multiple_origins_for_free_and_chooses_attacker(scenario):
    s = state(scenario)
    for origin in (rc.MORINI, rc.ATREBATES):
        place_piece(s, origin, rc.ROMANS, rc.AUXILIA, 3)
    for enemy in (rc.ARVERNI, rc.BELGAE):
        place_piece(s, rc.NERVII, enemy, rc.WARBAND, 2)
    s['resources'][rc.ROMANS] = s['resources'][rc.ARVERNI] = 0
    calls = choose(s, plan(origins=(rc.ATREBATES, rc.MORINI)), rc.ARVERNI)
    result = resolve_impetuosity_unshaded(s, rc.ROMANS)[0]
    assert result['executed'] and result['battle']['executed']
    assert result['attacker'] == rc.ARVERNI
    assert result['march']['total_cost'] == 0
    assert not result['battle']['battle_sa_executed']
    assert [e['origin'] for e in result['march']['marches']] == [rc.ATREBATES, rc.MORINI]
    assert [f for f, req in calls if req.get('request_type') in (MARCH_REQUEST, BATTLE_REQUEST)] == [rc.ROMANS, rc.ROMANS]
    assert count_pieces(s, rc.MORINI, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(s, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 1
    assert s['resources'][rc.ROMANS] == s['resources'][rc.ARVERNI] == 0


def test_human_can_march_without_enemy_and_normal_origin_flips_apply():
    s = state()
    place_piece(s, rc.MORINI, rc.ROMANS, rc.AUXILIA, 3, piece_state=rc.REVEALED)
    choose(s, plan())
    result = resolve_impetuosity_unshaded(s, rc.ROMANS)[0]
    assert result['executed'] and result['battle'] is None
    assert count_pieces_by_state(s, rc.MORINI, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 1
    assert count_pieces_by_state(s, rc.NERVII, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 2


@pytest.mark.parametrize('attacker,leader', [(rc.ARVERNI,rc.VERCINGETORIX),(rc.BELGAE,rc.AMBIORIX)])
def test_leader_without_warbands_is_a_legal_attacker(attacker, leader):
    s = state()
    place_piece(s, rc.MORINI, rc.ROMANS, rc.AUXILIA, 3)
    place_piece(s, rc.NERVII, attacker, rc.LEADER, leader_name=leader)
    calls = choose(s, plan(), attacker)
    result = resolve_impetuosity_unshaded(s, rc.ROMANS)[0]
    assert result['battle']['executed']
    assert any(req.get('attackers') == [attacker] for _, req in calls)


def test_default_attacker_includes_once_per_command_capability():
    from fs_bot.cards.capabilities import activate_capability, set_capability_owner
    s = state()
    place_piece(s, rc.NERVII, rc.ROMANS, rc.AUXILIA, 4)
    for enemy in (rc.ARVERNI, rc.BELGAE):
        place_piece(s, rc.NERVII, enemy, rc.WARBAND, 2)
    activate_capability(s, 59, rc.EVENT_SHADED)
    set_capability_owner(s, 59, rc.ARVERNI)
    before = deepcopy(s['spaces'])
    s['decision_agent'] = lambda *args: pytest.fail('Preview consulted human')
    assert default_attacker(s, rc.ROMANS, rc.NERVII) == rc.BELGAE
    assert s['spaces'] == before
    assert 'card59_shaded_region' not in s.get('event_modifiers', {})


def test_equal_attackers_use_seeded_tie_selection():
    seen = set()
    for seed in range(10):
        s = state()
        s['rng'].seed(seed)
        place_piece(s, rc.NERVII, rc.ROMANS, rc.AUXILIA, 4)
        for enemy in (rc.ARVERNI, rc.BELGAE):
            place_piece(s, rc.NERVII, enemy, rc.WARBAND, 2)
        seen.add(default_attacker(s, rc.ROMANS, rc.NERVII))
    assert seen == {rc.ARVERNI, rc.BELGAE}


@pytest.mark.parametrize('bad', [
    plan(destination=rc.MORINI), plan(destination=rc.PROVINCIA),
    plan(origins=(rc.MORINI,rc.MORINI)), plan(count=0), plan(count=4),
    {'destination': rc.NERVII, 'groups': [{'origin': rc.MORINI, 'group': {rc.FORT:1}}]},
    {'destination': rc.NERVII, 'groups': [{'origin': rc.MORINI, 'group': {rc.LEADER:True}}]},
    dict(plan(), sa=rc.SA_SCOUT),
])
def test_invalid_march_cannot_mutate_state(bad):
    s = state()
    place_piece(s, rc.MORINI, rc.ROMANS, rc.AUXILIA, 3)
    before = encode(s)
    assert validate_free_action_response(s, rc.ROMANS, {'request_type':MARCH_REQUEST}, bad)
    assert encode(s) == before


@pytest.mark.parametrize('response', [{'attacker':rc.AEDUI},{'decline':True},{'attacker':rc.BELGAE,'sa':rc.SA_AMBUSH}])
def test_enemy_battle_choice_cannot_change_mandatory_grant(response):
    s = state()
    assert validate_free_action_response(s, rc.ROMANS,
        {'request_type':BATTLE_REQUEST,'attackers':[rc.BELGAE]}, response)


def test_cli_offers_multiple_adjacent_origins_and_board_command():
    from fs_bot.cli.menus import set_board_hook
    s = state()
    for origin in (rc.MORINI,rc.ATREBATES):
        place_piece(s, origin, rc.ROMANS, rc.AUXILIA, 3)
    before = encode(s)
    output, calls = io.StringIO(), []
    set_board_hook(lambda: calls.append('board'))
    try:
        response = collect_free_action(s, rc.ROMANS, {'request_type':MARCH_REQUEST},
            io.StringIO('\n'.join(['Plan the action','board',rc.NERVII,rc.MORINI,'2',rc.ATREBATES,'2'])+'\n'), output)
    finally:
        set_board_hook(None)
    assert response == plan(origins=(rc.MORINI,rc.ATREBATES))
    assert calls == ['board'] and encode(s) == before
    response = collect_free_action(s, rc.ROMANS,
        {'request_type':BATTLE_REQUEST,'region':rc.NERVII,'attackers':[rc.ARVERNI,rc.BELGAE]},
        io.StringIO(rc.BELGAE+'\n'), output)
    assert response == {'attacker':rc.BELGAE}


def test_frost_checks_enemy_battle_after_safe_march():
    from fs_bot.cards.impetuosity_unshaded import _np_attackers, execute_march
    from fs_bot.cards.impetuosity import _frost_ok
    from fs_bot.board.control import refresh_all_control
    from fs_bot.engine.victory import calculate_victory_margin
    s = state()
    s['frost'] = True
    s['non_player_factions'].remove(rc.BELGAE)
    place_piece(s, rc.MORINI, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(s, rc.NERVII, rc.ROMANS, rc.AUXILIA, 5)
    place_piece(s, rc.NERVII, rc.BELGAE, rc.WARBAND, 4)
    place_piece(s, rc.NERVII, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    # The human Belgic player is already above threshold elsewhere. Neither
    # side Controls Nervii; the forced Battle can give it Belgic Control.
    for region in s['spaces']:
        if region not in (rc.NERVII, rc.MORINI, rc.CISALPINA):
            place_piece(s, region, rc.BELGAE, rc.WARBAND)
    refresh_all_control(s)
    after = deepcopy(s)
    execute_march(after, rc.ROMANS, plan())
    before = s
    assert calculate_victory_margin(before, rc.BELGAE) > 0
    assert _frost_ok(before, after)
    assert _np_attackers(before, after, rc.ROMANS, rc.NERVII) == []


def test_pause_save_resume_and_replay_preserve_both_human_choices(tmp_path):
    from fs_bot.cards.card_effects import execute_card_72
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.engine.execute import _resolve_free_actions
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.state.serialize import decode, save_game, load_game
    from fs_bot.tools.seat_session import SeatSession, DecisionPending, board_copy
    s = state()
    s['non_player_factions'].remove(rc.ROMANS)
    s['next_card'] = 4
    place_piece(s, rc.MORINI, rc.ROMANS, rc.AUXILIA, 3)
    place_piece(s, rc.NERVII, rc.BELGAE, rc.WARBAND, 2)
    place_piece(s, rc.NERVII, rc.ARVERNI, rc.WARBAND, 2)
    execute_card_72(s, shaded=False)
    before = encode(s)

    def session(board, meta=None, log=None):
        out = io.StringIO()
        view = HumanTurnDisplay(out)
        view.remember(board, [rc.ROMANS])
        seat = SeatSession(board, meta or {'seat':rc.ROMANS}, log or [], view)
        board['decision_agent'] = seat.reactive
        return seat, out

    def resolve(seat):
        def callback(*args): pass
        callback.transaction_checkpoint = seat.checkpoint
        callback.transaction_restore = seat.restore
        with _action_transaction(seat.state, callback):
            return _resolve_free_actions(seat.state, rc.ROMANS)

    seat, output = session(s)
    with pytest.raises(DecisionPending): resolve(seat)
    assert encode(board_copy(s)) == before
    pending = seat.data['pending']
    assert decode(pending['request'])['request_type'] == MARCH_REQUEST
    seat.import_inbox({'decision_id':pending['id'],'response':plan()})
    with pytest.raises(DecisionPending): resolve(seat)
    assert encode(board_copy(s)) == before
    pending = seat.data['pending']
    assert decode(pending['request'])['request_type'] == BATTLE_REQUEST
    pending_board = decode(pending['board'])
    assert count_pieces(pending_board, rc.MORINI, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(pending_board, rc.NERVII, rc.ROMANS, rc.AUXILIA) == 2
    assert 'changes since your last decision' in output.getvalue()
    save = tmp_path / 'unshaded72.json'
    save_game(s, save, meta=seat.meta, log=seat.log)
    restored, meta, log = load_game(save)
    resumed, _ = session(restored, meta, log)
    resumed.import_inbox({'decision_id':pending['id'],'response':{'attacker':rc.BELGAE}})
    for _ in range(10):
        try:
            result = resolve(resumed)
            break
        except DecisionPending:
            pending = resumed.data['pending']
            request = decode(pending['request'])
            response = ({'retreat':False,'region':None} if request['kind'] == 'retreat'
                        else request['pieces'] if request['kind'] == 'loss_order' else False)
            resumed.import_inbox({'decision_id':pending['id'],'response':response})
    else:
        pytest.fail('Battle never completed')
    resumed.finish()
    assert result[0]['attacker'] == rc.BELGAE and result[0]['battle']['executed']
    assert 'card_72_march_enemy_battle' not in restored['event_modifiers']
    committed = encode(board_copy(restored))
    replay, _ = session(decode(before))
    replay.data['expected'] = [{'id':e['assistant_id'],'signature':e['assistant_signature']}
                               for e in resumed.log]
    replay.import_inbox([{'decision_id':e['assistant_id'],'response':decode(e['assistant_response'])}
                        for e in resumed.log])
    assert resolve(replay) == result
    replay.finish()
    assert encode(board_copy(replay.state)) == committed
    assert replay.log == resumed.log




@pytest.mark.parametrize('faction,piece', [(rc.ROMANS,rc.AUXILIA),(rc.AEDUI,rc.WARBAND)])
def test_human_cannot_skip_required_march_using_unavailable_bot_default(faction, piece):
    s = state()
    s['non_player_factions'].remove(faction)
    place_piece(s, rc.MORINI, faction, piece, 2)
    before = encode(s)
    s['decision_agent'] = lambda *args: {'use_default':True}
    with pytest.raises(ValueError, match='choose the required Impetuosity March'):
        resolve_impetuosity_unshaded(s, faction)
    assert encode({k:v for k,v in s.items() if k != 'decision_agent'}) == before
    assert validate_free_action_response(s, faction,
        {'request_type':MARCH_REQUEST}, {'decline':True})
