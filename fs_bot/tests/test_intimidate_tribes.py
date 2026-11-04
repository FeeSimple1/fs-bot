"""A4.6.2: the acting player chooses the actual Allied Tribe disc."""
from copy import deepcopy
from io import StringIO
import random

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, count_pieces_by_state, flip_piece
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cards.capabilities import activate_capability
from fs_bot.commands.rally import rally_in_region
from fs_bot.commands.raid import raid_in_region
from fs_bot.commands.sa_intimidate import intimidate
from fs_bot.engine.execute import _execute_intimidate, _resolve_card_A45_intimidate
from fs_bot.engine.raid_intimidate import target_options, resolve_raid_intimidate
from fs_bot.state.state_schema import build_initial_state, validate_state, check_structural_integrity
from fs_bot.state.serialize import encode, decode, save_game, load_game
from fs_bot.tools.seat_session import SeatSession, DecisionPending, board_copy
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine.game_engine import _action_transaction
from fs_bot.tests.test_raid_intimidate_decisions import _driver

R = rc.MANDUBII
CHOSEN = rc.TRIBE_SENONES
OTHER = rc.TRIBE_LINGONES
CITY = rc.TRIBE_MANDUBII


def board(scenario=rc.SCENARIO_ARIOVISTUS, owner=rc.ROMANS, citadel=False):
    state = build_initial_state(scenario, seed=19)
    state.update(current_card='A45', next_card=4,
                 non_player_factions={rc.ROMANS, rc.AEDUI, rc.BELGAE})
    place_piece(state, R, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    place_piece(state, R, rc.GERMANS, rc.WARBAND, 4)
    for tribe in (OTHER, CITY, CHOSEN):
        assert _ally_tribe(state, tribe, owner)
    if citadel:
        assert owner == rc.ARVERNI
        rally_in_region(state, R, owner, 'place_citadel', tribe=CITY, free=True)
    assert not validate_state(state) and not check_structural_integrity(state)
    return state


def entry(tribe=CHOSEN, owner=rc.ROMANS, **extra):
    return {'region': R, 'target_faction': owner, 'target_piece': rc.ALLY,
            'target_state': None, 'target_tribe': tribe, **extra}


def action(*entries):
    return {'sa': rc.SA_INTIMIDATE, 'sa_regions': [R],
            'details': {'intimidate_plan': list(entries)}}


def reactive_target(entry):
    return {k:v for k,v in entry.items() if k != 'region'}


def assert_exact(state, owner=rc.ROMANS):
    assert state['tribes'][CHOSEN]['allied_faction'] is None
    assert state['tribes'][OTHER]['allied_faction'] == owner
    assert not validate_state(state) and not check_structural_integrity(state)


@pytest.mark.parametrize('scenario', rc.ARIOVISTUS_SCENARIOS)
@pytest.mark.parametrize('owner', [rc.ROMANS, rc.ARVERNI])
@pytest.mark.parametrize('flow', ['ordinary', 'raid', 'A45'])
def test_exact_nondefault_tribe_survives_all_execution_adapters(scenario, owner, flow):
    state = board(scenario, owner)
    target = entry(owner=owner)
    if flow == 'ordinary':
        result = _execute_intimidate(state, rc.GERMANS, action(target))
    elif flow == 'raid':
        flip_piece(state, R, rc.GERMANS, rc.WARBAND, from_state=rc.HIDDEN, to_state=rc.REVEALED)
        state['decision_agent'] = lambda *_: {'targets': [reactive_target(target)]}
        result = resolve_raid_intimidate(state, R, 1)
    else:
        state['decision_agent'] = lambda *_: action(target)
        result = _resolve_card_A45_intimidate(state)[0]['result']
    assert result['executed'] and not result.get('errors')
    assert_exact(state, owner)
    assert result['intimidations'][0]['target_details'][0]['tribe'] == CHOSEN


@pytest.mark.parametrize('case', ['unknown', 'wrong_region', 'wrong_owner', 'citadel',
    'duplicate', 'null', 'list', 'non_ally', 'ally_visibility', 'marker_only', 'empty'])
def test_invalid_named_targets_reject_whole_region_before_any_effect(case):
    state = board(owner=rc.ARVERNI, citadel=True)
    first = entry(owner=rc.ARVERNI)
    targets = [first]
    if case == 'unknown': first['target_tribe'] = 'not a Tribe'
    if case == 'wrong_region': first['target_tribe'] = rc.TRIBE_HELVETII
    if case == 'wrong_owner': first['target_faction'] = rc.ROMANS
    if case == 'citadel': first['target_tribe'] = CITY
    if case == 'duplicate': targets.append(deepcopy(first))
    if case == 'null': first['target_tribe'] = None
    if case == 'list': first['target_tribe'] = [CHOSEN]
    if case == 'non_ally':
        place_piece(state, R, rc.ARVERNI, rc.WARBAND)
        first.update(target_piece=rc.WARBAND, target_state=rc.HIDDEN)
    if case == 'ally_visibility': first['target_state'] = rc.HIDDEN
    if case == 'marker_only': first.update(target_faction=None, target_piece=None)
    if case == 'empty': first['target_tribe'] = ''
    before = encode(board_copy(state))
    result = _execute_intimidate(state, rc.GERMANS, action(*targets))
    assert result['errors'] and not result['executed']
    assert encode(board_copy(state)) == before


def test_unspecified_legacy_target_keeps_sorted_default():
    state = board()
    target = entry();target.pop('target_tribe')
    result = _execute_intimidate(state, rc.GERMANS, action(target))
    assert result['executed'] and not result['errors']
    assert state['tribes'][OTHER]['allied_faction'] is None
    assert state['tribes'][CHOSEN]['allied_faction'] == rc.ROMANS


def test_unspecified_target_does_not_consume_a_later_explicit_reservation():
    state = board()
    default = entry();default.pop('target_tribe')
    result = _execute_intimidate(state, rc.GERMANS, action(default, entry(OTHER)))
    assert result['executed'] and not result['errors']
    assert state['tribes'][OTHER]['allied_faction'] is None
    assert state['tribes'][CITY]['allied_faction'] is None
    assert state['tribes'][CHOSEN]['allied_faction'] == rc.ROMANS
    assert not check_structural_integrity(state)


def test_dread_three_distinct_discs_and_two_pair_legacy_helper_contract():
    state = board()
    activate_capability(state, 'A22', rc.EVENT_SHADED)
    result = intimidate(state, R, 3, rc.ROMANS,
                        [(rc.ALLY, None, t) for t in (CHOSEN, CITY, OTHER)])
    assert len(result['target_removed']) == 3
    assert not count_pieces(state, R, rc.ROMANS, rc.ALLY)
    assert not check_structural_integrity(state)
    legacy = board()
    result = intimidate(legacy, R, 2, rc.ROMANS, [(rc.ALLY, None)] * 2)
    assert len(result['target_removed']) == 2
    assert legacy['tribes'][CHOSEN]['allied_faction'] == rc.ROMANS


def test_live_citadel_is_not_an_ally_option_or_removed_instead_of_disc():
    state = board(owner=rc.ARVERNI, citadel=True)
    offered = [t for t in target_options(state, R) if t['target_piece'] == rc.ALLY]
    assert {t.get('target_tribe') for t in offered} == {CHOSEN, OTHER}
    assert all(t['available'] == 1 for t in offered)
    result = _execute_intimidate(state, rc.GERMANS, action(entry(owner=rc.ARVERNI)))
    assert result['executed']
    assert_exact(state, rc.ARVERNI)
    assert state['tribes'][CITY]['allied_faction'] == rc.ARVERNI
    assert count_pieces(state, R, rc.ARVERNI, rc.CITADEL) == 1


@pytest.mark.parametrize('timing', [False, True])
def test_ordinary_terminal_plan_names_nondefault_disc_and_is_detached(timing):
    from fs_bot.cli.human_plan import _collect_intimidate
    state = board(owner=rc.ARVERNI, citadel=True)
    state['non_player_factions'] = set()
    answers = [R, rc.ARVERNI, rc.ALLY, CHOSEN, '(stop here)']
    if timing:
        state['_cli_action_windows'] = True
        answers = ['Finish voluntary removal', R, rc.ARVERNI,
                   f'{rc.ALLY} {CHOSEN}', '(stop here)', 'Finish voluntary removal']
    before = encode(state)
    output = StringIO()
    regions, extra = _collect_intimidate(state, rc.GERMANS,
        StringIO('\n'.join(answers)+'\n'), output)
    assert regions == [R] and encode(state) == before
    assert extra['intimidate_plan'][0]['target_tribe'] == CHOSEN
    assert f'{rc.ALLY} {CITY}\n' not in output.getvalue()
    from fs_bot.engine.action_windows import scope
    with scope(state, actor=rc.GERMANS, force=True):
        result = _execute_intimidate(state, rc.GERMANS, {'details': extra})
    assert result['executed'] and not result['errors']
    assert_exact(state, rc.ARVERNI)


def test_raid_terminal_names_and_reserves_each_disc_once():
    from fs_bot.cli.raid_intimidate import collect_raid_intimidate
    state = board(owner=rc.ARVERNI, citadel=True)
    request = {'kind':'raid_intimidate', 'region':R, 'raiders':2, 'max_removals':2}
    before = encode(state)
    response = collect_raid_intimidate(state, rc.GERMANS, request,
        StringIO(f'Remove {rc.ARVERNI} pieces and place the marker\n'
                 f'{rc.ALLY} at {CHOSEN}\n{rc.ALLY} at {OTHER}\n'), StringIO())
    assert [t['target_tribe'] for t in response['targets']] == [CHOSEN, OTHER]
    assert encode(state) == before


def test_raid_tribe_prompt_retains_board_inspection_and_eof_is_detached():
    from fs_bot.cli.raid_intimidate import collect_raid_intimidate
    state = board(owner=rc.ARVERNI, citadel=True)
    request = {'kind':'raid_intimidate', 'region':R, 'raiders':1, 'max_removals':1}
    before = encode(state)
    output = StringIO()
    response = collect_raid_intimidate(state, rc.GERMANS, request,
        StringIO(f'Remove {rc.ARVERNI} pieces and place the marker\nb\n'
                 f'{rc.ALLY} at {CHOSEN}\n'), output)
    assert response['targets'][0]['target_tribe'] == CHOSEN
    assert 'BOARD' in output.getvalue().upper()
    assert 'Please enter' not in output.getvalue()
    with pytest.raises(EOFError):
        collect_raid_intimidate(state, rc.GERMANS, request,
            StringIO(f'Remove {rc.ARVERNI} pieces and place the marker\n'), StringIO())
    assert encode(state) == before


@pytest.mark.parametrize('bad', [None, CITY, OTHER, 'missing'])
def test_bad_named_reactive_choice_stays_pending_without_consuming_board(bad):
    from fs_bot.engine.agent import consult_agent
    state = board(owner=rc.ARVERNI, citadel=True)
    flip_piece(state, R, rc.GERMANS, rc.WARBAND, from_state=rc.HIDDEN, to_state=rc.REVEALED)
    if bad == OTHER:
        targets = [reactive_target(entry(OTHER, rc.ARVERNI))] * 2
    else:
        targets = [reactive_target(entry(bad, rc.ARVERNI))]
        if bad == 'missing':
            targets[0].pop('target_tribe')
    session = SeatSession(state, {'seat':rc.GERMANS}, [], HumanTurnDisplay(StringIO()))
    state['decision_agent'] = session.reactive
    session.import_inbox([{'response':{'targets':targets}}])
    before = encode(board_copy(state))
    request = {'kind':'raid_intimidate', 'region':R, 'raiders':2,
               'max_removals':2, 'targets':target_options(state,R)}
    with pytest.raises(DecisionPending):
        with _action_transaction(state, _driver(session)):
            consult_agent(state, rc.GERMANS, request)
    assert session.error and session.data['pending']['id'] == 'd000001'
    assert len(session.data['queue']) == 1 and not session.data['journal']
    assert encode(board_copy(state)) == before


@pytest.mark.parametrize('flow', ['ordinary', 'A45'])
@pytest.mark.parametrize('layout', ['merged', 'nested', 'null_merged'])
def test_missing_named_human_ally_is_rejected_instead_of_using_default(flow, layout):
    state = board()
    target = entry(); target.pop('target_tribe')
    plan = action(target)
    if layout != 'merged':
        plan['details'] = {'sa_details': plan['details']}
        if layout == 'null_merged':
            plan['details']['intimidate_plan'] = None
    before = encode(state)
    if flow == 'ordinary':
        from fs_bot.engine.action_validation import validate_human_structure
        plan.update(command=rc.CMD_RAID)
        error = validate_human_structure(state, rc.GERMANS, plan)
    else:
        from fs_bot.engine.free_actions import validate_free_action_response
        error = validate_free_action_response(state, rc.GERMANS,
            {'kind':'free_action','request_type':'event_sa','allowed_sas':[rc.SA_INTIMIDATE],
             'free':True,'intimidate_anywhere':True}, plan)
    assert error and 'target_tribe' in error
    assert encode(state) == before


def test_actual_raid_pause_save_resume_and_journal_preserve_named_disc(tmp_path):
    state = board(owner=rc.ARVERNI, citadel=True)
    session = SeatSession(state, {'seat':rc.GERMANS}, [], HumanTurnDisplay(StringIO()))
    state['decision_agent'] = session.reactive
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending):
        with _action_transaction(state, _driver(session)):
            raid_in_region(state, R, rc.GERMANS, [{'type':'gain'}])
    pending = session.data['pending']
    assert encode(board_copy(state)) == before
    offered = decode(pending['request'])['targets']
    assert {t.get('target_tribe') for t in offered if t['target_piece']==rc.ALLY} == {CHOSEN, OTHER}
    path = tmp_path/'named-tribe.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path)
    resumed = SeatSession(restored, meta, log, HumanTurnDisplay(StringIO()))
    restored['decision_agent'] = resumed.reactive
    choice = {'targets':[reactive_target(entry(owner=rc.ARVERNI))]}
    resumed.import_inbox({'decision_id':pending['id'], 'response':choice})
    with _action_transaction(restored, _driver(resumed)):
        result = raid_in_region(restored, R, rc.GERMANS, [{'type':'gain'}])
    resumed.finish()
    assert result['raid_intimidate']['executed']
    assert_exact(restored, rc.ARVERNI)
    assert decode(log[0]['assistant_response']) == choice
    assert not resumed.data['queue'] and not resumed.data['journal']


