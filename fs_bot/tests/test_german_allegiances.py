"""Card 65 shaded: exact German targets, own replacements, §§5.1–5.1.3."""
from copy import deepcopy
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
import json

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, get_available, place_piece,
)
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine.execute import _execute_event
from fs_bot.engine.game_engine import ACTION_EVENT
from fs_bot.engine.moves import validate_player_action
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools import llm_seat
from fs_bot.tools.seat_session import SeatSession, board_copy


def board(faction=rc.BELGAE, seed=23):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=seed)
    state['non_player_factions'] = set(rc.FACTIONS) - {faction}
    state['current_card'] = state['current_card_id'] = 65
    state['next_card'], state['deck'], state['played_cards'] = None, [], [65]
    for owner in state['eligibility']:
        state['eligibility'][owner] = rc.ELIGIBLE if owner == faction else rc.INELIGIBLE
    return state


def occupy(state, faction, region=rc.NERVII, count=10):
    piece_type = rc.AUXILIA if faction == rc.ROMANS else rc.WARBAND
    place_piece(state, region, faction, piece_type, count)
    refresh_all_control(state)


def ally(state, tribe, owner=rc.GERMANS):
    place_piece(state, rc.TRIBE_TO_REGION[tribe], owner, rc.ALLY)
    state['tribes'][tribe]['allied_faction'] = owner
    refresh_all_control(state)


def warband(region=rc.NERVII, visibility=rc.HIDDEN, replace=True):
    return {'region': region, 'piece_type': rc.WARBAND,
            'piece_state': visibility, 'replace': replace}


def allied(tribe=rc.TRIBE_NERVII, replace=True):
    return {'region': rc.TRIBE_TO_REGION[tribe], 'piece_type': rc.ALLY,
            'tribe': tribe, 'replace': replace}


def plan(*entries):
    return {'replacements': list(entries)}


def action(params):
    return {'command': 'Event', 'regions': [], 'sa': 'No SA', 'details': {
        'card_id': 65, 'text_preference': rc.EVENT_SHADED, 'event_params': params}}


def event(state, faction, params):
    return _execute_event(state, faction, action(params), human=True)


def populated(faction=rc.BELGAE):
    state = board(faction)
    occupy(state, faction)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 5)
    ally(state, rc.TRIBE_NERVII)
    assert validate_state(state) == []
    return state, plan(*[warband() for _ in range(5)], allied())


@pytest.mark.parametrize('faction', [rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE])
def test_replacement_is_the_executors_own_troop_and_ally(faction):
    state, params = populated(faction)
    native = rc.AUXILIA if faction == rc.ROMANS else rc.WARBAND
    native_before = count_pieces(state, rc.NERVII, faction, native)
    available = get_available(state, faction, native)
    assert event(state, faction, params)['executed']
    assert count_pieces(state, rc.NERVII, rc.GERMANS, rc.WARBAND) == 0
    assert count_pieces(state, rc.NERVII, faction, native) == native_before + 5
    assert get_available(state, faction, native) == available - 5
    assert state['tribes'][rc.TRIBE_NERVII]['allied_faction'] == faction
    if faction != rc.ROMANS:
        assert count_pieces(state, rc.NERVII, faction, rc.AUXILIA) == 0
    assert validate_state(state) == []


