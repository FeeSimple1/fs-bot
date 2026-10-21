"""Source-derived regressions for Event diagnostics from the 50-game census.

Card Reference 11/17/21/25/36/44/58; A Card Reference A19/A20/A21;
base Aedui/Roman and Ariovistus German specific Event instructions.
"""
from collections import Counter
from copy import deepcopy
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import (place_piece, count_pieces, count_pieces_by_state,
                                 get_available, get_leader_in_region)
from fs_bot.bots.bot_common import should_decline_event, get_dual_use_preference
from fs_bot.bots.aedui_bot import node_a_event
from fs_bot.cards.event_conditions import np_event_available
from fs_bot.commands.raid import validate_raid_steal_target
from fs_bot.engine import execute as ex
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.tools.error_census import census_result


def state(scenario=rc.SCENARIO_GREAT_REVOLT):
    board = build_initial_state(scenario, seed=19)
    board['non_player_factions'] = set(rc.FACTIONS)
    return board


def event(board, card, faction, shaded=False, params=None, human=False):
    board['current_card'] = board['current_card_id'] = card
    action = {'command': 'Event', 'sa': 'No SA', 'details': {
        'card_id': card, 'text_preference': rc.EVENT_SHADED if shaded else rc.EVENT_UNSHADED}}
    if params is not None:
        action['details']['event_params'] = params
    result = ex._execute_event(board, faction, action, human=human)
    assert result['executed']
    assert validate_state(board) == []
    return result


