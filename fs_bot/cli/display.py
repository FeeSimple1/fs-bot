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

import copy

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
    EVENT_SHADED, EVENT_UNSHADED, WINTER_CARD,
)
from fs_bot.cards.card_data import (
    get_card, get_np_symbols, get_faction_order, card_has_carnyx_trigger,
)
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_available
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

def format_card(card_id, scenario, *, include_text=False):
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
    if card_id == WINTER_CARD:
        return f"Card: {WINTER_CARD} — resolve the Winter Round (Sec 6.0)"
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
    if include_text:
        from fs_bot.cards.card_text import format_card_text
        printed = format_card_text(card_id, indent="  | ", scenario=scenario)
        if printed:
            lines.append(printed)
    return "\n".join(lines)


# ============================================================================
# STATE SUMMARY
# ============================================================================

def _eligibility_label(state, faction):
    val = state["eligibility"].get(faction, ELIGIBLE)
    return "Eligible" if val == ELIGIBLE else "Ineligible"


def _faction_total_allies_citadels(state, faction):
    """Return (allies, citadels) on the map for a faction."""
    from fs_bot.board.pieces import count_allied_discs
    allies = count_allied_discs(state, faction)
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
    from fs_bot.rules_consts import (CARD_NAMES_BASE,
                                     CARD_NAMES_ARIOVISTUS)
    CARD_TITLES = {**CARD_NAMES_BASE, **CARD_NAMES_ARIOVISTUS}
    owners = state.get("capability_owners") or {}
    parts = []
    for card_id, side in caps.items():
        side_short = "shaded" if side == EVENT_SHADED else "unshaded"
        title = CARD_TITLES.get(card_id, "")
        name = f" {title}" if title else ""
        holder = f", held by {owners[card_id]}" if card_id in owners else ""
        parts.append(f"#{card_id}{name} ({side_short}{holder})")
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
    for ln in format_card(state.get("current_card"), scenario,
                          include_text=True).splitlines():
        lines.append("  " + ln)
    lines.append("")
    lines.append("Upcoming card:")
    for ln in format_card(state.get("next_card"), scenario,
                          include_text=True).splitlines():
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
        f"{'Allies*':>9}{'Citadels':>10}"
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
    lines.append("  (*Allies = Allied Tribes, INCLUDING those upgraded "
                 "to Citadels)")
    lines.append(f"Capabilities:  {_format_capabilities(state)}")
    lines.append(f"Cards remaining in deck: {len(state.get('deck', []))}")
    lines.append("Played cards: " + ", ".join(
        str(c) for c in state.get("played_cards", [])))
    if state.get("forced_ineligible"):
        lines.append("Ineligible through next card: "
                     + _visible_value(state["forced_ineligible"]))
    if state.get("stay_eligible"):
        lines.append("Remain Eligible: "
                     + _visible_value(state["stay_eligible"]))
    if state.get("winter_track_legions") or state.get("spring_box_leaders"):
        lines.append(f"Winter track Legions: "
                     f"{state.get('winter_track_legions', 0)}; "
                     f"Spring box Leaders: "
                     f"{_visible_value(state.get('spring_box_leaders', []))}")
    lines.append(SEP_HEAVY)
    return "\n".join(lines)


# ============================================================================
# REGION TABLE
# ============================================================================

def _region_pieces_summary(state, region, faction, scenario):
    """One-cell summary of a faction's pieces in a region."""
    parts = []
    # Allied Tribe discs FIRST — they are victory points and battle
    # targets; omitting them made enemy Allies invisible in play.
    from fs_bot.rules_consts import ALLY as _ALLY_D
    allies = count_pieces(state, region, faction, _ALLY_D)
    if allies:
        parts.append(f"Al:{allies}")
    # Full names distinguish Leaders from Successors in the board view.
    leader = state["spaces"].get(region, {}).get("pieces", {}).get(
        faction, {}
    ).get(LEADER)
    if leader is not None:
        parts.append(f"L({leader})")
    # Legions (Romans)
    if faction == ROMANS:
        legs = count_pieces(state, region, faction, LEGION)
        if legs:
            parts.append(f"Lg:{legs}")
        aux = count_pieces(state, region, faction, AUXILIA)
        if aux:
            parts.append(_flippable_summary(state, region, faction, AUXILIA,
                                            "A", aux))
        forts = count_pieces(state, region, faction, FORT)
        if forts:
            parts.append(f"F:{forts}")
    else:
        wb = count_pieces(state, region, faction, WARBAND)
        if wb:
            parts.append(_flippable_summary(state, region, faction, WARBAND,
                                            "W", wb))
    cit = count_pieces(state, region, faction, CITADEL)
    if cit:
        parts.append(f"C:{cit}")
    if faction == GERMANS and scenario in ARIOVISTUS_SCENARIOS:
        st = count_pieces(state, region, faction, SETTLEMENT)
        if st:
            parts.append(f"S:{st}")
    return ",".join(parts) if parts else "-"


