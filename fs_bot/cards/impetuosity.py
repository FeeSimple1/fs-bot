"""Card72 shaded: one Hidden group Marches, and only it may Battle.

The Event's own piece restriction is checked before origin flipping. Ordinary
March still hides the other Revealed Warbands at its selected origin (§3.3.2).
The Battle uses a force view, preserving physical counters and Control.
"""
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_leader_in_region
from fs_bot.board.control import is_controlled_by
from fs_bot.commands.common import free_action_scope
from fs_bot.commands.sa_enlist import scoped_free_force, FREE_FORCE_KEY
from fs_bot.engine.free_actions import consult_free_action, execute_free_action_plan
from fs_bot.map.map_data import get_playable_regions_for_state, get_adjacent_for_state


def _copy(state):
    return deepcopy({key: value for key, value in state.items() if key != 'decision_agent'})


def march_choices(state, faction):
    """Each legal origin/destination and its original Hidden-group maximum."""
    choices = []
    playable = set(get_playable_regions_for_state(state, faction))
    for origin in sorted(playable):
        hidden = count_pieces_by_state(state, origin, faction, rc.WARBAND, rc.HIDDEN)
        if not hidden:
            continue
        for destination in sorted(({origin} | set(get_adjacent_for_state(state, origin))) & playable):
            choices.append({'origin': origin, 'destination': destination, 'maximum': hidden})
    return choices


def validate_march(state, faction, response):
    if not isinstance(response, dict) or set(response) != {'origin', 'destination', 'warbands'}:
        raise ValueError('Impetuosity requires one origin, destination, and Warband count; no Leader.')
    n = response['warbands']
    if type(n) is not int or n < 1:
        raise ValueError('Impetuosity Warbands must be a positive integer.')
    if not any(c['origin'] == response['origin'] and c['destination'] == response['destination']
               and n <= c['maximum'] for c in march_choices(state, faction)):
        raise ValueError('Choose one original Hidden group and an adjacent or in-place destination.')


def _march(state, faction, plan):
    from fs_bot.commands.march import _flip_origin_pieces, march_group
    validate_march(state, faction, plan)
    origin, destination, n = plan['origin'], plan['destination'], plan['warbands']
    with free_action_scope(state, faction):
        flipped = _flip_origin_pieces(state, origin, faction)
        result = march_group(state, faction, origin,
                             [] if destination == origin else [destination],
                             {rc.WARBAND: n}, free=True)
    return dict(result, executed=True, command=rc.CMD_MARCH, origin_flips=flipped)


def _players(state, faction):
    from fs_bot.engine.game_engine import get_sop_factions
    return set(get_sop_factions(state)) - set(state.get('non_player_factions', ())) - {faction}


def _frost_ok(before, after):
    from fs_bot.engine.game_engine import is_frost
    from fs_bot.engine.victory import calculate_victory_margin
    if not before.get('frost') and not is_frost(before):
        return True
    # Victory uses the physical board, including resident Citadels and
    # Settlements excluded from this one group's Battle force.
    after = {key: value for key, value in after.items() if key != FREE_FORCE_KEY}
    return all(calculate_victory_margin(after, f) <= max(0, calculate_victory_margin(before, f))
               for f in _players(before, None))


def _belgic_leader_safe(state):
    """A72: the physical Belgic Leader must end with at least four Warbands."""
    physical = {key: value for key, value in state.items() if key != FREE_FORCE_KEY}
    return any(get_leader_in_region(physical, r, rc.BELGAE)
               and count_pieces(physical, r, rc.BELGAE, rc.WARBAND) >= 4
               for r in physical['spaces'])


def _battle_outcomes_ok(before, after, faction, target, region, n):
    from fs_bot.engine.game_engine import is_frost
    if not _frost_ok(before, after):
        return False
    leader_floor = (faction == rc.BELGAE and before['scenario'] in rc.ARIOVISTUS_SCENARIOS
                    and get_leader_in_region(after, region, faction))
    if not before.get('frost') and not is_frost(before) and not leader_floor:
        return True
    from fs_bot.cards.divination_np import _battle_frost_outcomes
    with scoped_free_force(after, region, {rc.HIDDEN: n}, faction=faction, source='Impetuosity'):
        return all(_frost_ok(before, outcome)
                   and (not leader_floor or _belgic_leader_safe(outcome))
                   for outcome in _battle_frost_outcomes(
                       after, region, target, attacker=faction, command=True))


