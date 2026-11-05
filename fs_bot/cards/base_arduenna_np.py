"""Numeric 67 Arverni planning under provisional PR-11.

The printed objective is maximum Losses on Legions, using ordinary March
legality, safe Vercingetorix Harassment, and §§8.4.1/8.4.4. PR-11 supplies
the conservative response forecast; it is not an official game-rule ruling.
Real decisions and dice always resolve through the normal Command executor.
"""
from copy import deepcopy
from itertools import permutations
from json import dumps
from random import Random

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (count_pieces, count_pieces_by_state,
                                 find_leader, get_leader_in_region, flip_piece)
from fs_bot.cards.arduenna import TARGETS, march_request
from fs_bot.map.map_data import get_adjacent_for_state, get_playable_regions_for_state

STATES = (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)


def _copy(state):
    trial = deepcopy({k: v for k, v in state.items() if k != 'decision_agent'})
    trial['_diviciacus_preview'] = True
    trial['non_player_factions'] = set(trial.get('non_player_factions', ())) | {rc.ARVERNI}
    return trial


def _physical(state, region):
    return tuple(count_pieces_by_state(state, region, rc.ARVERNI, rc.WARBAND, ps) for ps in STATES)


def _signature(state):
    from fs_bot.state.serialize import encode
    return dumps(encode({k: v for k, v in state.items()
                         if k not in ('rng', 'decision_agent')}), sort_keys=True)


def _battle_action(regions):
    return {'command': rc.CMD_BATTLE, 'sa': 'No SA', 'sa_regions': [],
            'regions': list(regions), 'details': {'battle_plan': [
                {'region': region, 'target': rc.ROMANS} for region in regions]}}


def _outcomes(state, regions, *, frost=False, before=None):
    """Branch the whole Command: later Battles see earlier Retreats/prefire.

Score forecasts fix Roman Defender Loss rolls to removals (§8.7.1), retain
the existing printed/default physical casualty order, and minimize across
human stance/host decisions and uncertain own hard saves. Frost additionally
branches every roll and legal human casualty choice, as Divination does.
"""
    from fs_bot.cards.divination_np import _OutcomeBranch, _legal_loss_choices
    from fs_bot.cards.migration import _frost_ok
    from fs_bot.commands.common import free_action_scope
    from fs_bot.engine.agent import AGREEMENT, LOSS_ORDER, RETREAT
    from fs_bot.engine.execute import _execute_battle
    from fs_bot.engine.free_actions import _result_error
    scripts, branched, completed = [()], set(), set()
    while scripts:
        script = scripts.pop()
        sim = _copy(state)
        # This simulation supplies its own explicit agreement branches. The
        # generic detached-preview shortcut would silently force Diviciacus
        # sharing even when that synthetic human response declines it.
        sim.pop('_diviciacus_preview', None)
        score, leader_risk, permitted = 0, False, True
        class ForecastRng(Random):
            def __init__(self):
                super().__init__(0)
                self.index, self.faction, self.loss, self.remaining = 0, None, False, None
                self.roll_index = 0
                self.selected = None
                self.reactions = []

            def choose(self, options, stage):
                if len(options) == 1:
                    return options[0]
                if self.index < len(script):
                    result = script[self.index]
                    self.index += 1
                    if stage[0] in ('agreement', 'retreat', 'horse'):
                        self.reactions.append((stage, result))
                    return result
                key = (stage, _signature(sim), self.faction, self.loss,
                       self.remaining, self.selected, self.roll_index, tuple(options),
                       tuple(self.reactions), score, leader_risk, permitted)
                raise _OutcomeBranch(key, options)

            def randint(self, low, high):
                # Abatis absorbs before LOSS_ORDER. Its successful save
                # leaves the board unchanged but consumes a Loss, so the
                # roll position is part of the continuation identity too.
                self.roll_index += 1
                if not frost and self.loss and self.faction == rc.ROMANS:
                    return low
                return self.choose((low, high), ('roll',))

            def choice(self, values):
                return values[0]

            def random(self):
                return 0.0

            def shuffle(self, values):
                pass

        rng = sim['rng'] = ForecastRng()
        def agent(board, faction, request):
            nonlocal score, leader_risk
            kind = request.get('kind')
            npc = faction in sim['non_player_factions']
            if kind == 'horse_window':
                rng.loss = False
                if not npc:
                    return {'action': rng.choose(tuple(request['actions']),
                        ('horse', faction, dumps(request, sort_keys=True)))}
                return None
            if kind == AGREEMENT:
                rng.loss = False
                if not npc:
                    return rng.choose((False, True), ('agreement', faction, dumps(request, sort_keys=True)))
                return None
            if kind == RETREAT:
                # Defending Abatis can roll before the first piece-choice
                # callback. The following absorption belongs to this side.
                rng.faction, rng.loss = faction, True
                if not npc:
                    choice = rng.choose((None, *request.get('legal_regions', [])),
                                        ('retreat', faction, dumps(request, sort_keys=True)))
                    return {'retreat': choice is not None, 'region': choice}
                return None  # The canonical Roman NP Retreat policy.
            if kind != LOSS_ORDER:
                return None
            rng.faction, rng.loss = faction, True
            rng.remaining = request['num_losses']
            chosen = tuple(request['pieces'][0])
            if frost and not npc:
                chosen = rng.choose(_legal_loss_choices(board, request['region'], faction, request),
                                    ('piece', faction, request['region']))
            rng.selected = chosen
            if faction == rc.ROMANS and chosen[0] == rc.LEGION:
                score += 1
            if (faction == rc.ARVERNI and chosen[0] == rc.LEADER
                    and get_leader_in_region(board, request['region'], faction) == rc.VERCINGETORIX):
                leader_risk = True
            return [chosen]
        sim['decision_agent'] = agent
        def observe(phase, board, region, enemy, result):
            nonlocal permitted
            if phase == 'after' and frost and not _frost_ok(before or state, board):
                permitted = False
        try:
            with free_action_scope(sim, rc.ARVERNI):
                result = _execute_battle(sim, rc.ARVERNI, _battle_action(regions),
                                         _battle_observer=observe, _skip_absent_targets=True)
            error = _result_error(result)
            if error:
                raise ValueError(f'Arduenna Battle forecast failed: {error}')
        except _OutcomeBranch as branch:
            if branch.key not in branched:
                branched.add(branch.key)
                scripts.extend(script + (option,) for option in branch.options)
            continue
        sim.pop('decision_agent', None)
        permitted = permitted and (not frost or _frost_ok(before or state, sim))
        key = (_signature(sim), score, leader_risk, permitted)
        if key not in completed:
            completed.add(key)
            yield score, leader_risk, permitted


