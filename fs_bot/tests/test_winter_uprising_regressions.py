"""A66 forced activation and Gallic War Interlude Winter Events.

Source: A66; A6.2; 5.1.3 Partial Execution; A Scenario - The Gallic War,
Winter Events (resolve Uprising then shaded Campaign before Adjust Forces).
"""
from collections import Counter

import pytest

import fs_bot.rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, count_pieces_by_state
from fs_bot.cards.card_effects import execute_card_A63, execute_card_A66
from fs_bot.engine.arverni_phase import run_arverni_phase
from fs_bot.engine.execute import _resolve_winter_uprising
from fs_bot.engine.interlude import _step1_winter_events, run_interlude
from fs_bot.engine.winter_campaign import winter_campaign_after_harvest
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state
from fs_bot.map.map_data import get_adjacent_for_state


def _uprising(state, region=rc.CISALPINA):
    state["event_params"] = {"region": region}
    execute_card_A66(state)
    state.pop("event_params")


@pytest.mark.parametrize("scenario", [rc.SCENARIO_ARIOVISTUS, rc.SCENARIO_GALLIC_WAR])
def test_actual_a66_without_at_war_targets_finishes_available_phase_steps(scenario):
    state = build_initial_state(scenario, seed=1)
    # No enemy in any Home/Ally/Citadel Region. A66 still activates the
    # Arverni, including March's flip-to-Hidden step away from the marker.
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.WARBAND, 2,
                piece_state=rc.REVEALED)
    _uprising(state)
    result = _resolve_winter_uprising(state)
    phase = result[1]
    assert phase["executed"]
    assert phase["result"]["at_war"]
    assert phase["result"]["triggering_regions"] == []
    assert phase["result"]["target_region"] is None
    assert phase["result"]["target_faction"] is None
    assert phase["result"]["march"]["warbands_flipped"] == 2
    assert count_pieces_by_state(state, rc.NERVII, rc.ARVERNI,
                                 rc.WARBAND, rc.HIDDEN) == 2
    within_one = {rc.CISALPINA, *get_adjacent_for_state(state, rc.CISALPINA)}
    assert sum(count_pieces(state, region, rc.ARVERNI, rc.WARBAND)
               for region in within_one) == 8
    assert all(entry['region'] in within_one for entry in result[0]['placements']['warbands'])
    assert "card_A66_winter_uprising" not in state["event_modifiers"]
    assert rc.MARKER_WINTER_UPRISING not in state["markers"][rc.CISALPINA]


def test_unforced_at_peace_activation_remains_skipped():
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=1)
    place_piece(state, rc.NERVII, rc.ARVERNI, rc.WARBAND,
                piece_state=rc.REVEALED)
    before_rng = state["rng"].getstate()
    result = run_arverni_phase(state)
    assert not result["at_war"]
    assert result["march"] is None
    assert state["rng"].getstate() == before_rng
    assert count_pieces_by_state(state, rc.NERVII, rc.ARVERNI,
                                 rc.WARBAND, rc.REVEALED) == 1


def test_interlude_resolves_actual_uprising_before_base_scenario_transition():
    state = setup_scenario(rc.SCENARIO_GALLIC_WAR, seed=8)
    state["non_player_factions"] = {rc.ROMANS, rc.AEDUI, rc.BELGAE, rc.GERMANS}
    _uprising(state)
    result = run_interlude(state, britannia_decision=False)
    events = result["step1_winter_events"]
    assert events["events_resolved"] == ["Winter Uprising!"]
    assert events["winter_uprising"][0]["warbands"] == 8
    assert events["winter_uprising"][1]["executed"]
    assert "card_A66_winter_uprising" not in state["event_modifiers"]
    assert rc.MARKER_WINTER_UPRISING not in state["markers"].get(rc.CISALPINA, {})
    assert state["scenario"] == rc.SCENARIO_PAX_GALLICA
    # The one-shot event cannot leak into a later base-game Quarters Phase.
    assert _step1_winter_events(state)["events_resolved"] == []


