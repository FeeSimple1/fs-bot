"""Mandatory Battle casualty tiers: §§3.2.4/3.3.4 and A3.2.4."""

import copy
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.battle.combined import combined_force
from fs_bot.battle.losses import _build_loss_priority, resolve_losses
from fs_bot.battle.resolve import resolve_battle
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.game_engine import _action_transaction
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


CASES = [
    (scenario, faction, mobile, static)
    for scenario in (rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS)
    for faction, mobile, static in (
        (rc.AEDUI, rc.WARBAND, rc.ALLY),
        (rc.BELGAE, rc.WARBAND, rc.CITADEL),
        (rc.ROMANS, rc.AUXILIA, rc.FORT),
        (rc.GERMANS, rc.WARBAND, rc.SETTLEMENT),
    )
    if static != rc.SETTLEMENT or scenario == rc.SCENARIO_ARIOVISTUS
]


def _state(scenario, faction, mobile, static, *, seed=1):
    state = build_initial_state(scenario, seed=seed)
    state['non_player_factions'] = set()
    place_piece(state, rc.CARNUTES, faction, mobile)
    place_piece(state, rc.CARNUTES, faction, static)
    if static in (rc.ALLY, rc.CITADEL):
        state['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] = faction
    assert validate_state(state) == []
    return state


@pytest.mark.parametrize('scenario,faction,mobile,static', CASES)
@pytest.mark.parametrize('retreat', [False, True])
def test_battle_projection_priority_keeps_later_tiers(
        scenario, faction, mobile, static, retreat):
    state = _state(scenario, faction, mobile, static)
    before = encode(state)
    priority = _build_loss_priority(state, rc.CARNUTES, faction,
                                     is_retreat=retreat)
    expected = [static, mobile] if retreat else [mobile, static]
    assert [entry[0] for entry in priority] == expected
    assert encode(state) == before


@pytest.mark.parametrize('scenario,faction,mobile,static', CASES)
@pytest.mark.parametrize('retreat', [False, True])
def test_raw_callback_cannot_choose_the_later_loss_tier(
        scenario, faction, mobile, static, retreat):
    state = _state(scenario, faction, mobile, static)
    first, later = (static, mobile) if retreat else (mobile, static)
    requests = []

    def choose_later(board, owner, request):
        requests.append(request)
        return [(later, None)]

    state['decision_agent'] = choose_later
    result = resolve_losses(state, rc.CARNUTES, faction, 1, is_retreat=retreat)
    assert {entry[0] for entry in requests[0]['pieces']} == {first}
    assert result['removed'] == [(first, 1)]  # Seed 1 rolls 2 for hard targets.
    assert count_pieces(state, rc.CARNUTES, faction, later) == 1
    assert validate_state(state) == []


@pytest.mark.parametrize('retreat', [False, True])
def test_real_menu_offers_only_the_current_tier(retreat):
    state = _state(rc.SCENARIO_GREAT_REVOLT, rc.AEDUI, rc.WARBAND, rc.ALLY)
    first, later = (rc.ALLY, rc.WARBAND) if retreat else (rc.WARBAND, rc.ALLY)
    output = io.StringIO()
    state['decision_agent'] = make_cli_reactive(
        [rc.AEDUI], io.StringIO('1\n'), output)
    result = resolve_losses(state, rc.CARNUTES, rc.AEDUI, 1, is_retreat=retreat)
    assert first in output.getvalue()
    assert later not in output.getvalue()
    assert result['removed'] == [(first, 1)]
    assert validate_state(state) == []


def _session(state, faction, meta=None, log=None):
    session = SeatSession(state, meta or {'seat': faction},
                          [] if log is None else log, HumanTurnDisplay(io.StringIO()))
    state['decision_agent'] = session.reactive

    def driver(*args):
        pass

    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    return session, driver


@pytest.mark.parametrize('scenario,faction,mobile,static', CASES)
@pytest.mark.parametrize('retreat', [False, True])
def test_saved_pending_loss_rejects_wrong_tier_then_resumes(
        tmp_path, scenario, faction, mobile, static, retreat):
    state = _state(scenario, faction, mobile, static)
    first, later = (static, mobile) if retreat else (mobile, static)
    session, driver = _session(state, faction)
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending):
        with _action_transaction(state, driver):
            resolve_losses(state, rc.CARNUTES, faction, 1, is_retreat=retreat)
    pending = copy.deepcopy(session.data['pending'])
    assert encode(board_copy(state)) == before
    assert {entry[0] for entry in decode(pending['request'])['pieces']} == {first}
    path = tmp_path / 'pending_loss.json'
    save_game(state, path, meta=session.meta, log=session.log)
    state, meta, log = load_game(path, validate=True)
    session, driver = _session(state, faction, meta, log)
    illegal = {'decision_id': pending['id'], 'response': [[later, None]]}
    session.import_inbox(illegal)
    with pytest.raises(DecisionPending):
        with _action_transaction(state, driver):
            resolve_losses(state, rc.CARNUTES, faction, 1, is_retreat=retreat)
    assert 'not offered' in session.error
    assert session.data['pending'] == pending
    assert session.data['queue'] == [illegal]
    assert session.data['journal'] == []
    assert session.log == []
    assert encode(board_copy(state)) == before
    first_entry = decode(pending['request'])['pieces'][0]
    session.import_inbox({'decision_id': pending['id'], 'response': [first_entry]})
    with _action_transaction(state, driver):
        result = resolve_losses(state, rc.CARNUTES, faction, 1, is_retreat=retreat)
    session.finish()
    assert result['removed'] == [(first, 1)]
    assert len(session.log) == 1
    assert session.data['pending'] is None
    assert session.data['queue'] == []
    assert session.data['journal'] == []
    assert count_pieces(state, rc.CARNUTES, faction, later) == 1
    assert validate_state(state) == []


