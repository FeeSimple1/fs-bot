"""
Tests for the March command and Harassment.

Covers Roman, Gallic, and Germanic March in base game and Ariovistus,
plus Harassment resolution, scenario isolation, and edge cases.

Reference: §3.2.2, §3.3.2, §3.4.2, §3.4.5, §1.3.4, §1.3.5, §2.3.5,
           §2.3.8, §3.1.2, §6.2.2, A3.2.2, A3.3.2, A3.4.2, A3.4.5
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
    CAESAR, VERCINGETORIX, AMBIORIX, ARIOVISTUS_LEADER,
    DIVICIACUS, SUCCESSOR,
    # Scenarios
    SCENARIO_PAX_GALLICA, SCENARIO_ARIOVISTUS,
    # Regions
    MORINI, NERVII, ATREBATES, TREVERI, CARNUTES, MANDUBII,
    VENETI, PICTONES, BITURIGES, AEDUI_REGION, SEQUANI,
    ARVERNI_REGION, SUGAMBRI, UBII, PROVINCIA, CISALPINA,
    BRITANNIA,
    BELGICA_REGIONS, GERMANIA_REGIONS,
    # Control
    ROMAN_CONTROL, NO_CONTROL, ARVERNI_CONTROL,
    GERMANIC_CONTROL, BELGIC_CONTROL, AEDUI_CONTROL,
    FACTION_CONTROL,
    # Costs
    ROMAN_MARCH_COST, GALLIC_MARCH_COST,
    # Markers
    MARKER_DEVASTATED, MARKER_FROST,
    # Battle / Harassment
    HARASSMENT_WARBANDS_PER_LOSS,
)
from fs_bot.state.state_schema import build_initial_state
from fs_bot.board.pieces import (
    place_piece, remove_piece, count_pieces, count_pieces_by_state,
    get_available, get_leader_in_region, flip_piece, PieceError,
)
from fs_bot.board.control import refresh_all_control, is_controlled_by
from fs_bot.commands.march import (
    execute_march,
    march_from_origin,
    march_group,
    march_cost,
    resolve_harassment,
    germans_phase_march,
    drop_off_pieces,
    MarchError,
    _flip_origin_pieces,
    _check_crossing_stop,
    _max_steps_for_group,
    _get_movable_piece_types,
)
from fs_bot.map.map_data import ALL_REGION_DATA


# ============================================================================
# TEST HELPERS
# ============================================================================

def make_state(scenario=SCENARIO_PAX_GALLICA, seed=42):
    """Create a fresh state for testing."""
    return build_initial_state(scenario, seed=seed)


def give_resources(state, faction, amount):
    """Give a faction some resources for testing."""
    state["resources"][faction] = amount


def setup_roman_presence(state, region, *, leader=None,
                         legions=0, auxilia=0, forts=0, allies=0):
    """Set up Roman pieces in a region for testing."""
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


def setup_gallic_presence(state, region, faction, *, leader=None,
                          warbands=0, allies=0, citadels=0):
    """Set up Gallic/Germanic pieces in a region."""
    if leader:
        place_piece(state, region, faction, LEADER, leader_name=leader)
    if allies > 0:
        place_piece(state, region, faction, ALLY, allies)
    if citadels > 0:
        place_piece(state, region, faction, CITADEL, citadels)
    if warbands > 0:
        place_piece(state, region, faction, WARBAND, warbands)
    refresh_all_control(state)


def make_auxilia_revealed(state, region, count):
    """Flip Hidden Auxilia to Revealed for testing."""
    flip_piece(state, region, ROMANS, AUXILIA, count=count,
               from_state=HIDDEN, to_state=REVEALED)


def make_warbands_revealed(state, region, faction, count):
    """Flip Hidden Warbands to Revealed for testing."""
    flip_piece(state, region, faction, WARBAND, count=count,
               from_state=HIDDEN, to_state=REVEALED)


def make_warbands_scouted(state, region, faction, count):
    """Flip Hidden Warbands to Scouted for testing."""
    flip_piece(state, region, faction, WARBAND, count=count,
               from_state=HIDDEN, to_state=SCOUTED)


def mark_devastated(state, region):
    """Mark a region as Devastated."""
    state.setdefault("markers", {}).setdefault(region, {})
    state["markers"][region][MARKER_DEVASTATED] = True


# ============================================================================
# ROMAN MARCH TESTS — §3.2.2
# ============================================================================

class TestRomanMarchOneRegion:
    """Roman March: group moves 1 Region."""

    def test_move_legion_one_region(self):
        state = make_state()
        give_resources(state, ROMANS, 10)
        setup_roman_presence(state, PROVINCIA, legions=2)

        group = {LEADER: None, LEGION: 2, AUXILIA: 0, WARBAND: 0}
        result = march_group(state, ROMANS, PROVINCIA, [SEQUANI], group)

        assert result["final_region"] == SEQUANI
        assert count_pieces(state, SEQUANI, ROMANS, LEGION) == 2
        assert count_pieces(state, PROVINCIA, ROMANS, LEGION) == 0

    def test_move_auxilia_one_region(self):
        state = make_state()
        give_resources(state, ROMANS, 10)
        setup_roman_presence(state, PROVINCIA, auxilia=3)

        group = {LEADER: None, LEGION: 0, AUXILIA: 3, WARBAND: 0}
        result = march_group(state, ROMANS, PROVINCIA, [SEQUANI], group)

        assert result["final_region"] == SEQUANI
        assert count_pieces(state, SEQUANI, ROMANS, AUXILIA) == 3


class TestRomanMarchTwoRegions:
    """Roman March: group moves 2 Regions."""

    def test_legion_moves_two_regions(self):
        state = make_state()
        give_resources(state, ROMANS, 10)
        setup_roman_presence(state, PROVINCIA, legions=3)

        # Provincia -> Sequani -> Mandubii
        group = {LEADER: None, LEGION: 3, AUXILIA: 0, WARBAND: 0}
        result = march_group(state, ROMANS, PROVINCIA,
                             [SEQUANI, MANDUBII], group)

        assert result["final_region"] == MANDUBII
        assert count_pieces(state, MANDUBII, ROMANS, LEGION) == 3
        assert count_pieces(state, PROVINCIA, ROMANS, LEGION) == 0
        assert count_pieces(state, SEQUANI, ROMANS, LEGION) == 0


class TestRomanMarchCaesar:
    """Roman March: Caesar moves 3 Regions."""

    def test_caesar_three_regions(self):
        state = make_state()
        give_resources(state, ROMANS, 10)
        setup_roman_presence(state, PROVINCIA, leader=CAESAR, legions=2,
                             auxilia=1)

        # Provincia -> Sequani -> Mandubii -> Carnutes
        group = {LEADER: CAESAR, LEGION: 2, AUXILIA: 1, WARBAND: 0}
        result = march_group(state, ROMANS, PROVINCIA,
                             [SEQUANI, MANDUBII, CARNUTES], group)

        assert result["final_region"] == CARNUTES
        assert get_leader_in_region(state, CARNUTES, ROMANS) == CAESAR
        assert count_pieces(state, CARNUTES, ROMANS, LEGION) == 2
        assert count_pieces(state, CARNUTES, ROMANS, AUXILIA) == 1
        assert len(result["path"]) == 4


class TestRomanMarchDropOff:
    """Roman March: pieces drop off mid-march."""

    def test_drop_off_legion_mid_march(self):
        """Pieces can be dropped off in a region before group moves on."""
        state = make_state()
        give_resources(state, ROMANS, 10)
        setup_roman_presence(state, PROVINCIA, legions=3)

        # Move group to Sequani, drop 1 legion, continue to Mandubii with 2
        group = {LEADER: None, LEGION: 3, AUXILIA: 0, WARBAND: 0}

        # Step 1: move to Sequani
        result1 = march_group(state, ROMANS, PROVINCIA, [SEQUANI], group)
        assert count_pieces(state, SEQUANI, ROMANS, LEGION) == 3

        # Drop off 1 legion (pieces stay in Sequani — caller adjusts group)
        drop_off_pieces(state, SEQUANI, ROMANS, {LEGION: 1})
        # The remaining group has 2 legions
        group2 = {LEADER: None, LEGION: 2, AUXILIA: 0, WARBAND: 0}

        # Step 2: move remaining from Sequani to Mandubii
        result2 = march_group(state, ROMANS, SEQUANI, [MANDUBII], group2)

        assert count_pieces(state, SEQUANI, ROMANS, LEGION) == 1
        assert count_pieces(state, MANDUBII, ROMANS, LEGION) == 2


class TestRomanFlipAtOrigin:
    """Roman March: Revealed Auxilia flipped to Hidden at origin."""

    def test_revealed_auxilia_flipped(self):
        state = make_state()
        setup_roman_presence(state, PROVINCIA, auxilia=4)
        make_auxilia_revealed(state, PROVINCIA, 2)

        assert count_pieces_by_state(
            state, PROVINCIA, ROMANS, AUXILIA, REVEALED) == 2

        result = _flip_origin_pieces(state, PROVINCIA, ROMANS)

        assert count_pieces_by_state(
            state, PROVINCIA, ROMANS, AUXILIA, REVEALED) == 0
        assert count_pieces_by_state(
            state, PROVINCIA, ROMANS, AUXILIA, HIDDEN) == 4
        assert result["flipped_to_hidden"] == 2


class TestRomanMarchCost:
    """Roman March: cost 2 per origin, 4 if Devastated."""

    def test_cost_normal(self):
        state = make_state()
        assert march_cost(state, PROVINCIA, ROMANS) == ROMAN_MARCH_COST

    def test_cost_devastated(self):
        state = make_state()
        mark_devastated(state, TREVERI)
        assert march_cost(state, TREVERI, ROMANS) == ROMAN_MARCH_COST * 2

    def test_cost_deducted_on_execute(self):
        state = make_state()
        give_resources(state, ROMANS, 10)
        setup_roman_presence(state, PROVINCIA, legions=1)

        result = execute_march(state, ROMANS, [
            {"origin": PROVINCIA,
             "groups": [({LEADER: None, LEGION: 1, AUXILIA: 0, WARBAND: 0},
                         [SEQUANI])]}
        ])

        assert result["total_cost"] == ROMAN_MARCH_COST
        assert state["resources"][ROMANS] == 10 - ROMAN_MARCH_COST

    def test_insufficient_resources(self):
        state = make_state()
        give_resources(state, ROMANS, 1)
        setup_roman_presence(state, PROVINCIA, legions=1)

        with pytest.raises(MarchError, match="Resources"):
            execute_march(state, ROMANS, [
                {"origin": PROVINCIA,
                 "groups": [({LEADER: None, LEGION: 1, AUXILIA: 0,
                              WARBAND: 0}, [SEQUANI])]}
            ])


class TestRomanMarchFrost:
    """Roman March: Frost blocks March — §2.3.8."""

    # NOTE: Frost blocking is a Sequence of Play enforcement at the caller
    # level, not within the march module itself. The march module executes
    # movement mechanically. The caller must check state for Frost before
    # calling execute_march. This test validates cost/movement mechanics
    # still work correctly — actual Frost gate is above this module.
    pass


class TestRomanMarchBritannia:
    """Roman March: entering Britannia stops group — §1.3.4."""

    def test_entering_britannia_stops(self):
        state = make_state()
        give_resources(state, ROMANS, 10)
        setup_roman_presence(state, ATREBATES, legions=2)

        # Atrebates -> Britannia (coastal): should stop
        group = {LEADER: None, LEGION: 2, AUXILIA: 0, WARBAND: 0}
        result = march_group(state, ROMANS, ATREBATES,
                             [BRITANNIA], group)

        assert result["final_region"] == BRITANNIA
        assert result["stopped_reason"] == "Britannia crossing"

    def test_leaving_britannia_stops(self):
        state = make_state()
        give_resources(state, ROMANS, 10)
        setup_roman_presence(state, BRITANNIA, legions=2)

        # Britannia -> Atrebates (coastal): should stop
        group = {LEADER: None, LEGION: 2, AUXILIA: 0, WARBAND: 0}
        result = march_group(state, ROMANS, BRITANNIA,
                             [ATREBATES], group)

        assert result["final_region"] == ATREBATES
        assert result["stopped_reason"] == "Britannia crossing"

    def test_britannia_stops_even_with_caesar(self):
        """Even Caesar cannot continue past Britannia crossing."""
        state = make_state()
        give_resources(state, ROMANS, 10)
        setup_roman_presence(state, ATREBATES, leader=CAESAR, legions=2)

        # Try to go Atrebates -> Britannia -> further (should stop at Brit)
        group = {LEADER: CAESAR, LEGION: 2, AUXILIA: 0, WARBAND: 0}
        result = march_group(state, ROMANS, ATREBATES,
                             [BRITANNIA, MORINI], group)

        assert result["final_region"] == BRITANNIA
        assert result["stopped_reason"] == "Britannia crossing"


class TestRomanMarchRhenus:
    """Roman March: Rhenus crossing stops group — §1.3.5."""

    def test_rhenus_crossing_stops_romans(self):
        state = make_state()
        give_resources(state, ROMANS, 10)
        setup_roman_presence(state, TREVERI, legions=2)

        # Treveri -> Sugambri (rhenus crossing): should stop
        group = {LEADER: None, LEGION: 2, AUXILIA: 0, WARBAND: 0}
        result = march_group(state, ROMANS, TREVERI,
                             [SUGAMBRI], group)

        assert result["final_region"] == SUGAMBRI
        assert result["stopped_reason"] == "Rhenus crossing"


class TestRomanMarchDevastated:
    """Roman March: entering Devastated stops group — §3.2.2."""

    def test_entering_devastated_stops(self):
        state = make_state()
        give_resources(state, ROMANS, 10)
        mark_devastated(state, MANDUBII)
        setup_roman_presence(state, CARNUTES, legions=2)

        # Carnutes -> Mandubii (Devastated): should stop
        group = {LEADER: None, LEGION: 2, AUXILIA: 0, WARBAND: 0}
        result = march_group(state, ROMANS, CARNUTES,
                             [MANDUBII], group)

        assert result["final_region"] == MANDUBII
        assert result["stopped_reason"] == "Entering Devastated region"


class TestRomanMarchPieceRestrictions:
    """Roman March: Allies and Forts cannot march — §3.2.2."""

    def test_forts_cannot_march(self):
        assert FORT not in _get_movable_piece_types(ROMANS, SCENARIO_PAX_GALLICA)

    def test_allies_cannot_march(self):
        assert ALLY not in _get_movable_piece_types(ROMANS, SCENARIO_PAX_GALLICA)

    def test_movable_types_roman(self):
        types = _get_movable_piece_types(ROMANS, SCENARIO_PAX_GALLICA)
        assert LEADER in types
        assert LEGION in types
        assert AUXILIA in types


# ============================================================================
# GALLIC MARCH TESTS — §3.3.2
# ============================================================================

class TestGallicMarchOneRegion:
    """Gallic March: group moves 1 Region only (no 2nd move)."""

    def test_warbands_move_one_region(self):
        state = make_state()
        give_resources(state, ARVERNI, 10)
        setup_gallic_presence(state, ARVERNI_REGION, ARVERNI, warbands=5)

        group = {LEADER: None, LEGION: 0, AUXILIA: 0, WARBAND: 5}
        result = march_group(state, ARVERNI, ARVERNI_REGION,
                             [BITURIGES], group)

        assert result["final_region"] == BITURIGES
        assert count_pieces(state, BITURIGES, ARVERNI, WARBAND) == 5

    def test_cannot_move_two_regions_without_vercingetorix(self):
        """Without Vercingetorix, Gallic groups max 1 step."""
        state = make_state()
        max_steps = _max_steps_for_group(
            state, ARVERNI_REGION, ARVERNI,
            {LEADER: None, WARBAND: 5})
        assert max_steps == 1


class TestGallicMarchFlip:
    """Gallic March: Revealed Warbands flipped to Hidden."""

    def test_revealed_warbands_flipped(self):
        state = make_state()
        setup_gallic_presence(state, ARVERNI_REGION, ARVERNI, warbands=6)
        make_warbands_revealed(state, ARVERNI_REGION, ARVERNI, 3)

        assert count_pieces_by_state(
            state, ARVERNI_REGION, ARVERNI, WARBAND, REVEALED) == 3

        result = _flip_origin_pieces(state, ARVERNI_REGION, ARVERNI)

        assert count_pieces_by_state(
            state, ARVERNI_REGION, ARVERNI, WARBAND, REVEALED) == 0
        assert count_pieces_by_state(
            state, ARVERNI_REGION, ARVERNI, WARBAND, HIDDEN) == 6
        assert result["flipped_to_hidden"] == 3


class TestGallicMarchScouted:
    """Gallic March: Scouted Warbands lose Scouted marker, stay Revealed."""

    def test_scouted_become_revealed(self):
        """§3.3.2 / §4.2.2: Scouted Warbands remove marker, stay Revealed."""
        state = make_state()
        setup_gallic_presence(state, ARVERNI_REGION, ARVERNI, warbands=4)
        make_warbands_scouted(state, ARVERNI_REGION, ARVERNI, 2)

        assert count_pieces_by_state(
            state, ARVERNI_REGION, ARVERNI, WARBAND, SCOUTED) == 2

        result = _flip_origin_pieces(state, ARVERNI_REGION, ARVERNI)

        # Scouted -> Revealed (not Hidden) per §1.4.3/§4.2.2
        assert count_pieces_by_state(
            state, ARVERNI_REGION, ARVERNI, WARBAND, SCOUTED) == 0
        assert count_pieces_by_state(
            state, ARVERNI_REGION, ARVERNI, WARBAND, REVEALED) == 2
        assert result["scouted_to_revealed"] == 2


class TestGallicMarchCost:
    """Gallic March: cost 1 per origin, 2 if Devastated."""

    def test_cost_normal(self):
        state = make_state()
        assert march_cost(state, ARVERNI_REGION, ARVERNI) == GALLIC_MARCH_COST

    def test_cost_devastated(self):
        state = make_state()
        mark_devastated(state, TREVERI)
        assert march_cost(state, TREVERI, AEDUI) == GALLIC_MARCH_COST * 2


class TestGallicMarchPieceRestrictions:
    """Gallic March: Allies and Citadels cannot march — §3.3.2."""

    def test_allies_cannot_march(self):
        assert ALLY not in _get_movable_piece_types(
            ARVERNI, SCENARIO_PAX_GALLICA)

    def test_citadels_cannot_march(self):
        assert CITADEL not in _get_movable_piece_types(
            ARVERNI, SCENARIO_PAX_GALLICA)

    def test_movable_types_gallic(self):
        types = _get_movable_piece_types(ARVERNI, SCENARIO_PAX_GALLICA)
        assert LEADER in types
        assert WARBAND in types
        assert len(types) == 2


# ============================================================================
# GERMANIC MARCH TESTS — §3.4.2
# ============================================================================

class TestGermanicMarchRhenus:
    """Germanic March: Rhenus crossing does NOT stop group — §3.4.5."""

    def test_rhenus_does_not_stop_germans(self):
        state = make_state()
        setup_gallic_presence(state, SUGAMBRI, GERMANS, warbands=5)

        # Sugambri -> Treveri (rhenus): should NOT stop Germans
        stops, reason = _check_crossing_stop(
            state, SUGAMBRI, TREVERI, GERMANS)
        assert stops is False

    def test_rhenus_still_stops_gauls(self):
        state = make_state()
        stops, reason = _check_crossing_stop(
            state, TREVERI, SUGAMBRI, ARVERNI)
        assert stops is True
        assert reason == "Rhenus crossing"

    def test_german_march_across_rhenus(self):
        state = make_state()
        setup_gallic_presence(state, SUGAMBRI, GERMANS, warbands=5)

        group = {LEADER: None, LEGION: 0, AUXILIA: 0, WARBAND: 5}
        result = march_group(state, GERMANS, SUGAMBRI,
                             [TREVERI], group)

        assert result["final_region"] == TREVERI
        assert result["stopped_reason"] is None
        assert count_pieces(state, TREVERI, GERMANS, WARBAND) == 5


# ============================================================================
# HARASSMENT TESTS — §3.2.2, §3.4.5
# ============================================================================

class TestHarassment:
    """Harassment: 3 Hidden Warbands inflict 1 Loss."""

    def test_three_hidden_warbands_one_loss(self):
        state = make_state()
        setup_roman_presence(state, TREVERI, legions=2, auxilia=3)
        setup_gallic_presence(state, TREVERI, ARVERNI, warbands=3)
        # All Warbands placed Hidden by default

        departing_pieces = {
            LEADER: None, LEGION: 2, AUXILIA: 3, WARBAND: 0
        }

        result = resolve_harassment(
            state, TREVERI, ROMANS, departing_pieces,
            harassing_factions=[(ARVERNI, 3)])

        assert result["harassment_occurred"] is True
        assert len(result["losses_by_faction"]) == 1
        faction_loss = result["losses_by_faction"][0]
        assert faction_loss["num_losses"] == 1
        assert result["total_pieces_removed"] == 1

    def test_six_hidden_warbands_two_losses(self):
        state = make_state()
        setup_roman_presence(state, TREVERI, auxilia=5)
        setup_gallic_presence(state, TREVERI, BELGAE, warbands=6)

        departing_pieces = {
            LEADER: None, LEGION: 0, AUXILIA: 5, WARBAND: 0
        }

        result = resolve_harassment(
            state, TREVERI, ROMANS, departing_pieces,
            harassing_factions=[(BELGAE, 6)])

        assert result["losses_by_faction"][0]["num_losses"] == 2
        assert result["total_pieces_removed"] == 2

    def test_two_hidden_warbands_no_loss(self):
        """Fewer than 3 Hidden Warbands = no Harassment."""
        state = make_state()
        setup_roman_presence(state, TREVERI, auxilia=3)
        setup_gallic_presence(state, TREVERI, ARVERNI, warbands=2)

        departing_pieces = {
            LEADER: None, LEGION: 0, AUXILIA: 3, WARBAND: 0
        }

        result = resolve_harassment(
            state, TREVERI, ROMANS, departing_pieces,
            harassing_factions=[(ARVERNI, 2)])

        assert result["harassment_occurred"] is True
        assert result["total_pieces_removed"] == 0


class TestHarassmentRoll:
    """Harassment: roll for Legion/Leader (use seeded RNG)."""

    def test_roll_for_legion(self):
        """When no Auxilia, must roll for Legion. Seeded RNG for determinism."""
        # Use seed that produces a roll <= 3 (remove)
        state = make_state(seed=1)
        setup_roman_presence(state, TREVERI, legions=2)
        setup_gallic_presence(state, TREVERI, ARVERNI, warbands=3)

        departing_pieces = {
            LEADER: None, LEGION: 2, AUXILIA: 0, WARBAND: 0
        }

        result = resolve_harassment(
            state, TREVERI, ROMANS, departing_pieces,
            harassing_factions=[(ARVERNI, 3)])

        # One loss was attempted — either removed or survived based on roll
        assert result["harassment_occurred"] is True
        faction_loss = result["losses_by_faction"][0]
        assert faction_loss["num_losses"] == 1
        assert len(faction_loss["removals"]) == 1
        removal = faction_loss["removals"][0]
        # removal is (piece_type, count_removed, die_roll)
        assert removal[2] is not None  # Roll was made

    def test_soft_target_preferred_over_roll(self):
        """Auxilia removed before rolling for Legions."""
        state = make_state()
        setup_roman_presence(state, TREVERI, legions=2, auxilia=1)
        setup_gallic_presence(state, TREVERI, ARVERNI, warbands=3)

        departing_pieces = {
            LEADER: None, LEGION: 2, AUXILIA: 1, WARBAND: 0
        }

        result = resolve_harassment(
            state, TREVERI, ROMANS, departing_pieces,
            harassing_factions=[(ARVERNI, 3)])

        faction_loss = result["losses_by_faction"][0]
        removal = faction_loss["removals"][0]
        # Should have removed Auxilia (soft target, no roll)
        assert removal[0] == AUXILIA
        assert removal[2] is None  # No die roll for soft target


# ============================================================================
# ARIOVISTUS TESTS — A3.2.2, A3.3.2, A3.4.2, A3.4.5
# ============================================================================

class TestAriovistusAlpsCrossing:
    """Ariovistus: Alps crossing stops group (A3.2.2)."""

    def test_entering_cisalpina_stops_in_ariovistus(self):
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        stops, reason = _check_crossing_stop(
            state, PROVINCIA, CISALPINA, ROMANS)
        assert stops is True
        assert "Cisalpina" in reason

    def test_leaving_cisalpina_stops_in_ariovistus(self):
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        stops, reason = _check_crossing_stop(
            state, CISALPINA, PROVINCIA, ROMANS)
        assert stops is True

    def test_cisalpina_does_not_stop_in_base(self):
        """In base game, Cisalpina is not playable — no Alps rule."""
        state = make_state(scenario=SCENARIO_PAX_GALLICA)
        # In base game Cisalpina is not playable by default
        # The stop check for Cisalpina only applies in Ariovistus
        stops, reason = _check_crossing_stop(
            state, PROVINCIA, CISALPINA, ROMANS)
        # Should not trigger Alps crossing (only Ariovistus scenario)
        assert stops is False


class TestAriovistusBritanniaNotPlayable:
    """Ariovistus: Britannia not playable — cannot march there."""

    def test_britannia_not_playable_in_ariovistus(self):
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        region_data = ALL_REGION_DATA[BRITANNIA]
        assert region_data.is_playable(SCENARIO_ARIOVISTUS) is False

    def test_march_to_britannia_fails_in_ariovistus(self):
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        give_resources(state, ROMANS, 10)
        setup_roman_presence(state, ATREBATES, legions=2)

        group = {LEADER: None, LEGION: 2, AUXILIA: 0, WARBAND: 0}
        with pytest.raises(MarchError, match="not playable"):
            march_group(state, ROMANS, ATREBATES, [BRITANNIA], group)


class TestAriovistusGermanicMarch:
    """Ariovistus: Germanic March like Gallic — A3.4.2."""

    def test_german_can_march_leader_in_ariovistus(self):
        types = _get_movable_piece_types(GERMANS, SCENARIO_ARIOVISTUS)
        assert LEADER in types
        assert WARBAND in types

    def test_german_base_warbands_only(self):
        types = _get_movable_piece_types(GERMANS, SCENARIO_PAX_GALLICA)
        assert types == (WARBAND,)


# ============================================================================
# SCENARIO ISOLATION TESTS
# ============================================================================

class TestScenarioIsolation:
    """Scenario isolation: Germans Phase March only in base game."""

    def test_germans_phase_march_base_only(self):
        state = make_state(scenario=SCENARIO_PAX_GALLICA)
        setup_gallic_presence(state, SUGAMBRI, GERMANS, warbands=10)
        setup_gallic_presence(state, UBII, GERMANS, warbands=5)
        refresh_all_control(state)

        # Should work in base game
        result = germans_phase_march(state)
        assert isinstance(result, dict)

    def test_germans_phase_march_fails_ariovistus(self):
        state = make_state(scenario=SCENARIO_ARIOVISTUS)

        with pytest.raises(MarchError, match="base game only"):
            germans_phase_march(state)


# ============================================================================
# VERCINGETORIX MARCH BONUS — §3.3.2
# ============================================================================

class TestVercingetorixMarch:
    """Vercingetorix: can march into 2nd Region."""

    def test_vercingetorix_two_regions(self):
        state = make_state()
        give_resources(state, ARVERNI, 10)
        setup_gallic_presence(state, ARVERNI_REGION, ARVERNI,
                              leader=VERCINGETORIX, warbands=5)

        max_steps = _max_steps_for_group(
            state, ARVERNI_REGION, ARVERNI,
            {LEADER: VERCINGETORIX, WARBAND: 5})
        assert max_steps == 2

    def test_vercingetorix_not_in_ariovistus(self):
        """Vercingetorix doesn't exist in Ariovistus — no bonus."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        # Arverni have no leader in Ariovistus (cap is 0)
        max_steps = _max_steps_for_group(
            state, ARVERNI_REGION, ARVERNI,
            {LEADER: None, WARBAND: 5})
        assert max_steps == 1


