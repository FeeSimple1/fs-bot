"""Human March paths follow 3.2.2/3.3.2 and A3.2.2, without future dice."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.pieces import count_pieces, get_leader_in_region, place_piece
from fs_bot.cli.human_plan import collect_player_action, _collect_command, _march_routes
from fs_bot.commands.march import march_group
from fs_bot.engine.execute import execute_decision
from fs_bot.engine.game_engine import ACTION_COMMAND
from fs_bot.state.state_schema import build_initial_state


def board(faction=rc.ROMANS, leader=None, scenario=rc.SCENARIO_GREAT_REVOLT):
    state = build_initial_state(scenario, seed=7)
    piece = rc.LEGION if faction == rc.ROMANS else rc.WARBAND
    place_piece(state, rc.PROVINCIA, faction, piece, 2,
                from_legions_track=faction == rc.ROMANS)
    if leader:
        place_piece(state, rc.PROVINCIA, faction, rc.LEADER, leader_name=leader)
    state['resources'][faction] = 20
    return state


@pytest.mark.parametrize('faction,leader,path', [
    (rc.ROMANS, None, [rc.ARVERNI_REGION, rc.BITURIGES]),
    (rc.ROMANS, rc.CAESAR, [rc.ARVERNI_REGION, rc.BITURIGES, rc.CARNUTES]),
    (rc.ARVERNI, rc.VERCINGETORIX, [rc.ARVERNI_REGION, rc.BITURIGES]),
])
def test_normal_command_menu_executes_full_selected_route(faction, leader, path):
    state = board(faction, leader)
    before = deepcopy(state['spaces'])
    rng = state['rng'].getstate()
    lines = ['March', rc.PROVINCIA, ' → '.join(path), 'all 2']
    if leader:
        lines.append('y')
    lines.append('n')  # Decline a Resource gift.
    action = collect_player_action(state, faction, ACTION_COMMAND,
        StringIO('\n'.join(lines) + '\n'), StringIO())
    assert state['spaces'] == before and state['rng'].getstate() == rng
    assert action['details']['routes'] == {rc.PROVINCIA: path}
    result = execute_decision(state, faction, {'player_action': action})
    assert result['executed'], result
    piece = rc.LEGION if faction == rc.ROMANS else rc.WARBAND
    assert count_pieces(state, path[-1], faction, piece) == 2
    assert count_pieces(state, rc.PROVINCIA, faction) == 0
    if leader:
        assert get_leader_in_region(state, path[-1], faction) == leader
    assert state['resources'][faction] == 20 - (2 if faction == rc.ROMANS else 1)


@pytest.mark.parametrize('faction,maximum', [(rc.ROMANS, 2), (rc.ARVERNI, 1)])
def test_successor_menu_does_not_offer_named_leader_bonus(faction, maximum):
    state = board(faction, rc.SUCCESSOR)
    routes = _march_routes(state, rc.PROVINCIA, faction)
    assert max(map(len, routes)) == maximum


def test_leaving_caesar_behind_repicks_route_for_selected_legions():
    state = board(leader=rc.CAESAR)
    output = StringIO()
    action = collect_player_action(state, rc.ROMANS, ACTION_COMMAND, StringIO('\n'.join([
        'March', rc.PROVINCIA, ' → '.join([rc.ARVERNI_REGION, rc.BITURIGES, rc.CARNUTES]),
        'all 2', 'n', ' → '.join([rc.ARVERNI_REGION, rc.BITURIGES]),
        'n', 'n']) + '\n'), output)
    assert 'cannot complete that route' in output.getvalue()
    assert action['details']['routes'][rc.PROVINCIA] == [rc.ARVERNI_REGION, rc.BITURIGES]
    result = execute_decision(state, rc.ROMANS, {'player_action': action})
    assert result['executed'], result
    assert get_leader_in_region(state, rc.PROVINCIA, rc.ROMANS) == rc.CAESAR
    assert count_pieces(state, rc.BITURIGES, rc.ROMANS, rc.LEGION) == 2


def test_required_distant_destination_does_not_offer_leaderless_extra_group():
    state = board(leader=rc.CAESAR)
    output = StringIO()
    action = _collect_command(state, rc.ROMANS, ACTION_COMMAND,
        StringIO('\n'.join(['March', rc.PROVINCIA,
            ' → '.join([rc.ARVERNI_REGION, rc.BITURIGES, rc.CARNUTES]),
            '2', 'y']) + '\n'), output,
        required_destinations={rc.CARNUTES})
    assert 'remaining pieces cannot reach' in output.getvalue()
    assert not action['details'].get('extra_groups')
    assert action['details']['groups'][rc.PROVINCIA][rc.LEGION] == 1


@pytest.mark.parametrize('scenario,origin,stopped,after', [
    (rc.SCENARIO_ARIOVISTUS, rc.PROVINCIA, rc.CISALPINA, rc.SEQUANI),
    (rc.SCENARIO_ARIOVISTUS, rc.CISALPINA, rc.PROVINCIA, rc.ARVERNI_REGION),
    (rc.SCENARIO_GREAT_REVOLT, rc.MORINI, rc.BRITANNIA, rc.VENETI),
    (rc.SCENARIO_GREAT_REVOLT, rc.BRITANNIA, rc.MORINI, rc.NERVII),
    (rc.SCENARIO_GREAT_REVOLT, rc.MORINI, rc.SUGAMBRI, rc.UBII),
])
def test_crossing_stop_excludes_continuation_even_with_caesar(scenario, origin, stopped, after):
    state = build_initial_state(scenario, seed=7)
    place_piece(state, origin, rc.ROMANS, rc.LEGION, from_legions_track=True)
    place_piece(state, origin, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    routes = _march_routes(state, origin, rc.ROMANS)
    assert [stopped] in routes
    assert [stopped, after] not in routes


def test_devastation_stops_on_entry_but_does_not_block_departure():
    state = board(leader=rc.CAESAR)
    state['markers'].setdefault(rc.ARVERNI_REGION, {})[rc.MARKER_DEVASTATED] = True
    routes = _march_routes(state, rc.PROVINCIA, rc.ROMANS)
    assert [rc.ARVERNI_REGION] in routes
    assert [rc.ARVERNI_REGION, rc.BITURIGES] not in routes
    state['markers'][rc.ARVERNI_REGION].pop(rc.MARKER_DEVASTATED)
    state['markers'].setdefault(rc.PROVINCIA, {})[rc.MARKER_DEVASTATED] = True
    assert [rc.ARVERNI_REGION, rc.BITURIGES] in _march_routes(state, rc.PROVINCIA, rc.ROMANS)


def test_route_menu_does_not_predict_harassment_or_consult_live_players():
    state = board(leader=rc.CAESAR)
    place_piece(state, rc.ARVERNI_REGION, rc.GERMANS, rc.WARBAND, 6)
    place_piece(state, rc.BITURIGES, rc.GERMANS, rc.WARBAND, 6)
    def unexpected(*args, **kwargs):
        pytest.fail('Route collection must not ask a future Harassment decision')
    state['decision_agent'] = unexpected
    before, rng = deepcopy(state['spaces']), state['rng'].getstate()
    # Two hostile Regions can eliminate this force on later dice. The route
    # must remain selectable now; neither hostile Control nor Harassment stops it.
    assert [rc.ARVERNI_REGION, rc.BITURIGES, rc.CARNUTES] in _march_routes(
        state, rc.PROVINCIA, rc.ROMANS)
    assert state['spaces'] == before and state['rng'].getstate() == rng


@pytest.mark.parametrize('owner', [rc.BELGAE, rc.AEDUI, rc.GERMANS])
def test_actual_a64_abatis_stops_roman_entry_regardless_of_owner(owner):
    from fs_bot.cards.card_effects import execute_card_A64
    state = board(leader=rc.CAESAR, scenario=rc.SCENARIO_ARIOVISTUS)
    place_piece(state, rc.ARVERNI_REGION, owner, rc.WARBAND)
    state.update(executing_faction=owner, event_params={'region': rc.ARVERNI_REGION})
    execute_card_A64(state)
    assert state['markers'][rc.ARVERNI_REGION][rc.MARKER_ABATIS] == owner
    assert [rc.ARVERNI_REGION, rc.BITURIGES] not in _march_routes(state, rc.PROVINCIA, rc.ROMANS)
    result = march_group(state, rc.ROMANS, rc.PROVINCIA,
        [rc.ARVERNI_REGION, rc.BITURIGES], {rc.LEGION: 2, rc.LEADER: rc.CAESAR})
    assert result['path'] == [rc.PROVINCIA, rc.ARVERNI_REGION]
    assert result['stopped_reason'] == 'Entering Abatis region'


def test_actual_abatis_survives_interlude_and_only_stops_roman_march():
    from fs_bot.cards.card_effects import execute_card_A64
    from fs_bot.engine.interlude import run_interlude
    state = build_initial_state(rc.SCENARIO_GALLIC_WAR, seed=7)
    place_piece(state, rc.ARVERNI_REGION, rc.GERMANS, rc.WARBAND)
    state.update(executing_faction=rc.GERMANS, event_params={'region': rc.ARVERNI_REGION})
    execute_card_A64(state)
    run_interlude(state, britannia_decision=False)
    assert state['scenario'] == rc.SCENARIO_PAX_GALLICA
    assert state['markers'][rc.ARVERNI_REGION][rc.MARKER_ABATIS] == rc.GERMANS
    place_piece(state, rc.PROVINCIA, rc.ROMANS, rc.LEGION, from_legions_track=True)
    assert [rc.ARVERNI_REGION, rc.BITURIGES] not in _march_routes(state, rc.PROVINCIA, rc.ROMANS)
    from fs_bot.commands.march import _check_crossing_stop
    assert _check_crossing_stop(state, rc.PROVINCIA, rc.ARVERNI_REGION, rc.ARVERNI) == (False, None)
