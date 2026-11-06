"""Exact physical piece selections for base and expansion Events.

Card Reference 3/5/6/7/11/19/22/24/31/45/58/60/61, A Card Reference
11/A5/A17/A36/A69 and Chapter 5 §§5.1–5.1.3.
Live responses are strict. Authored legacy region and replacement lists
retain their selection priorities.
"""
from collections import Counter

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import _count_on_legions_track, count_pieces, count_pieces_by_state, get_available
from fs_bot.board.control import is_controlled_by
from fs_bot.map.map_data import get_adjacent_for_state, get_playable_regions_for_state

KIND = 'event_piece_choice'
STATES = (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)
FIELDS = ('region', 'target_faction', 'piece_type', 'piece_state')
GARRISON_TOTALS = {rc.LEGION: 1, rc.AUXILIA: 2}
ROMAN_TOTALS = {3: {rc.LEGION: 2}, 5: GARRISON_TOTALS, 'A5': GARRISON_TOTALS}
A36_TOTALS = {rc.SETTLEMENT: 2, rc.WARBAND: 8}
A36_REGIONS = (rc.MORINI, rc.NERVII, rc.TREVERI)
A17_LIMIT = 4
MARCUS_ANTONIUS_LIMIT = 4
ALAUDAE_TRACK_LIMIT = 7
ALAUDAE_STEPS = ((rc.LEGION, '7.legion_removal', 'legion_removal_region'),
                 (rc.AUXILIA, '7.auxilia_removal', 'auxilia_removal_region'))
NUMIDIANS_LIMIT = 4
LITAVICCUS_REGIONS = 2
LITAVICCUS_PER_REGION = 2
ADUATUCA_LIMIT = 9
ADUATUCA_FACTIONS = (rc.BELGAE, rc.GERMANS)
INDUTIOMARUS_LIMIT = 6
COTUATUS_FACTIONS = {'roman': (rc.ROMANS,), 'aedui': (rc.AEDUI,),
                     'third': (rc.ROMANS, rc.AEDUI)}
LEGACY_ROMAN_KEYS = {'legion_removal_regions', 'legion_removal_region', 'auxilia_removal_regions'}
A5_LEGACY_KEYS = {'legion_region', 'auxilia_removals'}


def choice_request(state, card_id):
    owner = state.get('executing_faction')
    if card_id == 6:
        regions = sorted(region for region in state['spaces'] if region != rc.PROVINCIA)
        request = _required_removal_request(state, card_id, owner, rc.ROMANS, regions,
                                            {rc.AUXILIA: MARCUS_ANTONIUS_LIMIT})
        request['max_count'] = request.pop('required')[rc.AUXILIA]
        request['destination'] = rc.PROVINCIA
        return request
    regions = get_playable_regions_for_state(state)
    if card_id == 45:
        limit = LITAVICCUS_REGIONS * LITAVICCUS_PER_REGION
        request = _required_removal_request(state, card_id, owner, rc.ARVERNI, sorted(regions),
                                            {rc.WARBAND: limit})
        request.pop('required')
        return dict(request, max_count=limit, max_regions=LITAVICCUS_REGIONS,
                    max_per_region=LITAVICCUS_PER_REGION)
    if card_id == 19:
        nearby = {rc.PROVINCIA, *get_adjacent_for_state(state, rc.PROVINCIA)}
        regions = [r for r in regions if r in nearby]
    elif card_id == 22:
        regions = [r for r in regions if owner and is_controlled_by(state, r, owner)]
    else:
        raise ValueError('Unsupported optional piece Event')
    available = []
    for region in regions:
        for faction in ((rc.ARVERNI,) if card_id == 19 else rc.FACTIONS):
            piece_type = rc.AUXILIA if faction == rc.ROMANS else rc.WARBAND
            for visibility in STATES:
                count = count_pieces_by_state(state, region, faction, piece_type, visibility)
                if count:
                    available.append(dict(zip(FIELDS, (region, faction, piece_type, visibility)), count=count))
    return {'kind': KIND, 'card_id': card_id, 'owner': owner, 'available': available,
            'legal_regions': list(regions), 'max_count': 6 if card_id == 19 else 4,
            'auxilia_max': 5, 'auxilia_available': get_available(state, rc.ROMANS, rc.AUXILIA)}


def roman_removal_request(state, card_id):
    """Offer only on-map cohorts and require all printed removals possible."""
    regions = get_playable_regions_for_state(state, rc.ROMANS)
    return _required_removal_request(state, card_id, rc.ROMANS, rc.ROMANS,
                                     regions, ROMAN_TOTALS[card_id])


def a36_removal_request(state):
    return _required_removal_request(state, 'A36', state.get('executing_faction'),
                                     rc.GERMANS, A36_REGIONS, A36_TOTALS)


def numidians_removal_request(state):
    return _required_removal_request(state, 11, state.get('executing_faction'), rc.ROMANS,
                                     sorted(state['spaces']),
                                     {rc.AUXILIA: NUMIDIANS_LIMIT})


def alaudae_request(state, kind):
    return _required_removal_request(state, 7, state.get('executing_faction'), rc.ROMANS,
                                     sorted(state['spaces']), {kind: 1})


def a69_removal_request(state):
    region = rc.TRIBE_TO_REGION[rc.TRIBE_BELLOVACI]
    return _required_removal_request(state, 'A69', state.get('executing_faction'),
                                     rc.BELGAE, (region,), {rc.WARBAND: 4})


def a17_removal_request(state):
    return auxilia_region_request(state, 'A17', get_playable_regions_for_state(state, rc.ROMANS),
                                  A17_LIMIT)


