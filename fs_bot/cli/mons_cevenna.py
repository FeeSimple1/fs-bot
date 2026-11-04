"""Exact one-edge Mons Cevenna March selection on a detached board."""
from fs_bot import rules_consts as rc
from fs_bot.cards import mons_cevenna as card
from fs_bot.cli.action_windows import inspect_board
from fs_bot.cli.diviciacus import choose_regions, planning_scope
from fs_bot.cli.human_plan import _planning_copy
from fs_bot.cli.menus import prompt_choice
from fs_bot.engine.free_actions import validate_free_action_response


def collect_march(state, faction, request, stdin, stdout):
    with inspect_board(state, stdout):
        if request.get('previous_error'):
            stdout.write(request['previous_error'] + '\n')
        while True:
            mode = prompt_choice(stdin, stdout, 'Mons Cevenna: choose the first March.',
                                 [('Choose March pieces and destination', 'plan'),
                                  ('Use bot default', 'default')])
            if mode == 'default':
                return {'use_default': True}
            sim = _planning_copy(state)
            sim['_cli_allowed_regions'] = request['allowed_regions']
            cooperation = choose_regions(sim, faction, 'command', stdin, stdout)
            with planning_scope(sim, faction, cooperation, 'command'):
                pools = card.pools(sim, faction)
                origins = [r for r, pool in pools.items()
                           if any(pool.values()) and card.routes(sim, faction, r, pool)]
                if not origins:
                    destination = prompt_choice(stdin, stdout,
                        'No March available. Choose the remaining benefit Region:',
                        [(r, r) for r in request['allowed_regions']])
                    response = {'origin': None, 'destination': destination, 'group': {}}
                else:
                    origin = prompt_choice(stdin, stdout, 'March from which Region?',
                                           [(r, r) for r in origins])
                    pool, group = pools[origin], {}
                    for piece in (rc.LEGION, rc.AUXILIA, rc.WARBAND):
                        if pool[piece]:
                            group[piece] = prompt_choice(stdin, stdout,
                                f'How many {piece} to March?',
                                [(str(n), n) for n in range(pool[piece] + 1)])
                    if pool[rc.LEADER]:
                        group[rc.LEADER] = prompt_choice(stdin, stdout,
                            'March the Leader?', [('Leave here', False), ('March', True)])
                    actual = dict(group, **{rc.LEADER: pool[rc.LEADER] if group.get(rc.LEADER) else None})
                    paths = card.routes(sim, faction, origin, actual) if any(group.values()) else []
                    if not paths:
                        stdout.write('Choose a nonempty group with a legal adjacent destination.\n')
                        continue
                    destination = prompt_choice(stdin, stdout,
                        'March into which adjacent Region?', [(p[0], p[0]) for p in paths])
                    response = {'origin': origin, 'destination': destination, 'group': group}
                    if cooperation:
                        response['diviciacus_regions'] = [r for r in cooperation if r == origin]
            error = validate_free_action_response(state, faction, request, response)
            if error:
                stdout.write(f'Cannot use this March: {error}\n')
                continue
            return response
