"""
Tests for scenario setup.

For all 5 scenarios: verify piece counts reconcile (map + available + track
= caps), verify resources match scenario reference, verify Senate position,
verify tribal allegiances.

Also tests scenario isolation.
"""

import pytest

from fs_bot.rules_consts import (
    # Scenarios
    SCENARIO_PAX_GALLICA, SCENARIO_RECONQUEST, SCENARIO_GREAT_REVOLT,
    SCENARIO_ARIOVISTUS, SCENARIO_GALLIC_WAR,
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS, ALL_SCENARIOS,
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    FACTIONS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    HIDDEN, REVEALED,
    # Leaders
    CAESAR, VERCINGETORIX, AMBIORIX, SUCCESSOR,
    ARIOVISTUS_LEADER, DIVICIACUS, BODUOGNATUS,
    # Regions
    MORINI, NERVII, ATREBATES, SUGAMBRI, UBII,
    TREVERI, CARNUTES, MANDUBII, VENETI, PICTONES,
    BITURIGES, AEDUI_REGION, SEQUANI, ARVERNI_REGION,
    BRITANNIA, PROVINCIA, CISALPINA,
    # Tribes
    TRIBE_MENAPII, TRIBE_MORINI, TRIBE_EBURONES, TRIBE_NERVII,
    TRIBE_BELLOVACI, TRIBE_ATREBATES, TRIBE_REMI,
    TRIBE_SUEBI_NORTH, TRIBE_SUGAMBRI, TRIBE_SUEBI_SOUTH, TRIBE_UBII,
    TRIBE_TREVERI,
    TRIBE_CARNUTES, TRIBE_AULERCI,
    TRIBE_MANDUBII, TRIBE_SENONES, TRIBE_LINGONES,
    TRIBE_VENETI, TRIBE_NAMNETES,
    TRIBE_PICTONES, TRIBE_SANTONES,
    TRIBE_BITURIGES,
    TRIBE_AEDUI,
    TRIBE_SEQUANI, TRIBE_HELVETII,
    TRIBE_ARVERNI, TRIBE_CADURCI, TRIBE_VOLCAE,
    TRIBE_CATUVELLAUNI,
    TRIBE_HELVII,
    TRIBE_NORI,
    # Senate
    UPROAR, INTRIGUE, ADULATION,
    # Legions track
    LEGIONS_ROW_BOTTOM, LEGIONS_ROW_MIDDLE, LEGIONS_ROW_TOP,
    LEGIONS_ROWS,
    # Control
    ROMAN_CONTROL, ARVERNI_CONTROL, AEDUI_CONTROL,
    BELGIC_CONTROL, GERMANIC_CONTROL, NO_CONTROL,
    # Caps
    CAPS_BASE, CAPS_ARIOVISTUS,
    # Tribe status
    ALLIED, DISPERSED, DISPERSED_GATHERING,
    # Cards
    WINTER_CARD,
    # Markers
    MARKER_BRITANNIA_NOT_IN_PLAY, MARKER_ARVERNI_RALLY,
)

from fs_bot.state.state_schema import validate_state
from fs_bot.state.setup import setup_scenario
from fs_bot.board.pieces import (
    count_pieces, get_leader_in_region, find_leader, get_available,
)
from fs_bot.board.control import is_controlled_by


# ============================================================================
# VALIDATE ALL SCENARIOS PASS CONSISTENCY CHECK
# ============================================================================

class TestAllScenariosValidate:
    """All 5 scenarios must produce valid states."""

    @pytest.mark.parametrize("scenario", ALL_SCENARIOS)
    def test_scenario_validates(self, scenario):
        state = setup_scenario(scenario, seed=42)
        errors = validate_state(state)
        assert errors == [], f"Validation errors: {errors}"


# ============================================================================
# PAX GALLICA? — DETAILED VERIFICATION
# ============================================================================

