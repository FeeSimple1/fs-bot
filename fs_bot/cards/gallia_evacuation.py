"""A5: each non-Roman owner evacuates its physical Cisalpina pieces.

A Card Reference A5; §§1.4.2, 5.1, 5.1.1; A1.3.1/A1.4.2. This is a
relocation, not a March: visibility and Leader identity are retained.
"""
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (
    clear_allied_tribe, count_pieces, count_pieces_by_state,
    get_leader_in_region, move_piece, remove_piece,
)
from fs_bot.commands.rally import _find_subdued_tribe_for_ally
from fs_bot.map.map_data import get_playable_regions_for_state


OWNERS = (rc.ARVERNI, rc.AEDUI, rc.BELGAE, rc.GERMANS)


def planning_copy(state):
    """A detached board/RNG, with no callable decision agent."""
    result = deepcopy({key: value for key, value in state.items()
                       if key != 'decision_agent'})
    result['_diviciacus_preview'] = True
    return result


def home_regions(state, faction):
    ario = state['scenario'] in rc.ARIOVISTUS_SCENARIOS
    homes = {
        rc.ARVERNI: (rc.ARVERNI_HOME_REGIONS_ARIOVISTUS if ario
                     else rc.ARVERNI_HOME_REGIONS_BASE),
        rc.AEDUI: rc.AEDUI_HOME_REGIONS,
        rc.BELGAE: rc.BELGAE_HOME_REGIONS,
        rc.GERMANS: rc.GERMAN_HOME_REGIONS_BASE,
    }
    result = set(homes[faction])
    if ario and faction == rc.GERMANS:
        result.update(region for region in state['spaces']
                      if count_pieces(state, region, faction, rc.SETTLEMENT))
    return sorted(result & set(get_playable_regions_for_state(state, faction))
                  - {rc.CISALPINA})


def pieces(state, faction):
    """Stable IDs retain each visibility cohort and each named Tribe piece."""
    from fs_bot.cards.card_effects import _tribe_region, _tribe_piece_type
    result = []
    for piece_type in rc.PIECE_TYPES:
        count = count_pieces(state, rc.CISALPINA, faction, piece_type)
        if not count:
            continue
        if piece_type in rc.FLIPPABLE_PIECES:
            for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
                number = count_pieces_by_state(
                    state, rc.CISALPINA, faction, piece_type, visibility)
                if number:
                    result.append({'id': f'{piece_type}:{visibility}',
                                   'piece_type': piece_type, 'count': number,
                                   'piece_state': visibility})
        elif piece_type in (rc.ALLY, rc.CITADEL):
            tribes = sorted(tribe for tribe, info in state['tribes'].items()
                            if info.get('allied_faction') == faction
                            and _tribe_region(state, tribe) == rc.CISALPINA
                            and _tribe_piece_type(state, tribe) == piece_type)
            for index in range(count):
                tribe = tribes[index] if index < len(tribes) else None
                result.append({'id': f'{piece_type}:{tribe or index}',
                               'piece_type': piece_type, 'count': 1,
                               'tribe': tribe})
        else:
            entry = {'id': piece_type, 'piece_type': piece_type, 'count': count}
            if piece_type == rc.LEADER:
                entry['leader_name'] = get_leader_in_region(state, rc.CISALPINA, faction)
            result.append(entry)
    return result


def destinations(state, faction, piece):
    """Only legal Home slots; A5 creates no exception to ordinary stacking."""
    options = []
    piece_type = piece['piece_type']
    for region in home_regions(state, faction):
        if piece_type in (rc.ALLY, rc.CITADEL):
            if piece_type == rc.CITADEL and any(
                    count_pieces(state, region, owner, rc.CITADEL)
                    for owner in rc.FACTIONS):
                continue
            for tribe in sorted(_find_subdued_tribe_for_ally(state, region, faction)):
                if piece_type == rc.ALLY or tribe in rc.TRIBE_TO_CITY:
                    options.append({'destination': region, 'tribe': tribe})
        elif piece_type in (rc.SETTLEMENT, rc.FORT):
            if not any(count_pieces(state, region, owner, piece_type)
                       for owner in rc.FACTIONS):
                options.append({'destination': region})
        else:
            options.append({'destination': region})
    return options


