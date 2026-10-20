"""NP choices for Gobannitio/Correus: Card Reference 26/64, §8.3–8.4."""
from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces_by_state, get_available
from fs_bot.cards.card_effects import _tribe_region, _tribe_piece_type
from fs_bot.bots.bot_common import (get_faction_targeting_order, random_select,
                                     is_ally_in_city_or_remi)


def _tribes(state, region):
    return [t for t in sorted(state['tribes']) if _tribe_region(state, t) == region]


def _ordered_allies(state, region, recipient, *, include_own=False, owners=None):
    order = get_faction_targeting_order(recipient, state['scenario'])
    candidates = [t for t in _tribes(state, region)
                  if _tribe_piece_type(state, t) == rc.ALLY
                  and (owners is None or state['tribes'][t]['allied_faction'] in owners)
                  and (include_own or state['tribes'][t]['allied_faction'] != recipient)]
    def priority(tribe):
        owner = state['tribes'][tribe]['allied_faction']
        own = owner == recipient
        city_or_remi = is_ally_in_city_or_remi(tribe, state["scenario"])
        # §8.4.1 reverses piece priorities when removing own pieces.
        return (own, city_or_remi if own else not city_or_remi,
                order.index(owner) if owner in order else len(order))
    result = []
    while candidates:
        first = min(priority(t) for t in candidates)
        tribe = random_select(state, [t for t in candidates if priority(t) == first])
        result.append(tribe)
        candidates.remove(tribe)
    return result


def _placements(state, region, recipient, removals, limit):
    available = get_available(state, recipient, rc.ALLY) + sum(
        state['tribes'][t]['allied_faction'] == recipient for t in removals)
    candidates = [t for t in _tribes(state, region)
                  if t in removals or (state['tribes'][t].get('allied_faction') is None
                                      and state['tribes'][t].get('status') in (None, rc.ALLIED))]
    result = []
    while candidates and len(result) < min(available, limit):
        # §8.4.1: Cities/Remi before other Allied Tribes, then equal ties.
        preferred = [t for t in candidates if is_ally_in_city_or_remi(t, state["scenario"])]
        tribe = random_select(state, preferred or candidates)
        result.append(tribe)
        candidates.remove(tribe)
    return result


def derive_gobannitio(state, faction, shaded):
    if not shaded:
        if faction not in (rc.ROMANS, rc.AEDUI):
            return None
        own_citadel = (state['tribes'][rc.TRIBE_ARVERNI].get('allied_faction') == faction
                       and _tribe_piece_type(state, rc.TRIBE_ARVERNI) == rc.CITADEL)
        kind = (rc.CITADEL if faction == rc.AEDUI
                and (get_available(state, faction, rc.CITADEL) or own_citadel) else rc.ALLY)
        return {'place_faction': faction, 'place_type': kind}
    removals = _ordered_allies(state, rc.ARVERNI_REGION, rc.ARVERNI)
    return {'ally_removals': removals,
            'ally_placements': _placements(state, rc.ARVERNI_REGION, rc.ARVERNI,
                                           removals, len(state['tribes']))}


def derive_correus(state, faction, shaded):
    if shaded:
        removals = _ordered_allies(state, rc.ATREBATES, rc.BELGAE, include_own=True)[:2]
        return {'ally_removals': removals,
                'belgae_ally_placements': _placements(state, rc.ATREBATES, rc.BELGAE,
                                                     removals, 2)}
    replacements = [{'from_type': rc.ALLY, 'tribe': t}
                    for t in _ordered_allies(state, rc.ATREBATES, faction,
                                             owners=(rc.BELGAE,))][:8]
    for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        number = count_pieces_by_state(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, visibility)
        replacements.extend({'from_type': rc.WARBAND, 'piece_state': visibility}
                            for _ in range(min(number, 8 - len(replacements))))
    return {'replacements': replacements} if replacements else None
