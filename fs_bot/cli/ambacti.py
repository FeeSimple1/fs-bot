"""Card 16: choose a placement now, or casualties after seeing the die."""

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import get_available
from fs_bot.cards.ambacti import eligible_regions, placement_limit
from fs_bot.cli.menus import prompt_choice


def collect_params(state, faction, shaded, stdin, stdout):
    if shaded:
        stdout.write('Ambacti: roll the die, then choose 3 or the rolled number of Auxilia to remove.\n')
        return {}
    regions = eligible_regions(state)
    available = get_available(state, rc.ROMANS, rc.AUXILIA)
    if not regions or not available:
        stdout.write('Ambacti: no Auxilia can be placed.\n')
        return {}
    options = []
    for region in regions:
        limit = placement_limit(state, region)
        count = min(limit, available)
        context = ' with Caesar' if limit == 6 else ''
        partial = f' ({limit} allowed; {available} Available)' if count < limit else ''
        options.append((f'{region}: place {count} Auxilia{context}{partial}', region))
    return {'target_region': prompt_choice(stdin, stdout, 'Ambacti placement Region?', options)}


def collect_removal(state, faction, request, stdin, stdout):
    stdout.write(f'\n{faction}: Ambacti die roll: {request["roll"]}.\n')
    counts = request['removal_counts']
    choice = prompt_choice(stdin, stdout, 'Remove the rolled number or three Auxilia?', [
        (f'Rolled number ({request["roll"]}): remove {counts["roll"]} Auxilia', 'roll'),
        (f'Three: remove {counts["three"]} Auxilia', 'three'),
        ('Use bot default', None),
    ])
    if choice is None:
        return {'use_default': True}
    targets = [dict(entry) for entry in request['targets']]
    removals = []
    for index in range(counts[choice]):
        options = [(f'{target["region"]}: {target["piece_state"]} Auxilia '
                    f'({target["available"]} remaining)', offset)
                   for offset, target in enumerate(targets) if target['available']]
        offset = prompt_choice(stdin, stdout,
                               f'Remove Auxilia {index + 1} of {counts[choice]}:', options)
        target = targets[offset]
        target['available'] -= 1
        existing = next((entry for entry in removals
                         if entry['region'] == target['region']
                         and entry['piece_state'] == target['piece_state']), None)
        if existing:
            existing['count'] += 1
        else:
            removals.append({'region': target['region'], 'piece_state': target['piece_state'],
                             'count': 1})
    return {'removal_choice': choice, 'removals': removals}
