"""
Trade Special Ability — §4.4.1 (Aedui).

Trade garners Aedui Resources via Supply Lines.
May accompany any type of Command.

Selection (§4.4.1):
  - Occurs in Regions that are part of any Supply Lines to Cisalpina.
  - No Leader requirement in base game.
  - Ariovistus with Diviciacus: within 1 of Diviciacus — A4.4, A4.1.2.

Procedure:
  - Player Factions declare agreement for Supply Lines.
  - Aedui receive +1 Resource (or +2 if Romans agreed) for each:
    - Aedui Allied Tribe and Aedui Citadel within Supply Lines.
    - Where Aedui Control only: each Subdued Tribe and, only if Romans
      agreed, each Roman Allied Tribe.

Reference: §4.4.1, A4.4
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS, AEDUI,
    # Piece types
    ALLY, CITADEL,
    # Leaders
    DIVICIACUS,
    # Resources
    MAX_RESOURCES,
    # Scenarios
    ARIOVISTUS_SCENARIOS,
    # Tribe restrictions
    TRIBE_FACTION_RESTRICTION,
)
from fs_bot.board.pieces import (
    count_pieces, find_leader, get_leader_in_region,
)
from fs_bot.board.control import is_controlled_by
from fs_bot.map.map_data import (
    is_adjacent, get_tribes_in_region, get_playable_regions,
)
from fs_bot.commands.common import CommandError
from fs_bot.commands.rally import has_supply_line


def trade(state, agreements=None, roman_agreed=False):
    """Execute Trade — Aedui gain Resources from Supply Lines.

    §4.4.1: Aedui receive +1 Resource (or +2 if Romans agreed) for each
    qualifying piece/tribe within Supply Lines.

    Args:
        state: Game state dict. Modified in place.
        agreements: Dict of {faction: bool} for Supply Line agreement.
        roman_agreed: True if Romans agreed to Supply Lines. This
            determines whether +1 or +2 Resources per qualifying item.

    Returns:
        dict with:
            "resources_gained": Total resources gained.
            "per_item": List of (item_type, region/tribe, amount) details.

    Raises:
        CommandError: On rule violations.
    """
    scenario = state["scenario"]
    result = {"resources_gained": 0, "per_item": []}

    per_item_value = 2 if roman_agreed else 1

    # Find all regions on Supply Lines
    supply_line_regions = set()
    for region in get_playable_regions(scenario, state.get("capabilities")):
        if has_supply_line(state, region, ROMANS, agreements):
            supply_line_regions.add(region)

    # Ariovistus Diviciacus proximity filter — A4.4, A4.1.2
    # "If the Diviciacus piece is on the map, Suborn, Trade, and Aedui Ambush
    # may occur only within a distance of one Region from Diviciacus."
    # If Diviciacus removed, no filtering (revert to base rules per A4.1.2).
    if scenario in ARIOVISTUS_SCENARIOS:
        leader_region = find_leader(state, AEDUI)
        if leader_region is not None:
            supply_line_regions = {
                r for r in supply_line_regions
                if r == leader_region or is_adjacent(r, leader_region)
            }

    if not supply_line_regions:
        return result

    total = 0

    for region in supply_line_regions:
        # Aedui Allied Tribes and Citadels — §4.4.1
        space = state["spaces"][region]
        aedui_pieces = space.get("pieces", {}).get(AEDUI, {})

        # Aedui Allies
        aedui_allies = aedui_pieces.get(ALLY, 0)
        if aedui_allies > 0:
            gain = aedui_allies * per_item_value
            total += gain
            result["per_item"].append(("aedui_ally", region, gain))

        # Aedui Citadels
        aedui_citadels = aedui_pieces.get(CITADEL, 0)
        if aedui_citadels > 0:
            gain = aedui_citadels * per_item_value
            total += gain
            result["per_item"].append(("aedui_citadel", region, gain))

        # Where Aedui Control: Subdued Tribes
        if is_controlled_by(state, region, AEDUI):
            tribes = get_tribes_in_region(region, scenario)
            for tribe in tribes:
                tribe_info = state["tribes"].get(tribe, {})
                allied_faction = tribe_info.get("allied_faction")

                if allied_faction is None:
                    # Subdued Tribe
                    gain = per_item_value
                    total += gain
                    result["per_item"].append(
                        ("subdued_tribe", tribe, gain)
                    )
                elif allied_faction == ROMANS and roman_agreed:
                    # Roman Allied Tribe — only if Romans agreed
                    gain = per_item_value
                    total += gain
                    result["per_item"].append(
                        ("roman_ally", tribe, gain)
                    )

    # Cap at MAX_RESOURCES
    current = state["resources"].get(AEDUI, 0)
    actual_gain = min(total, MAX_RESOURCES - current)
    state["resources"][AEDUI] = current + actual_gain

    result["resources_gained"] = actual_gain
    return result
