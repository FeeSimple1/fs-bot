"""Live validation must reject impossible physical inventories (§1.4.1).

These intentionally corrupt counts directly: piece conservation must not
certify a state that the playable-save boundary cannot reload.
"""

import copy

import pytest

from fs_bot import rules_consts as rc
from fs_bot.state.serialize import SaveFileError, encode, load_game, save_game
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import (
    build_initial_state,
    check_structural_integrity,
    validate_state,
)


VALIDATORS = (validate_state, check_structural_integrity)


def _set_path(state, path, value):
    target = state
    for key in path[:-1]:
        target = target.setdefault(key, {})
    target[path[-1]] = value


COUNT_PATHS = (
    ("spaces", rc.PROVINCIA, "pieces", rc.ROMANS, rc.HIDDEN, rc.AUXILIA),
    ("spaces", rc.PROVINCIA, "pieces", rc.ROMANS, rc.FORT),
    ("available", rc.ROMANS, rc.AUXILIA),
    ("available", rc.ROMANS, rc.LEADER),
    ("removed_pieces", rc.BELGAE, rc.WARBAND),
    ("legions_track", rc.LEGIONS_ROW_BOTTOM),
    ("fallen_legions",),
    ("removed_legions",),
    ("winter_track_legions",),
)


@pytest.mark.parametrize("path", COUNT_PATHS)
@pytest.mark.parametrize("bad_count", [-1, 0.5, True, "1", None])
def test_live_validators_report_invalid_counts_without_arithmetic_failure(path, bad_count):
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=21)
    _set_path(state, path, bad_count)
    before = encode(copy.deepcopy(state))
    for validator in VALIDATORS:
        errors = validator(state)
        assert errors
        assert any("nonnegative integer" in error for error in errors)
    assert encode(state) == before


@pytest.mark.parametrize("scenario", [rc.SCENARIO_PAX_GALLICA, rc.SCENARIO_ARIOVISTUS])
@pytest.mark.parametrize("map_count", [-1, 0.5, True])
def test_compensated_map_corruption_cannot_pass_conservation_or_reload(tmp_path, scenario, map_count):
    state = build_initial_state(scenario, seed=21)
    _set_path(state, COUNT_PATHS[0], map_count)
    # The physical total remains twenty, which previously concealed the bad
    # domains from both runtime validators (including bool's integer behavior).
    state["available"][rc.ROMANS][rc.AUXILIA] = 20 - map_count
    for validator in VALIDATORS:
        assert any("nonnegative integer" in error for error in validator(state))
    path = tmp_path / "invalid-count.json"
    save_game(state, path)
    with pytest.raises(SaveFileError, match="nonnegative integer"):
        load_game(path, validate=True)


@pytest.mark.parametrize("path", [
    ("spaces",),
    ("spaces", rc.PROVINCIA),
    ("spaces", rc.PROVINCIA, "pieces"),
    ("spaces", rc.PROVINCIA, "pieces", rc.ROMANS),
    ("spaces", rc.PROVINCIA, "pieces", rc.ROMANS, rc.HIDDEN),
    ("available",),
    ("available", rc.ROMANS),
    ("removed_pieces",),
    ("removed_pieces", rc.BELGAE),
    ("legions_track",),
])
def test_malformed_inventory_containers_are_reported(path):
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=21)
    _set_path(state, path, [])
    for validator in VALIDATORS:
        assert any("must be a mapping" in error for error in validator(state))


def test_legions_track_row_limit_is_checked_even_when_total_is_conserved(tmp_path):
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=21)
    state["legions_track"][rc.LEGIONS_ROW_BOTTOM] += 1
    state["legions_track"][rc.LEGIONS_ROW_MIDDLE] -= 1
    for validator in VALIDATORS:
        assert any("max 4" in error for error in validator(state))
    path = tmp_path / "invalid-track.json"
    save_game(state, path)
    with pytest.raises(SaveFileError, match="max 4"):
        load_game(path, validate=True)


@pytest.mark.parametrize("resources", [-1, 0.5, True, "1", None, rc.MAX_RESOURCES + 1])
def test_resources_follow_integer_domain_and_printed_track_limit(resources):
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=21)
    state["resources"][rc.ROMANS] = resources
    assert any("Resources" in error for error in check_structural_integrity(state))


@pytest.mark.parametrize("scenario", rc.ALL_SCENARIOS)
def test_every_scenario_setup_still_passes_live_and_save_validation(tmp_path, scenario):
    state = setup_scenario(scenario, seed=21)
    for validator in VALIDATORS:
        assert validator(state) == []
    path = tmp_path / "valid-counts.json"
    save_game(state, path)
    resumed, _, _ = load_game(path, validate=True)
    assert encode(resumed) == encode(state)
