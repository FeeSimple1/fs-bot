"""Voluntary Resource transfers (§1.5.2/A1.5.2) and the §8.6.6 NP Aedui
subsidy — previously decision logic existed in every bot's agreements
node but NOTHING ever called it or moved the Resources."""

import pytest

import fs_bot.rules_consts as rc
from fs_bot.commands.common import CommandError
from fs_bot.commands.transfer import transfer_resources
from fs_bot.state.setup import setup_scenario
from fs_bot.engine.execute import execute_decision, maybe_np_aedui_subsidy
from fs_bot.cards.capabilities import activate_capability


def _st(scenario=rc.SCENARIO_GREAT_REVOLT, seed=4):
    st = setup_scenario(scenario, seed=seed)
    st["non_player_factions"] = set()
    return st


class TestTransferMechanic:
    def test_basic_transfer_and_conservation(self):
        st = _st()
        st["resources"][rc.AEDUI] = 10
        st["resources"][rc.ROMANS] = 5
        res = transfer_resources(st, rc.AEDUI, rc.ROMANS, 4)
        assert res["given"] == 4
        assert st["resources"][rc.AEDUI] == 6
        assert st["resources"][rc.ROMANS] == 9

    def test_receiver_caps_at_max_resources(self):
        st = _st()
        st["resources"][rc.AEDUI] = 10
        st["resources"][rc.ROMANS] = rc.MAX_RESOURCES - 2
        res = transfer_resources(st, rc.AEDUI, rc.ROMANS, 5)
        assert res["given"] == 2                      # only the room
        assert st["resources"][rc.AEDUI] == 8         # pays what arrived
        assert st["resources"][rc.ROMANS] == rc.MAX_RESOURCES

    def test_validation_errors(self):
        st = _st()
        st["resources"][rc.AEDUI] = 3
        with pytest.raises(CommandError):
            transfer_resources(st, rc.AEDUI, rc.AEDUI, 1)
        with pytest.raises(CommandError):
            transfer_resources(st, rc.AEDUI, rc.ROMANS, 0)
        with pytest.raises(CommandError):
            transfer_resources(st, rc.AEDUI, rc.ROMANS, 4)   # > stock
        # Base game: Germans neither give nor receive (§1.5.2/§1.8).
        with pytest.raises(CommandError):
            transfer_resources(st, rc.AEDUI, rc.GERMANS, 1)

    def test_germans_allowed_in_ariovistus(self):
        """A1.5.2: the Germans transfer just as the other Factions."""
        st = _st(rc.SCENARIO_ARIOVISTUS)
        st["resources"][rc.GERMANS] = 5
        res = transfer_resources(st, rc.GERMANS, rc.BELGAE, 3)
        assert res["given"] == 3

    def test_card_38_shaded_bans_rome_aedui(self):
        st = _st()
        st["resources"][rc.AEDUI] = 10
        activate_capability(st, 38, rc.EVENT_SHADED)
        with pytest.raises(CommandError):
            transfer_resources(st, rc.AEDUI, rc.ROMANS, 2)
        # Other pairs unaffected.
        transfer_resources(st, rc.AEDUI, rc.ARVERNI, 2)


class TestTransfersRideExecution:
    def test_player_action_transfers_applied_and_reported(self):
        """§1.5.2: transfers ride the acting Faction's Command execution;
        errors are reported, never block the Command."""
        from fs_bot.board.pieces import place_piece
        st = _st(rc.SCENARIO_PAX_GALLICA)
        st["resources"][rc.AEDUI] = 10
        place_piece(st, rc.AEDUI_REGION, rc.AEDUI, rc.WARBAND, 2,
                    piece_state=rc.HIDDEN)
        pa = {"command": "Rally", "regions": [], "sa": "No SA",
              "sa_regions": [],
              "details": {"rally_plan": {"citadels": [], "allies": [],
                                         "warbands": [rc.AEDUI_REGION]},
                          "transfers": [
                              {"to": rc.ROMANS, "amount": 3},
                              {"to": rc.GERMANS, "amount": 1}]}}   # illegal
        before_r = st["resources"][rc.ROMANS]
        res = execute_decision(st, rc.AEDUI, {"player_action": pa})
        assert res["executed"]
        assert st["resources"][rc.ROMANS] == before_r + 3
        ok, bad = res["transfers"]
        assert ok["given"] == 3
        assert "error" in bad                          # German ban reported


