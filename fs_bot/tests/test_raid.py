"""
Tests for the Raid command.

Covers Gallic Raid (§3.3.3), Germanic Raid in Ariovistus (A3.4.3),
and Germans Phase Raid (§6.2.3) for the base game.

Reference: §3.3.3, §3.4.3, §6.2.3, A3.3.3, A3.4.3
"""

import pytest

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    # Piece types
    WARBAND, AUXILIA, FORT, CITADEL, ALLY, LEGION, SETTLEMENT,
    # Piece states
    HIDDEN, REVEALED,
    # Scenarios
    SCENARIO_PAX_GALLICA, SCENARIO_ARIOVISTUS,
    # Regions
    MORINI, NERVII, ATREBATES, TREVERI, CARNUTES, MANDUBII,
    SEQUANI, ARVERNI_REGION, SUGAMBRI, UBII, PROVINCIA, BRITANNIA,
    # Markers
    MARKER_DEVASTATED,
    # Resources
    MAX_RESOURCES,
)
from fs_bot.state.state_schema import build_initial_state
from fs_bot.board.pieces import (
    place_piece, count_pieces, count_pieces_by_state, flip_piece,
)
from fs_bot.board.control import refresh_all_control
from fs_bot.commands.raid import (
    raid_in_region,
    validate_raid_region,
    validate_raid_steal_target,
    get_valid_steal_targets,
    germans_phase_raid_region,
    get_germans_phase_raid_targets,
    CommandError,
    RAID_GAIN,
    RAID_STEAL,
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


def setup_hidden_warbands(state, region, faction, count):
    """Place Hidden Warbands in a region."""
    place_piece(state, region, faction, WARBAND, count)
    refresh_all_control(state)


def mark_devastated(state, region):
    """Mark a region as Devastated."""
    state.setdefault("markers", {}).setdefault(region, {})
    state["markers"][region][MARKER_DEVASTATED] = True


# ============================================================================
# RAID VALIDATION TESTS — §3.3.3
# ============================================================================

class TestRaidValidation:
    """Test Raid region validation — §3.3.3."""

    def test_valid_raid_region(self):
        """Faction with Hidden Warbands can Raid."""
        state = make_state()
        setup_hidden_warbands(state, MORINI, ARVERNI, 2)
        valid, reason = validate_raid_region(state, MORINI, ARVERNI)
        assert valid is True
        assert reason is None

    def test_no_hidden_warbands_rejected(self):
        """Cannot Raid without Hidden Warbands."""
        state = make_state()
        valid, reason = validate_raid_region(state, MORINI, ARVERNI)
        assert valid is False
        assert "Hidden Warbands" in reason

    def test_revealed_warbands_not_enough(self):
        """Revealed Warbands don't count — need Hidden."""
        state = make_state()
        place_piece(
            state, MORINI, ARVERNI, WARBAND, 3, piece_state=REVEALED
        )
        valid, reason = validate_raid_region(state, MORINI, ARVERNI)
        assert valid is False

    def test_romans_cannot_raid(self):
        """Romans cannot Raid — §3.2."""
        state = make_state()
        valid, reason = validate_raid_region(state, MORINI, ROMANS)
        assert valid is False
        assert "cannot Raid" in reason

    def test_germans_cannot_raid_base_game(self):
        """Germans cannot Raid as player command in base game — §3.4.3."""
        state = make_state()
        setup_hidden_warbands(state, SUGAMBRI, GERMANS, 2)
        valid, reason = validate_raid_region(state, SUGAMBRI, GERMANS)
        assert valid is False
        assert "base game" in reason

    def test_germans_can_raid_ariovistus(self):
        """Germans can Raid as player command in Ariovistus — A3.4.3."""
        state = make_state(SCENARIO_ARIOVISTUS)
        setup_hidden_warbands(state, SUGAMBRI, GERMANS, 2)
        valid, reason = validate_raid_region(state, SUGAMBRI, GERMANS)
        assert valid is True

    def test_aedui_can_raid(self):
        """Aedui can Raid — §3.3.3."""
        state = make_state()
        setup_hidden_warbands(state, MORINI, AEDUI, 1)
        valid, reason = validate_raid_region(state, MORINI, AEDUI)
        assert valid is True

    def test_belgae_can_raid(self):
        """Belgae can Raid — §3.3.3."""
        state = make_state()
        setup_hidden_warbands(state, MORINI, BELGAE, 1)
        valid, reason = validate_raid_region(state, MORINI, BELGAE)
        assert valid is True

    def test_unplayable_region_rejected(self):
        """Cannot Raid in unplayable region."""
        state = make_state(SCENARIO_ARIOVISTUS)
        # Britannia is unplayable in Ariovistus — A1.3.4
        valid, reason = validate_raid_region(state, BRITANNIA, ARVERNI)
        assert valid is False


# ============================================================================
# STEAL TARGET VALIDATION TESTS — §3.3.3
# ============================================================================

class TestRaidStealValidation:
    """Test Raid steal target validation — §3.3.3."""

    def test_valid_steal_target(self):
        """Can steal from enemy with pieces, no Citadel/Fort, and Resources."""
        state = make_state()
        place_piece(state, MORINI, ROMANS, AUXILIA, 2)
        give_resources(state, ROMANS, 5)
        valid, reason = validate_raid_steal_target(
            state, MORINI, ARVERNI, ROMANS
        )
        assert valid is True

    def test_cannot_steal_from_self(self):
        """Cannot steal from own faction."""
        state = make_state()
        setup_hidden_warbands(state, MORINI, ARVERNI, 2)
        valid, reason = validate_raid_steal_target(
            state, MORINI, ARVERNI, ARVERNI
        )
        assert valid is False
        assert "own faction" in reason

    def test_cannot_steal_from_germans_base_game(self):
        """Cannot steal from Germans in base game — §3.3.3 non-Germanic."""
        state = make_state()
        setup_hidden_warbands(state, SUGAMBRI, GERMANS, 2)
        valid, reason = validate_raid_steal_target(
            state, SUGAMBRI, ARVERNI, GERMANS
        )
        assert valid is False
        assert "non-Germanic" in reason

    def test_can_steal_from_germans_ariovistus(self):
        """Can steal from Germans in Ariovistus — A3.3.3."""
        state = make_state(SCENARIO_ARIOVISTUS)
        setup_hidden_warbands(state, SUGAMBRI, GERMANS, 2)
        give_resources(state, GERMANS, 5)
        # Place some Arverni warbands as the raiding faction
        setup_hidden_warbands(state, SUGAMBRI, ARVERNI, 1)
        valid, reason = validate_raid_steal_target(
            state, SUGAMBRI, ARVERNI, GERMANS
        )
        assert valid is True

    def test_cannot_steal_if_no_pieces(self):
        """Cannot steal from faction with no pieces in region."""
        state = make_state()
        give_resources(state, ROMANS, 5)
        valid, reason = validate_raid_steal_target(
            state, MORINI, ARVERNI, ROMANS
        )
        assert valid is False
        assert "no pieces" in reason

    def test_cannot_steal_if_citadel(self):
        """Cannot steal from faction with Citadel in region — §3.3.3."""
        state = make_state()
        place_piece(state, MORINI, BELGAE, WARBAND, 2)
        place_piece(state, MORINI, BELGAE, CITADEL, 1)
        give_resources(state, BELGAE, 5)
        valid, reason = validate_raid_steal_target(
            state, MORINI, ARVERNI, BELGAE
        )
        assert valid is False
        assert "Citadel" in reason

    def test_cannot_steal_if_fort(self):
        """Cannot steal from Romans with Fort in region — §3.3.3."""
        state = make_state()
        place_piece(state, MORINI, ROMANS, AUXILIA, 2)
        place_piece(state, MORINI, ROMANS, FORT, 1)
        give_resources(state, ROMANS, 5)
        valid, reason = validate_raid_steal_target(
            state, MORINI, ARVERNI, ROMANS
        )
        assert valid is False
        assert "Fort" in reason

    def test_cannot_steal_if_zero_resources(self):
        """Cannot steal from faction with 0 Resources."""
        state = make_state()
        place_piece(state, MORINI, ROMANS, AUXILIA, 2)
        give_resources(state, ROMANS, 0)
        valid, reason = validate_raid_steal_target(
            state, MORINI, ARVERNI, ROMANS
        )
        assert valid is False
        assert "0 Resources" in reason

    def test_settlement_does_not_block_steal(self):
        """Settlements do NOT block stealing (only Fort/Citadel do)."""
        state = make_state(SCENARIO_ARIOVISTUS)
        setup_hidden_warbands(state, SUGAMBRI, GERMANS, 2)
        place_piece(state, SUGAMBRI, GERMANS, SETTLEMENT, 1)
        give_resources(state, GERMANS, 5)
        setup_hidden_warbands(state, SUGAMBRI, ARVERNI, 1)
        valid, reason = validate_raid_steal_target(
            state, SUGAMBRI, ARVERNI, GERMANS
        )
        assert valid is True


class TestGetValidStealTargets:
    """Test get_valid_steal_targets helper."""

    def test_returns_valid_targets(self):
        """Returns only factions meeting all steal criteria."""
        state = make_state()
        place_piece(state, MORINI, ROMANS, AUXILIA, 2)
        give_resources(state, ROMANS, 5)
        place_piece(state, MORINI, BELGAE, WARBAND, 1)
        give_resources(state, BELGAE, 3)
        targets = get_valid_steal_targets(state, MORINI, ARVERNI)
        assert ROMANS in targets
        assert BELGAE in targets
        assert ARVERNI not in targets  # Self
        assert GERMANS not in targets  # Non-Germanic rule

    def test_excludes_fortified_enemies(self):
        """Excludes enemies with Fort or Citadel."""
        state = make_state()
        place_piece(state, MORINI, ROMANS, AUXILIA, 2)
        place_piece(state, MORINI, ROMANS, FORT, 1)
        give_resources(state, ROMANS, 5)
        targets = get_valid_steal_targets(state, MORINI, ARVERNI)
        assert ROMANS not in targets


# ============================================================================
# RAID EXECUTION TESTS — §3.3.3
# ============================================================================

class TestRaidExecution:
    """Test Raid execution mechanics — §3.3.3."""

    def test_raid_gain_one_warband(self):
        """Raid with 1 Warband gaining Resource."""
        state = make_state()
        setup_hidden_warbands(state, MORINI, ARVERNI, 3)
        give_resources(state, ARVERNI, 5)

        result = raid_in_region(
            state, MORINI, ARVERNI,
            [{"type": RAID_GAIN}]
        )

        assert result["warbands_flipped"] == 1
        assert result["resources_gained"] == 1
        assert result["cost"] == 0
        assert state["resources"][ARVERNI] == 6
        # Check warband was flipped
        assert count_pieces_by_state(
            state, MORINI, ARVERNI, WARBAND, HIDDEN
        ) == 2
        assert count_pieces_by_state(
            state, MORINI, ARVERNI, WARBAND, REVEALED
        ) == 1

    def test_raid_gain_two_warbands(self):
        """Raid with 2 Warbands gaining Resources."""
        state = make_state()
        setup_hidden_warbands(state, MORINI, ARVERNI, 3)
        give_resources(state, ARVERNI, 5)

        result = raid_in_region(
            state, MORINI, ARVERNI,
            [{"type": RAID_GAIN}, {"type": RAID_GAIN}]
        )

        assert result["warbands_flipped"] == 2
        assert result["resources_gained"] == 2
        assert state["resources"][ARVERNI] == 7
        assert count_pieces_by_state(
            state, MORINI, ARVERNI, WARBAND, HIDDEN
        ) == 1
        assert count_pieces_by_state(
            state, MORINI, ARVERNI, WARBAND, REVEALED
        ) == 2

    def test_raid_steal_one_resource(self):
        """Raid stealing 1 Resource from enemy."""
        state = make_state()
        setup_hidden_warbands(state, MORINI, ARVERNI, 2)
        place_piece(state, MORINI, ROMANS, AUXILIA, 2)
        give_resources(state, ARVERNI, 5)
        give_resources(state, ROMANS, 10)

        result = raid_in_region(
            state, MORINI, ARVERNI,
            [{"type": RAID_STEAL, "target": ROMANS}]
        )

        assert result["warbands_flipped"] == 1
        assert result["resources_gained"] == 1
        assert result["resources_stolen"] == {ROMANS: 1}
        assert state["resources"][ARVERNI] == 6
        assert state["resources"][ROMANS] == 9

    def test_raid_mixed_gain_and_steal(self):
        """Raid with one gain and one steal action."""
        state = make_state()
        setup_hidden_warbands(state, MORINI, ARVERNI, 3)
        place_piece(state, MORINI, ROMANS, AUXILIA, 2)
        give_resources(state, ARVERNI, 5)
        give_resources(state, ROMANS, 10)

        result = raid_in_region(
            state, MORINI, ARVERNI,
            [{"type": RAID_GAIN},
             {"type": RAID_STEAL, "target": ROMANS}]
        )

        assert result["warbands_flipped"] == 2
        assert result["resources_gained"] == 2
        assert result["resources_stolen"] == {ROMANS: 1}
        assert state["resources"][ARVERNI] == 7
        assert state["resources"][ROMANS] == 9

    def test_raid_cannot_gain_in_devastated_region(self):
        """Cannot gain Resources in Devastated Region — §3.3.3."""
        state = make_state()
        setup_hidden_warbands(state, MORINI, ARVERNI, 2)
        mark_devastated(state, MORINI)

        with pytest.raises(CommandError, match="Devastated"):
            raid_in_region(
                state, MORINI, ARVERNI,
                [{"type": RAID_GAIN}]
            )

    def test_raid_can_steal_in_devastated_region(self):
        """CAN steal Resources even in Devastated Region — §3.3.3."""
        state = make_state()
        setup_hidden_warbands(state, MORINI, ARVERNI, 2)
        place_piece(state, MORINI, ROMANS, AUXILIA, 2)
        mark_devastated(state, MORINI)
        give_resources(state, ARVERNI, 5)
        give_resources(state, ROMANS, 10)

        result = raid_in_region(
            state, MORINI, ARVERNI,
            [{"type": RAID_STEAL, "target": ROMANS}]
        )

        assert result["resources_gained"] == 1
        assert state["resources"][ROMANS] == 9

    def test_raid_max_resources_cap(self):
        """Resources cannot exceed MAX_RESOURCES (45)."""
        state = make_state()
        setup_hidden_warbands(state, MORINI, ARVERNI, 2)
        give_resources(state, ARVERNI, MAX_RESOURCES)

        result = raid_in_region(
            state, MORINI, ARVERNI,
            [{"type": RAID_GAIN}]
        )

        assert state["resources"][ARVERNI] == MAX_RESOURCES

    def test_raid_three_warbands_rejected(self):
        """Cannot flip more than 2 Warbands per Region — §3.3.3."""
        state = make_state()
        setup_hidden_warbands(state, MORINI, ARVERNI, 5)

        with pytest.raises(CommandError, match="Maximum 2"):
            raid_in_region(
                state, MORINI, ARVERNI,
                [{"type": RAID_GAIN}] * 3
            )

    def test_raid_insufficient_hidden_warbands(self):
        """Cannot flip more Warbands than available Hidden."""
        state = make_state()
        setup_hidden_warbands(state, MORINI, ARVERNI, 1)

        with pytest.raises(CommandError, match="only 1"):
            raid_in_region(
                state, MORINI, ARVERNI,
                [{"type": RAID_GAIN}, {"type": RAID_GAIN}]
            )

    def test_raid_empty_actions_rejected(self):
        """Must specify at least 1 action."""
        state = make_state()
        setup_hidden_warbands(state, MORINI, ARVERNI, 2)

        with pytest.raises(CommandError, match="at least 1"):
            raid_in_region(state, MORINI, ARVERNI, [])

    def test_raid_invalid_action_type(self):
        """Invalid action type is rejected."""
        state = make_state()
        setup_hidden_warbands(state, MORINI, ARVERNI, 2)

        with pytest.raises(CommandError, match="Unknown"):
            raid_in_region(
                state, MORINI, ARVERNI,
                [{"type": "invalid"}]
            )

    def test_raid_steal_missing_target(self):
        """Steal action without target is rejected."""
        state = make_state()
        setup_hidden_warbands(state, MORINI, ARVERNI, 2)

        with pytest.raises(CommandError, match="target"):
            raid_in_region(
                state, MORINI, ARVERNI,
                [{"type": RAID_STEAL}]
            )


# ============================================================================
# GERMANIC RAID — ARIOVISTUS (A3.4.3)
# ============================================================================

class TestGermanicRaidAriovistus:
    """Test Germanic Raid in Ariovistus — A3.4.3."""

    def test_german_raid_gains_resources(self):
        """Germans receive Resources when Raiding in Ariovistus — A3.4.3."""
        state = make_state(SCENARIO_ARIOVISTUS)
        setup_hidden_warbands(state, SUGAMBRI, GERMANS, 3)
        give_resources(state, GERMANS, 5)

        result = raid_in_region(
            state, SUGAMBRI, GERMANS,
            [{"type": RAID_GAIN}]
        )

        assert result["resources_gained"] == 1
        assert state["resources"][GERMANS] == 6

    def test_german_raid_steal_from_gallic(self):
        """Germans can steal from Gallic factions in Ariovistus."""
        state = make_state(SCENARIO_ARIOVISTUS)
        setup_hidden_warbands(state, SUGAMBRI, GERMANS, 2)
        place_piece(state, SUGAMBRI, ARVERNI, WARBAND, 2)
        give_resources(state, GERMANS, 5)
        give_resources(state, ARVERNI, 10)

        result = raid_in_region(
            state, SUGAMBRI, GERMANS,
            [{"type": RAID_STEAL, "target": ARVERNI}]
        )

        assert result["resources_gained"] == 1
        assert result["resources_stolen"] == {ARVERNI: 1}
        assert state["resources"][GERMANS] == 6
        assert state["resources"][ARVERNI] == 9


# ============================================================================
# GERMANS PHASE RAID — §6.2.3 (Base Game Only)
# ============================================================================

class TestGermansPhaseRaid:
    """Test Germans Phase Raid — §6.2.3."""

    def test_basic_germans_phase_raid(self):
        """Germans Phase Raid targets enemy factions — §6.2.3."""
        state = make_state(seed=1)
        setup_hidden_warbands(state, SUGAMBRI, GERMANS, 3)
        place_piece(state, SUGAMBRI, ARVERNI, WARBAND, 2)
        give_resources(state, ARVERNI, 5)

        result = germans_phase_raid_region(state, SUGAMBRI)

        assert result["warbands_flipped"] > 0
        # Germans don't receive Resources — §3.4.3
        # Arverni should have lost Resources
        assert state["resources"][ARVERNI] < 5

    def test_germans_phase_raid_target_loses_resources(self):
        """Target faction loses Resources — §3.4.3, §6.2.3."""
        state = make_state(seed=1)
        setup_hidden_warbands(state, SUGAMBRI, GERMANS, 2)
        place_piece(state, SUGAMBRI, ARVERNI, WARBAND, 1)
        give_resources(state, ARVERNI, 3)

        result = germans_phase_raid_region(state, SUGAMBRI)

        # Arverni lost Resources
        total_stolen = result["resources_stolen"].get(ARVERNI, 0)
        assert state["resources"][ARVERNI] == 3 - total_stolen

    def test_germans_phase_raid_stops_at_zero(self):
        """Raid only until target reaches 0 Resources — §6.2.3."""
        state = make_state(seed=1)
        setup_hidden_warbands(state, SUGAMBRI, GERMANS, 5)
        place_piece(state, SUGAMBRI, ARVERNI, WARBAND, 1)
        give_resources(state, ARVERNI, 2)

        result = germans_phase_raid_region(state, SUGAMBRI)

        assert state["resources"][ARVERNI] == 0
        # Should have flipped at most 2 warbands (limited by target resources)
        assert result["resources_stolen"].get(ARVERNI, 0) == 2

    def test_germans_phase_raid_skips_fortified(self):
        """Skip factions with Fort in region — §6.2.3 via §3.3.3."""
        state = make_state(seed=1)
        setup_hidden_warbands(state, SUGAMBRI, GERMANS, 3)
        place_piece(state, SUGAMBRI, ROMANS, AUXILIA, 2)
        place_piece(state, SUGAMBRI, ROMANS, FORT, 1)
        give_resources(state, ROMANS, 10)

        result = germans_phase_raid_region(state, SUGAMBRI)

        # Romans should NOT be targeted (Fort present)
        assert ROMANS not in result["resources_stolen"]

    def test_germans_phase_raid_skips_zero_resources(self):
        """Skip factions with 0 Resources — §6.2.3."""
        state = make_state(seed=1)
        setup_hidden_warbands(state, SUGAMBRI, GERMANS, 3)
        place_piece(state, SUGAMBRI, ARVERNI, WARBAND, 1)
        give_resources(state, ARVERNI, 0)

        result = germans_phase_raid_region(state, SUGAMBRI)

        # No targets available, no warbands flipped
        assert result["warbands_flipped"] == 0

    def test_germans_phase_raid_ariovistus_rejected(self):
        """Germans Phase Raid is base game only — §6.2.3."""
        state = make_state(SCENARIO_ARIOVISTUS)
        setup_hidden_warbands(state, SUGAMBRI, GERMANS, 3)

        with pytest.raises(CommandError, match="base game only"):
            germans_phase_raid_region(state, SUGAMBRI)

    def test_germans_phase_raid_no_hidden_warbands(self):
        """Germans Phase Raid requires Hidden Warbands."""
        state = make_state()

        with pytest.raises(CommandError, match="no Hidden Warbands"):
            germans_phase_raid_region(state, SUGAMBRI)

    def test_germans_phase_raid_multiple_targets(self):
        """Germans Phase Raid can target multiple factions in a region."""
        state = make_state(seed=100)
        setup_hidden_warbands(state, MORINI, GERMANS, 6)
        place_piece(state, MORINI, ARVERNI, WARBAND, 1)
        place_piece(state, MORINI, BELGAE, WARBAND, 1)
        give_resources(state, ARVERNI, 3)
        give_resources(state, BELGAE, 3)

        result = germans_phase_raid_region(state, MORINI)

        # Both factions should have lost some Resources
        total_stolen = sum(result["resources_stolen"].values())
        assert total_stolen > 0
        assert result["warbands_flipped"] == total_stolen


class TestGermansPhaseRaidTargets:
    """Test get_germans_phase_raid_targets — §6.2.3."""

    def test_includes_valid_targets(self):
        """Returns factions with pieces, Resources, and no Fort/Citadel."""
        state = make_state()
        place_piece(state, MORINI, ARVERNI, WARBAND, 1)
        give_resources(state, ARVERNI, 5)
        targets = get_germans_phase_raid_targets(state, MORINI)
        assert ARVERNI in targets

    def test_excludes_germans(self):
        """Germans are excluded (can't raid themselves)."""
        state = make_state()
        setup_hidden_warbands(state, SUGAMBRI, GERMANS, 2)
        targets = get_germans_phase_raid_targets(state, SUGAMBRI)
        assert GERMANS not in targets

    def test_excludes_citadel(self):
        """Factions with Citadel in region are excluded."""
        state = make_state()
        place_piece(state, MORINI, ARVERNI, WARBAND, 2)
        place_piece(state, MORINI, ARVERNI, CITADEL, 1)
        give_resources(state, ARVERNI, 5)
        targets = get_germans_phase_raid_targets(state, MORINI)
        assert ARVERNI not in targets
