"""Executor-selected Gallic beneficiaries, with their own live Command choices.

Card Reference 35S, 46S and 67; §§3.1, 5.1–5.1.3, 5.4, 8.2.3.
The outer Event executor retains timing authority throughout every grant.
"""
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.engine.free_actions import (command_options, consult_free_action,
                                         execute_free_action_plan)

ORDERS = (('command', 'limited_command'), ('limited_command', 'command'))


def supported(card_id, shaded):
    return card_id == 67 or (card_id in (35, 46) and shaded)


def factions(card_id):
    return ([rc.ROMANS] if card_id == 67 else []) + list(rc.GALLIC_FACTIONS)


def initial_params(state, card_id):
    raw = state.get('event_params')
    params = {} if raw is None else raw
    if not isinstance(params, dict) or set(params) - {'faction', 'stage_timing_actions'}:
        raise ValueError('This Event accepts its executor\'s beneficiary only; the recipient chooses its own actions live.')
    if 'faction' in params and params['faction'] not in factions(card_id):
        raise ValueError('Choose a Gallic beneficiary' + (' or Romans.' if card_id == 67 else '.'))
    if 'stage_timing_actions' in params:
        stages = params['stage_timing_actions']
        names = {'handler_complete', f'grant.card_{card_id}_' + {
            35: 'gallic_commands', 46: 'free_command', 67: 'arduenna'}[card_id],
            f'{card_id}.beneficiary'}
        names.update({35: {'35.order', '35.command', '35.limited_command'},
                      46: {'46.command'},
                      67: {'67.accept', '67.march', '67.command', '67.hide'}}[card_id])
        names.add('resolve_free_command')
        # Outer timing belongs to the Event executor, even beside a
        # recipient-owned decision. Initial params cannot supply that decision.
        if (not isinstance(stages, dict) or set(stages) - names
                or any(not isinstance(value, list) for value in stages.values())):
            raise ValueError('Only outer Event timing may accompany the beneficiary selection.')
    return params


def beneficiary_request(card_id):
    return {'kind': 'free_action', 'request_type': 'gallic_event_beneficiary',
            'card_id': card_id, 'factions': factions(card_id),
            'allow_decline': False, 'validate_default_response': True}


def order_request():
    return {'kind': 'free_action', 'request_type': 'gallic_command_order',
            'card_id': 35, 'orders': [list(order) for order in ORDERS],
            'allow_decline': False, 'validate_default_response': True}


def command_request(actor, card_id, *, limited=False):
    return {'kind': 'free_action', 'request_type': 'event_command',
            'card_id': card_id, 'gallic_event_card': card_id,
            'allowed_commands': [c for c in command_options(actor)
                                  if card_id != 35 or c != rc.CMD_BATTLE],
            'allowed_regions': None, 'max_regions': 1 if limited else None,
            'with_sa': False, 'free': True, 'allow_decline': False,
            'validate_default_response': True}


def _copy(state):
    trial = deepcopy({key: value for key, value in state.items() if key != 'decision_agent'})
    trial['_diviciacus_preview'] = True
    return trial


def validate_response(state, actor, request, response):
    from fs_bot.engine.free_actions import _validate_plan
    if not isinstance(response, dict):
        raise ValueError('Return an explicit beneficiary, order, or complete Command.')
    if set(response) & {'decline', 'use_default'}:
        if response != {'use_default': True} or response.get('use_default') is not True:
            raise ValueError('This Event requires its available actions; only explicit use_default is allowed.')
        if request.get('gallic_event_card'):
            result = _default_command(_copy(state), actor, request)
            if not result.get('executed'):
                raise ValueError('No non-player default is available; choose a legal Command.')
        return
    if request['request_type'] == 'gallic_event_beneficiary':
        if set(response) != {'faction'} or response['faction'] not in factions(request['card_id']):
            raise ValueError('Choose exactly one of this Event\'s legal beneficiary Factions.')
        return
    if request['request_type'] == 'gallic_command_order':
        if (set(response) != {'order'} or not isinstance(response['order'], list)
                or tuple(response['order']) not in ORDERS):
            raise ValueError('Choose Command then Limited Command, or Limited Command then Command.')
        return
    if 'command_parts' in (response.get('details') or {}):
        raise ValueError('This grant is one uninterrupted Command without a Special Ability.')
    error = _validate_plan(state, actor, request, response)
    if error:
        raise ValueError(error)


