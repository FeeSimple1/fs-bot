"""
Tests for the map data module.

Tests every adjacency pair from Map Transcription, Rhenus and coastal flags,
playability gating per scenario, tribe-to-region mappings, CV values.
"""

import pytest

from fs_bot.rules_consts import (
    # Regions
    MORINI, NERVII, ATREBATES, SUGAMBRI, UBII,
    TREVERI, CARNUTES, MANDUBII, VENETI, PICTONES,
    BITURIGES, AEDUI_REGION, SEQUANI, ARVERNI_REGION,
    BRITANNIA, PROVINCIA, CISALPINA,
    ALL_REGIONS,
    # Region groups
    BELGICA, GERMANIA, CELTICA, BRITANNIA_GROUP,
    PROVINCIA_GROUP, CISALPINA_GROUP,
    # Adjacency
    ADJ_NORMAL, ADJ_RHENUS, ADJ_COASTAL,
    ADJACENCIES,
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
    BASE_TRIBES, ARIOVISTUS_TRIBES,
    # Cities
    CITY_CENABUM, CITY_ALESIA, CITY_AVARICUM,
    CITY_BIBRACTE, CITY_VESONTIO, CITY_GERGOVIA,
    # Scenarios
    SCENARIO_PAX_GALLICA, SCENARIO_RECONQUEST, SCENARIO_GREAT_REVOLT,
    SCENARIO_ARIOVISTUS, SCENARIO_GALLIC_WAR,
    # Factions
    AEDUI, ARVERNI, GERMANS,
    # Markers
    MARKER_GALLIA_TOGATA,
    # CVs
    REGION_CONTROL_VALUES, CISALPINA_CV_ARIOVISTUS,
)

from fs_bot.map.map_data import (
    get_region_data,
    get_tribe_data,
    get_adjacent,
    get_adjacent_with_type,
    is_adjacent,
    get_adjacency_type,
    get_region_for_tribe,
    get_tribes_in_region,
    get_playable_regions,
    get_control_value,
    get_tribe_city,
    get_tribe_restriction,
    is_city_tribe,
    get_region_group,
    ALL_REGION_DATA,
)


# ============================================================================
# ADJACENCY TESTS — every pair from Map Transcription
# ============================================================================

