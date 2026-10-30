"""Morasses shaded: the selected Gallic Faction Ambushes, then Marches.

Card36 waives Hidden/Leader requirements for the granted Ambush. The Belgic
instruction overrides its usual March chart: March in place to go Hidden.
All other granted Commands retain §8.2.3's conditions and priorities.
"""
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_leader_in_region
from fs_bot.commands.common import free_action_scope
from fs_bot.engine.free_actions import consult_free_action, execute_free_action_plan
from fs_bot.map.map_data import get_playable_regions_for_state


def _copy(state):
    return deepcopy({k: v for k, v in state.items() if k != 'decision_agent'})


def battle_request():
    return {'kind': 'free_action', 'request_type': 'event_command', 'card_id': 36,
            'allowed_commands': [rc.CMD_BATTLE], 'with_sa': True,
            'morasses_ambush': True, 'free': True}


def march_request():
    return {'kind': 'free_action', 'request_type': 'morasses_march', 'card_id': 36,
            'allowed_commands': [rc.CMD_MARCH], 'with_sa': False, 'free': True}


def origins(state, faction):
    return sorted(r for r in get_playable_regions_for_state(state, faction)
                  if count_pieces(state, r, faction, rc.WARBAND)
                  or get_leader_in_region(state, r, faction))


def validate_faction(state, faction, response):
    if set(response) != {'faction'} or response['faction'] not in rc.GALLIC_FACTIONS:
        raise ValueError('Morasses grants actions to one Gallic Faction.')


def _moving_origins(state, faction, action):
    from fs_bot.engine.execute import _collect_march_moves
    if action is None:
        return set()
    moves, _ = _collect_march_moves(_copy(state), faction, action)
    return {move['origin'] for move in moves}


def validate_march(state, faction, response):
    from fs_bot.engine.free_actions import _validate_plan
    if set(response) != {'action', 'in_place'}:
        raise ValueError('Choose a March action and/or in-place origins.')
    regions = response['in_place']
    if (not isinstance(regions, list) or any(not isinstance(r, str) for r in regions)
            or len(regions) != len(set(regions))
            or not set(regions).issubset(origins(state, faction))):
        raise ValueError('Select distinct playable in-place origins with your mobile pieces.')
    action = response['action']
    if action is None and not regions:
        raise ValueError('Select at least one March origin, or decline.')
    if action is not None:
        if not isinstance(action, dict):
            raise ValueError('The moving March must be a complete action.')
        if set(regions) & _moving_origins(state, faction, action):
            raise ValueError('Select each March origin only once.')
        error = _validate_plan(state, faction, march_request(), action)
        if error:
            raise ValueError(error)


def execute_march(state, faction, response):
    from fs_bot.commands.march import _flip_origin_pieces
    # All selected origins flip BEFORE movement. An arriving group must not
    # be hidden a second time merely because its destination also stays put.
    with free_action_scope(state, faction):
        flips = {r: _flip_origin_pieces(state, r, faction) for r in response['in_place']}
        moving = (execute_free_action_plan(state, faction, march_request(), response['action'])
                  if response['action'] is not None else None)
    return {'executed': bool(flips) or bool(moving and moving.get('executed')),
            'command': rc.CMD_MARCH, 'in_place': flips, 'moving': moving}


def ambush_active(state, region):
    return state.get('_morasses_ambush') and (
        state.get('_morasses_ambush_region') in (None, region))


