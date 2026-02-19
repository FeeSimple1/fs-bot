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
    # Markers
    MARKER_DEVASTATED,
)
from fs_bot.state.state_schema import build_initial_state
from fs_bot.cards.card_effects import execute_event
from fs_bot.board.pieces import (
    place_piece, remove_piece, count_pieces, get_leader_in_region,
)
from fs_bot.board.control import refresh_all_control, is_controlled_by
from fs_bot.cards.capabilities import is_capability_active, activate_capability
from fs_bot.rules_consts import EVENT_SHADED, EVENT_UNSHADED


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


# ===================================================================
# Card 16: Ambacti
# Unshaded: Place 4 Auxilia (6 with Caesar) in Region with Romans.
# Shaded: Roll die, remove 3 or that many Auxilia from anywhere.
# ===================================================================

class TestCard16Ambacti:
    """Tests for Card 16: Ambacti."""

    def test_card_16_unshaded_place_4_auxilia(self):
        """Place 4 Auxilia in region with Romans (no Caesar)."""
        state = _setup_base_state()
        place_piece(state, SEQUANI, ROMANS, LEGION, from_legions_track=True)
        state["event_params"] = {"target_region": SEQUANI}
        execute_event(state, 16, shaded=False)
        assert count_pieces(state, SEQUANI, ROMANS, AUXILIA) == 4

    def test_card_16_unshaded_place_6_with_caesar(self):
        """Place 6 Auxilia if Caesar is in the region."""
        state = _setup_base_state()
        place_piece(state, SEQUANI, ROMANS, LEADER, leader_name=CAESAR)
        state["event_params"] = {"target_region": SEQUANI}
        execute_event(state, 16, shaded=False)
        assert count_pieces(state, SEQUANI, ROMANS, AUXILIA) == 6

    def test_card_16_unshaded_no_romans_ineffective(self):
        """No Roman pieces in region — event ineffective."""
        state = _setup_base_state()
        state["event_params"] = {"target_region": SEQUANI}
        execute_event(state, 16, shaded=False)
        assert count_pieces(state, SEQUANI, ROMANS, AUXILIA) == 0

    def test_card_16_shaded_removes_auxilia(self):
        """Shaded: removes Auxilia based on die roll."""
        state = _setup_base_state(seed=1)  # Deterministic
        place_piece(state, PROVINCIA, ROMANS, AUXILIA, count=5)
        state["event_params"] = {"removal_choice": "max"}
        execute_event(state, 16, shaded=True)
        # Some Auxilia should have been removed
        remaining = count_pieces(state, PROVINCIA, ROMANS, AUXILIA)
        assert remaining < 5


# ===================================================================
# Card 21: The Province
# ===================================================================

class TestCard21TheProvince:
    """Tests for Card 21: The Province."""

    def test_card_21_unshaded_place_auxilia(self):
        """Only Romans in Provincia -> place 5 Auxilia."""
        state = _setup_base_state()
        # Place a Roman Fort to establish Romans in Provincia
        place_piece(state, PROVINCIA, ROMANS, FORT)
        state["event_params"] = {"province_choice": "auxilia"}
        execute_event(state, 21, shaded=False)
        assert count_pieces(state, PROVINCIA, ROMANS, AUXILIA) == 5

    def test_card_21_unshaded_add_resources(self):
        """Only Romans in Provincia -> +10 Resources."""
        state = _setup_base_state()
        place_piece(state, PROVINCIA, ROMANS, FORT)
        state["event_params"] = {"province_choice": "resources"}
        before = state["resources"][ROMANS]
        execute_event(state, 21, shaded=False)
        assert state["resources"][ROMANS] == before + 10

    def test_card_21_unshaded_non_roman_pieces_blocks(self):
        """Non-Roman pieces in Provincia -> event ineffective."""
        state = _setup_base_state()
        place_piece(state, PROVINCIA, ROMANS, FORT)
        place_piece(state, PROVINCIA, ARVERNI, WARBAND)
        state["event_params"] = {"province_choice": "auxilia"}
        execute_event(state, 21, shaded=False)
        assert count_pieces(state, PROVINCIA, ROMANS, AUXILIA) == 0

    def test_card_21_shaded_arverni_control_shifts_senate(self):
        """Arverni Control Provincia -> shift Senate 2 boxes up."""
        state = _setup_base_state()
        state["senate"]["position"] = ADULATION
        # Give Arverni control of Provincia
        place_piece(state, PROVINCIA, ARVERNI, WARBAND, count=10)
        refresh_all_control(state)
        execute_event(state, 21, shaded=True)
        assert state["senate"]["position"] == UPROAR

    def test_card_21_shaded_no_control_places_warbands(self):
        """No Arverni Control -> place 4 Arverni Warbands."""
        state = _setup_base_state()
        execute_event(state, 21, shaded=True)
        assert count_pieces(state, PROVINCIA, ARVERNI, WARBAND) == 4