def cotuatus_request(state, slot):
    from fs_bot.cards.card_effects import _tribe_piece_type, _tribe_region

    factions = COTUATUS_FACTIONS[slot]
    targets = [{'tribe': tribe, 'region': _tribe_region(state, tribe),
                'target_faction': info['allied_faction']}
               for tribe, info in sorted(state['tribes'].items())
               if info.get('allied_faction') in factions
               and _tribe_piece_type(state, tribe) == rc.ALLY]
    return {'kind': KIND, 'card_id': 31, 'owner': state.get('executing_faction'),
            'slot': slot, 'targets': targets}


def auxilia_region_request(state, card_id, regions, limit):
    return _region_removal_request(state, card_id, regions, (rc.AUXILIA,), limit)


def sappers_request(state):
    regions = [region for region in sorted(state['spaces'])
               if count_pieces(state, region, rc.ARVERNI, rc.CITADEL)]
    return _region_removal_request(state, 24, regions, (rc.LEGION, rc.AUXILIA), 2)


def aduatuca_request(state):
    regions = [region for region in sorted(get_playable_regions_for_state(state))
               if count_pieces(state, region, rc.ROMANS, rc.FORT)]
    return _region_removal_request(state, 58, regions, (rc.WARBAND,), ADUATUCA_LIMIT,
                                   ADUATUCA_FACTIONS)


def indutiomarus_request(state):
    from fs_bot.cards.card_effects import _tribe_piece_type, _tribe_region

    regions = sorted((rc.TREVERI, *get_adjacent_for_state(state, rc.TREVERI)))
    owner = state.get('executing_faction')
    warbands = _required_removal_request(state, 60, owner, rc.BELGAE, regions,
                                         {rc.WARBAND: INDUTIOMARUS_LIMIT})['available']
    allies = []
    for tribe, info in sorted(state['tribes'].items()):
        region = _tribe_region(state, tribe)
        if (region in regions and info.get('allied_faction') == rc.BELGAE
                and _tribe_piece_type(state, tribe) == rc.ALLY):
            allies.append({'region': region, 'target_faction': rc.BELGAE, 'piece_type': rc.ALLY,
                           'piece_state': None, 'count': 1, 'tribe': tribe})
    return _regional_request(60, owner, regions, allies + warbands, INDUTIOMARUS_LIMIT)


def _region_removal_request(state, card_id, regions, kinds, limit, targets=(rc.ROMANS,)):
    owner = state.get('executing_faction')
    available = [entry for faction in targets for entry in _required_removal_request(
        state, card_id, owner, faction, regions, dict.fromkeys(kinds, limit))['available']]
    return _regional_request(card_id, owner, regions, available, limit)


def _regional_request(card_id, owner, regions, available, limit):
    totals = Counter()
    for entry in available:
        totals[entry['region']] += entry['count']
    return {'kind': KIND, 'card_id': card_id, 'owner': owner, 'available': available,
            'required_by_region': {region: min(limit, totals[region]) for region in regions}}


def _required_removal_request(state, card_id, owner, target, regions, limits):
    available = []
    totals = Counter()
    for kind in limits:
        for region in regions:
            for visibility in (STATES if kind in (rc.AUXILIA, rc.WARBAND) else (None,)):
                count = (count_pieces_by_state(state, region, target, kind, visibility)
                         if visibility else count_pieces(state, region, target, kind))
                if count:
                    available.append(dict(zip(FIELDS, (region, target, kind, visibility)), count=count))
                    totals[kind] += count
    return {'kind': KIND, 'card_id': card_id, 'owner': owner,
            'available': available,
            'required': {kind: min(limit, totals[kind]) for kind, limit in limits.items()}}


def _default(response):
    return (isinstance(response, dict) and set(response) == {'use_default'}
            and response['use_default'] is True)


def validate_response(state, request, response):
    if _default(response):
        return response
    if not isinstance(response, dict):
        raise ValueError('Choose an explicit Event quantity or piece list')
    card = request['card_id']
    if card == 31:
        live = cotuatus_request(state, request['slot'])['targets']
        if (set(response) != {'tribe'}
                or not any(row['tribe'] == response['tribe'] and row in live
                           for row in request['targets'])):
            raise ValueError('Choose an offered Roman or Aedui Ally for this removal')
        return response
    if card == 61 and request['step'] == 'allies':
        from fs_bot.cards.catuvolcus import validate_allies
        return validate_allies(state, request, response)
    if card == 'A58':
        from fs_bot.cards.aduatuci import validate_response as validate_aduatuci
        return validate_aduatuci(state, request, response)
    if card in (24, 58, 60, 'A17'):
        if set(response) != {'region', 'selections'}:
            raise ValueError('Choose one Region and its exact removals')
        if card == 24:
            live = sappers_request(state)
        elif card == 58:
            live = aduatuca_request(state)
        elif card == 60:
            live = indutiomarus_request(state)
        else:
            live = a17_removal_request(state)
        validate_region_removals(request, live, response['region'], response['selections'])
        return response
    if card in ROMAN_TOTALS or card in (7, 11, 61, 'A36', 'A69'):
        if card == 7:
            live = alaudae_request(state, next(iter(request['required'])))
        elif card == 11:
            live = numidians_removal_request(state)
        elif card == 61:
            from fs_bot.cards.catuvolcus import choice_request as catuvolcus_request
            live = catuvolcus_request(state, 'warbands')
        elif card == 'A69':
            live = a69_removal_request(state)
        elif card == 'A36':
            live = a36_removal_request(state)
        else:
            live = roman_removal_request(state, card)
        if set(response) != {'selections'} or not isinstance(response['selections'], list):
            raise ValueError('Choose exact Event piece removals')
        used = _validate_cohorts(request, live, response['selections'])
        totals = Counter()
        for (_, _, kind, _), count in used.items():
            totals[kind] += count
        if totals != Counter(request['required']) or totals != Counter(live['required']):
            raise ValueError('Select the required total of each piece type')
        return response
    if card == 19 and response.get('choice') == 'auxilia':
        if (set(response) != {'choice', 'count'} or type(response['count']) is not int
                or not 0 <= response['count'] <= 5):
            raise ValueError('Lucterius Auxilia quantity must be an integer from zero to five')
        return response
    key = 'removals' if card == 19 else 'selections'
    if (set(response) != ({'choice', key} if card == 19 else {key})
            or (card == 19 and response['choice'] != 'warbands')
            or not isinstance(response[key], list)):
        raise ValueError('Choose the Event effect and a list of physical selections')
    used = _validate_cohorts(request, choice_request(state, card), response[key],
                             with_action=card == 22)
    if sum(used.values()) > request['max_count']:
        raise ValueError('Selection exceeds the Event total')
    if card == 45:
        counts = Counter()
        for cohort, count in used.items():
            counts[cohort[0]] += count
        if len(counts) > request['max_regions'] or any(n > request['max_per_region'] for n in counts.values()):
            raise ValueError('Litaviccus replaces up to two Warbands in each of up to two Regions')
    return response


