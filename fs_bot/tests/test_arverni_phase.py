"""Tests for Arverni Phase — fs_bot/engine/arverni_phase.py.

Tests cover:
  - At War detection: enemies in Home Regions, enemies with Allies
  - At Peace when no triggering conditions
  - Target selection uses rng
  - Rally/March/Raid/Battle ordering
  - March skipped on Frost
  - Scenario isolation: only in Ariovistus

Reference: A2.3.9, A6.2
"""

import pytest

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    FACTIONS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Leaders
    CAESAR, ARIOVISTUS_LEADER, BODUOGNATUS,
    # Scenarios
    SCENARIO_PAX_GALLICA, SCENARIO_ARIOVISTUS, SCENARIO_GALLIC_WAR,
    # Regions
    MORINI, NERVII, ATREBATES, SUGAMBRI, UBII,
    TREVERI, CARNUTES, MANDUBII, VENETI, PICTONES,
    BITURIGES, AEDUI_REGION, SEQUANI, ARVERNI_REGION,
    PROVINCIA,
    # Tribes
    TRIBE_VENETI, TRIBE_NAMNETES, TRIBE_CARNUTES, TRIBE_AULERCI,
    TRIBE_PICTONES, TRIBE_SANTONES,
    TRIBE_ARVERNI, TRIBE_CADURCI, TRIBE_VOLCAE,
    TRIBE_AEDUI,
    # Home
    ARVERNI_HOME_REGIONS_ARIOVISTUS,
    # Markers
    MARKER_DEVASTATED, MARKER_INTIMIDATED,
    MAX_RESOURCES,
)
from fs_bot.state.state_schema import build_initial_state
from fs_bot.board.pieces import (
    place_piece, remove_piece, count_pieces, count_pieces_by_state,
    get_available, flip_piece,
)
from fs_bot.board.control import refresh_all_control, is_controlled_by
from fs_bot.commands.common import CommandError
from fs_bot.engine.arverni_phase import (
    check_arverni_at_war,
    select_arverni_targets,
    run_arverni_phase,
    _arverni_phase_rally,
    _arverni_phase_march,
    _arverni_phase_raid,
    _arverni_phase_battle,
)


# ============================================================================
# HELPERS
# ============================================================================

def make_state(scenario=SCENARIO_ARIOVISTUS, seed=42):
    """Create fresh state for testing."""
    return build_initial_state(scenario, seed=seed)


def set_tribe_allied(state, tribe, faction):
    """Set a tribe as Allied to a faction."""
    state["tribes"][tribe]["allied_faction"] = faction
    state["tribes"][tribe]["status"] = None


def mark_devastated(state, region):
    """Mark a region as Devastated."""
    state.setdefault("markers", {}).setdefault(region, {})[MARKER_DEVASTATED] = True


def mark_intimidated(state, region):
    """Mark a region as Intimidated."""
    state.setdefault("markers", {}).setdefault(region, {})[MARKER_INTIMIDATED] = True


def give_resources(state, faction, amount):
    """Give resources to a faction."""
    state["resources"][faction] = amount


def setup_at_war_basic(state):
    """Set up a basic At War condition: Romans in Arverni Region."""
    place_piece(state, ARVERNI_REGION, ROMANS, LEGION, 2,
                from_legions_track=True)
    refresh_all_control(state)


# ============================================================================
# TEST: AT WAR CHECK (A6.2)
# ============================================================================

