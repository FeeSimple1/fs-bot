"""Complete human A65 choices, with no bot filtering of legal Regions."""
from fs_bot.cli.menus import prompt_choice
from fs_bot.cards.kinship import validate_response


def collect_kinship(state, faction, request, stdin, stdout):
    choice = prompt_choice(stdin, stdout, f'{faction}: Kinship Battle?', [
        ('Choose the attacker and Regions', 'plan'), ('Use bot default', 'default'),
        ('Decline', 'decline')])
    if choice != 'plan':
        return {'use_default' if choice == 'default' else 'decline': True}
    actors = [actor for actor in request['attackers'] if request['regions_by_faction'][actor]]
    if not actors:
        return {'decline': True}
    actor = prompt_choice(stdin, stdout, 'Which Faction Battles without its Leader?',
                          [(actor, actor) for actor in actors])
    remaining, selected = list(request['regions_by_faction'][actor]), []
    while remaining:
        region = prompt_choice(stdin, stdout, 'Select the next Battle Region:',
                               [(region, region) for region in remaining] + [('Done', None)])
        if region is None:
            break
        selected.append(region)
        remaining.remove(region)
    response = {'faction': actor, 'regions': selected} if selected else {'decline': True}
    error = validate_response(state, response)
    if error:
        raise ValueError(error)
    return response