def ambush_prediction(state, region, attacker, defender):
    """Actual Command pre-fire, then best-case Defender loss rolls (§8.7.1).

    Caesar's ability to retain Counterattack is possible even with Ambush.
    Own pre-fire rolls remove pieces, exposing every possible Leader Loss.
    The observer sees the board after Card13/27 and while Card59 is scoped.
    """
    from fs_bot.engine.execute import _execute_battle
    from fs_bot.battle.losses import calculate_losses
    trial = _copy(state)
    prediction = {'inflicted': 0, 'taken': 0, 'attacker_leader_lost': False}
    initial = count_pieces(trial, region, attacker)
    initial_enemy = count_pieces(trial, region, defender)
    leader = get_leader_in_region(trial, region, attacker)
    class RemovalRng:
        caesar = False
        def randint(self, low, high):
            if self.caesar:
                self.caesar = False
                return high
            return low
        def choice(self, values): return values[0]
        def random(self): return 0.0
        def shuffle(self, values): pass
    rng = RemovalRng()
    trial['rng'] = rng
    def observe(phase, board, selected_region, enemy, result):
        if phase == 'before':
            prediction['inflicted'] = (initial_enemy - count_pieces(board, region, enemy)
                                      + calculate_losses(board, region, attacker, enemy))
            prediction['taken'] = initial - count_pieces(board, region, attacker)
            rng.caesar = (ambush_active(state, region)
                          and get_leader_in_region(board, region, enemy) == rc.CAESAR
                          and not count_pieces(board, region, enemy, rc.FORT)
                          and not count_pieces(board, region, enemy, rc.CITADEL))
        else:
            counter = result.get('counterattack') or {}
            prediction['taken'] += counter.get('losses_taken', 0) + counter.get('losses_absorbed', 0)
    plan = _battle_action([{'region': region, 'target': defender}],
                         [region] if ambush_active(state, region) else [])
    with free_action_scope(trial, attacker):
        _execute_battle(trial, attacker, plan, _ambush_anywhere=True, _battle_observer=observe)
    prediction['attacker_leader_lost'] = bool(leader and not get_leader_in_region(trial, region, attacker))
    return prediction


def _battle_action(plan, ambush_regions=None):
    return {'command': rc.CMD_BATTLE, 'regions': [e['region'] for e in plan],
            'sa': rc.SA_AMBUSH if ambush_regions != [] else 'No SA',
            'sa_regions': [e['region'] for e in plan] if ambush_regions is None else ambush_regions,
            'details': {'battle_plan': plan}}


def default_battle(state, faction):
    from fs_bot.battle.losses import calculate_losses
    from fs_bot.engine.execute import _free_command_planning_state, _commit_planning_rng
    planning = _free_command_planning_state(state, faction, forced_command=rc.CMD_BATTLE,
        exclude_commands=[rc.CMD_MARCH, rc.CMD_RALLY, rc.CMD_RAID], with_sa=False)
    planning['_morasses_ambush'] = True
    if faction == rc.BELGAE:
        # Printed instruction: Romans THEN Gauls, never Germans; one enemy
        # per Region. March after these Battles will hide survivors in place.
        plan, used = [], set()
        for enemy in (rc.ROMANS, rc.AEDUI, rc.ARVERNI):
            for region in sorted(get_playable_regions_for_state(planning, faction)):
                if (region not in used and count_pieces(planning, region, enemy)
                        and (count_pieces(planning, region, faction, rc.WARBAND)
                             or get_leader_in_region(planning, region, faction))
                        and calculate_losses(planning, region, faction, enemy) > 0):
                    plan.append({'region': region, 'target': enemy})
                    used.add(region)
        action = _battle_action(plan) if plan else None
    elif faction == rc.ARVERNI:
        from fs_bot.bots.arverni_bot import node_v_battle
        action = node_v_battle(planning)
    elif faction == rc.AEDUI:
        from fs_bot.bots.aedui_bot import node_a_battle
        # §4.4.3's one-Region limit survives the Hidden/location waiver.
        # Try the normal high-value priority with each possible first Ambush.
        action = None
        for region in sorted(get_playable_regions_for_state(planning, faction)):
            planning['_morasses_ambush_region'] = region
            candidate = node_a_battle(planning)
            if (candidate.get('command') == rc.CMD_BATTLE
                    and any(e['region'] == region for e in candidate['details']['battle_plan'])):
                from fs_bot.cards.morasses_np import safe_battle_plan
                candidate = _battle_action(candidate['details']['battle_plan'], [region])
                action = safe_battle_plan(state, faction, candidate)
                if action is not None:
                    _commit_planning_rng(state, planning)
                    return action
        return None
    else:
        return None
    if not action or action.get('command') != rc.CMD_BATTLE:
        return None
    action = _battle_action(action['details']['battle_plan'],
                            [planning['_morasses_ambush_region']] if faction == rc.AEDUI else None)
    from fs_bot.cards.morasses_np import safe_battle_plan
    action = safe_battle_plan(state, faction, action)
    if action is not None:
        _commit_planning_rng(state, planning)
    return action


