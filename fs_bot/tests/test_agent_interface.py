"""Agent interface: a human/LLM driver playing by its own judgment.

Covers the reactive-decision hooks (Retreat, Loss order, Agreements) via
state["decision_agent"], the legal-move/validation API, and that the no-agent
path is unchanged.
"""

import copy
import io
import contextlib

from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import build_initial_state, validate_state
from fs_bot.board.pieces import place_piece, remove_piece, count_pieces
from fs_bot.board.control import refresh_all_control
from fs_bot.engine.agent import RETREAT, LOSS_ORDER, AGREEMENT
from fs_bot.engine.execute import _decide_defender_retreat, execute_decision
from fs_bot.engine.game_engine import run_game, get_sop_factions
from fs_bot.cli.dispatcher import make_decision_func
from fs_bot.engine import moves
import fs_bot.rules_consts as rc


def _clear(st, region, faction, types):
    for pt in types:
        c = count_pieces(st, region, faction, pt)
        if c:
            remove_piece(st, region, faction, pt, count=c)


class TestRetreatHook:
    def _battle_state(self):
        st = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=1)
        region, adj = "Bituriges", "Arverni"
        for r in (region, adj):
            _clear(st, r, rc.AEDUI, (rc.WARBAND, rc.AUXILIA))
            _clear(st, r, rc.ROMANS, (rc.LEGION, rc.AUXILIA))
        # Aedui defend Bituriges; they Control the adjacent Arverni Region.
        place_piece(st, region, rc.AEDUI, rc.WARBAND, count=2)
        place_piece(st, adj, rc.AEDUI, rc.WARBAND, count=3)
        place_piece(st, region, rc.ROMANS, rc.LEGION, count=4, from_legions_track=True)
        refresh_all_control(st)
        return st, region, adj

    def test_agent_forces_retreat(self):
        st, region, adj = self._battle_state()
        st["decision_agent"] = lambda s, f, req: (
            {"retreat": True, "region": adj}
            if req["kind"] == RETREAT and f == rc.AEDUI else None)
        rd, rr = _decide_defender_retreat(st, region, rc.ROMANS, rc.AEDUI, False)
        assert rd is True and rr == adj

    def test_agent_declines_retreat(self):
        st, region, adj = self._battle_state()
        st["decision_agent"] = lambda s, f, req: (
            {"retreat": False, "region": None}
            if req["kind"] == RETREAT else None)
        rd, rr = _decide_defender_retreat(st, region, rc.ROMANS, rc.AEDUI, False)
        assert rd is False

    def test_no_agent_uses_default(self):
        # Without an agent, the NP retreat rule decides (deterministic).
        st, region, adj = self._battle_state()
        rd1, rr1 = _decide_defender_retreat(st, region, rc.ROMANS, rc.AEDUI, False)
        rd2, rr2 = _decide_defender_retreat(st, region, rc.ROMANS, rc.AEDUI, False)
        assert (rd1, rr1) == (rd2, rr2)

    def test_agent_cannot_choose_illegal_destination(self):
        st, region, adj = self._battle_state()
        # "Britannia" is not a legal Retreat destination -> treated as no retreat.
        st["decision_agent"] = lambda s, f, req: {"retreat": True,
                                                  "region": "Britannia"}
        rd, rr = _decide_defender_retreat(st, region, rc.ROMANS, rc.AEDUI, False)
        assert rd is False


class TestLossOrderHook:
    def test_agent_chooses_which_piece_absorbs(self):
        from fs_bot.battle.losses import resolve_losses
        st = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=1)
        region = "Aedui"
        _clear(st, region, rc.AEDUI, (rc.WARBAND, rc.AUXILIA))
        place_piece(st, region, rc.AEDUI, rc.WARBAND, count=2)
        # Default Gallic loss order would remove a Warband first; the agent
        # instead directs the Loss onto a Warband of a specific state. Here we
        # just confirm the agent's choice is honored: force the loss onto the
        # only present type and confirm it is removed.
        chosen = (rc.WARBAND, None)
        st["decision_agent"] = lambda s, f, req: (
            [chosen] if req["kind"] == LOSS_ORDER and f == rc.AEDUI else None)
        before = count_pieces(st, region, rc.AEDUI, rc.WARBAND)
        res = resolve_losses(st, region, rc.AEDUI, 1)
        assert count_pieces(st, region, rc.AEDUI, rc.WARBAND) == before - 1
        assert res["losses_taken"] == 1


