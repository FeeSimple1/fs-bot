"""Tests for the player-action fuzzer (fs_bot.tools.player_fuzz).

The fuzzer is the acceptance instrument for the human-facing action space:
random-legal players in random seats, randomized reactive decisions, with
crash / structural / dry-vs-live divergence / replay-determinism oracles.
"""
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