def optional_room(request, selections, region, remaining):
    """Return the remaining budget for a Region in an optional selection."""
    if 'max_regions' not in request:
        return remaining
    counts = Counter()
    for entry in selections:
        counts[entry['region']] += entry['count']
    if region not in counts and len(counts) == request['max_regions']:
        return 0
    return min(remaining, request['max_per_region'] - counts[region])


def validate_region_removals(request, live, region, selections):
    if not isinstance(region, str) or not isinstance(selections, list):
        raise ValueError('Choose one Region and its exact removals')
    required = request['required_by_region'].get(region)
    if required is None or required != live['required_by_region'].get(region):
        raise ValueError('Choose an offered Region with its live removal total')
    used = _validate_cohorts(request, live, selections)
    if any(key[0] != region for key in used) or sum(used.values()) != required:
        raise ValueError('Remove the required pieces from the single selected Region')


def _validate_cohorts(request, live, entries, *, with_action=False):
    offered = {_cohort_key(e): e['count'] for e in request['available']}
    available = {_cohort_key(e): e['count'] for e in live['available']}
    base_fields = {*FIELDS, 'count', 'action'} if with_action else {*FIELDS, 'count'}
    used = Counter()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError('Each selection needs exact physical identity and a positive count')
        named = request['card_id'] == 60 and entry.get('piece_type') == rc.ALLY
        required = base_fields | {'tribe'} if named else base_fields
        if (set(entry) != required or (named and not isinstance(entry['tribe'], str))
                or type(entry['count']) is not int or entry['count'] <= 0
                or any(not isinstance(entry[k], str) for k in FIELDS[:-1])
                or (entry['piece_state'] is not None and not isinstance(entry['piece_state'], str))
                or (with_action and entry['action'] not in ('remove', 'replace'))):
            raise ValueError('Each selection needs exact physical identity and a positive count')
        cohort = _cohort_key(entry)
        used[cohort] += entry['count']
        if used[cohort] > min(offered.get(cohort, 0), available.get(cohort, 0)):
            raise ValueError('Selection exceeds an offered live physical cohort or Region scope')
    return used


def _cohort_key(entry):
    key = tuple(entry[field] for field in FIELDS)
    return (*key, entry['tribe']) if 'tribe' in entry else key


def choose(state, card_id, params):
    """Return a validated new plan, or None for the existing delegated plan."""
    request = choice_request(state, card_id)
    if card_id == 19:
        if 'choice' in params and params['choice'] not in ('auxilia', 'warbands'):
            raise ValueError('Lucterius choice must be auxilia or warbands')
        if 'count' in params or 'removals' in params:
            response = {k: params[k] for k in ('choice', 'count', 'removals') if k in params}
        elif 'choice' in params or 'removal_regions' in params:
            return None
        else:
            response = _consult(state, request)
    elif 'piece_choices' in params:
        if 'replacements' in params:
            raise ValueError('Choose one Hostages plan format, not both')
        response = {'selections': params['piece_choices']}
    elif 'replacements' in params:
        return None
    else:
        response = _consult(state, request)
    if response is None:
        return None
    validate_response(state, request, response)
    return None if _default(response) else response


def _consult(state, request):
    from fs_bot.engine.agent import consult_agent
    owner = request['owner']
    return (consult_agent(state, owner, request)
            if owner in rc.FACTIONS and not state.get('_diviciacus_preview') else None)


def alaudae_effective(state, faction=None):
    """Check the track and the scope of the German bot's printed instruction."""
    if _count_on_legions_track(state) > ALAUDAE_TRACK_LIMIT:
        return False
    regions = state['spaces']
    if faction == rc.GERMANS and state['scenario'] in rc.ARIOVISTUS_SCENARIOS:
        from fs_bot.cards.ambacti_np import german_removal_tiers
        primary, adjacent = german_removal_tiers(state)
        regions = primary | adjacent
    return any(count_pieces(state, region, rc.ROMANS, kind)
               for region in regions for kind, _, _ in ALAUDAE_STEPS)


def resolve_alaudae(state, params):
    """Check the track once, then collect each removal on its live board."""
    from fs_bot.cards.card_effects import _event_step

    if _count_on_legions_track(state) > ALAUDAE_TRACK_LIMIT:
        return
    exact = 'piece_choices' in params
    choices = params.get('piece_choices')
    if exact:
        if any(key in params for _, _, key in ALAUDAE_STEPS):
            raise ValueError('Choose one Alaudae removal plan format')
        if (not isinstance(choices, list)
                or any(not isinstance(row, dict) or row.get('piece_type') not in (rc.LEGION, rc.AUXILIA)
                       for row in choices)):
            raise ValueError('Choose exact Alaudae Legion and Auxilia removals')

    for kind, step, legacy_key in ALAUDAE_STEPS:
        _event_step(state, step)
        request = alaudae_request(state, kind)
        region = params.get(legacy_key)
        owner = request['owner']
        if exact:
            response = {'selections': [row for row in choices if row['piece_type'] == kind]}
        elif region is None and request['available'] and owner not in state.get('non_player_factions', ()):
            response = _consult(state, request)
        else:
            response = None
        if response is None or _default(response):
            response = {'selections': _alaudae_default(state, request, region)}
        validate_response(state, request, response)
        _apply_required_removals(state, request, response['selections'])