def request_for(state, faction):
    entries = pieces(state, faction)
    for entry in entries:
        entry['destinations'] = destinations(state, faction, entry)
    return {'kind': 'free_action', 'request_type': 'gallia_evacuation',
            'card_id': 'A5', 'acting_faction': faction, 'origin': rc.CISALPINA,
            'home_regions': home_regions(state, faction), 'pieces': entries,
            'allow_decline': False, 'free': True, 'with_sa': False}


def apply_allocation(state, faction, piece, allocation):
    """One prevalidated physical transfer, with exact Tribe bookkeeping."""
    destination = allocation['destination']
    kwargs = {'count': allocation['count'], 'piece_state': piece.get('piece_state')}
    if destination is None:
        remove_piece(state, rc.CISALPINA, faction, piece['piece_type'], **kwargs)
    else:
        move_piece(state, rc.CISALPINA, destination, faction, piece['piece_type'], **kwargs)
    if piece['piece_type'] in (rc.ALLY, rc.CITADEL):
        if piece.get('tribe') is not None:
            clear_allied_tribe(state, rc.CISALPINA, faction,
                              piece['piece_type'], tribe=piece['tribe'])
        if destination is not None:
            info = state['tribes'][allocation['tribe']]
            info['allied_faction'], info['status'] = faction, None


def validate_response(state, faction, response):
    """Validate the complete allocation on a copy, consuming no live RNG."""
    if (not isinstance(response, dict) or set(response) != {'allocations'}
            or not isinstance(response['allocations'], list)):
        raise ValueError('Provide an allocations list for every Cisalpina piece.')
    available = {entry['id']: entry for entry in pieces(state, faction)}
    remaining = {key: entry['count'] for key, entry in available.items()}
    sim = planning_copy(state)
    for allocation in response['allocations']:
        if not isinstance(allocation, dict):
            raise ValueError('Each allocation must identify a piece, count and destination.')
        key = allocation.get('piece_id')
        if not isinstance(key, str) or key not in available:
            raise ValueError('Choose a physical piece offered by this owner request.')
        piece = available[key]
        fields = {'piece_id', 'count', 'destination'}
        if (piece['piece_type'] in (rc.ALLY, rc.CITADEL)
                and allocation.get('destination') is not None):
            fields.add('tribe')
        if set(allocation) != fields:
            raise ValueError('Allocation contains missing or unexpected fields.')
        number = allocation['count']
        if type(number) is not int or not 0 < number <= remaining[key]:
            raise ValueError('Allocation count must be a positive available integer.')
        slot = {name: allocation[name] for name in ('destination', 'tribe')
                if name in allocation}
        if allocation['destination'] is not None and slot not in destinations(sim, faction, piece):
            raise ValueError('Choose a legal unoccupied Home Region/Tribe slot, or remove.')
        apply_allocation(sim, faction, piece, allocation)
        remaining[key] -= number
    if any(remaining.values()):
        raise ValueError('Every non-Roman piece must leave Cisalpina.')


def _random_slot(state, options):
    """§8.3.4: equal chance by Region, then by Tribe within that Region."""
    regions = sorted({slot['destination'] for slot in options})
    region = regions[0] if len(regions) == 1 else state['rng'].choice(regions)
    slots = [slot for slot in options if slot['destination'] == region]
    return slots[0] if len(slots) == 1 else state['rng'].choice(slots)


