"""A66's held-card timing, physical placements, and mandatory Interlude use.

The holder chooses a Quarters window (§5.1); Belgae/Germans choose their
expressly granted placements. For Arverni placement, the holder chooses and
the subsequent Arverni Phase remains automatic (A6.2).
"""
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import get_available, place_piece
from fs_bot.cards.card_text import get_card_text
from fs_bot.engine.agent import consult_agent
from fs_bot.map.map_data import get_adjacent_for_state, get_playable_regions_for_state

TIMING = 'winter_uprising_timing'
PLACEMENT = 'winter_uprising_placement'
HOLDER_KEY = 'card_A66_holder'


def marker_region(state):
    saved = state.get('event_modifiers', {}).get('card_A66_uprising_region')
    if isinstance(saved, str) and saved in state['spaces']:
        return saved
    # Earlier saves used either a canonical marker or the former label.
    return next((region for region, markers in state.get('markers', {}).items()
                 if isinstance(markers, (dict, set))
                 and (rc.MARKER_WINTER_UPRISING in markers or 'Uprising' in markers)), None)


def active(state):
    return (bool(state.get('event_modifiers', {}).get('card_A66_winter_uprising'))
            or marker_region(state) is not None or 'A66' in state.get('capabilities', {}))


def holder(state):
    owner = state.get('event_modifiers', {}).get(HOLDER_KEY)
    if owner is None:
        # Recover an actually recorded legacy owner; a marker's geography
        # identifies its beneficiary, never the person who took the card.
        owner = state.get('capability_owners', {}).get('A66')
    return owner if owner in rc.FACTIONS else None


def _explicit_default(response):
    return (isinstance(response, dict) and set(response) == {'use_default'}
            and response['use_default'] is True)


def _context(state, region, owner, forced):
    return {'card_id': 'A66', 'card_text': get_card_text('A66', state['scenario']),
            'region': region, 'holder': owner, 'forced': forced}


def placement_request(state, region, owner, forced=False):
    from fs_bot.cards.card_effects import _tribe_region
    group = rc.REGION_TO_GROUP.get(region)
    beneficiary, ally_limit, warband_limit = (
        (rc.BELGAE, 2, 4) if group == rc.BELGICA else
        (rc.GERMANS, 2, 4) if group == rc.GERMANIA else (rc.ARVERNI, 4, 8))
    playable = set(get_playable_regions_for_state(state, beneficiary))
    regions = sorted(({region} | set(get_adjacent_for_state(state, region))) & playable)
    tribes = sorted(tribe for tribe, info in state.get('tribes', {}).items()
                    if _tribe_region(state, tribe) in regions
                    and info.get('allied_faction') is None
                    and info.get('status') in (None, rc.ALLIED)
                    and rc.TRIBE_FACTION_RESTRICTION.get(tribe, beneficiary) == beneficiary)
    return dict(_context(state, region, owner, forced), kind=PLACEMENT,
                beneficiary=beneficiary, regions=regions, tribes=tribes,
                allies=min(ally_limit, get_available(state, beneficiary, rc.ALLY), len(tribes)),
                warbands=min(warband_limit, get_available(state, beneficiary, rc.WARBAND))
                if regions else 0)


def validate_response(state, request, response):
    """Validate without placing pieces, drawing dice, or consuming human input."""
    if _explicit_default(response):
        return response
    if request['kind'] == TIMING:
        if (not isinstance(response, dict) or set(response) != {'activate'}
                or type(response['activate']) is not bool):
            raise ValueError('Winter Uprising timing requires activate: true or false.')
        if request.get('forced') and not response['activate']:
            raise ValueError('The Gallic War Interlude requires Winter Uprising now.')
        return response
    if request['kind'] != PLACEMENT:
        raise ValueError('Unknown Winter Uprising decision.')
    if not isinstance(response, dict) or set(response) != {'allies', 'warbands'}:
        raise ValueError('Choose Winter Uprising Allied Tribes and Warband allocations.')
    current = placement_request(state, request['region'], request.get('holder'),
                                request.get('forced', False))
    allies, warbands = response['allies'], response['warbands']
    if (not isinstance(allies, list) or any(not isinstance(tribe, str) for tribe in allies)
            or len(allies) != len(set(allies))
            or len(allies) != current['allies'] or len(allies) != request['allies']
            or any(tribe not in current['tribes'] or tribe not in request['tribes'] for tribe in allies)):
        raise ValueError('Place the required Available Allies at distinct offered Subdued Tribes.')
    if not isinstance(warbands, list):
        raise ValueError('Winter Uprising Warbands require Region/count entries.')
    total = 0
    for entry in warbands:
        if (not isinstance(entry, dict) or set(entry) != {'region', 'count'}
                or entry['region'] not in current['regions'] or entry['region'] not in request['regions']
                or type(entry['count']) is not int or entry['count'] <= 0):
            raise ValueError('Place positive Warband counts within one Region of the Uprising marker.')
        total += entry['count']
    if total != current['warbands'] or total != request['warbands']:
        raise ValueError('Place the entire required Available Warband total.')
    return response


