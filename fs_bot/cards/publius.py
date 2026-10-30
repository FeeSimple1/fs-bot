"""A17: one bounded Roman March followed by a double-Auxilia Battle."""
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, get_leader_in_region
from fs_bot.commands.common import free_action_scope
from fs_bot.engine.free_actions import consult_free_action, execute_free_action_plan
from fs_bot.map.map_data import get_playable_regions_for_state


def _copy(state):
    return deepcopy({key: value for key, value in state.items() if key != 'decision_agent'})


def march_routes(state, origin, legions, auxilia):
    """Movement-only preview: never roll Harassment or ask another player."""
    from fs_bot.cli.human_plan import _march_routes
    group = {rc.LEGION: legions, rc.AUXILIA: auxilia}
    routes = [[], *_march_routes(state, origin, rc.ROMANS, group)]
    return [route for route in routes
            if get_leader_in_region(state, route[-1] if route else origin, rc.ROMANS) != rc.CAESAR]


def march_origins(state):
    return [region for region in sorted(get_playable_regions_for_state(state, rc.ROMANS))
            if count_pieces(state, region, rc.ROMANS, rc.LEGION)
            and count_pieces(state, region, rc.ROMANS, rc.AUXILIA)]


def validate_march(state, response):
    if (not isinstance(response, dict)
            or set(response) - {'origin', 'route', 'legions', 'auxilia', 'dropoffs'}
            or not {'origin', 'route', 'legions', 'auxilia'} <= set(response)):
        raise ValueError('Publius requires one origin, route, Legion count and Auxilia count; no Leader.')
    origin, route = response['origin'], response['route']
    if origin not in march_origins(state):
        raise ValueError('Choose an origin containing both Legions and Auxilia.')
    for key, piece, limit in (('legions', rc.LEGION, 4), ('auxilia', rc.AUXILIA, 8)):
        n = response[key]
        if type(n) is not int or not 1 <= n <= min(limit, count_pieces(state, origin, rc.ROMANS, piece)):
            raise ValueError(f'Publius requires 1–{limit} available {piece}.')
    if not isinstance(route, list) or route not in march_routes(
            state, origin, response['legions'], response['auxilia']):
        raise ValueError('Choose a legal Roman March route ending without Caesar.')
    drops = response.get('dropoffs', {})
    if not isinstance(drops, dict) or not set(drops) <= set(route[:-1]):
        raise ValueError('Drop-offs must be in intermediate Regions on this route.')
    remaining = {rc.LEGION: response['legions'], rc.AUXILIA: response['auxilia']}
    for region in route[:-1]:
        drop = drops.get(region, {})
        if not isinstance(drop, dict) or set(drop) - set(remaining):
            raise ValueError('Only Legions and Auxilia can drop off from this group.')
        for piece, n in drop.items():
            if type(n) is not int or not 0 <= n <= remaining[piece]:
                raise ValueError('Drop-off counts cannot exceed the remaining group.')
            remaining[piece] -= n
        if not sum(remaining.values()):
            raise ValueError('Leave a moving group to reach the chosen final destination.')


def _march(state, plan):
    from fs_bot.engine.execute import _march_with_harassment
    explicit = {key: plan[key] for key in ('origin', 'route', 'legions', 'auxilia')}
    if 'dropoffs' in plan:
        explicit['dropoffs'] = plan['dropoffs']
    validate_march(state, explicit)
    with free_action_scope(state, rc.ROMANS):
        region = _march_with_harassment(
            state, rc.ROMANS, plan['origin'], plan['route'],
            group_cap={rc.LEGION: plan['legions'], rc.AUXILIA: plan['auxilia']},
            harassers_by_region=plan.get('_harassers'),
            dropoffs_by_region=plan.get('dropoffs'))
    return {'executed': True, 'command': rc.CMD_MARCH, 'origin': plan['origin'],
            'region': region, 'route': list(plan['route']), 'total_cost': 0}


