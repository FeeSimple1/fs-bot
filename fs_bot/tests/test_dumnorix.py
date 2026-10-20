"""Card Reference 44/A44: finite replacements and just-placed free actions."""
from copy import deepcopy

import pytest

import fs_bot.rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces, count_pieces_by_state
from fs_bot.cards.card_effects import execute_event
from fs_bot.cards.dumnorix import derive_params
from fs_bot.engine.execute import _execute_event
from fs_bot.state.state_schema import build_initial_state, validate_state


def game(profile="original", scenario=rc.SCENARIO_GREAT_REVOLT):
    s = build_initial_state(scenario, seed=4)
    s["card_edition"] = profile
    s["executing_faction"] = rc.AEDUI
    s["non_player_factions"] = set()
    return s


def rep(source=rc.BELGAE, destination=rc.AEDUI, kind=rc.WARBAND,
        to_kind=rc.WARBAND, region=rc.CARNUTES, n=1, **extra):
    return {"region": region, "from_faction": source, "to_faction": destination,
            "from_type": kind, "to_type": to_kind, "count": n, **extra}


def reveal(n=2, faction=rc.AEDUI, target=rc.BELGAE, region=rc.CARNUTES, **extra):
    return {"region": region, "faction": faction, "target_faction": target,
            "count": n, **extra}


def raid(faction=rc.ARVERNI, target=None, region=rc.CARNUTES):
    return {"region": region, "faction": faction, "target_faction": target}


def snapshot(s):
    return deepcopy({k: (v.getstate() if k == "rng" else v) for k, v in s.items()})


def play(s, shaded=False, faction=rc.AEDUI):
    return _execute_event(s, faction, {"details": {"card_id": 44,
        "text_preference": rc.EVENT_SHADED if shaded else rc.EVENT_UNSHADED,
        "event_params": s["event_params"]}}, human=True)


@pytest.mark.parametrize("profile", ["original", "second-edition"])
@pytest.mark.parametrize("shaded,entry", [
    (False, rep(n=5)), (True, rep(rc.ROMANS, rc.ARVERNI, rc.AUXILIA, n=4)),
    (False, rep(n=0)), (False, rep(n=-1)), (False, rep(n=True)),
    (False, rep(n=1.5)), (False, rep(source=rc.ROMANS)),
    (False, rep(kind=rc.LEGION)), (False, rep(destination=rc.BELGAE)),
    (False, rep(destination=rc.ROMANS, to_kind=rc.WARBAND)),
    (True, rep(source=rc.ARVERNI)), (True, rep(destination=rc.ROMANS)),
    (True, rep(rc.ROMANS, rc.ARVERNI, rc.AUXILIA, piece_state=rc.SCOUTED)),
    (False, rep(region=rc.CISALPINA)), (False, rep(piece_state="typo")),
])
def test_invalid_replacements_fail_without_mutation(profile, shaded, entry):
    s = game(profile)
    place_piece(s, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 6)
    place_piece(s, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 6)
    s["event_params"] = {"replacements": [entry]}
    before = snapshot(s)
    with pytest.raises(ValueError):
        execute_event(s, 44, shaded)
    assert snapshot(s) == before


@pytest.mark.parametrize("profile", ["original", "second-edition"])
def test_limit_counts_entries_not_just_per_entry(profile):
    s = game(profile)
    place_piece(s, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 6)
    s["event_params"] = {"replacements": [rep(n=3), rep(n=2)]}
    before = snapshot(s)
    with pytest.raises(ValueError):
        execute_event(s, 44)
    assert snapshot(s) == before


