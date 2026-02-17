"""
Tests for the piece operations module.

Tests cap enforcement, Available pool updates on place/remove/move,
Legion routing to track/fallen, flip states.
"""

import pytest

from fs_bot.rules_consts import (
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    HIDDEN, REVEALED, SCOUTED,
    CAESAR, VERCINGETORIX, AMBIORIX, ARIOVISTUS_LEADER, DIVICIACUS,
    SUCCESSOR,
    SCENARIO_PAX_GALLICA, SCENARIO_ARIOVISTUS,
    MORINI, NERVII, PROVINCIA, SUGAMBRI, UBII, SEQUANI,
    AEDUI_REGION, MANDUBII,
    LEGIONS_ROW_BOTTOM, LEGIONS_ROW_MIDDLE, LEGIONS_ROW_TOP,
    CAPS_BASE, CAPS_ARIOVISTUS,
    MAX_FORTS_PER_REGION, MAX_SETTLEMENTS_PER_REGION,
)

from fs_bot.state.state_schema import build_initial_state
from fs_bot.board.pieces import (
    place_piece, remove_piece, move_piece, flip_piece,
    count_pieces, count_pieces_by_state, get_available,
    get_leader_in_region, find_leader,
    PieceError,
)


def make_state(scenario=SCENARIO_PAX_GALLICA, seed=42):
    """Helper to create a fresh state for testing."""
    return build_initial_state(scenario, seed=seed)


# ============================================================================
# PLACEMENT TESTS
# ============================================================================

class TestPlacePiece:
    """Test piece placement from Available onto map."""

    def test_place_warband(self):
        state = make_state()
        avail_before = get_available(state, ARVERNI, WARBAND)
        place_piece(state, MORINI, ARVERNI, WARBAND, 3)
        assert count_pieces(state, MORINI, ARVERNI, WARBAND) == 3
        assert get_available(state, ARVERNI, WARBAND) == avail_before - 3

    def test_place_auxilia_hidden_by_default(self):
        """Auxilia placed Hidden per §1.4.3."""
        state = make_state()
        place_piece(state, PROVINCIA, ROMANS, AUXILIA, 2)
        assert count_pieces_by_state(
            state, PROVINCIA, ROMANS, AUXILIA, HIDDEN
        ) == 2
        assert count_pieces_by_state(
            state, PROVINCIA, ROMANS, AUXILIA, REVEALED
        ) == 0

    def test_place_warband_hidden_by_default(self):
        state = make_state()
        place_piece(state, MORINI, BELGAE, WARBAND, 1)
        assert count_pieces_by_state(
            state, MORINI, BELGAE, WARBAND, HIDDEN
        ) == 1

    def test_place_fort(self):
        state = make_state()
        avail_before = get_available(state, ROMANS, FORT)
        place_piece(state, MORINI, ROMANS, FORT, 1)
        assert count_pieces(state, MORINI, ROMANS, FORT) == 1
        assert get_available(state, ROMANS, FORT) == avail_before - 1

    def test_place_ally(self):
        state = make_state()
        avail_before = get_available(state, BELGAE, ALLY)
        place_piece(state, MORINI, BELGAE, ALLY, 1)
        assert count_pieces(state, MORINI, BELGAE, ALLY) == 1
        assert get_available(state, BELGAE, ALLY) == avail_before - 1

    def test_place_leader(self):
        state = make_state()
        place_piece(state, PROVINCIA, ROMANS, LEADER, leader_name=CAESAR)
        assert get_leader_in_region(state, PROVINCIA, ROMANS) == CAESAR
        assert get_available(state, ROMANS, LEADER) == 0

    def test_place_legion_from_track(self):
        state = make_state()
        # Base game: 12 Legions, all on track initially
        track_before = sum(
            state["legions_track"][r]
            for r in (LEGIONS_ROW_BOTTOM, LEGIONS_ROW_MIDDLE, LEGIONS_ROW_TOP)
        )
        place_piece(state, PROVINCIA, ROMANS, LEGION, 3,
                    from_legions_track=True)
        assert count_pieces(state, PROVINCIA, ROMANS, LEGION) == 3
        track_after = sum(
            state["legions_track"][r]
            for r in (LEGIONS_ROW_BOTTOM, LEGIONS_ROW_MIDDLE, LEGIONS_ROW_TOP)
        )
        assert track_after == track_before - 3

    def test_place_settlement_ariovistus(self):
        state = make_state(SCENARIO_ARIOVISTUS)
        avail_before = get_available(state, GERMANS, SETTLEMENT)
        place_piece(state, SUGAMBRI, GERMANS, SETTLEMENT, 1)
        assert count_pieces(state, SUGAMBRI, GERMANS, SETTLEMENT) == 1
        assert get_available(state, GERMANS, SETTLEMENT) == avail_before - 1


