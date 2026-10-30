"""A37: one selected Celtica Region, followed by direct optional relocation.

A Card Reference A37 and §§5.1/5.1.1: "any Allies" may have any owner,
but only the executing Aedui/Romans move their own Leader and Warbands or
Auxilia. This is Event movement, not a March Command.
"""
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.control import calculate_control, refresh_all_control
from fs_bot.board.pieces import (
    count_pieces_by_state, get_available, get_leader_in_region, move_piece,
)
from fs_bot.map.map_data import get_adjacent, get_playable_regions_for_state


def _clone(state):
    return deepcopy({key: value for key, value in state.items()
                     if key != 'decision_agent'})


def eligible_regions(state):
    """Evaluate German Control before the Event changes any pieces."""
    if state['scenario'] not in rc.ARIOVISTUS_SCENARIOS:
        return []
    playable = set(get_playable_regions_for_state(state))
    german = {region for region in playable
              if calculate_control(state, region) == rc.GERMANIC_CONTROL}
    return [region for region in rc.CELTICA_REGIONS if region in playable
            and ({region, *get_adjacent(region, state['scenario'],
                                       state.get('capabilities'))} & german)]


def ally_options(state, region, *, require_available=True):
    """Legal (tribe, owner) placements, including normal stacking limits."""
    from fs_bot.cards.card_effects import _tribe_region
    options = []
    for tribe, info in state.get('tribes', {}).items():
        if (_tribe_region(state, tribe) != region
                or info.get('allied_faction') is not None
                or info.get('status') not in (None, rc.ALLIED)):
            continue
        for owner in rc.FACTIONS:
            if (rc.TRIBE_FACTION_RESTRICTION.get(tribe, owner) == owner
                    and (not require_available
                         or get_available(state, owner, rc.ALLY) > 0)):
                options.append((tribe, owner))
    return options


def move_options(state, faction, destination):
    """Every own eligible mobile group, with its actual orientation."""
    kind = rc.AUXILIA if faction == rc.ROMANS else rc.WARBAND
    options = []
    for origin in sorted(get_playable_regions_for_state(state, faction)):
        if origin == destination:
            continue
        if get_leader_in_region(state, origin, faction) is not None:
            options.append((origin, rc.LEADER, None, 1))
        for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
            count = count_pieces_by_state(state, origin, faction, kind, visibility)
            if count:
                options.append((origin, kind, visibility, count))
    return options


def removal_options(state):
    from fs_bot.cards.card_effects import _tribe_piece_type, _tribe_region
    allowed = set(eligible_regions(state))
    return [(tribe, info['allied_faction'])
            for tribe, info in state.get('tribes', {}).items()
            if (_tribe_region(state, tribe) in allowed
                and info.get('allied_faction') in (rc.AEDUI, rc.ROMANS)
                and _tribe_piece_type(state, tribe) == rc.ALLY)]


def _entries(params, key):
    entries = params.get(key, [])
    if not isinstance(entries, list) or any(not isinstance(e, dict) for e in entries):
        raise ValueError(f'A37 {key} must be a list of entries')
    return entries


def _apply(state, placements, moves, faction):
    from fs_bot.cards.card_effects import _ally_tribe, _tribe_region, _event_entries
    from fs_bot.engine.action_windows import set_cohorts, get_cohorts, clear_cohorts
    from fs_bot.board.pieces import count_pieces, PieceError
    ledger, groups, available = 'event.A37.moves', [], {}
    # Reserve the originally selected counters before any Event window.
    # Removing a selected group must not silently substitute a resident.
    for index, move in enumerate(moves):
        origin, kind = move['from_region'], move['piece_type']
        visibility = None if kind == rc.LEADER else move['piece_state'] or rc.HIDDEN
        cell = origin, kind, visibility
        if cell not in available:
            available[cell] = (count_pieces(state, origin, faction, kind)
                               if visibility is None else count_pieces_by_state(
                                   state, origin, faction, kind, visibility))
        if move['count'] > available[cell]:
            raise PieceError('A37 movement selects more original pieces than present')
        available[cell] -= move['count']
        group = {'id': f'{ledger}.{index}', 'label': f'A37 movement group {index + 1}',
                 'region': origin, 'piece_type': kind, 'count': move['count']}
        if visibility is not None:
            group['piece_state'] = visibility
        groups.append(group)
    set_cohorts(state, ledger, faction, groups)
    try:
        for entry in _event_entries(state, 'A37.allies', placements):
            tribe, owner = entry['tribe'], entry['faction']
            if (tribe, owner) not in ally_options(
                    state, _tribe_region(state, tribe)):
                raise ValueError('A37 Ally placement needs an eligible Subdued Tribe and Available disc')
            if not _ally_tribe(state, tribe, owner):
                raise ValueError('A37 could not place the selected Ally')
        for index, move in enumerate(_event_entries(state, 'A37.moves', moves)):
            groups = get_cohorts(state, ledger)
            group = groups[index]
            if group['count']:
                move_piece(state, move['from_region'], move['to_region'], faction,
                           move['piece_type'], count=group['count'],
                           piece_state=group.get('piece_state'))
            # The one destination cannot be an origin. Arrivals have no
            # remaining movement entitlement to distinguish from residents.
            group['count'] = 0
            set_cohorts(state, ledger, faction, groups)
        refresh_all_control(state)
    finally:
        clear_cohorts(state, ledger)


