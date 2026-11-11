"""Round-four Event selections and Harvest's Resource track bound."""

from io import StringIO
import json
from types import SimpleNamespace

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, get_available, place_piece, remove_piece
from fs_bot.cards.card_effects import _ally_tribe, _unally_tribe
from fs_bot.cards.capabilities import get_capability_owner
from fs_bot.cli.display import HumanTurnDisplay
from fs_bot.cli.human_plan import _collect_event_params
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_EVENT, get_sop_factions
from fs_bot.engine.moves import validate_player_action
from fs_bot.engine.victory import calculate_victory_score, check_any_victory
from fs_bot.engine.winter import harvest_phase, run_winter_round
from fs_bot.state.serialize import encode, load_game, save_game
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state
from fs_bot.tools.seat_session import SeatSession, board_copy


def event(card, params, shaded=False):
    return {'command': rc.FIRST_DID_EVENT, 'details': {
        'card_id': card, 'event_params': params,
        'text_preference': rc.EVENT_SHADED if shaded else rc.EVENT_UNSHADED,
    }}


def clean(state):
    assert validate_state(state) == check_structural_integrity(state) == []


def play(state, actor, card, params, *, shaded=False, rejected=False):
    state['current_card'] = card
    action = event(card, params, shaded)
    clean(state)
    before = encode(board_copy(state))
    ok, detail = validate_player_action(state, actor, action)
    assert ok is not rejected, detail
    assert encode(board_copy(state)) == before
    result = execute_decision(state, actor, {'action': ACTION_EVENT, 'player_action': action})
    assert result['executed'] is not rejected, result
    if rejected:
        assert result['rejected']
        assert encode(board_copy(state)) == before
    clean(state)


def hostages_board(edition='original'):
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=4, card_edition=edition)
    _unally_tribe(state, rc.TRIBE_HELVII)
    return state


HELVII = {'tribe': rc.TRIBE_HELVII, 'region': rc.PROVINCIA, 'faction': rc.BELGAE}


@pytest.mark.parametrize('edition', ['original', 'second-edition'])
@pytest.mark.parametrize('entry', [
    {'tribe': rc.TRIBE_CATUVELLAUNI, 'region': rc.PROVINCIA, 'faction': rc.BELGAE},
    dict(HELVII, faction=rc.ROMANS, warband_faction=rc.BELGAE),
    dict(HELVII, warband_faction=rc.ROMANS),
    {'region': rc.PROVINCIA, 'faction': rc.BELGAE},
])
def test_hostages_rejects_wrong_tribe_region_or_piece_owner(edition, entry):
    state = hostages_board(edition)
    play(state, rc.BELGAE, 22, {'target_tribes': [entry]}, shaded=True, rejected=True)


@pytest.mark.parametrize('entries', [[], [HELVII, HELVII], [HELVII] * 3])
def test_hostages_enforces_one_or_two_distinct_tribes(entries):
    play(hostages_board(), rc.BELGAE, 22, {'target_tribes': entries}, shaded=True, rejected=True)


def test_hostages_uses_colony_region_and_independent_warband_owner():
    state = hostages_board()
    place_piece(state, rc.BRITANNIA, rc.ROMANS, rc.AUXILIA)
    play(state, rc.ROMANS, 71, {'region': rc.BRITANNIA})
    colony = next(tribe for tribe, info in state['tribes'].items()
                  if info.get('region') == rc.BRITANNIA)
    _unally_tribe(state, colony)
    play(state, rc.ROMANS, 22, {'target_tribes': [
        HELVII, {'tribe': colony, 'faction': rc.AEDUI, 'warband_faction': rc.GERMANS},
    ]}, shaded=True)
    assert state['tribes'][rc.TRIBE_HELVII]['allied_faction'] == rc.BELGAE
    assert state['tribes'][colony]['allied_faction'] == rc.AEDUI
    assert count_pieces(state, rc.BRITANNIA, rc.GERMANS, rc.WARBAND) == 1


