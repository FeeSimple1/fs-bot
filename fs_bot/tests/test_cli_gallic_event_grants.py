"""Real terminal menus for numeric 35/46/67 Command beneficiaries and scopes."""
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.cards import arduenna, gallic_event_grants as rules
from fs_bot.cli.free_actions import collect_free_action
from fs_bot.cli.human_plan import _collect_event_params
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.free_actions import execute_free_action_plan
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state, validate_state


def state(card=35, executor=rc.ROMANS):
    st = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=135)
    st.update(current_card=card, next_card=3, executing_faction=executor,
              non_player_factions=set())
    return st


def beneficiary(card):
    return rules.beneficiary_request(card)


def order():
    return rules.order_request()


@pytest.mark.parametrize('card,shaded', [(35, True), (46, True), (67, False), (67, True), (68, True)])
@pytest.mark.parametrize('executor', [rc.ROMANS, rc.AEDUI])
def test_event_parameters_wait_for_live_owner_without_consuming_input(card, shaded, executor):
    st, output = state(card, executor), StringIO()
    before = encode(st)
    assert _collect_event_params(st, executor, card, shaded, StringIO(), output) == {}
    assert not output.getvalue() and encode(st) == before


@pytest.mark.parametrize('card', [35, 46, 67])
@pytest.mark.parametrize('selected', [rc.ARVERNI, rc.AEDUI, rc.BELGAE])
def test_executor_selects_every_gallic_faction_with_board_and_invalid_retry(card, selected):
    st, output = state(card), StringIO()
    before = encode(st)
    response = collect_free_action(st, rc.ROMANS, beneficiary(card),
        StringIO(f'not a faction\n99\nboard\n{selected}\n'), output)
    assert response == {'faction': selected}
    assert 'Please enter' in output.getvalue()
    assert 'AVAILABLE PIECES' in output.getvalue()
    assert encode(st) == before


def test_numeric_arduenna_also_offers_romans_but_never_germans():
    st, output = state(67), StringIO()
    assert collect_free_action(st, rc.AEDUI, beneficiary(67),
        StringIO('Germans\nRomans\n'), output) == {'faction': rc.ROMANS}
    assert "got 'Germans'" in output.getvalue()


@pytest.mark.parametrize('line,expected', [
    ('full Command then Limited Command', ['command', 'limited_command']),
    ('Limited Command then full Command', ['limited_command', 'command']),
])
def test_beneficiary_chooses_both_command_orders(line, expected):
    st, output = state(), StringIO()
    before = encode(st)
    assert collect_free_action(st, rc.AEDUI, order(), StringIO('b\n' + line + '\n'), output) == {'order': expected}
    assert 'AVAILABLE PIECES' in output.getvalue() and encode(st) == before
    assert 'no Battles or Special Activity' in output.getvalue()


@pytest.mark.parametrize('offered', [beneficiary(35), beneficiary(46), beneficiary(67), order()])
def test_selection_default_is_explicit_and_eof_never_defaults(offered):
    st, output = state(offered['card_id']), StringIO()
    before = encode(st)
    assert collect_free_action(st, rc.AEDUI, offered,
        StringIO('Use bot default\n'), output) == {'use_default': True}
    assert ') Decline' not in output.getvalue()
    with pytest.raises(EOFError):
        make_cli_reactive([rc.AEDUI], StringIO(), StringIO())(st, rc.AEDUI, offered)
    assert encode(st) == before


@pytest.mark.parametrize('line,expected', [('Accept', {'accept': True}),
    ('Decline', {'decline': True}), ('Use bot default', {'use_default': True})])
def test_numeric_arduenna_acceptance_covers_whole_sequence(line, expected):
    st, output = state(67), StringIO()
    before = encode(st)
    request = {'kind': 'free_action', 'request_type': 'arduenna_accept', 'card_id': 67}
    assert collect_free_action(st, rc.AEDUI, request, StringIO('board\n' + line + '\n'), output) == expected
    assert 'complete March, Command, then Hide sequence' in output.getvalue()
    assert 'AVAILABLE PIECES' in output.getvalue() and encode(st) == before


@pytest.mark.parametrize('limited', [False, True])
def test_shouts_real_raid_menu_is_free_without_battle_or_special_activity(limited):
    st, output = state(), StringIO()
    for region in (rc.ATREBATES, rc.NERVII):
        place_piece(st, region, rc.AEDUI, rc.WARBAND)
    before = encode(st)
    request = rules.command_request(rc.AEDUI, 35, limited=limited)
    lines = ['board', 'Plan the action', 'Raid', 'b', rc.ATREBATES]
    if not limited:
        lines.append(rc.NERVII)
    lines.extend(['gain 1 Resource'] * (1 if limited else 2))
    action = collect_free_action(st, rc.AEDUI, request,
        StringIO('\n'.join(lines) + '\n'), output)
    assert encode(st) == before
    assert action['sa'] == 'No SA'
    assert ') Battle' not in output.getvalue() and ') Decline' not in output.getvalue()
    assert 'Add a Special Activity?' not in output.getvalue()
    assert output.getvalue().count('AVAILABLE PIECES') == 2
    assert len(action['details']['raid_plan']) == (1 if limited else 2)
    assert execute_free_action_plan(st, rc.AEDUI, request, action)['executed']
    assert st['resources'][rc.AEDUI] == (1 if limited else 2)
    assert validate_state(st) == []


