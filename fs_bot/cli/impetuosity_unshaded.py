"""Card72: human choice of adjacent marching groups and enemy attacker."""
from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, get_leader_in_region
from fs_bot.cli.menus import prompt_choice, prompt_yes_no


def collect_march(state, faction, request, stdin, stdout):
    from fs_bot.cards.impetuosity_unshaded import origins_by_destination, validate_march, roman_plan, _copy
    while True:
        choices = origins_by_destination(state, faction)
        if not choices:
            stdout.write('No adjacent group can March.\n')
            return {'decline': True}
        menu = [('Plan the action', 'plan')]
        if faction == rc.ROMANS and roman_plan(_copy(state)) is not None:
            menu.append(('Use bot default', 'default'))
        choice = prompt_choice(stdin, stdout,
            f'{faction}: Impetuosity requires a March into one Region from adjacent origins.', menu)
        if choice == 'default':
            return {'use_default': True}
        destination = prompt_choice(stdin, stdout, 'March into which Region?',
                                    [(r, r) for r in sorted(choices)])
        remaining = list(choices[destination])
        groups = []
        while remaining:
            menu = [(r, r) for r in remaining]
            if groups:
                menu.append(('Done selecting origins', None))
            origin = prompt_choice(stdin, stdout, 'March from which adjacent Region?', menu)
            if origin is None:
                break
            group = {}
            for piece in (rc.LEGION, rc.AUXILIA, rc.WARBAND):
                maximum = count_pieces(state, origin, faction, piece)
                if maximum:
                    group[piece] = prompt_choice(stdin, stdout,
                        f'March how many {piece}s from {origin}?',
                        [(str(n), n) for n in range(maximum, -1, -1)])
            if get_leader_in_region(state, origin, faction):
                group[rc.LEADER] = prompt_yes_no(stdin, stdout, f'March the Leader from {origin}?', default=True)
            if not any(group.values()):
                stdout.write('Choose at least one piece from this origin.\n')
                continue
            groups.append({'origin': origin, 'group': group})
            remaining.remove(origin)
        plan = {'destination': destination, 'groups': groups}
        try:
            validate_march(state, faction, plan)
        except ValueError as exc:
            stdout.write(f'Cannot use this plan: {exc}\n')
            continue
        return plan


def collect_attacker(state, faction, request, stdin, stdout):
    attacker = prompt_choice(stdin, stdout,
        f"{faction}: which enemy Battles you in {request['region']}? (No Ambush.)",
        [(enemy, enemy) for enemy in request['attackers']] + [('Use bot default', None)])
    return {'attacker': attacker} if attacker else {'use_default': True}
