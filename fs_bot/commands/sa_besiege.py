"""
Besiege Special Ability — §4.2.3 (Roman).

Besiege may ONLY accompany Battle. Once announced, it may modify any Battle
Region that both has at least one Legion and a Defender with a Citadel or
Allied Tribe.

Does NOT have the usual Leader proximity requirement — §4.2.3 NOTE.

Procedure: Before and in addition to any Losses, the (Roman) Attacker may
automatically remove (Subdue) a Defending Citadel or Allied Tribe (no roll,
Attacker's choice which), regardless of whether or not the Defender is
Retreating.

§4.2.3 NOTE: "A Defender with a Citadel still suffers only half Losses
that Battle, even after the Citadel is removed."

Ariovistus (A4.2.3): May also remove a Settlement instead of an Ally.

This module provides validation only. The actual Besiege removal is
executed by resolve_battle(besiege_target=...) in fs_bot/battle/resolve.py.
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS,
    # Piece types
    LEGION, ALLY, CITADEL, SETTLEMENT,
    # Scenarios
    ARIOVISTUS_SCENARIOS,
)
from fs_bot.board.pieces import count_pieces
from fs_bot.commands.common import CommandError


def validate_besiege_region(state, region, defending_faction):
    """Validate that Besiege can modify a Battle in this region.

    §4.2.3: Region must have at least one Legion and a Defender with a
    Citadel or Allied Tribe.

    No Leader proximity requirement — §4.2.3 NOTE.

    Args:
        state: Game state dict.
        region: Battle region.
        defending_faction: Faction being attacked.

    Returns:
        (True, "") if valid, (False, reason) if not.
    """
    # Must have at least one Legion
    legion_count = count_pieces(state, region, ROMANS, LEGION)
    if legion_count < 1:
        return (False,
                "Besiege requires at least one Legion in the region")

    # Defender must have Citadel or Allied Tribe
    space = state["spaces"][region]
    d_pieces = space.get("pieces", {}).get(defending_faction, {})
    has_citadel = d_pieces.get(CITADEL, 0) > 0
    has_ally = d_pieces.get(ALLY, 0) > 0

    # Ariovistus: also check Settlements — A4.2.3
    scenario = state["scenario"]
    has_settlement = False
    if scenario in ARIOVISTUS_SCENARIOS:
        has_settlement = d_pieces.get(SETTLEMENT, 0) > 0

    if not (has_citadel or has_ally or has_settlement):
        return (False,
                "Defender must have a Citadel, Allied Tribe, or "
                "Settlement for Besiege")

    return (True, "")


def get_besiege_targets(state, region, defending_faction):
    """Get valid Besiege target piece types in a region.

    §4.2.3: Attacker's choice of Citadel or Allied Tribe.
    A4.2.3: Also Settlement in Ariovistus.

    Args:
        state: Game state dict.
        region: Battle region.
        defending_faction: Faction being attacked.

    Returns:
        List of valid piece type constants (CITADEL, ALLY, SETTLEMENT).
    """
    space = state["spaces"][region]
    d_pieces = space.get("pieces", {}).get(defending_faction, {})
    scenario = state["scenario"]

    targets = []
    if d_pieces.get(CITADEL, 0) > 0:
        targets.append(CITADEL)
    if d_pieces.get(ALLY, 0) > 0:
        targets.append(ALLY)
    if scenario in ARIOVISTUS_SCENARIOS and d_pieces.get(SETTLEMENT, 0) > 0:
        targets.append(SETTLEMENT)

    return targets
