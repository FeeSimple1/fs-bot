"""March can pay for an origin and hide without moving (§3.2.2/3.3.2/A3.4.2)."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces_by_state, count_pieces
from fs_bot.commands.march import march_cost
from fs_bot.engine.execute import _execute_march, execute_decision
from fs_bot.engine.moves import validate_player_action
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import encode, decode

CASES=[(rc.SCENARIO_GREAT_REVOLT,f) for f in (rc.ROMANS,rc.ARVERNI,rc.AEDUI,rc.BELGAE)] + [
    (rc.SCENARIO_ARIOVISTUS,f) for f in (rc.ROMANS,rc.AEDUI,rc.BELGAE,rc.GERMANS)]
ORIGIN=rc.MORINI


def position(scenario,faction,region=ORIGIN):
    state=build_initial_state(scenario,seed=31)
    state['non_player_factions']=set()
    state['resources'][faction]=10
    piece=rc.AUXILIA if faction==rc.ROMANS else rc.WARBAND
    place_piece(state,region,faction,piece,2,piece_state=rc.REVEALED)
    if faction!=rc.ROMANS:
        place_piece(state,region,faction,piece,1,piece_state=rc.SCOUTED)
    assert validate_state(state)==[]
    return state


def action(*origins):
    return {'command':rc.CMD_MARCH,'sa':'No SA','details':{
        'origins':list(origins),'destinations':[],'routes':{r:[] for r in origins}}}


@pytest.mark.parametrize('scenario,faction',CASES)
@pytest.mark.parametrize('devastated',[False,True])
def test_stay_hides_every_origin_piece_pays_once_and_never_moves(scenario,faction,devastated):
    state=position(scenario,faction)
    if devastated:state.setdefault('markers',{}).setdefault(ORIGIN,{})[rc.MARKER_DEVASTATED]=True
    piece=rc.AUXILIA if faction==rc.ROMANS else rc.WARBAND
    counts={s:count_pieces_by_state(state,ORIGIN,faction,piece,s) for s in (rc.HIDDEN,rc.REVEALED,rc.SCOUTED)}
    totals={r:count_pieces(state,r,faction) for r in state['spaces']}
    rng=state['rng'].getstate();cost=march_cost(state,ORIGIN,faction)
    result=execute_decision(state,faction,{'player_action':action(ORIGIN)})
    assert result['executed'] and not result['errors'],result
    assert result['marches']==[] and result['stayed_origins']==[ORIGIN]
    assert result['total_cost']==cost and state['resources'][faction]==10-cost
    assert count_pieces_by_state(state,ORIGIN,faction,piece,rc.HIDDEN)==counts[rc.HIDDEN]+counts[rc.REVEALED]
    assert count_pieces_by_state(state,ORIGIN,faction,piece,rc.REVEALED)==counts[rc.SCOUTED]
    assert count_pieces_by_state(state,ORIGIN,faction,piece,rc.SCOUTED)==0
    assert totals=={r:count_pieces(state,r,faction) for r in state['spaces']}
    assert state['rng'].getstate()==rng
    assert validate_state(state)==[]


@pytest.mark.parametrize('scenario,faction',CASES)
def test_preview_and_save_load_accept_stay_without_mutating_live(scenario,faction):
    state=position(scenario,faction);before=encode(state)
    ok,result=validate_player_action(state,faction,action(ORIGIN))
    assert ok and result['stayed_origins']==[ORIGIN]
    assert encode(state)==before
    other=decode(before)
    assert execute_decision(state,faction,{'player_action':action(ORIGIN)})==execute_decision(other,faction,{'player_action':action(ORIGIN)})
    assert encode(state)==encode(other)


def test_unaffordable_stay_does_not_flip_or_spend():
    state=position(rc.SCENARIO_GREAT_REVOLT,rc.ROMANS);state['resources'][rc.ROMANS]=1
    before=encode(state)
    result=_execute_march(state,rc.ROMANS,action(ORIGIN))
    assert not result['executed'] and result['total_cost']==0
    assert result['deferred_origins']==[ORIGIN]
    assert encode(state)==before


def test_stay_and_moving_origin_share_ordered_resource_budget():
    state=position(rc.SCENARIO_GREAT_REVOLT,rc.ROMANS)
    place_piece(state,rc.NERVII,rc.ROMANS,rc.AUXILIA,2,piece_state=rc.REVEALED)
    state['resources'][rc.ROMANS]=2
    plan=action(ORIGIN,rc.NERVII);plan['details']['routes'][rc.NERVII]=[rc.ATREBATES]
    plan['details']['destinations']=[rc.ATREBATES]
    result=_execute_march(state,rc.ROMANS,plan)
    assert result['stayed_origins']==[ORIGIN] and result['deferred_origins']==[rc.NERVII]
    assert count_pieces_by_state(state,rc.NERVII,rc.ROMANS,rc.AUXILIA,rc.REVEALED)==2


def test_missing_route_never_becomes_implicit_stay():
    state=position(rc.SCENARIO_GREAT_REVOLT,rc.ROMANS)
    plan=action(ORIGIN);del plan['details']['routes'][ORIGIN]
    before=encode(state)
    result=_execute_march(state,rc.ROMANS,plan)
    assert not result['executed'] and 'stayed_origins' not in result
    assert encode(state)==before


def test_cli_stay_skips_group_allocation_and_keeps_live_board(monkeypatch):
    from fs_bot.cli import human_plan
    state=position(rc.SCENARIO_GREAT_REVOLT,rc.ROMANS);before=encode(state)
    monkeypatch.setattr(human_plan,'_pick_regions',lambda *a,**k:[ORIGIN])
    def pick(stdin,stdout,prompt,options):
        assert 'along which route' in prompt
        return next(value for label,value in options if value==[])
    monkeypatch.setattr(human_plan,'prompt_choice',pick)
    plan=human_plan._collect_march(state,rc.ROMANS,StringIO(),StringIO(),single=False)
    assert plan['origins']==[ORIGIN] and plan['routes']=={ORIGIN:[]} and plan['destinations']==[]
    assert encode(state)==before
    assert _execute_march(state,rc.ROMANS,{'details':plan})['executed']


def test_required_destination_event_cannot_stay(monkeypatch):
    from fs_bot.cli import human_plan
    from fs_bot.engine.free_actions import validate_free_action_response
    state=position(rc.SCENARIO_GREAT_REVOLT,rc.ROMANS)
    request={'kind':'free_action','request_type':'event_command','allowed_commands':[rc.CMD_MARCH],
             'free':True,'with_sa':False,'required_destinations':[rc.NERVII]}
    assert 'end in the Event destination' in validate_free_action_response(state,rc.ROMANS,request,action(ORIGIN))
    state['_cli_required_destinations']=[rc.NERVII]
    monkeypatch.setattr(human_plan,'_pick_regions',lambda *a,**k:[ORIGIN])
    def pick(stdin,stdout,prompt,options):
        if 'along which route' in prompt:
            assert all(value for label,value in options)
        return options[0][1]
    monkeypatch.setattr(human_plan,'prompt_choice',pick)
    human_plan._collect_march(state,rc.ROMANS,StringIO('n\n'),StringIO(),single=True)


def test_staying_in_britannia_does_not_cross_it_for_sa_constraint():
    from fs_bot.engine.action_validation import validate_human_structure
    state=position(rc.SCENARIO_GREAT_REVOLT,rc.ROMANS,rc.BRITANNIA)
    plan=action(rc.BRITANNIA);plan['sa']=rc.SA_SCOUT
    plan['details']['scout_plan']={'auxilia_moves':[],'scout_targets':[]}
    assert validate_human_structure(state,rc.ROMANS,plan) is None
    plan['details']['routes'][rc.BRITANNIA]=[rc.MORINI]
    assert 'Britannia' in validate_human_structure(state,rc.ROMANS,plan)


def test_empty_route_does_not_bypass_frost():
    state=position(rc.SCENARIO_GREAT_REVOLT,rc.ROMANS)
    state['current_card'],state['next_card']=1,rc.WINTER_CARD
    before=encode(state)
    result=execute_decision(state,rc.ROMANS,{'player_action':action(ORIGIN)})
    assert not result['executed'] and 'Frost' in result['reason']
    assert encode(state)==before


def test_explicit_stay_and_extra_movement_share_one_flip_and_cost():
    state=position(rc.SCENARIO_GREAT_REVOLT,rc.AEDUI)
    plan=action(ORIGIN)
    plan['details']['extra_groups']=[{'origin':ORIGIN,'route':[rc.NERVII],
                                      'group':{rc.WARBAND:1}}]
    result=_execute_march(state,rc.AEDUI,plan)
    assert result['executed'] and not result['errors'],result
    assert result['total_cost']==1
    assert count_pieces_by_state(state,ORIGIN,rc.AEDUI,rc.WARBAND,rc.REVEALED)==1
    assert count_pieces_by_state(state,ORIGIN,rc.AEDUI,rc.WARBAND,rc.SCOUTED)==0
    assert validate_state(state)==[]


def test_free_event_stay_uses_origin_scope_and_no_resources():
    from fs_bot.engine.free_actions import execute_free_action_plan,validate_free_action_response
    state=position(rc.SCENARIO_ARIOVISTUS,rc.GERMANS)
    request={'kind':'free_action','request_type':'event_command','allowed_commands':[rc.CMD_MARCH],
             'allowed_regions':[ORIGIN],'free':True,'with_sa':False}
    assert validate_free_action_response(state,rc.GERMANS,request,action(ORIGIN)) is None
    assert 'Regions granted' in validate_free_action_response(state,rc.GERMANS,request,action(rc.NERVII))
    result=execute_free_action_plan(state,rc.GERMANS,request,action(ORIGIN))
    assert result['executed'] and result['total_cost']==0
    assert state['resources'][rc.GERMANS]==10


def test_base_german_mechanic_hides_in_place_without_resource_cost():
    state=position(rc.SCENARIO_GREAT_REVOLT,rc.GERMANS)
    result=_execute_march(state,rc.GERMANS,action(ORIGIN))
    assert result['executed'] and result['total_cost']==0
    assert count_pieces_by_state(state,ORIGIN,rc.GERMANS,rc.WARBAND,rc.SCOUTED)==0


@pytest.mark.parametrize('standalone',[False,True])
def test_stay_durable_choice_survives_save_resume_and_replays_exactly(tmp_path,standalone):
    from fs_bot.tests.test_repeated_seize_entreat_regions import session_for,attempt
    from fs_bot.tools.seat_session import DecisionPending,board_copy
    from fs_bot.state.serialize import save_game,load_game
    from fs_bot.engine.game_engine import ACTION_COMMAND
    state=position(rc.SCENARIO_GREAT_REVOLT,rc.ROMANS)
    plan=action(ORIGIN)
    if standalone:
        request={'kind':'free_action','request_type':'event_command','allowed_commands':[rc.CMD_MARCH],
                 'allowed_regions':[ORIGIN],'with_sa':False,'free':True}
        response=plan
    else:
        request={'kind':'turn','options':[ACTION_COMMAND],'position':'1st_eligible'}
        response={'action':ACTION_COMMAND,'player_action':plan}
    session=session_for(state,rc.ROMANS);before=encode(board_copy(state))
    with pytest.raises(DecisionPending):attempt(session,request)
    pending=deepcopy(session.data['pending'])
    path=tmp_path/'stay.json';save_game(state,path,meta=session.meta,log=session.log)
    loaded,meta,log=load_game(path);resumed=session_for(loaded,rc.ROMANS,meta,log)
    assert encode(board_copy(loaded))==before
    resumed.import_inbox({'decision_id':pending['id'],'response':response})
    for _ in range(20):
        try:
            result=attempt(resumed,request)
            break
        except DecisionPending:
            next_pending=resumed.data['pending']
            assert decode(next_pending['request'])['kind']=='voluntary_removal'
            resumed.import_inbox({'decision_id':next_pending['id'],'response':{'done':True}})
    else:pytest.fail('Stay did not complete')
    assert result['executed'] and result['stayed_origins']==[ORIGIN]
    resumed.finish()
    assert not resumed.data['pending'] and not resumed.data['queue']
    assert resumed.log[0]['assistant_id']==pending['id']
    assert decode(resumed.log[0]['assistant_response'])==response


@pytest.mark.parametrize('timing',['before','after'])
def test_stay_can_accompany_build(timing):
    state=position(rc.SCENARIO_GREAT_REVOLT,rc.ROMANS,rc.SEQUANI)
    place_piece(state,rc.SEQUANI,rc.ROMANS,rc.LEADER,leader_name=rc.CAESAR)
    plan=action(rc.SEQUANI);plan.update(sa=rc.SA_BUILD,sa_timing=timing,sa_regions=[rc.SEQUANI])
    plan['details']['build_plan']={'forts':[rc.SEQUANI],'region_order':[rc.SEQUANI]}
    result=execute_decision(state,rc.ROMANS,{'player_action':plan})
    assert result['executed'] and result['sa_execution']['executed'],result
    assert result['stayed_origins']==[rc.SEQUANI]
    assert state['resources'][rc.ROMANS]==6
    assert count_pieces(state,rc.SEQUANI,rc.ROMANS,rc.FORT)==1


def test_limited_stay_still_selects_only_one_origin():
    from fs_bot.engine.action_validation import validate_human_structure
    state=position(rc.SCENARIO_GREAT_REVOLT,rc.ROMANS)
    assert 'one Region' in validate_human_structure(state,rc.ROMANS,action(ORIGIN,rc.NERVII),limited=True)
    assert validate_human_structure(state,rc.ROMANS,action(ORIGIN),limited=True) is None


def test_stay_never_needs_a_reachable_adjacent_region(monkeypatch):
    from fs_bot.cli import human_plan
    state=position(rc.SCENARIO_GREAT_REVOLT,rc.ROMANS)
    monkeypatch.setattr(human_plan,'_march_routes',lambda *a,**k:[])
    monkeypatch.setattr(human_plan,'_pick_regions',lambda *a,**k:[ORIGIN])
    monkeypatch.setattr(human_plan,'prompt_choice',lambda i,o,p,opts:opts[0][1])
    plan=human_plan._collect_march(state,rc.ROMANS,StringIO(),StringIO(),single=True)
    assert plan['routes']=={ORIGIN:[]}
