"""A58 shaded: one Belgica Region for replacements and the follow-on Ambush."""
from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_available, place_piece, remove_piece
from fs_bot.bots.bot_common import random_select
from fs_bot.cards.base_piece_choices import STATES, _consult, _default, auxilia_region_request, validate_region_removals
from fs_bot.cards.expansion_validation import source_allies
from fs_bot.commands.sa_ambush import validate_ambush_region
from fs_bot.map.map_data import get_playable_regions_for_state

AUXILIA_LIMIT = 3


def make_request(state):
    playable = get_playable_regions_for_state(state)
    regions = [r for r in rc.BELGICA_REGIONS if r in playable]
    request = auxilia_region_request(state, 'A58', regions, AUXILIA_LIMIT)
    allies = {region: [] for region in regions}
    for entry in source_allies(state, regions):
        if entry['faction'] == rc.ROMANS:
            allies[entry['region']].append(entry['tribe'])
    request['ally_tribes_by_region'] = allies
    return request


def validate_response(state, request, response):
    if set(response) != {'region', 'ally_tribe', 'selections'}:
        raise ValueError('Choose one Belgica Region, its Roman Ally and exact Auxilia')
    live = make_request(state)
    region = response['region']
    validate_region_removals(request, live, region, response['selections'])
    tribe = response['ally_tribe']
    offered = request['ally_tribes_by_region'][region]
    present = live['ally_tribes_by_region'][region]
    if tribe is None and not (offered or present):
        return response
    if not isinstance(tribe, str) or tribe not in offered or tribe not in present:
        raise ValueError('Choose an offered Roman Ally in that Region')
    return response


def can_ambush(state, region, faction):
    if faction not in rc.FACTIONS or faction == rc.ROMANS:
        return False
    return (count_pieces(state, region, rc.ROMANS) > 0
            and validate_ambush_region(state, region, faction, rc.ROMANS)[0])


def _ranked_regions(state, request, faction):
    scores = {}
    for region, count in request['required_by_region'].items():
        ally = bool(request['ally_tribes_by_region'][region]) and faction != rc.ROMANS
        if ally or count or can_ambush(state, region, faction):
            scores[region] = (ally, count)
    if not scores:
        return []
    best = max(scores.values())
    return [region for region, score in scores.items() if score == best]


def np_available(state, faction):
    return bool(_ranked_regions(state, make_request(state), faction))


def _default_ally(state, tribes):
    priority = [tribe for tribe in tribes if tribe in rc.TRIBE_TO_CITY or tribe == rc.TRIBE_REMI]
    return random_select(state, priority or tribes) if tribes else None


def derive_params(state, faction):
    request = make_request(state)
    regions = _ranked_regions(state, request, faction)
    if not regions:
        return None
    region = random_select(state, regions)
    return {'region': region, 'ally_tribe': _default_ally(state, request['ally_tribes_by_region'][region])}


def _replace_ally(state, tribe, faction):
    from fs_bot.cards.card_effects import _ally_tribe, _unally_tribe

    if tribe is not None:
        _unally_tribe(state, tribe)
        if faction in rc.FACTIONS and rc.TRIBE_FACTION_RESTRICTION.get(tribe, faction) == faction:
            _ally_tribe(state, tribe, faction)


def _replace_auxilia(state, region, faction, visibility, count):
    remove_piece(state, region, rc.ROMANS, rc.AUXILIA, count=count, piece_state=visibility)
    if faction in rc.FACTIONS:
        replacements = min(count, get_available(state, faction, rc.WARBAND))
        if replacements:
            place_piece(state, region, faction, rc.WARBAND, count=replacements)


def resolve_replacements(state, params, region, tribe):
    """Return the chosen Region for the subsequent live Ambush."""
    from fs_bot.cards.card_effects import _event_entries

    request = make_request(state)
    faction = request['owner']
    ranked = _ranked_regions(state, request, faction)
    if 'piece_choices' in params:
        response = {'region': region, 'ally_tribe': tribe, 'selections': params['piece_choices']}
    else:
        response = _consult(state, request) if region is None and ranked else None
    if response is not None and not _default(response):
        validate_response(state, request, response)
        region = response['region']
        _replace_ally(state, response['ally_tribe'], faction)
        for entry in response['selections']:
            _replace_auxilia(state, region, faction, entry['piece_state'], entry['count'])
        return region

    if region is None:
        if not ranked:
            return None
        region = random_select(state, ranked)
    allies = request['ally_tribes_by_region']
    if not isinstance(region, str) or region not in allies:
        raise ValueError('Choose a playable Belgica Region for shaded A58')
    if tribe is not None and tribe not in allies[region]:
        raise ValueError('Choose a Roman Ally disc in that Region')
    _replace_ally(state, tribe if tribe is not None else _default_ally(state, allies[region]), faction)
    visibility_order = STATES[::-1] if faction == rc.ROMANS else STATES
    for _ in _event_entries(state, 'A58.auxilia_replacements', range(AUXILIA_LIMIT)):
        for visibility in visibility_order:
            if count_pieces_by_state(state, region, rc.ROMANS, rc.AUXILIA, visibility):
                _replace_auxilia(state, region, faction, visibility, 1)
                break
    return region
