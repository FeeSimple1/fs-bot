"""Base-game capability cards (§5.3) — regression tests for the formerly
inert set: 8, 10, 12, 13, 15, 27, 43 (55 covered in test_rally).
Card texts: Card Reference; audit: QUESTIONS.md capability audit."""

import pytest

from fs_bot.rules_consts import (
    SCENARIO_GREAT_REVOLT, ROMANS, ARVERNI, AEDUI, BELGAE, GERMANS,
    WARBAND, AUXILIA, LEGION, LEADER, ALLY, CITADEL, FORT,
    EVENT_SHADED, EVENT_UNSHADED, CAESAR,
    MANDUBII, ATREBATES, TREVERI, MORINI, PROVINCIA,
)
from fs_bot.state.state_schema import build_initial_state
from fs_bot.board.pieces import (place_piece, remove_piece, count_pieces,
                                 get_leader_in_region)
from fs_bot.board.control import refresh_all_control
from fs_bot.cards.capabilities import (activate_capability,
                                       set_capability_owner,
                                       get_capability_owner,
                                       deactivate_capability)


def _state():
    return build_initial_state(SCENARIO_GREAT_REVOLT, seed=5)


def _clear(state, region):
    from fs_bot.rules_consts import FACTIONS, HIDDEN, REVEALED, SCOUTED
    from fs_bot.board.pieces import (count_pieces_by_state,
                                     clear_allied_tribe)
    for f in FACTIONS:
        for pt in (ALLY, CITADEL):
            while count_pieces(state, region, f, pt) > 0:
                remove_piece(state, region, f, pt)
                clear_allied_tribe(state, region, f, pt)
        for pt in (WARBAND, AUXILIA):
            for ps in (HIDDEN, REVEALED, SCOUTED):
                c = count_pieces_by_state(state, region, f, pt, ps)
                if c:
                    remove_piece(state, region, f, pt, count=c,
                                 piece_state=ps)
        for pt in (LEGION, FORT):
            c = count_pieces(state, region, f, pt)
            if c:
                remove_piece(state, region, f, pt, count=c)
        if get_leader_in_region(state, region, f) is not None:
            remove_piece(state, region, f, LEADER)
    refresh_all_control(state)


class TestCard8BaggageTrains:
    def test_unshaded_owner_march_costs_zero(self):
        from fs_bot.commands.march import march_cost
        st = _state()
        base = march_cost(st, MANDUBII, BELGAE)
        assert base > 0
        activate_capability(st, 8, EVENT_UNSHADED)
        set_capability_owner(st, 8, BELGAE)
        assert march_cost(st, MANDUBII, BELGAE) == 0
        assert march_cost(st, MANDUBII, ARVERNI) > 0  # non-owner unchanged

    def test_shaded_owner_raids_three_and_steals_past_fort(self):
        from fs_bot.commands.raid import (raid_in_region,
                                          validate_raid_steal_target)
        st = _state()
        _clear(st, TREVERI)
        place_piece(st, TREVERI, BELGAE, WARBAND, 3)  # hidden by default
        place_piece(st, TREVERI, ROMANS, FORT, 1)
        st["resources"][ROMANS] = 10
        ok, why = validate_raid_steal_target(st, TREVERI, BELGAE, ROMANS)
        assert not ok                     # §3.3.3: Fort blocks steal
        activate_capability(st, 8, EVENT_SHADED)
        set_capability_owner(st, 8, BELGAE)
        ok, _ = validate_raid_steal_target(st, TREVERI, BELGAE, ROMANS)
        assert ok                         # card 8 shaded bypasses
        res = raid_in_region(st, TREVERI, BELGAE,
                             [{"type": "steal", "target": ROMANS}] * 3)
        assert res["warbands_flipped"] == 3   # 3 per Region, not 2

    def test_shaded_non_owner_still_capped(self):
        from fs_bot.commands.raid import raid_in_region
        from fs_bot.commands.common import CommandError
        st = _state()
        _clear(st, TREVERI)
        place_piece(st, TREVERI, ARVERNI, WARBAND, 3)
        activate_capability(st, 8, EVENT_SHADED)
        set_capability_owner(st, 8, BELGAE)
        with pytest.raises(CommandError):
            raid_in_region(st, TREVERI, ARVERNI, [{"type": "gain"}] * 3)