def test_missing_sources_never_create_phantom_replacements():
    s = game()
    place_piece(s, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    s["event_params"] = {"replacements": [rep(n=4)]}
    execute_event(s, 44)
    assert count_pieces(s, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 1
    assert s["event_modifiers"]["card_44_placed"] == [
        {"region": rc.CARNUTES, "faction": rc.AEDUI, "piece_type": rc.WARBAND, "count": 1}]
    assert validate_state(s) == []


def test_newly_placed_piece_cannot_be_replaced_again():
    s = game()
    place_piece(s, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    s["event_params"] = {"replacements": [rep(), rep(source=rc.AEDUI,
        destination=rc.ROMANS, to_kind=rc.AUXILIA)]}
    execute_event(s, 44)
    assert count_pieces(s, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 1
    assert count_pieces(s, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 0


def test_unavailable_destination_only_removes_and_grants_no_command(monkeypatch):
    s = game("second-edition")
    place_piece(s, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    place_piece(s, rc.BITURIGES, rc.ARVERNI, rc.WARBAND,
                s["available"][rc.ARVERNI][rc.WARBAND])
    s["event_params"] = {"replacements": [rep(rc.ROMANS, rc.ARVERNI, rc.AUXILIA)]}
    import fs_bot.engine.execute as exe
    def forbidden(*args, **kwargs):
        pytest.fail("No placed pieces means no authorized free Command")
    monkeypatch.setattr(exe, "_resolve_free_command", forbidden)
    result = play(s, True, rc.ARVERNI)
    assert result["executed"]
    assert count_pieces(s, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 0
    assert count_pieces(s, rc.CARNUTES, rc.ARVERNI, rc.WARBAND) == 0
    assert validate_state(s) == []


@pytest.mark.parametrize("profile", ["original", "second-edition"])
@pytest.mark.parametrize("owner,kind", [(rc.ROMANS, rc.AUXILIA), (rc.AEDUI, rc.WARBAND)])
def test_scout_is_player_chosen_and_uses_only_new_pieces(profile, owner, kind):
    s = game(profile)
    place_piece(s, rc.CARNUTES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(s, rc.CARNUTES, owner, kind, 5)
    place_piece(s, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 5)
    s["event_params"] = {"replacements": [rep(destination=owner, to_kind=kind)],
                         "scout_reveals": [reveal(faction=owner)]}
    assert play(s)["executed"]
    assert count_pieces_by_state(s, rc.CARNUTES, owner, kind, rc.HIDDEN) == 5
    assert count_pieces_by_state(s, rc.CARNUTES, owner, kind, rc.REVEALED) == 1
    assert count_pieces_by_state(s, rc.CARNUTES, rc.BELGAE, rc.WARBAND, rc.SCOUTED) == 2
    assert validate_state(s) == []


@pytest.mark.parametrize("choice", ["too_many_scouts", "too_many_targets", "outside_cohort", "auxilia_target"])
def test_invalid_scout_plan_rejects_before_replacing(choice):
    s = game()
    place_piece(s, rc.CARNUTES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(s, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 5)
    place_piece(s, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 5)
    r = reveal()
    if choice == "too_many_scouts": r["scouts"] = 2
    if choice == "too_many_targets": r.update(count=3, scouts=1)
    if choice == "outside_cohort": r["region"] = rc.BITURIGES
    if choice == "auxilia_target": r["target_faction"] = rc.ROMANS
    s["event_params"] = {"replacements": [rep()], "scout_reveals": [r]}
    before = snapshot(s)
    with pytest.raises(ValueError): execute_event(s, 44)
    assert snapshot(s) == before


@pytest.mark.parametrize("leader,region,valid", [
    (rc.CAESAR, rc.BITURIGES, True), (rc.SUCCESSOR, rc.BITURIGES, False),
    (rc.SUCCESSOR, rc.CARNUTES, True), (rc.CAESAR, rc.PROVINCIA, False),
])
def test_scout_respects_caesar_and_successor_reach(leader, region, valid):
    s = game()
    place_piece(s, region, rc.ROMANS, rc.LEADER, leader_name=leader)
    place_piece(s, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 3)
    s["event_params"] = {"replacements": [rep()], "scout_reveals": [reveal()]}
    before = snapshot(s)
    if valid:
        assert play(s)["executed"]
    else:
        with pytest.raises(ValueError): execute_event(s, 44)
        assert snapshot(s) == before


def test_aedui_scout_moves_once_and_reveals_at_destination():
    s = game()
    place_piece(s, rc.BITURIGES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(s, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    place_piece(s, rc.BITURIGES, rc.BELGAE, rc.WARBAND, 2)
    place_piece(s, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 5)
    s["event_params"] = {"replacements": [rep()], "scout_moves": [
        {"from_region": rc.CARNUTES, "to_region": rc.BITURIGES, "faction": rc.AEDUI}],
        "scout_reveals": [reveal(region=rc.BITURIGES)]}
    assert play(s)["executed"]
    assert count_pieces_by_state(s, rc.CARNUTES, rc.AEDUI, rc.WARBAND, rc.HIDDEN) == 5
    assert count_pieces_by_state(s, rc.BITURIGES, rc.AEDUI, rc.WARBAND, rc.REVEALED) == 1
    assert count_pieces_by_state(s, rc.BITURIGES, rc.BELGAE, rc.WARBAND, rc.SCOUTED) == 2


def test_same_new_piece_cannot_move_twice():
    s = game()
    place_piece(s, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    s["event_params"] = {"replacements": [rep()], "scout_moves": [
        {"from_region": rc.CARNUTES, "to_region": rc.BITURIGES, "faction": rc.AEDUI},
        {"from_region": rc.BITURIGES, "to_region": rc.CARNUTES, "faction": rc.AEDUI}]}
    before = snapshot(s)
    with pytest.raises(ValueError): execute_event(s, 44)
    assert snapshot(s) == before


def test_one_scout_may_reveal_two_different_enemy_factions():
    s = game()
    place_piece(s, rc.CARNUTES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(s, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 2)
    place_piece(s, rc.CARNUTES, rc.ARVERNI, rc.WARBAND)
    s["event_params"] = {"replacements": [rep()], "scout_reveals": [
        reveal(n=1, scouts=1), reveal(n=1, target=rc.ARVERNI, scouts=0)]}
    assert play(s)["executed"]
    for target in (rc.ARVERNI, rc.BELGAE):
        assert count_pieces_by_state(s, rc.CARNUTES, target, rc.WARBAND, rc.SCOUTED) == 1


def test_scout_may_be_declined_even_when_targets_exist():
    s = game()
    place_piece(s, rc.CARNUTES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(s, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 3)
    s["event_params"] = {"replacements": [rep()], "scout_reveals": [], "scout_moves": []}
    assert play(s)["executed"]
    assert count_pieces_by_state(s, rc.CARNUTES, rc.BELGAE, rc.WARBAND, rc.HIDDEN) == 2


@pytest.mark.parametrize("scenario,expected", [(rc.SCENARIO_GREAT_REVOLT, rc.ARVERNI),
                                               (rc.SCENARIO_ARIOVISTUS, rc.GERMANS)])
def test_aedui_np_never_moves_and_scouts_prescribed_hidden_priority(scenario, expected):
    from fs_bot.cards.dumnorix import derive_scout_reveals
    s = game(scenario=scenario)
    place_piece(s, rc.CARNUTES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    for faction in (rc.ARVERNI, rc.BELGAE, rc.GERMANS):
        place_piece(s, rc.CARNUTES, faction, rc.WARBAND, 6)
    params = derive_params(s, rc.AEDUI, False)
    assert params["scout_moves"] == []
    assert params["scout_reveals"][0]["target_faction"] == expected
    assert {(r["to_faction"], r["to_type"]) for r in params["replacements"]} == {(rc.AEDUI, rc.WARBAND)}
    # Existing Auxilia cannot expand this single new blue Scout's budget.
    place_piece(s, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 8)
    cohort = [{"region": rc.CARNUTES, "faction": rc.AEDUI, "count": 1}]
    assert derive_scout_reveals(s, cohort, rc.AEDUI) == [reveal(target=expected, scouts=1)]


def test_original_raid_cannot_borrow_preexisting_warbands():
    s = game()
    place_piece(s, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    place_piece(s, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 5)
    s["event_params"] = {"replacements": [rep(rc.ROMANS, rc.ARVERNI, rc.AUXILIA)],
                         "raid_actions": [raid(), raid()]}
    before = snapshot(s)
    with pytest.raises(ValueError): execute_event(s, 44, True)
    assert snapshot(s) == before
    s["event_params"]["raid_actions"] = [raid()]
    resources = s["resources"][rc.ARVERNI]
    assert play(s, True, rc.ARVERNI)["executed"]
    assert s["resources"][rc.ARVERNI] == resources + 1
    assert count_pieces_by_state(s, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 5


def test_original_raid_may_be_declined_by_player():
    s = game()
    place_piece(s, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    s["event_params"] = {"replacements": [rep(rc.ROMANS, rc.ARVERNI, rc.AUXILIA)], "raid_actions": []}
    before_resources = dict(s["resources"])
    assert play(s, True, rc.ARVERNI)["executed"]
    assert s["resources"] == before_resources
    assert count_pieces_by_state(s, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, rc.HIDDEN) == 1


def test_original_raid_multiple_owners_share_only_remaining_enemy_resources():
    s = game()
    place_piece(s, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 3)
    s["resources"][rc.ROMANS] = 1
    s["event_params"] = {"replacements": [
        rep(rc.ROMANS, rc.ARVERNI, rc.AUXILIA), rep(rc.ROMANS, rc.BELGAE, rc.AUXILIA)]}
    assert play(s, True, rc.ARVERNI)["executed"]
    assert s["resources"][rc.ROMANS] == 0
    assert count_pieces_by_state(s, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, rc.REVEALED) == 1
    assert count_pieces_by_state(s, rc.CARNUTES, rc.BELGAE, rc.WARBAND, rc.REVEALED) == 1


@pytest.mark.parametrize("capability", [False, True])
def test_original_raid_per_region_limit_and_baggage_trains(capability):
    s = game()
    place_piece(s, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 3)
    if capability:
        s["capabilities"][8] = rc.EVENT_SHADED
        s["capability_owners"] = {8: rc.ARVERNI}
    s["event_params"] = {"replacements": [rep(rc.ROMANS, rc.ARVERNI, rc.AUXILIA, n=3)],
                         "raid_actions": [raid()] * 3}
    if capability:
        assert play(s, True, rc.ARVERNI)["executed"]
        assert count_pieces_by_state(s, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, rc.REVEALED) == 3
    else:
        before = snapshot(s)
        with pytest.raises(ValueError): execute_event(s, 44, True)
        assert snapshot(s) == before


def test_base_german_free_raid_takes_resources_without_gaining():
    s = game()
    place_piece(s, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 2)
    s["resources"][rc.ROMANS] = 4
    s["event_params"] = {"replacements": [rep(rc.ROMANS, rc.GERMANS, rc.AUXILIA)],
                         "raid_actions": [raid(rc.GERMANS, rc.ROMANS)]}
    assert play(s, True, rc.ARVERNI)["executed"]
    assert s["resources"][rc.ROMANS] == 3
    assert rc.GERMANS not in s["resources"]


def test_arverni_np_exposes_legions_in_most_regions_then_uses_aedui_warbands():
    s = game()
    for region, n in ((rc.CARNUTES, 3), (rc.BITURIGES, 1), (rc.AEDUI_REGION, 1)):
        place_piece(s, region, rc.ROMANS, rc.AUXILIA, n)
        place_piece(s, region, rc.ROMANS, rc.LEGION, from_legions_track=True)
    p = derive_params(s, rc.ARVERNI, True)
    assert {r["region"] for r in p["replacements"][:2]} == {rc.BITURIGES, rc.AEDUI_REGION}
    assert sum(r["count"] for r in p["replacements"]) == 3
    s = game()
    place_piece(s, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 3)
    p = derive_params(s, rc.ARVERNI, True)
    assert p["replacements"] == [rep(rc.AEDUI, rc.ARVERNI, n=3, piece_state=rc.HIDDEN)]


def test_german_np_replacements_obey_germania_settlement_neighborhood():
    s = game(scenario=rc.SCENARIO_ARIOVISTUS)
    place_piece(s, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 3)
    assert derive_params(s, rc.GERMANS, True) is None
    place_piece(s, rc.SUGAMBRI, rc.ROMANS, rc.AUXILIA, 2)
    place_piece(s, rc.UBII, rc.ROMANS, rc.AUXILIA, 1)
    p = derive_params(s, rc.GERMANS, True)
    assert {r["region"] for r in p["replacements"]} == {rc.SUGAMBRI, rc.UBII}
    assert sum(r["count"] for r in p["replacements"]) == 3


def test_new_human_choices_are_available_in_typed_card_menu():
    from fs_bot.cards.param_schema import card_param_schema, kind_values
    s = game()
    schema = card_param_schema(44, s["scenario"])
    assert set(schema) == {"replacements", "scout_moves", "scout_reveals", "raid_actions"}
    assert kind_values(s, schema["raid_actions"]["entry_fields"]["target_faction"])[0] is None


def test_typed_menu_can_decline_raid_instead_of_omitting_choice():
    import io
    from fs_bot.cli.human_plan import _prompt_event_param
    from fs_bot.cards.param_schema import card_param_schema
    s = game()
    spec = card_param_schema(44, s["scenario"])["raid_actions"]
    assert _prompt_event_param(s, "raid_actions", spec, io.StringIO("n\n"), io.StringIO()) == []


def test_roman_np_scout_move_cannot_borrow_existing_auxilia():
    s = game()
    place_piece(s, rc.BITURIGES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(s, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 6)
    place_piece(s, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    params = derive_params(s, rc.ROMANS, False)
    assert params["scout_moves"] == [{"from_region": rc.CARNUTES,
        "to_region": rc.BITURIGES, "count": 1, "piece_state": rc.HIDDEN, "faction": rc.ROMANS}]
    s["event_params"] = params
    assert play(s, faction=rc.ROMANS)["executed"]
    assert count_pieces(s, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 6
    assert count_pieces(s, rc.BITURIGES, rc.ROMANS, rc.AUXILIA) == 1


def test_roman_np_scout_can_reveal_already_revealed_warbands():
    s = game()
    place_piece(s, rc.CARNUTES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(s, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 7, piece_state=rc.REVEALED)
    params = derive_params(s, rc.ROMANS, False)
    assert params["scout_reveals"] == [reveal(n=3, faction=rc.ROMANS, scouts=2)]
    s["event_params"] = params
    assert play(s, faction=rc.ROMANS)["executed"]
    assert count_pieces_by_state(s, rc.CARNUTES, rc.BELGAE, rc.WARBAND, rc.SCOUTED) == 3


def test_card12_unshaded_allows_scout_reveal_without_leader():
    s = game()
    s["capabilities"][12] = rc.EVENT_UNSHADED
    place_piece(s, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 3)
    s["event_params"] = {"replacements": [rep()], "scout_reveals": [reveal()]}
    assert play(s)["executed"]
    assert count_pieces_by_state(s, rc.CARNUTES, rc.BELGAE, rc.WARBAND, rc.SCOUTED) == 2


def test_card12_shaded_limits_scout_reveal_to_one_region_atomically():
    s = game()
    s["capabilities"][12] = rc.EVENT_SHADED
    place_piece(s, rc.CARNUTES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    for region in (rc.CARNUTES, rc.BITURIGES):
        place_piece(s, region, rc.BELGAE, rc.WARBAND, 3)
    s["event_params"] = {"replacements": [rep(), rep(region=rc.BITURIGES)],
                         "scout_reveals": [reveal(), reveal(region=rc.BITURIGES)]}
    before = snapshot(s)
    with pytest.raises(ValueError): execute_event(s, 44)
    assert snapshot(s) == before


def test_missing_source_never_authorizes_revised_board_wide_command(monkeypatch):
    s = game("second-edition")
    s["event_params"] = {"replacements": [rep(rc.ROMANS, rc.ARVERNI, rc.AUXILIA)]}
    import fs_bot.engine.execute as exe
    monkeypatch.setattr(exe, "_resolve_free_command", lambda *a, **k: pytest.fail("No placements"))
    assert play(s, True, rc.ARVERNI)["executed"]
    assert count_pieces(s, rc.CARNUTES, rc.ARVERNI, rc.WARBAND) == 0


def test_revised_command_regions_include_only_successfully_placed_pieces(monkeypatch):
    s = game("second-edition")
    place_piece(s, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    s["event_params"] = {"replacements": [rep(rc.ROMANS, rc.ARVERNI, rc.AUXILIA),
        rep(rc.ROMANS, rc.ARVERNI, rc.AUXILIA, region=rc.BITURIGES)]}
    import fs_bot.engine.execute as exe
    seen = []
    monkeypatch.setattr(exe, "_resolve_free_command", lambda *a, **k: seen.append(k) or {"executed": False})
    assert play(s, True, rc.ARVERNI)["executed"]
    assert seen == [{"allowed_regions": {rc.CARNUTES}}]


def test_german_np_prioritizes_settlement_regions_outside_germania():
    s = game("second-edition", rc.SCENARIO_ARIOVISTUS)
    place_piece(s, rc.CARNUTES, rc.GERMANS, rc.SETTLEMENT)
    place_piece(s, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 3)
    place_piece(s, rc.BITURIGES, rc.ROMANS, rc.AUXILIA, 3)
    params = derive_params(s, rc.GERMANS, True)
    assert params["replacements"] == [rep(rc.ROMANS, rc.GERMANS, rc.AUXILIA,
                                          n=3, piece_state=rc.HIDDEN)]


def test_german_bot_declines_card44_when_its_instruction_has_no_roman_target():
    from fs_bot.bots.german_bot import node_g3b
    s = game("second-edition", rc.SCENARIO_ARIOVISTUS)
    s["current_card_id"] = 44
    place_piece(s, rc.CARNUTES, rc.ROMANS, rc.AUXILIA, 3)
    assert node_g3b(s) == "Yes"
    place_piece(s, rc.SUGAMBRI, rc.ROMANS, rc.AUXILIA)
    assert node_g3b(s) == "No"


def test_roman_np_card12_reveals_even_without_roman_leader():
    s = game()
    s["capabilities"][12] = rc.EVENT_UNSHADED
    place_piece(s, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 6)
    params = derive_params(s, rc.ROMANS, False)
    assert params["scout_reveals"] == [reveal(faction=rc.ROMANS, scouts=1)]


@pytest.mark.parametrize("profile", ["original", "second-edition"])
@pytest.mark.parametrize("scenario", [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
def test_gallia_togata_replacement_obeys_removal_only_stacking(profile, scenario):
    s = game(profile, scenario)
    execute_event(s, "A5" if scenario in rc.ARIOVISTUS_SCENARIOS else 5)
    s["event_params"] = {"replacements": [rep(rc.ROMANS, rc.ARVERNI, rc.AUXILIA,
                                              region=rc.CISALPINA)], "raid_actions": []}
    execute_event(s, 44, shaded=True)
    assert count_pieces(s, rc.CISALPINA, rc.ROMANS, rc.AUXILIA) == 2
    assert count_pieces(s, rc.CISALPINA, rc.ARVERNI, rc.WARBAND) == 0
    assert s["event_modifiers"]["card_44_placed"] == []
    assert not s["event_modifiers"].get("card_44a_command_regions")


@pytest.mark.parametrize("owner,kind,valid", [(rc.ROMANS, rc.AUXILIA, True),
                                               (rc.AEDUI, rc.WARBAND, False)])
@pytest.mark.parametrize("scenario", [rc.SCENARIO_GREAT_REVOLT, rc.SCENARIO_ARIOVISTUS])
def test_only_roman_scout_cohort_can_enter_activated_cisalpina(owner, kind, valid, scenario):
    s = game(scenario=scenario)
    execute_event(s, "A5" if scenario in rc.ARIOVISTUS_SCENARIOS else 5)
    place_piece(s, rc.UBII, rc.BELGAE, rc.WARBAND)
    s["event_params"] = {"replacements": [rep(destination=owner, to_kind=kind, region=rc.UBII)],
        "scout_moves": [{"from_region": rc.UBII, "to_region": rc.CISALPINA,
                         "faction": owner, "count": 1}]}
    if valid:
        assert play(s)["executed"]
        assert count_pieces(s, rc.CISALPINA, rc.ROMANS, rc.AUXILIA) == 4
    else:
        before = snapshot(s)
        with pytest.raises(ValueError): execute_event(s, 44)
        assert snapshot(s) == before


def test_ariovistus_cisalpina_may_receive_replacement_warbands():
    s = game("second-edition", rc.SCENARIO_ARIOVISTUS)
    place_piece(s, rc.CISALPINA, rc.ROMANS, rc.AUXILIA)
    s["event_params"] = {"replacements": [rep(rc.ROMANS, rc.GERMANS, rc.AUXILIA,
                                              region=rc.CISALPINA)]}
    execute_event(s, 44, shaded=True)
    assert count_pieces(s, rc.CISALPINA, rc.GERMANS, rc.WARBAND) == 1
    assert s["event_modifiers"]["card_44a_command_regions"] == [rc.CISALPINA]
