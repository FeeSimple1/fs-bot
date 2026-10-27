"""Diviciacus's agreed Auxilia/Warband exchange, with physical ownership.

Card 38 and A1.4 change how consenting pieces act, never their colour,
Control, inventory, or destination on removal. A scope keeps the original
borrowed cohort after movement, including beyond the Leader's starting range.
"""
from contextlib import contextmanager, ExitStack
from functools import wraps

from fs_bot import rules_consts as rc

KEY = '_diviciacus_force'
PIECES = {rc.ROMANS: rc.AUXILIA, rc.AEDUI: rc.WARBAND}
STATES = (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)
DIVICIACUS_PIECES = 'diviciacus_pieces'


def partner(faction):
    return rc.AEDUI if faction == rc.ROMANS else rc.ROMANS


def leader_region(state):
    for region, space in state['spaces'].items():
        if space.get('pieces', {}).get(rc.AEDUI, {}).get(rc.LEADER) == rc.DIVICIACUS:
            return region
    return None


def enabled(state, phase='command'):
    from fs_bot.cards.capabilities import is_capability_active
    return (leader_region(state) is not None or
            (phase != 'special_ability' and
             is_capability_active(state, 38, rc.EVENT_UNSHADED)))


def eligible_regions(state, faction, phase='command'):
    """Regions in which physical Auxilia and Aedui Warbands are together."""
    if faction not in PIECES or not enabled(state, phase):
        return []
    from fs_bot.map.map_data import get_adjacent
    leader = leader_region(state)
    near = {leader, *get_adjacent(leader, state.get('scenario'),
                                 state.get('capabilities'))} if leader else None
    from fs_bot.cards.capabilities import is_capability_active
    capability = (phase != 'special_ability' and
                  is_capability_active(state, 38, rc.EVENT_UNSHADED))
    result = []
    for region, space in state['spaces'].items():
        if not capability and region not in near:
            continue
        raw = space.get('pieces', {})
        if all(sum(raw.get(f, {}).get(ps, {}).get(pt, 0) for ps in STATES)
               for f, pt in PIECES.items()):
            result.append(region)
    return sorted(result)


def validate_response(request, response):
    if not isinstance(response, dict) or set(response) != {'counts'}:
        raise ValueError('Diviciacus selection requires counts by physical owner.')
    counts = response['counts']
    available = request['available']
    if (not isinstance(counts, dict) or set(counts) - set(available)
            or any(type(n) is not int or not 0 <= n <= available[f]
                   for f, n in counts.items())
            or sum(counts.values()) != request['count']):
        raise ValueError('Choose the requested number of physical pieces.')
    return response


def choose_owners(state, faction, region, count, available, phase):
    """Exact physical colours for a human subset; NP losses borrow first."""
    lender = partner(faction)
    order = (faction, lender) if phase == 'placement' else (lender, faction)
    left, default = count, {}
    for owner in order:
        take = min(left, available.get(owner, 0))
        default[owner] = take
        left -= take
    if left:
        raise ValueError('Not enough Diviciacus pieces in the selected cohort.')
    if (faction in state.get('non_player_factions', set())
            or not all(available.get(f, 0) for f in order)
            or count == sum(available.values()) or state.get('_diviciacus_preview')):
        return default
    from fs_bot.engine.agent import consult_agent
    request = {'kind': DIVICIACUS_PIECES, 'phase': phase, 'region': region,
               'piece_type': PIECES[faction], 'count': count,
               'available': available}
    response = consult_agent(state, faction, request)
    if response is None or response == {'use_default': True}:
        return default
    validate_response(request, response)
    return {f: response['counts'].get(f, 0) for f in order}


def _targets(action, region):
    details = action.get('details') or {}
    result = []
    for entry in details.get('battle_plan', []) or []:
        if entry.get('region') == region:
            result.extend([entry.get('target')] if entry.get('target') is not None
                          else (entry.get('targets') or [])[:1])
    for entry in details.get('raid_plan', []) or []:
        if isinstance(entry, dict) and entry.get('region') == region:
            result.extend(x.get('target') for x in entry.get('raids', []) if isinstance(x, dict))
            result.append(entry.get('target'))
    scout = details.get('scout_plan')
    if scout is None:
        scout = (details.get('sa_details') or {}).get('scout_plan')
    # _execute_scout consumes region/enemy/hidden entries, not a nested
    # reveals/targets shape. Inspect exactly the targets it will Reveal.
    for entry in (scout or {}).get('scout_targets', []):
        if entry.get('region') == region and entry.get('hidden', 0) > 0:
            result.append(entry.get('enemy'))
    return result


