"""A Setup/A1.2.1: choose and retain the five printed card replacements.

Expected differences below come from the original and A Card Reference
texts, not from comparing the two implementation paths to one another.
"""

import copy
import io

import pytest

import fs_bot.rules_consts as rc
from fs_bot.board.pieces import place_piece, count_pieces
from fs_bot.cards.card_effects import execute_event
from fs_bot.cards.card_text import get_card_text
from fs_bot.cards.edition import CARD_EDITIONS, uses_second_edition
from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state


@pytest.mark.parametrize("scenario", rc.ALL_SCENARIOS)
@pytest.mark.parametrize("profile,revised", [
    ("original", False), ("second-edition", True),
])
@pytest.mark.parametrize("card,original,replacement", [
    (11, "there, with Auxilia causing double", "there with Auxilia, causing double"),
    (30, "pick 2 Arverni Warbands", "pick 4 Arverni Warbands"),
    (39, "always\nyield +2 Resources", "Trade yields Resources regardless"),
    (44, "They all free Raid", "Execute a free Command"),
    (54, "In the first Battle", "In the 1st Faction’s Battle"),
])
def test_explicit_profile_selects_printed_text_in_every_scenario(
        scenario, profile, revised, card, original, replacement):
    text = get_card_text(card, scenario, profile)
    assert (replacement if revised else original) in text
    assert (original if revised else replacement) not in text


@pytest.mark.parametrize("scenario", rc.ALL_SCENARIOS)
def test_old_saves_keep_scenario_selection(scenario):
    assert uses_second_edition({"scenario": scenario}) == (
        scenario in rc.ARIOVISTUS_SCENARIOS)


@pytest.mark.parametrize("profile", CARD_EDITIONS)
def test_profile_does_not_change_deck_or_faction_roles(profile):
    from fs_bot.engine.game_engine import get_sop_factions
    expected = setup_scenario(rc.SCENARIO_ARIOVISTUS, seed=9)
    state = setup_scenario(rc.SCENARIO_ARIOVISTUS, seed=9, card_edition=profile)
    assert state["deck"] == expected["deck"]
    assert get_sop_factions(state) == get_sop_factions(expected)
    assert 30 not in state["deck"]
    # A-prefix and optional O38 identities are unaffected by this selector.
    assert get_card_text("A30", state["scenario"], profile) == get_card_text("A30")
    assert get_card_text(rc.CARD_O38, state["scenario"], profile) == get_card_text(rc.CARD_O38)


def test_bad_profile_is_rejected():
    with pytest.raises(ValueError, match="Unknown card edition"):
        setup_scenario(rc.SCENARIO_PAX_GALLICA, seed=1, card_edition="typo")


@pytest.mark.parametrize("profile,expected_losses", [("original", 8), ("second-edition", 3)])
def test_numidians_revised_battle_excludes_caesar_and_legions(profile, expected_losses):
    """Original: Caesar + 2 doubled Legions + 3 doubled Auxilia = 8.
    Revised: only the 3 Auxilia fight, inflicting 3 Losses.
    """
    from fs_bot.engine.execute import _execute_event
    from fs_bot.engine.agent import RETREAT
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=4)
    state["card_edition"] = profile
    state["non_player_factions"] = set()
    state["decision_agent"] = lambda s, f, req: (
        {"retreat": False} if req.get("kind") == RETREAT else None)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEADER, leader_name=rc.CAESAR)
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.LEGION, 2,
                from_legions_track=True)
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 15)
    result = _execute_event(state, rc.ROMANS, {"details": {
        "card_id": 11, "text_preference": rc.EVENT_UNSHADED,
        "event_params": {"region": rc.CARNUTES, "target_region": rc.CARNUTES},
    }}, human=True)
    assert result["executed"], result
    battle = next(a for a in result["free_actions"] if a["free_action"] == "battle")
    assert battle["result"]["attack"]["losses_taken"] == expected_losses
    assert count_pieces(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND) == 15 - expected_losses


@pytest.mark.parametrize("profile,elite,losses", [("original", 2, 4), ("second-edition", 4, 5)])
def test_elite_warbands_use_printed_count_for_attack_and_defence(profile, elite, losses):
    from fs_bot.battle.losses import (calculate_losses, resolve_losses,
                                     card30_arverni_legion_warbands)
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=2)
    state["card_edition"] = profile
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.LEADER,
                leader_name=rc.VERCINGETORIX)
    place_piece(state, rc.CARNUTES, rc.ARVERNI, rc.WARBAND, 4)
    execute_event(state, 30, shaded=True)
    assert card30_arverni_legion_warbands(state, rc.CARNUTES, rc.ARVERNI) == elite
    # Leader 1 + elite at 1 each + remaining Warbands at 1/2, rounded down.
    assert calculate_losses(state, rc.CARNUTES, rc.ARVERNI, rc.ROMANS) == losses
    # Seed 2 starts with 1,1,1,3: every elite selected for loss is removed.
    result = resolve_losses(state, rc.CARNUTES, rc.ARVERNI, 4,
                             loss_order=[(rc.WARBAND, rc.HIDDEN)] * 4)
    assert len(result["rolls"]) == elite
    assert result["losses_taken"] == 4


def _trade_state(profile, blocked):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=2)
    state["card_edition"] = profile
    state["non_player_factions"] = set()
    state["resources"][rc.AEDUI] = 0
    place_piece(state, rc.CARNUTES, rc.AEDUI, rc.ALLY)
    state["tribes"][rc.TRIBE_CARNUTES]["allied_faction"] = rc.AEDUI
    # Keep the Region outside Aedui Control, isolating the Ally's earnings.
    place_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 2)
    execute_event(state, 39)
    return state, {rc.BELGAE: not blocked}


