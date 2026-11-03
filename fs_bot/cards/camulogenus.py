"""Card70: Roman acceptance and exact, single-destination March choices.

The printed four-Legion limit applies to the entire March. Groups retain
their initial physical counters; only moving Auxilia flip. Battle is a
separate Command, with fresh Diviciacus agreement on its resulting board.
"""
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, get_leader_in_region
from fs_bot.engine.diviciacus import eligible_regions, force_scope
from fs_bot.engine.free_actions import consult_free_action, _explicit_sentinel
from fs_bot.map.map_data import get_playable_regions_for_state

TARGETS = (rc.ATREBATES, rc.CARNUTES, rc.MANDUBII)
REQUEST = 'camulogenus_march'
FLAG = 'card_70_roman_march_battle'
REFUSED = 'Diviciacus agreement was refused; choose a new plan'


def _copy(state):
    return deepcopy({key: value for key, value in state.items() if key != 'decision_agent'})


def origin_groups(state):
    """Physical/planned loan totals; does not consume choices or randomness."""
    result = {}
    for region in sorted(get_playable_regions_for_state(state, rc.ROMANS)):
        group = {'legions': count_pieces(state, region, rc.ROMANS, rc.LEGION),
                 'auxilia': count_pieces(state, region, rc.ROMANS, rc.AUXILIA),
                 'caesar': get_leader_in_region(state, region, rc.ROMANS) == rc.CAESAR}
        if group['legions'] or group['auxilia'] or group['caesar']:
            result[region] = group
    return result


def march_routes(state, origin, group, destination=None):
    """Complete movement-only routes, with no Harassment preview or die rolls."""
    from fs_bot.cli.human_plan import _march_routes
    probe = _copy(state)
    probe['_diviciacus_preview'] = True
    # The Event supplies its own destination, independent of any outer menu.
    probe.pop('_cli_required_destinations', None)
    destinations = set(TARGETS if destination is None else [destination])
    return [path for path in _march_routes(probe, origin, rc.ROMANS, group)
            if path and path[-1] in destinations]


def make_request(state, target_regions=None, legion_limit=4, *, attempt=1, previous_error=None):
    targets = sorted(set(TARGETS) & set(TARGETS if target_regions is None else target_regions))
    request = {'kind': 'free_action', 'request_type': REQUEST, 'card_id': 70,
               'acting_faction': rc.ROMANS, 'destinations': targets,
               'allowed_regions': targets, 'allowed_commands': [rc.CMD_MARCH],
               'legion_limit': min(4, legion_limit), 'origins': origin_groups(state),
               'cooperation_regions': sorted(eligible_regions(state, rc.ROMANS)),
               'free': True, 'with_sa': False, 'allow_decline': False,
               'validate_default_response': True, 'default_available': True,
               'attempt': attempt}
    if previous_error:
        request['previous_error'] = previous_error
    return request


def _group(entry):
    return {rc.LEGION: entry['legions'], rc.AUXILIA: entry['auxilia'],
            rc.WARBAND: 0, rc.LEADER: rc.CAESAR if entry['caesar'] else None}


def _validate(state, request, response):
    if _explicit_sentinel(response, 'use_default'):
        return
    if _explicit_sentinel(response, 'decline'):
        raise ValueError('Decline the entire Camulogenus benefit before choosing its March.')
    if (not isinstance(response, dict)
            or not {'destination', 'marches'} <= set(response)
            or set(response) - {'destination', 'marches', 'diviciacus_regions'}):
        raise ValueError('Choose one destination and an ordered list of March groups.')
    destination, marches = response['destination'], response['marches']
    if not isinstance(destination, str) or destination not in request['destinations']:
        raise ValueError('Choose Atrebates, Carnutes, or Mandubii as the single destination.')
    if not isinstance(marches, list):
        raise ValueError('Marches must be an ordered list; use an empty list for no movement.')
    regions = response.get('diviciacus_regions', [])
    if (not isinstance(regions, list) or any(not isinstance(r, str) for r in regions)
            or len(regions) != len(set(regions))
            or not set(regions) <= set(eligible_regions(state, rc.ROMANS))):
        raise ValueError('Request Diviciacus cooperation only in eligible March origins.')
    # Validation assumes permission without obtaining the other player's
    # live answer. Actual command_scope independently obtains that consent.
    probe = _copy(state)
    probe['_diviciacus_preview'] = True
    with force_scope(probe, rc.ROMANS, regions):
        remaining = origin_groups(probe)
        total_legions, origins = 0, set()
        for entry in marches:
            if (not isinstance(entry, dict) or set(entry) !=
                    {'origin', 'route', 'legions', 'auxilia', 'caesar'}):
                raise ValueError('Each group requires origin, route, legions, auxilia, and caesar; no drop-offs.')
            origin, path = entry['origin'], entry['route']
            if not isinstance(origin, str) or origin not in remaining:
                raise ValueError('Choose an origin with available Legions, Auxilia, or Caesar.')
            available = remaining[origin]
            for piece in ('legions', 'auxilia'):
                n = entry[piece]
                if type(n) is not int or not 0 <= n <= available[piece]:
                    raise ValueError('Counts must fit the pieces remaining at their initial origin.')
                available[piece] -= n
            if type(entry['caesar']) is not bool or (entry['caesar'] and not available['caesar']):
                raise ValueError('Only Caesar may accompany a group, once from his initial origin.')
            if entry['caesar']:
                available['caesar'] = False
            total_legions += entry['legions']
            if total_legions > request['legion_limit']:
                raise ValueError('Camulogenus permits at most four Legions across the entire March.')
            if not (entry['legions'] or entry['auxilia'] or entry['caesar']):
                raise ValueError('Each selected moving group needs at least one piece.')
            if (not isinstance(path, list) or not path
                    or any(not isinstance(region, str) for region in path)
                    or path not in march_routes(probe, origin, _group(entry), destination)):
                raise ValueError('Each moving group needs a complete legal route to the single destination; no drop-offs.')
            origins.add(origin)
        if not set(regions) <= origins:
            raise ValueError('Diviciacus cooperation must apply to selected March origins.')


