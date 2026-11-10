"""The Gallic War evacuates exact Cisalpina forces in printed faction order."""
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board import pieces
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cli.display import format_board
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.interlude import _cisalpina_relocation
from fs_bot.engine.interlude_choices import CISALPINA_RELOCATION, cisalpina_request
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import board_copy, validate_response


def position():
    state = build_initial_state(rc.SCENARIO_GALLIC_WAR, seed=41)
    pieces.place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    return state


def allocation(piece_id, destination, count=1, *, tribe=None):
    row = dict(piece_id=piece_id, destination=destination, count=count)
    if tribe is not None:
        row['tribe'] = tribe
    return row


def test_faction_order_german_controller_and_exact_relocation():
    state = position()
    state['non_player_factions'] = {rc.ARVERNI}
    order = [rc.GERMANS, rc.BELGAE, rc.AEDUI, rc.ARVERNI, rc.ROMANS]
    for owner in order[:-1]:
        pieces.place_piece(state, rc.CISALPINA, owner, rc.WARBAND, 3 if owner == rc.GERMANS else 1)
    assert _ally_tribe(state, rc.TRIBE_NORI, rc.ARVERNI)
    pieces.place_piece(state, rc.CISALPINA, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    pieces.place_piece(state, rc.CISALPINA, rc.ROMANS, rc.LEGION, 2, from_legions_track=True)
    pieces.place_piece(state, rc.CISALPINA, rc.ROMANS, rc.AUXILIA, 3, piece_state=rc.REVEALED)
    pieces.place_piece(state, rc.CISALPINA, rc.ROMANS, rc.AUXILIA, 1, piece_state=rc.SCOUTED)
    hidden = f'{rc.WARBAND}:{rc.HIDDEN}'
    revealed = f'{rc.AUXILIA}:{rc.REVEALED}'
    scouted = f'{rc.AUXILIA}:{rc.SCOUTED}'
    plans = {
        rc.GERMANS: [allocation(hidden, rc.UBII), allocation(hidden, rc.SUGAMBRI), allocation(hidden, None)],
        rc.BELGAE: [allocation(hidden, rc.MORINI)],
        rc.AEDUI: [allocation(hidden, rc.AEDUI_REGION)],
        rc.ARVERNI: [allocation(hidden, rc.VENETI),
                    allocation(f'{rc.ALLY}:{rc.TRIBE_NORI}', rc.CARNUTES, tribe=rc.TRIBE_CARNUTES)],
        rc.ROMANS: [allocation(rc.LEADER, rc.PROVINCIA), allocation(rc.LEGION, rc.PROVINCIA),
                    allocation(rc.LEGION, None), allocation(revealed, rc.PROVINCIA, 2),
                    allocation(revealed, None), allocation(scouted, rc.PROVINCIA)],
    }
    seen = []

    def agent(board, controller, request):
        owner = request['acting_faction']
        seen.append((controller, owner, request['kind'],
                     [pieces.count_pieces(board, rc.CISALPINA, earlier) for earlier in order[:order.index(owner)]]))
        return {'allocations': plans[owner]}

    state['decision_agent'] = agent
    before_rng = state['rng'].getstate()
    before_track = sum(state['legions_track'].values())
    result = _cisalpina_relocation(state)
    assert seen == [(rc.GERMANS if owner == rc.ARVERNI else owner, owner, CISALPINA_RELOCATION, [0] * i)
                    for i, owner in enumerate(order)]
    assert [row['faction'] for row in result['moved']] == [
        rc.GERMANS, rc.GERMANS, rc.BELGAE, rc.AEDUI, rc.ARVERNI, rc.ARVERNI,
        rc.ROMANS, rc.ROMANS, rc.ROMANS, rc.ROMANS,
    ]
    assert result['removed'] == {rc.GERMANS: 1, rc.ROMANS: 2}
    assert not pieces.count_pieces(state, rc.CISALPINA)
    assert pieces.get_leader_in_region(state, rc.PROVINCIA, rc.ROMANS) == rc.CAESAR
    assert pieces.count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION) == 1
    assert sum(state['legions_track'].values()) == before_track + 1
    assert pieces.count_pieces_by_state(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 2
    assert pieces.count_pieces_by_state(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, rc.SCOUTED) == 1
    assert state['tribes'][rc.TRIBE_NORI]['allied_faction'] is None
    assert state['tribes'][rc.TRIBE_CARNUTES]['allied_faction'] == rc.ARVERNI
    assert state['rng'].getstate() == before_rng and validate_state(state) == []


def test_only_current_home_and_subdued_tribe_are_legal_and_all_pieces_must_leave():
    state = position()
    assert _ally_tribe(state, rc.TRIBE_NORI, rc.ROMANS)
    pieces.place_piece(state, rc.CISALPINA, rc.ROMANS, rc.AUXILIA, 2, piece_state=rc.SCOUTED)
    request = cisalpina_request(state, rc.ROMANS)
    ally = allocation(f'{rc.ALLY}:{rc.TRIBE_NORI}', rc.PROVINCIA, tribe=rc.TRIBE_HELVII)
    aux = allocation(f'{rc.AUXILIA}:{rc.SCOUTED}', rc.PROVINCIA, 2)
    before = encode(state)
    assert validate_response(state, request, {'allocations': [ally, aux]}) == {'allocations': [ally, aux]}
    for response in (
        {'allocations': [ally]},
        {'allocations': [ally, dict(aux, count=True)]},
        {'allocations': [ally, dict(aux, destination=rc.SEQUANI)]},
        {'allocations': [ally, aux, aux]},
        {'decline': True},
    ):
        with pytest.raises(ValueError):
            validate_response(state, request, response)
    assert encode(state) == before
    state['tribes'][rc.TRIBE_HELVII]['status'] = rc.DISPERSED
    before = encode(state)
    with pytest.raises(ValueError, match='have changed'):
        validate_response(state, request, {'allocations': [ally, aux]})
    request = cisalpina_request(state, rc.ROMANS)
    assert next(row for row in request['pieces'] if row['piece_type'] == rc.ALLY)['destinations'] == []
    with pytest.raises(ValueError, match='legal unoccupied'):
        validate_response(state, request, {'allocations': [ally, aux]})
    assert encode(state) == before


def test_fort_has_no_legal_roman_home_slot_and_is_removed_automatically():
    state = position()
    pieces.place_piece(state, rc.CISALPINA, rc.ROMANS, rc.FORT)
    state['decision_agent'] = lambda *args: pytest.fail('The permanent Fort fills the only Home slot')
    assert cisalpina_request(state, rc.ROMANS)['pieces'][0]['destinations'] == []
    before = pieces.get_available(state, rc.ROMANS, rc.FORT)
    assert _cisalpina_relocation(state)['removed'] == {rc.ROMANS: 1}
    assert not pieces.count_pieces(state, rc.CISALPINA)
    assert pieces.count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.FORT) == 1
    assert pieces.get_available(state, rc.ROMANS, rc.FORT) == before + 1


