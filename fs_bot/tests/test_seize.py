"""
Tests for the Seize command.

Covers Roman Seize (§3.2.3) including Dispersal, Forage,
Rally checks, and Harassment.

Reference: §3.2.3, A3.2.3
"""

import pytest

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL,
    # Piece states
    HIDDEN, REVEALED,
    # Leaders
    CAESAR,
    # Scenarios
    SCENARIO_PAX_GALLICA, SCENARIO_ARIOVISTUS,
    # Regions
    MORINI, NERVII, ATREBATES, TREVERI, CARNUTES, MANDUBII,
    SEQUANI, ARVERNI_REGION, SUGAMBRI, UBII, PROVINCIA, BRITANNIA,
    # Tribes
    TRIBE_MENAPII, TRIBE_MORINI,
    TRIBE_EBURONES, TRIBE_NERVII,
    TRIBE_BELLOVACI, TRIBE_ATREBATES, TRIBE_REMI,
    TRIBE_TREVERI,
    TRIBE_HELVII,
    # Markers
    MARKER_DEVASTATED,
    # Tribe statuses
    DISPERSED, DISPERSED_GATHERING,
    # Constants
    MAX_DISPERSED_MARKERS, MAX_RESOURCES,
    LOSS_ROLL_THRESHOLD,
)
from fs_bot.state.state_schema import build_initial_state
from fs_bot.board.pieces import (
    place_piece, count_pieces, count_pieces_by_state, remove_piece,
)
from fs_bot.board.control import refresh_all_control, is_controlled_by
from fs_bot.commands.seize import (
    seize_in_region,
    validate_seize_region,
    count_dispersed_on_map,
    get_dispersible_tribes,
    calculate_forage,
    calculate_harassment,
    get_harassment_factions,
    execute_harassment_loss,
    remove_hard_target,
    seize_rally_roll,
    CommandError,
    SEIZE_RESOURCES_PER_TRIBE,
    SEIZE_RESOURCES_PER_DISPERSED,
)


# ============================================================================
# TEST HELPERS
# ============================================================================

def make_state(scenario=SCENARIO_PAX_GALLICA, seed=42):
    """Create a fresh state for testing."""
    return build_initial_state(scenario, seed=seed)


def give_resources(state, faction, amount):
    """Give a faction some resources for testing."""
    state["resources"][faction] = amount


def setup_roman_control(state, region, *, legions=0, auxilia=0, forts=0,
                         allies=0, leader=None):
    """Set up Roman pieces to ensure Roman Control in a region."""
    if leader:
        place_piece(state, region, ROMANS, LEADER, leader_name=leader)
    if legions > 0:
        place_piece(state, region, ROMANS, LEGION, legions,
                    from_legions_track=True)
    if auxilia > 0:
        place_piece(state, region, ROMANS, AUXILIA, auxilia)
    if forts > 0:
        place_piece(state, region, ROMANS, FORT, forts)
    if allies > 0:
        place_piece(state, region, ROMANS, ALLY, allies)
    refresh_all_control(state)


def mark_devastated(state, region):
    """Mark a region as Devastated."""
    state.setdefault("markers", {}).setdefault(region, {})
    state["markers"][region][MARKER_DEVASTATED] = True


def set_tribe_allied(state, tribe, faction):
    """Set a tribe as allied to a faction."""
    state["tribes"][tribe]["allied_faction"] = faction
    state["tribes"][tribe]["status"] = None


def set_tribe_dispersed(state, tribe):
    """Set a tribe as Dispersed."""
    state["tribes"][tribe]["status"] = DISPERSED
    state["tribes"][tribe]["allied_faction"] = None


# ============================================================================
# SEIZE VALIDATION TESTS — §3.2.3
# ============================================================================