def _np_agrees(state, owner, actor, region, action, phase):
    from fs_bot.engine.victory import check_victory, calculate_victory_score
    command = action.get('command')
    targets = _targets(action, region)
    if owner == rc.AEDUI and actor == rc.ROMANS and action.get('sa') == rc.SA_SCOUT:
        details = action.get('details') or {}
        if (details.get('scout_plan') is None and
                (details.get('sa_details') or {}).get('scout_plan') is None):
            # NP Scout usually derives its plan at execution, after the
            # Command. Check that same plan before granting the SA loan.
            # It is a preview: never call the human or advance live RNG.
            from copy import deepcopy
            from fs_bot.bots.roman_bot import node_r_scout
            preview = deepcopy({k: v for k, v in state.items() if k != 'decision_agent'})
            preview['_diviciacus_preview'] = True
            preview.pop(KEY, None)
            preview.pop('_diviciacus_planning_faction', None)
            scout = node_r_scout(preview)
            targets.extend(_targets({'details': {'scout_plan': scout}}, region))
    if phase == 'defense':
        # §8.8.8: Romans lend to their own defense, never Aedui defense.
        return actor == rc.ROMANS and calculate_victory_score(state, rc.ROMANS) <= 12
    if owner == rc.ROMANS and actor == rc.AEDUI:
        return not check_victory(state, rc.AEDUI) and not (
            command in (rc.CMD_BATTLE, rc.CMD_RAID) and rc.ROMANS in targets)
    if owner == rc.AEDUI and actor == rc.ROMANS:
        return calculate_victory_score(state, rc.ROMANS) <= 12 and not (
            (command == rc.CMD_BATTLE or action.get('sa') == rc.SA_SCOUT) and rc.AEDUI in targets)
    return True


def consent_regions(state, faction, regions, action=None, phase='command'):
    """Obtain one agreement for the action; NP restrictions remain regional."""
    action = action or {}
    regions = list(regions)
    allowed = set(eligible_regions(state, faction, phase))
    if len(regions) != len(set(regions)) or any(r not in allowed for r in regions):
        raise ValueError('Diviciacus selections must be distinct eligible Regions.')
    if not regions:
        return []
    other = partner(faction)
    nonplayers = state.get('non_player_factions', set())
    if other in nonplayers:
        return [r for r in regions if _np_agrees(state, other, faction, r, action, phase)]
    if state.get('_diviciacus_preview'):
        return regions
    from fs_bot.engine.agent import AGREEMENT, consult_agent
    response = consult_agent(state, other, {
        'kind': AGREEMENT, 'request_type': 'diviciacus',
        'requesting_faction': faction,
        'context': {'phase': phase, 'command': action.get('command'),
                    'sa': action.get('sa'), 'regions': regions,
                    'targets': {r: _targets(action, r) for r in regions}}})
    # Raw callback deferral follows the same documented default as other agreements.
    if response is None:
        return [r for r in regions if _np_agrees(state, other, faction, r, action, phase)]
    return regions if response is True or (isinstance(response, dict) and response.get('agree') is True) else []


@contextmanager
def force_scope(state, faction, regions, phase='command'):
    """Expose borrowed counters as the acting type without recolouring them."""
    regions = list(regions)
    old = state.get(KEY)
    if old and old['faction'] == faction and old['phase'] == phase:
        yield
        return
    if not regions:
        yield
        return
    lender = partner(faction)
    physical_type = PIECES[lender]
    ledger = {r: {ps: state['spaces'][r].get('pieces', {}).get(lender, {}).get(ps, {}).get(physical_type, 0)
                  for ps in STATES} for r in regions}
    context = {'faction': faction, 'lender': lender, 'piece_type': PIECES[faction],
               'physical_type': physical_type, 'regions': regions,
               'pieces': ledger, 'phase': phase}
    state[KEY] = context
    try:
        yield
    finally:
        if old is None:
            state.pop(KEY, None)
        else:
            state[KEY] = old