def np_choices(state, faction):
    """Printed Impetuosity directives, before the Event is selected."""
    if faction not in (rc.ARVERNI, rc.BELGAE, rc.GERMANS):
        return []
    players = _players(state, faction)
    if not players:
        return []
    from fs_bot.engine.game_engine import is_frost
    frost = state.get('frost') or is_frost(state)
    choices = []
    for option in march_choices(state, faction):
        origin, destination = option['origin'], option['destination']
        targets = {f for f in players if count_pieces(state, destination, f)}
        if faction in (rc.ARVERNI, rc.GERMANS):
            targets &= {rc.ROMANS, rc.AEDUI, rc.BELGAE}
        if not targets:
            continue
        maximum = option['maximum']
        if faction == rc.GERMANS and origin != destination and is_controlled_by(state, origin, faction):
            own = count_pieces(state, origin, faction)
            opposition = count_pieces(state, origin) - own
            maximum = min(maximum, own - opposition - 1)
        if (faction == rc.BELGAE and state['scenario'] in rc.ARIOVISTUS_SCENARIOS
                and origin != destination and get_leader_in_region(state, origin, faction)):
            maximum = min(maximum, count_pieces(state, origin, faction, rc.WARBAND) - 4)
        if maximum < 1:
            continue
        # Frost or the A72 Leader floor can make the largest group illegal
        # while a smaller cohort preserves Control or limits Battle losses.
        leader_floor = (faction == rc.BELGAE and state['scenario'] in rc.ARIOVISTUS_SCENARIOS
                        and get_leader_in_region(state, destination, faction))
        accepted = set()
        for n in range(maximum, 0 if frost or leader_floor else maximum - 1, -1):
            plan = {'origin': origin, 'destination': destination, 'warbands': n}
            after = _copy(state)
            _march(after, faction, plan)
            if faction == rc.BELGAE and state['scenario'] in rc.ARIOVISTUS_SCENARIOS:
                if not _belgic_leader_safe(after):
                    continue
            if faction in (rc.ARVERNI, rc.GERMANS) and not is_controlled_by(after, destination, faction):
                continue
            for target in sorted(targets - accepted):
                if not _battle_outcomes_ok(state, after, faction, target, destination, n):
                    continue
                choices.append(dict(plan, target=target))
                accepted.add(target)
            if accepted == targets:
                break
    return choices


def default_plan(state, faction):
    from fs_bot.bots.bot_common import random_select
    from fs_bot.engine.victory import calculate_victory_margin
    choices = np_choices(state, faction)
    if not choices:
        return None
    if faction in (rc.ARVERNI, rc.GERMANS):
        priority = lambda c: (-(rc.ROMANS, rc.AEDUI, rc.BELGAE).index(c['target']), c['warbands'])
    else:
        priority = lambda c: (calculate_victory_margin(state, c['target']), c['warbands'])
    best = max(map(priority, choices))
    return random_select(state, [c for c in choices if priority(c) == best])


def _battle_action(region, target):
    return {'command': rc.CMD_BATTLE, 'regions': [region], 'sa': 'No SA',
            'sa_regions': [], 'details': {'battle_plan': [{'region': region, 'target': target}]}}


def _default_target(state, faction, region):
    """The Event's player-target priority after an explicitly chosen March."""
    from fs_bot.bots.bot_common import random_select
    from fs_bot.engine.victory import calculate_victory_margin
    state = {key: value for key, value in state.items() if key != FREE_FORCE_KEY}
    targets = [f for f in sorted(_players(state, faction))
               if count_pieces(state, region, f)]
    if faction in (rc.ARVERNI, rc.GERMANS):
        return next((f for f in (rc.ROMANS, rc.AEDUI, rc.BELGAE) if f in targets), None)
    if faction == rc.BELGAE and targets:
        best = max(calculate_victory_margin(state, f) for f in targets)
        return random_select(state, [f for f in targets
                                     if calculate_victory_margin(state, f) == best])
    return None


def resolve_impetuosity(state, faction):
    """Resolve separate player March and optional Battle choices."""
    from fs_bot.cards.card_effects import _event_step
    _event_step(state, "72.march")
    request = {'kind': 'free_action', 'request_type': 'impetuosity_march',
               'card_id': 72, 'free': True, 'with_sa': False}
    plan = consult_free_action(state, faction, request)
    target = None
    if plan is None:
        plan = default_plan(state, faction)
        if plan:
            target = plan.pop('target')
    if plan is None or plan.get('decline'):
        return [{'free_action': 'march_battle', 'flag': 'card_72_hidden_march_battle',
                 'executed': False, 'declined_no_effect': True, 'reason': 'Impetuosity March declined'}]
    march = _march(state, faction, plan)
    region, n = plan['destination'], plan['warbands']
    battle_request = {'kind': 'free_action', 'request_type': 'event_command',
                      'card_id': 72, 'allowed_commands': [rc.CMD_BATTLE],
                      'allowed_regions': [region], 'max_regions': 1,
                      'free': True, 'with_sa': False}
    with scoped_free_force(state, region, {rc.HIDDEN: n}, faction=faction, source='Impetuosity'):
        from fs_bot.cards.card_effects import _event_step
        _event_step(state, "72.battle")
        action = consult_free_action(state, faction, battle_request)
        if action is None:
            if target is None:
                target = _default_target(state, faction, region)
            action = _battle_action(region, target) if target else {'decline': True}
        if action.get('decline'):
            battle = {'executed': False, 'declined_no_effect': True,
                      'reason': 'Impetuosity optional Battle declined'}
        else:
            battle = execute_free_action_plan(state, faction, battle_request, action)
    return [{'free_action': 'march_battle', 'flag': 'card_72_hidden_march_battle',
             'executed': True, 'source': plan['origin'], 'region': region,
             'defender': next((target for _, target in battle.get('battles_resolved', [])), None),
             'warbands_marched': n, 'march': march, 'battle': battle}]
