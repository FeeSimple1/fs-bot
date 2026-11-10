"""One player can run a printed pair (§1.5.1 / A1.5.1)."""

import json
from io import StringIO
from types import SimpleNamespace

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import get_leader_in_region, place_piece
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cli import app
from fs_bot.cli.display import format_victory_state
from fs_bot.engine import resource_transfers as gifts
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_COMMAND, ACTION_EVENT, ACTION_PASS, resolve_card_turn
from fs_bot.engine.interlude import run_interlude
from fs_bot.engine.victory import check_any_victory, determine_final_ranking, player_standings
from fs_bot.engine.winter import victory_phase
from fs_bot.state import player_ownership as owners
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools import llm_seat
from fs_bot.tools.seat_session import validate_response


def paired(scenario=rc.SCENARIO_GREAT_REVOLT):
    state = build_initial_state(scenario, seed=42)
    owners.install(state, {member: str(index) for index, pair in
                           enumerate(owners.spare_pairs(scenario)) for member in pair})
    return state


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
def test_setup_accepts_both_printed_pairs_and_preserves_their_player_ids(scenario):
    first, second = owners.spare_pairs(scenario)
    assigned = {**dict.fromkeys(first, 'First'), **dict.fromkeys(second, 'Second')}
    state = setup_scenario(scenario, seed=4, faction_owners=assigned)
    assert owners.factions_of(state, 'First') == first
    assert owners.factions_of(state, 'Second') == second
    assert state['non_player_factions'] == set()
    assert len(determine_final_ranking(state)) == 2
    assert validate_state(state) == []


@pytest.mark.parametrize('assigned', [
    {rc.ROMANS: 'One', rc.BELGAE: 'One'},
    {rc.ROMANS: 'One', rc.AEDUI: 'One', rc.BELGAE: 'One'},
    {rc.GERMANS: 'Phase Faction'},
    {rc.AEDUI: ''},
])
def test_invalid_ownership_assignments_fail_at_setup(assigned):
    with pytest.raises(ValueError):
        setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=4, faction_owners=assigned)


def test_saved_ownership_cannot_conflict_with_nonplayer_control(tmp_path):
    from fs_bot.state.serialize import SaveFileError

    state = paired()
    state['non_player_factions'].add(rc.AEDUI)
    assert 'Player ownership and Non-player Factions disagree.' in validate_state(state)
    path = tmp_path / 'bad.json'
    save_game(state, path)
    with pytest.raises(SaveFileError, match='ownership'):
        load_game(path, validate=True)


@pytest.mark.parametrize('assigned,leader', [
    ({rc.BELGAE: 'One', rc.AEDUI: 'Two', rc.ROMANS: 'Three'}, rc.AMBIORIX),
    ({rc.ARVERNI: 'One', rc.BELGAE: 'One'}, rc.SUCCESSOR),
    ({rc.ROMANS: 'One', rc.AEDUI: 'One'}, rc.AMBIORIX),
    ({rc.ROMANS: 'One', rc.AEDUI: 'One', rc.ARVERNI: 'Two', rc.BELGAE: 'Two'}, rc.AMBIORIX),
])
def test_great_revolt_ambiorix_uses_the_players_actual_assignments(assigned, leader):
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=4, faction_owners=assigned)
    assert get_leader_in_region(state, rc.SUGAMBRI, rc.BELGAE) == leader


def test_ordinary_pair_passes_only_when_both_factions_meet_threshold():
    state = paired(rc.SCENARIO_PAX_GALLICA)
    assert check_any_victory(state) is None  # Romans pass and Aedui tie at zero.
    assert not victory_phase(state)['game_over']
    assert 'Romans + Aedui) margin=+0' in format_victory_state(state)
    final = victory_phase(state, is_final=True)
    assert final['winner_factions'] == [rc.ROMANS, rc.AEDUI]
    assert final['rankings'] == [(rc.AEDUI, 0), (rc.BELGAE, -15)]
    assert _ally_tribe(state, rc.TRIBE_AEDUI, rc.AEDUI)
    result = victory_phase(state)
    assert result['game_over'] and result['winner'] == rc.AEDUI
    assert result['winner_player'] == '0' and result['winner_factions'] == [rc.ROMANS, rc.AEDUI]
    assert result['player_rankings'][0]['margin'] == 1


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_PAX_GALLICA])
def test_only_great_revolt_gives_arverni_belgae_the_higher_margin(scenario):
    state = paired(scenario)
    for region in (rc.MORINI, rc.NERVII, rc.ATREBATES, rc.CARNUTES,
                   rc.MANDUBII, rc.TREVERI, rc.VENETI):
        place_piece(state, region, rc.BELGAE, rc.WARBAND)
    for tribe in (rc.TRIBE_MENAPII, rc.TRIBE_EBURONES):
        assert _ally_tribe(state, tribe, rc.BELGAE)
    rebels = next(row for row in player_standings(state) if rc.ARVERNI in row['factions'])
    if scenario == rc.SCENARIO_GREAT_REVOLT:
        assert rebels['margin'] == 2 and rebels['passed']
        assert victory_phase(state)['winner_factions'] == [rc.ARVERNI, rc.BELGAE]
    else:
        assert rebels['margin'] == -8 and not rebels['passed']
        assert not victory_phase(state)['game_over']


