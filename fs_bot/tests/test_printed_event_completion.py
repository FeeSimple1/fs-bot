"""Third comparative audit: literal Event effects and attainable mandatory choices."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import (
    count_pieces, count_pieces_by_state, get_available, place_piece, remove_piece,
)
from fs_bot.cards.card_effects import _ally_tribe, _tribe_region, execute_event
from fs_bot.cards.event_piece_plans import derive_params
from fs_bot.commands.seize import seize_in_region
from fs_bot.engine.execute import execute_decision, _derive_card_71
from fs_bot.engine.germans_battle import germans_phase_battle
from fs_bot.engine.victory import calculate_victory_score
from fs_bot.map.map_data import get_playable_regions_for_state
from fs_bot.state.serialize import encode, decode
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state, check_structural_integrity, validate_state


def board(expansion=False, edition='original'):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS if expansion else rc.SCENARIO_GREAT_REVOLT,
                                seed=317)
    state['card_edition'] = edition
    state['non_player_factions'] = set()
    return state


def clean(state):
    assert validate_state(state) == []
    assert check_structural_integrity(state) == []


def play(state, card, params=None, *, shaded=False, actor=rc.BELGAE, reject=False):
    state['current_card'] = card
    clean(state)
    before = encode(state)
    result = execute_decision(state, actor, {'action': 'event', 'player_action': {
        'command': rc.FIRST_DID_EVENT, 'sa': 'No SA', 'regions': [], 'sa_regions': [],
        'details': {'card_id': card,
                    'text_preference': rc.EVENT_SHADED if shaded else rc.EVENT_UNSHADED,
                    'event_params': params or {}}}})
    if reject:
        assert not result['executed'] and result['rejected'], result
        assert encode(state) == before
    else:
        assert result['executed'] and not result.get('errors'), result
        clean(state)
    return result


def exhaust_allies(state, faction, *, exclude=()):
    for tribe in list(state['tribes']):
        if get_available(state, faction, rc.ALLY) == 0:
            break
        region = _tribe_region(state, tribe)
        if (region not in exclude and region in get_playable_regions_for_state(state, faction)
                and rc.TRIBE_FACTION_RESTRICTION.get(tribe, faction) == faction):
            _ally_tribe(state, tribe, faction)
    assert get_available(state, faction, rc.ALLY) == 0


@pytest.mark.parametrize('edition', ['original', 'second-edition'])
@pytest.mark.parametrize('visibility', [rc.HIDDEN, rc.REVEALED, rc.SCOUTED])
def test_consuetudine_ambushes_more_hidden_enemies_in_every_own_visibility(edition, visibility):
    state = board(edition=edition)
    place_piece(state, rc.PICTONES, rc.GERMANS, rc.WARBAND, 4, piece_state=visibility)
    place_piece(state, rc.PICTONES, rc.AEDUI, rc.WARBAND, 5)
    play(state, 53)
    assert count_pieces(state, rc.PICTONES, rc.AEDUI, rc.WARBAND) == 3
    assert count_pieces_by_state(state, rc.PICTONES, rc.GERMANS, rc.WARBAND, rc.REVEALED) == 4
    assert count_pieces_by_state(state, rc.PICTONES, rc.GERMANS, rc.WARBAND, rc.SCOUTED) == 0
    assert count_pieces(state, rc.PICTONES, rc.GERMANS, rc.WARBAND) == 4  # no March


@pytest.mark.parametrize('edition', ['original', 'second-edition'])
def test_consuetudine_scouted_hide_is_one_attempt_and_does_not_leak(edition):
    state = board(edition=edition)
    place_piece(state, rc.PICTONES, rc.GERMANS, rc.WARBAND, piece_state=rc.SCOUTED)
    place_piece(state, rc.PICTONES, rc.AEDUI, rc.WARBAND, 2)
    play(state, 53)
    assert count_pieces_by_state(state, rc.PICTONES, rc.GERMANS, rc.WARBAND, rc.REVEALED) == 1
    assert count_pieces_by_state(state, rc.PICTONES, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 0
    assert count_pieces_by_state(state, rc.PICTONES, rc.GERMANS, rc.WARBAND, rc.SCOUTED) == 0
    assert germans_phase_battle(state)['regions'] == []


def test_ordinary_germans_phase_still_requires_hidden_superiority():
    state = board()
    place_piece(state, rc.PICTONES, rc.GERMANS, rc.WARBAND, 4)
    place_piece(state, rc.PICTONES, rc.AEDUI, rc.WARBAND, 5)
    before = encode(state)
    assert germans_phase_battle(state)['regions'] == []
    assert encode(state) == before


@pytest.mark.parametrize('faction', [rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE, rc.GERMANS])
@pytest.mark.parametrize('scarce', [False, True])
def test_colony_creates_its_tribe_independently_of_available_ally(faction, scarce):
    state = board(expansion=faction == rc.GERMANS)
    if scarce:
        exhaust_allies(state, faction)
    before = calculate_victory_score(state, rc.ROMANS)
    tribe_count = len(state['tribes'])
    play(state, 71, {'region': rc.CARNUTES}, actor=faction)
    assert state['markers'][rc.CARNUTES][rc.MARKER_COLONY]
    assert len(state['tribes']) == tribe_count + 1
    info = state['tribes']['Colony_' + rc.CARNUTES]
    assert info == {'status': None, 'allied_faction': None if scarce else faction,
                    'region': rc.CARNUTES}
    if scarce:
        assert calculate_victory_score(state, rc.ROMANS) == before + 1
        assert _derive_card_71(state, faction, False) is not None


def test_colony_name_collision_rejects_even_without_available_allies():
    state = board()
    exhaust_allies(state, rc.ROMANS)
    play(state, 71, {'region': rc.CARNUTES, 'colony_tribe_name': rc.TRIBE_CARNUTES},
         actor=rc.ROMANS, reject=True)


def migration_plan():
    return {'faction': rc.ARVERNI, 'target_region': rc.BRITANNIA, 'moves': [{
        'from_region': rc.ARVERNI_REGION, 'to_region': rc.BRITANNIA,
        'piece_type': rc.WARBAND, 'count': 1}]}


@pytest.mark.parametrize('edition', ['original', 'second-edition'])
@pytest.mark.parametrize('omitted', [None, ''])
def test_migration_cannot_commit_movement_without_possible_ally(edition, omitted):
    state = board(edition=edition)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND)
    params = dict(migration_plan(), ally_tribe=omitted)
    play(state, 66, params, shaded=True, reject=True)
    play(state, 66, dict(params, ally_tribe=rc.TRIBE_CATUVELLAUNI), shaded=True)
    assert state['tribes'][rc.TRIBE_CATUVELLAUNI]['allied_faction'] == rc.ARVERNI
    assert count_pieces(state, rc.BRITANNIA, rc.ARVERNI, rc.WARBAND) == 1


@pytest.mark.parametrize('reason', ['no_disc', 'dispersed'])
@pytest.mark.parametrize('explicit_target', [False, True])
def test_migration_keeps_legal_partial_execution(reason, explicit_target):
    state = board()
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND)
    if reason == 'no_disc':
        exhaust_allies(state, rc.ARVERNI, exclude=(rc.BRITANNIA,))
    else:
        place_piece(state, rc.BRITANNIA, rc.ROMANS, rc.AUXILIA)
        seize_in_region(state, rc.BRITANNIA, [rc.TRIBE_CATUVELLAUNI], no_rally=True)
        remove_piece(state, rc.BRITANNIA, rc.ROMANS, rc.AUXILIA)
    params = migration_plan()
    if explicit_target:
        params['ally_tribe'] = rc.TRIBE_CATUVELLAUNI
    play(state, 66, params, shaded=True)
    assert count_pieces(state, rc.BRITANNIA, rc.ARVERNI, rc.WARBAND) == 1
    assert state['tribes'][rc.TRIBE_CATUVELLAUNI]['allied_faction'] is None


def harudes_plan(warbands=4, settlement=True):
    entries = ([{'region': rc.TREVERI, 'piece_type': rc.WARBAND, 'count': warbands}]
               if warbands else [])
    if settlement:
        entries.append({'region': rc.TREVERI, 'piece_type': rc.SETTLEMENT})
    return {'placements': entries}


@pytest.mark.parametrize('edition', ['original', 'second-edition'])
@pytest.mark.parametrize('plan', [harudes_plan(0, False), harudes_plan(4, False),
                                 harudes_plan(0, True), harudes_plan(3, True)])
def test_harudes_cannot_omit_possible_mandatory_placements(edition, plan):
    state = board(expansion=True, edition=edition)
    play(state, 'A29', deepcopy(plan), shaded=True, reject=True)


@pytest.mark.parametrize('warbands', [0, 2, 4])
@pytest.mark.parametrize('settlement', [False, True])
def test_harudes_requires_only_attainable_quantities(warbands, settlement):
    state = board(expansion=True)
    remaining = get_available(state, rc.GERMANS, rc.WARBAND) - warbands
    if remaining:
        place_piece(state, rc.UBII, rc.GERMANS, rc.WARBAND, remaining)
    if not settlement:
        for region in get_playable_regions_for_state(state, rc.GERMANS):
            if region != rc.TREVERI and get_available(state, rc.GERMANS, rc.SETTLEMENT):
                place_piece(state, region, rc.GERMANS, rc.SETTLEMENT)
        assert get_available(state, rc.GERMANS, rc.SETTLEMENT) == 0
    play(state, 'A29', harudes_plan(warbands, settlement), shaded=True)
    assert count_pieces(state, rc.TREVERI, rc.GERMANS, rc.WARBAND) == warbands
    assert count_pieces(state, rc.TREVERI, rc.GERMANS, rc.SETTLEMENT) == int(settlement)


@pytest.mark.parametrize('settlement_first', [False, True])
def test_harudes_keeps_authored_order_and_only_raids_with_new_pieces(settlement_first):
    state = board(expansion=True)
    place_piece(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, 3)
    plan = harudes_plan()
    if settlement_first:
        plan['placements'].reverse()
    play(state, 'A29', plan, shaded=True, actor=rc.GERMANS)
    assert count_pieces_by_state(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 5
    assert count_pieces_by_state(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, rc.REVEALED) == 2
    assert state['resources'][rc.GERMANS] == 2


def test_harudes_np_default_completes_all_pieces_in_its_selected_region():
    state = board(expansion=True)
    state['non_player_factions'] = {rc.GERMANS}
    params = derive_params(state, rc.GERMANS, 'A29')
    assert sum(e.get('count', 1) for e in params['placements']) == 5
    assert len({e['region'] for e in params['placements']}) == 1
    assert params['placements'][0]['piece_type'] == rc.SETTLEMENT
    play(state, 'A29', params, shaded=True, actor=rc.GERMANS)


def test_harudes_terminal_offers_complete_concrete_choices_without_mutating_state(monkeypatch):
    from fs_bot.cli import event_piece_plans, human_plan
    state = board(expansion=True)
    before = encode(state)
    selections = []
    def choose(stdin, stdout, prompt, choices):
        entries = [entry for _, entry in choices]
        assert None not in entries
        wanted = ({'region': rc.TREVERI, 'piece_type': rc.WARBAND, 'count': 4}
                  if not selections else {'region': rc.TREVERI, 'piece_type': rc.SETTLEMENT})
        assert wanted in entries
        selections.append(wanted)
        return wanted
    monkeypatch.setattr(event_piece_plans, 'prompt_choice', choose)
    params = human_plan._collect_event_params(state, rc.GERMANS, 'A29', True, StringIO(), StringIO())
    assert encode(state) == before
    play(state, 'A29', params, shaded=True, actor=rc.GERMANS)


def test_migration_terminal_chooses_required_ally_after_its_moves(monkeypatch):
    from fs_bot.cli import human_plan
    state = board()
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND)
    before = encode(state)
    given = migration_plan()
    def parameter(board, key, spec, stdin, stdout):
        assert key != 'ally_tribe'
        return given.get(key)
    def choose(stdin, stdout, prompt, choices):
        assert 'required Ally' in prompt
        assert choices == [(rc.TRIBE_CATUVELLAUNI, rc.TRIBE_CATUVELLAUNI)]
        return rc.TRIBE_CATUVELLAUNI
    monkeypatch.setattr(human_plan, '_prompt_event_param', parameter)
    monkeypatch.setattr(human_plan, 'prompt_choice', choose)
    params = human_plan._collect_event_params(state, rc.BELGAE, 66, True, StringIO(), StringIO())
    assert encode(state) == before
    play(state, 66, params, shaded=True)


@pytest.mark.parametrize('status', [None, rc.DISPERSED, rc.DISPERSED_GATHERING])
@pytest.mark.parametrize('available', [False, True])
def test_nasua_replaces_the_actual_treveri_marker_even_without_counterpart(status, available):
    state = board(expansion=True)
    if status is not None:
        place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA)
        seize_in_region(state, rc.TREVERI, [rc.TRIBE_TREVERI], no_rally=True)
        if status == rc.DISPERSED_GATHERING:
            from fs_bot.engine.winter import spring_phase
            spring_phase(state)
    if not available:
        exhaust_allies(state, rc.BELGAE, exclude=(rc.TREVERI,))
    state['markers'].setdefault(rc.TREVERI, {})[rc.MARKER_ABATIS] = rc.BELGAE
    play(state, 'A35', {'ally_faction': rc.BELGAE, 'piece_faction': rc.BELGAE,
                        'piece_type': rc.WARBAND, 'count': 0})
    assert state['tribes'][rc.TRIBE_TREVERI]['status'] is None
    assert state['tribes'][rc.TRIBE_TREVERI]['allied_faction'] == (rc.BELGAE if available else None)
    assert rc.MARKER_DISPERSED not in state['markers'].get(rc.TRIBE_TREVERI, {})
    assert rc.MARKER_DISPERSED_GATHERING not in state['markers'].get(rc.TRIBE_TREVERI, {})
    assert state['markers'][rc.TREVERI][rc.MARKER_ABATIS] == rc.BELGAE


def test_completed_event_state_survives_plain_json_roundtrip():
    state = board(expansion=True)
    play(state, 'A29', harudes_plan(), shaded=True, actor=rc.GERMANS)
    restored = decode(encode(state))
    assert encode(restored) == encode(state)
    clean(restored)


def test_nasua_replaces_a_legacy_set_form_dispersed_marker():
    state = board(expansion=True)
    place_piece(state, rc.TREVERI, rc.ROMANS, rc.AUXILIA)
    seize_in_region(state, rc.TREVERI, [rc.TRIBE_TREVERI], no_rally=True)
    state['markers'][rc.TRIBE_TREVERI] = {rc.MARKER_DISPERSED}
    play(state, 'A35', {'ally_faction': rc.BELGAE, 'piece_faction': rc.BELGAE, 'count': 0})
    assert state['tribes'][rc.TRIBE_TREVERI]['allied_faction'] == rc.BELGAE
    assert rc.MARKER_DISPERSED not in state['markers'][rc.TRIBE_TREVERI]


def test_harudes_legacy_warband_entry_keeps_its_default_piece_type():
    state = board(expansion=True)
    params = harudes_plan()
    params['placements'][0].pop('piece_type')
    play(state, 'A29', params, shaded=True)
    assert count_pieces(state, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 4


def test_harudes_does_not_refill_placed_pieces_removed_at_a_later_window():
    state = board(expansion=True)
    params = harudes_plan()
    params['placements'][1]['timing_actions'] = [{
        'kind': 'voluntary_removal', 'response': {'operations': [{
            'action': 'remove', 'region': rc.TREVERI, 'piece_type': rc.WARBAND,
            'piece_state': rc.HIDDEN, 'count': 2, 'cohort': 'card_A29_raid.' + rc.TREVERI}]}}]
    play(state, 'A29', params, shaded=True, actor=rc.GERMANS)
    assert count_pieces(state, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 2
    assert count_pieces_by_state(state, rc.TREVERI, rc.GERMANS, rc.WARBAND, rc.REVEALED) == 2
    assert state['resources'][rc.GERMANS] == 2


def test_harudes_rechecks_the_required_settlement_after_authored_reclamation():
    state = board(expansion=True)
    occupied = []
    for region in get_playable_regions_for_state(state, rc.GERMANS):
        if region != rc.TREVERI and get_available(state, rc.GERMANS, rc.SETTLEMENT):
            place_piece(state, region, rc.GERMANS, rc.SETTLEMENT)
            occupied.append(region)
    assert get_available(state, rc.GERMANS, rc.SETTLEMENT) == 0
    actions = [{'kind': 'voluntary_removal', 'response': {'operations': [{
        'action': 'remove', 'region': occupied[0], 'piece_type': rc.SETTLEMENT, 'count': 1}]}}]
    omitted = harudes_plan(settlement=False)
    omitted['stage_timing_actions'] = {'A29.placements:1': actions}
    play(state, 'A29', omitted, shaded=True, actor=rc.GERMANS, reject=True)
    complete = harudes_plan()
    complete['placements'][1]['timing_actions'] = actions
    play(state, 'A29', complete, shaded=True, actor=rc.GERMANS)
    assert count_pieces(state, rc.TREVERI, rc.GERMANS, rc.SETTLEMENT) == 1


def test_migration_cannot_use_a_blocked_tribe_to_skip_a_legal_alternative():
    state = board()
    place_piece(state, rc.PICTONES, rc.ROMANS, rc.AUXILIA)
    seize_in_region(state, rc.PICTONES, [rc.TRIBE_PICTONES], no_rally=True)
    remove_piece(state, rc.PICTONES, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND)
    params = {'faction': rc.ARVERNI, 'target_region': rc.PICTONES,
              'ally_tribe': rc.TRIBE_PICTONES, 'moves': [{
                  'from_region': rc.ARVERNI_REGION, 'to_region': rc.PICTONES,
                  'piece_type': rc.WARBAND, 'count': 1}]}
    play(state, 66, params, shaded=True, reject=True)
    play(state, 66, dict(params, ally_tribe=rc.TRIBE_SANTONES), shaded=True)
    assert state['tribes'][rc.TRIBE_PICTONES]['status'] == rc.DISPERSED
    assert state['tribes'][rc.TRIBE_SANTONES]['allied_faction'] == rc.ARVERNI


def test_migration_terminal_reclaims_before_selecting_the_mandatory_ally(monkeypatch):
    from fs_bot.cli import action_windows, human_plan
    from fs_bot.cards.card_effects import _unally_tribe
    state = board()
    place_piece(state, rc.ARVERNI_REGION, rc.ARVERNI, rc.WARBAND)
    exhaust_allies(state, rc.ARVERNI, exclude=(rc.BRITANNIA,))
    tribe = next(t for t, info in state['tribes'].items()
                 if info.get('allied_faction') == rc.ARVERNI)
    region = _tribe_region(state, tribe)
    before = encode(state)
    given = migration_plan()
    action = {'kind': 'voluntary_removal', 'response': {'operations': [{
        'action': 'remove', 'region': region, 'piece_type': rc.ALLY,
        'tribe': tribe, 'count': 1}]}}
    def parameter(board, key, spec, stdin, stdout):
        assert key != 'ally_tribe'
        return given.get(key)
    def prepare(current, actor, stdin, stdout, **context):
        assert actor == rc.ARVERNI and context['step'] == '66.ally'
        assert get_available(current, rc.ARVERNI, rc.ALLY) == 0
        assert _unally_tribe(current, tribe) == rc.ARVERNI
        return current, [action]
    def choose(stdin, stdout, prompt, choices):
        assert choices == [(rc.TRIBE_CATUVELLAUNI, rc.TRIBE_CATUVELLAUNI)]
        return rc.TRIBE_CATUVELLAUNI
    monkeypatch.setattr(human_plan, '_prompt_event_param', parameter)
    monkeypatch.setattr(human_plan, 'prompt_choice', choose)
    monkeypatch.setattr(action_windows, 'prepare', prepare)
    params = human_plan._collect_event_params(state, rc.ARVERNI, 66, True, StringIO(), StringIO())
    assert encode(state) == before
    assert params['stage_timing_actions']['66.ally'] == [action]
    play(state, 66, params, shaded=True, actor=rc.ARVERNI)
    assert state['tribes'][rc.TRIBE_CATUVELLAUNI]['allied_faction'] == rc.ARVERNI
