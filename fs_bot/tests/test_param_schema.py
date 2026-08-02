"""Tests for cards/param_schema.py — per-card event_params schemas
extracted from handler AST, shared by the CLI prompts and the fuzzer's
success-path generator."""

import random
import re
import inspect

import pytest

import fs_bot.rules_consts as rc
from fs_bot.cards import card_effects as ce
from fs_bot.cards.param_schema import (card_param_schema, generate_params,
                                       kind_values, region_pool, infer_kind)
from fs_bot.state.setup import setup_scenario

BASE = rc.SCENARIO_GREAT_REVOLT
ARIO = rc.SCENARIO_ARIOVISTUS


def test_scalar_and_direction_schema():
    sch = card_param_schema(1, BASE)
    assert sch["senate_direction"]["kind"] == "direction"


def test_entries_schema_includes_rare_fields():
    """Card 62 moves: every entry field the handler reads, incl. the rare
    ones (piece_state, leader_name), plus the coastal region pool."""
    sch = card_param_schema(62, BASE)
    moves = sch["moves"]
    assert moves["kind"] == "entries"
    assert set(moves["entry_fields"]) >= {"from_region", "to_region",
                                          "piece_type", "count",
                                          "piece_state"}
    assert moves["entry_fields"]["piece_state"] == "piece_state"
    assert moves["region_pool"] == "card62_coastal"
    st = setup_scenario(BASE, seed=1)
    pool = region_pool(st, "card62_coastal")
    assert rc.PICTONES in pool and rc.ARVERNI_REGION in pool
    assert "Sequani" not in pool


def test_list_of_scalars_schema():
    sch = card_param_schema(64, BASE)
    assert sch["ally_removals"]["kind"] == "list:tribe"


def test_override_values_and_omit():
    sch = card_param_schema("A35", ARIO)
    assert set(sch["piece_type"]["values"]) == {rc.WARBAND, rc.AUXILIA}
    assert rc.GERMANS not in sch["ally_faction"]["values"]
    sch26 = card_param_schema(26, BASE)
    assert set(sch26["place_faction"]["values"]) == {rc.ROMANS, rc.AEDUI}
    sch71 = card_param_schema(71, BASE)
    assert sch71["colony_tribe_name"]["kind"] == "omit"


def test_schema_covers_every_params_key_all_cards():
    """Consistency sweep: the AST schema finds at least every key a naive
    regex over each handler's source finds — no card's params can go
    schema-invisible as handlers evolve."""
    rx = re.compile(r'params\.get\("([a-z_0-9]+)"')
    handlers = dict(ce._BASE_HANDLERS)
    handlers.update(ce._ARIOVISTUS_HANDLERS)
    missing = []
    for cid, fn in handlers.items():
        want = set(rx.findall(inspect.getsource(fn)))
        got = set(card_param_schema(
            cid, ARIO if isinstance(cid, str) else BASE))
        if not want <= got:
            missing.append((cid, want - got))
    assert not missing, missing


def test_generate_params_typed_and_complete():
    """Generated params: keys from the schema, entries carry every field,
    values drawn from the shared kind vocabulary."""
    st = setup_scenario(ARIO, seed=2)
    rng = random.Random(9)
    for cid in list(ce._BASE_HANDLERS) + list(ce._ARIOVISTUS_HANDLERS):
        sch = card_param_schema(cid, ARIO)
        if not sch:
            continue
        params = generate_params(st, cid, rng, include_p=1.0)
        assert set(params) <= set(sch)
        for key, spec in sch.items():
            if spec["kind"] == "omit":
                assert key not in params
                continue
            assert key in params
            if spec["kind"] == "entries":
                for e in params[key]:
                    assert set(e) == set(spec["entry_fields"])
                    for sub, sk in spec["entry_fields"].items():
                        assert e[sub] in kind_values(st, sk, spec)


def test_infer_kind_vocabulary():
    assert infer_kind("from_region") == "region"
    assert infer_kind("target_factions") == "factions"
    assert infer_kind("from_type") == "piece_type"
    assert infer_kind("piece_state") == "piece_state"
    assert infer_kind("leader_name") == "leader_name"
    assert infer_kind("target_tribes") == "list:tribe"
    assert infer_kind("legions_to_remove") == "count"


def test_card_26_rejects_non_card_placements():
    """Card 26 unshaded places a Roman Ally or an Aedui Ally/Citadel ONLY;
    an arbitrary faction/piece pair used to ally Gergovia's tribe behind a
    non-Ally piece (tribe<->piece desync, schema-fuzz catch)."""
    st = setup_scenario(BASE, seed=3)
    st["executing_faction"] = rc.ARVERNI
    st["event_params"] = {"place_faction": rc.BELGAE,
                          "place_type": rc.WARBAND}
    with pytest.raises(ValueError):
        ce.execute_event(st, 26, shaded=False)
    st2 = setup_scenario(BASE, seed=3)
    st2["executing_faction"] = rc.ARVERNI
    st2["event_params"] = {"place_faction": rc.ROMANS,
                           "place_type": rc.CITADEL}
    with pytest.raises(ValueError):
        ce.execute_event(st2, 26, shaded=False)


def test_card_71_rejects_existing_tribe_name():
    """Card 71's colony name must be new — an existing Tribe's name would
    silently overwrite its allegiance entry (schema-fuzz catch)."""
    st = setup_scenario(BASE, seed=3)
    st["executing_faction"] = rc.ARVERNI
    existing = next(iter(st["tribes"]))
    st["event_params"] = {"region": rc.ARVERNI_REGION,
                          "colony_tribe_name": existing}
    with pytest.raises(ValueError):
        ce.execute_event(st, 71, shaded=False)
    # The default per-Region name is safe and creates a NEW tribe.
    st2 = setup_scenario(BASE, seed=3)
    st2["executing_faction"] = rc.ARVERNI
    st2["event_params"] = {"region": rc.ARVERNI_REGION}
    ce.execute_event(st2, 71, shaded=False)
    assert f"Colony_{rc.ARVERNI_REGION}" in st2["tribes"]


def test_card_40_rejects_non_listed_piece_types():
    """Card 40 unshaded places Warbands/Auxilia/an Ally only, with
    per-Region caps — a fuzzed Citadel placement stranded a backing piece
    with no allied Tribe (player_fuzz catch, Gallic War seed 30)."""
    from fs_bot.board.pieces import count_pieces
    st = setup_scenario(BASE, seed=3)
    st["executing_faction"] = rc.AEDUI
    st["event_params"] = {"placements": [
        {"region": "Provincia", "piece_type": rc.CITADEL, "count": 1,
         "faction": rc.AEDUI}]}
    with pytest.raises(ValueError):
        ce.execute_event(st, 40, shaded=False)
    # Per-Region caps: 5 Warbands requested -> 3 placed.
    st2 = setup_scenario(BASE, seed=3)
    st2["executing_faction"] = rc.ARVERNI
    st2["event_params"] = {"placements": [
        {"region": "Sequani", "piece_type": rc.WARBAND, "count": 5,
         "faction": rc.ARVERNI}]}
    before = count_pieces(st2, "Sequani", rc.ARVERNI, rc.WARBAND)
    ce.execute_event(st2, 40, shaded=False)
    assert count_pieces(st2, "Sequani", rc.ARVERNI,
                        rc.WARBAND) == before + 3