class TestAgreementHook:
    def test_agent_refuses_retreat_into_its_control(self):
        from fs_bot.engine.execute import _retreat_destinations
        st = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=1)
        region, adj = "Bituriges", "Arverni"
        _clear(st, adj, rc.ARVERNI, (rc.WARBAND,))
        place_piece(st, adj, rc.ARVERNI, rc.WARBAND, count=3)  # Arverni control adj
        place_piece(st, region, rc.AEDUI, rc.WARBAND, count=1)
        refresh_all_control(st)
        # By default the NP Arverni never agree to a Retreat (so adj excluded);
        # an agent that AGREES would include it.
        st["decision_agent"] = lambda s, f, req: (
            True if req["kind"] == AGREEMENT and f == rc.ARVERNI
            and req["request_type"] == "retreat_into_control" else None)
        dests = _retreat_destinations(st, region, rc.AEDUI)
        assert adj in dests
        # And an agent that REFUSES excludes it.
        st["decision_agent"] = lambda s, f, req: (
            False if req["kind"] == AGREEMENT else None)
        assert adj not in _retreat_destinations(st, region, rc.AEDUI)


class TestMoveAPI:
    def _state(self):
        st = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=3)
        st["non_player_factions"] = set(get_sop_factions(st))
        return st

    def test_legal_sop_actions_and_commands(self):
        st = self._state()
        assert "pass" in moves.legal_sop_actions(st)
        assert set(moves.legal_commands(rc.AEDUI)) == {"Rally", "March", "Raid", "Battle"}

    def test_validate_good_and_bad_plan(self):
        st = self._state()
        region = moves.regions_with_pieces(st, rc.AEDUI)[0]
        good = {"command": "Rally", "regions": [], "sa": "No SA",
                "sa_regions": [], "details": {"rally_plan": {
                    "citadels": [], "allies": [], "warbands": [region]}}}
        ok, _info = moves.validate_player_action(st, rc.AEDUI, good)
        assert ok is True
        bad = {"command": "Battle", "regions": [], "sa": "No SA",
               "sa_regions": [], "details": {"battle_plan": [
                   {"region": "Britannia", "target": "Romans"}]}}
        ok2, _ = moves.validate_player_action(st, rc.AEDUI, bad)
        assert ok2 is False

    def test_validation_does_not_mutate_live_state(self):
        st = self._state()
        snapshot = copy.deepcopy(st)
        snapshot.pop("rng", None)
        region = moves.regions_with_pieces(st, rc.AEDUI)[0]
        plan = {"command": "Rally", "regions": [], "sa": "No SA",
                "sa_regions": [], "details": {"rally_plan": {
                    "citadels": [], "allies": [], "warbands": [region]}}}
        moves.validate_player_action(st, rc.AEDUI, plan)
        live = copy.deepcopy(st)
        live.pop("rng", None)
        assert live == snapshot


class TestAgentFullTurn:
    def test_agent_plays_a_turn_and_reactive_decision(self):
        """A faction driven entirely by an agent: a player_action for its turn
        AND a reactive Retreat decision when attacked."""
        st = build_initial_state(rc.SCENARIO_GREAT_REVOLT, seed=1)
        region = "Aedui"
        st["resources"][rc.AEDUI] = 10
        # An Aedui Ally gives the Rally a Warband-placement cap (§3.3.1).
        st["tribes"]["Aedui"]["allied_faction"] = rc.AEDUI
        place_piece(st, region, rc.AEDUI, rc.ALLY)
        place_piece(st, region, rc.AEDUI, rc.WARBAND, count=3)
        refresh_all_control(st)
        # The agent: Rally on the Aedui's own turn; for any Retreat, decline.
        def agent(state, faction, request):
            if request["kind"] == RETREAT:
                return {"retreat": False, "region": None}
            return None
        st["decision_agent"] = agent
        # Top-level turn via a player_action (the same path the CLI/LLM uses).
        plan = {"command": "Rally", "regions": [], "sa": "No SA",
                "sa_regions": [], "details": {"rally_plan": {
                    "citadels": [], "allies": [], "warbands": [region]}}}
        res = execute_decision(st, rc.AEDUI, {"player_action": plan})
        assert res["executed"] is True
        assert count_pieces(st, region, rc.AEDUI, rc.WARBAND) > 3
        assert validate_state(st) == []


