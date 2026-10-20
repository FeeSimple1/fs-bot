"""Card Reference 62/66: relocate the specified mobile forces, never Allies.

These adjacent paths share the immobile-piece corruption exposed by the
Card 32 mixed-seat soak. Expectations come from the cards and §§1.4/5.1.
"""

from copy import deepcopy

import pytest

from fs_bot.board.control import calculate_control
from fs_bot.board.pieces import (
    PieceError, count_pieces, count_pieces_by_state, get_leader_in_region,
    place_piece,
)
from fs_bot.cards.card_effects import execute_event
from fs_bot.rules_consts import (
    AEDUI, AEDUI_REGION, ALLY, ALL_SCENARIOS, ARIOVISTUS_SCENARIOS, ARVERNI,
    ARVERNI_REGION, AUXILIA, BASE_SCENARIOS, BELGAE, BRITANNIA, CAESAR,
    CITADEL, FACTION_CONTROL, GERMANS, HIDDEN, LEADER, LEGION,
    MARKER_DISPERSED, NO_CONTROL, PICTONES, REVEALED, ROMANS,
    SCENARIO_PAX_GALLICA, SCOUTED, SEQUANI, TRIBE_AEDUI, TRIBE_ARVERNI,
    TRIBE_PICTONES, TRIBE_SEQUANI, VERCINGETORIX, WARBAND,
)
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity


def _state(faction=ARVERNI, scenario=SCENARIO_PAX_GALLICA):
    state = build_initial_state(scenario, seed=62)
    state["executing_faction"] = faction
    return state


def _move(piece_type=WARBAND, **overrides):
    return {"from_region": ARVERNI_REGION, "to_region": PICTONES,
            "piece_type": piece_type, "count": 1, **overrides}


def _assert_unchanged(state, before):
    assert state["spaces"] == before["spaces"]
    assert state["tribes"] == before["tribes"]
    assert state["available"] == before["available"]
    assert state.get("event_modifiers") == before.get("event_modifiers")
    assert state["rng"].getstate() == before["rng"].getstate()
    assert check_structural_integrity(state) == []


@pytest.mark.parametrize("card", [62, 66])
@pytest.mark.parametrize("piece_type", [ALLY, CITADEL])
def test_relocation_cannot_separate_ally_or_citadel_from_its_tribe(card, piece_type):
    """Cards 62/66 enumerate mobile forces; tribe backing pieces stay put."""
    state = _state()
    place_piece(state, ARVERNI_REGION, ARVERNI, piece_type)
    state["tribes"][TRIBE_ARVERNI]["allied_faction"] = ARVERNI
    place_piece(state, ARVERNI_REGION, ARVERNI, WARBAND)
    state["event_params"] = {"target_region": PICTONES,
                             "moves": [_move(), _move(piece_type)]}
    before = deepcopy(state)

    with pytest.raises(ValueError):
        execute_event(state, card, shaded=card == 66)

    _assert_unchanged(state, before)


@pytest.mark.parametrize("scenario", ALL_SCENARIOS)
@pytest.mark.parametrize("piece_state", [HIDDEN, REVEALED, SCOUTED])
def test_war_fleet_preserves_moved_warband_state(scenario, piece_state):
    """Card 62 relocates, without the Hidden instruction found on Card 32."""
    state = _state(AEDUI, scenario)
    place_piece(state, ARVERNI_REGION, AEDUI, WARBAND, piece_state=piece_state)
    state["event_params"] = {"moves": [_move(piece_state=piece_state)]}
    before_available = deepcopy(state["available"])

    execute_event(state, 62)

    assert count_pieces(state, ARVERNI_REGION, AEDUI, WARBAND) == 0
    assert count_pieces_by_state(state, PICTONES, AEDUI, WARBAND, piece_state) == 1
    assert state["available"] == before_available
    assert state["event_modifiers"]["card_62_war_fleet"]
    assert check_structural_integrity(state) == []


