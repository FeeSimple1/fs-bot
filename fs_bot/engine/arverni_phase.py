"""Arverni Phase — Game-run Arverni activation for Ariovistus.

The Arverni Phase replaces the base game's Germans Phase conceptually.
It happens during Event cards (A2.3.9), NOT during Winter, whenever
cued by the carnyx symbol and the Arverni are At War.

All decisions are mechanical/procedural per A6.2 — this is game-run,
not bot-controlled.

Reference:
  A2.3.9  Arverni Activation (carnyx symbol trigger)
  A6.2    Arverni Phase procedures
  A6.2.1  Arverni Rally
  A6.2.2  Arverni March
  A6.2.3  Arverni Raid
  A6.2.4  Arverni Battle with Ambush
  arverni_and_other_celts.txt — Aid sheet with die roll table
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    FACTIONS,
    # Piece types
    LEADER, WARBAND, AUXILIA, ALLY, CITADEL, FORT,
    FLIPPABLE_PIECES,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Scenarios
    ARIOVISTUS_SCENARIOS,
    # Regions
    VENETI, CARNUTES, PICTONES, ARVERNI_REGION,
    ALL_REGIONS,
    # Home regions
    ARVERNI_HOME_REGIONS_ARIOVISTUS,
    # Markers
    MARKER_DEVASTATED, MARKER_INTIMIDATED,
    MARKER_AT_WAR, MARKER_ARVERNI_TARGET,
    # Control
    ARVERNI_CONTROL, AEDUI_CONTROL, ROMAN_CONTROL,
    FACTION_CONTROL,
    # Die
    DIE_MIN, DIE_MAX,
    # Costs
    MAX_RESOURCES,
)
from fs_bot.board.pieces import (
    place_piece, remove_piece, move_piece, flip_piece,
    count_pieces, count_pieces_by_state, get_available,
    get_leader_in_region, find_leader, PieceError,
)
from fs_bot.board.control import (
    refresh_all_control, is_controlled_by, get_controlled_regions,
    calculate_control,
)
from fs_bot.map.map_data import (
    get_adjacent, get_tribes_in_region, is_city_tribe,
    ALL_REGION_DATA, get_region_data, get_playable_regions,
)
from fs_bot.commands.common import CommandError, _is_devastated, _is_intimidated
from fs_bot.battle.losses import calculate_losses
from fs_bot.battle.resolve import resolve_battle


# ============================================================================
# Die roll table from arverni_and_other_celts.txt
# ============================================================================

# Target Region selection (A6.2)
# Die Roll | Target Region
# 1-2      | Most Enemy Pieces (triggering region with most enemies)
# 3        | Arverni Region
# 4        | Carnutes Region
# 5        | Pictones Region
# 6        | Veneti Region

_REGION_ROLL_TABLE = {
    1: "most_enemies",
    2: "most_enemies",
    3: ARVERNI_REGION,
    4: CARNUTES,
    5: PICTONES,
    6: VENETI,
}

# Target Faction selection (A6.2)
# Die Roll | Target Faction
# 1-2      | Enemy With Most (pieces in target region)
# 3        | Aedui
# 4        | Germans
# 5        | Romans
# 6        | Belgae

_FACTION_ROLL_TABLE = {
    1: "most_pieces",
    2: "most_pieces",
    3: AEDUI,
    4: GERMANS,
    5: ROMANS,
    6: BELGAE,
}


# ============================================================================
# AT WAR CHECK (A6.2)
# ============================================================================

def check_arverni_at_war(state):
    """Check if the Arverni are At War per A6.2.

    Arverni are At War if any non-Arverni Forces are in any Arverni
    Home Regions or are with any Arverni Allies or Citadels in any
    other Regions.

    Args:
        state: Game state dict.

    Returns:
        (is_at_war: bool, triggering_regions: list)
    """
    scenario = state["scenario"]
    if scenario not in ARIOVISTUS_SCENARIOS:
        raise CommandError(
            "Arverni Phase is Ariovistus only (A6.2)"
        )

    home_regions = ARVERNI_HOME_REGIONS_ARIOVISTUS
    triggering = []

    # Check Arverni Home Regions for non-Arverni Forces
    for region in home_regions:
        for faction in FACTIONS:
            if faction == ARVERNI:
                continue
            if count_pieces(state, region, faction) > 0:
                if region not in triggering:
                    triggering.append(region)
                break

    # Check other regions: non-Arverni Forces with Arverni Allies/Citadels
    for region in state["spaces"]:
        if region in home_regions:
            continue
        # Does Arverni have Allies or Citadels here?
        arverni_allies = count_pieces(state, region, ARVERNI, ALLY)
        arverni_citadels = count_pieces(state, region, ARVERNI, CITADEL)
        if arverni_allies + arverni_citadels == 0:
            continue
        # Are there non-Arverni Forces here?
        for faction in FACTIONS:
            if faction == ARVERNI:
                continue
            if count_pieces(state, region, faction) > 0:
                if region not in triggering:
                    triggering.append(region)
                break

    is_at_war = len(triggering) > 0
    state["at_war"] = is_at_war
    return (is_at_war, triggering)


# ============================================================================
# TARGET SELECTION (A6.2)
# ============================================================================

def select_arverni_targets(state, triggering_regions):
    """Select Target Region and Target Faction per A6.2 die roll table.

    Uses state["rng"] for all rolls.

    Args:
        state: Game state dict.
        triggering_regions: List of regions causing At War status.

    Returns:
        (target_region, target_faction)
    """
    rng = state["rng"]

    # Roll for Target Region
    target_region = _roll_target_region(state, rng, triggering_regions)

    # Roll for Target Faction
    target_faction = _roll_target_faction(state, rng, target_region)

    return (target_region, target_faction)


def _roll_target_region(state, rng, triggering_regions):
    """Roll to select Target Region from the die roll table.

    Roll a die. If result doesn't yield a valid candidate, track down
    the column (3→4→5→6→1→2→3→...) until valid.
    """
    roll = rng.randint(DIE_MIN, DIE_MAX)

    # Try the roll and then cycle through the table
    for offset in range(DIE_MAX):
        check_roll = ((roll - 1 + offset) % DIE_MAX) + 1
        region_result = _REGION_ROLL_TABLE[check_roll]

        if region_result == "most_enemies":
            # Select triggering region with most enemy pieces total
            candidates = _regions_with_most_enemies(state, triggering_regions)
            if candidates:
                if len(candidates) == 1:
                    return candidates[0]
                return rng.choice(candidates)
        else:
            # Named home region — must be a triggering region
            if region_result in triggering_regions:
                return region_result

    # Fallback: shouldn't reach here if triggering_regions is non-empty
    return rng.choice(triggering_regions)


def _roll_target_faction(state, rng, target_region):
    """Roll to select Target Faction that has Forces in the Target Region.

    Roll a die. If result doesn't yield a valid candidate, track down
    the column until valid.
    """
    roll = rng.randint(DIE_MIN, DIE_MAX)

    for offset in range(DIE_MAX):
        check_roll = ((roll - 1 + offset) % DIE_MAX) + 1
        faction_result = _FACTION_ROLL_TABLE[check_roll]

        if faction_result == "most_pieces":
            # Faction with most pieces in target region
            candidates = _factions_with_most_pieces(state, target_region)
            if candidates:
                if len(candidates) == 1:
                    return candidates[0]
                return rng.choice(candidates)
        else:
            # Named faction — must have Forces in the Target Region
            if count_pieces(state, target_region, faction_result) > 0:
                return faction_result

    # Fallback: pick any non-Arverni faction with pieces
    for faction in FACTIONS:
        if faction == ARVERNI:
            continue
        if count_pieces(state, target_region, faction) > 0:
            return faction

    raise CommandError(
        f"No valid target faction in {target_region}"
    )


def _regions_with_most_enemies(state, triggering_regions):
    """Find triggering region(s) with the most enemy pieces total."""
    max_enemies = 0
    best = []
    for region in triggering_regions:
        enemies = 0
        for faction in FACTIONS:
            if faction == ARVERNI:
                continue
            enemies += count_pieces(state, region, faction)
        if enemies > max_enemies:
            max_enemies = enemies
            best = [region]
        elif enemies == max_enemies and enemies > 0:
            best.append(region)
    return best


def _factions_with_most_pieces(state, region):
    """Find non-Arverni faction(s) with most pieces in a region."""
    max_pieces = 0
    best = []
    for faction in FACTIONS:
        if faction == ARVERNI:
            continue
        n = count_pieces(state, region, faction)
        if n > max_pieces:
            max_pieces = n
            best = [faction]
        elif n == max_pieces and n > 0:
            best.append(faction)
    return best


# ============================================================================
# A6.2.1 ARVERNI RALLY
# ============================================================================

def _arverni_phase_rally(state, at_war_regions):
    """Execute Arverni Rally per A6.2.1.

    Rally only in At War Regions, only once per region.
    Priority:
    1. Replace City Allies with Citadels
    2. Place Allies (Cities first, then Home Regions, then elsewhere)
    3. Place Warbands (Allies+Citadels +1, or 1 in Home)

    Cannot Rally in Intimidated or Devastated regions.

    Returns:
        Dict with rally results.
    """
    scenario = state["scenario"]
    rng = state["rng"]
    result = {
        "citadels_placed": [],
        "allies_placed": [],
        "warbands_placed": {},
    }

    # Filter At War Regions: remove Intimidated and Devastated
    valid_regions = [
        r for r in at_war_regions
        if not _is_intimidated(state, r) and not _is_devastated(state, r)
    ]

    rallied_regions = set()

    # Step 1: Replace City Allies with Citadels — A6.2.1
    city_candidates = []
    for region in valid_regions:
        tribes = get_tribes_in_region(region, scenario)
        for tribe in tribes:
            if not is_city_tribe(tribe):
                continue
            tribe_info = state["tribes"].get(tribe, {})
            if tribe_info.get("allied_faction") != ARVERNI:
                continue
            # Has Arverni Ally at a City — can replace with Citadel
            if get_available(state, ARVERNI, CITADEL) > 0:
                city_candidates.append((region, tribe))

    rng.shuffle(city_candidates)
    for region, tribe in city_candidates:
        if region in rallied_regions:
            continue
        if get_available(state, ARVERNI, CITADEL) < 1:
            break
        # Verify still valid
        tribe_info = state["tribes"].get(tribe, {})
        if tribe_info.get("allied_faction") != ARVERNI:
            continue
        # Remove Ally, place Citadel
        remove_piece(state, region, ARVERNI, ALLY)
        tribe_info["allied_faction"] = None
        tribe_info["status"] = None
        place_piece(state, region, ARVERNI, CITADEL)
        result["citadels_placed"].append((region, tribe))
        rallied_regions.add(region)
        refresh_all_control(state)

    # Step 2: Place Allies — A6.2.1
    # Priority: Cities first, then Home Regions, then elsewhere
    ally_city_candidates = []
    ally_home_candidates = []
    ally_elsewhere_candidates = []

    for region in valid_regions:
        if region in rallied_regions:
            continue
        tribes = get_tribes_in_region(region, scenario)
        for tribe in tribes:
            tribe_info = state["tribes"].get(tribe, {})
            # Must be Subdued (no ally, no dispersed)
            if tribe_info.get("allied_faction") is not None:
                continue
            if tribe_info.get("status") is not None:
                continue
            entry = (region, tribe)
            if is_city_tribe(tribe):
                ally_city_candidates.append(entry)
            elif region in ARVERNI_HOME_REGIONS_ARIOVISTUS:
                ally_home_candidates.append(entry)
            else:
                ally_elsewhere_candidates.append(entry)

    for candidate_list in [ally_city_candidates, ally_home_candidates,
                           ally_elsewhere_candidates]:
        rng.shuffle(candidate_list)
        for region, tribe in candidate_list:
            if region in rallied_regions:
                continue
            if get_available(state, ARVERNI, ALLY) < 1:
                break
            # Verify still valid
            tribe_info = state["tribes"].get(tribe, {})
            if tribe_info.get("allied_faction") is not None:
                continue
            if tribe_info.get("status") is not None:
                continue
            # Place Ally
            place_piece(state, region, ARVERNI, ALLY)
            tribe_info["allied_faction"] = ARVERNI
            result["allies_placed"].append((region, tribe))
            rallied_regions.add(region)
            refresh_all_control(state)

    # Step 3: Place Warbands — A6.2.1
    # Warbands = Allies + Citadels + 1 (Arverni Rally rule §3.3.1)
    # Or 1 in Home Region even if no Ally there
    warband_candidates = []
    for region in valid_regions:
        if region in rallied_regions:
            # Already rallied for Citadel or Ally, but can still place Warbands
            pass
        # Calculate Warband cap per §3.3.1 Arverni Rally
        allies_here = count_pieces(state, region, ARVERNI, ALLY)
        citadels_here = count_pieces(state, region, ARVERNI, CITADEL)
        cap = allies_here + citadels_here + 1  # +1 per §3.3.1
        is_home = region in ARVERNI_HOME_REGIONS_ARIOVISTUS
        if cap == 1 and not is_home and allies_here == 0 and citadels_here == 0:
            # No Ally or Citadel and not Home — can't Rally Warbands
            continue
        if cap > 0:
            warband_candidates.append((region, cap))

    rng.shuffle(warband_candidates)
    for region, cap in warband_candidates:
        if region in rallied_regions and region not in [
            r for r, _ in result["citadels_placed"]
        ] + [r for r, _ in result["allies_placed"]]:
            # Only rally once per region, but regions that already rallied
            # for Citadel/Ally can still get Warbands
            pass
        available = get_available(state, ARVERNI, WARBAND)
        if available <= 0:
            break
        to_place = min(cap, available)
        if to_place > 0:
            place_piece(state, region, ARVERNI, WARBAND, to_place)
            result["warbands_placed"][region] = to_place

    refresh_all_control(state)
    return result


# ============================================================================
# A6.2.2 ARVERNI MARCH
# ============================================================================

def _arverni_phase_march(state, target_region, is_frost=False):
    """Execute Arverni March per A6.2.2.

    - Skip if Frost
    - Flip all Arverni Warbands to Hidden
    - March from regions (except target) with surplus Warbands
    - Move to target region first, then 1 other region to remove
      Aedui/Roman Control

    Returns:
        Dict with march results.
    """
    scenario = state["scenario"]
    rng = state["rng"]
    result = {
        "skipped_frost": False,
        "warbands_flipped": 0,
        "marches": [],
    }

    if is_frost:
        result["skipped_frost"] = True
        return result

    # Flip all Arverni Warbands to Hidden — A6.2.2
    for region in state["spaces"]:
        for ps in (REVEALED, SCOUTED):
            wb_count = count_pieces_by_state(
                state, region, ARVERNI, WARBAND, ps
            )
            if wb_count > 0:
                flip_piece(
                    state, region, ARVERNI, WARBAND, count=wb_count,
                    from_state=ps, to_state=HIDDEN
                )
                result["warbands_flipped"] += wb_count

    # Find marching groups — A6.2.2
    # From regions (except target) with 1+ Warband beyond Control needs
    march_groups = []
    for region in state["spaces"]:
        if region == target_region:
            continue
        rd = ALL_REGION_DATA.get(region)
        if rd is None or not rd.is_playable(scenario, state.get("capabilities")):
            continue

        arverni_warbands = count_pieces(state, region, ARVERNI, WARBAND)
        if arverni_warbands == 0:
            continue

        # Calculate pieces needed for Arverni Control
        ctrl = calculate_control(state, region)
        if ctrl != FACTION_CONTROL[ARVERNI]:
            # No Arverni Control — would not move (A6.2.2 NOTE)
            continue

        # Count all Arverni Forces (for control calculation)
        arverni_total = count_pieces(state, region, ARVERNI)
        # Count all other Forces
        others_total = 0
        for f in FACTIONS:
            if f == ARVERNI:
                continue
            others_total += count_pieces(state, region, f)

        # Need strictly more than others for Control
        # Surplus = total - (others + 1) = available to march
        min_to_keep = others_total + 1
        # Only Warbands march (mobile pieces), but keep Leaders/Allies/etc
        non_wb = arverni_total - arverni_warbands
        wb_needed_for_control = max(0, min_to_keep - non_wb)
        can_march = arverni_warbands - wb_needed_for_control

        if can_march > 0:
            march_groups.append((region, can_march))

    # Move largest groups first — A6.2.2
    march_groups.sort(key=lambda x: x[1], reverse=True)

    # First: March to target region (adjacent groups)
    for region, wb_count in list(march_groups):
        adj = get_adjacent(region, scenario, state.get("capabilities"))
        if target_region in adj:
            # March to target
            for ps in (HIDDEN, REVEALED, SCOUTED):
                ps_count = count_pieces_by_state(
                    state, region, ARVERNI, WARBAND, ps
                )
                to_move = min(ps_count, wb_count)
                if to_move > 0:
                    move_piece(
                        state, region, target_region, ARVERNI, WARBAND,
                        count=to_move, piece_state=ps
                    )
                    wb_count -= to_move
                if wb_count <= 0:
                    break
            march_groups.remove((region, wb_count + to_move))
            result["marches"].append({
                "from": region,
                "to": target_region,
                "warbands": to_move,
            })

    # Then: 1 additional region where Aedui or Roman Control can be removed
    # Aedui first — A6.2.2
    additional_dest = None
    for control_target in (AEDUI_CONTROL, ROMAN_CONTROL):
        for region in state["spaces"]:
            if region == target_region:
                continue
            space = state["spaces"].get(region, {})
            if space.get("control") != control_target:
                continue
            # Check if any remaining marching groups are adjacent
            for mg_region, mg_count in march_groups:
                adj = get_adjacent(mg_region, scenario,
                                   state.get("capabilities"))
                if region in adj:
                    additional_dest = region
                    break
            if additional_dest:
                break
        if additional_dest:
            break

    if additional_dest:
        for mg_region, mg_count in list(march_groups):
            adj = get_adjacent(mg_region, scenario,
                               state.get("capabilities"))
            if additional_dest not in adj:
                continue
            for ps in (HIDDEN, REVEALED, SCOUTED):
                ps_count = count_pieces_by_state(
                    state, mg_region, ARVERNI, WARBAND, ps
                )
                to_move = min(ps_count, mg_count)
                if to_move > 0:
                    move_piece(
                        state, mg_region, additional_dest, ARVERNI, WARBAND,
                        count=to_move, piece_state=ps
                    )
                    mg_count -= to_move
                if mg_count <= 0:
                    break
            result["marches"].append({
                "from": mg_region,
                "to": additional_dest,
                "warbands": to_move,
            })

    refresh_all_control(state)
    return result


# ============================================================================
# A6.2.3 ARVERNI RAID
# ============================================================================

def _arverni_phase_raid(state, target_faction):
    """Execute Arverni Raid per A6.2.3.

    Raid with Hidden Warbands not needed for Ambush.
    Raid against target faction first, then players, then non-players.

    Returns:
        Dict with raid results.
    """
    rng = state["rng"]
    result = {
        "raids": [],
        "total_stolen": {},
    }

    # Find all regions where Arverni have Hidden Warbands
    for region in state["spaces"]:
        hidden = count_pieces_by_state(
            state, region, ARVERNI, WARBAND, HIDDEN
        )
        if hidden == 0:
            continue

        # Calculate Warbands needed for Ambush — A6.2.3
        # Don't Raid with Warbands needed to enable Ambush
        warbands_for_raid = _warbands_available_for_raid(state, region)
        if warbands_for_raid <= 0:
            continue

        # Find valid raid targets: Factions with Resources > 0, no Fort/Citadel
        targets = _get_raid_targets(state, region, target_faction)
        if not targets:
            continue

        wb_remaining = warbands_for_raid
        for target in targets:
            while wb_remaining > 0:
                target_resources = state["resources"].get(target, 0)
                if target_resources <= 0:
                    break
                # Check no Fort or Citadel
                if count_pieces(state, region, target, FORT) > 0:
                    break
                if count_pieces(state, region, target, CITADEL) > 0:
                    break

                # Flip one Warband Hidden→Revealed and steal 1 Resource
                flip_piece(
                    state, region, ARVERNI, WARBAND, count=1,
                    from_state=HIDDEN, to_state=REVEALED
                )
                wb_remaining -= 1

                # Steal Resource
                state["resources"][target] = target_resources - 1
                arverni_resources = state["resources"].get(ARVERNI, 0)
                state["resources"][ARVERNI] = min(
                    arverni_resources + 1, MAX_RESOURCES
                )
                result["total_stolen"][target] = (
                    result["total_stolen"].get(target, 0) + 1
                )

        if warbands_for_raid - wb_remaining > 0:
            result["raids"].append({
                "region": region,
                "warbands_used": warbands_for_raid - wb_remaining,
            })

    return result


def _warbands_available_for_raid(state, region):
    """Calculate how many Hidden Warbands can Raid (not needed for Ambush).

    Per A6.2.3: Only Raid with Warbands not needed to enable an Ambush.
    """
    hidden = count_pieces_by_state(
        state, region, ARVERNI, WARBAND, HIDDEN
    )

    # Check if any Ambush is possible in this region
    # Ambush needs: Hidden Arverni Warbands > enemy Hidden pieces
    warbands_needed_for_ambush = 0
    for faction in FACTIONS:
        if faction == ARVERNI:
            continue
        if count_pieces(state, region, faction) == 0:
            continue
        enemy_hidden = (
            count_pieces_by_state(state, region, faction, WARBAND, HIDDEN)
            + count_pieces_by_state(state, region, faction, AUXILIA, HIDDEN)
        )
        # Need enemy_hidden + 1 Warbands to Ambush this faction
        needed = enemy_hidden + 1
        # Only reserve if Ambush would cause losses
        if _ambush_would_cause_loss(state, region, faction):
            warbands_needed_for_ambush = max(
                warbands_needed_for_ambush, needed
            )

    return max(0, hidden - warbands_needed_for_ambush)


def _ambush_would_cause_loss(state, region, defending_faction):
    """Check if an Arverni Ambush would cause a Loss in this region."""
    losses = calculate_losses(
        state, region,
        attacking_faction=ARVERNI,
        defending_faction=defending_faction,
        is_retreat=False,
        is_counterattack=False,
    )
    return losses > 0


def _get_raid_targets(state, region, target_faction):
    """Get ordered list of raid targets per A6.2.3 priority.

    Order: target faction first, then players, then non-players.
    """
    non_players = state.get("non_player_factions", set())
    targets = []
    player_targets = []
    np_targets = []

    for faction in FACTIONS:
        if faction == ARVERNI:
            continue
        if count_pieces(state, region, faction) == 0:
            continue
        if state["resources"].get(faction, 0) <= 0:
            continue
        if count_pieces(state, region, faction, FORT) > 0:
            continue
        if count_pieces(state, region, faction, CITADEL) > 0:
            continue
        if faction == target_faction:
            targets.insert(0, faction)
        elif faction not in non_players:
            player_targets.append(faction)
        else:
            np_targets.append(faction)

    # Shuffle within priority groups
    rng = state["rng"]
    rng.shuffle(player_targets)
    rng.shuffle(np_targets)
    targets.extend(player_targets)
    targets.extend(np_targets)
    return targets


# ============================================================================
# A6.2.4 ARVERNI BATTLE WITH AMBUSH
# ============================================================================

def _arverni_phase_battle(state, target_region, target_faction):
    """Execute Arverni Battle with Ambush per A6.2.4.

    Battle in target region first, then other regions in random order.
    Within each region, attack target faction first, then players,
    then non-players.

    Returns:
        Dict with battle results.
    """
    rng = state["rng"]
    result = {
        "battles": [],
    }

    # Order: target region first, then others randomly
    battle_regions = [target_region]
    other_regions = [
        r for r in state["spaces"]
        if r != target_region
    ]
    rng.shuffle(other_regions)
    battle_regions.extend(other_regions)

    for region in battle_regions:
        # Check if Arverni can Ambush anyone here
        hidden = count_pieces_by_state(
            state, region, ARVERNI, WARBAND, HIDDEN
        )
        if hidden == 0:
            continue

        # Find valid battle targets
        candidates = _get_battle_targets(
            state, region, target_faction, hidden
        )
        if not candidates:
            continue

        for defending_faction in candidates:
            # Re-verify
            hidden = count_pieces_by_state(
                state, region, ARVERNI, WARBAND, HIDDEN
            )
            if hidden == 0:
                break
            enemy_hidden = (
                count_pieces_by_state(
                    state, region, defending_faction, WARBAND, HIDDEN
                )
                + count_pieces_by_state(
                    state, region, defending_faction, AUXILIA, HIDDEN
                )
            )
            if hidden <= enemy_hidden:
                continue
            if not _ambush_would_cause_loss(state, region, defending_faction):
                continue

            battle_result = resolve_battle(
                state, region,
                attacking_faction=ARVERNI,
                defending_faction=defending_faction,
                is_ambush=True,
            )
            result["battles"].append({
                "region": region,
                "defender": defending_faction,
                "result": battle_result,
            })

    refresh_all_control(state)
    return result


def _get_battle_targets(state, region, target_faction, arverni_hidden):
    """Get ordered battle targets per A6.2.4 priority.

    Target faction first (if there and would cause loss),
    then players, then non-players.
    """
    non_players = state.get("non_player_factions", set())
    targets = []
    player_targets = []
    np_targets = []

    for faction in FACTIONS:
        if faction == ARVERNI:
            continue
        if count_pieces(state, region, faction) == 0:
            continue
        enemy_hidden = (
            count_pieces_by_state(state, region, faction, WARBAND, HIDDEN)
            + count_pieces_by_state(state, region, faction, AUXILIA, HIDDEN)
        )
        if arverni_hidden <= enemy_hidden:
            continue
        if not _ambush_would_cause_loss(state, region, faction):
            continue

        if faction == target_faction:
            targets.insert(0, faction)
        elif faction not in non_players:
            player_targets.append(faction)
        else:
            np_targets.append(faction)

    rng = state["rng"]
    rng.shuffle(player_targets)
    rng.shuffle(np_targets)
    targets.extend(player_targets)
    targets.extend(np_targets)
    return targets


# ============================================================================
# MAIN: RUN ARVERNI PHASE
# ============================================================================

def run_arverni_phase(state, is_frost=False):
    """Execute the full Arverni Phase — A6.2.

    Check At War. If At Peace, skip.
    Select targets, then Rally, March, Raid, Battle with Ambush.

    Args:
        state: Game state dict. Modified in place.
        is_frost: True if Frost condition is active (§2.3.8).

    Returns:
        Dict with phase results.
    """
    scenario = state["scenario"]
    if scenario not in ARIOVISTUS_SCENARIOS:
        raise CommandError("Arverni Phase is Ariovistus only (A6.2)")

    result = {
        "at_war": False,
        "triggering_regions": [],
        "target_region": None,
        "target_faction": None,
        "rally": None,
        "march": None,
        "raid": None,
        "battle": None,
    }

    # Check At War
    is_at_war, triggering_regions = check_arverni_at_war(state)
    result["at_war"] = is_at_war
    result["triggering_regions"] = triggering_regions

    if not is_at_war:
        return result

    # Select Targets
    target_region, target_faction = select_arverni_targets(
        state, triggering_regions
    )
    result["target_region"] = target_region
    result["target_faction"] = target_faction

    # A6.2.1 Rally
    result["rally"] = _arverni_phase_rally(state, triggering_regions)

    # A6.2.2 March (skip if Frost)
    result["march"] = _arverni_phase_march(
        state, target_region, is_frost=is_frost
    )

    # A6.2.3 Raid
    result["raid"] = _arverni_phase_raid(state, target_faction)

    # A6.2.4 Battle with Ambush
    result["battle"] = _arverni_phase_battle(
        state, target_region, target_faction
    )

    refresh_all_control(state)
    return result