def test_nonplayer_threshold_still_defeats_a_pair_with_a_higher_margin():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=42)
    owners.install(state, {rc.ROMANS: 'Pair', rc.AEDUI: 'Pair', rc.ARVERNI: 'Other'})
    for region in (rc.MORINI, rc.NERVII, rc.ATREBATES, rc.CARNUTES,
                   rc.MANDUBII, rc.TREVERI, rc.VENETI):
        place_piece(state, region, rc.BELGAE, rc.WARBAND)
    assert _ally_tribe(state, rc.TRIBE_MENAPII, rc.BELGAE)
    for tribe in (rc.TRIBE_AEDUI, rc.TRIBE_SEQUANI, rc.TRIBE_BITURIGES):
        assert _ally_tribe(state, tribe, rc.AEDUI)
    result = victory_phase(state)
    assert result['game_over'] and result['winner'] == rc.BELGAE
    assert result['winner_factions'] == [rc.BELGAE] and result['winner_player'] is None


@pytest.mark.parametrize('belgae_bot', [False, True])
def test_final_winter_uses_the_faction_supplying_the_pair_margin_for_ties(belgae_bot):
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=42)
    assigned = {rc.ROMANS: 'Pair', rc.AEDUI: 'Pair', rc.ARVERNI: 'Other'}
    if not belgae_bot:
        assigned[rc.BELGAE] = 'Third'
    owners.install(state, assigned)
    for region in (rc.MORINI, rc.NERVII, rc.ATREBATES, rc.CARNUTES,
                   rc.MANDUBII, rc.TREVERI, rc.VENETI):
        place_piece(state, region, rc.BELGAE, rc.WARBAND)
    assert check_any_victory(state) is None
    assert victory_phase(state, is_final=True)['winner'] == (rc.BELGAE if belgae_bot else rc.AEDUI)


def gift_position():
    state = paired()
    state['current_card'] = state['current_card_id'] = 16
    state['resources'].update({rc.ROMANS: 10, rc.AEDUI: 10})
    for faction in state['eligibility']:
        state['eligibility'][faction] = rc.ELIGIBLE if faction == rc.AEDUI else rc.INELIGIBLE
    assert _ally_tribe(state, rc.TRIBE_AEDUI, rc.AEDUI)
    return state


def rally(*transfers):
    return {'command': rc.CMD_RALLY, 'details': {
        'transfers': list(transfers), 'rally_plan': {'warbands': [rc.AEDUI_REGION]}}}


def give(to, amount):
    return {'to': to, 'amount': amount}


def test_typed_and_raw_gifts_share_the_cap_for_one_command():
    state = gift_position()
    plan = rally(give(rc.ROMANS, 3), give(rc.ROMANS, 2))
    decision = {'action': ACTION_COMMAND, 'player_action': plan}
    request = {'kind': 'turn', 'options': [ACTION_COMMAND], 'faction': rc.AEDUI}
    before = encode(state)
    with pytest.raises(ValueError, match='four Resources'):
        validate_response(state, request, decision)
    assert encode(state) == before
    result = execute_decision(state, rc.AEDUI, decision)
    assert result['executed'] and result['transfers'][0]['given'] == 3
    assert 'four Resources' in result['transfers'][1]['error']
    assert state['resources'][rc.ROMANS] == 13 and gifts.FRAME not in state
    fresh = {'action': ACTION_COMMAND, 'player_action': rally(give(rc.ROMANS, 4))}
    assert execute_decision(state, rc.AEDUI, fresh)['transfers'][0]['given'] == 4


