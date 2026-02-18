"""Seize command — Roman Seize (§3.2.3, A3.2.3).

Seize extracts Resources from Subdued Tribes and can Disperse them.
Procedure per Region (in order):
    1. Dispersal: Place Dispersed markers on Subdued Tribes (Roman Control)
    2. Rally: Arverni/Belgae may free Rally adjacent to dispersed tribes
    3. Forage: Gain Resources based on tribe statuses
    4. Harassment: Enemy factions may inflict losses on Roman pieces

Available to: Romans only
Cost: 0 Resources (§3.2.3)

Reference: §3.2.3, A3.2.3
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    FACTIONS, GALLIC_FACTIONS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL,
    # Piece states
    HIDDEN,
    # Costs
    SEIZE_COST,
    # Scenarios
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    # Markers
    MARKER_DEVASTATED,
    # Tribe statuses
    DISPERSED, DISPERSED_GATHERING,
    # Dispersed limit
    MAX_DISPERSED_MARKERS,
    # Resources
    MAX_RESOURCES,
    # Battle
    LOSS_ROLL_THRESHOLD, HARASSMENT_WARBANDS_PER_LOSS,
    DIE_MIN, DIE_MAX,
)

from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, remove_piece,
    PieceError,
)
from fs_bot.board.control import (
    is_controlled_by, refresh_all_control,
)
from fs_bot.map.map_data import (
    ALL_REGION_DATA, get_tribes_in_region,
)


class CommandError(Exception):
    """Raised when a Seize command violates game rules."""
    pass


# ============================================================================
# Seize Resource constants — §3.2.3
# ============================================================================

SEIZE_RESOURCES_PER_TRIBE = 2          # +2 per Subdued or Roman Allied tribe
SEIZE_RESOURCES_PER_DISPERSED = 6      # +6 per Dispersed marker just placed


# ============================================================================
# VALIDATION
# ============================================================================

def _is_devastated(state, region):
    """Check if a region has the Devastated marker."""
    markers = state.get("markers", {}).get(region, {})
    return MARKER_DEVASTATED in markers


def validate_seize_region(state, region):
    """Check if Romans can Seize in a region.

    Requirements (§3.2.3):
    - Region must be playable for the current scenario
    - Region must have Roman pieces

    Args:
        state: Game state dict.
        region: Region name constant.

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

    # Must have Roman pieces — §3.2.3
    roman_pieces = count_pieces(state, region, ROMANS)
    if roman_pieces < 1:
        return False, f"Romans have no pieces in {region}"

    return True, None


# ============================================================================
# DISPERSAL — §3.2.3 Step 1
# ============================================================================

def count_dispersed_on_map(state):
    """Count total Dispersed markers currently on the map.

    Counts both Dispersed and Dispersed-Gathering markers, as both
    occupy a tribe circle. Maximum 4 Dispersed markers (§3.2.3).

    Args:
        state: Game state dict.

    Returns:
        Integer count of Dispersed markers on the map.
    """
    count = 0
    for tribe, tribe_state in state.get("tribes", {}).items():
        if tribe_state.get("status") in (DISPERSED, DISPERSED_GATHERING):
            count += 1
    return count


def get_dispersible_tribes(state, region):
    """Get Subdued tribes in a region that can receive Dispersed markers.

    Requirements (§3.2.3):
    - Region must have Roman Control
    - Tribe must be Subdued (no Ally, no Dispersed marker)
    - Total Dispersed markers on map must be < MAX_DISPERSED_MARKERS (4)

    Args:
        state: Game state dict.
        region: Region name constant.

    Returns:
        List of tribe name constants that can be Dispersed.
    """
    scenario = state["scenario"]

    # Must have Roman Control for Dispersal — §3.2.3
    if not is_controlled_by(state, region, ROMANS):
        return []

    # Check marker limit
    current_dispersed = count_dispersed_on_map(state)
    if current_dispersed >= MAX_DISPERSED_MARKERS:
        return []

    result = []
    tribes = get_tribes_in_region(region, scenario)
    remaining_markers = MAX_DISPERSED_MARKERS - current_dispersed

    for tribe in tribes:
        if len(result) >= remaining_markers:
            break

        tribe_state = state.get("tribes", {}).get(tribe, {})

        # Must be Subdued: no allied faction, no Dispersed status
        if tribe_state.get("allied_faction") is not None:
            continue
        if tribe_state.get("status") in (DISPERSED, DISPERSED_GATHERING):
            continue

        result.append(tribe)

    return result


