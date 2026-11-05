"""Owner's optional Ballistae removal after Ambush."""
from fs_bot.cli.menus import prompt_choice
from fs_bot.engine.ballistae_choice import validate_response


def collect_ballistae(state, faction, request, stdin, stdout):
    from fs_bot.cli.action_windows import inspect_board
    options = [(f"Remove {target['owner']} {target['piece_type']}"
                + (f" at {target['tribe']}" if target['tribe'] else ''),
                {'target': target}) for target in request['targets']]
    options.append(('Do not remove a piece with Ballistae', {'decline': True}))
    with inspect_board(state, stdout):
        response = prompt_choice(stdin, stdout,
            f"{faction}: Ballistae after Ambush in {request['region']}?", options)
    return validate_response(state, request, response)
