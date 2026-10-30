"""Card72 unshaded: adjacent origins, one destination, then an enemy Battle.

Card Reference 72 and §8.2.3/§8.8.3: the Romans first apply their normal
March priorities; a March without a resulting Battle makes this No Romans.
The executing human chooses both the marching pieces and the enemy attacker.
"""
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, get_leader_in_region
from fs_bot.commands.common import free_action_scope
from fs_bot.map.map_data import get_adjacent_for_state, get_playable_regions_for_state

MARCH_REQUEST = 'impetuosity_unshaded_march'
BATTLE_REQUEST = 'impetuosity_enemy_battle'


def _copy(state):
    return deepcopy({key: value for key, value in state.items() if key != 'decision_agent'})


def origins_by_destination(state, faction):
    from fs_bot.engine.execute import _mobile_march_group, _group_has_pieces
    playable = set(get_playable_regions_for_state(state, faction))
    choices = {}
    for origin in sorted(playable):
        if not _group_has_pieces(_mobile_march_group(state, faction, origin)):
            continue
        for destination in sorted(set(get_adjacent_for_state(state, origin)) & playable):
            choices.setdefault(destination, []).append(origin)
    return choices


def attackers(state, faction, region):
    from fs_bot.engine.execute import _attacker_has_force
    if not count_pieces(state, region, faction):
        return []
    return [enemy for enemy in (rc.ARVERNI, rc.BELGAE) if enemy != faction
            and _attacker_has_force(state, region, enemy)]


def march_action(plan):
    destination = plan['destination']
    return {'command': rc.CMD_MARCH, 'regions': [], 'sa': 'No SA',
            'sa_regions': [], 'details': {'explicit_moves': [
                {'origin': entry['origin'], 'path': [destination],
                 'group': entry['group']} for entry in plan['groups']]}}


def execute_march(state, faction, plan):
    from fs_bot.engine.execute import _execute_march
    from fs_bot.board.control import refresh_all_control
    with free_action_scope(state, faction):
        result = _execute_march(state, faction, march_action(plan))
    refresh_all_control(state)
    return result


def validate_march(state, faction, plan):
    if set(plan) != {'destination', 'groups'}:
        raise ValueError('Choose one destination and its adjacent marching groups.')
    candidates = origins_by_destination(state, faction).get(plan['destination'], [])
    groups = plan['groups']
    if not isinstance(groups, list) or not groups:
        raise ValueError('March from at least one adjacent origin.')
    origins = []
    for entry in groups:
        if not isinstance(entry, dict) or set(entry) != {'origin', 'group'}:
            raise ValueError('Each marching group requires an origin and piece counts.')
        origin, group = entry['origin'], entry['group']
        if origin not in candidates or origin in origins:
            raise ValueError('Choose each adjacent origin once; an in-place March is not allowed.')
        origins.append(origin)
        if not isinstance(group, dict) or not group or set(group) - {
                rc.LEGION, rc.AUXILIA, rc.WARBAND, rc.LEADER}:
            raise ValueError('Select only your mobile pieces for March.')
        for piece, number in group.items():
            if piece == rc.LEADER:
                if type(number) is not bool or (number and not get_leader_in_region(state, origin, faction)):
                    raise ValueError('Select only a Leader present at the origin.')
            elif (type(number) is not int or number < 0
                  or number > count_pieces(state, origin, faction, piece)):
                raise ValueError('March counts must be nonnegative and available at their origin.')
        if not any(group.values()):
            raise ValueError('Each selected origin must move at least one piece.')
    from fs_bot.engine.free_actions import _result_error
    result = execute_march(_copy(state), faction, plan)
    error = _result_error(result)
    if error or not result.get('executed'):
        raise ValueError(error or 'No group can complete this March.')


def roman_plan(state):
    """Normal Roman March priorities, bounded only by the card's move grant.

    Do not filter destinations for Arverni/Belgae before ranking: a higher
    priority March without their Battle makes the Event No Romans.
    """
    from fs_bot.cards.war_fleet_roman import (_destination_sequence, _origin_options,
                                            _choose_origins)
    from fs_bot.engine.execute import _free_command_planning_state, _commit_planning_rng
    from fs_bot.cards.impetuosity import _frost_ok
    choices = origins_by_destination(state, rc.ROMANS)
    planning = _free_command_planning_state(state, rc.ROMANS, forced_command=rc.CMD_MARCH)
    # A one-edge March has no intermediate Harassment. These shared Roman
    # priorities preserve destination tiers and equal-chance origin choices.
    for destination in _destination_sequence(planning, sorted(choices)):
        options = _origin_options(planning, choices[destination], [destination])
        legal = []
        for groups in options:
            plan = {'destination': destination, 'groups': [
                {'origin': origin, 'group': group} for origin, group in groups.items()]}
            validate_march(planning, rc.ROMANS, plan)
            after = _copy(planning)
            execute_march(after, rc.ROMANS, plan)
            if _frost_ok(state, after):
                legal.append(groups)
        if not legal:
            continue
        groups = _choose_origins(planning, legal)
        plan = {'destination': destination, 'groups': [
            {'origin': origin, 'group': group} for origin, group in groups.items()]}
        after = _copy(planning)
        execute_march(after, rc.ROMANS, plan)
        if not _np_attackers(state, after, rc.ROMANS, destination):
            return None
        _commit_planning_rng(state, planning)
        return plan
    return None


