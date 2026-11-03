"""Printed plan limits and named placers for EXP-09's five Event sides.

A Card Reference A29/A30/A36/A43/A45; §§5.1–5.1.3. Fixed numbers
are fulfilled as far as possible. Lack of a replacement never saves its
selected source. Availability is checked after authored timing windows.
"""
from collections import Counter
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_available, place_piece, remove_piece
from fs_bot.map.map_data import get_adjacent_for_state, get_playable_regions_for_state


def supported(card_id, shaded):
    return (card_id, shaded) in {('A29', False), ('A30', False),
                                ('A36', True), ('A43', False), ('A45', False)}


def beneficiaries(state):
    return (rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE)


def clone(state):
    result = deepcopy({key: value for key, value in state.items() if key != 'decision_agent'})
    result['_diviciacus_preview'] = True
    return result


def region_options(state, card_id):
    playable = set(get_playable_regions_for_state(state))
    if card_id == 'A29':
        return sorted(r for r in playable if count_pieces(state, r, rc.GERMANS, rc.SETTLEMENT))
    if card_id in ('A30', 'A36', 'A43'):
        origin = {'A30': rc.SEQUANI, 'A36': rc.SUGAMBRI, 'A43': rc.AEDUI_REGION}[card_id]
        return sorted(playable & {origin, *get_adjacent_for_state(state, origin)})
    marked = {r for r, markers in state.get('markers', {}).items()
              if rc.MARKER_INTIMIDATED in markers}
    near = marked | {r for origin in marked for r in get_adjacent_for_state(state, origin)}
    return sorted(playable & set(rc.CELTICA_REGIONS) & near)


def ally_options(state, regions, owners, *, available=True):
    from fs_bot.cards.all_gaul_gathers import ally_options as choices
    return [{'tribe': tribe, 'faction': owner, 'region': region}
            for region in regions for tribe, owner in choices(state, region, require_available=available)
            if owner in owners and region in get_playable_regions_for_state(state, owner)]


def source_allies(state, regions):
    from fs_bot.cards.card_effects import _tribe_region, _tribe_piece_type
    return [{'tribe': tribe, 'region': _tribe_region(state, tribe), 'faction': info['allied_faction']}
            for tribe, info in sorted(state['tribes'].items())
            if info.get('allied_faction') in rc.FACTIONS
            and _tribe_region(state, tribe) in regions and _tribe_piece_type(state, tribe) == rc.ALLY]


def _entries(params, key):
    entries = params.get(key, [])
    if not isinstance(entries, list) or any(not isinstance(e, dict) for e in entries):
        raise ValueError(f'{key} must be a list of objects')
    return entries


def _count(entry):
    count = entry.get('count', 1)
    if type(count) is not int or count <= 0:
        raise ValueError('Event counts must be positive integers')
    return count


def _fields(entry, allowed):
    if set(entry) - set(allowed) - {'timing_actions'}:
        raise ValueError('Unexpected Event entry fields')


def _totals(params, key='placements', field='piece_type'):
    result = Counter()
    for entry in _entries(params, key):
        result[entry.get(field)] += _count(entry)
    return result


