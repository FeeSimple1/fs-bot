"""
Non-Player Aedui flowchart — §8.6.

Every node from the Aedui bot flowchart (A1 through A_SUBORN, plus
A_QUARTERS, A_AGREEMENTS, A_DIVICIACUS) is a labeled function.

The Aedui bot runs in both base game and Ariovistus scenarios.
In Ariovistus, Chapter A8 modifications apply (swapping Arverni ↔ Germans
in targeting, Diviciacus leader, etc.).

Node functions return an action dict describing what the bot decided to do.
The dispatch loop calls execute_aedui_turn(state) which walks the flowchart.
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    FACTIONS, GALLIC_FACTIONS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    MOBILE_PIECES,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Scenarios
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    # Commands / SAs
    CMD_RALLY, CMD_MARCH, CMD_RAID, CMD_BATTLE,
    SA_TRADE, SA_SUBORN, SA_AMBUSH,
    # Leaders
    DIVICIACUS, CAESAR,
    # Regions
    AEDUI_REGION, BRITANNIA,
    # Events
    EVENT_UNSHADED,
    # Die
    DIE_MIN, DIE_MAX,
    # Suborn limits
    SUBORN_MAX_PIECES, SUBORN_MAX_ALLIES,
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
SA_ACTION_TRADE = "Trade"
SA_ACTION_SUBORN = "Suborn"
SA_ACTION_NONE = "No SA"


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
# HELPER: Aedui-specific board queries
# ============================================================================

def _diviciacus_region(state):
    """Find Diviciacus's region, or None.

    Diviciacus only exists in Ariovistus scenarios — A1.4.
    In base game, Aedui have no Leader (cap = 0).
    """
    return find_leader(state, AEDUI)


def _count_aedui_warbands_on_map(state):
    """Count total Aedui Warbands on map."""
    return count_on_map(state, AEDUI, WARBAND)


def _count_aedui_allies_citadels_on_map(state):
    """Count total Aedui Allies + Citadels on map."""
    return count_faction_allies_and_citadels(state, AEDUI)


def _aedui_at_victory(state):
    """Check if Aedui are currently at or exceeding their victory threshold.

    Per §7.2: Aedui win if they have more Allies + Citadels than any other
    faction. This checks the current state against the threshold.

    Returns:
        True if Aedui are at victory.
    """
    try:
        return check_victory(state, AEDUI)
    except Exception:
        return False


def _estimate_battle_losses(state, region, attacker, defender, scenario):
    """Estimate Attack Losses inflicted by attacker on defender.

    Per §3.3.4 / §3.2.4: Losses = Legions×1 + Warbands×½ + Leader×1
    + Auxilia×½, rounded down. Fort/Citadel halves.

    Returns:
        (losses_inflicted, losses_suffered) tuple — integers.
    """
    # Attacker forces
    atk_warbands = count_pieces(state, region, attacker, WARBAND)
    atk_auxilia = count_pieces(state, region, attacker, AUXILIA)
    atk_legions = count_pieces(state, region, attacker, LEGION)
    atk_leader = get_leader_in_region(state, region, attacker)

    attack_raw = (atk_legions * 1
                  + atk_warbands * 0.5
                  + (1 if atk_leader else 0)
                  + atk_auxilia * 0.5)

    # Defender Fort/Citadel halves Attack Losses — §3.3.4
    def_fort = count_pieces(state, region, defender, FORT)
    def_citadel = count_pieces(state, region, defender, CITADEL)
    if def_fort > 0 or def_citadel > 0:
        attack_raw = attack_raw / 2

    losses_inflicted = int(attack_raw)

    # Counterattack: defender hits back
    def_warbands = count_pieces(state, region, defender, WARBAND)
    def_auxilia = count_pieces(state, region, defender, AUXILIA)
    def_legions = count_pieces(state, region, defender, LEGION)
    def_leader = get_leader_in_region(state, region, defender)

    counter_raw = (def_legions * 1
                   + def_warbands * 0.5
                   + (1 if def_leader else 0)
                   + def_auxilia * 0.5)

    # Our Fort/Citadel halves Counterattack Losses — §3.3.4
    our_fort = count_pieces(state, region, attacker, FORT)
    our_citadel = count_pieces(state, region, attacker, CITADEL)
    if our_fort > 0 or our_citadel > 0:
        counter_raw = counter_raw / 2

    losses_suffered = int(counter_raw)

    return (losses_inflicted, losses_suffered)


def _would_force_loss_on_high_value(state, region, attacker, defender,
                                     scenario):
    """Check if Battle would force a Loss on enemy Leader, Ally, Citadel,
    or Legion — per §8.6.2.

    "accounting for which enemy the Aedui would Battle, any Aedui Ambush,
    a possible enemy Retreat, Aedui Resources, and so on"

    Returns:
        True if Battle is sure to inflict a Loss on a high-value target.
    """
    losses_inflicted, _ = _estimate_battle_losses(
        state, region, attacker, defender, scenario)

    if losses_inflicted <= 0:
        return False

    # Check if enemy has high-value targets that would take a Loss
    def_leader = get_leader_in_region(state, region, defender)
    def_legions = count_pieces(state, region, defender, LEGION)
    def_allies = count_pieces(state, region, defender, ALLY)
    def_citadels = count_pieces(state, region, defender, CITADEL)

    # Count total defender pieces to see if losses reach high-value targets
    # Losses remove pieces in defender's choice, but we check if losses
    # are enough that a high-value piece MUST be hit.
    # Lower-value pieces (Warbands/Auxilia) are removed first by defender.
    def_warbands = count_pieces(state, region, defender, WARBAND)
    def_auxilia = count_pieces(state, region, defender, AUXILIA)
    expendable = def_warbands + def_auxilia

    # If losses exceed expendable pieces, high-value targets MUST take hits
    if losses_inflicted > expendable:
        return True

    # If defender has ONLY high-value targets (no expendable), any loss hits them
    if expendable == 0 and (def_leader or def_legions > 0
                            or def_allies > 0 or def_citadels > 0):
        return True

    return False


def _get_battle_enemies(state, scenario):
    """Get enemy factions the Aedui will Battle.

    Per §8.6.2: "Battle against other Gauls or Germans; Battle against Romans
    only if the Aedui are at that moment exceeding their victory threshold."

    Returns:
        List of enemy faction constants.
    """
    enemies = []
    # Always battle Gauls and Germans (not self, not Romans unless at victory)
    targeting = get_faction_targeting_order(AEDUI, scenario)
    at_victory = _aedui_at_victory(state)

    for faction in targeting:
        if faction == ROMANS and not at_victory:
            continue
        enemies.append(faction)

    return enemies


# ============================================================================
# NODE FUNCTIONS — Main flowchart
# ============================================================================

def node_a1(state):
    """A1: Aedui 1st on upcoming but not current card, and roll 1-4?

    Per §8.6.1: Check faction order on current and next cards. If Aedui
    symbol is 1st on the next upcoming card but not on the currently played
    card (regardless of Eligibility cylinders), roll a die: on 1-4, Pass.

    Returns:
        "Yes" (Pass) or "No" (proceed to A2).
    """
    current_order = state.get("current_card_faction_order", [])
    next_order = state.get("next_card_faction_order", [])

    # Aedui 1st on upcoming card?
    aedui_first_next = (len(next_order) > 0 and next_order[0] == AEDUI)

    # Aedui NOT 1st on current card?
    aedui_first_current = (len(current_order) > 0
                           and current_order[0] == AEDUI)

    if aedui_first_next and not aedui_first_current:
        die_result = roll_die(state)
        if die_result <= 4:
            return "Yes"

    return "No"


def node_a2(state):
    """A2: Aedui by Sequence of Play may use Event?

    Per §8.6.1.

    Returns:
        "Yes" or "No".
    """
    return "Yes" if state.get("can_play_event", False) else "No"


def node_a3(state):
    """A3: Event Ineffective, Capability in final year, or 'No Aedui'?

    Per §8.6.1: Check all decline conditions, including Non-player
    Aedui Event Instructions (§8.2.1).

    Returns:
        "Yes" (decline, go to A4 Battle) or "No" (play Event).
    """
    card_id = state.get("current_card_id")
    if card_id is None:
        return "Yes"

    if should_decline_event(state, card_id, AEDUI):
        return "Yes"

    # Check specific instructions that might render ineffective
    scenario = state["scenario"]
    instr = get_event_instruction(card_id, AEDUI, scenario)
    if instr and instr.action == NO_EVENT:
        return "Yes"

    return "No"


def node_a4(state):
    """A4: Battle would force Loss on enemy Leader, Ally, Citadel, or Legion?

    Per §8.6.2: "If Aedui Battle in any Region would be sure to inflict a
    Loss on an enemy Leader, Ally, Citadel, or Legion (accounting for which
    enemy the Aedui would Battle, any Aedui Ambush, a possible enemy Retreat,
    Aedui Resources, and so on), the Aedui Battle."

    Returns:
        "Yes" (Battle) or "No" (proceed to A5).
    """
    scenario = state["scenario"]
    playable = get_playable_regions(scenario, state.get("capabilities"))
    enemies = _get_battle_enemies(state, scenario)

    for region in playable:
        if count_pieces(state, region, AEDUI) == 0:
            continue
        for enemy in enemies:
            if count_pieces(state, region, enemy) == 0:
                continue
            if _would_force_loss_on_high_value(
                    state, region, AEDUI, enemy, scenario):
                return "Yes"

    return "No"


def node_a5(state):
    """A5: 0-4 Aedui Warbands on map, or Rally would place Citadel, Ally,
    or 3+ pieces?

    Per §8.6.3.

    Returns:
        "Yes" (Rally) or "No" (proceed to A6).
    """
    scenario = state["scenario"]

    # Check: fewer than 5 Warbands on map
    wb_on_map = _count_aedui_warbands_on_map(state)
    if wb_on_map < 5:
        return "Yes"

    # Check: Rally would place Citadel, Ally, or 3+ pieces
    estimate = _estimate_rally_placements(state, scenario)
    if estimate["citadels"] > 0:
        return "Yes"
    if estimate["allies"] > 0:
        return "Yes"
    if estimate["total"] >= 3:
        return "Yes"

    return "No"


def node_a6(state):
    """A6: Aedui have 0-3 Resources and roll 1-4?

    Per §8.6.4.

    Returns:
        "Yes" (Raid) or "No" (March).
    """
    resources = state.get("resources", {}).get(AEDUI, 0)
    if resources >= 4:
        return "No"

    die_result = roll_die(state)
    if die_result <= 4:
        return "Yes"

    return "No"


# ============================================================================
# HELPER: Rally estimation
# ============================================================================

def _estimate_rally_placements(state, scenario):
    """Estimate how many pieces Rally would place.

    Per §8.6.3: Rally places Citadels, Allies, Warbands.

    Returns:
        Dict with "citadels", "allies", "warbands", "total" counts.
    """
    playable = get_playable_regions(scenario, state.get("capabilities"))
    citadels = 0
    allies = 0
    warbands = 0

    avail_citadels = get_available(state, AEDUI, CITADEL)
    avail_allies = get_available(state, AEDUI, ALLY)
    avail_warbands = get_available(state, AEDUI, WARBAND)

    # Step 1: Citadels — replace Allies in Cities with Citadels
    for region in playable:
        if avail_citadels <= 0:
            break
        tribes = get_tribes_in_region(region, scenario)
        for tribe in tribes:
            if avail_citadels <= 0:
                break
            tribe_info = state["tribes"].get(tribe, {})
            if (tribe_info.get("allied_faction") == AEDUI
                    and is_city_tribe(tribe)):
                citadels += 1
                avail_citadels -= 1
                # This frees up an Ally
                avail_allies += 1

    # Step 2: Allies — place wherever possible
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
            # Must have Aedui presence for Rally — §3.3.1
            if (count_pieces(state, region, AEDUI) > 0
                    or is_controlled_by(state, region, AEDUI)):
                allies += 1
                avail_allies -= 1

    # Step 3: Warbands — place most possible
    for region in playable:
        if avail_warbands <= 0:
            break
        has_base = False
        tribes = get_tribes_in_region(region, scenario)
        for tribe in tribes:
            tribe_info = state["tribes"].get(tribe, {})
            if tribe_info.get("allied_faction") == AEDUI:
                has_base = True
                break
        if count_pieces(state, region, AEDUI, CITADEL) > 0:
            has_base = True
        if is_controlled_by(state, region, AEDUI):
            has_base = True

        if has_base:
            warbands += 1
            avail_warbands -= 1

    return {
        "citadels": citadels,
        "allies": allies,
        "warbands": warbands,
        "total": citadels + allies + warbands,
    }


# ============================================================================
# HELPER: Raid estimation
# ============================================================================

def _would_raid_gain_enough(state, scenario):
    """Check if Raiding would gain at least 2 Resources total.

    Per §8.6.4: Raid if would gain 2+ Resources.
    Per §8.6.4: Raid priorities:
      1. Versus players at 0+ victory margin.
      2. Versus other non-Roman enemies.
      3. In non-Devastated Regions, versus no Faction (only).
    Per §8.6.4: "do not take Resources from Romans unless player at 0+
    victory."

    Returns:
        (bool, list of raid plan dicts).
    """
    playable = get_playable_regions(scenario, state.get("capabilities"))
    non_players = state.get("non_player_factions", set())
    total_gain = 0
    raid_plan = []

    # Build ordered target list per §8.6.4 priorities
    # 1. Players at 0+ victory margin
    # 2. Other non-Roman enemies
    # 3. No faction (non-Devastated)
    targeting = get_faction_targeting_order(AEDUI, scenario)

    # Determine which factions are valid raid targets
    raid_targets = []
    for target in targeting:
        if target == AEDUI:
            continue
        # Don't take from Romans unless player at 0+ victory — §8.6.4
        if target == ROMANS:
            if target in non_players:
                continue  # NP Romans — never raid
            try:
                margin = calculate_victory_margin(state, ROMANS)
                if margin < 0:
                    continue  # Player Romans below victory — skip
            except Exception:
                continue
        raid_targets.append(target)

    for region in playable:
        hidden_wb = count_pieces_by_state(
            state, region, AEDUI, WARBAND, HIDDEN)
        if hidden_wb == 0:
            continue

        flips = min(2, hidden_wb)
        is_devastated = state["spaces"].get(region, {}).get(
            "devastated", False)

        # Build steal targets for this region
        steal_targets = []
        for target in raid_targets:
            if count_pieces(state, region, target) == 0:
                continue
            if (count_pieces(state, region, target, CITADEL) > 0
                    or count_pieces(state, region, target, FORT) > 0):
                continue
            steal_targets.append(target)

        region_entries = []
        remaining_flips = flips
        for target in steal_targets:
            if remaining_flips <= 0:
                break
            region_entries.append({"region": region, "target": target})
            total_gain += 1
            remaining_flips -= 1

        while remaining_flips > 0:
            if not is_devastated:
                region_entries.append({"region": region, "target": None})
                total_gain += 1
            remaining_flips -= 1

        raid_plan.extend(region_entries)

    return (total_gain >= 2, raid_plan)


# ============================================================================
# HELPER: March targeting
# ============================================================================

def _count_enemy_allies_citadels(state, faction):
    """Count total Allies + Citadels for a faction on the map."""
    return count_faction_allies_and_citadels(state, faction)


def _get_enemy_with_most_allies_citadels(state, scenario):
    """Get the enemy faction with the most Allies + Citadels total.

    Per §8.6.5 step 1: "those of enemies with the most Allies + Citadels."

    Returns:
        Enemy faction constant, or None.
    """
    targeting = get_faction_targeting_order(AEDUI, scenario)
    best_faction = None
    best_count = -1

    for faction in targeting:
        ac = _count_enemy_allies_citadels(state, faction)
        if ac > best_count:
            best_count = ac
            best_faction = faction

    return best_faction


# ============================================================================
# PROCESS NODES
# ============================================================================

def node_a_event(state):
    """A_EVENT: Execute Event.

    Per §8.6.1: Use Unshaded text (§8.2.2). Check Instructions (§8.2.1)
    if gray laurels on card's Aedui symbol.

    Returns:
        Action dict for Event execution.
    """
    card_id = state.get("current_card_id")
    scenario = state["scenario"]
    preference = get_dual_use_preference(AEDUI, scenario)
    instr = get_event_instruction(card_id, AEDUI, scenario)

    return _make_action(
        ACTION_EVENT,
        details={
            "card_id": card_id,
            "text_preference": preference,
            "instruction": instr.instruction if instr else None,
        },
    )


def node_a_battle(state):
    """A_BATTLE: Battle process.

    Per §8.6.2: Battle versus Gauls, Germans, and — if Aedui are at
    victory — Romans.

    Steps:
    1. Ambush in first Battle where box at right applies.
    2. Attack to inflict Losses on enemy Leaders, Allies, Citadels, OR Legions.
    3. Attack where enemy will take Losses AND at least as many as Aedui.

    For all Battle Regions, pay Resources as soon as selected.

    Returns:
        Action dict for Battle.
    """
    scenario = state["scenario"]
    non_players = state.get("non_player_factions", set())
    playable = get_playable_regions(scenario, state.get("capabilities"))
    enemies = _get_battle_enemies(state, scenario)

    battle_plan = []

    # Step 2: Battle where we force Loss on Leader, Ally, Citadel, Legion
    for region in playable:
        if count_pieces(state, region, AEDUI) == 0:
            continue
        for enemy in enemies:
            if count_pieces(state, region, enemy) == 0:
                continue
            if _would_force_loss_on_high_value(
                    state, region, AEDUI, enemy, scenario):
                battle_plan.append({
                    "region": region,
                    "target": enemy,
                    "priority": "high_value",
                })
                break  # One battle per region

    # Step 3: Additional Battles where enemy takes Losses AND at least
    # as many as Aedui — §8.6.2
    for region in playable:
        if any(bp["region"] == region for bp in battle_plan):
            continue
        if count_pieces(state, region, AEDUI) == 0:
            continue
        for enemy in enemies:
            if count_pieces(state, region, enemy) == 0:
                continue
            losses_inflicted, losses_suffered = _estimate_battle_losses(
                state, region, AEDUI, enemy, scenario)
            if losses_inflicted > 0 and losses_inflicted >= losses_suffered:
                battle_plan.append({
                    "region": region,
                    "target": enemy,
                    "priority": "favorable",
                })
                break

    if not battle_plan:
        return _make_action(ACTION_PASS)

    # Determine SA — Ambush first, then Trade
    sa, sa_regions, sa_details = _determine_battle_sa(
        state, battle_plan, scenario)

    return _make_action(
        ACTION_BATTLE,
        regions=[bp["region"] for bp in battle_plan],
        sa=sa,
        sa_regions=sa_regions,
        details={
            "battle_plan": battle_plan,
            "sa_details": sa_details,
            "battled": True,
        },
    )


def node_a_rally(state):
    """A_RALLY: Rally process.

    Per §8.6.3: Rally wherever able to place a piece:
    1. Replace City Allies with Citadels.
    2. Place all Allies able.
    3. Place all Warbands able.

    IF NONE: Raid per §8.6.4.

    Returns:
        Action dict for Rally, or redirects to Raid.
    """
    scenario = state["scenario"]
    playable = get_playable_regions(scenario, state.get("capabilities"))

    rally_plan = {
        "citadels": [],
        "allies": [],
        "warbands": [],
    }

    avail_citadels = get_available(state, AEDUI, CITADEL)
    avail_allies = get_available(state, AEDUI, ALLY)
    avail_warbands = get_available(state, AEDUI, WARBAND)

    # Step 1: Citadels — replace Allies in Cities
    for region in playable:
        if avail_citadels <= 0:
            break
        tribes = get_tribes_in_region(region, scenario)
        for tribe in tribes:
            if avail_citadels <= 0:
                break
            tribe_info = state["tribes"].get(tribe, {})
            if (tribe_info.get("allied_faction") == AEDUI
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
            # Must have Aedui presence for Rally — §3.3.1
            if (count_pieces(state, region, AEDUI) > 0
                    or is_controlled_by(state, region, AEDUI)):
                rally_plan["allies"].append({
                    "region": region, "tribe": tribe,
                })
                avail_allies -= 1

    # Step 3: Warbands — place all possible
    for region in playable:
        if avail_warbands <= 0:
            break
        has_base = False
        tribes = get_tribes_in_region(region, scenario)
        for tribe in tribes:
            tribe_info = state["tribes"].get(tribe, {})
            if tribe_info.get("allied_faction") == AEDUI:
                has_base = True
                break
        if count_pieces(state, region, AEDUI, CITADEL) > 0:
            has_base = True
        if is_controlled_by(state, region, AEDUI):
            has_base = True

        if has_base:
            rally_plan["warbands"].append(region)
            avail_warbands -= 1

    total_placed = (len(rally_plan["citadels"]) + len(rally_plan["allies"])
                    + len(rally_plan["warbands"]))

    # IF NONE: Couldn't Rally any pieces → Raid per §8.6.4
    if total_placed == 0:
        return node_a_raid(state)

    # SA: Trade after Rally — §8.6.3
    sa, sa_regions, sa_details = _determine_trade_sa(
        state, scenario, battled=False)

    return _make_action(
        ACTION_RALLY,
        regions=list({r for entry in rally_plan["citadels"]
                      for r in [entry["region"]]}
                     | {r for entry in rally_plan["allies"]
                        for r in [entry["region"]]}
                     | set(rally_plan["warbands"])),
        sa=sa,
        sa_regions=sa_regions,
        details={"rally_plan": rally_plan, "sa_details": sa_details},
    )


def node_a_raid(state):
    """A_RAID: Raid process.

    Per §8.6.4: Raid if would gain 2+ Resources total.
    1. Versus players at 0+ victory margin.
    2. Versus other non-Roman enemies.
    3. In non-Devastated Regions, versus no Faction (only).

    IF NONE: Pass.

    Returns:
        Action dict for Raid, or Pass.
    """
    scenario = state["scenario"]
    enough, raid_plan = _would_raid_gain_enough(state, scenario)

    if not enough:
        return _make_action(ACTION_PASS)

    # SA: Trade after Raid — §8.6.4
    sa, sa_regions, sa_details = _determine_trade_sa(
        state, scenario, battled=False)

    return _make_action(
        ACTION_RAID,
        regions=[r["region"] for r in raid_plan],
        sa=sa,
        sa_regions=sa_regions,
        details={"raid_plan": raid_plan, "sa_details": sa_details},
    )


def node_a_march(state):
    """A_MARCH: March process.

    Per §8.6.5: March. Leave 1 Aedui Warband per Region. Lose no Aedui
    Control.
    1. Move from 1 Region to add 1 Hidden Aedui to up to 3 Regions where none:
       a. To enemy Allies or Citadels.
       b. To those of enemies with the most Allies + Citadels.
    2. Move to add Aedui Control to 1 Region (beyond or among the above):
       a. With fewest Warbands needed.

    IF NONE (or Frost): Raid per §8.6.4.

    Returns:
        Action dict for March, or redirects to Raid.
    """
    scenario = state["scenario"]
    playable = get_playable_regions(scenario, state.get("capabilities"))

    # IF NONE or Frost — §8.6.5
    if is_frost_active(state):
        return node_a_raid(state)

    march_plan = {
        "origin": None,
        "spread_destinations": [],
        "control_destination": None,
    }

    # Step 1: Move from 1 Region to add 1 Hidden Aedui to up to 3 adjacent
    # Regions that have no Hidden Aedui Warband — §8.6.5

    # Find best origin: region with Aedui Warbands where adjacent regions
    # lack Hidden Aedui and have enemy Allies/Citadels
    best_origin = None
    best_dests = []
    best_score = -1

    enemy_most_ac = _get_enemy_with_most_allies_citadels(state, scenario)

    for origin in playable:
        aedui_wb = count_pieces(state, origin, AEDUI, WARBAND)
        if aedui_wb < 2:  # Need at least 2 (leave 1 behind)
            continue

        # Check if removing Warbands would lose Aedui Control — §8.6.5
        # We can move at most (aedui_wb - 1) out
        max_moveable = aedui_wb - 1

        # Find adjacent destinations with no Hidden Aedui
        candidate_dests = []
        for adj in get_adjacent(origin, scenario):
            if adj not in set(playable):
                continue
            hidden_aedui = count_pieces_by_state(
                state, adj, AEDUI, WARBAND, HIDDEN)
            if hidden_aedui > 0:
                continue
            # Score: prioritize enemy Allies/Citadels — §8.6.5 step 1a
            has_enemy_ac = False
            enemy_ac_score = 0
            for enemy in get_faction_targeting_order(AEDUI, scenario):
                enemy_allies = count_pieces(state, adj, enemy, ALLY)
                enemy_citadels = count_pieces(state, adj, enemy, CITADEL)
                if enemy_allies > 0 or enemy_citadels > 0:
                    has_enemy_ac = True
                    # Prioritize enemies with most total AC — §8.6.5 step 1b
                    if enemy == enemy_most_ac:
                        enemy_ac_score += 10
                    enemy_ac_score += enemy_allies + enemy_citadels
            candidate_dests.append((adj, has_enemy_ac, enemy_ac_score))

        # Sort: enemy AC first (step 1a), then most AC enemy (step 1b)
        candidate_dests.sort(key=lambda x: (-int(x[1]), -x[2]))

        # Take up to 3 destinations, limited by moveable Warbands
        selected = [d[0] for d in candidate_dests[:min(3, max_moveable)]]
        if not selected:
            continue

        # Score this origin by total destinations covered
        score = len(selected)
        # Prefer origins that reach enemy AC
        score += sum(10 for d in candidate_dests[:min(3, max_moveable)]
                     if d[1])

        if score > best_score:
            best_score = score
            best_origin = origin
            best_dests = selected

    if best_origin and best_dests:
        march_plan["origin"] = best_origin
        march_plan["spread_destinations"] = best_dests

    # Step 2: Move to add Aedui Control to 1 Region — §8.6.5
    # "possibly in addition to Control just added, or to add Control to
    # a destination above."
    # "With fewest Warbands needed" — §8.6.5 step 2a
    best_ctrl_dest = None
    fewest_needed = 999

    for region in playable:
        if is_controlled_by(state, region, AEDUI):
            continue  # Already have Control

        # How many Warbands needed to take Control?
        # Need: Aedui forces > all other forces combined
        from fs_bot.board.control import _count_faction_forces
        aedui_forces = _count_faction_forces(
            state["spaces"].get(region, {}), AEDUI, scenario)
        total_other = 0
        for faction in FACTIONS:
            if faction == AEDUI:
                continue
            total_other += _count_faction_forces(
                state["spaces"].get(region, {}), faction, scenario)

        # Need aedui_forces + warbands_to_add > total_other
        needed = total_other - aedui_forces + 1
        if needed <= 0:
            needed = 1  # Already could control, just need presence

        # Check if we have a source for these Warbands (adjacent with enough)
        can_supply = False
        for adj in get_adjacent(region, scenario):
            if adj not in set(playable):
                continue
            adj_wb = count_pieces(state, adj, AEDUI, WARBAND)
            # Leave 1 behind, don't lose Control
            moveable = adj_wb - 1
            if moveable >= needed:
                can_supply = True
                break

        if can_supply and needed < fewest_needed:
            fewest_needed = needed
            best_ctrl_dest = region

    if best_ctrl_dest is not None:
        march_plan["control_destination"] = best_ctrl_dest

    has_any_march = (march_plan["spread_destinations"]
                     or march_plan["control_destination"] is not None)

    if not has_any_march:
        return node_a_raid(state)

    # Check Britannia restriction for SA — §4.1.3
    all_dests = list(march_plan["spread_destinations"])
    if march_plan["control_destination"]:
        all_dests.append(march_plan["control_destination"])
    marched_britannia = (
        BRITANNIA in all_dests
        or march_plan.get("origin") == BRITANNIA
    )

    # SA: Trade or Suborn after March — §8.6.5
    if marched_britannia:
        # No SA if Marched into/out of Britannia — §4.1.3
        sa = SA_ACTION_NONE
        sa_regions = []
        sa_details = {}
    else:
        sa, sa_regions, sa_details = _determine_suborn_sa(state, scenario)

    return _make_action(
        ACTION_MARCH,
        regions=all_dests,
        sa=sa,
        sa_regions=sa_regions,
        details={"march_plan": march_plan, "sa_details": sa_details},
    )


# ============================================================================
# SPECIAL ABILITY NODES
# ============================================================================

def _check_ambush(state, battle_plan, scenario):
    """A_AMBUSH: Determine Ambush region.

    Per §8.6.2: Ambush in the first Battle in which:
      - Retreat out could lessen removals AND/OR
      - any Counterattack Loss to Aedui is possible.

    Returns:
        Region where Ambush applies, or None.
    """
    if not battle_plan:
        return None

    for bp in battle_plan:
        region = bp["region"]
        enemy = bp["target"]

        # Check Hidden Aedui > Hidden enemy — Ambush eligibility
        hidden_aedui = count_pieces_by_state(
            state, region, AEDUI, WARBAND, HIDDEN)
        hidden_enemy = count_pieces_by_state(
            state, region, enemy, WARBAND, HIDDEN)
        if enemy == ROMANS:
            hidden_enemy += count_pieces_by_state(
                state, region, enemy, AUXILIA, HIDDEN)
        if hidden_aedui <= hidden_enemy:
            continue

        should_ambush = False

        # Estimate losses inflicted
        losses_inflicted, _ = _estimate_battle_losses(
            state, region, AEDUI, enemy, scenario)

        # (a) "Retreat out could lessen removals" — enemy mobile pieces
        # could retreat to halve losses
        enemy_mobile = count_mobile_pieces(state, region, enemy)
        if enemy_mobile > 0 and losses_inflicted > 0:
            should_ambush = True

        # (b) "any Counterattack Loss to Aedui is possible"
        # Enemy Legion or Leader could survive Attack to Counterattack
        if count_pieces(state, region, enemy, LEGION) > 0:
            should_ambush = True
        if get_leader_in_region(state, region, enemy) is not None:
            should_ambush = True

        if should_ambush:
            return region

    return None


def _determine_battle_sa(state, battle_plan, scenario):
    """Determine SA for Battle: Ambush first, then Trade.

    Per §8.6.2: Check Ambush first. If no Ambush, Trade after Battle.

    Returns:
        (sa_action, sa_regions, sa_details) tuple.
    """
    ambush_region = _check_ambush(state, battle_plan, scenario)
    if ambush_region:
        return (SA_ACTION_AMBUSH, [ambush_region], {"ambush": True})

    # No Ambush → Trade after Battle — §8.6.2
    sa, sa_regions, sa_details = _determine_trade_sa(
        state, scenario, battled=True)
    return (sa, sa_regions, sa_details)


def _determine_trade_sa(state, scenario, *, battled=False):
    """A_TRADE: Determine if Aedui should Trade.

    Per §8.6.3: Trade only if:
      - Aedui Battled OR Aedui Resources 0-9 OR Aedui+Roman Resources < 15
      - AND Aedui are 2nd Eligible OR Trade would add 3+ Resources

    Trade for all Resources possible — players must agree or not.
    Non-player Romans agree.

    If no Trade conditions met, fall through to Suborn (unless Battled).

    Returns:
        (sa_action, sa_regions, sa_details) tuple.
    """
    resources = state.get("resources", {}).get(AEDUI, 0)
    roman_resources = state.get("resources", {}).get(ROMANS, 0)
    is_second_eligible = state.get("is_second_eligible", False)

    # Check Trade preconditions — §8.6.3
    precondition_met = False
    if battled:
        precondition_met = True
    elif resources < 10:
        precondition_met = True
    elif resources + roman_resources < 15:
        precondition_met = True

    if not precondition_met:
        if not battled:
            return _determine_suborn_sa(state, scenario)
        return (SA_ACTION_NONE, [], {})

    # Check Trade trigger — §8.6.3
    # "Trade only if either the Aedui are currently acting as the 2nd
    # Eligible Faction or if Trading would earn the Aedui more than two
    # Resources"
    trade_resources = _estimate_trade_resources(state, scenario)

    trigger_met = False
    if is_second_eligible:
        trigger_met = True
    elif trade_resources > 2:
        trigger_met = True

    if not trigger_met:
        # No Trade: if Battled, no SA; otherwise fall through to Suborn
        if battled:
            return (SA_ACTION_NONE, [], {})
        return _determine_suborn_sa(state, scenario)

    # Trade for all Resources possible
    trade_regions = _get_trade_regions(state, scenario)

    return (SA_ACTION_TRADE, trade_regions, {
        "trade_resources": trade_resources,
        "trade_regions": trade_regions,
    })


def _estimate_trade_resources(state, scenario):
    """Estimate how many Resources Trade would earn.

    Per §4.4.1: Trade earns Resources based on pieces within Supply Lines
    to Cisalpina:
      - +1 per Aedui Allied Tribe within Supply Lines
      - +1 per Aedui Citadel within Supply Lines
      If Romans agree: double those to +2 each, plus:
      - +1 per Subdued Tribe in Aedui-Controlled regions within Supply Lines
      - +1 per Roman Allied Tribe in Aedui-Controlled regions within Supply
        Lines

    NOTE: This is an approximation pending full Supply Line pathfinding.
    We count all Aedui Allies + Citadels on the map as a baseline (they
    earn at least +1 each if any Supply Line exists), then check the
    Roman agreement multiplier.

    Returns:
        Integer estimated Resources gained.
    """
    non_players = state.get("non_player_factions", set())

    # Count Aedui Allies on map
    aedui_allies = 0
    for tribe_info in state["tribes"].values():
        if tribe_info.get("allied_faction") == AEDUI:
            aedui_allies += 1

    # Count Aedui Citadels on map
    aedui_citadels = count_on_map(state, AEDUI, CITADEL)

    base_pieces = aedui_allies + aedui_citadels
    if base_pieces == 0:
        return 0

    # Check if Romans would agree — §8.6.3, §8.6.6
    # NP Romans always agree per §8.6.3
    romans_agree = False
    if ROMANS in non_players:
        romans_agree = True
    else:
        # Player Romans: use same victory-score tiers from agreements
        # For estimation, assume agreement if score < 10
        try:
            roman_score = calculate_victory_score(state, ROMANS)
            if roman_score < 10:
                romans_agree = True
        except Exception:
            pass

    if romans_agree:
        # +2 per Aedui Ally and Citadel — §4.4.1
        total = base_pieces * 2

        # +1 per Subdued Tribe in Aedui-Controlled regions
        aedui_controlled = set(get_controlled_regions(state, AEDUI))
        for tribe_name, tribe_info in state["tribes"].items():
            from fs_bot.rules_consts import TRIBE_TO_REGION
            tribe_region = TRIBE_TO_REGION.get(tribe_name)
            if tribe_region and tribe_region in aedui_controlled:
                # Subdued = no allied_faction and no Dispersed marker
                if tribe_info.get("allied_faction") is None:
                    if not tribe_info.get("status"):
                        total += 1

        # +1 per Roman Allied Tribe in Aedui-Controlled regions
        for tribe_name, tribe_info in state["tribes"].items():
            tribe_region = TRIBE_TO_REGION.get(tribe_name)
            if tribe_region and tribe_region in aedui_controlled:
                if tribe_info.get("allied_faction") == ROMANS:
                    total += 1
    else:
        # +1 per Aedui Ally and Citadel — §4.4.1
        total = base_pieces

    return total


def _get_trade_regions(state, scenario):
    """Get regions where Trade would occur.

    Returns:
        List of region constants.
    """
    return get_controlled_regions(state, AEDUI)


def _determine_suborn_sa(state, scenario):
    """A_SUBORN: Determine Suborn action.

    Per §8.6.3: Suborn in 1 Region (or 2 if unshaded Convictolitavis).
    1. Place Aedui Ally.
    2. If none placed, remove enemy Ally (enemy with most AC, NP Romans last).
    3. Place all Aedui Warbands able.
    4. Remove most enemy Warbands: (1) Arverni (2) Belgae (3) Germans.
    5. Remove Auxilia.

    Per §4.4.2: "remove and/or place a total of up to three such pieces in
    the Suborn Region (in any combination). A maximum of one of the three
    pieces removed or placed in the Region may be an Allied Tribe."
    Cap: 3 pieces total per region, 1 Ally max per region.

    Note: Suborn costs (2 Resources per Ally, 1 per Warband/Auxilia — §4.4.2)
    are tracked by the execution layer, not the planning layer.

    If none: no Special Ability.

    Returns:
        (sa_action, sa_regions, sa_details) tuple.
    """
    playable = get_playable_regions(scenario, state.get("capabilities"))
    non_players = state.get("non_player_factions", set())
    capabilities = state.get("capabilities", {})

    # Check Convictolitavis unshaded — allows 2 regions
    max_regions = 1
    if capabilities.get("convictolitavis_unshaded", False):
        max_regions = 2

    suborn_plan = []
    regions_used = 0

    avail_allies = get_available(state, AEDUI, ALLY)
    avail_warbands = get_available(state, AEDUI, WARBAND)

    for region in playable:
        if regions_used >= max_regions:
            break

        # Need Hidden Aedui Warband to Suborn — §4.4.2
        hidden_aedui = count_pieces_by_state(
            state, region, AEDUI, WARBAND, HIDDEN)
        if hidden_aedui == 0:
            continue

        region_actions = []
        # Per §4.4.2: max 3 pieces total, max 1 Ally per region
        pieces_affected = 0
        allies_affected = 0

        # Step 1: Place Aedui Ally — §8.6.3
        ally_placed = False
        if (avail_allies > 0
                and pieces_affected < SUBORN_MAX_PIECES
                and allies_affected < SUBORN_MAX_ALLIES):
            tribes = get_tribes_in_region(region, scenario)
            for tribe in tribes:
                tribe_info = state["tribes"].get(tribe, {})
                if tribe_info.get("allied_faction") is None:
                    region_actions.append({
                        "action": "place_ally",
                        "tribe": tribe,
                    })
                    avail_allies -= 1
                    ally_placed = True
                    pieces_affected += 1
                    allies_affected += 1
                    break

        # Step 2: If no Ally placed, remove enemy Ally — §8.6.3
        if (not ally_placed
                and pieces_affected < SUBORN_MAX_PIECES
                and allies_affected < SUBORN_MAX_ALLIES):
            # Remove from faction with most AC, NP Romans last
            best_target = None
            best_ac = -1
            tribes = get_tribes_in_region(region, scenario)

            # Build priority: faction with most AC total, NP Romans last
            targeting = get_faction_targeting_order(AEDUI, scenario)
            for target_faction in targeting:
                if target_faction == AEDUI:
                    continue
                # NP Romans last — §8.6.3
                faction_ac = _count_enemy_allies_citadels(
                    state, target_faction)
                # Deprioritize NP Romans
                priority = faction_ac
                if target_faction == ROMANS and ROMANS in non_players:
                    priority = -1

                for tribe in tribes:
                    tribe_info = state["tribes"].get(tribe, {})
                    if tribe_info.get("allied_faction") == target_faction:
                        if priority > best_ac:
                            best_ac = priority
                            best_target = {
                                "action": "remove_ally",
                                "tribe": tribe,
                                "target_faction": target_faction,
                            }

            if best_target:
                region_actions.append(best_target)
                pieces_affected += 1
                allies_affected += 1

        # Step 3: Place all Aedui Warbands able — §8.6.3
        # Capped by remaining piece slots — §4.4.2
        while avail_warbands > 0 and pieces_affected < SUBORN_MAX_PIECES:
            region_actions.append({"action": "place_warband"})
            avail_warbands -= 1
            pieces_affected += 1

        # Step 4: Remove most enemy Warbands — §8.6.3
        # Priority: (1) Arverni (2) Belgae (3) Germans
        # In Ariovistus: Germans swap with Arverni per A8.4
        # Capped by remaining piece slots — §4.4.2
        if scenario in ARIOVISTUS_SCENARIOS:
            wb_remove_order = (GERMANS, BELGAE, ARVERNI)
        else:
            wb_remove_order = (ARVERNI, BELGAE, GERMANS)

        for target_faction in wb_remove_order:
            if pieces_affected >= SUBORN_MAX_PIECES:
                break
            enemy_wb = count_pieces(state, region, target_faction, WARBAND)
            for _ in range(enemy_wb):
                if pieces_affected >= SUBORN_MAX_PIECES:
                    break
                region_actions.append({
                    "action": "remove_warband",
                    "target_faction": target_faction,
                })
                pieces_affected += 1

        # Step 5: Remove Auxilia — §8.6.3
        # Capped by remaining piece slots — §4.4.2
        for target_faction in get_faction_targeting_order(AEDUI, scenario):
            if pieces_affected >= SUBORN_MAX_PIECES:
                break
            enemy_aux = count_pieces(
                state, region, target_faction, AUXILIA)
            for _ in range(enemy_aux):
                if pieces_affected >= SUBORN_MAX_PIECES:
                    break
                region_actions.append({
                    "action": "remove_auxilia",
                    "target_faction": target_faction,
                })
                pieces_affected += 1

        if region_actions:
            suborn_plan.append({
                "region": region,
                "actions": region_actions,
            })
            regions_used += 1

    if not suborn_plan:
        return (SA_ACTION_NONE, [], {})

    return (SA_ACTION_SUBORN,
            [sp["region"] for sp in suborn_plan],
            {"suborn_plan": suborn_plan})


# ============================================================================
# WINTER NODES
# ============================================================================

def node_a_quarters(state):
    """A_QUARTERS: Quarters Phase.

    Per §8.6.7: Non-player Aedui move only to leave Devastated Regions
    where they have no Ally or Citadel, if they can.

    Returns:
        Quarters action details dict.
    """
    scenario = state["scenario"]
    playable = get_playable_regions(scenario, state.get("capabilities"))

    quarters_plan = {
        "leave_devastated": [],
    }

    for region in playable:
        if count_pieces(state, region, AEDUI) == 0:
            continue
        is_devastated = state["spaces"].get(region, {}).get(
            "devastated", False)
        if not is_devastated:
            continue
        # Check for Ally or Citadel
        has_ally = False
        tribes = get_tribes_in_region(region, scenario)
        for tribe in tribes:
            if state["tribes"].get(tribe, {}).get(
                    "allied_faction") == AEDUI:
                has_ally = True
                break
        has_citadel = count_pieces(state, region, AEDUI, CITADEL) > 0
        if not has_ally and not has_citadel:
            # Find adjacent non-Devastated region to move to
            for adj in get_adjacent(region, scenario):
                adj_devastated = state["spaces"].get(adj, {}).get(
                    "devastated", False)
                if not adj_devastated:
                    quarters_plan["leave_devastated"].append({
                        "from": region, "to": adj,
                    })
                    break

    return quarters_plan


# ============================================================================
# AGREEMENTS
# ============================================================================

def node_a_agreements(state, requesting_faction, request_type):
    """A_AGREEMENTS: Agreement decisions.

    Per §8.6.6:
    - Harass Vercingetorix BUT NOT Romans.
    - Transfer 10 Resources to Romans when Romans at 0-1 Resources AND
      Aedui at 21+ Resources.
    - Agree to Retreat, Supply Line, Quarters for Romans based on
      Roman victory score tiers.
    - To Arverni, Belgae: Never.
    - To NP Roman: Always.

    Args:
        state: Game state dict.
        requesting_faction: Faction making the request.
        request_type: "supply_line", "retreat", "quarters", "resources",
                      "harassment".

    Returns:
        True if Aedui agree.
    """
    non_players = state.get("non_player_factions", set())

    if request_type == "harassment":
        # Harass Vercingetorix BUT NOT Romans — §8.6.6
        if requesting_faction == ROMANS:
            return False
        # Harass Vercingetorix — checked by caller for Arverni March
        if requesting_faction == ARVERNI:
            return True
        return False

    if request_type == "resources":
        # Transfer 10 Resources to Romans when Romans at 0-1 Resources
        # AND Aedui at 21+ Resources — §8.6.6
        if requesting_faction == ROMANS:
            roman_res = state.get("resources", {}).get(ROMANS, 0)
            aedui_res = state.get("resources", {}).get(AEDUI, 0)
            if roman_res <= 1 and aedui_res >= 21:
                return True
        # Never transfer to Arverni or Belgae — §8.6.6
        return False

    # Retreat, Supply Line, Quarters
    if request_type in ("retreat", "supply_line", "quarters"):
        # To Arverni, Belgae: Never — §8.6.6
        if requesting_faction in (ARVERNI, BELGAE):
            return False

        if requesting_faction == ROMANS:
            # NP Roman: Always — §8.6.6
            if ROMANS in non_players:
                return True

            # Player Roman: based on victory score — §8.6.6
            try:
                roman_score = calculate_victory_score(state, ROMANS)
            except Exception:
                return False

            if roman_score < 10:
                return True
            if roman_score <= 12:
                result = roll_die(state) <= 4
                # If failed Supply Line roll, Roman player may re-choose
                # action — §8.6.6 (handled by caller)
                return result
            # Score > 12: No
            return False

        return False

    return False


# ============================================================================
# DIVICIACUS
# ============================================================================

def node_a_diviciacus(state, context):
    """A_DIVICIACUS: Diviciacus handling.

    Per §8.6.8: If unshaded Diviciacus in effect:
    - During Roman Commands or defense, agree only while Roman victory
      < 13, BUT NOT if they are Scouting or Battling Aedui.
    - During Aedui Commands, use Auxilia as able while Romans agree.
    - Place Auxilia only if NP Roman AND once no Aedui Warbands Available.

    Args:
        state: Game state dict.
        context: Dict with "phase" ("roman_command", "aedui_command",
                 "roman_defense"), "action" (optional, "scout"/"battle"),
                 "target" (optional, faction being targeted).

    Returns:
        True if Diviciacus agreement applies.
    """
    capabilities = state.get("capabilities", {})
    if not capabilities.get("diviciacus_unshaded", False):
        return False

    non_players = state.get("non_player_factions", set())
    phase = context.get("phase", "")

    if phase in ("roman_command", "roman_defense"):
        # Agree only while Roman victory < 13 — §8.6.8
        try:
            roman_score = calculate_victory_score(state, ROMANS)
        except Exception:
            return False
        if roman_score >= 13:
            return False
        # BUT NOT if Scouting or Battling Aedui — §8.6.8
        action = context.get("action", "")
        target = context.get("target", None)
        if action in ("scout", "battle") and target == AEDUI:
            return False
        return True

    if phase == "aedui_command":
        # Use Auxilia as Aedui Warbands to max degree Romans agree
        # Place Auxilia only if NP Roman AND no Aedui Warbands Available
        if context.get("placing", False):
            if ROMANS not in non_players:
                return False
            if get_available(state, AEDUI, WARBAND) > 0:
                return False
            return True
        return True

    return False


# ============================================================================
# MAIN FLOWCHART DRIVER
# ============================================================================

def execute_aedui_turn(state):
    """Walk the Aedui bot flowchart and return the chosen action.

    Implements the full decision tree: A1 → A2 → A3 → A4 → A5 → A6 and
    all process nodes.

    The Aedui bot runs in both base game and Ariovistus scenarios.

    Args:
        state: Game state dict.

    Returns:
        Action dict describing the Aedui bot's decision.
    """
    scenario = state["scenario"]

    # §8.1.2: Upgrade Limited Command from SoP
    if state.get("limited_by_sop", False):
        pass  # NP gets full Command + SA — upgrade is implicit

    # A1: Aedui 1st on upcoming but not current card, and roll 1-4?
    a1_result = node_a1(state)
    if a1_result == "Yes":
        return _make_action(ACTION_PASS)

    # A2: Can play Event by SoP?
    a2_result = node_a2(state)
    if a2_result == "Yes":
        # A3: Decline checks
        a3_result = node_a3(state)
        if a3_result == "No":
            return node_a_event(state)

    # A4: Battle would force Loss on high-value target?
    a4_result = node_a4(state)
    if a4_result == "Yes":
        return node_a_battle(state)

    # A5: Rally?
    a5_result = node_a5(state)
    if a5_result == "Yes":
        return node_a_rally(state)

    # A6: Raid (0-3 Resources and roll 1-4)?
    a6_result = node_a6(state)
    if a6_result == "Yes":
        return node_a_raid(state)

    # Default: March — §8.6.5
    return node_a_march(state)