def effective_pieces(state, region, faction, raw):
    ctx = state.get(KEY)
    if not ctx or faction not in (ctx['faction'], ctx['lender']):
        return None
    loan = ctx['pieces'].get(region)
    if loan is None:
        return None
    result = dict(raw)
    for ps in STATES:
        result[ps] = dict(raw.get(ps, {}))
        pt = ctx['piece_type'] if faction == ctx['faction'] else ctx['physical_type']
        combined = state.get('_combined_battle_force', {})
        already_lent = (combined.get('faction') == ctx['faction'] and
                        ctx['lender'] in combined.get('owners', {}).get(region, ()))
        if already_lent and faction == ctx['lender']:
            continue  # A28 has already removed these from the lender's view.
        result[ps][pt] = result[ps].get(pt, 0) + (1 if faction == ctx['faction'] else -1) * loan.get(ps, 0)
        if already_lent and faction == ctx['faction']:
            original = ctx['physical_type']
            result[ps][original] -= loan.get(ps, 0)
    return result


def operate(state, region, faction, piece_type, count, operation, *, owner=None, **kwargs):
    ctx = state.get(KEY)
    if not ctx or region not in ctx['pieces']:
        return False
    actor, lender = ctx['faction'], ctx['lender']
    if faction != actor or piece_type != ctx['piece_type']:
        return False
    from fs_bot.board import pieces as board
    if owner is not None and owner not in (actor, lender):
        return False  # An A28 ally keeps its existing combined-force route.
    if type(count) is not int or count < 0:
        raise board.PieceError('Invalid Diviciacus physical piece selection')
    ps = kwargs.get('from_state') if operation == 'flip' else kwargs.get('piece_state')
    states = (ps,) if ps is not None else STATES
    allocations, remaining = [], count
    # §8.6.8/§8.8.8 use the other faction's pieces to maximum degree.
    for physical_owner in ((owner,) if owner is not None else (lender, actor)):
        physical_type = ctx['physical_type'] if physical_owner == lender else piece_type
        raw = state['spaces'][region].get('pieces', {}).get(physical_owner, {})
        for visibility in states:
            n = (ctx['pieces'][region].get(visibility, 0) if physical_owner == lender
                 else raw.get(visibility, {}).get(physical_type, 0))
            take = min(remaining, n)
            if take:
                allocations.append((physical_owner, physical_type, visibility, take))
                remaining -= take
    if remaining:
        raise board.PieceError('Not enough Diviciacus pieces of the selected owner/state')
    for physical_owner, physical_type, visibility, n in allocations:
        params = dict(kwargs)
        destination = params.pop('destination', None)
        if operation == 'remove':
            params['piece_state'] = visibility
            board._remove_piece_inner(state, region, physical_owner, physical_type, n, **params)
            new_state = None
        elif operation == 'move':
            board._move_piece_inner(state, region, destination, physical_owner, physical_type, n, piece_state=visibility)
            # §3.2.2: native members of the selected group may continue
            # even when no borrowed piece was selected or the last one
            # dropped off/suffered Harassment. Keep their physical-owner
            # route active without lending any destination residents.
            ctx['pieces'].setdefault(destination, {})
            new_state = None
        elif operation == 'flip':
            new_state = params['to_state']
            if visibility == rc.SCOUTED and new_state == rc.HIDDEN:
                new_state = rc.REVEALED
            board._flip_piece_inner(state, region, physical_owner, physical_type, n,
                                    from_state=visibility, to_state=new_state)
        else:
            raise board.PieceError('Unknown Diviciacus piece operation')
        if physical_owner == lender:
            ctx['pieces'][region][visibility] -= n
            if operation == 'move':
                target = ctx['pieces'].setdefault(destination, {})
                target[visibility] = target.get(visibility, 0) + n
            elif operation == 'flip':
                ctx['pieces'][region][new_state] = ctx['pieces'][region].get(new_state, 0) + n
    return True


def loss_choices(state, region, faction, choices):
    ctx = state.get(KEY)
    if not ctx or ctx['faction'] != faction or region not in ctx['pieces']:
        return choices
    piece = ctx['piece_type']
    result = [c for c in choices if c[0] != piece]
    index = next((i for i, c in enumerate(choices) if c[0] == piece), 0)
    borrowed, own = [], []
    raw = state['spaces'][region].get('pieces', {}).get(faction, {})
    for ps in STATES:
        borrowed.extend([(piece, ps, ctx['lender'])] * ctx['pieces'][region].get(ps, 0))
        own.extend([(piece, ps, faction)] * raw.get(ps, {}).get(piece, 0))
    # A28 can additionally lend same-type pieces from other physical owners.
    # Preserve those explicit entries after the Diviciacus borrowing priority.
    other_allies = [c for c in choices if c[0] == piece and len(c) == 3
                   and c[2] not in (faction, ctx['lender'])]
    return result[:index] + borrowed + own + other_allies + result[index:]