class TestAdjacency:
    """Test every adjacency pair from Map Transcription."""

    # Morini adjacencies
    def test_morini_nervii(self):
        assert is_adjacent(MORINI, NERVII)
        assert get_adjacency_type(MORINI, NERVII) == ADJ_NORMAL

    def test_morini_atrebates(self):
        assert is_adjacent(MORINI, ATREBATES)
        assert get_adjacency_type(MORINI, ATREBATES) == ADJ_NORMAL

    def test_morini_sugambri_rhenus(self):
        assert is_adjacent(MORINI, SUGAMBRI)
        assert get_adjacency_type(MORINI, SUGAMBRI) == ADJ_RHENUS

    def test_morini_britannia_coastal(self):
        assert is_adjacent(MORINI, BRITANNIA)
        assert get_adjacency_type(MORINI, BRITANNIA) == ADJ_COASTAL

    # Nervii adjacencies
    def test_nervii_atrebates(self):
        assert is_adjacent(NERVII, ATREBATES)
        assert get_adjacency_type(NERVII, ATREBATES) == ADJ_NORMAL

    def test_nervii_treveri(self):
        assert is_adjacent(NERVII, TREVERI)
        assert get_adjacency_type(NERVII, TREVERI) == ADJ_NORMAL

    def test_nervii_sugambri_rhenus(self):
        assert is_adjacent(NERVII, SUGAMBRI)
        assert get_adjacency_type(NERVII, SUGAMBRI) == ADJ_RHENUS

    # Atrebates adjacencies
    def test_atrebates_treveri(self):
        assert is_adjacent(ATREBATES, TREVERI)

    def test_atrebates_carnutes(self):
        assert is_adjacent(ATREBATES, CARNUTES)

    def test_atrebates_mandubii(self):
        assert is_adjacent(ATREBATES, MANDUBII)

    def test_atrebates_britannia_coastal(self):
        assert is_adjacent(ATREBATES, BRITANNIA)
        assert get_adjacency_type(ATREBATES, BRITANNIA) == ADJ_COASTAL

    def test_atrebates_veneti(self):
        assert is_adjacent(ATREBATES, VENETI)

    # Sugambri adjacencies
    def test_sugambri_ubii(self):
        assert is_adjacent(SUGAMBRI, UBII)
        assert get_adjacency_type(SUGAMBRI, UBII) == ADJ_NORMAL

    def test_sugambri_treveri_rhenus(self):
        assert is_adjacent(SUGAMBRI, TREVERI)
        assert get_adjacency_type(SUGAMBRI, TREVERI) == ADJ_RHENUS

    # Ubii adjacencies
    def test_ubii_treveri_rhenus(self):
        assert is_adjacent(UBII, TREVERI)
        assert get_adjacency_type(UBII, TREVERI) == ADJ_RHENUS

    def test_ubii_sequani_rhenus(self):
        assert is_adjacent(UBII, SEQUANI)
        assert get_adjacency_type(UBII, SEQUANI) == ADJ_RHENUS

    def test_ubii_cisalpina(self):
        assert is_adjacent(UBII, CISALPINA)
        assert get_adjacency_type(UBII, CISALPINA) == ADJ_NORMAL

    # Treveri adjacencies
    def test_treveri_mandubii(self):
        assert is_adjacent(TREVERI, MANDUBII)

    def test_treveri_sequani(self):
        assert is_adjacent(TREVERI, SEQUANI)

    # Carnutes adjacencies
    def test_carnutes_mandubii(self):
        assert is_adjacent(CARNUTES, MANDUBII)

    def test_carnutes_pictones(self):
        assert is_adjacent(CARNUTES, PICTONES)

    def test_carnutes_bituriges(self):
        assert is_adjacent(CARNUTES, BITURIGES)

    def test_carnutes_veneti(self):
        assert is_adjacent(CARNUTES, VENETI)

    # Mandubii adjacencies
    def test_mandubii_aedui(self):
        assert is_adjacent(MANDUBII, AEDUI_REGION)

    def test_mandubii_sequani(self):
        assert is_adjacent(MANDUBII, SEQUANI)

    def test_mandubii_bituriges(self):
        assert is_adjacent(MANDUBII, BITURIGES)

    # Veneti adjacencies
    def test_veneti_pictones(self):
        assert is_adjacent(VENETI, PICTONES)

    def test_veneti_britannia_coastal(self):
        assert is_adjacent(VENETI, BRITANNIA)
        assert get_adjacency_type(VENETI, BRITANNIA) == ADJ_COASTAL

    # Pictones adjacencies
    def test_pictones_bituriges(self):
        assert is_adjacent(PICTONES, BITURIGES)

    def test_pictones_arverni(self):
        assert is_adjacent(PICTONES, ARVERNI_REGION)

    # Bituriges adjacencies
    def test_bituriges_aedui(self):
        assert is_adjacent(BITURIGES, AEDUI_REGION)

    def test_bituriges_arverni(self):
        assert is_adjacent(BITURIGES, ARVERNI_REGION)

    # Aedui adjacencies
    def test_aedui_sequani(self):
        assert is_adjacent(AEDUI_REGION, SEQUANI)

    def test_aedui_arverni(self):
        assert is_adjacent(AEDUI_REGION, ARVERNI_REGION)

    def test_aedui_provincia(self):
        assert is_adjacent(AEDUI_REGION, PROVINCIA)

    # Sequani adjacencies
    def test_sequani_arverni(self):
        assert is_adjacent(SEQUANI, ARVERNI_REGION)

    def test_sequani_provincia(self):
        assert is_adjacent(SEQUANI, PROVINCIA)

    def test_sequani_cisalpina(self):
        assert is_adjacent(SEQUANI, CISALPINA)

    # Arverni adjacencies
    def test_arverni_provincia(self):
        assert is_adjacent(ARVERNI_REGION, PROVINCIA)

    # Provincia adjacencies
    def test_provincia_cisalpina(self):
        assert is_adjacent(PROVINCIA, CISALPINA)

    # Non-adjacent pairs
    def test_not_adjacent_morini_carnutes(self):
        assert not is_adjacent(MORINI, CARNUTES)

    def test_not_adjacent_britannia_ubii(self):
        assert not is_adjacent(BRITANNIA, UBII)

    def test_not_adjacent_provincia_morini(self):
        assert not is_adjacent(PROVINCIA, MORINI)

    # Bidirectional
    def test_adjacency_is_bidirectional(self):
        for a, b, _ in ADJACENCIES:
            assert is_adjacent(a, b), f"{a} -> {b} missing"
            assert is_adjacent(b, a), f"{b} -> {a} missing"

    def test_adjacency_type_is_bidirectional(self):
        for a, b, adj_type in ADJACENCIES:
            assert get_adjacency_type(a, b) == adj_type
            assert get_adjacency_type(b, a) == adj_type


