"""
Non-Player Germanic Tribes flowchart — Chapter A8.7.

Every node from the German bot flowchart (G1 through G5, plus G_BATTLE,
G_MARCH_THREAT, G_RAID, G_RALLY, G_MARCH_EXPAND, G_EVENT, and SAs
G_AMBUSH, G_INTIMIDATE, G_SETTLE) is a labeled function.

The German bot is Ariovistus-only. In the base game, Germans are game-run
via §6.2 (Germans Phase) — they have no Sequence of Play slot and no
flowchart. In Ariovistus they replace Arverni's slot in the SoP as a
full Non-Player faction (A8.0, A8.7).

Per A8.4: throughout §8.4 references, treat "Arverni" as "Germans",
"Gauls" as "Gauls or Germans", and "Germans" as "Arverni". So:
- Germans never voluntarily transfer Resources, nor agree to Supply
  Lines / Retreat / Quarters.
- Germans always Harass Roman March and Seize.

Node functions return an action dict describing what the bot decided to
do. The dispatch loop calls execute_german_turn(state) which walks the
flowchart.
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
    SA_AMBUSH, SA_SETTLE, SA_INTIMIDATE,
    # Leaders
    ARIOVISTUS_LEADER, SUCCESSOR,
    # Regions
    GERMANIA_REGIONS, BELGICA_REGIONS,
    # Events
    EVENT_SHADED,
    # Markers
    MARKER_INTIMIDATED, MARKER_DISPERSED, MARKER_DISPERSED_GATHERING,
    MARKER_DEVASTATED,
    # Die
    DIE_MIN, DIE_MAX,
    # Map
    REGION_TO_GROUP, GERMANIA,
    # Costs
    GERMAN_RALLY_COST_OUTSIDE_GERMANIA_NO_SETTLEMENT,
    GERMAN_RALLY_COST_AT_SETTLEMENT,
    GERMAN_RALLY_COST_IN_GERMANIA,
    SETTLE_COST,
    GALLIC_BATTLE_COST,
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
    get_dual_use_preference, get_event_instruction,
    get_faction_targeting_order, get_enemy_piece_target_order,
    is_frost_active,
    random_select, roll_die,
    count_mobile_pieces, count_faction_allies_and_citadels,
    get_leader_placement_region,
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
SA_ACTION_SETTLE = "Settle"
SA_ACTION_INTIMIDATE = "Intimidate"
SA_ACTION_NONE = "No SA"

# March sub-types for clarity in action dicts
MARCH_THREAT = "March (threat)"
MARCH_EXPAND = "March (expand)"

# Trigger thresholds — A8.7.1
G1_MIN_WARBANDS_FOR_TRIGGER = 6     # "at least six Germanic Warbands"
G1_MIN_ENEMY_PIECES = 4              # "separately at least four pieces"
G1B_MIN_ARIOVISTUS_WARBANDS = 12     # "at least 12 Germanic Warbands"


def _make_action(command, *, regions=None, sa=SA_ACTION_NONE, sa_regions=None,
                 details=None):
    """Build a standardized action result dict.

    Region collections are sorted into a deterministic order. Bots assemble
    them from sets, whose iteration order varies with Python hash
    randomization; the order is never semantically consumed (the executable
    plan lives in ``details``), so sorting here makes action dicts and their
    logs byte-reproducible for deterministic replay without affecting any
    decision. See CLAUDE.md "Determinism".
    """
    return {
        "command": command,
        "regions": sorted(regions, key=repr) if regions else [],
        "sa": sa,
        "sa_regions": sorted(sa_regions, key=repr) if sa_regions else [],
        "details": details or {},
    }


# ============================================================================
# HELPER: Germanic-specific board queries
# ============================================================================

def _ariovistus_region(state):
    """Find Ariovistus's region (or Successor), or None if not on map."""
    return find_leader(state, GERMANS)


def _has_ariovistus(state, region):
    """Is the named leader Ariovistus in this region?

    Per A1.4: Ariovistus is the German Leader; flip side is Successor.
    """
    leader = get_leader_in_region(state, region, GERMANS)
    return leader == ARIOVISTUS_LEADER


def _count_german_warbands_on_map(state):
    """Count total Germanic Warbands on map."""
    return count_on_map(state, GERMANS, WARBAND)


def _get_all_enemies():
    """Get enemy factions considered for G1 threat condition.

    Per A8.7.1: "where ANY enemy has an Ally, a Citadel, a Legion, or
    separately at least four pieces." Unlike Belgae §8.5.1, the Germans
    consider ALL enemies, including other Gauls — there is no
    "non-German enemies" carve-out.

    Returns:
        Tuple of enemy faction constants. Germans excluded (self).
    """
    return (ROMANS, ARVERNI, AEDUI, BELGAE)


def _has_german_threat(state, region):
    """Check if a region meets the G1 'Battle or March under Threat' condition.

    Per A8.7.1: "If the Germans have Ariovistus or a group of at least
    six Germanic Warbands in any Region where any enemy has an Ally, a
    Citadel, a Legion, or separately at least four pieces."

    Args:
        state: Game state dict.
        region: Region constant.

    Returns:
        True if the region has a G1 threat.
    """
    # Must have Ariovistus OR 6+ German Warbands in this region
    has_aristos = _has_ariovistus(state, region)
    german_wb = count_pieces(state, region, GERMANS, WARBAND)
    if not has_aristos and german_wb < G1_MIN_WARBANDS_FOR_TRIGGER:
        return False

    # Check ANY enemy for Ally, Citadel, Legion, or >=4 pieces — A8.7.1
    enemies = _get_all_enemies()
    for enemy in enemies:
        if count_pieces(state, region, enemy, ALLY) > 0:
            return True
        if count_pieces(state, region, enemy, CITADEL) > 0:
            return True
        if count_pieces(state, region, enemy, LEGION) > 0:
            return True
        # "separately at least four pieces" — A8.7.1
        if count_pieces(state, region, enemy) >= G1_MIN_ENEMY_PIECES:
            return True

    return False


def _get_threat_regions(state, scenario):
    """Get all regions meeting the G1 threat condition.

    Returns:
        Sorted list of region constants (deterministic).
    """
    playable = get_playable_regions(scenario, state.get("capabilities"))
    return sorted(r for r in playable if _has_german_threat(state, r))


def _estimate_battle_losses(state, region, enemy):
    """Estimate Losses inflicted and suffered for a German Battle.

    Per A8.7.1 / §3.3.4: presume "all Defender Loss rolls result in
    Defender removals (the best possible case for the Germanic Attack)".

    Returns:
        (losses_inflicted, losses_suffered) tuple of ints.
    """
    german_wb = count_pieces(state, region, GERMANS, WARBAND)
    has_aristos = _has_ariovistus(state, region)

    # Germanic Attack: 1/2 per Warband + 1 per Leader — §3.3.4
    attack_raw = german_wb * 0.5 + (1 if has_aristos else 0)
    # Enemy Fort/Citadel halves Attack Losses inflicted — §3.3.4
    enemy_fort = count_pieces(state, region, enemy, FORT)
    enemy_citadel = count_pieces(state, region, enemy, CITADEL)
    if enemy_fort > 0 or enemy_citadel > 0:
        attack_raw = attack_raw / 2
    losses_inflicted = int(attack_raw)

    # Counterattack Losses suffered by Germans — §3.3.4
    enemy_warbands = count_pieces(state, region, enemy, WARBAND)
    enemy_auxilia = count_pieces(state, region, enemy, AUXILIA)
    enemy_legions = count_pieces(state, region, enemy, LEGION)
    enemy_leader = get_leader_in_region(state, region, enemy)

    counter_raw = (enemy_legions * 1
                   + enemy_warbands * 0.5
                   + enemy_auxilia * 0.5
                   + (1 if enemy_leader else 0))

    # Germans have no Fort/Citadel — no halving on the German side.
    losses_suffered = int(counter_raw)
    return (losses_inflicted, losses_suffered)


def _can_battle_in_region(state, region, enemy):
    """Check if Germans can Battle a specific enemy in a region per A8.7.1.

    Conditions: Germans inflict MORE Losses than they suffer AND no Loss
    on Ariovistus, presuming all Defender Loss rolls remove pieces.

    Per A8.7.1: "only in Regions where they will inflict more Losses on
    the enemy than they will suffer, and no Loss on Ariovistus."

    Args:
        state: Game state dict.
        region: Region constant.
        enemy: Enemy faction constant.

    Returns:
        True if Germans can Battle this enemy here per A8.7.1 restrictions.
    """
    if enemy == GERMANS:
        return False  # never battle self

    german_wb = count_pieces(state, region, GERMANS, WARBAND)
    has_aristos = _has_ariovistus(state, region)
    if german_wb == 0 and not has_aristos:
        return False

    if count_pieces(state, region, enemy) == 0:
        return False

    losses_inflicted, losses_suffered = _estimate_battle_losses(
        state, region, enemy)

    # No Loss on Ariovistus — A8.7.1
    # Ariovistus would take a Loss only if all Warbands removed first
    if has_aristos and losses_suffered >= german_wb + 1:
        return False

    # Germans must inflict MORE Losses than they suffer — A8.7.1
    if losses_inflicted > losses_suffered:
        return True
    return False


