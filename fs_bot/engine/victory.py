"""Victory module — Victory calculation, checking, and ranking.

Implements all victory logic per §7.0-§7.3 (base game) and A7.0-A7.3
(Ariovistus). Each function gates on state["scenario"] to select the
correct formula.

Reference:
  §7.0  Victory overview
  §7.1  Ranking Wins and Breaking Ties
  §7.2  Exceeding Victory Threshold
  §7.3  During the Final Winter
  A7.0  Ariovistus victory overview (Arverni do NOT track)
  A7.1  Ariovistus tiebreaking
  A7.2  Ariovistus victory conditions
  A7.3  Ariovistus victory margins
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    FACTIONS,
    # Piece types
    ALLY, CITADEL, SETTLEMENT,
    # Scenarios
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    # Tribes
    BASE_TRIBES, ARIOVISTUS_TRIBES,
    SUEBI_TRIBES, TRIBE_TO_REGION,
    # Victory constants
    ROMAN_VICTORY_THRESHOLD,
    ARVERNI_LEGIONS_THRESHOLD,
    ARVERNI_ALLIES_THRESHOLD,
    BELGAE_VICTORY_THRESHOLD,
    GERMAN_VICTORY_THRESHOLD,
    # Tiebreaking
    TIEBREAK_ORDER_BASE,
    TIEBREAK_ORDER_ARIOVISTUS,
    # Control
    BELGIC_CONTROL, GERMANIC_CONTROL,
    FACTION_CONTROL,
    # Regions
    GERMANIA_REGIONS,
    # Map
    REGION_CONTROL_VALUES,
    CISALPINA, CISALPINA_CV_ARIOVISTUS,
    # Markers
    MARKER_DISPERSED, MARKER_DISPERSED_GATHERING, MARKER_COLONY,
    # Legions
    LEGIONS_ROWS,
    # Misc
    TOTAL_TRIBES_BASE,
    COLONY_EXTRA_TRIBE,
)
from fs_bot.board.pieces import count_pieces, count_on_map
from fs_bot.board.control import get_controlled_regions, is_controlled_by
from fs_bot.map.map_data import (
    get_tribes_in_region, get_control_value, get_playable_regions,
    ALL_REGION_DATA,
)


class VictoryError(Exception):
    """Raised when victory logic encounters an invalid state."""
    pass


# ============================================================================
# HELPER: Count allied tribes + citadels for a faction
# ============================================================================

def _count_allies_and_citadels(state, faction):
    """Count a faction's Allied Tribes + Citadels on the map.

    Allied Tribes are counted from the tribes dict (not piece counts),
    and Citadels from piece counts on the map.

    Returns:
        Integer total.
    """
    allies = 0
    for tribe_info in state["tribes"].values():
        if tribe_info.get("allied_faction") == faction:
            allies += 1

    citadels = count_on_map(state, faction, CITADEL)
    return allies + citadels


def _count_settlements_on_map(state):
    """Count total Germanic Settlements on the map.

    Returns:
        Integer count of Settlement pieces on the map.
    """
    return count_on_map(state, GERMANS, SETTLEMENT)


def _count_off_map_legions(state):
    """Count off-map Legions: Fallen + Legions Track + removed by Event.

    Per §7.2: Off-map Legions = Fallen + on Legions Track + removed by Event.

    Returns:
        Integer count.
    """
    fallen = state.get("fallen_legions", 0)
    on_track = sum(state["legions_track"].get(row, 0) for row in LEGIONS_ROWS)
    removed = state.get("removed_legions", 0)
    return fallen + on_track + removed


def _count_subdued_tribes(state):
    """Count Subdued tribes (empty circles — no Ally, not Dispersed).

    Per §1.7: A tribe is Subdued if it has no Ally disc and no
    Dispersed/Dispersed-Gathering marker. In our state, status=None
    and allied_faction=None means Subdued.

    Returns:
        Integer count.
    """
    count = 0
    for tribe_info in state["tribes"].values():
        if (tribe_info.get("allied_faction") is None
                and tribe_info.get("status") is None):
            count += 1
    return count


def _count_dispersed_tribes(state):
    """Count tribes with Dispersed or Dispersed-Gathering markers.

    Returns:
        Integer count.
    """
    count = 0
    for tribe_info in state["tribes"].values():
        status = tribe_info.get("status")
        if status in (MARKER_DISPERSED, MARKER_DISPERSED_GATHERING):
            count += 1
    return count


def _count_allied_tribes(state, faction):
    """Count Allied Tribes for a specific faction.

    Returns:
        Integer count.
    """
    count = 0
    for tribe_info in state["tribes"].values():
        if tribe_info.get("allied_faction") == faction:
            count += 1
    return count


def _has_colony_marker(state):
    """Check if the Colony Event marker is in play.

    Returns:
        True if Colony marker is active.
    """
    # Colony marker is tracked in capabilities or markers
    caps = state.get("capabilities", {})
    markers = state.get("markers", {})
    # Check capabilities
    if MARKER_COLONY in caps:
        return True
    # Check region markers
    for region_markers in markers.values():
        if isinstance(region_markers, dict) and MARKER_COLONY in region_markers:
            return True
        if isinstance(region_markers, set) and MARKER_COLONY in region_markers:
            return True
    return False


def _colony_region(state):
    """Find the region with the Colony marker, if any.

    Returns:
        Region name or None.
    """
    markers = state.get("markers", {})
    for region, region_markers in markers.items():
        if isinstance(region_markers, dict) and MARKER_COLONY in region_markers:
            return region
        if isinstance(region_markers, set) and MARKER_COLONY in region_markers:
            return region
    return None


# ============================================================================
# VICTORY FACTIONS PER SCENARIO
# ============================================================================

def _get_victory_factions(state):
    """Return the factions that track victory in the current scenario.

    Base game: Romans, Arverni, Aedui, Belgae (NOT Germans) — §7.0 NOTE
    Ariovistus: Romans, Germans, Aedui, Belgae (NOT Arverni) — A7.0 NOTE
    """
    scenario = state["scenario"]
    if scenario in ARIOVISTUS_SCENARIOS:
        return (ROMANS, GERMANS, AEDUI, BELGAE)
    return (ROMANS, ARVERNI, AEDUI, BELGAE)


# ============================================================================
# BELGIC CONTROL VALUE — §7.2
# ============================================================================

def _calculate_belgic_control_value(state):
    """Calculate Belgic Control Value per §7.2.

    BCV = sum of Control Value of all Regions under Belgic Control,
    including +1 for Colony marker in a Belgic-Controlled region,
    and -1 for each non-Suebi Dispersed tribe.

    Per §7.2 PLAY NOTES:
    - CV = sum of Control Values of Belgic-Controlled regions
    - Non-Suebi Dispersed tribes subtract 1 each from CV
    - Colony marker adds +1 if in a Belgic-Controlled region (implied
      by "including +1 for a Region with the Colony Event marker")

    Per §7.2 and §3.2.3: Dispersed reduces a Region's Control Value.
    BCV sums CV of Belgic-Controlled regions only, so only Dispersed
    tribes IN Belgic-Controlled regions reduce BCV.
    """
    scenario = state["scenario"]
    bcv = 0

    # Sum CV of all Belgic-Controlled regions
    belgic_regions = get_controlled_regions(state, BELGAE)
    for region in belgic_regions:
        cv = get_control_value(region, scenario)
        bcv += cv

    # Colony marker: +1 if Colony exists in a Belgic-Controlled region
    colony_reg = _colony_region(state)
    if colony_reg is not None and colony_reg in belgic_regions:
        bcv += 1

    # -1 for each non-Suebi Dispersed tribe in Belgic-Controlled regions
    # Per §7.2 and §3.2.3: Dispersed reduces a Region's CV, so only
    # tribes in regions that contribute to BCV (Belgic-Controlled) count.
    for tribe_name, tribe_info in state["tribes"].items():
        status = tribe_info.get("status")
        if status in (MARKER_DISPERSED, MARKER_DISPERSED_GATHERING):
            if tribe_name not in SUEBI_TRIBES:
                tribe_region = TRIBE_TO_REGION.get(tribe_name)
                if tribe_region in belgic_regions:
                    bcv -= 1

    return bcv


# ============================================================================
# CALCULATE VICTORY SCORE
# ============================================================================

def calculate_victory_score(state, faction):
    """Calculate the current victory total for a faction.

    Per §7.2 and A7.2. The returned value is the "score" used to
    compare against thresholds.

    For Arverni, returns a dict with both components since they have
    dual conditions: {"off_map_legions": int, "allies_citadels": int}.

    Args:
        state: Game state dict.
        faction: Faction constant.

    Returns:
        Integer score (or dict for Arverni).

    Raises:
        VictoryError: If faction doesn't track victory in this scenario.
    """
    scenario = state["scenario"]

    if faction == ROMANS:
        # §7.2: Subdued + Dispersed + Roman Allied Tribes
        subdued = _count_subdued_tribes(state)
        dispersed = _count_dispersed_tribes(state)
        roman_allies = _count_allied_tribes(state, ROMANS)
        score = subdued + dispersed + roman_allies
        if scenario in ARIOVISTUS_SCENARIOS:
            # A7.2: minus Germanic Settlements on the map
            score -= _count_settlements_on_map(state)
        return score

    if faction == ARVERNI:
        if scenario in ARIOVISTUS_SCENARIOS:
            raise VictoryError(
                "Arverni do not track victory in Ariovistus (A7.0)"
            )
        # §7.2: Two separate conditions
        off_map = _count_off_map_legions(state)
        allies_citadels = _count_allies_and_citadels(state, ARVERNI)
        return {"off_map_legions": off_map, "allies_citadels": allies_citadels}

    if faction == AEDUI:
        # §7.2 / A7.2: Aedui Allied Tribes + Citadels
        return _count_allies_and_citadels(state, AEDUI)

    if faction == BELGAE:
        # §7.2: Belgic Control Value + Belgic Allies + Citadels
        bcv = _calculate_belgic_control_value(state)
        allies_citadels = _count_allies_and_citadels(state, BELGAE)
        return bcv + allies_citadels

    if faction == GERMANS:
        if scenario in BASE_SCENARIOS:
            raise VictoryError(
                "Germans do not track victory in base game (§7.0 NOTE)"
            )
        # A7.2: Germania Regions under Germanic Control +
        #        German Settlements under Germanic Control
        german_controlled = get_controlled_regions(state, GERMANS)
        germania_controlled = sum(
            1 for r in german_controlled if r in GERMANIA_REGIONS
        )
        # Settlements under Germanic Control: count Settlements in
        # regions that are under Germanic Control
        settlements_controlled = 0
        for region in german_controlled:
            settlements_controlled += count_pieces(
                state, region, GERMANS, SETTLEMENT
            )
        return germania_controlled + settlements_controlled

    raise VictoryError(f"Unknown faction: {faction}")


# ============================================================================
# CHECK VICTORY
# ============================================================================

def check_victory(state, faction):
    """Check if a faction currently meets its victory condition.

    Per §7.2 / A7.2.

    Args:
        state: Game state dict.
        faction: Faction constant.

    Returns:
        True if the faction meets its victory condition.

    Raises:
        VictoryError: If faction doesn't track victory in this scenario.
    """
    scenario = state["scenario"]

    if faction == ROMANS:
        score = calculate_victory_score(state, ROMANS)
        return score > ROMAN_VICTORY_THRESHOLD

    if faction == ARVERNI:
        if scenario in ARIOVISTUS_SCENARIOS:
            raise VictoryError(
                "Arverni do not track victory in Ariovistus (A7.0)"
            )
        scores = calculate_victory_score(state, ARVERNI)
        # Both conditions must be met — §7.2
        return (scores["off_map_legions"] > ARVERNI_LEGIONS_THRESHOLD
                and scores["allies_citadels"] > ARVERNI_ALLIES_THRESHOLD)

    if faction == AEDUI:
        # §7.2: Must exceed EACH other faction's Allies + Citadels
        # individually (not total)
        aedui_score = calculate_victory_score(state, AEDUI)
        for other in FACTIONS:
            if other == AEDUI:
                continue
            other_ac = _count_allies_and_citadels(state, other)
            # A7.2: In Ariovistus, count Settlements as Germanic Allies
            if (scenario in ARIOVISTUS_SCENARIOS
                    and other == GERMANS):
                other_ac += _count_settlements_on_map(state)
            if aedui_score <= other_ac:
                return False
        return True

    if faction == BELGAE:
        score = calculate_victory_score(state, BELGAE)
        return score > BELGAE_VICTORY_THRESHOLD

    if faction == GERMANS:
        if scenario in BASE_SCENARIOS:
            raise VictoryError(
                "Germans do not track victory in base game (§7.0 NOTE)"
            )
        score = calculate_victory_score(state, GERMANS)
        return score > GERMAN_VICTORY_THRESHOLD

    raise VictoryError(f"Unknown faction: {faction}")


# ============================================================================
# CALCULATE VICTORY MARGIN
# ============================================================================

def calculate_victory_margin(state, faction):
    """Calculate the victory margin for final Winter tiebreaking.

    Per §7.3 / A7.3. Positive means above threshold, negative means below.

    Args:
        state: Game state dict.
        faction: Faction constant.

    Returns:
        Integer or float margin.

    Raises:
        VictoryError: If faction doesn't track victory in this scenario.
    """
    scenario = state["scenario"]

    if faction == ROMANS:
        score = calculate_victory_score(state, ROMANS)
        return score - ROMAN_VICTORY_THRESHOLD

    if faction == ARVERNI:
        if scenario in ARIOVISTUS_SCENARIOS:
            raise VictoryError(
                "Arverni do not track victory in Ariovistus (A7.0)"
            )
        scores = calculate_victory_score(state, ARVERNI)
        # §7.3: Lower of (off-map Legions - 6) or (Allies+Citadels - 8)
        legions_margin = scores["off_map_legions"] - ARVERNI_LEGIONS_THRESHOLD
        allies_margin = scores["allies_citadels"] - ARVERNI_ALLIES_THRESHOLD
        return min(legions_margin, allies_margin)

    if faction == AEDUI:
        aedui_score = calculate_victory_score(state, AEDUI)
        # §7.3: Aedui score - other faction with the most
        highest_other = 0
        for other in FACTIONS:
            if other == AEDUI:
                continue
            other_ac = _count_allies_and_citadels(state, other)
            # A7.3: counting Settlements as Germanic Allies
            if (scenario in ARIOVISTUS_SCENARIOS
                    and other == GERMANS):
                other_ac += _count_settlements_on_map(state)
            if other_ac > highest_other:
                highest_other = other_ac
        return aedui_score - highest_other

    if faction == BELGAE:
        score = calculate_victory_score(state, BELGAE)
        return score - BELGAE_VICTORY_THRESHOLD

    if faction == GERMANS:
        if scenario in BASE_SCENARIOS:
            raise VictoryError(
                "Germans do not track victory in base game (§7.0 NOTE)"
            )
        score = calculate_victory_score(state, GERMANS)
        return score - GERMAN_VICTORY_THRESHOLD

    raise VictoryError(f"Unknown faction: {faction}")


# ============================================================================
# CHECK ANY VICTORY
# ============================================================================

def check_any_victory(state):
    """Check if any eligible faction meets its victory condition.

    Returns the winning faction, or None. If multiple factions win
    simultaneously, ties are broken per §7.1 / A7.1:
    - Non-players first, then tiebreak order.

    Args:
        state: Game state dict.

    Returns:
        Winning faction constant, or None.
    """
    scenario = state["scenario"]
    victory_factions = _get_victory_factions(state)

    winners = []
    for faction in victory_factions:
        if check_victory(state, faction):
            winners.append(faction)

    if not winners:
        return None

    if len(winners) == 1:
        return winners[0]

    # Break ties per §7.1 / A7.1
    # Non-players first, then tiebreak order
    return _break_tie(state, winners)


def _break_tie(state, tied_factions):
    """Break a tie among factions per §7.1 / A7.1.

    Priority:
    1. Non-player factions (bot-controlled) — §7.1 / A7.1
    2. Then by faction order:
       Base: Romans, Arverni, Aedui, Belgae
       Ariovistus: Romans, Germans, Aedui, Belgae

    Args:
        state: Game state dict.
        tied_factions: List of tied faction constants.

    Returns:
        Winning faction constant.
    """
    scenario = state["scenario"]
    if scenario in ARIOVISTUS_SCENARIOS:
        tiebreak = TIEBREAK_ORDER_ARIOVISTUS
    else:
        tiebreak = TIEBREAK_ORDER_BASE

    # Check non-player factions first
    # Non-player status is tracked in state; for now, check if
    # a faction is bot-controlled
    non_players = state.get("non_player_factions", set())

    # Among tied factions, non-players win first
    np_tied = [f for f in tied_factions if f in non_players]
    player_tied = [f for f in tied_factions if f not in non_players]

    # If any non-players are tied, they win
    candidates = np_tied if np_tied else player_tied

    # Break remaining ties by tiebreak order
    for faction in tiebreak:
        if faction in candidates:
            return faction

    return tied_factions[0]


# ============================================================================
# DETERMINE FINAL RANKING
# ============================================================================

def determine_final_ranking(state):
    """Determine final ranking for the end of the game (§7.3 / A7.3).

    Rank all eligible factions by victory margin. Break ties per
    §7.1 / A7.1.

    Args:
        state: Game state dict.

    Returns:
        List of (faction, margin) tuples, ordered from 1st to last.
    """
    scenario = state["scenario"]
    victory_factions = _get_victory_factions(state)

    # Calculate margins for all victory-tracking factions
    faction_margins = []
    for faction in victory_factions:
        margin = calculate_victory_margin(state, faction)
        faction_margins.append((faction, margin))

    # Sort by margin descending, with ties broken by §7.1 / A7.1
    if scenario in ARIOVISTUS_SCENARIOS:
        tiebreak = TIEBREAK_ORDER_ARIOVISTUS
    else:
        tiebreak = TIEBREAK_ORDER_BASE

    non_players = state.get("non_player_factions", set())

    def _sort_key(item):
        faction, margin = item
        # Primary: higher margin wins (negate for ascending sort)
        # Secondary: non-player beats player (0 < 1)
        # Tertiary: tiebreak order position
        is_player = 0 if faction in non_players else 1
        tb_pos = list(tiebreak).index(faction)
        return (-margin, is_player, tb_pos)

    faction_margins.sort(key=_sort_key)
    return faction_margins