# ============================================================================
# RHENUS AND COASTAL FLAGS
# ============================================================================

class TestRhenusAndCoastal:
    """Test Rhenus and coastal adjacency flags."""

    def test_all_rhenus_crossings(self):
        """Verify all Rhenus crossings from Map Transcription."""
        rhenus_pairs = [
            (MORINI, SUGAMBRI),
            (NERVII, SUGAMBRI),
            (SUGAMBRI, TREVERI),
            (UBII, TREVERI),
            (UBII, SEQUANI),
        ]
        for a, b in rhenus_pairs:
            assert get_adjacency_type(a, b) == ADJ_RHENUS, \
                f"{a}-{b} should be Rhenus"

    def test_all_coastal_connections(self):
        """Verify all coastal connections from Map Transcription."""
        coastal_pairs = [
            (MORINI, BRITANNIA),
            (ATREBATES, BRITANNIA),
            (VENETI, BRITANNIA),
        ]
        for a, b in coastal_pairs:
            assert get_adjacency_type(a, b) == ADJ_COASTAL, \
                f"{a}-{b} should be coastal"

    def test_ubii_cisalpina_is_normal(self):
        """Ubii-Cisalpina is normal, not Rhenus."""
        assert get_adjacency_type(UBII, CISALPINA) == ADJ_NORMAL


# ============================================================================
# PLAYABILITY GATING PER SCENARIO
# ============================================================================

