"""Mandatory quantities and exact piece choices for 68 and A30/A51/A56/A65."""
from fs_bot import rules_consts as rc
from fs_bot.board.control import is_controlled_by
from fs_bot.board.pieces import (
    clear_allied_tribe, count_pieces, count_pieces_by_state, get_available,
    place_piece, remove_piece,
)
from fs_bot.map.map_data import (
    get_adjacent_for_state, get_playable_regions_for_state, is_city_tribe,
)

# Each operation records its existing timing boundary and printed range.
STEPS = {
    68: (('replacements', '68.replacements', 1, 2),),
    'A30': (('placements', 'A30.placements', 9, 9),),
    'A51': (('removals', 'A51.removals', 0, 5),),
    'A56': (('warband_placements', 'A56.warbands', 4, 4),
            ('ally_placements', 'A56.allies', 2, 2)),
    'A65': (('warband_replacements', 'A65.warbands', 4, 4),
            ('ally_replacements', 'A65.allies', 2, 2)),
}
ORGETORIX_REGIONS = (rc.AEDUI_REGION, rc.SEQUANI)
VISIBILITIES = (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)


def supported(card_id, shaded):
    return not shaded if card_id == 68 else shaded and card_id in STEPS


def _remi_allies(state):
    from fs_bot.cards.expansion_validation import source_allies
    remi = state['tribes'].get(rc.TRIBE_REMI, {})
    owner = remi.get('allied_faction')
    if not remi or not (owner == rc.ROMANS or (owner is None and remi.get('status') is None)):
        return []
    regions = (rc.ATREBATES, *get_adjacent_for_state(state, rc.ATREBATES))
    return [e for e in source_allies(state, regions) if e['faction'] != rc.ROMANS]


def _tribe_slots(state, regions, faction, *, replace=False, ignore_restriction=False):
    from fs_bot.cards.card_effects import _tribe_region, _tribe_piece_type
    playable = set(get_playable_regions_for_state(state, faction))
    for tribe, info in sorted(state['tribes'].items()):
        region = _tribe_region(state, tribe)
        if region not in regions or region not in playable:
            continue
        if not ignore_restriction and rc.TRIBE_FACTION_RESTRICTION.get(tribe, faction) != faction:
            continue
        owner = info.get('allied_faction')
        if owner is None and info.get('status') in (None, rc.ALLIED):
            yield tribe, region
        elif replace and owner != faction and _tribe_piece_type(state, tribe) == rc.ALLY:
            yield tribe, region


def _warband_placements(state, faction, regions, remaining):
    available = min(remaining, get_available(state, faction, rc.WARBAND))
    playable = get_playable_regions_for_state(state, faction)
    return [{'region': region, 'count': count} for region in regions if region in playable
            for count in range(1, available + 1)]


def _structure_capacity(slots, cities, allies, citadels):
    citadels = min(citadels, cities)
    return citadels + min(allies, slots - citadels)


def _orgetorix_options(state, remaining):
    entries = [dict(entry, piece_type=rc.WARBAND) for entry in
               _warband_placements(state, rc.ARVERNI, ORGETORIX_REGIONS, remaining)]
    warbands = max((entry['count'] for entry in entries), default=0)
    slots = list(_tribe_slots(state, ORGETORIX_REGIONS, rc.ARVERNI,
                             ignore_restriction=True))
    cities = {tribe for tribe, region in slots if is_city_tribe(tribe)
              and not count_pieces(state, region, piece_type=rc.CITADEL)}
    allies = get_available(state, rc.ARVERNI, rc.ALLY)
    citadels = get_available(state, rc.ARVERNI, rc.CITADEL)
    required = min(remaining, warbands + _structure_capacity(
        len(slots), len(cities), allies, citadels))
    for tribe, region in slots:
        city = tribe in cities
        # A City Ally can occupy a slot needed for a Citadel when the Ally
        # could go on a different Tribe. Preserve the attainable quota.
        if allies and 1 + warbands + _structure_capacity(
                len(slots) - 1, len(cities) - city, allies - 1, citadels) >= required:
            entries.append({'region': region, 'piece_type': rc.ALLY, 'tribe': tribe})
        if city and citadels:
            entries.append({'region': region, 'piece_type': rc.CITADEL, 'tribe': tribe})
    return entries


