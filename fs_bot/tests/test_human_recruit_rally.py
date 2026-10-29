"""Printed placement quantities and Vercingetorix's two Rally orders."""

from copy import deepcopy
from io import StringIO

import pytest

from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import count_pieces, get_available, place_piece
from fs_bot.cli.human_plan import _collect_rally, _collect_recruit
from fs_bot.cli.menus import set_board_hook
from fs_bot.engine.execute import execute_decision
from fs_bot.rules_consts import (
    AEDUI, AEDUI_REGION, ALLY, AMBIORIX, ARVERNI, ARVERNI_REGION, AUXILIA,
    BELGAE, BITURIGES, CAESAR, CITADEL, FORT, GERMANS, LEADER, PROVINCIA, ROMANS,
    SCENARIO_ARIOVISTUS, SCENARIO_PAX_GALLICA, SEQUANI, SUCCESSOR,
    SUGAMBRI, TREVERI, TRIBE_AEDUI, TRIBE_ARVERNI, TRIBE_BITURIGES, TRIBE_SEQUANI, TRIBE_SUGAMBRI,
    TRIBE_TREVERI,
    VERCINGETORIX,
    WARBAND,
)
from fs_bot.state.state_schema import build_initial_state, validate_state


def state(scenario=SCENARIO_PAX_GALLICA):
    st = build_initial_state(scenario, seed=18)
    st["non_player_factions"] = set()
    st["resources"].update({ROMANS: 20, ARVERNI: 20, AEDUI: 20, GERMANS: 20})
    return st


def ally(st, region, faction, tribe):
    place_piece(st, region, faction, ALLY)
    st["tribes"][tribe]["allied_faction"] = faction
    refresh_all_control(st)


def execute(st, faction, details, command="Rally"):
    result = execute_decision(st, faction, {"player_action": {
        "command": command, "regions": [], "sa": "No SA", "sa_regions": [],
        "details": details}})
    assert result["executed"], result
    assert not result.get("errors"), result
    assert validate_state(st) == []
    return result


def unchanged(st, before):
    assert st["rng"].getstate() == before["rng"].getstate()
    assert {k: v for k, v in st.items() if k != "rng"} == {
        k: v for k, v in before.items() if k != "rng"}


def test_recruit_real_menu_partial_count_and_board_inspection():
    st = state()
    place_piece(st, PROVINCIA, ROMANS, FORT)
    place_piece(st, PROVINCIA, ROMANS, LEADER, leader_name=CAESAR)
    before = deepcopy(st)
    out, boards = StringIO(), []
    set_board_hook(lambda: boards.append("board"))
    try:
        # 3 is the third quantity option: exactly1 of max3.
        plan = _collect_recruit(st, ROMANS, StringIO(
            f"{PROVINCIA}\nAuxilia\nboard\n3\n"), out, single=True)
    finally:
        set_board_hook(None)
    assert boards == ["board"]
    assert plan["recruit_plan"][0]["count"] == 1
    unchanged(st, before)
    execute(st, ROMANS, plan, "Recruit")
    assert count_pieces(st, PROVINCIA, ROMANS, AUXILIA) == 1


@pytest.mark.parametrize("count,answer", [(0, "0"), (1, "2")])
def test_rally_allows_below_maximum_and_zero(count, answer):
    st = state()
    ally(st, ARVERNI_REGION, ARVERNI, TRIBE_ARVERNI)
    before = deepcopy(st)
    plan = _collect_rally(st, ARVERNI, StringIO(
        f"{ARVERNI_REGION}\nWarbands\n{answer}\n"), StringIO(), single=True)
    assert plan["rally_plan"]["steps"][0]["count"] == count
    unchanged(st, before)
    execute(st, ARVERNI, plan)
    assert count_pieces(st, ARVERNI_REGION, ARVERNI, WARBAND) == count
    assert st["resources"][ARVERNI] == 19


