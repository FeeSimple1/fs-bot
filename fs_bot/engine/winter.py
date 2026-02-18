"""Winter module — Full Winter Round execution per §6.0 / A6.0.

Implements all six Winter phases in order:
1. Victory Phase (§6.1 / A6.1)
2. Germans Phase (§6.2, base game only)
3. Quarters Phase (§6.3 / A6.3)
4. Harvest Phase (§6.4 / A6.4)
5. Senate Phase (§6.5 / A6.5)
6. Spring Phase (§6.6 / A6.6)

Reference:
  §6.0-§6.6  Base game Winter Round
  A6.0-A6.6  Ariovistus Winter Round
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    FACTIONS, GALLIC_FACTIONS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    FLIPPABLE_PIECES, MOBILE_PIECES,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Leaders
    CAESAR, VERCINGETORIX, AMBIORIX, ARIOVISTUS_LEADER,
    DIVICIACUS, BODUOGNATUS, SUCCESSOR,
    BASE_LEADERS, ARIOVISTUS_LEADERS,
    LEADER_FACTION,
    # Scenarios
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    SCENARIO_GALLIC_WAR,
    # Regions
    ALL_REGIONS,
    PROVINCIA, CISALPINA,
    SUGAMBRI, UBII,
    GERMANIA_REGIONS,
    # Legions
    LEGIONS_ROWS, LEGIONS_PER_ROW,
    LEGIONS_ROW_BOTTOM, LEGIONS_ROW_MIDDLE, LEGIONS_ROW_TOP,
    # Senate
    UPROAR, INTRIGUE, ADULATION,
    SENATE_POSITIONS, SENATE_AUXILIA,
    ARIOVISTUS_SENATE_MAX_LEGIONS,
    SENATE_SHIFT_LOW_THRESHOLD, SENATE_SHIFT_HIGH_THRESHOLD,
    # Quarters
    QUARTERS_COST_WITH_ALLY, QUARTERS_COST_WITHOUT_ALLY,
    QUARTERS_DEVASTATED_MULTIPLIER,
    QUARTERS_FREE_PIECES_PER_ALLY, QUARTERS_FREE_PIECES_PER_FORT,
    GERMAN_QUARTERS_SUGAMBRI_THRESHOLD,
    DESERTION_ROLL_THRESHOLD,
    # Harvest
    AEDUI_RIVER_TOLLS,
    # Victory
    MAX_RESOURCES,
    # Home regions
    ROMAN_HOME_REGIONS,
    ARVERNI_HOME_REGIONS_BASE, ARVERNI_HOME_REGIONS_ARIOVISTUS,
    AEDUI_HOME_REGIONS, BELGAE_HOME_REGIONS,
    GERMAN_HOME_REGIONS_BASE,
    # Markers
    MARKER_DEVASTATED, MARKER_DISPERSED, MARKER_DISPERSED_GATHERING,
    MARKER_SCOUTED, MARKER_INTIMIDATED, MARKER_RAZED,
    # Eligibility
    ELIGIBLE,
    # Die
    DIE_MIN, DIE_MAX,
    # Control
    NO_CONTROL, GERMANIC_CONTROL,
    FACTION_CONTROL,
)
from fs_bot.board.pieces import (
    place_piece, remove_piece, move_piece, flip_piece,
    count_pieces, count_pieces_by_state, get_available,
    get_leader_in_region, find_leader, PieceError,
    _count_on_legions_track,
)
from fs_bot.board.control import (
    refresh_all_control, is_controlled_by, get_controlled_regions,
)
from fs_bot.map.map_data import (
    get_adjacent, get_playable_regions, get_tribes_in_region,
    ALL_REGION_DATA, get_region_group,
)
from fs_bot.commands.common import _is_devastated, _is_intimidated
from fs_bot.engine.victory import (
    check_any_victory, check_victory, calculate_victory_score,
    calculate_victory_margin, determine_final_ranking,
)
from fs_bot.engine.germans_battle import germans_phase_battle
from fs_bot.commands.rally import germans_phase_rally
from fs_bot.commands.march import germans_phase_march
from fs_bot.commands.raid import (
    get_germans_phase_raid_targets, germans_phase_raid_region,
)


# Senate position index mapping for shift logic
_SENATE_INDEX = {pos: i for i, pos in enumerate(SENATE_POSITIONS)}

# Row-to-senate mapping for Legion placement: §6.5.2
# Legions on same row as Senate or above are placed into Provincia.
# Bottom = below Adulation, Middle = Adulation, Top = Intrigue
_ROW_SENATE_MAP = {
    LEGIONS_ROW_BOTTOM: None,      # Below Adulation — never at Senate level
    LEGIONS_ROW_MIDDLE: ADULATION,  # At Adulation level
    LEGIONS_ROW_TOP: INTRIGUE,      # At Intrigue level
}

# Senate rows at or above each position
# If Senate is at Uproar (index 0): rows at or above = Top only (Intrigue)
# If Senate is at Intrigue (index 1): rows at or above = Top (Intrigue)
# If Senate is at Adulation (index 2): rows at or above = Middle + Top
_ROWS_AT_OR_ABOVE_SENATE = {
    UPROAR: (LEGIONS_ROW_TOP,),
    INTRIGUE: (LEGIONS_ROW_TOP,),
    ADULATION: (LEGIONS_ROW_MIDDLE, LEGIONS_ROW_TOP),
}


# ============================================================================
# PHASE 1: VICTORY PHASE (§6.1, A6.1)
# ============================================================================

def victory_phase(state, is_final=False):
    """Execute the Victory Phase — §6.1 / A6.1.

    Check if any faction meets its victory condition. If the game ends,
    return the winner. If it's the final Winter and no one wins, determine
    ranking by margins.

    Args:
        state: Game state dict.
        is_final: True if this is the final Winter card (§2.4.1).

    Returns:
        Dict with:
            "game_over": bool
            "winner": faction or None
            "rankings": list of (faction, margin) or None
    """
    result = {
        "game_over": False,
        "winner": None,
        "rankings": None,
    }

    # Check victory — §6.1
    winner = check_any_victory(state)
    if winner is not None:
        result["game_over"] = True
        result["winner"] = winner
        result["rankings"] = determine_final_ranking(state)
        return result

    # Final Winter with no victor — §7.3
    if is_final:
        result["game_over"] = True
        rankings = determine_final_ranking(state)
        result["rankings"] = rankings
        if rankings:
            result["winner"] = rankings[0][0]
        return result

    return result


# ============================================================================
# PHASE 2: GERMANS PHASE (§6.2, base game only)
# ============================================================================

def germans_phase(state):
    """Execute the Germans Phase — §6.2.

    Base game only. Ariovistus skips this entirely.
    Orchestrates: Rally, March, Raid, Battle with Ambush.

    Args:
        state: Game state dict. Modified in place.

    Returns:
        Dict with phase results, or None if skipped.
    """
    scenario = state["scenario"]
    if scenario in ARIOVISTUS_SCENARIOS:
        return None

    result = {
        "rally": None,
        "march": None,
        "raid": None,
        "battle": None,
    }

    # §6.2.1 Rally
    result["rally"] = germans_phase_rally(state)

    # §6.2.2 March
    result["march"] = germans_phase_march(state)

    # §6.2.3 Raid
    result["raid"] = _germans_phase_raid_all(state)

    # §6.2.4 Battle with Ambush
    result["battle"] = germans_phase_battle(state)

    refresh_all_control(state)
    return result


def _germans_phase_raid_all(state):
    """Orchestrate German Phase Raid across all regions — §6.2.3.

    Raid with as many Germanic Warbands as able, against factions
    that have more than 0 Resources (and no Fort or Citadel),
    only until they reach 0 Resources.
    Raid against player before Non-player factions.

    Returns:
        Dict with combined raid results.
    """
    rng = state["rng"]
    result = {
        "raids": [],
        "total_stolen": {},
    }

    # Find all regions where Germans have Hidden Warbands
    raid_regions = []
    for region in state["spaces"]:
        hidden = count_pieces_by_state(
            state, region, GERMANS, WARBAND, HIDDEN
        )
        if hidden > 0:
            targets = get_germans_phase_raid_targets(state, region)
            if targets:
                raid_regions.append(region)

    # Raid in random order
    rng.shuffle(raid_regions)

    for region in raid_regions:
        # Re-check: still have Hidden Warbands and valid targets?
        hidden = count_pieces_by_state(
            state, region, GERMANS, WARBAND, HIDDEN
        )
        if hidden < 1:
            continue
        targets = get_germans_phase_raid_targets(state, region)
        if not targets:
            continue

        raid_result = germans_phase_raid_region(state, region)
        result["raids"].append(raid_result)
        for target, amount in raid_result.get("resources_stolen", {}).items():
            result["total_stolen"][target] = (
                result["total_stolen"].get(target, 0) + amount
            )

    return result


# ============================================================================
# PHASE 3: QUARTERS PHASE (§6.3, A6.3)
# ============================================================================

def quarters_phase(state, relocations=None):
    """Execute the Quarters Phase — §6.3 / A6.3.

    Each faction relocates its Forces, then forced die rolls for
    pieces in Devastated regions.

    The relocations parameter accepts pre-made player decisions.
    For Phase 4, this implements the forced/mechanical parts:
    - German relocation to Germania (§6.3.1)
    - Warband die rolls in Devastated regions (§6.3.2)
    - Player-choice relocations can be passed as parameters.

    Args:
        state: Game state dict. Modified in place.
        relocations: Optional dict of pre-made relocation decisions,
            keyed by faction. Each value is a list of
            (piece_type, from_region, to_region, count) tuples.

    Returns:
        Dict with phase results.
    """
    scenario = state["scenario"]
    if relocations is None:
        relocations = {}

    result = {
        "german_relocation": None,
        "gallic_relocations": {},
        "gallic_desertion": {},
        "roman_relocation": None,
        "roman_quartering": None,
    }

    if scenario in BASE_SCENARIOS:
        # Base game order: Germans, Belgae, Aedui, Arverni, Romans — §6.3
        result["german_relocation"] = _quarters_german_relocation(state)
        for faction in (BELGAE, AEDUI, ARVERNI):
            _apply_relocations(state, faction, relocations.get(faction, []))
            result["gallic_desertion"][faction] = _quarters_gallic_desertion(
                state, faction
            )
        _apply_relocations(state, ROMANS, relocations.get(ROMANS, []))
        result["roman_quartering"] = _quarters_roman_pay_or_roll(
            state, relocations.get(ROMANS + "_quartering", {})
        )
    else:
        # Ariovistus order: Belgae, Aedui, Germans, Romans — A6.3
        # A6.3.1: Arverni do not relocate
        for faction in (BELGAE, AEDUI):
            _apply_relocations(state, faction, relocations.get(faction, []))
            result["gallic_desertion"][faction] = _quarters_gallic_desertion(
                state, faction
            )
        # A6.3.2: Germans treated like Gauls in Ariovistus
        _apply_relocations(state, GERMANS, relocations.get(GERMANS, []))
        result["gallic_desertion"][GERMANS] = _quarters_gallic_desertion(
            state, GERMANS
        )
        # Romans unchanged — A6.3.3
        _apply_relocations(state, ROMANS, relocations.get(ROMANS, []))
        result["roman_quartering"] = _quarters_roman_pay_or_roll(
            state, relocations.get(ROMANS + "_quartering", {})
        )

    refresh_all_control(state)
    return result


def _quarters_german_relocation(state):
    """Relocate Germanic Warbands from Devastated regions — §6.3.1.

    Base game only. All Germanic Warbands in Devastated regions without
    German Allies and outside Germania relocate to Sugambri (1-3) or
    Ubii (4-6).

    Returns:
        Dict with relocation results.
    """
    result = {
        "relocated": {},
        "destination": None,
        "die_roll": None,
    }

    # Find Warbands to relocate
    warbands_to_move = {}
    for region in state["spaces"]:
        if region in GERMANIA_REGIONS:
            continue
        if not _is_devastated(state, region):
            continue
        # Check for German Allies in region
        german_allies = count_pieces(state, region, GERMANS, ALLY)
        if german_allies > 0:
            continue
        # Count German Warbands
        wb_count = count_pieces(state, region, GERMANS, WARBAND)
        if wb_count > 0:
            warbands_to_move[region] = wb_count

    if not warbands_to_move:
        return result

    # Roll die: 1-3 Sugambri, 4-6 Ubii — §6.3.1
    roll = state["rng"].randint(DIE_MIN, DIE_MAX)
    result["die_roll"] = roll
    if roll <= GERMAN_QUARTERS_SUGAMBRI_THRESHOLD:
        dest = SUGAMBRI
    else:
        dest = UBII
    result["destination"] = dest

    for region, wb_count in warbands_to_move.items():
        # Move Hidden, then Revealed, then Scouted Warbands
        for ps in (HIDDEN, REVEALED, SCOUTED):
            ps_count = count_pieces_by_state(
                state, region, GERMANS, WARBAND, ps
            )
            if ps_count > 0:
                move_piece(
                    state, region, dest, GERMANS, WARBAND,
                    count=ps_count, piece_state=ps
                )
        result["relocated"][region] = wb_count

    return result


def _quarters_gallic_desertion(state, faction):
    """Roll for Warbands in Devastated regions without Ally/Citadel — §6.3.2.

    For Gallic factions (and Germans in Ariovistus), roll a die for each
    Warband in Devastated regions where the faction has no Allied Tribe
    or Citadel (or Settlement for Germans in Ariovistus). Remove on 1-3.

    Returns:
        Dict with desertion results: {region: {"rolls": [...], "removed": int}}
    """
    result = {}
    scenario = state["scenario"]
    rng = state["rng"]

    for region in list(state["spaces"].keys()):
        if not _is_devastated(state, region):
            continue

        # Check for Ally, Citadel (and Settlement for Germans in Ariovistus)
        has_ally = count_pieces(state, region, faction, ALLY) > 0
        has_citadel = count_pieces(state, region, faction, CITADEL) > 0
        has_settlement = False
        if faction == GERMANS and scenario in ARIOVISTUS_SCENARIOS:
            has_settlement = count_pieces(
                state, region, faction, SETTLEMENT
            ) > 0

        if has_ally or has_citadel or has_settlement:
            continue

        wb_count = count_pieces(state, region, faction, WARBAND)
        if wb_count == 0:
            continue

        region_result = {"rolls": [], "removed": 0}

        # Roll for each Warband individually
        for _ in range(wb_count):
            # Re-check count (may have been removed)
            current = count_pieces(state, region, faction, WARBAND)
            if current == 0:
                break
            roll = rng.randint(DIE_MIN, DIE_MAX)
            region_result["rolls"].append(roll)
            if roll <= DESERTION_ROLL_THRESHOLD:
                remove_piece(state, region, faction, WARBAND)
                region_result["removed"] += 1

        if region_result["rolls"]:
            result[region] = region_result

    return result


def _apply_relocations(state, faction, relocation_list):
    """Apply pre-made relocation decisions for a faction.

    Each relocation is (piece_type, from_region, to_region, count).
    """
    for piece_type, from_region, to_region, count in relocation_list:
        if piece_type in FLIPPABLE_PIECES:
            # Move all states
            for ps in (HIDDEN, REVEALED, SCOUTED):
                ps_count = count_pieces_by_state(
                    state, from_region, faction, piece_type, ps
                )
                to_move = min(ps_count, count)
                if to_move > 0:
                    move_piece(
                        state, from_region, to_region, faction, piece_type,
                        count=to_move, piece_state=ps
                    )
                    count -= to_move
                if count <= 0:
                    break
        else:
            move_piece(
                state, from_region, to_region, faction, piece_type,
                count=count
            )


def _quarters_roman_pay_or_roll(state, quartering_decisions=None):
    """Execute Roman pay-or-roll for pieces outside Provincia — §6.3.3.

    For each Legion and Auxilia outside Provincia:
    - Pay to keep: 1 Resource with Roman Ally, 2 without, doubled if Devastated
    - One piece per Roman Ally and per Fort stays free
    - Or roll: remove on 1-3 (Legion to Fallen)

    quartering_decisions: Dict of {region: {"pay": int, "roll": int}}
    specifying how many to pay for and how many to roll for. If not
    provided, defaults to rolling for all (bot behavior).

    Returns:
        Dict with quartering results.
    """
    if quartering_decisions is None:
        quartering_decisions = {}

    result = {
        "payments": {},
        "rolls": {},
        "removed": {},
        "total_cost": 0,
    }
    rng = state["rng"]

    for region in list(state["spaces"].keys()):
        if region == PROVINCIA:
            continue

        # Count Roman pieces that need quartering
        legion_count = count_pieces(state, region, ROMANS, LEGION)
        auxilia_count = count_pieces(state, region, ROMANS, AUXILIA)
        total_pieces = legion_count + auxilia_count
        if total_pieces == 0:
            continue

        # Free pieces: one per Roman Ally + one per Fort — §6.3.3
        roman_allies = count_pieces(state, region, ROMANS, ALLY)
        roman_forts = count_pieces(state, region, ROMANS, FORT)
        free_pieces = (
            roman_allies * QUARTERS_FREE_PIECES_PER_ALLY
            + roman_forts * QUARTERS_FREE_PIECES_PER_FORT
        )
        pieces_needing_quarters = max(0, total_pieces - free_pieces)

        if pieces_needing_quarters == 0:
            continue

        # Cost per piece
        has_ally = roman_allies > 0
        base_cost = (
            QUARTERS_COST_WITH_ALLY if has_ally
            else QUARTERS_COST_WITHOUT_ALLY
        )
        if _is_devastated(state, region):
            base_cost *= QUARTERS_DEVASTATED_MULTIPLIER

        # Apply decisions or default to rolling
        decisions = quartering_decisions.get(region, {})
        pay_count = decisions.get("pay", 0)
        roll_count = decisions.get("roll", pieces_needing_quarters - pay_count)

        # Pay for pieces
        actual_paid = min(pay_count, pieces_needing_quarters)
        cost = actual_paid * base_cost
        available_resources = state["resources"].get(ROMANS, 0)
        # Can only pay if have enough Resources
        affordable = min(actual_paid, available_resources // base_cost) if base_cost > 0 else actual_paid
        cost = affordable * base_cost
        state["resources"][ROMANS] = state["resources"].get(ROMANS, 0) - cost
        result["payments"][region] = {"count": affordable, "cost": cost}
        result["total_cost"] += cost

        # Roll for remaining
        remaining_to_roll = pieces_needing_quarters - affordable
        if remaining_to_roll > 0:
            region_rolls = {"rolls": [], "removed_legions": 0,
                            "removed_auxilia": 0}
            # Roll for Legions first (more valuable), then Auxilia
            for _ in range(remaining_to_roll):
                roll = rng.randint(DIE_MIN, DIE_MAX)
                region_rolls["rolls"].append(roll)
                if roll <= DESERTION_ROLL_THRESHOLD:
                    # Remove a piece — Legion first, then Auxilia
                    current_legions = count_pieces(
                        state, region, ROMANS, LEGION
                    )
                    if current_legions > 0:
                        remove_piece(
                            state, region, ROMANS, LEGION, to_fallen=True
                        )
                        region_rolls["removed_legions"] += 1
                    else:
                        current_auxilia = count_pieces(
                            state, region, ROMANS, AUXILIA
                        )
                        if current_auxilia > 0:
                            remove_piece(state, region, ROMANS, AUXILIA)
                            region_rolls["removed_auxilia"] += 1

            result["rolls"][region] = region_rolls
            result["removed"][region] = (
                region_rolls["removed_legions"]
                + region_rolls["removed_auxilia"]
            )

    return result


# ============================================================================
# PHASE 4: HARVEST PHASE (§6.4, A6.4)
# ============================================================================

def harvest_phase(state):
    """Execute the Harvest Phase — §6.4 / A6.4.

    Add Resources to each faction, capped at MAX_RESOURCES (45).

    Returns:
        Dict with earnings per faction.
    """
    scenario = state["scenario"]
    result = {}

    # §6.4.1 Roman Earnings: Resources += victory score
    roman_score = calculate_victory_score(state, ROMANS)
    roman_earn = roman_score
    _add_resources(state, ROMANS, roman_earn)
    result[ROMANS] = roman_earn

    # §6.4.2 Gallic Earnings: 2x (Allied Tribes + Citadels)
    for faction in GALLIC_FACTIONS:
        if faction == ARVERNI and scenario in ARIOVISTUS_SCENARIOS:
            # A6.4.2: Arverni do not earn Resources in Ariovistus
            result[faction] = 0
            continue
        allies = 0
        for tribe_info in state["tribes"].values():
            if tribe_info.get("allied_faction") == faction:
                allies += 1
        citadels = 0
        for region_data in state["spaces"].values():
            f_pieces = region_data.get("pieces", {}).get(faction, {})
            citadels += f_pieces.get(CITADEL, 0)
        earn = 2 * (allies + citadels)
        _add_resources(state, faction, earn)
        result[faction] = earn

    # §6.4.3 River Tolls: Aedui +4
    _add_resources(state, AEDUI, AEDUI_RIVER_TOLLS)
    result[AEDUI] = result.get(AEDUI, 0) + AEDUI_RIVER_TOLLS

    # A6.4.4 Germanic Earnings (Ariovistus only): 2x (Allies + Settlements)
    if scenario in ARIOVISTUS_SCENARIOS:
        german_allies = 0
        for tribe_info in state["tribes"].values():
            if tribe_info.get("allied_faction") == GERMANS:
                german_allies += 1
        german_settlements = 0
        for region_data in state["spaces"].values():
            f_pieces = region_data.get("pieces", {}).get(GERMANS, {})
            german_settlements += f_pieces.get(SETTLEMENT, 0)
        german_earn = 2 * (german_allies + german_settlements)
        _add_resources(state, GERMANS, german_earn)
        result[GERMANS] = german_earn

    return result


def _add_resources(state, faction, amount):
    """Add Resources to a faction, capping at MAX_RESOURCES."""
    current = state["resources"].get(faction, 0)
    state["resources"][faction] = min(current + amount, MAX_RESOURCES)


# ============================================================================
# PHASE 5: SENATE PHASE (§6.5, A6.5)
# ============================================================================

def senate_phase(state, first_senate_after_interlude=False):
    """Execute the Senate Phase — §6.5 / A6.5.

    Shift Senate marker, move Legions from Fallen to track and place
    into Provincia, place Auxilia if Leader in Provincia.

    Args:
        state: Game state dict. Modified in place.
        first_senate_after_interlude: True if this is the first Senate
            Phase after the Gallic War Interlude (A6.5.1).

    Returns:
        Dict with phase results.
    """
    scenario = state["scenario"]
    result = {
        "marker_shift": None,
        "legions_from_fallen": 0,
        "legions_to_track": 0,
        "legions_placed": 0,
        "auxilia_placed": 0,
    }

    # §6.5.1 Senate Marker shift
    result["marker_shift"] = _senate_marker_shift(
        state, first_senate_after_interlude
    )

    # §6.5.2 Legions
    legions_result = _senate_legions(state)
    result.update(legions_result)

    # §6.5.3 Auxilia
    result["auxilia_placed"] = _senate_auxilia(state)

    refresh_all_control(state)
    return result


def _senate_marker_shift(state, first_senate_after_interlude=False):
    """Shift the Senate marker per §6.5.1 / A6.5.1.

    Returns:
        Dict describing the shift.
    """
    scenario = state["scenario"]
    result = {
        "old_position": state["senate"]["position"],
        "old_firm": state["senate"]["firm"],
        "new_position": state["senate"]["position"],
        "new_firm": state["senate"]["firm"],
        "shifted": False,
        "reason": None,
    }

    # A6.5.1: In Gallic War scenario, skip shift during first Senate
    # after Interlude
    if (scenario == SCENARIO_GALLIC_WAR
            and first_senate_after_interlude):
        result["reason"] = "First Senate Phase after Interlude — no shift"
        return result

    # Determine shift direction based on Roman victory score
    roman_score = calculate_victory_score(state, ROMANS)
    fallen = state.get("fallen_legions", 0)

    if roman_score < SENATE_SHIFT_LOW_THRESHOLD:
        # Shift toward Uproar
        direction = "up"
    elif roman_score <= SENATE_SHIFT_HIGH_THRESHOLD:
        # Shift toward Intrigue
        current_pos = _SENATE_INDEX[state["senate"]["position"]]
        intrigue_pos = _SENATE_INDEX[INTRIGUE]
        if current_pos < intrigue_pos:
            direction = "down"  # below Intrigue, move toward it
        elif current_pos > intrigue_pos:
            direction = "up"  # above Intrigue, move toward it
        else:
            direction = None  # already at Intrigue
    else:
        # Above 12: shift toward Adulation
        direction = "down"

    # EXCEPTION: Do not shift down (toward Adulation, including to Intrigue
    # from Uproar) if any Legions are in the Fallen box — §6.5.1
    if direction == "down" and fallen > 0:
        result["reason"] = "Fallen Legions prevent downward shift"
        return result

    if direction is None:
        result["reason"] = "Already at target position"
        return result

    # Apply the shift
    _apply_senate_shift(state, direction)

    result["new_position"] = state["senate"]["position"]
    result["new_firm"] = state["senate"]["firm"]
    result["shifted"] = True
    result["reason"] = f"Shifted {direction}"
    return result


def _apply_senate_shift(state, direction):
    """Apply a single Senate marker shift.

    Per §6.5.1:
    - Any shift toward Uproar when already at Uproar: flip to Firm
    - Any shift toward Adulation when already at Adulation: flip to Firm
    - Any other shift when Firm: flip back to normal (without moving)
    """
    position = state["senate"]["position"]
    is_firm = state["senate"]["firm"]
    pos_idx = _SENATE_INDEX[position]

    if direction == "up":
        # Toward Uproar (index 0)
        if pos_idx == 0:
            # Already at Uproar — flip to Firm if not already
            if not is_firm:
                state["senate"]["firm"] = True
            # If already Firm, do nothing (already at extreme + Firm)
        elif is_firm:
            # Firm: flip back to normal without moving
            state["senate"]["firm"] = False
        else:
            # Move up one position
            state["senate"]["position"] = SENATE_POSITIONS[pos_idx - 1]
    elif direction == "down":
        # Toward Adulation (index 2)
        if pos_idx == len(SENATE_POSITIONS) - 1:
            # Already at Adulation — flip to Firm if not already
            if not is_firm:
                state["senate"]["firm"] = True
        elif is_firm:
            # Firm: flip back to normal without moving
            state["senate"]["firm"] = False
        else:
            # Move down one position
            state["senate"]["position"] = SENATE_POSITIONS[pos_idx + 1]


def _senate_legions(state):
    """Move Legions from Fallen to track and place into Provincia — §6.5.2.

    Half (rounded down) of Fallen stay unavailable. Move rest to track
    (fill lowest rows first). Then place into Provincia all Legions on
    same row as Senate marker or above.

    A6.5.2: Max 2 Legions placed into Provincia in Ariovistus.

    Returns:
        Dict with results.
    """
    scenario = state["scenario"]
    result = {
        "legions_from_fallen": 0,
        "legions_to_track": 0,
        "legions_placed": 0,
        "half_stay_fallen": 0,
    }

    # Step 1: Move half of Fallen Legions to track — §6.5.2
    fallen = state.get("fallen_legions", 0)
    if fallen > 0:
        stay = fallen // 2
        to_move = fallen - stay
        result["half_stay_fallen"] = stay
        result["legions_from_fallen"] = to_move
        result["legions_to_track"] = to_move

        state["fallen_legions"] = stay
        remaining = to_move
        for row in LEGIONS_ROWS:  # Bottom, Middle, Top
            space_on_row = LEGIONS_PER_ROW - state["legions_track"].get(row, 0)
            add = min(space_on_row, remaining)
            state["legions_track"][row] = (
                state["legions_track"].get(row, 0) + add
            )
            remaining -= add
            if remaining == 0:
                break

    # Step 2: Place into Provincia all Legions at or above Senate row
    senate_pos = state["senate"]["position"]
    rows_to_place = _ROWS_AT_OR_ABOVE_SENATE.get(senate_pos, ())

    total_to_place = 0
    for row in rows_to_place:
        total_to_place += state["legions_track"].get(row, 0)

    # A6.5.2: Max 2 Legions in Ariovistus
    if scenario in ARIOVISTUS_SCENARIOS:
        total_to_place = min(total_to_place, ARIOVISTUS_SENATE_MAX_LEGIONS)

    if total_to_place > 0:
        # Remove from track (top rows first) and place in Provincia
        # We manually manage the track and use direct placement to avoid
        # conflicts with place_piece(from_legions_track=True) which takes
        # from top rows unconditionally.
        remaining = total_to_place
        for row in reversed(list(rows_to_place)):
            on_row = state["legions_track"].get(row, 0)
            take = min(on_row, remaining)
            if take > 0:
                state["legions_track"][row] -= take
                remaining -= take
            if remaining == 0:
                break

        # Place directly into Provincia (track already decremented)
        from fs_bot.board.pieces import _ensure_faction_pieces_structure
        _ensure_faction_pieces_structure(state, PROVINCIA, ROMANS)
        f_pieces = state["spaces"][PROVINCIA]["pieces"][ROMANS]
        f_pieces[LEGION] = f_pieces.get(LEGION, 0) + total_to_place
        result["legions_placed"] = total_to_place

    return result


def _senate_auxilia(state):
    """Place Auxilia into Provincia if Roman Leader there — §6.5.3.

    If the Roman Leader is in Provincia, place Auxilia from Available:
    3 if Uproar, 4 if Intrigue, 5 if Adulation.

    Returns:
        Integer count of Auxilia placed.
    """
    leader = get_leader_in_region(state, PROVINCIA, ROMANS)
    if leader is None:
        return 0

    senate_pos = state["senate"]["position"]
    count_to_place = SENATE_AUXILIA.get(senate_pos, 0)

    available = get_available(state, ROMANS, AUXILIA)
    actual = min(count_to_place, available)

    if actual > 0:
        place_piece(state, PROVINCIA, ROMANS, AUXILIA, count=actual)

    return actual


# ============================================================================
# PHASE 6: SPRING PHASE (§6.6, A6.6)
# ============================================================================

def spring_phase(state):
    """Execute the Spring Phase — §6.6 / A6.6.

    Prepare for the coming year:
    - Place Successor Leaders from Available
    - Move remaining Fallen Legions to track
    - Remove Scouted markers, flip Revealed to Hidden
    - Remove Devastated markers
    - Cycle Dispersed markers (Dispersed-Gathering→remove, Dispersed→Dispersed-Gathering)
    - Mark all factions Eligible
    - Ariovistus: remove Intimidated markers

    Returns:
        Dict with phase results.
    """
    scenario = state["scenario"]
    result = {
        "successors_placed": [],
        "fallen_to_track": 0,
        "scouted_removed": 0,
        "pieces_flipped_hidden": 0,
        "devastated_removed": 0,
        "dispersed_gathering_removed": 0,
        "dispersed_flipped": 0,
        "intimidated_removed": 0,
    }

    # Place Successor Leaders from Available — §6.6
    result["successors_placed"] = _place_successor_leaders(state)

    # Move remaining Fallen Legions to track — §6.6
    fallen = state.get("fallen_legions", 0)
    if fallen > 0:
        remaining = fallen
        for row in LEGIONS_ROWS:
            space_on_row = LEGIONS_PER_ROW - state["legions_track"].get(row, 0)
            add = min(space_on_row, remaining)
            state["legions_track"][row] = (
                state["legions_track"].get(row, 0) + add
            )
            remaining -= add
            if remaining == 0:
                break
        state["fallen_legions"] = remaining
        result["fallen_to_track"] = fallen - remaining

    # Remove Scouted markers, flip Revealed to Hidden — §6.6
    for region in state["spaces"]:
        for faction in FACTIONS:
            # Scouted → Revealed (removing Scouted marker) — §4.2.2
            for pt in FLIPPABLE_PIECES:
                scouted = count_pieces_by_state(
                    state, region, faction, pt, SCOUTED
                )
                if scouted > 0:
                    flip_piece(
                        state, region, faction, pt, count=scouted,
                        from_state=SCOUTED, to_state=HIDDEN
                    )
                    # Note: flip_piece converts SCOUTED→HIDDEN into SCOUTED→REVEALED
                    # per §1.4.3. So after this, pieces are REVEALED.
                    result["scouted_removed"] += scouted

            # Now flip all Revealed to Hidden — §6.6
            for pt in FLIPPABLE_PIECES:
                revealed = count_pieces_by_state(
                    state, region, faction, pt, REVEALED
                )
                if revealed > 0:
                    flip_piece(
                        state, region, faction, pt, count=revealed,
                        from_state=REVEALED, to_state=HIDDEN
                    )
                    result["pieces_flipped_hidden"] += revealed

    # Remove Devastated markers — §6.6
    markers = state.get("markers", {})
    for region in list(markers.keys()):
        region_markers = markers.get(region, {})
        if isinstance(region_markers, dict):
            if MARKER_DEVASTATED in region_markers:
                del region_markers[MARKER_DEVASTATED]
                result["devastated_removed"] += 1
        elif isinstance(region_markers, set):
            if MARKER_DEVASTATED in region_markers:
                region_markers.discard(MARKER_DEVASTATED)
                result["devastated_removed"] += 1

    # Dispersed cycling — §6.6
    # 1. Remove all Dispersed-Gathering markers (only)
    # 2. Flip all Dispersed to Dispersed-Gathering
    # (Do NOT remove or flip Razed marker from Sacking Event — §6.6)
    for tribe_name, tribe_info in state["tribes"].items():
        status = tribe_info.get("status")
        if status == MARKER_DISPERSED_GATHERING:
            # Remove Dispersed-Gathering → tribe becomes Subdued
            tribe_info["status"] = None
            tribe_info["allied_faction"] = None
            result["dispersed_gathering_removed"] += 1
        elif status == MARKER_DISPERSED:
            # Flip Dispersed → Dispersed-Gathering
            tribe_info["status"] = MARKER_DISPERSED_GATHERING
            result["dispersed_flipped"] += 1
        # Razed: do not touch — §6.6

    # Ariovistus: Remove Intimidated markers — A6.6
    if scenario in ARIOVISTUS_SCENARIOS:
        for region in list(markers.keys()):
            region_markers = markers.get(region, {})
            if isinstance(region_markers, dict):
                if MARKER_INTIMIDATED in region_markers:
                    del region_markers[MARKER_INTIMIDATED]
                    result["intimidated_removed"] += 1
            elif isinstance(region_markers, set):
                if MARKER_INTIMIDATED in region_markers:
                    region_markers.discard(MARKER_INTIMIDATED)
                    result["intimidated_removed"] += 1

    # Mark all factions Eligible — §6.6
    for faction in FACTIONS:
        state["eligibility"][faction] = ELIGIBLE

    refresh_all_control(state)
    return result


def _place_successor_leaders(state):
    """Place Successor Leaders from Available to map — §6.6.

    Place where the faction has a piece or a Home Region.

    Returns:
        List of (faction, region) tuples for placed leaders.
    """
    scenario = state["scenario"]
    result = []

    if scenario in ARIOVISTUS_SCENARIOS:
        leaders = ARIOVISTUS_LEADERS
    else:
        leaders = BASE_LEADERS

    for leader_name in leaders:
        faction = LEADER_FACTION[leader_name]
        available = get_available(state, faction, LEADER)
        if available < 1:
            continue

        # Check if leader is already on map
        on_map = find_leader(state, faction)
        if on_map is not None:
            continue

        # Diviciacus has no Successor — A1.4 NOTE in A6.6
        if leader_name == DIVICIACUS:
            continue

        # Find placement region: where faction has a piece, or Home Region
        placement = _find_successor_placement(state, faction)
        if placement is not None:
            place_piece(
                state, placement, faction, LEADER,
                leader_name=SUCCESSOR
            )
            result.append((faction, placement))

    return result


def _find_successor_placement(state, faction):
    """Find where to place a Successor Leader — §6.6.

    Place where faction has a piece or a Home Region "Rally" or
    "Recruit" symbol.

    Returns:
        Region name, or None if no valid placement.
    """
    scenario = state["scenario"]

    # First check Home Regions
    if faction == ROMANS:
        home = ROMAN_HOME_REGIONS
    elif faction == ARVERNI:
        if scenario in ARIOVISTUS_SCENARIOS:
            home = ARVERNI_HOME_REGIONS_ARIOVISTUS
        else:
            home = ARVERNI_HOME_REGIONS_BASE
    elif faction == AEDUI:
        home = AEDUI_HOME_REGIONS
    elif faction == BELGAE:
        home = BELGAE_HOME_REGIONS
    elif faction == GERMANS:
        home = GERMAN_HOME_REGIONS_BASE
    else:
        home = ()

    # Check home regions first
    for region in home:
        rd = ALL_REGION_DATA.get(region)
        if rd and rd.is_playable(scenario, state.get("capabilities")):
            return region

    # Then check regions where faction has pieces
    for region in state["spaces"]:
        rd = ALL_REGION_DATA.get(region)
        if rd and not rd.is_playable(scenario, state.get("capabilities")):
            continue
        if count_pieces(state, region, faction) > 0:
            return region

    return None


# ============================================================================
# MAIN: RUN WINTER ROUND
# ============================================================================

def run_winter_round(state, is_final=False,
                     first_senate_after_interlude=False,
                     relocations=None):
    """Execute the full Winter Round per §6.0 / A6.0.

    Calls each phase in order. Stops early if Victory Phase ends the game.

    Args:
        state: Game state dict. Modified in place.
        is_final: True if this is the final Winter card (§2.4.1).
        first_senate_after_interlude: For Gallic War scenario (A6.5.1).
        relocations: Optional dict of relocation decisions for Quarters.

    Returns:
        Dict with results from each phase.
    """
    scenario = state["scenario"]
    state["winter_count"] = state.get("winter_count", 0) + 1

    result = {
        "winter_count": state["winter_count"],
        "phases": {},
    }

    # Phase 1: Victory
    victory_result = victory_phase(state, is_final=is_final)
    result["phases"]["victory"] = victory_result
    if victory_result["game_over"]:
        return result

    # Phase 2: Germans Phase (base game only)
    if scenario in BASE_SCENARIOS:
        result["phases"]["germans"] = germans_phase(state)

    # Phase 3: Quarters
    result["phases"]["quarters"] = quarters_phase(
        state, relocations=relocations
    )

    # Phase 4: Harvest
    result["phases"]["harvest"] = harvest_phase(state)

    # Phase 5: Senate
    result["phases"]["senate"] = senate_phase(
        state,
        first_senate_after_interlude=first_senate_after_interlude,
    )

    # Phase 6: Spring
    result["phases"]["spring"] = spring_phase(state)

    return result
