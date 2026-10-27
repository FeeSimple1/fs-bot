"""A66's delayed NP placements: §§8.2.3, 8.3.1 and 8.4.1."""

from fs_bot.bots.bot_common import is_ally_in_city_or_remi, random_select
from fs_bot.cards.card_effects import _tribe_region


def np_placements(state, faction, regions, tribes, allies, warbands):
    """Plan within the caller's legal scope without placing any pieces.

    ``regions`` and ``tribes`` already obey the recipient's geography and
    stacking rules; both counts already reflect Available pieces and legal
    destinations. ``faction`` identifies that recipient, which need not be the
    card holder. Equal choices consume only the game's seeded RNG.
    """
    remaining_regions = sorted(set(regions))
    remaining_tribes = sorted(set(tribes))
    answer = {'allies': [], 'warbands': []}
    while remaining_regions and (allies or warbands):
        scores = {region: min(allies, sum(_tribe_region(state, tribe) == region
                                         for tribe in remaining_tribes))
                  for region in remaining_regions}
        most_allies = max(scores.values())
        # Every offered Region can receive every remaining Warband, so the
        # other-piece priority is tied after comparing legal Ally placements.
        region = random_select(state, [candidate for candidate in remaining_regions
                                       if scores[candidate] == most_allies])
        local = [tribe for tribe in remaining_tribes
                 if _tribe_region(state, tribe) == region]
        while local and allies:
            preferred = [tribe for tribe in local
                         if is_ally_in_city_or_remi(tribe, state['scenario'])]
            tribe = random_select(state, preferred or local)
            answer['allies'].append(tribe)
            local.remove(tribe)
            remaining_tribes.remove(tribe)
            allies -= 1
        if warbands:
            # §8.3.1 completes actions in this Region before selecting another;
            # §8.4.1's four-with-Leader rule concerns moving, not placement.
            answer['warbands'].append({'region': region, 'count': warbands})
            warbands = 0
        remaining_regions.remove(region)
    return answer
