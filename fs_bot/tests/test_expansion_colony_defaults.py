"""Card 71's Colony is a Tribe, including A45/A36 default Region selection."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, get_available
from fs_bot.cards.card_effects import execute_card_71, _ally_tribe, _unally_tribe
from fs_bot.cards.expansion_validation import _default_entry, default_params, next_choice
from fs_bot.engine.execute import _execute_event
from fs_bot.state.state_schema import build_initial_state, validate_state


def colony_board(region, owner, *, subdued=False):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=317)
    state['executing_faction'] = owner
    state['event_params'] = {'region': region}
    execute_card_71(state)
    colony = next(tribe for tribe, info in state['tribes'].items()
                  if info.get('region') == region)
    if subdued:
        _unally_tribe(state, colony)
    state['event_params'] = None
    assert validate_state(state) == []
    return state, colony


def event(state, card, faction):
    return _execute_event(state, faction, {
        'command': rc.FIRST_DID_EVENT, 'regions': [], 'sa': 'No SA', 'sa_regions': [],
        'details': {'card_id': card,
                    'text_preference': rc.EVENT_SHADED if card == 'A36' else rc.EVENT_UNSHADED}})


def occupy_other_a45_tribes(state, keep):
    """Leave exactly the desired Subdued choices using real available Allies."""
    choices = next_choice(state, 'A45', rc.AEDUI, {})['options']
    for tribe in dict.fromkeys(entry['tribe'] for entry in choices):
        if tribe in keep:
            continue
        owners = [entry['faction'] for entry in choices if entry['tribe'] == tribe]
        owner = max(owners, key=lambda faction: get_available(state, faction, rc.ALLY))
        _ally_tribe(state, tribe, owner)
    assert validate_state(state) == []


def test_a45_default_and_live_event_accept_colony_among_ordinary_tribes():
    # Card 71 explicitly makes a Colony a Tribe. A45 permits up to three
    # non-German Allies near an Intimidated marker, including that Tribe.
    state, colony = colony_board(rc.MANDUBII, rc.AEDUI, subdued=True)
    state['markers'].setdefault(rc.SEQUANI, {})[rc.MARKER_INTIMIDATED] = True
    targets = {colony, rc.TRIBE_SENONES, rc.TRIBE_LINGONES}
    occupy_other_a45_tribes(state, targets)
    planned = deepcopy(state)
    plan = default_params(planned, 'A45', rc.AEDUI)
    assert len(plan['placements']) == 3
    assert {entry['tribe'] for entry in plan['placements']} == targets
    assert all(entry['faction'] == rc.AEDUI for entry in plan['placements'])
    assert event(state, 'A45', rc.AEDUI)['executed']
    for entry in plan['placements']:
        assert state['tribes'][entry['tribe']]['allied_faction'] == rc.AEDUI
    assert state['tribes'][colony]['region'] == rc.MANDUBII
    assert validate_state(state) == []


def test_a36_default_and_live_event_remove_colony_and_ordinary_ally():
    # Cross Rhenus removes any two Allies within one Region of Sugambri.
    # Both the printed Tribe and the Colony are physical Belgic Allies.
    state, colony = colony_board(rc.TREVERI, rc.BELGAE)
    _ally_tribe(state, rc.TRIBE_NERVII, rc.BELGAE)
    state['executing_faction'] = rc.GERMANS
    plan = default_params(deepcopy(state), 'A36', rc.GERMANS)
    assert {entry['tribe'] for entry in plan['ally_removals']} == {colony, rc.TRIBE_NERVII}
    assert event(state, 'A36', rc.GERMANS)['executed']
    assert state['tribes'][colony]['allied_faction'] is None
    assert state['tribes'][rc.TRIBE_NERVII]['allied_faction'] is None
    assert sum(count_pieces(state, region, rc.GERMANS, rc.SETTLEMENT)
               for region in state['spaces']) == 2
    assert sum(count_pieces(state, region, rc.GERMANS, rc.WARBAND)
               for region in state['spaces']) == 4
    assert validate_state(state) == []


def test_default_remembers_colony_region_after_first_placement():
    state, colony = colony_board(rc.MANDUBII, rc.AEDUI, subdued=True)
    state['markers'].setdefault(rc.SEQUANI, {})[rc.MARKER_INTIMIDATED] = True
    occupy_other_a45_tribes(state, {colony, rc.TRIBE_LINGONES, rc.TRIBE_HELVETII})
    state['rng'].seed(6)  # Equal first choices select the Mandubii Colony.
    plan = default_params(state, 'A45', rc.AEDUI)
    # §8.3.1 then completes Mandubii before moving to Helvetii in Sequani.
    assert [entry['tribe'] for entry in plan['placements']] == [
        colony, rc.TRIBE_LINGONES, rc.TRIBE_HELVETII]


@pytest.mark.parametrize('card,region,other_tribe,owner,subdued', [
    ('A45', rc.MANDUBII, rc.TRIBE_HELVETII, rc.AEDUI, True),
    ('A36', rc.TREVERI, rc.TRIBE_NERVII, rc.GERMANS, False),
])
def test_default_exhausts_selected_colony_region_before_other_equal_regions(
        card, region, other_tribe, owner, subdued):
    # §8.3.1 exhausts the selected Region before selecting another equal
    # one. A dynamic Tribe's geography must participate in that comparison.
    state, colony = colony_board(region, rc.BELGAE, subdued=subdued)
    if not subdued:
        _ally_tribe(state, other_tribe, rc.BELGAE)
    choices = [{'tribe': tribe, **({'faction': owner} if card == 'A45' else {})}
               for tribe in (other_tribe, colony)]
    before_rng = state['rng'].getstate()
    assert _default_entry(state, card, owner, choices, previous_region=region)['tribe'] == colony
    # A sole remaining candidate needs no arbitrary random selection.
    assert state['rng'].getstate() == before_rng
