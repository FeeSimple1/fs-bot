"""
Non-Player Belgae flowchart — §8.5.

Every node from the Belgae bot flowchart (B1 through B_ENLIST, plus
B_QUARTERS, B_SPRING, B_AGREEMENTS) is a labeled function.

The Belgae bot runs in both base game and Ariovistus scenarios.
In Ariovistus, Chapter A8 modifications apply:
- A8.5.1: Ignore "non-German" stipulation for Battle/March under Threat
  (consider German enemies too). Count Settlements as "Allies".
  Enlist: march Germans from Belgica/Germania/Treveri if able.
- A8.5.6: Quarters — first move to Morini, Nervii, or Treveri.

Node functions return an action dict describing what the bot decided to do.
The dispatch loop calls execute_belgae_turn(state) which walks the flowchart.
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
    SA_ENLIST, SA_RAMPAGE, SA_AMBUSH,
    # Leaders
    AMBIORIX, BODUOGNATUS, CAESAR, SUCCESSOR,
    # Regions
    BRITANNIA, TREVERI, MORINI, NERVII,
    # Region groups
    BELGICA, GERMANIA,
    BELGICA_REGIONS, GERMANIA_REGIONS,
    # Events
    EVENT_SHADED,
    # Die
    DIE_MIN, DIE_MAX,
    # Map
    REGION_TO_GROUP,
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
    get_region_group, is_city_tribe, is_adjacent,
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
SA_ACTION_ENLIST = "Enlist"
SA_ACTION_RAMPAGE = "Rampage"
SA_ACTION_NONE = "No SA"

# March sub-types for clarity in action dicts
MARCH_THREAT = "March (threat)"
MARCH_CONTROL = "March (control)"


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
# HELPER: Belgae-specific board queries
# ============================================================================

def _ambiorix_region(state):
    """Find Ambiorix's region, or None."""
    return find_leader(state, BELGAE)


def _count_belgae_warbands_on_map(state):
    """Count total Belgae Warbands on map."""
    return count_on_map(state, BELGAE, WARBAND)


def _count_belgae_allies_citadels_on_map(state):
    """Count total Belgae Allies + Citadels on map."""
    return count_faction_allies_and_citadels(state, BELGAE)


def _get_non_german_enemies(scenario):
    """Get non-German enemy factions for B1 threat condition.

    Per §8.5.1: "any non-Germanic enemy (Romans, Arverni, or Aedui)".
    Per A8.5.1: In Ariovistus, ignore "non-German" stipulation — consider
    German enemies also.

    Args:
        scenario: Scenario constant.

    Returns:
        Tuple of enemy faction constants.
    """
    if scenario in ARIOVISTUS_SCENARIOS:
        # A8.5.1: consider German enemies too
        return (ROMANS, ARVERNI, AEDUI, GERMANS)
    # Base game: non-German enemies only — §8.5.1
    return (ROMANS, ARVERNI, AEDUI)


def _has_belgae_threat(state, region, scenario):
    """Check if a region meets the B1 'Battle or March under Threat' condition.

    Per §8.5.1: Ambiorix or 4+ Belgic Warbands in a Region where any
    non-Germanic enemy has an Ally, Citadel, Legion, or separately ≥4 pieces.

    Per A8.5.1: In Ariovistus, ignore "non-German" — consider German enemies
    too. Count Settlements as "Allies" for these conditions.

    Args:
        state: Game state dict.
        region: Region constant.
        scenario: Scenario constant.

    Returns:
        True if the region has a threat per §8.5.1.
    """
    # Must have Ambiorix OR 4+ Belgic Warbands in this region
    has_ambiorix = get_leader_in_region(state, region, BELGAE) is not None
    belgae_wb = count_pieces(state, region, BELGAE, WARBAND)
    if not has_ambiorix and belgae_wb < 4:
        return False

    # Check enemies for Ally, Citadel, Legion, or ≥4 pieces
    enemies = _get_non_german_enemies(scenario)
    for enemy in enemies:
        if count_pieces(state, region, enemy, ALLY) > 0:
            return True
        if count_pieces(state, region, enemy, CITADEL) > 0:
            return True
        # A8.5.1: count Settlements as "Allies"
        if (scenario in ARIOVISTUS_SCENARIOS
                and count_pieces(state, region, enemy, SETTLEMENT) > 0):
            return True
        if count_pieces(state, region, enemy, LEGION) > 0:
            return True
        # "separately at least four pieces" — §8.5.1
        if count_pieces(state, region, enemy) >= 4:
            return True

    return False


def _get_threat_regions(state, scenario):
    """Get all regions meeting the B1 threat condition.

    Returns:
        List of region constants.
    """
    playable = get_playable_regions(scenario, state.get("capabilities"))
    return [r for r in playable if _has_belgae_threat(state, r, scenario)]


def _can_battle_in_region(state, region, scenario, enemy):
    """Check if Belgae can Battle a specific enemy in a region per §8.5.1.

    Conditions: Belgic Losses less than enemy's AND no Loss on Ambiorix
    (presuming all Defender Loss rolls result in removals, best case for
    Belgic Attack).

    Per §8.5.1 NOTE: "Non-player Belgae do not Battle against Germans."
    Per A8.5.1: In Ariovistus, ignore "non-German" stipulation.

    Args:
        state: Game state dict.
        region: Region constant.
        scenario: Scenario constant.
        enemy: Enemy faction constant.

    Returns:
        True if Belgae can Battle this enemy here per §8.5.1 restrictions.
    """
    # §8.5.1 NOTE: do not Battle against Germans (base game only)
    if enemy == GERMANS and scenario not in ARIOVISTUS_SCENARIOS:
        return False

    belgae_wb = count_pieces(state, region, BELGAE, WARBAND)
    has_ambiorix = get_leader_in_region(state, region, BELGAE) is not None

    if belgae_wb == 0 and not has_ambiorix:
        return False

    enemy_pieces = count_pieces(state, region, enemy)
    if enemy_pieces == 0:
        return False

    # Estimate Belgae Attack Losses inflicted per §3.3.4:
    # Losses = ½ per Warband + 1 per Leader, rounded down
    attack_raw = belgae_wb * 0.5 + (1 if has_ambiorix else 0)

    # Enemy Fort/Citadel halves Attack Losses inflicted — §3.3.4
    enemy_fort = count_pieces(state, region, enemy, FORT)
    enemy_citadel = count_pieces(state, region, enemy, CITADEL)
    if enemy_fort > 0 or enemy_citadel > 0:
        attack_raw = attack_raw / 2

    losses_inflicted = int(attack_raw)

    # Estimate Counterattack Losses suffered per §3.3.4:
    enemy_warbands = count_pieces(state, region, enemy, WARBAND)
    enemy_auxilia = count_pieces(state, region, enemy, AUXILIA)
    enemy_legions = count_pieces(state, region, enemy, LEGION)
    enemy_leader = get_leader_in_region(state, region, enemy)

    counter_raw = (enemy_legions * 1
                   + enemy_warbands * 0.5
                   + (1 if enemy_leader else 0)
                   + enemy_auxilia * 0.5)

    # Our Fort/Citadel halves Counterattack Losses suffered — §3.3.4
    our_fort = count_pieces(state, region, BELGAE, FORT)
    our_citadel = count_pieces(state, region, BELGAE, CITADEL)
    if our_fort > 0 or our_citadel > 0:
        counter_raw = counter_raw / 2

    losses_suffered = int(counter_raw)

    # Check: no Loss on Ambiorix — §8.5.1
    # "presuming all Defender Loss rolls result in removals"
    # Ambiorix would take a Loss only if all Warbands removed first
    if has_ambiorix and losses_suffered >= belgae_wb + 1:
        return False

    # Condition: Belgic Losses less than enemy's — §8.5.1
    if losses_inflicted > losses_suffered:
        return True

    return False


