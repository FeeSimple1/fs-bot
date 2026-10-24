"""Tests for the player-action fuzzer (fs_bot.tools.player_fuzz).

The fuzzer is the acceptance instrument for the human-facing action space:
random-legal players in random seats, randomized reactive decisions, with
crash / structural / dry-vs-live divergence / replay-determinism oracles.
"""
import pytest

import fs_bot.rules_consts as rc
from fs_bot.tools.player_fuzz import (play_game, make_random_reactive,
                                      _pick_seats, _sig)


def test_pick_seats_deterministic_and_nonempty():
    import random
    factions = sorted((rc.ROMANS, rc.ARVERNI, rc.AEDUI, rc.BELGAE))
    for seed in range(30):
        a = _pick_seats(factions, random.Random(f"x|{seed}"))
        b = _pick_seats(factions, random.Random(f"x|{seed}"))
        assert a == b
        assert a and set(a) <= set(factions)


def test_random_reactive_response_shapes():
    import random
    from fs_bot.engine.agent import RETREAT, LOSS_ORDER, AGREEMENT
    rng = random.Random(1)
    agent = make_random_reactive([rc.BELGAE], rng)
    # Non-seated faction defers.
    assert agent({}, rc.ROMANS, {"kind": AGREEMENT}) is None
    # RETREAT: dict with retreat/region, region legal or None.
    for _ in range(20):
        r = agent({}, rc.BELGAE, {"kind": RETREAT,
                                  "legal_regions": ["R1", "R2"]})
        assert set(r) == {"retreat", "region"}
        assert (r["region"] in ("R1", "R2")) if r["retreat"] else \
            (r["region"] is None)
    # LOSS_ORDER: subset/permutation of the offered pieces.
    pieces = [("Warband", "Hidden"), ("Warband", "Revealed"), ("Ally", None)]
    for _ in range(20):
        out = agent({}, rc.BELGAE, {"kind": LOSS_ORDER, "pieces": pieces})
        assert 1 <= len(out) <= len(pieces)
        assert all(p in pieces for p in out)
    # AGREEMENT: bool.
    assert isinstance(agent({}, rc.BELGAE, {"kind": AGREEMENT}), bool)


def test_sig_distinguishes_outcomes():
    ok = _sig({"executed": True, "errors": []})
    err = _sig({"executed": True, "errors": [{"region": "X", "error": "e"}]})
    failed = _sig({"executed": False, "errors": []})
    assert len({ok, err, failed}) == 3
    assert _sig("not a dict") is None


@pytest.mark.parametrize('phase', ['placement', 'removal', 'march'])
def test_random_diviciacus_choices_cover_native_borrowed_and_mixed_counts(phase):
    import random
    from fs_bot.engine.diviciacus import DIVICIACUS_PIECES, validate_response
    request = {'kind': DIVICIACUS_PIECES, 'phase': phase,
               'region': rc.CARNUTES, 'piece_type': rc.AUXILIA, 'count': 3,
               'available': {rc.ROMANS: 4, rc.AEDUI: 3}}
    observed, responses = set(), []
    agent = make_random_reactive([rc.ROMANS], random.Random(38))
    for _ in range(64):
        response = agent({}, rc.ROMANS, request)
        assert validate_response(request, response) == response
        observed.add((response['counts'].get(rc.ROMANS, 0),
                      response['counts'].get(rc.AEDUI, 0)))
        responses.append(response)
    assert observed == {(0, 3), (1, 2), (2, 1), (3, 0)}
    # The same seeded choices survive either request dictionary order.
    replay = make_random_reactive([rc.ROMANS], random.Random(38))
    reordered = dict(request, available={rc.AEDUI: 3, rc.ROMANS: 4})
    assert [replay({}, rc.ROMANS, reordered) for _ in range(64)] == responses


@pytest.mark.parametrize('available,count', [
    ({rc.ROMANS: 1, rc.AEDUI: 4}, 4),
    ({rc.ROMANS: 0, rc.AEDUI: 2}, 2),
    ({rc.ROMANS: 2, rc.AEDUI: 0}, 1),
    ({rc.ROMANS: 2, rc.AEDUI: 3}, 5),
])
def test_random_diviciacus_choices_reserve_enough_pieces_for_remaining_owner(available, count):
    import random
    from fs_bot.engine.diviciacus import DIVICIACUS_PIECES, validate_response
    request = {'kind': DIVICIACUS_PIECES, 'count': count, 'available': available}
    agent = make_random_reactive([rc.AEDUI], random.Random(70))
    for _ in range(32):
        response = agent({}, rc.AEDUI, request)
        assert validate_response(request, response) == response
    assert agent({}, rc.ROMANS, request) is None