def _beneficiary(state, executor, card_id):
    from fs_bot.cards.card_effects import _event_step
    params = initial_params(state, card_id)
    _event_step(state, f'{card_id}.beneficiary')
    if executor in state.get('non_player_factions', ()):
        return executor if executor in factions(card_id) else None
    if 'faction' in params:
        return params['faction']
    selected = consult_free_action(state, executor, beneficiary_request(card_id))
    if selected is not None:
        return selected['faction']
    # §8.2.3: a Non-player selects its own benefits, never another faction's.
    # Human default choices outside that set use the game's seeded RNG.
    return executor if executor in factions(card_id) else state['rng'].choice(factions(card_id))


def _default_command(state, actor, request):
    from fs_bot.engine.execute import _resolve_free_command
    if actor == rc.ARVERNI and state['scenario'] in rc.ARIOVISTUS_SCENARIOS:
        from fs_bot.cards.gallic_arverni_np import resolve_command
        return resolve_command(state, request)
    return _resolve_free_command(state, actor, _consult=False,
        exclude_commands=set(command_options(actor)) - set(request['allowed_commands']),
        limited=request.get('max_regions') == 1, allow_decline=False)


def command_witness(state, actor, request):
    """A mechanically legal choice, independent of bot preference/IF-NONE."""
    from fs_bot.cards.arduenna import command_witness as other_witness
    from fs_bot.cli.human_plan import _march_routes
    from fs_bot.engine.free_actions import _validate_plan
    from fs_bot.map.map_data import get_playable_regions_for_state
    trial = _copy(state)
    regions = sorted(get_playable_regions_for_state(trial, actor))
    action = other_witness(trial, actor, regions=regions, request=request)
    if action is not None or rc.CMD_MARCH not in request['allowed_commands']:
        return action
    for origin in regions:
        for route in _march_routes(trial, origin, actor):
            action = {'command': rc.CMD_MARCH, 'regions': [origin], 'sa': 'No SA', 'sa_regions': [],
                'details': {'march_plan': {'origins': [origin], 'destinations': [route[-1]],
                                          'routes': {origin: route}}}}
            if _validate_plan(trial, actor, request, action) is None:
                return action
    return None


def _resolve_command(state, actor, card_id, *, limited=False):
    from fs_bot.cards.arduenna import consult_mandatory
    automatic = actor == rc.ARVERNI and state['scenario'] in rc.ARIOVISTUS_SCENARIOS
    request = command_request(actor, card_id, limited=limited)
    if automatic or not state.get('decision_agent') or actor in state.get('non_player_factions', ()):
        return _default_command(state, actor, request)
    attempt, previous_error = 1, None
    while True:
        if command_witness(state, actor, request) is None:
            return {'executed': False, 'declined_no_effect': True, 'reason': 'No legal Command is possible.'}
        request.update(attempt=attempt)
        if previous_error:
            request['previous_error'] = previous_error
        action, explicit = consult_mandatory(state, actor, request)
        result = (execute_free_action_plan(state, actor, request, action) if action is not None
                  else _default_command(state, actor, request))
        if not explicit or result.get('executed'):
            return result
        # Supply/loan refusal can invalidate a once-valid plan. Accepted
        # mandatory Commands are replanned on the actual resulting board.
        attempt += 1
        previous_error = result.get('reason', 'The selected action did not execute; choose another Command.')


