"""§4.5.1/A4.5.1: borrowed counters remain German while acting as Belgic."""
from copy import deepcopy
from io import StringIO

import pytest

from fs_bot.rules_consts import (
    ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS, WARBAND, LEADER, LEGION,
    AUXILIA, ALLY, HIDDEN, REVEALED, SCOUTED, AMBIORIX, BODUOGNATUS,
    ARIOVISTUS_LEADER, CAESAR, VERCINGETORIX, SCENARIO_PAX_GALLICA,
    SCENARIO_ARIOVISTUS, NERVII, MORINI, ATREBATES, TREVERI, MANDUBII,
    AEDUI_REGION, ARVERNI_REGION, SEQUANI, BELGIC_CONTROL, GERMANIC_CONTROL,
    TRIBE_NERVII,
)
from fs_bot.state.state_schema import build_initial_state
from fs_bot.state.serialize import encode
from fs_bot.board.pieces import (
    place_piece, count_pieces, count_pieces_by_state, get_available,
    get_effective_faction_pieces, move_piece, remove_piece, PieceError,
)
from fs_bot.board.control import refresh_all_control
from fs_bot.commands.sa_enlist import begin_borrow, end_borrow, BORROW_KEY, borrowed_count
from fs_bot.commands.common import CommandError
from fs_bot.engine.execute import execute_decision, _march_with_harassment
from fs_bot.battle.losses import calculate_losses, resolve_losses


def state(scenario=SCENARIO_PAX_GALLICA):
    st = build_initial_state(scenario, seed=5)
    st["resources"][BELGAE] = 10
    st["non_player_factions"] = {ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS}
    place_piece(st, NERVII, BELGAE, LEADER,
                leader_name=AMBIORIX if scenario == SCENARIO_PAX_GALLICA else BODUOGNATUS)
    return st


def plan(command, details, *, regions=(NERVII,), selected=None):
    ed = {"type": "borrow", "regions": list(regions)}
    if selected is not None:
        ed["warbands"] = selected
    return {"command": command, "sa": "Enlist", "sa_regions": list(regions),
            "details": dict(details, enlist=ed), "sa_timing": "before"}


@pytest.mark.parametrize("scenario", [SCENARIO_PAX_GALLICA, SCENARIO_ARIOVISTUS])
def test_borrow_control_view_preserves_physical_ownership_and_pools(scenario):
    st = state(scenario)
    place_piece(st, NERVII, GERMANS, WARBAND, 3)
    refresh_all_control(st)
    assert st["spaces"][NERVII]["control"] == GERMANIC_CONTROL
    physical = deepcopy(st["spaces"][NERVII]["pieces"])
    pools = deepcopy(st["available"])
    begin_borrow(st, plan("Rally", {}))
    assert count_pieces(st, NERVII, BELGAE, WARBAND) == 3
    assert count_pieces(st, NERVII, GERMANS, WARBAND) == 0
    assert st["spaces"][NERVII]["control"] == BELGIC_CONTROL
    assert st["spaces"][NERVII]["pieces"] == physical
    assert st["available"] == pools
    end_borrow(st)
    assert st["spaces"][NERVII]["control"] == GERMANIC_CONTROL
    assert count_pieces(st, NERVII, GERMANS, WARBAND) == 3


def test_borrowed_control_enables_belgic_ally_then_reverts():
    st = state()
    place_piece(st, NERVII, GERMANS, WARBAND, 3)
    action = plan("Rally", {"rally_plan": {"allies": [{"region": NERVII, "tribe": TRIBE_NERVII}]}})
    result = execute_decision(st, BELGAE, {"player_action": action})
    assert result["executed"] and result["sa_execution"]["executed"]
    assert st["tribes"][TRIBE_NERVII]["allied_faction"] == BELGAE
    assert st["spaces"][NERVII]["control"] == GERMANIC_CONTROL
    assert st["resources"][BELGAE] == 9
    assert BORROW_KEY not in st