@pytest.mark.parametrize("profile,blocked,agreed,expected", [
    ("original", True, False, 0), ("original", False, False, 2),
    ("original", False, True, 2), ("second-edition", True, False, 1),
    ("second-edition", False, False, 1), ("second-edition", True, True, 2),
])
def test_river_commerce_uses_correct_supply_and_agreement_rule(
        profile, blocked, agreed, expected):
    from fs_bot.commands.sa_trade import trade
    from fs_bot.commands.rally import has_supply_line
    state, agreements = _trade_state(profile, blocked)
    assert has_supply_line(state, rc.CARNUTES, rc.ROMANS, agreements) != blocked
    result = trade(state, agreements=agreements, roman_agreed=agreed)
    assert result["resources_gained"] == expected


def test_revised_commerce_bot_estimate_uses_same_printed_yield():
    from fs_bot.bots.aedui_bot import _estimate_trade_resources
    from fs_bot.board.pieces import remove_piece
    state, _ = _trade_state("second-edition", blocked=True)
    state["non_player_factions"] = {rc.AEDUI}
    remove_piece(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND, 2)
    place_piece(state, rc.CARNUTES, rc.GERMANS, rc.WARBAND, 2)
    # Game-run Germans never agree to a Supply Line. The NP Trade estimate
    # assumes Roman agreement, so revised Commerce earns 2 despite the block.
    assert _estimate_trade_resources(state, state["scenario"]) == 2
    state["card_edition"] = "original"
    assert _estimate_trade_resources(state, state["scenario"]) == 0


@pytest.mark.parametrize("profile,flag", [
    ("original", "card_44_free_raid"), ("second-edition", "card_44a_free_command"),
])
def test_loyalists_selects_raid_or_command_effect_and_evaluation(profile, flag):
    from fs_bot.cards.event_eval import get_event_flags, FREE_COMMAND, FREE_RAID
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=2)
    state["card_edition"] = profile
    place_piece(state, rc.CARNUTES, rc.ROMANS, rc.AUXILIA)
    state["event_params"] = {"replacements": [{
        "region": rc.CARNUTES, "from_faction": rc.ROMANS,
        "from_type": rc.AUXILIA, "to_faction": rc.BELGAE,
    }]}
    execute_event(state, 44, shaded=True)
    assert state["event_modifiers"][flag]
    assert count_pieces(state, rc.CARNUTES, rc.BELGAE, rc.WARBAND) == 1
    flags = get_event_flags(44, True, state["scenario"], profile)
    assert (FREE_COMMAND if profile == "second-edition" else FREE_RAID) in flags
    assert (FREE_RAID if profile == "second-edition" else FREE_COMMAND) not in flags


@pytest.mark.parametrize("profile,revised", [("original", False), ("second-edition", True)])
def test_joined_ranks_retreat_scope_dispatch(profile, revised):
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=2)
    state["card_edition"] = profile
    execute_event(state, 54)
    assert bool(state["event_modifiers"].get("card_54a_second_always_retreat")) == revised


@pytest.mark.parametrize("profile,param", [("original", "target_region"), ("second-edition", "region")])
def test_human_parameter_schema_tracks_selected_numidians_handler(profile, param):
    from fs_bot.cli.human_plan import _card_param_keys
    state = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=2)
    state["card_edition"] = profile
    keys = _card_param_keys(state, 11)
    assert param in keys
    assert ("region" if param == "target_region" else "target_region") not in keys


def test_current_upcoming_and_capability_text_use_saved_profile():
    from fs_bot.cli.display import format_board
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=1, card_edition="second-edition")
    state["current_card"], state["next_card"] = 30, 39
    execute_event(state, 30, shaded=True)
    text = format_board(state)
    assert "Cards 11/30/39/44/54: Second Edition replacements" in text
    assert text.count("pick 4 Arverni Warbands") == 2
    assert "Trade yields Resources regardless" in text
    assert "pick 2 Arverni Warbands" not in text


@pytest.mark.parametrize("profile", CARD_EDITIONS)
def test_profile_survives_interlude_and_save_roundtrip(profile, tmp_path):
    from fs_bot.engine.interlude import run_interlude
    from fs_bot.state.serialize import save_game, load_game
    state = setup_scenario(rc.SCENARIO_GALLIC_WAR, seed=1, card_edition=profile)
    run_interlude(state, britannia_decision=False)
    assert state["scenario"] == rc.SCENARIO_PAX_GALLICA
    path = tmp_path / "game.json"
    save_game(state, path)
    restored, _, _ = load_game(path)
    assert restored["card_edition"] == profile
    assert uses_second_edition(restored) == (profile == "second-edition")


def test_cli_replay_retains_profile_and_load_cannot_change_it(tmp_path, monkeypatch):
    from fs_bot.cli import app
    from fs_bot.state.serialize import save_game
    state = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=11, card_edition="second-edition")
    path = tmp_path / "game.json"
    save_game(state, path, meta={"scenario": rc.SCENARIO_GREAT_REVOLT,
                                "seed": 11, "faction_modes": {rc.ROMANS: "human"}})
    out = io.StringIO()
    assert app.main(["--load", str(path), "--card-edition", "original"],
                    stdin=io.StringIO(), stdout=out) == 2
    assert "Cannot change --card-edition" in out.getvalue()
    observed = []
    real_setup = setup_scenario
    def capture(*args, **kwargs):
        result = real_setup(*args, **kwargs)
        observed.append(copy.deepcopy(result))
        return result
    monkeypatch.setattr(app, "setup_scenario", capture)
    app.main(["--replay", str(path)], stdin=io.StringIO(), stdout=io.StringIO())
    assert observed[0]["card_edition"] == "second-edition"
