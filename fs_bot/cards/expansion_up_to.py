"""Executor-owned optional quantities on A40 shaded and A51/A60 unshaded.

A Card Reference and §5.1: the executor selects Regions and physical pieces.
Zero is a real choice. Omitted choices use a live request; raw delegation
retains the maximum default. A60 compensation counts actual placements.
"""
from fs_bot import rules_consts as rc
from fs_bot.board.control import is_controlled_by
from fs_bot.board.pieces import count_pieces_by_state, get_available
from fs_bot.map.map_data import get_adjacent_for_state, get_playable_regions_for_state

KIND = 'event_up_to'
STATES = (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)


def supported(card_id, shaded):
    return (card_id, shaded) in {('A40', True), ('A51', False), ('A60', False)}


def validate_params(card_id, params):
    if not isinstance(params, dict):
        raise ValueError('Optional Event choices must be an object')
    allowed = {'A40': {'regions'}, 'A51': {'piece_type', 'warband_removals'},
               'A60': {'auxilia_count'}}[card_id]
    if set(params) - allowed - {'stage_timing_actions'}:
        raise ValueError('Unexpected or wrong-side optional Event choices')
    if card_id == 'A51' and params.get('piece_type', rc.AUXILIA) not in (rc.AUXILIA, rc.WARBAND):
        raise ValueError('Siege of Bibrax places Auxilia or Aedui Warbands')


def choice_request(state, card_id):
    request = {'kind': KIND, 'card_id': card_id, 'faction': state.get('executing_faction'),
               'shaded': card_id == 'A40'}
    if card_id == 'A40':
        nearby = {rc.CISALPINA, *get_adjacent_for_state(state, rc.CISALPINA)}
        regions = sorted(r for r in nearby & set(get_playable_regions_for_state(state))
                         if not is_controlled_by(state, r, rc.ROMANS))
        request.update(legal_regions=regions, max_count=min(3, len(regions)))
    elif card_id == 'A51':
        region = rc.TRIBE_TO_REGION[rc.TRIBE_REMI]
        available = [{'piece_state': ps, 'count': count}
                     for ps in STATES
                     if (count := count_pieces_by_state(state, region, rc.BELGAE, rc.WARBAND, ps))]
        request.update(region=region, available=available,
                       max_count=min(6, sum(e['count'] for e in available)))
    elif card_id == 'A60':
        request.update(region=rc.TRIBE_TO_REGION[rc.TRIBE_REMI], max_count=4,
                       available_count=get_available(state, rc.ROMANS, rc.AUXILIA))
    else:
        raise ValueError('Unsupported optional Event')
    return request


def validate_response(state, request, response):
    if isinstance(response, dict) and response == {'use_default': True}:
        if type(response['use_default']) is not bool:
            raise ValueError('Explicit default must be boolean true')
        return response
    card = request['card_id']
    key = {'A40': 'regions', 'A51': 'removals', 'A60': 'count'}[card]
    if not isinstance(response, dict) or set(response) != {key}:
        raise ValueError(f'{card} requires an explicit {key} choice (zero is allowed)')
    live = choice_request(state, card)
    if card == 'A40':
        regions = response[key]
        if (not isinstance(regions, list) or any(not isinstance(r, str) for r in regions)
                or len(regions) > request['max_count'] or len(set(regions)) != len(regions)
                or any(r not in request['legal_regions'] or r not in live['legal_regions'] for r in regions)):
            raise ValueError('Select up to three distinct eligible Regions within one of Cisalpina')
    elif card == 'A51':
        entries = response[key]
        if not isinstance(entries, list):
            raise ValueError('Select exact Belgic Warband visibility cohorts')
        offered = {e['piece_state']: e['count'] for e in request['available']}
        available = {e['piece_state']: e['count'] for e in live['available']}
        used = {}
        for entry in entries:
            if (not isinstance(entry, dict) or set(entry) != {'piece_state', 'count'}
                    or entry['piece_state'] not in STATES
                    or type(entry['count']) is not int or entry['count'] <= 0):
                raise ValueError('Each removal needs a visibility and positive integer count')
            ps, count = entry['piece_state'], entry['count']
            used[ps] = used.get(ps, 0) + count
            if used[ps] > min(offered.get(ps, 0), available.get(ps, 0)):
                raise ValueError('Removal exceeds an offered physical visibility cohort')
        if sum(used.values()) > min(6, request['max_count']):
            raise ValueError('Remove at most six Belgic Warbands')
    elif type(response[key]) is not int or not 0 <= response[key] <= 4:
        raise ValueError('Choose an integer Auxilia quantity from zero to four')
    return response


def default_response(request):
    if request['card_id'] == 'A40':
        return {'regions': request['legal_regions'][:request['max_count']]}
    if request['card_id'] == 'A60':
        return {'count': 4}
    remaining, removals = request['max_count'], []
    # Retain the existing Hidden/Revealed order, including Scouted Warbands
    # as the final eligible cohort instead of leaving them unremovable.
    for entry in request['available']:
        count = min(remaining, entry['count'])
        if count:
            removals.append(dict(entry, count=count))
            remaining -= count
    return {'removals': removals}


def choose(state, card_id, params):
    from fs_bot.engine.agent import consult_agent
    request = choice_request(state, card_id)
    param, key = {'A40': ('regions', 'regions'), 'A51': ('warband_removals', 'removals'),
                  'A60': ('auxilia_count', 'count')}[card_id]
    if param in params:
        response = {key: params[param]}
    elif request['faction'] in rc.FACTIONS and not state.get('_diviciacus_preview'):
        response = consult_agent(state, request['faction'], request)
    else:
        response = None
    if response is None:
        return default_response(request)
    validate_response(state, request, response)
    return default_response(request) if response.get('use_default') is True else response