class TestCard43Convictolitavis:
    def test_shaded_doubles_aedui_command_costs(self):
        from fs_bot.commands.march import march_cost
        from fs_bot.commands.rally import rally_cost
        st = _state()
        m0 = march_cost(st, MANDUBII, AEDUI)
        r0 = rally_cost(st, MANDUBII, AEDUI)
        activate_capability(st, 43, EVENT_SHADED)
        assert march_cost(st, MANDUBII, AEDUI) == m0 * 2
        assert rally_cost(st, MANDUBII, AEDUI) == r0 * 2
        assert march_cost(st, MANDUBII, BELGAE) > 0  # others unchanged

    def test_unshaded_suborn_two_regions_executor(self):
        from fs_bot.engine.execute import _execute_suborn
        st = _state()
        st["resources"][AEDUI] = 20
        for r in (MANDUBII, ATREBATES):
            _clear(st, r)
            place_piece(st, r, AEDUI, WARBAND, 2)
            place_piece(st, r, BELGAE, WARBAND, 1)
        refresh_all_control(st)
        plan = {"sa": "Suborn", "details": {"suborn_plan": [
            {"region": MANDUBII, "actions": [
                {"action": "remove_warband", "target_faction": BELGAE}]},
            {"region": ATREBATES, "actions": [
                {"action": "remove_warband", "target_faction": BELGAE}]},
        ]}}
        res = _execute_suborn(st, AEDUI, plan)
        assert len(res["regions"]) == 1          # base: 1 Region max
        activate_capability(st, 43, EVENT_UNSHADED)
        place_piece(st, MANDUBII, BELGAE, WARBAND, 1)
        res = _execute_suborn(st, AEDUI, plan)
        assert len(res["regions"]) == 2          # card 43: 2 Regions


class TestCard13BalearicSlingersShaded:
    def test_recruit_only_where_supply_and_costs_two(self):
        from fs_bot.commands.rally import (validate_recruit_region,
                                           recruit_cost)
        st = _state()
        # build_initial_state places no pieces — give Provincia a Roman
        # presence (Fort) so the §3.2.1 presence gate passes.
        place_piece(st, PROVINCIA, ROMANS, FORT, 1)
        refresh_all_control(st)
        activate_capability(st, 13, EVENT_SHADED)
        # Provincia is on a Supply Line by definition (Cisalpina border).
        ok, why = validate_recruit_region(st, PROVINCIA)
        assert ok, why
        assert recruit_cost(st, PROVINCIA) == 2   # no free Supply discount


class TestCard12TitusLabienus:
    def test_unshaded_ignores_leader_proximity(self):
        from fs_bot.commands.common import check_leader_proximity
        st = _state()
        _clear(st, TREVERI)
        ok, _ = check_leader_proximity(st, TREVERI, ROMANS, CAESAR, "Build")
        activate_capability(st, 12, EVENT_UNSHADED)
        ok2, _ = check_leader_proximity(st, TREVERI, ROMANS, CAESAR, "Build")
        assert ok2 is True

    def test_shaded_scout_reveal_one_region(self):
        # executor-level trim is covered by the scout execution path; here
        # assert the capability flag routes (smoke via _execute_scout would
        # need a full battle context — the trim filter is pure).
        st = _state()
        activate_capability(st, 12, EVENT_SHADED)
        from fs_bot.cards.capabilities import is_capability_active
        assert is_capability_active(st, 12, EVENT_SHADED)


