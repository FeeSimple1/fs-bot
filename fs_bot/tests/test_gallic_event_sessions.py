"""BE-03: human-owned Event grants survive real durable decision boundaries."""
from copy import deepcopy
from io import StringIO
from types import SimpleNamespace

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cards.card_text import get_card_text
from fs_bot.cli.display import HumanTurnDisplay, format_board
from fs_bot.engine.execute import _execute_event
from fs_bot.engine.game_engine import ACTION_EVENT, _action_transaction, _maybe_execute
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.llm_seat import cmd_board
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def position(card, edition='original'):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=35067)
    state['card_edition'] = edition
    state['current_card'], state['next_card'] = card, 46 if card != 46 else 35
    state['executing_faction'] = rc.ROMANS
    state['event_params'] = None
    state['non_player_factions'] = {rc.ARVERNI, rc.BELGAE}
    state['resources'].update({rc.AEDUI: 10, rc.ROMANS: 10})
    if card in (35, 46):
        assert _ally_tribe(state, rc.TRIBE_AEDUI, rc.AEDUI)
        assert _ally_tribe(state, rc.TRIBE_SEQUANI, rc.AEDUI)
    elif card == 67:
        place_piece(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND, 4)
        place_piece(state, rc.TREVERI, rc.AEDUI, rc.WARBAND,
                    piece_state=rc.SCOUTED)
    else:
        assert _ally_tribe(state, rc.TRIBE_REMI, rc.AEDUI)
        assert _ally_tribe(state, rc.TRIBE_MANDUBII, rc.BELGAE)
        place_piece(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND, 2)
    assert validate_state(state) == []
    return state


def event(state, card, params=None, side=rc.EVENT_SHADED):
    action = {'command': rc.FIRST_DID_EVENT, 'regions': [], 'sa': 'No SA',
              'sa_regions': [], 'details': {'card_id': card,
                  'text_preference': side,
                  'event_params': {} if params is None else params}}
    return _execute_event(state, rc.ROMANS, action, human=True)


def session(state, meta=None, log=None, seat=rc.AEDUI):
    output = StringIO()
    ses = SeatSession(state, meta if meta is not None else {'seat': seat},
                      [] if log is None else log, HumanTurnDisplay(output))
    state['decision_agent'] = ses.reactive
    ses.output = output
    return ses


def run(ses, card, params=None, side=rc.EVENT_SHADED):
    def driver(*args):
        pass
    driver.transaction_checkpoint = ses.checkpoint
    driver.transaction_restore = ses.restore
    with _action_transaction(ses.state, driver):
        return event(ses.state, card, params, side)


def submit(ses, response):
    ses.import_inbox({'decision_id': ses.data['pending']['id'], 'response': response})


def pending(ses, card, params=None, side=rc.EVENT_SHADED):
    with pytest.raises(DecisionPending):
        run(ses, card, params, side)
    return decode(ses.data['pending']['request'])


def assert_retry(ses, card, responses, params=None, side=rc.EVENT_SHADED):
    original = deepcopy(ses.data['pending'])
    journal, log = deepcopy(ses.data['journal']), deepcopy(ses.log)
    before = encode(board_copy(ses.state))
    for response in responses:
        submit(ses, response)
        pending(ses, card, params, side)
        assert ses.error
        for key in ('id', 'request', 'board'):
            assert ses.data['pending'][key] == original[key]
        assert encode(board_copy(ses.state)) == before
        assert ses.data['journal'] == journal and ses.log == log


def assert_replay(initial, final, card, log, result, params=None, side=rc.EVENT_SHADED):
    entries = iter(log)

    def respond(state, faction, request):
        entry = next(entries)
        assert decode(entry['assistant_request']) == dict(request, faction=faction)
        return decode(entry['assistant_response'])

    initial['decision_agent'] = respond
    assert event(initial, card, params, side) == result
    assert next(entries, None) is None
    assert encode(board_copy(initial)) == encode(board_copy(final))
    assert validate_state(final) == []


def rally(*regions):
    return {'command': rc.CMD_RALLY, 'regions': list(regions), 'sa': 'No SA',
            'sa_regions': [], 'details': {'rally_plan': {'steps': [
                {'region': region, 'action': 'place_warbands', 'count': 1}
                for region in regions]}}}


