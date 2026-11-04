"""Card 9: one adjacent March near Provincia, then destination-scoped actions."""
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.commands.common import free_action_scope
from fs_bot.engine.diviciacus import eligible_regions, force_scope
from fs_bot.engine.free_actions import consult_free_action, _explicit_sentinel
from fs_bot.map.map_data import get_adjacent_for_state, get_playable_regions_for_state

REQUEST = 'mons_cevenna_march'
NEAR = (rc.PROVINCIA, rc.SEQUANI, rc.ARVERNI_REGION)


def _copy(state):
    return deepcopy({key: value for key, value in state.items() if key != 'decision_agent'})


def near_regions(state, faction):
    return [r for r in NEAR if r in get_playable_regions_for_state(state, faction)]


def validate_pair(state, faction, origin, destination):
    near = near_regions(state, faction)
    if (origin not in near or destination not in near
            or destination not in get_adjacent_for_state(state, origin, faction)):
        raise ValueError('Mons Cevenna needs adjacent, distinct Regions within Provincia, Sequani and Arverni.')


def initial_params(state):
    raw = state.get('event_params')
    params = {} if raw is None else raw
    if not isinstance(params, dict) or set(params) - {'march_from', 'march_to', 'stage_timing_actions'}:
        raise ValueError('Mons Cevenna accepts only its initial route and Event timing.')
    origin, destination = params.get('march_from'), params.get('march_to')
    if origin is not None or destination is not None:
        validate_pair(state, state.get('executing_faction') or rc.ROMANS, origin, destination)
    return origin, destination


def pools(state, faction):
    from fs_bot.engine.execute import _mobile_march_group
    return {r: _mobile_march_group(state, faction, r) for r in near_regions(state, faction)}


def routes(state, faction, origin, group):
    from fs_bot.cli.human_plan import _march_routes
    sim = _copy(state)
    sim['_diviciacus_preview'] = True
    sim.pop('_cli_required_destinations', None)
    with free_action_scope(sim, faction):
        return [path for path in _march_routes(sim, origin, faction, group)
                if len(path) == 1 and path[0] in near_regions(sim, faction)]


def has_march(state, faction):
    return any(any(group.values()) and routes(state, faction, origin, group)
               for origin, group in pools(state, faction).items())


def make_request(state, faction, *, attempt=1, previous_error=None):
    request = {'kind': 'free_action', 'request_type': REQUEST, 'card_id': 9,
               'acting_faction': faction, 'allowed_commands': [rc.CMD_MARCH],
               'allowed_regions': near_regions(state, faction),
               'origins': pools(state, faction),
               'cooperation_regions': sorted(eligible_regions(state, faction)),
               'free': True, 'with_sa': False, 'allow_decline': False,
               'validate_default_response': True, 'attempt': attempt}
    if previous_error:
        request['previous_error'] = previous_error
    return request


def validate_response(state, faction, request, response):
    try:
        _validate(state, faction, response)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        return str(exc)
    return None


def _validate(state, faction, response):
    if _explicit_sentinel(response, 'use_default'):
        return
    if (not isinstance(response, dict) or not {'origin', 'destination', 'group'} <= set(response)
            or set(response) - {'origin', 'destination', 'group', 'diviciacus_regions'}):
        raise ValueError('Choose origin, destination and explicit mobile piece counts.')
    origin, destination, group = response['origin'], response['destination'], response['group']
    cooperation = response.get('diviciacus_regions', [])
    if (not isinstance(cooperation, list) or any(not isinstance(r, str) for r in cooperation)
            or len(cooperation) != len(set(cooperation))
            or not set(cooperation) <= ({origin} & set(eligible_regions(state, faction)))):
        raise ValueError('Request cooperation only at the chosen March origin.')
    if origin is None:
        if (destination not in near_regions(state, faction) or group != {} or cooperation
                or has_march(state, faction)):
            raise ValueError('Omit movement only if no native March is possible; choose its follow-on Region.')
        return
    validate_pair(state, faction, origin, destination)
    if (not isinstance(group, dict) or not group
            or set(group) - {rc.LEGION, rc.AUXILIA, rc.WARBAND, rc.LEADER}):
        raise ValueError('Select mobile pieces only.')
    sim = _copy(state)
    sim['_diviciacus_preview'] = True
    with force_scope(sim, faction, cooperation):
        available = pools(sim, faction)[origin]
        for piece in (rc.LEGION, rc.AUXILIA, rc.WARBAND):
            n = group.get(piece, 0)
            if type(n) is not int or not 0 <= n <= available[piece]:
                raise ValueError('Piece counts must fit the selected initial origin.')
        leader = group.get(rc.LEADER, False)
        if type(leader) is not bool or (leader and not available[rc.LEADER]):
            raise ValueError('Choose only a Leader present at this origin.')
        if not any(group.values()):
            raise ValueError('Select at least one moving piece.')
        actual = dict(group, **{rc.LEADER: available[rc.LEADER] if leader else None})
        if [destination] not in routes(sim, faction, origin, actual):
            raise ValueError('The selected group cannot March along that adjacent route.')


def action_for(response):
    return {'command': rc.CMD_MARCH, 'regions': [response['origin']], 'sa': 'No SA',
            'sa_regions': [], 'details': {
                'diviciacus_regions': response.get('diviciacus_regions', []),
                'explicit_moves': [{'origin': response['origin'],
                    'path': [response['destination']], 'group': response['group']}]}}


def _resolve(state, faction, march_from, march_to):
    from fs_bot.engine.execute import (_resolve_card9_march_command_default,
                                      _resolve_free_command)
    from fs_bot.cards.arduenna_march import execute_march
    from fs_bot.engine.diviciacus_planning import clear_confirmation
    if faction in state.get('non_player_factions', ()):
        return _resolve_card9_march_command_default(state, faction, march_from, march_to)
    attempt, error = 1, None
    while True:
        response = consult_free_action(state, faction, make_request(
            state, faction, attempt=attempt, previous_error=error))
        if response is None:
            return _resolve_card9_march_command_default(state, faction, march_from, march_to)
        destination = response['destination']
        result = {'executed': False, 'declined_no_effect': True,
                  'reason': 'No native March available; resolve the remaining destination benefit.'}
        if response['origin'] is not None:
            action = action_for(response)
            try:
                with free_action_scope(state, faction):
                    result = execute_march(state, faction, action,
                        target_regions={destination}, source_id='9')
            finally:
                clear_confirmation(state, faction, action)
            if result.get('reason') == 'Diviciacus agreement was refused; choose a new plan':
                attempt += 1
                error = result['reason']
                continue
        following = _resolve_free_command(state, faction, allowed_regions={destination},
                                           with_sa=True, allow_decline=False)
        return [{'free_action': 'march', 'flag': 'card_9', 'source': response['origin'],
                 'final_region': destination, 'result': result},
                {'free_action': 'free_command', 'flag': 'card_9', 'result': following}]


def resolve(state, faction, march_from=None, march_to=None):
    """Keep the complete Event atomic across later human pending decisions."""
    snapshot = _copy(state)
    agent, had_agent = state.get('decision_agent'), 'decision_agent' in state
    card_turn = state.get('_card_turn')
    try:
        return _resolve(state, faction, march_from, march_to)
    except BaseException:
        state.clear()
        state.update(snapshot)
        if card_turn is not None:
            state['_card_turn'] = card_turn
        if had_agent:
            state['decision_agent'] = agent
        raise
