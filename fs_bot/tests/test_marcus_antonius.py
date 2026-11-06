"""Card Reference 6: Roman Scout and Battle, or an optional Auxilia relocation.

§8.1.1 declines a wholly ineffective NP Event; §8.2.3 retains the Roman
priorities. A human beneficiary chooses both actions on the current board.
"""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_available, place_piece
from fs_bot.bots.bot_common import should_decline_event
from fs_bot.cards.base_piece_choices import KIND
from fs_bot.cards.card_text import get_card_text
from fs_bot.cards.event_conditions import np_event_available
from fs_bot.cli.display import HumanTurnDisplay, format_board
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine import execute as ex
from fs_bot.engine.agent import RETREAT
from fs_bot.engine.free_actions import (
    execute_free_action_plan, validate_free_action_response,
)
from fs_bot.engine.game_engine import (
    ACTION_EVENT, _action_transaction, adjust_eligibility, get_sop_factions,
)
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import SeatSession, DecisionPending, board_copy


def board(scenario=rc.SCENARIO_GREAT_REVOLT, human=False):
    state = build_initial_state(scenario, seed=7)
    state['current_card'] = state['current_card_id'] = 6
    state['next_card'] = 4
    state['non_player_factions'] = set(get_sop_factions(state))
    if human:
        state['non_player_factions'].discard(rc.ROMANS)
    return state


def event(state, executor=rc.ROMANS):
    return ex._execute_event(state, executor, {'command': ACTION_EVENT,
        'details': {'card_id': 6, 'text_preference': rc.EVENT_UNSHADED}}, human=True)


def scout_move():
    return {'command': None, 'sa': rc.SA_SCOUT, 'sa_regions': [], 'details': {
        'scout_plan': {'auxilia_moves': [{
            'from_region': rc.PROVINCIA, 'to_region': rc.SEQUANI,
            'count': 4, 'piece_state': rc.REVEALED}], 'scout_targets': []}}}


def battle(region=rc.SEQUANI, enemy=rc.ARVERNI):
    return {'command': rc.CMD_BATTLE, 'regions': [region], 'details': {
        'battle_plan': [{'region': region, 'target': enemy}]}}


def human_board(scenario=rc.SCENARIO_GREAT_REVOLT):
    state = board(scenario, human=True)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 4,
                piece_state=rc.REVEALED)
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 4,
                piece_state=rc.REVEALED)
    refresh_all_control(state)
    return state


@pytest.mark.parametrize('scenario', rc.ALL_SCENARIOS)
def test_np_declines_when_neither_scout_nor_battle_has_an_effect(scenario):
    state = board(scenario)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION, 4,
                from_legions_track=True)
    # Enemies share a Region only with a Fort, which cannot attack.
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.FORT)
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 2)
    refresh_all_control(state)
    called = []
    state['decision_agent'] = lambda *args: called.append(args)
    before = encode(board_copy(state))
    assert np_event_available(state, 6, rc.ROMANS, False) is False
    assert should_decline_event(state, 6, rc.ROMANS)
    assert encode(board_copy(state)) == before and not called
    # Card 6's shaded eligibility effect remains independent.
    assert np_event_available(state, 6, rc.ROMANS, True) is None


@pytest.mark.parametrize('scout_only', [True, False])
def test_either_optional_np_action_can_make_the_event_effective(scout_only):
    state = board()
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 4,
                piece_state=rc.REVEALED)
    place_piece(state, rc.PROVINCIA if scout_only else rc.SEQUANI,
                rc.ROMANS, rc.LEGION, 4, from_legions_track=True)
    if not scout_only:
        place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 2,
                    piece_state=rc.REVEALED)
    refresh_all_control(state)
    before = encode(state)
    assert np_event_available(state, 6, rc.ROMANS, False) is True
    assert not should_decline_event(state, 6, rc.ROMANS)
    assert encode(state) == before
    result = event(state)['free_actions']
    assert result[0 if scout_only else 1]['result']['executed']
    if scout_only:
        assert result[1]['declined_no_effect']
    assert validate_state(state) == []


def test_availability_checks_roman_beneficiary_even_when_aedui_execute():
    state = board()
    place_piece(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND, 4)
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 2)
    assert np_event_available(state, 6, rc.AEDUI, False) is False
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 4)
    assert np_event_available(state, 6, rc.AEDUI, False) is True


