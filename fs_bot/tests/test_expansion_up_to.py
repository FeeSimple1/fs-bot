"""A Card Reference A40S/A51U/A60U: every optional quantity includes zero."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece, get_available
from fs_bot.cards.card_effects import execute_event, _ally_tribe
from fs_bot.engine.execute import _execute_event
from fs_bot.engine.moves import validate_player_action
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import encode, decode, save_game, load_game

SIDES = [('A40', True), ('A51', False), ('A60', False)]


def position(card='A40', faction=rc.AEDUI):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=2)
    state['non_player_factions'] = set()
    state['current_card'], state['next_card'] = card, 'A67'
    state['executing_faction'] = faction
    state['resources'][rc.ROMANS] = 20
    state['event_params'] = {}
    for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        place_piece(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 3, piece_state=visibility)
    return state


def action(card, params):
    return {'command': rc.FIRST_DID_EVENT, 'regions': [], 'sa': 'No SA', 'sa_regions': [],
            'details': {'card_id': card, 'text_preference': rc.EVENT_SHADED if card == 'A40' else rc.EVENT_UNSHADED,
                        'event_params': params}}


def request_for(state, card):
    from fs_bot.cards.expansion_up_to import choice_request
    return choice_request(state, card)


def cohort(visibility, count=1):
    return {'piece_state': visibility, 'count': count}


@pytest.mark.parametrize('regions', [[], [rc.CISALPINA], [rc.CISALPINA, rc.SEQUANI, rc.UBII]])
def test_a40_author_selects_exact_number_of_regions(regions):
    state = position(); state['event_params'] = {'regions': regions}
    execute_event(state, 'A40', shaded=True)
    assert state['resources'][rc.ROMANS] == 20 - 5 * len(regions)
    assert state['eligibility'][rc.AEDUI] == rc.ELIGIBLE and state['stay_eligible'] == [rc.AEDUI]
    assert validate_state(state) == []


@pytest.mark.parametrize('count', range(5))
def test_a60_author_selects_auxilia_resource_tradeoff(count):
    state = position('A60'); state['event_params'] = {'auxilia_count': count}
    execute_event(state, 'A60')
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == count
    assert state['tribes'][rc.TRIBE_REMI]['allied_faction'] == rc.ROMANS
    assert state['resources'][rc.ROMANS] == 20 + 2 * (4 - count)
    assert validate_state(state) == []


@pytest.mark.parametrize('visibility', [rc.HIDDEN, rc.REVEALED, rc.SCOUTED])
@pytest.mark.parametrize('count', [0, 1, 3])
def test_a51_author_selects_exact_physical_removals(visibility, count):
    state = position('A51')
    state['event_params'] = {'piece_type': rc.WARBAND,
                             'warband_removals': [cohort(visibility, count)] if count else []}
    execute_event(state, 'A51')
    for ps in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        assert count_pieces_by_state(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, ps) == 3 - (count if ps == visibility else 0)
    assert count_pieces(state, rc.ATREBATES, rc.AEDUI, rc.WARBAND) == 4
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.FORT) == 1
    assert validate_state(state) == []


def test_a51_six_can_mix_visibility_without_touching_unselected_cohort():
    state = position('A51'); state['event_params'] = {
        'warband_removals': [cohort(rc.REVEALED, 3), cohort(rc.SCOUTED, 3)]}
    execute_event(state, 'A51')
    assert count_pieces_by_state(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, rc.HIDDEN) == 3
    assert count_pieces(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND) == 3


@pytest.mark.parametrize('card,params', [
    ('A40', {'regions': None}), ('A40', {'regions': 'Cisalpina'}),
    ('A40', {'regions': [rc.CISALPINA] * 2}), ('A40', {'regions': [rc.MORINI]}),
    ('A40', {'regions': [rc.CISALPINA, rc.SEQUANI, rc.UBII, rc.PROVINCIA]}),
    ('A40', {'regions': [[]]}), ('A40', {'count': 0}),
    ('A51', {'warband_removals': None}), ('A51', {'warband_removals': [cohort(rc.REVEALED, 4)]}),
    ('A51', {'warband_removals': [cohort(rc.HIDDEN, 2)] * 2}),
    ('A51', {'warband_removals': [cohort(rc.HIDDEN, 3), cohort(rc.REVEALED, 3), cohort(rc.SCOUTED)]}),
    ('A51', {'warband_removals': [cohort(rc.HIDDEN, 0)]}),
    ('A51', {'warband_removals': [cohort(rc.HIDDEN, True)]}),
    ('A51', {'warband_removals': [cohort(rc.HIDDEN, 1.5)]}),
    ('A51', {'warband_removals': [cohort(None)]}),
    ('A51', {'warband_removals': [dict(cohort(rc.HIDDEN), faction=rc.ARVERNI)]}),
    ('A51', {'piece_type': rc.ALLY, 'warband_removals': []}),
    ('A60', {'auxilia_count': True}), ('A60', {'auxilia_count': -1}),
    ('A60', {'auxilia_count': 5}), ('A60', {'auxilia_count': 1.5}),
    ('A60', {'auxilia_count': None}), ('A60', {'count': 0}),
])
def test_invalid_authored_choices_are_atomic_in_engine_and_public_preview(card, params):
    state = position(card); before = encode(state)
    ok, _ = validate_player_action(state, rc.AEDUI, action(card, params))
    assert not ok and encode(state) == before
    result = _execute_event(state, rc.AEDUI, action(card, params), human=True)
    assert not result['executed'] and result['rejected']
    assert encode(state) == before


@pytest.mark.parametrize('card,shaded', SIDES)
@pytest.mark.parametrize('executor', [rc.ROMANS, rc.AEDUI, rc.BELGAE, rc.GERMANS])
def test_omitted_choice_requests_executor_after_prerequisites(card, shaded, executor):
    state = position(card, executor); seen = []
    answer = {'A40': {'regions': []}, 'A51': {'removals': []}, 'A60': {'count': 0}}[card]
    def agent(board, faction, request):
        assert request['kind'] == 'event_up_to' and faction == executor
        assert request['card_id'] == card
        if card == 'A51':
            assert count_pieces(board, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 4
            assert count_pieces(board, rc.ATREBATES, rc.ROMANS, rc.FORT) == 1
        if card == 'A60':
            assert board['tribes'][rc.TRIBE_REMI]['allied_faction'] == rc.ROMANS
        seen.append(request)
        return answer
    state['decision_agent'] = agent
    execute_event(state, card, shaded)
    assert len(seen) == 1
    assert state['resources'][rc.ROMANS] == (28 if card == 'A60' else 20)
    assert count_pieces(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND) == 9


@pytest.mark.parametrize('card,shaded', SIDES)
def test_preview_never_consults_live_optional_choice_or_rng(card, shaded):
    state = position(card)
    state['decision_agent'] = lambda *a: pytest.fail('Preview consumed live choice')
    from fs_bot.tools.seat_session import board_copy
    before = encode(board_copy(state))
    assert validate_player_action(state, rc.AEDUI, action(card, {}))[0]
    assert encode(board_copy(state)) == before
    sim = deepcopy(board_copy(state)); sim['_diviciacus_preview'] = True
    sim['decision_agent'] = state['decision_agent']
    execute_event(sim, card, shaded)
    assert encode(board_copy(state)) == before


@pytest.mark.parametrize('answer', [None, {'use_default': True}])
@pytest.mark.parametrize('card,shaded', SIDES)
def test_raw_delegation_keeps_maximum_default(card, shaded, answer):
    state = position(card)
    state['decision_agent'] = lambda *a: answer
    execute_event(state, card, shaded)
    assert state['resources'][rc.ROMANS] == (5 if card == 'A40' else 20)
    if card == 'A51':
        assert count_pieces(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND) == 3
    if card == 'A60':
        assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 4


def test_a40_rejects_roman_control_and_drain_stops_at_zero():
    state = position(); place_piece(state, rc.CISALPINA, rc.ROMANS, rc.AUXILIA)
    state['event_params'] = {'regions': [rc.CISALPINA]}; before = encode(state)
    with pytest.raises(ValueError): execute_event(state, 'A40', True)
    assert encode(state) == before
    state['event_params'] = {'regions': [rc.SEQUANI]}; state['resources'][rc.ROMANS] = 2
    execute_event(state, 'A40', True)
    assert state['resources'][rc.ROMANS] == 0


def test_a51_prerequisite_failure_has_no_optional_request_or_placements():
    state = position('A51'); state['tribes'][rc.TRIBE_REMI]['status'] = rc.DISPERSED
    state['decision_agent'] = lambda *a: pytest.fail('Inapplicable Event offered choices')
    from fs_bot.tools.seat_session import board_copy
    before = encode(board_copy(state))
    execute_event(state, 'A51')
    assert encode(board_copy(state)) == before


def test_a51_default_also_removes_eligible_scouted_warbands():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=2)
    state['event_params'] = {}
    place_piece(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 2, piece_state=rc.SCOUTED)
    execute_event(state, 'A51')
    assert count_pieces(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND) == 0


def test_a60_compensation_uses_actual_scarce_placements_and_resource_cap():
    state = position('A60')
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, get_available(state, rc.ROMANS, rc.AUXILIA) - 1)
    state['event_params'] = {'auxilia_count': 4}
    execute_event(state, 'A60')
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 1
    assert state['resources'][rc.ROMANS] == 26
    state = position('A60'); state['resources'][rc.ROMANS] = 44
    state['event_params'] = {'auxilia_count': 0}; execute_event(state, 'A60')
    assert state['resources'][rc.ROMANS] == 45


def test_a60_missing_ally_adds_two_independently_of_chosen_auxilia():
    state = position('A60')
    # All Roman Ally discs are physically elsewhere, so Remi cannot receive one.
    from fs_bot.cards.all_gaul_gathers import ally_options
    while get_available(state, rc.ROMANS, rc.ALLY):
        choices = [(tribe, owner) for region in state['spaces']
                   for tribe, owner in ally_options(state, region) if owner == rc.ROMANS and tribe != rc.TRIBE_REMI]
        if not choices: break
        assert _ally_tribe(state, choices[0][0], rc.ROMANS)
    assert get_available(state, rc.ROMANS, rc.ALLY) == 0
    state['event_params'] = {'auxilia_count': 0}; execute_event(state, 'A60')
    assert state['resources'][rc.ROMANS] == 30
    assert validate_state(state) == []


@pytest.mark.parametrize('card,shaded', SIDES)
def test_terminal_zero_choice_and_board_inspection(card, shaded):
    from fs_bot.cli.reactive import make_cli_reactive
    state = position(card); output = StringIO(); before = encode(state)
    # A51 asks independently about all three present cohorts.
    inputs = 'board\n1\n1\n1\n' if card == 'A51' else 'board\n1\n'
    response = make_cli_reactive({rc.AEDUI}, StringIO(inputs), output)(state, rc.AEDUI, request_for(state, card))
    assert response == {'A40': {'regions': []}, 'A51': {'removals': []}, 'A60': {'count': 0}}[card]
    assert encode(state) == before and output.getvalue()


def test_terminal_a51_selects_revealed_and_scouted_counts():
    from fs_bot.cli.reactive import make_cli_reactive
    state = position('A51')
    response = make_cli_reactive({rc.AEDUI}, StringIO('1\n3\n2\n'), StringIO())(
        state, rc.AEDUI, request_for(state, 'A51'))
    assert response == {'removals': [cohort(rc.REVEALED, 2), cohort(rc.SCOUTED, 1)]}


def test_terminal_event_planner_only_collects_a51_compulsory_type():
    from fs_bot.cli.human_plan import _collect_event_params
    state = position()
    assert _collect_event_params(state, rc.AEDUI, 'A40', True, StringIO(), StringIO()) == {}
    assert _collect_event_params(state, rc.AEDUI, 'A60', False, StringIO(), StringIO()) == {}
    assert _collect_event_params(state, rc.AEDUI, 'A51', False, StringIO('2\n'), StringIO()) == {'piece_type': rc.WARBAND}


@pytest.mark.parametrize('card,shaded', SIDES)
@pytest.mark.parametrize('bad', [None, {'use_default': 1}])
def test_live_optional_pending_rolls_back_prerequisites_save_resume_and_exact_replay(tmp_path, card, shaded, bad):
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.tools.seat_session import SeatSession, DecisionPending, board_copy
    state = position(card); origin = deepcopy(state); before = encode(state)
    def session_for(board, meta=None, log=None):
        session = SeatSession(board, meta or {'seat': rc.AEDUI}, log if log is not None else [], HumanTurnDisplay(StringIO()))
        board['decision_agent'] = session.reactive
        return session
    def attempt(session):
        def driver(*args): pass
        driver.transaction_checkpoint = session.checkpoint; driver.transaction_restore = session.restore
        with _action_transaction(session.state, driver):
            return _execute_event(session.state, rc.AEDUI, action(card, {}), human=True)
    session = session_for(state)
    with pytest.raises(DecisionPending): attempt(session)
    pending = deepcopy(session.data['pending']); request = decode(pending['request'])
    assert request['kind'] == 'event_up_to' and request['card_id'] == card
    if card == 'A51':
        assert count_pieces(decode(pending['board']), rc.ATREBATES, rc.ROMANS, rc.FORT) == 1
    session.import_inbox({'decision_id': pending['id'], 'response': bad})
    with pytest.raises(DecisionPending): attempt(session)
    assert session.data['pending']['id'] == pending['id'] and not session.data['journal']
    assert encode(board_copy(state)) == before
    path = tmp_path / 'optional.json'; save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True); resumed = session_for(restored, meta, log)
    answer = {'A40': {'regions': []}, 'A51': {'removals': [cohort(rc.SCOUTED, 2)]}, 'A60': {'count': 0}}[card]
    resumed.import_inbox({'decision_id': pending['id'], 'response': answer})
    result = attempt(resumed); resumed.finish(); assert result['executed']
    replay = session_for(origin)
    replay.data['queue'] = [SeatSession._inbox_entry(e) for e in resumed.log]
    replay.data['expected'] = [
        {'id': e['assistant_id'], 'signature': e['assistant_signature'], 'request': e['assistant_request'],
         'action_windows_version': e.get('assistant_action_windows_version', 0)} for e in resumed.log]
    assert attempt(replay) == result
    replay.finish()
    assert replay.log == resumed.log and encode(board_copy(origin)) == encode(board_copy(restored))
    assert validate_state(restored) == []


@pytest.mark.parametrize('card,shaded', SIDES)
def test_second_expansion_scenario_accepts_explicit_zero(card, shaded):
    state = position(card); state['scenario'] = rc.SCENARIO_GALLIC_WAR
    state['event_params'] = {'A40': {'regions': []}, 'A51': {'warband_removals': []},
                             'A60': {'auxilia_count': 0}}[card]
    execute_event(state, card, shaded)
    assert state['resources'][rc.ROMANS] == (28 if card == 'A60' else 20)
    assert count_pieces(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND) == 9


def test_a60_live_reclamation_precedes_quantity_and_actual_compensation():
    from fs_bot.engine.action_windows import scope
    state = position('A60', rc.ROMANS)
    total = get_available(state, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, total)
    state['event_params'] = {'auxilia_count': 2, 'stage_timing_actions': {'A60.auxilia': [
        {'kind': 'voluntary_removal', 'response': {'operations': [
            {'action': 'remove', 'region': rc.PROVINCIA, 'piece_type': rc.AUXILIA,
             'piece_state': rc.HIDDEN, 'count': 2}]}}]}}
    with scope(state, actor=rc.ROMANS, plan=state['event_params'], force=True):
        execute_event(state, 'A60')
    assert count_pieces(state, rc.ATREBATES, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == total - 2
    assert state['resources'][rc.ROMANS] == 24
    assert validate_state(state) == []


def test_a51_stale_authored_cohort_after_timing_is_rejected_atomically():
    from fs_bot.engine.action_windows import scope
    state = position('A51', rc.BELGAE)
    state['event_params'] = {'warband_removals': [cohort(rc.SCOUTED, 2)],
        'stage_timing_actions': {'A51.warbands': [
            {'kind': 'voluntary_removal', 'response': {'operations': [
                {'action': 'remove', 'region': rc.ATREBATES, 'piece_type': rc.WARBAND,
                 'piece_state': rc.SCOUTED, 'count': 2}]}}]}}
    from fs_bot.tools.seat_session import board_copy
    before = encode(board_copy(state))
    with pytest.raises(ValueError):
        with scope(state, actor=rc.BELGAE, plan=state['event_params'], force=True):
            execute_event(state, 'A51')
    assert encode(board_copy(state)) == before


@pytest.mark.parametrize('card,shaded', SIDES)
def test_terminal_eof_rolls_back_entire_event(card, shaded):
    from fs_bot.cli.reactive import make_cli_reactive
    from fs_bot.tools.seat_session import board_copy
    state = position(card); before = encode(state)
    state['decision_agent'] = make_cli_reactive({rc.AEDUI}, StringIO(), StringIO())
    with pytest.raises(EOFError): execute_event(state, card, shaded)
    assert encode(board_copy(state)) == before


def test_old_request_cannot_authorize_newly_roman_controlled_region_or_missing_cohort():
    from fs_bot.cards.expansion_up_to import validate_response
    from fs_bot.board.pieces import remove_piece
    state = position(); request = request_for(state, 'A40')
    place_piece(state, rc.CISALPINA, rc.ROMANS, rc.AUXILIA)
    before = encode(state)
    with pytest.raises(ValueError): validate_response(state, request, {'regions': [rc.CISALPINA]})
    assert encode(state) == before
    state = position('A51'); request = request_for(state, 'A51')
    remove_piece(state, rc.ATREBATES, rc.BELGAE, rc.WARBAND, count=3, piece_state=rc.SCOUTED)
    before = encode(state)
    with pytest.raises(ValueError): validate_response(state, request, {'removals': [cohort(rc.SCOUTED)]})
    assert encode(state) == before
