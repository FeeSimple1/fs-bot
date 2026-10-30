"""§8.6.6 reconsideration precedes Recruit/Build effects, with PR-07 one die."""
from copy import deepcopy
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, move_piece, place_piece
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_COMMAND, ACTION_COMMAND_SA, _action_transaction
from fs_bot.engine.supply_reconsideration import validate_response
from fs_bot.engine.supply_retry import RECEIPT
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy
from fs_bot.tests.test_np_aedui_supply_action import _state, _recruit


def _march():
    return {'command': rc.CMD_MARCH, 'regions': [], 'sa': 'No SA', 'details': {
        'origins': [rc.SEQUANI], 'destinations': [rc.UBII],
        'routes': {rc.SEQUANI: [rc.UBII]}, 'groups': {rc.SEQUANI: {rc.AUXILIA: 1}}}}


@pytest.mark.parametrize('replacement', [_recruit((rc.MANDUBII,)), _march()])
def test_payable_recruit_refusal_offers_new_plan_before_any_effect(replacement):
    state = _state(5)
    before = encode(state)
    observed = []

    def agent(board, faction, request):
        if request['kind'] != 'supply_refusal':
            return None
        assert faction == rc.ROMANS and board is state
        assert request['action_type'] == 'command'
        assert request['allowed_special_abilities'] == ['No SA']
        for key in ('spaces', 'available', 'resources'):
            assert encode(state[key]) == before[key]
        observed.append(request)
        return {'replacement': deepcopy(replacement)}

    state['decision_agent'] = agent
    expected_rng = deepcopy(state['rng'])
    assert expected_rng.randint(1, 6) == 5
    result = execute_decision(state, rc.ROMANS, {
        'action': ACTION_COMMAND, 'player_action': _recruit()})
    assert result['executed'] and not result.get('errors'), result
    assert result['command'] == replacement['command']
    assert len(observed) == 1
    assert state['rng'].getstate() == expected_rng.getstate()
    if replacement['command'] == rc.CMD_RECRUIT:
        assert state['resources'][rc.ROMANS] == 8
        assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 1
    else:
        assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 0
        assert count_pieces(state, rc.UBII, rc.ROMANS, rc.AUXILIA) == 1


def test_refusal_after_march_rechooses_only_build_and_preserves_march():
    state = _state(5)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 6)
    move_piece(state, rc.SEQUANI, rc.MANDUBII, rc.ROMANS, rc.LEADER)
    action = _march()
    action.update(sa=rc.SA_BUILD, sa_timing='after', sa_regions=[rc.CARNUTES])
    action['details']['build_plan'] = {'forts': [rc.CARNUTES], 'allies': [], 'subdue': []}
    observed = []

    def agent(board, faction, request):
        if request['kind'] != 'supply_refusal':
            return None
        assert request['action_type'] == 'special_ability'
        assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 0
        assert count_pieces(state, rc.UBII, rc.ROMANS, rc.AUXILIA) == 1
        assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.FORT) == 0
        revised = deepcopy(request['action'])
        revised.update(sa=rc.SA_SCOUT, sa_regions=[rc.MANDUBII])
        revised['details'].pop('build_plan')
        revised['details']['scout_plan'] = {
            'auxilia_moves': [{'from_region': rc.MANDUBII, 'to_region': rc.ATREBATES,
                              'count': 1, 'piece_state': rc.HIDDEN}], 'scout_targets': []}
        observed.append(request)
        return {'replacement': revised}

    state['decision_agent'] = agent
    before_atrebates = count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA)
    rng = deepcopy(state['rng'])
    rng.randint(1, 6)
    result = execute_decision(state, rc.ROMANS, {
        'action': ACTION_COMMAND_SA, 'player_action': action})
    assert result['executed'] and not result.get('errors'), result
    assert result['sa_execution']['sa'] == rc.SA_SCOUT
    assert result['sa_execution']['executed'] and not result['sa_execution']['errors']
    assert len(observed) == 1 and state['rng'].getstate() == rng.getstate()
    assert count_pieces(state, rc.UBII, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == before_atrebates + 1
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.FORT) == 0


def _session(state, meta=None, log=None):
    session = SeatSession(state, meta or {'seat': rc.ROMANS}, log or [],
                          HumanTurnDisplay(io.StringIO()))
    state['decision_agent'] = session.reactive
    return session


