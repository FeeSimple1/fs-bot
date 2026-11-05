"""Card Reference 19/22: optional totals and exact remove/replace selections."""
from copy import deepcopy
from io import StringIO
import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, place_piece, remove_piece, get_available
from fs_bot.cards.card_effects import execute_event
from fs_bot.cards.base_piece_choices import KIND, choice_request, validate_response
from fs_bot.engine.execute import _execute_event
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import encode, decode, save_game, load_game

REGIONS = (rc.SEQUANI, rc.ARVERNI_REGION)


def position(card=19, scenario=rc.SCENARIO_GREAT_REVOLT, owner=rc.AEDUI):
    state = build_initial_state(scenario, seed=17)
    state['non_player_factions'] = set()
    state['executing_faction'] = owner
    state['event_params'] = {}
    state['current_card'], state['next_card'] = card, 67
    for region in REGIONS:
        place_piece(state, region, rc.ARVERNI, rc.WARBAND, 2, piece_state=rc.HIDDEN)
        place_piece(state, region, rc.ARVERNI, rc.WARBAND, 2, piece_state=rc.REVEALED)
        place_piece(state, region, rc.ARVERNI, rc.WARBAND, 2, piece_state=rc.SCOUTED)
        if card == 22:
            if owner == rc.ROMANS:
                place_piece(state, region, owner, rc.AUXILIA, 8)
            else:
                place_piece(state, region, owner, rc.WARBAND, 9)
                place_piece(state, region, rc.ROMANS, rc.AUXILIA, 2, piece_state=rc.REVEALED)
    return state


def cohort(region=REGIONS[0], faction=rc.ARVERNI, kind=rc.WARBAND, visibility=rc.SCOUTED, count=1, action=None):
    entry = {'region': region, 'target_faction': faction, 'piece_type': kind,
             'piece_state': visibility, 'count': count}
    if action is not None: entry['action'] = action
    return entry


def action(card, params=None):
    return {'command': rc.FIRST_DID_EVENT, 'regions': [], 'sa': None, 'sa_regions': [],
            'details': {'card_id': card, 'text_preference': rc.EVENT_UNSHADED,
                        'event_params': {} if params is None else params}}


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
@pytest.mark.parametrize('count', [0, 1, 3, 5])
def test_lucterius_all_scenarios_exact_auxilia_quantities(scenario, count):
    state = position(scenario=scenario)
    state['event_params'] = {'choice': 'auxilia', 'count': count}
    execute_event(state, 19)
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == count
    assert validate_state(state) == []


@pytest.mark.parametrize('count', [0, 1, 2, 6])
def test_lucterius_exact_warband_totals_and_visibility(count):
    state = position()
    entries = []
    remaining = count
    for visibility in (rc.SCOUTED, rc.REVEALED, rc.HIDDEN):
        n = min(2, remaining)
        if n: entries.append(cohort(visibility=visibility, count=n))
        remaining -= n
    state['event_params'] = {'choice': 'warbands', 'removals': entries}
    execute_event(state, 19)
    assert count_pieces(state, REGIONS[0], rc.ARVERNI, rc.WARBAND) == 6-count
    assert count_pieces(state, REGIONS[1], rc.ARVERNI, rc.WARBAND) == 6
    assert count_pieces_by_state(state, REGIONS[0], rc.ARVERNI, rc.WARBAND, rc.SCOUTED) == max(0, 2-count)
    assert validate_state(state) == []


