"""Human cooperation keeps ownership, consent and durable choices visible."""

from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces
from fs_bot.cards.card_effects import execute_event
from fs_bot.cli.display import format_board, snapshot_state, HumanTurnDisplay
from fs_bot.cli.diviciacus import choose_regions, collect_pieces
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.agent import AGREEMENT
from fs_bot.engine.diviciacus import force_scope
from fs_bot.state.serialize import encode, save_game, load_game
from fs_bot.state.state_schema import build_initial_state
from fs_bot.tools.seat_session import SeatSession, DecisionPending, validate_response


def _cooperating_state():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=38)
    state['non_player_factions'] = set()
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 3)
    execute_event(state, 38, shaded=False)
    return state


def _request():
    return {'kind': 'diviciacus_pieces', 'phase': 'formation',
            'region': rc.CARNUTES, 'piece_type': rc.AUXILIA, 'count': 2,
            'available': {rc.ROMANS: 2, rc.AEDUI: 3}}


def test_planning_region_choice_preserves_board_rng_and_other_human_input():
    state = _cooperating_state()
    before = encode(state)
    state['decision_agent'] = lambda *_: pytest.fail('Planning consulted a live human')
    output = StringIO()
    selected = choose_regions(state, rc.ROMANS, 'command',
                              StringIO('y\nCarnutes\n'), output)
    assert selected == [rc.CARNUTES]
    assert 'assumes the other Faction agrees' in output.getvalue()
    assert encode({k: v for k, v in state.items() if k != 'decision_agent'}) == before
    # The original card grants Commands and defense, never Special Activities.
    assert choose_regions(state, rc.ROMANS, 'special_ability',
                          StringIO(''), StringIO()) is None


def test_declining_cooperation_is_explicit_and_does_not_change_board():
    state = _cooperating_state()
    before = encode(state)
    assert choose_regions(state, rc.AEDUI, 'command', StringIO('n\n'), StringIO()) == []
    assert encode(state) == before


@pytest.mark.parametrize('number,roman_count', [('1', 0), ('2', 1), ('3', 2)])
def test_piece_menu_offers_every_physical_owner_allocation(number, roman_count):
    response = collect_pieces({}, rc.ROMANS, _request(), StringIO(number + '\n'), StringIO())
    assert response == {'counts': {rc.ROMANS: roman_count, rc.AEDUI: 2 - roman_count}}
    assert validate_response({}, _request(), response) == response


@pytest.mark.parametrize('response', [
    {'counts': {rc.ROMANS: 3, rc.AEDUI: -1}},
    {'counts': {rc.ROMANS: 1}},
    {'counts': {rc.ROMANS: True, rc.AEDUI: 1}},
    {'counts': {rc.BELGAE: 2}},
])
def test_invalid_allocation_remains_pending_after_save_and_load(tmp_path, response):
    state = _cooperating_state()
    meta = {'seat': rc.ROMANS, 'scenario': state['scenario'], 'seed': 38}
    session = SeatSession(state, meta, [], HumanTurnDisplay(StringIO()))
    session.import_inbox([{'response': response}])
    before = encode(state)
    with pytest.raises(DecisionPending):
        session.ask(state, rc.ROMANS, _request())
    assert session.data['queue'] == [{'response': response}]
    assert session.data['pending']['id'] == 'd000001'
    assert encode(state) == before
    path = tmp_path / 'pending.json'
    save_game(state, path, meta=meta, log=[])
    loaded, saved_meta, log = load_game(path, validate=True)
    resumed = SeatSession(loaded, saved_meta, log, HumanTurnDisplay(StringIO()))
    resumed.import_inbox({'decision_id': 'd000001',
                          'response': {'counts': {rc.AEDUI: 2}}})
    assert resumed.ask(loaded, rc.ROMANS, _request()) == {'counts': {rc.AEDUI: 2}}
    assert resumed.data['pending'] is None


def test_board_displays_physical_owners_during_temporary_cooperation():
    state = _cooperating_state()
    before = snapshot_state(state)
    with force_scope(state, rc.ROMANS, [rc.CARNUTES]):
        assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 5
        assert snapshot_state(state) == before
        board = format_board(state)
        assert 'Diviciacus in Carnutes: Romans use 3 Aedui Warband as Auxilia' in board
        assert 'board counts show physical owners' in board
    assert snapshot_state(state) == before
    assert 'ACTIVE FORCES' not in format_board(state)


def test_defender_and_lender_receive_distinct_explicit_consent_prompts():
    output = StringIO()
    agent = make_cli_reactive([rc.ROMANS, rc.AEDUI], StringIO('y\nn\n'), output)
    assert agent({}, rc.ROMANS, {'kind': AGREEMENT,
        'request_type': 'diviciacus_defense', 'requesting_faction': rc.ROMANS,
        'context': {'phase': 'defense', 'region': rc.CARNUTES,
                    'attacker': rc.BELGAE}}) is True
    assert agent({}, rc.AEDUI, {'kind': AGREEMENT,
        'request_type': 'diviciacus', 'requesting_faction': rc.ROMANS,
        'context': {'phase': 'defense', 'regions': [rc.CARNUTES]}}) is False
    assert 'defend against Belgae in Carnutes' in output.getvalue()
    assert 'keeping their physical owners' in output.getvalue()
