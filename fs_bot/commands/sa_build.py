"""
Build Special Ability — §4.2.1 (Roman).

Build constructs forts or public works. It may accompany Recruit, March,
or Seize Commands — NOT Battle.

Selection requirements (§4.2.1):
  - Region has a Roman Ally already, or is part of a Supply Line to
    Cisalpina and has any Roman piece in it.
  - Region is within one Region of Caesar or is the Region with Successor.

Procedure per region — one or both of:
  1. Place a Fort (if none already there).
  2. If the Region is now under Roman Control and is NOT selected for
     Seize in the accompanying Command:
     - Either Subdue (remove) one Gallic or Germanic Allied Tribe, or
     - Place a Roman Ally at an already Subdued Tribe (not at Aedui
       [Bibracte], Arverni [Gergovia], or Suebi).

Cost: 2 Resources per Fort and per Ally placed or removed — §4.2.1

Reference: §4.2.1, §1.4.1, §1.4.2, A4.2.1
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    GALLIC_FACTIONS,
    # Piece types
    FORT, ALLY, CITADEL, SETTLEMENT,
    # Leaders
    CAESAR,
    # Costs
    BUILD_COST_PER_FORT, BUILD_COST_PER_ALLY,
    # Stacking
    MAX_FORTS_PER_REGION,
    # Tribe restrictions
    TRIBE_FACTION_RESTRICTION,
    # Scenarios
    ARIOVISTUS_SCENARIOS,
)
from fs_bot.board.pieces import (
    place_piece, remove_piece, get_available,
    get_leader_in_region, find_leader, count_pieces,
)
from fs_bot.board.control import is_controlled_by, refresh_all_control
from fs_bot.map.map_data import (
    is_adjacent, get_tribes_in_region, get_tribe_data,
)
from fs_bot.commands.common import CommandError
from fs_bot.commands.rally import has_supply_line


def validate_build_region(state, region, agreements=None):
    """Validate that a region can be selected for Build.

    §4.2.1: Region must have a Roman Ally already, or be part of a Supply
    Line to Cisalpina and have any Roman piece in it. Must be within one
    Region of Caesar or same Region as Successor.

    Args:
        state: Game state dict.
        region: Region to check.
        agreements: Dict of {faction: bool} for Supply Line agreement.

    Returns:
        (True, "") if valid, (False, reason) if not.
    """
    # Check Leader proximity
    valid_leader, leader_reason = _check_build_leader(state, region)
    if not valid_leader:
        return (False, leader_reason)

    # Check Roman Ally OR Supply Line + Roman piece
    has_ally = _has_roman_ally(state, region)
    has_supply = (
        has_supply_line(state, region, ROMANS, agreements)
        and _has_any_roman_piece(state, region)
    )

    if not has_ally and not has_supply:
        return (False,
                f"Region must have a Roman Ally or be on a Supply Line "
                f"with a Roman piece for Build")

    return (True, "")


def build_fort(state, region):
    """Place a Fort in a region via Build.

    §4.2.1: "Place a Fort (if none already there, 1.4, 1.4.2)"
    Cost: 2 Resources — §4.2.1

    Args:
        state: Game state dict. Modified in place.
        region: Region to build Fort in.

    Returns:
        dict with:
            "placed": FORT
            "cost": Resource cost paid.

    Raises:
        CommandError: If placement violates rules.
    """
    # Check existing Fort
    space = state["spaces"][region]
    roman_pieces = space.get("pieces", {}).get(ROMANS, {})
    if roman_pieces.get(FORT, 0) >= MAX_FORTS_PER_REGION:
        raise CommandError(
            f"Region {region} already has a Fort (max {MAX_FORTS_PER_REGION})"
        )

    # Check Available
    avail = get_available(state, ROMANS, FORT)
    if avail < 1:
        raise CommandError("No Forts Available")

    # Check Resources
    resources = state["resources"].get(ROMANS, 0)
    if resources < BUILD_COST_PER_FORT:
        raise CommandError(
            f"Not enough Resources ({resources}) for Fort "
            f"(need {BUILD_COST_PER_FORT})"
        )

    # Pay cost
    state["resources"][ROMANS] -= BUILD_COST_PER_FORT

    # Place Fort
    place_piece(state, region, ROMANS, FORT)

    # Refresh control — Fort placement may change control
    refresh_all_control(state)

    return {"placed": FORT, "cost": BUILD_COST_PER_FORT}


def build_subdue(state, region, tribe, target_faction):
    """Subdue (remove) one Gallic or Germanic Allied Tribe via Build.

    §4.2.1: "if the Region is now under Roman Control... Subdue (remove)
    any one Gallic or Germanic Allied Tribe there (a disc, not a Citadel)"

    Cost: 2 Resources — §4.2.1

    Args:
        state: Game state dict. Modified in place.
        region: Region to subdue tribe in.
        tribe: Tribe name constant to subdue.
        target_faction: Faction whose Ally to remove.

    Returns:
        dict with:
            "subdued": tribe name
            "faction_removed": target_faction
            "cost": Resource cost.

    Raises:
        CommandError: If subdue violates rules.
    """
    # Must be under Roman Control
    if not is_controlled_by(state, region, ROMANS):
        raise CommandError(
            f"Region must be under Roman Control to subdue via Build"
        )

    # Target must not be Roman
    if target_faction == ROMANS:
        raise CommandError("Cannot subdue a Roman Ally via Build")

    # Check the tribe is in this region
    tribes = get_tribes_in_region(region, state["scenario"])
    if tribe not in tribes:
        raise CommandError(f"Tribe {tribe} is not in {region}")

    # Check the tribe has an Allied disc of the target faction
    tribe_info = state["tribes"].get(tribe, {})
    if tribe_info.get("allied_faction") != target_faction:
        raise CommandError(
            f"Tribe {tribe} is not allied to {target_faction}"
        )

    # Check Resources
    resources = state["resources"].get(ROMANS, 0)
    if resources < BUILD_COST_PER_ALLY:
        raise CommandError(
            f"Not enough Resources ({resources}) for subdue "
            f"(need {BUILD_COST_PER_ALLY})"
        )

    # Pay cost
    state["resources"][ROMANS] -= BUILD_COST_PER_ALLY

    # Remove the Allied Tribe disc
    remove_piece(state, region, target_faction, ALLY, 1)

    # Mark tribe as Subdued
    state["tribes"][tribe]["status"] = None
    state["tribes"][tribe]["allied_faction"] = None

    # Refresh control
    refresh_all_control(state)

    return {
        "subdued": tribe,
        "faction_removed": target_faction,
        "cost": BUILD_COST_PER_ALLY,
    }


def build_place_ally(state, region, tribe):
    """Place a Roman Ally at a Subdued Tribe via Build.

    §4.2.1: "place a Roman Ally at an already Subdued Tribe there (not at
    Aedui [Bibracte], Arverni [Gergovia], or Suebi, 1.4.2)"

    Cost: 2 Resources — §4.2.1

    Args:
        state: Game state dict. Modified in place.
        region: Region to place Ally in.
        tribe: Tribe name constant.

    Returns:
        dict with:
            "placed_ally_at": tribe name
            "cost": Resource cost.

    Raises:
        CommandError: If placement violates rules.
    """
    # Must be under Roman Control
    if not is_controlled_by(state, region, ROMANS):
        raise CommandError(
            f"Region must be under Roman Control to place Ally via Build"
        )

    # Check the tribe is in this region
    tribes = get_tribes_in_region(region, state["scenario"])
    if tribe not in tribes:
        raise CommandError(f"Tribe {tribe} is not in {region}")

    # Check tribe is Subdued (no Allied disc)
    tribe_info = state["tribes"].get(tribe, {})
    if tribe_info.get("allied_faction") is not None:
        raise CommandError(f"Tribe {tribe} is not Subdued")

    # Check stacking restriction — §1.4.2
    td = get_tribe_data(tribe)
    if td.faction_restriction is not None and td.faction_restriction != ROMANS:
        raise CommandError(
            f"Cannot place Roman Ally at {tribe} — restricted to "
            f"{td.faction_restriction} (§1.4.2)"
        )

    # Check Available
    avail = get_available(state, ROMANS, ALLY)
    if avail < 1:
        raise CommandError("No Roman Allies Available")

    # Check Resources
    resources = state["resources"].get(ROMANS, 0)
    if resources < BUILD_COST_PER_ALLY:
        raise CommandError(
            f"Not enough Resources ({resources}) for Ally placement "
            f"(need {BUILD_COST_PER_ALLY})"
        )

    # Pay cost
    state["resources"][ROMANS] -= BUILD_COST_PER_ALLY

    # Place Ally
    place_piece(state, region, ROMANS, ALLY)

    # Update tribe status
    state["tribes"][tribe]["allied_faction"] = ROMANS

    # Refresh control
    refresh_all_control(state)

    return {"placed_ally_at": tribe, "cost": BUILD_COST_PER_ALLY}


def _check_build_leader(state, region):
    """Check leader proximity for Build.

    §4.2.1: "within one Region of Caesar or is the Region that the Roman
    Successor Leader is in."
    """
    leader_region = find_leader(state, ROMANS)
    if leader_region is None:
        return (False, "Roman leader not on map — cannot Build")

    actual_leader = get_leader_in_region(state, leader_region, ROMANS)

    if actual_leader == CAESAR:
        if region == leader_region or is_adjacent(region, leader_region):
            return (True, "")
        return (False, "Region must be within 1 of Caesar for Build")
    else:
        # Successor: must be same region
        if region == leader_region:
            return (True, "")
        return (False, "Successor must be in the same region for Build")


def _has_roman_ally(state, region):
    """Check if region has a Roman Ally."""
    space = state["spaces"][region]
    roman_pieces = space.get("pieces", {}).get(ROMANS, {})
    return roman_pieces.get(ALLY, 0) > 0


def _has_any_roman_piece(state, region):
    """Check if region has any Roman piece."""
    return count_pieces(state, region, ROMANS) > 0
