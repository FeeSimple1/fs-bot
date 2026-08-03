"""Regression tests from the knock-on / persistent-card-effect audit.

The audit swept every event_modifiers flag for set-without-read gaps and
every timed card wording against its implementation. Five genuine defects
surfaced; each gets a regression test here:

1. "Executing Faction Eligible" / "Stay Eligible" (cards 6/14 shaded, 46
   shaded, 35 unshaded) was clobbered by the Sec.2.3.6 end-of-card reset —
   the exact mirror of the "Ineligible through next card" bug found via
   the live-playtest transcript audit. Fixed via state["stay_eligible"],
   consumed by adjust_eligibility (forced_ineligible wins conflicts).
2. Card 35 unshaded benefited the *executing* Faction; the card's text and
   Tip make the Romans the beneficiary regardless of who executes it.
3. Card 34 Acco: "free Rallies or Recruits in any 3 Regions" ran the
   Faction's full uncapped Rally plan — an illegal over-grant.
4. Card 44 (Ariovistus) shaded: the free Command is "in Regions placed";
   the placed-region restriction was recorded but never applied.
5. Card 72 Impetuosity unshaded (free March + Arverni/Belgae free Battle
   against the marcher) was set and consumed nowhere — a silent no-op turn
   for the Roman bot, whose event instruction plays that side.
"""

from fs_bot.state.setup import setup_scenario
from fs_bot.state.state_schema import validate_state
from fs_bot.engine.game_engine import (get_sop_factions, adjust_eligibility,
                                       ACTION_EVENT)
from fs_bot.engine.execute import (_execute_event, _resolve_free_actions,
                                   _resolve_card72_march_enemy_battle,
                                   _resolve_free_rally, _plan_region_order,
                                   _constrain_bot_action)
from fs_bot.rules_consts import (SCENARIO_GREAT_REVOLT, ROMANS, ARVERNI,
                                 AEDUI, BELGAE, ELIGIBLE, INELIGIBLE,
                                 EVENT_UNSHADED, EVENT_SHADED)


def _np_state(seed, card=None):
    st = setup_scenario(SCENARIO_GREAT_REVOLT, seed=seed)
    st["non_player_factions"] = set(get_sop_factions(st))
    if card is not None:
        st["current_card"] = card
    return st


def _play(st, faction, card, shaded):
    pref = EVENT_SHADED if shaded else EVENT_UNSHADED
    return _execute_event(st, faction, {
        "command": "Event", "sa": "No SA", "sa_regions": [],
        "details": {"card_id": card, "text_preference": pref}})


class TestStayEligible:
    """Cards 6/14 shaded ("Executing Faction Eligible") and 46 shaded
    ("Stay Eligible"): the executor must remain Eligible through the
    Sec.2.3.6 reset despite having executed the Event."""

    def test_control_event_actor_goes_ineligible(self):
        st = _np_state(203)
        adjust_eligibility(st, {ARVERNI: {"action": ACTION_EVENT}})
        assert st["eligibility"][ARVERNI] == INELIGIBLE

    def test_card14_shaded_executor_stays_eligible(self):
        st = _np_state(203, card=14)
        _play(st, ARVERNI, 14, shaded=True)
        adjust_eligibility(st, {ARVERNI: {"action": ACTION_EVENT}})
        assert st["eligibility"][ARVERNI] == ELIGIBLE
        # Rome's own "Ineligible through next card" clause still holds.
        assert st["eligibility"][ROMANS] == INELIGIBLE
        # One-shot: consumed at the adjustment, not persistent.
        assert not st.get("stay_eligible")
        adjust_eligibility(st, {ARVERNI: {"action": ACTION_EVENT}})
        assert st["eligibility"][ARVERNI] == INELIGIBLE

    def test_card6_shaded_executor_stays_eligible(self):
        st = _np_state(204, card=6)
        _play(st, BELGAE, 6, shaded=True)
        adjust_eligibility(st, {BELGAE: {"action": ACTION_EVENT}})
        assert st["eligibility"][BELGAE] == ELIGIBLE
        assert st["eligibility"][ROMANS] == INELIGIBLE

    def test_card46_shaded_executor_stays_eligible(self):
        st = _np_state(205, card=46)
        _play(st, AEDUI, 46, shaded=True)
        adjust_eligibility(st, {AEDUI: {"action": ACTION_EVENT}})
        assert st["eligibility"][AEDUI] == ELIGIBLE

    def test_forced_ineligibility_beats_stay_eligible(self):
        """If the same Faction is under an explicit 'Ineligible through
        next card' clause, the specific penalty wins the conflict."""
        st = _np_state(206, card=14)
        st["executing_faction"] = ROMANS
        _play(st, ROMANS, 14, shaded=True)
        adjust_eligibility(st, {ROMANS: {"action": ACTION_EVENT}})
        assert st["eligibility"][ROMANS] == INELIGIBLE