def test_war_fleet_moves_roman_auxilia_legion_and_actual_leader():
    state = _state(ROMANS)
    place_piece(state, ARVERNI_REGION, ROMANS, AUXILIA, piece_state=REVEALED)
    place_piece(state, ARVERNI_REGION, ROMANS, LEGION, from_legions_track=True)
    place_piece(state, ARVERNI_REGION, ROMANS, LEADER, leader_name=CAESAR)
    state["event_params"] = {"moves": [
        _move(AUXILIA, piece_state=REVEALED), _move(LEGION), _move(LEADER)]}

    execute_event(state, 62)

    assert count_pieces_by_state(state, PICTONES, ROMANS, AUXILIA, REVEALED) == 1
    assert count_pieces(state, PICTONES, ROMANS, LEGION) == 1
    assert get_leader_in_region(state, PICTONES, ROMANS) == CAESAR
    assert check_structural_integrity(state) == []


@pytest.mark.parametrize("scenario", ALL_SCENARIOS)
def test_war_fleet_britannia_destination_respects_scenario(scenario):
    """A1.3.4 closes Britannia only in the Ariovistus ruleset."""
    state = _state(AEDUI, scenario)
    place_piece(state, ARVERNI_REGION, AEDUI, WARBAND)
    state["event_params"] = {"moves": [_move(to_region=BRITANNIA)]}
    before = deepcopy(state)

    if scenario in ARIOVISTUS_SCENARIOS:
        with pytest.raises(ValueError):
            execute_event(state, 62)
        _assert_unchanged(state, before)
    else:
        execute_event(state, 62)
        assert count_pieces(state, BRITANNIA, AEDUI, WARBAND) == 1


@pytest.mark.parametrize("card", [62, 66])
@pytest.mark.parametrize("count", [-1, 1.5, True])
def test_relocation_rejects_invalid_counts_before_moving(card, count):
    state = _state()
    place_piece(state, ARVERNI_REGION, ARVERNI, WARBAND, count=2)
    state["event_params"] = {"target_region": PICTONES,
                             "moves": [_move(), _move(count=count)]}
    before = deepcopy(state)

    with pytest.raises(ValueError):
        execute_event(state, card, shaded=card == 66)

    _assert_unchanged(state, before)


@pytest.mark.parametrize("card", [62, 66])
def test_zero_movement_preserves_board_and_allows_remaining_event(card):
    """'Any'/'as desired' permits moving no forces before the next effect."""
    state = _state()
    place_piece(state, ARVERNI_REGION, ARVERNI, WARBAND)
    state["event_params"] = {"target_region": PICTONES,
                             "moves": [_move(count=0)],
                             "ally_tribe": TRIBE_PICTONES}

    execute_event(state, card, shaded=card == 66)

    assert count_pieces(state, ARVERNI_REGION, ARVERNI, WARBAND) == 1
    assert count_pieces(state, PICTONES, ARVERNI, WARBAND) == 0
    if card == 62:
        assert state["event_modifiers"]["card_62_war_fleet"]
    else:
        assert count_pieces(state, PICTONES, ARVERNI, ALLY) == 1
    assert check_structural_integrity(state) == []


@pytest.mark.parametrize("card", [62, 66])
def test_relocation_cannot_move_another_factions_warbands(card):
    state = _state()
    place_piece(state, ARVERNI_REGION, AEDUI, WARBAND)
    state["event_params"] = {"target_region": PICTONES,
                             "moves": [_move(faction=AEDUI)]}
    before = deepcopy(state)

    with pytest.raises(PieceError):
        execute_event(state, card, shaded=card == 66)

    _assert_unchanged(state, before)


@pytest.mark.parametrize("card", [62, 66])
def test_unavailable_later_move_does_not_leave_partial_relocation(card):
    state = _state()
    place_piece(state, ARVERNI_REGION, ARVERNI, WARBAND)
    state["event_params"] = {"target_region": PICTONES,
                             "moves": [_move(), _move()]}
    before = deepcopy(state)

    with pytest.raises(PieceError):
        execute_event(state, card, shaded=card == 66)

    _assert_unchanged(state, before)