def default_march(state, faction, *, under_threat=False):
    if faction == rc.BELGAE:
        regions = [r for r in origins(state, faction)
                   if any(count_pieces_by_state(state, r, faction, rc.WARBAND, visibility)
                          for visibility in (rc.REVEALED, rc.SCOUTED))]
        return {'action': None, 'in_place': regions} if regions else None
    from fs_bot.engine.execute import _free_command_planning_state, _commit_planning_rng
    from fs_bot.bots.arverni_bot import node_v_march_mass, node_v_march_threat
    from fs_bot.bots.aedui_bot import node_a_march
    planning = _free_command_planning_state(state, faction, forced_command=rc.CMD_MARCH,
        exclude_commands=[rc.CMD_BATTLE, rc.CMD_RALLY, rc.CMD_RAID], with_sa=False)
    # §8.2.3: use the bottom March box if none was specified.
    node = (node_v_march_threat if under_threat else node_v_march_mass) if faction == rc.ARVERNI else node_a_march
    action = node(planning)
    if not action or action.get('command') != rc.CMD_MARCH:
        return None
    from fs_bot.engine.execute import march_plan_has_effect
    if not march_plan_has_effect(planning, faction, action.get('details') or {}):
        return None
    action['sa'], action['sa_regions'] = 'No SA', []
    response = {'action': action, 'in_place': []}
    from fs_bot.cards.morasses_np import safe
    if not safe(state, faction, lambda board: execute_march(board, faction, response)):
        return None
    _commit_planning_rng(state, planning)
    return response


def _march_under_threat(state, faction):
    if faction != rc.ARVERNI:
        return False
    from fs_bot.engine.execute import _free_command_planning_state
    from fs_bot.bots.arverni_bot import node_v_battle, _get_threat_regions
    planning = _free_command_planning_state(state, faction, forced_command=rc.CMD_BATTLE,
        exclude_commands=[rc.CMD_RALLY, rc.CMD_RAID], with_sa=False)
    planning['_morasses_ambush'] = True
    return bool(_get_threat_regions(planning, planning['scenario'])
                and node_v_battle(planning).get('command') == rc.CMD_MARCH)


def np_available(state, faction):
    if faction not in rc.GALLIC_FACTIONS:
        return False  # §8.2.3: may select only itself as beneficiary.
    trial = _copy(state)
    # A loss-causing Battle is effective even if its following March cannot
    # change anything. Conversely an existing Revealed group can hide alone.
    return bool(default_battle(trial, faction) or default_march(
        trial, faction, under_threat=_march_under_threat(trial, faction)))


def _declined(command, explicit):
    return {'executed': False, 'command': command,
            'declined': explicit, 'declined_no_effect': not explicit,
            'reason': f'Morasses {command} declined' if explicit else f'No applicable Morasses {command}'}


def resolve_morasses(state, chooser):
    from fs_bot.cards.card_effects import _event_step
    _event_step(state, "36.beneficiary")
    selected = consult_free_action(state, chooser, {
        'kind': 'free_action', 'request_type': 'morasses_faction', 'card_id': 36,
        'factions': list(rc.GALLIC_FACTIONS)})
    if selected == {'decline': True}:
        return [{'free_action': 'ambush_then_march', 'flag': 'card_36',
                 'executed': False, 'declined': True}]
    if selected is None:
        candidates = [chooser] if chooser in rc.GALLIC_FACTIONS else list(rc.GALLIC_FACTIONS)
        if chooser in state.get('non_player_factions', set()) and chooser not in rc.GALLIC_FACTIONS:
            candidates = []
        actor = next((f for f in candidates if np_available(state, f)), None)
        if actor is None:
            return [{'free_action': 'ambush_then_march', 'flag': 'card_36',
                     'executed': False, 'declined_no_effect': True,
                     'reason': 'No applicable Morasses action'}]
    else:
        actor = selected['faction']
    from fs_bot.cards.card_effects import _event_step
    _event_step(state, "36.battle")
    under_threat = _march_under_threat(state, actor)
    request = battle_request()
    battle = consult_free_action(state, actor, request)
    if battle is None:
        battle = default_battle(state, actor)
    battle_result = (_declined(rc.CMD_BATTLE, battle is not None)
                     if battle is None or battle == {'decline': True}
                     else execute_free_action_plan(state, actor, request, battle))
    from fs_bot.cards.card_effects import _event_step
    _event_step(state, "36.march")
    march = consult_free_action(state, actor, march_request())
    if march is None:
        march = default_march(state, actor, under_threat=under_threat)
    march_result = (_declined(rc.CMD_MARCH, march is not None)
                    if march is None or march == {'decline': True}
                    else execute_march(state, actor, march))
    return [{'free_action': 'ambush_then_march', 'flag': 'card_36',
             'faction': actor, 'battle': battle_result, 'march': march_result,
             'executed': battle_result['executed'] or march_result['executed']}]