def test_exact_visibility_and_ally_identity_and_mixed_remove_replace():
    state = board()
    occupy(state, rc.BELGAE)
    for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 2, piece_state=visibility)
    ally(state, rc.TRIBE_NERVII)
    ally(state, rc.TRIBE_EBURONES)
    params = plan(warband(visibility=rc.SCOUTED), warband(visibility=rc.SCOUTED, replace=False),
                  warband(visibility=rc.REVEALED), warband(visibility=rc.REVEALED, replace=False),
                  warband(replace=False), allied(rc.TRIBE_EBURONES, replace=False))
    assert event(state, rc.BELGAE, params)['executed']
    assert count_pieces_by_state(state, rc.NERVII, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 1
    assert count_pieces_by_state(state, rc.NERVII, rc.GERMANS, rc.WARBAND, rc.REVEALED) == 0
    assert count_pieces_by_state(state, rc.NERVII, rc.GERMANS, rc.WARBAND, rc.SCOUTED) == 0
    assert count_pieces_by_state(state, rc.NERVII, rc.BELGAE, rc.WARBAND, rc.HIDDEN) == 12
    assert state['tribes'][rc.TRIBE_NERVII]['allied_faction'] == rc.GERMANS
    assert state['tribes'][rc.TRIBE_EBURONES]['allied_faction'] is None
    assert validate_state(state) == []


def test_remove_only_is_legal_even_when_all_replacements_are_available():
    state, params = populated()
    for choice in params['replacements']:
        choice['replace'] = False
    before = deepcopy(state['available'][rc.BELGAE])
    assert event(state, rc.BELGAE, params)['executed']
    assert state['available'][rc.BELGAE] == before
    assert count_pieces(state, rc.NERVII, rc.GERMANS) == 0
    assert state['tribes'][rc.TRIBE_NERVII]['allied_faction'] is None
    assert validate_state(state) == []


def test_partial_execution_removes_every_eligible_target_when_fewer_exist():
    state = board()
    occupy(state, rc.BELGAE)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 2, piece_state=rc.SCOUTED)
    assert event(state, rc.BELGAE, plan(warband(visibility=rc.SCOUTED),
                                       warband(visibility=rc.SCOUTED)))['executed']
    assert count_pieces(state, rc.NERVII, rc.GERMANS, rc.WARBAND) == 0
    assert count_pieces(state, rc.NERVII, rc.BELGAE, rc.WARBAND) == 12
    assert validate_state(state) == []


def test_unavailable_replacements_remove_targets_instead_of_rejecting_event():
    state, params = populated()
    place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND,
                get_available(state, rc.BELGAE, rc.WARBAND))
    for tribe in (rc.TRIBE_MORINI, rc.TRIBE_MENAPII, rc.TRIBE_EBURONES,
                  rc.TRIBE_ATREBATES, rc.TRIBE_BELLOVACI, rc.TRIBE_REMI,
                  rc.TRIBE_TREVERI, rc.TRIBE_CARNUTES, rc.TRIBE_AULERCI,
                  rc.TRIBE_MANDUBII):
        if not get_available(state, rc.BELGAE, rc.ALLY):
            break
        ally(state, tribe, rc.BELGAE)
    assert get_available(state, rc.BELGAE, rc.ALLY) == 0
    assert event(state, rc.BELGAE, params)['executed']
    assert count_pieces(state, rc.NERVII, rc.GERMANS) == 0
    assert state['tribes'][rc.TRIBE_NERVII]['allied_faction'] is None
    assert count_pieces(state, rc.NERVII, rc.BELGAE, rc.WARBAND) == 10
    assert validate_state(state) == []


def test_restricted_suebi_ally_is_removed_when_replacement_would_violate_stacking():
    state = board()
    occupy(state, rc.BELGAE, rc.SUGAMBRI, count=2)
    ally(state, rc.TRIBE_SUEBI_NORTH)
    before = get_available(state, rc.BELGAE, rc.ALLY)
    assert event(state, rc.BELGAE, plan(allied(rc.TRIBE_SUEBI_NORTH)))['executed']
    assert state['tribes'][rc.TRIBE_SUEBI_NORTH]['allied_faction'] is None
    assert get_available(state, rc.BELGAE, rc.ALLY) == before
    assert validate_state(state) == []


_BAD_EDITS = [
    ('omit-available', lambda entries: entries.pop()),
    ('six-warbands', lambda entries: entries.insert(0, warband())),
    ('duplicate-ally', lambda entries: entries.append(allied())),
    ('wrong-region', lambda entries: entries[0].update(region=rc.MORINI)),
    ('wrong-state', lambda entries: entries[0].update(piece_state=rc.REVEALED)),
    ('missing-state', lambda entries: entries[0].pop('piece_state')),
    ('wrong-piece', lambda entries: entries[0].update(piece_type=rc.AUXILIA)),
    ('forged-recipient', lambda entries: entries[0].update(faction=rc.ROMANS)),
    ('boolean-count', lambda entries: entries[0].update(count=True)),
    ('string-replace', lambda entries: entries[0].update(replace='false')),
    ('missing-replace', lambda entries: entries[0].pop('replace')),
    ('wrong-tribe-region', lambda entries: entries[-1].update(region=rc.MORINI)),
    ('unknown-tribe', lambda entries: entries[-1].update(tribe='not-a-tribe')),
]


