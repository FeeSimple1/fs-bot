"""Pax first Harvest places Winter Track Legions in any Belgica Region(s)."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece,count_pieces,PieceError
from fs_bot.engine.winter import run_winter_round
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import validate_state
from fs_bot.state.serialize import encode,decode

KIND='harvest_legions'
REGIONS=tuple(sorted(rc.BELGICA_REGIONS))


def place_harvest(state,maximum=3):
    from fs_bot.engine.harvest_legions import place_harvest_legions
    return place_harvest_legions(state,maximum)


def validate(state,request,response):
    from fs_bot.engine.harvest_legions import validate_response
    return validate_response(state,request,response)


def position():
    state=setup_scenario(rc.SCENARIO_PAX_GALLICA,seed=41)
    state['non_player_factions']={rc.ARVERNI,rc.BELGAE,rc.AEDUI}
    state['current_card']=rc.WINTER_CARD
    assert state['winter_track_legions']==3
    assert validate_state(state)==[]
    return state


def counts(state):return {r:count_pieces(state,r,rc.ROMANS,rc.LEGION) for r in rc.BELGICA_REGIONS}


ALLOCATIONS=[{r:n for r,n in zip(REGIONS,(a,b,3-a-b)) if n}
             for a in range(4) for b in range(4-a)]


@pytest.mark.parametrize('allocation',ALLOCATIONS)
def test_every_three_legion_distribution_preserves_census_control_and_rng(allocation):
    from fs_bot.board.control import calculate_control
    state=position();before=counts(state);rng=state['rng'].getstate();track=deepcopy(state['legions_track'])
    seen=[]
    def agent(board,faction,request):
        assert faction==rc.ROMANS and request['kind']==KIND
        seen.append(deepcopy(request));return {'placements':allocation}
    state['decision_agent']=agent
    result=place_harvest(state)
    assert len(seen)==1 and seen[0]['count']==3 and seen[0]['legal_regions']==list(REGIONS)
    assert result=={'placements':allocation,'legions':3}
    assert counts(state)=={r:before[r]+allocation.get(r,0) for r in rc.BELGICA_REGIONS}
    assert state['winter_track_legions']==0 and state['legions_track']==track
    assert state['rng'].getstate()==rng and validate_state(state)==[]
    assert all(state['spaces'][r]['control']==calculate_control(state,r) for r in rc.BELGICA_REGIONS)
    assert place_harvest(state) is None and len(seen)==1


@pytest.mark.parametrize('response',[None,{'use_default':True}])
def test_raw_default_preserves_concentration_and_legacy_result(response):
    state=position();before=counts(state)
    dest=max(REGIONS,key=lambda r:count_pieces(state,r,rc.ROMANS,rc.LEGION)+count_pieces(state,r,rc.ROMANS,rc.AUXILIA))
    state['decision_agent']=lambda *a:response
    assert place_harvest(state)=={'region':dest,'legions':3}
    assert counts(state)=={r:before[r]+(3 if r==dest else 0) for r in rc.BELGICA_REGIONS}
    assert validate_state(state)==[]


@pytest.mark.parametrize('bad',[None,{}, {'decline':True},{'placements':{}}, {'placements':[]},
    {'placements':{rc.MORINI:2}}, {'placements':{rc.MORINI:4}},
    {'placements':{rc.PROVINCIA:3}}, {'placements':{rc.MORINI:True,rc.NERVII:2}},
    {'placements':{rc.MORINI:3.0}}, {'placements':{rc.MORINI:-1,rc.NERVII:4}},
    {'placements':{rc.MORINI:3,rc.NERVII:0}}, {'placements':{rc.MORINI:3},'extra':True},
    {'use_default':1}])
def test_invalid_allocation_rejected_before_any_placement(bad):
    state=position();request={'count':3,'legal_regions':list(REGIONS)};before=encode(state)
    with pytest.raises(ValueError):validate(state,request,bad)
    assert encode(state)==before


@pytest.mark.parametrize('remaining',[0,1,2])
def test_only_actual_winter_track_reserve_can_be_placed(remaining):
    state=position()
    place_piece(state,rc.PROVINCIA,rc.ROMANS,rc.LEGION,3-remaining,from_winter_track=True)
    seen=[]
    def agent(board,faction,request):
        seen.append(request);return {'placements':{rc.NERVII:remaining}}
    state['decision_agent']=agent
    result=place_harvest(state)
    assert state['winter_track_legions']==0 and validate_state(state)==[]
    if remaining:assert result['legions']==remaining and len(seen)==1
    else:assert result is None and seen==[]


@pytest.mark.parametrize('kwargs',[{'count':4},{'count':True},{'count':-1},
    {'piece_type':rc.AUXILIA},{'from_fallen':True},{'from_legions_track':True}])
def test_winter_track_piece_helper_rejects_overdraw_bad_count_or_source(kwargs):
    state=position();before=encode(state)
    args={'piece_type':rc.LEGION,'count':1,'from_winter_track':True};args.update(kwargs)
    with pytest.raises(PieceError):place_piece(state,rc.MORINI,rc.ROMANS,**args)
    assert encode(state)==before


def test_full_first_winter_asks_after_quarters_before_ordinary_harvest_and_only_once():
    state=position();seen=[]
    def agent(board,faction,request):
        if request['kind']!=KIND:return None
        assert faction==rc.ROMANS and board['winter_count']==1
        seen.append((deepcopy(request),counts(board)))
        return {'placements':{r:1 for r in rc.BELGICA_REGIONS}}
    state['decision_agent']=agent
    result=run_winter_round(state)
    assert len(seen)==1
    assert result['phases']['harvest_belgica_legions']=={
        'placements':{r:1 for r in rc.BELGICA_REGIONS},'legions':3}
    assert counts(state)=={r:n+1 for r,n in seen[0][1].items()}
    assert state['winter_track_legions']==0 and validate_state(state)==[]
    assert 'first_winter_special' not in state


def test_native_first_winter_result_keeps_existing_default_shape():
    state=position();state['non_player_factions'].add(rc.ROMANS)
    def no_human(*args):pytest.fail('Bot placement requested human input')
    # Other reactive callbacks have their own contracts; observe only this kind.
    state['decision_agent']=lambda st,fa,re:no_human() if re['kind']==KIND else None
    result=run_winter_round(state)
    placed=result['phases']['harvest_belgica_legions']
    assert set(placed)=={'region','legions'} and placed['legions']==3
    assert state['winter_track_legions']==0 and validate_state(state)==[]


def test_cli_can_distribute_all_three_with_board_inspection():
    from fs_bot.cli.reactive import make_cli_reactive
    state=position();before=encode(state);output=StringIO()
    request={'kind':KIND,'count':3,'legal_regions':list(REGIONS),'source':'winter_track'}
    answer=make_cli_reactive({rc.ROMANS},StringIO('board\n2\n2\n'),output)(state,rc.ROMANS,request)
    assert answer=={'placements':{r:1 for r in REGIONS}}
    assert 'Legions' in output.getvalue() and encode(state)==before


@pytest.mark.parametrize('bad',[None,{'placements':{rc.PROVINCIA:3}}])
def test_durable_winter_allocation_preserves_pending_and_replays_after_save(tmp_path,bad):
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.state.serialize import save_game,load_game
    from fs_bot.tools.seat_session import SeatSession,DecisionPending,board_copy
    state=position();session=SeatSession(state,{'seat':rc.ROMANS},[],HumanTurnDisplay(StringIO()))
    def install(current):
        current.state['decision_agent']=lambda st,fa,re:current.reactive(st,fa,re) if re['kind']==KIND else None
    def attempt(current):
        def driver(*args):pass
        driver.transaction_checkpoint=current.checkpoint;driver.transaction_restore=current.restore
        with _action_transaction(current.state,driver):return run_winter_round(current.state)
    install(session);before=encode(board_copy(state))
    with pytest.raises(DecisionPending):attempt(session)
    pending=deepcopy(session.data['pending'])
    assert decode(pending['request'])['kind']==KIND
    payload={'decision_id':pending['id'],'response':bad};session.import_inbox(payload)
    with pytest.raises(DecisionPending):attempt(session)
    assert session.data['pending']==pending and session.data['queue']==[payload]
    assert encode(board_copy(state))==before and not session.data['journal']
    path=tmp_path/'harvest.json';save_game(state,path,meta=session.meta,log=session.log)
    restored,meta,log=load_game(path);resumed=SeatSession(restored,meta,log,HumanTurnDisplay(StringIO()));install(resumed)
    with pytest.raises(DecisionPending):attempt(resumed)
    assert resumed.data['pending']==pending and resumed.data['queue']==[payload]
    response={'placements':{r:1 for r in rc.BELGICA_REGIONS}}
    resumed.import_inbox({'decision_id':pending['id'],'response':response})
    result=attempt(resumed);resumed.finish()
    assert result['phases']['harvest_belgica_legions']['placements']==response['placements']
    assert not resumed.data['pending'] and not resumed.data['queue']
    assert log[0]['assistant_id']==pending['id'] and decode(log[0]['assistant_response'])==response
    replay=position();replay['decision_agent']=lambda st,fa,re:response if re['kind']==KIND else None
    assert run_winter_round(replay)==result
    assert encode(board_copy(replay))==encode(board_copy(restored))


@pytest.mark.parametrize('expedition',[False,True])
@pytest.mark.parametrize('npc',[False,True])
def test_post_interlude_first_harvest_obeys_actual_expedition_reserve(expedition,npc):
    from fs_bot.engine.interlude import run_interlude
    state=setup_scenario(rc.SCENARIO_GALLIC_WAR,seed=9)
    state['non_player_factions']={rc.ROMANS,rc.AEDUI,rc.BELGAE,rc.GERMANS}
    run_interlude(state,britannia_decision=expedition)
    if not npc:state['non_player_factions'].discard(rc.ROMANS)
    state['non_player_factions'].add(rc.ARVERNI)
    reserved=state.get('winter_track_legions',0)
    assert bool(reserved)==expedition
    seen=[]
    def agent(board,faction,request):
        if request['kind']!=KIND:return None
        seen.append(request);return {'placements':{rc.MORINI:1,rc.NERVII:2}}
    state['decision_agent']=agent
    result=run_winter_round(state)
    assert len(seen)==int(expedition and not npc)
    if expedition:
        placed=result['phases']['harvest_belgica_legions']
        if npc:assert set(placed)=={'region','legions'} and placed['legions']==3
        else:assert placed['placements']=={rc.MORINI:1,rc.NERVII:2}
    else:assert 'harvest_belgica_legions' not in result['phases']
    assert not state['first_harvest_after_interlude_pending']
    assert state.get('winter_track_legions',0)==0 and validate_state(state)==[]


def test_stale_request_cannot_overdraw_winter_box():
    state=position();request={'count':3,'legal_regions':list(REGIONS)}
    place_piece(state,rc.PROVINCIA,rc.ROMANS,rc.LEGION,1,from_winter_track=True)
    before=encode(state)
    with pytest.raises(ValueError):validate(state,request,{'placements':{rc.MORINI:3}})
    assert encode(state)==before


def test_no_first_harvest_rule_never_spends_a_held_winter_reserve():
    state=position();state['first_winter_special'].pop('harvest_place_legions_in_belgica')
    seen=[]
    state['decision_agent']=lambda st,fa,re:seen.append(re) if re['kind']==KIND else None
    result=run_winter_round(state)
    assert 'harvest' in result['phases'] and 'harvest_belgica_legions' not in result['phases']
    assert seen==[] and state['winter_track_legions']==3
    assert validate_state(state)==[]
