"""§1.4.1: own physical counters, exact Tribes, and atomic human choices."""

import io
import pytest

from fs_bot import rules_consts as rc
from fs_bot.board import pieces
from fs_bot.battle.combined import COMBINED_KEY
from fs_bot.battle.excluded_leader import EXCLUDED_LEADER_KEY
from fs_bot.commands.sa_enlist import BORROW_KEY, FREE_FORCE_KEY
from fs_bot.engine.diviciacus import KEY as DIVICIACUS_KEY
from fs_bot.engine import voluntary_removal as removal
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.state.serialize import encode


def state(scenario=rc.SCENARIO_GREAT_REVOLT):
    return build_initial_state(scenario, seed=73)


def pick(board, faction, *, count=1, cohorts=None, **fields):
    matches = [choice for choice in removal.options(board, faction, cohorts=cohorts)
               if all(choice.get(key) == value for key, value in fields.items())]
    assert len(matches) == 1, matches
    return removal.operation(matches[0], count)


def apply(board, faction, *operations, cohorts=None):
    return removal.apply_response(board, removal.make_request(board, faction,
        cohorts=cohorts), {"operations": list(operations)}, cohorts=cohorts)


def allied(board, faction, tribe, *, citadel=False):
    region = rc.TRIBE_TO_REGION[tribe]
    pieces.place_piece(board, region, faction, rc.CITADEL if citadel else rc.ALLY)
    board["tribes"][tribe]["allied_faction"] = faction
    return region


@pytest.mark.parametrize("visibility", (rc.HIDDEN, rc.REVEALED, rc.SCOUTED))
def test_remove_mobile_counters_preserves_visibility_inventory_and_control(visibility):
    board = state()
    pieces.place_piece(board, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 3,
                       piece_state=visibility)
    pieces.place_piece(board, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 1)
    before = pieces.get_available(board, rc.AEDUI, rc.WARBAND)
    apply(board, rc.AEDUI, pick(board, rc.AEDUI, piece_type=rc.WARBAND,
                               piece_state=visibility, count=2))
    assert pieces.count_pieces_by_state(board, rc.CARNUTES, rc.AEDUI,
                                        rc.WARBAND, visibility) == 1
    assert pieces.get_available(board, rc.AEDUI, rc.WARBAND) == before + 2
    assert board["spaces"][rc.CARNUTES]["control"] == rc.NO_CONTROL
    assert validate_state(board) == []


def test_legions_return_to_track_without_counting_as_fallen_or_removed():
    board = state()
    pieces.place_piece(board, rc.CARNUTES, rc.ROMANS, rc.LEGION, 3,
                       from_legions_track=True)
    original_track = sum(board["legions_track"].values())
    apply(board, rc.ROMANS, pick(board, rc.ROMANS, piece_type=rc.LEGION, count=2))
    assert sum(board["legions_track"].values()) == original_track + 2
    assert board["fallen_legions"] == board["removed_legions"] == 0
    assert validate_state(board) == []


def test_forts_include_only_the_removable_fort():
    board = state()
    pieces.place_piece(board, rc.PROVINCIA, rc.ROMANS, rc.FORT)
    pieces.place_piece(board, rc.CARNUTES, rc.ROMANS, rc.FORT)
    choices = removal.options(board, rc.ROMANS)
    assert [c["region"] for c in choices if c["piece_type"] == rc.FORT] == [rc.CARNUTES]
    before = encode(board)
    with pytest.raises(ValueError, match="own physical"):
        apply(board, rc.ROMANS, {"action": "remove", "region": rc.PROVINCIA,
                                 "piece_type": rc.FORT, "count": 1})
    assert encode(board) == before
    apply(board, rc.ROMANS, pick(board, rc.ROMANS, piece_type=rc.FORT))
    assert pieces.count_pieces(board, rc.PROVINCIA, rc.ROMANS, rc.FORT) == 1
    assert validate_state(board) == []


