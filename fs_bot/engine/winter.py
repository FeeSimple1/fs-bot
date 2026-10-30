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

from functools import wraps

from fs_bot.engine import action_windows
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
# The printed board aligns Top with Uproar, Middle with Intrigue, and
# Bottom with Adulation. See docs/reviews/vassal-module-2026-10-20.md for the image
# and coordinate evidence; the legacy comments in rules_consts.py are
# not the board geometry (that file remains read-only).
_ROW_SENATE_MAP = {
    LEGIONS_ROW_BOTTOM: ADULATION,
    LEGIONS_ROW_MIDDLE: INTRIGUE,
    LEGIONS_ROW_TOP: UPROAR,
}

# Senate rows at or above each position — §6.5.2
# "Place into Provincia all Legions on same row as Senate or above."
# Keep rows in bottom-to-top order: the placement loop reverses this
# order when taking Legions, including the Ariovistus lower-row limit.
_ROWS_AT_OR_ABOVE_SENATE = {
    UPROAR: (LEGIONS_ROW_TOP,),
    INTRIGUE: (LEGIONS_ROW_MIDDLE, LEGIONS_ROW_TOP),
    ADULATION: (LEGIONS_ROW_BOTTOM, LEGIONS_ROW_MIDDLE, LEGIONS_ROW_TOP),
}


def _winter_scope(function):
    @wraps(function)
    def wrapped(state, *args, **kwargs):
        with action_windows.scope(state, phase='winter'):
            return function(state, *args, **kwargs)
    return wrapped


# ============================================================================
# PHASE 1: VICTORY PHASE (§6.1, A6.1)
# ============================================================================

def _optimates_remove_all_legions(state):
    """Remove every Legion on the map to the Legions track (Card 20)."""
    from fs_bot.board.pieces import count_pieces, remove_piece
    for region in list(state["spaces"].keys()):
        n = count_pieces(state, region, ROMANS, LEGION)
        if n > 0:
            remove_piece(state, region, ROMANS, LEGION, count=n,
                         to_available=False, to_track=True)


@_winter_scope
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

    # §6.1 ends the game now if this check succeeds. No later window can
    # alter that completed result.
    action_windows.window(state, 'winter_victory')
    # Check victory — §6.1
    winner = check_any_victory(state)
    if winner is not None:
        result["game_over"] = True
        result["winner"] = winner
        result["rankings"] = determine_final_ranking(state)
        return result

    # Card 20 Optimates: on the game's 2nd and each later Victory Phase,
    # if Roman victory exceeds 12 (red Subdued+Dispersed+Allies marker at
    # 13+), first remove all Legions to the Legions track, then end the
    # game and determine victory.
    if (state.get("event_modifiers", {}).get("optimates_active")
            and state.get("winter_count", 0) >= 2):
        from fs_bot.engine.victory import calculate_victory_score
        if calculate_victory_score(state, ROMANS) > 12:
            _optimates_remove_all_legions(state)
            result["game_over"] = True
            result["optimates_end"] = True
            rankings = determine_final_ranking(state)
            result["rankings"] = rankings
            if rankings:
                result["winner"] = rankings[0][0]
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

@_winter_scope
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
    action_windows.window(state, 'winter_germans_command', command='Rally')
    result["rally"] = germans_phase_rally(state)

    # §6.2.2 March
    action_windows.window(state, 'winter_germans_command', command='March')
    result["march"] = germans_phase_march(state)

    # §6.2.3 Raid
    action_windows.window(state, 'winter_germans_command', command='Raid')
    result["raid"] = _germans_phase_raid_all(state)

    # §6.2.4 Battle with Ambush
    action_windows.window(state, 'winter_germans_command', command='Battle')
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
        action_windows.window(state, 'winter_germans_raid_region', region=region)
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

@_winter_scope
def quarters_phase(state, relocations=None):
    """Execute §6.3/A6.3 with stable agreements across plan/execute."""
    from fs_bot.engine.quarters import agreement_cache
    with agreement_cache(state):
        return _quarters_phase(state, relocations)