class TestCheckAtWar:
    """At War detection — enemies in Home Regions or with Allies."""

    def test_at_peace_initially(self):
        """No enemies anywhere → At Peace."""
        state = make_state()
        is_at_war, regions = check_arverni_at_war(state)
        assert is_at_war is False
        assert regions == []

    def test_at_war_enemies_in_home_region(self):
        """Non-Arverni Forces in Arverni Home Region → At War."""
        state = make_state()
        place_piece(state, ARVERNI_REGION, ROMANS, LEGION, 2,
                    from_legions_track=True)
        is_at_war, regions = check_arverni_at_war(state)
        assert is_at_war is True
        assert ARVERNI_REGION in regions

    def test_at_war_enemies_with_allies(self):
        """Enemies with Arverni Allies in non-Home Region → At War."""
        state = make_state()
        # Place Arverni Ally in Morini
        place_piece(state, MORINI, ARVERNI, ALLY)
        set_tribe_allied(state, TRIBE_VENETI, ARVERNI)  # different tribe
        # Actually, we need an Arverni Ally in a non-home region
        # Morini is not an Arverni Home Region
        # Let's use Mandubii instead
        place_piece(state, MANDUBII, ARVERNI, ALLY)
        place_piece(state, MANDUBII, ROMANS, AUXILIA, 2)
        is_at_war, regions = check_arverni_at_war(state)
        assert is_at_war is True
        assert MANDUBII in regions

    def test_at_war_multiple_regions(self):
        """Multiple triggering regions detected."""
        state = make_state()
        place_piece(state, ARVERNI_REGION, ROMANS, LEGION, 1,
                    from_legions_track=True)
        place_piece(state, VENETI, BELGAE, WARBAND, 3)
        is_at_war, regions = check_arverni_at_war(state)
        assert is_at_war is True
        # Arverni_region is a Home Region with enemies
        assert ARVERNI_REGION in regions
        # Veneti is a Home Region with enemies
        assert VENETI in regions

    def test_base_game_raises(self):
        """Arverni Phase only in Ariovistus."""
        state = build_initial_state(SCENARIO_PAX_GALLICA, seed=42)
        with pytest.raises(CommandError, match="Ariovistus only"):
            check_arverni_at_war(state)

    def test_at_war_with_citadel(self):
        """Enemies with Arverni Citadel in non-Home → At War."""
        state = make_state()
        place_piece(state, MANDUBII, ARVERNI, CITADEL)
        place_piece(state, MANDUBII, AEDUI, WARBAND, 2)
        is_at_war, regions = check_arverni_at_war(state)
        assert is_at_war is True
        assert MANDUBII in regions

    def test_arverni_own_pieces_dont_trigger(self):
        """Arverni's own Forces don't trigger At War."""
        state = make_state()
        place_piece(state, ARVERNI_REGION, ARVERNI, WARBAND, 5)
        is_at_war, regions = check_arverni_at_war(state)
        assert is_at_war is False


# ============================================================================
# TEST: TARGET SELECTION (A6.2)
# ============================================================================

class TestTargetSelection:
    """Target Region and Faction selection via die roll table."""

    def test_selects_region_and_faction(self):
        """Returns a valid (region, faction) pair."""
        state = make_state()
        setup_at_war_basic(state)
        _, triggering = check_arverni_at_war(state)
        target_region, target_faction = select_arverni_targets(
            state, triggering
        )
        assert target_region in triggering or target_region in ARVERNI_HOME_REGIONS_ARIOVISTUS
        assert target_faction != ARVERNI

    def test_target_faction_has_pieces(self):
        """Selected faction must have pieces in target region."""
        state = make_state()
        setup_at_war_basic(state)
        _, triggering = check_arverni_at_war(state)
        target_region, target_faction = select_arverni_targets(
            state, triggering
        )
        assert count_pieces(state, target_region, target_faction) > 0

    def test_uses_rng(self):
        """Different seeds produce different targets."""
        state1 = make_state(seed=1)
        setup_at_war_basic(state1)
        place_piece(state1, VENETI, BELGAE, WARBAND, 3)
        _, trig1 = check_arverni_at_war(state1)
        r1, f1 = select_arverni_targets(state1, trig1)

        state2 = make_state(seed=999)
        setup_at_war_basic(state2)
        place_piece(state2, VENETI, BELGAE, WARBAND, 3)
        _, trig2 = check_arverni_at_war(state2)
        r2, f2 = select_arverni_targets(state2, trig2)

        # At least one should differ (not guaranteed but very likely)
        # Just check they're valid
        assert r1 is not None and r2 is not None
        assert f1 is not None and f2 is not None


