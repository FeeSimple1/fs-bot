"""A34 Non-player decisions: the chooser's priorities, German mechanics.

§8.2.3 applies the beneficiary's chart even when it commands Germans. Keep
these two roles separate: named victory/Control/enemy priorities refer to the
beneficiary; the force available to March/Battle is German. In particular,
German arrival never adds Aedui/Belgic Control. All plans use real German
pieces; no ownership, Leader identity, or piece type is projected or changed.
"""
from copy import deepcopy
from itertools import groupby

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (count_pieces, count_pieces_by_state,
                                 get_leader_in_region, find_leader)
from fs_bot.board.control import is_controlled_by, refresh_all_control
from fs_bot.battle.losses import calculate_losses, _build_loss_priority
from fs_bot.bots.bot_common import (predict_battle, count_mobile_pieces,
    count_faction_allies_and_citadels, get_faction_targeting_order, random_select)
from fs_bot.map.map_data import get_playable_regions_for_state, get_adjacent, get_control_value


def _copy(state):
    return deepcopy({k:v for k,v in state.items() if k != 'decision_agent'})


def _regions(state):
    return list(get_playable_regions_for_state(state, rc.GERMANS))


def _wb(state, region):
    return count_pieces(state, region, rc.GERMANS, rc.WARBAND)


def _leader(state, region):
    return get_leader_in_region(state, region, rc.GERMANS)


def _force(state, region):
    return _wb(state, region) + bool(_leader(state, region))


def _bases(state, region, faction):
    return sum(count_pieces(state, region, faction, p)
               for p in (rc.ALLY, rc.CITADEL, rc.SETTLEMENT))


def _enemies(state, chooser, *, battle=True):
    enemies = [f for f in get_faction_targeting_order(chooser, state['scenario'])
               if f != chooser and (not battle or f != rc.GERMANS)]
    if chooser == rc.AEDUI and battle:
        from fs_bot.bots.aedui_bot import _aedui_at_victory
        if not _aedui_at_victory(state):
            enemies = [f for f in enemies if f != rc.ROMANS]
    return enemies


def _shuffle_sort(state, values, key):
    """Order priorities; use the shared §8.3.4 chooser only within a tie."""
    ordered = []
    for _, members in groupby(sorted(values, key=key), key=key):
        tied = list(members)
        while tied:
            chosen = random_select(state, tied)
            ordered.append(chosen)
            tied.remove(chosen)
    return ordered


def _high_value_forced(state, region, enemy):
    """A4, with the granted normal Battle's possible Retreat and no Ambush."""
    from fs_bot.cards.capabilities import is_capability_active
    high = {rc.LEADER, rc.LEGION, rc.ALLY, rc.CITADEL, rc.SETTLEMENT}
    choices = [False]
    if (enemy != rc.ARVERNI and count_mobile_pieces(state, region, enemy)
            and not (enemy == rc.BELGAE and is_capability_active(
                state, 'A70', rc.EVENT_UNSHADED))):
        choices.append(True)
    for retreat in choices:
        losses = calculate_losses(state, region, rc.GERMANS, enemy, is_retreat=retreat)
        order = _build_loss_priority(state, region, enemy, is_retreat=retreat)
        if not any(p[0] in high for p in order[:losses]):
            return False
    return True


