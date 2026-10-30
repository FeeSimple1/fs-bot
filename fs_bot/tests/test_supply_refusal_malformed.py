"""Malformed Supply replans must retain the human decision, never default it.

§8.6.6 / PR-07 gives Rome reconsideration after the actual refusal. The
durable interface must await a valid choice while preserving that refusal.
"""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.engine.supply_reconsideration import validate_response
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.tools.seat_session import DecisionPending, board_copy
from fs_bot.tests.test_np_aedui_supply_action import _state, _recruit
from fs_bot.tests.test_supply_refusal_choices import _session, _run, _run_declining_timing


@pytest.mark.parametrize('details', [[1], [], 'bad', '', 1, 0, True, False, None])
def test_malformed_details_preserve_actual_supply_pending(details):
    state = _state(5)
    state['_card_turn'] = {'idx': 0}
    initial = encode(state)
    session = _session(state)
    with pytest.raises(DecisionPending):
        _run_declining_timing(session)
    pending = deepcopy(session.data['pending'])
    assert decode(pending['request'])['kind'] == 'supply_refusal'
    bad = {'replacement': {'command': rc.CMD_RECRUIT, 'sa': 'No SA', 'details': details}}
    session.import_inbox({'decision_id': pending['id'], 'response': bad})
    queue = deepcopy(session.data['queue'])
    journal = deepcopy(session.data['journal'])
    with pytest.raises(DecisionPending):
        _run(session)
    assert session.data['pending'] == pending
    assert 'details must be an object' in session.error
    assert session.data['queue'] == queue
    assert session.data['journal'] == journal
    assert encode(board_copy(state)) == initial


def test_malformed_supply_replan_save_correct_resume_and_replay(tmp_path):
    state = _state(5)
    state['_card_turn'] = {'idx': 0}
    initial = encode(state)
    session = _session(state)
    with pytest.raises(DecisionPending):
        _run_declining_timing(session)
    pending = deepcopy(session.data['pending'])
    session.import_inbox({'decision_id': pending['id'], 'response': {
        'replacement': {'command': rc.CMD_RECRUIT, 'sa': 'No SA', 'details': [1]}}})
    with pytest.raises(DecisionPending):
        _run(session)
    assert session.data['pending'] == pending
    path = tmp_path / 'malformed-supply.json'
    save_game(state, path, meta=session.meta, log=session.log)
    saved, meta, log = load_game(path)
    resumed = _session(saved, meta, log)
    assert resumed.data['pending'] == pending
    resumed.import_inbox({'decision_id': pending['id'], 'response': {
        'replacement': _recruit((rc.MANDUBII,))}})
    result = _run_declining_timing(resumed)
    choices = [e for e in resumed.log if e.get('reactive') == 'supply_refusal']
    assert result['executed'] and len(choices) == 1
    assert choices[0]['assistant_id'] == pending['id']
    replay = _session(decode(initial))
    replay.data['expected'] = [{'id': e['assistant_id'], 'signature': e['assistant_signature'],
                               'request': e['assistant_request'],
                               'action_windows_version': e.get('assistant_action_windows_version', 0)}
                              for e in resumed.log]
    replay.import_inbox([replay._inbox_entry(e) for e in resumed.log])
    assert _run(replay) == result
    assert replay.log == resumed.log
    assert encode(board_copy(replay.state)) == encode(board_copy(resumed.state))


@pytest.mark.parametrize('details', [[1], [], 'bad', '', 1, 0, True, False, None])
def test_build_only_reconsideration_rejects_malformed_details(details):
    # This route intentionally does not revalidate its already completed
    # accompanying Command; it still must validate the submitted object.
    state = _state(5)
    action = _recruit()
    action['sa'] = rc.SA_BUILD
    request = {'action_type': 'special_ability', 'action': action,
               'allowed_commands': list(rc.ROMAN_COMMANDS),
               'allowed_special_abilities': [rc.SA_BUILD, 'No SA']}
    candidate = deepcopy(action)
    candidate['details'] = details
    with pytest.raises(ValueError, match='details must be an object'):
        validate_response(state, request, {'replacement': candidate})
