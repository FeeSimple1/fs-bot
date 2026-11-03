"""A67: executor chooses beneficiary; beneficiary Marches, Commands, then Hides.

A Card Reference A67, §§5.1, 5.1.1, 5.4. German non-players retain
Arduenna's specific gather-to-Control/Battle priorities in the NP resolver.
"""
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces_by_state, flip_piece
from fs_bot.engine.free_actions import consult_free_action, execute_free_action_plan, command_options

TARGETS = (rc.NERVII, rc.TREVERI)
FLAG = 'card_A67_arduenna'


def factions(state):
    from fs_bot.engine.game_engine import get_sop_factions
    return [f for f in get_sop_factions(state) if f != rc.ARVERNI]


def validate_faction(state, response):
    if set(response) != {'faction'} or response['faction'] not in factions(state):
        raise ValueError('Arduenna grants actions to one playable Faction other than Arverni.')


def march_request():
    return {'kind': 'free_action', 'request_type': 'arduenna_march', 'card_id': 'A67',
            'allowed_commands': [rc.CMD_MARCH], 'required_destinations': list(TARGETS),
            'with_sa': False, 'free': True, 'allow_decline': False, 'validate_default_response': True}


def validate_march(state, faction, response):
    from fs_bot.engine.free_actions import _validate_plan
    details = response.get('details') or {}
    plan = details.get('march_plan') or details
    # Require the same concrete routes the CLI creates. Otherwise the generic
    # normalizer's explicit_moves escape hatch could bypass destination scope.
    if set(plan) - {'origins', 'destinations', 'routes', 'groups', 'extra_groups'}:
        raise ValueError('Arduenna March needs explicit origins, groups and routes into Nervii/Treveri.')
    error = _validate_plan(state, faction, march_request(), response)
    if error:
        raise ValueError(error)


def hide(state, actor):
    """Hide every friendly piece there, including residents; de-Scout only once."""
    flipped = scouted = 0
    for region in TARGETS:
        for piece in (rc.AUXILIA, rc.WARBAND):
            n = count_pieces_by_state(state, region, actor, piece, rc.REVEALED)
            if n:
                flip_piece(state, region, actor, piece, n,
                           from_state=rc.REVEALED, to_state=rc.HIDDEN)
                flipped += n
            n = count_pieces_by_state(state, region, actor, piece, rc.SCOUTED)
            if n:
                flip_piece(state, region, actor, piece, n,
                           from_state=rc.SCOUTED, to_state=rc.REVEALED)
                scouted += n
    return {'free_action': 'flip_hidden', 'flag': FLAG, 'faction': actor,
            'flipped': flipped, 'scouted_removed': scouted,
            'executed': bool(flipped or scouted)}


def _default_sequence(state, actor):
    from fs_bot.engine.execute import _resolve_a67_arduenna, _resolve_card67_arduenna
    results = (_resolve_a67_arduenna(state, actor) if actor == rc.GERMANS
               else _resolve_card67_arduenna(state, actor))
    if actor == rc.GERMANS and not results:
        # German Arduenna instructions decline the complete optional grant
        # without a safe Control/Battle plan. Refusal does not grant hiding.
        return results
    hidden = hide(state, actor)
    if hidden['executed']:
        results.append(hidden)
    return results


def default_march(state, actor):
    """An explicit default retains existing A67 movement priorities only."""
    from fs_bot.engine.execute import _mobile_march_group, _group_has_pieces
    from fs_bot.map.map_data import get_adjacent
    from fs_bot.board.pieces import count_pieces
    from fs_bot.commands.march import march_group
    planning = deepcopy({k: v for k, v in state.items() if k != 'decision_agent'})
    chosen = []
    if actor == rc.GERMANS:
        selected = german_plan(state)
        if selected:
            target, _, origins = selected
            chosen = [(origin, target, group) for origin, group in origins]
    else:
        for target in TARGETS:
            if _group_has_pieces(_mobile_march_group(planning, actor, target)):
                continue
            origins = [r for r in get_adjacent(target, state['scenario'])
                       if r not in TARGETS and r not in [m[0] for m in chosen]
                       and _group_has_pieces(_mobile_march_group(planning, actor, r))]
            if not origins:
                continue
            origin = max(origins, key=lambda r: sum(count_pieces(planning, r, actor, p)
                                                    for p in (rc.LEGION, rc.AUXILIA, rc.WARBAND)))
            group = _mobile_march_group(planning, actor, origin)
            march_group(planning, actor, origin, [target], group, free=True)
            chosen.append((origin, target, group))
    if not chosen:
        return None
    origins = [origin for origin, _, _ in chosen]
    return {'command': rc.CMD_MARCH, 'sa': 'No SA', 'sa_regions': [], 'regions': origins,
            'details': {'march_plan': {'origins': origins,
                'destinations': list(dict.fromkeys(target for _, target, _ in chosen)),
                'routes': {origin: [target] for origin, target, _ in chosen},
                'groups': {origin: group for origin, _, group in chosen}}}}


