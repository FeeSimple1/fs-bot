"""Exact optional quantities and remove/replace choices for numeric 19/22.

Card Reference 19/22, Chapter 5 §§5.1–5.1.3. New live responses are strict;
legacy explicitly authored region/replacement lists retain their contract.
"""
from collections import Counter

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces_by_state, get_available
from fs_bot.board.control import is_controlled_by
from fs_bot.map.map_data import get_adjacent_for_state, get_playable_regions_for_state

KIND = 'event_piece_choice'
STATES = (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)
FIELDS = ('region', 'target_faction', 'piece_type', 'piece_state')


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


def _default(response):
    return (isinstance(response, dict) and set(response) == {'use_default'}
            and response['use_default'] is True)


def validate_response(state, request, response):
    if _default(response):
        return response
    if not isinstance(response, dict):
        raise ValueError('Choose an explicit optional Event quantity or piece list')
    card = request['card_id']
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
    live = choice_request(state, card)
    offered = {tuple(e[k] for k in FIELDS): e['count'] for e in request['available']}
    available = {tuple(e[k] for k in FIELDS): e['count'] for e in live['available']}
    used = Counter()
    for entry in response[key]:
        required = {*FIELDS, 'count', *(['action'] if card == 22 else [])}
        if (not isinstance(entry, dict) or set(entry) != required
                or type(entry['count']) is not int or entry['count'] <= 0
                or any(not isinstance(entry[k], str) for k in FIELDS)
                or (card == 22 and entry['action'] not in ('remove', 'replace'))):
            raise ValueError('Each selection needs exact physical identity and a positive count')
        cohort = tuple(entry[k] for k in FIELDS)
        used[cohort] += entry['count']
        if used[cohort] > min(offered.get(cohort, 0), available.get(cohort, 0)):
            raise ValueError('Selection exceeds an offered live physical cohort or Region scope')
    if sum(used.values()) > request['max_count']:
        raise ValueError('Selection exceeds the Event total')
    return response


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
