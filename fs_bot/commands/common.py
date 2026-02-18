"""Common definitions shared across command modules.

Provides the base CommandError exception and shared helper functions
used by rally, march, raid, and seize modules.
"""

from fs_bot.rules_consts import MARKER_DEVASTATED, MARKER_INTIMIDATED
from fs_bot.board.pieces import find_leader, get_leader_in_region
from fs_bot.map.map_data import is_adjacent


class CommandError(Exception):
    """Raised when a command violates game rules."""
    pass


def _is_devastated(state, region):
    """Check if a region has the Devastated marker."""
    markers = state.get("markers", {}).get(region, {})
    return MARKER_DEVASTATED in markers


def _is_intimidated(state, region):
    """Check if a region has the Intimidated marker (Ariovistus only)."""
    markers = state.get("markers", {}).get(region, {})
    return MARKER_INTIMIDATED in markers


def check_leader_proximity(state, region, faction, named_leader, sa_name):
    """Check if region is within 1 of a named leader or has Successor.

    Standard leader proximity check used by most Special Abilities (§4.1.2):
    - Named leader: region must be same or adjacent (within 1).
    - Successor: region must be the same region.

    Args:
        state: Game state dict.
        region: Region to check.
        faction: Faction owning the leader.
        named_leader: Named leader constant (CAESAR, VERCINGETORIX, etc.).
        sa_name: Name of the SA for error messages.

    Returns:
        (True, "") if valid, (False, reason) if not.
    """
    leader_region = find_leader(state, faction)
    if leader_region is None:
        return (False, f"{faction} leader not on map — cannot {sa_name}")

    actual_leader = get_leader_in_region(state, leader_region, faction)

    if actual_leader == named_leader:
        # Named leader: within 1 region (same or adjacent)
        if region == leader_region or is_adjacent(region, leader_region):
            return (True, "")
        return (False,
                f"Region must be within 1 of {named_leader} for {sa_name}")
    else:
        # Successor: must be same region — §4.1.2
        if region == leader_region:
            return (True, "")
        return (False,
                f"Successor must be in the same region for {sa_name}")
