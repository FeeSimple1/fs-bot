"""
Non-Player Roman flowchart — §8.8 and A8.8.

Every node from the Roman bot flowchart (R1 through R_SCOUT, plus
R_QUARTERS, R_SPRING, R_AGREEMENTS, R_DIVICIACUS) is a labeled function.
Ariovistus A8 conditional branches are gated on state["scenario"].

Node functions return an action dict describing what the bot decided to do.
The dispatch loop calls execute_roman_turn(state) which walks the flowchart.
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
    CMD_RECRUIT, CMD_MARCH, CMD_SEIZE, CMD_BATTLE,
    SA_BUILD, SA_SCOUT, SA_BESIEGE,
    # Markers
    MARKER_FROST,
    # Leaders
    CAESAR, DIVICIACUS as DIVICIACUS_LEADER,
    # Tribes
    TRIBE_HELVII,
    # Map
    PROVINCIA, BELGICA,
    BELGICA_REGIONS, GERMANIA_REGIONS,
    # Sequence of play
    ELIGIBLE, FIRST_ELIGIBLE, SECOND_ELIGIBLE,
    # Events
    EVENT_UNSHADED,
    # Victory
    ROMAN_VICTORY_THRESHOLD,
    # Die
    DIE_MIN, DIE_MAX,
)
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, get_leader_in_region,
    find_leader, get_available, _count_on_map,
)
from fs_bot.board.control import (
    is_controlled_by, get_controlled_regions, calculate_control,
)
from fs_bot.engine.victory import (
    calculate_victory_score, calculate_victory_margin, check_victory,
)
from fs_bot.map.map_data import (
    get_adjacent, get_playable_regions, get_tribes_in_region,
    get_region_group, ALL_REGION_DATA,
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
    # Supply line / agreements
    np_agrees_to_supply_line,
)


# ============================================================================
# Action result constants
# ============================================================================

ACTION_BATTLE = "Battle"
ACTION_MARCH = "March"
ACTION_RECRUIT = "Recruit"
ACTION_SEIZE = "Seize"
ACTION_EVENT = "Event"
ACTION_PASS = "Pass"
ACTION_NONE = "None"

SA_ACTION_BUILD = "Build"
SA_ACTION_SCOUT = "Scout"
SA_ACTION_BESIEGE = "Besiege"
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
# HELPER: Check Roman-specific threat conditions
# ============================================================================

def _caesar_region(state):
    """Find Caesar's region, or None."""
    return find_leader(state, ROMANS)


def _has_roman_threat(state, region, scenario):
    """Check if a region meets the R1 'Battle or March under Threat' condition.

    Per §8.8.1: Caesar or any Legion is in a Region where any Gaul or
    Germans have an Ally, Citadel, Leader, or Control, OR where an
    immediate enemy Attack would force a Loss roll on a Legion or Caesar.

    Ariovistus (A8.8.1): Count Settlements as Allies for these conditions.

    Args:
        state: Game state dict.
        region: Region constant.
        scenario: Scenario constant.

    Returns:
        True if the region has a threat per §8.8.1 / A8.8.1.
    """
    # Must have Caesar or a Legion in this region
    has_caesar = get_leader_in_region(state, region, ROMANS) is not None
    has_legion = count_pieces(state, region, ROMANS, LEGION) > 0
    if not has_caesar and not has_legion:
        return False

    # Check all non-Roman factions (including Aedui per "any Gaul")
    for enemy in FACTIONS:
        if enemy == ROMANS:
            continue
        # Ally
        if count_pieces(state, region, enemy, ALLY) > 0:
            return True
        # Citadel
        if count_pieces(state, region, enemy, CITADEL) > 0:
            return True
        # Settlement (Ariovistus counts as Ally) — A8.8.1
        if (scenario in ARIOVISTUS_SCENARIOS
                and count_pieces(state, region, enemy, SETTLEMENT) > 0):
            return True
        # Leader
        if get_leader_in_region(state, region, enemy) is not None:
            return True
        # Control
        if is_controlled_by(state, region, enemy):
            return True

    # TODO: Check if immediate enemy Battle/Rampage would force Loss on
    # Legion or Caesar. This requires full battle simulation which will be
    # implemented when battle logic is complete. For now, the above checks
    # cover the primary conditions from the flowchart.

    return False


def _get_threat_regions(state, scenario):
    """Get all regions meeting the R1 threat condition.

    Returns:
        List of region constants.
    """
    playable = get_playable_regions(scenario, state.get("capabilities"))
    return [r for r in playable if _has_roman_threat(state, r, scenario)]


def _enemy_at_victory(state, scenario):
    """Check if any enemy has a victory margin of 0 or better.

    Per §8.8.1: "an enemy Faction currently has a victory margin of 0 or
    better (7.3)."

    Returns:
        The enemy faction with highest margin >= 0, or None.
    """
    best_faction = None
    best_margin = -1

    # In base game, victory factions: Romans, Arverni, Aedui, Belgae
    # In Ariovistus: Romans, Germans, Aedui, Belgae
    for faction in FACTIONS:
        if faction == ROMANS:
            continue
        try:
            margin = calculate_victory_margin(state, faction)
            if margin >= 0 and margin > best_margin:
                best_margin = margin
                best_faction = faction
        except Exception:
            continue

    return best_faction


