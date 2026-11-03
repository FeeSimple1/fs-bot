"""Real terminal choices for the printed fixed Event Battles (BE-02)."""

from copy import deepcopy
from contextlib import nullcontext
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.cli.free_actions import collect_free_action
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state


CARDS = (11, '11a', 25, 36, 45, 70)


def fixture(card=36, scenario=rc.SCENARIO_GREAT_REVOLT):
    board = build_initial_state(scenario, seed=125)
    board.update(current_card=11 if card == '11a' else card, next_card=3,
                 non_player_factions=set())
    if card == '11a':
        board['card_edition'] = 'second-edition'
    faction = rc.BELGAE if card in (25, 45) else rc.ROMANS
    if card in (11, '11a', 70):
        choices = {rc.CARNUTES: [rc.ARVERNI, rc.BELGAE]}
    elif card == 25:
        choices = {rc.PICTONES: [rc.ARVERNI, rc.ROMANS], rc.ARVERNI_REGION: [rc.AEDUI]}
    elif card == 36:
        choices = {rc.PICTONES: [rc.ARVERNI, rc.BELGAE], rc.ARVERNI_REGION: [rc.AEDUI]}
    else:
        choices = {rc.PICTONES: [rc.ROMANS], rc.ARVERNI_REGION: [rc.ROMANS]}
    for region, defenders in choices.items():
        if card != 25:
            owner = rc.AEDUI if card == 45 else faction
            piece = rc.AUXILIA if owner == rc.ROMANS else rc.WARBAND
            place_piece(board, region, owner, piece, 4)
        for defender in defenders:
            piece = rc.AUXILIA if defender == rc.ROMANS else rc.WARBAND
            place_piece(board, region, defender, piece, 2)
    board['executing_faction'] = faction
    request = {
        'kind': 'free_action', 'request_type': 'fixed_event_battle',
        'card_id': card, 'allowed_regions': list(choices),
        'defenders_by_region': choices, 'max_regions': 1,
        'allowed_commands': [rc.CMD_BATTLE], 'with_sa': False, 'free': True,
        'allow_decline': False, 'default_available': True,
        'validate_default_response': True,
    }
    return board, faction, request


@pytest.mark.parametrize('card', CARDS)
@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS,
                                      rc.SCENARIO_GALLIC_WAR])
def test_event_battle_menu_selects_last_legal_choice_and_rejects_outside_inputs(card, scenario):
    board, faction, request = fixture(card, scenario)
    region = request['allowed_regions'][-1]
    defender = request['defenders_by_region'][region][-1]
    before = encode(board)
    output = StringIO()
    response = collect_free_action(board, faction, request, StringIO(
        f'Choose Region and defender\n{rc.PROVINCIA}\n{region}\n{faction}\n{defender}\n'), output)
    assert response == {'region': region, 'defender': defender}
    assert f"got '{rc.PROVINCIA}'" in output.getvalue()
    assert f"got '{faction}'" in output.getvalue()
    assert ') Decline' not in output.getvalue()
    assert 'Add a Special Activity?' not in output.getvalue()
    assert encode(board) == before


def test_aquitani_menu_does_not_require_friendly_forces():
    board, faction, request = fixture(25)
    assert all(count_pieces(board, region, faction) == 0 for region in request['allowed_regions'])
    output = StringIO()
    response = collect_free_action(board, faction, request,
        StringIO(f'Choose Region and defender\n{rc.PICTONES}\n{rc.ROMANS}\n'), output)
    assert response == {'region': rc.PICTONES, 'defender': rc.ROMANS}
    assert 'No legal plan' not in output.getvalue()


def test_litaviccus_menu_includes_region_with_only_lent_aedui_attackers():
    board, faction, request = fixture(45)
    assert count_pieces(board, rc.ARVERNI_REGION, faction) == 0
    assert count_pieces(board, rc.ARVERNI_REGION, rc.AEDUI) == 4
    response = collect_free_action(board, faction, request,
        StringIO(f'Choose Region and defender\n{rc.ARVERNI_REGION}\n{rc.ROMANS}\n'), StringIO())
    assert response == {'region': rc.ARVERNI_REGION, 'defender': rc.ROMANS}