def census(result):
    counts, examples, occurrences = Counter(), {}, []
    census_result({'card_results': [{'card': 44, 'turn_result': {'actions_taken': {
        rc.AEDUI: {'bot_action': {'command': 'Event'}, 'execution': result}}}}]},
        counts, examples, rc.SCENARIO_GREAT_REVOLT, 19, occurrences)
    return occurrences


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
def test_numidians_places_full_auxilia_even_without_battle_target(scenario):
    board = state(scenario)
    place_piece(board, rc.PROVINCIA, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    before = get_available(board, rc.ROMANS, rc.AUXILIA)
    assert not should_decline_event(board, 11, rc.ROMANS)
    result = event(board, 11, rc.ROMANS)
    assert get_available(board, rc.ROMANS, rc.AUXILIA) == before - 3
    rows = census(result)
    assert rows and all(row['severity'] == 'legal-decline' for row in rows)


def test_numidians_np_requires_three_available_auxilia():
    board = state()
    place_piece(board, rc.PROVINCIA, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(board, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA,
                get_available(board, rc.ROMANS, rc.AUXILIA) - 2)
    assert should_decline_event(board, 11, rc.ROMANS)


def test_aquitani_extra_losses_can_attack_without_friendly_force():
    board = state()
    place_piece(board, rc.PICTONES, rc.ARVERNI, rc.WARBAND, 3, piece_state=rc.REVEALED)
    result = event(board, 25, rc.ROMANS)
    assert count_pieces(board, rc.PICTONES, rc.ARVERNI, rc.WARBAND) == 0
    assert result['free_actions'][0]['region'] == rc.PICTONES


@pytest.mark.parametrize('scenario,preference', [
    (rc.SCENARIO_GREAT_REVOLT, rc.EVENT_SHADED),
    (rc.SCENARIO_ARIOVISTUS, rc.EVENT_UNSHADED)])
@pytest.mark.parametrize('card,title', [
    (25, 'Aquitani'), (8, 'Baggage Trains'), (10, 'Ballistae'),
    (70, 'Camulogenus'), (46, 'Celtic Rites'), (35, 'Gallic Shouts'),
    (65, 'German Allegiances'), (59, 'Germanic Horse'),
    (68, 'Remi Influence'), (63, 'Winter Campaign')])
def test_aedui_specific_side_is_scenario_scoped(scenario, preference, card, title):
    assert rc.CARD_NAMES_BASE[card] == title
    board = state(scenario)
    board['current_card_id'] = card
    assert get_dual_use_preference(rc.AEDUI, scenario, card) == preference
    assert node_a_event(board)['details']['text_preference'] == preference


@pytest.mark.parametrize('scenario,player,allowed', [
    (rc.SCENARIO_GREAT_REVOLT, False, False),
    (rc.SCENARIO_GREAT_REVOLT, True, True),
    (rc.SCENARIO_ARIOVISTUS, False, True)])
def test_morasses_base_aedui_instruction_only_targets_player_gauls(scenario, player, allowed):
    board = state(scenario)
    place_piece(board, rc.MANDUBII, rc.AEDUI, rc.WARBAND, 4)
    place_piece(board, rc.MANDUBII, rc.BELGAE, rc.WARBAND, 2)
    if player:
        board['non_player_factions'].remove(rc.BELGAE)
    assert (ex._card36_battle_target(board, rc.AEDUI) is not None) == allowed
    assert np_event_available(board, 36, rc.AEDUI, False) == allowed


@pytest.mark.parametrize('visibility', [rc.REVEALED, rc.SCOUTED])
def test_aduatuca_marches_all_visibility_and_waives_hidden_superiority(visibility):
    board = state()
    place_piece(board, rc.NERVII, rc.ROMANS, rc.FORT)
    place_piece(board, rc.NERVII, rc.ROMANS, rc.AUXILIA, 8)
    place_piece(board, rc.TREVERI, rc.GERMANS, rc.WARBAND, 4, piece_state=visibility)
    result = ex._resolve_card58_german_ambush(board)
    assert result[0].get('executed') is not False
    assert count_pieces(board, rc.TREVERI, rc.GERMANS) == 0
    assert count_pieces(board, rc.NERVII, rc.GERMANS, rc.WARBAND) == 4
    assert count_pieces(board, rc.NERVII, rc.ROMANS, rc.AUXILIA) == 6
    assert count_pieces(board, rc.NERVII, rc.ROMANS, rc.FORT) == 1
    assert board['resources'].get(rc.GERMANS, 0) == 0


def test_card21_human_can_choose_raid_and_steal_despite_fort():
    board = state()
    board['non_player_factions'].remove(rc.ARVERNI)
    board['resources'][rc.ROMANS] = 10
    place_piece(board, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    requests = []
    def agent(st, faction, request):
        requests.append(request)
        assert faction == rc.ARVERNI
        assert set(request['allowed_commands']) == {'Raid', 'Battle'}
        assert request['allowed_regions'] == [rc.PROVINCIA]
        assert not request['with_sa']
        return {'command': 'Raid', 'regions': [], 'sa': 'No SA', 'sa_regions': [],
                'details': {'raid_plan': [{'region': rc.PROVINCIA, 'target': rc.ROMANS}]}}
    board['decision_agent'] = agent
    result = event(board, 21, rc.ARVERNI, True, {}, human=True)
    assert requests and result['free_actions'][0]['result']['executed']
    assert board['resources'][rc.ROMANS] == 9
    assert board['resources'][rc.ARVERNI] == 1
    assert count_pieces(board, rc.PROVINCIA, rc.ROMANS, rc.FORT) == 1
    assert 'card_21_no_fort' not in board['event_modifiers']
    assert not validate_raid_steal_target(board, rc.PROVINCIA, rc.ARVERNI, rc.ROMANS)[0]


def test_card21_terminal_menu_collects_scoped_raid():
    from fs_bot.cli.free_actions import collect_free_action
    board = state()
    place_piece(board, rc.PROVINCIA, rc.ARVERNI, rc.WARBAND, 4)
    place_piece(board, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    board['resources'][rc.ROMANS] = 3
    board['event_modifiers'] = {'card_21_no_fort': True}
    request = {'kind': 'free_action', 'request_type': 'event_command',
               'allowed_commands': ['Battle', 'Raid'], 'allowed_regions': [rc.PROVINCIA],
               'with_sa': False, 'free': True}
    output = io.StringIO()
    action = collect_free_action(board, rc.ARVERNI, request,
        io.StringIO('Plan the action\nRaid\nProvincia\n(done)\n1\nsteal from Romans\n'), output)
    assert action['command'] == 'Raid'
    assert 'Rally' not in output.getvalue() and 'March' not in output.getvalue()
    assert action['details']['raid_plan'][0]['target'] == rc.ROMANS


def test_card21_battle_applies_fort_exception_through_shared_executor():
    board = state()
    board['non_player_factions'].remove(rc.ARVERNI)
    place_piece(board, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    place_piece(board, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA, 8, piece_state=rc.REVEALED)
    def agent(st, faction, request):
        return {'command': 'Battle', 'regions': [rc.PROVINCIA], 'sa': 'No SA',
                'details': {'battle_plan': [{'region': rc.PROVINCIA, 'target': rc.ROMANS}]}}
    board['decision_agent'] = agent
    result = event(board, 21, rc.ARVERNI, True, {}, human=True)
    assert result['free_actions'][0]['result']['count'] == 1
    assert count_pieces(board, rc.PROVINCIA, rc.ROMANS, rc.AUXILIA) == 6


def test_card21_np_declines_when_no_placement_or_existing_force():
    board = state()
    place_piece(board, rc.MANDUBII, rc.ARVERNI, rc.WARBAND,
                get_available(board, rc.ARVERNI, rc.WARBAND))
    assert should_decline_event(board, 21, rc.ARVERNI)


def test_card44_optional_scout_is_explicit_decline_but_errors_remain_visible():
    board = state()
    result = {'executed': True, 'free_actions': ex._resolve_card44_scout(board)}
    assert [row['severity'] for row in census(result)] == ['legal-decline']
    result['free_actions'][0]['result']['errors'] = ['invalid Scout destination']
    assert 'illegal' in [row['severity'] for row in census(result)]


def test_a19_np_declines_unavailable_move_before_eligibility_effect():
    board = state(rc.SCENARIO_ARIOVISTUS)
    assert np_event_available(board, 'A19', rc.GERMANS, True) is False
    assert ex._resolve_a19_march_romans(board, rc.GERMANS)[0]['declined_no_effect']


def test_a19_moves_successor_and_counts_all_german_pieces_for_outnumbering():
    board = state(rc.SCENARIO_ARIOVISTUS)
    place_piece(board, rc.SEQUANI, rc.ROMANS, rc.LEADER, leader_name=rc.SUCCESSOR)
    place_piece(board, rc.MANDUBII, rc.GERMANS, rc.WARBAND)
    place_piece(board, rc.MANDUBII, rc.GERMANS, rc.ALLY)
    result = ex._resolve_a19_march_romans(board, rc.GERMANS)
    assert result[0]['dest'] == rc.MANDUBII
    assert get_leader_in_region(board, rc.MANDUBII, rc.ROMANS) == rc.SUCCESSOR


def test_a20_unshaded_adjacent_roman_ally_removes_scouted_arverni_without_seize():
    board = state(rc.SCENARIO_ARIOVISTUS)
    place_piece(board, rc.CARNUTES, rc.ROMANS, rc.ALLY)
    place_piece(board, rc.VENETI, rc.ARVERNI, rc.WARBAND, 2, piece_state=rc.SCOUTED)
    result = event(board, 'A20', rc.ROMANS)
    assert count_pieces(board, rc.VENETI, rc.ARVERNI) == 0
    assert result['free_actions'][0]['declined_no_effect']
    assert all(row['severity'] == 'legal-decline' for row in census(result))


def test_a20_projects_all_warbands_between_opposite_veneti_neighbours():
    from fs_bot.map.map_data import get_adjacent
    board = state(rc.SCENARIO_ARIOVISTUS)
    near = sorted(get_adjacent(rc.VENETI, board['scenario']))
    source, target = next((a, b) for a in near for b in near
                          if a != b and b not in get_adjacent(a, board['scenario']))
    place_piece(board, rc.VENETI, rc.ARVERNI, rc.ALLY)
    board['tribes'][rc.TRIBE_VENETI]['allied_faction'] = rc.ARVERNI
    place_piece(board, source, rc.ARVERNI, rc.WARBAND, 1)
    place_piece(board, source, rc.ARVERNI, rc.WARBAND, 3, piece_state=rc.SCOUTED)
    place_piece(board, target, rc.ROMANS, rc.AUXILIA, 4, piece_state=rc.REVEALED)
    result = ex._resolve_a20_arverni_ambush(board)
    assert result[0]['region'] == target
    assert result[0]['projected_warbands'] == 4
    assert count_pieces(board, target, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(board, target, rc.ARVERNI, rc.WARBAND) == 0
    assert count_pieces_by_state(board, source, rc.ARVERNI, rc.WARBAND, rc.REVEALED) == 4


def test_a20_and_a21_unavailable_specific_instructions_decline():
    from fs_bot.bots.german_bot import node_g3b
    board = state(rc.SCENARIO_ARIOVISTUS)
    for card in ('A20', 'A21', 'A19'):
        board['current_card_id'] = card
        assert node_g3b(board) == 'Yes'


def test_card17_roman_instruction_marches_revealed_germans_away_from_romans():
    board = state()
    place_piece(board, rc.TREVERI, rc.ROMANS, rc.AUXILIA)
    place_piece(board, rc.TREVERI, rc.GERMANS, rc.WARBAND, 4, piece_state=rc.REVEALED)
    place_piece(board, rc.NERVII, rc.BELGAE, rc.WARBAND, 2, piece_state=rc.REVEALED)
    result = ex._resolve_card17_march_ambush(board, 3)
    assert result[0]['marches'] == [{'source': rc.TREVERI, 'dest': rc.NERVII, 'warbands': 4}]
    assert result[0]['defender'] == rc.BELGAE
    assert count_pieces(board, rc.TREVERI, rc.ROMANS, rc.AUXILIA) == 1
    assert count_pieces(board, rc.NERVII, rc.BELGAE, rc.WARBAND) == 0


@pytest.mark.parametrize('card,shaded', [(17, False), (58, True), ('A19', True), ('A20', True), ('A21', True)])
def test_applicability_preview_preserves_live_board_rng_and_never_prompts(card, shaded):
    board = state(rc.SCENARIO_ARIOVISTUS if isinstance(card, str) else rc.SCENARIO_GREAT_REVOLT)
    def unexpected(*args):
        raise AssertionError('preview queried human')
    board['decision_agent'] = unexpected
    before = deepcopy({k: v for k, v in board.items() if k not in ('rng', 'decision_agent')})
    rng = board['rng'].getstate()
    np_event_available(board, card, rc.GERMANS if shaded else rc.ROMANS, shaded)
    assert {k: v for k, v in board.items() if k not in ('rng', 'decision_agent')} == before
    assert board['rng'].getstate() == rng


def test_litaviccus_no_roman_target_declines_before_event():
    board = state()
    assert np_event_available(board, 45, rc.BELGAE, True) is False
    assert ex._resolve_card45_battle(board, rc.BELGAE)[0]['declined_no_effect']
    place_piece(board, rc.MANDUBII, rc.ROMANS, rc.AUXILIA)
    place_piece(board, rc.MANDUBII, rc.AEDUI, rc.WARBAND, 2)
    assert np_event_available(board, 45, rc.BELGAE, True) is True


def test_card21_fort_exception_is_only_arverni_in_provincia_and_not_citadels():
    board = state()
    board['event_modifiers'] = {'card_21_no_fort': True}
    board['resources'][rc.ROMANS] = 3
    board['resources'][rc.BELGAE] = 3
    place_piece(board, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    place_piece(board, rc.MANDUBII, rc.ROMANS, rc.FORT)
    place_piece(board, rc.PROVINCIA, rc.BELGAE, rc.CITADEL)
    assert validate_raid_steal_target(board, rc.PROVINCIA, rc.ARVERNI, rc.ROMANS)[0]
    assert not validate_raid_steal_target(board, rc.MANDUBII, rc.ARVERNI, rc.ROMANS)[0]
    assert not validate_raid_steal_target(board, rc.PROVINCIA, rc.AEDUI, rc.ROMANS)[0]
    assert not validate_raid_steal_target(board, rc.PROVINCIA, rc.ARVERNI, rc.BELGAE)[0]


def test_aquitani_roman_instruction_targets_arverni_then_belgae_never_aedui():
    board = state()
    place_piece(board, rc.PICTONES, rc.AEDUI, rc.WARBAND, 9)
    assert np_event_available(board, 25, rc.ROMANS, False) is False
    place_piece(board, rc.PICTONES, rc.BELGAE, rc.WARBAND, 5)
    place_piece(board, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND, 1)
    assert ex._derive_card_25(board, rc.ROMANS, False)['battle_region'] == rc.ARVERNI_REGION
    result = event(board, 25, rc.ROMANS)
    assert result['free_actions'][0]['defender'] == rc.ARVERNI
    assert count_pieces(board, rc.PICTONES, rc.AEDUI, rc.WARBAND) == 9


def test_invalid_scout_plan_is_not_relabelled_as_a_legal_decline(monkeypatch):
    from fs_bot.cards import dumnorix
    monkeypatch.setattr(dumnorix, 'scout_cohort', lambda *args: {
        'executed': False, 'errors': ['invalid Scout destination']})
    action = ex._resolve_card44_scout(state())[0]
    assert not action['result'].get('declined_no_effect')
    assert 'illegal' in [row['severity'] for row in census({'free_actions': [action]})]


def test_event_march_applicability_during_frost_keeps_live_scope_and_rng():
    board = state()
    board['frost'] = True
    place_piece(board, rc.NERVII, rc.ROMANS, rc.FORT)
    place_piece(board, rc.NERVII, rc.ROMANS, rc.AUXILIA, 4)
    place_piece(board, rc.TREVERI, rc.GERMANS, rc.WARBAND, 4, piece_state=rc.REVEALED)
    before = deepcopy({k: v for k, v in board.items() if k != 'rng'})
    rng = board['rng'].getstate()
    assert np_event_available(board, 58, rc.BELGAE, True)
    assert {k: v for k, v in board.items() if k != 'rng'} == before
    assert board['rng'].getstate() == rng


def test_card17_combines_groups_that_only_jointly_enable_ambush():
    board = state()
    for region in (rc.MORINI, rc.NERVII):
        place_piece(board, region, rc.ROMANS, rc.AUXILIA)
        place_piece(board, region, rc.GERMANS, rc.WARBAND, 2)
    place_piece(board, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 3)
    assert np_event_available(board, 17, rc.ROMANS, False)
    result = ex._resolve_card17_march_ambush(board, 3)
    assert {m['source'] for m in result[0]['marches']} == {rc.MORINI, rc.NERVII}
    assert result[0]['region'] == rc.ATREBATES
    assert count_pieces(board, rc.ATREBATES, rc.GERMANS, rc.WARBAND) == 4
    assert count_pieces(board, rc.ATREBATES, rc.BELGAE, rc.WARBAND) == 1


def test_a45_germans_require_removable_np_target_but_ignore_leader_control_scope():
    board = state(rc.SCENARIO_ARIOVISTUS)
    board['current_card_id'] = 'A45'
    place_piece(board, rc.MANDUBII, rc.GERMANS, rc.WARBAND)
    # Legions, other NP Belgae/Arverni and no-target marker alone are not
    # prescribed NP removals. A45 waives region selection, not A8.7.1 priorities.
    place_piece(board, rc.MANDUBII, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(board, rc.MANDUBII, rc.BELGAE, rc.WARBAND)
    assert np_event_available(board, 'A45', rc.GERMANS, True) is False
    place_piece(board, rc.MANDUBII, rc.ROMANS, rc.AUXILIA)
    assert np_event_available(board, 'A45', rc.GERMANS, True) is True
    place_piece(board, rc.MANDUBII, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    assert np_event_available(board, 'A45', rc.GERMANS, True) is False
    # The NP-specific gate does not change any human selection/marker choice.
    assert np_event_available(board, 'A45', rc.ROMANS, True) is None


def _ally(board, region, tribe, faction, piece=rc.ALLY):
    place_piece(board, region, faction, piece)
    board['tribes'][tribe]['allied_faction'] = faction


def test_gobannitio_aedui_places_own_citadel_and_removes_dispersed_marker():
    board = state()
    board['tribes'][rc.TRIBE_ARVERNI]['status'] = rc.DISPERSED
    assert np_event_available(board, 26, rc.AEDUI, False)
    event(board, 26, rc.AEDUI)
    assert board['tribes'][rc.TRIBE_ARVERNI]['allied_faction'] == rc.AEDUI
    assert board['tribes'][rc.TRIBE_ARVERNI]['status'] is None
    assert count_pieces(board, rc.ARVERNI_REGION, rc.AEDUI, rc.CITADEL) == 1
    assert count_pieces(board, rc.ARVERNI_REGION, rc.ROMANS, rc.ALLY) == 0


@pytest.mark.parametrize('successor', [False, True])
def test_gobannitio_missing_vercingetorix_still_replaces_allies_and_skips_dispersed(successor):
    board = state()
    if successor:
        place_piece(board, rc.ARVERNI_REGION, rc.ARVERNI, rc.LEADER,
                    leader_name=rc.SUCCESSOR)
    _ally(board, rc.ARVERNI_REGION, rc.TRIBE_CADURCI, rc.ROMANS)
    board['tribes'][rc.TRIBE_VOLCAE]['status'] = rc.DISPERSED
    assert np_event_available(board, 26, rc.ARVERNI, True)
    result = event(board, 26, rc.ARVERNI, True)
    assert board['tribes'][rc.TRIBE_CADURCI]['allied_faction'] == rc.ARVERNI
    assert board['tribes'][rc.TRIBE_ARVERNI]['allied_faction'] == rc.ARVERNI
    assert board['tribes'][rc.TRIBE_VOLCAE]['allied_faction'] is None
    assert result['free_actions'][0]['executed'] is False


def test_gobannitio_shaded_never_removes_enemy_citadel_as_ally():
    from fs_bot.cards.card_effects import execute_card_26
    board = state()
    _ally(board, rc.ARVERNI_REGION, rc.TRIBE_ARVERNI, rc.AEDUI, rc.CITADEL)
    board['event_params'] = {'ally_removals': [rc.TRIBE_ARVERNI]}
    execute_card_26(board, True)
    assert count_pieces(board, rc.ARVERNI_REGION, rc.AEDUI, rc.CITADEL) == 1
    assert board['tribes'][rc.TRIBE_ARVERNI]['allied_faction'] == rc.AEDUI


@pytest.mark.parametrize('successor', [False, True])
def test_gobannitio_declines_without_ally_changes_or_leader_for_rally(successor):
    board = state()
    if successor:
        place_piece(board, rc.ARVERNI_REGION, rc.ARVERNI, rc.LEADER,
                    leader_name=rc.SUCCESSOR)
    for tribe in (rc.TRIBE_ARVERNI, rc.TRIBE_CADURCI, rc.TRIBE_VOLCAE):
        _ally(board, rc.ARVERNI_REGION, tribe, rc.ARVERNI)
    assert np_event_available(board, 26, rc.ARVERNI, True) is False


@pytest.mark.parametrize('faction,kind', [(rc.ROMANS, rc.AUXILIA), (rc.AEDUI, rc.WARBAND)])
def test_correus_derives_eight_replacements_allies_first_and_own_mobile_type(faction, kind):
    board = state()
    _ally(board, rc.ATREBATES, rc.TRIBE_REMI, rc.BELGAE)
    _ally(board, rc.ATREBATES, rc.TRIBE_ATREBATES, rc.BELGAE)
    place_piece(board, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 10)
    event(board, 64, faction)
    assert count_pieces(board, rc.ATREBATES, faction, rc.ALLY) == 2
    assert count_pieces(board, rc.ATREBATES, faction, kind) == 6
    assert count_pieces(board, rc.ATREBATES, rc.BELGAE, rc.WARBAND) == 4


def test_correus_shaded_adds_allies_before_one_region_rally():
    board = state()
    _ally(board, rc.ATREBATES, rc.TRIBE_REMI, rc.ROMANS)
    _ally(board, rc.ATREBATES, rc.TRIBE_ATREBATES, rc.AEDUI)
    _ally(board, rc.ATREBATES, rc.TRIBE_BELLOVACI, rc.BELGAE)
    assert np_event_available(board, 64, rc.BELGAE, True)
    event(board, 64, rc.BELGAE, True)
    assert count_pieces(board, rc.ATREBATES, rc.BELGAE, rc.ALLY) == 3
    assert board['tribes'][rc.TRIBE_REMI]['allied_faction'] == rc.BELGAE


def test_correus_np_declines_if_whole_event_does_not_add_allies_citadels():
    board = state()
    for tribe in (rc.TRIBE_REMI, rc.TRIBE_ATREBATES, rc.TRIBE_BELLOVACI):
        _ally(board, rc.ATREBATES, tribe, rc.BELGAE)
    assert np_event_available(board, 64, rc.BELGAE, True) is False


def test_correus_does_not_replace_belgic_citadel_as_ally():
    board = state()
    _ally(board, rc.ATREBATES, rc.TRIBE_REMI, rc.BELGAE, rc.CITADEL)
    from fs_bot.cards.ally_events import derive_correus
    assert derive_correus(board, rc.AEDUI, False) is None
    assert np_event_available(board, 64, rc.AEDUI, False) is False


def test_card21_np_selects_one_of_granted_commands_when_normal_choice_is_rally():
    board = state()
    place_piece(board, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    place_piece(board, rc.PROVINCIA, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    result = event(board, 21, rc.ARVERNI, True)
    command = result['free_actions'][0]['result']
    assert command['executed'], command
    assert command['command'] in ('Raid', 'Battle')
    assert not command.get('errors')


def test_correus_handler_never_replaces_more_than_eight_total_pieces():
    from fs_bot.cards.card_effects import execute_card_64
    board = state()
    board['executing_faction'] = rc.AEDUI
    place_piece(board, rc.ATREBATES, rc.BELGAE, rc.WARBAND, 10)
    board['event_params'] = {'replacements': [{'from_type': rc.WARBAND}] * 9}
    execute_card_64(board)
    assert count_pieces(board, rc.ATREBATES, rc.AEDUI, rc.WARBAND) == 8
    assert count_pieces(board, rc.ATREBATES, rc.BELGAE, rc.WARBAND) == 2


def test_morbihan_requires_veneti_tribe_not_merely_an_ally_in_its_region():
    board = state(rc.SCENARIO_ARIOVISTUS)
    _ally(board, rc.VENETI, rc.TRIBE_NAMNETES, rc.ARVERNI)
    place_piece(board, rc.VENETI, rc.ARVERNI, rc.WARBAND, 4)
    place_piece(board, rc.VENETI, rc.ROMANS, rc.AUXILIA, 2, piece_state=rc.REVEALED)
    assert np_event_available(board, 'A20', rc.GERMANS, True) is False
    assert ex._resolve_a20_arverni_ambush(board)[0]['declined_no_effect']


def test_morbihan_can_ambush_roman_allies_without_mobile_escort():
    board = state(rc.SCENARIO_ARIOVISTUS)
    _ally(board, rc.VENETI, rc.TRIBE_VENETI, rc.ARVERNI)
    _ally(board, rc.VENETI, rc.TRIBE_NAMNETES, rc.ROMANS)
    place_piece(board, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 2)
    result = ex._resolve_a20_arverni_ambush(board)
    assert result[0]['region'] == rc.VENETI
    assert count_pieces(board, rc.VENETI, rc.ROMANS, rc.ALLY) == 0
    assert board['tribes'][rc.TRIBE_NAMNETES]['allied_faction'] is None


@pytest.mark.parametrize('owner', [None, rc.ROMANS, rc.BELGAE, rc.AEDUI])
def test_base_aedui_remi_influence_requires_their_remi_ally(owner):
    board = state()
    if owner:
        _ally(board, rc.ATREBATES, rc.TRIBE_REMI, owner)
    assert should_decline_event(board, 68, rc.AEDUI) == (owner != rc.AEDUI)


@pytest.mark.parametrize('scenario', [*rc.BASE_SCENARIOS, *rc.ARIOVISTUS_SCENARIOS])
def test_city_and_remi_ally_priority_in_both_rule_sets(scenario):
    from fs_bot.bots.bot_common import is_ally_in_city_or_remi
    assert is_ally_in_city_or_remi(rc.TRIBE_REMI, scenario)
    assert is_ally_in_city_or_remi(rc.TRIBE_CARNUTES, scenario)
    assert not is_ally_in_city_or_remi(rc.TRIBE_ATREBATES, scenario)


def test_correus_mandatory_own_removals_preserve_remi_before_ordinary_allies():
    from fs_bot.cards.ally_events import derive_correus
    board = state()
    for tribe in (rc.TRIBE_REMI, rc.TRIBE_ATREBATES, rc.TRIBE_BELLOVACI):
        _ally(board, rc.ATREBATES, tribe, rc.BELGAE)
    params = derive_correus(board, rc.BELGAE, True)
    assert set(params['ally_removals']) == {rc.TRIBE_ATREBATES, rc.TRIBE_BELLOVACI}


@pytest.mark.parametrize('removals', [None, [], [rc.TRIBE_REMI],
    [rc.TRIBE_REMI, rc.TRIBE_REMI], [rc.TRIBE_REMI, rc.TRIBE_CARNUTES],
    [rc.TRIBE_REMI, rc.TRIBE_ATREBATES, rc.TRIBE_BELLOVACI],
    [rc.TRIBE_REMI, {}]])
def test_correus_human_rejects_missing_duplicate_or_invalid_mandatory_removals(removals):
    board = state()
    _ally(board, rc.ATREBATES, rc.TRIBE_REMI, rc.ROMANS)
    _ally(board, rc.ATREBATES, rc.TRIBE_ATREBATES, rc.ROMANS)
    before = deepcopy({key: board[key] for key in ('spaces', 'tribes', 'available')})
    rng = board['rng'].getstate()
    params = {'belgae_ally_placements': []}
    if removals is not None:
        params['ally_removals'] = removals
    result = ex._execute_event(board, rc.AEDUI, {'command': 'Event', 'details': {
        'card_id': 64, 'text_preference': rc.EVENT_SHADED, 'event_params': params}},
        human=True)
    assert result['executed'] is False
    assert 'requires 2 distinct Allied Tribes' in result['reason']
    assert {key: board[key] for key in before} == before
    assert board['rng'].getstate() == rng


@pytest.mark.parametrize('number', [0, 1, 2, 3])
def test_correus_removes_exactly_two_allies_or_as_many_as_exist(number):
    from fs_bot.cards.card_effects import execute_card_64
    board = state()
    tribes = [rc.TRIBE_REMI, rc.TRIBE_ATREBATES, rc.TRIBE_BELLOVACI][:number]
    for tribe in tribes:
        _ally(board, rc.ATREBATES, tribe, rc.ROMANS)
    board['event_params'] = {'ally_removals': tribes[:2], 'belgae_ally_placements': []}
    execute_card_64(board, shaded=True)
    assert count_pieces(board, rc.ATREBATES, rc.ROMANS, rc.ALLY) == max(0, number - 2)
    assert count_pieces(board, rc.ATREBATES, rc.BELGAE, rc.ALLY) == 0
    assert board['event_modifiers']['card_64_belgae_rally'] is True