class TestSeizeValidation:
    """Test Seize region validation — §3.2.3."""

    def test_valid_seize_region(self):
        """Region with Roman pieces is valid for Seize."""
        state = make_state()
        place_piece(state, MORINI, ROMANS, AUXILIA, 1)
        valid, reason = validate_seize_region(state, MORINI)
        assert valid is True
        assert reason is None

    def test_no_roman_pieces_rejected(self):
        """Cannot Seize in region without Roman pieces — §3.2.3."""
        state = make_state()
        valid, reason = validate_seize_region(state, MORINI)
        assert valid is False
        assert "no pieces" in reason

    def test_unplayable_region_rejected(self):
        """Cannot Seize in unplayable region."""
        state = make_state(SCENARIO_ARIOVISTUS)
        valid, reason = validate_seize_region(state, BRITANNIA)
        assert valid is False


# ============================================================================
# DISPERSAL TESTS — §3.2.3 Step 1
# ============================================================================

class TestCountDispersedOnMap:
    """Test count_dispersed_on_map utility."""

    def test_zero_dispersed(self):
        """No Dispersed markers on fresh state."""
        state = make_state()
        assert count_dispersed_on_map(state) == 0

    def test_counts_dispersed(self):
        """Counts Dispersed markers."""
        state = make_state()
        set_tribe_dispersed(state, TRIBE_MENAPII)
        set_tribe_dispersed(state, TRIBE_MORINI)
        assert count_dispersed_on_map(state) == 2

    def test_counts_dispersed_gathering(self):
        """Counts Dispersed-Gathering markers too."""
        state = make_state()
        set_tribe_dispersed(state, TRIBE_MENAPII)
        state["tribes"][TRIBE_MORINI]["status"] = DISPERSED_GATHERING
        assert count_dispersed_on_map(state) == 2


class TestGetDispersibleTribes:
    """Test get_dispersible_tribes — §3.2.3."""

    def test_subdued_tribes_with_roman_control(self):
        """Returns Subdued tribes when Roman Control exists."""
        state = make_state()
        setup_roman_control(state, MORINI, auxilia=5)
        assert is_controlled_by(state, MORINI, ROMANS)
        tribes = get_dispersible_tribes(state, MORINI)
        assert TRIBE_MENAPII in tribes
        assert TRIBE_MORINI in tribes

    def test_no_roman_control_returns_empty(self):
        """No Dispersal without Roman Control — §3.2.3."""
        state = make_state()
        tribes = get_dispersible_tribes(state, MORINI)
        assert tribes == []

    def test_allied_tribes_excluded(self):
        """Allied tribes cannot be Dispersed."""
        state = make_state()
        setup_roman_control(state, MORINI, auxilia=5)
        set_tribe_allied(state, TRIBE_MENAPII, ARVERNI)
        tribes = get_dispersible_tribes(state, MORINI)
        assert TRIBE_MENAPII not in tribes
        assert TRIBE_MORINI in tribes

    def test_already_dispersed_excluded(self):
        """Already Dispersed tribes cannot be Dispersed again."""
        state = make_state()
        setup_roman_control(state, MORINI, auxilia=5)
        set_tribe_dispersed(state, TRIBE_MENAPII)
        tribes = get_dispersible_tribes(state, MORINI)
        assert TRIBE_MENAPII not in tribes
        assert TRIBE_MORINI in tribes

    def test_marker_limit_respected(self):
        """Cannot exceed MAX_DISPERSED_MARKERS (4) — §3.2.3."""
        state = make_state()
        # Disperse 4 tribes elsewhere
        set_tribe_dispersed(state, TRIBE_EBURONES)
        set_tribe_dispersed(state, TRIBE_NERVII)
        set_tribe_dispersed(state, TRIBE_BELLOVACI)
        set_tribe_dispersed(state, TRIBE_ATREBATES)
        assert count_dispersed_on_map(state) == MAX_DISPERSED_MARKERS

        setup_roman_control(state, MORINI, auxilia=5)
        tribes = get_dispersible_tribes(state, MORINI)
        assert tribes == []


# ============================================================================
# FORAGE TESTS — §3.2.3 Step 3
# ============================================================================

