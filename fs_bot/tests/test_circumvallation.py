"""Card4's Roman-owned optional benefit and marker placement sequence."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece,count_pieces,count_pieces_by_state
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.commands.rally import rally_in_region
from fs_bot.engine import execute as ex
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state,validate_state


def board(executor=rc.BELGAE):
    state=build_initial_state(rc.SCENARIO_GREAT_REVOLT,seed=4)
    state.update(current_card=4,next_card=35,executing_faction=executor,non_player_factions=set(),event_params={})
    for region,tribe,n in ((rc.MANDUBII,rc.TRIBE_MANDUBII,4),(rc.CARNUTES,rc.TRIBE_CARNUTES,7)):
        assert _ally_tribe(state,tribe,rc.ARVERNI)
        rally_in_region(state,region,rc.ARVERNI,'place_citadel',tribe=tribe,free=True)
        place_piece(state,region,rc.ARVERNI,rc.WARBAND,n,piece_state=rc.REVEALED)
    place_piece(state,rc.SEQUANI,rc.ROMANS,rc.AUXILIA,3,piece_state=rc.REVEALED)
    place_piece(state,rc.CARNUTES,rc.ROMANS,rc.AUXILIA,6,piece_state=rc.REVEALED)
    place_piece(state,rc.MANDUBII,rc.ROMANS,rc.AUXILIA,1)
    state['resources'][rc.ROMANS]=0
    return state


def snapshot(state):
    return encode({k:v for k,v in state.items() if k!='decision_agent'})


def group(origin=rc.SEQUANI,n=1,legions=0,leader=False):
    return {'origin':origin,'legions':legions,'auxilia':n,'leader':leader}


def plan(*groups,destination=rc.MANDUBII):
    return {'destination':destination,'marches':list(groups)}


def event(state,executor=rc.BELGAE,side=rc.EVENT_UNSHADED,params=None):
    return ex._execute_event(state,executor,{'command':'Event','sa':'No SA','sa_regions':[],
        'details':{'card_id':4,'text_preference':side,'event_params':{} if params is None else params}},human=True)


def install(state,response):
    seen=[]
    def agent(current,actor,request):
        if request.get('request_type')=='circumvallation_march':
            seen.append((actor,deepcopy(request)))
            assert not any(rc.MARKER_CIRCUMVALLATION in marker for marker in current['markers'].values())
            return response
    state['decision_agent']=agent
    return seen


@pytest.mark.parametrize('executor',[rc.ROMANS,rc.ARVERNI,rc.AEDUI,rc.BELGAE])
def test_other_executor_still_gets_roman_destination_and_exact_groups(executor):
    state=board(executor);seen=install(state,plan(group(n=2),group(rc.CARNUTES)))
    result=event(state,executor)
    assert result['executed']
    assert seen and all(actor==rc.ROMANS for actor,_ in seen)
    assert count_pieces(state,rc.SEQUANI,rc.ROMANS,rc.AUXILIA)==1
    assert count_pieces_by_state(state,rc.SEQUANI,rc.ROMANS,rc.AUXILIA,rc.HIDDEN)==1
    assert count_pieces(state,rc.CARNUTES,rc.ROMANS,rc.AUXILIA)==5
    assert count_pieces(state,rc.MANDUBII,rc.ROMANS,rc.AUXILIA)==4
    assert rc.MARKER_CIRCUMVALLATION in state['markers'][rc.MANDUBII]
    assert rc.MARKER_CIRCUMVALLATION not in state['markers'].get(rc.CARNUTES,{})
    assert state['resources'][rc.ROMANS]==0
    assert validate_state(state)==[]


@pytest.mark.parametrize('side',[rc.EVENT_UNSHADED,rc.EVENT_SHADED])
def test_decline_precedes_marker_and_movement_on_both_legacy_text_sides(side):
    state=board();install(state,{'decline':True});before=snapshot(state)
    result=event(state,side=side,params={'target_region':rc.MANDUBII})
    assert result['executed']
    assert not any(rc.MARKER_CIRCUMVALLATION in markers for markers in state['markers'].values())
    assert count_pieces(state,rc.SEQUANI,rc.ROMANS,rc.AUXILIA)==3
    assert count_pieces_by_state(state,rc.SEQUANI,rc.ROMANS,rc.AUXILIA,rc.REVEALED)==3
    assert state['resources'][rc.ROMANS]==0
    assert result['free_actions'][0]['declined_no_effect']


@pytest.mark.parametrize('bad',[
    {'decline':1},{'use_default':1},
    plan(group(),destination=rc.SEQUANI),
    plan(group(rc.PROVINCIA)),
    plan(group(n=4)),plan(group(n=True)),plan(group(n=-1)),plan(group(n=0)),
    plan(group(n=2),group(n=2)),
    plan(dict(group(),leader=True)),
    {'destination':rc.MANDUBII,'marches':[dict(group(),route=[rc.CARNUTES,rc.MANDUBII])]},
])
def test_invalid_roman_plan_does_not_apply_marker_or_movement(bad):
    state=board();install(state,bad);before=snapshot(state)
    with pytest.raises(ValueError):
        ex._resolve_card4_circumvallation(state,None)
    assert snapshot(state)==before


def test_split_original_groups_and_more_than_four_legions_are_legal():
    state=board();place_piece(state,rc.SEQUANI,rc.ROMANS,rc.LEGION,6,from_legions_track=True)
    install(state,plan(group(n=1,legions=3),group(n=1,legions=2)))
    event(state)
    assert count_pieces(state,rc.MANDUBII,rc.ROMANS,rc.LEGION)==5
    assert count_pieces(state,rc.SEQUANI,rc.ROMANS,rc.LEGION)==1
    assert count_pieces(state,rc.MANDUBII,rc.ROMANS,rc.AUXILIA)==3
    assert validate_state(state)==[]


def test_empty_march_places_marker_with_resident_romans_only():
    state=board();install(state,plan())
    result=event(state)
    assert rc.MARKER_CIRCUMVALLATION in state['markers'][rc.MANDUBII]
    assert result['free_actions'][0]['marker_placed']
    assert count_pieces_by_state(state,rc.SEQUANI,rc.ROMANS,rc.AUXILIA,rc.REVEALED)==3
    assert count_pieces(state,rc.MANDUBII,rc.ROMANS,rc.AUXILIA)==1


def test_no_romans_at_destination_leaves_no_new_marker():
    from fs_bot.board.pieces import remove_piece
    state=board();remove_piece(state,rc.MANDUBII,rc.ROMANS,rc.AUXILIA)
    install(state,plan())
    result=event(state,params={'target_region':rc.MANDUBII})
    assert rc.MARKER_CIRCUMVALLATION not in state['markers'].get(rc.MANDUBII,{})
    assert not result['free_actions'][0]['marker_placed']


def test_successor_is_a_valid_ordinary_roman_leader():
    state=board();place_piece(state,rc.SEQUANI,rc.ROMANS,rc.LEADER,leader_name=rc.SUCCESSOR)
    install(state,plan(group(n=0,leader=True)))
    event(state)
    assert count_pieces(state,rc.SEQUANI,rc.ROMANS,rc.LEADER)==0
    assert count_pieces(state,rc.MANDUBII,rc.ROMANS,rc.LEADER)==1
    assert validate_state(state)==[]


def test_legacy_parameters_cannot_target_a_region_without_enemy_citadel():
    state=board();before=snapshot(state)
    result=event(state,params={'target_region':rc.SEQUANI})
    assert result['executed'] is False
    assert snapshot(state)==before


def test_terminal_roman_plan_and_decline_support_board_inspection():
    from fs_bot.cards.circumvallation import make_request
    from fs_bot.cli.free_actions import collect_free_action
    state=board();before=snapshot(state);out=StringIO()
    response=collect_free_action(state,rc.ROMANS,make_request(state),StringIO(
        'board\nChoose Citadel and exact March groups\nMandubii\nb\nSequani\n0 Legions\n2 Auxilia\nFinish March; place marker if possible\n'),out)
    assert response==plan(group(n=2))
    assert out.getvalue().count('AVAILABLE PIECES')==2
    assert collect_free_action(state,rc.ROMANS,make_request(state),StringIO('Decline the whole benefit\n'),StringIO())=={'decline':True}
    assert snapshot(state)==before


def test_native_roman_default_preserves_its_existing_largest_adjacent_group():
    state=board();state['non_player_factions']={rc.ROMANS}
    event(state,params={'target_region':rc.MANDUBII})
    assert count_pieces(state,rc.CARNUTES,rc.ROMANS,rc.AUXILIA)==0
    assert count_pieces(state,rc.MANDUBII,rc.ROMANS,rc.AUXILIA)==7
    assert rc.MARKER_CIRCUMVALLATION in state['markers'][rc.MANDUBII]
    assert validate_state(state)==[]


def test_refused_cooperation_reoffers_unmarked_roman_plan():
    from fs_bot.cards.card_effects import execute_event
    state=board();execute_event(state,38)
    place_piece(state,rc.SEQUANI,rc.AEDUI,rc.WARBAND,2)
    seen=[]
    def agent(current,actor,request):
        if request.get('request_type')=='circumvallation_march':
            seen.append(request)
            assert rc.MARKER_CIRCUMVALLATION not in current['markers'].get(rc.MANDUBII,{})
            return dict(plan(group()),diviciacus_regions=[rc.SEQUANI] if len(seen)==1 else [])
        if request['kind']=='agreement':
            return False
    state['decision_agent']=agent
    event(state)
    assert len(seen)==2 and seen[1]['attempt']==2
    assert count_pieces(state,rc.SEQUANI,rc.AEDUI,rc.WARBAND)==2
    assert rc.MARKER_CIRCUMVALLATION in state['markers'][rc.MANDUBII]
    assert validate_state(state)==[]


def test_cooperation_preserves_physical_owner_and_origin_visibility():
    from fs_bot.cards.card_effects import execute_event
    state=board();execute_event(state,38)
    place_piece(state,rc.SEQUANI,rc.AEDUI,rc.WARBAND,2,piece_state=rc.REVEALED)
    def agent(current,actor,request):
        if request.get('request_type')=='circumvallation_march':
            return dict(plan(group()),diviciacus_regions=[rc.SEQUANI])
        if request['kind']=='agreement':
            return True
        if request['kind']=='diviciacus_pieces':
            return {'counts':{rc.ROMANS:0,rc.AEDUI:1}}
    state['decision_agent']=agent
    event(state)
    assert count_pieces(state,rc.SEQUANI,rc.ROMANS,rc.AUXILIA)==3
    assert count_pieces(state,rc.MANDUBII,rc.ROMANS,rc.AUXILIA)==1
    assert count_pieces_by_state(state,rc.SEQUANI,rc.AEDUI,rc.WARBAND,rc.HIDDEN)==1
    assert count_pieces_by_state(state,rc.MANDUBII,rc.AEDUI,rc.WARBAND,rc.HIDDEN)==1
    assert validate_state(state)==[]


def test_durable_marker_stays_absent_until_saved_formation_choice_is_applied(tmp_path):
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.state.serialize import decode,save_game,load_game
    from fs_bot.tools.seat_session import SeatSession,DecisionPending,board_copy
    state=board();place_piece(state,rc.SEQUANI,rc.ROMANS,rc.AUXILIA,1,piece_state=rc.SCOUTED)
    state['non_player_factions']={rc.BELGAE,rc.ARVERNI,rc.AEDUI}
    ses=SeatSession(state,{'seat':rc.ROMANS},[],HumanTurnDisplay(StringIO()));state['decision_agent']=ses.reactive
    before=encode(board_copy(state))
    def step():
        def driver(*args):
            pass
        driver.transaction_checkpoint=ses.checkpoint;driver.transaction_restore=ses.restore
        with _action_transaction(state,driver):
            return event(state)
    def pending():
        with pytest.raises(DecisionPending):
            step()
        assert encode(board_copy(state))==before
        preview=decode(ses.data['pending']['board'])
        assert not any(rc.MARKER_CIRCUMVALLATION in m for m in preview['markers'].values())
        return decode(ses.data['pending']['request'])
    assert pending()['request_type']=='circumvallation_march'
    first=deepcopy(ses.data['pending'])
    ses.import_inbox({'decision_id':first['id'],'response':plan(group(n=99))})
    pending();assert ses.error and ses.data['pending']==first
    ses.import_inbox({'decision_id':first['id'],'response':plan(group())})
    request=pending();assert request['kind']=='march_cohort'
    save_game(state,tmp_path/'save.json',meta=ses.meta,log=ses.log)
    state,meta,log=load_game(tmp_path/'save.json',validate=True)
    ses=SeatSession(state,meta,log,HumanTurnDisplay(StringIO()));state['decision_agent']=ses.reactive
    ses.import_inbox({'decision_id':ses.data['pending']['id'],'response':{'counts':{rc.SCOUTED:1}}})
    assert step()['executed']
    assert rc.MARKER_CIRCUMVALLATION in state['markers'][rc.MANDUBII]
    assert count_pieces_by_state(state,rc.SEQUANI,rc.ROMANS,rc.AUXILIA,rc.HIDDEN)==3
    assert count_pieces_by_state(state,rc.MANDUBII,rc.ROMANS,rc.AUXILIA,rc.REVEALED)==1
    assert validate_state(state)==[]


def test_generated_roman_choices_are_repeatable_and_do_not_change_live_rng():
    import random
    from fs_bot.cards.circumvallation import make_request,validate_response
    from fs_bot.tools.player_fuzz import make_random_reactive
    state=board();request=make_request(state);before=snapshot(state)
    for seed in range(20):
        one=make_random_reactive([rc.ROMANS],random.Random(seed))(state,rc.ROMANS,request)
        two=make_random_reactive([rc.ROMANS],random.Random(seed))(state,rc.ROMANS,request)
        assert one==two and validate_response(state,request,one) is None
    assert snapshot(state)==before


def test_initial_event_menu_defers_to_roman_beneficiary():
    from fs_bot.cli.human_plan import _collect_event_params
    state=board();before=snapshot(state)
    assert _collect_event_params(state,rc.BELGAE,4,False,StringIO(),StringIO())=={}
    assert snapshot(state)==before