def _np_group(state, origin):
    """8.8.1 extra Auxilia use the Event's actual mandatory departures."""
    legions = min(4, count_pieces(state, origin, rc.ROMANS, rc.LEGION))
    maximum = min(8, count_pieces(state, origin, rc.ROMANS, rc.AUXILIA))
    if not legions or not maximum:
        return None
    own = count_pieces(state, origin, rc.ROMANS)
    others = [count_pieces(state, origin, faction) for faction in rc.FACTIONS if faction != rc.ROMANS]
    opposition = sum(others)
    mandatory_after = own - legions - 1  # Caesar/Successor cannot join this group.
    roman_control = mandatory_after > opposition
    enemy_control = any(n > mandatory_after + opposition - n for n in others)
    for auxilia in range(maximum, 0, -1):
        remaining = own - legions - auxilia
        if roman_control and remaining <= opposition:
            continue
        if not enemy_control and any(n > remaining + opposition - n for n in others):
            continue
        return legions, auxilia


def _battle_action(region, target):
    return {'command': rc.CMD_BATTLE, 'regions': [region], 'sa': 'No SA',
            'details': {'battle_plan': [{'region': region, 'target': target}]}}


def _frost_ok(before, after, region):
    from fs_bot.cards.migration import _frost_ok as permitted
    from fs_bot.engine.game_engine import is_frost, get_sop_factions
    if not before.get('frost') and not is_frost(before):
        return True
    if all(f in before.get('non_player_factions', ()) for f in get_sop_factions(before)):
        return True
    if not permitted(before, after):
        return False
    from fs_bot.bots.roman_bot import _rank_battle_targets
    targets = _rank_battle_targets(after, region, after['scenario'])
    if not targets:
        return True
    from fs_bot.cards.divination_np import _battle_frost_outcomes
    return all(permitted(before, outcome) for outcome in _battle_frost_outcomes(
        after, region, targets[0], attacker=rc.ROMANS, command=True, double_auxilia=True))