# ============================================================================
# R_BATTLE targeting helpers
# ============================================================================

def _rank_battle_targets(state, region, scenario):
    """Rank enemy factions as Battle targets in a region per §8.8.1.

    Priority: (a) Leaders, (b) most Warbands, (c) players first,
    (d) most Allies+Citadels, (e) highest victory margins.

    Ariovistus (A8.8.1): Battle Diviciacus only if Aedui at 0+ victory.

    Args:
        state: Game state dict.
        region: Battle region.
        scenario: Scenario constant.

    Returns:
        List of enemy factions sorted by targeting priority (best first).
    """
    non_players = state.get("non_player_factions", set())
    enemies = []

    for enemy in FACTIONS:
        if enemy == ROMANS:
            continue
        if count_pieces(state, region, enemy) == 0:
            continue

        # A8.8.1: Only Battle Aedui (Diviciacus) if Aedui at 0+ victory
        if (scenario in ARIOVISTUS_SCENARIOS
                and enemy == AEDUI
                and get_leader_in_region(state, region, AEDUI) is not None):
            try:
                aedui_margin = calculate_victory_margin(state, AEDUI)
                if aedui_margin < 0:
                    continue
            except Exception:
                continue

        has_leader = 1 if get_leader_in_region(state, region, enemy) else 0
        warbands = count_pieces(state, region, enemy, WARBAND)
        is_player = 0 if enemy in non_players else 1
        allies_citadels = count_faction_allies_and_citadels(state, enemy)
        try:
            margin = calculate_victory_margin(state, enemy)
        except Exception:
            margin = -999

        enemies.append((enemy, (-has_leader, -warbands, -is_player,
                                -allies_citadels, -margin)))

    enemies.sort(key=lambda x: x[1])
    return [e[0] for e in enemies]


# ============================================================================
# R_MARCH destination helpers
# ============================================================================

def _rank_march_destinations(state, scenario):
    """Rank destination regions for Roman March per §8.8.1.

    Destinations must have enemy Allies or Citadels.  Tiers evaluated in
    order, falling through to the next if no candidates:
      (1) enemies at 0+ victory margin, players before NPs;
      then roll a die:
      (2) on 1-2: Germanic Allies if 2+ on map (base) /
          Arverni Allies+Citadels (Ariovistus, A8.8.1);
      (3) on 3-4: player Factions' Allies/Citadels;
      (4) on 5-6 or fallthrough: enemies with most Allies+Citadels.

    Sub-priorities within each tier:
      (b) fewest enemy mobile pieces (approximation for fewest Losses
          to enemy Battle — full battle simulation not yet implemented),
      (c) most such Allies/Citadels in the region,
      (d) ending in Supply Line (approximated: region has Roman pieces
          or is adjacent to Roman-controlled region — full supply-line
          graph check deferred),
      (e) least Harassment (fewest enemy Hidden Warbands).

    Returns:
        List of (region, target_faction) tuples sorted by priority.
    """
    from fs_bot.commands.rally import has_supply_line

    playable = get_playable_regions(scenario, state.get("capabilities"))
    non_players = state.get("non_player_factions", set())

    # Build candidate list with all relevant metadata
    all_candidates = []
    for region in playable:
        for enemy in FACTIONS:
            if enemy == ROMANS:
                continue
            ally_count = count_pieces(state, region, enemy, ALLY)
            citadel_count = count_pieces(state, region, enemy, CITADEL)
            # A8.8.1: count Settlements as Allies
            if scenario in ARIOVISTUS_SCENARIOS:
                ally_count += count_pieces(state, region, enemy, SETTLEMENT)
            if ally_count + citadel_count == 0:
                continue

            try:
                margin = calculate_victory_margin(state, enemy)
            except Exception:
                margin = -999

            # (b) Approximate fewest Losses to enemy Battle as fewest
            # enemy mobile pieces in the region
            enemy_mobile = count_mobile_pieces(state, region, enemy)
            # (c) Most Allies/Citadels of this enemy in the region
            local_ac = ally_count + citadel_count
            # (d) Ending in Supply Line — best-effort approximation
            in_supply = 1 if has_supply_line(state, region) else 0
            # (e) Least Harassment — fewest enemy Hidden Warbands
            enemy_hidden_wb = 0
            for f in FACTIONS:
                if f == ROMANS:
                    continue
                enemy_hidden_wb += count_pieces_by_state(
                    state, region, f, WARBAND, HIDDEN)

            all_candidates.append({
                "region": region,
                "enemy": enemy,
                "margin": margin,
                "at_victory": margin >= 0,
                "is_player": enemy not in non_players,
                "local_ac": local_ac,
                "total_ac": count_faction_allies_and_citadels(state, enemy),
                "enemy_mobile": enemy_mobile,
                "in_supply": in_supply,
                "hidden_wb": enemy_hidden_wb,
            })

    if not all_candidates:
        return []

    def _sub_sort_key(c):
        """Sub-priorities (b)-(e) used within each tier."""
        return (
            c["enemy_mobile"],    # (b) fewest enemy mobile pieces first
            -c["local_ac"],       # (c) most local Allies/Citadels first
            -c["in_supply"],      # (d) in Supply Line first
            c["hidden_wb"],       # (e) fewest Hidden Warbands first
        )

    # --- Tier 1: enemies at 0+ victory margin ---
    tier1 = [c for c in all_candidates if c["at_victory"]]
    if tier1:
        # Players before NPs, then sub-priorities
        tier1.sort(key=lambda c: (
            0 if c["is_player"] else 1,
            _sub_sort_key(c),
        ))
        return [(c["region"], c["enemy"]) for c in tier1]

    # --- Die roll for tiers 2-4 ---
    die = roll_die(state)

    # --- Tier 2: on roll 1-2 ---
    if die <= 2:
        if scenario in ARIOVISTUS_SCENARIOS:
            # A8.8.1: count Arverni Allies+Citadels instead of Germanic;
            # March to Arverni targets
            tier2 = [c for c in all_candidates if c["enemy"] == ARVERNI]
        else:
            # Base: Germanic Allies — only if 2+ Germanic Allies on map
            german_ally_count = 0
            for tribe_info in state["tribes"].values():
                if tribe_info.get("allied_faction") == GERMANS:
                    german_ally_count += 1
            if german_ally_count >= 2:
                tier2 = [c for c in all_candidates if c["enemy"] == GERMANS]
            else:
                tier2 = []
        if tier2:
            tier2.sort(key=_sub_sort_key)
            return [(c["region"], c["enemy"]) for c in tier2]
        # Fall through if no tier 2 candidates

    # --- Tier 3: on roll 3-4 ---
    if die <= 4:
        tier3 = [c for c in all_candidates if c["is_player"]]
        if tier3:
            tier3.sort(key=_sub_sort_key)
            return [(c["region"], c["enemy"]) for c in tier3]
        # Fall through if no tier 3 candidates

    # --- Tier 4: enemies with most Allies+Citadels (roll 5-6 or fallthrough) ---
    tier4 = list(all_candidates)
    tier4.sort(key=lambda c: (
        -c["total_ac"],       # Most total Allies+Citadels first
        _sub_sort_key(c),
    ))
    return [(c["region"], c["enemy"]) for c in tier4]