def _bibrax_targets(state):
    from fs_bot.cards.card_effects import _tribe_region, _tribe_piece_type
    targets = []
    for faction, troop in ((rc.ROMANS, rc.AUXILIA), (rc.AEDUI, rc.WARBAND)):
        targets.extend({'faction': faction, 'piece_type': troop, 'piece_state': ps}
                       for ps in VISIBILITIES
                       if count_pieces_by_state(state, rc.ATREBATES, faction, troop, ps))
        if count_pieces(state, rc.ATREBATES, faction, rc.FORT):
            targets.append({'faction': faction, 'piece_type': rc.FORT})
        for tribe, info in sorted(state['tribes'].items()):
            if info.get('allied_faction') != faction or _tribe_region(state, tribe) != rc.ATREBATES:
                continue
            kind = _tribe_piece_type(state, tribe)
            if kind in (rc.ALLY, rc.CITADEL):
                targets.append({'faction': faction, 'piece_type': kind, 'tribe': tribe})
    return targets


def _kinship_targets(state, source, key):
    from fs_bot.cards.expansion_validation import source_allies
    regions = get_playable_regions_for_state(state)
    if key == 'ally_replacements':
        return [{'tribe': entry['tribe']} for entry in source_allies(state, regions)
                if entry['faction'] == source]
    return [{'region': region, 'piece_state': ps} for region in regions for ps in VISIBILITIES
            if count_pieces_by_state(state, region, source, rc.WARBAND, ps)]


def kinship_sources(state):
    from fs_bot.cards.kinship import ATTACKERS
    return [source for source in ATTACKERS if any(
        _kinship_targets(state, source, key) for key, _, _, _ in STEPS['A65'])]


def options(state, card, key, params, remaining):
    """Legal entries on the board at the next placement or removal."""
    if remaining <= 0:
        return []
    if card == 68:
        return [{'tribe': e['tribe']} for e in _remi_allies(state)]
    if card == 'A30':
        return _orgetorix_options(state, remaining)
    if card == 'A51':
        return _bibrax_targets(state)
    if card == 'A56':
        if key == 'warband_placements':
            return _warband_placements(state, rc.BELGAE, rc.BELGICA_REGIONS, remaining)
        available = get_available(state, rc.BELGAE, rc.ALLY)
        return [{'tribe': tribe} for tribe, _ in
                _tribe_slots(state, rc.BELGICA_REGIONS, rc.BELGAE, replace=True)
                if available or state['tribes'][tribe].get('allied_faction')]
    return _kinship_targets(state, params.get('from_faction', rc.BELGAE), key)


def may_finish(state, card, key, used, minimum, choices):
    # Galba's replacement of an enemy Ally is optional when the Belgic
    # pool is empty. An explicit replacement still removes its source.
    return (used >= minimum or not choices or
            (card == 'A56' and key == 'ally_placements'
             and not get_available(state, rc.BELGAE, rc.ALLY)))


def _selected_entry(state, card, key, entry, choices):
    from fs_bot.cards.card_effects import _tribe_region
    choice = {k: v for k, v in entry.items() if k != 'timing_actions'}
    kind = choice.get('piece_type')
    count = choice.pop('count', 1)
    if type(count) is not int or count < 1:
        raise ValueError(f'{card} piece count must be a positive integer')
    placing_warbands = key == 'warband_placements' or (card == 'A30' and kind == rc.WARBAND)
    if placing_warbands:
        if key == 'warband_placements' and kind == rc.WARBAND:
            choice.pop('piece_type')
        choice['count'] = count
        # Older Orgetorix menus included a Tribe field on mobile entries.
        choice.pop('tribe', None)
    elif count != 1:
        raise ValueError(f'{card} needs one exact piece per entry')

    if key == 'warband_replacements' or (card == 'A51' and kind in (rc.WARBAND, rc.AUXILIA)):
        choice.setdefault('piece_state', rc.HIDDEN)
    if card == 'A51':
        if choice.pop('region', rc.ATREBATES) != rc.ATREBATES:
            raise ValueError('Siege of Bibrax removes pieces in Atrebates')
        if kind in (rc.ALLY, rc.CITADEL, rc.FORT):
            # Older generic menus carried an unused visibility for structures.
            choice.pop('piece_state', None)
    if key == 'ally_placements' and 'region' in choice:
        if choice.pop('region') != _tribe_region(state, choice.get('tribe')):
            raise ValueError('Select the Region of the named Tribe')

    if choice in choices:
        return choice
    if placing_warbands:
        # A legacy grouped placement can request more than the pool
        # supplies. Apply its legal portion and count the actual pieces.
        matches = [e for e in choices if 'count' in e and e['count'] < count
                   and dict(choice, count=e['count']) == e]
        if matches:
            return max(matches, key=lambda e: e['count'])
    # A Citadel's Region identifies its City. Old Bibrax Ally entries may
    # likewise omit the Tribe if exactly one physical piece matches.
    if ((card == 'A30' and set(choice) == {'region', 'piece_type'} and kind == rc.CITADEL)
            or (card == 'A51' and set(choice) == {'faction', 'piece_type'}
                and kind in (rc.ALLY, rc.CITADEL))):
        matches = [e for e in choices if all(e.get(k) == v for k, v in choice.items())]
        if len(matches) == 1:
            return matches[0]
        if matches:
            raise ValueError('Select the exact Allied Tribe to remove at Bibrax')
    raise ValueError(f'{card} {key} entry does not identify an eligible piece')


