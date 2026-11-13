"""Paid Winter Campaign selection and transit decisions (63/A63)."""

import json
from io import StringIO
from types import SimpleNamespace

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, get_leader_in_region, place_piece
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT, draw_card, get_sop_factions
from fs_bot.engine.march_choices import MARCH_DROPOFF
from fs_bot.engine.victory import check_any_victory
from fs_bot.engine.winter_campaign import validate_human_plan, winter_campaign_after_harvest
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity
from fs_bot.tests.test_action_window_frontends import leave_timing_unchanged
from fs_bot.tools import llm_seat
from fs_bot.tools.seat_session import SeatSession, board_copy


def _acquire_campaign(state, owner, card):
    state['current_card'] = card
    result = execute_decision(state, owner, {'action': ACTION_EVENT, 'player_action': {
        'command': rc.FIRST_DID_EVENT, 'details': {
            'card_id': card, 'text_preference': rc.EVENT_SHADED,
            'event_params': {'faction': owner} if card == 63 else {}}}})
    assert result['executed'], result


def _campaign_position(owner, scenario, edition, card):
    state = build_initial_state(scenario, seed=19)
    state['card_edition'] = edition
    state['non_player_factions'] = set(get_sop_factions(state)) - {owner}
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    state['resources'][owner] = 20
    _acquire_campaign(state, owner, card)
    state['current_card'] = rc.WINTER_CARD
    return state


def _battle_plan(count):
    return {'command': rc.CMD_BATTLE, 'details': {'battle_plan': [
        {'region': rc.CARNUTES, 'target': rc.BELGAE} for _ in range(count)]}}


@pytest.mark.parametrize('scenario,edition,card', [
    (rc.SCENARIO_GREAT_REVOLT, 'legacy', 63),
    (rc.SCENARIO_GREAT_REVOLT, 'second-edition', 63),
    (rc.SCENARIO_ARIOVISTUS, 'second-edition', 'A63'),
])
def test_repeated_battle_region_retries_and_two_separate_battles_are_paid(scenario, edition, card):
    state = _campaign_position(rc.AEDUI, scenario, edition, card)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 12)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 10, piece_state=rc.REVEALED)
    before = encode(board_copy(state))
    budgets = []

    def agent(board, owner, request):
        if request['kind'] != 'winter_campaign':
            return None
        assert owner == rc.AEDUI and request['card_id'] == card
        budgets.append(request['remaining_actions'])
        if len(budgets) == 1:
            return _battle_plan(2)
        if len(budgets) == 2:
            assert request['errors'] == ['Invalid Winter Campaign plan: '
                                         'Select each Battle Region only once (§3.1).']
            assert encode(board_copy(board)) == before
        else:
            assert count_pieces(board, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 10
            assert count_pieces(board, rc.CARNUTES, rc.BELGAE, rc.WARBAND) == 4
            assert board['resources'][owner] == 19
        return _battle_plan(1)

    state['decision_agent'] = agent
    with pytest.raises(ValueError, match='Select each Battle Region only once'):
        validate_human_plan(state, rc.AEDUI, _battle_plan(2))
    assert encode(board_copy(state)) == before
    result = winter_campaign_after_harvest(state)

    assert budgets == [2, 2, 1]
    assert [entry['actions'] for entry in result['actions']] == [1, 1]
    assert result['remaining_actions'] == 0
    assert count_pieces(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND) == 0
    assert state['resources'][rc.AEDUI] == 18


def test_terminal_campaign_march_offers_dropoff_and_charges_one_action():
    state = _campaign_position(rc.ARVERNI, rc.SCENARIO_GREAT_REVOLT, 'second-edition', 63)
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 4)
    stdin = StringIO('\n'.join([
        'Command: March', rc.CARNUTES, 'Mandubii → Sequani', 'all 4', 'y',
        'Leave Arverni Hidden Warband (up to 4)', '2', 'Finish Winter Campaign',
    ]) + '\n')
    stdout = StringIO()
    agent = make_cli_reactive([rc.ARVERNI], stdin, stdout)
    agent.supports_action_windows = False
    state['decision_agent'] = agent

    result = winter_campaign_after_harvest(state)
    assert 'drop off pieces in Mandubii before Marching to Sequani?' in stdout.getvalue()
    assert result['remaining_actions'] == 1
    assert len(result['actions']) == 1 and result['actions'][0]['actions'] == 1
    assert state['resources'][rc.ARVERNI] == 19
    assert count_pieces(state, rc.MANDUBII, rc.ARVERNI, rc.WARBAND) == 2
    assert count_pieces(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND) == 2
    assert get_leader_in_region(state, rc.SEQUANI, rc.ARVERNI) == rc.VERCINGETORIX