# ============================================================================
# NODE FUNCTIONS — Main flowchart
# ============================================================================

def node_r1(state):
    """R1: Caesar or Legion with enemy threat?

    Per §8.8.1: Check if Caesar or any Legion is in a Region with
    enemy Ally, Citadel, Leader, Control, or where enemy Battle/Rampage
    would force Loss on Legion or Caesar.

    Returns:
        "Yes" and list of threat regions, or "No".
    """
    scenario = state["scenario"]
    threat_regions = _get_threat_regions(state, scenario)
    if threat_regions:
        return ("Yes", threat_regions)
    return ("No", [])


def node_r2(state):
    """R2: Enemy at 0+ victory AND Caesar with 2+ Legions and 4+ Auxilia?

    Per §8.8.1: If no Battle from R1, check if conditions for March exist.

    Returns:
        "Yes" or "No".
    """
    scenario = state["scenario"]

    # Check if any enemy is at 0+ victory margin
    if _enemy_at_victory(state, scenario) is None:
        return "No"

    # Check Caesar's position
    caesar_region = _caesar_region(state)
    if caesar_region is None:
        return "No"

    # At least 2 Legions in Caesar's region
    legions = count_pieces(state, caesar_region, ROMANS, LEGION)
    if legions < 2:
        return "No"

    # At least 4 Auxilia in Caesar's region
    auxilia = count_pieces(state, caesar_region, ROMANS, AUXILIA)
    if auxilia < 4:
        return "No"

    return "Yes"


def node_r3(state):
    """R3: Romans by Sequence of Play may use Event?

    Per §8.8.2: If 2nd Eligible and 1st used Event or Command only,
    Romans can't play Event.

    Returns:
        "Yes" or "No".
    """
    return "Yes" if state.get("can_play_event", False) else "No"


def node_r4(state):
    """R4: Event Ineffective, Capability in final year, or 'No Romans'?

    Per §8.8.2: Check all decline conditions. Also check NP Instructions.

    Returns:
        "Yes" (decline Event) or "No" (play Event).
    """
    card_id = state.get("current_card_id")
    if card_id is None:
        return "Yes"

    if should_decline_event(state, card_id, ROMANS):
        return "Yes"

    # Check specific instructions that might render Event ineffective
    instr = get_event_instruction(card_id, ROMANS, state["scenario"])
    if instr and instr.instruction:
        # Some instructions say "treat as 'No Romans'" conditionally
        # This will be evaluated by the Event handler
        pass

    return "No"