def _estimate_battle_losses(state, region, scenario, enemy):
    """Estimate losses inflicted and suffered for a Battle.

    Returns:
        (losses_inflicted, losses_suffered) tuple.
    """
    belgae_wb = count_pieces(state, region, BELGAE, WARBAND)
    has_ambiorix = get_leader_in_region(state, region, BELGAE) is not None

    attack_raw = belgae_wb * 0.5 + (1 if has_ambiorix else 0)
    enemy_fort = count_pieces(state, region, enemy, FORT)
    enemy_citadel = count_pieces(state, region, enemy, CITADEL)
    if enemy_fort > 0 or enemy_citadel > 0:
        attack_raw = attack_raw / 2
    losses_inflicted = int(attack_raw)

    enemy_warbands = count_pieces(state, region, enemy, WARBAND)
    enemy_auxilia = count_pieces(state, region, enemy, AUXILIA)
    enemy_legions = count_pieces(state, region, enemy, LEGION)
    enemy_leader = get_leader_in_region(state, region, enemy)

    counter_raw = (enemy_legions * 1
                   + enemy_warbands * 0.5
                   + (1 if enemy_leader else 0)
                   + enemy_auxilia * 0.5)

    our_fort = count_pieces(state, region, BELGAE, FORT)
    our_citadel = count_pieces(state, region, BELGAE, CITADEL)
    if our_fort > 0 or our_citadel > 0:
        counter_raw = counter_raw / 2
    losses_suffered = int(counter_raw)

    return (losses_inflicted, losses_suffered)


def _estimate_rally_would_qualify(state, scenario):
    """Check if Rally would add a Belgic Ally, Citadel, 3+ Belgic Warbands,
    or Belgic Control.

    Per §8.5.3: "they Rally if doing so would place a Belgic Ally, a Citadel,
    or at least three Belgic Warbands total, or if it would add to Belgic
    Control."

    Per §8.5.3 NOTE: "If the Belgae have 0 Resources, a normal (not free, 5.4)
    Rally would not place any pieces."

    Returns:
        True if Rally qualifies per §8.5.3.
    """
    resources = state.get("resources", {}).get(BELGAE, 0)

    # §8.5.3 NOTE: 0 Resources means Rally places nothing (not free)
    if resources <= 0:
        return False

    playable = get_playable_regions(scenario, state.get("capabilities"))

    avail_citadels = get_available(state, BELGAE, CITADEL)
    avail_allies = get_available(state, BELGAE, ALLY)
    avail_warbands = get_available(state, BELGAE, WARBAND)

    would_place_citadel = False
    would_place_ally = False
    warband_count = 0
    would_add_control = False

    # Step 1: Citadel — replace Ally in City
    for region in playable:
        if avail_citadels <= 0:
            break
        tribes = get_tribes_in_region(region, scenario)
        for tribe in tribes:
            if avail_citadels <= 0:
                break
            tribe_info = state["tribes"].get(tribe, {})
            if (tribe_info.get("allied_faction") == BELGAE
                    and is_city_tribe(tribe)):
                would_place_citadel = True
                avail_citadels -= 1
                avail_allies += 1  # Freed Ally

    # Step 2: Allies — place wherever able
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
            # Rally requires Control or Ally/Citadel — §3.3.1
            if (count_pieces(state, region, BELGAE) > 0
                    or is_controlled_by(state, region, BELGAE)):
                would_place_ally = True
                avail_allies -= 1

    # Step 3: Warbands — count how many we'd place
    for region in playable:
        if avail_warbands <= 0:
            break
        has_base = False
        tribes = get_tribes_in_region(region, scenario)
        for tribe in tribes:
            tribe_info = state["tribes"].get(tribe, {})
            if tribe_info.get("allied_faction") == BELGAE:
                has_base = True
                break
        if count_pieces(state, region, BELGAE, CITADEL) > 0:
            has_base = True
        if is_controlled_by(state, region, BELGAE):
            has_base = True

        if has_base:
            # Check if placing here would add Belgic Control
            if not is_controlled_by(state, region, BELGAE):
                would_add_control = True
            warband_count += 1
            avail_warbands -= 1

    # Also check if placing Warbands anywhere would flip Control
    # (even if we already counted them above)
    if not would_add_control and warband_count > 0:
        # Re-check: placing Warbands might add control somewhere
        for region in playable:
            if not is_controlled_by(state, region, BELGAE):
                belgae_total = count_pieces(state, region, BELGAE)
                if belgae_total > 0:
                    # Would the Rally Warband tip control?
                    would_add_control = True
                    break

    if would_place_citadel:
        return True
    if would_place_ally:
        return True
    if warband_count >= 3:
        return True
    if would_add_control:
        return True

    return False


def _would_raid_gain_enough(state, scenario):
    """Check if Raiding would gain at least 2 Resources total.

    Per §8.5.4: Raid if would gain 2+ Resources.
    Per §3.3.3: Each Raid region flips 1-2 Hidden Warbands; each flip either
    steals 1 Resource from an enemy or gains 1 Resource (non-Devastated).

    Priority: (1) Romans (2) Aedui (3) Other — §8.5.4

    Returns:
        (bool, list of raid plan dicts) — whether 2+ Resources would be
        gained and the raid plan.
    """
    playable = get_playable_regions(scenario, state.get("capabilities"))
    non_players = state.get("non_player_factions", set())
    total_gain = 0
    raid_plan = []

    for region in playable:
        hidden_wb = count_pieces_by_state(
            state, region, BELGAE, WARBAND, HIDDEN)
        if hidden_wb == 0:
            continue

        flips = min(2, hidden_wb)
        is_devastated = state["spaces"].get(region, {}).get("devastated", False)

        # Build ordered list of steal targets — §8.5.4
        # "Versus players (only)": (1) Romans (2) Aedui (3) Other
        steal_targets = []
        for target in (ROMANS, AEDUI):
            if target in non_players:
                continue  # "players (only)" — §8.5.4
            if count_pieces(state, region, target) == 0:
                continue
            if (count_pieces(state, region, target, CITADEL) > 0
                    or count_pieces(state, region, target, FORT) > 0):
                continue
            steal_targets.append(target)

        # "Other" player factions — §8.5.4
        # Per §3.3.3: Raid steals from "a non-Germanic enemy" — exclude
        # GERMANS in base game. Per A8.4: swap "Germans" ↔ "Arverni"
        # throughout §8.4-§8.5, so exclude ARVERNI in Ariovistus.
        if scenario in ARIOVISTUS_SCENARIOS:
            other_targets = (GERMANS,)  # Arverni excluded per A8.4
        else:
            other_targets = (ARVERNI,)  # Germans excluded per §3.3.3
        for target in other_targets:
            if target in non_players:
                continue
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

        # Remaining flips: non-Devastated +1 Resource (no faction target)
        # §8.5.4 step 2: "In non-Devastated Regions, versus no Faction."
        while remaining_flips > 0:
            if not is_devastated:
                region_entries.append({"region": region, "target": None})
                total_gain += 1
            remaining_flips -= 1

        raid_plan.extend(region_entries)

    return (total_gain >= 2, raid_plan)


def _count_adjacent_belgae_regions(state, region, scenario):
    """Count Regions within distance 1 that have Belgae pieces.

    Per §8.5.1 step 2a: "within 1 of most Regions that have Belgae."
    """
    count = 0
    if count_pieces(state, region, BELGAE) > 0:
        count += 1
    for adj in get_adjacent(region, scenario):
        if count_pieces(state, adj, BELGAE) > 0:
            count += 1
    return count


def _find_largest_belgae_warband_group(state, scenario):
    """Find the region with the single largest group of Belgic Warbands.

    Per §8.5.1: "the single largest group of Belgic Warbands on the map."

    Returns:
        (region, count) or (None, 0) if no Warbands on map.
    """
    playable = get_playable_regions(scenario, state.get("capabilities"))
    best_region = None
    best_count = 0

    for region in playable:
        wb = count_pieces(state, region, BELGAE, WARBAND)
        if wb > best_count:
            best_count = wb
            best_region = region

    return (best_region, best_count)


