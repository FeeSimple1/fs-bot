"""Source-bounded human menus for original Events 40, 41, 42 and 51."""
from collections import Counter

from fs_bot import rules_consts as rc
from fs_bot.cards import base_event_limits as limits
from fs_bot.cards.card_effects import _tribe_piece_type, _tribe_region
from fs_bot.cards.event_preview import preview_event_prefix
from fs_bot.cli.action_windows import planning_copy, prepare, inspect_board
from fs_bot.board.pieces import count_pieces, get_available


def collect_params(state, faction, card, shaded, stdin, stdout):
    from fs_bot.cli import human_plan
    from fs_bot.cards.boii import eligible_allies
    original = planning_copy(state)
    params = {}

    def choose(board, prompt, choices):
        with inspect_board(board, stdout):
            return human_plan.prompt_choice(stdin, stdout, prompt, choices)

    def stage(step, index=None):
        board = preview_event_prefix(original, faction, card, shaded, params,
                                     step=step, index=index)
        return prepare(board, faction, stdin, stdout, stage='event_step', step=step, index=index)

    def save_tail(step, index, actions):
        if actions:
            key = step if index is None else f'{step}:{index}'
            params.setdefault('stage_timing_actions', {})[key] = actions

    if card == 40:
        params['placements'] = []
        totals, kinds = Counter(), {}
        while True:
            regions = [r for r in limits.adjacent_cisalpina(original)
                       if totals[r] < {rc.WARBAND: 3, rc.AUXILIA: 2, rc.ALLY: 1}.get(kinds.get(r), 3)]
            if not regions or not human_plan.prompt_yes_no(
                    stdin, stdout, 'Add a placements entry?', default=not params['placements']):
                break
            index = len(params['placements'])
            board, actions = stage('40.placements', index)
            region = choose(board, '  region:', [(r, r) for r in regions])
            types = [kinds[region]] if region in kinds else [rc.WARBAND, rc.AUXILIA, rc.ALLY]
            types = [kind for kind in types if kind != rc.ALLY or any(
                eligible_allies(board, [region], owner) for owner in rc.FACTIONS)]
            kind = choose(board, '  piece_type:', [(v, v) for v in types])
            cap = {rc.WARBAND: 3, rc.AUXILIA: 2, rc.ALLY: 1}[kind]
            count = choose(board, '  count:', [(str(n), n) for n in range(1, cap - totals[region] + 1)])
            owners = [rc.ROMANS] if kind == rc.AUXILIA else [f for f in rc.FACTIONS
                if (kind != rc.WARBAND or f != rc.ROMANS)
                and region in limits.get_playable_regions_for_state(board, f)
                and (kind != rc.ALLY or eligible_allies(board, [region], f))]
            if not owners:
                stdout.write('No legal owner has a Tribe destination there.\n')
                save_tail('40.placements', index, actions)
                continue
            owner = choose(board, '  faction:', [(f, f) for f in owners])
            entry = {'region': region, 'piece_type': kind, 'count': count, 'faction': owner}
            if kind == rc.ALLY:
                entry['tribe'] = choose(board, '  tribe:', [(t, t) for t in eligible_allies(board, [region], owner)])
            if actions:
                entry['timing_actions'] = actions
            params['placements'].append(entry)
            totals[region] += count
            kinds[region] = kind
        return params

    if card == 41:
        if not limits.owns_avaricum(original, faction):
            stdout.write('Avaricum is not your Ally or Citadel.\n')
            return {}
        params['ally_placements'] = []
        regions = limits.avaricum_regions(original)
        for index in range(2):
            board, actions = stage('41.allies', index)
            targets = eligible_allies(board, regions, faction)
            tribe = choose(board, 'Avaricum: place an Ally?', [('Finish Ally placements', None)] + [(t, t) for t in targets])
            if tribe is None:
                save_tail('41.allies', index, actions)
                break
            entry = {'tribe': tribe}
            if actions:
                entry['timing_actions'] = actions
            params['ally_placements'].append(entry)
        board, actions = stage('41.citadel')
        save_tail('41.citadel', None, actions)
        targets = [t for t in board['tribes'] if _tribe_region(board, t) in regions
                   and board['tribes'].get(t, {}).get('allied_faction') == faction
                   and _tribe_piece_type(board, t) == rc.ALLY]
        if targets:
            stdout.write('Replacement removes the Ally if a Citadel is unavailable or cannot stack at its Tribe.\n')
            target = choose(board, 'Avaricum: replace an Ally with a Citadel?', [('Skip', None)] + [(t, t) for t in targets])
            if target is not None:
                params['citadel_upgrade_tribe'] = target
        board, actions = stage('41.fort')
        save_tail('41.fort', None, actions)
        if faction == rc.ROMANS:
            targets = [r for r in regions if not count_pieces(board, r, rc.ROMANS, rc.FORT)]
            target = choose(board, 'Avaricum: place a Fort?', [('Skip', None)] + [(r, r) for r in targets])
            if target is not None:
                params['fort_region'] = target
        return params

    if card == 42:
        scopes = limits.wine_regions(original, shaded)
        mode = 'supply' if shaded else choose(original, 'Roman Wine: removal area?',
            [('Up to four under Roman Control', 'controlled'), ('Up to two adjacent to Roman Control', 'adjacent')])
        if not shaded:
            params['mode'] = mode
        params['removals'] = []
        maximum = 3 if shaded else (4 if mode == 'controlled' else 2)
        for index in range(maximum):
            board, actions = stage('42.removals', index)
            targets = limits.wine_targets(board, scopes[mode], shaded)
            choices = [(f'{t} ({_tribe_region(board, t)})', t) for t in targets]
            if not shaded or params['removals'] or not targets:
                choices.insert(0, ('Finish removals', None))
            target = choose(board, 'Roman Wine: remove which Ally?', choices)
            if target is None:
                save_tail('42.removals', index, actions)
                break
            entry = {'tribe': target}
            if actions:
                entry['timing_actions'] = actions
            params['removals'].append(entry)
        return params

    if card == 51:
        from fs_bot.board.pieces import count_pieces_by_state
        params['region'] = choose(original, 'Surus: select one Region?', [(r, r) for r in limits.surus_regions(original)])
        params['replacements'] = []
        region = params['region']
        budget = {(f, v): count_pieces_by_state(original, region, f, rc.WARBAND, v)
                  for f in (*rc.GALLIC_FACTIONS, rc.GERMANS) for v in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)}
        required, selected = min(4, sum(budget.values())), Counter()
        while sum(selected.values()) < required:
            index = len(params['replacements'])
            board, actions = stage('51.replacements', index)
            candidates = [cell for cell, number in budget.items() if selected[cell] < number]
            owner, visibility = choose(board, 'Surus: replace which original Warband?',
                [(f'{f} {v} Warband', (f, v)) for f, v in candidates])
            maximum = min(required - sum(selected.values()), budget[(owner, visibility)] - selected[(owner, visibility)])
            count = choose(board, 'Surus: how many?', [(str(n), n) for n in range(1, maximum + 1)])
            entry = {'from_faction': owner, 'piece_state': visibility, 'count': count}
            if actions:
                entry['timing_actions'] = actions
            params['replacements'].append(entry)
            selected[(owner, visibility)] += count
        return params
    raise ValueError('Unsupported base Event menu')