@pytest.mark.parametrize("scenario", [SCENARIO_PAX_GALLICA, SCENARIO_ARIOVISTUS])
def test_rally_can_place_german_warband_from_german_pool(scenario):
    st = state(scenario)
    before = deepcopy(st["available"])
    action = plan("Rally", {"rally_plan": {"warbands": [
        {"region": NERVII, "warband_mix": {GERMANS: 1, BELGAE: 0}}]}})
    result = execute_decision(st, BELGAE, {"player_action": action})
    assert result["executed"]
    assert get_available(st, GERMANS, WARBAND) == before[GERMANS][WARBAND] - 1
    assert get_available(st, BELGAE, WARBAND) == before[BELGAE][WARBAND]
    assert count_pieces(st, NERVII, GERMANS, WARBAND) == 1
    assert count_pieces(st, NERVII, BELGAE, WARBAND) == 0


def test_ariovistus_counts_new_rally_warband_against_four_total():
    st = state(SCENARIO_ARIOVISTUS)
    place_piece(st, NERVII, GERMANS, WARBAND, 4)
    before = encode(st)
    result = execute_decision(st, BELGAE, {"player_action": plan("Rally", {
        "rally_plan": {"warbands": [{"region": NERVII, "warband_mix": {GERMANS: 1}}]}})})
    assert not result["executed"]
    assert encode(st) == before


@pytest.mark.parametrize("visibility, final", [(HIDDEN, HIDDEN), (REVEALED, HIDDEN), (SCOUTED, REVEALED)])
def test_march_keeps_german_identity_and_correct_visibility(visibility, final):
    st = state()
    place_piece(st, NERVII, GERMANS, WARBAND, 2, piece_state=visibility)
    action = plan("March", {"origins": [NERVII], "destinations": [TREVERI],
        "routes": {NERVII: [TREVERI]}, "groups": {NERVII: {WARBAND: 2, "german_warbands": 2}}})
    result = execute_decision(st, BELGAE, {"player_action": action})
    assert result["executed"] and not result["errors"]
    assert count_pieces_by_state(st, TREVERI, GERMANS, WARBAND, final) == 2
    assert count_pieces(st, TREVERI, BELGAE, WARBAND) == 0
    assert st["resources"][BELGAE] == 9
    assert BORROW_KEY not in st


@pytest.mark.parametrize("take_germans", [0, 1, 2])
def test_partial_march_allows_physical_owner_choice(take_germans):
    st = state()
    place_piece(st, NERVII, GERMANS, WARBAND, 2)
    place_piece(st, NERVII, BELGAE, WARBAND, 2)
    result = execute_decision(st, BELGAE, {"player_action": plan("March", {
        "origins": [NERVII], "destinations": [TREVERI], "routes": {NERVII: [TREVERI]},
        "groups": {NERVII: {WARBAND: 2, "german_warbands": take_germans}}})})
    assert result["executed"]
    assert count_pieces(st, TREVERI, GERMANS, WARBAND) == take_germans
    assert count_pieces(st, TREVERI, BELGAE, WARBAND) == 2 - take_germans


def test_raid_borrowed_hidden_warband_gains_belgic_resources():
    st = state()
    place_piece(st, NERVII, GERMANS, WARBAND, 1)
    result = execute_decision(st, BELGAE, {"player_action": plan("Raid", {
        "raid_plan": [{"region": NERVII, "target": None}]})})
    assert result["executed"]
    assert st["resources"][BELGAE] == 11
    assert count_pieces_by_state(st, NERVII, GERMANS, WARBAND, REVEALED) == 1


def test_borrowed_warbands_use_ambiorix_and_absorb_losses_before_belgae():
    st = state()
    place_piece(st, NERVII, BELGAE, WARBAND, 2)
    place_piece(st, NERVII, GERMANS, WARBAND, 2)
    place_piece(st, NERVII, ROMANS, AUXILIA, 1)
    german_pool = get_available(st, GERMANS, WARBAND)
    belgic_pool = get_available(st, BELGAE, WARBAND)
    begin_borrow(st, plan("Battle", {}))
    assert calculate_losses(st, NERVII, BELGAE, ROMANS) == 5  # Leader+4 WB.
    resolve_losses(st, NERVII, BELGAE, 2)
    end_borrow(st)
    assert count_pieces(st, NERVII, BELGAE, WARBAND) == 2
    assert count_pieces(st, NERVII, GERMANS, WARBAND) == 0
    assert get_available(st, GERMANS, WARBAND) == german_pool + 2
    assert get_available(st, BELGAE, WARBAND) == belgic_pool