def _is_in_belgica(region):
    """Check if a region is in Belgica."""
    return REGION_TO_GROUP.get(region) == BELGICA


def _is_within_one_of_ambiorix(state, region, scenario):
    """Check if a region is within one Region of Ambiorix or has Successor.

    Per §4.1.2 / §4.5.1 / §4.5.2 / §4.5.3: Belgae Special Abilities may
    select only Regions within one Region of Ambiorix (same Region or
    adjacent), or the same Region that has his Successor Leader.

    In Ariovistus scenarios, the Belgae leader is Boduognatus (A1.4).

    Args:
        state: Game state dict.
        region: Region to check.
        scenario: Scenario constant.

    Returns:
        True if the region is eligible per Ambiorix/Boduognatus proximity.
    """
    leader_region = find_leader(state, BELGAE)
    if leader_region is None:
        return False

    leader_name = get_leader_in_region(state, leader_region, BELGAE)

    # Determine the named leader for the scenario — §4.5.3, A1.4
    named_leader = AMBIORIX
    if scenario in ARIOVISTUS_SCENARIOS:
        named_leader = BODUOGNATUS

    if leader_name == named_leader:
        # Named leader: within 1 region (same or adjacent) — §4.1.2
        if region == leader_region:
            return True
        return is_adjacent(region, leader_region)
    else:
        # Successor: must be same region — §4.1.2
        return region == leader_region


# ============================================================================
# NODE FUNCTIONS — Main flowchart
# ============================================================================

def node_b1(state):
    """B1: Ambiorix or 4+ Belgic Warbands where non-German enemy has
    an Ally, Citadel, Legion, or ≥4 pieces?

    Per §8.5.1.

    Returns:
        ("Yes", threat_regions) or ("No", []).
    """
    scenario = state["scenario"]
    threat_regions = _get_threat_regions(state, scenario)
    if threat_regions:
        return ("Yes", threat_regions)
    return ("No", [])


def node_b2(state):
    """B2: Belgae 1st on upcoming but not current card, and roll 1-4?

    Per §8.5.2: Check the Faction order on the currently played and next
    showing cards. If the Belgic symbol is first on the next upcoming card
    but not on the currently played card, roll a die: on 1-4, they Pass.
    NOTE: They do not Pass if 1st on both cards or if Winter is showing.

    Returns:
        "Yes" (Pass) or "No" (continue).
    """
    # Check faction order on current and next cards
    current_order = state.get("current_card_faction_order", [])
    next_order = state.get("next_card_faction_order", [])

    # Winter showing means no Pass — §8.5.2 NOTE
    if state.get("frost", False):
        return "No"

    belgae_1st_current = (len(current_order) > 0
                          and current_order[0] == BELGAE)
    belgae_1st_next = (len(next_order) > 0
                       and next_order[0] == BELGAE)

    # Pass only if 1st on next but NOT 1st on current
    if belgae_1st_next and not belgae_1st_current:
        die_result = roll_die(state)
        if die_result <= 4:
            return "Yes"

    return "No"


def node_b3(state):
    """B3: Belgae by Sequence of Play may use Event?

    Per §8.5.2.

    Returns:
        "Yes" or "No".
    """
    return "Yes" if state.get("can_play_event", False) else "No"


def node_b3b(state):
    """B3b: Event Ineffective, or Capability in final year, or 'No Belgae'?

    Per §8.5.2: Also check Non-player Belgae Event Instructions — they may
    render the Event Ineffective or "No Belgae"; if so, proceed to §8.5.3.

    Returns:
        "Yes" (decline, go to Rally check) or "No" (proceed to Event).
    """
    card_id = state.get("current_card_id")
    if card_id is None:
        return "Yes"

    if should_decline_event(state, card_id, BELGAE):
        return "Yes"

    # Check specific instructions that might render ineffective
    scenario = state["scenario"]
    instr = get_event_instruction(card_id, BELGAE, scenario)
    if instr and instr.action == NO_EVENT:
        return "Yes"

    return "No"


def node_b4(state):
    """B4: Rally would add Belgic Ally, Citadel, 3+ Belgic Warbands,
    or Belgic Control?

    Per §8.5.3.

    Returns:
        "Yes" (Rally) or "No" (proceed to Raid check).
    """
    scenario = state["scenario"]
    if _estimate_rally_would_qualify(state, scenario):
        return "Yes"
    return "No"


def node_b5(state):
    """B5: Belgae have 0-3 Resources and roll 1-4?

    Per §8.5.4.

    Returns:
        "Yes" (Raid) or "No" (March).
    """
    resources = state.get("resources", {}).get(BELGAE, 0)
    if resources >= 4:
        return "No"

    die_result = roll_die(state)
    if die_result <= 4:
        return "Yes"

    return "No"


# ============================================================================
# PROCESS NODES
# ============================================================================

def node_b_event(state):
    """B_EVENT: Execute Event.

    Per §8.5.2: Execute per §8.2 — use Shaded text (§8.2.2).
    See Instructions (§8.2.1) if gray laurels on card's Belgae symbol.

    Returns:
        Action dict for Event execution.
    """
    card_id = state.get("current_card_id")
    scenario = state["scenario"]
    preference = get_dual_use_preference(BELGAE, scenario)
    instr = get_event_instruction(card_id, BELGAE, scenario)

    return _make_action(
        ACTION_EVENT,
        details={
            "card_id": card_id,
            "text_preference": preference,
            "instruction": instr.instruction if instr else None,
        },
    )


def node_b_battle(state):
    """B_BATTLE: Battle process.

    Per §8.5.1: Battle only where Belgic Losses less than enemy's AND
    no Loss on Ambiorix.

    1. If Ambiorix meets condition at left BUT will not Battle, March instead.
    2. Check Ambush, Rampage before Battle, OR Enlist.
    3. Fight enemies meeting condition:
       a. Ambiorix versus enemy with fewer mobile forces than Belgae.
    4. Fight other non-Germans (or all enemies in Ariovistus).

    Returns:
        Action dict for Battle, or redirects to March (threat).
    """
    scenario = state["scenario"]
    non_players = state.get("non_player_factions", set())
    threat_regions = _get_threat_regions(state, scenario)

    if not threat_regions:
        return node_b_march_threat(state)

    # Step 1: Check Ambiorix — §8.5.1
    ambiorix_region = _ambiorix_region(state)
    if ambiorix_region and ambiorix_region in threat_regions:
        # Check if Ambiorix can Battle here
        can_ambiorix_battle = False
        enemies = _get_non_german_enemies(scenario)
        for enemy in enemies:
            if count_pieces(state, ambiorix_region, enemy) == 0:
                continue
            if _can_battle_in_region(state, ambiorix_region, scenario, enemy):
                can_ambiorix_battle = True
                break

        if not can_ambiorix_battle:
            # "If Ambiorix meets condition at left BUT will not Battle,
            # March instead." — §8.5.1
            return node_b_march_threat(state)

    # Build battle plan — §8.5.1
    battle_plan = []

    # Step 3a: Ambiorix versus enemy with fewer mobile forces — §8.5.1
    if ambiorix_region and ambiorix_region in threat_regions:
        belgae_mobile = count_mobile_pieces(state, ambiorix_region, BELGAE)
        enemies = _get_non_german_enemies(scenario)
        # Find enemy with fewer mobile pieces than Belgae
        best_enemy = None
        for enemy in enemies:
            if count_pieces(state, ambiorix_region, enemy) == 0:
                continue
            enemy_mobile = count_mobile_pieces(
                state, ambiorix_region, enemy)
            if enemy_mobile < belgae_mobile:
                if _can_battle_in_region(
                        state, ambiorix_region, scenario, enemy):
                    best_enemy = enemy
                    break  # First matching enemy in priority order

        if best_enemy:
            battle_plan.append({
                "region": ambiorix_region,
                "target": best_enemy,
                "is_trigger": True,
            })

    # Step 3/4: Fight enemies meeting trigger condition, then others — §8.5.1
    # "the Belgae next Battle non-German enemies where they can"
    # (or all enemies in Ariovistus per A8.5.1)
    playable = get_playable_regions(scenario, state.get("capabilities"))
    enemies = _get_non_german_enemies(scenario)

    for region in threat_regions:
        if any(bp["region"] == region for bp in battle_plan):
            continue
        for enemy in enemies:
            if count_pieces(state, region, enemy) == 0:
                continue
            if _can_battle_in_region(state, region, scenario, enemy):
                battle_plan.append({
                    "region": region,
                    "target": enemy,
                    "is_trigger": True,
                })
                break

    # Step 4: Fight other non-Germans (or all in Ariovistus) — §8.5.1
    for region in playable:
        if any(bp["region"] == region for bp in battle_plan):
            continue
        if count_pieces(state, region, BELGAE) == 0:
            continue
        for enemy in enemies:
            if count_pieces(state, region, enemy) == 0:
                continue
            if _can_battle_in_region(state, region, scenario, enemy):
                battle_plan.append({
                    "region": region,
                    "target": enemy,
                    "is_trigger": False,
                })
                break

    if not battle_plan:
        return node_b_march_threat(state)

    # Determine SA — §8.5.1: check Ambush → Rampage before Battle → Enlist
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
        },
    )


