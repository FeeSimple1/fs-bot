"""A58 shaded replaces exact Roman pieces and Ambushes within one Region."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_available, place_piece
from fs_bot.cards.aduatuci import make_request
from fs_bot.cards.base_piece_choices import KIND
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cards.event_conditions import np_event_available
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT, _action_transaction
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def position(scenario=rc.SCENARIO_ARIOVISTUS, *, populated=True):
    state = build_initial_state(scenario, seed=58)
    state['current_card'] = state['current_card_id'] = 'A58'
    if populated:
        _ally_tribe(state, rc.TRIBE_NERVII, rc.ROMANS)
        _ally_tribe(state, rc.TRIBE_EBURONES, rc.ROMANS)
        place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, 2, piece_state=rc.HIDDEN)
        place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, 3, piece_state=rc.SCOUTED)
        place_piece(state, rc.MORINI, rc.ROMANS, rc.AUXILIA, 2)
    return state


def selection(count=3, region=rc.NERVII, visibility=rc.SCOUTED):
    return {'region': region, 'target_faction': rc.ROMANS, 'piece_type': rc.AUXILIA,
            'piece_state': visibility, 'count': count}


def plan(region=rc.NERVII, tribe=rc.TRIBE_EBURONES, pieces=None):
    return {'region': region, 'ally_tribe': tribe,
            'piece_choices': [selection()] if pieces is None else pieces}


def play(state, executor=rc.BELGAE, params=None, *, npc=False):
    action = {'command': rc.FIRST_DID_EVENT, 'regions': [],
              'details': {'card_id': 'A58', 'text_preference': rc.EVENT_SHADED,
                          'event_params': params or {}}}
    return execute_decision(state, executor, {'action': ACTION_EVENT,
                            ('bot_action' if npc else 'player_action'): action})


def ambushes(result):
    return [ambush for grant in result.get('free_actions', []) if grant['flag'] == 'card_A58'
            for ambush in grant['ambushes']]


@pytest.mark.parametrize('scenario', rc.ARIOVISTUS_SCENARIOS)
@pytest.mark.parametrize('executor', [rc.BELGAE, rc.AEDUI, rc.GERMANS])
def test_named_ally_and_exact_auxilia_replaced_with_executors_pieces(scenario, executor):
    state = position(scenario)
    assert _ally_tribe(state, rc.TRIBE_MORINI, rc.ROMANS)
    # Preserve the replacement snapshot without suppressing the legal check.
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, 2)
    result = play(state, executor, plan())
    assert result['executed'] and ambushes(result) == []
    assert state['tribes'][rc.TRIBE_EBURONES]['allied_faction'] == executor
    assert state['tribes'][rc.TRIBE_NERVII]['allied_faction'] == rc.ROMANS
    assert state['tribes'][rc.TRIBE_MORINI]['allied_faction'] == rc.ROMANS
    assert count_pieces_by_state(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 4
    assert count_pieces_by_state(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, rc.SCOUTED) == 0
    assert count_pieces_by_state(state, rc.NERVII, executor, rc.WARBAND, rc.HIDDEN) == 3
    assert validate_state(state) == []


def test_ambush_uses_replacement_warbands_only_in_selected_region():
    state = position()
    place_piece(state, rc.NERVII, rc.BELGAE, rc.LEADER, leader_name=rc.BODUOGNATUS)
    place_piece(state, rc.MORINI, rc.BELGAE, rc.WARBAND, 6)
    place_piece(state, rc.TREVERI, rc.BELGAE, rc.WARBAND, 6)
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA, 2)
    resources = state['resources'][rc.BELGAE]
    result = play(state, params=plan())
    assert result['executed']
    assert [(row['region'], row['defender']) for row in ambushes(result)] == [(rc.NERVII, rc.ROMANS)]
    for other in (rc.MORINI, rc.TREVERI):
        assert count_pieces(state, other, rc.ROMANS, rc.AUXILIA) == 2
        assert count_pieces_by_state(state, other, rc.BELGAE, rc.WARBAND, rc.HIDDEN) == 6
    assert state['resources'][rc.BELGAE] == resources
    assert validate_state(state) == []


def test_ambush_preserves_belgic_leader_range():
    state = position()
    result = play(state, params=plan())
    assert result['executed'] and ambushes(result) == []
    assert count_pieces_by_state(state, rc.NERVII, rc.BELGAE, rc.WARBAND, rc.HIDDEN) == 3


def test_roman_executor_removes_auxilia_when_it_has_no_warbands():
    state = position()
    result = play(state, rc.ROMANS, plan())
    assert result['executed'] and ambushes(result) == []
    assert state['tribes'][rc.TRIBE_EBURONES]['allied_faction'] == rc.ROMANS
    assert count_pieces(state, rc.NERVII, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(state, rc.NERVII, rc.ROMANS, rc.WARBAND) == 0
    assert validate_state(state) == []


def test_ambush_can_resolve_without_any_replacement_targets():
    state = position(populated=False)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.LEADER, leader_name=rc.BODUOGNATUS)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 6)
    place_piece(state, rc.NERVII, rc.ROMANS, rc.LEGION, from_legions_track=True)
    assert np_event_available(state, 'A58', rc.BELGAE, True)
    result = play(state, npc=True)
    assert result['executed'] and [row['region'] for row in ambushes(result)] == [rc.NERVII]


def test_scarce_replacements_do_not_save_selected_roman_pieces():
    state = position()
    allies = get_available(state, rc.BELGAE, rc.ALLY)
    # Put every Ally and all but one Warband onto the board.
    for tribe in list(state['tribes']):
        if get_available(state, rc.BELGAE, rc.ALLY) == 0:
            break
        if rc.TRIBE_FACTION_RESTRICTION.get(tribe, rc.BELGAE) == rc.BELGAE:
            _ally_tribe(state, tribe, rc.BELGAE)
    assert allies > 0 and get_available(state, rc.BELGAE, rc.ALLY) == 0
    place_piece(state, rc.PROVINCIA, rc.BELGAE, rc.WARBAND,
                get_available(state, rc.BELGAE, rc.WARBAND) - 1)
    assert play(state, params=plan())['executed']
    assert state['tribes'][rc.TRIBE_EBURONES]['allied_faction'] is None
    assert count_pieces(state, rc.NERVII, rc.BELGAE, rc.WARBAND) == 1
    assert count_pieces_by_state(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, rc.SCOUTED) == 0
    assert validate_state(state) == []


@pytest.mark.parametrize('bad', [
    plan(region=rc.PROVINCIA, tribe=None, pieces=[]),
    plan(tribe=None),
    plan(tribe=rc.TRIBE_MORINI),
    plan(pieces=[selection(count=2)]),
    plan(pieces=[selection(count=2), selection(count=1, region=rc.MORINI, visibility=rc.HIDDEN)]),
])
def test_invalid_plan_rolls_back_replacements_and_ambush(bad):
    state = position()
    before = encode(board_copy(state))
    assert play(state, params=bad)['rejected']
    assert encode(board_copy(state)) == before


@pytest.mark.parametrize('only_ally', [False, True])
def test_delegated_play_executes_partial_region_and_accepts_scouted(only_ally):
    state = position(populated=False)
    if only_ally:
        _ally_tribe(state, rc.TRIBE_NERVII, rc.ROMANS)
    else:
        place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, 2, piece_state=rc.SCOUTED)
    assert np_event_available(state, 'A58', rc.BELGAE, True)
    assert play(state, npc=True)['executed']
    if only_ally:
        assert state['tribes'][rc.TRIBE_NERVII]['allied_faction'] == rc.BELGAE
    else:
        assert count_pieces(state, rc.NERVII, rc.BELGAE, rc.WARBAND) == 2
    assert validate_state(state) == []


def test_bot_declines_targets_outside_belgica():
    state = position(populated=False)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 5)
    assert not np_event_available(state, 'A58', rc.BELGAE, True)


def test_terminal_selects_region_named_ally_and_scouted_cohort():
    from fs_bot.cli.human_plan import _collect_event_params
    state = position()
    output = StringIO()
    assert _collect_event_params(state, rc.BELGAE, 'A58', True, StringIO(), output) == {}
    request = make_request(state)
    region_index = list(request['required_by_region']).index(rc.NERVII) + 1
    tribe_index = request['ally_tribes_by_region'][rc.NERVII].index(rc.TRIBE_EBURONES) + 1
    state['decision_agent'] = make_cli_reactive(
        {rc.BELGAE}, StringIO(f'board\n{region_index}\n{tribe_index}\n2\n3\n1\n1\n1\n'), output)
    assert play(state)['executed']
    assert 'Choose the Roman Ally' in output.getvalue()
    assert state['tribes'][rc.TRIBE_EBURONES]['allied_faction'] == rc.BELGAE
    assert count_pieces_by_state(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, rc.SCOUTED) == 0


def test_pending_choice_survives_invalid_reply_and_save(tmp_path):
    state = position()
    initial = encode(board_copy(state))

    def session_for(board, meta=None, log=None):
        session = SeatSession(board, meta or {'seat': rc.BELGAE}, [] if log is None else log,
                              HumanTurnDisplay(StringIO()))
        board['decision_agent'] = lambda b, f, r: session.reactive(b, f, r) if r['kind'] == KIND else None
        return session

    def attempt(session):
        def driver(*args):
            pass
        driver.transaction_checkpoint = session.checkpoint
        driver.transaction_restore = session.restore
        with _action_transaction(session.state, driver):
            return play(session.state)

    session = session_for(state)
    with pytest.raises(DecisionPending):
        attempt(session)
    pending = deepcopy(session.data['pending'])
    assert decode(pending['request'])['owner'] == rc.BELGAE
    response = {'region': rc.NERVII, 'ally_tribe': rc.TRIBE_EBURONES, 'selections': [selection()]}
    session.import_inbox({'decision_id': pending['id'], 'response': dict(response, selections=[])})
    with pytest.raises(DecisionPending):
        attempt(session)
    assert session.error and session.data['pending'] == pending
    assert encode(board_copy(state)) == initial
    path = tmp_path / 'a58.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session_for(restored, meta, log)
    with pytest.raises(DecisionPending):
        attempt(resumed)
    assert resumed.data['pending'] == pending
    resumed.import_inbox({'decision_id': pending['id'], 'response': response})
    assert attempt(resumed)['executed']
    resumed.finish()
    reference = decode(initial)
    assert play(reference, params=plan())['executed']
    assert encode(board_copy(restored)) == encode(board_copy(reference))
    assert len(log) == 1 and validate_state(restored) == []
