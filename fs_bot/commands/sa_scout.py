"""
Scout Special Ability — §4.2.2 (Roman).

Scout may accompany any type of Command, subject to §4.1.3.

Two capabilities:
1. Scout Movement: Move Auxilia from any Regions to adjacent Regions
   (even if no Leader nearby). Revealed stay Revealed, Hidden stay Hidden.
   No piece may move more than once. Cannot move into or out of Britannia.

2. Scout Reveal: In Regions within one of Caesar or with Successor —
   each Hidden Auxilia may flip to Revealed to Reveal up to two Warbands
   in that Region, placing Scouted markers on them.

Reference: §4.2.2, §4.1.2, §4.1.3, A4.2
"""

from fs_bot.rules_consts import (
    # Factions
    ROMANS,
    # Piece types
    AUXILIA, WARBAND,
    # Piece states
    HIDDEN, REVEALED, SCOUTED,
    # Leaders
    CAESAR,
    # Regions
    BRITANNIA,
)
from fs_bot.board.pieces import (
    count_pieces_by_state,
    move_piece, flip_piece,
)
from fs_bot.map.map_data import is_adjacent
from fs_bot.commands.common import CommandError, check_leader_proximity


def clear_scout_cohorts(state):
    from fs_bot import rules_consts as rc
    from fs_bot.engine.action_windows import clear_cohorts
    for owner in (ROMANS, rc.AEDUI):
        clear_cohorts(state, f'scout:{owner}')


def scout_moved_count(state, region, visibility, owner=None):
    from fs_bot import rules_consts as rc
    from fs_bot.engine.action_windows import get_cohorts
    owners = (owner,) if owner is not None else (ROMANS, rc.AEDUI)
    return sum(c['count'] for faction in owners
               for c in get_cohorts(state, f'scout:{faction}')
               if c['region'] == region and c.get('piece_state') == visibility)


def validate_scout_movement_regions(state, origin, target):
    """Scout uses adjacent playable Regions, including Card 5/A5 exceptions."""
    from fs_bot.map.map_data import is_region_playable
    if not all(isinstance(region, str) and is_region_playable(state, region, ROMANS)
               for region in (origin, target)):
        raise CommandError('Scout movement requires playable Regions (§1.4.2)')
    if origin == BRITANNIA or target == BRITANNIA:
        raise CommandError('Scout movement cannot move into or out of Britannia (§4.1.3)')
    if not is_adjacent(origin, target):
        raise CommandError(f'{origin} and {target} are not adjacent')


def scout_movement_step(state, move, *, index=0):
    """One Scout move, reserving the exact pieces that have already moved."""
    from fs_bot import rules_consts as rc
    from fs_bot.engine.action_windows import window, get_cohorts, set_cohorts
    from fs_bot.engine.diviciacus import KEY, choose_owners, validate_response
    origin, target = move['from_region'], move['to_region']
    count, visibility = move['count'], move['piece_state']
    validate_scout_movement_regions(state, origin, target)
    window(state, 'scout_move', author=ROMANS, index=index,
           from_region=origin, to_region=target,
           timing_actions=move.get('timing_actions'))
    if type(count) is not int or count < 1 or visibility not in (HIDDEN, REVEALED):
        raise CommandError('Scout needs a positive count of Hidden or Revealed Auxilia')
    context = state.get(KEY, {})
    borrowed = (context.get('faction') == ROMANS
                and origin in context.get('pieces', {}))
    raw = state['spaces'][origin].get('pieces', {})
    available = {ROMANS: raw.get(ROMANS, {}).get(visibility, {}).get(AUXILIA, 0)
                 - scout_moved_count(state, origin, visibility, ROMANS)}
    if borrowed:
        available[rc.AEDUI] = (context['pieces'][origin].get(visibility, 0)
                              - scout_moved_count(state, origin, visibility, rc.AEDUI))
    if min(available.values()) < 0 or sum(available.values()) < count:
        raise CommandError(f'Not enough unmoved {visibility} Auxilia in {origin}; '
                           'no Scout piece may move twice (§4.2.2)')
    selected = move.get('physical_owners')
    if selected is not None:
        try:
            validate_response({'available': available, 'count': count}, {'counts': selected})
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        allocation = selected
    elif borrowed:
        allocation = choose_owners(state, ROMANS, origin, count, available, 'scout_movement')
    else:
        allocation = {ROMANS: count}
    for owner, amount in allocation.items():
        if not amount:
            continue
        move_piece(state, origin, target, ROMANS, AUXILIA, count=amount,
                   piece_state=visibility, physical_owner=owner if borrowed else None)
        ledger = get_cohorts(state, f'scout:{owner}')
        identifier = f'scout:{owner}:{target}:{visibility}'
        item = next((c for c in ledger if c['id'] == identifier), None)
        if item is None:
            item = {'id': identifier, 'label': 'Already moved by Scout',
                    'region': target, 'piece_type': AUXILIA if owner == ROMANS else WARBAND,
                    'piece_state': visibility, 'count': 0}
            if owner != ROMANS:
                item['loan_kind'] = 'diviciacus'
            ledger.append(item)
        item['count'] += amount
        set_cohorts(state, f'scout:{owner}', owner, ledger)
    return (origin, target, count, visibility)


