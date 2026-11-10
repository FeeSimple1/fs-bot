"""A29/A69 and §5.1: humans select grants without replacing their cohorts."""
from copy import deepcopy
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece
from fs_bot.cards.card_effects import execute_card_A29, execute_card_A69
from fs_bot.cards.harudes_bellovaci import HARUDES, BELLOVACI, RAID_CHOOSER
from fs_bot.cli.free_actions import collect_free_action
from fs_bot.engine.execute import _execute_event, _resolve_free_actions
from fs_bot.engine.free_actions import validate_free_action_response
from fs_bot.state.serialize import encode, decode
from fs_bot.state.state_schema import build_initial_state, validate_state


def board(card='A29', chooser=rc.ROMANS):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=19)
    state['current_card'] = state['current_card_id'] = card
    state['next_card'] = 'A19'
    state['non_player_factions'] = set(rc.FACTIONS) - {chooser}
    return state


def placements(count=4):
    return {'placements': [{'region': rc.TREVERI, 'piece_type': rc.WARBAND,
                             'count': count}]}


def raid(target=None, count=1, region=rc.TREVERI):
    return {'raid_actions': [{'region': region, 'target_faction': target}
                            for _ in range(count)]}


def bellovaci(state):
    place_piece(state, rc.ATREBATES, rc.BELGAE, rc.ALLY)
    state['tribes'][rc.TRIBE_BELLOVACI]['allied_faction'] = rc.BELGAE
    place_piece(state, rc.NERVII, rc.BELGAE, rc.LEADER, leader_name=rc.BODUOGNATUS)


def play(state, chooser, params=None):
    return _execute_event(state, chooser, {'command': rc.FIRST_DID_EVENT,
        'details': {'card_id': state['current_card'],
                    'text_preference': rc.EVENT_SHADED, 'event_params': params or {}}}, human=True)