def _battle(state, chooser, limit):
    """Relevant force conditions, then each beneficiary's Battle priorities."""
    regions, enemies = _regions(state), _enemies(state, chooser)
    leader_region = find_leader(state, rc.GERMANS)
    threats = []
    for region in regions:
        if not _force(state, region):
            continue
        targets = [e for e in enemies if count_pieces(state, region, e)]
        if chooser == rc.BELGAE:
            triggered = (_leader(state, region) is not None or _wb(state, region) >= 4) and any(
                _bases(state, region, e) or count_pieces(state, region, e, rc.LEGION)
                or count_pieces(state, region, e) >= 4 for e in targets)
        elif chooser == rc.ROMANS:
            # The commanded force has no Legions. Its actual Leader is the
            # only applicable Leader/Legion threat branch; no Caesar bonus.
            triggered = bool(_leader(state, region)) and any(
                _bases(state, region, e) or get_leader_in_region(state, region, e)
                or is_controlled_by(state, region, e) for e in targets)
        else:
            triggered = any(_high_value_forced(state, region, e) for e in targets)
        if triggered:
            threats.append(region)
    if not threats:
        return None, []

    candidates = []
    for region in regions:
        if not _force(state, region):
            continue
        for enemy in enemies:
            if not count_pieces(state, region, enemy):
                continue
            pred = predict_battle(state, region, rc.GERMANS, enemy)
            if not pred:
                continue
            inflicted, taken = pred['inflicted'], pred['taken']
            if chooser == rc.ROMANS:
                favorable = region in threats and 2 * taken < inflicted and not pred['attacker_leader_lost']
                from fs_bot.engine.victory import calculate_victory_margin
                if enemy == rc.AEDUI and get_leader_in_region(state, region, enemy):
                    if calculate_victory_margin(state, enemy) < 0:
                        continue
                key = (-bool(get_leader_in_region(state, region, enemy)),
                       -count_pieces(state, region, enemy, rc.WARBAND),
                       enemy in state.get('non_player_factions', set()),
                       -count_faction_allies_and_citadels(state, enemy),
                       -(calculate_victory_margin(state, enemy) if enemy != rc.ARVERNI else -999))
            elif chooser == rc.BELGAE:
                favorable = inflicted > taken and not pred['attacker_leader_lost']
                leader_first = region == leader_region and count_mobile_pieces(
                    state, region, enemy) < _force(state, region)
                key = (not leader_first, region not in threats)
            else:
                high = _high_value_forced(state, region, enemy)
                favorable = high or (inflicted > 0 and inflicted >= taken)
                key = (not high, enemies.index(enemy))
            if favorable and _battle_frost_ok(state, region, enemy):
                candidates.append((key, region, enemy))
    # B/R: if the threatened commanded Leader cannot Battle, withdraw first.
    if chooser in (rc.BELGAE, rc.ROMANS) and leader_region in threats:
        if not any(r == leader_region for _, r, _ in candidates):
            return None, threats
    from fs_bot.engine.game_engine import is_frost
    frost = (state.get('frost') or is_frost(state)) and any(
        f not in state.get('non_player_factions', set())
        for f in (rc.ROMANS, rc.AEDUI, rc.BELGAE, rc.GERMANS))
    frontier = [state] if frost else None
    selected, seen = [], set()
    for _, region, enemy in _shuffle_sort(state, candidates, lambda x:x[0]):
        if region in seen:
            continue
        if frontier is not None:
            next_frontier, outcomes_seen, safe = [], set(), True
            from fs_bot.state.serialize import encode
            for previous in frontier:
                for outcome in _battle_frost_outcomes(previous, region, enemy):
                    if not _frost_ok(state, outcome):
                        safe = False
                        break
                    signature = repr(encode({k:v for k,v in outcome.items() if k != 'rng'}))
                    if signature not in outcomes_seen:
                        outcomes_seen.add(signature)
                        next_frontier.append(outcome)
                if not safe:
                    break
            if not safe:
                continue
            frontier = next_frontier
        selected.append({'region': region, 'target': enemy})
        seen.add(region)
        if len(seen) == limit:
            break
    return (_action('Battle', {'battle_plan': selected}) if selected else None), threats


def _action(command, details):
    return {'command': command, 'sa': 'No SA', 'sa_regions': [],
            'regions': [], 'details': details}


def _march_action(moves):
    if not moves:
        return None
    origins, groups, routes, extra = [], {}, {}, []
    for origin, dest, group in moves:
        if origin in routes:
            extra.append({'origin': origin, 'route': [dest], 'group': group})
        else:
            origins.append(origin)
            routes[origin], groups[origin] = [dest], group
    return _action('March', {'origins': origins, 'routes': routes,
        'groups': groups, 'destinations': list(dict.fromkeys(d for _, d, _ in moves)),
        'extra_groups': extra})


def _group(state, origin, number=None, leader=True):
    group = {}
    count = _wb(state, origin) if number is None else number
    if count:
        group[rc.WARBAND] = count
    if leader and _leader(state, origin):
        group[rc.LEADER] = True
    return group