def _quarters_phase(state, relocations=None):
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
    from fs_bot.engine.quarters import (
        QuartersError, quarters_factions, validate_quarters_plan,
    )
    from fs_bot.engine.agent import consult_agent
    scenario = state["scenario"]
    action_windows.window(state, 'winter_quarters')
    if relocations is not None:
        errors = validate_quarters_plan(state, relocations)
        if errors:
            raise QuartersError("; ".join(errors))
    result = {
        "german_relocation": None, "gallic_relocations": {},
        "gallic_desertion": {}, "roman_relocation": None,
        "roman_quartering": None,
    }
    if scenario in BASE_SCENARIOS:
        action_windows.window(state, 'winter_german_relocation')
        result["german_relocation"] = _quarters_german_relocation(state)
    for faction in quarters_factions(state):
        action_windows.window(state, 'winter_quarters_faction', faction=faction)
        errors = []
        while True:
            plan = relocations
            human_choice = False
            if plan is None:
                if faction not in state.get("non_player_factions", set()):
                    plan = consult_agent(state, faction, {
                        "kind": "quarters_plan", "request_type": "quarters_plan",
                        "faction": faction, "errors": errors})
                    human_choice = plan is not None
                if plan is None:
                    if faction == ROMANS:
                        from fs_bot.bots.roman_bot import build_np_winter_relocations
                        plan = build_np_winter_relocations(state)
                    else:
                        plan = {faction: []}
            # An explicitly supplied full-phase plan may include other
            # factions; a human response may choose only its own pieces.
            current_plan = plan
            if relocations is not None:
                # Previous factions have already moved; validating their
                # entries again would replay them against depleted origins.
                current_plan = {faction: plan.get(faction, [])}
                if faction == ROMANS and ROMANS + "_quartering" in plan:
                    current_plan[ROMANS + "_quartering"] = plan[ROMANS + "_quartering"]
            errors = validate_quarters_plan(state, current_plan, faction=faction)
            if not errors:
                try:
                    relocation_result = _apply_relocations(state, faction, plan.get(faction, []))
                    break
                except QuartersError as exc:
                    errors = [str(exc)]
            if (relocations is not None or not human_choice
                    or faction in state.get("non_player_factions", set())):
                raise QuartersError("; ".join(errors))
        if faction == ROMANS:
            result["roman_relocation"] = relocation_result['moves']
            action_windows.window(state, 'winter_roman_quartering')
            quartering = plan.get(ROMANS + "_quartering", {})
            if relocation_result['reconsider_quartering']:
                from fs_bot.engine.quarters import reconsider_quartering
                quartering = reconsider_quartering(state)
            result["roman_quartering"] = _quarters_roman_pay_or_roll(
                state, quartering)
        else:
            result["gallic_relocations"][faction] = plan.get(faction, [])
            action_windows.window(state, 'winter_gallic_desertion', faction=faction)
            result["gallic_desertion"][faction] = _quarters_gallic_desertion(state, faction)
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
        action_windows.window(state, 'winter_german_relocation_region',
                              region=region, destination=dest, roll=roll)
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

        action_windows.window(state, 'winter_desertion_region', faction=faction,
                              region=region)

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
        for index in range(wb_count):
            action_windows.window(state, 'winter_desertion_piece', faction=faction,
                                  region=region, index=index)
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
    """Validate and atomically apply one faction's §6.3 relocations."""
    from fs_bot.engine.quarters import apply_relocations
    return apply_relocations(state, faction, relocation_list)


def validate_quarters_plan(state, relocations, *, faction=None):
    """Public nonmutating frontend validator; see engine.quarters."""
    from fs_bot.engine.quarters import validate_quarters_plan as validate
    return validate(state, relocations, faction=faction)