def test_fuzzed_games_clean_and_replay_deterministic():
    """Smoke: fuzzed mixed player/bot games finish with zero hard findings
    and identical digests on in-process replay (base + Ariovistus). The
    cross-PYTHONHASHSEED digest check runs in the tool/CI, not here (the
    hash seed is fixed per process)."""
    # Seeds include past fuzzer catches: Great Revolt 47 / Ariovistus 27
    # (free-Battle tie hashseed leak), Great Revolt 1 (card 62 dirty
    # event), The Gallic War 73 (card A35 piece_type corruption).
    for scenario, seed in ((rc.SCENARIO_PAX_GALLICA, 1),
                           (rc.SCENARIO_GREAT_REVOLT, 1),
                           (rc.SCENARIO_GREAT_REVOLT, 47),
                           (rc.SCENARIO_ARIOVISTUS, 27),
                           (rc.SCENARIO_GALLIC_WAR, 73)):
        r1 = play_game(scenario, seed)
        assert r1["findings"] == [], (scenario, seed, r1["findings"][:3])
        assert r1["seats"], "at least one seated player per fuzzed game"
        r2 = play_game(scenario, seed)
        assert r2["digest"] == r1["digest"], (scenario, seed)
        assert r2["findings"] == []


@pytest.mark.parametrize("different_live_result", [False, True])
def test_rejected_plans_replan_boundedly_without_hiding_divergence(
        monkeypatch, different_live_result):
    """Refusals do not spend a turn; unmatched live refusals remain defects."""
    from fs_bot.engine import game_engine as ge
    from fs_bot.tools import player_fuzz as fuzz

    monkeypatch.setattr(fuzz, "_pick_seats", lambda *_: [rc.ROMANS])
    # A consistently invalid policy exercises the rejection loop and its
    # bounded fallback. Romans cannot Raid, so this is refused unchanged.
    monkeypatch.setattr(
        fuzz.RandomPlanPolicy, "plan_turn",
        lambda *_: {"action": ge.ACTION_COMMAND, "player_action": {
            "command": "Raid", "regions": [], "details": {}}})
    observed = []

    def one_card(state, decision_func, *, execute):
        state["current_card"] = state["current_card_id"] = 1
        state["next_card"] = 2
        for faction in ge.get_sop_factions(state):
            state["eligibility"][faction] = (
                rc.ELIGIBLE if faction == rc.ROMANS else rc.INELIGIBLE)
        before = state["resources"][rc.ROMANS]
        turn = ge.resolve_card_turn(state, decision_func, execute=execute)
        observed.append((before, state["resources"][rc.ROMANS], turn))
        return {"total_cards_played": 1, "winter_count": 0,
                "card_results": [{"card": 1, "turn_result": turn}]}

    monkeypatch.setattr(fuzz, "run_game", one_card)
    if different_live_result:
        original = ge._maybe_execute

        def divergent_execution(*args, **kwargs):
            try:
                return original(*args, **kwargs)
            except ge.ActionRejected as exc:
                # Change only LIVE resolution; dry-run still reports its
                # original refusal. The fuzzer must retain this finding.
                exc.result["reason"] = "unexpected live-only refusal"
                raise

        monkeypatch.setattr(ge, "_maybe_execute", divergent_execution)

    result = fuzz.play_game(rc.SCENARIO_PAX_GALLICA, 1, events=False)

    assert result["rejected"] == fuzz._MAX_REJECTED_PLANS
    assert result["human_turns"] == fuzz._MAX_REJECTED_PLANS + 1
    before, after, turn = observed[0]
    assert after == before + 2  # Exactly one accepted Pass, no failed costs.
    assert turn["passes"] == [rc.ROMANS]
    assert turn["actions_taken"][rc.ROMANS]["action"] == ge.ACTION_PASS
    # This injected runner deliberately stops after one nonterminal card.
    # The completion oracle must flag that without hiding refusal findings.
    assert sum(f[0] == "incomplete-game" for f in result["findings"]) == 1
    action_findings = [f for f in result["findings"] if f[0] != "incomplete-game"]
    if different_live_result:
        assert len(action_findings) == fuzz._MAX_REJECTED_PLANS
        assert all(f[0] == "divergence" for f in action_findings)
    else:
        assert action_findings == []