class TestNpAeduiSubsidy:
    def test_subsidy_fires_for_np_rome(self):
        st = _st(rc.SCENARIO_PAX_GALLICA)
        st["non_player_factions"] = {rc.AEDUI, rc.ROMANS, rc.ARVERNI,
                                     rc.BELGAE}
        st["resources"][rc.ROMANS] = 1
        st["resources"][rc.AEDUI] = 25
        res = maybe_np_aedui_subsidy(st)
        assert res and res["given"] == 10
        assert st["resources"][rc.ROMANS] == 11
        assert st["resources"][rc.AEDUI] == 15

    def test_subsidy_conditions(self):
        st = _st(rc.SCENARIO_PAX_GALLICA)
        st["non_player_factions"] = {rc.AEDUI, rc.ROMANS, rc.ARVERNI,
                                     rc.BELGAE}
        # Rome not poor enough.
        st["resources"][rc.ROMANS] = 2
        st["resources"][rc.AEDUI] = 25
        assert maybe_np_aedui_subsidy(st) is None
        # Aedui not rich enough.
        st["resources"][rc.ROMANS] = 1
        st["resources"][rc.AEDUI] = 20
        assert maybe_np_aedui_subsidy(st) is None
        # Player Aedui: no NP subsidy at all.
        st["non_player_factions"] = {rc.ROMANS, rc.ARVERNI, rc.BELGAE}
        st["resources"][rc.AEDUI] = 25
        assert maybe_np_aedui_subsidy(st) is None

    def test_subsidy_blocked_for_player_rome_at_high_score(self):
        """§8.6.6 NOTE: no transfer to a player Rome above score 12 —
        a bare board scores > 12 for Rome (all Tribes Subdued)."""
        st = _st(rc.SCENARIO_PAX_GALLICA)
        st["non_player_factions"] = {rc.AEDUI, rc.ARVERNI, rc.BELGAE}
        st["resources"][rc.ROMANS] = 1
        st["resources"][rc.AEDUI] = 25
        assert maybe_np_aedui_subsidy(st) is None

    def test_subsidy_fires_after_executed_action(self):
        """The engine checks after every executed SoP action."""
        from fs_bot.engine.game_engine import _maybe_execute
        from fs_bot.board.pieces import place_piece
        st = _st(rc.SCENARIO_PAX_GALLICA)
        st["non_player_factions"] = {rc.AEDUI, rc.ROMANS, rc.ARVERNI,
                                     rc.BELGAE}
        st["resources"][rc.ROMANS] = 1
        st["resources"][rc.AEDUI] = 25
        place_piece(st, rc.AEDUI_REGION, rc.BELGAE, rc.WARBAND, 2,
                    piece_state=rc.HIDDEN)
        pa = {"command": "Raid", "regions": [], "sa": "No SA",
              "sa_regions": [],
              "details": {"raid_plan": [{"region": rc.AEDUI_REGION,
                                         "target": None}]}}
        actions = {rc.BELGAE: {"action": "command"}}
        res = _maybe_execute(st, rc.BELGAE, {"player_action": pa}, actions)
        assert res.get("np_aedui_subsidy", {}).get("given") == 10
        assert st["resources"][rc.ROMANS] == 11


def test_suborn_rejects_dispersed_tribe():
    """§4.4.2/§1.7: Suborn places an Ally at a SUBDUED Tribe — a
    Dispersed(-Gathering) Tribe is not Subdued. The old check looked only
    at allied_faction, so the NP Aedui allied a Dispersed-Gathering Tribe
    and the Spring Phase stranded the Ally piece (player_fuzz structural
    catch: Gallic War seed 2)."""
    from fs_bot.commands.sa_suborn import suborn
    from fs_bot.board.pieces import place_piece
    from fs_bot.board.control import refresh_all_control
    st = _st(rc.SCENARIO_GALLIC_WAR, seed=2)
    st["tribes"]["Atrebates"]["status"] = "Dispersed-Gathering"
    place_piece(st, "Atrebates", rc.AEDUI, rc.WARBAND, 15,
                piece_state=rc.HIDDEN)
    refresh_all_control(st)
    st["resources"][rc.AEDUI] = 10
    with pytest.raises(CommandError):
        suborn(st, "Atrebates", [{"action": "place", "faction": rc.AEDUI,
                                  "piece_type": rc.ALLY,
                                  "tribe": "Atrebates"}])
    # And the Aedui bot's Suborn planner no longer picks such a Tribe.
    from fs_bot.bots.aedui_bot import _determine_suborn_sa
    sa, regions, details = _determine_suborn_sa(st, rc.SCENARIO_GALLIC_WAR)
    for sp in (details.get("suborn_plan") or []):
        for a in sp.get("actions", []):
            assert not (a.get("action") == "place_ally"
                        and a.get("tribe") == "Atrebates")


def test_card_a51_shaded_clears_allegiance_with_removed_ally():
    """A51 shaded removes Roman/Aedui pieces at Atrebates — removing an
    Ally disc must clear its Tribe's allegiance too (player_fuzz catch:
    stranded Roman allegiance, Ariovistus seed 45)."""
    from fs_bot.cards import card_effects as ce
    from fs_bot.board.pieces import place_piece, count_pieces
    st = _st(rc.SCENARIO_ARIOVISTUS, seed=5)
    st["executing_faction"] = rc.BELGAE
    st["tribes"]["Atrebates"]["allied_faction"] = rc.ROMANS
    place_piece(st, "Atrebates", rc.ROMANS, rc.ALLY)
    st["event_params"] = {"removals": [{"faction": rc.ROMANS,
                                        "piece_type": rc.ALLY}]}
    from fs_bot.map.map_data import get_tribes_in_region
    def roman_allied_tribes():
        return sum(1 for t in get_tribes_in_region("Atrebates",
                                                   st["scenario"])
                   if st["tribes"].get(t, {}).get("allied_faction")
                   == rc.ROMANS)
    pieces_before = count_pieces(st, "Atrebates", rc.ROMANS, rc.ALLY)
    tribes_before = roman_allied_tribes()
    assert pieces_before == tribes_before          # consistent going in
    ce.execute_event(st, "A51", shaded=True)
    pieces_after = count_pieces(st, "Atrebates", rc.ROMANS, rc.ALLY)
    assert pieces_after == pieces_before - 1       # one Ally removed
    assert roman_allied_tribes() == pieces_after   # allegiance kept in sync


def test_card_22_rejects_non_mobile_replacements():
    """Card 22 unshaded replaces Warbands or Auxilia only — an Ally
    replacement would strand the Tribe's allegiance."""
    from fs_bot.cards import card_effects as ce
    st = _st(rc.SCENARIO_GREAT_REVOLT, seed=5)
    st["executing_faction"] = rc.ARVERNI
    st["event_params"] = {"replacements": [
        {"region": rc.ARVERNI_REGION, "target_faction": rc.AEDUI,
         "piece_type": rc.ALLY}]}
    with pytest.raises(ValueError):
        ce.execute_event(st, 22, shaded=False)