def node_r5(state):
    """R5: 9+ Auxilia Available?

    Per §8.8.3/8.8.4: If 8 or fewer Auxilia Available → March.
    If 9+ → check Recruit.

    Returns:
        "Yes" (9+ available → Recruit path) or "No" (≤8 → March).
    """
    avail = get_available(state, ROMANS, AUXILIA)
    return "Yes" if avail >= 9 else "No"


# ============================================================================
# PROCESS NODES
# ============================================================================

def node_r_event(state):
    """R_EVENT: Execute Event.

    Per §8.8.2: Execute per §8.2 — use Unshaded text (§8.2.2).
    Check Instructions (§8.2.1) if gray laurels on card's Roman symbol.

    Returns:
        Action dict for Event execution.
    """
    card_id = state.get("current_card_id")
    preference = get_dual_use_preference(ROMANS, state["scenario"])
    instr = get_event_instruction(card_id, ROMANS, state["scenario"])

    return _make_action(
        ACTION_EVENT,
        details={
            "card_id": card_id,
            "text_preference": preference,
            "instruction": instr.instruction if instr else None,
        },
    )


def node_r_battle(state):
    """R_BATTLE: Battle process.

    Per §8.8.1: Battle where Roman Losses < 1/2 enemy's AND no Loss on Caesar.
    Priorities: (a) Leaders, (b) most Warbands, (c) players, (d) most A+C,
    (e) highest victory margins.

    If Caesar meets condition but won't Battle → March instead.

    Returns:
        Action dict for Battle, or redirects to March.
    """
    scenario = state["scenario"]
    threat_regions = _get_threat_regions(state, scenario)

    if not threat_regions:
        return node_r_march(state)

    # Check if Caesar is in a threat region but won't Battle — §8.8.1
    caesar_region = _caesar_region(state)
    if caesar_region and caesar_region in threat_regions:
        # Simplified: if Caesar can't guarantee favorable Battle, March
        # Full battle simulation will be implemented later
        pass

    # Rank targets in each region
    battle_plan = []
    for region in threat_regions:
        targets = _rank_battle_targets(state, region, scenario)
        if targets:
            battle_plan.append({"region": region, "targets": targets})

    if not battle_plan:
        return node_r_march(state)

    # Determine SA: Besiege at start, or Scout after — §8.8.1
    sa, sa_regions = _determine_battle_sa(state, battle_plan, scenario)

    return _make_action(
        ACTION_BATTLE,
        regions=[bp["region"] for bp in battle_plan],
        sa=sa,
        sa_regions=sa_regions,
        details={"battle_plan": battle_plan},
    )


def _determine_battle_sa(state, battle_plan, scenario):
    """Determine SA for Battle: Besiege, then Scout, per §8.8.1.

    Besiege if needed to ensure removal of enemy Ally, or Citadel that
    might suffer < 3 Loss rolls. If Besiege anywhere, Besiege everywhere
    possible.

    If no Besiege, Scout after Battle.

    Returns:
        (sa_action, sa_regions) tuple.
    """
    besiege_regions = []
    for bp in battle_plan:
        region = bp["region"]
        for enemy in bp["targets"]:
            # Check for Allies that need Besiege to ensure removal
            if count_pieces(state, region, enemy, ALLY) > 0:
                besiege_regions.append(region)
                break
            # Check for Citadels that might suffer < 3 Losses
            if count_pieces(state, region, enemy, CITADEL) > 0:
                besiege_regions.append(region)
                break

    if besiege_regions:
        # If Besiege anywhere, do it everywhere possible — §8.8.1
        all_regions = [bp["region"] for bp in battle_plan]
        return (SA_ACTION_BESIEGE, all_regions)

    # No Besiege → Scout after Battle
    return (SA_ACTION_SCOUT, [])


def node_r_march(state):
    """R_MARCH: March process.

    Per §8.8.1: March with Leader, most Legions, Auxilia. From up to 3
    origins. To enemy Allies/Citadels in 1-2 regions.

    Returns:
        Action dict for March.
    """
    scenario = state["scenario"]

    # If Frost blocks March — §8.4.4
    if is_frost_active(state):
        # Check if any player faction is at victory
        non_players = state.get("non_player_factions", set())
        for f in FACTIONS:
            if f != ROMANS and f not in non_players:
                if check_frost_restriction(state, f):
                    return node_r_recruit(state)

    destinations = _rank_march_destinations(state, scenario)

    if not destinations:
        return node_r_recruit(state)

    # Determine origin regions — §8.8.1
    threat_regions = _get_threat_regions(state, scenario)
    origins = _select_march_origins(state, threat_regions, destinations, scenario)

    # Determine how many destination regions — §8.8.1
    # If ≤6 Legions on map and can consolidate to one → one destination
    legions_on_map = _count_on_map(state, ROMANS, LEGION)
    dest_count = 1 if legions_on_map <= 6 else min(2, len(destinations))
    selected_dests = destinations[:dest_count]

    # Determine SA: Scout during March or Build after — §8.8.1
    sa = SA_ACTION_BUILD

    return _make_action(
        ACTION_MARCH,
        regions=[d[0] for d in selected_dests],
        sa=sa,
        details={
            "origins": origins,
            "destinations": selected_dests,
            "dest_count": dest_count,
        },
    )