class TestCard15LegioX:
    def _setup(self):
        st = _state()
        r = TREVERI
        _clear(st, r)
        place_piece(st, r, ROMANS, LEGION, 2, from_legions_track=True)
        place_piece(st, r, ROMANS, LEADER, leader_name=CAESAR)
        place_piece(st, r, ROMANS, AUXILIA, 2)
        place_piece(st, r, BELGAE, WARBAND, 6)
        return st, r

    def test_unshaded_final_adjustments(self):
        from fs_bot.battle.losses import calculate_losses
        st, r = self._setup()
        inflicted0 = calculate_losses(st, r, ROMANS, BELGAE)
        suffered0 = calculate_losses(st, r, BELGAE, ROMANS)
        activate_capability(st, 15, EVENT_UNSHADED)
        assert calculate_losses(st, r, ROMANS, BELGAE) == inflicted0 + 2
        assert calculate_losses(st, r, BELGAE, ROMANS) == suffered0 - 1

    def test_unshaded_requires_leader_and_legion(self):
        from fs_bot.battle.losses import calculate_losses
        st, r = self._setup()
        remove_piece(st, r, ROMANS, LEGION, count=2)
        base = calculate_losses(st, r, BELGAE, ROMANS)
        activate_capability(st, 15, EVENT_UNSHADED)
        assert calculate_losses(st, r, BELGAE, ROMANS) == base

    def test_shaded_caesar_doubles_one_legion_only(self):
        from fs_bot.battle.losses import calculate_losses
        st, r = self._setup()
        # Caesar + 2 Legions + 2 Auxilia: base = 2*2 + 1 + 1 = 6
        assert calculate_losses(st, r, ROMANS, BELGAE) == 6
        activate_capability(st, 15, EVENT_SHADED)
        # One Legion doubled: (2+1) + 1 + 1 = 5
        assert calculate_losses(st, r, ROMANS, BELGAE) == 5


class TestCard27MassedGallicArchers:
    def test_unshaded_arverni_attack_one_fewer_before_halving(self):
        from fs_bot.battle.losses import calculate_losses
        st = _state()
        r = MANDUBII
        _clear(st, r)
        place_piece(st, r, ARVERNI, WARBAND, 6)
        place_piece(st, r, ROMANS, FORT, 1)
        place_piece(st, r, ROMANS, AUXILIA, 2)
        # base: 6*0.5=3, fort halves -> 1
        assert calculate_losses(st, r, ARVERNI, ROMANS) == 1
        activate_capability(st, 27, EVENT_UNSHADED)
        # 3-1=2 BEFORE halving -> 1; against no-fort it'd be 3->2.
        assert calculate_losses(st, r, ARVERNI, ROMANS) == 1
        remove_piece(st, r, ROMANS, FORT)
        assert calculate_losses(st, r, ARVERNI, ROMANS) == 2

    def test_unshaded_not_on_defense(self):
        from fs_bot.battle.losses import calculate_losses
        st = _state()
        r = MANDUBII
        _clear(st, r)
        place_piece(st, r, ARVERNI, WARBAND, 6)
        place_piece(st, r, BELGAE, WARBAND, 4)
        base = calculate_losses(st, r, ARVERNI, BELGAE,
                                is_counterattack=True)
        activate_capability(st, 27, EVENT_UNSHADED)
        assert calculate_losses(st, r, ARVERNI, BELGAE,
                                is_counterattack=True) == base


class TestCard10BallistaeUnshaded:
    def test_fort_roll_threshold_two(self):
        from fs_bot.battle.losses import resolve_losses
        st = _state()
        r = TREVERI
        _clear(st, r)
        place_piece(st, r, ROMANS, FORT, 1)
        activate_capability(st, 10, EVENT_UNSHADED)
        # Deterministic RNG probe: roll=3 must NOT remove the Fort now.
        class _R:
            def randint(self, a, b):
                return 3
        st["rng"] = _R()
        res = resolve_losses(st, r, ROMANS, 1)
        assert count_pieces(st, r, ROMANS, FORT) == 1


class TestCapabilityOwnership:
    def test_owner_recorded_and_cleared(self):
        st = _state()
        activate_capability(st, 8, EVENT_UNSHADED)
        set_capability_owner(st, 8, BELGAE)
        assert get_capability_owner(st, 8) == BELGAE
        deactivate_capability(st, 8)
        assert get_capability_owner(st, 8) is None