def _preview_move(state, origin, dest, group):
    from fs_bot.commands.march import march_group
    sim = _copy(state)
    # Movement records the selected pieces' visibility on its carried group;
    # a detached preview must not attach that private ledger to the plan.
    march_group(sim, rc.GERMANS, origin, [dest], _copy(group), free=True)
    return sim


def _frost_ok(before, after):
    """§8.4.4: physical outcomes may not advance a player beyond victory."""
    from fs_bot.engine.game_engine import is_frost
    if not before.get('frost') and not is_frost(before):
        return True
    from fs_bot.engine.victory import calculate_victory_margin
    for faction in (rc.ROMANS, rc.AEDUI, rc.BELGAE, rc.GERMANS):
        if faction in before.get('non_player_factions', set()):
            continue
        start = calculate_victory_margin(before, faction)
        end = calculate_victory_margin(after, faction)
        if end > max(0, start):
            return False
    return True


def _game_run_arverni(state, faction):
    return faction == rc.ARVERNI and state['scenario'] in rc.ARIOVISTUS_SCENARIOS


class _LossOutcomeRng:
    """Realize each ordinary-loss outcome using failure counts per phase.

    For a fixed loss priority, soft removals and successful hard removals
    advance through the same piece order. Failed rolls only consume Losses.
    Moving all failures to that phase's first hard target therefore preserves
    the resulting pieces; failure counts enumerate outcomes in polynomial time.
    """
    def __init__(self, enemy, defender_failures, attacker_failures, attacker=rc.GERMANS):
        self.faction = enemy
        self.remaining = {enemy: defender_failures, attacker: attacker_failures}

    def randint(self, low, high):
        if self.remaining[self.faction] > 0:
            self.remaining[self.faction] -= 1
            return high
        return low

    def choice(self, values):
        return values[0]

    def random(self):
        return 0.0

    def shuffle(self, values):
        pass


class _OutcomeBranch(BaseException):
    # A private control signal must pass through consult_agent's exception
    # fallback; it never escapes the detached prediction below.
    def __init__(self, key, options):
        self.key, self.options = key, options


def _legal_loss_choices(state, region, faction, request):
    """Player choices within the required mobile/static loss tiers (§3.2.4)."""
    pieces = list(dict.fromkeys(tuple(p) for p in request['pieces']))
    if get_leader_in_region(state, region, faction) == rc.DIVICIACUS and len(pieces) > 1:
        pieces = [p for p in pieces if p[0] != rc.LEADER]
    static = {rc.ALLY, rc.SETTLEMENT, rc.CITADEL, rc.FORT}
    first = [p for p in pieces if (p[0] in static) == request['is_retreat']]
    return first or pieces


