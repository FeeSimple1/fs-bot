"""Each successful Seize die grants its Rally before the next die/Forage."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.commands.seize import seize_in_region
from fs_bot.engine import execute
from fs_bot.engine.free_actions import validate_free_action_response
from fs_bot.map.map_data import get_adjacent
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state


R = rc.CARNUTES


def state(scenario=rc.SCENARIO_GREAT_REVOLT):
    board = build_initial_state(scenario, seed=81)
    board['non_player_factions'] = set()
    board['resources'] = {f: 0 for f in rc.FACTIONS}
    place_piece(board, R, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(board, rc.BITURIGES, rc.ARVERNI, rc.ALLY)
    board['tribes'][rc.TRIBE_BITURIGES]['allied_faction'] = rc.ARVERNI
    refresh_all_control(board)
    return board


def rally(region, count=1):
    return {'command': rc.CMD_RALLY, 'sa': 'No SA', 'regions': [region],
            'details': {'rally_plan': {'steps': [
                {'region': region, 'action': 'place_warbands', 'count': count}]}}}


def rolls(monkeypatch, values):
    outcomes = iter(values)
    def roll(board, faction):
        value = next(outcomes)
        return {'faction': faction, 'roll': value, 'can_rally': value <= 3}
    monkeypatch.setattr('fs_bot.commands.seize.seize_rally_roll', roll)


def test_human_rallies_resolve_after_each_roll_before_forage(monkeypatch):
    board = state()
    calls = []
    def roll(current, faction):
        calls.append(('roll', faction))
        if faction == rc.BELGAE:
            assert count_pieces(current, rc.BITURIGES, rc.ARVERNI, rc.WARBAND) == 1
        return {'faction': faction, 'roll': 1, 'can_rally': True}
    monkeypatch.setattr('fs_bot.commands.seize.seize_rally_roll', roll)
    def choose(current, faction, request):
        assert current['resources'][rc.ROMANS] == 0
        assert request['source'] == 'seize' and request['roll'] == 1
        assert request['source_region'] == R and request['tribe'] == rc.TRIBE_CARNUTES
        assert set(request['allowed_regions']) == set(get_adjacent(R, current['scenario']))
        calls.append(('rally', faction))
        return rally(rc.BITURIGES if faction == rc.ARVERNI else rc.ATREBATES)
    board['decision_agent'] = choose
    result = seize_in_region(board, R, [rc.TRIBE_CARNUTES],
                             rally_resolver=execute._resolve_seize_rally)
    assert calls == [('roll', rc.ARVERNI), ('rally', rc.ARVERNI),
                     ('roll', rc.BELGAE), ('rally', rc.BELGAE)]
    assert count_pieces(board, rc.ATREBATES, rc.BELGAE, rc.WARBAND) == 1
    assert board['resources'][rc.ARVERNI] == board['resources'][rc.BELGAE] == 0
    assert board['resources'][rc.ROMANS] == result['forage_resources'] == 8
    assert all(row['rally_result']['executed'] for row in result['rally_opportunities'][0]['rolls'])
    assert validate_state(board) == []


def test_execute_seize_grants_separate_rally_for_each_dispersed_tribe(monkeypatch):
    board = state()
    rolls(monkeypatch, [1, 6, 2, 6])
    requests = []
    def choose(current, faction, request):
        requests.append(deepcopy(request))
        return rally(rc.BITURIGES)
    board['decision_agent'] = choose
    result = execute._execute_seize(board, rc.ROMANS, {'regions': [R], 'details': {
        'disperse_regions': [R], 'no_harassment': True}})
    assert result['executed'] and result['errors'] == []
    assert len(requests) == result['tribes_dispersed_total'] == 2
    assert {r['tribe'] for r in requests} == {rc.TRIBE_CARNUTES, rc.TRIBE_AULERCI}
    assert count_pieces(board, rc.BITURIGES, rc.ARVERNI, rc.WARBAND) == 2
    assert result['regions'][0]['rally_opportunities'][1]['rolls'][0]['rally_result']['executed']
    assert validate_state(board) == []


def test_success_may_decline_and_failed_roll_does_not_request(monkeypatch):
    board = state()
    rolls(monkeypatch, [6, 3])
    asked = []
    def choose(current, faction, request):
        asked.append(faction)
        return {'decline': True}
    board['decision_agent'] = choose
    result = seize_in_region(board, R, [rc.TRIBE_CARNUTES],
                             rally_resolver=execute._resolve_seize_rally)
    assert asked == [rc.BELGAE]
    rows = result['rally_opportunities'][0]['rolls']
    assert 'rally_result' not in rows[0]
    assert rows[1]['rally_result']['declined_no_effect']


def test_grant_excludes_source_nonadjacent_devastated_and_special_activity(monkeypatch):
    board = state()
    board['markers'].setdefault(rc.BITURIGES, {})[rc.MARKER_DEVASTATED] = True
    place_piece(board, rc.BITURIGES, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    rolls(monkeypatch, [1, 6])
    def choose(current, faction, request):
        # The explicit Seize exclusion holds even at Vercingetorix.
        assert rc.BITURIGES not in request['allowed_regions']
        for forbidden in (R, rc.BITURIGES, rc.PROVINCIA):
            assert validate_free_action_response(current, faction, request, rally(forbidden))
        action = rally(rc.PICTONES)
        action.update(sa='Devastate', sa_regions=[rc.PICTONES])
        assert validate_free_action_response(current, faction, request, action)
        return {'decline': True}
    board['decision_agent'] = choose
    seize_in_region(board, R, [rc.TRIBE_CARNUTES], rally_resolver=execute._resolve_seize_rally)


def test_nonplayer_success_actually_executes_free_rally(monkeypatch):
    board = state()
    board['non_player_factions'] = {rc.ARVERNI, rc.BELGAE}
    rolls(monkeypatch, [1, 6])
    result = seize_in_region(board, R, [rc.TRIBE_CARNUTES],
                             rally_resolver=execute._resolve_seize_rally)
    granted = result['rally_opportunities'][0]['rolls'][0]['rally_result']
    assert granted['executed'] and granted['errors'] == []
    assert any(count_pieces(board, region, rc.ARVERNI) > 0
               for region in get_adjacent(R, board['scenario']))
    assert board['resources'][rc.ARVERNI] == 0
    assert validate_state(board) == []


def test_ariovistus_arverni_uses_game_run_rally_without_human_request(monkeypatch):
    board = state(rc.SCENARIO_ARIOVISTUS)
    rolls(monkeypatch, [1, 6])
    board['decision_agent'] = lambda *_: pytest.fail('Game-run Arverni is not a human choice')
    result = seize_in_region(board, R, [rc.TRIBE_CARNUTES],
                             rally_resolver=execute._resolve_seize_rally)
    granted = result['rally_opportunities'][0]['rolls'][0]['rally_result']
    assert granted['executed'] and granted['result']['allies_placed']
    assert count_pieces(board, R, rc.ARVERNI) == 0
    assert validate_state(board) == []


def test_invalid_later_rally_rolls_back_earlier_rally_markers_and_rng():
    # Seed 4 rolls 2 then 3: both factions receive a Rally. Invalid second
    # input restores this whole Region, including its already rolled dice.
    board = state()
    board['rng'].seed(4)
    before = encode(board)
    def choose(current, faction, request):
        return rally(rc.BITURIGES if faction == rc.ARVERNI else rc.PROVINCIA)
    board['decision_agent'] = choose
    with pytest.raises(ValueError, match='Regions granted'):
        seize_in_region(board, R, [rc.TRIBE_CARNUTES],
                         rally_resolver=execute._resolve_seize_rally)
    assert encode({k: v for k, v in board.items() if k != 'decision_agent'}) == before


def test_pending_rally_restores_dispersal_and_rng():
    from fs_bot.tools.seat_session import DecisionPending
    board = state()
    board['rng'].seed(4)
    before = encode(board)
    def pending(*_):
        raise DecisionPending()
    board['decision_agent'] = pending
    with pytest.raises(DecisionPending):
        seize_in_region(board, R, [rc.TRIBE_CARNUTES],
                         rally_resolver=execute._resolve_seize_rally)
    assert encode({k: v for k, v in board.items() if k != 'decision_agent'}) == before


def test_first_rally_receipt_replays_after_save_before_second_rally(tmp_path):
    from io import StringIO
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.state.serialize import decode, load_game, save_game
    from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy

    def session_for(board, meta=None, log=None):
        session = SeatSession(board, meta if meta is not None else {'seat': rc.ARVERNI},
                              log if log is not None else [], HumanTurnDisplay(StringIO()))
        board['decision_agent'] = session.reactive
        def driver(*args):
            pass
        driver.transaction_checkpoint = session.checkpoint
        driver.transaction_restore = session.restore
        return session, driver

    def run(board, driver):
        with _action_transaction(board, driver):
            return execute._execute_seize(board, rc.ROMANS, {
                'regions': [R], 'details': {'disperse_regions': [R], 'no_harassment': True}})

    board = state()
    board['rng'].seed(28)  # Arverni successes, Belgae failures: 1,6,2,5.
    origin, before = deepcopy(board), encode(board)
    session, driver = session_for(board)
    session.import_inbox([{'response': rally(rc.BITURIGES)}])
    with pytest.raises(DecisionPending):
        run(board, driver)
    assert encode(board_copy(board)) == before
    pending = deepcopy(session.data['pending'])
    request = decode(pending['request'])
    assert request['source'] == 'seize' and request['tribe'] == rc.TRIBE_AULERCI
    assert request['roll'] == 2
    accepted = deepcopy(session.data['journal'][0])
    save_game(board, tmp_path / 'seize.json', meta=session.meta, log=session.log)
    restored, meta, log = load_game(tmp_path / 'seize.json', validate=True)
    resumed, resumed_driver = session_for(restored, meta, log)
    resumed.import_inbox({'decision_id': pending['id'], 'response': rally(rc.BITURIGES)})
    result = run(restored, resumed_driver)
    resumed.finish()
    assert resumed.log[0] == accepted
    assert count_pieces(restored, rc.BITURIGES, rc.ARVERNI, rc.WARBAND) == 2
    replay, replay_driver = session_for(origin)
    replay.data['queue'] = [SeatSession._inbox_entry(entry) for entry in resumed.log]
    replay.data['expected'] = [{'id': entry['assistant_id'],
        'signature': entry['assistant_signature'], 'request': entry['assistant_request'],
        'action_windows_version': entry.get('assistant_action_windows_version', 0)}
        for entry in resumed.log]
    assert run(origin, replay_driver) == result
    replay.finish()
    assert replay.log == resumed.log
    assert encode(board_copy(origin)) == encode(board_copy(restored))
