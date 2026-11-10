"""Citadel, Settlement, expedition and marker choices in the Gallic War Interlude (A2.1)."""
from fs_bot import rules_consts as rc
from fs_bot.board.control import is_controlled_by
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, find_leader, get_available
from fs_bot.engine.agent import consult_agent

EXPEDITION = 'interlude_expedition'
MARKER = 'interlude_marker'
SETTLEMENTS = 'interlude_settlements'
AEDUI_CITADEL = 'interlude_aedui_citadel'
ARVERNI_CITADELS = 'interlude_arverni_citadels'


def settlement_request(state):
    """Find legal Ally replacements after the permanent German removals."""
    from fs_bot.commands.rally import _find_subdued_tribe_for_ally

    available = get_available(state, rc.GERMANS, rc.ALLY)
    options = {}
    if available:
        for region in state['spaces']:
            if (count_pieces(state, region, rc.GERMANS, rc.SETTLEMENT)
                    and is_controlled_by(state, region, rc.GERMANS)):
                tribes = [tribe for tribe in _find_subdued_tribe_for_ally(state, region, rc.GERMANS)
                          if tribe in state['tribes']
                          and state['tribes'][tribe].get('status') in (None, rc.ALLIED)]
                if tribes:
                    options[region] = tribes
    return dict(kind=SETTLEMENTS, options=options, required_allies=min(available, len(options)))


def choose_settlement_allies(state):
    request = settlement_request(state)
    options = request['options']
    required = request['required_allies']
    has_choice = required < len(options) or any(len(tribes) > 1 for tribes in options.values())
    if has_choice and rc.GERMANS not in state.get('non_player_factions', ()):
        response = consult_agent(state, rc.GERMANS, request)
        if response is not None:
            validate_response(state, request, response)
            if 'allies' in response:
                return response['allies']
    return {region: tribes[0] for region, tribes in list(options.items())[:required]}


def aedui_citadel_request(state):
    regions = [region for region in state['spaces']
               if count_pieces(state, region, rc.AEDUI, rc.CITADEL)]
    outside = [region for region in regions if region != rc.AEDUI_REGION]
    return dict(kind=AEDUI_CITADEL, regions=outside or regions,
                ally_available=get_available(state, rc.AEDUI, rc.ALLY) > 0)


def choose_aedui_citadel(state):
    request = aedui_citadel_request(state)
    regions = request['regions']
    if len(regions) > 1 and rc.AEDUI not in state.get('non_player_factions', ()):
        response = consult_agent(state, rc.AEDUI, request)
        if response is not None:
            validate_response(state, request, response)
            if 'region' in response:
                return response['region']
    # Bibracte can contain only one Citadel. Shuffling only the legal tier
    # preserves the old RNG draws from shuffling each tier separately.
    regions = list(regions)
    state['rng'].shuffle(regions)
    return regions[0] if regions else None


def arverni_citadel_request(state):
    regions = [region for region in state['spaces']
               if count_pieces(state, region, rc.ARVERNI, rc.CITADEL)]
    outside = [region for region in regions if region != rc.ARVERNI_REGION]
    required = min(2, len(regions))
    return dict(kind=ARVERNI_CITADELS, regions=outside if len(outside) >= required else regions,
                count=required, available_allies=get_available(state, rc.ARVERNI, rc.ALLY))


def choose_arverni_citadels(state):
    request = arverni_citadel_request(state)
    regions = request['regions']
    required = request['count']
    outside = [region for region in regions if region != rc.ARVERNI_REGION]
    # When the targets are forced, their order matters only if they compete
    # for a scarce Ally disc and Gergovia does not already go last.
    has_choice = (len(regions) > required
                  or (0 < request['available_allies'] < required and len(outside) > 1))
    if has_choice and rc.GERMANS not in state.get('non_player_factions', ()):
        response = consult_agent(state, rc.GERMANS, request)
        if response is not None:
            validate_response(state, request, response)
            if 'regions' in response:
                return response['regions']
    state['rng'].shuffle(outside)
    return (outside + [r for r in regions if r == rc.ARVERNI_REGION])[:required]