def predicted_legion_losses(state, regions):
    """Pure PR-11 lower forecast for an ordered Battle sequence."""
    if isinstance(regions, str):
        regions = [regions]
    outcomes = list(_outcomes(state, regions))
    if not outcomes or any(risk for _, risk, _ in outcomes):
        return 0
    return min(score for score, _, _ in outcomes)


def _best_battles(before, state):
    from fs_bot.cards.migration import _frost_ok
    from fs_bot.engine.game_engine import is_frost, get_sop_factions
    if not _frost_ok(before, state):
        return 0, []
    # These are prospective Regions, selected only when reached (§3.1).
    # A first Retreat may bring Romans into a target that was initially empty.
    regions = [r for r in TARGETS if count_pieces(state, r, rc.ARVERNI, rc.WARBAND)
               or get_leader_in_region(state, r, rc.ARVERNI)]
    frost = (before.get('frost') or is_frost(before)) and any(
        f not in before.get('non_player_factions', ()) for f in get_sop_factions(before))
    best, choices = 0, []
    for size in range(1, len(regions) + 1):
        for sequence in permutations(regions, size):
            score = predicted_legion_losses(state, sequence)
            if score < best or not score:
                continue
            if frost and any(not permitted for _, _, permitted in _outcomes(
                    state, sequence, frost=True, before=before)):
                continue
            if score > best:
                best, choices = score, [sequence]
            else:
                choices.append(sequence)
    return best, choices


def _action(moves):
    if not moves:
        return None
    origins, routes, groups, extras = [], {}, {}, []
    for move in moves:
        origin = move['origin']
        if origin not in routes:
            origins.append(origin)
            routes[origin], groups[origin] = move['route'], move['group']
        else:
            extras.append(move)
    plan = {'origins': origins, 'destinations': sorted({m['route'][-1] for m in moves}),
            'routes': routes, 'groups': groups}
    if extras:
        plan['extra_groups'] = extras
    return {'command': rc.CMD_MARCH, 'sa': 'No SA', 'sa_regions': [],
            'regions': origins, 'details': {'march_plan': plan}}


