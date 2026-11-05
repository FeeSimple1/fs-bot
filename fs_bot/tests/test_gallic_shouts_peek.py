"""Card 35 gives Romans the actual next two facedown cards privately."""
from copy import deepcopy
from io import StringIO
import json

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece
from fs_bot.cards.card_text import get_card_text
from fs_bot.engine.execute import _resolve_card35_roman,execute_decision
from fs_bot.state.state_schema import build_initial_state,validate_state
from fs_bot.state.serialize import encode,decode

SCENARIOS=list(rc.ALL_SCENARIOS)


def position(scenario=rc.SCENARIO_GREAT_REVOLT,edition='second-edition'):
    state=build_initial_state(scenario,seed=35)
    state['current_card']=state['current_card_id']=35
    state['deck']=[1,2,3,4];state['next_card']=1
    state['card_edition']=edition
    state['non_player_factions']=set(rc.FACTIONS)-{rc.ROMANS}
    state['resources'][rc.ROMANS]=10
    state['eligibility'][rc.ROMANS]=rc.INELIGIBLE
    place_piece(state,rc.SEQUANI,rc.ROMANS,rc.AUXILIA,2)
    assert validate_state(state)==[]
    return state


def action(shaded=False):
    return {'command':'Event','sa':'No SA','regions':[],
        'details':{'card_id':35,'text_preference':rc.EVENT_SHADED if shaded else rc.EVENT_UNSHADED}}


def seize(*regions):
    return {'command':rc.CMD_SEIZE,'regions':list(regions),'sa':'No SA',
            'details':{'disperse_tribes':{r:[] for r in regions}}}


def capture(state,response):
    seen=[]
    def agent(board,faction,request):
        if request['kind']!='free_action':return None
        seen.append((faction,deepcopy(request)))
        return response
    state['decision_agent']=agent
    return seen


@pytest.mark.parametrize('scenario',SCENARIOS)
@pytest.mark.parametrize('edition',['original','second-edition'])
@pytest.mark.parametrize('executor',[rc.ROMANS,rc.BELGAE])
def test_peek_precedes_choice_is_roman_owned_and_excludes_faceup_card(scenario,edition,executor):
    state=position(scenario,edition);deck=list(state['deck']);rng=state['rng'].getstate()
    seen=capture(state,{'decline':True})
    result=_resolve_card35_roman(state,executor)
    assert len(seen)==1 and seen[0][0]==rc.ROMANS
    request=seen[0][1]
    assert request['card_id']==35 and request['alternative']=='eligible'
    assert request['max_regions']==1 and not request['with_sa']
    assert [c['card_id'] for c in request['private_cards']]==[2,3]
    for card in request['private_cards']:
        assert card['title'] and card['text']==get_card_text(card['card_id'],scenario,edition)
    assert state['eligibility'][rc.ROMANS]==rc.ELIGIBLE
    assert result[0]['free_action']=='stay_eligible'
    assert state['deck']==deck and state['next_card']==1 and state['rng'].getstate()==rng
    assert 'private_cards' not in json.dumps(result)
    assert 'private_cards' not in json.dumps(state.get('event_modifiers',{}))


@pytest.mark.parametrize('deck,ids',[([],[]),([1],[]),([1,2],[2]),
    ([1,rc.WINTER_CARD,2,3],[rc.WINTER_CARD,2]),([rc.WINTER_CARD,2,3],[2,3])])
def test_short_decks_and_winter_peek_are_reported_without_drawing(deck,ids):
    state=position();state['deck']=list(deck);state['next_card']=deck[0] if deck else None
    seen=capture(state,{'decline':True});before_rng=state['rng'].getstate()
    _resolve_card35_roman(state,rc.BELGAE)
    cards=seen[0][1]['private_cards']
    assert [c['card_id'] for c in cards]==ids and state['deck']==deck
    assert state['rng'].getstate()==before_rng
    for card in cards:
        if card['card_id']==rc.WINTER_CARD:
            assert card['is_winter'] and card['faction_order']==[] and not card['text']


def test_free_limited_command_can_be_chosen_after_the_peek():
    state=position();seen=capture(state,seize(rc.SEQUANI));resources=state['resources'][rc.ROMANS]
    result=_resolve_card35_roman(state,rc.BELGAE)
    assert [c['card_id'] for c in seen[0][1]['private_cards']]==[2,3]
    assert result[0]['free_action']=='free_command' and result[0]['result']['executed']
    assert state['resources'][rc.ROMANS]>resources
    assert state['eligibility'][rc.ROMANS]==rc.INELIGIBLE
    assert validate_state(state)==[]


def test_cli_shows_cards_before_become_eligible_and_keeps_board_inspection():
    from fs_bot.cli.reactive import make_cli_reactive
    state=position();output=StringIO()
    state['decision_agent']=make_cli_reactive({rc.ROMANS},StringIO('board\nBecome Eligible\n'),output)
    result=_resolve_card35_roman(state,rc.BELGAE)
    shown=output.getvalue()
    assert 'private Gallic Shouts' in shown and 'Card 2:' in shown and 'Card 3:' in shown
    assert shown.index('Card 2:')<shown.index('Become Eligible')
    assert 'Faction order:' in shown and result[0]['free_action']=='stay_eligible'
    assert state['deck']==[1,2,3,4]