class TestPaxGallica:
    """Verify Pax Gallica? setup against reference."""

    @pytest.fixture
    def state(self):
        return setup_scenario(SCENARIO_PAX_GALLICA, seed=42)

    def test_resources(self, state):
        assert state["resources"][ARVERNI] == 5
        assert state["resources"][AEDUI] == 5
        assert state["resources"][BELGAE] == 5
        assert state["resources"][ROMANS] == 8

    def test_senate(self, state):
        # 1st year: Senate not in any position
        assert state["senate"]["position"] is None

    def test_legions_track(self, state):
        assert state["legions_track"][LEGIONS_ROW_BOTTOM] == 4

    def test_britannia(self, state):
        assert get_leader_in_region(state, BRITANNIA, ROMANS) == CAESAR
        assert count_pieces(state, BRITANNIA, ROMANS, LEGION) == 5
        assert count_pieces(state, BRITANNIA, ROMANS, AUXILIA) == 1
        assert is_controlled_by(state, BRITANNIA, ROMANS)

    def test_morini(self, state):
        assert count_pieces(state, MORINI, BELGAE, WARBAND) == 1
        assert count_pieces(state, MORINI, BELGAE, ALLY) == 1
        assert state["tribes"][TRIBE_MENAPII]["allied_faction"] == BELGAE
        assert is_controlled_by(state, MORINI, BELGAE)

    def test_nervii(self, state):
        assert get_leader_in_region(state, NERVII, BELGAE) == AMBIORIX
        assert count_pieces(state, NERVII, BELGAE, WARBAND) == 2
        assert count_pieces(state, NERVII, BELGAE, ALLY) == 1
        assert count_pieces(state, NERVII, GERMANS, WARBAND) == 2
        assert count_pieces(state, NERVII, ROMANS, FORT) == 1
        assert state["tribes"][TRIBE_EBURONES]["allied_faction"] == BELGAE

    def test_atrebates(self, state):
        assert count_pieces(state, ATREBATES, BELGAE, WARBAND) == 2
        assert count_pieces(state, ATREBATES, BELGAE, ALLY) == 1
        assert count_pieces(state, ATREBATES, ROMANS, ALLY) == 2
        assert count_pieces(state, ATREBATES, ROMANS, AUXILIA) == 1
        assert state["tribes"][TRIBE_BELLOVACI]["allied_faction"] == BELGAE
        assert state["tribes"][TRIBE_ATREBATES]["allied_faction"] == ROMANS
        assert state["tribes"][TRIBE_REMI]["allied_faction"] == ROMANS

    def test_sugambri(self, state):
        assert count_pieces(state, SUGAMBRI, GERMANS, WARBAND) == 4
        assert count_pieces(state, SUGAMBRI, GERMANS, ALLY) == 2
        assert state["tribes"][TRIBE_SUGAMBRI]["allied_faction"] == GERMANS
        assert state["tribes"][TRIBE_SUEBI_NORTH]["allied_faction"] == GERMANS
        assert is_controlled_by(state, SUGAMBRI, GERMANS)

    def test_ubii(self, state):
        assert count_pieces(state, UBII, GERMANS, WARBAND) == 4
        assert count_pieces(state, UBII, GERMANS, ALLY) == 1
        assert state["tribes"][TRIBE_SUEBI_SOUTH]["allied_faction"] == GERMANS
        assert is_controlled_by(state, UBII, GERMANS)

    def test_treveri(self, state):
        assert count_pieces(state, TREVERI, BELGAE, WARBAND) == 1
        assert count_pieces(state, TREVERI, BELGAE, ALLY) == 1
        assert state["tribes"][TRIBE_TREVERI]["allied_faction"] == BELGAE
        assert is_controlled_by(state, TREVERI, BELGAE)

    def test_veneti_dispersed(self, state):
        assert state["tribes"][TRIBE_VENETI]["status"] == DISPERSED

    def test_mandubii(self, state):
        assert count_pieces(state, MANDUBII, ARVERNI, WARBAND) == 3
        assert count_pieces(state, MANDUBII, ARVERNI, ALLY) == 1
        assert count_pieces(state, MANDUBII, AEDUI, WARBAND) == 2
        assert state["tribes"][TRIBE_SENONES]["allied_faction"] == ARVERNI
        assert is_controlled_by(state, MANDUBII, ARVERNI)

    def test_aedui_region(self, state):
        assert count_pieces(state, AEDUI_REGION, AEDUI, WARBAND) == 2
        assert count_pieces(state, AEDUI_REGION, AEDUI, ALLY) == 1
        assert state["tribes"][TRIBE_AEDUI]["allied_faction"] == AEDUI
        assert is_controlled_by(state, AEDUI_REGION, AEDUI)

    def test_arverni_region(self, state):
        assert count_pieces(state, ARVERNI_REGION, ARVERNI, WARBAND) == 2
        assert count_pieces(state, ARVERNI_REGION, ARVERNI, ALLY) == 1
        assert state["tribes"][TRIBE_ARVERNI]["allied_faction"] == ARVERNI
        assert is_controlled_by(state, ARVERNI_REGION, ARVERNI)

    def test_provincia(self, state):
        assert count_pieces(state, PROVINCIA, ROMANS, AUXILIA) == 2
        assert count_pieces(state, PROVINCIA, ROMANS, FORT) == 1
        assert is_controlled_by(state, PROVINCIA, ROMANS)

    def test_empty_regions(self, state):
        for region in (CARNUTES, PICTONES, BITURIGES, SEQUANI):
            assert count_pieces(state, region) == 0

    def test_deck_has_winter_cards(self, state):
        winter_count = state["deck"].count(WINTER_CARD)
        assert winter_count == 5

    def test_deck_size(self, state):
        # 70 events + 5 winters = 75 cards total
        assert len(state["deck"]) == 75