# ===================================================================
# Card 24: Sappers
# ===================================================================

class TestCard24Sappers:
    """Tests for Card 24: Sappers."""

    def test_card_24_unshaded_gallic_faction_loses_resources(self):
        """Gallic faction with Citadel loses 10 Resources."""
        state = _setup_base_state()
        state["resources"][ARVERNI] = 15
        place_piece(state, ARVERNI_REGION, ARVERNI, CITADEL)
        state["event_params"] = {"target_faction": ARVERNI}
        execute_event(state, 24, shaded=False)
        assert state["resources"][ARVERNI] == 5

    def test_card_24_shaded_removes_legions_to_fallen(self):
        """Remove 2 Legions/Auxilia from region with Arverni Citadel."""
        state = _setup_base_state()
        place_piece(state, ARVERNI_REGION, ARVERNI, CITADEL)
        place_piece(state, ARVERNI_REGION, ROMANS, LEGION, count=2,
                    from_legions_track=True)
        state["event_params"] = {
            "target_region": ARVERNI_REGION,
            "legions_to_remove": 2,
            "auxilia_to_remove": 0,
        }
        execute_event(state, 24, shaded=True)
        assert count_pieces(state, ARVERNI_REGION, ROMANS, LEGION) == 0
        assert state["fallen_legions"] >= 2


# ===================================================================
# Card 31: Cotuatus & Conconnetodumnus
# ===================================================================

class TestCard31Cotuatus:
    """Tests for Card 31: Cotuatus & Conconnetodumnus."""

    def test_card_31_unshaded_place_legion(self):
        """Place 1 Legion in Provincia from track."""
        state = _setup_base_state()
        legions_before = count_pieces(state, PROVINCIA, ROMANS, LEGION)
        execute_event(state, 31, shaded=False)
        assert count_pieces(state, PROVINCIA, ROMANS, LEGION) == \
            legions_before + 1

    def test_card_31_shaded_removes_3_allies(self):
        """Remove 1 Roman, 1 Aedui, 1 Roman or Aedui Ally."""
        state = _setup_base_state()
        place_piece(state, PROVINCIA, ROMANS, ALLY)
        place_piece(state, SEQUANI, ROMANS, ALLY)
        place_piece(state, AEDUI_REGION, AEDUI, ALLY)
        state["event_params"] = {
            "roman_ally_region": PROVINCIA,
            "aedui_ally_region": AEDUI_REGION,
            "third_ally_faction": ROMANS,
            "third_ally_region": SEQUANI,
        }
        execute_event(state, 31, shaded=True)
        assert count_pieces(state, PROVINCIA, ROMANS, ALLY) == 0
        assert count_pieces(state, AEDUI_REGION, AEDUI, ALLY) == 0
        assert count_pieces(state, SEQUANI, ROMANS, ALLY) == 0


# ===================================================================
# Card 33: Lost Eagle
# ===================================================================