@pytest.mark.parametrize('chooser', [rc.ROMANS, rc.GERMANS])
def test_harudes_executor_selects_lower_count_and_nonpriority_target(chooser):
    state = board(chooser=chooser)
    place_piece(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, 4)
    for enemy in (rc.ROMANS, rc.BELGAE):
        place_piece(state, rc.TREVERI, enemy, rc.WARBAND if enemy == rc.BELGAE else rc.AUXILIA)
        state['resources'][enemy] = 5
    seen = []
    def agent(current, owner, request):
        if request.get('request_type') == HARUDES:
            seen.append((owner, request))
            return raid(rc.BELGAE)
    state['decision_agent'] = agent
    result = play(state, chooser, placements())
    assert result['executed'], result
    assert [owner for owner, _ in seen] == [chooser]
    assert seen[0][1]['acting_faction'] == rc.GERMANS
    assert seen[0][1]['regions'][rc.TREVERI]['max_raiders'] == 2
    assert state['resources'][rc.BELGAE] == 4
    assert state['resources'][rc.ROMANS] == 5
    assert state['resources'][rc.GERMANS] == 1
    assert count_pieces_by_state(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 7
    assert validate_state(state) == []


def test_harudes_intrinsic_intimidate_follows_executor_not_german_seat():
    state = board()
    place_piece(state, rc.TREVERI, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    place_piece(state, rc.TREVERI, rc.BELGAE, rc.WARBAND, 2)
    seen = []
    def agent(current, owner, request):
        seen.append((owner, request))
        if request.get('request_type') == HARUDES:
            return raid(count=1)
        if request['kind'] == 'raid_intimidate':
            assert request['acting_faction'] == rc.GERMANS
            assert request['raiders'] == request['max_removals'] == 1
            return {'decline': True}
    state['decision_agent'] = agent
    result = play(state, rc.ROMANS, placements())
    assert result['executed'], result
    assert [owner for owner, req in seen if req['kind'] == 'raid_intimidate'] == [rc.ROMANS]
    assert count_pieces(state, rc.TREVERI, rc.BELGAE, rc.WARBAND) == 2
    assert RAID_CHOOSER not in state


def test_np_executor_does_not_hand_raid_to_human_germans():
    state = board(chooser=rc.GERMANS)
    state['event_params'] = placements()
    place_piece(state, rc.TREVERI, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA, 3)
    state['resources'][rc.ROMANS] = 5
    execute_card_A29(state, True)
    seen = []
    def agent(current, owner, request):
        seen.append((owner, request['kind']))
        if owner == rc.GERMANS:
            pytest.fail('The physical German seat does not choose a Roman-executed Event grant')
    state['decision_agent'] = agent
    result = _resolve_free_actions(state, rc.ROMANS)
    assert result[0]['result']['executed']
    assert (rc.ROMANS, 'free_action') in seen and (rc.ROMANS, 'raid_intimidate') in seen


def test_bellovaci_selects_smaller_defender_and_keeps_resident_normal_losses():
    state = board('A69')
    bellovaci(state)
    place_piece(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 4)
    place_piece(state, rc.ATREBATES, rc.GERMANS, rc.WARBAND, 12, piece_state=rc.REVEALED)
    place_piece(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND, 10, piece_state=rc.REVEALED)
    seen = []
    def agent(current, owner, request):
        seen.append((owner, request))
        if request.get('request_type') == BELLOVACI:
            assert request['acting_faction'] == rc.BELGAE
            return {'defender': rc.AEDUI}
    state['decision_agent'] = agent
    result = play(state, rc.ROMANS)
    assert result['executed'], result
    assert result['free_actions'][0]['defender'] == rc.AEDUI
    assert [owner for owner, req in seen if req.get('request_type') == BELLOVACI] == [rc.ROMANS]
    assert all(owner == rc.AEDUI for owner, req in seen if req['kind'] == 'loss_order')
    assert count_pieces(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND) == 2  # 6 new + 4/2 resident
    assert count_pieces(state, rc.ATREBATES, rc.GERMANS, rc.WARBAND) == 12
    assert validate_state(state) == []


def test_bellovaci_counterattack_casualties_stay_with_physical_belgic_owner():
    state = board('A69', chooser=rc.AEDUI)
    bellovaci(state)
    place_piece(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 4)
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, 20, piece_state=rc.REVEALED)
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    owners = []
    def agent(current, owner, request):
        if request.get('request_type') == BELLOVACI:
            assert owner == rc.AEDUI
            return {'defender': rc.ROMANS}
        if request['kind'] == 'loss_order':
            owners.append(owner)
    state['decision_agent'] = agent
    assert play(state, rc.AEDUI)['executed']
    assert set(owners) == {rc.ROMANS, rc.BELGAE}
    assert count_pieces(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND) == 3


@pytest.mark.parametrize('removed,residents', [(0, 0), (3, 0), (5, 0), (6, 0), (6, 4)])
def test_bellovaci_late_removal_cannot_downgrade_grant_to_ordinary_battle(removed, residents):
    from fs_bot.engine.action_windows import scope
    from fs_bot.engine.voluntary_removal import operation
    state = board('A69', chooser=rc.BELGAE)
    bellovaci(state)
    if residents:
        place_piece(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, residents)
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, 12, piece_state=rc.REVEALED)
    class Agent:
        supports_action_windows = True
        did = False
        def __call__(self, current, owner, request):
            if request.get('request_type') == BELLOVACI:
                return {'defender': rc.ROMANS}
            if request['kind'] == 'voluntary_removal':
                if (removed and not self.did
                        and request.get('window', {}).get('stage') == 'battle_command'):
                    selected = next(c for c in request['options']
                                    if c.get('cohort', '').startswith('card_A69_ambush.'))
                    self.did = True
                    removal = operation(selected)
                    removal['count'] = removed
                    return {'operations': [removal]}
                return {'done': True}
    state['decision_agent'] = Agent()
    with scope(state, actor=rc.BELGAE, force=True):
        result = play(state, rc.BELGAE)
    assert result['executed'], result  # placements and chosen removals remain
    battle = result['free_actions'][0]['result']
    assert not battle['errors']
    surviving = 6 - removed
    assert count_pieces(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND) == surviving + residents
    if surviving > 2:
        assert battle['executed'] and battle['battle_sa_executed']
        assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 14 - surviving
        assert count_pieces_by_state(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND,
                                     rc.REVEALED) == surviving
    else:
        assert not battle['executed'] and battle['declined_no_effect']
        assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 14
        assert count_pieces_by_state(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND,
                                     rc.HIDDEN) == surviving + residents
    assert validate_state(state) == []


