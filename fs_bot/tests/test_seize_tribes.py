"""§3.2.3: exact selected Tribe circles, including when markers are scarce."""
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.commands.seize import seize_in_region, get_dispersible_tribes, count_dispersed_on_map
from fs_bot.commands.common import CommandError
from fs_bot.engine.execute import _execute_seize, execute_decision, _constrain_bot_action
from fs_bot.engine.game_engine import ACTION_COMMAND, _action_transaction
from fs_bot.state.serialize import encode, decode, save_game, load_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import SeatSession, DecisionPending, board_copy
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.tests.test_raid_intimidate_decisions import _driver

R=rc.MANDUBII
C=rc.CARNUTES
T=rc.TRIBE_LINGONES
FINISH='Finish Dispersal (Forage still occurs)'


def board(scenario=rc.SCENARIO_GREAT_REVOLT):
    state=build_initial_state(scenario,seed=4)
    state.update(current_card=1,next_card=4,non_player_factions=set())
    for region in (R,C):place_piece(state,region,rc.ROMANS,rc.AUXILIA,4)
    state['decision_agent']=lambda *args: {'decline':True}
    return state


def scarce(state):
    for i,tribe in enumerate((rc.TRIBE_MORINI,rc.TRIBE_MENAPII,rc.TRIBE_NERVII)):
        state['tribes'][tribe]['status']=rc.DISPERSED_GATHERING if i else rc.DISPERSED
    assert count_dispersed_on_map(state)==3


def plan(tribes,regions=None):
    return {'command':rc.CMD_SEIZE,'regions':regions or [R],'sa':'No SA','sa_regions':[],
            'details':{'disperse_tribes':tribes}}


@pytest.mark.parametrize('scenario',rc.ALL_SCENARIOS)
@pytest.mark.parametrize('selected',[[T],[rc.TRIBE_SENONES,T]])
def test_ordinary_exact_nondefault_subset_in_all_scenarios(scenario,selected):
    state=board(scenario)
    result=execute_decision(state,rc.ROMANS,{'player_action':plan({R:selected})})
    assert result['executed'] and not result['errors']
    assert result['regions'][0]['tribes_dispersed']==selected
    assert count_dispersed_on_map(state)==len(selected)
    assert state['tribes'][rc.TRIBE_MANDUBII]['status'] is None
    assert result['forage_resources_total']==6*len(selected)+2*(3-len(selected))
    assert not validate_state(state)


@pytest.mark.parametrize('scenario',rc.ALL_SCENARIOS)
def test_last_marker_can_choose_last_tribe_not_automatic_prefix(scenario):
    state=board(scenario);scarce(state)
    result=_execute_seize(state,rc.ROMANS,plan({R:[T]}))
    assert result['executed'] and not result['errors']
    assert result['regions'][0]['tribes_dispersed']==[T]
    assert count_dispersed_on_map(state)==4 and state['tribes'][T]['status']==rc.DISPERSED
    assert state['tribes'][rc.TRIBE_MANDUBII]['status'] is None
    assert result['forage_resources_total']==10


@pytest.mark.parametrize('scenario',rc.ALL_SCENARIOS)
def test_explicit_forage_only_needs_no_markers_or_rng(scenario):
    state=board(scenario);scarce(state)
    state['tribes'][rc.TRIBE_EBURONES]['status']=rc.DISPERSED
    rng=state['rng'].getstate()
    result=_execute_seize(state,rc.ROMANS,plan({R:[]}))
    assert result['executed'] and not result['errors']
    assert result['forage_resources_total']==6 and not result['tribes_dispersed_total']
    assert state['rng'].getstate()==rng and count_dispersed_on_map(state)==4


@pytest.mark.parametrize('case',['missing','null_map','partial','extra_region','null_list',
    'string_list','duplicate','non_string','foreign','unknown','mixed_legacy',
    'one_shadow_part','wrong_part_command','nested_part','phantom_no_sa'])