def _flippable_summary(state, region, faction, piece_type, tag, total):
    counts = [count_pieces_by_state(state, region, faction, piece_type, ps)
              for ps in (HIDDEN, REVEALED, SCOUTED)]
    return f"{tag}:{total}[H{counts[0]}/R{counts[1]}/S{counts[2]}]"


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
    playable = get_playable_regions(scenario, state.get("capabilities"))
    lines = []
    lines.append(SEP_HEAVY)
    lines.append("REGIONS  (Al=Ally L=Leader Lg=Legion A=Aux W=Warband "
                 "F=Fort C=Citadel S=Settlement)")
    lines.append("  Mobile piece states: H=Hidden / R=Revealed / S=Scouted")
    lines.append(SEP)
    # Column widths chosen so the Roman cell (which carries Caesar,
    # Legions, Auxilia, and Forts together) fits.
    cells = {(region, f): _region_pieces_summary(state, region, f, scenario)
             for region in playable for f in FACTIONS}
    w_rom = max(21, max((len(cells[(r, ROMANS)]) + 2 for r in playable),
                        default=0))
    w_other = max(21, max((len(cell) + 2 for (r, f), cell in cells.items()
                           if f != ROMANS), default=0))
    header = (
        f"{'Region':<14}{'Ctrl':<6}"
        f"{'Romans':<{w_rom}}{'Arverni':<{w_other}}{'Aedui':<{w_other}}"
        f"{'Belgae':<{w_other}}"
    )
    # Germans field pieces in BASE games too (Germanic Phase forces) —
    # they were invisible without a column.
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
    if status:
        return str(status)
    return "Subdued"


def format_tribes_table(state):
    """Render the tribe allegiances table, grouped by region.

    Columns: Region | Tribe | Status

    Returns:
        Multi-line string.
    """
    scenario = state["scenario"]
    playable = get_playable_regions(scenario, state.get("capabilities"))
    lines = []
    lines.append(SEP_HEAVY)
    lines.append("TRIBES")
    lines.append(SEP)
    lines.append(f"{'Region':<14}{'Tribe':<22}{'Status':<24}")
    lines.append("-" * 60)
    for region in ALL_REGIONS:
        if region not in playable:
            continue
        tribes = list(get_tribes_in_region(region, scenario))
        # Colony Events can create a new tribal circle in a Region.
        tribes += [t for t, info in state.get("tribes", {}).items()
                   if info.get("region") == region and t not in tribes]
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
    lines.append("VICTORY (checked each Winter; margin >= +1 wins)")
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


# ============================================================================
# STATE SNAPSHOTS + DELTAS — "what changed since my last decision"
# ============================================================================

# Public tracks and persistent effects, shared by the board and its delta.
_PUBLIC_FIELDS = (
    ("available", "Available pieces"),
    ("removed_pieces", "Removed pieces"),
    ("eligibility", "Eligibility"),
    ("forced_ineligible", "Forced Ineligible"),
    ("stay_eligible", "Remain Eligible"),
    ("legions_track", "Legions track"),
    ("removed_legions", "Removed Legions"),
    ("winter_track_legions", "Winter track Legions"),
    ("spring_box_leaders", "Spring box Leaders"),
    ("capability_owners", "Capability holders"),
    ("markers", "Markers"),
    ("event_modifiers", "Event effects"),
    ("at_war", "Arverni At War"),
    ("diviciacus_in_play", "Diviciacus in play"),
    ("scenario_phase", "Scenario phase"),
)


def _visible_value(value):
    """Stable readable representation, including nested marker groups."""
    if value is None:
        return "(none)"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, dict):
        return ", ".join(f"{k}: {_visible_value(v)}"
                         for k, v in sorted(value.items(),
                                            key=lambda item: str(item[0]))) \
            or "(none)"
    if isinstance(value, (list, tuple, set, frozenset)):
        ordered = sorted(value, key=str) if isinstance(value, (set, frozenset)) \
            else value
        return ", ".join(_visible_value(v) for v in ordered) or "(none)"
    return str(value)


