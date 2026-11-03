"""A5, §5.1/5.1.1 and A1.3.1: owners evacuate exact pieces to legal Homes."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, get_available, place_piece,
)
from fs_bot.cards.card_effects import execute_event as card_event
from fs_bot.cards.gallia_evacuation import (
    default_response, destinations, home_regions, pieces, request_for, resolve,
    resolve_owner, validate_response,
)
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.free_actions import collect_free_action
from fs_bot.engine.execute import _execute_event
from fs_bot.engine.free_actions import validate_free_action_response
from fs_bot.engine.game_engine import _action_transaction
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def board(seed=19):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=seed)
    state['current_card'], state['next_card'] = 'A5', 'A67'
    state['non_player_factions'] = set()
    return state


def event(state, executor=rc.ROMANS):
    return _execute_event(state, executor, {'command': 'Event', 'details': {
        'card_id': 'A5', 'text_preference': rc.EVENT_UNSHADED}}, human=True)


def allocation(piece_type, destination, count=1, *, visibility=None, tribe=None,
               source_tribe=None):
    suffix = visibility or source_tribe
    result = {'piece_id': f'{piece_type}:{suffix}' if suffix else piece_type,
              'destination': destination, 'count': count}
    if tribe is not None:
        result['tribe'] = tribe
    return result


def ally(state, region, owner, tribe, piece_type=rc.ALLY):
    place_piece(state, region, owner, piece_type)
    state['tribes'][tribe]['allied_faction'] = owner


def plan(*entries):
    return {'allocations': list(entries)}


def test_owner_can_split_visibility_remove_some_and_keep_roman_garrison():
    state = board()
    place_piece(state, rc.CISALPINA, rc.BELGAE, rc.WARBAND, 3)
    place_piece(state, rc.CISALPINA, rc.BELGAE, rc.WARBAND, 2, piece_state=rc.SCOUTED)
    place_piece(state, rc.CISALPINA, rc.BELGAE, rc.WARBAND, piece_state=rc.REVEALED)
    place_piece(state, rc.CISALPINA, rc.ROMANS, rc.AUXILIA, piece_state=rc.REVEALED)
    response = plan(
        allocation(rc.WARBAND, rc.MORINI, 2, visibility=rc.HIDDEN),
        allocation(rc.WARBAND, None, visibility=rc.HIDDEN),
        allocation(rc.WARBAND, rc.NERVII, 2, visibility=rc.SCOUTED),
        allocation(rc.WARBAND, rc.ATREBATES, visibility=rc.REVEALED))
    requests = []
    def agent(st, owner, request):
        if request['kind'] == 'free_action':
            requests.append((owner, deepcopy(request)))
            return response
    state['decision_agent'] = agent
    before = get_available(state, rc.BELGAE, rc.WARBAND)
    assert event(state)['executed']
    assert [owner for owner, _ in requests] == [rc.BELGAE]
    assert requests[0][1]['acting_faction'] == rc.BELGAE
    assert count_pieces(state, rc.CISALPINA, rc.BELGAE) == 0
    assert count_pieces_by_state(state, rc.MORINI, rc.BELGAE, rc.WARBAND, rc.HIDDEN) == 2
    assert count_pieces_by_state(state, rc.NERVII, rc.BELGAE, rc.WARBAND, rc.SCOUTED) == 2
    assert count_pieces_by_state(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, rc.REVEALED) == 1
    assert get_available(state, rc.BELGAE, rc.WARBAND) == before + 1
    assert count_pieces_by_state(state, rc.CISALPINA, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 3
    assert count_pieces_by_state(state, rc.CISALPINA, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 1
    assert validate_state(state) == []


def test_german_settlement_homes_and_exact_ally_metadata_and_leader_move():
    state = board()
    place_piece(state, rc.CISALPINA, rc.GERMANS, rc.SETTLEMENT)
    place_piece(state, rc.SEQUANI, rc.GERMANS, rc.SETTLEMENT)
    place_piece(state, rc.CISALPINA, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    ally(state, rc.CISALPINA, rc.GERMANS, rc.TRIBE_NORI)
    assert rc.SEQUANI in home_regions(state, rc.GERMANS)
    assert rc.CISALPINA not in home_regions(state, rc.GERMANS)
    response = plan(
        allocation(rc.SETTLEMENT, rc.UBII),
        allocation(rc.ALLY, rc.SEQUANI, source_tribe=rc.TRIBE_NORI, tribe=rc.TRIBE_HELVETII),
        allocation(rc.LEADER, rc.SEQUANI))
    state['decision_agent'] = lambda *args: response
    assert event(state)['executed']
    assert count_pieces(state, rc.CISALPINA, rc.GERMANS) == 0
    assert state['tribes'][rc.TRIBE_NORI]['allied_faction'] is None
    assert state['tribes'][rc.TRIBE_HELVETII]['allied_faction'] == rc.GERMANS
    assert state['spaces'][rc.SEQUANI]['pieces'][rc.GERMANS][rc.LEADER] == rc.ARIOVISTUS_LEADER
    assert count_pieces(state, rc.UBII, rc.GERMANS, rc.SETTLEMENT) == 1
    assert validate_state(state) == []


def test_removing_diviciacus_uses_removed_pool_and_ally_removal_clears_exact_tribe():
    state = board()
    place_piece(state, rc.CISALPINA, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    state['diviciacus_in_play'] = True
    ally(state, rc.CISALPINA, rc.AEDUI, rc.TRIBE_NORI)
    state['decision_agent'] = lambda *args: plan(
        allocation(rc.LEADER, None), allocation(rc.ALLY, None, source_tribe=rc.TRIBE_NORI))
    assert event(state)['executed']
    assert state['removed_pieces'][rc.AEDUI][rc.LEADER] == 1
    assert not state['diviciacus_in_play']
    assert state['tribes'][rc.TRIBE_NORI]['allied_faction'] is None
    assert validate_state(state) == []


@pytest.mark.parametrize('bad', [
    plan(), plan(allocation(rc.WARBAND, rc.NERVII, 3, visibility=rc.HIDDEN)),
    plan(allocation(rc.WARBAND, rc.NERVII, True, visibility=rc.HIDDEN)),
    plan(allocation(rc.WARBAND, rc.CISALPINA, 2, visibility=rc.HIDDEN)),
    plan(allocation(rc.WARBAND, rc.UBII, 2, visibility=rc.HIDDEN)),
    plan(allocation(rc.WARBAND, rc.NERVII, 2, visibility=rc.SCOUTED)),
    {'decline': True}, {'use_default': 1}, {'acting_faction': rc.GERMANS},
])
def test_invalid_response_is_atomic_and_does_not_consume_rng(bad):
    state = board()
    place_piece(state, rc.CISALPINA, rc.BELGAE, rc.WARBAND, 2)
    before = encode(board_copy(state))
    request = request_for(state, rc.BELGAE)
    assert validate_free_action_response(state, rc.BELGAE, request, bad)
    assert encode(board_copy(state)) == before
    state['decision_agent'] = lambda *args: bad
    assert not event(state)['executed']
    state.pop('event_params', None); state.pop('executing_faction', None)
    assert encode(board_copy(state)) == before


def test_structure_slots_reject_restricted_occupied_dispersed_and_duplicate_settlement():
    state = board()
    ally(state, rc.CISALPINA, rc.GERMANS, rc.TRIBE_NORI)
    for region in (rc.AEDUI_REGION, rc.ARVERNI_REGION, rc.SEQUANI):
        place_piece(state, region, rc.GERMANS, rc.SETTLEMENT)
    place_piece(state, rc.CISALPINA, rc.GERMANS, rc.SETTLEMENT)
    state['tribes'][rc.TRIBE_HELVETII]['status'] = rc.DISPERSED
    ally(state, rc.SEQUANI, rc.ARVERNI, rc.TRIBE_SEQUANI)
    for destination, tribe in (
            (rc.AEDUI_REGION, rc.TRIBE_AEDUI),
            (rc.ARVERNI_REGION, rc.TRIBE_ARVERNI),
            (rc.SEQUANI, rc.TRIBE_HELVETII),
            (rc.SEQUANI, rc.TRIBE_SEQUANI)):
        with pytest.raises(ValueError):
            validate_response(state, rc.GERMANS, plan(
                allocation(rc.ALLY, destination, source_tribe=rc.TRIBE_NORI, tribe=tribe),
                allocation(rc.SETTLEMENT, None)))
    with pytest.raises(ValueError):
        validate_response(state, rc.GERMANS, plan(
            allocation(rc.ALLY, None, source_tribe=rc.TRIBE_NORI),
            allocation(rc.SETTLEMENT, rc.SEQUANI)))


def test_invalid_legacy_cisalpina_citadel_does_not_overwrite_existing_tribes():
    state = board()
    # No legal Cisalpina Citadel exists (there is no City). This tests only
    # conservative invalid-save containment, not a ruling about legal Events
    # that explicitly move/replace Citadels elsewhere on the map.
    place_piece(state, rc.CISALPINA, rc.AEDUI, rc.CITADEL)
    entry = pieces(state, rc.AEDUI)[0]
    slot = next(slot for slot in destinations(state, rc.AEDUI, entry)
                if slot['tribe'] in rc.TRIBE_TO_CITY)
    ally(state, slot['destination'], rc.AEDUI, slot['tribe'])
    before = encode(board_copy(state))
    for target in (slot, {'destination': rc.NERVII, 'tribe': rc.TRIBE_NERVII}):
        with pytest.raises(ValueError):
            validate_response(state, rc.AEDUI, plan(
                {'piece_id': entry['id'], 'count': 1, **target}))
    assert encode(board_copy(state)) == before


def test_default_keeps_leader_escort_preserves_visibility_and_uses_live_seed_only():
    state = board()
    place_piece(state, rc.CISALPINA, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND, 2)
    place_piece(state, rc.CISALPINA, rc.BELGAE, rc.WARBAND, 6, piece_state=rc.SCOUTED)
    before = encode(board_copy(state))
    response = default_response(deepcopy(state), rc.BELGAE)
    assert encode(board_copy(state)) == before
    assert response == default_response(deepcopy(state), rc.BELGAE)
    state['decision_agent'] = lambda *args: response
    assert event(state)['executed']
    assert state['spaces'][rc.MORINI]['pieces'][rc.BELGAE][rc.LEADER] == rc.AMBIORIX
    assert count_pieces(state, rc.MORINI, rc.BELGAE, rc.WARBAND) >= 4
    assert sum(count_pieces_by_state(state, region, rc.BELGAE, rc.WARBAND, rc.SCOUTED)
               for region in state['spaces']) == 6
    assert validate_state(state) == []


def contested_board():
    state = board()
    # Card 71 legally adds a second Tribe in Cisalpina for another owner.
    state['executing_faction'] = rc.BELGAE
    state['event_params'] = {'region': rc.CISALPINA}
    card_event(state, 71)
    state.pop('event_params'); state.pop('executing_faction')
    colony = next(tribe for tribe, info in state['tribes'].items()
                  if info.get('region') == rc.CISALPINA)
    ally(state, rc.CISALPINA, rc.GERMANS, rc.TRIBE_NORI)
    place_piece(state, rc.MORINI, rc.GERMANS, rc.SETTLEMENT)
    return state, colony


@pytest.mark.parametrize('first', [rc.BELGAE, rc.GERMANS])
def test_executor_orders_contesting_owners_who_then_choose_their_own_pieces(first):
    state, colony = contested_board()
    order = [first, rc.GERMANS if first == rc.BELGAE else rc.BELGAE]
    seen = []
    def agent(st, owner, request):
        if request['kind'] != 'free_action':
            return None
        seen.append((owner, request['request_type']))
        if request['request_type'] == 'gallia_evacuation_order':
            return {'owner_order': order}
        entry = request['pieces'][0]
        if owner == first:
            target = {'destination': rc.MORINI, 'tribe': rc.TRIBE_MORINI}
        else:
            assert {'destination': rc.MORINI, 'tribe': rc.TRIBE_MORINI} not in entry['destinations']
            target = {'destination': None}
        return plan({'piece_id': entry['id'], 'count': 1, **target})
    state['decision_agent'] = agent
    assert event(state, rc.AEDUI)['executed']
    assert seen == [(rc.AEDUI, 'gallia_evacuation_order'),
                    (order[0], 'gallia_evacuation'), (order[1], 'gallia_evacuation')]
    assert state['tribes'][rc.TRIBE_MORINI]['allied_faction'] == first
    assert state['tribes'][colony]['allied_faction'] is None
    assert state['tribes'][rc.TRIBE_NORI]['allied_faction'] is None
    assert validate_state(state) == []


def test_ario_arverni_evacuation_is_automatic_and_not_a_march():
    state = board()
    place_piece(state, rc.CISALPINA, rc.ARVERNI, rc.WARBAND, 2, piece_state=rc.REVEALED)
    requests = []
    state['decision_agent'] = lambda st, faction, request: requests.append(request)
    assert event(state)['executed']
    assert not [request for request in requests if request['kind'] == 'free_action']
    assert sum(count_pieces_by_state(state, region, rc.ARVERNI, rc.WARBAND, rc.REVEALED)
               for region in rc.ARVERNI_HOME_REGIONS_ARIOVISTUS) == 2
    assert validate_state(state) == []


def session(state, meta=None, log=None):
    view = HumanTurnDisplay(StringIO())
    view.remember(state, [rc.GERMANS])
    ses = SeatSession(state, meta or {'seat': rc.GERMANS}, [] if log is None else log, view)
    def agent(st, faction, request):
        if request.get('request_type') == 'gallia_evacuation_order':
            return {'owner_order': [rc.BELGAE, rc.GERMANS]}
        return ses.reactive(st, faction, request)
    state['decision_agent'] = agent
    return ses


def run(ses):
    def driver(*args):
        pass
    driver.transaction_checkpoint, driver.transaction_restore = ses.checkpoint, ses.restore
    with _action_transaction(ses.state, driver):
        return event(ses.state)


def test_pending_second_owner_invalid_save_load_and_exact_replay(tmp_path):
    state, _ = contested_board()
    ses = session(state)
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending):
        run(ses)
    pending = deepcopy(ses.data['pending'])
    request = decode(pending['request'])
    shown = decode(pending['board'])
    assert request['faction'] == rc.GERMANS
    assert request['request_type'] == 'gallia_evacuation'
    assert count_pieces(shown, rc.CISALPINA, rc.BELGAE) == 0
    assert count_pieces(shown, rc.CISALPINA, rc.GERMANS) == 1
    assert count_pieces(shown, rc.CISALPINA, rc.ROMANS, rc.AUXILIA) == 3
    assert encode(board_copy(state)) == before
    ses.import_inbox({'decision_id': pending['id'], 'response': plan()})
    with pytest.raises(DecisionPending):
        run(ses)
    assert ses.data['pending']['id'] == pending['id'] and ses.error
    assert encode(board_copy(state)) == before
    response = plan(allocation(rc.ALLY, rc.UBII, source_tribe=rc.TRIBE_NORI,
                               tribe=rc.TRIBE_SUEBI_SOUTH))
    ses.import_inbox({'decision_id': pending['id'], 'response': response})
    save_game(state, tmp_path / 'gallia.json', meta=ses.meta, log=ses.log)
    restored, meta, log = load_game(tmp_path / 'gallia.json')
    resumed = session(restored, meta, log)
    result = run(resumed)
    resumed.finish()
    assert result['executed'] and validate_state(restored) == []
    replay, _ = contested_board()
    def agent(st, faction, request):
        if request.get('request_type') == 'gallia_evacuation_order':
            return {'owner_order': [rc.BELGAE, rc.GERMANS]}
        if faction == rc.GERMANS and request['kind'] == 'free_action':
            return decode(log[0]['assistant_response'])
    replay['decision_agent'] = agent
    assert event(replay) == result
    assert encode(board_copy(replay)) == encode(board_copy(restored))
    shown_text = resumed.display.stdout.getvalue()
    # The common human decision view supplies complete card/context/deltas.
    assert 'Gallia Togata' in shown_text and 'Auxilia' in shown_text


@pytest.mark.parametrize('response', [
    {'owner_order': [rc.GERMANS, rc.GERMANS]}, {'owner_order': [rc.GERMANS]},
    {'owner_order': [rc.GERMANS, rc.ROMANS]}, {'owner_order': [rc.GERMANS, []]},
    {'owner_order': [rc.GERMANS, rc.BELGAE], 'acting_faction': rc.GERMANS},
    {'decline': True},
])
def test_invalid_owner_order_is_rejected_without_mutation(response):
    state, _ = contested_board()
    before = encode(board_copy(state))
    state['decision_agent'] = lambda *args: response
    assert not event(state)['executed']
    state.pop('event_params', None); state.pop('executing_faction', None)
    assert encode(board_copy(state)) == before


def test_terminal_board_aliases_and_eof_do_not_mutate_preview_or_rng():
    state = board()
    place_piece(state, rc.CISALPINA, rc.BELGAE, rc.WARBAND, piece_state=rc.SCOUTED)
    request = request_for(state, rc.BELGAE)
    before = encode(board_copy(state))
    out = StringIO()
    response = collect_free_action(state, rc.BELGAE, request,
                                   StringIO('board\n1\nb\n1\n'), out)
    validate_response(state, rc.BELGAE, response)
    assert response == plan(allocation(rc.WARBAND, rc.ATREBATES, visibility=rc.SCOUTED))
    assert 'Scouted' in out.getvalue() and rc.CISALPINA in out.getvalue()
    assert encode(board_copy(state)) == before
    with pytest.raises(EOFError):
        collect_free_action(state, rc.BELGAE, request, StringIO('1\n'), StringIO())
    assert encode(board_copy(state)) == before
    assert collect_free_action(state, rc.BELGAE, request, StringIO('2\n'), StringIO()) == {
        'use_default': True}


def test_terminal_selects_order_and_avoids_reusing_planned_tribe_slots():
    state, colony = contested_board()
    request = {'kind': 'free_action', 'request_type': 'gallia_evacuation_order',
               'owners': [rc.BELGAE, rc.GERMANS], 'allow_decline': False}
    assert collect_free_action(state, rc.AEDUI, request, StringIO('1\n2\n1\n'), StringIO()) == {
        'owner_order': [rc.GERMANS, rc.BELGAE]}
    # One owner has both the ordinary Nori disc and the additional Colony.
    from fs_bot.board.pieces import remove_piece, clear_allied_tribe
    remove_piece(state, rc.CISALPINA, rc.BELGAE, rc.ALLY)
    clear_allied_tribe(state, rc.CISALPINA, rc.BELGAE, rc.ALLY, tribe=colony)
    ally(state, rc.CISALPINA, rc.GERMANS, colony)
    request = request_for(state, rc.GERMANS)
    response = collect_free_action(state, rc.GERMANS, request,
                                   StringIO('1\n1\n1\n'), StringIO())
    targets = {(entry['destination'], entry['tribe']) for entry in response['allocations']}
    assert len(targets) == 2
    validate_response(state, rc.GERMANS, response)


def test_default_owner_order_benefits_executor_first_and_removal_is_only_if_forced():
    state, _ = contested_board()
    # All German Home Tribes occupied: A5 must remove the stranded Nori Ally.
    for region in rc.GERMAN_HOME_REGIONS_BASE:
        for tribe in list(state['tribes']):
            if rc.TRIBE_TO_REGION.get(tribe) == region:
                ally(state, region, rc.GERMANS, tribe)
    for tribe in (rc.TRIBE_MORINI, rc.TRIBE_MENAPII):
        ally(state, rc.MORINI, rc.BELGAE, tribe)
    before = get_available(state, rc.GERMANS, rc.ALLY)
    result = resolve(state, rc.GERMANS)[0]
    assert result['owner_order'][0] == rc.GERMANS
    assert get_available(state, rc.GERMANS, rc.ALLY) == before + 1
    assert len(result['removed']) == 1 and result['removed'][0]['faction'] == rc.GERMANS
    assert validate_state(state) == []


def test_allocation_preview_preserves_legal_choice_rng_and_available_counts():
    state = board()
    place_piece(state, rc.CISALPINA, rc.GERMANS, rc.WARBAND, 2)
    response = plan(allocation(rc.WARBAND, rc.UBII, 2, visibility=rc.HIDDEN))
    before = encode(board_copy(state))
    validate_response(state, rc.GERMANS, response)
    assert encode(board_copy(state)) == before
    state['decision_agent'] = lambda *args: response
    available = deepcopy(state['available'])
    resolve_owner(state, rc.GERMANS)
    assert state['available'] == available
    assert state['rng'].getstate() == decode(before)['rng'].getstate()