def _replace_ally(state, tribe, owner):
    from fs_bot.cards.card_effects import _ally_tribe, _tribe_region, _unally_tribe
    _unally_tribe(state, tribe)
    region = _tribe_region(state, tribe)
    # §§5.1.1, 8.4.1: the source is removed even if the counterpart
    # is unavailable or cannot legally stack.
    if (rc.TRIBE_FACTION_RESTRICTION.get(tribe, owner) == owner
            and region in get_playable_regions_for_state(state, owner)):
        _ally_tribe(state, tribe, owner)


def _apply_entry(state, card, key, params, entry):
    from fs_bot.cards.card_effects import _ally_tribe, _unally_tribe
    if card == 68:
        _replace_ally(state, entry['tribe'], rc.ROMANS)
    elif card == 'A30':
        kind = entry['piece_type']
        if kind == rc.WARBAND:
            place_piece(state, entry['region'], rc.ARVERNI, kind, entry['count'])
        else:
            _ally_tribe(state, entry['tribe'], rc.ARVERNI, citadel=kind == rc.CITADEL)
    elif card == 'A51':
        if 'tribe' in entry:
            _unally_tribe(state, entry['tribe'])
        else:
            remove_piece(state, rc.ATREBATES, entry['faction'], entry['piece_type'],
                         piece_state=entry.get('piece_state'))
    elif card == 'A56':
        if key == 'warband_placements':
            place_piece(state, entry['region'], rc.BELGAE, rc.WARBAND, entry['count'])
        else:
            _replace_ally(state, entry['tribe'], rc.BELGAE)
    else:
        from fs_bot.cards.kinship import opponent
        source = params.get('from_faction', rc.BELGAE)
        destination = opponent(source)
        if key == 'ally_replacements':
            _replace_ally(state, entry['tribe'], destination)
        else:
            region = entry['region']
            remove_piece(state, region, source, rc.WARBAND, piece_state=entry['piece_state'])
            if (get_available(state, destination, rc.WARBAND)
                    and region in get_playable_regions_for_state(state, destination)):
                place_piece(state, region, destination, rc.WARBAND)


def _clear_orgetorix(state):
    from fs_bot.cards.card_effects import _event_entries, _tribe_region, _unally_tribe
    for region in _event_entries(state, 'A30.clear_regions', ORGETORIX_REGIONS):
        for tribe in sorted(state['tribes']):
            if _tribe_region(state, tribe) == region:
                _unally_tribe(state, tribe)
        # Old saves could contain an unbacked Citadel here.
        for faction in rc.FACTIONS:
            if count_pieces(state, region, faction, rc.CITADEL):
                remove_piece(state, region, faction, rc.CITADEL)
                clear_allied_tribe(state, region, faction, rc.CITADEL)


def execute(state, card):
    """Apply an authored plan through the Event transaction and live timing."""
    from fs_bot.cards.card_effects import _cap_resources, _event_entries, _event_step
    from fs_bot.cards.expansion_validation import _entries
    params = state.get('event_params')
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ValueError(f'{card} Event choices must be an object')
    allowed = {key for key, _, _, _ in STEPS[card]} | {'stage_timing_actions'}
    if card == 'A65':
        from fs_bot.cards.kinship import opponent
        allowed.add('from_faction')
        source = params.get('from_faction', rc.BELGAE)
        opponent(source)
        sources = kinship_sources(state)
        if sources and source not in sources:
            raise ValueError('Kinship must select a side with eligible source pieces')
    if set(params) - allowed:
        raise ValueError(f'{card} has unexpected or wrong-side Event choices')
    if card == 'A30':
        _clear_orgetorix(state)
    for key, step, minimum, maximum in STEPS[card]:
        used = 0
        for entry in _event_entries(state, step, _entries(params, key)):
            if used == maximum and card == 'A30':
                # Preserve the capped Orgetorix placement tail and its
                # existing timing boundary.
                break
            choices = options(state, card, key, params, maximum - used)
            selected = _selected_entry(state, card, key, entry, choices)
            _apply_entry(state, card, key, params, selected)
            used += selected.get('count', 1)
        choices = options(state, card, key, params, maximum - used)
        if not may_finish(state, card, key, used, minimum, choices):
            raise ValueError(f'{card} must complete its required {key} as far as possible')
    if card == 'A56':
        _event_step(state, 'A56.resources')
        _cap_resources(state, rc.BELGAE, 4)


