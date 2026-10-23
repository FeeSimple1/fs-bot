"""Human A17 group and route selection, without moving or rolling pieces."""
from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces
from fs_bot.cards.publius import march_origins, march_routes
from fs_bot.cli.menus import prompt_choice


def collect_publius_march(state, faction, request, stdin, stdout):
    while True:
        choice = prompt_choice(stdin, stdout,
            'Romans: Publius permits one group of 1–4 Legions and 1–8 Auxilia to March, then Battle.',
            [('Plan the action', 'plan'), ('Use bot default', 'default'), ('Decline', 'decline')])
        if choice != 'plan':
            return {'use_default' if choice == 'default' else 'decline': True}
        origins = [r for r in march_origins(state) if march_routes(state, r, 1, 1)]
        if not origins:
            stdout.write('No eligible group can reach a Region without Caesar.\n')
            continue
        origin = prompt_choice(stdin, stdout, 'March from which Region?', [(r, r) for r in origins])
        legions = prompt_choice(stdin, stdout, 'How many Legions?',
            [(str(n), n) for n in range(1, min(4, count_pieces(state, origin, rc.ROMANS, rc.LEGION)) + 1)])
        auxilia = prompt_choice(stdin, stdout, 'How many Auxilia?',
            [(str(n), n) for n in range(1, min(8, count_pieces(state, origin, rc.ROMANS, rc.AUXILIA)) + 1)])
        routes = march_routes(state, origin, legions, auxilia)
        route = prompt_choice(stdin, stdout, 'Which route (ending without Caesar)?',
            [(' → '.join([origin, *path]) if path else f'{origin} (stay)', path) for path in routes])
        response = {'origin': origin, 'route': route, 'legions': legions, 'auxilia': auxilia}
        remaining = {rc.LEGION: legions, rc.AUXILIA: auxilia}
        drops = {}
        for region in route[:-1]:
            drop = {}
            for piece in (rc.LEGION, rc.AUXILIA):
                maximum = min(remaining[piece], sum(remaining.values()) - 1)
                n = prompt_choice(stdin, stdout, f'How many {piece} stay in {region}?',
                                  [(f'{n} {piece}', n) for n in range(maximum + 1)])
                remaining[piece] -= n
                if n:
                    drop[piece] = n
            if drop:
                drops[region] = drop
        if drops:
            response['dropoffs'] = drops
        return response
