"""§3.2.2/3.3.2 let a human select any group and any pieces to drop off."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces_by_state
from fs_bot.cards.card_text import get_card_text
from fs_bot.cards.publius import _march as publius_march
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine.execute import _march_with_harassment
from fs_bot.engine.game_engine import get_sop_factions, _action_transaction
from fs_bot.engine.march_choices import MARCH_COHORT, validate_response
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import encode, decode, save_game, load_game
from fs_bot.tools.seat_session import SeatSession, DecisionPending, board_copy


def board():
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=3)
    state['non_player_factions'] = set(get_sop_factions(state)) - {rc.ARVERNI}
    state['current_card'], state['next_card'] = 4, 5
    place_piece(state, rc.MORINI, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(state, rc.MORINI, rc.ARVERNI, rc.WARBAND, 2)
    place_piece(state, rc.MORINI, rc.ARVERNI, rc.WARBAND, 2, piece_state=rc.SCOUTED)
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.WARBAND, 3)
    return state


def march(state, *, drop=True):
    return _march_with_harassment(state, rc.ARVERNI, rc.MORINI,
        [rc.NERVII, rc.ATREBATES], group_cap={rc.LEADER: True, rc.WARBAND: 2},
        dropoffs_by_region={rc.NERVII: {rc.WARBAND: 1}} if drop else None,
        harassers_by_region={rc.NERVII: []})


def visibility(state, region, faction=rc.ARVERNI):
    return tuple(count_pieces_by_state(state, region, faction, rc.WARBAND, ps)
                 for ps in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED))


def responses(state, entries):
    queue, seen = iter(entries), []
    def agent(st, faction, request):
        if request['kind'] != MARCH_COHORT:
            return None
        seen.append((deepcopy(request), visibility(st, request['region'])))
        return next(queue)
    state['decision_agent'] = agent
    return seen


def test_human_selects_revealed_origin_and_dropoff_without_changing_residents():
    state = board()
    rng = state['rng'].getstate()
    seen = responses(state, [{'counts': {rc.HIDDEN: 1, rc.REVEALED: 1}},
                             {'counts': {rc.REVEALED: 1}}])
    assert march(state) == rc.ATREBATES
    assert [r['phase'] for r, _ in seen] == ['formation', 'dropoff']
    assert seen[0][0]['available'] == {rc.HIDDEN: 2, rc.REVEALED: 2}
    assert seen[0][1] == (2, 2, 0)  # source Scouted already became Revealed
    assert seen[1][0]['available'] == {rc.HIDDEN: 1, rc.REVEALED: 1}
    assert visibility(state, rc.MORINI) == (1, 1, 0)
    assert visibility(state, rc.NERVII) == (3, 1, 0)
    assert visibility(state, rc.ATREBATES) == (1, 0, 0)
    assert state['rng'].getstate() == rng
    assert validate_state(state) == []


@pytest.mark.parametrize('default', [None, {'use_default': True}])
def test_human_default_preserves_hidden_first_without_rng(default):
    state = board()
    rng = state['rng'].getstate()
    seen = responses(state, [default])
    march(state)
    assert len(seen) == 1  # both selected Warbands Hidden: drop-off is forced
    assert visibility(state, rc.MORINI) == (0, 2, 0)
    assert visibility(state, rc.NERVII) == (4, 0, 0)
    assert visibility(state, rc.ATREBATES) == (1, 0, 0)
    assert state['rng'].getstate() == rng


def test_np_keeps_existing_priorities_and_never_consults_cohort_agent():
    state = board()
    state['non_player_factions'].add(rc.ARVERNI)
    seen = responses(state, [])
    march(state)
    assert seen == [] and visibility(state, rc.ATREBATES) == (1, 0, 0)


@pytest.mark.parametrize('human', [True, False])
def test_multiple_groups_flip_their_shared_origin_only_once(human):
    from fs_bot.engine.execute import _execute_march_moves
    state = board()
    if not human:
        state['non_player_factions'].add(rc.ARVERNI)
    seen = responses(state, [{'counts': {rc.HIDDEN: 2}}])
    result = _execute_march_moves(state, rc.ARVERNI, [
        {'origin': rc.MORINI, 'path': [rc.NERVII], 'group': {rc.WARBAND: 2}},
        {'origin': rc.MORINI, 'path': [rc.ATREBATES], 'group': {rc.WARBAND: 2}},
    ], free=True)
    assert result['executed'] and not result['errors']
    assert len(seen) == int(human)
    assert visibility(state, rc.MORINI) == (0, 0, 0)
    assert visibility(state, rc.NERVII) == (5, 0, 0)
    assert visibility(state, rc.ATREBATES) == (0, 2, 0)
    assert validate_state(state) == []


def test_morasses_mixed_in_place_and_split_movement_flips_each_origin_once():
    from fs_bot.cards.morasses import execute_march, validate_march
    state = board()
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 1, piece_state=rc.SCOUTED)
    seen = responses(state, [{'counts': {rc.HIDDEN: 2}}])
    response = {'in_place': [rc.CARNUTES], 'action': {
        'command': rc.CMD_MARCH, 'regions': [], 'sa': 'No SA', 'details': {
            'origins': [rc.MORINI], 'destinations': [rc.NERVII, rc.ATREBATES],
            'routes': {rc.MORINI: [rc.NERVII]}, 'groups': {rc.MORINI: {rc.WARBAND: 2}},
            'extra_groups': [{'origin': rc.MORINI, 'route': [rc.ATREBATES],
                              'group': {rc.WARBAND: 2}}]}}}
    validate_march(state, rc.ARVERNI, response)
    result = execute_march(state, rc.ARVERNI, response)
    assert result['executed'] and not result['moving']['errors']
    assert len(seen) == 1
    assert visibility(state, rc.NERVII) == (5, 0, 0)
    assert visibility(state, rc.ATREBATES) == (0, 2, 0)
    assert visibility(state, rc.CARNUTES) == (0, 1, 0)


@pytest.mark.parametrize('scenario,human', [
    (rc.SCENARIO_PAX_GALLICA, False), (rc.SCENARIO_ARIOVISTUS, True)])
def test_german_visibility_choice_exists_only_for_ariovistus_human_seat(scenario, human):
    state = build_initial_state(scenario, seed=3)
    state['non_player_factions'] = set(get_sop_factions(state)) - {rc.GERMANS}
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, 1)
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, 1, piece_state=rc.SCOUTED)
    seen = responses(state, [{'counts': {rc.REVEALED: 1}}])
    _march_with_harassment(state, rc.GERMANS, rc.SUGAMBRI, [rc.UBII],
                           group_cap={rc.WARBAND: 1})
    assert bool(seen) == human
    assert visibility(state, rc.UBII, rc.GERMANS) == ((0, 1, 0) if human else (1, 0, 0))


def test_publius_auxilia_all_hide_before_formation_and_dropoff():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=3)
    state['non_player_factions'] = set(get_sop_factions(state)) - {rc.ROMANS}
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION, 2, from_legions_track=True)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 2, piece_state=rc.REVEALED)
    seen = responses(state, [])
    publius_march(state, {'origin': rc.PROVINCIA, 'route': [rc.SEQUANI, rc.MANDUBII],
        'legions': 1, 'auxilia': 2, 'dropoffs': {rc.SEQUANI: {rc.AUXILIA: 1}}})
    assert seen == []
    assert count_pieces_by_state(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 2
    assert count_pieces_by_state(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 1
    assert count_pieces_by_state(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 1


def test_enlisted_subset_preserves_human_visibility_and_physical_owner():
    from fs_bot.commands.sa_enlist import begin_borrow, end_borrow
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=3)
    state['non_player_factions'] = set(get_sop_factions(state)) - {rc.BELGAE}
    place_piece(state, rc.NERVII, rc.BELGAE, rc.LEADER, leader_name=rc.AMBIORIX)
    for faction in (rc.GERMANS, rc.BELGAE):
        place_piece(state, rc.NERVII, faction, rc.WARBAND, 1)
        place_piece(state, rc.NERVII, faction, rc.WARBAND, 1, piece_state=rc.SCOUTED)
    begin_borrow(state, {'command': rc.CMD_MARCH, 'sa': rc.SA_ENLIST,
        'sa_regions': [rc.NERVII], 'details': {'enlist': {'type': 'borrow', 'regions': [rc.NERVII]}}})
    seen = responses(state, [{'counts': {rc.REVEALED: 1}}, {'counts': {rc.REVEALED: 1}}])
    _march_with_harassment(state, rc.BELGAE, rc.NERVII, [rc.ATREBATES],
        group_cap={rc.WARBAND: 2, 'german_warbands': 1})
    end_borrow(state)
    assert [r['physical_owner'] for r, _ in seen] == [rc.GERMANS, rc.BELGAE]
    for faction in (rc.GERMANS, rc.BELGAE):
        assert visibility(state, rc.NERVII, faction) == (1, 0, 0)
        assert visibility(state, rc.ATREBATES, faction) == (0, 1, 0)
    assert validate_state(state) == []


@pytest.mark.parametrize('german_human', [True, False])
def test_divination_chooser_selects_real_german_visibility_on_live_board_only(german_human):
    from fs_bot.engine.free_actions import execute_free_action_plan, validate_free_action_response
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=3)
    state['non_player_factions'] = set(get_sop_factions(state)) - {rc.AEDUI}
    if german_human:
        state['non_player_factions'].remove(rc.GERMANS)
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, 1)
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, 1, piece_state=rc.SCOUTED)
    request = {'kind': 'free_action', 'request_type': 'event_command', 'card_id': 'A34',
               'acting_faction': rc.GERMANS, 'allowed_commands': [rc.CMD_MARCH],
               'with_sa': False, 'free': True, 'max_regions': 3}
    action = {'command': rc.CMD_MARCH, 'regions': [], 'sa': 'No SA', 'details': {
        'origins': [rc.SUGAMBRI], 'destinations': [rc.UBII],
        'routes': {rc.SUGAMBRI: [rc.UBII]}, 'groups': {rc.SUGAMBRI: {rc.WARBAND: 1}}}}
    seen = []
    def agent(board, faction, choice):
        seen.append((faction, deepcopy(choice)))
        return {'counts': {rc.REVEALED: 1}}
    state['decision_agent'] = agent
    before = encode(board_copy(state))
    assert validate_free_action_response(state, rc.AEDUI, request, action) is None
    assert seen == [] and encode(board_copy(state)) == before
    result = execute_free_action_plan(state, rc.AEDUI, request, action)
    assert result['executed'] and not result['errors']
    assert len(seen) == 1 and seen[0][0] == rc.AEDUI
    assert seen[0][1]['acting_faction'] == rc.GERMANS
    assert visibility(state, rc.UBII, rc.GERMANS) == (0, 1, 0)
    assert visibility(state, rc.SUGAMBRI, rc.GERMANS) == (1, 0, 0)
    assert '_march_chooser' not in state
    assert validate_state(state) == []


def driver(session):
    def callback(*args):
        pass
    callback.transaction_checkpoint = session.checkpoint
    callback.transaction_restore = session.restore
    return callback


def test_pause_after_formation_saves_dropoff_board_and_replays_exactly(tmp_path):
    state, output = board(), StringIO()
    display = HumanTurnDisplay(output)
    display.remember(state, [rc.ARVERNI])
    session = SeatSession(state, {'seat': rc.ARVERNI}, [], display)
    state['decision_agent'] = session.reactive
    session.import_inbox([{'response': {'counts': {rc.HIDDEN: 1, rc.REVEALED: 1}}}])
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending):
        with _action_transaction(state, driver(session)):
            march(state)
    assert encode(board_copy(state)) == before
    pending = decode(session.data['pending']['request'])
    assert pending['kind'] == MARCH_COHORT and pending['phase'] == 'dropoff'
    assert pending['available'] == {rc.HIDDEN: 1, rc.REVEALED: 1}
    assert visibility(decode(session.data['pending']['board']), rc.NERVII) == (4, 1, 0)
    assert len(session.data['journal']) == 1
    text = output.getvalue()
    assert 'changes since your last decision' in text
    for card in (4, 5):
        assert all(line in text for line in get_card_text(card, state['scenario']).splitlines())
    save_game(state, tmp_path / 'cohort.json', meta=session.meta, log=session.log)
    restored, meta, log = load_game(tmp_path / 'cohort.json')
    resumed = SeatSession(restored, meta, log, HumanTurnDisplay(StringIO()))
    restored['decision_agent'] = resumed.reactive
    resumed.import_inbox([{'response': {'counts': {rc.REVEALED: 1}}}])
    with _action_transaction(restored, driver(resumed)):
        march(restored)
    resumed.finish()
    assert len(log) == 2 and visibility(restored, rc.ATREBATES) == (1, 0, 0)
    replay, entries, seen = board(), iter(log), []
    def recorded(st, faction, request):
        entry = next(entries)
        seen.append((decode(entry['assistant_request']), dict(request, faction=faction)))
        return decode(entry['assistant_response'])
    replay['decision_agent'] = recorded
    march(replay)
    assert all(expected == actual for expected, actual in seen)
    assert next(entries, None) is None
    assert encode(board_copy(replay)) == encode(board_copy(restored))


@pytest.mark.parametrize('counts', [None, {rc.HIDDEN: True, rc.REVEALED: 1},
    {rc.HIDDEN: -1, rc.REVEALED: 3}, {rc.HIDDEN: 3}, {rc.HIDDEN: 1},
    {rc.SCOUTED: 2}, {rc.LEGION: 2}])
def test_invalid_visibility_preserves_pending_inbox_board_and_rng(counts):
    state = board()
    session = SeatSession(state, {'seat': rc.ARVERNI}, [], HumanTurnDisplay(StringIO()))
    state['decision_agent'] = session.reactive
    response = {'counts': counts}
    session.import_inbox([{'response': response}])
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending):
        with _action_transaction(state, driver(session)):
            march(state)
    assert session.error and not session.data['journal']
    assert session.data['queue'] == [{'response': response}]
    assert encode(board_copy(state)) == before


def test_detached_route_preview_never_calls_or_mutates_live_agent():
    from fs_bot.cli.human_plan import _march_routes
    state = board()
    seen = responses(state, [])
    before = encode(board_copy(state))
    routes = _march_routes(state, rc.MORINI, rc.ARVERNI,
                           {rc.LEADER: True, rc.WARBAND: 2})
    assert [rc.NERVII, rc.ATREBATES] in routes
    assert seen == [] and encode(board_copy(state)) == before


def test_cli_choice_accepts_board_command_and_exact_count_without_mutation():
    from fs_bot.cli.march_choices import collect_march_cohort
    from fs_bot.cli.menus import set_board_hook
    state, output, calls = board(), StringIO(), []
    request = {'kind': MARCH_COHORT, 'phase': 'formation', 'region': rc.MORINI,
               'piece_type': rc.WARBAND, 'count': 2,
               'available': {rc.HIDDEN: 2, rc.REVEALED: 2}}
    before = encode(board_copy(state))
    set_board_hook(lambda: calls.append('board'))
    try:
        response = collect_march_cohort(state, rc.ARVERNI, request,
            StringIO('board\n0 Hidden Warband\n'), output)
    finally:
        set_board_hook(None)
    assert response == {'counts': {rc.REVEALED: 2}}
    assert calls == ['board'] and encode(board_copy(state)) == before


def test_terminal_cohort_decisions_show_cards_changes_board_and_replay(monkeypatch, tmp_path):
    from fs_bot.cli import app
    seen = []
    def play_card(state, decision, *, execute):
        agent = state['decision_agent']
        cards = state['current_card'], state['next_card']
        state.clear()
        state.update(board())
        state['decision_agent'] = agent
        state['current_card'], state['next_card'] = cards
        state['resources'][rc.ARVERNI] += 1
        seen.append(cards)
        march(state)
        return {'card': state['current_card'], 'game_over': True}
    monkeypatch.setattr(app, 'play_card', play_card)
    saved, output = tmp_path / 'terminal.json', StringIO()
    assert app.main(['--scenario', rc.SCENARIO_PAX_GALLICA, '--seed', '3',
                     '--bots', 'Romans,Aedui,Belgae', '--save', str(saved)],
        stdin=StringIO('board\n1 Hidden Warband\nboard\n0 Hidden Warband\n'),
        stdout=output) == 0
    state, _, log = load_game(saved)
    assert len(log) == 2 and all(e['reactive'] == MARCH_COHORT for e in log)
    assert visibility(state, rc.NERVII) == (3, 1, 0)
    before_first_prompt = output.getvalue().split('How many Hidden Warband?')[0]
    assert 'changes since your last decision' in before_first_prompt
    for card in seen[0]:
        assert all(line in before_first_prompt
                   for line in get_card_text(card, state['scenario']).splitlines())
    assert output.getvalue().count('AVAILABLE PIECES') >= 3
    assert app.main(['--replay', str(saved)], stdin=StringIO(''), stdout=StringIO()) == 0
