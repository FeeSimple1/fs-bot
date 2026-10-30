"""Special Activity choices on the current detached board at each step."""

from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import PieceError, count_pieces, count_pieces_by_state
from fs_bot.cli.action_windows import inspect_board, planning_copy, prepare
from fs_bot.cli.menus import prompt_choice
from fs_bot.commands.common import CommandError


class Planning:
    def __init__(self, state, faction, stdin, stdout):
        self.state = planning_copy(state)
        self.faction, self.stdin, self.stdout = faction, stdin, stdout
        self.pending, self.stages = [], {}

    def before(self, stage, index):
        self.state, choices = prepare(self.state, self.faction, self.stdin, self.stdout,
                                      stage=stage, index=index)
        self.pending.extend(choices)

    def choose(self, prompt, choices):
        with inspect_board(self.state, self.stdout):
            return prompt_choice(self.stdin, self.stdout, prompt, choices)

    def entry(self, entry):
        if self.pending:
            entry['timing_actions'] = self.pending
            self.pending = []
        return entry

    def scalar(self, stage, index):
        if self.pending:
            self.stages[f'{stage}:{index}'] = self.pending
            self.pending = []

    def extra(self):
        details = {}
        if self.stages:
            details['stage_timing_actions'] = self.stages
        if self.pending:
            details['after_sa_timing_actions'] = self.pending
        return {'sa_details': details} if details else {}


def _legal(board, execute, *args):
    try:
        execute(planning_copy(board), *args)
    except (CommandError, PieceError):
        return False
    return True


def collect_scalar(state, faction, sa, stdin, stdout):
    """Devastate/Settle reserve their shared pools and retain every timing choice."""
    from fs_bot.cli.human_plan import _playable_regions
    if sa == rc.SA_DEVASTATE:
        from fs_bot.commands.sa_devastate import validate_devastate_region, devastate_region
        validate, execute, stage = validate_devastate_region, devastate_region, 'devastate_region'
    else:
        from fs_bot.commands.sa_settle import validate_settle_region, settle
        validate, execute, stage = validate_settle_region, settle, 'settle_region'
    plan = Planning(state, faction, stdin, stdout)
    selected = []
    while True:
        plan.before(stage, len(selected))
        candidates = [region for region in _playable_regions(plan.state, faction)
                      if region not in selected and validate(plan.state, region)[0]
                      and _legal(plan.state, execute, region)]
        if not candidates:
            break
        region = plan.choose(f'{sa} in which Region? (in resolution order)',
                             [(r, r) for r in candidates] + [('(done)', None)])
        if region is None:
            break
        plan.scalar(stage, len(selected))
        execute(plan.state, region)
        selected.append(region)
    return selected, plan.extra()


def _entreat_options(state, region):
    from fs_bot.cli.human_plan import _enemy_ally_tribes
    from fs_bot.commands.sa_entreat import entreat_replace_ally, entreat_replace_piece
    options = []
    for tribe, owner in _enemy_ally_tribes(state, region, rc.ARVERNI):
        if (tribe in rc.TRIBE_TO_CITY
                and count_pieces(state, region, owner, rc.CITADEL)):
            continue
        if _legal(state, entreat_replace_ally, region, owner, tribe):
            options.append((f'replace {owner} Ally at {tribe} with yours', {
                'region': region, 'action': 'replace_ally', 'target_faction': owner, 'tribe': tribe}))
    for owner in rc.FACTIONS:
        if owner == rc.ARVERNI:
            continue
        for piece in (rc.WARBAND, rc.AUXILIA):
            for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
                if (count_pieces_by_state(state, region, owner, piece, visibility)
                        and _legal(state, entreat_replace_piece, region, owner, piece, visibility)):
                    options.append((f'replace a {owner} {piece} ({visibility}) with your Warband', {
                        'region': region, 'action': 'replace_piece', 'target_faction': owner,
                        'piece_type': piece, 'target_state': visibility}))
    return options


