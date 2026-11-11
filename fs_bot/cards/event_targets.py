"""Region eligibility shared by Event resolution and planning."""

from fs_bot import rules_consts as rc
from fs_bot.board.control import get_controlled_regions
from fs_bot.board.pieces import count_pieces, find_leader, get_available, get_leader_in_region
from fs_bot.map.map_data import (
    get_adjacent_for_state, get_playable_regions_for_state,
    get_region_for_tribe_for_state, get_tribe_restriction, get_tribes_in_region_for_state,
)


def alaudae_regions(state):
    playable = get_playable_regions_for_state(state, rc.ROMANS)
    return tuple(region for region in get_controlled_regions(state, rc.ROMANS)
                 if region in playable)


def sacking_regions(state, faction):
    if not faction:
        return ()
    return tuple(region for region in get_playable_regions_for_state(state, faction)
                 if count_pieces(state, region, faction, rc.CITADEL)
                 and count_pieces(state, region, rc.ROMANS, rc.LEGION))


def hostages_tribes(state):
    """Subdued circles with Roman pieces where the non-Roman placements can stack."""
    targets = {}
    # Gallia Togata's Roman-only stacking applies to every Hostages placement.
    for region in get_playable_regions_for_state(state, rc.ARVERNI):
        if not count_pieces(state, region, rc.ROMANS):
            continue
        for tribe in get_tribes_in_region_for_state(state, region):
            info = state['tribes'].get(tribe)
            if (info is not None and info.get('allied_faction') is None
                    and info.get('status') in (None, rc.ALLIED)
                    and get_region_for_tribe_for_state(state, tribe) == region):
                targets[tribe] = region
    return targets


def hostages_ally_factions(state, tribe):
    """A Colony uses its own circle, even if its name matches a printed Tribe."""
    info = state['tribes'][tribe]
    restriction = None if info.get('region') else get_tribe_restriction(tribe)
    return tuple(faction for faction in rc.GALLIC_FACTIONS
                 if restriction in (None, faction))


def abatis_regions(state, faction):
    """Card A64 counts the executor's Hidden, Revealed and Scouted Warbands."""
    if faction not in rc.FACTIONS:
        return ()
    return tuple(region for region in get_playable_regions_for_state(state, faction)
                 if count_pieces(state, region, faction, rc.WARBAND))


def roman_leader_regions(state, *, caesar_only=False):
    origin = find_leader(state, rc.ROMANS)
    if origin is None or (caesar_only
                          and get_leader_in_region(state, origin, rc.ROMANS) != rc.CAESAR):
        return ()
    within_one = {origin, *get_adjacent_for_state(state, origin, rc.ROMANS)}
    return tuple(region for region in get_playable_regions_for_state(state, rc.ROMANS)
                 if region in within_one)


def successor_regions(state, faction):
    """Lucterius and Flight of Ambiorix return the Leader symbol-up."""
    origin = find_leader(state, faction)
    if origin is None:
        if not get_available(state, faction, rc.LEADER):
            return ()
    elif get_leader_in_region(state, origin, faction) != rc.SUCCESSOR:
        return ()
    playable = get_playable_regions_for_state(state, faction)
    if faction == rc.BELGAE:
        # Card 56 Tips name the exact Regions outside Germania.
        destinations = (*rc.GERMANIA_REGIONS, rc.MORINI, rc.NERVII,
                        rc.TREVERI, rc.SEQUANI)
        return tuple(region for region in destinations if region in playable)
    return playable
