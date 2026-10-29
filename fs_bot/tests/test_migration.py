"""Card 66's chooser, two-region limits and Roman NP instructions."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, count_pieces_by_state
from fs_bot.bots.roman_bot import node_r4
from fs_bot.cards.migration import can_roman_migrate, _request
from fs_bot.cli.free_actions import collect_free_action
from fs_bot.commands.rally import _find_subdued_tribe_for_ally
from fs_bot.engine.execute import execute_decision
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import encode


def state():
    st = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=5)
    st['current_card'] = st['current_card_id'] = 66
    st['non_player_factions'] = set()
    return st


def action(command, plan):
    return {'command': command, 'sa': 'No SA', 'sa_regions': [],
            'details': {f'{command.lower()}_plan': plan}}


def march(routes, groups=None):
    plan = {'origins': list(routes), 'routes': routes,
            'destinations': [path[-1] for path in routes.values()]}
    if groups is not None:
        plan['groups'] = groups
    return action(rc.CMD_MARCH, plan)


def event(st, chooser=rc.ROMANS):
    return execute_decision(st, chooser, {'player_action': {
        'command': 'Event', 'sa': 'No SA', 'details': {
            'card_id': 66, 'text_preference': rc.EVENT_UNSHADED}}})


def choose(st, responses, chooser):
    seen = []
    def agent(board, faction, request):
        if request['kind'] != 'free_action':
            return None
        assert faction == chooser
        assert request['acting_faction'] == rc.GERMANS
        assert request['max_regions'] == 2 and not request['with_sa']
        command = request['allowed_commands'][0]
        seen.append((command, count_pieces(board, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND)))
        return deepcopy(responses[command])
    st['decision_agent'] = agent
    return seen


@pytest.mark.parametrize('chooser', [rc.ROMANS, rc.AEDUI, rc.BELGAE, rc.ARVERNI])
def test_human_chooser_rallies_then_marches_real_germans_from_two_origins(chooser):
    st = state()
    for r in (rc.SUGAMBRI, rc.UBII):
        place_piece(st, r, rc.GERMANS, rc.WARBAND, 2, piece_state=rc.REVEALED)
    place_piece(st, rc.TREVERI, chooser, rc.AUXILIA if chooser == rc.ROMANS else rc.WARBAND, 2)
    seen = choose(st, {
        rc.CMD_RALLY: action(rc.CMD_RALLY, {'warbands': [rc.SUGAMBRI, rc.UBII]}),
        rc.CMD_MARCH: march({rc.SUGAMBRI: [rc.NERVII], rc.UBII: [rc.SEQUANI]})}, chooser)
    result = event(st, chooser)
    assert result['executed']
    assert seen == [(rc.CMD_RALLY, 2), (rc.CMD_MARCH, 3)]
    report = result['free_actions'][0]
    assert report['chooser'] == chooser and report['faction'] == rc.GERMANS
    assert len(report['rally']['placements']) == len(report['march']['marches']) == 2
    for r in (rc.NERVII, rc.SEQUANI):
        assert count_pieces_by_state(st, r, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 3
    assert count_pieces(st, rc.TREVERI, chooser) == 2
    assert rc.GERMANS not in st['resources']  # base Germans have no Resource track
    assert validate_state(st) == []


def test_german_rally_can_place_ally_then_warbands_in_same_selected_region():
    st = state()
    place_piece(st, rc.NERVII, rc.GERMANS, rc.WARBAND, 3)
    tribe = _find_subdued_tribe_for_ally(st, rc.NERVII, rc.GERMANS)[0]
    choose(st, {rc.CMD_RALLY: action(rc.CMD_RALLY, {
        'allies': [{'region': rc.NERVII, 'tribe': tribe}], 'warbands': [rc.NERVII]}),
        rc.CMD_MARCH: {'decline': True}}, rc.BELGAE)
    assert event(st, rc.BELGAE)['executed']
    assert st['tribes'][tribe]['allied_faction'] == rc.GERMANS
    assert count_pieces(st, rc.NERVII, rc.GERMANS, rc.WARBAND) == 4


@pytest.mark.parametrize('invalid_stage', [rc.CMD_RALLY, rc.CMD_MARCH])
def test_three_regions_rejected_atomically_even_after_valid_rally(invalid_stage):
    st = state()
    for r in (rc.SUGAMBRI, rc.UBII, rc.TREVERI):
        place_piece(st, r, rc.GERMANS, rc.WARBAND, 2)
    responses = {rc.CMD_RALLY: action(rc.CMD_RALLY, {'warbands': [rc.SUGAMBRI]}),
                 rc.CMD_MARCH: {'decline': True}}
    if invalid_stage == rc.CMD_RALLY:
        responses[invalid_stage] = action(rc.CMD_RALLY, {'warbands': [rc.SUGAMBRI, rc.UBII, rc.TREVERI]})
    else:
        responses[invalid_stage] = march({rc.SUGAMBRI: [rc.NERVII],
            rc.UBII: [rc.SEQUANI], rc.TREVERI: [rc.MANDUBII]})
    choose(st, responses, rc.ROMANS)
    before = encode({k:v for k,v in st.items() if k != 'decision_agent'})
    assert not event(st)['executed']
    assert encode({k:v for k,v in st.items() if k != 'decision_agent'}) == before


def test_german_march_rejects_two_moving_groups_from_same_origin():
    st = state()
    place_piece(st, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, 4)
    plan = march({rc.SUGAMBRI: [rc.NERVII]}, {rc.SUGAMBRI: {rc.WARBAND: 2}})
    plan['details']['march_plan']['extra_groups'] = [
        {'origin': rc.SUGAMBRI, 'route': [rc.MORINI], 'group': {rc.WARBAND: 2}}]
    choose(st, {rc.CMD_RALLY: {'decline': True}, rc.CMD_MARCH: plan}, rc.AEDUI)
    before = encode({k:v for k,v in st.items() if k != 'decision_agent'})
    assert not event(st, rc.AEDUI)['executed']
    assert encode({k:v for k,v in st.items() if k != 'decision_agent'}) == before


def test_roman_np_avoids_german_allies_and_moves_only_away_from_romans():
    st = state()
    st['non_player_factions'] = {rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE}
    roman_origins = (rc.SUGAMBRI, rc.UBII, rc.TREVERI)
    for r in roman_origins:
        place_piece(st, r, rc.GERMANS, rc.WARBAND, 3)
        place_piece(st, r, rc.ROMANS, rc.AUXILIA)
    place_piece(st, rc.CARNUTES, rc.GERMANS, rc.WARBAND, 2)
    result = event(st)
    assert result['executed']
    report = result['free_actions'][0]
    assert len(report['rally']['placements']) <= 2
    assert len(report['march']['marches']) == 2
    for m in report['march']['marches']:
        assert m['origin'] in roman_origins
        assert not count_pieces(st, m['final_region'], rc.ROMANS)
    assert all(count_pieces(st, r, rc.GERMANS, rc.ALLY) == 0 for r in st['spaces'])
    assert count_pieces(st, rc.CARNUTES, rc.GERMANS, rc.WARBAND) >= 2
    assert validate_state(st) == []


def test_roman_entry_guard_includes_rally_created_group_without_mutating_rng():
    st = state()
    st['non_player_factions'] = {rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE}
    place_piece(st, rc.SUGAMBRI, rc.ROMANS, rc.AUXILIA)
    before = encode(st)
    assert can_roman_migrate(st) and node_r4(st) == 'No'
    assert encode(st) == before
    result = event(st)
    assert result['executed']
    assert any(m['origin'] == rc.SUGAMBRI for m in result['free_actions'][0]['march']['marches'])


def test_roman_entry_guard_declines_without_from_roman_destination():
    st = state()
    st['non_player_factions'] = {rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE}
    place_piece(st, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, 3)
    assert not can_roman_migrate(st)
    assert node_r4(st) == 'Yes'


def test_arrivals_cannot_march_again_from_second_origin():
    st = state()
    place_piece(st, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, 3)
    place_piece(st, rc.TREVERI, rc.GERMANS, rc.WARBAND, 2)
    choose(st, {rc.CMD_RALLY: {'decline': True}, rc.CMD_MARCH: march({
        rc.SUGAMBRI: [rc.TREVERI], rc.TREVERI: [rc.MANDUBII]})}, rc.AEDUI)
    assert event(st, rc.AEDUI)['executed']
    assert count_pieces(st, rc.TREVERI, rc.GERMANS, rc.WARBAND) == 3
    assert count_pieces(st, rc.MANDUBII, rc.GERMANS, rc.WARBAND) == 2


def test_terminal_rally_uses_german_home_minimum_at_zero_resources():
    st = state()
    out = StringIO()
    plan = collect_free_action(st, rc.ROMANS, _request(rc.CMD_RALLY),
        StringIO('Plan the action\nRally\n' + rc.SUGAMBRI + '\n(done)\nWarbands\n1\n'), out)
    assert plan['details']['rally_plan']['steps'] == [
        {'region': rc.SUGAMBRI, 'action': 'place_warbands', 'count': 1}]
    assert 'using Germans pieces' in out.getvalue()


def test_terminal_base_germans_may_place_warbands_after_new_ally():
    st = state()
    place_piece(st, rc.NERVII, rc.GERMANS, rc.WARBAND, 3)
    tribe = _find_subdued_tribe_for_ally(st, rc.NERVII, rc.GERMANS)[0]
    out = StringIO()
    plan = collect_free_action(st, rc.ROMANS, _request(rc.CMD_RALLY),
        StringIO('Plan the action\nRally\n' + rc.NERVII
                 + '\n(done)\nan Ally at a Subdued Tribe\n' + tribe + '\nWarbands\n1\n'), out)
    assert plan['details']['rally_plan']['steps'] == [
        {'region': rc.NERVII, 'action': 'place_ally', 'tribe': tribe},
        {'region': rc.NERVII, 'action': 'place_warbands', 'count': 1}]
    assert 'Finish this Region' in out.getvalue()


def test_roman_rally_chooses_required_march_origin_before_other_rally_options():
    st = state()
    st['non_player_factions'] = {rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE}
    place_piece(st, rc.SUGAMBRI, rc.ROMANS, rc.AUXILIA)
    for r in (rc.NERVII, rc.TREVERI):
        tribe = _find_subdued_tribe_for_ally(st, r, rc.GERMANS)[0]
        place_piece(st, r, rc.GERMANS, rc.ALLY)
        st['tribes'][tribe]['allied_faction'] = rc.GERMANS
    assert can_roman_migrate(st)
    result = event(st)
    assert result['executed']
    report = result['free_actions'][0]
    assert any(p['region'] == rc.SUGAMBRI for p in report['rally']['placements'])
    assert [m['origin'] for m in report['march']['marches']] == [rc.SUGAMBRI]
    assert validate_state(st) == []


def test_roman_rally_places_most_warbands_before_random_ties():
    from fs_bot.map.map_data import get_tribes_in_region
    st = state()
    st['non_player_factions'] = {rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE}
    for region in (rc.ATREBATES, rc.NERVII):
        for tribe in get_tribes_in_region(region, st['scenario']):
            place_piece(st, region, rc.GERMANS, rc.ALLY)
            st['tribes'][tribe]['allied_faction'] = rc.GERMANS
    place_piece(st, rc.ATREBATES, rc.GERMANS, rc.WARBAND)
    place_piece(st, rc.ATREBATES, rc.ROMANS, rc.AUXILIA)
    result = event(st)
    report = result['free_actions'][0]
    assert [p['region'] for p in report['rally']['placements']] == [rc.ATREBATES, rc.NERVII]
    assert sum(count_pieces(st, r, rc.GERMANS, rc.WARBAND) for r in st['spaces']) == 6
    assert validate_state(st) == []


def test_terminal_ariovistus_german_rally_keeps_one_option_per_region():
    st = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=5)
    place_piece(st, rc.NERVII, rc.GERMANS, rc.WARBAND, 3)
    tribe = _find_subdued_tribe_for_ally(st, rc.NERVII, rc.GERMANS)[0]
    out = StringIO()
    plan = collect_free_action(st, rc.ROMANS, _request(rc.CMD_RALLY),
        StringIO('Plan the action\nRally\n' + rc.NERVII
                 + '\n(done)\nan Ally at a Subdued Tribe\n' + tribe + '\n'), out)
    assert plan['details']['rally_plan']['steps'] == [
        {'region': rc.NERVII, 'action': 'place_ally', 'tribe': tribe}]
    assert 'Finish this Region' not in out.getvalue()