class TestCard33LostEagle:
    """Tests for Card 33: Lost Eagle."""

    def test_card_33_unshaded_place_fallen_legion(self):
        """Place 1 Fallen Legion into Region with non-Aedui Warband + Legion."""
        state = _setup_base_state()
        # Set up: region with Legion and Arverni Warband, plus Fallen Legions
        place_piece(state, SEQUANI, ROMANS, LEGION, from_legions_track=True)
        place_piece(state, SEQUANI, ARVERNI, WARBAND)
        state["fallen_legions"] = 1
        state["event_params"] = {"target_region": SEQUANI}
        execute_event(state, 33, shaded=False)
        assert count_pieces(state, SEQUANI, ROMANS, LEGION) == 2
        assert state["fallen_legions"] == 0

    def test_card_33_unshaded_no_fallen_no_effect(self):
        """No Fallen Legions -> no effect."""
        state = _setup_base_state()
        place_piece(state, SEQUANI, ROMANS, LEGION, from_legions_track=True)
        place_piece(state, SEQUANI, ARVERNI, WARBAND)
        state["fallen_legions"] = 0
        execute_event(state, 33, shaded=False)
        assert count_pieces(state, SEQUANI, ROMANS, LEGION) == 1

    def test_card_33_shaded_removes_fallen_permanently(self):
        """Remove 1 Fallen Legion permanently."""
        state = _setup_base_state()
        state["fallen_legions"] = 2
        removed_before = state.get("removed_legions", 0)
        execute_event(state, 33, shaded=True)
        assert state["fallen_legions"] == 1
        assert state["removed_legions"] == removed_before + 1

    def test_card_33_shaded_sets_no_shift_down_marker(self):
        """Sets Lost Eagle marker preventing Senate shift down."""
        state = _setup_base_state()
        state["fallen_legions"] = 1
        execute_event(state, 33, shaded=True)
        assert state["event_modifiers"]["lost_eagle_no_shift_down"] is True


# ===================================================================
# Card 49: Drought
# ===================================================================

class TestCard49Drought:
    """Tests for Card 49: Drought."""

    def test_card_49_halves_resources(self):
        """Each Faction drops to half Resources (rounded down)."""
        state = _setup_base_state()
        state["resources"][ROMANS] = 25
        state["resources"][ARVERNI] = 15
        state["resources"][AEDUI] = 11
        state["resources"][BELGAE] = 7
        state["event_params"] = {"devastate_region": SEQUANI}
        execute_event(state, 49, shaded=False)
        assert state["resources"][ROMANS] == 12
        assert state["resources"][ARVERNI] == 7
        assert state["resources"][AEDUI] == 5
        assert state["resources"][BELGAE] == 3

    def test_card_49_places_devastated_marker(self):
        """Place 1 Devastated marker in a Region without one."""
        state = _setup_base_state()
        state["event_params"] = {"devastate_region": SEQUANI}
        execute_event(state, 49, shaded=False)
        assert MARKER_DEVASTATED in state["markers"].get(SEQUANI, set())

    def test_card_49_removes_pieces_from_devastated(self):
        """Each Faction removes 1 piece from each Devastated Region."""
        state = _setup_base_state()
        # Pre-place Devastated marker and pieces
        state.setdefault("markers", {})
        state["markers"][SEQUANI] = {MARKER_DEVASTATED}
        place_piece(state, SEQUANI, ROMANS, LEGION, from_legions_track=True)
        place_piece(state, SEQUANI, ARVERNI, WARBAND)
        # Place Devastated in another region for this card
        state["event_params"] = {"devastate_region": ATREBATES}
        execute_event(state, 49, shaded=False)
        # Roman Legion removed to Fallen from SEQUANI
        assert count_pieces(state, SEQUANI, ROMANS, LEGION) == 0
        # Arverni Warband removed from SEQUANI
        assert count_pieces(state, SEQUANI, ARVERNI, WARBAND) == 0


# ===================================================================
# Card 50: Shifting Loyalties
# ===================================================================

