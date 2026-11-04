"""Roman-owned numeric17 and executor-owned numeric65 German guidance."""
from copy import deepcopy

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces
from fs_bot.commands.common import free_action_scope
from fs_bot.engine.free_actions import consult_free_action, _explicit_sentinel
from fs_bot.engine.march_choices import chooser_scope
from fs_bot.map.map_data import get_playable_regions_for_state

FLAG = 'card_65_german_march_ambush'


def _copy(state):
    return deepcopy({k: v for k, v in state.items() if k != 'decision_agent'})


def origins(state):
    return {r: count_pieces(state, r, rc.GERMANS, rc.WARBAND)
            for r in sorted(get_playable_regions_for_state(state, rc.GERMANS))
            if count_pieces(state, r, rc.GERMANS, rc.WARBAND)}


def destinations(state, origin, n):
    from fs_bot.cli.human_plan import _march_routes
    sim = _copy(state)
    sim['_diviciacus_preview'] = True
    sim.pop('_cli_required_destinations', None)
    with free_action_scope(sim, rc.GERMANS):
        return [path[0] for path in _march_routes(sim, origin, rc.GERMANS,
            {rc.WARBAND:n, rc.LEADER:None, rc.LEGION:0, rc.AUXILIA:0}) if len(path)==1]


def defenders(state, remaining=None):
    from fs_bot.commands.sa_ambush import validate_ambush_region
    regions = set(get_playable_regions_for_state(state, rc.GERMANS))
    if remaining is not None:
        regions &= set(remaining)
    result = {}
    for region in sorted(regions):
        enemies = [f for f in rc.FACTIONS if f != rc.GERMANS
                   and count_pieces(state, region, f)
                   and validate_ambush_region(state, region, rc.GERMANS, f)[0]]
        if enemies:
            result[region] = enemies
    return result


def march_request(state, limit, card_id=65):
    request = {'kind':'free_action','request_type':'german_guided_march','card_id':card_id,
            'acting_faction':rc.GERMANS,'origins':origins(state),
            'max_origins':min(3 if card_id==17 else 2,limit),'free':True,'with_sa':False,
            'allow_decline':False,'validate_default_response':True}
    if card_id==17:
        request['moving_groups_only']=True
    return request


def battle_request(state, remaining, blocked=(), card_id=65):
    choices={r:[f for f in enemies if (r,f) not in blocked]
             for r,enemies in defenders(state,remaining).items()}
    choices={r:enemies for r,enemies in choices.items() if enemies}
    return {'kind':'free_action','request_type':'german_guided_ambush','card_id':card_id,
            'acting_faction':rc.GERMANS,'defenders_by_region':choices,
            'remaining_regions':sorted(remaining),'max_regions':1 if card_id==17 else None,'free':True,'with_sa':False,
            'allow_decline':False,'validate_default_response':True}


def validate_response(state, request, response):
    try:
        _validate(state, request, response)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        return str(exc)
    return None


def _validate(state, request, response):
    if _explicit_sentinel(response,'use_default'):
        return
    if request['request_type']=='german_guided_ambush':
        if not isinstance(response,dict) or set(response)!={'region','defender'}:
            raise ValueError('Choose one able Ambush Region and defender; none may be declined independently.')
        region, enemy = response['region'], response['defender']
        if (not isinstance(region,str) or enemy not in request['defenders_by_region'].get(region,())
                or enemy not in defenders(state,request['remaining_regions']).get(region,())):
            raise ValueError('Choose an offered defender in a Region not yet used for this Ambush Command.')
        return
    if not isinstance(response,dict) or set(response)!={'marches'} or not isinstance(response['marches'],list):
        raise ValueError('Supply an ordered marches list (empty permits no March).')
    if len(response['marches'])>request['max_origins']:
        raise ValueError(f"This Event permits at most {request['max_origins']} original German groups/Regions.")
    selected=set(); available=origins(state)
    for entry in response['marches']:
        if not isinstance(entry,dict) or set(entry)!={'origin','destination','warbands'}:
            raise ValueError('Each selected origin needs origin, destination and warbands only.')
        origin,n,destination=entry['origin'],entry['warbands'],entry['destination']
        if not isinstance(origin,str) or origin not in available or origin in selected:
            raise ValueError('Choose distinct original German Regions; arrivals cannot March again.')
        if type(n) is not int or not 0<=n<=available[origin]:
            raise ValueError('Choose an available quantity of German Warbands.')
        if n==0:
            if request.get('moving_groups_only'):
                raise ValueError('Germanic Chieftains grants moving groups; select a positive quantity or omit the group.')
            if destination is not None:
                raise ValueError('A hide-only origin uses destination: null.')
        elif not isinstance(destination,str) or destination not in destinations(state,origin,n):
            raise ValueError('Each moving group must enter one adjacent playable Region.')
        selected.add(origin)


