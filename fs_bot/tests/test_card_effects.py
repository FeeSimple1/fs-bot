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
from fs_bot.board.pieces import place_piece, remove_piece, count_pieces
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
