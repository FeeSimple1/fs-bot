"""A20 casualty origins: A3.2.4 priority and owner-adopted provisional PR-09."""
from copy import deepcopy
import io
import pytest

from fs_bot import rules_consts as rc
from fs_bot.battle.losses import resolve_losses
from fs_bot.board.pieces import (
    PieceError, count_pieces, count_pieces_by_state, get_available, move_piece, place_piece,
)
from fs_bot.cards.event_conditions import np_event_available
from fs_bot.cards.morbihan_display import (
    PROJECTION_KEY, projected_battle, snapshot_sources,
)
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.engine.agent import LOSS_ORDER
from fs_bot.engine.execute import _execute_event, _resolve_a20_arverni_ambush
from fs_bot.engine.game_engine import _action_transaction
from fs_bot.state.serialize import encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import SeatSession, DecisionPending, board_copy


def _state(scenario=rc.SCENARIO_ARIOVISTUS, seed=0):
    state = build_initial_state(scenario, seed=seed)
    state['current_card'] = state['current_card_id'] = 'A20'
    state['non_player_factions'] = {rc.ROMANS, rc.GERMANS, rc.BELGAE, rc.AEDUI}
    place_piece(state, rc.VENETI, rc.ARVERNI, rc.ALLY)
    state['tribes'][rc.TRIBE_VENETI]['allied_faction'] = rc.ARVERNI
    return state


def _gather(state, cohorts, target=rc.CARNUTES):
    """Build a scoped force without bypassing physical piece accounting."""
    for (origin, visibility), count in cohorts.items():
        place_piece(state, origin, rc.ARVERNI, rc.WARBAND, count,
                    piece_state=visibility)
    sources = snapshot_sources(state, sorted({r for r, _ in cohorts}))
    for (origin, visibility), count in cohorts.items():
        if origin != target:
            move_piece(state, origin, target, rc.ARVERNI, rc.WARBAND,
                       count, piece_state=visibility)
    return sources


def _battle_state(scenario=rc.SCENARIO_ARIOVISTUS, seed=0):
    state = _state(scenario, seed)
    place_piece(state, rc.VENETI, rc.ARVERNI, rc.WARBAND, 1)
    place_piece(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEGION, 2,
                from_legions_track=True)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    return state


def _event(state, human):
    return _execute_event(state, rc.GERMANS, {'command': 'Event', 'details': {
        'card_id': 'A20', 'text_preference': rc.EVENT_SHADED}}, human=human)


def test_each_loss_selects_equally_among_origins_not_weighted_counters(monkeypatch):
    state = _state()
    sources = _gather(state, {(rc.VENETI, rc.HIDDEN): 1,
                              (rc.PICTONES, rc.HIDDEN): 3})
    calls = []
    selected = iter((rc.PICTONES, rc.VENETI))

    def choose(origins):
        calls.append(tuple(origins))
        return next(selected)

    monkeypatch.setattr(state['rng'], 'choice', choose)
    with projected_battle(state, rc.CARNUTES, sources) as survivors:
        losses = resolve_losses(state, rc.CARNUTES, rc.ARVERNI, 3)
    # PR-09: the 3-to-1 force split still gives each Region one entry.
    # After the second casualty empties Veneti, the third needs no die.
    assert calls == [tuple(sorted((rc.VENETI, rc.PICTONES)))] * 2
    assert losses['origin_losses'] == [
        (rc.PICTONES, rc.HIDDEN, 1), (rc.VENETI, rc.HIDDEN, 1),
        (rc.PICTONES, rc.HIDDEN, 1)]
    assert survivors[rc.VENETI][rc.HIDDEN] == 0
    assert survivors[rc.PICTONES][rc.HIDDEN] == 1
    assert sources[rc.VENETI][rc.HIDDEN] == 1