@pytest.mark.parametrize('name,edit', _BAD_EDITS, ids=[name for name, _ in _BAD_EDITS])
def test_complete_illegal_plan_is_rejected_before_any_mutation(name, edit):
    from fs_bot.cards.german_allegiances import validate_params
    state, params = populated()
    edit(params['replacements'])
    before = encode(board_copy(state))
    with pytest.raises(ValueError):
        validate_params(state, rc.BELGAE, params)
    assert encode(board_copy(state)) == before
    assert not validate_player_action(state, rc.BELGAE, action(params))[0]
    assert encode(board_copy(state)) == before
    result = event(state, rc.BELGAE, params)
    assert not result['executed'] and result['rejected'] is True
    # The raw Event adapter restores these optional context keys to None.
    state.pop('executing_faction', None)
    state.pop('event_params', None)
    assert encode(board_copy(state)) == before


def test_no_control_cannot_target_otherwise_present_german_pieces():
    state = board()
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND)
    before = encode(state)
    assert not validate_player_action(state, rc.BELGAE, action(plan(warband())))[0]
    assert encode(state) == before


@pytest.mark.parametrize('params', [None, [], 'replace', {'replacements': None},
                                     {'replacements': [None]}, {'replacements': [], 'faction': rc.ROMANS}])
def test_malformed_params_fail_without_mutation(params):
    from fs_bot.cards.german_allegiances import validate_params
    state, _ = populated()
    before = encode(state)
    with pytest.raises(ValueError):
        validate_params(state, rc.BELGAE, params)
    assert encode(state) == before


def test_validation_preview_cannot_consume_human_responses_or_rng():
    state, params = populated()
    session = SeatSession(state, {'seat': rc.BELGAE}, [], HumanTurnDisplay(StringIO()))
    state['decision_agent'] = session.reactive
    session.import_inbox([{'response': {'done': True}}])
    before, data = encode(board_copy(state)), deepcopy(session.data)
    assert validate_player_action(state, rc.BELGAE, action(params))[0]
    assert encode(board_copy(state)) == before and session.data == data


def test_nonplayer_default_uses_exact_scouted_targets_and_native_replacement():
    from fs_bot.cards.german_allegiances import derive_params, validate_params
    state = board(rc.AEDUI)
    occupy(state, rc.AEDUI, count=4)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 2, piece_state=rc.SCOUTED)
    ally(state, rc.TRIBE_NERVII)
    params = derive_params(state, rc.AEDUI, True)
    validate_params(state, rc.AEDUI, params)
    assert event(state, rc.AEDUI, params)['executed']
    assert count_pieces(state, rc.NERVII, rc.AEDUI, rc.WARBAND) == 6
    assert state['tribes'][rc.TRIBE_NERVII]['allied_faction'] == rc.AEDUI
    assert count_pieces(state, rc.NERVII, rc.GERMANS) == 0
    assert validate_state(state) == []


def test_nonplayer_declines_without_targets_and_belgae_require_an_added_ally():
    from fs_bot.cards.event_conditions import np_event_available
    from fs_bot.bots.bot_common import should_decline_event
    state = board()
    state['non_player_factions'] = set(rc.FACTIONS)
    occupy(state, rc.BELGAE, rc.SUGAMBRI, 4)
    assert not np_event_available(state, 65, rc.BELGAE, True)
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND)
    assert not np_event_available(state, 65, rc.BELGAE, True)
    ally(state, rc.TRIBE_SUEBI_NORTH)
    assert not np_event_available(state, 65, rc.BELGAE, True)
    assert should_decline_event(state, 65, rc.BELGAE)
    occupy(state, rc.BELGAE, rc.NERVII, 2)
    ally(state, rc.TRIBE_NERVII)
    before = encode(state)
    assert np_event_available(state, 65, rc.BELGAE, True)
    assert not should_decline_event(state, 65, rc.BELGAE)
    assert encode(state) == before