def default_response(state, faction):
    """§§8.3.2/8.4.1: preserve own pieces, Leader stack, then random ties."""
    sim = planning_copy(state)
    entries = pieces(sim, faction)
    priority = {rc.LEADER: 0, rc.LEGION: 1, rc.CITADEL: 2,
                rc.SETTLEMENT: 2, rc.FORT: 2, rc.ALLY: 3}
    entries.sort(key=lambda entry: priority.get(entry['piece_type'], 4))
    allocations = []
    for piece in entries:
        remaining = piece['count']
        while remaining:
            options = destinations(sim, faction, piece)
            number = remaining
            if piece['piece_type'] == rc.LEADER and options:
                most = max(count_pieces(sim, slot['destination'], faction) for slot in options)
                options = [slot for slot in options
                           if count_pieces(sim, slot['destination'], faction) == most]
            elif piece['piece_type'] == rc.ALLY and options:
                preferred = [slot for slot in options
                             if slot['tribe'] in rc.TRIBE_TO_CITY or slot['tribe'] == rc.TRIBE_REMI]
                options = preferred or options
            elif piece['piece_type'] in (rc.WARBAND, rc.AUXILIA) and options:
                escort = [slot for slot in options
                          if get_leader_in_region(sim, slot['destination'], faction) is not None
                          and count_pieces(sim, slot['destination'], faction, piece['piece_type']) < 4]
                if escort:
                    options = escort
                    number = min(number, 4 - count_pieces(
                        sim, escort[0]['destination'], faction, piece['piece_type']))
            slot = _random_slot(state, options) if options else {'destination': None}
            allocation = {'piece_id': piece['id'], 'count': number, **slot}
            apply_allocation(sim, faction, piece, allocation)
            allocations.append(allocation)
            remaining -= number
    return {'allocations': allocations}


def resolve_owner(state, faction):
    from fs_bot.engine.free_actions import consult_free_action
    request = request_for(state, faction)
    if not request['pieces']:
        return []
    automatic_arverni = (faction == rc.ARVERNI
                         and state['scenario'] in rc.ARIOVISTUS_SCENARIOS)
    response = None if automatic_arverni else consult_free_action(state, faction, request)
    if response is None:
        response = default_response(state, faction)
    validate_response(state, faction, response)
    source = {entry['id']: entry for entry in request['pieces']}
    result = []
    for allocation in response['allocations']:
        piece = source[allocation['piece_id']]
        apply_allocation(state, faction, piece, allocation)
        result.append({'faction': faction, 'piece_type': piece['piece_type'],
                       'piece_state': piece.get('piece_state'),
                       'source_tribe': piece.get('tribe'), **allocation})
    return result


def affected_owners(state):
    return [owner for owner in OWNERS if pieces(state, owner)]


def validate_order(state, response):
    owners = affected_owners(state)
    if (not isinstance(response, dict) or set(response) != {'owner_order'}
            or not isinstance(response['owner_order'], list)
            or len(response['owner_order']) != len(owners)
            or any(not isinstance(owner, str) for owner in response['owner_order'])
            or set(response['owner_order']) != set(owners)):
        raise ValueError('Order each affected non-Roman owner exactly once.')


def resolve(state, executor):
    """§5.1 leaves group order to executor; A5 gives each owner its pieces."""
    from fs_bot.cards.card_effects import _event_step
    from fs_bot.engine.free_actions import consult_free_action
    order = affected_owners(state)
    if len(order) > 1:
        request = {'kind': 'free_action', 'request_type': 'gallia_evacuation_order',
                   'card_id': 'A5', 'owners': order, 'allow_decline': False,
                   'free': True, 'with_sa': False}
        response = consult_free_action(state, executor, request)
        if response is None:
            # §8.3.1: benefit self first; §8.3.4 resolves the remaining ties.
            first = [executor] if executor in order else []
            rest = [owner for owner in order if owner != executor]
            state['rng'].shuffle(rest)
            order = first + rest
        else:
            validate_order(state, response)
            order = response['owner_order']
    allocations = []
    for index, owner in enumerate(order):
        # A whole owner's allocation is atomic. Later owners see the actual
        # occupied slots after earlier owners and executor timing choices.
        _event_step(state, 'A5.evacuation', index=index, affected_faction=owner)
        allocations.extend(resolve_owner(state, owner))
    moved = [entry for entry in allocations if entry['destination'] is not None]
    removed = [entry for entry in allocations if entry['destination'] is None]
    return [{'free_action': 'evict_cisalpina', 'flag': 'card_A5',
             'owner_order': order, 'moved': moved, 'removed': removed,
             'executed': bool(allocations)}]
