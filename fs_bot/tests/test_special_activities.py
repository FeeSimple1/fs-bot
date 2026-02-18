"""
Tests for Special Activities — §4.0-§4.5, A4.0-A4.6.

Tests cover all Special Activities: Ambush, Scout, Build, Besiege,
Entreat, Devastate, Trade, Suborn, Enlist, Rampage, Settle, Intimidate.
"""

import pytest

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Leaders
    CAESAR, VERCINGETORIX, AMBIORIX, ARIOVISTUS_LEADER,
    DIVICIACUS, BODUOGNATUS, SUCCESSOR,
    # Scenarios
    SCENARIO_PAX_GALLICA, SCENARIO_ARIOVISTUS,
    # Regions
    MORINI, NERVII, ATREBATES, SUGAMBRI, UBII,
    TREVERI, CARNUTES, MANDUBII, VENETI, PICTONES,
    BITURIGES, AEDUI_REGION, SEQUANI, ARVERNI_REGION,
    BRITANNIA, PROVINCIA, CISALPINA,
    GERMANIA_REGIONS,
    # Tribes
    TRIBE_CARNUTES, TRIBE_AULERCI, TRIBE_MANDUBII, TRIBE_SENONES,
    TRIBE_LINGONES, TRIBE_BITURIGES, TRIBE_AEDUI, TRIBE_ARVERNI,
    TRIBE_HELVII, TRIBE_TREVERI, TRIBE_SEQUANI, TRIBE_HELVETII,
    TRIBE_SUEBI_SOUTH, TRIBE_UBII, TRIBE_NORI,
    TRIBE_BELLOVACI, TRIBE_ATREBATES, TRIBE_REMI,
    # Costs
    BUILD_COST_PER_FORT, BUILD_COST_PER_ALLY, ENTREAT_COST,
    SUBORN_COST_PER_ALLY, SUBORN_COST_PER_PIECE,
    SETTLE_COST,
    SUBORN_MAX_PIECES, SUBORN_MAX_ALLIES,
    ENLIST_MAX_GERMAN_PIECES_ARIOVISTUS,
    # Markers
    MARKER_DEVASTATED, MARKER_INTIMIDATED, MARKER_SCOUTED,
    # Stacking
    MAX_FORTS_PER_REGION, MAX_SETTLEMENTS_PER_REGION,
    # Control
    ROMAN_CONTROL, ARVERNI_CONTROL, GERMANIC_CONTROL, NO_CONTROL,
)
from fs_bot.state.state_schema import build_initial_state
from fs_bot.board.pieces import (
    place_piece, count_pieces, count_pieces_by_state,
    get_available, get_leader_in_region,
)
from fs_bot.board.control import refresh_all_control, is_controlled_by
from fs_bot.commands.common import CommandError

# Special Activities under test
from fs_bot.commands.sa_ambush import validate_ambush_region
from fs_bot.commands.sa_scout import scout_move, scout_reveal
from fs_bot.commands.sa_build import (
    validate_build_region, build_fort, build_subdue, build_place_ally,
)
from fs_bot.commands.sa_besiege import validate_besiege_region, get_besiege_targets
from fs_bot.commands.sa_entreat import (
    validate_entreat_region, entreat_replace_piece, entreat_replace_ally,
)
from fs_bot.commands.sa_devastate import validate_devastate_region, devastate_region
from fs_bot.commands.sa_trade import trade
from fs_bot.commands.sa_suborn import validate_suborn_region, suborn
from fs_bot.commands.sa_enlist import (
    validate_enlist_region, get_enlistable_german_pieces,
    validate_enlist_ariovistus_limit,
)
from fs_bot.commands.sa_rampage import (
    validate_rampage_region, validate_rampage_target, rampage,
)
from fs_bot.commands.sa_settle import validate_settle_region, settle
from fs_bot.commands.sa_intimidate import validate_intimidate_region, intimidate


# ============================================================================
# HELPERS
# ============================================================================

def make_state(scenario=SCENARIO_PAX_GALLICA, seed=42):
    """Create a fresh state for testing."""
    return build_initial_state(scenario, seed=seed)


def give_resources(state, faction, amount):
    """Give a faction some resources for testing."""
    state["resources"][faction] = amount


def place_hidden_warbands(state, region, faction, count):
    """Place Hidden Warbands for a faction in a region."""
    place_piece(state, region, faction, WARBAND, count, piece_state=HIDDEN)


def place_revealed_warbands(state, region, faction, count):
    """Place Revealed Warbands for a faction in a region."""
    place_piece(state, region, faction, WARBAND, count, piece_state=REVEALED)


def place_leader(state, region, faction, leader_name):
    """Place a leader on the map."""
    place_piece(state, region, faction, LEADER, leader_name=leader_name)


def set_tribe_allied(state, tribe, faction):
    """Set a tribe as allied to a faction."""
    state["tribes"][tribe]["allied_faction"] = faction
    state["tribes"][tribe]["status"] = None


def mark_devastated(state, region):
    """Mark a region as Devastated."""
    state.setdefault("markers", {}).setdefault(region, {})
    state["markers"][region][MARKER_DEVASTATED] = True


def setup_roman_control(state, region, *, legions=0, auxilia=0, forts=0):
    """Place Roman pieces to establish control, then refresh."""
    if legions > 0:
        place_piece(state, region, ROMANS, LEGION, legions,
                    from_legions_track=True)
    if auxilia > 0:
        place_piece(state, region, ROMANS, AUXILIA, auxilia,
                    piece_state=REVEALED)
    if forts > 0:
        place_piece(state, region, ROMANS, FORT, forts)
    refresh_all_control(state)


# ============================================================================
# AMBUSH TESTS — §4.3.3, §4.4.3, §4.5.3, §3.4.4, A4.3.3, A4.6.3
# ============================================================================

