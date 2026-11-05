"""Card 10 shaded: owner may remove a surviving Fort/Citadel after Ambush."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, remove_piece, count_pieces, count_pieces_by_state
from fs_bot.cards.capabilities import activate_capability, set_capability_owner
from fs_bot.engine.execute import _execute_battle, execute_decision
from fs_bot.engine.ballistae_choice import KIND, target_options, validate_response
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import encode, decode

REGION = rc.SEQUANI


def target(piece=rc.CITADEL, tribe=rc.TRIBE_SEQUANI, owner=rc.ARVERNI):
    return dict(piece_type=piece, tribe=tribe, owner=owner)


def position(scenario=rc.SCENARIO_GREAT_REVOLT, owner=rc.BELGAE,
             defender=rc.ARVERNI, region=REGION):
    state = build_initial_state(scenario, seed=17)
    state['non_player_factions'] = set(rc.FACTIONS) - {owner}
    state['resources'][owner] = 10
    place_piece(state, region, owner, rc.WARBAND)
    if owner == rc.BELGAE:
        place_piece(state, region, owner, rc.LEADER, leader_name=rc.AMBIORIX)
    elif owner == rc.ARVERNI and scenario in rc.BASE_SCENARIOS:
        place_piece(state, region, owner, rc.LEADER, leader_name=rc.VERCINGETORIX)
    if defender == rc.ROMANS:
        place_piece(state, region, defender, rc.FORT)
        place_piece(state, region, defender, rc.AUXILIA, 4, piece_state=rc.REVEALED)
    else:
        place_piece(state, region, defender, rc.CITADEL)
        state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] = defender
        place_piece(state, region, defender, rc.WARBAND, 4, piece_state=rc.REVEALED)
    activate_capability(state, 10, rc.EVENT_SHADED)
    set_capability_owner(state, 10, owner)
    return state


def plan(owner=rc.BELGAE, defender=rc.ARVERNI, regions=(REGION,), ambush=True):
    return dict(command=rc.CMD_BATTLE, sa=rc.SA_AMBUSH if ambush else None,
                sa_regions=list(regions) if ambush else [],
                details={'battle_plan': [dict(region=r, target=defender) for r in regions]})


def agent_for(state, response, seen=None):
    seen = seen if seen is not None else []
    def agent(board, faction, request):
        if request['kind'] != KIND:
            return None
        assert faction == request['attacker']
        # Full Battle, including Reveal, has already finished.
        assert count_pieces_by_state(board, request['region'], faction,
                                     rc.WARBAND, rc.HIDDEN) == 0
        seen.append(deepcopy(request))
        return response
    state['decision_agent'] = agent
    return seen


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
@pytest.mark.parametrize('remove', [False, True])
def test_owner_chooses_after_actual_ambush_with_named_citadel(scenario, remove):
    state = position(scenario)
    response = {'target': target()} if remove else {'decline': True}
    seen = agent_for(state, response)
    result = _execute_battle(state, rc.BELGAE, plan())
    assert result['executed'] and not result['errors']
    assert len(seen) == 1 and seen[0]['targets'] == [target()]
    assert seen[0]['card_id'] == 10 and seen[0]['side'] == rc.EVENT_SHADED
    assert count_pieces(state, REGION, rc.ARVERNI, rc.CITADEL) == (not remove)
    assert (state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] is None) == remove
    assert count_pieces(state, REGION, rc.ARVERNI, rc.WARBAND) == 3
    assert validate_state(state) == []


@pytest.mark.parametrize('owner', [rc.AEDUI, rc.ARVERNI, rc.BELGAE])
def test_request_belongs_to_gallic_capability_owner(owner):
    defender = rc.AEDUI if owner == rc.ARVERNI else rc.ARVERNI
    state = position(owner=owner, defender=defender)
    seen = agent_for(state, {'decline': True})
    result = _execute_battle(state, owner, plan(owner, defender), _ambush_anywhere=True)
    assert result['executed'] and not result['errors']
    assert seen[0]['attacker'] == owner and seen[0]['defender'] == defender
    assert count_pieces(state, REGION, defender, rc.CITADEL) == 1


@pytest.mark.parametrize('remove', [False, True])
def test_optional_roman_fort_removal(remove):
    state = position(defender=rc.ROMANS)
    fort = target(rc.FORT, None, rc.ROMANS)
    seen = agent_for(state, {'target': fort} if remove else {'decline': True})
    result = _execute_battle(state, rc.BELGAE, plan(defender=rc.ROMANS))
    assert result['executed'] and not result['errors']
    assert seen[0]['targets'] == [fort]
    assert count_pieces(state, REGION, rc.ROMANS, rc.FORT) == (not remove)
    assert validate_state(state) == []


@pytest.mark.parametrize('response', [None, {'use_default': True}])
def test_raw_defer_retains_existing_removal_and_rng(response):
    state = position()
    control = decode(encode(state))
    agent_for(state, response)
    assert _execute_battle(state, rc.BELGAE, plan()) == _execute_battle(control, rc.BELGAE, plan())
    state.pop('decision_agent')
    assert encode(state) == encode(control)
    assert count_pieces(state, REGION, rc.ARVERNI, rc.CITADEL) == 0


@pytest.mark.parametrize('bad', [{}, {'decline': False}, {'decline': 1},
    {'use_default': 1}, {'target': None}, {'target': rc.CITADEL},
    {'target': target(tribe=rc.TRIBE_HELVETII)}, {'target': target(owner=rc.AEDUI)},
    {'target': target(rc.ALLY)}, {'target': target(), 'decline': True},
    {'target': dict(target(), count=2)}])
def test_invalid_target_does_not_mutate_piece_selection(bad):
    state = position()
    request = dict(region=REGION, defender=rc.ARVERNI,
                   targets=target_options(state, REGION, rc.ARVERNI))
    before = encode(state)
    with pytest.raises(ValueError):
        validate_response(state, request, bad)
    assert encode(state) == before


def test_stale_target_is_rejected_against_live_survivors():
    state = position()
    request = dict(region=REGION, defender=rc.ARVERNI,
                   targets=target_options(state, REGION, rc.ARVERNI))
    remove_piece(state, REGION, rc.ARVERNI, rc.CITADEL)
    with pytest.raises(ValueError):
        validate_response(state, request, {'target': target()})


@pytest.mark.parametrize('mode', ['ordinary_battle', 'unshaded', 'other_owner', 'no_target'])
def test_inapplicable_capability_does_not_request(mode):
    state = position()
    if mode == 'unshaded':
        activate_capability(state, 10, rc.EVENT_UNSHADED)
    elif mode == 'other_owner':
        set_capability_owner(state, 10, rc.AEDUI)
    elif mode == 'no_target':
        remove_piece(state, REGION, rc.ARVERNI, rc.CITADEL)
        state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] = None
    seen = agent_for(state, {'decline': True})
    _execute_battle(state, rc.BELGAE, plan(ambush=mode != 'ordinary_battle'))
    assert seen == []


def test_permanent_provincia_fort_is_not_a_removal_candidate():
    state = position(defender=rc.ROMANS, region=rc.PROVINCIA)
    seen = agent_for(state, {'decline': True})
    result = _execute_battle(state, rc.BELGAE,
                            plan(defender=rc.ROMANS, regions=(rc.PROVINCIA,)))
    assert result['executed'] and not result['errors']
    assert not seen and count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.FORT) == 1
    assert validate_state(state) == []


def test_targets_removed_in_combat_are_not_offered(monkeypatch):
    state = position()
    seen = agent_for(state, {'decline': True})
    def combat(board, region, attacker, defender, **kwargs):
        remove_piece(board, region, defender, rc.CITADEL)
        board['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] = None
        return {}
    monkeypatch.setattr('fs_bot.engine.execute.resolve_battle', combat)
    _execute_battle(state, rc.BELGAE, plan())
    assert not seen


def test_fallback_raw_legacy_citadel_without_tribe_can_still_be_declined():
    state = position()
    state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] = None
    response = {'decline': True}
    seen = agent_for(state, response)
    _execute_battle(state, rc.BELGAE, plan())
    assert seen[0]['targets'] == [target(tribe=None)]
    assert count_pieces(state, REGION, rc.ARVERNI, rc.CITADEL) == 1


def test_terminal_inspection_then_decline_reads_live_board():
    from fs_bot.cli.reactive import make_cli_reactive
    state = position()
    request = dict(kind=KIND, region=REGION, attacker=rc.BELGAE,
                   defender=rc.ARVERNI, targets=target_options(state, REGION, rc.ARVERNI))
    output = StringIO()
    before = encode(state)
    response = make_cli_reactive({rc.BELGAE}, StringIO('board\n2\n'), output)(state, rc.BELGAE, request)
    assert response == {'decline': True}
    assert 'after Ambush' in output.getvalue() and rc.TRIBE_SEQUANI in output.getvalue()
    assert encode(state) == before


def test_preview_does_not_consume_live_human_input_or_rng():
    from fs_bot.engine.moves import validate_player_action
    state = position()
    state['decision_agent'] = lambda *args: pytest.fail('Preview consumed live input')
    before = encode({k: v for k, v in state.items() if k != 'decision_agent'})
    assert validate_player_action(state, rc.BELGAE, plan())[0]
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before


def session_for(state, meta=None, log=None):
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.tools.seat_session import SeatSession
    session = SeatSession(state, meta or {'seat': rc.BELGAE},
                          log if log is not None else [], HumanTurnDisplay(StringIO()))
    state['decision_agent'] = lambda board, faction, request: (
        session.reactive(board, faction, request) if request['kind'] == KIND else None)
    return session


def attempt(session, regions=(REGION,)):
    from fs_bot.engine.game_engine import _action_transaction
    def driver(*args):
        pass
    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    with _action_transaction(session.state, driver):
        return execute_decision(session.state, rc.BELGAE,
                                {'player_action': plan(regions=regions)})


@pytest.mark.parametrize('bad', [None, {}, {'target': target(tribe=rc.TRIBE_HELVETII)}])
def test_invalid_durable_response_remains_pending_and_restores_ambush(tmp_path, bad):
    from fs_bot.tools.seat_session import DecisionPending, board_copy
    from fs_bot.state.serialize import save_game, load_game
    state = position()
    session = session_for(state)
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending):
        attempt(session)
    pending = deepcopy(session.data['pending'])
    assert decode(pending['request'])['kind'] == KIND
    assert encode(board_copy(state)) == before
    session.import_inbox({'decision_id': pending['id'], 'response': bad})
    with pytest.raises(DecisionPending):
        attempt(session)
    assert session.error and session.data['pending'] == pending
    assert encode(board_copy(state)) == before
    path = tmp_path / 'ballistae.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session_for(restored, meta, log)
    with pytest.raises(DecisionPending):
        attempt(resumed)
    assert resumed.data['pending'] == pending
    resumed.import_inbox({'decision_id': pending['id'], 'response': {'decline': True}})
    assert attempt(resumed)['executed']
    resumed.finish()
    assert count_pieces(restored, REGION, rc.ARVERNI, rc.CITADEL) == 1
    assert restored['resources'][rc.BELGAE] == 9
    assert validate_state(restored) == []


@pytest.mark.parametrize('first_decline', [False, True])
def test_second_region_pending_retains_first_choice_and_replays(tmp_path, first_decline):
    from fs_bot.tools.seat_session import DecisionPending, board_copy
    from fs_bot.state.serialize import save_game, load_game
    state = position()
    place_piece(state, rc.MANDUBII, rc.BELGAE, rc.WARBAND)
    place_piece(state, rc.MANDUBII, rc.ARVERNI, rc.CITADEL)
    state['tribes'][rc.TRIBE_MANDUBII]['allied_faction'] = rc.ARVERNI
    place_piece(state, rc.MANDUBII, rc.ARVERNI, rc.WARBAND, 4, piece_state=rc.REVEALED)
    origin = decode(encode(state))
    regions = (REGION, rc.MANDUBII)
    session = session_for(state)
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending):
        attempt(session, regions)
    first = deepcopy(session.data['pending'])
    response = {'decline': True} if first_decline else {'target': target()}
    session.import_inbox({'decision_id': first['id'], 'response': response})
    with pytest.raises(DecisionPending):
        attempt(session, regions)
    second = deepcopy(session.data['pending'])
    assert decode(second['request'])['region'] == rc.MANDUBII
    assert len(session.data['journal']) == 1 and first['id'] != second['id']
    assert encode(board_copy(state)) == before
    path = tmp_path / 'second.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session_for(restored, meta, log)
    with pytest.raises(DecisionPending):
        attempt(resumed, regions)
    assert resumed.data['pending'] == second
    resumed.import_inbox({'decision_id': second['id'], 'response': {'decline': True}})
    result = attempt(resumed, regions)
    resumed.finish()
    assert result['executed'] and not result['errors']
    assert restored['resources'][rc.BELGAE] == 8
    assert count_pieces(restored, REGION, rc.ARVERNI, rc.CITADEL) == first_decline
    assert count_pieces(restored, rc.MANDUBII, rc.ARVERNI, rc.CITADEL) == 1
    assert len(log) == 2 and validate_state(restored) == []
    origin['decision_agent'] = lambda board, faction, req: (
        response if req['kind'] == KIND and req['region'] == REGION
        else {'decline': True} if req['kind'] == KIND else None)
    assert execute_decision(origin, rc.BELGAE,
                            {'player_action': plan(regions=regions)}) == result
    assert encode(board_copy(origin)) == encode(board_copy(restored))


def test_borrowed_citadel_keeps_its_physical_owner_and_tribe():
    from fs_bot.battle.combined import combined_force
    from fs_bot.engine.ballistae_choice import remove_after_ambush
    state = position(defender=rc.AEDUI)
    state['decision_agent'] = lambda board, faction, request: {
        'target': target(owner=rc.AEDUI)} if request['kind'] == KIND else None
    with combined_force(state, rc.ARVERNI, {REGION: [rc.AEDUI]},
                        piece_types=(rc.CITADEL,)):
        assert target_options(state, REGION, rc.ARVERNI) == [target(owner=rc.AEDUI)]
        remove_after_ambush(state, REGION, rc.BELGAE, rc.ARVERNI)
    assert count_pieces(state, REGION, rc.AEDUI, rc.CITADEL) == 0
    assert state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] is None
    assert validate_state(state) == []


def test_terminal_can_select_named_target():
    from fs_bot.cli.reactive import make_cli_reactive
    state = position()
    request = dict(kind=KIND, region=REGION, attacker=rc.BELGAE,
                   defender=rc.ARVERNI, targets=target_options(state, REGION, rc.ARVERNI))
    assert make_cli_reactive({rc.BELGAE}, StringIO('1\n'), StringIO())(
        state, rc.BELGAE, request) == {'target': target()}


def test_free_event_ambush_still_asks_the_capability_owner():
    from fs_bot.engine.free_actions import execute_free_action_plan
    state = position()
    state['resources'][rc.BELGAE] = 0
    state['executing_faction'] = rc.AEDUI
    seen = agent_for(state, {'decline': True})
    result = execute_free_action_plan(state, rc.BELGAE,
        {'request_type': 'event_command', 'morasses_ambush': True}, plan())
    assert result['executed'] and not result['errors']
    assert len(seen) == 1 and seen[0]['attacker'] == rc.BELGAE
    assert state['resources'][rc.BELGAE] == 0
    assert count_pieces(state, REGION, rc.ARVERNI, rc.CITADEL) == 1


def test_durable_explicit_default_removes_once():
    from fs_bot.tools.seat_session import DecisionPending
    state = position()
    session = session_for(state)
    with pytest.raises(DecisionPending):
        attempt(session)
    pending = session.data['pending']
    session.import_inbox({'decision_id': pending['id'], 'response': {'use_default': True}})
    assert attempt(session)['executed']
    session.finish()
    assert len(session.log) == 1
    assert count_pieces(state, REGION, rc.ARVERNI, rc.CITADEL) == 0
    assert state['resources'][rc.BELGAE] == 9
    assert validate_state(state) == []
