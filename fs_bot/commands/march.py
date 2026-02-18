"""March command — Mechanical execution of piece movement.

This module implements March for all factions (Roman, Gallic, Germanic)
in both base game and Ariovistus scenarios, plus Harassment resolution.

Functions are mechanical execution: given origins, groups, and destinations,
execute the movement. Bot target selection (which groups go where) is Phase 5.
Human input is Phase 6.

Reference: §3.2.2 (Roman March), §3.3.2 (Gallic March), §3.4.2 (Germanic March),
           §3.4.5 (Germanic Losses, Harassment, Agreement),
           §1.3.4 (Britannia), §1.3.5 (Rhenus), §2.3.5 (Limited Command),
           §2.3.8 (Frost), §3.1.2 (Free Actions), §6.2.2 (Germans Phase March),
           A3.2.2, A3.3.2, A3.4.2, A3.4.5
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    GALLIC_FACTIONS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    FLIPPABLE_PIECES,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Leaders
    CAESAR, VERCINGETORIX,
    # Scenarios
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    # Regions
    BRITANNIA, CISALPINA,
    GERMANIA_REGIONS,
    # Adjacency types
    ADJ_RHENUS, ADJ_COASTAL,
    # Costs
    ROMAN_MARCH_COST, GALLIC_MARCH_COST,
    GERMAN_COMMAND_COST_BASE,
    # Markers
    MARKER_DEVASTATED,
    # Battle / Harassment
    HARASSMENT_WARBANDS_PER_LOSS,
    LOSS_ROLL_THRESHOLD,
    DIE_SIDES, DIE_MIN, DIE_MAX,
    # Control
    FACTION_CONTROL,
)
from fs_bot.board.pieces import (
    move_piece, count_pieces, count_pieces_by_state,
    flip_piece, remove_piece, get_leader_in_region,
    PieceError,
)
from fs_bot.board.control import refresh_all_control
from fs_bot.map.map_data import (
    get_adjacent_with_type, get_adjacency_type,
    ALL_REGION_DATA,
)
from fs_bot.commands.common import CommandError, _is_devastated


class MarchError(CommandError):
    """Raised when a March operation violates game rules."""
    pass


# ============================================================================
# COST CALCULATIONS
# ============================================================================

def march_cost(state, region, faction):
    """Calculate the Resource cost for March from an origin region.

    §3.2.2: Romans pay 2 per origin, 4 if Devastated.
    §3.3.2: Gauls pay 1 per origin, 2 if Devastated.
    §3.4 (base): Germans pay 0.
    A3.4.2: Germans in Ariovistus March like Gauls (1 per origin, 2 Devastated).

    Args:
        state: Game state dict.
        region: Origin region.
        faction: Faction executing March.

    Returns:
        Integer Resource cost.
    """
    scenario = state["scenario"]

    if faction == GERMANS:
        if scenario in BASE_SCENARIOS:
            return GERMAN_COMMAND_COST_BASE
        # Ariovistus: Germans March like Gauls — A3.4.2
        # "The German Leader and Warbands March in the same way as Gallic
        # Leaders and Warbands do (3.3.2)"
        base = GALLIC_MARCH_COST
    elif faction == ROMANS:
        base = ROMAN_MARCH_COST
    else:
        # Gallic factions
        base = GALLIC_MARCH_COST

    # Double if Devastated — §3.2.2, §3.3.2
    if _is_devastated(state, region):
        return base * 2

    return base


# ============================================================================
# VALIDATION
# ============================================================================

def _is_region_playable(state, region):
    """Check if a region is playable in the current scenario."""
    region_data = ALL_REGION_DATA.get(region)
    if region_data is None:
        return False
    return region_data.is_playable(state["scenario"],
                                   state.get("capabilities"))


def _get_movable_piece_types(faction, scenario):
    """Get piece types that can March for a faction.

    §3.2.2: Roman groups may include Leader, Legions, Auxilia
            — NOT Allied Tribes nor Forts.
    §3.3.2: Gallic groups may include Leader and Warbands
            — NOT Allied Tribes nor Citadels.
    §3.4.2: Germanic groups: Warbands only (base game).
    A3.4.2: Germanic groups in Ariovistus: Leader and Warbands
            (like Gallic).

    Returns:
        Tuple of piece type constants.
    """
    if faction == ROMANS:
        return (LEADER, LEGION, AUXILIA)
    elif faction == GERMANS:
        if scenario in BASE_SCENARIOS:
            # §3.4.2: "Germanic Warbands within a March origin Region may
            # form at most a single moving Group"
            return (WARBAND,)
        else:
            # A3.4.2: "The German Leader and Warbands March in the same
            # way as Gallic Leaders and Warbands do"
            return (LEADER, WARBAND)
    else:
        # Gallic factions — §3.3.2
        return (LEADER, WARBAND)


def _check_crossing_stop(state, from_region, to_region, faction):
    """Check if crossing between two regions stops a group.

    Returns (stops, reason) tuple.
    Stops are:
    - Entering/exiting Britannia — §1.3.4
    - Crossing Rhenus (non-Germans) — §1.3.5, §3.4.2
    - Entering Devastated (not beginning in) — §3.2.2
    - Entering/exiting Cisalpina (Ariovistus) — A3.2.2

    Args:
        state: Game state dict.
        from_region: Source region.
        to_region: Destination region.
        faction: Faction marching.

    Returns:
        (stops: bool, reason: str or None)
    """
    scenario = state["scenario"]

    # Britannia — §1.3.4
    # "Upon moving into or out of Britannia... the group must stop"
    if from_region == BRITANNIA or to_region == BRITANNIA:
        # Check if Britannia is playable
        if _is_region_playable(state, BRITANNIA):
            return True, "Britannia crossing"

    # Rhenus — §1.3.5
    adj_type = get_adjacency_type(from_region, to_region)
    if adj_type == ADJ_RHENUS:
        if faction == GERMANS:
            # §3.4.5 / §3.4.2: Germans cross Rhenus freely
            # (no stop for Germans)
            pass
        else:
            return True, "Rhenus crossing"

    # Devastated — §3.2.2
    # "entering (as opposed to beginning in) a Devastated Region stops"
    if _is_devastated(state, to_region):
        return True, "Entering Devastated region"

    # Alps / Cisalpina — A3.2.2 (Ariovistus only)
    # "Upon Marching into or out of Cisalpina, a Roman group must stop"
    # A3.4.2: Germans March like Gauls; Cisalpina stop applies to all
    if scenario in ARIOVISTUS_SCENARIOS:
        if from_region == CISALPINA or to_region == CISALPINA:
            return True, "Alps crossing (Cisalpina)"

    return False, None


def _max_steps_for_group(state, origin, faction, group):
    """Determine the maximum number of movement steps for a group.

    §3.2.2: Roman groups move up to 2 regions.
             Caesar + accompanying pieces may move to a 3rd.
    §3.3.2: Gallic groups move 1 region only.
             Vercingetorix + Warbands may enter a 2nd — §3.3.2.
    §3.4.2 (base): Germanic groups move 1 region.
    A3.4.2: Germanic groups in Ariovistus move 1 region
            (like Gallic, no Vercingetorix bonus).

    Args:
        state: Game state dict.
        origin: Origin region.
        faction: Marching faction.
        group: Group dict with piece composition.

    Returns:
        Integer max steps (1, 2, or 3).
    """
    scenario = state["scenario"]

    if faction == ROMANS:
        # §3.2.2: Base 2 regions
        max_steps = 2
        # Caesar bonus: Caesar + Legions/Auxilia may move to 3rd
        if group.get(LEADER) is not None:
            leader_name = get_leader_in_region(state, origin, ROMANS)
            if leader_name == CAESAR:
                max_steps = 3
        return max_steps

    if faction in GALLIC_FACTIONS:
        # §3.3.2: Gallic groups move 1 region
        max_steps = 1
        # Vercingetorix bonus — §3.3.2
        # Only in base game (Vercingetorix doesn't exist in Ariovistus)
        if (faction == ARVERNI and scenario in BASE_SCENARIOS
                and group.get(LEADER) is not None):
            leader_name = get_leader_in_region(state, origin, ARVERNI)
            if leader_name == VERCINGETORIX:
                max_steps = 2
        return max_steps

    if faction == GERMANS:
        # §3.4.2 (base): 1 region
        # A3.4.2: "March in the same way as Gallic Leaders and Warbands do
        # (3.3.2; not into a 2nd Region—an effect particular to Vercingetorix)"
        return 1

    return 1


# ============================================================================
# FLIPPING (HIDE) AT ORIGIN
# ============================================================================

def _flip_origin_pieces(state, origin, faction):
    """Flip faction's Revealed pieces to Hidden at origin before movement.

    §3.2.2 (Roman): Flip all Revealed Auxilia to Hidden.
    §3.3.2 (Gallic): Flip all Revealed Warbands to Hidden;
        or for Scouted Warbands, remove Scouted marker and leave Revealed.
    §3.4.2 (Germanic): All Warbands flip to Hidden
        (or remove Scouted marker).

    Returns:
        Dict of flipping results: {"flipped_to_hidden": count,
                                   "scouted_to_revealed": count}
    """
    scenario = state["scenario"]
    result = {"flipped_to_hidden": 0, "scouted_to_revealed": 0}

    if faction == ROMANS:
        # §3.2.2: "flip all Revealed Auxilia to Hidden"
        revealed_auxilia = count_pieces_by_state(
            state, origin, ROMANS, AUXILIA, REVEALED)
        if revealed_auxilia > 0:
            flip_piece(state, origin, ROMANS, AUXILIA,
                       count=revealed_auxilia,
                       from_state=REVEALED, to_state=HIDDEN)
            result["flipped_to_hidden"] = revealed_auxilia

    elif faction in GALLIC_FACTIONS or (
            faction == GERMANS and scenario in ARIOVISTUS_SCENARIOS):
        # §3.3.2 / §3.4.2 / A3.4.2: Flip Revealed Warbands to Hidden;
        # For Scouted, remove marker (leave Revealed) — §4.2.2
        piece_type = WARBAND

        # IMPORTANT: Flip Revealed→Hidden FIRST, then handle Scouted.
        # §3.3.2: "flip all... Revealed Warbands there to Hidden; or,
        # for Scouted Warbands (4.2.2), instead remove the Scouted marker
        # and leave them Revealed"
        # If we did Scouted first, they'd become Revealed and then
        # get flipped to Hidden, violating "leave them Revealed".
        revealed = count_pieces_by_state(
            state, origin, faction, piece_type, REVEALED)
        if revealed > 0:
            flip_piece(state, origin, faction, piece_type,
                       count=revealed,
                       from_state=REVEALED, to_state=HIDDEN)
            result["flipped_to_hidden"] = revealed

        # Then handle Scouted — §3.3.2:
        # "for Scouted Warbands (4.2.2), instead remove the Scouted marker
        # and leave them Revealed"
        scouted = count_pieces_by_state(
            state, origin, faction, piece_type, SCOUTED)
        if scouted > 0:
            # flip_piece with from_state=SCOUTED, to_state=HIDDEN
            # automatically converts to REVEALED per §1.4.3 in flip_piece
            flip_piece(state, origin, faction, piece_type,
                       count=scouted,
                       from_state=SCOUTED, to_state=HIDDEN)
            result["scouted_to_revealed"] = scouted

    elif faction == GERMANS and scenario in BASE_SCENARIOS:
        # §3.4.2: "All Warbands in Regions selected for March flip to Hidden
        # (or remove their Scouted marker), whether or not they move."
        piece_type = WARBAND

        # Flip Revealed→Hidden first
        revealed = count_pieces_by_state(
            state, origin, GERMANS, piece_type, REVEALED)
        if revealed > 0:
            flip_piece(state, origin, GERMANS, piece_type,
                       count=revealed,
                       from_state=REVEALED, to_state=HIDDEN)
            result["flipped_to_hidden"] = revealed

        # Then handle Scouted → Revealed (remove marker, leave Revealed)
        scouted = count_pieces_by_state(
            state, origin, GERMANS, piece_type, SCOUTED)
        if scouted > 0:
            flip_piece(state, origin, GERMANS, piece_type,
                       count=scouted,
                       from_state=SCOUTED, to_state=HIDDEN)
            result["scouted_to_revealed"] = scouted

    return result


# ============================================================================
# HARASSMENT — §3.2.2, §3.3.2, §3.2.3, A3.2.2, A3.4.5
# ============================================================================

def resolve_harassment(state, region, marching_faction, departing_pieces,
                       *, harassing_factions=None):
    """Resolve Harassment against departing pieces in a region.

    Harassment is triggered when a group both enters and then leaves a region.
    Any Factions with enough Hidden Warbands may inflict Losses on the
    departing pieces.

    §3.2.2: For every 3 Hidden Warbands (rounded down), the marching faction
    must either remove one departing Auxilia/Warband OR — if any Legions or
    Leader remain with the group — may instead roll a die. On 1-3, remove
    the Legion or Leader.

    §3.4.5: Germans always Harass (base game).
    A3.4.5: Germanic player may opt to Harass (Ariovistus).
    A3.2.2: Arverni always opt to Harass (Ariovistus).

    This function handles the mechanical resolution. The decision of WHO
    harasses (bot/player choice) is provided via harassing_factions parameter.

    Args:
        state: Game state dict.
        region: Region where harassment occurs.
        marching_faction: Faction whose pieces are departing.
        departing_pieces: Dict describing pieces still in the group
            that are about to leave:
            {piece_type: count} for non-flippable,
            {piece_type: {piece_state: count}} for flippable.
            Or simpler: {LEADER: leader_name_or_None, LEGION: count,
                         AUXILIA: count, WARBAND: count}
        harassing_factions: List of (faction, num_hidden_warbands) tuples
            for each faction that opts to harass, in Faction Order.
            If None, auto-detect all factions with 3+ Hidden Warbands
            that always harass (Germans in base game, Arverni in Ariovistus).

    Returns:
        Dict with results:
            "harassment_occurred": bool
            "losses_by_faction": [{
                "faction": harassing faction,
                "hidden_warbands": count,
                "num_losses": int,
                "removals": [(piece_type, count, roll_or_None)],
            }]
            "total_pieces_removed": int
    """
    scenario = state["scenario"]
    result = {
        "harassment_occurred": False,
        "losses_by_faction": [],
        "total_pieces_removed": 0,
    }

    if harassing_factions is None:
        harassing_factions = _auto_detect_harassers(
            state, region, marching_faction)

    if not harassing_factions:
        return result

    result["harassment_occurred"] = True

    for harasser_faction, num_hidden_warbands in harassing_factions:
        # §3.2.2: "For every three Hidden Warbands that the Faction has there
        # (rounded down)"
        num_losses = num_hidden_warbands // HARASSMENT_WARBANDS_PER_LOSS

        if num_losses == 0:
            continue

        faction_result = {
            "faction": harasser_faction,
            "hidden_warbands": num_hidden_warbands,
            "num_losses": num_losses,
            "removals": [],
        }

        for _ in range(num_losses):
            removal = _resolve_one_harassment_loss(
                state, region, marching_faction, departing_pieces)
            if removal is not None:
                faction_result["removals"].append(removal)
                result["total_pieces_removed"] += removal[1]

        result["losses_by_faction"].append(faction_result)

    return result


def _auto_detect_harassers(state, region, marching_faction):
    """Auto-detect factions that will harass in a region.

    §3.4.5 (base): Germans always Harass.
    A3.4.5: Germanic player may opt (not auto).
    A3.2.2: Arverni always opt to Harass in Ariovistus.
    All others: player choice (not auto-detected here).

    Returns:
        List of (faction, num_hidden_warbands) tuples.
    """
    scenario = state["scenario"]
    harassers = []

    from fs_bot.rules_consts import FACTIONS
    for faction in FACTIONS:
        if faction == marching_faction:
            continue
        hidden_wb = count_pieces_by_state(
            state, region, faction, WARBAND, HIDDEN)
        if hidden_wb < HARASSMENT_WARBANDS_PER_LOSS:
            continue

        # Determine if faction auto-harasses
        if faction == GERMANS and scenario in BASE_SCENARIOS:
            # §3.4.5: "Germans always Harass"
            harassers.append((faction, hidden_wb))
        elif faction == ARVERNI and scenario in ARIOVISTUS_SCENARIOS:
            # A3.2.2: "Arverni always opt to do so"
            harassers.append((faction, hidden_wb))
        # Other factions: player/bot decides — not auto-detected

    return harassers


def _resolve_one_harassment_loss(state, region, marching_faction,
                                 departing_pieces):
    """Resolve one Harassment loss against the departing group.

    §3.2.2: "the Romans must either remove one departing Auxilia or—if any
    Legions or Leader remain with the group—may instead roll a die. If the
    roll is a 1, 2, or 3 (only), the Romans must remove the Legion or Leader."

    This same mechanism applies to all factions per §3.3.2 Vercingetorix and
    §3.2.3 Seize Harassment.

    For the mechanical execution, the loss priority is:
    - Remove a soft target (Auxilia for Romans, Warband for Gauls) from
      the departing group.
    - If no soft targets remain and a hard target (Legion/Leader) is present,
      roll for it.

    Args:
        state: Game state dict.
        region: Region of harassment.
        marching_faction: Faction taking the loss.
        departing_pieces: Mutable dict of pieces still in the group.

    Returns:
        Tuple of (piece_type, count_removed, die_roll_or_None),
        or None if no pieces to remove.
    """
    # Determine soft target type for the marching faction
    if marching_faction == ROMANS:
        soft_target = AUXILIA
    else:
        soft_target = WARBAND

    # Check if we can remove a soft target from the departing group
    soft_count = departing_pieces.get(soft_target, 0)
    if soft_count > 0:
        departing_pieces[soft_target] = soft_count - 1
        # Actually remove from the region (the piece is still there
        # since it hasn't moved yet — it's "departing")
        # The piece removal happens in the region it's departing FROM,
        # which is the harassment region.
        remove_piece(state, region, marching_faction, soft_target, 1)
        return (soft_target, 1, None)

    # No soft targets — check for hard targets (Leader, Legion)
    has_legion = departing_pieces.get(LEGION, 0) > 0
    has_leader = departing_pieces.get(LEADER) is not None

    if has_legion or has_leader:
        # Roll for the hard target
        roll = state["rng"].randint(DIE_MIN, DIE_MAX)
        if roll <= LOSS_ROLL_THRESHOLD:
            # Remove: prefer Legion over Leader
            if has_legion:
                departing_pieces[LEGION] = departing_pieces[LEGION] - 1
                remove_piece(state, region, marching_faction, LEGION, 1,
                             to_fallen=True)
                return (LEGION, 1, roll)
            elif has_leader:
                departing_pieces[LEADER] = None
                remove_piece(state, region, marching_faction, LEADER, 1)
                return (LEADER, 1, roll)
        else:
            # Survived — loss absorbed without removing
            return (LEADER if has_leader and not has_legion else LEGION,
                    0, roll)

    # No pieces left to take losses
    return None


# ============================================================================
# MARCH EXECUTION — SINGLE GROUP
# ============================================================================

def march_group(state, faction, origin, destinations, group, *,
                free=False):
    """Execute a March for a single group from origin through destinations.

    This moves the specified pieces step by step. It checks crossing stops
    and halts when required. It does NOT handle Harassment — the caller
    must check for and invoke resolve_harassment() when a group passes
    through a region (enters and then leaves).

    Args:
        state: Game state dict. Modified in place.
        faction: Faction executing March.
        origin: Origin region name.
        destinations: List of destination region names in order.
            May be shorter than max steps. Stops when a crossing stop
            is encountered.
        group: Dict describing the pieces in this group:
            {LEADER: leader_name_or_None,
             LEGION: count,
             AUXILIA: count,
             WARBAND: count}
            The pieces must exist in the origin region.
        free: If True, no Resource cost (Event-granted).

    Returns:
        Dict with results:
            "faction": faction
            "origin": origin region
            "final_region": where the group ended up
            "path": list of regions traversed (origin + moved-to regions)
            "stopped_reason": reason the group stopped, or None
            "pieces_moved": {piece_type: count}
            "regions_passed_through": list of regions entered then left
                (for Harassment checking)

    Raises:
        MarchError: If the March violates rules.
    """
    scenario = state["scenario"]

    # Validate the group has only movable piece types
    movable_types = _get_movable_piece_types(faction, scenario)
    for piece_type, count in _iter_group_pieces(group):
        if count <= 0:
            continue
        if piece_type not in movable_types:
            raise MarchError(
                f"{piece_type} cannot March for {faction} (§3.2.2/§3.3.2)")

    # Validate pieces exist in origin
    _validate_group_in_region(state, origin, faction, group)

    result = {
        "faction": faction,
        "origin": origin,
        "final_region": origin,
        "path": [origin],
        "stopped_reason": None,
        "pieces_moved": {},
        "regions_passed_through": [],
    }

    current_region = origin

    for step_index, dest in enumerate(destinations):
        # If this is not the first step, the current region was entered
        # on a prior step and is now being left — it was passed through.
        # The origin is never passed through (the group started there).
        if step_index > 0:
            result["regions_passed_through"].append(current_region)

        # Check adjacency
        adj_type = get_adjacency_type(current_region, dest)
        if adj_type is None:
            raise MarchError(
                f"{dest} is not adjacent to {current_region}")

        # Check destination is playable
        if not _is_region_playable(state, dest):
            raise MarchError(
                f"{dest} is not playable in scenario {scenario}")

        # Check crossing stop
        stops, reason = _check_crossing_stop(
            state, current_region, dest, faction)

        # Move the group
        _move_group_to(state, current_region, dest, faction, group)
        prev_region = current_region
        current_region = dest
        result["path"].append(current_region)

        if stops:
            result["stopped_reason"] = reason
            result["final_region"] = current_region
            break

        result["final_region"] = current_region

    # Track pieces moved
    for piece_type, count in _iter_group_pieces(group):
        if count > 0:
            result["pieces_moved"][piece_type] = count
    if group.get(LEADER) is not None:
        result["pieces_moved"][LEADER] = 1

    return result


def _iter_group_pieces(group):
    """Iterate over (piece_type, count) pairs in a group dict.

    The group dict has:
        LEADER: leader_name or None (treated as 0/1)
        LEGION: count
        AUXILIA: count
        WARBAND: count
    """
    yield LEGION, group.get(LEGION, 0)
    yield AUXILIA, group.get(AUXILIA, 0)
    yield WARBAND, group.get(WARBAND, 0)


def _validate_group_in_region(state, region, faction, group):
    """Validate that all pieces in a group exist in the region."""
    if group.get(LEADER) is not None:
        leader_name = get_leader_in_region(state, region, faction)
        if leader_name is None:
            raise MarchError(f"No {faction} Leader in {region}")

    for piece_type, count in _iter_group_pieces(group):
        if count <= 0:
            continue
        actual = count_pieces(state, region, faction, piece_type)
        if actual < count:
            raise MarchError(
                f"Only {actual} {faction} {piece_type} in {region}, "
                f"need {count}")


def _move_group_to(state, from_region, to_region, faction, group):
    """Move all pieces in a group from one region to another.

    Flippable pieces are moved in their current state (Hidden stays Hidden,
    etc.). This preserves their flip state as set by the origin flipping.
    """
    # Move Leader
    if group.get(LEADER) is not None:
        move_piece(state, from_region, to_region, faction, LEADER)

    # Move Legions
    legion_count = group.get(LEGION, 0)
    if legion_count > 0:
        move_piece(state, from_region, to_region, faction, LEGION,
                   count=legion_count)

    # Move Auxilia (Hidden — they were flipped at origin)
    auxilia_count = group.get(AUXILIA, 0)
    if auxilia_count > 0:
        move_piece(state, from_region, to_region, faction, AUXILIA,
                   count=auxilia_count, piece_state=HIDDEN)

    # Move Warbands (Hidden — they were flipped at origin)
    warband_count = group.get(WARBAND, 0)
    if warband_count > 0:
        move_piece(state, from_region, to_region, faction, WARBAND,
                   count=warband_count, piece_state=HIDDEN)


# ============================================================================
# DROP OFF — §3.2.2
# ============================================================================

def drop_off_pieces(state, region, faction, pieces_to_drop):
    """Drop off pieces from a marching group in the current region.

    §3.2.2: "Any of a group's pieces may drop off in a Region before
    the rest move on."

    Args:
        state: Game state dict.
        region: Region where pieces are dropping off.
        faction: Marching faction.
        pieces_to_drop: Dict of {piece_type: count} to drop off.
            Pieces stay in the region; they are removed from the group.

    Returns:
        Dict of pieces dropped: {piece_type: count}.
    """
    # Validate the pieces are in the region
    for piece_type, count in pieces_to_drop.items():
        if count <= 0:
            continue
        if piece_type == LEADER:
            if get_leader_in_region(state, region, faction) is None:
                raise MarchError(
                    f"No {faction} Leader in {region} to drop off")
        else:
            actual = count_pieces(state, region, faction, piece_type)
            if actual < count:
                raise MarchError(
                    f"Only {actual} {faction} {piece_type} in {region}, "
                    f"cannot drop off {count}")

    # Pieces already ARE in the region (they were moved there).
    # "Dropping off" means they stay — no physical move needed.
    # The caller must adjust the group dict to remove dropped pieces.
    return dict(pieces_to_drop)


# ============================================================================
# MARCH FROM ORIGIN — FULL PROCEDURE
# ============================================================================

def march_from_origin(state, faction, origin, groups_and_destinations, *,
                      free=False):
    """Execute March from a single origin region with one or more groups.

    This is the per-origin procedure:
    1. Flip Revealed pieces to Hidden at origin — §3.2.2, §3.3.2
    2. Move each group one by one — §3.2.2, §3.3.2

    The caller handles cost payment and multi-origin coordination.

    Args:
        state: Game state dict. Modified in place.
        faction: Faction executing March.
        origin: Origin region name.
        groups_and_destinations: List of (group_dict, destinations_list) tuples.
            Each group_dict: {LEADER: name_or_None, LEGION: n, AUXILIA: n,
                              WARBAND: n}
            Each destinations_list: [region1, region2, ...] — the intended
                path. May be truncated by crossing stops.
        free: If True, Event-granted free March.

    Returns:
        Dict with results:
            "origin": origin region
            "flip_result": result from flipping at origin
            "group_results": [march_group result dicts]
    """
    # Step 1: Flip Revealed pieces at origin — §3.2.2, §3.3.2, §3.4.2
    flip_result = _flip_origin_pieces(state, origin, faction)

    # Step 2: Move each group
    group_results = []
    for group, destinations in groups_and_destinations:
        grp_result = march_group(state, faction, origin, destinations, group,
                                 free=free)
        group_results.append(grp_result)

    return {
        "origin": origin,
        "flip_result": flip_result,
        "group_results": group_results,
    }


# ============================================================================
# FULL MARCH COMMAND
# ============================================================================

def execute_march(state, faction, origins_data, *, free=False, limited=False):
    """Execute a full March command across one or more origin regions.

    Handles cost payment, origin iteration, and control refresh.

    Args:
        state: Game state dict. Modified in place.
        faction: Faction executing March.
        origins_data: List of dicts, one per origin region:
            [{"origin": region_name,
              "groups": [(group_dict, destinations_list), ...]}]
        free: If True, no Resource cost and no Eligibility change — §3.1.2.
        limited: If True, Limited Command — one origin only — §2.3.5.

    Returns:
        Dict with results:
            "faction": faction
            "origins": [per-origin result dicts]
            "total_cost": total Resources spent
            "limited": bool

    Raises:
        MarchError: If the command violates rules.
    """
    scenario = state["scenario"]

    # Limited Command validation — §2.3.5
    if limited and len(origins_data) > 1:
        raise MarchError(
            "Limited Command: March may select only one origin Region (§2.3.5)")

    result = {
        "faction": faction,
        "origins": [],
        "total_cost": 0,
        "limited": limited,
    }

    for origin_entry in origins_data:
        origin = origin_entry["origin"]
        groups = origin_entry["groups"]

        # Calculate and pay cost
        cost = 0 if free else march_cost(state, origin, faction)

        if not free and cost > 0:
            current_resources = state["resources"].get(faction, 0)
            if current_resources < cost:
                raise MarchError(
                    f"{faction} has {current_resources} Resources, "
                    f"need {cost} to March from {origin}")
            state["resources"][faction] -= cost

        result["total_cost"] += cost

        # Execute march from this origin
        origin_result = march_from_origin(
            state, faction, origin, groups, free=free)
        origin_result["cost"] = cost
        result["origins"].append(origin_result)

    # Refresh control after all movement
    refresh_all_control(state)

    return result


# ============================================================================
# GERMANS PHASE MARCH (§6.2.2) — Base Game Only
# ============================================================================

def germans_phase_march(state):
    """Execute the Germans Phase March procedure — §6.2.2.

    This is the base-game-only deterministic March for the Germanic
    non-player faction during Winter. It uses state["rng"] for random
    choices among equal candidates.

    §6.2.2:
    - Form a group of Germanic Warbands to March out of each Region that
      has at least one Germanic Warband beyond pieces needed for Control.
    - March out with as many as possible without losing Germanic Control.
    - Move the largest groups first.
    - Move into at most one Region with each group.
    - Select destinations: first add Germanic Control (not yet controlled),
      then player-controlled Factions, then others.
    - Choose among equal candidates randomly.
    - Flip all Germanic Warbands to Hidden (or remove Scouted markers).

    Args:
        state: Game state dict. Modified in place.

    Returns:
        Dict with results:
            "groups_moved": [(from_region, to_region, warband_count)]
            "flipped_regions": [region_names]
    """
    scenario = state["scenario"]
    if scenario not in BASE_SCENARIOS:
        raise MarchError("Germans Phase March is base game only (§6.2.2)")

    rng = state["rng"]
    result = {
        "groups_moved": [],
        "flipped_regions": [],
    }

    # Collect regions with German Warbands that can send groups out
    # §6.2.2: "each Region that has at least one Germanic Warband
    # beyond the pieces needed for Germanic Control"
    candidate_origins = []
    for region in state["spaces"]:
        region_data = ALL_REGION_DATA.get(region)
        if region_data is None:
            continue
        if not region_data.is_playable(scenario, state.get("capabilities")):
            continue

        german_warbands = count_pieces(state, region, GERMANS, WARBAND)
        if german_warbands == 0:
            continue

        # Calculate how many Warbands are needed to maintain Control
        # Control = faction's forces > all others combined — §1.6
        german_total = count_pieces(state, region, GERMANS)
        other_total = 0
        from fs_bot.rules_consts import FACTIONS
        for fac in FACTIONS:
            if fac != GERMANS:
                other_total += count_pieces(state, region, fac)

        # Currently controlling: german_total > other_total
        # To maintain control after removing warbands:
        # (german_total - sent) > other_total
        # => sent < german_total - other_total
        # Also: must have at least 1 warband beyond control need
        if german_total <= other_total:
            # No Germanic Control — don't march — §6.2.2 NOTE
            continue

        surplus = german_total - other_total - 1
        # surplus = max Warbands we can send while keeping control
        can_send = min(german_warbands, surplus)
        if can_send <= 0:
            continue

        candidate_origins.append((region, can_send))

    # Sort by largest groups first — §6.2.2
    candidate_origins.sort(key=lambda x: x[1], reverse=True)

    # Move each group to a destination
    for from_region, warband_count in candidate_origins:
        # Find candidate destinations
        adj = get_adjacent_with_type(
            from_region, scenario, state.get("capabilities"))

        # Priority: add Germanic Control > player-controlled > others
        # §6.2.2: "not yet German-Controlled", "Controlled by player Factions
        # (not Non-players)"
        add_control = []
        player_controlled = []
        others = []

        for dest, adj_type in adj.items():
            # Germans cross Rhenus freely — §3.4.5
            # But check other stops (Devastated, Britannia, etc.)
            # For Germans Phase, the rules say "March into at most one
            # Region with each group (3.3.2, 3.4.2)" — 1 step
            dest_data = ALL_REGION_DATA.get(dest)
            if dest_data is None or not dest_data.is_playable(
                    scenario, state.get("capabilities")):
                continue

            from fs_bot.board.control import is_controlled_by
            is_german_controlled = is_controlled_by(state, dest, GERMANS)

            if not is_german_controlled:
                # Could add Germanic Control?
                # Check if the Warbands would give control
                german_in_dest = count_pieces(state, dest, GERMANS)
                others_in_dest = 0
                for fac in FACTIONS:
                    if fac != GERMANS:
                        others_in_dest += count_pieces(state, dest, fac)
                would_control = (german_in_dest + warband_count
                                 > others_in_dest)
                if would_control:
                    add_control.append(dest)
                else:
                    # Check if destination is player-controlled
                    # Non-player factions check would be in Phase 8;
                    # for now, treat all factions as potential player factions
                    is_any_controlled = False
                    for fac in FACTIONS:
                        if fac != GERMANS and is_controlled_by(
                                state, dest, fac):
                            is_any_controlled = True
                            break
                    if is_any_controlled:
                        player_controlled.append(dest)
                    else:
                        others.append(dest)
            else:
                others.append(dest)

        # Choose destination in priority order, randomly among equals
        dest = None
        for candidate_list in [add_control, player_controlled, others]:
            if candidate_list:
                rng.shuffle(candidate_list)
                dest = candidate_list[0]
                break

        if dest is None:
            continue

        # Execute the march: move Warbands
        # Re-validate warbands available (may have changed from prior moves)
        current_warbands = count_pieces(state, from_region, GERMANS, WARBAND)
        german_total = count_pieces(state, from_region, GERMANS)
        other_total = 0
        for fac in FACTIONS:
            if fac != GERMANS:
                other_total += count_pieces(state, from_region, fac)
        surplus = german_total - other_total - 1
        actual_send = min(current_warbands, surplus)
        if actual_send <= 0:
            continue

        # Move all Warbands (Hidden — they'll be flipped after all movement)
        # move_piece needs a piece_state for flippable pieces
        # Move Hidden first, then Revealed, then Scouted
        sent = 0
        for ps in (HIDDEN, REVEALED, SCOUTED):
            ps_count = count_pieces_by_state(
                state, from_region, GERMANS, WARBAND, ps)
            to_move = min(ps_count, actual_send - sent)
            if to_move > 0:
                move_piece(state, from_region, dest, GERMANS, WARBAND,
                           count=to_move, piece_state=ps)
                sent += to_move
            if sent >= actual_send:
                break

        result["groups_moved"].append((from_region, dest, sent))

    # §6.2.2: "Flip all Germanic Warbands to Hidden (or remove their Scouted
    # markers). (Warbands that did not move in effect Marched within their
    # Regions.)"
    for region in state["spaces"]:
        region_data = ALL_REGION_DATA.get(region)
        if region_data is None:
            continue
        if not region_data.is_playable(scenario, state.get("capabilities")):
            continue

        flipped = False
        # Scouted -> Revealed (remove marker per §1.4.3)
        scouted = count_pieces_by_state(
            state, region, GERMANS, WARBAND, SCOUTED)
        if scouted > 0:
            flip_piece(state, region, GERMANS, WARBAND,
                       count=scouted,
                       from_state=SCOUTED, to_state=HIDDEN)
            flipped = True

        # Revealed -> Hidden
        revealed = count_pieces_by_state(
            state, region, GERMANS, WARBAND, REVEALED)
        if revealed > 0:
            flip_piece(state, region, GERMANS, WARBAND,
                       count=revealed,
                       from_state=REVEALED, to_state=HIDDEN)
            flipped = True

        if flipped:
            result["flipped_regions"].append(region)

    # Refresh control
    refresh_all_control(state)

    return result