class TestCalculateForage:
    """Test calculate_forage — §3.2.3."""

    def test_subdued_tribes_give_resources(self):
        """+2 per Subdued tribe — §3.2.3."""
        state = make_state()
        # Morini has 2 tribes: Menapii, Morini — both Subdued by default
        forage = calculate_forage(state, MORINI, [])
        assert forage == 2 * SEIZE_RESOURCES_PER_TRIBE  # 2 * 2 = 4

    def test_roman_allied_tribes_give_resources(self):
        """Roman Allied tribes count as +2 — §3.2.3."""
        state = make_state()
        set_tribe_allied(state, TRIBE_MENAPII, ROMANS)
        forage = calculate_forage(state, MORINI, [])
        assert forage == 2 * SEIZE_RESOURCES_PER_TRIBE  # 1 Allied + 1 Subdued

    def test_non_roman_allied_excluded(self):
        """Non-Roman Allied tribes don't count — §3.2.3."""
        state = make_state()
        set_tribe_allied(state, TRIBE_MENAPII, ARVERNI)
        forage = calculate_forage(state, MORINI, [])
        # Only 1 Subdued tribe (Morini), Menapii is Arverni Allied
        assert forage == SEIZE_RESOURCES_PER_TRIBE  # 2

    def test_dispersed_tribes_excluded_from_per_tribe(self):
        """Already Dispersed tribes don't give +2 — §3.2.3."""
        state = make_state()
        set_tribe_dispersed(state, TRIBE_MENAPII)
        forage = calculate_forage(state, MORINI, [])
        # Only 1 Subdued tribe left
        assert forage == SEIZE_RESOURCES_PER_TRIBE  # 2

    def test_just_dispersed_gives_six(self):
        """+6 per Dispersed marker just placed — §3.2.3."""
        state = make_state()
        forage = calculate_forage(state, MORINI, [TRIBE_MENAPII])
        # 1 just dispersed (+6) + 1 still Subdued (+2) = 8
        assert forage == SEIZE_RESOURCES_PER_DISPERSED + SEIZE_RESOURCES_PER_TRIBE

    def test_devastated_region_zero_forage(self):
        """No Forage in Devastated Region — §3.2.3."""
        state = make_state()
        mark_devastated(state, MORINI)
        forage = calculate_forage(state, MORINI, [])
        assert forage == 0

    def test_devastated_region_zero_even_with_dispersal(self):
        """No Forage in Devastated Region even with Dispersal — §3.2.3."""
        state = make_state()
        mark_devastated(state, MORINI)
        forage = calculate_forage(state, MORINI, [TRIBE_MENAPII])
        assert forage == 0


# ============================================================================
# SEIZE EXECUTION TESTS — §3.2.3
# ============================================================================

