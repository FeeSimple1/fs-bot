"""Tests for the Q13 tribe/piece sync helpers and the no-desync invariant.

``state["tribes"][tribe]["allied_faction"]`` (authoritative for victory)
must stay in sync with on-map ALLY/CITADEL pieces: each allied tribe is
represented by exactly one piece of its faction in its Region — an ALLY
disc, or (for a City tribe) a CITADEL. The card_effects helpers
``_ally_tribe`` / ``_unally_tribe`` mutate both records together; the
canary below replays bot-only games and asserts no desync survives.
"""
import contextlib
import io

import fs_bot.rules_consts as rc
from fs_bot.rules_consts import (
    ALLY, CITADEL, AEDUI, ARVERNI, BELGAE, GERMANS,
    TRIBE_TO_REGION, TRIBE_ARVERNI, TRIBE_AEDUI,
    MARKER_DISPERSED,
)
from fs_bot.state.setup import setup_scenario
from fs_bot.board.pieces import count_pieces
from fs_bot.cards.card_effects import (
    _ally_tribe, _unally_tribe, _tribe_piece_type, _tribe_region,
)
from fs_bot.tools.sync_check import desyncs, _bot_func

NERVII_TRIBE = "Nervii"          # Subdued at Great Revolt setup
ATREBATES_TRIBE = "Atrebates"    # Subdued at Great Revolt setup
CADURCI_TRIBE = "Cadurci"        # Arverni Ally disc at Great Revolt setup


def _gr_state():
    return setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=1)


# ---------------------------------------------------------------------------
# _ally_tribe
# ---------------------------------------------------------------------------

def test_ally_tribe_places_piece_and_sets_dict_together():
    state = _gr_state()
    region = TRIBE_TO_REGION[NERVII_TRIBE]
    before = count_pieces(state, region, BELGAE, ALLY)
    assert _ally_tribe(state, NERVII_TRIBE, BELGAE) is True
    assert state["tribes"][NERVII_TRIBE]["allied_faction"] == BELGAE
    assert count_pieces(state, region, BELGAE, ALLY) == before + 1
    assert desyncs(state) == set()


def test_ally_tribe_no_piece_available_no_dict_change():
    state = _gr_state()
    state["available"][BELGAE][ALLY] = 0
    region = TRIBE_TO_REGION[NERVII_TRIBE]
    before = count_pieces(state, region, BELGAE, ALLY)
    assert _ally_tribe(state, NERVII_TRIBE, BELGAE) is False
    assert state["tribes"][NERVII_TRIBE]["allied_faction"] is None
    assert count_pieces(state, region, BELGAE, ALLY) == before
    assert desyncs(state) == set()


def test_ally_tribe_refuses_already_allied_tribe():
    state = _gr_state()
    region = TRIBE_TO_REGION[CADURCI_TRIBE]
    before = count_pieces(state, region, ARVERNI, ALLY)
    assert _ally_tribe(state, CADURCI_TRIBE, BELGAE) is False
    assert state["tribes"][CADURCI_TRIBE]["allied_faction"] == ARVERNI
    assert count_pieces(state, region, ARVERNI, ALLY) == before
    assert desyncs(state) == set()


def test_ally_tribe_refuses_dispersed_tribe():
    state = _gr_state()
    state["tribes"][NERVII_TRIBE]["status"] = MARKER_DISPERSED
    assert _ally_tribe(state, NERVII_TRIBE, BELGAE) is False
    assert state["tribes"][NERVII_TRIBE]["allied_faction"] is None


def test_ally_tribe_unknown_tribe_is_noop():
    state = _gr_state()
    assert _ally_tribe(state, "NotATribe", BELGAE) is False
    assert desyncs(state) == set()


# ---------------------------------------------------------------------------
# _unally_tribe
# ---------------------------------------------------------------------------

def test_unally_tribe_removes_ally_disc_and_clears_dict():
    state = _gr_state()
    region = TRIBE_TO_REGION[CADURCI_TRIBE]
    before = count_pieces(state, region, ARVERNI, ALLY)
    avail_before = state["available"][ARVERNI][ALLY]
    assert _unally_tribe(state, CADURCI_TRIBE) == ARVERNI
    assert state["tribes"][CADURCI_TRIBE]["allied_faction"] is None
    assert count_pieces(state, region, ARVERNI, ALLY) == before - 1
    assert state["available"][ARVERNI][ALLY] == avail_before + 1
    assert desyncs(state) == set()


