"""Optional timing changes future Battle choices, never completed losses."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.battle import elite
from fs_bot.battle.losses import resolve_losses
from fs_bot.battle.resolve import resolve_battle
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.cards.capabilities import activate_capability
from fs_bot.engine import action_windows as windows, execute
from fs_bot.engine.spring import UNLOCK_KEY
from fs_bot.engine.voluntary_removal import operation
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state


R = rc.CARNUTES


class FixedRng:
    def __init__(self, value=6):
        self.value, self.calls = value, 0

    def randint(self, *args):
        self.calls += 1
        return self.value


class Agent:
    supports_action_windows = True

    def __init__(self, choose=None):
        self.choose, self.requests = choose, []

    def __call__(self, state, faction, request):
        self.requests.append(deepcopy(request))
        answer = self.choose(state, faction, request) if self.choose else None
        if answer is not None:
            return answer
        kind = request['kind']
        if kind == 'voluntary_removal':
            return {'done': True}
        if kind == 'spring_leader':
            return {'defer': True}
        if kind == 'battle_elite':
            return {'use_default': True}
        if kind == 'retreat':
            return {'retreat': False}
        return None


def state(*, boxed=False, card30=False):
    board = build_initial_state(rc.SCENARIO_PAX_GALLICA if boxed else rc.SCENARIO_GREAT_REVOLT,
                                seed=81)
    board['non_player_factions'] = set()
    board['resources'] = {f: 20 for f in rc.FACTIONS}
    if boxed:
        board['spring_box_leaders'] = [rc.VERCINGETORIX]
        board['available'][rc.ARVERNI][rc.LEADER] -= 1
        board[UNLOCK_KEY] = True
    if card30:
        activate_capability(board, 30, rc.EVENT_SHADED)
        place_piece(board, R, rc.ARVERNI, rc.LEADER, leader_name=rc.VERCINGETORIX)
    return board


def battle_plan(defender=rc.ARVERNI, *, sa='No SA'):
    return {'command': rc.CMD_BATTLE, 'sa': sa, 'sa_regions': [R] if sa != 'No SA' else [],
            'details': {'battle_plan': [{'region': R, 'target': defender}]}}


def test_entry_precedes_retreat_destination_and_agreement_choices():
    board = state(boxed=True)
    place_piece(board, R, rc.ARVERNI, rc.WARBAND)
    from fs_bot.map.map_data import get_adjacent
    destination = sorted(get_adjacent(R, board['scenario']))[0]
    place_piece(board, destination, rc.ARVERNI, rc.WARBAND)
    place_piece(board, destination, rc.AEDUI, rc.WARBAND)
    def choose(current, faction, request):
        if request['kind'] == 'spring_leader':
            assert request['window']['stage'] == 'battle_retreat_choice'
            return {'region': destination}
    agent = Agent(choose)
    board['decision_agent'] = agent
    with windows.scope(board, actor=rc.ROMANS):
        execute._decide_defender_retreat(board, R, rc.ROMANS, rc.ARVERNI, False)
    retreat = next(req for req in agent.requests if req['kind'] == 'retreat')
    assert destination in retreat['legal_regions']
    assert validate_state(board) == []


def test_entry_between_losses_keeps_prior_loss_and_fixed_total():
    board = state(boxed=True)
    place_piece(board, R, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(board, R, rc.ARVERNI, rc.WARBAND, 2)
    board['rng'] = FixedRng(6)
    def choose(current, faction, request):
        if (request['kind'] == 'spring_leader'
                and request['window']['stage'] == 'battle_loss'
                and request['window']['faction'] == rc.ARVERNI
                and request['window']['remaining'] == 1):
            return {'region': R}
        if request['kind'] == 'loss_order' and faction == rc.ARVERNI:
            leaders = [piece for piece in request['pieces'] if piece[0] == rc.LEADER]
            return leaders or None
    board['decision_agent'] = Agent(choose)
    with windows.scope(board, actor=None):
        result = resolve_battle(board, R, rc.ROMANS, rc.ARVERNI)
    assert result['attack']['losses_taken'] == 1
    assert result['attack']['losses_absorbed'] == 1
    assert result['attack']['rolls'] == [(rc.LEADER, 6, False)]
    assert board['rng'].calls == 1
    assert count_pieces(board, R, rc.ARVERNI, rc.WARBAND) == 1


def test_entry_before_counterattack_uses_current_forces():
    board = state(boxed=True)
    place_piece(board, R, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(board, R, rc.ARVERNI, rc.WARBAND, 3)
    def choose(current, faction, request):
        if (request['kind'] == 'spring_leader'
                and request['window']['stage'] == 'battle_counterattack'):
            return {'region': R}
    board['decision_agent'] = Agent(choose)
    with windows.scope(board, actor=None):
        result = resolve_battle(board, R, rc.ROMANS, rc.ARVERNI)
    assert result['attack']['losses_taken'] == 2
    assert result['counterattack']['losses_taken'] == 1
    assert count_pieces(board, R, rc.ROMANS, rc.AUXILIA) == 3


def test_removing_attacking_force_does_not_recalculate_already_inflicted_losses():
    board = state()
    place_piece(board, R, rc.ROMANS, rc.AUXILIA, 8)
    place_piece(board, R, rc.ARVERNI, rc.WARBAND, 5)
    removed = False
    def choose(current, faction, request):
        nonlocal removed
        if (request['kind'] == 'voluntary_removal' and not removed
                and request['window']['stage'] == 'battle_loss'
                and request['window']['remaining'] == 3):
            removed = True
            choice = next(c for c in request['options'] if c['piece_type'] == rc.AUXILIA)
            return {'operations': [operation(choice, 8)]}
    board['decision_agent'] = Agent(choose)
    with windows.scope(board, actor=rc.ROMANS):
        result = resolve_battle(board, R, rc.ROMANS, rc.ARVERNI)
    assert removed and result['attack']['losses_taken'] == 4
    assert count_pieces(board, R, rc.ARVERNI, rc.WARBAND) == 1
    assert count_pieces(board, R, rc.ROMANS, rc.AUXILIA) == 0
    assert validate_state(board) == []


def test_removed_citadel_keeps_start_protection_and_is_not_besieged_twice():
    board = state()
    place_piece(board, R, rc.ROMANS, rc.AUXILIA, 6)
    place_piece(board, R, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(board, R, rc.ARVERNI, rc.WARBAND, 5)
    place_piece(board, R, rc.ARVERNI, rc.CITADEL)
    board['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] = rc.ARVERNI
    removed, observed = False, []
    def choose(current, faction, request):
        nonlocal removed
        if (request['kind'] == 'voluntary_removal' and not removed
                and request['window']['stage'] == 'battle_retreat_choice'):
            removed = True
            choice = next(c for c in request['options']
                          if c['piece_type'] == rc.CITADEL and c['action'] == 'remove')
            return {'operations': [operation(choice)]}
    board['decision_agent'] = Agent(choose)
    def observe(phase, current, region, defender, result):
        if phase == 'after':
            observed.append(result)
    with windows.scope(board, actor=rc.ARVERNI):
        result = execute._execute_battle(board, rc.ROMANS,
            battle_plan(sa=rc.SA_BESIEGE), _battle_observer=observe)
    assert result['executed'] and not result['errors'], result
    assert removed and observed[0]['attack']['losses_taken'] == 2
    assert observed[0]['besiege'] is None
    assert not result['battle_sa_executed']
    assert validate_state(board) == []


def test_a69_full_loss_uses_surviving_selected_cohort_at_attack():
    board = state()
    place_piece(board, R, rc.BELGAE, rc.WARBAND, 3)
    place_piece(board, R, rc.AEDUI, rc.WARBAND, 8)
    removed, observed = False, []
    def choose(current, faction, request):
        nonlocal removed
        if (request['kind'] == 'voluntary_removal' and not removed
                and request['window']['stage'] == 'battle_attack'):
            removed = True
            choice = next(c for c in request['options'] if c.get('cohort') == 'a69.placed')
            return {'operations': [operation(choice)]}
    board['decision_agent'] = Agent(choose)
    def observe(phase, current, region, defender, result):
        if phase == 'after':
            observed.append(result)
    with windows.scope(board, actor=rc.BELGAE):
        windows.set_cohorts(board, 'a69', rc.BELGAE, [{
            'id': 'a69.placed', 'region': R, 'piece_type': rc.WARBAND,
            'piece_state': rc.HIDDEN, 'count': 2}])
        result = execute._execute_battle(board, rc.BELGAE, battle_plan(rc.AEDUI),
            _full_loss_warbands=2, _full_loss_cohort='a69', _battle_observer=observe)
    assert result['executed'] and not result['errors'], result
    assert removed and observed[0]['attack']['losses_taken'] == 1


@pytest.mark.parametrize('picked', [False, True])
def test_elite_and_ordinary_same_visibility_are_distinct_casualties(picked):
    board = state(card30=True)
    place_piece(board, R, rc.ARVERNI, rc.WARBAND, 4)
    board['rng'] = FixedRng(1)
    def choose(current, faction, request):
        if request['kind'] == 'loss_order':
            return [next(piece for piece in request['pieces']
                         if piece[0] == rc.WARBAND and (len(piece) == 4) == picked)]
    board['decision_agent'] = Agent(choose)
    with windows.scope(board, actor=None):
        result = resolve_losses(board, R, rc.ARVERNI, 1)
    assert result['losses_taken'] == 1
    assert board['rng'].calls == int(picked)
    assert result['legion_warbands_surviving'] == (1 if picked else 2)
    assert elite.KEY not in board and windows.COHORTS not in board


@pytest.mark.parametrize('remove_picked,expected', [(True, 2), (False, 3)])
def test_voluntary_removal_updates_exact_elite_counterattack_cohort(remove_picked, expected):
    board = state(card30=True)
    place_piece(board, R, rc.ARVERNI, rc.WARBAND, 5)
    place_piece(board, R, rc.ARVERNI, rc.CITADEL)
    board['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] = rc.ARVERNI
    place_piece(board, R, rc.ROMANS, rc.AUXILIA, 6)
    removed = False
    def choose(current, faction, request):
        nonlocal removed
        if request['kind'] == 'loss_order' and faction == rc.ARVERNI:
            return [next(piece for piece in request['pieces']
                         if piece[0] == rc.WARBAND and len(piece) == 2)]
        if (request['kind'] == 'voluntary_removal' and not removed
                and request['window']['stage'] == 'battle_counterattack'):
            removed = True
            choice = next(c for c in request['options'] if c['piece_type'] == rc.WARBAND
                          and (c.get('cohort') == elite.COHORT) == remove_picked)
            return {'operations': [operation(choice, 2)]}
    board['decision_agent'] = Agent(choose)
    with windows.scope(board, actor=rc.ARVERNI):
        result = resolve_battle(board, R, rc.ROMANS, rc.ARVERNI)
    assert removed and result['attack']['losses_taken'] == 1
    assert result['counterattack']['losses_taken'] == expected
    assert validate_state(board) == []


def test_elite_selection_can_choose_revealed_instead_of_hidden():
    board = state(card30=True)
    place_piece(board, R, rc.ARVERNI, rc.WARBAND, 2)
    place_piece(board, R, rc.ARVERNI, rc.WARBAND, 2, piece_state=rc.REVEALED)
    def choose(current, faction, request):
        if request['kind'] == elite.KIND:
            return {'counts': {rc.REVEALED: 2}}
        if request['kind'] == 'loss_order':
            assert (rc.WARBAND, rc.REVEALED, None, 'elite') in request['pieces']
            return [(rc.WARBAND, rc.HIDDEN)]
    board['decision_agent'] = Agent(choose)
    with windows.scope(board, actor=None):
        result = resolve_losses(board, R, rc.ARVERNI, 1)
    assert result['rolls'] == [] and result['legion_warbands_surviving'] == 2


def test_pending_elite_choice_restores_complete_command():
    board = state(card30=True)
    place_piece(board, R, rc.ARVERNI, rc.WARBAND, 4)
    place_piece(board, R, rc.ROMANS, rc.AUXILIA, 4)
    before = encode(board)
    def choose(current, faction, request):
        if request['kind'] == elite.KIND:
            raise EOFError('Elite choice pending')
    board['decision_agent'] = Agent(choose)
    with pytest.raises(EOFError, match='Elite choice pending'):
        execute.execute_decision(board, rc.ROMANS, {'player_action': battle_plan()})
    assert encode({key: value for key, value in board.items() if key != 'decision_agent'}) == before


def test_preview_never_consults_live_timing_or_elite_agent():
    board = state(boxed=True, card30=False)
    place_piece(board, R, rc.ARVERNI, rc.WARBAND, 4)
    place_piece(board, R, rc.ROMANS, rc.AUXILIA, 4)
    before = encode(board)
    board['decision_agent'] = Agent(lambda *args: pytest.fail('Live preview input'))
    from fs_bot.engine.moves import preview_player_action
    preview_player_action(board, rc.ROMANS, battle_plan())
    assert encode({key: value for key, value in board.items() if key != 'decision_agent'}) == before


@pytest.mark.parametrize('edition,number', [('original', 2), ('second-edition', 4)])
def test_elite_pick_uses_the_selected_card_edition(edition, number):
    board = state(card30=True)
    board['card_edition'] = edition
    place_piece(board, R, rc.ARVERNI, rc.WARBAND, 5)
    agent = Agent()
    board['decision_agent'] = agent
    with windows.scope(board, actor=None), elite.scope(board, R, rc.ARVERNI):
        elite.ensure_selected(board, R)
        assert elite.count(board, R) == number
    request = next(req for req in agent.requests if req['kind'] == elite.KIND)
    assert request['count'] == number


@pytest.mark.parametrize('response', [
    {'counts': {rc.HIDDEN: True}}, {'counts': {rc.HIDDEN: -1, rc.REVEALED: 3}},
    {'counts': {rc.HIDDEN: 1}}, {'counts': {rc.HIDDEN: 3}},
    {'counts': {rc.HIDDEN: 2}, 'other': 1}, {'use_default': 1},
])
def test_invalid_elite_allocation_does_not_mutate_state(response):
    board = state(card30=True)
    request = {'kind': elite.KIND, 'faction': rc.ARVERNI, 'region': R,
               'count': 2, 'available': {rc.HIDDEN: 2, rc.REVEALED: 0, rc.SCOUTED: 0}}
    before = encode(board)
    with pytest.raises(ValueError):
        elite.validate_response(board, request, response)
    assert encode(board) == before


def test_explicit_ordinary_loss_priority_does_not_consume_elite_piece():
    board = state(card30=True)
    place_piece(board, R, rc.ARVERNI, rc.WARBAND, 4)
    board['decision_agent'] = Agent()
    board['rng'] = FixedRng(1)
    with windows.scope(board, actor=None):
        result = resolve_losses(board, R, rc.ARVERNI, 1,
                                loss_order=[(rc.WARBAND, rc.HIDDEN)])
    assert result['rolls'] == [] and result['legion_warbands_surviving'] == 2


@pytest.mark.parametrize('faction,piece', [
    (rc.ARVERNI, rc.WARBAND), (rc.AEDUI, rc.WARBAND),
    (rc.BELGAE, rc.WARBAND), (rc.ROMANS, rc.AUXILIA),
])
def test_nonplayer_mobile_losses_follow_scouted_revealed_hidden_priority(faction, piece):
    board = state()
    board['non_player_factions'] = {faction}
    place_piece(board, R, faction, piece, 2)
    place_piece(board, R, faction, piece, piece_state=rc.REVEALED)
    place_piece(board, R, faction, piece, piece_state=rc.SCOUTED)
    resolve_losses(board, R, faction, 2)
    from fs_bot.board.pieces import count_pieces_by_state
    assert count_pieces_by_state(board, R, faction, piece, rc.HIDDEN) == 2
    assert count_pieces_by_state(board, R, faction, piece, rc.REVEALED) == 0
    assert count_pieces_by_state(board, R, faction, piece, rc.SCOUTED) == 0


def test_unresolved_nonplayer_elite_designation_keeps_existing_order():
    """Do not choose a new physical Elite policy via the ordinary NP fix."""
    from fs_bot.board.pieces import count_pieces_by_state
    board = state(card30=True)
    board['non_player_factions'] = {rc.ARVERNI}
    place_piece(board, R, rc.ARVERNI, rc.WARBAND, 2)
    place_piece(board, R, rc.ARVERNI, rc.WARBAND, piece_state=rc.SCOUTED)
    board['rng'] = FixedRng(1)
    result = resolve_losses(board, R, rc.ARVERNI, 1)
    assert result['losses_taken'] == 1
    assert count_pieces_by_state(board, R, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 1
    assert count_pieces_by_state(board, R, rc.ARVERNI, rc.WARBAND, rc.SCOUTED) == 1


def _session(board, meta=None, log=None):
    from io import StringIO
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.tools.seat_session import SeatSession
    session = SeatSession(board, meta if meta is not None else {'seat': rc.ARVERNI},
                          log if log is not None else [], HumanTurnDisplay(StringIO()))
    board['decision_agent'] = session.reactive
    def driver(*args):
        pass
    driver.transaction_checkpoint = session.checkpoint
    driver.transaction_restore = session.restore
    return session, driver


def _transaction_loss(board, driver, *, live_windows=True):
    from contextlib import nullcontext
    from fs_bot.engine.game_engine import _action_transaction
    with _action_transaction(board, driver):
        with windows.scope(board, actor=None, force=True) if live_windows else nullcontext():
            return resolve_losses(board, R, rc.ARVERNI, 1)


def test_accepted_elite_selection_survives_save_load_and_exact_replay(tmp_path):
    from fs_bot.state.serialize import decode, load_game, save_game
    from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy
    board = state(card30=True)
    place_piece(board, R, rc.ARVERNI, rc.WARBAND, 4)
    origin, before = deepcopy(board), encode(board)
    session, driver = _session(board)
    session.import_inbox([{'response': {'counts': {rc.HIDDEN: 2}}}])
    with pytest.raises(DecisionPending):
        _transaction_loss(board, driver)
    assert encode(board_copy(board)) == before
    pending = deepcopy(session.data['pending'])
    assert decode(pending['request'])['kind'] == 'loss_order'
    accepted = deepcopy(session.data['journal'][0])
    assert decode(accepted['assistant_request'])['kind'] == elite.KIND
    save_game(board, tmp_path / 'elite.json', meta=session.meta, log=session.log)
    restored, meta, log = load_game(tmp_path / 'elite.json', validate=True)
    resumed, resumed_driver = _session(restored, meta, log)
    resumed.import_inbox({'decision_id': pending['id'],
                          'response': [[rc.WARBAND, rc.HIDDEN]]})
    result = _transaction_loss(restored, resumed_driver)
    resumed.finish()
    assert resumed.log[0] == accepted and result['rolls'] == []
    replay, replay_driver = _session(origin)
    replay.data['queue'] = [SeatSession._inbox_entry(entry) for entry in resumed.log]
    replay.data['expected'] = [{'id': entry['assistant_id'],
        'signature': entry['assistant_signature'], 'request': entry['assistant_request'],
        'action_windows_version': entry.get('assistant_action_windows_version', 0)}
        for entry in resumed.log]
    assert _transaction_loss(origin, replay_driver) == result
    replay.finish()
    assert replay.log == resumed.log
    assert encode(board_copy(origin)) == encode(board_copy(restored))


def test_old_loss_journal_replays_without_inserting_elite_choice(monkeypatch):
    from fs_bot.tools.seat_session import SeatSession, board_copy
    board = state(card30=True)
    place_piece(board, R, rc.ARVERNI, rc.WARBAND, 4)
    origin = deepcopy(board)
    with monkeypatch.context() as patch:
        patch.setattr(SeatSession, 'supports_action_windows', False)
        old, old_driver = _session(board)
        old.import_inbox([{'response': [[rc.WARBAND, None]]}])
        result = _transaction_loss(board, old_driver, live_windows=False)
        old.finish()
    assert len(old.log) == 1
    replay, replay_driver = _session(origin)
    replay.data['queue'] = [SeatSession._inbox_entry(entry) for entry in old.log]
    replay.data['expected'] = [{'id': entry['assistant_id'],
        'signature': entry['assistant_signature'], 'request': entry['assistant_request']}
        for entry in old.log]
    assert _transaction_loss(origin, replay_driver) == result
    replay.finish()
    assert len(replay.log) == 1 and not replay.data['pending']
    assert encode(board_copy(origin)) == encode(board_copy(board))


@pytest.mark.parametrize('germans,executed', [(2, False), (3, True)])
def test_base_german_free_battle_requires_and_uses_intrinsic_ambush(germans, executed):
    board = state()
    place_piece(board, R, rc.GERMANS, rc.WARBAND, germans)
    place_piece(board, R, rc.AEDUI, rc.WARBAND, 2)
    result = execute._execute_battle(board, rc.GERMANS, battle_plan(rc.AEDUI))
    assert result['executed'] is executed
    assert bool(result['errors']) is not executed
    if executed:
        assert result['battle_sa_executed']
