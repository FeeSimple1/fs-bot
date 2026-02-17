"""
Tests for the control module.

Tests Roman control with Fort, Gallic control with Allies, Germanic control
with Settlements, tied pieces = no control, stacking restriction enforcement.

Reference: §1.6, A1.4
"""

import pytest

from fs_bot.rules_consts import (
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    HIDDEN, REVEALED,
    CAESAR, AMBIORIX, ARIOVISTUS_LEADER,
    ROMAN_CONTROL, ARVERNI_CONTROL, AEDUI_CONTROL,
    BELGIC_CONTROL, GERMANIC_CONTROL, NO_CONTROL,
    SCENARIO_PAX_GALLICA, SCENARIO_ARIOVISTUS,
    MORINI, NERVII, PROVINCIA, SUGAMBRI, UBII, SEQUANI,
    AEDUI_REGION,
)

from fs_bot.state.state_schema import build_initial_state
from fs_bot.board.pieces import place_piece, count_pieces
from fs_bot.board.control import (
    calculate_control, refresh_all_control, is_controlled_by,
    get_controlled_regions,
)


def make_state(scenario=SCENARIO_PAX_GALLICA, seed=42):
    return build_initial_state(scenario, seed=seed)


class TestControlCalculation:
    """Test control calculation per §1.6."""

    def test_empty_region_no_control(self):
        state = make_state()
        assert calculate_control(state, MORINI) == NO_CONTROL

    def test_single_faction_controls(self):
        """One faction with pieces, others with none = control."""
        state = make_state()
        place_piece(state, MORINI, BELGAE, WARBAND, 3)
        assert calculate_control(state, MORINI) == BELGIC_CONTROL

    def test_more_than_all_others_combined(self):
        """Control requires more than ALL others combined."""
        state = make_state()
        place_piece(state, MORINI, BELGAE, WARBAND, 5)
        place_piece(state, MORINI, ROMANS, AUXILIA, 2)
        place_piece(state, MORINI, ARVERNI, WARBAND, 2)
        # Belgae: 5, Others: 2+2=4. 5 > 4, so Belgic Control
        assert calculate_control(state, MORINI) == BELGIC_CONTROL

    def test_equal_no_control(self):
        """Equal pieces = no control."""
        state = make_state()
        place_piece(state, MORINI, BELGAE, WARBAND, 3)
        place_piece(state, MORINI, ROMANS, AUXILIA, 3)
        # Belgae: 3, Others: 3. Not strictly more. No control.
        assert calculate_control(state, MORINI) == NO_CONTROL

    def test_roman_fort_counts(self):
        """Roman Forts count as pieces for control — §1.6."""
        state = make_state()
        place_piece(state, MORINI, ROMANS, AUXILIA, 2)
        place_piece(state, MORINI, ROMANS, FORT, 1)
        place_piece(state, MORINI, BELGAE, WARBAND, 2)
        # Romans: 2 Auxilia + 1 Fort = 3, Belgae: 2. 3 > 2 = Roman Control
        assert calculate_control(state, MORINI) == ROMAN_CONTROL

    def test_roman_fort_tips_balance(self):
        """Fort is the piece that tips control to Romans."""
        state = make_state()
        place_piece(state, MORINI, ROMANS, AUXILIA, 2)
        place_piece(state, MORINI, BELGAE, WARBAND, 2)
        # Without fort: 2 vs 2, no control
        assert calculate_control(state, MORINI) == NO_CONTROL
        # Add fort
        place_piece(state, MORINI, ROMANS, FORT, 1)
        # With fort: 3 vs 2, Roman control
        assert calculate_control(state, MORINI) == ROMAN_CONTROL

    def test_allies_count(self):
        """Allies count as pieces for control."""
        state = make_state()
        place_piece(state, MORINI, BELGAE, ALLY, 1)
        place_piece(state, MORINI, BELGAE, WARBAND, 1)
        # Belgae: 2, others: 0
        assert calculate_control(state, MORINI) == BELGIC_CONTROL

    def test_citadels_count(self):
        """Citadels count as pieces for control."""
        state = make_state()
        place_piece(state, MORINI, BELGAE, CITADEL, 1)
        # Belgae: 1, others: 0
        assert calculate_control(state, MORINI) == BELGIC_CONTROL

    def test_leader_counts(self):
        """Leader counts as 1 piece for control."""
        state = make_state()
        place_piece(state, MORINI, BELGAE, LEADER, leader_name=AMBIORIX)
        # Belgae: 1, others: 0
        assert calculate_control(state, MORINI) == BELGIC_CONTROL

    def test_settlement_counts_in_ariovistus(self):
        """Settlements count for German control in Ariovistus."""
        state = make_state(SCENARIO_ARIOVISTUS)
        place_piece(state, SUGAMBRI, GERMANS, SETTLEMENT, 1)
        # Germans: 1, others: 0
        assert calculate_control(state, SUGAMBRI) == GERMANIC_CONTROL

    def test_settlement_does_not_count_in_base(self):
        """Settlements don't exist in base game — can't even place them."""
        state = make_state(SCENARIO_PAX_GALLICA)
        # Settlement can't be placed in base (PieceError), so this
        # tests that the control calc doesn't find phantom settlements
        assert calculate_control(state, SUGAMBRI) == NO_CONTROL

    def test_germanic_control(self):
        state = make_state()
        place_piece(state, SUGAMBRI, GERMANS, WARBAND, 4)
        place_piece(state, SUGAMBRI, GERMANS, ALLY, 1)
        assert calculate_control(state, SUGAMBRI) == GERMANIC_CONTROL


class TestRefreshAllControl:
    """Test refresh_all_control updates all regions."""

    def test_refresh_sets_control(self):
        state = make_state()
        place_piece(state, MORINI, BELGAE, WARBAND, 3)
        place_piece(state, NERVII, ROMANS, AUXILIA, 2)
        refresh_all_control(state)
        assert state["spaces"][MORINI]["control"] == BELGIC_CONTROL
        assert state["spaces"][NERVII]["control"] == ROMAN_CONTROL


class TestIsControlledBy:
    """Test is_controlled_by helper."""

    def test_controlled_by_true(self):
        state = make_state()
        place_piece(state, MORINI, BELGAE, WARBAND, 3)
        refresh_all_control(state)
        assert is_controlled_by(state, MORINI, BELGAE)

    def test_controlled_by_false(self):
        state = make_state()
        place_piece(state, MORINI, BELGAE, WARBAND, 3)
        refresh_all_control(state)
        assert not is_controlled_by(state, MORINI, ROMANS)


class TestGetControlledRegions:
    """Test get_controlled_regions."""

    def test_get_controlled(self):
        state = make_state()
        place_piece(state, MORINI, BELGAE, WARBAND, 3)
        place_piece(state, NERVII, BELGAE, WARBAND, 2)
        place_piece(state, SUGAMBRI, GERMANS, WARBAND, 4)
        refresh_all_control(state)
        belgic = get_controlled_regions(state, BELGAE)
        assert MORINI in belgic
        assert NERVII in belgic
        assert SUGAMBRI not in belgic
