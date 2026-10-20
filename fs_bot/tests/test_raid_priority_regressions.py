"""Raid priority/resource regressions from §3.3.3, §§8.5–8.7 and A8.7.3."""
import importlib

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces_by_state
from fs_bot.cards.capabilities import activate_capability, set_capability_owner
from fs_bot.commands.raid import raid_in_region, validate_raid_steal_target
from fs_bot.commands.common import CommandError
from fs_bot.state.state_schema import build_initial_state
from fs_bot.state.serialize import encode

CASES = [
    (rc.BELGAE, rc.ROMANS, 'belgae_bot', rc.SCENARIO_PAX_GALLICA),
    (rc.ARVERNI, rc.ROMANS, 'arverni_bot', rc.SCENARIO_PAX_GALLICA),
    (rc.AEDUI, rc.BELGAE, 'aedui_bot', rc.SCENARIO_PAX_GALLICA),
    (rc.GERMANS, rc.ROMANS, 'german_bot', rc.SCENARIO_ARIOVISTUS),
]


def raid_state(faction, target, scenario, *, regions=(rc.NERVII,), resources=3):
    state = build_initial_state(scenario, seed=17)
    state['non_player_factions'] = {faction}
    state['resources'][faction] = 0
    state['resources'][target] = resources
    for region in regions:
        place_piece(state, region, faction, rc.WARBAND, 2)
        place_piece(state, region, target, rc.ALLY, 1)
    return state


@pytest.mark.parametrize('faction,target,module,scenario', CASES)
def test_raid_uses_each_warband_against_preferred_target(faction, target, module, scenario):
    state = raid_state(faction, target, scenario)
    before = encode(state)
    enough, plan = importlib.import_module('fs_bot.bots.' + module)._would_raid_gain_enough(state, scenario)
    assert enough
    assert plan == [{'region': rc.NERVII, 'target': target}] * 2
    assert encode(state) == before
    result = raid_in_region(state, rc.NERVII, faction,
                            [{'type': 'steal', 'target': target}] * 2)
    assert result['resources_stolen'] == {target: 2}
    assert state['resources'][target] == 1
    assert state['resources'][faction] == 2


@pytest.mark.parametrize('faction,target,module,scenario', CASES)
def test_raid_repeated_steals_share_budget_across_regions(faction, target, module, scenario):
    state = raid_state(faction, target, scenario, regions=(rc.NERVII, rc.TREVERI))
    enough, plan = importlib.import_module('fs_bot.bots.' + module)._would_raid_gain_enough(state, scenario)
    assert enough and len(plan) == 4
    assert sum(entry['target'] == target for entry in plan) == 3
    assert sum(entry['target'] is None for entry in plan) == 1


@pytest.mark.parametrize('faction,target,module,scenario', CASES)
def test_two_steals_in_devastated_region_can_qualify_raid(faction, target, module, scenario):
    state = raid_state(faction, target, scenario, resources=2)
    state['markers'].setdefault(rc.NERVII, {})[rc.MARKER_DEVASTATED] = True
    enough, plan = importlib.import_module('fs_bot.bots.' + module)._would_raid_gain_enough(state, scenario)
    assert enough and len(plan) == 2
    assert all(entry['target'] == target for entry in plan)


def test_arverni_exhaust_roman_priority_before_aedui():
    state = raid_state(rc.ARVERNI, rc.ROMANS, rc.SCENARIO_PAX_GALLICA)
    place_piece(state, rc.NERVII, rc.AEDUI, rc.ALLY)
    state['resources'][rc.AEDUI] = 5
    from fs_bot.bots.arverni_bot import _would_raid_gain_enough
    _, plan = _would_raid_gain_enough(state, state['scenario'])
    assert all(entry['target'] == rc.ROMANS for entry in plan)
    state['resources'][rc.ROMANS] = 1
    _, plan = _would_raid_gain_enough(state, state['scenario'])
    assert [entry['target'] for entry in plan] == [rc.ROMANS, rc.AEDUI]


@pytest.mark.parametrize('scenario', [rc.SCENARIO_PAX_GALLICA, rc.SCENARIO_ARIOVISTUS])
def test_card8_bypasses_fort_but_not_target_resource_requirement(scenario):
    state = raid_state(rc.BELGAE, rc.ROMANS, scenario, resources=0)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.FORT)
    activate_capability(state, 8, rc.EVENT_SHADED)
    set_capability_owner(state, 8, rc.BELGAE)
    before = encode(state)
    assert not validate_raid_steal_target(state, rc.NERVII, rc.BELGAE, rc.ROMANS)[0]
    with pytest.raises(CommandError, match='0 Resources'):
        raid_in_region(state, rc.NERVII, rc.BELGAE, [{'type': 'steal', 'target': rc.ROMANS}])
    assert encode(state) == before
    state['resources'][rc.ROMANS] = 1
    assert validate_raid_steal_target(state, rc.NERVII, rc.BELGAE, rc.ROMANS)[0]
    raid_in_region(state, rc.NERVII, rc.BELGAE, [{'type': 'steal', 'target': rc.ROMANS}])
    assert state['resources'][rc.ROMANS] == 0


@pytest.mark.parametrize('card8', [False, True])
def test_whole_raid_rejects_stealing_same_last_resource_twice(card8):
    state = raid_state(rc.BELGAE, rc.ROMANS, rc.SCENARIO_PAX_GALLICA, resources=1)
    if card8:
        activate_capability(state, 8, rc.EVENT_SHADED)
        set_capability_owner(state, 8, rc.BELGAE)
    before = encode(state)
    with pytest.raises(CommandError, match='no Resources remain'):
        raid_in_region(state, rc.NERVII, rc.BELGAE,
                       [{'type': 'steal', 'target': rc.ROMANS}] * 2)
    assert encode(state) == before
    assert count_pieces_by_state(state, rc.NERVII, rc.BELGAE, rc.WARBAND, rc.HIDDEN) == 2
