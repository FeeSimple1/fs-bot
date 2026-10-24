"""
capabilities.py — Manage active capabilities in game state.

Per §5.3: Capabilities persist for the rest of the game unless altered
by a later Event (§5.1.2 — "Dueling Events" can replace or remove
capabilities). Track which side (shaded/unshaded) is active.

State storage: state["capabilities"] is a dict:
    {card_id: EVENT_SHADED or EVENT_UNSHADED}
Owner-scoped capabilities ("Take this card" / "Place near a Faction" —
cards 8, 10 shaded, 59 shaded, 63 shaded) additionally record the owning
Faction in state["capability_owners"]: {card_id: faction}.

Source: §5.3, §5.1.2, Card Reference, A Card Reference
"""

from fs_bot.rules_consts import (
    EVENT_SHADED, EVENT_UNSHADED,
    CAPABILITY_CARDS, CAPABILITY_CARDS_ARIOVISTUS,
    ARIOVISTUS_SCENARIOS,
)


# Companion event_modifiers set by capability handlers, keyed by
# (card_id, side). Cleared when the capability is removed (card 50
# Shifting Loyalties) or replaced by its other side (§5.1.2 Dueling
# Events) — previously these leaked and stayed in effect forever.
_CAPABILITY_MODIFIERS = {
    ("A31", EVENT_UNSHADED): ("card_A31_no_ario_double",
                              "card_A31_cancel_german_benefits"),
    ("A63", EVENT_UNSHADED): ("card_A63_quarters_devastated_only",),
    ("A22", EVENT_UNSHADED): ("card_A22_no_intimidate_romans",),
    ("A38", EVENT_UNSHADED): ("card_A38_suborn_enhanced",),
}


def _clear_companion_modifiers(state, card_id, side):
    mods = state.get("event_modifiers")
    if not mods:
        return
    for key in _CAPABILITY_MODIFIERS.get((card_id, side), ()):
        mods.pop(key, None)


def _ensure_capabilities(state):
    """Ensure state has a capabilities dict."""
    if "capabilities" not in state:
        state["capabilities"] = {}


def activate_capability(state, card_id, shaded_or_unshaded):
    """Activate a capability card in game state.

    Per §5.3, the capability persists until removed by a later Event.
    Per §5.1.2 (Dueling Events), if the capability is already active
    on a different side, the new activation replaces it.

    Args:
        state: game state dict
        card_id: card identifier (int or str)
        shaded_or_unshaded: EVENT_SHADED or EVENT_UNSHADED
    """
    if shaded_or_unshaded not in (EVENT_SHADED, EVENT_UNSHADED):
        raise ValueError(
            f"shaded_or_unshaded must be EVENT_SHADED or EVENT_UNSHADED, "
            f"got {shaded_or_unshaded!r}"
        )
    _ensure_capabilities(state)
    # §5.1.2 Dueling Events: replacing the other side clears that side's
    # companion modifiers.
    prev = get_active_capabilities(state).get(card_id)
    if prev is not None and prev != shaded_or_unshaded:
        _clear_companion_modifiers(state, card_id, prev)
    if card_id == "A38" and shaded_or_unshaded == EVENT_SHADED:
        # Older saves could retain the unshaded modifier alongside the
        # shaded capability. Replaying the shaded side must clear it too.
        _clear_companion_modifiers(state, card_id, EVENT_UNSHADED)
    state["capabilities"][card_id] = shaded_or_unshaded


def set_capability_owner(state, card_id, faction):
    """Record the Faction that holds an owner-scoped capability card
    ("Take this card ..." / "Place this card near a ... Faction")."""
    state.setdefault("capability_owners", {})[card_id] = faction


def get_capability_owner(state, card_id):
    """The Faction holding an owner-scoped capability card, or None."""
    return state.get("capability_owners", {}).get(card_id)


def deactivate_capability(state, card_id):
    """Remove a capability from play.

    Per §5.1.2, a later Event can remove a capability entirely.
    Also used by card 50 (Shifting Loyalties) to remove any capability.

    Args:
        state: game state dict
        card_id: card identifier

    Returns:
        The side that was active (EVENT_SHADED/EVENT_UNSHADED),
        or None if the capability was not active.
    """
    _ensure_capabilities(state)
    state.get("capability_owners", {}).pop(card_id, None)
    side = get_active_capabilities(state).get(card_id)
    state["capabilities"].pop(card_id, None)
    if side is not None:
        _clear_companion_modifiers(state, card_id, side)
    if card_id == "A38":
        _clear_companion_modifiers(state, card_id, EVENT_UNSHADED)
    return side


def is_capability_active(state, card_id, shaded_or_unshaded=None):
    """Check if a capability is active in game state.

    Args:
        state: game state dict
        card_id: card identifier
        shaded_or_unshaded: if None, returns True if capability is active
            on either side. If EVENT_SHADED or EVENT_UNSHADED, returns
            True only if active on that specific side.

    Returns:
        bool
    """
    active = get_active_capabilities(state)
    if card_id not in active:
        return False
    if shaded_or_unshaded is None:
        return True
    return active[card_id] == shaded_or_unshaded


def get_active_capabilities(state):
    """Return dict of all active capabilities.

    Returns:
        dict {card_id: EVENT_SHADED or EVENT_UNSHADED}
    """
    active = dict(state.get("capabilities", {}))
    # Before the Vergobret lifecycle fix its unshaded Capability was saved
    # only as this modifier. Interpret those saves without rewriting them;
    # an explicit side always takes precedence over a stale modifier.
    if ("A38" not in active and state.get("event_modifiers", {}).get(
            "card_A38_suborn_enhanced")):
        active["A38"] = EVENT_UNSHADED
    return active


def is_valid_capability(card_id, scenario=None):
    """Check if a card_id is a valid capability card.

    Args:
        card_id: card identifier
        scenario: if provided, checks scenario-appropriate capability sets

    Returns:
        bool
    """
    if scenario is not None and scenario in ARIOVISTUS_SCENARIOS:
        return (card_id in CAPABILITY_CARDS or
                card_id in CAPABILITY_CARDS_ARIOVISTUS)
    return card_id in CAPABILITY_CARDS
