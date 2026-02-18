"""
Entreat Special Ability — §4.3.1 (Arverni, base game only).

Entreaties sponsor betrayals of allegiance from the enemy to the Arverni.
May accompany any type of Command.

Selection (§4.3.1):
  - Region must have a Hidden Arverni Warband.
  - Region must be within one of Vercingetorix or same as Successor.

Procedure per region:
  - Pay 1 Resource per Region.
  - Replace one non-Arverni Warband or Auxilia with an Arverni Warband,
    OR — only if Arverni Controlled — replace one Aedui, Belgic, or
    Germanic Allied Tribe with an Arverni Allied Tribe.
  - If Arverni piece not available or couldn't stack: remove rather than
    replace.

NOT available in Ariovistus — A4.3.

Reference: §4.3.1, §1.4.1, §1.4.2
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    # Piece types
    WARBAND, AUXILIA, ALLY, CITADEL,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Leaders
    VERCINGETORIX,
    # Costs
    ENTREAT_COST,
    # Scenarios
    ARIOVISTUS_SCENARIOS,
    # Tribe restrictions
    TRIBE_FACTION_RESTRICTION,
)
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state,
    place_piece, remove_piece, get_available,
)
from fs_bot.board.control import is_controlled_by, refresh_all_control
from fs_bot.map.map_data import get_tribes_in_region, get_tribe_data
from fs_bot.commands.common import CommandError, check_leader_proximity


def validate_entreat_region(state, region):
    """Validate that a region can be selected for Entreat.

    §4.3.1: Region must have a Hidden Arverni Warband and be within one
    of Vercingetorix or same Region as Successor.

    Args:
        state: Game state dict.
        region: Region to check.

    Returns:
        (True, "") if valid, (False, reason) if not.
    """
    scenario = state["scenario"]
    if scenario in ARIOVISTUS_SCENARIOS:
        return (False, "Entreat is not available in Ariovistus (A4.3)")

    # Must have Hidden Arverni Warband
    hidden_wb = count_pieces_by_state(
        state, region, ARVERNI, WARBAND, HIDDEN
    )
    if hidden_wb < 1:
        return (False,
                "Region must have a Hidden Arverni Warband for Entreat")

    # Leader proximity
    valid, reason = check_leader_proximity(
        state, region, ARVERNI, VERCINGETORIX, "Entreat"
    )
    if not valid:
        return (False, reason)

    return (True, "")


def entreat_replace_piece(state, region, target_faction, target_piece_type,
                          target_piece_state=None):
    """Replace one enemy Warband or Auxilia with an Arverni Warband.

    §4.3.1: "replace either any one non-Arverni Warband or Auxilia there...
    with their Arverni counterparts (one Arverni Warband for each enemy
    Warband or Auxilia)"

    If the Arverni Warband is not available: remove the target instead.

    Cost: 1 Resource per Region (caller is responsible for tracking this
    across multiple Entreat calls).

    Args:
        state: Game state dict. Modified in place.
        region: Region where Entreat occurs.
        target_faction: Faction whose piece to replace.
        target_piece_type: WARBAND or AUXILIA.
        target_piece_state: HIDDEN/REVEALED/SCOUTED for the target.

    Returns:
        dict with:
            "target_removed": (faction, piece_type)
            "arverni_placed": True if replacement placed, False if just removed.
            "cost": ENTREAT_COST

    Raises:
        CommandError: If operation violates rules.
    """
    if target_faction == ARVERNI:
        raise CommandError("Cannot Entreat own pieces")

    if target_piece_type not in (WARBAND, AUXILIA):
        raise CommandError(
            f"Can only Entreat Warbands or Auxilia, not {target_piece_type}"
        )

    # Check Resources
    resources = state["resources"].get(ARVERNI, 0)
    if resources < ENTREAT_COST:
        raise CommandError(
            f"Not enough Resources ({resources}) for Entreat "
            f"(need {ENTREAT_COST})"
        )

    # Check target exists
    if target_piece_state:
        available_count = count_pieces_by_state(
            state, region, target_faction, target_piece_type,
            target_piece_state
        )
    else:
        available_count = count_pieces(
            state, region, target_faction, target_piece_type
        )

    if available_count < 1:
        raise CommandError(
            f"No {target_faction} {target_piece_type} in {region}"
        )

    # Pay cost
    state["resources"][ARVERNI] -= ENTREAT_COST

    # Remove the target piece
    remove_piece(state, region, target_faction, target_piece_type, 1,
                 piece_state=target_piece_state)

    # Try to place Arverni Warband
    arverni_avail = get_available(state, ARVERNI, WARBAND)
    placed = False
    if arverni_avail >= 1:
        place_piece(state, region, ARVERNI, WARBAND, 1, piece_state=HIDDEN)
        placed = True

    refresh_all_control(state)

    return {
        "target_removed": (target_faction, target_piece_type),
        "arverni_placed": placed,
        "cost": ENTREAT_COST,
    }


def entreat_replace_ally(state, region, target_faction, tribe):
    """Replace one enemy Allied Tribe with an Arverni Allied Tribe.

    §4.3.1: "only if the Region is already Arverni Controlled — one Aedui,
    Belgic, or Germanic Allied Tribe there (not a Citadel, Roman Ally, or
    Subdued Tribe)"

    Cost: 1 Resource per Region.

    Args:
        state: Game state dict. Modified in place.
        region: Region where Entreat occurs.
        target_faction: Faction whose Ally to replace (Aedui, Belgae, or Germans).
        tribe: Tribe name constant where Ally is located.

    Returns:
        dict with:
            "target_removed": (faction, tribe)
            "arverni_placed": True if replacement placed.
            "cost": ENTREAT_COST

    Raises:
        CommandError: If operation violates rules.
    """
    # Must be Arverni Controlled
    if not is_controlled_by(state, region, ARVERNI):
        raise CommandError(
            "Region must be Arverni Controlled to Entreat an Allied Tribe"
        )

    # Target must be Aedui, Belgic, or Germanic — not Roman
    if target_faction not in (AEDUI, BELGAE, GERMANS):
        raise CommandError(
            f"Can only Entreat Aedui, Belgic, or Germanic Allies, "
            f"not {target_faction}"
        )

    # Check the tribe is in this region and allied to target
    tribes = get_tribes_in_region(region, state["scenario"])
    if tribe not in tribes:
        raise CommandError(f"Tribe {tribe} is not in {region}")

    tribe_info = state["tribes"].get(tribe, {})
    if tribe_info.get("allied_faction") != target_faction:
        raise CommandError(
            f"Tribe {tribe} is not allied to {target_faction}"
        )

    # Check Resources
    resources = state["resources"].get(ARVERNI, 0)
    if resources < ENTREAT_COST:
        raise CommandError(
            f"Not enough Resources ({resources}) for Entreat "
            f"(need {ENTREAT_COST})"
        )

    # Check stacking for Arverni Ally — §1.4.2
    td = get_tribe_data(tribe)
    can_place = True
    if td.faction_restriction is not None and td.faction_restriction != ARVERNI:
        can_place = False

    # Pay cost
    state["resources"][ARVERNI] -= ENTREAT_COST

    # Remove enemy Ally
    remove_piece(state, region, target_faction, ALLY, 1)
    state["tribes"][tribe]["allied_faction"] = None

    # Try to place Arverni Ally
    placed = False
    if can_place:
        arverni_avail = get_available(state, ARVERNI, ALLY)
        if arverni_avail >= 1:
            place_piece(state, region, ARVERNI, ALLY)
            state["tribes"][tribe]["allied_faction"] = ARVERNI
            placed = True

    refresh_all_control(state)

    return {
        "target_removed": (target_faction, tribe),
        "arverni_placed": placed,
        "cost": ENTREAT_COST,
    }


