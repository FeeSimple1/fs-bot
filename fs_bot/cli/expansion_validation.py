"""Current-board menus for the EXP-09 expansion Event choices."""
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.cli.action_windows import inspect_board, prepare
from fs_bot.cli.menus import prompt_choice


def _label(state, card_id, key, entry):
    """Describe a concrete legal choice instead of independent form fields."""
    from fs_bot.cards.card_effects import _tribe_region
    tribe = entry.get('tribe')
    region = entry.get('region') or _tribe_region(state, tribe)
    if key == 'ally_removals':
        owner = state['tribes'][tribe].get('allied_faction')
        return f'{region}: remove {owner} Ally at {tribe}'
    if key == 'replacements':
        source = tribe or ' '.join(value for value in (
            entry.get('piece_state'), entry.get('from_type')) if value)
        owner = entry['to_faction']
        kind = (rc.ALLY if entry['from_type'] == rc.ALLY else
                rc.AUXILIA if owner == rc.ROMANS else rc.WARBAND)
        return f'{region}: replace {rc.ARVERNI} {source} with {owner} {kind}'
    owner = entry.get('faction', rc.GERMANS if card_id == 'A36' else '')
    kind = entry.get('piece_type', rc.ALLY)
    location = f' at {tribe}' if tribe else ''
    return f'{region}: place {owner} {kind}{location}'


def _finish_label(card_id, key):
    if card_id == 'A36' and key == 'placements':
        return 'Continue to Ally removals'
    if key == 'replacements':
        return 'Finish replacements'
    if key == 'ally_removals':
        return 'Finish Ally removals'
    return 'Finish placements'


def _collect_owned(state, owner, card_id, stdin, stdout):
    from fs_bot.cards import expansion_validation as rules
    params = {'faction': owner} if card_id == 'A29' else {}
    while True:
        stage = rules.preview(state, card_id, owner, params)
        spec = rules.next_choice(stage, card_id, owner, params)
        key, step = spec['key'], spec['step']
        index = len(params.get(key, []))
        stage, actions = prepare(stage, owner, stdin, stdout,
                                 stage='event_step', step=step, index=index)
        # Reclamation can create a legal placement even with an initially
        # empty Available pool. Compute choices only after that boundary.
        spec = rules.next_choice(stage, card_id, owner, params)
        options = spec.get('options', [])
        choices = [(_label(stage, card_id, key, entry), entry) for entry in options]
        if spec.get('may_finish'):
            choices.insert(0, (_finish_label(card_id, key), None))
        if spec.get('done') or (not options and spec.get('may_finish')):
            selected = None
        else:
            with inspect_board(stage, stdout):
                selected = prompt_choice(stdin, stdout,
                    f'{owner}: {card_id}: choose the next piece.', choices)
        if selected is None:
            params.setdefault(key, [])
            if actions:
                params.setdefault('stage_timing_actions', {})[
                    f'{step}:{index}'] = actions
            if card_id == 'A36' and key == 'placements':
                # Presence of this key marks the printed transition from
                # German placements to the subsequent Ally removals.
                params.setdefault('ally_removals', [])
                continue
            return params
        entry = deepcopy(selected)
        if actions:
            entry['timing_actions'] = actions
        params.setdefault(key, []).append(entry)


def collect_params(state, faction, card_id, shaded, stdin, stdout):
    """Collect only choices belonging to this Event executor."""
    from fs_bot.cards import expansion_validation as rules
    if not rules.supported(card_id, shaded):
        raise ValueError('This card side does not use the expansion validation menu')
    if card_id == 'A29':
        with inspect_board(state, stdout):
            owner = prompt_choice(stdin, stdout,
                'Harudes: which Gallic or Roman faction places its pieces?',
                [(owner, owner) for owner in rules.beneficiaries(state)])
        if owner != faction:
            return {'faction': owner}
        return _collect_owned(state, owner, card_id, stdin, stdout)
    if card_id == 'A36' and faction != rc.GERMANS:
        # German choices are requested from that seat on the live board.
        return {}
    if card_id == 'A30':
        with inspect_board(state, stdout):
            region = prompt_choice(stdin, stdout,
                'Orgetorix: remove all Arverni from which Region near Sequani?',
                [(region, region) for region in rules.region_options(state, card_id)])
        return {'region': region}
    return _collect_owned(state, faction, card_id, stdin, stdout)


def collect_response(state, faction, request, stdin, stdout):
    """A named beneficiary supplies its own placement/removal plan."""
    owner, card_id = request.get('acting_faction', faction), request['card_id']
    with inspect_board(state, stdout):
        mode = prompt_choice(stdin, stdout, f'{owner}: choose {card_id} pieces.',
                             [('Choose the pieces', 'choose'),
                              ('Use bot default', 'default')])
    if mode == 'default':
        return {'use_default': True}
    return _collect_owned(state, owner, card_id, stdin, stdout)