def test_named_leader_is_selectable_even_when_excluded_from_battle():
    board = state()
    pieces.place_piece(board, rc.CARNUTES, rc.ROMANS, rc.LEADER,
                       leader_name=rc.CAESAR)
    board[EXCLUDED_LEADER_KEY] = {"faction": rc.ROMANS, "regions": [rc.CARNUTES]}
    assert pieces.get_leader_in_region(board, rc.CARNUTES, rc.ROMANS) is None
    apply(board, rc.ROMANS, pick(board, rc.ROMANS, piece_type=rc.LEADER))
    assert pieces.get_available(board, rc.ROMANS, rc.LEADER) == 1
    assert validate_state(board) == []


def test_diviciacus_is_removed_from_play_not_to_available():
    board = state(rc.SCENARIO_ARIOVISTUS)
    pieces.place_piece(board, rc.CARNUTES, rc.AEDUI, rc.LEADER,
                       leader_name=rc.DIVICIACUS)
    board["diviciacus_in_play"] = True
    apply(board, rc.AEDUI, pick(board, rc.AEDUI, piece_type=rc.LEADER))
    assert not board["diviciacus_in_play"]
    assert board["removed_pieces"][rc.AEDUI][rc.LEADER] == 1
    assert pieces.get_available(board, rc.AEDUI, rc.LEADER) == 0
    assert validate_state(board) == []


def test_germanic_settlement_and_leader_can_be_removed():
    board = state(rc.SCENARIO_ARIOVISTUS)
    pieces.place_piece(board, rc.CARNUTES, rc.GERMANS, rc.SETTLEMENT)
    pieces.place_piece(board, rc.CARNUTES, rc.GERMANS, rc.LEADER,
                       leader_name=rc.ARIOVISTUS_LEADER)
    apply(board, rc.GERMANS,
          pick(board, rc.GERMANS, piece_type=rc.SETTLEMENT),
          pick(board, rc.GERMANS, piece_type=rc.LEADER))
    assert pieces.get_available(board, rc.GERMANS, rc.SETTLEMENT) == 6
    assert pieces.get_available(board, rc.GERMANS, rc.LEADER) == 1
    assert validate_state(board) == []


def test_remove_exact_ally_does_not_clear_neighboring_city_citadel():
    board = state()
    region = allied(board, rc.AEDUI, rc.TRIBE_CARNUTES, citadel=True)
    allied(board, rc.AEDUI, rc.TRIBE_AULERCI)
    apply(board, rc.AEDUI, pick(board, rc.AEDUI, piece_type=rc.ALLY,
                               tribe=rc.TRIBE_AULERCI))
    assert board["tribes"][rc.TRIBE_AULERCI]["allied_faction"] is None
    assert board["tribes"][rc.TRIBE_CARNUTES]["allied_faction"] == rc.AEDUI
    assert pieces.count_pieces(board, region, rc.AEDUI, rc.CITADEL) == 1
    assert validate_state(board) == []


def test_downgrade_retains_exact_city_alliance_and_other_ally():
    board = state()
    region = allied(board, rc.AEDUI, rc.TRIBE_CARNUTES, citadel=True)
    allied(board, rc.AEDUI, rc.TRIBE_AULERCI)
    effects = apply(board, rc.AEDUI, pick(board, rc.AEDUI,
                    action="downgrade", tribe=rc.TRIBE_CARNUTES))
    assert effects[0]["replacement_placed"] is True
    assert pieces.count_pieces(board, region, rc.AEDUI, rc.CITADEL) == 0
    assert pieces.count_pieces(board, region, rc.AEDUI, rc.ALLY) == 2
    assert board["tribes"][rc.TRIBE_CARNUTES]["allied_faction"] == rc.AEDUI
    assert board["tribes"][rc.TRIBE_AULERCI]["allied_faction"] == rc.AEDUI
    assert validate_state(board) == []


def exhaust_allies(board, faction):
    for tribe in board["tribes"]:
        if pieces.get_available(board, faction, rc.ALLY) == 0:
            break
        if board["tribes"][tribe]["allied_faction"] is None:
            allied(board, faction, tribe)