class TestSeizeExecution:
    """Test full Seize execution — §3.2.3."""

    def test_seize_no_dispersal_forage_only(self):
        """Seize without Dispersal still does Forage — §3.2.3."""
        state = make_state()
        place_piece(state, MORINI, ROMANS, AUXILIA, 1)
        give_resources(state, ROMANS, 0)

        result = seize_in_region(state, MORINI)

        assert result["cost"] == 0
        assert result["tribes_dispersed"] == []
        # 2 Subdued tribes * 2 = 4 Resources
        assert result["forage_resources"] == 4
        assert state["resources"][ROMANS] == 4

    def test_seize_with_dispersal(self):
        """Seize with Dispersal + Forage — §3.2.3."""
        state = make_state()
        setup_roman_control(state, MORINI, auxilia=5)
        give_resources(state, ROMANS, 0)

        result = seize_in_region(
            state, MORINI, tribes_to_disperse=[TRIBE_MENAPII]
        )

        assert result["tribes_dispersed"] == [TRIBE_MENAPII]
        assert state["tribes"][TRIBE_MENAPII]["status"] == DISPERSED
        # 1 just dispersed (+6) + 1 Subdued (+2) = 8
        assert result["forage_resources"] == 8
        assert state["resources"][ROMANS] == 8

    def test_seize_dispersal_requires_roman_control(self):
        """Dispersal requires Roman Control — §3.2.3."""
        state = make_state()
        place_piece(state, MORINI, ROMANS, AUXILIA, 1)
        # Place enough enemy pieces so Romans don't have control
        place_piece(state, MORINI, ARVERNI, WARBAND, 3)
        refresh_all_control(state)
        assert not is_controlled_by(state, MORINI, ROMANS)

        # No Roman Control, but try to Disperse
        with pytest.raises(CommandError, match="Roman Control"):
            seize_in_region(
                state, MORINI, tribes_to_disperse=[TRIBE_MENAPII]
            )

    def test_seize_dispersal_marker_limit(self):
        """Cannot exceed 4 Dispersed markers — §3.2.3."""
        state = make_state()
        setup_roman_control(state, MORINI, auxilia=5)
        # Place 4 Dispersed markers elsewhere
        set_tribe_dispersed(state, TRIBE_EBURONES)
        set_tribe_dispersed(state, TRIBE_NERVII)
        set_tribe_dispersed(state, TRIBE_BELLOVACI)
        set_tribe_dispersed(state, TRIBE_ATREBATES)

        with pytest.raises(CommandError, match="max"):
            seize_in_region(
                state, MORINI, tribes_to_disperse=[TRIBE_MENAPII]
            )

    def test_seize_cannot_disperse_allied_tribe(self):
        """Cannot Disperse an Allied tribe — §3.2.3."""
        state = make_state()
        setup_roman_control(state, MORINI, auxilia=5)
        set_tribe_allied(state, TRIBE_MENAPII, ROMANS)

        with pytest.raises(CommandError, match="Ally"):
            seize_in_region(
                state, MORINI, tribes_to_disperse=[TRIBE_MENAPII]
            )

    def test_seize_cannot_disperse_already_dispersed(self):
        """Cannot Disperse an already Dispersed tribe — §3.2.3."""
        state = make_state()
        setup_roman_control(state, MORINI, auxilia=5)
        set_tribe_dispersed(state, TRIBE_MENAPII)

        with pytest.raises(CommandError, match="already Dispersed"):
            seize_in_region(
                state, MORINI, tribes_to_disperse=[TRIBE_MENAPII]
            )

    def test_seize_cannot_disperse_wrong_region_tribe(self):
        """Cannot Disperse a tribe not in the region."""
        state = make_state()
        setup_roman_control(state, MORINI, auxilia=5)

        with pytest.raises(CommandError, match="not in"):
            seize_in_region(
                state, MORINI, tribes_to_disperse=[TRIBE_TREVERI]
            )

    def test_seize_rally_opportunities_generated(self):
        """Rally opportunities generated for each dispersed tribe — §3.2.3."""
        state = make_state(seed=1)
        setup_roman_control(state, MORINI, auxilia=5)

        result = seize_in_region(
            state, MORINI, tribes_to_disperse=[TRIBE_MENAPII]
        )

        # Should have rally info for the 1 dispersed tribe
        assert len(result["rally_opportunities"]) == 1
        tribe_rally = result["rally_opportunities"][0]
        assert tribe_rally["tribe"] == TRIBE_MENAPII
        # Arverni and Belgae each roll
        assert len(tribe_rally["rolls"]) == 2
        assert tribe_rally["rolls"][0]["faction"] == ARVERNI
        assert tribe_rally["rolls"][1]["faction"] == BELGAE
        # Each roll has a value and can_rally flag
        for roll_info in tribe_rally["rolls"]:
            assert "roll" in roll_info
            assert "can_rally" in roll_info
            assert 1 <= roll_info["roll"] <= 6

    def test_seize_multiple_tribes_dispersed(self):
        """Can Disperse multiple tribes in one Seize — §3.2.3."""
        state = make_state(seed=1)
        setup_roman_control(state, MORINI, auxilia=5)
        give_resources(state, ROMANS, 0)

        result = seize_in_region(
            state, MORINI,
            tribes_to_disperse=[TRIBE_MENAPII, TRIBE_MORINI]
        )

        assert len(result["tribes_dispersed"]) == 2
        assert state["tribes"][TRIBE_MENAPII]["status"] == DISPERSED
        assert state["tribes"][TRIBE_MORINI]["status"] == DISPERSED
        # 2 just dispersed * 6 = 12 Resources
        assert result["forage_resources"] == 12
        assert state["resources"][ROMANS] == 12

    def test_seize_resources_capped(self):
        """Resources cannot exceed MAX_RESOURCES — §3.2.3."""
        state = make_state()
        setup_roman_control(state, MORINI, auxilia=5)
        give_resources(state, ROMANS, MAX_RESOURCES - 1)

        result = seize_in_region(
            state, MORINI,
            tribes_to_disperse=[TRIBE_MENAPII, TRIBE_MORINI]
        )

        assert state["resources"][ROMANS] == MAX_RESOURCES

    def test_seize_harassment_opportunities(self):
        """Harassment info returned for factions with Hidden Warbands."""
        state = make_state()
        place_piece(state, MORINI, ROMANS, AUXILIA, 3)
        place_piece(state, MORINI, ARVERNI, WARBAND, 6)  # 6 Hidden = 2 losses
        refresh_all_control(state)

        result = seize_in_region(state, MORINI)

        harassment = result["harassment_opportunities"]
        assert len(harassment) >= 1
        factions = [h[0] for h in harassment]
        assert ARVERNI in factions
        for fac, losses in harassment:
            if fac == ARVERNI:
                assert losses == 2  # 6 // 3


