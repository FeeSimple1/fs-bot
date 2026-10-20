"""Human Event choices must preserve source-defined piece and field types."""

import random

import pytest

from fs_bot import rules_consts as rc
from fs_bot.cards.param_schema import card_param_schema, generate_params
from fs_bot.cli.human_plan import _kind_options
from fs_bot.state.setup import setup_scenario


@pytest.mark.parametrize(
    "card, expected",
    [
        (32, {rc.WARBAND, rc.LEGION, rc.AUXILIA, rc.LEADER}),
        (62, {rc.WARBAND, rc.LEGION, rc.AUXILIA, rc.LEADER}),
        (66, {rc.WARBAND, rc.LEADER}),
    ],
)
def test_relocation_menus_offer_only_card_listed_mobile_pieces(card, expected):
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=1)
    spec = card_param_schema(card, state["scenario"])["moves"]
    options = _kind_options(state, "piece_type", spec)
    assert {value for _, value in options} == expected
    assert rc.ALLY not in {value for _, value in options}
    assert rc.CITADEL not in {value for _, value in options}
    assert rc.FORT not in {value for _, value in options}


@pytest.mark.parametrize(
    "card, key, allowed",
    [
        (22, "replacements", {rc.WARBAND, rc.AUXILIA}),
        (40, "placements", {rc.WARBAND, rc.AUXILIA, rc.ALLY}),
    ],
)
def test_piece_constraints_do_not_replace_region_faction_or_count_choices(
    card, key, allowed
):
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=1)
    spec = card_param_schema(card, state["scenario"])[key]
    assert {v for _, v in _kind_options(state, "piece_type", spec)} == allowed
    regions = {v for _, v in _kind_options(state, "region", spec)}
    assert rc.SEQUANI in regions
    assert not regions & allowed
    assert {v for _, v in _kind_options(state, "faction", spec)} == set(rc.FACTIONS)
    counts = [v for _, v in _kind_options(state, "count", spec)]
    assert counts and all(isinstance(v, int) for v in counts)


@pytest.mark.parametrize("card, key", [(22, "replacements"), (40, "placements")])
def test_generated_entry_fields_keep_their_types(card, key):
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=1)
    for seed in range(10):
        entries = generate_params(state, card, random.Random(seed), include_p=1)[key]
        assert entries
        for entry in entries:
            assert entry["region"] in state["spaces"]
            faction = entry.get("target_faction", entry.get("faction"))
            assert faction in rc.FACTIONS
            if "count" in entry:
                assert isinstance(entry["count"], int)


def test_migration_beneficiary_menu_is_gallic_even_for_roman_executor():
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=1)
    state["executing_faction"] = rc.ROMANS
    spec = card_param_schema(66, state["scenario"])["faction"]
    assert {v for _, v in _kind_options(state, "faction", spec)} == {
        rc.ARVERNI, rc.AEDUI, rc.BELGAE}


@pytest.mark.parametrize("scenario", [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
def test_relocation_region_menus_respect_britannia_rules(scenario):
    state = setup_scenario(scenario, seed=1)
    forced = card_param_schema(32, scenario)["moves"]
    fleet = card_param_schema(62, scenario)["moves"]
    assert rc.BRITANNIA not in {v for _, v in _kind_options(state, "region", forced)}
    fleet_regions = {v for _, v in _kind_options(state, "region", fleet)}
    assert (rc.BRITANNIA in fleet_regions) == (scenario == rc.SCENARIO_GREAT_REVOLT)
    assert rc.PICTONES in fleet_regions