def _quarters_roman_pay_or_roll(state, quartering_decisions=None):
    """Quarter exactly the pieces selected as free, paid, or rolled (§6.3.3).

    Legacy pay counts still work. ``free_pieces``/``pay_pieces`` entries
    identify (piece type, visibility or None, count), so a failed Auxilia
    roll cannot remove a Legion that was already protected by payment.
    """
    from fs_bot.engine.quarters import quartering_allocations
    allocations = quartering_allocations(state, quartering_decisions or {})
    result = {"payments": {}, "rolls": {}, "removed": {}, "total_cost": 0}
    for region, allocation in allocations.items():
        if not (allocation["paid"] or allocation["roll"]):
            continue
        action_windows.window(state, 'winter_roman_quartering_region', region=region)
        cost = allocation["cost"]
        state["resources"][ROMANS] -= cost
        result["payments"][region] = {"count": len(allocation["paid"]), "cost": cost}
        result["total_cost"] += cost
        if not allocation["roll"]:
            continue
        rolled = {"rolls": [], "pieces": [], "removed_legions": 0,
                  "removed_auxilia": 0}
        for index, (piece, visibility) in enumerate(allocation["roll"]):
            action_windows.window(state, 'winter_roman_quartering_piece',
                                  region=region, index=index)
            roll = state["rng"].randint(DIE_MIN, DIE_MAX)
            rolled["rolls"].append(roll)
            rolled["pieces"].append((piece, visibility))
            if roll <= DESERTION_ROLL_THRESHOLD:
                remove_piece(state, region, ROMANS, piece, count=1,
                             piece_state=visibility, to_fallen=(piece == LEGION))
                rolled["removed_legions" if piece == LEGION else "removed_auxilia"] += 1
        result["rolls"][region] = rolled
        result["removed"][region] = rolled["removed_legions"] + rolled["removed_auxilia"]
    return result


# ============================================================================
# PHASE 4: HARVEST PHASE (§6.4, A6.4)
# ============================================================================

@_winter_scope
def harvest_phase(state):
    """Execute the Harvest Phase — §6.4 / A6.4.

    A6.4.1: Ariovistus Roman earnings equal the Roman victory score,
    which A7.2 defines as Subdued + Dispersed + Roman Allies MINUS
    Settlements — the subtraction lives in calculate_victory_score.

    Add Resources to each faction, capped at MAX_RESOURCES (45).

    Returns:
        Dict with earnings per faction.
    """
    scenario = state["scenario"]
    result = {}

    # §6.4.1 Roman Earnings: Resources += victory score
    action_windows.window(state, 'winter_harvest_faction', faction=ROMANS)
    roman_score = calculate_victory_score(state, ROMANS)
    roman_earn = roman_score
    _add_resources(state, ROMANS, roman_earn)
    result[ROMANS] = roman_earn

    # §6.4.2 Gallic Earnings: 2x (Allied Tribes + Citadels)
    for faction in GALLIC_FACTIONS:
        action_windows.window(state, 'winter_harvest_faction', faction=faction)
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
    action_windows.window(state, 'winter_river_tolls', faction=AEDUI)
    _add_resources(state, AEDUI, AEDUI_RIVER_TOLLS)
    result[AEDUI] = result.get(AEDUI, 0) + AEDUI_RIVER_TOLLS

    # A6.4.4 Germanic Earnings (Ariovistus only): 2x (Allies + Settlements)
    if scenario in ARIOVISTUS_SCENARIOS:
        action_windows.window(state, 'winter_harvest_faction', faction=GERMANS)
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