def format_decision_context(state):
    """Public current/upcoming cards and tracks before a human decision."""
    return format_state_summary(state) + "\n" + format_victory_state(state)


def format_board(state):
    """Complete inspectable board, used by the CLI's b/board command."""
    parts = [format_decision_context(state), format_region_table(state),
             format_tribes_table(state), "AVAILABLE PIECES"]
    for faction in FACTIONS:
        parts.append(f"  {faction}: "
                     f"{_visible_value(state.get('available', {}).get(faction))}")
    # Markers can be keyed by Region, Tribe, or an Event-specific group.
    parts.append("MARKERS / ONGOING EFFECTS")
    parts.append("  " + _visible_value(state.get("markers", {})))
    for key in ("event_modifiers", "removed_pieces"):
        if state.get(key):
            title = dict(_PUBLIC_FIELDS)[key]
            parts.append(f"  {title}: {_visible_value(state[key])}")
    for region, space in state.get("spaces", {}).items():
        extra = {k: v for k, v in space.items()
                 if k not in ("pieces", "control") and v}
        if extra:
            parts.append(f"  {region}: {_visible_value(extra)}")
    if state.get("capabilities"):
        from fs_bot.cards.card_text import format_card_text
        parts.append("ACTIVE CAPABILITY CARD TEXT")
        for card_id in sorted(state["capabilities"], key=str):
            parts.append(f"  Card {card_id}: "
                         f"{state['capabilities'][card_id]}")
            printed = format_card_text(card_id, indent="  | ",
                                       scenario=state["scenario"])
            if printed:
                parts.append(printed)
    return "\n".join(parts)


def snapshot_state(state):
    """Detached snapshot of visible board elements, safe to serialize.

    Card movement is shown in format_decision_context; private future deck
    order, RNG and transient bot bookkeeping are deliberately excluded.
    """
    from fs_bot.rules_consts import (FACTIONS, WARBAND, AUXILIA, LEGION,
                                     ALLY, CITADEL, FORT, SETTLEMENT)
    from fs_bot.board.pieces import count_pieces, get_leader_in_region
    pieces = {}
    piece_states = {}
    leaders = {}
    for region in state.get("spaces", {}):
        for f in FACTIONS:
            for pt in (WARBAND, AUXILIA, LEGION, ALLY, CITADEL, FORT,
                       SETTLEMENT):
                n = count_pieces(state, region, f, pt)
                if n:
                    pieces[(region, f, pt)] = n
                if pt in (WARBAND, AUXILIA):
                    for ps in (HIDDEN, REVEALED, SCOUTED):
                        count = count_pieces_by_state(state, region, f, pt, ps)
                        if count:
                            piece_states[(region, f, pt, ps)] = count
            ldr = get_leader_in_region(state, region, f)
            if ldr:
                leaders[(region, f)] = ldr
    tribes = {t: (ti.get("allied_faction"), ti.get("status"))
              for t, ti in state.get("tribes", {}).items()}
    snapshot = {
        "resources": dict(state.get("resources", {})),
        "pieces": pieces,
        "piece_states": piece_states,
        "leaders": leaders,
        "tribes": tribes,
        "controls": {r: space.get("control", NO_CONTROL)
                     for r, space in state.get("spaces", {}).items()},
        "space_effects": {
            r: copy.deepcopy({k: v for k, v in space.items()
                              if k not in ("pieces", "control") and v})
            for r, space in state.get("spaces", {}).items()
            if any(v for k, v in space.items()
                   if k not in ("pieces", "control"))},
        "senate": dict(state.get("senate") or {}),
        "fallen": state.get("fallen_legions", 0),
        "capabilities": dict(state.get("capabilities", {})),
    }
    for field, _label in _PUBLIC_FIELDS:
        snapshot[field] = copy.deepcopy(state.get(field))
    return snapshot


def _tribe_label(alleg):
    faction, status = alleg
    if faction:
        return f"{faction} Ally"
    if status:
        return str(status)
    return "Subdued"


