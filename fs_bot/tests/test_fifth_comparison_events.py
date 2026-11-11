"""Event ownership and map scope from the fifth comparison audit."""

from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, flip_piece, move_piece, place_piece
from fs_bot.cards.capabilities import get_capability_owner, is_capability_active
from fs_bot.cli.human_plan import _collect_event_params
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT, _action_transaction
from fs_bot.engine.moves import validate_player_action
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def board(scenario=rc.SCENARIO_GREAT_REVOLT, edition='second-edition'):
    state = setup_scenario(scenario, seed=17, card_edition=edition)
    state['non_player_factions'] = set()
    clean(state)
    return state


def clean(state):
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.FORT) == 1
    assert validate_state(state) == check_structural_integrity(state) == []


def event_plan(state, card, params, shaded=False, *, bot=False):
    state['current_card'] = state['current_card_id'] = card
    return {'action': ACTION_EVENT, 'bot_action' if bot else 'player_action': {
        'command': rc.FIRST_DID_EVENT, 'details': {
            'card_id': card, 'event_params': params,
            'text_preference': rc.EVENT_SHADED if shaded else rc.EVENT_UNSHADED}}}


def play(state, actor, card, params, shaded=False, *, bot=False):
    result = execute_decision(state, actor, event_plan(state, card, params, shaded, bot=bot))
    assert result['executed'] and not result.get('errors'), result
    clean(state)
    return result


def reject(state, actor, card, params, reason, shaded=False):
    plan = event_plan(state, card, params, shaded)
    before = encode(board_copy(state))
    ok, result = validate_player_action(state, actor, plan['player_action'])
    assert not ok and reason in result['reason']
    assert encode(board_copy(state)) == before
    result = execute_decision(state, actor, plan)
    assert result['rejected'] and not result['executed'] and reason in result['reason']
    assert encode(board_copy(state)) == before
    clean(state)


@pytest.mark.parametrize('card', [10, 63])
@pytest.mark.parametrize('actor,params', [
    (rc.ROMANS, {}), (rc.BELGAE, {}), (rc.BELGAE, {'faction': rc.ROMANS}),
    (rc.ROMANS, {'faction': rc.GERMANS}),
])
def test_shaded_capability_requires_an_explicit_gallic_recipient(card, actor, params):
    state = board()
    play(state, rc.ROMANS, card, {})
    reject(state, actor, card, params, 'Gallic Faction recipient', shaded=True)
    assert is_capability_active(state, card, rc.EVENT_UNSHADED)
    assert get_capability_owner(state, card) is None


@pytest.mark.parametrize('card', [10, 63])
@pytest.mark.parametrize('actor', [rc.ROMANS, rc.AEDUI])
def test_shaded_capability_can_be_given_to_belgae(card, actor):
    state = board(edition='original')
    play(state, actor, card, {'faction': rc.BELGAE}, shaded=True)
    assert is_capability_active(state, card, rc.EVENT_SHADED)
    assert get_capability_owner(state, card) == rc.BELGAE
    play(state, rc.ROMANS, card, {})
    assert is_capability_active(state, card, rc.EVENT_UNSHADED)
    assert get_capability_owner(state, card) is None


@pytest.mark.parametrize('card', [10, 63])
def test_non_player_selects_itself_for_shaded_capability(card):
    state = board()
    state['non_player_factions'].add(rc.BELGAE)
    play(state, rc.BELGAE, card, {}, shaded=True, bot=True)
    assert get_capability_owner(state, card) == rc.BELGAE


def test_invalid_recipient_stays_pending_and_can_be_corrected_after_reload(tmp_path):
    from fs_bot.cli.display import HumanTurnDisplay

    state = board()
    invalid = event_plan(state, 63, {'faction': rc.ROMANS}, shaded=True)
    request = {'kind': 'turn', 'options': [ACTION_EVENT], 'position': '1st_eligible'}
    before = encode(board_copy(state))

    def step(session):
        def driver(*args):
            return None

        driver.transaction_checkpoint = session.checkpoint
        driver.transaction_restore = session.restore
        with _action_transaction(session.state, driver):
            response = session.ask(session.state, rc.ROMANS, request)
            result = execute_decision(session.state, rc.ROMANS, response)
        session.finish()
        return result

    session = SeatSession(state, {'seat': rc.ROMANS}, [], HumanTurnDisplay(StringIO()))
    with pytest.raises(DecisionPending):
        step(session)
    pending = session.data['pending']['id']
    session.import_inbox({'decision_id': pending, 'response': invalid})
    with pytest.raises(DecisionPending):
        step(session)
    assert session.data['pending']['id'] == pending
    assert not session.log and not session.data['journal']
    assert encode(board_copy(state)) == before

    path = tmp_path / 'recipient.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = SeatSession(restored, meta, log, HumanTurnDisplay(StringIO()))
    valid = event_plan(restored, 63, {'faction': rc.BELGAE}, shaded=True)
    resumed.import_inbox({'decision_id': pending, 'response': valid})
    assert step(resumed)['executed']
    assert get_capability_owner(restored, 63) == rc.BELGAE
    assert decode(log[0]['assistant_response']) == valid
    assert resumed.data['pending'] is None
    clean(restored)


