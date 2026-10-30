"""Voluntary removal keeps the exact moving cohort and already paid origins."""
import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (place_piece, count_pieces, count_pieces_by_state,
                                  get_leader_in_region)
from fs_bot.engine import action_windows, execute, voluntary_removal
from fs_bot.engine.diviciacus import force_scope
from fs_bot.engine.spring import UNLOCK_KEY
from fs_bot.state.state_schema import build_initial_state, validate_state


def board():
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=92)
    state['resources'][rc.ROMANS] = 20
    return state


class Agent:
    supports_action_windows = True
    def __init__(self, choose):
        self.choose, self.did = choose, False
    def __call__(self, state, faction, request):
        answer = self.choose(self, state, faction, request)
        if answer is not None:
            return answer
        if request['kind'] == voluntary_removal.KIND:
            return {'done': True}
        if request['kind'] == 'spring_leader':
            return {'defer': True}
        return None


def remove_at(region, *, cohort=None, piece=rc.AUXILIA, stage='march_arrival'):
    def choose(agent, state, faction, request):
        window = request.get('window', {})
        if (not agent.did and request['kind'] == voluntary_removal.KIND
                and window.get('stage') == stage and window.get('region') == region):
            choices = [c for c in request['options'] if c['region'] == region
                       and c['piece_type'] == piece and c.get('cohort') == cohort]
            assert len(choices) == 1, choices
            agent.did = True
            return {'operations': [voluntary_removal.operation(choices[0])]}
    return choose


@pytest.mark.parametrize('moving', [False, True])
def test_midroute_removal_selects_moving_or_resident_counter(moving):
    state = board()
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 3)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, 2)
    state['decision_agent'] = Agent(remove_at(rc.NERVII,
        cohort='moving_group' if moving else None))
    with action_windows.scope(state, actor=rc.ROMANS, force=True):
        final = execute._march_with_harassment(state, rc.ROMANS, rc.MORINI,
            [rc.NERVII, rc.ATREBATES], harassers_by_region={rc.NERVII: []})
    assert final == rc.ATREBATES
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == (2 if moving else 3)
    assert count_pieces(state, rc.NERVII, rc.ROMANS, rc.AUXILIA) == (2 if moving else 1)
    assert validate_state(state) == []


def test_removing_carried_caesar_recomputes_third_step_allowance():
    state = board()
    place_piece(state, rc.NERVII, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, 2)
    state['decision_agent'] = Agent(remove_at(rc.TREVERI,
        cohort='moving_group', piece=rc.LEADER))
    with action_windows.scope(state, actor=rc.ROMANS, force=True):
        final = execute._march_with_harassment(state, rc.ROMANS, rc.NERVII,
            [rc.TREVERI, rc.SEQUANI, rc.AEDUI_REGION],
            harassers_by_region={rc.TREVERI: [], rc.SEQUANI: []})
    assert final == rc.SEQUANI
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 2
    assert get_leader_in_region(state, rc.SEQUANI, rc.ROMANS) is None
    assert validate_state(state) == []


def test_vercingetorix_entering_after_group_selection_does_not_join_it():
    state = board()
    # Put the sole physical named Leader in the Spring box, as Pax setup does.
    state['available'][rc.ARVERNI][rc.LEADER] -= 1
    state['spring_box_leaders'] = [rc.VERCINGETORIX]
    state[UNLOCK_KEY] = True
    place_piece(state, rc.MORINI, rc.ARVERNI, rc.WARBAND, 2)
    def choose(agent, current, faction, request):
        if (request['kind'] == 'spring_leader'
                and request.get('window', {}).get('stage') == 'march_before_step'):
            return {'region': rc.MORINI}
    state['decision_agent'] = Agent(choose)
    with action_windows.scope(state, actor=rc.ARVERNI, force=True):
        execute._march_with_harassment(state, rc.ARVERNI, rc.MORINI, [rc.NERVII])
    assert get_leader_in_region(state, rc.MORINI, rc.ARVERNI) == rc.VERCINGETORIX
    assert get_leader_in_region(state, rc.NERVII, rc.ARVERNI) is None
    assert count_pieces(state, rc.NERVII, rc.ARVERNI, rc.WARBAND) == 2
    assert validate_state(state) == []


def test_event_executor_removes_own_lent_marching_warband_not_roman_auxilia():
    state = board()
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.MORINI, rc.AEDUI, rc.WARBAND, 2)
    place_piece(state, rc.NERVII, rc.AEDUI, rc.WARBAND)
    state['decision_agent'] = Agent(remove_at(rc.NERVII,
        cohort='moving_group', piece=rc.WARBAND))
    with action_windows.scope(state, actor=rc.AEDUI, force=True):
        with force_scope(state, rc.ROMANS, [rc.MORINI]):
            execute._march_with_harassment(state, rc.ROMANS, rc.MORINI,
                [rc.NERVII, rc.ATREBATES], harassers_by_region={rc.NERVII: []})
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND) == 1
    assert count_pieces(state, rc.NERVII, rc.AEDUI, rc.WARBAND) == 1
    assert validate_state(state) == []


