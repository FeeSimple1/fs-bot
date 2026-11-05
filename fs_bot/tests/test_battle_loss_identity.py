"""Physical casualties within the mandatory Battle loss tiers (§3.2.4)."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.battle.losses import _build_loss_priority, resolve_losses
from fs_bot.battle.resolve import resolve_battle
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece, remove_piece
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.game_engine import _action_transaction
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy, validate_response

REGION = rc.CARNUTES
SCENARIOS = (rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS)
VISIBILITIES = (rc.HIDDEN, rc.REVEALED, rc.SCOUTED)
CASES = [(scenario, faction, piece) for scenario in SCENARIOS
         for faction, piece in ((rc.ROMANS, rc.AUXILIA), (rc.AEDUI, rc.WARBAND),
                                (rc.BELGAE, rc.WARBAND), (rc.ARVERNI, rc.WARBAND),
                                (rc.GERMANS, rc.WARBAND))
         if (faction != rc.ARVERNI or scenario not in rc.ARIOVISTUS_SCENARIOS)
         and (faction != rc.GERMANS or scenario not in rc.BASE_SCENARIOS)]


def position(scenario=rc.SCENARIO_GREAT_REVOLT, faction=rc.AEDUI, piece=rc.WARBAND):
    state = build_initial_state(scenario, seed=29)
    state['non_player_factions'] = set()
    for visibility in VISIBILITIES:
        place_piece(state, REGION, faction, piece, piece_state=visibility)
    return state


def ally_position(scenario=rc.SCENARIO_GREAT_REVOLT, faction=rc.AEDUI):
    state = build_initial_state(scenario, seed=29)
    state['non_player_factions'] = set()
    for tribe in (rc.TRIBE_CARNUTES, rc.TRIBE_AULERCI):
        place_piece(state, REGION, faction, rc.ALLY)
        state['tribes'][tribe]['allied_faction'] = faction
    return state


@pytest.mark.parametrize('scenario,faction,piece', CASES)
@pytest.mark.parametrize('visibility', VISIBILITIES)
def test_each_human_selects_exact_ordinary_visibility(scenario, faction, piece, visibility):
    state = position(scenario, faction, piece)
    before_rng = state['rng'].getstate()
    requests = []

    def choose(board, owner, request):
        assert owner == faction
        requests.append(request)
        return [(piece, visibility)]

    state['decision_agent'] = choose
    result = resolve_losses(state, REGION, faction, 1)
    assert len(requests) == 1 and result['removed'] == [(piece, 1)]
    assert set(requests[0]['pieces']) == {(piece, ps) for ps in VISIBILITIES}
    for ps in VISIBILITIES:
        assert count_pieces_by_state(state, REGION, faction, piece, ps) == int(ps != visibility)
    assert state['rng'].getstate() == before_rng and validate_state(state) == []


@pytest.mark.parametrize('scenario', SCENARIOS)
@pytest.mark.parametrize('tribe', [rc.TRIBE_CARNUTES, rc.TRIBE_AULERCI])
def test_human_selects_named_ally_and_preserves_other_affiliation(scenario, tribe):
    state = ally_position(scenario)
    seen = []

    def choose(board, faction, request):
        seen.append(request['pieces'])
        return [(rc.ALLY, None, None, tribe)]

    state['decision_agent'] = choose
    result = resolve_losses(state, REGION, rc.AEDUI, 1)
    assert set(seen[0]) == {(rc.ALLY, None, None, t) for t in (rc.TRIBE_CARNUTES, rc.TRIBE_AULERCI)}
    assert result['removed'] == [(rc.ALLY, 1)]
    assert state['tribes'][tribe]['allied_faction'] is None
    other = rc.TRIBE_AULERCI if tribe == rc.TRIBE_CARNUTES else rc.TRIBE_CARNUTES
    assert state['tribes'][other]['allied_faction'] == rc.AEDUI
    assert count_pieces(state, REGION, rc.AEDUI, rc.ALLY) == 1 and validate_state(state) == []


def test_city_citadel_is_not_offered_as_an_ally_disc():
    state = ally_position()
    remove_piece(state, REGION, rc.AEDUI, rc.ALLY)
    place_piece(state, REGION, rc.AEDUI, rc.CITADEL)
    seen = []
    state['decision_agent'] = lambda board, faction, request: seen.append(request['pieces']) or [
        (rc.ALLY, None, None, rc.TRIBE_AULERCI)]
    result = resolve_losses(state, REGION, rc.AEDUI, 1)
    assert seen == [[(rc.ALLY, None, None, rc.TRIBE_AULERCI), (rc.CITADEL, None)]]
    assert result['removed'] == [(rc.ALLY, 1)]
    assert state['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] == rc.AEDUI
    assert state['tribes'][rc.TRIBE_AULERCI]['allied_faction'] is None
    assert validate_state(state) == []


def test_litaviccus_casualty_keeps_owner_and_named_tribe():
    from fs_bot.battle.combined import litaviccus_force
    state = ally_position()
    state['tribes'][rc.TRIBE_AULERCI]['allied_faction'] = rc.BELGAE
    remove_piece(state, REGION, rc.AEDUI, rc.ALLY)
    place_piece(state, REGION, rc.BELGAE, rc.ALLY)
    seen = []

    def choose(board, faction, request):
        assert faction == rc.BELGAE
        seen.append(request['pieces'])
        return [(rc.ALLY, None, rc.AEDUI, rc.TRIBE_CARNUTES)]

    state['decision_agent'] = choose
    with litaviccus_force(state, rc.BELGAE, REGION):
        result = resolve_losses(state, REGION, rc.BELGAE, 1)
    assert (rc.ALLY, None, rc.AEDUI, rc.TRIBE_CARNUTES) in seen[0]
    assert result['removed'] == [(rc.ALLY, 1)]
    assert count_pieces(state, REGION, rc.BELGAE, rc.ALLY) == 1
    assert state['tribes'][rc.TRIBE_AULERCI]['allied_faction'] == rc.BELGAE
    assert state['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] is None
    assert validate_state(state) == []


def test_full_battle_attack_and_counterattack_select_revealed_casualties(monkeypatch):
    from fs_bot.battle import losses
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=29)
    state['non_player_factions'] = set()
    for faction, piece in ((rc.AEDUI, rc.WARBAND), (rc.ROMANS, rc.AUXILIA)):
        for visibility in (rc.HIDDEN, rc.REVEALED):
            place_piece(state, REGION, faction, piece, 2, piece_state=visibility)
    removed = []
    original = losses._remove_battle_piece

    def record(board, region, faction, piece, visibility, owner=None, *, tribe=None):
        removed.append((faction, piece, visibility))
        return original(board, region, faction, piece, visibility, owner, tribe=tribe)

    monkeypatch.setattr(losses, '_remove_battle_piece', record)
    state['decision_agent'] = lambda board, faction, request: [next(
        entry for entry in request['pieces'] if entry[1] == rc.REVEALED)]
    result = resolve_battle(state, REGION, rc.ROMANS, rc.AEDUI, retreat_declaration=False)
    assert removed == [(rc.AEDUI, rc.WARBAND, rc.REVEALED)] * 2 + [(rc.ROMANS, rc.AUXILIA, rc.REVEALED)]
    assert result['attack']['losses_taken'] == 2 and result['counterattack']['losses_taken'] == 1
    assert validate_state(state) == []


def session_for(state, faction=rc.AEDUI, meta=None, log=None):
    session = SeatSession(state, meta if meta is not None else {'seat': faction},
                          log if log is not None else [], HumanTurnDisplay(StringIO()))
    state['decision_agent'] = session.reactive
    return session


def attempt(session, count=2, *, faction=rc.AEDUI, retreat=False):
    def driver(*args):
        pass
    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    with _action_transaction(session.state, driver):
        return resolve_losses(session.state, REGION, faction, count, is_retreat=retreat)


@pytest.mark.parametrize('bad', [None, [[rc.WARBAND, None]], [[rc.WARBAND, rc.SCOUTED]],
                               [[rc.WARBAND, rc.REVEALED]] * 2,
                               [[rc.WARBAND, rc.REVEALED, rc.GERMANS]]])
def test_second_casualty_pause_rejects_stale_choices_and_survives_save_resume(tmp_path, bad):
    session = session_for(position())
    before = encode(board_copy(session.state))
    with pytest.raises(DecisionPending):
        attempt(session)
    first = deepcopy(session.data['pending'])
    session.import_inbox({'decision_id': first['id'], 'response': [[rc.WARBAND, rc.SCOUTED]]})
    with pytest.raises(DecisionPending):
        attempt(session)
    second = deepcopy(session.data['pending'])
    assert second['id'] != first['id'] and len(session.data['journal']) == 1
    assert (rc.WARBAND, rc.SCOUTED) not in decode(second['request'])['pieces']
    session.import_inbox({'decision_id': second['id'], 'response': bad})
    with pytest.raises(DecisionPending):
        attempt(session)
    assert session.error and session.data['pending'] == second
    assert encode(board_copy(session.state)) == before and len(session.data['journal']) == 1
    path = tmp_path / 'casualties.json'
    save_game(session.state, path, meta=session.meta, log=session.log)
    state, meta, log = load_game(path, validate=True)
    resumed = session_for(state, meta=meta, log=log)
    resumed.import_inbox({'decision_id': second['id'], 'response': [[rc.WARBAND, rc.REVEALED]]})
    result = attempt(resumed)
    resumed.finish()
    assert result['losses_taken'] == 2 and len(log) == 2
    assert count_pieces_by_state(state, REGION, rc.AEDUI, rc.WARBAND, rc.HIDDEN) == 1
    assert count_pieces_by_state(state, REGION, rc.AEDUI, rc.WARBAND, rc.REVEALED) == 0
    assert count_pieces_by_state(state, REGION, rc.AEDUI, rc.WARBAND, rc.SCOUTED) == 0
    assert validate_state(state) == []
    replay = session_for(position())
    replay.data['queue'] = [SeatSession._inbox_entry(entry) for entry in log]
    replay.data['expected'] = [{'id': entry['assistant_id'], 'signature': entry['assistant_signature'],
                                'request': entry['assistant_request']} for entry in log]
    assert attempt(replay) == result
    replay.finish()
    assert encode(board_copy(replay.state)) == encode(board_copy(state))


@pytest.mark.parametrize('bad', [
    [[rc.ALLY, None]], [[rc.ALLY, None, None, rc.TRIBE_VENETI]],
    [[rc.ALLY, None, rc.ROMANS, rc.TRIBE_AULERCI]],
    [[rc.ALLY, None, None, rc.TRIBE_CARNUTES]] * 2,
])
def test_fresh_durable_ally_request_rejects_unoffered_or_duplicate_identity(bad):
    session = session_for(ally_position())
    with pytest.raises(DecisionPending):
        attempt(session, 1)
    pending = deepcopy(session.data['pending'])
    session.import_inbox({'decision_id': pending['id'], 'response': bad})
    before = encode(board_copy(session.state))
    with pytest.raises(DecisionPending):
        attempt(session, 1)
    assert session.error and session.data['pending'] == pending
    assert encode(board_copy(session.state)) == before


@pytest.mark.parametrize('stale_board', [False, True])
def test_recorded_legacy_pending_and_accepted_loss_require_the_original_board(tmp_path, monkeypatch, stale_board):
    from fs_bot.battle import losses
    session = session_for(position())
    with monkeypatch.context() as patch:
        patch.setattr(losses, '_human_loss_identities', lambda state, region, faction, choices: choices)
        with pytest.raises(DecisionPending):
            attempt(session)
        first = deepcopy(session.data['pending'])
        session.import_inbox({'decision_id': first['id'], 'response': [[rc.WARBAND, None]]})
        with pytest.raises(DecisionPending):
            attempt(session)
    second = deepcopy(session.data['pending'])
    assert decode(second['request'])['pieces'] == [(rc.WARBAND, None)] * 2
    path = tmp_path / 'legacy-casualties.json'
    save_game(session.state, path, meta=session.meta, log=session.log)
    state, meta, log = load_game(path, validate=True)
    resumed = session_for(state, meta=meta, log=log)
    if stale_board:
        state['resources'][rc.AEDUI] += 1
    resumed.import_inbox({'decision_id': second['id'], 'response': [[rc.WARBAND, None]]})
    if stale_board:
        with pytest.raises(DecisionPending):
            attempt(resumed)
        assert 'no longer matches' in resumed.error
        return
    result = attempt(resumed)
    resumed.finish()
    assert result['losses_taken'] == 2 and len(log) == 2
    assert count_pieces_by_state(state, REGION, rc.AEDUI, rc.WARBAND, rc.SCOUTED) == 1
    assert all(decode(entry['assistant_response']) == [[rc.WARBAND, None]] for entry in log)
    replay = session_for(position())
    replay.data['expected'] = [{'id': entry['assistant_id'], 'signature': entry['assistant_signature'],
                                'request': entry['assistant_request']} for entry in log]
    replay.data['queue'] = [SeatSession._inbox_entry(entry) for entry in log]
    assert attempt(replay) == result
    replay.finish()
    assert encode(board_copy(replay.state)) == encode(board_copy(state))


def test_cli_names_visibility_tribes_and_supports_board_inspection():
    state = position()
    before = encode(state)
    output = StringIO()
    state['decision_agent'] = make_cli_reactive({rc.AEDUI}, StringIO('board\n2\n3\n'), output)
    result = resolve_losses(state, REGION, rc.AEDUI, 1)
    assert result['removed'] == [(rc.WARBAND, 1)]
    assert count_pieces_by_state(state, REGION, rc.AEDUI, rc.WARBAND, rc.REVEALED) == 0
    assert all(visibility in output.getvalue() for visibility in VISIBILITIES)
    allies = ally_position()
    output = StringIO()
    allies['decision_agent'] = make_cli_reactive({rc.AEDUI}, StringIO('board\n2\n2\n'), output)
    resolve_losses(allies, REGION, rc.AEDUI, 1)
    assert rc.TRIBE_CARNUTES in output.getvalue() and rc.TRIBE_AULERCI in output.getvalue()
    assert allies['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] is None
    assert before != encode(board_copy(state))


@pytest.mark.parametrize('retreat', [False, True])
def test_named_ally_cannot_bypass_the_current_loss_tier(retreat):
    state = ally_position()
    place_piece(state, REGION, rc.AEDUI, rc.WARBAND, piece_state=rc.REVEALED)
    requests = []
    state['decision_agent'] = lambda board, faction, request: requests.append(request) or [
        (rc.ALLY, None, None, rc.TRIBE_CARNUTES)]
    resolve_losses(state, REGION, rc.AEDUI, 1, is_retreat=retreat)
    assert {entry[0] for entry in requests[0]['pieces']} == ({rc.ALLY} if retreat else {rc.WARBAND})
    assert count_pieces(state, REGION, rc.AEDUI, rc.WARBAND) == int(retreat)
    assert state['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] == (None if retreat else rc.AEDUI)


@pytest.mark.parametrize('scenario,faction', [
    (rc.SCENARIO_GREAT_REVOLT, rc.GERMANS), (rc.SCENARIO_ARIOVISTUS, rc.ARVERNI),
    (rc.SCENARIO_GREAT_REVOLT, rc.AEDUI), (rc.SCENARIO_ARIOVISTUS, rc.GERMANS),
])
def test_npc_and_game_run_priorities_retain_scouted_first_order(scenario, faction):
    state = position(scenario, faction)
    state['non_player_factions'] = {faction}
    before_rng = state['rng'].getstate()
    assert _build_loss_priority(state, REGION, faction) == [(rc.WARBAND, ps) for ps in reversed(VISIBILITIES)]
    resolve_losses(state, REGION, faction, 1)
    assert count_pieces_by_state(state, REGION, faction, rc.WARBAND, rc.SCOUTED) == 0
    assert state['rng'].getstate() == before_rng


def test_legacy_raw_type_priority_and_unattached_disc_remain_supported():
    state = position()
    resolve_losses(state, REGION, rc.AEDUI, 1, loss_order=[(rc.WARBAND, None)])
    assert count_pieces_by_state(state, REGION, rc.AEDUI, rc.WARBAND, rc.HIDDEN) == 0
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=29)
    place_piece(state, REGION, rc.AEDUI, rc.ALLY)
    assert _build_loss_priority(state, REGION, rc.AEDUI) == [(rc.ALLY, None)]
    assert resolve_losses(state, REGION, rc.AEDUI, 1)['removed'] == [(rc.ALLY, 1)]
