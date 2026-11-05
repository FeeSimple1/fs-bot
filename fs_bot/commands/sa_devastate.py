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
    ARVERNI, LEGION, VERCINGETORIX, MARKER_DEVASTATED, ARIOVISTUS_SCENARIOS,
)
from fs_bot.board.pieces import remove_piece
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
            using §8.4.1 default priority when an owner defers. Exact owner
            choices are gathered before any removal. Supplied triples are
            trusted pre-authorized owner plans and must specify the exact loss.

    Returns:
        dict with:
            "removed": {faction: [(piece_type, count)]}
            "devastated_placed": True if marker placed.

    Raises:
        CommandError: If operation violates rules.
    """
    from fs_bot.engine.devastate_losses import collect_removals
    plans,authored=collect_removals(state,region,removals)
    result = {"removed": {}, "devastated_placed": False}
    for faction,entries in plans.items():
        totals={}
        for entry in entries:
            piece,visibility,count=entry['piece_type'],entry['piece_state'],entry['count']
            remove_piece(state,region,faction,piece,count,
                         piece_state=visibility,to_fallen=piece==LEGION)
            totals[piece]=totals.get(piece,0)+count
        if totals:result['removed'][faction]=list(totals.items())
    if authored:
        result['removal_details']={f:[dict(e) for e in entries] for f,entries in plans.items()}

    # Place Devastated marker — §4.3.2
    markers = state.setdefault("markers", {})
    region_markers = markers.setdefault(region, {})
    if MARKER_DEVASTATED not in region_markers:
        region_markers[MARKER_DEVASTATED] = True
        result["devastated_placed"] = True

    refresh_all_control(state)

    return result