def _enemy_at_victory(state, faction):
    """Check if a faction currently has a victory margin of 0 or better.

    Per A8.7.1 / §7.3: margin >= 0 means at or beyond victory threshold.
    """
    try:
        margin = calculate_victory_margin(state, faction)
    except Exception:
        return False
    return margin >= 0


def _romans_at_victory(state):
    """Per A8.7.1: 'Romans at victory (margin of 1 or better, 7.3)'."""
    try:
        margin = calculate_victory_margin(state, ROMANS)
    except Exception:
        return False
    return margin >= 1


def _gaul_at_victory(state, faction):
    """Per A8.7.1: 'Aedui or Belgae at victory'."""
    try:
        margin = calculate_victory_margin(state, faction)
    except Exception:
        return False
    return margin >= 1


def _is_dispersed_tribe(tribe_info):
    """Check if a tribe is Dispersed or Dispersed-Gathering."""
    status = tribe_info.get("status")
    return status in (MARKER_DISPERSED, MARKER_DISPERSED_GATHERING)


def _count_dispersed_tribes_in_region(state, region, scenario):
    """Count Dispersed (or Dispersed-Gathering) tribes in a region."""
    count = 0
    for tribe in get_tribes_in_region(region, scenario):
        if _is_dispersed_tribe(state["tribes"].get(tribe, {})):
            count += 1
    return count


def _count_allied_tribes_in_region(state, region, scenario, faction):
    """Count tribes Allied to a faction in a region."""
    count = 0
    for tribe in get_tribes_in_region(region, scenario):
        info = state["tribes"].get(tribe, {})
        if info.get("allied_faction") == faction:
            count += 1
    return count


def _is_in_or_adjacent_to_germania(region, scenario):
    """True if region is in Germania or adjacent to Germania (A8.7.5)."""
    if region in GERMANIA_REGIONS:
        return True
    for gr in GERMANIA_REGIONS:
        if is_adjacent(region, gr):
            return True
    return False


def _has_settlement(state, region):
    """True if a Germanic Settlement is in this region."""
    return count_pieces(state, region, GERMANS, SETTLEMENT) > 0


def _find_largest_german_warband_group_leaderless(state, scenario):
    """Find the region with the largest Germanic Warband group that does
    NOT have the Germanic Leader.

    Per A8.7.5 step 2: "the largest group of Germanic Warbands on the map
    that is not with the Germanic Leader".

    Returns:
        (region, count) or (None, 0).
    """
    playable = get_playable_regions(scenario, state.get("capabilities"))
    leader_region = _ariovistus_region(state)
    best_region = None
    best_count = 0
    for region in playable:
        if region == leader_region:
            continue
        wb = count_pieces(state, region, GERMANS, WARBAND)
        if wb > best_count:
            best_count = wb
            best_region = region
    return (best_region, best_count)


# ============================================================================
# G1 / G1b — Battle or March under Threat
# ============================================================================

def node_g1(state):
    """G1: Ariovistus or 6+ German Warbands where any enemy has an Ally,
    Citadel, Legion, or >=4 pieces?

    Per A8.7.1: "If the Germans have Ariovistus or a group of at least
    six Germanic Warbands in any Region where any enemy has an Ally, a
    Citadel, a Legion, or separately at least four pieces, the Germans
    may Battle."

    Returns:
        ("Yes", threat_regions) or ("No", []).
    """
    scenario = state["scenario"]
    threat_regions = _get_threat_regions(state, scenario)
    if threat_regions:
        return ("Yes", threat_regions)
    return ("No", [])


def node_g1b(state):
    """G1b: Enemy at 0+ victory margin AND Ariovistus's region has 12+
    German Warbands?

    Per A8.7.1: "if the condition did not apply but an enemy Faction
    currently has a victory margin of 0 or better (7.3) and Ariovistus
    has at least 12 Germanic Warbands in his Region."

    Returns:
        "Yes" (proceed to March-threat) or "No" (proceed to G2).
    """
    aristos_region = _ariovistus_region(state)
    if aristos_region is None:
        return "No"

    aristos_wb = count_pieces(state, aristos_region, GERMANS, WARBAND)
    if aristos_wb < G1B_MIN_ARIOVISTUS_WARBANDS:
        return "No"

    # Check any victory-tracking enemy at margin >= 0 — A8.7.1
    scenario = state["scenario"]
    for enemy in _get_all_enemies():
        # Arverni do not track victory in Ariovistus (A7.0); skip.
        if enemy == ARVERNI and scenario in ARIOVISTUS_SCENARIOS:
            continue
        if _enemy_at_victory(state, enemy):
            return "Yes"
    return "No"


# ============================================================================
# G2 — Pass
# ============================================================================

def node_g2(state):
    """G2: Germans 1st on upcoming card but not current, and roll 1-4?

    Per A8.7.2: "If the Germanic Tribes symbol is first of the four
    symbols on the next upcoming card but not on the currently played
    card (regardless of Faction Eligibility cylinders), roll a die: on
    a roll of 1-4, they Pass. NOTE: They do not Pass if 1st on both
    cards or if WINTER is showing."

    Returns:
        "Yes" (Pass) or "No" (continue to G3).
    """
    current_order = state.get("current_card_faction_order", [])
    next_order = state.get("next_card_faction_order", [])

    # Winter showing means no Pass — A8.7.2 NOTE
    if state.get("frost", False):
        return "No"

    germans_1st_current = (len(current_order) > 0
                           and current_order[0] == GERMANS)
    germans_1st_next = (len(next_order) > 0
                        and next_order[0] == GERMANS)

    # Pass only if 1st on next but NOT 1st on current — A8.7.2
    if germans_1st_next and not germans_1st_current:
        die_result = roll_die(state)
        if die_result <= 4:
            return "Yes"
    return "No"


# ============================================================================
# G3 / G3b — Event decisions
# ============================================================================

def node_g3(state):
    """G3: Germans by Sequence of Play may use Event?

    Per A8.7.2: NP plays the Event only if 1st Eligible, or the 1st
    Eligible used a Special Ability.

    Returns:
        "Yes" or "No".
    """
    return "Yes" if state.get("can_play_event", False) else "No"


def node_g3b(state):
    """G3b: Event Ineffective, would add Capability in final year, or
    'No Germans'?

    Per A8.7.2: Decline if Ineffective, final-year Capability, or
    "No Germans". Also check the Non-player Germans Event Instructions
    foldout (A8.2.1) — if the instruction handler returns NO_EVENT, treat
    as decline. Some specific-instruction entries also include conditional
    "treat as 'No Germans'" cases (Romans Non-Player, Belgae Non-Player,
    final-Winter checks).

    Returns:
        "Yes" (decline, go to G4) or "No" (proceed to G_EVENT).
    """
    card_id = state.get("current_card_id")
    if card_id is None:
        return "Yes"

    scenario = state["scenario"]
    instr = get_event_instruction(card_id, GERMANS, scenario)
    if instr is None:
        # No instruction table entry — treat as decline for safety.
        return "Yes"

    # "No Germans" cards — A8.2.1, A8.7.2
    if instr.action == NO_EVENT:
        return "Yes"

    # Capabilities in the game's final year — §8.1.1, A8.7.2
    from fs_bot.rules_consts import (
        CAPABILITY_CARDS, CAPABILITY_CARDS_ARIOVISTUS,
    )
    is_cap = (card_id in CAPABILITY_CARDS
              or card_id in CAPABILITY_CARDS_ARIOVISTUS)
    if is_cap and state.get("final_year", False):
        return "Yes"

    # Specific-instruction conditional decline cases — per-card text.
    if instr.action == SPECIFIC_INSTRUCTION:
        if _instruction_says_no_germans(state, card_id, instr):
            return "Yes"

    return "No"