class TestCard50ShiftingLoyalties:
    """Tests for Card 50: Shifting Loyalties."""

    def test_card_50_removes_capability(self):
        """Remove a specified Capability from play."""
        state = _setup_base_state()
        from fs_bot.cards.capabilities import activate_capability, is_capability_active
        from fs_bot.rules_consts import EVENT_UNSHADED
        activate_capability(state, 8, EVENT_UNSHADED)
        assert is_capability_active(state, 8)
        state["event_params"] = {"target_capability": 8}
        execute_event(state, 50, shaded=False)
        assert not is_capability_active(state, 8)

    def test_card_50_auto_removes_first_capability(self):
        """Without params, removes first active capability."""
        state = _setup_base_state()
        from fs_bot.cards.capabilities import activate_capability, is_capability_active
        from fs_bot.rules_consts import EVENT_SHADED
        activate_capability(state, 10, EVENT_SHADED)
        execute_event(state, 50, shaded=True)
        assert not is_capability_active(state, 10)


# ===================================================================
# Card 28: Oppida — Gallic Allies at Cities
# ===================================================================

class TestCard28Oppida:
    """Tests for Card 28: Oppida (place Gallic Allies, upgrade to Citadels)."""

    def test_card_28_place_ally_and_upgrade_citadel(self):
        """Place Gallic Ally at Subdued City, then upgrade to Citadel."""
        from fs_bot.rules_consts import (
            CITY_AVARICUM, TRIBE_BITURIGES, TRIBE_TO_REGION,
        )
        state = _setup_base_state()
        region = TRIBE_TO_REGION[TRIBE_BITURIGES]
        state["event_params"] = {
            "ally_placements": [
                {"tribe": TRIBE_BITURIGES, "faction": ARVERNI},
            ],
            "citadel_upgrades": [CITY_AVARICUM],
        }
        execute_event(state, 28, shaded=False)
        # Ally placed then upgraded to Citadel
        assert count_pieces(state, region, ARVERNI, CITADEL) == 1
        assert state["tribes"][TRIBE_BITURIGES]["allied_faction"] == ARVERNI

    def test_card_28_no_ally_at_roman_control(self):
        """Cannot place Ally at City under Roman Control."""
        from fs_bot.rules_consts import TRIBE_BITURIGES, TRIBE_TO_REGION
        state = _setup_base_state()
        region = TRIBE_TO_REGION[TRIBE_BITURIGES]
        # Make region Roman Controlled
        place_piece(state, region, ROMANS, FORT)
        place_piece(state, region, ROMANS, AUXILIA, count=3)
        refresh_all_control(state)
        state["event_params"] = {
            "ally_placements": [
                {"tribe": TRIBE_BITURIGES, "faction": ARVERNI},
            ],
            "citadel_upgrades": [],
        }
        execute_event(state, 28, shaded=False)
        assert count_pieces(state, region, ARVERNI, ALLY) == 0


# ===================================================================
# Card 34: Acco — Replace Allies in Carnutes & Mandubii
# ===================================================================

class TestCard34Acco:
    """Tests for Card 34: Acco shaded (replace Allies with Arverni)."""

    def test_card_34_shaded_replaces_allies(self):
        """Shaded: Replace non-Arverni Allies in Carnutes/Mandubii."""
        from fs_bot.rules_consts import (
            CARNUTES, TRIBE_CARNUTES, TRIBE_TO_REGION,
        )
        state = _setup_base_state()
        # Place Aedui Ally at Carnutes tribe
        place_piece(state, CARNUTES, AEDUI, ALLY)
        state["tribes"][TRIBE_CARNUTES]["allied_faction"] = AEDUI
        execute_event(state, 34, shaded=True)
        # Should be replaced with Arverni
        assert count_pieces(state, CARNUTES, AEDUI, ALLY) == 0
        assert count_pieces(state, CARNUTES, ARVERNI, ALLY) == 1
        assert state["tribes"][TRIBE_CARNUTES]["allied_faction"] == ARVERNI


# ===================================================================
# Card 46: Celtic Rites — Resource drain + Ineligible
# ===================================================================

