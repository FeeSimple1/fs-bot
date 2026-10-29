"""Printed NP thresholds measure legal quantities, including compulsory extras."""

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import get_available, place_piece
from fs_bot.bots.aedui_bot import node_a5, _estimate_rally_placements as aedui_estimate
from fs_bot.bots.arverni_bot import node_v3, _estimate_rally_placements as arverni_estimate
from fs_bot.bots.belgae_bot import node_b4, node_b_rally, _estimate_rally_would_qualify
from fs_bot.bots.bot_common import estimate_scoped_rally
from fs_bot.cards.capabilities import activate_capability, set_capability_owner
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity


def board(faction, scenario=rc.SCENARIO_GREAT_REVOLT):
    state = build_initial_state(scenario, seed=19)
    state['non_player_factions'] = set(rc.FACTIONS)
    state['resources'][faction] = 3
    # Keep enough Warbands on-map to avoid the Aedui/Arverni low-force gate.
    # They neither Control this Region nor have a Subdued Tribe to ally.
    place_piece(state, rc.SUGAMBRI, faction, rc.WARBAND, 5 if faction == rc.AEDUI else 9)
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, 6)
    place_piece(state, rc.SUGAMBRI, rc.ROMANS, rc.AUXILIA, 20)
    assert _ally_tribe(state, rc.TRIBE_SUGAMBRI, rc.GERMANS)
    assert _ally_tribe(state, rc.TRIBE_SUEBI_NORTH, rc.GERMANS)
    refresh_all_control(state)
    assert check_structural_integrity(state) == []
    return state


def aquitani(state, faction):
    activate_capability(state, 25, rc.EVENT_SHADED)
    set_capability_owner(state, 25, faction)


def pure_estimate(state, estimate):
    before = encode(state)
    state['decision_agent'] = lambda *_: pytest.fail('estimate consulted a live human')
    result = estimate(state, state['scenario'])
    del state['decision_agent']
    assert encode(state) == before
    return result


@pytest.mark.parametrize('scenario', rc.BASE_SCENARIOS + rc.ARIOVISTUS_SCENARIOS)
def test_aedui_three_piece_gate_counts_aquitani_in_empty_regions(scenario):
    state = board(rc.AEDUI, scenario)
    assert node_a5(state) == 'No'
    aquitani(state, rc.AEDUI)
    estimate = pure_estimate(state, aedui_estimate)
    assert estimate['allies'] == estimate['citadels'] == 0
    assert estimate['warbands'] == estimate['total'] == 5  # Home1 + Pictones2 + Arverni2.
    assert node_a5(state) == 'Yes'


@pytest.mark.parametrize('restriction', ['wrong_owner', 'no_resources', 'pool_shortage', 'devastated'])
def test_aedui_bonus_gate_respects_owner_cost_pool_and_region_restrictions(restriction):
    state = board(rc.AEDUI)
    aquitani(state, rc.AEDUI)
    if restriction == 'wrong_owner':
        set_capability_owner(state, 25, rc.ARVERNI)
    elif restriction == 'no_resources':
        state['resources'][rc.AEDUI] = 0
    elif restriction == 'pool_shortage':
        place_piece(state, rc.SUGAMBRI, rc.AEDUI, rc.WARBAND,
                    get_available(state, rc.AEDUI, rc.WARBAND) - 1)
        refresh_all_control(state)
    else:
        for region in (rc.PICTONES, rc.ARVERNI_REGION):
            state['markers'].setdefault(region, {})[rc.MARKER_DEVASTATED] = True
    estimate = pure_estimate(state, aedui_estimate)
    assert estimate['allies'] == estimate['citadels'] == 0
    assert estimate['total'] <= 1
    assert node_a5(state) == 'No'
    assert check_structural_integrity(state) == []


