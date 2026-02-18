"""
Rampage Special Ability — §4.5.2 (Belgae).

Rampaging demonstrates Belgic ferocity to frighten enemy Forces out of
Regions and compel surrender.
May accompany Rally, Raid, or Battle.

Selection (§4.5.2):
  - Region must have Hidden Belgic Warbands.
  - Region must be within one of Ambiorix or have Successor.

Procedure per region:
  1. Select one target Roman or Gallic Faction (not Germanic) that has
     neither a Leader, nor a Citadel, nor a Fort in the Region.
  2. Target Faction must remove or Retreat one piece (Warband, Auxilia,
     or Legion — no roll) per Hidden Belgic Warband that the Belgae
     flip to Revealed.
  3. Retreat per Battle procedure — into one adjacent Region where the
     targeted Faction or an agreeing Faction has Control.

Ariovistus note (A4.5 NOTE): Rampage may not Target Germans. When
targeting Arverni in Ariovistus, they are removed rather than Retreating
(since Arverni never Retreat in Ariovistus — A3.2.4).

Reference: §4.5.2, §3.2.4, §3.3.4, A4.5
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    GALLIC_FACTIONS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND, FORT, CITADEL,
    FLIPPABLE_PIECES,
    # Piece states
    HIDDEN, REVEALED,
    # Leaders
    AMBIORIX, BODUOGNATUS,
    # Scenarios
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
)
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, get_leader_in_region,
    flip_piece, remove_piece, move_piece,
)
from fs_bot.board.control import refresh_all_control
from fs_bot.map.map_data import is_adjacent
from fs_bot.commands.common import CommandError, check_leader_proximity


def validate_rampage_region(state, region):
    """Validate that a region can be selected for Rampage.

    §4.5.2: Must have Hidden Belgic Warbands and be within one of
    Ambiorix or have Successor.

    Args:
        state: Game state dict.
        region: Region to check.

    Returns:
        (True, "") if valid, (False, reason) if not.
    """
    scenario = state["scenario"]

    # Must have Hidden Belgic Warbands
    hidden_wb = count_pieces_by_state(
        state, region, BELGAE, WARBAND, HIDDEN
    )
    if hidden_wb < 1:
        return (False,
                "Region must have Hidden Belgic Warbands for Rampage")

    # Leader proximity
    leader_name = AMBIORIX
    if scenario in ARIOVISTUS_SCENARIOS:
        leader_name = BODUOGNATUS

    valid, reason = check_leader_proximity(
        state, region, BELGAE, leader_name, "Rampage"
    )
    if not valid:
        return (False, reason)

    return (True, "")


def validate_rampage_target(state, region, target_faction):
    """Validate that a faction can be targeted by Rampage.

    §4.5.2: Target must be Roman or Gallic (not Germanic), and must not
    have a Leader, Citadel, or Fort in the Region.

    A4.5 NOTE: Rampage may not Target Germans.

    Args:
        state: Game state dict.
        region: Rampage region.
        target_faction: Faction to target.

    Returns:
        (True, "") if valid, (False, reason) if not.
    """
    # Cannot target self
    if target_faction == BELGAE:
        return (False, "Cannot Rampage own faction")

    # Cannot target Germans — §4.5.2, A4.5 NOTE
    if target_faction == GERMANS:
        return (False, "Rampage cannot target Germans")

    # Must be Roman or Gallic
    if target_faction not in (ROMANS, ARVERNI, AEDUI):
        return (False, f"Rampage can only target Roman or Gallic factions")

    # Target must not have Leader, Citadel, or Fort in region
    space = state["spaces"][region]
    t_pieces = space.get("pieces", {}).get(target_faction, {})

    if get_leader_in_region(state, region, target_faction) is not None:
        return (False,
                f"{target_faction} has a Leader in {region} — cannot Rampage")

    if t_pieces.get(CITADEL, 0) > 0:
        return (False,
                f"{target_faction} has a Citadel in {region} — cannot Rampage")

    if t_pieces.get(FORT, 0) > 0:
        return (False,
                f"{target_faction} has a Fort in {region} — cannot Rampage")

    return (True, "")


def rampage(state, region, target_faction, warbands_to_flip,
            target_actions):
    """Execute Rampage in a region.

    §4.5.2: Belgae flip Hidden Warbands to Revealed. For each flipped
    Warband, the target must remove or Retreat one piece.

    Args:
        state: Game state dict. Modified in place.
        region: Region where Rampage occurs.
        target_faction: Faction being Rampaged.
        warbands_to_flip: Number of Hidden Belgic Warbands to flip.
        target_actions: List of dicts, one per flipped Warband:
            "action": "remove" or "retreat"
            "piece_type": WARBAND, AUXILIA, or LEGION
            "piece_state": For flippable, the state.
            "retreat_region": For retreat, the destination.

    Returns:
        dict with:
            "warbands_flipped": Number of Belgic Warbands flipped.
            "target_removed": List of (piece_type, count).
            "target_retreated": List of (piece_type, retreat_region).

    Raises:
        CommandError: If operation violates rules.
    """
    scenario = state["scenario"]

    # Validate we have enough Hidden Warbands
    hidden_wb = count_pieces_by_state(
        state, region, BELGAE, WARBAND, HIDDEN
    )
    if hidden_wb < warbands_to_flip:
        raise CommandError(
            f"Only {hidden_wb} Hidden Belgic Warbands in {region}, "
            f"need {warbands_to_flip}"
        )

    # Must have matching target actions
    if len(target_actions) != warbands_to_flip:
        raise CommandError(
            f"Need exactly {warbands_to_flip} target actions, "
            f"got {len(target_actions)}"
        )

    result = {
        "warbands_flipped": warbands_to_flip,
        "target_removed": [],
        "target_retreated": [],
    }

    # Flip Belgic Warbands from Hidden to Revealed
    flip_piece(state, region, BELGAE, WARBAND,
               count=warbands_to_flip,
               from_state=HIDDEN, to_state=REVEALED)

    # Process target actions
    for action_info in target_actions:
        action = action_info["action"]
        piece_type = action_info["piece_type"]
        piece_state = action_info.get("piece_state")

        if piece_type not in (WARBAND, AUXILIA, LEGION):
            raise CommandError(
                f"Rampage can only affect Warbands, Auxilia, or Legions, "
                f"not {piece_type}"
            )

        if action == "remove":
            # A4.5 NOTE: "When Rampage Targets Arverni, they are removed
            # rather than Retreating" in Ariovistus.
            if piece_type == LEGION:
                remove_piece(state, region, target_faction, LEGION, 1,
                             to_fallen=True)
            else:
                remove_piece(state, region, target_faction, piece_type, 1,
                             piece_state=piece_state)
            result["target_removed"].append((piece_type, 1))

        elif action == "retreat":
            retreat_region = action_info.get("retreat_region")
            if retreat_region is None:
                raise CommandError(
                    "Must specify retreat_region for Rampage retreat"
                )

            # A4.5 NOTE: Arverni never retreat in Ariovistus
            if (target_faction == ARVERNI
                    and scenario in ARIOVISTUS_SCENARIOS):
                raise CommandError(
                    "Arverni cannot Retreat in Ariovistus — must remove"
                )

            # Retreat to adjacent controlled region
            if not is_adjacent(region, retreat_region):
                raise CommandError(
                    f"{retreat_region} is not adjacent to {region}"
                )

            # Move the piece
            if piece_type == LEGION:
                move_piece(state, region, retreat_region,
                           target_faction, LEGION)
            else:
                move_piece(state, region, retreat_region,
                           target_faction, piece_type,
                           piece_state=piece_state)
            result["target_retreated"].append(
                (piece_type, retreat_region)
            )

        else:
            raise CommandError(f"Unknown Rampage action: {action}")

    refresh_all_control(state)
    return result