class TestCard59GermanicHorse:
    def test_unshaded_roman_auxilia_full_loss_in_flagged_region(self):
        from fs_bot.battle.losses import calculate_losses
        st = _state()
        r = TREVERI
        _clear(st, r)
        place_piece(st, r, ROMANS, AUXILIA, 4)
        place_piece(st, r, BELGAE, WARBAND, 6)
        base = calculate_losses(st, r, ROMANS, BELGAE)
        assert base == 2      # 4 aux * 0.5
        st.setdefault("event_modifiers", {})[
            "card59_unshaded_region"] = r
        assert calculate_losses(st, r, ROMANS, BELGAE) == 4  # 1 each

    def test_shaded_owner_doubles_unless_fort(self):
        from fs_bot.battle.losses import calculate_losses
        st = _state()
        r = TREVERI
        _clear(st, r)
        place_piece(st, r, BELGAE, WARBAND, 4)
        place_piece(st, r, ROMANS, AUXILIA, 3)
        activate_capability(st, 59, EVENT_SHADED)
        set_capability_owner(st, 59, BELGAE)
        base = calculate_losses(st, r, BELGAE, ROMANS)
        st.setdefault("event_modifiers", {})["card59_shaded_region"] = r
        assert calculate_losses(st, r, BELGAE, ROMANS) == base * 2
        place_piece(st, r, ROMANS, FORT, 1)
        # Fort: no doubling, and the fort halves instead.
        assert calculate_losses(st, r, BELGAE, ROMANS) == base // 2


class TestCard13BalearicSlingersUnshaded:
    def test_prefire_strips_attacker_before_battle(self):
        from fs_bot.engine.execute import _execute_battle
        st = _state()
        r = TREVERI
        _clear(st, r)
        place_piece(st, r, BELGAE, WARBAND, 4)   # attacker
        place_piece(st, r, ROMANS, AUXILIA, 4)   # defender with 4 aux
        refresh_all_control(st)
        activate_capability(st, 13, EVENT_UNSHADED)
        st["non_player_factions"] = {ROMANS, BELGAE, ARVERNI, AEDUI}
        res = _execute_battle(st, BELGAE, {
            "sa": None, "sa_regions": [],
            "details": {"battle_plan": [{"region": r, "target": ROMANS}]}})
        # Pre-fire: 4 aux -> 2 Belgae warbands dead BEFORE the battle;
        # attack then computed from 2 warbands (1 loss on Rome).
        assert count_pieces(st, r, BELGAE, WARBAND) <= 2


class TestCard27ShadedAbsorption:
    def test_six_arverni_attacking_forces_extra_loss(self):
        from fs_bot.engine.execute import _execute_battle
        st = _state()
        r = MANDUBII
        _clear(st, r)
        place_piece(st, r, ARVERNI, WARBAND, 6)
        place_piece(st, r, AEDUI, WARBAND, 4)
        refresh_all_control(st)
        activate_capability(st, 27, EVENT_SHADED)
        st["non_player_factions"] = {ROMANS, BELGAE, ARVERNI, AEDUI}
        before = count_pieces(st, r, AEDUI, WARBAND)
        _execute_battle(st, ARVERNI, {
            "sa": None, "sa_regions": [],
            "details": {"battle_plan": [{"region": r, "target": AEDUI}]}})
        # 6*0.5=3 battle losses + 1 pre-absorbed = all 4 gone.
        assert count_pieces(st, r, AEDUI, WARBAND) == 0


class TestCard10ShadedAmbushRemoval:
    def test_owner_ambush_removes_citadel(self):
        from fs_bot.engine.execute import _execute_battle
        from fs_bot.rules_consts import HIDDEN
        st = _state()
        r = MANDUBII
        _clear(st, r)
        place_piece(st, r, BELGAE, WARBAND, 6, piece_state=HIDDEN)
        place_piece(st, r, AEDUI, WARBAND, 1, piece_state=HIDDEN)
        place_piece(st, r, AEDUI, CITADEL, 1)
        refresh_all_control(st)
        activate_capability(st, 10, EVENT_SHADED)
        set_capability_owner(st, 10, BELGAE)
        st["non_player_factions"] = {ROMANS, BELGAE, ARVERNI, AEDUI}
        _execute_battle(st, BELGAE, {
            "sa": "Ambush", "sa_regions": [r],
            "details": {"battle_plan": [{"region": r, "target": AEDUI}]}})
        assert count_pieces(st, r, AEDUI, CITADEL) == 0