def test_bellovaci_diviciacus_defense_can_legally_cancel_ambush():
    state = board('A69', chooser=rc.BELGAE)
    state['non_player_factions'] = set()
    bellovaci(state)
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND, 4)
    place_piece(state, rc.ATREBATES, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    owners = []
    def agent(current, owner, request):
        if request.get('request_type') == BELLOVACI:
            return {'defender': rc.ROMANS}
        if request['kind'] == 'agreement':
            if request['request_type'] in ('diviciacus_defense', 'diviciacus'):
                owners.append(owner)
            return True
    state['decision_agent'] = agent
    result = play(state, rc.BELGAE)
    assert result['executed'], result
    battle = result['free_actions'][0]['result']
    assert battle['executed'] and not battle['errors']
    assert not battle['battle_sa_executed']
    assert battle['ambush_blocked_by_diviciacus'] == [rc.ATREBATES]
    assert set(owners) == {rc.ROMANS, rc.AEDUI}
    assert validate_state(state) == []


def grant_state(card):
    state = board(card)
    if card == 'A29':
        place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA)
        state['resources'][rc.ROMANS] = 1
        state['event_params'] = placements(2)
        execute_card_A29(state, True)
        request = {'kind': 'free_action', 'request_type': HARUDES, 'allow_decline': False}
    else:
        bellovaci(state)
        place_piece(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND, 4, piece_state=rc.REVEALED)
        execute_card_A69(state, True)
        request = {'kind': 'free_action', 'request_type': BELLOVACI, 'allow_decline': False}
    return state, request


@pytest.mark.parametrize('bad', [
    raid(count=0), raid(count=3), raid(region=rc.NERVII), raid(rc.GERMANS),
    raid(rc.ROMANS, count=2), {'raid_actions': [None]}, {'raid_actions': 'bad'},
    {'raid_actions': [{'region': rc.TREVERI, 'target_faction': None, 'faction': rc.ROMANS}]},
    {'raid_actions': [{'region': rc.TREVERI, 'target_faction': None, 'count': 2}]},
    dict(raid(), acting_faction=rc.ROMANS), {'decline': True}, {'use_default': 1},
])
def test_invalid_harudes_response_does_not_mutate_board_or_rng(bad):
    state, request = grant_state('A29')
    before = encode(state)
    state['decision_agent'] = lambda *args: pytest.fail('Preview must not consume human input')
    assert validate_free_action_response(state, rc.ROMANS, request, bad)
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before


@pytest.mark.parametrize('bad', [
    {'defender': rc.BELGAE}, {'defender': rc.ROMANS}, {'defender': []},
    {'defender': rc.AEDUI, 'warband_full_loss': True}, {'decline': True},
    {'defender': rc.AEDUI, 'acting_faction': rc.ROMANS},
])
def test_invalid_bellovaci_response_cannot_override_grant(bad):
    state, request = grant_state('A69')
    before = encode(state)
    assert validate_free_action_response(state, rc.ROMANS, request, bad)
    assert encode(state) == before


