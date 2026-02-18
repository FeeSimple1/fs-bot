"""
test_card_effects.py — Tests for card event effect implementations.

Each test verifies against the Card Reference text, not against assumed behavior.
Test names include the card number for traceability.
"""

import pytest

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    # Scenarios
    SCENARIO_PAX_GALLICA, SCENARIO_ARIOVISTUS,
    # Senate
    UPROAR, INTRIGUE, ADULATION,
    SENATE_UP, SENATE_DOWN,
    # Pieces
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL,
    # Piece states
    HIDDEN, REVEALED,
    # Leaders
    CAESAR, VERCINGETORIX, AMBIORIX, SUCCESSOR,
    # Regions
    PROVINCIA, SEQUANI, ARVERNI_REGION, AEDUI_REGION, MANDUBII,
    ATREBATES, NERVII, MORINI, TREVERI, CARNUTES, BITURIGES,
    SUGAMBRI, UBII,
    # Legions track
    LEGIONS_ROW_BOTTOM, LEGIONS_ROW_MIDDLE, LEGIONS_ROW_TOP,
    # Resources
    MAX_RESOURCES,
    # Control
    ROMAN_CONTROL, NO_CONTROL, FACTION_CONTROL,
    # Eligibility
    ELIGIBLE, INELIGIBLE,
)
from fs_bot.state.state_schema import build_initial_state
from fs_bot.cards.card_effects import execute_event
from fs_bot.board.pieces import (
    place_piece, remove_piece, count_pieces, get_leader_in_region,
)
from fs_bot.board.control import refresh_all_control, is_controlled_by


def _setup_base_state(seed=42):
    """Build a minimal base game state for testing card effects."""
    state = build_initial_state(SCENARIO_PAX_GALLICA, seed=seed)
    # Set Senate to a known position
    state["senate"]["position"] = INTRIGUE
    state["senate"]["firm"] = False
    # Set some resources
    state["resources"][ROMANS] = 20
    state["resources"][ARVERNI] = 15
    state["resources"][AEDUI] = 10
    state["resources"][BELGAE] = 10
    return state


def _setup_ariovistus_state(seed=42):
    """Build a minimal Ariovistus state for testing card effects."""
    state = build_initial_state(SCENARIO_ARIOVISTUS, seed=seed)
    state["senate"]["position"] = INTRIGUE
    state["senate"]["firm"] = False
    state["resources"][ROMANS] = 20
    state["resources"][AEDUI] = 10
    state["resources"][BELGAE] = 10
    state["resources"][GERMANS] = 10
    return state


# ===================================================================
# Card 1: Cicero — Senate shift
# Card Reference: "Shift the Senate 1 box in either direction
#   (or flip to Firm if already at top or bottom)."
# Tips: Senate shifts regardless of Fallen Legions. If already Firm,
#   flip back to normal side.
# ===================================================================