@pytest.mark.parametrize('card', [25, 36, 45])
def test_actual_battle_resolver_uses_terminal_selection(card):
    from fs_bot.engine import execute
    from fs_bot.state.state_schema import validate_state
    board, faction, request = fixture(card)
    region = request['allowed_regions'][-1]
    defender = request['defenders_by_region'][region][-1]
    board['non_player_factions'] = {rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE} - {faction}
    output = StringIO()
    board['decision_agent'] = make_cli_reactive([faction], StringIO(
        f'Choose Region and defender\n{region}\n{defender}\n'), output)
    if card == 25:
        result = execute._resolve_card25_battle(board, faction, region, 3)
    elif card == 36:
        result = execute._resolve_card36_battle(board, faction)
    else:
        result = execute._resolve_card45_battle(board, faction)
    assert result[0]['region'] == region
    assert result[0]['defender'] == defender
    assert count_pieces(board, region, defender) == 0
    assert f'{faction}: choose the Event Battle.' in output.getvalue()
    assert validate_state(board) == []


@pytest.mark.parametrize('auxilia_only', [False, True])
def test_numidians_resolver_uses_roman_terminal_defender_choice(auxilia_only):
    from fs_bot.engine import execute
    board, faction, _ = fixture('11a' if auxilia_only else 11)
    board['non_player_factions'] = {rc.ARVERNI, rc.AEDUI, rc.BELGAE}
    output = StringIO()
    board['decision_agent'] = make_cli_reactive([rc.ROMANS], StringIO(
        f'Choose Region and defender\n{rc.CARNUTES}\n{rc.BELGAE}\n'), output)
    result = execute._free_double_aux_battle(board, rc.CARNUTES, auxilia_only=auxilia_only)
    assert result['attack'] is not None
    assert count_pieces(board, rc.CARNUTES, rc.BELGAE) == 0
    assert count_pieces(board, rc.CARNUTES, rc.ARVERNI) == 2
    assert 'Romans: choose the Event Battle.' in output.getvalue()


def test_camulogenus_defender_menu_uses_board_after_the_existing_march():
    from fs_bot.engine import execute
    board, _, _ = fixture(70)
    place_piece(board, rc.MANDUBII, rc.ROMANS, rc.AUXILIA, 4)
    board['non_player_factions'] = {rc.ARVERNI, rc.AEDUI, rc.BELGAE}
    output = StringIO()
    observed = []
    cli = make_cli_reactive([rc.ROMANS], StringIO(
        f'board\nChoose Region and defender\n{rc.CARNUTES}\n{rc.BELGAE}\n'), output)

    def agent(live, faction, request):
        if request.get('request_type') == 'fixed_event_battle':
            observed.append((count_pieces(live, rc.MANDUBII, rc.ROMANS),
                             count_pieces(live, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)))
        return cli(live, faction, request)

    board['decision_agent'] = agent
    result = execute._resolve_card70_march_battle(board, [rc.CARNUTES], 4)
    assert observed == [(0, 8)]
    assert result[0]['region'] == rc.CARNUTES and result[0]['defender'] == rc.BELGAE
    assert count_pieces(board, rc.CARNUTES, rc.BELGAE) == 0
    assert count_pieces(board, rc.CARNUTES, rc.ARVERNI) == 2
    assert 'AVAILABLE PIECES' in output.getvalue()


