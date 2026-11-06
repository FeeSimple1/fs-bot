"""Unshaded Catuvolcus chooses same-faction Allies and exact Warbands."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, count_pieces_by_state, get_available, place_piece
from fs_bot.bots.bot_common import should_decline_event
from fs_bot.cards.base_piece_choices import KIND
from fs_bot.cards.card_effects import _ally_tribe
from fs_bot.cards.event_eval import is_event_effective
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.human_plan import _collect_event_params
from fs_bot.cli.reactive import make_cli_reactive
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT, _action_transaction
from fs_bot.state.serialize import decode, encode, load_game, save_game
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.seat_session import DecisionPending, SeatSession, board_copy


def position(scenario=rc.SCENARIO_GREAT_REVOLT):
    state = build_initial_state(scenario, seed=61)
    state.update(current_card=61, current_card_id=61)
    return state


def populated():
    state = position()
    assert _ally_tribe(state, rc.TRIBE_EBURONES, rc.ROMANS)
    assert _ally_tribe(state, rc.TRIBE_NERVII, rc.BELGAE)
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.WARBAND, 5, piece_state=rc.SCOUTED)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 4)
    return state


def selection(faction, count, visibility=rc.HIDDEN, region=rc.NERVII):
    return {'region': region, 'target_faction': faction, 'piece_type': rc.WARBAND,
            'piece_state': visibility, 'count': count}


def play(state, params=None, executor=rc.AEDUI, *, npc=False):
    action = {'command': rc.FIRST_DID_EVENT, 'regions': [], 'details': {
        'card_id': 61, 'text_preference': rc.EVENT_UNSHADED, 'event_params': params or {}}}
    actor_key = 'bot_action' if npc else 'player_action'
    return execute_decision(state, executor, {'action': ACTION_EVENT, actor_key: action})


def test_exact_mix_can_remove_warbands_of_other_factions_than_the_ally():
    state = populated()
    pool = get_available(state, rc.BELGAE, rc.ALLY)
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 2, piece_state=rc.REVEALED)
    assert play(state, {'ally_removals': [rc.TRIBE_NERVII], 'piece_choices': [
        selection(rc.ARVERNI, 3, rc.SCOUTED), selection(rc.GERMANS, 2, rc.REVEALED)]})['executed']
    assert state['tribes'][rc.TRIBE_NERVII]['allied_faction'] is None
    assert state['tribes'][rc.TRIBE_EBURONES]['allied_faction'] == rc.ROMANS
    assert get_available(state, rc.BELGAE, rc.ALLY) == pool + 1
    assert count_pieces(state, rc.NERVII, rc.ARVERNI, rc.WARBAND) == 2
    assert count_pieces(state, rc.NERVII, rc.BELGAE, rc.WARBAND) == 4
    assert count_pieces(state, rc.NERVII, rc.GERMANS, rc.WARBAND) == 0
    assert validate_state(state) == []


@pytest.mark.parametrize('number', [1, 2])
def test_human_can_choose_one_or_both_allies_of_the_same_faction(number):
    state = position()
    tribes = [rc.TRIBE_EBURONES, rc.TRIBE_NERVII]
    for tribe in tribes:
        assert _ally_tribe(state, tribe, rc.BELGAE)
    assert play(state, {'ally_removals': tribes[:number], 'piece_choices': []})['executed']
    assert count_pieces(state, rc.NERVII, rc.BELGAE, rc.ALLY) == 2 - number
    for tribe in tribes[:number]:
        assert state['tribes'][tribe]['allied_faction'] is None


@pytest.mark.parametrize('params', [
    {'ally_removals': [rc.TRIBE_EBURONES, rc.TRIBE_NERVII]},
    {'ally_removals': [rc.TRIBE_NERVII, rc.TRIBE_NERVII]},
    {'ally_removals': [rc.TRIBE_MORINI]},
    {'ally_removals': []},
    {'ally_removals': [rc.TRIBE_NERVII], 'piece_choices': [selection(rc.ARVERNI, 4, rc.SCOUTED)]},
    {'ally_removals': [rc.TRIBE_NERVII], 'piece_choices': [selection(rc.BELGAE, 4),
                                                        selection(rc.ARVERNI, 2, rc.SCOUTED)]},
    {'ally_removals': [rc.TRIBE_NERVII], 'piece_choices': [selection(rc.ARVERNI, 5, rc.SCOUTED, rc.MORINI)]},
])
def test_rejects_invalid_selections_and_rolls_back_the_first_step(params):
    state = populated()
    assert _ally_tribe(state, rc.TRIBE_MORINI, rc.BELGAE)
    place_piece(state, rc.MORINI, rc.ARVERNI, rc.WARBAND, 5, piece_state=rc.SCOUTED)
    before = encode(board_copy(state))
    assert play(state, params)['rejected']
    assert encode(board_copy(state)) == before


def test_fewer_than_five_warbands_without_allies_are_still_removed():
    state = position()
    place_piece(state, rc.MORINI, rc.ARVERNI, rc.WARBAND, 5)
    assert not is_event_effective(state, 61)
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.WARBAND, 2, piece_state=rc.SCOUTED)
    assert is_event_effective(state, 61)
    assert play(state, {'piece_choices': [selection(rc.ARVERNI, 2, rc.SCOUTED)]})['executed']
    assert count_pieces(state, rc.NERVII, rc.ARVERNI, rc.WARBAND) == 0
    assert count_pieces(state, rc.MORINI, rc.ARVERNI, rc.WARBAND) == 5


@pytest.mark.parametrize('scenario,player', [
    (rc.SCENARIO_GREAT_REVOLT, rc.ARVERNI), (rc.SCENARIO_ARIOVISTUS, rc.GERMANS),
])
def test_aedui_bot_requires_printed_player_targets_and_limits_both_steps(scenario, player):
    state = position(scenario)
    state['non_player_factions'] = {rc.AEDUI, rc.BELGAE}
    assert _ally_tribe(state, rc.TRIBE_NERVII, rc.BELGAE)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 5)
    assert should_decline_event(state, 61, rc.AEDUI)
    assert _ally_tribe(state, rc.TRIBE_EBURONES, player)
    place_piece(state, rc.NERVII, player, rc.WARBAND, 2, piece_state=rc.SCOUTED)
    assert not should_decline_event(state, 61, rc.AEDUI)
    assert play(state, npc=True)['executed']
    assert state['tribes'][rc.TRIBE_EBURONES]['allied_faction'] is None
    assert state['tribes'][rc.TRIBE_NERVII]['allied_faction'] == rc.BELGAE
    assert count_pieces(state, rc.NERVII, player, rc.WARBAND) == 0
    assert count_pieces(state, rc.NERVII, rc.BELGAE, rc.WARBAND) == 5


def test_legacy_faction_counts_keep_timing_and_fill_remaining_removals():
    state = populated()
    timing = {'kind': 'voluntary_removal', 'response': {'operations': [{
        'action': 'remove', 'region': rc.NERVII, 'piece_type': rc.WARBAND,
        'piece_state': rc.HIDDEN, 'count': 1}]}}
    params = {'ally_removals': [rc.TRIBE_EBURONES], 'warband_removals': [
        {'faction': rc.ARVERNI, 'count': 1, 'timing_actions': [timing]}]}
    assert play(state, params, executor=rc.BELGAE)['executed']
    assert state['tribes'][rc.TRIBE_EBURONES]['allied_faction'] is None
    assert count_pieces(state, rc.NERVII, rc.ARVERNI, rc.WARBAND) == 0
    assert count_pieces(state, rc.NERVII, rc.BELGAE, rc.WARBAND) == 3


def test_live_warband_choice_follows_the_ally_removal_and_timing_window():
    state = position()
    assert _ally_tribe(state, rc.TRIBE_EBURONES, rc.ROMANS)
    place_piece(state, rc.NERVII, rc.BELGAE, rc.WARBAND, 2, piece_state=rc.SCOUTED)
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.WARBAND, 1)
    seen = []

    def agent(board, faction, request):
        if request['kind'] == KIND:
            if request['step'] == 'allies':
                return {'tribes': [rc.TRIBE_EBURONES]}
            seen.append((faction, request['required'][rc.WARBAND],
                         board['tribes'][rc.TRIBE_EBURONES]['allied_faction']))
            return {'selections': request['available']}

    state['decision_agent'] = agent
    timing = {'kind': 'voluntary_removal', 'response': {'operations': [{
        'action': 'remove', 'region': rc.NERVII, 'piece_type': rc.WARBAND,
        'piece_state': rc.SCOUTED, 'count': 1}]}}
    params = {'stage_timing_actions': {'61.warband_choice': [timing]}}
    assert play(state, params, executor=rc.BELGAE)['executed']
    assert seen == [(rc.BELGAE, 2, None)]
    assert count_pieces(state, rc.NERVII, rc.BELGAE, rc.WARBAND) == 0


def test_terminal_offers_named_allies_and_scouted_warbands():
    state = populated()
    output = StringIO()
    assert _collect_event_params(state, rc.AEDUI, 61, False, StringIO(), output) == {}
    terminal = make_cli_reactive({rc.AEDUI}, StringIO('board\n2\n1\n5\n'), output)
    state['decision_agent'] = lambda b, f, r: terminal(b, f, r) if r['kind'] == KIND else None
    assert play(state)['executed']
    assert f'{rc.TRIBE_NERVII} ({rc.BELGAE})' in output.getvalue()
    assert f'{rc.SCOUTED} {rc.WARBAND}' in output.getvalue()
    assert state['tribes'][rc.TRIBE_NERVII]['allied_faction'] is None
    assert count_pieces(state, rc.NERVII, rc.ARVERNI, rc.WARBAND) == 0


def test_assistant_resumes_warbands_with_the_named_ally_choice_preserved(tmp_path):
    state = populated()
    initial = encode(board_copy(state))

    def session_for(board, meta=None, log=None):
        session = SeatSession(board, meta or {'seat': rc.AEDUI}, [] if log is None else log,
                              HumanTurnDisplay(StringIO()))
        board['decision_agent'] = lambda b, f, r: session.reactive(b, f, r) if r['kind'] == KIND else None
        return session

    def attempt(session):
        def driver(*args):
            pass

        driver.transaction_checkpoint = session.checkpoint
        driver.transaction_restore = session.restore
        with _action_transaction(session.state, driver):
            return play(session.state)

    session = session_for(state)
    with pytest.raises(DecisionPending):
        attempt(session)
    first = session.data['pending']['id']
    allies = [rc.TRIBE_NERVII]
    session.import_inbox({'decision_id': first, 'response': {'tribes': allies}})
    with pytest.raises(DecisionPending):
        attempt(session)
    pending = deepcopy(session.data['pending'])
    assert pending['id'] != first
    assert decode(pending['request'])['step'] == 'warbands'
    assert encode(board_copy(state)) == initial

    path = tmp_path / 'catuvolcus.json'
    save_game(state, path, meta=session.meta, log=session.log)
    restored, meta, log = load_game(path, validate=True)
    resumed = session_for(restored, meta, log)
    with pytest.raises(DecisionPending):
        attempt(resumed)
    assert resumed.data['pending'] == pending
    picks = [selection(rc.ARVERNI, 5, rc.SCOUTED)]
    resumed.import_inbox({'decision_id': pending['id'], 'response': {'selections': picks}})
    assert attempt(resumed)['executed']
    resumed.finish()
    reference = decode(initial)
    assert play(reference, {'ally_removals': allies, 'piece_choices': picks})['executed']
    assert encode(board_copy(restored)) == encode(board_copy(reference))
    assert len(log) == 2 and validate_state(restored) == []
