"""A67 sequencing and ownership: A Card Reference; §§3.2.2, 5.1, 5.1.1, 5.4."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, count_pieces_by_state
from fs_bot.cli.free_actions import collect_free_action
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cards.arduenna import resolve, march_request
from fs_bot.engine.execute import _execute_event
from fs_bot.engine.free_actions import validate_free_action_response
from fs_bot.engine.game_engine import _action_transaction
from fs_bot.state.serialize import encode, decode, save_game, load_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import SeatSession, DecisionPending, board_copy


def state():
    st = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=67)
    st['current_card'], st['next_card'] = 'A67', 'A19'
    st['non_player_factions'] = set()
    place_piece(st, rc.UBII, rc.GERMANS, rc.WARBAND, 4)
    return st


def march(faction=rc.GERMANS, origin=rc.UBII, route=None, count=2):
    route = [rc.TREVERI] if route is None else route
    piece = rc.AUXILIA if faction == rc.ROMANS else rc.WARBAND
    return {'command': rc.CMD_MARCH, 'sa': 'No SA', 'sa_regions': [], 'regions': [origin],
            'details': {'march_plan': {'origins': [origin], 'destinations': [route[-1]],
                'routes': {origin: route}, 'groups': {origin: {piece: count}}}}}


def raid(region=rc.TREVERI):
    return {'command': rc.CMD_RAID, 'sa': 'No SA', 'sa_regions': [], 'regions': [region],
            'details': {'raid_plan': [{'region': region, 'target': None}]}}


def event(st, faction=rc.AEDUI):
    return _execute_event(st, faction, {'command': 'Event', 'details': {
        'card_id': 'A67', 'event_params': {'flip_hidden_regions': [rc.TREVERI]}}}, human=True)


def test_executor_selects_german_beneficiary_then_resulting_board_raid_then_hide():
    st = state()
    place_piece(st, rc.TREVERI, rc.GERMANS, rc.WARBAND, 1, piece_state=rc.SCOUTED)
    owners = []
    def agent(board, owner, request):
        owners.append((owner, request['request_type']))
        if request['request_type'] == 'arduenna_faction':
            assert count_pieces_by_state(board, rc.TREVERI, rc.GERMANS, rc.WARBAND, rc.SCOUTED) == 1
            return {'faction': rc.GERMANS}
        if request['request_type'] == 'arduenna_accept': return {'accept': True}
        if request['request_type'] == 'arduenna_march':
            return march()
        assert owner == rc.GERMANS and request['allowed_regions'] == [rc.NERVII, rc.TREVERI]
        assert count_pieces(board, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 3
        assert count_pieces_by_state(board, rc.TREVERI, rc.GERMANS, rc.WARBAND, rc.SCOUTED) == 1
        return raid()
    st['decision_agent'] = agent
    assert event(st)['executed']
    assert owners == [(rc.AEDUI, 'arduenna_faction'), (rc.GERMANS, 'arduenna_accept'),
                      (rc.GERMANS, 'arduenna_march'), (rc.GERMANS, 'arduenna_command')]
    assert count_pieces(st, rc.UBII, rc.GERMANS, rc.WARBAND) == 2
    assert count_pieces_by_state(st, rc.TREVERI, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 2
    assert count_pieces_by_state(st, rc.TREVERI, rc.GERMANS, rc.WARBAND, rc.REVEALED) == 1
    assert st['resources'][rc.GERMANS] == 1
    assert validate_state(st) == []


@pytest.mark.parametrize('actor', [rc.ROMANS, rc.GERMANS, rc.AEDUI, rc.BELGAE])
def test_beneficiary_may_decline_entire_grant_before_march_or_hide(actor):
    st = state(); piece = rc.AUXILIA if actor == rc.ROMANS else rc.WARBAND
    for region in (rc.NERVII, rc.TREVERI):
        place_piece(st, region, actor, piece, 2, piece_state=rc.REVEALED)
    responses = iter([{'faction': actor}, {'decline': True}])
    before = deepcopy(st['spaces'])
    st['decision_agent'] = lambda *args: next(responses)
    assert event(st)['executed']
    assert st['spaces'] == before


@pytest.mark.parametrize('change', ['wrong_destination', 'extra_destination', 'explicit_moves',
                                  'empty_route', 'too_long', 'stop_crossing', 'sa'])
def test_march_validation_scopes_all_groups_and_routes_without_live_mutation(change):
    st = state(); action = march()
    plan = action['details']['march_plan']
    if change == 'wrong_destination':
        plan['routes'][rc.UBII] = [rc.SEQUANI]
    elif change == 'extra_destination':
        plan['extra_groups'] = [{'origin': rc.UBII, 'route': [rc.SEQUANI], 'group': {rc.WARBAND: 1}}]
    elif change == 'explicit_moves':
        plan['explicit_moves'] = [{'origin': rc.UBII, 'path': [rc.SEQUANI]}]
    elif change == 'empty_route':
        plan['routes'][rc.UBII] = []
    elif change == 'too_long':
        plan['routes'][rc.UBII] = [rc.SEQUANI, rc.MANDUBII, rc.TREVERI]
    elif change == 'stop_crossing':
        # Romans stop after leaving Germania, even with a longer route supplied.
        place_piece(st, rc.UBII, rc.ROMANS, rc.AUXILIA, 2)
        action = march(rc.ROMANS, route=[rc.SEQUANI, rc.TREVERI])
    else:
        action['sa'] = rc.SA_SETTLE
    before = encode(board_copy(st))
    actor = rc.ROMANS if change == 'stop_crossing' else rc.GERMANS
    assert validate_free_action_response(st, actor, march_request(), action)
    assert encode(board_copy(st)) == before


def test_roman_march_harassment_uses_only_carried_force_and_roman_loss_choice():
    st = state()
    place_piece(st, rc.MANDUBII, rc.ROMANS, rc.AUXILIA, 3)
    place_piece(st, rc.MANDUBII, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(st, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, 4, piece_state=rc.REVEALED)
    place_piece(st, rc.ATREBATES, rc.ARVERNI, rc.WARBAND, 3)
    seen = []
    def agent(board, owner, request):
        seen.append((owner, request['kind']))
        if request['kind'] == 'free_action':
            if request['request_type'] == 'arduenna_faction': return {'faction': rc.ROMANS}
            if request['request_type'] == 'arduenna_accept': return {'accept': True}
            if request['request_type'] == 'arduenna_march':
                action = march(rc.ROMANS, rc.MANDUBII, [rc.ATREBATES, rc.NERVII])
                action['details']['march_plan']['groups'][rc.MANDUBII][rc.LEGION] = 1
                return action
            return {'use_default': True}
        if request['kind'] == 'harassment_loss':
            assert owner == rc.ROMANS
            return {'choice': request['options'][0]}
        return None
    st['decision_agent'] = agent
    assert event(st)['executed']
    assert count_pieces(st, rc.NERVII, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(st, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces_by_state(st, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 4
    assert (rc.ROMANS, 'harassment_loss') in seen


def session(st, meta=None, log=None):
    view = HumanTurnDisplay(StringIO()); view.remember(st, [rc.AEDUI, rc.GERMANS])
    ses = SeatSession(st, meta or {'seat': rc.GERMANS}, [] if log is None else log, view)
    st['decision_agent'] = ses.reactive
    return ses


def run(ses):
    def driver(*args): pass
    driver.transaction_checkpoint, driver.transaction_restore = ses.checkpoint, ses.restore
    with _action_transaction(ses.state, driver): return event(ses.state, ses.seat)


def test_three_stages_pending_invalid_save_load_and_replay(tmp_path):
    st = state(); ses = session(st); before = encode(board_copy(st))
    with pytest.raises(DecisionPending): run(ses)
    assert decode(ses.data['pending']['request'])['request_type'] == 'arduenna_faction'
    for response in ({'faction': rc.GERMANS}, {'accept': True}, march()):
        ses.import_inbox({'decision_id': ses.data['pending']['id'], 'response': response})
        with pytest.raises(DecisionPending): run(ses)
        assert encode(board_copy(st)) == before
    pending = deepcopy(ses.data['pending'])
    assert decode(pending['request'])['faction'] == rc.GERMANS
    assert count_pieces(decode(pending['board']), rc.TREVERI, rc.GERMANS, rc.WARBAND) == 2
    ses.import_inbox({'decision_id': pending['id'], 'response': raid(rc.UBII)})
    with pytest.raises(DecisionPending): run(ses)
    assert ses.error and ses.data['pending']['id'] == pending['id']
    assert len(ses.data['journal']) == 3
    assert encode(board_copy(st)) == before
    ses.import_inbox({'decision_id': pending['id'], 'response': raid()})
    save_game(st, tmp_path / 'arduenna.json', meta=ses.meta, log=ses.log)
    restored, meta, log = load_game(tmp_path / 'arduenna.json')
    resumed = session(restored, meta, log); result = run(resumed); resumed.finish()
    replay = state(); entries = iter(log)
    def recorded(board, owner, request):
        if request['kind'] != 'free_action': return None
        entry = next(entries)
        assert decode(entry['assistant_request']) == dict(request, faction=owner)
        return decode(entry['assistant_response'])
    replay['decision_agent'] = recorded
    assert event(replay, rc.GERMANS) == result
    assert encode(board_copy(replay)) == encode(board_copy(restored))
    assert next(entries, None) is None


def test_beneficiary_menu_and_invalid_arverni():
    st = state(); request = {'kind': 'free_action', 'request_type': 'arduenna_faction',
                            'factions': [rc.ROMANS, rc.AEDUI, rc.BELGAE, rc.GERMANS]}
    out = StringIO()
    assert collect_free_action(st, rc.AEDUI, request, StringIO('4\n'), out) == {'faction': rc.GERMANS}
    assert validate_free_action_response(st, rc.AEDUI, request, {'faction': rc.ARVERNI})


def execute_march(st, actor, action):
    from fs_bot.engine.free_actions import execute_free_action_plan
    request = march_request()
    assert validate_free_action_response(st, actor, request, action) is None
    return execute_free_action_plan(st, actor, request, action)


def test_arrivals_cannot_move_again_or_hide_as_later_origin_residents():
    st = state()
    place_piece(st, rc.NERVII, rc.BELGAE, rc.WARBAND, piece_state=rc.SCOUTED)
    place_piece(st, rc.TREVERI, rc.BELGAE, rc.WARBAND)
    action = march(rc.BELGAE, rc.NERVII, [rc.TREVERI], 1)
    plan = action['details']['march_plan']
    plan['origins'].append(rc.TREVERI)
    plan['routes'][rc.TREVERI] = [rc.NERVII]
    plan['destinations'].append(rc.NERVII)
    # Omitted second cap means all ORIGINAL pieces, not arriving pieces.
    execute_march(st, rc.BELGAE, action)
    assert count_pieces_by_state(st, rc.TREVERI, rc.BELGAE, rc.WARBAND, rc.REVEALED) == 1
    assert count_pieces_by_state(st, rc.NERVII, rc.BELGAE, rc.WARBAND, rc.HIDDEN) == 1
    assert count_pieces(st, rc.TREVERI, rc.BELGAE, rc.WARBAND) == 1


@pytest.mark.parametrize('first,second', [(5, 0), (3, 2), (True, 1), (-1, 1)])
def test_overallocated_and_noninteger_initial_groups_are_rejected(first, second):
    st = state(); action = march(count=first)
    if second:
        action['details']['march_plan']['extra_groups'] = [
            {'origin': rc.UBII, 'route': [rc.TREVERI], 'group': {rc.WARBAND: second}}]
    before = encode(board_copy(st))
    assert validate_free_action_response(st, rc.GERMANS, march_request(), action)
    assert encode(board_copy(st)) == before


def test_split_origin_selects_physical_visibility_and_two_target_regions():
    st = state()
    place_piece(st, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 2)
    place_piece(st, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 2, piece_state=rc.SCOUTED)
    action = march(rc.BELGAE, rc.ATREBATES, [rc.NERVII], 2)
    action['details']['march_plan']['extra_groups'] = [
        {'origin': rc.ATREBATES, 'route': [rc.TREVERI], 'group': {rc.WARBAND: 2}}]
    seen = []
    def agent(board, owner, request):
        seen.append(request)
        if request['kind'] == 'march_cohort': return {'counts': {rc.SCOUTED: 2}}
        return None
    st['decision_agent'] = agent
    execute_march(st, rc.BELGAE, action)
    assert len(seen) == 1
    assert count_pieces_by_state(st, rc.NERVII, rc.BELGAE, rc.WARBAND, rc.REVEALED) == 2
    assert count_pieces_by_state(st, rc.TREVERI, rc.BELGAE, rc.WARBAND, rc.HIDDEN) == 2
    assert count_pieces(st, rc.ATREBATES, rc.BELGAE) == 0


def test_split_dropoff_group_is_not_harassed_with_continuing_group():
    st = state()
    place_piece(st, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, 3)
    place_piece(st, rc.NERVII, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(st, rc.NERVII, rc.ARVERNI, rc.WARBAND, 3)
    action = march(rc.ROMANS, rc.ATREBATES, [rc.NERVII], 1)
    action['details']['march_plan']['extra_groups'] = [
        {'origin': rc.ATREBATES, 'route': [rc.NERVII, rc.TREVERI], 'group': {rc.AUXILIA: 2}}]
    execute_march(st, rc.ROMANS, action)
    assert count_pieces(st, rc.NERVII, rc.ROMANS, rc.AUXILIA) == 5
    assert count_pieces(st, rc.TREVERI, rc.ROMANS, rc.AUXILIA) == 1


def test_diviciacus_two_groups_preserve_owner_and_scouted_reservations():
    st = state()
    place_piece(st, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(st, rc.ATREBATES, rc.AEDUI, rc.WARBAND, 2, piece_state=rc.SCOUTED)
    place_piece(st, rc.ATREBATES, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    action = march(rc.ROMANS, rc.ATREBATES, [rc.NERVII], 2)
    action['details']['diviciacus_regions'] = [rc.ATREBATES]
    action['details']['march_plan']['extra_groups'] = [
        {'origin': rc.ATREBATES, 'route': [rc.TREVERI], 'group': {rc.AUXILIA: 2}}]
    owners = []
    def agent(board, actor, request):
        if request['kind'] == 'agreement': return True
        if request['kind'] == 'diviciacus_pieces':
            owners.append(actor)
            return {'counts': {rc.AEDUI: 2}}
        return None
    st['decision_agent'] = agent
    execute_march(st, rc.ROMANS, action)
    assert owners == [rc.ROMANS]
    assert count_pieces_by_state(st, rc.NERVII, rc.AEDUI, rc.WARBAND, rc.REVEALED) == 2
    assert count_pieces(st, rc.TREVERI, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(st, rc.ATREBATES, rc.ROMANS) == 0
    assert validate_state(st) == []


def test_mandatory_stages_reject_declines_and_command_parts_scope_spoof():
    from fs_bot.cards.arduenna import command_request
    st = state()
    assert validate_free_action_response(st, rc.GERMANS, march_request(), {'decline': True})
    assert validate_free_action_response(st, rc.GERMANS, command_request(rc.GERMANS), {'decline': True})
    action = raid(rc.UBII)
    action['details']['command_parts'] = [raid(rc.TREVERI)]
    assert validate_free_action_response(st, rc.GERMANS, command_request(rc.GERMANS), action)


def test_mandatory_default_with_no_npc_march_stays_pending():
    st = state(); ses = session(st); before = encode(board_copy(st))
    ses.import_inbox([{'response': {'faction': rc.GERMANS}}, {'response': {'accept': True}}])
    with pytest.raises(DecisionPending): run(ses)
    pending = deepcopy(ses.data['pending'])
    assert decode(pending['request'])['request_type'] == 'arduenna_march'
    ses.import_inbox({'decision_id': pending['id'], 'response': {'use_default': True}})
    with pytest.raises(DecisionPending): run(ses)
    assert ses.error and ses.data['pending']['id'] == pending['id']
    assert len(ses.data['journal']) == 2
    assert encode(board_copy(st)) == before


def test_impossible_march_still_requires_command_when_legal():
    st = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=67)
    st['current_card'] = 'A67'; st['non_player_factions'] = set()
    from fs_bot.board.pieces import place_piece
    place_piece(st, rc.TREVERI, rc.GERMANS, rc.SETTLEMENT)
    requests = []
    def agent(board, faction, request):
        requests.append(request['request_type'])
        if request['request_type'] == 'arduenna_faction': return {'faction': rc.GERMANS}
        if request['request_type'] == 'arduenna_accept': return {'accept': True}
        from fs_bot.cards.arduenna import command_witness
        return command_witness(board, faction)
    st['decision_agent'] = agent
    result = event(st)
    assert result['executed']
    assert requests == ['arduenna_faction', 'arduenna_accept', 'arduenna_command']
    assert not result['free_actions'][0]['result']['executed']
    assert result['free_actions'][1]['result']['executed']


@pytest.mark.parametrize('stage,cohort,expected_origin,expected_target', [
    ('march_before_plan', None, 0, 1),
    ('march_origin', 'moving_group', 1, 0),
])
def test_preplan_and_selected_group_removals_do_not_substitute_residents(stage, cohort, expected_origin, expected_target):
    from fs_bot.engine import action_windows, voluntary_removal
    from fs_bot.tests.test_march_action_windows import Agent
    st = state()
    place_piece(st, rc.NERVII, rc.ROMANS, rc.AUXILIA, 2)
    action = march(rc.ROMANS, rc.NERVII, [rc.TREVERI], 1)
    def choose(agent, board, faction, request):
        if (not agent.did and request['kind'] == 'voluntary_removal'
                and request.get('window', {}).get('stage') == stage):
            selected = next(c for c in request['options'] if c['region'] == rc.NERVII
                            and c.get('cohort') == cohort and c['piece_type'] == rc.AUXILIA)
            agent.did = True
            return {'operations': [voluntary_removal.operation(selected)]}
    st['decision_agent'] = Agent(choose)
    with action_windows.scope(st, actor=rc.ROMANS, force=True):
        execute_march(st, rc.ROMANS, action)
    assert count_pieces(st, rc.NERVII, rc.ROMANS, rc.AUXILIA) == expected_origin
    assert count_pieces(st, rc.TREVERI, rc.ROMANS, rc.AUXILIA) == expected_target
    assert '_action_window_cohorts' not in st


def test_later_initial_group_removal_preserves_arriving_piece():
    from fs_bot.engine import action_windows, voluntary_removal
    from fs_bot.tests.test_march_action_windows import Agent
    st = state()
    place_piece(st, rc.NERVII, rc.ROMANS, rc.AUXILIA)
    place_piece(st, rc.TREVERI, rc.ROMANS, rc.AUXILIA)
    action = march(rc.ROMANS, rc.NERVII, [rc.TREVERI], 1)
    plan = action['details']['march_plan']
    plan['origins'].append(rc.TREVERI); plan['routes'][rc.TREVERI] = [rc.NERVII]
    plan['destinations'].append(rc.NERVII)
    def choose(agent, board, faction, request):
        if (not agent.did and request['kind'] == 'voluntary_removal'
                and request.get('window', {}).get('stage') == 'march_arrival'):
            selected = next(c for c in request['options'] if c.get('cohort') == 'A67.group.2')
            agent.did = True
            return {'operations': [voluntary_removal.operation(selected)]}
    st['decision_agent'] = Agent(choose)
    with action_windows.scope(st, actor=rc.ROMANS, force=True):
        execute_march(st, rc.ROMANS, action)
    assert count_pieces(st, rc.TREVERI, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(st, rc.NERVII, rc.ROMANS, rc.AUXILIA) == 0
    assert '_action_window_cohorts' not in st


def test_terminal_rejects_unavailable_mandatory_default_before_acceptance():
    st = state(); output = StringIO(); before = encode(board_copy(st))
    with pytest.raises(EOFError):
        collect_free_action(st, rc.GERMANS, march_request(), StringIO('2\n'), output)
    assert 'No non-player March default' in output.getvalue()
    assert encode(board_copy(st)) == before


def test_terminal_march_routes_may_continue_through_one_target_to_the_other():
    from fs_bot.cli.human_plan import _march_routes
    st = state()
    place_piece(st, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, 2)
    st['_cli_required_destinations'] = [rc.NERVII, rc.TREVERI]
    st['_cli_arduenna_transit'] = True
    assert [rc.NERVII, rc.TREVERI] in _march_routes(st, rc.ATREBATES, rc.ROMANS)


@pytest.mark.parametrize('refused_stage', ['arduenna_march', 'arduenna_command'])
def test_refused_diviciacus_loan_reoffers_only_current_mandatory_stage(refused_stage):
    from fs_bot.cards.arduenna import command_witness
    st = state()
    place_piece(st, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(st, rc.ATREBATES, rc.AEDUI, rc.WARBAND)
    place_piece(st, rc.ATREBATES, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    place_piece(st, rc.NERVII, rc.AEDUI, rc.WARBAND)
    attempts = []
    def agent(board, actor, request):
        if request['kind'] == 'agreement': return False
        if request['kind'] != 'free_action': return None
        kind = request['request_type']
        if kind == 'arduenna_faction': return {'faction': rc.ROMANS}
        if kind == 'arduenna_accept': return {'accept': True}
        attempts.append((kind, request['attempt']))
        action = (march(rc.ROMANS, rc.ATREBATES, [rc.NERVII]) if kind == 'arduenna_march'
                  else command_witness(board, actor))
        if kind == refused_stage and request['attempt'] == 1:
            action['details']['diviciacus_regions'] = [rc.ATREBATES if kind == 'arduenna_march' else rc.NERVII]
        if request['attempt'] == 2:
            assert 'refused' in request['previous_error']
            assert count_pieces(board, rc.ATREBATES if kind == 'arduenna_march' else rc.NERVII,
                                rc.ROMANS, rc.AUXILIA) == 2
        return action
    st['decision_agent'] = agent
    result = event(st)
    assert result['executed']
    assert attempts.count((refused_stage, 2)) == 1
    assert attempts.count(('arduenna_march', 1)) == 1
    assert count_pieces(st, rc.NERVII, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(st, rc.ATREBATES, rc.AEDUI, rc.WARBAND) == 1


def test_refused_march_replan_remains_pending_across_save_and_replay(tmp_path):
    from fs_bot.cards.arduenna import command_witness
    st = state()
    place_piece(st, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(st, rc.ATREBATES, rc.AEDUI, rc.WARBAND)
    place_piece(st, rc.ATREBATES, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    origin = deepcopy(st)
    ses = session(st, {'seat': rc.ROMANS})
    def bind(current, controller):
        current['decision_agent'] = lambda board, owner, request: (
            False if request['kind'] == 'agreement' else controller.reactive(board, owner, request))
    bind(st, ses)
    first = march(rc.ROMANS, rc.ATREBATES, [rc.NERVII])
    first['details']['diviciacus_regions'] = [rc.ATREBATES]
    ses.import_inbox([{'response': response} for response in
                      ({'faction': rc.ROMANS}, {'accept': True}, first)])
    with pytest.raises(DecisionPending): run(ses)
    pending = deepcopy(ses.data['pending'])
    request = decode(pending['request'])
    assert request['request_type'] == 'arduenna_march' and request['attempt'] == 2
    assert len(ses.data['journal']) == 3
    save_game(st, tmp_path / 'arduenna-refusal.json', meta=ses.meta, log=ses.log)
    restored, meta, log = load_game(tmp_path / 'arduenna-refusal.json')
    resumed = session(restored, meta, log); bind(restored, resumed)
    resumed.import_inbox({'decision_id': pending['id'], 'response': march(rc.ROMANS, rc.ATREBATES, [rc.NERVII])})
    with pytest.raises(DecisionPending): run(resumed)
    pending = resumed.data['pending']; board = decode(pending['board'])
    resumed.import_inbox({'decision_id': pending['id'], 'response': command_witness(board, rc.ROMANS)})
    result = run(resumed); resumed.finish()
    entries = iter(log)
    def recorded(board, owner, request):
        if request['kind'] == 'agreement': return False
        if request['kind'] != 'free_action': return None
        entry = next(entries)
        assert decode(entry['assistant_request']) == dict(request, faction=owner)
        return decode(entry['assistant_response'])
    origin['decision_agent'] = recorded
    assert event(origin, rc.ROMANS) == result
    assert encode(board_copy(origin)) == encode(board_copy(restored))
    assert next(entries, None) is None


@pytest.mark.parametrize('visibility', [rc.REVEALED, rc.SCOUTED])
def test_german_whole_grant_default_refuses_without_control_battle_plan(visibility):
    st = state(); st['non_player_factions'] = {rc.GERMANS}
    place_piece(st, rc.NERVII, rc.GERMANS, rc.WARBAND, piece_state=visibility)
    before = deepcopy(st['spaces'])
    assert resolve(st, rc.GERMANS) == []
    assert st['spaces'] == before