def test_human_loss_choice_can_preserve_borrowed_german():
    st = state()
    place_piece(st, NERVII, BELGAE, WARBAND, 1)
    place_piece(st, NERVII, GERMANS, WARBAND, 1)
    begin_borrow(st, plan("Battle", {}))
    requests = []
    def choose(_st, faction, request):
        requests.append(request)
        return [(WARBAND, HIDDEN, BELGAE)]
    st["decision_agent"] = choose
    resolve_losses(st, NERVII, BELGAE, 1)
    assert (WARBAND, HIDDEN, GERMANS) in requests[0]["pieces"]
    end_borrow(st)
    assert count_pieces(st, NERVII, BELGAE, WARBAND) == 0
    assert count_pieces(st, NERVII, GERMANS, WARBAND) == 1


def test_scoped_borrow_ends_when_reactive_decision_interrupts():
    st = state()
    st["non_player_factions"] = set()
    place_piece(st, NERVII, GERMANS, WARBAND, 2)
    place_piece(st, NERVII, ROMANS, AUXILIA, 3)
    def pause(*args):
        raise EOFError
    st["decision_agent"] = pause
    before = encode({k: v for k, v in st.items() if k != "decision_agent"})
    with pytest.raises(EOFError):
        execute_decision(st, BELGAE, {"player_action": plan("Battle", {
            "battle_plan": [{"region": NERVII, "target": ROMANS}]})})
    assert BORROW_KEY not in st
    assert encode({k: v for k, v in st.items() if k != "decision_agent"}) == before


@pytest.mark.parametrize("count", [-1, True, 1.5, 5])
def test_bad_borrowed_counts_reject_before_mutation(count):
    st = state(SCENARIO_ARIOVISTUS)
    place_piece(st, NERVII, GERMANS, WARBAND, 5)
    before = encode(st)
    result = execute_decision(st, BELGAE, {"player_action": plan("Raid", {
        "raid_plan": [{"region": NERVII, "target": None}]}, selected={NERVII: {HIDDEN: count}})})
    assert not result["executed"] and encode(st) == before


def test_ariovistus_forbids_borrow_in_ariovistus_region():
    st = state(SCENARIO_ARIOVISTUS)
    place_piece(st, NERVII, GERMANS, LEADER, leader_name=ARIOVISTUS_LEADER)
    place_piece(st, NERVII, GERMANS, WARBAND, 1)
    with pytest.raises(CommandError, match="Ariovistus"):
        begin_borrow(st, plan("Raid", {}))
    assert BORROW_KEY not in st


def test_multiple_regions_share_ariovistus_budget():
    st = state(SCENARIO_ARIOVISTUS)
    place_piece(st, NERVII, GERMANS, WARBAND, 2)
    place_piece(st, TREVERI, GERMANS, WARBAND, 3)
    with pytest.raises(CommandError, match="at most"):
        begin_borrow(st, plan("Raid", {}, regions=(NERVII, TREVERI)))
    assert BORROW_KEY not in st


def test_invalid_second_piece_removal_cannot_half_apply():
    st = state()
    place_piece(st, NERVII, GERMANS, WARBAND, 1)
    place_piece(st, NERVII, BELGAE, WARBAND, 1)
    begin_borrow(st, plan("Battle", {}))
    before = encode(st)
    with pytest.raises(PieceError):
        remove_piece(st, NERVII, BELGAE, WARBAND, 3)
    assert encode(st) == before
    end_borrow(st)