def test_numeric_arduenna_menu_keeps_two_step_target_route_and_chosen_group():
    st, output = state(67), StringIO()
    place_piece(st, rc.ATREBATES, rc.ROMANS, rc.AUXILIA, 2)
    before = encode(st)
    request = arduenna.march_request(67)
    lines = ['Plan the action', 'March', rc.ATREBATES,
             'board', f'{rc.NERVII} → {rc.TREVERI}', 'all 2']
    action = collect_free_action(st, rc.ROMANS, request,
        StringIO('\n'.join(lines) + '\n'), output)
    assert encode(st) == before
    assert action['details']['routes'] == {rc.ATREBATES: [rc.NERVII, rc.TREVERI]}
    assert 'AVAILABLE PIECES' in output.getvalue()
    assert ') Raid' not in output.getvalue() and 'Add a Special Activity?' not in output.getvalue()
    assert execute_free_action_plan(st, rc.ROMANS, request, action)['executed']
    assert count_pieces(st, rc.TREVERI, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(st, rc.ATREBATES, rc.ROMANS) == 0
    assert validate_state(st) == []


def test_celtic_rites_keeps_battle_available_without_special_activity():
    st, output = state(46), StringIO()
    place_piece(st, rc.NERVII, rc.AEDUI, rc.WARBAND, 2)
    place_piece(st, rc.NERVII, rc.BELGAE, rc.WARBAND)
    before = encode(st)
    action = collect_free_action(st, rc.AEDUI, rules.command_request(rc.AEDUI, 46),
        StringIO(f'Plan the action\nBattle\n{rc.NERVII}\n{rc.BELGAE}\n'), output)
    assert encode(st) == before
    assert action['command'] == rc.CMD_BATTLE and action['sa'] == 'No SA'
    assert action['details']['battle_plan'] == [{'region': rc.NERVII, 'target': rc.BELGAE}]
    assert 'Add a Special Activity?' not in output.getvalue()


def test_numeric_arduenna_follow_on_command_stays_in_two_targets():
    st, output = state(67), StringIO()
    for region in (rc.NERVII, rc.TREVERI, rc.ATREBATES):
        place_piece(st, region, rc.AEDUI, rc.WARBAND)
    before = encode(st)
    request = arduenna.command_request(rc.AEDUI, 67)
    action = collect_free_action(st, rc.AEDUI, request,
        StringIO(f'Plan the action\nRaid\n{rc.ATREBATES}\n{rc.NERVII}\n{rc.TREVERI}\n'
                 'gain 1 Resource\ngain 1 Resource\n'), output)
    assert encode(st) == before
    assert action['details']['raid_plan'] == [
        {'region': rc.NERVII, 'target': None}, {'region': rc.TREVERI, 'target': None}]
    text = output.getvalue()
    assert f"got '{rc.ATREBATES}'" in text and f') {rc.ATREBATES}' not in text
    assert ') March' not in text and 'Add a Special Activity?' not in text
    assert execute_free_action_plan(st, rc.AEDUI, request, action)['executed']
    assert st['resources'][rc.AEDUI] == 2


@pytest.mark.parametrize('card', [35, 46, 67, 68])
def test_app_shows_full_cards_and_latest_changes_before_event_choices(monkeypatch, card):
    from copy import deepcopy
    from fs_bot.cards.card_effects import _ally_tribe
    from fs_bot.cards.card_text import get_card_text
    from fs_bot.cards import remi_event_effect
    from fs_bot.cli import app
    from fs_bot.engine.agent import consult_agent
    st = state(card)
    st['deck'] = [card, 3, 4]
    if card == 68:
        assert _ally_tribe(st, rc.TRIBE_REMI, rc.AEDUI)
    owner = rc.AEDUI if card == 68 else rc.ROMANS
    offered = remi_event_effect.request(st) if card == 68 else beneficiary(card)
    label = 'Decline this effect' if card == 68 else rc.AEDUI
    expected = {'decline': True} if card == 68 else {'faction': rc.AEDUI}
    prompt = ('Aedui: choose the optional Remi Influence effect.' if card == 68 else
              'Romans: which Faction receives the Event actions?')
    monkeypatch.setattr(app, 'setup_scenario', lambda *a, **k: deepcopy(st))

    def resolve(board, decision, *, execute):
        assert consult_agent(board, owner, offered) == expected
        board['resources'][rc.AEDUI] += 2
        assert consult_agent(board, owner, offered) == expected
        return {'card': card, 'game_over': True}

    monkeypatch.setattr(app, 'play_card', resolve)
    output = StringIO()
    assert app.main(['--scenario', rc.SCENARIO_GREAT_REVOLT, '--seed', '135', '--bots', ''],
        stdin=StringIO(f'{label}\n{label}\n'), stdout=output) == 0
    chunks = output.getvalue().split(prompt)
    assert len(chunks) == 3
    for before_choice in chunks[:2]:
        for current in (card, 3):
            for line in get_card_text(current, st['scenario'], st.get('card_edition')).splitlines():
                assert line in before_choice
    assert f'{owner}: changes since your last decision' in chunks[1]
    assert 'Aedui Resources: 0 -> 2' in chunks[1]