# ============================================================================
# CAP ENFORCEMENT TESTS
# ============================================================================

class TestCapEnforcement:
    """Test that piece caps are enforced."""

    def test_exceed_warband_cap(self):
        state = make_state()
        cap = CAPS_BASE[ARVERNI][WARBAND]
        with pytest.raises(PieceError):
            place_piece(state, MORINI, ARVERNI, WARBAND, cap + 1)

    def test_exceed_fort_cap_per_region(self):
        state = make_state()
        place_piece(state, MORINI, ROMANS, FORT, 1)
        with pytest.raises(PieceError):
            place_piece(state, MORINI, ROMANS, FORT, 1)

    def test_exceed_settlement_cap_per_region(self):
        state = make_state(SCENARIO_ARIOVISTUS)
        place_piece(state, SUGAMBRI, GERMANS, SETTLEMENT, 1)
        with pytest.raises(PieceError):
            place_piece(state, SUGAMBRI, GERMANS, SETTLEMENT, 1)

    def test_settlement_not_in_base(self):
        state = make_state(SCENARIO_PAX_GALLICA)
        with pytest.raises(PieceError):
            place_piece(state, SUGAMBRI, GERMANS, SETTLEMENT, 1)

    def test_vercingetorix_not_in_ariovistus(self):
        """Arverni have 0 Leader cap in Ariovistus."""
        state = make_state(SCENARIO_ARIOVISTUS)
        with pytest.raises(PieceError):
            place_piece(state, MORINI, ARVERNI, LEADER,
                        leader_name=VERCINGETORIX)

    def test_legion_requires_track_or_fallen(self):
        state = make_state()
        with pytest.raises(PieceError):
            place_piece(state, PROVINCIA, ROMANS, LEGION, 1)

    def test_leader_requires_name(self):
        state = make_state()
        with pytest.raises(PieceError):
            place_piece(state, PROVINCIA, ROMANS, LEADER)


# ============================================================================
# REMOVAL TESTS
# ============================================================================

class TestRemovePiece:
    """Test piece removal from map."""

    def test_remove_warband_to_available(self):
        state = make_state()
        place_piece(state, MORINI, BELGAE, WARBAND, 5)
        avail_before = get_available(state, BELGAE, WARBAND)
        remove_piece(state, MORINI, BELGAE, WARBAND, 2)
        assert count_pieces(state, MORINI, BELGAE, WARBAND) == 3
        assert get_available(state, BELGAE, WARBAND) == avail_before + 2

    def test_remove_legion_to_fallen(self):
        state = make_state()
        place_piece(state, PROVINCIA, ROMANS, LEGION, 4,
                    from_legions_track=True)
        remove_piece(state, PROVINCIA, ROMANS, LEGION, 2, to_fallen=True)
        assert count_pieces(state, PROVINCIA, ROMANS, LEGION) == 2
        assert state["fallen_legions"] == 2

    def test_remove_legion_default_to_fallen(self):
        """Default removal destination for Legions is Fallen — §1.4.1."""
        state = make_state()
        place_piece(state, PROVINCIA, ROMANS, LEGION, 2,
                    from_legions_track=True)
        remove_piece(state, PROVINCIA, ROMANS, LEGION, 1)
        assert state["fallen_legions"] == 1

    def test_remove_legion_to_track(self):
        state = make_state()
        place_piece(state, PROVINCIA, ROMANS, LEGION, 4,
                    from_legions_track=True)
        fallen_before = state["fallen_legions"]
        remove_piece(state, PROVINCIA, ROMANS, LEGION, 2, to_track=True)
        assert state["fallen_legions"] == fallen_before

    def test_remove_legion_to_removed(self):
        """Legions removed by Event for Arverni victory tracking."""
        state = make_state()
        place_piece(state, PROVINCIA, ROMANS, LEGION, 2,
                    from_legions_track=True)
        remove_piece(state, PROVINCIA, ROMANS, LEGION, 1, to_removed=True)
        assert state["removed_legions"] == 1

    def test_remove_leader(self):
        state = make_state()
        place_piece(state, PROVINCIA, ROMANS, LEADER, leader_name=CAESAR)
        remove_piece(state, PROVINCIA, ROMANS, LEADER)
        assert get_leader_in_region(state, PROVINCIA, ROMANS) is None
        assert get_available(state, ROMANS, LEADER) == 1

    def test_remove_diviciacus_from_play(self):
        """Diviciacus removed from play, NOT to Available — A1.4."""
        state = make_state(SCENARIO_ARIOVISTUS)
        place_piece(state, AEDUI_REGION, AEDUI, LEADER,
                    leader_name=DIVICIACUS)
        remove_piece(state, AEDUI_REGION, AEDUI, LEADER)
        assert get_leader_in_region(state, AEDUI_REGION, AEDUI) is None
        # Should NOT be in Available
        assert get_available(state, AEDUI, LEADER) == 0

    def test_cannot_remove_provincia_permanent_fort(self):
        """Provincia permanent Fort cannot be removed — §1.4.2."""
        state = make_state()
        place_piece(state, PROVINCIA, ROMANS, FORT, 1)
        with pytest.raises(PieceError):
            remove_piece(state, PROVINCIA, ROMANS, FORT, 1)

    def test_remove_nonexistent_piece_raises(self):
        state = make_state()
        with pytest.raises(PieceError):
            remove_piece(state, MORINI, BELGAE, WARBAND, 1)