def test_harudes_ordinary_raid_restrictions_and_card8_limit():
    from fs_bot.cards.capabilities import activate_capability, set_capability_owner
    state, request = grant_state('A29')
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.FORT)
    assert validate_free_action_response(state, rc.ROMANS, request, raid(rc.ROMANS))
    activate_capability(state, 8, rc.EVENT_SHADED)
    set_capability_owner(state, 8, rc.GERMANS)
    assert validate_free_action_response(state, rc.ROMANS, request, raid(rc.ROMANS)) is None
    # The capability increases the intrinsic limit, never the physical cohort.
    assert validate_free_action_response(state, rc.ROMANS, request, raid(count=3))
    state['event_modifiers']['card_A29_raid_cohort'][0]['count'] += 1
    place_piece(state, rc.TREVERI, rc.GERMANS, rc.WARBAND)
    assert validate_free_action_response(state, rc.ROMANS, request, raid(count=3)) is None
    state['markers'].setdefault(rc.TREVERI, set()).add(rc.MARKER_DEVASTATED)
    assert validate_free_action_response(state, rc.ROMANS, request, raid())


@pytest.mark.parametrize('card', ['A29', 'A69'])
def test_invalid_live_callback_rolls_back_full_event_including_placements(card):
    state = board(card)
    if card == 'A69':
        bellovaci(state)
        place_piece(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND)
    before = encode(state)
    state['decision_agent'] = lambda *args: {'acting_faction': rc.GERMANS}
    result = play(state, rc.ROMANS, placements() if card == 'A29' else {})
    assert not result['executed']
    # _execute_event historically restores absent context fields as None.
    expected = decode(before)
    expected['event_params'] = expected['executing_faction'] = None
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == encode(expected)


def test_cli_harudes_count_target_and_board_inspection():
    from fs_bot.cli.menus import set_board_hook
    from fs_bot.cards.harudes_bellovaci import harudes_cohort, harudes_regions
    state, request = grant_state('A29')
    request['regions'] = harudes_regions(state, harudes_cohort(state))
    before = encode(state)
    out, calls = io.StringIO(), []
    set_board_hook(lambda: calls.append('board'))
    try:
        response = collect_free_action(state, rc.ROMANS, request,
            io.StringIO('Plan the action\nboard\n' + rc.TREVERI + '\n1\nGain one Resource\n'), out)
    finally:
        set_board_hook(None)
    assert response == raid()
    assert calls == ['board'] and encode(state) == before
    assert collect_free_action(state, rc.ROMANS, request,
        io.StringIO('Use bot default\n'), out) == {'use_default': True}
    with pytest.raises(EOFError):
        collect_free_action(state, rc.ROMANS, request, io.StringIO(''), out)


def test_cli_bellovaci_selects_any_legal_defender():
    state, request = grant_state('A69')
    request['defenders'] = [rc.AEDUI, rc.GERMANS]
    assert collect_free_action(state, rc.ROMANS, request,
        io.StringIO(rc.AEDUI + '\n'), io.StringIO()) == {'defender': rc.AEDUI}


