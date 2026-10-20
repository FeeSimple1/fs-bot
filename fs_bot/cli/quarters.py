"""Human Quarters relocation and piece-specific payment menus (§6.3/A6.3)."""
from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces
from fs_bot.engine.quarters import (
    validate_quarters_plan, preview_relocations, quartering_inventory,
    quartering_cost, quartering_allocations,
)
from fs_bot.cli.menus import prompt_choice


def collect_quarters_plan(state, faction, request, stdin, stdout):
    for error in request.get('errors', []):
        stdout.write(f'Quarters choice refused: {error}\n')
    pick = prompt_choice(stdin, stdout, f'{faction}: Quarters choices', [
        ('Use the standard Quarters plan', 'standard'),
        ('Choose relocations and payments', 'choose'),
        ('Stay in place (Romans choose payments next)', 'stay'),
    ])
    if pick == 'standard':
        if faction == rc.ROMANS:
            from fs_bot.bots.roman_bot import build_np_winter_relocations
            return build_np_winter_relocations(state)
        return {faction: []}
    moves = []
    if pick == 'choose':
        while True:
            preview = preview_relocations(state, faction, moves)
            candidates = []
            types = ((rc.LEGION, rc.AUXILIA, rc.LEADER) if faction == rc.ROMANS
                     else (rc.WARBAND, rc.LEADER))
            for origin in state['spaces']:
                for piece in types:
                    number = count_pieces(preview, origin, faction, piece)
                    if not number:
                        continue
                    destinations = []
                    for destination in state['spaces']:
                        attempt = moves + [(piece, origin, destination, 1)]
                        if not validate_quarters_plan(state, {faction: attempt}, faction=faction):
                            destinations.append(destination)
                    if destinations:
                        candidates.append((f'{piece} from {origin}', (piece, origin, number, destinations)))
            selected = prompt_choice(stdin, stdout, 'Add a Quarters relocation?',
                                     [('Finish relocations', None)] + candidates)
            if selected is None:
                break
            piece, origin, number, destinations = selected
            destination = prompt_choice(stdin, stdout, 'Destination (other factions must agree):',
                                        [(r, r) for r in destinations])
            counts = [n for n in range(1, number + 1)
                      if not validate_quarters_plan(state, {faction: moves + [(piece, origin, destination, n)]},
                                                    faction=faction)]
            number = prompt_choice(stdin, stdout, 'How many pieces?', [(str(n), n) for n in counts])
            moves.append((piece, origin, destination, number))
            stdout.write(f'Planned: {number} {piece}, {origin} to {destination}.\n')
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
