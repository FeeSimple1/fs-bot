"""Donor-owned Resource gifts during §1.5.2 actions and Winter phases."""
from contextlib import contextmanager

from fs_bot import rules_consts as rc
from fs_bot.commands.transfer import transfer_eligibility_error, transfer_resources
from fs_bot.engine import action_windows
from fs_bot.engine.agent import consult_agent

KIND = 'resource_transfer'
SEQUENCE = 'sequence_of_play'
FRAME = '_resource_transfer_action'


def enabled(state):
    """Standard frontends opt in, preserving existing raw callback contracts."""
    agent = state.get('decision_agent')
    return not action_windows.is_preview(state) and bool(
        getattr(agent, 'supports_resource_transfers', False)
        or getattr(getattr(agent, '__self__', None), 'supports_resource_transfers', False))


def request_for(state, giver, phase, stage, **context):
    resources = state['resources']
    available = resources.get(giver, 0)
    if available <= 0:
        return None
    recipients = {}
    actor = context.get('actor')
    for receiver in rc.FACTIONS:
        if actor is not None and actor not in (giver, receiver):
            continue
        room = rc.MAX_RESOURCES - resources.get(receiver, 0)
        if room > 0 and transfer_eligibility_error(state, giver, receiver) is None:
            recipients[receiver] = min(available, room)
    if not recipients:
        return None
    return dict(kind=KIND, faction=giver, available=available, recipients=recipients,
                window=dict(phase=phase, stage=stage, winter=state.get('winter_count', 0),
                            **context))


def can_defer(request):
    window = request['window']
    return (window['phase'] == SEQUENCE and 'actor' in window
            and window['stage'] != 'action_end')


def validate_response(state, request, response):
    """Check every gift against the live offer and shared stock before moving any."""
    if (isinstance(response, dict) and set(response) == {'use_default'}
            and response['use_default'] is True):
        return response
    fields = set(response) if isinstance(response, dict) else set()
    defer = fields == {'transfers', 'defer'} and response['defer'] is True and can_defer(request)
    if ((fields != {'transfers'} and not defer)
            or not isinstance(response['transfers'], list)):
        raise ValueError('Provide a transfers list, or delegate to give nothing.')
    window = {key: value for key, value in request['window'].items() if key != 'winter'}
    if request != request_for(state, request['faction'], **window):
        raise ValueError('The offered Resource balances or recipients have changed.')
    available = request['available']
    remaining = dict(request['recipients'])
    for gift in response['transfers']:
        if not isinstance(gift, dict) or set(gift) != {'to', 'amount'}:
            raise ValueError('Each Resource transfer needs only to and amount.')
        receiver, amount = gift['to'], gift['amount']
        if not isinstance(receiver, str) or receiver not in remaining:
            raise ValueError('Choose an offered recipient for each Resource transfer.')
        if type(amount) is not int or not 0 < amount <= min(available, remaining[receiver]):
            raise ValueError('Give a positive integer within the remaining stock and recipient room.')
        available -= amount
        remaining[receiver] -= amount
    return response


def offer(state, phase, stage, *, finished=None, **context):
    """Resolve each eligible human donor's list on the current board."""
    if not enabled(state):
        return []
    receipts = []
    for giver in rc.FACTIONS:
        if giver in state.get('non_player_factions', ()) or (
                finished is not None and giver in finished):
            continue
        request = request_for(state, giver, phase, stage, **context)
        if request is None:
            continue
        response = consult_agent(state, giver, request)
        if response is None:
            response = {'use_default': True}
        validate_response(state, request, response)
        for gift in response.get('transfers', ()):
            receipt = transfer_resources(state, giver, gift['to'], gift['amount'])
            receipts.append(dict(receipt, stage=stage))
        if finished is not None and not response.get('defer'):
            finished.add(giver)
    return receipts


@contextmanager
def sequence(state, actor):
    """Keep one outer executor and one gift ledger through all sub-actions."""
    if FRAME in state or not enabled(state):
        yield
        return
    state[FRAME] = dict(actor=actor, action=None, occurrence=0, finished=set(), transfers=[])
    try:
        yield
    finally:
        state.pop(FRAME, None)


def started(state):
    return bool(state.get(FRAME, {}).get('action'))


def open_action(state, actor, action):
    """Open a selected Command or Event, possibly before collecting its plan."""
    frame = state.get(FRAME)
    if not frame or frame['actor'] != actor or frame['action'] or not enabled(state):
        return
    frame['action'] = action
    _boundary(state, frame, 'action_start')


def prepare_for_plan(state, actor, action_type):
    """Let terminal donors fund the plan before its costs are evaluated."""
    from fs_bot.engine.game_engine import (
        ACTION_COMMAND, ACTION_COMMAND_SA, ACTION_EVENT, ACTION_LIMITED_COMMAND,
    )
    if action_type in (ACTION_COMMAND, ACTION_COMMAND_SA, ACTION_EVENT, ACTION_LIMITED_COMMAND):
        open_action(state, actor, 'Event' if action_type == ACTION_EVENT else 'Command')


def record_authored(state, actor, transfers):
    frame = state.get(FRAME)
    if frame and frame['actor'] == actor and enabled(state):
        frame['transfers'].extend(transfers)


def checkpoint(state, context):
    """Use complete operation boundaries under the outer action's authority."""
    stage = context['stage']
    if (stage in ('action_start', 'action_end') or not started(state)
            or context['phase'] != SEQUENCE or not enabled(state)):
        return
    if state.get('_frumentum_budget', {}).get('paying'):
        # A53 is temporarily showing the grant allowance on Rome's track.
        return
    location = {key: context[key] for key in ('step', 'region', 'index', 'sa')
                if key in context}
    _boundary(state, state[FRAME], stage, **location)


def finish_action(state, actor, result):
    frame = state.get(FRAME)
    if frame and frame['action'] and frame['actor'] == actor and enabled(state):
        if result.get('executed'):
            _boundary(state, frame, 'action_end')
        if frame['transfers']:
            result['transfers'] = frame['transfers']


def _boundary(state, frame, stage, **location):
    frame['occurrence'] += 1
    frame['transfers'].extend(offer(
        state, SEQUENCE, stage, finished=frame['finished'], actor=frame['actor'],
        action=frame['action'], card=state.get('current_card'),
        occurrence=frame['occurrence'], **location))


def replay_position(state):
    """Order actions even when the Interlude resets the played-card pile."""
    completed = len(rc.FACTIONS) if state.get('_resolved_card') else 0
    return (bool(state.get('interlude_completed')), len(state.get('played_cards', ())),
            state.get('_card_turn', {}).get('idx', completed))
