"""Choose actual Hidden/Revealed pieces at March boundaries."""

from fs_bot.cli.menus import prompt_choice
from fs_bot.engine.march_choices import VISIBILITIES, validate_response


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
