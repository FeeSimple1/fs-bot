"""CLI state display module — Phase 6.

Renders plain-text snapshots of the game state for the player. ASCII only,
no curses, no emojis. All labels come from rules_consts. The display layer
is read-only — it never mutates state.

Reference:
  §1.0   Pieces, regions, tribes
  §1.6   Control
  §2.3.8 Frost
  §5.3   Capabilities
  §6.5   Senate
  §6.5.2 Legions track
  §7.0   Victory
  A1.4   Settlements / Diviciacus
  A2.3.9 At War
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    FACTIONS, GALLIC_FACTIONS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Scenarios
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS,
    # Regions
    ALL_REGIONS,
    # Senate
    UPROAR, INTRIGUE, ADULATION,
    # Legions track
    LEGIONS_ROW_BOTTOM, LEGIONS_ROW_MIDDLE, LEGIONS_ROW_TOP,
    LEGIONS_ROWS, LEGIONS_PER_ROW,
    # Eligibility
    ELIGIBLE, INELIGIBLE,
    # Control
    ROMAN_CONTROL, ARVERNI_CONTROL, AEDUI_CONTROL,
    BELGIC_CONTROL, GERMANIC_CONTROL, NO_CONTROL,
    FACTION_CONTROL,
    # Tribe status
    ALLIED, DISPERSED, DISPERSED_GATHERING, SUBDUED,
    MARKER_DISPERSED, MARKER_DISPERSED_GATHERING,
    # Markers
    MARKER_AT_WAR,
    # Events
    EVENT_SHADED, EVENT_UNSHADED,
)
from fs_bot.cards.card_data import (
    get_card, get_np_symbols, get_faction_order, card_has_carnyx_trigger,
)
from fs_bot.board.pieces import count_pieces, get_available
from fs_bot.map.map_data import (
    get_playable_regions, get_tribes_in_region,
)


# Display width target — keep lines ≤ 100 chars
SEP = "-" * 78
SEP_HEAVY = "=" * 78


# Faction display short codes for tables
_FACTION_SHORT = {
    ROMANS: "Rom",
    ARVERNI: "Arv",
    AEDUI: "Aed",
    BELGAE: "Bel",
    GERMANS: "Ger",
}

_CONTROL_SHORT = {
    ROMAN_CONTROL: "Rom",
    ARVERNI_CONTROL: "Arv",
    AEDUI_CONTROL: "Aed",
    BELGIC_CONTROL: "Bel",
    GERMANIC_CONTROL: "Ger",
    NO_CONTROL: "-",
}


# ============================================================================
# CARD DISPLAY
# ============================================================================

def format_card(card_id, scenario):
    """Render a card as a multi-line summary.

    Shows: card number, title, faction order, NP instruction symbols
    (Carnyx/Laurels/Swords) per §8.2.1, and the Arverni carnyx trigger
    flag (A2.3.9) if present.

    Args:
        card_id: Card identifier (int or "A##" or "W#"), or None.
        scenario: Active scenario constant.

    Returns:
        Multi-line string.
    """
    if card_id is None:
        return "Card: (none)"
    try:
        card = get_card(card_id, scenario)
    except KeyError:
        return f"Card #{card_id} (unknown)"

    lines = [f"Card #{card_id}: {card.title}"]
    if card.faction_order:
        order = " > ".join(_FACTION_SHORT.get(f, f) for f in card.faction_order)
        lines.append(f"  Faction order: {order}")
    syms = card.np_symbols or {}
    if syms:
        sym_strs = [f"{_FACTION_SHORT.get(f, f)}={s}" for f, s in syms.items()]
        lines.append(f"  NP symbols:    {', '.join(sym_strs)}")
    if scenario in ARIOVISTUS_SCENARIOS and card_has_carnyx_trigger(card_id, scenario):
        lines.append("  Arverni carnyx trigger (A2.3.9): check At War")
    if card.is_capability:
        lines.append("  Capability card (Sec 5.3)")
    return "\n".join(lines)


# ============================================================================
# STATE SUMMARY
# ============================================================================

def _eligibility_label(state, faction):
    val = state["eligibility"].get(faction, ELIGIBLE)
    return "Eligible" if val == ELIGIBLE else "Ineligible"


def _faction_total_allies_citadels(state, faction):
    """Return (allies, citadels) on the map for a faction."""
    allies = sum(
        1 for t in state["tribes"].values()
        if t.get("allied_faction") == faction
    )
    citadels = 0
    for region in state["spaces"]:
        citadels += count_pieces(state, region, faction, CITADEL)
    return allies, citadels


def _format_senate(state):
    """Render Senate position+firm marker — §6.5, §6.5.1."""
    pos = state["senate"].get("position")
    firm = state["senate"].get("firm", False)
    if pos is None:
        pos_str = "(none)"
    else:
        pos_str = pos
    suffix = " [Firm]" if firm else ""
    return f"{pos_str}{suffix}"


def _format_legions_track_inline(state):
    """One-line summary of the Legions track."""
    parts = []
    for row in LEGIONS_ROWS:
        parts.append(f"{row}:{state['legions_track'].get(row, 0)}")
    return " | ".join(parts)


def _format_capabilities(state):
    """Render active capabilities — §5.3."""
    caps = state.get("capabilities") or {}
    if not caps:
        return "(none)"
    parts = []
    for card_id, side in caps.items():
        side_short = "shaded" if side == EVENT_SHADED else "unshaded"
        parts.append(f"#{card_id} ({side_short})")
    return ", ".join(parts)


def format_state_summary(state):
    """Render a multi-line plain-text snapshot of the full game state.

    Includes:
      - Current and upcoming card
      - Frost status (§2.3.8)
      - At War (Ariovistus) — A2.3.9
      - Faction rows: resources, eligibility, Allies + Citadels
      - Senate position+firm (§6.5)
      - Legions track inline (§6.5.2)
      - Active capabilities (§5.3)

    Args:
        state: Game state dict.

    Returns:
        Multi-line string.
    """
    scenario = state["scenario"]
    lines = []
    lines.append(SEP_HEAVY)
    lines.append(f"Scenario: {scenario}")
    lines.append(SEP)

    # Cards
    lines.append("Current card:")
    for ln in format_card(state.get("current_card"), scenario).splitlines():
        lines.append("  " + ln)
    lines.append("")
    lines.append("Upcoming card:")
    for ln in format_card(state.get("next_card"), scenario).splitlines():
        lines.append("  " + ln)

    # Markers
    from fs_bot.engine.game_engine import is_frost
    frost = is_frost(state)
    lines.append("")
    lines.append(f"Frost: {'YES' if frost else 'no'}")
    if scenario in ARIOVISTUS_SCENARIOS:
        lines.append(f"At War (Arverni): {'YES' if state.get('at_war') else 'no'}")
        lines.append(f"Diviciacus in play: "
                     f"{'YES' if state.get('diviciacus_in_play') else 'no'}")

    # Faction table
    lines.append(SEP)
    lines.append(
        f"{'Faction':<10}{'Resources':>10}{'Eligibility':>14}"
        f"{'Allies':>9}{'Citadels':>10}"
    )
    lines.append("-" * 53)
    # Show all factions that have resources or eligibility relevant
    for faction in FACTIONS:
        res = state["resources"].get(faction)
        if res is None and faction == GERMANS and scenario in BASE_SCENARIOS:
            # Germans don't have resources in base — §1.8
            continue
        allies, citadels = _faction_total_allies_citadels(state, faction)
        elig = _eligibility_label(state, faction)
        res_str = "-" if res is None else str(res)
        lines.append(
            f"{faction:<10}{res_str:>10}{elig:>14}{allies:>9}{citadels:>10}"
        )

    # Senate / Legions
    lines.append(SEP)
    lines.append(f"Senate:        {_format_senate(state)}")
    lines.append(f"Legions track: {_format_legions_track_inline(state)}")
    lines.append(f"  Fallen: {state.get('fallen_legions', 0)}   "
                 f"Removed by Event: {state.get('removed_legions', 0)}")
    lines.append(f"Capabilities:  {_format_capabilities(state)}")
    lines.append(SEP_HEAVY)
    return "\n".join(lines)


# ============================================================================
# REGION TABLE
# ============================================================================

def _region_pieces_summary(state, region, faction, scenario):
    """One-cell summary of a faction's pieces in a region."""
    parts = []
    # Leader — show only "L" + suffix (full names like Caesar/Ambiorix/Boduognatus
    # are too wide for the table). The leader's identity is on the card
    # and in the faction-detail views.
    leader = state["spaces"].get(region, {}).get("pieces", {}).get(
        faction, {}
    ).get(LEADER)
    if leader is not None:
        # Use first 3 chars of leader name for ID hint
        leader_tag = str(leader)[:3]
        parts.append(f"L({leader_tag})")
    # Legions (Romans)
    if faction == ROMANS:
        legs = count_pieces(state, region, faction, LEGION)
        if legs:
            parts.append(f"Lg:{legs}")
        aux = count_pieces(state, region, faction, AUXILIA)
        if aux:
            parts.append(f"A:{aux}")
        forts = count_pieces(state, region, faction, FORT)
        if forts:
            parts.append(f"F:{forts}")
    else:
        wb = count_pieces(state, region, faction, WARBAND)
        if wb:
            parts.append(f"W:{wb}")
    cit = count_pieces(state, region, faction, CITADEL)
    if cit:
        parts.append(f"C:{cit}")
    if faction == GERMANS and scenario in ARIOVISTUS_SCENARIOS:
        st = count_pieces(state, region, faction, SETTLEMENT)
        if st:
            parts.append(f"S:{st}")
    return ",".join(parts) if parts else "-"


