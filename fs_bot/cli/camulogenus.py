"""Roman-owned Camulogenus March selection on a detached planning board."""

from fs_bot import rules_consts as rc
from fs_bot.cards.camulogenus import origin_groups, march_routes
from fs_bot.cli.action_windows import inspect_board
from fs_bot.cli.diviciacus import choose_regions, planning_scope
from fs_bot.cli.human_plan import _planning_copy
from fs_bot.cli.menus import prompt_choice
from fs_bot.engine.free_actions import validate_free_action_response


def _group(pool):
    return {rc.LEGION: pool['legions'], rc.AUXILIA: pool['auxilia'],
            rc.LEADER: rc.CAESAR if pool['caesar'] else None}


def _collect_plan(state, faction, request, stdin, stdout):
    planning = _planning_copy(state)
    cooperation = choose_regions(planning, faction, 'command', stdin, stdout)
    destination = prompt_choice(stdin, stdout, 'March and Battle in which Region?',
                                [(r, r) for r in request['destinations']])
    marches = []
    legion_budget = request['legion_limit']
    with planning_scope(planning, faction, cooperation, 'command'):
        # Pools remain the original force, reduced by previous selections.
        # Arrivals must never join a later group from the same Region.
        remaining = origin_groups(planning)
        while True:
            origins = []
            for origin, pool in remaining.items():
                maximum = dict(pool, legions=min(pool['legions'], legion_budget))
                if (any(maximum.values()) and march_routes(
                        planning, origin, _group(maximum), destination)):
                    origins.append(origin)
            options = [(r, r) for r in sorted(origins)]
            options.append(('Finish March selection; continue to Battle', None))
            origin = prompt_choice(stdin, stdout,
                f'Select the next March origin ({legion_budget} Legions remaining in the limit):',
                options)
            if origin is None:
                break
            pool = remaining[origin]
            legions = prompt_choice(stdin, stdout, 'How many Legions in this group?',
                [(f'{n} Legions', n) for n in range(min(pool['legions'], legion_budget) + 1)])
            auxilia = prompt_choice(stdin, stdout, 'How many Auxilia in this group?',
                [(f'{n} Auxilia', n) for n in range(pool['auxilia'] + 1)])
            caesar = (prompt_choice(stdin, stdout, 'Does Caesar accompany this group?',
                                   [('Leave Caesar here', False), ('March Caesar', True)])
                      if pool['caesar'] else False)
            group = _group({'legions': legions, 'auxilia': auxilia, 'caesar': caesar})
            if not (legions or auxilia or caesar):
                stdout.write('Select at least one piece for a moving group.\n')
                continue
            routes = march_routes(planning, origin, group, destination)
            if not routes:
                stdout.write('That group cannot reach the selected destination. Choose another group.\n')
                continue
            route = prompt_choice(stdin, stdout, 'Which route? No pieces may be dropped off.',
                [(' → '.join([origin, *path]), path) for path in routes])
            marches.append({'origin': origin, 'route': route, 'legions': legions,
                            'auxilia': auxilia, 'caesar': caesar})
            pool['legions'] -= legions
            pool['auxilia'] -= auxilia
            pool['caesar'] = pool['caesar'] and not caesar
            legion_budget -= legions
    response = {'destination': destination, 'marches': marches}
    if cooperation is not None:
        # A preliminary loan selection is relevant only where this Command
        # actually forms a group. Do not seek consent for an unused origin.
        used_origins = {entry['origin'] for entry in marches}
        response['diviciacus_regions'] = [r for r in cooperation if r in used_origins]
    return response


def collect_march(state, faction, request, stdin, stdout):
    """Collect exact groups without moving counters or consuming live RNG."""
    if request.get('previous_error'):
        stdout.write(request['previous_error'] + '\n')
    with inspect_board(state, stdout):
        while True:
            options = [('Choose destination and March groups', 'plan')]
            if request.get('default_available'):
                options.append(('Use bot default', 'default'))
            mode = prompt_choice(stdin, stdout,
                'Romans: choose the Camulogenus March. Only selected moving pieces flip.',
                options)
            response = ({'use_default': True} if mode == 'default'
                        else _collect_plan(state, faction, request, stdin, stdout))
            error = validate_free_action_response(state, faction, request, response)
            if error:
                stdout.write(f'Cannot use this March: {error}\n')
                continue
            return response