def resolve(state, executor, card_id):
    from fs_bot.cards.card_effects import _event_step
    actor = _beneficiary(state, executor, card_id)
    if actor is None:
        return [{'free_action': 'free_command', 'flag': f'card_{card_id}',
                 'executed': False, 'declined_no_effect': True,
                 'reason': 'A Non-player cannot select another faction to benefit.'}]
    if card_id == 67:
        return resolve_arduenna(state, actor)
    if card_id == 35:
        _event_step(state, '35.order', beneficiary=actor)
        automatic = actor in state.get('non_player_factions', ()) or (
            actor == rc.ARVERNI and state['scenario'] in rc.ARIOVISTUS_SCENARIOS)
        selected = None if automatic else consult_free_action(state, actor, order_request())
        order = selected['order'] if selected is not None else state['rng'].choice(ORDERS)
    else:
        order = ['command']
    results = []
    for kind in order:
        _event_step(state, f'{card_id}.{kind}', beneficiary=actor)
        result = _resolve_command(state, actor, card_id, limited=kind == 'limited_command')
        results.append({'free_action': 'free_command', 'flag': f'card_{card_id}',
                        'faction': actor, 'kind': kind, 'result': result})
    return results


def resolve_arduenna(state, actor):
    from fs_bot.cards import arduenna
    from fs_bot.cards.card_effects import _event_step
    from fs_bot.board.pieces import count_pieces_by_state
    if (arduenna.march_witness(state, actor) is None
            and arduenna.command_witness(state, actor) is None
            and not any(count_pieces_by_state(state, r, actor, p, visibility)
                        for r in arduenna.TARGETS for p in (rc.AUXILIA, rc.WARBAND)
                        for visibility in (rc.REVEALED, rc.SCOUTED))):
        return [{'free_action': 'arduenna', 'flag': 'card_67',
                 'faction': actor, 'executed': False, 'declined_no_effect': True}]
    _event_step(state, '67.accept', beneficiary=actor)
    if actor in state.get('non_player_factions', ()):
        return default_arduenna(state, actor)
    accepted = consult_free_action(state, actor, {
        'kind': 'free_action', 'request_type': 'arduenna_accept', 'card_id': 67})
    if accepted is None:
        return default_arduenna(state, actor)
    if accepted == {'decline': True}:
        return [{'free_action': 'arduenna', 'flag': 'card_67',
                 'faction': actor, 'executed': False, 'declined': True}]
    _event_step(state, '67.march', beneficiary=actor)
    march = arduenna.resolve_stage(state, actor, marching=True, card_id=67)
    _event_step(state, '67.command', beneficiary=actor)
    command = arduenna.resolve_stage(state, actor, marching=False, card_id=67)
    _event_step(state, '67.hide', beneficiary=actor)
    hidden = arduenna.hide(state, actor, card_id=67)
    return [{'free_action': 'march', 'flag': 'card_67', 'faction': actor, 'result': march},
            {'free_action': 'free_command', 'flag': 'card_67', 'faction': actor, 'result': command}, hidden]


def default_arduenna(state, actor):
    from fs_bot.cards import arduenna
    from fs_bot.cards.card_effects import _event_step
    from fs_bot.engine.execute import _resolve_free_command
    if actor == rc.ARVERNI and state['scenario'] not in rc.ARIOVISTUS_SCENARIOS:
        from fs_bot.cards.base_arduenna_np import default_sequence
        return default_sequence(state)
    results = []
    _event_step(state, '67.march', beneficiary=actor)
    action = arduenna.default_march(state, actor)
    if action is not None:
        result = execute_free_action_plan(state, actor, arduenna.march_request(67), action)
        results.append({'free_action': 'march', 'flag': 'card_67',
                        'faction': actor, 'result': result})
    _event_step(state, '67.command', beneficiary=actor)
    result = _resolve_free_command(state, actor, allowed_regions=set(arduenna.TARGETS),
                                   exclude_commands={rc.CMD_MARCH}, _consult=False)
    results.append({'free_action': 'free_command', 'flag': 'card_67',
                    'faction': actor, 'result': result})
    _event_step(state, '67.hide', beneficiary=actor)
    results.append(arduenna.hide(state, actor, card_id=67))
    return results
