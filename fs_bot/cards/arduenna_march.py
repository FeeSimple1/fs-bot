"""A67's initial-origin cohorts: no arriving counter may March a second time."""
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces_by_state, flip_piece
from fs_bot.engine.diviciacus import command_scope

STATES = (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)
SOFT = (rc.AUXILIA, rc.WARBAND)


def _pool(state, faction, origin, piece):
    ctx = state.get('_diviciacus_force', {})
    borrowed = (ctx.get('pieces', {}).get(origin, {})
                if ctx.get('faction') == faction and ctx.get('piece_type') == piece else {})
    own = {ps: count_pieces_by_state(state, origin, faction, piece, ps) - borrowed.get(ps, 0)
           for ps in STATES}
    return {faction: own, **({ctx['lender']: dict(borrowed)} if borrowed else {})}



def _reserve(state, faction, origin, group, pools):
    from fs_bot.engine.diviciacus import choose_owners
    from fs_bot.engine.march_choices import choose_visibility
    ledger = group['_march_visibility'] = {}
    for piece in SOFT:
        count = group.get(piece, 0)
        if not count:
            continue
        owners = pools[piece]
        if len(owners) > 1:
            chosen = choose_owners(state, faction, origin, count,
                {owner: sum(values.values()) for owner, values in owners.items()}, 'formation')
            group['_diviciacus_owners'] = {}
        else:
            chosen = {faction: count}
        ledger[piece] = {}
        for owner, n in chosen.items():
            selected = choose_visibility(state, faction, origin, piece, n, owners[owner],
                phase='formation', physical_owner=owner if len(owners) > 1 else None)
            if len(owners) > 1:
                group['_diviciacus_owners'][owner] = selected
            for ps, amount in selected.items():
                owners[owner][ps] -= amount
                ledger[piece][ps] = ledger[piece].get(ps, 0) + amount


def _rows(state, faction, prepared, original, remaining):
    """Form exact physical groups before the origin-by-origin flip procedure."""
    pools = deepcopy(original)
    raw = deepcopy(original)
    rows = {}
    ctx = state.get('_diviciacus_force', {})
    def add(owner, gid, origin, piece, count, visibility=None):
        if not count:
            return
        physical = ctx['physical_type'] if owner != faction else piece
        row = {'id': gid, 'label': gid, 'region': origin, 'piece_type': physical, 'count': count}
        if visibility is not None:
            row['piece_state'] = visibility
        if owner != faction:
            row['loan_kind'] = 'diviciacus'
        rows.setdefault(owner, []).append(row)
    for index, (origin, path, group) in enumerate(prepared):
        gid = f'A67.group.{index + 1}'
        _reserve(state, faction, origin, group, pools[origin])
        add(faction, gid, origin, rc.LEADER, int(group[rc.LEADER] is not None))
        add(faction, gid, origin, rc.LEGION, group[rc.LEGION])
        for piece, visibilities in group['_march_visibility'].items():
            selected = (group['_diviciacus_owners'] if piece == ctx.get('piece_type')
                        and '_diviciacus_owners' in group else {faction: visibilities})
            for owner, values in selected.items():
                for ps, count in values.items():
                    add(owner, gid, origin, piece, count, ps)
                    raw[origin][piece][owner][ps] -= count
    # Unselected initial pieces also need a cohort, so removing them at a
    # later window cannot be confused with arrivals or another selected group.
    for origin, pieces in raw.items():
        gid = f'A67.remaining.{origin}'
        add(faction, gid, origin, rc.LEADER, int(remaining[origin][rc.LEADER] is not None))
        add(faction, gid, origin, rc.LEGION, remaining[origin][rc.LEGION])
        for piece, owners in pieces.items():
            for owner, counts in owners.items():
                for ps, n in counts.items():
                    add(owner, gid, origin, piece, n, ps)
    return rows


