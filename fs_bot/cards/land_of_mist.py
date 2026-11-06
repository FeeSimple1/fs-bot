"""Britannia targets and placement pools for shaded Card Reference 57."""

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import get_available
from fs_bot.cards.boii import eligible_allies
from fs_bot.map.map_data import is_region_playable


def removal_options(state):
    from fs_bot.cards.card_effects import _tribe_piece_type, _tribe_region

    if not is_region_playable(state, rc.BRITANNIA):
        return []
    options = []
    for tribe, info in sorted(state['tribes'].items()):
        if _tribe_region(state, tribe) != rc.BRITANNIA:
            continue
        if _tribe_piece_type(state, tribe) == rc.ALLY:
            options.append({'type': 'ally', 'tribe': tribe})
        elif info.get('status') in (rc.MARKER_DISPERSED, rc.MARKER_DISPERSED_GATHERING):
            options.append({'type': 'dispersed', 'tribe': tribe})
    return options


def remove_target(state, removal):
    from fs_bot.cards.card_effects import _unally_tribe

    if removal is None:
        return
    if removal not in removal_options(state):
        raise ValueError('Choose an Ally or Dispersed marker in Britannia')
    tribe = removal['tribe']
    if removal['type'] == 'ally':
        _unally_tribe(state, tribe)
    else:
        state['tribes'][tribe]['status'] = None


def ally_options(state):
    return [(tribe, faction) for faction in rc.GALLIC_FACTIONS
            if get_available(state, faction, rc.ALLY)
            for tribe in eligible_allies(state, (rc.BRITANNIA,), faction)]


def warband_limits(state):
    return {faction: min(4, available) for faction in rc.GALLIC_FACTIONS
            if is_region_playable(state, rc.BRITANNIA, faction)
            and (available := get_available(state, faction, rc.WARBAND))}
