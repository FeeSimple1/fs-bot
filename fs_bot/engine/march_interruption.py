"""Keep a March's physical cohorts while its standalone ability resolves."""

from collections import defaultdict
from contextlib import contextmanager

from fs_bot import rules_consts as rc
from fs_bot.engine import action_windows, march_timing

PAUSE = '_march_sa_pause'
MOVERS = (rc.LEADER, rc.LEGION, rc.AUXILIA, rc.WARBAND)
_ACTIVE = 'march.sa.active'


def ordered_moves(action):
    """Give an authored boundary a stable group number even if a group cannot move."""
    from fs_bot.commands.common import CommandError
    details = action.get('details') or {}
    plan = details.get('march_plan', details)
    if not isinstance(plan, dict) or 'explicit_moves' in plan:
        raise CommandError('An interrupted March needs explicit origins and routes.')
    origins, routes = plan.get('origins'), plan.get('routes')
    if (not isinstance(origins, list) or not origins
            or any(not isinstance(origin, str) for origin in origins)
            or len(set(origins)) != len(origins) or not isinstance(routes, dict)
            or set(routes) != set(origins)):
        raise CommandError('Supply one route for each distinct March origin.')
    groups = plan.get('groups', {})
    extras = plan.get('extra_groups', [])
    if not isinstance(groups, dict) or set(groups) - set(origins) or not isinstance(extras, list):
        raise CommandError('Supply March groups for the named origins.')
    moves = []

    def add(origin, path, group, *, extra=False):
        if (not isinstance(path, list) or (extra and not path)
                or any(not isinstance(region, str) for region in path)):
            raise CommandError('Each March route must list its successive Regions.')
        if group is not None and (not isinstance(group, dict)
                or set(group) - set(MOVERS)
                or any((type(n) is not bool if piece == rc.LEADER else type(n) is not int or n < 0)
                       for piece, n in group.items())):
            raise CommandError('Choose a Leader flag and nonnegative March group counts.')
        move = {'origin': origin, 'path': path}
        if path:
            move['group'] = group
        else:
            move['stay'] = True
        if extra:
            move['extra_group'] = True
        moves.append(move)

    for origin in origins:
        add(origin, routes[origin], groups.get(origin))
    for entry in extras:
        if (not isinstance(entry, dict) or entry.get('origin') not in origins
                or not entry.get('group')):
            raise CommandError('An extra March group needs a named origin, pieces, and a route.')
        add(entry['origin'], entry.get('route'), entry['group'], extra=True)
    return moves


def validate_boundary(state, faction, action):
    from fs_bot.commands.common import CommandError
    from fs_bot.map.map_data import get_adjacency_type, get_playable_regions_for_state

    moves = ordered_moves(action)
    step = action['details']['sa_after_step']
    if (not isinstance(step, dict) or set(step) != {'group', 'hop'}
            or any(type(step[key]) is not int for key in step)
            or not 1 <= step['group'] <= len(moves)):
        raise CommandError('Choose a March group number and a hop number.')
    path = moves[step['group'] - 1]['path']
    if not 0 <= step['hop'] <= len(path) or (
            step['group'] == len(moves) and step['hop'] == len(path)):
        raise CommandError('Place the Special Ability before the end of the March.')
    playable = set(get_playable_regions_for_state(state, faction))
    for move in moves:
        route = [move['origin'], *move['path']]
        if move['path'] and rc.BRITANNIA in route:
            raise CommandError('No Special Ability with March into/out of Britannia (§4.1.3).')
        if set(route) - playable or any(get_adjacency_type(a, b) is None
                                        for a, b in zip(route, route[1:])):
            raise CommandError('Choose adjacent, playable Regions for the March.')


@contextmanager
def pause(state, faction, region, group, arrivals, sa):
    """Register the moving group, then suspend only the Command's loan scope."""
    from fs_bot.commands.common import CommandError
    from fs_bot.engine.diviciacus import KEY as DIVICIACUS

    if PAUSE in state:
        raise CommandError('Only one March Special Ability can interrupt this Command.')
    members = defaultdict(list)
    for owner, row in march_timing.physical_members(state, faction, region, group):
        members[owner].append(row)
    loan = state.get(DIVICIACUS)
    if loan and loan['faction'] == faction and loan['phase'] == 'command':
        del state[DIVICIACUS]
    else:
        loan = None
    lender = loan['lender'] if loan else None
    parked_key = arrivals.key(faction)
    foreign_key = arrivals.keys.get(lender)
    foreign_parked = action_windows.get_cohorts(state, foreign_key) if foreign_key else []
    if foreign_key:
        action_windows.clear_cohorts(state, foreign_key)
    action_windows.set_cohorts(state, _ACTIVE, faction, members.get(faction, []))
    state[PAUSE] = {'faction': faction, 'sa': sa, 'parked_key': parked_key,
                    'origins': sorted(region for region in arrivals.remaining if arrivals.needs(region)),
                    'loan': loan, 'foreign_active': members.get(lender, []),
                    'foreign_parked': foreign_parked}
    try:
        yield
    finally:
        # Atomic Special Abilities can restore the frame from a detached copy.
        frame = state.pop(PAUSE)
        rows = {faction: action_windows.get_cohorts(state, _ACTIVE)}
        action_windows.clear_cohorts(state, _ACTIVE)
        if loan:
            state[DIVICIACUS] = frame['loan']
            rows[lender] = frame['foreign_active']
            if foreign_key:
                arrivals._set(lender, frame['foreign_parked'])
        march_timing.restore_members(state, faction, group, rows)