def command_scope(function=None, *, phase='command'):
    """Wrap actual Commands/SAs, including Event grants, in agreed forces."""
    def decorate(func):
        @wraps(func)
        def wrapped(state, faction, action, *args, **kwargs):
            if faction not in PIECES or (state.get(KEY) and state[KEY]['faction'] == faction):
                return func(state, faction, action, *args, **kwargs)
            details = action.get('details') or {}
            key = 'diviciacus_sa_regions' if phase == 'special_ability' else 'diviciacus_regions'
            regions = details.get(key)
            if regions is None:
                regions = eligible_regions(state, faction, phase) if faction in state.get('non_player_factions', set()) else []
            if phase == 'special_ability' and action.get('sa') in (
                    None, 'No SA', rc.SA_AMBUSH, rc.SA_BESIEGE):
                regions = []
            if (phase == 'special_ability' and regions and
                    set(regions) - set(eligible_regions(state, faction, phase))):
                return {'executed': False, 'declined_no_effect': True,
                        'reason': 'Diviciacus cooperation is no longer available for this Special Ability'}
            from fs_bot.engine.diviciacus_planning import take_confirmation
            accepted = take_confirmation(state, faction, action, phase)
            if accepted is None:
                accepted = consent_regions(state, faction, regions, action, phase)
            if set(accepted) != set(regions) and faction not in state.get('non_player_factions', set()):
                return {'executed': False, 'command': action.get('command'),
                        'reason': 'Diviciacus agreement was refused; choose a new plan'}
            with force_scope(state, faction, accepted, phase):
                return func(state, faction, action, *args, **kwargs)
        return wrapped
    return decorate(function) if function is not None else decorate


@contextmanager
def defense_scope(state, region, attacker, defender):
    """Make one defense decision even when Battle resolution is nested."""
    key = '_diviciacus_defense_decision'
    decision = (region, attacker, defender)
    old = state.get(key)
    if old == decision:
        yield
        return
    state[key] = decision
    try:
        with _defense_force_scope(state, region, attacker, defender):
            yield
    finally:
        if old is None:
            state.pop(key, None)
        else:
            state[key] = old


@contextmanager
def _defense_force_scope(state, region, attacker, defender):
    if defender not in PIECES or state.get(KEY) or region not in eligible_regions(state, defender, 'defense'):
        yield
        return
    if defender not in state.get('non_player_factions', set()):
        from fs_bot.engine.agent import AGREEMENT, consult_agent
        response = consult_agent(state, defender, {'kind': AGREEMENT, 'request_type': 'diviciacus_defense',
            'requesting_faction': defender, 'context': {'phase': 'defense', 'region': region, 'attacker': attacker}})
        if response is not True and not state.get('_diviciacus_preview'):
            yield
            return
    accepted = consent_regions(state, defender, [region], {'command': rc.CMD_BATTLE}, 'defense')
    with force_scope(state, defender, accepted, 'defense'):
        yield


def defensive_battle(func):
    @wraps(func)
    def wrapped(state, region, attacking_faction, defending_faction, **kwargs):
        with defense_scope(state, region, attacking_faction, defending_faction):
            if kwargs.get('is_ambush') and state.get(KEY, {}).get('phase') == 'defense':
                from fs_bot.commands.sa_ambush import validate_ambush_region
                valid, _ = validate_ambush_region(state, region, attacking_faction, defending_faction)
                if not valid:
                    kwargs['is_ambush'] = False
            return func(state, region, attacking_faction, defending_faction, **kwargs)
    return wrapped


def select_march_group(state, faction, origin, group):
    ctx = state.get(KEY)
    if not ctx or ctx['faction'] != faction or origin not in ctx['pieces']:
        return False
    piece = ctx['piece_type']
    count = group.get(piece, 0)
    if not count:
        return False
    from fs_bot.engine.march_choices import choose_visibility
    lender = ctx['lender']
    raw = state['spaces'][origin].get('pieces', {}).get(faction, {})
    available = {faction: {ps: raw.get(ps, {}).get(piece, 0) for ps in STATES},
                 lender: dict(ctx['pieces'][origin])}
    owners = choose_owners(state, faction, origin, count,
                           {f: sum(v.values()) for f, v in available.items()}, 'formation')
    ledger = group['_diviciacus_owners'] = {}
    combined = group.setdefault('_march_visibility', {})[piece] = {}
    for owner, n in owners.items():
        selected = choose_visibility(state, faction, origin, piece, n,
                                     available[owner], phase='formation', physical_owner=owner)
        ledger[owner] = selected
        for ps, amount in selected.items():
            combined[ps] = combined.get(ps, 0) + amount
    return True


