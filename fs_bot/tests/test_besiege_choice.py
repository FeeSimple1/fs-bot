"""Besiege's Roman chooses a physical target (§4.2.3/A4.2.3)."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece,count_pieces
from fs_bot.battle.resolve import resolve_battle
KIND='besiege_target'


def target_options(*args,**kwargs):
    from fs_bot.engine.besiege_choice import target_options as options
    return options(*args,**kwargs)


def validate_response(*args,**kwargs):
    from fs_bot.engine.besiege_choice import validate_response as validate
    return validate(*args,**kwargs)
from fs_bot.state.state_schema import build_initial_state,validate_state
from fs_bot.state.serialize import encode,decode

REGION=rc.SEQUANI


def position(scenario=rc.SCENARIO_GREAT_REVOLT,defender=rc.ARVERNI,*,citadel=True):
    state=build_initial_state(scenario,seed=17)
    state['non_player_factions']={defender}
    place_piece(state,REGION,rc.ROMANS,rc.LEGION,1,from_legions_track=True)
    place_piece(state,REGION,defender,rc.WARBAND,6)
    place_piece(state,REGION,defender,rc.CITADEL if citadel else rc.ALLY)
    place_piece(state,REGION,defender,rc.ALLY)
    for tribe in (rc.TRIBE_SEQUANI,rc.TRIBE_HELVETII):
        state['tribes'][tribe]['allied_faction']=defender
    assert validate_state(state)==[]
    return state


def resolve(state,defender=rc.ARVERNI,default=rc.CITADEL):
    return resolve_battle(state,REGION,rc.ROMANS,defender,
        besiege_target=default,retreat_declaration=False,no_counterattack=True)


def target(piece,tribe=None):return {'piece_type':piece,'tribe':tribe}


def agent_for(state,response):
    seen=[]
    def agent(board,faction,request):
        if request['kind']!=KIND:return None
        assert faction==rc.ROMANS
        seen.append(deepcopy(request))
        return response
    state['decision_agent']=agent
    return seen


@pytest.mark.parametrize('scenario',[rc.SCENARIO_GREAT_REVOLT,rc.SCENARIO_ARIOVISTUS])
@pytest.mark.parametrize('piece,tribe',[(rc.CITADEL,rc.TRIBE_SEQUANI),(rc.ALLY,rc.TRIBE_HELVETII)])
def test_roman_selects_ally_or_citadel_and_exact_tribe(scenario,piece,tribe):
    state=position(scenario)
    seen=agent_for(state,{'target':target(piece,tribe)})
    result=resolve(state)
    assert len(seen)==1
    assert seen[0]['targets']==[target(rc.CITADEL,rc.TRIBE_SEQUANI),target(rc.ALLY,rc.TRIBE_HELVETII)]
    assert result['besiege']=={'removed':piece,'tribe':tribe}
    assert state['tribes'][tribe]['allied_faction'] is None
    other=rc.TRIBE_HELVETII if tribe==rc.TRIBE_SEQUANI else rc.TRIBE_SEQUANI
    assert state['tribes'][other]['allied_faction']==rc.ARVERNI
    assert validate_state(state)==[]


@pytest.mark.parametrize('tribe',[rc.TRIBE_SEQUANI,rc.TRIBE_HELVETII])
def test_choose_between_two_physical_ally_discs(tribe):
    state=position(citadel=False)
    agent_for(state,{'target':target(rc.ALLY,tribe)})
    result=resolve(state,default=rc.ALLY)
    assert result['besiege']['tribe']==tribe
    assert count_pieces(state,REGION,rc.ARVERNI,rc.ALLY)==1
    assert state['tribes'][tribe]['allied_faction'] is None
    assert validate_state(state)==[]


@pytest.mark.parametrize('piece,tribe',[(rc.ALLY,rc.TRIBE_SEQUANI),(rc.ALLY,rc.TRIBE_HELVETII),(rc.SETTLEMENT,None)])
def test_expansion_can_choose_settlement_instead_of_either_ally(piece,tribe):
    state=position(rc.SCENARIO_ARIOVISTUS,rc.GERMANS,citadel=False)
    place_piece(state,REGION,rc.GERMANS,rc.SETTLEMENT)
    seen=agent_for(state,{'target':target(piece,tribe)})
    result=resolve(state,rc.GERMANS,rc.ALLY)
    assert target(rc.SETTLEMENT) in seen[0]['targets']
    assert result['besiege']['removed']==piece
    if piece==rc.SETTLEMENT:
        assert count_pieces(state,REGION,rc.GERMANS,rc.ALLY)==2
        assert all(state['tribes'][t]['allied_faction']==rc.GERMANS for t in (rc.TRIBE_SEQUANI,rc.TRIBE_HELVETII))
    else:assert count_pieces(state,REGION,rc.GERMANS,rc.SETTLEMENT)==1
    assert validate_state(state)==[]


def test_decline_removal_keeps_both_tribes_allied():
    state=position();seen=agent_for(state,{'decline':True})
    result=resolve(state)
    assert seen and result['besiege'] is None
    assert count_pieces(state,REGION,rc.ARVERNI,rc.CITADEL)==1
    assert count_pieces(state,REGION,rc.ARVERNI,rc.ALLY)==1


@pytest.mark.parametrize('response',[None,{'use_default':True}])
def test_raw_defer_retains_legacy_type_and_deterministic_identity(response):
    state=position();agent_for(state,response)
    result=resolve(state)
    assert result['besiege']=={'removed':rc.CITADEL}
    assert state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] is None


@pytest.mark.parametrize('response',[{},None,{'target':None},{'target':rc.ALLY},
    {'target':target(rc.ALLY,rc.TRIBE_SEQUANI)}, {'target':target(rc.CITADEL,rc.TRIBE_HELVETII)},
    {'target':target(rc.ALLY,rc.TRIBE_NERVII)},{'target':target(rc.SETTLEMENT)},
    {'decline':False},{'decline':1},{'use_default':1},{'target':target(rc.ALLY,rc.TRIBE_HELVETII),'extra':1}])
def test_validator_rejects_missing_or_forged_identity_without_mutation(response):
    state=position();before=encode(state)
    request={'region':REGION,'defender':rc.ARVERNI,'targets':target_options(state,REGION,rc.ARVERNI)}
    with pytest.raises(ValueError):validate_response(state,request,response)
    assert encode(state)==before


def test_validator_rechecks_stale_options_on_live_board():
    from fs_bot.board.pieces import remove_piece,clear_allied_tribe
    state=position();offered=target_options(state,REGION,rc.ARVERNI)
    remove_piece(state,REGION,rc.ARVERNI,rc.ALLY)
    clear_allied_tribe(state,REGION,rc.ARVERNI,rc.ALLY,tribe=rc.TRIBE_HELVETII)
    request={'region':REGION,'defender':rc.ARVERNI,'targets':offered}
    with pytest.raises(ValueError):validate_response(state,request,{'target':target(rc.ALLY,rc.TRIBE_HELVETII)})


def test_zero_losses_still_allow_besiege_and_citadel_halving_survives(monkeypatch):
    state=position();seen=agent_for(state,{'target':target(rc.CITADEL,rc.TRIBE_SEQUANI)})
    original=__import__('fs_bot.battle.resolve',fromlist=['calculate_losses']).calculate_losses
    losses=[]
    def record(*args,**kwargs):
        result=original(*args,**kwargs);losses.append(result);return result
    monkeypatch.setattr('fs_bot.battle.resolve.calculate_losses',record)
    result=resolve(state)
    assert seen and result['besiege']['removed']==rc.CITADEL
    assert result['attack']['losses_taken']==0
    assert count_pieces(state,REGION,rc.ARVERNI,rc.WARBAND)==6


def test_cli_board_inspection_and_named_choice():
    from fs_bot.cli.reactive import make_cli_reactive
    state=position();out=StringIO()
    request={'kind':KIND,'region':REGION,'defender':rc.ARVERNI,
             'targets':target_options(state,REGION,rc.ARVERNI),'may_decline':True}
    before=encode(state)
    response=make_cli_reactive({rc.ROMANS},StringIO('board\n2\n'),out)(state,rc.ROMANS,request)
    assert response=={'target':target(rc.ALLY,rc.TRIBE_HELVETII)}
    assert rc.TRIBE_HELVETII in out.getvalue()
    assert encode(state)==before


def test_save_load_has_identical_choice_result_and_rng():
    state=position();other=decode(encode(state))
    for board in (state,other):agent_for(board,{'target':target(rc.ALLY,rc.TRIBE_HELVETII)})
    assert resolve(state)==resolve(other)
    for board in (state,other):board.pop('decision_agent')
    assert encode(state)==encode(other)


def test_command_executor_requests_roman_choice_once():
    from fs_bot.engine.execute import execute_decision
    state=position();state['resources'][rc.ROMANS]=10
    seen=agent_for(state,{'target':target(rc.ALLY,rc.TRIBE_HELVETII)})
    plan={'command':rc.CMD_BATTLE,'sa':rc.SA_BESIEGE,'sa_regions':[REGION],
          'details':{'battle_plan':[{'region':REGION,'target':rc.ARVERNI}]}}
    result=execute_decision(state,rc.ROMANS,{'player_action':plan})
    assert result['executed'] and not result['errors'],result
    assert len(seen)==1
    assert state['tribes'][rc.TRIBE_HELVETII]['allied_faction'] is None
    assert state['tribes'][rc.TRIBE_SEQUANI]['allied_faction']==rc.ARVERNI


def test_preview_does_not_consume_live_agent_or_rng():
    from fs_bot.engine.moves import validate_player_action
    state=position();state['resources'][rc.ROMANS]=10
    def live(*args):pytest.fail('Preview consumed live input')
    state['decision_agent']=live
    before=encode({k:v for k,v in state.items() if k!='decision_agent'})
    plan={'command':rc.CMD_BATTLE,'sa':rc.SA_BESIEGE,'sa_regions':[REGION],
          'details':{'battle_plan':[{'region':REGION,'target':rc.ARVERNI}]}}
    assert validate_player_action(state,rc.ROMANS,plan)[0]
    assert encode({k:v for k,v in state.items() if k!='decision_agent'})==before


@pytest.mark.parametrize('decline',[False,True])
def test_ballistae_keeps_besiege_halving_cancellation_when_removal_declined(decline):
    from fs_bot.cards.capabilities import activate_capability
    state=position();activate_capability(state,10,rc.EVENT_UNSHADED)
    agent_for(state,{'decline':True} if decline else {'target':target(rc.CITADEL,rc.TRIBE_SEQUANI)})
    result=resolve(state)
    assert result['attack']['losses_taken']==1
    assert (result['besiege'] is None)==decline


@pytest.mark.parametrize('bad',[None,{}, {'target':target(rc.ALLY,rc.TRIBE_SEQUANI)}])
def test_invalid_durable_target_stays_pending_across_rollback_and_save_resume(tmp_path,bad):
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.state.serialize import save_game,load_game
    from fs_bot.tools.seat_session import SeatSession,DecisionPending,board_copy
    state=position();session=SeatSession(state,{'seat':rc.ROMANS},[],HumanTurnDisplay(StringIO()))
    state['decision_agent']=session.reactive
    def attempt(current):
        def driver(*args):pass
        driver.transaction_checkpoint=current.checkpoint
        driver.transaction_restore=current.restore
        with _action_transaction(current.state,driver):
            return resolve(current.state)
    before=encode(board_copy(state))
    with pytest.raises(DecisionPending):attempt(session)
    pending=deepcopy(session.data['pending'])
    assert decode(pending['request'])['kind']==KIND
    payload={'decision_id':pending['id'],'response':bad};session.import_inbox(payload)
    with pytest.raises(DecisionPending):attempt(session)
    assert session.data['pending']==pending and session.data['queue']==[payload]
    assert encode(board_copy(state))==before and not session.data['journal']
    path=tmp_path/'besiege.json';save_game(state,path,meta=session.meta,log=session.log)
    restored,meta,log=load_game(path);resumed=SeatSession(restored,meta,log,HumanTurnDisplay(StringIO()))
    restored['decision_agent']=resumed.reactive
    with pytest.raises(DecisionPending):attempt(resumed)
    assert resumed.data['pending']==pending and resumed.data['queue']==[payload]
    response={'target':target(rc.ALLY,rc.TRIBE_HELVETII)}
    resumed.import_inbox({'decision_id':pending['id'],'response':response})
    result=attempt(resumed);resumed.finish()
    assert result['besiege']['tribe']==rc.TRIBE_HELVETII
    assert not resumed.data['pending'] and not resumed.data['queue']
    assert log[0]['assistant_id']==pending['id']
    assert decode(log[0]['assistant_response'])==response
    replay=position()
    replay['decision_agent']=lambda st,fa,req:decode(log[0]['assistant_response']) if req['kind']==KIND else None
    resolve(replay)
    assert encode(board_copy(replay))==encode(board_copy(restored))


def test_besiege_choice_also_applies_when_defender_declares_retreat():
    state=position();place_piece(state,rc.MANDUBII,rc.ARVERNI,rc.WARBAND)
    agent_for(state,{'target':target(rc.ALLY,rc.TRIBE_HELVETII)})
    result=resolve_battle(state,REGION,rc.ROMANS,rc.ARVERNI,
        besiege_target=rc.CITADEL,retreat_declaration=True,retreat_region=rc.MANDUBII,
        no_counterattack=True)
    assert result['defender_retreated']
    assert result['besiege']=={'removed':rc.ALLY,'tribe':rc.TRIBE_HELVETII}
    assert validate_state(state)==[]


def test_multiregion_battle_requests_separate_live_targets():
    from fs_bot.engine.execute import execute_decision
    state=position();state['resources'][rc.ROMANS]=10
    place_piece(state,rc.MANDUBII,rc.ROMANS,rc.LEGION,1,from_legions_track=True)
    place_piece(state,rc.MANDUBII,rc.ARVERNI,rc.WARBAND,6)
    place_piece(state,rc.MANDUBII,rc.ARVERNI,rc.ALLY)
    state['tribes'][rc.TRIBE_SENONES]['allied_faction']=rc.ARVERNI
    seen=[]
    def agent(st,faction,request):
        if request['kind']!=KIND:return None
        seen.append(request['region'])
        tribe=rc.TRIBE_HELVETII if request['region']==REGION else rc.TRIBE_SENONES
        return {'target':target(rc.ALLY,tribe)}
    state['decision_agent']=agent
    plan={'command':rc.CMD_BATTLE,'sa':rc.SA_BESIEGE,'sa_regions':[REGION,rc.MANDUBII],
          'details':{'battle_plan':[{'region':r,'target':rc.ARVERNI} for r in (REGION,rc.MANDUBII)]}}
    result=execute_decision(state,rc.ROMANS,{'player_action':plan})
    assert result['executed'] and not result['errors'],result
    assert seen==[REGION,rc.MANDUBII]
    assert state['tribes'][rc.TRIBE_SENONES]['allied_faction'] is None
    assert state['tribes'][rc.TRIBE_HELVETII]['allied_faction'] is None
    assert state['tribes'][rc.TRIBE_SEQUANI]['allied_faction']==rc.ARVERNI
    assert validate_state(state)==[]
