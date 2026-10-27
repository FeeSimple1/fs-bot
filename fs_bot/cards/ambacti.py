"""Ambacti's placement and post-roll physical choices (Card 16, §5.1)."""

from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, get_available, get_leader_in_region,
    place_piece, remove_piece,
)
from fs_bot.engine.agent import consult_agent
from fs_bot.map.map_data import get_playable_regions_for_state

AMBACTI_REMOVAL = 'ambacti_removal'


def _explicit_default(response):
    return (isinstance(response, dict) and set(response) == {'use_default'}
            and response['use_default'] is True)


def eligible_regions(state):
    """Any Roman Forces piece satisfies the printed placement condition."""
    return sorted(region for region in get_playable_regions_for_state(state, rc.ROMANS)
                  if count_pieces(state, region, rc.ROMANS))


def placement_limit(state, region):
    return 6 if get_leader_in_region(state, region, rc.ROMANS) == rc.CAESAR else 4


def removal_targets(state):
    """Offer every on-map Auxilia, retaining Region and physical visibility."""
    return [{'region': region, 'piece_state': visibility, 'available': count}
            for region in sorted(state['spaces'])
            for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)
            if (count := count_pieces_by_state(
                state, region, rc.ROMANS, rc.AUXILIA, visibility))]


def removal_request(state, roll):
    targets = removal_targets(state)
    total = sum(target['available'] for target in targets)
    return {'kind': AMBACTI_REMOVAL, 'card_id': 16, 'roll': roll,
            'removal_counts': {'roll': min(roll, total), 'three': min(3, total)},
            'targets': targets}


def validate_response(state, request, response):
    """Require the full chosen number, subject to §5.1.3, before any loss."""
    if _explicit_default(response):
        return response
    if not isinstance(response, dict) or set(response) != {'removal_choice', 'removals'}:
        raise ValueError('Ambacti requires removal_choice and physical removals.')
    choice = response['removal_choice']
    if choice not in ('roll', 'three'):
        raise ValueError('Ambacti removal_choice must be roll or three.')
    removals = response['removals']
    if not isinstance(removals, list):
        raise ValueError('Ambacti removals must be a list of physical piece entries.')
    available = {(entry['region'], entry['piece_state']): entry['available']
                 for entry in removal_targets(state)}
    offered = {(entry['region'], entry['piece_state']): entry['available']
               for entry in request['targets']}
    total = 0
    for entry in removals:
        if not isinstance(entry, dict) or set(entry) != {'region', 'piece_state', 'count'}:
            raise ValueError('Each Ambacti removal needs region, piece_state, and count.')
        region, visibility, count = entry['region'], entry['piece_state'], entry['count']
        if not isinstance(region, str) or visibility not in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
            raise ValueError('Choose an offered Region and Auxilia visibility.')
        key = region, visibility
        if type(count) is not int or count <= 0 or count > min(
                available.get(key, 0), offered.get(key, 0)):
            raise ValueError('Ambacti removals exceed the offered physical Auxilia.')
        available[key] -= count
        offered[key] -= count
        total += count
    if total != request['removal_counts'][choice]:
        raise ValueError('Remove the entire chosen number of Auxilia, or all if fewer remain.')
    return response


def _legacy_response(state, faction, request, params):
    """Keep direct callers' old (Region, count) priorities outside human input."""
    choice = params.get('removal_choice', 'max')
    if choice not in ('roll', 'three', 'max'):
        raise ValueError('Ambacti removal_choice must be roll, three, or max.')
    if choice == 'max':
        choice = 'roll' if request['roll'] > 3 else 'three'
    number = request['removal_counts'][choice]
    if 'removals' in params:
        return {'removal_choice': choice, 'removals': params['removals']}
    priorities = params.get('auxilia_removal_regions')
    if priorities is None:
        from fs_bot.cards.ambacti_np import default_removals
        return {'removal_choice': choice,
                'removals': default_removals(state, faction, number)}
    if not isinstance(priorities, (list, tuple)):
        raise ValueError('Legacy Ambacti removal Regions must be (Region, count) pairs.')
    for entry in priorities:
        if (not isinstance(entry, (list, tuple)) or len(entry) != 2
                or not isinstance(entry[0], str) or entry[0] not in state['spaces']
                or type(entry[1]) is not int or entry[1] < 0):
            raise ValueError('Legacy Ambacti removal Regions must be (Region, count) pairs.')
    remaining = {(entry['region'], entry['piece_state']): entry['available']
                 for entry in request['targets']}
    removals = []
    # Historical priorities may be partial. Finish the required removals,
    # without changing the explicit Regions' ordering or inventing pieces.
    priorities = list(priorities) + [(region, number) for region in state['spaces']]
    for region, limit in priorities:
        for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
            count = min(number, limit, remaining.get((region, visibility), 0))
            if count:
                removals.append({'region': region, 'piece_state': visibility, 'count': count})
                remaining[region, visibility] -= count
                number -= count
                limit -= count
    return {'removal_choice': choice, 'removals': removals}


def _remove_after_roll(state, params):
    roll = state['rng'].randint(rc.DIE_MIN, rc.DIE_MAX)
    state.setdefault('event_modifiers', {})['card_16_die_roll'] = roll
    request = removal_request(state, roll)
    faction = state.get('executing_faction')
    response = consult_agent(state, faction, request)
    if response is None:
        # Durable frontends normalize an explicitly accepted bot default to
        # None. With an agent installed, old pre-roll params must never turn
        # that post-roll default into a different, precommitted human choice.
        legacy = params if state.get('decision_agent') is None else {}
        response = _legacy_response(state, faction, request, legacy)
    elif _explicit_default(response):
        response = _legacy_response(state, faction, request, {})
    validate_response(state, request, response)
    for entry in response['removals']:
        remove_piece(state, entry['region'], rc.ROMANS, rc.AUXILIA,
                     count=entry['count'], piece_state=entry['piece_state'])
    return dict(response, roll=roll)


def execute(state, shaded=False):
    params = state.get('event_params') or {}
    if not isinstance(params, dict):
        raise ValueError('Ambacti choices must be an object.')
    if not shaded:
        target = params.get('target_region')
        if target not in eligible_regions(state):
            return
        number = min(placement_limit(state, target), get_available(state, rc.ROMANS, rc.AUXILIA))
        if number:
            place_piece(state, target, rc.ROMANS, rc.AUXILIA, count=number)
        return {'target_region': target, 'placed': number}
    # Direct card callers get the same interruption guarantee as full turns:
    # a failed or pending post-roll decision restores both board and RNG.
    snapshot = deepcopy({key: value for key, value in state.items() if key != 'decision_agent'})
    agent = state.get('decision_agent')
    had_agent = 'decision_agent' in state
    try:
        return _remove_after_roll(state, params)
    except BaseException:
        state.clear()
        state.update(snapshot)
        if had_agent:
            state['decision_agent'] = agent
        raise