def next_choice(state, card_id, owner, params):
    """Current-board concrete choices for menus and source-based defaults."""
    regions = region_options(state, card_id)
    if card_id == 'A30':
        return {'key': 'region', 'step': 'A30.region', 'options': regions,
                'may_finish': not regions, 'done': True}
    key = ('replacements' if card_id == 'A43' else
           'ally_removals' if card_id == 'A36' and 'ally_removals' in params else 'placements')
    result = {'key': key, 'step': f'{card_id}.{ "allies" if key == "ally_removals" else key}',
              'options': [], 'may_finish': True, 'done': False}
    choices = result['options']
    if key == 'ally_removals':
        if len(params[key]) < 2:
            choices.extend({'tribe': e['tribe']} for e in source_allies(state, regions))
        result['may_finish'] = not choices
    elif card_id == 'A43':
        used = _totals(params, key, 'from_type')
        if used[rc.ALLY] < 2:
            choices.extend({'region': e['region'], 'tribe': e['tribe'], 'from_type': rc.ALLY,
                            'to_faction': target}
                           for e in source_allies(state, regions) if e['faction'] == rc.ARVERNI
                           for target in (rc.ROMANS, rc.AEDUI))
        if used[rc.WARBAND] < 2:
            choices.extend({'region': region, 'from_type': rc.WARBAND, 'piece_state': visibility,
                            'to_faction': target}
                           for region in regions for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)
                           if count_pieces_by_state(state, region, rc.ARVERNI, rc.WARBAND, visibility)
                           for target in (rc.ROMANS, rc.AEDUI))
        result['may_finish'] = not choices
    elif card_id == 'A45':
        if len(params.get(key, [])) < 3:
            choices.extend({'tribe': e['tribe'], 'faction': e['faction']}
                           for e in ally_options(state, regions, beneficiaries(state)))
    else:
        used = _totals(params)
        playable = set(get_playable_regions_for_state(state, owner))
        regions = [r for r in regions if r in playable]
        mobile = rc.AUXILIA if owner == rc.ROMANS else rc.WARBAND
        cap = (3 if owner == rc.ROMANS else 5) if card_id == 'A29' else 4
        if card_id == 'A29' and used[rc.ALLY] < 2:
            choices.extend({'region': e['region'], 'tribe': e['tribe'], 'faction': owner,
                            'piece_type': rc.ALLY, 'count': 1}
                           for e in ally_options(state, regions, (owner,)))
        if card_id == 'A36' and used[rc.SETTLEMENT] < 2 and get_available(state, owner, rc.SETTLEMENT):
            choices.extend({'region': r, 'piece_type': rc.SETTLEMENT, 'count': 1}
                           for r in regions if not count_pieces(state, r, owner, rc.SETTLEMENT))
        if used[mobile] < cap and get_available(state, owner, mobile):
            choices.extend({'region': r, 'piece_type': mobile, 'count': 1,
                            **({'faction': owner} if card_id == 'A29' else {})} for r in regions)
        result['may_finish'] = not any(e['piece_type'] != rc.ALLY for e in choices)
    return result


