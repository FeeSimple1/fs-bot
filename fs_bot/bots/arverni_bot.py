"""
Non-Player Arverni flowchart — §8.7.

Every node from the Arverni bot flowchart (V1 through V_ENTREAT, plus
V_QUARTERS, V_SPRING, V_AGREEMENTS, V_ELITE) is a labeled function.

The Arverni bot is base-game-only. In Ariovistus, the Arverni are game-run
via the Arverni Phase (A6.2) and have no bot flowchart.

Node functions return an action dict describing what the bot decided to do.
The dispatch loop calls execute_arverni_turn(state) which walks the flowchart.
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    FACTIONS, GALLIC_FACTIONS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL,
    MOBILE_PIECES,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Scenarios
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    # Commands / SAs
    CMD_RALLY, CMD_MARCH, CMD_RAID, CMD_BATTLE,
    SA_DEVASTATE, SA_ENTREAT, SA_AMBUSH,
    # Leaders
    VERCINGETORIX, CAESAR,
    # Regions
    AEDUI_REGION, BRITANNIA,
    # Events
    EVENT_SHADED,
    # Die
    DIE_MIN, DIE_MAX,
)
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, get_leader_in_region,
    find_leader, get_available, count_on_map,
)
from fs_bot.board.control import (
    is_controlled_by, get_controlled_regions, calculate_control,
)
from fs_bot.engine.victory import (
    calculate_victory_score, calculate_victory_margin, check_victory,
)
from fs_bot.map.map_data import (
    get_adjacent, get_playable_regions, get_tribes_in_region,
    get_region_group, is_city_tribe,
)
from fs_bot.bots.bot_common import (
    # Event decisions
    should_decline_event, get_dual_use_preference, get_event_instruction,
    upgrade_limited_command,
    # Targeting
    get_faction_targeting_order, get_enemy_piece_target_order,
    get_own_loss_order,
    # Frost
    is_frost_active, check_frost_restriction,
    # Harassment
    get_harassing_factions, np_will_harass,
    # Retreat
    should_retreat, get_retreat_preferences,
    # Random
    random_select, roll_die,
    # Helpers
    has_enemy_threat_in_region, count_mobile_pieces,
    count_faction_allies_and_citadels,
    rank_regions_for_event_placement,
    leader_escort_needed,
    get_leader_placement_region,
    # Supply line / agreements
    np_agrees_to_supply_line,
    is_no_faction_event,
)
from fs_bot.bots.bot_dispatch import BotDispatchError
from fs_bot.cards.bot_instructions import (
    get_bot_instruction, NO_EVENT, SPECIFIC_INSTRUCTION, PLAY_EVENT,
    CONDITIONAL,
)


# ============================================================================
# Action result constants
# ============================================================================

ACTION_BATTLE = "Battle"
ACTION_MARCH = "March"
ACTION_RALLY = "Rally"
ACTION_RAID = "Raid"
ACTION_EVENT = "Event"
ACTION_PASS = "Pass"
ACTION_NONE = "None"

SA_ACTION_AMBUSH = "Ambush"
SA_ACTION_DEVASTATE = "Devastate"
SA_ACTION_ENTREAT = "Entreat"
SA_ACTION_NONE = "No SA"

# March sub-types for clarity in action dicts
MARCH_THREAT = "March (threat)"
MARCH_SPREAD = "March (spread)"
MARCH_MASS = "March (mass)"


def _make_action(command, *, regions=None, sa=SA_ACTION_NONE, sa_regions=None,
                 details=None):
    """Build a standardized action result dict."""
    return {
        "command": command,
        "regions": regions or [],
        "sa": sa,
        "sa_regions": sa_regions or [],
        "details": details or {},
    }


# ============================================================================
# HELPER: Arverni-specific board queries
# ============================================================================

def _vercingetorix_region(state):
    """Find Vercingetorix's region, or None."""
    return find_leader(state, ARVERNI)


def _count_arverni_warbands_on_map(state):
    """Count total Arverni Warbands on map."""
    return count_on_map(state, ARVERNI, WARBAND)


def _count_arverni_allies_citadels_on_map(state):
    """Count total Arverni Allies + Citadels on map."""
    return count_faction_allies_and_citadels(state, ARVERNI)


def _has_arverni_threat(state, region, scenario):
    """Check if a region meets the V1 'Battle or March under Threat' condition.

    Per §8.7.1: Vercingetorix or 10+ Arverni Warbands in a Region where
    Romans or Aedui have an Ally, Citadel, Legion, or separately ≥4 pieces.

    Args:
        state: Game state dict.
        region: Region constant.
        scenario: Scenario constant.

    Returns:
        True if the region has a threat per §8.7.1.
    """
    # Must have Vercingetorix OR 10+ Arverni Warbands in this region
    has_verc = get_leader_in_region(state, region, ARVERNI) is not None
    arverni_wb = count_pieces(state, region, ARVERNI, WARBAND)
    if not has_verc and arverni_wb < 10:
        return False

    # Check Romans and Aedui for Ally, Citadel, Legion, or ≥4 pieces
    for enemy in (ROMANS, AEDUI):
        if count_pieces(state, region, enemy, ALLY) > 0:
            return True
        if count_pieces(state, region, enemy, CITADEL) > 0:
            return True
        if count_pieces(state, region, enemy, LEGION) > 0:
            return True
        # "separately at least four pieces" — §8.7.1
        if count_pieces(state, region, enemy) >= 4:
            return True

    return False


def _get_threat_regions(state, scenario):
    """Get all regions meeting the V1 threat condition.

    Returns:
        List of region constants.
    """
    playable = get_playable_regions(scenario, state.get("capabilities"))
    return [r for r in playable if _has_arverni_threat(state, r, scenario)]