def test_campaign_march_and_suborn_can_pair_across_britannia():
    state = _campaign_position(rc.AEDUI, rc.SCENARIO_GREAT_REVOLT, 'second-edition', 63)
    for region in (rc.MORINI, rc.CARNUTES):
        place_piece(state, region, rc.AEDUI, rc.WARBAND)
    plan = {'command': rc.CMD_MARCH, 'sa': rc.SA_SUBORN, 'details': {
        'origins': [rc.MORINI], 'destinations': [rc.BRITANNIA],
        'routes': {rc.MORINI: [rc.BRITANNIA]},
        'suborn_plan': [{'region': rc.CARNUTES, 'actions': [{'action': 'place_warband'}]}]}}
    assert validate_human_plan(state, rc.AEDUI, plan) == 2

    def agent(board, owner, request):
        if request['kind'] == 'winter_campaign':
            return plan
        pytest.fail(f"Unexpected decision during a one-hop Campaign March: {request['kind']}")

    agent.supports_march_dropoffs = True
    agent.supports_resource_transfers = True
    state['decision_agent'] = agent
    result = winter_campaign_after_harvest(state)

    assert result['remaining_actions'] == 0 and result['actions'][0]['actions'] == 2
    assert state['resources'][rc.AEDUI] == 18
    assert count_pieces(state, rc.BRITANNIA, rc.AEDUI, rc.WARBAND) == 1
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 2


def _save_winter(tmp_path, state, owner, card, next_card):
    # The other Winter in the controlled deck keeps this one nonfinal.
    state['non_player_factions'] = set(get_sop_factions(state)) - {owner}
    _acquire_campaign(state, owner, card)
    state.update(played_cards=[card], deck=[rc.WINTER_CARD, next_card, rc.WINTER_CARD])
    draw_card(state)
    assert check_any_victory(state) is None
    path = tmp_path / 'live' / 'save.json'
    path.parent.mkdir()
    args = SimpleNamespace(dir=str(path.parent), output_dir=str(tmp_path / 'replay'))
    save_game(state, path, meta={'seat': owner, 'scenario': state['scenario'], 'seed': 19,
                                'card_edition': state['card_edition']}, log=[])
    assert llm_seat.cmd_play(args) == 0
    leave_timing_unchanged(args)
    while _saved(args)[1]['kind'] in ('quarters_plan', 'agreement'):
        _submit(args, {'use_default': True})
    assert _saved(args)[1]['kind'] == 'winter_campaign'
    return args


def _saved(args):
    state, meta, log = load_game(f'{args.dir}/save.json', validate=True)
    pending = meta['assistant_session']['pending']
    assert pending is not None
    assert check_structural_integrity(state) == []
    return state, decode(pending['request']), pending, log


def _submit(args, response):
    _, _, pending, _ = _saved(args)
    assert llm_seat.cmd_submit(SimpleNamespace(
        dir=args.dir, decision_id=pending['id'], response=json.dumps(response))) == 0
    leave_timing_unchanged(args)


def _verify_replay(args):
    assert llm_seat.cmd_replay(args) == 0
    final, _, pending, log = _saved(args)
    replay, meta, replay_log = load_game(f'{args.output_dir}/save.json', validate=True)
    assert encode(replay) == encode(final) and replay_log == log
    assert meta['assistant_session']['pending'] == pending