@_winter_scope
def senate_phase(state, first_senate_after_interlude=False,
                 force_position=None):
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

    # §6.5.1 Senate Marker shift — or the 1st-Winter special: "instead
    # of shifting the Senate, put its marker at Intrigue (not Firm)".
    action_windows.window(state, 'winter_senate_marker')
    if force_position is not None:
        state.setdefault("senate", {})["position"] = force_position
        state["senate"]["firm"] = False
        result["marker_shift"] = {"shifted": False,
                                  "forced": force_position}
    else:
        result["marker_shift"] = _senate_marker_shift(
            state, first_senate_after_interlude
        )

    # §6.5.2 Legions
    action_windows.window(state, 'winter_senate_legions')
    legions_result = _senate_legions(state)
    result.update(legions_result)

    # §6.5.3 Auxilia
    action_windows.window(state, 'winter_senate_auxilia')
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

    # A6.5.1: skip the shift during the first Senate Phase after the
    # Gallic War Interlude. Keyed on the flag alone — only the Interlude
    # sets it, and the Interlude switches state["scenario"] to
    # Pax Gallica? for the second half (A2.1).
    if first_senate_after_interlude:
        result["reason"] = "First Senate Phase after Interlude — no shift"
        return result

    # Pax Gallica? 1st Winter: the Senate marker starts in the "Senate box"
    # (position None). Per that scenario's 1st-Winter rule, that Senate Phase
    # "instead of shifting the Senate, put its marker at Intrigue (not Firm)".
    # Handling the None (marker-in-box) state here also guards every base
    # scenario from indexing a marker that is not yet on the track.
    if state["senate"]["position"] is None:
        state["senate"]["position"] = INTRIGUE
        state["senate"]["firm"] = False
        result["new_position"] = INTRIGUE
        result["new_firm"] = False
        result["shifted"] = True
        result["reason"] = (
            "Senate marker placed at Intrigue (was in the Senate box)"
        )
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

    # Card 33 (Lost Eagle), shaded: "This upcoming Senate Phase, no shift down."
    # The flag persists from event play to here; consume it this phase.
    mods = state.get("event_modifiers")
    no_shift_down = False
    if isinstance(mods, dict):
        no_shift_down = bool(mods.pop("lost_eagle_no_shift_down", False))

    # EXCEPTION: Do not shift down (toward Adulation, including to Intrigue
    # from Uproar) if any Legions are in the Fallen box — §6.5.1 — or if a
    # Lost Eagle (card 33) suppresses the downward shift this phase.
    if direction == "down" and (fallen > 0 or no_shift_down):
        result["reason"] = ("Lost Eagle prevents downward shift" if no_shift_down
                            and fallen == 0 else
                            "Fallen Legions prevent downward shift")
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

    A6.5.2: In Ariovistus, at most 2 total from the Intrigue/Adulation
    rows; Legions from the Uproar row are not subject to that limit.

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
    action_windows.window(state, 'winter_senate_legion_placement')
    senate_pos = state["senate"]["position"]
    rows_to_place = _ROWS_AT_OR_ABOVE_SENATE.get(senate_pos, ())

    # A6.5.2 caps the combined Intrigue/Adulation rows, not the Uproar
    # row. Keep that budget separate so Top-row Legions neither consume
    # it nor become restricted by it.
    lower_row_budget = ARIOVISTUS_SENATE_MAX_LEGIONS
    taken_by_row = {}
    for row in reversed(rows_to_place):
        take = state["legions_track"].get(row, 0)
        if scenario in ARIOVISTUS_SCENARIOS and row != LEGIONS_ROW_TOP:
            take = min(take, lower_row_budget)
            lower_row_budget -= take
        taken_by_row[row] = take
    total_to_place = sum(taken_by_row.values())

    if total_to_place > 0:
        # Remove from track (top rows first) and place in Provincia
        # We manually manage the track and use direct placement to avoid
        # conflicts with place_piece(from_legions_track=True) which takes
        # from top rows unconditionally.
        for row, take in taken_by_row.items():
            state["legions_track"][row] -= take

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

@_winter_scope
def spring_phase(state, *, unlock_vercingetorix=False):
    """Resolve Spring atomically, including all seats' Leader decisions."""
    from fs_bot.engine.spring import atomic
    with atomic(state):
        return _spring_phase(state, unlock_vercingetorix=unlock_vercingetorix)


def _spring_phase(state, *, unlock_vercingetorix=False):
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

    from fs_bot.engine.spring import unlock_spring_box_entry, resolve_spring_box_entry
    if unlock_vercingetorix:
        unlock_spring_box_entry(state)
    entry = resolve_spring_box_entry(state)
    if entry is not None:
        result['spring_box_entry'] = entry

    # Place Successor Leaders from Available — §6.6
    result["successors_placed"] = _place_successor_leaders(state)

    # Move remaining Fallen Legions to track — §6.6
    action_windows.window(state, 'winter_spring_fallen')
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
        if any(count_pieces_by_state(state, region, faction, piece, visibility)
               for faction in FACTIONS for piece in FLIPPABLE_PIECES
               for visibility in (SCOUTED, REVEALED)):
            action_windows.window(state, 'winter_spring_region', region=region)
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
    action_windows.window(state, 'winter_spring_devastation')
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
        if status in (MARKER_DISPERSED_GATHERING, MARKER_DISPERSED):
            action_windows.window(state, 'winter_spring_tribe', tribe=tribe_name)
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
    action_windows.window(state, 'winter_spring_eligibility')
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
    from fs_bot.engine.spring import place_successors
    return place_successors(state)


def _find_successor_placement(state, faction):
    """Find where to place a Successor Leader — §6.6.

    Place where faction has a piece or a Home Region "Rally" or
    "Recruit" symbol.

    Returns:
        Region name, or None if no valid placement.
    """
    from fs_bot.engine.spring import successor_regions
    from fs_bot.bots.bot_common import get_leader_placement_region
    return get_leader_placement_region(state, faction,
                                      candidates=successor_regions(state, faction))