def test_visibility_priority_is_global_before_any_origin_tie_break(monkeypatch):
    state = _state()
    sources = _gather(state, {
        (rc.VENETI, rc.SCOUTED): 1, (rc.VENETI, rc.HIDDEN): 2,
        (rc.PICTONES, rc.SCOUTED): 1, (rc.PICTONES, rc.REVEALED): 1,
        (rc.PICTONES, rc.HIDDEN): 3,
    })
    calls = []

    def choose(origins):
        calls.append(tuple(origins))
        return rc.PICTONES

    monkeypatch.setattr(state['rng'], 'choice', choose)
    state['decision_agent'] = lambda *_: pytest.fail('game-run Arverni asked a human')
    with projected_battle(state, rc.CARNUTES, sources):
        # Neither a raw agent nor an explicit reverse order may override A3.2.4.
        losses = resolve_losses(state, rc.CARNUTES, rc.ARVERNI, 4,
                                loss_order=[(rc.WARBAND, rc.HIDDEN)])
    assert losses['origin_losses'] == [
        (rc.PICTONES, rc.SCOUTED, 1), (rc.VENETI, rc.SCOUTED, 1),
        (rc.PICTONES, rc.REVEALED, 1), (rc.PICTONES, rc.HIDDEN, 1)]
    assert len(calls) == 2


@pytest.mark.parametrize('visibility', [rc.SCOUTED, rc.REVEALED, rc.HIDDEN])
def test_single_origin_and_excess_losses_use_no_rng_or_nonparticipants(visibility):
    state = _state()
    sources = _gather(state, {(rc.VENETI, visibility): 2})
    # Cenabum's Citadel and the Aulerci Ally occupy different Tribe spaces.
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.CITADEL)
    state['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] = rc.ARVERNI
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.ALLY)
    state['tribes'][rc.TRIBE_AULERCI]['allied_faction'] = rc.ARVERNI
    assert validate_state(state) == []
    available = get_available(state, rc.ARVERNI, rc.WARBAND)
    rng = state['rng'].getstate()
    with projected_battle(state, rc.CARNUTES, sources) as survivors:
        losses = resolve_losses(state, rc.CARNUTES, rc.ARVERNI, 20)
    assert losses['losses_taken'] == 2
    assert losses['origin_losses'] == [(rc.VENETI, visibility, 1)] * 2
    assert survivors[rc.VENETI][visibility] == 0
    assert state['rng'].getstate() == rng
    assert count_pieces(state, rc.CARNUTES, rc.ARVERNI, rc.ALLY) == 1
    assert count_pieces(state, rc.CARNUTES, rc.ARVERNI, rc.CITADEL) == 1
    assert get_available(state, rc.ARVERNI, rc.WARBAND) == available + 2
    assert validate_state(state) == []


