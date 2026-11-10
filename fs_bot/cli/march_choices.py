"""Choose actual Hidden/Revealed pieces at March boundaries."""

from fs_bot import rules_consts as rc
from fs_bot.cli.action_windows import inspect_board
from fs_bot.cli.menus import prompt_amount, prompt_choice
from fs_bot.engine.march_choices import VISIBILITIES, validate_dropoffs, validate_response


def collect_march_cohort(state, faction, request, stdin, stdout):
    piece = request["piece_type"]
    owner = request.get("physical_owner", request.get("acting_faction", faction))
    action = "drop off" if request["phase"] == "dropoff" else "March"
    available = request["available"]
    states = [ps for ps in VISIBILITIES if available.get(ps, 0)]
    remaining, counts = request["count"], {}
    stdout.write(f'\n{faction}: choose {remaining} {owner} {piece} to {action} '
                 f'in {request["region"]}.\n')
    for index, ps in enumerate(states):
        minimum = max(0, remaining - sum(available[s] for s in states[index + 1:]))
        maximum = min(remaining, available[ps])
        n = (minimum if minimum == maximum else prompt_choice(
            stdin, stdout, f'How many {ps} {piece}?',
            [(f'{n} {ps} {piece}', n) for n in range(minimum, maximum + 1)]))
        if n:
            counts[ps] = n
        remaining -= n
    response = {"counts": counts}
    return validate_response(request, response)


def collect_dropoffs(state, faction, request, stdin, stdout):
    """Choose exact physical pieces to leave at the current transit Region."""
    choices = {}
    for index, piece in enumerate(request['pieces']):
        label = piece['piece_type']
        if label == rc.LEADER:
            label = request.get('leader', label)
        if piece['piece_state'] is not None:
            label = f"{piece['piece_state']} {label}"
        choices[index] = (f"{piece['faction']} {label}", piece)
    selected = []
    left = request['max_dropoffs']
    with inspect_board(state, stdout):
        while left and choices:
            menu = [('Keep the remaining pieces moving', None)]
            menu.extend((f"Leave {label} (up to {min(left, piece['count'])})", index)
                        for index, (label, piece) in choices.items())
            index = prompt_choice(stdin, stdout,
                                   f"{faction}, drop off pieces in {request['region']} "
                                   f"before Marching to {request['destination']}?", menu)
            if index is None:
                break
            label, piece = choices.pop(index)
            maximum = min(left, piece['count'])
            count = (prompt_amount(stdin, stdout, f"How many {label} to leave?", maximum)
                     if maximum > 1 else 1)
            selected.append(dict(piece, count=count))
            left -= count
    return validate_dropoffs(request, {'dropoffs': selected})