class TestAmbushValidation:
    """Tests for Ambush SA validation."""

    def test_arverni_ambush_more_hidden_than_defender(self):
        """§4.3.3: Need more Hidden Arverni than Hidden Defenders."""
        state = make_state()
        region = CARNUTES
        place_leader(state, region, ARVERNI, VERCINGETORIX)
        place_hidden_warbands(state, region, ARVERNI, 3)
        # Romans use Auxilia, not Warbands
        place_piece(state, region, ROMANS, AUXILIA, 2, piece_state=HIDDEN)

        valid, reason = validate_ambush_region(
            state, region, ARVERNI, ROMANS
        )
        assert valid is True

    def test_arverni_ambush_equal_hidden_fails(self):
        """§4.3.3: Equal Hidden pieces is insufficient."""
        state = make_state()
        region = CARNUTES
        place_leader(state, region, ARVERNI, VERCINGETORIX)
        place_hidden_warbands(state, region, ARVERNI, 2)
        place_hidden_warbands(state, region, AEDUI, 2)

        valid, reason = validate_ambush_region(
            state, region, ARVERNI, AEDUI
        )
        assert valid is False
        assert "need more Hidden" in reason

    def test_arverni_ambush_leader_proximity(self):
        """§4.3.3: Must be within 1 of Vercingetorix."""
        state = make_state()
        place_leader(state, ARVERNI_REGION, ARVERNI, VERCINGETORIX)
        # MORINI is far from ARVERNI_REGION
        place_hidden_warbands(state, MORINI, ARVERNI, 3)
        place_piece(state, MORINI, ROMANS, AUXILIA, 1, piece_state=HIDDEN)

        valid, reason = validate_ambush_region(
            state, MORINI, ARVERNI, ROMANS
        )
        assert valid is False
        assert "within 1 of Vercingetorix" in reason

    def test_arverni_ambush_adjacent_ok(self):
        """§4.3.3: Adjacent to Vercingetorix is valid."""
        state = make_state()
        place_leader(state, CARNUTES, ARVERNI, VERCINGETORIX)
        # MANDUBII is adjacent to CARNUTES
        place_hidden_warbands(state, MANDUBII, ARVERNI, 3)
        place_hidden_warbands(state, MANDUBII, BELGAE, 1)

        valid, reason = validate_ambush_region(
            state, MANDUBII, ARVERNI, BELGAE
        )
        assert valid is True

    def test_aedui_ambush_no_leader_needed(self):
        """§4.4.3: No Leader required for Aedui Ambush (base game)."""
        state = make_state()
        place_hidden_warbands(state, CARNUTES, AEDUI, 3)
        place_hidden_warbands(state, CARNUTES, BELGAE, 1)

        valid, reason = validate_ambush_region(
            state, CARNUTES, AEDUI, BELGAE
        )
        assert valid is True

    def test_belgae_ambush_with_ambiorix(self):
        """§4.5.3: Belgic Ambush uses Ambiorix."""
        state = make_state()
        place_leader(state, NERVII, BELGAE, AMBIORIX)
        place_hidden_warbands(state, NERVII, BELGAE, 3)
        place_piece(state, NERVII, ROMANS, AUXILIA, 1, piece_state=HIDDEN)

        valid, reason = validate_ambush_region(
            state, NERVII, BELGAE, ROMANS
        )
        assert valid is True

    def test_germans_base_no_leader_needed(self):
        """§3.4.4: Germans in base game need no leader, just hidden pieces."""
        state = make_state()
        place_hidden_warbands(state, TREVERI, GERMANS, 4)
        place_hidden_warbands(state, TREVERI, ARVERNI, 2)

        valid, reason = validate_ambush_region(
            state, TREVERI, GERMANS, ARVERNI
        )
        assert valid is True

    def test_germans_ariovistus_needs_leader(self):
        """A4.6.3: Germans in Ariovistus use Ariovistus leader."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        place_hidden_warbands(state, TREVERI, GERMANS, 4)
        place_piece(state, TREVERI, ROMANS, AUXILIA, 1, piece_state=HIDDEN)

        # No leader on map
        valid, reason = validate_ambush_region(
            state, TREVERI, GERMANS, ROMANS
        )
        assert valid is False
        assert "leader not on map" in reason

    def test_arverni_ariovistus_no_leader_needed(self):
        """A4.3.3: Arverni in Ariovistus do not need a Leader for Ambush."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        place_hidden_warbands(state, CARNUTES, ARVERNI, 3)
        place_hidden_warbands(state, CARNUTES, BELGAE, 1)

        valid, reason = validate_ambush_region(
            state, CARNUTES, ARVERNI, BELGAE
        )
        assert valid is True


# ============================================================================
# SCOUT TESTS — §4.2.2
# ============================================================================

class TestScoutMove:
    """Tests for Scout movement."""

    def test_basic_scout_movement(self):
        """§4.2.2: Move Auxilia to adjacent region."""
        state = make_state()
        place_piece(state, CARNUTES, ROMANS, AUXILIA, 3, piece_state=HIDDEN)

        result = scout_move(state, [{
            "from_region": CARNUTES,
            "to_region": MANDUBII,
            "count": 2,
            "piece_state": HIDDEN,
        }])

        assert len(result["moved"]) == 1
        assert count_pieces_by_state(
            state, CARNUTES, ROMANS, AUXILIA, HIDDEN
        ) == 1
        assert count_pieces_by_state(
            state, MANDUBII, ROMANS, AUXILIA, HIDDEN
        ) == 2

    def test_scout_movement_preserves_state(self):
        """§4.2.2: Hidden stay Hidden, Revealed stay Revealed."""
        state = make_state()
        place_piece(state, CARNUTES, ROMANS, AUXILIA, 2, piece_state=REVEALED)

        result = scout_move(state, [{
            "from_region": CARNUTES,
            "to_region": MANDUBII,
            "count": 1,
            "piece_state": REVEALED,
        }])

        assert count_pieces_by_state(
            state, MANDUBII, ROMANS, AUXILIA, REVEALED
        ) == 1

    def test_scout_movement_no_britannia(self):
        """§4.1.3: Cannot move into or out of Britannia."""
        state = make_state()
        place_piece(state, BRITANNIA, ROMANS, AUXILIA, 2, piece_state=HIDDEN)

        with pytest.raises(CommandError, match="Britannia"):
            scout_move(state, [{
                "from_region": BRITANNIA,
                "to_region": MORINI,
                "count": 1,
                "piece_state": HIDDEN,
            }])

    def test_scout_movement_not_adjacent(self):
        """§4.2.2: Must be adjacent."""
        state = make_state()
        place_piece(state, PROVINCIA, ROMANS, AUXILIA, 2, piece_state=HIDDEN)

        with pytest.raises(CommandError, match="not adjacent"):
            scout_move(state, [{
                "from_region": PROVINCIA,
                "to_region": MORINI,
                "count": 1,
                "piece_state": HIDDEN,
            }])


