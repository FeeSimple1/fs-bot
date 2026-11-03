"""Printed selection contracts for original Events 40, 41, 42 and 51.

Keep geographic/quantity selections separate from §5.1.1 availability and
the live §1.4.1 windows between operations. Sources: Card Reference and
Chapter 5 §§5.1–5.1.3; normal Tribe/City stacking is §1.4.2.
"""
from collections import Counter

from fs_bot import rules_consts as rc
from fs_bot.board.control import calculate_control
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_available
from fs_bot.map.map_data import get_adjacent, get_playable_regions_for_state


def params_for(state, allowed):
    params = state.get('event_params', {})
    if not isinstance(params, dict):
        raise ValueError('Event choices must be an object')
    if set(params) - set(allowed) - {'stage_timing_actions'}:
        raise ValueError('Unknown choice for this Event side')
    return params


def entries(params, key, allowed):
    values = params.get(key, [])
    if not isinstance(values, list) or any(not isinstance(e, dict) for e in values):
        raise ValueError(f'{key} must be a list of objects')
    for entry in values:
        if set(entry) - set(allowed) - {'timing_actions'}:
            raise ValueError(f'Unknown field in {key}')
    return values


def positive_count(entry, maximum):
    count = entry.get('count', 1)
    if type(count) is not int or not 1 <= count <= maximum:
        raise ValueError(f'Event count must be an integer from 1 to {maximum}')
    return count


def adjacent_cisalpina(state):
    return sorted(set(get_adjacent(rc.CISALPINA, state['scenario'])) &
                  set(get_playable_regions_for_state(state)))


def avaricum_regions(state):
    return sorted({rc.BITURIGES, *get_adjacent(rc.BITURIGES, state['scenario'])}
                  & set(get_playable_regions_for_state(state)))


def owns_avaricum(state, faction):
    from fs_bot.cards.card_effects import _tribe_piece_type
    tribe = rc.CITY_TO_TRIBE[rc.CITY_AVARICUM]
    return (state.get('tribes', {}).get(tribe, {}).get('allied_faction') == faction
            and _tribe_piece_type(state, tribe) in (rc.ALLY, rc.CITADEL))


def check_ally_target(state, tribe, faction, regions):
    from fs_bot.cards.boii import eligible_allies
    if tribe not in eligible_allies(state, regions, faction):
        raise ValueError('Event Ally must occupy a legal Subdued Tribe in its allowed Regions')


def alpine_plan(state):
    params = params_for(state, {'placements'})
    placements = entries(params, 'placements', {'region', 'piece_type', 'count', 'faction', 'tribe'})
    kinds, totals, tribes = {}, Counter(), set()
    regions = adjacent_cisalpina(state)
    for entry in placements:
        region, kind = entry.get('region'), entry.get('piece_type')
        faction = entry.get('faction', state.get('executing_faction'))
        if region not in regions or kind not in (rc.WARBAND, rc.AUXILIA, rc.ALLY):
            raise ValueError('Alpine Tribes places Warbands, Auxilia or an Ally adjacent to Cisalpina')
        if (faction not in rc.FACTIONS
                or (kind == rc.WARBAND and faction == rc.ROMANS)
                or (kind == rc.AUXILIA and faction != rc.ROMANS)
                or region not in get_playable_regions_for_state(state, faction)):
            raise ValueError('Alpine Tribes placement has an invalid faction or stacking location')
        if region in kinds and kinds[region] != kind:
            raise ValueError('Alpine Tribes chooses only one piece type per Region')
        kinds[region] = kind
        cap = {rc.WARBAND: 3, rc.AUXILIA: 2, rc.ALLY: 1}[kind]
        totals[region] += positive_count(entry, cap)
        if totals[region] > cap:
            raise ValueError('Alpine Tribes exceeds its per-Region placement limit')
        if kind == rc.ALLY:
            from fs_bot.cards.card_effects import _tribe_region
            tribe = entry.get('tribe')
            if (tribe in tribes or _tribe_region(state, tribe) != region
                    or rc.TRIBE_FACTION_RESTRICTION.get(tribe, faction) != faction):
                raise ValueError('Alpine Tribes Ally needs a distinct legal Tribe in its Region')
            tribes.add(tribe)
    return placements


def avaricum_plan(state):
    params = params_for(state, {'ally_placements', 'citadel_upgrade_tribe', 'fort_region'})
    placements = entries(params, 'ally_placements', {'tribe', 'region', 'faction', 'count'})
    faction = state.get('executing_faction')
    regions, seen = avaricum_regions(state), set()
    if len(placements) > 2:
        raise ValueError('Avaricum places at most two Allies')
    from fs_bot.cards.card_effects import _tribe_region
    for entry in placements:
        tribe = entry.get('tribe')
        region = _tribe_region(state, tribe)
        if (tribe in seen or region not in regions or entry.get('region', region) != region
                or entry.get('faction', faction) != faction):
            raise ValueError('Avaricum places distinct own Allies within one Region of Avaricum')
        positive_count(entry, 1)
        seen.add(tribe)
    upgrade = params.get('citadel_upgrade_tribe')
    if upgrade is not None and _tribe_region(state, upgrade) not in regions:
        raise ValueError('Avaricum replaces an own Ally within one Region')
    fort = params.get('fort_region')
    if fort is not None and fort not in regions:
        raise ValueError('Avaricum Fort placement must be within one Region of Avaricum')
    if (placements or upgrade is not None or fort is not None) and not owns_avaricum(state, faction):
        raise ValueError('Avaricum must be the executing faction\'s Ally or Citadel')
    return params, placements