def test_gifts_in_both_directions_share_one_action_allowance():
    state = gift_position()
    offered = []

    def agent(board, faction, request):
        if request['kind'] != gifts.KIND:
            return None
        offered.append((faction, request['window']['stage'], dict(request['recipients'])))
        if request['window']['stage'] == 'action_start':
            if faction == rc.ROMANS:
                return {'transfers': [give(rc.AEDUI, 2)], 'defer': True}
            if faction == rc.AEDUI:
                return {'transfers': [give(rc.ROMANS, 1)], 'defer': True}
        return {'transfers': []}

    agent.supports_resource_transfers = True
    state['decision_agent'] = agent
    decision = {'action': ACTION_COMMAND, 'player_action': rally(give(rc.ROMANS, 1))}
    result = resolve_card_turn(state, lambda *_: decision, execute=True)['actions_taken'][rc.AEDUI]['execution']
    assert result['executed']
    assert [receipt['given'] for receipt in result['transfers']] == [1, 2, 1]
    assert offered[0] == (rc.ROMANS, 'action_start', {rc.AEDUI: 3})
    assert offered[1][2][rc.ROMANS] == 1
    assert any(faction == rc.AEDUI and stage != 'action_start' and rc.ROMANS not in recipients
               for faction, stage, recipients in offered)
    assert gifts.FRAME not in state


def test_event_voluntary_gifts_use_cap_and_winter_gifts_use_full_stock():
    state = gift_position()
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    event = {'action': ACTION_EVENT, 'player_action': {'command': 'Event', 'details': {
        'card_id': 16, 'text_preference': rc.EVENT_UNSHADED, 'event_params': {'region': rc.PROVINCIA},
        'transfers': [give(rc.AEDUI, 4), give(rc.AEDUI, 1)]}}}
    result = execute_decision(state, rc.ROMANS, event)
    assert result['executed'] and result['transfers'][0]['given'] == 4, result
    assert 'four Resources' in result['transfers'][1]['error']
    assert gifts.request_for(state, rc.AEDUI, 'harvest', 'before_harvest')['recipients'][rc.ROMANS] == 14
    with gifts.sequence(state, rc.ROMANS, live=False):
        assert gifts.give(state, rc.AEDUI, rc.ROMANS, 9, 'quarters')['given'] == 9
        assert gifts.shared_allowance(state, rc.ROMANS, rc.AEDUI, gifts.SEQUENCE) == 4


def test_interlude_moves_the_german_player_to_arverni_and_keeps_belgae(tmp_path):
    state = setup_scenario(rc.SCENARIO_GALLIC_WAR, seed=4,
                           faction_owners={rc.GERMANS: 'North', rc.BELGAE: 'North'})
    run_interlude(state)
    assert owners.factions_of(state, 'North') == (rc.ARVERNI, rc.BELGAE)
    assert state['non_player_factions'] == {rc.ROMANS, rc.AEDUI}
    assert validate_state(state) == []
    path = tmp_path / 'save.json'
    save_game(state, path, meta={'scenario': rc.SCENARIO_GALLIC_WAR,
                                'seat': rc.GERMANS, 'player_id': 'North'})
    assert llm_seat.cmd_play(SimpleNamespace(dir=str(tmp_path))) == 0
    restored, meta, _ = load_game(path, validate=True)
    assert meta['seat'] == rc.ARVERNI
    assert {faction for faction, mode in meta['faction_modes'].items() if mode == 'human'} == {rc.ARVERNI, rc.BELGAE}
    assert restored[owners.FIELD] == state[owners.FIELD]


def test_terminal_wizard_and_replay_keep_the_two_players_distinct(tmp_path, monkeypatch):
    def pause(*args, **kwargs):
        raise EOFError

    monkeypatch.setattr(app, 'play_card', pause)
    initial, replay = tmp_path / 'initial.json', tmp_path / 'replay.json'
    assert app.main(['--scenario', rc.SCENARIO_GREAT_REVOLT, '--seed', '4', '--save', str(initial)],
                    stdin=StringIO('Human with Aedui\nHuman with Belgae\n'), stdout=StringIO()) == 0
    first, meta, _ = load_game(initial, validate=True)
    assert meta[owners.SETUP_FIELD] == first[owners.FIELD]
    assert first[owners.FIELD] == {rc.ROMANS: 'Player 1', rc.AEDUI: 'Player 1',
                                  rc.ARVERNI: 'Player 2', rc.BELGAE: 'Player 2'}
    assert app.main(['--replay', str(initial), '--save', str(replay)],
                    stdin=StringIO(), stdout=StringIO()) == 0
    assert encode(load_game(replay, validate=True)[0]) == encode(first)


