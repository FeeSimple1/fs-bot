"""Card 62 Roman relocation using §8.8.1 priorities, without March limits."""
from itertools import product

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_on_map, get_leader_in_region
from fs_bot.bots.bot_common import random_select, roll_die, count_faction_allies_and_citadels
from fs_bot.bots.roman_bot import _march_group_8_8_1, _has_roman_threat
from fs_bot.engine.victory import calculate_victory_margin, VictoryError

_TYPES = (rc.LEADER, rc.LEGION, rc.AUXILIA)


def _bases(state, region, faction):
    return (count_pieces(state, region, faction, rc.ALLY)
            + count_pieces(state, region, faction, rc.CITADEL)
            + (count_pieces(state, region, faction, rc.SETTLEMENT)
               if state['scenario'] in rc.ARIOVISTUS_SCENARIOS else 0))


def _total_bases(state, faction):
    return (count_faction_allies_and_citadels(state, faction)
            + (count_on_map(state, faction, rc.SETTLEMENT)
               if state['scenario'] in rc.ARIOVISTUS_SCENARIOS else 0))


def _random_order(state, values, key):
    """§8.3.4 only breaks equal printed priorities."""
    while values:
        best = min(key(value) for value in values)
        # This choice is among destination Regions. Multiple enemy bases
        # qualifying in one Region must not give that Region extra chances.
        equal = sorted({value['region'] for value in values if key(value) == best})
        region = random_select(state, equal)
        # One Region is selected once, even if several enemy bases are there.
        values[:] = [other for other in values if other['region'] != region]
        yield region


def _destination_sequence(state, regions):
    from fs_bot.battle.resolve import _calculate_attack_losses
    from fs_bot.cards.capabilities import is_capability_active
    from fs_bot.cards.war_fleet import _copy
    from fs_bot.engine.game_engine import get_sop_factions
    from fs_bot.commands.rally import has_supply_line
    candidates = []
    nps = state.get('non_player_factions', set())
    players = set(get_sop_factions(state)) - nps
    for region in regions:
        # Event relocation has no route Harassment. Retain Roman defenses
        # when comparing the most damaging enemy Battle at the destination.
        threat = _copy(state)
        if is_capability_active(threat, 59, rc.EVENT_SHADED):
            # Each possible enemy Battle can select this Region for its
            # capability; no selection or modifier is written to the board.
            threat.setdefault('event_modifiers', {})['card59_shaded_region'] = region
        losses = max(_calculate_attack_losses(
            threat, region, enemy, rc.ROMANS, is_retreat=False,
            had_citadel_at_start=False,
            had_fort_at_start=bool(count_pieces(state, region, rc.ROMANS, rc.FORT)))
            for enemy in rc.FACTIONS if enemy != rc.ROMANS)
        supply = has_supply_line(state, region)
        for enemy in rc.FACTIONS:
            if enemy == rc.ROMANS or not _bases(state, region, enemy):
                continue
            try:
                margin = calculate_victory_margin(state, enemy)
            except VictoryError:  # game-run faction has no victory condition
                margin = -999
            candidates.append({'region': region, 'enemy': enemy,
                'victory': margin >= 0, 'player': enemy in players,
                'total': _total_bases(state, enemy),
                'sub': (losses, -_bases(state, region, enemy), -int(supply))})
    if not candidates:
        return
    at_victory = [c for c in candidates if c['victory']]
    chosen_regions = set()
    for region in _random_order(state, at_victory,
                                 lambda c: (not c['player'], c['sub'])):
        chosen_regions.add(region)
        yield region
    remaining = [c for c in candidates if not c['victory']
                 and c['region'] not in chosen_regions]
    if remaining:
        # The die is rolled only if higher-priority victory targets have
        # failed to supply the destinations actually needed for this move.
        die = roll_die(state)
        special = (rc.ARVERNI if state['scenario'] in rc.ARIOVISTUS_SCENARIOS
                   else rc.GERMANS)
        special_count = (count_faction_allies_and_citadels(state, special)
                         if special == rc.ARVERNI else
                         count_on_map(state, rc.GERMANS, rc.ALLY))
        if die <= 2 and special_count >= 2 and any(c['enemy'] == special for c in remaining):
            priority = lambda c: (c['enemy'] != special, c['sub'])
        elif die in (3, 4):
            priority = lambda c: (not c['player'], c['sub'])
        else:
            priority = lambda c: (-c['total'], c['sub'])
        yield from _random_order(state, remaining, priority)


