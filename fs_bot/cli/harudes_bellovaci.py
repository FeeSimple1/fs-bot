"""Explicit A29 Raid and A69 Ambush choices for the Event executor."""
from fs_bot.cli.menus import prompt_choice
from fs_bot.engine.free_actions import validate_free_action_response


def collect_grant(state, faction, request, stdin, stdout):
    if request['request_type'] == 'bellovaci_ambush':
        options = [(enemy, enemy) for enemy in request['defenders']]
        if request.get('default_available', True):
            options.append(('Use bot default', None))
        defender = prompt_choice(stdin, stdout,
            f"{faction}: choose the Belgic Ambush defender at Bellovaci.",
            options)
        return {'use_default': True} if defender is None else {'defender': defender}
    while True:
        choice = prompt_choice(stdin, stdout,
            f'{faction}: choose Raids using the newly placed German Warbands.',
            [('Plan the action', 'plan'), ('Use bot default', 'default')])
        if choice == 'default':
            return {'use_default': True}
        available = dict(request['regions'])
        raids = []
        while available:
            options = [(region, region) for region in sorted(available)]
            if raids:
                options.append(('Done selecting Regions', None))
            region = prompt_choice(stdin, stdout, 'Raid in which Region?', options)
            if region is None:
                break
            scope = available.pop(region)
            count = prompt_choice(stdin, stdout, 'How many newly placed Warbands Raid?',
                [(str(n), n) for n in range(1, scope['max_raiders'] + 1)])
            for index in range(count):
                targets = [(f'Steal from {enemy}', enemy) for enemy in scope['targets']]
                if scope['can_gain']:
                    targets.insert(0, ('Gain one Resource', None))
                target = prompt_choice(stdin, stdout, f'Raider {index + 1}:', targets)
                raids.append({'region': region, 'target_faction': target})
        response = {'raid_actions': raids}
        error = validate_free_action_response(state, faction, request, response)
        if error:
            stdout.write(f'Cannot use this plan: {error}\n')
            continue
        return response