def test_gallia_togata_marker_skips_the_entire_relocation():
    state = position()
    state['markers'].setdefault(rc.CISALPINA, {})[rc.MARKER_GALLIA_TOGATA] = {'card_id': 'A5'}
    pieces.place_piece(state, rc.CISALPINA, rc.ROMANS, rc.AUXILIA)
    state['decision_agent'] = lambda *args: pytest.fail('Gallia Togata is in effect')
    before = encode(board_copy(state))
    assert _cisalpina_relocation(state)['skipped'] is True
    assert encode(board_copy(state)) == before


def test_terminal_allocation_uses_physical_owner_and_supports_board_inspection():
    state = position()
    pieces.place_piece(state, rc.CISALPINA, rc.ARVERNI, rc.WARBAND, 2, piece_state=rc.REVEALED)
    request = cisalpina_request(state, rc.ARVERNI)
    assert request['faction'] == rc.GERMANS
    output = StringIO()
    before = encode(state)
    agent = make_cli_reactive({rc.GERMANS}, StringIO('board\ny\nVeneti\n1\nRemove from the map\n'), output)
    piece_id = f'{rc.WARBAND}:{rc.REVEALED}'
    assert agent(state, rc.ARVERNI, request) is None
    assert agent(state, rc.GERMANS, request) == {'allocations': [
        allocation(piece_id, rc.VENETI), allocation(piece_id, None),
    ]}
    assert format_board(state) in output.getvalue() and encode(state) == before