def _can_battle_in_region(state, region, scenario, enemy):
    """Check if Arverni can Battle a specific enemy in a region per §8.7.1.

    Conditions: Force at least one Loss on a Legion AND/OR inflict more
    Losses than suffered — AND no Loss on Vercingetorix possible (presuming
    all Defender Loss rolls result in removals, best case for Arverni Attack).

    Args:
        state: Game state dict.
        region: Region constant.
        scenario: Scenario constant.
        enemy: Enemy faction constant.

    Returns:
        True if Arverni can Battle this enemy here per §8.7.1 restrictions.
    """
    arverni_wb = count_pieces(state, region, ARVERNI, WARBAND)
    has_verc = get_leader_in_region(state, region, ARVERNI) is not None
    arverni_mobile = arverni_wb + (1 if has_verc else 0)

    if arverni_mobile == 0:
        return False

    enemy_pieces = count_pieces(state, region, enemy)
    if enemy_pieces == 0:
        return False

    # Estimate Arverni Losses inflicted (Attack): mobile pieces / 2 rounded up
    # per §3.3.4 for Gallic Battle
    losses_inflicted = arverni_mobile // 2
    if has_verc:
        # Vercingetorix adds to combat value
        losses_inflicted = arverni_mobile // 2

    # Check for Legion loss — can we force at least one Loss on a Legion?
    enemy_legions = count_pieces(state, region, enemy, LEGION)
    can_hit_legion = enemy_legions > 0 and losses_inflicted > 0

    # Estimate Losses Arverni would suffer (Counterattack)
    enemy_mobile = count_mobile_pieces(state, region, enemy)
    # Counterattack: enemy mobile / 2 rounded up
    losses_suffered = (enemy_mobile + 1) // 2

    # Enemy Fort/Citadel halves our Attack Losses inflicted
    enemy_fort = count_pieces(state, region, enemy, FORT)
    enemy_citadel = count_pieces(state, region, enemy, CITADEL)
    if enemy_fort > 0 or enemy_citadel > 0:
        losses_inflicted = losses_inflicted // 2

    # Our Citadel halves Counterattack Losses suffered
    our_citadel = count_pieces(state, region, ARVERNI, CITADEL)
    if our_citadel > 0:
        losses_suffered = losses_suffered // 2

    # Check: no Loss on Vercingetorix — §8.7.1
    # "presuming all Defender Loss rolls result in removals"
    # Vercingetorix would take a Loss only if all Warbands removed first
    if has_verc and losses_suffered >= arverni_wb + 1:
        return False

    # Condition: force Loss on Legion AND/OR inflict more Losses than suffered
    if can_hit_legion:
        return True
    if losses_inflicted > losses_suffered:
        return True

    return False


def _caesar_in_region(state, region):
    """Check if Caesar is in a specific region."""
    return get_leader_in_region(state, region, ROMANS) is not None


def _check_caesar_ratio(state, region):
    """Check the >2:1 mobile ratio for fighting near Caesar.

    Per §8.7.1: Vercingetorix Battles Caesar only if Arverni mobile
    forces (Warbands + Vercingetorix) outnumber Roman mobile forces
    (Legions + Auxilia + Caesar) by more than 2:1.

    Returns:
        True if ratio is satisfied (safe to fight Caesar).
    """
    arverni_wb = count_pieces(state, region, ARVERNI, WARBAND)
    has_verc = get_leader_in_region(state, region, ARVERNI) is not None
    arverni_mobile = arverni_wb + (1 if has_verc else 0)

    roman_legions = count_pieces(state, region, ROMANS, LEGION)
    roman_auxilia = count_pieces(state, region, ROMANS, AUXILIA)
    has_caesar = _caesar_in_region(state, region)
    roman_mobile = roman_legions + roman_auxilia + (1 if has_caesar else 0)

    if roman_mobile == 0:
        return True
    return arverni_mobile > 2 * roman_mobile


def _estimate_rally_placements(state, scenario):
    """Estimate how many pieces Rally would place (without Entreat).

    Per §8.7.3: Rally places Citadels, Allies, Warbands.

    Returns:
        Dict with "citadels", "allies", "warbands", "total" counts.
    """
    playable = get_playable_regions(scenario, state.get("capabilities"))
    citadels = 0
    allies = 0
    warbands = 0

    avail_citadels = get_available(state, ARVERNI, CITADEL)
    avail_allies = get_available(state, ARVERNI, ALLY)
    avail_warbands = get_available(state, ARVERNI, WARBAND)

    # Step 1: Citadels — replace Allies in Cities with Citadels
    for region in playable:
        if avail_citadels <= 0:
            break
        tribes = get_tribes_in_region(region, scenario)
        for tribe in tribes:
            if avail_citadels <= 0:
                break
            tribe_info = state["tribes"].get(tribe, {})
            if (tribe_info.get("allied_faction") == ARVERNI
                    and is_city_tribe(tribe)):
                citadels += 1
                avail_citadels -= 1
                # This frees up an Ally
                avail_allies += 1

    # Step 2: Allies — place wherever possible
    # Allies require Arverni Control or Home Region with pieces
    for region in playable:
        if avail_allies <= 0:
            break
        tribes = get_tribes_in_region(region, scenario)
        for tribe in tribes:
            if avail_allies <= 0:
                break
            tribe_info = state["tribes"].get(tribe, {})
            # Can place if tribe is subdued/empty and region has Arverni
            # control or is a Rally region
            if tribe_info.get("allied_faction") is None:
                if count_pieces(state, region, ARVERNI) > 0:
                    allies += 1
                    avail_allies -= 1

    # Step 3: Warbands — place most possible
    for region in playable:
        if avail_warbands <= 0:
            break
        # Can place Warbands in regions where Arverni have Control or
        # an Ally/Citadel — standard Rally rules §3.3.1
        has_ally_or_citadel = False
        tribes = get_tribes_in_region(region, scenario)
        for tribe in tribes:
            tribe_info = state["tribes"].get(tribe, {})
            if tribe_info.get("allied_faction") == ARVERNI:
                has_ally_or_citadel = True
                break
        if count_pieces(state, region, ARVERNI, CITADEL) > 0:
            has_ally_or_citadel = True

        if has_ally_or_citadel or is_controlled_by(state, region, ARVERNI):
            # Place Warbands here
            warbands += 1
            avail_warbands -= 1

    return {
        "citadels": citadels,
        "allies": allies,
        "warbands": warbands,
        "total": citadels + allies + warbands,
    }