@pytest.mark.parametrize('scenario,card', [
    (rc.SCENARIO_GREAT_REVOLT, 63),
    (rc.SCENARIO_ARIOVISTUS, 'A63'),
])
def test_saved_winter_rejects_duplicate_battle_and_replays_two_legal_actions(
        tmp_path, scenario, card):
    state = setup_scenario(scenario, seed=19, card_edition='second-edition')
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 6)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 5, piece_state=rc.REVEALED)
    args = _save_winter(tmp_path, state, rc.AEDUI, card, 37)
    before, request, original, log = _saved(args)
    assert request['remaining_actions'] == 2

    _submit(args, _battle_plan(2))
    rejected, _, pending, rejected_log = _saved(args)
    assert pending == original and log == rejected_log
    assert encode(rejected) == encode(before)
    assert llm_seat.cmd_play(args) == 0
    assert _saved(args)[2] == original

    for remaining in (2, 1):
        _, request, pending, _ = _saved(args)
        assert request['kind'] == 'winter_campaign' and request['remaining_actions'] == remaining
        live = decode(pending['board'])
        assert count_pieces(live, rc.CARNUTES, rc.BELGAE, rc.WARBAND) == (5 if remaining == 2 else 2)
        _submit(args, _battle_plan(1))
        request = _saved(args)[1]
        while request['kind'] in ('agreement', 'loss_order'):
            response = False if request.get('request_type') == 'retreat_into_control' else {
                'use_default': True}
            _submit(args, response)
            request = _saved(args)[1]

    final, request, _, log = _saved(args)
    assert request['kind'] == 'turn'
    assert count_pieces(final, rc.CARNUTES, rc.BELGAE, rc.WARBAND) == 0
    assert final['resources'][rc.AEDUI] == decode(original['board'])['resources'][rc.AEDUI] - 2
    assert [decode(entry['assistant_response']) for entry in log
            if entry.get('reactive') == 'winter_campaign'] == [_battle_plan(1), _battle_plan(1)]
    _verify_replay(args)


@pytest.mark.parametrize('legacy', [False, True], ids=['live-dropoff', 'older-default'])
def test_saved_winter_march_pauses_at_dropoff_and_replays(tmp_path, monkeypatch, legacy):
    if legacy:
        monkeypatch.setattr(SeatSession, 'supports_march_dropoffs', False)
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=19, card_edition='second-edition')
    args = _save_winter(tmp_path, state, rc.ARVERNI, 63, 19)
    before, _, original, log = _saved(args)
    start = decode(original['board'])
    plan = {'command': rc.CMD_MARCH, 'details': {
        'origins': [rc.CARNUTES], 'destinations': [rc.SEQUANI],
        'routes': {rc.CARNUTES: [rc.MANDUBII, rc.SEQUANI]},
        'groups': {rc.CARNUTES: {rc.WARBAND: 4, rc.LEADER: True}}}}
    _submit(args, plan)
    leave = {'faction': rc.ARVERNI, 'piece_type': rc.WARBAND,
             'piece_state': rc.HIDDEN, 'count': 2}

    if not legacy:
        rolled_back, request, pending, paused_log = _saved(args)
        assert request['kind'] == MARCH_DROPOFF
        assert (request['region'], request['destination']) == (rc.MANDUBII, rc.SEQUANI)
        assert request['pieces'] == [dict(leave, count=4)]
        assert encode(rolled_back) == encode(before) and paused_log == log
        live = decode(pending['board'])
        assert get_leader_in_region(live, rc.MANDUBII, rc.ARVERNI) == rc.VERCINGETORIX
        assert live['resources'][rc.ARVERNI] == start['resources'][rc.ARVERNI] - 1
        _submit(args, {'dropoffs': [dict(leave, count=5)]})
        assert _saved(args)[2] == pending
        assert llm_seat.cmd_play(args) == 0 and _saved(args)[2] == pending
        _submit(args, {'dropoffs': [leave]})

    _, request, _, _ = _saved(args)
    assert request['kind'] == 'harassment_loss' and request['harasser'] == rc.AEDUI
    assert request['departing_pieces'][rc.WARBAND] == (4 if legacy else 2)
    _submit(args, {'choice': rc.WARBAND})
    rolled_back, request, _, paused_log = _saved(args)
    assert request['kind'] == 'winter_campaign' and request['remaining_actions'] == 1
    assert encode(rolled_back) == encode(before) and paused_log == log
    _submit(args, {'decline': True})

    final, request, _, log = _saved(args)
    assert request['kind'] == 'turn'
    for region, delta in ((rc.MANDUBII, 0 if legacy else 2), (rc.SEQUANI, 3 if legacy else 1)):
        assert (count_pieces(final, region, rc.ARVERNI, rc.WARBAND)
                - count_pieces(start, region, rc.ARVERNI, rc.WARBAND)) == delta
    assert final['resources'][rc.ARVERNI] == start['resources'][rc.ARVERNI] - 1
    assert get_leader_in_region(final, rc.SEQUANI, rc.ARVERNI) == rc.VERCINGETORIX
    assert sum(entry.get('reactive') == MARCH_DROPOFF for entry in log) == int(not legacy)
    monkeypatch.setattr(SeatSession, 'supports_march_dropoffs', True)
    _verify_replay(args)