@pytest.mark.parametrize('scenario', rc.ARIOVISTUS_SCENARIOS)
@pytest.mark.parametrize('human', [False, True])
def test_caesar_counterattack_returns_exact_survivors_for_each_origin(scenario, human):
    state = _battle_state(scenario)
    calls = []

    def agent(board, faction, request):
        calls.append(faction)
        assert faction != rc.ARVERNI
        return None

    state['decision_agent'] = agent
    result = _event(state, human)['free_actions'][0]['result']
    assert result['caesar_roll'] == (4, True)
    losses = result['counterattack']
    assert losses['losses_taken'] == 2
    for origin, initial in ((rc.VENETI, 1), (rc.PICTONES, 3)):
        removed = sum(n for region, _, n in losses['origin_losses'] if region == origin)
        assert count_pieces_by_state(
            state, origin, rc.ARVERNI, rc.WARBAND, rc.REVEALED) == initial - removed
        assert count_pieces_by_state(
            state, origin, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 0
    assert count_pieces(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND) == 0
    assert PROJECTION_KEY not in state and validate_state(state) == []


def test_local_participants_share_origin_selection_but_distant_warbands_do_not(monkeypatch):
    state = _state()
    place_piece(state, rc.VENETI, rc.ARVERNI, rc.WARBAND, 1)
    place_piece(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 2, piece_state=rc.SCOUTED)
    place_piece(state, rc.PICTONES, rc.ROMANS, rc.LEGION, 2,
                from_legions_track=True)
    place_piece(state, rc.PICTONES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    candidates = []

    def choose(origins):
        candidates.append(tuple(origins))
        return rc.PICTONES

    monkeypatch.setattr(state['rng'], 'choice', choose)
    result = _resolve_a20_arverni_ambush(state)[0]
    assert result['region'] == rc.PICTONES
    assert candidates == [tuple(sorted((rc.PICTONES, rc.VENETI)))] * 2
    assert count_pieces_by_state(state, rc.VENETI, rc.ARVERNI, rc.WARBAND, rc.REVEALED) == 1
    assert count_pieces_by_state(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND, rc.REVEALED) == 1
    assert count_pieces_by_state(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, rc.SCOUTED) == 2


def test_actual_counterattack_stops_at_warbands_and_preserves_veneti_ally():
    state = _state()
    place_piece(state, rc.VENETI, rc.ARVERNI, rc.WARBAND, 2)
    place_piece(state, rc.VENETI, rc.ROMANS, rc.LEGION, 4,
                from_legions_track=True)
    place_piece(state, rc.VENETI, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    result = _resolve_a20_arverni_ambush(state)[0]['result']
    assert result['caesar_roll'][1]
    assert result['counterattack']['losses_taken'] == 2
    assert count_pieces(state, rc.VENETI, rc.ARVERNI, rc.ALLY) == 1
    assert state['tribes'][rc.TRIBE_VENETI]['allied_faction'] == rc.ARVERNI
    assert validate_state(state) == []


def test_mixed_visibility_casualties_return_remaining_scouted_to_exact_origins(monkeypatch):
    state = _state()
    place_piece(state, rc.VENETI, rc.ARVERNI, rc.WARBAND, 1)
    place_piece(state, rc.VENETI, rc.ARVERNI, rc.WARBAND, 1, piece_state=rc.SCOUTED)
    place_piece(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND, 3, piece_state=rc.SCOUTED)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 4, piece_state=rc.REVEALED)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    monkeypatch.setattr(state['rng'], 'choice', lambda origins: rc.PICTONES)
    battle = _resolve_a20_arverni_ambush(state)[0]['result']
    assert battle['counterattack']['origin_losses'] == [(rc.PICTONES, rc.SCOUTED, 1)] * 2
    assert count_pieces_by_state(state, rc.VENETI, rc.ARVERNI, rc.WARBAND, rc.SCOUTED) == 1
    assert count_pieces_by_state(state, rc.VENETI, rc.ARVERNI, rc.WARBAND, rc.REVEALED) == 1
    assert count_pieces_by_state(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND, rc.SCOUTED) == 1
    assert count_pieces(state, rc.CARNUTES, rc.ARVERNI) == 0
    assert validate_state(state) == []


def test_multiple_origins_without_counterattack_do_not_consume_randomness():
    state = _state()
    place_piece(state, rc.VENETI, rc.ARVERNI, rc.WARBAND, 1)
    place_piece(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND, 3)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 4, piece_state=rc.REVEALED)
    rng = state['rng'].getstate()
    battle = _resolve_a20_arverni_ambush(state)[0]['result']
    assert battle['counterattack'] is None
    assert state['rng'].getstate() == rng
    assert count_pieces_by_state(state, rc.VENETI, rc.ARVERNI, rc.WARBAND, rc.REVEALED) == 1
    assert count_pieces_by_state(state, rc.PICTONES, rc.ARVERNI, rc.WARBAND, rc.REVEALED) == 3


def test_preview_leaves_live_rng_board_and_callback_untouched():
    state = _battle_state()
    before = encode(state)
    calls = []
    state['decision_agent'] = lambda *args: calls.append(args)
    assert np_event_available(state, 'A20', rc.GERMANS, True)
    assert calls == []
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before
    assert PROJECTION_KEY not in state


def test_save_resume_replays_identical_origins_and_rng(tmp_path):
    state = _battle_state()
    path = tmp_path / 'before-morbihan.json'
    save_game(state, path)
    resumed, _, _ = load_game(path)
    uninterrupted = _event(state, True)
    replayed = _event(resumed, True)
    assert replayed == uninterrupted
    assert encode(resumed) == encode(state)
    save_game(resumed, path)
    restored, _, _ = load_game(path)
    assert encode(restored) == encode(state)
    assert PROJECTION_KEY not in restored


def test_human_loss_pause_save_resume_preserves_accepted_choices_and_origin_dice(tmp_path):
    state = _battle_state()
    state['non_player_factions'].remove(rc.ROMANS)
    baseline = deepcopy(state)
    baseline['decision_agent'] = lambda board, faction, request: (
        [(rc.LEGION, None)] if faction == rc.ROMANS and request['kind'] == LOSS_ORDER
        else None)
    expected = _event(baseline, False)
    session = SeatSession(state, {'seat': rc.ROMANS, 'scenario': state['scenario'],
                                 'seed': 0}, [], HumanTurnDisplay(io.StringIO()))

    def attach(current):
        current.state['decision_agent'] = current.reactive
        def driver(*args):
            pass
        driver.transaction_checkpoint = current.checkpoint
        driver.transaction_restore = current.restore
        return driver

    driver = attach(session)
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending):
        with _action_transaction(state, driver):
            _event(state, False)
    first = session.data['pending']
    session.import_inbox({'decision_id': first['id'], 'response': [[rc.LEGION, None]]})
    with pytest.raises(DecisionPending):
        with _action_transaction(state, driver):
            _event(state, False)
    second = session.data['pending']
    assert second['id'] != first['id']
    assert len(session.data['journal']) == 1
    assert encode(board_copy(state)) == before
    assert PROJECTION_KEY not in state
    path = tmp_path / 'morbihan-second-loss-pending.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = SeatSession(restored, meta, log, HumanTurnDisplay(io.StringIO()))
    resumed_driver = attach(resumed)
    resumed.import_inbox({'decision_id': second['id'], 'response': [[rc.LEGION, None]]})
    with _action_transaction(restored, resumed_driver):
        actual = _event(restored, False)
    resumed.finish()
    assert actual == expected
    assert encode(board_copy(restored)) == encode(board_copy(baseline))
    assert len(log) == 2 and all(row['reactive'] == LOSS_ORDER for row in log)
    assert resumed.data['pending'] is None
    assert PROJECTION_KEY not in restored