def _player_loss_outcomes(state, region, enemy, retreat, destination, *,
                          attacker=rc.GERMANS, command=False, double_auxilia=False):
    """Explore legal player absorption choices, merging identical continuations."""
    from fs_bot.battle.resolve import resolve_battle
    from fs_bot.engine.agent import LOSS_ORDER, AGREEMENT, RETREAT
    from fs_bot.state.serialize import encode
    from json import dumps
    scripts, branches, complete = [()], set(), set()
    while scripts:
        script = scripts.pop()
        sim = _copy(state)
        class OutcomeRng:
            def __init__(self):
                self.index, self.faction, self.selected = 0, enemy, None
                self.failed = {enemy: 0, attacker: 0}
                self.remaining = None
                self.reactions = []

            def choose(self, options, stage):
                if len(options) == 1:
                    return options[0]
                if self.index < len(script):
                    result = script[self.index]
                    self.index += 1
                    if isinstance(stage, tuple) and stage[0] in ('agreement', 'retreat'):
                        self.reactions.append((stage, result))
                    return result
                board = dumps(encode({k:v for k,v in sim.items()
                                      if k not in ('rng', 'decision_agent')}), sort_keys=True)
                # Same board, phase, remaining Losses, and selected absorber
                # are the same continuation, irrespective of earlier rolls.
                key = (stage, board, self.faction, self.remaining,
                       self.failed[self.faction], self.selected, tuple(options),
                       tuple(self.reactions))
                raise _OutcomeBranch(key, options)

            def randint(self, low, high):
                # Abatis can absorb before the normal LOSS_ORDER hook.
                order = _build_loss_priority(sim, region, self.faction,
                                            is_retreat=retreat and self.faction == enemy)
                if (self.faction == enemy
                        and sim.get('markers', {}).get(region, {}).get(rc.MARKER_ABATIS) == enemy
                        and (retreat or not order or order[0][0] in (rc.ALLY, rc.CITADEL, rc.FORT))):
                    self.selected = ('Abatis', None)
                value = self.choose((low, high), 'roll')
                if value == high:
                    self.failed[self.faction] += 1
                return value

            def choice(self, values):
                return values[0]

            def random(self):
                return 0.0

            def shuffle(self, values):
                pass

        rng = OutcomeRng()
        sim['rng'] = rng
        def agent(board, faction, request):
            non_player = (faction in state.get('non_player_factions', set())
                          or _game_run_arverni(state, faction))
            if command and not non_player:
                if request.get('kind') == AGREEMENT:
                    # Different adjacent hosts/Regions are independent
                    # permission decisions even when neither changes pieces.
                    # Their request identity must survive branch deduplication.
                    return rng.choose((False, True), (
                        'agreement', faction, dumps(encode(request), sort_keys=True)))
                if request.get('kind') == RETREAT:
                    options = [None, *request.get('legal_regions', [])]
                    choice = rng.choose(options, ('retreat', faction,
                                                  dumps(encode(request), sort_keys=True)))
                    return {'retreat': choice is not None, 'region': choice}
            if request.get('kind') != LOSS_ORDER:
                return None
            rng.faction, rng.remaining, rng.selected = faction, request['num_losses'], None
            if faction in state.get('non_player_factions', set()) or _game_run_arverni(state, faction):
                rng.selected = tuple(request['pieces'][0])
                return None
            rng.selected = rng.choose(_legal_loss_choices(board, region, faction, request), 'piece')
            return [rng.selected]
        sim['decision_agent'] = agent
        try:
            if command:
                # Use the actual Command boundary: Card13/27 pre-fire and
                # Card59 region choices are not standalone Battle effects.
                from fs_bot.engine.execute import _execute_battle
                from fs_bot.commands.common import free_action_scope
                from fs_bot.engine.free_actions import _result_error
                with free_action_scope(sim, attacker):
                    result = _execute_battle(sim, attacker, {
                        'command': rc.CMD_BATTLE, 'sa': 'No SA', 'sa_regions': [],
                        'details': {'battle_plan': [{'region': region, 'target': enemy}]}},
                        _double_auxilia=double_auxilia)
                if _result_error(result):
                    raise ValueError(f'Invalid Battle outcome preview: {result}')
            else:
                resolve_battle(sim, region, attacker, enemy,
                               retreat_declaration=retreat, retreat_region=destination)
        except _OutcomeBranch as branch:
            if branch.key not in branches:
                branches.add(branch.key)
                scripts.extend(script + (option,) for option in branch.options)
            continue
        sim.pop('decision_agent', None)
        refresh_all_control(sim)
        key = dumps(encode({k:v for k,v in sim.items() if k != 'rng'}), sort_keys=True)
        if key not in complete:
            complete.add(key)
            yield sim