def test_other_human_executor_never_receives_roman_peek_in_its_console():
    from fs_bot.cli.reactive import make_cli_reactive
    from fs_bot.cli.display import format_board,snapshot_state
    state=position();output=StringIO()
    cli=make_cli_reactive({rc.BELGAE},StringIO(),output)
    state['decision_agent']=lambda st,fa,re:cli(st,fa,re) if re.get('card_id')==35 else None
    result=_resolve_card35_roman(state,rc.BELGAE)
    assert output.getvalue()==''
    public=json.dumps(result)+repr(snapshot_state(state))+format_board(state)
    assert 'private_cards' not in public and 'Card 2:' not in public and 'Card 3:' not in public


def test_event_executor_path_keeps_private_cards_out_of_public_receipts():
    from fs_bot.cli.display import snapshot_state
    state=position();seen=capture(state,{'decline':True})
    result=execute_decision(state,rc.BELGAE,{'player_action':action()})
    assert result['executed'] and len(seen)==1
    assert seen[0][0]==rc.ROMANS and [c['card_id'] for c in seen[0][1]['private_cards']]==[2,3]
    assert 'private_cards' not in json.dumps(result)
    assert 'private_cards' not in repr(snapshot_state(state))


def test_preview_consumes_neither_live_private_input_nor_rng():
    from fs_bot.engine.moves import validate_player_action
    state=position();before=encode(state)
    state['decision_agent']=lambda *a:pytest.fail('Preview consumed live private response')
    assert validate_player_action(state,rc.BELGAE,action())[0]
    assert encode({k:v for k,v in state.items() if k!='decision_agent'})==before


@pytest.mark.parametrize('bad',[None,{}, {'decline':1},seize(rc.SEQUANI,rc.PROVINCIA)])
def test_private_pending_invalid_choice_save_resume_and_replay(tmp_path,bad):
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.state.serialize import save_game,load_game
    from fs_bot.tools.seat_session import SeatSession,DecisionPending,board_copy
    state=position();session=SeatSession(state,{'seat':rc.ROMANS},[],HumanTurnDisplay(StringIO()))
    state['decision_agent']=session.reactive
    def attempt(current):
        def driver(*args):pass
        driver.transaction_checkpoint=current.checkpoint;driver.transaction_restore=current.restore
        with _action_transaction(current.state,driver):
            return execute_decision(current.state,rc.BELGAE,{'player_action':action()})
    before=encode(board_copy(state))
    with pytest.raises(DecisionPending):attempt(session)
    pending=deepcopy(session.data['pending']);request=decode(pending['request'])
    assert request['faction']==rc.ROMANS and request['card_id']==35
    assert [c['card_id'] for c in request['private_cards']]==[2,3]
    payload={'decision_id':pending['id'],'response':bad};session.import_inbox(payload)
    with pytest.raises(DecisionPending):attempt(session)
    assert session.data['pending']==pending and session.data['queue']==[payload]
    assert encode(board_copy(state))==before and not session.data['journal']
    path=tmp_path/'peek.json';save_game(state,path,meta=session.meta,log=session.log)
    restored,meta,log=load_game(path);resumed=SeatSession(restored,meta,log,HumanTurnDisplay(StringIO()))
    restored['decision_agent']=resumed.reactive
    with pytest.raises(DecisionPending):attempt(resumed)
    assert resumed.data['pending']==pending and resumed.data['queue']==[payload]
    resumed.import_inbox({'decision_id':pending['id'],'response':{'decline':True}})
    result=attempt(resumed);resumed.finish()
    assert result['executed'] and restored['eligibility'][rc.ROMANS]==rc.ELIGIBLE
    assert not resumed.data['pending'] and not resumed.data['queue']
    assert log[0]['assistant_id']==pending['id']
    assert [c['card_id'] for c in decode(log[0]['assistant_request'])['private_cards']]==[2,3]
    replay=position();replay['decision_agent']=lambda st,fa,re:{'decline':True} if fa==rc.ROMANS else None
    assert execute_decision(replay,rc.BELGAE,{'player_action':action()})==result
    assert encode(board_copy(replay))==encode(board_copy(restored))


def test_terminal_private_prompt_eof_rolls_back_whole_event():
    from fs_bot.cli.reactive import make_cli_reactive
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.tools.seat_session import board_copy
    state=position();before=encode(state);output=StringIO()
    state['decision_agent']=make_cli_reactive({rc.ROMANS},StringIO(),output)
    with pytest.raises(EOFError):
        with _action_transaction(state,lambda *a:None):
            execute_decision(state,rc.BELGAE,{'player_action':action()})
    assert 'Card 2:' in output.getvalue() and 'Card 3:' in output.getvalue()
    assert encode(board_copy(state))==before
