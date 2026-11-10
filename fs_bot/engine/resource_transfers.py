"""Donor-owned Resource gifts at the §1.5.2 Winter phase boundaries."""
from fs_bot import rules_consts as rc
from fs_bot.commands.transfer import transfer_eligibility_error, transfer_resources
from fs_bot.engine import action_windows
from fs_bot.engine.agent import consult_agent

KIND = 'resource_transfer'


def enabled(state):
    """Standard frontends opt in, preserving existing raw callback contracts."""
    agent = state.get('decision_agent')
    return not action_windows.is_preview(state) and bool(
        getattr(agent, 'supports_resource_transfers', False)
        or getattr(getattr(agent, '__self__', None), 'supports_resource_transfers', False))


def request_for(state, giver, phase, stage):
    resources = state['resources']
    available = resources.get(giver, 0)
    if available <= 0:
        return None
    recipients = {}
    for receiver in rc.FACTIONS:
        room = rc.MAX_RESOURCES - resources.get(receiver, 0)
        if room > 0 and transfer_eligibility_error(state, giver, receiver) is None:
            recipients[receiver] = min(available, room)
    if not recipients:
        return None
    return dict(kind=KIND, faction=giver, available=available, recipients=recipients,
                window=dict(phase=phase, stage=stage, winter=state.get('winter_count', 0)))


def validate_response(state, request, response):
    """Check every gift against the live offer and shared stock before moving any."""
    if (isinstance(response, dict) and set(response) == {'use_default'}
            and response['use_default'] is True):
        return response
    if (not isinstance(response, dict) or set(response) != {'transfers'}
            or not isinstance(response['transfers'], list)):
        raise ValueError('Provide a transfers list, or delegate to give nothing.')
    window = request['window']
    if request != request_for(state, request['faction'], window['phase'], window['stage']):
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


def offer(state, phase, stage):
    """Resolve each eligible human donor's list on the current board."""
    if not enabled(state):
        return []
    receipts = []
    for giver in rc.FACTIONS:
        if giver in state.get('non_player_factions', ()):
            continue
        request = request_for(state, giver, phase, stage)
        if request is None:
            continue
        response = consult_agent(state, giver, request)
        if response is None:
            continue
        for gift in validate_response(state, request, response).get('transfers', ()):
            receipt = transfer_resources(state, giver, gift['to'], gift['amount'])
            receipts.append(dict(receipt, stage=stage))
    return receipts