class TestScoutReveal:
    """Tests for Scout Reveal."""

    def test_basic_scout_reveal(self):
        """§4.2.2: Flip Auxilia to reveal Warbands with Scouted markers."""
        state = make_state()
        place_leader(state, CARNUTES, ROMANS, CAESAR)
        place_piece(state, CARNUTES, ROMANS, AUXILIA, 2, piece_state=HIDDEN)
        place_hidden_warbands(state, CARNUTES, ARVERNI, 3)

        result = scout_reveal(state, CARNUTES, 1, [
            {"faction": ARVERNI, "count": 2},
        ])

        assert result["auxilia_flipped"] == 1
        # 1 Auxilia flipped from Hidden to Revealed (2 started, 1 flipped)
        assert count_pieces_by_state(
            state, CARNUTES, ROMANS, AUXILIA, HIDDEN
        ) == 1
        assert count_pieces_by_state(
            state, CARNUTES, ROMANS, AUXILIA, REVEALED
        ) == 1
        # Warbands are now Scouted
        assert count_pieces_by_state(
            state, CARNUTES, ARVERNI, WARBAND, SCOUTED
        ) == 2
        assert count_pieces_by_state(
            state, CARNUTES, ARVERNI, WARBAND, HIDDEN
        ) == 1

    def test_scout_reveal_max_2_per_auxilia(self):
        """§4.2.2: Each Auxilia reveals up to 2 Warbands."""
        state = make_state()
        place_leader(state, CARNUTES, ROMANS, CAESAR)
        place_piece(state, CARNUTES, ROMANS, AUXILIA, 1, piece_state=HIDDEN)
        place_hidden_warbands(state, CARNUTES, BELGAE, 5)

        # Trying to reveal 3 with 1 Auxilia should fail
        with pytest.raises(CommandError, match="2 per Auxilia"):
            scout_reveal(state, CARNUTES, 1, [
                {"faction": BELGAE, "count": 3},
            ])

    def test_scout_reveal_needs_leader_proximity(self):
        """§4.2.2: Reveal requires being within 1 of Caesar."""
        state = make_state()
        place_leader(state, PROVINCIA, ROMANS, CAESAR)
        place_piece(state, MORINI, ROMANS, AUXILIA, 2, piece_state=HIDDEN)
        place_hidden_warbands(state, MORINI, BELGAE, 2)

        # MORINI is far from PROVINCIA
        with pytest.raises(CommandError, match="within 1 of Caesar"):
            scout_reveal(state, MORINI, 1, [
                {"faction": BELGAE, "count": 1},
            ])

    def test_scout_reveal_cannot_target_romans(self):
        """§4.2.2: Cannot Scout-reveal Roman pieces."""
        state = make_state()
        place_leader(state, CARNUTES, ROMANS, CAESAR)
        place_piece(state, CARNUTES, ROMANS, AUXILIA, 2, piece_state=HIDDEN)

        with pytest.raises(CommandError, match="Roman"):
            scout_reveal(state, CARNUTES, 1, [
                {"faction": ROMANS, "count": 1},
            ])


# ============================================================================
# BUILD TESTS — §4.2.1
# ============================================================================

class TestBuild:
    """Tests for Build SA."""

    def test_validate_build_region_with_ally(self):
        """§4.2.1: Region with Roman Ally is valid for Build."""
        state = make_state()
        place_leader(state, MANDUBII, ROMANS, CAESAR)
        # Place a Roman Ally at Mandubii tribe
        place_piece(state, MANDUBII, ROMANS, ALLY)
        set_tribe_allied(state, TRIBE_MANDUBII, ROMANS)

        valid, reason = validate_build_region(state, MANDUBII)
        assert valid is True

    def test_validate_build_needs_leader(self):
        """§4.2.1: Must be within 1 of Caesar."""
        state = make_state()
        place_leader(state, PROVINCIA, ROMANS, CAESAR)
        place_piece(state, MORINI, ROMANS, ALLY)

        valid, reason = validate_build_region(state, MORINI)
        assert valid is False
        assert "within 1 of Caesar" in reason

    def test_build_fort(self):
        """§4.2.1: Place a Fort, pay 2 Resources."""
        state = make_state()
        place_leader(state, MANDUBII, ROMANS, CAESAR)
        setup_roman_control(state, MANDUBII, legions=3)
        give_resources(state, ROMANS, 10)

        result = build_fort(state, MANDUBII)

        assert result["placed"] == FORT
        assert result["cost"] == BUILD_COST_PER_FORT
        assert state["resources"][ROMANS] == 10 - BUILD_COST_PER_FORT
        assert count_pieces(state, MANDUBII, ROMANS, FORT) == 1

    def test_build_fort_already_exists(self):
        """§4.2.1: Cannot place a Fort if one already there."""
        state = make_state()
        place_leader(state, MANDUBII, ROMANS, CAESAR)
        setup_roman_control(state, MANDUBII, legions=3, forts=1)
        give_resources(state, ROMANS, 10)

        with pytest.raises(CommandError, match="already has a Fort"):
            build_fort(state, MANDUBII)

    def test_build_fort_not_enough_resources(self):
        """§4.2.1: Need 2 Resources for Fort."""
        state = make_state()
        place_leader(state, MANDUBII, ROMANS, CAESAR)
        setup_roman_control(state, MANDUBII, legions=3)
        give_resources(state, ROMANS, 1)

        with pytest.raises(CommandError, match="Not enough Resources"):
            build_fort(state, MANDUBII)

    def test_build_subdue_ally(self):
        """§4.2.1: Subdue enemy Allied Tribe under Roman Control."""
        state = make_state()
        place_leader(state, MANDUBII, ROMANS, CAESAR)
        setup_roman_control(state, MANDUBII, legions=4)
        # Place an Arverni Ally
        place_piece(state, MANDUBII, ARVERNI, ALLY)
        set_tribe_allied(state, TRIBE_MANDUBII, ARVERNI)
        refresh_all_control(state)
        # Must still be Roman Control
        assert is_controlled_by(state, MANDUBII, ROMANS)
        give_resources(state, ROMANS, 10)

        result = build_subdue(state, MANDUBII, TRIBE_MANDUBII, ARVERNI)

        assert result["subdued"] == TRIBE_MANDUBII
        assert result["faction_removed"] == ARVERNI
        assert state["tribes"][TRIBE_MANDUBII]["allied_faction"] is None

    def test_build_place_ally(self):
        """§4.2.1: Place Roman Ally at Subdued Tribe."""
        state = make_state()
        place_leader(state, MANDUBII, ROMANS, CAESAR)
        setup_roman_control(state, MANDUBII, legions=4)
        give_resources(state, ROMANS, 10)

        result = build_place_ally(state, MANDUBII, TRIBE_MANDUBII)

        assert result["placed_ally_at"] == TRIBE_MANDUBII
        assert state["tribes"][TRIBE_MANDUBII]["allied_faction"] == ROMANS
        assert count_pieces(state, MANDUBII, ROMANS, ALLY) == 1

    def test_build_place_ally_restricted_tribe(self):
        """§1.4.2: Cannot place Roman Ally at Aedui [Bibracte]."""
        state = make_state()
        place_leader(state, AEDUI_REGION, ROMANS, CAESAR)
        setup_roman_control(state, AEDUI_REGION, legions=4)
        give_resources(state, ROMANS, 10)

        with pytest.raises(CommandError, match="restricted"):
            build_place_ally(state, AEDUI_REGION, TRIBE_AEDUI)


