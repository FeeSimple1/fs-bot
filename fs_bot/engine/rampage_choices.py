"""Physical Rampage victims and their shared Retreat destination (§4.5.2)."""
from collections import Counter

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state
from fs_bot.board.control import is_controlled_by
from fs_bot.map.map_data import is_adjacent


def victim_pieces(state, region, faction):
    """Keep the established NPC type and visibility priority."""
    pieces = []
    for piece in (rc.WARBAND, rc.AUXILIA):
        for visibility in (rc.SCOUTED, rc.REVEALED, rc.HIDDEN):
            pieces.extend([(piece, visibility)] * count_pieces_by_state(
                state, region, faction, piece, visibility))
    pieces.extend([(rc.LEGION, None)] * count_pieces(state, region, faction, rc.LEGION))
    return pieces


def validate_response(state, request, response):
    """Choose exactly the affected count, reserving every physical cohort."""
    if isinstance(response, dict) and set(response) == {'use_default'} and response['use_default'] is True:
        return response
    if (not isinstance(response, dict) or set(response) != {'actions', 'retreat_region'}
            or not isinstance(response['actions'], list)
            or len(response['actions']) != request['context']['num_pieces']):
        raise ValueError('Choose one exact piece and disposition per affected Warband.')
    available = Counter(tuple(piece) for piece in request['pieces'])
    live = Counter(victim_pieces(state, request['region'], request['defender']))
    retreating = False
    for action in response['actions']:
        if (not isinstance(action, dict) or set(action) != {'action', 'piece_type', 'piece_state'}
                or action['action'] not in ('remove', 'retreat')
                or action['piece_type'] not in (rc.WARBAND, rc.AUXILIA, rc.LEGION)
                or action['piece_state'] not in (None, rc.HIDDEN, rc.REVEALED, rc.SCOUTED)):
            raise ValueError('Select offered physical pieces and remove or retreat dispositions.')
        piece = action['piece_type'], action['piece_state']
        if available[piece] <= 0 or live[piece] <= 0:
            raise ValueError('Rampage selects an unavailable or already claimed physical piece.')
        available[piece] -= 1
        live[piece] -= 1
        retreating |= action['action'] == 'retreat'
    destination = response['retreat_region']
    if retreating:
        if (not isinstance(destination, str) or destination not in request['legal_regions']
                or not is_adjacent(request['region'], destination)
                or not any(is_controlled_by(state, destination, owner) for owner in rc.FACTIONS
                           if owner != rc.GERMANS and not
                           (owner == rc.ARVERNI and state['scenario'] in rc.ARIOVISTUS_SCENARIOS))
                or (state['scenario'] in rc.ARIOVISTUS_SCENARIOS
                    and request['defender'] == rc.ARVERNI)):
            raise ValueError('Retreating Rampage victims must share one legal destination.')
    elif destination is not None:
        raise ValueError('A removal-only Rampage choice must have retreat_region null.')
    return response


def compatible_request(current, saved):
    """An old recorded all-or-none prompt differs only by its absent pieces."""
    return (isinstance(saved, dict) and saved.get('kind') == 'retreat'
            and saved.get('context', {}).get('rampage') is True and 'pieces' not in saved
            and {key: value for key, value in current.items() if key != 'pieces'} == saved)


def target_actions(response):
    return [dict(action, **({'retreat_region': response['retreat_region']}
                           if action['action'] == 'retreat' else {}))
            for action in response['actions']]


def legacy_destination(response, legal_regions):
    """A raw adapter or recorded old prompt delegates its physical subset."""
    if (not isinstance(response, dict) or set(response) - {'retreat', 'region'}
            or type(response.get('retreat')) is not bool):
        raise ValueError('A legacy Rampage choice needs a boolean retreat flag.')
    destination = response.get('region')
    if response['retreat']:
        if destination not in legal_regions:
            raise ValueError('Retreat destination is not a legal Region.')
        return destination
    if destination is not None:
        raise ValueError('A removal-only legacy response must have region null.')
    return None