@pytest.mark.parametrize('card', [35, 46, 67])
@pytest.mark.parametrize('default', [False, True])
def test_executor_chooses_beneficiary_and_missing_input_never_delegates(card, default):
    state = position(card)
    state['non_player_factions'].add(rc.AEDUI)
    ses = session(state, seat=rc.ROMANS)
    before = encode(board_copy(state))
    request = pending(ses, card)
    assert request['request_type'] == 'gallic_event_beneficiary'
    assert request['faction'] == rc.ROMANS
    assert set(request['factions']) == set(rc.GALLIC_FACTIONS) | (
        {rc.ROMANS} if card == 67 else set())
    assert encode(board_copy(state)) == before and not ses.data['journal']
    assert_retry(ses, card, [None, {'faction': rc.GERMANS}, {'use_default': 1},
                            {'decline': True}])
    choice = {'use_default': True} if default else {'faction': rc.AEDUI}
    submit(ses, choice)
    result = run(ses, card)
    ses.finish()
    assert result['executed'] and len(ses.log) == 1
    assert decode(ses.log[0]['assistant_response']) == choice
    assert validate_state(state) == []


@pytest.mark.parametrize('edition', ['original', 'second-edition'])
@pytest.mark.parametrize('limited_first', [False, True])
def test_gallic_shouts_owner_orders_two_commands_with_saved_intermediate_board(
        tmp_path, capsys, edition, limited_first):
    state = position(35, edition)
    initial = deepcopy(state)
    params = {'faction': rc.AEDUI}
    ses = session(state)
    before = encode(board_copy(state))
    order = ['limited_command', 'command'] if limited_first else ['command', 'limited_command']
    request = pending(ses, 35, params)
    assert request['request_type'] == 'gallic_command_order'
    assert request['faction'] == rc.AEDUI
    assert_retry(ses, 35, [None, {'order': ['command', 'command']},
                          {'order': order, 'acting_faction': rc.ROMANS}], params)
    submit(ses, {'order': order})
    request = pending(ses, 35, params)
    assert request['request_type'] == 'event_command'
    assert request['faction'] == rc.AEDUI and rc.CMD_BATTLE not in request['allowed_commands']
    assert (request.get('max_regions') == 1) == limited_first
    first = rally(rc.AEDUI_REGION) if limited_first else rally(rc.AEDUI_REGION, rc.SEQUANI)
    second = rally(rc.AEDUI_REGION, rc.SEQUANI) if limited_first else rally(rc.AEDUI_REGION)
    submit(ses, first)
    request = pending(ses, 35, params)
    assert request['faction'] == rc.AEDUI
    assert (request.get('max_regions') == 1) != limited_first
    intermediate = decode(ses.data['pending']['board'])
    assert count_pieces(intermediate, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == 1
    assert count_pieces(intermediate, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == int(not limited_first)
    assert encode(board_copy(state)) == before
    assert len(ses.data['journal']) == 2 and not ses.log
    illegal = dict(second, command=rc.CMD_BATTLE)
    assert_retry(ses, 35, [None, illegal, {'decline': True}], params)
    save_game(state, tmp_path / 'save.json', meta=ses.meta, log=ses.log)
    cmd_board(SimpleNamespace(dir=str(tmp_path)))
    shown = capsys.readouterr().out
    assert format_board(intermediate) in shown
    assert ses.data['pending']['id'] in shown
    restored, meta, log = load_game(tmp_path / 'save.json', validate=True)
    resumed = session(restored, meta, log)
    assert resumed.data['pending'] == ses.data['pending']
    submit(resumed, second)
    result = run(resumed, 35, params)
    resumed.finish()
    assert len(log) == 3 and result['executed']
    assert count_pieces(restored, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == 2
    assert count_pieces(restored, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == 1
    assert restored['resources'][rc.AEDUI] == 10
    assert_replay(initial, restored, 35, log, result, params)


def test_explicit_order_default_is_saved_before_owner_command_choice():
    ses = session(position(35))
    params = {'faction': rc.AEDUI}
    pending(ses, 35, params)
    submit(ses, {'use_default': True})
    request = pending(ses, 35, params)
    assert request['request_type'] == 'event_command'
    assert request['faction'] == rc.AEDUI
    assert decode(ses.data['journal'][0]['assistant_response']) == {'use_default': True}


def test_celtic_rites_command_owner_is_separate_from_executor_eligibility():
    state = position(46)
    state['eligibility'].update({rc.ROMANS: rc.INELIGIBLE, rc.AEDUI: rc.INELIGIBLE})
    initial = deepcopy(state)
    ses, params = session(state), {'faction': rc.AEDUI}
    request = pending(ses, 46, params)
    assert request['request_type'] == 'event_command' and request['faction'] == rc.AEDUI
    assert request['with_sa'] is False and request['free'] is True
    assert_retry(ses, 46, [None, {'decline': True}, dict(rally(rc.AEDUI_REGION), sa=rc.SA_TRADE)], params)
    submit(ses, rally(rc.AEDUI_REGION, rc.SEQUANI))
    result = run(ses, 46, params)
    ses.finish()
    assert count_pieces(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND) == 1
    assert count_pieces(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == 1
    assert state['resources'][rc.AEDUI] == 10
    assert state['eligibility'][rc.AEDUI] == rc.INELIGIBLE
    assert state['eligibility'][rc.ROMANS] == rc.ELIGIBLE
    assert rc.ROMANS in state['stay_eligible'] and rc.AEDUI not in state['stay_eligible']
    assert_replay(initial, state, 46, ses.log, result, params)


@pytest.mark.parametrize('side', [rc.EVENT_UNSHADED, rc.EVENT_SHADED])
def test_numeric_arduenna_saves_between_march_and_command_then_replays(tmp_path, side):
    state = position(67)
    initial = deepcopy(state)
    ses, params = session(state), {'faction': rc.AEDUI}
    before = encode(board_copy(state))
    request = pending(ses, 67, params, side)
    assert request['request_type'] == 'arduenna_accept' and request['faction'] == rc.AEDUI
    submit(ses, {'accept': True})
    request = pending(ses, 67, params, side)
    assert request['request_type'] == 'arduenna_march' and request['card_id'] == 67
    march = {'command': rc.CMD_MARCH, 'regions': [rc.ATREBATES], 'sa': 'No SA',
             'sa_regions': [], 'details': {'march_plan': {
                 'origins': [rc.ATREBATES], 'destinations': [rc.TREVERI],
                 'routes': {rc.ATREBATES: [rc.TREVERI]},
                 'groups': {rc.ATREBATES: {rc.WARBAND: 2}}}}}
    submit(ses, march)
    request = pending(ses, 67, params, side)
    assert request['request_type'] == 'arduenna_command'
    assert request['faction'] == rc.AEDUI and request['card_id'] == 67
    intermediate = decode(ses.data['pending']['board'])
    assert count_pieces(intermediate, rc.TREVERI, rc.AEDUI, rc.WARBAND) == 3
    assert count_pieces_by_state(intermediate, rc.TREVERI, rc.AEDUI, rc.WARBAND, rc.SCOUTED) == 1
    assert encode(board_copy(state)) == before and len(ses.data['journal']) == 2
    raid = {'command': rc.CMD_RAID, 'regions': [rc.TREVERI], 'sa': 'No SA',
            'sa_regions': [], 'details': {'raid_plan': [{'region': rc.TREVERI, 'target': None}]}}
    invalid = dict(raid, regions=[rc.ATREBATES], details={'raid_plan': [
        {'region': rc.ATREBATES, 'target': None}]})
    assert_retry(ses, 67, [None, {'decline': True}, invalid], params, side)
    save_game(state, tmp_path / 'arduenna.json', meta=ses.meta, log=ses.log)
    restored, meta, log = load_game(tmp_path / 'arduenna.json', validate=True)
    resumed = session(restored, meta, log)
    submit(resumed, raid)
    result = run(resumed, 67, params, side)
    resumed.finish()
    assert result['executed'] and len(log) == 3
    assert count_pieces(restored, rc.ATREBATES, rc.AEDUI, rc.WARBAND) == 2
    assert count_pieces_by_state(restored, rc.TREVERI, rc.AEDUI, rc.WARBAND, rc.HIDDEN) == 2
    assert count_pieces_by_state(restored, rc.TREVERI, rc.AEDUI, rc.WARBAND, rc.REVEALED) == 1
    assert count_pieces_by_state(restored, rc.TREVERI, rc.AEDUI, rc.WARBAND, rc.SCOUTED) == 0
    assert_replay(initial, restored, 67, log, result, params, side)


@pytest.mark.parametrize('edition', ['original', 'second-edition'])
@pytest.mark.parametrize('city', [rc.CITY_ALESIA, rc.CITY_CENABUM])
def test_foreign_executor_remi_asks_owner_with_context_and_places_owner_stock(tmp_path, edition, city):
    state = position(68, edition)
    ses = session(state)
    ses.display.remember(state, [rc.AEDUI])
    state['resources'][rc.AEDUI] += 1
    initial = deepcopy(board_copy(state))
    before = encode(board_copy(state))
    request = pending(ses, 68)
    assert request['request_type'] == 'remi_event_effect'
    assert request['faction'] == request['acting_faction'] == rc.AEDUI
    assert set(request['target_cities']) == {rc.CITY_ALESIA, rc.CITY_CENABUM}
    shown = ses.output.getvalue()
    assert 'changes since your last decision' in shown
    assert f'{rc.AEDUI} Resources: 10 -> 11' in shown
    for card in (68, 46):
        printed = get_card_text(card, state['scenario'], edition)
        assert printed
        assert all(line in shown for line in printed.splitlines())
    assert encode(board_copy(state)) == before
    choice = {'target_city': city}
    assert_retry(ses, 68, [None, {'use_default': 1}, {'target_city': rc.CITY_BIBRACTE},
                          dict(choice, acting_faction=rc.ROMANS)])
    submit(ses, choice)
    save_game(state, tmp_path / 'remi.json', meta=ses.meta, log=ses.log)
    restored, meta, log = load_game(tmp_path / 'remi.json', validate=True)
    resumed = session(restored, meta, log)
    result = run(resumed, 68)
    resumed.finish()
    tribe = rc.CITY_TO_TRIBE[city]
    region = rc.TRIBE_TO_REGION[tribe]
    assert count_pieces(restored, region, rc.AEDUI, rc.CITADEL) == 1
    assert count_pieces(restored, region, rc.AEDUI, rc.WARBAND) == 4
    assert count_pieces(restored, region, rc.ROMANS) == 0
    assert count_pieces(restored, rc.MANDUBII, rc.BELGAE, rc.WARBAND) == 2
    assert restored['tribes'][tribe]['allied_faction'] == rc.AEDUI
    assert restored['tribes'][rc.TRIBE_REMI]['allied_faction'] == rc.AEDUI
    assert len(log) == 1 and result['executed']
    assert_replay(initial, restored, 68, log, result)


@pytest.mark.parametrize('choice', [{'decline': True}, {'use_default': True}])
def test_remi_owner_explicit_default_or_decline_is_distinct_from_missing(choice):
    state = position(68)
    initial = deepcopy(state)
    before = encode(board_copy(state))
    ses = session(state)
    pending(ses, 68)
    assert encode(board_copy(state)) == before
    submit(ses, choice)
    result = run(ses, 68)
    ses.finish()
    assert len(ses.log) == 1
    assert decode(ses.log[0]['assistant_response']) == choice
    if choice == {'decline': True}:
        after = encode(board_copy(state))
        for key in ('spaces', 'tribes', 'available', 'resources', 'rng'):
            assert after[key] == before[key]
    else:
        assert sum(count_pieces(state, r, rc.AEDUI, rc.CITADEL)
                   for r in (rc.MANDUBII, rc.CARNUTES)) == 1
    assert_replay(initial, state, 68, ses.log, result)


@pytest.mark.parametrize('card', [35, 46])
@pytest.mark.parametrize('at_war', [False, True])
def test_automatic_arverni_grant_saved_selection_and_replay_never_asks_an_arverni_seat(
        tmp_path, card, at_war):
    """Provisional PR-10 follows the actual At War state and one A6 Command."""
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=3546)
    state['current_card'], state['next_card'] = card, 'A19'
    # Arverni are automatic, outside the four playable seats. The human
    # Roman executor selects their benefit without becoming their controller.
    state['non_player_factions'] = {rc.AEDUI, rc.BELGAE, rc.GERMANS}
    state['resources'].update({rc.AEDUI: 10, rc.ROMANS: 10})
    state['at_war'] = at_war
    assert _ally_tribe(state, rc.TRIBE_ARVERNI, rc.ARVERNI)
    assert _ally_tribe(state, rc.TRIBE_PICTONES, rc.ARVERNI)
    for region in (rc.ARVERNI_REGION, rc.PICTONES):
        place_piece(state, region, rc.ARVERNI, rc.WARBAND, 3)
        if at_war:
            place_piece(state, region, rc.ROMANS, rc.AUXILIA)
    assert validate_state(state) == []
    initial = deepcopy(state)
    before = encode(board_copy(state))

    def automatic_session(board, meta=None, log=None):
        current = session(board, meta, log, seat=rc.ROMANS)

        def reactive(live, faction, request):
            if live is not current.state:
                return None
            assert faction == rc.ROMANS, 'Automatic Arverni must not prompt a human seat'
            assert request['request_type'] == 'gallic_event_beneficiary'
            return current.reactive(live, faction, request)

        board['decision_agent'] = reactive
        return current

    def run_turn(current):
        def driver(*args):
            pass
        driver.transaction_checkpoint = current.checkpoint
        driver.transaction_restore = current.restore
        with _action_transaction(current.state, driver):
            decision = current.ask(current.state, rc.ROMANS, {
                'kind': 'turn', 'options': [ACTION_EVENT], 'position': '1st_eligible'})
            return _maybe_execute(current.state, rc.ROMANS, decision, {})

    turn = {'action': ACTION_EVENT, 'player_action': {
        'command': rc.FIRST_DID_EVENT, 'regions': [], 'sa': 'No SA',
        'sa_regions': [], 'details': {'card_id': card,
            'text_preference': rc.EVENT_SHADED, 'event_params': {}}}}

    ses = automatic_session(state)
    with pytest.raises(DecisionPending):
        run_turn(ses)
    submit(ses, turn)
    with pytest.raises(DecisionPending):
        run_turn(ses)
    request = decode(ses.data['pending']['request'])
    assert request['request_type'] == 'gallic_event_beneficiary'
    assert rc.ARVERNI in request['factions']
    assert encode(board_copy(state)) == before and len(ses.data['journal']) == 1
    submit(ses, {'faction': rc.ARVERNI})
    save_game(state, tmp_path / 'automatic-arverni.json', meta=ses.meta, log=ses.log)
    restored, meta, log = load_game(tmp_path / 'automatic-arverni.json', validate=True)
    resumed = automatic_session(restored, meta, log)
    result = run_turn(resumed)
    resumed.finish()
    assert result['executed'] and len(log) == 2
    assert resumed.data['pending'] is None
    assert [decode(entry['assistant_request'])['faction'] for entry in log] == [rc.ROMANS] * 2
    assert [decode(entry['assistant_response']) for entry in log] == [turn, {'faction': rc.ARVERNI}]
    grants = result['free_actions']
    assert len(grants) == (2 if card == 35 else 1)
    assert all(grant['faction'] == rc.ARVERNI for grant in grants)
    if at_war:
        assert all(grant['result']['executed'] for grant in grants)
        assert all(grant['result']['command'] == rc.CMD_RALLY for grant in grants)
        assert count_pieces(restored, rc.ARVERNI_REGION, rc.ARVERNI, rc.CITADEL) == 1
    else:
        assert all(not grant['result']['executed'] and grant['result']['declined_no_effect']
                   for grant in grants)
        after = encode(board_copy(restored))
        for key in ('spaces', 'tribes', 'available', 'resources'):
            assert after[key] == before[key]
    assert restored['at_war'] is at_war
    assert restored['resources'] == initial['resources']
    if card == 46:
        assert rc.ROMANS in restored['stay_eligible']
        assert rc.ARVERNI not in restored['stay_eligible']
    assert validate_state(restored) == []
    replayed = automatic_session(initial)
    replayed.import_inbox([{'response': decode(entry['assistant_response'])} for entry in log])
    assert run_turn(replayed) == result
    replayed.finish()
    assert replayed.log == log
    assert encode(board_copy(initial)) == encode(board_copy(restored))


def test_np_arduenna_binding_no_harassment_survives_save_and_exact_replay(tmp_path):
    """PR-11 binds the human promise before planning and reuses it on March."""
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=67)
    state.update(current_card=67, next_card=3, executing_faction=rc.ARVERNI,
                 non_player_factions={rc.ARVERNI, rc.AEDUI, rc.BELGAE})
    place_piece(state, rc.VENETI, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(state, rc.VENETI, rc.ARVERNI, rc.WARBAND, 2)
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, 9)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.LEGION, from_legions_track=True)
    state['resources'][rc.ROMANS] = 10
    ses = session(state, seat=rc.ROMANS)
    ses.display.remember(state, [rc.ROMANS])
    state['resources'][rc.ROMANS] = 11
    initial = deepcopy(board_copy(state))
    before = encode(board_copy(state))
    action = {'command': rc.FIRST_DID_EVENT, 'sa': 'No SA', 'sa_regions': [],
              'details': {'card_id': 67, 'text_preference': rc.EVENT_SHADED}}

    def run_np(current):
        def driver(*args):
            pass
        driver.transaction_checkpoint = current.checkpoint
        driver.transaction_restore = current.restore
        with _action_transaction(current.state, driver):
            return _execute_event(current.state, rc.ARVERNI, action)

    with pytest.raises(DecisionPending):
        run_np(ses)
    request = decode(ses.data['pending']['request'])
    assert request['request_type'] == 'harassment'
    assert request['faction'] == rc.ROMANS and request['requesting_faction'] == rc.ARVERNI
    assert request['context']['region'] == rc.ATREBATES
    assert encode(board_copy(state)) == before and not ses.data['journal']
    shown = ses.output.getvalue()
    assert f'{rc.ROMANS} Resources: 10 -> 11' in shown
    for card in (67, 3):
        assert all(line in shown for line in get_card_text(card, state['scenario']).splitlines())
    submit(ses, False)
    save_game(state, tmp_path / 'binding-promise.json', meta=ses.meta, log=ses.log)
    restored, meta, log = load_game(tmp_path / 'binding-promise.json', validate=True)
    resumed = session(restored, meta, log)
    with pytest.raises(DecisionPending):
        run_np(resumed)
    request = decode(resumed.data['pending']['request'])
    assert request.get('request_type') != 'harassment'
    intermediate = decode(resumed.data['pending']['board'])
    # Nine Hidden Auxilia could remove both Warbands and threaten the Leader;
    # the promised refusal keeps both Warbands through the actual transit.
    assert count_pieces(intermediate, rc.NERVII, rc.ARVERNI, rc.WARBAND) == 2
    assert count_pieces(intermediate, rc.NERVII, rc.ARVERNI, rc.LEADER) == 1
    assert count_pieces(intermediate, rc.VENETI, rc.ARVERNI) == 0
    assert encode(board_copy(restored)) == before
    assert len(resumed.data['journal']) == 1
    assert decode(resumed.data['journal'][0]['assistant_response']) is False
    for _ in range(8):
        assert decode(resumed.data['pending']['request']).get('request_type') != 'harassment'
        submit(resumed, {'use_default': True})
        try:
            result = run_np(resumed)
            break
        except DecisionPending:
            continue
    else:
        pytest.fail('Roman Battle reactions did not complete')
    resumed.finish()
    assert result['executed'] and validate_state(restored) == []
    assert sum(decode(entry['assistant_request']).get('request_type') == 'harassment'
               for entry in log) == 1
    entries = iter(log)

    def recorded(board, faction, question):
        entry = next(entries)
        assert decode(entry['assistant_request']) == dict(question, faction=faction)
        return decode(entry['assistant_response'])

    initial['decision_agent'] = recorded
    assert _execute_event(initial, rc.ARVERNI, action) == result
    assert next(entries, None) is None
    assert encode(board_copy(initial)) == encode(board_copy(restored))