def _select(state, frame, owner, region, piece, visibility, operation, count,
            selected, total, label, other_label):
    from fs_bot.commands.common import CommandError
    from fs_bot.engine.diviciacus import choose_force_cohort
    if not 0 <= selected <= total or not 0 <= count <= total:
        raise CommandError('The Special Ability no longer matches the physical March cohorts.')
    if count == 0 or selected == 0:
        return 0
    chooser = owner if operation == 'voluntarily remove' or frame['sa'] == rc.SA_DEVASTATE else frame['faction']
    return choose_force_cohort(state, chooser, {
        'kind': 'force_cohort', 'region': region, 'piece_type': piece,
        'piece_state': visibility, 'operation': operation, 'count': count,
        'physical_owner': owner, 'selected_label': label, 'other_label': other_label,
        'available': {'selected': selected, 'other': total - selected},
    })


def _adjust(rows, region, piece, visibility, count, new_state=None):
    """Change an already selected cohort and keep one row per physical cell."""
    if not count:
        return
    row = next(row for row in rows if _cell(row) == (region, piece, visibility))
    row['count'] -= count
    if new_state is not None:
        _add(rows, dict(row, piece_state=new_state, count=count))


def _cell(row):
    return row['region'], row['piece_type'], row.get('piece_state')


def _add(rows, addition):
    row = next((row for row in rows if _cell(row) == _cell(addition)), None)
    if row is None:
        rows.append(addition)
    else:
        row['count'] += addition['count']


def record_arrival(state, region, owner, piece, visibility, count):
    """A counter added during the pause did not start in this March origin."""
    frame = state[PAUSE]
    if owner != frame['faction'] or piece not in MOVERS or region not in frame['origins']:
        return
    key = frame['parked_key']
    rows = action_windows.get_cohorts(state, key)
    row = {'id': 'marched_pieces', 'label': 'Already marched or newly arrived',
           'region': region, 'piece_type': piece, 'count': count}
    if visibility is not None:
        row['piece_state'] = visibility
    _add(rows, row)
    action_windows.set_cohorts(state, key, owner, rows)


def track_change(state, region, owner, piece, visibility, count, total, operation,
                 *, new_state=None, destination=None, voluntary=False, sa_loan=False):
    """Track the actual physical subset affected by one complete piece operation."""
    frame = state[PAUSE]
    native = owner == frame['faction'] and piece in MOVERS
    loan = frame['loan']
    foreign = loan and owner == loan['lender'] and piece == loan['physical_type']
    if not (native or foreign) or (native and voluntary):
        # Native voluntary choices already update the registered cohorts.
        return
    if native:
        active = action_windows.get_cohorts(state, _ACTIVE)
        parked = action_windows.get_cohorts(state, frame['parked_key'])
    else:
        active, parked = frame['foreign_active'], frame['foreign_parked']
    cell = (region, piece, visibility)
    moving = sum(row['count'] for row in active if _cell(row) == cell)
    waiting = sum(row['count'] for row in parked if _cell(row) == cell)
    available = total
    if foreign:
        from fs_bot.engine.diviciacus import KEY as DIVICIACUS
        ability_loan = state.get(DIVICIACUS, {})
        if (ability_loan.get('phase') == 'special_ability'
                and ability_loan.get('lender') == owner and region not in ability_loan['regions']):
            if sa_loan:
                # These counters arrived by Scout during the pause. They
                # have already left any March group and Command loan.
                return
            available -= ability_loan['pieces'].get(region, {}).get(visibility, 0)
    if destination is not None and f'scout:{owner}' in state.get(action_windows.COHORTS, {}):
        from fs_bot.commands.sa_scout import scout_moved_count
        used = scout_moved_count(state, region, visibility, owner)
        available -= used
        if native and region in frame['origins']:
            waiting -= used
    if voluntary:
        operation = 'voluntarily remove'
    moving_used = _select(state, frame, owner, *cell, operation, count, moving,
                          available, 'moving group', 'other counters')
    waiting_used = _select(state, frame, owner, *cell, operation, count - moving_used,
                           waiting, available - moving, 'already marched or newly arrived',
                           'original pieces outside the moving group')
    if foreign:
        lent = loan['pieces'].get(region, {}).get(visibility, 0)
        still_lent = _select(state, frame, owner, *cell, operation,
            count - moving_used - waiting_used, lent - moving - waiting,
            available - moving - waiting, 'other March loans', 'unlent counters')
        affected = moving_used + waiting_used + still_lent
        if affected:
            cell_loan = loan['pieces'][region]
            cell_loan[visibility] -= affected
            if new_state is not None:
                cell_loan[new_state] = cell_loan.get(new_state, 0) + affected
    _adjust(active, *cell, moving_used, new_state)
    _adjust(parked, *cell, waiting_used, new_state)
    if native:
        action_windows.set_cohorts(state, _ACTIVE, owner, active)
        action_windows.set_cohorts(state, frame['parked_key'], owner, parked)
        if destination is not None:
            record_arrival(state, destination, owner, piece, visibility, count)
