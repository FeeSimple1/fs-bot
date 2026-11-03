"""BE-02 Event Battle choices cross real durable decision boundaries."""
from copy import deepcopy
from io import StringIO
from types import SimpleNamespace

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece
from fs_bot.cards.card_effects import _ally_tribe, execute_event
from fs_bot.cards.card_text import get_card_text
from fs_bot.cli.display import HumanTurnDisplay, format_board, format_region_table
from fs_bot.engine.execute import _execute_event
from fs_bot.engine.game_engine import ACTION_EVENT, _action_transaction, _maybe_execute
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.llm_seat import cmd_board
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


CASES = [
    (11, 'original', rc.SCENARIO_GREAT_REVOLT),
    (11, 'second-edition', rc.SCENARIO_GREAT_REVOLT),
    (11, 'legacy', rc.SCENARIO_ARIOVISTUS),
    (25, 'original', rc.SCENARIO_GREAT_REVOLT),
    (36, 'original', rc.SCENARIO_GREAT_REVOLT),
    (45, 'original', rc.SCENARIO_GREAT_REVOLT),
    (70, 'original', rc.SCENARIO_GREAT_REVOLT),
]


def position(card, edition, scenario):
    state = build_initial_state(scenario, seed=1125364570)
    state['card_edition'] = edition
    state['current_card'], state['next_card'] = card, 35
    state['executing_faction'] = rc.BELGAE
    state['event_params'] = None
    actor = rc.ROMANS if card in (11, 70) else rc.BELGAE
    playable = {rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE}
    if scenario in rc.ARIOVISTUS_SCENARIOS:
        playable = {rc.ROMANS, rc.GERMANS, rc.AEDUI, rc.BELGAE}
    state['non_player_factions'] = playable - {actor, rc.BELGAE}
    state['resources'].update({rc.ROMANS: 10, rc.BELGAE: 10})
    if card == 11:
        place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEADER,
                    leader_name=rc.CAESAR)
        place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 3)
        place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND)
    elif card == 25:
        assert _ally_tribe(state, rc.TRIBE_PICTONES, rc.AEDUI)
        place_piece(state, rc.PICTONES, rc.AEDUI, rc.WARBAND, 4)
        place_piece(state, rc.PICTONES, rc.ROMANS, rc.AUXILIA, 3)
    elif card == 36:
        place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 4)
        place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 6)
        place_piece(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND, 4)
        place_piece(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND, 2)
    elif card == 45:
        # The Event permits an attack with Aedui pieces alone.
        place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 4)
        place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
        place_piece(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND, 6)
        place_piece(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA, 3)
    else:
        place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, 4)
        place_piece(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 2)
        place_piece(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND)
    assert validate_state(state) == []
    return state, actor


def params(card):
    if card == 11:
        return {'target_region': rc.CARNUTES, 'region': rc.CARNUTES}
    return {'battle_region': rc.PICTONES} if card == 25 else {}


def selected(card):
    return {
        11: {'region': rc.CARNUTES, 'defender': rc.AEDUI},
        25: {'region': rc.PICTONES, 'defender': rc.AEDUI},
        36: {'region': rc.MANDUBII, 'defender': rc.AEDUI},
        45: {'region': rc.CARNUTES, 'defender': rc.ROMANS},
        70: {'region': rc.ATREBATES, 'defender': rc.AEDUI},
    }[card]


def event(state, card, executor=rc.BELGAE, event_params=None):
    action = {'command': rc.FIRST_DID_EVENT, 'regions': [], 'sa': 'No SA',
              'sa_regions': [], 'details': {
                  'card_id': card,
                  'text_preference': rc.EVENT_SHADED if card == 45 else rc.EVENT_UNSHADED,
                  'event_params': params(card) if event_params is None else event_params}}
    return _execute_event(state, executor, action,
                          human=executor not in state.get('non_player_factions', ()))


def session(state, actor, meta=None, log=None):
    output = StringIO()
    ses = SeatSession(state, {'seat': actor} if meta is None else meta,
                      [] if log is None else log, HumanTurnDisplay(output))
    # These cases isolate the BE-02 Battle boundary. Camulogenus's earlier
    # acceptance/March boundaries have their own end-to-end session tests.
    def battle_agent(live, faction, request):
        if request.get('card_id') == 70:
            if request.get('request_type') == 'roman_event_accept':
                return {'accept': True}
            if request.get('request_type') == 'camulogenus_march':
                return {'use_default': True}
        return ses.reactive(live, faction, request)
    state['decision_agent'] = battle_agent if state.get('current_card') == 70 else ses.reactive
    ses.output = output
    return ses


