"""Third-audit Batch 1 regressions against §§2.3.6, 4.3.1 and 5.1.1."""
from copy import deepcopy
import io
import json
from types import SimpleNamespace

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (
    clear_allied_tribe, count_pieces, get_available, move_piece, place_piece, remove_piece,
)
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.commands.common import CommandError
from fs_bot.commands.sa_entreat import entreat_replace_ally
from fs_bot.engine import game_engine as ge
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.moves import validate_player_action
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import check_structural_integrity, validate_state
from fs_bot.tools import llm_seat
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy, validate_response


def recruit():
    return {'action': ge.ACTION_COMMAND, 'player_action': {
        'command': rc.CMD_RECRUIT, 'sa': 'No SA', 'regions': [rc.PROVINCIA],
        'details': {'recruit_plan': [
            {'region': rc.PROVINCIA, 'action': 'place_auxilia', 'count': 1}]}}}


def clean(state):
    assert validate_state(state) == []
    assert check_structural_integrity(state) == []


def submit(args, pending, response):
    assert llm_seat.cmd_submit(SimpleNamespace(
        dir=args.dir, decision_id=pending['id'], response=json.dumps(response))) == 0


def next_turn(args, path):
    for _ in range(40):
        state, meta, log = load_game(path, validate=True)
        pending = meta['assistant_session']['pending']
        assert pending
        if decode(pending['request'])['kind'] == 'turn':
            return state, meta['assistant_session'], log
        submit(args, pending, {'use_default': True})
    pytest.fail('Expected the next human turn.')


@pytest.mark.parametrize('extra', [
    {'free_action': True}, {'assistant_response': {'action': ge.ACTION_PASS}},
])
def test_assistant_rejects_turn_metadata_then_keeps_recruit_through_resume_and_replay(
        tmp_path, capsys, monkeypatch, extra):
    args = SimpleNamespace(dir=str(tmp_path / 'game'), scenario=rc.SCENARIO_GREAT_REVOLT,
                           seed=46, seat=rc.ROMANS, output_dir=str(tmp_path / 'replay'))
    path = tmp_path / 'game' / 'save.json'
    llm_seat.cmd_init(args)
    assert llm_seat.cmd_play(args) == 0
    state, session, log = next_turn(args, path)
    pending = deepcopy(session['pending'])
    assert state['current_card'] == 16

    capsys.readouterr()
    submit(args, pending, dict(recruit(), **extra))
    assert 'engine history' in capsys.readouterr().out
    rejected, meta, rejected_log = load_game(path, validate=True)
    assert encode(rejected) == encode(state)
    assert meta['assistant_session']['pending'] == pending
    assert meta['assistant_session']['journal'] == session['journal']
    assert rejected_log == log

    observed = []
    original = ge.adjust_eligibility

    def observe(board, actions):
        original(board, actions)
        if board['current_card'] == 16:
            observed.append((board['eligibility'][rc.ROMANS], deepcopy(actions[rc.ROMANS])))

    monkeypatch.setattr(ge, 'adjust_eligibility', observe)
    before = count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA)
    submit(args, pending, recruit())
    paused, paused_meta, _ = load_game(path, validate=True)
    accepted = paused_meta['assistant_session']['journal'][0]
    assert decode(accepted['assistant_response']) == recruit()
    assert accepted['action'] == ge.ACTION_COMMAND
    assert decode(paused_meta['assistant_session']['pending']['request'])['kind'] != 'turn'
    # Each subsequent submit reloads the saved transaction and its journal.
    final, _, final_log = next_turn(args, path)
    assert observed[0][0] == rc.INELIGIBLE
    assert observed[0][1]['action'] == ge.ACTION_COMMAND
    assert count_pieces(final, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == before + 1
    recorded = next(row for row in final_log if row.get('assistant_id') == pending['id'])
    assert recorded['player_action'] == recruit()['player_action']
    assert decode(recorded['assistant_response']) == recruit()
    assert llm_seat.cmd_replay(args) == 0
    replayed, _, replayed_log = load_game(tmp_path / 'replay' / 'save.json', validate=True)
    assert encode(replayed) == encode(final)
    assert replayed_log == final_log


@pytest.mark.parametrize('field', [
    'free_action', 'assistant_id', 'assistant_signature', 'assistant_request',
    'assistant_response', 'assistant_action_windows_version', 'position', 'faction',
    'card', 'execution', 'declared_action', 'reactive', 'response',
])
@pytest.mark.parametrize('action', [ge.ACTION_PASS, ge.ACTION_COMMAND, ge.ACTION_EVENT])
def test_turn_envelope_rejects_internal_fields(field, action):
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=1)
    submitted = recruit() if action == ge.ACTION_COMMAND else {'action': action}
    if action == ge.ACTION_EVENT:
        submitted['player_action'] = {'command': rc.FIRST_DID_EVENT}
    submitted[field] = True
    before = encode(state)
    with pytest.raises(ValueError, match='engine history'):
        validate_response(state, {'kind': 'turn', 'options': [action], 'faction': rc.ROMANS}, submitted)
    assert encode(state) == before