def _validate_shape(state, card_id, owner, params):
    from fs_bot.cards.card_effects import _tribe_region
    if not isinstance(params, dict):
        raise ValueError('Event choices must be an object')
    keys = {'A29': {'faction', 'placements'}, 'A30': {'region'},
            'A36': {'placements', 'ally_removals'}, 'A43': {'replacements'}, 'A45': {'placements'}}[card_id]
    if set(params) - keys - {'stage_timing_actions'}:
        raise ValueError(f'{card_id} has unexpected or wrong-side choices')
    regions = set(region_options(state, card_id))
    if card_id == 'A29' and (owner not in beneficiaries(state) or params.get('faction', owner) != owner):
        raise ValueError('A29 has one Gallic or Roman beneficiary')
    if card_id == 'A30':
        if params.get('region') is not None and params['region'] not in regions:
            raise ValueError('A30 selects one Region within one of Sequani')
        return
    if card_id in ('A29', 'A36', 'A45'):
        totals, tribes = Counter(), set()
        for entry in _entries(params, 'placements'):
            _fields(entry, {'region', 'piece_type', 'faction', 'count', 'tribe'})
            kind = rc.ALLY if card_id == 'A45' else entry.get('piece_type')
            if card_id == 'A45' and entry.get('piece_type', rc.ALLY) != rc.ALLY:
                raise ValueError('A45 places Allies only')
            faction = entry.get('faction', owner)
            tribe = entry.get('tribe')
            region = entry.get('region', _tribe_region(state, tribe))
            count = _count(entry)
            allowed = ((rc.ALLY,) if card_id == 'A45' else (rc.SETTLEMENT, rc.WARBAND)
                       if card_id == 'A36' else (rc.ALLY, rc.AUXILIA if owner == rc.ROMANS else rc.WARBAND))
            if kind not in allowed or region not in regions:
                raise ValueError(f'{card_id} placement has an ineligible piece or Region')
            if (faction not in beneficiaries(state) if card_id == 'A45' else faction != owner):
                raise ValueError(f'{card_id} placement has an ineligible owner')
            if kind in (rc.ALLY, rc.SETTLEMENT) and count != 1:
                raise ValueError('Each structure entry places exactly one piece')
            if kind == rc.ALLY:
                if tribe in tribes or _tribe_region(state, tribe) != region:
                    raise ValueError('Choose distinct existing Tribe locations matching their Regions')
                tribes.add(tribe)
            elif tribe is not None:
                raise ValueError('Only an Ally placement names a Tribe')
            totals[kind] += count
        caps = ({rc.ALLY: 3} if card_id == 'A45' else {rc.SETTLEMENT: 2, rc.WARBAND: 4}
                if card_id == 'A36' else {rc.ALLY: 2, rc.WARBAND: 5, rc.AUXILIA: 3})
        if any(totals[kind] > caps[kind] for kind in totals):
            raise ValueError(f'{card_id} exceeds its printed placement quota')
    if card_id == 'A36':
        seen = set()
        for entry in _entries(params, 'ally_removals'):
            _fields(entry, {'tribe'})
            tribe = entry.get('tribe')
            if tribe in seen or _tribe_region(state, tribe) not in regions:
                raise ValueError('A36 removes distinct Allies within one of Sugambri')
            seen.add(tribe)
        if len(seen) > 2:
            raise ValueError('A36 removes at most two Allies')
    if card_id == 'A43':
        totals, seen = Counter(), Counter()
        for entry in _entries(params, 'replacements'):
            _fields(entry, {'region', 'from_type', 'to_faction', 'piece_state', 'tribe'})
            kind, region = entry.get('from_type'), entry.get('region')
            if kind not in (rc.ALLY, rc.WARBAND) or region not in regions or entry.get('to_faction') not in (rc.ROMANS, rc.AEDUI):
                raise ValueError('A43 replaces Arverni Allies/Warbands near Bibracte with Roman/Aedui counterparts')
            if kind == rc.ALLY:
                tribe = entry.get('tribe')
                if entry.get('piece_state') is not None or _tribe_region(state, tribe) != region or seen[tribe]:
                    raise ValueError('A43 selects a distinct exact Allied Tribe')
                seen[tribe] += 1
            elif entry.get('tribe') is not None or entry.get('piece_state', rc.HIDDEN) not in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
                raise ValueError('A43 Warbands require an exact valid visibility')
            totals[kind] += 1
        if any(n > 2 for n in totals.values()):
            raise ValueError('A43 replaces at most two Allies and two Warbands')