def step(ses, card, executor=rc.BELGAE, event_params=None):
    def driver(*args):
        pass
    driver.transaction_checkpoint = ses.checkpoint
    driver.transaction_restore = ses.restore
    with _action_transaction(ses.state, driver):
        return event(ses.state, card, executor, event_params)


def submit(ses, response):
    ses.import_inbox({'decision_id': ses.data['pending']['id'], 'response': response})


def pending(ses, card, executor=rc.BELGAE, event_params=None):
    with pytest.raises(DecisionPending):
        step(ses, card, executor, event_params)
    return decode(ses.data['pending']['request'])


def replay(initial, final, card, log, result, executor=rc.BELGAE, event_params=None):
    records = iter(log)
    def respond(state, faction, request):
        if request.get('card_id') == 70:
            if request.get('request_type') == 'roman_event_accept':
                return {'accept': True}
            if request.get('request_type') == 'camulogenus_march':
                return {'use_default': True}
        entry = next(records)
        assert decode(entry['assistant_request']) == dict(request, faction=faction)
        return decode(entry['assistant_response'])
    initial['decision_agent'] = respond
    assert event(initial, card, executor, event_params) == result
    assert next(records, None) is None
    assert encode(board_copy(initial)) == encode(board_copy(final))
    assert validate_state(final) == []


@pytest.mark.parametrize('card,edition,scenario', CASES)
def test_event_battle_missing_and_invalid_choices_keep_exact_pending_state(card, edition, scenario):
    state, actor = position(card, edition, scenario)
    ses = session(state, actor)
    ses.display.remember(state, [actor])
    state['resources'][actor] += 1
    before = encode(board_copy(state))
    request = pending(ses, card)
    assert request['kind'] == 'free_action'
    assert request['request_type'] == 'fixed_event_battle'
    assert request['faction'] == actor
    assert request['allow_decline'] is False
    assert encode(board_copy(state)) == before
    text = ses.output.getvalue()
    assert 'changes since your last decision' in text
    assert f'{actor} Resources: 10 -> 11' in text
    assert rc.CARD_NAMES_BASE[35] in text and rc.CARD_NAMES_BASE[card] in text
    for shown_card in (card, 35):
        assert all(line in text for line in get_card_text(
            shown_card, scenario, edition).splitlines())
    original = deepcopy(ses.data['pending'])
    for answer in (None, {'decline': True}, {'use_default': 1},
                   {'region': rc.PROVINCIA, 'defender': rc.AEDUI},
                   dict(selected(card), defender=actor),
                   dict(selected(card), extra_losses=99),
                   dict(selected(card), sa=rc.SA_AMBUSH)):
        submit(ses, answer)
        pending(ses, card)
        assert ses.error
        for key in ('id', 'request', 'board'):
            assert ses.data['pending'][key] == original[key]
        assert encode(board_copy(state)) == before
        assert not ses.data['journal'] and not ses.log