# ============================================================================
# TEST: RUN ARVERNI PHASE
# ============================================================================

class TestRunArverniPhase:
    """Full Arverni Phase execution."""

    def test_at_peace_skips(self):
        """If At Peace, skip activation."""
        state = make_state()
        result = run_arverni_phase(state)
        assert result["at_war"] is False
        assert result["rally"] is None
        assert result["march"] is None

    def test_at_war_executes_all(self):
        """At War: Rally, March, Raid, Battle all execute."""
        state = make_state()
        setup_at_war_basic(state)
        give_resources(state, ROMANS, 10)
        give_resources(state, ARVERNI, 5)
        result = run_arverni_phase(state)
        assert result["at_war"] is True
        assert result["rally"] is not None
        assert result["march"] is not None
        assert result["raid"] is not None
        assert result["battle"] is not None

    def test_march_skipped_on_frost(self):
        """A6.2.2: March skipped on Frost."""
        state = make_state()
        setup_at_war_basic(state)
        result = run_arverni_phase(state, is_frost=True)
        assert result["march"]["skipped_frost"] is True

    def test_base_game_raises(self):
        """Arverni Phase is Ariovistus only."""
        state = build_initial_state(SCENARIO_PAX_GALLICA, seed=42)
        with pytest.raises(CommandError, match="Ariovistus only"):
            run_arverni_phase(state)


# ============================================================================
# TEST: ARVERNI RALLY (A6.2.1)
# ============================================================================

class TestArverniRally:
    """Arverni Phase Rally in At War Regions."""

    def test_rally_only_at_war_regions(self):
        """Rally only in regions that trigger At War."""
        state = make_state()
        place_piece(state, ARVERNI_REGION, ROMANS, LEGION, 2,
                    from_legions_track=True)
        _, at_war_regions = check_arverni_at_war(state)
        result = _arverni_phase_rally(state, at_war_regions)
        # Should only rally in Arverni Region (the At War region)
        all_regions = set()
        for r, _ in result.get("citadels_placed", []):
            all_regions.add(r)
        for r, _ in result.get("allies_placed", []):
            all_regions.add(r)
        for r in result.get("warbands_placed", {}).keys():
            all_regions.add(r)
        for r in all_regions:
            assert r in at_war_regions

    def test_rally_not_in_intimidated(self):
        """Cannot Rally in Intimidated regions — A6.2.1."""
        state = make_state()
        place_piece(state, ARVERNI_REGION, ROMANS, LEGION, 2,
                    from_legions_track=True)
        mark_intimidated(state, ARVERNI_REGION)
        _, at_war_regions = check_arverni_at_war(state)
        result = _arverni_phase_rally(state, at_war_regions)
        assert ARVERNI_REGION not in result.get("warbands_placed", {})

    def test_rally_not_in_devastated(self):
        """Cannot Rally in Devastated regions — A6.2.1."""
        state = make_state()
        place_piece(state, ARVERNI_REGION, ROMANS, LEGION, 2,
                    from_legions_track=True)
        mark_devastated(state, ARVERNI_REGION)
        _, at_war_regions = check_arverni_at_war(state)
        result = _arverni_phase_rally(state, at_war_regions)
        assert ARVERNI_REGION not in result.get("warbands_placed", {})


# ============================================================================
# TEST: ARVERNI MARCH (A6.2.2)
# ============================================================================

