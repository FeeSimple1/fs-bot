"""§§1.4.1/5.1.1: timing choices belong between complete Event effects."""
from copy import deepcopy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board import pieces
from fs_bot.cards.card_effects import execute_event, _ally_tribe
from fs_bot.engine.action_windows import scope, COHORTS
from fs_bot.engine.execute import _execute_event
from fs_bot.engine.spring import UNLOCK_KEY
from fs_bot.engine.voluntary_removal import operation
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import encode


def board(faction=rc.AEDUI, scenario=rc.SCENARIO_GREAT_REVOLT):
    result = build_initial_state(scenario, seed=23)
    result['non_player_factions'] = set()
    result['executing_faction'] = faction
    return result


def remove(region, kind=rc.WARBAND, count=1, **fields):
    entry = {'action': 'remove', 'region': region, 'piece_type': kind, 'count': count}
    if kind in (rc.WARBAND, rc.AUXILIA):
        entry['piece_state'] = rc.HIDDEN
    return dict(entry, **fields)


def timing(*operations):
    return [{'kind': 'voluntary_removal', 'response': {'operations': list(operations)}}]


def run(state, card, params, shaded=False):
    state['event_params'] = params
    with scope(state, actor=state['executing_faction'], plan=params, force=True):
        return execute_event(state, card, shaded)


@pytest.mark.parametrize('card,scenario,shaded,field,regions,faction', [
    (40, rc.SCENARIO_GREAT_REVOLT, False, 'placements', (rc.SEQUANI, rc.PROVINCIA), rc.AEDUI),
    ('A40', rc.SCENARIO_ARIOVISTUS, False, 'placements', (rc.SEQUANI, rc.PROVINCIA), rc.AEDUI),
    (70, rc.SCENARIO_PAX_GALLICA, True, 'placements', (rc.CARNUTES, rc.MANDUBII), rc.ARVERNI),
    ('A56', rc.SCENARIO_GALLIC_WAR, True, 'warband_placements', (rc.ATREBATES, rc.NERVII), rc.BELGAE),
])
def test_empty_pool_can_be_reclaimed_then_reused_between_placements(card, scenario, shaded, field, regions, faction):
    state = board(faction, scenario)
    total = pieces.get_available(state, faction, rc.WARBAND)
    pieces.place_piece(state, rc.VENETI, faction, rc.WARBAND, total)
    params = {field: [
        {'region': regions[0], 'piece_type': rc.WARBAND, 'count': 1,
         'timing_actions': timing(remove(rc.VENETI))},
        {'region': regions[1], 'piece_type': rc.WARBAND, 'count': 1,
         'timing_actions': timing(remove(regions[0]))},
    ]}
    rng = state['rng'].getstate()
    run(state, card, params, shaded)
    assert pieces.count_pieces(state, regions[0], faction, rc.WARBAND) == 0
    assert pieces.count_pieces(state, regions[1], faction, rc.WARBAND) == 1
    assert pieces.count_pieces(state, rc.VENETI, faction, rc.WARBAND) == total - 1
    assert pieces.get_available(state, faction, rc.WARBAND) == 0
    assert state['rng'].getstate() == rng
    assert validate_state(state) == []


def test_later_a37_ally_can_reuse_first_placed_disc_without_preflight_rejection():
    state = board(scenario=rc.SCENARIO_ARIOVISTUS)
    pieces.place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 4)
    # Leave exactly one disc Available, respecting faction-exclusive circles.
    for tribe, info in state['tribes'].items():
        if pieces.get_available(state, rc.AEDUI, rc.ALLY) == 1:
            break
        if (rc.TRIBE_TO_REGION.get(tribe) != rc.SEQUANI
                and rc.TRIBE_FACTION_RESTRICTION.get(tribe, rc.AEDUI) == rc.AEDUI):
            _ally_tribe(state, tribe, rc.AEDUI)
    assert pieces.get_available(state, rc.AEDUI, rc.ALLY) == 1
    params = {'target_region': rc.SEQUANI, 'ally_placements': [
        {'tribe': rc.TRIBE_SEQUANI, 'faction': rc.AEDUI},
        {'tribe': rc.TRIBE_HELVETII, 'faction': rc.AEDUI,
         'timing_actions': timing(remove(rc.SEQUANI, rc.ALLY, tribe=rc.TRIBE_SEQUANI))}], 'moves': []}
    run(state, 'A37', params)
    assert state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] is None
    assert state['tribes'][rc.TRIBE_HELVETII]['allied_faction'] == rc.AEDUI
    assert pieces.get_available(state, rc.AEDUI, rc.ALLY) == 0
    assert validate_state(state) == []


