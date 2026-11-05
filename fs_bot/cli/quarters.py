"""Human Quarters relocation and piece-specific payment menus (§6.3/A6.3)."""
from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state
from fs_bot.engine.quarters import (
    validate_quarters_plan, preview_relocations, quartering_inventory,
    quartering_cost, quartering_allocations,
)
from fs_bot.cli.menus import prompt_choice


def _entry(piece, origin, destination, count, visibility):
    entry = (piece, origin, destination, count)
    return entry + (visibility,) if visibility is not None else entry


def _label(piece, visibility):
    return piece + (f' ({visibility})' if visibility is not None else '')


def collect_provincia(state, faction, request, stdin, stdout):
    """Rechoose only the still-unresolved Provincia move after Supply changes."""
    for error in request.get('errors', []):
        stdout.write(f'Provincia relocation needs a new choice: {error}\n')
    selection = prompt_choice(stdin, stdout, 'Remaining Provincia relocations?', [
        ('Choose which pieces now move to Provincia', 'choose'),
        ('Keep the original moves that remain legal', 'default'),
        ('Make no further Provincia relocations', 'decline'),
    ])
    if selection != 'choose':
        return {'use_default': True} if selection == 'default' else {'decline': True}
    remaining = []
    for piece, origin, destination, maximum in request['legal_moves']:
        if piece in rc.FLIPPABLE_PIECES:
            for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
                count = min(maximum, count_pieces_by_state(state, origin, faction, piece, visibility))
                if count:
                    remaining.append((piece, origin, destination, count, visibility))
        else:
            remaining.append((piece, origin, destination, maximum, None))
    moves = []
    from fs_bot.engine.quarters import validate_provincia_response, QuartersError
    while remaining:
        options = []
        for index, (piece, origin, destination, maximum, visibility) in enumerate(remaining):
            counts = []
            for count in range(1, maximum + 1):
                try:
                    validate_provincia_response(state, request, {'moves': moves + [
                        _entry(piece, origin, destination, count, visibility)]})
                except QuartersError:
                    continue
                counts.append(count)
            if counts:
                options.append((f'{_label(piece, visibility)} from {origin} (up to {counts[-1]})',
                                (index, counts)))
        if not options:
            break
        selected = prompt_choice(stdin, stdout, 'Add a Provincia relocation?',
                                 [('Finish relocations', None)] + options)
        if selected is None:
            break
        index, counts = selected
        piece, origin, destination, maximum, visibility = remaining.pop(index)
        count = prompt_choice(stdin, stdout, 'How many pieces?', [(str(n), n) for n in counts])
        moves.append(_entry(piece, origin, destination, count, visibility))
    return {'moves': moves}


def collect_payment(state, faction, request, stdin, stdout):
    choice = prompt_choice(stdin, stdout,
        'Provincia relocations changed; choose payments for the pieces now remaining:', [
            ('Choose free quarters and paid pieces', 'choose'),
            ('Use standard payments', 'default'),
        ])
    return ({'use_default': True} if choice == 'default'
            else {'payments': _payments(state, stdin, stdout)})


def collect_quarters_plan(state, faction, request, stdin, stdout):
    for error in request.get('errors', []):
        stdout.write(f'Quarters choice refused: {error}\n')
    pick = prompt_choice(stdin, stdout, f'{faction}: Quarters choices', [
        ('Use the standard Quarters plan', 'standard'),
        ('Choose relocations and payments', 'choose'),
        ('Stay in place (Romans choose payments next)', 'stay'),
    ])
    if pick == 'standard':
        # Record the explicit default choice, then let the engine run the
        # planner. Planning can consume agreement dice; running it inside
        # this menu would omit those draws when replay uses the saved answer.
        return None
    moves = []
    if pick == 'choose':
        while True:
            preview = preview_relocations(state, faction, moves)
            candidates = []
            types = ((rc.LEGION, rc.AUXILIA, rc.LEADER) if faction == rc.ROMANS
                     else (rc.WARBAND, rc.LEADER))
            for origin in state['spaces']:
                for piece in types:
                    states = ((rc.HIDDEN, rc.REVEALED, rc.SCOUTED)
                              if piece in rc.FLIPPABLE_PIECES else (None,))
                    for visibility in states:
                        number = (count_pieces(preview, origin, faction, piece) if visibility is None
                                  else count_pieces_by_state(preview, origin, faction, piece, visibility))
                        if not number:
                            continue
                        destinations = []
                        for destination in state['spaces']:
                            attempt = moves + [_entry(piece, origin, destination, 1, visibility)]
                            if not validate_quarters_plan(state, {faction: attempt}, faction=faction):
                                destinations.append(destination)
                        if destinations:
                            candidates.append((f'{_label(piece, visibility)} from {origin}',
                                               (piece, origin, number, destinations, visibility)))
            selected = prompt_choice(stdin, stdout, 'Add a relocation?', [('Finished relocations', None)] + candidates)
            if selected is None:
                break
            piece, origin, number, destinations, visibility = selected
            destination = prompt_choice(stdin, stdout, 'Destination (other factions must agree):',
                                        [(r, r) for r in destinations])
            counts = [n for n in range(1, number + 1)
                      if not validate_quarters_plan(state, {faction: moves + [
                          _entry(piece, origin, destination, n, visibility)]}, faction=faction)]
            number = prompt_choice(stdin, stdout, 'How many pieces?', [(str(n), n) for n in counts])
            moves.append(_entry(piece, origin, destination, number, visibility))
            stdout.write(f'Planned: {number} {_label(piece, visibility)}, {origin} to {destination}.\n')
    plan = {faction: moves}
    if faction == rc.ROMANS:
        preview = preview_relocations(state, faction, moves)
        plan[rc.ROMANS + '_quartering'] = _payments(preview, stdin, stdout)
    return plan


def _payments(state, stdin, stdout):
    payments = {}
    budget = state['resources'].get(rc.ROMANS, 0)
    for region in state['spaces']:
        if region == rc.PROVINCIA:
            continue
        inventory = {(p, ps): n for p, ps, n in quartering_inventory(state, region) if n}
        if not inventory:
            continue
        cost = quartering_cost(state, region)
        if cost == 0:
            continue
        slots = min(sum(inventory.values()), count_pieces(state, region, rc.ROMANS, rc.ALLY)
                    + count_pieces(state, region, rc.ROMANS, rc.FORT))
        free, paid = [], []
        def label(piece):
            return f'{piece[0]} ({piece[1]})' if piece[1] else piece[0]
        for _ in range(slots):
            piece = prompt_choice(stdin, stdout, f'{region}: choose a piece to Quarter free:',
                                  [(label(p), p) for p, n in inventory.items() if n])
            free.append((*piece, 1))
            inventory[piece] -= 1
        while any(inventory.values()) and budget >= cost:
            selected = prompt_choice(stdin, stdout,
                                     f'{region}: pay {cost} Resources per piece ({budget} remaining):',
                                     [('Roll for all remaining pieces', None)] +
                                     [(f'Pay for {label(p)}', p) for p, n in inventory.items() if n])
            if selected is None:
                break
            paid.append((*selected, 1))
            inventory[selected] -= 1
            budget -= cost
        payments[region] = {'free_pieces': free, 'pay_pieces': paid}
    # Keep the collector and executor on the same typed allocation contract.
    quartering_allocations(state, payments)
    return payments