# ============================================================================
# BESIEGE TESTS — §4.2.3
# ============================================================================

class TestBesiege:
    """Tests for Besiege SA validation."""

    def test_besiege_valid_with_legion_and_citadel(self):
        """§4.2.3: Valid when Legion present and Defender has Citadel."""
        state = make_state()
        setup_roman_control(state, CARNUTES, legions=2)
        place_piece(state, CARNUTES, ARVERNI, CITADEL)

        valid, reason = validate_besiege_region(state, CARNUTES, ARVERNI)
        assert valid is True

    def test_besiege_no_legion(self):
        """§4.2.3: Requires at least one Legion."""
        state = make_state()
        place_piece(state, CARNUTES, ROMANS, AUXILIA, 3, piece_state=REVEALED)
        place_piece(state, CARNUTES, ARVERNI, CITADEL)

        valid, reason = validate_besiege_region(state, CARNUTES, ARVERNI)
        assert valid is False
        assert "Legion" in reason

    def test_besiege_no_citadel_or_ally(self):
        """§4.2.3: Defender must have Citadel or Allied Tribe."""
        state = make_state()
        setup_roman_control(state, CARNUTES, legions=2)
        place_hidden_warbands(state, CARNUTES, ARVERNI, 3)

        valid, reason = validate_besiege_region(state, CARNUTES, ARVERNI)
        assert valid is False
        assert "Citadel" in reason

    def test_besiege_targets(self):
        """§4.2.3: Get valid target types."""
        state = make_state()
        setup_roman_control(state, CARNUTES, legions=2)
        place_piece(state, CARNUTES, ARVERNI, CITADEL)
        place_piece(state, CARNUTES, ARVERNI, ALLY)

        targets = get_besiege_targets(state, CARNUTES, ARVERNI)
        assert CITADEL in targets
        assert ALLY in targets

    def test_besiege_settlement_ariovistus(self):
        """A4.2.3: Settlement is valid Besiege target in Ariovistus."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        setup_roman_control(state, TREVERI, legions=2)
        place_piece(state, TREVERI, GERMANS, SETTLEMENT)

        valid, reason = validate_besiege_region(state, TREVERI, GERMANS)
        assert valid is True

        targets = get_besiege_targets(state, TREVERI, GERMANS)
        assert SETTLEMENT in targets


# ============================================================================
# ENTREAT TESTS — §4.3.1
# ============================================================================

class TestEntreat:
    """Tests for Entreat SA."""

    def test_validate_entreat_region(self):
        """§4.3.1: Need Hidden Arverni Warband + leader proximity."""
        state = make_state()
        place_leader(state, CARNUTES, ARVERNI, VERCINGETORIX)
        place_hidden_warbands(state, CARNUTES, ARVERNI, 2)

        valid, reason = validate_entreat_region(state, CARNUTES)
        assert valid is True

    def test_entreat_not_in_ariovistus(self):
        """A4.3: Entreat not available in Ariovistus."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        place_hidden_warbands(state, CARNUTES, ARVERNI, 2)

        valid, reason = validate_entreat_region(state, CARNUTES)
        assert valid is False
        assert "Ariovistus" in reason

    def test_entreat_no_hidden_warband(self):
        """§4.3.1: Need Hidden Arverni Warband."""
        state = make_state()
        place_leader(state, CARNUTES, ARVERNI, VERCINGETORIX)
        place_revealed_warbands(state, CARNUTES, ARVERNI, 2)

        valid, reason = validate_entreat_region(state, CARNUTES)
        assert valid is False
        assert "Hidden Arverni Warband" in reason

    def test_entreat_replace_warband(self):
        """§4.3.1: Replace enemy Warband with Arverni Warband."""
        state = make_state()
        place_leader(state, CARNUTES, ARVERNI, VERCINGETORIX)
        place_hidden_warbands(state, CARNUTES, ARVERNI, 2)
        place_hidden_warbands(state, CARNUTES, BELGAE, 3)
        give_resources(state, ARVERNI, 10)

        result = entreat_replace_piece(
            state, CARNUTES, BELGAE, WARBAND, HIDDEN
        )

        assert result["target_removed"] == (BELGAE, WARBAND)
        assert result["arverni_placed"] is True
        assert result["cost"] == ENTREAT_COST
        # Belgae lost 1, Arverni gained 1
        assert count_pieces(state, CARNUTES, BELGAE, WARBAND) == 2
        # Arverni had 2 + 1 placed = 3
        assert count_pieces(state, CARNUTES, ARVERNI, WARBAND) == 3

    def test_entreat_replace_auxilia(self):
        """§4.3.1: Replace enemy Auxilia with Arverni Warband."""
        state = make_state()
        place_leader(state, CARNUTES, ARVERNI, VERCINGETORIX)
        place_hidden_warbands(state, CARNUTES, ARVERNI, 1)
        place_piece(state, CARNUTES, ROMANS, AUXILIA, 2, piece_state=HIDDEN)
        give_resources(state, ARVERNI, 5)

        result = entreat_replace_piece(
            state, CARNUTES, ROMANS, AUXILIA, HIDDEN
        )

        assert result["target_removed"] == (ROMANS, AUXILIA)
        assert result["arverni_placed"] is True

    def test_entreat_replace_ally(self):
        """§4.3.1: Replace enemy Ally in Arverni-Controlled region."""
        state = make_state()
        place_leader(state, MANDUBII, ARVERNI, VERCINGETORIX)
        place_hidden_warbands(state, MANDUBII, ARVERNI, 8)
        place_piece(state, MANDUBII, BELGAE, ALLY)
        set_tribe_allied(state, TRIBE_MANDUBII, BELGAE)
        refresh_all_control(state)
        assert is_controlled_by(state, MANDUBII, ARVERNI)
        give_resources(state, ARVERNI, 10)

        result = entreat_replace_ally(
            state, MANDUBII, BELGAE, TRIBE_MANDUBII
        )

        assert result["target_removed"] == (BELGAE, TRIBE_MANDUBII)
        assert result["arverni_placed"] is True
        assert state["tribes"][TRIBE_MANDUBII]["allied_faction"] == ARVERNI


# ============================================================================
# DEVASTATE TESTS — §4.3.2
# ============================================================================