def test_hostages_terminal_preserves_partial_placement_and_excludes_a_used_tribe():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=4)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    place_piece(state, rc.BRITANNIA, rc.ROMANS, rc.AUXILIA)
    targets = {rc.TRIBE_HELVII, rc.TRIBE_CATUVELLAUNI}
    for tribe in state['tribes']:
        if not get_available(state, rc.BELGAE, rc.ALLY):
            break
        if (tribe not in targets
                and rc.TRIBE_FACTION_RESTRICTION.get(tribe, rc.BELGAE) == rc.BELGAE):
            _ally_tribe(state, tribe, rc.BELGAE)
    assert get_available(state, rc.BELGAE, rc.ALLY) == 0
    first = f'{rc.TRIBE_HELVII} ({rc.PROVINCIA})'
    second = f'{rc.TRIBE_CATUVELLAUNI} ({rc.BRITANNIA})'
    output = StringIO()
    params = _collect_event_params(state, rc.BELGAE, 22, True,
        StringIO(f'{first}\n{rc.BELGAE}\n{rc.BELGAE}\ny\n{second}\n{rc.BELGAE}\n{rc.BELGAE}\n'),
        output)
    assert first not in output.getvalue().split('Place at a second Tribe?', 1)[1]
    play(state, rc.BELGAE, 22, params, shaded=True)
    assert all(state['tribes'][tribe]['allied_faction'] is None for tribe in targets)
    assert count_pieces(state, rc.PROVINCIA, rc.BELGAE, rc.WARBAND) == 1
    assert count_pieces(state, rc.BRITANNIA, rc.BELGAE, rc.WARBAND) == 1


def test_hostages_can_resolve_when_no_subdued_tribe_has_roman_pieces():
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=4)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    assert _ally_tribe(state, rc.TRIBE_HELVII, rc.ROMANS)
    play(state, rc.BELGAE, 22, {}, shaded=True)
    assert state['tribes'][rc.TRIBE_HELVII]['allied_faction'] == rc.ROMANS


def test_hostages_terminal_selects_the_tribe_once_and_places_both_pieces():
    state = hostages_board()
    output = StringIO()
    params = _collect_event_params(state, rc.ROMANS, 22, True,
                                  StringIO(f'{rc.TRIBE_HELVII} ({rc.PROVINCIA})\n'
                                           f'{rc.BELGAE}\n{rc.AEDUI}\nn\n'), output)
    assert params['target_tribes'] == [{'tribe': rc.TRIBE_HELVII, 'faction': rc.BELGAE,
                                      'warband_faction': rc.AEDUI}]
    play(state, rc.ROMANS, 22, params, shaded=True)
    assert state['tribes'][rc.TRIBE_HELVII]['allied_faction'] == rc.BELGAE
    assert count_pieces(state, rc.PROVINCIA, rc.AEDUI, rc.WARBAND) == 1


@pytest.mark.parametrize('params', [{}, {'target_factions': []},
    {'target_factions': [rc.ARVERNI, rc.ROMANS]}, {'target_factions': rc.ARVERNI}])
def test_celtic_rites_requires_a_nonempty_list_of_gallic_targets(params):
    play(hostages_board(), rc.ROMANS, 46, params, rejected=True)


def test_celtic_rites_applies_both_effects_once_per_selected_faction():
    state = hostages_board()
    state['resources'].update({rc.ARVERNI: 20, rc.BELGAE: 1})
    play(state, rc.ROMANS, 46, {'target_factions': [rc.ARVERNI, rc.BELGAE, rc.ARVERNI]})
    assert (state['resources'][rc.ARVERNI], state['resources'][rc.BELGAE]) == (17, 0)
    assert state['forced_ineligible'] == {rc.ARVERNI: 1, rc.BELGAE: 1}


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
def test_roman_bot_celtic_rites_uses_its_printed_targets(scenario):
    state = setup_scenario(scenario, seed=4)
    state['current_card'] = 46
    start = dict(state['resources'])
    result = execute_decision(state, rc.ROMANS, {'action': ACTION_EVENT,
                                                'bot_action': event(46, {})})
    assert result['executed'], result
    targets = (rc.ARVERNI, rc.BELGAE) if scenario == rc.SCENARIO_GREAT_REVOLT else (rc.BELGAE,)
    assert state.get('forced_ineligible') == dict.fromkeys(targets, 1)
    assert state['resources'] == {f: max(0, n - 3) if f in targets else n for f, n in start.items()}