def _determine_battle_sa(state, battle_plan, scenario):
    """Determine SA for Battle: Ambush → Rampage before Battle → Enlist.

    Per §8.5.1:
    - Check Ambush first.
    - If no Ambush, Rampage before Battle.
    - If no Rampage possible, OR if Command was March, Enlist.

    Returns:
        (sa_action, sa_regions, sa_details) tuple.
    """
    ambush_regions = _check_ambush(state, battle_plan, scenario)
    if ambush_regions:
        # With Ambush, also determine Enlist for in-Battle use — §8.5.1
        enlist_details = _check_enlist_in_battle(state, battle_plan, scenario)
        return (SA_ACTION_AMBUSH, ambush_regions,
                {"enlist": enlist_details})

    # No Ambush → check Rampage before Battle — §8.5.1
    rampage_regions = _check_rampage(
        state, scenario, before_battle=True, battle_plan=battle_plan)
    if rampage_regions:
        # With Rampage, also determine Enlist for in-Battle use
        enlist_details = _check_enlist_in_battle(state, battle_plan, scenario)
        return (SA_ACTION_RAMPAGE, rampage_regions,
                {"enlist": enlist_details})

    # No Rampage → Enlist — §8.5.1
    enlist_details = _check_enlist_after_command(state, scenario)
    if enlist_details:
        return (SA_ACTION_ENLIST, enlist_details.get("regions", []),
                {"enlist": enlist_details})

    return (SA_ACTION_NONE, [], {})


def node_b_march_threat(state):
    """B_MARCH_THREAT: March (from threat).

    Per §8.5.1: March with all Warbands and Leader. Split no origin's
    moving forces.

    1. From Regions that meet upper-left condition AND Leader's Region
       if not already with largest Warband group.
       a. Belgic Leader's Region.
    2. To at least 1 Region, up to number of origin Regions, NOT any origins:
       a. Move to Regions within 1 of most Regions that have Belgae.
       b. Add most Belgic Control able.

    SA: Enlist after March.

    Returns:
        Action dict for March.
    """
    scenario = state["scenario"]
    playable = get_playable_regions(scenario, state.get("capabilities"))
    ambiorix_region = _ambiorix_region(state)
    threat_regions = _get_threat_regions(state, scenario)

    march_plan = {
        "origins": [],
        "destinations": [],
        "type": MARCH_THREAT,
    }

    # Determine origins — §8.5.1
    # "March all mobile Belgic Forces out of each Region that either meets
    # the 'Battle or March under Threat' condition above or has the Belgic
    # Leader but not the single largest group of Belgic Warbands on the map."
    origins = set()
    for region in threat_regions:
        origins.add(region)

    # Leader's Region if not with largest Warband group
    if ambiorix_region:
        largest_region, largest_count = _find_largest_belgae_warband_group(
            state, scenario)
        if ambiorix_region != largest_region:
            origins.add(ambiorix_region)

    # Sort: Leader's Region first — §8.5.1
    # "March first with the Belgic Leader (and the Belgic Warbands with him)
    # then with other groups."
    origin_list = sorted(origins)
    if ambiorix_region and ambiorix_region in origin_list:
        origin_list.remove(ambiorix_region)
        origin_list.insert(0, ambiorix_region)

    march_plan["origins"] = origin_list

    # Determine destinations — §8.5.1
    # "into at least one destination Region and up to the number of
    # destinations equal to the number of origin Regions."
    # "They do not enter any of the above Regions that other Belgae
    # are departing."
    max_dests = len(origin_list)
    excluded = set(origin_list)

    # Score each candidate destination
    candidates = []
    for region in playable:
        if region in excluded:
            continue
        # (a) within 1 of most Regions that have Belgae — §8.5.1
        adj_belgae = _count_adjacent_belgae_regions(state, region, scenario)
        # (b) add most Belgic Control — §8.5.1
        would_add_control = 0
        if not is_controlled_by(state, region, BELGAE):
            would_add_control = 1
        candidates.append((region, adj_belgae, would_add_control))

    # Sort by (a) then (b) — §8.5.1
    candidates.sort(key=lambda x: (x[1], x[2]), reverse=True)

    for region, _, _ in candidates[:max_dests]:
        march_plan["destinations"].append(region)

    if not march_plan["destinations"]:
        # Must March to at least 1 — pick random playable
        valid = [r for r in playable if r not in excluded]
        if valid:
            march_plan["destinations"].append(random_select(state, valid))

    # SA: Enlist after March — §8.5.1
    sa = SA_ACTION_NONE
    sa_regions = []
    sa_details = {}

    # Check Britannia restriction — §4.1.3
    marched_britannia = (BRITANNIA in origins
                         or BRITANNIA in march_plan["destinations"])
    if not marched_britannia:
        enlist_details = _check_enlist_after_command(state, scenario)
        if enlist_details:
            sa = SA_ACTION_ENLIST
            sa_regions = enlist_details.get("regions", [])
            sa_details = {"enlist": enlist_details}

    return _make_action(
        ACTION_MARCH,
        regions=march_plan["destinations"],
        sa=sa,
        sa_regions=sa_regions,
        details={"march_plan": march_plan, **sa_details},
    )


