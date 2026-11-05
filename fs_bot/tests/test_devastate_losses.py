"""Devastate owners select exact physical casualties (§4.3.2/§8.4.1)."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece,count_pieces,count_pieces_by_state
from fs_bot.board.control import refresh_all_control
from fs_bot.commands.common import CommandError
from fs_bot.commands.sa_devastate import devastate_region
from fs_bot.engine.execute import _execute_devastate
from fs_bot.state.state_schema import build_initial_state,validate_state
from fs_bot.state.serialize import encode,decode

KIND='devastate_losses'
REGION=rc.CARNUTES


def position(*,all_owners=False,scenario=rc.SCENARIO_GREAT_REVOLT):
    state=build_initial_state(scenario,seed=29)
    state['non_player_factions']=set()
    state['resources'][rc.ARVERNI]=10
    place_piece(state,REGION,rc.ARVERNI,rc.LEADER,leader_name=rc.VERCINGETORIX)
    place_piece(state,REGION,rc.ARVERNI,rc.WARBAND,12 if all_owners else 4)
    place_piece(state,REGION,rc.ARVERNI,rc.WARBAND,2,piece_state=rc.REVEALED)
    place_piece(state,REGION,rc.ARVERNI,rc.WARBAND,2,piece_state=rc.SCOUTED)
    place_piece(state,REGION,rc.ROMANS,rc.LEGION,1,from_legions_track=True)
    place_piece(state,REGION,rc.ROMANS,rc.AUXILIA,1)
    place_piece(state,REGION,rc.ROMANS,rc.AUXILIA,1,piece_state=rc.REVEALED)
    if all_owners:
        for faction in (rc.AEDUI,rc.BELGAE,rc.GERMANS):
            for visibility in (rc.HIDDEN,rc.REVEALED,rc.SCOUTED):
                place_piece(state,REGION,faction,rc.WARBAND,1,piece_state=visibility)
    refresh_all_control(state)
    assert validate_state(state)==[]
    return state


def entry(piece,visibility,count=1):
    return {'piece_type':piece,'piece_state':visibility,'count':count}


def request(state,faction=rc.ROMANS):
    from fs_bot.engine.devastate_losses import removal_request
    return removal_request(state,REGION,faction)


def validate(state,req,response):
    from fs_bot.engine.devastate_losses import validate_response
    return validate_response(state,req,response)


def owner_agent(state,faction,response):
    seen=[]
    def agent(board,owner,req):
        if req['kind']==KIND and owner==faction:
            seen.append(deepcopy(req));return response
        return None
    state['decision_agent']=agent
    return seen


@pytest.mark.parametrize('piece,visibility',[(rc.LEGION,None),(rc.AUXILIA,rc.HIDDEN),(rc.AUXILIA,rc.REVEALED)])
def test_roman_owner_chooses_legion_or_exact_auxilia_visibility(piece,visibility):
    state=position();seen=owner_agent(state,rc.ROMANS,{'removals':[entry(piece,visibility)]})
    before={(p,s):count_pieces_by_state(state,REGION,rc.ROMANS,p,s)
            for p in (rc.AUXILIA,) for s in (rc.HIDDEN,rc.REVEALED,rc.SCOUTED)}
    fallen=state['fallen_legions'];rng=state['rng'].getstate()
    result=devastate_region(state,REGION)
    assert len(seen)==1 and seen[0]['count']==1
    assert result['removal_details'][rc.ROMANS]==[entry(piece,visibility)]
    assert count_pieces(state,REGION,rc.ROMANS,rc.LEGION)==(0 if piece==rc.LEGION else 1)
    assert state['fallen_legions']==fallen+int(piece==rc.LEGION)
    assert {(p,s):count_pieces_by_state(state,REGION,rc.ROMANS,p,s) for p,s in before}=={
        cell:n-int(cell==(piece,visibility)) for cell,n in before.items()}
    assert state['rng'].getstate()==rng and validate_state(state)==[]


@pytest.mark.parametrize('faction',[rc.ARVERNI,rc.AEDUI,rc.BELGAE,rc.GERMANS])
@pytest.mark.parametrize('visibility',[rc.HIDDEN,rc.REVEALED,rc.SCOUTED])
def test_each_warband_owner_chooses_visibility(faction,visibility):
    state=position(all_owners=True);needed=request(state,faction)['count']
    if faction==rc.ARVERNI:
        # Four losses: combine this cohort with other eligible Warbands.
        chosen=[entry(rc.WARBAND,visibility,min(needed,count_pieces_by_state(state,REGION,faction,rc.WARBAND,visibility)))]
        remaining=needed-chosen[0]['count']
        if remaining:chosen.append(entry(rc.WARBAND,rc.HIDDEN,remaining))
    else:chosen=[entry(rc.WARBAND,visibility)]
    before=count_pieces_by_state(state,REGION,faction,rc.WARBAND,visibility)
    seen=owner_agent(state,faction,{'removals':chosen})
    result=devastate_region(state,REGION)
    assert len(seen)==1 and seen[0]['count']==needed
    assert count_pieces_by_state(state,REGION,faction,rc.WARBAND,visibility)==before-sum(e['count'] for e in chosen if e['piece_state']==visibility)
    assert result['removal_details'][faction]==chosen
    assert validate_state(state)==[]


def test_all_owner_counts_are_frozen_and_choices_finish_before_any_removal():
    state=position(all_owners=True);seen=[]
    original={f:count_pieces(state,REGION,f) for f in rc.FACTIONS}
    def agent(board,faction,req):
        if req['kind']!=KIND:return None
        assert {f:count_pieces(board,REGION,f) for f in rc.FACTIONS}==original
        seen.append((faction,req['count']))
        return {'removals':[entry(rc.LEGION,None)] if faction==rc.ROMANS else [entry(rc.WARBAND,rc.HIDDEN,req['count'])]}
    state['decision_agent']=agent
    devastate_region(state,REGION)
    assert seen==[(rc.ROMANS,1),(rc.ARVERNI,4),(rc.AEDUI,1),(rc.BELGAE,1),(rc.GERMANS,1)]
    assert validate_state(state)==[]


def test_default_nonplayers_remove_scouted_then_revealed_preserving_hidden():
    state=position();hidden=count_pieces_by_state(state,REGION,rc.ARVERNI,rc.WARBAND,rc.HIDDEN)
    result=devastate_region(state,REGION)
    assert count_pieces_by_state(state,REGION,rc.ARVERNI,rc.WARBAND,rc.SCOUTED)==0
    assert count_pieces_by_state(state,REGION,rc.ARVERNI,rc.WARBAND,rc.HIDDEN)==hidden
    assert count_pieces_by_state(state,REGION,rc.ROMANS,rc.AUXILIA,rc.REVEALED)==0
    assert 'removal_details' not in result and result['removed'][rc.ARVERNI]==[(rc.WARBAND,2)]


@pytest.mark.parametrize('bad',[None,{}, {'decline':True},{'removals':[]},
    {'removals':[entry(rc.LEGION,None,2)]},{'removals':[entry(rc.ALLY,None)]},
    {'removals':[entry(rc.LEADER,None)]},{'removals':[entry(rc.AUXILIA,None)]},
    {'removals':[entry(rc.AUXILIA,rc.SCOUTED)]},{'removals':[entry(rc.AUXILIA,rc.HIDDEN,True)]},
    {'removals':[entry(rc.AUXILIA,rc.HIDDEN,-1)]},{'removals':[entry(rc.AUXILIA,rc.HIDDEN,1.0)]},
    {'removals':[entry(rc.AUXILIA,rc.HIDDEN)],'faction':rc.ARVERNI}, {'use_default':1}])
def test_invalid_choice_cannot_change_any_casualty_or_marker(bad):
    state=position();before=encode(state)
    with pytest.raises(ValueError):validate(state,request(state),bad)
    assert encode(state)==before


@pytest.mark.parametrize('plan',[{rc.ROMANS:[]},{rc.ROMANS:[(rc.LEGION,None,2)]},
    {rc.ARVERNI:[(rc.ALLY,None,2)]},{rc.ROMANS:[(rc.AUXILIA,rc.HIDDEN,True)]},
    {rc.ROMANS:[(rc.AUXILIA,rc.HIDDEN,1)],rc.ARVERNI:[(rc.WARBAND,rc.HIDDEN,1)]}])
def test_trusted_preselected_map_is_validated_whole_before_mutation(plan):
    state=position();before=encode(state)
    with pytest.raises(CommandError):devastate_region(state,REGION,plan)
    assert encode(state)==before


def test_legacy_tuple_plan_retains_explicit_none_visibility_fallback():
    state=position()
    result=devastate_region(state,REGION,{rc.ROMANS:[(rc.AUXILIA,None,1)]})
    assert result['removal_details'][rc.ROMANS]==[entry(rc.AUXILIA,rc.HIDDEN)]
    assert count_pieces_by_state(state,REGION,rc.ROMANS,rc.AUXILIA,rc.REVEALED)==1


def test_cli_chooses_legion_and_allows_board_inspection():
    from fs_bot.cli.reactive import make_cli_reactive
    state=position();req=request(state);before=encode(state);output=StringIO()
    # Decline both Auxilia cohorts; the remaining required casualty is a Legion.
    response=make_cli_reactive({rc.ROMANS},StringIO('board\n1\n1\n'),output)(state,rc.ROMANS,req)
    assert response=={'removals':[entry(rc.LEGION,None)]}
    assert encode(state)==before and 'casualties' in output.getvalue()


def test_rounding_zero_casualties_never_ask_the_owner():
    state=build_initial_state(rc.SCENARIO_GREAT_REVOLT,seed=3)
    place_piece(state,REGION,rc.ARVERNI,rc.WARBAND,3)
    place_piece(state,REGION,rc.ROMANS,rc.AUXILIA,2)
    state['decision_agent']=lambda *a:pytest.fail('Zero losses require no selection')
    result=devastate_region(state,REGION)
    assert result['removed']=={} and result['devastated_placed']


def test_ariovistus_still_cannot_devastate():
    state=build_initial_state(rc.SCENARIO_ARIOVISTUS,seed=3);before=encode(state)
    result=_execute_devastate(state,rc.ARVERNI,{'sa_regions':[REGION]})
    assert not result['executed'] and 'Ariovistus' in result['errors'][0]['error']
    assert encode(state)==before


def test_actor_plan_does_not_override_another_owners_casualties():
    state=position();seen=owner_agent(state,rc.ROMANS,{'removals':[entry(rc.LEGION,None)]})
    result=_execute_devastate(state,rc.ARVERNI,{'sa_regions':[REGION],
        'details':{'removals':{rc.ROMANS:[(rc.AUXILIA,rc.HIDDEN,1)]}}})
    assert result['executed'] and not result['errors']
    assert len(seen)==1 and count_pieces(state,REGION,rc.ROMANS,rc.LEGION)==0
    assert count_pieces_by_state(state,REGION,rc.ROMANS,rc.AUXILIA,rc.HIDDEN)==1


def test_leaders_and_allies_neither_count_nor_absorb_devastate_losses():
    state=position();place_piece(state,REGION,rc.ROMANS,rc.ALLY)
    state['tribes'][rc.TRIBE_CARNUTES]['allied_faction']=rc.ROMANS
    place_piece(state,REGION,rc.ROMANS,rc.LEADER,leader_name=rc.CAESAR)
    req=request(state)
    assert req['count']==1 and all(e['piece_type'] not in (rc.ALLY,rc.LEADER) for e in req['available'])
    devastate_region(state,REGION)
    assert count_pieces(state,REGION,rc.ROMANS,rc.ALLY)==1
    assert count_pieces(state,REGION,rc.ROMANS,rc.LEADER)==1
    assert state['tribes'][rc.TRIBE_CARNUTES]['allied_faction']==rc.ROMANS
    assert validate_state(state)==[]


def test_duplicate_cohort_entries_cannot_exceed_physical_supply():
    state=position();before=encode(state)
    with pytest.raises(ValueError):validate(state,request(state),{'removals':[entry(rc.AUXILIA,rc.HIDDEN),entry(rc.AUXILIA,rc.HIDDEN)]})
    assert encode(state)==before


def test_cli_eof_preserves_board_marker_and_rng_in_transaction():
    from fs_bot.cli.reactive import make_cli_reactive
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.tools.seat_session import board_copy
    state=position();before=encode(state)
    state['decision_agent']=make_cli_reactive({rc.ROMANS},StringIO(),StringIO())
    with pytest.raises(EOFError):
        with _action_transaction(state,lambda *a:None):devastate_region(state,REGION)
    assert encode(board_copy(state))==before


def test_preview_never_consumes_live_casualty_input():
    from fs_bot.engine.moves import validate_player_action
    state=position();before=encode(state)
    state['decision_agent']=lambda *a:pytest.fail('Preview consumed live casualty choice')
    plan={'command':rc.CMD_RAID,'sa':rc.SA_DEVASTATE,'sa_timing':'after','sa_regions':[REGION],
          'details':{'raid_plan':[{'region':REGION,'target':None}]}}
    assert validate_player_action(state,rc.ARVERNI,plan)[0]
    assert encode({k:v for k,v in state.items() if k!='decision_agent'})==before


@pytest.mark.parametrize('response',[None,{'use_default':True}])
def test_delegation_uses_source_priority_without_changing_result_shape(response):
    state=position();seen=owner_agent(state,rc.ROMANS,response)
    result=devastate_region(state,REGION)
    assert seen and set(result)=={'removed','devastated_placed'}
    assert count_pieces_by_state(state,REGION,rc.ROMANS,rc.AUXILIA,rc.REVEALED)==0
    assert count_pieces(state,REGION,rc.ROMANS,rc.LEGION)==1


@pytest.mark.parametrize('bad',[None,{}, {'removals':[entry(rc.LEGION,None,2)]}])
def test_two_region_casualty_pending_survives_rollback_save_and_replay(tmp_path,bad):
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.state.serialize import save_game,load_game
    from fs_bot.tools.seat_session import SeatSession,DecisionPending,board_copy
    state=position()
    second=rc.MANDUBII
    place_piece(state,second,rc.ARVERNI,rc.WARBAND,8)
    place_piece(state,second,rc.ROMANS,rc.LEGION,1,from_legions_track=True)
    place_piece(state,second,rc.ROMANS,rc.AUXILIA,2)
    refresh_all_control(state)
    plan={'sa_regions':[REGION,second]}
    session=SeatSession(state,{'seat':rc.ROMANS},[],HumanTurnDisplay(StringIO()))
    state['decision_agent']=session.reactive
    def attempt(current):
        def driver(*args):pass
        driver.transaction_checkpoint=current.checkpoint;driver.transaction_restore=current.restore
        with _action_transaction(current.state,driver):return _execute_devastate(current.state,rc.ARVERNI,plan)
    before=encode(board_copy(state))
    with pytest.raises(DecisionPending):attempt(session)
    first=deepcopy(session.data['pending'])
    response={'removals':[entry(rc.LEGION,None)]}
    session.import_inbox({'decision_id':first['id'],'response':response})
    with pytest.raises(DecisionPending):attempt(session)
    pending=deepcopy(session.data['pending'])
    req=decode(pending['request'])
    assert pending['id']!=first['id'] and req['region']==second and req['faction']==rc.ROMANS
    assert encode(board_copy(state))==before
    payload={'decision_id':pending['id'],'response':bad};session.import_inbox(payload)
    with pytest.raises(DecisionPending):attempt(session)
    assert session.data['pending']==pending and session.data['queue']==[payload]
    assert encode(board_copy(state))==before
    path=tmp_path/'devastate.json';save_game(state,path,meta=session.meta,log=session.log)
    restored,meta,log=load_game(path);resumed=SeatSession(restored,meta,log,HumanTurnDisplay(StringIO()))
    restored['decision_agent']=resumed.reactive
    with pytest.raises(DecisionPending):attempt(resumed)
    assert resumed.data['pending']==pending
    resumed.import_inbox({'decision_id':pending['id'],'response':response})
    result=attempt(resumed);resumed.finish()
    assert result['executed'] and result['regions']==[REGION,second] and not result['errors']
    assert count_pieces(restored,REGION,rc.ROMANS,rc.LEGION)==0
    assert count_pieces(restored,second,rc.ROMANS,rc.LEGION)==0
    assert not resumed.data['pending'] and not resumed.data['queue']
    assert [e['assistant_id'] for e in log]==[first['id'],pending['id']]
    for e in log:assert decode(e['assistant_response'])==response
    replay=position()
    place_piece(replay,second,rc.ARVERNI,rc.WARBAND,8)
    place_piece(replay,second,rc.ROMANS,rc.LEGION,1,from_legions_track=True)
    place_piece(replay,second,rc.ROMANS,rc.AUXILIA,2)
    refresh_all_control(replay)
    replay['decision_agent']=lambda st,fa,re:response if fa==rc.ROMANS and re['kind']==KIND else None
    assert _execute_devastate(replay,rc.ARVERNI,plan)==result
    assert encode(board_copy(replay))==encode(board_copy(restored))
    assert validate_state(restored)==[]