def _instruction_says_no_germans(state, card_id, instr):
    """Evaluate per-card 'treat as No Germans' conditions.

    Per germans_bot_event_instructions_ariovistus.txt:
    - Balearic Slingers / Clodius Pulcher / Legio X / Pompey:
      if Romans Non-Player, treat as 'No Germans'.
    - Kinship: if Belgae Non-Player, treat as 'No Germans'.
    - Winter Uprising!: if next Winter is the last, treat as 'No Germans'.
    """
    non_players = state.get("non_player_factions", set())
    text = (instr.instruction or "").lower()

    if "if romans are a non-player" in text:
        return ROMANS in non_players
    if "if belgae non-player" in text:
        return BELGAE in non_players
    if "if next winter is the last" in text:
        return state.get("final_year", False)
    return False


# ============================================================================
# G4 — Raid trigger
# ============================================================================

def node_g4(state):
    """G4: Germans have 0-3 Resources and roll 1-4?

    Per A8.7.3: "Check the Germans' Resources — if fewer than four
    Resources, roll a die and on a roll of 1-4, they attempt to Raid."

    Returns:
        "Yes" (attempt Raid) or "No" (proceed to G5).
    """
    resources = state.get("resources", {}).get(GERMANS, 0)
    if resources >= 4:
        return "No"
    die_result = roll_die(state)
    if die_result <= 4:
        return "Yes"
    return "No"


# ============================================================================
# G5 — Rally / Settle qualification
# ============================================================================

def node_g5(state):
    """G5: Rally (+Settle) would add German Ally, Settlement, 4+ German
    Warbands total, or German Control?

    Per A8.7.4: "they Rally and Settle if doing either would place a
    Germanic Ally, a Settlement, or at least four Germanic Warbands total,
    or if it would add to Germanic Control."

    Returns:
        "Yes" (Rally+Settle) or "No" (March-expand).
    """
    scenario = state["scenario"]
    if _estimate_rally_settle_would_qualify(state, scenario):
        return "Yes"
    return "No"


def _estimate_rally_settle_would_qualify(state, scenario):
    """Check the G5 qualification condition per A8.7.4.

    Returns True if either Rally or Settle (taken together) would place:
    - a Germanic Ally,
    - a Settlement,
    - 4+ Germanic Warbands total, OR
    - add to Germanic Control.
    """
    resources = state.get("resources", {}).get(GERMANS, 0)
    playable = get_playable_regions(scenario, state.get("capabilities"))

    avail_settlements = get_available(state, GERMANS, SETTLEMENT)
    avail_allies = get_available(state, GERMANS, ALLY)
    avail_warbands = get_available(state, GERMANS, WARBAND)

    # Settlement: at least one validly placeable region — A4.6.1
    if avail_settlements > 0 and _any_settle_destination(state, scenario):
        return True

    # Ally: at any tribe where Germans have base AND tribe unallied
    if avail_allies > 0:
        for region in playable:
            if (count_pieces(state, region, GERMANS) == 0
                    and not is_controlled_by(state, region, GERMANS)
                    and region not in GERMANIA_REGIONS):
                continue
            for tribe in get_tribes_in_region(region, scenario):
                tribe_info = state["tribes"].get(tribe, {})
                if tribe_info.get("allied_faction") is not None:
                    continue
                # Ally placement cost = same as Warband per A3.4.1
                cost = _german_rally_cost(state, region)
                if resources >= cost:
                    return True

    # Warbands: count how many we could afford+place
    if avail_warbands > 0:
        wb_placeable = _count_placeable_warbands(
            state, scenario, resources, avail_warbands)
        if wb_placeable >= 4:
            return True

        # Or: any Warband placement that would add Germanic Control?
        if wb_placeable > 0:
            for region in playable:
                if is_controlled_by(state, region, GERMANS):
                    continue
                if _rally_would_tip_control(state, region):
                    return True

    return False


def _any_settle_destination(state, scenario):
    """True if at least one region is a valid Settle destination per A4.6.1."""
    aristos_region = _ariovistus_region(state)
    if aristos_region is None:
        return False
    leader_name = get_leader_in_region(state, aristos_region, GERMANS)
    is_named_leader = leader_name == ARIOVISTUS_LEADER

    playable = get_playable_regions(scenario, state.get("capabilities"))
    for region in playable:
        if region in GERMANIA_REGIONS:
            continue
        if not is_controlled_by(state, region, GERMANS):
            continue
        if is_named_leader:
            if region != aristos_region and not is_adjacent(
                    region, aristos_region):
                continue
        else:
            if region != aristos_region:
                continue
        adj_to_germania = any(is_adjacent(region, gr)
                              for gr in GERMANIA_REGIONS)
        adj_to_settlement = any(
            _has_settlement(state, adj)
            for adj in get_adjacent(region)
        )
        if not adj_to_germania and not adj_to_settlement:
            continue
        if _has_settlement(state, region):
            continue
        return True
    return False


def _german_rally_cost(state, region):
    """Resource cost to Rally a piece in a region per A3.4.1.

    Returns:
        0 in Germania, 1 at Settlement, 2 elsewhere.
    """
    if region in GERMANIA_REGIONS:
        return GERMAN_RALLY_COST_IN_GERMANIA
    if _has_settlement(state, region):
        return GERMAN_RALLY_COST_AT_SETTLEMENT
    return GERMAN_RALLY_COST_OUTSIDE_GERMANIA_NO_SETTLEMENT


def _count_placeable_warbands(state, scenario, resources, avail_warbands):
    """Estimate how many Warbands could be Rallied with current Resources.

    Per A8.7.4 starting-with-Settlements-and-Germania to reduce costs.
    """
    playable = get_playable_regions(scenario, state.get("capabilities"))
    remaining_res = resources
    remaining_wb = avail_warbands
    placed = 0

    def _region_sort_key(r):
        if r in GERMANIA_REGIONS:
            return 0
        if _has_settlement(state, r):
            return 1
        return 2

    candidates = []
    for region in playable:
        # Rally needs a base: Control, Ally, Settlement, or Home — §3.3.1, A3.4.1
        has_base = False
        if is_controlled_by(state, region, GERMANS):
            has_base = True
        if not has_base:
            for tribe in get_tribes_in_region(region, scenario):
                if state["tribes"].get(tribe, {}).get(
                        "allied_faction") == GERMANS:
                    has_base = True
                    break
        if not has_base and _has_settlement(state, region):
            has_base = True
        if region in GERMANIA_REGIONS:
            has_base = True
        if has_base:
            candidates.append(region)

    candidates.sort(key=_region_sort_key)

    for region in candidates:
        cost = _german_rally_cost(state, region)
        while remaining_wb > 0 and remaining_res >= cost:
            placed += 1
            remaining_wb -= 1
            remaining_res -= cost
            if cost == 0:
                # Avoid infinite loop on free Germania placement; cap by avail
                continue

    return placed


def _rally_would_tip_control(state, region):
    """Conservative check: would adding 1+ German Warband(s) flip Control?
    """
    german_forces = count_pieces(state, region, GERMANS)
    non_german_forces = sum(
        count_pieces(state, region, f)
        for f in (ROMANS, ARVERNI, AEDUI, BELGAE)
    )
    return german_forces + 1 > non_german_forces


# ============================================================================
# G_EVENT — Execute Event
# ============================================================================

def node_g_event(state):
    """G_EVENT: Execute Event.

    Per A8.7.2 / A8.2.2: Use shaded Event text. See Instructions (A8.2.1)
    if gray laurels or carnyx on the card's Germans OR Arverni symbol.

    Returns:
        Action dict for Event execution.
    """
    card_id = state.get("current_card_id")
    scenario = state["scenario"]
    preference = get_dual_use_preference(GERMANS, scenario)
    instr = get_event_instruction(card_id, GERMANS, scenario)

    return _make_action(
        ACTION_EVENT,
        details={
            "card_id": card_id,
            "text_preference": preference,
            "instruction": instr.instruction if instr else None,
        },
    )


# ============================================================================
# G_BATTLE — Battle process
# ============================================================================

