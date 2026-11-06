"""Unshaded Bellovaci removes exact Belgic Warbands and places replacements."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_available, place_piece
from fs_bot.cards.base_piece_choices import KIND, STATES
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.human_plan import _collect_event_params
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT, _action_transaction
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def position(scenario=rc.SCENARIO_ARIOVISTUS, warbands=(3, 2, 3)):
    state = build_initial_state(scenario, seed=69)
    state['current_card'] = state['current_card_id'] = 'A69'
    assert _ally_tribe(state, rc.TRIBE_BELLOVACI, rc.BELGAE)
    for visibility, count in zip(STATES, warbands):
        if count:
            place_piece(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, count,
                        piece_state=visibility)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 2, piece_state=rc.SCOUTED)
    return state


def entry(visibility, count, region=rc.ATREBATES, faction=rc.BELGAE):
    return {'region': region, 'target_faction': faction, 'piece_type': rc.WARBAND,
            'piece_state': visibility, 'count': count}


def choices():
    return [entry(rc.REVEALED, 1), entry(rc.SCOUTED, 3)]


def play(state, executor=rc.ROMANS, params=None, *, npc=False):
    action = {'command': rc.FIRST_DID_EVENT, 'regions': [],
              'details': {'card_id': 'A69', 'text_preference': rc.EVENT_UNSHADED,
                          'event_params': params or {}}}
    return execute_decision(state, executor, {'action': ACTION_EVENT,
                            ('bot_action' if npc else 'player_action'): action})


def warband_counts(state):
    return tuple(count_pieces_by_state(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, visibility)
                 for visibility in STATES)


def ally(state):
    return state['tribes'][rc.TRIBE_BELLOVACI]['allied_faction']


@pytest.mark.parametrize('scenario', rc.ARIOVISTUS_SCENARIOS)
def test_executor_selects_removals_and_independent_replacements(scenario):
    state = position(scenario)
    params = {'piece_choices': choices(), 'ally_faction': rc.ROMANS, 'piece_faction': rc.AEDUI}
    assert play(state, rc.GERMANS, params)['executed']
    assert warband_counts(state) == (3, 1, 0)
    assert count_pieces(state, rc.NERVII, rc.BELGAE, rc.WARBAND) == 2
    assert ally(state) == rc.ROMANS
    assert count_pieces(state, rc.ATREBATES, rc.BELGAE, rc.ALLY) == 0
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.ALLY) == 1
    assert count_pieces(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND) == 4
    assert validate_state(state) == []


@pytest.mark.parametrize('executor,warbands,remaining', [
    (rc.ROMANS, (3, 2, 3), (0, 1, 3)),
    (rc.BELGAE, (3, 2, 3), (3, 1, 0)),
    (rc.AEDUI, (0, 0, 2), (0, 0, 0)),
    (rc.AEDUI, (0, 0, 0), (0, 0, 0)),
])
def test_delegated_removals_and_replacements(executor, warbands, remaining):
    state = position(warbands=warbands)
    assert play(state, executor, npc=True)['executed']
    assert warband_counts(state) == remaining
    beneficiary, troop = (rc.AEDUI, rc.WARBAND) if executor == rc.AEDUI else (rc.ROMANS, rc.AUXILIA)
    assert ally(state) == beneficiary
    assert count_pieces(state, rc.ATREBATES, beneficiary, troop) == 4


@pytest.mark.parametrize('selections', [
    [], choices()[:1], [entry(rc.SCOUTED, 2), entry(rc.SCOUTED, 2)],
    [entry(rc.SCOUTED, 2, rc.NERVII), entry(rc.REVEALED, 2)],
    [entry(rc.HIDDEN, 4, faction=rc.AEDUI)],
])
def test_invalid_plan_rolls_back_the_ally_removal(selections):
    state = position()
    before = encode(board_copy(state))
    assert play(state, params={'piece_choices': selections})['rejected']
    assert encode(board_copy(state)) == before


def test_terminal_chooses_beneficiaries_and_exact_scouted_losses():
    state = position()
    output = StringIO()
    params = _collect_event_params(state, rc.GERMANS, 'A69', False, StringIO('2\n1\n'), output)
    terminal = make_cli_reactive({rc.GERMANS}, StringIO('board\n3\n3\n2\n1\n'), output)
    state['decision_agent'] = lambda b, f, r: terminal(b, f, r) if r['kind'] == KIND else None
    assert play(state, rc.GERMANS, params)['executed']
    assert 'place whose troops?' in output.getvalue()
    assert rc.SCOUTED in output.getvalue()
    assert ally(state) == rc.AEDUI
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 4
    assert warband_counts(state) == (3, 1, 0)


def test_no_local_warbands_skips_choice_and_troop_type_can_stand_alone():
    state = position(warbands=(0, 0, 0))

    def agent(board, faction, request):
        if request['kind'] == KIND:
            pytest.fail('Bellovaci had no local Warbands to choose')

    state['decision_agent'] = agent
    assert play(state, params={'piece_type': rc.WARBAND})['executed']
    assert ally(state) == rc.ROMANS
    assert count_pieces(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND) == 4


def test_exact_removals_and_troop_placements_respect_scarcity():
    state = position(warbands=(0, 0, 2))
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA,
                get_available(state, rc.ROMANS, rc.AUXILIA) - 1)
    assert play(state, params={'piece_choices': [entry(rc.SCOUTED, 2)]})['executed']
    assert warband_counts(state) == (0, 0, 0)
    assert ally(state) == rc.ROMANS
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 1


def test_pending_choice_survives_save_and_invalid_retry(tmp_path):
    state = position()
    initial = encode(board_copy(state))

    def session_for(board, meta=None, log=None):
        session = SeatSession(board, meta or {'seat': rc.ROMANS}, [] if log is None else log,
                              HumanTurnDisplay(StringIO()))

        def agent(live, faction, request):
            if request['kind'] == KIND:
                assert ally(live) is None
                return session.reactive(live, faction, request)

        board['decision_agent'] = agent
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
    request = decode(pending['request'])
    assert request['owner'] == rc.ROMANS and request['required'] == {rc.WARBAND: 4}
    session.import_inbox({'decision_id': pending['id'], 'response': {'selections': []}})
    with pytest.raises(DecisionPending):
        attempt(session)
    assert session.error and session.data['pending'] == pending
    assert encode(board_copy(state)) == initial

    path = tmp_path / 'a69.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session_for(restored, meta, log)
    with pytest.raises(DecisionPending):
        attempt(resumed)
    assert resumed.data['pending'] == pending
    resumed.import_inbox({'decision_id': pending['id'], 'response': {'selections': choices()}})
    assert attempt(resumed)['executed']
    resumed.finish()
    reference = decode(initial)
    assert play(reference, params={'piece_choices': choices()})['executed']
    assert encode(board_copy(restored)) == encode(board_copy(reference))
    assert len(log) == 1 and validate_state(restored) == []