def _alaudae_default(state, request, region):
    from fs_bot.bots.bot_common import random_select

    owner = request['owner']
    by_region = {}
    for row in request['available']:
        by_region.setdefault(row['region'], []).append(row)
    if region is None:
        if not by_region:
            return []
        candidates = list(by_region)
        if owner in state.get('non_player_factions', ()):
            if owner == rc.GERMANS and state['scenario'] in rc.ARIOVISTUS_SCENARIOS:
                from fs_bot.cards.ambacti_np import german_removal_tiers
                primary, adjacent = german_removal_tiers(state)
                candidates = ([name for name in candidates if name in primary]
                              or [name for name in candidates if name in adjacent]
                              or candidates)
            region = random_select(state, candidates)
        else:
            region = next(name for name in state['spaces'] if name in by_region)
    if not isinstance(region, str) or region not in by_region:
        raise ValueError('Choose a Region with the selected Alaudae piece')
    return [dict(by_region[region][-1 if owner == rc.ROMANS else 0], count=1)]


def resolve_sappers(state, params):
    """Remove two Roman pieces in one Arverni Citadel Region, as far as possible."""
    from fs_bot.board.pieces import remove_piece
    from fs_bot.cards.card_effects import _event_step

    _event_step(state, '24.piece_choice')
    request = sappers_request(state)
    target = params.get('target_region')
    legacy_counts = {'legions_to_remove', 'auxilia_to_remove'} & params.keys()
    if 'piece_choices' in params:
        if legacy_counts:
            raise ValueError('Choose one Sappers removal plan format')
        response = {'region': target, 'selections': params['piece_choices']}
    elif (target is None and not legacy_counts and any(request['required_by_region'].values())
          and request['owner'] not in state.get('non_player_factions', ())):
        response = _consult(state, request)
    else:
        response = None
    if response is None or _default(response):
        response = _sappers_default(state, request, target, params)
        if response is None:
            return
    validate_response(state, request, response)
    for entry in response['selections']:
        kind = entry['piece_type']
        remove_piece(state, entry['region'], rc.ROMANS, kind, count=entry['count'],
                     piece_state=entry['piece_state'], to_fallen=kind == rc.LEGION)


def _sappers_default(state, request, region, params):
    from fs_bot.bots.bot_common import random_select

    amounts = request['required_by_region']
    owner = request['owner']
    own = owner == rc.ROMANS
    kinds = (rc.AUXILIA, rc.LEGION) if own else (rc.LEGION, rc.AUXILIA)
    if region is None:
        if not any(amounts.values()):
            return None
        scores = {name: (min(total, count_pieces(state, name, rc.ROMANS, kinds[0])), total)
                  for name, total in amounts.items()}
        best = max(scores.values())
        tied = [name for name, score in scores.items() if score == best]
        region = random_select(state, tied) if owner in state.get('non_player_factions', ()) else tied[0]
    if region not in amounts:
        raise ValueError('Sappers requires a Region with an Arverni Citadel')

    preferred = {rc.LEGION: params.get('legions_to_remove', 0),
                 rc.AUXILIA: params.get('auxilia_to_remove', 0)}
    if any(type(n) is not int or n < 0 for n in preferred.values()):
        raise ValueError('Sappers removal preferences must be nonnegative integers')
    stock = {kind: count_pieces(state, region, rc.ROMANS, kind) for kind in kinds}
    remaining = amounts[region]
    wanted = Counter()
    # Honor old requested quantities first, then fill the mandatory total.
    for limits in (preferred, stock):
        for kind, limit in limits.items():
            count = min(limit, stock[kind] - wanted[kind], remaining)
            wanted[kind] += count
            remaining -= count
    selections = []
    cohorts = request['available'][::-1] if own else request['available']
    for entry in cohorts:
        if entry['region'] == region:
            kind = entry['piece_type']
            count = min(wanted[kind], entry['count'])
            if count:
                selections.append(dict(entry, count=count))
                wanted[kind] -= count
    return {'region': region, 'selections': selections}


def resolve_aduatuca_removals(state, params):
    """Remove nine Warbands, as far as possible, in the selected Fort Region."""
    from fs_bot.cards.card_effects import _event_step

    region = params.get('region')
    if 'removals' in params:
        if 'piece_choices' in params:
            raise ValueError('Choose one Aduatuca removal plan format')
        _legacy_aduatuca_removals(state, region, params['removals'])
        return

    _event_step(state, '58.piece_choice')
    request = aduatuca_request(state)
    response = _region_removal_choice(state, request, params)
    if response is None:
        response = _aduatuca_default(state, request, region)
    if response is not None:
        _remove_cohorts(state, response['selections'])


def _region_removal_choice(state, request, params):
    region = params.get('region')
    if 'piece_choices' in params:
        response = {'region': region, 'selections': params['piece_choices']}
    elif (region is None and any(request['required_by_region'].values())
          and request['owner'] not in state.get('non_player_factions', ())):
        response = _consult(state, request)
    else:
        response = None
    if response is None or _default(response):
        return None
    return validate_response(state, request, response)


