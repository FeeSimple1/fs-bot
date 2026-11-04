"""Human A3.4.3 choice: the Warbands that just Raided may Intimidate."""
from fs_bot.cli.menus import prompt_choice
from fs_bot.engine.raid_intimidate import target_options


def collect_raid_intimidate(state, faction, request, stdin, stdout):
    from fs_bot.cli.action_windows import inspect_board
    with inspect_board(state, stdout):
        return _collect_raid_intimidate(state, faction, request, stdin, stdout)


def _collect_raid_intimidate(state, faction, request, stdin, stdout):
    region = request['region']
    stdout.write(f'\n{faction}: {request["raiders"]} Warband(s) just Raided in {region}. '
                 'With Ariovistus they may also free Intimidate now, without '
                 'revealing another Warband or using your Special Ability.\n')
    if request.get('extra_warband_available'):
        stdout.write('Dread also allows one additional Hidden Warband to Reveal '
                     'for one extra removal.\n')
    available = target_options(state, region)
    factions = list(dict.fromkeys(t['target_faction'] for t in available))
    choices = [('Decline free Intimidate', 'decline'),
               ('Use bot default', 'default'),
               ('Place an Intimidated marker only', 'marker')]
    choices += [(f'Remove {owner} pieces and place the marker', owner) for owner in factions]
    chosen = prompt_choice(stdin, stdout, 'Use the raiders to Intimidate?', choices)
    if chosen == 'decline':
        return {'decline': True}
    if chosen == 'default':
        # The engine runs the policy after recording this explicit choice,
        # keeping any policy randomness reproducible on replay.
        return {'use_default': True}
    if chosen == 'marker':
        return {'targets': []}
    remaining = [dict(t) for t in available if t['target_faction'] == chosen]
    extra = False
    if (request.get('extra_warband_available')
            and sum(t['available'] for t in remaining) >= 2):
        extra = prompt_choice(stdin, stdout, 'Reveal an additional Warband with Dread?',
            [('Use only the Warbands that Raided', False),
             ('Reveal one additional Hidden Warband for an extra removal', True)])
    maximum = (request['max_with_extra'] if extra else
               request.get('max_raider_removals', request['max_removals']))
    targets = []
    for _ in range(maximum):
        options = []
        for index, target in enumerate(remaining):
            if target['available'] <= 0:
                continue
            visibility = f' ({target["target_state"]})' if target['target_state'] else ''
            tribe = f' at {target["target_tribe"]}' if 'target_tribe' in target else ''
            options.append((f'{target["target_piece"]}{visibility}{tribe}', index))
        if not options:
            break
        if len(targets) >= (2 if extra else 1):
            options.append(('Finish with these removals', None))
        index = prompt_choice(stdin, stdout, f'Remove which {chosen} piece?', options)
        if index is None:
            break
        selected = remaining[index]
        selected['available'] -= 1
        targets.append({key: selected[key] for key in
                        ('target_faction', 'target_piece', 'target_state', 'target_tribe')
                        if key in selected})
    response = {'targets': targets}
    if extra:
        response['extra_warband'] = True
    return response