def test_interlude_executes_paid_campaign_after_uprising_before_force_adjustments():
    state = build_initial_state(rc.SCENARIO_GALLIC_WAR, seed=8)
    state["resources"][rc.AEDUI] = 10
    place_piece(state, rc.NERVII, rc.AEDUI, rc.WARBAND, 2)
    state["executing_faction"] = rc.AEDUI
    execute_card_A63(state, shaded=True)
    state.pop("executing_faction")
    _uprising(state)
    requests = []

    def decide(board, faction, request):
        if request["kind"] != "winter_campaign":
            return None
        assert board["scenario"] == rc.SCENARIO_GALLIC_WAR
        assert "card_A66_winter_uprising" not in board["event_modifiers"]
        within_one = {rc.CISALPINA, *get_adjacent_for_state(board, rc.CISALPINA)}
        assert sum(count_pieces(board, region, rc.ARVERNI, rc.WARBAND)
                   for region in within_one) == 8
        assert faction == rc.AEDUI
        requests.append(request["remaining_actions"])
        origin, destination = ((rc.NERVII, rc.ATREBATES) if len(requests) == 1
                               else (rc.ATREBATES, rc.NERVII))
        return {"command": rc.CMD_MARCH, "sa": "No SA", "regions": [],
                "details": {"origins": [origin], "destinations": [destination],
                            "routes": {origin: [destination]}}}

    state["decision_agent"] = decide
    events = _step1_winter_events(state)
    assert events["events_resolved"] == ["Winter Uprising!", "Winter Campaign (shaded)"]
    assert requests == [2, 1]
    assert events["winter_campaign"]["remaining_actions"] == 0
    assert state["resources"][rc.AEDUI] == 8
    assert count_pieces(state, rc.NERVII, rc.AEDUI, rc.WARBAND) == 2


@pytest.mark.parametrize("marker", [rc.MARKER_WINTER_UPRISING, "Uprising"])
def test_interlude_recovers_marker_only_uprising_in_old_saves(marker):
    state = build_initial_state(rc.SCENARIO_GALLIC_WAR, seed=1)
    state["markers"][rc.CISALPINA] = {marker: True}
    state["capabilities"]["A66"] = rc.EVENT_SHADED
    events = _step1_winter_events(state)
    assert events["winter_uprising"][1]["executed"]
    assert marker not in state["markers"][rc.CISALPINA]
    assert "A66" not in state["capabilities"]
    assert _step1_winter_events(state)["events_resolved"] == []


@pytest.mark.parametrize("region,owner", [(rc.MORINI, rc.BELGAE),
                                         (rc.SUGAMBRI, rc.GERMANS)])
def test_uprising_offers_the_printed_command_plus_special_ability(region, owner):
    state = build_initial_state(rc.SCENARIO_ARIOVISTUS, seed=1)
    _uprising(state, region)
    grants = []

    def decide(board, faction, request):
        assert faction == owner
        if request['kind'] == 'winter_uprising_placement':
            return {'use_default': True}
        assert request["kind"] == "free_action"
        assert request["with_sa"] is True
        assert request['allow_decline'] is False
        assert region in request["allowed_regions"]
        grants.append(request)
        return {"use_default": True}

    state["decision_agent"] = decide
    _resolve_winter_uprising(state)
    assert len(grants) == 1


@pytest.mark.parametrize("owner", [rc.AEDUI, rc.BELGAE])
def test_actual_a63_owner_keeps_paid_actions_after_actual_interlude(owner):
    state = build_initial_state(rc.SCENARIO_GALLIC_WAR, seed=8)
    state["resources"][owner] = 10
    place_piece(state, rc.NERVII, owner, rc.WARBAND, 4)
    state["executing_faction"] = owner
    execute_card_A63(state, shaded=True)
    state.pop("executing_faction")
    requests = []

    def decide(board, faction, request):
        if request["kind"] != "winter_campaign":
            return None
        assert faction == owner
        if board["scenario"] == rc.SCENARIO_GALLIC_WAR:
            return {"decline": True}
        requests.append(request["remaining_actions"])
        origin, destination = ((rc.NERVII, rc.ATREBATES) if len(requests) == 1
                               else (rc.ATREBATES, rc.NERVII))
        return {"command": rc.CMD_MARCH, "sa": "No SA", "regions": [],
                "details": {"origins": [origin], "destinations": [destination],
                            "routes": {origin: [destination]}}}

    state["decision_agent"] = decide
    run_interlude(state, britannia_decision=False)
    assert state["scenario"] == rc.SCENARIO_PAX_GALLICA
    resources = state["resources"][owner]
    result = winter_campaign_after_harvest(state)
    assert result["card_id"] == "A63"
    assert result["owner"] == owner
    assert result["remaining_actions"] == 0
    assert requests == [2, 1]
    assert state["resources"][owner] == resources - 2