def _routes(state, origin, group):
    from fs_bot.cli.human_plan import _march_routes
    return [route for route in _march_routes(state, origin, rc.ARVERNI, group)
            if route[-1] in TARGETS]


def _agreements(state, *, preview):
    """Bind each human Harassment declaration once, as the Publius planner."""
    from fs_bot.engine.execute import _np_harassers
    from fs_bot.engine.game_engine import get_sop_factions
    origin = find_leader(state, rc.ARVERNI)
    if origin is None:
        return {}
    group = {rc.LEADER: get_leader_in_region(state, origin, rc.ARVERNI),
             rc.WARBAND: count_pieces(state, origin, rc.ARVERNI, rc.WARBAND)}
    probe = _copy(state) if preview else state
    if preview:
        players = set(get_sop_factions(probe)) - set(probe['non_player_factions'])
        probe['decision_agent'] = lambda board, faction, request: (
            False if faction in players and request.get('request_type') == 'harassment' else None)
    transits = sorted({region for route in _routes(state, origin, group) for region in route[:-1]})
    return {region: _np_harassers(probe, region, rc.ARVERNI, group) for region in transits}


def _march(state, action, agreements):
    """Keep binding Harassment promises without replacing other live choices."""
    from fs_bot.engine.free_actions import execute_free_action_plan
    if action is None:
        return {'executed': False, 'declined_no_effect': True}
    old, had = state.get('decision_agent'), 'decision_agent' in state
    def agent(board, faction, request):
        if request.get('request_type') == 'harassment':
            region = request.get('context', {}).get('region')
            if region in agreements:
                return any(owner == faction for owner, _ in agreements[region])
        return old(board, faction, request) if old else None
    agent.supports_action_windows = bool(getattr(old, 'supports_action_windows', False)
        or getattr(getattr(old, '__self__', None), 'supports_action_windows', False))
    state['decision_agent'] = agent
    try:
        return execute_free_action_plan(state, rc.ARVERNI, march_request(67), deepcopy(action))
    finally:
        if had:
            state['decision_agent'] = old
        else:
            state.pop('decision_agent', None)


def _preview_moves(state, moves, agreements):
    """Apply already validated routes to frozen original physical cohorts.

Candidate construction checks normal reachability once per origin/Leader.
Repeatedly running the public planner would re-enumerate those same routes
for every quantity. This detached replay uses the canonical movement and
Harassment mechanics; only NPC formation and the once-per-origin flip are
expanded here. Full execution still uses the public Arduenna executor.
    """
    from fs_bot.commands.march import march_group, resolve_harassment
    after, pools, prepared = _copy(state), {}, []
    for move in moves:
        origin, group = move['origin'], deepcopy(move['group'])
        pool = pools.setdefault(origin, dict(zip(STATES, _physical(state, origin))))
        remaining, selected = group.get(rc.WARBAND, 0), {}
        for ps in STATES:
            take = min(remaining, pool[ps])
            pool[ps] -= take
            remaining -= take
            if take:
                flipped = rc.REVEALED if ps == rc.SCOUTED else rc.HIDDEN
                selected[flipped] = selected.get(flipped, 0) + take
        if remaining:
            raise ValueError('Arduenna preview exceeds its original physical cohort')
        group['_march_visibility'] = {rc.WARBAND: selected}
        prepared.append((origin, move['route'], group))
    # Flip only initial pieces. Doing all these flips before detached
    # movement is equivalent to the executor's original-cohort ledger and
    # prevents an arriving piece from being flipped a second time.
    for origin in pools:
        for ps, target in ((rc.REVEALED, rc.HIDDEN), (rc.SCOUTED, rc.REVEALED)):
            count = count_pieces_by_state(after, origin, rc.ARVERNI, rc.WARBAND, ps)
            if count:
                flip_piece(after, origin, rc.ARVERNI, rc.WARBAND, count,
                           from_state=ps, to_state=target)
    for origin, route, group in prepared:
        current = origin
        for index, target in enumerate(route):
            result = march_group(after, rc.ARVERNI, current, [target], group, free=True)
            current = result['final_region']
            if current != target or (result['stopped_reason'] and index < len(route) - 1):
                raise ValueError('A validated Arduenna route became incomplete in preview')
            if index < len(route) - 1:
                resolve_harassment(after, current, rc.ARVERNI, group,
                                   harassing_factions=agreements[current])
    return after


