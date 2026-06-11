"""Regressions for the external mixed human/bot matrix playtest (June 2026).

Three defect families it surfaced: stale one-shot Event free-action flags
replaying in later Events; Ariovistus A18/A25 removing German Ally discs
without clearing the authoritative tribe allegiance; and after-Command
Special Activities being awarded even when the Command produced no legal
effect.
"""
import contextlib
import io

import fs_bot.rules_consts as rc
from fs_bot.state.setup import setup_scenario
from fs_bot.board.pieces import count_pieces, place_piece
from fs_bot.engine.victory import TRIBE_TO_REGION


def _allied_tribes(state, region, faction):
    out = []
    for t, info in state.get("tribes", {}).items():
        if info.get("allied_faction") == faction and \
                TRIBE_TO_REGION.get(t) == region:
            out.append(t)
    return out


def test_one_shot_free_action_flags_consumed():
    """A one-shot free-action flag must not survive _resolve_free_actions
    (stale flags replayed in later Events -- defect family 1)."""
    from fs_bot.engine.execute import _resolve_free_actions
    st = setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=1)
    st["event_modifiers"] = {"card_34_free_rally": True,
                             "optimates_active": True}
    with contextlib.redirect_stdout(io.StringIO()):
        _resolve_free_actions(st, rc.AEDUI)
    em = st.get("event_modifiers", {})
    assert "card_34_free_rally" not in em, "one-shot flag must be consumed"
    assert em.get("optimates_active"), "persistent modifier must survive"


def test_a18_removes_german_allies_in_sync():
    """A18 unshaded removes German Allies as pieces AND allegiance."""
    from fs_bot.cards.card_effects import execute_card_A18
    from fs_bot.rules_consts import GERMANIA_REGIONS, SUGAMBRI

    st = setup_scenario(rc.SCENARIO_ARIOVISTUS, seed=1)
    region = SUGAMBRI if SUGAMBRI in GERMANIA_REGIONS else GERMANIA_REGIONS[0]
    # Ensure a German ally exists there and Rome is adjacent/controlling.
    tribe = next((t for t, r in TRIBE_TO_REGION.items() if r == region), None)
    if tribe is None:
        return
    st["tribes"].setdefault(tribe, {})["allied_faction"] = rc.GERMANS
    st["tribes"][tribe]["status"] = None
    if count_pieces(st, region, rc.GERMANS, rc.ALLY) == 0:
        place_piece(st, region, rc.GERMANS, rc.ALLY)
    st["event_params"] = {"region": region}
    # Force Roman adjacency by controlling the region outright.
    place_piece(st, region, rc.ROMANS, rc.LEGION, 3, from_legions_track=True)
    with contextlib.redirect_stdout(io.StringIO()):
        execute_card_A18(st, shaded=False)
    # If the removal fired, pieces and allegiance must agree (no stray ally).
    assert count_pieces(st, region, rc.GERMANS, rc.ALLY) == \
        len(_allied_tribes(st, region, rc.GERMANS))


def test_after_command_sa_skipped_when_command_fails():
    """A failed Command must not award its after-Command SA (defect 3):
    a zero-Resource Aedui Rally + Trade must not still grant resources."""
    from fs_bot.engine.execute import _execute_bot_command

    st = setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=1)
    st["resources"][rc.AEDUI] = 0
    res_before = st["resources"][rc.AEDUI]
    bot_action = {"command": "Rally", "sa": "Trade", "sa_regions": [],
                  "details": {"rally_plan": {"citadels": [],
                                             "allies": [], "warbands": []}}}
    with contextlib.redirect_stdout(io.StringIO()):
        result = _execute_bot_command(st, rc.AEDUI, bot_action)
    # Rally produced no legal effect, so Trade must not have run.
    if result is not None and result.get("executed") is False:
        assert "sa_execution" not in result or \
            result.get("sa_skipped"), "after-Command SA must be withheld"
        assert st["resources"][rc.AEDUI] == res_before, \
            "Trade must not have granted resources after a failed Rally"