def _select_march_origins(state, threat_regions, destinations, scenario):
    """Select up to 3 March origin regions per §8.8.1.

    (1) 1 meeting threat condition
    (2) 1 also meeting threat condition BUT not destination of 1st group
    (3) 1 where no enemy Ally/Citadel (with Leader first, then most Legions)

    Returns:
        List of origin region constants.
    """
    origins = []
    dest_regions = {d[0] for d in destinations}

    # (1) First threat region
    if threat_regions:
        origins.append(threat_regions[0])

    # (2) Second threat region, not a destination of 1st group
    for r in threat_regions[1:]:
        if r not in dest_regions or len(origins) == 0:
            origins.append(r)
            break

    # (3) Region with no enemy Ally/Citadel, prefer with Leader then Legions
    playable = get_playable_regions(scenario, state.get("capabilities"))
    clean_regions = []
    for r in playable:
        if r in origins:
            continue
        has_enemy_ac = False
        for enemy in FACTIONS:
            if enemy == ROMANS:
                continue
            if (count_pieces(state, r, enemy, ALLY) > 0
                    or count_pieces(state, r, enemy, CITADEL) > 0):
                has_enemy_ac = True
                break
        if not has_enemy_ac and count_pieces(state, r, ROMANS) > 0:
            clean_regions.append(r)

    if clean_regions:
        # Prefer Leader's region, then most Legions
        def _rank(r):
            has_leader = 1 if get_leader_in_region(state, r, ROMANS) else 0
            legions = count_pieces(state, r, ROMANS, LEGION)
            return (-has_leader, -legions)
        clean_regions.sort(key=_rank)
        origins.append(clean_regions[0])

    return origins[:3]


def node_r_recruit(state):
    """R_RECRUIT: Recruit process.

    Per §8.8.4: Recruit if would add 2+ Allies or 6+ pieces total.
    (1) Place all Allies, first at Supply Line.
    (2) Place all Auxilia, first at Supply Line.
    Build before Recruit, or Scout after.

    If wouldn't place enough → Seize.

    Returns:
        Action dict for Recruit, or redirects to Seize.
    """
    scenario = state["scenario"]

    # Check if Recruit would place enough pieces
    avail_allies = get_available(state, ROMANS, ALLY)
    avail_auxilia = get_available(state, ROMANS, AUXILIA)

    # Count how many could actually be placed (simplified — full validation
    # requires checking region eligibility, which depends on Supply Lines)
    potential_allies = avail_allies
    potential_auxilia = avail_auxilia
    total_potential = potential_allies + potential_auxilia

    if potential_allies >= 2 or total_potential >= 6:
        # Build before Recruit — §8.8.4
        sa = SA_ACTION_BUILD

        return _make_action(
            ACTION_RECRUIT,
            sa=sa,
            details={
                "potential_allies": potential_allies,
                "potential_auxilia": potential_auxilia,
            },
        )

    return node_r_seize(state)


def node_r_seize(state):
    """R_SEIZE: Seize process.

    Per §8.8.5: Seize only where no Harassment.
    (1) Disperse all Tribes, NOT Helvii — at player pieces first, in Belgica.
    (2) Seize for all other Resources.
    Build or Scout after.

    If no Seize possible → Pass.

    Returns:
        Action dict for Seize, or Pass.
    """
    scenario = state["scenario"]
    non_players = state.get("non_player_factions", set())
    playable = get_playable_regions(scenario, state.get("capabilities"))

    # Find regions where Romans can Seize without Harassment
    # Per §3.2.3: Harassment comes from ALL factions with Warbands in the
    # region, not just the designated March/Seize harassers from §8.4.2.
    # Per §8.8.5: "Seize only where no Harassment Loss" — skip any region
    # where ANY non-Roman faction has 3+ Hidden Warbands.
    seize_regions = []

    for region in playable:
        if count_pieces(state, region, ROMANS) == 0:
            continue
        # Check for Harassment — any non-Roman faction with 3+ Hidden Warbands
        # Per §3.2.3: "For every three Hidden Warbands..."
        has_harassment = False
        for faction in FACTIONS:
            if faction == ROMANS:
                continue
            hidden_wb = count_pieces_by_state(
                state, region, faction, WARBAND, HIDDEN)
            if hidden_wb >= 3:
                has_harassment = True
                break
        if not has_harassment:
            seize_regions.append(region)

    if not seize_regions:
        return _make_action(ACTION_PASS)

    # Rank Seize regions: Disperse first (at player pieces, in Belgica)
    disperse_regions = []
    resource_regions = []

    for region in seize_regions:
        # Per §3.2.3: Dispersal requires Roman Control in the region
        if not is_controlled_by(state, region, ROMANS):
            resource_regions.append(region)
            continue
        tribes = get_tribes_in_region(region, scenario)
        can_disperse = False
        for tribe in tribes:
            # NOT Helvii — §8.8.5
            if tribe == TRIBE_HELVII:
                continue
            tribe_info = state["tribes"].get(tribe, {})
            if tribe_info.get("allied_faction") is None and tribe_info.get("status") is None:
                # Subdued tribe — can be Dispersed
                can_disperse = True
                break
        if can_disperse:
            disperse_regions.append(region)
        else:
            resource_regions.append(region)

    # Sort disperse regions: player pieces first, Belgica first — §8.8.5
    def _disperse_rank(r):
        has_player_pieces = 0
        for f in FACTIONS:
            if f != ROMANS and f not in non_players:
                if count_pieces(state, r, f) > 0:
                    has_player_pieces = 1
                    break
        in_belgica = 1 if get_region_group(r) == BELGICA else 0
        return (-has_player_pieces, -in_belgica)

    disperse_regions.sort(key=_disperse_rank)

    all_seize = disperse_regions + resource_regions

    return _make_action(
        ACTION_SEIZE,
        regions=all_seize,
        sa=SA_ACTION_BUILD,
        details={"disperse_regions": disperse_regions},
    )