# ============================================================================
# MAIN: RUN WINTER ROUND
# ============================================================================

@_winter_scope
def run_winter_round(state, is_final=False,
                     first_senate_after_interlude=False,
                     relocations=None,
                     britannia_decision=None,
                     roman_dispersed_keep=None):
    """Execute the full Winter Round per §6.0 / A6.0.

    Calls each phase in order. Stops early if Victory Phase ends the game.

    For SCENARIO_GALLIC_WAR, after the 3rd Victory Phase (and only if
    no faction has won), the Gallic War Interlude (A2.1) replaces the
    rest of the Winter Round. Pass britannia_decision and
    roman_dispersed_keep to control Roman choices during the Interlude.

    On Winter Rounds AFTER the Interlude has completed, the
    state["first_senate_after_interlude_pending"] and
    state["first_harvest_after_interlude_pending"] flags are consumed
    here and override the corresponding phases per A2.1 "During the
    1st Winter Round" rules.

    Args:
        state: Game state dict. Modified in place.
        is_final: True if this is the final Winter card (§2.4.1).
        first_senate_after_interlude: For Gallic War scenario (A6.5.1).
            Auto-consumed from state if pending.
        relocations: Optional dict of relocation decisions for Quarters.
        britannia_decision: Optional Roman decision for the Britannia
            expedition (Interlude only).
        roman_dispersed_keep: Optional tribe constant — the one
            Dispersed/Dispersed-Gathering tribe Romans keep through
            the Interlude Spring step.

    Returns:
        Dict with results from each phase. Contains "interlude" key
        when the Gallic War Interlude ran.
    """
    scenario = state["scenario"]
    state["winter_count"] = state.get("winter_count", 0) + 1
    # 1st-Winter Special Rules (scenario sheet "Winter Track Setup" /
    # A2.1 Interlude): stored at setup, consumed ONCE by the next Winter
    # Round. These were written by setup and never read — every Pax
    # Gallica game ran its first Victory Phase (Rome, opening above the
    # >15 threshold, won at Winter 1 in most games) and Vercingetorix
    # never left the Spring box. Found by live human-seat play.
    fws = state.pop("first_winter_special", None) or {}
    if fws.get('place_vercingetorix_in_spring'):
        # Explicitly keep the Spring-box gate closed while this Winter's
        # earlier phases run, including for legacy states without a flag.
        from fs_bot.engine.spring import UNLOCK_KEY
        state.setdefault(UNLOCK_KEY, False)

    result = {
        "winter_count": state["winter_count"],
        "phases": {},
    }
    if fws:
        result["first_winter_special"] = dict(fws)

    # Consume the pending first-Winter-after-Interlude flags.
    consume_first_senate = False
    if state.get("first_senate_after_interlude_pending"):
        consume_first_senate = True
    if first_senate_after_interlude:
        consume_first_senate = True
    consume_first_harvest_no_belgica = state.get(
        "first_harvest_after_interlude_pending", False,
    )

    # Phase 1: Victory
    if fws.get("skip_victory_phase"):
        victory_result = {"game_over": False, "winner": None,
                          "rankings": None,
                          "skipped": "1st Winter special rule"}
    else:
        victory_result = victory_phase(state, is_final=is_final)
    result["phases"]["victory"] = victory_result
    if victory_result["game_over"]:
        return result

    # Gallic War Interlude trigger — A2.1.
    from fs_bot.rules_consts import INTERLUDE_VICTORY_TRIGGER_WINTER
    if (scenario == SCENARIO_GALLIC_WAR
            and state["winter_count"] ==
            INTERLUDE_VICTORY_TRIGGER_WINTER
            and not state.get("interlude_completed", False)):
        # Run Interlude in place of the rest of the Winter Round.
        from fs_bot.engine.interlude import run_interlude
        interlude_result = run_interlude(
            state,
            britannia_decision=britannia_decision,
            roman_dispersed_keep=roman_dispersed_keep,
        )
        result["interlude"] = interlude_result
        return result

    # Phase 2: Germans Phase (base game only)
    if scenario in BASE_SCENARIOS:
        if fws.get("skip_germans_phase"):
            result["phases"]["germans"] = {"skipped":
                                           "1st Winter special rule"}
        else:
            result["phases"]["germans"] = germans_phase(state)

    # §6.3/A6.3 decisions are collected in faction order, after earlier
    # relocations/desertions have changed the board. Every human faction
    # can choose; a deferring Roman still receives the standard NP plan.
    result["phases"]["quarters"] = quarters_phase(
        state, relocations=relocations
    )

    # Card A66 Winter Uprising: after any Quarters Phase, resolve the
    # Uprising (remove marker, place pieces, free Command / Arverni Phase).
    from fs_bot.cards.winter_uprising_resolution import active as uprising_active
    if uprising_active(state):
        action_windows.window(state, 'winter_uprising')
        from fs_bot.engine.execute import _resolve_winter_uprising
        result["phases"]["winter_uprising"] = _resolve_winter_uprising(state)

    # Phase 4: Harvest — apply the 1st-Winter-after-Interlude exception
    # before normal harvest.
    action_windows.window(state, 'winter_harvest')
    if consume_first_harvest_no_belgica:
        # Per A2.1: "If there are no Legions on the Winter Track, do
        # not place any in Belgica during that Harvest Phase." The
        # Pax Gallica 1st-Winter rule otherwise would place 3 Legions
        # from the Winter Track in Belgica — for the Gallic War
        # post-Interlude path, that placement is conditional on
        # winter_track_legions > 0. We just record the exception in
        # the result.
        state["first_harvest_after_interlude_pending"] = False
        result["phases"]["harvest_special"] = {
            "no_belgica_legions_if_track_empty": True,
            "winter_track_legions":
                state.get("winter_track_legions", 0),
        }

    n_bel = fws.get("harvest_place_legions_in_belgica", 0)
    if n_bel:
        # "At the start of that Harvest Phase, the Romans place the
        # three Legions from the Winter Track into any Belgica
        # Region(s)." NP default (documented): all into the Belgica
        # Region with the most Roman pieces (sorted-first on ties).
        from fs_bot.rules_consts import BELGICA_REGIONS
        from fs_bot.board.pieces import count_pieces as _cp
        k = min(n_bel, state.get("winter_track_legions", 0))
        if k > 0:
            dest = max(sorted(BELGICA_REGIONS),
                       key=lambda r: _cp(state, r, ROMANS, LEGION)
                       + _cp(state, r, ROMANS, AUXILIA))
            pieces = state["spaces"][dest]["pieces"].setdefault(ROMANS, {})
            pieces[LEGION] = pieces.get(LEGION, 0) + k
            state["winter_track_legions"] -= k
            refresh_all_control(state)
            result["phases"]["harvest_belgica_legions"] = {
                "region": dest, "legions": k}
    result["phases"]["harvest"] = harvest_phase(state)

    # Cards 63/A63 grant any two paid Commands/SAs, with explicit human
    # choices and the card's exceptions to normal accompanying-SA rules.
    from fs_bot.engine.winter_campaign import winter_campaign_after_harvest
    action_windows.window(state, 'winter_campaign')
    campaign = winter_campaign_after_harvest(state)
    if campaign is not None:
        result["phases"]["winter_campaign"] = campaign
    # §8.6.6 NP Aedui subsidy — Quarters/Harvest are §1.5.2 transfer
    # windows and Roman Resources drop paying Quarters costs.
    from fs_bot.engine.execute import maybe_np_aedui_subsidy
    _sub = maybe_np_aedui_subsidy(state)
    if _sub:
        result["phases"]["np_aedui_subsidy"] = _sub

    # Phase 5: Senate
    result["phases"]["senate"] = senate_phase(
        state,
        first_senate_after_interlude=consume_first_senate,
        force_position=(INTRIGUE if fws.get("senate_set_to_intrigue")
                        else None),
    )
    if consume_first_senate:
        state["first_senate_after_interlude_pending"] = False

    # Phase 6: Spring
    result["phases"]["spring"] = spring_phase(
        state, unlock_vercingetorix=bool(fws.get("place_vercingetorix_in_spring")))
    entry = result["phases"]["spring"].get('spring_box_entry')
    if entry and 'region' in entry:
        result["phases"]["vercingetorix_placed"] = {"region": entry['region']}

    return result
