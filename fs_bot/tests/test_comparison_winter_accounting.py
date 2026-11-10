"""WS3-01/02: physical Harvest counts and the upcoming Lost Eagle Senate window."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_allied_discs, count_on_map
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.winter import harvest_phase, senate_phase, _senate_marker_shift
from fs_bot.state.serialize import decode, encode
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import check_structural_integrity, validate_state


def event(state, card, shaded=False, params=None):
    state['current_card'] = card
    result = execute_decision(state, rc.ROMANS, {'action': 'event', 'player_action': {
        'command': rc.FIRST_DID_EVENT, 'regions': [], 'sa': 'No SA', 'sa_regions': [],
        'details': {'card_id': card, 'event_params': params or {},
                    'text_preference': rc.EVENT_SHADED if shaded else rc.EVENT_UNSHADED}}})
    assert result['executed'] and not result.get('errors'), result
    return result


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
@pytest.mark.parametrize('starting_resources', [0, 44])
def test_harvest_counts_each_physical_structure_once_in_every_scenario(scenario, starting_resources):
    state = setup_scenario(scenario, seed=1)
    for faction in rc.GALLIC_FACTIONS:
        state['resources'][faction] = starting_resources
    expected = {f: 2 * (count_allied_discs(state, f) + count_on_map(state, f, rc.CITADEL))
                   + (4 if f == rc.AEDUI else 0) for f in rc.GALLIC_FACTIONS}
    if scenario in rc.ARIOVISTUS_SCENARIOS:
        expected[rc.ARVERNI] = 0
        expected[rc.GERMANS] = 2 * (count_allied_discs(state, rc.GERMANS)
                                   + count_on_map(state, rc.GERMANS, rc.SETTLEMENT))
        state['resources'][rc.GERMANS] = starting_resources
    result = harvest_phase(state)
    assert {f: result[f] for f in expected} == expected
    for faction, amount in expected.items():
        assert state['resources'][faction] == min(45, starting_resources + amount)
    assert validate_state(state) == check_structural_integrity(state) == []


@pytest.mark.parametrize('scenario,faction,amount', [
    (rc.SCENARIO_RECONQUEST, rc.AEDUI, 10),
    (rc.SCENARIO_GREAT_REVOLT, rc.ARVERNI, 20),
    (rc.SCENARIO_GREAT_REVOLT, rc.AEDUI, 10),
])
def test_printed_initialized_harvest_totals(scenario, faction, amount):
    assert harvest_phase(setup_scenario(scenario, seed=1))[faction] == amount


@pytest.mark.parametrize('card', [1, 3])
@pytest.mark.parametrize('position,firm', [(rc.INTRIGUE, False), (rc.ADULATION, False),
                                           (rc.UPROAR, True)])
def test_lost_eagle_does_not_restrict_intervening_cicero_or_pompey(card, position, firm):
    state = setup_scenario(rc.SCENARIO_RECONQUEST, seed=1)
    state['non_player_factions'] = set()
    state['senate'] = {'position': position, 'firm': firm}
    control = deepcopy(state)
    event(state, 33, shaded=True)
    params = {'senate_direction': rc.SENATE_DOWN} if card == 1 else {}
    event(state, card, params=params)
    event(control, card, params=params)
    assert state['senate'] == control['senate']
    assert state['event_modifiers']['lost_eagle_no_shift_down'] is True


@pytest.mark.parametrize('first_phase', ['pax_forced', 'pax_box', 'post_interlude'])
def test_scenario_senate_exception_still_expires_lost_eagle(first_phase):
    state = setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=1)
    state['non_player_factions'] = set()
    event(state, 33, shaded=True)
    if first_phase == 'post_interlude':
        state['interlude_completed'] = True
        state['senate'] = {'position': rc.INTRIGUE, 'firm': False}
        original = deepcopy(state['senate'])
        senate_phase(state, first_senate_after_interlude=True)
        assert state['senate'] == original
    else:
        senate_phase(state, **({'force_position': rc.INTRIGUE} if first_phase == 'pax_forced' else {}))
        assert state['senate'] == {'position': rc.INTRIGUE, 'firm': False}
    assert 'lost_eagle_no_shift_down' not in state['event_modifiers']
    # Save/load the phase boundary, then compare the next normal Senate.
    restored = decode(encode(state))
    control = deepcopy(restored)
    control['event_modifiers'].pop('lost_eagle_no_shift_down', None)
    assert senate_phase(restored) == senate_phase(control)
    assert restored['senate']['position'] == rc.ADULATION


@pytest.mark.parametrize('position', [rc.INTRIGUE, rc.ADULATION])
def test_upcoming_normal_senate_still_blocks_downward_shift_or_firm_flip(position):
    state = setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=1)
    state['senate'] = {'position': position, 'firm': False}
    event(state, 33, shaded=True)
    before = deepcopy(state['senate'])
    result = _senate_marker_shift(state)
    assert result['reason'] == 'Lost Eagle prevents downward shift'
    assert state['senate'] == before
    assert 'lost_eagle_no_shift_down' not in state['event_modifiers']
    _senate_marker_shift(state)
    assert state['senate'] != before
