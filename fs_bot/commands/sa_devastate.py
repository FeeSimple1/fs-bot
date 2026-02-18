"""
Devastate Special Ability — §4.3.2 (Arverni, base game only).

Devastation starves armies and hinders many actions.
May accompany any Command.

Selection (§4.3.2):
  - Region must be Arverni-Controlled.
  - Region must be within one of Vercingetorix or have Successor.

Procedure per region:
  - Arverni remove 1 in 4 of their Warbands there (round down).
  - Each other Faction removes 1 in 3 of its total Warbands, Auxilia,
    and Legions there (round down; owners choose which; Legions to Fallen).
  - Place a Devastated marker (if none already).

NOT available in Ariovistus — A4.3.

Reference: §4.3.2, §4.3.3 (this is the Devastate SA not the Ambush §4.3.3)
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    FACTIONS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND,
    FLIPPABLE_PIECES,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Leaders
    VERCINGETORIX,
    # Markers
    MARKER_DEVASTATED,
    # Scenarios
    ARIOVISTUS_SCENARIOS,
)
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, remove_piece,
)
from fs_bot.board.control import is_controlled_by, refresh_all_control
from fs_bot.commands.common import CommandError, check_leader_proximity


def validate_devastate_region(state, region):
    """Validate that a region can be selected for Devastate.

    §4.3.2: Arverni-Controlled, within one of Vercingetorix or same
    Region as Successor.

    Args:
        state: Game state dict.
        region: Region to check.

    Returns:
        (True, "") if valid, (False, reason) if not.
    """
    scenario = state["scenario"]
    if scenario in ARIOVISTUS_SCENARIOS:
        return (False, "Devastate is not available in Ariovistus (A4.3)")

    # Must be Arverni Controlled
    if not is_controlled_by(state, region, ARVERNI):
        return (False, "Region must be Arverni Controlled for Devastate")

    # Leader proximity
    valid, reason = check_leader_proximity(
        state, region, ARVERNI, VERCINGETORIX, "Devastate"
    )
    if not valid:
        return (False, reason)

    return (True, "")


def devastate_region(state, region, removals=None):
    """Execute Devastation in a region.

    §4.3.2:
    - Arverni remove 1 in 4 of their Warbands (round down).
    - Each other Faction removes 1 in 3 of total Warbands + Auxilia +
      Legions (round down; owners choose which; Legions to Fallen).
    - Place Devastated marker.

    Args:
        state: Game state dict. Modified in place.
        region: Region to Devastate.
        removals: Optional dict of {faction: [(piece_type, piece_state, count)]}
            specifying which pieces each faction removes. If None, removes
            using default priority (Warbands first, then Auxilia, then
            Legions). Owner chooses are handled by the caller in bot/player
            decision phase.

    Returns:
        dict with:
            "removed": {faction: [(piece_type, count)]}
            "devastated_placed": True if marker placed.

    Raises:
        CommandError: If operation violates rules.
    """
    result = {"removed": {}, "devastated_placed": False}

    # Calculate removals per faction
    for faction in FACTIONS:
        space = state["spaces"][region]
        f_pieces = space.get("pieces", {}).get(faction, {})

        if faction == ARVERNI:
            # Remove 1 in 4 Warbands — §4.3.2
            total_wb = _count_all_flippable(f_pieces, WARBAND)
            to_remove = total_wb // 4
        else:
            # Remove 1 in 3 of (Warbands + Auxilia + Legions) — §4.3.2
            total_wb = _count_all_flippable(f_pieces, WARBAND)
            total_aux = _count_all_flippable(f_pieces, AUXILIA)
            total_leg = f_pieces.get(LEGION, 0)
            total_mobile = total_wb + total_aux + total_leg
            to_remove = total_mobile // 3

        if to_remove == 0:
            continue

        # Use caller-provided removals if available
        if removals and faction in removals:
            faction_removals = removals[faction]
            removed_count = 0
            faction_result = []
            for piece_type, piece_state, count in faction_removals:
                if removed_count + count > to_remove:
                    count = to_remove - removed_count
                if count <= 0:
                    continue
                if piece_type == LEGION:
                    remove_piece(state, region, faction, LEGION, count,
                                 to_fallen=True)
                else:
                    remove_piece(state, region, faction, piece_type, count,
                                 piece_state=piece_state)
                faction_result.append((piece_type, count))
                removed_count += count
                if removed_count >= to_remove:
                    break
            result["removed"][faction] = faction_result
        else:
            # Default removal: Warbands, then Auxilia, then Legions
            faction_result = []
            remaining = to_remove

            if faction == ARVERNI:
                # Only Warbands for Arverni
                remaining = _remove_warbands(
                    state, region, faction, remaining, faction_result
                )
            else:
                # Other factions: Warbands → Auxilia → Legions
                remaining = _remove_warbands(
                    state, region, faction, remaining, faction_result
                )
                if remaining > 0:
                    remaining = _remove_auxilia(
                        state, region, faction, remaining, faction_result
                    )
                if remaining > 0:
                    # Legions to Fallen
                    leg_count = state["spaces"][region].get(
                        "pieces", {}
                    ).get(faction, {}).get(LEGION, 0)
                    leg_remove = min(remaining, leg_count)
                    if leg_remove > 0:
                        remove_piece(state, region, faction, LEGION,
                                     leg_remove, to_fallen=True)
                        faction_result.append((LEGION, leg_remove))
                        remaining -= leg_remove

            if faction_result:
                result["removed"][faction] = faction_result

    # Place Devastated marker — §4.3.2
    markers = state.setdefault("markers", {})
    region_markers = markers.setdefault(region, {})
    if MARKER_DEVASTATED not in region_markers:
        region_markers[MARKER_DEVASTATED] = True
        result["devastated_placed"] = True

    refresh_all_control(state)

    return result


def _count_all_flippable(faction_pieces, piece_type):
    """Count all instances of a flippable piece type across all states."""
    total = 0
    for ps in (HIDDEN, REVEALED, SCOUTED):
        total += faction_pieces.get(ps, {}).get(piece_type, 0)
    return total


def _remove_warbands(state, region, faction, remaining, result_list):
    """Remove Warbands (default ordering) and return remaining count."""
    space = state["spaces"][region]
    f_pieces = space.get("pieces", {}).get(faction, {})
    total_wb = _count_all_flippable(f_pieces, WARBAND)
    wb_remove = min(remaining, total_wb)
    if wb_remove > 0:
        remove_piece(state, region, faction, WARBAND, wb_remove)
        result_list.append((WARBAND, wb_remove))
    return remaining - wb_remove


def _remove_auxilia(state, region, faction, remaining, result_list):
    """Remove Auxilia (default ordering) and return remaining count."""
    space = state["spaces"][region]
    f_pieces = space.get("pieces", {}).get(faction, {})
    total_aux = _count_all_flippable(f_pieces, AUXILIA)
    aux_remove = min(remaining, total_aux)
    if aux_remove > 0:
        remove_piece(state, region, faction, AUXILIA, aux_remove)
        result_list.append((AUXILIA, aux_remove))
    return remaining - aux_remove