def node_b_rally(state):
    """B_RALLY: Rally process.

    Per §8.5.3: Rally wherever able to place a piece:
    1. Replace City Ally with Citadel.
    2. Place all Allies able.
    3. Place all Warbands able:
       a. To add any Belgic Control.

    SA: Rampage after Rally.

    Returns:
        Action dict for Rally.
    """
    scenario = state["scenario"]
    playable = get_playable_regions(scenario, state.get("capabilities"))

    rally_plan = {
        "citadels": [],
        "allies": [],
        "warbands": [],
    }

    avail_citadels = get_available(state, BELGAE, CITADEL)
    avail_allies = get_available(state, BELGAE, ALLY)
    avail_warbands = get_available(state, BELGAE, WARBAND)

    # Step 1: Citadels — replace Allies in Cities — §8.5.3
    for region in playable:
        if avail_citadels <= 0:
            break
        tribes = get_tribes_in_region(region, scenario)
        for tribe in tribes:
            if avail_citadels <= 0:
                break
            tribe_info = state["tribes"].get(tribe, {})
            if (tribe_info.get("allied_faction") == BELGAE
                    and is_city_tribe(tribe)):
                rally_plan["citadels"].append({
                    "region": region, "tribe": tribe,
                })
                avail_citadels -= 1
                avail_allies += 1  # Freed Ally

    # Step 2: Allies — place all possible — §8.5.3
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
            if (count_pieces(state, region, BELGAE) > 0
                    or is_controlled_by(state, region, BELGAE)):
                rally_plan["allies"].append({
                    "region": region, "tribe": tribe,
                })
                avail_allies -= 1

    # Step 3: Warbands — place all possible — §8.5.3
    # "first where they would add any Belgic Control" — §8.5.3
    wb_candidates = []
    for region in playable:
        has_base = False
        tribes = get_tribes_in_region(region, scenario)
        for tribe in tribes:
            tribe_info = state["tribes"].get(tribe, {})
            if tribe_info.get("allied_faction") == BELGAE:
                has_base = True
                break
        if count_pieces(state, region, BELGAE, CITADEL) > 0:
            has_base = True
        if is_controlled_by(state, region, BELGAE):
            has_base = True

        if has_base:
            adds_control = 0 if is_controlled_by(state, region, BELGAE) else 1
            wb_candidates.append((region, adds_control))

    # Sort: regions that add Control first — §8.5.3
    wb_candidates.sort(key=lambda x: x[1], reverse=True)

    for region, _ in wb_candidates:
        if avail_warbands <= 0:
            break
        rally_plan["warbands"].append(region)
        avail_warbands -= 1

    # SA: Rampage after Rally — §8.5.3 / flowchart B_RALLY → B_RAMPAGE
    # If none: Enlist — flowchart B_RAMPAGE → If none: B_ENLIST
    sa = SA_ACTION_NONE
    sa_regions = []
    sa_details = {}
    rampage_regions = _check_rampage(state, scenario, before_battle=False)
    if rampage_regions:
        sa = SA_ACTION_RAMPAGE
        sa_regions = rampage_regions
    else:
        # Flowchart: B_RAMPAGE → If none: B_ENLIST
        enlist_details = _check_enlist_after_command(state, scenario)
        if enlist_details:
            sa = SA_ACTION_ENLIST
            sa_regions = enlist_details.get("regions", [])
            sa_details = {"enlist": enlist_details}

    all_regions = list({entry["region"] for entry in rally_plan["citadels"]}
                       | {entry["region"] for entry in rally_plan["allies"]}
                       | set(rally_plan["warbands"]))

    return _make_action(
        ACTION_RALLY,
        regions=all_regions,
        sa=sa,
        sa_regions=sa_regions,
        details={"rally_plan": rally_plan, **sa_details},
    )


def node_b_raid(state):
    """B_RAID: Raid process.

    Per §8.5.4: Raid if would gain 2+ Resources total.
    1. Versus players (only): (1) Romans (2) Aedui (3) Other
    2. In non-Devastated Regions, versus no Faction.

    SA: Rampage after Raid.
    IF NONE: Pass.

    Returns:
        Action dict for Raid, or Pass.
    """
    scenario = state["scenario"]
    enough, raid_plan = _would_raid_gain_enough(state, scenario)

    if not enough:
        return _make_action(ACTION_PASS)

    # SA: Rampage after Raid — §8.5.4 / flowchart B_RAID → B_RAMPAGE
    # If none: Enlist — flowchart B_RAMPAGE → If none: B_ENLIST
    sa = SA_ACTION_NONE
    sa_regions = []
    sa_details = {}
    rampage_regions = _check_rampage(state, scenario, before_battle=False)
    if rampage_regions:
        sa = SA_ACTION_RAMPAGE
        sa_regions = rampage_regions
    else:
        # Flowchart: B_RAMPAGE → If none: B_ENLIST
        enlist_details = _check_enlist_after_command(state, scenario)
        if enlist_details:
            sa = SA_ACTION_ENLIST
            sa_regions = enlist_details.get("regions", [])
            sa_details = {"enlist": enlist_details}

    return _make_action(
        ACTION_RAID,
        regions=[r["region"] for r in raid_plan],
        sa=sa,
        sa_regions=sa_regions,
        details={"raid_plan": raid_plan, **sa_details},
    )


def node_b_march(state):
    """B_MARCH: March (to add Control).

    Per §8.5.5: March into up to 3 Regions:
    1. To add Control to up to 2 Regions:
       (1) In Belgica, with most Warbands able except 1 per origin,
           while losing no Belgic Control.
       (2) Outside Belgica, with fewest Warbands needed to take Control.
    2. With Leader alone, to 1 Region above if needed to join most Belgic
       pieces able, OR to another Region to end Leader where >3 Belgic Warbands.

    SA: Enlist after March.
    IF NONE (or 0 Resources, Frost): Raid per §8.5.4.

    Returns:
        Action dict for March, or redirects to Raid.
    """
    scenario = state["scenario"]
    playable = get_playable_regions(scenario, state.get("capabilities"))
    resources = state.get("resources", {}).get(BELGAE, 0)

    # IF NONE: 0 Resources or Frost — §8.5.5
    if resources <= 0 or is_frost_active(state):
        return node_b_raid(state)

    march_plan = {
        "control_destinations": [],
        "leader_destination": None,
        "origins": [],
        "type": MARCH_CONTROL,
    }

    # Step 1: March to add Control to up to 2 Regions — §8.5.5
    # Priority: Belgica first, then outside Belgica
    control_dests_found = 0

    # (1) In Belgica — §8.5.5
    belgica_candidates = []
    for region in playable:
        if not _is_in_belgica(region):
            continue
        if is_controlled_by(state, region, BELGAE):
            continue  # Already have Control
        # Calculate how many Warbands we'd need to March in
        # to take Belgic Control
        belgica_candidates.append(region)

    # Score Belgica candidates by fewest Warbands needed
    for dest in belgica_candidates:
        if control_dests_found >= 2:
            break
        # Find origins that can supply Warbands
        origin_supply = []
        for origin in playable:
            if origin == dest:
                continue
            adj_regions = get_adjacent(origin, scenario)
            if dest not in adj_regions:
                continue
            origin_wb = count_pieces(state, origin, BELGAE, WARBAND)
            # Leave 1 per origin, and don't remove Control — §8.5.5
            keep_for_control = 0
            if is_controlled_by(state, origin, BELGAE):
                # Need to keep enough to retain control
                keep_for_control = 1
            available_from_origin = max(
                0, origin_wb - 1 - keep_for_control)
            if available_from_origin > 0:
                origin_supply.append((origin, available_from_origin))

        total_available = sum(s[1] for s in origin_supply)
        if total_available > 0:
            march_plan["control_destinations"].append(dest)
            march_plan["origins"].extend([s[0] for s in origin_supply])
            control_dests_found += 1

    # (2) Outside Belgica — §8.5.5
    if control_dests_found < 2:
        outside_candidates = []
        for region in playable:
            if _is_in_belgica(region):
                continue
            if is_controlled_by(state, region, BELGAE):
                continue

            # "with fewest Warbands needed to take Control" — §8.5.5
            # Estimate pieces needed
            origin_supply = []
            for origin in playable:
                if origin == region:
                    continue
                adj_regions = get_adjacent(origin, scenario)
                if region not in adj_regions:
                    continue
                origin_wb = count_pieces(state, origin, BELGAE, WARBAND)
                available_from_origin = max(0, origin_wb - 1)
                if available_from_origin > 0:
                    origin_supply.append((origin, available_from_origin))

            total_available = sum(s[1] for s in origin_supply)
            if total_available > 0:
                outside_candidates.append(
                    (region, total_available, origin_supply))

        # Sort: fewest Warbands needed — §8.5.5
        outside_candidates.sort(key=lambda x: x[1])

        for dest, _, origin_supply in outside_candidates:
            if control_dests_found >= 2:
                break
            march_plan["control_destinations"].append(dest)
            march_plan["origins"].extend([s[0] for s in origin_supply])
            control_dests_found += 1

    # Step 2: Leader alone — §8.5.5
    ambiorix_region = _ambiorix_region(state)
    if ambiorix_region:
        # Option A: "to 1 Region above if needed to join most Belgic
        # pieces able" — §8.5.5
        if march_plan["control_destinations"]:
            best_dest = None
            best_pieces = -1
            for dest in march_plan["control_destinations"]:
                belgae_there = count_pieces(state, dest, BELGAE)
                if belgae_there > best_pieces:
                    best_pieces = belgae_there
                    best_dest = dest
            if best_dest and best_dest != ambiorix_region:
                march_plan["leader_destination"] = best_dest

        # Option B: "OR to another Region to end Leader where >3
        # Belgic Warbands" — §8.5.5
        if march_plan["leader_destination"] is None:
            for region in playable:
                if region == ambiorix_region:
                    continue
                adj_regions = get_adjacent(ambiorix_region, scenario)
                if region not in adj_regions:
                    continue
                wb_there = count_pieces(state, region, BELGAE, WARBAND)
                if wb_there > 3:
                    march_plan["leader_destination"] = region
                    break

    has_any_march = (march_plan["control_destinations"]
                     or march_plan["leader_destination"] is not None)

    if not has_any_march:
        return node_b_raid(state)

    # SA: Enlist after March — §8.5.5
    sa = SA_ACTION_NONE
    sa_regions = []
    sa_details = {}

    # Check Britannia restriction — §4.1.3
    all_origins = set(march_plan["origins"])
    all_dests = set(march_plan["control_destinations"])
    if march_plan["leader_destination"]:
        all_dests.add(march_plan["leader_destination"])
    marched_britannia = (BRITANNIA in all_origins or BRITANNIA in all_dests)

    if not marched_britannia:
        enlist_details = _check_enlist_after_command(state, scenario)
        if enlist_details:
            sa = SA_ACTION_ENLIST
            sa_regions = enlist_details.get("regions", [])
            sa_details = {"enlist": enlist_details}

    dest_list = list(march_plan["control_destinations"])
    if march_plan["leader_destination"]:
        dest_list.append(march_plan["leader_destination"])

    return _make_action(
        ACTION_MARCH,
        regions=dest_list,
        sa=sa,
        sa_regions=sa_regions,
        details={"march_plan": march_plan, **sa_details},
    )