def test_nonplayer_prefers_replaceable_remi_ally_and_exhausts_most_pieces_region():
    from fs_bot.cards.german_allegiances import derive_params, validate_params
    state = board(rc.AEDUI)
    for region, number in [(rc.NERVII, 10), (rc.MORINI, 4),
                           (rc.TRIBE_TO_REGION[rc.TRIBE_REMI], 2), (rc.SUGAMBRI, 2)]:
        occupy(state, rc.AEDUI, region, number)
    for visibility, number in [(rc.HIDDEN, 1), (rc.REVEALED, 3), (rc.SCOUTED, 4)]:
        place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, number,
                    piece_state=visibility)
    place_piece(state, rc.MORINI, rc.GERMANS, rc.WARBAND, 3)
    ally(state, rc.TRIBE_NERVII)
    ally(state, rc.TRIBE_REMI)
    ally(state, rc.TRIBE_SUEBI_NORTH)
    state_before = board_copy(state)
    params = derive_params(state, rc.AEDUI, True)
    assert params['replacements'][0] == allied(rc.TRIBE_REMI)
    troops = params['replacements'][1:]
    assert [entry['region'] for entry in troops] == [rc.NERVII] * 5
    assert [entry['piece_state'] for entry in troops] == [rc.HIDDEN, *[rc.REVEALED] * 3, rc.SCOUTED]
    validate_params(state, rc.AEDUI, params)
    state_before.pop('rng'); after = board_copy(state); after.pop('rng')
    assert encode(after) == encode(state_before)


def test_reclamation_before_replacement_uses_newly_available_piece_without_substituting_target():
    from fs_bot.engine.action_windows import scope
    state = board()
    occupy(state, rc.BELGAE)
    place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND,
                get_available(state, rc.BELGAE, rc.WARBAND))
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, piece_state=rc.SCOUTED)
    entry = warband(visibility=rc.SCOUTED)
    entry['timing_actions'] = [{'kind': 'voluntary_removal', 'response': {'operations': [{
        'action': 'remove', 'region': rc.MORINI, 'piece_type': rc.WARBAND,
        'piece_state': rc.HIDDEN, 'count': 1}]}}]
    params = plan(entry)
    with scope(state, actor=rc.BELGAE, plan=action(params), force=True):
        assert event(state, rc.BELGAE, params)['executed']
    assert count_pieces(state, rc.NERVII, rc.BELGAE, rc.WARBAND) == 11
    assert count_pieces(state, rc.NERVII, rc.GERMANS) == 0
    assert get_available(state, rc.BELGAE, rc.WARBAND) == 0
    assert validate_state(state) == []


def test_losing_control_in_timing_window_cannot_retarget_or_commit_partial_event():
    from fs_bot.engine.action_windows import scope
    state = board()
    occupy(state, rc.BELGAE, count=2)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND)
    entry = warband()
    entry['timing_actions'] = [{'kind': 'voluntary_removal', 'response': {'operations': [{
        'action': 'remove', 'region': rc.NERVII, 'piece_type': rc.WARBAND,
        'piece_state': rc.HIDDEN, 'count': 1}]}}]
    params = plan(entry)
    before = encode(board_copy(state))
    with scope(state, actor=rc.BELGAE, plan=action(params), force=True):
        assert not event(state, rc.BELGAE, params)['executed']
    state.pop('event_params', None); state.pop('executing_faction', None)
    assert encode(board_copy(state)) == before


def _save_session(path, state):
    path.mkdir()
    display = HumanTurnDisplay(StringIO())
    display.remember(state, [rc.BELGAE])
    meta = {'seat': rc.BELGAE, 'scenario': state['scenario'], 'seed': 23,
            'human_snapshots': encode(display.snapshots)}
    SeatSession(state, meta, [], display)
    save_game(state, path / 'save.json', meta=meta, log=[])
    return SimpleNamespace(dir=str(path))


def _finish_timing(args):
    for _ in range(30):
        _, meta, _ = load_game(Path(args.dir) / 'save.json')
        pending = meta['assistant_session']['pending']
        if not pending:
            return
        request = decode(pending['request'])
        if request['kind'] != 'voluntary_removal':
            return
        args.response = json.dumps({'done': True})
        assert llm_seat.cmd_submit(args) == 0
    pytest.fail('Event did not finish after its optional timing windows')


