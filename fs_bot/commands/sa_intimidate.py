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
    HIDDEN, REVEALED, SCOUTED,
    # Leaders
    ARIOVISTUS_LEADER,
    # Markers
    MARKER_INTIMIDATED,
    # Scenarios
    ARIOVISTUS_SCENARIOS,
)
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, get_leader_in_region,
    flip_piece, remove_piece, clear_allied_tribe,
)
from fs_bot.board.control import is_controlled_by, refresh_all_control
from fs_bot.commands.common import CommandError, check_leader_proximity


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

    valid, reason = check_leader_proximity(
        state, region, GERMANS, ARIOVISTUS_LEADER, "Intimidate"
    )
    if not valid:
        return (False, reason)

    return (True, "")


def intimidate(state, region, warbands_to_flip, target_faction,
               target_removals, *, revealed_by_raid=0):
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

    # A3.4.3: the SAME Warbands may Raid and Intimidate simultaneously.
    # Only the engine's successful Raid result supplies this credit; an
    # action's caller-controlled ``free`` flag never supplies it.
    if (type(revealed_by_raid) is not int
            or not 0 <= revealed_by_raid <= warbands_to_flip
            or count_pieces_by_state(state, region, GERMANS, WARBAND,
                                     REVEALED) < revealed_by_raid):
        raise CommandError("Invalid Raiding Warband credit for Intimidate")
    fresh_flips = warbands_to_flip - revealed_by_raid
    # Check Hidden Warbands available
    hidden_wb = count_pieces_by_state(
        state, region, GERMANS, WARBAND, HIDDEN
    )
    if hidden_wb < fresh_flips:
        raise CommandError(
            f"Only {hidden_wb} Hidden Germanic Warbands in {region}, "
            f"need {fresh_flips}"
        )

    # Validate target: must have no Leader in region — A4.6.2
    from fs_bot.rules_consts import ROMANS as _ROMANS
    if (target_faction == _ROMANS
            and state.get("event_modifiers", {}).get("card_A22_no_intimidate_romans")):
        raise CommandError(
            "A22: Intimidate has no effect on Romans")
    if target_faction == GERMANS:
        raise CommandError("Cannot Intimidate own faction")

    target_leader = (get_leader_in_region(state, region, target_faction)
                     if target_faction is not None else None)
    if target_leader is not None:
        raise CommandError(
            f"{target_faction} has a Leader in {region} — cannot Intimidate"
        )

    # Validate removals match flip count
    marker_only = target_faction is None and not target_removals
    if not marker_only and len(target_removals) != warbands_to_flip:
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

    # Validate every removal before flipping or placing a marker. A plan may
    # mix specified visibility with "any"; reserve those pieces in the same
    # Hidden/Revealed/Scouted order used by remove_piece.
    pool = {(pt, ps): count_pieces_by_state(state, region, target_faction, pt, ps)
            for pt in (WARBAND, AUXILIA) for ps in (HIDDEN, REVEALED, SCOUTED)}
    pool[(ALLY, None)] = (count_pieces(state, region, target_faction, ALLY)
                          if target_faction is not None else 0)
    for pt, ps in target_removals:
        choices = (None,) if pt == ALLY else ((ps,) if ps is not None
                                             else (HIDDEN, REVEALED, SCOUTED))
        selected = next((p for p in choices if pool.get((pt, p), 0) > 0), False)
        if selected is False:
            raise CommandError(f"Not enough {target_faction} {pt} in {region}")
        pool[(pt, selected)] -= 1

    result = {
        "warbands_flipped": fresh_flips,
        "raiding_warbands_used": revealed_by_raid,
        "intimidated_placed": False,
        "target_removed": [],
    }

    # Flip Germanic Warbands
    if fresh_flips:
        flip_piece(state, region, GERMANS, WARBAND,
                   count=fresh_flips,
                   from_state=HIDDEN, to_state=REVEALED)

    # Place Intimidated marker
    markers = state.setdefault("markers", {})
    region_markers = markers.get(region)
    if MARKER_INTIMIDATED not in (region_markers or {}):
        if isinstance(region_markers, set):
            region_markers.add(MARKER_INTIMIDATED)
        elif isinstance(region_markers, dict):
            region_markers[MARKER_INTIMIDATED] = True
        else:
            markers[region] = {MARKER_INTIMIDATED: True}
        result["intimidated_placed"] = True

    # Remove target pieces
    for piece_type, piece_state in target_removals:
        if piece_type == ALLY:
            remove_piece(state, region, target_faction, ALLY, 1)
            # Keep state["tribes"] in sync with the removed Ally.
            clear_allied_tribe(state, region, target_faction, ALLY)
        else:
            remove_piece(state, region, target_faction, piece_type, 1,
                         piece_state=piece_state)
        result["target_removed"].append((piece_type, 1))

    refresh_all_control(state)
    return result