# ============================================================================
# FORAGE — §3.2.3 Step 3
# ============================================================================

def calculate_forage(state, region, tribes_just_dispersed):
    """Calculate Resources gained from Seize Forage.

    Per §3.2.3:
    - Only if region is NOT Devastated
    - +2 per Subdued or Roman Allied (not Dispersed) tribe
    - +6 per Dispersed marker just placed

    Args:
        state: Game state dict.
        region: Region name constant.
        tribes_just_dispersed: List of tribe names that were just Dispersed.

    Returns:
        Integer Resources to gain (0 if Devastated).
    """
    if _is_devastated(state, region):
        return 0

    scenario = state["scenario"]
    tribes = get_tribes_in_region(region, scenario)
    resources = 0

    for tribe in tribes:
        # Skip tribes that were just dispersed — they get +6 instead
        if tribe in tribes_just_dispersed:
            continue

        tribe_state = state.get("tribes", {}).get(tribe, {})

        # Skip already-Dispersed tribes
        if tribe_state.get("status") in (DISPERSED, DISPERSED_GATHERING):
            continue

        # Subdued (no ally, no dispersed) or Roman Allied
        allied_faction = tribe_state.get("allied_faction")
        if allied_faction is None:
            # Subdued — +2
            resources += SEIZE_RESOURCES_PER_TRIBE
        elif allied_faction == ROMANS:
            # Roman Allied — +2
            resources += SEIZE_RESOURCES_PER_TRIBE
        # Other faction's Ally: not counted

    # +6 per Dispersed marker just placed
    resources += len(tribes_just_dispersed) * SEIZE_RESOURCES_PER_DISPERSED

    return resources


# ============================================================================
# HARASSMENT — §3.2.3 Step 4 (same as March Harassment §3.2.2)
# ============================================================================

def calculate_harassment(state, region, harassing_faction):
    """Calculate Harassment losses a faction can inflict on Romans.

    Per §3.2.3 / §3.2.2:
    For every 3 Hidden Warbands the harassing faction has in the region,
    Romans must lose 1 piece.

    Args:
        state: Game state dict.
        region: Region name constant.
        harassing_faction: Faction inflicting Harassment.

    Returns:
        Integer number of losses the harassing faction can inflict.
    """
    hidden_warbands = count_pieces_by_state(
        state, region, harassing_faction, WARBAND, HIDDEN
    )
    return hidden_warbands // HARASSMENT_WARBANDS_PER_LOSS


def get_harassment_factions(state, region):
    """Get factions that can Harass during Seize.

    Per §3.2.3: "each Faction with Warbands in the selected Region
    may opt to inflict Losses on Roman pieces there."

    Args:
        state: Game state dict.
        region: Region name constant.

    Returns:
        List of (faction, potential_losses) tuples for factions that
        can Harass, in faction order from the card. Note: potential_losses
        is based on Hidden Warbands only (per §3.2.2 Harassment).
    """
    result = []
    for faction in FACTIONS:
        if faction == ROMANS:
            continue
        losses = calculate_harassment(state, region, faction)
        if losses > 0:
            result.append((faction, losses))
    return result