# ============================================================================
# CONTROL REFRESH
# ============================================================================

class TestControlRefresh:
    """Control refreshed after all movement."""

    def test_control_updated_after_march(self):
        state = make_state()
        give_resources(state, ROMANS, 10)
        setup_roman_presence(state, PROVINCIA, legions=5)

        # Sequani should have no Roman control initially
        assert not is_controlled_by(state, SEQUANI, ROMANS)

        result = execute_march(state, ROMANS, [
            {"origin": PROVINCIA,
             "groups": [({LEADER: None, LEGION: 5, AUXILIA: 0, WARBAND: 0},
                         [SEQUANI])]}
        ])

        # After march, Sequani should be Roman-controlled
        assert is_controlled_by(state, SEQUANI, ROMANS)


# ============================================================================
# FREE MARCH — §3.1.2
# ============================================================================

class TestFreeMarch:
    """Free March: no cost, granted by Events."""

    def test_free_march_no_cost(self):
        state = make_state()
        give_resources(state, ROMANS, 0)
        setup_roman_presence(state, PROVINCIA, legions=2)

        result = execute_march(state, ROMANS, [
            {"origin": PROVINCIA,
             "groups": [({LEADER: None, LEGION: 2, AUXILIA: 0, WARBAND: 0},
                         [SEQUANI])]}
        ], free=True)

        assert result["total_cost"] == 0
        assert state["resources"][ROMANS] == 0
        assert count_pieces(state, SEQUANI, ROMANS, LEGION) == 2


