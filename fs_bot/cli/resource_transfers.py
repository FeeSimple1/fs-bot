"""Collect one donor's exact gifts without mutating the live board."""
from fs_bot.cli.action_windows import inspect_board
from fs_bot.cli.menus import prompt_amount, prompt_choice
from fs_bot.engine.resource_transfers import can_defer


def collect_transfers(state, faction, request, stdin, stdout):
    window = request['window']
    stage = window.get('step') or window['stage'].replace('_', ' ')
    if 'actor' in window:
        label = f"{window['actor']} {window['action']}, {stage}"
        if window.get('region'):
            label += f" in {window['region']}"
    else:
        label = f"{window['phase'].replace('_', ' ').capitalize()} {stage}"
    available = request['available']
    remaining = dict(request['recipients'])
    transfers = []
    later = can_defer(request)
    with inspect_board(state, stdout):
        while later or (available and any(remaining.values())):
            choices = [('Finish Resource transfers', None)]
            if later:
                choices.append(('Offer Resource transfers again later in this action', 'defer'))
            choices.extend(
                (f'Give to {receiver} (up to {min(available, room)})', receiver)
                for receiver, room in remaining.items() if available and room)
            receiver = prompt_choice(stdin, stdout,
                                     f'{label}. {faction} has {available} Resources to give.', choices)
            if receiver is None:
                break
            if receiver == 'defer':
                return {'transfers': transfers, 'defer': True}
            amount = prompt_amount(stdin, stdout, f'Give how many to {receiver}?',
                                   min(available, remaining[receiver]))
            transfers.append(dict(to=receiver, amount=amount))
            available -= amount
            remaining[receiver] -= amount
    return {'transfers': transfers}