class TestCard1Cicero:
    """Tests for Card 1: Cicero (Senate shift)."""

    def test_card_1_shift_senate_down_from_intrigue(self):
        """Unshaded: shift down from Intrigue -> Adulation."""
        state = _setup_base_state()
        state["senate"]["position"] = INTRIGUE
        state["event_params"] = {"senate_direction": SENATE_DOWN}
        execute_event(state, 1, shaded=False)
        assert state["senate"]["position"] == ADULATION
        assert state["senate"]["firm"] is False

    def test_card_1_shift_senate_up_from_intrigue(self):
        """Shaded: shift up from Intrigue -> Uproar."""
        state = _setup_base_state()
        state["senate"]["position"] = INTRIGUE
        state["event_params"] = {"senate_direction": SENATE_UP}
        execute_event(state, 1, shaded=True)
        assert state["senate"]["position"] == UPROAR
        assert state["senate"]["firm"] is False

    def test_card_1_shift_down_at_adulation_flips_to_firm(self):
        """At Adulation + not Firm, shift down -> flip to Firm."""
        state = _setup_base_state()
        state["senate"]["position"] = ADULATION
        state["senate"]["firm"] = False
        state["event_params"] = {"senate_direction": SENATE_DOWN}
        execute_event(state, 1, shaded=False)
        assert state["senate"]["position"] == ADULATION
        assert state["senate"]["firm"] is True

    def test_card_1_shift_up_at_uproar_flips_to_firm(self):
        """At Uproar + not Firm, shift up -> flip to Firm."""
        state = _setup_base_state()
        state["senate"]["position"] = UPROAR
        state["senate"]["firm"] = False
        state["event_params"] = {"senate_direction": SENATE_UP}
        execute_event(state, 1, shaded=False)
        assert state["senate"]["position"] == UPROAR
        assert state["senate"]["firm"] is True

    def test_card_1_already_firm_flips_back_to_normal(self):
        """Tips: If already Firm, flip marker back to normal side (§6.5.1)."""
        state = _setup_base_state()
        state["senate"]["position"] = ADULATION
        state["senate"]["firm"] = True
        state["event_params"] = {"senate_direction": SENATE_DOWN}
        execute_event(state, 1, shaded=False)
        # Already at Firm Adulation — shift down does nothing further
        # (already at extreme + Firm)
        assert state["senate"]["position"] == ADULATION
        assert state["senate"]["firm"] is True

    def test_card_1_firm_intrigue_shift_up_flips_to_normal(self):
        """Firm at Intrigue, shift up -> flip to normal (no position change)."""
        state = _setup_base_state()
        state["senate"]["position"] = INTRIGUE
        state["senate"]["firm"] = True
        state["event_params"] = {"senate_direction": SENATE_UP}
        execute_event(state, 1, shaded=False)
        assert state["senate"]["position"] == INTRIGUE
        assert state["senate"]["firm"] is False

    def test_card_1_shift_down_from_uproar(self):
        """From Uproar, shift down -> Intrigue."""
        state = _setup_base_state()
        state["senate"]["position"] = UPROAR
        state["senate"]["firm"] = False
        state["event_params"] = {"senate_direction": SENATE_DOWN}
        execute_event(state, 1, shaded=False)
        assert state["senate"]["position"] == INTRIGUE
        assert state["senate"]["firm"] is False

    def test_card_1_requires_direction_param(self):
        """Must provide event_params with senate_direction."""
        state = _setup_base_state()
        with pytest.raises(ValueError, match="senate_direction"):
            execute_event(state, 1, shaded=False)

    def test_card_1_shaded_same_effect(self):
        """Both unshaded and shaded have the same effect (Card Reference
        only lists one effect text for Card 1)."""
        state1 = _setup_base_state()
        state1["event_params"] = {"senate_direction": SENATE_DOWN}
        execute_event(state1, 1, shaded=False)

        state2 = _setup_base_state()
        state2["event_params"] = {"senate_direction": SENATE_DOWN}
        execute_event(state2, 1, shaded=True)

        assert state1["senate"] == state2["senate"]


# ===================================================================
# Card 2: Legiones XIIII et XV
# Unshaded: Romans shift Senate up to place 2 Legions from track/Fallen
#   into Provincia. Cannot occur if already at Firm Uproar.
# Shaded: Free Battle against Romans; first Loss removes Legion auto.
# ===================================================================