@pytest.mark.parametrize('card,removed', [('A29', 3), ('A29', 4), ('A69', 2), ('A69', 6)])
def test_grant_request_uses_exact_survivors_after_pregrant_removals(card, removed):
    from fs_bot.engine.action_windows import scope
    actor = rc.GERMANS if card == 'A29' else rc.BELGAE
    region = rc.TREVERI if card == 'A29' else rc.ATREBATES
    cohort = 'card_A29_raid' if card == 'A29' else 'card_A69_ambush'
    grant = 'card_A29_german_raid' if card == 'A29' else 'card_A69_ambush'
    count = 4 if card == 'A29' else 6
    state = board(card, chooser=actor)
    if card == 'A69':
        bellovaci(state)
        place_piece(state, region, rc.ROMANS, rc.AUXILIA, 10, piece_state=rc.REVEALED)
    place_piece(state, region, actor, rc.WARBAND, 4)  # unrelated residents
    params = placements() if card == 'A29' else {}
    params['stage_timing_actions'] = {'grant.' + grant: [{
        'kind': 'voluntary_removal', 'response': {'operations': [{
            'action': 'remove', 'region': region, 'piece_type': rc.WARBAND,
            'piece_state': rc.HIDDEN, 'count': removed, 'cohort': cohort + '.' + region}]}}]}
    requests = []
    def agent(current, owner, request):
        if request['kind'] == 'free_action':
            requests.append(request)
            return raid() if card == 'A29' else {'defender': rc.ROMANS}
    state['decision_agent'] = agent
    with scope(state, actor=actor, force=True):
        result = play(state, actor, params)
    assert result['executed'], result
    assert len(requests) == int(count > removed)
    if card == 'A29':
        if requests:
            assert requests[0]['regions'][region]['max_raiders'] == 1
        assert state['resources'][actor] == int(count > removed)
        assert count_pieces_by_state(state, region, actor, rc.WARBAND, rc.HIDDEN) == 4
    else:
        if requests:
            assert requests[0]['placed_warbands'] == count - removed
        expected_loss = count - removed + 2 if removed < count else 0
        assert count_pieces(state, region, rc.ROMANS, rc.AUXILIA) == 10 - expected_loss
    assert validate_state(state) == []


@pytest.mark.parametrize('card', ['A29', 'A69'])
def test_explicit_default_retains_existing_np_choice_and_rng(card):
    state, _ = grant_state(card)
    default = deepcopy(state)
    state['decision_agent'] = lambda *args: {'use_default': True}
    expected = _resolve_free_actions(default, rc.ROMANS)
    actual = _resolve_free_actions(state, rc.ROMANS)
    assert actual == expected
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == encode(default)


def zero_loss_bellovaci():
    from fs_bot.board.pieces import get_available
    state = board('A69')
    bellovaci(state)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND,
                get_available(state, rc.BELGAE, rc.WARBAND) - 1)
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.FORT)
    execute_card_A69(state, True)
    return state


def test_human_can_select_legal_zero_loss_ambush_but_default_keeps_np_filter():
    state = zero_loss_bellovaci()
    np_state = deepcopy(state)
    seen = []
    def agent(current, owner, request):
        if request.get('request_type') == BELLOVACI:
            seen.append(request)
            return {'defender': rc.ROMANS}
    state['decision_agent'] = agent
    assert _resolve_free_actions(state, rc.ROMANS)[0]['result']['executed']
    assert seen[0]['defenders'] == [rc.ROMANS]
    assert seen[0]['default_available'] is False
    assert count_pieces_by_state(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, rc.REVEALED) == 1
    assert _resolve_free_actions(np_state, rc.ROMANS)[0]['declined_no_effect']
    assert count_pieces_by_state(np_state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, rc.HIDDEN) == 1


def test_unavailable_explicit_default_stays_pending_for_required_bellovaci():
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.tools.seat_session import SeatSession, DecisionPending, board_copy
    state = zero_loss_bellovaci()
    before = encode(state)
    seat = SeatSession(state, {'seat': rc.ROMANS}, [], HumanTurnDisplay(io.StringIO()))
    state['decision_agent'] = seat.reactive
    def resolve():
        def callback(*args):
            pass
        callback.transaction_checkpoint = seat.checkpoint
        callback.transaction_restore = seat.restore
        with _action_transaction(state, callback):
            return _resolve_free_actions(state, rc.ROMANS)
    with pytest.raises(DecisionPending):
        resolve()
    pending = deepcopy(seat.data['pending'])
    seat.import_inbox({'decision_id': pending['id'], 'response': {'use_default': True}})
    with pytest.raises(DecisionPending):
        resolve()
    assert seat.data['pending']['id'] == pending['id']
    assert seat.data['pending']['request'] == pending['request']
    assert encode(board_copy(state)) == before
    seat.import_inbox({'decision_id': pending['id'], 'response': {'defender': rc.ROMANS}})
    assert resolve()[0]['result']['executed']