def test_raw_human_turn_rejects_eligibility_metadata_before_execution():
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=1)
    state['current_card'] = 16
    state['eligibility'] = {f: rc.ELIGIBLE if f == rc.ROMANS else rc.INELIGIBLE
                            for f in state['eligibility']}
    captured = []

    def choose(board, faction, options, position):
        captured.append(encode(board))
        return dict(recruit(), free_action=True)

    with pytest.raises(ge.ActionRejected, match='engine history'):
        ge.resolve_card_turn(state, choose, execute=True)
    assert encode(state) == captured[0]
    assert state['_card_turn']['actions_taken'] == {}


@pytest.mark.parametrize('conflict', [False, True])
def test_saved_turn_journal_resumes_accepted_choice_or_stops_on_conflict(tmp_path, conflict):
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=1)
    meta = {'seat': rc.ROMANS, 'scenario': state['scenario'], 'seed': 1}
    session = SeatSession(state, meta, [], HumanTurnDisplay(io.StringIO()))
    request = {'kind': 'turn', 'options': [ge.ACTION_COMMAND], 'position': '1st_eligible'}
    session.import_inbox([{'response': recruit()}])
    session.checkpoint()
    assert session.ask(state, rc.ROMANS, request) == recruit()
    if conflict:
        session.data['journal'][0]['assistant_response'] = {'action': ge.ACTION_PASS}
    save_game(state, tmp_path / 'save.json', meta=meta, log=[])
    restored, saved_meta, log = load_game(tmp_path / 'save.json', validate=True)
    resumed = SeatSession(restored, saved_meta, log, HumanTurnDisplay(io.StringIO()))
    before = encode(board_copy(restored))
    if conflict:
        with pytest.raises(DecisionPending):
            resumed.ask(restored, rc.ROMANS, request)
        assert 'conflicts' in resumed.error
        with pytest.raises(ValueError, match='conflicts'):
            SeatSession._inbox_entry(resumed.data['journal'][0])
    else:
        assert resumed.ask(restored, rc.ROMANS, request) == recruit()
    assert encode(board_copy(restored)) == before


def test_tuple_form_march_journal_resumes_after_json_roundtrip(tmp_path):
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=1)
    meta = {'seat': rc.ROMANS, 'scenario': state['scenario'], 'seed': 1}
    response = {'action': ge.ACTION_COMMAND, 'player_action': {
        'command': rc.CMD_MARCH, 'details': {
            'origins': [(rc.PROVINCIA, 1)], 'destinations': [rc.SEQUANI],
            'routes': {rc.PROVINCIA: [rc.SEQUANI]},
            'groups': {rc.PROVINCIA: {rc.AUXILIA: 1}}}}}
    request = {'kind': 'turn', 'options': [ge.ACTION_COMMAND], 'position': '1st_eligible'}
    session = SeatSession(state, meta, [], HumanTurnDisplay(io.StringIO()))
    session.import_inbox([{'response': response}])
    session.checkpoint()
    assert session.ask(state, rc.ROMANS, request) == response
    save_game(state, tmp_path / 'save.json', meta=meta, log=[])
    restored, saved_meta, log = load_game(tmp_path / 'save.json', validate=True)
    resumed = SeatSession(restored, saved_meta, log, HumanTurnDisplay(io.StringIO()))
    assert resumed.ask(restored, rc.ROMANS, request) == response
    assert SeatSession._inbox_entry(resumed.data['journal'][0])['response'] == response
    before = count_pieces(restored, rc.SEQUANI, rc.ROMANS, rc.AUXILIA)
    assert execute_decision(restored, rc.ROMANS, response)['executed']
    assert count_pieces(restored, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == before + 1
    clean(restored)


def entreat_position():
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=1)
    state['non_player_factions'] = set()
    for tribe in (rc.TRIBE_SEQUANI, rc.TRIBE_HELVETII):
        remove_piece(state, rc.SEQUANI, rc.ARVERNI, rc.ALLY)
        clear_allied_tribe(state, rc.SEQUANI, rc.ARVERNI, rc.ALLY, tribe=tribe)
    place_piece(state, rc.SEQUANI, rc.BELGAE, rc.CITADEL)
    state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] = rc.BELGAE
    place_piece(state, rc.SEQUANI, rc.BELGAE, rc.ALLY)
    state['tribes'][rc.TRIBE_HELVETII]['allied_faction'] = rc.BELGAE
    move_piece(state, rc.CARNUTES, rc.SEQUANI, rc.ARVERNI, rc.LEADER)
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 5, piece_state=rc.HIDDEN)
    clean(state)
    return state


