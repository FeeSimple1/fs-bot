"""
Suborn Special Ability — §4.4.2 (Aedui).

Suborning buys allegiance to the Aedui or others.
May accompany Rally, March, or Raid.

Selection (§4.4.2):
  - Any one Region with a Hidden Aedui Warband.
  - No Leader requirement in base game.
  - Ariovistus with Diviciacus: within 1 of Diviciacus — A4.4, A4.1.2.

Procedure:
  - Pay 2 Aedui Resources per Ally and 1 per Warband or Auxilia.
  - Remove and/or place a total of up to 3 pieces in the Region.
  - At most 1 of the 3 may be an Allied Tribe (no Citadels).
  - Any Faction's pieces may be involved.
  - Place Allies only at Subdued Tribes (faction-restricted tribes apply).

Convictolitavis Capability (§5.3, Card 43): Expands to 6 pieces total
(max 2 Allies) across 2 regions.

Reference: §4.4.2, §1.4.2, A4.4
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    FACTIONS,
    # Piece types
    WARBAND, AUXILIA, ALLY,
    # Piece states
    HIDDEN,
    # Leaders
    DIVICIACUS,
    # Costs
    SUBORN_COST_PER_ALLY, SUBORN_COST_PER_PIECE,
    SUBORN_MAX_PIECES, SUBORN_MAX_ALLIES,
    # Scenarios
    ARIOVISTUS_SCENARIOS,
    # Tribe restrictions
    TRIBE_FACTION_RESTRICTION,
)
from fs_bot.board.pieces import (
    count_pieces_by_state, get_leader_in_region, find_leader,
    place_piece, remove_piece, get_available,
)
from fs_bot.board.control import refresh_all_control
from fs_bot.map.map_data import (
    is_adjacent, get_tribes_in_region, get_tribe_data,
)
from fs_bot.commands.common import CommandError


def validate_suborn_region(state, region):
    """Validate that a region can be selected for Suborn.

    §4.4.2: Must have a Hidden Aedui Warband. One region only (not checked
    here — caller enforces count).

    Args:
        state: Game state dict.
        region: Region to check.

    Returns:
        (True, "") if valid, (False, reason) if not.
    """
    # Must have Hidden Aedui Warband
    hidden_wb = count_pieces_by_state(
        state, region, AEDUI, WARBAND, HIDDEN
    )
    if hidden_wb < 1:
        return (False,
                "Region must have a Hidden Aedui Warband for Suborn")

    # Ariovistus Diviciacus proximity — A4.4, A4.1.2
    scenario = state["scenario"]
    if scenario in ARIOVISTUS_SCENARIOS:
        leader_region = find_leader(state, AEDUI)
        if leader_region is not None:
            # Must be within 1 of Diviciacus
            if region != leader_region and not is_adjacent(region, leader_region):
                return (False,
                        "Region must be within 1 of Diviciacus for Suborn "
                        "in Ariovistus")

    return (True, "")


def suborn(state, region, operations):
    """Execute Suborn — remove and/or place pieces.

    §4.4.2: "Pay two Aedui Resources per Ally and one Aedui Resource per
    Warband or Auxilia to remove and/or place a total of up to three such
    pieces in the Suborn Region."

    Args:
        state: Game state dict. Modified in place.
        region: Region where Suborn occurs.
        operations: List of dicts, each with:
            "action": "remove" or "place"
            "faction": Faction of the piece.
            "piece_type": WARBAND, AUXILIA, or ALLY.
            "tribe": For Ally placement, the tribe name.
            "piece_state": For remove of flippable, the state.

    Returns:
        dict with:
            "removed": List of (faction, piece_type, count).
            "placed": List of (faction, piece_type, count).
            "cost": Total resources spent.

    Raises:
        CommandError: If operation violates rules.
    """
    result = {"removed": [], "placed": [], "cost": 0}

    # Validate operation count
    if len(operations) > SUBORN_MAX_PIECES:
        raise CommandError(
            f"Suborn allows at most {SUBORN_MAX_PIECES} pieces, "
            f"got {len(operations)}"
        )

    # Count Allies in operations
    ally_ops = sum(1 for op in operations if op["piece_type"] == ALLY)
    if ally_ops > SUBORN_MAX_ALLIES:
        raise CommandError(
            f"Suborn allows at most {SUBORN_MAX_ALLIES} Ally operations, "
            f"got {ally_ops}"
        )

    # Calculate total cost
    total_cost = 0
    for op in operations:
        if op["piece_type"] == ALLY:
            total_cost += SUBORN_COST_PER_ALLY
        else:
            total_cost += SUBORN_COST_PER_PIECE

    # Check Resources
    resources = state["resources"].get(AEDUI, 0)
    if resources < total_cost:
        raise CommandError(
            f"Not enough Resources ({resources}) for Suborn "
            f"(need {total_cost})"
        )

    # Validate all operations first
    for op in operations:
        _validate_suborn_operation(state, region, op)

    # Pay cost
    state["resources"][AEDUI] -= total_cost
    result["cost"] = total_cost

    # Execute operations
    for op in operations:
        action = op["action"]
        faction = op["faction"]
        piece_type = op["piece_type"]

        if action == "remove":
            piece_state = op.get("piece_state")
            remove_piece(state, region, faction, piece_type, 1,
                         piece_state=piece_state)
            result["removed"].append((faction, piece_type, 1))

            # If removing an Ally, update tribe status
            if piece_type == ALLY:
                tribe = op.get("tribe")
                if tribe:
                    state["tribes"][tribe]["allied_faction"] = None

        elif action == "place":
            if piece_type == ALLY:
                tribe = op["tribe"]
                place_piece(state, region, faction, ALLY)
                state["tribes"][tribe]["allied_faction"] = faction
            else:
                place_piece(state, region, faction, piece_type, 1,
                            piece_state=HIDDEN)
            result["placed"].append((faction, piece_type, 1))

    refresh_all_control(state)
    return result


def _validate_suborn_operation(state, region, op):
    """Validate a single Suborn operation.

    Raises:
        CommandError: If operation is invalid.
    """
    action = op["action"]
    faction = op["faction"]
    piece_type = op["piece_type"]

    # Only Warbands, Auxilia, or Allies — no Citadels
    if piece_type not in (WARBAND, AUXILIA, ALLY):
        raise CommandError(
            f"Suborn can only affect Warbands, Auxilia, or Allies, "
            f"not {piece_type}"
        )

    if action == "remove":
        # Check piece exists in region
        piece_state = op.get("piece_state")
        if piece_type == ALLY:
            space = state["spaces"][region]
            f_pieces = space.get("pieces", {}).get(faction, {})
            if f_pieces.get(ALLY, 0) < 1:
                raise CommandError(
                    f"No {faction} Ally in {region} to remove"
                )
        else:
            if piece_state:
                avail = count_pieces_by_state(
                    state, region, faction, piece_type, piece_state
                )
            else:
                from fs_bot.board.pieces import count_pieces
                avail = count_pieces(state, region, faction, piece_type)
            if avail < 1:
                raise CommandError(
                    f"No {faction} {piece_type} in {region} to remove"
                )

    elif action == "place":
        if piece_type == ALLY:
            tribe = op.get("tribe")
            if not tribe:
                raise CommandError("Must specify tribe for Ally placement")

            # Tribe must be in region
            tribes = get_tribes_in_region(region, state["scenario"])
            if tribe not in tribes:
                raise CommandError(f"Tribe {tribe} is not in {region}")

            # Tribe must be Subdued
            tribe_info = state["tribes"].get(tribe, {})
            if tribe_info.get("allied_faction") is not None:
                raise CommandError(f"Tribe {tribe} is not Subdued")

            # Check stacking restriction — §1.4.2
            td = get_tribe_data(tribe)
            if (td.faction_restriction is not None
                    and td.faction_restriction != faction):
                raise CommandError(
                    f"Cannot place {faction} Ally at {tribe} — restricted "
                    f"to {td.faction_restriction}"
                )

            # Check Available
            avail = get_available(state, faction, ALLY)
            if avail < 1:
                raise CommandError(f"No {faction} Allies Available")
        else:
            # Check Available for Warband/Auxilia
            avail = get_available(state, faction, piece_type)
            if avail < 1:
                raise CommandError(
                    f"No {faction} {piece_type} Available"
                )

    else:
        raise CommandError(f"Unknown Suborn action: {action}")