def test_unally_citadel_tribe_removes_citadel_not_ally():
    """Gergovia (TRIBE_ARVERNI) is allied with a CITADEL piece at setup;
    un-allying it must remove the Citadel and leave the Cadurci Ally
    disc in the same Region untouched."""
    state = _gr_state()
    region = TRIBE_TO_REGION[TRIBE_ARVERNI]
    assert _tribe_piece_type(state, TRIBE_ARVERNI) == CITADEL
    ally_before = count_pieces(state, region, ARVERNI, ALLY)
    cit_before = count_pieces(state, region, ARVERNI, CITADEL)
    assert _unally_tribe(state, TRIBE_ARVERNI) == ARVERNI
    assert state["tribes"][TRIBE_ARVERNI]["allied_faction"] is None
    assert count_pieces(state, region, ARVERNI, CITADEL) == cit_before - 1
    assert count_pieces(state, region, ARVERNI, ALLY) == ally_before
    assert desyncs(state) == set()


def test_unally_bibracte_citadel_tribe():
    state = _gr_state()
    region = TRIBE_TO_REGION[TRIBE_AEDUI]
    cit_before = count_pieces(state, region, AEDUI, CITADEL)
    assert cit_before > 0
    assert _unally_tribe(state, TRIBE_AEDUI) == AEDUI
    assert count_pieces(state, region, AEDUI, CITADEL) == cit_before - 1
    assert state["tribes"][TRIBE_AEDUI]["allied_faction"] is None
    assert desyncs(state) == set()


def test_unally_not_allied_is_noop():
    state = _gr_state()
    region = TRIBE_TO_REGION[NERVII_TRIBE]
    pieces_before = count_pieces(state, region)
    assert _unally_tribe(state, NERVII_TRIBE) is None
    assert count_pieces(state, region) == pieces_before
    assert desyncs(state) == set()


# ---------------------------------------------------------------------------
# Transfer = _unally_tribe + _ally_tribe
# ---------------------------------------------------------------------------

def test_transfer_tribe_between_factions():
    state = _gr_state()
    region = TRIBE_TO_REGION[CADURCI_TRIBE]
    assert _unally_tribe(state, CADURCI_TRIBE) == ARVERNI
    assert _ally_tribe(state, CADURCI_TRIBE, AEDUI) is True
    assert state["tribes"][CADURCI_TRIBE]["allied_faction"] == AEDUI
    assert count_pieces(state, region, AEDUI, ALLY) == 1
    assert count_pieces(state, region, ARVERNI, ALLY) == 0
    assert desyncs(state) == set()


def test_transfer_with_no_target_piece_leaves_tribe_unallied():
    state = _gr_state()
    state["available"][AEDUI][ALLY] = 0
    assert _unally_tribe(state, CADURCI_TRIBE) == ARVERNI
    assert _ally_tribe(state, CADURCI_TRIBE, AEDUI) is False
    assert state["tribes"][CADURCI_TRIBE]["allied_faction"] is None
    assert desyncs(state) == set()


def test_tribe_region_reads_dynamic_colony_region():
    state = _gr_state()
    state["tribes"]["Colony_Mandubii"] = {
        "status": None, "allied_faction": None, "region": "Mandubii",
    }
    assert _tribe_region(state, "Colony_Mandubii") == "Mandubii"


# ---------------------------------------------------------------------------
# Canary: full bot-only games end with zero desyncs
# ---------------------------------------------------------------------------

def _play_bot_game(scenario, seed):
    from fs_bot.engine.game_engine import play_card, start_game, get_sop_factions
    state = setup_scenario(scenario, seed=seed)
    state["non_player_factions"] = set(get_sop_factions(state))
    with contextlib.redirect_stdout(io.StringIO()):
        start_game(state)
        while state["current_card"] is not None:
            result = play_card(state, _bot_func, execute=True)
            if result["game_over"]:
                break
    return state


def test_no_desyncs_pax_gallica_bot_game():
    state = _play_bot_game(rc.SCENARIO_PAX_GALLICA, seed=2)
    assert desyncs(state) == set()


def test_no_desyncs_reconquest_bot_game():
    state = _play_bot_game(rc.SCENARIO_RECONQUEST, seed=2)
    assert desyncs(state) == set()


def test_no_desyncs_great_revolt_bot_game():
    state = _play_bot_game(rc.SCENARIO_GREAT_REVOLT, seed=2)
    assert desyncs(state) == set()


def test_no_desyncs_full_bot_game_ariovistus():
    """Ariovistus exercises the game-run Arverni Phase, whose Rally
    Ally->Citadel upgrade desynced allegiance until the external-playtest
    patch (Citadel keeps the tribe allied)."""
    state = _play_bot_game(rc.SCENARIO_ARIOVISTUS, seed=2)
    assert desyncs(state) == set()