def test_later_origin_removal_does_not_refund_selected_origin_cost():
    state = board()
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA)
    def choose(agent, current, faction, request):
        if (not agent.did and request['kind'] == voluntary_removal.KIND
                and request.get('window', {}).get('stage') == 'march_arrival'):
            choice = next(c for c in request['options'] if c['region'] == rc.ATREBATES)
            agent.did = True
            return {'operations': [voluntary_removal.operation(choice)]}
    state['decision_agent'] = Agent(choose)
    with action_windows.scope(state, actor=rc.ROMANS, force=True):
        result = execute._execute_march_moves(state, rc.ROMANS, [
            {'origin': rc.MORINI, 'path': [rc.NERVII]},
            {'origin': rc.ATREBATES, 'path': [rc.CARNUTES]}])
    assert result['total_cost'] == 4
    assert state['resources'][rc.ROMANS] == 16
    assert len(result['marches']) == 1
    assert validate_state(state) == []


def test_enlisted_harassment_updates_exact_owner_and_visibility_ledgers():
    from fs_bot.commands.sa_enlist import BORROW_KEY
    from fs_bot.commands.march import _resolve_one_harassment_loss, march_group
    state = board()
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND)
    state[BORROW_KEY] = {'pieces': {rc.NERVII: {rc.HIDDEN: 1}}}
    group = {rc.WARBAND: 2, 'german_warbands': 1,
             '_march_visibility': {rc.WARBAND: {rc.HIDDEN: 2}},
             '_march_owner_visibility': {rc.BELGAE: {rc.HIDDEN: 1},
                                         rc.GERMANS: {rc.HIDDEN: 1}}}
    def choose(agent, current, faction, request):
        if request['kind'] == 'harassment_loss' and request['phase'] == 'physical_owner':
            return {'choice': rc.BELGAE}
    state['decision_agent'] = Agent(choose)
    _resolve_one_harassment_loss(state, rc.NERVII, rc.BELGAE, group)
    assert group[rc.WARBAND] == group['german_warbands'] == 1
    assert group['_march_owner_visibility'][rc.BELGAE][rc.HIDDEN] == 0
    march_group(state, rc.BELGAE, rc.NERVII, [rc.ATREBATES], group)
    assert state['spaces'][rc.ATREBATES]['pieces'][rc.GERMANS][rc.HIDDEN][rc.WARBAND] == 1
    assert count_pieces_by_state(state, rc.NERVII, rc.BELGAE, rc.WARBAND, rc.HIDDEN) == 0
    assert validate_state(state) == []


def test_direct_event_march_uses_same_exact_selected_group_window():
    from fs_bot.commands.march import march_group
    state = board()
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 3)
    state['decision_agent'] = Agent(remove_at(rc.MORINI,
        cohort='moving_group', stage='march_before_step'))
    group = {rc.AUXILIA: 2}
    with action_windows.scope(state, actor=rc.ROMANS, force=True):
        march_group(state, rc.ROMANS, rc.MORINI, [rc.NERVII], group, free=True)
    assert count_pieces(state, rc.MORINI, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(state, rc.NERVII, rc.ROMANS, rc.AUXILIA) == 1
    assert validate_state(state) == []


def test_enlisted_dropoff_keeps_exact_carried_owner_ledger():
    from fs_bot.commands.sa_enlist import BORROW_KEY
    from fs_bot.commands.march import march_group
    from fs_bot.engine.march_choices import drop_visibility
    state = board()
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND)
    state[BORROW_KEY] = {'pieces': {rc.NERVII: {rc.HIDDEN: 1}}}
    group = {rc.WARBAND: 2, 'german_warbands': 1,
             '_march_visibility': {rc.WARBAND: {rc.HIDDEN: 2}},
             '_march_owner_visibility': {rc.BELGAE: {rc.HIDDEN: 1},
                                         rc.GERMANS: {rc.HIDDEN: 1}}}
    def choose(agent, current, faction, request):
        if request['kind'] == 'force_cohort':
            return {'counts': {'selected': 0, 'other': 1}}
    state['decision_agent'] = Agent(choose)
    drop_visibility(state, rc.BELGAE, rc.NERVII, group, rc.WARBAND, 1)
    assert group['german_warbands'] == group[rc.WARBAND] == 1
    march_group(state, rc.BELGAE, rc.NERVII, [rc.ATREBATES], group)
    assert state['spaces'][rc.NERVII]['pieces'][rc.BELGAE][rc.HIDDEN][rc.WARBAND] == 1
    assert state['spaces'][rc.ATREBATES]['pieces'][rc.GERMANS][rc.HIDDEN][rc.WARBAND] == 1
    assert validate_state(state) == []