def _frost_retreat_choices(state, region, enemy, *, attacker=rc.GERMANS):
    """Enumerate Retreat decisions under possible agreements and refusals.

    8.4.4 covers any player agreement or die outcome. A friendly host's
    refusal can make a Non-player stand and Counterattack instead of
    Retreating, so assuming every host agrees is not conservative.
    """
    from fs_bot.engine.agent import AGREEMENT
    from fs_bot.engine.execute import _retreat_destinations, _decide_defender_retreat
    non_players = state.get('non_player_factions', set())
    scripts, choices = [()], set()
    while scripts:
        script = scripts.pop()
        probe, index, agreements = _copy(state), 0, {}

        def choose(options):
            nonlocal index
            if index == len(script):
                raise _OutcomeBranch(index, options)
            result = script[index]
            index += 1
            return result

        class AgreementRng:
            def randint(self, low, high):
                # The published NP agreement roll is a threshold (8.6.6);
                # its two endpoint outcomes cover agreement and refusal.
                return choose((low, high))

        def agent(board, faction, request):
            if (request.get('kind') != AGREEMENT or faction in non_players
                    or _game_run_arverni(state, faction)):
                return None
            key = (faction, request.get('requesting_faction'),
                   request.get('context', {}).get('region'))
            if key not in agreements:
                agreements[key] = choose((False, True))
            return agreements[key]

        probe['rng'], probe['decision_agent'] = AgreementRng(), agent
        try:
            if enemy in non_players or _game_run_arverni(state, enemy):
                choices.add(_decide_defender_retreat(
                    probe, region, attacker, enemy, False))
            else:
                destinations = _retreat_destinations(probe, region, enemy)
                choices.update([(False, None), (True, None)])
                choices.update((True, dest) for dest in destinations)
        except _OutcomeBranch as branch:
            scripts.extend(script + (option,) for option in branch.options)
    return sorted(choices, key=lambda item: (item[0], item[1] or ''))


def _battle_frost_outcomes(state, region, enemy, *, attacker=rc.GERMANS, command=False,
                           double_auxilia=False):
    """Never let an empty prediction make a Frost safety check pass vacuously."""
    produced = False
    for outcome in _enumerate_battle_frost_outcomes(
            state, region, enemy, attacker=attacker, command=command,
            double_auxilia=double_auxilia):
        produced = True
        yield outcome
    if not produced:
        raise ValueError('Battle outcome preview produced no possible states')


def _enumerate_battle_frost_outcomes(state, region, enemy, *, attacker=rc.GERMANS,
                                    command=False, double_auxilia=False):
    """All loss-roll outcomes, plus legal player Retreat/agreement choices.

    A34 defaults to its actual German force. Other explicit Event Battles
    (Card62's Arverni) supply their own attacker without projecting pieces.
    """
    from fs_bot.battle.resolve import resolve_battle, _calculate_attack_losses
    from fs_bot.engine.agent import LOSS_ORDER
    from fs_bot.state.serialize import encode
    from json import dumps

    if command:
        yield from _player_loss_outcomes(
            state, region, enemy, False, None, attacker=attacker, command=True,
            double_auxilia=double_auxilia)
        return
    non_players = state.get('non_player_factions', set())
    retreat_choices = _frost_retreat_choices(state, region, enemy, attacker=attacker)

    had_citadel = count_pieces(state, region, enemy, rc.CITADEL) > 0
    had_fort = count_pieces(state, region, enemy, rc.FORT) > 0
    counter_max = calculate_losses(state, region, enemy, attacker, is_counterattack=True)
    seen = set()
    player_choices = any(f not in non_players and not _game_run_arverni(state, f)
                         and len(set(_build_loss_priority(state, region, f))) > 1
                         for f in (enemy, attacker))
    for retreat, destination in retreat_choices:
        if player_choices:
            yield from _player_loss_outcomes(state, region, enemy, retreat, destination, attacker=attacker)
            continue
        attack_max = _calculate_attack_losses(state, region, attacker, enemy,
            is_retreat=retreat, had_citadel_at_start=had_citadel, had_fort_at_start=had_fort)
        for defender_failures in range(attack_max + 1):
            for attacker_failures in range((0 if retreat else counter_max) + 1):
                sim = _copy(state)
                rng = _LossOutcomeRng(enemy, defender_failures, attacker_failures, attacker)
                sim['rng'] = rng
                def phase_agent(board, faction, request):
                    if request.get('kind') == LOSS_ORDER:
                        rng.faction = faction
                    return None
                sim['decision_agent'] = phase_agent
                resolve_battle(sim, region, attacker, enemy,
                    retreat_declaration=retreat, retreat_region=destination)
                refresh_all_control(sim)
                sim.pop('decision_agent', None)
                # Equal final boards are the same victory outcome regardless
                # of when the individual failed rolls occurred.
                key = dumps(encode({k:v for k,v in sim.items() if k != 'rng'}), sort_keys=True)
                if key not in seen:
                    seen.add(key)
                    yield sim