# ============================================================================
# HARASSMENT TESTS — §3.2.3 / §3.2.2
# ============================================================================

class TestHarassment:
    """Test Harassment calculations and execution — §3.2.2, §3.2.3."""

    def test_calculate_harassment_basic(self):
        """3 Hidden Warbands = 1 loss — §3.2.2."""
        state = make_state()
        place_piece(state, MORINI, ARVERNI, WARBAND, 3)
        assert calculate_harassment(state, MORINI, ARVERNI) == 1

    def test_calculate_harassment_six_warbands(self):
        """6 Hidden Warbands = 2 losses — §3.2.2."""
        state = make_state()
        place_piece(state, MORINI, ARVERNI, WARBAND, 6)
        assert calculate_harassment(state, MORINI, ARVERNI) == 2

    def test_calculate_harassment_two_warbands(self):
        """2 Hidden Warbands = 0 losses (needs 3)."""
        state = make_state()
        place_piece(state, MORINI, ARVERNI, WARBAND, 2)
        assert calculate_harassment(state, MORINI, ARVERNI) == 0

    def test_revealed_warbands_dont_count(self):
        """Only Hidden Warbands count for Harassment — §3.2.2."""
        state = make_state()
        place_piece(state, MORINI, ARVERNI, WARBAND, 3, piece_state=REVEALED)
        assert calculate_harassment(state, MORINI, ARVERNI) == 0

    def test_execute_harassment_remove_auxilia(self):
        """Remove Auxilia as Harassment loss — §3.2.3."""
        state = make_state()
        place_piece(state, MORINI, ROMANS, AUXILIA, 3)

        result = execute_harassment_loss(state, MORINI, "auxilia")

        assert result["removed"] == AUXILIA
        assert count_pieces(state, MORINI, ROMANS, AUXILIA) == 2

    def test_execute_harassment_remove_ally(self):
        """Remove Roman Ally as Harassment loss — §3.2.3."""
        state = make_state()
        place_piece(state, MORINI, ROMANS, ALLY, 1)
        place_piece(state, MORINI, ROMANS, AUXILIA, 1)

        result = execute_harassment_loss(state, MORINI, "ally")

        assert result["removed"] == ALLY
        assert count_pieces(state, MORINI, ROMANS, ALLY) == 0

    def test_execute_harassment_roll_success(self):
        """Roll 1-3 removes hard target — §3.2.3."""
        state = make_state(seed=1)
        place_piece(state, MORINI, ROMANS, AUXILIA, 2)
        place_piece(state, MORINI, ROMANS, LEGION, 1,
                    from_legions_track=True)

        result = execute_harassment_loss(state, MORINI, "roll")

        assert result["roll"] is not None
        assert 1 <= result["roll"] <= 6
        # Result depends on roll value
        if result["roll"] <= LOSS_ROLL_THRESHOLD:
            assert result["removed"] == "hard_target_hit"
        else:
            assert result["removed"] is None

    def test_execute_harassment_roll_no_hard_target(self):
        """Cannot roll without hard target present — §3.2.3."""
        state = make_state()
        place_piece(state, MORINI, ROMANS, AUXILIA, 2)

        with pytest.raises(CommandError, match="No Legion"):
            execute_harassment_loss(state, MORINI, "roll")

    def test_remove_hard_target_legion(self):
        """Remove Legion goes to Fallen — §1.4.1."""
        state = make_state()
        place_piece(state, MORINI, ROMANS, LEGION, 2,
                    from_legions_track=True)
        initial_fallen = state.get("fallen_legions", 0)

        remove_hard_target(state, MORINI, LEGION)

        assert count_pieces(state, MORINI, ROMANS, LEGION) == 1
        assert state["fallen_legions"] == initial_fallen + 1

    def test_remove_hard_target_fort(self):
        """Remove Fort returns to Available."""
        state = make_state()
        place_piece(state, MORINI, ROMANS, FORT, 1)

        remove_hard_target(state, MORINI, FORT)

        assert count_pieces(state, MORINI, ROMANS, FORT) == 0

    def test_get_harassment_factions(self):
        """Returns factions that can Harass."""
        state = make_state()
        place_piece(state, MORINI, ARVERNI, WARBAND, 3)
        place_piece(state, MORINI, BELGAE, WARBAND, 6)

        factions = get_harassment_factions(state, MORINI)

        faction_names = [f for f, _ in factions]
        assert ARVERNI in faction_names
        assert BELGAE in faction_names
        assert ROMANS not in faction_names

        for fac, losses in factions:
            if fac == ARVERNI:
                assert losses == 1
            elif fac == BELGAE:
                assert losses == 2