def test_invalid_authored_identity_plan_rejects_before_command_effects(case):
    state=board();action=plan({R:[T]})
    d=action['details']
    if case=='missing':d.pop('disperse_tribes')
    if case=='null_map':d['disperse_tribes']=None
    if case=='partial':d['disperse_tribes']={}
    if case=='extra_region':d['disperse_tribes'][C]=[]
    if case=='null_list':d['disperse_tribes'][R]=None
    if case=='string_list':d['disperse_tribes'][R]=T
    if case=='duplicate':d['disperse_tribes'][R]=[T,T]
    if case=='non_string':d['disperse_tribes'][R]=[[T]]
    if case=='foreign':d['disperse_tribes'][R]=[rc.TRIBE_AULERCI]
    if case=='unknown':d['disperse_tribes'][R]=['unknown Tribe']
    if case=='mixed_legacy':d['disperse_regions']=[R]
    if case in ('one_shadow_part','wrong_part_command','nested_part','phantom_no_sa'):
        action['details']={'command_parts':[plan({C:[]},[C]),plan({R:[T]})]}
        action.update(sa=rc.SA_BUILD,sa_timing='during')
        if case=='one_shadow_part':action['details']['command_parts']=action['details']['command_parts'][:1]
        if case=='wrong_part_command':action['details']['command_parts'][0]['command']=rc.CMD_RAID
        if case=='nested_part':action['details']['command_parts'][0]['details']['command_parts']=[plan({C:[]},[C])]
        if case=='phantom_no_sa':action['sa']='No SA'
    before=encode(board_copy(state))
    result=execute_decision(state,rc.ROMANS,{'player_action':action})
    assert not result['executed'] and result['rejected']
    assert encode(board_copy(state))==before


@pytest.mark.parametrize('case',['budget','ally','dispersed','control'])
def test_live_eligibility_is_rechecked_without_substitution_or_partial_region(case):
    state=board();action=plan({R:[T]})
    if case=='budget':scarce(state);action=plan({R:[rc.TRIBE_SENONES,T]})
    if case=='ally':assert _ally_tribe(state,T,rc.AEDUI)
    if case=='dispersed':state['tribes'][T]['status']=rc.DISPERSED_GATHERING
    if case=='control':
        place_piece(state,R,rc.ARVERNI,rc.WARBAND,5)
        action['details']['as_if_control']=True  # Not trusted Event authority.
    before=encode(board_copy(state))
    result=_execute_seize(state,rc.ROMANS,action)
    assert result['errors'] and not result['executed']
    assert encode(board_copy(state))==before


def test_mechanical_duplicate_cannot_double_forage_or_rally_rolls():
    state=board();before=encode(board_copy(state))
    with pytest.raises(CommandError):seize_in_region(state,R,[T,T])
    assert encode(board_copy(state))==before


@pytest.mark.parametrize('timing',[False,True])
def test_menu_shows_all_tribes_for_one_slot_and_inspection_is_detached(timing):
    from fs_bot.cli.human_plan import _collect_seize
    state=board();scarce(state)
    if timing:state['_cli_action_windows']=True
    answers=[R]
    if timing:answers+=['Finish voluntary removal']
    answers+=['b',T]
    before=encode(board_copy(state));output=StringIO()
    details=_collect_seize(state,rc.ROMANS,StringIO('\n'.join(answers)+'\n'),output,True)
    assert details['disperse_tribes']=={R:[T]}
    assert '1 markers available' in output.getvalue()
    assert 'BOARD' in output.getvalue().upper() and 'Please enter' not in output.getvalue()
    assert encode(board_copy(state))==before


def test_two_region_menu_reserves_marker_budget_and_can_stop_after_one_tribe():
    from fs_bot.cli.human_plan import _collect_seize
    state=board();scarce(state)
    # Use labels so Region indices/order are irrelevant to the test.
    stream=StringIO(f'{R}\n{C}\n{T}\n')
    output=StringIO();before=encode(board_copy(state))
    details=_collect_seize(state,rc.ROMANS,stream,output,False)
    assert details['_regions']==[R,C]
    assert details['disperse_tribes']=={R:[T],C:[]}
    assert encode(board_copy(state))==before


def test_menu_empty_subset_forages_and_does_not_roll_rng():
    from fs_bot.cli.human_plan import _collect_seize
    state=board();before=encode(board_copy(state))
    details=_collect_seize(state,rc.ROMANS,StringIO(f'{R}\n{FINISH}\n'),StringIO(),True)
    assert details['disperse_tribes']=={R:[]} and encode(board_copy(state))==before


def test_scoped_exact_plan_clips_map_keys_without_adding_legacy_disperse_flag():
    state=board();action=plan({R:[T],C:[rc.TRIBE_AULERCI]},[R,C])
    clipped=_constrain_bot_action(action,{R},state=state,faction=rc.ROMANS)
    assert clipped['regions']==[R] and clipped['details']['disperse_tribes']=={R:[T]}
    assert 'disperse_regions' not in clipped['details']
    result=_execute_seize(state,rc.ROMANS,clipped)
    assert result['executed'] and result['regions'][0]['tribes_dispersed']==[T]