def _run(session):
    def driver(*args):
        pass
    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    driver.transaction_complete = session.transaction_complete
    with _action_transaction(session.state, driver):
        result = execute_decision(session.state, rc.ROMANS, {
            'action': ACTION_COMMAND, 'player_action': _recruit()})
    session.finish()
    return result


def test_refusal_pending_invalid_save_resume_and_origin_replay(tmp_path):
    state = _state(5)
    state['_card_turn'] = {'idx': 0}
    initial = encode(state)
    session = _session(state)
    with pytest.raises(DecisionPending):
        _run(session)
    assert encode(board_copy(state)) == initial
    pending = deepcopy(session.data['pending'])
    assert decode(pending['request'])['kind'] == 'supply_refusal'
    assert decode(pending['board'])['_card_turn'][RECEIPT]['answer'] is False
    session.import_inbox({'decision_id': pending['id'], 'response': {'continue': 1}})
    with pytest.raises(DecisionPending):
        _run(session)
    assert session.data['pending'] == pending and session.error
    assert encode(board_copy(state)) == initial
    save_game(state, tmp_path / 'refusal.json', meta=session.meta, log=session.log)
    saved_state, meta, log = load_game(tmp_path / 'refusal.json')
    resumed = _session(saved_state, meta, log)
    resumed.import_inbox({'decision_id': pending['id'], 'response': {
        'replacement': _recruit((rc.MANDUBII,))}})
    result = _run(resumed)
    assert result['executed'] and len(resumed.log) == 1
    assert resumed.log[0]['assistant_id'] == pending['id']
    replay = _session(decode(initial))
    replay.data['expected'] = [{'id': entry['assistant_id'],
                               'signature': entry['assistant_signature']}
                              for entry in resumed.log]
    replay.import_inbox([replay._inbox_entry(entry) for entry in resumed.log])
    assert _run(replay) == result
    assert replay.log == resumed.log
    assert encode(board_copy(replay.state)) == encode(board_copy(saved_state))


def test_replacement_cannot_upgrade_command_only_to_special_ability():
    state = _state(5)
    request = {'action_type': 'command', 'action': _recruit(),
               'allowed_commands': list(rc.ROMAN_COMMANDS),
               'allowed_special_abilities': ['No SA']}
    upgraded = _recruit()
    upgraded['sa'] = rc.SA_BUILD
    with pytest.raises(ValueError, match='Special Ability is not allowed'):
        validate_response(state, request, {'replacement': upgraded})


def test_real_failed_recruit_retains_refusal_and_rng_through_rechoose():
    from fs_bot.engine.game_engine import ActionRejected, ACTION_PASS, resolve_card_turn
    from fs_bot.engine.supply_retry import current_receipt
    state = _state(5)
    state['current_card'] = state['current_card_id'] = 1
    state['next_card'] = state['next_card_id'] = 2
    state['resources'][rc.ROMANS] = 0
    for faction in state['eligibility']:
        state['eligibility'][faction] = rc.ELIGIBLE if faction == rc.ROMANS else rc.INELIGIBLE
    before = encode(state)
    rng = deepcopy(state['rng'])
    assert rng.randint(1, 6) == 5
    with pytest.raises(ActionRejected) as refused:
        resolve_card_turn(state, lambda *_: {'action': ACTION_COMMAND,
                          'player_action': _recruit()}, execute=True)
    receipt = current_receipt(state)
    assert receipt['answer'] is False
    assert refused.value.result['supply_reconsideration'] == receipt
    assert state['rng'].getstate() == rng.getstate()
    for key in ('spaces', 'resources', 'available'):
        assert encode(state[key]) == before[key]
    # Known refusal is authoritative even in a pure preview: no affordable
    # Recruit now exists, and trying a different Region cannot reroll it.
    from fs_bot.engine.moves import validate_player_action
    state_after_refusal = encode(state)
    assert not validate_player_action(state, rc.ROMANS, _recruit((rc.MANDUBII,)))[0]
    assert encode(state) == state_after_refusal
    with pytest.raises(ActionRejected) as again:
        resolve_card_turn(state, lambda *_: {'action': ACTION_COMMAND,
                          'player_action': _recruit((rc.MANDUBII,))}, execute=True)
    assert 'supply_reconsideration' not in again.value.result
    assert state['rng'].getstate() == rng.getstate()
    result = resolve_card_turn(state, lambda *_: {'action': ACTION_PASS}, execute=True)
    assert result['passes'] == [rc.ROMANS]
    assert state['rng'].getstate() == rng.getstate()