def format_region_table(state):
    """Render a table of playable regions with piece counts per faction.

    Columns: Region | Control | Rom | Arv | Aed | Bel | Ger

    Pieces are abbreviated: L=Leader, Lg=Legion, A=Auxilia, W=Warband,
    F=Fort, C=Citadel, S=Settlement (Ariovistus). Each cell lists only
    non-zero piece types separated by commas, or '-' if empty.

    Returns:
        Multi-line string.
    """
    scenario = state["scenario"]
    playable = get_playable_regions(scenario)
    lines = []
    lines.append(SEP_HEAVY)
    lines.append("REGIONS  (L=Leader Lg=Legion A=Aux W=Warband "
                 "F=Fort C=Citadel S=Settlement)")
    lines.append(SEP)
    # Column widths chosen so the Roman cell (which carries Caesar,
    # Legions, Auxilia, and Forts together) fits.
    w_rom = 18
    w_other = 14
    header = (
        f"{'Region':<14}{'Ctrl':<6}"
        f"{'Romans':<{w_rom}}{'Arverni':<{w_other}}{'Aedui':<{w_other}}"
        f"{'Belgae':<{w_other}}"
    )
    if scenario in ARIOVISTUS_SCENARIOS:
        header += f"{'Germans':<{w_other}}"
    lines.append(header)
    lines.append("-" * len(header))
    for region in ALL_REGIONS:
        if region not in playable:
            continue
        ctrl = _CONTROL_SHORT.get(
            state["spaces"][region].get("control", NO_CONTROL), "-"
        )
        row = f"{region:<14}{ctrl:<6}"
        row += f"{_region_pieces_summary(state, region, ROMANS, scenario):<{w_rom}}"
        row += f"{_region_pieces_summary(state, region, ARVERNI, scenario):<{w_other}}"
        row += f"{_region_pieces_summary(state, region, AEDUI, scenario):<{w_other}}"
        row += f"{_region_pieces_summary(state, region, BELGAE, scenario):<{w_other}}"
        if scenario in ARIOVISTUS_SCENARIOS:
            row += f"{_region_pieces_summary(state, region, GERMANS, scenario):<{w_other}}"
        lines.append(row)
    lines.append(SEP_HEAVY)
    return "\n".join(lines)