@pytest.mark.parametrize('actor', [rc.BELGAE, rc.ROMANS])
def test_shaded_horse_cannot_be_awarded_to_another_faction(actor):
    play(hostages_board(), actor, 59, {'faction': rc.AEDUI}, shaded=True, rejected=True)


def test_shaded_horse_requires_a_gallic_executor_and_preserves_matching_legacy_choice():
    state = hostages_board()
    play(state, rc.ROMANS, 59, {}, shaded=True)
    assert 59 not in state['capabilities']
    play(state, rc.BELGAE, 59, {'faction': rc.BELGAE}, shaded=True)
    assert state['capabilities'][59] == rc.EVENT_SHADED
    assert get_capability_owner(state, 59) == rc.BELGAE
    play(state, rc.ROMANS, 59, {})
    assert state['capabilities'][59] == rc.EVENT_UNSHADED
    assert get_capability_owner(state, 59) is None


@pytest.mark.parametrize('params', [{}, {'region': rc.PROVINCIA}, {'region': rc.BRITANNIA}])
def test_abatis_requires_an_eligible_region_when_own_warbands_exist(params):
    state = setup_scenario(rc.SCENARIO_ARIOVISTUS, seed=317)
    play(state, rc.AEDUI, 'A64', params, rejected=True)


def test_abatis_terminal_offers_own_scouted_warband_and_roman_no_effect():
    state = setup_scenario(rc.SCENARIO_ARIOVISTUS, seed=317)
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.WARBAND, piece_state=rc.SCOUTED)
    output = StringIO()
    params = _collect_event_params(state, rc.AEDUI, 'A64', False, StringIO(f'{rc.CARNUTES}\n'), output)
    assert rc.PROVINCIA not in output.getvalue()
    play(state, rc.AEDUI, 'A64', params)
    assert state['markers'][rc.CARNUTES][rc.MARKER_ABATIS] == rc.AEDUI
    play(state, rc.ROMANS, 'A64', {})
    assert state['markers'][rc.CARNUTES][rc.MARKER_ABATIS] == rc.AEDUI


def test_abatis_invalid_plan_keeps_saved_turn_pending_for_correction(tmp_path):
    from fs_bot.tests.test_action_window_frontends import leave_timing_unchanged
    from fs_bot.tools import llm_seat

    state = setup_scenario(rc.SCENARIO_ARIOVISTUS, seed=317)
    # The carnyx still triggers its Arverni Phase. Keep this test's human
    # pieces out of the unrelated immediate Ambush at Sequani.
    remove_piece(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND)
    state['current_card'] = state['current_card_id'] = 'A64'
    state['played_cards'], state['deck'], state['next_card'] = ['A64'], [], None
    state['non_player_factions'] = set(get_sop_factions(state)) - {rc.AEDUI}
    for faction in state['eligibility']:
        state['eligibility'][faction] = rc.ELIGIBLE if faction == rc.AEDUI else rc.INELIGIBLE
    display = HumanTurnDisplay(StringIO())
    meta = {'seat': rc.AEDUI, 'scenario': state['scenario'], 'seed': 317}
    SeatSession(state, meta, [], display)
    path = tmp_path / 'save.json'
    save_game(state, path, meta=meta, log=[])
    args = SimpleNamespace(dir=str(tmp_path))
    assert llm_seat.cmd_play(args) == 0
    initial, initial_meta, _ = load_game(path)
    turn = initial_meta['assistant_session']['pending']
    args.decision_id = turn['id']
    args.response = json.dumps({'action': ACTION_EVENT, 'player_action': event('A64', {})})
    assert llm_seat.cmd_submit(args) == 0
    leave_timing_unchanged(args)
    rejected, rejected_meta, log = load_game(path)
    assert encode(rejected) == encode(initial)
    assert rejected_meta['assistant_session']['pending'] == turn and not log
    assert not rejected_meta['assistant_session']['journal']

    args.decision_id = turn['id']
    args.response = json.dumps({'action': ACTION_EVENT, 'player_action':
                                event('A64', {'region': rc.AEDUI_REGION})})
    assert llm_seat.cmd_submit(args) == 0
    leave_timing_unchanged(args)
    final, final_meta, log = load_game(path, validate=True)
    assert final['markers'][rc.AEDUI_REGION][rc.MARKER_ABATIS] == rc.AEDUI
    assert not final_meta['assistant_session']['pending']
    assert [entry['assistant_id'] for entry in log if entry.get('action') == ACTION_EVENT] == [turn['id']]


