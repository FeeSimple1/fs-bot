"""Card17 unshaded: Roman-owned original groups, then exactly one Ambush."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece,count_pieces,count_pieces_by_state
from fs_bot.engine import execute as ex
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state,validate_state


def board(executor=rc.BELGAE):
    state=build_initial_state(rc.SCENARIO_GREAT_REVOLT,seed=17)
    state.update(current_card=17,next_card=35,non_player_factions=set(),executing_faction=executor,event_params={})
    return state


def snapshot(state):
    return encode({k:v for k,v in state.items() if k!='decision_agent'})


def group(origin,destination,n):
    return {'origin':origin,'destination':destination,'warbands':n}


def position(executor=rc.BELGAE):
    state=board(executor)
    for region in (rc.PROVINCIA,rc.SEQUANI,rc.CARNUTES):
        place_piece(state,region,rc.GERMANS,rc.WARBAND,2,piece_state=rc.REVEALED)
    place_piece(state,rc.ATREBATES,rc.GERMANS,rc.WARBAND,6)
    place_piece(state,rc.ATREBATES,rc.ROMANS,rc.AUXILIA,3,piece_state=rc.REVEALED)
    place_piece(state,rc.MANDUBII,rc.AEDUI,rc.WARBAND,3,piece_state=rc.REVEALED)
    return state


def marches():
    return [group(rc.PROVINCIA,rc.SEQUANI,1),group(rc.SEQUANI,rc.MANDUBII,1),
            group(rc.CARNUTES,rc.MANDUBII,1)]


def install(state,plan,battle=None):
    seen=[]
    def agent(current,actor,request):
        seen.append((actor,deepcopy(request)))
        if request.get('request_type')=='german_guided_march':
            return plan
        if request.get('request_type')=='german_guided_ambush':
            return battle
    state['decision_agent']=agent
    return seen


@pytest.mark.parametrize('executor',[rc.ROMANS,rc.ARVERNI,rc.AEDUI,rc.BELGAE])
def test_other_executor_still_gives_romans_three_groups_and_single_chosen_ambush(executor):
    state=position(executor)
    seen=install(state,{'marches':marches()},{'region':rc.MANDUBII,'defender':rc.AEDUI})
    result=ex._resolve_card17_march_ambush(state,3)[0]
    guided=[(actor,r) for actor,r in seen if r.get('request_type') in ('german_guided_march','german_guided_ambush')]
    assert len(guided)==2 and all(actor==rc.ROMANS and r['card_id']==17 for actor,r in guided)
    assert guided[0][1]['max_origins']==3 and guided[0][1]['moving_groups_only']
    assert result['region']==rc.MANDUBII and result['defender']==rc.AEDUI
    assert len(result['ambushes'])==1
    assert count_pieces(state,rc.MANDUBII,rc.AEDUI,rc.WARBAND)==2
    assert count_pieces(state,rc.ATREBATES,rc.ROMANS,rc.AUXILIA)==3
    assert count_pieces_by_state(state,rc.ATREBATES,rc.GERMANS,rc.WARBAND,rc.HIDDEN)==6
    assert count_pieces(state,rc.SEQUANI,rc.GERMANS,rc.WARBAND)==2
    assert validate_state(state)==[]


@pytest.mark.parametrize('bad',[
    {'decline':True}, {'marches':marches()+[group(rc.ATREBATES,rc.NERVII,1)]},
    {'marches':[group(rc.PROVINCIA,rc.SEQUANI,1)]*2},
    {'marches':[group(rc.PROVINCIA,rc.SEQUANI,True)]},
    {'marches':[group(rc.PROVINCIA,rc.SEQUANI,-1)]},
    {'marches':[group(rc.PROVINCIA,rc.SEQUANI,3)]},
    {'marches':[group(rc.PROVINCIA,rc.MANDUBII,1)]},
    {'marches':[group(rc.PROVINCIA,None,0)]},
    {'marches':[dict(group(rc.PROVINCIA,rc.SEQUANI,1),leader=True)]},
])
def test_invalid_first_choices_cannot_change_board_or_rng(bad):
    state=position();install(state,bad)
    before=snapshot(state)
    with pytest.raises(ValueError):
        ex._resolve_card17_march_ambush(state,3)
    assert snapshot(state)==before


@pytest.mark.parametrize('battle',[{'decline':True},{'region':rc.SEQUANI,'defender':rc.AEDUI},
                                    {'region':rc.MANDUBII,'defender':rc.GERMANS}])
def test_single_required_ambush_cannot_be_declined_or_redirected(battle):
    state=position();install(state,{'marches':marches()},battle)
    before=snapshot(state)
    with pytest.raises(ValueError):
        ex._resolve_card17_march_ambush(state,3)
    assert snapshot(state)==before


def test_native_roman_bot_keeps_control_even_when_other_executor_is_human():
    state=board()
    state['non_player_factions']={rc.ROMANS}
    place_piece(state,rc.NERVII,rc.GERMANS,rc.WARBAND,4)
    place_piece(state,rc.NERVII,rc.ROMANS,rc.AUXILIA,1)
    place_piece(state,rc.ATREBATES,rc.AEDUI,rc.WARBAND,2,piece_state=rc.REVEALED)
    seen=install(state,{'decline':True},{'decline':True})
    result=ex._resolve_card17_march_ambush(state,3)[0]
    assert not any(r.get('request_type') in ('german_guided_march','german_guided_ambush') for _,r in seen)
    assert result['region']==rc.ATREBATES
    assert count_pieces(state,rc.NERVII,rc.ROMANS,rc.AUXILIA)==1


def test_explicit_whole_grant_default_uses_roman_instructions_not_germans_phase():
    state=board()
    place_piece(state,rc.NERVII,rc.GERMANS,rc.WARBAND,4)
    place_piece(state,rc.NERVII,rc.ROMANS,rc.AUXILIA,1)
    place_piece(state,rc.ATREBATES,rc.AEDUI,rc.WARBAND,2,piece_state=rc.REVEALED)
    seen=install(state,{'use_default':True})
    result=ex._resolve_card17_march_ambush(state,3)[0]
    assert any(actor==rc.ROMANS and r.get('request_type')=='german_guided_march' for actor,r in seen)
    assert result['region']==rc.ATREBATES
    assert count_pieces(state,rc.NERVII,rc.ROMANS,rc.AUXILIA)==1
    assert count_pieces(state,rc.ATREBATES,rc.AEDUI,rc.WARBAND)==0


def test_zero_loss_ambush_is_a_legal_single_choice():
    state=board()
    place_piece(state,rc.MANDUBII,rc.GERMANS,rc.WARBAND,1)
    place_piece(state,rc.MANDUBII,rc.AEDUI,rc.WARBAND,1,piece_state=rc.REVEALED)
    install(state,{'marches':[]},{'region':rc.MANDUBII,'defender':rc.AEDUI})
    result=ex._resolve_card17_march_ambush(state,3)[0]
    assert count_pieces_by_state(state,rc.MANDUBII,rc.GERMANS,rc.WARBAND,rc.REVEALED)==1
    assert result['region']==rc.MANDUBII
    assert count_pieces(state,rc.MANDUBII,rc.AEDUI,rc.WARBAND)==1


def test_no_able_ambush_ends_after_authored_march():
    state=board();place_piece(state,rc.PROVINCIA,rc.GERMANS,rc.WARBAND,2,piece_state=rc.REVEALED)
    seen=install(state,{'marches':[group(rc.PROVINCIA,rc.SEQUANI,1)]})
    result=ex._resolve_card17_march_ambush(state,3)[0]
    assert count_pieces(state,rc.SEQUANI,rc.GERMANS,rc.WARBAND)==1
    assert not result['ambushes']
    assert not any(r.get('request_type')=='german_guided_ambush' for _,r in seen)


def test_full_event_asks_roman_beneficiary_even_with_another_npc_executor():
    state=position();state['non_player_factions']={rc.BELGAE}
    seen=install(state,{'marches':marches()},{'region':rc.MANDUBII,'defender':rc.AEDUI})
    result=ex._execute_event(state,rc.BELGAE,{'command':'Event','sa':'No SA','sa_regions':[],
        'details':{'card_id':17,'text_preference':rc.EVENT_UNSHADED,'event_params':{}}})
    assert result['executed']
    assert any(actor==rc.ROMANS and r.get('request_type')=='german_guided_march' for actor,r in seen)
    assert count_pieces(state,rc.MANDUBII,rc.AEDUI,rc.WARBAND)==2


def test_terminal_roman_groups_hide_only_options_are_not_offered():
    from fs_bot.cards.german_guidance import march_request,battle_request
    from fs_bot.cli.free_actions import collect_free_action
    state=position();before=snapshot(state);out=StringIO()
    response=collect_free_action(state,rc.ROMANS,march_request(state,3,17),StringIO(
        'board\nChoose exact action\nProvincia\n1 Warbands\nSequani\nFinish March selection\n'),out)
    assert response=={'marches':[group(rc.PROVINCIA,rc.SEQUANI,1)]}
    assert 'hide only' not in out.getvalue()
    assert 'Germanic Chieftains' in out.getvalue() and 'AVAILABLE PIECES' in out.getvalue()
    battle=collect_free_action(state,rc.ROMANS,battle_request(state,{rc.ATREBATES},card_id=17),StringIO(
        'b\nChoose exact action\nAtrebates\nRomans\n'),out)
    assert battle=={'region':rc.ATREBATES,'defender':rc.ROMANS}
    assert snapshot(state)==before


def test_original_visibility_cohorts_are_roman_owned_and_arrivals_do_not_flip_again():
    state=position();place_piece(state,rc.PROVINCIA,rc.GERMANS,rc.WARBAND,1,piece_state=rc.SCOUTED)
    selected=marches();selected[0]['warbands']=2
    formation=[]
    def agent(current,actor,request):
        if request.get('request_type')=='german_guided_march':
            return {'marches':selected}
        if request.get('request_type')=='german_guided_ambush':
            return {'region':rc.MANDUBII,'defender':rc.AEDUI}
        if request['kind']=='march_cohort':
            formation.append((actor,deepcopy(request)))
            return {'counts':{rc.SCOUTED:1,rc.REVEALED:1}}
    state['decision_agent']=agent
    ex._resolve_card17_march_ambush(state,3)
    assert len(formation)==1 and formation[0][0]==rc.ROMANS
    assert formation[0][1]['acting_faction']==rc.GERMANS
    assert count_pieces_by_state(state,rc.SEQUANI,rc.GERMANS,rc.WARBAND,rc.REVEALED)==1
    assert count_pieces_by_state(state,rc.SEQUANI,rc.GERMANS,rc.WARBAND,rc.HIDDEN)==2
    assert count_pieces_by_state(state,rc.PROVINCIA,rc.GERMANS,rc.WARBAND,rc.HIDDEN)==1
    assert validate_state(state)==[]


def test_durable_roman_choice_survives_other_executor_save_and_invalid_ambush(tmp_path):
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.state.serialize import decode,save_game,load_game
    from fs_bot.tools.seat_session import SeatSession,DecisionPending,board_copy
    state=position();state['non_player_factions']={rc.ARVERNI,rc.AEDUI,rc.BELGAE}
    ses=SeatSession(state,{'seat':rc.ROMANS},[],HumanTurnDisplay(StringIO()))
    state['decision_agent']=ses.reactive;before=encode(board_copy(state))
    def step():
        def driver(*args):
            pass
        driver.transaction_checkpoint=ses.checkpoint;driver.transaction_restore=ses.restore
        with _action_transaction(state,driver):
            return ex._execute_event(state,rc.BELGAE,{'command':'Event','sa':'No SA','sa_regions':[],
                'details':{'card_id':17,'text_preference':rc.EVENT_UNSHADED,'event_params':{}}})
    def pending():
        with pytest.raises(DecisionPending):
            step()
        assert encode(board_copy(state))==before
        return decode(ses.data['pending']['request'])
    request=pending();assert request['request_type']=='german_guided_march' and request['card_id']==17
    first=deepcopy(ses.data['pending'])
    ses.import_inbox({'decision_id':first['id'],'response':None})
    pending();assert ses.error and ses.data['pending']==first
    ses.import_inbox({'decision_id':first['id'],'response':{'marches':marches()}})
    request=pending();assert request['request_type']=='german_guided_ambush' and request['max_regions']==1
    preview=decode(ses.data['pending']['board'])
    assert count_pieces(preview,rc.MANDUBII,rc.GERMANS,rc.WARBAND)==2
    save_game(state,tmp_path/'save.json',meta=ses.meta,log=ses.log)
    state,meta,log=load_game(tmp_path/'save.json',validate=True)
    ses=SeatSession(state,meta,log,HumanTurnDisplay(StringIO()));state['decision_agent']=ses.reactive
    second=deepcopy(ses.data['pending'])
    ses.import_inbox({'decision_id':second['id'],'response':{'decline':True}})
    pending();assert ses.error and ses.data['pending']==second
    ses.import_inbox({'decision_id':second['id'],'response':{'region':rc.MANDUBII,'defender':rc.AEDUI}})
    result=step()
    assert result['executed']
    assert len(result['free_actions'][0]['ambushes'])==1
    assert count_pieces(state,rc.MANDUBII,rc.AEDUI,rc.WARBAND)==2
    assert count_pieces(state,rc.ATREBATES,rc.ROMANS,rc.AUXILIA)==3
    assert validate_state(state)==[]


def test_defensive_cooperation_does_not_turn_single_german_ambush_into_normal_battle():
    from fs_bot.cards.card_effects import execute_event
    state=board();execute_event(state,38)
    place_piece(state,rc.MANDUBII,rc.GERMANS,rc.WARBAND,2)
    place_piece(state,rc.MANDUBII,rc.ROMANS,rc.AUXILIA,1)
    place_piece(state,rc.MANDUBII,rc.AEDUI,rc.WARBAND,3)
    def agent(current,actor,request):
        if request.get('request_type')=='german_guided_march':
            return {'marches':[]}
        if request.get('request_type')=='german_guided_ambush':
            return {'region':rc.MANDUBII,'defender':rc.ROMANS}
        if request['kind']=='agreement':
            return True
    state['decision_agent']=agent
    result=ex._resolve_card17_march_ambush(state,3)[0]
    assert not result['ambushes']
    assert count_pieces_by_state(state,rc.MANDUBII,rc.GERMANS,rc.WARBAND,rc.HIDDEN)==2
    assert count_pieces(state,rc.MANDUBII,rc.ROMANS,rc.AUXILIA)==1
    assert validate_state(state)==[]


def test_fuzzer_authors_positive_groups_within_three_group_budget_and_does_not_mutate_rng():
    import random
    from fs_bot.cards.german_guidance import march_request,battle_request,validate_response
    from fs_bot.tools.player_fuzz import make_random_reactive
    state=position();before=snapshot(state)
    for request in (march_request(state,3,17),battle_request(state,{rc.ATREBATES},card_id=17)):
        for seed in range(20):
            one=make_random_reactive([rc.ROMANS],random.Random(seed))(state,rc.ROMANS,request)
            two=make_random_reactive([rc.ROMANS],random.Random(seed))(state,rc.ROMANS,request)
            assert one==two and validate_response(state,request,one) is None
            if 'marches' in one:
                assert len(one['marches'])<=3 and all(e['warbands']>0 for e in one['marches'])
    assert snapshot(state)==before


def test_initial_event_menu_leaves_german_group_choices_to_roman_live_request():
    from fs_bot.cli.human_plan import _collect_event_params
    state=position();before=snapshot(state)
    assert _collect_event_params(state,rc.BELGAE,17,False,StringIO(),StringIO())=={}
    assert snapshot(state)==before