def test_terminal_pair_flag_combines_human_seats_and_rejects_bot_conflicts(tmp_path, monkeypatch):
    def pause(*args, **kwargs):
        raise EOFError

    monkeypatch.setattr(app, 'play_card', pause)
    save = tmp_path / 'paired.json'
    args = ['--scenario', rc.SCENARIO_GREAT_REVOLT, '--seed', '4', '--pair', 'Romans,Aedui']
    assert app.main([*args, '--bots', rc.ARVERNI, '--save', str(save)],
                    stdin=StringIO(), stdout=StringIO()) == 0
    state, _, _ = load_game(save, validate=True)
    assert owners.shares_player(state, rc.ROMANS, rc.AEDUI)
    assert not owners.shares_player(state, rc.ROMANS, rc.BELGAE)
    assert state['non_player_factions'] == {rc.ARVERNI}
    output = StringIO()
    assert app.main([*args, '--bots', rc.AEDUI], stdin=StringIO(), stdout=output) == 2
    assert 'cannot be both paired and a bot' in output.getvalue()


def test_assistant_pair_owns_both_factions_and_keeps_gift_allowance_on_replay(tmp_path):
    from fs_bot.tests.test_action_window_frontends import TIMING_DEFAULTS

    live = tmp_path / 'live'
    args = SimpleNamespace(scenario=rc.SCENARIO_GREAT_REVOLT, seed=4,
                           seat='Aedui,Romans', dir=str(live), output_dir=str(tmp_path / 'replay'))
    llm_seat.cmd_init(args)
    path = live / 'save.json'
    _, meta, _ = load_game(path, validate=True)
    # One fixed card reaches each of the paired turns and a mid-action pause.
    state = gift_position()
    owners.install(state, {rc.ROMANS: meta['player_id'], rc.AEDUI: meta['player_id']})
    state['eligibility'][rc.ROMANS] = rc.ELIGIBLE
    meta.pop('assistant_session')
    save_game(state, path, meta=meta, log=[])
    assert llm_seat.cmd_play(args) == 0

    turns, sent, reloaded = [], False, False
    for _ in range(35):
        current, saved, log = load_game(path, validate=True)
        pending = saved['assistant_session']['pending']
        if pending is None:
            break
        request = decode(pending['request'])
        faction, kind = request['faction'], request['kind']
        if kind == 'turn':
            turns.append(faction)
            response = ({'action': ACTION_PASS} if faction == rc.ROMANS else
                        {'action': ACTION_COMMAND, 'player_action': rally()})
        elif kind == gifts.KIND and not sent and faction == rc.ROMANS:
            assert request['recipients'] == {rc.AEDUI: 4}
            response = {'transfers': [give(rc.AEDUI, 3)], 'defer': True}
            sent = True
        elif kind == gifts.KIND and not reloaded and faction == rc.AEDUI:
            assert request['recipients'][rc.ROMANS] == 1
            assert llm_seat.cmd_play(args) == 0
            assert load_game(path)[1]['assistant_session']['pending'] == pending
            response = {'transfers': [give(rc.ROMANS, 1)]}
            reloaded = True
        else:
            response = TIMING_DEFAULTS[kind]
        assert llm_seat.cmd_submit(SimpleNamespace(
            dir=args.dir, decision_id=pending['id'], response=json.dumps(response))) == 0
    else:
        pytest.fail('The paired assistant did not finish the card')

    assert turns == [rc.ROMANS, rc.AEDUI] and sent and reloaded
    assert current['resources'][rc.ROMANS] == 10  # Pass gains two before both gifts.
    assert current['resources'][rc.AEDUI] == 11
    assert llm_seat.cmd_replay(args) == 0
    replayed, replay_meta, replay_log = load_game(tmp_path / 'replay' / 'save.json', validate=True)
    assert encode(replayed) == encode(current) and replay_log == log
    assert replay_meta['player_id'] == meta['player_id']