def test_durable_illegal_target_stays_pending_then_corrected_plan_saves_and_replays(tmp_path, capsys):
    state, params = populated()
    args = _save_session(tmp_path / 'live', state)
    assert llm_seat.cmd_play(args) == 0
    original, meta, log = load_game(tmp_path / 'live/save.json')
    pending = deepcopy(meta['assistant_session']['pending'])
    bad = deepcopy(params)
    bad['replacements'][0]['region'] = rc.MORINI
    args.response = json.dumps({'action': ACTION_EVENT, 'player_action': action(bad)})
    assert llm_seat.cmd_submit(args) == 0
    _finish_timing(args)
    rejected, rejected_meta, rejected_log = load_game(tmp_path / 'live/save.json')
    assert encode(rejected) == encode(original)
    assert rejected_meta['assistant_session']['pending'] == pending
    assert rejected_meta['assistant_session']['journal'] == [] and rejected_log == log
    # A deliberately mixed removal/replacement plan must survive journaling.
    params['replacements'][0]['replace'] = False
    args.response = json.dumps({'action': ACTION_EVENT, 'player_action': action(params)})
    assert llm_seat.cmd_submit(args) == 0
    _finish_timing(args)
    final, final_meta, final_log = load_game(tmp_path / 'live/save.json')
    assert count_pieces(final, rc.NERVII, rc.BELGAE, rc.WARBAND) == 14
    assert count_pieces(final, rc.NERVII, rc.GERMANS) == 0
    assert final_log[0]['player_action'] == action(params)
    assert not final_meta['assistant_session']['pending']
    args.output_dir = str(tmp_path / 'replay')
    assert llm_seat.cmd_replay(args) == 0
    replay, _, _ = load_game(tmp_path / 'replay/save.json')
    assert encode(replay) == encode(final)
    assert 'Replay verified' in capsys.readouterr().out


def test_ordered_replacements_spend_the_last_available_piece_in_chosen_region():
    state = board()
    occupy(state, rc.BELGAE, rc.NERVII, 12)
    occupy(state, rc.BELGAE, rc.MORINI, 12)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 3)
    place_piece(state, rc.MORINI, rc.GERMANS, rc.WARBAND, 2)
    assert get_available(state, rc.BELGAE, rc.WARBAND) == 1
    params = plan(warband(rc.MORINI), warband(rc.NERVII), warband(rc.NERVII),
                  warband(rc.MORINI), warband(rc.NERVII))
    assert event(state, rc.BELGAE, params)['executed']
    assert count_pieces(state, rc.MORINI, rc.BELGAE, rc.WARBAND) == 13
    assert count_pieces(state, rc.NERVII, rc.BELGAE, rc.WARBAND) == 12
    assert count_pieces(state, rc.MORINI, rc.GERMANS, rc.WARBAND) == 0
    assert count_pieces(state, rc.NERVII, rc.GERMANS, rc.WARBAND) == 0
    assert validate_state(state) == []


def test_empty_plan_is_legal_only_when_no_eligible_target_exists():
    state = board()
    place_piece(state, rc.MORINI, rc.GERMANS, rc.WARBAND, 6)
    ally(state, rc.TRIBE_MORINI)
    # No executor Control: those German pieces are not eligible.
    before = encode(board_copy(state))
    result = event(state, rc.BELGAE, plan())
    assert result['executed'] and not result.get('rejected')
    state.pop('executing_faction', None); state.pop('event_params', None)
    assert encode(board_copy(state)) == before


def test_cli_board_aliases_exact_choice_and_eof_preserve_live_board_and_rng():
    from fs_bot.cards.german_allegiances import validate_params
    from fs_bot.cli.human_plan import _collect_event_params
    state = board()
    occupy(state, rc.BELGAE, count=4)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, piece_state=rc.SCOUTED)
    ally(state, rc.TRIBE_NERVII)
    before = encode(board_copy(state))
    output = StringIO()
    params = _collect_event_params(state, rc.BELGAE, 65, True,
                                  StringIO('board\nb\n1\n2\n1\n1\n'), output)
    validate_params(state, rc.BELGAE, params)
    assert params == plan(warband(visibility=rc.SCOUTED), allied(replace=False))
    assert 'Scouted' in output.getvalue() and rc.NERVII in output.getvalue()
    assert encode(board_copy(state)) == before
    with pytest.raises(EOFError):
        _collect_event_params(state, rc.BELGAE, 65, True, StringIO('1\n'), StringIO())
    assert encode(board_copy(state)) == before