def test_downgrade_without_available_replacement_removes_original_piece():
    board = state()
    region = allied(board, rc.AEDUI, rc.TRIBE_CARNUTES, citadel=True)
    exhaust_allies(board, rc.AEDUI)
    effects = apply(board, rc.AEDUI, pick(board, rc.AEDUI,
                    action="downgrade", tribe=rc.TRIBE_CARNUTES))
    assert effects[0]["replacement_placed"] is False
    assert board["tribes"][rc.TRIBE_CARNUTES]["allied_faction"] is None
    assert pieces.count_pieces(board, region, rc.AEDUI, rc.CITADEL) == 0
    assert validate_state(board) == []


def test_ordered_batch_can_reclaim_ally_before_downgrading_citadel():
    board = state()
    allied(board, rc.AEDUI, rc.TRIBE_CARNUTES, citadel=True)
    exhaust_allies(board, rc.AEDUI)
    disc = next(c for c in removal.options(board, rc.AEDUI)
                if c["piece_type"] == rc.ALLY)
    effects = apply(board, rc.AEDUI, removal.operation(disc), pick(board, rc.AEDUI,
                      action="downgrade", tribe=rc.TRIBE_CARNUTES))
    assert effects[-1]["replacement_placed"] is True
    assert board["tribes"][disc["tribe"]]["allied_faction"] is None
    assert board["tribes"][rc.TRIBE_CARNUTES]["allied_faction"] == rc.AEDUI
    assert validate_state(board) == []


