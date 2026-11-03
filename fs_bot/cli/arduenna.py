"""Executor-owned beneficiary; ordinary scoped menus collect the later actions."""
from fs_bot.cli.menus import prompt_choice


def collect_faction(state, faction, request, stdin, stdout):
    if request['request_type'] == 'arduenna_accept':
        selected = prompt_choice(stdin, stdout,
            f'{faction}: accept the complete March, Command, then Hide sequence?',
            [('Accept', True), ('Decline', False), ('Use bot default', None)])
        return ({'use_default': True} if selected is None else
                {'accept': True} if selected else {'decline': True})
    selected = prompt_choice(stdin, stdout,
        f'{faction}: which Faction receives the Arduenna actions?',
        [(f, f) for f in request['factions']]
        + [('Use bot default', None), ('Decline', False)])
    if selected is None or selected is False:
        return {'use_default' if selected is None else 'decline': True}
    return {'faction': selected}
