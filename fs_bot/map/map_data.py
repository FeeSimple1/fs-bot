"""
Map data module — Parsed from Map Transcription reference document.

Provides region data, tribe data, adjacency queries, and
scenario-dependent playability. All constants imported from rules_consts.py.
"""

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
    REGION_TO_GROUP, REGION_CONTROL_VALUES,
    CISALPINA_CV_ARIOVISTUS,
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
    TRIBE_TO_REGION, TRIBE_FACTION_RESTRICTION,
    # Cities
    CITY_CENABUM, CITY_ALESIA, CITY_AVARICUM,
    CITY_BIBRACTE, CITY_VESONTIO, CITY_GERGOVIA,
    TRIBE_TO_CITY,
    # Adjacency
    ADJ_NORMAL, ADJ_RHENUS, ADJ_COASTAL,
    ADJACENCIES,
    # Scenarios
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    SCENARIO_ARIOVISTUS, SCENARIO_GALLIC_WAR,
    # Factions
    AEDUI, ARVERNI, GERMANS,
    # Markers
    MARKER_GALLIA_TOGATA,
)


# ============================================================================
# REGION DATA
# ============================================================================
# Each region: {name, group, base_cv, tribes: [tribe_name, ...]}
# Built from Map Transcription.

_REGION_TRIBES = {
    MORINI: (TRIBE_MENAPII, TRIBE_MORINI),
    NERVII: (TRIBE_EBURONES, TRIBE_NERVII),
    ATREBATES: (TRIBE_BELLOVACI, TRIBE_ATREBATES, TRIBE_REMI),
    SUGAMBRI: (TRIBE_SUEBI_NORTH, TRIBE_SUGAMBRI),
    UBII: (TRIBE_SUEBI_SOUTH, TRIBE_UBII),
    TREVERI: (TRIBE_TREVERI,),
    CARNUTES: (TRIBE_CARNUTES, TRIBE_AULERCI),
    MANDUBII: (TRIBE_MANDUBII, TRIBE_SENONES, TRIBE_LINGONES),
    VENETI: (TRIBE_VENETI, TRIBE_NAMNETES),
    PICTONES: (TRIBE_PICTONES, TRIBE_SANTONES),
    BITURIGES: (TRIBE_BITURIGES,),
    AEDUI_REGION: (TRIBE_AEDUI,),
    SEQUANI: (TRIBE_SEQUANI, TRIBE_HELVETII),
    ARVERNI_REGION: (TRIBE_ARVERNI, TRIBE_CADURCI, TRIBE_VOLCAE),
    BRITANNIA: (TRIBE_CATUVELLAUNI,),
    PROVINCIA: (TRIBE_HELVII,),
    CISALPINA: (),  # No tribes in base; Nori in Ariovistus
}

# Ariovistus overrides: Britannia has no tribes, Cisalpina gets Nori
_REGION_TRIBES_ARIOVISTUS_OVERRIDES = {
    BRITANNIA: (),          # Not playable — A1.3.4
    CISALPINA: (TRIBE_NORI,),  # Nori tribe added — A1.3.2
}


# ============================================================================
# ADJACENCY INDEX
# ============================================================================
# Build bidirectional adjacency lookup from the canonical ADJACENCIES tuple.

_ADJACENCY_MAP = {}  # {region: {adjacent_region: adj_type}}

for _a, _b, _adj_type in ADJACENCIES:
    _ADJACENCY_MAP.setdefault(_a, {})[_b] = _adj_type
    _ADJACENCY_MAP.setdefault(_b, {})[_a] = _adj_type


# ============================================================================
# REGION DATA STRUCTURE
# ============================================================================

class RegionData:
    """Immutable data about a region."""
    __slots__ = ("name", "group", "base_cv", "base_tribes",
                 "ariovistus_tribes")

    def __init__(self, name, group, base_cv, base_tribes, ariovistus_tribes):
        self.name = name
        self.group = group
        self.base_cv = base_cv
        self.base_tribes = base_tribes
        self.ariovistus_tribes = ariovistus_tribes

    def get_cv(self, scenario):
        """Get control value for this region in the given scenario."""
        if scenario in ARIOVISTUS_SCENARIOS and self.name == CISALPINA:
            return CISALPINA_CV_ARIOVISTUS
        return self.base_cv

    def get_tribes(self, scenario):
        """Get tribes for this region in the given scenario."""
        if scenario in ARIOVISTUS_SCENARIOS:
            return self.ariovistus_tribes
        return self.base_tribes

    def is_playable(self, scenario, capabilities=None):
        """Check if this region is playable in the given scenario.

        Args:
            scenario: The active scenario identifier.
            capabilities: Set/dict of active capabilities, checked for
                Gallia Togata making Cisalpina playable in base game.
        """
        if self.name == BRITANNIA:
            # Britannia: playable in base game, NOT playable in Ariovistus
            # — A1.3.4
            return scenario in BASE_SCENARIOS
        if self.name == CISALPINA:
            # Cisalpina: always playable in Ariovistus — A1.3.2
            # In base game: only playable if Gallia Togata event — §1.4.2
            if scenario in ARIOVISTUS_SCENARIOS:
                return True
            if capabilities and MARKER_GALLIA_TOGATA in capabilities:
                return True
            return False
        # All other regions are always playable
        return True


# Build the master region data dictionary
ALL_REGION_DATA = {}
for _region in ALL_REGIONS:
    _group = REGION_TO_GROUP[_region]
    _base_cv = REGION_CONTROL_VALUES[_region]
    _base_tribes = _REGION_TRIBES[_region]
    _ario_tribes = _REGION_TRIBES_ARIOVISTUS_OVERRIDES.get(
        _region, _base_tribes
    )
    ALL_REGION_DATA[_region] = RegionData(
        name=_region,
        group=_group,
        base_cv=_base_cv,
        base_tribes=_base_tribes,
        ariovistus_tribes=_ario_tribes,
    )