# ============================================================================
# SPECIAL ABILITY NODES
# ============================================================================

def node_r_besiege(state, battle_regions):
    """R_BESIEGE: Besiege at start of Battle.

    Per §8.8.1: Besiege where needed to ensure removal of Ally, or
    Citadel that might suffer < 3 Loss rolls. If anywhere, then everywhere.

    Args:
        state: Game state dict.
        battle_regions: List of Battle region constants.

    Returns:
        List of regions to Besiege, or empty.
    """
    scenario = state["scenario"]
    besiege_needed = []

    for region in battle_regions:
        for enemy in FACTIONS:
            if enemy == ROMANS:
                continue
            # Ally that needs Besiege to ensure removal
            if count_pieces(state, region, enemy, ALLY) > 0:
                besiege_needed.append(region)
                break
            # Citadel at risk
            if count_pieces(state, region, enemy, CITADEL) > 0:
                besiege_needed.append(region)
                break

    if besiege_needed:
        # If Besiege anywhere, do it everywhere possible
        return battle_regions[:]
    return []


def node_r_build(state, *, exclude_regions=None):
    """R_BUILD: Build after March/Seize or before Recruit.

    Per §8.8.1:
    (1) Place all Forts, first at non-Aedui Warbands.
    (2) Subdue all Allies, best victory margins first, players first.
    (3) Place all Roman Allies.
    Stop spending when Resources drop below 6.

    Args:
        state: Game state dict.
        exclude_regions: Regions to exclude (e.g. where Seize occurred).

    Returns:
        Build action details dict.
    """
    scenario = state["scenario"]
    non_players = state.get("non_player_factions", set())
    playable = get_playable_regions(scenario, state.get("capabilities"))
    exclude = set(exclude_regions or [])

    build_plan = {
        "forts": [],
        "subdue": [],
        "allies": [],
    }

    # (1) Place Forts — first where non-Aedui Warbands
    avail_forts = get_available(state, ROMANS, FORT)
    fort_candidates = []
    for region in playable:
        if region in exclude:
            continue
        if count_pieces(state, region, ROMANS, FORT) > 0:
            continue  # Already has a Fort
        if count_pieces(state, region, ROMANS) == 0:
            continue  # Must have Romans present
        # Check for non-Aedui Warbands
        non_aedui_wb = 0
        for f in FACTIONS:
            if f == AEDUI or f == ROMANS:
                continue
            non_aedui_wb += count_pieces(state, region, f, WARBAND)
        fort_candidates.append((region, non_aedui_wb))

    fort_candidates.sort(key=lambda x: -x[1])
    for region, _ in fort_candidates[:avail_forts]:
        build_plan["forts"].append(region)

    # (2) Subdue Allies — best victory margins, players first
    subdue_candidates = []
    for region in playable:
        if region in exclude:
            continue
        tribes = get_tribes_in_region(region, scenario)
        for tribe in tribes:
            tribe_info = state["tribes"].get(tribe, {})
            allied_to = tribe_info.get("allied_faction")
            if allied_to and allied_to != ROMANS:
                try:
                    margin = calculate_victory_margin(state, allied_to)
                except Exception:
                    margin = -999
                is_player = 0 if allied_to in non_players else 1
                subdue_candidates.append((region, tribe, allied_to,
                                          -margin, -is_player))

    subdue_candidates.sort(key=lambda x: (x[3], x[4]))
    for region, tribe, _, _, _ in subdue_candidates:
        build_plan["subdue"].append({"region": region, "tribe": tribe})

    # (3) Place Roman Allies
    avail_allies = get_available(state, ROMANS, ALLY)
    ally_candidates = []
    for region in playable:
        if region in exclude:
            continue
        tribes = get_tribes_in_region(region, scenario)
        for tribe in tribes:
            tribe_info = state["tribes"].get(tribe, {})
            if (tribe_info.get("allied_faction") is None
                    and tribe_info.get("status") is None):
                ally_candidates.append((region, tribe))

    for region, tribe in ally_candidates[:avail_allies]:
        build_plan["allies"].append({"region": region, "tribe": tribe})

    return build_plan