def scout_move(state, movements, *, after_movements=None):
    """Execute Scout movement — move Auxilia to adjacent Regions.

    §4.2.2: "Move Auxilia as desired from any Regions to adjacent Regions,
    but not into or out of Britannia (Revealed stay Revealed, Hidden stay
    Hidden; no piece may move more than once)."

    No Leader proximity requirement for Scout movement.

    Args:
        state: Game state dict. Modified in place.
        movements: List of dicts, each with:
            "from_region": Source region.
            "to_region": Destination region.
            "count": Number of Auxilia to move.
            "piece_state": HIDDEN or REVEALED.

    Returns:
        dict with:
            "moved": List of (from_region, to_region, count, piece_state).

    Raises:
        CommandError: If movement violates rules.
    """
    from copy import deepcopy
    saved = deepcopy({key: value for key, value in state.items()
                      if key not in ('decision_agent', '_card_turn')})
    agent, card_turn = state.get('decision_agent'), state.get('_card_turn')
    clear_scout_cohorts(state)
    try:
        result = {'moved': [scout_movement_step(state, move, index=index)
                           for index, move in enumerate(movements)]}
        from fs_bot.engine.action_windows import window
        window(state, 'scout_movement_complete', author=ROMANS,
               timing_actions=after_movements)
        return result
    except BaseException:
        state.clear()
        state.update(saved)
        if agent is not None:
            state['decision_agent'] = agent
        if card_turn is not None:
            state['_card_turn'] = card_turn
        raise
    finally:
        clear_scout_cohorts(state)


def scout_reveal_owners(state, region):
    """Hidden Auxilia by physical owner, including agreed Aedui cooperation."""
    from fs_bot import rules_consts as rc
    from fs_bot.engine.diviciacus import KEY
    context = state.get(KEY, {})
    total = count_pieces_by_state(state, region, ROMANS, AUXILIA, HIDDEN)
    if context.get('faction') == ROMANS and region in context.get('pieces', {}):
        borrowed = context['pieces'][region].get(HIDDEN, 0)
        return {ROMANS: total - borrowed, rc.AEDUI: borrowed}
    return {ROMANS: total}


def scout_reveal(state, region, auxilia_count, targets, *, physical_owners=None):
    """§4.2.2: one Auxilia allocation Scouts up to two targets per piece.

    Targets name faction/count and optionally an exact piece_state. Legacy
    count-only rows retain Hidden/Revealed allocation and partial
    fulfillment; explicit cohorts must be available in full. Already-Scouted
    targets need no new marker. Validate/reserve all targets before flipping.
    """
    from fs_bot.engine.spring import atomic
    with atomic(state):
        return _scout_reveal(state, region, auxilia_count, targets, physical_owners)


def _scout_reveal(state, region, auxilia_count, targets, physical_owners):
    from fs_bot import rules_consts as rc
    from fs_bot.map.map_data import get_playable_regions_for_state
    from fs_bot.engine.diviciacus import choose_owners, validate_response
    if region not in get_playable_regions_for_state(state, ROMANS):
        raise CommandError('Scout Reveal requires a playable Region')
    valid, reason = check_leader_proximity(state, region, ROMANS, CAESAR, 'Scout Reveal')
    if not valid:
        raise CommandError(reason)
    if type(auxilia_count) is not int or auxilia_count < 0:
        raise CommandError('Scout Auxilia count must be a nonnegative integer')
    if not isinstance(targets, (list, tuple)):
        raise CommandError('Scout targets must be a list')
    total = 0
    for target in targets:
        if (not isinstance(target, dict) or set(target) - {'faction', 'count', 'piece_state'}
                or target.get('faction') not in rc.FACTIONS or target['faction'] == ROMANS):
            raise CommandError('Scout targets must name non-Roman Warbands')
        if type(target.get('count')) is not int or target['count'] <= 0:
            raise CommandError('Scout target counts must be positive integers')
        if 'piece_state' in target and target['piece_state'] not in (HIDDEN, REVEALED, SCOUTED):
            raise CommandError('Scout targets must name a valid physical visibility')
        total += target['count']
    if total > 2 * auxilia_count:
        raise CommandError(f'Can only reveal up to {2 * auxilia_count} Warbands with '
                           f'{auxilia_count} Auxilia (2 per Auxilia), but {total} requested')
    available = scout_reveal_owners(state, region)
    if sum(available.values()) < auxilia_count:
        raise CommandError(f'Only {sum(available.values())} Hidden Auxilia in {region}, need {auxilia_count}')
    remaining = {(f, ps): count_pieces_by_state(state, region, f, WARBAND, ps)
                 for f in rc.FACTIONS if f != ROMANS for ps in (HIDDEN, REVEALED, SCOUTED)}
    allocated, counts = [], []
    for target in targets:
        faction, count = target['faction'], target['count']
        states = (target['piece_state'],) if 'piece_state' in target else (HIDDEN, REVEALED)
        capacity = sum(remaining[faction, ps] for ps in states)
        if 'piece_state' in target and count > capacity:
            raise CommandError('Scout selects unavailable physical Warbands')
        count = min(count, capacity)
        counts.append((faction, count))
        for ps in states:
            amount = min(count, remaining[faction, ps])
            if amount:
                allocated.append((faction, ps, amount))
                remaining[faction, ps] -= amount
                count -= amount
    if physical_owners is not None:
        try:
            validate_response({'available': available, 'count': auxilia_count}, {'counts': physical_owners})
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        allocation = physical_owners
    elif len(available) > 1:
        allocation = choose_owners(state, ROMANS, region, auxilia_count, available, 'scout_reveal')
    else:
        allocation = {ROMANS: auxilia_count}
    for owner, count in allocation.items():
        if count:
            flip_piece(state, region, ROMANS, AUXILIA, count=count,
                       from_state=HIDDEN, to_state=REVEALED,
                       physical_owner=owner if len(available) > 1 else None)
    placed = []
    for faction, ps, count in allocated:
        if ps != SCOUTED:
            flip_piece(state, region, faction, WARBAND, count=count,
                       from_state=ps, to_state=SCOUTED)
            placed.append((faction, count))
    return {'auxilia_flipped': auxilia_count, 'warbands_revealed': counts, 'scouted_placed': placed}
