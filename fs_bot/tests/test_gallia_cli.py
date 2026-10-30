"""Gallia Togata remains selectable through normal and scoped menus."""
import io

import pytest

from fs_bot import rules_consts as rc
from fs_bot.cards.card_effects import execute_event
from fs_bot.state.state_schema import build_initial_state
from fs_bot.cli.human_plan import (
    _collect_march, _march_routes, _playable_regions, _regions_with_pieces,
)
from fs_bot.engine.execute import _execute_march
from fs_bot.board.pieces import place_piece


def gallia(scenario):
    state = build_initial_state(scenario, seed=3)
    execute_event(state, 'A5' if scenario in rc.ARIOVISTUS_SCENARIOS else 5)
    state['resources'][rc.ROMANS] = 0
    return state


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
def test_human_march_can_select_actual_gallia_garrison_at_zero_resources(scenario):
    state = gallia(scenario)
    out = io.StringIO()
    plan = _collect_march(state, rc.ROMANS,
        io.StringIO(f'{rc.CISALPINA}\n{rc.SEQUANI}\nall 3\n'), out, True)
    assert plan['origins'] == [rc.CISALPINA]
    assert plan['routes'] == {rc.CISALPINA: [rc.SEQUANI]}
    result = _execute_march(state, rc.ROMANS, {'command': 'March', 'details': plan})
    assert result['executed'] and result['total_cost'] == 0


@pytest.mark.parametrize('scenario', [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
def test_scoped_geography_keeps_event_limits_and_gallia_ownership(scenario):
    state = gallia(scenario)
    # Route legality now validates a real carried group; empty origins do
    # not constitute a March, even when their map edge would be traversable.
    place_piece(state, rc.SEQUANI, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.SEQUANI, rc.GERMANS, rc.WARBAND)
    state['_cli_allowed_regions'] = {rc.CISALPINA}
    assert _playable_regions(state, rc.ROMANS) == [rc.CISALPINA]
    assert _regions_with_pieces(state, rc.ROMANS) == [rc.CISALPINA]
    assert _playable_regions(state, rc.GERMANS) == []
    assert [rc.CISALPINA] in _march_routes(state, rc.SEQUANI, rc.ROMANS)
    assert [rc.CISALPINA] not in _march_routes(state, rc.SEQUANI, rc.GERMANS)


def test_required_event_destination_routes_include_activated_cisalpina():
    state = gallia(rc.SCENARIO_GREAT_REVOLT)
    place_piece(state, rc.AEDUI_REGION, rc.ROMANS, rc.AUXILIA)
    place_piece(state, rc.SEQUANI, rc.AEDUI, rc.WARBAND)
    state['_cli_required_destinations'] = {rc.CISALPINA}
    routes = _march_routes(state, rc.AEDUI_REGION, rc.ROMANS)
    assert [rc.SEQUANI, rc.CISALPINA] in routes
    assert all(route[-1] == rc.CISALPINA and len(route) <= 2 for route in routes)
    assert _march_routes(state, rc.SEQUANI, rc.AEDUI) == []


def test_card44_typed_replacement_menu_includes_actual_gallia_region():
    from fs_bot.cards.param_schema import card_param_schema, kind_values
    state = gallia(rc.SCENARIO_GREAT_REVOLT)
    schema = card_param_schema(44, state['scenario'])['replacements']
    assert rc.CISALPINA in kind_values(state, schema['entry_fields']['region'], schema)