def test_saved_second_tier_replays_the_accepted_first_loss(tmp_path):
    state = _state(rc.SCENARIO_GREAT_REVOLT, rc.AEDUI, rc.WARBAND, rc.ALLY)
    session, driver = _session(state, rc.AEDUI)
    before = encode(board_copy(state))
    session.import_inbox([{'response': [[rc.WARBAND, None]]}])
    with pytest.raises(DecisionPending):
        with _action_transaction(state, driver):
            resolve_losses(state, rc.CARNUTES, rc.AEDUI, 2)
    assert encode(board_copy(state)) == before
    assert len(session.data['journal']) == 1
    pending = copy.deepcopy(session.data['pending'])
    assert pending['id'] == 'd000002'
    assert decode(pending['request'])['pieces'] == [(rc.ALLY, None)]
    path = tmp_path / 'second_tier.json'
    save_game(state, path, meta=session.meta, log=session.log)
    state, meta, log = load_game(path, validate=True)
    session, driver = _session(state, rc.AEDUI, meta, log)
    session.import_inbox({'decision_id': pending['id'],
                          'response': [[rc.ALLY, None]]})
    with _action_transaction(state, driver):
        result = resolve_losses(state, rc.CARNUTES, rc.AEDUI, 2)
    session.finish()
    assert result['removed'] == [(rc.WARBAND, 1), (rc.ALLY, 1)]
    assert [entry['assistant_id'] for entry in log] == ['d000001', 'd000002']
    assert [decode(entry['assistant_response']) for entry in log] == [
        [[rc.WARBAND, None]], [[rc.ALLY, None]]]
    assert session.data['pending'] is None
    assert session.data['journal'] == []
    assert validate_state(state) == []


@pytest.mark.parametrize('retreat', [False, True])
def test_explicit_priority_rechecks_the_tier_and_piece_presence(retreat):
    state = _state(rc.SCENARIO_GREAT_REVOLT, rc.AEDUI, rc.WARBAND, rc.ALLY)
    first, later = (rc.ALLY, rc.WARBAND) if retreat else (rc.WARBAND, rc.ALLY)
    result = resolve_losses(state, rc.CARNUTES, rc.AEDUI, 3,
                            is_retreat=retreat, loss_order=[(later, None)])
    assert result['removed'] == [(first, 1), (later, 1)]
    assert result['losses_taken'] == 2
    assert validate_state(state) == []