def test_harudes_executor_directs_exact_intrinsic_raid_choice():
    from fs_bot.cards.harudes_bellovaci import RAID_CHOOSER
    state = board(owner=rc.ARVERNI)
    state[RAID_CHOOSER] = rc.ROMANS
    flip_piece(state, R, rc.GERMANS, rc.WARBAND, from_state=rc.HIDDEN, to_state=rc.REVEALED)
    seen=[]
    def agent(current, faction, request):
        seen.append((faction,request['acting_faction']))
        return {'targets':[reactive_target(entry(owner=rc.ARVERNI))]}
    state['decision_agent']=agent
    assert resolve_raid_intimidate(state,R,1)['executed']
    assert seen==[(rc.ROMANS,rc.GERMANS)]
    assert_exact(state,rc.ARVERNI)


def test_fuzzer_retains_exact_tribes_and_never_reuses_a_disc():
    from fs_bot.tools.player_fuzz import make_random_reactive
    from fs_bot.engine.raid_intimidate import validate_response
    state=board(owner=rc.ARVERNI,citadel=True)
    flip_piece(state,R,rc.GERMANS,rc.WARBAND,2,from_state=rc.HIDDEN,to_state=rc.REVEALED)
    request={'kind':'raid_intimidate','region':R,'raiders':2,'max_removals':2,
             'targets':target_options(state,R)}
    named=0
    for seed in range(30):
        response=make_random_reactive({rc.GERMANS}, random.Random(seed))(state,rc.GERMANS,request)
        validate_response(state,request,response)
        targets=response.get('targets',[])
        assert all('target_tribe' in t for t in targets)
        assert len({t['target_tribe'] for t in targets})==len(targets)
        named+=len(targets)
    assert named