# ============================================================================
# MOVE TESTS
# ============================================================================

class TestMovePiece:
    """Test piece movement between regions."""

    def test_move_warband(self):
        state = make_state()
        place_piece(state, MORINI, BELGAE, WARBAND, 3)
        avail_before = get_available(state, BELGAE, WARBAND)
        move_piece(state, MORINI, NERVII, BELGAE, WARBAND, 2)
        assert count_pieces(state, MORINI, BELGAE, WARBAND) == 1
        assert count_pieces(state, NERVII, BELGAE, WARBAND) == 2
        # Available should not change
        assert get_available(state, BELGAE, WARBAND) == avail_before

    def test_move_legion(self):
        state = make_state()
        place_piece(state, PROVINCIA, ROMANS, LEGION, 4,
                    from_legions_track=True)
        move_piece(state, PROVINCIA, MORINI, ROMANS, LEGION, 2)
        assert count_pieces(state, PROVINCIA, ROMANS, LEGION) == 2
        assert count_pieces(state, MORINI, ROMANS, LEGION) == 2

    def test_move_leader(self):
        state = make_state()
        place_piece(state, PROVINCIA, ROMANS, LEADER, leader_name=CAESAR)
        move_piece(state, PROVINCIA, MORINI, ROMANS, LEADER)
        assert get_leader_in_region(state, PROVINCIA, ROMANS) is None
        assert get_leader_in_region(state, MORINI, ROMANS) == CAESAR

    def test_move_insufficient_pieces_raises(self):
        state = make_state()
        place_piece(state, MORINI, BELGAE, WARBAND, 1)
        with pytest.raises(PieceError):
            move_piece(state, MORINI, NERVII, BELGAE, WARBAND, 2)


# ============================================================================
# FLIP TESTS
# ============================================================================