# ============================================================================
# RECONQUEST OF GAUL — KEY CHECKS
# ============================================================================

class TestReconquest:
    """Verify Reconquest of Gaul setup."""

    @pytest.fixture
    def state(self):
        return setup_scenario(SCENARIO_RECONQUEST, seed=42)

    def test_resources(self, state):
        assert state["resources"][ARVERNI] == 10
        assert state["resources"][BELGAE] == 10
        assert state["resources"][AEDUI] == 15
        assert state["resources"][ROMANS] == 20

    def test_senate(self, state):
        assert state["senate"]["position"] == INTRIGUE

    def test_legions_track(self, state):
        assert state["legions_track"][LEGIONS_ROW_BOTTOM] == 4

    def test_morini(self, state):
        assert count_pieces(state, MORINI, BELGAE, WARBAND) == 4
        assert count_pieces(state, MORINI, BELGAE, ALLY) == 2
        assert count_pieces(state, MORINI, ROMANS, LEGION) == 1
        assert count_pieces(state, MORINI, ROMANS, AUXILIA) == 1
        assert state["tribes"][TRIBE_MORINI]["allied_faction"] == BELGAE
        assert state["tribes"][TRIBE_MENAPII]["allied_faction"] == BELGAE

    def test_provincia(self, state):
        assert get_leader_in_region(state, PROVINCIA, ROMANS) == CAESAR
        assert count_pieces(state, PROVINCIA, ROMANS, LEGION) == 4
        assert count_pieces(state, PROVINCIA, ROMANS, AUXILIA) == 6

    def test_veneti_dispersed_gathering(self, state):
        assert state["tribes"][TRIBE_VENETI]["status"] == DISPERSED_GATHERING

    def test_aedui_citadel(self, state):
        assert count_pieces(state, AEDUI_REGION, AEDUI, CITADEL) == 1

    def test_deck_size(self, state):
        # 60 events + 4 winters = 64
        assert len(state["deck"]) == 64

    def test_validates(self, state):
        assert validate_state(state) == []


# ============================================================================
# THE GREAT REVOLT — KEY CHECKS
# ============================================================================

class TestGreatRevolt:
    """Verify The Great Revolt setup."""

    @pytest.fixture
    def state(self):
        return setup_scenario(SCENARIO_GREAT_REVOLT, seed=42)

    def test_resources(self, state):
        assert state["resources"][BELGAE] == 10
        assert state["resources"][AEDUI] == 15
        assert state["resources"][ARVERNI] == 20
        assert state["resources"][ROMANS] == 20

    def test_senate(self, state):
        assert state["senate"]["position"] == INTRIGUE

    def test_legions_track(self, state):
        assert state["legions_track"][LEGIONS_ROW_BOTTOM] == 2

    def test_belgae_successor_in_sugambri(self, state):
        assert get_leader_in_region(state, SUGAMBRI, BELGAE) == SUCCESSOR

    def test_vercingetorix_in_carnutes(self, state):
        assert get_leader_in_region(state, CARNUTES, ARVERNI) == VERCINGETORIX

    def test_caesar_in_provincia(self, state):
        assert get_leader_in_region(state, PROVINCIA, ROMANS) == CAESAR

    def test_mandubii_massive(self, state):
        assert count_pieces(state, MANDUBII, ROMANS, LEGION) == 8
        assert count_pieces(state, MANDUBII, ROMANS, FORT) == 1
        assert count_pieces(state, MANDUBII, ARVERNI, WARBAND) == 4
        assert count_pieces(state, MANDUBII, AEDUI, WARBAND) == 4

    def test_arverni_citadel_gergovia(self, state):
        assert count_pieces(state, ARVERNI_REGION, ARVERNI, CITADEL) == 1
        assert state["tribes"][TRIBE_ARVERNI]["allied_faction"] == ARVERNI

    def test_helvii_roman_ally(self, state):
        assert state["tribes"][TRIBE_HELVII]["allied_faction"] == ROMANS

    def test_deck_size(self, state):
        # 45 events + 3 winters = 48
        assert len(state["deck"]) == 48

    def test_validates(self, state):
        assert validate_state(state) == []


