"""A28's shared Battle force without changing any counter's ownership.

Admagetobriga lends Warbands and Auxilia only. The view applies throughout
the granted Battle Command, including losses and Reveal, and never changes
physical Control. Allies, Leaders, Legions and other pieces stay with their
original factions. Source: A Card Reference A28; §3.2.4/§3.3.4.
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
def combined_force(state, faction, owners_by_region):
    """Temporarily treat each Region's consenting mobile pieces as the actor's."""
    if COMBINED_KEY in state:
        raise ValueError('A combined Battle force is already active')
    state[COMBINED_KEY] = {'faction': faction, 'owners': owners_by_region}
    try:
        yield
    finally:
        state.pop(COMBINED_KEY, None)


def effective_pieces(state, region, faction, raw):
    """Return the A28 view, or None when this faction is unaffected."""
    context = _context(state, region)
    if context is None:
        return None
    actor, owners = context['faction'], context['owners'][region]
    if faction != actor and faction not in owners:
        return None
    result = dict(raw)
    physical = state['spaces'][region].get('pieces', {})
    for visibility in STATES:
        result[visibility] = dict(raw.get(visibility, {}))
        for piece in TYPES:
            if faction == actor:
                result[visibility][piece] = raw.get(visibility, {}).get(piece, 0) + sum(
                    physical.get(owner, {}).get(visibility, {}).get(piece, 0)
                    for owner in owners)
            else:
                result[visibility][piece] = 0
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
    return others[:index] + mobile + others[index:]


def operate(state, region, faction, piece_type, count, operation, *, owner=None,
            **kwargs):
    """Route A28 remove/flip/move requests through the physical piece helpers."""
    context = _context(state, region)
    if context is None:
        return False
    actor, owners = context['faction'], context['owners'][region]
    if faction != actor and faction not in owners:
        return False
    if piece_type not in TYPES:
        return False
    from fs_bot.board import pieces as board
    if faction != actor:
        raise board.PieceError('These Warbands/Auxilia belong to the combined Battle force')
    if type(count) is not int or count < 0:
        raise board.PieceError('Combined-force count must be a nonnegative integer')
    allowed = (faction, *owners)
    if owner is not None and owner not in allowed:
        raise board.PieceError('That faction did not lend pieces to this Battle')
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