def execute_harassment_loss(state, region, loss_choice):
    """Execute a single Harassment loss on Roman pieces.

    Per §3.2.2/§3.2.3: Romans select and remove one Auxilia or
    Roman Ally, or — if any Legions, Leader, or Fort there — may
    instead roll a die. On 1-2-3, must remove a Legion, Leader, or Fort.

    Args:
        state: Game state dict. Modified in place.
        region: Region name constant.
        loss_choice: One of:
            "auxilia" — remove 1 Auxilia
            "ally" — remove 1 Roman Ally
            "roll" — roll die for hard target (Legion/Leader/Fort)

    Returns:
        Dict with:
            "choice": the loss_choice
            "removed": piece_type removed (or None if roll survived)
            "roll": die roll value (or None if no roll)
    """
    result = {"choice": loss_choice, "removed": None, "roll": None}

    if loss_choice == "auxilia":
        total_auxilia = count_pieces(state, region, ROMANS, AUXILIA)
        if total_auxilia < 1:
            raise CommandError(
                f"No Roman Auxilia in {region} to remove"
            )
        remove_piece(state, region, ROMANS, AUXILIA, count=1)
        result["removed"] = AUXILIA

    elif loss_choice == "ally":
        allies = count_pieces(state, region, ROMANS, ALLY)
        if allies < 1:
            raise CommandError(
                f"No Roman Allies in {region} to remove"
            )
        remove_piece(state, region, ROMANS, ALLY, count=1)
        result["removed"] = ALLY

    elif loss_choice == "roll":
        # Must have hard targets (Legion, Leader, or Fort) to roll
        has_legion = count_pieces(state, region, ROMANS, LEGION) > 0
        has_leader = count_pieces(state, region, ROMANS, LEADER) > 0
        has_fort = count_pieces(state, region, ROMANS, FORT) > 0
        if not (has_legion or has_leader or has_fort):
            raise CommandError(
                "No Legion, Leader, or Fort in region to roll for"
            )

        roll = state["rng"].randint(DIE_MIN, DIE_MAX)
        result["roll"] = roll

        if roll <= LOSS_ROLL_THRESHOLD:
            # Must remove a Legion, Leader, or Fort
            # The Romans choose which hard target to remove
            # For mechanical execution, we remove in priority order:
            # Fort first (least impactful to Roman combat), then
            # Legion (goes to Fallen), then Leader
            # NOTE: The caller/bot should make this decision.
            # For now we store the roll result; actual removal
            # requires a follow-up call.
            result["removed"] = "hard_target_hit"
        else:
            # Roll survived — no piece removed
            result["removed"] = None

    else:
        raise CommandError(f"Unknown loss choice: {loss_choice}")

    return result


def remove_hard_target(state, region, piece_type):
    """Remove a specific hard target piece from Harassment roll.

    Called after execute_harassment_loss returns "hard_target_hit"
    to remove the specific piece the Romans chose.

    Args:
        state: Game state dict. Modified in place.
        region: Region name constant.
        piece_type: One of LEGION, LEADER, FORT.

    Returns:
        Dict with "removed": piece_type.

    Raises:
        CommandError: If the piece is not present.
    """
    if piece_type == LEGION:
        if count_pieces(state, region, ROMANS, LEGION) < 1:
            raise CommandError(f"No Legion in {region} to remove")
        # Legions removed from map go to Fallen — §1.4.1
        remove_piece(
            state, region, ROMANS, LEGION, count=1, to_fallen=True
        )
    elif piece_type == LEADER:
        if count_pieces(state, region, ROMANS, LEADER) < 1:
            raise CommandError(f"No Leader in {region} to remove")
        remove_piece(state, region, ROMANS, LEADER, count=1)
    elif piece_type == FORT:
        if count_pieces(state, region, ROMANS, FORT) < 1:
            raise CommandError(f"No Fort in {region} to remove")
        remove_piece(state, region, ROMANS, FORT, count=1)
    else:
        raise CommandError(
            f"Invalid hard target type: {piece_type} "
            f"(must be {LEGION}, {LEADER}, or {FORT})"
        )
    return {"removed": piece_type}


# ============================================================================
# RALLY CHECK — §3.2.3 Step 2
# ============================================================================

def seize_rally_roll(state, faction):
    """Roll die for Seize-triggered free Rally.

    Per §3.2.3: For each tribe just Dispersed, Arverni then Belgae
    each roll a die. On 1-2-3, they may free Rally in adjacent regions.

    Args:
        state: Game state dict (for rng).
        faction: Faction rolling (ARVERNI or BELGAE).

    Returns:
        Dict with:
            "faction": rolling faction
            "roll": die value (1-6)
            "can_rally": True if roll <= 3
    """
    if faction not in (ARVERNI, BELGAE):
        raise CommandError(
            f"Only Arverni and Belgae roll for Seize Rally (not {faction})"
        )

    roll = state["rng"].randint(DIE_MIN, DIE_MAX)
    return {
        "faction": faction,
        "roll": roll,
        "can_rally": roll <= LOSS_ROLL_THRESHOLD,
    }


# ============================================================================
# SEIZE EXECUTION — §3.2.3
# ============================================================================

