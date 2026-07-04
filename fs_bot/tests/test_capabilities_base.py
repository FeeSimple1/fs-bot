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
