"""Shared Event Battle forces without changing any counter's ownership.

Admagetobriga lends Warbands and Auxilia only. The view applies throughout
the granted Battle Command, including losses and Reveal, and never changes
physical Control. Allies, Leaders, Legions and other pieces stay with their
original factions. Litaviccus instead uses all Aedui pieces as the actor's
own for its Battle. Source: Card Reference 45; A Card Reference A28;
§3.2.4/§3.3.4; optional Diviciacus Leader A1.4/A3.3.4.
"""
from contextlib import contextmanager

from fs_bot import rules_consts as rc

COMBINED_KEY = '_combined_battle_force'
TYPES = (rc.WARBAND, rc.AUXILIA)
STATES = (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)


def _context(state, region):
    context = state.get(COMBINED_KEY)
    return context if context and region in context['owners'] else None


@contextmanager
def combined_force(state, faction, owners_by_region, *, piece_types=TYPES,
                   source=None):
    """Treat the specified owners' pieces as the actor's for this Battle."""
    if COMBINED_KEY in state:
        raise ValueError('A combined Battle force is already active')
    state[COMBINED_KEY] = {'faction': faction, 'owners': owners_by_region}
    if piece_types != TYPES:
        state[COMBINED_KEY]['piece_types'] = tuple(piece_types)
    if source is not None:
        state[COMBINED_KEY]['source'] = source
    try:
        yield
    finally:
        state.pop(COMBINED_KEY, None)


@contextmanager
def litaviccus_force(state, faction, region):
    """Card 45 includes all Aedui pieces, without an agreement or doubling."""
    if faction == rc.AEDUI:
        yield
        return
    with combined_force(state, faction, {region: [rc.AEDUI]},
                        piece_types=(rc.WARBAND, rc.ALLY, rc.CITADEL, rc.LEADER),
                        source='Litaviccus'):
        yield


def extra_leaders(state, region, faction):
    """Count borrowed Leaders separately from the actor's named Leader.

    Each causes its ordinary one Loss and can absorb a Loss. Diviciacus
    does not acquire Ambiorix's/Vercingetorix's/Successor's identity or SA
    range; get_leader_in_region therefore retains the native Leader.
    """
    context = _context(state, region)
    if (context is None or context['faction'] != faction
            or rc.LEADER not in context.get('piece_types', TYPES)):
        return 0
    physical = state['spaces'][region].get('pieces', {})
    return sum(physical.get(owner, {}).get(rc.LEADER) is not None
               for owner in context['owners'][region])


def physical_leader(state, region, faction, owner=None):
    """Keep the identity of a selected physical Leader casualty."""
    if owner is not None:
        return state['spaces'][region].get('pieces', {}).get(owner, {}).get(rc.LEADER)
    from fs_bot.board.pieces import get_leader_in_region
    return get_leader_in_region(state, region, faction)


def _npc_allied_choices(state, region, owners):
    """§8.4.1 preserves City/Remi Allies across physical-owner boundaries."""
    from fs_bot.board.pieces import tribe_has_ally_disc
    physical = {key: value for key, value in state.items() if key != COMBINED_KEY}
    tiers = {False: [], True: []}
    for owner in owners:
        for tribe in sorted(state.get('tribes', {})):
            if tribe_has_ally_disc(physical, region, tribe, owner):
                valuable = tribe in rc.TRIBE_TO_CITY or tribe == rc.TRIBE_REMI
                tiers[valuable].append((rc.ALLY, None, owner, tribe))
    for tied in tiers.values():
        state['rng'].shuffle(tied)
    return tiers[False] + tiers[True]


def effective_pieces(state, region, faction, raw):
    """Return the combined view, or None when this faction is unaffected."""
    context = _context(state, region)
    if context is None:
        return None
    actor, owners = context['faction'], context['owners'][region]
    if faction != actor and faction not in owners:
        return None
    result = dict(raw)
    physical = state['spaces'][region].get('pieces', {})
    types = context.get('piece_types', TYPES)
    for visibility in STATES:
        result[visibility] = dict(raw.get(visibility, {}))
        for piece in (piece for piece in types if piece in rc.FLIPPABLE_PIECES):
            if faction == actor:
                result[visibility][piece] = raw.get(visibility, {}).get(piece, 0) + sum(
                    physical.get(owner, {}).get(visibility, {}).get(piece, 0)
                    for owner in owners)
            else:
                result[visibility][piece] = 0
    for piece in types:
        if piece in rc.FLIPPABLE_PIECES:
            continue
        if piece == rc.LEADER:
            if faction != actor:
                result[piece] = None
            # Extra Leaders retain their individual identities in loss
            # choices/counts; never replace the actor's named Leader.
        elif faction == actor:
            result[piece] = raw.get(piece, 0) + sum(
                physical.get(owner, {}).get(piece, 0) for owner in owners)
        else:
            result[piece] = 0
    return result