def entreat(tribe, timing='before', operation='replace_ally'):
    return {'action': ge.ACTION_COMMAND_SA, 'player_action': {
        'command': rc.CMD_RAID, 'sa': rc.SA_ENTREAT, 'sa_timing': timing,
        'sa_regions': [{'region': rc.SEQUANI, 'action': operation,
                        'target_faction': rc.BELGAE, 'tribe': tribe}],
        'details': {'raid_plan': [{'region': rc.SEQUANI, 'target': None}]}}}


@pytest.mark.parametrize('timing', ['before', 'after'])
@pytest.mark.parametrize('operation', ['replace_ally', 'remove_ally'])
def test_entreat_rejects_citadel_identity_without_spending_or_removing(timing, operation):
    state = entreat_position()
    submitted = entreat(rc.TRIBE_SEQUANI, timing, operation)
    before = encode(state)
    with pytest.raises(ValueError, match='Allied Tribe disc'):
        validate_response(state, {'kind': 'turn', 'faction': rc.ARVERNI,
                                 'options': [ge.ACTION_COMMAND_SA]}, submitted)
    result = execute_decision(state, rc.ARVERNI, submitted)
    assert result['rejected'] and not result['executed']
    assert encode(state) == before
    with pytest.raises(CommandError, match='Allied Tribe disc'):
        entreat_replace_ally(state, rc.SEQUANI, rc.BELGAE, rc.TRIBE_SEQUANI)
    assert encode(state) == before
    clean(state)


@pytest.mark.parametrize('supply', [False, True])
def test_entreat_takes_the_named_disc_beside_citadel_with_available_or_empty_pool(supply):
    state = entreat_position()
    if not supply:
        for tribe, info in state['tribes'].items():
            if not get_available(state, rc.ARVERNI, rc.ALLY):
                break
            if (not info.get('allied_faction') and not info.get('status')
                    and rc.TRIBE_FACTION_RESTRICTION.get(tribe) in (None, rc.ARVERNI)):
                place_piece(state, rc.TRIBE_TO_REGION[tribe], rc.ARVERNI, rc.ALLY)
                info['allied_faction'] = rc.ARVERNI
        assert get_available(state, rc.ARVERNI, rc.ALLY) == 0
    clean(state)
    result = execute_decision(state, rc.ARVERNI, entreat(rc.TRIBE_HELVETII))
    assert result['executed'] and result['sa_execution']['executed']
    assert result['sa_execution']['errors'] == []
    assert state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] == rc.BELGAE
    assert state['tribes'][rc.TRIBE_HELVETII]['allied_faction'] == (rc.ARVERNI if supply else None)
    assert count_pieces(state, rc.SEQUANI, rc.BELGAE, rc.CITADEL) == 1
    clean(state)


def test_both_terminal_entreat_menus_offer_the_disc_and_preserve_citadel():
    from fs_bot.cli.human_plan import _enemy_ally_tribes
    from fs_bot.cli.sa_timing import _entreat_options
    state = entreat_position()
    assert _enemy_ally_tribes(state, rc.SEQUANI, rc.ARVERNI) == [(rc.TRIBE_HELVETII, rc.BELGAE)]
    named = [entry['tribe'] for _, entry in _entreat_options(state, rc.SEQUANI)
             if entry['action'] == 'replace_ally']
    assert named == [rc.TRIBE_HELVETII]


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
@pytest.mark.parametrize('field,value', [
    ('warband_full_loss', True), ('allied_factions', [rc.AEDUI, rc.AEDUI]),
    ('no_retreat', True), ('force_retreat', True), ('no_retreat', False),
])
def test_ordinary_battle_cannot_author_event_modifiers(scenario, field, value):
    state = setup_scenario(scenario, seed=1)
    submitted = {'action': ge.ACTION_COMMAND, 'player_action': {
        'command': rc.CMD_BATTLE, 'sa': 'No SA',
        'details': {'battle_plan': [{'region': rc.TREVERI, 'target': rc.GERMANS}], field: value}}}
    before = encode(state)
    with pytest.raises(ValueError, match='Event supplies Battle modifiers'):
        validate_response(state, {'kind': 'turn', 'faction': rc.AEDUI,
                                 'options': [ge.ACTION_COMMAND]}, submitted)
    ok, info = validate_player_action(state, rc.AEDUI, submitted['player_action'])
    assert not ok and info['rejected']
    result = execute_decision(state, rc.AEDUI, submitted)
    assert result['rejected'] and not result['executed']
    assert encode(state) == before
