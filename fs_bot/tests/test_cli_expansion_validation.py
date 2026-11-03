"""Printed EXP-09 targets, mandatory quantities and current-board menus."""
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_available, place_piece
from fs_bot.cards.card_effects import _ally_tribe, execute_event
from fs_bot.cli import expansion_validation as cli
from fs_bot.cli import voluntary_removal
from fs_bot.engine.action_windows import scope
from fs_bot.map.map_data import get_playable_regions_for_state
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state


def board(card, faction=rc.AEDUI):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=909)
    state['current_card'] = card
    state['executing_faction'] = faction
    state['non_player_factions'] = set()
    return state


def run(state, card, faction, params, shaded=False):
    state['executing_faction'], state['event_params'] = faction, params
    with scope(state, actor=faction, plan=params, force=True):
        execute_event(state, card, shaded)
    assert validate_state(state) == []


def values(choices):
    return [value for _, value in choices]


def test_a29_foreign_beneficiary_is_named_without_collecting_its_pieces():
    state = board('A29', rc.BELGAE)
    before = encode(state)
    output = StringIO()
    params = cli.collect_params(state, rc.BELGAE, 'A29', False,
                                StringIO('b\nRomans\n'), output)
    assert params == {'faction': rc.ROMANS}
    assert 'choose the next piece' not in output.getvalue()
    assert rc.SEQUANI in output.getvalue()
    assert encode(state) == before


def test_a36_foreign_executor_leaves_named_german_decisions_for_live_request():
    state = board('A36', rc.ROMANS)
    output = StringIO()
    assert cli.collect_params(state, rc.ROMANS, 'A36', True,
                              StringIO(), output) == {}
    assert output.getvalue() == ''


def test_a29_cannot_finish_troops_early_but_can_choose_zero_allies(monkeypatch):
    state = board('A29')
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.SETTLEMENT)
    before = encode(state)
    picked = 0

    def choose(stdin, stdout, prompt, choices):
        nonlocal picked
        if prompt.startswith('Harudes:'):
            assert rc.GERMANS not in values(choices)
            return rc.AEDUI
        options = values(choices)
        if picked < 5:
            assert None not in options
            entry = next(e for e in options if e['piece_type'] == rc.WARBAND
                         and e['region'] == rc.SUGAMBRI)
            picked += entry.get('count', 1)
            return entry
        assert None in options
        return None

    monkeypatch.setattr(cli, 'prompt_choice', choose)
    params = cli.collect_params(state, rc.AEDUI, 'A29', False, StringIO(), StringIO())
    assert encode(state) == before
    assert sum(e.get('count', 1) for e in params['placements']) == 5
    assert all(e['piece_type'] == rc.WARBAND for e in params['placements'])
    run(state, 'A29', rc.AEDUI, params)
    assert count_pieces(state, rc.SUGAMBRI, rc.AEDUI, rc.WARBAND) == 5
    assert count_pieces(state, rc.SUGAMBRI, rc.AEDUI, rc.ALLY) == 0


def test_a30_menu_is_within_one_sequani_and_board_inspection_is_read_only(monkeypatch):
    state = board('A30')
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 1, piece_state=rc.SCOUTED)
    before = encode(state)
    original, offered = cli.prompt_choice, []

    def capture(stdin, stdout, prompt, choices):
        offered.extend(values(choices))
        return original(stdin, stdout, prompt, choices)

    monkeypatch.setattr(cli, 'prompt_choice', capture)
    output = StringIO()
    params = cli.collect_params(state, rc.AEDUI, 'A30', False,
                                StringIO('board\nSequani\n'), output)
    assert rc.SEQUANI in offered and rc.MORINI not in offered
    assert params == {'region': rc.SEQUANI}
    assert rc.SEQUANI in output.getvalue()
    assert encode(state) == before
    run(state, 'A30', rc.AEDUI, params)
    assert count_pieces(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND) == 0


def test_a36_places_required_pieces_in_distinct_settlement_slots_then_removes_allies(monkeypatch):
    state = board('A36', rc.GERMANS)
    assert _ally_tribe(state, rc.TRIBE_MORINI, rc.ROMANS)
    assert _ally_tribe(state, rc.TRIBE_NERVII, rc.BELGAE)
    before = encode(state)
    settlements, warbands, removed = [], 0, []

    def choose(stdin, stdout, prompt, choices):
        nonlocal warbands
        options = values(choices)
        entries = [e for e in options if isinstance(e, dict)]
        if entries and 'piece_type' in entries[0]:
            if len(settlements) < 2:
                target = (rc.SUGAMBRI, rc.UBII)[len(settlements)]
                entry = next(e for e in entries if e['piece_type'] == rc.SETTLEMENT
                             and e['region'] == target)
                assert not any(e['piece_type'] == rc.SETTLEMENT
                               and e['region'] in settlements for e in entries)
                settlements.append(target)
                return entry
            if warbands < 4:
                entry = next(e for e in entries if e['piece_type'] == rc.WARBAND
                             and e['region'] == rc.NERVII)
                warbands += entry.get('count', 1)
                return entry
            return None
        if entries:
            target = (rc.TRIBE_NERVII, rc.TRIBE_MORINI)[len(removed)]
            entry = next(e for e in entries if e['tribe'] == target)
            removed.append(target)
            return entry
        return None

    monkeypatch.setattr(cli, 'prompt_choice', choose)
    params = cli.collect_params(state, rc.GERMANS, 'A36', True, StringIO(), StringIO())
    assert encode(state) == before
    assert settlements == [rc.SUGAMBRI, rc.UBII] and warbands == 4
    assert removed == [rc.TRIBE_NERVII, rc.TRIBE_MORINI]
    run(state, 'A36', rc.GERMANS, params, shaded=True)
    assert all(count_pieces(state, region, rc.GERMANS, rc.SETTLEMENT) == 1
               for region in settlements)
    assert count_pieces(state, rc.NERVII, rc.GERMANS, rc.WARBAND) == 4
    assert all(state['tribes'][tribe]['allied_faction'] is None for tribe in removed)


