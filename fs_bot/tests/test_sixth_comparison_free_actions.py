"""Sixth-audit Aedui Ambush and German Enlist March regressions."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.human_plan import _collect_enlist_details
from fs_bot.commands.common import CommandError, free_action_scope
from fs_bot.commands.enlist_free import execute_free_enlist
from fs_bot.engine.execute import _execute_battle, execute_decision
from fs_bot.engine.free_actions import execute_free_action_plan, validate_free_action_response
from fs_bot.engine.game_engine import ACTION_COMMAND_SA, ACTION_EVENT, _action_transaction
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy, validate_response

BATTLE_REGIONS = (rc.CARNUTES, rc.MANDUBII)
ORIGIN = rc.SUGAMBRI
DESTINATIONS = (rc.NERVII, rc.TREVERI)


def _board(scenario):
    state = build_initial_state(scenario, seed=7)
    state.update(current_card=52, current_card_id=52, next_card=49,
                 card_edition='second-edition', non_player_factions=set())
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    return state


def _check_board(state):
    assert validate_state(state) == check_structural_integrity(state) == []


def _assembly_board():
    state = _board(rc.SCENARIO_GREAT_REVOLT)
    state['resources'][rc.AEDUI] = 10
    for region in BATTLE_REGIONS:
        place_piece(state, region, rc.AEDUI, rc.WARBAND, 6)
        place_piece(state, region, rc.BELGAE, rc.WARBAND, 5, piece_state=rc.REVEALED)
    _check_board(state)
    return state


def _ambush_plan(regions=BATTLE_REGIONS):
    return {'command': rc.CMD_BATTLE, 'sa': rc.SA_AMBUSH, 'sa_regions': list(regions),
            'details': {'battle_plan': [{'region': r, 'target': rc.BELGAE} for r in BATTLE_REGIONS]}}


def _play_assembly(state, faction=rc.AEDUI):
    return execute_decision(state, faction, {'action': ACTION_EVENT, 'player_action': {
        'command': rc.FIRST_DID_EVENT,
        'details': {'card_id': 52, 'text_preference': rc.EVENT_SHADED},
    }})


def _stand(board, faction, request):
    if request['kind'] == 'retreat':
        return {'retreat': False}


def _assembly_session(state, meta, log):
    session = SeatSession(state, meta, log, HumanTurnDisplay(StringIO()))
    state['decision_agent'] = lambda board, faction, req: (
        session.reactive(board, faction, req) if req['kind'] == 'free_action'
        else _stand(board, faction, req))
    return session


def _attempt_assembly(session, faction=rc.AEDUI):
    def driver(*args):
        pass

    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    with _action_transaction(session.state, driver):
        return _play_assembly(session.state, faction)


@pytest.mark.parametrize('route', ['ordinary', 'assembly', 'battle_executor'])
def test_aedui_cannot_ambush_two_regions(route):
    state = _assembly_board()
    plan = _ambush_plan()
    state['decision_agent'] = lambda board, faction, req: (
        plan if req['kind'] == 'free_action' else _stand(board, faction, req))
    before = encode(board_copy(state))

    if route == 'assembly':
        result = _play_assembly(state)
    elif route == 'ordinary':
        result = execute_decision(state, rc.AEDUI, {'action': ACTION_COMMAND_SA, 'player_action': plan})
    else:
        with free_action_scope(state, rc.AEDUI):
            result = _execute_battle(state, rc.AEDUI, plan)

    assert not result['executed'] and 'one Region' in str(result)
    assert encode(board_copy(state)) == before


def test_assembly_two_ability_plan_keeps_one_ambush_limit():
    state = _assembly_board()
    plan = _ambush_plan()
    plan.update(sa='No SA', sa_regions=[], special_abilities=[
        {'sa': rc.SA_AMBUSH, 'sa_regions': list(BATTLE_REGIONS), 'sa_timing': 'during'},
        {'sa': rc.SA_TRADE, 'sa_regions': [], 'sa_timing': 'after'},
    ])
    request = {'request_type': 'event_command', 'with_sa': True, 'max_special_abilities': 2}
    before = encode(state)
    error = validate_free_action_response(state, rc.AEDUI, request, plan)
    assert error and 'one Region' in error
    assert encode(state) == before


def test_assembly_keeps_excess_ambush_pending_then_resumes_with_one(tmp_path):
    initial = _assembly_board()
    session = _assembly_session(deepcopy(initial), {'seat': rc.AEDUI}, [])
    with pytest.raises(DecisionPending):
        _attempt_assembly(session)
    pending = deepcopy(session.data['pending'])
    assert decode(pending['request'])['request_type'] == 'event_command'
    session.import_inbox({'decision_id': pending['id'], 'response': _ambush_plan()})
    with pytest.raises(DecisionPending):
        _attempt_assembly(session)
    assert session.data['pending'] == pending and 'one Region' in session.error
    assert encode(board_copy(session.state)) == encode(initial)

    path = tmp_path / 'assembly.json'
    save_game(session.state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = _assembly_session(restored, meta, log)
    assert resumed.data['pending'] == pending
    accepted = _ambush_plan(BATTLE_REGIONS[:1])
    resumed.import_inbox({'decision_id': pending['id'], 'response': accepted})
    result = _attempt_assembly(resumed)
    assert result['executed']
    resumed.finish()
    assert count_pieces(restored, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 6
    assert count_pieces(restored, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == 5
    assert restored['resources'][rc.AEDUI] == 10
    _check_board(restored)

    initial['decision_agent'] = lambda board, faction, req: (
        decode(log[-1]['assistant_response']) if req['kind'] == 'free_action'
        else _stand(board, faction, req))
    assert _play_assembly(initial) == result
    assert encode(board_copy(initial)) == encode(board_copy(restored))


def _enlist_board(scenario=rc.SCENARIO_ARIOVISTUS, warbands=None):
    state = _board(scenario)
    leader = rc.BODUOGNATUS if scenario in rc.ARIOVISTUS_SCENARIOS else rc.AMBIORIX
    place_piece(state, ORIGIN, rc.BELGAE, rc.LEADER, leader_name=leader)
    place_piece(state, ORIGIN, rc.BELGAE, rc.WARBAND)
    for visibility, count in (warbands or {rc.HIDDEN: 4}).items():
        place_piece(state, ORIGIN, rc.GERMANS, rc.WARBAND, count, piece_state=visibility)
    _check_board(state)
    return state


def _split_groups():
    return [{'destination': region, 'warbands': {rc.HIDDEN: 2}} for region in DESTINATIONS]


def _enlist_plan(groups=None):
    return {'type': 'german_march', 'origin': ORIGIN,
            'groups': _split_groups() if groups is None else groups}


def _raid_and_enlist(state, enlist):
    return execute_decision(state, rc.BELGAE, {'action': ACTION_COMMAND_SA, 'player_action': {
        'command': rc.CMD_RAID, 'sa': rc.SA_ENLIST, 'sa_timing': 'after', 'sa_regions': [ORIGIN],
        'details': {'raid_plan': [{'region': ORIGIN, 'target': None}], 'enlist': enlist},
    }})


@pytest.mark.parametrize('scenario', rc.ARIOVISTUS_SCENARIOS)
def test_terminal_can_collect_and_execute_two_enlist_march_groups(scenario):
    state = _enlist_board(scenario)
    original = encode(state)
    output = StringIO()
    terminal_input = StringIO('Sugambri\nNervii\n3\nTreveri\n1\n')
    regions, details = _collect_enlist_details(state, rc.BELGAE, terminal_input, output, _sub='german_march')
    assert regions == [ORIGIN] and encode(state) == original
    assert details['enlist']['groups'] == [
        {'destination': region, 'warbands': {rc.HIDDEN: 2, rc.REVEALED: 0, rc.SCOUTED: 0}}
        for region in DESTINATIONS]
    assert not terminal_input.read() and output.getvalue().count('March Germans TO:') == 2

    result = _raid_and_enlist(state, details['enlist'])

    assert result['executed'] and result['sa_execution']['executed']
    moves = result['sa_execution']['details']['marches']
    assert [move['final_region'] for move in moves] == list(DESTINATIONS)
    assert [count_pieces(state, region, rc.GERMANS, rc.WARBAND) for region in DESTINATIONS] == [2, 2]
    assert not count_pieces(state, ORIGIN, rc.GERMANS, rc.WARBAND)
    _check_board(state)


def test_terminal_base_enlist_keeps_single_destination():
    state = _enlist_board(rc.SCENARIO_GREAT_REVOLT)
    source = StringIO('Sugambri\nNervii\n3\n')
    output = StringIO()
    regions, details = _collect_enlist_details(state, rc.BELGAE, source, output, _sub='german_march')
    assert regions == [ORIGIN] and not source.read()
    assert details['enlist'] == {'type': 'german_march', 'origin': ORIGIN,
                                 'destination': DESTINATIONS[0],
                                 'warbands': {rc.HIDDEN: 2, rc.REVEALED: 0, rc.SCOUTED: 0}}

    result = _raid_and_enlist(state, details['enlist'])

    assert result['sa_execution']['details']['march']['final_region'] == DESTINATIONS[0]
    assert count_pieces(state, ORIGIN, rc.GERMANS, rc.WARBAND) == 2
    _check_board(state)


def test_grouped_enlist_saved_event_grant_replays(tmp_path):
    initial = _enlist_board()
    place_piece(initial, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    session = _assembly_session(deepcopy(initial), {'seat': rc.BELGAE}, [])
    with pytest.raises(DecisionPending):
        _attempt_assembly(session, rc.BELGAE)
    pending = deepcopy(session.data['pending'])
    assert encode(board_copy(session.state)) == encode(initial)

    path = tmp_path / 'enlist.json'
    save_game(session.state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = _assembly_session(restored, meta, log)
    assert resumed.data['pending'] == pending
    response = {'command': rc.CMD_RAID, 'sa': rc.SA_ENLIST, 'sa_regions': [ORIGIN],
                'details': {'raid_plan': [{'region': rc.CARNUTES, 'target': None}],
                            'enlist': _enlist_plan()}}
    resumed.import_inbox({'decision_id': pending['id'], 'response': response})
    result = _attempt_assembly(resumed, rc.BELGAE)
    assert result['executed'] and result['free_actions'][0]['result']['sa_execution']['executed']
    resumed.finish()
    assert [count_pieces(restored, region, rc.GERMANS, rc.WARBAND) for region in DESTINATIONS] == [2, 2]
    _check_board(restored)

    initial['decision_agent'] = lambda board, faction, req: (
        decode(log[-1]['assistant_response']) if req['kind'] == 'free_action' else None)
    assert _play_assembly(initial, rc.BELGAE) == result
    assert encode(board_copy(initial)) == encode(board_copy(restored))


def test_enlist_groups_move_exact_visibility_and_can_hide_in_place():
    state = _enlist_board(warbands={rc.HIDDEN: 2, rc.REVEALED: 2, rc.SCOUTED: 2})
    place_piece(state, ORIGIN, rc.GERMANS, rc.LEADER, leader_name=rc.SUCCESSOR)
    request = {'request_type': 'event_sa', 'allowed_regions': [ORIGIN],
               'allowed_sas': [rc.SA_ENLIST], 'with_sa': True}
    groups = [{'destination': DESTINATIONS[0], 'warbands': {rc.REVEALED: 1, rc.SCOUTED: 1}},
              {'destination': DESTINATIONS[1], 'warbands': {rc.HIDDEN: 1}},
              {'destination': None, 'warbands': {rc.REVEALED: 1}}]
    action = {'command': None, 'sa': rc.SA_ENLIST, 'details': {'enlist': _enlist_plan(groups)}}
    before = encode(state)
    resources = dict(state['resources'])
    assert validate_free_action_response(state, rc.BELGAE, request, action) is None
    assert encode(state) == before

    result = execute_free_action_plan(state, rc.BELGAE, request, action)

    assert result['executed'] and result['details']['flipped'] == {
        'flipped_to_hidden': 2, 'scouted_to_revealed': 1}
    visibility = (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)
    counts = {region: tuple(count_pieces_by_state(state, region, rc.GERMANS, rc.WARBAND, ps)
                            for ps in visibility) for region in (ORIGIN, *DESTINATIONS)}
    assert counts == {ORIGIN: (2, 0, 1), DESTINATIONS[0]: (1, 1, 0), DESTINATIONS[1]: (1, 0, 0)}
    assert state['resources'] == resources and count_pieces(state, ORIGIN, rc.GERMANS, rc.LEADER) == 1
    _check_board(state)


@pytest.mark.parametrize('problem', ['too_many', 'not_adjacent', 'mixed_schema', 'extra_origin', 'boolean', 'base', 'frost'])
def test_invalid_grouped_enlist_is_refused_before_accepting_turn(problem):
    state = _enlist_board(rc.SCENARIO_GREAT_REVOLT if problem == 'base' else rc.SCENARIO_ARIOVISTUS)
    plan = _enlist_plan()
    if problem == 'too_many':
        plan['groups'][0]['warbands'][rc.HIDDEN] = 3
    elif problem == 'not_adjacent':
        plan['groups'][1]['destination'] = rc.PROVINCIA
    elif problem == 'mixed_schema':
        plan['destination'] = DESTINATIONS[0]
    elif problem == 'extra_origin':
        plan['groups'][1]['origin'] = rc.UBII
    elif problem == 'boolean':
        plan['groups'][0]['warbands'][rc.HIDDEN] = True
    elif problem == 'frost':
        state['next_card'] = rc.WINTER_CARD
    action = {'command': rc.CMD_RAID, 'sa': rc.SA_ENLIST, 'details': {
        'raid_plan': [{'region': ORIGIN, 'target': None}], 'enlist': plan,
    }}
    request = {'kind': 'turn', 'faction': rc.BELGAE, 'options': [ACTION_COMMAND_SA]}
    before = encode(state)

    with pytest.raises(ValueError, match='Enlist'):
        validate_response(state, request, {'action': ACTION_COMMAND_SA, 'player_action': action})
    assert encode(state) == before


def test_enlist_cannot_allocate_same_visibility_twice():
    state = _enlist_board(warbands={rc.HIDDEN: 2, rc.REVEALED: 2})
    before = encode(state)

    with pytest.raises(CommandError, match='Warbands are not present'):
        execute_free_enlist(state, _enlist_plan())

    assert encode(state) == before


def test_enlist_group_failure_restores_the_completed_first_group(monkeypatch):
    from fs_bot.commands import march

    state = _enlist_board()
    before = encode(state)
    move = march.march_group

    def interrupted(board, faction, origin, route, group, **kwargs):
        if route == [DESTINATIONS[1]]:
            assert count_pieces(board, DESTINATIONS[0], rc.GERMANS, rc.WARBAND) == 2
            raise CommandError('second group interrupted')
        return move(board, faction, origin, route, group, **kwargs)

    monkeypatch.setattr(march, 'march_group', interrupted)
    with pytest.raises(CommandError, match='second group interrupted'):
        execute_free_enlist(state, _enlist_plan())
    assert encode(state) == before