def test_a63_does_not_leak_into_an_unrelated_base_game():
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=8)
    state["capabilities"]["A63"] = rc.EVENT_SHADED
    state["capability_owners"] = {"A63": rc.AEDUI}
    assert winter_campaign_after_harvest(state) is None


def test_retained_german_a63_does_not_silently_transfer_to_arverni():
    state = build_initial_state(rc.SCENARIO_PAX_GALLICA, seed=8)
    state["interlude_completed"] = True
    state["capabilities"]["A63"] = rc.EVENT_SHADED
    state["capability_owners"] = {"A63": rc.GERMANS}
    # Provisional PR-04 preserves German ownership while making the retained
    # capability dormant; authoritative clarification may supersede this.
    assert winter_campaign_after_harvest(state) is None
    assert state["capability_owners"]["A63"] == rc.GERMANS


def test_provisional_german_campaign_acts_during_interlude_then_stays_dormant(tmp_path):
    """PR-04 permits the final paid German activation before the seat changes."""
    from fs_bot.state.serialize import save_game, load_game

    state = build_initial_state(rc.SCENARIO_GALLIC_WAR, seed=8)
    state["resources"][rc.GERMANS] = 10
    place_piece(state, rc.NERVII, rc.GERMANS, rc.WARBAND, 4)
    state["executing_faction"] = rc.GERMANS
    execute_card_A63(state, shaded=True)
    state.pop("executing_faction")
    requests = []

    def decide(board, faction, request):
        if request["kind"] != "winter_campaign":
            return None
        assert board["scenario"] == rc.SCENARIO_GALLIC_WAR
        assert faction == rc.GERMANS
        requests.append((request["remaining_actions"], board["resources"][faction]))
        origin, destination = ((rc.NERVII, rc.ATREBATES) if len(requests) == 1
                               else (rc.ATREBATES, rc.NERVII))
        return {"command": rc.CMD_MARCH, "sa": "No SA", "regions": [],
                "details": {"origins": [origin], "destinations": [destination],
                            "routes": {origin: [destination]}}}

    state["decision_agent"] = decide
    result = run_interlude(state, britannia_decision=False)
    campaign = result["step1_winter_events"]["winter_campaign"]
    assert requests == [(2, 10), (1, 9)]
    assert campaign["owner"] == rc.GERMANS
    assert campaign["remaining_actions"] == 0
    assert state["scenario"] == rc.SCENARIO_PAX_GALLICA
    assert state["capability_owners"]["A63"] == rc.GERMANS
    assert state["capabilities"]["A63"] == rc.EVENT_SHADED
    assert winter_campaign_after_harvest(state) is None

    path = tmp_path / "german-campaign-after-interlude.json"
    save_game(state, path)
    resumed, _, _ = load_game(path, validate=True)
    resumed["decision_agent"] = lambda *_: pytest.fail("Dormant A63 prompted a player")
    assert winter_campaign_after_harvest(resumed) is None
    assert resumed["capability_owners"]["A63"] == rc.GERMANS
    assert resumed["capabilities"]["A63"] == rc.EVENT_SHADED


@pytest.mark.parametrize("scenario,seed", [
    (rc.SCENARIO_ARIOVISTUS, 1),
    (rc.SCENARIO_GALLIC_WAR, 1),
    (rc.SCENARIO_GALLIC_WAR, 8),
])
def test_reported_census_games_do_not_swallow_winter_exceptions(scenario, seed):
    from fs_bot.tools.error_census import play_game, census_result
    result = play_game(scenario, seed)
    occurrences = []
    census_result(result, Counter(), {}, scenario, seed, occurrences)
    assert not [row for row in occurrences
                if row["card"] == rc.WINTER_CARD
                and ("IndexError(" in row["message"]
                     or "CommandError(" in row["message"])]