class TestDevastate:
    """Tests for Devastate SA."""

    def test_validate_devastate_region(self):
        """§4.3.2: Need Arverni Control + leader proximity."""
        state = make_state()
        place_leader(state, CARNUTES, ARVERNI, VERCINGETORIX)
        place_hidden_warbands(state, CARNUTES, ARVERNI, 10)
        refresh_all_control(state)
        assert is_controlled_by(state, CARNUTES, ARVERNI)

        valid, reason = validate_devastate_region(state, CARNUTES)
        assert valid is True

    def test_devastate_not_in_ariovistus(self):
        """A4.3: Devastate not available in Ariovistus."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        valid, reason = validate_devastate_region(state, CARNUTES)
        assert valid is False
        assert "Ariovistus" in reason

    def test_devastate_no_control(self):
        """§4.3.2: Must be Arverni Controlled."""
        state = make_state()
        place_leader(state, CARNUTES, ARVERNI, VERCINGETORIX)
        place_hidden_warbands(state, CARNUTES, ARVERNI, 2)
        setup_roman_control(state, CARNUTES, legions=3)

        valid, reason = validate_devastate_region(state, CARNUTES)
        assert valid is False
        assert "Arverni Controlled" in reason

    def test_devastate_removes_pieces(self):
        """§4.3.2: Arverni remove 1/4 Warbands, others remove 1/3."""
        state = make_state()
        place_leader(state, CARNUTES, ARVERNI, VERCINGETORIX)
        place_hidden_warbands(state, CARNUTES, ARVERNI, 8)
        place_piece(state, CARNUTES, ROMANS, AUXILIA, 6, piece_state=REVEALED)
        refresh_all_control(state)

        result = devastate_region(state, CARNUTES)

        # Arverni: 8 Warbands, 1/4 = 2 removed → 6 left
        assert count_pieces(state, CARNUTES, ARVERNI, WARBAND) == 6
        # Romans: 6 Auxilia, 1/3 = 2 removed → 4 left
        assert count_pieces(state, CARNUTES, ROMANS, AUXILIA) == 4
        # Devastated marker placed
        assert result["devastated_placed"] is True
        assert state["markers"][CARNUTES].get(MARKER_DEVASTATED) is True

    def test_devastate_marker_already_present(self):
        """§4.3.2: Only one Devastated marker per region."""
        state = make_state()
        place_leader(state, CARNUTES, ARVERNI, VERCINGETORIX)
        place_hidden_warbands(state, CARNUTES, ARVERNI, 8)
        refresh_all_control(state)
        mark_devastated(state, CARNUTES)

        result = devastate_region(state, CARNUTES)

        # Marker was already there
        assert result["devastated_placed"] is False

    def test_devastate_round_down(self):
        """§4.3.2: Round fractions down."""
        state = make_state()
        place_leader(state, CARNUTES, ARVERNI, VERCINGETORIX)
        place_hidden_warbands(state, CARNUTES, ARVERNI, 5)
        # 5 Warbands, 1/4 = 1.25 → 1 removed
        place_piece(state, CARNUTES, ROMANS, AUXILIA, 2, piece_state=REVEALED)
        # 2 Auxilia, 1/3 = 0.66 → 0 removed
        refresh_all_control(state)

        result = devastate_region(state, CARNUTES)

        assert count_pieces(state, CARNUTES, ARVERNI, WARBAND) == 4
        assert count_pieces(state, CARNUTES, ROMANS, AUXILIA) == 2


# ============================================================================
# TRADE TESTS — §4.4.1
# ============================================================================

class TestTrade:
    """Tests for Trade SA."""

    def test_trade_basic_without_roman_agreement(self):
        """§4.4.1: +1 per Aedui Ally/Citadel on Supply Line."""
        state = make_state()
        # Set up supply line: AEDUI_REGION → PROVINCIA → Cisalpina
        # Place Roman pieces for supply line to work
        setup_roman_control(state, PROVINCIA, legions=2)
        # Place Aedui Ally
        place_piece(state, AEDUI_REGION, AEDUI, ALLY)
        set_tribe_allied(state, TRIBE_AEDUI, AEDUI)
        give_resources(state, AEDUI, 0)

        result = trade(state, roman_agreed=False)

        # Should gain at least 1 resource for Aedui Ally
        assert result["resources_gained"] >= 1

    def test_trade_with_roman_agreement(self):
        """§4.4.1: +2 per item if Romans agree."""
        state = make_state()
        setup_roman_control(state, PROVINCIA, legions=2)
        place_piece(state, AEDUI_REGION, AEDUI, ALLY)
        set_tribe_allied(state, TRIBE_AEDUI, AEDUI)
        give_resources(state, AEDUI, 0)

        result = trade(state, roman_agreed=True)

        # Each item worth 2 instead of 1
        assert result["resources_gained"] >= 2

    def test_trade_no_qualifying_items(self):
        """§4.4.1: No resources without Aedui Allies/Citadels on line."""
        state = make_state()
        # No Aedui pieces on map at all — no qualifying items
        give_resources(state, AEDUI, 0)

        result = trade(state, roman_agreed=False)

        assert result["resources_gained"] == 0
        assert len(result["per_item"]) == 0


# ============================================================================
# SUBORN TESTS — §4.4.2
# ============================================================================

class TestSuborn:
    """Tests for Suborn SA."""

    def test_validate_suborn_region(self):
        """§4.4.2: Need Hidden Aedui Warband."""
        state = make_state()
        place_hidden_warbands(state, CARNUTES, AEDUI, 2)

        valid, reason = validate_suborn_region(state, CARNUTES)
        assert valid is True

    def test_validate_suborn_no_hidden_warband(self):
        """§4.4.2: Fails without Hidden Aedui Warband."""
        state = make_state()
        place_revealed_warbands(state, CARNUTES, AEDUI, 2)

        valid, reason = validate_suborn_region(state, CARNUTES)
        assert valid is False
        assert "Hidden Aedui Warband" in reason

    def test_suborn_remove_and_place(self):
        """§4.4.2: Remove enemy piece and place own piece."""
        state = make_state()
        place_hidden_warbands(state, CARNUTES, AEDUI, 2)
        place_hidden_warbands(state, CARNUTES, BELGAE, 3)
        give_resources(state, AEDUI, 10)

        result = suborn(state, CARNUTES, [
            {"action": "remove", "faction": BELGAE, "piece_type": WARBAND},
            {"action": "place", "faction": AEDUI, "piece_type": WARBAND},
        ])

        assert len(result["removed"]) == 1
        assert len(result["placed"]) == 1
        # 1 per Warband remove + 1 per Warband place = 2
        assert result["cost"] == 2

    def test_suborn_max_pieces(self):
        """§4.4.2: Max 3 pieces total."""
        state = make_state()
        place_hidden_warbands(state, CARNUTES, AEDUI, 2)
        place_hidden_warbands(state, CARNUTES, BELGAE, 5)
        give_resources(state, AEDUI, 20)

        with pytest.raises(CommandError, match="at most 3"):
            suborn(state, CARNUTES, [
                {"action": "remove", "faction": BELGAE, "piece_type": WARBAND},
                {"action": "remove", "faction": BELGAE, "piece_type": WARBAND},
                {"action": "remove", "faction": BELGAE, "piece_type": WARBAND},
                {"action": "remove", "faction": BELGAE, "piece_type": WARBAND},
            ])

    def test_suborn_max_allies(self):
        """§4.4.2: Max 1 Allied Tribe operation."""
        state = make_state()
        place_hidden_warbands(state, CARNUTES, AEDUI, 2)
        give_resources(state, AEDUI, 20)

        with pytest.raises(CommandError, match="at most 1 Ally"):
            suborn(state, CARNUTES, [
                {"action": "place", "faction": AEDUI, "piece_type": ALLY,
                 "tribe": TRIBE_CARNUTES},
                {"action": "place", "faction": AEDUI, "piece_type": ALLY,
                 "tribe": TRIBE_AULERCI},
            ])

    def test_suborn_ally_at_restricted_tribe(self):
        """§1.4.2: Cannot place wrong faction at restricted tribe."""
        state = make_state()
        place_hidden_warbands(state, AEDUI_REGION, AEDUI, 2)
        give_resources(state, AEDUI, 20)

        with pytest.raises(CommandError, match="restricted"):
            suborn(state, AEDUI_REGION, [
                {"action": "place", "faction": BELGAE, "piece_type": ALLY,
                 "tribe": TRIBE_AEDUI},
            ])

    def test_suborn_not_enough_resources(self):
        """§4.4.2: Must pay 2 per Ally, 1 per Warband/Auxilia."""
        state = make_state()
        place_hidden_warbands(state, CARNUTES, AEDUI, 2)
        place_hidden_warbands(state, CARNUTES, BELGAE, 3)
        give_resources(state, AEDUI, 0)

        with pytest.raises(CommandError, match="Not enough Resources"):
            suborn(state, CARNUTES, [
                {"action": "remove", "faction": BELGAE, "piece_type": WARBAND},
            ])


# ============================================================================
# ENLIST TESTS — §4.5.1
# ============================================================================

class TestEnlist:
    """Tests for Enlist SA."""

    def test_validate_enlist_in_germania(self):
        """§4.5.1: Region in Germania is valid."""
        state = make_state()
        place_leader(state, SUGAMBRI, BELGAE, AMBIORIX)

        valid, reason = validate_enlist_region(state, SUGAMBRI)
        assert valid is True

    def test_validate_enlist_adjacent_to_germania(self):
        """§4.5.1: Region adjacent to Germania is valid."""
        state = make_state()
        place_leader(state, TREVERI, BELGAE, AMBIORIX)
        # TREVERI is adjacent to SUGAMBRI

        valid, reason = validate_enlist_region(state, TREVERI)
        assert valid is True

    def test_validate_enlist_far_with_german_pieces(self):
        """§4.5.1: Far region with Germanic pieces is valid."""
        state = make_state()
        place_leader(state, CARNUTES, BELGAE, AMBIORIX)
        place_hidden_warbands(state, CARNUTES, GERMANS, 2)

        valid, reason = validate_enlist_region(state, CARNUTES)
        assert valid is True

    def test_validate_enlist_no_leader(self):
        """§4.5.1: Need leader on map."""
        state = make_state()
        place_hidden_warbands(state, SUGAMBRI, GERMANS, 3)

        valid, reason = validate_enlist_region(state, SUGAMBRI)
        assert valid is False
        assert "leader not on map" in reason

    def test_enlistable_count(self):
        """Count Germanic Warbands available for Enlist."""
        state = make_state()
        place_hidden_warbands(state, TREVERI, GERMANS, 3)
        place_revealed_warbands(state, TREVERI, GERMANS, 2)

        count = get_enlistable_german_pieces(state, TREVERI)
        assert count == 5

    def test_enlist_ariovistus_limit(self):
        """A4.5.1: Max 4 Germanic pieces in Ariovistus."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)

        valid, reason = validate_enlist_ariovistus_limit(state, 4)
        assert valid is True

        valid, reason = validate_enlist_ariovistus_limit(state, 5)
        assert valid is False
        assert "at most 4" in reason

    def test_enlist_ariovistus_no_ariovistus_region(self):
        """A4.5.1: Cannot select Region containing Ariovistus."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        place_leader(state, TREVERI, BELGAE, BODUOGNATUS)
        place_leader(state, TREVERI, GERMANS, ARIOVISTUS_LEADER)

        valid, reason = validate_enlist_region(state, TREVERI)
        assert valid is False
        assert "Ariovistus" in reason


# ============================================================================
# RAMPAGE TESTS — §4.5.2
# ============================================================================

class TestRampage:
    """Tests for Rampage SA."""

    def test_validate_rampage_region(self):
        """§4.5.2: Need Hidden Belgic Warbands + leader proximity."""
        state = make_state()
        place_leader(state, NERVII, BELGAE, AMBIORIX)
        place_hidden_warbands(state, NERVII, BELGAE, 3)

        valid, reason = validate_rampage_region(state, NERVII)
        assert valid is True

    def test_validate_rampage_no_hidden_warbands(self):
        """§4.5.2: Need Hidden Belgic Warbands."""
        state = make_state()
        place_leader(state, NERVII, BELGAE, AMBIORIX)
        place_revealed_warbands(state, NERVII, BELGAE, 3)

        valid, reason = validate_rampage_region(state, NERVII)
        assert valid is False
        assert "Hidden Belgic Warbands" in reason

    def test_validate_rampage_target_no_germans(self):
        """§4.5.2: Cannot target Germans."""
        state = make_state()
        valid, reason = validate_rampage_target(state, NERVII, GERMANS)
        assert valid is False
        assert "Germans" in reason

    def test_validate_rampage_target_with_leader(self):
        """§4.5.2: Cannot target faction with Leader in region."""
        state = make_state()
        place_leader(state, NERVII, ROMANS, CAESAR)

        valid, reason = validate_rampage_target(state, NERVII, ROMANS)
        assert valid is False
        assert "Leader" in reason

    def test_validate_rampage_target_with_fort(self):
        """§4.5.2: Cannot target faction with Fort in region."""
        state = make_state()
        place_piece(state, NERVII, ROMANS, FORT)

        valid, reason = validate_rampage_target(state, NERVII, ROMANS)
        assert valid is False
        assert "Fort" in reason

    def test_rampage_remove(self):
        """§4.5.2: Flip Warbands to remove enemy pieces."""
        state = make_state()
        place_leader(state, NERVII, BELGAE, AMBIORIX)
        place_hidden_warbands(state, NERVII, BELGAE, 3)
        place_piece(state, NERVII, ROMANS, AUXILIA, 3, piece_state=REVEALED)

        result = rampage(state, NERVII, ROMANS, 2, [
            {"action": "remove", "piece_type": AUXILIA,
             "piece_state": REVEALED},
            {"action": "remove", "piece_type": AUXILIA,
             "piece_state": REVEALED},
        ])

        assert result["warbands_flipped"] == 2
        # 2 Belgic Warbands flipped Hidden→Revealed
        assert count_pieces_by_state(
            state, NERVII, BELGAE, WARBAND, HIDDEN
        ) == 1
        assert count_pieces_by_state(
            state, NERVII, BELGAE, WARBAND, REVEALED
        ) == 2
        # 2 Roman Auxilia removed
        assert count_pieces(state, NERVII, ROMANS, AUXILIA) == 1

    def test_rampage_retreat(self):
        """§4.5.2: Target can Retreat pieces."""
        state = make_state()
        place_leader(state, NERVII, BELGAE, AMBIORIX)
        place_hidden_warbands(state, NERVII, BELGAE, 2)
        place_piece(state, NERVII, ROMANS, AUXILIA, 2, piece_state=REVEALED)

        result = rampage(state, NERVII, ROMANS, 1, [
            {"action": "retreat", "piece_type": AUXILIA,
             "piece_state": REVEALED, "retreat_region": ATREBATES},
        ])

        assert len(result["target_retreated"]) == 1
        assert count_pieces(state, NERVII, ROMANS, AUXILIA) == 1
        assert count_pieces(state, ATREBATES, ROMANS, AUXILIA) == 1

    def test_rampage_arverni_no_retreat_ariovistus(self):
        """A4.5 NOTE: Arverni removed rather than Retreating in Ariovistus."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        place_leader(state, NERVII, BELGAE, BODUOGNATUS)
        place_hidden_warbands(state, NERVII, BELGAE, 2)
        place_hidden_warbands(state, NERVII, ARVERNI, 2)

        with pytest.raises(CommandError, match="cannot Retreat"):
            rampage(state, NERVII, ARVERNI, 1, [
                {"action": "retreat", "piece_type": WARBAND,
                 "piece_state": HIDDEN, "retreat_region": ATREBATES},
            ])