def _apply(state, card_id, owner, params, *, complete=True):
    from fs_bot.cards.card_effects import _event_entries, _ally_tribe, _unally_tribe, _tribe_region, _tribe_piece_type
    _validate_shape(state, card_id, owner, params)
    if card_id == 'A30':
        region = params.get('region')
        if region is None:
            if complete and any(count_pieces(state, r, rc.ARVERNI) for r in region_options(state, card_id)):
                raise ValueError('A30 requires a selected Region')
            return
        for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
            count = count_pieces_by_state(state, region, rc.ARVERNI, rc.WARBAND, visibility)
            if count:
                remove_piece(state, region, rc.ARVERNI, rc.WARBAND, count=count, piece_state=visibility)
        for tribe, info in list(state['tribes'].items()):
            if info.get('allied_faction') == rc.ARVERNI and _tribe_region(state, tribe) == region:
                _unally_tribe(state, tribe)
        if count_pieces(state, region, rc.ARVERNI, rc.LEADER):
            remove_piece(state, region, rc.ARVERNI, rc.LEADER)
        return
    if card_id in ('A29', 'A36', 'A45'):
        for entry in _event_entries(state, f'{card_id}.placements', _entries(params, 'placements')):
            kind = rc.ALLY if card_id == 'A45' else entry['piece_type']
            faction = entry.get('faction', owner)
            region = entry.get('region', _tribe_region(state, entry.get('tribe')))
            if region not in get_playable_regions_for_state(state, faction):
                raise ValueError('Selected faction cannot stack in that Region')
            if kind == rc.ALLY:
                if not any(e['tribe'] == entry['tribe'] and e['faction'] == faction
                           for e in ally_options(state, [region], [faction], available=False)):
                    raise ValueError('Ally placement needs a legal Subdued Tribe')
                _ally_tribe(state, entry['tribe'], faction)
            else:
                if kind == rc.SETTLEMENT and count_pieces(state, region, faction, kind):
                    raise ValueError('A Region may contain only one Settlement')
                number = min(_count(entry), get_available(state, faction, kind))
                if number:
                    place_piece(state, region, faction, kind, count=number)
        if complete and card_id in ('A29', 'A36'):
            check = dict(params)
            check.pop('ally_removals', None)
            if not next_choice(state, card_id, owner, check)['may_finish']:
                raise ValueError(f'{card_id} must place its remaining fixed-number pieces when possible')
    if card_id == 'A36':
        for entry in _event_entries(state, 'A36.allies', _entries(params, 'ally_removals')):
            tribe = entry['tribe']
            if not any(e['tribe'] == tribe for e in source_allies(state, region_options(state, card_id))):
                raise ValueError('A36 removes an existing Ally, not a Citadel or empty Tribe')
            _unally_tribe(state, tribe)
        if complete and not next_choice(state, card_id, owner, dict(params, ally_removals=params.get('ally_removals', [])))['may_finish']:
            raise ValueError('A36 must remove two Allies when possible')
    if card_id == 'A43':
        for entry in _event_entries(state, 'A43.replacements', _entries(params, 'replacements')):
            region, kind, target = entry['region'], entry['from_type'], entry['to_faction']
            if kind == rc.ALLY:
                tribe = entry['tribe']
                if (state['tribes'][tribe].get('allied_faction') != rc.ARVERNI
                        or _tribe_piece_type(state, tribe) != rc.ALLY):
                    raise ValueError('A43 selects an existing Arverni Ally')
                _unally_tribe(state, tribe)
                # §5.1.1: failure to place the counterpart does not save the source.
                if any(e['tribe'] == tribe for e in ally_options(state, [region], [target], available=False)):
                    _ally_tribe(state, tribe, target)
            else:
                visibility = entry.get('piece_state', rc.HIDDEN)
                if not count_pieces_by_state(state, region, rc.ARVERNI, rc.WARBAND, visibility):
                    raise ValueError('A43 selects an existing exact Arverni Warband')
                remove_piece(state, region, rc.ARVERNI, rc.WARBAND, piece_state=visibility)
                target_kind = rc.AUXILIA if target == rc.ROMANS else rc.WARBAND
                if get_available(state, target, target_kind):
                    place_piece(state, region, target, target_kind)
        if complete and not next_choice(state, card_id, owner, params)['may_finish']:
            raise ValueError('A43 must replace two Allies and two Warbands when possible')


def preview(state, card_id, owner, params):
    from fs_bot.engine.action_windows import scope
    sim = clone(state)
    executor = state.get('executing_faction') or owner
    sim['event_params'] = deepcopy(params)
    sim['executing_faction'] = owner
    with scope(sim, actor=executor, plan=params, force=True):
        _apply(sim, card_id, owner, params, complete=False)
    return sim


def validate_response(state, owner, request, response):
    from fs_bot.engine.action_windows import scope
    sim = clone(state)
    executor = state.get('executing_faction') or owner
    sim['event_params'] = deepcopy(response)
    sim['executing_faction'] = owner
    with scope(sim, actor=executor, plan=response, force=True):
        _apply(sim, request['card_id'], owner, response)


def _entry_region(state, entry):
    from fs_bot.cards.card_effects import _tribe_region
    # Card 71 creates a Tribe whose Region lives in state, not the printed
    # map. Use that same geography for tie groups and Region continuation.
    return entry.get('region', _tribe_region(state, entry.get('tribe')))