def _battle_frost_ok(state, region, enemy):
    from fs_bot.engine.game_engine import is_frost
    if not state.get('frost') and not is_frost(state):
        return True
    if all(f in state.get('non_player_factions', set())
           for f in (rc.ROMANS, rc.AEDUI, rc.BELGAE, rc.GERMANS)):
        return True
    return all(_frost_ok(state, outcome)
               for outcome in _battle_frost_outcomes(state, region, enemy))


def _native_control_score(state, chooser):
    return sum(get_control_value(r, state['scenario']) for r in _regions(state)
               if is_controlled_by(state, r, chooser))


def _belgic_march(state, threats, limit):
    leader_region = find_leader(state, rc.GERMANS)
    regions = _regions(state)
    # Threat withdrawal keeps each German origin together, prioritizes its
    # Leader, and approaches actual Belgic pieces (§8.5.1). Named Belgic
    # Control is always scored on the physical board, never on a loan view.
    origins = list(threats)
    if threats and leader_region and _wb(state, leader_region) < max((_wb(state, r) for r in regions), default=0):
        if leader_region not in origins:
            origins.append(leader_region)
    origins = _shuffle_sort(state, origins, lambda r:r != leader_region)[:limit]
    moves, sim = [], _copy(state)
    for origin in origins:
        options = [d for d in get_adjacent(origin) if d in regions and d not in origins]
        group = _group(sim, origin)
        ranked = []
        for dest in options:
            after = _preview_move(sim, origin, dest, group)
            if not _frost_ok(sim, after):
                continue
            nearby = sum(count_pieces(state, r, rc.BELGAE) > 0
                         for r in {dest, *get_adjacent(dest)} if r in regions)
            ranked.append((dest, (-nearby, -_native_control_score(after, rc.BELGAE))))
        if ranked:
            dest = _shuffle_sort(state, ranked, lambda x:x[1])[0][0]
            moves.append((origin, dest, group))
            sim = _preview_move(sim, origin, dest, group)
    if moves:
        return _march_action(moves)
    # §8.5.5's 'add Belgic Control' destination stage cannot be fulfilled by
    # arriving German pieces. Its separate Leader-consolidation stage can.
    if leader_region:
        options = [r for r in get_adjacent(leader_region) if r in regions
                   and _wb(state, r) > 3 and _wb(state, r) > _wb(state, leader_region)
                   and _frost_ok(state, _preview_move(state, leader_region, r, {rc.LEADER: True}))]
        if options:
            dest = _shuffle_sort(state, options, lambda r:-_wb(state, r))[0]
            return _march_action([(leader_region, dest, {rc.LEADER: True})])
    return None


def _aedui_march(state, limit):
    regions, enemies = _regions(state), _enemies(state, rc.AEDUI, battle=False)
    # The spread priority concerns the commanded Warbands; target Factions
    # and their native Allies/Citadels retain Aedui §8.6.5 priorities.
    totals = {e: count_faction_allies_and_citadels(state, e) for e in enemies}
    options = []
    for origin in regions:
        hidden_after_march = sum(count_pieces_by_state(state, origin, rc.GERMANS, rc.WARBAND, visibility)
                                 for visibility in (rc.HIDDEN, rc.REVEALED))
        maximum = min(hidden_after_march, _wb(state, origin) - 1)
        # Leave one. Scouted Warbands become Revealed, not Hidden (3.3.2).
        if maximum < 1:
            continue
        destinations = [r for r in get_adjacent(origin) if r in regions
            and not count_pieces_by_state(state, r, rc.GERMANS, rc.WARBAND, rc.HIDDEN)
            and _frost_ok(state, _preview_move(state, origin, r, {rc.WARBAND: 1}))]
        def rank(dest):
            bases = [e for e in enemies if _bases(state, dest, e)]
            return (not bool(bases), -max((totals[e] for e in bases), default=0))
        ranked = _shuffle_sort(state, destinations, rank)
        destinations, sim = [], _copy(state)
        for dest in ranked:
            after = _preview_move(sim, origin, dest, {rc.WARBAND: 1})
            if not _frost_ok(sim, after):
                continue
            destinations.append(dest)
            sim = after
            if len(destinations) == min(3, maximum):
                break
        if destinations:
            options.append((origin, destinations, tuple(rank(r) for r in destinations)))
    if not options:
        return None
    origin, destinations, _ = _shuffle_sort(state, options,
        lambda x:(x[2] + ((True, 0),) * (3 - len(x[1])), -len(x[1])))[0]
    # German arrivals cannot satisfy the later 'add Aedui Control' step;
    # Diviciacus is not part of the granted German force (A8.6.5).
    return _march_action([(origin, d, {rc.WARBAND: 1}) for d in destinations])