# ============================================================================
# SPECIAL ABILITY NODES
# ============================================================================

def _check_ambush(state, battle_plan, scenario):
    """B_AMBUSH: Determine Ambush regions.

    Per §8.5.1:
    1. In 1st Battle, BUT only if Retreat out could lessen removals
       AND/OR any Counterattack Loss to Belgae is possible.
    2. In all other Battles only if Belgae Ambushed in the 1st Battle.

    Ambush requires (§4.5.3 / §4.3.3):
    - More Hidden Belgic Warbands than Hidden Defenders in the region.
    - Region must be within one Region of Ambiorix or have Successor.

    Returns:
        List of Ambush regions, or empty.
    """
    if not battle_plan:
        return []

    first_battle = battle_plan[0]
    region = first_battle["region"]
    enemy = first_battle["target"]

    # §4.5.3 / §4.3.3: Region must be within 1 of Ambiorix or Successor
    if not _is_within_one_of_ambiorix(state, region, scenario):
        return []

    # §4.5.3 eligibility: more Hidden Belgae Warbands than Hidden enemy
    hidden_belgae = count_pieces_by_state(
        state, region, BELGAE, WARBAND, HIDDEN)
    hidden_enemy = count_pieces_by_state(
        state, region, enemy, WARBAND, HIDDEN)
    if hidden_belgae <= hidden_enemy:
        return []

    # Check if Ambush is needed in 1st Battle — §8.5.1
    should_ambush_first = False

    # Estimate Belgae Attack losses
    losses_inflicted, losses_suffered = _estimate_battle_losses(
        state, region, scenario, enemy)

    # (a) "Retreat out could lessen removals" — §8.5.1
    enemy_mobile = count_mobile_pieces(state, region, enemy)
    if enemy_mobile > 0 and losses_inflicted > 0:
        should_ambush_first = True

    # (b) "any Counterattack Loss to Belgae is possible" — §8.5.1
    # "A defending Legion or Leader would meet the 2nd requirement"
    if count_pieces(state, region, enemy, LEGION) > 0:
        should_ambush_first = True
    if get_leader_in_region(state, region, enemy) is not None:
        should_ambush_first = True

    if not should_ambush_first:
        return []

    # If Ambushed in 1st Battle, Ambush in all others where eligible — §8.5.1
    # "each other Battle possible" — filter by §4.5.3 eligibility
    ambush_regions = [region]
    for bp in battle_plan[1:]:
        bp_region = bp["region"]
        bp_enemy = bp["target"]
        # §4.5.3: within 1 of Ambiorix + more Hidden Belgae than Hidden enemy
        if not _is_within_one_of_ambiorix(state, bp_region, scenario):
            continue
        bp_hidden_belgae = count_pieces_by_state(
            state, bp_region, BELGAE, WARBAND, HIDDEN)
        bp_hidden_enemy = count_pieces_by_state(
            state, bp_region, bp_enemy, WARBAND, HIDDEN)
        if bp_hidden_belgae > bp_hidden_enemy:
            ambush_regions.append(bp_region)

    return ambush_regions


def _check_rampage(state, scenario, *, before_battle=False, battle_plan=None):
    """B_RAMPAGE: Determine Rampage regions.

    Per §4.5.2: Rampage requires Hidden Belgic Warbands present and the
    region must be within one Region of Ambiorix or have Successor.
    Target faction must be Roman or Gallic (not Germanic) and must NOT
    have a Leader, Citadel, or Fort in the region.

    Per §8.5.1: Rampage with all Warbands able to remove or Retreat enemies.
    If before Battle, no Rampage against enemy's last piece.

    Priority per §8.5.1:
    1. To force removal of pieces, assuming no one grants Retreat.
    2. To add most Belgic Control.
    3. Elsewhere: Versus (1) Romans (2) Aedui (3) Arverni

    Returns:
        List of Rampage region dicts, or empty.
    """
    playable = get_playable_regions(scenario, state.get("capabilities"))
    rampage_regions = []

    # Collect battle regions if before battle
    battle_region_set = set()
    if before_battle and battle_plan:
        battle_region_set = {bp["region"] for bp in battle_plan}

    # Find regions where Belgae have Hidden Warbands — §4.5.2
    for region in playable:
        hidden_wb = count_pieces_by_state(
            state, region, BELGAE, WARBAND, HIDDEN)
        if hidden_wb == 0:
            continue

        # §4.5.2: Must be within 1 of Ambiorix or have Successor
        if not _is_within_one_of_ambiorix(state, region, scenario):
            continue

        # Check for enemies — §8.5.1
        # §4.5.2: Target must be Roman or Gallic (not Germanic)
        enemy_order = (ROMANS, AEDUI, ARVERNI)
        for enemy in enemy_order:
            enemy_count = count_pieces(state, region, enemy)
            if enemy_count == 0:
                continue

            # §4.5.2: Target must NOT have Leader, Citadel, or Fort
            if get_leader_in_region(state, region, enemy) is not None:
                continue
            if count_pieces(state, region, enemy, CITADEL) > 0:
                continue
            if count_pieces(state, region, enemy, FORT) > 0:
                continue

            # If before Battle, don't Rampage against last piece — §8.5.1
            if before_battle and region in battle_region_set:
                if enemy_count <= 1:
                    continue

            # Would this force removal? — §8.5.1 step 1
            # "force removal of pieces, assuming no Faction grants Retreat"
            forces_removal = False
            enemy_mobile = count_mobile_pieces(state, region, enemy)
            if enemy_mobile > 0 and hidden_wb > 0:
                forces_removal = True

            # Would this add Belgic Control? — §8.5.1 step 2
            adds_control = not is_controlled_by(state, region, BELGAE)

            rampage_regions.append({
                "region": region,
                "target": enemy,
                "forces_removal": forces_removal,
                "adds_control": adds_control,
            })
            break  # One target per region

    # Sort by priority — §8.5.1
    # 1. Force removal
    # 2. Add most Belgic Control
    # 3. Enemy priority (Romans first, etc.)
    enemy_priority = {ROMANS: 0, AEDUI: 1, ARVERNI: 2}
    rampage_regions.sort(key=lambda x: (
        -int(x["forces_removal"]),
        -int(x["adds_control"]),
        enemy_priority.get(x["target"], 99),
    ))

    return rampage_regions