def _local_options(state, origin, agreements):
    number = count_pieces(state, origin, rc.ARVERNI, rc.WARBAND)
    leader = get_leader_in_region(state, origin, rc.ARVERNI)
    direct = {route[-1]: route for route in _routes(state, origin, {rc.WARBAND: number})
              if len(route) == 1} if number else {}
    leader_routes = [None] + (_routes(state, origin, {rc.LEADER: leader, rc.WARBAND: number}) if leader else [])
    seen = set()
    for route in leader_routes:
        destination = route[-1] if route else origin
        reachable = {target for target in TARGETS if target == origin or target in direct}
        if route:
            reachable.add(destination)
        losses = sum(n // rc.HARASSMENT_WARBANDS_PER_LOSS
                     for region in (route or [])[:-1] for _, n in agreements[region])
        if losses > 3:
            continue
        for first in range(number + 1 if TARGETS[0] in reachable else 1):
            for second in range(number - first + 1 if TARGETS[1] in reachable else 1):
                amounts = (first, second)
                if origin in TARGETS and first + second != number:
                    continue
                if route and losses > amounts[TARGETS.index(destination)]:
                    continue  # No Harassment Loss may reach Vercingetorix.
                moves = []
                for index, target in enumerate(TARGETS):
                    leading = bool(route and destination == target)
                    if target != origin and (amounts[index] or leading):
                        moves.append({'origin': origin, 'route': route if leading else direct[target],
                                      'group': {rc.WARBAND: amounts[index], rc.LEADER: leader if leading else None}})
                # NPC physical selection is Hidden-first before origin flips.
                # Both split-group orders can therefore produce distinct
                # surviving visibility cohorts, even for equal piece totals.
                orders = [moves] + ([list(reversed(moves))] if len(moves) == 2 else [])
                for ordered in orders:
                    action = _action(ordered)
                    key = dumps(action, sort_keys=True)
                    if key in seen:
                        continue
                    seen.add(key)
                    after = _preview_moves(state, ordered, agreements)
                    delta = tuple(after_n - before_n for r in TARGETS
                                  for after_n, before_n in zip(_physical(after, r), _physical(state, r)))
                    yield {'moves': ordered, 'delta': delta, 'losses': losses,
                           'leader': destination if leader else None,
                           'escort': min(4, count_pieces(after, destination, rc.ARVERNI, rc.WARBAND)) if leader else 0,
                           'outside': _physical(after, origin),
                           'control': after['spaces'][origin]['control']}


def _layers(state, agreements):
    """Exact continuation equivalence for this two-target, one-March grant.

Keep target physical visibility; outside Regions common to both targets
keep exact remaining physical counts because a first Retreat can alter
their Control before the second Battle. Other outside origins retain their
Control: they cannot fight, move again, or receive a Retreat from both
targets. Their different residual mobile counts cannot affect future
Battle legality, Roman destination priority or Frost victory margins.
The representative path always retains the real initial cohorts.
"""
    origins = sorted(r for r in get_playable_regions_for_state(state, rc.ARVERNI)
                     if count_pieces(state, r, rc.ARVERNI, rc.WARBAND)
                     or get_leader_in_region(state, r, rc.ARVERNI))
    common = set(get_adjacent_for_state(state, TARGETS[0])) & set(get_adjacent_for_state(state, TARGETS[1]))
    # A Region containing only Arverni can never host a Roman Retreat:
    # Arverni NP refuse, and No Control is not a Retreat destination. Its
    # mobile departures also cannot create another faction's Control.
    relevant_outside = {r for r in origins if any(
        count_pieces(state, r, f) for f in rc.FACTIONS if f != rc.ARVERNI)}
    counts = tuple(n for r in TARGETS for n in _physical(state, r))
    # key: target visibility, Leader destination, outside escort, outside
    # continuation signature. Value: least Harassment, path count, links.
    layers = [{(counts, find_leader(state, rc.ARVERNI), 0, ()): (0, 1, [])}]
    all_options = []
    for origin in origins:
        local = list(_local_options(state, origin, agreements))
        all_options.append(local)
        current = {}
        for previous, (cost, ways, _) in layers[-1].items():
            for index, option in enumerate(local):
                physical = tuple(a + b for a, b in zip(previous[0], option['delta']))
                outside = previous[3]
                if origin not in TARGETS and origin in relevant_outside:
                    outside += ((origin, option['outside'] if origin in common else option['control']),)
                key = (physical, option['leader'] or previous[1],
                       option['escort'] if option['leader'] not in (None, *TARGETS) else previous[2], outside)
                total = cost + option['losses']
                old = current.get(key)
                link = (previous, index, ways)
                if old is None or total < old[0]:
                    current[key] = (total, ways, [link])
                elif total == old[0]:
                    old[2].append(link)
                    current[key] = (total, old[1] + ways, old[2])
        layers.append(current)
    return layers, all_options