# ============================================================================
# SETTLE TESTS — A4.6.1
# ============================================================================

class TestSettle:
    """Tests for Settle SA (Ariovistus only)."""

    def test_settle_not_in_base(self):
        """A4.6.1: Settle only in Ariovistus."""
        state = make_state()
        valid, reason = validate_settle_region(state, TREVERI)
        assert valid is False
        assert "Ariovistus" in reason

    def test_validate_settle_region(self):
        """A4.6.1: Outside Germania, adjacent to Germania, Germanic Control,
        within 1 of Ariovistus."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        place_leader(state, TREVERI, GERMANS, ARIOVISTUS_LEADER)
        place_hidden_warbands(state, TREVERI, GERMANS, 6)
        refresh_all_control(state)
        assert is_controlled_by(state, TREVERI, GERMANS)

        valid, reason = validate_settle_region(state, TREVERI)
        assert valid is True

    def test_validate_settle_in_germania(self):
        """A4.6.1: Must be outside Germania."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        place_leader(state, SUGAMBRI, GERMANS, ARIOVISTUS_LEADER)
        place_hidden_warbands(state, SUGAMBRI, GERMANS, 6)
        refresh_all_control(state)

        valid, reason = validate_settle_region(state, SUGAMBRI)
        assert valid is False
        assert "outside Germania" in reason

    def test_validate_settle_no_german_control(self):
        """A4.6.1: Must be under Germanic Control."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        place_leader(state, TREVERI, GERMANS, ARIOVISTUS_LEADER)
        # Not enough to control
        place_hidden_warbands(state, TREVERI, GERMANS, 1)
        setup_roman_control(state, TREVERI, legions=3)

        valid, reason = validate_settle_region(state, TREVERI)
        assert valid is False
        assert "Germanic Control" in reason

    def test_settle_places_settlement(self):
        """A4.6.1: Place Settlement, pay 2 Resources."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        place_leader(state, TREVERI, GERMANS, ARIOVISTUS_LEADER)
        place_hidden_warbands(state, TREVERI, GERMANS, 6)
        refresh_all_control(state)
        give_resources(state, GERMANS, 10)

        result = settle(state, TREVERI)

        assert result["placed"] == SETTLEMENT
        assert result["cost"] == SETTLE_COST
        assert state["resources"][GERMANS] == 10 - SETTLE_COST
        assert count_pieces(state, TREVERI, GERMANS, SETTLEMENT) == 1

    def test_settle_devastated_double_cost(self):
        """A4.6.1: 4 Resources if Devastated."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        place_leader(state, TREVERI, GERMANS, ARIOVISTUS_LEADER)
        place_hidden_warbands(state, TREVERI, GERMANS, 6)
        refresh_all_control(state)
        mark_devastated(state, TREVERI)
        give_resources(state, GERMANS, 10)

        result = settle(state, TREVERI)

        assert result["cost"] == SETTLE_COST * 2

    def test_settle_not_enough_resources(self):
        """A4.6.1: Need enough Resources."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        place_leader(state, TREVERI, GERMANS, ARIOVISTUS_LEADER)
        place_hidden_warbands(state, TREVERI, GERMANS, 6)
        refresh_all_control(state)
        give_resources(state, GERMANS, 1)

        with pytest.raises(CommandError, match="Not enough Resources"):
            settle(state, TREVERI)

    def test_settle_chain_adjacency(self):
        """A4.6.1 NOTE: New Settlement qualifies adjacent region."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        place_leader(state, TREVERI, GERMANS, ARIOVISTUS_LEADER)
        place_hidden_warbands(state, TREVERI, GERMANS, 6)
        # Place a settlement in TREVERI first
        place_piece(state, TREVERI, GERMANS, SETTLEMENT)
        # MANDUBII is adjacent to TREVERI but not to Germania
        place_hidden_warbands(state, MANDUBII, GERMANS, 6)
        refresh_all_control(state)

        # MANDUBII adj to TREVERI which has a Settlement
        valid, reason = validate_settle_region(state, MANDUBII)
        assert valid is True


# ============================================================================
# INTIMIDATE TESTS — A4.6.2
# ============================================================================

class TestIntimidate:
    """Tests for Intimidate SA (Ariovistus only)."""

    def test_intimidate_not_in_base(self):
        """A4.6.2: Intimidate only in Ariovistus."""
        state = make_state()
        valid, reason = validate_intimidate_region(state, TREVERI)
        assert valid is False
        assert "Ariovistus" in reason

    def test_validate_with_ariovistus_present(self):
        """A4.6.2: Valid if Ariovistus is in the region."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        place_leader(state, TREVERI, GERMANS, ARIOVISTUS_LEADER)

        valid, reason = validate_intimidate_region(state, TREVERI)
        assert valid is True

    def test_validate_german_control_within_leader(self):
        """A4.6.2: Germanic Control + within 1 of Ariovistus."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        place_leader(state, TREVERI, GERMANS, ARIOVISTUS_LEADER)
        # MANDUBII is adjacent to TREVERI
        place_hidden_warbands(state, MANDUBII, GERMANS, 6)
        refresh_all_control(state)

        valid, reason = validate_intimidate_region(state, MANDUBII)
        assert valid is True

    def test_intimidate_execution(self):
        """A4.6.2: Flip Warbands, place marker, remove enemy pieces."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        place_leader(state, TREVERI, GERMANS, ARIOVISTUS_LEADER)
        place_hidden_warbands(state, TREVERI, GERMANS, 4)
        place_hidden_warbands(state, TREVERI, ARVERNI, 3)
        refresh_all_control(state)

        result = intimidate(state, TREVERI, 2, ARVERNI, [
            (WARBAND, HIDDEN),
            (WARBAND, HIDDEN),
        ])

        assert result["warbands_flipped"] == 2
        assert result["intimidated_placed"] is True
        assert state["markers"][TREVERI].get(MARKER_INTIMIDATED) is True
        # 2 Germanic Warbands flipped
        assert count_pieces_by_state(
            state, TREVERI, GERMANS, WARBAND, HIDDEN
        ) == 2
        assert count_pieces_by_state(
            state, TREVERI, GERMANS, WARBAND, REVEALED
        ) == 2
        # 2 Arverni Warbands removed
        assert count_pieces(state, TREVERI, ARVERNI, WARBAND) == 1

    def test_intimidate_cannot_target_own_faction(self):
        """A4.6.2: Cannot Intimidate own faction."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        place_leader(state, TREVERI, GERMANS, ARIOVISTUS_LEADER)
        place_hidden_warbands(state, TREVERI, GERMANS, 4)

        with pytest.raises(CommandError, match="own faction"):
            intimidate(state, TREVERI, 1, GERMANS, [(WARBAND, HIDDEN)])

    def test_intimidate_target_has_leader(self):
        """A4.6.2: Cannot target faction with Leader in region."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        place_leader(state, TREVERI, GERMANS, ARIOVISTUS_LEADER)
        place_hidden_warbands(state, TREVERI, GERMANS, 4)
        place_leader(state, TREVERI, ROMANS, CAESAR)

        with pytest.raises(CommandError, match="Leader"):
            intimidate(state, TREVERI, 1, ROMANS, [(AUXILIA, HIDDEN)])

    def test_intimidate_flip_limit(self):
        """A4.6.2: Must flip 1 or 2 Warbands."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        place_leader(state, TREVERI, GERMANS, ARIOVISTUS_LEADER)
        place_hidden_warbands(state, TREVERI, GERMANS, 4)
        place_hidden_warbands(state, TREVERI, ARVERNI, 4)

        with pytest.raises(CommandError, match="1 or 2"):
            intimidate(state, TREVERI, 3, ARVERNI, [
                (WARBAND, HIDDEN),
                (WARBAND, HIDDEN),
                (WARBAND, HIDDEN),
            ])

    def test_intimidate_marker_already_present(self):
        """A4.6.2: Only one Intimidated marker per region."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        place_leader(state, TREVERI, GERMANS, ARIOVISTUS_LEADER)
        place_hidden_warbands(state, TREVERI, GERMANS, 4)
        place_hidden_warbands(state, TREVERI, ARVERNI, 4)
        # Pre-place marker
        state.setdefault("markers", {}).setdefault(TREVERI, {})
        state["markers"][TREVERI][MARKER_INTIMIDATED] = True
        refresh_all_control(state)

        result = intimidate(state, TREVERI, 1, ARVERNI, [
            (WARBAND, HIDDEN),
        ])

        # Marker already there — not placed again
        assert result["intimidated_placed"] is False


