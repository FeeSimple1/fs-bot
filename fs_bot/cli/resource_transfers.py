"""Collect one donor's exact Winter gifts without mutating the live board."""
from fs_bot.cli.action_windows import inspect_board
from fs_bot.cli.menus import prompt_amount, prompt_choice


def collect_transfers(state, faction, request, stdin, stdout):
    window = request['window']
    phase = window['phase'].capitalize()
    stage = window['stage'].replace('_', ' ')
    available = request['available']
    remaining = dict(request['recipients'])
    transfers = []
    with inspect_board(state, stdout):
        while available and any(remaining.values()):
            choices = [('Finish Resource transfers', None)] + [
                (f'Give to {receiver} (up to {min(available, room)})', receiver)
                for receiver, room in remaining.items() if room
            ]
            receiver = prompt_choice(stdin, stdout,
                                     f'{phase} {stage}. {faction} has {available} Resources to give.', choices)
            if receiver is None:
                break
            amount = prompt_amount(stdin, stdout, f'Give how many to {receiver}?',
                                   min(available, remaining[receiver]))
            transfers.append(dict(to=receiver, amount=amount))
            available -= amount
            remaining[receiver] -= amount
    return {'transfers': transfers}