@pytest.mark.parametrize('auxilia,expected', [(1, False), (2, True)])
def test_np_requires_possible_enemy_losses_even_with_a_battle_target(auxilia, expected):
    state = board()
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, auxilia,
                piece_state=rc.REVEALED)
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.CITADEL)
    state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] = rc.ARVERNI
    state['tribes'][rc.TRIBE_SEQUANI]['citadel'] = True
    before = encode(state)
    assert np_event_available(state, 6, rc.ROMANS, False) is expected
    assert encode(state) == before


def test_default_battle_preserves_roman_player_before_np_target_priority():
    state = board()
    state['non_player_factions'].remove(rc.AEDUI)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 4,
                piece_state=rc.REVEALED)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEGION, 4,
                from_legions_track=True)
    for faction in (rc.ARVERNI, rc.AEDUI):
        place_piece(state, rc.SEQUANI, faction, rc.WARBAND, 2,
                    piece_state=rc.REVEALED)
    state['decision_agent'] = lambda *args: {'retreat': False} if args[-1]['kind'] == RETREAT else None
    result = event(state)['free_actions'][1]['result']
    assert result['battles_resolved'] == [(rc.SEQUANI, rc.AEDUI)]
    assert count_pieces(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND) == 2


def test_ariovistus_availability_respects_diviciacus_target_exclusion():
    state = board(rc.SCENARIO_ARIOVISTUS)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 4,
                piece_state=rc.REVEALED)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEGION, 4,
                from_legions_track=True)
    place_piece(state, rc.SEQUANI, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    place_piece(state, rc.MANDUBII, rc.BELGAE, rc.ALLY)
    state['tribes'][rc.TRIBE_MANDUBII]['allied_faction'] = rc.BELGAE
    assert np_event_available(state, 6, rc.ROMANS, False) is False


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
@pytest.mark.parametrize('executor', [rc.ROMANS, rc.AEDUI])
def test_human_roman_scout_then_battle_is_free_and_doubles_auxilia(scenario, executor):
    state = human_board(scenario)
    requests = []
    def choose(live, faction, request):
        if request['kind'] == RETREAT:
            return {'retreat': False}
        if request['kind'] != 'free_action':
            return None
        assert faction == rc.ROMANS
        requests.append(request)
        if request['request_type'] == 'event_sa':
            assert request['allowed_sas'] == [rc.SA_SCOUT]
            return scout_move()
        assert count_pieces(live, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 4
        assert request['allowed_commands'] == [rc.CMD_BATTLE]
        assert request['max_regions'] == 1 and not request['with_sa']
        assert request['double_auxilia']
        return battle()
    state['decision_agent'] = choose
    result = event(state, executor)
    assert len(requests) == 2
    assert all(item['result']['executed'] for item in result['free_actions'])
    assert count_pieces(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND) == 0
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 0
    assert state['resources'][rc.ROMANS] == 0
    assert not state.get('_free_action_factions')
    assert 'card_6_double_auxilia_losses' not in state.get('event_modifiers', {})
    assert validate_state(state) == []


@pytest.mark.parametrize('decline_scout,decline_battle', [(True, True), (True, False), (False, True)])
def test_human_may_independently_decline_either_action(decline_scout, decline_battle):
    state = human_board()
    if decline_scout and not decline_battle:
        # A separate ready force makes Battle independent of Scout.
        place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 4,
                    piece_state=rc.REVEALED)
    before = encode(board_copy(state))
    def choose(live, faction, request):
        if request['kind'] == RETREAT:
            return {'retreat': False}
        if request['kind'] != 'free_action':
            return None
        if request['request_type'] == 'event_sa':
            return {'decline': True} if decline_scout else scout_move()
        return {'decline': True} if decline_battle else battle()
    state['decision_agent'] = choose
    result = ex._resolve_card6_scout_battle(state)
    for item, declined in zip(result, (decline_scout, decline_battle)):
        assert bool(item.get('declined')) == declined
        if not declined:
            assert item['result']['executed']
    if decline_scout and decline_battle:
        assert encode(board_copy(state)) == before


@pytest.mark.parametrize('invalid', ['second_region', 'sa'])
def test_human_battle_scope_cannot_be_expanded(invalid):
    state = human_board()
    request = {'request_type': 'event_command', 'allowed_commands': [rc.CMD_BATTLE],
               'max_regions': 1, 'with_sa': False, 'double_auxilia': True}
    action = battle()
    if invalid == 'second_region':
        action['details']['battle_plan'].append({'region': rc.PROVINCIA, 'target': rc.BELGAE})
    else:
        action['sa'] = rc.SA_BESIEGE
    before = encode(state)
    assert validate_free_action_response(state, rc.ROMANS, request, action)
    assert encode(state) == before


def test_double_auxilia_is_trusted_request_data_and_does_not_leak():
    state = board()
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 4,
                piece_state=rc.REVEALED)
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 4,
                piece_state=rc.REVEALED)
    state['decision_agent'] = lambda *args: {'retreat': False} if args[-1]['kind'] == RETREAT else None
    action = battle()
    action['double_auxilia'] = action['details']['double_auxilia'] = True
    normal = deepcopy(state)
    request = {'request_type': 'event_command', 'allowed_commands': [rc.CMD_BATTLE],
               'max_regions': 1, 'with_sa': False, 'double_auxilia': True}
    before = encode(board_copy(state))
    assert validate_free_action_response(state, rc.ROMANS, request, action) is None
    assert encode(board_copy(state)) == before
    execute_free_action_plan(state, rc.ROMANS, request, action)
    execute_free_action_plan(normal, rc.ROMANS, {k: v for k, v in request.items()
                                               if k != 'double_auxilia'}, action)
    assert count_pieces(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND) == 0
    assert count_pieces(normal, rc.SEQUANI, rc.ARVERNI, rc.WARBAND) == 2