def node_r_scout(state):
    """R_SCOUT: Scout per Command.

    Per §8.8.1:
    (1) Move Auxilia to keep/get 4 with Caesar.
    (2) Move Auxilia to add Supply Lines.
    (3) Move Auxilia from no-Legion regions to join Legions.
    (4) Scout Hidden Warbands first; if Frost, German first.

    Ariovistus (A8.8.1): Ignore Frost priority on Germanic Warbands.

    Returns:
        Scout action details dict.
    """
    scenario = state["scenario"]

    scout_plan = {
        "auxilia_moves": [],
        "scout_targets": [],
    }

    # Step 1: Ensure 4 Auxilia with Caesar — §8.8.1
    caesar_region = _caesar_region(state)
    if caesar_region:
        auxilia_with_caesar = count_pieces(
            state, caesar_region, ROMANS, AUXILIA)
        if auxilia_with_caesar < 4:
            scout_plan["auxilia_moves"].append({
                "to": caesar_region,
                "needed": 4 - auxilia_with_caesar,
                "reason": "Caesar escort",
            })

    # Step 2: Scout targets — Hidden first, then Revealed
    playable = get_playable_regions(scenario, state.get("capabilities"))
    for region in playable:
        for enemy in FACTIONS:
            if enemy == ROMANS:
                continue
            hidden_wb = count_pieces_by_state(
                state, region, enemy, WARBAND, HIDDEN)
            revealed_wb = count_pieces_by_state(
                state, region, enemy, WARBAND, REVEALED)

            if hidden_wb > 0 or revealed_wb > 0:
                # Frost priority: German Warbands first (base game only)
                is_german = enemy == GERMANS
                frost_priority = (is_frost_active(state) and is_german
                                  and scenario not in ARIOVISTUS_SCENARIOS)
                scout_plan["scout_targets"].append({
                    "region": region,
                    "enemy": enemy,
                    "hidden": hidden_wb,
                    "revealed": revealed_wb,
                    "frost_priority": frost_priority,
                })

    # Sort: Frost-priority German first (base only), then Hidden count
    scout_plan["scout_targets"].sort(
        key=lambda x: (-x["frost_priority"], -x["hidden"], -x["revealed"]))

    return scout_plan


# ============================================================================
# WINTER NODES
# ============================================================================

def node_r_quarters(state):
    """R_QUARTERS: Quarters Phase.

    Per §8.8.7:
    - 1 Auxilia stays per Fort & Roman Ally.
    - All others (including Leader) move to Provincia if able,
      including via adjacent Supply Line regions.
    - Pay to avoid rolls: at Roman Allies first, then no Devastation,
      Devastated last.

    Returns:
        Quarters action details dict.
    """
    scenario = state["scenario"]
    playable = get_playable_regions(scenario, state.get("capabilities"))

    quarters_plan = {
        "stay_auxilia": [],     # (region, count) — 1 per Fort & Ally
        "move_to_provincia": [],  # regions whose forces should move
        "pay_order": [],        # regions to pay for, in priority order
    }

    for region in playable:
        if count_pieces(state, region, ROMANS) == 0:
            continue

        # Count pieces that stay: 1 Auxilia per Fort, 1 per Roman Ally
        forts = count_pieces(state, region, ROMANS, FORT)
        roman_allies_in_region = 0
        tribes = get_tribes_in_region(region, scenario)
        for tribe in tribes:
            t_info = state["tribes"].get(tribe, {})
            if t_info.get("allied_faction") == ROMANS:
                roman_allies_in_region += 1

        stay_count = forts + roman_allies_in_region
        if stay_count > 0:
            quarters_plan["stay_auxilia"].append((region, stay_count))

        # Remaining pieces move to Provincia
        if region != PROVINCIA:
            quarters_plan["move_to_provincia"].append(region)

    # Pay order: Roman Allies first, then non-Devastated, Devastated last
    for region in playable:
        if count_pieces(state, region, ROMANS) == 0:
            continue
        has_roman_ally = False
        tribes = get_tribes_in_region(region, scenario)
        for tribe in tribes:
            t_info = state["tribes"].get(tribe, {})
            if t_info.get("allied_faction") == ROMANS:
                has_roman_ally = True
                break
        is_devastated = state["spaces"].get(region, {}).get("devastated", False)
        # Priority: (0=ally, 1=no devas, 2=devastated)
        if has_roman_ally:
            priority = 0
        elif not is_devastated:
            priority = 1
        else:
            priority = 2
        quarters_plan["pay_order"].append((region, priority))

    quarters_plan["pay_order"].sort(key=lambda x: x[1])

    return quarters_plan


