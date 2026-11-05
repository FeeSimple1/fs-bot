"""Roman/Gallic Region choice for Germanic Horse."""
from fs_bot import rules_consts as rc
from fs_bot.cli.menus import prompt_choice
from fs_bot.engine.horse_choice import validate_response


def collect_horse(state, faction, request, stdin, stdout):
    from fs_bot.cli.action_windows import inspect_board
    options = []
    for region in request['legal_regions']:
        detail = (f"{request['auxilia'][region]} Roman Auxilia" if request['side'] == rc.EVENT_UNSHADED
                  else 'doubling currently blocked' if request['blocked'][region]
                  else 'doubling currently available')
        options.append((f"{region}: {detail}; defender {request['defenders'][region]}",
                        {'region': region}))
    if request['may_decline']:
        options.append(('Do not use Germanic Horse this Command', {'decline': True}))
    with inspect_board(state, stdout):
        response = prompt_choice(stdin, stdout,
                                 f'{faction}: choose the Germanic Horse Battle Region', options)
    return validate_response(state, request, response)