def test_no_agent_game_is_deterministic_and_valid():
    """The all-bot harness (no decision_agent) is unchanged: identical games."""
    def play(seed):
        st = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=seed)
        st["non_player_factions"] = set(get_sop_factions(st))
        dfn = make_decision_func({f: "bot" for f in get_sop_factions(st)},
                                 pause=False)
        with contextlib.redirect_stdout(io.StringIO()):
            run_game(st, decision_func=dfn, execute=True)
        st.pop("rng", None)
        return st
    a, b = play(7), play(7)
    assert a == b
    assert validate_state(a) == []


def _agent_turn_policy(state, faction):
    """A tiny self-judgment policy: prefer a Raid, else a Rally, else Pass —
    each candidate VALIDATED via the moves API before it is chosen. Returns a
    player_action dict, or None to Pass."""
    from fs_bot.engine import moves
    # Raid where the Faction has a Warband and an enemy is present.
    for region in moves.regions_with_pieces(state, faction):
        if count_pieces(state, region, faction, rc.WARBAND) <= 0:
            continue
        enemies = moves.enemies_in_region(state, region, faction)
        target = enemies[0] if enemies else None
        plan = {"command": "Raid", "regions": [], "sa": "No SA",
                "sa_regions": [], "details": {"raid_plan": [
                    {"region": region, "target": target}]}}
        if moves.validate_player_action(state, faction, plan)[0]:
            return plan
    # Else Rally, placing Warbands where able.
    for region in moves.regions_with_pieces(state, faction):
        plan = {"command": "Rally", "regions": [], "sa": "No SA",
                "sa_regions": [], "details": {"rally_plan": {
                    "citadels": [], "allies": [], "warbands": [region]}}}
        if moves.validate_player_action(state, faction, plan)[0]:
            return plan
    return None


def test_full_game_with_one_agent_controlled_faction():
    """End to end: the Aedui are driven by the agent policy + reactive agent;
    the other Factions by the bots. The game completes with a valid state."""
    from fs_bot.bots.bot_dispatch import dispatch_bot_turn
    from fs_bot.cli.dispatcher import _translate_bot_action
    from fs_bot.engine.game_engine import ACTION_PASS, ACTION_COMMAND, ACTION_EVENT
    AGENT = rc.AEDUI

    st = setup_scenario(rc.SCENARIO_GREAT_REVOLT, seed=5)
    st["non_player_factions"] = set(get_sop_factions(st))

    # Reactive agent for the Aedui: retreat when able, refuse agreements.
    def reactive(state, faction, request):
        if faction != AGENT:
            return None
        if request["kind"] == RETREAT:
            legal = request["legal_regions"]
            return {"retreat": bool(legal),
                    "region": legal[0] if legal else None}
        if request["kind"] == AGREEMENT:
            return False
        return None
    st["decision_agent"] = reactive

    def decision_func(state, faction, options, position):
        if faction == AGENT:
            if ACTION_COMMAND in options:
                pa = _agent_turn_policy(state, faction)
                if pa is not None:
                    return {"action": ACTION_COMMAND, "player_action": pa}
            return {"action": ACTION_PASS}
        # Bots drive the rest.
        state["current_card_id"] = state.get("current_card")
        state["is_second_eligible"] = (position == "2nd_eligible")
        state["can_play_event"] = (ACTION_EVENT in options)
        ba = dispatch_bot_turn(state, faction)
        return {"action": _translate_bot_action(ba, options), "bot_action": ba}

    with contextlib.redirect_stdout(io.StringIO()):
        run_game(st, decision_func=decision_func, execute=True)
    assert validate_state(st) == []