def _check_enlist_in_battle(state, battle_plan, scenario):
    """B_ENLIST (in Battle): Enlist Germans as Belgae in Battle.

    Per §8.5.1: "If there is any already selected Battle Region in which
    the Belgae could Enlist Germanic Warbands to add to enemy Losses
    and/or absorb Losses from a possible Counterattack, the Belgae do so."

    Per §4.5.1: affected Regions must be within one Region of Ambiorix
    or have the Belgic Successor.

    Returns:
        Dict with enlist details, or None.
    """
    if not battle_plan:
        return None

    for bp in battle_plan:
        region = bp["region"]

        # §4.5.1: Must be within 1 of Ambiorix or have Successor
        if not _is_within_one_of_ambiorix(state, region, scenario):
            continue

        # Check if Germanic Warbands exist in this region
        german_wb = count_pieces(state, region, GERMANS, WARBAND)
        if german_wb == 0:
            continue

        # Would adding German Warbands help?
        # "add to enemy Losses and/or absorb Losses from a possible
        # Counterattack" — §8.5.1
        enemy = bp["target"]
        enemy_pieces = count_pieces(state, region, enemy)
        if enemy_pieces > 0:
            return {
                "type": "in_battle",
                "region": region,
                "german_warbands": german_wb,
                "regions": [region],
            }

    return None


def _check_enlist_after_command(state, scenario):
    """B_ENLIST (after Command): Enlist to add a free German Command.

    Per §8.5.1: Add a free Germanic Command in 1 Region:
    1. Battle if able to cause enemy Loss:
       Versus a. player b. other Non-player.
    2. March 2+ and most Germans able:
       (1) From Belgica OR Germania to Roman, Aedui, or Arverni Control.
       (2) In place with 2+ Revealed/Scouted Warbands to Hide/remove marker.
    3. Rally to place a piece:
       (1) Ally (2) most Warbands able.
    4. Raid to take 1-2 Resources from player.

    Per §4.5.1: The Region must be in the usual vicinity of the Belgic
    Leader for a Special Ability (within one of Ambiorix or Successor).

    A8.5.1: If Marching Germans, move them out of Belgica/Germania/Treveri.

    Returns:
        Dict with enlist details, or None.
    """
    playable = get_playable_regions(scenario, state.get("capabilities"))
    non_players = state.get("non_player_factions", set())

    # Step 1: Battle — §8.5.1
    for region in playable:
        # §4.5.1: Must be within 1 of Ambiorix or have Successor
        if not _is_within_one_of_ambiorix(state, region, scenario):
            continue

        german_wb = count_pieces(state, region, GERMANS, WARBAND)
        if german_wb == 0:
            continue

        # Check if Battle can cause enemy Loss
        # (a) against player, (b) against Non-player
        for enemy in (ROMANS, AEDUI, ARVERNI, BELGAE):
            if enemy == BELGAE:
                continue  # Don't battle self
            if count_pieces(state, region, enemy) == 0:
                continue

            # Estimate German Attack Losses
            german_mobile = count_mobile_pieces(state, region, GERMANS)
            enemy_fort = count_pieces(state, region, enemy, FORT)
            enemy_citadel = count_pieces(state, region, enemy, CITADEL)
            attack_raw = german_wb * 0.5
            if enemy_fort > 0 or enemy_citadel > 0:
                attack_raw = attack_raw / 2
            losses = int(attack_raw)

            if losses > 0:
                is_player_target = enemy not in non_players
                return {
                    "type": "german_battle",
                    "region": region,
                    "target": enemy,
                    "is_player": is_player_target,
                    "regions": [region],
                }

    # Step 2: March — §8.5.1
    # (1) From Belgica/Germania to enemy Control
    # A8.5.1: also from Treveri in Ariovistus
    # §4.5.1: origin must be within 1 of Ambiorix; dest need not be
    march_origin_groups = list(BELGICA_REGIONS) + list(GERMANIA_REGIONS)
    if scenario in ARIOVISTUS_SCENARIOS:
        march_origin_groups.append(TREVERI)

    for origin in march_origin_groups:
        if origin not in playable:
            continue
        # §4.5.1: origin must be within 1 of Ambiorix
        if not _is_within_one_of_ambiorix(state, origin, scenario):
            continue
        german_wb = count_pieces(state, origin, GERMANS, WARBAND)
        if german_wb < 2:
            continue

        # Find destination with enemy Control
        for dest in get_adjacent(origin, scenario):
            if dest not in playable:
                continue
            # Player Control first, then Non-player — §8.5.1
            for target in (ROMANS, AEDUI, ARVERNI):
                if is_controlled_by(state, dest, target):
                    is_player = target not in non_players
                    return {
                        "type": "german_march",
                        "origin": origin,
                        "destination": dest,
                        "target_control": target,
                        "is_player": is_player,
                        "warbands": german_wb,
                        "regions": [origin, dest],
                    }

    # (2) In place with 2+ Revealed/Scouted to Hide — §8.5.1
    for region in playable:
        # §4.5.1: Must be within 1 of Ambiorix
        if not _is_within_one_of_ambiorix(state, region, scenario):
            continue
        revealed_wb = count_pieces_by_state(
            state, region, GERMANS, WARBAND, REVEALED)
        scouted_wb = count_pieces_by_state(
            state, region, GERMANS, WARBAND, SCOUTED)
        unhidden = revealed_wb + scouted_wb
        if unhidden >= 2:
            return {
                "type": "german_march_hide",
                "region": region,
                "warbands_to_hide": unhidden,
                "regions": [region],
            }

    # Step 3: Rally — §8.5.1
    avail_german_allies = get_available(state, GERMANS, ALLY)
    avail_german_wb = get_available(state, GERMANS, WARBAND)

    # (1) Place Ally
    if avail_german_allies > 0:
        for region in playable:
            # §4.5.1: Must be within 1 of Ambiorix
            if not _is_within_one_of_ambiorix(state, region, scenario):
                continue
            if count_pieces(state, region, GERMANS) == 0:
                continue
            tribes = get_tribes_in_region(region, scenario)
            for tribe in tribes:
                tribe_info = state["tribes"].get(tribe, {})
                if tribe_info.get("allied_faction") is None:
                    return {
                        "type": "german_rally",
                        "region": region,
                        "place": "ally",
                        "tribe": tribe,
                        "regions": [region],
                    }

    # (2) Place most Warbands
    if avail_german_wb > 0:
        for region in playable:
            # §4.5.1: Must be within 1 of Ambiorix
            if not _is_within_one_of_ambiorix(state, region, scenario):
                continue
            has_base = False
            tribes = get_tribes_in_region(region, scenario)
            for tribe in tribes:
                tribe_info = state["tribes"].get(tribe, {})
                if tribe_info.get("allied_faction") == GERMANS:
                    has_base = True
                    break
            if is_controlled_by(state, region, GERMANS):
                has_base = True
            if has_base:
                return {
                    "type": "german_rally",
                    "region": region,
                    "place": "warbands",
                    "regions": [region],
                }

    # Step 4: Raid — §8.5.1
    # "take 1-2 Resources from player"
    for region in playable:
        # §4.5.1: Must be within 1 of Ambiorix
        if not _is_within_one_of_ambiorix(state, region, scenario):
            continue
        german_hidden = count_pieces_by_state(
            state, region, GERMANS, WARBAND, HIDDEN)
        if german_hidden == 0:
            continue
        for target in (ROMANS, AEDUI, ARVERNI):
            if target in non_players:
                continue
            if count_pieces(state, region, target) == 0:
                continue
            if (count_pieces(state, region, target, CITADEL) > 0
                    or count_pieces(state, region, target, FORT) > 0):
                continue
            return {
                "type": "german_raid",
                "region": region,
                "target": target,
                "regions": [region],
            }

    return None


# ============================================================================
# WINTER NODES
# ============================================================================