@command_scope
def execute_march(state, faction, action, *, free=True):
    from fs_bot.engine.execute import (_collect_march_moves, _mobile_march_group,
                                      _group_has_pieces, _march_with_harassment)
    from fs_bot.cli.human_plan import _march_routes
    from fs_bot.engine.action_windows import window, set_cohorts, get_cohorts, clear_cohorts
    from fs_bot.cards.arduenna import TARGETS
    moves, deferred = _collect_march_moves(state, faction, action)
    if deferred or not moves:
        raise ValueError('Every selected Arduenna origin must supply a moving group.')
    remaining, pools, prepared = {}, {}, []
    for move in moves:
        origin = move['origin']
        if origin not in remaining:
            remaining[origin] = _mobile_march_group(state, faction, origin)
            pools[origin] = {piece: _pool(state, faction, origin, piece) for piece in SOFT}
        available = remaining[origin]
        cap = move.get('group')
        if cap is not None and (not isinstance(cap, dict) or set(cap) - set(available)):
            raise ValueError('Choose only mobile pieces from this initial origin.')
        group = dict(available) if cap is None else {piece: cap.get(piece, 0) for piece in available}
        leader = group.get(rc.LEADER)
        if (leader is not None and type(leader) is not bool
                and leader != available[rc.LEADER] and leader != 0):
            raise ValueError('This Leader is not in the initial origin group.')
        if leader and not available[rc.LEADER]:
            raise ValueError('The Leader may March only once.')
        group[rc.LEADER] = available[rc.LEADER] if leader else None
        for piece in (rc.LEGION, rc.AUXILIA, rc.WARBAND):
            n = group[piece]
            if type(n) is not int or not 0 <= n <= available[piece]:
                raise ValueError('March counts exceed the pieces remaining at their initial origin.')
            available[piece] -= n
        if leader:
            available[rc.LEADER] = None
        path = move.get('path')
        if (not _group_has_pieces(group) or not path or path[-1] not in TARGETS
                or path not in _march_routes(state, origin, faction, group)):
            raise ValueError('Each group must follow a legal route into Nervii or Treveri.')
        prepared.append((origin, path, group))
    # These windows precede physical formation. Validate the authored counts
    # first, then form only surviving counters after any voluntary removal.
    window(state, 'march_before_plan', marching_faction=faction)
    window(state, 'march_before_payment', marching_faction=faction)
    remaining = {origin: _mobile_march_group(state, faction, origin) for origin in remaining}
    pools = {origin: {piece: _pool(state, faction, origin, piece) for piece in SOFT}
             for origin in remaining}
    for origin, path, group in prepared:
        available = remaining[origin]
        if group[rc.LEADER] != available[rc.LEADER]:
            group[rc.LEADER] = None
        if group[rc.LEADER] is not None:
            available[rc.LEADER] = None
        for piece in (rc.LEGION, rc.AUXILIA, rc.WARBAND):
            group[piece] = min(group[piece], available[piece])
            available[piece] -= group[piece]
    registered = _rows(state, faction, prepared, pools, remaining)
    keys = {owner: f'event.A67.origins.{owner}' for owner in registered}
    for owner, rows in registered.items():
        set_cohorts(state, keys[owner], owner, rows)
    flipped, marches = set(), []
    ctx = state.get('_diviciacus_force', {})
    try:
        for index, (origin, path, original_group) in enumerate(prepared):
            if origin not in flipped:
                window(state, 'arduenna_origin', marching_faction=faction, region=origin)
                for owner, key in keys.items():
                    rows = get_cohorts(state, key)
                    for row in rows:
                        if row['region'] != origin or row['piece_type'] not in SOFT or not row['count']:
                            continue
                        ps = row['piece_state']
                        after = rc.HIDDEN if ps == rc.REVEALED else rc.REVEALED if ps == rc.SCOUTED else ps
                        if ps != after:
                            piece = ctx['piece_type'] if owner != faction else row['piece_type']
                            kwargs = {'physical_owner': owner} if owner != faction or ctx.get('faction') == faction else {}
                            flip_piece(state, origin, faction, piece, row['count'],
                                       from_state=ps, to_state=after, **kwargs)
                            row['piece_state'] = after
                    set_cohorts(state, key, owner, rows)
                flipped.add(origin)
            gid = f'A67.group.{index + 1}'
            group = {rc.LEADER: None, rc.LEGION: 0, rc.AUXILIA: 0, rc.WARBAND: 0,
                     '_march_visibility': {}}
            for owner, key in keys.items():
                rows = get_cohorts(state, key)
                for row in rows:
                    if row['id'] != gid or not row['count']:
                        continue
                    piece = ctx['piece_type'] if owner != faction else row['piece_type']
                    if piece == rc.LEADER:
                        group[piece] = original_group[rc.LEADER]
                    else:
                        group[piece] += row['count']
                    if piece in SOFT:
                        ps = row['piece_state']
                        vis = group['_march_visibility'].setdefault(piece, {})
                        vis[ps] = vis.get(ps, 0) + row['count']
                        if piece == ctx.get('piece_type') and ctx.get('faction') == faction:
                            owners = group.setdefault('_diviciacus_owners', {}).setdefault(owner, {})
                            owners[ps] = owners.get(ps, 0) + row['count']
                set_cohorts(state, key, owner, [row for row in rows if row['id'] != gid])
            if not _group_has_pieces(group):
                continue
            final = _march_with_harassment(state, faction, origin, path,
                flipped_origins=flipped, initial_group=group)
            marches.append({'origin': origin, 'final_region': final})
        return {'executed': bool(marches), 'command': rc.CMD_MARCH,
                'marches': marches, 'errors': [], 'total_cost': 0}
    finally:
        for key in keys.values():
            clear_cohorts(state, key)
