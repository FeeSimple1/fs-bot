"""
Enlist Special Ability — §4.5.1 (Belgae).

Enlist invites help from Germanic kinsmen.
May accompany any Command.

Selection (§4.5.1):
  - Regions in or adjacent to Germania, or further Regions with Germanic
    pieces.
  - Regions must be within one of Ambiorix or have Successor.

Two options:
1. Treat Germanic Warbands as Belgic Warbands for the accompanying Command.
   This includes Rally, March, Raid, Battle, and Control. Germanic Warbands
   cannot be voluntarily removed. Once the Command is done, they revert to
   Germanic.

2. Execute one free Limited Command with Germanic pieces (per §3.4). The
   Region need not be one selected for the Belgic Command but must be in
   leader proximity. Battling Germans must be able to Ambush (§3.4.4).

Ariovistus restrictions (A4.5.1):
  - Max 4 Germanic Warbands + Allies total.
  - May not affect Leader or Settlements.
  - May not select a Region containing Ariovistus.
  - Free Battle: no Ambush added, ignores other Germanic pieces.
  - Free Raid: provides Resources to Germans.

Reference: §4.5.1, A4.5.1
"""

from fs_bot.rules_consts import (
    # Factions
    BELGAE, GERMANS,
    # Piece types
    WARBAND, ALLY, SETTLEMENT,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Leaders
    AMBIORIX, BODUOGNATUS, ARIOVISTUS_LEADER,
    # Regions
    SUGAMBRI, UBII,
    GERMANIA_REGIONS,
    # Costs
    ENLIST_MAX_GERMAN_PIECES_ARIOVISTUS,
    # Scenarios
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
)
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, get_leader_in_region,
)
from fs_bot.map.map_data import is_adjacent, get_adjacent
from fs_bot.commands.common import CommandError, check_leader_proximity


def validate_enlist_region(state, region):
    """Validate that a region can be affected by Enlist.

    §4.5.1: Regions in or adjacent to Germania, or further Regions with
    Germanic pieces. Must be within one of Ambiorix or have Successor.

    Args:
        state: Game state dict.
        region: Region to check.

    Returns:
        (True, "") if valid, (False, reason) if not.
    """
    scenario = state["scenario"]

    # Check region eligibility: in/adjacent to Germania or has Germanic pieces
    in_or_adj_germania = (
        region in GERMANIA_REGIONS
        or any(is_adjacent(region, gr) for gr in GERMANIA_REGIONS)
    )
    has_german_pieces = count_pieces(state, region, GERMANS) > 0

    if not in_or_adj_germania and not has_german_pieces:
        return (False,
                f"Region must be in/adjacent to Germania or have Germanic "
                f"pieces for Enlist")

    # Leader proximity
    leader_name = AMBIORIX
    if scenario in ARIOVISTUS_SCENARIOS:
        leader_name = BODUOGNATUS

    valid, reason = check_leader_proximity(
        state, region, BELGAE, leader_name, "Enlist"
    )
    if not valid:
        return (False, reason)

    # Ariovistus: may not select Region containing Ariovistus — A4.5.1
    if scenario in ARIOVISTUS_SCENARIOS:
        ario_leader = get_leader_in_region(state, region, GERMANS)
        if ario_leader == ARIOVISTUS_LEADER:
            return (False,
                    "Enlist may not select a Region containing Ariovistus "
                    "(A4.5.1)")

    return (True, "")


def get_enlistable_german_pieces(state, region):
    """Get count of Germanic Warbands that can be enlisted in a region.

    Args:
        state: Game state dict.
        region: Region to check.

    Returns:
        Integer count of Germanic Warbands in the region.
    """
    total = 0
    for ps in (HIDDEN, REVEALED, SCOUTED):
        total += count_pieces_by_state(
            state, region, GERMANS, WARBAND, ps
        )
    return total


def validate_enlist_ariovistus_limit(state, total_pieces):
    """Validate that Enlist doesn't exceed Ariovistus piece limit.

    A4.5.1: "Each Enlist may affect no more than a total of four Germanic
    Warbands and Allies"

    Args:
        state: Game state dict.
        total_pieces: Total Germanic pieces being enlisted.

    Returns:
        (True, "") if valid, (False, reason) if not.
    """
    scenario = state["scenario"]
    if scenario not in ARIOVISTUS_SCENARIOS:
        return (True, "")  # No limit in base game

    if total_pieces > ENLIST_MAX_GERMAN_PIECES_ARIOVISTUS:
        return (False,
                f"Enlist may affect at most "
                f"{ENLIST_MAX_GERMAN_PIECES_ARIOVISTUS} Germanic pieces "
                f"in Ariovistus, got {total_pieces}")

    return (True, "")


