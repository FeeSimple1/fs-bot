"""Remi's Gallic owner chooses the optional City replacement on Card 68."""

from fs_bot.cli.action_windows import inspect_board, prepare
from fs_bot.cli.menus import prompt_choice
from fs_bot.engine.free_actions import validate_free_action_response


def collect_params(state, faction, card_id, shaded, stdin, stdout):
    """Wait for the live Remi owner instead of choosing for another seat."""
    if card_id != 68 or not shaded:
        raise ValueError('Only shaded Remi Influence has this owner choice')
    return {}


def _choose(state, stdin, stdout, prompt, choices):
    with inspect_board(state, stdout):
        return prompt_choice(stdin, stdout, prompt, choices)


def _stage(state, owner, params, step, stdin, stdout):
    from fs_bot.cards import remi_event_effect as rules
    from fs_bot.engine.action_windows import scope
    board = rules.preview(state, params, complete=False, stage=step)
    # The Remi owner receives this effect, but only the Event executor may
    # reclaim its own pieces. Arverni retain their independent Spring choice.
    executor = state.get('executing_faction') or owner
    with scope(board, actor=executor, plan=params, force=True):
        board, actions = prepare(board, owner, stdin, stdout,
                                 stage='event_step', step=step)
    if actions:
        params.setdefault('stage_timing_actions', {})[step] = actions
    return board


def collect_response(state, faction, request, stdin, stdout):
    from fs_bot.cards import remi_event_effect as rules
    owner = rules.owner(state)
    if faction != owner or request.get('acting_faction', owner) != owner:
        raise ValueError('Only the Gallic Faction with the Remi Ally chooses this effect')
    while True:
        targets = rules.options(state)['target_cities']
        choices = [('Choose the City', 'choose')] if targets else []
        choices.extend([('Use bot default', 'default'), ('Decline this effect', 'decline')])
        mode = _choose(state, stdin, stdout,
            f'{owner}: choose the optional Remi Influence effect.', choices)
        if mode != 'choose':
            response = {'use_default' if mode == 'default' else 'decline': True}
        else:
            target = _choose(state, stdin, stdout,
                'Replace which City piece or marker with your Citadel and four Warbands (as available)?',
                [(city, city) for city in targets])
            response = {'target_city': target}
            for step in ('68.citadel', '68.warbands'):
                _stage(state, owner, response, step, stdin, stdout)
        error = validate_free_action_response(state, faction, request, response)
        if error:
            stdout.write(f'Cannot use this choice: {error}\n')
            continue
        return response