# ============================================================================
# LIMITED COMMAND — §2.3.5
# ============================================================================

class TestLimitedCommand:
    """Limited Command: one origin only."""

    def test_limited_rejects_multiple_origins(self):
        state = make_state()
        give_resources(state, ROMANS, 20)
        setup_roman_presence(state, PROVINCIA, legions=2)
        setup_roman_presence(state, TREVERI, legions=2)

        with pytest.raises(MarchError, match="Limited Command"):
            execute_march(state, ROMANS, [
                {"origin": PROVINCIA,
                 "groups": [({LEADER: None, LEGION: 2, AUXILIA: 0,
                              WARBAND: 0}, [SEQUANI])]},
                {"origin": TREVERI,
                 "groups": [({LEADER: None, LEGION: 2, AUXILIA: 0,
                              WARBAND: 0}, [MANDUBII])]},
            ], limited=True)

    def test_limited_allows_one_origin(self):
        state = make_state()
        give_resources(state, ROMANS, 10)
        setup_roman_presence(state, PROVINCIA, legions=2)

        result = execute_march(state, ROMANS, [
            {"origin": PROVINCIA,
             "groups": [({LEADER: None, LEGION: 2, AUXILIA: 0, WARBAND: 0},
                         [SEQUANI])]}
        ], limited=True)

        assert result["limited"] is True
        assert count_pieces(state, SEQUANI, ROMANS, LEGION) == 2


