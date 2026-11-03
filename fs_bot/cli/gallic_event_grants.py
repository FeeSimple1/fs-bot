"""Executor and beneficiary choices for Gallic Shouts, Celtic Rites and Arduenna."""

from fs_bot.cli.action_windows import inspect_board
from fs_bot.cli.menus import prompt_choice
from fs_bot.engine.free_actions import validate_free_action_response


def collect_params(state, faction, card_id, shaded, stdin, stdout):
    """Defer selection to the live executor, then the selected beneficiary."""
    if card_id != 67 and not (card_id in (35, 46) and shaded):
        raise ValueError('This Event side does not grant a Gallic Command')
    return {}


def collect_selection(state, faction, request, stdin, stdout):
    """Choose a recipient or the recipient's order without silently delegating."""
    if request['request_type'] == 'gallic_event_beneficiary':
        choices = [(recipient, {'faction': recipient})
                   for recipient in request['factions']]
        prompt = f'{faction}: which Faction receives the Event actions?'
    elif request['request_type'] == 'gallic_command_order':
        labels = {'command': 'full Command', 'limited_command': 'Limited Command'}
        choices = [(' then '.join(labels[step] for step in order), {'order': list(order)})
                   for order in request['orders']]
        prompt = f'{faction}: choose the order of your free Commands (no Battles or Special Activity).'
    else:
        raise ValueError('Unknown Gallic Event selection')
    choices.append(('Use bot default', {'use_default': True}))
    while True:
        with inspect_board(state, stdout):
            response = prompt_choice(stdin, stdout, prompt, choices)
        error = validate_free_action_response(state, faction, request, response)
        if error:
            stdout.write(f'Cannot use this choice: {error}\n')
            continue
        return response