class TestPlayability:
    """Test scenario-dependent region playability."""

    def test_britannia_playable_in_base(self):
        for scen in (SCENARIO_PAX_GALLICA, SCENARIO_RECONQUEST,
                     SCENARIO_GREAT_REVOLT):
            rd = get_region_data(BRITANNIA)
            assert rd.is_playable(scen), \
                f"Britannia should be playable in {scen}"

    def test_britannia_not_playable_in_ariovistus(self):
        for scen in (SCENARIO_ARIOVISTUS, SCENARIO_GALLIC_WAR):
            rd = get_region_data(BRITANNIA)
            assert not rd.is_playable(scen), \
                f"Britannia should NOT be playable in {scen}"

    def test_cisalpina_not_playable_in_base(self):
        for scen in (SCENARIO_PAX_GALLICA, SCENARIO_RECONQUEST,
                     SCENARIO_GREAT_REVOLT):
            rd = get_region_data(CISALPINA)
            assert not rd.is_playable(scen), \
                f"Cisalpina should NOT be playable in {scen}"

    def test_cisalpina_playable_in_base_with_gallia_togata(self):
        rd = get_region_data(CISALPINA)
        caps = {MARKER_GALLIA_TOGATA: True}
        assert rd.is_playable(SCENARIO_PAX_GALLICA, capabilities=caps)

    def test_cisalpina_playable_in_ariovistus(self):
        for scen in (SCENARIO_ARIOVISTUS, SCENARIO_GALLIC_WAR):
            rd = get_region_data(CISALPINA)
            assert rd.is_playable(scen), \
                f"Cisalpina should be playable in {scen}"

    def test_normal_regions_always_playable(self):
        normal_regions = [
            MORINI, NERVII, ATREBATES, SUGAMBRI, UBII,
            TREVERI, CARNUTES, MANDUBII, VENETI, PICTONES,
            BITURIGES, AEDUI_REGION, SEQUANI, ARVERNI_REGION,
            PROVINCIA,
        ]
        for scen in (SCENARIO_PAX_GALLICA, SCENARIO_ARIOVISTUS):
            for region in normal_regions:
                rd = get_region_data(region)
                assert rd.is_playable(scen), \
                    f"{region} should be playable in {scen}"

    def test_get_playable_regions_base(self):
        playable = get_playable_regions(SCENARIO_PAX_GALLICA)
        assert BRITANNIA in playable
        assert CISALPINA not in playable
        # 16 regions playable (17 minus Cisalpina)
        assert len(playable) == 16

    def test_get_playable_regions_ariovistus(self):
        playable = get_playable_regions(SCENARIO_ARIOVISTUS)
        assert BRITANNIA not in playable
        assert CISALPINA in playable
        # 16 regions playable (17 minus Britannia)
        assert len(playable) == 16

    def test_get_adjacent_filters_unplayable(self):
        """Adjacency queries respect playability."""
        # In Ariovistus, Morini's adjacencies should not include Britannia
        adj = get_adjacent(MORINI, scenario=SCENARIO_ARIOVISTUS)
        assert BRITANNIA not in adj

        # In base, Ubii's adjacencies should not include Cisalpina
        adj_base = get_adjacent(UBII, scenario=SCENARIO_PAX_GALLICA)
        assert CISALPINA not in adj_base


# ============================================================================
# TRIBE-TO-REGION MAPPINGS
# ============================================================================

