"""Regression: first-year (off-track) Senate shifts must be a clean no-op.

Pax Gallica?: "During the first year, the Senate is not in Uproar, nor
Intrigue, nor Adulation and does not shift." Setup leaves
state["senate"]["position"] = None for year 1; a Senate-shift Event (Cicero
card 1, Legiones card 2, Pompey card 3) played then must not crash on
_SENATE_INDEX[None] (KeyError(None)) -- it must simply not shift.
(Surfaced by the external all-bot timing audit: many bot Events forfeited
as 'event not applicable: KeyError(None)'.)
"""
import fs_bot.rules_consts as rc
from fs_bot.state.setup import setup_scenario
from fs_bot.cards.card_effects import (execute_card_1, execute_card_2,
                                       execute_card_3, _apply_senate_shift)
from fs_bot.rules_consts import SENATE_UP, SENATE_DOWN


def test_pax_gallica_year_one_senate_is_off_track():
    st = setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=1)
    assert st["senate"]["position"] is None


def test_apply_senate_shift_noop_when_off_track():
    st = setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=1)
    _apply_senate_shift(st, SENATE_UP)
    _apply_senate_shift(st, SENATE_DOWN)
    assert st["senate"]["position"] is None


def test_senate_shift_cards_no_crash_in_year_one():
    st = setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=1)
    st["event_params"] = {"senate_direction": SENATE_DOWN}
    execute_card_1(st, shaded=False)
    execute_card_1(st, shaded=True)
    st["event_params"] = {"legions_from_track": 2}
    execute_card_2(st, shaded=False)
    st["event_params"] = {}
    execute_card_3(st, shaded=False)
    assert st["senate"]["position"] is None  # never shifted in year 1


def test_senate_shift_still_works_once_on_track():
    """The guard must not break normal shifting once the Senate is placed."""
    st = setup_scenario(rc.SCENARIO_RECONQUEST, seed=1)  # starts at Intrigue
    start = st["senate"]["position"]
    assert start is not None
    st["event_params"] = {"senate_direction": SENATE_UP}
    execute_card_1(st, shaded=False)
    # A normal shift must change position or firmness (not a silent no-op).
    assert (st["senate"]["position"] != start) or st["senate"]["firm"]