# ============================================================================
# ARIOVISTUS — KEY CHECKS
# ============================================================================

class TestAriovistus:
    """Verify Ariovistus scenario setup."""

    @pytest.fixture
    def state(self):
        return setup_scenario(SCENARIO_ARIOVISTUS, seed=42)

    def test_resources(self, state):
        assert state["resources"][BELGAE] == 5
        assert state["resources"][AEDUI] == 10
        assert state["resources"][GERMANS] == 10
        assert state["resources"][ROMANS] == 20

    def test_senate(self, state):
        assert state["senate"]["position"] == INTRIGUE

    def test_legions_track(self, state):
        assert state["legions_track"][LEGIONS_ROW_BOTTOM] == 4
        assert state["legions_track"][LEGIONS_ROW_MIDDLE] == 2

    def test_ariovistus_leader_in_ubii(self, state):
        assert get_leader_in_region(state, UBII, GERMANS) == ARIOVISTUS_LEADER

    def test_boduognatus_in_nervii(self, state):
        assert get_leader_in_region(state, NERVII, BELGAE) == BODUOGNATUS

    def test_diviciacus_in_aedui(self, state):
        assert get_leader_in_region(state, AEDUI_REGION, AEDUI) == DIVICIACUS
        assert state["diviciacus_in_play"] is True

    def test_caesar_in_provincia(self, state):
        assert get_leader_in_region(state, PROVINCIA, ROMANS) == CAESAR

    def test_cisalpina_has_german_pieces(self, state):
        assert count_pieces(state, CISALPINA, GERMANS, WARBAND) == 4
        assert count_pieces(state, CISALPINA, GERMANS, ALLY) == 1
        assert state["tribes"][TRIBE_NORI]["allied_faction"] == GERMANS

    def test_sequani_settlement(self, state):
        assert count_pieces(state, SEQUANI, GERMANS, SETTLEMENT) == 1
        assert count_pieces(state, SEQUANI, GERMANS, WARBAND) == 4

    def test_ubii_forces(self, state):
        assert count_pieces(state, UBII, GERMANS, WARBAND) == 8
        assert count_pieces(state, UBII, GERMANS, ALLY) == 2
        assert state["tribes"][TRIBE_UBII]["allied_faction"] == GERMANS

    def test_provincia_forces(self, state):
        assert count_pieces(state, PROVINCIA, ROMANS, LEGION) == 6
        assert count_pieces(state, PROVINCIA, ROMANS, AUXILIA) == 8

    def test_britannia_not_in_play(self, state):
        assert MARKER_BRITANNIA_NOT_IN_PLAY in state["markers"].get(
            BRITANNIA, {}
        )

    def test_arverni_home_markers(self, state):
        for region in (VENETI, CARNUTES, PICTONES, ARVERNI_REGION):
            assert MARKER_ARVERNI_RALLY in state["markers"].get(region, {})

    def test_deck_has_winter_cards(self, state):
        winter_count = state["deck"].count(WINTER_CARD)
        assert winter_count == 3

    def test_deck_size(self, state):
        # 45 events + 3 winters = 48
        assert len(state["deck"]) == 48

    def test_validates(self, state):
        assert validate_state(state) == []


# ============================================================================
# THE GALLIC WAR — KEY CHECKS
# ============================================================================

class TestGallicWar:
    """Verify The Gallic War first half setup (same as Ariovistus)."""

    @pytest.fixture
    def state(self):
        return setup_scenario(SCENARIO_GALLIC_WAR, seed=42)

    def test_is_gallic_war_scenario(self, state):
        assert state["scenario"] == SCENARIO_GALLIC_WAR

    def test_same_as_ariovistus_resources(self, state):
        assert state["resources"][BELGAE] == 5
        assert state["resources"][AEDUI] == 10
        assert state["resources"][GERMANS] == 10
        assert state["resources"][ROMANS] == 20

    def test_validates(self, state):
        assert validate_state(state) == []


# ============================================================================
# SCENARIO ISOLATION TESTS
# ============================================================================