def test_interrupted_seize_validates_and_preserves_each_portions_exact_map():
    state=board();place_piece(state,C,rc.ROMANS,rc.LEADER,leader_name=rc.CAESAR)
    action={'command':rc.CMD_SEIZE,'sa':rc.SA_BUILD,'sa_regions':[C],'sa_timing':'during',
            'details':{'command_parts':[plan({C:[]},[C]),plan({R:[T]})],
                       'build_plan':{'forts':[C]}}}
    result=execute_decision(state,rc.ROMANS,{'player_action':action})
    assert result['executed'] and not result['errors']
    assert result['command_parts'][1]['regions'][0]['tribes_dispersed']==[T]
    assert count_pieces(state,C,rc.ROMANS,rc.FORT)==1
    assert count_dispersed_on_map(state)==1 and not validate_state(state)


def test_legacy_npc_regions_still_disperse_the_same_automatic_subset():
    state=board();scarce(state)
    chosen=get_dispersible_tribes(state,R)
    result=_execute_seize(state,rc.ROMANS,{'command':rc.CMD_SEIZE,'regions':[R],
                                         'details':{'disperse_regions':[R]}})
    assert result['executed'] and result['regions'][0]['tribes_dispersed']==chosen
    assert len(chosen)==1


@pytest.mark.parametrize('disperse',[False,True])
def test_synthetic_policy_authors_real_regions_and_reserves_exact_markers(disperse):
    from fs_bot.agents.heuristic import build_seize
    from fs_bot.engine.moves import validate_player_action
    state=board();scarce(state);before=encode(board_copy(state))
    action=build_seize(state,rc.ROMANS,{'disperse':disperse,'max_regions':2},False)
    action.update(sa='No SA',sa_regions=[])
    assert action['regions'] and set(action['details']['disperse_tribes'])==set(action['regions'])
    assert sum(map(len,action['details']['disperse_tribes'].values()))==int(disperse)
    ok,result=validate_player_action(state,rc.ROMANS,action)
    assert ok and not result['errors'] and encode(board_copy(state))==before


def test_arduenna_mechanical_seize_witness_uses_the_shared_exact_contract():
    from fs_bot.cards.arduenna import command_witness
    state=board()
    request={'allowed_commands':[rc.CMD_SEIZE],'allowed_regions':[R],
             'free':True,'with_sa':False}
    action=command_witness(state,rc.ROMANS,regions=[R],request=request)
    assert action and action['command']==rc.CMD_SEIZE
    assert action['details']['disperse_tribes']=={R:[]}


@pytest.mark.parametrize('bad',[{}, {R:None}, {R:[T,T]}])
def test_invalid_durable_map_stays_pending_without_consuming_input(bad):
    state=board();session=SeatSession(state,{'seat':rc.ROMANS},[],HumanTurnDisplay(StringIO()))
    request={'kind':'turn','options':[ACTION_COMMAND],'position':'1st_eligible'}
    session.import_inbox([{'response':{'action':ACTION_COMMAND,'player_action':plan(bad)}}])
    before=encode(board_copy(state))
    with pytest.raises(DecisionPending):
        with _action_transaction(state,_driver(session)):
            session.ask(state,rc.ROMANS,request)
    assert session.error and session.data['pending']['id']=='d000001'
    assert session.data['queue'] and not session.data['journal']
    assert encode(board_copy(state))==before


def test_accepted_actor_subset_survives_rally_pause_save_resume_and_journal(tmp_path):
    state=board();session=SeatSession(state,{'seat':rc.ROMANS},[],HumanTurnDisplay(StringIO()))
    request={'kind':'turn','options':[ACTION_COMMAND],'position':'1st_eligible'}
    decision={'action':ACTION_COMMAND,'player_action':plan({R:[T]})}
    session.import_inbox([{'response':decision}])
    def step(current,pause):
        def agent(live,faction,req):
            if req.get('source')=='seize' and faction==rc.ARVERNI:
                if pause:raise EOFError('pause after selected marker and published roll')
                return {'decline':True}
            if faction!=rc.ROMANS:return {'decline':True}
            return current.reactive(live,faction,req)
        current.state['decision_agent']=agent
        with _action_transaction(current.state,_driver(current)):
            accepted=current.ask(current.state,rc.ROMANS,request)
            return execute_decision(current.state,rc.ROMANS,accepted)
    before=encode(board_copy(state))
    with pytest.raises(EOFError):step(session,True)
    assert encode(board_copy(state))==before
    assert decode(session.data['journal'][0]['assistant_response'])==decision
    path=tmp_path/'seize.json';save_game(state,path,meta=session.meta,log=session.log)
    restored,meta,log=load_game(path)
    resumed=SeatSession(restored,meta,log,HumanTurnDisplay(StringIO()))
    result=step(resumed,False);resumed.finish()
    assert result['executed'] and result['regions'][0]['tribes_dispersed']==[T]
    assert restored['resources'][rc.ROMANS]==10 and count_dispersed_on_map(restored)==1
    assert decode(log[0]['assistant_response'])==decision and not validate_state(restored)
