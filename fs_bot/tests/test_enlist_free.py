"""Source-derived Enlist free Command checks: §3.4/4.5.1, A3.4/A4.5.1."""

import pytest

from fs_bot import rules_consts as rc
from fs_bot.board.control import refresh_all_control
from fs_bot.board.pieces import place_piece, count_pieces, count_pieces_by_state
from fs_bot.commands.common import CommandError
from fs_bot.commands.enlist_free import execute_free_enlist
from fs_bot.engine.execute import _execute_enlist, _execute_rally
from fs_bot.state.serialize import encode
from fs_bot.state.state_schema import build_initial_state


def state(ario=False, region=rc.SUGAMBRI):
    st = build_initial_state(rc.SCENARIO_ARIOVISTUS if ario else rc.SCENARIO_PAX_GALLICA,
                             seed=11)
    place_piece(st, region, rc.BELGAE, rc.LEADER,
                leader_name=rc.BODUOGNATUS if ario else rc.AMBIORIX)
    st["resources"][rc.GERMANS] = 10 if ario else 0
    st["resources"][rc.AEDUI] = 10
    return st


def ally(st, region, tribe):
    place_piece(st, region, rc.GERMANS, rc.ALLY)
    st["tribes"][tribe]["status"] = None
    st["tribes"][tribe]["allied_faction"] = rc.GERMANS


def wb(st, count, *, region=rc.SUGAMBRI, faction=rc.GERMANS, visibility=rc.HIDDEN):
    place_piece(st, region, faction, rc.WARBAND, count, piece_state=visibility)


def fingerprint(st):
    return encode({k: v for k, v in st.items() if k != "decision_agent"})


@pytest.mark.parametrize("ario", [False, True])
def test_free_raid_steals_two_but_only_ario_receives_resources(ario):
    st = state(ario)
    wb(st, 3)
    wb(st, 1, faction=rc.AEDUI)
    before = st["resources"][rc.GERMANS]
    execute_free_enlist(st, {"type": "german_raid", "region": rc.SUGAMBRI,
                             "target": rc.AEDUI, "count": 2})
    assert st["resources"][rc.AEDUI] == 8
    assert st["resources"][rc.GERMANS] == before + (2 if ario else 0)
    assert count_pieces_by_state(st, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, rc.REVEALED) == 2


def test_base_raid_cannot_gain_unowned_resources():
    st = state()
    wb(st, 2)
    before = fingerprint(st)
    with pytest.raises(CommandError, match="must target"):
        execute_free_enlist(st, {"type": "german_raid", "region": rc.SUGAMBRI})
    assert fingerprint(st) == before


def test_base_battle_requires_hidden_superiority_before_mutation():
    st = state()
    wb(st, 2)
    wb(st, 2, faction=rc.AEDUI)
    before = fingerprint(st)
    with pytest.raises(CommandError, match="Ambush"):
        execute_free_enlist(st, {"type": "german_battle", "region": rc.SUGAMBRI,
                                 "target": rc.AEDUI})
    assert fingerprint(st) == before


def test_base_battle_success_ambushes_and_reveals():
    st = state()
    wb(st, 4)
    wb(st, 2, faction=rc.AEDUI)
    result = execute_free_enlist(st, {"type": "german_battle", "region": rc.SUGAMBRI,
                                      "target": rc.AEDUI})
    assert result["counterattack"] is None
    assert count_pieces(st, rc.SUGAMBRI, rc.AEDUI, rc.WARBAND) == 0
    assert count_pieces_by_state(st, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, rc.REVEALED) == 4


