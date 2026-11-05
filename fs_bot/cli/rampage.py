"""Let a Rampage target select exact pieces and mixed dispositions."""
from fs_bot.cli.action_windows import inspect_board
from fs_bot.cli.menus import prompt_choice
from fs_bot.engine.rampage_choices import validate_response


def collect_victims(state, faction, request, stdin, stdout):
    remaining, actions, destination = list(request['pieces']), [], None
    count = request['context']['num_pieces']
    stdout.write(f"\n{faction}: choose {count} exact Rampage victims.\n")
    with inspect_board(state, stdout):
        for index in range(count):
            choices = [(f'{piece} ({visibility})' if visibility else piece, slot)
                       for slot, (piece, visibility) in enumerate(remaining)]
            slot = prompt_choice(stdin, stdout, f'Victim {index + 1} of {count}?', choices)
            piece, visibility = remaining.pop(slot)
            options = [('Remove this piece', 'remove')]
            if request['legal_regions']:
                options.append(('Retreat this piece', 'retreat'))
            disposition = prompt_choice(stdin, stdout, 'Remove or Retreat this piece?', options)
            if disposition == 'retreat' and destination is None:
                destination = prompt_choice(stdin, stdout, 'Shared Retreat destination?',
                                            [(region, region) for region in request['legal_regions']])
            actions.append({'action': disposition, 'piece_type': piece, 'piece_state': visibility})
    return validate_response(state, request, {'actions': actions, 'retreat_region': destination})