def _default_entry(state, card_id, owner, choices, previous_region=None, *, rng_state=None):
    from fs_bot.bots.bot_common import random_select, is_ally_in_city_or_remi, get_faction_targeting_order
    # Prefer own benefits, structures/City Allies, then target and visibility
    # priorities; exhaust a chosen Region before selecting another equal one.
    def score(entry):
        kind = entry.get('piece_type', entry.get('from_type', rc.ALLY))
        tribe = entry.get('tribe')
        target = state['tribes'].get(tribe, {}).get('allied_faction')
        faction_order = list(get_faction_targeting_order(owner, state['scenario']))
        enemy = faction_order.index(target) if target in faction_order else len(faction_order)
        own = (target != owner if card_id == 'A36' and 'piece_type' not in entry
               else entry.get('to_faction', entry.get('faction', owner)) == owner)
        if card_id == 'A43':
            own = own and replacement_possible(state, entry, owner)
        priority = (0 if kind == rc.SETTLEMENT else 1 if kind == rc.ALLY and is_ally_in_city_or_remi(tribe, state['scenario'])
                    else 2 if kind == rc.ALLY else 3)
        visibility = (rc.HIDDEN, rc.REVEALED, rc.SCOUTED).index(entry.get('piece_state', rc.HIDDEN))
        return (not own, priority, enemy, visibility)
    best = min(map(score, choices))
    candidates = [e for e in choices if score(e) == best]
    if previous_region is not None:
        same = [e for e in candidates if _entry_region(state, e) == previous_region]
        candidates = same or candidates
    # Equal Regions, then equal targets within that Region, each by seeded tie.
    regions = sorted({_entry_region(state, e) for e in candidates})
    random_state = state if rng_state is None else rng_state
    region = random_select(random_state, regions)
    return random_select(random_state, [e for e in candidates if _entry_region(state, e) == region])


def default_params(state, card_id, owner):
    from fs_bot.bots.bot_common import random_select
    if card_id == 'A30':
        regions = region_options(state, card_id)
        if not regions:
            return {}
        def score(region):
            # §§8.2.3/8.3.1 rank Event Regions by structures, then other
            # pieces. §8.4.1's Leader-first priority applies only after the
            # Region has been selected; this Event removes everything there.
            citadels = count_pieces(state, region, rc.ARVERNI, rc.CITADEL)
            allies = count_pieces(state, region, rc.ARVERNI, rc.ALLY)
            others = count_pieces(state, region, rc.ARVERNI) - citadels - allies
            return citadels, allies, others
        best = max(map(score, regions))
        return {'region': random_select(state, [r for r in regions if score(r) == best])}
    params = {'faction': owner, 'placements': []} if card_id == 'A29' else {}
    sim, previous = clone(state), None
    for _ in range(20):
        spec = next_choice(sim, card_id, owner, params)
        if card_id in ('A43', 'A45'):
            field = 'to_faction' if card_id == 'A43' else 'faction'
            spec['options'] = [e for e in spec['options'] if e[field] == owner]
        if not spec['options']:
            if card_id == 'A36' and spec['key'] == 'placements':
                params['ally_removals'] = []
                continue
            break
        entry = _default_entry(sim, card_id, owner, spec['options'], previous, rng_state=state)
        params.setdefault(spec['key'], []).append(entry)
        previous = _entry_region(sim, entry)
        sim = preview(state, card_id, owner, params)
    return params


def execute(state, card_id):
    from fs_bot.engine.free_actions import consult_free_action
    executor = state.get('executing_faction')
    params = state.get('event_params')
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ValueError('Event choices must be an object')
    owner = executor
    if card_id == 'A29':
        owners = [e.get('faction', executor) for e in _entries(params, 'placements')]
        if any(not isinstance(f, str) for f in owners):
            raise ValueError('A29 placement owners must be faction names')
        inferred = set(owners)
        owner = params.get('faction', next(iter(inferred)) if len(inferred) == 1 else executor)
        if owner not in beneficiaries(state) or len(inferred) > 1:
            raise ValueError('A29 has one Gallic or Roman beneficiary')
    elif card_id == 'A36':
        owner = rc.GERMANS
    if card_id in ('A29', 'A36'):
        if owner != executor and any(params.get(k) for k in ('placements', 'ally_removals')):
            raise ValueError('The named placing faction chooses its own Event pieces')
        if owner != executor or not any(k in params for k in ('placements', 'ally_removals')):
            _validate_shape(state, card_id, owner, params)
            request = {'kind': 'free_action', 'request_type': 'expansion_event_choices',
                       'card_id': card_id, 'acting_faction': owner, 'allow_decline': False,
                       'free': True, 'with_sa': False, 'regions': region_options(state, card_id)}
            automatic = owner == rc.ARVERNI and state['scenario'] in rc.ARIOVISTUS_SCENARIOS
            chosen = None if automatic else consult_free_action(state, owner, request)
            params = chosen if chosen is not None else default_params(state, card_id, owner)
    previous = state.get('event_params')
    previous_executor = state.get('executing_faction')
    state['event_params'] = params
    state['executing_faction'] = owner
    try:
        _apply(state, card_id, owner, params)
    finally:
        state['event_params'] = previous
        state['executing_faction'] = previous_executor