@pytest.mark.parametrize('scenario,region', [
    (rc.SCENARIO_GREAT_REVOLT, rc.CISALPINA),
    (rc.SCENARIO_GREAT_REVOLT, rc.AQUITANIA),
    (rc.SCENARIO_ARIOVISTUS, rc.BRITANNIA),
])
def test_colony_cannot_create_a_tribe_in_a_nonplayable_area(scenario, region):
    state = board(scenario)
    reject(state, rc.ROMANS, 71, {'region': region}, 'Colony requires a playable Region')


def test_colony_respects_gallia_togata_even_when_cisalpina_has_no_control():
    state = board()
    play(state, rc.ROMANS, 5, {})
    move_piece(state, rc.CISALPINA, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 3)
    reject(state, rc.BELGAE, 71, {'region': rc.CISALPINA}, 'Colony requires a playable Region')
    play(state, rc.ROMANS, 71, {'region': rc.CISALPINA})
    assert state['markers'][rc.CISALPINA][rc.MARKER_COLONY]
    assert state['tribes'][f'Colony_{rc.CISALPINA}']['allied_faction'] == rc.ROMANS
    assert count_pieces(state, rc.CISALPINA, rc.ROMANS, rc.ALLY) == 1


def test_colony_rejects_a_region_controlled_by_another_faction():
    state = board()
    reject(state, rc.BELGAE, 71, {'region': rc.PROVINCIA}, 'Colony requires a playable Region')


def test_roman_colony_bot_can_select_gallia_togata_cisalpina():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=17)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    state['non_player_factions'] = set()
    play(state, rc.ROMANS, 5, {})
    state['non_player_factions'].add(rc.ROMANS)
    play(state, rc.ROMANS, 71, {}, bot=True)
    assert state['tribes'][f'Colony_{rc.CISALPINA}']['allied_faction'] == rc.ROMANS


@pytest.mark.parametrize('origin,destination', [
    (rc.CISALPINA, rc.PROVINCIA), (rc.PROVINCIA, rc.CISALPINA),
])
@pytest.mark.parametrize('legacy_capability', [False, True])
def test_forced_marches_uses_gallia_togata_in_either_direction(origin, destination, legacy_capability):
    state = board()
    play(state, rc.ROMANS, 5, {})
    if legacy_capability:
        state['markers'][rc.CISALPINA].pop(rc.MARKER_GALLIA_TOGATA)
        state['capabilities'][rc.MARKER_GALLIA_TOGATA] = True
    flip_piece(state, origin, rc.ROMANS, rc.AUXILIA, 1, from_state=rc.HIDDEN, to_state=rc.REVEALED)
    hidden = count_pieces_by_state(state, destination, rc.ROMANS, rc.AUXILIA, rc.HIDDEN)
    play(state, rc.ROMANS, 32, {'moves': [{
        'from_region': origin, 'to_region': destination, 'piece_type': rc.AUXILIA,
        'piece_state': rc.REVEALED, 'count': 1}]})
    assert count_pieces_by_state(state, destination, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == hidden + 1
    assert count_pieces_by_state(state, origin, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 0


def test_forced_marches_respects_roman_only_cisalpina_on_legacy_boards():
    state = board()
    play(state, rc.ROMANS, 5, {})
    state['markers'][rc.CISALPINA].pop(rc.MARKER_GALLIA_TOGATA)
    state['capabilities'][rc.MARKER_GALLIA_TOGATA] = True
    reject(state, rc.ARVERNI, 32, {'moves': [{
        'from_region': rc.ARVERNI_REGION, 'to_region': rc.CISALPINA,
        'piece_type': rc.WARBAND, 'count': 1}]}, 'Forced Marches requires playable Regions')


@pytest.mark.parametrize('card', [10, 63])
def test_terminal_prompts_for_recipient_only_on_shaded_side(card):
    state = board()
    output = StringIO()
    assert _collect_event_params(state, rc.ROMANS, card, False, StringIO(''), output) == {}
    assert output.getvalue() == ''
    assert _collect_event_params(state, rc.ROMANS, card, True, StringIO('3\n'), output) == {
        'faction': rc.BELGAE}
    assert '(skip)' not in output.getvalue()


def test_terminal_colony_choices_respect_the_actors_map_and_control():
    state = board()
    play(state, rc.ROMANS, 5, {})
    move_piece(state, rc.CISALPINA, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 3)
    output = StringIO()
    params = _collect_event_params(state, rc.BELGAE, 71, False, StringIO('n\n1\n'), output)
    assert rc.CISALPINA not in output.getvalue()
    assert rc.PROVINCIA not in output.getvalue()
    play(state, rc.BELGAE, 71, params)


@pytest.mark.parametrize('actor', [rc.ROMANS, rc.BELGAE])
def test_terminal_forced_marches_choices_use_the_movers_map(actor):
    state = board()
    play(state, rc.ROMANS, 5, {})
    output = StringIO()
    _collect_event_params(state, actor, 32, False, StringIO('y\n1\n1\n1\n1\n1\nn\n'), output)
    assert (rc.CISALPINA in output.getvalue()) == (actor == rc.ROMANS)
    assert rc.BRITANNIA not in output.getvalue()
