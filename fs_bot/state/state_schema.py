"""
State schema module — Master game state dictionary.

Builds an empty initial state with correct Available pools for the scenario.
All constants from rules_consts.py.

Reference: §1.4.1, §1.8, §6.5, §6.6, A1.4, A1.8
"""

import random

from fs_bot.rules_consts import (
    # Factions
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    FACTIONS,
    # Piece types
    LEADER, LEGION, AUXILIA, WARBAND, FORT, ALLY, CITADEL, SETTLEMENT,
    FLIPPABLE_PIECES,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Caps
    CAPS_BASE, CAPS_ARIOVISTUS,
    # Scenarios
    BASE_SCENARIOS, ARIOVISTUS_SCENARIOS, ALL_SCENARIOS,
    # Regions
    ALL_REGIONS, PROVINCIA,
    # Tribes
    BASE_TRIBES, ARIOVISTUS_TRIBES,
    TRIBE_TO_REGION,
    # Senate
    UPROAR, INTRIGUE, ADULATION,
    # Legions track
    LEGIONS_ROW_BOTTOM, LEGIONS_ROW_MIDDLE, LEGIONS_ROW_TOP,
    LEGIONS_ROWS, LEGIONS_PER_ROW,
    # Victory
    MAX_RESOURCES,
    # Eligibility
    ELIGIBLE,
    # Control
    NO_CONTROL,
    # Markers
    MARKER_GALLIA_TOGATA,
)

from fs_bot.map.map_data import (
    ALL_REGION_DATA,
    get_playable_regions,
    get_tribes_in_region,
)


def build_initial_state(scenario, seed=None):
    """Create an empty game state with correct pools for the scenario.

    This creates a state with all pieces in Available pools (or on the
    Legions track for Legions), all resources at 0, empty map. Scenario
    setup (setup.py) then places pieces and sets values.

    Args:
        scenario: Scenario identifier from rules_consts.
        seed: Optional RNG seed for deterministic replay.

    Returns:
        Game state dictionary.

    Raises:
        ValueError: If scenario is not valid.
    """
    if scenario not in ALL_SCENARIOS:
        raise ValueError(f"Unknown scenario: {scenario}")

    caps = CAPS_ARIOVISTUS if scenario in ARIOVISTUS_SCENARIOS else CAPS_BASE

    # Build Available pools
    available = {}
    for faction in FACTIONS:
        faction_caps = caps.get(faction, {})
        available[faction] = {}
        for piece_type, cap in faction_caps.items():
            if piece_type == LEGION:
                # Legions go on Legions track, not Available — §1.4.1
                continue
            if piece_type == LEADER:
                # Leaders start in Available unless cap is 0
                available[faction][LEADER] = cap
            else:
                available[faction][piece_type] = cap

    # Build spaces — one entry per region
    spaces = {}
    playable = get_playable_regions(scenario)
    for region in ALL_REGIONS:
        spaces[region] = {
            "pieces": {},
            "control": NO_CONTROL,
        }

    # Build tribe statuses
    tribes_for_scenario = (
        ARIOVISTUS_TRIBES if scenario in ARIOVISTUS_SCENARIOS
        else BASE_TRIBES
    )
    tribes = {}
    for tribe in tribes_for_scenario:
        tribes[tribe] = {
            "status": None,  # None = Subdued (empty circle), or set later
            "allied_faction": None,
        }

    # Legions track — all Legions start on bottom rows
    legion_cap = caps.get(ROMANS, {}).get(LEGION, 0)
    legions_track = {row: 0 for row in LEGIONS_ROWS}
    remaining = legion_cap
    for row in LEGIONS_ROWS:
        place = min(LEGIONS_PER_ROW, remaining)
        legions_track[row] = place
        remaining -= place
        if remaining == 0:
            break

    # Resources — all start at 0, scenario setup will set them
    resources = {}
    for faction in FACTIONS:
        if faction == GERMANS and scenario in BASE_SCENARIOS:
            continue  # Germans don't track resources in base — §1.8
        resources[faction] = 0

    # Eligibility — all start Eligible
    eligibility = {faction: ELIGIBLE for faction in FACTIONS}

    state = {
        "scenario": scenario,
        "spaces": spaces,
        "available": available,
        "resources": resources,
        "senate": {
            "position": None,  # Set by scenario setup
            "firm": False,
        },
        "legions_track": legions_track,
        "fallen_legions": 0,
        "removed_legions": 0,
        "eligibility": eligibility,
        "capabilities": {},
        "markers": {},  # Per-region/tribe markers (Devastated, etc.)
        "tribes": tribes,
        "rng": random.Random(seed),
        "current_card": None,
        "next_card": None,
        "winter_count": 0,
        "deck": [],
        "played_cards": [],
        # Ariovistus-specific
        "at_war": scenario in ARIOVISTUS_SCENARIOS,  # Arverni At War marker
        "diviciacus_in_play": False,  # Tracked separately — A1.4
    }

    return state