def test_a43_selects_exact_revealed_scouted_warbands_and_allied_tribes(monkeypatch):
    state = board('A43')
    for tribe in (rc.TRIBE_SEQUANI, rc.TRIBE_HELVETII):
        assert _ally_tribe(state, tribe, rc.ARVERNI)
    for visibility, number in ((rc.HIDDEN, 3), (rc.REVEALED, 1), (rc.SCOUTED, 1)):
        place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, number,
                    piece_state=visibility)
    before = encode(state)
    desired = [(rc.WARBAND, rc.REVEALED), (rc.ALLY, rc.TRIBE_HELVETII),
               (rc.WARBAND, rc.SCOUTED), (rc.ALLY, rc.TRIBE_SEQUANI)]

    def choose(stdin, stdout, prompt, choices):
        if not desired:
            return None
        kind, identity = desired.pop(0)
        return next(e for e in values(choices) if isinstance(e, dict)
                    and e['from_type'] == kind and e['to_faction'] == rc.ROMANS
                    and e.get('piece_state' if kind == rc.WARBAND else 'tribe') == identity)

    monkeypatch.setattr(cli, 'prompt_choice', choose)
    params = cli.collect_params(state, rc.AEDUI, 'A43', False, StringIO(), StringIO())
    assert not desired and encode(state) == before
    run(state, 'A43', rc.AEDUI, params)
    assert count_pieces_by_state(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 3
    assert count_pieces_by_state(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, rc.REVEALED) == 0
    assert count_pieces_by_state(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, rc.SCOUTED) == 0
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 2
    assert all(state['tribes'][tribe]['allied_faction'] == rc.ROMANS
               for tribe in (rc.TRIBE_SEQUANI, rc.TRIBE_HELVETII))


def test_a45_optional_zero_is_available_and_no_marker_means_no_placement_menu(monkeypatch):
    state = board('A45')
    monkeypatch.setattr(cli, 'prompt_choice', lambda *args: pytest.fail('No eligible choices'))
    params = cli.collect_params(state, rc.AEDUI, 'A45', False, StringIO(), StringIO())
    assert params == {'placements': []}
    state['markers'].setdefault(rc.SEQUANI, {})[rc.MARKER_INTIMIDATED] = True

    def finish(stdin, stdout, prompt, choices):
        assert None in values(choices)
        assert all(e['faction'] != rc.GERMANS for e in values(choices) if e is not None)
        return None

    monkeypatch.setattr(cli, 'prompt_choice', finish)
    before = encode(state)
    assert cli.collect_params(state, rc.AEDUI, 'A45', False, StringIO(), StringIO()) == params
    assert encode(state) == before


@pytest.mark.parametrize('card,shaded', [('A29', False), ('A30', False), ('A45', False)])
def test_eof_preserves_pending_choices_without_mutation(card, shaded):
    state = board(card)
    state['markers'].setdefault(rc.SEQUANI, {})[rc.MARKER_INTIMIDATED] = True
    before = encode(state)
    with pytest.raises(EOFError):
        cli.collect_params(state, rc.AEDUI, card, shaded, StringIO(), StringIO())
    assert encode(state) == before


def test_named_owner_response_can_explicitly_choose_default_and_inspect_board():
    state = board('A36', rc.GERMANS)
    output = StringIO()
    before = encode(state)
    request = {'card_id': 'A36', 'acting_faction': rc.GERMANS}
    response = cli.collect_response(state, rc.GERMANS, request,
                                    StringIO('b\n2\n'), output)
    assert response == {'use_default': True}
    assert rc.SEQUANI in output.getvalue()
    assert encode(state) == before


def test_a45_reclamation_precedes_options_and_survives_the_plan(monkeypatch):
    state = board('A45', rc.ROMANS)
    state['_cli_action_windows'] = True
    state['markers'].setdefault(rc.SEQUANI, {})[rc.MARKER_INTIMIDATED] = True
    occupied = []
    for tribe in state['tribes']:
        if tribe != rc.TRIBE_SEQUANI and get_available(state, rc.ROMANS, rc.ALLY):
            if _ally_tribe(state, tribe, rc.ROMANS):
                occupied.append(tribe)
    assert get_available(state, rc.ROMANS, rc.ALLY) == 0

    before, reclaimed, placed = encode(state), False, False

    def choose(stdin, stdout, prompt, choices):
        nonlocal reclaimed, placed
        if prompt == 'Voluntary removal?':
            if not reclaimed:
                reclaimed = True
                return next(e for e in values(choices) if isinstance(e, dict)
                            and e.get('tribe') == occupied[0])
            return 'done'
        if not placed:
            placed = True
            return next(e for e in values(choices) if isinstance(e, dict)
                        and e.get('tribe') == rc.TRIBE_SEQUANI
                        and e['faction'] == rc.ROMANS)
        return None

    monkeypatch.setattr(cli, 'prompt_choice', choose)
    monkeypatch.setattr(voluntary_removal, 'prompt_choice', choose)
    params = cli.collect_params(state, rc.ROMANS, 'A45', False, StringIO(), StringIO())
    assert reclaimed and placed and encode(state) == before
    assert params['placements'][0]['timing_actions'][0]['kind'] == 'voluntary_removal'
    run(state, 'A45', rc.ROMANS, params)
    assert state['tribes'][occupied[0]]['allied_faction'] is None
    assert state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] == rc.ROMANS
    assert get_available(state, rc.ROMANS, rc.ALLY) == 0