def _battle_action(region, target):
    return {'command': rc.CMD_BATTLE, 'regions': [region], 'sa': 'No SA',
            'sa_regions': [], 'details': {'battle_plan': [{'region': region, 'target': target}]}}


def _np_attackers(before, after, faction, region):
    choices = attackers(after, faction, region)
    from fs_bot.engine.game_engine import is_frost, get_sop_factions
    if not (before.get('frost') or is_frost(before)) or not (
            set(get_sop_factions(before)) - set(before.get('non_player_factions', ()))):
        return choices
    from fs_bot.cards.divination_np import _battle_frost_outcomes
    from fs_bot.cards.impetuosity import _frost_ok
    return [enemy for enemy in choices if all(_frost_ok(before, outcome)
        for outcome in _battle_frost_outcomes(after, region, faction,
                                             attacker=enemy, command=True))]


def default_attacker(state, faction, region, *, before=None):
    """§8.3.1: preserve own pieces, then maximize enemy removals; random ties.

    Use the shared bot prediction's failed-saving-roll assumption on detached
    full Commands so pre-fire, Counterattack and once-per-Command capabilities
    contribute. Hypothetical rolls and Retreat consultations never reach the
    live board or a human agent.
    """
    from fs_bot.bots.bot_common import _AllRemovalsRng, random_select
    from fs_bot.engine.free_actions import execute_free_action_plan, _result_error
    choices = (_np_attackers(before or state, state, faction, region)
               if faction in state.get('non_player_factions', ()) else attackers(state, faction, region))
    ranks = []
    pieces = (rc.LEADER, rc.LEGION, rc.CITADEL, rc.FORT, rc.ALLY, rc.AUXILIA, rc.WARBAND)
    for enemy in choices:
        sim = _copy(state)
        sim['rng'] = _AllRemovalsRng()
        result = execute_free_action_plan(sim, faction, {'acting_faction': enemy},
                                         _battle_action(region, faction))
        error = _result_error(result)
        if error:
            raise ValueError(f'Impetuosity Battle preview failed: {error}')
        own = tuple(sum(count_pieces(sim, r, faction, piece) - count_pieces(state, r, faction, piece)
                        for r in state['spaces']) for piece in pieces)
        removed = tuple(sum(count_pieces(state, r, enemy, piece) - count_pieces(sim, r, enemy, piece)
                           for r in state['spaces']) for piece in (rc.LEGION, rc.CITADEL, rc.ALLY))
        other = sum(count_pieces(state, r, enemy) - count_pieces(sim, r, enemy)
                    for r in state['spaces']) - sum(removed)
        ranks.append((own + removed + (other,), enemy))
    if not ranks:
        return None
    best = max(rank for rank, _ in ranks)
    return random_select(state, [enemy for rank, enemy in ranks if rank == best])


def resolve_impetuosity_unshaded(state, faction):
    from fs_bot.engine.free_actions import consult_free_action, execute_free_action_plan
    from fs_bot.cards.card_effects import _event_step
    _event_step(state, "72.march")
    request = {'kind': 'free_action', 'request_type': MARCH_REQUEST,
               'card_id': 72, 'free': True, 'with_sa': False}
    plan = consult_free_action(state, faction, request)
    if plan is None:
        plan = roman_plan(state) if faction == rc.ROMANS else None
    if (plan is None and faction not in state.get('non_player_factions', ())
            and origins_by_destination(state, faction)):
        raise ValueError('No bot default applies; choose the required Impetuosity March explicitly.')
    if plan is None or plan.get('decline'):
        return [{'free_action': 'march_enemy_battle', 'flag': 'card_72',
                 'executed': False, 'declined_no_effect': True,
                 'reason': 'Impetuosity March declined'}]
    before = _copy(state)
    march = execute_march(state, faction, plan)
    region = plan['destination']
    from fs_bot.cards.card_effects import _event_step
    _event_step(state, "72.enemy_battle")
    choices = attackers(state, faction, region)
    battle = None
    if choices:
        request = {'kind': 'free_action', 'request_type': BATTLE_REQUEST,
                   'card_id': 72, 'region': region, 'attackers': choices,
                   'free': True, 'with_sa': False}
        response = consult_free_action(state, faction, request)
        enemy = response['attacker'] if response else default_attacker(state, faction, region, before=before)
        action = _battle_action(region, faction)
        # The executor chooses the attacker; normal Battle then consults the
        # actual defender and owners for Retreat and Losses. No Ambush grant.
        battle = execute_free_action_plan(state, faction,
            {'acting_faction': enemy, 'with_sa': False}, action)
    return [{'free_action': 'march_enemy_battle', 'flag': 'card_72',
             'executed': march['executed'], 'region': region, 'march': march,
             'attacker': enemy if choices else None, 'battle': battle}]