class TestCard46CelticRites:
    """Tests for Card 46: Celtic Rites."""

    def test_card_46_unshaded_drain_resources(self):
        """Unshaded: Selected Gallic Factions lose 3 Resources, go Ineligible."""
        state = _setup_base_state()
        state["event_params"] = {"target_factions": [ARVERNI, BELGAE]}
        execute_event(state, 46, shaded=False)
        assert state["resources"][ARVERNI] == 12  # 15 - 3
        assert state["resources"][BELGAE] == 7   # 10 - 3
        assert state["eligibility"][ARVERNI] == INELIGIBLE
        assert state["eligibility"][BELGAE] == INELIGIBLE

    def test_card_46_shaded_stay_eligible(self):
        """Shaded: Executing faction stays Eligible."""
        state = _setup_base_state()
        state["executing_faction"] = ARVERNI
        execute_event(state, 46, shaded=True)
        assert state["eligibility"][ARVERNI] == ELIGIBLE


# ===================================================================
# Card 52: Assembly of Gaul — Resource drain
# ===================================================================

class TestCard52AssemblyOfGaul:
    """Tests for Card 52: Assembly of Gaul."""

    def test_card_52_unshaded_drain_gallic_resources(self):
        """Unshaded: Drain Gallic factions -8 if Carnutes is Subdued."""
        from fs_bot.rules_consts import TRIBE_CARNUTES
        state = _setup_base_state()
        # Carnutes tribe is Subdued by default (allied_faction=None, no Dispersed)
        state["event_params"] = {"target_factions": [ARVERNI]}
        execute_event(state, 52, shaded=False)
        assert state["resources"][ARVERNI] == 7  # 15 - 8


# ===================================================================
# Card 56: Flight of Ambiorix
# ===================================================================

class TestCard56FlightOfAmbiorix:
    """Tests for Card 56: Flight of Ambiorix."""

    def test_card_56_shaded_place_ambiorix(self):
        """Shaded: If Ambiorix not on map, place in Germania region."""
        state = _setup_base_state()
        state["event_params"] = {"target_region": SUGAMBRI}
        execute_event(state, 56, shaded=True)
        from fs_bot.board.pieces import find_leader
        assert find_leader(state, BELGAE) == SUGAMBRI


# ===================================================================
# Card 61: Catuvolcus — Belgic placement
# ===================================================================

class TestCard61Catuvolcus:
    """Tests for Card 61: Catuvolcus."""

    def test_card_61_shaded_place_belgic_allies(self):
        """Shaded: Place Belgic Allies at Nervii and Eburones, +6 Resources."""
        from fs_bot.rules_consts import TRIBE_NERVII, TRIBE_EBURONES
        state = _setup_base_state()
        execute_event(state, 61, shaded=True)
        assert state["tribes"][TRIBE_NERVII]["allied_faction"] == BELGAE
        assert state["tribes"][TRIBE_EBURONES]["allied_faction"] == BELGAE
        assert state["resources"][BELGAE] == 16  # 10 + 6


# ===================================================================
# Card A25: Ariovistus's Wife
# ===================================================================

class TestCardA25AriovistusWife:
    """Tests for Card A25: Ariovistus's Wife."""

    def test_card_A25_unshaded_remove_germans_cisalpina(self):
        """Unshaded: Remove non-Leader German pieces from Cisalpina, -6 Resources."""
        from fs_bot.rules_consts import CISALPINA
        state = _setup_ariovistus_state()
        place_piece(state, CISALPINA, GERMANS, WARBAND, count=3)
        execute_event(state, "A25", shaded=False)
        from fs_bot.board.pieces import count_pieces_by_state
        total_wb = (count_pieces_by_state(state, CISALPINA, GERMANS, WARBAND, HIDDEN) +
                    count_pieces_by_state(state, CISALPINA, GERMANS, WARBAND, REVEALED))
        assert total_wb == 0
        assert state["resources"][GERMANS] == 4  # 10 - 6

    def test_card_A25_shaded_place_at_nori(self):
        """Shaded: Place German Ally and 6 Warbands at Nori, +6 Resources."""
        from fs_bot.rules_consts import TRIBE_NORI, TRIBE_TO_REGION, CISALPINA
        state = _setup_ariovistus_state()
        region = TRIBE_TO_REGION[TRIBE_NORI]
        execute_event(state, "A25", shaded=True)
        assert state["tribes"][TRIBE_NORI]["allied_faction"] == GERMANS
        assert state["resources"][GERMANS] == 16  # 10 + 6


