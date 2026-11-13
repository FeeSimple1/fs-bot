"""Printed non-player Capability removal priorities for Shifting Loyalties."""

from fs_bot import rules_consts as rc
from fs_bot.cards.capabilities import get_active_capabilities, get_capability_owner
from fs_bot.cards.card_data import get_faction_order


# Factions whose actions the unshaded and shaded Capability texts affect.
# The cards with a selected holder read that holder from the live board.
_AFFECTED_FACTIONS = {
    10: ((rc.ROMANS,), ()),
    12: ((rc.ROMANS,), (rc.ROMANS,)),
    13: ((rc.ROMANS,), (rc.ROMANS,)),
    15: ((rc.ROMANS,), (rc.ROMANS,)),
    27: ((rc.ARVERNI,), (rc.ARVERNI,)),
    30: ((rc.ARVERNI,), (rc.ARVERNI,)),
    38: ((rc.ROMANS, rc.AEDUI), (rc.ROMANS, rc.AEDUI)),
    39: ((rc.AEDUI,), (rc.AEDUI,)),
    43: ((rc.AEDUI,), (rc.AEDUI,)),
    55: ((rc.ROMANS,), (rc.BELGAE,)),
    59: ((rc.ROMANS,), ()),
    63: ((rc.ROMANS,), ()),
    'A22': ((rc.GERMANS, rc.ROMANS), (rc.GERMANS,)),
    'A31': ((rc.GERMANS,), (rc.GERMANS,)),
    'A33': ((rc.GERMANS,), (rc.GERMANS,)),
    'A38': ((rc.AEDUI,), (rc.AEDUI,)),
    'A63': ((rc.ROMANS,), ()),
    'A70': ((rc.BELGAE,), (rc.BELGAE,)),
    rc.CARD_O38: ((rc.AEDUI,), (rc.ROMANS, rc.AEDUI)),
}


def _affected_factions(state, card_id, side):
    shaded = side == rc.EVENT_SHADED
    if card_id == 8 or (shaded and card_id in (10, 25, 59, 63, 'A63')):
        owner = get_capability_owner(state, card_id)
        return (owner,) if owner is not None else ()
    unshaded_factions, shaded_factions = _AFFECTED_FACTIONS.get(card_id, ((), ()))
    return shaded_factions if shaded else unshaded_factions


def removal_candidates(state, faction):
    """Return the best eligible priority tier without consuming a tie roll."""
    scenario = state['scenario']
    if faction in (rc.ROMANS, rc.AEDUI):
        side = rc.EVENT_SHADED
        opponents = {rc.BELGAE, rc.GERMANS if scenario in rc.ARIOVISTUS_SCENARIOS else rc.ARVERNI}
    else:
        side = rc.EVENT_UNSHADED
        opponents = {rc.ROMANS, rc.AEDUI}
    players = opponents.difference(state.get('non_player_factions', ()))
    active = get_active_capabilities(state)
    primary, fallback = [], []
    for card_id in sorted(active, key=str):
        if active[card_id] != side:
            continue
        affected = _affected_factions(state, card_id, side)
        if players.intersection(affected):
            primary.append(card_id)
        elif faction == rc.AEDUI:
            if get_faction_order(card_id, scenario)[:1] == (rc.AEDUI,):
                fallback.append(card_id)
        elif faction in affected:
            fallback.append(card_id)
    return primary or fallback


def derive_params(state, faction, _shaded):
    """Choose one tied Capability using the game RNG (§8.2.3, §8.3.4)."""
    if faction not in state.get('non_player_factions', ()):
        return None
    from fs_bot.bots.bot_common import random_select

    candidates = removal_candidates(state, faction)
    if not candidates:
        raise ValueError('Shifting Loyalties has no Capability matching the bot instructions.')
    return {'target_capability': random_select(state, candidates)}
