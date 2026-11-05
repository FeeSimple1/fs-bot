"""§4.5.2 assigns exact Rampage pieces and dispositions to their owner."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece, remove_piece
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.commands.common import CommandError
from fs_bot.commands.sa_rampage import rampage
from fs_bot.engine.execute import _execute_rampage
from fs_bot.engine.game_engine import _action_transaction
from fs_bot.engine.rampage_choices import validate_response, victim_pieces
from fs_bot.state.serialize import encode, decode, save_game, load_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy

ORIGIN, DESTINATION = rc.NERVII, rc.ATREBATES


def position(scenario=rc.SCENARIO_GREAT_REVOLT):
    state = build_initial_state(scenario, seed=43)
    state['non_player_factions'] = {rc.BELGAE, rc.AEDUI, rc.ARVERNI, rc.GERMANS}
    leader = rc.BODUOGNATUS if scenario in rc.ARIOVISTUS_SCENARIOS else rc.AMBIORIX
    place_piece(state, ORIGIN, rc.BELGAE, rc.LEADER, leader_name=leader)
    place_piece(state, ORIGIN, rc.BELGAE, rc.WARBAND, 4)
    place_piece(state, ORIGIN, rc.ROMANS, rc.LEGION, 2, from_legions_track=True)
    for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        place_piece(state, ORIGIN, rc.ROMANS, rc.AUXILIA, 2, piece_state=visibility)
    place_piece(state, DESTINATION, rc.ROMANS, rc.AUXILIA)
    return state


def action(count=2, region=ORIGIN, target=rc.ROMANS):
    return {'command': rc.CMD_RALLY, 'sa': rc.SA_RAMPAGE,
            'sa_regions': [{'region': region, 'target': target, 'count': count}]}


def piece(kind=rc.AUXILIA, visibility=rc.REVEALED, disposition='remove'):
    return {'action': disposition, 'piece_type': kind, 'piece_state': visibility}


def mixed():
    return {'actions': [piece(rc.LEGION, None), piece(disposition='retreat')],
            'retreat_region': DESTINATION}


def request(state, count=2):
    return {'kind': 'retreat', 'region': ORIGIN, 'attacker': rc.BELGAE,
            'defender': rc.ROMANS, 'is_ambush': False,
            'legal_regions': [DESTINATION], 'context': {'rampage': True, 'num_pieces': count},
            'pieces': victim_pieces(state, ORIGIN, rc.ROMANS)}


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
def test_target_selects_legion_removal_and_revealed_auxilia_retreat(scenario):
    state = position(scenario)
    before_rng = state['rng'].getstate()
    seen = []
    state['decision_agent'] = lambda board, faction, prompt: seen.append((faction, prompt)) or mixed()
    result = _execute_rampage(state, rc.BELGAE, action())
    assert result['executed'] and not result['errors']
    assert len(seen) == 1 and seen[0][0] == rc.ROMANS and seen[0][1]['pieces']
    assert state['fallen_legions'] == 1
    assert count_pieces(state, ORIGIN, rc.ROMANS, rc.LEGION) == 1
    assert count_pieces_by_state(state, ORIGIN, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 2
    assert count_pieces_by_state(state, ORIGIN, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 1
    assert count_pieces_by_state(state, DESTINATION, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 1
    assert count_pieces_by_state(state, ORIGIN, rc.BELGAE, rc.WARBAND, rc.HIDDEN) == 2
    assert state['rng'].getstate() == before_rng and validate_state(state) == []


@pytest.mark.parametrize('visibility', [rc.HIDDEN, rc.REVEALED, rc.SCOUTED])
@pytest.mark.parametrize('disposition', ['remove', 'retreat'])
def test_exact_visibility_is_never_substituted(visibility, disposition):
    state = position()
    response = {'actions': [piece(visibility=visibility, disposition=disposition)],
                'retreat_region': DESTINATION if disposition == 'retreat' else None}
    state['decision_agent'] = lambda *args: response
    result = _execute_rampage(state, rc.BELGAE, action(1))
    assert result['executed']
    for ps in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        assert count_pieces_by_state(state, ORIGIN, rc.ROMANS, rc.AUXILIA, ps) == (1 if ps == visibility else 2)
    assert validate_state(state) == []


BAD = [None, {}, {'retreat': False}, {'use_default': 1},
       {'actions': [], 'retreat_region': None},
       {'actions': [piece()], 'retreat_region': None},
       {'actions': [piece(rc.ALLY, None), piece()], 'retreat_region': None},
       {'actions': [piece(visibility=None), piece()], 'retreat_region': None},
       {'actions': [piece(disposition='stay'), piece()], 'retreat_region': None},
       {'actions': [piece(disposition='retreat'), piece()], 'retreat_region': rc.UBII},
       {'actions': [piece(), piece()], 'retreat_region': DESTINATION},
       {'actions': [dict(piece(), count=1), piece()], 'retreat_region': None},
       {'actions': [piece(visibility=[]), piece()], 'retreat_region': None},
       {'actions': [piece(disposition='retreat'), piece()], 'retreat_region': None}]


@pytest.mark.parametrize('bad', BAD)
def test_invalid_fresh_response_stays_pending_without_flips_or_casualties(bad):
    session = session_for(position())
    before = encode(board_copy(session.state))
    with pytest.raises(DecisionPending):
        attempt(session)
    pending = deepcopy(session.data['pending'])
    session.import_inbox({'decision_id': pending['id'], 'response': bad})
    with pytest.raises(DecisionPending):
        attempt(session)
    assert session.error and session.data['pending'] == pending
    assert not session.data['journal'] and encode(board_copy(session.state)) == before


def test_duplicate_physical_cohort_is_rejected_before_mutation():
    state = position()
    prompt = request(state, count=3)
    before = encode(state)
    with pytest.raises(ValueError):
        validate_response(state, prompt, {'actions': [piece()] * 3, 'retreat_region': None})
    with pytest.raises(CommandError):
        rampage(state, ORIGIN, rc.ROMANS, 3, [piece()] * 3)
    assert encode(state) == before


def test_low_level_checks_complete_plan_before_any_belgic_flip():
    state = position()
    before = encode(state)
    with pytest.raises(CommandError):
        rampage(state, ORIGIN, rc.ROMANS, 2, [piece(), piece(rc.ALLY, None)])
    assert encode(state) == before
    with pytest.raises(CommandError):
        rampage(state, ORIGIN, rc.ROMANS, 2, [dict(piece(disposition='retreat'), retreat_region=DESTINATION),
                                             dict(piece(disposition='retreat'), retreat_region=rc.MORINI)])
    assert encode(state) == before


@pytest.mark.parametrize('scenario', (rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS))
@pytest.mark.parametrize('host', [rc.AEDUI, rc.GERMANS, rc.ARVERNI])
def test_host_consent_is_asked_once_and_destination_restrictions_apply(scenario, host):
    state = position(scenario)
    remove_piece(state, DESTINATION, rc.ROMANS, rc.AUXILIA)
    place_piece(state, DESTINATION, host, rc.WARBAND, 3)
    state['non_player_factions'].discard(host)
    seen = []

    def choose(board, faction, prompt):
        seen.append((faction, prompt))
        if prompt['kind'] == 'agreement':
            return True
        if DESTINATION in prompt['legal_regions']:
            return mixed()
        return {'actions': [piece(), piece(rc.LEGION, None)], 'retreat_region': None}

    state['decision_agent'] = choose
    result = _execute_rampage(state, rc.BELGAE, action())
    assert result['executed'] and not result['errors']
    permitted = host != rc.GERMANS and not (host == rc.ARVERNI and scenario in rc.ARIOVISTUS_SCENARIOS)
    agreements = [prompt for _, prompt in seen if prompt['kind'] == 'agreement']
    assert len(agreements) == int(permitted)
    victim = [prompt for faction, prompt in seen if faction == rc.ROMANS][0]
    assert (DESTINATION in victim['legal_regions']) is permitted
    assert count_pieces(state, DESTINATION, rc.ROMANS, rc.AUXILIA) == int(permitted)
    assert validate_state(state) == []


def test_no_control_destination_is_rejected_by_low_level_api():
    state = position()
    remove_piece(state, DESTINATION, rc.ROMANS, rc.AUXILIA)
    before = encode(state)
    with pytest.raises(CommandError):
        rampage(state, ORIGIN, rc.ROMANS, 1, [dict(piece(disposition='retreat'), retreat_region=DESTINATION)])
    assert encode(state) == before


def test_expansion_arverni_are_forced_to_remove_without_human_prompts():
    state = position(rc.SCENARIO_ARIOVISTUS)
    for ps in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        place_piece(state, ORIGIN, rc.ARVERNI, rc.WARBAND, piece_state=ps)
    seen = []
    state['decision_agent'] = lambda *args: seen.append(args)
    result = _execute_rampage(state, rc.BELGAE, action(2, target=rc.ARVERNI))
    assert result['executed'] and not seen
    assert count_pieces_by_state(state, ORIGIN, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 1
    assert count_pieces_by_state(state, ORIGIN, rc.ARVERNI, rc.WARBAND, rc.REVEALED) == 0
    assert count_pieces_by_state(state, ORIGIN, rc.ARVERNI, rc.WARBAND, rc.SCOUTED) == 0


def test_terminal_can_mix_removal_and_retreat_with_board_inspection():
    state = position()
    output = StringIO()
    # Pool is two Scouted, two Revealed, two Hidden Auxilia, then two Legions.
    state['decision_agent'] = make_cli_reactive({rc.ROMANS}, StringIO('board\n7\n1\n3\n2\n1\n'), output)
    result = _execute_rampage(state, rc.BELGAE, action())
    assert result['executed'] and not result['errors']
    assert state['fallen_legions'] == 1
    assert count_pieces_by_state(state, DESTINATION, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 1
    assert all(word in output.getvalue() for word in ('Hidden', 'Revealed', 'Scouted', 'Legion'))
    assert 'Shared Retreat destination' in output.getvalue()


def session_for(state, meta=None, log=None):
    session = SeatSession(state, meta if meta is not None else {'seat': rc.ROMANS},
                          log if log is not None else [], HumanTurnDisplay(StringIO()))
    state['decision_agent'] = session.reactive
    return session


def attempt(session, plan=None):
    def driver(*args):
        pass
    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    with _action_transaction(session.state, driver):
        return _execute_rampage(session.state, rc.BELGAE, action() if plan is None else plan)


@pytest.mark.parametrize('stale', [False, True])
def test_recorded_legacy_pending_prompt_finishes_only_on_saved_board(tmp_path, monkeypatch, stale):
    from fs_bot.tools import seat_session
    session = session_for(position())
    original = SeatSession.ask

    def old_ask(current, state, faction, prompt):
        if prompt.get('context', {}).get('rampage'):
            prompt = {key: value for key, value in prompt.items() if key != 'pieces'}
        return original(current, state, faction, prompt)

    with monkeypatch.context() as patch:
        patch.setattr(seat_session.SeatSession, 'ask', old_ask)
        with pytest.raises(DecisionPending):
            attempt(session)
    pending = deepcopy(session.data['pending'])
    assert 'pieces' not in decode(pending['request'])
    path = tmp_path / 'old-rampage.json'
    save_game(session.state, path, meta=session.meta, log=session.log)
    state, meta, log = load_game(path, validate=True)
    resumed = session_for(state, meta, log)
    if stale:
        state['resources'][rc.ROMANS] += 1
    resumed.import_inbox({'decision_id': pending['id'], 'response': {'retreat': False}})
    if stale:
        with pytest.raises(DecisionPending):
            attempt(resumed)
        assert 'pieces' in decode(resumed.data['pending']['request'])
        return
    result = attempt(resumed)
    resumed.finish()
    assert result['executed'] and len(log) == 1
    assert state['fallen_legions'] == 0
    assert count_pieces_by_state(state, ORIGIN, rc.ROMANS, rc.AUXILIA, rc.SCOUTED) == 0
    assert decode(log[0]['assistant_response']) == {'retreat': False}
    replay = session_for(position())
    replay.data['expected'] = [{'id': row['assistant_id'], 'signature': row['assistant_signature'],
                                'request': row['assistant_request']} for row in log]
    replay.data['queue'] = [SeatSession._inbox_entry(row) for row in log]
    assert attempt(replay) == result
    replay.finish()
    assert encode(board_copy(replay.state)) == encode(board_copy(state))


def test_second_region_pause_retains_first_mixed_choice_across_save_resume(tmp_path):
    state = position()
    second = rc.MORINI
    place_piece(state, second, rc.BELGAE, rc.WARBAND, 2)
    place_piece(state, second, rc.ROMANS, rc.AUXILIA, 2)
    plan = action()
    plan['sa_regions'].append({'region': second, 'target': rc.ROMANS, 'count': 1})
    session = session_for(state)
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending):
        attempt(session, plan)
    first = deepcopy(session.data['pending'])
    session.import_inbox({'decision_id': first['id'], 'response': mixed()})
    with pytest.raises(DecisionPending):
        attempt(session, plan)
    pending = deepcopy(session.data['pending'])
    assert pending['id'] != first['id'] and len(session.data['journal']) == 1
    assert encode(board_copy(state)) == before
    path = tmp_path / 'two-regions.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session_for(restored, meta, log)
    resumed.import_inbox({'decision_id': pending['id'], 'response': {
        'actions': [piece(visibility=rc.HIDDEN)], 'retreat_region': None}})
    result = attempt(resumed, plan)
    resumed.finish()
    assert result['executed'] and len(result['rampages']) == 2 and len(log) == 2
    assert restored['fallen_legions'] == 1
    assert count_pieces(restored, second, rc.ROMANS, rc.AUXILIA) == 1
    replay = session_for(position())
    place_piece(replay.state, second, rc.BELGAE, rc.WARBAND, 2)
    place_piece(replay.state, second, rc.ROMANS, rc.AUXILIA, 2)
    replay.data['expected'] = [{'id': row['assistant_id'], 'signature': row['assistant_signature'],
                                'request': row['assistant_request']} for row in log]
    replay.data['queue'] = [SeatSession._inbox_entry(row) for row in log]
    assert attempt(replay, plan) == result
    replay.finish()
    assert encode(board_copy(replay.state)) == encode(board_copy(restored))
    assert validate_state(restored) == []


@pytest.mark.parametrize('mode', ['npc', 'raw_legacy', 'delegate'])
def test_established_default_subset_and_retreat_policy_remain_supported(mode):
    state = position()
    if mode == 'npc':
        state['non_player_factions'].add(rc.ROMANS)
    else:
        state['decision_agent'] = lambda *args: {'retreat': False} if mode == 'raw_legacy' else {'use_default': True}
    result = _execute_rampage(state, rc.BELGAE, action())
    assert result['executed'] and not result['errors']
    assert state['fallen_legions'] == 0
    assert count_pieces_by_state(state, ORIGIN, rc.ROMANS, rc.AUXILIA, rc.SCOUTED) == 0
    expected = 0 if mode == 'raw_legacy' else 2
    assert count_pieces_by_state(state, DESTINATION, rc.ROMANS, rc.AUXILIA, rc.SCOUTED) == expected