@pytest.mark.parametrize("scenario", BASE_SCENARIOS)
def test_migration_roman_executor_selects_gallic_beneficiary(scenario):
    """Card 66/§5.1: one Gallic Faction migrates from multiple origins."""
    state = _state(ROMANS, scenario)
    place_piece(state, ARVERNI_REGION, ARVERNI, WARBAND, piece_state=SCOUTED)
    place_piece(state, SEQUANI, ARVERNI, WARBAND, piece_state=REVEALED)
    place_piece(state, ARVERNI_REGION, ARVERNI, LEADER, leader_name=VERCINGETORIX)
    state["event_params"] = {
        "faction": ARVERNI, "target_region": PICTONES,
        "ally_tribe": TRIBE_PICTONES,
        "moves": [_move(piece_state=SCOUTED),
                  _move(from_region=SEQUANI, piece_state=REVEALED),
                  _move(LEADER)],
    }
    assert calculate_control(state, PICTONES) == NO_CONTROL

    execute_event(state, 66, shaded=True)

    # The first arrival gains Control, but later arrivals remain legal.
    assert count_pieces_by_state(state, PICTONES, ARVERNI, WARBAND, SCOUTED) == 1
    assert count_pieces_by_state(state, PICTONES, ARVERNI, WARBAND, REVEALED) == 1
    assert get_leader_in_region(state, PICTONES, ARVERNI) == VERCINGETORIX
    assert state["tribes"][TRIBE_PICTONES]["allied_faction"] == ARVERNI
    assert count_pieces(state, PICTONES, ARVERNI, ALLY) == 1
    assert calculate_control(state, PICTONES) == FACTION_CONTROL[ARVERNI]
    assert check_structural_integrity(state) == []


@pytest.mark.parametrize("faction", [ROMANS, GERMANS])
def test_migration_shaded_requires_gallic_beneficiary(faction):
    state = _state(faction)
    state["event_params"] = {"target_region": PICTONES,
                             "ally_tribe": TRIBE_PICTONES}
    before = deepcopy(state)

    with pytest.raises(ValueError):
        execute_event(state, 66, shaded=True)

    _assert_unchanged(state, before)


@pytest.mark.parametrize("invalid_choice", ["controlled", "split", "remote_ally"])
def test_migration_requires_one_initially_uncontrolled_destination(invalid_choice):
    state = _state()
    place_piece(state, ARVERNI_REGION, ARVERNI, WARBAND, count=2)
    state["event_params"] = {"target_region": PICTONES,
                             "moves": [_move()], "ally_tribe": TRIBE_PICTONES}
    if invalid_choice == "controlled":
        place_piece(state, PICTONES, BELGAE, WARBAND)
    elif invalid_choice == "split":
        state["event_params"]["moves"].append(_move(to_region=SEQUANI))
    else:
        state["event_params"]["ally_tribe"] = TRIBE_SEQUANI
    before = deepcopy(state)

    with pytest.raises(ValueError):
        execute_event(state, 66, shaded=True)

    _assert_unchanged(state, before)


def test_migration_keeps_legal_movement_when_ally_cannot_be_placed():
    """Card 66 tip/§5.1.3: a Dispersed tribe cannot receive the Ally."""
    state = _state()
    place_piece(state, ARVERNI_REGION, ARVERNI, WARBAND)
    state["tribes"][TRIBE_PICTONES]["status"] = MARKER_DISPERSED
    state["event_params"] = {"target_region": PICTONES,
                             "moves": [_move()], "ally_tribe": TRIBE_PICTONES}

    execute_event(state, 66, shaded=True)

    assert count_pieces(state, PICTONES, ARVERNI, WARBAND) == 1
    assert count_pieces(state, PICTONES, ARVERNI, ALLY) == 0
    assert state["tribes"][TRIBE_PICTONES]["status"] == MARKER_DISPERSED
    assert check_structural_integrity(state) == []


def test_migration_cannot_place_ally_in_another_factions_exclusive_tribe():
    """§§1.4.2/5.1.1: Aedui's circle remains Aedui-only during Migration."""
    state = _state()
    place_piece(state, ARVERNI_REGION, ARVERNI, WARBAND)
    state["event_params"] = {
        "target_region": AEDUI_REGION, "ally_tribe": TRIBE_AEDUI,
        "moves": [_move(to_region=AEDUI_REGION)],
    }

    execute_event(state, 66, shaded=True)

    assert count_pieces(state, AEDUI_REGION, ARVERNI, WARBAND) == 1
    assert count_pieces(state, AEDUI_REGION, ARVERNI, ALLY) == 0
    assert state["tribes"][TRIBE_AEDUI]["allied_faction"] is None
    assert check_structural_integrity(state) == []