def expedition_request(state):
    """Offer the physical Roman force after Adjust Forces and relocation."""
    legions, auxilia = {}, []
    for region in state['spaces']:
        if region == rc.BRITANNIA:
            continue
        count = count_pieces(state, region, rc.ROMANS, rc.LEGION)
        if count:
            legions[region] = count
        for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
            count = count_pieces_by_state(state, region, rc.ROMANS, rc.AUXILIA, visibility)
            if count:
                auxilia.append({'region': region, 'piece_state': visibility, 'count': count})
    leader = find_leader(state, rc.ROMANS)
    harvest = rc.BRITANNIA_EXPEDITION_LEGIONS_TO_TRACK
    minimum_legions = rc.BRITANNIA_EXPEDITION_MIN_LEGIONS_TO_BRITANNIA
    minimum_auxilia = rc.BRITANNIA_EXPEDITION_MIN_AUXILIA_TO_BRITANNIA
    return {'kind': EXPEDITION, 'legions': legions, 'auxilia': auxilia,
            'leader_region': leader, 'harvest_count': harvest,
            'minimum_legions': minimum_legions, 'minimum_auxilia': minimum_auxilia,
            'can_conduct': (leader is not None and leader != rc.BRITANNIA
                            and sum(legions.values()) >= harvest + minimum_legions
                            and sum(row['count'] for row in auxilia) >= minimum_auxilia)}


def marker_request(state):
    return {'kind': MARKER, 'markers': [
        {'tribe': tribe, 'status': info['status']}
        for tribe, info in sorted(state['tribes'].items())
        if info.get('status') in (rc.MARKER_DISPERSED, rc.MARKER_DISPERSED_GATHERING)]}


def validate_response(state, request, response):
    """Validate the complete choice before mutating the Interlude board."""
    if isinstance(response, dict) and set(response) == {'use_default'} and response['use_default'] is True:
        return response
    if request['kind'] == ARVERNI_CITADELS:
        current = arverni_citadel_request(state)
        if (request.get('faction', rc.GERMANS) != rc.GERMANS
                or current != {key: value for key, value in request.items() if key != 'faction'}):
            raise ValueError('The offered Arverni Citadels have changed.')
        regions = response.get('regions') if isinstance(response, dict) else None
        if (not isinstance(regions, list) or set(response) != {'regions'}
                or len(regions) != current['count']
                or any(region not in current['regions'] for region in regions)
                or len(set(regions)) != len(regions)
                or rc.ARVERNI_REGION in regions[:-1]):
            raise ValueError('Choose the required distinct Arverni Citadels, taking Gergovia last.')
        return response
    if request['kind'] == AEDUI_CITADEL:
        current = aedui_citadel_request(state)
        if (request.get('faction', rc.AEDUI) != rc.AEDUI
                or current != {key: value for key, value in request.items() if key != 'faction'}):
            raise ValueError('The offered Aedui Citadels have changed.')
        if (not isinstance(response, dict) or set(response) != {'region'}
                or response['region'] not in current['regions']):
            raise ValueError('Choose a Citadel in one of the offered Regions.')
        return response
    if request['kind'] == SETTLEMENTS:
        current = settlement_request(state)
        if current != {key: value for key, value in request.items() if key != 'faction'}:
            raise ValueError('The offered Settlement replacements have changed.')
        allies = response.get('allies') if isinstance(response, dict) else None
        if (not isinstance(allies, dict) or set(response) != {'allies'}
                or len(allies) != current['required_allies']
                or any(tribe not in current['options'].get(region, ())
                       for region, tribe in allies.items())):
            raise ValueError(f"Assign exactly {current['required_allies']} Allies to offered Tribes in distinct Settlement Regions.")
        return response
    if request['kind'] == MARKER:
        if (not isinstance(response, dict) or set(response) != {'tribe'}
                or (response['tribe'] is not None and not any(
                    row['tribe'] == response['tribe']
                    and state['tribes'].get(row['tribe'], {}).get('status') == row['status']
                    for row in request['markers']))):
            raise ValueError('Choose one offered Dispersed marker, or tribe null to keep none.')
        return response
    if response == {'conduct': False} and type(response['conduct']) is bool:
        return response
    if (not isinstance(response, dict)
            or set(response) != {'conduct', 'harvest', 'legions', 'auxilia'}
            or response['conduct'] is not True or not request['can_conduct']):
        raise ValueError('Decline the expedition or allocate its complete Roman force.')
    current = expedition_request(state)
    if current != {key: value for key, value in request.items() if key != 'faction'}:
        raise ValueError('The offered expedition force has changed.')
    for key in ('harvest', 'legions'):
        allocation = response[key]
        if (not isinstance(allocation, dict) or not allocation
                or any(region not in request['legions'] or type(count) is not int or count <= 0
                       for region, count in allocation.items())):
            raise ValueError('Allocate positive Legion counts from offered Regions.')
    if (sum(response['harvest'].values()) != request['harvest_count']
            or sum(response['legions'].values()) < request['minimum_legions']
            or any(response['harvest'].get(region, 0) + response['legions'].get(region, 0) > count
                   for region, count in request['legions'].items())):
        raise ValueError('Reserve exactly three Harvest Legions and at least three other Legions.')
    rows = response['auxilia']
    if not isinstance(rows, list):
        raise ValueError('Choose exact Auxilia origins, visibility and positive counts.')
    remaining = {(row['region'], row['piece_state']): row['count'] for row in request['auxilia']}
    total = 0
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {'region', 'piece_state', 'count'}
                or not isinstance(row['region'], str) or not isinstance(row['piece_state'], str)
                or type(row['count']) is not int or row['count'] <= 0):
            raise ValueError('Choose exact Auxilia origins, visibility and positive counts.')
        cohort = row['region'], row['piece_state']
        if row['count'] > remaining.get(cohort, 0):
            raise ValueError('Expedition Auxilia exceed the offered physical cohort.')
        remaining[cohort] -= row['count']
        total += row['count']
    if total < request['minimum_auxilia']:
        raise ValueError('The expedition requires at least one Auxilia.')
    return response