def collect_entreat(state, faction, stdin, stdout):
    from fs_bot.cli.human_plan import _playable_regions
    from fs_bot.commands.sa_entreat import (
        validate_entreat_region, entreat_replace_ally, entreat_replace_piece)
    plan = Planning(state, faction, stdin, stdout)
    entries, selected = [], set()
    while True:
        plan.before('entreat_operation', len(entries))
        choices = {region: _entreat_options(plan.state, region)
                   for region in _playable_regions(plan.state, faction)
                   if region not in selected and validate_entreat_region(plan.state, region)[0]}
        choices = {region: options for region, options in choices.items() if options}
        if not choices:
            break
        region = plan.choose('Entreat in which Region?',
                             [(r, r) for r in choices] + [('(done)', None)])
        if region is None:
            break
        entry = plan.choose(f'Entreat action in {region}:',
                            choices[region] + [('(cancel this Region)', None)])
        if entry is None:
            continue
        if entry['action'] == 'replace_ally':
            entreat_replace_ally(plan.state, region, entry['target_faction'], entry['tribe'])
        else:
            entreat_replace_piece(plan.state, region, entry['target_faction'],
                                  entry['piece_type'], entry['target_state'])
        entries.append(plan.entry(entry))
        selected.add(region)
    return entries, plan.extra()


def _suborn_label(operation):
    target = operation.get('tribe') or operation.get('piece_state')
    return ' '.join(str(part) for part in (
        operation['action'], operation['faction'], operation['piece_type'], target) if part)


def collect_suborn(state, faction, stdin, stdout):
    """Keep each operation's authored choices with its exact native counter."""
    from fs_bot.cli.human_plan import _playable_regions
    from fs_bot.commands.sa_suborn import (
        legal_suborn_operations, suborn_limits, suborn_region_limit,
        suborn_preview, validate_suborn_region)
    plan = Planning(state, faction, stdin, stdout)
    regions, entries = [], []
    maximum = suborn_region_limit(plan.state)
    max_pieces, max_allies = suborn_limits(plan.state)
    while len(entries) < maximum:
        before_region = planning_copy(plan.state)
        plan.before('suborn_region', len(entries))
        candidates = [region for region in _playable_regions(plan.state, faction)
                      if region not in regions and validate_suborn_region(plan.state, region)[0]]
        if not candidates:
            break
        region = plan.choose('Suborn in which Region?',
                             [(r, r) for r in candidates] + [('(done)', None)])
        if region is None:
            break
        entry = plan.entry({'region': region, 'actions': []})
        snapshots, cancelled = [], False
        while len(entry['actions']) < max_pieces:
            before_option = planning_copy(plan.state)
            plan.before('suborn_operation', len(entry['actions']))
            ally_count = sum(op['piece_type'] == rc.ALLY for op in entry['actions'])
            options = [op for op in legal_suborn_operations(plan.state, region)
                       if op['piece_type'] != rc.ALLY or ally_count < max_allies]
            menu = [(_suborn_label(op), op) for op in options] + [('(done)', None)]
            if entry['actions']:
                menu.append(('(undo last operation and its timing choices)', 'undo'))
            menu.append(('(cancel this Region and its timing choices)', 'cancel'))
            selected = plan.choose(
                f'Suborn action {len(entry["actions"]) + 1} of up to {max_pieces}:', menu)
            if selected == 'cancel':
                plan.state, plan.pending, cancelled = before_region, [], True
                break
            if selected == 'undo':
                entry['actions'].pop()
                plan.state, plan.pending = snapshots.pop(), []
                continue
            if selected is None:
                break
            # Timing has already changed this preview. Store it on the
            # operation for execution, but do not apply it twice here.
            current = deepcopy(selected)
            plan.state, _ = suborn_preview(plan.state, region, [current])
            entry['actions'].append(plan.entry(current))
            snapshots.append(before_option)
        if cancelled:
            continue
        if not entry['actions']:
            # Region selection was never executed. Carry its choices into
            # the SA tail rather than silently lose them on an empty plan.
            plan.pending = entry.get('timing_actions', []) + plan.pending
            break
        regions.append(region)
        entries.append(entry)
    if not plan.pending:
        plan.before('special_ability_complete', 0)
    extra = plan.extra()
    extra['suborn_plan'] = entries
    return regions, extra