def derive_params(state, faction, card_id):
    """NP/default choices for the validated sides, using printed priorities."""
    if card_id == 'A36':
        # The named Germans own both components, even on another NPC turn.
        return None
    if card_id == 'A29' and faction not in beneficiaries(state):
        return None
    return default_params(state, card_id, faction)


def replacement_possible(state, entry, owner):
    kind = rc.ALLY if entry['from_type'] == rc.ALLY else rc.AUXILIA if owner == rc.ROMANS else rc.WARBAND
    if get_available(state, owner, kind) <= 0 or entry['region'] not in get_playable_regions_for_state(state, owner):
        return False
    return kind != rc.ALLY or rc.TRIBE_FACTION_RESTRICTION.get(entry['tribe'], owner) == owner


def np_available(state, card_id, faction):
    """§8.1.1/8.2.3: no impossible or other-recipient-only NP benefit."""
    if card_id == 'A30':
        return any(count_pieces(state, r, rc.ARVERNI) for r in region_options(state, card_id))
    if card_id == 'A29':
        if faction not in beneficiaries(state):
            return False
        if faction == rc.ROMANS and get_available(state, faction, rc.AUXILIA) < 3:
            return False  # Printed Harudes Roman instruction, not human legality.
    owner = rc.GERMANS if card_id == 'A36' else faction
    choices = next_choice(state, card_id, owner, {})['options']
    if card_id == 'A36':
        return bool(choices or source_allies(state, region_options(state, card_id)))
    if card_id == 'A45':
        return any(e['faction'] == faction for e in choices)
    if card_id != 'A43':
        return bool(choices)
    if faction not in (rc.ROMANS, rc.AEDUI):
        return False
    from itertools import combinations, product
    regions = region_options(state, card_id)
    allies = [e for e in source_allies(state, regions) if e['faction'] == rc.ARVERNI]
    quota = min(2, len(allies))
    own_max = min(quota, get_available(state, faction, rc.ALLY), sum(
        rc.TRIBE_FACTION_RESTRICTION.get(e['tribe'], faction) == faction
        and e['region'] in get_playable_regions_for_state(state, faction) for e in allies))
    any_max = 0
    for count in range(1, quota + 1):
        for selected in combinations(allies, count):
            for owners in product((rc.ROMANS, rc.AEDUI), repeat=count):
                if (all(owners.count(owner) <= get_available(state, owner, rc.ALLY) for owner in owners)
                        and all(rc.TRIBE_FACTION_RESTRICTION.get(e['tribe'], owner) == owner
                                and e['region'] in get_playable_regions_for_state(state, owner)
                                for e, owner in zip(selected, owners))):
                    any_max = count
    if own_max < any_max:
        return False
    quota = min(2, sum(count_pieces(state, r, rc.ARVERNI, rc.WARBAND) for r in regions))
    own_stock = get_available(state, faction, rc.AUXILIA if faction == rc.ROMANS else rc.WARBAND)
    combined_stock = get_available(state, rc.ROMANS, rc.AUXILIA) + get_available(state, rc.AEDUI, rc.WARBAND)
    return min(quota, own_stock) == min(quota, combined_stock) and bool(choices)
