"""
Piece operations module — The ONLY way pieces change in the game state.

All piece operations go through this module. Functions enforce caps from
rules_consts.py, update Available pools, and maintain state integrity.
Never manipulate piece counts in space dictionaries directly.

Reference: §1.4, §1.4.1, §1.4.2, §1.4.3, A1.4
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    PIECE_TYPES, FLIPPABLE_PIECES, MOBILE_PIECES,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Caps
    CAPS_BASE, CAPS_ARIOVISTUS,
    # Scenarios
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    # Leaders
    CAESAR, VERCINGETORIX, AMBIORIX, ARIOVISTUS_LEADER,
    DIVICIACUS, BODUOGNATUS, SUCCESSOR,
    BASE_LEADERS, ARIOVISTUS_LEADERS,
    LEADER_FACTION,
    # Stacking
    MAX_FORTS_PER_REGION, MAX_SETTLEMENTS_PER_REGION,
    # Special
    PROVINCIA, PROVINCIA_PERMANENT_FORT,
    LEGIONS_TRACK, FALLEN_LEGIONS,
    LEGIONS_ROW_BOTTOM, LEGIONS_ROW_MIDDLE, LEGIONS_ROW_TOP,
    LEGIONS_ROWS, LEGIONS_PER_ROW,
    # Tribe stacking
    TRIBE_FACTION_RESTRICTION,
)


class PieceError(Exception):
    """Raised when a piece operation violates game rules."""
    pass


def _get_caps(state):
    """Get the piece caps dict for the current scenario."""
    if state["scenario"] in ARIOVISTUS_SCENARIOS:
        return CAPS_ARIOVISTUS
    return CAPS_BASE


def _get_faction_cap(state, faction, piece_type):
    """Get the cap for a specific faction/piece_type in the current scenario."""
    caps = _get_caps(state)
    faction_caps = caps.get(faction, {})
    return faction_caps.get(piece_type, 0)


def _count_on_map(state, faction, piece_type):
    """Count how many of a piece type a faction has on the map."""
    total = 0
    for region, space in state["spaces"].items():
        pieces = space.get("pieces", {}).get(faction, {})
        if piece_type == LEADER:
            if pieces.get(LEADER) is not None:
                total += 1
        elif piece_type in FLIPPABLE_PIECES:
            total += pieces.get(HIDDEN, {}).get(piece_type, 0)
            total += pieces.get(REVEALED, {}).get(piece_type, 0)
            total += pieces.get(SCOUTED, {}).get(piece_type, 0)
        else:
            total += pieces.get(piece_type, 0)
    return total


def count_on_map(state, faction, piece_type):
    """Count how many of a piece type a faction has on the map (public API).

    Args:
        state: Game state dict.
        faction: Faction constant.
        piece_type: Piece type constant.

    Returns:
        Integer count.
    """
    return _count_on_map(state, faction, piece_type)


def _count_on_legions_track(state):
    """Count total Legions on the Legions track."""
    total = 0
    for row in LEGIONS_ROWS:
        total += state["legions_track"].get(row, 0)
    return total


def _total_legions_accounted(state):
    """Count all Legions everywhere (map + track + fallen + removed)."""
    on_map = _count_on_map(state, ROMANS, LEGION)
    on_track = _count_on_legions_track(state)
    fallen = state.get("fallen_legions", 0)
    removed = state.get("removed_legions", 0)
    return on_map + on_track + fallen + removed


def get_available(state, faction, piece_type):
    """Get the count of available pieces for a faction/type.

    Args:
        state: Game state dict.
        faction: Faction constant.
        piece_type: Piece type constant.

    Returns:
        Integer count of available pieces.
    """
    if piece_type == LEGION:
        # Legions are NOT on Available — they use the Legions track
        # Available Legions = on track, placeable via Senate Phase
        return _count_on_legions_track(state)
    return state["available"].get(faction, {}).get(piece_type, 0)


def _set_available(state, faction, piece_type, count):
    """Set the available count for a faction/piece_type."""
    if piece_type == LEGION:
        raise PieceError("Legions use the Legions track, not Available")
    state["available"].setdefault(faction, {})[piece_type] = count


def _validate_piece_exists_in_scenario(state, faction, piece_type):
    """Validate that a piece type exists for a faction in this scenario."""
    cap = _get_faction_cap(state, faction, piece_type)
    if cap == 0 and piece_type != LEADER:
        raise PieceError(
            f"{faction} cannot have {piece_type} in scenario "
            f"{state['scenario']}"
        )
    # Special leader validation
    if piece_type == LEADER:
        if cap == 0:
            raise PieceError(
                f"{faction} has no Leader in scenario {state['scenario']}"
            )


def _get_piece_count_in_region(state, region, faction, piece_type):
    """Get count of a specific piece type for a faction in a region."""
    space = state["spaces"].get(region, {})
    pieces = space.get("pieces", {}).get(faction, {})

    if piece_type == LEADER:
        return 1 if pieces.get(LEADER) is not None else 0
    elif piece_type in FLIPPABLE_PIECES:
        return (pieces.get(HIDDEN, {}).get(piece_type, 0) +
                pieces.get(REVEALED, {}).get(piece_type, 0) +
                pieces.get(SCOUTED, {}).get(piece_type, 0))
    else:
        return pieces.get(piece_type, 0)


def count_pieces(state, region, faction=None, piece_type=None):
    """Count pieces in a region, optionally filtered by faction/type.

    Args:
        state: Game state dict.
        region: Region name constant.
        faction: Optional faction to filter by.
        piece_type: Optional piece type to filter by.

    Returns:
        Integer count.
    """
    space = state["spaces"].get(region, {})
    total = 0

    factions_to_check = [faction] if faction else list(space.get("pieces", {}).keys())

    for f in factions_to_check:
        f_pieces = space.get("pieces", {}).get(f, {})
        if piece_type:
            if piece_type == LEADER:
                if f_pieces.get(LEADER) is not None:
                    total += 1
            elif piece_type in FLIPPABLE_PIECES:
                total += f_pieces.get(HIDDEN, {}).get(piece_type, 0)
                total += f_pieces.get(REVEALED, {}).get(piece_type, 0)
                total += f_pieces.get(SCOUTED, {}).get(piece_type, 0)
            else:
                total += f_pieces.get(piece_type, 0)
        else:
            # Count all piece types for this faction
            # Leader
            if f_pieces.get(LEADER) is not None:
                total += 1
            # Non-flippable static/other pieces
            for pt in (LEGION, FORT, ALLY, CITADEL, SETTLEMENT):
                total += f_pieces.get(pt, 0)
            # Flippable pieces (Auxilia, Warband) in all states
            for pt in FLIPPABLE_PIECES:
                total += f_pieces.get(HIDDEN, {}).get(pt, 0)
                total += f_pieces.get(REVEALED, {}).get(pt, 0)
                total += f_pieces.get(SCOUTED, {}).get(pt, 0)

    return total


def count_pieces_by_state(state, region, faction, piece_type, piece_state):
    """Count pieces of a specific state (Hidden/Revealed/Scouted).

    Args:
        state: Game state dict.
        region: Region name constant.
        faction: Faction constant.
        piece_type: Piece type constant (must be in FLIPPABLE_PIECES).
        piece_state: HIDDEN, REVEALED, or SCOUTED.

    Returns:
        Integer count.
    """
    if piece_type not in FLIPPABLE_PIECES:
        raise PieceError(f"{piece_type} is not flippable")
    space = state["spaces"].get(region, {})
    return space.get("pieces", {}).get(faction, {}).get(
        piece_state, {}
    ).get(piece_type, 0)


def _ensure_faction_pieces_structure(state, region, faction):
    """Ensure the pieces structure exists for a faction in a region."""
    state["spaces"].setdefault(region, {})
    state["spaces"][region].setdefault("pieces", {})
    state["spaces"][region]["pieces"].setdefault(faction, {})
    f_pieces = state["spaces"][region]["pieces"][faction]
    # Ensure flippable sub-dicts
    for ps in (HIDDEN, REVEALED, SCOUTED):
        f_pieces.setdefault(ps, {})


def place_piece(state, region, faction, piece_type, count=1, *,
                from_legions_track=False, from_fallen=False,
                leader_name=None, piece_state=None):
    """Place piece(s) from Available (or Legions track) onto the map.

    Args:
        state: Game state dict.
        region: Target region name constant.
        faction: Faction constant.
        piece_type: Piece type constant.
        count: Number of pieces to place (default 1).
        from_legions_track: If True, place Legions from track (not Available).
        from_fallen: If True, place Legions from Fallen box.
        leader_name: For Leaders, specify which leader (CAESAR, etc.).
        piece_state: For flippable pieces, HIDDEN or REVEALED.
            Defaults to HIDDEN per §1.4.3.

    Raises:
        PieceError: If placement violates game rules.
    """
    _validate_piece_exists_in_scenario(state, faction, piece_type)
    _ensure_faction_pieces_structure(state, region, faction)
    f_pieces = state["spaces"][region]["pieces"][faction]

    if piece_type == LEADER:
        if count != 1:
            raise PieceError("Can only place 1 Leader at a time")
        if f_pieces.get(LEADER) is not None:
            raise PieceError(
                f"{faction} already has a Leader in {region}"
            )
        # Check Available
        avail = state["available"].get(faction, {}).get(LEADER, 0)
        if avail < 1:
            raise PieceError(f"No {faction} Leader Available")
        state["available"][faction][LEADER] = avail - 1
        # Place leader — leader_name determines symbol end
        if leader_name is None:
            raise PieceError("leader_name required when placing a Leader")
        f_pieces[LEADER] = leader_name
        return

    if piece_type == LEGION:
        if faction != ROMANS:
            raise PieceError("Only Romans have Legions")
        if from_fallen:
            if state.get("fallen_legions", 0) < count:
                raise PieceError(
                    f"Only {state.get('fallen_legions', 0)} Fallen Legions "
                    f"available, need {count}"
                )
            state["fallen_legions"] -= count
        elif from_legions_track:
            # Remove from track, top rows first
            remaining = count
            for row in reversed(LEGIONS_ROWS):
                on_row = state["legions_track"].get(row, 0)
                take = min(on_row, remaining)
                state["legions_track"][row] = on_row - take
                remaining -= take
                if remaining == 0:
                    break
            if remaining > 0:
                raise PieceError(
                    f"Not enough Legions on track (need {count})"
                )
        else:
            raise PieceError(
                "Must specify from_legions_track=True or from_fallen=True "
                "when placing Legions — Legions are not in Available (§1.4.1)"
            )
        f_pieces[LEGION] = f_pieces.get(LEGION, 0) + count
        return

    if piece_type == FORT:
        if faction != ROMANS:
            raise PieceError("Only Romans have Forts")
        current_forts = f_pieces.get(FORT, 0)
        if current_forts + count > MAX_FORTS_PER_REGION:
            raise PieceError(
                f"Max {MAX_FORTS_PER_REGION} Fort per region (§1.4.2)"
            )
        avail = get_available(state, faction, FORT)
        if avail < count:
            raise PieceError(f"Only {avail} Forts Available, need {count}")
        _set_available(state, faction, FORT, avail - count)
        f_pieces[FORT] = current_forts + count
        return

    if piece_type == SETTLEMENT:
        if faction != GERMANS:
            raise PieceError("Only Germans have Settlements")
        current = f_pieces.get(SETTLEMENT, 0)
        # Check across all factions in region for settlement limit
        total_settlements = 0
        for fac, fp in state["spaces"][region].get("pieces", {}).items():
            total_settlements += fp.get(SETTLEMENT, 0)
        if total_settlements + count > MAX_SETTLEMENTS_PER_REGION:
            raise PieceError(
                f"Max {MAX_SETTLEMENTS_PER_REGION} Settlement per region "
                f"(A1.4.2)"
            )
        avail = get_available(state, faction, SETTLEMENT)
        if avail < count:
            raise PieceError(
                f"Only {avail} Settlements Available, need {count}"
            )
        _set_available(state, faction, SETTLEMENT, avail - count)
        f_pieces[SETTLEMENT] = current + count
        return

    if piece_type == ALLY:
        avail = get_available(state, faction, ALLY)
        if avail < count:
            raise PieceError(
                f"Only {avail} {faction} Allies Available, need {count}"
            )
        _set_available(state, faction, ALLY, avail - count)
        f_pieces[ALLY] = f_pieces.get(ALLY, 0) + count
        return

    if piece_type == CITADEL:
        avail = get_available(state, faction, CITADEL)
        if avail < count:
            raise PieceError(
                f"Only {avail} {faction} Citadels Available, need {count}"
            )
        _set_available(state, faction, CITADEL, avail - count)
        f_pieces[CITADEL] = f_pieces.get(CITADEL, 0) + count
        return

    if piece_type in FLIPPABLE_PIECES:
        # Auxilia/Warband — always placed Hidden per §1.4.3
        ps = piece_state if piece_state is not None else HIDDEN
        avail = get_available(state, faction, piece_type)
        if avail < count:
            raise PieceError(
                f"Only {avail} {faction} {piece_type} Available, need {count}"
            )
        _set_available(state, faction, piece_type, avail - count)
        f_pieces[ps][piece_type] = f_pieces[ps].get(piece_type, 0) + count
        return

    raise PieceError(f"Unknown piece type: {piece_type}")


def remove_piece(state, region, faction, piece_type, count=1, *,
                 to_available=True, to_fallen=False, to_track=False,
                 to_removed=False, piece_state=None):
    """Remove piece(s) from the map.

    Args:
        state: Game state dict.
        region: Source region name constant.
        faction: Faction constant.
        piece_type: Piece type constant.
        count: Number of pieces to remove (default 1).
        to_available: If True (default), pieces go to Available.
        to_fallen: If True, Legions go to Fallen box.
        to_track: If True, Legions go to Legions track.
        to_removed: If True, Legions are removed by Event (for Arverni
            victory tracking).
        piece_state: For flippable pieces, specify which state to remove from.
            If None, removes Hidden first, then Revealed, then Scouted.

    Raises:
        PieceError: If removal violates game rules.
    """
    space = state["spaces"].get(region, {})
    f_pieces = space.get("pieces", {}).get(faction, {})

    if piece_type == LEADER:
        if count != 1:
            raise PieceError("Can only remove 1 Leader at a time")
        if f_pieces.get(LEADER) is None:
            raise PieceError(f"No {faction} Leader in {region}")
        leader_name = f_pieces[LEADER]
        # Diviciacus: removed from play, not to Available — A1.4
        if leader_name == DIVICIACUS:
            f_pieces[LEADER] = None
            # Do NOT add to available — removed from play
            return
        f_pieces[LEADER] = None
        if to_available:
            state["available"][faction][LEADER] = (
                state["available"].get(faction, {}).get(LEADER, 0) + 1
            )
        return

    if piece_type == LEGION:
        if faction != ROMANS:
            raise PieceError("Only Romans have Legions")
        current = f_pieces.get(LEGION, 0)
        if current < count:
            raise PieceError(
                f"Only {current} Legions in {region}, need {count}"
            )
        f_pieces[LEGION] = current - count
        if to_fallen:
            state["fallen_legions"] = state.get("fallen_legions", 0) + count
        elif to_track:
            # Add to lowest available row
            remaining = count
            for row in LEGIONS_ROWS:
                on_row = state["legions_track"].get(row, 0)
                space_on_row = LEGIONS_PER_ROW - on_row
                add = min(space_on_row, remaining)
                state["legions_track"][row] = on_row + add
                remaining -= add
                if remaining == 0:
                    break
        elif to_removed:
            state["removed_legions"] = (
                state.get("removed_legions", 0) + count
            )
        else:
            # Default: Legions removed from Region go to Fallen — §1.4.1
            state["fallen_legions"] = state.get("fallen_legions", 0) + count
        return

    if piece_type == FORT:
        # Check for permanent Fort in Provincia — §1.4.2
        if region == PROVINCIA and f_pieces.get(FORT, 0) <= count:
            raise PieceError(
                "Cannot remove the permanent Fort from Provincia (§1.4.2)"
            )
        current = f_pieces.get(FORT, 0)
        if current < count:
            raise PieceError(
                f"Only {current} Forts in {region}, need {count}"
            )
        f_pieces[FORT] = current - count
        if to_available:
            avail = get_available(state, faction, FORT)
            _set_available(state, faction, FORT, avail + count)
        return

    if piece_type in (ALLY, CITADEL, SETTLEMENT):
        current = f_pieces.get(piece_type, 0)
        if current < count:
            raise PieceError(
                f"Only {current} {faction} {piece_type} in {region}, "
                f"need {count}"
            )
        f_pieces[piece_type] = current - count
        if to_available:
            avail = get_available(state, faction, piece_type)
            _set_available(state, faction, piece_type, avail + count)
        return

    if piece_type in FLIPPABLE_PIECES:
        # Remove from specific state or auto-select
        removed = 0
        if piece_state is not None:
            states_to_check = [piece_state]
        else:
            # Remove Hidden first, then Revealed, then Scouted
            states_to_check = [HIDDEN, REVEALED, SCOUTED]

        for ps in states_to_check:
            current = f_pieces.get(ps, {}).get(piece_type, 0)
            take = min(current, count - removed)
            if take > 0:
                f_pieces[ps][piece_type] = current - take
                removed += take
            if removed >= count:
                break

        if removed < count:
            raise PieceError(
                f"Only {removed} {faction} {piece_type} in {region}, "
                f"need {count}"
            )
        if to_available:
            avail = get_available(state, faction, piece_type)
            _set_available(state, faction, piece_type, avail + count)
        return

    raise PieceError(f"Unknown piece type: {piece_type}")


def move_piece(state, from_region, to_region, faction, piece_type, count=1,
               *, piece_state=None):
    """Move piece(s) between regions. Does not change Available.

    Args:
        state: Game state dict.
        from_region: Source region.
        to_region: Destination region.
        faction: Faction constant.
        piece_type: Piece type constant.
        count: Number of pieces to move.
        piece_state: For flippable pieces, state to move.

    Raises:
        PieceError: If move violates rules.
    """
    if piece_type == LEADER:
        # Remove then place leader, preserving identity
        space = state["spaces"].get(from_region, {})
        f_pieces = space.get("pieces", {}).get(faction, {})
        leader_name = f_pieces.get(LEADER)
        if leader_name is None:
            raise PieceError(f"No {faction} Leader in {from_region}")
        f_pieces[LEADER] = None
        _ensure_faction_pieces_structure(state, to_region, faction)
        dest = state["spaces"][to_region]["pieces"][faction]
        if dest.get(LEADER) is not None:
            raise PieceError(f"{faction} already has a Leader in {to_region}")
        dest[LEADER] = leader_name
        return

    if piece_type == LEGION:
        src = state["spaces"].get(from_region, {}).get("pieces", {}).get(
            faction, {}
        )
        current = src.get(LEGION, 0)
        if current < count:
            raise PieceError(
                f"Only {current} Legions in {from_region}, need {count}"
            )
        src[LEGION] = current - count
        _ensure_faction_pieces_structure(state, to_region, faction)
        dest = state["spaces"][to_region]["pieces"][faction]
        dest[LEGION] = dest.get(LEGION, 0) + count
        return

    if piece_type in (FORT, ALLY, CITADEL, SETTLEMENT):
        src = state["spaces"].get(from_region, {}).get("pieces", {}).get(
            faction, {}
        )
        current = src.get(piece_type, 0)
        if current < count:
            raise PieceError(
                f"Only {current} {faction} {piece_type} in {from_region}, "
                f"need {count}"
            )
        if piece_type == FORT and from_region == PROVINCIA:
            # Don't allow moving the permanent Fort
            if current - count < 1:
                raise PieceError(
                    "Cannot remove the permanent Fort from Provincia"
                )
        src[piece_type] = current - count
        _ensure_faction_pieces_structure(state, to_region, faction)
        dest = state["spaces"][to_region]["pieces"][faction]
        dest[piece_type] = dest.get(piece_type, 0) + count
        return

    if piece_type in FLIPPABLE_PIECES:
        ps = piece_state if piece_state else HIDDEN
        src = state["spaces"].get(from_region, {}).get("pieces", {}).get(
            faction, {}
        )
        current = src.get(ps, {}).get(piece_type, 0)
        if current < count:
            raise PieceError(
                f"Only {current} {faction} {ps} {piece_type} in "
                f"{from_region}, need {count}"
            )
        src[ps][piece_type] = current - count
        _ensure_faction_pieces_structure(state, to_region, faction)
        dest = state["spaces"][to_region]["pieces"][faction]
        dest[ps][piece_type] = dest[ps].get(piece_type, 0) + count
        return

    raise PieceError(f"Unknown piece type: {piece_type}")


def flip_piece(state, region, faction, piece_type, count=1, *,
               from_state=None, to_state=None):
    """Flip flippable pieces between Hidden/Revealed/Scouted.

    For flipping to Hidden when Scouted: remove Scouted marker instead
    of flipping per §1.4.3.

    Args:
        state: Game state dict.
        region: Region name constant.
        faction: Faction constant.
        piece_type: Piece type constant (must be in FLIPPABLE_PIECES).
        count: Number of pieces to flip.
        from_state: Current state (HIDDEN, REVEALED, SCOUTED).
        to_state: Target state (HIDDEN, REVEALED, SCOUTED).

    Raises:
        PieceError: If flip violates rules.
    """
    if piece_type not in FLIPPABLE_PIECES:
        raise PieceError(f"{piece_type} cannot be flipped")
    if from_state is None or to_state is None:
        raise PieceError("Must specify from_state and to_state for flip")
    if from_state == to_state:
        return  # No-op

    space = state["spaces"].get(region, {})
    f_pieces = space.get("pieces", {}).get(faction, {})

    current = f_pieces.get(from_state, {}).get(piece_type, 0)
    if current < count:
        raise PieceError(
            f"Only {current} {faction} {from_state} {piece_type} in "
            f"{region}, need {count}"
        )

    # Per §1.4.3: Scouted pieces flipped to Hidden — remove marker instead
    # This means Scouted -> Hidden becomes Scouted -> Revealed
    actual_to = to_state
    if from_state == SCOUTED and to_state == HIDDEN:
        actual_to = REVEALED

    f_pieces[from_state][piece_type] = current - count
    f_pieces.setdefault(actual_to, {})
    f_pieces[actual_to][piece_type] = (
        f_pieces[actual_to].get(piece_type, 0) + count
    )


def get_leader_in_region(state, region, faction):
    """Get the leader name in a region for a faction, if any.

    Args:
        state: Game state dict.
        region: Region name constant.
        faction: Faction constant.

    Returns:
        Leader name string (e.g. CAESAR), or None.
    """
    space = state["spaces"].get(region, {})
    return space.get("pieces", {}).get(faction, {}).get(LEADER)


def find_leader(state, faction):
    """Find the region where a faction's leader is, if on map.

    Args:
        state: Game state dict.
        faction: Faction constant.

    Returns:
        Region name constant, or None if leader not on map.
    """
    for region in state["spaces"]:
        if get_leader_in_region(state, region, faction) is not None:
            return region
    return None
