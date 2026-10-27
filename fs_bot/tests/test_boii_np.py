"""Source-derived Boii non-player placement and replacement priorities."""

from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, get_available
from fs_bot.cards.boii_np import derive_boii
from fs_bot.cards.card_effects import execute_event, _ally_tribe
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity


def _state(seed=3):
    return build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=seed)


@pytest.mark.parametrize("faction,piece_type", [(rc.ROMANS, rc.AUXILIA),
                                               (rc.AEDUI, rc.WARBAND)])
def test_boii_np_places_own_two_allies_and_troops_in_best_region(faction, piece_type):
    state = _state()
    place_piece(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND, 3)
    # Only Mandubii can receive two Allies. Other Tribes are Dispersed.
    for tribe, info in state["tribes"].items():
        if rc.TRIBE_TO_REGION.get(tribe) != rc.MANDUBII:
            info["status"] = rc.DISPERSED
    plan = derive_boii(state, faction, False)
    allies = [entry for entry in plan["placements"] if entry["piece_type"] == rc.ALLY]
    assert plan["place_faction"] == faction
    assert len(allies) == 2
    assert all(entry["region"] == rc.MANDUBII for entry in plan["placements"])
    assert allies[0]["tribe"] == rc.TRIBE_MANDUBII
    before = count_pieces(state, rc.MANDUBII, faction, piece_type)
    state["event_params"] = plan
    execute_event(state, 37)
    assert count_pieces(state, rc.MANDUBII, faction, rc.ALLY) == 2
    assert count_pieces(state, rc.MANDUBII, faction, piece_type) == before + 2
    assert check_structural_integrity(state) == []


def test_boii_np_shaded_replaces_most_allies_with_city_first():
    state = _state()
    place_piece(state, rc.MANDUBII, rc.ARVERNI, rc.WARBAND, 4)
    for tribe in (rc.TRIBE_MANDUBII, rc.TRIBE_SENONES, rc.TRIBE_LINGONES):
        assert _ally_tribe(state, tribe, rc.AEDUI)
    plan = derive_boii(state, rc.ARVERNI, True)
    assert len(plan["replacements"]) == 2
    assert plan["replacements"][0]["tribe"] == rc.TRIBE_MANDUBII
    state["event_params"] = plan
    execute_event(state, 37, shaded=True)
    assert count_pieces(state, rc.MANDUBII, rc.ARVERNI, rc.ALLY) == 2
    assert count_pieces(state, rc.MANDUBII, rc.AEDUI, rc.ALLY) == 1
    assert check_structural_integrity(state) == []


@pytest.mark.parametrize("faction,shaded", [(rc.BELGAE, False), (rc.BELGAE, True),
    (rc.ARVERNI, False), (rc.ROMANS, True), (rc.AEDUI, True), (rc.GERMANS, False)])
def test_boii_np_never_gives_optional_benefits_to_another_faction(faction, shaded):
    assert derive_boii(_state(), faction, shaded) is None


def test_boii_np_uses_available_piece_count_and_seeded_ties():
    state = _state()
    place_piece(state, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND, 1)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA,
                get_available(state, rc.ROMANS, rc.AUXILIA) - 1)
    clone = deepcopy(state)
    plan = derive_boii(state, rc.ROMANS, False)
    assert plan == derive_boii(clone, rc.ROMANS, False)
    assert state["rng"].getstate() == clone["rng"].getstate()
    assert sum(p["count"] for p in plan["placements"]
               if p["piece_type"] == rc.AUXILIA) == 1
    assert all(p.get("tribe") != rc.TRIBE_AEDUI for p in plan["placements"])


def test_boii_np_declines_outside_eligible_control_without_using_rng():
    from fs_bot.cards.event_conditions import np_event_available
    state = _state()
    before = state['rng'].getstate()
    assert np_event_available(state, 37, rc.ROMANS, False) is False
    assert np_event_available(state, 37, rc.ARVERNI, True) is False
    place_piece(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND)
    assert np_event_available(state, 37, rc.ROMANS, False) is True
    assert state['rng'].getstate() == before


def test_boii_np_declines_when_no_own_piece_can_be_placed():
    from fs_bot.cards.event_conditions import np_event_available
    state = _state()
    place_piece(state, rc.MANDUBII, rc.AEDUI, rc.WARBAND)
    place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA,
                get_available(state, rc.ROMANS, rc.AUXILIA))
    for info in state['tribes'].values():
        info['status'] = rc.DISPERSED
    assert np_event_available(state, 37, rc.ROMANS, False) is False