# ============================================================================
# SCENARIO ISOLATION TESTS
# ============================================================================

class TestScenarioIsolation:
    """Verify SAs respect scenario boundaries."""

    def test_entreat_base_only(self):
        """§4.3.1/A4.3: Entreat only in base game."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        place_hidden_warbands(state, CARNUTES, ARVERNI, 2)

        valid, reason = validate_entreat_region(state, CARNUTES)
        assert valid is False

    def test_devastate_base_only(self):
        """§4.3.2/A4.3: Devastate only in base game."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        valid, reason = validate_devastate_region(state, CARNUTES)
        assert valid is False

    def test_settle_ariovistus_only(self):
        """A4.6.1: Settle only in Ariovistus."""
        state = make_state()
        valid, reason = validate_settle_region(state, TREVERI)
        assert valid is False

    def test_intimidate_ariovistus_only(self):
        """A4.6.2: Intimidate only in Ariovistus."""
        state = make_state()
        valid, reason = validate_intimidate_region(state, TREVERI)
        assert valid is False

    def test_aedui_ambush_diviciacus_ariovistus(self):
        """A4.4: With Diviciacus on map, Suborn needs proximity."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        place_leader(state, AEDUI_REGION, AEDUI, DIVICIACUS)
        place_hidden_warbands(state, MORINI, AEDUI, 3)

        # MORINI is far from AEDUI_REGION
        valid, reason = validate_suborn_region(state, MORINI)
        assert valid is False
        assert "Diviciacus" in reason

    def test_enlist_ariovistus_no_ariovistus_region(self):
        """A4.5.1: Cannot Enlist in Region with Ariovistus."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        place_leader(state, TREVERI, BELGAE, BODUOGNATUS)
        place_leader(state, TREVERI, GERMANS, ARIOVISTUS_LEADER)

        valid, reason = validate_enlist_region(state, TREVERI)
        assert valid is False
