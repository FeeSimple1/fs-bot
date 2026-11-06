"""Card Reference 3/5/A5 and §§5.1, 5.1.3: Roman-owned mandatory removals."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (
    _count_on_legions_track, count_pieces, count_pieces_by_state, get_available,
    place_piece, remove_piece,
)
from fs_bot.cards.base_piece_choices import KIND, roman_removal_request, validate_response
from fs_bot.cards.card_effects import execute_event
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.execute import _execute_event
from fs_bot.engine.game_engine import _action_transaction
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def position(card, scenario=None):
    if scenario is None:
        scenario = rc.SCENARIO_ARIOVISTUS if card == 'A5' else rc.SCENARIO_GREAT_REVOLT
    state = build_initial_state(scenario, seed=23)
    state['event_params'] = state['executing_faction'] = None
    state['senate']['position'] = rc.INTRIGUE
    state['current_card'], state['next_card'] = card, 67
    for region in (rc.PROVINCIA, rc.SEQUANI):
        place_piece(state, region, rc.ROMANS, rc.LEGION, 2, from_legions_track=True)
        for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
            place_piece(state, region, rc.ROMANS, rc.AUXILIA, 2, piece_state=visibility)
    if card == 3:
        place_piece(state, rc.TREVERI, rc.ROMANS, rc.LEGION,
                    _count_on_legions_track(state) - 4, from_legions_track=True)
    return state


def cohort(region, kind=rc.LEGION, visibility=None, count=1):
    return {'region': region, 'target_faction': rc.ROMANS,
            'piece_type': kind, 'piece_state': visibility, 'count': count}


def split(card):
    if card == 3:
        return [cohort(rc.PROVINCIA), cohort(rc.SEQUANI)]
    return [cohort(rc.SEQUANI), cohort(rc.PROVINCIA, rc.AUXILIA, rc.SCOUTED),
            cohort(rc.SEQUANI, rc.AUXILIA, rc.REVEALED)]


def action(card, params=None):
    return {'command': rc.FIRST_DID_EVENT, 'regions': [],
            'details': {'card_id': card, 'text_preference': rc.EVENT_SHADED,
                        'event_params': params or {}}}


@pytest.mark.parametrize('card,scenario', [
    (card, scenario) for card in (3, 5) for scenario in rc.ALL_SCENARIOS
] + [('A5', scenario) for scenario in sorted(rc.ARIOVISTUS_SCENARIOS)])
def test_exact_roman_plan_splits_regions_and_preserves_other_cohorts(card, scenario):
    state = position(card, scenario)
    track_before = _count_on_legions_track(state)
    available_before = get_available(state, rc.ROMANS, rc.AUXILIA)
    result = _execute_event(state, rc.ROMANS, action(card, {'piece_choices': split(card)}),
                            human=True)
    assert result['executed']
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.LEGION) == 1
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == (1 if card == 3 else 2)
    assert _count_on_legions_track(state) == track_before + (2 if card == 3 else 1)
    assert state['fallen_legions'] == 0
    assert get_available(state, rc.ROMANS, rc.AUXILIA) == available_before + (0 if card == 3 else 2)
    for region, selected in ((rc.PROVINCIA, rc.SCOUTED), (rc.SEQUANI, rc.REVEALED)):
        for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
            assert count_pieces_by_state(state, region, rc.ROMANS, rc.AUXILIA, visibility) == (
                1 if card != 3 and visibility == selected else 2)
    assert validate_state(state) == []


@pytest.mark.parametrize('card,legacy_plan', [
    (3, {'legion_removal_regions': [rc.PROVINCIA]}),
    (5, {'legion_removal_region': rc.SEQUANI}),
    ('A5', {'legion_region': rc.SEQUANI}),
    ('A5', {'auxilia_removals': [{'region': rc.SEQUANI}]}),
])
def test_other_executor_cannot_author_a_legacy_roman_choice(card, legacy_plan):
    assert_rejects_foreign_plan(card, legacy_plan)


@pytest.mark.parametrize('card', [3, 5, 'A5'])
def test_other_executor_cannot_author_an_exact_roman_choice(card):
    assert_rejects_foreign_plan(card, {'piece_choices': split(card)})


def assert_rejects_foreign_plan(card, params):
    state = position(card)
    before = encode(board_copy(state))
    result = _execute_event(state, rc.AEDUI, action(card, params), human=True)
    assert result['rejected'] and 'Only the Romans' in result['reason']
    assert encode(board_copy(state)) == before


@pytest.mark.parametrize('card', [3, 5, 'A5'])
def test_inactive_shaded_effect_does_not_ask_romans(card):
    state = position(card)
    if card == 3:
        remove_piece(state, rc.TREVERI, rc.ROMANS, rc.LEGION, to_track=True)
    else:
        state['senate']['position'] = rc.ADULATION
    state['decision_agent'] = lambda *args: pytest.fail('Inactive Event asked for removals')
    before = encode(board_copy(state))
    execute_event(state, card, shaded=True)
    assert encode(board_copy(state)) == before


@pytest.mark.parametrize('card', [3, 5, 'A5'])
def test_mandatory_totals_shrink_only_when_board_has_too_few_pieces(card):
    state = position(card)
    remove_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION, 2)
    remove_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEGION, 1 if card == 3 else 2)
    if card == 3:
        remove_piece(state, rc.TREVERI, rc.ROMANS, rc.LEGION, 4)
        choices = [cohort(rc.SEQUANI)]
    else:
        remove_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 6)
        remove_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 5)
        choices = [cohort(rc.SEQUANI, rc.AUXILIA, rc.SCOUTED)]
    state['event_params'] = {'piece_choices': choices}
    execute_event(state, card, shaded=True)
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.LEGION) == 0
    if card != 3:
        assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 0
    assert validate_state(state) == []


@pytest.mark.parametrize('bad', ['short', 'wrong_type_total', 'wrong_visibility',
                                 'foreign_faction', 'off_map', 'duplicate', 'boolean'])
def test_bad_gallia_plan_rejects_before_any_removal(bad):
    state = position(5)
    selections = split(5)
    if bad == 'short':
        selections.pop()
    elif bad == 'wrong_type_total':
        selections[-1] = cohort(rc.PROVINCIA)
    elif bad == 'wrong_visibility':
        selections[0]['piece_state'] = rc.HIDDEN
    elif bad == 'foreign_faction':
        selections[-1]['target_faction'] = rc.AEDUI
    elif bad == 'off_map':
        selections[-1]['region'] = rc.CISALPINA
    elif bad == 'duplicate':
        selections = [selections[0], dict(selections[1], count=2), selections[1]]
    else:
        selections[0]['count'] = True
    before = encode(board_copy(state))
    result = _execute_event(state, rc.ROMANS, action(5, {'piece_choices': selections}), human=True)
    assert result['rejected']
    assert encode(board_copy(state)) == before


def test_stale_auxilia_cohort_rejected():
    state = position(5)
    request = roman_removal_request(state, 5)
    remove_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 2, piece_state=rc.SCOUTED)
    with pytest.raises(ValueError, match='live physical cohort'):
        validate_response(state, request, {'selections': split(5)})


@pytest.mark.parametrize('card', [3, 5, 'A5'])
def test_explicit_delegation_matches_legacy_no_agent_resolution(card):
    state = position(card)
    default_state = decode(encode(state))
    default_state['decision_agent'] = lambda *args: {'use_default': True}
    track_before = _count_on_legions_track(state)
    available_before = get_available(state, rc.ROMANS, rc.AUXILIA)
    execute_event(state, card, shaded=True)
    execute_event(default_state, card, shaded=True)
    assert encode(board_copy(state)) == encode(board_copy(default_state))
    assert _count_on_legions_track(state) == track_before + (2 if card == 3 else 1)
    assert get_available(state, rc.ROMANS, rc.AUXILIA) == available_before + (0 if card == 3 else 2)


@pytest.mark.parametrize('card', [5, 'A5'])
def test_live_requirement_uses_board_after_event_timing(card):
    from fs_bot.engine.action_windows import scope

    state = position(card)
    remove_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 6)
    remove_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 2, piece_state=rc.HIDDEN)
    remove_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 2, piece_state=rc.REVEALED)
    params = {'stage_timing_actions': {f'{card}.piece_choice': [
        {'kind': 'voluntary_removal', 'response': {'operations': [
            {'action': 'remove', 'region': rc.PROVINCIA, 'piece_type': rc.AUXILIA,
             'piece_state': rc.SCOUTED, 'count': 1}]}}]}}

    def agent(board, faction, request):
        if request['kind'] == KIND:
            assert request['required'] == {rc.LEGION: 1, rc.AUXILIA: 1}
            return {'selections': [cohort(rc.SEQUANI),
                                    cohort(rc.PROVINCIA, rc.AUXILIA, rc.SCOUTED)]}

    state['decision_agent'] = agent
    with scope(state, actor=rc.ROMANS, plan=params, force=True):
        assert _execute_event(state, rc.ROMANS, action(card, params), human=True)['executed']
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 0
    assert validate_state(state) == []


def test_terminal_defers_to_live_roman_menu_and_allows_board_inspection():
    from fs_bot.cli.human_plan import _collect_event_params
    state = position(3)
    output = StringIO()
    assert _collect_event_params(state, rc.AEDUI, 3, True, StringIO(), output) == {}
    request = roman_removal_request(state, 3)
    options = request['available']
    inputs = 'board\n' + ''.join(f'{options.index(dict(entry, count=2)) + 1}\n1\n'
                                 for entry in split(3))
    agent = make_cli_reactive({rc.ROMANS}, StringIO(inputs), output)
    assert agent(state, rc.AEDUI, request) is None
    assert agent(state, rc.ROMANS, request) == {'selections': split(3)}
    assert 'Romans: remove' in output.getvalue()


@pytest.mark.parametrize('card', [3, 5, 'A5'])
def test_roman_choice_on_another_seats_event_stays_pending_and_replays(card, tmp_path):
    state = position(card)
    initial = encode(board_copy(state))

    def session_for(board, meta=None, log=None):
        session = SeatSession(board, meta or {'seat': rc.ROMANS},
                              [] if log is None else log, HumanTurnDisplay(StringIO()))
        board['decision_agent'] = lambda b, f, r: session.reactive(b, f, r) if r['kind'] == KIND else None
        return session

    def attempt(session):
        def driver(*args):
            pass
        driver.transaction_checkpoint = session.checkpoint
        driver.transaction_restore = session.restore
        with _action_transaction(session.state, driver):
            return _execute_event(session.state, rc.AEDUI, action(card), human=False)

    session = session_for(state)
    with pytest.raises(DecisionPending):
        attempt(session)
    pending = deepcopy(session.data['pending'])
    assert decode(pending['request'])['owner'] == rc.ROMANS
    session.import_inbox({'decision_id': pending['id'], 'response': {'selections': []}})
    with pytest.raises(DecisionPending):
        attempt(session)
    assert session.error and session.data['pending'] == pending
    assert encode(board_copy(state)) == initial

    path = tmp_path / 'choice.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session_for(restored, meta, log)
    with pytest.raises(DecisionPending):
        attempt(resumed)
    assert resumed.data['pending'] == pending
    response = {'selections': split(card)}
    resumed.import_inbox({'decision_id': pending['id'], 'response': response})
    result = attempt(resumed)
    resumed.finish()
    original = decode(initial)
    original['decision_agent'] = lambda b, f, r: response if r['kind'] == KIND else None
    assert result['executed'] and _execute_event(original, rc.AEDUI, action(card)) == result
    assert encode(board_copy(restored)) == encode(board_copy(original))
    assert len(log) == 1 and validate_state(restored) == []


@pytest.mark.parametrize('card', [3, 5, 'A5'])
def test_preview_does_not_consume_live_roman_input(card):
    from fs_bot.cards.event_preview import preview_event_prefix
    state = position(card)
    state['decision_agent'] = lambda *args: pytest.fail('Preview used live input')
    before = encode(board_copy(state))
    preview_event_prefix(state, rc.AEDUI, card, True, {}, step=f'{card}.piece_choice', index=None)
    assert encode(board_copy(state)) == before


def test_a5_terminal_offers_cisalpina_and_exact_auxilia():
    from fs_bot.cli.human_plan import _collect_event_params

    state = position('A5')
    place_piece(state, rc.CISALPINA, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(state, rc.CISALPINA, rc.ROMANS, rc.AUXILIA, piece_state=rc.SCOUTED)
    output = StringIO()
    assert _collect_event_params(state, rc.GERMANS, 'A5', True, StringIO(), output) == {}
    request = roman_removal_request(state, 'A5')
    chosen = [cohort(rc.CISALPINA), cohort(rc.CISALPINA, rc.AUXILIA, rc.SCOUTED),
              cohort(rc.SEQUANI, rc.AUXILIA, rc.REVEALED)]
    legions = [e for e in request['available'] if e['piece_type'] == rc.LEGION]
    auxilia = [e for e in request['available'] if e['piece_type'] == rc.AUXILIA]
    inputs = f'board\n{legions.index(chosen[0]) + 1}\n1\n'
    inputs += f'{auxilia.index(chosen[1]) + 1}\n1\n'
    auxilia.remove(chosen[1])
    inputs += f'{auxilia.index(dict(chosen[2], count=2)) + 1}\n1\n'
    agent = make_cli_reactive({rc.ROMANS}, StringIO(inputs), output)
    state['decision_agent'] = agent
    assert _execute_event(state, rc.GERMANS, action('A5'), human=True)['executed']
    assert 'Romans: remove' in output.getvalue()
    assert count_pieces(state, rc.CISALPINA, rc.ROMANS, rc.LEGION) == 0
    assert count_pieces(state, rc.CISALPINA, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces_by_state(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 1
    assert validate_state(state) == []


def test_a5_delegated_auxilia_removals_favor_scouted_then_revealed():
    state = position('A5')
    remove_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 6)
    remove_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, piece_state=rc.SCOUTED)
    execute_event(state, 'A5', shaded=True)
    assert count_pieces_by_state(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, rc.SCOUTED) == 0
    assert count_pieces_by_state(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 1
    assert count_pieces_by_state(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 2


def test_a5_bot_declines_shaded_event_when_senate_is_in_adulation():
    from fs_bot.cards.event_eval import is_event_effective, should_skip_event

    state = position('A5')
    assert is_event_effective(state, 'A5', shaded=True)
    state['senate']['position'] = rc.ADULATION
    assert should_skip_event(state, 'A5', rc.GERMANS)
    assert is_event_effective(state, 'A5', shaded=False)


def test_a5_legacy_plan_keeps_chosen_regions_and_fills_missing_removal():
    state = position('A5')
    params = {'legion_region': rc.PROVINCIA, 'auxilia_removals': [{'region': rc.SEQUANI}]}
    before = get_available(state, rc.ROMANS, rc.AUXILIA)
    assert _execute_event(state, rc.ROMANS, action('A5', params), human=True)['executed']
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == 1
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.LEGION) == 2
    assert count_pieces_by_state(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 1
    assert get_available(state, rc.ROMANS, rc.AUXILIA) == before + 2
    assert validate_state(state) == []
