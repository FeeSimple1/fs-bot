"""EXP-09: printed scope/quota/ownership before a human Event commits."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_available, place_piece
from fs_bot.cards.card_effects import execute_event, _ally_tribe
from fs_bot.cards.expansion_validation import default_params, np_available, preview, region_options, validate_response
from fs_bot.engine.execute import _execute_event
from fs_bot.engine.moves import validate_player_action
from fs_bot.engine.action_windows import scope
from fs_bot.engine.game_engine import _action_transaction
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import encode, decode, save_game, load_game
from fs_bot.tools.seat_session import SeatSession, DecisionPending, board_copy


def board(card='A29', executor=rc.AEDUI):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=317)
    state['non_player_factions'] = set()
    state['current_card'], state['next_card'] = card, 'A67'
    state['executing_faction'] = executor
    state['event_params'] = None
    return state


def action(card, params):
    return {'command': rc.FIRST_DID_EVENT, 'regions': [], 'sa': 'No SA', 'sa_regions': [],
            'details': {'card_id': card, 'text_preference': rc.EVENT_SHADED if card == 'A36' else rc.EVENT_UNSHADED,
                        'event_params': params}}


def run(state, card, params, executor=None):
    return _execute_event(state, executor or state['executing_faction'], action(card, params), human=True)


def troops(owner=rc.AEDUI, count=5, region=rc.SEQUANI):
    return {'region': region, 'piece_type': rc.AUXILIA if owner == rc.ROMANS else rc.WARBAND,
            'faction': owner, 'count': count}


def a36_plan(state):
    regions = region_options(state, 'A36')
    return {'placements': [{'region': regions[0], 'piece_type': rc.SETTLEMENT},
                           {'region': regions[1], 'piece_type': rc.SETTLEMENT},
                           {'region': regions[0], 'piece_type': rc.WARBAND, 'count': 4}],
            'ally_removals': []}


def sources43(state):
    _ally_tribe(state, rc.TRIBE_SEQUANI, rc.ARVERNI)
    _ally_tribe(state, rc.TRIBE_HELVETII, rc.ARVERNI)
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 2, piece_state=rc.SCOUTED)
    return {'replacements': [
        {'region': rc.SEQUANI, 'from_type': rc.ALLY, 'tribe': tribe, 'to_faction': rc.AEDUI}
        for tribe in (rc.TRIBE_SEQUANI, rc.TRIBE_HELVETII)] + [
        {'region': rc.SEQUANI, 'from_type': rc.WARBAND, 'piece_state': rc.SCOUTED,
         'to_faction': rc.ROMANS} for _ in range(2)]}


@pytest.mark.parametrize('card,executor,params', [
    ('A29', rc.GERMANS, {'placements': [troops(rc.GERMANS)]}),
    ('A29', rc.AEDUI, {'placements': [troops(rc.AEDUI, 6)]}),
    ('A29', rc.AEDUI, {'placements': [troops(rc.AEDUI, 3), troops(rc.ROMANS, 2)]}),
    ('A29', rc.AEDUI, {'placements': [troops(rc.AEDUI, 5, rc.MORINI)]}),
    ('A29', rc.AEDUI, {'placements': [troops(rc.AEDUI, True)]}),
    ('A29', rc.AEDUI, {'placements': [troops(rc.AEDUI, -1)]}),
    ('A29', rc.AEDUI, {'placements': [dict(troops(), faction=[])]}),
    ('A30', rc.ROMANS, {'region': rc.MORINI}),
    ('A30', rc.ROMANS, {'regions': [rc.SEQUANI, rc.AEDUI_REGION]}),
    ('A36', rc.GERMANS, {'placements': [{'region': rc.SUGAMBRI, 'piece_type': rc.WARBAND, 'count': 10}]}),
    ('A36', rc.GERMANS, {'placements': [{'region': rc.MORINI, 'piece_type': rc.LEGION}]}),
    ('A43', rc.AEDUI, {'replacements': [{'region': rc.MORINI, 'from_type': rc.WARBAND, 'to_faction': rc.AEDUI}]}),
    ('A43', rc.AEDUI, {'replacements': [{'region': rc.SEQUANI, 'from_type': rc.WARBAND, 'to_faction': rc.GERMANS}]}),
    ('A43', rc.AEDUI, {'replacements': [{'region': rc.SEQUANI, 'from_type': rc.WARBAND, 'to_faction': rc.AEDUI}] * 3}),
    ('A45', rc.AEDUI, {'placements': [{'tribe': rc.TRIBE_SEQUANI, 'faction': rc.AEDUI}]}),
    ('A45', rc.AEDUI, {'placements': [{'tribe': rc.TRIBE_SEQUANI, 'faction': rc.GERMANS}]}),
])
def test_invalid_printed_scope_or_quota_is_atomic_and_fails_public_validation(card, executor, params):
    state = board(card, executor)
    place_piece(state, rc.SEQUANI, rc.GERMANS, rc.SETTLEMENT)
    place_piece(state, rc.MORINI, rc.ARVERNI, rc.WARBAND, 5)
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 5)
    before = encode(board_copy(state))
    rng = state['rng'].getstate()
    ok, _ = validate_player_action(state, executor, action(card, params))
    assert not ok
    assert encode(board_copy(state)) == before and state['rng'].getstate() == rng
    result = run(state, card, params)
    assert not result['executed'], result
    assert encode(board_copy(state)) == before


def test_a29_allies_optional_but_five_troops_mandatory_with_one_beneficiary():
    state = board()
    place_piece(state, rc.SEQUANI, rc.GERMANS, rc.SETTLEMENT)
    before = encode(board_copy(state))
    assert not run(state, 'A29', {'placements': [troops(count=4)]})['executed']
    assert encode(board_copy(state)) == before
    assert run(state, 'A29', {'placements': [troops()]})['executed']
    assert count_pieces(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == 5
    assert count_pieces(state, rc.SEQUANI, rc.AEDUI, rc.ALLY) == 0
    assert validate_state(state) == []


def test_a29_scarce_troops_partial_and_roman_np_full_count_are_distinct():
    state = board(executor=rc.ROMANS)
    place_piece(state, rc.SEQUANI, rc.GERMANS, rc.SETTLEMENT)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, get_available(state, rc.ROMANS, rc.AUXILIA)-1)
    assert not np_available(state, 'A29', rc.ROMANS)
    assert run(state, 'A29', {'placements': [troops(rc.ROMANS, 1)]})['executed']
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 1


def test_a29_exact_owner_and_tribe_duplicates_are_rejected_before_troops():
    state = board()
    place_piece(state, rc.SEQUANI, rc.GERMANS, rc.SETTLEMENT)
    ally = {'region': rc.SEQUANI, 'piece_type': rc.ALLY, 'tribe': rc.TRIBE_SEQUANI, 'faction': rc.AEDUI}
    before = encode(board_copy(state))
    assert not run(state, 'A29', {'placements': [troops(), ally, ally]})['executed']
    assert encode(board_copy(state)) == before


def test_a30_removes_all_physical_visibility_and_exact_tribe_in_range():
    state = board('A30', rc.ROMANS)
    for visibility in (rc.HIDDEN, rc.REVEALED, rc.SCOUTED):
        place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, piece_state=visibility)
    _ally_tribe(state, rc.TRIBE_HELVETII, rc.ARVERNI)
    assert run(state, 'A30', {'region': rc.SEQUANI})['executed']
    assert count_pieces(state, rc.SEQUANI, rc.ARVERNI) == 0
    assert state['tribes'][rc.TRIBE_HELVETII]['allied_faction'] is None
    assert run(state, 'A30', {'region': rc.SEQUANI})['executed']  # a legal empty selection
    assert validate_state(state) == []


def test_a30_region_priority_prefers_citadel_over_leader():
    # A deliberate generic-default position: normal Ariovistus play has no
    # Arverni Leader. Region choice follows §8.3.1, not the once-selected
    # piece ordering in §8.4.1, even when a Leader is present.
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=317)
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.LEADER,
                leader_name=rc.VERCINGETORIX)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.CITADEL)
    state['tribes'][rc.TRIBE_ARVERNI]['allied_faction'] = rc.ARVERNI
    before = encode(state)
    assert default_params(state, 'A30', rc.AEDUI) == {'region': rc.ARVERNI_REGION}
    assert encode(state) == before


def test_a36_complete_fixed_placements_and_distinct_settlement_slots():
    state = board('A36', rc.GERMANS)
    plan = a36_plan(state)
    plan['placements'][1]['region'] = plan['placements'][0]['region']
    before = encode(board_copy(state))
    assert not run(state, 'A36', plan)['executed']
    assert encode(board_copy(state)) == before
    assert run(state, 'A36', a36_plan(state))['executed']
    assert sum(count_pieces(state, r, rc.GERMANS, rc.SETTLEMENT) for r in state['spaces']) == 2
    assert sum(count_pieces(state, r, rc.GERMANS, rc.WARBAND) for r in state['spaces']) == 4
    assert validate_state(state) == []


def test_a36_removal_is_exact_two_existing_allies_not_citadels():
    state = board('A36', rc.GERMANS)
    _ally_tribe(state, rc.TRIBE_TREVERI, rc.BELGAE)
    _ally_tribe(state, rc.TRIBE_NERVII, rc.BELGAE)
    plan = a36_plan(state)
    before = encode(board_copy(state))
    assert not run(state, 'A36', plan)['executed']
    assert encode(board_copy(state)) == before
    plan['ally_removals'] = [{'tribe': rc.TRIBE_TREVERI}, {'tribe': rc.TRIBE_NERVII}]
    assert run(state, 'A36', plan)['executed']
    assert state['tribes'][rc.TRIBE_TREVERI]['allied_faction'] is None
    assert state['tribes'][rc.TRIBE_NERVII]['allied_faction'] is None


def test_a43_exact_sources_and_scarce_replacements_still_remove_all_sources():
    state = board('A43', rc.AEDUI)
    params = sources43(state)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, get_available(state, rc.ROMANS, rc.AUXILIA))
    assert run(state, 'A43', params)['executed']
    assert count_pieces(state, rc.SEQUANI, rc.ARVERNI) == 0
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(state, rc.SEQUANI, rc.AEDUI, rc.ALLY) == 2
    assert validate_state(state) == []


def test_a43_partial_sources_and_bibracte_unshaded_stacking_fallback():
    state = board('A43', rc.ROMANS)
    # A30 shaded legally creates this exceptional Arverni Ally at Bibracte.
    _ally_tribe(state, rc.TRIBE_AEDUI, rc.ARVERNI)
    params = {'replacements': [{'region': rc.AEDUI_REGION, 'tribe': rc.TRIBE_AEDUI,
                               'from_type': rc.ALLY, 'to_faction': rc.ROMANS}]}
    assert run(state, 'A43', params)['executed']
    assert state['tribes'][rc.TRIBE_AEDUI]['allied_faction'] is None
    assert count_pieces(state, rc.AEDUI_REGION, rc.ROMANS, rc.ALLY) == 0


def test_a43_repeated_exact_warband_rolls_back_instead_of_substituting_visibility():
    state = board('A43', rc.AEDUI)
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, piece_state=rc.REVEALED)
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, piece_state=rc.HIDDEN)
    entry = {'region': rc.SEQUANI, 'from_type': rc.WARBAND, 'piece_state': rc.REVEALED, 'to_faction': rc.AEDUI}
    before = encode(board_copy(state))
    assert not run(state, 'A43', {'replacements': [entry, entry]})['executed']
    assert encode(board_copy(state)) == before


@pytest.mark.parametrize('change', [
    {'piece_type': rc.WARBAND}, {'count': 2}, {'count': False},
    {'region': rc.MORINI}, {'acting_faction': rc.GERMANS},
])
def test_a45_rejects_ignored_or_malformed_entry_fields(change):
    state = board('A45')
    state['markers'][rc.SEQUANI] = {rc.MARKER_INTIMIDATED: True}
    entry = dict(tribe=rc.TRIBE_SEQUANI, faction=rc.AEDUI, **change)
    before = encode(board_copy(state))
    assert not run(state, 'A45', {'placements': [entry]})['executed']
    assert encode(board_copy(state)) == before


def test_a45_celtica_marker_region_is_legal_and_zero_is_optional():
    state = board('A45')
    state['markers'][rc.SEQUANI] = {rc.MARKER_INTIMIDATED: True}
    assert run(state, 'A45', {'placements': []})['executed']
    assert run(state, 'A45', {'placements': [{'tribe': rc.TRIBE_SEQUANI, 'faction': rc.BELGAE}]})['executed']
    assert state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] == rc.BELGAE


def test_named_german_actor_cannot_be_commanded_by_executor_params():
    state = board('A36', rc.ROMANS)
    before = encode(board_copy(state))
    assert not run(state, 'A36', a36_plan(state))['executed']
    assert encode(board_copy(state)) == before
    seen = []
    def agent(st, owner, request):
        seen.append((owner, request['acting_faction']))
        return a36_plan(st)
    state['decision_agent'] = agent
    assert run(state, 'A36', {})['executed']
    assert seen == [(rc.GERMANS, rc.GERMANS)]


@pytest.mark.parametrize('card,seat,executor', [('A29', rc.AEDUI, rc.ROMANS), ('A36', rc.GERMANS, rc.ROMANS)])
def test_named_owner_pending_invalid_save_load_and_replay(tmp_path, card, seat, executor):
    state = board(card, executor)
    if card == 'A29':
        place_piece(state, rc.SEQUANI, rc.GERMANS, rc.SETTLEMENT)
    initial = deepcopy(state)
    params = {'faction': seat} if card == 'A29' else {}
    def session(st, meta=None, log=None):
        ses = SeatSession(st, meta or {'seat': seat}, [] if log is None else log, HumanTurnDisplay(StringIO()))
        st['decision_agent'] = ses.reactive
        return ses
    def step(ses):
        def driver(*args): pass
        driver.transaction_checkpoint, driver.transaction_restore = ses.checkpoint, ses.restore
        with _action_transaction(ses.state, driver):
            return run(ses.state, card, params, executor)
    ses = session(state)
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending): step(ses)
    pending = deepcopy(ses.data['pending'])
    assert decode(pending['request'])['faction'] == seat
    ses.import_inbox({'decision_id': pending['id'], 'response': {'placements': []}})
    with pytest.raises(DecisionPending): step(ses)
    assert ses.data['pending']['id'] == pending['id'] and ses.error
    assert encode(board_copy(state)) == before
    response = {'placements': [troops(seat)]} if card == 'A29' else a36_plan(state)
    ses.import_inbox({'decision_id': pending['id'], 'response': response})
    path = tmp_path/'pending.json'
    save_game(state, path, meta=ses.meta, log=ses.log)
    restored, meta, log = load_game(path)
    resumed = session(restored, meta, log)
    result = step(resumed)
    resumed.finish()
    assert result['executed'] and validate_state(restored) == []
    initial['decision_agent'] = lambda *args: decode(log[0]['assistant_response'])
    assert run(initial, card, params, executor) == result
    assert encode(board_copy(initial)) == encode(board_copy(restored))


def test_foreign_beneficiary_cannot_author_executor_voluntary_removal():
    state = board('A29', rc.ROMANS)
    place_piece(state, rc.SEQUANI, rc.GERMANS, rc.SETTLEMENT)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA)
    response = {'placements': [dict(troops(), timing_actions=[{'kind': 'voluntary_removal', 'response': {
        'operations': [{'action': 'remove', 'region': rc.PROVINCIA, 'piece_type': rc.AUXILIA,
                        'piece_state': rc.HIDDEN, 'count': 1}]}}])]}
    before = encode(board_copy(state))
    with scope(state, actor=rc.ROMANS, force=True):
        with pytest.raises(Exception):
            validate_response(state, rc.AEDUI, {'card_id': 'A29'}, response)
    assert encode(board_copy(state)) == before


@pytest.mark.parametrize('validate', [False, True])
def test_foreign_beneficiary_has_no_removal_authority_without_an_outer_scope(validate):
    state = board('A29', rc.ROMANS)
    place_piece(state, rc.SEQUANI, rc.GERMANS, rc.SETTLEMENT)
    place_piece(state, rc.PROVINCIA, rc.AEDUI, rc.WARBAND)
    response = {'placements': [dict(troops(), timing_actions=[{'kind': 'voluntary_removal', 'response': {
        'operations': [{'action': 'remove', 'region': rc.PROVINCIA, 'piece_type': rc.WARBAND,
                        'piece_state': rc.HIDDEN, 'count': 1}]}}])]}
    before = encode(board_copy(state))
    with pytest.raises(Exception, match='Only the executing player'):
        if validate:
            validate_response(state, rc.AEDUI, {'card_id': 'A29'}, response)
        else:
            preview(state, 'A29', rc.AEDUI, response)
    assert encode(board_copy(state)) == before


def test_np_defaults_do_not_place_other_factions_when_own_allies_exhausted():
    state = board('A45')
    state['markers'][rc.SEQUANI] = {rc.MARKER_INTIMIDATED: True}
    # Put all Aedui discs elsewhere, leaving eligible slots for other owners.
    for tribe in state['tribes']:
        if rc.TRIBE_TO_REGION.get(tribe) != rc.SEQUANI and rc.TRIBE_FACTION_RESTRICTION.get(tribe, rc.AEDUI) == rc.AEDUI:
            _ally_tribe(state, tribe, rc.AEDUI)
    assert get_available(state, rc.AEDUI, rc.ALLY) == 0
    assert not np_available(state, 'A45', rc.AEDUI)
    assert default_params(state, 'A45', rc.AEDUI).get('placements', []) == []


def test_a43_np_shortage_declines_only_when_other_recipient_could_place():
    state = board('A43', rc.ROMANS)
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 2)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, get_available(state, rc.ROMANS, rc.AUXILIA))
    assert not np_available(state, 'A43', rc.ROMANS)
    place_piece(state, rc.VENETI, rc.AEDUI, rc.WARBAND, get_available(state, rc.AEDUI, rc.WARBAND))
    assert np_available(state, 'A43', rc.ROMANS)
    assert run(state, 'A43', default_params(state, 'A43', rc.ROMANS))['executed']
    assert count_pieces(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND) == 0
