"""Raid command — Gallic (§3.3.3) and Germanic (§3.4.3, A3.4.3) Raid.

Raid adds Resources by flipping Hidden Warbands to Revealed.
For each flipped Warband, the faction either gains 1 Resource
(if the Region is not Devastated) or steals 1 Resource from a
qualifying enemy faction.

Available to: Arverni, Aedui, Belgae (all scenarios),
              Germans (Ariovistus only as player command;
              base game only via Germans Phase §6.2.3).

Cost: 0 Resources (§3.3.3, §3.4.3)
Frost: Does NOT restrict Raid (§2.3.8 restricts March only)

Reference: §3.3.3, §3.4.3, §6.2.3, A3.3.3, A3.4.3
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    FACTIONS, GALLIC_FACTIONS,
    # Piece types
    WARBAND, FORT, CITADEL,
    # Piece states
    HIDDEN, REVEALED,
    # Scenarios
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    # Costs
    RAID_COST,
    # Markers
    MARKER_DEVASTATED,
    # Resources
    MAX_RESOURCES,
)

from fs_bot.board.pieces import (
    flip_piece, count_pieces, count_pieces_by_state, PieceError,
)
from fs_bot.board.control import refresh_all_control
from fs_bot.map.map_data import ALL_REGION_DATA
from fs_bot.commands.common import CommandError, _is_devastated


# Factions that can execute Raid as a player command
RAID_FACTIONS_BASE = GALLIC_FACTIONS + (GERMANS,)
RAID_FACTIONS_ARIOVISTUS = GALLIC_FACTIONS + (GERMANS,)

# Raid action types
RAID_GAIN = "gain"
RAID_STEAL = "steal"


# ============================================================================
# VALIDATION
# ============================================================================

def validate_raid_region(state, region, faction):
    """Check if a faction can Raid in a region.

    Requirements (§3.3.3):
    - Region must be playable for the current scenario
    - Faction must have at least 1 Hidden Warband in the region

    Args:
        state: Game state dict.
        region: Region name constant.
        faction: Faction executing the Raid.

    Returns:
        Tuple of (valid: bool, reason: str or None).
    """
    scenario = state["scenario"]

    # Check playability
    region_data = ALL_REGION_DATA.get(region)
    if region_data is None:
        return False, f"{region} is not a valid region"

    if not region_data.is_playable(scenario, state.get("capabilities")):
        return False, f"{region} is not playable in {scenario}"

    # Check faction can Raid
    if faction not in GALLIC_FACTIONS and faction != GERMANS:
        return False, f"{faction} cannot Raid"

    # Germans cannot Raid as a player command in base game — §3.4.3
    # (base game Germanic Raid is only via Germans Phase §6.2.3)
    if faction == GERMANS and scenario in BASE_SCENARIOS:
        return False, (
            "Germans cannot Raid as a player command in base game "
            "(only via Germans Phase §6.2.3)"
        )

    # Must have Hidden Warbands
    hidden_warbands = count_pieces_by_state(
        state, region, faction, WARBAND, HIDDEN
    )
    if hidden_warbands < 1:
        return False, f"{faction} has no Hidden Warbands in {region}"

    return True, None


def validate_raid_steal_target(state, region, faction, target_faction):
    """Check if target_faction is a valid Raid steal target.

    Requirements (§3.3.3):
    - Target must be an enemy (not executing faction)
    - Target must be non-Germanic in base game; any enemy in
      Ariovistus (A3.3.3)
    - Target must have pieces in the region
    - Target must NOT have a Citadel in the region
    - Target must NOT have a Fort in the region
    - Target must have at least 1 Resource

    Args:
        state: Game state dict.
        region: Region name constant.
        faction: Executing faction.
        target_faction: Faction to steal from.

    Returns:
        Tuple of (valid: bool, reason: str or None).
    """
    scenario = state["scenario"]

    # Must be enemy
    if target_faction == faction:
        return False, "Cannot steal from own faction"

    # Base game: cannot steal from Germans — §3.3.3 "non-Germanic enemy"
    if target_faction == GERMANS and scenario in BASE_SCENARIOS:
        return False, (
            "Cannot steal from Germans in base game "
            "(§3.3.3: non-Germanic enemy)"
        )

    # Must have pieces in the region
    target_pieces = count_pieces(state, region, target_faction)
    if target_pieces < 1:
        return False, f"{target_faction} has no pieces in {region}"

    # Must NOT have Citadel — §3.3.3
    target_citadels = count_pieces(state, region, target_faction, CITADEL)
    if target_citadels > 0:
        return False, f"{target_faction} has a Citadel in {region}"

    # Must NOT have Fort — §3.3.3
    target_forts = count_pieces(state, region, target_faction, FORT)
    if target_forts > 0:
        return False, f"{target_faction} has a Fort in {region}"

    # Must have Resources to steal
    target_resources = state["resources"].get(target_faction, 0)
    if target_resources < 1:
        return False, f"{target_faction} has 0 Resources"

    return True, None


def get_valid_steal_targets(state, region, faction):
    """Get all valid factions to steal from during Raid.

    Args:
        state: Game state dict.
        region: Region name constant.
        faction: Executing faction.

    Returns:
        List of valid target faction constants.
    """
    targets = []
    for target in FACTIONS:
        if target == faction:
            continue
        valid, _ = validate_raid_steal_target(
            state, region, faction, target
        )
        if valid:
            targets.append(target)
    return targets


# ============================================================================
# RAID EXECUTION
# ============================================================================

def raid_in_region(state, region, faction, raid_actions, *, free=False):
    """Execute Raid in a single region.

    Flips 1 or 2 Hidden Warbands to Revealed. For each flipped Warband,
    the faction either gains 1 Resource or steals 1 Resource from a
    qualifying enemy.

    Args:
        state: Game state dict. Modified in place.
        region: Target region.
        faction: Executing faction.
        raid_actions: List of 1 or 2 dicts, each one of:
            {"type": "gain"} — gain 1 Resource (region must not be Devastated)
            {"type": "steal", "target": faction_name} — steal 1 Resource
        free: If True, skip cost check (always free, but matches pattern).

    Returns:
        Dict with results:
            "faction": executing faction
            "region": region
            "warbands_flipped": count of Warbands flipped
            "resources_gained": net Resources gained by executing faction
            "resources_stolen": dict of {target: amount stolen}
            "cost": 0

    Raises:
        CommandError: If the action violates rules.
    """
    scenario = state["scenario"]

    # Validate region
    valid, reason = validate_raid_region(state, region, faction)
    if not valid:
        raise CommandError(f"Cannot Raid in {region}: {reason}")

    # Validate action count
    if not raid_actions or len(raid_actions) < 1:
        raise CommandError("Must specify at least 1 Raid action")
    if len(raid_actions) > 2:
        raise CommandError("Maximum 2 Warbands can Raid per Region (§3.3.3)")

    # Check enough Hidden Warbands
    hidden_warbands = count_pieces_by_state(
        state, region, faction, WARBAND, HIDDEN
    )
    if hidden_warbands < len(raid_actions):
        raise CommandError(
            f"{faction} has only {hidden_warbands} Hidden Warbands in "
            f"{region}, need {len(raid_actions)}"
        )

    # Validate each action
    is_devastated = _is_devastated(state, region)
    for i, action in enumerate(raid_actions):
        action_type = action.get("type")
        if action_type == RAID_GAIN:
            if is_devastated:
                raise CommandError(
                    f"Cannot gain Resources from Raid in Devastated "
                    f"Region {region} (§3.3.3)"
                )
        elif action_type == RAID_STEAL:
            target = action.get("target")
            if target is None:
                raise CommandError(
                    f"Raid steal action {i+1} must specify 'target'"
                )
            valid, reason = validate_raid_steal_target(
                state, region, faction, target
            )
            if not valid:
                raise CommandError(
                    f"Cannot steal from {target} in {region}: {reason}"
                )
        else:
            raise CommandError(
                f"Unknown Raid action type: {action_type} "
                f"(must be '{RAID_GAIN}' or '{RAID_STEAL}')"
            )

    # Execute: flip Warbands and apply effects
    result = {
        "faction": faction,
        "region": region,
        "warbands_flipped": len(raid_actions),
        "resources_gained": 0,
        "resources_stolen": {},
        "cost": RAID_COST,
    }

    for action in raid_actions:
        # Flip one Hidden Warband to Revealed
        flip_piece(
            state, region, faction, WARBAND, count=1,
            from_state=HIDDEN, to_state=REVEALED,
        )

        action_type = action["type"]
        if action_type == RAID_GAIN:
            # Add 1 Resource — §3.3.3
            current = state["resources"].get(faction, 0)
            state["resources"][faction] = min(current + 1, MAX_RESOURCES)
            result["resources_gained"] += 1

        elif action_type == RAID_STEAL:
            # Steal 1 Resource from target — §3.3.3
            target = action["target"]
            target_resources = state["resources"].get(target, 0)
            if target_resources >= 1:
                state["resources"][target] = target_resources - 1
                current = state["resources"].get(faction, 0)
                state["resources"][faction] = min(
                    current + 1, MAX_RESOURCES
                )
                result["resources_gained"] += 1
                result["resources_stolen"][target] = (
                    result["resources_stolen"].get(target, 0) + 1
                )

    # Control doesn't change from Raid (no pieces placed/removed,
    # only flipped), but refresh for safety
    refresh_all_control(state)

    return result


# ============================================================================
# GERMANS PHASE RAID (§6.2.3) — Base Game Only
# ============================================================================

def get_germans_phase_raid_targets(state, region):
    """Get valid Raid targets in a region for the Germans Phase.

    Per §6.2.3:
    - Only factions with more than 0 Resources
    - Target must not have Fort or Citadel in region
    - Player factions are targeted before Non-player factions

    Args:
        state: Game state dict.
        region: Region name constant.

    Returns:
        List of valid target faction constants, ordered by priority
        (player factions first).
    """
    targets = []
    for target in FACTIONS:
        if target == GERMANS:
            continue
        # Must have pieces in region
        if count_pieces(state, region, target) < 1:
            continue
        # Must not have Fort or Citadel — §6.2.3 / §3.3.3
        if count_pieces(state, region, target, FORT) > 0:
            continue
        if count_pieces(state, region, target, CITADEL) > 0:
            continue
        # Must have Resources > 0 — §6.2.3
        if state["resources"].get(target, 0) < 1:
            continue
        targets.append(target)
    return targets


def germans_phase_raid_region(state, region):
    """Execute deterministic Germanic Raid in a region during Germans Phase.

    Per §6.2.3:
    - Raid with as many Germanic Warbands as able (flip Hidden to Revealed)
    - Only against factions with > 0 Resources and no Fort/Citadel
    - Raid until target reaches 0 Resources
    - Target reduces Resources; Germans do not receive them (§3.4.3)
    - Player factions targeted before Non-player factions
    - Choose randomly among equal targets within a region

    This uses the standard Raid mechanic (§3.3.3) but:
    - Germans don't receive the Resources (§3.4.3)
    - All available Hidden Warbands are used (not just 1-2)
    - Targeting is deterministic per §6.2.3 priority

    Args:
        state: Game state dict. Modified in place.
        region: Region to Raid in.

    Returns:
        Dict with results:
            "region": region
            "warbands_flipped": count of Warbands used
            "resources_stolen": {target_faction: amount lost}

    Raises:
        CommandError: If region has no Germanic Hidden Warbands.
    """
    scenario = state["scenario"]
    if scenario not in BASE_SCENARIOS:
        raise CommandError(
            "Germans Phase Raid is base game only (§6.2.3)"
        )

    hidden_warbands = count_pieces_by_state(
        state, region, GERMANS, WARBAND, HIDDEN
    )
    if hidden_warbands < 1:
        raise CommandError(
            f"Germans have no Hidden Warbands in {region}"
        )

    result = {
        "region": region,
        "warbands_flipped": 0,
        "resources_stolen": {},
    }

    # Raid with as many Warbands as able — §6.2.3
    # Each Warband flipped steals 1 Resource from a target
    warbands_remaining = hidden_warbands
    rng = state["rng"]

    while warbands_remaining > 0:
        targets = get_germans_phase_raid_targets(state, region)
        if not targets:
            break

        # Choose target: player before NP, then random — §6.2.3
        # For now we use rng to select among equal-priority targets
        target = rng.choice(targets)

        # Flip one Warband
        flip_piece(
            state, region, GERMANS, WARBAND, count=1,
            from_state=HIDDEN, to_state=REVEALED,
        )
        warbands_remaining -= 1
        result["warbands_flipped"] += 1

        # Target loses 1 Resource; Germans do NOT receive — §3.4.3
        target_resources = state["resources"].get(target, 0)
        if target_resources >= 1:
            state["resources"][target] = target_resources - 1
            result["resources_stolen"][target] = (
                result["resources_stolen"].get(target, 0) + 1
            )

    refresh_all_control(state)
    return result