def loss_choices(state, region, faction, choices):
    """Keep each offered Warband/Auxilia loss attached to its physical owner."""
    context = _context(state, region)
    if context is None or context['faction'] != faction:
        return choices
    physical = state['spaces'][region].get('pieces', {})
    mobile = []
    for visibility in (rc.SCOUTED, rc.REVEALED, rc.HIDDEN):
        tied = []
        for owner in (faction, *context['owners'][region]):
            for piece in TYPES:
                number = physical.get(owner, {}).get(visibility, {}).get(piece, 0)
                converted = state.get('_diviciacus_force', {})
                if (converted.get('lender') == owner
                        and converted.get('physical_type') == piece):
                    # Converted counters belong to the Diviciacus cohort,
                    # including when lent to the opposing defender.
                    number -= converted.get('pieces', {}).get(region, {}).get(visibility, 0)
                tied.extend([(piece, visibility, owner)] * number)
        if faction in state.get('non_player_factions', set()):
            state['rng'].shuffle(tied)  # Equal mobile losses: §8.3.4/§8.4.1.
        mobile.extend(tied)
    others = [choice for choice in choices if choice[0] not in TYPES]
    index = next((i for i, choice in enumerate(choices) if choice[0] in TYPES), 0)
    result = others[:index] + mobile + others[index:]
    types = context.get('piece_types', TYPES)
    static = [piece for piece in types
              if piece not in (*rc.FLIPPABLE_PIECES, rc.LEADER)]
    for piece in static:
        choices = []
        for owner in (faction, *context['owners'][region]):
            choices.extend([(piece, None, owner)] * physical.get(owner, {}).get(piece, 0))
        if faction in state.get('non_player_factions', set()):
            if piece == rc.ALLY:
                choices = _npc_allied_choices(
                    state, region, (faction, *context['owners'][region]))
            else:
                state['rng'].shuffle(choices)
        index = next((i for i, entry in enumerate(result) if entry[0] == piece), len(result))
        result = [entry for entry in result if entry[0] != piece]
        result[index:index] = choices
    if rc.LEADER in types:
        index = next((i for i, entry in enumerate(result) if entry[0] == rc.LEADER), len(result))
        result = [entry for entry in result if entry[0] != rc.LEADER]
        ordinary, diviciacus = [], []
        for owner in (faction, *context['owners'][region]):
            leader = physical.get(owner, {}).get(rc.LEADER)
            if leader is not None:
                target = diviciacus if leader == rc.DIVICIACUS else ordinary
                target.append((rc.LEADER, None, owner))
        result[index:index] = ordinary
        # A1.4/A3.3.4: not merely last in a default order—Diviciacus
        # cannot be offered until every other possible casualty is gone.
        if not result:
            result.extend(diviciacus)
    return result


def operate(state, region, faction, piece_type, count, operation, *, owner=None,
            **kwargs):
    """Route combined remove/flip/move requests through physical piece helpers."""
    context = _context(state, region)
    if context is None:
        return False
    actor, owners = context['faction'], context['owners'][region]
    if faction != actor and faction not in owners:
        return False
    if piece_type not in context.get('piece_types', TYPES):
        return False
    from fs_bot.board import pieces as board
    if faction != actor:
        raise board.PieceError('These pieces belong to the combined Battle force')
    if type(count) is not int or count < 0:
        raise board.PieceError('Combined-force count must be a nonnegative integer')
    allowed = (faction, *owners)
    if owner is not None and owner not in allowed:
        raise board.PieceError('That faction did not lend pieces to this Battle')
    if piece_type not in rc.FLIPPABLE_PIECES:
        if operation != 'remove':
            raise board.PieceError('This combined Battle only removes non-flippable pieces')
        allocations, remaining = [], count
        for physical_owner in ((owner,) if owner is not None else allowed):
            raw = state['spaces'][region].get('pieces', {}).get(physical_owner, {})
            available = (int(raw.get(rc.LEADER) is not None)
                         if piece_type == rc.LEADER else raw.get(piece_type, 0))
            number = min(remaining, available)
            if number:
                allocations.append((physical_owner, number))
                remaining -= number
        if remaining:
            raise board.PieceError('Not enough combined pieces of the selected owner')
        for physical_owner, number in allocations:
            board._remove_piece_inner(state, region, physical_owner, piece_type,
                                      number, **kwargs)
        return True
    visibility = kwargs.get('from_state') if operation == 'flip' else kwargs.get('piece_state')
    states = (visibility,) if visibility is not None else STATES
    allocations, remaining = [], count
    for physical_owner in ((owner,) if owner is not None else allowed):
        raw = state['spaces'][region].get('pieces', {}).get(physical_owner, {})
        for ps in states:
            available = raw.get(ps, {}).get(piece_type, 0)
            converted = state.get('_diviciacus_force', {})
            if (converted.get('lender') == physical_owner
                    and converted.get('physical_type') == piece_type):
                available -= converted.get('pieces', {}).get(region, {}).get(ps, 0)
            number = min(remaining, available)
            if number:
                allocations.append((physical_owner, ps, number))
                remaining -= number
    if remaining:
        raise board.PieceError('Not enough combined Warbands/Auxilia of the selected owner/state')
    for physical_owner, ps, number in allocations:
        params = dict(kwargs)
        destination = params.pop('destination', None)
        if operation == 'remove':
            params['piece_state'] = ps
            board._remove_piece_inner(state, region, physical_owner, piece_type,
                                      number, **params)
        elif operation == 'flip':
            params['from_state'] = ps
            board._flip_piece_inner(state, region, physical_owner, piece_type,
                                    number, **params)
        elif operation == 'move':
            board._move_piece_inner(state, region, destination, physical_owner,
                                    piece_type, number, piece_state=ps)
        else:
            raise board.PieceError('Unknown combined-force operation')
    return True