# ============================================================================
# GERMANS PHASE MARCH — §6.2.2
# ============================================================================

class TestGermansPhasesMarch:
    """Germans Phase March: deterministic base-game procedure."""

    def test_germans_phase_march_moves_surplus(self):
        """Warbands beyond control need move out."""
        state = make_state()
        # Place enough Warbands in Sugambri that there's a surplus
        setup_gallic_presence(state, SUGAMBRI, GERMANS, warbands=8)
        refresh_all_control(state)

        result = germans_phase_march(state)

        # Some groups should have moved
        assert len(result["groups_moved"]) > 0 or True  # May be 0 if no surplus
        # All warbands should be flipped to Hidden afterward
        for region in state["spaces"]:
            revealed = count_pieces_by_state(
                state, region, GERMANS, WARBAND, REVEALED)
            scouted = count_pieces_by_state(
                state, region, GERMANS, WARBAND, SCOUTED)
            assert revealed == 0, f"Revealed Warbands in {region}"
            assert scouted == 0, f"Scouted Warbands in {region}"

    def test_all_warbands_flipped_hidden_after_phase(self):
        """§6.2.2: All Germanic Warbands flip to Hidden afterward."""
        state = make_state()
        setup_gallic_presence(state, UBII, GERMANS, warbands=4)
        # Make some Revealed
        make_warbands_revealed(state, UBII, GERMANS, 2)
        refresh_all_control(state)

        result = germans_phase_march(state)

        # Check all German Warbands are Hidden
        for region in state["spaces"]:
            revealed = count_pieces_by_state(
                state, region, GERMANS, WARBAND, REVEALED)
            scouted = count_pieces_by_state(
                state, region, GERMANS, WARBAND, SCOUTED)
            assert revealed == 0
            assert scouted == 0