def test_legacy_explicit_visibility_keeps_the_exact_legal_casualty():
    state = _state(rc.SCENARIO_GREAT_REVOLT, rc.AEDUI, rc.WARBAND, rc.ALLY)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND,
                piece_state=rc.REVEALED)
    result = resolve_losses(state, rc.CARNUTES, rc.AEDUI, 1,
                            loss_order=[(rc.ALLY, None), (rc.WARBAND, rc.REVEALED)])
    assert result['removed'] == [(rc.WARBAND, 1)]
    assert count_pieces_by_state(state, rc.CARNUTES, rc.AEDUI,
                                 rc.WARBAND, rc.HIDDEN) == 1
    assert count_pieces_by_state(state, rc.CARNUTES, rc.AEDUI,
                                 rc.WARBAND, rc.REVEALED) == 0
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.ALLY) == 1
    assert validate_state(state) == []


def test_surviving_retreat_fort_keeps_mobile_pieces_ineligible():
    state = _state(rc.SCENARIO_GREAT_REVOLT, rc.ROMANS, rc.AUXILIA, rc.FORT,
                   seed=0)
    offered = []

    def choose(board, faction, request):
        offered.append(request['pieces'])
        return request['pieces']

    state['decision_agent'] = choose
    result = resolve_losses(state, rc.CARNUTES, rc.ROMANS, 4, is_retreat=True)
    assert offered == [[(rc.FORT, None)]] * 3 + [[(rc.AUXILIA, None)]]
    assert result['rolls'] == [(rc.FORT, 4, False), (rc.FORT, 4, False),
                               (rc.FORT, 1, True)]
    assert result['removed'] == [(rc.FORT, 1), (rc.AUXILIA, 1)]
    assert validate_state(state) == []


def test_full_battle_filters_attack_and_counterattack_requests():
    state = _state(rc.SCENARIO_GREAT_REVOLT, rc.AEDUI, rc.WARBAND, rc.ALLY)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 3)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.FORT)
    requests = []

    def choose(board, faction, request):
        requests.append((faction, request['pieces']))
        return [(rc.ALLY if faction == rc.AEDUI else rc.FORT, None)]

    state['decision_agent'] = choose
    result = resolve_battle(state, rc.CARNUTES, rc.ROMANS, rc.AEDUI,
                            retreat_declaration=False)
    assert result['attack']['removed'] == [(rc.WARBAND, 1)]
    assert result['counterattack']['removed'] == [(rc.AUXILIA, 1)]
    assert requests == [(rc.AEDUI, [(rc.WARBAND, None)] * 4),
                        (rc.ROMANS, [(rc.AUXILIA, None)] * 2)]
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.ALLY) == 1
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.FORT) == 1
    assert validate_state(state) == []


def test_settlement_and_ally_remain_owner_choices_in_the_static_tier():
    state = _state(rc.SCENARIO_ARIOVISTUS, rc.GERMANS, rc.WARBAND, rc.SETTLEMENT)
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.ALLY)
    state['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] = rc.GERMANS
    requests = []

    def choose(board, faction, request):
        requests.append(request['pieces'])
        return [(rc.SETTLEMENT, None)]

    state['decision_agent'] = choose
    result = resolve_losses(state, rc.CARNUTES, rc.GERMANS, 1, is_retreat=True)
    assert requests == [[(rc.ALLY, None), (rc.SETTLEMENT, None)]]
    assert result['removed'] == [(rc.SETTLEMENT, 1)]
    assert count_pieces(state, rc.CARNUTES, rc.GERMANS, rc.ALLY) == 1
    assert count_pieces(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND) == 1
    assert validate_state(state) == []


@pytest.mark.parametrize('retreat', [False, True])
def test_diviciacus_remains_after_both_mobile_and_static_tiers(retreat):
    state = _state(rc.SCENARIO_ARIOVISTUS, rc.AEDUI, rc.WARBAND, rc.ALLY)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.LEADER,
                leader_name=rc.DIVICIACUS)
    requests = []

    def choose_leader(board, faction, request):
        requests.append(request['pieces'])
        return [(rc.LEADER, None)]

    state['decision_agent'] = choose_leader
    result = resolve_losses(state, rc.CARNUTES, rc.AEDUI, 2, is_retreat=retreat)
    expected = [rc.ALLY, rc.WARBAND] if retreat else [rc.WARBAND, rc.ALLY]
    assert requests == [[(piece, None)] for piece in expected]
    assert result['removed'] == [(piece, 1) for piece in expected]
    assert result['rolls'] == []
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.LEADER) == 1
    assert validate_state(state) == []