def _would_raid_gain_enough(state, scenario):
    """Check if Raiding would gain at least 2 Resources total.

    Per §8.7.5: Raid only if would gain 2+ Resources.
    Per §3.3.3: Each Raid region flips 1-2 Hidden Warbands; each flip either
    steals 1 Resource from an enemy (no Citadel/Fort) or gains 1 Resource
    (non-Devastated, no faction target).  Max 2 flips per region total.

    Iterates by REGION first to avoid double-counting.  For each flip,
    assigns to highest-priority target: Romans → Aedui → Belgae (checking
    no Citadel/Fort for stealing), then non-Devastated +1 Resource.

    Returns:
        (bool, list of raid plan dicts) — whether 2+ Resources would be
        gained and the raid plan organized by region.
    """
    playable = get_playable_regions(scenario, state.get("capabilities"))
    total_gain = 0
    raid_plan = []

    for region in playable:
        hidden_wb = count_pieces_by_state(
            state, region, ARVERNI, WARBAND, HIDDEN)
        if hidden_wb == 0:
            continue

        # Max flips in this region — §3.3.3: flip 1-2 Hidden Warbands
        flips = min(2, hidden_wb)

        is_devastated = state["spaces"].get(region, {}).get("devastated", False)

        # Build ordered list of available targets for this region.
        # Priority: (1) Romans, (2) Aedui, (3) Belgae — §8.7.5
        # Stealing requires enemy has pieces but neither Citadel nor Fort — §3.3.3
        steal_targets = []
        for target in (ROMANS, AEDUI, BELGAE):
            if count_pieces(state, region, target) == 0:
                continue
            if (count_pieces(state, region, target, CITADEL) > 0
                    or count_pieces(state, region, target, FORT) > 0):
                continue
            steal_targets.append(target)

        # Assign each flip to the best available use
        region_entries = []
        remaining_flips = flips
        for target in steal_targets:
            if remaining_flips <= 0:
                break
            region_entries.append({"region": region, "target": target})
            total_gain += 1
            remaining_flips -= 1

        # Remaining flips: non-Devastated +1 Resource (no faction target)
        while remaining_flips > 0:
            if not is_devastated:
                region_entries.append({"region": region, "target": None})
                total_gain += 1
            remaining_flips -= 1

        raid_plan.extend(region_entries)

    return (total_gain >= 2, raid_plan)


def _distance_to_region(region_a, region_b, scenario, max_dist=10):
    """Calculate shortest distance (in adjacent Regions) between two regions.

    BFS distance. Returns max_dist if unreachable.
    """
    if region_a == region_b:
        return 0
    visited = {region_a}
    frontier = [region_a]
    dist = 0
    while frontier and dist < max_dist:
        dist += 1
        next_frontier = []
        for r in frontier:
            for adj in get_adjacent(r, scenario):
                if adj == region_b:
                    return dist
                if adj not in visited:
                    visited.add(adj)
                    next_frontier.append(adj)
        frontier = next_frontier
    return max_dist


def _count_adjacent_arverni_regions(state, region, scenario):
    """Count Regions within distance 1 that have Arverni pieces.

    Per §8.7.4 step 2: "within a distance of one Region from the most
    Regions possible that have Arverni pieces."
    """
    count = 0
    # Include the region itself
    if count_pieces(state, region, ARVERNI) > 0:
        count += 1
    for adj in get_adjacent(region, scenario):
        if count_pieces(state, adj, ARVERNI) > 0:
            count += 1
    return count


# ============================================================================
# NODE FUNCTIONS — Main flowchart
# ============================================================================

def node_v1(state):
    """V1: Vercingetorix or 10+ Arverni Warbands where Romans/Aedui have
    an Ally, Citadel, Legion, or ≥4 pieces?

    Per §8.7.1.

    Returns:
        ("Yes", threat_regions) or ("No", []).
    """
    scenario = state["scenario"]
    threat_regions = _get_threat_regions(state, scenario)
    if threat_regions:
        return ("Yes", threat_regions)
    return ("No", [])


def node_v2(state):
    """V2: Arverni by Sequence of Play may use Event?

    Per §8.7.2.

    Returns:
        "Yes" or "No".
    """
    return "Yes" if state.get("can_play_event", False) else "No"


def node_v2b(state):
    """V2b: Event Ineffective, Capability in final year, or 'No Arverni'?

    Per §8.7.2: Check all decline conditions.

    Returns:
        "Yes" (decline, go to Rally) or "No" (proceed to Carnyx check).
    """
    card_id = state.get("current_card_id")
    if card_id is None:
        return "Yes"

    if should_decline_event(state, card_id, ARVERNI):
        return "Yes"

    # Check specific instructions that might render ineffective
    scenario = state["scenario"]
    instr = get_event_instruction(card_id, ARVERNI, scenario)
    if instr and instr.action == NO_EVENT:
        return "Yes"

    return "No"


def node_v2c(state):
    """V2c: Roll of 1-4 or 'Auto 1-4' (Carnyx)?

    Per §8.7.2: Check if the card is "Auto 1-4" (Carnyx). If not, roll.
    If Carnyx or roll 1-4 → play Event. If roll 5-6 → Rally.

    Returns:
        "Yes" (play Event) or "No" (go to Rally).
    """
    card_id = state.get("current_card_id")
    scenario = state["scenario"]

    # Check for Auto 1-4 (Carnyx symbol)
    instr = get_event_instruction(card_id, ARVERNI, scenario)
    if instr and instr.action == PLAY_EVENT and instr.instruction:
        if "Auto 1-4" in instr.instruction:
            return "Yes"

    # Roll the die — §8.7.2
    die_result = roll_die(state)
    if die_result <= 4:
        return "Yes"

    return "No"


def node_v3(state):
    """V3: 0-8 Arverni Warbands on map, or Rally would place 2+ Allies/Citadels
    or 6+ pieces?

    Per §8.7.3.

    Returns:
        "Yes" (Rally) or "No" (proceed to March/Raid check).
    """
    scenario = state["scenario"]

    # Check: fewer than 9 Warbands on map
    wb_on_map = _count_arverni_warbands_on_map(state)
    if wb_on_map < 9:
        return "Yes"

    # Check: Rally would place 2+ Citadels/Allies or 6+ pieces
    estimate = _estimate_rally_placements(state, scenario)
    if estimate["citadels"] + estimate["allies"] >= 2:
        return "Yes"
    if estimate["total"] >= 6:
        return "Yes"

    return "No"


def node_v4(state):
    """V4: 0-5 Arverni Allies+Citadels on map, or 6+ Warbands Available?

    Per §8.7.4.

    Returns:
        "Yes" (March to spread) or "No" (proceed to Raid/March mass).
    """
    ac_on_map = _count_arverni_allies_citadels_on_map(state)
    if ac_on_map < 6:
        return "Yes"

    avail_wb = get_available(state, ARVERNI, WARBAND)
    if avail_wb >= 6:
        return "Yes"

    return "No"


def node_v5(state):
    """V5: Arverni have 0-3 Resources and roll 1-4?

    Per §8.7.5.

    Returns:
        "Yes" (Raid) or "No" (March to mass).
    """
    resources = state.get("resources", {}).get(ARVERNI, 0)
    if resources >= 4:
        return "No"

    die_result = roll_die(state)
    if die_result <= 4:
        return "Yes"

    return "No"


# ============================================================================
# PROCESS NODES
# ============================================================================

