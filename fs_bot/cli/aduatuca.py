"""Executor-owned quantities for numeric58's German March to a Fort."""
from fs_bot.cli.action_windows import inspect_board
from fs_bot.cli.menus import prompt_choice
from fs_bot.engine.free_actions import validate_free_action_response


def collect_march(state, faction, request, stdin, stdout):
    with inspect_board(state, stdout):
        while True:
            mode = prompt_choice(stdin, stdout, 'Aduatuca: choose German Marches and the Fort.',
                [('Choose destination and groups', 'plan'), ('Use bot default', 'default')])
            if mode == 'default':
                return {'use_default': True}
            destination = prompt_choice(stdin, stdout, 'Which Roman Fort Region?',
                                        [(r, r) for r in request['destinations']])
            remaining = dict(request['origins_by_destination'][destination])
            marches = []
            while remaining:
                origin = prompt_choice(stdin, stdout, 'Select next German March origin:',
                    [(r, r) for r in remaining] + [('Finish Marches; Ambush Romans there', None)])
                if origin is None:
                    break
                n = remaining.pop(origin)
                count = prompt_choice(stdin, stdout, 'How many German Warbands move?',
                    [('0 (select origin for hiding only)', 0)] + [(f'{i} Warbands', i) for i in range(1, n + 1)])
                marches.append({'origin': origin, 'warbands': count})
            response = {'destination': destination, 'marches': marches}
            error = validate_free_action_response(state, faction, request, response)
            if error:
                stdout.write(f'Cannot use this March: {error}\n')
                continue
            return response