def command_request(actor):
    return {'kind': 'free_action', 'request_type': 'arduenna_command', 'card_id': 'A67',
            'allowed_commands': [c for c in command_options(actor) if c != rc.CMD_MARCH],
            'allowed_regions': list(TARGETS), 'max_regions': 2,
            'with_sa': False, 'free': True, 'allow_decline': False, 'validate_default_response': True}


def validate_response(state, faction, request, response):
    kind = request['request_type']
    if kind == 'arduenna_faction':
        return validate_faction(state, response)
    if kind == 'arduenna_accept':
        if response != {'accept': True} or type(response.get('accept')) is not bool:
            raise ValueError('Accept the complete Arduenna sequence or decline before acting.')
        return
    if 'command_parts' in (response.get('details') or {}):
        raise ValueError('Arduenna grants one uninterrupted Command without a Special Ability.')
    if kind == 'arduenna_march':
        return validate_march(state, faction, response)
    from fs_bot.engine.free_actions import _validate_plan
    error = _validate_plan(state, faction, request, response)
    if error:
        raise ValueError(error)


def march_witness(state, actor):
    from fs_bot.map.map_data import get_playable_regions_for_state
    from fs_bot.cli.human_plan import _march_routes
    for origin in sorted(get_playable_regions_for_state(state, actor)):
        for route in _march_routes(state, origin, actor):
            if route[-1] in TARGETS:
                return {'command': rc.CMD_MARCH, 'sa': 'No SA', 'sa_regions': [],
                    'regions': [origin], 'details': {'march_plan': {
                        'origins': [origin], 'destinations': [route[-1]],
                        'routes': {origin: route}}}}
    return None


def command_witness(state, actor):
    """Mechanical human choices; a flowchart's IF-NONE is not impossibility."""
    from fs_bot.engine.free_actions import _validate_plan
    from fs_bot.commands.common import free_action_scope
    from fs_bot.cli.recruit_rally import _options
    from fs_bot.board.pieces import count_pieces
    planning = deepcopy({k: v for k, v in state.items() if k != 'decision_agent'})
    planning['_diviciacus_preview'] = True
    candidates = []
    for region in TARGETS:
        if actor == rc.ROMANS:
            candidates.append({'command': rc.CMD_SEIZE, 'regions': [region],
                               'details': {'disperse_regions': []}})
        else:
            candidates.append({'command': rc.CMD_RAID, 'regions': [region],
                'details': {'raid_plan': [{'region': region, 'target': None}]}})
            for enemy in rc.FACTIONS:
                if enemy != actor and count_pieces(planning, region, enemy):
                    candidates.append({'command': rc.CMD_RAID, 'regions': [region],
                        'details': {'raid_plan': [{'region': region, 'target': enemy}]}})
        for enemy in rc.FACTIONS:
            if enemy != actor and count_pieces(planning, region, enemy):
                candidates.append({'command': rc.CMD_BATTLE, 'regions': [region],
                    'details': {'battle_plan': [{'region': region, 'target': enemy}]}})
        with free_action_scope(planning, actor):
            for _, action, values, mixed in _options(planning, actor, region, rally=actor != rc.ROMANS):
                entry = {'region': region, 'action': action}
                if action in ('place_ally', 'place_citadel'):
                    entry['tribe'] = values[0]
                elif mixed:
                    entry['warband_mix'] = values[0]
                else:
                    entry['count'] = values[0]
                candidates.append({'command': rc.CMD_RECRUIT if actor == rc.ROMANS else rc.CMD_RALLY,
                    'regions': [region], 'details': ({'recruit_plan': [entry]} if actor == rc.ROMANS
                                                    else {'rally_plan': {'steps': [entry]}})})
    for action in candidates:
        action.update(sa='No SA', sa_regions=[])
        if _validate_plan(planning, actor, command_request(actor), action) is None:
            return action
    return None


def validate_default(state, actor, request):
    from fs_bot.engine.execute import _resolve_free_command
    trial = deepcopy({k: v for k, v in state.items() if k != 'decision_agent'})
    if request['request_type'] == 'arduenna_march':
        plan = default_march(trial, actor)
        if plan is None:
            return 'No non-player March default is available; choose a legal Arduenna March.'
        try:
            validate_march(trial, actor, plan)
        except (ValueError, TypeError, KeyError) as exc:
            return str(exc)
    else:
        result = _resolve_free_command(trial, actor, allowed_regions=set(TARGETS),
                                       exclude_commands={rc.CMD_MARCH}, _consult=False)
        if not result.get('executed'):
            return 'No non-player Command default is available; choose a legal non-March Command.'
    return None


def consult_mandatory(state, actor, request):
    from fs_bot.engine.agent import consult_agent
    from fs_bot.engine.free_actions import validate_free_action_response
    response = consult_agent(state, actor, request)
    if response is not None:
        error = validate_free_action_response(state, actor, request, response)
        if error:
            raise ValueError(error)
    return (None if response == {'use_default': True} else response), response is not None