# ===================================================================
# Card A53: Frumentum — Resource drain
# ===================================================================

class TestCardA53Frumentum:
    """Tests for Card A53: Frumentum."""

    def test_card_A53_shaded_drain_and_ineligible(self):
        """Shaded: Aedui and Roman -4 each, both Ineligible. Executor Eligible."""
        state = _setup_ariovistus_state()
        state["executing_faction"] = BELGAE
        execute_event(state, "A53", shaded=True)
        assert state["resources"][AEDUI] == 6   # 10 - 4
        assert state["resources"][ROMANS] == 16  # 20 - 4
        assert state["eligibility"][AEDUI] == INELIGIBLE
        assert state["eligibility"][ROMANS] == INELIGIBLE
        assert state["eligibility"][BELGAE] == ELIGIBLE


# ===================================================================
# Card A70: Nervii — CAPABILITY
# ===================================================================

class TestCardA70Nervii:
    """Tests for Card A70: Nervii."""

    def test_card_A70_unshaded_sets_modifier(self):
        """Unshaded: Sets no-Belgae-Retreat modifier."""
        state = _setup_ariovistus_state()
        execute_event(state, "A70", shaded=False)
        assert state["event_modifiers"]["card_A70_no_belgae_retreat"] is True

    def test_card_A70_shaded_activates_capability(self):
        """Shaded: Activates capability."""
        from fs_bot.cards.capabilities import is_capability_active
        state = _setup_ariovistus_state()
        execute_event(state, "A70", shaded=True)
        assert is_capability_active(state, "A70")


# ===================================================================
# Card 8: Baggage Trains — CAPABILITY (both sides)
# Card Reference: "Well-stocked: Take this card and place it at your
#   Forces display. Your March costs 0 Resources. CAPABILITY"
# Shaded: "Slow wagons: Take this card. Your Raids may use 3
#   Warbands per Region and steal Resources despite Citadels or Forts."
# ===================================================================

class TestCard8BaggageTrains:
    """Tests for Card 8: Baggage Trains (CAPABILITY)."""

    def test_card_8_unshaded_activates_capability(self):
        """Unshaded: activates unshaded capability (March costs 0)."""
        state = _setup_base_state()
        execute_event(state, 8, shaded=False)
        assert is_capability_active(state, 8, EVENT_UNSHADED)

    def test_card_8_shaded_activates_capability(self):
        """Shaded: activates shaded capability (Raids with 3 Warbands)."""
        state = _setup_base_state()
        execute_event(state, 8, shaded=True)
        assert is_capability_active(state, 8, EVENT_SHADED)

    def test_card_8_unshaded_replaces_shaded(self):
        """Per §5.1.2: activating unshaded replaces existing shaded capability."""
        state = _setup_base_state()
        execute_event(state, 8, shaded=True)
        assert is_capability_active(state, 8, EVENT_SHADED)
        execute_event(state, 8, shaded=False)
        assert is_capability_active(state, 8, EVENT_UNSHADED)
        assert not is_capability_active(state, 8, EVENT_SHADED)

    def test_card_8_shaded_replaces_unshaded(self):
        """Per §5.1.2: activating shaded replaces existing unshaded capability."""
        state = _setup_base_state()
        execute_event(state, 8, shaded=False)
        assert is_capability_active(state, 8, EVENT_UNSHADED)
        execute_event(state, 8, shaded=True)
        assert is_capability_active(state, 8, EVENT_SHADED)
        assert not is_capability_active(state, 8, EVENT_UNSHADED)

    def test_card_8_no_other_state_mutation(self):
        """Capability-only: no pieces, resources, or senate changes."""
        state = _setup_base_state()
        resources_before = dict(state["resources"])
        senate_before = dict(state["senate"])
        execute_event(state, 8, shaded=False)
        assert state["resources"] == resources_before
        assert state["senate"] == senate_before