def test_colony_is_an_exact_selectable_tribe():
    board = state()
    from fs_bot.cards.card_effects import execute_event
    pieces.place_piece(board, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    board["executing_faction"] = rc.ROMANS
    board["event_params"] = {"region": rc.CARNUTES}
    execute_event(board, 71)
    colony = next(t for t in board["tribes"] if t not in rc.TRIBE_TO_REGION)
    apply(board, rc.ROMANS, pick(board, rc.ROMANS, piece_type=rc.ALLY, tribe=colony))
    assert board["tribes"][colony]["allied_faction"] is None
    assert board["markers"][rc.CARNUTES][rc.MARKER_COLONY]
    assert validate_state(board) == []


@pytest.mark.parametrize("scenario,faction", [
    (rc.SCENARIO_GREAT_REVOLT, rc.GERMANS),
    (rc.SCENARIO_ARIOVISTUS, rc.ARVERNI),
])
def test_game_run_factions_never_have_voluntary_removal(scenario, faction):
    board = state(scenario)
    pieces.place_piece(board, rc.CARNUTES, faction, rc.WARBAND)
    assert removal.make_request(board, faction) is None


def test_nonplayer_default_is_not_voluntary_removal():
    board = state()
    pieces.place_piece(board, rc.CARNUTES, rc.AEDUI, rc.WARBAND)
    board["non_player_factions"] = {rc.AEDUI}
    assert removal.options(board, rc.AEDUI) == []
    with pytest.raises(ValueError, match="authorized player"):
        removal.apply_response(board, {"kind": removal.KIND, "faction": rc.AEDUI},
                               {"done": True})


@pytest.mark.parametrize("response", [
    None, {}, {"done": 1}, {"done": True, "operations": []},
    {"use_default": True, "faction": rc.ROMANS}, {"operations": []},
])
def test_malformed_responses_are_pure(response):
    board = state()
    pieces.place_piece(board, rc.CARNUTES, rc.AEDUI, rc.WARBAND)
    request = removal.make_request(board, rc.AEDUI)
    before = encode(board)
    with pytest.raises(ValueError):
        removal.apply_response(board, request, response)
    assert encode(board) == before


@pytest.mark.parametrize("bad", [True, 0, -1, 1.5, "1", 3])
def test_invalid_later_operation_rolls_back_entire_batch_and_rng(bad):
    board = state()
    pieces.place_piece(board, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 2)
    op = pick(board, rc.AEDUI, piece_type=rc.WARBAND)
    request = removal.make_request(board, rc.AEDUI)
    before = encode(board)
    with pytest.raises(ValueError):
        removal.apply_response(board, request,
            {"operations": [op, dict(op, count=bad)]})
    assert encode(board) == before


def test_pure_preview_and_default_never_call_agent_or_consume_rng():
    board = state()
    pieces.place_piece(board, rc.CARNUTES, rc.AEDUI, rc.WARBAND)
    class Agent:
        def __deepcopy__(self, memo):
            raise AssertionError("agent copied")
        def __call__(self, *args):
            raise AssertionError("agent consulted")
    agent = Agent()
    board["decision_agent"] = agent
    before = encode({k: v for k, v in board.items() if k != "decision_agent"})
    request = removal.make_request(board, rc.AEDUI)
    op = pick(board, rc.AEDUI, piece_type=rc.WARBAND)
    removal.validate_response(board, request, {"operations": [op]})
    assert removal.apply_response(board, request, {"use_default": True}) == []
    assert removal.apply_response(board, request, {"done": True}) == []
    assert encode({k: v for k, v in board.items() if k != "decision_agent"}) == before
    assert board["decision_agent"] is agent


def test_unexpected_live_failure_restores_board_rng_and_agent(monkeypatch):
    board = state()
    pieces.place_piece(board, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 2)
    op = pick(board, rc.AEDUI)
    request = removal.make_request(board, rc.AEDUI)
    agent = object()
    board["decision_agent"] = agent
    before = encode({k: v for k, v in board.items() if k != "decision_agent"})
    real_remove = pieces._remove_piece_inner
    calls = 0
    def failing_remove(current, *args, **kwargs):
        nonlocal calls
        calls += 1
        real_remove(current, *args, **kwargs)
        if calls == 4:  # Two successful preview operations, then the live batch.
            current["rng"].random()
            raise RuntimeError("interrupted physical operation")
    monkeypatch.setattr(pieces, "_remove_piece_inner", failing_remove)
    with pytest.raises(RuntimeError, match="interrupted"):
        removal.apply_response(board, request, {"operations": [op, op]})
    assert encode({k: v for k, v in board.items() if k != "decision_agent"}) == before
    assert board["decision_agent"] is agent


@pytest.mark.parametrize("loan_kind", ["diviciacus", "enlist", "free_force"])
@pytest.mark.parametrize("remove_lent", [False, True])
def test_owner_selects_lent_or_resident_counter_and_updates_exact_ledger(loan_kind, remove_lent):
    board = state(rc.SCENARIO_ARIOVISTUS)
    owner = rc.AEDUI if loan_kind == "diviciacus" else rc.GERMANS
    pieces.place_piece(board, rc.CARNUTES, owner, rc.WARBAND, 3)
    context = {"pieces": {rc.CARNUTES: {rc.HIDDEN: 2}}}
    if loan_kind == "diviciacus":
        key = DIVICIACUS_KEY
        context.update(faction=rc.ROMANS, lender=owner, piece_type=rc.AUXILIA,
                       physical_type=rc.WARBAND, regions=[rc.CARNUTES])
    else:
        key = BORROW_KEY if loan_kind == "enlist" else FREE_FORCE_KEY
    board[key] = context
    op = pick(board, owner, piece_type=rc.WARBAND,
              loan_kind=loan_kind if remove_lent else None)
    apply(board, owner, op)
    assert board["spaces"][rc.CARNUTES]["pieces"][owner][rc.HIDDEN][rc.WARBAND] == 2
    assert context["pieces"][rc.CARNUTES][rc.HIDDEN] == (1 if remove_lent else 2)
    assert validate_state(board) == []


def test_borrower_cannot_remove_lender_counters_with_diviciacus_or_a28():
    board = state()
    pieces.place_piece(board, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 2)
    pieces.place_piece(board, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    board[DIVICIACUS_KEY] = {"faction": rc.ROMANS, "lender": rc.AEDUI,
        "piece_type": rc.AUXILIA, "physical_type": rc.WARBAND,
        "regions": [rc.CARNUTES], "pieces": {rc.CARNUTES: {rc.HIDDEN: 2}}}
    board[COMBINED_KEY] = {"faction": rc.ROMANS,
                          "owners": {rc.CARNUTES: [rc.AEDUI]}}
    assert pieces.count_pieces(board, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 3
    own = pick(board, rc.ROMANS, piece_type=rc.AUXILIA)
    apply(board, rc.ROMANS, own)
    assert board["spaces"][rc.CARNUTES]["pieces"][rc.AEDUI][rc.HIDDEN][rc.WARBAND] == 2
    assert removal.make_request(board, rc.ROMANS) is None
    assert validate_state(board) == []


def test_a28_lender_removes_own_physical_piece_from_combined_force():
    board = state(rc.SCENARIO_ARIOVISTUS)
    pieces.place_piece(board, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 2)
    pieces.place_piece(board, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    board[COMBINED_KEY] = {"faction": rc.ROMANS,
                          "owners": {rc.CARNUTES: [rc.AEDUI]}}
    assert pieces.count_pieces(board, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 0
    apply(board, rc.AEDUI, pick(board, rc.AEDUI, piece_type=rc.WARBAND))
    assert pieces.count_pieces(board, rc.CARNUTES, rc.ROMANS, rc.WARBAND) == 1
    assert pieces.count_pieces(board, rc.CARNUTES, rc.ROMANS, rc.AUXILIA) == 1
    assert validate_state(board) == []


@pytest.mark.parametrize("remove_selected", [False, True])
def test_impetuosity_group_lent_to_roman_defense_tracks_the_exact_intersection(remove_selected):
    board = state()
    pieces.place_piece(board, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 3)
    board[FREE_FORCE_KEY] = {"faction": rc.AEDUI, "source": "Impetuosity",
                             "pieces": {rc.CARNUTES: {rc.HIDDEN: 2}}}
    board[DIVICIACUS_KEY] = {"faction": rc.ROMANS, "lender": rc.AEDUI,
        "piece_type": rc.AUXILIA, "physical_type": rc.WARBAND,
        "phase": "defense", "regions": [rc.CARNUTES],
        "pieces": {rc.CARNUTES: {rc.HIDDEN: 3}}}
    kind = "diviciacus+free_force" if remove_selected else "diviciacus"
    apply(board, rc.AEDUI, pick(board, rc.AEDUI, loan_kind=kind))
    assert board[DIVICIACUS_KEY]["pieces"][rc.CARNUTES][rc.HIDDEN] == 2
    assert board[FREE_FORCE_KEY]["pieces"][rc.CARNUTES][rc.HIDDEN] == (1 if remove_selected else 2)
    assert board["spaces"][rc.CARNUTES]["pieces"][rc.AEDUI][rc.HIDDEN][rc.WARBAND] == 2
    assert validate_state(board) == []


def test_belgae_cannot_reclaim_enlisted_german_counters():
    board = state(rc.SCENARIO_ARIOVISTUS)
    pieces.place_piece(board, rc.CARNUTES, rc.GERMANS, rc.WARBAND, 2)
    pieces.place_piece(board, rc.CARNUTES, rc.BELGAE, rc.WARBAND)
    board[BORROW_KEY] = {"pieces": {rc.CARNUTES: {rc.HIDDEN: 2}}}
    own = pick(board, rc.BELGAE, piece_type=rc.WARBAND)
    apply(board, rc.BELGAE, own)
    assert board[BORROW_KEY]["pieces"][rc.CARNUTES][rc.HIDDEN] == 2
    assert board["spaces"][rc.CARNUTES]["pieces"][rc.GERMANS][rc.HIDDEN][rc.WARBAND] == 2
    assert removal.make_request(board, rc.BELGAE) is None
    assert validate_state(board) == []


def test_march_cohorts_remain_distinct_from_resident_pieces():
    board = state()
    pieces.place_piece(board, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 4)
    cohorts = [{"id": "march_0", "label": "Moving group", "region": rc.CARNUTES,
                "piece_type": rc.WARBAND, "piece_state": rc.HIDDEN, "count": 3}]
    resident = pick(board, rc.AEDUI, cohorts=cohorts, cohort=None)
    moving = pick(board, rc.AEDUI, cohorts=cohorts, cohort="march_0", count=2)
    effects = apply(board, rc.AEDUI, resident, moving, cohorts=cohorts)
    assert [effect.get("cohort") for effect in effects] == [None, "march_0"]
    assert cohorts[0]["count"] == 3  # Caller local objects are never changed.
    assert removal.advance_cohorts(cohorts, effects)[0]["count"] == 1
    assert pieces.count_pieces(board, rc.CARNUTES, rc.AEDUI, rc.WARBAND) == 1
    assert validate_state(board) == []


def test_oversized_or_forged_cohort_never_silently_clamps():
    board = state()
    pieces.place_piece(board, rc.CARNUTES, rc.AEDUI, rc.WARBAND)
    cohorts = [{"id": "march", "region": rc.CARNUTES,
                "piece_type": rc.WARBAND, "piece_state": rc.HIDDEN, "count": 2}]
    before = encode(board)
    with pytest.raises(ValueError, match="exceeds"):
        removal.options(board, rc.AEDUI, cohorts=cohorts)
    request = removal.make_request(board, rc.AEDUI)
    request["cohorts"] = [dict(cohorts[0], count=1)]
    forged = dict(pick(board, rc.AEDUI), cohort="march")
    with pytest.raises(ValueError, match="own physical"):
        removal.apply_response(board, request, {"operations": [forged]})
    assert encode(board) == before


def test_collector_supports_board_command_and_preserves_live_board(monkeypatch):
    from fs_bot.cli.menus import set_board_hook, _BOARD_HOOK
    from fs_bot.cli.voluntary_removal import collect_removals
    board = state()
    pieces.place_piece(board, rc.CARNUTES, rc.AEDUI, rc.WARBAND, 2)
    request = removal.make_request(board, rc.AEDUI)
    before = encode(board)
    calls = []
    displayed_counts = []
    def display(current):
        displayed_counts.append(pieces.count_pieces(
            current, rc.CARNUTES, rc.AEDUI, rc.WARBAND))
        return "Board snapshot"
    monkeypatch.setattr("fs_bot.cli.display.format_board", display)
    set_board_hook(lambda: calls.append("board"))
    previous = _BOARD_HOOK[0]
    stdout = io.StringIO()
    try:
        response = collect_removals(board, rc.AEDUI, request,
            io.StringIO("board\n3\n2\nboard\n1\n"), stdout)
        assert _BOARD_HOOK[0] is previous
    finally:
        set_board_hook(None)
    assert calls == []  # The collector shows its current detached proposals.
    assert displayed_counts == [2, 0]
    assert stdout.getvalue().count("Proposed board after selected removals:") == 2
    assert response == {"operations": [pick(board, rc.AEDUI, count=2)]}
    assert encode(board) == before


def test_collector_eof_after_proposed_removal_does_not_mutate_board():
    from fs_bot.cli.menus import set_board_hook, _BOARD_HOOK
    from fs_bot.cli.voluntary_removal import collect_removals
    board = state()
    pieces.place_piece(board, rc.CARNUTES, rc.AEDUI, rc.WARBAND)
    before = encode(board)
    previous = lambda: None
    set_board_hook(previous)
    try:
        with pytest.raises(EOFError):
            collect_removals(board, rc.AEDUI, removal.make_request(board, rc.AEDUI),
                             io.StringIO("3\n"), io.StringIO())
        assert _BOARD_HOOK[0] is previous
    finally:
        set_board_hook(None)
    assert encode(board) == before