def test_a29_removed_placement_cohort_does_not_raid_with_residents():
    state = board(rc.GERMANS, rc.SCENARIO_ARIOVISTUS)
    pieces.place_piece(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, 2)
    params = {'placements': [
        {'region': rc.TREVERI, 'piece_type': rc.WARBAND, 'count': 4},
        {'region': rc.TREVERI, 'piece_type': rc.SETTLEMENT,
         'timing_actions': timing(remove(rc.TREVERI, count=4,
                                          cohort=f'card_A29_raid.{rc.TREVERI}'))},
    ]}
    action = {'command': rc.FIRST_DID_EVENT, 'details': {
        'card_id': 'A29', 'text_preference': rc.EVENT_SHADED,
        'event_params': params}}
    resources = deepcopy(state['resources'])
    with scope(state, actor=rc.GERMANS, plan=action, force=True):
        result = _execute_event(state, rc.GERMANS, action, human=True)
    assert result['executed'], result
    assert result['free_actions'][0]['result']['declined_no_effect']
    assert pieces.count_pieces_by_state(state, rc.TREVERI, rc.GERMANS,
                                       rc.WARBAND, rc.HIDDEN) == 2
    assert state['resources'] == resources
    assert validate_state(state) == []


def test_free_event_command_executes_its_authored_completion_once():
    from fs_bot.engine.free_actions import execute_free_action_plan
    state = board(rc.AEDUI)
    pieces.place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 2)
    action = {'command': rc.CMD_RAID, 'sa': 'No SA', 'details': {
        'raid_plan': [{'region': rc.CARNUTES, 'target': None}],
        'after_command_timing_actions': timing(
            remove(rc.CARNUTES, piece_state=rc.REVEALED)),
    }}
    request = {'kind': 'free_action', 'request_type': 'event_command',
               'acting_faction': rc.AEDUI, 'allowed_commands': [rc.CMD_RAID],
               'with_sa': False, 'free': True}
    with scope(state, actor=rc.AEDUI, plan=action, force=True):
        result = execute_free_action_plan(state, rc.AEDUI, request, action)
    assert result['executed'], result
    assert pieces.count_pieces(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 1
    assert pieces.count_pieces_by_state(state, rc.CARNUTES, rc.AEDUI,
                                       rc.WARBAND, rc.HIDDEN) == 1
    assert validate_state(state) == []


@pytest.mark.parametrize('card', [32, 62, 66])
def test_selected_relocation_group_removal_never_substitutes_a_resident(card):
    state = board(rc.ARVERNI)
    origin, second, destination = rc.ARVERNI_REGION, rc.VENETI, rc.PICTONES
    pieces.place_piece(state, origin, rc.ARVERNI, rc.WARBAND, 2)
    pieces.place_piece(state, second, rc.ARVERNI, rc.WARBAND, 3)
    entries = [
        {'from_region': origin, 'to_region': destination, 'piece_type': rc.WARBAND, 'count': 2},
        {'from_region': second, 'to_region': destination, 'piece_type': rc.WARBAND, 'count': 2,
         'timing_actions': timing(remove(second, cohort=f'event.{card}.moves.1'))},
    ]
    params = {'moves': entries, 'target_region': destination}
    run(state, card, params, card == 66)
    assert pieces.count_pieces(state, destination, rc.ARVERNI, rc.WARBAND) == 3
    assert pieces.count_pieces(state, second, rc.ARVERNI, rc.WARBAND) == 1
    assert COHORTS not in state
    assert validate_state(state) == []


def test_pure_preview_applies_explicit_relocation_timing_without_input_or_rng():
    state = board(rc.ARVERNI)
    pieces.place_piece(state, rc.SEQUANI, rc.ARVERNI, rc.WARBAND, 2)
    params = {'moves': [{'from_region': rc.SEQUANI, 'to_region': rc.MANDUBII,
        'piece_type': rc.WARBAND, 'count': 2,
        'timing_actions': timing(remove(rc.SEQUANI, cohort='event.32.moves.0'))}]}
    def agent(*args):
        pytest.fail('Pure Event preview consulted live input')
    agent.supports_action_windows = True
    state['decision_agent'] = agent
    state['_diviciacus_preview'] = True
    rng = state['rng'].getstate()
    run(state, 32, params)
    assert pieces.count_pieces(state, rc.MANDUBII, rc.ARVERNI, rc.WARBAND) == 1
    assert state['rng'].getstate() == rng


def test_replacement_window_never_exposes_half_a_remove_replace_pair():
    state = board()
    count = pieces.get_available(state, rc.AEDUI, rc.WARBAND) - 1
    pieces.place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, count)
    pieces.place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 2)
    observations = []
    def agent(live, faction, request):
        if request['kind'] != 'voluntary_removal':
            return None
        if request['window'].get('step') == '22.replacements':
            observations.append((pieces.count_pieces(live, rc.CARNUTES, rc.BELGAE, rc.WARBAND),
                                 pieces.count_pieces(live, rc.CARNUTES, rc.AEDUI, rc.WARBAND)))
        return {'done': True}
    agent.supports_action_windows = True
    state['decision_agent'] = agent
    run(state, 22, {'replacements': [
        {'region': rc.CARNUTES, 'target_faction': rc.BELGAE},
        {'region': rc.CARNUTES, 'target_faction': rc.BELGAE}]})
    assert observations == [(2, count), (1, count + 1)]