def validate_response(state, request, response):
    """Validate without changing the live board, RNG, or player decisions."""
    try:
        _validate(state, request, response)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        return str(exc)
    return None


def action_for(response):
    origins = list(dict.fromkeys(entry['origin'] for entry in response['marches']))
    return {'command': rc.CMD_MARCH, 'sa': 'No SA', 'sa_regions': [], 'regions': origins,
            'details': {'diviciacus_regions': list(response.get('diviciacus_regions', [])),
                        'explicit_moves': [{'origin': entry['origin'], 'path': list(entry['route']),
                                            'group': _group(entry)} for entry in response['marches']]}}


def _refused_march(result):
    return any(entry.get('free_action') == 'march'
               and (entry.get('result') or {}).get('reason') == REFUSED
               for entry in result)


def _resolve(state, target_regions, legion_limit):
    from fs_bot.cards.roman_event_grants import accept_request
    from fs_bot.engine.execute import (_resolve_card70_march_battle_default,
                                      _resolve_card70_battle)
    from fs_bot.engine.diviciacus_planning import clear_confirmation
    from fs_bot.commands.common import free_action_scope
    from fs_bot.cards.arduenna_march import execute_march
    if rc.ROMANS in state.get('non_player_factions', ()):
        return _resolve_card70_march_battle_default(state, target_regions, legion_limit)
    response = consult_free_action(state, rc.ROMANS, accept_request(70))
    if response and response.get('decline'):
        return [{'free_action': 'roman_benefit', 'flag': FLAG, 'executed': False,
                 'declined_no_effect': True, 'reason': 'Romans declined the complete March-and-Battle benefit.'}]
    attempt, previous_error = 1, None
    while True:
        request = make_request(state, target_regions, legion_limit,
                               attempt=attempt, previous_error=previous_error)
        response = consult_free_action(state, rc.ROMANS, request)
        if response is None:
            result = _resolve_card70_march_battle_default(state, target_regions, legion_limit)
            if _refused_march(result):
                attempt += 1
                previous_error = REFUSED
                continue
            return result
        destination = response['destination']
        march = {'executed': False, 'command': rc.CMD_MARCH, 'marches': [],
                 'errors': [], 'total_cost': 0, 'declined_no_effect': True,
                 'reason': 'Romans selected no moving groups.'}
        if response['marches']:
            action = action_for(response)
            try:
                with free_action_scope(state, rc.ROMANS):
                    march = execute_march(state, rc.ROMANS, action,
                        target_regions={destination}, source_id='70', moving_only=True)
            finally:
                clear_confirmation(state, rc.ROMANS, action)
            if march.get('executed') is False and march.get('reason') == REFUSED:
                attempt += 1
                previous_error = march['reason']
                continue
        moved = {'legions': sum(e['legions'] for e in response['marches']),
                 'auxilia': sum(e['auxilia'] for e in response['marches'])}
        result = _resolve_card70_battle(state, destination, moved)
        # Preserve the established Battle envelope and report all actual
        # March groups, including those stopped early by Harassment.
        result[0]['march_result'] = march
        return result


def resolve(state, target_regions=None, legion_limit=4):
    """Pending/invalid later choices roll back the entire compound benefit."""
    snapshot = _copy(state)
    agent, had_agent = state.get('decision_agent'), 'decision_agent' in state
    card_turn = state.get('_card_turn')
    try:
        return _resolve(state, target_regions, legion_limit)
    except BaseException:
        state.clear()
        state.update(snapshot)
        if card_turn is not None:
            state['_card_turn'] = card_turn
        if had_agent:
            state['decision_agent'] = agent
        raise