def seize_in_region(state, region, tribes_to_disperse=None):
    """Execute Seize in a single region.

    Handles the Dispersal and Forage substeps. Rally checks and
    Harassment are returned as info for the caller to execute
    (since they involve other factions' decisions).

    Args:
        state: Game state dict. Modified in place.
        region: Target region.
        tribes_to_disperse: List of tribe names to place Dispersed markers
            on. Empty list or None means no Dispersal (Forage still occurs).

    Returns:
        Dict with results:
            "region": region
            "cost": 0
            "tribes_dispersed": list of tribe names dispersed
            "forage_resources": Resources gained from Forage
            "rally_opportunities": list of dicts with rally roll info
                for each dispersed tribe (Arverni and Belgae rolls)
            "harassment_opportunities": list of (faction, potential_losses)
                tuples for factions that can Harass

    Raises:
        CommandError: If the action violates rules.
    """
    scenario = state["scenario"]

    # Validate region
    valid, reason = validate_seize_region(state, region)
    if not valid:
        raise CommandError(f"Cannot Seize in {region}: {reason}")

    if tribes_to_disperse is None:
        tribes_to_disperse = []

    result = {
        "region": region,
        "cost": SEIZE_COST,
        "tribes_dispersed": [],
        "forage_resources": 0,
        "rally_opportunities": [],
        "harassment_opportunities": [],
    }

    # ----- Step 1: Dispersal — §3.2.3 -----
    if tribes_to_disperse:
        # Validate Roman Control
        if not is_controlled_by(state, region, ROMANS):
            raise CommandError(
                f"Dispersal requires Roman Control in {region} (§3.2.3)"
            )

        # Validate marker limit
        current_dispersed = count_dispersed_on_map(state)
        if current_dispersed + len(tribes_to_disperse) > MAX_DISPERSED_MARKERS:
            raise CommandError(
                f"Cannot place {len(tribes_to_disperse)} Dispersed markers: "
                f"{current_dispersed} already on map, max "
                f"{MAX_DISPERSED_MARKERS} (§3.2.3)"
            )

        # Validate each tribe
        region_tribes = get_tribes_in_region(region, scenario)
        for tribe in tribes_to_disperse:
            if tribe not in region_tribes:
                raise CommandError(
                    f"Tribe {tribe} is not in {region}"
                )
            tribe_state = state.get("tribes", {}).get(tribe, {})
            if tribe_state.get("allied_faction") is not None:
                raise CommandError(
                    f"Tribe {tribe} has an Ally — cannot Disperse"
                )
            if tribe_state.get("status") in (DISPERSED,
                                              DISPERSED_GATHERING):
                raise CommandError(
                    f"Tribe {tribe} is already Dispersed"
                )

        # Place Dispersed markers — "not yet Gathering" — §3.2.3
        for tribe in tribes_to_disperse:
            state["tribes"][tribe]["status"] = DISPERSED
            result["tribes_dispersed"].append(tribe)

    # ----- Step 2: Rally Checks — §3.2.3 -----
    # For each tribe just Dispersed, Arverni then Belgae roll
    # Determine which factions roll based on scenario
    rally_factions = _get_seize_rally_factions(scenario)

    for tribe in result["tribes_dispersed"]:
        tribe_rally_info = {"tribe": tribe, "rolls": []}
        for faction in rally_factions:
            roll_result = seize_rally_roll(state, faction)
            tribe_rally_info["rolls"].append(roll_result)
        result["rally_opportunities"].append(tribe_rally_info)

    # ----- Step 3: Forage — §3.2.3 -----
    forage = calculate_forage(state, region, result["tribes_dispersed"])
    if forage > 0:
        current = state["resources"].get(ROMANS, 0)
        state["resources"][ROMANS] = min(current + forage, MAX_RESOURCES)
    result["forage_resources"] = forage

    # ----- Step 4: Harassment info — §3.2.3 -----
    # Return harassment opportunities for the caller to execute
    result["harassment_opportunities"] = get_harassment_factions(
        state, region
    )

    refresh_all_control(state)
    return result


def _get_seize_rally_factions(scenario):
    """Get factions that roll for Seize-triggered Rally.

    Base game (§3.2.3): Arverni then Belgae.
    Ariovistus (A3.2.3): Arverni execute free Rally per A6.2.1
    (the Rally is different in Ariovistus but the rolling factions
    still include Arverni; Belgae still roll per base rules).

    Args:
        scenario: Scenario identifier.

    Returns:
        Tuple of faction constants in roll order.
    """
    # §3.2.3: "Arverni then the Belgae each roll a die"
    # A3.2.3 modifies how Arverni execute the Rally but doesn't
    # remove the roll mechanic
    return (ARVERNI, BELGAE)