class TestTribeRegionMappings:
    """Test tribe-to-region mappings from Map Transcription."""

    def test_belgica_tribes(self):
        assert get_region_for_tribe(TRIBE_MENAPII) == MORINI
        assert get_region_for_tribe(TRIBE_MORINI) == MORINI
        assert get_region_for_tribe(TRIBE_EBURONES) == NERVII
        assert get_region_for_tribe(TRIBE_NERVII) == NERVII
        assert get_region_for_tribe(TRIBE_BELLOVACI) == ATREBATES
        assert get_region_for_tribe(TRIBE_ATREBATES) == ATREBATES
        assert get_region_for_tribe(TRIBE_REMI) == ATREBATES

    def test_germania_tribes(self):
        assert get_region_for_tribe(TRIBE_SUEBI_NORTH) == SUGAMBRI
        assert get_region_for_tribe(TRIBE_SUGAMBRI) == SUGAMBRI
        assert get_region_for_tribe(TRIBE_SUEBI_SOUTH) == UBII
        assert get_region_for_tribe(TRIBE_UBII) == UBII

    def test_celtica_tribes(self):
        assert get_region_for_tribe(TRIBE_TREVERI) == TREVERI
        assert get_region_for_tribe(TRIBE_CARNUTES) == CARNUTES
        assert get_region_for_tribe(TRIBE_AULERCI) == CARNUTES
        assert get_region_for_tribe(TRIBE_MANDUBII) == MANDUBII
        assert get_region_for_tribe(TRIBE_SENONES) == MANDUBII
        assert get_region_for_tribe(TRIBE_LINGONES) == MANDUBII
        assert get_region_for_tribe(TRIBE_VENETI) == VENETI
        assert get_region_for_tribe(TRIBE_NAMNETES) == VENETI
        assert get_region_for_tribe(TRIBE_PICTONES) == PICTONES
        assert get_region_for_tribe(TRIBE_SANTONES) == PICTONES
        assert get_region_for_tribe(TRIBE_BITURIGES) == BITURIGES
        assert get_region_for_tribe(TRIBE_AEDUI) == AEDUI_REGION
        assert get_region_for_tribe(TRIBE_SEQUANI) == SEQUANI
        assert get_region_for_tribe(TRIBE_HELVETII) == SEQUANI
        assert get_region_for_tribe(TRIBE_ARVERNI) == ARVERNI_REGION
        assert get_region_for_tribe(TRIBE_CADURCI) == ARVERNI_REGION
        assert get_region_for_tribe(TRIBE_VOLCAE) == ARVERNI_REGION

    def test_britannia_tribe(self):
        assert get_region_for_tribe(TRIBE_CATUVELLAUNI) == BRITANNIA

    def test_provincia_tribe(self):
        assert get_region_for_tribe(TRIBE_HELVII) == PROVINCIA

    def test_nori_tribe(self):
        assert get_region_for_tribe(TRIBE_NORI) == CISALPINA

    def test_tribes_in_region_base(self):
        """Tribes returned match Map Transcription for base game."""
        tribes = get_tribes_in_region(MORINI, SCENARIO_PAX_GALLICA)
        assert TRIBE_MENAPII in tribes
        assert TRIBE_MORINI in tribes
        assert len(tribes) == 2

    def test_tribes_in_region_mandubii(self):
        tribes = get_tribes_in_region(MANDUBII, SCENARIO_PAX_GALLICA)
        assert set(tribes) == {TRIBE_MANDUBII, TRIBE_SENONES, TRIBE_LINGONES}

    def test_britannia_has_catuvellauni_in_base(self):
        tribes = get_tribes_in_region(BRITANNIA, SCENARIO_PAX_GALLICA)
        assert TRIBE_CATUVELLAUNI in tribes

    def test_britannia_has_no_tribes_in_ariovistus(self):
        tribes = get_tribes_in_region(BRITANNIA, SCENARIO_ARIOVISTUS)
        assert len(tribes) == 0

    def test_cisalpina_has_no_tribes_in_base(self):
        tribes = get_tribes_in_region(CISALPINA, SCENARIO_PAX_GALLICA)
        assert len(tribes) == 0

    def test_cisalpina_has_nori_in_ariovistus(self):
        tribes = get_tribes_in_region(CISALPINA, SCENARIO_ARIOVISTUS)
        assert TRIBE_NORI in tribes
        assert len(tribes) == 1

    def test_base_tribe_count(self):
        assert len(BASE_TRIBES) == 30

    def test_ariovistus_tribe_count(self):
        assert len(ARIOVISTUS_TRIBES) == 30

    def test_nori_replaces_catuvellauni(self):
        assert TRIBE_CATUVELLAUNI in BASE_TRIBES
        assert TRIBE_CATUVELLAUNI not in ARIOVISTUS_TRIBES
        assert TRIBE_NORI in ARIOVISTUS_TRIBES
        assert TRIBE_NORI not in BASE_TRIBES


# ============================================================================
# CONTROL VALUES
# ============================================================================