def _rank_entry(state, actor, entry):
    from fs_bot.bots.bot_common import get_faction_targeting_order, is_ally_in_city_or_remi
    tribe = entry.get('tribe')
    owner = entry.get('faction') or state['tribes'].get(tribe, {}).get('allied_faction')
    priority = get_faction_targeting_order(actor, state['scenario'])
    kind = entry.get('piece_type', rc.ALLY if tribe else rc.WARBAND)
    structure = 2 if kind in (rc.CITADEL, rc.FORT) else int(kind == rc.ALLY)
    city_ally = kind == rc.ALLY and is_ally_in_city_or_remi(tribe, state['scenario'])
    ps = entry.get('piece_state')
    return (structure, city_ally, len(priority) - priority.index(owner) if owner in priority else 0,
            -VISIBILITIES.index(ps) if ps in VISIBILITIES else 0, entry.get('count', 1))


def derive_params(state, actor, card, *, npc=None):
    """Build a complete default from the same pools used by execution."""
    from fs_bot.bots.bot_common import random_select
    from fs_bot.cards.card_effects import _tribe_region
    from fs_bot.cards.expansion_validation import clone
    from fs_bot.cards.kinship import ATTACKERS, opponent

    sim = clone(state)
    # Derivation uses a detached board; tie rolls belong to the real chooser.
    sim['event_params'] = {}
    params = {}
    if npc is None:
        npc = actor in state.get('non_player_factions', ())
    if card == 'A65':
        sources = kinship_sources(sim)
        if actor in ATTACKERS:
            source = opponent(actor)
            if npc and source not in sources:
                return None
        elif npc:
            return None
        else:
            source = rc.BELGAE
        params['from_faction'] = source if source in sources or not sources else sources[0]
    protect = set()
    if card == 'A30':
        if npc and actor == rc.GERMANS:
            if any(count_pieces(sim, r, rc.GERMANS, rc.ALLY) for r in ORGETORIX_REGIONS):
                return None
            protect = {r for r in ORGETORIX_REGIONS if is_controlled_by(sim, r, rc.GERMANS)}
        _clear_orgetorix(sim)

    for key, _, minimum, maximum in STEPS[card]:
        params[key] = []
        used = 0
        while used < maximum:
            choices = options(sim, card, key, params, maximum - used)
            if card == 'A51':
                choices = [entry for entry in choices if entry['faction'] != actor]
            if protect:
                choices = [e for e in choices if e['region'] not in protect or
                           2 * count_pieces(sim, e['region'], rc.GERMANS) >
                           count_pieces(sim, e['region']) + e.get('count', 1)]
            if not choices:
                if not may_finish(sim, card, key, used, minimum,
                                  options(sim, card, key, params, maximum - used)):
                    return None
                break
            score = max(_rank_entry(sim, actor, entry) for entry in choices)
            top = [e for e in choices if _rank_entry(sim, actor, e) == score]
            regions = sorted({e.get('region') or _tribe_region(sim, e.get('tribe')) or rc.ATREBATES
                              for e in top})
            region = random_select(state, regions)
            entry = random_select(state, [e for e in top if
                (e.get('region') or _tribe_region(sim, e.get('tribe')) or rc.ATREBATES) == region])
            _apply_entry(sim, card, key, params, entry)
            params[key].append(entry)
            used += entry.get('count', 1)
    return params if card != 68 or params['replacements'] else None


def np_available(state, actor, card):
    from fs_bot.cards.expansion_validation import clone
    trial = clone(state)
    params = derive_params(trial, actor, card, npc=True)
    if params is None:
        return False
    if card == 'A30' and any(count_pieces(state, r, piece_type=kind)
                             for r in ORGETORIX_REGIONS for kind in (rc.ALLY, rc.CITADEL)):
        return True
    return (any(params[key] for key, _, _, _ in STEPS[card])
            or (card == 'A56' and state['resources'][rc.BELGAE] < rc.MAX_RESOURCES))
