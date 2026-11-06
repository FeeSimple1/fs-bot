"""Shaded A17: choose one Region, remove exact Auxilia, and bar Rome."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_available, place_piece
from fs_bot.cards.base_piece_choices import KIND, a17_removal_request
from fs_bot.cards.event_conditions import np_event_available
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.execute import execute_decision, _derive_card_A17
from fs_bot.engine.game_engine import ACTION_EVENT, _action_transaction, adjust_eligibility
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def position(scenario=rc.SCENARIO_ARIOVISTUS, *, seed=17, populated=True):
    state = build_initial_state(scenario, seed=seed)
    state['current_card'] = state['current_card_id'] = 'A17'
    if populated:
        place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 4)
        for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
            place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA, 3, piece_state=visibility)
    return state


def entry(visibility, count, region=rc.TREVERI):
    return {'region': region, 'target_faction': rc.ROMANS, 'piece_type': rc.AUXILIA,
            'piece_state': visibility, 'count': count}


def choices():
    return [entry(rc.REVEALED, 1), entry(rc.SCOUTED, 3)]


def play(state, executor=rc.GERMANS, params=None, *, npc=False):
    action = {'command': rc.FIRST_DID_EVENT, 'regions': [],
              'details': {'card_id': 'A17', 'text_preference': rc.EVENT_SHADED,
                          'event_params': params or {}}}
    return execute_decision(state, executor, {'action': ACTION_EVENT,
                            ('bot_action' if npc else 'player_action'): action})


@pytest.mark.parametrize('scenario', rc.ARIOVISTUS_SCENARIOS)
@pytest.mark.parametrize('executor', [rc.GERMANS, rc.ROMANS])
def test_exact_single_region_and_ineligible_through_next_card(scenario, executor):
    state = position(scenario)
    before = get_available(state, rc.ROMANS, rc.AUXILIA)
    assert play(state, executor, {'region': rc.TREVERI, 'piece_choices': choices()})['executed']
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 4
    assert count_pieces_by_state(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 3
    assert count_pieces_by_state(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 2
    assert count_pieces_by_state(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA, rc.SCOUTED) == 0
    assert get_available(state, rc.ROMANS, rc.AUXILIA) == before + 4
    assert state['eligibility'][rc.ROMANS] == rc.INELIGIBLE
    adjust_eligibility(state, {})
    assert state['eligibility'][rc.ROMANS] == rc.INELIGIBLE
    adjust_eligibility(state, {})
    assert state['eligibility'][rc.ROMANS] == rc.ELIGIBLE
    assert validate_state(state) == []


@pytest.mark.parametrize('count', [0, 2])
def test_required_total_is_local_to_the_chosen_region(count):
    state = position()
    place_piece(state, rc.NERVII, rc.ROMANS, rc.AUXILIA, count, piece_state=rc.SCOUTED)
    selections = [entry(rc.SCOUTED, count, rc.NERVII)] if count else []
    assert play(state, params={'region': rc.NERVII, 'piece_choices': selections})['executed']
    assert count_pieces(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA) == 9
    assert count_pieces(state, rc.NERVII, rc.ROMANS, rc.AUXILIA) == 0


@pytest.mark.parametrize('region,selections', [
    (rc.TREVERI, choices()[:1]),
    (rc.TREVERI, [entry(rc.HIDDEN, 1, rc.PROVINCIA), choices()[1]]),
    (rc.TREVERI, [entry(rc.SCOUTED, 2), entry(rc.SCOUTED, 2)]),
    (rc.BRITANNIA, []),
    (None, choices()),
])
def test_illegal_plan_rolls_back_before_roman_ineligibility(region, selections):
    state = position()
    before = encode(board_copy(state))
    assert play(state, params={'region': region, 'piece_choices': selections})['rejected']
    assert encode(board_copy(state)) == before


def test_no_auxilia_still_makes_romans_ineligible_without_choice():
    state = position(populated=False)
    state['decision_agent'] = lambda *args: pytest.fail('A17 had no Auxilia to choose')
    assert play(state, rc.BELGAE)['executed']
    assert state['forced_ineligible'][rc.ROMANS] == 1


def test_legacy_region_plan_removes_scouted_when_needed():
    state = position(populated=False)
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA, 2, piece_state=rc.SCOUTED)
    state['decision_agent'] = lambda *args: pytest.fail('Legacy A17 already specified its Region')
    assert play(state, params={'region': rc.TREVERI})['executed']
    assert count_pieces(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA) == 0


def test_german_bot_declines_outside_its_printed_scope_but_player_may_choose_it():
    from fs_bot.bots.german_bot import node_g3b
    state = position(populated=False)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 4)
    assert _derive_card_A17(state, rc.GERMANS, True) is None
    assert np_event_available(state, 'A17', rc.GERMANS, True) is False
    assert node_g3b(state) == 'Yes'
    assert play(state, params={'region': rc.PROVINCIA, 'piece_choices': [
        entry(rc.HIDDEN, 4, rc.PROVINCIA)]})['executed']
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 0


def test_german_settlement_and_adjacent_tiers():
    state = position(populated=False)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(state, rc.SEQUANI, rc.GERMANS, rc.SETTLEMENT)
    assert _derive_card_A17(state, rc.GERMANS, True) == {'region': rc.PROVINCIA}
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 1, piece_state=rc.SCOUTED)
    assert _derive_card_A17(state, rc.GERMANS, True) == {'region': rc.SEQUANI}
    assert play(state, npc=True)['executed']
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 4


def test_belgic_ties_use_seeded_choice_and_only_removable_quantity():
    selected = set()
    for seed in range(8):
        state = position(seed=seed, populated=False)
        for region, count in ((rc.MORINI, 4), (rc.NERVII, 5), (rc.PROVINCIA, 9)):
            place_piece(state, region, rc.ROMANS, rc.AUXILIA, count)
        twin = decode(encode(state))
        choice = _derive_card_A17(state, rc.BELGAE, True)
        assert choice == _derive_card_A17(twin, rc.BELGAE, True)
        selected.add(choice['region'])
    assert selected == {rc.MORINI, rc.NERVII}


def test_terminal_menu_offers_region_then_exact_auxilia():
    from fs_bot.cli.human_plan import _collect_event_params
    state = position()
    output = StringIO()
    assert _collect_event_params(state, rc.AEDUI, 'A17', True, StringIO(), output) == {}
    index = list(a17_removal_request(state)['required_by_region']).index(rc.TREVERI) + 1
    state['decision_agent'] = make_cli_reactive(
        {rc.AEDUI}, StringIO(f'board\n{index}\n3\n3\n2\n1\n'), output)
    assert play(state, rc.AEDUI)['executed']
    assert 'Choose the single A17 removal Region' in output.getvalue()
    assert count_pieces_by_state(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA, rc.SCOUTED) == 0


def test_pending_choice_survives_save_and_invalid_retry(tmp_path):
    state = position()
    initial = encode(board_copy(state))

    def session_for(board, meta=None, log=None):
        session = SeatSession(board, meta or {'seat': rc.GERMANS}, [] if log is None else log,
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
    assert decode(pending['request'])['owner'] == rc.GERMANS
    session.import_inbox({'decision_id': pending['id'],
                          'response': {'region': rc.TREVERI, 'selections': []}})
    with pytest.raises(DecisionPending):
        attempt(session)
    assert session.error and session.data['pending'] == pending
    assert encode(board_copy(state)) == initial
    path = tmp_path / 'a17.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session_for(restored, meta, log)
    with pytest.raises(DecisionPending):
        attempt(resumed)
    assert resumed.data['pending'] == pending
    resumed.import_inbox({'decision_id': pending['id'],
                          'response': {'region': rc.TREVERI, 'selections': choices()}})
    assert attempt(resumed)['executed']
    resumed.finish()
    reference = decode(initial)
    assert play(reference, params={'region': rc.TREVERI, 'piece_choices': choices()})['executed']
    assert encode(board_copy(restored)) == encode(board_copy(reference))
    assert len(log) == 1 and validate_state(restored) == []