@pytest.mark.parametrize('retreat', [False, True])
def test_native_nonplayer_loss_sequence_and_rng_remain_unchanged(retreat):
    state = _state(rc.SCENARIO_GREAT_REVOLT, rc.BELGAE, rc.WARBAND, rc.ALLY)
    state['non_player_factions'] = {rc.BELGAE}
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND,
                piece_state=rc.REVEALED)
    before_rng = state['rng'].getstate()
    result = resolve_losses(state, rc.CARNUTES, rc.BELGAE, 2, is_retreat=retreat)
    expected = [(rc.ALLY, 1), (rc.WARBAND, 1)] if retreat else [(rc.WARBAND, 1)] * 2
    assert result['removed'] == expected
    assert count_pieces_by_state(state, rc.CARNUTES, rc.BELGAE,
                                 rc.WARBAND, rc.HIDDEN) == int(retreat)
    assert count_pieces_by_state(state, rc.CARNUTES, rc.BELGAE,
                                 rc.WARBAND, rc.REVEALED) == 0
    assert count_pieces(state, rc.CARNUTES, rc.BELGAE, rc.ALLY) == int(not retreat)
    assert state['rng'].getstate() == before_rng
    assert validate_state(state) == []


@pytest.mark.parametrize('hard_target', [False, True])
def test_explicit_a28_owner_priority_uses_only_required_loss_rng(hard_target):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=1)
    state['non_player_factions'] = {rc.ROMANS}
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEGION, from_legions_track=True)
    expected_rng = copy.deepcopy(state['rng'])
    priorities = [(rc.WARBAND, rc.HIDDEN, rc.AEDUI)]
    if hard_target:
        priorities.insert(0, (rc.LEGION, None))
        roll = expected_rng.randint(rc.DIE_MIN, rc.DIE_MAX)
    with combined_force(state, rc.ROMANS, {rc.CARNUTES: [rc.AEDUI]}):
        result = resolve_losses(state, rc.CARNUTES, rc.ROMANS,
                                2 if hard_target else 1, loss_order=priorities)
    assert state['rng'].getstate() == expected_rng.getstate()
    assert result['removed'] == ([(rc.LEGION, 1)] if hard_target else []) + [
        (rc.WARBAND, 1)]
    assert result['rolls'] == ([(rc.LEGION, roll, True)] if hard_target else [])
    assert count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 0
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 1
    assert validate_state(state) == []


def test_ineligible_explicit_a28_priority_retains_default_tie_rng():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=1)
    state['non_player_factions'] = {rc.ROMANS}
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.FORT)
    default = copy.deepcopy(state)
    before_rng = state['rng'].getstate()
    with combined_force(state, rc.ROMANS, {rc.CARNUTES: [rc.AEDUI]}):
        result = resolve_losses(state, rc.CARNUTES, rc.ROMANS, 1,
                                loss_order=[(rc.FORT, None)])
    with combined_force(default, rc.ROMANS, {rc.CARNUTES: [rc.AEDUI]}):
        expected = resolve_losses(default, rc.CARNUTES, rc.ROMANS, 1)
    assert result == expected
    assert encode(state) == encode(default)
    assert state['rng'].getstate() != before_rng
    assert validate_state(state) == []