def _destinations(state, regions):
    """Materialized ranking for callers that explicitly need every candidate."""
    return list(_destination_sequence(state, regions))


def _origin_options(state, regions, destinations):
    groups = {r: _march_group_8_8_1(state, r) for r in regions}
    groups = {r: g for r, g in groups.items() if g and any(r != d for d in destinations)}
    threatened = [r for r in groups if
        (count_pieces(state, r, rc.ROMANS, rc.LEGION)
         or get_leader_in_region(state, r, rc.ROMANS) == rc.CAESAR)
        and _has_roman_threat(state, r, state['scenario'])]
    firsts = threatened or [None]
    results = []
    for first in firsts:
        first_destination = (next(d for d in destinations if d != first)
                             if first is not None else None)
        seconds = [r for r in threatened if r not in (first, first_destination)] or [None]
        for second in seconds:
            chosen = [r for r in (first, second) if r is not None]
            clean = [r for r in groups if r not in chosen and
                     not any(_bases(state, r, enemy) for enemy in rc.FACTIONS if enemy != rc.ROMANS)]
            if clean:
                key = lambda r: (-bool(get_leader_in_region(state, r, rc.ROMANS)),
                                  -count_pieces(state, r, rc.ROMANS, rc.LEGION))
                best = min(key(r) for r in clean)
                clean = [r for r in clean if key(r) == best]
            for third in clean or [None]:
                origins = chosen + ([third] if third is not None else [])
                if origins:
                    results.append({r: groups[r] for r in origins[:3]})
    return results


def _choose_origins(state, options):
    # Choose each equal Region in source order; an origin with more possible
    # continuations must not thereby have a greater chance of selection.
    remaining = list(options)
    for index in range(3):
        labels = []
        for option in remaining:
            keys = list(option)
            label = keys[index] if index < len(keys) else None
            if label not in labels:
                labels.append(label)
        chosen = random_select(state, labels)
        remaining = [option for option in remaining
                     if (list(option)[index] if index < len(option) else None) == chosen]
        if len(remaining) == 1:
            return remaining[0]
    return remaining[0]


def _can_consolidate(state, groups, destination):
    if count_on_map(state, rc.ROMANS, rc.LEGION) > 6 or destination in groups:
        return False
    # Existing destination residents count as already there; every other
    # Legion and the on-map Leader must be in a selected coastal origin.
    for region in state['spaces']:
        if region != destination and region not in groups:
            if (count_pieces(state, region, rc.ROMANS, rc.LEGION)
                    or get_leader_in_region(state, region, rc.ROMANS)):
                return False
    return bool(groups)


def _piece_ranges(groups, destinations, piece):
    origins = list(groups)
    ranges = []
    for index, origin in enumerate(origins):
        total = int(groups[origin].get(piece, 0))
        choices = ((0,) if origin == destinations[0] else
                   (total,) if origin == destinations[1] else range(total + 1))
        # §8.8.1: the second selected threat origin cannot receive any
        # departing part of the first origin's group, even in a split plan.
        if index == 0 and len(origins) > 1:
            if origins[1] == destinations[0]:
                choices = tuple(n for n in choices if n == 0)
            elif origins[1] == destinations[1]:
                choices = tuple(n for n in choices if n == total)
        ranges.append(choices)
    return ranges


def _allocations(groups, destinations, piece, total_first):
    ranges = _piece_ranges(groups, destinations, piece)
    return [counts for counts in product(*ranges) if sum(counts) == total_first]


def _moves(state, groups, destinations, totals, *, randomize=False):
    from fs_bot.cards.war_fleet import _entries, _copy, _apply
    selected = {}
    for piece, amount in zip(_TYPES, totals):
        choices = _allocations(groups, destinations, piece, amount)
        selected[piece] = random_select(state, choices) if randomize else choices[0]
    result = []
    for index, (origin, group) in enumerate(groups.items()):
        first = {piece: selected[piece][index] for piece in _TYPES}
        second = {piece: int(group.get(piece, 0)) - first[piece] for piece in _TYPES}
        # Reserve the original pieces by visibility before another origin's
        # arrivals can reach this origin. No arriving counter travels twice.
        local = _copy(state)
        batch = _entries(local, rc.ROMANS, origin, destinations[0], first)
        _apply(local, rc.ROMANS, batch)
        batch += _entries(local, rc.ROMANS, origin, destinations[1], second)
        result.extend(batch)
    return result