def format_state_delta(before, after):
    """Human-readable lines describing what changed between snapshots."""
    lines = []
    # Resources
    for f in sorted(set(before["resources"]) | set(after["resources"])):
        b = before["resources"].get(f)
        a = after["resources"].get(f)
        if a != b:
            lines.append(f"  {f} Resources: {_visible_value(b)} -> "
                         f"{_visible_value(a)}")
    # Pieces per region
    keys = set(before["pieces"]) | set(after["pieces"])
    per_region = {}
    for k in sorted(keys):
        region, f, pt = k
        # State-specific counts below also describe flips that leave totals
        # unchanged. Avoid printing mobile-piece losses twice.
        if pt in (WARBAND, AUXILIA) and "piece_states" in before:
            continue
        d = after["pieces"].get(k, 0) - before["pieces"].get(k, 0)
        if d:
            per_region.setdefault(region, []).append(
                f"{f} {'+' if d > 0 else ''}{d} {pt}")
    for region in sorted(per_region):
        lines.append(f"  {region}: " + ", ".join(per_region[region]))
    if "piece_states" in before:
        old_states = before["piece_states"]
        new_states = after.get("piece_states", {})
        for key in sorted(set(old_states) | set(new_states)):
            b, a = old_states.get(key, 0), new_states.get(key, 0)
            if a != b:
                region, faction, pt, ps = key
                lines.append(f"  {region}: {faction} {ps} {pt}: {b} -> {a}")
    # Leaders moved
    b_l, a_l = before["leaders"], after["leaders"]
    for k in sorted(set(b_l) | set(a_l)):
        if b_l.get(k) != a_l.get(k):
            region, f = k
            if k not in a_l:
                lines.append(f"  {region}: {b_l[k]} left")
            else:
                lines.append(f"  {region}: {a_l[k]} arrived")
    # Tribes
    for t in sorted(set(before["tribes"]) | set(after["tribes"])):
        b = before["tribes"].get(t, (None, None))
        a = after["tribes"].get(t, (None, None))
        if t not in before["tribes"]:
            lines.append(f"  {t}: new Tribe ({_tribe_label(a)})")
        elif t not in after["tribes"]:
            lines.append(f"  {t}: Tribe removed")
        elif b != a:
            lines.append(f"  {t}: {_tribe_label(b)} -> {_tribe_label(a)}")
    # Senate / fallen / capabilities
    if before["senate"] != after["senate"]:
        lines.append(f"  Senate: {_visible_value(before['senate'])} -> "
                     f"{_visible_value(after['senate'])}")
    if before["fallen"] != after["fallen"]:
        lines.append(f"  Fallen Legions: {before['fallen']} -> "
                     f"{after['fallen']}")
    for cid in sorted(set(after["capabilities"]) | set(before["capabilities"]),
                      key=str):
        b, a = before["capabilities"].get(cid), after["capabilities"].get(cid)
        if b != a:
            lines.append(f"  Capability card {cid}: "
                         f"{_visible_value(b)} -> {_visible_value(a)}")
    for key, title in (("controls", "Control"),
                       ("space_effects", "Region effects")) + _PUBLIC_FIELDS:
        b, a = before.get(key), after.get(key)
        if b == a:
            continue
        if isinstance(a, dict) or isinstance(b, dict):
            b, a = b or {}, a or {}
            for entry in sorted(set(b) | set(a), key=str):
                if b.get(entry) != a.get(entry):
                    lines.append(f"  {title} ({entry}): "
                                 f"{_visible_value(b.get(entry))} -> "
                                 f"{_visible_value(a.get(entry))}")
        else:
            lines.append(f"  {title}: {_visible_value(b)} -> "
                         f"{_visible_value(a)}")
    return lines


class HumanTurnDisplay:
    """Independent, serializable change baselines for human seats.

    Store ``serialize.encode(display.snapshots)`` in save metadata and pass
    its decoded value to the constructor on resume. The caller can checkpoint
    and restore ``snapshots`` with its decision transaction.
    """

    def __init__(self, stdout, snapshots=None):
        self.stdout = stdout
        self.snapshots = copy.deepcopy(snapshots or {})

    def remember(self, state, factions):
        """Initialize missing seats without overwriting saved baselines."""
        snap = snapshot_state(state)
        for faction in factions:
            if faction not in self.snapshots:
                self.snapshots[faction] = copy.deepcopy(snap)

    def before_decision(self, state, faction, *, show_context=True):
        snap = snapshot_state(state)
        previous = self.snapshots.get(faction)
        if previous is not None:
            delta = format_state_delta(previous, snap)
            self.stdout.write(f"\n--- {faction}: changes since your last "
                              "decision ---\n")
            self.stdout.write("\n".join(delta) + "\n" if delta
                              else "  No board changes.\n")
        if show_context:
            self.stdout.write("\n" + format_decision_context(state) + "\n")
        self.stdout.flush()
        self.snapshots[faction] = snap