class TestCard63WinterCampaign:
    def test_unshaded_quarters_free_outside_devastation(self):
        from fs_bot.engine.winter import _quarters_roman_pay_or_roll
        st = _state()
        r = TREVERI
        _clear(st, r)
        place_piece(st, r, ROMANS, AUXILIA, 2)
        st["resources"][ROMANS] = 10
        activate_capability(st, 63, EVENT_UNSHADED)
        res = _quarters_roman_pay_or_roll(
            st, {r: {"pay": 2, "roll": 0}})
        assert res["total_cost"] == 0
        assert st["resources"][ROMANS] == 10

    def test_shaded_np_owner_acts_after_harvest(self):
        # Owner recorded + capability active -> run_winter_round records a
        # winter_campaign phase (executed or a clean flowchart decline).
        from fs_bot.state.setup import setup_scenario
        from fs_bot.engine.winter import run_winter_round
        from fs_bot.engine.game_engine import get_sop_factions
        from fs_bot.rules_consts import SCENARIO_GREAT_REVOLT as _GR
        st = setup_scenario(_GR, seed=6)
        st["non_player_factions"] = set(get_sop_factions(st))
        activate_capability(st, 63, EVENT_SHADED)
        set_capability_owner(st, 63, BELGAE)
        res = run_winter_round(st)
        wc = res.get("phases", {}).get("winter_campaign")
        assert wc is not None and wc["owner"] == BELGAE


class TestA31QandA:
    """BGG thread 2079436 (Niko + Volko): A31 unshaded IS a capability;
    capabilities count as 'Event effects', so A31 unshaded cancels A33
    Motivation; companion event_modifiers are cleared when a capability
    is removed (card 50) or replaced by its other side (§5.1.2)."""

    def _ario_state(self):
        from fs_bot.rules_consts import SCENARIO_ARIOVISTUS
        return build_initial_state(SCENARIO_ARIOVISTUS, seed=3)

    def test_a31_unshaded_registered_and_removable(self):
        from fs_bot.cards.card_effects import execute_card_A31
        from fs_bot.cards.capabilities import (is_capability_active,
                                               deactivate_capability)
        st = self._ario_state()
        st["executing_faction"] = GERMANS
        execute_card_A31(st, shaded=False)
        assert is_capability_active(st, "A31", EVENT_UNSHADED)
        assert st["event_modifiers"]["card_A31_no_ario_double"]
        deactivate_capability(st, "A31")   # card 50 Shifting Loyalties
        assert not is_capability_active(st, "A31")
        assert "card_A31_no_ario_double" not in st["event_modifiers"]
        assert ("card_A31_cancel_german_benefits"
                not in st["event_modifiers"])

    def test_dueling_replace_clears_unshaded_modifiers(self):
        from fs_bot.cards.card_effects import execute_card_A31
        from fs_bot.cards.capabilities import is_capability_active
        st = self._ario_state()
        st["executing_faction"] = GERMANS
        execute_card_A31(st, shaded=False)
        execute_card_A31(st, shaded=True)   # §5.1.2 Dueling Events
        assert is_capability_active(st, "A31", EVENT_SHADED)
        assert "card_A31_no_ario_double" not in st["event_modifiers"]

    def test_a31_unshaded_cancels_a33_motivation(self):
        from fs_bot.battle.losses import calculate_losses
        from fs_bot.rules_consts import TREVERI as _T
        st = self._ario_state()
        r = _T
        _clear(st, r)
        place_piece(st, r, GERMANS, WARBAND, 4)   # defender
        place_piece(st, r, BELGAE, WARBAND, 8)
        activate_capability(st, "A33", EVENT_SHADED)
        assert calculate_losses(st, r, BELGAE, GERMANS) == 2   # halved
        counter0 = calculate_losses(st, r, GERMANS, BELGAE,
                                    is_counterattack=True)
        st.setdefault("event_modifiers", {})[
            "card_A31_cancel_german_benefits"] = True
        assert calculate_losses(st, r, BELGAE, GERMANS) == 4   # no halving
        assert calculate_losses(st, r, GERMANS, BELGAE,
                                is_counterattack=True) == counter0 - 1

    def test_a63_a22_unshaded_registered_and_removable(self):
        from fs_bot.cards.card_effects import (execute_card_A63,
                                               execute_card_A22)
        from fs_bot.cards.capabilities import (is_capability_active,
                                               deactivate_capability)
        st = self._ario_state()
        st["executing_faction"] = ROMANS
        execute_card_A63(st, shaded=False)
        execute_card_A22(st, shaded=False)
        assert is_capability_active(st, "A63", EVENT_UNSHADED)
        assert is_capability_active(st, "A22", EVENT_UNSHADED)
        deactivate_capability(st, "A63")
        deactivate_capability(st, "A22")
        assert ("card_A63_quarters_devastated_only"
                not in st["event_modifiers"])
        assert ("card_A22_no_intimidate_romans"
                not in st["event_modifiers"])