def _weighted(state, values, choose):
    if not choose or len(values) == 1:
        return values[0][0]
    roll = state['rng'].randint(1, sum(weight for _, weight in values))
    for value, weight in values:
        roll -= weight
        if roll <= 0:
            return value
    raise AssertionError('Weighted choice exhausted')


def _moves(state, key, layers, options, choose=False):
    moves = []
    for index in range(len(options) - 1, -1, -1):
        links = layers[index + 1][key][2]
        key, selected = _weighted(state, [((previous, option), ways)
                                for previous, option, ways in links], choose)
        moves[0:0] = options[index][selected]['moves']
    return moves


def plan(state, *, choose=False, _existence=False):
    """Pure deterministic best plan by default; live choice binds promises."""
    if state['scenario'] not in rc.BASE_SCENARIOS or not any(
            count_pieces(state, r, rc.ROMANS, rc.LEGION) for r in TARGETS):
        return None
    agreements = _agreements(state, preview=not choose)
    trial = _copy(state)
    layers, options = _layers(trial, agreements)
    best, candidates = None, []
    forecasts = {}
    for key, (harassment, ways, _) in layers[-1].items():
        # A normal Battle has no Hidden-majority test. For the existing NP
        # casualty/Elite policy, own Warband visibility does not change its
        # Loss count, Control, or Roman Retreat options. Keep the physical
        # variants in the DAG for real March/Hide, but share their forecast.
        forecast_key = (sum(key[0][:3]), sum(key[0][3:]), key[1], key[3])
        if forecast_key not in forecasts:
            after = _preview_moves(trial, _moves(trial, key, layers, options), agreements)
            forecasts[forecast_key] = _best_battles(trial, after)
        score, battles = forecasts[forecast_key]
        if not score:
            continue
        if _existence:
            return {'predicted_legion_losses': score}
        escort = (min(4, sum(key[0][3 * TARGETS.index(key[1]):3 * TARGETS.index(key[1]) + 3]))
                  if key[1] in TARGETS else key[2])
        rank = (score, -harassment, escort)
        if best is None or rank > best:
            best, candidates = rank, [(key, battles, ways)]
        elif rank == best:
            candidates.append((key, battles, ways))
    if not candidates:
        return None
    key, battles = _weighted(state, [((key, battles), ways) for key, battles, ways in candidates], choose)
    regions = _weighted(state, [(regions, 1) for regions in battles], choose)
    return {'march': _action(_moves(state, key, layers, options, choose)),
            'battle_regions': list(regions), 'predicted_legion_losses': best[0],
            '_harassers': agreements,
            'search_states': sum(len(layer) for layer in layers)}


def available(state):
    return plan(state, _existence=True) is not None


def default_sequence(state):
    from fs_bot.cards.arduenna import hide
    from fs_bot.cards.card_effects import _event_step
    from fs_bot.commands.common import free_action_scope
    from fs_bot.engine.execute import _execute_battle
    _event_step(state, '67.march', beneficiary=rc.ARVERNI)
    selected = plan(state, choose=True)
    if selected is None:
        return []
    results = []
    if selected['march'] is not None:
        result = _march(state, selected['march'], selected['_harassers'])
        results.append({'free_action': 'march', 'flag': 'card_67',
                        'faction': rc.ARVERNI, 'result': result})
    _event_step(state, '67.command', beneficiary=rc.ARVERNI)
    before = _copy(state)
    _, battles = _best_battles(before, before)
    if battles:
        regions = _weighted(state, [(regions, 1) for regions in battles], True)
        with free_action_scope(state, rc.ARVERNI):
            result = _execute_battle(state, rc.ARVERNI, _battle_action(regions),
                                    _skip_absent_targets=True)
        results.append({'free_action': 'free_command', 'flag': 'card_67',
                        'faction': rc.ARVERNI, 'result': result})
    _event_step(state, '67.hide', beneficiary=rc.ARVERNI)
    results.append(hide(state, rc.ARVERNI, card_id=67))
    return results