def wine_regions(state, shaded=False):
    playable = set(get_playable_regions_for_state(state))
    if shaded:
        from fs_bot.commands.rally import has_supply_line
        return {'supply': {r for r in playable if has_supply_line(
            state, r, faction=rc.ROMANS, agreements={rc.ROMANS: True, rc.AEDUI: True})}}
    controlled = {r for r in playable if calculate_control(state, r) == rc.ROMAN_CONTROL}
    adjacent = {n for r in controlled for n in get_adjacent(r, state['scenario'])} & playable
    return {'controlled': controlled, 'adjacent': adjacent}


def wine_targets(state, regions, shaded=False):
    from fs_bot.cards.card_effects import _tribe_piece_type, _tribe_region
    return sorted(t for t, info in state['tribes'].items()
                  if _tribe_region(state, t) in regions
                  and _tribe_piece_type(state, t) == rc.ALLY
                  and (not shaded or info.get('allied_faction') in (rc.ROMANS, rc.AEDUI)))


def wine_plan(state, shaded):
    params = params_for(state, {'removals'} if shaded else {'removals', 'mode'})
    removals = entries(params, 'removals', {'tribe', 'faction', 'region', 'count'})
    regions = wine_regions(state, shaded)
    mode = params.get('mode')
    if mode is not None and mode not in regions:
        raise ValueError('Roman Wine mode must be controlled or adjacent')
    targets = {key: set(wine_targets(state, value, shaded)) for key, value in regions.items()}
    chosen = []
    from fs_bot.cards.card_effects import _tribe_region
    for entry in removals:
        tribe = entry.get('tribe')
        info = state.get('tribes', {}).get(tribe) or {}
        if (tribe in chosen or not any(tribe in values for values in targets.values())
                or entry.get('faction', info.get('allied_faction')) != info.get('allied_faction')
                or entry.get('region', _tribe_region(state, tribe)) != _tribe_region(state, tribe)):
            raise ValueError('Roman Wine selects distinct eligible Allied Tribes, not Citadels')
        positive_count(entry, 1)
        chosen.append(tribe)
    if shaded:
        if len(chosen) > 3:
            raise ValueError('Roman Wine shaded removes one to three eligible Allies when possible')
    elif not any((mode is None or mode == key) and len(chosen) <= limit
                 and set(chosen) <= targets[key]
                 for key, limit in [('controlled', 4), ('adjacent', 2)]):
        raise ValueError('Roman Wine removes up to four under Roman Control OR up to two adjacent to it')
    return removals


def surus_regions(state):
    return sorted({rc.TREVERI, *get_adjacent(rc.TREVERI, state['scenario'])}
                  & set(get_playable_regions_for_state(state)))


def surus_plan(state):
    params = params_for(state, {'region', 'replacements'})
    region = params.get('region')
    if region not in surus_regions(state):
        raise ValueError('Surus requires one Region within one of Treveri')
    replacements = entries(params, 'replacements', {'region', 'from_faction', 'piece_state', 'count'})
    budget = Counter({(owner, visibility): count_pieces_by_state(state, region, owner, rc.WARBAND, visibility)
                      for owner in (*rc.GALLIC_FACTIONS, rc.GERMANS)
                      for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)})
    required = min(4, sum(budget.values()))
    selected, total = Counter(), 0
    for entry in replacements:
        cell = entry.get('from_faction'), entry.get('piece_state', rc.HIDDEN)
        count = positive_count(entry, 4)
        if entry.get('region', region) != region or cell not in budget:
            raise ValueError('Surus selects Warbands in one Region within one of Treveri')
        selected[cell] += count
        total += count
        if selected[cell] > budget[cell] or total > 4:
            raise ValueError('Surus cannot select more than four distinct original Warbands')
    return region, replacements, budget, required, total


