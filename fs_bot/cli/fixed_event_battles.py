"""Human Region and defender choices for printed, modified Event Battles."""

from fs_bot.cli.action_windows import inspect_board
from fs_bot.cli.menus import prompt_choice
from fs_bot.engine.free_actions import validate_free_action_response


def collect_battle(state, faction, request, stdin, stdout):
    """Use the Event's legal choices, including Battle without own Forces.

    The engine keeps card modifiers and cooperation authority. The response
    selects only the Region and defender; it cannot add a Special Activity
    or alter the printed Battle exceptions.
    """
    if request.get('previous_error'):
        stdout.write(request['previous_error'] + '\n')
    choices = request['defenders_by_region']
    regions = [region for region in request['allowed_regions']
               if choices.get(region)]
    with inspect_board(state, stdout):
        while True:
            menu = [('Choose Region and defender', 'plan')] if regions else []
            if request.get('default_available'):
                menu.append(('Use bot default', 'default'))
            if request.get('allow_decline'):
                menu.append(('Decline Battle', 'decline'))
            mode = prompt_choice(stdin, stdout,
                                 f'{faction}: choose the Event Battle.', menu)
            if mode == 'plan':
                region = prompt_choice(stdin, stdout, 'Battle in which Region?',
                                       [(region, region) for region in regions])
                defender = prompt_choice(stdin, stdout, 'Which Faction defends?',
                                         [(enemy, enemy) for enemy in choices[region]])
                response = {'region': region, 'defender': defender}
            else:
                response = {'use_default' if mode == 'default' else 'decline': True}
            error = validate_free_action_response(state, faction, request, response)
            if error:
                stdout.write(f'Cannot use this Battle: {error}\n')
                continue
            return response
