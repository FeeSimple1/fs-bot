"""Both sides of A38 persist and replace/remove one another (§5.3)."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.cards.capabilities import (get_active_capabilities,
    is_capability_active, deactivate_capability)
from fs_bot.cards.card_effects import execute_event
from fs_bot.cards.event_eval import is_event_effective, is_capability_final_year
from fs_bot.commands.sa_suborn import suborn_limits, suborn_operation_cost
from fs_bot.engine.winter import spring_phase
from fs_bot.state.state_schema import build_initial_state


def state(*, legacy=False):
    st = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=4)
    if legacy:
        st.setdefault('event_modifiers', {})['card_A38_suborn_enhanced'] = True
    else:
        execute_event(st, 'A38')
    return st


def test_unshaded_is_persistent_capability_and_free_auxilia():
    st = state()
    assert st['capabilities']['A38'] == rc.EVENT_UNSHADED
    assert suborn_limits(st) == (4, 2)
    assert suborn_operation_cost(st, {'action': 'place', 'piece_type': rc.AUXILIA}) == 0
    spring_phase(st)
    assert is_capability_active(st, 'A38', rc.EVENT_UNSHADED)
    assert suborn_limits(st) == (4, 2)


@pytest.mark.parametrize('legacy', [False, True])
def test_shaded_replaces_unshaded_and_drops_enhancement(legacy):
    st = state(legacy=legacy)
    execute_event(st, 'A38', shaded=True)
    assert is_capability_active(st, 'A38', rc.EVENT_SHADED)
    assert not is_capability_active(st, 'A38', rc.EVENT_UNSHADED)
    assert 'card_A38_suborn_enhanced' not in st['event_modifiers']
    assert suborn_limits(st) == (3, 1)
    assert suborn_operation_cost(st, {'action': 'place', 'piece_type': rc.AUXILIA}) == 1
    execute_event(st, 'A38')
    assert get_active_capabilities(st) == {'A38': rc.EVENT_UNSHADED}
    assert suborn_limits(st) == (4, 2)


@pytest.mark.parametrize('legacy', [False, True])
@pytest.mark.parametrize('explicit_target', [False, True])
def test_shifting_loyalties_removes_new_or_legacy_vergobret(legacy, explicit_target):
    st = state(legacy=legacy)
    assert is_event_effective(st, 50)
    if explicit_target:
        st['event_params'] = {'target_capability': 'A38'}
    execute_event(st, 50)
    assert get_active_capabilities(st) == {}
    assert not is_event_effective(st, 50)
    assert suborn_limits(st) == (3, 1)
    assert 'card_A38_suborn_enhanced' not in st['event_modifiers']


def test_legacy_lookup_is_read_only_and_explicit_side_wins():
    st = state(legacy=True)
    before = deepcopy(st)
    assert get_active_capabilities(st) == {'A38': rc.EVENT_UNSHADED}
    assert is_capability_active(st, 'A38', rc.EVENT_UNSHADED)
    assert st.keys() == before.keys()
    assert st['capabilities'] == before['capabilities'] == {}
    assert st['event_modifiers'] == before['event_modifiers']
    st['capabilities']['A38'] = rc.EVENT_SHADED
    assert suborn_limits(st) == (3, 1)
    assert deactivate_capability(st, 'A38') == rc.EVENT_SHADED
    assert not is_capability_active(st, 'A38')


def test_last_year_declines_both_vergobret_capability_sides():
    st = state()
    st['deck'] = ['A38', 'W4']
    assert is_capability_final_year(st, 'A38', shaded=False)
    assert is_capability_final_year(st, 'A38', shaded=True)


def test_capability_lookup_does_not_add_missing_dictionary():
    st = {'event_modifiers': {'card_A38_suborn_enhanced': True}}
    assert get_active_capabilities(st) == {'A38': rc.EVENT_UNSHADED}
    assert 'capabilities' not in st