class TestCard35Beneficiary:
    """Card 35 Gallic Shouts unshaded: 'Romans may look at the next 2
    facedown cards and either execute a free Limited Command or be
    Eligible' — the beneficiary is the Romans whoever executes it."""

    def test_gallic_executor_frees_the_romans(self):
        st = _np_state(210, card=35)
        res = _play(st, ARVERNI, 35, shaded=False)
        fa = [f for f in (res.get("free_actions") or [])
              if f.get("flag") == "card_35"]
        assert fa, "card 35 unshaded produced no free action"
        assert all(f.get("faction") == ROMANS for f in fa)
        assert validate_state(st) == []


class TestCard34RallyCap:
    """Card 34 Acco unshaded: 'free Rallies or Recruits in any 3 Regions'
    — the free Rally must not exceed 3 Regions."""

    def test_plan_region_order_and_cap(self):
        ba = {"command": "Rally", "details": {"rally_plan": {
            "citadels": [{"region": "R1"}],
            "allies": [{"region": "R2"}, {"region": "R3"}],
            "warbands": [{"region": "R4"}, {"region": "R5"},
                         {"region": "R1"}]}}}
        assert _plan_region_order(ba) == ["R1", "R2", "R3", "R4", "R5"]
        capped = _constrain_bot_action(ba, set(["R1", "R2", "R3"]))
        rp = capped["details"]["rally_plan"]
        kept = {e["region"] for k in rp for e in rp[k]}
        assert kept == {"R1", "R2", "R3"}

    def test_card34_touches_at_most_3_regions(self):
        from fs_bot.board.pieces import count_pieces
        from fs_bot.map.map_data import get_playable_regions
        for seed in (151, 220, 221):
            st = _np_state(seed, card=34)
            regions = list(get_playable_regions(
                st["scenario"], st.get("capabilities")))
            before = {r: count_pieces(st, r, ARVERNI) for r in regions}
            res = _play(st, ARVERNI, 34, shaded=False)
            changed = {r for r in regions
                       if count_pieces(st, r, ARVERNI) != before[r]}
            assert len(changed) <= 3, (seed, sorted(changed))
            assert validate_state(st) == []

    def test_free_rally_max_regions_param(self):
        st = _np_state(222)
        from fs_bot.board.pieces import count_pieces
        from fs_bot.map.map_data import get_playable_regions
        regions = list(get_playable_regions(
            st["scenario"], st.get("capabilities")))
        before = {r: count_pieces(st, r, BELGAE) for r in regions}
        res = _resolve_free_rally(st, BELGAE, max_regions=1)
        if res.get("executed"):
            changed = {r for r in regions
                       if count_pieces(st, r, BELGAE) != before[r]}
            assert len(changed) <= 1, sorted(changed)
        assert validate_state(st) == []