@pytest.mark.parametrize('owner,troop', [(rc.ROMANS, rc.WARBAND), (rc.AEDUI, rc.AUXILIA)])
def test_bellovaci_refuses_impossible_troop_pair_before_removing_victims(owner, troop):
    state = setup_scenario(rc.SCENARIO_ARIOVISTUS, seed=317)
    play(state, rc.ROMANS, 'A69', {'ally_faction': rc.ROMANS, 'piece_faction': owner,
                                   'piece_type': troop}, rejected=True)


def negative_harvest_position():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=14)
    tribes = [tribe for tribe in state['tribes'] if tribe not in rc.TRIBE_FACTION_RESTRICTION]
    for faction, group in (
        (rc.GERMANS, rc.SUEBI_TRIBES),
        (rc.ARVERNI, [rc.TRIBE_ARVERNI, *tribes[:9]]),
        (rc.AEDUI, [rc.TRIBE_AEDUI, *tribes[9:14]]),
        (rc.BELGAE, tribes[14:22]),
    ):
        for tribe in group:
            assert _ally_tribe(state, tribe, faction)
            if faction == rc.BELGAE:
                place_piece(state, rc.TRIBE_TO_REGION[tribe], rc.ROMANS, rc.AUXILIA)
    for region in (rc.MORINI, rc.NERVII, rc.ATREBATES, rc.TREVERI, rc.CARNUTES, rc.MANDUBII):
        place_piece(state, region, rc.GERMANS, rc.SETTLEMENT)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, rc.AEDUI_REGION, rc.AEDUI, rc.LEADER, leader_name=rc.DIVICIACUS)
    place_piece(state, rc.UBII, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    place_piece(state, rc.BITURIGES, rc.BELGAE, rc.LEADER, leader_name=rc.BODUOGNATUS)
    clean(state)
    assert check_any_victory(state) is None
    assert calculate_victory_score(state, rc.ROMANS) == -2
    return state


@pytest.mark.parametrize('starting', [0, 1])
def test_negative_roman_earnings_cannot_leave_the_track(starting):
    state = negative_harvest_position()
    state['resources'][rc.ROMANS] = starting
    assert harvest_phase(state)[rc.ROMANS] == -2
    assert state['resources'][rc.ROMANS] == 0
    clean(state)


def test_full_winter_keeps_roman_resources_on_the_track():
    state = negative_harvest_position()
    result = run_winter_round(state, relocations={})
    assert result['phases']['harvest'][rc.ROMANS] == -2
    assert state['resources'][rc.ROMANS] == 0
    clean(state)


def test_positive_roman_earnings_still_stop_at_45():
    state = negative_harvest_position()
    for region in state['spaces']:
        if count_pieces(state, region, rc.GERMANS, rc.SETTLEMENT):
            remove_piece(state, region, rc.GERMANS, rc.SETTLEMENT)
    state['resources'][rc.ROMANS] = 43
    assert harvest_phase(state)[rc.ROMANS] == 4
    assert state['resources'][rc.ROMANS] == rc.MAX_RESOURCES
    clean(state)
