"""Card65: executor-owned March limits, original counters and all able Ambushes."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece,count_pieces,count_pieces_by_state
from fs_bot.engine import execute as ex
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state,validate_state


def board(executor=rc.BELGAE):
    state=build_initial_state(rc.SCENARIO_GREAT_REVOLT,seed=65)
    state.update(current_card=65,next_card=35,non_player_factions=set(),executing_faction=executor,event_params={})
    return state


def snapshot(state):
    return encode({k:v for k,v in state.items() if k!='decision_agent'})


def group(origin,destination,n):
    return {'origin':origin,'destination':destination,'warbands':n}


def install(state,marches,battles=()):
    seen=[]; answers=iter(battles)
    def agent(current,actor,request):
        seen.append((actor,deepcopy(request)))
        if request.get('request_type')=='german_guided_march':
            return {'marches':marches}
        if request.get('request_type')=='german_guided_ambush':
            return next(answers,None)
    state['decision_agent']=agent
    return seen


@pytest.mark.parametrize('executor',[rc.ROMANS,rc.ARVERNI,rc.AEDUI,rc.BELGAE])
def test_executor_can_choose_revealed_partial_group_and_native_target(executor):
    state=board(executor)
    place_piece(state,rc.SEQUANI,rc.GERMANS,rc.WARBAND,4,piece_state=rc.REVEALED)
    place_piece(state,rc.MANDUBII,rc.ROMANS,rc.AUXILIA,2,piece_state=rc.REVEALED)
    seen=install(state,[group(rc.SEQUANI,rc.MANDUBII,2)],[{'region':rc.MANDUBII,'defender':rc.ROMANS}])
    result=ex._resolve_card65_german_march_ambush(state,2)[0]
    assert any(actor==executor and r.get('request_type')=='german_guided_march' for actor,r in seen)
    assert any(actor==executor and r.get('request_type')=='german_guided_ambush' for actor,r in seen)
    assert count_pieces(state,rc.SEQUANI,rc.GERMANS,rc.WARBAND)==2
    assert count_pieces_by_state(state,rc.SEQUANI,rc.GERMANS,rc.WARBAND,rc.HIDDEN)==2
    assert count_pieces(state,rc.MANDUBII,rc.ROMANS,rc.AUXILIA)==1
    assert result['ambushes'][0]['defender']==rc.ROMANS
    assert validate_state(state)==[]


def test_arrivals_cannot_join_later_origin_or_flip_again():
    state=board()
    place_piece(state,rc.PROVINCIA,rc.GERMANS,rc.WARBAND,3,piece_state=rc.SCOUTED)
    place_piece(state,rc.SEQUANI,rc.GERMANS,rc.WARBAND,1,piece_state=rc.REVEALED)
    install(state,[group(rc.PROVINCIA,rc.SEQUANI,2),group(rc.SEQUANI,rc.MANDUBII,1)])
    ex._resolve_card65_german_march_ambush(state,2)
    assert count_pieces_by_state(state,rc.SEQUANI,rc.GERMANS,rc.WARBAND,rc.REVEALED)==2
    assert count_pieces_by_state(state,rc.SEQUANI,rc.GERMANS,rc.WARBAND,rc.HIDDEN)==0
    assert count_pieces_by_state(state,rc.MANDUBII,rc.GERMANS,rc.WARBAND,rc.HIDDEN)==1
    assert count_pieces_by_state(state,rc.PROVINCIA,rc.GERMANS,rc.WARBAND,rc.REVEALED)==1
    assert validate_state(state)==[]


def test_hide_only_origin_does_not_hide_later_arrivals():
    state=board()
    place_piece(state,rc.PROVINCIA,rc.GERMANS,rc.WARBAND,3,piece_state=rc.SCOUTED)
    place_piece(state,rc.SEQUANI,rc.GERMANS,rc.WARBAND,1,piece_state=rc.SCOUTED)
    install(state,[group(rc.PROVINCIA,rc.SEQUANI,2),group(rc.SEQUANI,None,0)])
    ex._resolve_card65_german_march_ambush(state,2)
    assert count_pieces_by_state(state,rc.SEQUANI,rc.GERMANS,rc.WARBAND,rc.REVEALED)==3
    assert count_pieces_by_state(state,rc.SEQUANI,rc.GERMANS,rc.WARBAND,rc.HIDDEN)==0
    assert validate_state(state)==[]


def test_all_able_regions_with_chosen_order_and_defenders():
    state=board()
    for region in (rc.MANDUBII,rc.ATREBATES):
        place_piece(state,region,rc.GERMANS,rc.WARBAND,4)
        place_piece(state,region,rc.ROMANS,rc.AUXILIA,3,piece_state=rc.REVEALED)
        place_piece(state,region,rc.AEDUI,rc.WARBAND,3,piece_state=rc.REVEALED)
    install(state,[],[{'region':rc.ATREBATES,'defender':rc.AEDUI},{'region':rc.MANDUBII,'defender':rc.ROMANS}])
    result=ex._resolve_card65_german_march_ambush(state,2)[0]
    assert [(b['region'],b['defender']) for b in result['ambushes']]==[(rc.ATREBATES,rc.AEDUI),(rc.MANDUBII,rc.ROMANS)]
    assert count_pieces(state,rc.ATREBATES,rc.AEDUI,rc.WARBAND)==1
    assert count_pieces(state,rc.MANDUBII,rc.ROMANS,rc.AUXILIA)==1
    assert count_pieces(state,rc.MANDUBII,rc.AEDUI,rc.WARBAND)==3


def test_zero_loss_ambush_is_still_able_and_reveals_germans():
    state=board()
    place_piece(state,rc.MANDUBII,rc.GERMANS,rc.WARBAND,1)
    place_piece(state,rc.MANDUBII,rc.ROMANS,rc.FORT)
    install(state,[],[{'region':rc.MANDUBII,'defender':rc.ROMANS}])
    result=ex._resolve_card65_german_march_ambush(state,2)[0]
    assert len(result['ambushes'])==1
    assert count_pieces_by_state(state,rc.MANDUBII,rc.GERMANS,rc.WARBAND,rc.REVEALED)==1
    assert count_pieces(state,rc.MANDUBII,rc.ROMANS,rc.FORT)==1


@pytest.mark.parametrize('bad',[
    {'decline':True}, {'use_default':1},
    {'marches':[group(rc.PROVINCIA,rc.SEQUANI,1)]*2},
    {'marches':[group(rc.PROVINCIA,rc.SEQUANI,1),group(rc.SEQUANI,rc.MANDUBII,1),group(rc.MANDUBII,rc.CARNUTES,1)]},
    {'marches':[group(rc.PROVINCIA,rc.MANDUBII,1)]},
    {'marches':[group(rc.PROVINCIA,rc.SEQUANI,True)]},
    {'marches':[group(rc.PROVINCIA,rc.SEQUANI,3)]},
    {'marches':[group(rc.PROVINCIA,rc.SEQUANI,0)]},
    {'marches':[dict(group(rc.PROVINCIA,rc.SEQUANI,1),leader=True)]},
])
def test_invalid_first_plan_is_atomic(bad):
    state=board()
    for region in (rc.PROVINCIA,rc.SEQUANI,rc.MANDUBII):
        place_piece(state,region,rc.GERMANS,rc.WARBAND,2)
    state['decision_agent']=lambda *args:bad
    before=snapshot(state)
    with pytest.raises(ValueError):
        ex._resolve_card65_german_march_ambush(state,2)
    assert snapshot(state)==before


@pytest.mark.parametrize('answer',[{'decline':True},{'region':rc.MANDUBII,'defender':rc.ROMANS},{'region':rc.SEQUANI,'defender':rc.GERMANS}])
def test_required_ambush_cannot_be_declined_or_redirected(answer):
    state=board()
    place_piece(state,rc.PROVINCIA,rc.GERMANS,rc.WARBAND,2,piece_state=rc.REVEALED)
    place_piece(state,rc.SEQUANI,rc.ROMANS,rc.AUXILIA,2,piece_state=rc.REVEALED)
    install(state,[group(rc.PROVINCIA,rc.SEQUANI,1)],[answer])
    before=snapshot(state)
    with pytest.raises(ValueError):
        ex._resolve_card65_german_march_ambush(state,2)
    assert snapshot(state)==before


def test_terminal_exact_groups_and_battle_choices_support_board_inspection():
    from fs_bot.cards.german_guidance import march_request,battle_request
    from fs_bot.cli.free_actions import collect_free_action
    state=board()
    place_piece(state,rc.PROVINCIA,rc.GERMANS,rc.WARBAND,3)
    place_piece(state,rc.MANDUBII,rc.GERMANS,rc.WARBAND,2)
    place_piece(state,rc.MANDUBII,rc.ROMANS,rc.AUXILIA,2,piece_state=rc.REVEALED)
    before=snapshot(state);out=StringIO()
    response=collect_free_action(state,rc.BELGAE,march_request(state,2),StringIO(
        'board\nChoose exact action\nb\nProvincia\n1 Warbands\nSequani\nFinish March selection\n'),out)
    assert response=={'marches':[group(rc.PROVINCIA,rc.SEQUANI,1)]}
    battle=collect_free_action(state,rc.BELGAE,battle_request(state,{rc.MANDUBII}),StringIO(
        'b\nChoose exact action\nMandubii\nRomans\n'),out)
    assert battle=={'region':rc.MANDUBII,'defender':rc.ROMANS}
    assert out.getvalue().count('AVAILABLE PIECES')==3
    assert snapshot(state)==before


def test_event_keeps_execution_owner_separate_from_german_force():
    state=board()
    place_piece(state,rc.PROVINCIA,rc.GERMANS,rc.WARBAND,2)
    seen=install(state,[group(rc.PROVINCIA,rc.SEQUANI,1)])
    result=ex._execute_event(state,rc.BELGAE,{'command':'Event','sa':'No SA','sa_regions':[],
        'details':{'card_id':65,'text_preference':rc.EVENT_UNSHADED,'event_params':{}}},human=True)
    assert result['executed']
    actor,request=next((actor,r) for actor,r in seen if r.get('request_type')=='german_guided_march')
    assert actor==rc.BELGAE and request['acting_faction']==rc.GERMANS
    assert count_pieces(state,rc.PROVINCIA,rc.GERMANS,rc.WARBAND)==1


def test_stationary_permission_cannot_leak_to_other_event_marches():
    from fs_bot.cards.german_guidance import action_for
    from fs_bot.cards.arduenna_march import execute_march
    state=board()
    place_piece(state,rc.PROVINCIA,rc.GERMANS,rc.WARBAND,2,piece_state=rc.REVEALED)
    before=snapshot(state)
    action=action_for({'marches':[group(rc.PROVINCIA,None,0)]})
    with pytest.raises(ValueError):
        execute_march(state,rc.GERMANS,action,target_regions={rc.SEQUANI})
    assert snapshot(state)==before


def test_durable_save_at_ambush_and_rejected_repeat_region_preserve_whole_event(tmp_path):
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.state.serialize import decode,save_game,load_game
    from fs_bot.tools.seat_session import SeatSession,DecisionPending,board_copy
    state=board()
    place_piece(state,rc.PROVINCIA,rc.GERMANS,rc.WARBAND,4,piece_state=rc.REVEALED)
    place_piece(state,rc.SEQUANI,rc.ROMANS,rc.AUXILIA,3,piece_state=rc.REVEALED)
    place_piece(state,rc.ATREBATES,rc.GERMANS,rc.WARBAND,2)
    place_piece(state,rc.ATREBATES,rc.ROMANS,rc.AUXILIA,3,piece_state=rc.REVEALED)
    ses=SeatSession(state,{'seat':rc.BELGAE},[],HumanTurnDisplay(StringIO()))
    state['decision_agent']=ses.reactive;before=encode(board_copy(state))
    def step():
        def driver(*args):
            pass
        driver.transaction_checkpoint=ses.checkpoint;driver.transaction_restore=ses.restore
        with _action_transaction(state,driver):
            return ex._resolve_card65_german_march_ambush(state,2)
    def pending():
        with pytest.raises(DecisionPending):
            step()
        assert encode(board_copy(state))==before
        return decode(ses.data['pending']['request'])
    assert pending()['request_type']=='german_guided_march'
    first=deepcopy(ses.data['pending'])
    ses.import_inbox({'decision_id':first['id'],'response':{'decline':True}})
    pending();assert ses.error and ses.data['pending']==first
    ses.import_inbox({'decision_id':first['id'],'response':{'marches':[group(rc.PROVINCIA,rc.SEQUANI,2)]}})
    assert pending()['request_type']=='german_guided_ambush'
    save_game(state,tmp_path/'save.json',meta=ses.meta,log=ses.log)
    state,meta,log=load_game(tmp_path/'save.json',validate=True)
    ses=SeatSession(state,meta,log,HumanTurnDisplay(StringIO()));state['decision_agent']=ses.reactive
    ses.import_inbox({'decision_id':ses.data['pending']['id'],'response':{'region':rc.ATREBATES,'defender':rc.ROMANS}})
    request=pending();assert set(request['defenders_by_region'])=={rc.SEQUANI}
    second=deepcopy(ses.data['pending'])
    ses.import_inbox({'decision_id':second['id'],'response':{'region':rc.ATREBATES,'defender':rc.ROMANS}})
    pending();assert ses.error and ses.data['pending']==second
    ses.import_inbox({'decision_id':second['id'],'response':{'region':rc.SEQUANI,'defender':rc.ROMANS}})
    result=step()[0]
    assert len(result['ambushes'])==2
    assert count_pieces(state,rc.PROVINCIA,rc.GERMANS,rc.WARBAND)==2
    assert count_pieces(state,rc.SEQUANI,rc.ROMANS,rc.AUXILIA)==2
    assert count_pieces(state,rc.ATREBATES,rc.ROMANS,rc.AUXILIA)==2
    assert validate_state(state)==[]


def test_fuzzer_uses_legal_repeatable_original_groups_and_targets():
    import random
    from fs_bot.cards.german_guidance import march_request,battle_request,validate_response
    from fs_bot.tools.player_fuzz import make_random_reactive
    state=board()
    place_piece(state,rc.PROVINCIA,rc.GERMANS,rc.WARBAND,4)
    place_piece(state,rc.SEQUANI,rc.GERMANS,rc.WARBAND,2)
    place_piece(state,rc.MANDUBII,rc.GERMANS,rc.WARBAND,2)
    place_piece(state,rc.MANDUBII,rc.ROMANS,rc.FORT)
    before=snapshot(state)
    for request in (march_request(state,2),battle_request(state,{rc.MANDUBII})):
        for seed in range(20):
            one=make_random_reactive([rc.BELGAE],random.Random(seed))(state,rc.BELGAE,request)
            two=make_random_reactive([rc.BELGAE],random.Random(seed))(state,rc.BELGAE,request)
            assert one==two
            assert validate_response(state,request,one) is None
    assert snapshot(state)==before


def test_hidden_superiority_is_still_required_for_ordinary_german_ambush():
    state=board()
    place_piece(state,rc.MANDUBII,rc.GERMANS,rc.WARBAND,2)
    place_piece(state,rc.MANDUBII,rc.ROMANS,rc.AUXILIA,2)
    seen=install(state,[])
    result=ex._resolve_card65_german_march_ambush(state,2)[0]
    assert not result['ambushes']
    assert not any(r.get('request_type')=='german_guided_ambush' for _,r in seen)
    assert count_pieces_by_state(state,rc.MANDUBII,rc.GERMANS,rc.WARBAND,rc.HIDDEN)==2


def test_fort_halves_losses_on_card65_unlike_card58():
    state=board()
    place_piece(state,rc.MANDUBII,rc.GERMANS,rc.WARBAND,4)
    place_piece(state,rc.MANDUBII,rc.ROMANS,rc.AUXILIA,3,piece_state=rc.REVEALED)
    place_piece(state,rc.MANDUBII,rc.ROMANS,rc.FORT)
    install(state,[],[{'region':rc.MANDUBII,'defender':rc.ROMANS}])
    ex._resolve_card65_german_march_ambush(state,2)
    assert count_pieces(state,rc.MANDUBII,rc.ROMANS,rc.AUXILIA)==2
    assert count_pieces(state,rc.MANDUBII,rc.ROMANS,rc.FORT)==1


def test_defensive_cooperation_cannot_downgrade_germans_to_normal_battle():
    from fs_bot.cards.card_effects import execute_event
    state=board()
    execute_event(state,38)
    place_piece(state,rc.MANDUBII,rc.GERMANS,rc.WARBAND,2)
    place_piece(state,rc.MANDUBII,rc.ROMANS,rc.AUXILIA,1)
    place_piece(state,rc.MANDUBII,rc.AEDUI,rc.WARBAND,3)
    agreements=[]
    def agent(current,actor,request):
        if request.get('request_type')=='german_guided_march':
            return {'marches':[]}
        if request.get('request_type')=='german_guided_ambush':
            return {'region':rc.MANDUBII,'defender':rc.ROMANS}
        if request['kind']=='agreement':
            agreements.append((actor,request['request_type']))
            return True
    state['decision_agent']=agent
    result=ex._resolve_card65_german_march_ambush(state,2)[0]
    assert not result['ambushes']
    assert agreements
    assert count_pieces(state,rc.MANDUBII,rc.GERMANS,rc.WARBAND)==2
    assert count_pieces_by_state(state,rc.MANDUBII,rc.GERMANS,rc.WARBAND,rc.HIDDEN)==2
    assert count_pieces(state,rc.MANDUBII,rc.ROMANS,rc.AUXILIA)==1
    assert count_pieces(state,rc.MANDUBII,rc.AEDUI,rc.WARBAND)==3
    assert validate_state(state)==[]
