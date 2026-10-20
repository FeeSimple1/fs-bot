"""Common definitions shared across command modules.

Provides the base CommandError exception and shared helper functions
used by rally, march, raid, and seize modules.
"""

from contextlib import contextmanager

from fs_bot.rules_consts import (MARKER_DEVASTATED, MARKER_INTIMIDATED,
                                 ROMANS)
from fs_bot.board.pieces import find_leader, get_leader_in_region
from fs_bot.map.map_data import is_adjacent


class CommandError(Exception):
    """Raised when a command violates game rules."""
    pass


def _is_devastated(state, region):
    """Check if a region is Devastated — the single source of truth.

    Devastation is stored canonically as MARKER_DEVASTATED in
    state["markers"][region] (placed by the Devastate SA, cleared in Winter).
    A legacy state["spaces"][region]["devastated"] flag is also honoured so
    that callers/tests using either representation agree with the executor.
    Markers may be a dict ({MARKER_DEVASTATED: True}) or a set.
    """
    m = state.get("markers", {}).get(region) or {}
    if MARKER_DEVASTATED in m:  # key membership (dict) or membership (set)
        return True
    return bool(state.get("spaces", {}).get(region, {}).get(
        "devastated", False))


def _is_intimidated(state, region):
    """Check if a region has the Intimidated marker (Ariovistus only)."""
    markers = state.get("markers", {}).get(region, {})
    return MARKER_INTIMIDATED in markers


def check_leader_proximity(state, region, faction, named_leader, sa_name):
    """Check if region is within 1 of a named leader or has Successor.

    Standard leader proximity check used by most Special Abilities (§4.1.2):
    - Named leader: region must be same or adjacent (within 1).
    - Successor: region must be the same region.

    Args:
        state: Game state dict.
        region: Region to check.
        faction: Faction owning the leader.
        named_leader: Named leader constant (CAESAR, VERCINGETORIX, etc.).
        sa_name: Name of the SA for error messages.

    Returns:
        (True, "") if valid, (False, reason) if not.
    """
    # Card 12 unshaded (Titus Labienus): "Roman Special Abilities may
    # select Regions regardless of where the Roman leader is located."
    if faction == ROMANS:
        from fs_bot.cards.capabilities import is_capability_active
        from fs_bot.rules_consts import EVENT_UNSHADED
        if is_capability_active(state, 12, EVENT_UNSHADED):
            return (True, "")

    leader_region = find_leader(state, faction)
    if leader_region is None:
        return (False, f"{faction} leader not on map — cannot {sa_name}")

    actual_leader = get_leader_in_region(state, leader_region, faction)

    if actual_leader == named_leader:
        # Named leader: within 1 region (same or adjacent)
        if region == leader_region or is_adjacent(region, leader_region):
            return (True, "")
        return (False,
                f"Region must be within 1 of {named_leader} for {sa_name}")
    else:
        # Successor: must be same region — §4.1.2
        if region == leader_region:
            return (True, "")
        return (False,
                f"Successor must be in the same region for {sa_name}")


def is_free_action(state, faction):
    """Whether an Event's current action waives this Faction's costs (§5.4)."""
    grant = state.get("_free_action_factions", ())
    return faction in grant


def action_cost(state, faction, cost):
    """Apply only the Event Resource waiver; all other restrictions remain."""
    return 0 if is_free_action(state, faction) else cost


@contextmanager
def free_action_scope(state, faction=None):
    """Scope free-action costs, including nested grants, without leaking them."""
    from fs_bot.rules_consts import FACTIONS
    missing = object()
    previous = state.get("_free_action_factions", missing)
    prior = set() if previous is missing else set(previous)
    state["_free_action_factions"] = prior | set(FACTIONS if faction is None else (faction,))
    try:
        yield
    finally:
        if previous is missing:
            state.pop("_free_action_factions", None)
        else:
            state["_free_action_factions"] = previous


def battle_cost(state, region, faction):
    """Per-Region Battle cost, including scenario/capability exceptions."""
    from fs_bot.rules_consts import (ROMANS, GERMANS, ARVERNI, AEDUI,
        BASE_SCENARIOS, ARIOVISTUS_SCENARIOS, ROMAN_BATTLE_COST,
        GALLIC_BATTLE_COST, EVENT_SHADED)
    if is_free_action(state, faction):
        return 0
    if ((faction == GERMANS and state["scenario"] in BASE_SCENARIOS)
            or (faction == ARVERNI and state["scenario"] in ARIOVISTUS_SCENARIOS)):
        return 0
    cost = ROMAN_BATTLE_COST if faction == ROMANS else GALLIC_BATTLE_COST
    if _is_devastated(state, region):
        cost *= 2
    if faction == AEDUI:
        from fs_bot.cards.capabilities import is_capability_active
        if is_capability_active(state, 43, EVENT_SHADED):
            cost *= 2
    return cost


def free_action(function):
    """Decorate a (state, faction, ...) Event action, including its planner."""
    from functools import wraps
    @wraps(function)
    def scoped(state, faction, *args, **kwargs):
        with free_action_scope(state, faction):
            return function(state, faction, *args, **kwargs)
    return scoped