# ============================================================================
# TRIBES TABLE
# ============================================================================

def _tribe_status_label(tribe_info):
    """Render a tribe's status string."""
    status = tribe_info.get("status")
    allied = tribe_info.get("allied_faction")
    if status == ALLIED or allied:
        return f"Allied -> {_FACTION_SHORT.get(allied, allied or '?')}"
    if status in (MARKER_DISPERSED, DISPERSED):
        return "Dispersed"
    if status in (MARKER_DISPERSED_GATHERING, DISPERSED_GATHERING):
        return "Dispersed-Gathering"
    return "Subdued"


def format_tribes_table(state):
    """Render the tribe allegiances table, grouped by region.

    Columns: Region | Tribe | Status

    Returns:
        Multi-line string.
    """
    scenario = state["scenario"]
    playable = get_playable_regions(scenario)
    lines = []
    lines.append(SEP_HEAVY)
    lines.append("TRIBES")
    lines.append(SEP)
    lines.append(f"{'Region':<14}{'Tribe':<22}{'Status':<24}")
    lines.append("-" * 60)
    for region in ALL_REGIONS:
        if region not in playable:
            continue
        tribes = get_tribes_in_region(region, scenario)
        for tribe in tribes:
            info = state["tribes"].get(tribe, {})
            lines.append(
                f"{region:<14}{tribe:<22}{_tribe_status_label(info):<24}"
            )
    lines.append(SEP_HEAVY)
    return "\n".join(lines)