def test_lucterius_scarce_auxilia_places_only_available():
    state = position()
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA, get_available(state, rc.ROMANS, rc.AUXILIA)-2)
    state['event_params'] = {'choice': 'auxilia', 'count': 5}
    execute_event(state, 19)
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 2
    assert validate_state(state) == []


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
@pytest.mark.parametrize('mode', ['remove', 'replace'])
def test_hostages_optional_action_and_exact_identity(scenario, mode):
    state = position(22, scenario)
    before = count_pieces(state, REGIONS[0], rc.AEDUI, rc.WARBAND)
    state['event_params'] = {'piece_choices': [cohort(count=2, action=mode)]}
    execute_event(state, 22)
    assert count_pieces_by_state(state, REGIONS[0], rc.ARVERNI, rc.WARBAND, rc.SCOUTED) == 0
    assert count_pieces_by_state(state, REGIONS[0], rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 2
    assert count_pieces(state, REGIONS[0], rc.AEDUI, rc.WARBAND) == before + (2 if mode == 'replace' else 0)
    assert validate_state(state) == []


def test_hostages_mixed_removal_and_replacement_across_regions():
    state = position(22)
    state['event_params'] = {'piece_choices': [cohort(count=2, action='remove'),
        cohort(region=REGIONS[1], faction=rc.ROMANS, kind=rc.AUXILIA, visibility=rc.REVEALED, count=2, action='replace')]}
    execute_event(state, 22)
    assert count_pieces(state, REGIONS[0], rc.AEDUI, rc.WARBAND) == 9
    assert count_pieces(state, REGIONS[1], rc.AEDUI, rc.WARBAND) == 11
    assert count_pieces(state, REGIONS[1], rc.ROMANS, rc.AUXILIA) == 0
    assert validate_state(state) == []


def test_hostages_roman_replacement_uses_auxilia():
    state = position(22, owner=rc.ROMANS)
    state['event_params'] = {'piece_choices': [cohort(count=2, action='replace')]}
    execute_event(state, 22)
    assert count_pieces(state, REGIONS[0], rc.ROMANS, rc.AUXILIA) == 10
    assert validate_state(state) == []


def test_hostages_replacement_unavailable_still_removes():
    state = position(22)
    place_piece(state, rc.TREVERI, rc.AEDUI, rc.WARBAND, get_available(state, rc.AEDUI, rc.WARBAND))
    state['event_params'] = {'piece_choices': [cohort(count=2, action='replace')]}
    execute_event(state, 22)
    assert count_pieces(state, REGIONS[0], rc.ARVERNI, rc.WARBAND) == 4
    assert count_pieces(state, REGIONS[0], rc.AEDUI, rc.WARBAND) == 9
    assert validate_state(state) == []


def test_hostages_own_piece_removal_is_legal_and_scope_is_selected_before_removal():
    state = position(22)
    # Begin with 9 Aedui versus 8 other pieces; removing four loses Control.
    state['event_params'] = {'piece_choices': [cohort(faction=rc.AEDUI, visibility=rc.HIDDEN, count=4, action='remove')]}
    execute_event(state, 22)
    assert count_pieces(state, REGIONS[0], rc.AEDUI, rc.WARBAND) == 5
    assert validate_state(state) == []


@pytest.mark.parametrize('card', [19, 22])
def test_explicit_zero_and_default_delegation(card):
    state = position(card)
    seen = []
    def agent(board, faction, request):
        if request['kind'] == KIND:
            assert faction == rc.AEDUI
            seen.append(request)
            return {'choice': 'warbands', 'removals': []} if card == 19 else {'selections': []}
    state['decision_agent'] = agent
    execute_event(state, card)
    assert len(seen) == 1
    assert count_pieces(state, REGIONS[0], rc.ARVERNI, rc.WARBAND) == 6


@pytest.mark.parametrize('card', [19, 22])
@pytest.mark.parametrize('bad', [None, {}, {'use_default': 1}])
def test_strict_response_shape_rejected_without_mutation(card, bad):
    state = position(card)
    request = choice_request(state, card)
    before = encode(state)
    with pytest.raises(ValueError): validate_response(state, request, bad)
    assert encode(state) == before


@pytest.mark.parametrize('bad', [-1, 6, True, 1.5, '2'])
def test_lucterius_invalid_auxilia_quantity(bad):
    state = position(); state['event_params'] = {'choice': 'auxilia', 'count': bad}
    before = encode(state)
    with pytest.raises(ValueError): execute_event(state, 19)
    assert encode(state) == before


@pytest.mark.parametrize('card', [19, 22])
@pytest.mark.parametrize('change', ['outside', 'overcount', 'duplicate', 'type', 'owner', 'visibility', 'boolean'])
def test_invalid_physical_totals_and_scopes(card, change):
    state = position(card)
    entry = cohort(action='remove' if card == 22 else None)
    entries = [entry]
    if change == 'outside': entry['region'] = rc.TREVERI
    elif change == 'overcount': entry['count'] = 7
    elif change == 'duplicate': entries += [dict(entry, count=2)]
    elif change == 'type': entry['piece_type'] = rc.LEGION
    elif change == 'owner': entry['target_faction'] = rc.GERMANS
    elif change == 'visibility': entry['piece_state'] = 'invalid'
    elif change == 'boolean': entry['count'] = True
    response = {'choice': 'warbands', 'removals': entries} if card == 19 else {'selections': entries}
    before = encode(state)
    with pytest.raises(ValueError): validate_response(state, choice_request(state, card), response)
    assert encode(state) == before


@pytest.mark.parametrize('card', [19, 22])
def test_stale_cohort_rejected(card):
    state = position(card)
    request = choice_request(state, card)
    remove_piece(state, REGIONS[0], rc.ARVERNI, rc.WARBAND, 2, piece_state=rc.SCOUTED)
    response = ({'choice': 'warbands', 'removals': [cohort()]} if card == 19
                else {'selections': [cohort(action='remove')]})
    with pytest.raises(ValueError): validate_response(state, request, response)


def test_legacy_hostages_gallic_auxilia_replacement_uses_warband():
    state = position(22)
    state['event_params'] = {'replacements': [{'region': REGIONS[0], 'target_faction': rc.ROMANS, 'piece_type': rc.AUXILIA}]}
    execute_event(state, 22)
    assert count_pieces(state, REGIONS[0], rc.AEDUI, rc.WARBAND) == 10
    assert validate_state(state) == []


@pytest.mark.parametrize('card,inputs,response', [(19, 'board\n1\n1\n', {'choice': 'auxilia', 'count': 0}),
    (19, 'board\n2\n1\n', {'choice': 'warbands', 'removals': []}), (22, 'board\n1\n', {'selections': []})])
def test_terminal_zero_choice_inspection(card, inputs, response):
    from fs_bot.cli.reactive import make_cli_reactive
    state = position(card); output = StringIO(); before = encode(state)
    assert make_cli_reactive({rc.AEDUI}, StringIO(inputs), output)(state, rc.AEDUI, choice_request(state, card)) == response
    assert encode(state) == before and output.getvalue()


@pytest.mark.parametrize('card', [19, 22])
def test_terminal_planning_defers_to_live_choice(card):
    from fs_bot.cli.human_plan import _collect_event_params
    assert _collect_event_params(position(card), rc.AEDUI, card, False, StringIO(), StringIO()) == {}


def session_for(state, meta=None, log=None):
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.tools.seat_session import SeatSession
    session = SeatSession(state, meta or {'seat': rc.AEDUI}, log if log is not None else [], HumanTurnDisplay(StringIO()))
    state['decision_agent'] = lambda board, faction, request: (
        session.reactive(board, faction, request) if request['kind'] == KIND else None)
    return session


def attempt(session, card):
    from fs_bot.engine.game_engine import _action_transaction
    def driver(*args): pass
    driver.transaction_checkpoint, driver.transaction_restore = session.checkpoint, session.restore
    with _action_transaction(session.state, driver):
        return _execute_event(session.state, rc.AEDUI, action(card), human=True)


@pytest.mark.parametrize('card', [19, 22])
@pytest.mark.parametrize('bad', [None, {}, {'use_default': 1}])
def test_pending_invalid_save_load_acceptance_and_exact_replay(card, bad, tmp_path):
    from fs_bot.tools.seat_session import DecisionPending, board_copy
    state = position(card); origin = decode(encode(state)); session = session_for(state)
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending): attempt(session, card)
    pending = deepcopy(session.data['pending'])
    session.import_inbox({'decision_id': pending['id'], 'response': bad})
    with pytest.raises(DecisionPending): attempt(session, card)
    assert session.error and session.data['pending'] == pending
    assert encode(board_copy(state)) == before
    path = tmp_path / 'choice.json'; save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True); resumed = session_for(restored, meta, log)
    with pytest.raises(DecisionPending): attempt(resumed, card)
    assert resumed.data['pending'] == pending
    response = ({'choice': 'warbands', 'removals': [cohort()]} if card == 19 else {'selections': [cohort(action='remove')]})
    resumed.import_inbox({'decision_id': pending['id'], 'response': response})
    result = attempt(resumed, card); resumed.finish()
    origin['decision_agent'] = lambda b, f, r: response if r['kind'] == KIND else None
    assert _execute_event(origin, rc.AEDUI, action(card), human=True) == result
    assert encode(board_copy(restored)) == encode(board_copy(origin)) and len(log) == 1
    assert validate_state(restored) == []


