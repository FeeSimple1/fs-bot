"""
capabilities.py — Manage active capabilities in game state.

Per §5.3: Capabilities persist for the rest of the game unless altered
by a later Event (§5.1.2 — "Dueling Events" can replace or remove
capabilities). Track which side (shaded/unshaded) is active.

State storage: state["capabilities"] is a dict:
    {card_id: EVENT_SHADED or EVENT_UNSHADED}

Source: §5.3, §5.1.2, Card Reference, A Card Reference
"""

from fs_bot.rules_consts import (
    EVENT_SHADED, EVENT_UNSHADED,
    CAPABILITY_CARDS, CAPABILITY_CARDS_ARIOVISTUS,
    ARIOVISTUS_SCENARIOS,
)


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
    state["capabilities"][card_id] = shaded_or_unshaded


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
    return state["capabilities"].pop(card_id, None)


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
    _ensure_capabilities(state)
    if card_id not in state["capabilities"]:
        return False
    if shaded_or_unshaded is None:
        return True
    return state["capabilities"][card_id] == shaded_or_unshaded


def get_active_capabilities(state):
    """Return dict of all active capabilities.

    Returns:
        dict {card_id: EVENT_SHADED or EVENT_UNSHADED}
    """
    _ensure_capabilities(state)
    return dict(state["capabilities"])


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
