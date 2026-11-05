"""Player Region order (§4.1/4.2.1), distinct from NP passes (§8.8.1)."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces
from fs_bot.board.control import refresh_all_control
from fs_bot.engine.execute import _execute_build
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import encode, decode

A, B = rc.SEQUANI, rc.AEDUI_REGION


def position(scenario):
    state = build_initial_state(scenario, seed=19)
    state['non_player_factions'] = set()
    place_piece(state, A, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    for region in (A, B):
        place_piece(state, region, rc.ROMANS, rc.AUXILIA, 5)
    refresh_all_control(state)
    state['resources'][rc.ROMANS] = 2
    assert validate_state(state) == []
    return state


def action(order):
    return {'sa': rc.SA_BUILD, 'details': {'build_plan': {
        'forts': [B], 'allies': [{'region': A, 'tribe': rc.TRIBE_HELVETII}],
        'region_order': order}}}


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
@pytest.mark.parametrize('first', [A, B])
@pytest.mark.parametrize('nested', [False, True])
def test_resource_budget_follows_player_region_order(scenario, first, nested):
    state = position(scenario)
    plan = action([first, B if first == A else A])
    if nested:
        plan['details'] = {'sa_details': plan['details']}
    result = _execute_build(state, rc.ROMANS, plan)
    expected = ('ally', A, rc.TRIBE_HELVETII) if first == A else ('fort', B)
    assert result['actions'] == [expected], result
    assert len(result['errors']) == 1
    assert state['resources'][rc.ROMANS] == 0
    assert validate_state(state) == []


def test_legacy_plan_keeps_source_required_np_passes():
    state = position(rc.SCENARIO_GREAT_REVOLT)
    plan = action([A, B])
    del plan['details']['build_plan']['region_order']
    result = _execute_build(state, rc.ROMANS, plan)
    assert result['actions'] == [('fort', B)]


@pytest.mark.parametrize('order', [None, 'Sequani', [A,A], [A], [B], [A,B,rc.MORINI], [A,{}]])
def test_invalid_order_rejected_without_timing_or_mutation(order, monkeypatch):
    state = position(rc.SCENARIO_GREAT_REVOLT)
    before = encode(state)
    monkeypatch.setattr('fs_bot.engine.execute._timing_plan_step', lambda *a, **k: pytest.fail('timing before validation'))
    result = _execute_build(state, rc.ROMANS, action(order))
    assert not result['executed'] and 'region_order' in result['reason']
    assert encode(state) == before


@pytest.mark.parametrize('key,entry', [('forts', B), ('allies', {'region': A, 'tribe': rc.TRIBE_SEQUANI})])
def test_duplicate_operations_rejected_before_mutation(key, entry):
    state = position(rc.SCENARIO_GREAT_REVOLT)
    plan = action([A,B]);plan['details']['build_plan'][key].append(entry)
    before = encode(state)
    result = _execute_build(state, rc.ROMANS, plan)
    assert not result['executed']
    assert encode(state) == before


def test_timing_category_indices_follow_authored_order(monkeypatch):
    state = position(rc.SCENARIO_GREAT_REVOLT)
    state['resources'][rc.ROMANS] = 10
    calls=[]
    monkeypatch.setattr('fs_bot.engine.execute._timing_plan_step',
                        lambda state, faction, plan, stage, **kw: calls.append((stage,kw['index'],kw['region'])))
    plan = action([A,B]);plan['details']['build_plan']['forts'].append(A)
    result = _execute_build(state, rc.ROMANS, plan)
    assert not result['errors']
    assert calls == [('build_fort',1,A),('build_ally',0,A),('build_fort',0,B)]
    assert result['actions'] == [('fort',A),('ally',A,rc.TRIBE_HELVETII),('fort',B)]


def test_save_load_replays_identical_order():
    state = position(rc.SCENARIO_ARIOVISTUS)
    other = decode(encode(state))
    plan = action([A,B])
    assert _execute_build(state,rc.ROMANS,plan) == _execute_build(other,rc.ROMANS,deepcopy(plan))
    assert encode(state) == encode(other)


def test_shared_human_validation_rejects_before_command():
    from fs_bot.engine.action_validation import validate_human_structure
    from fs_bot.engine.execute import execute_decision
    state=position(rc.SCENARIO_GREAT_REVOLT)
    plan=action([A,A]);plan.update(command=rc.CMD_SEIZE,regions=[A],sa_timing='after')
    plan['details']['disperse_tribes']={A:[]}
    before=encode(state)
    assert 'region_order' in validate_human_structure(state,rc.ROMANS,plan)
    result=execute_decision(state,rc.ROMANS,{'player_action':plan})
    assert not result['executed']
    assert encode(state)==before


def test_timing_collector_completes_each_region_and_does_not_mutate_live(monkeypatch):
    from fs_bot.cli import roman_timing, human_plan
    state=position(rc.SCENARIO_GREAT_REVOLT)
    state['resources'][rc.ROMANS]=10
    before=encode(state);seen=[]
    monkeypatch.setattr(human_plan,'_pick_regions',lambda *a,**k:[A,B])
    def prepare(sim,faction,stdin,stdout,**kw):
        seen.append((kw['stage'],kw['region']))
        return sim,[]
    monkeypatch.setattr(roman_timing,'prepare',prepare)
    def pick(stdin,stdout,prompt,options):
        # Ally-only in A; Fort-only in B, despite category grouping.
        if prompt.startswith(A) and 'build ally' in prompt:
            return next(value for label,value in options if value == rc.TRIBE_HELVETII)
        if prompt.startswith(B) and 'build fort' in prompt:
            return B
        return None
    monkeypatch.setattr(roman_timing,'prompt_choice',pick)
    regions,extra=roman_timing.collect_build(state,rc.ROMANS,StringIO(),StringIO())
    assert extra['build_plan']['region_order']==[A,B]
    assert seen==[(stage,region) for region in (A,B) for stage in ('build_fort','build_subdue','build_ally')]
    assert encode(state)==before
    assert _execute_build(state,rc.ROMANS,{'sa':rc.SA_BUILD,'details':extra})['actions']==[
        ('ally',A,rc.TRIBE_HELVETII),('fort',B)]


def test_one_region_cap_rejects_ordered_plan_before_command():
    from fs_bot.cards.capabilities import activate_capability
    from fs_bot.commands.sa_build import build_plan_error
    state=position(rc.SCENARIO_GREAT_REVOLT)
    activate_capability(state,12,rc.EVENT_SHADED)
    before=encode(state)
    assert 'one Region' in build_plan_error(action([A,B]),state)
    assert not _execute_build(state,rc.ROMANS,action([A,B]))['executed']
    assert encode(state)==before


def test_legacy_collector_records_selected_region_order(monkeypatch):
    from fs_bot.cli import human_plan
    state=position(rc.SCENARIO_GREAT_REVOLT)
    monkeypatch.setattr(human_plan,'_pick_regions',lambda *a,**k:[A,B])
    def pick(stdin,stdout,prompt,options):
        if 'Build action' in prompt:
            return 'ally' if A in prompt else 'fort'
        return rc.TRIBE_HELVETII
    monkeypatch.setattr(human_plan,'prompt_choice',pick)
    before=encode(state)
    regions,extra=human_plan._collect_build(state,rc.ROMANS,StringIO(),StringIO())
    assert extra['build_plan']['region_order']==[A,B]
    assert encode(state)==before


@pytest.mark.parametrize('malformed',[[],{'forts':None},{'allies':[A]},{'subdue':[{}]}])
def test_malformed_plan_has_clear_atomic_refusal(malformed):
    state=position(rc.SCENARIO_GREAT_REVOLT)
    plan={'sa':rc.SA_BUILD,'details':{'build_plan':malformed}}
    before=encode(state)
    result=_execute_build(state,rc.ROMANS,plan)
    assert not result['executed'] and result['reason']
    assert encode(state)==before


@pytest.mark.parametrize('scenario',[rc.SCENARIO_GREAT_REVOLT,rc.SCENARIO_ARIOVISTUS])
def test_subdue_before_other_regions_fort(scenario):
    state=position(scenario)
    place_piece(state,A,rc.BELGAE,rc.ALLY)
    state['tribes'][rc.TRIBE_HELVETII]['allied_faction']=rc.BELGAE
    refresh_all_control(state)
    plan=action([A,B]);build=plan['details']['build_plan']
    build['subdue']=build.pop('allies')
    result=_execute_build(state,rc.ROMANS,plan)
    assert result['actions']==[('subdue',A,rc.TRIBE_HELVETII)]
    assert state['tribes'][rc.TRIBE_HELVETII]['allied_faction'] is None
    assert validate_state(state)==[]


@pytest.mark.parametrize('standalone',[False,True])
def test_invalid_order_pending_identity_survives_rollback_and_resume(tmp_path,standalone):
    from fs_bot.tests.test_repeated_seize_entreat_regions import session_for, attempt
    from fs_bot.tools.seat_session import DecisionPending, board_copy
    from fs_bot.state.serialize import save_game,load_game
    from fs_bot.engine.game_engine import ACTION_COMMAND_SA
    state=position(rc.SCENARIO_GREAT_REVOLT)
    state['resources'][rc.ROMANS]=10
    plan=action([A,A])
    if standalone:
        request={'kind':'free_action','request_type':'event_sa','allowed_sas':[rc.SA_BUILD],
                 'allowed_regions':[A,B],'free':True}
        response=plan
    else:
        plan.update(command=rc.CMD_SEIZE,regions=[A],sa_timing='after')
        plan['details']['disperse_tribes']={A:[]}
        request={'kind':'turn','options':[ACTION_COMMAND_SA],'position':'1st_eligible'}
        response={'action':ACTION_COMMAND_SA,'player_action':plan}
    session=session_for(state,rc.ROMANS)
    before=encode(board_copy(state))
    with pytest.raises(DecisionPending):attempt(session,request)
    pending=deepcopy(session.data['pending'])
    payload={'decision_id':pending['id'],'response':response}
    session.import_inbox(payload)
    with pytest.raises(DecisionPending):attempt(session,request)
    assert 'region_order' in session.error
    assert session.data['pending']==pending and session.data['queue']==[payload]
    assert encode(board_copy(state))==before
    path=tmp_path/'build.json';save_game(state,path,meta=session.meta,log=session.log)
    loaded,meta,log=load_game(path);resumed=session_for(loaded,rc.ROMANS,meta,log)
    with pytest.raises(DecisionPending):attempt(resumed,request)
    assert resumed.data['pending']==pending
    corrected=deepcopy(response)
    target=corrected if standalone else corrected['player_action']
    target['details']['build_plan']['region_order']=[A,B]
    resumed.import_inbox({'decision_id':pending['id'],'response':corrected})
    for _ in range(20):
        try:
            result=attempt(resumed,request)
            break
        except DecisionPending:
            next_pending=resumed.data['pending']
            assert decode(next_pending['request'])['kind']=='voluntary_removal'
            resumed.import_inbox({'decision_id':next_pending['id'],'response':{'done':True}})
    else:pytest.fail('Corrected Build did not finish')
    assert result['executed'] and not result.get('errors'),result
    resumed.finish()
    assert not resumed.data['pending'] and not resumed.data['queue']
    assert resumed.log[0]['assistant_id']==pending['id']
    assert decode(resumed.log[0]['assistant_response'])==corrected