def node_b_quarters(state):
    """B_QUARTERS: Quarters Phase.

    Per §8.5.6:
    - Leave Devastated if no Ally/Citadel for random adjacent Belgae-
      Controlled region.
    - Move Leader and/or one group of Warbands to join Leader with
      largest group of Belgic Warbands able; within that, get/keep
      Leader within one Region of most Regions with Belgic Forces.
    - Leave behind at least 1 Warband AND enough to keep Control.

    A8.5.6: In Ariovistus, first move to Morini, Nervii, or Treveri
    (if able, instead of keeping Leader within 1 of most Regions with
    Belgic Forces).

    Returns:
        Quarters action details dict.
    """
    scenario = state["scenario"]
    playable = get_playable_regions(scenario, state.get("capabilities"))

    quarters_plan = {
        "leave_devastated": [],
        "leader_move": None,
    }

    # Step 1: Leave Devastated Regions with no Ally/Citadel — §8.5.6
    # "for random adjacent Regions that they Control"
    for region in playable:
        if count_pieces(state, region, BELGAE) == 0:
            continue
        is_devastated = state["spaces"].get(region, {}).get("devastated", False)
        if not is_devastated:
            continue
        has_ally = False
        tribes = get_tribes_in_region(region, scenario)
        for tribe in tribes:
            if state["tribes"].get(tribe, {}).get("allied_faction") == BELGAE:
                has_ally = True
                break
        has_citadel = count_pieces(state, region, BELGAE, CITADEL) > 0
        if not has_ally and not has_citadel:
            # Find random adjacent Belgae-Controlled region — §8.5.6
            controlled_adj = [
                adj for adj in get_adjacent(region, scenario)
                if is_controlled_by(state, adj, BELGAE)
            ]
            if controlled_adj:
                dest = random_select(state, controlled_adj)
                quarters_plan["leave_devastated"].append({
                    "from": region, "to": dest,
                })

    # Step 2: Move Leader/group — §8.5.6
    # "join the Leader with the largest group of Belgic Warbands able
    # and, within that, to get or keep the Leader within one Region of
    # the most Regions with Belgic Forces able."
    ambiorix_region = _ambiorix_region(state)
    if ambiorix_region:
        best_dest = None
        best_wb_count = -1
        best_adj_count = -1

        candidates = [ambiorix_region] + list(
            get_adjacent(ambiorix_region, scenario))

        if scenario in ARIOVISTUS_SCENARIOS:
            # A8.5.6: first move to Morini, Nervii, or Treveri
            belgae_quarters_targets = (MORINI, NERVII, TREVERI)
            for target in belgae_quarters_targets:
                if target in candidates and target != ambiorix_region:
                    wb_count = count_pieces(state, target, BELGAE, WARBAND)
                    if wb_count > best_wb_count:
                        best_wb_count = wb_count
                        best_dest = target

            # If none of the Ariovistus targets are reachable, fall through
            # to normal logic
            if best_dest is None:
                for dest in candidates:
                    wb_count = count_pieces(state, dest, BELGAE, WARBAND)
                    adj_count = _count_adjacent_belgae_regions(
                        state, dest, scenario)
                    if (wb_count > best_wb_count
                            or (wb_count == best_wb_count
                                and adj_count > best_adj_count)):
                        best_wb_count = wb_count
                        best_adj_count = adj_count
                        best_dest = dest
        else:
            # Base game — §8.5.6
            for dest in candidates:
                wb_count = count_pieces(state, dest, BELGAE, WARBAND)
                adj_count = _count_adjacent_belgae_regions(
                    state, dest, scenario)
                if (wb_count > best_wb_count
                        or (wb_count == best_wb_count
                            and adj_count > best_adj_count)):
                    best_wb_count = wb_count
                    best_adj_count = adj_count
                    best_dest = dest

        if best_dest and best_dest != ambiorix_region:
            # §8.5.6: "leave behind at least one Warband and at least
            # the number of Warbands needed to retain any Belgic Control"
            origin_wb = count_pieces(state, ambiorix_region, BELGAE, WARBAND)
            min_leave = 1  # At least 1 Warband — §8.5.6
            if is_controlled_by(state, ambiorix_region, BELGAE):
                # Need to keep enough Warbands to retain Control
                # Calculate how many non-Belgae pieces are here
                total_non_belgae = 0
                for faction in (ROMANS, ARVERNI, AEDUI, GERMANS):
                    total_non_belgae += count_pieces(
                        state, ambiorix_region, faction)
                # Leader is also moving out, so only count non-Leader
                # non-Warband Belgae pieces staying behind (Allies, Citadels)
                belgae_non_wb = count_pieces(state, ambiorix_region, BELGAE) \
                    - origin_wb
                # Subtract the Leader (who is moving out)
                belgae_staying_non_wb = max(0, belgae_non_wb - 1)
                # Belgae need more than other factions for Control
                warbands_for_control = max(
                    0, total_non_belgae - belgae_staying_non_wb + 1)
                min_leave = max(min_leave, warbands_for_control)

            movable_wb = max(0, origin_wb - min_leave)
            if movable_wb > 0 or origin_wb == 0:
                quarters_plan["leader_move"] = {
                    "from": ambiorix_region, "to": best_dest,
                    "warbands_moved": movable_wb,
                    "warbands_left": min_leave,
                }

    return quarters_plan


def node_b_spring(state):
    """B_SPRING: Spring Phase.

    Per §8.3.2 / §6.6: Place Successor at most Belgae.

    Returns:
        Spring action details dict, or None if nothing to do.
    """
    ambiorix_region = _ambiorix_region(state)
    if ambiorix_region is not None:
        return None  # Ambiorix already on map

    best_region = get_leader_placement_region(state, BELGAE)
    if best_region:
        return {"place_leader": AMBIORIX, "region": best_region}
    return None


# ============================================================================
# AGREEMENTS
# ============================================================================

def node_b_agreements(state, requesting_faction, request_type):
    """B_AGREEMENTS: Agreement decisions.

    Per §8.4.2:
    - Never transfer or agree to Supply Line, Retreat, Quarters.
    - Always Harass Romans.

    Args:
        state: Game state dict.
        requesting_faction: Faction making the request.
        request_type: "supply_line", "retreat", "quarters", "resources",
                      "harassment".

    Returns:
        True if Belgae agree.
    """
    if request_type == "harassment":
        # Always Harass Romans — §8.4.2
        if requesting_faction == ROMANS:
            return True
        return False

    # Never agree to anything else — §8.4.2
    return False


# ============================================================================
# MAIN FLOWCHART DRIVER
# ============================================================================

def execute_belgae_turn(state):
    """Walk the Belgae bot flowchart and return the chosen action.

    Implements the full decision tree: B1 → B2 → B3 → B3b → B4 → B5
    and all process nodes.

    The Belgae bot runs in both base game and Ariovistus scenarios.

    Args:
        state: Game state dict.

    Returns:
        Action dict describing the Belgae bot's decision.
    """
    scenario = state["scenario"]

    # §8.1.2: Upgrade Limited Command from SoP
    if state.get("limited_by_sop", False):
        pass  # NP gets full Command + SA — upgrade is implicit

    # B1: Battle or March under Threat?
    b1_result, threat_regions = node_b1(state)

    if b1_result == "Yes":
        # Try Battle, may redirect to March (threat)
        return node_b_battle(state)

    # B2: Belgae 1st on upcoming but not current, and roll 1-4?
    b2_result = node_b2(state)
    if b2_result == "Yes":
        return _make_action(ACTION_PASS)

    # B3: Can play Event by SoP?
    b3_result = node_b3(state)
    if b3_result == "Yes":
        # B3b: Decline checks
        b3b_result = node_b3b(state)
        if b3b_result == "No":
            return node_b_event(state)

    # B4: Rally?
    b4_result = node_b4(state)
    if b4_result == "Yes":
        return node_b_rally(state)

    # B5: Raid (0-3 Resources and roll 1-4)?
    b5_result = node_b5(state)
    if b5_result == "Yes":
        return node_b_raid(state)

    # Default: March to add Control — §8.5.5
    return node_b_march(state)
