"""Council's executor selection and private beneficiary decisions."""
from fs_bot.cards.council import (
    command_request, selection_request, validate_choice, validate_selection,
)
from fs_bot.cli.menus import prompt_choice


def collect_selection(state, faction, request, stdin, stdout):
    candidates = request['regions']
    if not candidates:
        stdout.write('Council: no Region has the required Factions.\n')
        return {}
    region = prompt_choice(stdin, stdout, f'{faction}: Council meeting Region?',
                           [(r, r) for r in candidates])
    selected = []
    while len(selected) < len(candidates[region]):
        options = [(f, f) for f in candidates[region] if f not in selected]
        if len(selected) >= 2:
            options.append(('Done', None))
        choice = prompt_choice(stdin, stdout,
                               'Invite player Factions with pieces here (at least two):', options)
        if choice is None:
            break
        selected.append(choice)
    response = {'region': region, 'target_factions': selected}
    validate_selection(state, response)
    return response


def collect_params(state, faction, stdin, stdout):
    return collect_selection(state, faction, selection_request(state), stdin, stdout)


def collect_choice(state, faction, request, stdin, stdout):
    from fs_bot.cli.human_plan import _collect_command, _planning_copy
    from fs_bot.commands.common import free_action_scope
    from fs_bot.engine.game_engine import ACTION_COMMAND
    stdout.write(f'\n{faction}: private Council look at the next facedown cards:\n')
    cards = request['private_cards']
    for index, card in enumerate(cards, 1):
        stdout.write(f'  {index}. Card {card["card_id"]}: {card["title"]}\n')
        if card['faction_order']:
            stdout.write('  Faction order: ' + ' > '.join(card['faction_order']) + '\n')
        if card['np_symbols']:
            stdout.write('  NP symbols: ' + ', '.join(
                f'{f}: {symbol}' for f, symbol in card['np_symbols'].items()) + '\n')
        if card['is_winter']:
            stdout.write('  Resolve the Winter Round (§6.0).\n')
        if card['has_carnyx_trigger']:
            stdout.write('  Arverni carnyx trigger: check At War (§A2.3.9).\n')
        if card['text']:
            stdout.write(card['text'] + '\n')
    if not cards:
        stdout.write('  No facedown cards remain.\n')
    while True:
        choice = prompt_choice(stdin, stdout, f'{faction}: Council benefit?', [
            ('Free Limited Command anywhere (no Special Ability)', 'command'),
            ('Become Eligible', 'eligible'), ('Decline', 'decline'),
            ('Use bot default', 'default'),
        ])
        if choice != 'command':
            if choice == 'eligible':
                return {'choice': 'eligible'}
            return {'use_default' if choice == 'default' else 'decline': True}
        planning = _planning_copy(state)
        with free_action_scope(planning, faction):
            response = _collect_command(planning, faction, ACTION_COMMAND, stdin, stdout,
                                        allowed_commands=command_request(faction)['allowed_commands'],
                                        max_regions=1)
        if response is None:
            stdout.write('No Command selected. Choose a Council benefit.\n')
            continue
        try:
            validate_choice(state, faction, response)
        except ValueError as exc:
            stdout.write(f'Cannot use this plan: {exc}\n')
            continue
        return response
