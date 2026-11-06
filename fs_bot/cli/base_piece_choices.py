"""Live Event quantities and physical selections."""
from fs_bot.cards.base_piece_choices import FIELDS, validate_response
from fs_bot.cli.menus import prompt_choice
from fs_bot.cli.action_windows import inspect_board


def collect_choice(state, faction, request, stdin, stdout):
    card = request['card_id']
    with inspect_board(state, stdout):
        if 'required' in request:
            return validate_response(state, request, _required_removals(request, stdin, stdout))
        if card == 19:
            choice = prompt_choice(stdin, stdout, 'Lucterius: choose one effect:',
                [('Place up to five Roman Auxilia in Provincia', 'auxilia'),
                 ('Remove up to six nearby Arverni Warbands', 'warbands')])
            if choice == 'auxilia':
                count = prompt_choice(stdin, stdout, 'How many Auxilia?',
                    [(str(n), n) for n in range(min(5, request['auxilia_available']) + 1)])
                return validate_response(state, request, {'choice': choice, 'count': count})
        budget = [dict(e) for e in request['available']]
        selected, remaining = [], request['max_count']
        while remaining and any(e['count'] for e in budget):
            index = prompt_choice(stdin, stdout, 'Select pieces (zero total is allowed):',
                [('Finish selections', None)] +
                [(f"{e['region']}: {e['target_faction']} {e['piece_state']} {e['piece_type']} ({e['count']})", i)
                 for i, e in enumerate(budget) if e['count']])
            if index is None: break
            entry = budget[index]
            count = prompt_choice(stdin, stdout, 'How many?',
                [(str(n), n) for n in range(1, min(remaining, entry['count']) + 1)])
            selected.append({k: entry[k] for k in FIELDS} | {'count': count})
            if card == 22:
                selected[-1]['action'] = prompt_choice(stdin, stdout, 'Hostages: remove or replace?',
                    [('Remove only', 'remove'), ('Replace with your own pieces (if Available)', 'replace')])
            entry['count'] -= count
            remaining -= count
        response = ({'choice': 'warbands', 'removals': selected} if card == 19
                    else {'selections': selected})
    return validate_response(state, request, response)


def _required_removals(request, stdin, stdout):
    selected = []
    for kind, remaining in request['required'].items():
        budget = [dict(entry) for entry in request['available'] if entry['piece_type'] == kind]
        while remaining:
            index = prompt_choice(stdin, stdout, f"{request['owner']}: remove {remaining} {kind}:", [
                (f"{entry['region']}: {entry['piece_state'] or kind} ({entry['count']})", index)
                for index, entry in enumerate(budget) if entry['count']
            ])
            entry = budget[index]
            count = prompt_choice(stdin, stdout, 'How many?',
                [(str(n), n) for n in range(1, min(remaining, entry['count']) + 1)])
            selected.append({k: entry[k] for k in FIELDS} | {'count': count})
            entry['count'] -= count
            remaining -= count
    return {'selections': selected}