# ============================================================================
# LEGIONS TRACK (visual)
# ============================================================================

def format_legions_track(state):
    """Render the Legions track as a visual three-row diagram — §6.5.2.

    Each row shows N filled slots and (capacity-N) empty slots out of
    LEGIONS_PER_ROW.

    Returns:
        Multi-line string.
    """
    lines = []
    lines.append("Legions Track (top -> bottom):")
    for row in (LEGIONS_ROW_TOP, LEGIONS_ROW_MIDDLE, LEGIONS_ROW_BOTTOM):
        n = state["legions_track"].get(row, 0)
        filled = "[X]" * n
        empty = "[ ]" * (LEGIONS_PER_ROW - n)
        lines.append(f"  {row:<8} {filled}{empty}  ({n}/{LEGIONS_PER_ROW})")
    lines.append(f"  Fallen: {state.get('fallen_legions', 0)}   "
                 f"Removed: {state.get('removed_legions', 0)}")
    return "\n".join(lines)


# ============================================================================
# ACTION FORMATTING
# ============================================================================

def format_action(action_dict, faction=None):
    """Translate a bot's full action dict to a one-line summary.

    The bot action shape is:
      {"command": str, "regions": list, "sa": str, "sa_regions": list,
       "details": dict}

    Per §8.x bot flowcharts and *_bot.py ACTION_* / SA_ACTION_* constants.

    Args:
        action_dict: The bot's action dict.
        faction: Optional faction name to prefix the line.

    Returns:
        One-line string, e.g. "Belgae: Rally in Treveri, Morini, Nervii
        (SA: Enlist in Treveri)".
    """
    if action_dict is None:
        return "(no action)"
    command = action_dict.get("command", "?")
    regions = action_dict.get("regions") or []
    sa = action_dict.get("sa") or "No SA"
    sa_regions = action_dict.get("sa_regions") or []

    prefix = f"{faction}: " if faction else ""

    # Pass and Event don't usually have regions
    if command == "Pass":
        return f"{prefix}Pass"
    if command == "None":
        return f"{prefix}(no action)"
    if command == "Event":
        return f"{prefix}Event"

    region_str = ", ".join(_label(r) for r in regions) if regions else "(no regions)"
    base = f"{prefix}{command} in {region_str}"

    if sa and sa != "No SA":
        if sa_regions:
            sa_str = ", ".join(_label(r) for r in sa_regions)
            base += f" (SA: {sa} in {sa_str})"
        else:
            base += f" (SA: {sa})"
    return base


def _label(item):
    """Render a region/target item that may be a str or a dict.

    Some bots return enriched dicts (e.g. {"region": ..., "target": ...})
    for sa_regions. Extract a 'region' key when present; otherwise stringify.
    """
    if isinstance(item, dict):
        return str(item.get("region", item))
    return str(item)


# ============================================================================
# VICTORY STATE
# ============================================================================

def format_victory_state(state):
    """Render the current victory margins for all tracking factions.

    Per §7.0 / A7.0. Arverni do not track in Ariovistus; Germans do not
    track in base game.

    Returns:
        Multi-line string.
    """
    # Import locally to avoid circular import worries
    from fs_bot.engine.victory import (
        calculate_victory_score, calculate_victory_margin, VictoryError,
        check_victory,
    )
    scenario = state["scenario"]
    lines = []
    lines.append(SEP_HEAVY)
    lines.append("VICTORY STATE")
    lines.append(SEP)
    for faction in FACTIONS:
        try:
            score = calculate_victory_score(state, faction)
        except VictoryError:
            lines.append(f"  {faction:<10} (does not track in {scenario})")
            continue
        try:
            margin = calculate_victory_margin(state, faction)
            won = check_victory(state, faction)
        except VictoryError:
            margin = None
            won = False

        if isinstance(score, dict):
            # Arverni dual-condition
            score_str = (
                f"off-map legions={score['off_map_legions']}, "
                f"allies+citadels={score['allies_citadels']}"
            )
        else:
            score_str = str(score)

        margin_str = "n/a" if margin is None else f"{margin:+d}"
        flag = "  *VICTORY*" if won else ""
        lines.append(
            f"  {faction:<10} score={score_str:<40} margin={margin_str}{flag}"
        )
    lines.append(SEP_HEAVY)
    return "\n".join(lines)
