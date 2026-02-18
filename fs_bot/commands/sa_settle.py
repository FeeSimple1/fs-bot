"""
Settle Special Ability — A4.6.1 (Germanic, Ariovistus only).

Settling establishes Germanic Settlements in Gaul.
May accompany Rally or March Commands — NOT Raid or Battle.

Selection (A4.6.1):
  - Outside Germania.
  - Adjacent to Germania and/or to a Germanic Settlement already on map.
  - Under Germanic Control.
  - Within one of Ariovistus or the Region with Successor.

Procedure:
  - Pay 2 Resources per Region (4 if Devastated).
  - Place one Settlement (within stacking: max 1 per region).

NOTE: A new Settlement can immediately qualify an adjacent Region for
further Settling in the same SA execution.

Reference: A4.6.1, A1.4, A1.4.2
"""

from fs_bot.rules_consts import (
    # Factions
    GERMANS,
    # Piece types
    SETTLEMENT,
    # Leaders
    ARIOVISTUS_LEADER,
    # Regions
    GERMANIA_REGIONS,
    # Costs
    SETTLE_COST,
    # Stacking
    MAX_SETTLEMENTS_PER_REGION,
    # Markers
    MARKER_DEVASTATED,
    # Scenarios
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
)
from fs_bot.board.pieces import (
    place_piece, get_available, count_pieces,
    get_leader_in_region, find_leader,
)
from fs_bot.board.control import is_controlled_by, refresh_all_control
from fs_bot.map.map_data import is_adjacent, get_adjacent
from fs_bot.commands.common import CommandError, _is_devastated


def validate_settle_region(state, region, newly_placed_settlements=None):
    """Validate that a region can be selected for Settle.

    A4.6.1: Outside Germania, adjacent to Germania and/or existing
    Settlement, under Germanic Control, within 1 of Ariovistus or
    Successor.

    Args:
        state: Game state dict.
        region: Region to check.
        newly_placed_settlements: Set of regions where Settlements were
            placed earlier in this same SA execution (for chaining).

    Returns:
        (True, "") if valid, (False, reason) if not.
    """
    scenario = state["scenario"]
    if scenario not in ARIOVISTUS_SCENARIOS:
        return (False, "Settle is only available in Ariovistus")

    # Must be outside Germania — A4.6.1
    if region in GERMANIA_REGIONS:
        return (False, "Settle must be outside Germania")

    # Must be adjacent to Germania and/or a Germanic Settlement — A4.6.1
    adj_to_germania = any(
        is_adjacent(region, gr) for gr in GERMANIA_REGIONS
    )
    adj_to_settlement = _adjacent_to_settlement(
        state, region, newly_placed_settlements
    )

    if not adj_to_germania and not adj_to_settlement:
        return (False,
                "Settle region must be adjacent to Germania or an existing "
                "Germanic Settlement")

    # Must be under Germanic Control — A4.6.1
    if not is_controlled_by(state, region, GERMANS):
        return (False, "Region must be under Germanic Control for Settle")

    # Must be within 1 of Ariovistus or Successor — A4.6.1, A4.1.2
    valid, reason = _check_settle_leader(state, region)
    if not valid:
        return (False, reason)

    # Stacking: max 1 Settlement per region — A1.4.2
    space = state["spaces"][region]
    german_pieces = space.get("pieces", {}).get(GERMANS, {})
    if german_pieces.get(SETTLEMENT, 0) >= MAX_SETTLEMENTS_PER_REGION:
        return (False,
                f"Region already has a Settlement (max "
                f"{MAX_SETTLEMENTS_PER_REGION})")

    return (True, "")


def settle(state, region):
    """Place a Settlement in a region via Settle.

    A4.6.1: Pay 2 Resources (4 if Devastated). Place one Settlement.

    Args:
        state: Game state dict. Modified in place.
        region: Region to place Settlement in.

    Returns:
        dict with:
            "placed": SETTLEMENT
            "cost": Resource cost paid.

    Raises:
        CommandError: If operation violates rules.
    """
    scenario = state["scenario"]
    if scenario not in ARIOVISTUS_SCENARIOS:
        raise CommandError("Settle is only available in Ariovistus")

    # Calculate cost — A4.6.1
    cost = SETTLE_COST
    if _is_devastated(state, region):
        cost *= 2

    # Check Resources
    resources = state["resources"].get(GERMANS, 0)
    if resources < cost:
        raise CommandError(
            f"Not enough Resources ({resources}) for Settle "
            f"(need {cost})"
        )

    # Check Available
    avail = get_available(state, GERMANS, SETTLEMENT)
    if avail < 1:
        raise CommandError("No Settlements Available")

    # Pay cost
    state["resources"][GERMANS] -= cost

    # Place Settlement
    place_piece(state, region, GERMANS, SETTLEMENT)

    # Refresh control — Settlement counts for Germanic control
    refresh_all_control(state)

    return {"placed": SETTLEMENT, "cost": cost}


def _adjacent_to_settlement(state, region, newly_placed=None):
    """Check if region is adjacent to any existing Germanic Settlement."""
    adj_regions = get_adjacent(region)
    for adj in adj_regions:
        space = state["spaces"].get(adj, {})
        german_pieces = space.get("pieces", {}).get(GERMANS, {})
        if german_pieces.get(SETTLEMENT, 0) > 0:
            return True
    # Also check newly placed settlements from this SA execution
    if newly_placed:
        for adj in adj_regions:
            if adj in newly_placed:
                return True
    return False


def _check_settle_leader(state, region):
    """Check leader proximity for Settle.

    A4.6.1: "within a distance of one Region from Ariovistus, or the
    Region with his Successor"
    """
    leader_region = find_leader(state, GERMANS)
    if leader_region is None:
        return (False, "Germanic leader not on map — cannot Settle")

    actual_leader = get_leader_in_region(state, leader_region, GERMANS)

    if actual_leader == ARIOVISTUS_LEADER:
        if region == leader_region or is_adjacent(region, leader_region):
            return (True, "")
        return (False,
                "Region must be within 1 of Ariovistus for Settle")
    else:
        if region == leader_region:
            return (True, "")
        return (False,
                "Successor must be in the same region for Settle")