@pytest.mark.parametrize('card,edition,scenario', CASES)
def test_event_battle_saved_intermediate_board_choice_and_replay(tmp_path, capsys, card, edition, scenario):
    state, actor = position(card, edition, scenario)
    initial = deepcopy(state)
    ses = session(state, actor)
    before = encode(board_copy(state))
    request = pending(ses, card)
    assert request['faction'] == actor
    intermediate = decode(ses.data['pending']['board'])
    if card == 11:
        assert count_pieces(intermediate, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 3
        assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 0
    elif card == 70:
        assert count_pieces(intermediate, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 4
        assert count_pieces(intermediate, rc.NERVII, rc.ROMANS, rc.AUXILIA) == 0
        assert count_pieces(state, rc.NERVII, rc.ROMANS, rc.AUXILIA) == 4
    assert encode(board_copy(state)) == before
    save_game(state, tmp_path / 'save.json', meta=ses.meta, log=ses.log)
    cmd_board(SimpleNamespace(dir=str(tmp_path)))
    shown = capsys.readouterr().out
    assert format_board(intermediate) in shown
    assert ses.data['pending']['id'] in shown
    restored, meta, log = load_game(tmp_path / 'save.json', validate=True)
    resumed = session(restored, actor, meta, log)
    assert resumed.data['pending'] == ses.data['pending']
    submit(resumed, selected(card))
    result = step(resumed, card)
    resumed.finish()
    assert result['executed'] and len(log) == 1
    assert decode(log[0]['assistant_response']) == selected(card)
    assert restored['resources'][actor] == 10
    if card == 11:
        assert count_pieces(restored, rc.CARNUTES, rc.AEDUI) == 0
        assert count_pieces(restored, rc.CARNUTES, rc.ARVERNI, rc.WARBAND) == 3
    elif card == 25:
        assert count_pieces(restored, rc.PICTONES, rc.BELGAE) == 0
        assert count_pieces(restored, rc.PICTONES, rc.AEDUI, rc.ALLY) == 0
        assert count_pieces(restored, rc.PICTONES, rc.AEDUI, rc.WARBAND) == 2
        assert count_pieces(restored, rc.PICTONES, rc.ROMANS, rc.AUXILIA) == 3
    elif card == 36:
        assert count_pieces(restored, rc.MANDUBII, rc.AEDUI) == 0
        assert count_pieces_by_state(restored, rc.MANDUBII, rc.BELGAE, rc.WARBAND, rc.HIDDEN) == 4
        assert count_pieces(restored, rc.CARNUTES, rc.ARVERNI, rc.WARBAND) == 6
    elif card == 45:
        assert count_pieces(restored, rc.CARNUTES, rc.ROMANS) == 0
        assert count_pieces(restored, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 4
        assert count_pieces(restored, rc.CARNUTES, rc.BELGAE) == 0
        assert count_pieces(restored, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 3
    else:
        assert count_pieces(restored, rc.ATREBATES, rc.AEDUI) == 0
        assert count_pieces(restored, rc.ATREBATES, rc.BELGAE, rc.WARBAND) == 2
    replay(initial, restored, card, log, result)


def test_event_battle_explicit_default_is_recorded_and_replayable():
    state, actor = position(36, 'original', rc.SCENARIO_GREAT_REVOLT)
    initial = deepcopy(state)
    ses = session(state, actor)
    request = pending(ses, 36)
    assert request['default_available'] and request['validate_default_response']
    submit(ses, {'use_default': True})
    result = step(ses, 36)
    ses.finish()
    assert result['executed'] and len(ses.log) == 1
    assert decode(ses.log[0]['assistant_response']) == {'use_default': True}
    replay(initial, state, 36, ses.log, result)


def test_sack_event_without_preselected_region_offers_both_printed_regions(tmp_path):
    state, actor = position(25, 'original', rc.SCENARIO_GREAT_REVOLT)
    place_piece(state, rc.ARVERNI_REGION, rc.AEDUI, rc.WARBAND, 2)
    initial = deepcopy(state)
    ses = session(state, actor)
    request = pending(ses, 25, event_params={})
    assert request['request_type'] == 'fixed_event_battle'
    assert set(request['allowed_regions']) == {rc.PICTONES, rc.ARVERNI_REGION}
    assert request['defenders_by_region'][rc.ARVERNI_REGION] == [rc.AEDUI]
    save_game(state, tmp_path / 'save.json', meta=ses.meta, log=ses.log)
    restored, meta, log = load_game(tmp_path / 'save.json', validate=True)
    resumed = session(restored, actor, meta, log)
    chosen = {'region': rc.ARVERNI_REGION, 'defender': rc.AEDUI}
    submit(resumed, chosen)
    result = step(resumed, 25, event_params={})
    resumed.finish()
    assert result['executed'] and len(log) == 1
    assert decode(log[0]['assistant_response']) == chosen
    assert count_pieces(restored, rc.ARVERNI_REGION, rc.AEDUI) == 0
    assert count_pieces(restored, rc.PICTONES, rc.AEDUI, rc.WARBAND) == 4
    assert count_pieces(restored, rc.PICTONES, rc.AEDUI, rc.ALLY) == 1
    replay(initial, restored, 25, log, result, event_params={})


def test_revised_numidians_counterattack_pause_preserves_physical_board_and_replays(tmp_path, capsys):
    state, actor = position(11, 'second-edition', rc.SCENARIO_GREAT_REVOLT)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 7)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEGION, 2,
                from_legions_track=True)
    initial = deepcopy(state)
    ses = session(state, actor)
    before = encode(board_copy(state))
    pending(ses, 11)
    submit(ses, selected(11))
    request = pending(ses, 11)
    assert request['kind'] == 'loss_order' and request['faction'] == rc.ROMANS
    assert {piece[0] for piece in request['pieces']} == {rc.AUXILIA}
    assert len(ses.data['journal']) == 1
    assert encode(board_copy(state)) == before
    assert '_battle_auxilia_only' not in state
    intermediate = decode(ses.data['pending']['board'])
    physical = dict(intermediate)
    physical.pop('_battle_auxilia_only', None)
    assert count_pieces(physical, rc.CARNUTES, rc.ROMANS, rc.LEGION) == 2
    assert count_pieces(physical, rc.CARNUTES, rc.ROMANS, rc.LEADER) == 1
    assert format_region_table(intermediate) == format_region_table(physical)
    save_game(state, tmp_path / 'save.json', meta=ses.meta, log=ses.log)
    cmd_board(SimpleNamespace(dir=str(tmp_path)))
    assert format_region_table(physical) in capsys.readouterr().out
    restored, meta, log = load_game(tmp_path / 'save.json', validate=True)
    resumed = session(restored, actor, meta, log)
    while True:
        request = decode(resumed.data['pending']['request'])
        assert request['kind'] == 'loss_order'
        assert {piece[0] for piece in request['pieces']} == {rc.AUXILIA}
        submit(resumed, {'use_default': True})
        try:
            result = step(resumed, 11)
            break
        except DecisionPending:
            pass
    resumed.finish()
    assert result['executed']
    assert count_pieces(restored, rc.CARNUTES, rc.ROMANS, rc.LEGION) == 2
    assert count_pieces(restored, rc.CARNUTES, rc.ROMANS, rc.LEADER) == 1
    assert count_pieces(restored, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(restored, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 5
    assert '_battle_auxilia_only' not in restored
    replay(initial, restored, 11, log, result)


def test_refused_diviciacus_loan_reopens_required_battle_with_saved_choices(tmp_path):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=36)
    state['card_edition'] = 'original'
    state['current_card'], state['next_card'] = 36, 35
    state['executing_faction'], state['event_params'] = rc.ROMANS, None
    state['non_player_factions'] = {rc.BELGAE, rc.ARVERNI, rc.AEDUI}
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 2)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 3)
    execute_event(state, 38)
    initial = deepcopy(state)
    ses = session(state, rc.ROMANS)
    request = pending(ses, 36, rc.ROMANS)
    assert request['request_type'] == 'fixed_event_battle'
    submit(ses, {'region': rc.CARNUTES, 'defender': rc.BELGAE})
    request = pending(ses, 36, rc.ROMANS)
    assert request['request_type'] == 'diviciacus_command' and request['faction'] == rc.ROMANS
    submit(ses, True)
    request = pending(ses, 36, rc.ROMANS)
    assert request['request_type'] == 'fixed_event_battle'
    assert request['faction'] == rc.ROMANS and request['attempt'] == 2
    assert 'refused' in request['previous_error']
    assert len(ses.data['journal']) == 2 and not ses.log
    save_game(state, tmp_path / 'save.json', meta=ses.meta, log=ses.log)
    restored, meta, log = load_game(tmp_path / 'save.json', validate=True)
    resumed = session(restored, rc.ROMANS, meta, log)
    submit(resumed, {'region': rc.CARNUTES, 'defender': rc.BELGAE})
    request = pending(resumed, 36, rc.ROMANS)
    assert request['request_type'] == 'diviciacus_command'
    submit(resumed, False)
    result = step(resumed, 36, rc.ROMANS)
    resumed.finish()
    assert result['executed'] and len(log) == 4
    assert count_pieces(restored, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 2
    assert count_pieces(restored, rc.CARNUTES, rc.BELGAE, rc.WARBAND) == 3
    assert '_diviciacus_force' not in restored
    assert '_diviciacus_confirmations' not in restored
    replay(initial, restored, 36, log, result, rc.ROMANS)


def test_human_lender_owns_consent_to_nonplayer_event_battle_and_can_resume(tmp_path):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=36)
    state['card_edition'] = 'original'
    state['current_card'], state['next_card'] = 36, 35
    state['executing_faction'], state['event_params'] = rc.ROMANS, None
    state['non_player_factions'] = {rc.ROMANS, rc.BELGAE, rc.ARVERNI}
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 2)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 3)
    execute_event(state, 38)
    initial = deepcopy(state)
    ses = session(state, rc.AEDUI)
    request = pending(ses, 36, rc.ROMANS)
    assert request['kind'] == 'agreement' and request['request_type'] == 'diviciacus'
    assert request['faction'] == rc.AEDUI and request['requesting_faction'] == rc.ROMANS
    assert request['context']['targets'] == {rc.CARNUTES: [rc.BELGAE]}
    save_game(state, tmp_path / 'save.json', meta=ses.meta, log=ses.log)
    restored, meta, log = load_game(tmp_path / 'save.json', validate=True)
    resumed = session(restored, rc.AEDUI, meta, log)
    submit(resumed, False)
    result = step(resumed, 36, rc.ROMANS)
    resumed.finish()
    assert result['executed'] and len(log) == 1
    assert count_pieces(restored, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 2
    assert count_pieces(restored, rc.CARNUTES, rc.BELGAE, rc.WARBAND) == 3
    assert '_diviciacus_force' not in restored
    assert '_diviciacus_confirmations' not in restored
    replay(initial, restored, 36, log, result, rc.ROMANS)


def test_accepted_turn_event_remains_journaled_until_required_battle_is_answered(tmp_path):
    state, actor = position(36, 'original', rc.SCENARIO_GREAT_REVOLT)
    initial = deepcopy(state)
    ses = session(state, actor)
    before = encode(board_copy(state))
    turn = {'action': ACTION_EVENT, 'player_action': {
        'command': rc.FIRST_DID_EVENT, 'regions': [], 'sa': 'No SA',
        'sa_regions': [], 'details': {'card_id': 36,
            'text_preference': rc.EVENT_UNSHADED, 'event_params': {}}}}

    def run_turn(current):
        def driver(*args):
            pass
        driver.transaction_checkpoint = current.checkpoint
        driver.transaction_restore = current.restore
        with _action_transaction(current.state, driver):
            decision = current.ask(current.state, actor, {
                'kind': 'turn', 'options': [ACTION_EVENT], 'position': '1st_eligible'})
            return _maybe_execute(current.state, actor, decision, {})

    with pytest.raises(DecisionPending):
        run_turn(ses)
    submit(ses, turn)
    # A real turn also exposes voluntary-removal timing windows. Answer
    # those explicitly, retaining their journal entries, until Battle.
    while True:
        with pytest.raises(DecisionPending):
            run_turn(ses)
        request = decode(ses.data['pending']['request'])
        if request.get('request_type') == 'fixed_event_battle':
            break
        assert request['kind'] == 'voluntary_removal'
        submit(ses, {'done': True})
    original = deepcopy(ses.data['pending'])
    assert decode(original['request'])['request_type'] == 'fixed_event_battle'
    journal = deepcopy(ses.data['journal'])
    assert len(journal) > 1 and not ses.log
    assert encode(board_copy(state)) == before
    submit(ses, {'decline': True})
    with pytest.raises(DecisionPending):
        run_turn(ses)
    assert ses.error and ses.data['journal'] == journal
    assert ses.data['pending'] == original
    assert encode(board_copy(state)) == before
    save_game(state, tmp_path / 'save.json', meta=ses.meta, log=ses.log)
    restored, meta, log = load_game(tmp_path / 'save.json', validate=True)
    resumed = session(restored, actor, meta, log)
    submit(resumed, selected(36))
    while True:
        try:
            result = run_turn(resumed)
            break
        except DecisionPending:
            assert decode(resumed.data['pending']['request'])['kind'] == 'voluntary_removal'
            submit(resumed, {'done': True})
    resumed.finish()
    assert result['executed'] and len(log) > len(journal)
    assert decode(log[0]['assistant_response']) == turn
    battle_entries = [entry for entry in log
                      if decode(entry['assistant_request']).get('request_type') == 'fixed_event_battle']
    assert len(battle_entries) == 1
    assert decode(battle_entries[0]['assistant_response']) == selected(36)
    assert count_pieces(restored, rc.MANDUBII, rc.AEDUI) == 0
    answers = iter(log[1:])
    def respond(board, faction, request):
        entry = next(answers)
        assert decode(entry['assistant_request']) == dict(request, faction=faction)
        return decode(entry['assistant_response'])
    respond.supports_action_windows = True
    initial['decision_agent'] = respond
    assert _maybe_execute(initial, actor, turn, {}) == result
    assert next(answers, None) is None
    assert encode(board_copy(initial)) == encode(board_copy(restored))
    assert validate_state(restored) == []
