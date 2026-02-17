"""
Control module — Calculate and manage control per region.

A faction controls a region if it has more pieces there than each other
faction individually (§1.6). "Forces" for control purposes include:
- All mobile pieces (Leader, Legions, Auxilia, Warbands)
- Allies count as pieces
- Citadels count as pieces
- Forts count for Romans
- Settlements count for Germans (Ariovistus) — A1.4

Reference: §1.6, A1.4
"""

from fs_bot.rules_consts import (
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    FACTIONS,
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    FLIPPABLE_PIECES,
    HIDDEN, REVEALED, SCOUTED,
    ROMAN_CONTROL, ARVERNI_CONTROL, AEDUI_CONTROL,
    BELGIC_CONTROL, GERMANIC_CONTROL, NO_CONTROL,
    FACTION_CONTROL,
    ARIOVISTUS_SCENARIOS,
)


def _count_faction_forces(space, faction, scenario):
    """Count all forces for a faction in a space for control purposes.

    Per §1.6: Any Faction that has more Forces (pieces) in a Region
    than all other Factions combined Controls that Region.

    IMPORTANT: The rule says "more Forces than all other Factions combined",
    meaning a faction must have strictly more pieces than the sum of all
    other factions' pieces.

    Wait — re-reading §1.6: "Any Faction (including Germanic) that has more
    Forces (pieces, 1.4) in a Region than all other Factions combined Controls
    that Region."

    This means: faction_count > sum_of_all_others.
    """
    f_pieces = space.get("pieces", {}).get(faction, {})
    total = 0

    # Leader
    if f_pieces.get(LEADER) is not None:
        total += 1

    # Legions (Romans only)
    total += f_pieces.get(LEGION, 0)

    # Forts count for Romans — §1.6
    if faction == ROMANS:
        total += f_pieces.get(FORT, 0)

    # Allies
    total += f_pieces.get(ALLY, 0)

    # Citadels
    total += f_pieces.get(CITADEL, 0)

    # Settlements count for Germans — A1.4
    if faction == GERMANS and scenario in ARIOVISTUS_SCENARIOS:
        total += f_pieces.get(SETTLEMENT, 0)

    # Flippable pieces (Auxilia for Romans, Warbands for Gallic/Germanic)
    for piece_type in FLIPPABLE_PIECES:
        for ps in (HIDDEN, REVEALED, SCOUTED):
            total += f_pieces.get(ps, {}).get(piece_type, 0)

    return total


def calculate_control(state, region):
    """Calculate which faction controls a region.

    Per §1.6: A faction controls if it has more Forces than all other
    factions combined. If no faction does, No Control.

    Args:
        state: Game state dict.
        region: Region name constant.

    Returns:
        Control constant (ROMAN_CONTROL, ARVERNI_CONTROL, etc.,
        or NO_CONTROL).
    """
    space = state["spaces"].get(region, {})
    scenario = state["scenario"]

    # Count forces for each faction present
    force_counts = {}
    total_all = 0
    for faction in FACTIONS:
        c = _count_faction_forces(space, faction, scenario)
        force_counts[faction] = c
        total_all += c

    if total_all == 0:
        return NO_CONTROL

    # Check each faction: does it have more than all others combined?
    for faction in FACTIONS:
        my_count = force_counts[faction]
        others_count = total_all - my_count
        if my_count > others_count:
            return FACTION_CONTROL[faction]

    return NO_CONTROL


def refresh_all_control(state):
    """Recalculate control for all regions and update markers.

    Args:
        state: Game state dict. Modified in place.
    """
    for region in state["spaces"]:
        ctrl = calculate_control(state, region)
        state["spaces"][region]["control"] = ctrl


def is_controlled_by(state, region, faction):
    """Check if a region is controlled by a specific faction.

    Args:
        state: Game state dict.
        region: Region name constant.
        faction: Faction constant.

    Returns:
        True if the faction controls the region.
    """
    space = state["spaces"].get(region, {})
    return space.get("control") == FACTION_CONTROL.get(faction)


def get_controlled_regions(state, faction):
    """Get all regions controlled by a faction.

    Args:
        state: Game state dict.
        faction: Faction constant.

    Returns:
        List of region name constants.
    """
    ctrl = FACTION_CONTROL.get(faction)
    if ctrl is None:
        return []
    return [
        region for region, space in state["spaces"].items()
        if space.get("control") == ctrl
    ]
