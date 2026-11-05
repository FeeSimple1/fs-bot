"""Card 49: each owner chooses its own exact casualty in each Devastated Region.

Card Reference 49/Tips, §§1.4.1-.2, 5.1, 8.4.1; A1.4/A8.2.3.
The permanent Provincia Fort is never a casualty. German Warbands precede
German Allied Tribes, including when a human runs the German faction.
"""
from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_leader_in_region, remove_piece
from fs_bot.map.map_data import get_playable_regions_for_state

KIND = 'drought_loss'


def marker_regions(state):
    return [r for r in get_playable_regions_for_state(state)
            if rc.MARKER_DEVASTATED not in state.get('markers', {}).get(r, {})]


def validate_params(state, params):
    if not isinstance(params, dict):
        raise ValueError('Drought choices must be an object')
    if 'piece_removals' in params:
        raise ValueError('Drought losses belong to each owner; answer drought_loss instead of piece_removals')
    if set(params) - {'devastate_region', 'stage_timing_actions'}:
        raise ValueError('Unexpected Drought choices')
    if 'devastate_region' in params and params['devastate_region'] not in marker_regions(state):
        raise ValueError('Choose a playable Region without a Devastated marker')


def targets(state, region, faction):
    from fs_bot.cards.card_effects import _tribe_region, _tribe_piece_type
    result = []
    for piece in rc.PIECE_TYPES:
        count = count_pieces(state, region, faction, piece)
        if not count:
            continue
        if piece == rc.FORT and region == rc.PROVINCIA:
            continue
        if piece in rc.FLIPPABLE_PIECES:
            for ps in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
                if count_pieces_by_state(state, region, faction, piece, ps):
                    result.append({'piece_type': piece, 'piece_state': ps})
        elif piece in (rc.ALLY, rc.CITADEL):
            if (faction == rc.GERMANS and piece == rc.ALLY
                    and count_pieces(state, region, faction, rc.WARBAND)):
                continue
            tribes = sorted(t for t, info in state['tribes'].items()
                            if info.get('allied_faction') == faction
                            and _tribe_region(state, t) == region and _tribe_piece_type(state, t) == piece)
            result.extend({'piece_type': piece, 'tribe': t} for t in tribes)
            # Legacy synthetic boards can have an unnamed physical disc.
            # Never hide that casualty or attach it to another Tribe.
            if count > len(tribes):
                result.append({'piece_type': piece, 'tribe': None})
        elif piece == rc.LEADER:
            result.append({'piece_type': piece, 'leader_name': get_leader_in_region(state, region, faction)})
        else:
            result.append({'piece_type': piece})
    return result


def request_for(state, region, faction):
    return {'kind': KIND, 'card_id': 49, 'region': region, 'faction': faction,
            'targets': targets(state, region, faction)}


def validate_response(state, request, response):
    if (isinstance(response, dict) and set(response) == {'use_default'}
            and response['use_default'] is True):
        return response
    if not isinstance(response, dict) or set(response) != {'piece'} or not isinstance(response['piece'], dict):
        raise ValueError('Choose exactly one offered Drought casualty for this owner')
    target = response['piece']
    if target not in request['targets'] or target not in targets(state, request['region'], request['faction']):
        raise ValueError('Drought casualty must be an offered, present physical piece of this owner')
    return response


def default_target(state, request):
    from fs_bot.bots.bot_common import is_ally_in_city_or_remi, random_select
    def priority(target):
        piece = target['piece_type']
        if piece in rc.FLIPPABLE_PIECES:
            return (0, (rc.SCOUTED, rc.REVEALED, rc.HIDDEN).index(target['piece_state']))
        if piece == rc.ALLY:
            return (1, int(is_ally_in_city_or_remi(target.get('tribe'), state['scenario'])))
        if piece in (rc.CITADEL, rc.FORT, rc.SETTLEMENT):
            return (2, 0)
        return (3 if piece == rc.LEGION else 4, 0)
    best = min(map(priority, request['targets']))
    return random_select(state, [t for t in request['targets'] if priority(t) == best])


def remove_loss(state, region, faction):
    from fs_bot.cards.card_effects import _unally_tribe
    from fs_bot.engine.agent import consult_agent
    request = request_for(state, region, faction)
    if not request['targets']:
        return
    game_run = (faction == rc.GERMANS if state['scenario'] in rc.BASE_SCENARIOS else faction == rc.ARVERNI)
    response = (None if game_run or state.get('_diviciacus_preview') else
                consult_agent(state, faction, request))
    if response is not None:
        validate_response(state, request, response)
    target = (default_target(state, request) if response is None or response.get('use_default') is True
              else response['piece'])
    piece = target['piece_type']
    if piece in (rc.ALLY, rc.CITADEL) and target['tribe'] is not None:
        _unally_tribe(state, target['tribe'])
    else:
        remove_piece(state, region, faction, piece, piece_state=target.get('piece_state'),
                     to_fallen=piece == rc.LEGION)