def test_board_command_after_placement_shows_the_current_planning_board(monkeypatch):
    state = board('A29')
    place_piece(state, rc.SUGAMBRI, rc.GERMANS, rc.SETTLEMENT)
    before, picked = encode(state), 0
    original = cli.prompt_choice
    output = StringIO()

    def choose(stdin, stdout, prompt, choices):
        nonlocal picked
        if prompt.startswith('Harudes:'):
            return rc.AEDUI
        if picked == 5:
            return None
        entry = next(e for e in values(choices) if isinstance(e, dict)
                     and e['piece_type'] == rc.WARBAND and e['region'] == rc.SUGAMBRI)
        if picked == 1:
            index = values(choices).index(entry) + 1
            entry = original(StringIO(f'board\n{index}\n'), stdout, prompt, choices)
            line = next(line for line in output.getvalue().splitlines()
                        if line.startswith(rc.SUGAMBRI))
            assert 'W:1[H1/R0/S0]' in line
        picked += 1
        return entry

    monkeypatch.setattr(cli, 'prompt_choice', choose)
    params = cli.collect_params(state, rc.AEDUI, 'A29', False, StringIO(), output)
    assert len(params['placements']) == 5 and encode(state) == before


def test_a36_can_reclaim_settlements_before_advancing_to_ally_removals(monkeypatch):
    state = board('A36', rc.GERMANS)
    state['_cli_action_windows'] = True
    occupied = []
    for region in get_playable_regions_for_state(state, rc.GERMANS):
        if region not in (rc.SUGAMBRI, rc.UBII) and get_available(state, rc.GERMANS, rc.SETTLEMENT):
            place_piece(state, region, rc.GERMANS, rc.SETTLEMENT)
            occupied.append(region)
    assert get_available(state, rc.GERMANS, rc.SETTLEMENT) == 0
    before = encode(state)
    reclaimed, settlements, warbands = [], [], 0

    def choose(stdin, stdout, prompt, choices):
        nonlocal warbands
        options = values(choices)
        if prompt == 'Voluntary removal?':
            if len(reclaimed) < 2:
                region = occupied[len(reclaimed)]
                entry = next(e for e in options if isinstance(e, dict)
                             and e['region'] == region and e['piece_type'] == rc.SETTLEMENT)
                reclaimed.append(region)
                return entry
            return 'done'
        if len(settlements) < 2:
            region = (rc.SUGAMBRI, rc.UBII)[len(settlements)]
            entry = next(e for e in options if isinstance(e, dict)
                         and e['region'] == region and e['piece_type'] == rc.SETTLEMENT)
            settlements.append(region)
            return entry
        if warbands < 4:
            entry = next(e for e in options if isinstance(e, dict)
                         and e['region'] == rc.NERVII and e['piece_type'] == rc.WARBAND)
            warbands += 1
            return entry
        return None

    monkeypatch.setattr(cli, 'prompt_choice', choose)
    monkeypatch.setattr(voluntary_removal, 'prompt_choice', choose)
    params = cli.collect_params(state, rc.GERMANS, 'A36', True, StringIO(), StringIO())
    assert len(reclaimed) == len(settlements) == 2 and warbands == 4
    assert encode(state) == before
    operations = params['placements'][0]['timing_actions'][0]['response']['operations']
    assert len(operations) == 2
    run(state, 'A36', rc.GERMANS, params, shaded=True)
    assert all(count_pieces(state, region, rc.GERMANS, rc.SETTLEMENT) == 0 for region in reclaimed)
    assert all(count_pieces(state, region, rc.GERMANS, rc.SETTLEMENT) == 1 for region in settlements)
    assert get_available(state, rc.GERMANS, rc.SETTLEMENT) == 0