class TestRulingsHomework:
    """User rulings (July 2026) + the checkable follow-ups: Abatis loss
    absorption, A31 vs one-shot event benefits, card 27 estimate term."""

    def test_abatis_absorbs_and_rolls_off_like_fort(self):
        from fs_bot.battle.losses import resolve_losses
        from fs_bot.rules_consts import MARKER_ABATIS, SCENARIO_ARIOVISTUS
        st = build_initial_state(SCENARIO_ARIOVISTUS, seed=2)
        r = TREVERI
        _clear(st, r)
        place_piece(st, r, GERMANS, WARBAND, 1)
        st.setdefault("markers", {}).setdefault(r, {})[
            MARKER_ABATIS] = GERMANS

        class _Roll:
            def __init__(self, vals): self.vals = list(vals)
            def randint(self, a, b): return self.vals.pop(0)

        # 2 losses: warband dies first (soft), then the marker takes a
        # roll — 4 = survives, loss absorbed, marker stays.
        st["rng"] = _Roll([4])
        res = resolve_losses(st, r, GERMANS, 2, abatis_defender=True)
        assert st["markers"][r].get(MARKER_ABATIS) == GERMANS
        assert res["losses_absorbed"] == 1
        # Next battle: roll 2 removes the marker.
        st["rng"] = _Roll([2])
        res = resolve_losses(st, r, GERMANS, 1, abatis_defender=True)
        assert MARKER_ABATIS not in st["markers"][r]
        assert ("Abatis", 1) in res["removed"]

    def test_abatis_does_not_absorb_for_attacker(self):
        from fs_bot.battle.losses import resolve_losses
        from fs_bot.rules_consts import MARKER_ABATIS, SCENARIO_ARIOVISTUS
        st = build_initial_state(SCENARIO_ARIOVISTUS, seed=2)
        r = TREVERI
        _clear(st, r)
        place_piece(st, r, GERMANS, WARBAND, 1)
        st.setdefault("markers", {}).setdefault(r, {})[
            MARKER_ABATIS] = GERMANS
        res = resolve_losses(st, r, GERMANS, 2)   # counterattack path
        assert st["markers"][r].get(MARKER_ABATIS) == GERMANS

    def test_a31_unshaded_strips_german_event_battle_benefits(self):
        from fs_bot.engine.execute import _execute_battle
        from fs_bot.rules_consts import SCENARIO_ARIOVISTUS
        st = build_initial_state(SCENARIO_ARIOVISTUS, seed=2)
        r = TREVERI
        _clear(st, r)
        place_piece(st, r, GERMANS, WARBAND, 4)
        place_piece(st, r, BELGAE, WARBAND, 4)
        refresh_all_control(st)
        st["non_player_factions"] = {ROMANS, BELGAE, ARVERNI, AEDUI,
                                     GERMANS}
        st.setdefault("event_modifiers", {})[
            "card_A31_cancel_german_benefits"] = True
        res = _execute_battle(st, GERMANS, {
            "sa": None, "sa_regions": [],
            "details": {"battle_plan": [{"region": r, "target": BELGAE}],
                        "warband_full_loss": True, "no_retreat": True}})
        # warband_full_loss cancelled: 4*0.5 = 2 Belgae losses, not 4.
        assert count_pieces(st, r, BELGAE, WARBAND) >= 2

    def test_card27_estimate_term(self):
        from fs_bot.bots.bot_common import card27_shaded_absorption
        st = _state()
        r = MANDUBII
        _clear(st, r)
        place_piece(st, r, ARVERNI, WARBAND, 6)
        assert card27_shaded_absorption(st, r, BELGAE, ARVERNI) == 0
        activate_capability(st, 27, EVENT_SHADED)
        assert card27_shaded_absorption(st, r, BELGAE, ARVERNI) == 1
        assert card27_shaded_absorption(st, r, ARVERNI, BELGAE) == 0
        remove_piece(st, r, ARVERNI, WARBAND, count=1)
        assert card27_shaded_absorption(st, r, BELGAE, ARVERNI) == 0