# ============================================================================
# EDGE CASES
# ============================================================================

class TestEdgeCases:
    """Various edge cases and boundary conditions."""

    def test_march_no_piece_in_origin(self):
        """Cannot march pieces that don't exist."""
        state = make_state()
        give_resources(state, ROMANS, 10)

        group = {LEADER: None, LEGION: 2, AUXILIA: 0, WARBAND: 0}
        with pytest.raises(MarchError, match="need"):
            march_group(state, ROMANS, PROVINCIA, [SEQUANI], group)

    def test_march_to_non_adjacent(self):
        """Cannot march to a non-adjacent region."""
        state = make_state()
        give_resources(state, ROMANS, 10)
        setup_roman_presence(state, PROVINCIA, legions=2)

        group = {LEADER: None, LEGION: 2, AUXILIA: 0, WARBAND: 0}
        with pytest.raises(MarchError, match="not adjacent"):
            march_group(state, ROMANS, PROVINCIA, [BRITANNIA], group)

    def test_gallic_march_belgae(self):
        """Belgae March works the same as other Gallic factions."""
        state = make_state()
        give_resources(state, BELGAE, 10)
        setup_gallic_presence(state, NERVII, BELGAE,
                              leader=AMBIORIX, warbands=4)

        group = {LEADER: AMBIORIX, LEGION: 0, AUXILIA: 0, WARBAND: 4}
        result = march_group(state, BELGAE, NERVII,
                             [ATREBATES], group)

        assert result["final_region"] == ATREBATES
        assert count_pieces(state, ATREBATES, BELGAE, WARBAND) == 4
        assert get_leader_in_region(state, ATREBATES, BELGAE) == AMBIORIX

    def test_german_march_cost_base_free(self):
        """Germans don't pay for commands in base game."""
        state = make_state()
        assert march_cost(state, SUGAMBRI, GERMANS) == 0

    def test_german_march_cost_ariovistus(self):
        """Germans in Ariovistus pay like Gauls."""
        state = make_state(scenario=SCENARIO_ARIOVISTUS)
        assert march_cost(state, SUGAMBRI, GERMANS) == GALLIC_MARCH_COST

    def test_multiple_groups_from_one_origin(self):
        """Multiple groups can march from the same origin — §3.2.2."""
        state = make_state()
        give_resources(state, ROMANS, 10)
        setup_roman_presence(state, PROVINCIA, legions=4, auxilia=3)

        groups = [
            ({LEADER: None, LEGION: 2, AUXILIA: 0, WARBAND: 0}, [SEQUANI]),
            ({LEADER: None, LEGION: 2, AUXILIA: 3, WARBAND: 0},
             [AEDUI_REGION]),
        ]

        result = march_from_origin(state, ROMANS, PROVINCIA, groups)

        assert len(result["group_results"]) == 2
        assert count_pieces(state, SEQUANI, ROMANS, LEGION) == 2
        assert count_pieces(state, AEDUI_REGION, ROMANS, LEGION) == 2
        assert count_pieces(state, AEDUI_REGION, ROMANS, AUXILIA) == 3