def node_g_battle(state):
    """G_BATTLE: Battle process.

    Per A8.7.1:
    1. Battle only where Germans inflict more Losses than they suffer AND
       no Loss on Ariovistus, presuming all Defender Loss rolls remove
       pieces.
    2. If Ariovistus meets the trigger BUT will not Battle, March instead.
    3. Check Ambush; if no Ambush, Intimidate before Battle.
    4. First Ariovistus fights an enemy with fewer mobile pieces than the
       Germans. Then other Battles.
    5. Stop when out of candidate Regions or Resources.

    Returns:
        Action dict for Battle, or redirects to March-threat.
    """
    scenario = state["scenario"]
    threat_regions = _get_threat_regions(state, scenario)
    if not threat_regions:
        return node_g_march_threat(state)

    # Step 1 — Check Ariovistus refuses-to-Battle redirect — A8.7.1
    aristos_region = _ariovistus_region(state)
    if aristos_region and aristos_region in threat_regions:
        can_ariovistus_battle = False
        for enemy in _get_all_enemies():
            if count_pieces(state, aristos_region, enemy) == 0:
                continue
            if _can_battle_in_region(state, aristos_region, enemy):
                can_ariovistus_battle = True
                break
        if not can_ariovistus_battle:
            return node_g_march_threat(state)

    battle_plan = []
    resources = state.get("resources", {}).get(GERMANS, 0)

    # Step 3a — Ariovistus first vs enemy with fewer mobile than Germans
    if aristos_region and aristos_region in threat_regions:
        german_mobile = count_mobile_pieces(state, aristos_region, GERMANS)
        candidates = []
        for enemy in _get_all_enemies():
            if count_pieces(state, aristos_region, enemy) == 0:
                continue
            enemy_mobile = count_mobile_pieces(state, aristos_region, enemy)
            if enemy_mobile >= german_mobile:
                continue
            if _can_battle_in_region(state, aristos_region, enemy):
                candidates.append(enemy)
        if candidates:
            # §8.3.4 random tie-break among equally-valid first-tier enemies
            target = (random_select(state, candidates)
                      if len(candidates) > 1 else candidates[0])
            battle_plan.append({
                "region": aristos_region,
                "target": target,
                "is_trigger": True,
            })

    # Step 3 — Battle other trigger regions where Germans can
    for region in threat_regions:
        if any(bp["region"] == region for bp in battle_plan):
            continue
        candidates = []
        for enemy in _get_all_enemies():
            if count_pieces(state, region, enemy) == 0:
                continue
            if _can_battle_in_region(state, region, enemy):
                candidates.append(enemy)
        if candidates:
            target = (random_select(state, candidates)
                      if len(candidates) > 1 else candidates[0])
            battle_plan.append({
                "region": region,
                "target": target,
                "is_trigger": True,
            })

    # Step 4 — Battle other enemies where they can (no trigger required)
    # "until they run out of candidate Regions or of Resources" — A8.7.1
    playable = get_playable_regions(scenario, state.get("capabilities"))
    for region in playable:
        if any(bp["region"] == region for bp in battle_plan):
            continue
        if count_pieces(state, region, GERMANS) == 0:
            continue
        candidates = []
        for enemy in _get_all_enemies():
            if count_pieces(state, region, enemy) == 0:
                continue
            if _can_battle_in_region(state, region, enemy):
                candidates.append(enemy)
        if candidates:
            target = (random_select(state, candidates)
                      if len(candidates) > 1 else candidates[0])
            battle_plan.append({
                "region": region,
                "target": target,
                "is_trigger": False,
            })

    # Cap by Resources — Gallic Battle costs 1 per region — A3.4 (Ariovistus)
    max_battles = max(0, resources // max(1, GALLIC_BATTLE_COST))
    if max_battles < len(battle_plan):
        battle_plan = battle_plan[:max_battles]

    if not battle_plan:
        return node_g_march_threat(state)

    # SA: Ambush or Intimidate-before-Battle — A8.7.1
    sa, sa_regions, sa_details = _determine_battle_sa(state, battle_plan)

    return _make_action(
        ACTION_BATTLE,
        regions=[bp["region"] for bp in battle_plan],
        sa=sa,
        sa_regions=sa_regions,
        details={"battle_plan": battle_plan, "sa_details": sa_details},
    )


def _determine_battle_sa(state, battle_plan):
    """Per A8.7.1: check Ambush first; if no Ambush, Intimidate before Battle.

    Returns:
        (sa_action, sa_regions, sa_details).
    """
    ambush_regions = _check_ambush(state, battle_plan)
    if ambush_regions:
        return (SA_ACTION_AMBUSH, ambush_regions, {})

    intim_regions = _check_intimidate_before_battle(state, battle_plan)
    if intim_regions:
        return (SA_ACTION_INTIMIDATE,
                sorted({r["region"] for r in intim_regions}),
                {"intimidate_plan": intim_regions})

    return (SA_ACTION_NONE, [], {})


# ============================================================================
# G_MARCH_THREAT — March (from threat)
# ============================================================================

def node_g_march_threat(state):
    """G_MARCH_THREAT: March all mobile Germanic Forces out of each Region
    that meets the trigger or has the Germanic Leader.

    Per A8.7.1:
    1. Origins: each trigger region AND the Germanic Leader's region.
       Keep each origin's group together. Leader's group marches first.
    2. Destinations: at least 1, up to count of origins, NOT any origin.
       Priorities:
         (a) If Romans at victory, prefer regions with most Dispersed Tribes
             reachable.
         (b) Within (a), if Aedui or Belgae at victory, prefer regions with
             most Allied Tribes of those Gauls.
         (c) Within (a)(b), prefer regions adding the most Germanic Control
             (i.e. no current Germanic Control).
       Random tie-break — §8.3.4.

    After the March, the bot decides Intimidate-or-Settle.

    Returns:
        Action dict for March.
    """
    scenario = state["scenario"]
    playable = get_playable_regions(scenario, state.get("capabilities"))
    threat_regions = _get_threat_regions(state, scenario)
    aristos_region = _ariovistus_region(state)

    # Origins — A8.7.1
    origins = set(threat_regions)
    if aristos_region:
        origins.add(aristos_region)

    origin_list = sorted(origins)
    if aristos_region and aristos_region in origin_list:
        origin_list.remove(aristos_region)
        origin_list.insert(0, aristos_region)

    excluded = set(origin_list)
    max_dests = len(origin_list)

    romans_at_vic = _romans_at_victory(state)
    aedui_at_vic = _gaul_at_victory(state, AEDUI)
    belgae_at_vic = _gaul_at_victory(state, BELGAE)

    candidates = []
    for region in playable:
        if region in excluded:
            continue
        dispersed = _count_dispersed_tribes_in_region(state, region, scenario)
        gaul_allies = 0
        if aedui_at_vic:
            gaul_allies += _count_allied_tribes_in_region(
                state, region, scenario, AEDUI)
        if belgae_at_vic:
            gaul_allies += _count_allied_tribes_in_region(
                state, region, scenario, BELGAE)
        adds_control = 0 if is_controlled_by(state, region, GERMANS) else 1
        key_a = dispersed if romans_at_vic else 0
        key_b = gaul_allies if (aedui_at_vic or belgae_at_vic) else 0
        candidates.append({
            "region": region,
            "key_a": key_a,
            "key_b": key_b,
            "key_c": adds_control,
        })

    candidates.sort(key=lambda c: (-c["key_a"], -c["key_b"], -c["key_c"]))

    destinations = []
    remaining = list(candidates)
    while remaining and len(destinations) < max_dests:
        head = remaining[0]
        equal = [c for c in remaining
                 if (c["key_a"], c["key_b"], c["key_c"])
                 == (head["key_a"], head["key_b"], head["key_c"])]
        chosen = (random_select(state, equal)
                  if len(equal) > 1 else equal[0])
        destinations.append(chosen["region"])
        remaining = [c for c in remaining
                     if c["region"] != chosen["region"]]

    if not destinations or not origins:
        return _make_action(ACTION_PASS)

    march_plan = {
        "origins": origin_list,
        "destinations": destinations,
        "type": MARCH_THREAT,
    }

    sa, sa_regions, sa_details = _determine_intimidate_or_settle_after_march(
        state, march_plan)

    return _make_action(
        ACTION_MARCH,
        regions=destinations,
        sa=sa,
        sa_regions=sa_regions,
        details={"march_plan": march_plan, **sa_details},
    )


# ============================================================================
# G_RAID — Raid process
# ============================================================================

def node_g_raid(state):
    """G_RAID: Raid if would gain 2+ Resources total.

    Per A8.7.3: "If Raiding per below would gain the Germans at least two
    Resources total, they Raid wherever they can, in the following order:
    from Romans or Aedui where able, then from Belgae, then (in other
    Regions) from no Faction."

    After Raiding: free Intimidate in Ariovistus's region, then Intimidate
    further per A8.7.1.

    Returns:
        Action dict for Raid, or Pass.
    """
    scenario = state["scenario"]
    enough, raid_plan = _would_raid_gain_enough(state, scenario)
    if not enough:
        return _make_action(ACTION_PASS)

    sa, sa_regions, sa_details = _determine_intimidate_after_raid(
        state, raid_plan)

    return _make_action(
        ACTION_RAID,
        regions=sorted({r["region"] for r in raid_plan}),
        sa=sa,
        sa_regions=sa_regions,
        details={"raid_plan": raid_plan, **sa_details},
    )


def _is_devastated(state, region):
    """Check if a region is Devastated (per state markers or space flag).

    Robust to both marker representations used in the codebase: a dict
    ({MARKER_DEVASTATED: True}) and a set ({MARKER_DEVASTATED}). Uses the
    correct MARKER_DEVASTATED constant (a prior version checked the wrong
    lowercase key and crashed on set-form markers).
    """
    m = state.get("markers", {}).get(region) or {}
    if MARKER_DEVASTATED in m:  # key membership (dict) or membership (set)
        return True
    return bool(state["spaces"].get(region, {}).get("devastated", False))


def _would_raid_gain_enough(state, scenario):
    """Check if Raiding gains 2+ Resources total per A8.7.3.

    Per §3.3.3 / A8.7.3: each Raid region flips 1-2 Hidden Warbands →
    1 Resource each (steal from priority targets or non-Devastated gain).

    Per A8.7.3 priority:
      (1) Romans or Aedui where able,
      (2) Belgae,
      (3) No-Faction in other (non-Devastated) regions.

    Returns:
        (bool enough, list of raid plan dicts).
    """
    playable = get_playable_regions(scenario, state.get("capabilities"))
    total_gain = 0
    plan = []

    for region in playable:
        hidden_wb = count_pieces_by_state(
            state, region, GERMANS, WARBAND, HIDDEN)
        if hidden_wb == 0:
            continue

        flips = min(2, hidden_wb)
        is_devastated = _is_devastated(state, region)

        # Tier 1: Romans then Aedui — A8.7.3
        steal_targets = []
        for target in (ROMANS, AEDUI):
            if count_pieces(state, region, target) == 0:
                continue
            if (count_pieces(state, region, target, CITADEL) > 0
                    or count_pieces(state, region, target, FORT) > 0):
                continue
            steal_targets.append(target)
        # Tier 2: Belgae — A8.7.3
        if (count_pieces(state, region, BELGAE) > 0
                and count_pieces(state, region, BELGAE, CITADEL) == 0):
            steal_targets.append(BELGAE)

        region_entries = []
        remaining = flips
        for target in steal_targets:
            if remaining <= 0:
                break
            region_entries.append({"region": region, "target": target})
            total_gain += 1
            remaining -= 1

        # Tier 3: in other (non-Devastated) regions, no faction — A8.7.3
        while remaining > 0:
            if not is_devastated:
                region_entries.append({"region": region, "target": None})
                total_gain += 1
            remaining -= 1

        plan.extend(region_entries)

    return (total_gain >= 2, plan)


# ============================================================================
# G_RALLY — Rally process (+Settle)
# ============================================================================

def node_g_rally(state):
    """G_RALLY: Rally process per A8.7.4.

    Per A8.7.4:
    - Before Rallying, Settle to place any Settlement(s) possible.
      (Settle first if any can be placed; otherwise after Rallying.)
    - Then place all Germanic Allies possible.
    - Finally place all Germanic Warbands possible, starting with any
      Settlement Regions and/or Germania (to reduce Resource costs).
    - If no Settlement can be placed in the above cases, no SA — A8.7.1.

    Returns:
        Action dict for Rally with Settle (SA).
    """
    scenario = state["scenario"]
    playable = get_playable_regions(scenario, state.get("capabilities"))
    resources = state.get("resources", {}).get(GERMANS, 0)

    rally_plan = {
        "settlements_before": [],
        "allies": [],
        "warbands": [],
        "settlements_after": [],
    }

    # Phase A: Settle BEFORE Rally if any can be placed — A8.7.4
    settle_dests = _get_settle_destinations(state, scenario)
    if settle_dests:
        avail_settle = get_available(state, GERMANS, SETTLEMENT)
        for region in settle_dests:
            if avail_settle <= 0:
                break
            cost = SETTLE_COST
            if _is_devastated(state, region):
                cost *= 2
            if resources < cost:
                break
            rally_plan["settlements_before"].append({
                "region": region, "cost": cost,
            })
            resources -= cost
            avail_settle -= 1
        sa = (SA_ACTION_SETTLE
              if rally_plan["settlements_before"] else SA_ACTION_NONE)
        sa_regions = [s["region"] for s in rally_plan["settlements_before"]]
    else:
        sa = SA_ACTION_NONE
        sa_regions = []

    # Phase B: Place all Allies possible — A8.7.4
    avail_allies = get_available(state, GERMANS, ALLY)
    for region in playable:
        if avail_allies <= 0:
            break
        if (count_pieces(state, region, GERMANS) == 0
                and not is_controlled_by(state, region, GERMANS)
                and region not in GERMANIA_REGIONS):
            continue
        for tribe in get_tribes_in_region(region, scenario):
            if avail_allies <= 0:
                break
            tribe_info = state["tribes"].get(tribe, {})
            if tribe_info.get("allied_faction") is not None:
                continue
            cost = _german_rally_cost(state, region)
            if resources < cost:
                continue
            rally_plan["allies"].append({
                "region": region, "tribe": tribe, "cost": cost,
            })
            resources -= cost
            avail_allies -= 1

    # Phase C: Place all Warbands possible, cheapest first — A8.7.4
    def _wb_sort_key(r):
        if r in GERMANIA_REGIONS:
            return 0
        if _has_settlement(state, r):
            return 1
        return 2

    avail_warbands = get_available(state, GERMANS, WARBAND)
    candidates = []
    for region in playable:
        has_base = (
            is_controlled_by(state, region, GERMANS)
            or _has_settlement(state, region)
            or region in GERMANIA_REGIONS
        )
        if not has_base:
            for tribe in get_tribes_in_region(region, scenario):
                if state["tribes"].get(tribe, {}).get(
                        "allied_faction") == GERMANS:
                    has_base = True
                    break
        if has_base:
            candidates.append(region)
    candidates.sort(key=_wb_sort_key)

    for region in candidates:
        if avail_warbands <= 0:
            break
        cost = _german_rally_cost(state, region)
        placements_here = 0
        while avail_warbands > 0 and resources >= cost:
            rally_plan["warbands"].append({"region": region, "cost": cost})
            resources -= cost
            avail_warbands -= 1
            placements_here += 1
            if cost == 0 and placements_here >= avail_warbands + 1:
                break  # paranoia
        # If cost == 0 we keep placing in this region until out of warbands;
        # otherwise move to next candidate.
        if cost == 0:
            continue

    # Phase D: Settle AFTER Rally only if not done before — A8.7.4
    if not rally_plan["settlements_before"]:
        if settle_dests:
            avail = (get_available(state, GERMANS, SETTLEMENT)
                     - len(rally_plan["settlements_after"]))
            for region in settle_dests:
                if avail <= 0:
                    break
                cost = SETTLE_COST
                if _is_devastated(state, region):
                    cost *= 2
                if resources < cost:
                    break
                rally_plan["settlements_after"].append({
                    "region": region, "cost": cost,
                })
                resources -= cost
                avail -= 1
            if rally_plan["settlements_after"]:
                sa = SA_ACTION_SETTLE
                sa_regions = [s["region"]
                              for s in rally_plan["settlements_after"]]

    all_regions = list(
        {s["region"] for s in rally_plan["settlements_before"]}
        | {a["region"] for a in rally_plan["allies"]}
        | {w["region"] for w in rally_plan["warbands"]}
        | {s["region"] for s in rally_plan["settlements_after"]}
    )

    # Per A8.7.1: "unable to place any Settlements in the above cases ->
    # no SA". Set SA accordingly.
    if (not rally_plan["settlements_before"]
            and not rally_plan["settlements_after"]):
        sa = SA_ACTION_NONE
        sa_regions = []

    return _make_action(
        ACTION_RALLY,
        regions=all_regions,
        sa=sa,
        sa_regions=sa_regions,
        details={"rally_plan": rally_plan},
    )


def _get_settle_destinations(state, scenario):
    """Get all valid Settle destinations per A4.6.1, in priority order.

    Adjacency-to-Germania first; then those adjacent only to existing
    Settlements.
    """
    aristos_region = _ariovistus_region(state)
    if aristos_region is None:
        return []
    leader_name = get_leader_in_region(state, aristos_region, GERMANS)
    is_named_leader = leader_name == ARIOVISTUS_LEADER

    playable = get_playable_regions(scenario, state.get("capabilities"))
    valid = []
    for region in playable:
        if region in GERMANIA_REGIONS:
            continue
        if not is_controlled_by(state, region, GERMANS):
            continue
        if is_named_leader:
            if region != aristos_region and not is_adjacent(
                    region, aristos_region):
                continue
        else:
            if region != aristos_region:
                continue
        adj_to_germania = any(is_adjacent(region, gr)
                              for gr in GERMANIA_REGIONS)
        adj_to_settlement = any(
            _has_settlement(state, adj)
            for adj in get_adjacent(region)
        )
        if not adj_to_germania and not adj_to_settlement:
            continue
        if _has_settlement(state, region):
            continue
        valid.append((0 if adj_to_germania else 1, region))
    valid.sort()
    return [r for _, r in valid]


# ============================================================================
# G_MARCH_EXPAND — March (to expand or mass)
# ============================================================================

def node_g_march_expand(state):
    """G_MARCH_EXPAND: March into up to 3 Regions per A8.7.5.

    Step 1: March Warbands to add German Control to up to 2 Regions —
            Regions that are in or adjacent to Germania, if possible.
    Step 2: March into 1 additional Region as needed to move the largest
            group of Germanic Warbands not with the Leader toward the
            Leader, OR move the Leader (if in and adjacent only to
            German-Control regions) toward a non-German-Control region.
            Random tie-break — §8.3.4.

    Constraints:
    - Move with Leader and most Warbands able.
    - Leave 1 Warband per origin AND enough to keep German Control.
    - Keep groups together.

    Returns:
        Action dict for March, or redirects to Rally then Raid as fallback.
    """
    scenario = state["scenario"]
    playable = get_playable_regions(scenario, state.get("capabilities"))
    resources = state.get("resources", {}).get(GERMANS, 0)

    # IF NONE (or Frost): Rally per A8.7.4 instead — A8.7.5
    if resources <= 0 or is_frost_active(state):
        return node_g_rally(state)

    march_plan = {
        "control_destinations": [],
        "leader_or_group_destination": None,
        "origins": [],
        "type": MARCH_EXPAND,
    }

    candidates = []
    for region in playable:
        if is_controlled_by(state, region, GERMANS):
            continue
        german_forces = count_pieces(state, region, GERMANS)
        non_german_forces = sum(
            count_pieces(state, region, f)
            for f in (ROMANS, ARVERNI, AEDUI, BELGAE)
        )
        wb_needed = max(0, non_german_forces - german_forces + 1)
        if wb_needed == 0:
            wb_needed = 1

        origin_supply = []
        for origin in playable:
            if origin == region:
                continue
            if region not in get_adjacent(origin, scenario):
                continue
            origin_wb = count_pieces(state, origin, GERMANS, WARBAND)
            keep = 1
            if is_controlled_by(state, origin, GERMANS):
                other_factions = sum(
                    count_pieces(state, origin, f)
                    for f in (ROMANS, ARVERNI, AEDUI, BELGAE)
                )
                germans_remaining_non_wb = (
                    count_pieces(state, origin, GERMANS) - origin_wb)
                wb_keep_for_control = max(
                    0, other_factions - germans_remaining_non_wb + 1)
                keep = max(keep, wb_keep_for_control)
            available = max(0, origin_wb - keep)
            if available > 0:
                origin_supply.append((origin, available))

        total = sum(s[1] for s in origin_supply)
        if total >= wb_needed:
            in_or_adj = _is_in_or_adjacent_to_germania(region, scenario)
            candidates.append({
                "region": region,
                "wb_needed": wb_needed,
                "origin_supply": origin_supply,
                "in_or_adj_germania": in_or_adj,
            })

    candidates.sort(
        key=lambda c: (0 if c["in_or_adj_germania"] else 1, c["wb_needed"]))

    for cand in candidates:
        if len(march_plan["control_destinations"]) >= 2:
            break
        march_plan["control_destinations"].append(cand["region"])
        for origin, _ in cand["origin_supply"]:
            if origin not in march_plan["origins"]:
                march_plan["origins"].append(origin)

    # Step 2: One more region to massify — A8.7.5
    leader_region = _ariovistus_region(state)
    if leader_region:
        biggest_region, biggest_count = (
            _find_largest_german_warband_group_leaderless(state, scenario))
        option_a = None
        if biggest_region and biggest_count > 0:
            adj = get_adjacent(biggest_region, scenario)
            if leader_region in adj:
                option_a = leader_region
            else:
                forwards = [r for r in adj
                            if r not in march_plan["control_destinations"]
                            and r not in march_plan["origins"]]
                if forwards:
                    option_a = random_select(state, sorted(forwards))

        option_b = None
        leader_adj = get_adjacent(leader_region, scenario)
        all_german_control = (
            is_controlled_by(state, leader_region, GERMANS)
            and all(is_controlled_by(state, a, GERMANS)
                    for a in leader_adj if a in playable)
        )
        if all_german_control:
            non_control_adj = [
                a for a in leader_adj
                if a in playable
                and not is_controlled_by(state, a, GERMANS)
            ]
            if non_control_adj:
                option_b = random_select(state, sorted(non_control_adj))

        options = [o for o in (option_a, option_b) if o is not None]
        if options and len(march_plan["control_destinations"]) < 3:
            choice = (random_select(state, options)
                      if len(options) > 1 else options[0])
            march_plan["leader_or_group_destination"] = choice

    has_any_march = (march_plan["control_destinations"]
                     or march_plan["leader_or_group_destination"] is not None)
    if not has_any_march:
        return node_g_rally(state)

    sa, sa_regions, sa_details = _determine_intimidate_or_settle_after_march(
        state, march_plan)

    dest_list = list(march_plan["control_destinations"])
    if march_plan["leader_or_group_destination"]:
        dest_list.append(march_plan["leader_or_group_destination"])

    return _make_action(
        ACTION_MARCH,
        regions=dest_list,
        sa=sa,
        sa_regions=sa_regions,
        details={"march_plan": march_plan, **sa_details},
    )


# ============================================================================
# SA: G_AMBUSH
# ============================================================================

def _check_ambush(state, battle_plan):
    """G_AMBUSH: Determine Ambush regions per A8.7.1.

    Per A8.7.1:
    1. In the 1st Battle, only if Retreat could lower removals AND/OR
       Counterattack could inflict >=1 Loss on Germans.
       NOTE: A defending Legion or Leader satisfies the 2nd requirement.
    2. If Ambushed in 1st Battle, also Ambush in each other Battle possible.

    Ambush eligibility ("can Ambush", A8.7.1) defers to the Germanic Ambush
    Special-Ability rules:
    - A4.6.3 makes Germanic Ambush work "like Arverni Ambush (4.3.3) but
      uses Germanic... Ariovistus instead of Vercingetorix" — so §4.3.3's
      two conjunctive conditions apply with Ariovistus as the named Leader:
        (a) the Region begins with more Hidden Germanic pieces than Hidden
            Defenders, AND
        (b) the Region is within 1 of Ariovistus or has his Successor.
    - A4.1.2 (Ariovistus) independently confirms (b): German Special
      Abilities "may select only Regions within a distance of 1 Region of
      that Faction's named Leader... or (for Germans) the same Region that
      has its Successor Leader".
    Both conditions are enforced by validate_ambush_region() — the same
    check the SA execution layer applies — so the bot never proposes an
    Ambush it could not legally perform (matching the Belgae/Aedui bots).

    Returns:
        List of Ambush regions, or empty.
    """
    from fs_bot.commands.sa_ambush import validate_ambush_region

    if not battle_plan:
        return []

    first = battle_plan[0]
    region = first["region"]
    enemy = first["target"]

    # A4.6.3 -> §4.3.3 (+ A4.1.2) eligibility for the 1st Battle:
    # more Hidden Germans than Hidden Defenders AND within 1 of Ariovistus.
    eligible, _ = validate_ambush_region(state, region, GERMANS, enemy)
    if not eligible:
        return []

    should_ambush_first = False
    losses_inflicted, _ = _estimate_battle_losses(state, region, enemy)

    enemy_mobile = count_mobile_pieces(state, region, enemy)
    if enemy_mobile > 0 and losses_inflicted > 0:
        should_ambush_first = True

    if count_pieces(state, region, enemy, LEGION) > 0:
        should_ambush_first = True
    if get_leader_in_region(state, region, enemy) is not None:
        should_ambush_first = True

    if not should_ambush_first:
        return []

    ambush_regions = [region]
    for bp in battle_plan[1:]:
        bp_region = bp["region"]
        bp_enemy = bp["target"]
        # "each other Battle possible" — filter to Ambush-eligible Regions.
        bp_eligible, _ = validate_ambush_region(
            state, bp_region, GERMANS, bp_enemy)
        if bp_eligible:
            ambush_regions.append(bp_region)
    return ambush_regions


# ============================================================================
# SA: G_INTIMIDATE
# ============================================================================

def _can_intimidate_region(state, region):
    """Per A4.6.2: region has Ariovistus, OR Germanic Control + within
    one of Ariovistus / same region as Successor.
    """
    if _has_ariovistus(state, region):
        return (True, "")
    if not is_controlled_by(state, region, GERMANS):
        return (False, "no Germanic Control and no Ariovistus")
    aristos_region = _ariovistus_region(state)
    if aristos_region is None:
        return (False, "no Germanic Leader on map")
    leader_name = get_leader_in_region(state, aristos_region, GERMANS)
    if leader_name == ARIOVISTUS_LEADER:
        if region == aristos_region or is_adjacent(region, aristos_region):
            return (True, "")
        return (False, "not within 1 of Ariovistus")
    if region == aristos_region:
        return (True, "")
    return (False, "not in Successor's region")


def _select_intimidate_targets(state, region, max_count):
    """Pick up to max_count pieces to Intimidate in this region per A8.7.1.

    Targets ordered by:
      (1) Player Allies: Roman -> Aedui -> Belgae
      (2) Player Roman Auxilia -> player Aedui Warbands -> player Belgic
          Warbands
      (3) Non-player Roman Allies -> Non-player Aedui Allies (NOT
          Non-player Belgae or Arverni)
      (4) Other Non-player Roman/Aedui Auxilia or Warbands

    Excludes targets where the target faction has a Leader in the region
    (per A4.6.2).
    """
    non_players = state.get("non_player_factions", set())
    selected = []

    def _faction_has_leader(faction):
        return get_leader_in_region(state, region, faction) is not None

    # Tier 1 — Player Allies (Roman, Aedui, Belgae)
    for faction in (ROMANS, AEDUI, BELGAE):
        if faction in non_players:
            continue
        if _faction_has_leader(faction):
            continue
        if count_pieces(state, region, faction, ALLY) > 0:
            selected.append({
                "tier": 1,
                "target_faction": faction,
                "target_piece": ALLY,
                "target_state": None,
            })
            if len(selected) >= max_count:
                return selected

    # Tier 2 — Player Roman Auxilia / Aedui Warbands / Belgic Warbands
    tier2 = (
        (ROMANS, AUXILIA),
        (AEDUI, WARBAND),
        (BELGAE, WARBAND),
    )
    for faction, piece in tier2:
        if faction in non_players:
            continue
        if _faction_has_leader(faction):
            continue
        for st in (HIDDEN, REVEALED, SCOUTED):
            count = count_pieces_by_state(state, region, faction, piece, st)
            for _ in range(count):
                if len(selected) >= max_count:
                    return selected
                selected.append({
                    "tier": 2,
                    "target_faction": faction,
                    "target_piece": piece,
                    "target_state": st,
                })

    # Tier 3 — Non-player Roman/Aedui Allies (NOT Belgae or Arverni)
    for faction in (ROMANS, AEDUI):
        if faction not in non_players:
            continue
        if _faction_has_leader(faction):
            continue
        if count_pieces(state, region, faction, ALLY) > 0:
            selected.append({
                "tier": 3,
                "target_faction": faction,
                "target_piece": ALLY,
                "target_state": None,
            })
            if len(selected) >= max_count:
                return selected

    # Tier 4 — Other Non-player Roman/Aedui Auxilia or Warbands
    tier4 = (
        (ROMANS, AUXILIA),
        (AEDUI, WARBAND),
    )
    for faction, piece in tier4:
        if faction not in non_players:
            continue
        if _faction_has_leader(faction):
            continue
        for st in (HIDDEN, REVEALED, SCOUTED):
            count = count_pieces_by_state(state, region, faction, piece, st)
            for _ in range(count):
                if len(selected) >= max_count:
                    return selected
                selected.append({
                    "tier": 4,
                    "target_faction": faction,
                    "target_piece": piece,
                    "target_state": st,
                })

    return selected


def _check_intimidate_before_battle(state, battle_plan):
    """Determine Intimidate-before-Battle plan per A8.7.1.

    Per A8.7.1: Intimidate to remove enemy pieces that would NOT be
    guaranteed to be removed in the immediately subsequent Battle.
    Outside the free-Intimidate-in-Ariovistus's-Raid-Region case, the
    Germans will NOT Intimidate just to place markers.

    Returns:
        List of dicts {region, target_faction, target_piece, target_state}
        in order of Intimidate executions.
    """
    plan = []
    for bp in battle_plan:
        region = bp["region"]
        valid, _reason = _can_intimidate_region(state, region)
        if not valid:
            continue
        hidden = count_pieces_by_state(
            state, region, GERMANS, WARBAND, HIDDEN)
        if hidden == 0:
            continue
        targets = _select_intimidate_targets(state, region, max_count=hidden)
        for t in targets:
            plan.append({"region": region, "free": False, **t})
    return plan


def _determine_intimidate_after_raid(state, raid_plan):
    """Per A8.7.3 + A8.7.1: free Intimidate in Ariovistus's Raid region,
    then Intimidate further only if pieces would be removed.

    Per A8.7.1: "the Germans place Intimidated markers in Ariovistus's
    Region if the Germans Raided there, as part of their free Intimidate
    (A3.4.3). Then, if they removed any pieces above, they place
    Intimidated markers wherever they can (per A4.6.2). NOTE: Outside of
    Raid with free Intimidate, Non-player Germans will not Intimidate
    merely to place markers without removing pieces."

    If only the free marker (no removals at all), per A8.7.1 the Germans
    instead add no Special Ability.

    Returns:
        (sa_action, sa_regions, sa_details).
    """
    raided_regions = {r["region"] for r in raid_plan}
    aristos_region = _ariovistus_region(state)
    free_intim_region = (aristos_region
                         if aristos_region in raided_regions else None)

    intim_plan = []

    # Free Intimidate in Ariovistus's raid region (marker even if no removal)
    if free_intim_region is not None:
        valid, _ = _can_intimidate_region(state, free_intim_region)
        if valid:
            hidden = count_pieces_by_state(
                state, free_intim_region, GERMANS, WARBAND, HIDDEN)
            if hidden > 0:
                targets = _select_intimidate_targets(
                    state, free_intim_region, max_count=hidden)
                if targets:
                    for t in targets:
                        intim_plan.append({
                            "region": free_intim_region,
                            "free": True,
                            **t,
                        })
                else:
                    # No removal targets but free Intimidate places marker
                    intim_plan.append({
                        "region": free_intim_region,
                        "free": True,
                        "target_faction": None,
                        "target_piece": None,
                        "target_state": None,
                    })

    # Further Intimidates elsewhere — only if they would remove pieces
    for region in sorted({r["region"] for r in raid_plan}):
        if region == free_intim_region:
            continue
        valid, _ = _can_intimidate_region(state, region)
        if not valid:
            continue
        hidden = count_pieces_by_state(
            state, region, GERMANS, WARBAND, HIDDEN)
        if hidden == 0:
            continue
        targets = _select_intimidate_targets(
            state, region, max_count=hidden)
        for t in targets:
            intim_plan.append({"region": region, "free": False, **t})

    removed_anything = any(
        p.get("target_piece") is not None for p in intim_plan)
    only_free_marker = (
        len(intim_plan) == 1
        and intim_plan[0].get("free")
        and intim_plan[0].get("target_piece") is None
    )
    if not intim_plan:
        return (SA_ACTION_NONE, [], {})
    if only_free_marker and not removed_anything:
        # Per A8.7.1: "only free Intimidated -> no Special Ability"
        return (SA_ACTION_NONE, [], {})

    return (SA_ACTION_INTIMIDATE,
            sorted({p["region"] for p in intim_plan}),
            {"intimidate_plan": intim_plan})


def _determine_intimidate_or_settle_after_march(state, march_plan):
    """Per A8.7.1 / A8.7.5 — After a March, choose Intimidate OR Settle.

    Try Intimidate first; if nothing removable, fall through to Settle.
    If neither, no SA.

    Returns:
        (sa_action, sa_regions, sa_details).
    """
    scenario = state["scenario"]

    march_regions = set()
    for k in ("origins", "destinations", "control_destinations"):
        v = march_plan.get(k)
        if isinstance(v, list):
            march_regions.update(v)
    if march_plan.get("leader_or_group_destination"):
        march_regions.add(march_plan["leader_or_group_destination"])

    intim_plan = []
    for region in sorted(march_regions):
        valid, _ = _can_intimidate_region(state, region)
        if not valid:
            continue
        hidden = count_pieces_by_state(
            state, region, GERMANS, WARBAND, HIDDEN)
        if hidden == 0:
            continue
        targets = _select_intimidate_targets(
            state, region, max_count=hidden)
        if targets:
            for t in targets:
                intim_plan.append({"region": region, "free": False, **t})

    if intim_plan:
        return (SA_ACTION_INTIMIDATE,
                sorted({p["region"] for p in intim_plan}),
                {"intimidate_plan": intim_plan})

    # Then Settle — A8.7.1 / A8.7.5
    settle_dests = _get_settle_destinations(state, scenario)
    if settle_dests:
        resources = state.get("resources", {}).get(GERMANS, 0)
        plan = []
        avail = get_available(state, GERMANS, SETTLEMENT)
        for region in settle_dests:
            if avail <= 0:
                break
            cost = SETTLE_COST
            if _is_devastated(state, region):
                cost *= 2
            if resources < cost:
                break
            plan.append({"region": region, "cost": cost})
            resources -= cost
            avail -= 1
        if plan:
            return (SA_ACTION_SETTLE,
                    [s["region"] for s in plan],
                    {"settle_plan": plan})

    return (SA_ACTION_NONE, [], {})


# ============================================================================
# SA: G_SETTLE — public node for explicit Settle-only contexts
# ============================================================================

def node_g_settle(state):
    """G_SETTLE: Settle all Settlements able per A8.7.1.

    Per A8.7.1:
    - If Rallying: Settle first if any can be placed; else after Rally.
    - If Marching: Settle all possible after the March (only if didn't
      Intimidate).
    - If no Settlement can be placed, the Command gets no SA.

    Returns:
        (sa_action, sa_regions, sa_details).
    """
    scenario = state["scenario"]
    settle_dests = _get_settle_destinations(state, scenario)
    if not settle_dests:
        return (SA_ACTION_NONE, [], {})

    resources = state.get("resources", {}).get(GERMANS, 0)
    plan = []
    avail = get_available(state, GERMANS, SETTLEMENT)
    for region in settle_dests:
        if avail <= 0:
            break
        cost = SETTLE_COST
        if _is_devastated(state, region):
            cost *= 2
        if resources < cost:
            break
        plan.append({"region": region, "cost": cost})
        resources -= cost
        avail -= 1
    if not plan:
        return (SA_ACTION_NONE, [], {})
    return (SA_ACTION_SETTLE,
            [s["region"] for s in plan],
            {"settle_plan": plan})


# ============================================================================
# WINTER NODES — Quarters / Spring
# ============================================================================

def node_g_quarters(state):
    """G_QUARTERS: Quarters Phase per A8.7.6.

    Per A8.7.6:
    - First leave any (Drought) Devastated Region where Germans have no
      Ally or Settlement for random adjacent Regions they Control.
    - Then move their Leader and/or one group of Warbands to join the
      Leader with the largest group of Germanic Warbands able and, within
      that, to get or keep the Leader within one Region of the most
      Regions with Germanic Forces able.
    - Leave behind at least 1 Warband and at least the number of Warbands
      needed to retain German Control.

    Returns:
        Quarters action details dict.
    """
    scenario = state["scenario"]
    playable = get_playable_regions(scenario, state.get("capabilities"))

    quarters_plan = {
        "leave_devastated": [],
        "leader_move": None,
    }

    for region in playable:
        if count_pieces(state, region, GERMANS) == 0:
            continue
        if not _is_devastated(state, region):
            continue
        has_ally = False
        for tribe in get_tribes_in_region(region, scenario):
            if state["tribes"].get(tribe, {}).get(
                    "allied_faction") == GERMANS:
                has_ally = True
                break
        has_settlement = _has_settlement(state, region)
        if has_ally or has_settlement:
            continue
        controlled_adj = sorted([
            adj for adj in get_adjacent(region, scenario)
            if is_controlled_by(state, adj, GERMANS)
        ])
        if controlled_adj:
            dest = random_select(state, controlled_adj)
            quarters_plan["leave_devastated"].append({
                "from": region, "to": dest,
            })

    aristos_region = _ariovistus_region(state)
    if aristos_region:
        candidates = [aristos_region] + sorted(
            get_adjacent(aristos_region, scenario))
        best_dest = None
        best_wb = -1
        best_adj = -1
        for dest in candidates:
            wb = count_pieces(state, dest, GERMANS, WARBAND)
            adj_count = 0
            if count_pieces(state, dest, GERMANS) > 0:
                adj_count += 1
            for a in get_adjacent(dest, scenario):
                if count_pieces(state, a, GERMANS) > 0:
                    adj_count += 1
            if (wb > best_wb
                    or (wb == best_wb and adj_count > best_adj)):
                best_wb = wb
                best_adj = adj_count
                best_dest = dest
        if best_dest and best_dest != aristos_region:
            origin_wb = count_pieces(state, aristos_region, GERMANS, WARBAND)
            min_leave = 1
            if is_controlled_by(state, aristos_region, GERMANS):
                total_non_german = sum(
                    count_pieces(state, aristos_region, f)
                    for f in (ROMANS, ARVERNI, AEDUI, BELGAE)
                )
                german_non_wb = (
                    count_pieces(state, aristos_region, GERMANS) - origin_wb)
                german_staying_non_wb = max(0, german_non_wb - 1)
                wb_for_control = max(
                    0, total_non_german - german_staying_non_wb + 1)
                min_leave = max(min_leave, wb_for_control)
            movable = max(0, origin_wb - min_leave)
            quarters_plan["leader_move"] = {
                "from": aristos_region,
                "to": best_dest,
                "warbands_moved": movable,
                "warbands_left": min_leave,
            }

    return quarters_plan


def node_g_spring(state):
    """G_SPRING: Spring Phase per §8.3.2 / §6.6.

    Place Successor at most Germans if Ariovistus is off-map.

    Returns:
        Spring action dict, or None if nothing to do.
    """
    aristos_region = _ariovistus_region(state)
    if aristos_region is not None:
        return None
    best_region = get_leader_placement_region(state, GERMANS)
    if best_region:
        return {"place_leader": ARIOVISTUS_LEADER, "region": best_region}
    return None


# ============================================================================
# AGREEMENTS
# ============================================================================

def node_g_agreements(state, requesting_faction, request_type):
    """G_AGREEMENTS: Agreement decisions per A8.4 / A8.7 flowchart.

    Per A8.4: throughout §8.4, treat "Arverni" as "Germans"; references
    to "Gauls" become "Gauls or Germans"; references to "Germans" become
    "Arverni". So:
    - Germans never voluntarily transfer Resources.
    - Germans never agree to Supply Lines / Retreat / Quarters.
    - Germans always Harass Roman March and Seize.

    Args:
        state: Game state dict.
        requesting_faction: Faction making the request.
        request_type: "supply_line", "retreat", "quarters", "resources",
                      "harassment".

    Returns:
        True if Germans agree.
    """
    if request_type == "harassment":
        if requesting_faction == ROMANS:
            return True
        return False
    return False


# ============================================================================
# MAIN FLOWCHART DRIVER
# ============================================================================

def execute_german_turn(state):
    """Walk the German bot flowchart and return the chosen action.

    Implements the full decision tree per A8.7:
      G1 -> (Battle | G1b) -> G2 -> G3 -> G3b -> G4 -> G5 -> process nodes.

    The German bot is Ariovistus-only. Raises BotDispatchError if called
    in a base game scenario.

    Args:
        state: Game state dict.

    Returns:
        Action dict describing the German bot's decision.
    """
    scenario = state["scenario"]

    # Scenario isolation — German bot is Ariovistus-only
    if scenario in BASE_SCENARIOS:
        raise BotDispatchError(
            f"German bot cannot run in scenario '{scenario}'. "
            f"Germans are game-run via §6.2 in base game."
        )

    # G1: Battle or March under Threat?
    g1_result, _threats = node_g1(state)
    if g1_result == "Yes":
        return node_g_battle(state)

    # G1b: Enemy at victory and Ariovistus has 12+ Warbands?
    g1b_result = node_g1b(state)
    if g1b_result == "Yes":
        return node_g_march_threat(state)

    # G2: Pass?
    g2_result = node_g2(state)
    if g2_result == "Yes":
        return _make_action(ACTION_PASS)

    # G3: Can play Event by SoP?
    g3_result = node_g3(state)
    if g3_result == "Yes":
        g3b_result = node_g3b(state)
        if g3b_result == "No":
            return node_g_event(state)

    # G4: Raid (0-3 Resources and roll 1-4)?
    g4_result = node_g4(state)
    if g4_result == "Yes":
        return node_g_raid(state)

    # G5: Rally+Settle would qualify?
    g5_result = node_g5(state)
    if g5_result == "Yes":
        return node_g_rally(state)

    # Default: March to expand or mass — A8.7.5
    return node_g_march_expand(state)
