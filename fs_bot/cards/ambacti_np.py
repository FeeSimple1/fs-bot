"""Ambacti's printed NP instructions and §§8.2.3–8.4.1 priorities."""

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, get_available, get_leader_in_region,
)
from fs_bot.bots.bot_common import random_select
from fs_bot.map.map_data import get_adjacent_for_state, get_playable_regions_for_state


def _regions(state):
    return sorted(get_playable_regions_for_state(state))


def _removal_regions(state):
    # "Anywhere" removes existing physical pieces even if a restored save
    # retains pieces outside the currently playable placement geography.
    return sorted(region for region in rc.ALL_REGIONS if region in state['spaces'])


def _german_tiers(state):
    primary = set(rc.GERMANIA_REGIONS) | {
        region for region in _removal_regions(state)
        if count_pieces(state, region, rc.GERMANS, rc.SETTLEMENT)}
    adjacent = {neighbor for region in primary
                for neighbor in get_adjacent_for_state(state, region)} - primary
    return primary, adjacent


def np_available(state, faction, shaded):
    """Check applicability without drawing a tie-break or the Event die."""
    regions = _regions(state) if not shaded else _removal_regions(state)
    if not shaded:
        # The beneficiary is fixed by the card, so §8.2.3's restriction on
        # choosing another beneficiary does not prohibit Aedui execution.
        # Their Roman-player/victory condition is checked by the printed
        # instruction filter before this applicability check.
        return (get_available(state, rc.ROMANS, rc.AUXILIA) > 0
                and any(count_pieces(state, region, rc.ROMANS) for region in regions))
    if faction == rc.GERMANS and state['scenario'] in rc.ARIOVISTUS_SCENARIOS:
        primary, adjacent = _german_tiers(state)
        regions = sorted(primary | adjacent)
    return any(count_pieces(state, region, rc.ROMANS, rc.AUXILIA) for region in regions)


def derive_unshaded(state, faction):
    """Maximize actual placement, then select equal Regions by seeded tie."""
    if not np_available(state, faction, False):
        return None
    available = get_available(state, rc.ROMANS, rc.AUXILIA)
    candidates = [region for region in _regions(state)
                  if count_pieces(state, region, rc.ROMANS)]
    scores = {region: min(available, 6 if get_leader_in_region(
        state, region, rc.ROMANS) == rc.CAESAR else 4) for region in candidates}
    best = max(scores.values())
    return {'target_region': random_select(
        state, [region for region in candidates if scores[region] == best])}


def _clearable(counts, budget):
    """Maximum number of whole Auxilia groups removable within the budget."""
    total = 0
    for count in sorted(counts):
        if count > budget:
            break
        budget -= count
        total += 1
    return total


def _arverni_candidates(state, available, remaining):
    covered = {region: count for region, count in available.items()
               if count_pieces(state, region, rc.ROMANS, rc.LEGION)}
    maximum = _clearable(covered.values(), remaining)
    if not maximum:
        return list(available)
    # Keep every next choice that can still attain the maximum number of
    # newly unescorted Legion Regions. Merely preferring a Region with a
    # Legion can spend the whole allowance without exposing any Legions.
    return [region for region, count in covered.items()
            if count <= remaining and 1 + _clearable(
                (other for candidate, other in covered.items() if candidate != region),
                remaining - count) == maximum]


def default_removals(state, faction, count):
    """Choose physical Auxilia, finishing each selected Region before another.

    The German instruction establishes geographic priorities and an Event
    applicability condition; it does not change the printed mandatory total.
    After exhausting both preferred tiers, §5.1.3 still removes the remaining
    number from anywhere. The caller checks ``np_available`` before NP play.
    """
    available = {region: count_pieces(state, region, rc.ROMANS, rc.AUXILIA)
                 for region in _removal_regions(state)}
    available = {region: number for region, number in available.items() if number}
    remaining = min(count, sum(available.values()))
    german = faction == rc.GERMANS and state['scenario'] in rc.ARIOVISTUS_SCENARIOS
    primary, adjacent = _german_tiers(state) if german else (set(), set())
    visibility_order = ((rc.SCOUTED, rc.REVEALED, rc.HIDDEN) if faction == rc.ROMANS
                        else (rc.HIDDEN, rc.REVEALED, rc.SCOUTED))
    result = []
    while available and remaining > 0:
        candidates = list(available)
        if faction == rc.ARVERNI and state['scenario'] in rc.BASE_SCENARIOS:
            candidates = _arverni_candidates(state, available, remaining)
        elif faction == rc.BELGAE:
            candidates = [region for region in candidates if region in rc.BELGICA_REGIONS] or candidates
        elif german:
            candidates = ([region for region in candidates if region in primary]
                          or [region for region in candidates if region in adjacent]
                          or candidates)
        most = max(min(remaining, available[region]) for region in candidates)
        region = random_select(state, sorted(region for region in candidates
                                             if min(remaining, available[region]) == most))
        local = min(remaining, available.pop(region))
        remaining -= local
        for visibility in visibility_order:
            chosen = min(local, count_pieces_by_state(
                state, region, rc.ROMANS, rc.AUXILIA, visibility))
            if chosen:
                result.append({'region': region, 'piece_state': visibility, 'count': chosen})
                local -= chosen
            if not local:
                break
    return result