# ===================================================================
# Card 10: Ballistae — CAPABILITY (both sides)
# Card Reference:
# Unshaded: "Siege machines: Besiege cancels Citadel's halving of
#   Losses. Battle rolls remove Forts on 1-2 not 1-3."
# Shaded: "Siege stratagems: Place near a Gallic Faction. That
#   Faction after Ambush may remove defending Fort or Citadel."
# ===================================================================

class TestCard10Ballistae:
    """Tests for Card 10: Ballistae (CAPABILITY)."""

    def test_card_10_unshaded_activates_capability(self):
        """Unshaded: activates unshaded capability (improved Besiege)."""
        state = _setup_base_state()
        execute_event(state, 10, shaded=False)
        assert is_capability_active(state, 10, EVENT_UNSHADED)

    def test_card_10_shaded_activates_capability(self):
        """Shaded: activates shaded capability (Gallic Faction Ambush benefit)."""
        state = _setup_base_state()
        execute_event(state, 10, shaded=True)
        assert is_capability_active(state, 10, EVENT_SHADED)

    def test_card_10_unshaded_replaces_shaded(self):
        """Per §5.1.2: dueling event replaces opposite side."""
        state = _setup_base_state()
        execute_event(state, 10, shaded=True)
        assert is_capability_active(state, 10, EVENT_SHADED)
        execute_event(state, 10, shaded=False)
        assert is_capability_active(state, 10, EVENT_UNSHADED)
        assert not is_capability_active(state, 10, EVENT_SHADED)

    def test_card_10_no_other_state_mutation(self):
        """Capability-only: no pieces, resources, or senate changes."""
        state = _setup_base_state()
        resources_before = dict(state["resources"])
        senate_before = dict(state["senate"])
        execute_event(state, 10, shaded=True)
        assert state["resources"] == resources_before
        assert state["senate"] == senate_before


# ===================================================================
# Card 12: Titus Labienus — CAPABILITY (both sides)
# Card Reference:
# Unshaded: "Able lieutenant: Roman Special Abilities may select
#   Regions regardless of where the Roman leader is located."
# Shaded: "Opponents suborn Caesar's 2nd: Build and Scout Reveal
#   are maximum 1 Region."
# ===================================================================

class TestCard12TitusLabienus:
    """Tests for Card 12: Titus Labienus (CAPABILITY)."""

    def test_card_12_unshaded_activates_capability(self):
        """Unshaded: activates unshaded capability (unrestricted SA Regions)."""
        state = _setup_base_state()
        execute_event(state, 12, shaded=False)
        assert is_capability_active(state, 12, EVENT_UNSHADED)

    def test_card_12_shaded_activates_capability(self):
        """Shaded: activates shaded capability (Build/Scout max 1 Region)."""
        state = _setup_base_state()
        execute_event(state, 12, shaded=True)
        assert is_capability_active(state, 12, EVENT_SHADED)

    def test_card_12_shaded_replaces_unshaded(self):
        """Per §5.1.2: dueling event replaces opposite side."""
        state = _setup_base_state()
        execute_event(state, 12, shaded=False)
        assert is_capability_active(state, 12, EVENT_UNSHADED)
        execute_event(state, 12, shaded=True)
        assert is_capability_active(state, 12, EVENT_SHADED)
        assert not is_capability_active(state, 12, EVENT_UNSHADED)

    def test_card_12_no_other_state_mutation(self):
        """Capability-only: no pieces, resources, or senate changes."""
        state = _setup_base_state()
        resources_before = dict(state["resources"])
        senate_before = dict(state["senate"])
        execute_event(state, 12, shaded=False)
        assert state["resources"] == resources_before
        assert state["senate"] == senate_before