def action_for(response):
    return {'command':rc.CMD_MARCH,'sa':'No SA','sa_regions':[],
            'regions':[e['origin'] for e in response['marches']], 'details':{'explicit_moves':[
                {'origin':e['origin'],'path':[e['destination']] if e['warbands'] else [],
                 'group':{rc.WARBAND:e['warbands']}} for e in response['marches']]}}


def _resolve(state, executor, limit, card_id):
    from fs_bot.engine.execute import (_resolve_card65_german_march_ambush_default,
                                      _resolve_card17_march_ambush_default)
    from fs_bot.cards.arduenna_march import execute_march
    from fs_bot.battle.resolve import resolve_battle
    default = (_resolve_card17_march_ambush_default if card_id==17
               else _resolve_card65_german_march_ambush_default)
    if executor in state.get('non_player_factions',()):
        return default(state,limit)
    request=march_request(state,limit,card_id)
    if card_id==17:
        # Keep raw-callback legacy deferral distinct from an explicit Roman
        # bot choice: the latter must follow the card's Roman instructions.
        from fs_bot.engine.agent import consult_agent
        response=consult_agent(state,executor,request)
        if response is None:
            return default(state,limit)
        error=validate_response(state,request,response)
        if error:
            raise ValueError(error)
        if _explicit_sentinel(response,'use_default'):
            return default(state,limit,roman_guided=True)
    else:
        response=consult_free_action(state,executor,request)
        if response is None:
            return default(state,limit)
    if response['marches']:
        with free_action_scope(state,rc.GERMANS), chooser_scope(state,rc.GERMANS,executor):
            marched = execute_march(state,rc.GERMANS,action_for(response),source_id=str(card_id),
                target_regions=set(get_playable_regions_for_state(state,rc.GERMANS)),
                allow_stationary=card_id==65)
    else:
        marched=[]
    remaining=set(get_playable_regions_for_state(state,rc.GERMANS)); ambushes=[]; blocked={}
    while True:
        # A later live timing choice can change a formerly blocked defense.
        blocked={key:position for key,position in blocked.items()
                 if position==state['spaces'].get(key[0])}
        request=battle_request(state,remaining,blocked,card_id)
        choices=request['defenders_by_region']
        if not choices:
            break
        selected=consult_free_action(state,executor,request)
        if selected is None:
            # A human default must still execute a legal zero-Loss Ambush;
            # the native NP heuristic's effectiveness filter is not legality.
            region=next(iter(choices))
            enemy=max(choices[region],key=lambda f:count_pieces(state,region,f))
        else:
            region,enemy=selected['region'],selected['defender']
        from fs_bot.engine.diviciacus import defense_scope
        from fs_bot.commands.sa_ambush import validate_ambush_region
        defending_position=deepcopy(state['spaces'][region])
        with defense_scope(state,region,rc.GERMANS,enemy):
            if not validate_ambush_region(state,region,rc.GERMANS,enemy)[0]:
                # Defensive cooperation may remove Hidden superiority. Germans
                # cannot fall back to an ordinary Battle (§3.4.4); reoffer the
                # other able targets instead of attacking the combined force.
                blocked[(region,enemy)]=defending_position
                continue
            battle=resolve_battle(state,region,rc.GERMANS,enemy,is_ambush=True)
        ambushes.append({'region':region,'defender':enemy,'result':battle})
        remaining.remove(region)
        if card_id==17:
            break
    if card_id==17:
        result={'free_action':'german_march_ambush','flag':'card_17_german_ambush',
                'marches':marched,'ambushes':ambushes,'executed':bool(marched or ambushes),
                'declined_no_effect':not bool(marched or ambushes)}
        if ambushes:
            result.update(ambushes[0])
        else:
            result['reason']='No legal German Ambush.'
        return [result]
    return [{'free_action':'german_march_ambush','flag':FLAG,'marches':marched,
             'ambushes':ambushes,'executed':bool(marched or ambushes),
             'declined_no_effect':not bool(marched or ambushes)}]


def resolve(state, executor, limit=2, *, card_id=65):
    snapshot=_copy(state); agent=state.get('decision_agent'); had_agent='decision_agent' in state
    card_turn=state.get('_card_turn')
    try:
        return _resolve(state,rc.ROMANS if card_id==17 else executor,limit,card_id)
    except BaseException:
        state.clear();state.update(snapshot)
        if card_turn is not None:
            state['_card_turn']=card_turn
        if had_agent:
            state['decision_agent']=agent
        raise
