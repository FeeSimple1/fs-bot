"""
Intimidate Special Ability — A4.6.2 (Germanic, Ariovistus only).

Intimidation cows enemies into submission.
May accompany March, Raid, or Battle Commands — NOT Rally.

Selection (A4.6.2):
  - Region has Ariovistus, OR
  - Region is under Germanic Control and within one of Ariovistus or
    has Successor.

Procedure per region:
  - Flip one or two Hidden Germanic Warbands to Revealed.
  - Place an Intimidated marker there (if none already).
  - Remove that many Warbands, Auxilia, and/or Allies of one Faction
    that has no Leader there.

INTIMIDATED markers block non-Germanic Recruit and Rally by factions
without a Leader in the region. Removed in Spring (A6.6).

Reference: A4.6.2, A3.2.1, A3.3.1
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    # Piece types
    WARBAND, AUXILIA, ALLY, LEGION,
    # Piece states
    HIDDEN, REVEALED,
    # Leaders
    ARIOVISTUS_LEADER,
    # Markers
    MARKER_INTIMIDATED,
    # Scenarios
    ARIOVISTUS_SCENARIOS,
)
from fs_bot.board.pieces import (
    count_pieces_by_state, get_leader_in_region, find_leader,
    flip_piece, remove_piece,
)
from fs_bot.board.control import is_controlled_by, refresh_all_control
from fs_bot.map.map_data import is_adjacent
from fs_bot.commands.common import CommandError


def validate_intimidate_region(state, region):
    """Validate that a region can be selected for Intimidate.

    A4.6.2: Region has Ariovistus, OR Region is under Germanic Control
    and within one of Ariovistus or has Successor.

    Args:
        state: Game state dict.
        region: Region to check.

    Returns:
        (True, "") if valid, (False, reason) if not.
    """
    scenario = state["scenario"]
    if scenario not in ARIOVISTUS_SCENARIOS:
        return (False, "Intimidate is only available in Ariovistus")

    # Option 1: Region has Ariovistus
    german_leader = get_leader_in_region(state, region, GERMANS)
    if german_leader == ARIOVISTUS_LEADER:
        return (True, "")

    # Option 2: Germanic Control + within 1 of Ariovistus or Successor
    if not is_controlled_by(state, region, GERMANS):
        return (False,
                "Region must have Ariovistus or be under Germanic Control "
                "for Intimidate")

    valid, reason = _check_intimidate_leader(state, region)
    if not valid:
        return (False, reason)

    return (True, "")


def intimidate(state, region, warbands_to_flip, target_faction,
               target_removals):
    """Execute Intimidate in a region.

    A4.6.2: Flip 1-2 Hidden Germanic Warbands to Revealed. Place
    Intimidated marker. Remove that many enemy pieces.

    Args:
        state: Game state dict. Modified in place.
        region: Region where Intimidate occurs.
        warbands_to_flip: Number of Hidden Warbands to flip (1 or 2).
        target_faction: Faction targeted for removal.
        target_removals: List of (piece_type, piece_state_or_None) to
            remove from target. Length must equal warbands_to_flip.

    Returns:
        dict with:
            "warbands_flipped": Number of Warbands flipped.
            "intimidated_placed": True if marker placed.
            "target_removed": List of (piece_type, 1).

    Raises:
        CommandError: If operation violates rules.
    """
    scenario = state["scenario"]
    if scenario not in ARIOVISTUS_SCENARIOS:
        raise CommandError("Intimidate is only available in Ariovistus")

    # Validate warbands_to_flip: 1 or 2
    if warbands_to_flip not in (1, 2):
        raise CommandError(
            f"Must flip 1 or 2 Warbands for Intimidate, got "
            f"{warbands_to_flip}"
        )

    # Check Hidden Warbands available
    hidden_wb = count_pieces_by_state(
        state, region, GERMANS, WARBAND, HIDDEN
    )
    if hidden_wb < warbands_to_flip:
        raise CommandError(
            f"Only {hidden_wb} Hidden Germanic Warbands in {region}, "
            f"need {warbands_to_flip}"
        )

    # Validate target: must have no Leader in region — A4.6.2
    if target_faction == GERMANS:
        raise CommandError("Cannot Intimidate own faction")

    target_leader = get_leader_in_region(state, region, target_faction)
    if target_leader is not None:
        raise CommandError(
            f"{target_faction} has a Leader in {region} — cannot Intimidate"
        )

    # Validate removals match flip count
    if len(target_removals) != warbands_to_flip:
        raise CommandError(
            f"Must remove exactly {warbands_to_flip} pieces, "
            f"got {len(target_removals)}"
        )

    # Validate target piece types: Warbands, Auxilia, Allies — A4.6.2
    for piece_type, piece_state in target_removals:
        if piece_type not in (WARBAND, AUXILIA, ALLY):
            raise CommandError(
                f"Intimidate can only remove Warbands, Auxilia, or Allies, "
                f"not {piece_type}"
            )

    result = {
        "warbands_flipped": warbands_to_flip,
        "intimidated_placed": False,
        "target_removed": [],
    }

    # Flip Germanic Warbands
    flip_piece(state, region, GERMANS, WARBAND,
               count=warbands_to_flip,
               from_state=HIDDEN, to_state=REVEALED)

    # Place Intimidated marker
    markers = state.get("markers", {})
    region_markers = markers.setdefault(region, {})
    if MARKER_INTIMIDATED not in region_markers:
        region_markers[MARKER_INTIMIDATED] = True
        result["intimidated_placed"] = True

    # Remove target pieces
    for piece_type, piece_state in target_removals:
        if piece_type == ALLY:
            remove_piece(state, region, target_faction, ALLY, 1)
        else:
            remove_piece(state, region, target_faction, piece_type, 1,
                         piece_state=piece_state)
        result["target_removed"].append((piece_type, 1))

    refresh_all_control(state)
    return result


def _check_intimidate_leader(state, region):
    """Check leader proximity for Intimidate.

    A4.6.2: "within a distance of one Region from Ariovistus or have his
    Successor in them"
    """
    leader_region = find_leader(state, GERMANS)
    if leader_region is None:
        return (False, "Germanic leader not on map — cannot Intimidate")

    actual_leader = get_leader_in_region(state, leader_region, GERMANS)

    if actual_leader == ARIOVISTUS_LEADER:
        if region == leader_region or is_adjacent(region, leader_region):
            return (True, "")
        return (False,
                "Region must be within 1 of Ariovistus for Intimidate")
    else:
        if region == leader_region:
            return (True, "")
        return (False,
                "Successor must be in the same region for Intimidate")