@pytest.mark.parametrize("first", ["place_ally", "place_warbands"])
def test_vercingetorix_combined_rally_preserves_both_orders(first):
    st = state()
    place_piece(st, ARVERNI_REGION, ARVERNI, LEADER, leader_name=VERCINGETORIX)
    refresh_all_control(st)
    if first == "place_ally":
        # New Ally raises the later Warband maximum from2 to3.
        answers = f"{ARVERNI_REGION}\nan Ally at a Subdued Tribe\n{TRIBE_ARVERNI}\nWarbands\n1\n"
        expected = 3
    else:
        answers = f"{ARVERNI_REGION}\nWarbands\n1\nan Ally at a Subdued Tribe\n{TRIBE_ARVERNI}\n"
        expected = 2
    before = deepcopy(st)
    plan = _collect_rally(st, ARVERNI, StringIO(answers), StringIO(), single=True)
    steps = plan["rally_plan"]["steps"]
    assert steps[0]["action"] == first
    assert {step["action"] for step in steps} == {"place_ally", "place_warbands"}
    unchanged(st, before)
    execute(st, ARVERNI, plan)
    assert count_pieces(st, ARVERNI_REGION, ARVERNI, WARBAND) == expected
    assert st["resources"][ARVERNI] == 19


@pytest.mark.parametrize("first", ["place_citadel", "place_warbands"])
def test_vercingetorix_citadel_combination(first):
    st = state()
    ally(st, ARVERNI_REGION, ARVERNI, TRIBE_ARVERNI)
    place_piece(st, ARVERNI_REGION, ARVERNI, LEADER, leader_name=VERCINGETORIX)
    citadel = f"a Citadel (replace your Ally at a City)\n{TRIBE_ARVERNI}\n"
    troops = "Warbands\n2\n"  # Choose2 of3.
    answers = f"{ARVERNI_REGION}\n" + (citadel + troops if first == "place_citadel" else troops + citadel)
    plan = _collect_rally(st, ARVERNI, StringIO(answers), StringIO(), single=True)
    assert plan["rally_plan"]["steps"][0]["action"] == first
    execute(st, ARVERNI, plan)
    assert count_pieces(st, ARVERNI_REGION, ARVERNI, CITADEL) == 1
    assert count_pieces(st, ARVERNI_REGION, ARVERNI, ALLY) == 0
    assert count_pieces(st, ARVERNI_REGION, ARVERNI, WARBAND) == 2
    assert st["resources"][ARVERNI] == 19


def test_successor_does_not_offer_second_rally_option():
    st = state()
    ally(st, ARVERNI_REGION, ARVERNI, TRIBE_ARVERNI)
    place_piece(st, ARVERNI_REGION, ARVERNI, LEADER, leader_name=SUCCESSOR)
    out = StringIO()
    plan = _collect_rally(st, ARVERNI, StringIO(
        f"{ARVERNI_REGION}\nWarbands\n1\n"), out, single=True)
    assert len(plan["rally_plan"]["steps"]) == 1
    assert "Finish this Region" not in out.getvalue()


def test_later_region_quantity_uses_remaining_shared_pool():
    st = state()
    ally(st, AEDUI_REGION, AEDUI, TRIBE_AEDUI)
    ally(st, SEQUANI, AEDUI, TRIBE_SEQUANI)
    place_piece(st, PROVINCIA, AEDUI, WARBAND, get_available(st, AEDUI, WARBAND) - 1)
    before = deepcopy(st)
    plan = _collect_rally(st, AEDUI, StringIO(
        f"{AEDUI_REGION}\n{SEQUANI}\n(done)\nWarbands\n1\nWarbands\n0\n"),
        StringIO(), single=False)
    assert [e["count"] for e in plan["rally_plan"]["steps"]] == [1, 0]
    unchanged(st, before)
    execute(st, AEDUI, plan)
    assert count_pieces(st, AEDUI_REGION, AEDUI, WARBAND) == 1
    assert count_pieces(st, SEQUANI, AEDUI, WARBAND) == 0


def test_german_home_bonus_is_in_total_not_an_unexpected_extra():
    st = state(SCENARIO_ARIOVISTUS)
    plan = _collect_rally(st, GERMANS, StringIO(
        f"{SUGAMBRI}\nWarbands\n1\n"), StringIO(), single=True)
    assert plan["rally_plan"]["steps"][0]["count"] == 1
    execute(st, GERMANS, plan)
    assert count_pieces(st, SUGAMBRI, GERMANS, WARBAND) == 1


def test_enlist_base_ally_then_explicit_warband_count():
    from fs_bot.cli.human_plan import _collect_enlist
    from fs_bot.commands.enlist_free import execute_free_enlist
    st = state()
    place_piece(st, SUGAMBRI, BELGAE, LEADER, leader_name=AMBIORIX)
    place_piece(st, SUGAMBRI, GERMANS, WARBAND, 3)
    refresh_all_control(st)
    before = deepcopy(st)
    regions, details = _collect_enlist(st, BELGAE, StringIO(
        f"Rally\n{SUGAMBRI}\nan Ally\n{TRIBE_SUGAMBRI}\n1\n"), StringIO())
    assert regions == [SUGAMBRI]
    assert details["enlist"]["count"] == 1
    unchanged(st, before)
    execute_free_enlist(st, details["enlist"])
    assert count_pieces(st, SUGAMBRI, GERMANS, ALLY) == 1
    assert count_pieces(st, SUGAMBRI, GERMANS, WARBAND) == 4