@pytest.mark.parametrize('human', [False, True])
def test_free_battle_still_applies_command_capability_prefire(human):
    state = board(human=human)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 4,
                piece_state=rc.REVEALED)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.LEGION, 4,
                from_legions_track=True)
    place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 6,
                piece_state=rc.REVEALED)
    state['capabilities'][27] = rc.EVENT_SHADED
    def choose(live, faction, request):
        if request['kind'] == RETREAT:
            return {'retreat': False}
        if human and request['kind'] == 'free_action':
            return {'decline': True} if request['request_type'] == 'event_sa' else battle()
        return None
    state['decision_agent'] = choose
    result = event(state)
    assert result['free_actions'][1]['result']['executed']
    # Card 27 shaded: 6 Arverni first inflict one Loss on the Romans.
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 3
    assert count_pieces(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND) == 0


def _driver(session):
    def callback(*args):
        pass
    callback.transaction_checkpoint = session.checkpoint
    callback.transaction_restore = session.restore
    return callback


def test_scout_then_pause_save_resume_displays_changes_and_replays_once(tmp_path):
    state = human_board()
    output = StringIO()
    display = HumanTurnDisplay(output)
    display.remember(state, [rc.ROMANS])
    session = SeatSession(state, {'seat': rc.ROMANS}, [], display)
    state['decision_agent'] = session.reactive
    session.import_inbox([{'response': scout_move()}])
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending):
        with _action_transaction(state, _driver(session)):
            event(state, rc.AEDUI)
    assert encode(board_copy(state)) == before
    pending = session.data['pending']
    request = decode(pending['request'])
    assert request['allowed_commands'] == [rc.CMD_BATTLE]
    pending_board = decode(pending['board'])
    assert count_pieces(pending_board, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 4
    shown = output.getvalue()
    assert 'Sequani: Romans Revealed Auxilia: 0 -> 4' in shown
    for card in (6, 4):
        for line in get_card_text(card, state['scenario']).splitlines():
            assert line in shown
    save_game(state, tmp_path / 'marcus.json', meta=session.meta, log=session.log)
    restored, meta, log = load_game(tmp_path / 'marcus.json')
    resumed = SeatSession(restored, meta, log, HumanTurnDisplay(StringIO()))
    restored['decision_agent'] = resumed.reactive
    resumed.import_inbox({'decision_id': pending['id'], 'response': {'decline': True}})
    with _action_transaction(restored, _driver(resumed)):
        result = event(restored, rc.AEDUI)
    resumed.finish()
    assert result['free_actions'][0]['result']['executed']
    assert result['free_actions'][1]['declined']
    assert count_pieces(restored, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 4
    assert count_pieces(restored, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 0
    assert len(log) == 2
    assert [decode(row['assistant_response']) for row in log] == [scout_move(), {'decline': True}]
    assert not resumed.data['journal'] and not resumed.data['queue']


def test_terminal_can_show_board_then_decline_both_actions(monkeypatch):
    from fs_bot.cli import menus
    state = human_board()
    output = StringIO()
    monkeypatch.setattr(menus, '_BOARD_HOOK', [lambda: output.write(format_board(state))])
    state['decision_agent'] = make_cli_reactive(
        [rc.ROMANS], StringIO('board\nDecline\nboard\nDecline\n'), output)
    result = ex._resolve_card6_scout_battle(state)
    assert all(item['declined'] for item in result)
    assert output.getvalue().count(format_board(state)) == 2


def shaded_event(state, params=None, executor=rc.BELGAE, *, npc=False):
    action = {'command': rc.FIRST_DID_EVENT, 'regions': [], 'details': {
        'card_id': 6, 'text_preference': rc.EVENT_SHADED, 'event_params': params or {}}}
    actor_key = 'bot_action' if npc else 'player_action'
    return ex.execute_decision(state, executor, {'action': ACTION_EVENT, actor_key: action})


def selection(visibility, count, region=rc.SEQUANI, faction=rc.ROMANS):
    return {'region': region, 'target_faction': faction, 'piece_type': rc.AUXILIA,
            'piece_state': visibility, 'count': count}


@pytest.mark.parametrize('scenario,executor', [
    (rc.SCENARIO_GREAT_REVOLT, rc.BELGAE),
    (rc.SCENARIO_ARIOVISTUS, rc.GERMANS),
])
def test_shaded_moves_exact_cohorts_without_flipping_or_returning_them(scenario, executor):
    state = board(scenario)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 3)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 2, piece_state=rc.REVEALED)
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA, 3, piece_state=rc.SCOUTED)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA)
    pool = get_available(state, rc.ROMANS, rc.AUXILIA)
    choices = [selection(rc.REVEALED, 2), selection(rc.SCOUTED, 2, rc.TREVERI)]
    assert shaded_event(state, {'piece_choices': choices}, executor)['executed']
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 3
    assert count_pieces(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces_by_state(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, rc.HIDDEN) == 1
    for visibility in (rc.REVEALED, rc.SCOUTED):
        assert count_pieces_by_state(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, visibility) == 2
    assert get_available(state, rc.ROMANS, rc.AUXILIA) == pool
    assert validate_state(state) == []


@pytest.mark.parametrize('choices', [
    [selection(rc.REVEALED, 5)],
    [selection(rc.REVEALED, 3), selection(rc.REVEALED, 1)],
    [selection(rc.REVEALED, 1, rc.PROVINCIA)],
    [selection(rc.REVEALED, 1, faction=rc.AEDUI)],
])
def test_shaded_invalid_exact_plan_rolls_back_movement_and_eligibility(choices):
    state = board()
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 3, piece_state=rc.REVEALED)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 2, piece_state=rc.REVEALED)
    before = encode(board_copy(state))
    assert shaded_event(state, {'piece_choices': choices})['rejected']
    assert encode(board_copy(state)) == before