# ============================================================================
# RALLY ROLL TESTS — §3.2.3 Step 2
# ============================================================================

class TestSeizeRallyRoll:
    """Test Seize rally die rolls — §3.2.3."""

    def test_arverni_roll(self):
        """Arverni can roll for Seize Rally."""
        state = make_state(seed=1)
        result = seize_rally_roll(state, ARVERNI)
        assert result["faction"] == ARVERNI
        assert 1 <= result["roll"] <= 6
        assert result["can_rally"] == (result["roll"] <= LOSS_ROLL_THRESHOLD)

    def test_belgae_roll(self):
        """Belgae can roll for Seize Rally."""
        state = make_state(seed=1)
        result = seize_rally_roll(state, BELGAE)
        assert result["faction"] == BELGAE
        assert 1 <= result["roll"] <= 6

    def test_romans_cannot_roll(self):
        """Only Arverni and Belgae roll for Seize Rally — §3.2.3."""
        state = make_state()
        with pytest.raises(CommandError):
            seize_rally_roll(state, ROMANS)

    def test_deterministic_with_seed(self):
        """Rolls are deterministic with same seed."""
        state1 = make_state(seed=42)
        state2 = make_state(seed=42)
        r1 = seize_rally_roll(state1, ARVERNI)
        r2 = seize_rally_roll(state2, ARVERNI)
        assert r1["roll"] == r2["roll"]