class TestCard2LegionesXIIIIetXV:
    """Tests for Card 2: Legiones XIIII et XV."""

    def test_card_2_unshaded_shift_up_and_place_legions_from_track(self):
        """Unshaded: shift Senate up, place 2 Legions from track to Provincia."""
        state = _setup_base_state()
        state["senate"]["position"] = INTRIGUE
        state["event_params"] = {"legions_from_track": 2, "legions_from_fallen": 0}
        execute_event(state, 2, shaded=False)
        assert state["senate"]["position"] == UPROAR
        assert count_pieces(state, PROVINCIA, ROMANS, LEGION) == 2

    def test_card_2_unshaded_legions_from_fallen(self):
        """Tips: Legions can come from Fallen not just track."""
        state = _setup_base_state()
        state["senate"]["position"] = ADULATION
        state["fallen_legions"] = 2
        # Clear legions track to force from_fallen
        for row in [LEGIONS_ROW_BOTTOM, LEGIONS_ROW_MIDDLE, LEGIONS_ROW_TOP]:
            state["legions_track"][row] = 0
        state["event_params"] = {"legions_from_track": 0, "legions_from_fallen": 2}
        execute_event(state, 2, shaded=False)
        # Senate shifted up from Adulation to Intrigue
        assert state["senate"]["position"] == INTRIGUE
        assert count_pieces(state, PROVINCIA, ROMANS, LEGION) == 2
        assert state["fallen_legions"] == 0

    def test_card_2_unshaded_mixed_track_and_fallen(self):
        """Legions can come from both track and Fallen."""
        state = _setup_base_state()
        state["senate"]["position"] = INTRIGUE
        state["fallen_legions"] = 1
        state["event_params"] = {"legions_from_track": 1, "legions_from_fallen": 1}
        execute_event(state, 2, shaded=False)
        assert state["senate"]["position"] == UPROAR
        assert count_pieces(state, PROVINCIA, ROMANS, LEGION) == 2

    def test_card_2_unshaded_cannot_shift_at_firm_uproar(self):
        """Tips: Cannot occur if already at Firm Uproar."""
        state = _setup_base_state()
        state["senate"]["position"] = UPROAR
        state["senate"]["firm"] = True
        state["event_params"] = {"legions_from_track": 2, "legions_from_fallen": 0}
        legions_before = count_pieces(state, PROVINCIA, ROMANS, LEGION)
        execute_event(state, 2, shaded=False)
        # Nothing happens — still at Firm Uproar, no Legions placed
        assert state["senate"]["position"] == UPROAR
        assert state["senate"]["firm"] is True
        assert count_pieces(state, PROVINCIA, ROMANS, LEGION) == legions_before

    def test_card_2_shaded_sets_battle_modifier(self):
        """Shaded: sets up battle modifier for auto Legion loss."""
        state = _setup_base_state()
        state["event_params"] = {"battle_region": ARVERNI_REGION}
        execute_event(state, 2, shaded=True)
        assert state["event_modifiers"]["card_2_auto_legion_loss"] is True
        assert state["event_modifiers"]["card_2_battle_region"] == ARVERNI_REGION


# ===================================================================
# Card 3: Pompey
# Unshaded: If Adulation, place 1 Legion in Provincia. If not, shift
#   Senate 1 box down.
# Shaded: If Legions track has 4 or fewer, Romans remove 2 Legions
#   to the Legions track.
# ===================================================================

class TestCard3Pompey:
    """Tests for Card 3: Pompey."""

    def test_card_3_unshaded_adulation_places_legion(self):
        """If Adulation, place 1 Legion in Provincia."""
        state = _setup_base_state()
        state["senate"]["position"] = ADULATION
        legions_before = count_pieces(state, PROVINCIA, ROMANS, LEGION)
        execute_event(state, 3, shaded=False)
        assert count_pieces(state, PROVINCIA, ROMANS, LEGION) == legions_before + 1
        # Senate should NOT shift (already at Adulation, we place instead)
        assert state["senate"]["position"] == ADULATION

    def test_card_3_unshaded_not_adulation_shifts_down(self):
        """If not Adulation, shift Senate 1 box down."""
        state = _setup_base_state()
        state["senate"]["position"] = INTRIGUE
        execute_event(state, 3, shaded=False)
        assert state["senate"]["position"] == ADULATION

    def test_card_3_unshaded_uproar_shifts_to_intrigue(self):
        """From Uproar, shift down to Intrigue."""
        state = _setup_base_state()
        state["senate"]["position"] = UPROAR
        execute_event(state, 3, shaded=False)
        assert state["senate"]["position"] == INTRIGUE

    def test_card_3_shaded_removes_2_legions_to_track(self):
        """If track has 4 or fewer, remove 2 Legions to track."""
        state = _setup_base_state()
        # Put Legions on map
        place_piece(state, PROVINCIA, ROMANS, LEGION, count=3,
                    from_legions_track=True)
        # Ensure track has 4 or fewer
        track_before = sum(state["legions_track"][r] for r in
                           [LEGIONS_ROW_BOTTOM, LEGIONS_ROW_MIDDLE,
                            LEGIONS_ROW_TOP])
        assert track_before <= 12  # Some were placed on map
        # Set track count to <= 4 by moving more to map
        while sum(state["legions_track"][r] for r in
                  [LEGIONS_ROW_BOTTOM, LEGIONS_ROW_MIDDLE,
                   LEGIONS_ROW_TOP]) > 4:
            place_piece(state, SEQUANI, ROMANS, LEGION,
                        from_legions_track=True)
        state["event_params"] = {"legion_removal_regions": [PROVINCIA]}
        provincia_legions_before = count_pieces(
            state, PROVINCIA, ROMANS, LEGION)
        execute_event(state, 3, shaded=True)
        # 2 Legions removed from Provincia to track
        assert count_pieces(state, PROVINCIA, ROMANS, LEGION) == \
            provincia_legions_before - 2

    def test_card_3_shaded_track_more_than_4_no_effect(self):
        """If track has more than 4, shaded has no effect."""
        state = _setup_base_state()
        # Default state has all 12 Legions on track — well above 4
        # Place 2 on map to test, but track still has 10
        place_piece(state, PROVINCIA, ROMANS, LEGION, count=2,
                    from_legions_track=True)
        track_count = sum(state["legions_track"][r] for r in
                          [LEGIONS_ROW_BOTTOM, LEGIONS_ROW_MIDDLE,
                           LEGIONS_ROW_TOP])
        assert track_count > 4
        legions_before = count_pieces(state, PROVINCIA, ROMANS, LEGION)
        execute_event(state, 3, shaded=True)
        # No Legions removed
        assert count_pieces(state, PROVINCIA, ROMANS, LEGION) == legions_before