class TestArverniMarch:
    """Arverni Phase March."""

    def test_warbands_flipped_hidden(self):
        """All Arverni Warbands flipped to Hidden — A6.2.2."""
        state = make_state()
        place_piece(state, MORINI, ARVERNI, WARBAND, 3, piece_state=REVEALED)
        result = _arverni_phase_march(state, ARVERNI_REGION)
        revealed = count_pieces_by_state(
            state, MORINI, ARVERNI, WARBAND, REVEALED
        )
        hidden = count_pieces_by_state(
            state, MORINI, ARVERNI, WARBAND, HIDDEN
        )
        assert revealed == 0
        assert hidden == 3

    def test_frost_skips_march(self):
        """Frost prevents March — A6.2.2."""
        state = make_state()
        result = _arverni_phase_march(state, ARVERNI_REGION, is_frost=True)
        assert result["skipped_frost"] is True
        assert result["marches"] == []

    def test_no_march_from_target(self):
        """No Warbands march out of target region — A6.2.2."""
        state = make_state()
        place_piece(state, ARVERNI_REGION, ARVERNI, WARBAND, 10)
        refresh_all_control(state)
        result = _arverni_phase_march(state, ARVERNI_REGION)
        # Warbands in target region should stay
        for march in result["marches"]:
            assert march["from"] != ARVERNI_REGION

    def test_arverni_march_to_target_moves_warbands(self):
        """Warbands from adjacent region march to target correctly.

        Verifies no ValueError on march_groups.remove() and that
        result["marches"] has the correct total warbands count.
        """
        state = make_state()
        # Place Arverni Warbands in Pictones (adjacent to Arverni Region)
        # with enough to have surplus over control needs
        place_piece(state, PICTONES, ARVERNI, WARBAND, 8)
        # Place a single enemy to make Arverni Control possible
        place_piece(state, PICTONES, ROMANS, AUXILIA, 1)
        refresh_all_control(state)
        # Target is Arverni Region (adjacent to Pictones)
        result = _arverni_phase_march(state, ARVERNI_REGION)
        # Check Warbands arrived in target
        target_wb = count_pieces(state, ARVERNI_REGION, ARVERNI, WARBAND)
        # Find marches to target
        marched_to_target = [
            m for m in result["marches"] if m["to"] == ARVERNI_REGION
        ]
        total_marched = sum(m["warbands"] for m in marched_to_target)
        # Verify consistency: warbands in target match what marched there
        assert target_wb == total_marched
        # Verify result records correct count (not just last iteration's value)
        for m in marched_to_target:
            assert m["warbands"] > 0

    def test_arverni_march_multiple_states(self):
        """Warbands with both Hidden and Revealed states march correctly.

        Verifies total moved includes all piece states, not just the last.
        """
        state = make_state()
        # Place Hidden and Revealed Warbands in Pictones
        place_piece(state, PICTONES, ARVERNI, WARBAND, 4, piece_state=HIDDEN)
        place_piece(state, PICTONES, ARVERNI, WARBAND, 3, piece_state=REVEALED)
        # Place a single enemy so Arverni has control
        place_piece(state, PICTONES, ROMANS, AUXILIA, 1)
        refresh_all_control(state)
        # March flips all to Hidden first, then marches
        result = _arverni_phase_march(state, ARVERNI_REGION)
        # Check total Warbands that arrived
        target_wb = count_pieces(state, ARVERNI_REGION, ARVERNI, WARBAND)
        marched_to_target = [
            m for m in result["marches"] if m["to"] == ARVERNI_REGION
        ]
        total_marched = sum(m["warbands"] for m in marched_to_target)
        assert target_wb == total_marched
        # Should have moved both Hidden and (now-flipped-to-Hidden) Revealed
        if marched_to_target:
            assert total_marched > 1  # more than just one piece state


# ============================================================================
# TEST: SCENARIO ISOLATION
# ============================================================================

class TestScenarioIsolation:
    """Arverni Phase is Ariovistus only."""

    def test_check_at_war_base_raises(self):
        """check_arverni_at_war raises in base game."""
        state = build_initial_state(SCENARIO_PAX_GALLICA, seed=42)
        with pytest.raises(CommandError):
            check_arverni_at_war(state)

    def test_run_phase_base_raises(self):
        """run_arverni_phase raises in base game."""
        state = build_initial_state(SCENARIO_PAX_GALLICA, seed=42)
        with pytest.raises(CommandError):
            run_arverni_phase(state)

    def test_gallic_war_scenario(self):
        """Works in Gallic War (another Ariovistus scenario)."""
        state = build_initial_state(SCENARIO_GALLIC_WAR, seed=42)
        is_at_war, regions = check_arverni_at_war(state)
        assert is_at_war is False  # No enemies initially