def test_ario_battle_limits_force_losses_and_reveal_to_selected_four():
    st = state(True)
    wb(st, 9)
    wb(st, 2, faction=rc.AEDUI)
    result = execute_free_enlist(st, {"type": "german_battle", "region": rc.SUGAMBRI,
                                      "target": rc.AEDUI})
    assert result["attack"]["losses_taken"] == 2
    assert count_pieces_by_state(st, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 5
    assert count_pieces_by_state(st, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, rc.REVEALED) == 4
    assert "_enlist_free_force" not in st


def test_ario_battle_ignores_unselected_ally_settlement_and_successor():
    st = state(True)
    wb(st, 2)
    ally(st, rc.SUGAMBRI, rc.TRIBE_SUGAMBRI)
    place_piece(st, rc.SUGAMBRI, rc.GERMANS, rc.SETTLEMENT)
    place_piece(st, rc.SUGAMBRI, rc.GERMANS, rc.LEADER, leader_name=rc.SUCCESSOR)
    wb(st, 10, faction=rc.AEDUI)
    execute_free_enlist(st, {"type": "german_battle", "region": rc.SUGAMBRI,
                             "target": rc.AEDUI})
    assert count_pieces(st, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND) == 0
    assert count_pieces(st, rc.SUGAMBRI, rc.GERMANS, rc.ALLY) == 1
    assert count_pieces(st, rc.SUGAMBRI, rc.GERMANS, rc.SETTLEMENT) == 1
    assert count_pieces(st, rc.SUGAMBRI, rc.GERMANS, rc.LEADER) == 1
    assert count_pieces(st, rc.SUGAMBRI, rc.AEDUI, rc.WARBAND) == 9


def test_ario_counterattack_cannot_remove_unselected_warbands():
    st = state(True)
    wb(st, 9)
    wb(st, 20, faction=rc.AEDUI)
    execute_free_enlist(st, {"type": "german_battle", "region": rc.SUGAMBRI,
                             "target": rc.AEDUI})
    assert count_pieces(st, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND) == 5
    assert count_pieces_by_state(st, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 5


def test_ario_enlist_never_selects_ariovistus_region():
    st = state(True)
    wb(st, 4)
    wb(st, 1, faction=rc.AEDUI)
    place_piece(st, rc.SUGAMBRI, rc.GERMANS, rc.LEADER, leader_name=rc.ARIOVISTUS_LEADER)
    before = fingerprint(st)
    with pytest.raises(CommandError, match="Ariovistus"):
        execute_free_enlist(st, {"type": "german_battle", "region": rc.SUGAMBRI,
                                 "target": rc.AEDUI})
    assert fingerprint(st) == before


@pytest.mark.parametrize("selection", [5, -1, True, {rc.HIDDEN: 5}, {rc.LEADER: 1}])
def test_ario_invalid_selected_force_rejected_atomically(selection):
    st = state(True)
    wb(st, 6)
    wb(st, 2, faction=rc.AEDUI)
    before = fingerprint(st)
    with pytest.raises(CommandError):
        execute_free_enlist(st, {"type": "german_battle", "region": rc.SUGAMBRI,
                                 "target": rc.AEDUI, "warbands": selection})
    assert fingerprint(st) == before


@pytest.mark.parametrize("ario", [False, True])
def test_march_rejects_nonadjacent_destination_before_flipping(ario):
    st = state(ario)
    wb(st, 3, visibility=rc.REVEALED)
    before = fingerprint(st)
    with pytest.raises(CommandError, match="adjacent"):
        execute_free_enlist(st, {"type": "german_march", "origin": rc.SUGAMBRI,
                                 "destination": rc.PROVINCIA})
    assert fingerprint(st) == before


def test_ario_march_moves_selected_mixed_visibility_and_never_leader():
    st = state(True)
    wb(st, 5, visibility=rc.HIDDEN)
    wb(st, 3, visibility=rc.SCOUTED)
    place_piece(st, rc.SUGAMBRI, rc.GERMANS, rc.LEADER, leader_name=rc.SUCCESSOR)
    execute_free_enlist(st, {"type": "german_march", "origin": rc.SUGAMBRI,
                             "destination": rc.UBII,
                             "warbands": {rc.HIDDEN: 2, rc.SCOUTED: 2}})
    assert count_pieces(st, rc.SUGAMBRI, rc.GERMANS, rc.LEADER) == 1
    assert count_pieces_by_state(st, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 3
    assert count_pieces_by_state(st, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, rc.SCOUTED) == 1
    assert count_pieces_by_state(st, rc.UBII, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 2
    assert count_pieces_by_state(st, rc.UBII, rc.GERMANS, rc.WARBAND, rc.REVEALED) == 2


def test_ario_hide_affects_only_four_and_scouted_not_hidden():
    st = state(True)
    wb(st, 3, visibility=rc.REVEALED)
    wb(st, 3, visibility=rc.SCOUTED)
    execute_free_enlist(st, {"type": "german_march_hide", "region": rc.SUGAMBRI})
    assert count_pieces_by_state(st, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 3
    assert count_pieces_by_state(st, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, rc.REVEALED) == 1
    assert count_pieces_by_state(st, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, rc.SCOUTED) == 2


def test_base_march_flips_staying_warbands_too():
    st = state()
    wb(st, 5, visibility=rc.REVEALED)
    execute_free_enlist(st, {"type": "german_march", "origin": rc.SUGAMBRI,
                             "destination": rc.UBII, "warbands": 2})
    assert count_pieces_by_state(st, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 3
    assert count_pieces_by_state(st, rc.UBII, rc.GERMANS, rc.WARBAND, rc.HIDDEN) == 2


@pytest.mark.parametrize("ario", [False, True])
def test_free_rally_ally_also_places_source_defined_warbands(ario):
    st = state(ario)
    wb(st, 3)
    refresh_all_control(st)
    execute_free_enlist(st, {"type": "german_rally", "region": rc.SUGAMBRI,
                             "place": "ally", "tribe": rc.TRIBE_SUGAMBRI})
    assert count_pieces(st, rc.SUGAMBRI, rc.GERMANS, rc.ALLY) == 1
    assert count_pieces(st, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND) == 4


def test_ario_empty_home_rally_places_only_one_bonus():
    st = state(True)
    execute_free_enlist(st, {"type": "german_rally", "region": rc.SUGAMBRI,
                             "place": "warbands"})
    assert count_pieces(st, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND) == 1


def test_ario_rally_enlist_limit_includes_bonus():
    st = state(True, rc.MANDUBII)
    wb(st, 1, region=rc.MANDUBII)
    for tribe in (rc.TRIBE_MANDUBII, rc.TRIBE_SENONES, rc.TRIBE_LINGONES):
        ally(st, rc.MANDUBII, tribe)
    place_piece(st, rc.MANDUBII, rc.GERMANS, rc.SETTLEMENT)
    execute_free_enlist(st, {"type": "german_rally", "region": rc.MANDUBII,
                             "place": "warbands"})
    assert count_pieces(st, rc.MANDUBII, rc.GERMANS, rc.WARBAND) == 5


def test_normal_ario_rally_gets_bonus_after_main_option():
    st = state(True)
    ally(st, rc.SUGAMBRI, rc.TRIBE_SUGAMBRI)
    result = _execute_rally(st, rc.GERMANS, {"details": {
        "rally_plan": {"warbands": [rc.SUGAMBRI]}}})
    assert result["executed"]
    assert count_pieces(st, rc.SUGAMBRI, rc.GERMANS, rc.WARBAND) == 2


def test_other_factions_cannot_execute_belgic_enlist():
    st = state(True)
    before = fingerprint(st)
    result = _execute_enlist(st, rc.AEDUI, {"details": {"enlist": {
        "type": "german_rally", "region": rc.SUGAMBRI, "place": "warbands"}}})
    assert not result["executed"]
    assert fingerprint(st) == before