def node_v_event(state):
    """V_EVENT: Execute Event.

    Per §8.7.2: Execute per §8.2 — use Shaded text (§8.2.2).
    Check Instructions (§8.2.1) if gray laurels on card's Arverni symbol.

    Returns:
        Action dict for Event execution.
    """
    card_id = state.get("current_card_id")
    scenario = state["scenario"]
    preference = get_dual_use_preference(ARVERNI, scenario)
    instr = get_event_instruction(card_id, ARVERNI, scenario)

    return _make_action(
        ACTION_EVENT,
        details={
            "card_id": card_id,
            "text_preference": preference,
            "instruction": instr.instruction if instr else None,
        },
    )


def node_v_battle(state):
    """V_BATTLE: Battle process.

    Per §8.7.1: Battle where Loss on Legion AND/OR Arverni Losses < enemy's
    — AND no Loss on Vercingetorix. If Vercingetorix meets condition but
    won't Battle, March instead. Check Ambush, Devastate/Entreat.

    Returns:
        Action dict for Battle, or redirects to March (threat).
    """
    scenario = state["scenario"]
    non_players = state.get("non_player_factions", set())
    threat_regions = _get_threat_regions(state, scenario)

    if not threat_regions:
        return node_v_march_threat(state)

    # Step 1: Check Vercingetorix — §8.7.1
    verc_region = _vercingetorix_region(state)
    if verc_region and verc_region in threat_regions:
        # Check if Vercingetorix can Battle here
        can_verc_battle = False
        for enemy in (ROMANS, AEDUI):
            if count_pieces(state, verc_region, enemy) == 0:
                continue
            # Check Caesar ratio — §8.7.1 step 4a
            if enemy == ROMANS and _caesar_in_region(state, verc_region):
                if not _check_caesar_ratio(state, verc_region):
                    continue
            if _can_battle_in_region(state, verc_region, scenario, enemy):
                can_verc_battle = True
                break

        if not can_verc_battle:
            # "the Arverni do not Battle at all, but instead March" — §8.7.1
            return node_v_march_threat(state)

    # Step 2: Build battle plan — pay Resources as selecting — §8.7.1
    battle_plan = []

    # First: Vercingetorix fights Romans (step 4) — §8.7.1
    if verc_region and verc_region in threat_regions:
        if count_pieces(state, verc_region, ROMANS) > 0:
            # Check Caesar ratio
            if _caesar_in_region(state, verc_region):
                if _check_caesar_ratio(state, verc_region):
                    if _can_battle_in_region(state, verc_region, scenario, ROMANS):
                        battle_plan.append({
                            "region": verc_region,
                            "target": ROMANS,
                            "is_trigger": True,
                        })
            else:
                if _can_battle_in_region(state, verc_region, scenario, ROMANS):
                    battle_plan.append({
                        "region": verc_region,
                        "target": ROMANS,
                        "is_trigger": True,
                    })

    # Then other trigger regions — §8.7.1 (triggering enemies)
    for region in threat_regions:
        if any(bp["region"] == region for bp in battle_plan):
            continue
        for enemy in (ROMANS, AEDUI):
            if count_pieces(state, region, enemy) == 0:
                continue
            if _can_battle_in_region(state, region, scenario, enemy):
                battle_plan.append({
                    "region": region,
                    "target": enemy,
                    "is_trigger": True,
                })
                break

    # Step 5: Additional Battles vs Romans, Aedui, player Belgae — §8.7.1
    # "spaces that did not trigger the Battle Command above"
    # "Non-player Arverni do not Battle against Non-player Belgae or Germans."
    playable = get_playable_regions(scenario, state.get("capabilities"))
    for region in playable:
        if any(bp["region"] == region for bp in battle_plan):
            continue
        if count_pieces(state, region, ARVERNI) == 0:
            continue
        for enemy in (ROMANS, AEDUI):
            if count_pieces(state, region, enemy) == 0:
                continue
            if _can_battle_in_region(state, region, scenario, enemy):
                battle_plan.append({
                    "region": region,
                    "target": enemy,
                    "is_trigger": False,
                })
                break
        else:
            # Check player Belgae only — §8.7.1 NOTE
            if BELGAE not in non_players:
                if count_pieces(state, region, BELGAE) > 0:
                    if _can_battle_in_region(state, region, scenario, BELGAE):
                        battle_plan.append({
                            "region": region,
                            "target": BELGAE,
                            "is_trigger": False,
                        })

    if not battle_plan:
        return node_v_march_threat(state)

    # Determine SA — §8.7.1
    sa, sa_regions = _determine_battle_sa(state, battle_plan, scenario)

    return _make_action(
        ACTION_BATTLE,
        regions=[bp["region"] for bp in battle_plan],
        sa=sa,
        sa_regions=sa_regions,
        details={"battle_plan": battle_plan, "march_type": None},
    )


def _determine_battle_sa(state, battle_plan, scenario):
    """Determine SA for Battle: Ambush, then Devastate, then Entreat.

    Per §8.7.1: Check Ambush first. If no Ambush, Devastate/Entreat
    before Battle.

    Returns:
        (sa_action, sa_regions) tuple.
    """
    ambush_regions = _check_ambush(state, battle_plan, scenario)
    if ambush_regions:
        return (SA_ACTION_AMBUSH, ambush_regions)

    # No Ambush → Devastate before Battle, or Entreat — §8.7.1
    devastate_regions = _check_devastate(state, scenario)
    if devastate_regions:
        return (SA_ACTION_DEVASTATE, devastate_regions)

    entreat_result = _check_entreat(state, scenario)
    if entreat_result:
        return (SA_ACTION_ENTREAT, entreat_result)

    return (SA_ACTION_NONE, [])


def node_v_march_threat(state):
    """V_MARCH_THREAT: March (from threat).

    Per §8.7.1: March if no Battle.
    1. Vercingetorix with all Warbands to Region with most Arverni.
    2. Toward Vercingetorix with all Warbands EXCEPT 1 per origin Region.

    Returns:
        Action dict for March, including Devastate/Entreat SA.
    """
    scenario = state["scenario"]
    verc_region = _vercingetorix_region(state)
    playable = get_playable_regions(scenario, state.get("capabilities"))

    march_plan = {
        "origins": [],
        "destinations": [],
        "type": MARCH_THREAT,
    }

    # Step 1: Vercingetorix Marches to region with most Arverni pieces
    if verc_region:
        best_dest = None
        best_count = -1
        for region in playable:
            if region == verc_region:
                continue
            # Check Harassment restrictions — §8.7.1
            # "no more than three Losses that March and none on Vercingetorix"
            arverni_there = count_pieces(state, region, ARVERNI)
            if arverni_there > best_count:
                best_count = arverni_there
                best_dest = region

        if best_dest is not None:
            march_plan["origins"].append(verc_region)
            march_plan["destinations"].append(best_dest)

    # Step 2: Move all other Warbands toward Vercingetorix, leave 1 per origin
    verc_dest = march_plan["destinations"][0] if march_plan["destinations"] else verc_region
    if verc_dest:
        for region in playable:
            if region == verc_dest:
                continue
            if region == verc_region:
                continue
            arverni_wb = count_pieces(state, region, ARVERNI, WARBAND)
            if arverni_wb > 1:
                march_plan["origins"].append(region)

    # Determine SA: Devastate before March (if marching away from threat),
    # otherwise after — §8.7.1
    sa, sa_regions = _determine_march_sa(state, scenario, before_march=True)

    return _make_action(
        ACTION_MARCH,
        regions=march_plan["destinations"],
        sa=sa,
        sa_regions=sa_regions,
        details={"march_plan": march_plan},
    )


