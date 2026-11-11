"""Britannia targets and placement pools for shaded Card Reference 57."""

from copy import deepcopy

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

    options = removal_options(state)
    if removal is None and not options:
        return
    if removal not in options:
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


def _ranked_choices(state, faction):
    from fs_bot.bots.bot_common import get_faction_targeting_order

    if faction not in rc.GALLIC_FACTIONS or not is_region_playable(state, rc.BRITANNIA, faction):
        return []
    order = get_faction_targeting_order(faction, state['scenario'])
    warbands = warband_limits(state).get(faction, 0)
    choices = []
    for removal in removal_options(state) or [None]:
        trial = state
        removed_owner = None
        if removal is not None:
            trial = deepcopy({key: value for key, value in state.items() if key != 'decision_agent'})
            if removal['type'] == 'ally':
                removed_owner = state['tribes'][removal['tribe']]['allied_faction']
            remove_target(trial, removal)
        allies = ally_options(trial)
        own_tribes = [tribe for tribe, owner in allies if owner == faction]
        if allies and not own_tribes:
            continue  # §8.2.3: a selectable benefit must go to the executor.
        net_allies = int(bool(own_tribes)) - int(removed_owner == faction)
        if faction == rc.BELGAE and net_allies <= 0:
            continue  # The Belgic instruction requires an Ally or Citadel gain.
        enemy_ally = removed_owner in order
        removes_marker = removal is not None and removal['type'] == 'dispersed'
        if net_allies > 0 or enemy_ally or removes_marker or warbands:
            priority = -order.index(removed_owner) if enemy_ally else 0
            choices.append((removal, own_tribes, (net_allies, enemy_ally, priority)))
    return choices


def np_available(state, faction):
    return bool(_ranked_choices(state, faction))


def derive_params(state, faction, shaded):
    """Select the compulsory effects and maximize own Warbands under §8.4."""
    from fs_bot.bots.bot_common import random_select

    if not shaded:
        return None
    choices = _ranked_choices(state, faction)
    if not choices:
        return None
    best = max(score for _, _, score in choices)
    removal, tribes, _ = random_select(state, [choice for choice in choices if choice[2] == best])
    return {'removal': removal,
            'ally_tribe': random_select(state, tribes) if tribes else None,
            'ally_faction': faction if tribes else None,
            'warband_faction': faction,
            'warband_count': warband_limits(state).get(faction, 0)}