def _consume(state, region):
    mods = state.get('event_modifiers', {})
    for key in ('card_A66_winter_uprising', 'card_A66_uprising_region', HOLDER_KEY):
        mods.pop(key, None)
    state.get('capabilities', {}).pop('A66', None)
    state.get('capability_owners', {}).pop('A66', None)
    markers = state.get('markers', {}).get(region)
    if isinstance(markers, dict):
        markers.pop(rc.MARKER_WINTER_UPRISING, None)
        markers.pop('Uprising', None)
    elif isinstance(markers, set):
        markers.discard(rc.MARKER_WINTER_UPRISING)
        markers.discard('Uprising')


def _resolve(state, forced):
    region, owner = marker_region(state), holder(state)
    if region is None:
        _consume(state, region)
        return [{'free_action': 'winter_uprising', 'executed': False,
                 'reason': 'no Uprising marker region'}]
    if not forced and owner is not None and owner not in state.get('non_player_factions', set()):
        request = dict(_context(state, region, owner, False), kind=TIMING)
        response = consult_agent(state, owner, request)
        if response is not None and not _explicit_default(response):
            validate_response(state, request, response)
            if not response['activate']:
                return [{'free_action': 'winter_uprising', 'executed': False,
                         'deferred': True, 'region': region, 'holder': owner}]
    # Printed NP instructions remove when able. A legacy save with no holder
    # retains its former automatic timing; do not invent a human owner for it.
    request = placement_request(state, region, owner, forced)
    beneficiary = request['beneficiary']
    chooser = beneficiary if beneficiary in (rc.BELGAE, rc.GERMANS) else owner
    response = (consult_agent(state, chooser, request)
                if chooser is not None and chooser not in state.get('non_player_factions', set()) else None)
    if response is None or _explicit_default(response):
        from fs_bot.cards.winter_uprising_np import np_placements
        response = np_placements(state, beneficiary, request['regions'], request['tribes'],
                                 request['allies'], request['warbands'])
    validate_response(state, request, response)
    _consume(state, region)
    from fs_bot.cards.card_effects import _ally_tribe
    for tribe in response['allies']:
        if not _ally_tribe(state, tribe, beneficiary):
            raise ValueError('An offered Winter Uprising Ally could not be placed.')
    for entry in response['warbands']:
        place_piece(state, entry['region'], beneficiary, rc.WARBAND, count=entry['count'])
    results = [{'free_action': 'winter_uprising', 'executed': True,
                'holder': owner, 'legacy_holder_unknown': owner is None,
                'faction': beneficiary, 'region': region, 'forced': forced,
                'allies': len(response['allies']), 'warbands': request['warbands'],
                'placements': response}]
    from fs_bot.engine.execute import _resolve_event_arverni_phase, _resolve_free_command
    if beneficiary == rc.ARVERNI:
        results.extend(_resolve_event_arverni_phase(state))
    else:
        results.append(_resolve_free_command(state, beneficiary, allowed_regions=set(request['regions']),
                                             with_sa=True, allow_decline=False))
    return results


def resolve(state, forced=False):
    """Keep delayed decisions and their granted action atomic, including RNG."""
    snapshot = deepcopy({key: value for key, value in state.items() if key != 'decision_agent'})
    agent, had_agent = state.get('decision_agent'), 'decision_agent' in state
    try:
        return _resolve(state, forced)
    except BaseException:
        state.clear()
        state.update(snapshot)
        if had_agent:
            state['decision_agent'] = agent
        raise