def node_v_rally(state):
    """V_RALLY: Rally process.

    Per §8.7.3: Rally wherever able to place a piece:
    1. Citadels (replace Allies in Cities)
    2. Allies
    3. Most Warbands

    IF NONE: If <9 Warbands but couldn't Rally, March per §8.7.4.

    Returns:
        Action dict for Rally, or redirects to March (spread).
    """
    scenario = state["scenario"]
    playable = get_playable_regions(scenario, state.get("capabilities"))

    rally_plan = {
        "citadels": [],
        "allies": [],
        "warbands": [],
    }

    avail_citadels = get_available(state, ARVERNI, CITADEL)
    avail_allies = get_available(state, ARVERNI, ALLY)
    avail_warbands = get_available(state, ARVERNI, WARBAND)

    # Step 1: Citadels — replace Allies in Cities
    for region in playable:
        if avail_citadels <= 0:
            break
        tribes = get_tribes_in_region(region, scenario)
        for tribe in tribes:
            if avail_citadels <= 0:
                break
            tribe_info = state["tribes"].get(tribe, {})
            if (tribe_info.get("allied_faction") == ARVERNI
                    and is_city_tribe(tribe)):
                rally_plan["citadels"].append({
                    "region": region, "tribe": tribe,
                })
                avail_citadels -= 1
                avail_allies += 1  # Freed Ally returns to Available

    # Step 2: Allies — place all possible
    for region in playable:
        if avail_allies <= 0:
            break
        tribes = get_tribes_in_region(region, scenario)
        for tribe in tribes:
            if avail_allies <= 0:
                break
            tribe_info = state["tribes"].get(tribe, {})
            if tribe_info.get("allied_faction") is not None:
                continue
            # Must have Arverni presence for Rally
            if (count_pieces(state, region, ARVERNI) > 0
                    or is_controlled_by(state, region, ARVERNI)):
                rally_plan["allies"].append({
                    "region": region, "tribe": tribe,
                })
                avail_allies -= 1

    # Step 3: Warbands — place most possible
    for region in playable:
        if avail_warbands <= 0:
            break
        has_base = False
        tribes = get_tribes_in_region(region, scenario)
        for tribe in tribes:
            tribe_info = state["tribes"].get(tribe, {})
            if tribe_info.get("allied_faction") == ARVERNI:
                has_base = True
                break
        if count_pieces(state, region, ARVERNI, CITADEL) > 0:
            has_base = True
        if is_controlled_by(state, region, ARVERNI):
            has_base = True

        if has_base:
            rally_plan["warbands"].append(region)
            avail_warbands -= 1

    total_placed = (len(rally_plan["citadels"]) + len(rally_plan["allies"])
                    + len(rally_plan["warbands"]))

    # IF NONE: If <9 Warbands but couldn't Rally → March per §8.7.4
    if total_placed == 0:
        wb_on_map = _count_arverni_warbands_on_map(state)
        if wb_on_map < 9:
            return node_v_march_spread(state)
        # Otherwise pass downstream (will reach Raid or March Mass)
        return node_v_march_spread(state)

    # SA: Devastate or Entreat after Rally — §8.7.3
    sa, sa_regions = _determine_march_sa(state, scenario, before_march=False)

    return _make_action(
        ACTION_RALLY,
        regions=list({r for entry in rally_plan["citadels"]
                      for r in [entry["region"]]}
                     | {r for entry in rally_plan["allies"]
                        for r in [entry["region"]]}
                     | set(rally_plan["warbands"])),
        sa=sa,
        sa_regions=sa_regions,
        details={"rally_plan": rally_plan},
    )