def move_march_group(state, faction, origin, destination, group):
    ctx = state.get(KEY)
    ledger = group.get('_diviciacus_owners')
    if ctx and ctx['faction'] == faction and ledger is None:
        select_march_group(state, faction, origin, group)
        ledger = group.get('_diviciacus_owners')
    if not ctx or ctx['faction'] != faction or ledger is None:
        return None
    from fs_bot.board.pieces import move_piece
    piece = ctx['piece_type']
    for owner, counts in ledger.items():
        for ps, n in counts.items():
            if n:
                move_piece(state, origin, destination, faction, piece, n,
                           piece_state=ps, physical_owner=owner)
    return piece


def drop_march_group(state, faction, region, group, piece, count):
    ctx = state.get(KEY)
    ledger = group.get('_diviciacus_owners')
    if not ctx or ctx['piece_type'] != piece or ledger is None:
        return False
    from fs_bot.engine.march_choices import choose_visibility
    owners = choose_owners(state, faction, region, count,
                           {f: sum(v.values()) for f, v in ledger.items()}, 'dropoff')
    for owner, n in owners.items():
        drop = choose_visibility(state, faction, region, piece, n, ledger[owner],
                                 phase='dropoff', physical_owner=owner)
        for ps, amount in drop.items():
            ledger[owner][ps] -= amount
            group['_march_visibility'][piece][ps] -= amount
    group[piece] -= count
    return True


def march_casualty_owner(state, faction, region, group, visibility):
    ledger = group.get('_diviciacus_owners')
    if ledger is None:
        return None
    owners = choose_owners(state, faction, region, 1,
                           {f: v.get(visibility, 0) for f, v in ledger.items()}, 'loss')
    owner = next(f for f, n in owners.items() if n)
    ledger[owner][visibility] -= 1
    return owner


def placement_available(state, region, faction, piece_type, native):
    ctx = state.get(KEY)
    if (not ctx or ctx['faction'] != faction or ctx['piece_type'] != piece_type
            or ctx['phase'] not in ('command', 'special_ability')
            or region not in ctx['regions']):
        return native
    if faction in state.get('non_player_factions', set()):
        if ctx['phase'] == 'special_ability':
            return native
        if faction == rc.ROMANS or native or rc.ROMANS not in state.get('non_player_factions', set()):
            return native
    return native + state['available'].get(ctx['lender'], {}).get(ctx['physical_type'], 0)


def place_converted(state, region, faction, piece_type, count, **kwargs):
    ctx = state.get(KEY)
    if (not ctx or ctx['faction'] != faction or ctx['piece_type'] != piece_type
            or ctx['phase'] not in ('command', 'special_ability')
            or region not in ctx['regions']):
        return False
    native = state['available'].get(faction, {}).get(piece_type, 0)
    total = placement_available(state, region, faction, piece_type, native)
    other = max(0, total - native)
    owners = choose_owners(state, faction, region, count,
                           {faction: native, ctx['lender']: other}, 'placement')
    from fs_bot.board import pieces as board
    for owner, n in owners.items():
        if not n:
            continue
        physical_type = piece_type if owner == faction else ctx['physical_type']
        board._place_piece_inner(state, region, owner, physical_type, n, **kwargs)
        if owner != faction:
            # Match place_piece's default for omitted or explicit None.
            # The borrowed ledger must track the physical Hidden counters.
            ps = kwargs.get('piece_state') or rc.HIDDEN
            ctx['pieces'][region][ps] = ctx['pieces'][region].get(ps, 0) + n
    return True


@contextmanager
def ambush_scope(state, faction, action, region):
    """A1.4 may enable Ambush independently of lending to the Battle force."""
    if faction not in PIECES:
        yield
        return
    old = state.get(KEY)
    if old and old['faction'] == faction:
        state.pop(KEY, None)
    try:
        details = action.get('details') or {}
        regions = details.get('diviciacus_sa_regions')
        if regions is None:
            regions = eligible_regions(state, faction, 'special_ability') if faction in state.get('non_player_factions', set()) else []
        selected = [region] if region in regions else []
        accepted = consent_regions(state, faction, selected, action, 'special_ability')
        with force_scope(state, faction, accepted, 'special_ability'):
            yield
    finally:
        if old is not None:
            state[KEY] = old