def test_belgae_can_choose_own_citadel_at_an_allied_city():
    st = state()
    st["resources"][BELGAE] = 10
    ally(st, BITURIGES, BELGAE, TRIBE_BITURIGES)
    plan = _collect_rally(st, BELGAE, StringIO(
        f"{BITURIGES}\na Citadel (replace your Ally at a City)\n{TRIBE_BITURIGES}\n"),
        StringIO(), single=True)
    assert plan["rally_plan"]["steps"][0]["action"] == "place_citadel"
    execute(st, BELGAE, plan)
    assert count_pieces(st, BITURIGES, BELGAE, CITADEL) == 1
    assert count_pieces(st, BITURIGES, BELGAE, ALLY) == 0


def test_physical_owner_choice_preserves_later_native_recruit_quantity():
    from fs_bot.cards.card_effects import execute_event
    from fs_bot.engine.diviciacus import force_scope
    st = state()
    place_piece(st, SEQUANI, ROMANS, LEADER, leader_name=CAESAR)
    place_piece(st, SEQUANI, ROMANS, AUXILIA)
    place_piece(st, SEQUANI, AEDUI, WARBAND)
    place_piece(st, PROVINCIA, ROMANS, FORT)
    place_piece(st, PROVINCIA, ROMANS, AUXILIA, get_available(st, ROMANS, AUXILIA) - 1)
    execute_event(st, 38, shaded=False)
    before = deepcopy(st)
    with force_scope(st, ROMANS, [SEQUANI]):
        plan = _collect_recruit(st, ROMANS, StringIO(
            f"{SEQUANI}\n{PROVINCIA}\n(done)\nAuxilia\n1\n1\nAuxilia\n1\n"),
            StringIO(), single=False)
    unchanged(st, before)
    first, second = plan["recruit_plan"]
    assert first["placement_owners"] == {ROMANS: 0, AEDUI: 1}
    assert second["count"] == 1  # Native Auxilia retained for this later Region.
    original = count_pieces(st, PROVINCIA, ROMANS, AUXILIA)
    with force_scope(st, ROMANS, [SEQUANI]):
        execute(st, ROMANS, plan, "Recruit")
    assert count_pieces(st, SEQUANI, AEDUI, WARBAND) == 2
    assert count_pieces(st, PROVINCIA, ROMANS, AUXILIA) == original + 1


def test_recruit_region_listing_does_not_consume_live_supply_consent():
    from fs_bot.cards.card_effects import execute_event
    st = state()
    ally(st, SEQUANI, ROMANS, TRIBE_SEQUANI)
    place_piece(st, SEQUANI, AEDUI, WARBAND, 4)
    refresh_all_control(st)
    execute_event(st, 13, shaded=True)

    def unexpected(*args):
        pytest.fail("Region preview consulted a live decision agent")

    st["decision_agent"] = unexpected
    before = deepcopy(st)
    plan = _collect_recruit(st, ROMANS, StringIO(
        f"{SEQUANI}\nAuxilia\n1\n"), StringIO(), single=True)
    assert plan["recruit_plan"][0]["region"] == SEQUANI
    unchanged(st, before)


def test_borrowed_enlist_does_not_require_warband_base_for_ally_option():
    from fs_bot.commands.sa_enlist import begin_borrow
    st = state()
    st["resources"][BELGAE] = 10
    place_piece(st, TREVERI, BELGAE, LEADER, leader_name=AMBIORIX)
    place_piece(st, TREVERI, BELGAE, WARBAND, 4)
    place_piece(st, TREVERI, GERMANS, WARBAND)
    refresh_all_control(st)
    begin_borrow(st, {"details": {"enlist": {"type": "borrow", "regions": [TREVERI]}}})
    before = deepcopy(st)
    plan = _collect_rally(st, BELGAE, StringIO(
        f"{TREVERI}\nan Ally at a Subdued Tribe\n{TRIBE_TREVERI}\n"),
        StringIO(), single=True)
    assert plan["rally_plan"]["steps"] == [
        {"region": TREVERI, "action": "place_ally", "tribe": TRIBE_TREVERI}]
    unchanged(st, before)
