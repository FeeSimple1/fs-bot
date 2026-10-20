"""Card 57's ordered free March, Britannia Special Ability, and final bonus."""
from fs_bot.rules_consts import (ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
                                 BRITANNIA, MORINI, ATREBATES, VENETI)
from fs_bot.commands.common import free_action_scope
from fs_bot.engine.free_actions import consult_free_action, execute_free_action_plan


def _default_special_ability(state, faction):
    """Use the faction's SA priority with plans restricted before allocation."""
    allowed = {BRITANNIA}
    action = {'command': None, 'regions': [], 'sa': 'No SA',
              'sa_regions': [], 'details': {}}
    scenario = state['scenario']
    if faction == ROMANS:
        from fs_bot.bots.roman_bot import node_r_build, node_r_scout
        plan = node_r_build(state, allowed_regions=allowed)
        if any(plan.values()):
            action.update(sa='Build', sa_regions=[BRITANNIA], details={'build_plan': plan})
        else:
            plan = node_r_scout(state, allowed_regions=allowed)
            if any(plan.values()):
                action.update(sa='Scout', sa_regions=[BRITANNIA], details={'scout_plan': plan})
    elif faction == ARVERNI:
        from fs_bot.bots.arverni_bot import _check_devastate, _check_entreat
        regions = _check_devastate(state, scenario, allowed_regions=allowed)
        if regions:
            action.update(sa='Devastate', sa_regions=regions)
        else:
            plan = _check_entreat(state, scenario, allowed_regions=allowed)
            if plan:
                action.update(sa='Entreat', sa_regions=plan)
    elif faction == AEDUI:
        from fs_bot.bots.aedui_bot import _determine_trade_sa
        sa, regions, details = _determine_trade_sa(state, scenario, allowed_regions=allowed)
        action.update(sa=sa, sa_regions=regions, details=details)
    elif faction == BELGAE:
        from fs_bot.bots.belgae_bot import _check_rampage, _check_enlist_after_command
        plan = _check_rampage(state, scenario, allowed_regions=allowed)
        if plan:
            action.update(sa='Rampage', sa_regions=plan)
        else:
            plan = _check_enlist_after_command(state, scenario, allowed_regions=allowed)
            if plan:
                action.update(sa='Enlist', sa_regions=[BRITANNIA], details={'enlist': plan})
    return action if action['sa'] not in (None, 'No SA') else None


def resolve_britannia(state, executing_faction):
    """Resolve all possible text, including when the Faction is already there."""
    from fs_bot.engine import execute as ex
    from fs_bot.board.pieces import count_pieces
    from fs_bot.cards.card_effects import _cap_resources
    from fs_bot.map.map_data import get_playable_regions
    faction = state.get('event_modifiers', {}).get('card_57_faction', executing_faction)
    if faction == GERMANS:
        return [{'free_action': 'march', 'flag': 'card_57', 'executed': False,
                 'reason': 'Germans cannot receive Card 57'}]
    if BRITANNIA not in get_playable_regions(state['scenario'], state.get('capabilities')):
        return [{'free_action': 'march', 'flag': 'card_57', 'executed': False,
                 'reason': 'Britannia not in play'}]
    with free_action_scope(state, faction):
        request = {'kind': 'free_action', 'request_type': 'event_command',
                   'allowed_commands': ['March'], 'allowed_regions': None,
                   'required_destinations': [BRITANNIA], 'max_regions': None,
                   'with_sa': False, 'free': True}
        response = consult_free_action(state, faction, request)
        if response is None:
            # Default chooses the largest adjacent mobile group, retaining
            # the ordinary stop and Harassment procedures for the crossing.
            sources = [r for r in (MORINI, ATREBATES, VENETI)
                       if ex._group_has_pieces(ex._mobile_march_group(state, faction, r))]
            if sources:
                from fs_bot.rules_consts import LEGION, AUXILIA, WARBAND, LEADER
                def size(region):
                    group = ex._mobile_march_group(state, faction, region)
                    return sum(group.get(p, 0) for p in (LEGION, AUXILIA, WARBAND)) + bool(group.get(LEADER))
                origin = max(sources, key=size)
                response = {'command': 'March', 'regions': [], 'sa': 'No SA',
                            'sa_regions': [], 'details': {
                                'origins': [origin], 'destinations': [BRITANNIA],
                                'routes': {origin: [BRITANNIA]}}}
        march = {'executed': False, 'command': 'March', 'reason': 'no March selected'}
        if response is not None and not response.get('decline'):
            march = execute_free_action_plan(state, faction, request, response)

        from fs_bot.cli.human_plan import _faction_special_abilities
        request = {'kind': 'free_action', 'request_type': 'event_sa',
                   'allowed_commands': [], 'allowed_regions': [BRITANNIA],
                   'allowed_sas': [sa for sa in _faction_special_abilities(faction, state['scenario'])
                                   if sa not in ('Ambush', 'Besiege')],
                   'max_regions': 1, 'with_sa': True, 'free': True}
        response = consult_free_action(state, faction, request)
        if response is None:
            response = _default_special_ability(state, faction)
        sa_result = {'executed': False, 'reason': 'no Special Ability selected'}
        if response is not None and not response.get('decline'):
            sa_result = execute_free_action_plan(state, faction, request, response)
        before = state['resources'].get(faction, 0)
        if count_pieces(state, BRITANNIA, faction) > 0:
            _cap_resources(state, faction, 4)
        bonus = state['resources'].get(faction, 0) - before
    moves = march.get('marches') or []
    return [{'free_action': 'march', 'flag': 'card_57_march_britannia',
             'faction': faction, 'result': march, 'sa_execution': sa_result,
             'source': moves[0].get('origin') if moves else None,
             'final_region': moves[0].get('final_region') if moves else None,
             'resources_bonus': bonus}]
