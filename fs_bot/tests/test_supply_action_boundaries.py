"""§§4.1/8.6.6: Supply reconsideration belongs to the current effect boundary."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, move_piece, place_piece
from fs_bot.cards.card_effects import execute_event, _ally_tribe
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_COMMAND_SA
from fs_bot.engine.supply_reconsideration import validate_response
from fs_bot.engine.victory import calculate_victory_score
from fs_bot.tests.test_np_aedui_supply_action import _state, _recruit


def _build_carnutes(state, action, *, timing):
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 6)
    move_piece(state, rc.SEQUANI, rc.MANDUBII, rc.ROMANS, rc.LEADER)
    action.update(sa=rc.SA_BUILD, sa_timing=timing, sa_regions=[rc.CARNUTES])
    action['details']['build_plan'] = {'forts': [rc.CARNUTES], 'subdue': [], 'allies': []}


def test_before_build_refusal_is_not_presented_as_a_recruit_refusal():
    state = _state(5)
    action = _recruit((rc.PROVINCIA,))
    _build_carnutes(state, action, timing='before')
    observed = []
    before = count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA)

    def agent(board, faction, request):
        if request['kind'] == 'supply_refusal':
            observed.append(request['action_type'])
            assert count_pieces(board, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == before
            return {'continue': True}

    state['decision_agent'] = agent
    rng = deepcopy(state['rng'])
    rng.randint(1, 6)
    result = execute_decision(state, rc.ROMANS, {
        'action': ACTION_COMMAND_SA, 'player_action': action})
    assert result['executed'] and not result.get('errors'), result
    assert not result['sa_execution']['executed']
    assert observed == ['special_ability']
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == before + 1
    assert state['rng'].getstate() == rng.getstate()


def test_before_build_changes_victory_threshold_before_recruit_supply_check():
    state = _state(5)
    # Build needs no Supply agreement where the existing Lingones Roman Ally
    # permits selection. Subduing the Senones raises Rome's score 12 -> 13.
    move_piece(state, rc.PROVINCIA, rc.MANDUBII, rc.ROMANS, rc.LEGION, 8)
    move_piece(state, rc.SEQUANI, rc.MANDUBII, rc.ROMANS, rc.LEADER)
    assert state['spaces'][rc.MANDUBII]['control'] == rc.ROMAN_CONTROL
    assert state['tribes'][rc.TRIBE_LINGONES]['allied_faction'] == rc.ROMANS
    action = _recruit((rc.SEQUANI,))
    action.update(sa=rc.SA_BUILD, sa_timing='before', sa_regions=[rc.MANDUBII])
    action['details']['build_plan'] = {
        'forts': [], 'allies': [],
        'subdue': [{'region': rc.MANDUBII, 'tribe': rc.TRIBE_SENONES}]}
    observed = []

    def agent(board, faction, request):
        if request['kind'] == 'supply_refusal':
            observed.append(request)
            return {'continue': True}

    state['decision_agent'] = agent
    rng = state['rng'].getstate()
    result = execute_decision(state, rc.ROMANS, {
        'action': ACTION_COMMAND_SA, 'player_action': action})
    assert result['executed'] and not result.get('errors'), result
    assert result['sa_execution']['executed'] and not result['sa_execution'].get('errors')
    assert calculate_victory_score(state, rc.ROMANS) == 13
    assert state['resources'][rc.ROMANS] == 6  # Build 2 plus refused-Supply Recruit 2.
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 2
    assert not observed
    assert state['rng'].getstate() == rng


def test_first_interrupted_recruit_refusal_can_replace_whole_untouched_action():
    state = _state(5)
    action = _recruit()
    _build_carnutes(state, action, timing='during')
    action['details'].pop('recruit_plan')
    action['details']['command_parts'] = [_recruit((rc.SEQUANI,)), _recruit((rc.MANDUBII,))]
    replacement = {'command': rc.CMD_MARCH, 'regions': [], 'sa': 'No SA', 'details': {
        'origins': [rc.SEQUANI], 'destinations': [rc.UBII],
        'routes': {rc.SEQUANI: [rc.UBII]}, 'groups': {rc.SEQUANI: {rc.AUXILIA: 1}}}}
    observed = []

    def agent(board, faction, request):
        if request['kind'] == 'supply_refusal':
            assert request['action'] == action
            assert rc.CMD_MARCH in request['allowed_commands']
            observed.append(request)
            return {'replacement': replacement}

    state['decision_agent'] = agent
    result = execute_decision(state, rc.ROMANS, {
        'action': ACTION_COMMAND_SA, 'player_action': action})
    assert result['executed'] and result['command'] == rc.CMD_MARCH, result
    assert len(observed) == 1
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(state, rc.UBII, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.FORT) == 0


def test_later_recruit_replacement_cannot_reselect_completed_region():
    state = _state(5)
    action = _recruit()
    _build_carnutes(state, action, timing='during')
    action['details'].pop('recruit_plan')
    action['details']['command_parts'] = [_recruit((rc.PROVINCIA,)), _recruit((rc.SEQUANI,))]
    before = count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA)
    observed = []

    def agent(board, faction, request):
        if request['kind'] != 'supply_refusal':
            return None
        observed.append(request['action_type'])
        if request['action_type'] == 'special_ability':
            return {'continue': True}
        assert request['continuation'] is True
        assert request['excluded_regions'] == [rc.PROVINCIA]
        assert request['allowed_commands'] == [rc.CMD_RECRUIT]
        assert count_pieces(board, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == before + 1
        with pytest.raises(ValueError, match='reselects a Region'):
            validate_response(board, request, {'replacement': _recruit((rc.PROVINCIA,))})
        return {'replacement': _recruit((rc.MANDUBII,))}

    state['decision_agent'] = agent
    result = execute_decision(state, rc.ROMANS, {
        'action': ACTION_COMMAND_SA, 'player_action': action})
    assert result['executed'] and not result.get('errors'), result
    assert observed == ['special_ability', 'command']
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == before + 1
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 2


def test_replacement_scout_binds_its_new_diviciacus_borrowing_selection():
    state = _state(5, diviciacus_option=True)
    action = _recruit((rc.PROVINCIA,))
    _build_carnutes(state, action, timing='after')
    state['event_params'] = {'region': rc.MANDUBII}
    execute_event(state, rc.CARD_O38)
    observed = []

    def agent(board, faction, request):
        if request['kind'] != 'supply_refusal':
            return None
        observed.append(request['action_type'])
        revised = deepcopy(request['action'])
        revised.update(sa=rc.SA_SCOUT, sa_regions=[rc.CARNUTES])
        revised['details'].pop('build_plan')
        revised['details']['diviciacus_sa_regions'] = [rc.CARNUTES]
        # Only one physical Roman Auxilia is present. Two borrowed Aedui
        # Warbands must actually move under the replacement Scout's scope.
        revised['details']['scout_plan'] = {
            'auxilia_moves': [{'from_region': rc.CARNUTES, 'to_region': rc.MANDUBII,
                              'count': 2, 'piece_state': rc.HIDDEN}],
            'scout_targets': []}
        return {'replacement': revised}

    state['decision_agent'] = agent
    result = execute_decision(state, rc.ROMANS, {
        'action': ACTION_COMMAND_SA, 'player_action': action})
    assert result['executed'] and not result.get('errors'), result
    assert result['sa_execution']['executed'] and not result['sa_execution'].get('errors'), result
    assert result['sa_execution']['sa'] == rc.SA_SCOUT
    assert observed == ['special_ability']
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 4
    assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND) == 8
    assert '_diviciacus_force' not in state


def test_recruit_after_completed_build_cannot_become_seize_in_its_subdued_region():
    state = _state(5)
    assert _ally_tribe(state, rc.TRIBE_ATREBATES, rc.BELGAE)
    assert calculate_victory_score(state, rc.ROMANS) == 11
    move_piece(state, rc.PROVINCIA, rc.MANDUBII, rc.ROMANS, rc.LEGION, 8)
    move_piece(state, rc.SEQUANI, rc.MANDUBII, rc.ROMANS, rc.LEADER)
    action = _recruit((rc.SEQUANI,))
    action.update(sa=rc.SA_BUILD, sa_timing='before', sa_regions=[rc.MANDUBII])
    action['details']['build_plan'] = {
        'forts': [], 'allies': [],
        'subdue': [{'region': rc.MANDUBII, 'tribe': rc.TRIBE_SENONES}]}
    observed = []

    def agent(board, faction, request):
        if request['kind'] != 'supply_refusal':
            return None
        assert request['action_type'] == 'command'
        assert calculate_victory_score(board, rc.ROMANS) == 12
        assert board['tribes'][rc.TRIBE_SENONES]['allied_faction'] is None
        replacement = {'command': rc.CMD_SEIZE, 'regions': [rc.MANDUBII],
                       'sa': 'No SA', 'details': {}}
        with pytest.raises(ValueError, match='Build|Seize'):
            validate_response(board, request, {'replacement': replacement})
        observed.append(request)
        return {'continue': True}

    state['decision_agent'] = agent
    result = execute_decision(state, rc.ROMANS, {
        'action': ACTION_COMMAND_SA, 'player_action': action})
    assert result['executed'] and not result.get('errors'), result
    assert len(observed) == 1
    assert state['resources'][rc.ROMANS] == 6
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 2