def _aduatuca_default(state, request, region):
    from fs_bot.bots.bot_common import random_select

    amounts = request['required_by_region']
    owner = request['owner']
    if region is None:
        if not any(amounts.values()):
            return None
        enemies = Counter()
        for entry in request['available']:
            if entry['target_faction'] != owner:
                enemies[entry['region']] += entry['count']
        scores = {name: (min(enemies[name], total), total) for name, total in amounts.items()}
        best = max(scores.values())
        tied = [name for name, score in scores.items() if score == best]
        region = random_select(state, tied) if owner in state.get('non_player_factions', ()) else tied[0]
    if not isinstance(region, str) or region not in amounts:
        raise ValueError('Aduatuca requires a Region with a Roman Fort')
    local = [entry for entry in request['available'] if entry['region'] == region]
    # §8.4.1 orders enemy visibility first, then faction within it.
    enemy = sorted((entry for entry in local if entry['target_faction'] != owner),
                   key=lambda entry: STATES.index(entry['piece_state']))
    own = [entry for entry in reversed(local) if entry['target_faction'] == owner]
    return {'region': region, 'selections': _take_cohorts(enemy + own, amounts[region])}


def _take_cohorts(entries, remaining):
    selections = []
    for entry in entries:
        if not remaining:
            break
        count = min(remaining, entry['count'])
        selections.append(dict(entry, count=count))
        remaining -= count
    return selections


def _legacy_aduatuca_removals(state, region, removals):
    from fs_bot.cards.card_effects import _event_entries

    if not isinstance(region, str) or region not in aduatuca_request(state)['required_by_region']:
        raise ValueError('Aduatuca requires a Region with a Roman Fort')
    if not isinstance(removals, list):
        raise ValueError('Aduatuca removal preferences must be a list')
    remaining = ADUATUCA_LIMIT
    for entry in _event_entries(state, '58.removals', removals):
        if (not isinstance(entry, dict) or entry.get('faction') not in ADUATUCA_FACTIONS
                or type(entry.get('count', 1)) is not int or entry.get('count', 1) <= 0):
            raise ValueError('Aduatuca preferences require a Belgic or Germanic Warband count')
        if not count_pieces(state, region, rc.ROMANS, rc.FORT):
            raise ValueError('Aduatuca requires a live Roman Fort')
        cohorts = [row for row in aduatuca_request(state)['available']
                   if row['region'] == region and row['target_faction'] == entry['faction']]
        picked = _take_cohorts(cohorts, min(remaining, entry.get('count', 1)))
        _remove_cohorts(state, picked)
        remaining -= sum(row['count'] for row in picked)
    if remaining:
        request = aduatuca_request(state)
        if region not in request['required_by_region']:
            raise ValueError('Aduatuca requires a live Roman Fort')
        request['required_by_region'][region] = min(remaining, request['required_by_region'][region])
        response = _aduatuca_default(state, request, region)
        _remove_cohorts(state, response['selections'])


def resolve_indutiomarus_removals(state, params):
    """Remove six Belgic pieces, as far as possible, in one Region near Treveri."""
    from fs_bot.cards.card_effects import _event_step

    if 'removals' in params:
        if 'piece_choices' in params:
            raise ValueError('Choose one Indutiomarus removal plan format')
        _legacy_indutiomarus_removals(state, params.get('region', rc.TREVERI), params['removals'])
        return

    _event_step(state, '60.piece_choice')
    request = indutiomarus_request(state)
    response = _region_removal_choice(state, request, params)
    selections = (response['selections'] if response is not None else
                  _indutiomarus_default(state, request, params.get('region')))
    _remove_cohorts(state, selections)


def _indutiomarus_default(state, request, region, limit=INDUTIOMARUS_LIMIT):
    from fs_bot.bots.bot_common import is_ally_in_city_or_remi, random_select

    amounts = request['required_by_region']
    own = request['owner'] == rc.BELGAE
    if region is None:
        if not any(amounts.values()):
            return []
        allies = Counter(row['region'] for row in request['available'] if row['piece_type'] == rc.ALLY)
        scores = {name: (0 if own else min(allies[name], total), total)
                  for name, total in amounts.items()}
        best = max(scores.values())
        tied = [name for name, score in scores.items() if score == best]
        region = random_select(state, tied) if request['owner'] in state.get('non_player_factions', ()) else tied[0]
    if not isinstance(region, str) or region not in amounts:
        raise ValueError('Indutiomarus requires Treveri or one adjacent Region')

    def priority(entry):
        if entry['piece_type'] == rc.ALLY:
            return 0 if is_ally_in_city_or_remi(entry['tribe'], state['scenario']) else 1
        return 2 + STATES.index(entry['piece_state'])

    local = [row for row in request['available'] if row['region'] == region]
    return _take_cohorts(sorted(local, key=priority, reverse=own), min(limit, amounts[region]))


def _legacy_indutiomarus_removals(state, region, removals):
    from fs_bot.cards.card_effects import _event_entries

    if not isinstance(region, str) or region not in indutiomarus_request(state)['required_by_region']:
        raise ValueError('Indutiomarus requires Treveri or one adjacent Region')
    if not isinstance(removals, list):
        raise ValueError('Indutiomarus removal preferences must be a list')
    remaining = INDUTIOMARUS_LIMIT
    for entry in _event_entries(state, '60.removals', removals):
        if not remaining:
            break
        if not isinstance(entry, dict) or entry.get('type', rc.WARBAND) not in (rc.ALLY, rc.WARBAND):
            raise ValueError('Indutiomarus preferences require an Ally or Warband')
        kind = entry.get('type', rc.WARBAND)
        cohorts = [row for row in indutiomarus_request(state)['available']
                   if row['region'] == region and row['piece_type'] == kind
                   and (kind == rc.WARBAND or row['tribe'] == entry.get('tribe'))]
        picked = _take_cohorts(cohorts, 1)
        _remove_cohorts(state, picked)
        remaining -= len(picked)
    if remaining:
        _remove_cohorts(state, _indutiomarus_default(state, indutiomarus_request(state),
                                                    region, limit=remaining))