class TestCard44aRegionRestriction:
    """Card 44 (Ariovistus) shaded: the free Command is 'in Regions
    placed' — the recorded placement Regions must reach the chooser."""

    def test_placed_regions_passed_to_free_command(self, monkeypatch):
        import fs_bot.engine.execute as exe
        st = _np_state(230)
        st.setdefault("event_modifiers", {})
        st["event_modifiers"]["card_44a_free_command"] = True
        st["event_modifiers"]["card_44a_command_regions"] = ["Treveri"]
        seen = {}

        def recorder(state, faction, **kw):
            seen.update(kw)
            return {"executed": False, "reason": "recorder"}

        monkeypatch.setattr(exe, "_resolve_free_command", recorder)
        exe._resolve_free_actions(st, BELGAE)
        assert seen.get("allowed_regions") == {"Treveri"}

    def test_no_placement_falls_back_board_wide(self, monkeypatch):
        import fs_bot.engine.execute as exe
        st = _np_state(231)
        st.setdefault("event_modifiers", {})
        st["event_modifiers"]["card_44a_free_command"] = True
        st["event_modifiers"]["card_44a_command_regions"] = []
        seen = {}

        def recorder(state, faction, **kw):
            seen.update(kw)
            return {"executed": False, "reason": "recorder"}

        monkeypatch.setattr(exe, "_resolve_free_command", recorder)
        exe._resolve_free_actions(st, BELGAE)
        assert seen.get("allowed_regions") is None


class TestCard72Unshaded:
    """Card 72 Impetuosity unshaded: free March into 1 Region, then
    Arverni or Belgae there free Battle against the marcher. Was a
    silent no-op (flag consumed nowhere)."""

    def test_resolver_marches_then_is_battled(self):
        st = _np_state(201)
        out = _resolve_card72_march_enemy_battle(st, ROMANS)
        kinds = [o.get("free_action") for o in out]
        assert "march" in kinds
        battles = [o for o in out if o.get("free_action") == "battle"
                   and "result" in o]
        assert battles, out
        b = battles[0]
        assert b["defender"] == ROMANS
        assert b["attacker"] in (ARVERNI, BELGAE)
        assert validate_state(st) == []

    def test_event_wiring_consumes_the_flag(self):
        st = _np_state(202, card=72)
        res = _play(st, ROMANS, 72, shaded=False)
        fa = [f for f in (res.get("free_actions") or [])
              if f.get("flag") == "card_72"]
        assert fa, "card 72 unshaded produced no free action"
        assert validate_state(st) == []

    def test_both_present_executor_picks_weaker_battler(self):
        """Sec.5.1: the executing Faction makes the selection; a
        Non-player selects to benefit itself (8.3.1) — with both Arverni
        and Belgae present, the one with FEWER Warbands attacks."""
        from fs_bot.board.pieces import (count_pieces, remove_piece,
                                         place_piece)
        from fs_bot.map.map_data import get_playable_regions, get_adjacent
        from fs_bot.rules_consts import WARBAND, AUXILIA
        st = _np_state(233)
        regions = list(get_playable_regions(st["scenario"],
                                            st.get("capabilities")))
        # Strip all Arverni/Belgae Warbands, then build oneboth-present bait.
        for r in regions:
            for f in (ARVERNI, BELGAE):
                n = count_pieces(st, r, f, WARBAND)
                if n:
                    remove_piece(st, r, f, WARBAND, count=n)
        B = next(r for r in regions
                 if any(a in regions for a in
                        get_adjacent(r, st["scenario"])))
        S = next(a for a in get_adjacent(B, st["scenario"]) if a in regions)
        place_piece(st, B, ARVERNI, WARBAND, count=4)
        place_piece(st, B, BELGAE, WARBAND, count=1)
        place_piece(st, S, ROMANS, AUXILIA, count=4)
        out = _resolve_card72_march_enemy_battle(st, ROMANS)
        battles = [o for o in out if o.get("free_action") == "battle"
                   and "result" in o]
        assert battles and battles[0]["attacker"] == BELGAE, out

    def test_no_target_reports_cleanly(self):
        """With no Arverni/Belgae Warbands anywhere, the resolver reports
        an ineffective action instead of crashing or half-executing."""
        from fs_bot.board.pieces import count_pieces, remove_piece
        from fs_bot.map.map_data import get_playable_regions
        from fs_bot.rules_consts import WARBAND
        st = _np_state(232)
        for r in get_playable_regions(st["scenario"],
                                      st.get("capabilities")):
            for f in (ARVERNI, BELGAE):
                n = count_pieces(st, r, f, WARBAND)
                if n:
                    remove_piece(st, r, f, WARBAND, count=n)
        out = _resolve_card72_march_enemy_battle(st, ROMANS)
        assert len(out) == 1 and out[0]["executed"] is False
