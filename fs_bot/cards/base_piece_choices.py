"""Exact physical piece selections for 3/5/A5/A17/A36/A69 and numeric 19/22.

Card Reference 3/5/19/22, A Card Reference A5/A17/A36/A69 and Chapter 5 §§5.1–5.1.3.
Live responses are strict. Authored legacy region and replacement lists
retain their selection priorities.
"""
from collections import Counter

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_available
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
LEGACY_ROMAN_KEYS = {'legion_removal_regions', 'legion_removal_region', 'auxilia_removal_regions'}
A5_LEGACY_KEYS = {'legion_region', 'auxilia_removals'}


def choice_request(state, card_id):
    owner = state.get('executing_faction')
    regions = get_playable_regions_for_state(state)
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


def a69_removal_request(state):
    region = rc.TRIBE_TO_REGION[rc.TRIBE_BELLOVACI]
    return _required_removal_request(state, 'A69', state.get('executing_faction'),
                                     rc.BELGAE, (region,), {rc.WARBAND: 4})


def a17_removal_request(state):
    return auxilia_region_request(state, 'A17', get_playable_regions_for_state(state, rc.ROMANS),
                                  A17_LIMIT)


def auxilia_region_request(state, card_id, regions, limit):
    request = _required_removal_request(state, card_id, state.get('executing_faction'),
                                        rc.ROMANS, regions, {rc.AUXILIA: limit})
    request.pop('required')
    totals = Counter()
    for entry in request['available']:
        totals[entry['region']] += entry['count']
    request['required_by_region'] = {region: min(limit, totals[region]) for region in regions}
    return request


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
    if card == 'A58':
        from fs_bot.cards.aduatuci import validate_response as validate_aduatuci
        return validate_aduatuci(state, request, response)
    if card == 'A17':
        if set(response) != {'region', 'selections'}:
            raise ValueError('Choose one Region and its exact Auxilia removals')
        validate_region_auxilia(request, a17_removal_request(state),
                                response['region'], response['selections'])
        return response
    if card in ROMAN_TOTALS or card in ('A36', 'A69'):
        if card == 'A69':
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
        raise ValueError('Choose Lucterius warband removals or Hostages selections')
    used = _validate_cohorts(request, choice_request(state, card), response[key],
                             with_action=card == 22)
    if sum(used.values()) > request['max_count']:
        raise ValueError('Selection exceeds the Event total')
    return response


def validate_region_auxilia(request, live, region, selections):
    if not isinstance(region, str) or not isinstance(selections, list):
        raise ValueError('Choose one Region and its exact Auxilia removals')
    required = request['required_by_region'].get(region)
    if required is None or required != live['required_by_region'].get(region):
        raise ValueError('Choose an offered Region with its live Auxilia total')
    used = _validate_cohorts(request, live, selections)
    if any(key[0] != region for key in used) or sum(used.values()) != required:
        raise ValueError('Remove the required Auxilia from the single selected Region')


def _validate_cohorts(request, live, entries, *, with_action=False):
    offered = {tuple(e[k] for k in FIELDS): e['count'] for e in request['available']}
    available = {tuple(e[k] for k in FIELDS): e['count'] for e in live['available']}
    required = {*FIELDS, 'count'}
    if with_action:
        required.add('action')
    used = Counter()
    for entry in entries:
        if (not isinstance(entry, dict) or set(entry) != required
                or type(entry['count']) is not int or entry['count'] <= 0
                or any(not isinstance(entry[k], str) for k in FIELDS[:-1])
                or (entry['piece_state'] is not None and not isinstance(entry['piece_state'], str))
                or (with_action and entry['action'] not in ('remove', 'replace'))):
            raise ValueError('Each selection needs exact physical identity and a positive count')
        cohort = tuple(entry[k] for k in FIELDS)
        used[cohort] += entry['count']
        if used[cohort] > min(offered.get(cohort, 0), available.get(cohort, 0)):
            raise ValueError('Selection exceeds an offered live physical cohort or Region scope')
    return used


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
    from fs_bot.board.pieces import remove_piece
    for kind in request['required']:
        for entry in entries:
            if entry['piece_type'] == kind:
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