@pytest.mark.parametrize('card,response', [('A29', raid()), ('A69', {'defender': rc.AEDUI})])
def test_full_event_pending_invalid_save_resume_and_exact_replay(tmp_path, card, response):
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.state.serialize import save_game, load_game
    from fs_bot.tools.seat_session import SeatSession, DecisionPending, board_copy
    state = board(card)
    if card == 'A69':
        bellovaci(state)
        place_piece(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND, 8, piece_state=rc.REVEALED)
    else:
        place_piece(state, rc.TREVERI, rc.GERMANS, rc.LEADER,
                    leader_name=rc.ARIOVISTUS_LEADER)
    before = encode(state)

    def session(current, meta=None, log=None):
        view = HumanTurnDisplay(io.StringIO())
        view.remember(current, [rc.ROMANS])
        seat = SeatSession(current, meta or {'seat': rc.ROMANS}, log or [], view)
        current['decision_agent'] = seat.reactive
        return seat

    def resolve(seat):
        def callback(*args):
            pass
        callback.transaction_checkpoint = seat.checkpoint
        callback.transaction_restore = seat.restore
        with _action_transaction(seat.state, callback):
            return play(seat.state, rc.ROMANS, placements() if card == 'A29' else {})

    seat = session(state)
    with pytest.raises(DecisionPending):
        resolve(seat)
    pending = deepcopy(seat.data['pending'])
    assert decode(pending['request'])['request_type'] == (HARUDES if card == 'A29' else BELLOVACI)
    assert count_pieces(decode(pending['board']), rc.TREVERI if card == 'A29' else rc.ATREBATES,
                        rc.GERMANS if card == 'A29' else rc.BELGAE, rc.WARBAND) == (4 if card == 'A29' else 6)
    assert encode(board_copy(state)) == before
    seat.import_inbox({'decision_id': pending['id'], 'response': {'decline': True}})
    with pytest.raises(DecisionPending):
        resolve(seat)
    assert seat.data['pending']['id'] == pending['id']
    assert seat.data['pending']['request'] == pending['request']
    assert seat.data['pending']['board'] == pending['board']
    assert encode(board_copy(state)) == before
    path = tmp_path / (card + '.json')
    save_game(state, path, meta=seat.meta, log=seat.log)
    restored, meta, log = load_game(path)
    resumed = session(restored, meta, log)
    resumed.import_inbox({'decision_id': pending['id'], 'response': response})
    if card == 'A29':
        # The accepted Raid stays in the journal while its offensive
        # intrinsic choice pauses for the Roman executor. German counters
        # and the actual one-raider credit survive a second save/resume.
        with pytest.raises(DecisionPending):
            resolve(resumed)
        pending = deepcopy(resumed.data['pending'])
        request = decode(pending['request'])
        assert request['kind'] == 'raid_intimidate'
        assert request['faction'] == rc.ROMANS and request['acting_faction'] == rc.GERMANS
        assert request['raiders'] == 1
        assert count_pieces_by_state(decode(pending['board']), rc.TREVERI,
                                    rc.GERMANS, rc.WARBAND, rc.REVEALED) == 1
        assert encode(board_copy(restored)) == before
        path = tmp_path / 'A29-intimidate.json'
        save_game(restored, path, meta=resumed.meta, log=resumed.log)
        restored, meta, log = load_game(path)
        resumed = session(restored, meta, log)
        resumed.import_inbox({'decision_id': pending['id'], 'response': {'decline': True}})
    result = resolve(resumed)
    assert result['executed'], result
    resumed.finish()
    committed = encode(board_copy(restored))
    replay = session(decode(before))
    replay.data['expected'] = [{'id': e['assistant_id'], 'signature': e['assistant_signature']}
                               for e in resumed.log]
    replay.import_inbox([{'decision_id': e['assistant_id'], 'response': decode(e['assistant_response'])}
                        for e in resumed.log])
    assert resolve(replay) == result
    replay.finish()
    assert encode(board_copy(replay.state)) == committed
    assert replay.log == resumed.log