# ===================================================================
# Card 7: Alaudae
# Unshaded: Place 1 Legion (from track, not Fallen) and 1 Auxilia
#   in a Roman Controlled Region.
# Shaded: If Legions track has 7 or fewer, remove 1 Legion to track
#   and 1 Auxilia to Available.
# ===================================================================

class TestCard7Alaudae:
    """Tests for Card 7: Alaudae."""

    def test_card_7_unshaded_places_legion_and_auxilia(self):
        """Place 1 Legion and 1 Auxilia in Roman Controlled Region."""
        state = _setup_base_state()
        # Set up Roman control in Provincia (permanent Fort there)
        place_piece(state, PROVINCIA, ROMANS, AUXILIA, count=3)
        refresh_all_control(state)
        state["event_params"] = {"target_region": PROVINCIA}
        legions_before = count_pieces(state, PROVINCIA, ROMANS, LEGION)
        auxilia_before = count_pieces(state, PROVINCIA, ROMANS, AUXILIA)
        execute_event(state, 7, shaded=False)
        assert count_pieces(state, PROVINCIA, ROMANS, LEGION) == \
            legions_before + 1
        assert count_pieces(state, PROVINCIA, ROMANS, AUXILIA) == \
            auxilia_before + 1

    def test_card_7_unshaded_legion_from_track_not_fallen(self):
        """Tips: Legion could not be placed from Fallen."""
        state = _setup_base_state()
        place_piece(state, PROVINCIA, ROMANS, AUXILIA, count=3)
        refresh_all_control(state)
        # Move all track Legions to Fallen
        track_total = sum(state["legions_track"][r] for r in
                          [LEGIONS_ROW_BOTTOM, LEGIONS_ROW_MIDDLE,
                           LEGIONS_ROW_TOP])
        for row in [LEGIONS_ROW_BOTTOM, LEGIONS_ROW_MIDDLE, LEGIONS_ROW_TOP]:
            state["legions_track"][row] = 0
        state["fallen_legions"] = track_total
        state["event_params"] = {"target_region": PROVINCIA}
        # No Legions on track, so no Legion placed (even though Fallen exist)
        execute_event(state, 7, shaded=False)
        assert count_pieces(state, PROVINCIA, ROMANS, LEGION) == 0

    def test_card_7_shaded_removes_legion_to_track(self):
        """If track <= 7, remove 1 Legion to track, 1 Auxilia to Available."""
        state = _setup_base_state()
        # Place some pieces on map
        place_piece(state, PROVINCIA, ROMANS, LEGION, count=2,
                    from_legions_track=True)
        place_piece(state, PROVINCIA, ROMANS, AUXILIA, count=2)
        # Move most of track to map so track <= 7
        while sum(state["legions_track"][r] for r in
                  [LEGIONS_ROW_BOTTOM, LEGIONS_ROW_MIDDLE,
                   LEGIONS_ROW_TOP]) > 7:
            place_piece(state, SEQUANI, ROMANS, LEGION,
                        from_legions_track=True)
        state["event_params"] = {
            "legion_removal_region": PROVINCIA,
            "auxilia_removal_region": PROVINCIA,
        }
        legions_before = count_pieces(state, PROVINCIA, ROMANS, LEGION)
        auxilia_before = count_pieces(state, PROVINCIA, ROMANS, AUXILIA)
        execute_event(state, 7, shaded=True)
        assert count_pieces(state, PROVINCIA, ROMANS, LEGION) == \
            legions_before - 1
        assert count_pieces(state, PROVINCIA, ROMANS, AUXILIA) == \
            auxilia_before - 1

    def test_card_7_shaded_track_above_7_no_effect(self):
        """If track > 7, shaded has no effect."""
        state = _setup_base_state()
        place_piece(state, PROVINCIA, ROMANS, LEGION, count=2,
                    from_legions_track=True)
        place_piece(state, PROVINCIA, ROMANS, AUXILIA, count=2)
        track_count = sum(state["legions_track"][r] for r in
                          [LEGIONS_ROW_BOTTOM, LEGIONS_ROW_MIDDLE,
                           LEGIONS_ROW_TOP])
        assert track_count > 7  # Still 10 on track
        legions_before = count_pieces(state, PROVINCIA, ROMANS, LEGION)
        execute_event(state, 7, shaded=True)
        assert count_pieces(state, PROVINCIA, ROMANS, LEGION) == legions_before


