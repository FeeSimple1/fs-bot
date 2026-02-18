"""
Ambush Special Ability — §4.3.3 (Arverni), §4.4.3 (Aedui), §4.5.3 (Belgae),
§3.4.4 (Germanic base game), A4.3.3 (Arverni Ariovistus), A4.6.3 (Germanic
Ariovistus).

Ambush modifies Battle procedure. It must only accompany Battle.

Effects (§4.3.3):
  - Defender may not Retreat (but may use any Fort or Citadel normally).
  - Defender must remove a piece for each Loss suffered, including Leader,
    Legion, Citadel, or Fort without first rolling a 1-3.
    EXCEPTION: Caesar Defending on 4-6 retains roll ability + Counterattack.
  - No Counterattack except if Caesar rolled 4-6.

Belgic Ambush (§4.5.3): Caesar must roll 5-6 (not 4-6).

Requirements:
  - Arverni (§4.3.3): Region must begin with more Hidden Arverni than
    Hidden Defenders. Region must be within 1 of Vercingetorix or have
    Successor.
  - Aedui (§4.4.3): Same as Arverni but with Aedui pieces. No Leader
    requirement, but max 1 Region per Battle Command.
  - Belgae (§4.5.3): Uses Belgic pieces + Ambiorix/Successor.
    Caesar must roll 5-6.
  - Germans (base game §3.4.4): Germans ONLY battle via Ambush, always
    Ambush when they battle. Must have more Hidden pieces than enemy.
  - Arverni (Ariovistus A4.3.3): Always accompany Battle with Ambush.
    Must begin with more Hidden Arverni than Hidden Defenders. No Leader
    requirement.
  - Germans (Ariovistus A4.6.3): Like Arverni Ambush (§4.3.3) but with
    Germanic pieces + Ariovistus leader.

This module provides validation only. The actual battle modification is
handled by resolve_battle(is_ambush=True) in fs_bot/battle/resolve.py.
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    GALLIC_FACTIONS,
    # Piece types
    WARBAND, AUXILIA, FLIPPABLE_PIECES,
    # Piece states
    HIDDEN,
    # Leaders
    CAESAR, VERCINGETORIX, AMBIORIX, ARIOVISTUS_LEADER,
    # Scenarios
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    # SAs
    SA_AMBUSH,
    # Commands
    CMD_BATTLE,
)
from fs_bot.board.pieces import (
    count_pieces_by_state, get_leader_in_region, find_leader,
)
from fs_bot.map.map_data import is_adjacent
from fs_bot.commands.common import CommandError


def validate_ambush_region(state, region, faction, defending_faction):
    """Validate that a faction can Ambush in a region against a defender.

    Checks:
    1. Faction has Ambush as an available SA.
    2. Faction has more Hidden pieces in the region than the defender has
       Hidden pieces.
    3. Leader proximity requirements (faction-specific).

    Args:
        state: Game state dict.
        region: Region where battle will occur.
        faction: Faction attempting Ambush.
        defending_faction: Faction being attacked.

    Returns:
        (True, "") if valid, (False, reason) if not.
    """
    scenario = state["scenario"]

    # Count Hidden pieces for attacker
    attacker_hidden = _count_hidden(state, region, faction)

    # Count Hidden pieces for defender
    defender_hidden = _count_hidden(state, region, defending_faction)

    # §4.3.3: "begin with more Hidden Arverni than Hidden Defenders"
    # §3.4.4: "more Hidden pieces than an enemy"
    if attacker_hidden <= defender_hidden:
        return (False,
                f"{faction} has {attacker_hidden} Hidden pieces but "
                f"{defending_faction} has {defender_hidden} — need more "
                f"Hidden pieces than defender")

    # Leader proximity requirements per faction
    valid_leader, leader_reason = _check_leader_proximity(
        state, region, faction
    )
    if not valid_leader:
        return (False, leader_reason)

    return (True, "")


def _count_hidden(state, region, faction):
    """Count total Hidden pieces for a faction in a region."""
    total = 0
    for pt in FLIPPABLE_PIECES:
        total += count_pieces_by_state(state, region, faction, pt, HIDDEN)
    return total


def _check_leader_proximity(state, region, faction):
    """Check leader proximity requirements for Ambush.

    Returns:
        (True, "") if valid, (False, reason) if not.
    """
    scenario = state["scenario"]

    if faction == ARVERNI:
        if scenario in ARIOVISTUS_SCENARIOS:
            # A4.3.3: "they do not need a Leader"
            return (True, "")
        # Base game §4.3.3: "within one Region of Vercingetorix or in the
        # same Region as his Successor"
        return _within_one_of_leader(state, region, faction, VERCINGETORIX)

    elif faction == AEDUI:
        # §4.4.3: "No Leader is required"
        # But in Ariovistus with Diviciacus: A4.4 restricts to within 1
        # of Diviciacus. If Diviciacus removed, revert to original rules
        # (no leader needed per §4.4.3).
        if scenario in ARIOVISTUS_SCENARIOS:
            from fs_bot.rules_consts import DIVICIACUS
            leader_region = find_leader(state, AEDUI)
            if leader_region is not None:
                # Must be within 1 of Diviciacus — A4.4, A4.1.2
                if region == leader_region or is_adjacent(region, leader_region):
                    return (True, "")
                return (False,
                        f"Region must be within 1 of Diviciacus for "
                        f"Aedui Ambush in Ariovistus")
            # Diviciacus not on map — revert to base rules (no leader needed)
        return (True, "")

    elif faction == BELGAE:
        # §4.5.3: "uses... Ambiorix instead of Vercingetorix"
        leader_name = AMBIORIX
        if scenario in ARIOVISTUS_SCENARIOS:
            from fs_bot.rules_consts import BODUOGNATUS
            leader_name = BODUOGNATUS
        return _within_one_of_leader(state, region, faction, leader_name)

    elif faction == GERMANS:
        if scenario in BASE_SCENARIOS:
            # §3.4.4: No leader requirement — just need enough Hidden pieces
            return (True, "")
        # Ariovistus A4.6.3: "like Arverni Ambush (4.3.3) but uses
        # Germanic... Ariovistus instead of Vercingetorix"
        return _within_one_of_leader(
            state, region, faction, ARIOVISTUS_LEADER
        )

    return (False, f"{faction} cannot use Ambush")


def _within_one_of_leader(state, region, faction, leader_name):
    """Check if region is within 1 of a named leader or has Successor.

    Args:
        state: Game state dict.
        region: Region to check.
        faction: Faction owning the leader.
        leader_name: Named leader constant.

    Returns:
        (True, "") if valid, (False, reason) if not.
    """
    leader_region = find_leader(state, faction)
    if leader_region is None:
        return (False,
                f"{faction} leader not on map — cannot use Ambush")

    actual_leader = get_leader_in_region(state, leader_region, faction)

    if actual_leader == leader_name:
        # Named leader: within 1 region (same or adjacent)
        if region == leader_region or is_adjacent(region, leader_region):
            return (True, "")
        return (False,
                f"Region must be within 1 of {leader_name} for Ambush")
    else:
        # Successor: must be same region — §4.1.2
        if region == leader_region:
            return (True, "")
        return (False,
                f"Successor must be in the same region for Ambush")
