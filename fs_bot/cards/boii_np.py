"""Boii non-player choices: Card 37 and §§8.2.3, 8.3.1, 8.4.1."""

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import get_available
from fs_bot.bots.bot_common import is_ally_in_city_or_remi, random_select
from fs_bot.map.map_data import get_playable_regions_for_state


def _tribe_region(state, tribe):
    from fs_bot.cards.card_effects import _tribe_region as region_of
    return region_of(state, tribe)


def _pick_region(state, regions, tribes, limit):
    """Place/remove the most Allies in the next Region, then random ties."""
    scores = {region: min(limit, sum(_tribe_region(state, tribe) == region
                                    for tribe in tribes))
              for region in regions}
    best = max(scores.values())
    return random_select(state, sorted(region for region in regions
                                       if scores[region] == best))


def _pick_tribe(state, tribes):
    """Once the Region is selected, Cities/Remi precede other Allies."""
    preferred = [tribe for tribe in tribes
                 if is_ally_in_city_or_remi(tribe, state["scenario"])]
    return random_select(state, sorted(preferred or tribes))


def np_available(state, faction, shaded):
    """§8.1.1: an Available pool alone does not establish a legal Event target."""
    from fs_bot.cards.boii import (eligible_regions, eligible_allies,
                                   replacement_targets)
    if shaded:
        return faction == rc.ARVERNI and bool(replacement_targets(
            state, eligible_regions(state, rc.ARVERNI)))
    if faction not in (rc.ROMANS, rc.AEDUI):
        return False
    playable = set(get_playable_regions_for_state(state, faction))
    regions = [r for r in eligible_regions(state, rc.AEDUI) if r in playable]
    kind = rc.AUXILIA if faction == rc.ROMANS else rc.WARBAND
    return bool(regions and (get_available(state, faction, kind)
        or (get_available(state, faction, rc.ALLY)
            and eligible_allies(state, regions, faction))))


def derive_boii(state, faction, shaded):
    """Choose only own benefits; exhaust each selected Region before another.

    Non-player Belgae never play Boii (their Event instructions). The other
    factions have no card-specific override of the general Event priorities.
    """
    from fs_bot.cards.boii import (eligible_regions, eligible_allies,
                                   replacement_targets)

    if shaded:
        if faction != rc.ARVERNI:
            return None
        regions = list(eligible_regions(state, rc.ARVERNI))
        targets = list(replacement_targets(state, regions))
        replacements = []
        while targets and len(replacements) < 2:
            region = _pick_region(state, regions, targets, 2 - len(replacements))
            local = [tribe for tribe in targets
                     if _tribe_region(state, tribe) == region]
            while local and len(replacements) < 2:
                tribe = _pick_tribe(state, local)
                replacements.append({"tribe": tribe})
                local.remove(tribe)
                targets.remove(tribe)
            regions.remove(region)
        # §8.4.1 still removes enemy Allies when replacements are unavailable.
        return {"replacements": replacements}

    if faction not in (rc.ROMANS, rc.AEDUI):
        return None
    playable = set(get_playable_regions_for_state(state, faction))
    regions = [r for r in eligible_regions(state, rc.AEDUI) if r in playable]
    targets = list(eligible_allies(state, regions, faction))
    allies = min(2, get_available(state, faction, rc.ALLY))
    piece_type = rc.AUXILIA if faction == rc.ROMANS else rc.WARBAND
    troops = min(2, get_available(state, faction, piece_type))
    placements = []
    while regions and (troops or (allies and targets)):
        region = _pick_region(state, regions, targets, allies)
        local = [tribe for tribe in targets
                 if _tribe_region(state, tribe) == region]
        while local and allies:
            tribe = _pick_tribe(state, local)
            placements.append({"region": region, "tribe": tribe,
                               "piece_type": rc.ALLY, "count": 1})
            local.remove(tribe)
            targets.remove(tribe)
            allies -= 1
        if troops:
            placements.append({"region": region, "piece_type": piece_type,
                               "count": troops})
            troops = 0
        regions.remove(region)
    return {"place_faction": faction, "placements": placements}
