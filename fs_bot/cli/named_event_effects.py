"""Owner-directed optional Event effects from Cards 2, 18/A18, 23 and 26."""
from fs_bot import rules_consts as rc
from fs_bot.cli.action_windows import inspect_board, prepare
from fs_bot.cli.menus import prompt_choice


def collect_params(state, faction, card_id, shaded, stdin, stdout):
    """Leave the named owner's choices for the live reactive request."""
    from fs_bot.cards import named_event_effects as rules
    if not rules.supported(card_id, shaded):
        raise ValueError('This Event side does not have a named-owner effect')
    return {}


def _choose(state, stdin, stdout, prompt, choices):
    with inspect_board(state, stdout):
        return prompt_choice(stdin, stdout, prompt, choices)


def _save_window(params, step, index, actions):
    if actions:
        key = step if index is None else f'{step}:{index}'
        params.setdefault('stage_timing_actions', {})[key] = actions


def _stage(state, card_id, owner, params, step, index, stdin, stdout):
    from fs_bot.cards import named_event_effects as rules
    from fs_bot.engine.action_windows import scope
    board = rules.preview(state, card_id, params, complete=False)
    # A named beneficiary owns the effect, not the executor's voluntary
    # reclamation permission. Keep that authority even when a raw collector
    # has no enclosing action frame; the beneficiary's Spring choice remains.
    executor = state.get('executing_faction') or owner
    with scope(board, actor=executor, plan=params, force=True):
        board, actions = prepare(board, owner, stdin, stdout,
                                 stage='event_step', step=step, index=index)
    _save_window(params, step, index, actions)
    return board


def _legions(state, owner, stdin, stdout):
    from fs_bot.cards import named_event_effects as rules
    params = {}
    board = _stage(state, 2, owner, params, '2.legions', None, stdin, stdout)
    pools = rules.options(board, 2)
    required = pools['required_legions']
    low = max(0, required - pools['fallen_legions'])
    high = min(required, pools['legions_track'])
    offered_counts = set(range(low, high + 1))
    number = _choose(board, stdin, stdout,
        'Legiones XIIII et XV: how many Legions from the Legions Track?',
        [(str(n), n) for n in range(low, high + 1)])
    params['legions_from_track'] = number
    board = _stage(state, 2, owner, params, '2.fallen_legions', None, stdin, stdout)
    pools = rules.options(board, 2)
    required = min(2, number + pools['legions_track'] + pools['fallen_legions'])
    remaining = min(2 - number, pools['fallen_legions'])
    low = max(number, required - pools['fallen_legions'])
    high = min(required, number + pools['legions_track'])
    revised_counts = set(range(low, high + 1))
    if number + remaining < required or revised_counts - offered_counts:
        # Reclamation at this later window may make another track Legion
        # available, including a newly legal source mix when the previous
        # choice already fulfilled the quota. Keep prior placements/timing
        # and prompt again only for a required or newly available choice.
        number = _choose(board, stdin, stdout,
            'Another Legion is available. Choose the revised number from the Legions Track:',
            [(str(n), n) for n in range(low, high + 1)])
        params['legions_from_track'] = number
        remaining = required - number
    params['legions_from_fallen'] = remaining
    stdout.write(f'Place {number} from the Legions Track and {remaining} from Fallen in Provincia.\n')
    return params


def _allies(state, owner, stdin, stdout):
    from fs_bot.cards import named_event_effects as rules
    params = {'ally_removals': [], 'ally_placements': []}
    for key, option, step, verb in (
            ('ally_removals', 'removable_tribes', '26.removals', 'remove'),
            ('ally_placements', 'placeable_tribes', '26.placements', 'place')):
        while True:
            board = _stage(state, 26, owner, params, step, len(params[key]), stdin, stdout)
            tribes = rules.options(board, 26)[option]
            entries = []
            for tribe in tribes:
                if key == 'ally_removals':
                    faction = board['tribes'][tribe]['allied_faction']
                    label = f'Remove {faction} Ally at {tribe}'
                else:
                    label = f'Place {rc.ARVERNI} Ally at {tribe}'
                entries.append((label, tribe))
            selected = _choose(board, stdin, stdout,
                f'Gobannitio: {verb} an Ally in {rc.ARVERNI_REGION}?',
                [(f'Finish Ally {"removals" if key == "ally_removals" else "placements"}', None), *entries])
            if selected is None:
                break
            params[key].append(selected)
    return params


def collect_response(state, faction, request, stdin, stdout):
    """Collect the named owner's explicit effect, default or decline."""
    from fs_bot.cards import named_event_effects as rules
    card_id = request['card_id']
    owner = rules.owner(card_id)
    if faction != owner or request.get('acting_faction', owner) != owner:
        raise ValueError('Only the named faction chooses this Event effect')
    decline = 'Decline Ally changes and Rally' if card_id == 26 else 'Decline this effect'
    pools = rules.options(state, card_id)
    can_choose = (pools['can_shift'] if card_id == 2 else
                  bool(pools['target_regions']) if card_id in (18, 'A18') else
                  bool(pools['target_cities']) if card_id == 23 else True)
    choices = [('Choose the effect', 'choose')] if can_choose else []
    choices.append(('Use bot default', 'default'))
    if card_id == 26:
        choices.append(('Skip Ally changes; decide Rally', 'skip_changes'))
    choices.append((decline, 'decline'))
    mode = _choose(state, stdin, stdout, f'{owner}: choose the optional Event effect.',
                   choices)
    if mode == 'skip_changes':
        return {'ally_removals': [], 'ally_placements': []}
    if mode != 'choose':
        return {'use_default' if mode == 'default' else 'decline': True}
    if card_id == 2:
        return _legions(state, owner, stdin, stdout)
    if card_id == 26:
        return _allies(state, owner, stdin, stdout)
    key, option, prompt = (
        ('target_region', 'target_regions', 'Rhenus Bridge: remove all Germans from which Region?')
        if card_id in (18, 'A18') else
        ('target_city', 'target_cities', 'Sacking: raze which City for eight Roman Resources?'))
    targets = rules.options(state, card_id)[option]
    if not targets:
        stdout.write('No legal target remains for this effect.\n')
        return {'decline': True}
    target = _choose(state, stdin, stdout, prompt, [(target, target) for target in targets])
    return {key: target}
