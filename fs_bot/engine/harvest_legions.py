"""Pax Gallica first-Harvest Winter Track Legions, also after Interlude."""
from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.engine.agent import consult_agent
from fs_bot.map.map_data import get_playable_regions_for_state

KIND = 'harvest_legions'


def validate_response(state, request, response):
    """Require every reserved Legion, using only offered playable Belgica."""
    if isinstance(response, dict) and set(response) == {'use_default'} and response['use_default'] is True:
        return response
    if not isinstance(response, dict) or set(response) != {'placements'}:
        raise ValueError('Allocate all Harvest Legions among the offered Belgica Regions.')
    placements = response['placements']
    playable = set(get_playable_regions_for_state(state, rc.ROMANS))
    if (not isinstance(placements, dict) or not placements
            or any(region not in request['legal_regions'] or region not in rc.BELGICA_REGIONS
                   or region not in playable or type(count) is not int or count <= 0
                   for region, count in placements.items())
            or sum(placements.values()) != request['count']
            or state.get('winter_track_legions', 0) < request['count']):
        raise ValueError('Place exactly the offered Harvest Legion count in legal Belgica Regions.')
    return response


def place_harvest_legions(state, maximum):
    """Preserve the legacy NPC concentration; let Romans allocate exactly."""
    count = min(maximum, state.get('winter_track_legions', 0))
    if count <= 0:
        return None
    playable = set(get_playable_regions_for_state(state, rc.ROMANS))
    regions = sorted(r for r in rc.BELGICA_REGIONS if r in playable)
    request = {'kind': KIND, 'count': count, 'legal_regions': regions,
               'source': 'winter_track'}
    response = (consult_agent(state, rc.ROMANS, request)
                if rc.ROMANS not in state.get('non_player_factions', set()) else None)
    default = response is None or response == {'use_default': True}
    if response is not None:
        validate_response(state, request, response)
    if default:
        dest = max(regions, key=lambda r: count_pieces(state, r, rc.ROMANS, rc.LEGION)
                   + count_pieces(state, r, rc.ROMANS, rc.AUXILIA))
        placements = {dest: count}
    else:
        placements = response['placements']
    for region, amount in placements.items():
        place_piece(state, region, rc.ROMANS, rc.LEGION, amount, from_winter_track=True)
    if default:
        return {'region': dest, 'legions': count}
    return {'placements': dict(placements), 'legions': count}