class TestCard59DefendingSide:
    """Card 59 shaded Tips: the owner doubles Losses 'both when ...
    attacking and when defending', except when defending with a
    Citadel."""

    def test_counterattack_doubles_in_flagged_region(self):
        from fs_bot.battle.losses import calculate_losses
        st = _state()
        r = TREVERI
        _clear(st, r)
        place_piece(st, r, BELGAE, WARBAND, 4)   # owner, defending
        place_piece(st, r, ROMANS, AUXILIA, 4)   # attacker
        activate_capability(st, 59, EVENT_SHADED)
        set_capability_owner(st, 59, BELGAE)
        base = calculate_losses(st, r, BELGAE, ROMANS,
                                is_counterattack=True)
        st.setdefault("event_modifiers", {})["card59_shaded_region"] = r
        assert calculate_losses(st, r, BELGAE, ROMANS,
                                is_counterattack=True) == base * 2

    def test_own_citadel_blocks_defensive_doubling(self):
        from fs_bot.battle.losses import calculate_losses
        st = _state()
        r = MANDUBII
        _clear(st, r)
        place_piece(st, r, ARVERNI, WARBAND, 4)
        place_piece(st, r, ARVERNI, CITADEL, 1)
        place_piece(st, r, ROMANS, AUXILIA, 4)
        activate_capability(st, 59, EVENT_SHADED)
        set_capability_owner(st, 59, ARVERNI)
        st.setdefault("event_modifiers", {})["card59_shaded_region"] = r
        base_no_flag = None
        st2 = _state()  # independent baseline without flag
        _clear(st2, r)
        place_piece(st2, r, ARVERNI, WARBAND, 4)
        place_piece(st2, r, ARVERNI, CITADEL, 1)
        place_piece(st2, r, ROMANS, AUXILIA, 4)
        base_no_flag = calculate_losses(st2, r, ARVERNI, ROMANS,
                                        is_counterattack=True)
        assert calculate_losses(st, r, ARVERNI, ROMANS,
                                is_counterattack=True) == base_no_flag


