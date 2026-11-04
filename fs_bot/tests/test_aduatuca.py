"""Card58 shaded: executor choices, §3.4.2 movement and printed Fort exception."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, count_pieces_by_state
from fs_bot.engine import execute as ex
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state


def board():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=58)
    state.update(current_card=58, next_card=35, non_player_factions=set(), event_params={})
    for destination in (rc.MANDUBII, rc.ATREBATES):
        place_piece(state, destination, rc.ROMANS, rc.FORT)
        place_piece(state, destination, rc.ROMANS, rc.AUXILIA, 3)
    place_piece(state, rc.SEQUANI, rc.GERMANS, rc.WARBAND, 5, piece_state=rc.REVEALED)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 6)
    return state


def plan(n=2):
    return {'destination': rc.MANDUBII, 'marches': [{'origin': rc.SEQUANI, 'warbands': n}]}


def install(state, response):
    seen = []
    def agent(current, actor, request):
        seen.append((actor, deepcopy(request)))
        if request.get('request_type') == 'aduatuca_march':
            return response
    state['decision_agent'] = agent
    return seen


@pytest.mark.parametrize('executor', [rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE])
def test_executor_selects_smaller_group_and_less_populated_fort(executor):
    state = board()
    seen = install(state, plan())
    state['executing_faction'] = executor
    result = ex._resolve_card58_german_ambush(state)[0]
    assert any(actor == executor and r.get('request_type') == 'aduatuca_march' for actor,r in seen)
    assert result['region'] == rc.MANDUBII and result['warbands_marched'] == 2
    assert count_pieces(state, rc.SEQUANI, rc.GERMANS, rc.WARBAND) == 3
    assert count_pieces_by_state(state, rc.SEQUANI, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 3
    assert count_pieces(state, rc.NERVII, rc.GERMANS, rc.WARBAND) == 6
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 3
    assert validate_state(state) == []


@pytest.mark.parametrize('bad', [
    {'decline': True}, {'use_default': 1},
    {'destination': rc.SEQUANI, 'marches': []},
    {'destination': rc.MANDUBII, 'marches': [{'origin':rc.NERVII,'warbands':1}]},
    {'destination': rc.MANDUBII, 'marches': [{'origin':rc.SEQUANI,'warbands':6}]},
    {'destination': rc.MANDUBII, 'marches': [{'origin':rc.SEQUANI,'warbands':True}]},
    {'destination': rc.MANDUBII, 'marches': [{'origin':rc.SEQUANI,'warbands':-1}]},
    {'destination': rc.MANDUBII, 'marches': [{'origin':rc.SEQUANI,'warbands':1}]*2},
    {'destination': rc.MANDUBII, 'marches': [{'origin':rc.SEQUANI,'warbands':1,'leader':True}]},
])
def test_invalid_march_cannot_change_board_or_rng(bad):
    state = board()
    install(state,bad)
    state['executing_faction'] = rc.BELGAE
    before = encode({k:v for k,v in state.items() if k!='decision_agent'})
    with pytest.raises(ValueError):
        ex._resolve_card58_german_ambush(state)
    assert encode({k:v for k,v in state.items() if k!='decision_agent'}) == before


def test_empty_march_uses_resident_germans_and_ignores_hidden_superiority():
    state = board()
    place_piece(state, rc.MANDUBII, rc.GERMANS, rc.WARBAND, 4, piece_state=rc.REVEALED)
    install(state, {'destination':rc.MANDUBII,'marches':[]})
    result = ex._resolve_card58_german_ambush(state, rc.BELGAE)[0]
    assert result['warbands_marched'] == 0
    assert count_pieces(state, rc.MANDUBII, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces_by_state(state, rc.SEQUANI, rc.GERMANS, rc.WARBAND,rc.REVEALED)==5
    assert validate_state(state) == []


def test_zero_movement_selected_origin_flips_scouted_only_once():
    state = board()
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND, 2, piece_state=rc.SCOUTED)
    install(state, {'destination':rc.MANDUBII,'marches':[{'origin':rc.CARNUTES,'warbands':0}]})
    ex._resolve_card58_german_ambush(state, rc.BELGAE)
    assert count_pieces_by_state(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND,rc.REVEALED)==2
    assert count_pieces_by_state(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND,rc.HIDDEN)==0
    assert count_pieces(state, rc.MANDUBII, rc.GERMANS, rc.WARBAND)==0


def test_terminal_selects_quantities_without_changing_state():
    from fs_bot.cards.aduatuca import make_request
    from fs_bot.cli.free_actions import collect_free_action
    state = board(); before = encode(state); out = StringIO()
    response = collect_free_action(state,rc.BELGAE,make_request(state),StringIO(
        'board\nChoose destination and groups\nb\nMandubii\nSequani\n2 Warbands\n'),out)
    assert response == plan()
    assert out.getvalue().count('AVAILABLE PIECES')==2
    assert encode(state)==before


def test_durable_pending_and_save_at_defender_choice_replay_the_march(tmp_path):
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.state.serialize import decode, save_game, load_game
    from fs_bot.tools.seat_session import SeatSession, DecisionPending, board_copy
    state = board()
    state['executing_faction'] = rc.ROMANS
    ses = SeatSession(state, {'seat':rc.ROMANS}, [], HumanTurnDisplay(StringIO()))
    state['decision_agent'] = ses.reactive
    initial = encode(board_copy(state))
    def step():
        def driver(*args):
            pass
        driver.transaction_checkpoint = ses.checkpoint
        driver.transaction_restore = ses.restore
        with _action_transaction(state,driver):
            return ex._resolve_card58_german_ambush(state)
    with pytest.raises(DecisionPending):
        step()
    first = deepcopy(ses.data['pending'])
    assert decode(first['request'])['request_type']=='aduatuca_march'
    ses.import_inbox({'decision_id':first['id'],'response':{'decline':True}})
    with pytest.raises(DecisionPending):
        step()
    assert ses.error and ses.data['pending']==first
    assert encode(board_copy(state))==initial
    ses.import_inbox({'decision_id':first['id'],'response':plan()})
    with pytest.raises(DecisionPending):
        step()
    request=decode(ses.data['pending']['request'])
    assert request['kind']=='loss_order' and request['faction']==rc.ROMANS
    preview=decode(ses.data['pending']['board'])
    assert count_pieces(preview,rc.SEQUANI,rc.GERMANS,rc.WARBAND)==3
    assert encode(board_copy(state))==initial
    save_game(state,tmp_path/'save.json',meta=ses.meta,log=ses.log)
    state,meta,log=load_game(tmp_path/'save.json',validate=True)
    ses=SeatSession(state,meta,log,HumanTurnDisplay(StringIO()))
    state['decision_agent']=ses.reactive
    ses.import_inbox({'decision_id':ses.data['pending']['id'],'response':[request['pieces'][0]]})
    result=step()[0]
    assert result['region']==rc.MANDUBII and result['warbands_marched']==2
    assert count_pieces(state,rc.MANDUBII,rc.ROMANS,rc.AUXILIA)==2
    assert validate_state(state)==[]


def test_event_routes_the_choice_to_its_actual_executor():
    state=board()
    seen=install(state,plan())
    result=ex._execute_event(state,rc.BELGAE,{'command':'Event','sa':'No SA','sa_regions':[],
        'details':{'card_id':58,'text_preference':rc.EVENT_SHADED,'event_params':{}}},human=True)
    assert result['executed']
    choice=next((actor,r) for actor,r in seen if r.get('request_type')=='aduatuca_march')
    assert choice[0]==rc.BELGAE and choice[1]['acting_faction']==rc.GERMANS
    assert count_pieces(state,rc.SEQUANI,rc.GERMANS,rc.WARBAND)==3


def test_multiple_original_regions_gather_once_and_residents_join_ambush():
    state=board()
    place_piece(state,rc.CARNUTES,rc.GERMANS,rc.WARBAND,2)
    place_piece(state,rc.MANDUBII,rc.GERMANS,rc.WARBAND,2,piece_state=rc.REVEALED)
    install(state,{'destination':rc.MANDUBII,'marches':[
        {'origin':rc.SEQUANI,'warbands':2},{'origin':rc.CARNUTES,'warbands':2}]})
    result=ex._resolve_card58_german_ambush(state,rc.BELGAE)[0]
    assert result['warbands_marched']==4 and result['warbands_gathered']==6
    assert count_pieces(state,rc.MANDUBII,rc.ROMANS,rc.AUXILIA)==0
    assert count_pieces(state,rc.MANDUBII,rc.ROMANS,rc.FORT)==1
    assert count_pieces(state,rc.SEQUANI,rc.GERMANS,rc.WARBAND)==3
    assert count_pieces(state,rc.CARNUTES,rc.GERMANS,rc.WARBAND)==0
    assert validate_state(state)==[]


def test_mixed_visibility_formation_belongs_to_executor_not_germans():
    state=board()
    place_piece(state,rc.SEQUANI,rc.GERMANS,rc.WARBAND,1,piece_state=rc.SCOUTED)
    seen=[]
    def agent(current,actor,request):
        if request.get('request_type')=='aduatuca_march':
            return plan()
        if request['kind']=='march_cohort':
            seen.append((actor,deepcopy(request)))
            return {'counts':{rc.HIDDEN:1,rc.REVEALED:1}}
    state['decision_agent']=agent
    ex._resolve_card58_german_ambush(state,rc.BELGAE)
    assert len(seen)==1 and seen[0][0]==rc.BELGAE
    assert seen[0][1]['acting_faction']==rc.GERMANS
    assert count_pieces_by_state(state,rc.SEQUANI,rc.GERMANS,rc.WARBAND,rc.HIDDEN)==4
    assert count_pieces_by_state(state,rc.SEQUANI,rc.GERMANS,rc.WARBAND,rc.REVEALED)==0
    assert validate_state(state)==[]


def test_fuzzed_choices_are_legal_repeatable_and_do_not_consume_game_rng():
    import random
    from fs_bot.cards.aduatuca import make_request,validate_response
    from fs_bot.tools.player_fuzz import make_random_reactive
    state=board(); request=make_request(state); before=encode(state)
    for seed in range(20):
        first=make_random_reactive([rc.BELGAE],random.Random(seed))(state,rc.BELGAE,request)
        second=make_random_reactive([rc.BELGAE],random.Random(seed))(state,rc.BELGAE,request)
        assert first==second
        assert validate_response(state,request,first) is None
    assert encode(state)==before


def test_shaded_event_does_not_prompt_for_unshaded_removal_parameters():
    from fs_bot.cli.human_plan import _collect_event_params
    state=board();before=encode(state)
    assert _collect_event_params(state,rc.BELGAE,58,True,StringIO(),StringIO())=={}
    assert encode(state)==before