def node_v_march_spread(state):
    """V_MARCH_SPREAD: March (to spread).

    Per §8.7.4: March from fewest Regions. Leave 1 Arverni Warband per origin.
    Lose no Arverni Control.
    1. Add 1 Hidden Arverni to each Region where none.
    2. Leader with Warbands to replace Roman/Aedui Control — NOT Bibracte.

    IF NONE: Raid per §8.7.5.

    Returns:
        Action dict for March, or redirects to Raid.
    """
    scenario = state["scenario"]
    playable = get_playable_regions(scenario, state.get("capabilities"))

    # NOTE: No Frost check here — §8.7.4 does not mention Frost.
    # Frost is a fallback condition only on V_MARCH_MASS (§8.7.6:
    # "If none or Frost or no Leader → V_RAID").

    march_plan = {
        "spread_destinations": [],
        "control_destination": None,
        "origins": [],
        "type": MARCH_SPREAD,
    }

    # Step 1: Add 1 Hidden Arverni to each Region with no Hidden Arverni
    # — §8.7.4: "add one Hidden Arverni to each Region possible that
    # currently has no Hidden Arverni (without removing the last from any
    # origin)."
    # A region is reachable if it is adjacent to an origin with 2+ Arverni
    # Warbands (so one can March in while leaving at least 1 behind).
    # "from fewest Regions able" — track which origins serve which
    # destinations and prefer origins that serve multiple destinations.
    playable_set = set(playable)
    dest_to_origins = {}
    for region in playable:
        hidden_arverni = count_pieces_by_state(
            state, region, ARVERNI, WARBAND, HIDDEN)
        if hidden_arverni > 0:
            continue  # Already has Hidden Arverni
        # Find adjacent origins with 2+ Arverni Warbands
        possible_origins = []
        for adj in get_adjacent(region, scenario):
            if adj not in playable_set:
                continue
            adj_wb = count_pieces(state, adj, ARVERNI, WARBAND)
            if adj_wb >= 2:
                possible_origins.append(adj)
        if possible_origins:
            dest_to_origins[region] = possible_origins

    # Greedy assignment: pick origins that cover the most destinations
    # to satisfy "from fewest Regions able"
    remaining_dests = set(dest_to_origins.keys())
    chosen_origins = set()
    while remaining_dests:
        # Count how many remaining dests each origin can serve
        origin_coverage = {}
        for dest in remaining_dests:
            for orig in dest_to_origins[dest]:
                origin_coverage.setdefault(orig, set()).add(dest)
        if not origin_coverage:
            break
        # Pick origin that covers the most destinations
        best_origin = max(origin_coverage, key=lambda o: len(origin_coverage[o]))
        chosen_origins.add(best_origin)
        covered = origin_coverage[best_origin]
        remaining_dests -= covered
        march_plan["spread_destinations"].extend(sorted(covered))

    march_plan["origins"].extend(sorted(chosen_origins))

    # Step 2: Leader with Warbands to take Arverni Control of Roman/Aedui
    # Controlled region — NOT Bibracte (AEDUI_REGION) — §8.7.4
    verc_region = _vercingetorix_region(state)
    if verc_region:
        best_dest = None
        best_adj_count = -1
        for region in playable:
            if region == AEDUI_REGION:
                continue  # NOT Bibracte — §8.7.4
            if region == verc_region:
                continue
            # Must have Roman or Aedui Control
            if (not is_controlled_by(state, region, ROMANS)
                    and not is_controlled_by(state, region, AEDUI)):
                continue
            # Within 1 Region of most Regions with Arverni able — §8.7.4
            adj_arverni = _count_adjacent_arverni_regions(state, region, scenario)
            if adj_arverni > best_adj_count:
                best_adj_count = adj_arverni
                best_dest = region

        if best_dest is not None:
            march_plan["control_destination"] = best_dest

    has_any_march = (march_plan["spread_destinations"]
                     or march_plan["control_destination"] is not None)

    if not has_any_march:
        return node_v_raid(state)

    # SA: Devastate or Entreat after March — §8.7.4
    sa, sa_regions = _determine_march_sa(state, scenario, before_march=False)

    all_dests = list(march_plan["spread_destinations"])
    if march_plan["control_destination"]:
        all_dests.append(march_plan["control_destination"])

    return _make_action(
        ACTION_MARCH,
        regions=all_dests,
        sa=sa,
        sa_regions=sa_regions,
        details={"march_plan": march_plan},
    )


def node_v_raid(state):
    """V_RAID: Raid process.

    Per §8.7.5: Raid if would gain 2+ Resources total.
    1. Versus Factions: (1) Romans (2) Aedui (3) Belgae
    2. In non-Devastated Regions, versus no Faction.

    IF NONE: Pass.

    Returns:
        Action dict for Raid, or Pass.
    """
    scenario = state["scenario"]
    enough, raid_regions = _would_raid_gain_enough(state, scenario)

    if not enough:
        return _make_action(ACTION_PASS)

    # SA: Devastate or Entreat after Raid — §8.7.5
    sa, sa_regions = _determine_march_sa(state, scenario, before_march=False)

    return _make_action(
        ACTION_RAID,
        regions=[r["region"] for r in raid_regions],
        sa=sa,
        sa_regions=sa_regions,
        details={"raid_plan": raid_regions},
    )


def node_v_march_mass(state):
    """V_MARCH_MASS: March (to mass).

    Per §8.7.6: March with Leader and as many Warbands as can reach:
    1. Take Arverni Control of 1 Region with a Legion — but Caesar only
       if >2:1 mobile ratio.
    2. If none, mass most Arverni in 1 Region adjacent to a Legion,
       leaving 1 per origin.

    IF NONE (Frost, no Leader): Raid per §8.7.5.

    Returns:
        Action dict for March, or redirects to Raid.
    """
    scenario = state["scenario"]
    playable = get_playable_regions(scenario, state.get("capabilities"))
    verc_region = _vercingetorix_region(state)

    # IF NONE: no Leader or Frost — §8.7.6
    if verc_region is None or is_frost_active(state):
        return node_v_raid(state)

    march_plan = {
        "destination": None,
        "origins": [],
        "type": MARCH_MASS,
    }

    # Step 1: Add Arverni Control to a Region with a Legion — §8.7.6
    best_dest = None
    for region in playable:
        if region == verc_region:
            continue
        if is_controlled_by(state, region, ARVERNI):
            continue  # Already have Control
        if count_pieces(state, region, ROMANS, LEGION) == 0:
            continue  # No Legion

        # Caesar check — only if >2:1 ratio after move
        if _caesar_in_region(state, region):
            # Estimate: Vercingetorix + all Warbands from his region
            wb_available = count_pieces(state, verc_region, ARVERNI, WARBAND)
            arverni_after = wb_available + 1  # +1 for Vercingetorix
            roman_mobile = count_mobile_pieces(state, region, ROMANS)
            if arverni_after <= 2 * roman_mobile:
                continue

        best_dest = region
        break

    if best_dest:
        march_plan["destination"] = best_dest
        march_plan["origins"].append(verc_region)
    else:
        # Step 2: Mass most Arverni in 1 Region adjacent to a Legion — §8.7.6
        best_dest = None
        best_mass = -1
        for region in playable:
            # Must be adjacent to at least one Legion
            has_adj_legion = False
            for adj in get_adjacent(region, scenario):
                if count_pieces(state, adj, ROMANS, LEGION) > 0:
                    has_adj_legion = True
                    break
            if not has_adj_legion:
                continue

            # Count Arverni pieces that could gather here
            arverni_here = count_pieces(state, region, ARVERNI)
            # Add pieces that could March in
            for adj in get_adjacent(region, scenario):
                adj_wb = count_pieces(state, adj, ARVERNI, WARBAND)
                if adj_wb > 1:
                    arverni_here += adj_wb - 1  # Leave 1 per origin

            if arverni_here > best_mass:
                best_mass = arverni_here
                best_dest = region

        if best_dest:
            march_plan["destination"] = best_dest
            march_plan["origins"].append(verc_region)

    if march_plan["destination"] is None:
        return node_v_raid(state)

    # SA: Devastate or Entreat after March — §8.7.6
    sa, sa_regions = _determine_march_sa(state, scenario, before_march=False)

    return _make_action(
        ACTION_MARCH,
        regions=[march_plan["destination"]],
        sa=sa,
        sa_regions=sa_regions,
        details={"march_plan": march_plan},
    )


# ============================================================================
# SPECIAL ABILITY NODES
# ============================================================================