def resolve_stage(state, actor, *, marching):
    from fs_bot.engine.execute import _resolve_free_command
    witness = march_witness if marching else command_witness
    attempt, previous_error = 1, None
    while True:
        if witness(state, actor) is None:
            return {'executed': False, 'declined_no_effect': True,
                    'reason': 'No legal March into the targets' if marching else 'No legal non-March Command there'}
        request = march_request() if marching else command_request(actor)
        request['attempt'] = attempt
        if previous_error is not None:
            request['previous_error'] = previous_error
        action, explicit = consult_mandatory(state, actor, request)
        if action is not None:
            result = execute_free_action_plan(state, actor, request, action)
        elif marching:
            action = default_march(state, actor)
            result = (execute_free_action_plan(state, actor, request, action) if action else
                      {'executed': False, 'declined_no_effect': True,
                       'reason': 'Raw callback deferred to an unavailable NP March'})
        else:
            result = _resolve_free_command(state, actor, allowed_regions=set(TARGETS),
                                           exclude_commands={rc.CMD_MARCH}, _consult=False)
        if not explicit or result.get('executed') or witness(state, actor) is None:
            return result
        # A refusal before effects cannot discharge an accepted compulsory
        # action. Keep prior stages and decisions and replan on the live board.
        attempt += 1
        previous_error = result.get('reason', 'The selected action did not execute; choose a new plan')


def resolve(state, chooser):
    from fs_bot.cards.card_effects import _event_step
    from fs_bot.engine.execute import _resolve_free_command
    _event_step(state, 'A67.beneficiary')
    selected = consult_free_action(state, chooser, {
        'kind': 'free_action', 'request_type': 'arduenna_faction',
        'card_id': 'A67', 'factions': factions(state)})
    if selected == {'decline': True}:
        return [{'free_action': 'arduenna', 'flag': FLAG, 'executed': False, 'declined': True}]
    actor = selected['faction'] if selected is not None else chooser
    if actor not in factions(state):
        return [{'free_action': 'arduenna', 'flag': FLAG,
                 'executed': False, 'declined_no_effect': True}]
    if selected is None or actor in state.get('non_player_factions', ()):
        return _default_sequence(state, actor)
    _event_step(state, 'A67.accept', beneficiary=actor)
    accepted = consult_free_action(state, actor, {
        'kind': 'free_action', 'request_type': 'arduenna_accept', 'card_id': 'A67'})
    if accepted is None:
        return _default_sequence(state, actor)
    if accepted == {'decline': True}:
        return [{'free_action': 'arduenna', 'flag': FLAG, 'faction': actor,
                 'executed': False, 'declined': True}]
    _event_step(state, 'A67.march', beneficiary=actor)
    march = resolve_stage(state, actor, marching=True)
    _event_step(state, 'A67.command', beneficiary=actor)
    command = resolve_stage(state, actor, marching=False)
    _event_step(state, 'A67.hide', beneficiary=actor)
    hidden = hide(state, actor)
    return [{'free_action': 'march', 'flag': FLAG, 'faction': actor, 'result': march},
            {'free_action': 'free_command', 'flag': FLAG, 'faction': actor, 'result': command}, hidden]


def german_plan(state):
    """Published German NP safe-surplus and Roman/Aedui/Belgic priority."""
    from fs_bot.rules_consts import GERMANS, ROMANS, AEDUI, BELGAE, FACTIONS, WARBAND, LEADER, NERVII, TREVERI
    from fs_bot.board.pieces import count_pieces, get_leader_in_region
    from fs_bot.board.control import is_controlled_by
    from fs_bot.map.map_data import get_adjacent
    from fs_bot.engine.execute import _group_has_pieces
    from fs_bot.bots.bot_common import random_select
    priority = (ROMANS, AEDUI, BELGAE)

    def other_forces(region):
        return sum(count_pieces(state, region, other)
                   for other in FACTIONS if other != GERMANS)

    def safe_group(origin):
        warbands = count_pieces(state, origin, GERMANS, WARBAND)
        leader = get_leader_in_region(state, origin, GERMANS)
        movable = warbands + int(leader is not None)
        if is_controlled_by(state, origin, GERMANS):
            # Control requires strictly more than ALL other Forces combined.
            # Structures can retain Control without leaving a Warband behind.
            movable = min(movable, max(0,
                count_pieces(state, origin, GERMANS) - other_forces(origin) - 1))
        moving_leader = leader if movable > 0 else None
        return {LEADER: moving_leader,
                WARBAND: min(warbands, movable - int(moving_leader is not None))}

    candidates = []
    for region in (NERVII, TREVERI):
        defender = next((pf for pf in priority
                         if count_pieces(state, region, pf) > 0), None)
        if defender is None:
            continue
        moves = []
        gathered = count_pieces(state, region, GERMANS)
        for origin in get_adjacent(region, state['scenario']):
            group = safe_group(origin)
            if not _group_has_pieces(group):
                continue
            moves.append((origin, group))
            gathered += group[WARBAND] + int(group[LEADER] is not None)
        if gathered > other_forces(region):
            candidates.append((region, defender, moves))
    if not candidates:
        return None
    first_priority = min(priority.index(candidate[1]) for candidate in candidates)
    return random_select(state, [
        candidate for candidate in candidates
        if priority.index(candidate[1]) == first_priority])