def test_effective_german_defender_excludes_borrowed_warbands():
    st = state(SCENARIO_ARIOVISTUS)
    place_piece(st, NERVII, GERMANS, WARBAND, 5)
    begin_borrow(st, plan("Battle", {}, selected={NERVII: {HIDDEN: 2}}))
    assert count_pieces(st, NERVII, GERMANS, WARBAND) == 3
    assert calculate_losses(st, NERVII, GERMANS, BELGAE, is_counterattack=True) == 1
    end_borrow(st)


@pytest.mark.parametrize("faction, leader, max_steps", [
    (BELGAE, None, 1), (AEDUI, None, 1), (GERMANS, None, 1),
    (ROMANS, None, 2), (ROMANS, CAESAR, 3), (ARVERNI, None, 1),
    (ARVERNI, VERCINGETORIX, 2)])
def test_command_march_distance_checked_before_payment_or_flip(faction, leader, max_steps):
    st = build_initial_state(SCENARIO_PAX_GALLICA, seed=9)
    st["resources"][faction] = 10
    piece = AUXILIA if faction == ROMANS else WARBAND
    place_piece(st, NERVII, faction, piece, 2, piece_state=REVEALED)
    if leader:
        place_piece(st, NERVII, faction, LEADER, leader_name=leader)
    path = [TREVERI, SEQUANI, AEDUI_REGION, MANDUBII][:max_steps + 1]
    before = encode(st)
    from fs_bot.engine.execute import _execute_march
    result = _execute_march(st, faction, {"details": {
        "origins": [NERVII], "destinations": [path[-1]], "routes": {NERVII: path}}})
    assert not result["executed"] and encode(st) == before


def test_leader_left_behind_does_not_extend_march_distance():
    st = build_initial_state(SCENARIO_PAX_GALLICA, seed=9)
    place_piece(st, NERVII, ROMANS, LEADER, leader_name=CAESAR)
    place_piece(st, NERVII, ROMANS, AUXILIA, 2, piece_state=REVEALED)
    before = encode(st)
    with pytest.raises(CommandError, match="movement allowance"):
        _march_with_harassment(st, ROMANS, NERVII, [TREVERI, SEQUANI, AEDUI_REGION],
                               group_cap={AUXILIA: 2, LEADER: False})
    assert encode(st) == before


def test_borrowed_only_region_preserves_unfiltered_total():
    st = state()
    place_piece(st, TREVERI, GERMANS, WARBAND, 2)
    assert not st["spaces"][TREVERI].get("pieces", {}).get(BELGAE)
    before = count_pieces(st, TREVERI)
    begin_borrow(st, plan("March", {}, regions=(TREVERI,)))
    assert count_pieces(st, TREVERI) == before
    assert count_pieces(st, TREVERI, piece_type=WARBAND) == 2
    end_borrow(st)


def test_automatic_march_route_respects_the_carried_leader():
    from fs_bot.engine.execute import _collect_march_moves
    st = state()
    place_piece(st, NERVII, ROMANS, LEADER, leader_name=CAESAR)
    place_piece(st, NERVII, ROMANS, AUXILIA, 2)
    details = {"origins": [NERVII], "destinations": [ARVERNI_REGION],
               "groups": {NERVII: {AUXILIA: 2, LEADER: False}}}
    moves, deferred = _collect_march_moves(st, ROMANS, {"details": details})
    assert moves == [] and deferred == [NERVII]
    details["groups"][NERVII][LEADER] = True
    moves, deferred = _collect_march_moves(st, ROMANS, {"details": details})
    assert len(moves) == 1 and len(moves[0]["path"]) == 3
    assert deferred == []