class TestControlValues:
    """Test region control values from Map Transcription."""

    def test_belgica_cvs(self):
        assert get_control_value(MORINI, SCENARIO_PAX_GALLICA) == 2
        assert get_control_value(NERVII, SCENARIO_PAX_GALLICA) == 2
        assert get_control_value(ATREBATES, SCENARIO_PAX_GALLICA) == 3

    def test_germania_cvs(self):
        """Germania CVs = 1 (tribe count excluding Suebi)."""
        assert get_control_value(SUGAMBRI, SCENARIO_PAX_GALLICA) == 1
        assert get_control_value(UBII, SCENARIO_PAX_GALLICA) == 1

    def test_celtica_cvs(self):
        assert get_control_value(TREVERI, SCENARIO_PAX_GALLICA) == 1
        assert get_control_value(CARNUTES, SCENARIO_PAX_GALLICA) == 2
        assert get_control_value(MANDUBII, SCENARIO_PAX_GALLICA) == 3
        assert get_control_value(VENETI, SCENARIO_PAX_GALLICA) == 2
        assert get_control_value(PICTONES, SCENARIO_PAX_GALLICA) == 2
        assert get_control_value(BITURIGES, SCENARIO_PAX_GALLICA) == 1
        assert get_control_value(AEDUI_REGION, SCENARIO_PAX_GALLICA) == 1
        assert get_control_value(SEQUANI, SCENARIO_PAX_GALLICA) == 2
        assert get_control_value(ARVERNI_REGION, SCENARIO_PAX_GALLICA) == 3

    def test_other_cvs(self):
        assert get_control_value(BRITANNIA, SCENARIO_PAX_GALLICA) == 1
        assert get_control_value(PROVINCIA, SCENARIO_PAX_GALLICA) == 1
        assert get_control_value(CISALPINA, SCENARIO_PAX_GALLICA) == 0

    def test_cisalpina_cv_ariovistus(self):
        """Cisalpina CV = 1 in Ariovistus — A1.3.2."""
        assert get_control_value(CISALPINA, SCENARIO_ARIOVISTUS) == 1

    def test_cisalpina_cv_base(self):
        assert get_control_value(CISALPINA, SCENARIO_PAX_GALLICA) == 0


# ============================================================================
# TRIBE STACKING RESTRICTIONS AND CITIES
# ============================================================================

class TestTribeProperties:
    """Test tribe stacking restrictions and cities."""

    def test_aedui_only(self):
        assert get_tribe_restriction(TRIBE_AEDUI) == AEDUI

    def test_arverni_only(self):
        assert get_tribe_restriction(TRIBE_ARVERNI) == ARVERNI

    def test_suebi_germanic_only(self):
        assert get_tribe_restriction(TRIBE_SUEBI_NORTH) == GERMANS
        assert get_tribe_restriction(TRIBE_SUEBI_SOUTH) == GERMANS

    def test_no_restriction(self):
        assert get_tribe_restriction(TRIBE_REMI) is None
        assert get_tribe_restriction(TRIBE_CARNUTES) is None

    def test_city_tribes(self):
        assert get_tribe_city(TRIBE_CARNUTES) == CITY_CENABUM
        assert get_tribe_city(TRIBE_MANDUBII) == CITY_ALESIA
        assert get_tribe_city(TRIBE_BITURIGES) == CITY_AVARICUM
        assert get_tribe_city(TRIBE_AEDUI) == CITY_BIBRACTE
        assert get_tribe_city(TRIBE_SEQUANI) == CITY_VESONTIO
        assert get_tribe_city(TRIBE_ARVERNI) == CITY_GERGOVIA

    def test_non_city_tribes(self):
        assert get_tribe_city(TRIBE_REMI) is None
        assert get_tribe_city(TRIBE_MENAPII) is None

    def test_is_city_tribe(self):
        assert is_city_tribe(TRIBE_CARNUTES)
        assert not is_city_tribe(TRIBE_REMI)


# ============================================================================
# REGION GROUPS
# ============================================================================

class TestRegionGroups:
    """Test region-to-group mappings."""

    def test_belgica(self):
        assert get_region_group(MORINI) == BELGICA
        assert get_region_group(NERVII) == BELGICA
        assert get_region_group(ATREBATES) == BELGICA

    def test_germania(self):
        assert get_region_group(SUGAMBRI) == GERMANIA
        assert get_region_group(UBII) == GERMANIA

    def test_celtica(self):
        for r in (TREVERI, CARNUTES, MANDUBII, VENETI, PICTONES,
                  BITURIGES, AEDUI_REGION, SEQUANI, ARVERNI_REGION):
            assert get_region_group(r) == CELTICA

    def test_special_regions(self):
        assert get_region_group(BRITANNIA) == BRITANNIA_GROUP
        assert get_region_group(PROVINCIA) == PROVINCIA_GROUP
        assert get_region_group(CISALPINA) == CISALPINA_GROUP

    def test_all_regions_have_groups(self):
        for region in ALL_REGIONS:
            assert get_region_group(region) is not None
