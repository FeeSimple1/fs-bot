"""§4.5.2: the Belgae choose quantity; §8.5.1 NPCs use all able Warbands."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, count_pieces_by_state, flip_piece, remove_piece
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine.execute import _execute_rampage, execute_decision
from fs_bot.engine.game_engine import ACTION_COMMAND_SA, _action_transaction
from fs_bot.state.serialize import encode, decode, save_game, load_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import SeatSession, DecisionPending, board_copy, validate_response
from fs_bot.tests.test_raid_intimidate_decisions import _driver

R=rc.TREVERI
D=rc.NERVII


def board(scenario=rc.SCENARIO_GREAT_REVOLT, hidden=5, targets=5, owner=rc.ROMANS):
    state=build_initial_state(scenario,seed=11)
    state.update(current_card=1,next_card=4,non_player_factions=set())
    leader=rc.BODUOGNATUS if scenario in rc.ARIOVISTUS_SCENARIOS else rc.AMBIORIX
    place_piece(state,R,rc.BELGAE,rc.LEADER,leader_name=leader)
    if hidden:place_piece(state,R,rc.BELGAE,rc.WARBAND,hidden)
    if targets:place_piece(state,R,owner,rc.AUXILIA if owner==rc.ROMANS else rc.WARBAND,targets)
    state['resources'][rc.BELGAE]=10
    assert not validate_state(state)
    return state


def action(count=1, *, command=rc.CMD_RALLY, owner=rc.ROMANS, explicit=True):
    entry={'region':R,'target':owner}
    if explicit:entry['count']=count
    return {'command':command,'sa':rc.SA_RAMPAGE,'sa_regions':[entry],'sa_timing':'after',
            'details':{'rally_plan':{'steps':[{'region':R,'action':'place_warbands','count':0}]}}}


def hidden(state):
    return count_pieces_by_state(state,R,rc.BELGAE,rc.WARBAND,rc.HIDDEN)


@pytest.mark.parametrize('scenario',rc.ALL_SCENARIOS)
@pytest.mark.parametrize('count',[1,3,5])
def test_exact_quantity_in_every_scenario_leaves_unselected_warbands_hidden(scenario,count):
    state=board(scenario)
    result=_execute_rampage(state,rc.BELGAE,action(count))
    assert result['executed'] and not result['errors']
    assert result['rampages'][0]['count']==count
    assert hidden(state)==5-count
    assert count_pieces_by_state(state,R,rc.BELGAE,rc.WARBAND,rc.REVEALED)==count
    assert count_pieces(state,R,rc.ROMANS,rc.AUXILIA)==5-count
    assert not validate_state(state)


@pytest.mark.parametrize('count',[-1,0,True,False,1.5,'1',None,[],{},6])
def test_invalid_explicit_count_rejects_before_agreement_reaction_rng_or_flip(count):
    state=board();seen=[]
    def agent(*args):seen.append(args);return {'retreat':False}
    state['decision_agent']=agent
    before=encode(board_copy(state))
    result=_execute_rampage(state,rc.BELGAE,action(count))
    assert result['errors'] and not result['executed']
    assert encode(board_copy(state))==before and not seen


@pytest.mark.parametrize('scenario',rc.ALL_SCENARIOS)
def test_native_npc_default_uses_all_able_warbands_instead_of_two(scenario):
    state=board(scenario)
    state['non_player_factions']={rc.BELGAE,rc.ROMANS}
    result=_execute_rampage(state,rc.BELGAE,action(explicit=False))
    assert result['executed'] and not result['errors']
    assert result['rampages'][0]['count']==5 and hidden(state)==0
    assert count_pieces(state,R,rc.ROMANS,rc.AUXILIA)==0
    assert not validate_state(state)


@pytest.mark.parametrize('targets,expected',[(1,0),(3,2),(5,4)])
def test_npc_before_battle_uses_all_able_but_leaves_last_enemy_piece(targets,expected):
    state=board(hidden=7,targets=targets)
    state['non_player_factions']={rc.BELGAE,rc.ROMANS}
    result=_execute_rampage(state,rc.BELGAE,action(command=rc.CMD_BATTLE,explicit=False))
    assert not result['errors']
    assert (result['rampages'][0]['count'] if result['rampages'] else 0)==expected
    assert hidden(state)==7-expected
    assert count_pieces(state,R,rc.ROMANS,rc.AUXILIA)==1


@pytest.mark.parametrize('hidden_count,target_count',[(2,5),(5,2),(5,0)])
def test_explicit_quantity_must_fit_both_current_pools(hidden_count,target_count):
    state=board(hidden=hidden_count,targets=target_count)
    before=encode(state)
    result=_execute_rampage(state,rc.BELGAE,action(3))
    assert not result['executed'] and result['errors']
    assert encode(state)==before


def test_human_before_battle_quantity_is_not_npc_last_piece_policy():
    state=board(hidden=3,targets=3)
    result=_execute_rampage(state,rc.BELGAE,action(3,command=rc.CMD_BATTLE))
    assert result['executed'] and result['rampages'][0]['count']==3
    assert not count_pieces(state,R,rc.ROMANS,rc.AUXILIA)


def test_ariovistus_arverni_removal_and_scouted_pool_keep_chosen_count():
    state=board(rc.SCENARIO_ARIOVISTUS,owner=rc.ARVERNI)
    flip_piece(state,R,rc.ARVERNI,rc.WARBAND,5,from_state=rc.HIDDEN,to_state=rc.SCOUTED)
    # Even a friendly-controlled adjacent refuge cannot allow Arverni Retreat.
    place_piece(state,D,rc.ARVERNI,rc.WARBAND)
    result=_execute_rampage(state,rc.BELGAE,action(3,owner=rc.ARVERNI))
    assert result['executed'] and result['rampages'][0]['count']==3
    assert count_pieces_by_state(state,R,rc.ARVERNI,rc.WARBAND,rc.SCOUTED)==2
    assert count_pieces(state,D,rc.ARVERNI,rc.WARBAND)==1
    assert hidden(state)==2 and not validate_state(state)


@pytest.mark.parametrize('timing',[False,True])
def test_terminal_offers_full_range_and_authors_count_without_mutation(timing):
    from fs_bot.cli.human_plan import _collect_rampage
    from fs_bot.cli.action_windows import inspect_board
    state=board();answers=[R,rc.ROMANS,'b','3']
    if timing:
        state['_cli_action_windows']=True
        answers=['Finish voluntary removal']+answers+['Finish voluntary removal']
    before=encode(state);output=StringIO()
    with inspect_board(state,output):
        entries,extra=_collect_rampage(state,rc.BELGAE,StringIO('\n'.join(answers)+'\n'),output)
    assert entries[0]['count']==3 and encode(state)==before
    assert '5) 5' in output.getvalue() and 'BOARD' in output.getvalue().upper()
    assert 'Please enter' not in output.getvalue()


@pytest.mark.parametrize('flow',['ordinary','durable','grant'])
def test_missing_human_quantity_never_silently_uses_default(flow):
    state=board();plan=action(explicit=False);before=encode(state)
    if flow=='ordinary':
        result=execute_decision(state,rc.BELGAE,{'action':ACTION_COMMAND_SA,'player_action':plan})
        assert not result['executed'] and result['rejected'] and 'count' in result['reason']
    elif flow=='durable':
        with pytest.raises(ValueError,match='count'):
            validate_response(state,{'kind':'turn','faction':rc.BELGAE,'options':[ACTION_COMMAND_SA]},
                              {'action':ACTION_COMMAND_SA,'player_action':plan})
    else:
        from fs_bot.engine.free_actions import validate_free_action_response
        plan.pop('command')
        error=validate_free_action_response(state,rc.BELGAE,
            {'kind':'free_action','request_type':'event_sa','allowed_sas':[rc.SA_RAMPAGE]},plan)
        assert error and 'count' in error
    assert encode(state)==before


def test_victim_pending_request_receives_exact_quantity_and_saves_resumes(tmp_path):
    state=board();session=SeatSession(state,{'seat':rc.ROMANS},[],HumanTurnDisplay(StringIO()))
    state['decision_agent']=session.reactive;before=encode(board_copy(state))
    with pytest.raises(DecisionPending):
        with _action_transaction(state,_driver(session)):
            _execute_rampage(state,rc.BELGAE,action(3))
    pending=session.data['pending'];request=decode(pending['request'])
    assert request['context']=={'rampage':True,'num_pieces':3}
    assert encode(board_copy(state))==before
    path=tmp_path/'victim.json';save_game(state,path,meta=session.meta,log=session.log)
    restored,meta,log=load_game(path)
    resumed=SeatSession(restored,meta,log,HumanTurnDisplay(StringIO()));restored['decision_agent']=resumed.reactive
    resumed.import_inbox({'decision_id':pending['id'],'response':{'retreat':False}})
    with _action_transaction(restored,_driver(resumed)):
        result=_execute_rampage(restored,rc.BELGAE,action(3))
    resumed.finish()
    assert result['executed'] and hidden(restored)==2
    assert count_pieces(restored,R,rc.ROMANS,rc.AUXILIA)==2
    assert decode(log[0]['assistant_request'])['context']['num_pieces']==3
    assert not validate_state(restored)


def test_actor_accepted_count_survives_full_command_pause_save_and_replay(tmp_path):
    from fs_bot.cards.card_effects import _ally_tribe
    state=board()
    assert _ally_tribe(state,rc.TRIBE_TREVERI,rc.BELGAE)
    session=SeatSession(state,{'seat':rc.BELGAE},[],HumanTurnDisplay(StringIO()))
    request={'kind':'turn','options':[ACTION_COMMAND_SA],'position':'1st_eligible'}
    decision={'action':ACTION_COMMAND_SA,'player_action':action(3)}
    session.import_inbox([{'response':decision}])
    def step(current,pause):
        def agent(live,faction,request):
            if request['kind']=='retreat' and faction==rc.ROMANS:
                if pause:raise EOFError('pause at victim response')
                return {'retreat':False}
            return current.reactive(live,faction,request)
        current.state['decision_agent']=agent
        with _action_transaction(current.state,_driver(current)):
            accepted=current.ask(current.state,rc.BELGAE,request)
            return execute_decision(current.state,rc.BELGAE,accepted)
    before=encode(board_copy(state))
    with pytest.raises(EOFError):step(session,True)
    assert encode(board_copy(state))==before
    assert decode(session.data['journal'][0]['assistant_response'])==decision
    path=tmp_path/'actor.json';save_game(state,path,meta=session.meta,log=session.log)
    restored,meta,log=load_game(path)
    resumed=SeatSession(restored,meta,log,HumanTurnDisplay(StringIO()))
    result=step(resumed,False);resumed.finish()
    assert result['executed'] and result['sa_execution']['rampages'][0]['count']==3
    assert hidden(restored)==2 and count_pieces(restored,R,rc.ROMANS,rc.AUXILIA)==2
    assert decode(log[0]['assistant_response'])==decision
    assert not validate_state(restored)


def test_post_command_quantity_is_rechecked_instead_of_clamped():
    state=board()
    remove_piece(state,R,rc.BELGAE,rc.WARBAND,3)
    before=encode(state)
    result=_execute_rampage(state,rc.BELGAE,action(3))
    assert not result['executed'] and result['errors'] and encode(state)==before


@pytest.mark.parametrize('different_target',[False,True])
def test_counted_entries_cannot_repeat_a_region_or_select_two_victim_factions(different_target):
    state=board();plan=action(1)
    second=deepcopy(plan['sa_regions'][0])
    if different_target:
        place_piece(state,R,rc.AEDUI,rc.WARBAND,2)
        second['target']=rc.AEDUI
    plan['sa_regions'].append(second)
    before=encode(state)
    result=_execute_rampage(state,rc.BELGAE,plan)
    assert not result['executed'] and result['errors'] and encode(state)==before
    from fs_bot.engine.action_validation import validate_human_structure
    assert 'only once' in validate_human_structure(state,rc.BELGAE,plan)
