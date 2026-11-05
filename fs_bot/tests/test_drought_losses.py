"""Card 49/Tips: each physical owner chooses one exact loss in each Region."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, remove_piece, count_pieces, count_pieces_by_state
from fs_bot.cards.card_effects import execute_event, _ally_tribe
from fs_bot.engine.execute import _execute_event
from fs_bot.engine.moves import validate_player_action
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import encode, decode, save_game, load_game

REGION = rc.SEQUANI
SEATS = [(scenario, faction) for scenario, factions in (
    (rc.SCENARIO_GREAT_REVOLT, (rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE)),
    (rc.SCENARIO_ARIOVISTUS, (rc.ROMANS, rc.AEDUI, rc.BELGAE, rc.GERMANS))) for faction in factions]


def position(scenario=rc.SCENARIO_GREAT_REVOLT, seed=11):
    state = build_initial_state(scenario, seed=seed)
    state['non_player_factions'] = set()
    state['current_card'], state['next_card'] = 49, 50
    state['executing_faction'] = rc.AEDUI
    state['event_params'] = {'devastate_region': REGION}
    state['resources'][rc.ROMANS] = 25
    return state


def soft(piece, ps): return {'piece_type': piece, 'piece_state': ps}


def req(state, faction=rc.ROMANS, region=REGION):
    from fs_bot.cards.drought import request_for
    return request_for(state, region, faction)


def owner_agent(state, owner, target):
    seen = []
    def agent(board, faction, request):
        if request['kind'] == 'drought_loss' and faction == owner:
            assert request['faction'] == owner
            seen.append(deepcopy(request))
            return {'piece': target}
        return None
    state['decision_agent'] = agent
    return seen


def action(params):
    return {'command': rc.FIRST_DID_EVENT, 'regions': [], 'sa': 'No SA', 'sa_regions': [],
            'details': {'card_id': 49, 'text_preference': rc.EVENT_UNSHADED, 'event_params': params}}


@pytest.mark.parametrize('scenario,faction', SEATS)
@pytest.mark.parametrize('visibility', [rc.HIDDEN, rc.REVEALED, rc.SCOUTED])
def test_owner_selects_exact_physical_visibility(scenario, faction, visibility):
    state = position(scenario)
    piece = rc.AUXILIA if faction == rc.ROMANS else rc.WARBAND
    for ps in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        place_piece(state, REGION, faction, piece, 2, piece_state=ps)
    seen = owner_agent(state, faction, soft(piece, visibility))
    execute_event(state, 49)
    assert len(seen) == 1
    for ps in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        assert count_pieces_by_state(state, REGION, faction, piece, ps) == 2 - (ps == visibility)
    assert state['resources'][rc.ROMANS] == 12 and validate_state(state) == []


@pytest.mark.parametrize('tribe', [rc.TRIBE_SEQUANI, rc.TRIBE_HELVETII])
def test_owner_selects_named_ally_without_clearing_another_tribe(tribe):
    state = position()
    assert _ally_tribe(state, rc.TRIBE_SEQUANI, rc.ARVERNI)
    assert _ally_tribe(state, rc.TRIBE_HELVETII, rc.ARVERNI)
    seen = owner_agent(state, rc.ARVERNI, {'piece_type': rc.ALLY, 'tribe': tribe})
    execute_event(state, 49)
    assert seen and state['tribes'][tribe]['allied_faction'] is None
    other = rc.TRIBE_HELVETII if tribe == rc.TRIBE_SEQUANI else rc.TRIBE_SEQUANI
    assert state['tribes'][other]['allied_faction'] == rc.ARVERNI
    assert count_pieces(state, REGION, rc.ARVERNI, rc.ALLY) == 1 and validate_state(state) == []


def test_owner_can_select_legion_to_fallen_instead_of_auxilia():
    state = position()
    place_piece(state, REGION, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(state, REGION, rc.ROMANS, rc.AUXILIA)
    seen = owner_agent(state, rc.ROMANS, {'piece_type': rc.LEGION})
    execute_event(state, 49)
    assert seen and state['fallen_legions'] == 1
    assert count_pieces(state, REGION, rc.ROMANS, rc.AUXILIA) == 1
    assert validate_state(state) == []


@pytest.mark.parametrize('piece', [rc.LEADER, rc.FORT])
def test_roman_owner_can_sacrifice_leader_or_nonpermanent_fort(piece):
    state = position(); place_piece(state, REGION, rc.ROMANS, rc.AUXILIA)
    fields = {'leader_name': rc.CAESAR} if piece == rc.LEADER else {}
    place_piece(state, REGION, rc.ROMANS, piece, **fields)
    seen = owner_agent(state, rc.ROMANS, dict(piece_type=piece, **fields))
    execute_event(state, 49)
    assert seen and count_pieces(state, REGION, rc.ROMANS, piece) == 0
    assert count_pieces(state, REGION, rc.ROMANS, rc.AUXILIA) == 1
    assert validate_state(state) == []


def test_citadel_selection_clears_its_city_without_touching_adjacent_ally():
    state = position(); place_piece(state, REGION, rc.ARVERNI, rc.CITADEL)
    state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] = rc.ARVERNI
    assert _ally_tribe(state, rc.TRIBE_HELVETII, rc.ARVERNI)
    owner_agent(state, rc.ARVERNI, {'piece_type': rc.CITADEL, 'tribe': rc.TRIBE_SEQUANI})
    execute_event(state, 49)
    assert state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] is None
    assert state['tribes'][rc.TRIBE_HELVETII]['allied_faction'] == rc.ARVERNI
    assert validate_state(state) == []


def test_expansion_german_may_choose_settlement_and_aedui_leader_leaves_play():
    state = position(rc.SCENARIO_ARIOVISTUS)
    place_piece(state, REGION, rc.GERMANS, rc.SETTLEMENT)
    place_piece(state, REGION, rc.GERMANS, rc.WARBAND)
    owner_agent(state, rc.GERMANS, {'piece_type': rc.SETTLEMENT})
    execute_event(state, 49)
    assert count_pieces(state, REGION, rc.GERMANS, rc.SETTLEMENT) == 0
    assert count_pieces(state, REGION, rc.GERMANS, rc.WARBAND) == 1
    state = position(rc.SCENARIO_ARIOVISTUS)
    place_piece(state, REGION, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    owner_agent(state, rc.AEDUI, {'piece_type': rc.LEADER, 'leader_name': rc.DIVICIACUS})
    execute_event(state, 49)
    assert not state['diviciacus_in_play'] and state['removed_pieces'][rc.AEDUI][rc.LEADER] == 1
    assert validate_state(state) == []


@pytest.mark.parametrize('response', [None, {}, {'decline': True}, {'use_default': 1},
    {'piece': {}}, {'piece': {'piece_type': rc.LEGION}},
    {'piece': soft(rc.AUXILIA, rc.SCOUTED)}, {'piece': soft(rc.WARBAND, rc.HIDDEN)},
    {'piece': dict(soft(rc.AUXILIA, rc.HIDDEN), count=2)},
    {'piece': {'piece_type': rc.LEADER, 'leader_name': rc.CAESAR}},
    {'piece': {'piece_type': rc.ALLY, 'tribe': rc.TRIBE_SEQUANI}}])
def test_malformed_wrong_owner_or_unavailable_target_is_pure(response):
    from fs_bot.cards.drought import validate_response
    state = position(); place_piece(state, REGION, rc.ROMANS, rc.AUXILIA)
    before = encode(state)
    with pytest.raises(ValueError): validate_response(state, req(state), response)
    assert encode(state) == before


@pytest.mark.parametrize('params', [
    {'devastate_region': rc.CISALPINA}, {'devastate_region': []},
    {'devastate_region': REGION, 'piece_removals': {rc.ROMANS: rc.LEGION}},
    {'devastate_region': REGION, 'piece_removals': {(rc.ROMANS, REGION): rc.LEGION}},
    {'devastate_region': REGION, 'unknown': 1},
])
def test_invalid_marker_or_executor_override_is_atomic(params):
    state = position(); before = encode(state)
    ok, _ = validate_player_action(state, rc.AEDUI, action(params))
    assert not ok and encode(state) == before
    result = _execute_event(state, rc.AEDUI, action(params), human=True)
    assert not result['executed'] and result['rejected'] and encode(state) == before


def test_marker_cannot_be_replaced_in_already_devastated_region():
    state = position(); state['markers'][REGION] = {rc.MARKER_DEVASTATED: True}
    before = encode(state)
    with pytest.raises(ValueError): execute_event(state, 49)
    assert encode(state) == before


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
def test_german_warbands_block_allied_tribe_sacrifice_even_for_human(scenario):
    state = position(scenario); place_piece(state, REGION, rc.GERMANS, rc.WARBAND)
    assert _ally_tribe(state, rc.TRIBE_HELVETII, rc.GERMANS)
    assert {'piece_type': rc.ALLY, 'tribe': rc.TRIBE_HELVETII} not in req(state, rc.GERMANS)['targets']
    if scenario == rc.SCENARIO_ARIOVISTUS:
        owner_agent(state, rc.GERMANS, {'piece_type': rc.ALLY, 'tribe': rc.TRIBE_HELVETII})
        from fs_bot.tools.seat_session import board_copy
        before = encode(board_copy(state))
        with pytest.raises(ValueError): execute_event(state, 49)
        assert encode(board_copy(state)) == before
    else:
        state['decision_agent'] = lambda *a: pytest.fail('Game-run Germans are automatic')
        execute_event(state, 49)
        assert state['tribes'][rc.TRIBE_HELVETII]['allied_faction'] == rc.GERMANS


def test_game_run_arverni_in_expansion_never_receives_human_request():
    state = position(rc.SCENARIO_ARIOVISTUS)
    place_piece(state, REGION, rc.ARVERNI, rc.WARBAND)
    state['decision_agent'] = lambda *a: pytest.fail('Game-run Arverni are automatic')
    execute_event(state, 49)
    assert count_pieces(state, REGION, rc.ARVERNI, rc.WARBAND) == 0


@pytest.mark.parametrize('response', [None, {'use_default': True}])
def test_default_roman_loss_preserves_legion_and_hidden_auxilia(response):
    state = position()
    place_piece(state, REGION, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(state, REGION, rc.ROMANS, rc.AUXILIA)
    place_piece(state, REGION, rc.ROMANS, rc.AUXILIA, piece_state=rc.SCOUTED)
    state['decision_agent'] = lambda *a: response
    execute_event(state, 49)
    assert count_pieces(state, REGION, rc.ROMANS, rc.LEGION) == 1 and state['fallen_legions'] == 0
    assert count_pieces_by_state(state, REGION, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 1
    assert count_pieces_by_state(state, REGION, rc.ROMANS, rc.AUXILIA, rc.SCOUTED) == 0


def test_default_saves_city_ally_and_randomizes_equal_noncity_tribes_deterministically():
    from fs_bot.cards.drought import default_target
    state = position(); assert _ally_tribe(state, rc.TRIBE_SEQUANI, rc.ARVERNI)
    assert _ally_tribe(state, rc.TRIBE_HELVETII, rc.ARVERNI)
    assert default_target(state, req(state, rc.ARVERNI)) == {'piece_type': rc.ALLY, 'tribe': rc.TRIBE_HELVETII}
    state = position(); state['event_params'] = {'devastate_region': rc.MANDUBII}
    assert _ally_tribe(state, rc.TRIBE_SENONES, rc.ARVERNI)
    assert _ally_tribe(state, rc.TRIBE_LINGONES, rc.ARVERNI)
    origin = deepcopy(state)
    execute_event(state, 49); execute_event(origin, 49)
    assert encode(state) == encode(origin) and validate_state(state) == []


def test_permanent_fort_is_never_offered_and_does_not_protect_other_piece():
    state = position(); state['event_params'] = {'devastate_region': rc.PROVINCIA}
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    assert req(state, region=rc.PROVINCIA)['targets'] == []
    execute_event(state, 49)
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.FORT) == 1
    state = position(); state['event_params'] = {'devastate_region': rc.PROVINCIA}
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA)
    execute_event(state, 49)
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.FORT) == 1
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 0


def test_preview_does_not_consult_live_owners_or_consume_rng():
    state = position(); place_piece(state, REGION, rc.ROMANS, rc.AUXILIA)
    state['decision_agent'] = lambda *a: pytest.fail('Preview consumed input')
    from fs_bot.tools.seat_session import board_copy
    before = encode(board_copy(state))
    assert validate_player_action(state, rc.AEDUI, action(state['event_params']))[0]
    sim = deepcopy(board_copy(state)); sim['_diviciacus_preview'] = True; sim['decision_agent'] = state['decision_agent']
    execute_event(sim, 49)
    assert encode(board_copy(state)) == before


def test_terminal_selects_named_ally_and_allows_board_inspection():
    from fs_bot.cli.reactive import make_cli_reactive
    state = position(); assert _ally_tribe(state, rc.TRIBE_SEQUANI, rc.ARVERNI)
    assert _ally_tribe(state, rc.TRIBE_HELVETII, rc.ARVERNI)
    before = encode(state); output = StringIO()
    response = make_cli_reactive({rc.ARVERNI}, StringIO(f'board\nAlly ({rc.TRIBE_HELVETII})\n'), output)(
        state, rc.ARVERNI, req(state, rc.ARVERNI))
    assert response == {'piece': {'piece_type': rc.ALLY, 'tribe': rc.TRIBE_HELVETII}}
    assert encode(state) == before and 'Drought casualty' in output.getvalue()


def test_terminal_eof_restores_resources_marker_and_all_losses():
    from fs_bot.cli.reactive import make_cli_reactive
    from fs_bot.tools.seat_session import board_copy
    state = position(); place_piece(state, REGION, rc.ROMANS, rc.AUXILIA)
    before = encode(state); state['decision_agent'] = make_cli_reactive({rc.ROMANS}, StringIO(), StringIO())
    with pytest.raises(EOFError): execute_event(state, 49)
    assert encode(board_copy(state)) == before


@pytest.mark.parametrize('bad', [None, {}, {'piece': {'piece_type': rc.LEGION}}])
def test_second_region_pending_keeps_earlier_choice_save_resume_and_identical_replay(tmp_path, bad):
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.tools.seat_session import SeatSession, DecisionPending, board_copy
    state = position(); state['markers'][rc.MANDUBII] = {rc.MARKER_DEVASTATED: True}
    for region in (REGION, rc.MANDUBII):
        place_piece(state, region, rc.ROMANS, rc.AUXILIA)
        place_piece(state, region, rc.ROMANS, rc.AUXILIA, piece_state=rc.REVEALED)
    origin = deepcopy(state); before = encode(state)
    def session_for(board, meta=None, log=None):
        session = SeatSession(board, meta or {'seat': rc.ROMANS}, log if log is not None else [], HumanTurnDisplay(StringIO()))
        board['decision_agent'] = session.reactive
        return session
    def attempt(session):
        def driver(*a): pass
        driver.transaction_checkpoint = session.checkpoint; driver.transaction_restore = session.restore
        with _action_transaction(session.state, driver):
            return _execute_event(session.state, rc.AEDUI, action(session.state['event_params']), human=True)
    session = session_for(state)
    with pytest.raises(DecisionPending): attempt(session)
    first = deepcopy(session.data['pending'])
    answer = {'piece': soft(rc.AUXILIA, rc.REVEALED)}
    session.import_inbox({'decision_id': first['id'], 'response': answer})
    with pytest.raises(DecisionPending): attempt(session)
    pending = deepcopy(session.data['pending'])
    assert pending['id'] != first['id'] and len(session.data['journal']) == 1
    assert decode(pending['request'])['region'] != decode(first['request'])['region']
    assert encode(board_copy(state)) == before
    session.import_inbox({'decision_id': pending['id'], 'response': bad})
    with pytest.raises(DecisionPending): attempt(session)
    assert session.data['pending'] == pending and len(session.data['journal']) == 1
    path = tmp_path / 'drought.json'; save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True); resumed = session_for(restored, meta, log)
    resumed.import_inbox({'decision_id': pending['id'], 'response': answer})
    result = attempt(resumed); resumed.finish(); assert result['executed']
    assert restored['resources'][rc.ROMANS] == 12
    for region in (REGION, rc.MANDUBII):
        assert count_pieces_by_state(restored, region, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 1
        assert count_pieces_by_state(restored, region, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 0
    replay = session_for(origin)
    replay.data['queue'] = [SeatSession._inbox_entry(e) for e in resumed.log]
    replay.data['expected'] = [
        {'id': e['assistant_id'], 'signature': e['assistant_signature'], 'request': e['assistant_request'],
         'action_windows_version': e.get('assistant_action_windows_version', 0)} for e in resumed.log]
    assert attempt(replay) == result
    replay.finish()
    assert replay.log == resumed.log and encode(board_copy(origin)) == encode(board_copy(restored))
    assert validate_state(restored) == []


@pytest.mark.parametrize('faction', [rc.ARVERNI, rc.AEDUI, rc.BELGAE, rc.GERMANS])
def test_default_soft_loss_removes_scouted_before_hidden(faction):
    state = position(rc.SCENARIO_ARIOVISTUS if faction == rc.GERMANS else rc.SCENARIO_GREAT_REVOLT)
    for ps in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        place_piece(state, REGION, faction, rc.WARBAND, piece_state=ps)
    execute_event(state, 49)
    assert count_pieces_by_state(state, REGION, faction, rc.WARBAND, rc.HIDDEN) == 1
    assert count_pieces_by_state(state, REGION, faction, rc.WARBAND, rc.REVEALED) == 1
    assert count_pieces_by_state(state, REGION, faction, rc.WARBAND, rc.SCOUTED) == 0


def test_german_owner_can_select_exact_ally_when_no_warbands_remain():
    state = position(rc.SCENARIO_ARIOVISTUS)
    assert _ally_tribe(state, rc.TRIBE_SEQUANI, rc.GERMANS)
    assert _ally_tribe(state, rc.TRIBE_HELVETII, rc.GERMANS)
    owner_agent(state, rc.GERMANS, {'piece_type': rc.ALLY, 'tribe': rc.TRIBE_SEQUANI})
    execute_event(state, 49)
    assert state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] is None
    assert state['tribes'][rc.TRIBE_HELVETII]['allied_faction'] == rc.GERMANS
    assert validate_state(state) == []


def test_terminal_marker_menu_excludes_already_devastated_and_nonplayable_regions():
    from fs_bot.cli.human_plan import _collect_event_params
    state = position(rc.SCENARIO_ARIOVISTUS)
    state['markers'][rc.MORINI] = {rc.MARKER_DEVASTATED: True}
    output = StringIO(); before = encode(state)
    result = _collect_event_params(state, rc.AEDUI, 49, False,
                                  StringIO(f'{rc.MORINI}\n{REGION}\n'), output)
    assert result == {'devastate_region': REGION}
    assert f') {rc.MORINI}\n' not in output.getvalue() and f') {rc.BRITANNIA}\n' not in output.getvalue()
    assert encode(state) == before


def test_stale_casualty_request_cannot_remove_a_different_visibility():
    from fs_bot.cards.drought import validate_response
    state = position(); place_piece(state, REGION, rc.ROMANS, rc.AUXILIA)
    request = req(state)
    remove_piece(state, REGION, rc.ROMANS, rc.AUXILIA)
    place_piece(state, REGION, rc.ROMANS, rc.AUXILIA, piece_state=rc.REVEALED)
    before = encode(state)
    with pytest.raises(ValueError): validate_response(state, request, {'piece': soft(rc.AUXILIA, rc.HIDDEN)})
    assert encode(state) == before


def test_later_owner_missing_response_rolls_back_earlier_owners_loss():
    state = position()
    place_piece(state, REGION, rc.ROMANS, rc.AUXILIA)
    place_piece(state, REGION, rc.AEDUI, rc.WARBAND)
    from fs_bot.tools.seat_session import board_copy
    before = encode(state); asked = []
    def agent(board, faction, request):
        asked.append(faction)
        if faction == rc.ROMANS:
            return {'piece': soft(rc.AUXILIA, rc.HIDDEN)}
        assert count_pieces(board, REGION, rc.ROMANS, rc.AUXILIA) == 0
        raise EOFError('Aedui casualty still pending')
    state['decision_agent'] = agent
    with pytest.raises(EOFError): execute_event(state, 49)
    assert asked == [rc.ROMANS, rc.AEDUI] and encode(board_copy(state)) == before