# ===================================================================
# Card 14: Clodius Pulcher
# Unshaded: Shift Senate 1 box down (toward Adulation).
# Shaded: Roman Leader to Provincia. Romans Ineligible through next
#   card. Executing Faction Eligible.
# ===================================================================

class TestCard14ClodiusPulcher:
    """Tests for Card 14: Clodius Pulcher."""

    def test_card_14_unshaded_shift_down(self):
        """Unshaded: shift Senate 1 box down."""
        state = _setup_base_state()
        state["senate"]["position"] = INTRIGUE
        execute_event(state, 14, shaded=False)
        assert state["senate"]["position"] == ADULATION

    def test_card_14_unshaded_at_adulation_flips_firm(self):
        """At Adulation, shift down flips to Firm."""
        state = _setup_base_state()
        state["senate"]["position"] = ADULATION
        execute_event(state, 14, shaded=False)
        assert state["senate"]["position"] == ADULATION
        assert state["senate"]["firm"] is True

    def test_card_14_shaded_moves_leader_to_provincia(self):
        """Shaded: Roman Leader moves to Provincia."""
        state = _setup_base_state()
        place_piece(state, SEQUANI, ROMANS, LEADER, leader_name=CAESAR)
        state["executing_faction"] = ARVERNI
        execute_event(state, 14, shaded=True)
        assert get_leader_in_region(state, PROVINCIA, ROMANS) == CAESAR
        assert get_leader_in_region(state, SEQUANI, ROMANS) is None

    def test_card_14_shaded_leader_already_in_provincia(self):
        """If leader already in Provincia, no movement needed."""
        state = _setup_base_state()
        place_piece(state, PROVINCIA, ROMANS, LEADER, leader_name=CAESAR)
        state["executing_faction"] = ARVERNI
        execute_event(state, 14, shaded=True)
        assert get_leader_in_region(state, PROVINCIA, ROMANS) == CAESAR

    def test_card_14_shaded_no_leader_on_map(self):
        """If no Roman leader on map, no movement occurs."""
        state = _setup_base_state()
        state["executing_faction"] = ARVERNI
        execute_event(state, 14, shaded=True)
        # No error raised, Romans still Ineligible
        assert state["eligibility"][ROMANS] == INELIGIBLE

    def test_card_14_shaded_romans_ineligible(self):
        """Shaded: Romans Ineligible through next card."""
        state = _setup_base_state()
        state["executing_faction"] = ARVERNI
        execute_event(state, 14, shaded=True)
        assert state["eligibility"][ROMANS] == INELIGIBLE

    def test_card_14_shaded_executing_faction_eligible(self):
        """Shaded: Executing Faction stays Eligible."""
        state = _setup_base_state()
        state["executing_faction"] = ARVERNI
        state["eligibility"][ARVERNI] = INELIGIBLE
        execute_event(state, 14, shaded=True)
        assert state["eligibility"][ARVERNI] == ELIGIBLE
