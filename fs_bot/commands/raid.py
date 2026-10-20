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


def max_raiders_per_region(state, faction):
    """§3.3.3's two Warbands, or three for Card 8 shaded's owner."""
    from fs_bot.cards.capabilities import is_capability_active, get_capability_owner
    from fs_bot.rules_consts import EVENT_SHADED
    return (3 if is_capability_active(state, 8, EVENT_SHADED)
            and get_capability_owner(state, 8) == faction else 2)


# ============================================================================
# VALIDATION
# ============================================================================

def validate_raid_region(state, region, faction, *, allow_base_germans=False):
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
    if (faction == GERMANS and scenario in BASE_SCENARIOS
            and not allow_base_germans):
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

    # Card 8 shaded: the owner "steal[s] Resources despite Citadels or
    # Forts" — skip both checks for the owning Faction.
    from fs_bot.cards.capabilities import (is_capability_active as _ica8,
                                           get_capability_owner as _gco8)
    from fs_bot.rules_consts import EVENT_SHADED as _ES8
    bypass_fortifications = (_ica8(state, 8, _ES8)
                             and _gco8(state, 8) == faction)

    # Card 8 bypasses only fortifications; a Resource must still exist.
    target_citadels = count_pieces(state, region, target_faction, CITADEL)
    if target_citadels > 0 and not bypass_fortifications:
        return False, f"{target_faction} has a Citadel in {region}"

    target_forts = count_pieces(state, region, target_faction, FORT)
    if target_forts > 0 and not bypass_fortifications:
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
    valid, reason = validate_raid_region(
        state, region, faction, allow_base_germans=free)
    if not valid:
        raise CommandError(f"Cannot Raid in {region}: {reason}")

    # Validate action count
    if not raid_actions or len(raid_actions) < 1:
        raise CommandError("Must specify at least 1 Raid action")
    # Card 8 shaded (Baggage Trains): "Your Raids may use 3 Warbands
    # per Region ..."
    _raid_max = max_raiders_per_region(state, faction)
    if len(raid_actions) > _raid_max:
        raise CommandError(
            f"Maximum {_raid_max} Warbands can Raid per Region (§3.3.3"
            + (", card 8 shaded)" if _raid_max == 3 else ")"))

    # Check enough Hidden Warbands
    hidden_warbands = count_pieces_by_state(
        state, region, faction, WARBAND, HIDDEN
    )
    if hidden_warbands < len(raid_actions):
        raise CommandError(
            f"{faction} has only {hidden_warbands} Hidden Warbands in "
            f"{region}, need {len(raid_actions)}"
        )

    # A human Enlisting German Warbands may preserve either colour's Hidden
    # pieces. Check the complete allocation before revealing any Warband.
    from fs_bot.commands.sa_enlist import BORROW_KEY, borrowed_count
    borrowing = faction == BELGAE and BORROW_KEY in state
    remaining_borrowed = borrowed_count(state, region, HIDDEN) if borrowing else 0
    remaining_native = hidden_warbands - remaining_borrowed
    owners = []
    for action in raid_actions:
        owner = action.get("physical_owner")
        if owner is not None and (not borrowing or owner not in (BELGAE, GERMANS)):
            raise CommandError("Raid physical-owner choice requires borrowed Enlist Warbands")
        if borrowing:
            selected_owner = owner or (GERMANS if remaining_borrowed else BELGAE)
            if selected_owner == GERMANS:
                remaining_borrowed -= 1
            else:
                remaining_native -= 1
            if min(remaining_borrowed, remaining_native) < 0:
                raise CommandError("Not enough Hidden Warbands of the selected physical owner")
            owners.append(selected_owner)
        else:
            owners.append(None)

    # Validate each action
    is_devastated = _is_devastated(state, region)
    remaining_resources = dict(state["resources"])
    for i, action in enumerate(raid_actions):
        action_type = action.get("type")
        if action_type == RAID_GAIN:
            if faction == GERMANS and scenario in BASE_SCENARIOS:
                raise CommandError("Germanic Raid must target a Faction (§3.4.3)")
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
            if remaining_resources.get(target, 0) < 1:
                raise CommandError(f"Cannot steal from {target}: no Resources remain for Raid action {i+1}")
            remaining_resources[target] -= 1
        else:
            raise CommandError(
                f"Unknown Raid action type: {action_type} "
                f"(must be '{RAID_GAIN}' or '{RAID_STEAL}')"
            )

    # A reactive human choice may pause or reject this atomic Region. Keep
    # its pre-Raid board so neither resources nor visibility are half-applied.
    snapshot = None
    from fs_bot.engine.raid_intimidate import eligible
    if faction == GERMANS and eligible(state, region, len(raid_actions)):
        from copy import deepcopy
        snapshot = deepcopy({k: v for k, v in state.items()
                             if k not in ("decision_agent", "_card_turn")})
        agent, card_turn = state.get("decision_agent"), state.get("_card_turn")

    # Execute: flip Warbands and apply effects
    result = {
        "faction": faction,
        "region": region,
        "warbands_flipped": len(raid_actions),
        "resources_gained": 0,
        "resources_stolen": {},
        "cost": RAID_COST,
    }

    for action, owner in zip(raid_actions, owners):
        # Flip one Hidden Warband to Revealed
        flip_piece(
            state, region, faction, WARBAND, count=1,
            from_state=HIDDEN, to_state=REVEALED,
            physical_owner=owner,
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
                # §3.4.3: Event/Enlist-guided German Raid in the base game
                # reduces the victim's Resources but earns none for Germans.
                if not (faction == GERMANS and scenario in BASE_SCENARIOS):
                    current = state["resources"].get(faction, 0)
                    state["resources"][faction] = min(
                        current + 1, MAX_RESOURCES
                    )
                    result["resources_gained"] += 1
                result["resources_stolen"][target] = (
                    result["resources_stolen"].get(target, 0) + 1
                )

    # A3.4.3: these very Warbands can free Intimidate while Raiding with
    # Ariovistus. Resolve at the primitive boundary so Event-granted Raids
    # (including Card 44) get the same optional effect as ordinary Commands.
    if faction == GERMANS and scenario in ARIOVISTUS_SCENARIOS:
        from fs_bot.engine.raid_intimidate import resolve_raid_intimidate
        try:
            intrinsic = resolve_raid_intimidate(state, region, result["warbands_flipped"])
        except BaseException:
            if snapshot is not None:
                state.clear()
                state.update(snapshot)
                if agent is not None:
                    state["decision_agent"] = agent
                if card_turn is not None:
                    state["_card_turn"] = card_turn
            raise
        if intrinsic is not None:
            result["raid_intimidate"] = intrinsic

    # Intimidate may remove pieces, so refresh Control before returning.
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

        # Choose target: player Factions before Non-player, then random among
        # equal-priority — §6.2.3.
        non_players = state.get("non_player_factions", set())
        players = [t for t in targets if t not in non_players]
        pool = players if players else targets
        target = rng.choice(pool)

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
