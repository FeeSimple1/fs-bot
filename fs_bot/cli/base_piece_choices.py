"""Live Event quantities and physical selections."""
from fs_bot.cards.base_piece_choices import FIELDS, validate_response
from fs_bot.cli.menus import prompt_choice
from fs_bot.cli.action_windows import inspect_board
from fs_bot.rules_consts import AUXILIA


def collect_choice(state, faction, request, stdin, stdout):
    card = request['card_id']
    with inspect_board(state, stdout):
        if card == 31:
            tribe = prompt_choice(stdin, stdout, 'Cotuatus: remove which Allied Tribe?', [
                (f"{row['tribe']} ({row['region']}, {row['target_faction']})", row['tribe'])
                for row in request['targets']
            ])
            return validate_response(state, request, {'tribe': tribe})
        if 'required_by_region' in request:
            amounts = request['required_by_region']
            verb = 'replace' if card == 'A58' else 'remove'
            label = 'Roman pieces' if card == 24 else AUXILIA
            region = prompt_choice(stdin, stdout, f'Choose the single {card} removal Region:', [
                (f'{name} ({count} {label} to {verb})', name) for name, count in amounts.items()
            ])
            available = [row for row in request['available'] if row['region'] == region]
            if card == 24:
                selections = _pick_removals(available, amounts[region], request['owner'], label, stdin, stdout)
                return validate_response(state, request, {'region': region, 'selections': selections})
            target = {'region': region}
            if card == 'A58':
                tribes = request['ally_tribes_by_region'][region]
                target['ally_tribe'] = (prompt_choice(stdin, stdout, 'Choose the Roman Ally:', [
                    (tribe, tribe) for tribe in tribes
                ]) if tribes else None)
            local = dict(request, required={AUXILIA: amounts[region]}, available=available)
            response = {**target, **_required_removals(local, stdin, stdout)}
            return validate_response(state, request, response)
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
        prompt = (f"Select Auxilia to move to {request['destination']} (zero is allowed):" if card == 6
                  else 'Select pieces (zero total is allowed):')
        while remaining and any(e['count'] for e in budget):
            index = prompt_choice(stdin, stdout, prompt,
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
        available = [entry for entry in request['available'] if entry['piece_type'] == kind]
        selected.extend(_pick_removals(available, remaining, request['owner'], kind, stdin, stdout))
    return {'selections': selected}


def _pick_removals(available, remaining, owner, label, stdin, stdout):
    budget = [dict(entry) for entry in available]
    selected = []
    while remaining:
        index = prompt_choice(stdin, stdout, f'{owner}: remove {remaining} {label}:', [
            (f"{entry['region']}: {entry['piece_state'] or ''} {entry['piece_type']} ({entry['count']})", index)
            for index, entry in enumerate(budget) if entry['count']
        ])
        entry = budget[index]
        count = prompt_choice(stdin, stdout, 'How many?',
            [(str(n), n) for n in range(1, min(remaining, entry['count']) + 1)])
        selected.append(dict(entry, count=count))
        entry['count'] -= count
        remaining -= count
    return selected
