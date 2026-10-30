"""§8.6.6 reconsideration retains Event permissions and A53's paid budget."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, move_piece
from fs_bot.commands.rally import supply_agreement_scope
from fs_bot.engine.free_actions import execute_free_action_plan
from fs_bot.engine.frumentum import resolve_frumentum, _execute, ACTION_SA
from fs_bot.engine.supply_reconsideration import validate_response
from fs_bot.tests.test_np_aedui_supply_action import _state, _recruit
from fs_bot.tests.test_supply_action_boundaries import _build_carnutes
from fs_bot.tests.test_supply_refusal_choices import _march


@pytest.mark.parametrize('choice', ['continue', 'none', 'build'])
def test_standalone_free_build_refusal_keeps_sa_grant(choice):
    state = _state(5)
    action = _recruit((rc.PROVINCIA,))
    _build_carnutes(state, action, timing='before')
    action.pop('command')  # Event SA plans do not require a Command field.
    action['details'].pop('recruit_plan')
    move_piece(state, rc.PROVINCIA, rc.MANDUBII, rc.ROMANS, rc.LEGION, 8)
    grant = {'request_type': 'event_sa', 'allowed_sas': [rc.SA_BUILD],
             'allowed_regions': [rc.CARNUTES, rc.MANDUBII]}
    seen = []

    def agent(board, faction, request):
        assert request['kind'] == 'supply_refusal'
        assert request['action_type'] == 'special_ability'
        assert request['allowed_special_abilities'] == [rc.SA_BUILD, 'No SA']
        seen.append(request)
        if choice == 'continue':
            return {'continue': True}
        replacement = deepcopy(request['action'])
        replacement.update(sa=rc.SA_BUILD if choice == 'build' else 'No SA',
                           sa_regions=[rc.MANDUBII] if choice == 'build' else [])
        replacement['details']['build_plan'] = {'subdue': [
            {'region': rc.MANDUBII, 'tribe': rc.TRIBE_SENONES}]} if choice == 'build' else {}
        outside = deepcopy(replacement)
        outside.update(sa=rc.SA_BUILD, sa_regions=[rc.MORINI])
        outside['details']['build_plan'] = {'forts': [rc.MORINI]}
        with pytest.raises(ValueError, match='outside the action grant'):
            validate_response(board, request, {'replacement': outside})
        return {'replacement': replacement}

    state['decision_agent'] = agent
    rng = deepcopy(state['rng'])
    rng.randint(1, 6)
    resources = state['resources'][rc.ROMANS]
    result = execute_free_action_plan(state, rc.ROMANS, grant, action)
    assert len(seen) == 1 and state['rng'].getstate() == rng.getstate()
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.FORT) == 0
    assert state['resources'][rc.ROMANS] == resources
    assert bool(result['executed']) == (choice == 'build')
    if choice == 'build':
        assert state['tribes'][rc.TRIBE_SENONES]['allied_faction'] is None


def test_free_frost_march_preserved_when_its_build_is_declined():
    state = _state(5)
    action = _march()
    _build_carnutes(state, action, timing='after')
    state['current_card'] = state['current_card_id'] = 1
    state['next_card'] = state['next_card_id'] = rc.WINTER_CARD
    from fs_bot.engine.game_engine import is_frost
    assert is_frost(state)
    grant = {'request_type': 'event_command', 'allowed_commands': [rc.CMD_MARCH],
             'with_sa': True, 'allowed_regions': [rc.SEQUANI, rc.CARNUTES]}
    seen = []

    def agent(board, faction, request):
        assert request['kind'] == 'supply_refusal'
        assert count_pieces(board, rc.UBII, rc.ROMANS, rc.AUXILIA) == 1
        replacement = deepcopy(request['action'])
        replacement.update(sa='No SA', sa_regions=[])
        replacement['details'].pop('build_plan')
        seen.append(request)
        return {'replacement': replacement}

    state['decision_agent'] = agent
    result = execute_free_action_plan(state, rc.ROMANS, grant, action)
    assert result['executed'] and not result.get('errors'), result
    assert len(seen) == 1
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(state, rc.UBII, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.FORT) == 0


def test_free_command_rechoice_cannot_march_to_britannia_after_build():
    # §4.1.3 applies even though the preceding SA must not be executed again
    # to validate a replacement and Event March itself is allowed in Frost.
    state = _state(5)
    state['current_card'], state['next_card'] = 1, rc.WINTER_CARD
    request = {'kind': 'supply_refusal', 'action_type': 'command',
               'action': _recruit(), 'allowed_commands': list(rc.ROMAN_COMMANDS),
               'allowed_special_abilities': ['No SA'], 'command_only': True,
               'accompanying_sa': rc.SA_BUILD,
               'completed_sa_result': {'sa': rc.SA_BUILD, 'executed': True,
                                       'actions': [('fort', rc.CARNUTES)]},
               'grant': {'request_type': 'event_command', 'with_sa': True}}
    replacement = {'command': rc.CMD_MARCH, 'sa': 'No SA', 'details': {
        'origins': [rc.MORINI], 'destinations': [rc.BRITANNIA],
        'routes': {rc.MORINI: [rc.BRITANNIA]}, 'groups': {rc.MORINI: {rc.AUXILIA: 1}}}}
    with pytest.raises(ValueError, match='Britannia'):
        validate_response(state, request, {'replacement': replacement})


def test_frumentum_zero_allocation_refusal_can_skip_current_recruit():
    # A8.6.6 gives human Romans no NPC Aedui funding. An initially free
    # Recruit can become unaffordable on the actual Supply die: skip it
    # without borrowing from Rome's treasury or reissuing the allocation.
    state = _state(5)
    treasury, aedui = state['resources'][rc.ROMANS], state['resources'][rc.AEDUI]
    seen = []

    def agent(board, faction, request):
        seen.append(request['kind'])
        if request['kind'] == 'supply_refusal':
            assert request['frumentum']['remaining_resources'] == 0
            with pytest.raises(ValueError):
                validate_response(board, request, {'continue': True})
            return {'replacement': {'skip': rc.CMD_RECRUIT}}
        assert request['kind'] == 'frumentum_action'
        if rc.CMD_RECRUIT in request['remaining_actions']:
            return _recruit((rc.SEQUANI,))
        return {'decline': True}

    state['decision_agent'] = agent
    result = resolve_frumentum(state)[0]
    assert seen == ['frumentum_action', 'supply_refusal', 'frumentum_action']
    assert result['allocated'] == result['spent'] == result['unused'] == 0
    assert state['resources'][rc.ROMANS] == treasury
    assert state['resources'][rc.AEDUI] == aedui
    assert result['actions'][0]['plan'] == {'skip': rc.CMD_RECRUIT}
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 1


@pytest.mark.parametrize('choice', ['recruit', 'march', 'none'])
def test_frumentum_refusal_replacement_keeps_paid_budget_and_unused_actions(choice):
    # Test the already-authorized paid-action executor, independently of
    # A8.6.6's separate funding policy (NPC Aedui give human Rome zero).
    state = _state(5)
    original = _recruit((rc.SEQUANI,))
    if choice == 'none':
        _build_carnutes(state, original, timing='before')
        original.pop('command')
        original['details'].pop('recruit_plan')
    request = {'kind': 'frumentum_action', 'remaining_actions': [rc.CMD_RECRUIT, ACTION_SA],
               'remaining_resources': 2, 'allocated_resources': 2,
               'reserved_roman_resources': state['resources'][rc.ROMANS]}
    if choice == 'march':
        request['remaining_actions'].append(rc.CMD_MARCH)
    treasury = state['resources'][rc.ROMANS]
    observed = []

    def agent(board, faction, req):
        assert req['kind'] == 'supply_refusal'
        observed.append(req)
        if choice == 'none':
            replacement = deepcopy(req['action'])
            replacement.update(sa='No SA', sa_regions=[])
            replacement['details'].pop('build_plan')
        else:
            replacement = _recruit((rc.MANDUBII,)) if choice == 'recruit' else _march()
            if choice == 'recruit':
                with pytest.raises(ValueError, match='not allowed'):
                    validate_response(board, req, {'replacement': _march()})
            too_costly = _recruit((rc.SEQUANI, rc.MANDUBII))
            with pytest.raises(ValueError):
                validate_response(board, req, {'replacement': too_costly})
        return {'replacement': replacement}

    state['decision_agent'] = agent
    with supply_agreement_scope(state):
        result, spent = _execute(state, original, 2, request=request)
    assert len(observed) == 1
    assert spent == (0 if choice == 'none' else 2)
    assert state['resources'][rc.ROMANS] == treasury
    assert not result.get('errors'), result
    assert result['supply_replacement']['sa'] == 'No SA'
    if choice == 'march':
        assert result['supply_replacement']['command'] == rc.CMD_MARCH
        assert count_pieces(state, rc.UBII, rc.ROMANS, rc.AUXILIA) == 1
