"""
Shared Non-Player behaviors per §8.1–8.4 and A8.2–A8.4.

Every NP bot imports from here for: Limited Command upgrade, Event decisions,
Dual Use defaults, Place/Remove priority ordering, faction targeting,
Retreat logic, Harassment rules, Frost restrictions, random selection,
and Event location selection.
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    FACTIONS, GALLIC_FACTIONS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    MOBILE_PIECES, FLIPPABLE_PIECES,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Scenarios
    ARIOVISTUS_SCENARIOS,
    # Events
    EVENT_UNSHADED, EVENT_SHADED, CMD_RALLY,
    # NP symbols
    NP_SYMBOL_CARNYX, NP_SYMBOL_LAURELS, NP_SYMBOL_SWORDS,
    # Markers
    MARKER_FROST, MARKER_WINTER,
    # Cities / tribes
    TRIBE_REMI,
    # Victory
    ROMAN_VICTORY_THRESHOLD, ARVERNI_LEGIONS_THRESHOLD,
    ARVERNI_ALLIES_THRESHOLD, BELGAE_VICTORY_THRESHOLD,
    GERMAN_VICTORY_THRESHOLD,
    # Die
    DIE_MIN, DIE_MAX,
)
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, get_leader_in_region,
    find_leader, get_available,
)
from fs_bot.board.control import is_controlled_by, get_controlled_regions
from fs_bot.engine.victory import (
    calculate_victory_score, calculate_victory_margin, check_victory,
)
from fs_bot.map.map_data import (
    get_adjacent, get_playable_regions, get_tribes_in_region,
    is_city_tribe, get_tribe_data, ALL_TRIBE_DATA,
)
from fs_bot.cards.bot_instructions import (
    get_bot_instruction, NO_EVENT, SPECIFIC_INSTRUCTION, PLAY_EVENT,
    CONDITIONAL,
)


def command_region_candidates(state, regions):
    """Apply an Event's action-region scope without changing the physical board.

    Call at regional candidate selection, before priority limits and Available
    pools are consumed. March callers apply it to origins, not destinations.
    Explicitly map-wide objectives continue to query the complete state.
    """
    allowed = state.get("_command_region_scope")
    return [region for region in regions if allowed is None or region in allowed]


def command_sa_allowed(state):
    """An Event grants a Special Ability only when its text permits one."""
    return state.get("_command_with_sa", True)


def estimate_scoped_rally(state, faction, planner):
    """Measure a restricted/free Rally through its actual planner and executor.

    Entry conditions must reflect legal placement caps, one option per Region,
    available pieces, and free costs. Use detached state so estimates neither
    spend tie-break rolls nor ask player reactions or perform a Special Ability.
    """
    from copy import deepcopy
    from fs_bot.engine.execute import _execute_rally
    sim = deepcopy({k: v for k, v in state.items() if k != "decision_agent"})
    sim["_command_with_sa"] = False
    result = {"citadels": 0, "allies": 0, "warbands": 0,
              "total": 0, "adds_control": False}
    action = planner(sim)
    if action.get("command") != CMD_RALLY:
        return result
    before_warbands = get_available(sim, faction, WARBAND)
    before_control = set(get_controlled_regions(sim, faction))
    execution = _execute_rally(sim, faction, action)
    if execution.get("errors"):
        raise ValueError(f"Rally planner produced an invalid scoped plan: {execution['errors']}")
    for placement in execution.get("placements", []):
        if placement["action"] == "place_citadel":
            result["citadels"] += 1
        elif placement["action"] == "place_ally":
            result["allies"] += 1
    result["warbands"] = before_warbands - get_available(sim, faction, WARBAND)
    result["total"] = sum(result[key] for key in ("citadels", "allies", "warbands"))
    result["adds_control"] = bool(set(get_controlled_regions(sim, faction)) - before_control)
    return result


def command_is_allowed(state, command):
    """Whether a granted Command permits this flowchart branch (§8.2.3)."""
    return command not in state.get("_command_exclusions", ())


# ============================================================================
# §8.1.2 — Limited Command Upgrade
# ============================================================================

def upgrade_limited_command(is_limited_by_sop):
    """NPs entitled to Limited Command by SoP get full Command + SA instead.

    Per §8.1.2: "When a 2nd Eligible Non-Player by the Sequence of Play is
    to execute a Limited Command (2.3.4-.5), the Non-player instead receives
    a full Command plus a Special Ability option."

    NOTE: A Limited Command imposed by Event (e.g. Druids) stays Limited.

    Args:
        is_limited_by_sop: True if the limitation comes from Sequence of Play.

    Returns:
        True if the NP should get a full Command + SA (i.e. upgrade applies).
    """
    return is_limited_by_sop


# ============================================================================
# §8.2.2 / A8.2.2 — Dual Use Event Preference
# ============================================================================

def get_dual_use_preference(faction, scenario, card_id=None):
    """Which Event text a NP faction uses for Dual Use cards.

    Per §8.2.2 / A8.2.2: Romans/Aedui → unshaded; Belgae/Arverni → shaded.
    In Ariovistus: Germans → shaded (A8.2.2).

    Args:
        faction: Faction constant.
        scenario: Scenario constant.

    Returns:
        EVENT_UNSHADED or EVENT_SHADED.
    """
    # Aedui specific instructions override the generic §8.2.2 side in
    # either ruleset. The scenario's instruction table distinguishes shared
    # cards from replacements such as Winter Campaign (63/A63).
    if faction == AEDUI and card_id is not None:
        instruction = get_event_instruction(card_id, faction, scenario)
        if instruction and (instruction.instruction or "").startswith("Use shaded text"):
            return EVENT_SHADED
    if faction in (ROMANS, AEDUI):
        return EVENT_UNSHADED
    if faction in (BELGAE, ARVERNI):
        return EVENT_SHADED
    # Germans — shaded in Ariovistus (A8.2.2); base game Germans are not
    # a bot faction so this shouldn't be called, but default to shaded.
    if faction == GERMANS:
        return EVENT_SHADED
    raise ValueError(f"Unknown faction for Dual Use: {faction}")


# ============================================================================
# §8.1.1 — Event Decision Checks
# ============================================================================

def is_no_faction_event(card_id, faction, scenario):
    """Check if a card is a 'No [Faction]' event (Swords symbol).

    Per §8.1.1: Cards listed at the bottom of each NP flowchart as
    "No [Faction]" are declined.

    Args:
        card_id: Card identifier (int or str).
        faction: Faction constant.
        scenario: Scenario constant.

    Returns:
        True if the NP should decline this Event.
    """
    try:
        instr = get_bot_instruction(card_id, faction, scenario)
    except KeyError:
        return False
    return instr.action == NO_EVENT


def is_final_year_capability(state, card_id):
    """Check if a card adds a Capability during the game's final year.

    Per §8.1.1: NPs decline "Capabilities (5.3) during the last year of
    the game (when the next Winter will be final)."

    Args:
        state: Game state dict.
        card_id: Card identifier.

    Returns:
        True if this is a Capability card and it's the final year.
    """
    from fs_bot.rules_consts import CAPABILITY_CARDS, CAPABILITY_CARDS_ARIOVISTUS
    is_capability = (card_id in CAPABILITY_CARDS
                     or card_id in CAPABILITY_CARDS_ARIOVISTUS)
    if not is_capability:
        return False
    return state.get("final_year", False)


def mons_cevenna_cannot_affect_theatre(state, faction):
    """Card 9: a definite empty-theatre case, not a general action forecast.

    Germans, Aedui and Belgae have no Rally home in Provincia/Sequani/Arverni.
    Their other Commands need pieces there. Static pieces are retained as
    potential Rally/SA bases. Also retain Belgic cases with German Warbands
    that could be used through the card's SA-first Enlist allowance.
    With no Roman mobile force, their scoped full flowchart must still
    provide a follow-on Command (including a possible Build); a terminal
    Pass makes the whole Event ineffective. Preserve Arverni home Rally.
    """
    from fs_bot.rules_consts import PROVINCIA, SEQUANI, ARVERNI_REGION
    theatre = (PROVINCIA, SEQUANI, ARVERNI_REGION)
    if faction == ROMANS:
        if any(count_pieces(state, region, ROMANS, piece)
               for region in theatre for piece in MOBILE_PIECES):
            return False
        from fs_bot.engine.execute import _free_command_planning_state
        from fs_bot.bots.roman_bot import execute_roman_turn, ACTION_PASS
        planning = _free_command_planning_state(
            state, ROMANS, theatre, with_sa=True)
        return execute_roman_turn(planning).get("command") == ACTION_PASS
    if faction not in (GERMANS, AEDUI, BELGAE):
        return False
    if any(count_pieces(state, r, faction) for r in theatre):
        return False
    if faction == BELGAE and any(count_pieces(state, r, GERMANS, WARBAND)
                                 for r in theatre):
        return False
    return True


def sabis_has_qualifying_battle(state, faction):
    """A57 needs a Battle in Belgica to have any effect (§8.1.1).

    Reuse the execution selector so the Belgic Legion-Loss requirement and
    the German Ariovistus Warband floor also govern Event selection.
    """
    from fs_bot.engine.execute import _choose_free_battle
    from fs_bot.rules_consts import BELGICA_REGIONS
    region, _ = _choose_free_battle(state, faction, set(BELGICA_REGIONS))
    return region is not None


def aedui_cannot_reach_arduenna(state):
    """Arduenna is ineffective with no Aedui presence or adjacent mobile force.

    Cards 67/A67 grant March into Nervii/Treveri and a non-March Command
    there. Aedui March is one Region (§3.3.2), and neither target is their
    Home Rally Region. Retain any static presence: it can enable Rally.
    """
    from fs_bot.rules_consts import NERVII, TREVERI
    from fs_bot.map.map_data import get_adjacent_for_state
    targets = (NERVII, TREVERI)
    if any(count_pieces(state, region, AEDUI) for region in targets):
        return False
    origins = {origin for target in targets
               for origin in get_adjacent_for_state(state, target, AEDUI)}
    return not any(count_pieces(state, origin, AEDUI, piece)
                   for origin in origins for piece in MOBILE_PIECES)


def should_decline_event(state, card_id, faction):
    """Combined check: should a NP decline the current Event?

    Per §8.1.1: Decline if Ineffective, final-year Capability, or
    "No [Faction]". Ineffectiveness is evaluated against the current board
    via event_eval.is_event_effective (for the side the Faction would use:
    Romans/Aedui unshaded, Arverni/Belgae/Germans shaded — §8.2.2).

    Args:
        state: Game state dict.
        card_id: Card identifier.
        faction: Faction constant.

    Returns:
        True if the NP should decline this Event for a structural reason.
    """
    scenario = state["scenario"]

    # "No [Faction]" cards — §8.1.1
    if is_no_faction_event(card_id, faction, scenario):
        return True

    # Both supplied Aedui instruction tables make Remi Influence
    # conditional on Remi already being their Ally.
    if card_id == 68 and faction == AEDUI:
        instruction = get_event_instruction(card_id, faction, scenario)
        if (instruction
                and "if Remi are not an Aedui Ally" in (instruction.instruction or "")
                and state["tribes"].get(TRIBE_REMI, {}).get("allied_faction") != AEDUI):
            return True

    # War Fleet grants no Special Ability. Romans/Aedui have no Home Rally
    # in its theatre, so with no own pieces there neither movement nor the
    # follow-on Command can have an effect (§8.1.1; Card 62).
    if card_id == 62 and faction in (ROMANS, AEDUI):
        from fs_bot.rules_consts import ARVERNI_REGION, PICTONES, BRITANNIA
        theatre = {ARVERNI_REGION, PICTONES, BRITANNIA,
                   *get_adjacent(BRITANNIA, scenario)}
        if not any(count_pieces(state, r, faction)
                   for r in theatre if r in state["spaces"]):
            return True

    # Arverni Assembly of Gaul instruction: decline unless they qualify.
    # The shaded benefit belongs to the physical Carnutes controller.
    if card_id == 52 and faction == ARVERNI:
        from fs_bot.rules_consts import CARNUTES
        if not is_controlled_by(state, CARNUTES, ARVERNI):
            return True

    # Both expansion instruction tables make Kinship unavailable when
    # the opposite side is Non-player, regardless of the chosen card side.
    if card_id == "A65" and scenario in ARIOVISTUS_SCENARIOS:
        if (faction == BELGAE and GERMANS in state.get("non_player_factions", set())
                or faction == GERMANS and BELGAE in state.get("non_player_factions", set())):
            return True

    # Capability in final year — §8.1.1
    if is_final_year_capability(state, card_id):
        return True

    if card_id == 9 and mons_cevenna_cannot_affect_theatre(state, faction):
        return True
    if card_id == "A57" and not sabis_has_qualifying_battle(state, faction):
        return True
    if card_id in (67, "A67") and faction == AEDUI and aedui_cannot_reach_arduenna(state):
        return True

    # Ineffective Event — §8.1.1 (no effect, or merely Revealing own pieces).
    from fs_bot.cards.event_eval import is_event_effective
    shaded = get_dual_use_preference(faction, scenario, card_id) == EVENT_SHADED
    from fs_bot.cards.event_conditions import np_event_available
    if np_event_available(state, card_id, faction, shaded) is False:
        return True
    if not is_event_effective(state, card_id, shaded):
        return True

    return False


def get_event_instruction(card_id, faction, scenario):
    """Get the bot instruction for a card/faction, if any.

    Wraps bot_instructions.get_bot_instruction with a safe fallback.

    Returns:
        BotInstruction or None.
    """
    try:
        return get_bot_instruction(card_id, faction, scenario)
    except KeyError:
        return None


# ============================================================================
# §8.3.4 — Random Selection
# ============================================================================

def random_select(state, candidates):
    """Select one candidate from equal-priority options using state RNG.

    Per §8.3.4: "whenever equal candidate Regions, Tribes, or target
    Factions are offered to a Non-player, select using an equal-chance
    die roll."

    Args:
        state: Game state dict (must have state["rng"]).
        candidates: Sequence of candidates (must be non-empty).

    Returns:
        One selected candidate.

    Raises:
        ValueError: If candidates is empty.
    """
    if not candidates:
        raise ValueError("Cannot random_select from empty candidates")
    if len(candidates) == 1:
        return candidates[0]
    # Use state["rng"] for deterministic replay — CLAUDE.md Determinism rule
    idx = state["rng"].randint(0, len(candidates) - 1)
    return candidates[idx]


def random_select_multiple(state, candidates, count):
    """Select count candidates without replacement using state RNG.

    Args:
        state: Game state dict.
        candidates: Sequence of candidates.
        count: How many to select (capped at len(candidates)).

    Returns:
        List of selected candidates.
    """
    candidates = list(candidates)
    count = min(count, len(candidates))
    if count <= 0:
        return []
    selected = []
    remaining = list(candidates)
    for _ in range(count):
        idx = state["rng"].randint(0, len(remaining) - 1)
        selected.append(remaining.pop(idx))
    return selected


def roll_die(state):
    """Roll a single d6 using the state RNG.

    Args:
        state: Game state dict.

    Returns:
        Integer 1-6.
    """
    return state["rng"].randint(DIE_MIN, DIE_MAX)


# ============================================================================
# §8.4.4 — Frost Restriction
# ============================================================================

def is_frost_active(state):
    """Check if Frost (Winter card showing) restricts NP actions.

    Per §8.4.4 / 2.3.8: "While a Winter card is showing..."

    Args:
        state: Game state dict.

    Returns:
        True if a Winter card is currently showing (Frost is in effect).
    """
    return state.get("frost", False)


def would_advance_player_victory(state, faction, player_faction):
    """Check if an action by NP faction could advance a player faction's victory.

    Per §8.4.4: "Non-players take no action that could directly advance
    any player Faction above or any further beyond its victory threshold."

    This is a predicate for the calling code to check before each candidate
    action. The caller must determine what "directly advance" means for
    the specific action.

    Args:
        state: Game state dict.
        faction: The NP faction considering an action.
        player_faction: The player faction that might be advanced.

    Returns:
        True if the player faction is at or above its victory threshold.
    """
    scenario = state["scenario"]
    non_players = state.get("non_player_factions", set())

    # Only restricts advancement of PLAYER factions — §8.4.4 NOTE
    if player_faction in non_players:
        return False

    # Check if the player faction tracks victory in this scenario
    try:
        return check_victory(state, player_faction)
    except Exception:
        return False


def check_frost_restriction(state, player_faction):
    """Should a NP skip an action due to Frost?

    Combines the Frost-active check with the player-at-victory check.
    If Frost is active AND the action would advance a player faction
    that is at or beyond its threshold, return True (skip).

    Args:
        state: Game state dict.
        player_faction: The player faction that might benefit.

    Returns:
        True if the action should be skipped due to Frost.
    """
    if not is_frost_active(state):
        return False
    return would_advance_player_victory(state, None, player_faction)


# ============================================================================
# §8.4.1 — Place and Remove Priority Ordering
# ============================================================================

# Enemy piece targeting order (top = highest priority to target)
# Per §8.4.1: Leaders → Legions → Citadels/Forts → Allies (Cities first)
#             → Warbands/Auxilia (Hidden → Revealed → Scouted)
# Ariovistus adds Settlements alongside Citadels/Forts — A8.4.1

_ENEMY_TARGET_ORDER_BASE = (
    LEADER,
    LEGION,
    CITADEL,   # Citadels/Forts at same tier
    FORT,
    ALLY,      # Cities first handled by caller
    # Warbands/Auxilia: Hidden → Revealed → Scouted handled separately
)

_ENEMY_TARGET_ORDER_ARIOVISTUS = (
    LEADER,
    LEGION,
    SETTLEMENT,  # Alongside Citadels/Forts — A8.4.1
    CITADEL,
    FORT,
    ALLY,        # Cities or Remi first — A8.4.1
)


def get_enemy_piece_target_order(scenario):
    """Get the priority order for targeting enemy pieces.

    Per §8.4.1: target Leaders first, then Legions, then Citadels/Forts,
    then Allies (Cities first), then Warbands/Auxilia (Hidden first).
    Ariovistus: Settlements alongside Citadels/Forts; "Cities or Remi first".

    Returns a tuple of piece types in priority order. Flippable pieces
    (Warbands/Auxilia) are NOT in this list — they are handled separately
    with state ordering (Hidden → Revealed → Scouted).

    Args:
        scenario: Scenario constant.

    Returns:
        Tuple of piece type constants.
    """
    if scenario in ARIOVISTUS_SCENARIOS:
        return _ENEMY_TARGET_ORDER_ARIOVISTUS
    return _ENEMY_TARGET_ORDER_BASE


def get_own_loss_order(scenario):
    """Get the priority order for taking own Losses (reverse of placement).

    Per §8.4.1: "take Losses on or remove own pieces in the reverse order."
    So: Scouted/Revealed/Hidden Warbands/Auxilia first → Allies → Forts →
    Citadels → Legions → Leaders last.

    Returns a tuple of piece types in removal priority order (first = remove
    first). Flippable piece state ordering is Scouted → Revealed → Hidden.

    Args:
        scenario: Scenario constant.

    Returns:
        Tuple of piece type constants (excluding flippable — handled separately).
    """
    if scenario in ARIOVISTUS_SCENARIOS:
        # Reverse of _ENEMY_TARGET_ORDER_ARIOVISTUS
        return (ALLY, FORT, CITADEL, SETTLEMENT, LEGION, LEADER)
    return (ALLY, FORT, CITADEL, LEGION, LEADER)


def get_flippable_target_order():
    """State ordering for targeting enemy flippable pieces.

    Per §8.4.1: "Hidden before Revealed before Scouted enemy Warbands
    or Auxilia."

    Returns:
        Tuple of (piece_state, piece_type) pairs in priority order.
    """
    result = []
    for piece_state in (HIDDEN, REVEALED, SCOUTED):
        for piece_type in (WARBAND, AUXILIA):
            result.append((piece_state, piece_type))
    return tuple(result)


def get_own_flippable_loss_order():
    """State ordering for own flippable piece losses (reverse of targeting).

    Per §8.4.1: own losses reverse → Scouted before Revealed before Hidden.

    Returns:
        Tuple of (piece_state, piece_type) pairs in loss priority order.
    """
    result = []
    for piece_state in (SCOUTED, REVEALED, HIDDEN):
        for piece_type in (WARBAND, AUXILIA):
            result.append((piece_state, piece_type))
    return tuple(result)


def is_ally_in_city_or_remi(tribe_name, scenario):
    """Check if a tribe is in a City or is the Remi tribe.

    Both §8.4.1 and A8.4.1 prioritize Allies in Cities or at Remi.

    Args:
        tribe_name: Tribe constant.
        scenario: Scenario constant.

    Returns:
        True if the tribe is in a City or is Remi.
    """
    if is_city_tribe(tribe_name):
        return True
    if tribe_name == TRIBE_REMI:
        return True
    return False


# ============================================================================
# §8.4.1 — Faction Targeting Order
# ============================================================================

# Base game targeting — §8.4.1
_TARGETING_BASE = {
    # Belgae/Arverni target: Romans → Aedui → each other → Germans
    BELGAE:  (ROMANS, AEDUI, ARVERNI, GERMANS),
    ARVERNI: (ROMANS, AEDUI, BELGAE, GERMANS),
    # Romans/Aedui target: Arverni → Belgae → Germans → each other
    ROMANS:  (ARVERNI, BELGAE, GERMANS, AEDUI),
    AEDUI:   (ARVERNI, BELGAE, GERMANS, ROMANS),
}

# Ariovistus targeting — A8.4: swap "Arverni" ↔ "Germans"
_TARGETING_ARIOVISTUS = {
    # Belgae/Germans target: Romans → Aedui → each other → Arverni
    BELGAE:  (ROMANS, AEDUI, GERMANS, ARVERNI),
    GERMANS: (ROMANS, AEDUI, BELGAE, ARVERNI),
    # Romans/Aedui target: Germans → Belgae → Arverni → each other
    ROMANS:  (GERMANS, BELGAE, ARVERNI, AEDUI),
    AEDUI:   (GERMANS, BELGAE, ARVERNI, ROMANS),
}


def get_faction_targeting_order(faction, scenario):
    """Get the priority order for targeting enemy factions.

    Per §8.4.1:
    - Base: Belgae/Arverni → Romans, Aedui, each other, Germans.
            Romans/Aedui → Arverni, Belgae, Germans, each other.
    - Ariovistus (A8.4): swap Arverni ↔ Germans in all references.

    Args:
        faction: The NP faction doing the targeting.
        scenario: Scenario constant.

    Returns:
        Tuple of faction constants in targeting priority order.
    """
    if scenario in ARIOVISTUS_SCENARIOS:
        targeting = _TARGETING_ARIOVISTUS
    else:
        targeting = _TARGETING_BASE

    if faction in targeting:
        return targeting[faction]

    # Arverni in Ariovistus is game-run (not a bot), shouldn't be called.
    # Germans in base game is not a bot, shouldn't be called.
    # Return a default that excludes self.
    return tuple(f for f in FACTIONS if f != faction)


# ============================================================================
# §8.4.2 — Harassment Rules
# ============================================================================

def get_harassing_factions(faction_marching, scenario):
    """Which NP factions harass a given faction's March or Seize?

    Per §8.4.2:
    - Base: Belgae and Arverni harass Roman March and Seize.
            Aedui and Romans harass Vercingetorix March.
    - Ariovistus (A8.4.2): Belgae and Germans harass Roman March and Seize.
            No Vercingetorix harassment (he's not in play).

    Args:
        faction_marching: Faction performing March or Seize.
        scenario: Scenario constant.

    Returns:
        Tuple of NP faction constants that will harass.
    """
    if scenario in ARIOVISTUS_SCENARIOS:
        # A8.4.2: Belgae and Germans harass Roman March/Seize
        if faction_marching == ROMANS:
            return (BELGAE, GERMANS)
        # No Vercingetorix in Ariovistus, so no other harassment
        return ()
    else:
        # Base: Belgae/Arverni harass Roman March/Seize
        if faction_marching == ROMANS:
            return (BELGAE, ARVERNI)
        # Aedui/Romans harass Vercingetorix March (handled by caller
        # checking if Vercingetorix is in the marching group)
        return ()


def get_vercingetorix_harassers(scenario):
    """Which NP factions harass Vercingetorix March?

    Per §8.4.2: Aedui and Romans harass Vercingetorix March.
    Only in base game — Vercingetorix not in Ariovistus.

    Args:
        scenario: Scenario constant.

    Returns:
        Tuple of NP faction constants, or empty tuple if Ariovistus.
    """
    if scenario in ARIOVISTUS_SCENARIOS:
        return ()
    return (AEDUI, ROMANS)


def np_will_harass(np_faction, target_faction, scenario, *, vercingetorix_marching=False):
    """Will a specific NP faction harass a specific action?

    Args:
        np_faction: The NP faction that might harass.
        target_faction: The faction being harassed (March/Seize).
        scenario: Scenario constant.
        vercingetorix_marching: True if Vercingetorix is in the March group.

    Returns:
        True if the NP faction will harass.
    """
    if scenario in ARIOVISTUS_SCENARIOS:
        # Belgae/Germans harass Roman March/Seize
        if target_faction == ROMANS and np_faction in (BELGAE, GERMANS):
            return True
        return False
    else:
        # Belgae/Arverni harass Roman March/Seize
        if target_faction == ROMANS and np_faction in (BELGAE, ARVERNI):
            return True
        # Aedui/Romans harass Vercingetorix March
        if vercingetorix_marching and np_faction in (AEDUI, ROMANS):
            return True
        return False


# ============================================================================
# §8.4.3 — Non-Player Retreat
# ============================================================================

def should_retreat(state, faction, region, attacker,
                   own_losses, enemy_losses, *,
                   last_piece_threatened=False,
                   legion_loss_rolls=0,
                   has_fort_or_citadel=False,
                   retreat_removes_pieces=False):
    """Determine if a NP defender should Retreat from Battle.

    Per §8.4.3, NPs Retreat:
    1. When needed to save their last Defending piece.
    2. If Roman, to lower forced Loss rolls against Legions.
    3. If no Fort/Citadel AND Retreat won't remove pieces AND
       they'd inflict < 1/2 the Losses they'd suffer.

    Args:
        state: Game state dict.
        faction: Defending NP faction.
        region: Battle region.
        attacker: Attacking faction.
        own_losses: Number of Losses the NP would suffer (die rolls + removals).
        enemy_losses: Number of Losses the NP would inflict on attacker.
        last_piece_threatened: True if the last defending piece would be lost.
        legion_loss_rolls: Number of forced Loss rolls against Legions (Roman only).
        has_fort_or_citadel: True if defender has a Fort or Citadel in region.
        retreat_removes_pieces: True if Retreating itself would remove pieces.

    Returns:
        True if the NP should Retreat.
    """
    # (1) Save last piece — §8.4.3
    if last_piece_threatened:
        return True

    # (2) Roman: reduce Legion Loss rolls — §8.4.3
    if faction == ROMANS and legion_loss_rolls > 0:
        return True

    # (3) No Fort/Citadel AND safe Retreat AND inflict < 1/2 Losses — §8.4.3
    if (not has_fort_or_citadel
            and not retreat_removes_pieces
            and own_losses > 0
            and enemy_losses < own_losses / 2):
        return True

    return False


def get_retreat_preferences(state, faction, region, scenario):
    """Determine where retreating pieces go.

    Per §8.4.3:
    - Warbands stay in place when able.
    - Leaders join most friendly pieces (in place or adjacent).

    Args:
        state: Game state dict.
        faction: Retreating NP faction.
        region: Battle region.
        scenario: Scenario constant.

    Returns:
        Dict with keys:
        - "warbands_stay": True (Gauls leave Hidden Warbands vs Romans)
        - "leader_destination": region with most own pieces, or None
    """
    result = {
        "warbands_stay": True,
        "leader_destination": None,
    }

    # Find region with most own pieces for Leader — §8.4.3
    leader = get_leader_in_region(state, region, faction)
    if leader is not None:
        adjacent = get_adjacent(region, scenario)
        best_region = None
        best_count = -1

        # Consider staying in place
        own_count = count_pieces(state, region, faction)
        # Subtract leader itself from count
        if own_count > 0:
            own_count -= 1
        if own_count > best_count:
            best_count = own_count
            best_region = region

        # Consider adjacent regions
        for adj_region in adjacent:
            adj_count = count_pieces(state, adj_region, faction)
            if adj_count > best_count:
                best_count = adj_count
                best_region = adj_region

        result["leader_destination"] = best_region

    return result


# ============================================================================
# §8.3.1 — Event Location Selection
# ============================================================================

def rank_regions_for_event_placement(state, regions, scenario):
    """Rank regions for Event piece placement/removal.

    Per §8.3.1: "select Event Regions and Tribes to benefit themselves first;
    then to ensure that Event text 'places' the most own or 'removes' or
    'replaces' the most enemy Legions, then Citadels, then Allies, then
    other pieces possible."

    Ariovistus (A8.3.1): "Settlements receive an equal priority as Citadels."

    Args:
        state: Game state dict.
        regions: Iterable of candidate region constants.
        scenario: Scenario constant.

    Returns:
        List of regions sorted by priority (highest first).
    """
    def _score(region):
        # Count Legions (all factions)
        legions = count_pieces(state, region, piece_type=LEGION)
        # Count Citadels (all factions) + Settlements in Ariovistus
        citadels = count_pieces(state, region, piece_type=CITADEL)
        if scenario in ARIOVISTUS_SCENARIOS:
            citadels += count_pieces(state, region, piece_type=SETTLEMENT)
        # Count Allies (all factions)
        allies = count_pieces(state, region, piece_type=ALLY)
        # Count other pieces
        total = count_pieces(state, region)
        other = total - legions - citadels - allies
        # Lexicographic comparison: most Legions, then Citadels(/Settlements),
        # then Allies, then other
        return (legions, citadels, allies, other)

    return sorted(regions, key=_score, reverse=True)


# ============================================================================
# §8.3.2 — Placing Leaders
# ============================================================================

def get_leader_placement_region(state, faction):
    """Where to place a Leader when it enters/re-enters play.

    Per §8.3.2: "Place Leaders as soon as able where the most own pieces."

    Args:
        state: Game state dict.
        faction: Faction constant.

    Returns:
        Region with the most own pieces, or None if no valid region.
    """
    scenario = state["scenario"]
    playable = get_playable_regions(scenario,
                                   state.get("capabilities"))
    best_region = None
    best_count = -1

    for region in playable:
        own = count_pieces(state, region, faction)
        if own > best_count:
            best_count = own
            best_region = region

    return best_region


# ============================================================================
# §8.4.1 — Move pieces to keep Leader with 4 Warbands/Auxilia
# ============================================================================

def leader_escort_needed(state, faction, scenario):
    """Check if a faction's Leader needs more escort pieces.

    Per §8.4.1: "As they are able, move their own pieces to end the move
    with at least four of their own Warbands or Auxilia in the same Region
    as their Leader."

    Args:
        state: Game state dict.
        faction: Faction constant.
        scenario: Scenario constant.

    Returns:
        (leader_region, shortfall) — region where Leader is, and how many
        more Warbands/Auxilia are needed. Returns (None, 0) if no Leader
        on map or already has enough.
    """
    leader_region = find_leader(state, faction)
    if leader_region is None:
        return (None, 0)

    # Count own Warbands + Auxilia with Leader
    escort_count = 0
    if faction == ROMANS:
        escort_count = count_pieces(state, leader_region, faction, AUXILIA)
    else:
        escort_count = count_pieces(state, leader_region, faction, WARBAND)
        if faction == AEDUI:
            escort_count += count_pieces(state, leader_region, faction, AUXILIA)

    target = 4
    shortfall = max(0, target - escort_count)
    return (leader_region, shortfall)


# ============================================================================
# §8.4.2 — Resource Transfer / Supply Line Agreement
# ============================================================================

def np_agrees_to_supply_line(np_faction, requesting_faction, state):
    """Check if a NP faction agrees to let another use its Controlled region
    for a Supply Line.

    Per §8.4.2: Most NPs refuse. Aedui/Romans might for each other
    (detailed in §8.6.6, §8.8.6).

    Args:
        np_faction: The NP faction controlling the region.
        requesting_faction: The faction requesting the Supply Line.
        state: Game state dict.

    Returns:
        True if the NP agrees.
    """
    scenario = state["scenario"]
    non_players = state.get("non_player_factions", set())

    # §8.8.6: NP Romans agree only for NP Aedui
    if np_faction == ROMANS:
        if requesting_faction == AEDUI and AEDUI in non_players:
            return True
        return False

    # §8.6.6: NP Aedui agree for Romans under conditions
    if np_faction == AEDUI:
        if requesting_faction != ROMANS:
            return False
        # NP Romans always get agreement — §8.6.6
        if ROMANS in non_players:
            return True
        # Player Romans: agree if victory score < 10 — §8.6.6
        try:
            roman_score = calculate_victory_score(state, ROMANS)
            if roman_score < 10:
                return True
            # Score 10-12: agree on die roll 1-4 — §8.6.6
            if roman_score <= 12:
                return roll_die(state) <= 4
            # Score > 12: refuse — §8.6.6 NOTE
            return False
        except Exception:
            return False

    # All other NP factions refuse — §8.4.2
    return False


def np_agrees_to_retreat(np_faction, retreating_faction, state):
    """Check if a NP faction agrees to let another Retreat into its Control.

    Per §8.4.2: Most refuse. Romans for NP Aedui, Aedui for Romans
    under conditions.

    Args:
        np_faction: The NP faction controlling the retreat destination.
        retreating_faction: The faction retreating.
        state: Game state dict.

    Returns:
        True if the NP agrees.
    """
    # Same logic as Supply Line agreement — §8.4.2, §8.6.6, §8.8.6
    return np_agrees_to_supply_line(np_faction, retreating_faction, state)


# ============================================================================
# HELPERS — Counting and board queries for bot use
# ============================================================================

def count_faction_allies_and_citadels(state, faction):
    """Count total Allies + Citadels for a faction on the map.

    Useful for victory comparisons in bot targeting.

    Args:
        state: Game state dict.
        faction: Faction constant.

    Returns:
        Integer count.
    """
    from fs_bot.board.pieces import count_on_map
    from fs_bot.board.pieces import count_allied_discs
    allies = count_allied_discs(state, faction)
    citadels = count_on_map(state, faction, CITADEL)
    return allies + citadels


def get_enemy_factions(faction, scenario):
    """Get all enemy factions for a given faction in a scenario.

    Returns factions in targeting priority order.

    Args:
        faction: Faction constant.
        scenario: Scenario constant.

    Returns:
        Tuple of enemy faction constants.
    """
    return get_faction_targeting_order(faction, scenario)


def has_enemy_threat_in_region(state, region, faction, scenario):
    """Check if a region has enemy pieces that constitute a "threat".

    Used by Battle/March conditions. An enemy threat exists if any Gaul
    or Germans have an Ally, Citadel, Leader, or Control in the region.

    Args:
        state: Game state dict.
        region: Region constant.
        faction: The NP faction checking for threats (to determine enemies).
        scenario: Scenario constant.

    Returns:
        True if the region has enemy threats.
    """
    enemies = get_faction_targeting_order(faction, scenario)
    for enemy in enemies:
        # Ally
        if count_pieces(state, region, enemy, ALLY) > 0:
            return True
        # Citadel
        if count_pieces(state, region, enemy, CITADEL) > 0:
            return True
        # Settlement (Ariovistus) — counted as Allies per A8.8.1
        if (scenario in ARIOVISTUS_SCENARIOS
                and count_pieces(state, region, enemy, SETTLEMENT) > 0):
            return True
        # Leader
        if get_leader_in_region(state, region, enemy) is not None:
            return True
        # Control
        if is_controlled_by(state, region, enemy):
            return True
    return False


def count_mobile_pieces(state, region, faction):
    """Count mobile pieces (Leader, Legions, Auxilia, Warbands) for a faction.

    Args:
        state: Game state dict.
        region: Region constant.
        faction: Faction constant.

    Returns:
        Integer count.
    """
    total = 0
    if get_leader_in_region(state, region, faction) is not None:
        total += 1
    total += count_pieces(state, region, faction, LEGION)
    total += count_pieces(state, region, faction, AUXILIA)
    total += count_pieces(state, region, faction, WARBAND)
    return total


class _AllRemovalsRng:
    """A deterministic RNG stand-in whose rolls always force a removal — used
    only for NP Battle PREDICTION (never the real game). The bot flowcharts
    evaluate Battle outcomes "presuming all Defender Loss rolls result in
    removals (best for the attacker)"; rolling the die minimum (1 ≤ the 1-3
    removal threshold) realizes that on a throwaway state copy."""

    def randint(self, a, b):
        return a

    # Some code paths use random_select / choice on the rng; provide them.
    def choice(self, seq):
        return seq[0]

    def random(self):
        return 0.0

    def shuffle(self, seq):
        return None


def predict_battle(state, region, attacking_faction, defending_faction):
    """Deterministically predict a Battle's Losses for NP decision-making.

    Per the flowcharts' "presuming all Defender Loss rolls result in removals
    (the best possible case for the attacker)" — the presumption is scoped to
    the DEFENDER. So, on a deep copy with no Defender Retreat:
      - ``inflicted`` = Losses the attacker inflicts (Attack loss formula);
      - the Defender absorbs those Losses with all rolls forced to removals
        (fewest survivors -> least Counterattack);
      - ``taken`` = the Counterattack Loss COUNT from the survivors (a count of
        "die rolls or removals" on the attacker — NOT forced removals of the
        attacker's own pieces);
      - ``attacker_leader_lost`` = whether a Loss would be directed at the
        attacker's Leader: the Leader absorbs LAST among mobile pieces
        (Warbands/Auxilia/Legions, no-Retreat order, §3.2.4), so it is reached
        only when ``taken`` exceeds those non-Leader mobile pieces.
    Returns that dict, or None if the Battle cannot be evaluated.
    """
    import copy
    from fs_bot.battle.resolve import _calculate_attack_losses
    from fs_bot.battle.losses import resolve_losses, calculate_losses
    from fs_bot.rules_consts import CITADEL, FORT, WARBAND, AUXILIA, LEGION
    sim = copy.deepcopy(state)
    sim["rng"] = _AllRemovalsRng()
    try:
        d_pieces = sim["spaces"][region].get("pieces", {}).get(
            defending_faction, {})
        had_citadel = d_pieces.get(CITADEL, 0) > 0
        had_fort = d_pieces.get(FORT, 0) > 0
        # Attacker inflicts (no Defender Retreat — best for the attacker).
        inflicted = _calculate_attack_losses(
            sim, region, attacking_faction, defending_faction,
            is_retreat=False, had_citadel_at_start=had_citadel,
            had_fort_at_start=had_fort)
        # Defender absorbs them, all rolls forced to removals (fewest survivors).
        if inflicted > 0:
            resolve_losses(sim, region, defending_faction, inflicted)
        # Counterattack Loss COUNT from the surviving Defender.
        taken = calculate_losses(
            sim, region, attacking_faction=defending_faction,
            defending_faction=attacking_faction, is_counterattack=True)
        # The attacker's Leader is reached only after its non-Leader mobile
        # pieces absorb.
        absorbers = (count_pieces(sim, region, attacking_faction, WARBAND)
                     + count_pieces(sim, region, attacking_faction, AUXILIA)
                     + count_pieces(sim, region, attacking_faction, LEGION))
        has_leader = (get_leader_in_region(sim, region, attacking_faction)
                      is not None)
    except Exception:
        return None
    return {
        "inflicted": inflicted,
        "taken": taken,
        "attacker_leader_lost": has_leader and taken > absorbers,
    }


def roman_battle_is_favorable(state, region, defending_faction):
    """R_BATTLE condition (§8.8.1): "Roman Losses will be < 1/2 enemy's AND no
    Loss on Caesar." Evaluated via predict_battle. Returns bool."""
    pred = predict_battle(state, region, ROMANS, defending_faction)
    if pred is None:
        return False
    inflicted, taken = pred["inflicted"], pred["taken"]
    # Roman Losses (taken) strictly less than half the enemy's (inflicted).
    favorable = (taken * 2 < inflicted)
    return favorable and not pred["attacker_leader_lost"]


# ============================================================================
# Rally plan prevalidation — §3.3.1 / §3.4.1 / A3.4.1
# ============================================================================
# "One rule, one implementation": the flowchart Rally nodes (§8.5.3, §8.6.3,
# §8.7.3, A8.7.4) Rally "wherever able to place a piece". What a Rally is
# "able" to place is defined by the executor (fs_bot.commands.rally.
# rally_in_region), so each planner passes its draft rally_plan through this
# filter, which simulates the executor's own checks with the executor's own
# primitives, in _execute_rally order (Citadels, then Allies, then Warbands),
# against a running Resource budget that mirrors rally_in_region's per-call
# charging. Entries the executor would reject are dropped; per the Q12 owner
# ruling ("pay ... until Resources run out; no reserve"), the budget is spent
# in plan-priority order, skipping unaffordable entries while still taking
# cheaper later ones — exactly what the executor's sequential charging does.

def prevalidate_rally_plan(state, faction, rally_plan, *, resources=None):
    """Filter a draft Rally through the actual §3.3.1/A3.4.1 procedure.

    The copied board enforces one option per Region, Vercingetorix's two-option
    exception (one payment), German home bonuses, stock limits and Control
    changes. No live pieces, Resources, RNG or decision agent are touched.
    """
    from copy import deepcopy
    from fs_bot.commands.rally import rally_in_region, validate_rally_option
    from fs_bot.commands.common import CommandError
    from fs_bot.board.pieces import PieceError
    sim = deepcopy({k: v for k, v in state.items() if k != "decision_agent"})
    if resources is not None:
        sim["resources"][faction] = resources
    out = dict(rally_plan)
    selected = {}
    for key, option in (("citadels", "place_citadel"),
                         ("allies", "place_ally"),
                         ("warbands", "place_warbands")):
        kept = []
        for entry in rally_plan.get(key) or []:
            region = entry if isinstance(entry, str) else entry.get("region")
            tribe = entry.get("tribe") if isinstance(entry, dict) else None
            mix = entry.get("warband_mix") if isinstance(entry, dict) else None
            prior = selected.get(region, set())
            try:
                validate_rally_option(sim, region, faction, option, prior)
                rally_in_region(sim, region, faction, option, tribe=tribe,
                                free=bool(prior), warband_mix=mix,
                                include_home_bonus=True)
            except (CommandError, PieceError):
                continue
            selected.setdefault(region, set()).add(option)
            kept.append(entry)
        out[key] = kept
    return out


def card27_shaded_absorption(state, region, own_faction, enemy):
    """Card 27 shaded (Massed Gallic Archers): 'At start of Battles with
    6 or more Arverni Warbands, the other side first must absorb 1 extra
    Loss.' Returns the extra Losses OWN_FACTION should expect to suffer
    in a Battle against ENEMY here (for bot go/no-go estimates; the
    executor applies the actual absorption).
    """
    from fs_bot.cards.capabilities import is_capability_active
    from fs_bot.rules_consts import (ARVERNI, WARBAND, EVENT_SHADED)
    if not is_capability_active(state, 27, EVENT_SHADED):
        return 0
    from fs_bot.board.pieces import count_pieces
    if (enemy == ARVERNI and own_faction != ARVERNI
            and count_pieces(state, region, ARVERNI, WARBAND) >= 6):
        return 1
    return 0


def affordable_battle_plan(state, faction, plan):
    """Keep Battle Regions in flowchart order while Resources permit (8.3)."""
    from fs_bot.commands.common import battle_cost
    budget = state["resources"].get(faction, 0)
    selected = []
    seen = set()
    for entry in plan:
        region = entry.get("region")
        if region in seen:
            continue
        cost = battle_cost(state, region, faction)
        if cost > budget:
            continue
        selected.append(entry)
        seen.add(region)
        budget -= cost
    return selected