def _roman_march(state, threats, limit):
    from fs_bot.bots.roman_bot import _rank_march_destinations
    regions = _regions(state)
    leader_region = find_leader(state, rc.GERMANS)
    # Up to 2 threatened origins, then 1 with no enemy Ally/Citadel (§8.8.1).
    objectives = {r for r in regions if any(_bases(state, r, e)
                  for e in _enemies(state, rc.ROMANS, battle=False))}
    def reachable(origin):
        return any(d in objectives for d in get_adjacent(origin))
    origins = _shuffle_sort(state, [r for r in threats if reachable(r)],
                            lambda r:r != leader_region)[:2]
    clean = [r for r in regions if _force(state, r) and r not in origins and reachable(r)
             and not any(_bases(state, r, e) for e in _enemies(state, rc.ROMANS, battle=False))]
    if clean:
        origins.append(_shuffle_sort(state, clean, lambda r:r != leader_region)[0])
    origins = origins[:limit]
    reachable = {d for origin in origins for d in get_adjacent(origin)
                 if d in regions and d not in origins}
    # Restrict legality before ranking tiers; unreachable high-priority bases
    # cannot mask a reachable lower-priority destination.
    destinations = _rank_march_destinations(state, state['scenario'],
        allowed_regions=reachable, acting_faction=rc.GERMANS)
    if not destinations:
        return None
    moves, sim = [], _copy(state)
    chosen_dest = None  # no German Legions: consolidate in one destination
    for origin in origins[:limit]:
        choices = [r for r, _ in destinations if r in get_adjacent(origin)
                   and r not in origins and (chosen_dest is None or r == chosen_dest)]
        if not choices:
            continue
        dest = choices[0]
        # Take most able without losing Roman or No Control. Evaluate actual
        # German movement; native Roman troops and Caesar never join it.
        for number in range(_wb(sim, origin), -1, -1):
            group = _group(sim, origin, number)
            if not group:
                continue
            after = _preview_move(sim, origin, dest, group)
            if not _frost_ok(sim, after):
                continue
            before_control = sim['spaces'][origin].get('control')
            after_control = after['spaces'][origin].get('control')
            if before_control in (rc.ROMAN_CONTROL, rc.NO_CONTROL) and after_control not in (
                    rc.ROMAN_CONTROL, rc.NO_CONTROL):
                continue
            moves.append((origin, dest, group))
            chosen_dest = dest
            sim = after
            break
    return _march_action(moves)


def choose_divination_action(state, chooser, limit=3):
    """Return a concrete German action following the beneficiary's chart.

    No Event-selection/Pass decision is repeated for an already granted action
    (§8.2.1–3). Battle conditions/priorities apply first; excluded Rally/Raid/
    Recruit nodes cannot be executed, so use the bottom permitted March node.
    """
    if chooser not in (rc.ROMANS, rc.AEDUI, rc.BELGAE):
        raise ValueError('A34 needs a non-German player beneficiary')
    if state['scenario'] not in rc.ARIOVISTUS_SCENARIOS:
        raise ValueError('A34 requires an Ariovistus scenario')
    limit = min(3, limit)
    if limit < 1:
        return None
    planning = _copy(state)
    # Plans consume the caller's seeded tie-break stream, but speculative
    # mechanics use detached copies and never call a human reaction agent.
    planning['rng'] = state['rng']
    action, threats = _battle(planning, chooser, limit)
    if action:
        return action
    if chooser == rc.BELGAE:
        return _belgic_march(planning, threats, limit)
    if chooser == rc.AEDUI:
        return _aedui_march(planning, limit)
    return _roman_march(planning, threats, limit)