def _intimidate_removals(state, region, target, prior):
    from fs_bot.commands.sa_intimidate import intimidate
    options = []
    for piece in (rc.WARBAND, rc.AUXILIA, rc.ALLY):
        for visibility in ((None,) if piece == rc.ALLY else (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)):
            removal = (piece, visibility)
            if _legal(state, intimidate, region, len(prior) + 1, target, prior + [removal]):
                options.append((' '.join(p for p in (piece, visibility) if p), removal))
    return options


def collect_intimidate(state, faction, stdin, stdout):
    from fs_bot.cli.human_plan import _playable_regions
    from fs_bot.commands.sa_intimidate import intimidate, validate_intimidate_region
    plan = Planning(state, faction, stdin, stdout)
    regions, entries = [], []
    while True:
        plan.before('intimidate_region', len(regions))
        candidates = [region for region in _playable_regions(plan.state, faction)
                      if region not in regions and validate_intimidate_region(plan.state, region)[0]
                      and count_pieces_by_state(plan.state, region, rc.GERMANS, rc.WARBAND, rc.HIDDEN)]
        if not candidates:
            break
        region = plan.choose('Intimidate in which Region?',
                             [(r, r) for r in candidates] + [('(done)', None)])
        if region is None:
            break
        targets = [owner for owner in rc.FACTIONS if owner != faction
                   and _intimidate_removals(plan.state, region, owner, [])]
        target = plan.choose(f'Intimidate which Faction in {region}?',
            [(owner, owner) for owner in targets] + [('Place an Intimidated marker only', None)])
        removals = []
        if target is not None:
            limit = min(2, count_pieces_by_state(plan.state, region, rc.GERMANS, rc.WARBAND, rc.HIDDEN))
            while len(removals) < limit:
                options = _intimidate_removals(plan.state, region, target, removals)
                if not options:
                    break
                selected = plan.choose(f'Remove which {target} piece in {region}?',
                                       options + [('(stop here)', None)])
                if selected is None:
                    break
                removals.append(selected)
            if not removals:
                continue
        intimidate(plan.state, region, len(removals) or 1, target, removals)
        current = [{'region': region, 'target_faction': target,
                    'target_piece': piece, 'target_state': visibility}
                   for piece, visibility in removals or [(None, None)]]
        current[0] = plan.entry(current[0])
        entries.extend(current)
        regions.append(region)
    extra = plan.extra()
    extra['intimidate_plan'] = entries
    return regions, extra


def collect_rampage(state, faction, stdin, stdout):
    from fs_bot.cli.human_plan import _playable_regions
    from fs_bot.commands.sa_rampage import validate_rampage_region, validate_rampage_target
    from fs_bot.engine.execute import _execute_rampage
    plan = Planning(state, faction, stdin, stdout)
    entries, selected = [], set()
    while True:
        plan.before('rampage_target', len(entries))
        choices = {}
        for region in _playable_regions(plan.state, faction):
            if region in selected or not validate_rampage_region(plan.state, region)[0]:
                continue
            targets = [owner for owner in rc.FACTIONS
                       if validate_rampage_target(plan.state, region, owner)[0]
                       and any(count_pieces(plan.state, region, owner, piece)
                               for piece in (rc.WARBAND, rc.AUXILIA, rc.LEGION))]
            if targets:
                choices[region] = targets
        if not choices:
            break
        region = plan.choose('Rampage in which Region?',
                             [(r, r) for r in choices] + [('(done)', None)])
        if region is None:
            break
        target = plan.choose(f'Rampage target in {region}?', [(f, f) for f in choices[region]])
        entry = {'region': region, 'target': target}
        # Opponent declarations remain live choices at execution; this is
        # the same detached, default-outcome preview used by other Commands.
        _execute_rampage(plan.state, faction, {'command': rc.CMD_RALLY,
                         'sa': rc.SA_RAMPAGE, 'sa_regions': [entry], 'details': {}})
        entries.append(plan.entry(entry))
        selected.add(region)
    return entries, plan.extra()