@pytest.mark.parametrize('card', [19, 22])
def test_preview_does_not_consume_live_input_or_rng(card):
    from fs_bot.cards.event_preview import preview_event_prefix
    from fs_bot.tools.seat_session import board_copy
    state = position(card)
    state['decision_agent'] = lambda *a: pytest.fail('Preview used live input')
    before = encode(board_copy(state))
    preview_event_prefix(state, rc.AEDUI, card, False, {}, step=f'{card}.piece_choice', index=None)
    assert encode(board_copy(state)) == before


def test_hostages_stale_control_rejected():
    state = position(22); request = choice_request(state, 22)
    remove_piece(state, REGIONS[0], rc.AEDUI, rc.WARBAND, 4)
    with pytest.raises(ValueError):
        validate_response(state, request, {'selections': [cohort(action='remove')]})


@pytest.mark.parametrize('visibility', [rc.HIDDEN, rc.REVEALED, rc.SCOUTED])
def test_terminal_hostages_nonzero_removal_or_replacement(visibility):
    from fs_bot.cli.reactive import make_cli_reactive
    state = position(22); request = choice_request(state, 22)
    selected = cohort(visibility=visibility, count=2, action='remove')
    index = next(i for i, e in enumerate(request['available']) if all(e[k] == selected[k]
                for k in ('region', 'target_faction', 'piece_type', 'piece_state')))
    inputs = f'{index+2}\n2\n1\n1\n'
    response = make_cli_reactive({rc.AEDUI}, StringIO(inputs), StringIO())(state, rc.AEDUI, request)
    assert response == {'selections': [selected]}