@pytest.mark.parametrize('borrow', [False, True])
def test_numidians_display_keeps_excluded_physical_pieces_and_explains_participation(borrow):
    from fs_bot.battle.excluded_leader import only_attacker_auxilia
    from fs_bot.cards.card_effects import _ally_tribe
    from fs_bot.cli.display import (HumanTurnDisplay, _active_force_context,
                                    _physical_piece_view, format_region_table)
    from fs_bot.engine.diviciacus import force_scope
    board, _, _ = fixture('11a')
    place_piece(board, rc.CARNUTES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(board, rc.CARNUTES, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(board, rc.CARNUTES, rc.ROMANS, rc.FORT)
    assert _ally_tribe(board, rc.TRIBE_CARNUTES, rc.ROMANS)
    if borrow:
        place_piece(board, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 2)
    before = encode(board)
    physical_table = format_region_table(board)
    output = StringIO()
    display = HumanTurnDisplay(output)
    display.remember(board, (rc.ROMANS,))
    cooperation = force_scope(board, rc.ROMANS, [rc.CARNUTES]) if borrow else nullcontext()
    with cooperation, only_attacker_auxilia(board, rc.ROMANS, rc.CARNUTES):
        assert count_pieces(board, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == (6 if borrow else 4)
        for piece in (rc.LEADER, rc.LEGION, rc.FORT, rc.ALLY):
            assert count_pieces(board, rc.CARNUTES, rc.ROMANS, piece) == 0
            assert count_pieces(_physical_piece_view(board), rc.CARNUTES, rc.ROMANS, piece) == 1
        assert format_region_table(board) == physical_table
        explanation = '\n'.join(_active_force_context(board))
        assert 'Numidians: Romans Battle with only Auxilia in Carnutes' in explanation
        assert 'including any cooperating Aedui Warbands' in explanation
        display.before_decision(board, rc.ROMANS)
        assert 'No board changes.' in output.getvalue()
    assert encode(board) == before


def test_board_inspection_at_each_selection_uses_live_board_and_restores_hook():
    from fs_bot.cli import menus
    board, faction, request = fixture(36)
    output = StringIO()
    previous = lambda: output.write('previous board hook\n')
    saved = menus._BOARD_HOOK[0]
    menus.set_board_hook(previous)
    try:
        before = encode(board)
        response = collect_free_action(board, faction, request, StringIO(
            f'board\nChoose Region and defender\nb\n{rc.PICTONES}\nboard\n{rc.BELGAE}\n'), output)
        assert response == {'region': rc.PICTONES, 'defender': rc.BELGAE}
        assert output.getvalue().count('AVAILABLE PIECES') == 3
        assert 'previous board hook' not in output.getvalue()
        assert menus._BOARD_HOOK[0] is previous
        assert encode(board) == before
    finally:
        menus.set_board_hook(saved)


@pytest.mark.parametrize('card', CARDS)
def test_mandatory_battle_decline_is_not_a_menu_choice(card):
    board, faction, request = fixture(card)
    output = StringIO()
    response = collect_free_action(board, faction, request,
        StringIO('Decline Battle\nUse bot default\n'), output)
    assert response == {'use_default': True}
    assert "got 'Decline Battle'" in output.getvalue()
    assert ') Decline' not in output.getvalue()


def test_unavailable_default_is_not_offered_or_silently_used():
    board, faction, request = fixture(36)
    request['default_available'] = False
    output = StringIO()
    response = collect_free_action(board, faction, request, StringIO(
        f'Use bot default\nChoose Region and defender\n{rc.PICTONES}\n{rc.BELGAE}\n'), output)
    assert response == {'region': rc.PICTONES, 'defender': rc.BELGAE}
    assert "got 'Use bot default'" in output.getvalue()
    assert ') Use bot default' not in output.getvalue()


@pytest.mark.parametrize('prefix', ['', 'Choose Region and defender\n',
                                  f'Choose Region and defender\n{rc.PICTONES}\n'])
def test_eof_during_any_selection_interrupts_without_default_or_mutation(prefix):
    board, faction, request = fixture(36)
    before = encode(board)
    with pytest.raises(EOFError):
        make_cli_reactive([faction], StringIO(prefix), StringIO())(board, faction, request)
    assert encode(board) == before


@pytest.mark.parametrize('card', CARDS)
def test_app_displays_full_current_upcoming_cards_and_changes_before_each_battle_choice(monkeypatch, card):
    from fs_bot.cards.card_text import get_card_text
    from fs_bot.cli import app
    from fs_bot.engine.agent import consult_agent
    board, faction, request = fixture(card)
    board['deck'] = [board['current_card'], 3, 4]
    selected_region = request['allowed_regions'][-1]
    selected_defender = request['defenders_by_region'][selected_region][-1]
    response = {'region': selected_region, 'defender': selected_defender}
    monkeypatch.setattr(app, 'setup_scenario', lambda *a, **k: deepcopy(board))

    def resolve(live, decision, *, execute):
        assert consult_agent(live, faction, request) == response
        live['resources'][rc.AEDUI] += 2
        assert consult_agent(live, faction, request) == response
        return {'card': live['current_card'], 'game_over': True}

    monkeypatch.setattr(app, 'play_card', resolve)
    lines = f'Choose Region and defender\n{selected_region}\n{selected_defender}\n'
    output = StringIO()
    assert app.main(['--scenario', rc.SCENARIO_GREAT_REVOLT, '--seed', '125', '--bots', '',
                     '--card-edition', board.get('card_edition', 'legacy')],
                    stdin=StringIO(lines * 2), stdout=output) == 0
    chunks = output.getvalue().split(f'{faction}: choose the Event Battle.')
    assert len(chunks) == 3
    for before_choice in chunks[:2]:
        for current in (board['current_card'], 3):
            for line in get_card_text(current, board['scenario'], board.get('card_edition')).splitlines():
                assert line in before_choice
    assert f'{faction}: changes since your last decision' in chunks[1]
    assert 'Aedui Resources: 0 -> 2' in chunks[1]