def test_arverni_six_piece_gate_counts_actual_bonus_and_leader_cap_without_invented_ally():
    state = board(rc.ARVERNI)
    place_piece(state, rc.PICTONES, rc.ARVERNI, rc.LEADER, leader_name=rc.SUCCESSOR)
    # An opposing Legion prevents the Successor from qualifying an Ally.
    place_piece(state, rc.PICTONES, rc.ROMANS, rc.LEGION, 2, from_legions_track=True)
    refresh_all_control(state)
    assert node_v3(state) == 'No'
    aquitani(state, rc.ARVERNI)
    estimate = pure_estimate(state, arverni_estimate)
    assert estimate['allies'] == estimate['citadels'] == 0
    assert estimate['total'] == estimate['warbands'] == 7  # Home3 + Leader Region4.
    assert node_v3(state) == 'Yes'


@pytest.mark.parametrize('scenario', rc.ARIOVISTUS_SCENARIOS)
def test_belgic_three_warband_gate_counts_nervii_bonus_without_ally_or_added_control(scenario):
    state = board(rc.BELGAE, scenario)
    for region in (rc.MORINI, rc.ATREBATES):
        state['markers'].setdefault(region, {})[rc.MARKER_DEVASTATED] = True
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 6)
    refresh_all_control(state)
    assert node_b4(state) == 'No'
    activate_capability(state, 'A70', rc.EVENT_SHADED)
    estimate = pure_estimate(state, lambda st, _: estimate_scoped_rally(st, rc.BELGAE, node_b_rally))
    assert estimate['allies'] == estimate['citadels'] == 0
    assert estimate['warbands'] == 3 and not estimate['adds_control']
    assert node_b4(state) == 'Yes'


@pytest.mark.parametrize('faction,estimate', [
    (rc.AEDUI, aedui_estimate), (rc.ARVERNI, arverni_estimate),
    (rc.BELGAE, _estimate_rally_would_qualify),
])
def test_no_legal_rally_fallback_terminates_and_preserves_live_rng(faction, estimate):
    state = board(faction)
    state['resources'][faction] = 0
    result = pure_estimate(state, estimate)
    assert not result if faction == rc.BELGAE else result['total'] == 0


def test_aedui_three_piece_gate_counts_physical_auxilia_acting_as_warbands():
    from fs_bot.commands.rally import rally_in_region
    from fs_bot.engine.diviciacus import force_scope
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=19)
    state['non_player_factions'] = set(rc.FACTIONS)
    state['resources'][rc.AEDUI] = 3
    place_piece(state, rc.MANDUBII, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    place_piece(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND)
    place_piece(state, rc.SUGAMBRI, rc.AEDUI, rc.WARBAND,
                get_available(state, rc.AEDUI, rc.WARBAND))
    place_piece(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA)
    for tribe in (rc.TRIBE_MANDUBII, rc.TRIBE_SENONES, rc.TRIBE_LINGONES):
        assert _ally_tribe(state, tribe, rc.AEDUI)
    rally_in_region(state, rc.MANDUBII, rc.AEDUI, 'place_citadel',
                    tribe=rc.TRIBE_MANDUBII, free=True)
    for tribe in (rc.TRIBE_SUGAMBRI, rc.TRIBE_SUEBI_NORTH,
                  rc.TRIBE_MORINI, rc.TRIBE_MENAPII):
        assert _ally_tribe(state, tribe, rc.GERMANS)
    refresh_all_control(state)
    assert get_available(state, rc.AEDUI, rc.WARBAND) == 0
    # §8.6.8 permits this cooperating NP Rally to use Roman Auxilia after
    # exhausting Aedui Warbands. All three are effective Warband placements.
    with force_scope(state, rc.AEDUI, [rc.MANDUBII]):
        estimate = pure_estimate(state, aedui_estimate)
        assert estimate['allies'] == estimate['citadels'] == 0
        assert estimate['warbands'] == estimate['total'] == 3
        assert node_a5(state) == 'Yes'
    assert check_structural_integrity(state) == []