def default_plan(state, *, preview=False):
    """Apply Roman origin, destination, group and Harassment instructions.

    The detached availability probe permits a possible human agreement.
    Actual planning obtains each agreement once and carries that decision
    into the March, so a later movement step cannot ask and contradict it.
    """
    from fs_bot.bots.roman_bot import _get_threat_regions, _rank_march_destinations
    from fs_bot.bots.bot_common import random_select
    from fs_bot.engine.execute import _np_harassers
    candidates = []
    agreements = {}
    probe = _copy(state) if preview else state
    if preview:
        from fs_bot.engine.game_engine import get_sop_factions
        players = set(get_sop_factions(state)) - set(state.get('non_player_factions', ()))
        probe['decision_agent'] = lambda board, faction, request: (
            False if faction in players and request.get('request_type') == 'harassment' else None)
    for origin in march_origins(state):
        group = _np_group(state, origin)
        if not group:
            continue
        legions, auxilia = group
        for route in march_routes(state, origin, legions, auxilia):
            # 8.8.1 says the NP Romans March OUT of their selected origin.
            # A human may instead choose the normal in-place March.
            if not route:
                continue
            harassers, losses = {}, 0
            for region in route[:-1]:
                if region not in agreements:
                    agreements[region] = _np_harassers(
                        probe, region, rc.ROMANS, {rc.LEGION: legions, rc.AUXILIA: auxilia})
                harassers[region] = agreements[region]
                losses += sum(n // rc.HARASSMENT_WARBANDS_PER_LOSS for _, n in agreements[region])
            # At most one Loss, which must be absorbed by Auxilia rather
            # than force a Legion roll (8.8.1).
            if losses > 1 or losses > auxilia:
                continue
            plan = {'origin': origin, 'route': route, 'legions': legions,
                    'auxilia': auxilia, '_harassers': harassers}
            after = _copy(state)
            region = _march(after, plan)['region']
            if _frost_ok(state, after, region):
                candidates.append((plan, region, losses))
    threats = set(_get_threat_regions(state, state['scenario']))
    origins = {plan['origin'] for plan, _, _ in candidates}
    threatened = sorted(origins & threats)
    clean = [origin for origin in sorted(origins - threats)
             if not any(count_pieces(state, origin, faction, piece)
                        for faction in rc.FACTIONS if faction != rc.ROMANS
                        for piece in (rc.ALLY, rc.CITADEL, rc.SETTLEMENT))]
    # One group: the first applicable origin tier, then Leader/Legions
    # within the clean-origin tier (8.8.1). Ties use the seeded game RNG.
    origin_tiers = [threatened]
    for key in sorted({(-bool(get_leader_in_region(state, r, rc.ROMANS)),
                       -count_pieces(state, r, rc.ROMANS, rc.LEGION)) for r in clean}):
        origin_tiers.append([r for r in clean if (
            -bool(get_leader_in_region(state, r, rc.ROMANS)),
            -count_pieces(state, r, rc.ROMANS, rc.LEGION)) == key])
    for tier in origin_tiers:
        remaining = list(tier)
        while remaining:
            origin = random_select(state, remaining)
            remaining.remove(origin)
            options = [entry for entry in candidates if entry[0]['origin'] == origin]
            reachable = {region for _, region, _ in options}
            ranked = _rank_march_destinations(state, state['scenario'], allowed_regions=reachable)
            for destination, _ in ranked:
                routes = [entry for entry in options if entry[1] == destination]
                if routes:
                    least = min(entry[2] for entry in routes)
                    return random_select(state, [plan for plan, _, losses in routes if losses == least])
    return None


def resolve_publius(state):
    from fs_bot.cards.card_effects import _event_step
    _event_step(state, "A17.march")
    request = {'kind': 'free_action', 'request_type': 'publius_march',
               'card_id': 'A17', 'free': True, 'with_sa': False}
    plan = consult_free_action(state, rc.ROMANS, request)
    if plan is None:
        plan = default_plan(state)
    if plan is None or plan.get('decline'):
        return [{'free_action': 'march_battle', 'flag': 'card_A17_roman_march_battle',
                 'executed': False, 'declined_no_effect': True, 'reason': 'Publius March declined'}]
    march = _march(state, plan)
    # 'There' is the chosen Caesar-free endpoint, not an intermediate
    # Region where Harassment happened to destroy the marching group.
    region = plan['route'][-1] if plan['route'] else plan['origin']
    from fs_bot.cards.card_effects import _event_step
    _event_step(state, "A17.battle")
    battle_request = {'kind': 'free_action', 'request_type': 'event_command',
                      'card_id': 'A17', 'allowed_commands': [rc.CMD_BATTLE],
                      'allowed_regions': [region], 'max_regions': 1,
                      'free': True, 'with_sa': False, 'double_auxilia': True,
                      'allow_decline': False}
    # A17's single 'may' permits declining the compound action. After a
    # March has been selected, carry out its Battle if possible (5.1.3).
    enemies = [f for f in rc.FACTIONS if f != rc.ROMANS and count_pieces(state, region, f)]
    has_force = any(count_pieces(state, region, rc.ROMANS, p) for p in (rc.LEGION, rc.AUXILIA, rc.LEADER))
    action = consult_free_action(state, rc.ROMANS, battle_request) if enemies and has_force else None
    if action is None:
        from fs_bot.bots.roman_bot import _rank_battle_targets
        targets = _rank_battle_targets(state, region, state['scenario']) if has_force else []
        if has_force and rc.ROMANS not in state.get('non_player_factions', ()) and not targets:
            targets = enemies
        action = _battle_action(region, targets[0]) if targets else None
    if action is None:
        battle = {'executed': False, 'declined_no_effect': True, 'reason': 'No possible Publius Battle'}
    else:
        battle = execute_free_action_plan(state, rc.ROMANS, battle_request, action)
    return [{'free_action': 'march_battle', 'flag': 'card_A17_roman_march_battle',
             'executed': True, 'region': region, 'march': march, 'battle': battle,
             'defender': next((enemy for _, enemy in battle.get('battles_resolved', [])), None),
             'moved': {'legions': plan['legions'], 'auxilia': plan['auxilia']}}]