def default_expedition(request):
    """Retain the existing NPC minimums and map/visibility selection order."""
    if not request['can_conduct']:
        return {'conduct': False}
    remaining = dict(request['legions'])
    allocations = {}
    for key, required in (('harvest', request['harvest_count']),
                          ('legions', request['minimum_legions'])):
        allocation = {}
        for region, available in remaining.items():
            count = min(required, available)
            if count:
                allocation[region] = count
                remaining[region] -= count
                required -= count
        allocations[key] = allocation
    required, auxilia = request['minimum_auxilia'], []
    for row in request['auxilia']:
        count = min(required, row['count'])
        if count:
            auxilia.append(dict(row, count=count))
            required -= count
    return {'conduct': True, **allocations, 'auxilia': auxilia}


def choose_expedition(state, decision):
    request = expedition_request(state)
    supplied = decision is not None
    if decision is None:
        if rc.ROMANS not in state.get('non_player_factions', set()) and request['can_conduct']:
            decision = consult_agent(state, rc.ROMANS, request)
        if decision is None:
            return default_expedition(request), 'np'
    if supplied and (type(decision) is bool or (isinstance(decision, dict)
                    and set(decision) == {'conduct'} and decision['conduct'] is True)):
        conduct = decision if type(decision) is bool else True
        source = 'player_bool' if type(decision) is bool else 'player_dict'
        if conduct and not request['can_conduct']:
            return {'conduct': False}, 'player_unable'
        return (default_expedition(request) if conduct else {'conduct': False}), source
    validate_response(state, request, decision)
    if decision == {'use_default': True}:
        return default_expedition(request), 'np'
    return decision, 'player_dict'


def choose_marker(state, tribe):
    request = marker_request(state)
    if tribe is not None:
        return validate_response(state, request, {'tribe': tribe})['tribe']
    if request['markers'] and rc.ROMANS not in state.get('non_player_factions', set()):
        response = consult_agent(state, rc.ROMANS, request)
        if response is not None:
            validate_response(state, request, response)
            if response != {'use_default': True}:
                return response['tribe']
    return None