class TestScenarioIsolation:
    """Test that base and Ariovistus content don't bleed through."""

    def test_base_has_no_settlements(self):
        """Base game state has no Settlements anywhere."""
        for scen in BASE_SCENARIOS:
            state = setup_scenario(scen, seed=42)
            for region in state["spaces"]:
                for faction in FACTIONS:
                    pieces = state["spaces"][region].get("pieces", {}).get(
                        faction, {}
                    )
                    assert pieces.get(SETTLEMENT, 0) == 0, \
                        f"Found Settlement in {region} for {faction} in {scen}"

    def test_base_has_no_diviciacus(self):
        """Diviciacus piece is not on map in base game scenarios."""
        for scen in BASE_SCENARIOS:
            state = setup_scenario(scen, seed=42)
            for region in state["spaces"]:
                leader = state["spaces"][region].get("pieces", {}).get(
                    AEDUI, {}
                ).get(LEADER)
                assert leader != DIVICIACUS, \
                    f"Found Diviciacus in {region} in {scen}"

    def test_base_has_no_nori(self):
        """Nori tribe does not exist in base game."""
        for scen in BASE_SCENARIOS:
            state = setup_scenario(scen, seed=42)
            assert TRIBE_NORI not in state["tribes"]

    def test_base_has_no_extra_german_warbands(self):
        """Base game Germans cap is 15, not 30."""
        for scen in BASE_SCENARIOS:
            state = setup_scenario(scen, seed=42)
            total_german_warbands = 0
            for region in state["spaces"]:
                total_german_warbands += count_pieces(
                    state, region, GERMANS, WARBAND
                )
            total_german_warbands += get_available(state, GERMANS, WARBAND)
            assert total_german_warbands == 15, \
                f"German Warbands total = {total_german_warbands} in {scen}"

    def test_ariovistus_has_no_vercingetorix(self):
        """Vercingetorix is not in play in Ariovistus scenarios."""
        for scen in ARIOVISTUS_SCENARIOS:
            state = setup_scenario(scen, seed=42)
            for region in state["spaces"]:
                leader = state["spaces"][region].get("pieces", {}).get(
                    ARVERNI, {}
                ).get(LEADER)
                assert leader != VERCINGETORIX, \
                    f"Found Vercingetorix in {region} in {scen}"

    def test_ariovistus_has_no_catuvellauni(self):
        """Catuvellauni tribe does not exist in Ariovistus."""
        for scen in ARIOVISTUS_SCENARIOS:
            state = setup_scenario(scen, seed=42)
            assert TRIBE_CATUVELLAUNI not in state["tribes"]

    def test_ariovistus_britannia_not_playable(self):
        """Britannia is not playable in Ariovistus."""
        from fs_bot.map.map_data import get_region_data
        for scen in ARIOVISTUS_SCENARIOS:
            rd = get_region_data(BRITANNIA)
            assert not rd.is_playable(scen)

    def test_base_cisalpina_not_playable(self):
        """Cisalpina not playable in base (without Gallia Togata)."""
        from fs_bot.map.map_data import get_region_data
        for scen in BASE_SCENARIOS:
            rd = get_region_data(CISALPINA)
            assert not rd.is_playable(scen)

    def test_base_has_vercingetorix_or_in_available(self):
        """Base game has Vercingetorix on map or in Available."""
        for scen in BASE_SCENARIOS:
            state = setup_scenario(scen, seed=42)
            leader_on_map = find_leader(state, ARVERNI)
            avail = get_available(state, ARVERNI, LEADER)
            # Either on map or in available (for Pax Gallica where he's
            # in the "Spring box" which we track as available until placed)
            assert leader_on_map is not None or avail == 1, \
                f"No Arverni leader found in {scen}"

    def test_ariovistus_has_settlements_available(self):
        """Ariovistus starts with 6 Settlements (some on map, rest Available)."""
        for scen in ARIOVISTUS_SCENARIOS:
            state = setup_scenario(scen, seed=42)
            on_map = 0
            for region in state["spaces"]:
                on_map += count_pieces(state, region, GERMANS, SETTLEMENT)
            avail = get_available(state, GERMANS, SETTLEMENT)
            assert on_map + avail == 6, \
                f"Settlement total = {on_map + avail} in {scen}"

    def test_ariovistus_german_warbands_cap_30(self):
        """Ariovistus Germans have 30 Warbands total."""
        for scen in ARIOVISTUS_SCENARIOS:
            state = setup_scenario(scen, seed=42)
            on_map = 0
            for region in state["spaces"]:
                on_map += count_pieces(state, region, GERMANS, WARBAND)
            avail = get_available(state, GERMANS, WARBAND)
            assert on_map + avail == 30, \
                f"German Warbands total = {on_map + avail} in {scen}"

    def test_base_germans_no_resources(self):
        """Germans don't track resources in base game — §1.8."""
        for scen in BASE_SCENARIOS:
            state = setup_scenario(scen, seed=42)
            assert GERMANS not in state["resources"]

    def test_ariovistus_germans_have_resources(self):
        """Germans track resources in Ariovistus — A1.8."""
        for scen in ARIOVISTUS_SCENARIOS:
            state = setup_scenario(scen, seed=42)
            assert GERMANS in state["resources"]