@pytest.mark.parametrize('failure_point', ['after_battle', 'during_return'])
def test_failed_projected_battle_restores_all_effects_and_rng(monkeypatch, failure_point):
    state = _battle_state()
    agent = lambda *_: None
    state['decision_agent'] = agent
    before = encode(board_copy(state))
    observed = []
    if failure_point == 'after_battle':
        from fs_bot.battle.resolve import resolve_battle

        def fail_after_casualties(*args, **kwargs):
            result = resolve_battle(*args, **kwargs)
            observed.append(result['counterattack']['origin_losses'])
            raise PieceError('failure after actual casualty allocation')

        monkeypatch.setattr('fs_bot.battle.resolve.resolve_battle', fail_after_casualties)
    else:
        def fail_during_return(board, source, destination, *args, **kwargs):
            if source == rc.CARNUTES and destination == rc.PICTONES:
                observed.append(count_pieces(board, rc.CARNUTES, rc.ARVERNI, rc.WARBAND))
                raise PieceError('failure returning surviving Warbands')
            return move_piece(board, source, destination, *args, **kwargs)

        monkeypatch.setattr('fs_bot.board.pieces.move_piece', fail_during_return)
    result = _resolve_a20_arverni_ambush(state)[0]
    assert observed
    assert result['executed'] is False and result['rolled_back'] is True
    assert encode(board_copy(state)) == before
    assert state['decision_agent'] is agent
    assert PROJECTION_KEY not in state and validate_state(state) == []


@pytest.mark.parametrize('scenario', rc.BASE_SCENARIOS)
def test_ordinary_base_arverni_losses_are_not_subject_to_pr09(scenario):
    state = build_initial_state(scenario, seed=0)
    place_piece(state, rc.VENETI, rc.ARVERNI, rc.WARBAND, 1)
    place_piece(state, rc.VENETI, rc.ARVERNI, rc.ALLY)
    state['tribes'][rc.TRIBE_VENETI]['allied_faction'] = rc.ARVERNI
    rng = state['rng'].getstate()
    losses = resolve_losses(state, rc.VENETI, rc.ARVERNI, 2)
    assert losses['losses_taken'] == 2 and 'origin_losses' not in losses
    assert count_pieces(state, rc.VENETI, rc.ARVERNI) == 0
    assert state['rng'].getstate() == rng


def test_region_selection_is_stable_under_source_insertion_order():
    original = _battle_state(seed=31)
    copy = deepcopy(original)
    # Map iteration ordering must not determine which physical origin dies.
    copy['spaces'] = dict(reversed(list(copy['spaces'].items())))
    assert _event(copy, False) == _event(original, False)
    assert encode(copy) == encode(original)
