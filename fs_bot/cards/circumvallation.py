"""Numeric4: Roman-owned optional adjacent March and subsequent marker placement.

Persistent marked-group mechanics remain a separately documented repair.
"""
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces
from fs_bot.commands.common import free_action_scope
from fs_bot.engine.diviciacus import eligible_regions,force_scope
from fs_bot.engine.free_actions import consult_free_action,_explicit_sentinel
from fs_bot.map.map_data import get_playable_regions_for_state

REQUEST='circumvallation_march'
FLAG='card_4_free_march_to'


def _copy(state):
    return deepcopy({k:v for k,v in state.items() if k!='decision_agent'})


def targets(state):
    return [r for r in sorted(get_playable_regions_for_state(state,rc.ROMANS))
            if any(count_pieces(state,r,f,rc.CITADEL) for f in rc.FACTIONS if f!=rc.ROMANS)]


def initial_target(state):
    raw=state.get('event_params');params={} if raw is None else raw
    if not isinstance(params,dict) or set(params)-{'target_region','stage_timing_actions'}:
        raise ValueError('Circumvallation accepts its legacy target and Event timing only.')
    target=params.get('target_region')
    if target is not None and (not isinstance(target,str) or target not in targets(state)):
        raise ValueError('The Circumvallation destination must contain a non-Roman Citadel.')
    return target


def pools(state):
    from fs_bot.engine.execute import _mobile_march_group
    return {r:_mobile_march_group(state,rc.ROMANS,r)
            for r in sorted(get_playable_regions_for_state(state,rc.ROMANS))
            if count_pieces(state,r,rc.ROMANS,rc.LEGION)
            or count_pieces(state,r,rc.ROMANS,rc.AUXILIA)
            or _mobile_march_group(state,rc.ROMANS,r)[rc.LEADER]}


def routes(state,origin,destination,group):
    from fs_bot.cli.human_plan import _march_routes
    sim=_copy(state);sim['_diviciacus_preview']=True
    sim.pop('_cli_required_destinations',None)
    with free_action_scope(sim,rc.ROMANS):
        return [destination] in [p for p in _march_routes(sim,origin,rc.ROMANS,group) if len(p)==1]


def make_request(state,*,attempt=1,previous_error=None):
    request={'kind':'free_action','request_type':REQUEST,'card_id':4,
             'acting_faction':rc.ROMANS,'destinations':targets(state),'origins':pools(state),
             'cooperation_regions':sorted(eligible_regions(state,rc.ROMANS)),
             'allow_decline':True,'free':True,'with_sa':False,'validate_default_response':True,
             'attempt':attempt}
    if previous_error:
        request['previous_error']=previous_error
    return request


def group_for(entry,pool):
    return {rc.LEGION:entry['legions'],rc.AUXILIA:entry['auxilia'],rc.WARBAND:0,
            rc.LEADER:pool[rc.LEADER] if entry['leader'] else None}


def validate_response(state,request,response):
    try:
        _validate(state,response)
    except (ValueError,TypeError,KeyError,IndexError,AttributeError) as exc:
        return str(exc)
    return None


def _validate(state,response):
    if _explicit_sentinel(response,'decline') or _explicit_sentinel(response,'use_default'):
        return
    if (not isinstance(response,dict) or not {'destination','marches'}<=set(response)
            or set(response)-{'destination','marches','diviciacus_regions'}):
        raise ValueError('Choose one Citadel destination and ordered exact Roman groups, or decline the whole benefit.')
    destination,marches=response['destination'],response['marches']
    if not isinstance(destination,str) or destination not in targets(state):
        raise ValueError('Choose a playable non-Roman Citadel destination.')
    if not isinstance(marches,list):
        raise ValueError('Marches must be a list; empty leaves only resident Romans for marker placement.')
    cooperation=response.get('diviciacus_regions',[])
    if (not isinstance(cooperation,list) or any(not isinstance(r,str) for r in cooperation)
            or len(cooperation)!=len(set(cooperation))
            or not set(cooperation)<=set(eligible_regions(state,rc.ROMANS))):
        raise ValueError('Request cooperation only in eligible Roman origins.')
    sim=_copy(state);sim['_diviciacus_preview']=True
    with force_scope(sim,rc.ROMANS,cooperation):
        remaining=pools(sim);used=set()
        for entry in marches:
            if not isinstance(entry,dict) or set(entry)!={'origin','legions','auxilia','leader'}:
                raise ValueError('Each adjacent moving group needs origin, legions, auxilia and Boolean leader.')
            origin=entry['origin']
            if not isinstance(origin,str) or origin not in remaining:
                raise ValueError('Select an original Roman mobile force.')
            pool=remaining[origin]
            for key,piece in (('legions',rc.LEGION),('auxilia',rc.AUXILIA)):
                n=entry[key]
                if type(n) is not int or not 0<=n<=pool[piece]:
                    raise ValueError('Counts exceed the unselected original Roman force.')
            if type(entry['leader']) is not bool or (entry['leader'] and not pool[rc.LEADER]):
                raise ValueError('Select only a Leader present at this original source, once.')
            group=group_for(entry,pool)
            if not (entry['legions'] or entry['auxilia'] or entry['leader']):
                raise ValueError('Each selected moving group needs at least one piece.')
            if not routes(sim,origin,destination,group):
                raise ValueError('Every group must March one adjacent step into the same Citadel Region.')
            pool[rc.LEGION]-=entry['legions'];pool[rc.AUXILIA]-=entry['auxilia']
            if entry['leader']:
                pool[rc.LEADER]=None
            used.add(origin)
        if not set(cooperation)<=used:
            raise ValueError('Cooperation must apply to selected March origins only.')


