"""Non-player placement and replacement plans for A35, A51 and A60."""

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_available, tribe_has_ally_disc
from fs_bot.map.map_data import (
    get_adjacent_for_state, get_playable_regions_for_state, get_tribes_in_region_for_state,
    is_region_playable,
)


def nasua_regions(state):
    near = set(rc.GERMANIA_REGIONS)
    for region in rc.GERMANIA_REGIONS:
        near.update(get_adjacent_for_state(state, region, rc.GERMANS))
    return sorted(near.intersection(get_playable_regions_for_state(state, rc.GERMANS)))


def _nasua_shaded_choices(state):
    regions = nasua_regions(state)
    settlements = []
    if get_available(state, rc.GERMANS, rc.SETTLEMENT):
        settlements = [region for region in regions
                       if not count_pieces(state, region, rc.GERMANS, rc.SETTLEMENT)]
    warbands = min(8, get_available(state, rc.GERMANS, rc.WARBAND)) if regions else 0
    return regions, settlements, warbands


def _nasua_unshaded_plan(state, faction):
    if faction not in (rc.ROMANS, *rc.GALLIC_FACTIONS) or not is_region_playable(state, rc.TREVERI, faction):
        return None
    tribe = state['tribes'].get(rc.TRIBE_TREVERI)
    if tribe is None:
        return None
    troop = rc.AUXILIA if faction == rc.ROMANS else rc.WARBAND
    count = min(4 if troop == rc.AUXILIA else 8, get_available(state, faction, troop))
    if faction == rc.ROMANS and count < 4:
        return None  # The Roman instruction requires the full four Auxilia.
    gains_ally = tribe.get('allied_faction') != faction and get_available(state, faction, rc.ALLY) > 0
    if not (gains_ally or count):
        return None
    return {'ally_faction': faction, 'piece_faction': faction, 'piece_type': troop, 'count': count}


def nasua_available(state, faction, shaded):
    if not shaded:
        return _nasua_unshaded_plan(state, faction) is not None
    _, settlements, warbands = _nasua_shaded_choices(state)
    return bool(settlements or warbands)


def derive_nasua(state, faction, shaded):
    if not shaded:
        return _nasua_unshaded_plan(state, faction)

    from fs_bot.bots.bot_common import random_select

    regions, settlements, warbands = _nasua_shaded_choices(state)
    placements = []
    if settlements or warbands:
        # A8.3.1 ranks Settlements with Citadels. Finish placing in that
        # Region before considering another one. Warbands have no stack cap.
        region = random_select(state, settlements or regions)
        if settlements:
            placements.append({'region': region, 'piece_type': rc.SETTLEMENT})
        if warbands:
            placements.append({'region': region, 'piece_type': rc.WARBAND, 'count': warbands})
    return {'placements': placements}


def derive_bibrax(_state, faction, shaded):
    """Choose the executor's own troops for unshaded A51 (§8.2.3)."""
    if shaded:
        return None
    troop = {rc.ROMANS: rc.AUXILIA, rc.AEDUI: rc.WARBAND}.get(faction)
    return {'piece_type': troop} if troop is not None else None


def _iccius_allies(state):
    return [tribe for tribe in get_tribes_in_region_for_state(state, rc.ATREBATES)
            if tribe_has_ally_disc(state, rc.ATREBATES, tribe, rc.ROMANS)]


def iccius_available(state):
    return bool(_iccius_allies(state) or count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA))


def derive_iccius(state, faction, shaded):
    if not shaded:
        return None

    from fs_bot.bots.bot_common import is_ally_in_city_or_remi, random_select

    # §§8.3.1 and 8.4.1 prioritize Allies before Auxilia and Remi before
    # ordinary Allies. Replacement pool shortages do not save the sources.
    allies = _iccius_allies(state)
    replacements = []
    while allies and len(replacements) < 5:
        preferred = [tribe for tribe in allies if is_ally_in_city_or_remi(tribe, state['scenario'])]
        tribe = random_select(state, preferred or allies)
        replacements.append({'from_type': rc.ALLY, 'tribe': tribe})
        allies.remove(tribe)
    for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        available = count_pieces_by_state(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, visibility)
        count = min(available, 5 - len(replacements))
        replacements.extend({'from_type': rc.AUXILIA, 'piece_state': visibility} for _ in range(count))
    return {'replacements': replacements}