@pytest.mark.parametrize('card', [19, 22])
def test_invalid_new_plan_is_atomic_at_orchestrator(card):
    from fs_bot.tools.seat_session import board_copy
    state = position(card)
    params = ({'choice': 'warbands', 'removals': [cohort(), cohort(count=7)]} if card == 19
              else {'piece_choices': [cohort(action='remove'), cohort(count=7, action='replace')]})
    before = encode(board_copy(state))
    result = _execute_event(state, rc.AEDUI, action(card, params), human=True)
    assert not result['executed'] and result['rejected']
    assert encode(board_copy(state)) == before


def test_lucterius_live_reclamation_precedes_quantity():
    from fs_bot.engine.action_windows import scope
    state = position(owner=rc.ROMANS)
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA, get_available(state, rc.ROMANS, rc.AUXILIA))
    total = count_pieces(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA)
    state['event_params'] = {'choice': 'auxilia', 'count': 2,
        'stage_timing_actions': {'19.piece_choice': [
            {'kind': 'voluntary_removal', 'response': {'operations': [
                {'action': 'remove', 'region': rc.TREVERI, 'piece_type': rc.AUXILIA,
                 'piece_state': rc.HIDDEN, 'count': 2}]}}]}}
    with scope(state, actor=rc.ROMANS, plan=state['event_params'], force=True):
        execute_event(state, 19)
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA) == total-2
    assert validate_state(state) == []