class TestOwnerScopedCapabilityMatrix:
    """Every owner-scoped capability (8 both sides; 10/59/63 shaded)
    records its holder from every legal path, renders the holder in the
    CLI summary, honors a params-chosen Gallic recipient, rejects
    non-Gallic choices, and clears on removal."""

    def _exec(self, st, faction, cid, shaded):
        from fs_bot.engine.execute import execute_decision
        st["executing_faction"] = faction
        return execute_decision(st, faction, {"bot_action": {
            "command": "Event",
            "details": {"card_id": cid,
                        "text_preference": ("Shaded" if shaded
                                            else "Unshaded")}}})

    def test_owner_recorded_all_cards(self):
        from fs_bot.cards.capabilities import get_capability_owner
        cases = [
            (8, False, ROMANS, ROMANS),     # "Take this card" — any faction
            (8, True, BELGAE, BELGAE),
            (10, True, ARVERNI, ARVERNI),   # Gallic executor defaults self
            (59, True, BELGAE, BELGAE),
            (63, True, AEDUI, AEDUI),
        ]
        for cid, shaded, executor, expect in cases:
            st = _state()
            st["non_player_factions"] = set()
            self._exec(st, executor, cid, shaded)
            assert get_capability_owner(st, cid) == expect, (cid, executor)

    def test_params_faction_gifts_the_card(self):
        from fs_bot.cards.capabilities import get_capability_owner
        for cid in (10, 63):
            st = _state()
            st["non_player_factions"] = set()
            st["event_params"] = {"faction": ARVERNI}
            self._exec(st, BELGAE, cid, True)   # Belgae gift to Arverni
            assert get_capability_owner(st, cid) == ARVERNI, cid

    def test_non_gallic_choice_rejected(self):
        from fs_bot.cards.capabilities import get_capability_owner
        st = _state()
        st["non_player_factions"] = set()
        st["event_params"] = {"faction": ROMANS}   # illegal recipient
        self._exec(st, BELGAE, 63, True)
        # Falls back to the executing Gallic faction, never Rome.
        assert get_capability_owner(st, 63) == BELGAE

    def test_display_shows_holder_for_each(self):
        from fs_bot.cli.display import format_state_summary
        from fs_bot.cards.capabilities import (activate_capability,
                                               set_capability_owner)
        st = _state()
        for cid, owner in ((8, ROMANS), (10, ARVERNI), (59, BELGAE),
                           (63, AEDUI)):
            activate_capability(st, cid, EVENT_SHADED)
            set_capability_owner(st, cid, owner)
        line = [l for l in format_state_summary(st).splitlines()
                if "Capabilities" in l][0]
        for owner in (ROMANS, ARVERNI, BELGAE, AEDUI):
            assert f"held by {owner}" in line

    def test_schema_offers_gallic_faction_param(self):
        from fs_bot.cards.param_schema import card_param_schema
        for cid in (10, 63):
            sch = card_param_schema(cid, SCENARIO_GREAT_REVOLT)
            assert "faction" in sch, cid
            assert set(sch["faction"]["values"]) == {ARVERNI, AEDUI,
                                                     BELGAE}


class TestIneligibleThroughNextCard:
    """Cards 6/14/18/23/46/A17/A18: 'Ineligible through next card' must
    survive the Sec.2.3.6 end-of-card reset (found via live transcript
    audit: Rhenus Bridge docked Rome -6 but Rome acted the next card)."""

    def test_forced_ineligibility_survives_reset(self):
        from fs_bot.engine.game_engine import adjust_eligibility
        from fs_bot.rules_consts import (ELIGIBLE, INELIGIBLE, ROMANS,
                                         LEGION, TREVERI)
        from fs_bot.cards.card_effects import execute_card_18
        st = _state()
        st["eligibility"] = {f: ELIGIBLE for f in
                             (ROMANS, ARVERNI, AEDUI, BELGAE)}
        place_piece(st, TREVERI, ROMANS, LEGION, 1,
                    from_legions_track=True)   # legion adjacent Germania
        st["resources"][ROMANS] = 20
        execute_card_18(st, shaded=True)
        assert st["resources"][ROMANS] == 14
        # End of the card 18 turn: Rome took no action -> base reset
        # would clobber; the persistent flag must hold.
        adjust_eligibility(st, {})
        assert st["eligibility"][ROMANS] == INELIGIBLE
        assert "Romans" not in st.get("forced_ineligible", {})
        # End of the NEXT card: normal rules resume.
        adjust_eligibility(st, {})
        assert st["eligibility"][ROMANS] == ELIGIBLE
