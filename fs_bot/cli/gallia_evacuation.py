"""A5 owner order and shared exact Cisalpina allocation menus."""
from fs_bot.cards.gallia_evacuation import (
    apply_allocation, destinations, pieces, planning_copy,
)
from fs_bot.cli.action_windows import inspect_board
from fs_bot.cli.menus import prompt_choice


def collect_evacuation(state, faction, request, stdin, stdout):
    with inspect_board(state, stdout):
        choice = prompt_choice(stdin, stdout, f'{faction}: Gallia Togata evacuation.', [
            ('Choose the evacuation', 'choose'), ('Use bot default', 'default')])
    if choice == 'default':
        return {'use_default': True}
    if request['request_type'] == 'gallia_evacuation_order':
        remaining, order = list(request['owners']), []
        with inspect_board(state, stdout):
            while remaining:
                owner = prompt_choice(stdin, stdout, 'Which owner evacuates next?',
                                      [(owner, owner) for owner in remaining])
                order.append(owner)
                remaining.remove(owner)
        return {'owner_order': order}
    return collect_allocations(state, faction, stdin, stdout)


def collect_allocations(state, faction, stdin, stdout):
    sim, allocations = planning_copy(state), []
    for piece in pieces(sim, faction):
        remaining = piece['count']
        while remaining:
            options = destinations(sim, faction, piece)
            choices = [(slot['destination'] + (f' — {slot["tribe"]}' if 'tribe' in slot else ''), slot)
                       for slot in options]
            choices.append(('Remove from the map', {'destination': None}))
            label = ' '.join(str(value) for value in (
                piece.get('piece_state'), piece.get('leader_name') or piece['piece_type'],
                piece.get('tribe')) if value is not None)
            with inspect_board(sim, stdout):
                slot = prompt_choice(stdin, stdout, f'{label}: {remaining} remaining. Destination?', choices)
                number = 1 if remaining == 1 else prompt_choice(
                    stdin, stdout, 'How many of this exact piece/state?',
                    [(str(number), number) for number in range(1, remaining + 1)])
            allocation = {'piece_id': piece['id'], 'count': number, **slot}
            apply_allocation(sim, faction, piece, allocation)
            allocations.append(allocation)
            remaining -= number
    return {'allocations': allocations}