def _check_ambush(state, battle_plan, scenario):
    """V_AMBUSH: Determine Ambush regions.

    Per §8.7.1: Ambush in 1st Battle only if Retreat could lessen removals
    AND/OR Counterattack Loss to Arverni is possible. If Ambushed in 1st
    Battle, Ambush in all others.

    Returns:
        List of Ambush regions, or empty.
    """
    if not battle_plan:
        return []

    first_battle = battle_plan[0]
    region = first_battle["region"]
    enemy = first_battle["target"]

    # Check if Ambush is needed in 1st Battle — §8.7.1
    should_ambush_first = False

    # (a) Retreat could lessen removals
    enemy_mobile = count_mobile_pieces(state, region, enemy)
    if enemy_mobile > 0:
        # If enemy has mobile pieces that could Retreat, Ambush prevents that
        should_ambush_first = True

    # (b) Counterattack could inflict Loss on Arverni
    # "A defending Legion or Leader would meet the 2nd requirement"
    if count_pieces(state, region, enemy, LEGION) > 0:
        should_ambush_first = True
    if get_leader_in_region(state, region, enemy) is not None:
        should_ambush_first = True

    if not should_ambush_first:
        return []

    # If Ambushed in 1st Battle, Ambush in all others — §8.7.1
    return [bp["region"] for bp in battle_plan]


def _check_devastate(state, scenario):
    """V_DEVASTATE: Determine Devastate regions.

    Per §8.7.1: Devastate wherever able that will force removal of a Legion
    or two Auxilia or at least as many Roman+Aedui pieces as Arverni.

    Returns:
        List of Devastate regions, or empty.
    """
    playable = get_playable_regions(scenario, state.get("capabilities"))
    devastate_regions = []

    for region in playable:
        if count_pieces(state, region, ARVERNI) == 0:
            continue
        # Can't Devastate if already Devastated
        if state["spaces"].get(region, {}).get("devastated", False):
            continue

        # Must be able to Devastate (have enough pieces, per §4.3.1)
        # Simplified: Arverni must have Warbands here
        if count_pieces(state, region, ARVERNI, WARBAND) == 0:
            continue

        # Check conditions — §8.7.1
        roman_legions = count_pieces(state, region, ROMANS, LEGION)
        roman_auxilia = count_pieces(state, region, ROMANS, AUXILIA)
        roman_pieces = count_pieces(state, region, ROMANS)
        aedui_pieces = count_pieces(state, region, AEDUI)
        arverni_pieces = count_pieces(state, region, ARVERNI)

        enemy_total = roman_pieces + aedui_pieces

        # Force removal of a Legion
        if roman_legions > 0:
            devastate_regions.append(region)
            continue
        # Force removal of 2 Auxilia
        if roman_auxilia >= 2:
            devastate_regions.append(region)
            continue
        # At least as many Roman+Aedui pieces as Arverni
        if enemy_total >= 1 and enemy_total >= arverni_pieces:
            devastate_regions.append(region)

    return devastate_regions


def _check_entreat(state, scenario):
    """V_ENTREAT: Determine Entreat targets.

    Per §8.7.1: Replace enemy Allies with Arverni, then replace enemy
    pieces with Arverni, then remove (once no Arverni Available).

    If Arverni Marched into/out of Britannia: no SA — §4.1.3.

    Returns:
        List of Entreat action dicts, or empty.
    """
    playable = get_playable_regions(scenario, state.get("capabilities"))
    entreat_actions = []

    avail_allies = get_available(state, ARVERNI, ALLY)
    avail_warbands = get_available(state, ARVERNI, WARBAND)
    non_players = state.get("non_player_factions", set())

    # Step 1: Replace enemy Allies with Arverni Allies — §8.7.1
    # Priority: (1) Aedui, (2) Belgic, (3) Germanic
    for target_faction in (AEDUI, BELGAE, GERMANS):
        for region in playable:
            if avail_allies <= 0:
                break
            if count_pieces(state, region, ARVERNI) == 0:
                continue
            tribes = get_tribes_in_region(region, scenario)
            for tribe in tribes:
                if avail_allies <= 0:
                    break
                tribe_info = state["tribes"].get(tribe, {})
                if tribe_info.get("allied_faction") == target_faction:
                    entreat_actions.append({
                        "action": "replace_ally",
                        "region": region,
                        "tribe": tribe,
                        "target_faction": target_faction,
                    })
                    avail_allies -= 1

    # Step 2: Replace Auxilia/Aedui Warbands with Arverni Warbands — §8.7.1
    # (1) Auxilia, (2) Aedui Warbands only
    for target_faction, target_type in ((ROMANS, AUXILIA), (AEDUI, WARBAND)):
        for region in playable:
            if avail_warbands <= 0:
                break
            if count_pieces(state, region, ARVERNI) == 0:
                continue
            target_count = count_pieces(state, region, target_faction, target_type)
            if target_count > 0:
                entreat_actions.append({
                    "action": "replace_piece",
                    "region": region,
                    "target_faction": target_faction,
                    "target_type": target_type,
                })
                avail_warbands -= 1

    # Step 3: Remove (once no Arverni Available) — §8.7.1
    # (1) Auxilia, (2) Aedui Warbands, (3) Player Allies
    if avail_warbands <= 0:
        for target_faction, target_type in ((ROMANS, AUXILIA), (AEDUI, WARBAND)):
            for region in playable:
                if count_pieces(state, region, ARVERNI) == 0:
                    continue
                target_count = count_pieces(
                    state, region, target_faction, target_type)
                if target_count > 0:
                    entreat_actions.append({
                        "action": "remove_piece",
                        "region": region,
                        "target_faction": target_faction,
                        "target_type": target_type,
                    })

        # Player Allies only — §8.7.1
        for target_faction in (AEDUI, BELGAE, ROMANS):
            if target_faction in non_players:
                continue  # Only player Factions
            for region in playable:
                if count_pieces(state, region, ARVERNI) == 0:
                    continue
                tribes = get_tribes_in_region(region, scenario)
                for tribe in tribes:
                    tribe_info = state["tribes"].get(tribe, {})
                    if tribe_info.get("allied_faction") == target_faction:
                        entreat_actions.append({
                            "action": "remove_ally",
                            "region": region,
                            "tribe": tribe,
                            "target_faction": target_faction,
                        })

    return entreat_actions


def _determine_march_sa(state, scenario, *, before_march=False):
    """Determine SA for March/Rally/Raid: Devastate, then Entreat.

    Per §8.7.1: Devastate before March (threat) if able, otherwise after.
    Devastate before Battle, after other March/Rally/Raid.
    Entreat follows same timing rules.

    Args:
        state: Game state dict.
        scenario: Scenario constant.
        before_march: True if this is a March away from threat.

    Returns:
        (sa_action, sa_regions) tuple.
    """
    devastate_regions = _check_devastate(state, scenario)
    if devastate_regions:
        return (SA_ACTION_DEVASTATE, devastate_regions)

    entreat_result = _check_entreat(state, scenario)
    if entreat_result:
        return (SA_ACTION_ENTREAT,
                [e.get("region") for e in entreat_result if "region" in e])

    return (SA_ACTION_NONE, [])


