"""A66's held-card activation window and exact physical placements."""
from fs_bot.cli.menus import prompt_choice


def collect_timing(state, faction, request, stdin, stdout):
    stdout.write(f'\n{request["card_text"]}\n{faction} holds Winter Uprising in {request["region"]}.\n')
    choice = prompt_choice(stdin, stdout, 'Activate Winter Uprising after this Quarters Phase?', [
        ('Activate now', True), ('Keep the card and marker for a later Quarters Phase', False),
        ('Use bot default (activate now)', None)])
    return {'use_default': True} if choice is None else {'activate': choice}


def collect_placement(state, faction, request, stdin, stdout):
    from fs_bot.cards.card_effects import _tribe_region
    stdout.write(f'\n{request["card_text"]}\n{faction}: place {request["allies"]} '
                 f'{request["beneficiary"]} Allies and {request["warbands"]} Warbands '
                 f'within one Region of {request["region"]}.\n')
    if request['forced']:
        stdout.write('The Gallic War Interlude requires this Event now.\n')
    mode = prompt_choice(stdin, stdout, 'Winter Uprising placements?', [
        ('Choose the pieces and Regions', 'choose'), ('Use bot default', 'default')])
    if mode == 'default':
        return {'use_default': True}
    allies = []
    for number in range(request['allies']):
        tribes = [tribe for tribe in request['tribes'] if tribe not in allies]
        allies.append(prompt_choice(stdin, stdout, f'Place Ally {number + 1} of {request["allies"]}:',
                                    [(f'{tribe} ({_tribe_region(state, tribe)})', tribe) for tribe in tribes]))
    warbands, remaining = [], request['warbands']
    while remaining:
        region = prompt_choice(stdin, stdout, f'Place Warbands ({remaining} remaining) in which Region?',
                               [(region, region) for region in request['regions']])
        count = prompt_choice(stdin, stdout, f'How many Warbands in {region}?',
                              [(str(count), count) for count in range(1, remaining + 1)])
        existing = next((entry for entry in warbands if entry['region'] == region), None)
        if existing:
            existing['count'] += count
        else:
            warbands.append({'region': region, 'count': count})
        remaining -= count
    return {'allies': allies, 'warbands': warbands}