def test_shaded_zero_moves_still_applies_both_eligibility_clauses():
    state = board()
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 4)
    assert shaded_event(state, {'piece_choices': []})['executed']
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 4
    adjust_eligibility(state, {rc.BELGAE: {'action': ACTION_EVENT}})
    assert state['eligibility'][rc.BELGAE] == rc.ELIGIBLE
    assert state['eligibility'][rc.ROMANS] == rc.INELIGIBLE
    adjust_eligibility(state, {})
    assert state['eligibility'][rc.ROMANS] == rc.ELIGIBLE


def test_shaded_legacy_plan_retains_its_origins_and_preserves_visibility():
    state = board()
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 4, piece_state=rc.REVEALED)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 2, piece_state=rc.REVEALED)
    params = {'auxilia_moves': [[rc.PROVINCIA, 4], [rc.SEQUANI, 2]]}
    assert shaded_event(state, params)['executed']
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces_by_state(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 6


def test_shaded_selected_piece_removed_at_timing_window_is_not_replaced_by_resident():
    state = board(human=True)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 3, piece_state=rc.REVEALED)
    params = {'piece_choices': [selection(rc.REVEALED, 2)], 'stage_timing_actions': {
        '6.moves:0': [{'kind': 'voluntary_removal', 'response': {'operations': [{
            'action': 'remove', 'region': rc.SEQUANI, 'piece_type': rc.AUXILIA,
            'piece_state': rc.REVEALED, 'count': 1, 'cohort': 'event.6.moves.0'}]}}]}}
    assert shaded_event(state, params, rc.ROMANS)['executed']
    assert count_pieces(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces_by_state(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 1
    assert state['eligibility'][rc.ROMANS] == rc.ELIGIBLE


def test_shaded_german_bot_declines_without_a_qualified_origin_and_uses_its_tiers():
    from fs_bot.bots.german_bot import node_g3b

    state = board(rc.SCENARIO_ARIOVISTUS)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 3)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 4)
    assert node_g3b(state) == 'Yes'
    place_piece(state, rc.SUGAMBRI, rc.ROMANS, rc.AUXILIA, 1, piece_state=rc.REVEALED)
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA, 1, piece_state=rc.SCOUTED)
    assert node_g3b(state) == 'No'
    assert shaded_event(state, executor=rc.GERMANS, npc=True)['executed']
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 7
    assert count_pieces(state, rc.SUGAMBRI, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA) == 0