def node_r_spring(state):
    """R_SPRING: Spring Phase.

    Per §8.3.2: If Roman Leader off map, place with most Romans.

    Returns:
        Spring action details dict, or None if nothing to do.
    """
    from fs_bot.bots.bot_common import get_leader_placement_region

    caesar_region = _caesar_region(state)
    if caesar_region is not None:
        return None  # Caesar already on map

    # Place Caesar with most Roman pieces
    best_region = get_leader_placement_region(state, ROMANS)
    if best_region:
        return {"place_leader": CAESAR, "region": best_region}
    return None


# ============================================================================
# AGREEMENTS AND DIVICIACUS
# ============================================================================

def node_r_agreements(state, requesting_faction, request_type):
    """R_AGREEMENTS: Agreement decisions.

    Per §8.8.6:
    - Never transfer Resources.
    - Retreat/Supply Line/Quarters: agree only for NP Aedui.
    - Always Harass Vercingetorix.

    Args:
        state: Game state dict.
        requesting_faction: Faction making the request.
        request_type: "supply_line", "retreat", "quarters", "resources".

    Returns:
        True if Romans agree.
    """
    non_players = state.get("non_player_factions", set())

    if request_type == "resources":
        return False  # Never transfer — §8.8.6

    # Agree only for NP Aedui — §8.8.6
    if requesting_faction == AEDUI and AEDUI in non_players:
        return True
    return False


def node_r_diviciacus(state, context):
    """R_DIVICIACUS: Diviciacus Capability handling.

    Per §8.8.8:
    - During Aedui Commands: agree unless Aedui at victory, not if
      Aedui Battling/Raiding Romans.
    - During Roman Commands: use Warbands as Auxilia, but never Recruit them.
    - During Aedui Battle defense: do not agree.
    - During Roman Battle defense: do agree.

    Ariovistus (A8.8.8): For Admagetobriga, NP Romans don't agree to any
    Auxilia use.

    Args:
        state: Game state dict.
        context: Dict with "during": "aedui_command"|"roman_command"|
                 "aedui_defense"|"roman_defense", and optional
                 "aedui_action": "battle"|"raid"|other.

    Returns:
        True if Romans agree to Diviciacus.
    """
    scenario = state["scenario"]

    # A8.8.8: Admagetobriga — never agree
    if (scenario in ARIOVISTUS_SCENARIOS
            and state.get("admagetobriga_active", False)):
        return False

    during = context.get("during", "")

    if during == "aedui_command":
        # Agree unless Aedui at victory — §8.8.8
        if check_victory(state, AEDUI):
            return False
        # Not if Aedui Battling or Raiding Romans
        aedui_action = context.get("aedui_action", "")
        if aedui_action in ("battle", "raid"):
            return False
        return True

    if during == "roman_command":
        # Use Warbands as Auxilia to max degree Aedui agree — §8.8.8
        # But never place by Recruit
        if context.get("is_recruit", False):
            return False
        return True

    if during == "aedui_defense":
        return False  # §8.8.8

    if during == "roman_defense":
        return True  # §8.8.8

    return False


# ============================================================================
# MAIN FLOWCHART DRIVER
# ============================================================================

def execute_roman_turn(state):
    """Walk the Roman bot flowchart and return the chosen action.

    Implements the full decision tree: R1 → R2 → R3 → R4 → R5 and all
    process nodes.

    Args:
        state: Game state dict.

    Returns:
        Action dict describing the Roman bot's decision.
    """
    scenario = state["scenario"]

    # §8.1.2: Upgrade Limited Command from SoP
    if state.get("limited_by_sop", False):
        # NP gets full Command + SA instead
        pass  # The upgrade is implicit — we proceed with full options

    # R1: Caesar or Legion with enemy threat?
    r1_result, threat_regions = node_r1(state)

    if r1_result == "Yes":
        # Try Battle, may redirect to March
        return node_r_battle(state)

    # R2: Enemy at 0+ victory AND Caesar with 2+ Legions, 4+ Auxilia?
    r2_result = node_r2(state)
    if r2_result == "Yes":
        return node_r_march(state)

    # R3: Can play Event by SoP?
    r3_result = node_r3(state)
    if r3_result == "No":
        # Skip to R5 (check Auxilia for March vs Recruit)
        r5_result = node_r5(state)
        if r5_result == "No":
            return node_r_march(state)
        return node_r_recruit(state)

    # R4: Event decline checks
    r4_result = node_r4(state)
    if r4_result == "No":
        # Play the Event
        return node_r_event(state)

    # R5: 9+ Auxilia Available?
    r5_result = node_r5(state)
    if r5_result == "No":
        return node_r_march(state)

    return node_r_recruit(state)