def execute(state, shaded=False):
    """Apply ordered choices atomically, including newly Available pieces."""
    from fs_bot.engine.spring import atomic
    with atomic(state):
        return _execute(state, shaded)


def _execute(state, shaded=False):
    from fs_bot.cards.card_effects import _tribe_region, _unally_tribe, _event_entries
    if state['scenario'] not in rc.ARIOVISTUS_SCENARIOS:
        raise ValueError('A37 belongs to Ariovistus scenarios')
    params = state.get('event_params') or {}
    if not isinstance(params, dict):
        raise ValueError('A37 choices must be an object')
    if shaded:
        removals = _entries(params, 'removals')
        options = set(removal_options(state))
        selected = []
        for entry in removals:
            choice = (entry.get('tribe'), entry.get('faction'))
            if choice not in options or choice in selected or len(selected) == 3:
                raise ValueError('A37 removes at most three distinct Aedui/Roman Allies in Celtica within one of German Control')
            selected.append(choice)
        for entry in _event_entries(state, 'A37.removals', removals):
            _unally_tribe(state, entry['tribe'])
        return

    faction = state.get('executing_faction')
    placements = _entries(params, 'ally_placements')
    moves = _entries(params, 'moves')
    destination = params.get('target_region')
    if faction not in (rc.AEDUI, rc.ROMANS):
        if placements or moves or destination is not None:
            raise ValueError('A37 unshaded is available only to Aedui or Romans')
        return
    # Accept older plans whose unique destination was implicit in placements.
    if destination is None and placements:
        destination = _tribe_region(state, placements[0].get('tribe'))
    if destination is None and moves:
        destination = moves[0].get('to_region')
    if destination is not None and destination not in eligible_regions(state):
        raise ValueError('A37 destination must be a Celtica Region within one of German Control')
    if destination is None and (placements or moves):
        raise ValueError('A37 choices require a destination Region')

    normalized_placements = []
    seen = set()
    for entry in placements:
        tribe, owner = entry.get('tribe'), entry.get('faction', faction)
        if (tribe in seen or _tribe_region(state, tribe) != destination
                or tribe not in state.get('tribes', {})
                or owner not in rc.FACTIONS
                or rc.TRIBE_FACTION_RESTRICTION.get(tribe, owner) != owner
                or entry.get('region', destination) != destination):
            raise ValueError('A37 Allies must occupy distinct eligible Tribes in the one selected Region')
        normalized_placements.append(dict(entry, tribe=tribe, faction=owner))
        seen.add(tribe)

    mobile = rc.AUXILIA if faction == rc.ROMANS else rc.WARBAND
    playable = set(get_playable_regions_for_state(state, faction))
    normalized_moves = []
    for entry in moves:
        origin, target = entry.get('from_region'), entry.get('to_region', destination)
        kind, count = entry.get('piece_type'), entry.get('count', 1)
        visibility = entry.get('piece_state')
        if (origin not in playable or origin == destination or target != destination
                or entry.get('faction', faction) != faction
                or kind not in (rc.LEADER, mobile)):
            raise ValueError('A37 moves only your Leader and Warbands/Auxilia directly to the selected Region')
        if type(count) is not int or count <= 0 or (kind == rc.LEADER and count != 1):
            raise ValueError('A37 move count must be positive; a Leader count must be one')
        if kind == mobile and visibility not in (None, rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
            raise ValueError('A37 move has an invalid piece state')
        if kind == rc.LEADER and visibility is not None:
            raise ValueError('A37 Leader movement does not have a piece state')
        normalized_moves.append(dict(entry, from_region=origin, to_region=target,
            piece_type=kind, count=count, piece_state=visibility))

    # Availability is evaluated after each timing window. The outer local
    # transaction restores every prior effect if a later selection is invalid.
    # A detached preflight would wrongly reject a pool that a live player can
    # replenish, and must never consume their answers.
    _apply(state, normalized_placements, normalized_moves, faction)
    state.setdefault('event_modifiers', {})['card_A37_place_allies_move'] = {
        'region': destination, 'moves': normalized_moves}


def derive_params(state, faction, shaded):
    """NP Aedui place the most own Allies; their instruction forbids moving."""
    if shaded:
        if faction in (rc.AEDUI, rc.ROMANS):
            return None
        from fs_bot.bots.bot_common import get_faction_targeting_order
        order = get_faction_targeting_order(faction, state['scenario'])
        options = removal_options(state)
        state['rng'].shuffle(options)
        options.sort(key=lambda pair: (pair[0] not in rc.TRIBE_TO_CITY,
                                      order.index(pair[1]) if pair[1] in order else len(order)))
        return {'removals': [{'tribe': t, 'faction': f} for t, f in options[:3]]} if options else None
    if faction not in (rc.AEDUI, rc.ROMANS):
        return None
    candidates = []
    for region in eligible_regions(state):
        tribes = [tribe for tribe, owner in ally_options(state, region) if owner == faction]
        count = min(len(tribes), get_available(state, faction, rc.ALLY))
        if count:
            candidates.append((count, region, tribes))
    if not candidates:
        return None
    most = max(count for count, _, _ in candidates)
    _, destination, tribes = state['rng'].choice([c for c in candidates if c[0] == most])
    state['rng'].shuffle(tribes)
    tribes.sort(key=lambda tribe: tribe not in rc.TRIBE_TO_CITY)
    # Romans treat this Event as No Romans. The only active NP beneficiary,
    # Aedui, has the explicit A37 instruction "Move no pieces".
    return {'target_region': destination, 'ally_placements': [
        {'tribe': tribe, 'faction': faction} for tribe in tribes[:most]], 'moves': []}


def collect_params(state, faction, shaded, stdin, stdout):
    """Typed, bounded selections stored in the ordinary replayable Event plan."""
    from fs_bot.cli.menus import prompt_choice
    from fs_bot.cli.action_windows import prepare, planning_copy, inspect_board
    from fs_bot.cards.card_effects import _ally_tribe, _unally_tribe, _tribe_piece_type
    stage, tail_actions = planning_copy(state), {}

    def before(step, index):
        nonlocal stage
        stage, actions = prepare(stage, faction, stdin, stdout,
                                 stage='event_step', step=step, index=index)
        return actions

    def finish(params):
        if tail_actions:
            params['stage_timing_actions'] = tail_actions
        return params

    if shaded:
        original_options, selected = removal_options(state), []
        while len(selected) < 3:
            actions = before('A37.removals', len(selected))
            options = [(t, f) for t, f in original_options
                       if stage['tribes'][t].get('allied_faction') == f
                       and _tribe_piece_type(stage, t) == rc.ALLY]
            if not options:
                if actions:
                    tail_actions[f'A37.removals:{len(selected)}'] = actions
                break
            with inspect_board(stage, stdout):
                choice = prompt_choice(stdin, stdout, 'A37: remove which Ally?',
                    [('Finish removing Allies', None)] + [(f'{t}: {f}', (t, f)) for t, f in options])
            if choice is None:
                if actions:
                    tail_actions[f'A37.removals:{len(selected)}'] = actions
                break
            entry = {'tribe': choice[0], 'faction': choice[1]}
            if actions:
                entry['timing_actions'] = actions
            _unally_tribe(stage, choice[0])
            selected.append(entry)
        return finish({'removals': selected})
    if faction not in (rc.AEDUI, rc.ROMANS):
        return {}
    destination = prompt_choice(stdin, stdout, 'A37: select one Celtica Region near German Control:',
        [('Finish without placement or movement', None)] + [(r, r) for r in eligible_regions(state)])
    if destination is None:
        return {'ally_placements': [], 'moves': []}
    placements, moves = [], []
    while True:
        actions = before('A37.allies', len(placements))
        placed_tribes = {entry['tribe'] for entry in placements}
        options = [(tribe, owner) for tribe, owner in ally_options(stage, destination)
                   if tribe not in placed_tribes]
        if not options:
            if actions:
                tail_actions[f'A37.allies:{len(placements)}'] = actions
            break
        with inspect_board(stage, stdout):
            choice = prompt_choice(stdin, stdout, f'A37: place an Ally in {destination}?',
                [('Finish placing Allies', None)] + [(f'{t}: {f}', (t, f)) for t, f in options])
        if choice is None:
            if actions:
                tail_actions[f'A37.allies:{len(placements)}'] = actions
            break
        tribe, owner = choice
        _ally_tribe(stage, tribe, owner)
        entry = {'tribe': tribe, 'faction': owner}
        if actions:
            entry['timing_actions'] = actions
        placements.append(entry)
    while True:
        actions = before('A37.moves', len(moves))
        options = move_options(stage, faction, destination)
        if not options:
            if actions:
                tail_actions[f'A37.moves:{len(moves)}'] = actions
            break
        with inspect_board(stage, stdout):
            choice = prompt_choice(stdin, stdout, f'A37: move your pieces directly to {destination}?',
                [('Finish moving pieces', None)] + [
                    (f'{origin}: {count} {visibility + " " if visibility else ""}{kind}',
                     (origin, kind, visibility, count)) for origin, kind, visibility, count in options])
        if choice is None:
            if actions:
                tail_actions[f'A37.moves:{len(moves)}'] = actions
            break
        origin, kind, visibility, maximum = choice
        count = (1 if maximum == 1 else prompt_choice(stdin, stdout, 'How many pieces?',
                                                     [(str(n), n) for n in range(1, maximum + 1)]))
        move_piece(stage, origin, destination, faction, kind, count=count, piece_state=visibility)
        entry = {'from_region': origin, 'to_region': destination,
                 'piece_type': kind, 'piece_state': visibility, 'count': count}
        if actions:
            entry['timing_actions'] = actions
        moves.append(entry)
    return finish({'target_region': destination, 'ally_placements': placements, 'moves': moves})