def relocate_marcus_antonius_auxilia(state, params):
    """Move existing Auxilia without changing their visibility (§1.4.3)."""
    from fs_bot.cards.card_effects import _event_step, _relocate_event_groups

    if 'auxilia_moves' in params:
        if 'piece_choices' in params:
            raise ValueError('Choose one Marcus Antonius movement plan format')
        _legacy_marcus_antonius_moves(state, params['auxilia_moves'])
        return
    _event_step(state, '6.piece_choice')
    request = choice_request(state, 6)
    owner = request['owner']
    if 'piece_choices' in params:
        response = {'selections': params['piece_choices']}
    elif not request['max_count']:
        return
    elif owner in state.get('non_player_factions', ()):
        from fs_bot.cards.ambacti_np import default_removals
        selections = [dict(row, target_faction=rc.ROMANS, piece_type=rc.AUXILIA)
                      for row in default_removals(state, owner, MARCUS_ANTONIUS_LIMIT,
                                                  exclude_regions=(rc.PROVINCIA,))]
        response = {'selections': selections}
    else:
        response = _consult(state, request)
    if response is None or _default(response):
        return  # Preserve the optional zero-move default for a player who defers.
    validate_response(state, request, response)
    moves = [(row['region'], rc.PROVINCIA, rc.AUXILIA, row['count'], row['piece_state'], row)
             for row in response['selections']]
    _relocate_event_groups(state, rc.ROMANS, '6.moves', moves)


def _legacy_marcus_antonius_moves(state, moves):
    from fs_bot.board.pieces import move_piece
    from fs_bot.cards.card_effects import _event_entries

    remaining = MARCUS_ANTONIUS_LIMIT
    for region, limit in _event_entries(state, '6.moves', moves):
        if region not in state['spaces'] or type(limit) is not int or limit < 0:
            raise ValueError('Choose an Auxilia origin and a nonnegative count')
        if region == rc.PROVINCIA:
            continue
        limit = min(limit, remaining)
        for visibility in STATES:
            count = min(limit, count_pieces_by_state(state, region, rc.ROMANS,
                                                     rc.AUXILIA, visibility))
            if count:
                move_piece(state, region, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA,
                           count=count, piece_state=visibility)
                limit -= count
                remaining -= count
            if not limit:
                break
        if not remaining:
            break


def resolve_cotuatus(state, params):
    """Remove a Roman Ally, an Aedui Ally, then a further Roman or Aedui Ally."""
    from fs_bot.board.pieces import clear_allied_tribe, remove_piece
    from fs_bot.cards.card_effects import _event_step, _unally_tribe

    third_faction = params.get('third_ally_faction')
    if third_faction is not None and third_faction not in COTUATUS_FACTIONS['third']:
        raise ValueError('The third Ally must be Roman or Aedui')
    initial_allies = {(faction, region) for faction in COTUATUS_FACTIONS['third']
                      for region in state['spaces'] if count_pieces(state, region, faction, rc.ALLY)}
    for slot, factions in COTUATUS_FACTIONS.items():
        if slot != 'roman':
            _event_step(state, f'31.{slot}_ally')
        tribe = params.get(f'{slot}_ally_tribe')
        region = params.get(f'{slot}_ally_region')
        fixed_faction = third_faction if slot == 'third' else factions[0]
        legacy = region is not None or (slot == 'third' and third_faction is not None)
        if tribe is not None and legacy:
            raise ValueError('Choose the named Ally or the legacy Region/faction for each removal')
        if not legacy and (tribe is not None or state.get('decision_agent') is not None):
            request = cotuatus_request(state, slot)
            response = {'tribe': tribe} if tribe is not None else None
            if response is None and request['targets']:
                response = _consult(state, request)
            if response is not None and not _default(response):
                validate_response(state, request, response)
                _unally_tribe(state, response['tribe'])
                continue

        # Preserve the existing delegated and Region-only selection order.
        if not fixed_faction or region is None:
            candidates = (fixed_faction,) if fixed_faction else factions
            fixed_faction, region = next(
                ((faction, name) for faction in candidates for name in state['spaces']
                 if count_pieces(state, name, faction, rc.ALLY)), (None, None))
        if not region:
            continue
        if ((fixed_faction, region) in initial_allies
                and not count_pieces(state, region, fixed_faction, rc.ALLY)):
            continue  # Legacy targets removed during an earlier timing window.
        remove_piece(state, region, fixed_faction, rc.ALLY)
        clear_allied_tribe(state, region, fixed_faction, rc.ALLY)


def resolve_numidians_removals(state, params):
    """Both editions require four Roman Auxilia removals, as far as possible."""
    from fs_bot.cards.card_effects import _event_entries, _event_step

    legacy_keys = {'auxilia_removal_regions', 'removals'} & params.keys()
    if len(legacy_keys) > 1 or (legacy_keys and 'piece_choices' in params):
        raise ValueError('Choose one Numidians removal plan format')
    if not legacy_keys:
        _event_step(state, '11.piece_choice')
        request = numidians_removal_request(state)
        owner = request['owner']
        response = {'selections': params['piece_choices']} if 'piece_choices' in params else None
        if response is None and request['required'][rc.AUXILIA]:
            if owner in state.get('non_player_factions', ()):
                from fs_bot.cards.ambacti_np import default_removals
                # Both cards have the same printed Non-player removal instructions.
                selections = [dict(entry, target_faction=rc.ROMANS, piece_type=rc.AUXILIA)
                              for entry in default_removals(state, owner, NUMIDIANS_LIMIT)]
                _apply_required_removals(state, request, selections)
                return
            response = _consult(state, request)
        if response is not None and not _default(response):
            validate_response(state, request, response)
            _apply_required_removals(state, request, response['selections'])
            return

    remaining = NUMIDIANS_LIMIT
    # §8.4.1 reverses visibility priorities when removing one's own pieces.
    order = STATES[::-1] if state.get('executing_faction') == rc.ROMANS else STATES
    if legacy_keys:
        key = legacy_keys.pop()
        revised = key == 'removals'
        step = '11a.removals' if revised else '11.auxilia_removals'
        for entry in _event_entries(state, step, params[key]):
            if revised:
                if not isinstance(entry, dict) or entry.get('faction', rc.ROMANS) != rc.ROMANS:
                    raise ValueError('Numidians removes only Roman Auxilia')
                region, count = entry.get('region'), 1
            else:
                region, count = entry
            if region not in state['spaces'] or type(count) is not int or count < 0:
                raise ValueError('Choose a map Region and a nonnegative Auxilia count')
            remaining -= _remove_numidians_group(state, region, min(count, remaining), order)
            if not remaining:
                return

    for region in _event_entries(state, '11.remaining_auxilia', list(state['spaces'])):
        if not remaining:
            break
        remaining -= _remove_numidians_group(state, region, remaining, order)