def pax():
    state = setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=23)
    state['non_player_factions'] = set()
    state[UNLOCK_KEY] = True
    state.pop('first_winter_special', None)
    state['winter_count'] = 1
    state['current_card'] = 70
    return state


def test_other_players_event_offers_global_vercingetorix_between_effects():
    state = pax()
    state['executing_faction'] = rc.BELGAE
    answers = []
    def agent(live, faction, request):
        if request['kind'] == 'spring_leader':
            answers.append((faction, request['window'].get('index')))
            if request['window'].get('index') == 1:
                assert pieces.count_pieces(live, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
                return {'region': rc.CARNUTES}
            return {'defer': True}
        return {'done': True}
    agent.supports_action_windows = True
    state['decision_agent'] = agent
    run(state, 70, {'placements': [
        {'region': rc.CARNUTES, 'count': 1}, {'region': rc.MANDUBII, 'count': 1}]}, True)
    assert answers == [(rc.ARVERNI, 0), (rc.ARVERNI, 1)]
    assert pieces.get_leader_in_region(state, rc.CARNUTES, rc.ARVERNI) == rc.VERCINGETORIX


def test_boxed_vercingetorix_can_enter_before_later_relocation_group():
    state = pax()
    state['executing_faction'] = rc.ARVERNI
    params = {'moves': [
        {'from_region': rc.ARVERNI_REGION, 'to_region': rc.PICTONES,
         'piece_type': rc.WARBAND, 'count': 1},
        {'from_region': rc.SEQUANI, 'to_region': rc.MANDUBII, 'piece_type': rc.LEADER,
         'timing_actions': [{'kind': 'spring_leader', 'response': {'region': rc.SEQUANI}}]}]}
    run(state, 32, params)
    assert pieces.get_leader_in_region(state, rc.MANDUBII, rc.ARVERNI) == rc.VERCINGETORIX
    assert validate_state(state) == []


def test_event_grant_does_not_transfer_own_piece_removal_authority():
    state = board(rc.BELGAE)
    pieces.place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    pieces.place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    asked = []
    def agent(live, faction, request):
        if request['kind'] == 'voluntary_removal':
            asked.append(faction)
            return {'done': True}
        if request['kind'] == 'free_action':
            return {'decline': True}
        return None
    agent.supports_action_windows = True
    state['decision_agent'] = agent
    action = {'command': rc.FIRST_DID_EVENT, 'details': {
        'card_id': 6, 'text_preference': rc.EVENT_UNSHADED, 'event_params': {}}}
    with scope(state, actor=rc.BELGAE, force=True):
        result = _execute_event(state, rc.BELGAE, action, human=True)
    assert result['executed']
    assert asked and set(asked) == {rc.BELGAE}


def test_legacy_agent_has_identical_event_board_rng_and_no_new_requests():
    initial = board(rc.BELGAE)
    params = {'placements': [{'region': rc.CARNUTES, 'count': 1},
                             {'region': rc.MANDUBII, 'count': 1}]}
    legacy, baseline = deepcopy(initial), deepcopy(initial)
    def agent(*args):
        pytest.fail('Non-opted-in callback received a new timing prompt')
    legacy['decision_agent'] = agent
    run(legacy, 70, params, True)
    run(baseline, 70, params, True)
    legacy.pop('decision_agent')
    assert encode(legacy) == encode(baseline)


def test_invalid_later_a37_choice_rolls_back_prior_timing_and_placement():
    state = board(scenario=rc.SCENARIO_ARIOVISTUS)
    pieces.place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 4)
    pieces.place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND)
    params = {'target_region': rc.SEQUANI, 'ally_placements': [
        {'tribe': rc.TRIBE_SEQUANI, 'faction': rc.AEDUI,
         'timing_actions': timing(remove(rc.CARNUTES))}],
        'moves': [{'from_region': rc.VENETI, 'to_region': rc.SEQUANI,
                   'piece_type': rc.WARBAND, 'count': 1}]}
    state['event_params'] = params
    before = encode(state)
    with pytest.raises(pieces.PieceError):
        run(state, 'A37', params)
    assert encode(state) == before