def validate_state(state):
    """Validate state integrity: piece counts reconcile with caps.

    Checks that for each faction/piece_type:
        on_map + available + track/fallen/removed = cap

    Args:
        state: Game state dict.

    Returns:
        List of error strings. Empty list means valid.
    """
    errors = []
    scenario = state["scenario"]
    caps = CAPS_ARIOVISTUS if scenario in ARIOVISTUS_SCENARIOS else CAPS_BASE

    for faction in FACTIONS:
        faction_caps = caps.get(faction, {})
        for piece_type, cap in faction_caps.items():
            if piece_type == LEGION:
                # Legions: map + track + fallen + removed
                #          + winter_track = cap
                on_map = 0
                for region, space in state["spaces"].items():
                    on_map += space.get("pieces", {}).get(
                        faction, {}
                    ).get(LEGION, 0)
                on_track = sum(
                    state["legions_track"].get(row, 0)
                    for row in LEGIONS_ROWS
                )
                fallen = state.get("fallen_legions", 0)
                removed = state.get("removed_legions", 0)
                winter_track = state.get("winter_track_legions", 0)
                total = (on_map + on_track + fallen + removed
                         + winter_track)
                if total != cap:
                    errors.append(
                        f"{faction} {LEGION}: map({on_map}) + "
                        f"track({on_track}) + fallen({fallen}) + "
                        f"removed({removed}) + winter_track("
                        f"{winter_track}) = {total}, cap = {cap}"
                    )
                continue

            if piece_type == LEADER:
                # Leader: on_map (0 or 1) + available = cap
                on_map = 0
                for region, space in state["spaces"].items():
                    f_pieces = space.get("pieces", {}).get(faction, {})
                    if f_pieces.get(LEADER) is not None:
                        on_map += 1
                avail = state["available"].get(faction, {}).get(LEADER, 0)
                total = on_map + avail

                # Diviciacus special case: removed from play reduces total
                if (faction == AEDUI and scenario in ARIOVISTUS_SCENARIOS
                        and cap == 1):
                    # Diviciacus can be removed from play entirely
                    if total <= cap:
                        continue  # OK: may be 0 if removed from play
                    errors.append(
                        f"{faction} {LEADER}: map({on_map}) + "
                        f"available({avail}) = {total}, cap = {cap}"
                    )
                    continue

                if total != cap:
                    errors.append(
                        f"{faction} {LEADER}: map({on_map}) + "
                        f"available({avail}) = {total}, cap = {cap}"
                    )
                continue

            # All other piece types: on_map + available = cap
            on_map = 0
            for region, space in state["spaces"].items():
                f_pieces = space.get("pieces", {}).get(faction, {})
                if piece_type in FLIPPABLE_PIECES:
                    for ps in (HIDDEN, REVEALED, SCOUTED):
                        on_map += f_pieces.get(ps, {}).get(piece_type, 0)
                else:
                    on_map += f_pieces.get(piece_type, 0)

            avail = state["available"].get(faction, {}).get(piece_type, 0)
            total = on_map + avail
            if total != cap:
                errors.append(
                    f"{faction} {piece_type}: map({on_map}) + "
                    f"available({avail}) = {total}, cap = {cap}"
                )

    return errors