def execute_surus_unshaded(state):
    """Replace distinct originals, retaining timed removals and prefix planning."""
    from fs_bot.cards.card_effects import _event_entries
    from fs_bot.cards.dumnorix import _set_cells, _read_cells, _clear_cells, _registry_present
    from fs_bot.board.pieces import remove_piece, place_piece
    from fs_bot.map.map_data import is_region_playable
    region, replacements, budget, required, total = surus_plan(state)
    remaining = Counter()
    for entry in replacements:
        remaining[(region, entry['from_faction'], rc.WARBAND,
                   entry.get('piece_state', rc.HIDDEN))] += entry.get('count', 1)
    prefix = 'surus.original.'
    _set_cells(state, prefix, remaining, label='Original Surus replacement sources')
    try:
        for entry in _event_entries(state, '51.replacements', replacements):
            if _registry_present(state, prefix):
                remaining = Counter(_read_cells(state, prefix))
            owner, visibility = entry['from_faction'], entry.get('piece_state', rc.HIDDEN)
            cell = region, owner, rc.WARBAND, visibility
            actual = min(entry.get('count', 1), remaining[cell])
            remaining[cell] -= actual
            if actual:
                remove_piece(state, region, owner, rc.WARBAND, actual, piece_state=visibility)
                count = min(actual, get_available(state, rc.AEDUI, rc.WARBAND))
                if count and is_region_playable(state, region, rc.AEDUI):
                    place_piece(state, region, rc.AEDUI, rc.WARBAND, count)
            _set_cells(state, prefix, remaining, label='Original Surus replacement sources')
        # A prefix checkpoint stops at the tail window above. Only complete
        # human plans must meet the printed mandatory count.
        if total != required:
            raise ValueError('Surus replaces four original Warbands, or all present if fewer, in its selected Region')
    finally:
        _clear_cells(state, prefix)


def derive_avaricum(state, faction, shaded):
    """Choose legal own placements; never default to a removal-only upgrade."""
    from copy import deepcopy
    from fs_bot.cards.boii import eligible_allies
    from fs_bot.cards.card_effects import _ally_tribe, _tribe_piece_type
    from fs_bot.bots.bot_common import random_select, is_ally_in_city_or_remi
    if not owns_avaricum(state, faction):
        return None
    sim = deepcopy({k: v for k, v in state.items() if k != 'decision_agent'})
    regions, placements = avaricum_regions(state), []
    for _ in range(min(2, get_available(sim, faction, rc.ALLY))):
        candidates = eligible_allies(sim, regions, faction)
        if not candidates:
            break
        preferred = [t for t in candidates if is_ally_in_city_or_remi(t, state['scenario'])]
        tribe = random_select(state, preferred or candidates)
        placements.append({'tribe': tribe})
        _ally_tribe(sim, tribe, faction)
    out = {'ally_placements': placements}
    if get_available(sim, faction, rc.CITADEL):
        candidates = [t for t in rc.TRIBE_TO_CITY if t in sim['tribes']
                      and sim['tribes'][t].get('allied_faction') == faction
                      and _tribe_piece_type(sim, t) == rc.ALLY
                      and rc.TRIBE_FACTION_RESTRICTION.get(t, faction) == faction
                      and _tribe_region_for(sim, t) in regions]
        if candidates:
            out['citadel_upgrade_tribe'] = random_select(state, candidates)
    if faction == rc.ROMANS and get_available(sim, faction, rc.FORT):
        candidates = [r for r in regions if not count_pieces(sim, r, faction, rc.FORT)]
        if candidates:
            out['fort_region'] = random_select(state, candidates)
    return out


def _tribe_region_for(state, tribe):
    from fs_bot.cards.card_effects import _tribe_region
    return _tribe_region(state, tribe)


def derive_wine(state, faction, shaded):
    """Legal branch, exact Allies and printed actor-specific target priorities."""
    from fs_bot.bots.bot_common import random_select, is_ally_in_city_or_remi, get_faction_targeting_order
    modes = wine_regions(state, shaded)
    candidates = {key: [t for t in wine_targets(state, regions, shaded)
                        if state['tribes'][t]['allied_faction'] != faction]
                  for key, regions in modes.items()}
    if faction == rc.AEDUI:
        enemies = ((rc.GERMANS, rc.BELGAE) if state['scenario'] in rc.ARIOVISTUS_SCENARIOS
                   else (rc.ARVERNI, rc.BELGAE))
        players = set(enemies) - set(state.get('non_player_factions', ()))
        candidates = {key: [t for t in values if state['tribes'][t]['allied_faction'] in players]
                      for key, values in candidates.items()}
    limits = {'supply': 3, 'controlled': 4, 'adjacent': 2}
    counts = {key: min(limits[key], len(values)) for key, values in candidates.items()}
    if not max(counts.values()):
        return None
    scores = {key: (min(limits[key], sum(_tribe_region_for(state, t) in rc.BELGICA_REGIONS
                                       for t in values)) if faction == rc.BELGAE else 0,
                    counts[key]) for key, values in candidates.items()}
    best_mode = max(scores.values())
    mode = random_select(state, [key for key in candidates if scores[key] == best_mode])
    most = counts[mode]
    choices, selected = list(candidates[mode]), []
    enemy_order = get_faction_targeting_order(faction, state['scenario'])
    def priority(tribe):
        return (0 if faction == rc.BELGAE and _tribe_region_for(state, tribe) in rc.BELGICA_REGIONS else 1,
                0 if is_ally_in_city_or_remi(tribe, state['scenario']) else 1,
                enemy_order.index(state['tribes'][tribe]['allied_faction']))
    for _ in range(most):
        best = min(priority(t) for t in choices)
        tribe = random_select(state, [t for t in choices if priority(t) == best])
        selected.append({'tribe': tribe, 'faction': state['tribes'][tribe]['allied_faction']})
        choices.remove(tribe)
    return {'removals': selected, **({'mode': mode} if not shaded else {})}