def test_scalar_terminal_timing_is_retained_when_player_finishes_event_choices():
    state = board()
    pieces.place_piece(state, rc.VENETI, rc.AEDUI, rc.WARBAND)
    run(state, 40, {'placements': [], 'stage_timing_actions': {
        '40.placements:0': timing(remove(rc.VENETI))}})
    assert pieces.count_pieces(state, rc.VENETI, rc.AEDUI, rc.WARBAND) == 0


def test_a37_timing_can_free_an_initially_occupied_target_tribe():
    state = board(scenario=rc.SCENARIO_ARIOVISTUS)
    pieces.place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, 4)
    _ally_tribe(state, rc.TRIBE_SEQUANI, rc.AEDUI)
    available = pieces.get_available(state, rc.AEDUI, rc.ALLY)
    run(state, 'A37', {'target_region': rc.SEQUANI, 'ally_placements': [
        {'tribe': rc.TRIBE_SEQUANI, 'faction': rc.AEDUI,
         'timing_actions': timing(remove(rc.SEQUANI, rc.ALLY, tribe=rc.TRIBE_SEQUANI))}]})
    assert state['tribes'][rc.TRIBE_SEQUANI]['allied_faction'] == rc.AEDUI
    assert pieces.get_available(state, rc.AEDUI, rc.ALLY) == available


def test_interlude_retains_base_event_timing_without_unlocking_boxed_leader():
    state = pax()
    state.pop(UNLOCK_KEY)
    state['interlude_completed'] = True
    state['first_winter_special'] = {'place_vercingetorix_in_spring': True}
    state['executing_faction'] = rc.ARVERNI
    asked = []
    def agent(live, faction, request):
        asked.append(request['kind'])
        return {'done': True}
    agent.supports_action_windows = True
    state['decision_agent'] = agent
    run(state, 70, {'placements': [{'region': rc.CARNUTES, 'count': 1},
                                  {'region': rc.MANDUBII, 'count': 1}]}, True)
    assert 'voluntary_removal' in asked and 'spring_leader' not in asked
    assert rc.VERCINGETORIX in state['spring_box_leaders']


def test_event_pending_after_first_placement_survives_save_invalid_answer_and_resume(tmp_path):
    import io
    from fs_bot.cli.display import HumanTurnDisplay
    from fs_bot.engine.game_engine import _action_transaction
    from fs_bot.tools.seat_session import SeatSession, DecisionPending, board_copy
    from fs_bot.state.serialize import decode, save_game, load_game

    state = board()
    pieces.place_piece(state, rc.VENETI, rc.AEDUI, rc.WARBAND)
    params = {'placements': [
        {'region': rc.SEQUANI, 'piece_type': rc.WARBAND,
         'timing_actions': [{'kind': 'voluntary_removal', 'response': {'done': True}}]},
        {'region': rc.PROVINCIA, 'piece_type': rc.WARBAND}]}
    state['event_params'] = params
    meta, log = {'seat': rc.AEDUI}, []
    session = SeatSession(state, meta, log, HumanTurnDisplay(io.StringIO()))
    state['decision_agent'] = session.reactive
    before = encode(board_copy(state))

    def attempt(live, controller):
        def callback(*args):
            return None
        callback.transaction_checkpoint = controller.checkpoint
        callback.transaction_restore = controller.restore
        with _action_transaction(live, callback):
            with scope(live, actor=rc.AEDUI, force=True):
                execute_event(live, 40)
        controller.finish()

    with pytest.raises(DecisionPending):
        attempt(state, session)
    pending = deepcopy(session.data['pending'])
    assert decode(pending['request'])['window']['index'] == 1
    assert pieces.count_pieces(decode(pending['board']), rc.SEQUANI, rc.AEDUI, rc.WARBAND) == 1
    assert encode(board_copy(state)) == before
    save_game(state, tmp_path / 'event.json', meta=meta, log=log)
    restored, restored_meta, restored_log = load_game(tmp_path / 'event.json')
    resumed = SeatSession(restored, restored_meta, restored_log, HumanTurnDisplay(io.StringIO()))
    restored['decision_agent'] = resumed.reactive
    resumed.import_inbox({'decision_id': pending['id'], 'response': {
        'operations': [remove(rc.MANDUBII)]}})
    with pytest.raises(DecisionPending):
        attempt(restored, resumed)
    assert resumed.data['pending'] == pending
    assert encode(board_copy(restored)) == before
    resumed.import_inbox([{'decision_id': pending['id'], 'response': {
        'operations': [remove(rc.SEQUANI)]}}, {'response': {'done': True}}])
    attempt(restored, resumed)
    assert resumed.data['pending'] is None
    assert pieces.count_pieces(restored, rc.SEQUANI, rc.AEDUI, rc.WARBAND) == 0
    assert pieces.count_pieces(restored, rc.PROVINCIA, rc.AEDUI, rc.WARBAND) == 1
    assert len(restored_log) == 2
    assert restored['rng'].getstate() == state['rng'].getstate()
