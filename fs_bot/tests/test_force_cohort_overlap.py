"""Diviciacus operations reconcile an overlapping Impetuosity force exactly."""
import pytest

from fs_bot import rules_consts as rc
from fs_bot.board import pieces
from fs_bot.commands.sa_enlist import FREE_FORCE_KEY
from fs_bot.engine.diviciacus import KEY, force_scope, validate_force_cohort_response
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import encode


@pytest.mark.parametrize('operation', ['remove', 'move', 'flip'])
@pytest.mark.parametrize('selected', [0, 1])
def test_physical_operation_updates_only_selected_event_members(operation, selected):
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=52)
    pieces.place_piece(state, rc.MORINI, rc.AEDUI, rc.WARBAND, 3)
    state[FREE_FORCE_KEY] = {'faction': rc.AEDUI, 'source': 'Impetuosity',
                             'pieces': {rc.MORINI: {rc.HIDDEN: 2}}}
    requests = []
    def agent(board, faction, request):
        assert faction == rc.ROMANS and request['kind'] == 'force_cohort'
        requests.append(request)
        return {'counts': {'selected': selected, 'other': 1 - selected}}
    state['decision_agent'] = agent
    rng = state['rng'].getstate()
    with force_scope(state, rc.ROMANS, [rc.MORINI], phase='defense'):
        params = {'physical_owner': rc.AEDUI}
        if operation == 'remove':
            pieces.remove_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA,
                                piece_state=rc.HIDDEN, **params)
        elif operation == 'move':
            pieces.move_piece(state, rc.MORINI, rc.NERVII, rc.ROMANS, rc.AUXILIA,
                              piece_state=rc.HIDDEN, **params)
        else:
            pieces.flip_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA,
                              from_state=rc.HIDDEN, to_state=rc.REVEALED, **params)
        assert state[KEY]['pieces'][rc.MORINI][rc.HIDDEN] == 2
        free = state[FREE_FORCE_KEY]['pieces']
        assert free[rc.MORINI][rc.HIDDEN] == 2 - selected
        if operation == 'move':
            assert free.get(rc.NERVII, {}).get(rc.HIDDEN, 0) == selected
        if operation == 'flip':
            assert free[rc.MORINI].get(rc.REVEALED, 0) == selected
    assert len(requests) == 1
    assert state['rng'].getstate() == rng
    assert validate_state(state) == []


def test_invalid_overlap_choice_leaves_physical_board_and_ledgers_unchanged():
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=53)
    pieces.place_piece(state, rc.MORINI, rc.AEDUI, rc.WARBAND, 3)
    state[FREE_FORCE_KEY] = {'faction': rc.AEDUI,
                             'pieces': {rc.MORINI: {rc.HIDDEN: 2}}}
    state['decision_agent'] = lambda *args: {'counts': {'selected': True}}
    with force_scope(state, rc.ROMANS, [rc.MORINI], phase='defense'):
        before = encode({k: v for k, v in state.items() if k != 'decision_agent'})
        with pytest.raises(ValueError, match='exactly'):
            pieces.remove_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA,
                piece_state=rc.HIDDEN, physical_owner=rc.AEDUI)
        assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before


def test_forced_overlap_allocation_and_unrelated_operations_add_no_rng_or_choice():
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=54)
    pieces.place_piece(state, rc.MORINI, rc.AEDUI, rc.WARBAND, 3)
    state[FREE_FORCE_KEY] = {'faction': rc.AEDUI,
                             'pieces': {rc.MORINI: {rc.HIDDEN: 3}}}
    state['decision_agent'] = lambda *args: pytest.fail('Forced cohort allocation prompted')
    rng = state['rng'].getstate()
    with force_scope(state, rc.ROMANS, [rc.MORINI]):
        pieces.remove_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA,
                            physical_owner=rc.AEDUI, piece_state=rc.HIDDEN)
    assert state[FREE_FORCE_KEY]['pieces'][rc.MORINI][rc.HIDDEN] == 2
    assert state['rng'].getstate() == rng


@pytest.mark.parametrize('response', [None, {'counts': {}}, {'counts': {'selected': 2}},
    {'counts': {'selected': 1}, 'grant': True}, {'use_default': 1}])
def test_force_cohort_response_shape_and_counts_are_strict(response):
    request = {'count': 1, 'available': {'selected': 2, 'other': 1}}
    with pytest.raises(ValueError):
        validate_force_cohort_response(request, response)
