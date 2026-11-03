"""Card 65 shaded's physical targets and remove-or-replace choices."""
from fs_bot import rules_consts as rc
from fs_bot.cards.german_allegiances import (
    apply_entry, planning_copy, required_counts, targets,
)
from fs_bot.cli.action_windows import inspect_board
from fs_bot.cli.menus import prompt_choice


def collect_params(state, faction, stdin, stdout):
    sim = planning_copy(state)
    remaining = required_counts(sim, faction)
    choices = []
    while any(remaining.values()):
        offered = [entry for entry in targets(sim, faction)
                   if remaining[entry['piece_type']]]
        options = [(' / '.join((entry['region'], entry['piece_type'],
                               entry.get('piece_state') or entry.get('tribe'))), entry)
                   for entry in offered]
        with inspect_board(sim, stdout):
            target = prompt_choice(stdin, stdout, 'German Allegiances: choose a German piece.', options)
            replace = prompt_choice(stdin, stdout, 'Remove or replace this piece?', [
                ('Remove only', False), ('Replace with your own piece if legal and Available', True)])
        entry = {key: value for key, value in target.items() if key != 'available'}
        entry['replace'] = replace
        choices.append(entry)
        apply_entry(sim, faction, entry)
        remaining[entry['piece_type']] -= 1
    return {'replacements': choices}