# ============================================================================
# WINTER NODES
# ============================================================================

def node_v_quarters(state):
    """V_QUARTERS: Quarters Phase.

    Per §8.7.7:
    - Leave Devastated if no Ally/Citadel.
    - Move Leader/Warband group to join most, end next to most
      Regions with Arverni able; leave 1+ OR for Control.

    Returns:
        Quarters action details dict.
    """
    scenario = state["scenario"]
    playable = get_playable_regions(scenario, state.get("capabilities"))

    quarters_plan = {
        "leave_devastated": [],
        "leader_move": None,
    }

    # Step 1: Leave Devastated Regions with no Ally/Citadel — §8.7.7
    for region in playable:
        if count_pieces(state, region, ARVERNI) == 0:
            continue
        is_devastated = state["spaces"].get(region, {}).get("devastated", False)
        if not is_devastated:
            continue
        # Check for Ally or Citadel
        has_ally = False
        tribes = get_tribes_in_region(region, scenario)
        for tribe in tribes:
            if state["tribes"].get(tribe, {}).get("allied_faction") == ARVERNI:
                has_ally = True
                break
        has_citadel = count_pieces(state, region, ARVERNI, CITADEL) > 0
        if not has_ally and not has_citadel:
            # Find adjacent Arverni-Controlled region
            for adj in get_adjacent(region, scenario):
                if is_controlled_by(state, adj, ARVERNI):
                    quarters_plan["leave_devastated"].append({
                        "from": region, "to": adj,
                    })
                    break

    # Step 2: Move Leader/group to join most Warbands, near most
    # Regions with Arverni — §8.7.7
    verc_region = _vercingetorix_region(state)
    if verc_region:
        best_dest = None
        best_wb_count = -1
        best_adj_count = -1

        candidates = [verc_region] + list(get_adjacent(verc_region, scenario))
        for dest in candidates:
            wb_count = count_pieces(state, dest, ARVERNI, WARBAND)
            if dest == verc_region:
                pass  # Already there
            adj_count = _count_adjacent_arverni_regions(state, dest, scenario)
            if (wb_count > best_wb_count
                    or (wb_count == best_wb_count
                        and adj_count > best_adj_count)):
                best_wb_count = wb_count
                best_adj_count = adj_count
                best_dest = dest

        if best_dest and best_dest != verc_region:
            quarters_plan["leader_move"] = {
                "from": verc_region, "to": best_dest,
            }

    return quarters_plan


def node_v_spring(state):
    """V_SPRING: Spring Phase.

    Per §8.3.2 / §6.6: Place Leader at most Arverni.

    Returns:
        Spring action details dict, or None if nothing to do.
    """
    verc_region = _vercingetorix_region(state)
    if verc_region is not None:
        return None  # Vercingetorix already on map

    best_region = get_leader_placement_region(state, ARVERNI)
    if best_region:
        return {"place_leader": VERCINGETORIX, "region": best_region}
    return None


# ============================================================================
# AGREEMENTS AND ELITE
# ============================================================================

def node_v_agreements(state, requesting_faction, request_type):
    """V_AGREEMENTS: Agreement decisions.

    Per §8.4.2:
    - Never agree to Retreat, Supply, Quarters, or transfer Resources.
    - Always Harass Romans.

    Args:
        state: Game state dict.
        requesting_faction: Faction making the request.
        request_type: "supply_line", "retreat", "quarters", "resources",
                      "harassment".

    Returns:
        True if Arverni agree.
    """
    if request_type == "harassment":
        # Always Harass Romans — §8.4.2
        if requesting_faction == ROMANS:
            return True
        return False

    # Never agree to anything else — §8.4.2
    return False


def node_v_elite(state, region):
    """V_ELITE: Vercingetorix's Elite Capability handling.

    Per §8.7.8: If shaded Capability is in effect, take Battle Losses
    first by rolling against Warbands that take Losses as Legions.

    Args:
        state: Game state dict.
        region: Battle region.

    Returns:
        True if Elite Warbands should absorb Losses first.
    """
    capabilities = state.get("capabilities", {})
    # Check if shaded Vercingetorix's Elite is active
    return capabilities.get("vercingetorix_elite_shaded", False)


# ============================================================================
# MAIN FLOWCHART DRIVER
# ============================================================================

def execute_arverni_turn(state):
    """Walk the Arverni bot flowchart and return the chosen action.

    Implements the full decision tree: V1 → V2 → V3 → V4 → V5 and all
    process nodes.

    The Arverni bot is base-game-only. Raises BotDispatchError if called
    in an Ariovistus scenario.

    Args:
        state: Game state dict.

    Returns:
        Action dict describing the Arverni bot's decision.
    """
    scenario = state["scenario"]

    # Scenario isolation — Arverni bot is base-game-only
    if scenario not in BASE_SCENARIOS:
        raise BotDispatchError(
            f"Arverni bot cannot run in scenario '{scenario}'. "
            f"Arverni are game-run via A6.2 in Ariovistus."
        )

    # §8.1.2: Upgrade Limited Command from SoP
    if state.get("limited_by_sop", False):
        pass  # NP gets full Command + SA — upgrade is implicit

    # V1: Battle or March under Threat?
    v1_result, threat_regions = node_v1(state)

    if v1_result == "Yes":
        # Try Battle, may redirect to March (threat)
        return node_v_battle(state)

    # V2: Can play Event by SoP?
    v2_result = node_v2(state)
    if v2_result == "Yes":
        # V2b: Decline checks
        v2b_result = node_v2b(state)
        if v2b_result == "No":
            # V2c: Carnyx / die roll
            v2c_result = node_v2c(state)
            if v2c_result == "Yes":
                return node_v_event(state)
            # Rolled 5-6 → fall through to Rally

    # V3: Rally?
    v3_result = node_v3(state)
    if v3_result == "Yes":
        return node_v_rally(state)

    # V4: March to spread?
    v4_result = node_v4(state)
    if v4_result == "Yes":
        return node_v_march_spread(state)

    # V5: Raid (0-3 Resources and roll 1-4)?
    v5_result = node_v5(state)
    if v5_result == "Yes":
        return node_v_raid(state)

    # Default: March to mass — §8.7.6
    return node_v_march_mass(state)
