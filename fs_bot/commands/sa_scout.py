"""
Scout Special Ability — §4.2.2 (Roman).

Scout may accompany any type of Command. No Britannia (§4.1.3).

Two capabilities:
1. Scout Movement: Move Auxilia from any Regions to adjacent Regions
   (even if no Leader nearby). Revealed stay Revealed, Hidden stay Hidden.
   No piece may move more than once. Cannot move into or out of Britannia.

2. Scout Reveal: In Regions within one of Caesar or with Successor —
   each Hidden Auxilia may flip to Revealed to Reveal up to two Warbands
   in that Region, placing Scouted markers on them.

Reference: §4.2.2, §4.1.2, §4.1.3, A4.2
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS,
    # Piece types
    AUXILIA, WARBAND, FLIPPABLE_PIECES,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Leaders
    CAESAR,
    # Regions
    BRITANNIA,
    # Scenarios
    ARIOVISTUS_SCENARIOS,
    # Markers
    MARKER_SCOUTED,
)
from fs_bot.board.pieces import (
    count_pieces_by_state,
    move_piece, flip_piece,
)
from fs_bot.map.map_data import is_adjacent, get_adjacent
from fs_bot.commands.common import CommandError, check_leader_proximity


def scout_move(state, movements):
    """Execute Scout movement — move Auxilia to adjacent Regions.

    §4.2.2: "Move Auxilia as desired from any Regions to adjacent Regions,
    but not into or out of Britannia (Revealed stay Revealed, Hidden stay
    Hidden; no piece may move more than once)."

    No Leader proximity requirement for Scout movement.

    Args:
        state: Game state dict. Modified in place.
        movements: List of dicts, each with:
            "from_region": Source region.
            "to_region": Destination region.
            "count": Number of Auxilia to move.
            "piece_state": HIDDEN or REVEALED.

    Returns:
        dict with:
            "moved": List of (from_region, to_region, count, piece_state).

    Raises:
        CommandError: If movement violates rules.
    """
    result = {"moved": []}
    total_moved = 0

    for move in movements:
        from_region = move["from_region"]
        to_region = move["to_region"]
        count = move["count"]
        piece_state = move["piece_state"]

        # §4.1.3: "No Special Ability may accompany March into or out of
        # Britannia"
        if from_region == BRITANNIA or to_region == BRITANNIA:
            raise CommandError(
                "Scout movement cannot move into or out of Britannia (§4.1.3)"
            )

        # Must be adjacent
        if not is_adjacent(from_region, to_region):
            raise CommandError(
                f"{from_region} and {to_region} are not adjacent"
            )

        # Must have Auxilia in the from_region
        available = count_pieces_by_state(
            state, from_region, ROMANS, AUXILIA, piece_state
        )
        if available < count:
            raise CommandError(
                f"Only {available} {piece_state} Auxilia in {from_region}, "
                f"need {count}"
            )

        # Execute movement — pieces keep their state
        move_piece(state, from_region, to_region, ROMANS, AUXILIA,
                   count=count, piece_state=piece_state)

        result["moved"].append((from_region, to_region, count, piece_state))
        total_moved += count

    return result


def scout_reveal(state, region, auxilia_count, targets):
    """Execute Scout reveal — flip Auxilia to Revealed to Reveal Warbands.

    §4.2.2: "each Hidden Auxilia piece may flip to Revealed in order to
    Reveal up to two Warbands (flip from Hidden to Revealed, or leave
    Revealed, 1.4.3) in that Region and place Scouted markers on them"

    Requires region within one of Caesar or with Successor.

    Args:
        state: Game state dict. Modified in place.
        region: Region where Scout Reveal occurs.
        auxilia_count: Number of Hidden Auxilia to flip to Revealed.
        targets: List of dicts, each with:
            "faction": Faction whose Warbands to reveal.
            "count": Number of Warbands to reveal (max 2 per Auxilia
                flipped).

    Returns:
        dict with:
            "auxilia_flipped": Number of Auxilia flipped.
            "warbands_revealed": List of (faction, count) revealed.
            "scouted_placed": List of (faction, count) Scouted markers.

    Raises:
        CommandError: If reveal violates rules.
    """
    scenario = state["scenario"]

    # Check Leader proximity — within 1 of Caesar or with Successor
    valid, reason = check_leader_proximity(
        state, region, ROMANS, CAESAR, "Scout Reveal"
    )
    if not valid:
        raise CommandError(reason)

    # Check Hidden Auxilia available
    hidden_auxilia = count_pieces_by_state(
        state, region, ROMANS, AUXILIA, HIDDEN
    )
    if hidden_auxilia < auxilia_count:
        raise CommandError(
            f"Only {hidden_auxilia} Hidden Auxilia in {region}, "
            f"need {auxilia_count}"
        )

    # Total Warbands to reveal: max 2 per Auxilia flipped — §4.2.2
    max_reveals = auxilia_count * 2
    total_targets = sum(t["count"] for t in targets)
    if total_targets > max_reveals:
        raise CommandError(
            f"Can only reveal up to {max_reveals} Warbands with "
            f"{auxilia_count} Auxilia (2 per Auxilia), but {total_targets} "
            f"requested"
        )

    result = {
        "auxilia_flipped": auxilia_count,
        "warbands_revealed": [],
        "scouted_placed": [],
    }

    # Flip Auxilia from Hidden to Revealed
    flip_piece(state, region, ROMANS, AUXILIA,
               count=auxilia_count,
               from_state=HIDDEN, to_state=REVEALED)

    # Reveal target Warbands and place Scouted markers
    for target in targets:
        target_faction = target["faction"]
        target_count = target["count"]

        if target_faction == ROMANS:
            raise CommandError("Cannot Scout-reveal Roman pieces")

        # Check Hidden Warbands available for this faction
        hidden_warbands = count_pieces_by_state(
            state, region, target_faction, WARBAND, HIDDEN
        )
        # Also count Revealed (already revealed stay Revealed but get Scouted)
        revealed_warbands = count_pieces_by_state(
            state, region, target_faction, WARBAND, REVEALED
        )

        # §4.2.2: "Reveal up to two Warbands (flip from Hidden to Revealed,
        # or leave Revealed, 1.4.3) in that Region and place Scouted markers
        # on them (if none already)."
        # Warbands already Scouted don't get re-scouted.
        scouted_warbands = count_pieces_by_state(
            state, region, target_faction, WARBAND, SCOUTED
        )

        # Flip Hidden Warbands to Scouted (Revealed + Scouted marker)
        hidden_to_flip = min(target_count, hidden_warbands)
        remaining = target_count - hidden_to_flip

        if hidden_to_flip > 0:
            # Flip Hidden → Scouted (which is Revealed + Scouted marker)
            flip_piece(state, region, target_faction, WARBAND,
                       count=hidden_to_flip,
                       from_state=HIDDEN, to_state=SCOUTED)
            result["scouted_placed"].append(
                (target_faction, hidden_to_flip)
            )

        # Revealed Warbands → Scouted (place Scouted marker)
        if remaining > 0:
            revealed_to_scout = min(remaining, revealed_warbands)
            if revealed_to_scout > 0:
                flip_piece(state, region, target_faction, WARBAND,
                           count=revealed_to_scout,
                           from_state=REVEALED, to_state=SCOUTED)
                result["scouted_placed"].append(
                    (target_faction, revealed_to_scout)
                )
            remaining -= revealed_to_scout

        result["warbands_revealed"].append(
            (target_faction, target_count - remaining)
        )

    return result