class TestFlipPiece:
    """Test piece flipping between Hidden/Revealed/Scouted."""

    def test_flip_hidden_to_revealed(self):
        state = make_state()
        place_piece(state, MORINI, BELGAE, WARBAND, 3)
        flip_piece(state, MORINI, BELGAE, WARBAND, 2,
                   from_state=HIDDEN, to_state=REVEALED)
        assert count_pieces_by_state(
            state, MORINI, BELGAE, WARBAND, HIDDEN) == 1
        assert count_pieces_by_state(
            state, MORINI, BELGAE, WARBAND, REVEALED) == 2

    def test_flip_revealed_to_scouted(self):
        state = make_state()
        place_piece(state, MORINI, BELGAE, WARBAND, 2)
        flip_piece(state, MORINI, BELGAE, WARBAND, 2,
                   from_state=HIDDEN, to_state=REVEALED)
        flip_piece(state, MORINI, BELGAE, WARBAND, 1,
                   from_state=REVEALED, to_state=SCOUTED)
        assert count_pieces_by_state(
            state, MORINI, BELGAE, WARBAND, SCOUTED) == 1

    def test_flip_scouted_to_hidden_becomes_revealed(self):
        """Per §1.4.3: Scouted -> Hidden removes marker, piece is Revealed."""
        state = make_state()
        place_piece(state, MORINI, BELGAE, WARBAND, 1)
        flip_piece(state, MORINI, BELGAE, WARBAND, 1,
                   from_state=HIDDEN, to_state=REVEALED)
        flip_piece(state, MORINI, BELGAE, WARBAND, 1,
                   from_state=REVEALED, to_state=SCOUTED)
        # Now flip "to Hidden" — should become Revealed instead
        flip_piece(state, MORINI, BELGAE, WARBAND, 1,
                   from_state=SCOUTED, to_state=HIDDEN)
        assert count_pieces_by_state(
            state, MORINI, BELGAE, WARBAND, SCOUTED) == 0
        assert count_pieces_by_state(
            state, MORINI, BELGAE, WARBAND, REVEALED) == 1

    def test_flip_non_flippable_raises(self):
        state = make_state()
        place_piece(state, MORINI, ROMANS, FORT, 1)
        with pytest.raises(PieceError):
            flip_piece(state, MORINI, ROMANS, FORT, 1,
                       from_state=HIDDEN, to_state=REVEALED)

    def test_total_count_unchanged_after_flip(self):
        state = make_state()
        place_piece(state, MORINI, BELGAE, WARBAND, 5)
        flip_piece(state, MORINI, BELGAE, WARBAND, 3,
                   from_state=HIDDEN, to_state=REVEALED)
        assert count_pieces(state, MORINI, BELGAE, WARBAND) == 5


# ============================================================================
# COUNT AND FIND HELPERS
# ============================================================================

class TestCountHelpers:
    """Test count and find helper functions."""

    def test_count_all_pieces_in_region(self):
        state = make_state()
        place_piece(state, MORINI, BELGAE, WARBAND, 3)
        place_piece(state, MORINI, BELGAE, ALLY, 1)
        place_piece(state, MORINI, ROMANS, AUXILIA, 2)
        # Total: 3 warbands + 1 ally + 2 auxilia = 6
        assert count_pieces(state, MORINI) == 6

    def test_count_by_faction(self):
        state = make_state()
        place_piece(state, MORINI, BELGAE, WARBAND, 3)
        place_piece(state, MORINI, ROMANS, AUXILIA, 2)
        assert count_pieces(state, MORINI, BELGAE) == 3
        assert count_pieces(state, MORINI, ROMANS) == 2

    def test_count_by_faction_and_type(self):
        state = make_state()
        place_piece(state, MORINI, BELGAE, WARBAND, 3)
        place_piece(state, MORINI, BELGAE, ALLY, 1)
        assert count_pieces(state, MORINI, BELGAE, WARBAND) == 3
        assert count_pieces(state, MORINI, BELGAE, ALLY) == 1

    def test_find_leader(self):
        state = make_state()
        place_piece(state, PROVINCIA, ROMANS, LEADER, leader_name=CAESAR)
        assert find_leader(state, ROMANS) == PROVINCIA

    def test_find_leader_not_on_map(self):
        state = make_state()
        assert find_leader(state, ROMANS) is None


# ============================================================================
# AVAILABLE POOL INTEGRITY
# ============================================================================

class TestAvailableIntegrity:
    """Test that Available pools stay consistent through operations."""

    def test_place_remove_cycle(self):
        state = make_state()
        avail_start = get_available(state, BELGAE, WARBAND)
        place_piece(state, MORINI, BELGAE, WARBAND, 5)
        remove_piece(state, MORINI, BELGAE, WARBAND, 5)
        assert get_available(state, BELGAE, WARBAND) == avail_start

    def test_move_does_not_change_available(self):
        state = make_state()
        place_piece(state, MORINI, BELGAE, WARBAND, 3)
        avail = get_available(state, BELGAE, WARBAND)
        move_piece(state, MORINI, NERVII, BELGAE, WARBAND, 2)
        assert get_available(state, BELGAE, WARBAND) == avail
