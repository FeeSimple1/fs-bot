"""Rally and Recruit commands — Mechanical execution of piece placement.

This module implements the Rally (Gallic/Germanic) and Recruit (Roman)
commands as mechanical execution: given a faction, region, and chosen
action, place the correct pieces per the rules. Bot target selection
(Phase 5) and human input (Phase 6) are NOT implemented here.

Reference: §3.2.1 (Recruit), §3.3.1 (Rally), §3.4.1 (Germanic Rally),
           §3.1.2 (Free Actions), §6.2.1 (Germans Phase Rally),
           A3.2.1, A3.3.1, A3.4.1
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    FACTIONS, GALLIC_FACTIONS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    FLIPPABLE_PIECES,
    # Piece states
    HIDDEN,
    # Control
    ROMAN_CONTROL, NO_CONTROL,
    FACTION_CONTROL,
    # Scenarios
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    # Regions
    PROVINCIA, CISALPINA, UBII, SEQUANI,
    BELGICA_REGIONS, GERMANIA_REGIONS,
    # Home regions
    ROMAN_HOME_REGIONS,
    ARVERNI_HOME_REGIONS_BASE, ARVERNI_HOME_REGIONS_ARIOVISTUS,
    AEDUI_HOME_REGIONS, BELGAE_HOME_REGIONS,
    GERMAN_HOME_REGIONS_BASE, GERMAN_HOME_REGIONS_ARIOVISTUS_STATIC,
    # Costs
    RECRUIT_COST, RALLY_COST,
    BELGAE_RALLY_OUTSIDE_BELGICA,
    ARVERNI_RALLY_DEVASTATED_WITH_VERCINGETORIX,
    GERMAN_RALLY_COST_OUTSIDE_GERMANIA_NO_SETTLEMENT,
    GERMAN_RALLY_COST_AT_SETTLEMENT,
    GERMAN_RALLY_COST_IN_GERMANIA,
    GERMAN_COMMAND_COST_BASE,
    # Misc
    ARVERNI_RALLY_EXTRA_WARBAND,
    # Markers
    MARKER_DEVASTATED, MARKER_INTIMIDATED,
    # Leaders
    VERCINGETORIX,
    # Tribes
    TRIBE_FACTION_RESTRICTION,
    TRIBE_SUEBI_NORTH, TRIBE_SUEBI_SOUTH,
    SUEBI_TRIBES,
    # Senate
    ADULATION,
)

from fs_bot.board.pieces import (
    place_piece, remove_piece, count_pieces, get_available,
    get_leader_in_region, PieceError,
)
from fs_bot.board.control import (
    is_controlled_by, refresh_all_control, calculate_control,
)
from fs_bot.map.map_data import (
    get_adjacent, get_tribes_in_region, get_tribe_data,
    get_region_data, get_region_group, is_city_tribe,
    ALL_REGION_DATA,
)


class CommandError(Exception):
    """Raised when a command violates game rules."""
    pass


# ============================================================================
# SUPPLY LINE (§3.2.1, A3.2.1)
# ============================================================================

def _borders_cisalpina_or_provincia(region, scenario):
    """Check if a region borders Cisalpina and/or Provincia for Supply Line.

    Base game: Supply Line must reach a border with Cisalpina — §3.2.1.
    NOTE: Ubii, Sequani, and Provincia border Cisalpina.
    One alone under friendly or No Control qualifies.

    Ariovistus: Supply Line must include Provincia and/or Cisalpina — A3.2.1.
    Cisalpina is always playable in Ariovistus.
    """
    if scenario in ARIOVISTUS_SCENARIOS:
        # A3.2.1: chain must include Provincia and/or Cisalpina
        return region in (PROVINCIA, CISALPINA)
    else:
        # §3.2.1: chain must reach a border with Cisalpina
        # Ubii, Sequani, and Provincia border Cisalpina — §3.2.1 NOTE
        # Cisalpina is unplayable in base game so BFS won't reach it,
        # but these three regions qualify as endpoints.
        return region in (UBII, SEQUANI, PROVINCIA, CISALPINA)


def _region_allows_supply_line(state, region, faction, agreements=None):
    """Check if a region can be part of a Supply Line.

    Per §3.2.1: Each region in the chain must have No Control OR be under
    Control of a faction that agrees. Germans never agree (§3.4.5).
    In Ariovistus: Arverni never agree (A1.5.2).

    Args:
        state: Game state dict.
        region: Region to check.
        faction: The faction executing the Recruit.
        agreements: Dict of {faction: bool} for agreement declarations.
            If None, assumes all factions other than Germans agree
            (and Arverni in Ariovistus).
    """
    space = state["spaces"].get(region, {})
    control = space.get("control", NO_CONTROL)

    if control == NO_CONTROL:
        return True

    # Own control always OK
    if control == FACTION_CONTROL.get(faction):
        return True

    # Check who controls and whether they agree
    for fac in FACTIONS:
        if FACTION_CONTROL.get(fac) == control:
            controlling_faction = fac
            break
    else:
        return False

    # Germans never agree in base game — §3.4.5
    # In Ariovistus, Germans are a full faction and may agree — A3.2.1
    if controlling_faction == GERMANS:
        if state["scenario"] in BASE_SCENARIOS:
            return False
        # Ariovistus: fall through to agreements check below

    # In Ariovistus, Arverni never agree — A1.5.2
    if (state["scenario"] in ARIOVISTUS_SCENARIOS
            and controlling_faction == ARVERNI):
        return False

    # Check explicit agreements
    if agreements is not None:
        return agreements.get(controlling_faction, False)

    # Default: other factions agree (caller can override)
    return True


def has_supply_line(state, region, faction=ROMANS, agreements=None):
    """Check if a region is within a Supply Line.

    A Supply Line is a chain of adjacent Regions reaching a border with
    Cisalpina (base) or including Provincia/Cisalpina (Ariovistus), each
    region in the chain having No Control or friendly/agreed Control.

    Args:
        state: Game state dict.
        region: Region to check for Supply Line.
        faction: Faction executing the command (default ROMANS).
        agreements: Dict of {faction: bool} for agreement declarations.

    Returns:
        True if a valid Supply Line exists to this region.
    """
    scenario = state["scenario"]

    # BFS to find path to Cisalpina border
    visited = set()
    queue = [region]

    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)

        # Check if current region allows the supply line to pass
        if not _region_allows_supply_line(state, current, faction, agreements):
            continue

        # Check if we've reached a border with Cisalpina/Provincia
        if _borders_cisalpina_or_provincia(current, scenario):
            return True

        # Expand to adjacent regions
        for adj in get_adjacent(current, scenario,
                                state.get("capabilities")):
            if adj not in visited:
                queue.append(adj)

    return False


# ============================================================================
# COST CALCULATIONS
# ============================================================================

def recruit_cost(state, region, faction=ROMANS, agreements=None):
    """Calculate the Resource cost for Recruit in a region.

    §3.2.1: 2 Resources per Region; 0 if within a Supply Line.

    Args:
        state: Game state dict.
        region: Region to recruit in.
        faction: Faction (default ROMANS).
        agreements: Supply Line agreement dict.

    Returns:
        Integer Resource cost.
    """
    if has_supply_line(state, region, faction, agreements):
        return 0
    return RECRUIT_COST


def rally_cost(state, region, faction):
    """Calculate the Resource cost for Rally in a region.

    §3.3.1: 1 Resource per Region.
    Belgae outside Belgica: 2 Resources — §3.3.1.
    Arverni in Devastated with Vercingetorix: 2 Resources — §3.3.1.
    Germans base game: 0 (free) — §3.4.
    Germans Ariovistus: 0 in Germania, 1 at Settlement, 2 outside — A3.4.1.

    Args:
        state: Game state dict.
        region: Region to rally in.
        faction: Faction executing Rally.

    Returns:
        Integer Resource cost.
    """
    scenario = state["scenario"]

    if faction == GERMANS:
        if scenario in BASE_SCENARIOS:
            return GERMAN_COMMAND_COST_BASE
        # Ariovistus — A3.4.1
        if region in GERMANIA_REGIONS:
            return GERMAN_RALLY_COST_IN_GERMANIA
        # Check for Settlement
        if count_pieces(state, region, GERMANS, SETTLEMENT) > 0:
            return GERMAN_RALLY_COST_AT_SETTLEMENT
        return GERMAN_RALLY_COST_OUTSIDE_GERMANIA_NO_SETTLEMENT

    if faction == BELGAE:
        region_group = get_region_group(region)
        from fs_bot.rules_consts import BELGICA
        if region_group != BELGICA:
            return BELGAE_RALLY_OUTSIDE_BELGICA

    if faction == ARVERNI:
        # Check for Devastated + Vercingetorix exception — §3.3.1
        markers = state.get("markers", {}).get(region, {})
        is_devastated = MARKER_DEVASTATED in markers
        has_vercingetorix = (
            get_leader_in_region(state, region, ARVERNI) == VERCINGETORIX
        )
        if is_devastated and has_vercingetorix:
            return ARVERNI_RALLY_DEVASTATED_WITH_VERCINGETORIX

    return RALLY_COST


# ============================================================================
# VALIDATION
# ============================================================================

def _is_devastated(state, region):
    """Check if a region has the Devastated marker."""
    markers = state.get("markers", {}).get(region, {})
    return MARKER_DEVASTATED in markers


def _is_intimidated(state, region):
    """Check if a region has the Intimidated marker (Ariovistus only)."""
    markers = state.get("markers", {}).get(region, {})
    return MARKER_INTIMIDATED in markers


def _get_home_regions(faction, scenario):
    """Get the home regions (Rally/Recruit symbol) for a faction.

    Args:
        faction: Faction constant.
        scenario: Scenario identifier.

    Returns:
        Tuple of region name constants.
    """
    if faction == ROMANS:
        return ROMAN_HOME_REGIONS
    if faction == ARVERNI:
        if scenario in ARIOVISTUS_SCENARIOS:
            return ARVERNI_HOME_REGIONS_ARIOVISTUS
        return ARVERNI_HOME_REGIONS_BASE
    if faction == AEDUI:
        return AEDUI_HOME_REGIONS
    if faction == BELGAE:
        return BELGAE_HOME_REGIONS
    if faction == GERMANS:
        if scenario in ARIOVISTUS_SCENARIOS:
            return GERMAN_HOME_REGIONS_ARIOVISTUS_STATIC
        return GERMAN_HOME_REGIONS_BASE
    return ()


def validate_recruit_region(state, region):
    """Validate that a region is eligible for Roman Recruit.

    §3.2.1: Not Devastated, and must have Roman Control OR a Roman
    Leader, Ally, or Fort.
    A3.2.1: Not Intimidated unless Roman Leader present.

    Args:
        state: Game state dict.
        region: Region to validate.

    Returns:
        (valid, reason) tuple. valid is True if region is eligible.
    """
    scenario = state["scenario"]

    # Not Devastated — §3.2.1
    if _is_devastated(state, region):
        return False, "Region is Devastated"

    # Ariovistus: not Intimidated unless Roman Leader — A3.2.1
    if scenario in ARIOVISTUS_SCENARIOS:
        if _is_intimidated(state, region):
            if get_leader_in_region(state, region, ROMANS) is None:
                return False, "Region is Intimidated and has no Roman Leader"

    # Must have Roman Control OR Roman Leader/Ally/Fort — §3.2.1
    has_roman_control = is_controlled_by(state, region, ROMANS)
    has_roman_leader = get_leader_in_region(state, region, ROMANS) is not None
    has_roman_ally = count_pieces(state, region, ROMANS, ALLY) > 0
    has_roman_fort = count_pieces(state, region, ROMANS, FORT) > 0

    if not (has_roman_control or has_roman_leader
            or has_roman_ally or has_roman_fort):
        return False, "Region has no Roman Control, Leader, Ally, or Fort"

    return True, None


def validate_rally_region(state, region, faction):
    """Validate that a region is eligible for Rally.

    §3.3.1: Not Devastated, and must have faction's Control, Ally,
    Citadel, Arverni Leader, or Rally symbol.
    Exception: Arverni can rally in Devastated if Vercingetorix present.
    A3.3.1/A3.4.1: Intimidation check (Gallic blocked, Germans exempt).

    Args:
        state: Game state dict.
        region: Region to validate.
        faction: Faction executing Rally.

    Returns:
        (valid, reason) tuple.
    """
    scenario = state["scenario"]

    # Devastated check — §3.3.1, with Vercingetorix exception
    is_devastated = _is_devastated(state, region)
    if is_devastated:
        # Arverni exception: can rally if Vercingetorix present — §3.3.1
        if (faction == ARVERNI
                and scenario in BASE_SCENARIOS
                and get_leader_in_region(state, region, ARVERNI)
                == VERCINGETORIX):
            pass  # Allowed
        else:
            return False, "Region is Devastated"

    # Intimidation check (Ariovistus only)
    if scenario in ARIOVISTUS_SCENARIOS:
        if faction != GERMANS:
            # Gallic Rally blocked by Intimidation — A3.3.1
            # Unless faction's Leader is present
            if _is_intimidated(state, region):
                if get_leader_in_region(state, region, faction) is None:
                    return (False,
                            "Region is Intimidated and has no "
                            f"{faction} Leader")
        # Germans immune to Intimidation for Rally — A3.4.1

    # Must have effect: faction's Control, Ally, Citadel, Leader,
    # or Rally symbol — §3.3.1
    has_control = is_controlled_by(state, region, faction)
    has_ally = count_pieces(state, region, faction, ALLY) > 0
    has_citadel = count_pieces(state, region, faction, CITADEL) > 0

    # Leader check — Arverni Leader counts in base game
    has_leader = False
    if faction == ARVERNI and scenario in BASE_SCENARIOS:
        has_leader = (get_leader_in_region(state, region, ARVERNI)
                      is not None)

    # Rally symbol = home region
    home_regions = _get_home_regions(faction, scenario)
    has_rally_symbol = region in home_regions

    # Germans in Ariovistus: Settlement regions are also home — A3.4.1
    if (faction == GERMANS and scenario in ARIOVISTUS_SCENARIOS):
        if count_pieces(state, region, GERMANS, SETTLEMENT) > 0:
            has_rally_symbol = True

    if not (has_control or has_ally or has_citadel
            or has_leader or has_rally_symbol):
        return (False,
                f"Region has no {faction} Control, Ally, Citadel, "
                f"Leader, or Rally symbol")

    return True, None


# ============================================================================
# RECRUIT (§3.2.1, A3.2.1)
# ============================================================================

def _count_recruit_auxilia_cap(state, region):
    """Calculate Auxilia placement cap for Recruit in a region.

    §3.2.1: Available Auxilia up to the number of Roman Allied Tribes
    plus one per Leader and Fort there.

    HOME REGION: +1 extra in Provincia — §3.2.1.

    Args:
        state: Game state dict.
        region: Region to recruit in.

    Returns:
        Integer cap.
    """
    allies = count_pieces(state, region, ROMANS, ALLY)
    leader_count = 1 if get_leader_in_region(state, region, ROMANS) else 0
    forts = count_pieces(state, region, ROMANS, FORT)

    cap = allies + leader_count + forts

    # Home Region bonus: +1 in Provincia — §3.2.1
    if region in ROMAN_HOME_REGIONS:
        cap += 1

    return cap


def _find_subdued_tribe_for_ally(state, region, faction):
    """Find a valid Subdued tribe for Ally placement in a region.

    §3.2.1 / §3.3.1: Place at a Subdued Tribe, not at faction-restricted
    tribes of other factions, not at Suebi (for non-Germans), not at
    Dispersed tribes.

    Args:
        state: Game state dict.
        region: Region containing tribes.
        faction: Faction placing the Ally.

    Returns:
        List of eligible tribe names.
    """
    scenario = state["scenario"]
    tribes = get_tribes_in_region(region, scenario)
    eligible = []

    for tribe_name in tribes:
        tribe_info = get_tribe_data(tribe_name)

        # Check tribe status — must be Subdued (no existing Ally)
        tribe_state = state.get("tribes", {}).get(tribe_name, {})
        status = tribe_state.get("status")
        allied_faction = tribe_state.get("allied_faction")

        # A tribe with an existing Ally is not Subdued
        if allied_faction is not None:
            continue

        # Check for Dispersed marker
        from fs_bot.rules_consts import DISPERSED, DISPERSED_GATHERING
        if status in (DISPERSED, DISPERSED_GATHERING):
            continue

        # Check faction restriction — §1.4.2
        restriction = tribe_info.faction_restriction
        if restriction is not None and restriction != faction:
            continue

        # Suebi: only Germans can place there — §1.4.2
        if tribe_name in SUEBI_TRIBES and faction != GERMANS:
            continue

        eligible.append(tribe_name)

    return eligible


def recruit_in_region(state, region, action, *, tribe=None, free=False,
                      agreements=None):
    """Execute Roman Recruit in a single region.

    This is the mechanical execution. The caller decides which region
    and which action.

    Args:
        state: Game state dict. Modified in place.
        region: Region to recruit in.
        action: One of:
            "place_ally" — Place 1 Roman Ally at a Subdued Tribe.
            "place_auxilia" — Place Auxilia up to the cap.
        tribe: For "place_ally", the specific tribe to place at.
            Must be a valid Subdued tribe.
        free: If True, no Resource cost (Event-granted, §3.1.2).
        agreements: Supply Line agreement dict for cost calculation.

    Returns:
        Dict with results:
            "action": action taken
            "pieces_placed": {piece_type: count}
            "cost": Resources spent
            "tribe_allied": tribe name if ally placed, else None

    Raises:
        CommandError: If the action violates rules.
    """
    scenario = state["scenario"]

    # Validate region
    valid, reason = validate_recruit_region(state, region)
    if not valid:
        raise CommandError(f"Cannot Recruit in {region}: {reason}")

    # Calculate cost
    cost = 0 if free else recruit_cost(state, region, ROMANS, agreements)

    # Check resources
    if not free and cost > 0:
        current_resources = state["resources"].get(ROMANS, 0)
        if current_resources < cost:
            raise CommandError(
                f"Romans have {current_resources} Resources, "
                f"need {cost} to Recruit in {region}"
            )

    result = {
        "action": action,
        "pieces_placed": {},
        "cost": cost,
        "tribe_allied": None,
        "region": region,
    }

    if action == "place_ally":
        # §3.2.1: If under Roman Control, or if Caesar is there, place
        # one Available Roman Ally at a Subdued Tribe
        has_roman_control = is_controlled_by(state, region, ROMANS)
        from fs_bot.rules_consts import CAESAR
        has_caesar = (get_leader_in_region(state, region, ROMANS) == CAESAR)

        if not (has_roman_control or has_caesar):
            raise CommandError(
                "Place Ally requires Roman Control or Caesar in region"
            )

        if tribe is None:
            raise CommandError("Must specify tribe for Ally placement")

        # Validate the tribe
        eligible = _find_subdued_tribe_for_ally(state, region, ROMANS)
        if tribe not in eligible:
            raise CommandError(
                f"Tribe {tribe} is not eligible for Roman Ally placement"
            )

        # Check Available
        if get_available(state, ROMANS, ALLY) < 1:
            raise CommandError("No Roman Allies Available")

        # Deduct cost
        if not free and cost > 0:
            state["resources"][ROMANS] -= cost

        # Place the Ally
        place_piece(state, region, ROMANS, ALLY)

        # Update tribe status
        state["tribes"][tribe]["allied_faction"] = ROMANS
        state["tribes"][tribe]["status"] = None  # Allied now

        result["pieces_placed"][ALLY] = 1
        result["tribe_allied"] = tribe

    elif action == "place_auxilia":
        # §3.2.1: If Region has Roman Leader, Allied Tribe, or Fort,
        # place Auxilia up to cap
        has_leader = get_leader_in_region(state, region, ROMANS) is not None
        has_ally = count_pieces(state, region, ROMANS, ALLY) > 0
        has_fort = count_pieces(state, region, ROMANS, FORT) > 0

        if not (has_leader or has_ally or has_fort):
            raise CommandError(
                "Place Auxilia requires Roman Leader, Ally, or Fort in region"
            )

        cap = _count_recruit_auxilia_cap(state, region)
        available = get_available(state, ROMANS, AUXILIA)
        to_place = min(cap, available)

        if to_place <= 0:
            # Deduct cost even if nothing placed (region was selected)
            if not free and cost > 0:
                state["resources"][ROMANS] -= cost
            result["pieces_placed"][AUXILIA] = 0
            return result

        # Deduct cost
        if not free and cost > 0:
            state["resources"][ROMANS] -= cost

        # Place Auxilia (Hidden per §1.4.3)
        place_piece(state, region, ROMANS, AUXILIA, to_place)

        result["pieces_placed"][AUXILIA] = to_place

    else:
        raise CommandError(f"Unknown Recruit action: {action}")

    # Refresh control
    refresh_all_control(state)

    return result


# ============================================================================
# RALLY — GALLIC (§3.3.1, A3.3.1)
# ============================================================================

def _gallic_warband_cap(state, region, faction):
    """Calculate Warband placement cap for Gallic Rally.

    §3.3.1:
    - Aedui/Belgae: up to number of Allied Tribes and Citadels there.
    - Arverni: up to Allies + Citadels + Leaders + 1.

    Args:
        state: Game state dict.
        region: Region.
        faction: Faction.

    Returns:
        Integer cap.
    """
    allies = count_pieces(state, region, faction, ALLY)
    citadels = count_pieces(state, region, faction, CITADEL)

    if faction == ARVERNI:
        leader_count = (
            1 if get_leader_in_region(state, region, ARVERNI) else 0
        )
        return allies + citadels + leader_count + ARVERNI_RALLY_EXTRA_WARBAND
    else:
        # Aedui or Belgae
        return allies + citadels


def _german_warband_cap(state, region):
    """Calculate Warband placement cap for Germanic Rally.

    §3.4.1 (base): up to number of Germanic Allied Tribes.
    A3.4.1 (Ariovistus): up to Germanic Allies plus Settlements.

    Args:
        state: Game state dict.
        region: Region.

    Returns:
        Integer cap.
    """
    allies = count_pieces(state, region, GERMANS, ALLY)
    if state["scenario"] in ARIOVISTUS_SCENARIOS:
        settlements = count_pieces(state, region, GERMANS, SETTLEMENT)
        return allies + settlements
    return allies


def rally_in_region(state, region, faction, action, *, tribe=None,
                    free=False):
    """Execute Rally in a single region.

    This is the mechanical execution for ONE option in ONE region.
    The caller decides which region and action.

    EXCEPTION: Arverni with Vercingetorix may do BOTH place_ally/citadel
    AND place_warbands — §3.3.1. The caller should make two separate
    calls in that case, one for each action.

    Args:
        state: Game state dict. Modified in place.
        region: Region to rally in.
        faction: Faction executing Rally.
        action: One of:
            "place_ally" — Place 1 Ally at a Subdued Tribe.
            "place_warbands" — Place Warbands up to cap.
            "place_citadel" — Replace Ally with Citadel at a City.
        tribe: For "place_ally", the tribe to place at.
            For "place_citadel", the tribe at the City.
        free: If True, no Resource cost (Event-granted, §3.1.2).

    Returns:
        Dict with results:
            "action": action taken
            "faction": faction
            "region": region
            "pieces_placed": {piece_type: count}
            "pieces_removed": {piece_type: count}
            "cost": Resources spent (0 if free or if cost already paid)
            "tribe_allied": tribe name if ally placed

    Raises:
        CommandError: If the action violates rules.
    """
    scenario = state["scenario"]

    # Validate region
    valid, reason = validate_rally_region(state, region, faction)
    if not valid:
        raise CommandError(f"Cannot Rally in {region}: {reason}")

    # Calculate cost
    cost = 0 if free else rally_cost(state, region, faction)

    result = {
        "action": action,
        "faction": faction,
        "region": region,
        "pieces_placed": {},
        "pieces_removed": {},
        "cost": cost,
        "tribe_allied": None,
    }

    if action == "place_ally":
        # §3.3.1: If faction Controls the region, place one Ally at
        # a Subdued Tribe.
        # Vercingetorix exception: Arverni may place Ally without Control
        has_control = is_controlled_by(state, region, faction)

        # Vercingetorix exception — §3.3.1
        has_vercingetorix = False
        if (faction == ARVERNI and scenario in BASE_SCENARIOS):
            has_vercingetorix = (
                get_leader_in_region(state, region, ARVERNI)
                == VERCINGETORIX
            )

        if not (has_control or has_vercingetorix):
            raise CommandError(
                f"Place Ally requires {faction} Control "
                f"(or Vercingetorix for Arverni)"
            )

        if tribe is None:
            raise CommandError("Must specify tribe for Ally placement")

        eligible = _find_subdued_tribe_for_ally(state, region, faction)
        if tribe not in eligible:
            raise CommandError(
                f"Tribe {tribe} is not eligible for {faction} Ally placement"
            )

        if get_available(state, faction, ALLY) < 1:
            raise CommandError(f"No {faction} Allies Available")

        # Deduct cost
        if not free and cost > 0:
            if state["resources"].get(faction, 0) < cost:
                raise CommandError(
                    f"{faction} has {state['resources'].get(faction, 0)} "
                    f"Resources, need {cost}"
                )
            state["resources"][faction] -= cost

        # Place the Ally
        place_piece(state, region, faction, ALLY)

        # Update tribe status
        state["tribes"][tribe]["allied_faction"] = faction
        state["tribes"][tribe]["status"] = None

        result["pieces_placed"][ALLY] = 1
        result["tribe_allied"] = tribe

    elif action == "place_warbands":
        # Determine warband cap
        if faction == GERMANS:
            cap = _german_warband_cap(state, region)
        else:
            # Check prerequisite: Aedui/Belgae need existing Ally/Citadel;
            # Arverni need Ally, Citadel, or Leader — §3.3.1
            if faction in (AEDUI, BELGAE):
                has_ally = count_pieces(state, region, faction, ALLY) > 0
                has_citadel = count_pieces(
                    state, region, faction, CITADEL) > 0
                if not (has_ally or has_citadel):
                    # Home Region exception — §3.3.1
                    home = _get_home_regions(faction, scenario)
                    if region in home:
                        cap = 1  # "at least one Warband"
                    else:
                        raise CommandError(
                            f"Place Warbands requires {faction} Ally or "
                            f"Citadel in region"
                        )
                else:
                    cap = _gallic_warband_cap(state, region, faction)
            elif faction == ARVERNI:
                has_ally = count_pieces(state, region, faction, ALLY) > 0
                has_citadel = count_pieces(
                    state, region, faction, CITADEL) > 0
                has_leader = (
                    get_leader_in_region(state, region, ARVERNI) is not None
                )
                if not (has_ally or has_citadel or has_leader):
                    home = _get_home_regions(faction, scenario)
                    if region in home:
                        cap = 1
                    else:
                        raise CommandError(
                            f"Place Warbands requires Arverni Ally, "
                            f"Citadel, or Leader in region"
                        )
                else:
                    cap = _gallic_warband_cap(state, region, faction)
            else:
                cap = _gallic_warband_cap(state, region, faction)

        # Germans: home region minimum — §3.4.1
        if faction == GERMANS:
            has_ally = count_pieces(state, region, GERMANS, ALLY) > 0
            has_settlement = (
                scenario in ARIOVISTUS_SCENARIOS
                and count_pieces(state, region, GERMANS, SETTLEMENT) > 0
            )
            is_home = region in _get_home_regions(GERMANS, scenario)
            # Ariovistus: Settlement regions also count as home
            if scenario in ARIOVISTUS_SCENARIOS and has_settlement:
                is_home = True

            if not (has_ally or has_settlement):
                if is_home:
                    cap = max(cap, 1)  # At least 1 in home regions
                else:
                    if cap == 0:
                        raise CommandError(
                            "Place Warbands requires Germanic Ally "
                            "(or Settlement in Ariovistus) in region"
                        )

        # Home region minimum for Gallic factions — §3.3.1
        if faction in GALLIC_FACTIONS:
            home = _get_home_regions(faction, scenario)
            if region in home:
                cap = max(cap, 1)

        available = get_available(state, faction, WARBAND)
        to_place = min(cap, available)

        # Deduct cost
        if not free and cost > 0:
            if state["resources"].get(faction, 0) < cost:
                raise CommandError(
                    f"{faction} has {state['resources'].get(faction, 0)} "
                    f"Resources, need {cost}"
                )
            state["resources"][faction] -= cost

        if to_place > 0:
            place_piece(state, region, faction, WARBAND, to_place)

        result["pieces_placed"][WARBAND] = to_place

    elif action == "place_citadel":
        # §3.3.1: If the Faction has an Allied Tribe at a City,
        # replace the Ally with that Faction's Citadel.
        if tribe is None:
            raise CommandError("Must specify tribe for Citadel placement")

        # Validate tribe is a city
        if not is_city_tribe(tribe):
            raise CommandError(f"Tribe {tribe} does not have a City")

        # Validate faction has Ally at this tribe
        tribe_state = state.get("tribes", {}).get(tribe, {})
        if tribe_state.get("allied_faction") != faction:
            raise CommandError(
                f"Tribe {tribe} does not have a {faction} Ally"
            )

        # Check Available Citadels
        if get_available(state, faction, CITADEL) < 1:
            raise CommandError(f"No {faction} Citadels Available")

        # Deduct cost
        if not free and cost > 0:
            if state["resources"].get(faction, 0) < cost:
                raise CommandError(
                    f"{faction} has {state['resources'].get(faction, 0)} "
                    f"Resources, need {cost}"
                )
            state["resources"][faction] -= cost

        # Remove the Ally, place the Citadel — §1.4.1
        remove_piece(state, region, faction, ALLY, to_available=True)
        place_piece(state, region, faction, CITADEL)

        # Tribe remains allied to the faction (now via Citadel)
        # The tribe status doesn't change — still controlled by faction

        result["pieces_placed"][CITADEL] = 1
        result["pieces_removed"][ALLY] = 1

    else:
        raise CommandError(f"Unknown Rally action: {action}")

    # Refresh control
    refresh_all_control(state)

    return result


# ============================================================================
# GERMANIC RALLY — ARIOVISTUS HOME BONUS (A3.4.1)
# ============================================================================

def german_rally_home_bonus(state, region):
    """Place the Germanic home region bonus Warband.

    A3.4.1: At the end of Germanic Rally in each Region that has a
    Settlement or is in Germania, place one additional German Warband
    there, regardless of whether the Rally placed an Ally, Warbands,
    or nothing.

    This should be called AFTER the main rally_in_region() call.

    Args:
        state: Game state dict. Modified in place.
        region: Region to check for bonus.

    Returns:
        1 if bonus Warband placed, 0 otherwise.
    """
    scenario = state["scenario"]
    if scenario not in ARIOVISTUS_SCENARIOS:
        return 0

    is_germania = region in GERMANIA_REGIONS
    has_settlement = count_pieces(state, region, GERMANS, SETTLEMENT) > 0

    if not (is_germania or has_settlement):
        return 0

    # Check Available
    if get_available(state, GERMANS, WARBAND) < 1:
        return 0

    place_piece(state, region, GERMANS, WARBAND)
    refresh_all_control(state)
    return 1


# ============================================================================
# GERMANS PHASE RALLY (§6.2.1) — Base Game Only
# ============================================================================

def germans_phase_rally(state):
    """Execute the Germans Phase Rally procedure — §6.2.1.

    This is the base-game-only deterministic rally for the Germanic
    non-player faction during Winter. It uses state["rng"] for random
    choices among equal candidates.

    §6.2.1:
    1. Rally to place as many Germanic Allied Tribes as possible,
       starting with Suebi, then others in Germania, then elsewhere.
    2. Rally to place as many Warbands as possible (including where
       Allies were just placed, and in un-Devastated Germania even
       if no Germanic Allies).
    3. Choose among equal locations randomly.
    4. Adjust Control.

    Args:
        state: Game state dict. Modified in place.

    Returns:
        Dict with results:
            "allies_placed": [(region, tribe), ...]
            "warbands_placed": {region: count, ...}
    """
    scenario = state["scenario"]
    if scenario not in BASE_SCENARIOS:
        raise CommandError("Germans Phase Rally is base game only")

    result = {
        "allies_placed": [],
        "warbands_placed": {},
    }
    rng = state["rng"]

    # Step 1: Place as many Germanic Allies as possible — §6.2.1
    # Priority: Suebi first, then other Germania, then elsewhere
    # Per §3.4.1: Germanic Ally only if region has Germanic Control
    # Never at Aedui [Bibracte] or Arverni [Gergovia] — §1.4.2

    # Build ordered list of candidate regions/tribes
    suebi_candidates = []
    germania_candidates = []
    elsewhere_candidates = []

    for region in state["spaces"]:
        region_data = ALL_REGION_DATA.get(region)
        if region_data is None:
            continue
        if not region_data.is_playable(scenario, state.get("capabilities")):
            continue
        if _is_devastated(state, region):
            continue
        if not is_controlled_by(state, region, GERMANS):
            continue

        eligible_tribes = _find_subdued_tribe_for_ally(
            state, region, GERMANS)
        for tribe_name in eligible_tribes:
            entry = (region, tribe_name)
            if tribe_name in SUEBI_TRIBES:
                suebi_candidates.append(entry)
            elif region in GERMANIA_REGIONS:
                germania_candidates.append(entry)
            else:
                elsewhere_candidates.append(entry)

    # Place in priority order, choosing randomly among equals
    for candidate_list in [suebi_candidates, germania_candidates,
                           elsewhere_candidates]:
        while candidate_list and get_available(state, GERMANS, ALLY) > 0:
            # Choose randomly among equal candidates — §6.2.1
            rng.shuffle(candidate_list)
            chosen_region, chosen_tribe = candidate_list.pop(0)

            # Verify still valid (control may have changed)
            if not is_controlled_by(state, chosen_region, GERMANS):
                continue
            eligible = _find_subdued_tribe_for_ally(
                state, chosen_region, GERMANS)
            if chosen_tribe not in eligible:
                continue

            # Place the Ally
            place_piece(state, chosen_region, GERMANS, ALLY)
            state["tribes"][chosen_tribe]["allied_faction"] = GERMANS
            state["tribes"][chosen_tribe]["status"] = None
            result["allies_placed"].append((chosen_region, chosen_tribe))
            refresh_all_control(state)

    # Step 2: Place as many Warbands as possible — §6.2.1
    # Including where Allies were just placed, and in un-Devastated
    # Germania even if no Germanic Allies there.

    # Collect all regions where Warbands can be placed
    warband_regions = []
    for region in state["spaces"]:
        region_data = ALL_REGION_DATA.get(region)
        if region_data is None:
            continue
        if not region_data.is_playable(scenario, state.get("capabilities")):
            continue
        if _is_devastated(state, region):
            continue

        german_allies = count_pieces(state, region, GERMANS, ALLY)
        is_home = region in GERMANIA_REGIONS

        if german_allies > 0 or is_home:
            cap = german_allies  # §3.4.1: up to Germanic Allies
            if is_home:
                cap = max(cap, 1)  # Home: at least 1
            if cap > 0:
                warband_regions.append((region, cap))

    # Place Warbands, choosing randomly among equal regions
    rng.shuffle(warband_regions)
    for region, cap in warband_regions:
        available = get_available(state, GERMANS, WARBAND)
        if available <= 0:
            break
        to_place = min(cap, available)
        if to_place > 0:
            place_piece(state, region, GERMANS, WARBAND, to_place)
            result["warbands_placed"][region] = to_place

    refresh_all_control(state)
    return result