def _remove_numidians_group(state, region, limit, order):
    from fs_bot.board.pieces import remove_piece

    removed = 0
    for visibility in order:
        count = min(limit - removed, count_pieces_by_state(state, region, rc.ROMANS,
                                                           rc.AUXILIA, visibility))
        if count:
            remove_piece(state, region, rc.ROMANS, rc.AUXILIA, count=count, piece_state=visibility)
            removed += count
        if removed == limit:
            break
    return removed


def a17_np_regions(state, faction):
    """Best shaded A17 Regions under the actor's instructions and §§8.3.1, 8.3.4."""
    playable = get_playable_regions_for_state(state, rc.ROMANS)
    candidates = {region: min(A17_LIMIT, count_pieces(state, region, rc.ROMANS, rc.AUXILIA))
                  for region in playable}
    candidates = {region: n for region, n in candidates.items() if n}
    if faction == rc.GERMANS:
        core = set(rc.GERMANIA_REGIONS) | {
            region for region in playable if count_pieces(state, region, rc.GERMANS, rc.SETTLEMENT)
        }
        adjacent = {neighbor for region in core for neighbor in get_adjacent_for_state(state, region)}
        tiers = (core, adjacent)
    elif faction == rc.BELGAE:
        tiers = (set(rc.BELGICA_REGIONS), playable)
    else:
        tiers = (playable,)
    for tier in tiers:
        eligible = {region: n for region, n in candidates.items() if region in tier}
        if eligible:
            best = max(eligible.values())
            return [region for region, n in eligible.items() if n == best]
    return []


def resolve_a17_removals(state, params, region):
    """Apply a live one-Region choice or the historical Region-only plan."""
    from fs_bot.board.pieces import remove_piece
    from fs_bot.bots.bot_common import random_select
    from fs_bot.cards.card_effects import _event_entries

    request = a17_removal_request(state)
    required = request['required_by_region']
    if 'piece_choices' in params:
        response = {'region': region, 'selections': params['piece_choices']}
    else:
        response = (_consult(state, request)
                    if region is None and any(required.values()) else None)
    if response is not None and not _default(response):
        validate_response(state, request, response)
        for entry in response['selections']:
            remove_piece(state, response['region'], rc.ROMANS, rc.AUXILIA,
                         count=entry['count'], piece_state=entry['piece_state'])
        return

    owner = request['owner']
    if region is None:
        regions = a17_np_regions(state, owner)
        if not regions and owner not in state.get('non_player_factions', ()):
            regions = [candidate for candidate, n in required.items() if n]
        if not regions:
            return
        region = random_select(state, regions)
    if not isinstance(region, str) or region not in required:
        raise ValueError('Choose a playable Region for shaded A17')
    states = reversed(STATES) if owner == rc.ROMANS else STATES
    visibility_order = tuple(states)
    for _ in _event_entries(state, 'A17.removals', range(A17_LIMIT)):
        for visibility in visibility_order:
            if count_pieces_by_state(state, region, rc.ROMANS, rc.AUXILIA, visibility):
                remove_piece(state, region, rc.ROMANS, rc.AUXILIA, piece_state=visibility)
                break


def resolve_a36_removals(state, params):
    """Collect the executor's exact German removals, or run the delegated plan."""
    request = a36_removal_request(state)
    if 'piece_choices' in params:
        response = {'selections': params['piece_choices']}
    else:
        response = _consult(state, request) if any(request['required'].values()) else None
    if response is None or _default(response):
        _delegate_a36_removals(state, request['owner'])
        return
    validate_response(state, request, response)
    _apply_required_removals(state, request, response['selections'])


def resolve_a69_removals(state, params):
    """Remove four Belgic Warbands at Bellovaci, or all present if fewer."""
    request = a69_removal_request(state)
    remaining = request['required'][rc.WARBAND]
    if 'piece_choices' in params:
        response = {'selections': params['piece_choices']}
    else:
        response = _consult(state, request) if remaining else None
    if response is not None and not _default(response):
        validate_response(state, request, response)
        _apply_required_removals(state, request, response['selections'])
        return

    # §8.4.1 uses reverse visibility priority when removing one's own pieces.
    available = request['available']
    if request['owner'] == rc.BELGAE:
        available.reverse()
    selections = []
    for entry in available:
        if not remaining:
            break
        count = min(remaining, entry['count'])
        selections.append(dict(entry, count=count))
        remaining -= count
    _apply_required_removals(state, request, selections)