@pytest.mark.parametrize("order", ["sa_first", "enlist_command_first"])
def test_cli_collects_borrowed_command_in_either_selection_order(monkeypatch, order):
    from fs_bot.cli import human_plan as hp
    from fs_bot.engine.game_engine import ACTION_COMMAND_SA
    st = state()
    place_piece(st, NERVII, GERMANS, WARBAND, 1)
    asked = []

    def choose(stdin, stdout, title, options, **kwargs):
        values = [value for _, value in options]
        asked.append(title)
        for value in (order, "Raid", "Enlist", "borrow"):
            if value in values:
                return value
        return values[0]

    monkeypatch.setattr(hp, "prompt_choice", choose)
    monkeypatch.setattr(hp, "_pick_regions", lambda *a, **kw: [NERVII])

    def collect(sim, faction, command, *args, **kwargs):
        assert command == "Raid"
        assert count_pieces(sim, NERVII, BELGAE, WARBAND) == 1
        return {"command": command, "sa": "No SA", "regions": [NERVII],
                "sa_regions": [], "details": {"raid_plan": [{"region": NERVII, "target": None}]}}

    monkeypatch.setattr(hp, "_collect_command_plan", collect)
    before = encode(st)
    action = hp._collect_command(st, BELGAE, ACTION_COMMAND_SA, StringIO(), StringIO())
    assert encode(st) == before
    result = execute_decision(st, BELGAE, {"player_action": action})
    assert result["executed"] and result["sa_execution"]["executed"]
    assert count_pieces_by_state(st, NERVII, GERMANS, WARBAND, REVEALED) == 1
    if order == "sa_first":
        assert asked.index("Which Special Activity?") < asked.index("Which accompanying Command?")
    else:
        assert "Which Special Activity?" not in asked


def test_cli_free_ariovistus_battle_selects_visibility(monkeypatch):
    from fs_bot.cli import human_plan as hp
    st = state(SCENARIO_ARIOVISTUS)
    place_piece(st, NERVII, GERMANS, WARBAND, 3, piece_state=HIDDEN)
    place_piece(st, NERVII, GERMANS, WARBAND, 2, piece_state=REVEALED)
    place_piece(st, NERVII, AEDUI, WARBAND, 1)

    def choose(stdin, stdout, title, options, **kwargs):
        values = [value for _, value in options]
        if title.startswith("Enlist"):
            return "german_battle"
        if "Hidden German" in title:
            return 0
        if "Revealed German" in title:
            return 2
        if "Target" in title:
            return AEDUI
        return values[0]

    monkeypatch.setattr(hp, "prompt_choice", choose)
    _, details = hp._collect_enlist(st, BELGAE, StringIO(), StringIO())
    assert details["enlist"]["warbands"] == {HIDDEN: 0, REVEALED: 2, SCOUTED: 0}


def test_cli_free_raid_collects_two_separate_actions(monkeypatch):
    from fs_bot.cli import human_plan as hp
    st = state(SCENARIO_ARIOVISTUS)
    place_piece(st, NERVII, GERMANS, WARBAND, 2)
    place_piece(st, NERVII, AEDUI, WARBAND, 1)

    def choose(stdin, stdout, title, options, **kwargs):
        if title.startswith("Enlist"):
            return "german_raid"
        if "how many" in title:
            return 2
        if "Raid 1" in title:
            return AEDUI
        if "Raid 2" in title:
            return None
        return options[0][1]

    monkeypatch.setattr(hp, "prompt_choice", choose)
    _, details = hp._collect_enlist(st, BELGAE, StringIO(), StringIO())
    assert details["enlist"]["actions"] == [{"type": "steal", "target": AEDUI}, {"type": "gain"}]


def test_base_borrow_treats_all_german_warbands_in_selected_region():
    st = state()
    place_piece(st, NERVII, GERMANS, WARBAND, 2)
    before = encode(st)
    with pytest.raises(CommandError, match="all German Warbands"):
        begin_borrow(st, plan("Raid", {}, selected={NERVII: {HIDDEN: 1}}))
    assert encode(st) == before


def test_germans_cannot_remove_belgic_pieces_by_owner_override():
    st = state()
    place_piece(st, NERVII, BELGAE, WARBAND, 1)
    place_piece(st, NERVII, GERMANS, WARBAND, 1)
    begin_borrow(st, plan("Battle", {}))
    before = encode(st)
    with pytest.raises(PieceError, match="physical owner"):
        remove_piece(st, NERVII, GERMANS, WARBAND, physical_owner=BELGAE)
    assert encode(st) == before
    end_borrow(st)