def action_for(state,response):
    return {'command':rc.CMD_MARCH,'regions':list(dict.fromkeys(e['origin'] for e in response['marches'])),
            'sa':'No SA','sa_regions':[],'details':{
                'diviciacus_regions':response.get('diviciacus_regions',[]),
                'explicit_moves':[{'origin':e['origin'],'path':[response['destination']],
                    'group':{rc.LEGION:e['legions'],rc.AUXILIA:e['auxilia'],
                             rc.LEADER:bool(e['leader'])}} for e in response['marches']]}}


def place_marker(state,destination):
    from fs_bot.cards.card_effects import _add_region_marker
    if destination in targets(state) and count_pieces(state,destination,rc.ROMANS):
        _add_region_marker(state,destination,rc.MARKER_CIRCUMVALLATION)
        return True
    return False


def _default(state,target):
    from fs_bot.engine.execute import _derive_card_4,_resolve_card4_circumvallation_default
    if target is None:
        target=(_derive_card_4(state,rc.ROMANS,False) or {}).get('target_region')
    if target is None:
        return [{'free_action':'march','flag':FLAG,'executed':False,'declined_no_effect':True,
                 'reason':'No adjacent Roman March to an enemy Citadel.'}]
    result=_resolve_card4_circumvallation_default(state,target)
    placed=place_marker(state,target)
    for row in result:
        row['marker_placed']=placed
    return result


def _resolve(state,target):
    from fs_bot.cards.arduenna_march import execute_march
    from fs_bot.engine.diviciacus_planning import clear_confirmation
    if rc.ROMANS in state.get('non_player_factions',()):
        return _default(state,target)
    if not targets(state):
        return [{'free_action':'march','flag':FLAG,'executed':False,'declined_no_effect':True,
                 'reason':'No non-Roman Citadel destination.'}]
    attempt,error=1,None
    while True:
        response=consult_free_action(state,rc.ROMANS,make_request(state,attempt=attempt,previous_error=error))
        if response is None:
            return _default(state,target)
        if response.get('decline'):
            return [{'free_action':'roman_benefit','flag':FLAG,'executed':False,
                     'declined_no_effect':True,'reason':'Romans declined the complete benefit.'}]
        destination=response['destination'];march={'executed':False,'marches':[],'errors':[],'total_cost':0}
        if response['marches']:
            action=action_for(state,response)
            try:
                with free_action_scope(state,rc.ROMANS):
                    march=execute_march(state,rc.ROMANS,action,target_regions={destination},source_id='4')
            finally:
                clear_confirmation(state,rc.ROMANS,action)
            if march.get('reason')=='Diviciacus agreement was refused; choose a new plan':
                attempt+=1;error=march['reason'];continue
        placed=place_marker(state,destination)
        return [{'free_action':'march','flag':FLAG,'region':destination,'march_result':march,
                 'marker_placed':placed,'executed':bool(march.get('executed') or placed),
                 'declined_no_effect':not bool(march.get('executed') or placed)}]


def resolve(state,target=None):
    snapshot=_copy(state);agent=state.get('decision_agent');had_agent='decision_agent' in state
    card_turn=state.get('_card_turn')
    try:
        return _resolve(state,target)
    except BaseException:
        state.clear();state.update(snapshot)
        if card_turn is not None:
            state['_card_turn']=card_turn
        if had_agent:
            state['decision_agent']=agent
        raise