# ============================================================================
# TRIBE DATA STRUCTURE
# ============================================================================

class TribeData:
    """Immutable data about a tribe."""
    __slots__ = ("name", "region", "city", "faction_restriction")

    def __init__(self, name, region, city, faction_restriction):
        self.name = name
        self.region = region
        self.city = city
        self.faction_restriction = faction_restriction


# Build tribe data for all tribes (both base and Ariovistus)
_ALL_TRIBE_NAMES = set(BASE_TRIBES) | set(ARIOVISTUS_TRIBES)
ALL_TRIBE_DATA = {}
for _tribe in _ALL_TRIBE_NAMES:
    ALL_TRIBE_DATA[_tribe] = TribeData(
        name=_tribe,
        region=TRIBE_TO_REGION[_tribe],
        city=TRIBE_TO_CITY.get(_tribe),
        faction_restriction=TRIBE_FACTION_RESTRICTION.get(_tribe),
    )


# ============================================================================
# QUERY HELPERS
# ============================================================================

def get_region_data(region):
    """Get RegionData for a region.

    Args:
        region: Region name constant from rules_consts.

    Returns:
        RegionData object.

    Raises:
        KeyError: If region is not a valid region.
    """
    return ALL_REGION_DATA[region]


def get_tribe_data(tribe):
    """Get TribeData for a tribe.

    Args:
        tribe: Tribe name constant from rules_consts.

    Returns:
        TribeData object.

    Raises:
        KeyError: If tribe is not a valid tribe.
    """
    return ALL_TRIBE_DATA[tribe]


def get_adjacent(region, scenario=None, capabilities=None):
    """Get list of regions adjacent to the given region.

    Only returns playable regions if scenario is provided.

    Args:
        region: Region name constant.
        scenario: Optional scenario to filter by playability.
        capabilities: Optional active capabilities set/dict.

    Returns:
        Tuple of adjacent region names.
    """
    adj = _ADJACENCY_MAP.get(region, {})
    if scenario is None:
        return tuple(adj.keys())
    return tuple(
        r for r in adj
        if ALL_REGION_DATA[r].is_playable(scenario, capabilities)
    )


def get_adjacent_with_type(region, scenario=None, capabilities=None):
    """Get adjacent regions with their adjacency types.

    Args:
        region: Region name constant.
        scenario: Optional scenario to filter by playability.
        capabilities: Optional active capabilities set/dict.

    Returns:
        Dict of {adjacent_region: adjacency_type}.
    """
    adj = _ADJACENCY_MAP.get(region, {})
    if scenario is None:
        return dict(adj)
    return {
        r: t for r, t in adj.items()
        if ALL_REGION_DATA[r].is_playable(scenario, capabilities)
    }


def is_adjacent(region_a, region_b):
    """Check if two regions are adjacent.

    Args:
        region_a: First region name.
        region_b: Second region name.

    Returns:
        True if adjacent, False otherwise.
    """
    return region_b in _ADJACENCY_MAP.get(region_a, {})


def get_adjacency_type(region_a, region_b):
    """Get the adjacency type between two regions.

    Args:
        region_a: First region name.
        region_b: Second region name.

    Returns:
        Adjacency type string (ADJ_NORMAL, ADJ_RHENUS, ADJ_COASTAL),
        or None if not adjacent.
    """
    return _ADJACENCY_MAP.get(region_a, {}).get(region_b)


def get_region_for_tribe(tribe):
    """Get the region containing a tribe.

    Args:
        tribe: Tribe name constant.

    Returns:
        Region name constant.
    """
    return TRIBE_TO_REGION[tribe]


def get_tribes_in_region(region, scenario):
    """Get tribes in a region for the given scenario.

    Args:
        region: Region name constant.
        scenario: Scenario identifier.

    Returns:
        Tuple of tribe name constants.
    """
    return ALL_REGION_DATA[region].get_tribes(scenario)


def get_playable_regions(scenario, capabilities=None):
    """Get all playable regions for a scenario.

    Args:
        scenario: Scenario identifier.
        capabilities: Optional active capabilities set/dict.

    Returns:
        Tuple of playable region name constants.
    """
    return tuple(
        r for r in ALL_REGIONS
        if ALL_REGION_DATA[r].is_playable(scenario, capabilities)
    )


def get_control_value(region, scenario):
    """Get control value for a region in a scenario.

    Args:
        region: Region name constant.
        scenario: Scenario identifier.

    Returns:
        Integer control value.
    """
    return ALL_REGION_DATA[region].get_cv(scenario)


def get_tribe_city(tribe):
    """Get the city associated with a tribe, if any.

    Args:
        tribe: Tribe name constant.

    Returns:
        City name constant, or None if no city.
    """
    return TRIBE_TO_CITY.get(tribe)


def get_tribe_restriction(tribe):
    """Get the faction stacking restriction on a tribe, if any.

    Args:
        tribe: Tribe name constant.

    Returns:
        Faction constant (e.g. AEDUI, ARVERNI, GERMANS), or None.
    """
    return TRIBE_FACTION_RESTRICTION.get(tribe)


def is_city_tribe(tribe):
    """Check if a tribe has a city.

    Args:
        tribe: Tribe name constant.

    Returns:
        True if the tribe has a city, False otherwise.
    """
    return tribe in TRIBE_TO_CITY


def get_region_group(region):
    """Get the group (Belgica, Germania, Celtica, etc.) for a region.

    Args:
        region: Region name constant.

    Returns:
        Region group constant.
    """
    return REGION_TO_GROUP[region]
