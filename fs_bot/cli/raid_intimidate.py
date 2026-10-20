"""Human A3.4.3 choice: the Warbands that just Raided may Intimidate."""
from fs_bot.cli.menus import prompt_choice
from fs_bot.engine.raid_intimidate import target_options


def collect_raid_intimidate(state, faction, request, stdin, stdout):
    region = request['region']
    stdout.write(f'\n{faction}: {request["raiders"]} Warband(s) just Raided in {region}. '
                 'With Ariovistus they may also free Intimidate now, without '
                 'revealing another Warband or using your Special Ability.\n')
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
    targets = []
    for _ in range(request['max_removals']):
        options = []
        for index, target in enumerate(remaining):
            if target['available'] <= 0:
                continue
            visibility = f' ({target["target_state"]})' if target['target_state'] else ''
            options.append((f'{target["target_piece"]}{visibility}', index))
        if not options:
            break
        if targets:
            options.append(('Finish with these removals', None))
        index = prompt_choice(stdin, stdout, f'Remove which {chosen} piece?', options)
        if index is None:
            break
        selected = remaining[index]
        selected['available'] -= 1
        targets.append({key: selected[key] for key in
                        ('target_faction', 'target_piece', 'target_state')})
    return {'targets': targets}