def _two_destinations(state, groups, destinations, *, randomize=True):
    from fs_bot.cards.war_fleet import _copy, _apply, _frost_ok
    total = {piece: sum(int(g.get(piece, 0)) for g in groups.values()) for piece in _TYPES}
    residents = {d: {piece: count_pieces(state, d, rc.ROMANS, piece)
                        - int(groups.get(d, {}).get(piece, 0)) for piece in _TYPES}
                 for d in destinations}
    ranges = []
    for piece in _TYPES:
        options = _piece_ranges(groups, destinations, piece)
        if any(not choices for choices in options):
            return []
        low = sum(min(choices) for choices in options)
        high = sum(max(choices) for choices in options)
        ranges.append(range(low, high + 1))
    candidates, frost_cache = [], {}
    for allocation in product(*ranges):
        # Both selected destinations must actually receive moving pieces.
        if not 0 < sum(allocation) < sum(total.values()):
            continue
        key = sum(allocation)
        if key not in frost_cache:
            sim = _copy(state)
            _apply(sim, rc.ROMANS, _moves(state, groups, destinations, allocation))
            frost_cache[key] = _frost_ok(state, sim)
        if not frost_cache[key]:
            continue
        first = {p: residents[destinations[0]][p] + n for p, n in zip(_TYPES, allocation)}
        second = {p: residents[destinations[1]][p] + total[p] - n for p, n in zip(_TYPES, allocation)}
        # Specific §8.8.1 majorities precede the general §8.4.1 escort.
        # Once strictly greater, no preferred numerical split is printed.
        rank = tuple((1, 0) if first[p] > second[p] else (0, first[p] - second[p]) for p in _TYPES)
        escort = (min(4, first[rc.AUXILIA]) if first[rc.LEADER] else
                  min(4, second[rc.AUXILIA]) if second[rc.LEADER] else 0)
        candidates.append((rank + ((escort, 0),), allocation))
    if not candidates:
        return []
    best = max(rank for rank, _ in candidates)
    equal = [allocation for rank, allocation in candidates if rank == best]
    chosen = random_select(state, equal) if randomize else equal[0]
    return _moves(state, groups, destinations, chosen, randomize=randomize)


def roman_moves(state, regions):
    """Return frozen Event moves; mutate only seeded choice state on success."""
    from fs_bot.cards.war_fleet import _entries, _copy, _apply, _frost_ok
    initial_rng = state['rng'].getstate()
    sequence = iter(_destination_sequence(state, regions))
    destinations = []
    exhausted = False

    def destination(index):
        nonlocal exhausted
        while len(destinations) <= index and not exhausted:
            try:
                destinations.append(next(sequence))
            except StopIteration:
                exhausted = True
        return destinations[index] if index < len(destinations) else None

    index = 0
    while (first := destination(index)) is not None:
        single = []
        for groups in _origin_options(state, regions, [first]):
            moves = [move for origin, group in groups.items()
                     for move in _entries(state, rc.ROMANS, origin, first, group)]
            after = _copy(state)
            _apply(after, rc.ROMANS, moves)
            if moves and _frost_ok(state, after):
                single.append(groups)
        consolidated = [groups for groups in single if _can_consolidate(state, groups, first)]
        if consolidated:
            groups = _choose_origins(state, consolidated)
            return [move for origin, group in groups.items()
                    for move in _entries(state, rc.ROMANS, origin, first, group)]
        second_index = 0
        has_other = False
        while (second := destination(second_index)) is not None:
            second_index += 1
            if first == second:
                continue
            has_other = True
            selected = [first, second]
            valid = [groups for groups in _origin_options(state, regions, selected)
                     if _two_destinations(state, groups, selected, randomize=False)]
            if valid:
                groups = _choose_origins(state, valid)
                return _two_destinations(state, groups, selected)
        # If only one enemy-base Region exists, act to the maximum extent
        # possible; do not invent a second destination without an enemy base.
        if not has_other and single:
            groups = _choose_origins(state, single)
            return [move for origin, group in groups.items()
                    for move in _entries(state, rc.ROMANS, origin, first, group)]
        index += 1
    state['rng'].setstate(initial_rng)
    return []