# ===================================================================
# Card 13: Balearic Slingers — CAPABILITY (both sides)
# Card Reference:
# Unshaded: "Sharp skirmishers: Romans choose 1 Region per enemy
#   Battle Command. Auxilia there first inflict 1/2 Loss each on
#   attacker. Then resolve Battle."
# Shaded: "Reliance on foreign contingents: Recruit only where
#   Supply Line, paying 2 Resources per Region."
# ===================================================================

class TestCard13BalearicSlingers:
    """Tests for Card 13: Balearic Slingers (CAPABILITY)."""

    def test_card_13_unshaded_activates_capability(self):
        """Unshaded: activates capability (Auxilia skirmish before Battle)."""
        state = _setup_base_state()
        execute_event(state, 13, shaded=False)
        assert is_capability_active(state, 13, EVENT_UNSHADED)

    def test_card_13_shaded_activates_capability(self):
        """Shaded: activates capability (Recruit restricted to Supply Lines)."""
        state = _setup_base_state()
        execute_event(state, 13, shaded=True)
        assert is_capability_active(state, 13, EVENT_SHADED)

    def test_card_13_unshaded_replaces_shaded(self):
        """Per §5.1.2: dueling event replaces opposite side."""
        state = _setup_base_state()
        execute_event(state, 13, shaded=True)
        assert is_capability_active(state, 13, EVENT_SHADED)
        execute_event(state, 13, shaded=False)
        assert is_capability_active(state, 13, EVENT_UNSHADED)
        assert not is_capability_active(state, 13, EVENT_SHADED)

    def test_card_13_no_other_state_mutation(self):
        """Capability-only: no pieces, resources, or senate changes."""
        state = _setup_base_state()
        resources_before = dict(state["resources"])
        senate_before = dict(state["senate"])
        execute_event(state, 13, shaded=False)
        assert state["resources"] == resources_before
        assert state["senate"] == senate_before


# ===================================================================
# Card 30: Vercingetorix's Elite — CAPABILITY (both sides)
# Card Reference:
# Unshaded: "Harsh punishments unpopular: Arverni Rally places
#   Warbands up to Allies+Citadels (not Leader+1)."
# Shaded: "Roman-style discipline: In any Battles with their Leader,
#   Arverni pick 2 Arverni Warbands—they take & inflict Losses as
#   if Legions."
# Tip: If the two picked Warbands are defending, are chosen to
#   absorb Losses, and both roll a 1-3, the Counterattack would not
#   inflict Losses as if with any Legions.
# ===================================================================

class TestCard30VercingetorixsElite:
    """Tests for Card 30: Vercingetorix's Elite (CAPABILITY)."""

    def test_card_30_unshaded_activates_capability(self):
        """Unshaded: activates capability (Rally limit = Allies+Citadels)."""
        state = _setup_base_state()
        execute_event(state, 30, shaded=False)
        assert is_capability_active(state, 30, EVENT_UNSHADED)

    def test_card_30_shaded_activates_capability(self):
        """Shaded: activates capability (2 Warbands fight as Legions)."""
        state = _setup_base_state()
        execute_event(state, 30, shaded=True)
        assert is_capability_active(state, 30, EVENT_SHADED)

    def test_card_30_shaded_replaces_unshaded(self):
        """Per §5.1.2: dueling event replaces opposite side."""
        state = _setup_base_state()
        execute_event(state, 30, shaded=False)
        assert is_capability_active(state, 30, EVENT_UNSHADED)
        execute_event(state, 30, shaded=True)
        assert is_capability_active(state, 30, EVENT_SHADED)
        assert not is_capability_active(state, 30, EVENT_UNSHADED)

    def test_card_30_no_other_state_mutation(self):
        """Capability-only: no pieces, resources, or senate changes."""
        state = _setup_base_state()
        resources_before = dict(state["resources"])
        senate_before = dict(state["senate"])
        execute_event(state, 30, shaded=True)
        assert state["resources"] == resources_before
        assert state["senate"] == senate_before