def _delegate_a36_removals(state, owner):
    from fs_bot.board.pieces import remove_piece
    from fs_bot.bots.bot_common import random_select
    from fs_bot.cards.card_effects import _event_step

    for kind, step in ((rc.SETTLEMENT, 'A36.settlements'), (rc.WARBAND, 'A36.warbands')):
        remaining = A36_TOTALS[kind]
        for index in range(len(A36_REGIONS)):
            _event_step(state, step, index=index)
            if not remaining:
                break
            by_region = {}
            for entry in a36_removal_request(state)['available']:
                if entry['piece_type'] == kind:
                    by_region.setdefault(entry['region'], []).append(entry)
            if not by_region:
                break
            # No die roll is needed when every remaining counter must go.
            total = sum(entry['count'] for entries in by_region.values() for entry in entries)
            region = (random_select(state, list(by_region)) if total > remaining
                      else next(iter(by_region)))
            entries = by_region[region]
            # §8.4.1: use reverse visibility priority for own pieces.
            if owner == rc.GERMANS:
                entries.reverse()
            for entry in entries:
                count = min(remaining, entry['count'])
                remove_piece(state, region, rc.GERMANS, kind, count=count,
                             piece_state=entry['piece_state'])
                remaining -= count
                if not remaining:
                    break


def remove_roman_pieces(state, card_id, params):
    """Resolve an exact Roman plan, or leave the legacy fallback to the card."""
    legacy_keys = A5_LEGACY_KEYS if card_id == 'A5' else LEGACY_ROMAN_KEYS
    legacy = legacy_keys & params.keys()
    exact = 'piece_choices' in params
    if (exact or legacy) and state.get('executing_faction') not in (None, rc.ROMANS):
        raise ValueError('Only the Romans can choose their Event removals')
    if exact and legacy:
        raise ValueError('Choose one Roman removal plan format, not both')
    request = roman_removal_request(state, card_id)
    if exact:
        response = {'selections': params['piece_choices']}
    elif any(request['required'].values()):
        response = _consult(state, request)
    else:
        return False
    if response is None or _default(response):
        return False
    validate_response(state, request, response)
    _apply_required_removals(state, request, response['selections'])
    return True


def _apply_required_removals(state, request, entries):
    for kind in request['required']:
        _remove_cohorts(state, (entry for entry in entries if entry['piece_type'] == kind))


def _remove_cohorts(state, entries):
    from fs_bot.board.pieces import remove_piece
    from fs_bot.cards.card_effects import _unally_tribe

    for entry in entries:
        kind = entry['piece_type']
        if 'tribe' in entry:
            _unally_tribe(state, entry['tribe'])
            continue
        remove_piece(state, entry['region'], entry['target_faction'], kind,
                     count=entry['count'], piece_state=entry['piece_state'],
                     to_track=kind == rc.LEGION)


def resolve_a5_removals(state, params):
    """Resolve the Roman garrison, filling any missing legacy selections."""
    from fs_bot.cards.card_effects import _event_entries
    from fs_bot.board.pieces import remove_piece

    if remove_roman_pieces(state, 'A5', params):
        return

    legion_region = params.get('legion_region')
    entries = params.get('auxilia_removals', [])
    if (not isinstance(legion_region, (str, type(None)))
            or not isinstance(entries, (list, tuple))
            or any(not isinstance(entry, dict) or not isinstance(entry.get('region'), str)
                   for entry in entries)):
        raise ValueError('Legacy A5 removals must name Roman Regions')
    regions = get_playable_regions_for_state(state, rc.ROMANS)
    if legion_region in regions and count_pieces(state, legion_region, rc.ROMANS, rc.LEGION):
        remove_piece(state, legion_region, rc.ROMANS, rc.LEGION, to_track=True)
    else:
        _complete_a5_removals(state, rc.LEGION, GARRISON_TOTALS[rc.LEGION])

    remaining = GARRISON_TOTALS[rc.AUXILIA]
    for entry in _event_entries(state, 'A5.auxilia_removals', entries[:remaining]):
        region = entry['region']
        if region not in regions:
            continue
        # Keep the original visibility preference of a Region-only plan.
        for visibility in STATES:
            if count_pieces_by_state(state, region, rc.ROMANS, rc.AUXILIA, visibility):
                remove_piece(state, region, rc.ROMANS, rc.AUXILIA, piece_state=visibility)
                remaining -= 1
                break
    _complete_a5_removals(state, rc.AUXILIA, remaining)


def _complete_a5_removals(state, piece_type, remaining):
    """Use §8.3.1 Region order and §8.4.1 Roman own-piece priority."""
    from fs_bot.board.pieces import remove_piece
    from fs_bot.bots.bot_common import random_select

    if not remaining:
        return
    by_region = {}
    for entry in roman_removal_request(state, 'A5')['available']:
        if entry['piece_type'] == piece_type:
            by_region.setdefault(entry['region'], []).append(entry)
    while remaining and by_region:
        region = random_select(state, list(by_region))
        # Within the Region, remove Scouted, then Revealed, then Hidden Auxilia.
        for entry in reversed(by_region.pop(region)):
            count = min(remaining, entry['count'])
            remove_piece(state, region, rc.ROMANS, piece_type, count=count,
                         piece_state=entry['piece_state'], to_track=piece_type == rc.LEGION)
            remaining -= count
            if not remaining:
                break


def apply(state, card_id, response):
    """Apply an already validated aggregate selection as one Event operation."""
    from fs_bot.board.pieces import place_piece, remove_piece
    if card_id == 19 and response['choice'] == 'auxilia':
        count = min(response['count'], get_available(state, rc.ROMANS, rc.AUXILIA))
        if count:
            place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, count=count)
        return
    owner = state.get('executing_faction')
    for entry in response['removals' if card_id == 19 else 'selections']:
        region, faction, kind, visibility = (entry[k] for k in FIELDS)
        remove_piece(state, region, faction, kind, count=entry['count'], piece_state=visibility)
        if card_id == 22 and entry['action'] == 'replace':
            replacement = rc.AUXILIA if owner == rc.ROMANS else rc.WARBAND
            count = min(entry['count'], get_available(state, owner, replacement))
            if count:
                place_piece(state, region, owner, replacement, count=count)