@pytest.mark.parametrize('executor,preferred', [(rc.BELGAE, rc.ATREBATES), (rc.ARVERNI, rc.MANDUBII)])
def test_shaded_bots_use_their_printed_priorities(executor, preferred):
    state = board()
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(state, preferred, rc.ROMANS, rc.AUXILIA, 1, piece_state=rc.REVEALED)
    place_piece(state, preferred, rc.ROMANS, rc.LEGION, from_legions_track=True)
    assert shaded_event(state, executor=executor, npc=True)['executed']
    assert count_pieces(state, preferred, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces_by_state(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 1


def test_shaded_cli_selects_cohorts_for_the_executor():
    from fs_bot.cli.human_plan import _collect_event_params

    state = board()
    state['non_player_factions'].discard(rc.BELGAE)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 3)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 2, piece_state=rc.REVEALED)
    output = StringIO()
    assert _collect_event_params(state, rc.BELGAE, 6, True, StringIO(), output) == {}
    state['decision_agent'] = make_cli_reactive([rc.BELGAE], StringIO('board\n3\n2\n1\n'), output)
    assert shaded_event(state)['executed']
    assert 'move to Provincia' in output.getvalue()
    assert count_pieces_by_state(state, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, rc.REVEALED) == 2


def test_shaded_saved_choice_keeps_id_and_resumes_with_the_same_move(tmp_path):
    state = board()
    state['non_player_factions'].discard(rc.BELGAE)
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA, 4, piece_state=rc.REVEALED)

    def session_for(board, meta=None, log=None):
        session = SeatSession(board, meta or {'seat': rc.BELGAE}, [] if log is None else log,
                              HumanTurnDisplay(StringIO()))
        board['decision_agent'] = lambda b, f, r: session.reactive(b, f, r) if r['kind'] == KIND else None
        return session

    session = session_for(state)
    before = encode(board_copy(state))
    with pytest.raises(DecisionPending):
        with _action_transaction(state, _driver(session)):
            shaded_event(state)
    pending = deepcopy(session.data['pending'])
    request = decode(pending['request'])
    assert request['owner'] == rc.BELGAE and request['destination'] == rc.PROVINCIA
    assert encode(board_copy(state)) == before
    save_game(state, tmp_path / 'marcus_shaded.json', meta=session.meta, log=session.log)
    restored, meta, log = load_game(tmp_path / 'marcus_shaded.json', validate=True)
    resumed = session_for(restored, meta, log)
    with pytest.raises(DecisionPending):
        with _action_transaction(restored, _driver(resumed)):
            shaded_event(restored)
    assert resumed.data['pending'] == pending
    choices = [selection(rc.REVEALED, 3)]
    resumed.import_inbox({'decision_id': pending['id'], 'response': {'selections': choices}})
    with _action_transaction(restored, _driver(resumed)):
        assert shaded_event(restored)['executed']
    resumed.finish()
    reference = decode(before)
    assert shaded_event(reference, {'piece_choices': choices})['executed']
    assert encode(board_copy(restored)) == encode(board_copy(reference))
    assert len(log) == 1 and validate_state(restored) == []
