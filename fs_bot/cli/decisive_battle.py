"""A21/A57: choose the Region and defender, then optionally Battle again."""
from fs_bot.cli.menus import prompt_choice


def collect_battle(state, faction, request, stdin, stdout):
    from fs_bot.cards.decisive_battle import legal_defenders, validate_response
    second = request['phase'] == 'second'
    message = (f"{faction}: {request['card_id']} optional second Battle (Retreat allowed)."
               if second else f"{faction}: {request['card_id']} first Battle (No Retreat).")
    if request.get('previous_error'):
        stdout.write(request['previous_error'] + '\n')
    while True:
        menu = [('Choose Region and defender', 'plan')]
        if request['default_available'] or second:
            menu.append(('Use bot default', 'default'))
        if second:
            menu.append(('Decline second Battle', 'decline'))
        choice = prompt_choice(stdin, stdout, message, menu)
        if choice != 'plan':
            response = {'use_default' if choice == 'default' else 'decline': True}
        else:
            choices = legal_defenders(state, faction, request['allowed_regions'])
            region = prompt_choice(stdin, stdout, 'Battle in which Region?',
                                   [(r, r) for r in choices])
            defender = prompt_choice(stdin, stdout, 'Which Faction defends?',
                                     [(f, f) for f in choices[region]])
            response = {'region': region, 'defender': defender}
        error = validate_response(state, faction, request, response)
        if not error:
            return response
        stdout.write(f'Cannot use this Battle: {error}\n')
